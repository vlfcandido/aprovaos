"""O comando que gera e valida a justificativa das questões de um tópico (fundação jurídica).

O que é: `justificar_topico(db, topico_slug, gerador, motivo_sem_ia, ...)` (passo 5) — para cada
questão **publicável** do tópico que ainda não tem justificativa: busca os dispositivos já
ligados a ela (`dados.repositorio_citacao.dispositivos_da_questao`); sem nenhum, a questão fica sem
justificativa nesta rodada — **resultado correto, não falha** (regra 1 da tarefa: "toda
justificativa cita um dispositivo ligado; sem dispositivo ligado, não se gera nada"); com
dispositivo, chama o agente `gerador-de-justificativa`, roda o validador mecânico
(`dominio.justificativa.verificar_justificativa_certo_errado`/`_multipla_escolha`) e só grava o
que passou (`dados.repositorio_questao.gravar_justificativa_certo_errado`/
`_alternativas`) — reprovado não grava nada (regra 2). Uma falha do provedor numa questão (rede,
cota, resposta fora do contrato) vira item reprovado com o motivo, e o comando segue para a
próxima — nunca derruba o lote inteiro (o "nunca bloqueia" da arquitetura §8, aplicado aqui
porque não há fallback por regras possível para escrever justificativa).

`main()` é o `argparse` que resolve a IA (`GOOGLE_API_KEY` + teto diário, mesmo padrão de
`motor.curar._escolher_classificador` — comando, não rota, sem usuário autenticado), roda
`justificar_topico` com `asyncio.run`, comita (salvo `--dry-run`) e imprime o relatório.
`--limite` existe para respeitar a cota do free tier num lote específico; o espaçamento entre
chamadas (`_ESPERA_ENTRE_CHAMADAS_S`) respeita o limite por minuto medido para
`gemini-3.6-flash` no passo 12b (`aprovaos.agentes.classificador`, mesmo comentário).

Nenhuma execução acontece em import.

Quando ler: ao rodar a geração de justificativa de um tópico, ou ao investigar por que uma
questão ficou sem justificativa (`sem_dispositivo`, `sem_ia`, ou em `reprovadas`).
"""

import argparse
import asyncio

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.agentes.gerador_de_justificativa import GeradorDeJustificativa, criar_gerador_adk
from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.modelos import Alternativa, Questao
from aprovaos.dados.repositorio_citacao import dispositivos_da_questao
from aprovaos.dados.repositorio_questao import (
    gravar_justificativa_alternativas,
    gravar_justificativa_certo_errado,
    questoes_publicaveis_do_topico,
)
from aprovaos.dados.repositorio_traco import registrar_traco
from aprovaos.dominio.justificativa import (
    AlternativaParaJustificar,
    DispositivoParaJustificar,
    JustificativaCertoErrado,
    QuestaoParaJustificar,
    montar_texto,
    verificar_justificativa_certo_errado,
    verificar_justificativa_multipla_escolha,
)
from aprovaos.roteador.custo import ChamadaLlm
from aprovaos.roteador.teto import TetoDiario

MOTIVO_SEM_CHAVE = "sem GOOGLE_API_KEY"
MOTIVO_TETO = "teto diário atingido"

_ESPERA_ENTRE_CHAMADAS_S = 13.0
"""Espaça as chamadas ao `gemini-3.6-flash` para uma sequência de várias questões não estourar
o limite do free tier por minuto (5 req/min, medido no passo 12b — `aprovaos.agentes.
classificador`); um lote de 6 questões, por exemplo, leva o dobro do tempo de 6 chamadas
instantâneas, mas nunca esbarra no limite."""


class ItemReprovado(BaseModel):
    """Uma questão que teve justificativa gerada, mas reprovada (ou cuja geração falhou).

    Attributes:
        questao_id: chave da questão.
        motivos: os motivos de reprovação do validador mecânico, ou um único motivo
            `"erro na IA: <TipoDaExcecao>"` quando a chamada em si falhou.
    """

    questao_id: str
    motivos: list[str]


class RelatorioJustificacao(BaseModel):
    """O que `justificar_topico` devolve — o que entra no diário da fatia.

    Attributes:
        elegiveis: questões publicáveis do tópico que ainda não tinham justificativa, nesta
            rodada (respeitando `limite`, quando dado).
        sem_dispositivo: dessas, quantas não têm nenhum dispositivo ligado ainda — não passaram
            pelo gerador (regra 1: sem dispositivo, não se gera nada).
        sem_ia: dessas, quantas tinham dispositivo mas não havia IA disponível (`gerador is
            None`) para tentar.
        geradas: quantas chegaram a ter uma resposta do gerador (aprovada ou não).
        aprovadas: quantas passaram no validador mecânico e foram gravadas.
        reprovadas: uma entrada por questão cuja geração falhou ou cuja resposta foi reprovada.
    """

    elegiveis: int
    sem_dispositivo: int
    sem_ia: int
    geradas: int
    aprovadas: int
    reprovadas: list[ItemReprovado]


def _alternativas_da_questao(db: Session, questao_id: object) -> list[Alternativa]:
    """As alternativas (A–E) de uma questão de múltipla escolha, na ordem da letra."""
    return list(
        db.scalars(
            select(Alternativa)
            .where(Alternativa.questao_id == questao_id)
            .order_by(Alternativa.letra)
        ).all()
    )


def _ja_tem_justificativa(db: Session, questao: Questao) -> bool:
    """Se esta questão já tem justificativa gravada (idempotência: não regera)."""
    if questao.tipo_item == "certo_errado":
        return questao.justificativa_certo is not None
    return any(a.justificativa is not None for a in _alternativas_da_questao(db, questao.id))


async def justificar_topico(
    db: Session,
    topico_slug: str,
    gerador: GeradorDeJustificativa | None,
    motivo_sem_ia: str | None,
    *,
    espera_entre_chamadas_s: float = _ESPERA_ENTRE_CHAMADAS_S,
    limite: int | None = None,
) -> RelatorioJustificacao:
    """Gera e valida a justificativa de cada questão publicável de `topico_slug`.

    Args:
        db: sessão de banco (faz `add`/`flush`; o `commit` é de quem chama).
        topico_slug: o tópico cujas questões serão justificadas.
        gerador: implementação da porta `GeradorDeJustificativa`, ou `None` quando não há IA
            disponível (sem chave/teto atingido) — nesta rodada, `None` significa "não gera",
            não "usa regras" (não há regras possíveis para este passo).
        motivo_sem_ia: registrado só para o chamador/relatório saber por que não gerou; não
            entra no `RelatorioJustificacao` (fica no log de `main()`).
        espera_entre_chamadas_s: segundos de espera antes de cada chamada ao gerador, exceto a
            primeira — protege o limite por minuto do free tier; `0.0` nos testes.
        limite: quantas questões no máximo processar nesta rodada (cota diária); `None` processa
            todas as elegíveis.

    Returns:
        `RelatorioJustificacao` com o que aconteceu; nunca levanta por falha do provedor numa
        questão individual (vira `ItemReprovado`).
    """
    questoes = [
        q
        for q in questoes_publicaveis_do_topico(db, topico_slug)
        if not _ja_tem_justificativa(db, q)
    ]
    if limite is not None:
        questoes = questoes[:limite]

    sem_dispositivo = 0
    sem_ia = 0
    geradas = 0
    aprovadas = 0
    reprovadas: list[ItemReprovado] = []
    chamou_alguma = False

    for questao in questoes:
        dispositivos_orm = dispositivos_da_questao(db, questao.id)
        if not dispositivos_orm:
            sem_dispositivo += 1
            continue
        if gerador is None:
            sem_ia += 1
            continue

        dispositivos = [
            DispositivoParaJustificar(citacao_canonica=d.citacao_canonica, texto=d.texto)
            for d in dispositivos_orm
        ]
        alternativas_para_prompt: list[AlternativaParaJustificar] | None = None
        gabarito = questao.gabarito
        if questao.tipo_item == "multipla_escolha":
            gabarito = None
            alternativas_para_prompt = [
                AlternativaParaJustificar(letra=a.letra, texto=a.texto, correta=a.correta)
                for a in _alternativas_da_questao(db, questao.id)
            ]

        entrada = QuestaoParaJustificar(
            tipo_item=questao.tipo_item,
            comando=questao.comando,
            texto_apoio=questao.texto_apoio,
            enunciado=questao.enunciado,
            gabarito=gabarito,
            alternativas=alternativas_para_prompt,
            dispositivos=dispositivos,
        )

        if chamou_alguma and espera_entre_chamadas_s:
            await asyncio.sleep(espera_entre_chamadas_s)
        chamou_alguma = True

        try:
            resposta = await gerador.gerar(entrada)
        except Exception as erro:  # noqa: BLE001 — deliberado: uma questão que falhou não pode
            # derrubar o lote inteiro (arquitetura §8, "nunca bloquear"); só o tipo vai para o
            # motivo, para não vazar detalhe do provedor.
            reprovadas.append(
                ItemReprovado(
                    questao_id=str(questao.id), motivos=[f"erro na IA: {type(erro).__name__}"]
                )
            )
            continue
        geradas += 1

        if isinstance(resposta, JustificativaCertoErrado):
            veredito = verificar_justificativa_certo_errado(resposta, dispositivos)
            if not veredito.aprovado:
                reprovadas.append(
                    ItemReprovado(questao_id=str(questao.id), motivos=veredito.motivos)
                )
                continue
            gravar_justificativa_certo_errado(
                db,
                questao,
                certo=montar_texto(resposta.afirmacoes_certo),
                errado=montar_texto(resposta.afirmacoes_errado),
            )
        else:
            letras_esperadas = [a.letra for a in alternativas_para_prompt or []]
            veredito = verificar_justificativa_multipla_escolha(
                resposta, dispositivos, letras_esperadas
            )
            if not veredito.aprovado:
                reprovadas.append(
                    ItemReprovado(questao_id=str(questao.id), motivos=veredito.motivos)
                )
                continue
            textos = {
                alternativa.letra: montar_texto(alternativa.afirmacoes)
                for alternativa in resposta.alternativas
            }
            gravar_justificativa_alternativas(db, questao, textos)
        aprovadas += 1

    return RelatorioJustificacao(
        elegiveis=len(questoes),
        sem_dispositivo=sem_dispositivo,
        sem_ia=sem_ia,
        geradas=geradas,
        aprovadas=aprovadas,
        reprovadas=reprovadas,
    )


def _escolher_gerador(
    db: Session, config: Configuracoes
) -> tuple[GeradorDeJustificativa | None, str | None]:
    """Decide se a IA gera: sem chave ou sem teto → `None` com o motivo; senão o gerador ADK.

    Mesmo padrão de `motor.curar._escolher_classificador` — comando, não rota; a linha de
    `traco` de cada chamada fica com `usuario_id=None`.
    """
    if config.google_api_key is None:
        return None, MOTIVO_SEM_CHAVE
    if not TetoDiario(config.teto_diario_brl).pode_chamar(db, agora_utc()):
        return None, MOTIVO_TETO

    def registrar(chamada: ChamadaLlm) -> None:
        registrar_traco(db, chamada, usuario_id=None)

    return criar_gerador_adk(config, registrar), None


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Gera e valida a justificativa das questões publicáveis de um tópico, ancorada nos "
            "dispositivos legais já ligados a cada uma — fundação jurídica, passo 5."
        )
    )
    parser.add_argument("--topico", required=True, help="slug do tópico a justificar")
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help="processa no máximo N questões nesta rodada (respeita a cota diária do free tier)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="roda a geração, mas não comita (só imprime o relatório)",
    )
    return parser.parse_args(argv)


def _relatar(relatorio: RelatorioJustificacao, motivo_sem_ia: str | None) -> None:
    """Imprime o relatório no formato usado pelo diário da fatia."""
    if motivo_sem_ia is not None:
        print(f"sem IA disponível ({motivo_sem_ia}) — nada será gerado nesta rodada.")
    print(
        f"elegiveis={relatorio.elegiveis} sem_dispositivo={relatorio.sem_dispositivo} "
        f"sem_ia={relatorio.sem_ia} geradas={relatorio.geradas} aprovadas={relatorio.aprovadas} "
        f"reprovadas={len(relatorio.reprovadas)}"
    )
    for item in relatorio.reprovadas:
        print(f"  reprovada {item.questao_id}: {'; '.join(item.motivos)}")


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando de justificação por tópico.

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv` (padrão do `argparse`).
        config: configurações explícitas (testes); `None` lê do ambiente/.env.

    Returns:
        `0` sempre que o comando roda até o fim (mesmo sem IA disponível — mensagem clara, sem
        quebrar).
    """
    argumentos = _analisar_argumentos(argv)
    config = config or obter_configuracoes()

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db:
        gerador, motivo_sem_ia = _escolher_gerador(db, config)
        relatorio = asyncio.run(
            justificar_topico(
                db, argumentos.topico, gerador, motivo_sem_ia, limite=argumentos.limite
            )
        )
        if argumentos.dry_run:
            db.rollback()
        else:
            db.commit()
    _relatar(relatorio, motivo_sem_ia)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

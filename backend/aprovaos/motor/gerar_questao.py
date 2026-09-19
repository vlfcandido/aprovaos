"""O comando que gera e valida inéditas de um tópico (fatia 5, RF-11/RF-27/RF-28).

O que é: `gerar_questoes_topico(db, topico_slug, n_pedido, tipo_item, banca_alvo, regra_prova,
gerador, validador, ...)` — para o tópico dado: busca a versão mais recente do `DossieTopico`
(`dados.repositorio_dossie.dossie_mais_recente_do_topico`); monta até cinco originais do mesmo
tópico (`dados.repositorio_questao.questoes_publicaveis_do_topico`) como referência de estilo;
calcula o plano do lote (`dominio.questao_inedita.montar_plano_do_lote`); para cada item do
plano, chama o `gerador-de-questao` **uma vez** com o mecanismo/gabarito já prescritos (Ruling
44), depois chama o `validador-de-questao` (outra família de prompt, que não vê o gabarito do
gerador) e julga (`dominio.validacao_questao.julgar`); grava a `Questao` **sempre** — aprovada
ou reprovada (RF-28: "rejeição registrada com motivo", nunca descartada em silêncio) — e o
veredito em `veredito_questao` (histórico append-only). Ao final, confere o lote inteiro contra o
plano (`dominio.questao_inedita.conferir_lote`) e reporta qualquer divergência.

Uma falha do **gerador** numa chamada (rede, cota, resposta fora do contrato) não produz item
nenhum para gravar — vira `status="erro"` sem `questao_id`, e o lote segue para o próximo item
(o "nunca bloqueia" da arquitetura §8). Uma falha do **validador** já tem um item gerado de
verdade: ele é gravado mesmo assim, sempre `publicavel=False`, com o motivo da falha — a regra 1
do produto ("nada gerado chega ao aluno sem validação") não abre exceção para "o validador não
respondeu": sem validação bem-sucedida, não publica.

`main()` é o `argparse` que resolve a IA (`GOOGLE_API_KEY` + teto diário, mesmo padrão de
`motor.aula`/`motor.justificar`), carrega o DNA do concurso (`dados.repositorio_edital.dna_atual`)
para saber `tipo_item`/`banca_alvo`, roda um ou mais tópicos com `asyncio.run`, comita (salvo
`--dry-run`) e imprime o relatório. Nenhuma execução acontece em import.

Quando ler: ao rodar a geração de inéditas de um tópico, ou ao investigar por que um item saiu
`erro`/`reprovado`, ou por que um lote não bateu com o plano (`divergencias_do_plano`). Plano:
`docs/fatias/5-questoes-ineditas.md`.
"""

import argparse
import asyncio
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.agentes.gerador_de_questao import GeradorDeQuestao, criar_gerador_adk
from aprovaos.agentes.validador_de_questao import ValidadorDeQuestao, criar_validador_adk
from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.modelos import Alternativa, Edital, Topico
from aprovaos.dados.repositorio_dossie import dossie_mais_recente_do_topico
from aprovaos.dados.repositorio_edital import dna_atual
from aprovaos.dados.repositorio_questao import (
    questoes_publicaveis_do_topico,
    salvar_questao_inedita,
)
from aprovaos.dados.repositorio_traco import registrar_traco
from aprovaos.dados.repositorio_veredito import registrar_veredito
from aprovaos.dominio.dna import DnaConcurso
from aprovaos.dominio.dossie import FonteDossie
from aprovaos.dominio.edital import DESCONHECIDO
from aprovaos.dominio.questao import RegraProva
from aprovaos.dominio.questao_inedita import (
    AlternativaGerada,
    EntradaGeradorQuestao,
    OriginalParaGerador,
    QuestaoGerada,
    TipoItem,
    conferir_lote,
    montar_plano_do_lote,
)
from aprovaos.dominio.validacao_questao import (
    AlternativaParaValidador,
    EntradaValidadorQuestao,
    Veredito,
    julgar,
)
from aprovaos.roteador.custo import ChamadaLlm
from aprovaos.roteador.teto import TetoDiario

MOTIVO_SEM_CHAVE = "sem GOOGLE_API_KEY"
MOTIVO_TETO = "teto diário atingido"

_ESPERA_ENTRE_CHAMADAS_S = 13.0
"""Mesmo espaçamento de `motor.justificar`/`motor.aula` — protege o limite por minuto do free
tier; aqui vale a mais, porque cada item consome **duas** chamadas (gerador + validador,
Ruling 44), não uma."""

_LIMITE_ORIGINAIS_DE_REFERENCIA = 5

StatusItem = Literal["aprovado", "reprovado", "erro"]
StatusTopico = Literal["gerado", "sem_topico", "sem_dossie", "sem_ia"]


class ItemGerado(BaseModel):
    """Uma tentativa de gerar um item do lote — o que entra no relatório/diário da fatia.

    Attributes:
        mecanismo: o mecanismo prescrito pelo plano para este item.
        gabarito_alvo: o gabarito prescrito pelo plano para este item.
        status: `"aprovado"` (gravado, `publicavel=True`), `"reprovado"` (gravado,
            `publicavel=False`, com motivo) ou `"erro"` (o gerador falhou; nada foi gravado).
        questao_id: a `Questao` gravada, ou `None` só quando `status="erro"`.
        motivos: os motivos de reprovação/erro; vazio quando `status="aprovado"`.
    """

    mecanismo: str
    gabarito_alvo: str
    status: StatusItem
    questao_id: str | None
    motivos: list[str] = Field(default_factory=list)


class RelatorioGeracaoTopico(BaseModel):
    """O que `gerar_questoes_topico` devolve — o que entra no diário da fatia.

    Attributes:
        topico_slug: o tópico tentado.
        n_pedido: quantos itens foram pedidos.
        status: `"gerado"` (o lote rodou — itens podem ter sido aprovados, reprovados ou
            falhado individualmente), `"sem_topico"`, `"sem_dossie"` ou `"sem_ia"`.
        itens: uma entrada por item do plano, na ordem em que foram tentados; vazio para os
            três status que não chegam a tentar gerar nada.
        divergencias_do_plano: `dominio.questao_inedita.conferir_lote` sobre os itens que de fato
            saíram do gerador (aprovados ou reprovados — não os que deram `erro`); vazio quando
            o lote bateu com o plano.
    """

    topico_slug: str
    n_pedido: int
    status: StatusTopico
    itens: list[ItemGerado] = Field(default_factory=list)
    divergencias_do_plano: list[str] = Field(default_factory=list)


def _buscar_topico(db: Session, slug: str) -> Topico | None:
    """Busca o `Topico` por `slug`, sem levantar — `None` é um resultado válido aqui."""
    return db.scalars(select(Topico).where(Topico.slug == slug)).first()


def _alternativas_da_questao(db: Session, questao_id: UUID) -> list[Alternativa]:
    """As alternativas (A–E) de uma questão original, na ordem da letra."""
    return list(
        db.scalars(
            select(Alternativa)
            .where(Alternativa.questao_id == questao_id)
            .order_by(Alternativa.letra)
        ).all()
    )


def _originais_para_gerador(
    db: Session, topico_slug: str, *, limite: int = _LIMITE_ORIGINAIS_DE_REFERENCIA
) -> list[OriginalParaGerador]:
    """Até `limite` questões publicáveis do tópico, como referência de estilo para o gerador.

    Args:
        db: sessão do comando.
        topico_slug: o tópico cujas originais servem de referência.
        limite: quantas originais no máximo oferecer (a skill pede até 5).

    Returns:
        As `OriginalParaGerador` correspondentes, na mesma ordem de
        `questoes_publicaveis_do_topico`; vazia se o tópico não tiver nenhuma publicável (o caso
        normal do Ruling 45 — o tópico só é encomendado quando `publicaveis == 0`).
    """
    originais: list[OriginalParaGerador] = []
    for questao in questoes_publicaveis_do_topico(db, topico_slug)[:limite]:
        alternativas: list[AlternativaGerada] | None = None
        if questao.tipo_item == "multipla_escolha":
            alternativas = [
                AlternativaGerada(letra=a.letra, texto=a.texto)
                for a in _alternativas_da_questao(db, questao.id)
            ]
        originais.append(
            OriginalParaGerador(
                enunciado=questao.enunciado,
                gabarito=questao.gabarito or "",
                alternativas=alternativas,
            )
        )
    return originais


async def gerar_questoes_topico(
    db: Session,
    topico_slug: str,
    n_pedido: int,
    tipo_item: TipoItem,
    banca_alvo: str,
    regra_prova: RegraProva,
    gerador: GeradorDeQuestao | None,
    validador: ValidadorDeQuestao | None,
    *,
    espera_entre_chamadas_s: float = _ESPERA_ENTRE_CHAMADAS_S,
) -> RelatorioGeracaoTopico:
    """Gera e valida o lote de `n_pedido` inéditas de `topico_slug`.

    Args:
        db: sessão de banco (faz `add`/`flush`; o `commit` é de quem chama).
        topico_slug: o tópico a encomendar.
        n_pedido: quantos itens pedir (o plano decide mecanismo/gabarito de cada um).
        tipo_item: `"certo_errado"` ou `"multipla_escolha"` (do `DnaConcurso.regra_correcao`).
        banca_alvo: a banca cujo estilo os itens devem imitar (do `DnaConcurso.concurso.banca`).
        regra_prova: a regra de correção a gravar em cada `Questao` (do DNA, quando conhecida).
        gerador: implementação da porta `GeradorDeQuestao`, ou `None` sem IA disponível.
        validador: implementação da porta `ValidadorDeQuestao`, ou `None` sem IA disponível.
        espera_entre_chamadas_s: segundos de espera antes de cada chamada ao gerador, exceto a
            primeira do lote — protege o limite por minuto do free tier; `0.0` nos testes.

    Returns:
        `RelatorioGeracaoTopico` com o que aconteceu; nunca levanta por falha do provedor numa
        chamada individual.
    """
    topico = _buscar_topico(db, topico_slug)
    if topico is None:
        return RelatorioGeracaoTopico(
            topico_slug=topico_slug, n_pedido=n_pedido, status="sem_topico"
        )

    dossie = dossie_mais_recente_do_topico(db, topico.id)
    if dossie is None:
        return RelatorioGeracaoTopico(
            topico_slug=topico_slug, n_pedido=n_pedido, status="sem_dossie"
        )

    if gerador is None or validador is None:
        return RelatorioGeracaoTopico(topico_slug=topico_slug, n_pedido=n_pedido, status="sem_ia")

    fontes = [FonteDossie.model_validate(f) for f in dossie.fontes]
    originais = _originais_para_gerador(db, topico_slug)
    aderencia_medida = len(originais) >= _LIMITE_ORIGINAIS_DE_REFERENCIA
    plano = montar_plano_do_lote(n_pedido, len(originais), tipo_item)

    itens: list[ItemGerado] = []
    gerados: list[QuestaoGerada] = []
    chamou_alguma = False

    for item_do_plano in plano.itens:
        if chamou_alguma and espera_entre_chamadas_s:
            await asyncio.sleep(espera_entre_chamadas_s)
        chamou_alguma = True

        entrada_gerador = EntradaGeradorQuestao(
            topico_slug=topico_slug,
            banca_alvo=banca_alvo,
            tipo_item=tipo_item,
            fontes=fontes,
            originais=originais,
            mecanismo_alvo=item_do_plano.mecanismo,
            gabarito_alvo=item_do_plano.gabarito,
            aderencia_medida=aderencia_medida,
        )
        try:
            gerado = await gerador.gerar(entrada_gerador)
        except Exception as erro:  # noqa: BLE001 — deliberado: um item que falhou não pode
            # derrubar o lote inteiro (arquitetura §8, "nunca bloquear"); sem item gerado, não há
            # o que gravar — só o motivo entra no relatório.
            itens.append(
                ItemGerado(
                    mecanismo=item_do_plano.mecanismo,
                    gabarito_alvo=item_do_plano.gabarito,
                    status="erro",
                    questao_id=None,
                    motivos=[f"erro na IA (gerador): {type(erro).__name__}"],
                )
            )
            continue
        gerados.append(gerado)

        entrada_validador = EntradaValidadorQuestao(
            tipo_item=gerado.tipo_item,
            comando=gerado.comando,
            enunciado=gerado.enunciado,
            alternativas=(
                [
                    AlternativaParaValidador(letra=a.letra, texto=a.texto)
                    for a in gerado.alternativas
                ]
                if gerado.alternativas is not None
                else None
            ),
            fontes=fontes,
        )
        try:
            resolucao = await validador.resolver(entrada_validador)
        except Exception as erro:  # noqa: BLE001 — mesmo motivo do gerador; o item **existe**
            # (`gerado`), então é gravado mesmo assim — sempre reprovado, nunca publicado sem
            # validação bem-sucedida (regra 1 do produto).
            veredito = Veredito(
                aprovado=False,
                motivos=[f"erro na IA (validador): {type(erro).__name__}"],
                validador_versao="sem-resolucao-independente",
                aderencia_pct=None,
            )
        else:
            veredito = julgar(gerado, fontes, [o.enunciado for o in originais], resolucao.gabarito)

        questao = salvar_questao_inedita(
            db,
            topico_id=topico.id,
            item=gerado,
            publicavel=veredito.aprovado,
            motivo_nao_publicavel=None if veredito.aprovado else "; ".join(veredito.motivos),
            validador_versao=veredito.validador_versao,
            regra_prova=regra_prova,
        )
        registrar_veredito(db, questao.id, veredito)

        itens.append(
            ItemGerado(
                mecanismo=item_do_plano.mecanismo,
                gabarito_alvo=item_do_plano.gabarito,
                status="aprovado" if veredito.aprovado else "reprovado",
                questao_id=str(questao.id),
                motivos=veredito.motivos,
            )
        )

    divergencias = conferir_lote(gerados, plano)
    return RelatorioGeracaoTopico(
        topico_slug=topico_slug,
        n_pedido=n_pedido,
        status="gerado",
        itens=itens,
        divergencias_do_plano=divergencias,
    )


async def _gerar_todos(
    db: Session,
    topico_slugs: list[str],
    n_por_topico: int,
    tipo_item: TipoItem,
    banca_alvo: str,
    regra_prova: RegraProva,
    gerador: GeradorDeQuestao | None,
    validador: ValidadorDeQuestao | None,
) -> list[RelatorioGeracaoTopico]:
    """Gera o lote de cada tópico de `topico_slugs`, na ordem dada."""
    relatorios: list[RelatorioGeracaoTopico] = []
    for slug in topico_slugs:
        relatorios.append(
            await gerar_questoes_topico(
                db, slug, n_por_topico, tipo_item, banca_alvo, regra_prova, gerador, validador
            )
        )
    return relatorios


def _escolher_agentes(
    db: Session, config: Configuracoes
) -> tuple[GeradorDeQuestao | None, ValidadorDeQuestao | None, str | None]:
    """Decide se a IA gera: sem chave ou sem teto → `(None, None, motivo)`; senão os dois agentes.

    Mesmo padrão de `motor.aula._escolher_gerador`/`motor.justificar._escolher_gerador` —
    comando, não rota; a linha de `traco` de cada chamada fica com `usuario_id=None`.
    """
    if config.google_api_key is None:
        return None, None, MOTIVO_SEM_CHAVE
    if not TetoDiario(config.teto_diario_brl).pode_chamar(db, agora_utc()):
        return None, None, MOTIVO_TETO

    def registrar(chamada: ChamadaLlm) -> None:
        registrar_traco(db, chamada, usuario_id=None)

    return criar_gerador_adk(config, registrar), criar_validador_adk(config, registrar), None


def _regra_prova_do_dna(dna: DnaConcurso | None) -> RegraProva:
    """A `RegraProva` a gravar em cada inédita — do DNA quando conhecida, senão um placeholder.

    Args:
        dna: o `DnaConcurso` do edital, ou `None` sem DNA gerado ainda.

    Returns:
        `RegraProva` com `anula_por_erro` do DNA quando ele o declara; `False` com `fonte`
        marcando a ausência, nunca uma suposição silenciosa.
    """
    if dna is not None and dna.regra_correcao.anula_por_erro != DESCONHECIDO:
        return RegraProva(
            anula_por_erro=bool(dna.regra_correcao.anula_por_erro),
            fonte="DNA do concurso",
        )
    return RegraProva(anula_por_erro=False, fonte="inédita — regra de correção desconhecida")


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Gera e valida o lote de inéditas de um ou mais tópicos, via gerador-de-questao + "
            "validador-de-questao — fatia 5 (questões inéditas validadas)."
        )
    )
    parser.add_argument(
        "--edital-id", required=True, help="edital cujo DNA dá o tipo_item/banca dos itens"
    )
    parser.add_argument(
        "--topico", action="append", required=True, help="slug do tópico (repetível)"
    )
    parser.add_argument("--n", type=int, default=3, help="quantos itens pedir por tópico")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="roda a geração, mas não comita (só imprime o relatório)",
    )
    return parser.parse_args(argv)


def _relatar(relatorios: list[RelatorioGeracaoTopico], motivo_sem_ia: str | None) -> None:
    """Imprime o relatório no formato usado pelo diário da fatia."""
    if motivo_sem_ia is not None:
        print(f"sem IA disponível ({motivo_sem_ia}) — nada será gerado nesta rodada.")
    for relatorio in relatorios:
        print(f"{relatorio.topico_slug}: status={relatorio.status} n_pedido={relatorio.n_pedido}")
        for item in relatorio.itens:
            print(
                f"  {item.status} (mecanismo={item.mecanismo}, gabarito_alvo={item.gabarito_alvo}"
                f", questao_id={item.questao_id})"
            )
            for motivo in item.motivos:
                print(f"    - {motivo}")
        for divergencia in relatorio.divergencias_do_plano:
            print(f"  divergência do plano: {divergencia}")


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando de geração de inéditas.

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv` (padrão do `argparse`).
        config: configurações explícitas (testes); `None` lê do ambiente/.env.

    Returns:
        `0` quando o comando roda até o fim; `1` se `--edital-id` não corresponder a nenhum
        edital (erro de uso, não falha de geração).
    """
    argumentos = _analisar_argumentos(argv)
    config = config or obter_configuracoes()

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db:
        edital = db.get(Edital, UUID(argumentos.edital_id))
        if edital is None:
            print(f"edital {argumentos.edital_id!r} não encontrado")
            return 1

        registro_dna = dna_atual(db, edital.concurso_id)
        dna = (
            DnaConcurso.model_validate(registro_dna.conteudo) if registro_dna is not None else None
        )
        if dna is None or dna.regra_correcao.tipo_item == DESCONHECIDO:
            print("edital sem tipo_item conhecido no DNA — rode a V2/analista-de-edital primeiro")
            return 1
        tipo_item: TipoItem = dna.regra_correcao.tipo_item
        banca_alvo = dna.concurso.banca
        regra_prova = _regra_prova_do_dna(dna)

        gerador, validador, motivo_sem_ia = _escolher_agentes(db, config)
        relatorios = asyncio.run(
            _gerar_todos(
                db,
                argumentos.topico,
                argumentos.n,
                tipo_item,
                banca_alvo,
                regra_prova,
                gerador,
                validador,
            )
        )
        if argumentos.dry_run:
            db.rollback()
        else:
            db.commit()
    _relatar(relatorios, motivo_sem_ia)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

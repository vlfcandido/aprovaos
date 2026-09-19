"""O comando que gera e valida a aula de um tópico a partir do dossiê real (fatia 6).

O que é: `gerar_aula_topico(db, topico_slug, gerador, usuario_id, edital_id, ...)` — para o
tópico dado: busca a versão mais recente do `DossieTopico` (direto ou, sem nenhum, por
equivalência com outro tópico — `dados.repositorio_dossie.dossie_mais_recente_do_topico`,
ADR-0041/P-52 — a aula nasce presa a `topico_slug`, mesmo quando o dossiê usado veio de um
equivalente); monta o fio da memória (a) a partir
do histórico real da aluna (`dados.repositorio_fio_memoria.estatisticas_topicos_vistos`),
restrito aos tópicos que também têm dossiê (`dominio.aula.escolher_relacionados`); monta
`como_a_banca_cobra` a partir de questões publicáveis reais do tópico
(`dados.repositorio_questao.questoes_publicaveis_do_topico`); chama o agente `gerador-de-aula`;
roda o validador mecânico (`dominio.aula.verificar_aula`) e só grava
(`dados.repositorio_aula.salvar_aula`) o que passou — reprovado não grava nada (mesmo princípio
de `motor.justificar`). Sem dossiê, sem IA, ou uma falha do provedor numa aula individual vira
relatório com o motivo, nunca derruba o lote (o "nunca bloqueia" da arquitetura §8).

`main()` é o `argparse` que resolve a IA (`GOOGLE_API_KEY` + teto diário, mesmo padrão de
`motor.justificar`/`motor.curar`), resolve o usuário por e-mail (é assim que a rodada real chama
o comando contra a conta de verdade da Linda), roda uma ou mais aulas com `asyncio.run`, comita
(salvo `--dry-run`) e imprime o relatório. Nenhuma execução acontece em import.

Quando ler: ao rodar a geração de aula de um tópico, ou ao investigar por que um tópico ficou sem
aula (`sem_topico`, `sem_dossie`, `sem_ia`, `reprovada` ou `erro`). Plano:
`docs/fatias/6-trilha-e-aulas.md`.
"""

import argparse
import asyncio
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.agentes.gerador_de_aula import GeradorDeAula, criar_gerador_adk
from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.modelos import DossieTopico, Questao, Topico
from aprovaos.dados.repositorio_aula import salvar_aula
from aprovaos.dados.repositorio_conta import buscar_por_email
from aprovaos.dados.repositorio_dossie import dossie_mais_recente_do_topico
from aprovaos.dados.repositorio_fio_memoria import estatisticas_topicos_vistos
from aprovaos.dados.repositorio_questao import questoes_publicaveis_do_topico
from aprovaos.dados.repositorio_topico_relacao import topicos_equivalentes
from aprovaos.dados.repositorio_traco import registrar_traco
from aprovaos.dominio.aula import (
    EntradaGeradorAula,
    QuestaoParaAula,
    escolher_relacionados,
    verificar_aula,
)
from aprovaos.dominio.dossie import FonteDossie
from aprovaos.roteador.custo import ChamadaLlm
from aprovaos.roteador.teto import TetoDiario

MOTIVO_SEM_CHAVE = "sem GOOGLE_API_KEY"
MOTIVO_TETO = "teto diário atingido"

_ESPERA_ENTRE_CHAMADAS_S = 13.0
"""Mesmo espaçamento de `motor.justificar` — protege o limite por minuto do free tier quando
mais de um tópico é gerado na mesma rodada."""

StatusAula = Literal["gerada", "sem_topico", "sem_dossie", "sem_ia", "reprovada", "erro"]


class RelatorioAula(BaseModel):
    """O que `gerar_aula_topico` devolve para um tópico — o que entra no diário da fatia.

    Attributes:
        topico_slug: o tópico tentado.
        status: `"gerada"` (aprovada e publicada), `"sem_topico"` (slug não cadastrado),
            `"sem_dossie"` (tópico sem `DossieTopico` ainda), `"sem_ia"` (`gerador is None`),
            `"reprovada"` (o validador mecânico recusou) ou `"erro"` (falha do provedor).
        motivos: os motivos de reprovação do validador, ou `["erro na IA: <TipoDaExcecao>"]`
            quando a chamada em si falhou; vazio nos demais status.
    """

    topico_slug: str
    status: StatusAula
    motivos: list[str] = Field(default_factory=list)


def _buscar_topico(db: Session, slug: str) -> Topico | None:
    """Busca o `Topico` por `slug`, sem levantar — `None` é um resultado válido aqui."""
    return db.scalars(select(Topico).where(Topico.slug == slug)).first()


def _dossies_relacionados(
    db: Session, excluir_topico_id: UUID
) -> tuple[dict[UUID, str], dict[UUID, str]]:
    """Trecho representativo (F1 da versão mais recente) e slug de cada tópico com dossiê.

    Só tópicos diferentes de `excluir_topico_id` (o tópico da aula) **e** dos equivalentes a ele
    (ADR-0041) entram — nunca a aula cita a si mesma como "relacionada", nem mesmo travestida no
    slug de outro edital que cobre o mesmo assunto por `topico_relacao`. Um dossiê sem nenhuma
    fonte é ignorado (não há trecho para oferecer).

    Args:
        db: sessão do comando.
        excluir_topico_id: o tópico desta aula.

    Returns:
        `(trechos_por_topico, slugs_por_topico)`, ambos por `topico_id` — a entrada de
        `dominio.aula.escolher_relacionados`.
    """
    excluidos = {excluir_topico_id, *topicos_equivalentes(db, excluir_topico_id)}
    versao_maxima = (
        select(DossieTopico.topico_id, func.max(DossieTopico.versao).label("versao_max"))
        .where(DossieTopico.topico_id.not_in(excluidos))
        .group_by(DossieTopico.topico_id)
        .subquery()
    )
    consulta = (
        select(DossieTopico, Topico.slug)
        .join(
            versao_maxima,
            (DossieTopico.topico_id == versao_maxima.c.topico_id)
            & (DossieTopico.versao == versao_maxima.c.versao_max),
        )
        .join(Topico, Topico.id == DossieTopico.topico_id)
    )
    trechos: dict[UUID, str] = {}
    slugs: dict[UUID, str] = {}
    for dossie, slug in db.execute(consulta).all():
        if not dossie.fontes:
            continue
        trechos[dossie.topico_id] = dossie.fontes[0]["trecho"]
        slugs[dossie.topico_id] = slug
    return trechos, slugs


def _formatar_origem(questao: Questao) -> str | None:
    """`"<banca> <ano> <órgão em minúsculas> item <nº>"`, ou `None` sem `origem` (inédita)."""
    if questao.origem is None:
        return None
    return (
        f"{questao.banca} {questao.origem['ano']} {questao.origem['orgao'].lower()} "
        f"item {questao.origem['numero_item']}"
    )


async def gerar_aula_topico(
    db: Session,
    topico_slug: str,
    gerador: GeradorDeAula | None,
    usuario_id: UUID,
    edital_id: UUID,
    *,
    tempo_alvo_min: int = 25,
    limite_relacionados: int = 1,
    limite_questoes_banca: int = 5,
) -> RelatorioAula:
    """Gera e valida a aula de `topico_slug`, publicando-a se o validador aprovar.

    Args:
        db: sessão de banco (faz `add`/`flush`; o `commit` é de quem chama).
        topico_slug: o tópico a montar.
        gerador: implementação da porta `GeradorDeAula`, ou `None` quando não há IA disponível.
        usuario_id: a aluna cujo histórico alimenta o fio da memória (a).
        edital_id: o edital que escopa `estatisticas_topicos_vistos` (mesma restrição do fio da
            memória da V5).
        tempo_alvo_min: minutos-alvo da aula.
        limite_relacionados: quantos tópicos relacionados tentar reunir (padrão 1).
        limite_questoes_banca: quantas questões publicáveis reais oferecer para
            `como_a_banca_cobra` (padrão 5).

    Returns:
        `RelatorioAula` com o que aconteceu; nunca levanta por falha do provedor.
    """
    topico = _buscar_topico(db, topico_slug)
    if topico is None:
        return RelatorioAula(topico_slug=topico_slug, status="sem_topico")

    dossie = dossie_mais_recente_do_topico(db, topico.id)
    if dossie is None:
        return RelatorioAula(topico_slug=topico_slug, status="sem_dossie")

    if gerador is None:
        return RelatorioAula(topico_slug=topico_slug, status="sem_ia")

    fontes = [FonteDossie.model_validate(f) for f in dossie.fontes]

    questoes_reais = questoes_publicaveis_do_topico(db, topico_slug)[:limite_questoes_banca]
    questoes_para_aula: list[QuestaoParaAula] = []
    for questao in questoes_reais:
        origem = _formatar_origem(questao)
        if origem is not None:
            questoes_para_aula.append(QuestaoParaAula(origem=origem, enunciado=questao.enunciado))
    origens_permitidas = {q.origem for q in questoes_para_aula}

    estatisticas = estatisticas_topicos_vistos(db, usuario_id, edital_id)
    trechos_por_topico, slugs_por_topico = _dossies_relacionados(db, topico.id)
    relacionados_entrada = escolher_relacionados(
        topico.id,
        estatisticas,
        trechos_por_topico=trechos_por_topico,
        slugs_por_topico=slugs_por_topico,
        agora=agora_utc(),
        quantidade=limite_relacionados,
    )

    entrada = EntradaGeradorAula(
        topico_slug=topico_slug,
        fontes=fontes,
        relacionados=relacionados_entrada,
        questoes_como_banca=questoes_para_aula,
        tempo_alvo_min=tempo_alvo_min,
    )

    try:
        conteudo = await gerador.gerar(entrada)
    except Exception as erro:  # noqa: BLE001 — deliberado: uma aula que falhou não pode
        # derrubar o lote inteiro (arquitetura §8, "nunca bloquear"); só o tipo vai para o
        # motivo, para não vazar detalhe do provedor.
        return RelatorioAula(
            topico_slug=topico_slug, status="erro", motivos=[f"erro na IA: {type(erro).__name__}"]
        )

    veredito = verificar_aula(
        conteudo,
        fontes=fontes,
        relacionados_permitidos={r.topico_slug for r in relacionados_entrada},
        origens_permitidas=origens_permitidas,
        tempo_alvo_min=tempo_alvo_min,
        trechos_relacionados_esperados={
            r.topico_slug: r.trecho_do_dossie_relacionado for r in relacionados_entrada
        },
    )
    if not veredito.aprovado:
        return RelatorioAula(topico_slug=topico_slug, status="reprovada", motivos=veredito.motivos)

    salvar_aula(db, topico_id=topico.id, dossie=dossie, conteudo=conteudo)
    return RelatorioAula(topico_slug=topico_slug, status="gerada")


async def _gerar_todas(
    db: Session,
    topico_slugs: list[str],
    gerador: GeradorDeAula | None,
    usuario_id: UUID,
    edital_id: UUID,
    *,
    tempo_alvo_min: int,
    espera_entre_chamadas_s: float = _ESPERA_ENTRE_CHAMADAS_S,
) -> list[RelatorioAula]:
    """Gera a aula de cada tópico de `topico_slugs`, espaçando as chamadas ao provedor."""
    relatorios: list[RelatorioAula] = []
    for indice, slug in enumerate(topico_slugs):
        if indice > 0 and gerador is not None and espera_entre_chamadas_s:
            await asyncio.sleep(espera_entre_chamadas_s)
        relatorios.append(
            await gerar_aula_topico(
                db, slug, gerador, usuario_id, edital_id, tempo_alvo_min=tempo_alvo_min
            )
        )
    return relatorios


def _escolher_gerador(
    db: Session, config: Configuracoes
) -> tuple[GeradorDeAula | None, str | None]:
    """Decide se a IA gera: sem chave ou sem teto → `None` com o motivo; senão o gerador ADK.

    Mesmo padrão de `motor.justificar._escolher_gerador` — comando, não rota; a linha de `traco`
    de cada chamada fica com `usuario_id=None` (é a conta técnica do comando que gera, não a
    conta do request).
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
            "Gera e valida a aula de um ou mais tópicos a partir do dossiê real, com o fio da "
            "memória (a) do histórico de uma aluna — fatia 6 (trilha e aulas em texto)."
        )
    )
    parser.add_argument(
        "--topico", action="append", required=True, help="slug do tópico (repetível)"
    )
    parser.add_argument(
        "--usuario-email", required=True, help="e-mail da conta cujo histórico alimenta o fio (a)"
    )
    parser.add_argument(
        "--edital-id", required=True, help="edital que escopa o histórico (mesmo do fio da V5)"
    )
    parser.add_argument("--tempo-alvo-min", type=int, default=25, help="tamanho-alvo da aula")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="roda a geração, mas não comita (só imprime o relatório)",
    )
    return parser.parse_args(argv)


def _relatar(relatorios: list[RelatorioAula], motivo_sem_ia: str | None) -> None:
    """Imprime o relatório no formato usado pelo diário da fatia."""
    if motivo_sem_ia is not None:
        print(f"sem IA disponível ({motivo_sem_ia}) — nada será gerado nesta rodada.")
    for relatorio in relatorios:
        print(f"{relatorio.topico_slug}: {relatorio.status}")
        for motivo in relatorio.motivos:
            print(f"  {motivo}")


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando de geração de aula.

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv` (padrão do `argparse`).
        config: configurações explícitas (testes); `None` lê do ambiente/.env.

    Returns:
        `0` quando o comando roda até o fim; `1` se o e-mail do usuário não corresponder a
        nenhuma conta (erro de uso, não falha de geração).
    """
    argumentos = _analisar_argumentos(argv)
    config = config or obter_configuracoes()

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db:
        usuario = buscar_por_email(db, argumentos.usuario_email)
        if usuario is None:
            print(f"usuário {argumentos.usuario_email!r} não encontrado")
            return 1

        gerador, motivo_sem_ia = _escolher_gerador(db, config)
        relatorios = asyncio.run(
            _gerar_todas(
                db,
                argumentos.topico,
                gerador,
                usuario.id,
                UUID(argumentos.edital_id),
                tempo_alvo_min=argumentos.tempo_alvo_min,
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

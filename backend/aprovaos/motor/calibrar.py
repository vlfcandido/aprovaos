"""O calibrador (fatia 11): eventos agregados → dificuldade/discriminação, sinalização, fila.

O que é: `calibrar_questoes(db, agora, dias_janela=14, commit=True)` — lê `evento_estudo`/
`reporte_erro` da janela via `dados/repositorio_calibracao.py`, agrega e avalia com
`dominio/calibracao.py` (as regras R-0..R-9 da skill `calibracao-de-questoes`) e grava o
resultado (`Calibracao` + atualização de `Questao`). Determinístico, **sem LLM** — a cota do free
tier está esgotada e a skill inteira é regra determinística, sem julgamento de conteúdo. `main()`
é o `argparse` que resolve `--dias-janela` (padrão 14, o mesmo da skill) e `--dry-run`, abre o
engine, roda e imprime o relatório — incluindo, sempre, quantas questões da rodada tinham `n`
suficiente para declarar discriminação (o número que impede a próxima pessoa de supor volume que
a base não tem).

Sem agendador de verdade nesta fatia (mesma pendência de `motor/plano.py`, ADR-0030); até lá o
comando roda manualmente: `uv run python -m aprovaos.motor.calibrar`.

Quando ler: ao rodar o lote do calibrador, ou ao investigar por que uma questão foi/não foi
despublicada.
"""

import argparse
from datetime import date, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.repositorio_calibracao import (
    dificuldade_atual_por_questao,
    gravar_calibracao,
    origem_por_questao,
    reportes_da_janela,
    respostas_da_janela,
)
from aprovaos.dominio.calibracao import (
    N_MINIMO_DISCRIMINACAO,
    AjusteCalibracao,
    ItemFilaHumana,
    RetroalimentacaoGerador,
    agregar_metricas,
    avaliar_questao,
    montar_fila_humana,
    retroalimentacao_do_lote,
)

#: Janela padrão de agregação, em dias — a mesma que a skill usa como referência.
DIAS_JANELA_PADRAO = 14


class RelatorioCalibracao(BaseModel):
    """O relatório de uma rodada do calibrador — o que o diário da fatia e o cron registram.

    Attributes:
        dia: o dia da rodada (`calibracao.data`).
        dias_janela: quantos dias de `evento_estudo`/`reporte_erro` entraram na agregação.
        avaliadas: quantas questões tinham resposta e/ou reporte na janela (o universo avaliado).
        elegiveis_discriminacao: quantas dessas questões tinham `n ≥ N_MINIMO_DISCRIMINACAO` —
            **o número que não deve ser inflado**; com a base real de hoje, é honesto ele ser 0.
        ajustes: um `AjusteCalibracao` por questão avaliada.
        fila_humana: os itens que cabem nos 20 min do dono nesta rodada.
        fila_humana_adiada: o que sinalizou mas não coube — nunca descartado silenciosamente.
        retroalimentacao_gerador: os padrões (hoje só R-5) que voltam para o prompt do gerador.
    """

    dia: date
    dias_janela: int
    avaliadas: int
    elegiveis_discriminacao: int
    ajustes: list[AjusteCalibracao]
    fila_humana: list[ItemFilaHumana]
    fila_humana_adiada: list[ItemFilaHumana]
    retroalimentacao_gerador: list[RetroalimentacaoGerador]


def calibrar_questoes(
    db: Session,
    agora: datetime,
    *,
    dias_janela: int = DIAS_JANELA_PADRAO,
    commit: bool = True,
) -> RelatorioCalibracao:
    """Roda uma rodada completa do calibrador: lê a janela, avalia e grava (ou só relata).

    Args:
        db: sessão do comando.
        agora: o instante da rodada — `calibracao.data = agora.date()`; a janela é
            `[agora - dias_janela, agora]`.
        dias_janela: quantos dias de `evento_estudo`/`reporte_erro` entram na agregação (skill:
            14 dias de referência).
        commit: `True` grava de verdade (padrão); `False` (`--dry-run`) avalia e relata sem
            persistir nada — nem `calibracao`, nem mudança em `questao`.

    Returns:
        O `RelatorioCalibracao` da rodada.
    """
    desde = agora - timedelta(days=dias_janela)
    respostas = respostas_da_janela(db, desde)
    reportes = reportes_da_janela(db, desde)

    ids_com_resposta = {resposta.questao_id for resposta in respostas}
    ids_com_reporte = {reporte.questao_id for reporte in reportes}
    questao_ids = sorted(ids_com_resposta | ids_com_reporte, key=str)
    origens = origem_por_questao(db, questao_ids)
    dificuldades = dificuldade_atual_por_questao(db, questao_ids)

    metricas = agregar_metricas(respostas, reportes, origens, dificuldades)
    metricas_por_id = {metrica.questao_id: metrica for metrica in metricas}
    ajustes = [avaliar_questao(metrica) for metrica in metricas]
    fila, adiada = montar_fila_humana(ajustes, metricas_por_id)
    retroalimentacao = retroalimentacao_do_lote(ajustes)

    if commit:
        gravar_calibracao(db, ajustes, data=agora.date())
        db.commit()
    else:
        db.rollback()

    return RelatorioCalibracao(
        dia=agora.date(),
        dias_janela=dias_janela,
        avaliadas=len(metricas),
        elegiveis_discriminacao=sum(
            1 for metrica in metricas if metrica.n >= N_MINIMO_DISCRIMINACAO
        ),
        ajustes=ajustes,
        fila_humana=fila,
        fila_humana_adiada=adiada,
        retroalimentacao_gerador=retroalimentacao,
    )


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Calibrador: eventos agregados -> dificuldade/discriminacao, sinalizacao e "
            "despublicacao (fatia 11, skill calibracao-de-questoes). Sem LLM."
        )
    )
    parser.add_argument(
        "--dias-janela",
        type=int,
        default=DIAS_JANELA_PADRAO,
        help=f"tamanho da janela de agregação, em dias (padrão: {DIAS_JANELA_PADRAO})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="roda e imprime o relatório, mas não grava nada",
    )
    return parser.parse_args(argv)


def _relatar(relatorio: RelatorioCalibracao) -> None:
    """Imprime o relatório no formato usado pelo diário da fatia — nunca esconde o `n`."""
    print(
        f"calibração de {relatorio.dia.isoformat()} (janela de {relatorio.dias_janela} dias): "
        f"{relatorio.avaliadas} questão(ões) avaliada(s), "
        f"{relatorio.elegiveis_discriminacao} de {relatorio.avaliadas} com n >= "
        f"{N_MINIMO_DISCRIMINACAO} (elegível para discriminação)."
    )
    por_acao: dict[str, int] = {}
    for ajuste in relatorio.ajustes:
        por_acao[ajuste.acao] = por_acao.get(ajuste.acao, 0) + 1
    for acao, quantidade in sorted(por_acao.items()):
        print(f"  {acao}: {quantidade}")
    if relatorio.fila_humana:
        print(f"  fila humana ({len(relatorio.fila_humana)} item(ns)):")
        for item in relatorio.fila_humana:
            print(f"    {item.questao_id} — {item.o_que_olhar} ({item.minutos_estimados} min)")
    if relatorio.fila_humana_adiada:
        quantidade_adiada = len(relatorio.fila_humana_adiada)
        print(f"  fila humana adiada: {quantidade_adiada} item(ns) — não coube em 20 min")
    if relatorio.retroalimentacao_gerador:
        quantidade_retro = len(relatorio.retroalimentacao_gerador)
        print(f"  retroalimentação para o gerador: {quantidade_retro} padrão(ões)")


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando do calibrador.

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv` (padrão do `argparse`).
        config: configurações explícitas (testes); `None` lê do ambiente/.env.

    Returns:
        `0` sempre — o relatório impresso é a forma de saber o que a rodada decidiu.
    """
    argumentos = _analisar_argumentos(argv)
    config = config or obter_configuracoes()

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db:
        relatorio = calibrar_questoes(
            db,
            agora_utc(),
            dias_janela=argumentos.dias_janela,
            commit=not argumentos.dry_run,
        )
    _relatar(relatorio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

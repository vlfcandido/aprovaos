"""O relatório de cobertura de um edital e a encomenda de inéditas (fatia 5, RF-27).

O que é: `montar_relatorio_cobertura`, que lista, para cada tópico do edital, quantas questões
publicáveis ele já tem, se tem dossiê e se tem aula; `montar_encomendas`, que aplica o **Ruling
45** do plano da fatia (`docs/fatias/5-questoes-ineditas.md`) — encomenda geração só para o
tópico que tem dossiê **e** zero publicáveis (sem dossiê não há de onde tirar `trecho_que_decide`
literal; com publicável já não há lacuna a cobrir); e `topicos_sem_dossie_para_encomenda`, que
lista os tópicos que ficam de fora por falta de dossiê — lacuna declarada, nunca geração às
cegas. `main()` só lê e imprime o relatório; a geração de fato é `motor.gerar_questao`.

Quando ler: antes de rodar uma encomenda de inéditas; ao investigar por que um tópico não entrou
(ou entrou) na lista.
"""

import argparse
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.config import obter_configuracoes
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.modelos import Topico, TopicoEdital
from aprovaos.dados.repositorio_aula import aula_publicada_do_topico
from aprovaos.dados.repositorio_dossie import dossie_mais_recente_do_topico
from aprovaos.dados.repositorio_questao import contagem_por_topico

#: Quantas inéditas encomendar por tópico elegível, quando `main()` não recebe `--n-por-topico`
#: — pequeno de propósito: a cota diária do free tier (Ruling 44) só dá para poucos itens.
N_POR_TOPICO_PADRAO = 3


class LinhaCobertura(BaseModel):
    """A cobertura de um tópico do edital.

    Attributes:
        topico_slug: o tópico.
        publicaveis: quantas questões publicáveis (originais) esse tópico já tem.
        tem_dossie: se existe ao menos uma versão de `DossieTopico` para ele (direto ou por
            equivalência/subconjunto — `dados.repositorio_dossie.dossie_mais_recente_do_topico`).
        tem_aula: se existe aula publicada para ele.
    """

    topico_slug: str
    publicaveis: int
    tem_dossie: bool
    tem_aula: bool


class RelatorioCobertura(BaseModel):
    """A cobertura de todos os tópicos de um edital, na ordem do conteúdo programático.

    Attributes:
        linhas: uma `LinhaCobertura` por tópico do edital.
    """

    linhas: list[LinhaCobertura]


class Encomenda(BaseModel):
    """Um pedido de geração de inéditas para um tópico (Ruling 45).

    Attributes:
        topico_slug: o tópico a encomendar.
        n: quantos itens pedir.
    """

    topico_slug: str
    n: int


def montar_relatorio_cobertura(db: Session, edital_id: UUID) -> RelatorioCobertura:
    """Monta a cobertura de cada tópico do edital: publicáveis, dossiê e aula.

    Args:
        db: sessão do request/comando (só leitura).
        edital_id: o edital cujos tópicos serão relatados.

    Returns:
        `RelatorioCobertura` com uma linha por `TopicoEdital` deste edital, na ordem
        (`TopicoEdital.ordem`) do conteúdo programático.
    """
    topicos = list(
        db.scalars(
            select(Topico)
            .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
            .where(TopicoEdital.edital_id == edital_id)
            .order_by(TopicoEdital.ordem)
        ).all()
    )
    publicaveis_por_topico = contagem_por_topico(db, edital_id)

    linhas = [
        LinhaCobertura(
            topico_slug=topico.slug,
            publicaveis=publicaveis_por_topico.get(topico.id, 0),
            tem_dossie=dossie_mais_recente_do_topico(db, topico.id) is not None,
            tem_aula=aula_publicada_do_topico(db, topico.id) is not None,
        )
        for topico in topicos
    ]
    return RelatorioCobertura(linhas=linhas)


def montar_encomendas(relatorio: RelatorioCobertura, n_por_topico: int) -> list[Encomenda]:
    """Aplica o Ruling 45: encomenda só para tópico com dossiê **e** zero publicáveis.

    Args:
        relatorio: a cobertura do edital.
        n_por_topico: quantos itens pedir por tópico elegível.

    Returns:
        Uma `Encomenda` por tópico elegível, na ordem do relatório.
    """
    return [
        Encomenda(topico_slug=linha.topico_slug, n=n_por_topico)
        for linha in relatorio.linhas
        if linha.tem_dossie and linha.publicaveis == 0
    ]


def topicos_sem_dossie_para_encomenda(relatorio: RelatorioCobertura) -> list[str]:
    """Os tópicos sem dossiê e sem publicáveis — lacuna declarada, não geração às cegas.

    Args:
        relatorio: a cobertura do edital.

    Returns:
        Os `topico_slug` que ficam de fora da encomenda por falta de dossiê.
    """
    return [
        linha.topico_slug
        for linha in relatorio.linhas
        if not linha.tem_dossie and linha.publicaveis == 0
    ]


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Relatório de cobertura de um edital (publicáveis/dossiê/aula por tópico) e a "
            "encomenda de inéditas que o Ruling 45 autoriza — fatia 5."
        )
    )
    parser.add_argument("--edital-id", required=True, help="edital a relatar")
    parser.add_argument(
        "--n-por-topico",
        type=int,
        default=N_POR_TOPICO_PADRAO,
        help="quantos itens encomendar por tópico elegível",
    )
    return parser.parse_args(argv)


def _relatar(
    relatorio: RelatorioCobertura, encomendas: list[Encomenda], lacunas: list[str]
) -> None:
    """Imprime o relatório no formato usado pelo diário da fatia."""
    for linha in relatorio.linhas:
        print(
            f"{linha.topico_slug}: publicaveis={linha.publicaveis} "
            f"tem_dossie={linha.tem_dossie} tem_aula={linha.tem_aula}"
        )
    print(f"\nencomendas ({len(encomendas)}):")
    for encomenda in encomendas:
        print(f"  {encomenda.topico_slug}: n={encomenda.n}")
    print(f"\nlacunas — falta dossiê ({len(lacunas)}):")
    for slug in lacunas:
        print(f"  {slug}")


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada do relatório de cobertura.

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv`.

    Returns:
        `0` sempre que o comando roda até o fim (é um relatório; não grava nada).
    """
    argumentos = _analisar_argumentos(argv)
    config = obter_configuracoes()

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db:
        relatorio = montar_relatorio_cobertura(db, UUID(argumentos.edital_id))
        encomendas = montar_encomendas(relatorio, argumentos.n_por_topico)
        lacunas = topicos_sem_dossie_para_encomenda(relatorio)
    _relatar(relatorio, encomendas, lacunas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

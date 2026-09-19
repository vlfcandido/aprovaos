"""O comando `varrer`: catálogo inteiro da Cebraspe → `concurso_radar` (fatia 1b, F1.1).

O que é: `varrer(db, fonte_cebraspe, agora)` — um único `GET` (`FonteCebraspe.obter_catalogo`),
`dominio.radar.ler_catalogo` (lê a fase do corpo, nunca do caminho — o achado do §1 do plano
`docs/fatias/1b-radar-e-conta.md`: `/fase/<nome errado>` devolve HTTP 200 com `[]`, não 404) e
`dados.repositorio_radar.sincronizar`. Sem LLM; molde de `motor/plano.py`/`motor/calibrar.py`.
`main()` é o `argparse` que abre o engine, roda e imprime o relatório — idempotente, pode rodar
à mão; a frequência de 6h é configuração do agendador (ADR-0030, deploy é do dono).

Quando ler: ao rodar a varredura do radar, ou ao investigar por que um concurso não apareceu.
"""

import argparse
from datetime import datetime

from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.repositorio_radar import (
    RelatorioSincronizacao,
    obter_ou_criar_fonte,
    sincronizar,
)
from aprovaos.dominio.radar import ConcursoDoRadar, ler_catalogo
from aprovaos.motor.fontes.cebraspe import URL_LISTA, FonteCebraspe, criar_fonte_cebraspe

#: `id_externo`/`nome` da ficha `cebraspe` em `knowledge/fontes.yaml` — usados só para criar a
#: linha `fonte` na primeira varredura (get-or-create; rodadas seguintes reaproveitam a linha).
ID_FONTE_CEBRASPE = "cebraspe"
NOME_FONTE_CEBRASPE = (
    "Cebraspe — Centro Brasileiro de Pesquisa em Avaliação e Seleção de Candidatos a Concursos"
)


def _sem_duplicata_de_identidade(concursos: list[ConcursoDoRadar]) -> list[ConcursoDoRadar]:
    """Deduplica por `evento_url`, mantendo a última ocorrência.

    A própria API da Cebraspe repete algum evento na mesma resposta (medido em 19/09/2026:
    `INSS_22` aparece duas vezes no grupo "Encerrados", uma vez como `"INSS 22"` e outra como
    `"INSS_22"` no `eventoNomeAbreviado`) — o mesmo defeito de fonte que
    `motor/fontes/cebraspe.py::FonteCebraspe.listar_novidades` já trata para a listagem de
    eventos da V3. `sincronizar` identifica pela dupla `(fonte_id, evento_url)`; sem este passo,
    duas linhas com o mesmo `evento_url` no mesmo catálogo virariam uma atualização espúria
    dentro da própria rodada, nunca um duplicado real na tabela (a `UniqueConstraint` impediria
    isso de qualquer forma — este passo só evita o relatório mentiroso).
    """
    por_url: dict[str, ConcursoDoRadar] = {}
    for concurso in concursos:
        por_url[concurso.evento_url] = concurso
    return list(por_url.values())


def varrer(db: Session, fonte_cebraspe: FonteCebraspe, agora: datetime) -> RelatorioSincronizacao:
    """Roda uma varredura completa: busca o catálogo, normaliza e sincroniza.

    Args:
        db: sessão do comando.
        fonte_cebraspe: a fonte já aberta (real ou dublê de teste), injetada — nenhuma conexão é
            criada aqui.
        agora: instante da rodada.

    Returns:
        O `RelatorioSincronizacao` da rodada (novos/atualizados/inalterados).
    """
    fonte = obter_ou_criar_fonte(db, ID_FONTE_CEBRASPE, NOME_FONTE_CEBRASPE, URL_LISTA)
    payload = fonte_cebraspe.obter_catalogo()
    concursos = _sem_duplicata_de_identidade(ler_catalogo(payload))
    relatorio = sincronizar(db, fonte, concursos, agora)
    fonte.ultima_varredura = agora
    db.flush()
    return relatorio


def _relatar(relatorio: RelatorioSincronizacao) -> None:
    """Imprime o relatório no formato usado pelo diário da fatia."""
    print(
        f"radar: {relatorio.novos} novo(s), {relatorio.atualizados} atualizado(s), "
        f"{relatorio.inalterados} inalterado(s)"
    )


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando `varrer`.

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv` (o comando não tem opção
            hoje, mas segue o molde de `motor/plano.py`/`motor/calibrar.py`).
        config: configurações explícitas (testes); `None` lê do ambiente/.env.

    Returns:
        `0` sempre — o relatório impresso é a forma de saber o que a rodada trouxe.
    """
    argparse.ArgumentParser(
        description="Radar: catálogo inteiro da Cebraspe -> concurso_radar (fatia 1b). Sem LLM."
    ).parse_args(argv)
    config = config or obter_configuracoes()

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db, criar_fonte_cebraspe(config) as fonte_cebraspe:
        relatorio = varrer(db, fonte_cebraspe, agora_utc())
        db.commit()
    _relatar(relatorio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

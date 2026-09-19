"""O comando que monta e grava o dossiê de um tópico (fundação jurídica, passo 3).

O que é: `construir_dossie_improbidade(db, hoje)` — a prova de conceito de ponta a ponta pedida
pela tarefa: tópico real (`dir-adm-06-improbidade-administrativa`, escolhido por ter 6 questões
publicáveis na base e norma catalogada — Lei 8.429/1992) → HTML real já baixado
(`knowledge/fixtures/juridico/lei8429_planalto_compilada.htm`) → `dominio.dossie.montar_dossie`
(determinístico, sem LLM) → `dados.repositorio_dossie.salvar_dossie`. `PEDIDOS_IMPROBIDADE` é a
lista fixa de dispositivos que este tópico precisa — curada à mão nesta rodada a partir do que
`dominio.legislacao.extrair_artigo` consegue ler de fato (ver `knowledge/fixtures/juridico/
LEIA-ME.md`, achados 2 e 3, para os que não consegue: arts. 9º/10/11 têm título de Seção em
Title Case entre eles e o artigo seguinte; art. 17 tem um `§ 4º-A` com sufixo de letra).

`main()` é o `argparse` que abre o banco, roda o comando, comita (salvo `--dry-run`) e imprime
fontes/lacunas. Nenhuma execução acontece em import.

Quando ler: ao trocar o tópico-piloto do dossiê, ou ao investigar por que um dispositivo pedido
não virou fonte.
"""

import argparse
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.modelos import DossieTopico, Topico
from aprovaos.dados.repositorio_dossie import salvar_dossie
from aprovaos.dominio.dossie import ConteudoDossie, PedidoDispositivo, montar_dossie
from aprovaos.dominio.erros import TopicoNaoEncontrado
from aprovaos.motor.ancorar import html_offline_da_norma
from aprovaos.motor.fontes.planalto import CATALOGO

SLUG_IMPROBIDADE = "dir-adm-06-improbidade-administrativa"
"""O tópico-piloto desta rodada: Direito Administrativo, Improbidade (Lei 8.429/1992) — 6
questões publicáveis na base real e norma já no catálogo (ver relatório da tarefa)."""

_NORMA_IMPROBIDADE = "lei-8429-1992"

PEDIDOS_IMPROBIDADE: list[PedidoDispositivo] = [
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="1"),
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="1", paragrafo="1"),  # rol fechado (9-11)
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="1", paragrafo="2"),  # definição de dolo
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="1", paragrafo="3"),  # sem dolo, sem ato
    # § 8º: divergência interpretativa não configura improbidade
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="1", paragrafo="8"),
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="2"),  # quem é agente público
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="3"),  # particular que induz dolosamente
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="9"),  # lacuna: título "Seção II" (T. Case)
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="10"),  # lacuna: idem
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="11"),  # lacuna: idem + "CAPÍTULO III"
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="17"),  # lacuna: "§ 4º-A" (sufixo letra)
    PedidoDispositivo(norma=_NORMA_IMPROBIDADE, artigo="23"),  # prescrição
]
"""Os dispositivos pedidos para o dossiê-piloto. Mistura de propósito: os que
`dominio.legislacao.extrair_artigo` lê (viram fonte, com trecho real) e os que não lê (viram
lacuna declarada, com o erro literal) — a tarefa pede para provar as duas coisas, não só o
caminho feliz."""


def _buscar_topico(db: Session, slug: str) -> Topico:
    """Busca o `Topico` por `slug`; levanta `TopicoNaoEncontrado` em vez de criá-lo."""
    topico = db.scalars(select(Topico).where(Topico.slug == slug)).first()
    if topico is None:
        raise TopicoNaoEncontrado(
            f"tópico {slug!r} não está cadastrado — rode o parser de edital antes do dossiê."
        )
    return topico


def construir_dossie_improbidade(
    db: Session, *, hoje: date | None = None
) -> tuple[DossieTopico, ConteudoDossie]:
    """Monta e grava o dossiê-piloto de improbidade administrativa (Lei 8.429/1992).

    Args:
        db: sessão de banco (precisa ter o `Topico` de `SLUG_IMPROBIDADE` já cadastrado).
        hoje: data a gravar no `log_buscas`; `None` usa `date.today()`.

    Returns:
        A `DossieTopico` gravada (`add`/`flush`, sem `commit` — quem chama decide) e o
        `ConteudoDossie` em memória (fontes/lacunas como objetos Python, para quem quiser
        inspecionar sem reler o JSON persistido).

    Raises:
        TopicoNaoEncontrado: `SLUG_IMPROBIDADE` não está cadastrado em `topico`.
    """
    topico = _buscar_topico(db, SLUG_IMPROBIDADE)

    cache_html: dict[str, str] = {}
    html = html_offline_da_norma(_NORMA_IMPROBIDADE, cache_html)
    normas_html = {} if html is None else {_NORMA_IMPROBIDADE: html}
    normas_url = {_NORMA_IMPROBIDADE: CATALOGO[_NORMA_IMPROBIDADE].url}

    conteudo = montar_dossie(
        topico_slug=SLUG_IMPROBIDADE,
        pedidos=PEDIDOS_IMPROBIDADE,
        normas_html=normas_html,
        normas_url=normas_url,
        hoje=hoje or date.today(),
    )
    dossie = salvar_dossie(db, topico_id=topico.id, conteudo=conteudo)
    return dossie, conteudo


def _relatar(conteudo: ConteudoDossie) -> None:
    """Imprime fontes e lacunas no formato usado pelo diário da fatia."""
    print(f"fontes={len(conteudo.fontes)} lacunas={len(conteudo.lacunas)}")
    for fonte in conteudo.fontes:
        print(f"  fonte {fonte.id}: {fonte.citacao_canonica}")
    for lacuna in conteudo.lacunas:
        print(f"  lacuna: {lacuna.dispositivo} — {lacuna.motivo}")


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Monta e grava o dossiê-piloto de improbidade administrativa (Lei 8.429/1992), "
            "offline e sem LLM — prova de conceito da fundação jurídica, passo 3."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="roda a construção do dossiê, mas não comita (só imprime o relatório)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando de construção do dossiê-piloto.

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv` (padrão do `argparse`).
        config: configurações explícitas (testes); `None` lê do ambiente/.env.

    Returns:
        `0` sempre que o comando roda até o fim.
    """
    argumentos = _analisar_argumentos(argv)
    config = config or obter_configuracoes()

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db:
        _dossie, conteudo = construir_dossie_improbidade(db)
        if argumentos.dry_run:
            db.rollback()
        else:
            db.commit()
    _relatar(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

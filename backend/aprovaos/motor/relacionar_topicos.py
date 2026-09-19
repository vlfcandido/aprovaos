"""Liga pares de tópicos entre editais diferentes — plena ou parcial (ADR-0041, fecha a P-52; I1).

O que é: `RELACOES` (equivalência **plena**, peso 1) e `RELACOES_PARCIAIS` (cobertura **parcial**,
peso < 1 — um dossiê/aula cobre só um subconjunto do item do outro edital) são a curadoria manual
(mesmo padrão de `RECEITAS` em `motor/dossie.py`) — cada par de slugs que um humano conferiu, com
a evidência textual literal que sustenta a relação (nunca "parecem iguais", ADR-0036).
`relacionar_topicos(db)` resolve cada par por slug e grava a aresta correspondente
(`dados.repositorio_topico_relacao.criar_relacao_equivalente`/`criar_relacao_subconjunto`), sem
derrubar o lote quando um slug não existe ainda — vira uma linha do relatório, não uma exceção.

Correção de 19/09/2026 (revisão independente, I1): o par de "recursos" (Cascavel × TJ-PR) estava
gravado em `RELACOES` como equivalência plena, mas a própria evidência já dizia "a cobertura do
dossiê é parcial em relação ao item do TJ-PR" — contradição entre o que a aresta afirmava (peso
1, "é a mesma coisa") e o que o texto sabia. Movido para `RELACOES_PARCIAIS`.

Por que este comando existe (e não só uma migração de dados rodada uma vez): os pares crescem
conforme novos editais entram na base, exatamente como `RECEITAS` (dossiê) e
`topicos_de_maior_peso` (ranking); manter a curadoria como dado versionado no código, com
`main()`/`--dry-run` igual ao resto do `motor/`, é mais barato que um script solto.

Nenhuma execução acontece em import; `main()` é o `argparse` que abre o banco, roda o comando,
comita (salvo `--dry-run`) e imprime o relatório.

Quando ler: ao curar um par novo (plena ou parcial), ou ao investigar por que um tópico não está
encontrando o dossiê/aula/citação de outro edital que cobre o mesmo assunto (ou cobre só parte).
"""

import argparse
from collections.abc import Callable
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.modelos import Topico, TopicoRelacao
from aprovaos.dados.repositorio_topico_relacao import (
    criar_relacao_equivalente,
    criar_relacao_subconjunto,
    topicos_equivalentes,
    topicos_subconjunto,
)

#: Curadoria manual dos pares **plenos** já conferidos, `(slug_a, slug_b) -> evidência`. A
#: evidência cita o que, literalmente, aparece nos dois lados — nunca uma impressão ("parecem
#: tratar do mesmo assunto"), e nunca uma evidência que já admite cobertura parcial (isso é
#: `RELACOES_PARCIAIS`). Achado da correção estrutural de 19/09/2026: os 4 dossiês e as 2 aulas
#: da fatia 4/6 foram gerados sob o vocabulário do edital da Câmara Municipal de Cascavel
#: (`dir-*`), mas as questões publicáveis da V3 estão classificadas contra o edital do TJ-PR
#: (`noc-dir-*`) — os pares abaixo são os únicos, entre os tópicos com dossiê/aula, em que o
#: texto do conteúdo programático dos dois editais cita o mesmo dispositivo/expressão literal
#: **e** cobre o item inteiro; os demais tópicos com questão publicável (ex.:
#: `noc-dir-con-06-6-organizacao`, `noc-dir-pro-pen-06-provas-6`, `noc-dir-adm-09-9-agentes`) não
#: têm par honesto do lado do edital de Cascavel e ficam **sem relação** — ADR-0036 (na dúvida,
#: não relacione).
RELACOES: dict[tuple[str, str], str] = {
    ("dir-adm-06-improbidade-administrativa", "noc-dir-adm-06-6-improbidade"): (
        "ambos citam literalmente 'improbidade administrativa' e a Lei nº 8.429/1992 "
        "(edital Cascavel/Unioeste §6 vs. edital TJ-PR/AOCP, Noções de Direito Administrativo "
        "item 6)"
    ),
    ("dir-con-02-direitos-garantias", "noc-dir-con-04-4-direitos"): (
        "ambos citam literalmente 'Direitos e garantias fundamentais' (edital Cascavel/Unioeste "
        "§2, arts. 5º a 17, vs. edital TJ-PR/AOCP, Noções de Direito Constitucional item 4)"
    ),
    ("dir-pro-civ-03-atos-processuais", "noc-dir-pro-civ-04-atos-processuais"): (
        "ambos citam literalmente 'atos processuais' e 'prazos' (edital Cascavel/Unioeste §3 vs. "
        "edital TJ-PR/AOCP, Noções de Direito Processual Civil item 4)"
    ),
}

#: Curadoria manual dos pares de cobertura **parcial** (I1) — um dossiê/aula cobre só um
#: subconjunto do item do outro edital, nunca o item inteiro; a evidência diz explicitamente o
#: que fica de fora. Nunca grave aqui um par cuja cobertura seja completa — isso é `RELACOES`.
RELACOES_PARCIAIS: dict[tuple[str, str], str] = {
    ("dir-pro-civ-05-recursos-apelacao", "noc-dir-pro-civ-07-recursos"): (
        "ambos citam literalmente 'recursos' (edital Cascavel/Unioeste §5, que detalha apelação, "
        "agravo de instrumento e embargos de declaração — as três modalidades mais comuns do "
        "CPC), mas isso é um subconjunto do item genérico 'Dos recursos' do edital TJ-PR/AOCP, "
        "Noções de Direito Processual Civil item 7 — a cobertura do dossiê é parcial em relação "
        "ao item do TJ-PR, não incorreta, e a tela avisa isso"
    ),
}


StatusRelacaoTopicos = Literal["criada", "ja_existia", "sem_topico"]


class RelatorioRelacaoTopicos(BaseModel):
    """Uma linha do relatório de `relacionar_topicos` — o que aconteceu com um par.

    Attributes:
        pares: `(slug_a, slug_b)` tentado.
        status: `"criada"` (relação nova), `"ja_existia"` (idempotente — já estava ligado),
            `"sem_topico"` (um dos dois slugs não está cadastrado em `topico` ainda).
    """

    pares: tuple[str, str]
    status: StatusRelacaoTopicos


def _buscar_topico(db: Session, slug: str) -> Topico | None:
    """Busca o `Topico` por `slug`, sem levantar — `None` é um resultado válido aqui."""
    return db.scalars(select(Topico).where(Topico.slug == slug)).first()


def relacionar_topicos(
    db: Session,
    pares: dict[tuple[str, str], str] = RELACOES,
    *,
    criar_relacao: Callable[..., TopicoRelacao] = criar_relacao_equivalente,
    ja_ligados: Callable[[Session, UUID], list[UUID]] = topicos_equivalentes,
) -> list[RelatorioRelacaoTopicos]:
    """Grava a relação curada de cada par de `pares`, sem derrubar o lote por slug ausente.

    Args:
        db: sessão de banco (faz `add`/`flush`; o `commit` é de quem chama).
        pares: `(slug_a, slug_b) -> evidência`; `RELACOES` (equivalência plena) por padrão —
            passe `RELACOES_PARCIAIS` com `criar_relacao=criar_relacao_subconjunto` e
            `ja_ligados=topicos_subconjunto` para gravar cobertura parcial.
        criar_relacao: a função de gravação (`criar_relacao_equivalente` ou
            `criar_relacao_subconjunto`) — decide o `peso`/`origem` da aresta.
        ja_ligados: a função de leitura correspondente (`topicos_equivalentes` ou
            `topicos_subconjunto`) — usada só para o relatório dizer "já existia" com precisão.

    Returns:
        Um `RelatorioRelacaoTopicos` por par, na ordem de `pares`.
    """
    relatorios: list[RelatorioRelacaoTopicos] = []
    for (slug_a, slug_b), evidencia in pares.items():
        topico_a = _buscar_topico(db, slug_a)
        topico_b = _buscar_topico(db, slug_b)
        if topico_a is None or topico_b is None:
            relatorios.append(RelatorioRelacaoTopicos(pares=(slug_a, slug_b), status="sem_topico"))
            continue

        ja_existia = topico_b.id in ja_ligados(db, topico_a.id)
        criar_relacao(db, de_id=topico_a.id, para_id=topico_b.id, evidencia=evidencia)
        db.flush()
        status: StatusRelacaoTopicos = "ja_existia" if ja_existia else "criada"
        relatorios.append(RelatorioRelacaoTopicos(pares=(slug_a, slug_b), status=status))
    return relatorios


def _relatar(relatorios: list[RelatorioRelacaoTopicos]) -> None:
    """Imprime uma linha por par tentado, no formato usado pelo diário da fatia."""
    for relatorio in relatorios:
        slug_a, slug_b = relatorio.pares
        print(f"{slug_a} <-> {slug_b}: {relatorio.status}")


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Liga os pares de tópicos curados em `RELACOES` (equivalência plena) e "
            "`RELACOES_PARCIAIS` (cobertura parcial) — a ponte entre o vocabulário de tópico de "
            "editais diferentes que cobrem o mesmo assunto, inteiro ou em parte (ADR-0041/I1)."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="roda a ligação, mas não comita (só imprime o relatório)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando de ligação de tópicos (equivalência plena e parcial).

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
        relatorios = relacionar_topicos(db) + relacionar_topicos(
            db,
            RELACOES_PARCIAIS,
            criar_relacao=criar_relacao_subconjunto,
            ja_ligados=topicos_subconjunto,
        )
        if argumentos.dry_run:
            db.rollback()
        else:
            db.commit()
    _relatar(relatorios)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

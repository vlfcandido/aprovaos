"""O comando de ancoragem jurídica: liga cada questão ao dispositivo legal que ela cita.

O que é: `ancorar_citacoes(db)` — passo 2 da fundação jurídica. Para cada `Questao` da base,
concatena `enunciado` + `comando` + `texto_apoio`, roda `dominio.citacao.extrair_citacoes` e, para
cada referência que aponta a uma norma do catálogo (`motor.fontes.planalto.CATALOGO`) **e** tem
artigo, resolve o trecho exato offline (`dominio.legislacao.extrair_artigo` +
`localizar_trecho`, contra os HTMLs já baixados em `knowledge/fixtures/juridico/`) e grava
`DispositivoLegal`/`Citacao` (`dados.repositorio_citacao`, com dedup). Nada de IA, nada de rede:
é ancoragem determinística — a etapa anterior à justificativa gerada, que vem depois com
validador (fora do escopo deste passo).

Classificação por questão (mutuamente exclusiva, nesta ordem de prioridade — o relatório soma
exatamente ao total da base):
1. **resolvida**: pelo menos uma referência resolveu para um dispositivo do catálogo (citação
   gravada).
2. **lacuna_norma**: nenhuma resolveu, mas há referência a uma norma reconhecida que não está no
   catálogo (`RelatorioAncoragem.normas_fora_do_catalogo` rankeia essas normas por nº de
   questões — é a lista que diz quais leis baixar em seguida).
3. **catalogada_nao_resolvida**: só há referência a norma do catálogo sem artigo (`"Lei nº
   14.133/2021"` sozinha) ou a um artigo/inciso/parágrafo que não existe na fixture offline.
4. **sem_citacao**: `extrair_citacoes` não achou nada — o caso mais comum na base medida.

`main()` é o `argparse` que abre o banco, roda `ancorar_citacoes`, comita (salvo `--dry-run`) e
imprime o relatório. Nenhuma execução acontece em import.

Quando ler: ao rodar a ancoragem sobre uma base de questões nova, ou ao investigar por que uma
questão com citação "óbvia" não gerou linha em `citacao`.
"""

import argparse
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.modelos import DispositivoLegal, Questao
from aprovaos.dados.repositorio_citacao import buscar_ou_criar_dispositivo, registrar_citacao
from aprovaos.dominio.citacao import ReferenciaLegal, citacao_canonica, extrair_citacoes
from aprovaos.dominio.erros import DispositivoNaoEncontrado, EstruturaNaoTratada
from aprovaos.dominio.legislacao import (
    ArtigoExtraido,
    TrechoDispositivo,
    extrair_artigo,
    localizar_trecho,
)
from aprovaos.motor.fontes.planalto import CATALOGO, decodificar_html

_RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[3]

FIXTURES_OFFLINE: dict[str, str] = {
    "cf-1988": "constituicao_planalto_compilada.htm",
    "lei-14133-2021": "lei14133_planalto_compilada.htm",
    "clt": "clt_planalto_compilada.htm",
    "lei-8429-1992": "lei8429_planalto_compilada.htm",
    "lei-6404-1976": "lei6404_planalto_compilada.htm",
    "lei-11101-2005": "lei11101_planalto_compilada.htm",
    "lei-11340-2006": "lei11340_planalto_compilada.htm",
    "lei-6830-1980": "lei6830_planalto_compilada.htm",
    "lei-13105-2015": "lei13105_planalto_compilada.htm",
    # Ampliação de 23/09/2026 — as leis do edital real da piloto (TJ-PR/AOCP). Baixadas do
    # Planalto na mesma data com UA de navegador (sem ele o site devolve 0 bytes, ver
    # `LEIA-ME.md` das fixtures); tamanho e HTTP de cada uma registrados lá.
    "codigo-penal": "del2848_planalto_compilada.htm",
    "cpp": "del3689_planalto_compilada.htm",
    "codigo-civil": "lei10406_planalto_compilada.htm",
    "lgpd": "lei13709_planalto_compilada.htm",
    "lei-9099-1995": "lei9099_planalto_compilada.htm",
    "lei-12153-2009": "lei12153_planalto_compilada.htm",
    "lindb": "del4657_planalto_compilada.htm",
    "lei-12527-2011": "lei12527_planalto_compilada.htm",
}
"""As normas do catálogo que esta rodada resolve — offline, do HTML medido em
`knowledge/fixtures/juridico/` (ver `LEIA-ME.md` de lá). Uma norma nova no `CATALOGO` só entra
aqui depois de a fixture correspondente existir; até lá, cai em `lacuna_norma` ou
`catalogada_nao_resolvida`, nunca trava o comando. Estar aqui **não garante** que todo artigo
citado resolva: `_resolver_trecho` engole `EstruturaNaoTratada`/`DispositivoNaoEncontrado` e
devolve `None` — o artigo específico fica `catalogada_nao_resolvida` em vez de travar o comando.
Achados desta rodada de ampliação (19/09/2026, ver `LEIA-ME.md` de `knowledge/fixtures/juridico/`
para o trecho literal de cada um): CLT tem uma anotação "Vigência\\nencerrada" (sem parênteses,
2 palavras) que o extrator não reconhece entre os parágrafos do art. 477; Lei 8.429/1992 e Lei
11.340/2006 intercalam títulos de Seção/Capítulo em *Title Case* (não em CAIXA ALTA) entre
artigos, que `dominio.legislacao._eh_titulo_estrutural` não reconhece como estrutural. Nenhum
desses casos foi remendado nesta rodada — ficam como estrutura não tratada, resolvida como
`None` pelo comando."""


class RelatorioAncoragem(BaseModel):
    """O que `ancorar_citacoes` devolve — o tamanho do que dá para ancorar sem IA.

    Attributes:
        total: quantidade de questões da base processadas.
        resolvidas: citam um dispositivo do catálogo que a ancoragem resolveu e gravou.
        lacuna_norma: citam norma reconhecida fora do catálogo (nenhuma resolvida).
        catalogada_nao_resolvida: só citam norma do catálogo sem artigo, ou um
            artigo/inciso/parágrafo que a fixture offline não tem.
        sem_citacao: nenhuma referência reconhecível no texto.
        citacoes_novas: linhas novas em `citacao` nesta rodada (idempotente — rodar de novo
            sobre a mesma base soma `0`).
        dispositivos_novos: linhas novas em `dispositivo_legal` nesta rodada.
        normas_fora_do_catalogo: nº de questões distintas que citam cada norma reconhecida e
            ainda não catalogada, da mais citada para a menos citada — a lista de quais leis
            baixar em seguida.
    """

    total: int
    resolvidas: int
    lacuna_norma: int
    catalogada_nao_resolvida: int
    sem_citacao: int
    citacoes_novas: int
    dispositivos_novos: int
    normas_fora_do_catalogo: dict[str, int]


def html_offline_da_norma(norma_id: str, cache: dict[str, str]) -> str | None:
    """Devolve o HTML decodificado da `norma_id`, lendo a fixture offline uma vez só (cache).

    Pública (não só deste comando): `motor.dossie` reaproveita para carregar o HTML das normas
    que um dossiê pede, sem duplicar o caminho `knowledge/fixtures/juridico/` nem a tabela
    `FIXTURES_OFFLINE`.

    Args:
        norma_id: id da norma (`ReferenciaLegal.norma`).
        cache: dicionário mutável reaproveitado entre chamadas (uma execução do comando).

    Returns:
        O HTML decodificado, ou `None` quando não há fixture offline para esta norma ainda
        (norma do catálogo sem fixture baixada nesta rodada).
    """
    if norma_id not in FIXTURES_OFFLINE:
        return None
    if norma_id not in cache:
        caminho = (
            _RAIZ_DO_REPOSITORIO
            / "knowledge"
            / "fixtures"
            / "juridico"
            / FIXTURES_OFFLINE[norma_id]
        )
        cache[norma_id] = decodificar_html(caminho.read_bytes())
    return cache[norma_id]


def _resolver_trecho(
    referencia: ReferenciaLegal,
    cache_html: dict[str, str],
    cache_artigo: dict[tuple[str, str], ArtigoExtraido],
) -> TrechoDispositivo | None:
    """Resolve uma `ReferenciaLegal` (com artigo) para o trecho exato, offline.

    Args:
        referencia: a referência a resolver (`referencia.artigo` não pode ser `None`).
        cache_html: cache de HTML por norma (`html_offline_da_norma`).
        cache_artigo: cache de `ArtigoExtraido` por `(norma, artigo)` — evita reprocessar o
            mesmo artigo a cada questão que o cita.

    Returns:
        O `TrechoDispositivo` exato (caput/inciso/parágrafo), ou `None` quando a norma não tem
        fixture offline, o artigo não existe nela, ou o inciso/parágrafo pedido não existe nesse
        artigo — nunca levanta: é usado num laço sobre a base inteira, e uma citação que não
        resolve é resultado de medição, não uma falha do comando.
    """
    assert referencia.artigo is not None
    html = html_offline_da_norma(referencia.norma, cache_html)
    if html is None:
        return None

    chave_artigo = (referencia.norma, referencia.artigo)
    if chave_artigo not in cache_artigo:
        try:
            cache_artigo[chave_artigo] = extrair_artigo(html, referencia.artigo)
        except (DispositivoNaoEncontrado, EstruturaNaoTratada):
            return None
    artigo = cache_artigo[chave_artigo]

    try:
        return localizar_trecho(artigo, inciso=referencia.inciso, paragrafo=referencia.paragrafo)
    except DispositivoNaoEncontrado:
        return None


def _citacao_canonica_da_referencia(referencia: ReferenciaLegal) -> str:
    """Monta a `citacao_canonica` de uma `ReferenciaLegal` já resolvida (`artigo` não é `None`).

    Fina camada sobre `dominio.citacao.citacao_canonica` — só desempacota os campos da
    referência.
    """
    assert referencia.artigo is not None
    return citacao_canonica(
        referencia.norma,
        referencia.artigo,
        inciso=referencia.inciso,
        paragrafo=referencia.paragrafo,
    )


def ancorar_citacoes(db: Session) -> RelatorioAncoragem:
    """Roda a ancoragem sobre toda a tabela `questao` e grava as citações resolvidas.

    Idempotente: rodar duas vezes sobre a mesma base não duplica `dispositivo_legal` (dedup por
    `citacao_canonica`) nem `citacao` (dedup por conteúdo+dispositivo) — a segunda rodada soma
    `citacoes_novas=0`/`dispositivos_novos=0`. Faz `add`/`flush`; o `commit` é de quem chama
    (`main()`, ou o teste).

    Args:
        db: sessão de banco.

    Returns:
        `RelatorioAncoragem` com a classificação de cada questão e o ranking de normas fora do
        catálogo.
    """
    total_dispositivos_antes = db.scalar(select(func.count()).select_from(DispositivoLegal)) or 0

    cache_html: dict[str, str] = {}
    cache_artigo: dict[tuple[str, str], ArtigoExtraido] = {}
    normas_fora_do_catalogo: dict[str, int] = {}

    resolvidas = lacuna_norma = catalogada_nao_resolvida = sem_citacao = 0
    citacoes_novas = 0

    questoes = db.scalars(select(Questao)).all()
    for questao in questoes:
        texto = " ".join(
            parte for parte in (questao.enunciado, questao.comando, questao.texto_apoio) if parte
        )
        referencias = extrair_citacoes(texto)
        if not referencias:
            sem_citacao += 1
            continue

        houve_resolvida = False
        houve_catalogada = False
        normas_gap_da_questao: set[str] = set()
        posicao = 0

        for referencia in referencias:
            if referencia.norma not in CATALOGO:
                normas_gap_da_questao.add(referencia.norma)
                continue
            houve_catalogada = True
            if referencia.artigo is None:
                continue
            trecho = _resolver_trecho(referencia, cache_html, cache_artigo)
            if trecho is None:
                continue

            posicao += 1
            dispositivo = buscar_ou_criar_dispositivo(
                db,
                citacao_canonica=_citacao_canonica_da_referencia(referencia),
                norma=referencia.norma,
                artigo=referencia.artigo,
                inciso=referencia.inciso,
                paragrafo=referencia.paragrafo,
                texto=trecho.texto,
                vigente=True,
                fonte_url=CATALOGO[referencia.norma].url,
            )
            db.flush()
            criada = registrar_citacao(
                db,
                conteudo_tipo="questao",
                conteudo_id=questao.id,
                dispositivo_id=dispositivo.id,
                posicao=posicao,
            )
            db.flush()
            if criada is not None:
                citacoes_novas += 1
            houve_resolvida = True

        if houve_resolvida:
            resolvidas += 1
        elif normas_gap_da_questao:
            lacuna_norma += 1
            for norma in normas_gap_da_questao:
                normas_fora_do_catalogo[norma] = normas_fora_do_catalogo.get(norma, 0) + 1
        elif houve_catalogada:
            catalogada_nao_resolvida += 1
        else:
            sem_citacao += 1

    total_dispositivos_depois = db.scalar(select(func.count()).select_from(DispositivoLegal)) or 0
    ranking = dict(sorted(normas_fora_do_catalogo.items(), key=lambda item: item[1], reverse=True))
    return RelatorioAncoragem(
        total=len(questoes),
        resolvidas=resolvidas,
        lacuna_norma=lacuna_norma,
        catalogada_nao_resolvida=catalogada_nao_resolvida,
        sem_citacao=sem_citacao,
        citacoes_novas=citacoes_novas,
        dispositivos_novos=total_dispositivos_depois - total_dispositivos_antes,
        normas_fora_do_catalogo=ranking,
    )


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Ancora cada questão da base ao dispositivo legal que ela cita explicitamente "
            "(sem IA): extrai as referências do texto, resolve offline contra as fixtures do "
            "Planalto e grava dispositivo_legal/citacao."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="roda a extração e a resolução, mas não comita (só imprime o relatório)",
    )
    return parser.parse_args(argv)


def _relatar(relatorio: RelatorioAncoragem) -> None:
    """Imprime o relatório no formato usado pelo diário da fatia."""
    print(
        f"total={relatorio.total} resolvidas={relatorio.resolvidas} "
        f"lacuna_norma={relatorio.lacuna_norma} "
        f"catalogada_nao_resolvida={relatorio.catalogada_nao_resolvida} "
        f"sem_citacao={relatorio.sem_citacao} citacoes_novas={relatorio.citacoes_novas} "
        f"dispositivos_novos={relatorio.dispositivos_novos}"
    )
    if relatorio.normas_fora_do_catalogo:
        print("normas fora do catálogo (nº de questões que citam, decrescente):")
        for norma, quantidade in relatorio.normas_fora_do_catalogo.items():
            print(f"  {norma}: {quantidade}")


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando de ancoragem.

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
        relatorio = ancorar_citacoes(db)
        if argumentos.dry_run:
            db.rollback()
        else:
            db.commit()
    _relatar(relatorio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

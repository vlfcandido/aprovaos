"""Rotas públicas (fatia 13): família A, C, D, `sitemap.xml` e `robots.txt`.

O que é: as únicas rotas do produto que **nunca** dependem de login — nenhuma delas usa
`exigir_usuario`/`usuario_atual`, e `renderizar` só recebe `usuario=None` (o padrão), então
nenhuma resposta grava ou lê cookie de sessão (plano §3/§5). Todas usam a mesma consulta de
`dados.repositorio_publico` que decide quais páginas existem — `sitemap.xml` nunca lista uma
página que a rota da própria família recusaria (plano §3: "sitemap que lista página inexistente é
erro de indexação auto-infligido"). O `<script type="application/ld+json">` de cada página vem de
`_bloco_jsonld`: o `| safe` no template é seguro porque o conteúdo é sempre um dicionário Python
montado aqui (nunca texto solto de LLM — a regra de nunca usar `| safe` em texto de LLM, defeito
C3 da fatia 6, continua valendo para o resto da página).

Quando ler: ao mudar o conteúdo de uma página pública, o `sitemap.xml`/`robots.txt`, ou a
política de cache das rotas públicas.
"""

import json
from datetime import UTC, date, datetime, time
from email.utils import format_datetime
from typing import Annotated
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.api.templates import renderizar
from aprovaos.dados.repositorio_publico import (
    PaginaDuvida,
    PaginaTopicoBanca,
    PaginaVerticalizado,
    candidatas_familia_a,
    candidatas_familia_c,
    candidatas_familia_d,
    pagina_duvida,
    pagina_topico_banca,
    pagina_verticalizado,
)

router = APIRouter(include_in_schema=False)

#: Resposta pública cacheável (plano §5) — sem consulta por usuário, então o mesmo corpo vale
#: para qualquer visitante durante a janela.
CACHE_CONTROL_PUBLICO = "public, max-age=3600"

MENSAGEM_PAGINA_NAO_ENCONTRADA = "Esta página não existe ou ainda não passou do corte de conteúdo."

_ROBOTS_TXT = """User-agent: *
Disallow: /
Allow: /$
Allow: /o-que-cai/
Allow: /duvidas/
Allow: /verticalizado/
Allow: /sitemap.xml
Sitemap: {sitemap}
"""


def _bloco_jsonld(dado: dict[str, object]) -> str:
    """Serializa `dado` para um `<script type="application/ld+json">` seguro de embutir.

    `ensure_ascii=False` mantém o texto em pt-BR legível na fonte da página; escapar a barra de
    fechamento evita que um enunciado de questão contendo a sequência de fechamento de `script`
    feche a tag antes da hora — o único risco real de injeção neste bloco, já que `json.dumps`
    cuida do resto do escape.

    Args:
        dado: o objeto JSON-LD (schema.org) já montado.

    Returns:
        O JSON pronto para `{{ bloco | safe }}` dentro de `<script type="application/ld+json">`.
    """
    return json.dumps(dado, ensure_ascii=False).replace("</", "<\\/")


def _breadcrumb(base_url: str, itens: list[tuple[str, str]]) -> str:
    """Monta o `BreadcrumbList` (schema.org) comum a toda página pública (plano §4).

    Args:
        base_url: `str(request.base_url)` sem a barra final.
        itens: pares `(nome, caminho)`, na ordem da trilha (sem o "AprovaOS" inicial — esta
            função já o acrescenta).

    Returns:
        O JSON-LD pronto para `_bloco_jsonld`.
    """
    elementos = [{"@type": "ListItem", "position": 1, "name": "AprovaOS", "item": f"{base_url}/"}]
    for posicao, (nome, caminho) in enumerate(itens, start=2):
        elementos.append(
            {"@type": "ListItem", "position": posicao, "name": nome, "item": f"{base_url}{caminho}"}
        )
    return _bloco_jsonld(
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": elementos}
    )


def _faq(pergunta: str, resposta: str) -> str:
    """Monta o `FAQPage` (schema.org) da família C (plano §4)."""
    return _bloco_jsonld(
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": pergunta,
                    "acceptedAnswer": {"@type": "Answer", "text": resposta},
                }
            ],
        }
    )


def _cabecalhos_cache(atualizada_em_iso: str) -> dict[str, str]:
    """`Cache-Control` público + `Last-Modified` a partir de `atualizada_em_iso` (plano §5)."""
    data = date.fromisoformat(atualizada_em_iso)
    instante = datetime.combine(data, time.min, tzinfo=UTC)
    return {
        "Cache-Control": CACHE_CONTROL_PUBLICO,
        "Last-Modified": format_datetime(instante, usegmt=True),
    }


def _base_url(request: Request) -> str:
    """`str(request.base_url)` sem a barra final, para montar URL absoluta em JSON-LD/sitemap."""
    return str(request.base_url).rstrip("/")


@router.get("/o-que-cai/{banca}/{materia}/{topico}")
def obter_pagina_topico(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    banca: str,
    materia: str,
    topico: str,
) -> Response:
    """A página da família A: o que cai deste tópico, para esta banca.

    Nunca usa `exigir_usuario`/`usuario_atual` — página pública, sem cookie de sessão.

    Args:
        request: a requisição atual.
        db: sessão de banco (só leitura).
        banca: segmento de banca da URL.
        materia: segmento de matéria da URL.
        topico: segmento de tópico da URL (`Topico.slug`).

    Returns:
        `publico/topico.html`, com `Cache-Control`/`Last-Modified` (plano §5).

    Raises:
        HTTPException: 404 se os três segmentos não formarem um endereço que passou do corte
            (`dominio.pagina_publica.cabe_em_pagina`).
    """
    pagina: PaginaTopicoBanca | None = pagina_topico_banca(
        db, banca_slug=banca, materia_slug=materia, topico_slug=topico
    )
    if pagina is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_PAGINA_NAO_ENCONTRADA)

    jsonld = [
        _breadcrumb(
            _base_url(request),
            [(pagina.materia, f"/o-que-cai/{banca}/{materia}"), (pagina.h1, pagina.caminho)],
        )
    ]
    resposta = renderizar(request, "publico/topico.html", {"pagina": pagina, "jsonld": jsonld})
    resposta.headers.update(_cabecalhos_cache(pagina.atualizada_em_iso))
    return resposta


@router.get("/duvidas/{pergunta}")
def obter_pagina_duvida(
    request: Request, db: Annotated[Session, Depends(obter_db)], pergunta: str
) -> Response:
    """A página da família C: uma dúvida de formato, respondida a partir do DNA medido.

    Args:
        request: a requisição atual.
        db: sessão de banco (só leitura).
        pergunta: slug da pergunta.

    Returns:
        `publico/duvida.html`, com `FAQPage` e `BreadcrumbList` em JSON-LD.

    Raises:
        HTTPException: 404 se a pergunta não existir no catálogo.
    """
    pagina: PaginaDuvida | None = pagina_duvida(db, slug_pergunta=pergunta)
    if pagina is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_PAGINA_NAO_ENCONTRADA)

    jsonld = [
        _breadcrumb(_base_url(request), [("Dúvidas", "/duvidas"), (pagina.h1, pagina.caminho)]),
        _faq(pagina.pergunta, pagina.resposta),
    ]
    resposta = renderizar(request, "publico/duvida.html", {"pagina": pagina, "jsonld": jsonld})
    resposta.headers.update(_cabecalhos_cache(pagina.atualizada_em_iso))
    return resposta


@router.get("/verticalizado/{orgao_ano}")
def obter_pagina_verticalizado(
    request: Request, db: Annotated[Session, Depends(obter_db)], orgao_ano: str
) -> Response:
    """A página da família D: o edital verticalizado público de um concurso.

    Args:
        request: a requisição atual.
        db: sessão de banco (só leitura).
        orgao_ano: segmento `{orgao}-{ano}` da URL.

    Returns:
        `publico/verticalizado.html`.

    Raises:
        HTTPException: 404 se não houver concurso com `data_prova` conhecida nesse endereço.
    """
    pagina: PaginaVerticalizado | None = pagina_verticalizado(db, slug_orgao_ano=orgao_ano)
    if pagina is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_PAGINA_NAO_ENCONTRADA)

    jsonld = [
        _breadcrumb(
            _base_url(request), [("Verticalizado", "/verticalizado"), (pagina.h1, pagina.caminho)]
        )
    ]
    resposta = renderizar(
        request, "publico/verticalizado.html", {"pagina": pagina, "jsonld": jsonld}
    )
    resposta.headers.update(_cabecalhos_cache(pagina.atualizada_em_iso))
    return resposta


def _url_sitemap(base_url: str, caminho: str, atualizada_em_iso: str) -> str:
    return (
        "<url>"
        f"<loc>{escape(base_url + caminho)}</loc>"
        f"<lastmod>{escape(atualizada_em_iso)}</lastmod>"
        "</url>"
    )


@router.get("/sitemap.xml")
def obter_sitemap(request: Request, db: Annotated[Session, Depends(obter_db)]) -> Response:
    """O `sitemap.xml`, montado da mesma consulta que decide quais páginas existem.

    Só lista páginas canônicas da família A (`pagina.canonica is None`) — uma equivalente não
    entra aqui, mesmo sendo servível no próprio endereço (ela leva `<link rel="canonical">` para
    a canônica, plano §3/Ruling 49); listá-la no sitemap seria pedir ao buscador para indexar as
    duas como conteúdos distintos.

    Args:
        request: a requisição atual (dá a URL base absoluta).
        db: sessão de banco (só leitura).

    Returns:
        `Response` com `media_type="application/xml"`.
    """
    base_url = _base_url(request)
    hoje = date.today().isoformat()
    urls = [_url_sitemap(base_url, "/", hoje)]
    for pagina_a in candidatas_familia_a(db):
        if pagina_a.canonica is None:
            urls.append(_url_sitemap(base_url, pagina_a.caminho, pagina_a.atualizada_em_iso))
    for pagina_c in candidatas_familia_c(db):
        urls.append(_url_sitemap(base_url, pagina_c.caminho, pagina_c.atualizada_em_iso))
    for pagina_d in candidatas_familia_d(db):
        urls.append(_url_sitemap(base_url, pagina_d.caminho, pagina_d.atualizada_em_iso))
    corpo = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>"
    )
    return Response(content=corpo, media_type="application/xml")


@router.get("/robots.txt")
def obter_robots(request: Request) -> Response:
    """`robots.txt`, liberando só os prefixos das famílias que de fato existem (plano §3).

    Args:
        request: a requisição atual (dá a URL base absoluta do `Sitemap:`).

    Returns:
        `Response` com `media_type="text/plain"`.
    """
    conteudo = _ROBOTS_TXT.format(sitemap=f"{_base_url(request)}/sitemap.xml")
    return Response(content=conteudo, media_type="text/plain")

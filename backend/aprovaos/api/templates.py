"""Templates Jinja do AprovaOS: fábrica e helper de renderização.

O que é: `criar_templates(web_dir)` (chamado só dentro de `criar_app`, porque `Jinja2Templates`
lê disco), `renderizar(request, nome, contexto, usuario)` (injeta `usuario_email` para a
navegação) e `responder_redirecionamento(request, destino)` (`HX-Redirect` para HTMX, `303` sem
JS). Quando ler: ao escrever uma rota HTML — nunca instancie `Jinja2Templates` fora da fábrica.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import Request, Response
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse, RedirectResponse

from aprovaos.dados.modelos import Usuario


def criar_templates(web_dir: Path) -> Jinja2Templates:
    """Cria o ambiente Jinja apontando para `web_dir/templates`.

    Args:
        web_dir: pasta `web/` do repositório (ou `WEB_DIR` no container).

    Returns:
        O `Jinja2Templates` que a app guarda em `app.state.templates`.
    """
    return Jinja2Templates(directory=web_dir / "templates")


def renderizar(
    request: Request,
    nome: str,
    contexto: Mapping[str, Any] | None = None,
    usuario: Usuario | None = None,
) -> HTMLResponse:
    """Renderiza um template com o ambiente guardado em `request.app.state.templates`.

    O template recebe sempre `usuario_email` (`str` ou `None`) para a navegação de `base.html`;
    o modelo ORM nunca chega ao template (convenção transversal do plano V1).

    Args:
        request: a requisição atual (obrigatória na assinatura do FastAPI ≥ 0.108).
        nome: caminho do template relativo a `web/templates` (ex.: `inicio.html`).
        contexto: variáveis para o template; o `request` é acrescentado pelo Starlette.
        usuario: o usuário logado (de `usuario_atual`), ou `None` para anônimo.

    Returns:
        A resposta HTML com status 200.
    """
    templates: Jinja2Templates = request.app.state.templates
    variaveis: dict[str, Any] = {"usuario_email": usuario.email if usuario else None}
    variaveis.update(contexto or {})
    return templates.TemplateResponse(request=request, name=nome, context=variaveis)


def responder_redirecionamento(request: Request, destino: str) -> Response:
    """Redireciona após um formulário: `HX-Redirect` sob HTMX, `303 See Other` sem JS.

    Args:
        request: a requisição atual; `HX-Request: true` indica envio pelo htmx.
        destino: caminho de destino (ex.: `/conta`).

    Returns:
        `Response` 200 com `HX-Redirect` ou `RedirectResponse` 303 com `Location`.
    """
    if request.headers.get("HX-Request") == "true":
        return Response(status_code=200, headers={"HX-Redirect": destino})
    return RedirectResponse(destino, status_code=303)

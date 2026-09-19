"""A página de amostra da biblioteca de componentes — `GET /estilo`, só em desenvolvimento.

O que é: o espelho do sistema visual (fatia 14). Mostra cada componente de
`web/static/css/componentes.css` uma vez, para revisar o sistema inteiro numa tela em vez de
abrir doze. Quando ler: ao acrescentar um componente à biblioteca — a amostra dele entra em
`web/templates/estilo/pagina.html` no mesmo commit.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from aprovaos.api.templates import renderizar
from aprovaos.config import Configuracoes

router = APIRouter()


@router.get("/estilo")
def estilo(request: Request) -> HTMLResponse:
    """Mostra a amostra da biblioteca; 404 fora de `AMBIENTE=dev`.

    Não é tela de produto: é ferramenta de quem constrói. Fica fora do ar em produção para não
    virar uma página pública que ninguém mantém.

    Args:
        request: a requisição atual (`app.state.config`).

    Returns:
        O HTML de `estilo/pagina.html`.

    Raises:
        HTTPException: 404 quando `AMBIENTE` não é `dev`.
    """
    config: Configuracoes = request.app.state.config
    if config.ambiente != "dev":
        raise HTTPException(status_code=404)
    return renderizar(request, "estilo/pagina.html", {})

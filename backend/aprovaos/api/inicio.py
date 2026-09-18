"""Landing do AprovaOS: `GET /` renderiza `inicio.html`.

O que é: router da página inicial; a navegação reflete o login via `usuario_atual`. Quando ler:
ao mudar a landing.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from starlette.responses import HTMLResponse

from aprovaos.api.sessao import usuario_atual
from aprovaos.api.templates import renderizar
from aprovaos.dados.modelos import Usuario

router = APIRouter()


@router.get("/", include_in_schema=False)
def inicio(
    request: Request, usuario: Annotated[Usuario | None, Depends(usuario_atual)]
) -> HTMLResponse:
    """Página inicial: nome, frase e botão de criar conta (ou de ir à conta, se logado).

    Args:
        request: a requisição atual.
        usuario: o usuário logado, ou `None`.

    Returns:
        O HTML de `inicio.html`.
    """
    return renderizar(request, "inicio.html", usuario=usuario)

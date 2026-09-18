"""Dependência FastAPI que entrega uma `Session` por request, fechada ao fim.

O que é: `obter_db(request)`. Quando ler: ao escrever uma rota que fala com o banco —
use `Annotated[Session, Depends(obter_db)]`; o `commit` é responsabilidade da rota.
"""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def obter_db(request: Request) -> Iterator[Session]:
    """Abre uma sessão da fábrica guardada em `app.state.fabrica_sessao` e a fecha depois.

    Args:
        request: a requisição atual (dá acesso à app e ao seu estado).

    Yields:
        A `Session` ligada ao engine da app.
    """
    with request.app.state.fabrica_sessao() as db:
        yield db

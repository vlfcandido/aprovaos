"""Healthcheck: `GET /saude` confirma que a app responde e que o banco aceita `SELECT 1`.

O que é: router de saúde. Quando ler: ao configurar monitoramento ou o healthcheck do Compose.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db

router = APIRouter()


class RespostaSaude(BaseModel):
    """Resposta do healthcheck.

    Attributes:
        status: `ok` quando a app responde.
        banco: `ok` quando o banco executou `SELECT 1`.
    """

    status: str
    banco: str


@router.get("/saude")
def saude(db: Annotated[Session, Depends(obter_db)]) -> RespostaSaude:
    """Executa `SELECT 1` no banco; 503 (`banco_indisponivel`) se a conexão falhar.

    Args:
        db: sessão por request.

    Returns:
        `{"status": "ok", "banco": "ok"}`.

    Raises:
        HTTPException: 503 quando o banco não responde.
    """
    try:
        db.execute(text("SELECT 1"))
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail="banco indisponível") from exc
    return RespostaSaude(status="ok", banco="ok")

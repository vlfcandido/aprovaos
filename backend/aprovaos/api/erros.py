"""Formato de erro do produto (`{codigo, mensagem, acao}`, arquitetura §7) e seus tratadores.

O que é: `ErroApi` e `registrar_tratadores(app)` para `HTTPException`, `RequestValidationError`,
`RedirecionarParaEntrar` (303 para `/entrar`) e exceção não tratada; `mensagens_de_validacao`
traduz um `ValidationError` de formulário para pt-BR. Quando ler: ao criar um código de erro
novo, ao ver um erro sair fora do formato ou ao mostrar erro de campo numa página HTML.
"""

import http
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from aprovaos.api.sessao import RedirecionarParaEntrar

CODIGO_POR_STATUS: dict[int, str] = {
    401: "nao_autenticado",
    403: "proibido",
    404: "nao_encontrado",
    422: "dados_invalidos",
    503: "banco_indisponivel",
}

ACAO_POR_CODIGO: dict[str, str] = {
    "nao_autenticado": "Entre na sua conta e tente de novo.",
    "proibido": "Você não tem acesso a este recurso.",
    "nao_encontrado": "Confira o endereço ou volte à página inicial.",
    "dados_invalidos": "Corrija os campos indicados e envie de novo.",
    "banco_indisponivel": "Tente de novo em alguns instantes.",
    "erro_interno": "Tente de novo; se persistir, avise o suporte.",
}


MENSAGEM_PADRAO: dict[int, str] = {
    404: "Página ou recurso não encontrado.",
    405: "Método não permitido para este endereço.",
}

ROTULO_DO_CAMPO: dict[str, str] = {"email": "E-mail", "senha": "Senha"}


class ErroApi(BaseModel):
    """Corpo de toda resposta de erro que não seja um formulário HTML.

    Attributes:
        codigo: identificador estável, em snake_case (`nao_encontrado`, `dados_invalidos`…).
        mensagem: o que aconteceu, em pt-BR, sem detalhes internos.
        acao: o que a pessoa pode fazer a respeito.
    """

    codigo: str
    mensagem: str
    acao: str


def codigo_para_status(status: int) -> str:
    """Traduz o status HTTP no `codigo` do produto (`erro_interno` para os demais).

    Args:
        status: código de status HTTP.

    Returns:
        O `codigo` correspondente.
    """
    return CODIGO_POR_STATUS.get(status, "erro_interno")


def _resposta(status: int, mensagem: str, headers: Mapping[str, str] | None = None) -> JSONResponse:
    codigo = codigo_para_status(status)
    erro = ErroApi(codigo=codigo, mensagem=mensagem, acao=ACAO_POR_CODIGO[codigo])
    return JSONResponse(status_code=status, content=erro.model_dump(), headers=headers)


def _mensagem_http(exc: StarletteHTTPException) -> str:
    """Traduz a frase padrão do Starlette (`Not Found`) quando a rota não deu detalhe próprio."""
    frase_padrao = http.HTTPStatus(exc.status_code).phrase
    if str(exc.detail) == frase_padrao and exc.status_code in MENSAGEM_PADRAO:
        return MENSAGEM_PADRAO[exc.status_code]
    return str(exc.detail)


def _campos_invalidos(exc: RequestValidationError) -> str:
    campos = []
    for erro in exc.errors():
        local = ".".join(str(parte) for parte in erro.get("loc", ()) if parte != "body")
        campos.append(f"{local}: {erro.get('msg', 'inválido')}")
    return "; ".join(campos) or "corpo inválido"


def _mensagem_do_erro(campo: str, erro: Mapping[str, Any]) -> str:
    """Traduz um item de `ValidationError.errors()` para uma frase curta em pt-BR."""
    rotulo = ROTULO_DO_CAMPO.get(campo, campo)
    tipo = erro.get("type", "")
    contexto = erro.get("ctx") or {}
    if tipo == "string_too_short":
        return f"{rotulo}: use no mínimo {contexto['min_length']} caracteres."
    if tipo == "string_too_long":
        return f"{rotulo}: use no máximo {contexto['max_length']} caracteres."
    if tipo == "missing":
        return f"{rotulo}: campo obrigatório."
    if campo == "email":
        return "E-mail inválido. Confira o endereço e tente de novo."
    return f"{rotulo}: valor inválido."


def mensagens_de_validacao(erro: ValidationError) -> list[str]:
    """Converte um `ValidationError` de formulário em mensagens pt-BR, uma por campo.

    Args:
        erro: a exceção levantada ao montar `DadosCadastro`/`DadosLogin`.

    Returns:
        Lista de frases prontas para o template (sem detalhes internos do Pydantic).
    """
    mensagens: list[str] = []
    for item in erro.errors():
        local = item.get("loc") or ("",)
        campo = str(local[0])
        mensagem = _mensagem_do_erro(campo, item)
        if mensagem not in mensagens:
            mensagens.append(mensagem)
    return mensagens


def registrar_tratadores(app: FastAPI) -> None:
    """Instala na app os tratadores que convertem exceções em `ErroApi`.

    Args:
        app: a aplicação FastAPI criada por `criar_app`.
    """

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _resposta(exc.status_code, _mensagem_http(exc), exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _resposta(422, f"Dados inválidos — {_campos_invalidos(exc)}")

    @app.exception_handler(RedirecionarParaEntrar)
    async def _entrar(request: Request, exc: RedirecionarParaEntrar) -> RedirectResponse:
        return RedirectResponse("/entrar", status_code=303)

    @app.exception_handler(Exception)
    async def _interno(request: Request, exc: Exception) -> JSONResponse:
        return _resposta(500, "Erro inesperado no servidor.")

"""Rotas HTML de conta: `/cadastro`, `/entrar`, `/conta` (protegida) e `/sair`.

O que é: router com formulários de conta — `GET` renderiza, `POST` valida (`DadosCadastro`),
persiste, abre sessão e redireciona (`HX-Redirect` ou 303); erros esperados voltam na mesma
página com mensagem e status 200. Quando ler: ao mexer em cadastro, login ou logout.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.api.erros import mensagens_de_validacao
from aprovaos.api.sessao import (
    assinar,
    definir_cookie,
    exigir_usuario,
    limpar_cookie,
    token_do_request,
    usuario_atual,
)
from aprovaos.api.templates import renderizar, responder_redirecionamento
from aprovaos.config import Configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Usuario
from aprovaos.dados.repositorio_conta import autenticar, criar_conta
from aprovaos.dados.repositorio_sessao import abrir_sessao, revogar_sessao
from aprovaos.dominio.conta import DadosCadastro, DadosLogin
from aprovaos.dominio.erros import CredenciaisInvalidas, EmailJaCadastrado

router = APIRouter(include_in_schema=False)

MENSAGEM_EMAIL_REPETIDO = "Já existe conta com este e-mail."
MENSAGEM_LOGIN_INVALIDO = "E-mail ou senha inválidos. Confira e tente de novo."


def _entrar_com(request: Request, db: Session, usuario: Usuario, destino: str) -> Response:
    """Abre a sessão do usuário, faz o commit e devolve o redirecionamento com o cookie."""
    config: Configuracoes = request.app.state.config
    token = abrir_sessao(db, usuario, dias=config.sessao_dias, agora=agora_utc())
    db.commit()
    resposta = responder_redirecionamento(request, destino)
    definir_cookie(resposta, assinar(token, config.chave_secreta.get_secret_value()), config)
    return resposta


@router.get("/cadastro")
def cadastro(
    request: Request, usuario: Annotated[Usuario | None, Depends(usuario_atual)]
) -> Response:
    """Formulário de criar conta.

    Args:
        request: a requisição atual.
        usuario: o usuário logado, ou `None` (só para a navegação).

    Returns:
        O HTML de `conta/cadastro.html` sem erros.
    """
    return renderizar(request, "conta/cadastro.html", {"erros": [], "email": ""}, usuario)


@router.post("/cadastro")
def cadastrar(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario_logado: Annotated[Usuario | None, Depends(usuario_atual)],
    email: Annotated[str, Form()],
    senha: Annotated[str, Form()],
) -> Response:
    """Cria a conta, abre a sessão e redireciona para `/conta`.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario_logado: o usuário já logado, ou `None` (só para a navegação em caso de erro).
        email: campo `email` do formulário.
        senha: campo `senha` do formulário.

    Returns:
        Redirecionamento com cookie no sucesso; a página com mensagens (200) em erro esperado.
    """
    try:
        dados = DadosCadastro(email=email, senha=senha)
        usuario = criar_conta(db, dados)
    except ValidationError as erro:
        erros = mensagens_de_validacao(erro)
    except EmailJaCadastrado:
        erros = [MENSAGEM_EMAIL_REPETIDO]
    else:
        db.commit()
        return _entrar_com(request, db, usuario, "/conta")
    contexto = {"erros": erros, "email": email}
    return renderizar(request, "conta/cadastro.html", contexto, usuario_logado)


@router.get("/entrar")
def entrar(
    request: Request, usuario: Annotated[Usuario | None, Depends(usuario_atual)]
) -> Response:
    """Formulário de login.

    Args:
        request: a requisição atual.
        usuario: o usuário logado, ou `None` (só para a navegação).

    Returns:
        O HTML de `conta/entrar.html` sem erros.
    """
    return renderizar(request, "conta/entrar.html", {"erros": [], "email": ""}, usuario)


@router.post("/entrar")
def autenticar_e_entrar(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario_logado: Annotated[Usuario | None, Depends(usuario_atual)],
    email: Annotated[str, Form()],
    senha: Annotated[str, Form()],
) -> Response:
    """Autentica, abre sessão nova e redireciona para `/conta`.

    Qualquer falha (e-mail malformado, inexistente, senha errada) devolve a mesma mensagem
    genérica, para não enumerar contas.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario_logado: o usuário já logado, ou `None` (só para a navegação em caso de erro).
        email: campo `email` do formulário.
        senha: campo `senha` do formulário.

    Returns:
        Redirecionamento com cookie no sucesso; a página com a mensagem (200) em falha.
    """
    try:
        usuario = autenticar(db, DadosLogin(email=email, senha=senha))
    except (ValidationError, CredenciaisInvalidas):
        contexto = {"erros": [MENSAGEM_LOGIN_INVALIDO], "email": email}
        return renderizar(request, "conta/entrar.html", contexto, usuario_logado)
    return _entrar_com(request, db, usuario, "/conta")


@router.get("/conta")
def minha_conta(request: Request, usuario: Annotated[Usuario, Depends(exigir_usuario)]) -> Response:
    """Página protegida mínima: mostra o e-mail e o botão de sair.

    Args:
        request: a requisição atual.
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).

    Returns:
        O HTML de `conta/conta.html`.
    """
    return renderizar(request, "conta/conta.html", {"email": usuario.email}, usuario)


@router.post("/sair")
def sair(request: Request, db: Annotated[Session, Depends(obter_db)]) -> Response:
    """Revoga a sessão do cookie (se houver), limpa o cookie e volta para `/`.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).

    Returns:
        Redirecionamento para `/` (`HX-Redirect` ou 303) com o cookie expirado.
    """
    token = token_do_request(request)
    if token is not None:
        revogar_sessao(db, token, agora_utc())
        db.commit()
    resposta = responder_redirecionamento(request, "/")
    limpar_cookie(resposta, request.app.state.config)
    return resposta

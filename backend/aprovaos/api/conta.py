"""Rotas HTML de conta: `/cadastro`, `/entrar`, `/entrar/google`, `/conta` e `/sair`.

O que é: router com formulários de conta — `GET` renderiza, `POST` valida (`DadosCadastro`),
persiste, abre sessão e redireciona (`HX-Redirect` ou 303); erros esperados voltam na mesma
página com mensagem e status 200. `GET /entrar/google` e `GET /entrar/google/callback` são o
login por Google (fatia 1b, RF-20, Ruling 42): sem `GOOGLE_OAUTH_CLIENT_ID`/`_SECRET`
configurados, a rota devolve 404 e o botão não é renderizado — fluxo inteiro implementado,
inerte até o dono colar as credenciais no `.env`. Fonte: doc oficial do Google Identity, OAuth
2.0 para aplicações web — https://developers.google.com/identity/protocols/oauth2/web-server (e
o endpoint `userinfo`, https://developers.google.com/identity/openid-connect/openid-connect).
Quando ler: ao mexer em cadastro, login (e-mail+senha ou Google) ou logout.
"""

import secrets
from collections.abc import Mapping
from typing import Annotated, Any, Protocol
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
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
    verificar_assinatura,
)
from aprovaos.api.templates import renderizar, responder_redirecionamento
from aprovaos.config import Configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Usuario
from aprovaos.dados.repositorio_assinatura import (
    assinatura_do_usuario,
    cancelar_assinatura,
    tier_do_usuario,
)
from aprovaos.dados.repositorio_conta import autenticar, criar_conta, criar_ou_ligar_conta_google
from aprovaos.dados.repositorio_lgpd import excluir_dados_do_usuario, exportar_dados_do_usuario
from aprovaos.dados.repositorio_sessao import abrir_sessao, revogar_sessao
from aprovaos.dominio.conta import DadosCadastro, DadosLogin, PerfilGoogle
from aprovaos.dominio.erros import (
    CredenciaisInvalidas,
    EmailGoogleNaoVerificado,
    EmailJaCadastrado,
    GoogleOAuthIndisponivel,
)
from aprovaos.pagamento.gateway import GatewayPagamento

router = APIRouter(include_in_schema=False)

MENSAGEM_EMAIL_REPETIDO = "Já existe conta com este e-mail."
MENSAGEM_LOGIN_INVALIDO = "E-mail ou senha inválidos. Confira e tente de novo."
MENSAGEM_GOOGLE_INDISPONIVEL = (
    "Não deu para entrar com o Google agora. Tente de novo ou use e-mail e senha."
)
MENSAGEM_GOOGLE_ESTADO_INVALIDO = "Sessão de login com o Google expirou. Tente de novo."

#: Doc oficial: https://developers.google.com/identity/protocols/oauth2/web-server
URL_AUTORIZACAO_GOOGLE = "https://accounts.google.com/o/oauth2/v2/auth"
URL_TOKEN_GOOGLE = "https://oauth2.googleapis.com/token"
#: Doc oficial: https://developers.google.com/identity/openid-connect/openid-connect#obtaininguserprofileinformation
URL_USERINFO_GOOGLE = "https://openidconnect.googleapis.com/v1/userinfo"


class _RespostaHttpOAuth(Protocol):
    """O subconjunto de `httpx2.Response` que o login por Google usa."""

    @property
    def status_code(self) -> int:
        """Código de status HTTP da resposta."""
        ...

    def json(self) -> Any:
        """Devolve o corpo da resposta já decodificado."""
        ...


class _ClienteHttpOAuth(Protocol):
    """O subconjunto de `httpx2.Client` que o login por Google usa.

    Mesmo molde de `motor/fontes/cebraspe.py::_ClienteHttp` — também satisfeito por um dublê de
    teste.
    """

    def post(self, url: str, *, data: Mapping[str, str]) -> _RespostaHttpOAuth:
        """Executa um `POST` com corpo `application/x-www-form-urlencoded` e devolve a resposta."""
        ...

    def get(self, url: str, *, headers: Mapping[str, str]) -> _RespostaHttpOAuth:
        """Executa um `GET` e devolve a resposta."""
        ...


def _google_disponivel(config: Configuracoes) -> bool:
    """`True` só com as duas credenciais configuradas (Ruling 42: as duas nascem juntas)."""
    tem_id = config.google_oauth_client_id is not None
    tem_secret = config.google_oauth_client_secret is not None
    return tem_id and tem_secret


def _url_autorizacao_google(client_id: str, redirect_uri: str, state: str) -> str:
    """Monta a URL de consentimento do Google (`response_type=code`, escopo `openid email`)."""
    parametros = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email",
        "state": state,
    }
    return f"{URL_AUTORIZACAO_GOOGLE}?{urlencode(parametros)}"


def trocar_codigo_por_perfil(
    cliente: _ClienteHttpOAuth,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> PerfilGoogle:
    """Troca o código de autorização por um token e lê o perfil no endpoint `userinfo` do Google.

    Args:
        cliente: cliente HTTP (real ou dublê de teste).
        client_id: `Configuracoes.google_oauth_client_id`.
        client_secret: `Configuracoes.google_oauth_client_secret`, já sem `SecretStr`.
        code: o `code` devolvido no `GET /entrar/google/callback`.
        redirect_uri: a mesma URI usada em `/entrar/google` (o Google exige que bata).

    Returns:
        O `PerfilGoogle` já validado.

    Raises:
        GoogleOAuthIndisponivel: falha ao trocar o código ou ao consultar o perfil.
        EmailGoogleNaoVerificado: `email_verified=false`.
    """
    resposta_token = cliente.post(
        URL_TOKEN_GOOGLE,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if resposta_token.status_code >= 400:
        raise GoogleOAuthIndisponivel(f"token endpoint devolveu {resposta_token.status_code}")
    access_token = resposta_token.json().get("access_token")
    if not access_token:
        raise GoogleOAuthIndisponivel("resposta de token sem access_token")

    resposta_perfil = cliente.get(
        URL_USERINFO_GOOGLE, headers={"Authorization": f"Bearer {access_token}"}
    )
    if resposta_perfil.status_code >= 400:
        raise GoogleOAuthIndisponivel(f"userinfo devolveu {resposta_perfil.status_code}")
    perfil = PerfilGoogle.model_validate(resposta_perfil.json())
    if not perfil.email_verified:
        raise EmailGoogleNaoVerificado()
    return perfil


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
    config: Configuracoes = request.app.state.config
    contexto = {"erros": [], "email": "", "google_oauth_disponivel": _google_disponivel(config)}
    return renderizar(request, "conta/cadastro.html", contexto, usuario)


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
    config: Configuracoes = request.app.state.config
    contexto = {
        "erros": erros,
        "email": email,
        "google_oauth_disponivel": _google_disponivel(config),
    }
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
    config: Configuracoes = request.app.state.config
    contexto = {"erros": [], "email": "", "google_oauth_disponivel": _google_disponivel(config)}
    return renderizar(request, "conta/entrar.html", contexto, usuario)


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
        config: Configuracoes = request.app.state.config
        contexto = {
            "erros": [MENSAGEM_LOGIN_INVALIDO],
            "email": email,
            "google_oauth_disponivel": _google_disponivel(config),
        }
        return renderizar(request, "conta/entrar.html", contexto, usuario_logado)
    return _entrar_com(request, db, usuario, "/conta")


@router.get("/entrar/google")
def entrar_google(request: Request) -> Response:
    """Monta a URL de consentimento do Google e redireciona (Ruling 42).

    O `state` é um nonce assinado pelo mesmo HMAC do cookie de sessão (ADR-0026) — o callback
    rejeita qualquer `state` adulterado ou de outra chave.

    Args:
        request: a requisição atual.

    Returns:
        Redirecionamento 302 para a tela de consentimento do Google.

    Raises:
        HTTPException: 404 sem `GOOGLE_OAUTH_CLIENT_ID`/`_SECRET` configurados.
    """
    config: Configuracoes = request.app.state.config
    if not _google_disponivel(config):
        raise HTTPException(status_code=404)
    assert config.google_oauth_client_id is not None  # _google_disponivel já garantiu
    estado = assinar(secrets.token_urlsafe(24), config.chave_secreta.get_secret_value())
    redirect_uri = str(request.url_for("entrar_google_callback"))
    url = _url_autorizacao_google(config.google_oauth_client_id, redirect_uri, estado)
    return RedirectResponse(url, status_code=302)


@router.get("/entrar/google/callback", name="entrar_google_callback")
def entrar_google_callback(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    code: str | None = None,
    state: str | None = None,
) -> Response:
    """Troca o código pelo perfil, cria ou liga a conta e abre sessão (Ruling 42).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        code: o `code` de autorização devolvido pelo Google.
        state: o nonce assinado devolvido pelo Google — precisa bater com `entrar_google`.

    Returns:
        Redirecionamento com cookie no sucesso; `conta/entrar.html` com mensagem (200) quando o
        `state` é inválido/ausente, falta `code`, o provedor falha, ou o e-mail não é verificado.

    Raises:
        HTTPException: 404 sem `GOOGLE_OAUTH_CLIENT_ID`/`_SECRET` configurados.
    """
    config: Configuracoes = request.app.state.config
    if not _google_disponivel(config):
        raise HTTPException(status_code=404)
    assert config.google_oauth_client_id is not None  # _google_disponivel já garantiu
    assert config.google_oauth_client_secret is not None

    chave = config.chave_secreta.get_secret_value()
    estado_valido = state is not None and verificar_assinatura(state, chave) is not None
    if not estado_valido or code is None:
        contexto = {
            "erros": [MENSAGEM_GOOGLE_ESTADO_INVALIDO],
            "email": "",
            "google_oauth_disponivel": True,
        }
        return renderizar(request, "conta/entrar.html", contexto, None)

    cliente: _ClienteHttpOAuth = request.app.state.cliente_google_oauth
    redirect_uri = str(request.url_for("entrar_google_callback"))
    try:
        perfil = trocar_codigo_por_perfil(
            cliente,
            config.google_oauth_client_id,
            config.google_oauth_client_secret.get_secret_value(),
            code,
            redirect_uri,
        )
    except (GoogleOAuthIndisponivel, EmailGoogleNaoVerificado):
        contexto = {
            "erros": [MENSAGEM_GOOGLE_INDISPONIVEL],
            "email": "",
            "google_oauth_disponivel": True,
        }
        return renderizar(request, "conta/entrar.html", contexto, None)

    usuario = criar_ou_ligar_conta_google(db, perfil.sub, perfil.email)
    return _entrar_com(request, db, usuario, "/conta")


@router.get("/conta")
def minha_conta(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
) -> Response:
    """Página da conta: e-mail, sair, o bloco de assinatura (fatia 12) e os botões de LGPD.

    O bloco de assinatura só aparece com o gateway configurado (Ruling 46) — sem ele, o produto
    roda como hoje e todo mundo é Free sem tela nenhuma de billing. Os botões de exportar/excluir
    (RF-23) aparecem sempre, independente do gateway: LGPD não é billing.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).

    Returns:
        O HTML de `conta/conta.html`.
    """
    gateway: GatewayPagamento | None = request.app.state.gateway_pagamento
    contexto: dict[str, object] = {
        "email": usuario.email,
        "billing_disponivel": gateway is not None,
    }
    if gateway is not None:
        contexto["assinatura"] = assinatura_do_usuario(db, usuario.id)
        contexto["tier"] = "pro" if _e_pro_agora(db, usuario) else "free"
    return renderizar(request, "conta/conta.html", contexto, usuario)


def _e_pro_agora(db: Session, usuario: Usuario) -> bool:
    """`True` se o tier efetivo do usuário, agora, é Pro (`dados.repositorio_assinatura`)."""
    return tier_do_usuario(db, usuario.id, agora_utc().date()) == "pro"


@router.get("/conta/exportar")
def exportar_conta(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
) -> Response:
    """Exporta tudo que é do usuário em JSON (RF-23).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado.

    Returns:
        `JSONResponse` com `dados.repositorio_lgpd.exportar_dados_do_usuario`.
    """
    return JSONResponse(exportar_dados_do_usuario(db, usuario))


@router.post("/conta/excluir")
def excluir_conta(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    confirmar: Annotated[str | None, Form()] = None,
) -> Response:
    """Exclui a conta (RF-23, Ruling 48) — exige confirmação explícita e cancela a assinatura antes.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        confirmar: precisa vir preenchido (o formulário só o manda com a caixa marcada) — sem
            isso, a página volta sem apagar nada (200, nunca um erro por "esquecer de marcar").

    Returns:
        `conta/conta.html` com aviso (200) sem confirmação; redirecionamento para `/` com o
        cookie limpo, depois de excluir.
    """
    if not confirmar:
        contexto = {
            "email": usuario.email,
            "aviso_exclusao": "Marque a confirmação para excluir sua conta.",
        }
        return renderizar(request, "conta/conta.html", contexto, usuario)

    gateway: GatewayPagamento | None = request.app.state.gateway_pagamento
    if gateway is not None:
        assinatura = assinatura_do_usuario(db, usuario.id)
        if assinatura is not None and assinatura.status in ("ativa", "em_atraso"):
            gateway.cancelar(assinatura.id_externo)
            cancelar_assinatura(db, assinatura, agora_utc())

    token = token_do_request(request)
    if token is not None:
        revogar_sessao(db, token, agora_utc())
    excluir_dados_do_usuario(db, usuario, agora_utc())
    db.commit()

    resposta = responder_redirecionamento(request, "/")
    limpar_cookie(resposta, request.app.state.config)
    return resposta


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

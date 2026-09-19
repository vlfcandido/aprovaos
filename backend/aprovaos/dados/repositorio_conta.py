"""Repositório de conta: cadastro (tenant PF + usuário), autenticação e login por Google.

O que é: `buscar_por_email`, `criar_conta`, `autenticar` (e-mail+senha) e
`criar_ou_ligar_conta_google` (fatia 1b, RF-20, Ruling 42) sobre uma `Session`. Quando ler: ao
escrever a rota de cadastro/login/Google ou ao mudar as regras do modelo de dados §2. As funções
fazem `add`/`flush`; o `commit` é sempre da rota (convenção transversal do plano V1).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Tenant, Usuario
from aprovaos.dominio.conta import DadosCadastro, DadosLogin
from aprovaos.dominio.erros import CredenciaisInvalidas, EmailJaCadastrado
from aprovaos.dominio.senha import gerar_hash, verificar


def buscar_por_email(db: Session, email: str) -> Usuario | None:
    """Localiza o usuário ativo (sem `excluido_em`) com este e-mail.

    Args:
        db: sessão do request.
        email: e-mail já normalizado em minúsculas.

    Returns:
        O `Usuario`, ou `None` se não existir ou estiver excluído.
    """
    consulta = select(Usuario).where(Usuario.email == email, Usuario.excluido_em.is_(None))
    return db.scalars(consulta).first()


def criar_conta(db: Session, dados: DadosCadastro) -> Usuario:
    """Cria o tenant PF (nome = e-mail) e o usuário com senha em argon2id.

    Verifica o e-mail por consulta antes de inserir; a `UNIQUE` de `usuario.email` é a rede
    de segurança contra corrida. Faz `add` + `flush`; a rota faz o `commit`.

    Args:
        db: sessão do request.
        dados: e-mail e senha validados.

    Returns:
        O `Usuario` novo, já com `id` e `tenant` preenchidos.

    Raises:
        EmailJaCadastrado: se já houver conta ativa com o e-mail.
    """
    if buscar_por_email(db, dados.email) is not None:
        raise EmailJaCadastrado(dados.email)
    tenant = Tenant(tipo="pf", nome=dados.email)
    usuario = Usuario(email=dados.email, senha_hash=gerar_hash(dados.senha), tenant=tenant)
    db.add(usuario)
    db.flush()
    return usuario


def autenticar(db: Session, dados: DadosLogin) -> Usuario:
    """Devolve o usuário se e-mail e senha conferirem; falha sempre com a mesma exceção.

    Args:
        db: sessão do request.
        dados: e-mail e senha do formulário de login.

    Returns:
        O `Usuario` autenticado.

    Raises:
        CredenciaisInvalidas: e-mail inexistente, conta excluída, conta só-Google (sem
            `senha_hash`) ou senha errada — sem distinguir o motivo, para não enumerar contas
            nem revelar que aquele e-mail só entra pelo Google (mesma cautela da P-22).
    """
    usuario = buscar_por_email(db, dados.email)
    if usuario is None or usuario.senha_hash is None:
        raise CredenciaisInvalidas()
    if not verificar(usuario.senha_hash, dados.senha):
        raise CredenciaisInvalidas()
    return usuario


def criar_ou_ligar_conta_google(db: Session, google_sub: str, email: str) -> Usuario:
    """Cria a conta (sem senha) ou liga o `google_sub` a uma conta e-mail+senha existente.

    "Ligar" (Ruling 42): uma conta já cadastrada por e-mail+senha com o mesmo e-mail verificado
    passa a aceitar login por Google também — é a mesma pessoa, nunca uma conta duplicada. Uma
    conta que já tem `google_sub` (de um login anterior) não é alterada.

    Args:
        db: sessão do request.
        google_sub: o `sub` do perfil OpenID do Google — identidade estável naquela conta Google.
        email: e-mail já verificado pelo Google (`email_verified=true`), normalizado.

    Returns:
        O `Usuario` (novo ou existente), já com `id`, `tenant` e `google_sub` preenchidos.
    """
    usuario = buscar_por_email(db, email)
    if usuario is not None:
        if usuario.google_sub is None:
            usuario.google_sub = google_sub
            db.flush()
        return usuario
    tenant = Tenant(tipo="pf", nome=email)
    usuario = Usuario(email=email, senha_hash=None, google_sub=google_sub, tenant=tenant)
    db.add(usuario)
    db.flush()
    return usuario

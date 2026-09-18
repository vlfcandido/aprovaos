"""Repositório de conta: cadastro (tenant PF + usuário) e autenticação por e-mail+senha.

O que é: `buscar_por_email`, `criar_conta` e `autenticar` sobre uma `Session`. Quando ler: ao
escrever a rota de cadastro/login ou ao mudar as regras do modelo de dados §2. As funções
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
        CredenciaisInvalidas: e-mail inexistente, conta excluída ou senha errada — sem
            distinguir o motivo, para não enumerar contas.
    """
    usuario = buscar_por_email(db, dados.email)
    if usuario is None or not verificar(usuario.senha_hash, dados.senha):
        raise CredenciaisInvalidas()
    return usuario

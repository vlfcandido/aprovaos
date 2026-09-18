# O que é: ambiente de execução das migrações Alembic — liga `Base.metadata` à URL do banco.
# Quando ler: ao gerar migração (`revision --autogenerate`) ou quando `upgrade head` falhar.
"""Ambiente do Alembic: sem engine em import; a URL vem de `-x`/ini ou de `DATABASE_URL`.

O Alembic executa este arquivo como script ao rodar um comando; ele não faz parte do pacote
`aprovaos` e nunca é importado pela aplicação.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

import aprovaos.dados.modelos  # noqa: F401  (registra as tabelas em Base.metadata)
from alembic import context
from aprovaos.config import obter_configuracoes
from aprovaos.dados.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def obter_url() -> str:
    """URL do banco: `sqlalchemy.url` do ini/`set_main_option`, senão `DATABASE_URL`."""
    return config.get_main_option("sqlalchemy.url") or obter_configuracoes().database_url


def run_migrations_offline() -> None:
    """Gera o SQL das migrações sem conectar (modo offline do Alembic)."""
    context.configure(
        url=obter_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrações conectando ao banco (modo online do Alembic)."""
    connectable = create_engine(obter_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

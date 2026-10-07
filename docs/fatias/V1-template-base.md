# Fatia V1 — Template base: plano de implementação
> O que é: o plano passo a passo (micro-TDD red→green→refactor) da fatia V1 do piloto v0 — esqueleto `backend/` com `uv`, modelo de dados base, conta por e-mail+senha com sessão em cookie, landing mínima, Compose, CI. Quando ler: antes de escrever a primeira linha da V1 e a cada passo, para saber qual teste escrever primeiro; ao revisar o PR da V1, para conferir o critério de pronto.

Fontes de decisão: `CLAUDE.md` (regras 1–12), `docs/03-arquitetura.md` §2/§7/§9/§10, `docs/04-modelo-de-dados.md` §1/§2/§4/§6, ADR-0017, 0019, 0020, 0024, 0026, 0030, 0031, PRD §6 (linha V1).

## 1. Objetivo

Entregar, rodando na máquina do dono, um serviço FastAPI em Python 3.13 onde uma pessoa cria conta por e-mail+senha, entra, vê `/conta` e sai — com modelo de dados base migrado por Alembic, Postgres+pgvector no Compose, testes em SQLite sem Docker, e CI que prova zero efeito colateral em import.

## 2. Premissas (decisões tomadas por este plano; qualquer uma pode ser vetada pelo dono)

| # | premissa | por quê |
|---|---|---|
| A | **Assinatura do cookie com `hmac` da stdlib** (HMAC-SHA256 com `chave_secreta`), sem `itsdangerous`. Valor do cookie = `<token>.<assinatura_hex>`; no banco fica só `sha256(token)`. | A lista de dependências da V1 não inclui `itsdangerous`; `hmac.compare_digest` é suficiente e oficial (https://docs.python.org/3.13/library/hmac.html). A assinatura evita consulta ao banco para cookie forjado; o segredo real é o token aleatório (`secrets.token_urlsafe(32)`, https://docs.python.org/3.13/library/secrets.html). Registrar como adendo de uma linha na ADR-0026 no passo 18. |
| B | **Chaves `uuid4`**, não v7. | `uuid.uuid7` só existe no Python 3.14; o projeto pina 3.13 (ADR-0017). O modelo de dados diz "v7 quando disponível". Trocar o `default` é uma linha quando migrar. |
| C | **`python-multipart` e `psycopg[binary]` entram nas dependências** mesmo não citados no escopo. | FastAPI exige `python-multipart` para `Form()` (https://fastapi.tiangolo.com/tutorial/request-forms/); o Compose precisa de driver Postgres (`postgresql+psycopg`, https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg). `email-validator` entra por causa de `EmailStr` (https://docs.pydantic.dev/latest/api/networks/#pydantic.networks.EmailStr). |
| D | **`usuario` nasce só com as colunas que a V1 usa** (`google_sub`, `consentimento_dados_rotina` ficam para as fatias 1b e 7, cada uma com sua migração). | YAGNI; migrações aditivas são baratas e "uma por fatia" (modelo §6). |
| E | **`traco` nasce como tabela vazia** — sem exporter OTel nem escrita em V1. | §9 e ADR-0024 precisam da tabela; a instrumentação só faz sentido quando houver agente (V2/V3). |
| F | **Formato de erro JSON `{codigo, mensagem, acao}` vale para qualquer resposta de erro que não seja um formulário HTML**: `HTTPException`, `RequestValidationError` e exceção não tratada. Erros esperados de formulário (e-mail repetido, senha errada) são re-renderizados no HTML com mensagem, status 200. | Arquitetura §7; V1 não tem rota `/api/*` ainda. Um 404 de página em JSON é aceitável na V1 (piloto n=1). |
| G | **Timestamps sempre UTC e sempre *aware*** via `TypeDecorator` `DataHoraUtc` (SQLite devolve `datetime` naive; sem isso `expira_em < agora` levanta `TypeError`). | https://docs.sqlalchemy.org/en/20/core/custom_types.html#augmenting-existing-types |
| H | **Formulários com HTMX via `hx-post` + `hx-select` + `HX-Redirect`**; o servidor sempre devolve a página inteira (sem parciais) e, no sucesso, `HX-Redirect` quando o cabeçalho `HX-Request: true` estiver presente, senão `303`. Funciona sem JS. | https://htmx.org/attributes/hx-select/ e https://htmx.org/reference/#response_headers ; zero template parcial = menos arquivos. |
| I | **Mensagem "já existe conta com este e-mail" no cadastro** (enumera e-mails). | Piloto n=1; endurecer quando abrir ao público (fatia 12/13). Anotar em PENDENCIAS. |
| J | Landing e páginas usam as fontes do protótipo (Sora, IBM Plex) **só se já estiverem locais**; senão, `system-ui`. Sem CDN. | ADR-0019 e "sem SEO" — a tipografia definitiva é da Fase 6. |

## 3. Fora da V1 (rastreado; não implementar)

Google OAuth (fatia 1b, ADR-0026) · billing (fatia 12) · SEO/landing programática (fatia 13) · **verificação de e-mail** (adiada — nova pendência P-21 no passo 18 — P-20 já existe) · VPS/Caddy/deploy/GitHub Actions por SSH (fatia 8, ADR-0030) · radar de editais (1b) · exporter OTel para `traco` (V2/V3) · `CREATE EXTENSION vector` e coluna vetorial (V3) · serviço `jobs` no Compose (fatia 8) · PWA/`manifest.json`/`sw.js` (fatias 6–10) · anonimização LGPD em 30 dias (`excluido_em` existe; o job é da fatia 12) · repositório remoto (P-19, dono).

## 4. Estrutura final de arquivos (o que existe ao fim da V1)

```
backend/
  .python-version                  # "3.13"
  pyproject.toml                   # deps, ruff, mypy, pytest (markers)
  uv.lock
  alembic.ini
  alembic/env.py · alembic/script.py.mako · alembic/versions/0001_base.py
  Dockerfile
  aprovaos/__init__.py
  aprovaos/config.py               # Configuracoes + obter_configuracoes()
  aprovaos/main.py                 # criar_app()
  aprovaos/dominio/__init__.py · erros.py · senha.py · conta.py
  aprovaos/dados/__init__.py · base.py · modelos.py · conexao.py · repositorio_conta.py · repositorio_sessao.py
  aprovaos/api/__init__.py · erros.py · db.py · sessao.py · saude.py · inicio.py · conta.py
  tests/conftest.py · test_pacote.py · test_config.py · test_modelos.py · test_conexao.py
        · test_import_sem_efeito_colateral.py · test_migracoes.py · test_saude.py · test_erros.py
        · test_inicio.py · test_senha.py · test_dominio_conta.py · test_repositorio_conta.py
        · test_sessao.py · test_rota_cadastro.py · test_rota_entrar.py · test_rota_conta.py
        · test_env_example.py · test_postgres.py
web/
  templates/base.html · inicio.html · conta/cadastro.html · conta/entrar.html · conta/conta.html
  static/css/tokens.css · static/css/base.css
  static/js/htmx.min.js            # vendorizado, com LICENSE ao lado
scripts/checar.sh · scripts/checar_import.py
compose.yaml · .env.example
.github/workflows/ci.yml
```

Todo arquivo `.py`, `.html`, `.css`, `.sh`, `.yaml` começa com o cabeçalho de 2 linhas do projeto (comentário na sintaxe do arquivo): "O que é: … Quando ler: …" (CLAUDE.md regra 5).

## 5. Convenções transversais (valem em todos os passos)

- **Red primeiro**: escreva o teste, rode `uv run pytest tests/<arquivo> -x`, veja falhar pelo motivo esperado (import inexistente, assert), só então implemente o mínimo. Depois: refactor com testes verdes, `uv run ruff check --fix`, `uv run ruff format`, `uv run mypy`.
- **pt-BR** em nomes, docstrings (Google style, checadas pelo ruff regra `D`), mensagens de UI e commits.
- **Sem I/O em import**: nada de `create_engine`, `Configuracoes()`, leitura de `.env`, `Path.read_text` em nível de módulo. Objetos puros (`PasswordHasher()`, `APIRouter()`, `Jinja2Templates` **não** — este lê disco; criar dentro de `criar_app`).
- **Pydantic em toda fronteira**: formulários (`DadosCadastro`, `DadosLogin`), erro JSON (`ErroApi`), configuração (`Configuracoes`). Modelos ORM nunca saem de `dados/` para o template sem passar por um objeto simples (na V1, o template recebe `usuario.email` como `str`).
- **Transação**: funções de repositório fazem `db.add()`/`db.flush()`; **a rota** faz `db.commit()`. Uma regra só.
- **Fixtures** (definidas no passo 7): `config_teste`, `engine` (SQLite em memória, `StaticPool`), `app`, `cliente` (`TestClient`), `db` (`Session` ligada ao mesmo engine). Rotas testadas com `follow_redirects=False`.
- Docs oficiais citadas no passo em que a API é fixada. Se uma API não estiver nas docs citadas, pare e pergunte.

## 6. Passos

### Passo 1 — Esqueleto `backend/` com `uv`
**Objetivo:** projeto instalável, Python 3.13 pinado, ferramentas configuradas.
**Arquivos:** `backend/.python-version`, `backend/pyproject.toml`, `backend/aprovaos/__init__.py`, `backend/aprovaos/{dominio,dados,api}/__init__.py`, `backend/tests/__init__.py`, `backend/tests/test_pacote.py`.
**Teste red:** `tests/test_pacote.py::test_pacote_importa` — `importlib.import_module("aprovaos")` retorna módulo cujo `__doc__` começa com `"AprovaOS"`. Falha: `ModuleNotFoundError`.
**Implementação mínima:**
- `.python-version` = `3.13` (uv lê o arquivo: https://docs.astral.sh/uv/concepts/python-versions/#python-version-files).
- `pyproject.toml`: `[project] name="aprovaos" requires-python=">=3.13,<3.14"`, `dependencies = [fastapi, uvicorn[standard], sqlalchemy>=2.0,<3, alembic, pydantic>=2, pydantic-settings, email-validator, jinja2, python-multipart, argon2-cffi, psycopg[binary]]`; `[dependency-groups] dev = [pytest, httpx, ruff, mypy]` (PEP 735, https://docs.astral.sh/uv/concepts/projects/dependencies/#development-dependencies); `[build-system]` hatchling com `packages = ["aprovaos"]`. Versões: a última estável no PyPI na data; o `uv.lock` é a fonte da verdade.
- `[tool.ruff]` `line-length = 100`, `[tool.ruff.lint] select = ["E","F","I","UP","B","D"]`, `[tool.ruff.lint.pydocstyle] convention = "google"`, `per-file-ignores = {"tests/*" = ["D"], "alembic/*" = ["D"]}` (https://docs.astral.sh/ruff/rules/#pydocstyle-d).
- `[tool.mypy]` `strict = true`, `files = ["aprovaos","tests","scripts"]`, `plugins = ["pydantic.mypy"]` (https://docs.pydantic.dev/latest/integrations/mypy/).
- `[tool.pytest.ini_options]` `testpaths = ["tests"]`, `markers = ["postgres: exige DATABASE_URL_TEST apontando para um Postgres"]` (https://docs.pytest.org/en/stable/how-to/mark.html#registering-marks).
- `aprovaos/__init__.py` só com docstring `"""AprovaOS — …"""`.
**Pronto quando:** `cd backend && uv sync && uv run pytest` verde; `uv run ruff check .` e `uv run mypy` sem erro; `uv.lock` commitado.

### Passo 2 — `config.py`: configurações por fábrica
**Objetivo:** ler `.env`/ambiente só quando alguém chamar `obter_configuracoes()`.
**Arquivos:** `aprovaos/config.py`, `tests/test_config.py`.
**Testes red:**
- `test_configuracoes_aceita_valores_explicitos`: `Configuracoes(database_url="sqlite://", chave_secreta="x"*32, _env_file=None)` → `ambiente == "dev"`, `cookie_seguro is True`, `sessao_dias == 30`, `web_dir is None`.
- `test_configuracoes_le_variaveis_de_ambiente`: `monkeypatch.setenv("DATABASE_URL", "sqlite://")`, `setenv("CHAVE_SECRETA", …)` → `Configuracoes(_env_file=None).database_url == "sqlite://"`.
- `test_configuracoes_exige_obrigatorias`: sem env e `_env_file=None` → `pydantic.ValidationError`.
- `test_obter_configuracoes_e_cacheada`: `obter_configuracoes() is obter_configuracoes()`; `obter_configuracoes.cache_clear()` existe (use `monkeypatch` para env e chame `cache_clear()` no fim).
- `test_chave_secreta_nao_vaza_em_repr`: `chave_secreta` é `SecretStr`; `repr(cfg)` não contém o valor.
**Implementação mínima:** `class Configuracoes(BaseSettings)` com `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`; campos `database_url: str`, `chave_secreta: SecretStr`, `ambiente: Literal["dev","teste","prod"] = "dev"`, `cookie_seguro: bool = True`, `sessao_dias: int = 30`, `web_dir: Path | None = None`. `@lru_cache def obter_configuracoes() -> Configuracoes: return Configuracoes()`. Docs: pydantic-settings (`env_file`, prioridade init > env > dotenv; leitura só na instanciação) https://docs.pydantic.dev/latest/concepts/pydantic_settings/ ; padrão `lru_cache` do FastAPI https://fastapi.tiangolo.com/advanced/settings/#creating-the-settings-only-once-with-lru_cache .
**Pronto quando:** testes verdes; `grep -n "Configuracoes()" aprovaos/` só aparece dentro de `obter_configuracoes`.

### Passo 3 — Modelos ORM base: `tenant`, `usuario`, `sessao`, `traco`
**Objetivo:** mapeamento SQLAlchemy 2.0 das 4 tabelas, sem sessão nem engine.
**Arquivos:** `aprovaos/dados/base.py` (`Base`, `DataHoraUtc`, mixins), `aprovaos/dados/modelos.py`, `tests/test_modelos.py`.
**Testes red** (engine local no teste: `create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)` + `Base.metadata.create_all`):
- `test_tabelas_da_v1`: `set(Base.metadata.tables) == {"tenant","usuario","sessao","traco"}`.
- `test_colunas_padrao`: `Tenant`, `Usuario`, `Sessao` têm `id`, `criado_em`, `atualizado_em`; `Traco` tem `id`, `criado_em`.
- `test_insere_tenant_usuario_sessao`: cria `Tenant(tipo="pf", nome="Ana")`, `Usuario(email=…, senha_hash="h", tenant=…)`, `Sessao(usuario=…, token_hash="a"*64, expira_em=aware)`; após `commit`, `usuario.id` é `uuid.UUID`, `criado_em.tzinfo is not None`.
- `test_email_unico`: segundo `Usuario` com o mesmo e-mail → `sqlalchemy.exc.IntegrityError`.
- `test_tipo_do_tenant_restrito`: `Tenant(tipo="xx")` → `IntegrityError` (CHECK).
- `test_datahora_volta_aware_do_sqlite`: `sessao.expira_em` lido de volta é aware e igual ao gravado (em UTC).
- `test_traco_colunas_minimas`: colunas `iniciado_em, duracao_ms, usuario_id, agente, modelo, tokens_in, tokens_out, custo_brl, tier, resultado, erro, span_pai_id` existem.
**Implementação mínima:**
- `base.py`: `class Base(DeclarativeBase)` com `metadata = MetaData(naming_convention={...})` (convenção de nomes obrigatória para Alembic/SQLite: https://alembic.sqlalchemy.org/en/latest/naming.html); `class DataHoraUtc(TypeDecorator[datetime])` com `impl = DateTime(timezone=True)`, `cache_ok = True`, `process_bind_param` converte para UTC, `process_result_value` põe `tzinfo=UTC` se vier naive; mixin `ChaveUuid` (`id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)`; tipo genérico https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Uuid) e mixin `Carimbos` (`criado_em`, `atualizado_em` com `default`/`onupdate` = função `agora_utc()`).
- `modelos.py`: `Tenant(tipo: String(8) + CheckConstraint("tipo IN ('pf','org')"), nome: String(120))`; `Usuario(tenant_id FK index, email String(254) unique, senha_hash String(255), excluido_em DataHoraUtc | None)`; `Sessao(usuario_id FK index, token_hash String(64) unique, expira_em, revogada_em | None)`; `Traco(iniciado_em, duracao_ms int, usuario_id FK | None, agente String(64), modelo String(64) | None, tokens_in/out int | None, custo_brl Numeric(12,6) | None, tier String(8) | None, resultado String(16), erro Text | None, span_pai_id FK traco.id | None)`. `relationship()` só `Usuario.tenant` e `Sessao.usuario`. Padrão do modelo §6 e https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html .
**Pronto quando:** testes verdes; `mypy` sem `Any` nos modelos; nenhum `create_engine` fora do teste.

### Passo 4 — `dados/conexao.py`: engine e fábrica de sessão
**Objetivo:** único lugar que cria `Engine` e `sessionmaker`, sempre por chamada explícita.
**Arquivos:** `aprovaos/dados/conexao.py`, `tests/test_conexao.py`.
**Testes red:** `test_criar_engine_nao_conecta` — `criar_engine("sqlite:///" + str(tmp_path/"x.db"))` retorna `Engine` e o arquivo **não** existe ainda (engine é lazy); `test_fabrica_sessao_liga_ao_engine` — `criar_fabrica_sessao(engine)()` é `Session` com `.get_bind() is engine`.
**Implementação mínima:** `criar_engine(url: str) -> Engine` = `create_engine(url, pool_pre_ping=True)`; `criar_fabrica_sessao(engine) -> sessionmaker[Session]` = `sessionmaker(bind=engine, expire_on_commit=False)`. Docs: https://docs.sqlalchemy.org/en/20/orm/session_basics.html#using-a-sessionmaker .
**Pronto quando:** verde; `mypy` OK.

### Passo 5 — Prova de zero efeito colateral em import
**Objetivo:** um script que importa todos os submódulos de `aprovaos` com rede bloqueada, sem `.env`, sem variáveis, e com `sqlalchemy.create_engine` sabotado — e falha se qualquer módulo tentar algo disso.
**Arquivos:** `scripts/checar_import.py` (raiz do repo), `tests/test_import_sem_efeito_colateral.py`.
**Teste red:** `test_script_de_import_passa` — `subprocess.run([sys.executable, caminho_do_script], cwd=tmp_path, env={"PATH": …}, capture_output=True)` retorna `returncode == 0` e stdout contém `"importados:"`. Falha: script não existe. (Rodar em `tmp_path` garante que nenhum `.env` de dev seja lido.)
**Implementação mínima:** no script: (1) remove do `os.environ` toda chave que comece com `DATABASE_URL`, `CHAVE_SECRETA`, `AMBIENTE`; (2) `socket.socket.connect = _proibido` (levanta `RuntimeError("rede em import")`); (3) `import sqlalchemy; sqlalchemy.create_engine = _proibido`; (4) `import aprovaos`; `for m in pkgutil.walk_packages(aprovaos.__path__, "aprovaos."): importlib.import_module(m.name)` (https://docs.python.org/3.13/library/pkgutil.html#pkgutil.walk_packages); (5) imprime `importados: N` e sai com 0; qualquer exceção → traceback e `sys.exit(1)`. Tipado, com docstring de módulo e `if __name__ == "__main__": main()`.
**Pronto quando:** `uv run --project backend python scripts/checar_import.py` imprime `importados: N` (N ≥ 8 ao fim da V1). A partir daqui, **todo passo roda este teste**.

### Passo 6 — Alembic: migração inicial `0001_base`
**Objetivo:** `env.py` sem I/O em import; migração que reproduz exatamente `Base.metadata`.
**Arquivos:** `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/0001_base.py`, `tests/test_migracoes.py`.
**Teste red:** `test_migracao_inicial_bate_com_os_modelos` — `cfg = alembic.config.Config(str(backend/"alembic.ini"))`; `cfg.set_main_option("script_location", str(backend/"alembic"))`; `cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path}/m.db")`; `alembic.command.upgrade(cfg, "head")`; com `engine.connect()` → `compare_metadata(MigrationContext.configure(conn), Base.metadata) == []`. Segundo teste: `downgrade(cfg, "base")` deixa `inspect(engine).get_table_names() == ["alembic_version"]` ou `[]`. Docs: https://alembic.sqlalchemy.org/en/latest/api/commands.html ; https://alembic.sqlalchemy.org/en/latest/api/autogenerate.html#alembic.autogenerate.compare_metadata .
**Implementação mínima:** `alembic init alembic` dentro de `backend/`, depois: `alembic.ini` com `sqlalchemy.url =` vazio; `env.py`: `target_metadata = Base.metadata` (importar `aprovaos.dados.modelos` para registrar as tabelas); em `run_migrations_online()`: `url = config.get_main_option("sqlalchemy.url") or obter_configuracoes().database_url`, `engine_from_config`/`create_engine(url)`, `context.configure(connection=…, target_metadata=…, render_as_batch=True, compare_type=True)` (batch para SQLite: https://alembic.sqlalchemy.org/en/latest/batch.html). Offline mode pode ser mantido do template. Gerar a revisão com `uv run alembic -x … revision --autogenerate -m "base"` apontando `DATABASE_URL` para um SQLite temporário; **revisar o arquivo gerado** (nomes de constraint pela convenção do passo 3, `sa.Uuid()`, `sa.DateTime(timezone=True)`) e renomeá-lo para `0001_base.py` com `revision = "0001"`.
**Pronto quando:** os dois testes verdes; `checar_import.py` verde (env.py não é importado pelo pacote, mas `alembic/` não pode importar nada com efeito).

### Passo 7 — `criar_app()`, `/saude`, erros JSON e fixtures de teste
**Objetivo:** app por fábrica com engine injetável; healthcheck que toca o banco; erros no formato do produto.
**Arquivos:** `aprovaos/main.py`, `aprovaos/api/db.py`, `aprovaos/api/saude.py`, `aprovaos/api/erros.py`, `tests/conftest.py`, `tests/test_saude.py`, `tests/test_erros.py`.
**Fixtures (conftest):** `config_teste` = `Configuracoes(database_url="sqlite://", chave_secreta="t"*32, ambiente="teste", cookie_seguro=False, _env_file=None)`; `engine` = SQLite memória com `StaticPool` + `check_same_thread=False` (obrigatório porque o `TestClient` roda a app em outra thread: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#using-a-memory-database-in-multiple-threads) com `create_all`/`drop_all`; `app = criar_app(config_teste, engine=engine)`; `cliente = TestClient(app)` (https://fastapi.tiangolo.com/tutorial/testing/); `db` = sessão da mesma fábrica. Hook `pytest_collection_modifyitems` que adiciona `pytest.mark.skip(reason="defina DATABASE_URL_TEST")` aos testes `postgres` quando a variável não existe (https://docs.pytest.org/en/stable/example/simple.html#control-skipping-of-tests-according-to-command-line-option).
**Testes red:**
- `test_saude_ok`: `GET /saude` → 200, `{"status":"ok","banco":"ok"}`.
- `test_saude_sem_banco`: app criada com `criar_engine("sqlite:///" + str(tmp_path/"nao/existe/x.db"))` → 503 e corpo `{"codigo":"banco_indisponivel","mensagem":…,"acao":…}`.
- `test_404_em_json`: `GET /nao-existe` → 404 com as três chaves; `codigo == "nao_encontrado"`.
- `test_422_em_json`: registrar no `app` da fixture uma rota `POST /_teste` com corpo Pydantic e enviar `{}` → 422, `codigo == "dados_invalidos"`, `mensagem` cita o campo.
- `test_500_em_json`: rota `GET /_estoura` que levanta `RuntimeError` (usar `TestClient(app, raise_server_exceptions=False)`) → 500, `codigo == "erro_interno"`, sem traceback no corpo.
**Implementação mínima:**
- `api/erros.py`: `class ErroApi(BaseModel): codigo: str; mensagem: str; acao: str`; `registrar_tratadores(app)` com `@app.exception_handler(StarletteHTTPException)`, `(RequestValidationError)`, `(Exception)` devolvendo `JSONResponse(status, ErroApi(...).model_dump())` (https://fastapi.tiangolo.com/tutorial/handling-errors/#install-custom-exception-handlers). Mapa de `codigo` por status: 404→`nao_encontrado`, 401→`nao_autenticado`, 403→`proibido`, 422→`dados_invalidos`, 503→`banco_indisponivel`, demais→`erro_interno`.
- `api/db.py`: `def obter_db(request: Request) -> Iterator[Session]: with request.app.state.fabrica_sessao() as db: yield db` (https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/).
- `api/saude.py`: `APIRouter`; `GET /saude` executa `db.execute(text("SELECT 1"))`; em `OperationalError` levanta `HTTPException(503, "banco indisponível")`.
- `main.py`: `def criar_app(config: Configuracoes | None = None, engine: Engine | None = None) -> FastAPI` — resolve `config = config or obter_configuracoes()`, `engine = engine or criar_engine(config.database_url)`, guarda `app.state.config`, `app.state.fabrica_sessao`, inclui routers, registra tratadores. `uvicorn aprovaos.main:criar_app --factory` (https://www.uvicorn.org/settings/#application-interface).
**Pronto quando:** testes verdes; `checar_import.py` verde.

### Passo 8 — Templates, tokens CSS, HTMX e landing `/`
**Objetivo:** base Jinja com tema claro/escuro por tokens, largura de celular, HTMX vendorizado; landing com nome, frase e botão.
**Arquivos:** `web/templates/base.html`, `web/templates/inicio.html`, `web/static/css/tokens.css`, `web/static/css/base.css`, `web/static/js/htmx.min.js` (+ `LICENSE-htmx.txt`), `aprovaos/api/templates.py`, `aprovaos/api/inicio.py`, `tests/test_inicio.py`.
**Testes red:**
- `test_landing`: `GET /` → 200, `content-type` começa com `text/html`; corpo contém `AprovaOS`, `href="/cadastro"`, `<html lang="pt-BR"`, `name="viewport"`, `color-scheme`.
- `test_estaticos`: `GET /static/css/tokens.css` → 200; `GET /static/js/htmx.min.js` → 200.
- `test_tokens_sem_cor_literal_fora_de_tokens`: `base.css` não contém `#[0-9a-fA-F]{3,6}` nem `rgb(` (regex) — toda cor vem de `var(--…)`.
**Implementação mínima:**
- `api/templates.py`: `criar_templates(web_dir: Path) -> Jinja2Templates` (`Jinja2Templates(directory=web_dir/"templates")`, https://fastapi.tiangolo.com/advanced/templates/); `renderizar(request, nome, contexto)` chama `request.app.state.templates.TemplateResponse(request=request, name=nome, context=contexto)` (assinatura com `request` primeiro, FastAPI ≥ 0.108).
- `main.py`: resolve `web_dir = config.web_dir or Path(__file__).resolve().parents[2] / "web"` **dentro** de `criar_app`; `app.mount("/static", StaticFiles(directory=web_dir/"static"), name="static")`; `app.state.templates = criar_templates(web_dir)`.
- `tokens.css`: paleta completa em `:root` (claro), redefinida em `@media (prefers-color-scheme: dark)` e em `[data-theme="escuro"]`; `color-scheme: light dark`; tokens de espaço, raio, tipografia. `base.css`: reset mínimo, `max-width: 28rem; margin-inline: auto` (largura de celular), botão, campo, mensagem de erro, `@media (prefers-reduced-motion: no-preference)` para a única transição. Sem cor literal fora de `tokens.css` (ADR-0019; aprendizados dos mockups §3).
- `base.html`: `<!doctype html><html lang="pt-BR">`, `viewport`, links para os dois CSS, `<script src="/static/js/htmx.min.js" defer>`, blocos `titulo` e `conteudo`, `<nav>` (ganha estado de login no passo 14).
- `inicio.html`: `h1` "AprovaOS", uma frase, `<a class="botao" href="/cadastro">Criar conta</a>`, link "Entrar".
- `htmx.min.js`: baixar a 2.x de https://htmx.org/docs/#installing (arquivo em `unpkg.com/htmx.org@2.x/dist/htmx.min.js`) e guardar a licença (Zero-Clause BSD) ao lado. Registrar versão no cabeçalho do arquivo.
**Pronto quando:** testes verdes; abrir `http://localhost:8000/` no celular ou no modo responsivo mostra a landing nos dois temas.

### Passo 9 — Domínio: senha (argon2) e esquemas de conta
**Objetivo:** hash/verificação de senha e validação Pydantic dos formulários, sem I/O.
**Arquivos:** `aprovaos/dominio/senha.py`, `aprovaos/dominio/conta.py`, `aprovaos/dominio/erros.py`, `tests/test_senha.py`, `tests/test_dominio_conta.py`.
**Testes red:**
- `test_gerar_hash_e_argon2id`: `gerar_hash("segredo123")` começa com `$argon2id$` e difere da senha.
- `test_dois_hashes_diferem`: sal aleatório → `gerar_hash(s) != gerar_hash(s)`.
- `test_verificar`: `verificar(hash, "segredo123") is True`; `verificar(hash, "outra") is False`; `verificar("lixo", "x") is False` (hash inválido não estoura).
- `test_dados_cadastro_normaliza_email`: `DadosCadastro(email="Ana@Exemplo.com", senha="12345678")` → `email == "linda@exemplo.com"`.
- `test_dados_cadastro_rejeita`: senha com 7 chars → `ValidationError`; e-mail sem `@` → `ValidationError`.
- `test_dados_login`: mesmos campos, sem regra de tamanho mínimo além de `min_length=1`.
- `test_erros_de_dominio`: `EmailJaCadastrado` e `CredenciaisInvalidas` são `ErroDominio` (subclasse de `Exception`).
**Implementação mínima:** `senha.py`: `_HASHER = PasswordHasher()` (objeto puro; sem I/O); `gerar_hash(senha: str) -> str = _HASHER.hash(senha)`; `verificar(hash, senha) -> bool` com `try: return _HASHER.verify(hash, senha) except VerificationError: return False` — `VerifyMismatchError` e hashes malformados são subclasses de `VerificationError` (https://argon2-cffi.readthedocs.io/en/stable/api.html). `conta.py`: `DadosCadastro(BaseModel)` com `email: EmailStr`, `senha: str = Field(min_length=8, max_length=128)` e `@field_validator("email", mode="after")` que faz `.lower()`; `DadosLogin` idem com `min_length=1`. `erros.py`: as três classes com docstring.
**Pronto quando:** verde; `mypy` OK.

### Passo 10 — Repositório de conta: cadastro cria tenant PF + usuário
**Objetivo:** persistir a conta com as regras do modelo §2.
**Arquivos:** `aprovaos/dados/repositorio_conta.py`, `tests/test_repositorio_conta.py`.
**Testes red** (fixture `db`):
- `test_criar_conta_cria_tenant_pf`: `usuario = criar_conta(db, DadosCadastro(...))` → `usuario.tenant.tipo == "pf"`, `usuario.tenant.nome == email`, `usuario.senha_hash` começa com `$argon2id$`, `usuario.email` minúsculo.
- `test_criar_conta_email_repetido`: segunda chamada com o mesmo e-mail → `EmailJaCadastrado` (checar **antes** de inserir, por consulta; a `UNIQUE` é a rede de segurança).
- `test_autenticar`: `autenticar(db, DadosLogin(email, senha))` devolve o `Usuario`; senha errada → `CredenciaisInvalidas`; e-mail inexistente → `CredenciaisInvalidas` (mesma exceção, sem distinguir); usuário com `excluido_em` preenchido → `CredenciaisInvalidas`.
**Implementação mínima:** `buscar_por_email(db, email) -> Usuario | None` (`select(Usuario).where(Usuario.email == email, Usuario.excluido_em.is_(None))`, https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html); `criar_conta(db, dados) -> Usuario` (`Tenant(tipo="pf", nome=dados.email)` + `Usuario(senha_hash=gerar_hash(dados.senha))`, `db.add`, `db.flush`); `autenticar(db, dados) -> Usuario`. Docstrings explicam que a rota faz o `commit`.
**Pronto quando:** verde.

### Passo 11 — Sessão de login: token, assinatura, cookie e dependência `usuario_atual`
**Objetivo:** sessão server-side em `sessao` (ADR-0026), cookie assinado `HttpOnly/Secure/SameSite=Lax`.
**Arquivos:** `aprovaos/dados/repositorio_sessao.py`, `aprovaos/api/sessao.py`, `tests/test_sessao.py`.
**Testes red:**
- `test_assinar_e_verificar`: `verificar_assinatura(assinar("tok", chave), chave) == "tok"`; valor adulterado (`"tok.deadbeef"`), sem ponto, ou chave diferente → `None`.
- `test_abrir_sessao_grava_hash_e_nao_o_token`: `token = abrir_sessao(db, usuario, dias=30, agora=…)`; a linha em `sessao` tem `token_hash == sha256(token).hexdigest()` e `expira_em == agora + 30 dias`.
- `test_usuario_da_sessao`: token válido → `Usuario`; expirado (`agora` depois de `expira_em`) → `None`; revogado → `None`; token desconhecido → `None`.
- `test_revogar_sessao`: `revogar_sessao(db, token, agora)` preenche `revogada_em`; idempotente.
- `test_cookie_de_sessao`: `definir_cookie(resposta, "valor", config_com_seguro=True, dias=30)` → `set-cookie` contém `sessao=valor`, `HttpOnly`, `Secure`, `SameSite=lax`, `Path=/`, `Max-Age=2592000`; com `cookie_seguro=False` não contém `Secure`. `limpar_cookie` produz `Max-Age=0`.
- `test_usuario_atual_sem_cookie`: `usuario_atual(request_sem_cookie, db, config)` → `None`.
**Implementação mínima:** `repositorio_sessao.py`: `abrir_sessao(db, usuario, dias, agora) -> str` (`secrets.token_urlsafe(32)`, grava `hashlib.sha256`), `usuario_da_sessao(db, token, agora) -> Usuario | None`, `revogar_sessao(db, token, agora) -> None`. `api/sessao.py`: `NOME_COOKIE = "sessao"`; `assinar(token, chave: str) -> str` e `verificar_assinatura(valor, chave) -> str | None` com `hmac.new(chave.encode(), token.encode(), hashlib.sha256).hexdigest()` e `hmac.compare_digest`; `definir_cookie(resposta: Response, valor, config)` = `resposta.set_cookie(NOME_COOKIE, valor, max_age=dias*86400, httponly=True, secure=config.cookie_seguro, samesite="lax", path="/")` (https://www.starlette.io/responses/#set-cookie); `limpar_cookie(resposta)` = `delete_cookie` com os mesmos atributos; dependência `usuario_atual(request, db=Depends(obter_db)) -> Usuario | None` (lê `request.cookies.get(NOME_COOKIE)`, verifica assinatura com `request.app.state.config.chave_secreta.get_secret_value()`, consulta o repositório com `agora_utc()`); `exigir_usuario(usuario=Depends(usuario_atual)) -> Usuario` levanta `RedirecionarParaEntrar` — exceção própria tratada em `registrar_tratadores` como `RedirectResponse("/entrar", 303)` (FastAPI: handlers para exceções próprias, mesma doc do passo 7).
**Pronto quando:** verde; `mypy` OK.

### Passo 12 — Rotas `/cadastro` (GET/POST)
**Objetivo:** formulário de cadastro que cria a conta, abre sessão e redireciona para `/conta`.
**Arquivos:** `aprovaos/api/conta.py`, `web/templates/conta/cadastro.html`, `tests/test_rota_cadastro.py`.
**Testes red:**
- `test_get_cadastro`: 200, HTML contém `<form` com `method="post"`, campos `name="email"` e `name="senha"` (`type="password"`, `autocomplete="new-password"`), `hx-post="/cadastro"`, `hx-select="#form-cadastro"`, `hx-target="#form-cadastro"`.
- `test_post_cadastro_cria_e_entra`: `POST /cadastro` (form) → 303, `Location == "/conta"`, `set-cookie` com `sessao=` + `HttpOnly` + `SameSite=lax`; no `db` existe `Usuario` com o e-mail e um `Tenant` `pf`.
- `test_post_cadastro_htmx`: mesmo POST com cabeçalho `HX-Request: true` → 200 e `HX-Redirect: /conta` (https://htmx.org/reference/#request_headers e `#response_headers`).
- `test_post_cadastro_email_repetido`: 200, HTML contém "Já existe conta com este e-mail" e link para `/entrar`; nenhum cookie.
- `test_post_cadastro_senha_curta`: 200, HTML contém "no mínimo 8"; nenhum usuário criado.
- `test_post_cadastro_email_invalido`: 200, mensagem de e-mail inválido.
- `test_cookie_secure_quando_configurado`: app criada com `config_teste.model_copy(update={"cookie_seguro": True})` → `set-cookie` contém `Secure` (não seguir para `/conta` neste teste: o `TestClient` usa `http://testserver` e não reenvia cookie `Secure`).
**Implementação mínima:** `api/conta.py` com `APIRouter`; `GET /cadastro` renderiza; `POST /cadastro` lê `email: Annotated[str, Form()]`, `senha: Annotated[str, Form()]` (https://fastapi.tiangolo.com/tutorial/request-forms/), monta `DadosCadastro` num `try` e converte `ValidationError` em lista de mensagens pt-BR por campo (uma função `mensagens_de_validacao(erro) -> list[str]` em `api/erros.py`); em `EmailJaCadastrado` re-renderiza com a mensagem; sucesso: `criar_conta` → `db.commit()` → `abrir_sessao` → `db.commit()` → `responder_redirecionamento(request, "/conta")` (helper em `api/sessao.py` ou `api/templates.py`: `HX-Redirect` se `request.headers.get("HX-Request") == "true"`, senão `RedirectResponse(status_code=303)`) + `definir_cookie(resposta, assinar(token, chave), config)`.
**Pronto quando:** verde; fluxo manual no navegador cria conta e cai em `/conta` (que ainda dá 404 JSON até o passo 14 — aceitável).

### Passo 13 — Rotas `/entrar` (GET/POST)
**Objetivo:** login com mensagem genérica em falha.
**Arquivos:** `aprovaos/api/conta.py`, `web/templates/conta/entrar.html`, `tests/test_rota_entrar.py`.
**Testes red:**
- `test_get_entrar`: 200, form com `email`, `senha` (`autocomplete="current-password"`), `hx-post="/entrar"`.
- `test_post_entrar_ok`: cria conta pelo repositório na fixture; `POST /entrar` correto → 303 para `/conta` + cookie; `HX-Request` → 200 + `HX-Redirect`.
- `test_post_entrar_senha_errada` e `test_post_entrar_email_inexistente`: ambos 200 com o **mesmo** texto "E-mail ou senha inválidos" e sem cookie.
- `test_cada_login_abre_sessao_nova`: dois logins → duas linhas em `sessao` para o usuário.
**Implementação mínima:** `POST /entrar` → `DadosLogin` → `autenticar` → `abrir_sessao` → `db.commit()` → redirecionamento + cookie; `CredenciaisInvalidas` e `ValidationError` caem na mesma mensagem genérica.
**Pronto quando:** verde.

### Passo 14 — `/conta`, `/sair` e navegação com estado de login
**Objetivo:** página protegida mínima e logout que revoga a sessão.
**Arquivos:** `aprovaos/api/conta.py`, `web/templates/conta/conta.html`, `web/templates/base.html`, `tests/test_rota_conta.py`.
**Testes red:**
- `test_conta_sem_login_redireciona`: `GET /conta` → 303, `Location == "/entrar"`.
- `test_conta_logado`: após `POST /entrar` (o `TestClient` guarda o cookie), `GET /conta` → 200 com o e-mail e um `<form method="post" action="/sair">` com botão "Sair".
- `test_sair_revoga_e_limpa`: `POST /sair` → 303 para `/`, `set-cookie` com `Max-Age=0`; a linha em `sessao` tem `revogada_em`; `GET /conta` com o cookie antigo (reenviado manualmente via `cookies={...}`) → 303 para `/entrar`.
- `test_nav_reflete_login`: `GET /` sem login contém "Entrar" e "Criar conta"; logado contém "Minha conta" e não contém "Criar conta".
- `test_cookie_adulterado_e_ignorado`: `GET /conta` com `cookies={"sessao": "abc.def"}` → 303 (nunca 500).
**Implementação mínima:** `GET /conta` com `Depends(exigir_usuario)` renderiza `conta.html` recebendo `{"email": usuario.email}`; `POST /sair` lê o cookie, `revogar_sessao` (se houver), `db.commit()`, `RedirectResponse("/", 303)` + `limpar_cookie`. `base.html`: `nav` usa `usuario_email` do contexto (`None` = deslogado); todas as rotas HTML passam `usuario_email` via `Depends(usuario_atual)` — para não repetir, `renderizar()` aceita `usuario: Usuario | None` e injeta `usuario_email` no contexto.
**Pronto quando:** verde; no navegador: cadastrar → conta → sair → `/conta` volta para `/entrar`.

### Passo 15 — `.env.example`, `compose.yaml`, `Dockerfile`
**Objetivo:** subir Postgres+pgvector e o serviço `web` com um comando; variáveis documentadas.
**Arquivos:** `.env.example` (raiz), `compose.yaml` (raiz), `backend/Dockerfile`, `tests/test_env_example.py`.
**Teste red:** `test_env_example_cobre_todas_as_configuracoes` — lê `.env.example`, extrai as chaves (`linha.split("=")[0]` das linhas não vazias e sem `#`) e afirma `set(chaves) == {c.upper() for c in Configuracoes.model_fields}` ∪ `{"DATABASE_URL_TEST", "POSTGRES_PASSWORD"}`. Falha: arquivo não existe.
**Implementação mínima:**
- `.env.example`: `DATABASE_URL=postgresql+psycopg://aprovaos:troque@localhost:5432/aprovaos`, `CHAVE_SECRETA=` (comentário: `python -c "import secrets; print(secrets.token_urlsafe(48))"`), `AMBIENTE=dev`, `COOKIE_SEGURO=true` (comentário sobre http em rede local — ver pergunta Q1), `SESSAO_DIAS=30`, `WEB_DIR=` (vazio = padrão), `DATABASE_URL_TEST=` (comentário: aponte para um banco descartável para rodar os testes `postgres`), `POSTGRES_PASSWORD=troque`.
- `compose.yaml` (https://docs.docker.com/reference/compose-file/): serviço `postgres` com `image: pgvector/pgvector:pg16` (https://github.com/pgvector/pgvector#docker), `environment: POSTGRES_USER=aprovaos, POSTGRES_PASSWORD=${POSTGRES_PASSWORD}, POSTGRES_DB=aprovaos`, `volumes: ./data/postgres:/var/lib/postgresql/data` (`data/` já é git-ignored), `ports: "5432:5432"`, `healthcheck: pg_isready -U aprovaos`; serviço `web` com `build: {context: ., dockerfile: backend/Dockerfile}`, `env_file: .env`, `environment: DATABASE_URL=postgresql+psycopg://aprovaos:${POSTGRES_PASSWORD}@postgres:5432/aprovaos`, `ports: "8000:8000"`, `depends_on: postgres: condition: service_healthy`, `command: sh -c "uv run alembic upgrade head && uv run uvicorn aprovaos.main:criar_app --factory --host 0.0.0.0 --port 8000"`. Sem `caddy`, sem `jobs` (ADR-0030).
- `Dockerfile`: `FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim` (imagem oficial do uv: https://docs.astral.sh/uv/guides/integration/docker/), `WORKDIR /app`, copiar `backend/pyproject.toml backend/uv.lock backend/.python-version` → `uv sync --locked --no-dev`, copiar `backend/` e `web/` (a app resolve `web/` como `../web` a partir do pacote; no container, coloque em `/web` e defina `WEB_DIR=/web` no `environment` do serviço `web` para não depender de layout).
**Pronto quando:** `docker compose config` valida; `docker compose up -d --build`; `curl localhost:8000/saude` → `{"status":"ok","banco":"ok"}`; cadastro pelo navegador em `http://localhost:8000` funciona contra o Postgres; `docker compose down` limpa.

### Passo 16 — `scripts/checar.sh` e `.github/workflows/ci.yml`
**Objetivo:** um único comando local = o que a CI roda.
**Arquivos:** `scripts/checar.sh`, `.github/workflows/ci.yml`.
**Teste red:** rodar `bash scripts/checar.sh` → "arquivo não encontrado". Depois de criado, deve terminar com `exit 0` e imprimir as 5 etapas (ruff check, ruff format --check, mypy, checar_import, pytest). Quebre de propósito um docstring público e confirme que o script falha (red do lint).
**Implementação mínima:** `checar.sh` com `set -euo pipefail`, `cd "$(dirname "$0")/../backend"`, e as etapas: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run python ../scripts/checar_import.py`, `uv run pytest -q`. `ci.yml`: `on: [push, pull_request]`; job `checar` em `ubuntu-latest`; `actions/checkout@v4`; `astral-sh/setup-uv` (https://github.com/astral-sh/setup-uv) com `enable-cache: true`; `uv python install` (lê `backend/.python-version`; usar `working-directory: backend`); `uv sync --locked`; `bash scripts/checar.sh` a partir da raiz. Sem serviço Postgres na CI (os testes `postgres` são pulados por falta de `DATABASE_URL_TEST`; entram na V3 quando a suíte exigir Postgres — ADR-0031).
**Pronto quando:** script verde localmente; o YAML passa em `actionlint` se disponível (senão, revisão visual contra a doc: https://docs.github.com/en/actions/writing-workflows). A execução real na nuvem depende de P-19 (dono).

### Passo 17 — Testes marcados `postgres`
**Objetivo:** provar migração e app contra Postgres real quando `DATABASE_URL_TEST` existir.
**Arquivos:** `tests/test_postgres.py`.
**Testes red** (ambos `@pytest.mark.postgres`; pulados sem a variável):
- `test_migracao_no_postgres`: `downgrade base` + `upgrade head` com `sqlalchemy.url = DATABASE_URL_TEST`; `compare_metadata(...) == []`.
- `test_app_no_postgres`: `criar_app(config_teste.model_copy(update={"database_url": url}))` → `GET /saude` 200; cadastro + login + `/conta` 200.
**Implementação mínima:** só os testes (fixture `url_postgres = os.environ["DATABASE_URL_TEST"]`). Rodar com `docker compose up -d postgres` e `DATABASE_URL_TEST=postgresql+psycopg://aprovaos:troque@localhost:5432/aprovaos_teste` (criar o banco de teste uma vez: `docker compose exec postgres createdb -U aprovaos aprovaos_teste`).
**Pronto quando:** verde com a variável; pulado (não falho) sem ela.

### Passo 18 — Docs, pendências e commit de fim de fatia
**Objetivo:** deixar escrito o que entrou, o que ficou e por quê (CLAUDE.md regras 6, 7, 12).
**Arquivos:** `docs/02-produto.md` (linha V1 da tabela §6 — texto na seção 10 abaixo), `docs/PENDENCIAS.md` (P-20 verificação de e-mail; P-21 enumeração de e-mail no cadastro; P-22 cookie `Secure` na rede local — se Q1 não estiver decidida), `docs/DECISOES.md` (adendo de uma linha na ADR-0026: "V1: assinatura do cookie por HMAC da stdlib; `itsdangerous` não entrou"; adendo na ADR-0031: "V1 entregue em <data>, copiar para `fabrica-saas/template-saas/` = pendência da fábrica"), `CLAUDE.md` (mapa do repositório: `backend/`, `web/`, `compose.yaml`, `scripts/`, `.github/` existem; linha da Fase 5 com "V1 no ar (local)").
**Teste red:** não há teste automatizado; o critério é o revisor conferir que a tabela do PRD §6 tem a linha V1 atualizada e que nada da seção 3 deste plano ficou sem linha em PENDENCIAS ou na tabela.
**Pronto quando:** `git commit` com mensagem descritiva (`feat(v1): template base — …`) e resumo curto para o dono.

## 7. Comandos

```bash
# setup
cd ~/PycharmProjects/aprovaos/backend && uv sync
cp ../.env.example ../.env && $EDITOR ../.env      # CHAVE_SECRETA e POSTGRES_PASSWORD

# ciclo de desenvolvimento (sem Docker)
uv run pytest -q                                   # SQLite em memória; testes postgres pulados
uv run pytest tests/test_rota_cadastro.py -x -q    # um arquivo (red/green)
uv run ruff check --fix . && uv run ruff format . && uv run mypy
uv run python ../scripts/checar_import.py
bash ../scripts/checar.sh                          # tudo, igual à CI

# banco e app
docker compose up -d postgres
uv run alembic upgrade head
uv run uvicorn aprovaos.main:criar_app --factory --reload   # http://localhost:8000
docker compose up -d --build                       # web + postgres pelo Compose
curl -s localhost:8000/saude

# testes contra Postgres real
docker compose exec postgres createdb -U aprovaos aprovaos_teste
DATABASE_URL_TEST=postgresql+psycopg://aprovaos:troque@localhost:5432/aprovaos_teste uv run pytest -q -m postgres

# migração nova (fatias seguintes)
uv run alembic revision --autogenerate -m "descricao" && uv run alembic upgrade head
```

## 8. Riscos

| risco | mitigação neste plano |
|---|---|
| Cookie `Secure` é rejeitado pelo navegador em `http://192.168.x.x` (piloto na rede local, ADR-0030); só `localhost` é contexto seguro. | `COOKIE_SEGURO` configurável (padrão `true`); decisão do piloto na Q1. |
| SQLite devolve `datetime` naive → comparação com aware estoura. | `DataHoraUtc` (passo 3) com teste de ida e volta. |
| Migração gerada em SQLite diverge do Postgres (tipos, constraints). | `compare_metadata == []` nos dois bancos (passos 6 e 17); convenção de nomes de constraint. |
| `TestClient` em outra thread com SQLite em memória → "no such table". | `StaticPool` + `check_same_thread=False` (doc oficial, passo 7). |
| Alguém cria `Jinja2Templates`/`create_engine` em nível de módulo "só desta vez". | `checar_import.py` na CI e no script local; falha antes do merge. |
| Vendorizar `htmx.min.js` sem licença ou versão. | Arquivo de licença ao lado e versão no cabeçalho (passo 8). |
| Enumeração de e-mail no cadastro. | Aceita no piloto; P-21. |
| `Path(__file__).parents[2]/"web"` não vale dentro do container. | `WEB_DIR` explícito no Compose (passo 15). |
| Dev júnior amplia escopo (verificação de e-mail, OAuth, "só um JS"). | Seção 3 é a lista do que **não** fazer; revisor confere. |

## 9. Definition of done da V1

1. `bash scripts/checar.sh` verde (ruff, format, mypy strict, import sem efeito colateral, pytest).
2. Cobertura funcional pelos testes dos passos 7–14: landing, saúde, erros JSON, cadastro, entrar, conta, sair, cookie com os três atributos.
3. `docker compose up -d --build` sobe `postgres` (pgvector) e `web`; `alembic upgrade head` roda no `command`; cadastro no navegador persiste no Postgres.
4. Testes `postgres` verdes com `DATABASE_URL_TEST`.
5. Nenhum arquivo sem cabeçalho de 2 linhas; nenhuma função/classe pública sem docstring (ruff `D`); nenhuma cor literal fora de `tokens.css`.
6. PRD §6 (linha V1), PENDENCIAS, DECISOES e CLAUDE.md atualizados; commit feito; resumo entregue ao dono.

## 10. Linha para a tabela do PRD §6

`| V1 (1) | Template base | conta e-mail+senha (ADR-0026, HMAC stdlib no cookie), tenant PF, modelo base (tenant, usuario, sessao, traco) + Alembic 0001, `/saude`, erros `{codigo, mensagem, acao}`, Compose (pgvector/pg16 + web), CI + `scripts/checar.sh` com prova de import sem efeito colateral, landing mínima | Google OAuth (1b), billing (12), SEO (13), **verificação de e-mail (P-20)**, deploy/Caddy (8, ADR-0030), exporter OTel para `traco` (V2/V3), extensão `vector` (V3) | no ar (local) — <data> |`

## 11. Perguntas em aberto — respondidas em 17/09/2026 (opções recomendadas adotadas; o dono pode vetar)

Q1 → (a) `COOKIE_SEGURO=false` no `.env` do piloto, anotado em `docs/RISCOS.md`. Q2 → 8–128, sem outras regras. Q3 → `tenant.nome` = e-mail. Q4 → `system-ui`. Q5 → sim, 404 em JSON na V1.


- **Q1 (passo 11/15):** no piloto pela rede local (ADR-0030), a Ana vai acessar por `http://<ip-da-máquina>:8000`. Cookie `Secure` não funciona aí. Opções: (a) `COOKIE_SEGURO=false` no `.env` do piloto, anotado em RISCOS; (b) Caddy local com TLS interno já na V1 (contraria "sem Caddy" da ADR-0030); (c) acesso só por `localhost` (túnel SSH/Tailscale). Recomendado: (a).
- **Q2 (passo 9):** política de senha = mínimo 8, máximo 128, sem outras regras. OK?
- **Q3 (passo 3):** `tenant.nome` no cadastro = o próprio e-mail (não há campo "nome" no formulário). OK, ou incluir campo "nome" opcional?
- **Q4 (passo 8):** landing e páginas com fonte do sistema (`system-ui`) até a Fase 6, ou vendorizar Sora/IBM Plex já? Recomendado: sistema.
- **Q5 (passo 7):** 404 de página HTML em JSON é aceitável na V1? Recomendado: sim (página de erro HTML entra quando houver navegação real, V2).

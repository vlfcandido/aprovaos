# Fatia V1 — registro de execução (passos 1–7)
> O que é: o diário de execução do plano `V1-template-base.md`, um bloco por passo com o teste, a linha do red, a linha do green, o resultado de lint/mypy/import e os desvios. Quando ler: ao revisar o PR da V1 ou ao retomar a fatia a partir do passo 8.

Executado em 17/09/2026 em `/Users/vinicius/PycharmProjects/aprovaos`, `uv 0.8.22`, CPython 3.13.7, tudo em SQLite (sem Docker). Nenhum commit feito. Versões resolvidas no `backend/uv.lock`: fastapi 0.141.1, starlette 1.6.0, sqlalchemy 2.0.54, alembic 1.20.0, pydantic 2.13.5, pydantic-settings 2.15.0, psycopg 3.3.5, uvicorn 0.53.0, pytest 9.1.1, ruff 0.16.8, mypy 2.3.1, httpx 0.28.1.

Comandos padrão de cada passo (rodados de `backend/`): `uv run pytest tests/<arquivo> -x -q` (red e green) · `uv run ruff check --fix . ../scripts && uv run ruff format . ../scripts && uv run mypy` · a partir do passo 5, `uv run --project backend python scripts/checar_import.py` (da raiz).

## Passo 1 — Esqueleto `backend/` com `uv`
- Teste: `tests/test_pacote.py::test_pacote_importa`.
- Red: `E   ModuleNotFoundError: No module named 'aprovaos'`
- Green: `1 passed in 0.00s`
- ruff check `All checks passed!` · ruff format OK · mypy `Success: no issues found in 6 source files`.
- Arquivos: `backend/.python-version`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/aprovaos/{__init__,dominio/__init__,dados/__init__,api/__init__}.py`, `backend/tests/{__init__,test_pacote}.py`.
- Desvio: `[tool.mypy] files` nasceu como `["aprovaos", "tests"]` porque `scripts/` fica na **raiz do repo** (não em `backend/`) e só existe no passo 5; mypy aborta com caminho inexistente. No passo 5 virou `["aprovaos", "tests", "../scripts"]`.

## Passo 2 — `config.py`: configurações por fábrica
- Testes: `tests/test_config.py` (5: valores explícitos, env, obrigatórias, cache, `SecretStr` em `repr`).
- Red: `E   ModuleNotFoundError: No module named 'aprovaos.config'`
- Green: `5 passed in 0.14s`
- ruff OK · mypy `Success: no issues found in 8 source files` · `grep -rn "Configuracoes()" aprovaos/` → só `aprovaos/config.py:47` (dentro de `obter_configuracoes`).
- Sem desvios.

## Passo 3 — Modelos ORM base
- Testes: `tests/test_modelos.py` (7).
- Red: `E   ModuleNotFoundError: No module named 'aprovaos.dados.base'`
- Green: `7 passed in 0.18s`
- ruff OK · mypy OK (após trocar `inspect(modelo).columns` no teste por `Base.metadata.tables[nome].columns`, que é tipado) · `grep -rn create_engine aprovaos/` vazio.
- Detalhes: `CheckConstraint(..., name="tipo")` → `ck_tenant_tipo` pela convenção; `DataHoraUtc.process_bind_param` rejeita naive com `TypeError` (segue o exemplo oficial do `TypeDecorator`); `Traco.criado_em` com `default=agora_utc` (o plano só listava a coluna).
- Sem desvios de esquema.

## Passo 4 — `dados/conexao.py`
- Testes: `tests/test_conexao.py` (2).
- Red: `E   ModuleNotFoundError: No module named 'aprovaos.dados.conexao'`
- Green: `2 passed in 0.12s`
- ruff OK · mypy `Success: no issues found in 13 source files`.
- Sem desvios.

## Passo 5 — Prova de zero efeito colateral em import
- Teste: `tests/test_import_sem_efeito_colateral.py::test_script_de_import_passa`.
- Red: `E   AssertionError: .../backend/.venv/bin/python: can't open file '/Users/vinicius/PycharmProjects/aprovaos/scripts/checar_import.py': [Errno 2] No such file or directory` / `assert 2 == 0`
- Green: `1 passed in 0.29s`; `uv run --project backend python scripts/checar_import.py` → `importados: 8`.
- Sanidade: com um módulo temporário `aprovaos/_tmp_efeito.py` chamando `create_engine` em import, o script imprimiu `RuntimeError: efeito colateral em import: rede ou create_engine` (removido em seguida).
- ruff OK · mypy `Success: no issues found in 15 source files` (com `../scripts` incluído; um `# type: ignore` desnecessário removido).
- Desvio: ruff é rodado com `. ../scripts` explicitamente — o `scripts/checar.sh` do passo 16 deve incluir `../scripts` no `ruff check`, senão o script fica fora do lint.

## Passo 6 — Alembic: migração `0001_base`
- Testes: `tests/test_migracoes.py` (2).
- Red: `E   alembic.util.exc.CommandError: Path doesn't exist: /Users/vinicius/PycharmProjects/aprovaos/backend/alembic.  Please use the 'init' command to create a new scripts folder.`
- Green: `2 passed in 0.31s`
- ruff (2 correções automáticas de import em `env.py`) · mypy `Success: no issues found in 16 source files` · `checar_import.py` → `importados: 8` · suíte `18 passed`.
- Como foi: `uv run alembic init alembic`; `README` removido (fora da lista de arquivos do plano); `alembic.ini` com `sqlalchemy.url =` vazio e cabeçalho de 2 linhas; `env.py` reescrito (`create_engine` só dentro de `run_migrations_online`, `render_as_batch=True`, `compare_type=True`, URL de `sqlalchemy.url` ou `obter_configuracoes().database_url`); revisão gerada com `--autogenerate` num SQLite do scratchpad e **revisada**: `aprovaos.dados.base.DataHoraUtc(timezone=True)` (sem import, quebraria) virou `sa.DateTime(timezone=True)`, `id` passou para a primeira coluna, arquivo renomeado `0001_base.py` com `revision = "0001"`.
- Observação: `env.py` executa `run_migrations_online()` em nível de módulo por contrato do Alembic; ele não pertence ao pacote `aprovaos` e nunca é importado pela app (o `checar_import.py` não o toca).

## Passo 7 — `criar_app()`, `/saude`, erros JSON e fixtures
- Testes: `tests/conftest.py` (fixtures `config_teste`, `engine`, `app`, `cliente`, `db` + hook de skip `postgres`), `tests/test_saude.py` (2), `tests/test_erros.py` (3).
- Red: `E   ModuleNotFoundError: No module named 'aprovaos.main'` (ao carregar o conftest).
- Green: `5 passed, 2 warnings in 0.04s`
- ruff OK (após encurtar uma linha de cabeçalho do conftest) · mypy `Success: no issues found in 23 source files` (após aceitar `Mapping[str, str]` nos headers de `HTTPException`) · `checar_import.py` → `importados: 12` · suíte completa `23 passed, 2 warnings in 0.56s`.
- Ajuste pós-green: o 404 padrão saía com `mensagem="Not Found"` (frase do Starlette, em inglês) — visto num smoke `criar_app()` a partir do ambiente. Adicionei `MENSAGEM_PADRAO` (404/405 em pt-BR) em `api/erros.py` e a asserção `"não encontrado" in mensagem` em `test_404_em_json`. Esta asserção foi escrita junto com a correção (o red foi a saída do smoke, não um pytest vermelho).
- Warnings (de terceiros, não do nosso código): `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` e `DeprecationWarning: anyio.abc.BlockingPortal`. O plano fixa `httpx` como dependência de dev; decidir sobre `httpx2` é do dono/plano (não alterei).
- `FastAPI(docs_url=None, redoc_url=None)`: sem Swagger — não há rota `/api/*` na V1 e a landing/erros são a fronteira; reativar quando houver API pública.

## Passo 8 — Templates, tokens CSS, HTMX e landing `/`
- Testes: `tests/test_inicio.py` (5: landing, estáticos, cor literal fora de `tokens.css`, dois temas em `tokens.css`, licença do htmx com versão).
- Red: `FAILED tests/test_inicio.py::test_landing - assert 404 == 200`
- Green: `5 passed in 0.04s`
- Comandos: `uv run pytest tests/test_inicio.py -x -q` (red e green) · `uv run ruff check --fix . ../scripts && uv run ruff format . && uv run mypy && uv run python ../scripts/checar_import.py && uv run pytest -q` → ruff `All checks passed!` (após encurtar a linha 2 do cabeçalho do teste) · format `34 files left unchanged` · mypy `Success: no issues found in 33 source files` · `importados: 18` · suíte `38 passed in 1.66s` (sem avisos).
- htmx: `curl -sSL -o web/static/js/htmx.min.js https://unpkg.com/htmx.org@2/dist/htmx.min.js` resolveu para **2.0.10** (`version:"2.0.10"` dentro do minificado); `web/static/js/LICENSE-htmx.txt` = cabeçalho de 2 linhas com versão/data/URL + texto Zero-Clause BSD baixado de `unpkg.com/htmx.org@2.0.10/LICENSE`. O minificado não foi editado.
- Arquivos: `web/templates/base.html`, `web/templates/inicio.html`, `web/static/css/tokens.css`, `web/static/css/base.css`, `web/static/js/htmx.min.js`, `web/static/js/LICENSE-htmx.txt`, `backend/aprovaos/api/templates.py`, `backend/aprovaos/api/inicio.py`, `backend/aprovaos/main.py` (resolve `web_dir`, monta `/static`, guarda `app.state.templates`, inclui `inicio.router`), `backend/tests/test_inicio.py`.
- Tema: tokens em `:root` (claro, paleta do protótipo clicável com nomes em pt-BR: `--cor-fundo`, `--cor-acao`, `--cor-porque`…), redefinidos em `@media (prefers-color-scheme: dark) { :root:not([data-theme="claro"]) … }` e em `:root[data-theme="escuro"]`; `color-scheme: light dark`; `body` com `background`/`color` explícitos; `.pagina` com `max-width: 28rem`, `padding-inline: var(--espaco-4)` (16 px) e `overflow-x: hidden` em `html`/`body`; única transição sob `prefers-reduced-motion: no-preference`. Fonte `system-ui` (premissa J / Q4) — Sora/IBM Plex não estão locais.
- Desvios (pequenos, dentro do plano): (1) o teste de cor literal também rejeita `rgba(`/`hsl(` e `#` com até 8 dígitos; (2) dois testes além dos três listados (`test_tokens_cobrem_os_dois_temas`, `test_licenca_do_htmx_registra_versao`) para travar os requisitos do enunciado; (3) a `nav` do `base.html` mostra "Entrar"/"Criar conta" fixos — ganha estado de login no passo 14, como o plano prevê; (4) o cabeçalho de 2 linhas dos templates usa comentário Jinja `{#- … -#}` (com trim) para não vazar linha em branco antes do `<!doctype>`; (5) `include_in_schema=False` em `GET /` (não há OpenAPI ativo, mas evita a rota aparecer se `docs_url` voltar). PRD §6 não foi tocado: a linha V1 é do passo 18.
- Verificação manual pendente para o dono: abrir `http://localhost:8000/` no modo responsivo nos dois temas (`uv run uvicorn aprovaos.main:criar_app --factory --reload`, com `.env` — o arquivo só nasce no passo 15).

## Estado ao fim
- Após o passo 8: 38 testes verdes (inclui os testes dos passos 9–11 em andamento por outro agente); `ruff check`, `ruff format`, `mypy --strict` e `checar_import.py` (18 módulos) limpos.
- Não tocado pelo passo 8: passos 12–18 (rotas de conta, Compose, CI, docs/PRD). Nenhum commit.

## Passo 9 — Domínio: senha (argon2) e esquemas de conta
- Testes: `tests/test_senha.py` (3) e `tests/test_dominio_conta.py` (4).
- Red: `E   ModuleNotFoundError: No module named 'aprovaos.dominio.senha'`
- Green: `7 passed in 0.41s`
- ruff OK · format OK · mypy `Success: no issues found in 29 source files` · `importados: 15`.
- Arquivos: `backend/aprovaos/dominio/{erros,senha,conta}.py`. Senha 8–128 (Q2); e-mail em minúsculas por `field_validator(mode="after")`; `DadosLogin` com `min_length=1`.
- Desvio (documentado): no argon2-cffi 25.1.0, hash malformado (`"lixo"`) levanta `InvalidHashError`, que é subclasse de `ValueError`, **não** de `VerificationError` como o plano supunha. A doc do `PasswordHasher.verify` lista as três exceções (`VerifyMismatchError`, `VerificationError`, `InvalidHashError`); `verificar()` captura `(VerificationError, InvalidHashError)`. O teste ganhou um caso extra (hash com formato argon2 mas conteúdo inválido → `VerificationError` → `False`).

## Passo 10 — Repositório de conta
- Testes: `tests/test_repositorio_conta.py` (3), com a fixture `db` do conftest.
- Red: `E   ModuleNotFoundError: No module named 'aprovaos.dados.repositorio_conta'`
- Green: `3 passed in 0.29s`
- ruff (1 correção automática de ordem de import no teste) · mypy `Success: no issues found in 33 source files` · `importados: 18` · suíte `38 passed`.
- Arquivo: `backend/aprovaos/dados/repositorio_conta.py` — `buscar_por_email` (`select(...).where(email ==, excluido_em.is_(None))`), `criar_conta` (checa por consulta antes de inserir; `Tenant(tipo="pf", nome=email)` — Q3; `add`+`flush`, commit é da rota), `autenticar` (uma única `CredenciaisInvalidas` para e-mail inexistente, excluído ou senha errada).
- Sem desvios.

## Passo 11 — Sessão de login: token, assinatura, cookie e dependências
- Testes: `tests/test_sessao.py` (8: os 6 do plano + `test_usuario_atual_com_cookie_valido` e `test_exigir_usuario_redireciona_para_entrar`, que travam a parte da implementação mínima sem teste listado).
- Red: `E   ModuleNotFoundError: No module named 'aprovaos.api.sessao'`
- Green: `8 passed in 0.27s`
- ruff OK (após quebrar a linha longa do cabeçalho de `api/erros.py`) · format (1 arquivo reformatado) · mypy `Success: no issues found in 36 source files` · `importados: 20` · suíte `46 passed in 1.65s`, zero avisos.
- Arquivos: `backend/aprovaos/dados/repositorio_sessao.py` (`abrir_sessao` → `secrets.token_urlsafe(32)`, grava `sha256`; `usuario_da_sessao`; `revogar_sessao` idempotente), `backend/aprovaos/api/sessao.py` (`NOME_COOKIE`, `assinar`/`verificar_assinatura` com `hmac.new(..., hashlib.sha256)` + `compare_digest` e `rpartition(".")`; `definir_cookie`/`limpar_cookie` via `Response.set_cookie`/`delete_cookie`; `token_do_request`; `usuario_atual`; `exigir_usuario`; `RedirecionarParaEntrar`), `backend/aprovaos/api/erros.py` (tratador `RedirecionarParaEntrar` → `RedirectResponse("/entrar", 303)`; `main.py` não foi tocado porque já chama `registrar_tratadores`).
- Assinatura do cookie: premissa A do plano (HMAC stdlib, sem `itsdangerous`); adendo na ADR-0026 fica para o passo 18.
- Desvios: (1) `limpar_cookie(resposta, config)` recebe `config` (o plano não listava) para repetir `secure` nos mesmos atributos do `delete_cookie`; (2) `definir_cookie` lê `sessao_dias` da `Configuracoes` em vez de parâmetro `dias` separado (uma fonte só); (3) o teste de cookie adulterado usa `cliente.cookies.set(...)` em vez de `cookies={...}` por request — o httpx 0.28 emite `DeprecationWarning` para o segundo e a suíte trata aviso como erro. O passo 14 do plano cita `cookies={...}`: usar a forma do cliente lá também.

## Estado ao fim dos passos 9–11
- 46 testes verdes; `ruff check`/`ruff format` (backend + `../scripts`), `mypy --strict` (36 arquivos) e `checar_import.py` (20 módulos) limpos, sem avisos.
- Não tocado: `main.py`, `api/templates.py`, `api/inicio.py`, `web/`, `conftest.py`, `test_inicio.py`. Passos 12–18 pendentes. Nenhum commit.

## Passo 12 — Rotas `/cadastro` (GET/POST)
- Testes: `tests/test_rota_cadastro.py` (7, os do plano).
- Red: `FAILED tests/test_rota_cadastro.py::test_get_cadastro - assert 404 == 200`
- Green: `7 passed in 0.27s`
- ruff (1 correção automática de ordem de import no teste) · format OK · mypy `Success: no issues found in 39 source files` · `importados: 21` · suíte `54 passed` (o `test_env_example.py` do passo 15, de outro agente, já estava verde nesse momento).
- Arquivos: `backend/aprovaos/api/conta.py` (novo: router `include_in_schema=False`, `GET/POST /cadastro`, helper `_entrar_com` = `abrir_sessao` → `commit` → redirecionamento + cookie), `web/templates/conta/cadastro.html` (novo: `hx-post`/`hx-select`/`hx-target="#form-cadastro"` + `hx-swap="outerHTML"`, funciona sem JS), `backend/aprovaos/api/erros.py` (`mensagens_de_validacao(erro) -> list[str]` + `ROTULO_DO_CAMPO`, traduz `string_too_short`/`string_too_long`/`missing`/e-mail inválido), `backend/aprovaos/api/templates.py` (`responder_redirecionamento(request, destino)`: `HX-Redirect` sob `HX-Request: true`, senão `303`), `backend/aprovaos/main.py` (inclui `conta.router`).
- Desvios: (1) `hx-swap="outerHTML"` além dos três atributos do plano — com `hx-select="#form-cadastro"` e `hx-target="#form-cadastro"`, o padrão `innerHTML` aninharia um `<form>` dentro do outro (https://htmx.org/attributes/hx-swap/); (2) o link para `/entrar` exigido no erro de e-mail repetido é o "Já tenho conta — entrar" que já fica no formulário (sem bloco condicional extra).

## Passo 13 — Rotas `/entrar` (GET/POST)
- Testes: `tests/test_rota_entrar.py` (6: os 5 do plano + `test_post_entrar_email_invalido_mesma_mensagem`, que trava "`ValidationError` cai na mensagem genérica").
- Red: `FAILED tests/test_rota_entrar.py::test_get_entrar - assert 404 == 200`
- Green: `6 passed in 0.52s`
- ruff OK (após quebrar duas linhas longas no teste) · format OK · mypy `Success: no issues found in 40 source files` · `importados: 21` · suíte `60 passed`.
- Arquivos: `backend/aprovaos/api/conta.py` (`GET/POST /entrar`, `MENSAGEM_LOGIN_INVALIDO`; `ValidationError` e `CredenciaisInvalidas` no mesmo `except`), `web/templates/conta/entrar.html` (novo, `autocomplete="current-password"`).
- Achado (não é desvio, mas fica registrado): com `Annotated[str, Form()]` do plano, campo de formulário **vazio** (`senha=""`) é tratado pelo FastAPI como ausente e responde `422` JSON antes de chegar ao `DadosLogin` — o primeiro rascunho do teste extra usou senha vazia e falhou por isso; ajustei para `senha="x"` (o que eu queria testar era e-mail malformado → mensagem genérica). No navegador o `required` dos campos cobre o caso; premissa F aceita JSON fora de formulário HTML.

## Passo 14 — `/conta`, `/sair` e navegação com estado de login
- Testes: `tests/test_rota_conta.py` (6: os 5 do plano + `test_sair_htmx_e_sem_login`, que trava `HX-Redirect: /` e a limpeza do cookie mesmo sem sessão).
- Red: `FAILED tests/test_rota_conta.py::test_conta_sem_login_redireciona - assert 404 == 303`
- Green: `6 passed in 0.38s`
- ruff OK · format (1 arquivo reformatado) · mypy `Success: no issues found in 41 source files` · `importados: 21` · suíte `66 passed in 2.44s`, zero avisos. Smoke por `TestClient`: cadastrar → `/conta` (200, nav "Minha conta"/"Sair") → `/sair` → `/` → `/conta` cai em `/entrar`.
- Arquivos: `backend/aprovaos/api/templates.py` (`renderizar(request, nome, contexto, usuario)` injeta `usuario_email`; o ORM não chega ao template), `backend/aprovaos/api/conta.py` (`GET /conta` com `exigir_usuario`; `POST /sair` = `token_do_request` → `revogar_sessao` → `commit` → `responder_redirecionamento("/")` + `limpar_cookie`; rotas de formulário passam `usuario_atual` para a navegação), `backend/aprovaos/api/inicio.py` (passa `usuario_atual`), `web/templates/base.html` (nav: logado = "Minha conta" + form `POST /sair` com botão "Sair"; anônimo = "Entrar" + "Criar conta"), `web/templates/inicio.html` (logado: botão "Ir para minha conta" no lugar de "Criar conta" — o teste exige que "Criar conta" suma da landing logada), `web/templates/conta/conta.html` (novo), `web/static/css/base.css` (`.botao-link` e `.navegacao__sair`, sem cor literal).
- Desvios: (1) `POST /sair` usa `responder_redirecionamento` (o plano dizia `RedirectResponse("/", 303)` fixo) para o botão da nav funcionar também sob htmx — sem htmx é o mesmo 303; (2) o "Sair" aparece na nav (todas as páginas) e na `/conta` (botão do plano), duas `<form>` iguais; (3) o cookie adulterado no teste usa `cliente.cookies.set(...)`, como registrado no passo 11.

## Estado ao fim dos passos 12–14
- 66 testes verdes; `ruff check`/`ruff format` (backend + `../scripts`), `mypy --strict` (41 arquivos) e `checar_import.py` (21 módulos) limpos, sem avisos.
- Verificação manual pendente para o dono: no navegador, cadastrar → conta → sair → `/conta` volta para `/entrar` (passo 14, "pronto quando").
- Não tocado: passos 15–18 (Compose/Dockerfile já em andamento por outro agente; CI, testes `postgres`, docs/PRD). Nenhum commit.

## Passo 15 — `.env.example`, `compose.yaml`, `Dockerfile` (sessão principal)
- Red: `uv run pytest tests/test_env_example.py -q` → `FileNotFoundError: … /.env.example`.
- Green: arquivo criado com todas as chaves de `Configuracoes` + `DATABASE_URL_TEST`, `POSTGRES_PASSWORD` → `1 passed`.
- `compose.yaml` e `Dockerfile` (arquivos de configuração — sem teste unitário): `docker compose config --quiet` → rc=0 com um `.env` temporário (removido depois). **Não executado** `docker compose up` (daemon parado nesta máquina) — ver DoD.

## Passo 16 — `scripts/checar.sh` e `.github/workflows/ci.yml` (sessão principal)
- Red: `bash scripts/checar.sh` → `No such file or directory` (rc=127). Depois de criado, a primeira execução **falhou de verdade** na etapa 1 (ruff `I001` em `tests/test_rota_cadastro.py`, estado intermediário do passo 12) — prova de que o script barra lint.
- Green (após o passo 14): `ruff check` OK · `ruff format --check` OK · `mypy` OK · `importados: 21` · `66 passed, 2 skipped` · `checkagem completa: OK`.
- `ci.yml`: `actions/checkout@v4` + `astral-sh/setup-uv@v6` (cache por `backend/uv.lock`) + `uv python install` + `uv sync --locked` + `bash scripts/checar.sh`. Não executado na nuvem (sem remoto, P-19).

## Passo 17 — testes `postgres` (sessão principal)
- Red: sem `DATABASE_URL_TEST` → `2 skipped` (skip vem do `conftest`); com uma URL de Postgres inexistente → erro de conexão (`psycopg` `conn_errors`), i.e., o teste tenta o banco de verdade.
- Green real **pendente**: exige `docker compose up -d postgres`, `createdb aprovaos_teste` e `DATABASE_URL_TEST=…` — o daemon Docker estava parado na sessão de 17/09.

## Passo 18 — docs e commit (sessão principal)
- PRD §6 linha V1 → "no ar (local) — 17/09/2026"; P-21 (verificação de e-mail), P-22 (enumeração de e-mail); adendos nas ADR-0026 e 0031; `CLAUDE.md` (mapa, estado, como rodar); `RISCOS.md` R-19 (cookie sem `Secure` no piloto local).
- Prova de ponta a ponta com servidor real (SQLite em arquivo): `alembic upgrade head` → `0001`; `uvicorn --factory`; `/saude` ok; `POST /cadastro` → 303 `/conta` com cookie; via `HX-Request` → 200 + `HX-Redirect: /conta`; `/conta` logada mostra e-mail e `action="/sair"`; `POST /sair` → 303 `/`; `/conta` depois → 303 `/entrar`; `/nada` → 404 JSON `{codigo, mensagem, acao}`; zero erros no log.
- `qa-eval` (Sonnet, read-only) rodou `scripts/checar.sh` e os greps de efeito colateral: sem achados de código; bloqueantes = diário incompleto (este trecho resolve), commit (feito na sequência) e Compose/`postgres` não executados (Docker parado — passo do dono).

## DoD (plano §9) — estado em 17/09/2026
Itens 1, 2, 5, 6 ✅ · item 3 (Compose sobe Postgres+pgvector) e item 4 (testes `postgres` verdes) **pendentes de execução com Docker** — comandos: `cp .env.example .env` (preencher `CHAVE_SECRETA`, `POSTGRES_PASSWORD`), `docker compose up -d --build`, `curl localhost:8000/saude`, `docker compose exec postgres createdb -U aprovaos aprovaos_teste`, `cd backend && DATABASE_URL_TEST=postgresql+psycopg://aprovaos:<senha>@localhost:5432/aprovaos_teste uv run pytest -q tests/test_postgres.py`.

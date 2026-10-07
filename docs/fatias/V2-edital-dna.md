# Fatia V2 — Subir edital → DNA reduzido + edital verticalizado: plano de implementação
> O que é: o plano passo a passo (micro-TDD red→green→refactor) da fatia V2 do piloto v0 — a aluna sobe um edital em PDF, o sistema extrai o conteúdo programático por regras, monta um `DnaConcurso` (por IA via ADK quando há chave e teto, senão por regras) e mostra o DNA reduzido e o edital verticalizado zerado. Quando ler: antes da primeira linha da V2 e a cada passo, para saber qual teste escrever primeiro; ao revisar o PR da V2, para conferir o critério de pronto.

Fontes de decisão: `CLAUDE.md` (regras 1–12), `docs/fatias/V1-template-base.md` §2/§5 e `V1-execucao.md` (desvios: `httpx2`, `cliente.cookies.set()`, `hx-swap="outerHTML"`), `docs/03-arquitetura.md` §2/§4/§5/§8/§9, `docs/04-modelo-de-dados.md` §2/§3/§6, ADR-0018 (+ adendo 17/09), 0023, 0027, 0028, 0030, skill `.claude/skills/dna-do-concurso/SKILL.md` (contrato JSON = `output_schema`), PRD §3 F1.4–F1.6 e §6 (linha V2), fixture `docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md`.

## 1. Objetivo

Uma pessoa logada sobe um PDF de edital em `/editais/subir`, é levada a `/concurso/{id}` e vê (a) o DNA reduzido — distribuição por matéria em % de pontos, regra de correção, lacunas declaradas em linguagem clara, e se foi "gerado por regras" ou "por IA" — e (b) o edital verticalizado — matérias → tópicos, todos `não visto`, cobertura "0 de N"; tudo persistido nas tabelas `concurso`, `edital`, `documento`, `topico`, `topico_edital`, `dna_concurso`, com cada chamada de LLM registrada em `traco` e limitada por um teto diário em R$.

## 2. Premissas (decisões tomadas por este plano; qualquer uma pode ser vetada pelo dono)

| # | premissa | por quê |
|---|---|---|
| A | **Concurso principal = o último `concurso` do tenant** (por `criado_em`). `perfil_estudo.concurso_principal_id` não entra. | Escopo acordado; `perfil_estudo` é da fatia 7 (rotina). Registrar como P-23 no passo 15. |
| B | **`dna_concurso` guarda o JSON inteiro do `DnaConcurso` em uma coluna `conteudo` (JSON)** + `origem` (`ia`/`regras`), `modelo`, `motivo_fallback`, `versao`, `gerado_em`. As colunas JSON separadas do modelo §3 (`pesos`, `incidencia`, `estilo`…) **não** nascem. | Nenhuma consulta desta fatia filtra por dentro do JSON; 11 colunas JSON para um objeto que é sempre lido inteiro é abstração especulativa. Adendo de uma linha em `docs/04-modelo-de-dados.md` §3 no passo 15. Tipo `sqlalchemy.JSON` genérico (SQLite e Postgres): https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.JSON . |
| C | **Colunas mínimas** (padrão da V1, premissa D de lá): `concurso(tenant_id?, orgao, cargo, banca, data_prova?)`; `edital(concurso_id, versao, documento_id)`; `documento(tipo, hash, caminho, baixado_em, metadados)`; `topico(materia, nome, slug único)`; `topico_edital(edital_id, topico_id, ordem, peso_edital?, texto_original)`. `status`, `uf`, `vagas`, `fonte_id`, `retificacao_de`, `pai_id` ficam para as fatias que os usarem. `ordem` (posição do tópico no edital) é a única coluna fora do §3 — sem ela o verticalizado não tem ordem estável. | YAGNI; migrações aditivas são baratas. `documento.fonte_id` depende da tabela `fonte` (coletor, V3). |
| D | **Vocabulário de tópicos por `slug` global com get-or-create.** Dois editais que produzem o mesmo slug (`dir-adm-01-principios-administracao`) compartilham a linha em `topico`; o texto de cada edital fica em `topico_edital.texto_original`. | É o que a skill pede (`topico_novo` quando não existe) e o que a fatia V3 precisa para casar questões Cebraspe por tópico. |
| E | **Regra de slug** (a skill fixa só o formato `materia-nn-nome-curto`): prefixo da matéria = 3 primeiras letras de cada palavra significativa do nome, sem acento (`DIREITO ADMINISTRATIVO` → `dir-adm`, `LÍNGUA PORTUGUESA` → `lin-por`); `nn` = número do item com 2 dígitos; `nome-curto` = até 2 palavras significativas do texto do item (`4. Licitações e contratos — Lei nº 14.133/2021.` → `dir-adm-04-licitacoes-contratos`). Palavras não significativas: `de, da, do, das, dos, e, a, o, as, os, em, no, na, nº, n`. Slug de matéria (chave de `pesos.materia` e `topicos_edital[].materia`) = nome inteiro slugificado (`lingua-portuguesa`, `conhecimentos-especificos`). Normalização por `unicodedata.normalize("NFKD")` (https://docs.python.org/3.13/library/unicodedata.html#unicodedata.normalize). | Determinístico e reproduzível; o LLM recebe a lista de slugs já calculada e deve usá-la (verificação 4 da skill). |
| F | **Porta assíncrona**: `class AnalistaDeEdital(Protocol)` com `async def analisar(self, texto: str, materias: list[MateriaExtraida]) -> DnaConcurso`. A rota `POST /editais/subir` é `async def`. | O ADK é `run_async` (ADR-0018 adendo); `UploadFile.read()` também é `async`. Chamar SQLAlchemy síncrono dentro da rota async bloqueia o loop por milissegundos — aceito no piloto n=1 (risco §8). Doc: https://fastapi.tiangolo.com/async/ . |
| G | **Uso de tokens sai do ADK por callback**: `criar_analista_adk(config, registrar_chamada: Callable[[ChamadaLlm], None])`; o `AnalistaAdk` chama o callback uma vez por chamada (sucesso ou erro) com `ChamadaLlm(agente, modelo, iniciado_em, duracao_ms, tokens_in, tokens_out, custo_brl, resultado, erro)`. A rota passa um closure que grava em `traco`. A porta continua devolvendo só `DnaConcurso`. | Mantém a assinatura da porta do escopo; sem atributo mutável "última chamada"; a gravação em `traco` fica onde há `db`. |
| H | **`verificar_dna(dna, materias)`** recebe também a lista extraída pelo parser. | A verificação 4 da skill ("`topicos_edital` cobre 100 % das linhas do conteúdo programático") não é decidível só com o DNA. |
| I | **Chave do Gemini via `Gemini(model=…, client=genai.Client(api_key=…))`**, sem tocar `os.environ`. `LlmAgent.model` aceita uma instância de `BaseLlm`; `Gemini` tem o campo `client: Optional[genai.Client]` ("When provided, this client will be used for all API calls instead of constructing a new one from environment variables") — conferido em `google/adk/models/google_llm.py` (main, 17/09/2026). O passo 10 manda confirmar no pacote instalado; se a versão pinada não tiver `client`, usar `os.environ.setdefault("GOOGLE_API_KEY", …)` **dentro** da fábrica e registrar em `V2-execucao.md`. | ADR-0030: chave lida só por fábrica de configuração; `checar_import.py` continua provando zero efeito em import. |
| J | **Fixture PDF gerada por `reportlab` (BSD-3-Clause, https://pypi.org/project/reportlab/) como dependência de dev**, via `scripts/gerar_fixture_pdf.py`, e o PDF resultante **commitado uma vez** (exceção no `.gitignore`). Descartado `cupsfilter`: só macOS, deprecado pela Apple e não reproduzível na CI. Descartado escrever PDF "na mão": frágil com acentos e quebra de linha. `pypdfium2` não gera texto. | Um script reproduzível em qualquer máquina; a quebra de linha do `Paragraph` do reportlab produz exatamente o caso de borda "item quebrado em duas linhas" que o parser precisa tratar. |
| K | **Modelo do DNA: `MODELO_DNA=gemini-2.5-flash`** (ADR-0018: Flash para DNA); preços de `docs/06-custos.md` linhas 9–11 (Flash US$ 0,30/2,50 por 1M; Flash-Lite 0,10/0,40; câmbio R$ 5,40). Teto diário `TETO_DIARIO_BRL=3.00` (ADR-0018: R$ 3/dia sem receita). | Fonte única de preço; o teto vale desde a primeira chamada (ADR-0030). |
| L | **Traço só para chamada de LLM** (`resultado` ∈ `ok`/`erro`); DNA por regras não gera linha em `traco` — a origem fica em `dna_concurso.origem`/`motivo_fallback`. `tier` fica `None` na V2. | O escopo diz "uma linha em `traco` por chamada"; regras não custam. |
| M | **Sem `extra="forbid"` nos modelos do DNA.** | Gemini structured output não aceita `additionalProperties`; `forbid` só adicionaria risco de esquema sem ganho (o que vale é `verificar_dna`). |
| N | Erros esperados do formulário de upload (não é PDF, > 10 MB, PDF sem texto, conteúdo programático não encontrado) voltam **200 com a página re-renderizada** (premissa F da V1). 403 (concurso de outro tenant) e 404 saem em **JSON** `{codigo, mensagem, acao}` como na V1. | Mesmo contrato da V1; página de erro HTML fica para quando houver navegação real. |

## 3. Fora da V2 (rastreado; não implementar)

Radar/catálogo de concursos e `concurso.tenant_id = NULL` populado (fatia 1b) · estilo da banca local, corte histórico e incidência por prova (P-17; o DNA declara `desconhecido`) · retificações = versão 2 do `edital` (nova pendência P-24) · eventos de estudo e status `em andamento`/`visto` no verticalizado (V3/V4) · `perfil_estudo`/concurso principal escolhido (fatia 7, P-23) · `DatabaseSessionService` do ADK (ADR-0018 adendo) · OTel/exporter (ADR-0024; nova pendência P-25 — `traco` é escrito à mão nesta fatia) · dossiês, questões, aulas (V3+) · pipeline visível com status (F1.5 CA) · OCR de PDF-imagem (ADR-0023) · `pdfplumber` (só entra com gabaritos, V3) · página `/admin/tracos`.

## 4. Estrutura final de arquivos (o que a V2 acrescenta ou toca)

```
backend/
  pyproject.toml                       # + pypdfium2, google-adk; dev: reportlab; marker llm; overrides mypy se preciso
  alembic/versions/0002_edital_dna.py  # 6 tabelas novas
  aprovaos/config.py                   # + uploads_dir, google_api_key, modelo_dna, teto_diario_brl
  aprovaos/main.py                     # + uploads_dir em app.state, router editais, filtro Jinja `pct`
  aprovaos/dados/modelos.py            # + Concurso, Edital, Documento, Topico, TopicoEdital, DnaConcursoRegistro
  aprovaos/dados/arquivos.py           # guardar_pdf(uploads_dir, hash, conteudo)
  aprovaos/dados/repositorio_edital.py # persistência de concurso/edital/documento/topicos/dna e consultas da página
  aprovaos/dados/repositorio_traco.py  # registrar_traco, gasto_do_dia
  aprovaos/dominio/pdf.py              # validar_pdf, extrair_texto (pypdfium2)
  aprovaos/dominio/edital.py           # parser do conteúdo programático + fatos por regex (FatosEdital)
  aprovaos/dominio/dna.py              # modelos Pydantic do DNA, montar_dna_por_regras, verificar_dna
  aprovaos/roteador/__init__.py · custo.py · teto.py
  aprovaos/agentes/__init__.py · analista_de_edital.py · prompts/analista-de-edital.md
  aprovaos/api/editais.py              # /editais/subir, /editais, /concurso/{id}
  aprovaos/api/templates.py            # + formatar_pct (filtro `pct`)
  tests/conftest.py                    # + uploads_dir por tmp_path; skip `llm`
  tests/test_config.py · test_modelos.py · test_migracoes.py (tocados)
  tests/test_fixture_pdf.py · test_dominio_pdf.py · test_dominio_edital.py · test_dominio_dna.py
        · test_roteador.py · test_analista_de_edital.py · test_analista_adk_llm.py
        · test_repositorio_edital.py · test_rota_subir_edital.py · test_rota_concurso.py · test_rota_editais.py
web/templates/base.html                # nav "Meus editais"
web/templates/conta/conta.html         # link "Meus editais"
web/templates/editais/subir.html · lista.html · concurso.html
web/static/css/base.css                # tabela do verticalizado e barra de %, sem cor literal
knowledge/fixtures/editais/edital-assessor-gabinete.pdf   # gerado uma vez, commitado
scripts/gerar_fixture_pdf.py
.gitignore                             # !knowledge/fixtures/**/*.pdf
.env.example                           # + UPLOADS_DIR, GOOGLE_API_KEY, MODELO_DNA, TETO_DIARIO_BRL
docs/02-produto.md · PENDENCIAS.md · DECISOES.md · 04-modelo-de-dados.md · CLAUDE.md · docs/fatias/V2-execucao.md
```

Todo arquivo novo começa com o cabeçalho de 2 linhas do projeto (CLAUDE.md regra 5).

## 5. Convenções transversais (as da V1 §5 valem integralmente; acréscimos)

- **Red primeiro** em todo passo: `cd backend && uv run pytest tests/<arquivo> -x -q`, ver a falha esperada, implementar o mínimo, depois `uv run ruff check --fix . ../scripts && uv run ruff format . ../scripts && uv run mypy && uv run python ../scripts/checar_import.py && uv run pytest -q`.
- **Sem I/O em import**: `google.adk`/`google.genai` são importados **dentro** de `criar_analista_adk` (import tardio; anotações via `typing.TYPE_CHECKING`); o prompt é lido do disco dentro da fábrica; `pypdfium2` pode ser importado no topo (não abre nada em import).
- **Pydantic em toda fronteira**: `MateriaExtraida`/`TopicoExtraido` (parser → DNA), `FatosEdital`, `DnaConcurso` e submodelos, `ChamadaLlm`, `ResultadoDna`. O template recebe `dict` de `model_dump(mode="json")` e listas de `dict`, nunca ORM.
- **Transação**: repositório faz `add`/`flush`; a rota faz `commit`. O PDF é gravado em disco **antes** do `commit` e o nome do arquivo é o `sha256` do conteúdo (idempotente: subir o mesmo PDF duas vezes reaproveita o arquivo, mas cria concurso novo — ver Q3).
- **Registro de execução**: `docs/fatias/V2-execucao.md`, um bloco por passo (teste, linha do red, linha do green, lint/mypy/import, desvios), como na V1.
- **Marcadores de teste**: `postgres` (V1) e `llm` (novo; pulado sem `GOOGLE_API_KEY`).
- Docs oficiais citadas no passo em que a API é fixada; API que não esteja na doc citada → parar e perguntar.

## 6. Passos

### Passo 1 — Dependências, configuração e `.env.example`
**Objetivo:** `pypdfium2`, `google-adk` e `reportlab` (dev) instalados; quatro configurações novas lidas por fábrica; marker `llm`.
**Arquivos:** `backend/pyproject.toml`, `backend/uv.lock`, `backend/aprovaos/config.py`, `.env.example`, `backend/tests/test_config.py`, `backend/tests/conftest.py`.
**Testes red:**
- `test_config.py::test_configuracoes_da_v2_tem_padroes`: `Configuracoes(database_url="sqlite://", chave_secreta="x"*32, _env_file=None)` → `uploads_dir is None`, `google_api_key is None`, `modelo_dna == "gemini-2.5-flash"`, `teto_diario_brl == Decimal("3.00")`. Falha: `AttributeError`.
- `test_config.py::test_google_api_key_e_secreta`: com `monkeypatch.setenv("GOOGLE_API_KEY", "abc")`, `google_api_key` é `SecretStr` e `repr(cfg)` não contém `abc`.
- `test_env_example.py` (já existe) fica vermelho sozinho: as chaves novas precisam estar no `.env.example`.
**Implementação mínima:**
- `pyproject.toml`: `dependencies += ["pypdfium2", "google-adk"]` (licenças: pypdfium2 BSD-3-Clause/Apache-2.0 — https://pypi.org/project/pypdfium2/ ; google-adk Apache-2.0 — ADR-0018); `dev += ["reportlab"]` (BSD-3-Clause, premissa J). `markers += ["llm: exige GOOGLE_API_KEY (chama o Gemini de verdade)"]` (https://docs.pytest.org/en/stable/how-to/mark.html#registering-marks). `uv sync` e commitar o `uv.lock`. Se `mypy` reclamar `missing library stubs or py.typed` para `pypdfium2`, `google.adk`, `google.genai` ou `reportlab`, adicionar `[[tool.mypy.overrides]] module = [...] ignore_missing_imports = true` **só para esses módulos** (https://mypy.readthedocs.io/en/stable/config_file.html#confval-ignore_missing_imports) e registrar no diário.
- `config.py`: `uploads_dir: Path | None = None`, `google_api_key: SecretStr | None = None`, `modelo_dna: str = "gemini-2.5-flash"`, `teto_diario_brl: Decimal = Decimal("3.00")` (pydantic-settings lê `GOOGLE_API_KEY` pelo nome do campo em maiúsculas — mesma regra dos campos da V1: https://docs.pydantic.dev/latest/concepts/pydantic_settings/#environment-variable-names). Docstring da classe ganha os quatro atributos.
- `.env.example`: `UPLOADS_DIR=` (comentário: vazio = `data/uploads` na raiz; no container `/data/uploads`), `GOOGLE_API_KEY=` (comentário: AI Studio free tier, ADR-0030; vazio = DNA por regras), `MODELO_DNA=gemini-2.5-flash`, `TETO_DIARIO_BRL=3.00`.
- `conftest.py`: o hook `pytest_collection_modifyitems` também pula `llm` sem `GOOGLE_API_KEY` (`reason="defina GOOGLE_API_KEY"`); `config_teste` passa a receber `tmp_path` e define `uploads_dir=tmp_path / "uploads"` (fica `google_api_key=None` → caminho por regras nos testes de rota).
**Pronto quando:** testes verdes; `checar_import.py` verde (os pacotes novos ainda não são importados por nenhum módulo).

### Passo 2 — Modelos ORM da V2 e migração `0002_edital_dna`
**Objetivo:** seis tabelas mapeadas conforme o modelo §3 (colunas da premissa C) e a migração que as reproduz.
**Arquivos:** `aprovaos/dados/modelos.py`, `alembic/versions/0002_edital_dna.py`, `tests/test_modelos.py`, `tests/test_migracoes.py` (sem alteração — fica vermelho sozinho).
**Testes red** (em `test_modelos.py`):
- Alterar `test_tabelas_da_v1` para `test_tabelas`: `set(Base.metadata.tables) == {"tenant","usuario","sessao","traco","concurso","edital","documento","topico","topico_edital","dna_concurso"}`. Falha: faltam 6.
- `test_insere_concurso_edital_documento_topicos_dna`: cria `Tenant`, `Documento(tipo="edital", hash="a"*64, caminho="a.pdf", baixado_em=aware, metadados={"paginas": 1})`, `Concurso(tenant=tenant, orgao="Câmara", cargo="Assessor", banca="desconhecido")`, `Edital(concurso=…, versao=1, documento=…)`, `Topico(materia="direito-administrativo", nome="Licitações", slug="dir-adm-04-licitacoes-contratos")`, `TopicoEdital(edital=…, topico=…, ordem=4, texto_original="4. …", peso_edital=Decimal("3.409"))`, `DnaConcursoRegistro(concurso=…, versao=1, gerado_em=aware, origem="regras", conteudo={"versao": 1})`; após `commit`, `edital.id` é `UUID`, `dna.conteudo["versao"] == 1`, `concurso.tenant_id == tenant.id`.
- `test_concurso_sem_tenant_e_permitido`: `Concurso(tenant_id=None, …)` persiste (catálogo futuro).
- `test_slug_de_topico_unico`: segundo `Topico` com o mesmo `slug` → `IntegrityError`.
- `test_topico_edital_unico_por_edital`: mesmo `(edital_id, topico_id)` duas vezes → `IntegrityError`.
- `test_origem_do_dna_restrita`: `DnaConcursoRegistro(origem="xx")` → `IntegrityError` (CHECK `origem IN ('ia','regras')`).
- `test_migracoes.py::test_migracao_inicial_bate_com_os_modelos` (existente) fica vermelho porque `compare_metadata` passa a listar as 6 tabelas.
**Implementação mínima:**
- `Concurso(ChaveUuid, Carimbos, Base)`: `tenant_id: UUID | None` FK `tenant.id` index; `orgao String(200)`, `cargo String(200)`, `banca String(200)` (valor `"desconhecido"` quando não extraído — nunca `NULL`, para o DNA e a página não terem dois jeitos de dizer "não sei"); `data_prova: date | None` (`sqlalchemy.Date`). `relationship()` `tenant`.
- `Documento(ChaveUuid, Carimbos, Base)`: `tipo String(16)` + CHECK `tipo IN ('prova','gabarito','edital','lei','informativo')`; `hash String(64)` index; `caminho String(255)`; `baixado_em DataHoraUtc`; `metadados JSON` (nullable=False, default `dict`).
- `Edital(ChaveUuid, Carimbos, Base)`: `concurso_id` FK index; `versao Integer` (default 1); `documento_id` FK; `UniqueConstraint("concurso_id","versao")`; relationships `concurso`, `documento`.
- `Topico(ChaveUuid, Carimbos, Base)`: `materia String(120)`, `nome String(255)`, `slug String(120) unique`.
- `TopicoEdital(ChaveUuid, Carimbos, Base)`: `edital_id` FK index, `topico_id` FK, `ordem Integer` (nullable=False; posição do tópico no edital, contada de 1 sobre todas as matérias — é a ordem do verticalizado), `peso_edital Numeric(6,3) | None`, `texto_original Text`; `UniqueConstraint("edital_id","topico_id")`; relationships `edital`, `topico`.
- `DnaConcursoRegistro(ChaveUuid, Carimbos, Base)` com `__tablename__ = "dna_concurso"` (o nome Python evita colidir com o Pydantic `DnaConcurso` de `dominio/dna.py`): `concurso_id` FK index, `versao Integer`, `gerado_em DataHoraUtc`, `origem String(8)` + CHECK, `modelo String(64) | None`, `motivo_fallback Text | None`, `conteudo JSON`; `UniqueConstraint("concurso_id","versao")`.
- Padrão: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html ; `UniqueConstraint` em `__table_args__` (convenção `uq_` de `base.py`).
- Migração: `DATABASE_URL=sqlite:///<scratchpad>/m.db uv run alembic upgrade head && uv run alembic revision --autogenerate -m "edital_dna"`; **revisar** (como na V1: `sa.DateTime(timezone=True)` no lugar de `DataHoraUtc`, `sa.JSON()`, `id` primeiro, nomes de constraint pela convenção), renomear para `0002_edital_dna.py` com `revision = "0002"`, `down_revision = "0001"`.
**Pronto quando:** `test_modelos.py` e `test_migracoes.py` verdes (upgrade e downgrade); `checar_import.py` verde.

### Passo 3 — Fixture PDF: `scripts/gerar_fixture_pdf.py` e `.gitignore`
**Objetivo:** o PDF de teste existe no repositório, gerado por um script reproduzível.
**Arquivos:** `scripts/gerar_fixture_pdf.py`, `knowledge/fixtures/editais/edital-assessor-gabinete.pdf`, `.gitignore`, `tests/test_fixture_pdf.py`.
**Testes red:**
- `test_script_gera_pdf`: `subprocess.run([sys.executable, RAIZ/"scripts/gerar_fixture_pdf.py", RAIZ/"docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md", tmp_path/"e.pdf"], check=False)` → `returncode == 0` e `(tmp_path/"e.pdf").read_bytes().startswith(b"%PDF-")`. Falha: script não existe.
- `test_fixture_pdf_commitada_existe`: `(RAIZ/"knowledge/fixtures/editais/edital-assessor-gabinete.pdf").read_bytes().startswith(b"%PDF-")`.
- `test_gitignore_libera_fixtures_pdf`: `.gitignore` contém a linha `!knowledge/fixtures/**/*.pdf` **depois** da linha `*.pdf` (a ordem importa no gitignore: https://git-scm.com/docs/gitignore — "It is not possible to re-include a file if a parent directory of that file is excluded"; aqui o pai não é excluído, só o padrão `*.pdf`, então a negação funciona).
**Implementação mínima:** script tipado com docstring de módulo e `main()`; lê o `.md`, descarta linhas que começam com `# ` ou `> ` (cabeçalho do fixture), e para cada linha não vazia cria `Paragraph(xml.sax.saxutils.escape(linha), estilo)` com `getSampleStyleSheet()["Normal"]`; `SimpleDocTemplate(str(destino), pagesize=A4).build(paragrafos)` (Platypus: https://docs.reportlab.com/reportlab/userguide/ch5_platypus/ ). Fonte padrão Helvetica cobre acentos pt-BR, `º` e `—` (WinAnsi). Rodar o script uma vez com o destino `knowledge/fixtures/editais/edital-assessor-gabinete.pdf` e commitar. `.gitignore`: acrescentar `!knowledge/fixtures/**/*.pdf` logo após `*.pdf`. Confirmar com `git check-ignore -v knowledge/fixtures/editais/edital-assessor-gabinete.pdf` (deve **não** listar o arquivo).
**Pronto quando:** testes verdes; `git status` mostra o PDF como untracked (não ignorado); `ruff`/`mypy` cobrem `../scripts`.

### Passo 4 — `dominio/pdf.py`: validação e extração de texto com pypdfium2
**Objetivo:** função pura `extrair_texto(conteudo: bytes) -> str` e `validar_pdf(conteudo, content_type)`.
**Arquivos:** `aprovaos/dominio/pdf.py`, `aprovaos/dominio/erros.py` (+ `ArquivoInvalido`, `PdfSemTexto`), `tests/test_dominio_pdf.py`.
**Testes red:**
- `test_extrair_texto_da_fixture`: texto de `knowledge/fixtures/editais/edital-assessor-gabinete.pdf` contém `"CONTEÚDO PROGRAMÁTICO"`, `"LÍNGUA PORTUGUESA"`, `"Lei nº 14.133/2021"` e `"6.2 Distribuição"`; não contém `"\r"`.
- `test_extrair_texto_pdf_sem_texto`: PDF gerado no teste com reportlab só com `Spacer` (sem texto) → `extrair_texto` levanta `PdfSemTexto`.
- `test_extrair_texto_bytes_invalidos`: `b"nao e pdf"` → `ArquivoInvalido`.
- `test_validar_pdf`: `validar_pdf(b"%PDF-1.4 …", "application/pdf")` não levanta; `content_type="image/png"` → `ArquivoInvalido` com mensagem "Envie um arquivo PDF"; `b"x" * (LIMITE_BYTES + 1)` → `ArquivoInvalido` com mensagem contendo "10 MB"; bytes que não começam com `%PDF-` → `ArquivoInvalido`.
**Implementação mínima:** `LIMITE_BYTES = 10 * 1024 * 1024`; `validar_pdf` checa tipo, tamanho e prefixo `%PDF-`. `extrair_texto`: `with pypdfium2.PdfDocument(conteudo) as pdf:` (aceita `bytes`; suporta `with`), `for pagina in pdf:` → `pagina.get_textpage().get_text_range()` (padrão `index=0, count=-1` = todo o texto da página), junta páginas com `"\n"`, troca `"\r\n"`/`"\r"` por `"\n"`; se `texto.strip()` vazio → `PdfSemTexto`; `pypdfium2.PdfiumError` (arquivo corrompido) → `ArquivoInvalido`. Doc: https://pypdfium2.readthedocs.io/en/stable/python_api.html (`PdfDocument`, `PdfPage.get_textpage`, `PdfTextPage.get_text_range`). Sem I/O de disco aqui.
**Pronto quando:** verde; `mypy` OK (override se necessário, passo 1).

### Passo 5 — `dominio/edital.py` (parte 1): parser determinístico do conteúdo programático
**Objetivo:** `extrair_conteudo_programatico(texto) -> list[MateriaExtraida]` sem LLM.
**Arquivos:** `aprovaos/dominio/edital.py`, `aprovaos/dominio/erros.py` (+ `ConteudoProgramaticoNaoEncontrado`), `tests/test_dominio_edital.py`.
**Testes red:**
- `test_parser_fixture_md_36_topicos`: texto = `.md` do fixture lido do disco; resultado tem 7 matérias na ordem `LÍNGUA PORTUGUESA, RACIOCÍNIO LÓGICO, LEGISLAÇÃO MUNICIPAL, DIREITO CONSTITUCIONAL, DIREITO ADMINISTRATIVO, DIREITO CIVIL, DIREITO PROCESSUAL CIVIL`; contagens `[7, 4, 3, 6, 7, 4, 5]`; total 36; `grupo` é `None` para as três primeiras e `"CONHECIMENTOS ESPECÍFICOS"` para as quatro últimas; o item 4 de Direito Administrativo tem `numero == 4` e `texto_original == "4. Licitações e contratos — Lei nº 14.133/2021."` (o `14.133` não quebra a numeração).
- `test_parser_fixture_pdf_36_topicos`: mesmo resultado com o texto vindo de `extrair_texto(pdf)` — linhas quebradas pelo `Paragraph` são reunidas.
- `test_item_quebrado_em_duas_linhas` (sintético): `"CONTEÚDO PROGRAMÁTICO\nDIREITO CIVIL: 1. Lei de Introdução às\nNormas do Direito Brasileiro. 2. Pessoas\nnaturais e jurídicas."` → 1 matéria, 2 tópicos, `texto_original` do item 1 == `"1. Lei de Introdução às Normas do Direito Brasileiro."`.
- `test_materia_sem_dois_pontos` (sintético): `"CONTEÚDO PROGRAMÁTICO\nDIREITO TRIBUTÁRIO 1. Tributos. 2. Competência tributária."` → matéria `DIREITO TRIBUTÁRIO` com 2 tópicos.
- `test_sem_conteudo_programatico`: texto sem o marcador → `ConteudoProgramaticoNaoEncontrado`.
- `test_slugs`: `slug_materia("LÍNGUA PORTUGUESA") == "lingua-portuguesa"`; `prefixo_materia("DIREITO ADMINISTRATIVO") == "dir-adm"`; `slug_topico("DIREITO ADMINISTRATIVO", 4, "4. Licitações e contratos — Lei nº 14.133/2021.") == "dir-adm-04-licitacoes-contratos"`; `slug_topico("LÍNGUA PORTUGUESA", 1, "1. Compreensão e interpretação de textos.") == "lin-por-01-compreensao-interpretacao"`; todo slug casa `^[a-z]{1,3}(-[a-z]{1,3})*-\d{2}-[a-z0-9]+(-[a-z0-9]+)?$`.
**Implementação mínima:**
- Modelos: `TopicoExtraido(numero: int, texto_original: str, slug: str)`, `MateriaExtraida(nome: str, slug: str, grupo: str | None, topicos: list[TopicoExtraido])`.
- Algoritmo (documentado na docstring): (1) localizar o início por `re.search(r"CONTE[ÚU]DO PROGRAM[ÁA]TICO", texto, re.IGNORECASE)`; recorte até o próximo `^ANEXO\s` (linha) ou fim; (2) percorrer linhas: **cabeçalho de matéria** = linha cujo início casa `^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]{2,}?)\s*:\s*(.*)$` **ou** `^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]{2,}?)\s+(1\.\s.*)$` (sem dois-pontos); cabeçalho com resto vazio e sem item = **grupo** (vale para as matérias seguintes até o fim ou o próximo grupo); qualquer outra linha = continuação do texto da matéria atual, unida com espaço; (3) itens por numeração **sequencial**: procurar `\b1\.\s`, depois `\b2\.\s` a partir do fim do anterior, etc.; o texto de cada item vai até o começo do próximo; `texto_original` = item sem espaços nas pontas. Sem `\d+\.` genérico (quebraria em `14.133`).
- Slugs conforme premissa E (`unicodedata`, lista de palavras não significativas, `re.sub(r"[^a-z0-9]+", "-", …)`).
**Pronto quando:** verde; a função é pura (sem `print`, sem I/O); `mypy` OK.

### Passo 6 — `dominio/edital.py` (parte 2): fatos do edital por regex (`FatosEdital`)
**Objetivo:** extrair, com fonte (número do parágrafo), o que o DNA por regras precisa: distribuição, regra de correção, cabeçalho e etapas.
**Arquivos:** `aprovaos/dominio/edital.py`, `tests/test_dominio_edital.py`.
**Testes red** (texto = `.md` do fixture, salvo onde indicado):
- `test_distribuicao`: `fatos.distribuicao == [("Língua Portuguesa", 10, 1.0), ("Raciocínio Lógico", 5, 1.0), ("Legislação Municipal", 5, 1.0), ("Conhecimentos Específicos", 30, 2.0)]` (como `DistribuicaoMateria(nome, questoes, peso_questao, fonte="edital §6.2")`).
- `test_distribuicao_ausente`: texto sem "questões … peso" → `fatos.distribuicao == []`.
- `test_regra_correcao`: `tipo_item == "multipla_escolha"`, `alternativas == 5`, `anula_por_erro is False` ("sem desconto"), `minimo_global == "50 % do total de pontos"`, `minimo_por_materia == "nota zero elimina"`, `fonte == "edital §6.1, §6.3"`.
- `test_regra_correcao_certo_errado`: sintético "itens do tipo CERTO ou ERRADO … uma resposta errada anula uma certa" → `certo_errado`, `alternativas is None`, `anula_por_erro is True`.
- `test_regra_desconhecida`: texto sem nada disso → `tipo_item == "desconhecido"`, `anula_por_erro == "desconhecido"`, `minimo_* == "desconhecido"`.
- `test_cabecalho`: `orgao == "CÂMARA MUNICIPAL DE CASCAVEL — ESTADO DO PARANÁ"` (primeira linha não vazia em caixa alta que não começa por `EDITAL` nem `#`/`>`), `cargo == "ASSESSOR DE GABINETE"`, `banca == "FUNDAÇÃO DE APOIO À UNIOESTE"`, `edital == "01/2026"`, `data_prova == date(2026, 11, 15)`, `fonte == "edital §1.1, §1.2, §6.5"`; sintético sem esses trechos → `"desconhecido"`/`None` em cada campo.
- `test_etapas`: `[Etapa(nome="objetiva", pontos=80, quem_faz=None, fonte="edital §6.2"), Etapa(nome="discursiva", pontos=20, quem_faz="60 primeiros", fonte="edital §6.4")]`.
**Implementação mínima:** `extrair_fatos(texto) -> FatosEdital` com submodelos `DistribuicaoMateria`, `RegraExtraida`, `CabecalhoExtraido`, `Etapa`. Regex (todas `re.IGNORECASE` onde fizer sentido; `Desconhecido = Literal["desconhecido"]`):
| fato | regex / regra | fonte |
|---|---|---|
| distribuição | por ocorrência de `([A-Za-zÀ-ú ]+?)\s*[—–-]\s*(\d+)\s+quest(?:ões|oes)\s*,?\s*peso\s+(\d+(?:[.,]\d+)?)` na linha que contém "Distribuição" ou na que casar primeiro; vírgula decimal → ponto | `§` da linha (`^(\d+(?:\.\d+)*)\s`) |
| tipo_item | `múltipla escolha` → `multipla_escolha`; `certo` … `errado` (mesma linha) → `certo_errado` | linha |
| alternativas | `(\d+)\s+alternativas` | linha |
| anula_por_erro | `sem desconto` \| `não haverá desconto` → `False`; `anula` \| `desconto` → `True`; senão `"desconhecido"` | linha |
| minimo_global | `(\d+)\s*%\s*do total(?: de pontos)?` → `"N % do total de pontos"` | linha |
| minimo_por_materia | `nota zero` → `"nota zero elimina"` | linha |
| cargo | `Cargo:\s*([^.]+)\.` | linha |
| banca | `executad[oa] pel[ao]\s+(.+?)\s*\(banca` ou `banca organizadora[:\s]+(.+?)[.,]` | linha |
| edital | `EDITAL[^\n]*?N[ºo°.]?\s*(\d+/\d{4})` | "edital (cabeçalho)" |
| data_prova | `[Dd]ata (?:provável )?da prova[^\d]*(\d{2}/\d{2}/\d{4})` → `date` | linha |
| etapa objetiva | `pontos = Σ questoes × peso_questao` da distribuição (80); sem distribuição → `"desconhecido"` | fonte da distribuição |
| etapa discursiva | `[Pp]rova discursiva[^.]*?peso\s+(\d+)\s+pontos`; `quem_faz` = `(\d+)\s+primeiros` → `"60 primeiros"` | linha |
`fonte` = `"edital §" + ", §".join(números das linhas casadas)`; linha sem número → `"edital (trecho sem numeração)"`. Docs: https://docs.python.org/3.13/library/re.html .
**Pronto quando:** verde; nenhuma regex "genérica" além das da tabela (o revisor confere).

### Passo 7 — `dominio/dna.py`: modelos do `DnaConcurso`, `montar_dna_por_regras`, `verificar_dna`
**Objetivo:** o contrato JSON da skill como Pydantic e o DNA reduzido calculado por regras.
**Arquivos:** `aprovaos/dominio/dna.py`, `tests/test_dominio_dna.py`.
**Testes red:**
- `test_dna_valida_o_exemplo_da_skill`: o JSON de exemplo de `SKILL.md` (copiado literalmente para o teste, com `pct_uniforme` numérico) passa em `DnaConcurso.model_validate_json` e `model_dump(mode="json")` devolve as chaves **nesta ordem**: `concurso, regra_correcao, etapas, pesos, topicos_edital, incidencia, estilo, pegadinhas, corte, lacunas, fontes, versao`.
- `test_montar_dna_por_regras_fixture`: `dna = montar_dna_por_regras(texto_md, materias)` → `pesos.materia` tem 4 chaves `lingua-portuguesa, raciocinio-logico, legislacao-municipal, conhecimentos-especificos` com `pct_pontos` `12.5, 6.25, 6.25, 75.0` e `pontos` `10, 5, 5, 60`; `fonte == "edital §6.2"` em cada uma; `etapas[0].pontos == 80`; `pesos.topico["dir-adm-04-licitacoes-contratos"] == PesoTopico(pct_pontos="desconhecido", metodo="uniforme_no_edital", pct_uniforme=pytest.approx(75/22, abs=0.01))`; `pesos.topico["lin-por-01-compreensao-interpretacao"].pct_uniforme == pytest.approx(12.5/7, abs=0.01)`; `len(topicos_edital) == 36` e `topicos_edital[0].fonte == "edital Anexo I"`; `regra_correcao.minimo_global == "50 % do total de pontos (40 de 80)"`; `regra_correcao.minimo_por_materia == "nota zero elimina"`; `concurso.data_prova == date(2026, 11, 15)`; `incidencia.provas_analisadas == 0`; `corte.lo == "desconhecido"`; `pegadinhas == []`; `lacunas` contém (busca por substring, sem acento) `"incidencia"`, `"estilo"`, `"corte"`, `"pegadinhas"`; `fontes == ["edital 01/2026 (arquivo subido)"]`; `versao == 1`.
- `test_soma_dos_pct_uniforme_e_100`: `sum(t.pct_uniforme for t in pesos.topico.values()) == pytest.approx(100)`.
- `test_montar_dna_sem_distribuicao`: texto do fixture sem a linha 6.2 → cada `pesos.materia[*]` tem `questoes == "desconhecido"`, `peso_questao == 1.0`, `fonte == "edital omisso — assumido 1,0"`, `pct_pontos == "desconhecido"`; todo `pesos.topico[*].pct_uniforme == "desconhecido"`; `lacunas` contém `"distribuicao"`.
- `test_montar_dna_com_materia_fora_da_distribuicao`: distribuição lista "Informática" que não existe no conteúdo → `pesos.materia["informatica"]` presente e `lacunas` contém `"informatica"`.
- `test_verificar_dna_aprova_o_das_regras`: `verificar_dna(dna, materias) == []`.
- `test_verificar_dna_reprova`: (1) `pct_pontos` de LP trocado para 20 → mensagem contém `"soma"`; (2) `fonte=""` numa matéria → contém `"sem fonte"`; (3) `lacunas=[]` → contém `"lacuna"`; (4) um item removido de `topicos_edital` → contém `"cobertura"` e `"35 de 36"`.
**Implementação mínima:**
- `Desconhecido = Literal["desconhecido"]`. Modelos (campos e ordem **exatamente** os da skill): `ConcursoDna(orgao, cargo, banca: str, edital: str, data_prova: date | Desconhecido, fonte: str)`; `RegraCorrecao(tipo_item: Literal["certo_errado","multipla_escolha"] | Desconhecido, alternativas: int | None, anula_por_erro: bool | Desconhecido, minimo_por_materia: str, minimo_global: str, fonte: str)`; `EtapaDna(nome: str, pontos: float | Desconhecido, quem_faz: str | None = None, fonte: str)`; `PesoMateria(questoes: int | Desconhecido, peso_questao: float, pontos: float | Desconhecido, pct_pontos: float | Desconhecido, fonte: str)`; `PesoTopico(pct_pontos: float | Desconhecido, metodo: str, pct_uniforme: float | Desconhecido)`; `Pesos(materia: dict[str, PesoMateria], topico: dict[str, PesoTopico])`; `TopicoEditalDna(slug, materia, texto_original, fonte)`; `Incidencia(por_topico: dict[str, float] | Desconhecido, provas_analisadas: int, fonte: str)`; `Estilo(tipo_item: … | Desconhecido, alternativas: int | None, caracteristicas: str, fonte: str)`; `Pegadinha(descricao, banca, ano: int, item: str)`; `Corte(lo: float | Desconhecido, hi: float | Desconhecido, fonte: str)`; `DnaConcurso(concurso, regra_correcao, etapas: list[EtapaDna], pesos, topicos_edital: list[TopicoEditalDna], incidencia, estilo, pegadinhas: list[Pegadinha], corte, lacunas: list[str], fontes: list[str], versao: int)`. Docs: https://docs.pydantic.dev/latest/concepts/models/ ; `Literal`: https://docs.pydantic.dev/latest/api/standard_library_types/#literal .
- `montar_dna_por_regras(texto, materias)`: chama `extrair_fatos`; **matéria de prova** = nome da distribuição casado (sem acento, casefold) com `MateriaExtraida.nome` ou `.grupo`; `pct_pontos = pontos / Σ pontos × 100`; `pct_uniforme` do tópico = `pct_pontos` da matéria de prova ÷ nº de tópicos que ela agrupa (LP 7; CE 22). `lacunas` = sempre `["incidência por tópico", "estilo da banca", "corte histórico", "pegadinhas"]` + `"banca"` se desconhecida + `"data da prova"` + `"distribuição de questões por matéria"` + `"matéria <x> da distribuição sem conteúdo programático"` + `"peso de <matéria>: sem linha na distribuição"` conforme o caso. `estilo.fonte = "<fonte da regra>; sem provas"`, `incidencia.fonte = "nenhuma prova da banca na base"`, `corte.fonte = "sem provas/resultados anteriores"`.
- `verificar_dna(dna, materias) -> list[str]`: (1) se todos `pct_pontos` conhecidos, `abs(Σ − 100) ≤ 0.01`; (2) `fonte` não vazia em `concurso`, `regra_correcao`, cada etapa, cada `pesos.materia`, `incidencia`, `estilo`, `corte`, cada pegadinha, **e** começa por `edital` ou `prova ` ou `sem provas` ou `nenhuma prova` (regra 2 da skill); (3) para cada valor `"desconhecido"` em `concurso.banca`, `concurso.data_prova`, `regra_correcao.*`, `corte.*`, `incidencia.por_topico`, `estilo.caracteristicas`, `pesos.materia[*].pct_pontos` existe uma lacuna cujo texto normalizado contém a palavra-chave correspondente (`banca`, `data`, `correcao`, `corte`, `incidencia`, `estilo`, `distribuicao`); (4) `{t.slug for t in dna.topicos_edital} == {slug de todos os tópicos de materias}` e `len(dna.topicos_edital) == total`, senão `"cobertura: N de M tópicos"`.
**Pronto quando:** verde; `mypy` OK; nenhum número inventado (o revisor confere contra a tabela "Regras de cálculo" da skill).

### Passo 8 — Roteador mínimo: custo, teto diário e `traco`
**Objetivo:** estimar custo em R$, somar o gasto do dia e gravar uma linha em `traco` por chamada.
**Arquivos:** `aprovaos/roteador/__init__.py`, `aprovaos/roteador/custo.py`, `aprovaos/roteador/teto.py`, `aprovaos/dados/repositorio_traco.py`, `tests/test_roteador.py`.
**Testes red:**
- `test_estimar_custo_flash`: `estimar_custo_brl("gemini-2.5-flash", 60_000, 8_000) == Decimal("0.205200")` (0,018 + 0,020 US$ × 5,40).
- `test_estimar_custo_flash_lite`: `("gemini-2.5-flash-lite", 1_000_000, 0) == Decimal("0.540000")`.
- `test_modelo_sem_preco`: `"gemini-x"` → `ModeloSemPreco`.
- `test_registrar_traco_grava_linha` (fixture `db`): `registrar_traco(db, ChamadaLlm(...), usuario_id=usuario.id)`; a linha tem `agente == "analista-de-edital"`, `modelo`, `tokens_in`, `tokens_out`, `custo_brl`, `duracao_ms`, `resultado == "ok"`, `usuario_id`.
- `test_gasto_do_dia`: três linhas em `traco` (duas hoje com `custo_brl` 1,20 e 0,50; uma ontem com 9,00) → `gasto_do_dia(db, agora) == Decimal("1.70")`; `custo_brl=None` conta como zero.
- `test_teto_diario`: `TetoDiario(Decimal("3.00")).pode_chamar(db, agora)` é `True` com 1,70 gasto e `False` após mais uma linha de 1,40 (total 3,10); `limite_brl=Decimal("0")` → sempre `False`.
**Implementação mínima:** `custo.py`: `PRECOS_USD_POR_MILHAO: dict[str, tuple[Decimal, Decimal]] = {"gemini-2.5-flash": (Decimal("0.30"), Decimal("2.50")), "gemini-2.5-flash-lite": (Decimal("0.10"), Decimal("0.40"))}` e `CAMBIO_BRL_POR_USD = Decimal("5.40")` com comentário citando `docs/06-custos.md` linhas 9–11 (fonte oficial https://ai.google.dev/gemini-api/docs/pricing , 14/09/2026); `estimar_custo_brl` devolve `Decimal` quantizado em 6 casas (`Decimal.quantize`, https://docs.python.org/3.13/library/decimal.html). `ChamadaLlm(BaseModel)` em `roteador/custo.py`: `agente: str, modelo: str, iniciado_em: datetime, duracao_ms: int, tokens_in: int | None, tokens_out: int | None, custo_brl: Decimal | None, resultado: Literal["ok","erro"], erro: str | None = None`. `repositorio_traco.py`: `registrar_traco(db, chamada, usuario_id) -> Traco` (`add`+`flush`); `gasto_do_dia(db, agora) -> Decimal` = `select(func.coalesce(func.sum(Traco.custo_brl), 0)).where(Traco.iniciado_em >= inicio_do_dia_utc)` (https://docs.sqlalchemy.org/en/20/core/functions.html). `teto.py`: `class TetoDiario` com `limite_brl` e `pode_chamar(db, agora) -> bool` (`gasto_do_dia(db, agora) < limite_brl`).
**Pronto quando:** verde; `Decimal` em todo lugar (sem `float` em dinheiro).

### Passo 9 — Agente `analista-de-edital`: porta, `AnalistaPorRegras`, orquestração com fallback e prompt
**Objetivo:** a porta `Protocol`, a implementação por regras, `gerar_dna` (IA → verificação → fallback) e o prompt em arquivo.
**Arquivos:** `aprovaos/agentes/__init__.py`, `aprovaos/agentes/analista_de_edital.py`, `aprovaos/agentes/prompts/analista-de-edital.md`, `tests/test_analista_de_edital.py`.
**Testes red** (com dublês: `AnalistaFalso(dna)` devolve o DNA dado; `AnalistaQueEstoura` levanta `RuntimeError("timeout")`; `materias` e `texto` do fixture):
- `test_analista_por_regras_e_uma_implementacao_da_porta`: `isinstance(AnalistaPorRegras(), AnalistaDeEdital)` (Protocol `@runtime_checkable`, https://docs.python.org/3.13/library/typing.html#typing.runtime_checkable) e `await AnalistaPorRegras().analisar(texto, materias)` é `DnaConcurso` igual a `montar_dna_por_regras(texto, materias)`. (Testes `async` com `pytest.mark.anyio` — o `anyio` já vem com o Starlette: https://anyio.readthedocs.io/en/stable/testing.html ; fixture `anyio_backend` fixa `"asyncio"`.)
- `test_gerar_dna_sem_ia_usa_regras`: `gerar_dna(texto, materias, analista_ia=None, motivo_sem_ia="sem GOOGLE_API_KEY")` → `origem == "regras"`, `motivo_fallback == "sem GOOGLE_API_KEY"`.
- `test_gerar_dna_com_ia_aprovada`: `AnalistaFalso(dna_bom)` → `origem == "ia"`, `motivo_fallback is None`, `dna == dna_bom`.
- `test_gerar_dna_ia_reprovada_cai_para_regras`: `AnalistaFalso(dna_com_pct_20)` → `origem == "regras"`, `motivo_fallback` começa com `"DNA da IA reprovado: "` e cita `"soma"`.
- `test_gerar_dna_ia_estoura_cai_para_regras`: `AnalistaQueEstoura` → `origem == "regras"`, `motivo_fallback == "erro na IA: RuntimeError"` (tipo, não a mensagem — sem vazar detalhe).
- `test_prompt_existe_e_transcreve_a_skill`: `carregar_prompt()` devolve texto contendo `"Peso real é por pontos"`, `"uniforme_no_edital"`, `"desconhecido"` e `"edital omisso — assumido 1,0"`, e **não** contém `{` de placeholder não resolvido além do exemplo JSON (o prompt é estático; os dados vão na mensagem do usuário).
- `test_mensagem_lista_os_36_slugs`: `montar_mensagem(texto, materias)` contém o texto do edital e as 36 linhas `slug | materia | texto_original`.
**Implementação mínima:** `AnalistaDeEdital(Protocol)` (premissa F); `AnalistaPorRegras`; `ResultadoDna(BaseModel)`: `dna: DnaConcurso`, `origem: Literal["ia","regras"]`, `motivo_fallback: str | None`; `async def gerar_dna(texto, materias, analista_ia, motivo_sem_ia) -> ResultadoDna` com o fluxo dos testes (o `except Exception` é deliberado e comentado: qualquer falha do provedor degrada para regras — arquitetura §8 "nunca bloquear"); `carregar_prompt() -> str` lê `Path(__file__).parent / "prompts" / "analista-de-edital.md"` (chamada só pela fábrica do passo 10). Prompt: cabeçalho de 2 linhas, papel, as tabelas "Regras de cálculo", "Lacunas" e "Verificação" da skill transcritas, o JSON de exemplo, e a instrução "use exatamente os slugs fornecidos; devolva só o JSON". `montar_mensagem(texto, materias) -> str` (texto do edital + lista `slug | materia | texto_original`).
**Pronto quando:** verde; `checar_import.py` verde (nenhum import de `google.*` ainda).

### Passo 10 — `AnalistaAdk`: `LlmAgent` + `Runner` atrás da fábrica; teste `llm`
**Objetivo:** a implementação real da porta, criada só por `criar_analista_adk(config, registrar_chamada)`.
**Arquivos:** `aprovaos/agentes/analista_de_edital.py`, `tests/test_analista_de_edital.py`, `tests/test_analista_adk_llm.py`.
**Testes red:**
- `test_interpretar_resposta_valida`: `interpretar_resposta(json_da_skill)` → `DnaConcurso`; `interpretar_resposta("{}")` → `pydantic.ValidationError`; `interpretar_resposta("```json\n{...}\n```")` → aceita (remove cerca de código, defesa barata).
- `test_criar_analista_adk_exige_chave`: `criar_analista_adk(config_sem_chave, lambda c: None)` → `ValueError("GOOGLE_API_KEY ausente")`.
- `test_analista_adk_llm.py::test_dna_real_do_fixture` (`@pytest.mark.llm`, pulado sem chave): `chamadas: list[ChamadaLlm] = []`; `analista = criar_analista_adk(config_com_chave, chamadas.append)`; `dna = await analista.analisar(texto_pdf, materias)`; `verificar_dna(dna, materias) == []` **ou** o teste imprime os problemas e falha com eles (é o que o piloto precisa saber); `len(chamadas) == 1`, `chamadas[0].tokens_in > 0`, `custo_brl > 0`, `modelo == config.modelo_dna`.
**Implementação mínima (dentro da fábrica, imports tardios):**
- `from google.adk.agents import LlmAgent`; `from google.adk.runners import Runner`; `from google.adk.sessions import InMemorySessionService`; `from google.adk.models.google_llm import Gemini`; `from google import genai`; `from google.genai import types`.
- Antes de codar, **confirmar no pacote instalado** (registrar a saída no diário): `uv run python -c "from google.adk.models.google_llm import Gemini; print('client' in Gemini.model_fields)"` → premissa I.
- `modelo = Gemini(model=config.modelo_dna, client=genai.Client(api_key=config.google_api_key.get_secret_value()))` (python-genai: https://googleapis.github.io/python-genai/ , "client = genai.Client(api_key=…)"); `agente = LlmAgent(name="analista_de_edital", model=modelo, instruction=carregar_prompt(), output_schema=DnaConcurso, include_contents="none", generate_content_config=types.GenerateContentConfig(temperature=0.2))` — com `output_schema` **não** há `tools` (https://adk.dev/agents/llm-agents/ ); `servico = InMemorySessionService()`; `runner = Runner(agent=agente, app_name="aprovaos", session_service=servico)`.
- `AnalistaAdk.analisar`: `sessao = await servico.create_session(app_name="aprovaos", user_id="analista", session_id=str(uuid4()))`; `t0 = perf_counter()`; `async for evento in runner.run_async(user_id=…, session_id=…, new_message=types.Content(role="user", parts=[types.Part(text=montar_mensagem(texto, materias))]))`: se `evento.is_final_response()` guarda `evento.content.parts[0].text` e `evento.usage_metadata` (`prompt_token_count`, `candidates_token_count` — https://googleapis.github.io/python-genai/genai.html#genai.types.GenerateContentResponseUsageMetadata ); ao sair, `registrar_chamada(ChamadaLlm(agente="analista-de-edital", modelo=config.modelo_dna, iniciado_em, duracao_ms, tokens_in, tokens_out, custo_brl=estimar_custo_brl(...), resultado="ok"))` e devolve `interpretar_resposta(texto)`; em exceção, registra `resultado="erro", erro=type(exc).__name__` e relança (o fallback é do `gerar_dna`).
- Se o Gemini/ADK rejeitar o esquema por causa dos `dict[str, …]` de `pesos`/`incidencia` (risco §8), **parar**: registrar o erro literal no diário e abrir a Q4 com o dono. Plano B (só com aprovação): sem `output_schema`, `generate_content_config=GenerateContentConfig(response_mime_type="application/json")` e o esquema descrito no prompt.
**Pronto quando:** testes unitários verdes; `checar_import.py` verde (importar `aprovaos.agentes.analista_de_edital` não importa `google.*`); o teste `llm` verde com chave real **uma vez**, com a saída (tokens, custo, problemas de `verificar_dna`) colada no diário.

### Passo 11 — Repositório de edital e armazenamento do PDF
**Objetivo:** persistir o resultado do pipeline e consultar o que as páginas mostram.
**Arquivos:** `aprovaos/dados/arquivos.py`, `aprovaos/dados/repositorio_edital.py`, `tests/test_repositorio_edital.py`.
**Testes red** (fixture `db`; `tenant` e `usuario` criados por `criar_conta`):
- `test_guardar_pdf_cria_pasta_e_arquivo`: `caminho = guardar_pdf(tmp_path/"u", "ab"*32, b"%PDF-…")` → `caminho == tmp_path/"u"/"abab…ab.pdf"` existe; chamar de novo com o mesmo hash não reescreve (`mtime` igual) e devolve o mesmo caminho.
- `test_registrar_edital_cria_tudo`: `concurso = registrar_edital(db, tenant_id, resultado_dna, materias, documento=DadosDocumento(hash, caminho_relativo, nome_original, tamanho, paginas))` → existe 1 `Concurso` (orgao/cargo/banca/data_prova vindos de `dna.concurso`; `data_prova` `None` quando `"desconhecido"`), 1 `Edital(versao=1)`, 1 `Documento(tipo="edital")`, 36 `Topico`, 36 `TopicoEdital` (com `ordem` 1…36 na sequência do edital, `peso_edital == pct_uniforme` arredondado a 3 casas e `texto_original`), 1 `DnaConcursoRegistro(origem, modelo, motivo_fallback, conteudo == dna.model_dump(mode="json"))`.
- `test_registrar_edital_reaproveita_topico_por_slug`: registrar dois editais com as mesmas matérias → 36 `Topico` (não 72) e 72 `TopicoEdital`.
- `test_listar_concursos_do_tenant`: dois concursos do tenant A e um do B → `listar_concursos_do_tenant(db, A)` devolve 2, o mais recente primeiro; `concurso_principal(db, A)` é o mais recente; `concurso_principal(db, C_sem_nada) is None`.
- `test_buscar_concurso_e_verticalizado`: `buscar_concurso(db, id)` devolve o `Concurso`; `dna_atual(db, concurso_id)` devolve o `DnaConcursoRegistro` de maior `versao`; `verticalizado(db, edital_id)` devolve `list[MateriaVerticalizada(nome, slug, topicos=[TopicoVerticalizado(slug, texto_original, status="não visto")])]` com 7 matérias e 36 tópicos ordenados por `ordem`.
**Implementação mínima:** `guardar_pdf(uploads_dir: Path, hash: str, conteudo: bytes) -> Path` (`mkdir(parents=True, exist_ok=True)`; `write_bytes` só se não existir; https://docs.python.org/3.13/library/pathlib.html). `DadosDocumento(BaseModel)`. `registrar_edital` (add/flush; commit é da rota); get-or-create de `Topico` por `slug` (`select(Topico).where(Topico.slug == slug)`); `ordem` = contador de 1 a N na sequência matéria → item. `MateriaVerticalizada`/`TopicoVerticalizado` são Pydantic (fronteira dados → template); `status` fixo `"não visto"` na V2 (V3 lê eventos).
**Pronto quando:** verde; nenhum `commit` no repositório.

### Passo 12 — Rotas `GET/POST /editais/subir` e template `editais/subir.html`
**Objetivo:** o formulário multipart que roda o pipeline inteiro e redireciona para o concurso.
**Arquivos:** `aprovaos/api/editais.py`, `aprovaos/main.py`, `web/templates/editais/subir.html`, `tests/test_rota_subir_edital.py`.
**Testes red** (login por `POST /cadastro` na fixture; `PDF = fixture commitada`):
- `test_get_subir_sem_login_redireciona`: 303 → `/entrar`.
- `test_get_subir`: 200; `<form` com `method="post"`, `enctype="multipart/form-data"`, `hx-post="/editais/subir"`, `hx-encoding="multipart/form-data"`, `hx-select="#form-edital"`, `hx-target="#form-edital"`, `hx-swap="outerHTML"`, `<input type="file" name="arquivo" accept="application/pdf" required>`.
- `test_post_subir_cria_concurso_e_redireciona`: `cliente.post("/editais/subir", files={"arquivo": ("edital.pdf", PDF, "application/pdf")})` → 303, `Location` casa `^/concurso/[0-9a-f-]{36}$`; no `db`: 1 `Concurso` do tenant do usuário, 36 `TopicoEdital`, 1 `DnaConcursoRegistro(origem="regras", motivo_fallback="sem GOOGLE_API_KEY")`; o arquivo `<sha256>.pdf` existe em `config_teste.uploads_dir`; zero linhas em `traco` (premissa L).
- `test_post_subir_htmx`: com `HX-Request: true` → 200 e `HX-Redirect: /concurso/<id>`.
- `test_post_subir_nao_pdf`: `("foto.png", b"\x89PNG…", "image/png")` → 200, HTML contém "Envie um arquivo PDF"; nada criado.
- `test_post_subir_grande`: 10 MB + 1 byte começando com `%PDF-` → 200, contém "10 MB".
- `test_post_subir_sem_conteudo_programatico`: PDF gerado no teste (reportlab) com "OLÁ" → 200, contém "conteúdo programático"; nada criado.
- `test_post_subir_usa_ia_quando_ha_chave_e_teto` (dublê): `app` criada com `config_teste.model_copy(update={"google_api_key": SecretStr("x")})` e `monkeypatch.setattr(editais, "criar_analista_adk", lambda config, registrar: AnalistaFalso(dna_bom, registrar))` (o dublê chama `registrar(ChamadaLlm(...))` uma vez) → `origem="ia"`, `modelo="gemini-2.5-flash"`, 1 linha em `traco` com `usuario_id` do usuário e `custo_brl` do dublê.
- `test_post_subir_teto_estourado_usa_regras`: mesma app com chave; antes, gravar em `traco` uma linha de hoje com `custo_brl=Decimal("3.00")` → `origem="regras"`, `motivo_fallback == "teto diário atingido"`, e o `criar_analista_adk` monkeypatchado **não** é chamado.
**Implementação mínima:**
- `main.py`: `uploads_dir = config.uploads_dir or Path(__file__).resolve().parents[2] / "data" / "uploads"` em `app.state.uploads_dir` (sem `mkdir` aqui); `app.include_router(editais.router)`.
- `api/editais.py`: `router = APIRouter(include_in_schema=False)`; `GET /editais/subir` (`exigir_usuario`) renderiza `{"erros": []}`. `POST /editais/subir` `async def` com `arquivo: Annotated[UploadFile, File()]` (https://fastapi.tiangolo.com/tutorial/request-files/ ; `python-multipart` já está instalado), `usuario = exigir_usuario`, `db = obter_db`: (1) `conteudo = await arquivo.read(LIMITE_BYTES + 1)` (`UploadFile.read(size)` — mesma doc); (2) `validar_pdf(conteudo, arquivo.content_type or "")`; (3) `texto = extrair_texto(conteudo)`; (4) `materias = extrair_conteudo_programatico(texto)`; (5) escolha do analista: `if config.google_api_key is None: analista=None, motivo="sem GOOGLE_API_KEY"` / `elif not TetoDiario(config.teto_diario_brl).pode_chamar(db, agora_utc()): analista=None, motivo="teto diário atingido"` / senão `analista = criar_analista_adk(config, lambda chamada: registrar_traco(db, chamada, usuario_id=usuario.id))`; (6) `resultado = await gerar_dna(texto, materias, analista, motivo)`; (7) `hash = hashlib.sha256(conteudo).hexdigest()`; `caminho = guardar_pdf(request.app.state.uploads_dir, hash, conteudo)`; (8) `concurso = registrar_edital(db, usuario.tenant_id, resultado, materias, DadosDocumento(...))`; `db.commit()`; (9) `responder_redirecionamento(request, f"/concurso/{concurso.id}")`. `except (ArquivoInvalido, PdfSemTexto, ConteudoProgramaticoNaoEncontrado) as erro:` → re-renderiza com `str(erro)` (mensagens pt-BR definidas nas exceções). Sem `try` genérico: erro inesperado vira 500 JSON (V1).
- `subir.html`: extende `base.html`; `<form id="form-edital" … hx-encoding="multipart/form-data">` (https://htmx.org/attributes/hx-encoding/ ); lista de erros como em `cadastro.html`; texto de ajuda "PDF de até 10 MB com o conteúdo programático".
**Pronto quando:** verde; no navegador (`uvicorn … --factory --reload`, `.env` sem chave), subir a fixture leva a `/concurso/{id}` (que ainda dá 404 JSON até o passo 13 — aceitável).

### Passo 13 — Rota `GET /concurso/{id}`: DNA reduzido + edital verticalizado
**Objetivo:** a página que a aluna vê; só o dono do tenant acessa.
**Arquivos:** `aprovaos/api/editais.py`, `aprovaos/api/templates.py`, `aprovaos/main.py`, `web/templates/editais/concurso.html`, `web/static/css/base.css`, `tests/test_rota_concurso.py`.
**Testes red** (fixture: usuário logado + concurso criado via `POST /editais/subir` na própria fixture):
- `test_concurso_sem_login_redireciona`: 303 → `/entrar`.
- `test_concurso_inexistente_404_json`: `uuid4()` aleatório → 404, `codigo == "nao_encontrado"`.
- `test_concurso_de_outro_tenant_403_json`: segundo cliente com outra conta → 403, `codigo == "proibido"`.
- `test_concurso_id_invalido`: `/concurso/abc` → 422 JSON `dados_invalidos` (comportamento natural do parâmetro `UUID` + tratador da V1; ver Q5).
- `test_concurso_mostra_dna_reduzido`: 200; contém `"CÂMARA MUNICIPAL DE CASCAVEL"`, `"ASSESSOR DE GABINETE"`, `"Língua Portuguesa"` (nome de exibição = nome da `MateriaExtraida`/grupo cujo slug bate com a chave de `pesos.materia`, em Title Case; se nenhum bater, o próprio slug), `"12,5 %"`, `"75 %"`, `"50 % do total de pontos (40 de 80)"`, `"nota zero elimina"`, `"Gerado por regras"` e o motivo `"sem GOOGLE_API_KEY"`; seção "O que este DNA ainda não sabe" lista as lacunas e o texto fixo "Sem provas anteriores desta banca na base, o peso por tópico é uniforme dentro da matéria" quando algum `metodo == "uniforme_no_edital"`.
- `test_concurso_mostra_verticalizado`: contém `"0 de 36"`, `corpo.count("não visto") == 36`, os 7 nomes de matéria do conteúdo, `"Licitações e contratos"`, e cada tópico em `<li data-slug="…">` (36 ocorrências de `data-slug=`).
- `test_concurso_gerado_por_ia`: com o dublê do passo 12 → contém `"Gerado por IA (gemini-2.5-flash)"`.
- `test_formatar_pct`: `formatar_pct(12.5) == "12,5 %"`, `formatar_pct(75.0) == "75 %"`, `formatar_pct(3.409) == "3,4 %"`, `formatar_pct("desconhecido") == "desconhecido"`.
**Implementação mínima:** `GET /concurso/{concurso_id}` com `concurso_id: UUID` (FastAPI converte; inválido → 422 JSON pelo tratador da V1), `exigir_usuario`; `buscar_concurso` → `None` → `HTTPException(404, "Concurso não encontrado.")`; `concurso.tenant_id != usuario.tenant_id` → `HTTPException(403, "Este concurso pertence a outra conta.")`; monta `dna = DnaConcurso.model_validate(registro.conteudo)`, `materias_prova: list[{slug, nome_exibicao, pct_pontos, questoes, pontos, fonte}]` (a partir de `dna.pesos.materia` + nomes do verticalizado), `verticalizado(db, edital.id)` e passa `dict`s ao template. `templates.py`: `formatar_pct(valor: float | str) -> str` (1 casa, vírgula, sem `,0`) registrada em `criar_templates` como `templates.env.filters["pct"]` (https://jinja.palletsprojects.com/en/stable/api/#custom-filters ; `Jinja2Templates.env` https://fastapi.tiangolo.com/advanced/templates/ ). `concurso.html`: cabeçalho (órgão, cargo, banca, data da prova ou "data não informada no edital"), badge de origem, tabela de matérias com barra de largura `style="--pct: {{ m.pct_pontos }}"` (CSS lê a variável; sem cor literal), regra de correção em 3 linhas, lacunas, depois o verticalizado com `<details open>` por matéria e `<li data-slug>` com `<span class="status status--nao-visto">não visto</span>`. Contagem "0 de N" calculada na rota.
**Pronto quando:** verde; página legível no celular nos dois temas; `test_tokens_sem_cor_literal_fora_de_tokens` (V1) continua verde.

### Passo 14 — `GET /editais`, navegação e link em `/conta`
**Objetivo:** lista dos concursos do tenant (o último = principal) e entrada na navegação.
**Arquivos:** `aprovaos/api/editais.py`, `web/templates/editais/lista.html`, `web/templates/base.html`, `web/templates/conta/conta.html`, `tests/test_rota_editais.py`, `tests/test_rota_conta.py` (asserção da nav).
**Testes red:**
- `test_editais_sem_login_redireciona`: 303 → `/entrar`.
- `test_editais_vazio`: 200; contém "Você ainda não subiu nenhum edital" e `href="/editais/subir"`.
- `test_editais_lista_e_marca_principal`: dois uploads → dois `<a href="/concurso/…">`; o primeiro da lista é o mais recente e traz `"principal"`; o outro não.
- `test_editais_nao_mostra_de_outro_tenant`: conta B vê lista vazia.
- `test_nav_logado_tem_meus_editais`: `GET /` logado contém `href="/editais"` e "Meus editais"; deslogado não.
- `test_conta_tem_link_para_editais`: `GET /conta` contém `href="/editais"`.
**Implementação mínima:** `GET /editais` → `listar_concursos_do_tenant`; contexto `concursos: list[{id, orgao, cargo, banca, criado_em, principal: bool}]`. `base.html`: `<a href="/editais">Meus editais</a>` no bloco logado. `conta.html`: parágrafo com o link. Premissa A explícita no template ("principal = o último que você subiu").
**Pronto quando:** verde; fluxo manual: cadastrar → Meus editais (vazio) → subir → concurso → Meus editais (1, principal).

### Passo 15 — Docs, pendências, decisões e commit de fim de fatia
**Objetivo:** deixar escrito o que entrou, o que ficou e por quê (CLAUDE.md regras 6, 7, 12).
**Arquivos:** `docs/02-produto.md` (linha V2 — seção 10), `docs/PENDENCIAS.md` (P-23 concurso principal = último até `perfil_estudo`; P-24 retificações/versão 2 do edital; P-25 `traco` escrito à mão, exporter OTel pendente; atualizar P-17 com "DNA declara `desconhecido`; a página mostra as lacunas"), `docs/DECISOES.md` (ADR-0032: analista com fallback determinístico por regras + `dna_concurso.conteudo` JSON inteiro + `reportlab` dev-dep + porta async/callback; adendo na ADR-0023: "V2: `pypdfium2` em produção para texto; `pdfplumber` ainda não entrou"), `docs/04-modelo-de-dados.md` §3 (adendo de uma linha em `dna_concurso` e `topico_edital.ordem`), `CLAUDE.md` (mapa: `knowledge/fixtures/`, `backend/aprovaos/{agentes,roteador}/`; estado da Fase 5: "V1 e V2 no ar (local)"), `docs/fatias/V2-execucao.md` (completo), `docs/RISCOS.md` (R-20: LLM devolve DNA plausível mas errado — mitigação `verificar_dna` + fallback + revisão do dono no piloto).
**Teste red:** não há teste automatizado; o revisor confere que a tabela do PRD §6 tem a linha V2 atualizada, que cada item da seção 3 deste plano tem linha em PENDENCIAS ou na tabela, e que `V2-execucao.md` tem um bloco por passo com a saída do teste `llm`.
**Pronto quando:** `bash scripts/checar.sh` verde; `git commit` `feat(v2): subir edital → DNA reduzido + edital verticalizado — …` e resumo curto para o dono.

## 7. Comandos

```bash
cd ~/PycharmProjects/aprovaos/backend && uv sync                       # instala pypdfium2, google-adk, reportlab
uv run pytest tests/test_dominio_edital.py -x -q                         # um arquivo (red/green)
uv run ruff check --fix . ../scripts && uv run ruff format . ../scripts && uv run mypy
uv run python ../scripts/checar_import.py                                # deve continuar imprimindo importados: N (N ≥ 30)
uv run pytest -q                                                         # llm e postgres pulados sem as variáveis
bash ../scripts/checar.sh

# fixture PDF (uma vez; commitar o resultado)
uv run python ../scripts/gerar_fixture_pdf.py \
  ../docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md \
  ../knowledge/fixtures/editais/edital-assessor-gabinete.pdf
git check-ignore -v ../knowledge/fixtures/editais/edital-assessor-gabinete.pdf   # não deve listar

# migração
DATABASE_URL=sqlite:////tmp/m.db uv run alembic upgrade head
DATABASE_URL=sqlite:////tmp/m.db uv run alembic revision --autogenerate -m "edital_dna"   # revisar e renomear para 0002_edital_dna.py

# teste real com Gemini (uma vez, com a chave no .env ou no ambiente)
GOOGLE_API_KEY=... uv run pytest -q -m llm -s

# app
uv run alembic upgrade head && uv run uvicorn aprovaos.main:criar_app --factory --reload   # /editais/subir
```

## 8. Riscos

| risco | mitigação neste plano |
|---|---|
| Gemini structured output não aceita `dict` com chaves livres (`pesos.materia`, `pesos.topico`, `incidencia.por_topico`) — o ADK pode rejeitar o `output_schema` ou o modelo devolver objeto vazio. | Teste `llm` no passo 10 revela cedo; instrução de **parar e perguntar** (Q4) com plano B documentado (JSON via prompt + `response_mime_type`); `verificar_dna` + fallback por regras garantem que a aluna sempre vê um DNA. |
| LLM devolve DNA plausível mas errado (pct por contagem, tópico inventado). | 4 verificações da skill em `verificar_dna`; reprovou → regras, com motivo visível na página; R-20. |
| Parser por regex falha num edital real diferente do fixture (numeração `1.1`, matérias em Title Case, conteúdo em tabela). | Erro claro "não encontrei o conteúdo programático" em vez de DNA vazio; o primeiro edital real da Ana vira **fixture nova + caso de teste** (registrar em PENDENCIAS quando acontecer). |
| `pypdfium2` extrai texto fora de ordem em PDFs com colunas. | Fora do escopo (editais são uma coluna); se ocorrer, PENDENCIAS. |
| Rota `async def` com SQLAlchemy síncrono bloqueia o loop durante o pipeline (< 2 s por regras; segundos com IA). | Aceito no piloto n=1; anotar em RISCOS; solução (threadpool/`run_in_threadpool`) só quando houver mais de um usuário. |
| `google.adk` importado em nível de módulo "só para tipar". | Import tardio dentro da fábrica + `TYPE_CHECKING`; `checar_import.py` na CI. |
| `GOOGLE_API_KEY` no `.env` lida também pelo SDK via ambiente, escondendo que a config não foi usada. | Cliente explícito (`genai.Client(api_key=…)`); teste `test_criar_analista_adk_exige_chave`. |
| Teto diário é calculado só sobre `traco` — chamadas que estouram antes de gravar não contam. | O callback grava também em `resultado="erro"`; custo estimado com os tokens disponíveis (ou `None`). |
| Subir o mesmo PDF duas vezes cria dois concursos. | Comportamento aceito na V2 (Q3); o PDF em disco é deduplicado por hash. |
| `Decimal` vs `float` em `custo_brl`/`pct`. | Dinheiro em `Decimal`; percentuais do DNA em `float` (contrato da skill). |
| Dev júnior amplia escopo (pdfplumber, OTel, radar, retificação, status do verticalizado). | Seção 3 é a lista do que **não** fazer; revisor confere. |

## 9. Definition of done da V2

1. `bash scripts/checar.sh` verde (ruff, format, mypy strict, import sem efeito colateral com `importados: N ≥ 30`, pytest com `llm`/`postgres` pulados).
2. Testes dos passos 4–14 cobrem: validação e extração do PDF, parser (36 tópicos no `.md` e no PDF; dois casos de borda), fatos por regex, DNA por regras com `pct_pontos` corretos e lacunas declaradas, `verificar_dna` (4 verificações), custo/teto/`traco`, fallback IA→regras com dublê, upload (sucesso, htmx, 4 erros), `/concurso/{id}` (404/403 JSON, DNA, verticalizado "0 de 36"), `/editais` e navegação.
3. Teste `llm` executado **uma vez** com chave real; saída (tokens, custo, `verificar_dna`) registrada em `V2-execucao.md`.
4. Fluxo manual no navegador com `.env` sem chave: cadastrar → Meus editais → subir a fixture → página do concurso com "Gerado por regras" → Meus editais mostra "principal".
5. `alembic upgrade head` aplica `0002` em SQLite e (quando o Docker estiver de pé) em Postgres; `test_migracoes.py` verde nos dois.
6. Nenhum arquivo sem cabeçalho de 2 linhas; nenhuma função/classe pública sem docstring; nenhuma cor literal fora de `tokens.css`; o PDF da fixture commitado e não ignorado.
7. PRD §6 (linha V2), PENDENCIAS (P-23…P-25, P-17), DECISOES (ADR-0032 + adendo 0023), modelo de dados, RISCOS e CLAUDE.md atualizados; commit feito; resumo entregue ao dono.

## 10. Linha para a tabela do PRD §6

`| V2 (3+13 parcial) | Subir edital → DNA reduzido + edital verticalizado | PDF (≤ 10 MB, `pypdfium2`) → parser determinístico do conteúdo programático (36 tópicos no fixture) → `DnaConcurso` no contrato da skill `dna-do-concurso`: por IA (`analista-de-edital`, ADK `LlmAgent` + `output_schema`, Gemini 2.5 Flash) quando há `GOOGLE_API_KEY` e teto diário, senão por regras (pct por pontos, uniforme por tópico, lacunas declaradas); `verificar_dna` reprova → regras com motivo visível; tabelas `concurso`, `edital`, `documento`, `topico`, `topico_edital`, `dna_concurso` (Alembic 0002); `traco` por chamada de LLM + teto R$ 3/dia; `/editais/subir`, `/editais`, `/concurso/{id}` (DNA + verticalizado "0 de N", só o dono do tenant) | peso por prova, corte histórico e estilo da banca local (P-17); radar/catálogo (1b); retificações (P-24); concurso principal por `perfil_estudo` (P-23, fatia 7); status do verticalizado por eventos (V3/V4); OTel (P-25) | no ar (local) — <data> |`

## 11. Perguntas em aberto (respostas antes de executar o passo indicado; opção recomendada primeiro)

- **Q1 (passos 1, 3):** `reportlab` como dependência de dev para gerar a fixture (premissa J) — (a) sim, script commitado e PDF commitado; (b) gerar uma vez com `cupsfilter` no macOS e commitar só o PDF (sem script, sem dep); (c) outro. Recomendado: (a).
- **Q2 (passo 2):** `dna_concurso` com o JSON inteiro em `conteudo` (premissa B) em vez das colunas JSON separadas do modelo §3 — (a) sim, com adendo no modelo de dados; (b) seguir o §3 à risca (11 colunas). Recomendado: (a).
- **Q3 (passo 12):** subir o mesmo PDF de novo — (a) cria concurso novo (V2, simples; o arquivo é deduplicado por hash); (b) detectar pelo hash e redirecionar para o concurso existente. Recomendado: (a) no piloto; (b) vira pendência se atrapalhar.
- **Q4 (passo 10):** se o Gemini/ADK rejeitar o `output_schema` por causa dos `dict` de chaves livres — (a) plano B: `response_mime_type="application/json"` sem `output_schema`, esquema no prompt, `model_validate_json` igual; (b) mudar o contrato da skill para listas `[{slug, …}]` (mexe na skill testada na Fase 4). Recomendado: (a). Só decidir se o risco se materializar.
- **Q5 (passo 13):** `/concurso/abc` (UUID inválido) responde 422 `dados_invalidos` JSON (comportamento natural do FastAPI + tratador da V1) ou 404? Recomendado: 422, sem código extra.
- **Q6 (passo 1):** `TETO_DIARIO_BRL=3.00` vale para o piloto (free tier do AI Studio custa zero, mas o teto protege se a chave for de conta paga)? Recomendado: sim.

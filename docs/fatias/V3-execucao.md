# Fatia V3 — registro de execução
> O que é: o diário de execução do plano `V3-questoes-cebraspe.md`. Quando ler: ao revisar a curadoria real desta fatia ou ao retomar a partir do passo 13.

Os passos 1–11 (fonte Cebraspe, coleta, segmentação, gabarito, classificação, curador, modelos ORM
e repositório de questões) já estão commitados (ver `git log` — commits de `feat(v3): …` de
17–18/09/2026); este diário começa no passo 12, que é quem primeiro roda o pipeline inteiro de
ponta a ponta contra o banco real. Os números de cobertura por tópico citados abaixo (12/70,
19/70…) não tinham sido medidos fim a fim antes deste passo.

## Passo 12 — Comando `curar` e execução real

Executado em 18/09/2026 em `/Users/vinicius/PycharmProjects/aprovaos/backend`, `uv` + CPython
3.13, SQLite (`dev.db`, sem Docker) — a mesma máquina do passo 5. Sem `GOOGLE_API_KEY` no
ambiente: toda a classificação real saiu de `ClassificadorPorRegras` (o teste `test_classificador_llm.py`, marcado `llm`, continua pulado — P-27).

### Testes (`backend/tests/test_motor_curar.py`)
Três testes, todos verdes de primeira (nenhuma iteração RED→GREEN precisou de correção no
código de produção — só formatação/import por `ruff --fix`):

1. `test_curar_grava_questoes` — RED do brief. Sobe o caderno **real** da TJ-PA (o mesmo fixture
   de `test_curador.py`, 70 itens, 5 anulados) com o vocabulário real da Linda; confere
   `RelatorioCuradoria` (total 70, anuladas 5, publicáveis > 0, novas 70, repetidas 0), as 70
   linhas em `questao` e **zero linhas em `traco`** (sem chave).
2. `test_pendente_revisao_nao_grava_nada` — RED do brief. Gabarito sintético com 1 entrada a
   menos que os itens do caderno (mesma divergência que `test_curador.py::test_contagem_divergente_para_tudo`
   cobre no curador puro) — aqui provada na borda de `curar_documento`: `extrair_texto` (a
   fronteira de I/O) é trocada por um dublê determinístico, sem fabricar um PDF de banca real.
   `RelatorioCuradoria.pendente_revisao is True`, `total/novas/repetidas == 0`, `problemas` cita
   `"≠ gabarito"`, e a tabela `questao` continua vazia.
3. `test_curar_registra_traco_por_chamada_de_llm` — o terceiro teste pedido pelo brief ("teste os
   dois casos — o segundo com um classificador falso que devolve `ChamadaLlm`, sem rede").
   `config.google_api_key` preenchida + `criar_classificador_adk` trocado por uma fábrica falsa
   (`_ClassificadorFalso`, sem `google.*`, sem rede): `montar_lotes(70, 20) == [20, 20, 20, 10]` →
   exatamente 4 chamadas → 4 linhas de `traco`, todas com `usuario_id is None` (é um comando, não
   uma rota autenticada).

Comando: `cd backend && uv run pytest tests/test_motor_curar.py -v` → `3 passed`.
`bash scripts/checar.sh` na raiz → ruff, `ruff format --check`, `mypy --strict` (94 arquivos),
prova de import sem efeito colateral e a suíte inteira `264 passed, 5 skipped` — **exceto** um
teste pré-existente, fora do escopo deste passo (ver "Achado fora do escopo" abaixo).

### Decisões de design tomadas neste passo (não estavam no brief)
- **Assinatura de `curar_documento`**: `(db, config, documento_prova_id, documento_gabarito_id,
  edital_id)` — a versão com os dois ids de documento (não só o da prova), por instrução
  explícita do dono ao abrir este passo. O pareamento prova↔gabarito continua sendo decisão de
  quem chama (`main()`, a partir de `--evento`/`--cargo`) — `curar_documento` nunca adivinha.
- **`RegraProva` dos quatro cadernos reais**: os concursos de origem (TJ-PA, STJ, TRT10) têm
  edital próprio, que esta fatia não lê (só prova e gabarito, coletados no passo 5). Em vez de
  inventar `fonte="instrução do caderno"` (conferido: essa instrução **não** está no texto
  extraído da prova — só a partir do item 51 em diante), `RegraProva.fonte` entra como
  `"convenção Cebraspe C/E — edital do concurso de origem não lido nesta fatia"`, com
  `anula_por_erro=True` (a convenção mais comum da banca). Isso não afeta `publicavel` —
  `dominio.questao.decidir_publicacao` não consulta `RegraProva`.
- **`orgao`/`ano`/`cargo` de `Origem`**: derivados deterministicamente do que o coletor (passo 5)
  já gravou em `documento.metadados`, nunca de uma nova chamada à API nem de texto digitado à
  mão:
  - `orgao`/`ano` ← `metadados["evento"]` (`_orgao_e_ano_do_evento`): o primeiro token de 2
    dígitos do `eventoURL` é o ano (`"TJ_PA_25_SERVIDOR"` → `("TJ-PA", 2025)`,
    `"STJ_24"` → `("STJ", 2024)`, `"TRT10_24"` → `("TRT10", 2024)`).
  - `cargo` ← `metadados["descricao"]` (`_cargo_da_descricao`): só o identificador que a Cebraspe
    já usa no nome do arquivo (`"CARGO 9"`), **não** um nome de cargo bonito como "Analista
    Judiciário — Direito" — isso exigiria reabrir `eventoCargos` da API (rede) ou o edital do
    concurso de origem, fora do escopo deste passo. Registrado aqui para o dono decidir se vale a
    pena buscar depois (candidato a pendência).
- **Vocabulário do edital**: `_vocabulario_do_edital(db, edital_id)` — `TopicoEdital` ⋈ `Topico`
  do `edital_id` dado, traduzido para `TopicoVocabulario`. Não existia antes (o passo 9 recebia o
  vocabulário já pronto por parâmetro nos testes do curador puro).
- **`_escolher_classificador`**: mesmo padrão de `agentes.classificador.escolher_classificador`
  (chave → teto → `criar_classificador_adk`), mas sem `Usuario` — este é um comando, não uma
  rota autenticada; a linha de `traco` de cada chamada entra com `usuario_id=None`.

### Como o `edital_id` foi obtido (decisão 8 do passo)
Sem servidor HTTP: um script de uma vez (`/private/tmp/.../scratchpad/subir_edital.py`, **não
commitado** — só para preparar o `dev.db`) chamou exatamente o mesmo pipeline da rota
`POST /editais/subir` (`api/editais.py`): `validar_pdf` → `extrair_texto` →
`extrair_conteudo_programatico` → `gerar_dna(texto, materias, analista_ia=None, motivo="sem
GOOGLE_API_KEY")` → `guardar_pdf` → `registrar_edital`, sobre o fixture
`knowledge/fixtures/editais/edital-assessor-gabinete.pdf`, com uma conta nova
(`linda.piloto@exemplo.com`) criada por `criar_conta`. Resultado:
`edital_id = 508314e5-cba3-4799-bb60-9fd3a482b20a` (36 tópicos, DNA por regras).

Preparação do banco:
```bash
cd backend
DATABASE_URL=sqlite:///dev.db CHAVE_SECRETA=t12345678901234567890123456789012 uv run alembic upgrade head
# 0002 -> 0003 (tabelas fonte/questao/alternativa/evento_estudo/reporte_erro)
```

### Execução real dos quatro cadernos coletados
```bash
cd backend
export DATABASE_URL=sqlite:///dev.db CHAVE_SECRETA=t12345678901234567890123456789012
EDITAL=508314e5-cba3-4799-bb60-9fd3a482b20a
uv run python -m aprovaos.motor.curar --evento TJ_PA_25_SERVIDOR --cargo 9  --edital "$EDITAL"
uv run python -m aprovaos.motor.curar --evento STJ_24           --cargo 19 --edital "$EDITAL"
uv run python -m aprovaos.motor.curar --evento TRT10_24         --cargo 12 --edital "$EDITAL"
uv run python -m aprovaos.motor.curar --evento TRT10_24         --cargo 13 --edital "$EDITAL"
```
`TJ_CE_23_SERVIDOR` (coletado no passo 5) **ficou de fora**, como decidido: é múltipla escolha
A–E e a fatia é só Cebraspe C/E (decisão J do plano).

Saída de cada comando (sem `GOOGLE_API_KEY`; `tokens`/`custo`: N/A, zero chamadas de LLM):

| eventoURL | cargo | total | publicáveis | anuladas | sem tópico | novas | repetidas | `pendente_revisao` |
|---|---|---|---|---|---|---|---|---|
| `TJ_PA_25_SERVIDOR` | CARGO 9 | 70 | 12 | 5 | 57 | 70 | 0 | não |
| `STJ_24` | CARGO 19 | 70 | 19 | 2 | 51 | 70 | 0 | não |
| `TRT10_24` | CARGO 12 | 70 | 12 | 3 | 57 | 70 | 0 | não |
| `TRT10_24` | CARGO 13 | 70 | 12 | 3 | 57 | **0** | **70** | não |

Conferido direto no banco depois da execução (`sqlite3 dev.db`): `select count(*) from questao`
→ **210**; `sum(publicavel)` → **43**; `sum(gabarito_status='anulado')` → **10**;
`sum(topico_id is null)` → **165**; `select count(*) from traco` → **0**. Bate exatamente com a
soma das três linhas com `novas > 0` da tabela acima (70+70+70 = 210; 12+19+12 = 43; 5+2+3 = 10;
57+51+57 = 165).

**Achado real, não esperado**: o caderno de conhecimentos específicos do **CARGO 13** do
`TRT10_24` tem o **mesmo texto** do CARGO 12 (confirmado comparando os dois textos extraídos:
21 171 caracteres, mesmo enunciado item a item — dois arquivos PDF diferentes, hashes de arquivo
diferentes, mas o conteúdo da prova de conhecimentos específicos é idêntico entre os dois
cargos). `salvar_questoes` (dedup por `hash_dedup` do enunciado normalizado, passo 11) tratou
isso corretamente: as 70 questões do CARGO 13 saíram como **70 repetidas, 0 novas** — nenhuma
linha duplicada em `questao`. É o comportamento certo, não um bug; registrado aqui porque não
estava previsto no plano e explica por que o total em `questao` é 210, não 280.

### Cobertura por tópico (pergunta Q2 do plano, com o número na mão)
Publicáveis / total por caderno: TJ-PA 12/70 (17 %), STJ 19/70 (27 %), TRT10 12/70 (17 %) — a
mesma faixa medida no passo 9 isoladamente (12/70 no caderno da TJ-PA). A imensa maioria dos
itens "sem tópico" não é falha de segmentação nem de gabarito — é `ClassificadorPorRegras`
sem alcance: o léxico por termo/lei citada cobre bem menos do que a IA cobriria (Q2 do plano:
"se a cobertura ficar abaixo de ~60 %, entram mais concursos ou a tela assume a lacuna?" — aqui
ficou entre 17 % e 27 %, abaixo do que o plano cogitava como aceitável; fica registrado para o
dono decidir se roda de novo com `GOOGLE_API_KEY` antes do passo 13, em vez de aceitar a lacuna
ou coletar mais concursos). O comando é idempotente (dedup por `hash_dedup`): rodar de novo com
chave sobre os mesmos quatro cadernos não duplica nada, só teria chance de classificar mais itens
— mas a base grava `topico_slug` já decidido por regras; **reclassificar exigiria rodar `curar`
de novo sobre o mesmo par, o que hoje só acrescenta linhas repetidas, não atualiza uma questão já
gravada** (o repositório de questões, passo 11, não tem um `atualizar_questao`). Registrado como
pendência para quando a chave existir.

### Achado fora do escopo (não corrigido neste passo)
`tests/test_env_example.py::test_env_example_cobre_todas_as_configuracoes` já estava vermelho
antes deste passo: o commit `2d05598` ("fix(infra): porta do Postgres configurável por
POSTGRES_PORT") acrescentou `POSTGRES_PORT` ao `.env.example` sem atualizar o conjunto esperado
do teste. Não é deste passo (não toca `curar.py` nem configuração da V3) — não corrigido aqui
para não misturar dois commits; registrado para o dono decidir (1 linha em
`test_env_example.py`).

### Arquivos deste passo
Novos: `backend/aprovaos/motor/curar.py`, `backend/tests/test_motor_curar.py`,
`docs/fatias/V3-execucao.md` (este arquivo). Tocados: nenhum (não foi preciso mudar
`curador.py`, `classificacao.py`, `repositorio_questao.py` nem os modelos — o passo 12 só liga o
que já existia). Banco real (`backend/dev.db`, fora do git) com 210 questões, 1 edital, 1 usuário
de piloto (`linda.piloto@exemplo.com`) e as tabelas da migração `0003` aplicadas.

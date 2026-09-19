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
   de `test_curador.py`, 70 itens, 5 anulados) com o vocabulário do fixture de edital (fictício,
   Fase 4); confere
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

## Passo 12b — Chave real: modelo trocado, limite de taxa, reclassificar e a recuragem com IA

Executado em 18/09/2026, mesma máquina. O dono deu uma `GOOGLE_API_KEY` real (`.env` na raiz,
fora do git) depois do passo 12. Sete mudanças, nesta ordem.

### 1. Conserto do teste que o commit `2d05598` quebrou
`POSTGRES_PORT` é variável do Compose, não campo de `Configuracoes` — tratada como
`POSTGRES_PASSWORD`/`DATABASE_URL_TEST`, que o teste já tolerava.
`uv run pytest tests/test_env_example.py` → `1 passed`.

### 2. Troca de modelo: `gemini-2.5-flash` → `gemini-3.6-flash`
Confirmado pelo dono contra a API real: `gemini-2.5-flash` responde 404 ("no longer available
to new users") para esta chave. `modelo_dna`/`modelo_classificacao` (`config.py`, `.env.example`)
e `PRECOS_USD_POR_MILHAO` (`roteador/custo.py`) atualizados. Preço do `gemini-3.6-flash`
(paid tier, https://ai.google.dev/gemini-api/docs/pricing, lido em 18/09/2026, válido até
31/12/2026): US$ 0,75/M entrada, US$ 3,75/M saída — no **free tier** (a chave do piloto) o custo
real de entrada/saída é zero; a tabela existe para o teto diário proteger o dia em que a conta
virar paga. Mantidas as entradas do 2.5 (quem tiver chave antiga continua funcionando). Testes
novos: `test_estimar_custo_gemini_3_6_flash`, e os que dependiam do modelo padrão
(`test_configuracoes_da_v2_tem_padroes`, `test_campos_da_v3`,
`test_post_subir_usa_ia_quando_ha_chave_e_teto`, `test_concurso_gerado_por_ia`) atualizados para
`"gemini-3.6-flash"`.

### 3. Limite de taxa: retentativa com espera + achado real que corrigiu o desenho
`_com_retentativa_de_limite` (`agentes/classificador.py`): genérica, só olha `erro.code`/
`erro.details` — testável sem `google.*` (4 testes: espera e tenta de novo, desiste se a espera
sugerida passa de `_ESPERA_MAXIMA_S=90s` — é cota diária, não por minuto —, esgota
`_TENTATIVAS_MAX=3` e relança, não intercepta erro que não é 429).

**Rodando de verdade contra a chave real** (ver §6), a primeira tentativa mostrou que o desenho
inicial **não funcionava**: o traço gravado tinha `erro="RespostaDoModeloAusente"`, com
`duracao_ms` < 1 s — nenhuma retentativa real aconteceu. Causa (lida em
`google/adk/workflow/_node_runner.py::_execute_node`): o ADK não deixa o
`google.genai.errors.ClientError` de 429 subir como exceção Python até `Runner.run_async` — ele
captura a exceção do modelo e publica um `Event(error_code=erro.status ou o nome da classe,
error_message=str(erro))`; para um 429, `.status` é a string `"RESOURCE_EXHAUSTED"`. `_rodar`
tratava **qualquer** `error_code` como `RespostaDoModeloAusente` (sem `.code`), então
`_com_retentativa_de_limite` nunca reconhecia o 429. Corrigido: `LimiteDeTaxaExcedido` (nova
exceção, `.code = 429`, `.details` reconstruído por regex do texto "Please retry in Ns." — o
`RetryInfo` estruturado não sobrevive à conversão do ADK para `Event`, só o texto); `_rodar`
levanta essa classe quando `evento.error_code == "RESOURCE_EXHAUSTED"`, `RespostaDoModeloAusente`
para qualquer outro `error_code`. 4 testes novos, 2 deles rodando `ClassificadorAdk._rodar` de
verdade contra um `Runner`/`Event` dublês (sem rede) para provar a distinção.
**Reexecutado depois do conserto** (§6): os traços passaram a mostrar `erro="LimiteDeTaxaExcedido"`
com `duracao_ms` de ~78 s a ~120 s — a retentativa real aconteceu.

### 4. Reclassificar sem duplicar
`atualizar_classificacao` (`dados/repositorio_questao.py`): localiza por `hash_dedup` e muda só
`topico_id`/`topico_confianca`/`topico_evidencia`/`publicavel`/`motivo_nao_publicavel` — nunca o
texto, o gabarito ou a `origem`. 2 testes (muda tópico sem tocar o resto da linha; ignora hash
inexistente sem criar nada). `curar_documento(..., reclassificar: bool = False)` e `--reclassificar`
no comando trocam `salvar_questoes` por essa função. Teste de integração (com um classificador
falso que joga tudo no mesmo tópico): 70 atualizadas, 0 novas, 0 repetidas, `questao` continua
com 70 linhas — não 140.

### 5. `thinking_budget=0`: aceito pelo SDK, não medido
O dono mediu uma chamada real de classificação: 96 tokens de entrada, 102 de saída e **568 de
"pensamento"** — grátis no free tier, mas custa como saída no paid tier e infla a latência. O
`google-genai`/`google-adk` pinado aceita `GenerateContentConfig(thinking_config=ThinkingConfig(
thinking_budget=0))` (confirmado por inspeção do schema Pydantic instalado, sem precisar de
rede) — aplicado em `criar_classificador_adk`. `test_criar_classificador_adk_desliga_pensamento`
confere o esquema (sem rede). **Não medido**: a cota diária esgotou (ver §6) antes de eu
conseguir rodar uma chamada real para confirmar que a resposta continua correta com o
pensamento desligado — pendência para a próxima vez que houver cota (um `uv run pytest -m llm`
resolve).

### 6. A recuragem real — bloqueada pela cota diária do free tier, não pelo código
Ao testar a chave contra a API de verdade (passos 3 e 5 acima, mais a tentativa de recuragem em
si), o free tier do AI Studio para `gemini-3.6-flash` acusou dois limites, não um:
- **5 requisições/minuto** (o Fato 2 do dono, confirmado).
- **20 requisições/dia por projeto por modelo** — `quotaId:
  "GenerateRequestsPerDayPerProjectPerModel-FreeTier"`, `quotaValue: "20"` — **não estava nos
  três fatos do dono** e é bem mais restritivo. Minhas próprias chamadas de diagnóstico (medir o
  formato do erro 429 para escrever `_segundos_de_retentativa`, testar `thinking_budget=0`)
  consumiram a maior parte dessa cota antes de eu perceber que ela existia — o resto se esgotou
  tentando a recuragem em si.

Uma vez esgotada, toda chamada nova (mesmo minutos depois, em processos separados) devolveu 429
com a mesma mensagem (`retryDelay` variando entre ~40 s e ~60 s, mas nunca resolvendo) — não é um
balde que reabastece rápido; é o teto do dia mesmo, e o `retryDelay` curto parece ser só o valor
padrão que a API devolve para esse tipo de erro, não o instante real da renovação.

**O que rodei mesmo assim, com a chave real** (não fabricado): `curar --evento
TJ_PA_25_SERVIDOR --cargo 9 --edital <uuid> --reclassificar`, duas vezes (antes e depois do
conserto do item 3). As duas vezes a IA levou 429 real em todos os 4 lotes; a segunda vez (com
`LimiteDeTaxaExcedido` já corrigido) retentou de verdade — 3 tentativas por lote, esperando o
`retryDelay` real entre elas (`traco.duracao_ms` de ~78 500 a ~120 100 ms) — e caiu para
`ClassificadorPorRegras` em todos os 4 lotes depois de esgotar as tentativas. Resultado: **idêntico
ao de regras** (nenhuma classificação por IA foi obtida), `atualizadas=70`, `novas=0`, `0`
linhas duplicadas — a base não foi corrompida, só não melhorou.

**Não repeti para `STJ_24`/`TRT10_24` cargo 12**: a cota é por projeto+modelo (não por evento
curado), e a TJ-PA já provou de forma reprodutível (2 execuções, ~10 minutos de tentativas reais)
que está esgotada agora — rodar de novo só gastaria mais ~10 minutos por evento para o mesmo
resultado previsível, sem nenhuma informação nova.

**Tabela antes × depois** (publicáveis por regras vs. com IA — pedida pelo coordenador):

| eventoURL | cargo | publicáveis por regras | publicáveis com IA | tokens (IA) | custo estimado (IA) |
|---|---|---|---|---|---|
| `TJ_PA_25_SERVIDOR` | CARGO 9 | 12 | **bloqueado — cota diária esgotada** (caiu para regras: 12) | 0 (toda tentativa falhou antes de gerar conteúdo) | R$ 0,00 |
| `STJ_24` | CARGO 19 | 19 | não tentado (mesma cota, já provada esgotada) | — | — |
| `TRT10_24` | CARGO 12 | 12 | não tentado (mesma cota, já provada esgotada) | — | — |

`traco` desta rodada: 8 linhas, todas `resultado="erro"`, `tokens_in`/`tokens_out`/`custo_brl`
`NULL` (nenhuma chamada chegou a gerar conteúdo faturável) — 4 com `erro="RespostaDoModeloAusente"`
(antes do conserto do item 3) e 4 com `erro="LimiteDeTaxaExcedido"` (depois).

### O que fica para quando houver cota de novo
1. `uv run python -m aprovaos.motor.curar --evento STJ_24 --cargo 19 --edital <uuid>
   --reclassificar` e o mesmo para `TRT10_24 --cargo 12` — os comandos já existem e já foram
   testados; só falta a cota.
2. `GOOGLE_API_KEY=… uv run pytest -q -m llm` — mede se `thinking_budget=0` continua dando
   resposta correta (item 5) e roda `test_classificador_llm.py`/`test_analista_adk_llm.py`
   (P-27, ainda aberta).
3. Se a cota diária de 20 continuar tão apertada mesmo fora do período de testes, `LOTE_CLASSIFICACAO`
   maior (ex.: 35, dois lotes por caderno de 70 em vez de 4) reduz o nº de chamadas — troca lote
   maior por prompt maior; não teve por que mexer nisso agora, registrado como opção.

### Verde (passo 12b)
`bash scripts/checar.sh` na raiz: ruff, `ruff format --check`, `mypy --strict` (89 arquivos),
prova de import sem efeito colateral, suíte inteira `278 passed, 5 skipped` (`postgres` ×2,
`llm` ×2, `rede` ×1).

### Arquivos do passo 12b
Tocados: `.env.example`, `backend/aprovaos/config.py`, `backend/aprovaos/roteador/custo.py`,
`backend/aprovaos/agentes/classificador.py`, `backend/aprovaos/dados/repositorio_questao.py`,
`backend/aprovaos/motor/curar.py`, `backend/tests/{test_env_example,test_config,test_roteador,
test_rota_concurso,test_rota_subir_edital,test_classificacao,test_repositorio_questao,
test_motor_curar}.py`, `docs/fatias/V3-execucao.md` (este bloco), `docs/02-produto.md` (§6).
Banco real (`backend/dev.db`, fora do git): sem mudança de conteúdo (210 questões, mesmas 43
publicáveis) — só 8 linhas novas em `traco`.

## Passo 12c — Cota é por modelo: `gemini-3.5-flash-lite` e a recuragem real, de verdade

Executado em 18/09/2026, mesma máquina. Achado do coordenador: a cota diária de 20 req/dia do
free tier (passo 12b) é **por modelo**, não geral por projeto — `gemini-3.6-flash` está esgotado
no dia, mas `gemini-3.5-flash-lite` respondia 200 com cota intacta. Escolha também certa pela
tarefa: classificar item de prova num vocabulário fechado é "simple data processing" (a própria
página do modelo o descreve assim), e o Lite é o mais barato da família no paid tier.

### 1. Modelo do classificador trocado
`modelo_classificacao` → `gemini-3.5-flash-lite` (`config.py`, `.env.example`); `modelo_dna`
continua `gemini-3.6-flash` (DNA do edital é raciocínio, não triagem). `PRECOS_USD_POR_MILHAO`
ganhou a entrada (US$ 0,30/M entrada, US$ 2,50/M saída, paid tier,
https://ai.google.dev/gemini-api/docs/pricing, lido em 18/09/2026).

### 2. Achado real nº 2 do dia: `thinking_config` quebra o Flash-Lite
Primeira tentativa de recuragem real (TJ-PA) voltou **`400 INVALID_ARGUMENT`** nos 4 lotes —
com o `thinking_config=ThinkingConfig(thinking_budget=0)` que o passo 12b tinha ligado (item 5
de lá). Removido o campo do `GenerateContentConfig` do classificador; a chamada seguinte
funcionou. A pendência "medir se `thinking_budget=0` mantém a resposta correta" (passo 12b, item
5) fica **cancelada** para este modelo, não só adiada — ele não aceita o campo, então não há o
que medir. Custo real desse achado: 4 chamadas gastas (todas `400`, sem gerar conteúdo — não deu
para confirmar se contam contra a cota diária, mas nenhuma das rodadas seguintes indicou
problema de cota).

### 3. A recuragem real dos três cadernos — com sucesso desta vez
`uv run python -m aprovaos.motor.curar --evento <evento> --cargo <n> --edital <uuid>
--reclassificar`, um caderno por vez, na ordem pedida. As três rodaram sem erro (4 chamadas
`resultado="ok"` cada, 12 no total — exatamente o orçamento previsto).

**Tabela antes × depois** (publicáveis por regras vs. com IA de verdade, `gemini-3.5-flash-lite`)
— **corrigida na rodada de revisão do passo 12** (ver "Correção do método" logo abaixo; os
números de "só IA"/"só regras" mudaram, os de publicáveis e tokens/custo não:

| eventoURL | cargo | publicáveis (regras) | publicáveis (IA) | só IA (itens) | só regras (itens) | tokens in/out | custo estimado |
|---|---|---|---|---|---|---|---|
| `TJ_PA_25_SERVIDOR` | CARGO 9 | 12 | **37** | 27 | 2 (57, 78) | 14 307 / 4 692 | R$ 0,0865 |
| `STJ_24` | CARGO 19 | 19 | **19** | 5 (58, 81, 82, 83, 84) | 5 (75, 99, 107, 118, 120) | 15 022 / 3 648 | R$ 0,0736 |
| `TRT10_24` | CARGO 12 | 12 | **7** | 4 (59, 61, 70, 72) | 9 (51, 63, 96, 99, 113–117) | 14 755 / 3 757 | R$ 0,0746 |
| **Total** | | **43** | **63** | 36 | 16 | 44 084 / 12 097 | **R$ 0,2347** |

Custo real gasto: **R$ 0,00** — a chave está no free tier; a coluna "custo estimado" é o que
`traco.custo_brl` grava (o preço do paid tier, o que o teto diário protegeria).

**Correção do método (rodada de revisão do passo 12).** A primeira versão deste diário contava
"a IA achou, as regras não" só olhando `topico_slug`/`topico_confianca` — sem aplicar o resto do
gate de publicação (`dominio.questao.decidir_publicacao`, que também olha `gabarito_status` e
`origem`). Isso inflava o número: na TJ-PA, os itens **104 e 105 são anulados** (gabarito não
serve para nada, publicável nunca) — o método antigo contava os dois como "a IA achou" porque
regras não tinha atribuído tópico a eles, mas nenhum dos dois é publicável de qualquer jeito, com
IA ou sem. O método corrigido chama `decidir_publicacao` de verdade — mesmo gate que grava
`questao.publicavel` — com a classificação de `classificar_por_regras` (rodado offline sobre os
itens segmentados do PDF, sem rede) e com `gabarito_status`/`origem` **reais** lidos do banco;
"só IA" e "só regras" são a diferença simétrica dos dois conjuntos de publicáveis resultantes.
29 → 27 na TJ-PA (os itens 104 e 105, anulados, saíram da contagem); 6 → 5 na STJ_24. As duas
somas agora fecham: `publicáveis (regras) + só IA − só regras = publicáveis (IA)` em todas as
três linhas (ex.: TJ-PA: 12 + 27 − 2 = 37).

**Auditoria dos 9 itens que o TRT10_24 perdeu com a IA — conclusão: 8 são melhora de precisão,
não regressão.** Lidos os nove enunciados reais contra o motivo que o léxico usou para
classificá-los:
- **Item 51** — trata de **LGPD / dados pessoais sensíveis**; as regras casaram o termo "lei de
  introdução às normas do direito brasileiro" (LINDB) de passagem — **falso positivo**.
- **Item 63** — demonstrativo de cálculo em **execução fiscal**; casou "petição inicial" de
  passagem — **falso positivo**.
- **Item 99** — **revelia e confissão ficta**; casou "petição inicial" — **falso positivo**.
- **Itens 113, 114, 115, 116 e 117** — todos sobre **previdência complementar e seguridade
  social**; casaram "servidores públicos" — **falso positivo** (é Direito Previdenciário, matéria
  que nem está no edital de teste).
- **Item 96** — indeferimento de **petição inicial** por falta de documento indispensável: aqui
  o termo "petição inicial" era mesmo o assunto do item — **as regras estavam certas e a IA
  errou**, deixando sem tópico (registrado como pendência, P-29 em `docs/PENDENCIAS.md`).

**8 dos 9 itens que a TRT10_24 "perdeu" eram falso positivo do léxico por regras — a IA filtrou
lixo.** O "12 → 7" publicáveis do TRT10_24 é **melhora de precisão, não regressão**, ao preço de
uma perda ocasional (o item 96). Sem essa auditoria, o número parece um fracasso da IA; com ela,
é o oposto: o léxico estava inflando "publicáveis" com item que não é do tópico que ele diz ser.

### Amostra de 5 classificações que a IA fez e as regras não (TJ-PA, com `topico_evidencia`)
| item | tópico (IA) | confiança | evidência da IA |
|---|---|---|---|
| 51 | `dir-adm-03-poderes-administrativos` | alta | "o comando cita os poderes da administração pública, especificamente a autotutela" |
| 65 | `dir-con-01-constituicao-conceito` | alta | "o comando e o enunciado tratam explicitamente da classificação das Constituições" |
| 79 | `dir-civ-04-prescricao-decadencia` | alta | "o comando cita a prescrição e o enunciado aborda prazo prescricional" |
| 89 | `dir-civ-01-lei-introducao` | alta | "o comando menciona a eficácia das leis no espaço (LINDB)" |
| 93 | `dir-pro-civ-03-atos-processuais` | media | "o comando trata da valoração da prova com base no Código de Processo Civil" |

As cinco batem com o enunciado real do item (conferido à mão): 51 é sobre autotutela (poder de
rever atos), 65 sobre classificação de Constituições, 79 sobre prazo prescricional de
benfeitorias, 89 sobre LINDB/eficácia da lei no espaço, 93 sobre valoração de prova no CPC —
nenhuma parece invenção; são exatamente os tópicos que o léxico por regras não tinha termo para
casar (por isso ficavam "sem tópico" antes). Estes cinco continuam corretos na correção do
método acima — nenhum dos cinco é item anulado nem muda de lado.

### 4. `thinking_budget` — item cancelado, não pendente
O passo 12b deixou como pendência "medir se a resposta continua correta com
`thinking_budget=0`". Não sobrou o que medir: o achado do item 2 já respondeu — o modelo em uso
não aceita o campo. Fechado.

### Verde (passo 12c)
`uv run pytest -q`: `279 passed, 5 skipped`. `bash scripts/checar.sh` na raiz: ruff, `ruff
format --check`, `mypy --strict` (92 arquivos), import sem efeito colateral — tudo verde.

### Qual modelo classificou o quê (para não esquecer daqui a um mês)
- **`gemini-3.6-flash`**: gera o `DnaConcurso` do edital (`analista-de-edital`, V2) — nunca
  classificou questão nenhuma.
- **`gemini-3.5-flash-lite`**: classifica o tópico de cada item de prova desde o passo 12c —
  é o modelo por trás das 63 publicáveis atuais (37 + 19 + 7) que têm `topico_confianca` "alta"
  ou "media" com evidência em português corrido (não a frase fixa de `ClassificadorPorRegras`,
  do tipo "contém o termo […] do tópico" ou "cita a Lei nº […]").
- **Por regras (`ClassificadorPorRegras`)**: nenhuma questão atual foi classificada só por
  regras sem depois passar pela reclassificação com IA — as três rodadas do passo 12 (regras)
  foram todas sobrescritas pelas do passo 12c (IA) via `--reclassificar`. Continua sendo o
  fallback de qualquer lote que a IA não conseguir responder (ver passo 12b, item 3).

### Arquivos do passo 12c
Tocados: `backend/aprovaos/config.py`, `.env.example`, `backend/aprovaos/roteador/custo.py`,
`backend/aprovaos/agentes/classificador.py`, `backend/tests/{test_config,test_roteador,
test_classificacao}.py`, `docs/fatias/V3-execucao.md` (este bloco), `docs/02-produto.md` (§6).
Banco real (`backend/dev.db`, fora do git): mesmas 210 questões, agora **63 publicáveis** (era
43) — 12 linhas novas em `traco`, todas `resultado="ok"`.

## Rodada de correção dos passos 12/12b/12c

Revisão trouxe 3 Importantes + 1 Menor; o dono rodou a auditoria do TRT10 que tinha ficado em
aberto (§ acima, já incorporada) porque o revisor deste projeto é read-only, sem `Bash`.

### Importante 1 — números "só IA"/"só regras" corrigidos
Ver "Correção do método", na seção da tabela antes × depois acima: o método antigo não aplicava
`decidir_publicacao` por inteiro (ignorava `gabarito_status`), contando itens anulados como se
fossem "publicáveis só pela IA". Corrigido; as três linhas agora fecham
(`regras + só IA − só regras = IA`).

### Importante 2 — auditoria do TRT10: 8 dos 9 itens eram falso positivo do léxico
Ver "Auditoria dos 9 itens…", na mesma seção acima. Conclusão do dono, registrada com as
palavras dele: o "12 → 7" do TRT10_24 é **melhora de precisão, não regressão** — a IA filtrou
lixo do léxico por regras, ao custo de um falso negativo real (item 96, P-29).

### Importante 3 — `curar_documento` agora confere que prova e gabarito são o mesmo par
`ParDivergente` (`motor/curar.py`): `_conferir_par(documento_prova, documento_gabarito)` compara
`evento`/`cargo` dos dois `Documento` (os mesmos dois campos que `_origem_base` já deriva) logo
depois de carregá-los, antes de ler qualquer PDF. Chamar `curar_documento` com um par trocado
(prova de um evento/cargo, gabarito de outro) levanta `ParDivergente` em vez de gerar `Origem` e
gabarito silenciosamente errados. Dois testes novos: par de eventos diferentes
(`TJ_PA_25_SERVIDOR` × `STJ_24`) e mesmo evento com cargo diferente (`CARGO 9` × `CARGO 18`).

### Menor — todo modelo default de `Configuracoes` tem preço tabelado
`test_todo_modelo_default_de_configuracoes_tem_preco_tabelado` (`test_roteador.py`): itera os
campos `modelo_*` de `Configuracoes` e confere que o valor default de cada um está em
`PRECOS_USD_POR_MILHAO`. Passou de primeira (nada estava quebrado); existe para a **próxima**
troca de modelo não quebrar o roteador só em produção.

### Importante 4 — ADR-0018 e `06-custos.md` ganharam adendo de 18/09/2026
`docs/DECISOES.md` (ADR-0018) e `docs/06-custos.md` (§7, novo) registram: `gemini-2.5-flash`
responde 404 para chave nova; `modelo_dna` = `gemini-3.6-flash`, `modelo_classificacao` =
`gemini-3.5-flash-lite`; preços novos com fonte (18/09/2026); `gemini-3.5-flash-lite` rejeita
`thinking_config`; free tier real = R$ 0,00, cota de 5 req/min e **20 req/dia por modelo**.

### `docs/PENDENCIAS.md`
P-27 reescrita: a chave existe desde 18/09/2026, o bloqueio agora é a cota diária (20 req/dia
por modelo), não a falta de chave — os testes `llm` continuam sem rodar. P-29 nova: o item 96 do
TRT10_24 (Importante 2) — a IA deixou sem tópico um item que o léxico por regras acertava; caso
isolado, registrado para quando houver mais dado para comparar.

### Verde (rodada de correção)
`uv run pytest -q`: `282 passed, 5 skipped` (eram 279; +3: os dois testes de `ParDivergente` e o
de preço tabelado). `bash scripts/checar.sh` na raiz: ruff, `ruff format --check`, `mypy
--strict` (92 arquivos), import sem efeito colateral — tudo verde.

### Arquivos da rodada de correção
Tocados: `backend/aprovaos/motor/curar.py` (`ParDivergente`, `_conferir_par`),
`backend/tests/{test_motor_curar,test_roteador}.py`, `docs/DECISOES.md` (ADR-0018),
`docs/06-custos.md` (§1 e §7 novos), `docs/PENDENCIAS.md` (P-27, P-29), `docs/fatias/V3-execucao.md`
(este bloco e a correção da tabela antes × depois acima).

## Passo 15 — Fechamento documental e o limite honesto da V3

Executado em 18/09/2026. Sem código de produção — só docs, decisões e pendências (ADR-0033,
0034, 0035; `docs/RISCOS.md` R-21; `docs/PENDENCIAS.md`; `docs/02-produto.md` §6; `CLAUDE.md`).

### Erro cometido e corrigido no próprio fechamento: o edital usado na curadoria é fictício
Conferindo a tela do concurso no fechamento da fatia, um rascunho deste passo leu
`knowledge/fixtures/editais/edital-assessor-gabinete.pdf` (o mesmo PDF cujo `edital_id` foi usado
em toda a execução real do passo 12/12b/12c) como se fosse o edital **real** da Linda: §1.1 diz
banca "Fundação de Apoio à Unioeste"; §6.1 diz "50 questões de múltipla escolha com 5 alternativas
(A a E), sem desconto". Com base nisso, a P-17 chegou a ser marcada como fechada e três outros
arquivos (`docs/DECISOES.md`, `docs/02-produto.md` §6, `CLAUDE.md`) chegaram a afirmar que a banca
real da Linda é a Unioeste/COGEPS com prova A–E — **está errado, e o erro é meu**. O arquivo é
**fictício**: gerado por `scripts/gerar_fixture_pdf.py` a partir de
`docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md`, cujo próprio
cabeçalho diz "Fixture — trecho de edital (**fictício**, no formato usual de câmaras municipais do
PR)… **Não é um edital real; os números e datas são inventados para o teste**". Eu li o texto do
PDF e não li o cabeçalho da fonte que o gera. Corrigido no mesmo dia: P-17 **reaberta** em
`docs/PENDENCIAS.md` (com o relato do engano registrado nela, para não se repetir); as três
afirmações erradas removidas de `docs/DECISOES.md` (adendo da ADR-0035), `docs/02-produto.md` §6 e
`CLAUDE.md`. O que se sabe de verdade sobre a banca da Linda continua sendo só o da Fase 4: ela
presta concursos locais em Cascavel-PR, cargo de assessor de gabinete, área de Direito — **banca
desconhecida**.

**O limite honesto do que a V3 entregou, dito com todas as letras (agora corrigido):** a curadoria
real (passos 12/12b/12c) rodou contra o `edital_id` gerado a partir desse **edital de teste
fictício**, não contra o edital real da Linda — os 36 tópicos e a cobertura de 63/210 publicáveis
valem para esse edital de teste, e ainda não sabemos se valem para o dela. As **210 questões** em
si são reais (prova e gabarito de verdade, baixados da API da Cebraspe); o que é fictício é o
edital contra o qual elas foram classificadas. Além disso, as 210 questões são **certo/errado da
Cebraspe** — úteis como **conteúdo** de Direito, matéria que provavelmente se sobrepõe à do
concurso real dela (ADR-0027) —, mas não necessariamente no **formato** que ela vai encontrar de
verdade, que continua desconhecido (P-17). Isso não é demérito da fatia: o cano inteiro (coletor →
curador → gate de publicação → telas) é agnóstico de banca e de formato de item — é esse desenho
que permite a V3b ser uma fatia pequena quando a banca real for conhecida, reaproveitando tudo que
a V3 construiu em vez de recomeçar do zero. Mas quem ler este diário daqui a um mês precisa saber,
sem precisar garimpar: **a V3 valida o cano com conteúdo real da Cebraspe, sobre um edital de
teste; falta plugar o edital real da Linda quando ele chegar (P-17)**.

### Consequência para a V3b (registrada em P-30, `docs/PENDENCIAS.md`)
A V3b (múltipla escolha A–E) é decisão do dono de 18/09/2026 pelo formato **dominante no mercado
de concursos brasileiro** (certo/errado é marca da Cebraspe, a exceção) — **não** porque se
conheça o formato do concurso real da Linda, que continua indefinido (P-17). O caderno e o
gabarito do `TJ_CE_23_SERVIDOR` (A–E, real, coletado no passo 5 desta fatia e fora do escopo por
decisão J do plano) são o **primeiro fixture** para o segmentador A–E. Quando o edital real dela
chegar e a banca for identificada, mapear essa fonte específica com a skill `monitor-de-fontes`
antes de coletar dela — isso ainda não aconteceu.

### Números finais da V3, para não garimpar em outro lugar
4 concursos coletados (`TJ_PA_25_SERVIDOR`, `STJ_24`, `TRT10_24` com 2 cargos, mais
`TJ_CE_23_SERVIDOR` coletado e não curado por ser A–E), 10 PDFs, 1,3 MB no repositório; **210
questões** na base; **63 publicáveis** (classificação por regras isolada dava 43; com IA em lote
foi a 63) — TJ-PA 12→37, STJ_24 19→19 (saldo neutro), TRT10_24 cargo 12 12→7 (**ganho de
precisão**, não regressão: 8 dos 9 itens "perdidos" pela IA eram falso positivo do léxico por
regras, auditado item a item). Modelos: `gemini-3.6-flash` para o DNA do edital (V2), nunca usado
para classificar questão; `gemini-3.5-flash-lite` para a classificação de tópico desde o passo
12c. Suíte: **298 passed, 5 skipped** antes de o redesenho de UX (protótipo validado com a piloto)
começar a tocar `web/templates/**` e as rotas de questões/editais em paralelo a este passo — este
fechamento documental não altera nem depende desse redesenho, que segue em andamento por outro
agente.

### O que este passo fechou, abriu e não tentou fechar
Fechada: **P-26** (grupo com acento). **P-17** (banca e formato da Linda) **continua aberta** — um
rascunho deste passo chegou a marcá-la como fechada com base num fixture fictício lido por engano
como edital real; corrigido no mesmo dia (ver "Erro cometido e corrigido…" acima). Abertas:
**P-30** (V3b — A–E, pelo formato dominante no mercado, não pela banca real dela), **P-31**
(cobertura de tópicos e reclassificação com IA quando houver cota), **P-32**
(`fonte.politica`/`ultima_varredura`/`proxima` sem consumidor), **P-33**
(`questoes/topico.html` não renomeado para `resolver.html`, divergência nominal com o plano).
Confirmada, não fechada: **P-29** (item 96 do TRT10_24) — caso isolado, nada novo desde o
passo 12c. ADR-0033 (gate de publicação sem validador para original; `questao` é pool global),
ADR-0034 (dependências: `httpx2` em runtime, `pyyaml`/`types-pyyaml` em dev) e ADR-0035 (política
de coleta da Cebraspe, identidade `{eventoURL}/{nomeArquivo}`, com o adendo de que a Cebraspe é
fonte de conteúdo, não de formato, para o piloto) entram em `docs/DECISOES.md`. `docs/RISCOS.md`
ganha R-21 (política de dados do free tier do Gemini).

## Passo 16 — Reclassificação das 250 questões contra o edital real do TJ-PR (P-31, avanço)

Executado em 19/09/2026, na mesma máquina (`backend/dev.db`, sem Docker). Só execução — nenhum
código de produção mudou; os dois comandos usados já existiam (`registrar_edital`/`gerar_dna` da
V2, `curar_documento(..., reclassificar=True)` da V3/passo 12b). Objetivo: testar a hipótese de
que a baixa cobertura do passo 12 vinha do **vocabulário fictício** (fixture da Fase 4, 36
tópicos), não da classificação em si — agora que dois editais **reais** estão no repositório desde
18/09 (ADR-0038): `edital-tjpr-tecnico-judiciario-2025.pdf` (Instituto AOCP, 9 matérias/99
tópicos) e `edital-trt9-fcc-2022.pdf` (FCC, 25 matérias/580 tópicos).

**Passo 1 — subir o edital do TJ-PR pelo pipeline de verdade.** Script de uma vez
(`validar_pdf` → `extrair_texto` → `extrair_conteudo_programatico` → `gerar_dna` →
`registrar_edital` → commit — as mesmas funções de `api/editais.py::processar_edital`, sem
servidor HTTP) para a conta de `linda.piloto@exemplo.com`, já existente desde a V1. Parser
confirmou os 9 matérias/99 tópicos já medidos na V2 (ADR-0038). O DNA por IA (`gemini-3.6-flash`)
falhou com `503 UNAVAILABLE` (modelo sobrecarregado — a cota diária desse modelo já estava perto
do fim por outro trabalho em paralelo na fatia 6, 25 erros antes deste) e caiu para
`AnalistaPorRegras` (`gerar_dna` nunca bloqueia, arquitetura §8) — sem efeito na cobertura de
tópicos, que vem do parser/`registrar_edital`, não do DNA. Segundo concurso na base: "TRIBUNAL DE
JUSTIÇA DO ESTADO DO PARANÁ" / cargo `desconhecido` (o parser por regras não confirma o cargo sem
prova de conceito na cláusula, ADR-0036) / banca "Instituto AOCP" — o fictício (`edital-assessor-
gabinete.pdf`) continua na base, intocado (P-17 segue aberta; o TJ-PR **não** é o edital real da
Linda, é o primeiro edital real disponível para testar o vocabulário contra as 250 questões).

**Passo 2 — reclassificar as 250 questões.** `curar_documento(db, config, prova_id, gabarito_id,
edital_id=<TJ-PR>, reclassificar=True, tipo_item=...)` para os 4 pares já curados no passo 12
(`TJ_PA_25_SERVIDOR` cargo 9, `STJ_24` cargo 19, `TRT10_24` cargo 12 — C/E — e `TJ_CE_23_SERVIDOR`
cargo 1 — múltipla escolha); `atualizar_classificacao` troca só `topico_id`/`topico_confianca`/
`topico_evidencia`/`publicavel`/`motivo_nao_publicavel` de cada linha (por `hash_dedup`), nunca o
texto/gabarito/origem — a classificação contra o edital fictício foi **sobrescrita** (é o mesmo
campo `Questao.topico_id`, e o vocabulário `Topico` é global por slug, premissa D da V2); a medição
"antes" abaixo foi tirada por SQL direto no `dev.db` **antes** de rodar, para a comparação não
depender de memória. Modelo: `gemini-3.5-flash-lite` (o mesmo do passo 12c) — 14 chamadas, **0
erros**, todo o lote em lotes de 20 (`config.lote_classificacao`); a evidência de cada
classificação (`topico_evidencia`) é texto livre do modelo ("trata de recurso especial e tese
jurídica em IRDR, do tópico de recursos"), não léxico por regras — confirma que a reclassificação
saiu da IA, não do fallback. **Cota do dia consumida por completo**: `gemini-3.5-flash-lite` já
tinha 6 chamadas de outro agente (fatia 6, `gerador-de-justificativa` testando com esse modelo)
antes deste passo; 6 + 14 = **20/20**, o teto diário do free tier medido no passo 12b — não sobrou
cota para reclassificar o TRT9 hoje (fica para P-31, próxima rodada, com o vocabulário de 580
tópicos, o mais amplo que a base tem).

### Antes × depois, por tipo de item (250 questões, mesmas linhas, mesmos textos/gabaritos)

| tipo de item | vocabulário fictício (36 tópicos, passo 12) | vocabulário real TJ-PR/AOCP (99 tópicos) |
|---|---|---|
| certo/errado (210) | 63 publicáveis · 141 sem tópico | **106 publicáveis · 96 sem tópico** |
| múltipla escolha A–E (40) | 2 publicáveis · 38 sem tópico | **31 publicáveis · 7 sem tópico** |
| **total (250)** | **65 publicáveis (26 %) · 179 sem tópico** | **137 publicáveis (55 %) · 103 sem tópico** |

Tópicos do edital do TJ-PR com pelo menos uma questão publicável: **38 de 99** (38 %) — zero antes
desta rodada, porque nenhuma questão apontava para o vocabulário dele. A `Questao` continua sendo
um pool global (ADR-0033): o `topico_id` de cada linha agora resolve contra o TJ-PR; consultar
`contagem_por_topico` para o edital fictício depois deste passo dá zero em quase todos os tópicos
dele — a base não foi apagada (concurso, edital, DNA e as 250 linhas de `questao` continuam
intactos), só a classificação de tópico, que é um campo só por linha, migrou de vocabulário.

**O que este número não prova, dito com todas as letras (pedido explícito do dono):** o vocabulário
do TJ-PR é de **nível médio** (Técnico Judiciário); várias das 250 questões vêm de cadernos de
nível **superior** (ex.: `STJ_24` cargo 19, `TRT10_24` — analista/cargos técnicos especializados).
Bater o tópico ("Licitações", "Recursos") não significa que a questão está no nível certo para
quem presta um cargo de nível médio — o classificador decide **assunto**, não **dificuldade nem
adequação ao cargo**; `dificuldade_est`/o gate de publicação não filtram por isso hoje. Tratar
55 % como "cobertura pronta para o TJ-PR" seria vender o número além do que ele mede.

### O que não foi feito e por quê
TRT9/FCC (580 tópicos, o vocabulário mais amplo da base) **não** foi reclassificado: a cota diária
de `gemini-3.5-flash-lite` (o único modelo com folga suficiente hoje — `gemini-3.6-flash` já
estava com 25+1 erros no dia, de outro trabalho em paralelo) chegou a 20/20 com as 14 chamadas
deste passo. Fica como próximo passo de P-31, com prioridade sobre reclassificar de novo o mesmo
TJ-PR: o TRT9 é o teste mais forte da hipótese "vocabulário largo cobre mais questão", por ter
quase 6× mais tópicos. Rodar assim que a cota renovar (reset diário do free tier, `docs/06-
custos.md` §7) ou com outro modelo do catálogo (`gemini-2.5-flash-lite`/`gemini-3.1-flash-lite`,
`docs/06-custos.md` §1) se a chave aceitar chamada nova a esses modelos — não testado nesta rodada
por já ter alcançado o objetivo (TJ-PR) com o modelo padrão.

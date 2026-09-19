# Fatia 6 — Trilha + aulas em texto: diário de execução
> O que é: o que foi feito, medido, na fatia 6 — não o plano (`6-trilha-e-aulas.md`).
> Quando ler: para saber o que existe de verdade hoje, com que evidência.

## Estado de partida
Branch `main`, `625f8d5` (fim da fatia 4 — dossiês). 579 testes verdes. Reaproveitado sem
mudança: `dominio/dossie.py` (4 dossiês reais gravados), `dominio/justificativa.py` (o validador
mecânico de referência), `agentes/gerador_de_justificativa.py` (o molde de agente ADK),
`dados/repositorio_fio_memoria.py::estatisticas_topicos_vistos` (histórico real por tópico) e o
popover de lei já em `web/templates/questoes/_resultado.html`.

**Nota de concorrência:** durante esta fatia, outro agente editava `dominio/legislacao.py` e
`tests/test_dominio_legislacao.py` (conforme instrução recebida — não tocados aqui) e, por conta
disso, também `motor/dossie.py`, `tests/test_dominio_dossie.py`, `tests/test_motor_ancorar.py`,
`tests/test_motor_dossie.py` e `tests/test_modelos.py` ficaram com alterações concorrentes não
minhas. `git status` confirmou: nenhum desses arquivos foi tocado por este trabalho, exceto
`tests/test_modelos.py` (uma linha, `"aula"` na lista de tabelas — necessária porque a fatia 6
acrescenta uma tabela e esse teste é exaustivo sobre `Base.metadata.tables`).

## O que foi feito

### 1. Contrato e validador (`dominio/aula.py`, novo)
`EntradaGeradorAula`/`RelacionadoEntrada`/`QuestaoParaAula` (o que o agente recebe) e
`ConteudoAula`/`CitacaoAula`/`RelacionadoAula`/`ComoABancaCobra`/`MnemonicoAula` (o que devolve).
`verificar_aula` — o validador mecânico, no espírito de
`dominio.justificativa.verificar_justificativa_*` — confere: cada citação aponta uma fonte real
do dossiê com `citacao_canonica` batendo e `trecho` existindo literalmente; `frase_da_aula`
existe literalmente no `texto_denso`; todo marcador `{{...}}` do texto resolve para uma citação
conhecida; nenhuma lacuna declarada aparece como marcador; `relacionados`/`como_a_banca_cobra`
só citam o que foi oferecido na entrada (inclusive o `trecho` exato do relacionado); tamanho do
`texto_leigo` ≤ 40 % do denso; tamanho do `texto_denso` dentro de ±20 % de
`tempo_alvo_min × 36`; mnemônico (quando presente) passa pela mesma regra de trecho literal.
`escolher_relacionados` monta o fio da memória (a) reaproveitando
`dominio.fio_memoria.escolher_para_intercalar` (mesmo ranking de erro-recente/tempo-sem-ver),
restrito aos tópicos que têm dossiê. `renderizar_com_notas` troca marcador por nota numerada
(popover sem marcador cru na tela). 17 testes (`tests/test_dominio_aula.py`).

### 2. Trilha (`dominio/trilha.py`, novo)
`montar_trilha`: não visto/fraco (acerto < 70 % ou < 3 respostas) antes de dominado; dentro do
mesmo grupo, maior peso medido primeiro; desempate por slug. 6 testes
(`tests/test_dominio_trilha.py`).

### 3. Persistência (`Aula` em `dados/modelos.py`, migração `0009_aula.py`, `dados/repositorio_aula.py`)
Tabela `aula` conforme `docs/04-modelo-de-dados.md` §3 + extensão desta fatia
(`como_a_banca_cobra`, `lacunas_declaradas`, `mnemonico` — ADR-0040). `salvar_aula`/
`proxima_versao`/`aula_publicada_do_topico`, mesmo desenho de `repositorio_dossie.py`.
`test_migracao_inicial_bate_com_os_modelos` (já existente) confirma a migração bate com o ORM
sem diferença. 5 testes novos (`tests/test_repositorio_aula.py`).

### 4. Agente `gerador-de-aula` (`agentes/gerador_de_aula.py`, `agentes/prompts/gerador-de-aula.md`)
Mesmo molde ADK do `gerador-de-justificativa`: `LlmAgent` + JSON mode, sem `output_schema`,
`include_contents="none"`. `Configuracoes.modelo_aula` novo (`gemini-3.6-flash`, documentado em
`.env.example`). 9 testes (`tests/test_gerador_de_aula.py`).

**Achado real (bug do ADK, não do código desta fatia):** a primeira rodada contra a API real
falhou com `KeyError: "Context variable not found: `citação` ..."` — o motor de template de
instrução do ADK (`google/adk/utils/instructions_utils.py::_render_with_regex`) escaneia a
`instruction` do agente por `{...}`/`{{...}}` e tenta resolver como variável de sessão; um
`var_name` que seja um identificador Python válido (sem espaço) e não exista no estado levanta
`KeyError` — só cai como texto literal se `var_name` **não** for um identificador válido (tem
espaço, pontuação). O prompt tinha um exemplo `` `{{citação}}` `` (uma palavra só, identificador
válido em Python por causa do PEP 3131/Unicode) na seção de regras — corrigido para
`` `{{Lei X art. Y}}` `` (múltiplas palavras, nunca um identificador). O mesmo motivo, aliás, por
trás do teste já existente `test_gerador_de_justificativa.py::test_prompt_existe_e_fala_do_contrato`
(`assert re.findall(r"\{[a-z_]+\}", prompt) == []`) — o mesmo bug de infraestrutura, achado de
novo aqui porque o contrato desta skill *precisa* que o texto gerado contenha `{{...}}` de
verdade (marcador de citação), então o prompt não podia simplesmente evitar chaves.

### 5. Comando `motor/aula.py`
`gerar_aula_topico`: sem tópico/dossiê/IA → relatório, nunca `KeyError`/crash; reprovada → nada
grava; aprovada → `salvar_aula`. Monta `como_a_banca_cobra` só com questões publicáveis reais
(`origem` formatada `"<banca> <ano> <órgão> item <nº>"`) e `relacionados` só com tópicos que
**têm dossiê** no histórico real da aluna. `main()` resolve o usuário por e-mail
(`--usuario-email`), mesmo padrão de `motor.justificar`/`motor.curar`. 7 testes
(`tests/test_motor_aula.py`), incluindo um cenário completo com dossiê real
(`construir_dossie_improbidade`) + tópico relacionado com erro real da aluna.

### 6. Popover, tela de aula e trilha (web)
`web/templates/_macros.html` (novo): a macro `citacao_legal` extraída de
`questoes/_resultado.html` (que agora importa e chama a mesma macro — zero mudança visual, 3
testes de rota existentes confirmam). `GET /topico/{slug}/aula` (`api/questoes.py`) lê a última
aula publicada e renderiza `web/templates/aula/ver.html` (denso/leigo em `<details>`, notas de
citação numeradas com o mesmo popover, fio da memória, "como a banca cobra", lacunas,
mnemônico). `GET /concurso/{id}/trilha` (`api/editais.py`) monta a trilha do edital
(`topicos_de_maior_peso` + `estatisticas_topicos_vistos` + `montar_trilha`) e mostra link para a
aula (quando publicada) e para as questões. Links adicionados em `topico.html` ("Ver aula deste
tópico") e `concurso.html` ("Ver trilha de estudo"). 3 + 4 testes de rota
(`tests/test_rota_aula.py`, `tests/test_rota_trilha.py`).

### 7. Mnemônico (§5 do plano) e grifos (§6 do plano)
Mnemônico: campo opcional do mesmo JSON de saída do `gerador-de-aula` (sem chamada extra de
LLM), validado pela mesma regra de trecho literal (regra 9 de `verificar_aula`). As duas aulas
reais geradas trouxeram mnemônico aprovado (ver §"Geração real" abaixo).
Grifos: fora desta fatia — `docs/PENDENCIAS.md` P-50 (sem `Anotacao` ORM/migração/reancoragem;
entregar sem isso seria uma feature com o nome certo e o comportamento errado).

## Testes — o que mudou
| arquivo | testes |
|---|---|
| `tests/test_dominio_aula.py` | 17 (novo) |
| `tests/test_dominio_trilha.py` | 6 (novo) |
| `tests/test_repositorio_aula.py` | 5 (novo) |
| `tests/test_gerador_de_aula.py` | 9 (novo) |
| `tests/test_motor_aula.py` | 7 (novo) |
| `tests/test_rota_aula.py` | 3 (novo) |
| `tests/test_rota_trilha.py` | 4 (novo) |
| `tests/test_modelos.py` | +0 (mesma contagem; 1 linha ajustada — `"aula"` na lista de tabelas) |

`cd backend && uv run pytest -q` → **639 passed, 6 skipped** (mesmos 6 marcadores
`postgres`/`llm`/`rede` de sempre). Partindo de 579: **+60**, dos quais **51 desta fatia** (soma
da tabela acima) e **9 de `tests/test_dominio_legislacao_estruturas.py`**, arquivo novo da edição
concorrente de outro agente em `dominio/legislacao.py` (fora do escopo desta fatia), presente na
árvore de trabalho no momento em que rodei a suíte inteira.

`uv run mypy` (projeto inteiro) → **0 erros, 145 arquivos**. `uv run ruff check`/`ruff format
--check` → limpos em todos os arquivos desta fatia; **`dominio/legislacao.py` e
`tests/test_dominio_legislacao_estruturas.py` (edição concorrente de outro agente, fora do
escopo desta fatia por instrução explícita) tinham, no momento de fechar esta fatia, 2 avisos de
`ruff check` e 1 de `ruff format --check` não relacionados a este trabalho** — `bash
scripts/checar.sh` para nesse ponto (passo 1/5) por causa deles; rodado manualmente
`ruff check . ../scripts --exclude aprovaos/dominio/legislacao.py` (limpo) e `uv run mypy`
(projeto inteiro, limpo) para confirmar que o restante do repositório — incluindo os arquivos
desta fatia — está saudável.

## Geração real (contra `backend/dev.db`)
Backup tirado antes (`scratchpad/dev.db.bak-fatia6`). Migração `0009` aplicada ao `dev.db`
(`DATABASE_URL=sqlite:///dev.db CHAVE_SECRETA=... uv run alembic upgrade head`).

Cota do free tier: `gemini-3.6-flash` já tinha 26 chamadas registradas em `traco` no mesmo dia
(fatia de justificativa, sessão anterior) — "poucas e boas" seguido à risca: só 2 tópicos
tentados. `MODELO_AULA=gemini-3.6-flash` (`.env` sem sobrescrever — usa o padrão de
`config.py`).

Comando: `uv run python -m aprovaos.motor.aula --topico <slug> --usuario-email
linda.piloto@exemplo.com --edital-id 508314e5-cba3-4799-bb60-9fd3a482b20a --tempo-alvo-min 12`.

`tempo_alvo_min` calibrado por tentativa: a primeira rodada (dry-run, `tempo_alvo_min=25`)
devolveu 418 palavras — bem abaixo da faixa esperada para 25 min (720–1080); o modelo, limitado
a **só o que o dossiê real sustenta** (10 fontes para improbidade — 8 dispositivos da Lei
8.429/1992 + 2 súmulas do STJ; conferido em `backend/dev.db`, `dossie_topico` versão 2, coluna
`fontes`: os arts. 9º/10/11/17 continuavam como lacuna nesse dossiê, a P-40 ainda não tinha sido
regenerada para os dados persistidos — número corrigido em 19/09/2026, era "12" por engano),
simplesmente não tem mais fato para alongar sem inventar — o próprio validador correto, não um
defeito. Recalibrado para `tempo_alvo_min=12` (faixa 345–518 palavras), compatível com o volume
real de cada dossiê.

| tentativa | tópico | resultado | motivo |
|---|---|---|---|
| 1 (dry-run, 25 min) | improbidade | reprovada | tamanho (418 < 720) |
| 2–3 | improbidade | erro | `503 UNAVAILABLE` (sobrecarga do provedor, transitório) |
| 4 (12 min) | improbidade | reprovada | 2 `frase_da_aula` não literais + tamanho (440 > 432) |
| 5 | improbidade | erro | `503 UNAVAILABLE` |
| 6 | improbidade | reprovada | 1 `frase_da_aula` não literal + tamanho (443 > 432) |
| 7 | improbidade | erro | `503 UNAVAILABLE` |
| 8 (12 min) | **improbidade** | **gerada** | — |
| 9 (12 min) | **direitos e garantias** | **gerada** | — |

**9 chamadas reais, 4 `ok` + 5 `erro` em `traco`, custo estimado R$ 0,2546** (paid tier de
referência; free tier real R$ 0,00). **2 aulas publicadas**: `dir-adm-06-improbidade-
administrativa` (versão 1, 2611 caracteres denso / 960 leigo, mnemônico sobre o prazo
prescricional do art. 23) e `dir-con-02-direitos-garantias` (versão 1, mnemônico sobre as
hipóteses de uso de algemas da SV 11) — as duas com **zero lacunas declaradas** e **zero
`relacionados`/`como_a_banca_cobra`** (ver limite honesto abaixo).

## Limite honesto: fio (a) sem dado real nesta rodada (P-52)
`estatisticas_topicos_vistos(db, usuario_id, edital_id)` devolveu **vazio** para
`linda.piloto@exemplo.com` no edital `508314e5...`: o histórico real dela em `evento_estudo`
aponta para tópicos com slug `noc-dir-*` (outro vocabulário), enquanto os 4 dossiês da fatia 4
estão em `dir-*` (vocabulário do parser de edital) — sem sobreposição de `topico_id`, não há
relacionado para citar, e o pipeline **corretamente** não inventou nenhum (regra de ouro). Não
investigada a causa raiz (duplicação genuína de vocabulário entre fatias, ou efeito do outro
agente reprocessando `dev.db` em paralelo durante esta sessão) — registrado em `docs/PENDENCIAS
.md` P-52. **O mecanismo em si está implementado e comprovado**: `tests/test_motor_aula.py
::test_gera_e_publica_quando_aprovado` monta um cenário isolado com vocabulário alinhado (dossiê
real de improbidade + um tópico relacionado com dossiê e um erro real da aluna há 6 dias) e o
pipeline inteiro — geração, validação, persistência — funciona e a aula publicada carrega o
`relacionados` correto.

## O que ficou de fora (declarado, não escondido)
- Áudio (Pro) — excluído pela própria linha 6 do PRD.
- Grifos/anotações (F4.6) — P-50, fatia própria.
- Fio (a) sem demonstração real nesta rodada — P-52 (implementado e testado; sem dado real
  alinhado no `dev.db` no momento da geração).
- Popover de aula sem link "ver na fonte" (a citação tem `trecho` literal, não `url`) — P-51.
- Regeneração automática da aula quando o dossiê muda uma versão — trabalho do job noturno,
  fatia 8 (ainda não existe).
- `dominio/legislacao.py` e sua correção concorrente ficaram fora desta fatia por instrução
  explícita; `bash scripts/checar.sh` completo só volta a passar quando essa edição fechar.

## Correção crítica de 19/09/2026 — `verificar_aula` não validava metade do conteúdo
Uma revisão independente achou três defeitos no caminho "conteúdo gerado → aluna" (visão §4,
"nada gerado existe para o aluno sem validação"), todos em `dominio/aula.py::verificar_aula`:

- **C1 — `texto_leigo` sem checagem própria.** `marcadores_no_texto` só olhava `texto_denso`; a
  regra de lacuna também. O leigo podia citar `{{dispositivo inexistente}}` ou afirmar o que a
  aula declarou como lacuna e ser aprovado. Corrigido: o conjunto de marcadores verificado é
  agora a união de `texto_denso` + `texto_leigo`, e a regra de lacuna usa essa união. Testes
  vermelho→verde: `test_marcador_inexistente_no_texto_leigo_reprova`,
  `test_lacuna_declarada_e_citada_no_texto_leigo_reprova`.
- **C2 — nenhuma regra exigia fonte para uma afirmação.** Os laços do validador só iteravam
  sobre o que o modelo decidiu declarar em `citacoes`; uma `ConteudoAula` com `citacoes=[]` e
  prosa afirmativa passava. Implementado o **gate léxico** (`_frases`/`_frase_exige_citacao`,
  gatilhos `compete`, `vedado(a)`, `somente`, `apenas`, `só`, `prazo`, `quórum` ou um número):
  toda frase de `texto_denso`/`texto_leigo` que casa um gatilho precisa de `{{citação}}` própria,
  senão reprova com o texto da frase no motivo — **decisão do dono, default é reprovar**, aceita
  falso positivo ocasional. Escopo: só os gatilhos lexicais explícitos da correção; "verbo de
  competência" genérico (citado na `SKILL.md`) não é detectável mecanicamente sem NLP e ficou de
  fora — registrado como pendência (`docs/PENDENCIAS.md` P-60). Sentenças do fio da memória (a)
  são sustentadas por `RelacionadoAula.trecho` (conferido à parte, nunca por marcador) — a
  correção não as isenta por regra especial; o teste `test_motor_aula.py::_resposta_valida` foi
  reescrito para não usar palavra de gatilho nessa frase, mesma resposta que o dono aceitou
  (regenerar/reescrever em vez de criar exceção). Testes:
  `test_frase_afirmativa_sem_citacao_reprova`, `test_frase_com_gatilho_normativo_e_citacao_aprova`.
- **C3 — `| safe` no template com texto de LLM.** `web/templates/aula/ver.html` desligava o
  escape do Jinja em `texto_denso`/`texto_leigo` com `| replace(...) | safe`; qualquer `<script>`
  emitido pelo modelo executaria no navegador da aluna, e o `replace` gerava HTML malformado.
  Trocado por `{% for parágrafo in texto.split("\n\n") %}<p>{{ parágrafo }}</p>{% endfor %}`
  (escapado, bem formado — `Jinja2Templates` já usa `select_autoescape()` para `.html`,
  `starlette` 1.6.0). Acrescentada reprovação mecânica quando `texto_denso`/`texto_leigo` contêm
  `<` seguido de letra (`test_tag_html_no_texto_reprova`).
- **I9 — `notas_leigo` calculado e nunca mostrado.** `api/questoes.py::_contexto_aula` já
  montava `notas_leigo`; o template não renderizava. Acrescentado o mesmo `<ol>`/`<details>` da
  versão densa dentro do `<details>` da versão leiga, com `id="citacao-leigo-N"` (a versão densa
  usa `id="citacao-N"`, para não colidir). Testes:
  `test_notas_da_versao_leiga_aparecem_com_id_proprio`, `test_tag_html_no_texto_da_aula_sai_escapada`.

**Reverificação das 2 aulas publicadas no `dev.db`** (`dir-adm-06-improbidade-administrativa` e
`dir-con-02-direitos-garantias`, script pontual carregando `Aula`+`DossieTopico` reais e rodando
`verificar_aula` com `tempo_alvo_min=12`, o mesmo usado na geração): **as duas continuam
aprovadas** pelo validador novo — nenhuma reprovação, nenhuma despublicação necessária.

Suíte: `769 testes verdes, 6 skipped` (`bash scripts/checar.sh` completo, ruff+mypy+import+
pytest). Arquivos tocados: `backend/aprovaos/dominio/aula.py`,
`backend/tests/test_dominio_aula.py`, `backend/tests/test_motor_aula.py` (fixture reescrita, sem
mudar o que o teste prova), `backend/tests/test_rota_aula.py`, `web/templates/aula/ver.html`.

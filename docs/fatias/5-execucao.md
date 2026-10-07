# Fatia 5 — Questões inéditas validadas: diário de execução
> O que é: o que foi feito, medido, na fatia 5 — não o plano (`5-questoes-ineditas.md`).
> Quando ler: para saber o que existe de verdade hoje, com que evidência.

## Estado de partida
Branch `main`, commit `cf91dce`. Não medi a contagem de testes exata neste commit (stashar a
árvore para checar arriscaria o trabalho não commitado dos outros dois agentes presentes nela —
ver nota abaixo); a contagem final da fatia, com os três trabalhos somados, está em "Testes — o
que mudou". Reaproveitado sem mudança: `dominio/justificativa.py` (a disciplina de "trecho literal na fonte" e a normalização
de citação), `dominio/questao.py` (`Letra`, `decidir_publicacao` como referência de gate),
`agentes/gerador_de_aula.py` (o molde exato de agente ADK), `motor/aula.py` (o molde de comando:
teto → agente(s) → validador → publica ou não), `dossie_topico`/`dna_concurso` das fatias
anteriores.

**Nota de concorrência:** dois outros agentes trabalhavam, ao mesmo tempo, em
`dominio/{estatistica,curva,padroes,previsao,resumo_semanal,plano}.py`, `motor/plano.py`,
`api/plano.py` e `web/templates/hoje/` (fatias de painel/plano do dia). Nenhum desses arquivos
foi aberto ou tocado aqui — `git status`/`git diff` confirmam. `scripts/checar.sh` (`ruff format
--check`) parou em `aprovaos/dados/repositorio_painel.py` e `tests/test_rota_painel.py` — dois
arquivos de fora do meu escopo, não formatados no momento em que rodei a checagem; contornado
rodando `ruff check`/`ruff format --check`/`mypy`/`pytest` restritos aos meus arquivos (todos
limpos) e confirmando, por leitura, que a única falha do `ruff format --check` do repositório
inteiro estava nesses dois arquivos alheios.

## O que foi feito

### 1. `dominio/questao_inedita.py` (novo, puro) — o contrato e o Passo 0
`Mecanismo`, `AlternativaGerada`, `QuestaoGerada` (campo a campo do contrato da skill —
`publicado` sempre `False`, `marcacao` fixa "inédita validada — pendente"), `OriginalParaGerador`,
`EntradaGeradorQuestao`, `ItemDoPlano`, `PlanoDoLote` e `montar_plano_do_lote`/`conferir_lote`.
`montar_plano_do_lote` é 100 % determinístico: `literal = n // 5`; o resto (e o gabarito) são
distribuídos por `_round_robin`, uma função só, reaproveitada nas duas contagens — mesma ordem
fixa do cabeçalho de exemplo da skill (`troca_de_verbo, troca_de_competencia, troca_de_quorum,
excecao_omitida, troca_de_prazo`). `PlanoDoLote.itens` já sai pronto com o mecanismo/gabarito
prescrito de cada item — é o que o motor usa para pedir, a cada chamada, exatamente um item (ver
§4). 18 testes (`tests/test_dominio_questao_inedita.py`).

### 2. `dominio/validacao_questao.py` (novo, puro) — os cinco itens do validador
`Veredito`, `EntradaValidadorQuestao`/`ResolucaoValidador` (o contrato pobre do segundo agente —
sem gabarito, sem `trecho_que_decide`, sem mecanismo), `verificar_forma` (comando obrigatório e
≤ 40 palavras/uma afirmação só/sem "sempre-nunca" gratuito em C/E; cinco alternativas homogêneas
em A–E), `verificar_fontes` (cada `fontes[i]` existe no dossiê oferecido e `trecho_que_decide`
está, literalmente, em pelo menos uma delas), `similaridade_lexica` (Ruling 43: cosseno de
TF-IDF com stdlib `math`/`collections`, sem embedding) e `julgar`, que soma os cinco itens da
skill, incluindo a checagem de "consequência acrescentada" (o erro que a própria skill
documenta: uma oração do enunciado, fora do trecho que deveria sustentá-lo — detectado por uma
lista fechada de marcadores léxicos como `_MARCADORES_DE_CONSEQUENCIA`, mesmo espírito do gate
léxico de `dominio.aula.verificar_aula`). `aderencia_pct` é decidido pela contagem real de
originais recebidos por `julgar` (não pelo autorrelato `item.aderencia_medida` do gerador — o
validador confere pelos próprios dados). 20 testes (`tests/test_dominio_validacao_questao.py`).

### 3. Agentes ADK (`agentes/gerador_de_questao.py`, `agentes/validador_de_questao.py`)
Mesmo molde exato de `agentes/gerador_de_aula.py` (`LlmAgent` + `Runner`, JSON mode sem
`output_schema`, `include_contents="none"`, prompt em arquivo versionado,
`prompts/gerador-de-questao.md`/`prompts/validador-de-questao.md`). **Decisão de implementação
(faz o Passo 0 valer de verdade):** uma chamada ao `gerador-de-questao` produz **um único item**,
com `mecanismo_alvo`/`gabarito_alvo` já prescritos pelo `PlanoDoLote` — não um lote inteiro numa
resposta só, como o exemplo textual da skill sugere. O plano já foi decidido por regra
determinística antes de qualquer chamada (§1); pedir um item por vez mantém a auditoria
(`conferir_lote`) tratável e cumpre a Ruling 44 ("duas chamadas por item") de forma literal: uma
ao gerador, uma ao `validador-de-questao` (família de prompt **diferente**, que nunca recebe o
gabarito nem o `trecho_que_decide` do gerador — só comando/enunciado/alternativas e o dossiê).
`Configuracoes.modelo_questao`/`modelo_validador_questao` novos (`gemini-3.6-flash`, mesmo corte
de `modelo_aula`/`modelo_justificativa` — escrever ou resolver um item é raciocínio, não
classificação), documentados em `.env.example`. 9 + 9 testes (`tests/test_gerador_de_questao.py`,
`tests/test_validador_de_questao.py`).

### 4. `motor/preencher.py` (novo) — relatório de cobertura e a Ruling 45
`montar_relatorio_cobertura` (publicáveis + tem_dossiê + tem_aula por tópico do edital, reaproveitando
`repositorio_questao.contagem_por_topico`, `repositorio_dossie.dossie_mais_recente_do_topico`,
`repositorio_aula.aula_publicada_do_topico`), `montar_encomendas` (só tópico com dossiê **e**
zero publicáveis — Ruling 45, literal) e `topicos_sem_dossie_para_encomenda` (a lacuna declarada
para quem não tem dossiê, nunca geração às cegas). `main()` só lê e imprime — não grava nada. 4
testes (`tests/test_motor_preencher.py`).

### 5. `motor/gerar_questao.py` (novo) + `dados/repositorio_veredito.py` (novo) + migração `0016`
`gerar_questoes_topico`: busca tópico/dossiê, monta até 5 originais publicáveis do mesmo tópico
como referência de estilo, calcula o plano (§1) e, para cada item do plano, chama o gerador →
chama o validador → julga (§2) → grava a `Questao` **sempre**, aprovada ou reprovada, com
`salvar_questao_inedita` (novo em `dados/repositorio_questao.py`) — RF-28, "rejeição registrada
com motivo", nunca descartada em silêncio. Cada tentativa de julgamento vira uma linha em
`veredito_questao` (`dados/repositorio_veredito.py`; tabela nova, Alembic `0016`, append-only,
histórico completo — `Questao.validada_em`/`validador_versao` sozinhos só guardam a última
tentativa). Falha do **gerador**: item vira `status="erro"`, nada é gravado (não existe o que
gravar). Falha do **validador**: o item gerado existe e **é gravado**, sempre `publicavel=False`
com o motivo da falha — a regra "nada gerado chega ao aluno sem validação" não abre exceção para
"o validador não respondeu". Ao final do lote, `conferir_lote` audita o que de fato saiu do
gerador contra o plano. 9 + 4 testes (`tests/test_motor_gerar_questao.py`,
`tests/test_repositorio_questao.py::TestSalvarQuestaoInedita`) + 4 testes de
`dados/repositorio_veredito.py` (`tests/test_repositorio_veredito.py`).

### 6. Selo da inédita na tela (`api/questoes.py`, `web/templates/questoes/_cartao_questao.html`,
`_resultado.html`, `web/static/css/base.css`)
`contexto_questao` passa a incluir `questao["inedita"]`; os dois parciais trocam o bloco de
origem de prova (que uma inédita não tem — `questao.origem` é `None`) pelo selo `.selo--inedita`
("Questão inédita do AprovaOS — validada contra o dossiê deste tópico, nunca extraída de uma
prova real"), cor de alerta (`--cor-alerta`/`--cor-alerta-suave`, tokens já existentes) — nunca
confundido com o verde de "ok" nem o âmbar do "por quê". 3 testes de rota
(`tests/test_rota_questoes.py`), incluindo um que prova que uma original **não** ganha o selo.

## Testes — o que mudou
| arquivo | testes |
|---|---|
| `tests/test_dominio_questao_inedita.py` | 18 (novo) |
| `tests/test_dominio_validacao_questao.py` | 20 (novo) |
| `tests/test_gerador_de_questao.py` | 9 (novo) |
| `tests/test_validador_de_questao.py` | 9 (novo) |
| `tests/test_motor_preencher.py` | 4 (novo) |
| `tests/test_motor_gerar_questao.py` | 9 (novo) |
| `tests/test_repositorio_veredito.py` | 4 (novo) |
| `tests/test_repositorio_questao.py` | +3 (`TestSalvarQuestaoInedita`) |
| `tests/test_rota_questoes.py` | +3 (selo da inédita) |
| `tests/test_modelos.py` | +0 (1 linha ajustada — `"veredito_questao"` na lista de tabelas) |

Total desta fatia: **79 testes novos/ajustados**. `cd backend && uv run pytest -q` →
**1025 passed, 6 skipped** (mesmos marcadores `postgres`/`llm`/`rede` de sempre) ao final, já
somando o trabalho concorrente dos outros dois agentes presente na árvore no momento da corrida.
`uv run mypy` (projeto inteiro) → 1 erro **pré-existente e alheio**
(`tests/test_rota_publico.py:22`, `dominio.dna` não reexporta `DESCONHECIDO` — arquivo não
tocado por nenhum dos três agentes desta rodada, confirmado por `git status`); os arquivos desta
fatia estão limpos em `ruff check`/`ruff format --check`/`mypy`. Prova de import sem efeito
colateral (`scripts/checar_import.py`) passa com os módulos novos (104 módulos importados).

## Geração real (contra `backend/dev.db`)
Sem Docker disponível nesta sessão — usado o caminho alternativo do `CLAUDE.md` (`DATABASE_URL
sqlite:///dev.db`). Backup tirado antes de migrar (`backend/dev.db.bak-fatia5`, removido depois
de confirmar sucesso). Migração `0016` aplicada (`uv run alembic upgrade head`, `0014 → 0016`).

**Relatório de cobertura real** (`motor.preencher`):
- Edital de Cascavel/Unioeste (fixture, P-17 — 36 tópicos): **4 encomendas** possíveis
  (`dir-con-02-direitos-garantias`, `dir-adm-06-improbidade-administrativa`,
  `dir-pro-civ-03-atos-processuais`, `dir-pro-civ-05-recursos-apelacao` — todos com dossiê e
  zero publicáveis) e **32 tópicos em lacuna** (sem dossiê ainda).
- Edital real do TJ-PR/Instituto AOCP (99 tópicos): **0 encomendas** — dos 4 tópicos com
  dossiê, todos já têm questão publicável (herdada da reclassificação da V3/P-31); **61 tópicos
  em lacuna** (sem dossiê e sem publicável) — número batendo com o que a V3/P-31 já tinha
  registrado (38 dos 99 tópicos com questão, dos quais 4 também têm dossiê: 99 − 4 − 34 = 61).

**Cota do dia:** `gemini-3.6-flash` já tinha, no `traco` de hoje, **36 chamadas** de outras
fatias rodando em paralelo (5 ok + 31 erro, majoritariamente `RespostaDoModeloAusente`/instabilidade
do provedor) antes de eu começar — a cota estava visivelmente contendida. Segui a Ruling 44 à
risca: lote pequeno, sem repetir chamada por causa de cota.

**Execução real:** `python -m aprovaos.motor.gerar_questao --edital-id
508314e5-cba3-4799-bb60-9fd3a482b20a --topico dir-adm-06-improbidade-administrativa --n 1`.

- **n pedido:** 1 (tipo_item resolvido do DNA do edital: `multipla_escolha`; mecanismo prescrito
  pelo plano: `troca_de_verbo`; gabarito prescrito: `A`).
- **n gerado:** 1 tentativa produziu conteúdo (a 1ª falhou antes de gerar nada — ver abaixo).
- **n aprovado:** 1.
- **n reprovado:** 0.
- **Motivos de falha:** a 1ª chamada ao `gerador-de-questao` terminou sem resposta final
  (`RespostaDoModeloAusente`) — a causa de fundo, visível no traceback real, foi um `503
  UNAVAILABLE` do provedor ("This model is currently experiencing high demand"); nada foi
  gravado para essa tentativa (não existe item para gravar — só o "erro" ficou no relatório do
  comando, não no banco). A 2ª chamada (mesmo item do plano) gerou e o `validador-de-questao`
  aprovou de primeira — a resolução independente bateu com o gabarito do gerador, e a fonte
  citada (Súmula 651 do STJ, presente no dossiê real de improbidade) sustenta literalmente a
  `justificativa_certo`.
- **Chamadas feitas:** 3 reais (`gerador-de-questao` erro, `gerador-de-questao` ok,
  `validador-de-questao` ok). **Custo estimado:** R$ 0,029634 (tabela do paid tier, ADR-0018; o
  free tier real desta chave é R$ 0,00).

**A questão gravada** (`Questao.id = 57066ddc-6f89-4ab5-aeec-9c598c475501`, `inedita=True`,
`origem=None`, `publicavel=True`): múltipla escolha sobre a Súmula 651 do STJ (a autoridade
administrativa pode aplicar a pena de demissão por improbidade sem condenação judicial prévia),
cinco alternativas homogêneas, `justificativa_certo`/`justificativa_errado` ancoradas no dossiê
real do tópico — nenhum dado inventado, nenhuma citação fora do que o dossiê de
`dir-adm-06-improbidade-administrativa` já tinha.

`backend/dev.db` fica com essa questão real, mais a tabela `veredito_questao` com as duas linhas
de histórico (uma por tentativa de validação, incluindo a que nunca chegou a gerar — essa fica
só no relatório do comando, não em `veredito_questao`, porque o veredito é sobre um item que
existe; um item que falhou antes de nascer não tem o que julgar).

## O que ficou fora (fora de escopo desta fatia)
- Aderência por **embedding** e a extensão `vector` (Ruling 43) — `docs/PENDENCIAS.md` P-66.
- Suíte DeepEval em `eval/` — depende de cota e de amostra rotulada que ainda não existem —
  `docs/PENDENCIAS.md` P-67.
- Geração em escala para banca desconhecida (P-17, continua aberta — a banca real da Ana
  ainda não chegou).

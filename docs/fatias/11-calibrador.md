# Fatia 11 — Calibrador: plano

> O que é: o plano da fatia 11 do PRD (`docs/02-produto.md` §6, linha "Calibrador — eventos →
> dificuldade, sinalização"). Quando ler: antes de executar qualquer passo desta fatia e ao
> revisar o que foi feito; o diário fica em `11-execucao.md`.

**Ponto de partida:** 769 testes verdes (2 falhas pré-existentes em
`test_dominio_legislacao_estruturas.py`/`test_motor_dossie.py`, de edição concorrente em
`dominio/legislacao.py` por outro agente — fora do escopo desta fatia, não tocar). `evento_estudo`
(append-only, `acertou`/`confianca_declarada`/`tempo_ms`/`dados`), `reporte_erro`
(`aberto`/`analise`/`corrigido`/`improcedente`), `questao` (`dificuldade_est`,
`discriminacao_est`, `publicavel`, `publicada`, `despublicada_em`, `validada_em` — as cinco
últimas vazias em 100 % da base hoje). Skill: `.claude/skills/calibracao-de-questoes/SKILL.md`.

**Realidade dos dados (não inventar volume):** `dev.db` da Linda tem ~19 `evento_estudo` de uma
única aluna. Nenhuma questão real terá `n ≥ 30` — a execução contra `dev.db` é honesta sobre isso
e não fabrica evento nenhum lá (mesma cautela da fatia 7). O mecanismo é validado com séries
sintéticas **declaradas como tais**: a fixture de referência é a mesma que testou a skill na fase
4 (`docs/evidencias/2026-09-17-fase4-skills/fixtures/eventos-calibracao.json`, "números
inventados"), estendida em `knowledge/fixtures/calibracao/eventos-calibracao.json` com os casos
que faltavam (R-6/R-8/R-9).

## 1. O que a skill pede (contrato desta fatia)

Ler `.claude/skills/calibracao-de-questoes/SKILL.md` inteira antes de codificar. Resumo do
contrato: `MetricasQuestao` por questão (janela de 14 dias) → `avaliar_questao` decide uma de
`manter`/`ajustar`/`sinalizar`/`despublicar` pela **primeira regra que casa** (R-0..R-9); toda
questão calibrada grava uma linha em `calibracao`; toda `despublicar`/`sinalizar` cita a regra e
os números (`evidencia`); a fila humana cabe em ≤ 20 min; o que não cabe vira
`fila_humana_adiada`; padrões viram `retroalimentacao_gerador`.

## 2. Os dois pontos que mandam nesta fatia

### 2.1 `discriminacao_est` — o que ela é aqui e o piso

A skill diz "`discriminacao`: desconhecido se n < 30 senão calculada", sem fórmula. Fórmula
escolhida: **correlação ponto-bisserial item-resto**, o índice clássico de discriminação da
Teoria Clássica dos Testes (Crocker & Algina, *Introduction to Classical and Modern Test Theory*,
cap. 16 — mede se quem vai bem no resto das questões da janela também acerta este item). Por
resposta à questão N: cruza `acertou` (0/1) com o desempenho do respondente nas **demais**
respostas da mesma janela (exclui a própria questão, evita autocorrelação). A correlação de
Pearson entre as duas séries é a discriminação estimada, `[-1, 1]`.

Piso duplo, os dois documentados no código:
- `n < 30` → `"desconhecido"` (o piso que a skill já dá).
- `n ≥ 30` mas variância zero em qualquer uma das duas séries (ex.: uma única respondente, todo
  mundo acertou, todo mundo tem o mesmo desempenho-resto) → `"desconhecido"` também, com o motivo
  ("sem variância para correlacionar") — nunca um número fabricado por divisão que daria `NaN`.

Isso destrava o consumo do ADR-0022 no diagnóstico (fatia 7): a partir desta fatia,
`discriminacao_est` tem produtor; o diagnóstico continua sendo tarefa de fatia futura (fora de
escopo aqui — não tocar `dominio/diagnostico.py`).

### 2.2 P-34 — a consulta da tela ignora `publicada`/`despublicada_em`

**Decisão:** a consulta da tela passa a filtrar `Questao.despublicada_em.is_(None)` **além de**
`publicavel.is_(True)`, em todo ponto de leitura que serve conteúdo
(`repositorio_questao.proxima_questao`/`contagem_por_topico`/`questoes_publicaveis_do_topico`,
`api/questoes.py::questao_valida_para_responder`, `api/diagnostico.py`, `motor/dossie.py`,
`motor/ligar_por_topico.py`). O calibrador, ao decidir `despublicar`, grava
`despublicada_em = agora_utc()` e `publicada = False` (bookkeeping/auditoria) — nunca toca
`publicavel` (esse continua sendo o veredito estrutural do curador, ADR-0033; misturar os dois
esconderia a razão original da publicabilidade).

**Por que este lado e não "escrever `publicavel=False`":** `despublicada_em` é uma coluna nova
neste papel (nasce `None` em toda questão existente, real ou de teste — nenhuma migração de
dados/backfill é necessária) e vira o sentinela de "está sendo servida agora" sem contaminar o
histórico de por que ela nasceu publicável. Reabrir uma questão (reingestão resolve o gabarito,
por exemplo) é só voltar a `despublicada_em = None`, sem reconstruir `publicavel`.

Fecha a P-34 (`docs/PENDENCIAS.md`, hunk cirúrgico nessa linha ao final).

## 3. Domínio puro — `dominio/calibracao.py`

Sem banco, sem `datetime.now`, sem LLM. Contrato:

- `RespostaBruta(BaseModel)`: `questao_id, usuario_id, acertou, tempo_ms?, confianca_declarada?`.
- `ReporteBruto(BaseModel)`: `questao_id, motivo`.
- `MetricasQuestao(BaseModel)`: `questao_id, n, acertos, tempo_mediano_s?, confianca_alta_erro,
  reportes, reportes_motivos, dificuldade_est?, origem (original/inedita), discriminacao (float |
  "desconhecido")` + propriedades `acerto`/`erro_confiante`/`taxa_reporte`.
- `agregar_metricas(respostas: list[RespostaBruta], reportes: list[ReporteBruto],
  origem_por_questao, dificuldade_por_questao) -> list[MetricasQuestao]`: agrupa por questão e
  calcula a discriminação (item-resto) usando o desempenho de cada respondente nas outras
  questões da mesma lista `respostas`.
- `AjusteCalibracao(BaseModel)`: `questao_id, acao, regra, evidencia, efeito_colateral,
  dificuldade_real, discriminacao, n`.
- `avaliar_questao(metricas: MetricasQuestao) -> AjusteCalibracao`: R-0..R-9, ordem exata da
  skill, com a exceção documentada da própria skill — R-3 (conteúdo faltando) é avaliada **antes**
  do corte de `n < 30` ("vale com qualquer n"); as demais regras exigem `n ≥ 30`.
- `ItemFilaHumana(BaseModel)`: `questao_id, motivo, o_que_olhar, minutos_estimados, regra`.
- `montar_fila_humana(ajustes, metricas_por_id) -> (fila, adiada)`: só entram `sinalizar` (R-8);
  ordenada por `taxa_reporte` desc; corta em ≤ 20 min (`MINUTOS_POR_ITEM_FILA` constante,
  documentada — piso escolhido: 5 min/item, a skill não fixa um número).
- `RetroalimentacaoGerador(BaseModel)`: `questao_id, padrao` — uma por `AjusteCalibracao` com
  `regra == "R-5"`.

## 4. Camada de dados

- `dados/modelos.py`: nova classe `Calibracao` (`id, questao_id, data, dificuldade_real,
  discriminacao (Float, nullable — None = "desconhecido"), n, acao`), campo a campo do modelo de
  dados §6. Migração Alembic `0013_calibracao.py`.
- `dados/repositorio_calibracao.py`: `respostas_da_janela(db, desde) -> list[RespostaBruta]` (join
  `evento_estudo` tipo `resposta` + `Questao.origem`/`inedita` para saber `original`/`inedita`),
  `reportes_da_janela(db, desde) -> list[ReporteBruto]`, `dificuldade_atual_por_questao(db,
  questao_ids)`, `gravar_calibracao(db, ajustes: list[AjusteCalibracao]) -> None` (insere
  `Calibracao`, atualiza `Questao.dificuldade_est`/`discriminacao_est` sempre que a ação for
  `ajustar`/`despublicar`/R-6/R-7, e `despublicada_em`/`publicada` só quando `despublicar`).
- Ajuste dos 5 pontos de leitura citados em 2.2 (adiciona `despublicada_em.is_(None)`).

## 5. Comando — `motor/calibrar.py`

Molde de `motor/plano.py`: `calibrar_questoes(db, agora, *, commit=True) -> RelatorioCalibracao`
(uma linha por questão avaliada: `questao_id, acao, regra`), `main()` com `argparse`
(`--dias-janela` padrão 14, `--dry-run`), imprime o relatório incluindo, **sempre**, "N de M
questões com n ≥ 30 (elegíveis para discriminação)" — a frase que impede a próxima pessoa de
supor volume que não existe.

## 6. Testes (red-first)

- `tests/test_dominio_calibracao.py`: as 9 regras (usando a fixture estendida
  `knowledge/fixtures/calibracao/eventos-calibracao.json`, carregada e convertida em
  `MetricasQuestao` direto, sem passar pela discriminação item-resto — este arquivo só tem
  agregados, não respostas cruas); a discriminação item-resto ganha teste próprio com
  `RespostaBruta` sintéticas inline (caso de discriminação alta, caso de discriminação nula,
  caso `n < 30`, caso variância zero) — declaradas sintéticas no docstring do teste. Fila humana
  ≤ 20 min e `fila_humana_adiada`.
- `tests/test_repositorio_calibracao.py`: agregação real via `evento_estudo`/`reporte_erro` no
  banco de teste (nunca `dev.db`), gravação de `Calibracao` e atualização de `Questao`.
- `tests/test_motor_calibrar.py`: comando fim a fim contra o banco de teste; relatório honesto de
  elegibilidade de discriminação.
- Testes dos 5 pontos de leitura ajustados (P-34): uma questão com `despublicada_em` preenchido
  não aparece mais em `proxima_questao`/`contagem_por_topico`/`questao_valida_para_responder`.

## 7. Execução real (honesta, sem fabricar dado)

Rodar `python -m aprovaos.motor.calibrar` contra uma **cópia** de `dev.db` (nunca o original),
`--dry-run` — relatar quantas questões tinham evento suficiente, quantas foram avaliadas, quantas
tinham `n ≥ 30` (número esperado: zero ou muito próximo disso, dado real). Não gravar nada em
`dev.db`.

## 8. Fora de escopo (registrar em `docs/PENDENCIAS.md` se achado)

Consumo de `discriminacao_est` pelo diagnóstico (`dominio/diagnostico.py` continua com o proxy da
fatia 7); TRI 2PL completa (ADR-0022: só com `n ≥ 300` por item-âncora); agendador do job noturno
(ADR-0030, pendência de infraestrutura); LLM em qualquer parte (cota esgotada; a skill inteira é
determinística).

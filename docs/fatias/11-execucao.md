# Fatia 11 — Calibrador: diário de execução

> O que é: o que de fato aconteceu ao executar `11-calibrador.md`, na ordem em que aconteceu.
> Quando ler: para saber por que o código ficou como ficou, ou para retomar de onde parou.

**Contexto da sessão:** outro agente estava, em paralelo, corrigindo `dominio/legislacao.py`,
`motor/relacionar_topicos.py`, `dados/repositorio_topico_relacao.py`, `api/editais.py`,
`web/templates/rotina/formulario.html` e vários `docs/` — nenhum desses arquivos foi tocado
aqui. Em alguns pontos da execução, a suíte inteira mostrava 2–3 falhas transitórias nesses
arquivos (import quebrado em `api/editais.py`, migração `0014` do outro agente); confirmado por
`git status`/`git diff` que a causa era sempre um arquivo fora do meu escopo, nunca um dos meus.
A suíte de calibração (`test_dominio_calibracao.py`, `test_repositorio_calibracao.py`,
`test_motor_calibrar.py` e os testes de P-34 acrescentados a `test_repositorio_questao.py`/
`test_rota_questoes.py`) passou 100 % em toda rodada, isolada com `--ignore` quando necessário.

## 1. Domínio — `dominio/calibracao.py`

Red-first: escrevi `tests/test_dominio_calibracao.py` primeiro (`ModuleNotFoundError` confirmado),
depois implementei. A fixture sintética `knowledge/fixtures/calibracao/eventos-calibracao.json`
estende a fixture real da fase 4 (`docs/evidencias/2026-09-17-fase4-skills/fixtures/
eventos-calibracao.json`, "números inventados") com três casos que faltavam: `q-70` (R-6, original
trivial — ajusta, não despublica, ao contrário de uma inédita), `q-80` (R-8, motivos variados sem
gatilho — vai para a fila humana) e `q-90` (R-9, fallback). As nove regras batem exatamente com os
três números de referência que a skill cita (`erro_confiante` 0,32/0,23/0,07 para
gabarito-invertido/lei-mudou/difícil-legítima).

**Ajuste feito durante o TDD:** a primeira versão de `agregar_metricas` só incluía uma questão no
resultado se ela tivesse pelo menos uma resposta na janela — o que quebrava exatamente o caso que
a skill diz ser especial (R-3, "vale com qualquer n"): uma questão reportada por "faltou o texto"
**antes** de qualquer resposta registrada não entrava na avaliação nenhuma. Corrigido para incluir
toda questão com resposta **ou** reporte (`test_agregar_metricas_inclui_questao_so_reportada_sem_
nenhuma_resposta`).

**Discriminação (o ponto que a delegação pediu explicitamente):** correlação ponto-bisserial
item-resto (Crocker & Algina, cap. 16) — cruza o acerto no item com o desempenho do respondente
nas *outras* questões da mesma janela. Piso duplo, os dois testados com séries sintéticas
declaradas: `n < 30` (o piso que a própria skill já dá) e variância zero em qualquer uma das duas
séries (ex.: uma única aluna respondendo tudo — o caso real do `dev.db`) — os dois retornam
`"desconhecido"`, nunca um número fabricado.

## 2. Dados — `Calibracao`, `repositorio_calibracao.py`, migração 0013

`docs/04-modelo-de-dados.md` §6 lista `acao` com três valores (`manter`/`sinalizar`/
`despublicar`); a skill (fase 4, posterior a esse rascunho) define quatro
(`manter`/`ajustar`/`sinalizar`/`despublicar`). Segui a skill — é a fonte de verdade do contrato
(CLAUDE.md, regra "contratos vêm das skills") — e documentei a divergência no docstring da classe
`Calibracao` e na migração, em vez de reabrir o modelo de dados nesta fatia (arquivo fora do
escopo direto do pedido, e editá-lo tocaria seções que não são só a P-34).

`gravar_calibracao`: `manter` só grava a linha histórica; `ajustar`/`despublicar` também
atualizam `questao.dificuldade_est`/`discriminacao_est`; só `despublicar` grava
`despublicada_em`/`publicada=False`. Testado nos dois sentidos (P-34 abaixo).

## 3. A decisão da P-34

Duas opções estavam abertas: (a) a consulta da tela passa a filtrar `publicada` (o que o rascunho
antigo do modelo de dados sugeria) ou (b) o calibrador escreve numa coluna que a consulta já
filtra. Descartei (a): `publicada` nasce `False` em **toda** questão publicável que já existe hoje
(inclusive as 137 do TJ-PR no `dev.db`) — filtrar por ela sem um backfill apagaria a fila da aluna
inteira, o oposto do que a P-34 pede para consertar. Escolhi: **o calibrador grava
`despublicada_em`** (carimbo, nasce `None` em toda linha — nenhuma migração de dados necessária) e
**toda consulta que serve conteúdo passa a exigir `despublicada_em IS NULL`** além de
`publicavel=True`. `publicavel` nunca é tocado pelo calibrador — continua sendo só o veredito
estrutural do curador (ADR-0033); os dois vieses (estrutural vs. comportamental) ficam
distinguíveis na base, coisa que misturar num `publicavel=False` escondido teria perdido.

Seis pontos de leitura ajustados, todos testados no lado da leitura (não só da gravação):
`repositorio_questao.proxima_questao`/`contagem_por_topico`/`questoes_publicaveis_do_topico`,
`api/questoes.py::questao_valida_para_responder`, `api/diagnostico.py` (mesma função, cópia
paralela documentada), `motor/dossie.py::topicos_de_maior_peso`,
`motor/ligar_por_topico.py::ligar_questoes_por_topico`. `docs/PENDENCIAS.md` P-34 fechada com a
descrição da decisão.

## 4. Comando — `motor/calibrar.py`

Molde de `motor/plano.py` (mesmo padrão `argparse`+`main()`+relatório impresso). Nenhum loop por
usuário aqui — a granularidade é por questão, não por aluno. `--dias-janela` (padrão 14) e
`--dry-run`. O relatório sempre imprime "N de M com n ≥ 30 (elegível para discriminação)" —
justamente o número que a delegação pediu para nunca ser inflado.

## 5. Execução real, honesta (cópia de `dev.db`, nada gravado no original)

```
cp backend/dev.db /tmp/dev-copia-calibrador.db
DATABASE_URL=sqlite:////tmp/dev-copia-calibrador.db ... alembic upgrade head   # já estava em 0014 (0013 aplicada por mim, 0014 pelo outro agente)
DATABASE_URL=sqlite:////tmp/dev-copia-calibrador.db ... python -m aprovaos.motor.calibrar --dry-run --dias-janela 14
```
Saída real:
```
calibração de 2026-09-19 (janela de 14 dias): 18 questão(ões) avaliada(s), 0 de 18 com n >= 30 (elegível para discriminação).
  manter: 18
```
Conferido à mão (`sqlite3`): a base real tem 18 `evento_estudo(tipo="resposta")` + 1
`revisao_cartao` (corretamente ignorado pelo calibrador, que só olha `resposta`) + 0
`reporte_erro` — bate com os "~19 eventos de uma única aluna" da delegação. **Zero questões da
base real tinham `n` suficiente para calibrar** — o resultado honesto esperado, sem nenhum evento
fabricado em `dev.db` (a cópia temporária foi apagada depois).

## 6. Testes e checagem

- `dominio/calibracao.py`: 24 testes (`test_dominio_calibracao.py`).
- `dados/repositorio_calibracao.py`: 7 testes (`test_repositorio_calibracao.py`).
- `motor/calibrar.py`: 3 testes (`test_motor_calibrar.py`).
- P-34 (leitura): 3 testes novos em `test_repositorio_questao.py` + 1 em `test_rota_questoes.py`.
- `test_modelos.py::test_tabelas` atualizado com `"calibracao"`.
- `ruff check`/`ruff format --check`/`mypy` limpos nos arquivos desta fatia (verificado também
  escopado, isolando do trabalho concorrente do outro agente).
- Suíte cheia, ignorando os dois arquivos que o outro agente ainda tinha em vermelho no meio da
  própria correção: **812 passed, 6 skipped**.

## 7. Fora de escopo, não tocado

`dominio/diagnostico.py` continua com o proxy da fatia 7 (ADR-0022 aponta para consumir
`discriminacao_est`, mas isso é da fatia do diagnóstico, não desta); TRI 2PL completa; agendador
do job noturno; qualquer LLM (a skill inteira é determinística, e a cota do free tier está
esgotada de qualquer forma).

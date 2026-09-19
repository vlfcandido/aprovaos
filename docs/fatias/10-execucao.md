# Fatia 10 — Painel: curva, padrões, previsão v0, fio (c), semana da prova: diário

> O que é: o que foi feito, medido, na fatia 10 — não o plano (`10-painel.md`). Quando ler: para
> saber o que existe de verdade hoje, com que evidência. Este arquivo nasceu no passo 7 (os
> passos 1–6 já estavam commitados na `main` sem diário — a seção 1 abaixo reconstrói o que eles
> fizeram a partir das mensagens de commit, para o arquivo não começar incompleto).

## 1. Passos 1–6 (domínio puro), reconstruídos das mensagens de commit

- **Passo 1** (`3a638f0`) — `dominio/estatistica.py`: `Proporcao`, `intervalo_wilson` (Wilson,
  1927) e `sobrepoe`, puros. Substitui o proxy `50/(1+peso)` do diagnóstico para tudo que o
  painel exibe como proficiência (Ruling 35) — o intervalo nunca degenera em `[0, 0]` com pouco
  dado; a banda é grampeada em `[0, 100]` só como apresentação.
- **Passo 2** (`565eb01`) — `dominio/curva.py`: `montar_curva`/`alerta_da_curva`, puros. Sem
  `data_alvo` ou com data no passado, declara a lacuna em vez de desenhar reta inventada;
  "dominado" reaproveita `dominio/trilha.py`. Decisão fora do plano, registrada no commit:
  `atraso_topicos` não é "diferença para a reta necessária hoje" (dá zero por construção) — é
  "quantos tópicos ficariam faltando na data da prova se o ritmo real das últimas 4 semanas
  continuar" (é o que o adendo do brief do passo 7 também confirma).
- **Passo 3** (padroes.py) — `dominio/padroes.py`: `detectar_padroes` com piso de suporte
  (`MINIMO_RESPOSTAS_PADRAO=8`) e sobreposição de Wilson como critério de "padrão defensável";
  cinco dimensões (`materia`, `topico`, `banca`, `horario`, `energia`).
- **Passo 4** (`c2d3447`) — `dominio/previsao.py`: `prever_nota`, puro. Decisão fora do plano,
  registrada no commit: `DesempenhoMateria.proporcao` virou `Proporcao | None` (o esboço do
  plano mostrava obrigatório) — `None` é o que permite a própria função separar
  `materias_sem_dado` sem depender de convenção. `prever_nota` levanta `ValueError` quando
  nenhuma matéria tem dado.
- **Passo 5** (`d12f4da`) — `dominio/resumo_semanal.py`: `montar_resumo`, sem LLM (Ruling 36).
  Nasceu com tipos locais (`RespostaHistorica`/`Acertos` próprios) porque `curva.py`/
  `estatistica.py` estavam em construção paralela na mesma fatia — documentado no próprio
  cabeçalho do módulo à época.
- **Passo 6** (`5fc6c75`) — `dominio/plano.py` ganha o bloco de descanso na semana da prova
  (RF-19: "revisão cirúrgica **+** descanso", não só a primeira metade) — e, no mesmo commit,
  **unifica** `resumo_semanal.py` com `curva.py`/`estatistica.py`: `RespostaHistorica` passa a
  ser importada de `dominio.curva` (não mais uma cópia local) e `ResumoSemanal.acertos` vira
  `dominio.estatistica.Proporcao` (Wilson) em vez do `Acertos` simples de antes — "acertou X de
  Y" no resumo semanal agora nasce do mesmo intervalo do resto do painel (regra 11 do
  `CLAUDE.md`).

**Ponto de partida real do passo 7:** 1024+ testes verdes na `main`, os cinco módulos de domínio
acima prontos e com as assinaturas do commit mais recente (não as do esboço do plano) — o adendo
do brief do passo 7 já avisava disso e as assinaturas reais bateram com o que os commits mostram.

## 2. Passo 7 — camada de dados, rota e tela (este trabalho)

### O que foi construído
- `backend/aprovaos/dados/repositorio_painel.py` (novo): `respostas_historicas`/
  `respostas_classificadas` (mesma trava da P-34 — `publicavel=True` **e**
  `despublicada_em IS NULL`), `pesos_por_materia` (do DNA quando toda matéria do edital tem
  `questoes` inteiro; senão peso uniforme `1` com lacuna declarada — P-39), `nomes_por_topico`,
  `total_topicos`, `curva_atual` (chama `dominio.curva.montar_curva` com os dados buscados) e
  `alerta_atual` (a mesma curva + `alerta_da_curva`, reaproveitado por `GET /painel` **e**
  `GET /hoje` para o alerta nunca divergir entre as duas telas).
- `backend/aprovaos/api/painel.py` (novo): `GET /painel` (curva + alerta + padrões + previsão) e
  `GET /painel/semana` (resumo semanal). O `<svg>` da curva (duas polilinhas: real cheia,
  necessária tracejada, mais eixos) e da banda da previsão (retângulo translúcido) são montados
  em Python, direto na rota — sem JS, sem biblioteca, cores por `var(--cor-*)` (os tokens já
  carregados pela página resolvem as variáveis dentro do SVG, mesmo truque do protótipo
  validado). Sem concurso principal/edital resolvível, as duas rotas mostram o caminho para
  `/rotina`/`/editais/subir`, nunca uma exceção.
- `backend/aprovaos/api/plano.py` (`_pagina_do_plano`) e `web/templates/hoje/pagina.html`: o
  alerta de atraso (RF-10) passou a aparecer acima do plano, quando existir, chamando
  `alerta_atual` — mesmo alerta de `/painel`.
- `web/templates/painel/pagina.html`, `_curva.html`, `_padroes.html`, `_previsao.html`,
  `semana.html` (novos): shell e tokens de `base.html`/`tokens.css`, sem cor nova. Todo número
  aparece também por extenso ao lado do gráfico (ex.: "62 % — entre 48 % e 74 %"), e a curva sem
  `data_alvo` diz "você ainda não informou a data da prova" com link para `/rotina`, nunca uma
  linha inventada.
- Link "Painel" em `web/templates/base.html`, dentro do `{% if usuario_email %}`.
- `backend/aprovaos/main.py`: `app.include_router(painel.router)` — única linha acrescentada,
  relida imediatamente antes para não perder a linha `publico.router` de outro agente (não
  aconteceu conflito).
- Testes: `backend/tests/test_repositorio_painel.py` (10 testes) e
  `backend/tests/test_rota_painel.py` (9 testes) — 19 novos, TDD red-first, cobrindo:
  P-34 nas duas consultas de dado, conversão de hora para Brasília (Ruling 37), peso uniforme
  com lacuna quando o DNA não traz distribuição, curva sem `data_alvo`, curva com domínio real,
  ausência de alerta sem concurso, login obrigatório nas duas rotas, caminho para `/rotina` sem
  concurso, lacuna de `data_alvo` na tela, banda por extenso, regressão de questão despublicada
  (P-34) na tela, resumo sem estudo, e o alerta aparecendo — e não aparecendo — em `/hoje`.

### Divergências do plano (nenhuma foi extrapolação, todas registradas)
- O plano original de `previsao.py`/`padroes.py` já havia sido ajustado pelos passos 3/4 antes
  do passo 7 começar (ver §1); o adendo do brief já avisava e as assinaturas reais foram usadas
  como estão, sem tentar "corrigir" para bater com o esboço.
- `resumo_semanal.RespostaHistorica` deixou de existir como tipo próprio (unificado com
  `curva.RespostaHistorica` no passo 6, commit `5fc6c75`) **depois** da primeira leitura deste
  agente — a implementação inicial de `api/painel.py` tentou reexportar/converter entre os dois
  tipos; corrigida para reaproveitar a mesma lista de `respostas_historicas` sem conversão
  nenhuma, mais simples e mais correta (mesmo Wilson do resto do painel).
- O plano não detalhava como o alerta chegaria a `/hoje` sem duplicar a consulta da curva —
  decisão deste passo: `dados/repositorio_painel.alerta_atual` fica no repositório (não em
  `api/painel.py`) porque as duas rotas (`/painel` e `/hoje`) precisam dele igual.

## 3. Execução real contra uma cópia de `dev.db` (§9 do plano)

Copiado `backend/dev.db` para fora do repositório antes de qualquer leitura (nunca o original).
Usuária real: `linda.piloto@exemplo.com`; concurso principal resolvido por
`repositorio_edital.concurso_principal`: **TJ-PR / Instituto AOCP** (ela não gravou
`perfil_estudo.data_alvo`).

| número | valor real |
|---|---|
| respostas no histórico | **18** |
| acertos | **12 de 18 (66,7 %, Wilson 43,7 %–83,7 %)** |
| tópicos do edital | 99 |
| tópicos dominados hoje | **1** |
| curva necessária | nenhuma — `lacuna="sem data da prova"` |
| alerta de atraso (RF-10) | nenhum (não há curva necessária para comparar) |
| padrões acima do piso estatístico | **0** (honesto — 18 respostas não sustentam nenhum
  cruzamento com `n >= 8` e bandas sem sobreposição em nenhuma das cinco dimensões) |
| previsão de nota | **61,6 % (26,6 %–89,5 %), confiança baixa** |
| peso por matéria | uniforme (`1` para cada), com lacuna — o DNA da AOCP (por regras) não traz
  `questoes` por matéria (P-39) |
| resumo da semana corrente (seg–dom, Brasília) | 18 respostas, 12 certas (mesmo período — toda
  a atividade real dela está nesta semana), 9 tópicos novos, 5 para revisar, **1 tópico dominado
  nesta semana** |

Nenhum número saiu "bonito demais" — confiança baixa, 0 padrões e nenhum alerta são exatamente o
esperado com 18 respostas e sem `data_alvo`; é o resultado honesto que o §0 do plano já previa.

**Achado registrado como pendência nova (P-65, `docs/PENDENCIAS.md`):** `topico.materia` grava
`"LÍNGUA PORTUGUESA"` (7 linhas) e `"Língua Portuguesa"` (28 linhas) como duas linhas distintas
do mesmo edital real — `pesos_por_materia`/`_desempenho_por_materia` agrupam por matéria ao pé
da letra, então a previsão trata isso como duas matérias com peso uniforme cada. Não é um
defeito desta fatia (o painel só lê `Topico.materia` como está gravado); é um dado anterior,
provavelmente de duas ingestões/classificações diferentes do mesmo edital.

## 4. Testes e checagem

`cd backend && uv run pytest tests/test_repositorio_painel.py tests/test_rota_painel.py -q` →
**19 passed**. Suíte cheia (`uv run pytest -q`): **1024 passed, 6 skipped, 1 failed** — a falha é
`test_modelos.py::test_tabelas` (tabela `veredito_questao` de trabalho concorrente de outro
agente na mesma branch, arquivos fora do escopo desta fatia — não tocado). `ruff check` e `mypy
--strict` verdes nos arquivos deste passo (`repositorio_painel.py`, `api/painel.py`,
`api/plano.py`, os dois arquivos de teste).

## 5. O que ficou fora (registrado em `docs/PENDENCIAS.md`)
P-63 (notificação/push real do alerta; probabilidade de aprovação com corte histórico real),
P-64 (TRI/discriminação na previsão — ADR-0022 exige `n >= 300`, temos 18), P-65 (duas grafias
de `topico.materia` no edital real do TJ-PR/AOCP, achado nesta execução).

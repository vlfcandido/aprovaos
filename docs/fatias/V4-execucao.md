# Fatia V4 — registro de execução
> O que é: o diário de execução do plano `V4-revisao-espacada.md`. Quando ler: ao revisar o que
> foi feito nesta fatia ou ao retomar a partir de V5 (fio da memória).

Executado em 19/09/2026 em `/Users/vinicius/PycharmProjects/aprovaos/backend`, `uv` + CPython
3.13, branch `main` a partir do commit `a823327` (493 testes verdes).

## Passo 0 — `fsrs` instalado e o achado que mudou o plano

`uv add fsrs` → **6.3.2**, licença **MIT** confirmada no `dist-info` da distribuição instalada
(`backend/.venv/lib/python3.13/site-packages/fsrs-6.3.2.dist-info/METADATA`), batendo com "py-fsrs
6.3" da ADR-0022. Antes de escrever qualquer código de produção, inspecionei a API real
(`fsrs.Card`, `fsrs.Scheduler`, `fsrs.Rating`, `fsrs.State`) com um REPL contra a biblioteca de
verdade — não a documentação de memória:

- `fsrs.Card` **não tem `reps`/`lapses`** (campos reais: `card_id, state, step, stability,
  difficulty, due, last_review`). O modelo de dados (`docs/04-modelo-de-dados.md`) nomeia
  `reps`/`lapses` como parte do "estado serializado do `fsrs.Card`" — não é mais verdade nesta
  versão da lib.
- Pior: reconstruir o `Card` sem `state`/`step` **recalcula um `due` diferente do real**. Prova
  (script solto, sem mock, valores reais da lib):
  ```
  >>> c1 = Card(); scheduler.review_card(c1, Rating.Good, dt(2026,1,1))
  {'due': '2026-01-01T00:10:00+00:00', 'state': 1, 'step': 1, ...}
  >>> parcial = Card(stability=c1.stability, difficulty=c1.difficulty, due=c1.due, last_review=c1.last_review)  # sem state/step
  >>> scheduler.review_card(c1, Rating.Good, dt(2026,1,1,0,10))       # completo
  {'due': '2026-01-03T00:10:00+00:00', ...}
  >>> scheduler.review_card(parcial, Rating.Good, dt(2026,1,1,0,10))  # sem state/step
  {'due': '2026-01-01T00:20:00+00:00', ...}
  ```
  Quase dois dias de diferença no `due` calculado — a segunda revisão cai na tabela de
  "aprendizado" errada porque o `Card` reconstruído "esqueceu" que ainda estava em `Learning`.

**Decisão registrada** (`docs/DECISOES.md`, adendo à ADR-0022; `docs/fatias/V4-revisao-espacada.md`
§2): a tabela `cartao` ganha `estado_fsrs`/`passo_fsrs` além dos seis campos nomeados no modelo de
dados; `reps`/`lapses` viram contadores próprios (`dominio/revisao.py`), não lidos do `fsrs.Card`.
Isto não é uma invenção de coluna arbitrária — é o mínimo para a promessa "estado serializado do
`fsrs.Card`" ser verdade de fato, e ficou provado por teste antes de qualquer linha de produção
(`tests/test_dominio_revisao.py::test_ida_e_volta_sem_perder_estado_fsrs`, TDD red-first: o teste
existia e falhava contra uma implementação que só usava os seis campos, antes de eu acrescentar os
dois extras).

## Passo 1 — `dominio/revisao.py` (puro)

`EstadoCartaoFsrs` (pydantic), `rating_por_resposta` (proxy acertou+confiança → `fsrs.Rating` — só
`Again`/`Good`/`Easy`, nunca `Hard`: não há sinal de "acertei com dificuldade" sem inventar um
limiar novo, registrado como limitação em vez de inventado) e `revisar` (cria o estado do zero
quando `estado_atual is None`, ou aplica uma revisão a um existente). `montar_frente_verso`
recebe campos primitivos (`comando`/`enunciado`/`gabarito`), nunca o modelo ORM — o domínio não
importa de `dados/`.

9 testes em `tests/test_dominio_revisao.py`, incluindo o de ida e volta acima e um de `lapses`
(só conta esquecimento depois que o cartão já tinha saído de `Learning`).

## Passo 2 — modelo `Cartao`, migração 0007 e `evento_estudo.cartao_id`

`Cartao` em `dados/modelos.py` com `UniqueConstraint(usuario_id, questao_id)` — o mecanismo que
cumpre "errar a mesma questão duas vezes não cria dois cartões" no nível do banco, não só na
lógica da função. `evento_estudo` ganhou a coluna `cartao_id` (nullable) para o tipo
`revisao_cartao`, que já estava reservado no `CHECK` desde a V3 mas nunca tinha coluna. Migração
`0007_cartao.py` escrita à mão (mesma convenção das 0003/0006), `downgrade()` real (testado por
`test_migracoes.py::test_downgrade_remove_tudo`, que já existia e cobre qualquer migração nova
sem precisar de teste próprio). `compare_metadata` bate zero diferenças
(`test_migracao_inicial_bate_com_os_modelos`).

## Passo 3 — `dados/repositorio_cartao.py`

`registrar_erro` (idempotente — busca antes de criar), `cartoes_vencidos` (`due <= agora`, `ORDER
BY due, id`) e `revisar_cartao` (grava `EventoEstudo` **e** atualiza o estado, sempre as duas
coisas, no mesmo `flush`). `registrar_erro` devolve `None` quando `questao.topico_id is None` —
`Cartao.topico_id` é `NOT NULL`, e uma questão sem tópico casado nunca deveria ser publicável de
qualquer forma (o gate da V3 já filtra isso antes), mas a função não força o dado por
sorte/acidente: testado explicitamente
(`test_registrar_erro_sem_topico_nao_cria_cartao`).

7 testes em `tests/test_repositorio_cartao.py`.

## Passo 4 — `api/questoes.py`: o erro cria o cartão; `/revisar`

`responder_questao` chama `registrar_erro` só quando `not evento.acertou`, antes do `commit` (as
duas gravações — `EventoEstudo(tipo="resposta")` e o `Cartao` — commitam juntas ou nenhuma). Duas
rotas novas, `GET`/`POST /revisar`, com o mesmo formato de validação e resposta das rotas de
questão (`_cartao_pendente`, espelho de `_questao_pendente`; mesma mensagem de "não está mais
disponível" quando o cartão não bate com o usuário ou a questão do formulário).

**Não duplique a tela** foi cumprido de verdade, não só de intenção: `_contexto_questao` ganhou
`acao_post`/`campos_ocultos` (opcionais, default vazio) e o formulário de perguntar saiu de
`topico.html` para o parcial `questoes/_cartao_questao.html`, incluído tanto por `topico.html`
quanto pela `revisao.html` nova. `_resultado.html` trocou o link fixo `/topico/{slug}/questoes`
por `proximo_url`/`proximo_rotulo`, que as duas rotas preenchem de forma diferente ("Próxima
questão" vs. "Próxima revisão") — é o mesmo template para os dois fluxos, sem `if` de rota dentro
dele.

12 testes novos: 2 em `test_rota_questoes.py` (erro cria cartão / acerto não cria) e 10 em
`tests/test_rota_revisao.py` (isolamento por usuário nas duas rotas, agenda vazia, revisão grava
evento e atualiza `due`, cartão de outra conta é recusado). Link "Revisar hoje" em `base.html`.

## Resultado

`bash scripts/checar.sh` na raiz: ruff, `ruff format --check`, `mypy --strict` (123 arquivos),
prova de import sem efeito colateral e a suíte inteira — **517 passed, 6 skipped** (os 6 são os
markers `postgres`/`llm`/`rede`, nenhum tocado por esta fatia). Partindo de 493 antes da V4:
+30 (9 em `test_dominio_revisao.py`, 7 em `test_repositorio_cartao.py`, 2 em
`test_rota_questoes.py`, 10 em `test_rota_revisao.py`, 2 ajustes em testes existentes —
`test_modelos.py`/`test_migracoes.py` não somam teste novo, só passam a cobrir `cartao`).

## Demonstração real contra `backend/dev.db`

`dev.db` (SQLite local, sem Docker) estava parado na migração `0006` (da fundação jurídica);
`alembic upgrade head` aplicou a `0007` sem erro. Rodei um script solto (não commitado) contra o
banco de verdade, usando a conta real da Ana (`linda.piloto@exemplo.com`, criada na V3) e uma
questão publicável de verdade (Direito Administrativo, "O poder da administração pública de rever
os próprios atos é absoluto…", gabarito `E`):

1. **Ela erra** (respondeu `C`): `registrar_erro` criou o cartão `9073696c-…`
   — `origem=auto_erro`, `reps=1`, `lapses=0`, `estado_fsrs=1` (`Learning`), `passo_fsrs=0`,
   `stability=0.212`, `difficulty=6.4133`, **`due=2026-09-19 11:24:43 UTC`**
   (`last_review=2026-09-19 11:23:43 UTC` — a agenda inicial do FSRS para uma resposta `Again` é
   1 minuto depois, o primeiro degrau de aprendizado).
2. **Simulei a revisão** exatamente no instante do vencimento, acertando com certeza (rating
   `Easy`): `revisar_cartao` gravou `EventoEstudo(tipo="revisao_cartao", cartao_id=…,
   acertou=True)` e atualizou o cartão — `reps=2`, **`due` foi de `2026-09-19 11:24:43` para
   `2026-09-20 11:24:43`** (a segunda revisão promoveu o cartão para fora da fase de aprendizado
   — `Easy` empurra bem mais que `Good` — para 1 dia de intervalo), `stability=0.424`,
   `difficulty=5.20`.

Isto prova, contra dado real (não fixture inventada), que: o erro cria o cartão com o estado
FSRS de verdade; `cartoes_vencidos` não o lista antes do `due`; a revisão grava o evento e move a
agenda para a frente de um jeito que só faz sentido com `state`/`step` preservados (o achado do
Passo 0 é real, não teórico).

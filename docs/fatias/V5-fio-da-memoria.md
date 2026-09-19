# Fatia V5 — Fio da memória (b): intercalação de tópicos já vistos: plano de implementação
> O que é: o plano da V5 — 3 itens de tópicos já vistos, intercalados no bloco de questões do
> tópico atual, cada um com a explicação de por que apareceu ali. Quando ler: antes de executar
> qualquer passo desta fatia e ao revisar o que foi feito; o diário fica em `V5-execucao.md`.

**Spec desta fatia:** linha V5 da tabela do PRD `docs/02-produto.md` §6 ("3 itens de tópicos já
vistos intercalados no bloco de questões"; fio (a) e (c) ficam de fora — dependem de
aulas/dossiês, que ainda não existem). Pedido original da usuária-piloto (S-01,
`docs/evidencias/2026-09-14-entrevista-linda.md`): "conteúdos interligados para relembrar os
anteriores" — cena (b) descrita por ela: "o bloco de questões de um tema mistura, de propósito,
itens de temas já estudados". Princípio de produto que rege a explicação
(`docs/00-visao.md` §4): "o agente decide; o aluno discorda em um toque. Nunca esconder o porquê
de uma decisão."

## 1. O que existe e o que falta

A tela de questão de hoje (`GET/POST /topico/{slug}/questoes`, V3/V3b/V4) é uma fila: cada `GET`
devolve a **próxima questão pendente do tópico da URL** (`repositorio_questao.proxima_questao`),
nunca mistura tópico. Não existe ainda `plano_dia`/`bloco` (fatia 8) — "o bloco de questões" desta
fatia **é** essa fila; a V5 não cria uma tela nova, faz a própria fila, de vez em quando,
devolver uma questão de **outro** tópico já visto, com a explicação do porquê.

## 2. Critério de intercalação (decisão desta fatia, documentada e testada)

Dado o tópico atual e o histórico da aluna (tópicos com pelo menos uma resposta, mesma definição
de "visto" que `topicos_vistos` já usa), calcula-se por tópico já visto (exceto o atual):
`ultima_visita` (a resposta mais recente), `total_respostas`, `erros`, `ultimo_erro_em` (a
resposta errada mais recente, `None` se nunca errou).

**Ranking em duas filas, alternadas** (função pura `escolher_para_intercalar`,
`dominio/fio_memoria.py`):
1. **Erro recente** — tópicos com pelo menos um erro, ordenados pelo erro mais recente primeiro.
2. **Tempo sem ver** — todos os tópicos elegíveis, ordenados pela `ultima_visita` mais antiga
   primeiro (o que ela não vê há mais tempo).

As duas filas são consumidas alternadamente (erro, tempo, erro, tempo…), pulando quem já foi
escolhido, até reunir até 3 tópicos **distintos**. Escolha do dono deste plano, já que a spec não
fixa proporção: erro recente entra primeiro porque um erro é o sinal mais forte de que aquele
conteúdo precisa voltar; tempo sem ver garante que um tópico sem erro nenhum (mas cada vez mais
esquecido) também apareça, em vez de o ranking virar só "lista de erros". Sem histórico (nenhum
outro tópico visto), a lista sai vazia — não intercala nada, nunca sorteia. Se houver só 1 ou 2
tópicos elegíveis, a lista sai com 1 ou 2 — o chamador mostra "quantos houver" e diz quantos.

Cada item ranqueado carrega o `motivo` já formatado para a tela, no formato pedido pelo exemplo do
enunciado: `"de {matéria}, que você viu há N dia(s) e {errou X de Y | acertou todas as Y}"`.

## 3. Cadência (quando o item intercalado aparece na fila)

Sem `plano_dia`/`bloco`, "o bloco" desta fatia é a sequência de respostas dentro de um mesmo
tópico. Cada resposta grava, no `EventoEstudo.dados` (JSON — campo novo nesta fatia, §4), a chave
`bloco_topico_id`: o tópico que a aluna estava estudando quando respondeu (o mesmo tópico da URL,
mesmo quando a questão respondida é de **outro** tópico, por ser um item intercalado). Contar
quantos eventos já têm `bloco_topico_id == <tópico atual>` dá a posição na sequência,
independentemente de a resposta ter sido nativa ou intercalada — por isso o contador nunca trava
mostrando intercalados para sempre.

**Regra**: a cada 3 respostas nativas do tópico atual, a 4ª posição da fila é um item intercalado
(`PERIODO_INTERCALACAO = 4` em `dominio/fio_memoria.py`). Função pura
`decidir_proximo_intercalado(quantidade_no_bloco, itens)`: dispara quando
`quantidade_no_bloco % 4 == 3`, escolhendo o item pelo índice `(quantidade_no_bloco // 4) % len(itens)`
— cicla pelos até 3 candidatos, recalculados a cada chamada a partir do histórico mais recente
(um tópico que deixou de estar "esquecido" sai do topo do ranking sozinho, sem código extra).
Decisão registrada: isto **não** é "3 itens só uma vez na vida" — o fio da memória continua
oferecendo intercalação a cada 4 questões enquanto a aluna estuda aquele tópico, porque é isso que
combate o esquecimento de verdade (uma injeção única não cumpre a promessa da entrevista). O
número "3" do PRD é o tamanho do conjunto de candidatos por rodada, não um teto vitalício.

Se a questão do tópico escolhido não estiver mais disponível (todas já respondidas/reportadas —
`proxima_questao` devolve `None`), a rota tenta o próximo candidato da lista antes de desistir; se
nenhum dos elegíveis tiver questão disponível, a fila cai de volta para a próxima questão nativa
— nunca quebra a tela.

## 4. `evento_estudo.dados` (JSON) — a coluna que o modelo de dados já previa e ainda faltava

`docs/04-modelo-de-dados.md` §2 já lista `dados (JSON)` como campo de `evento_estudo` desde a
Fase 3; nenhuma fatia (V1–V4) precisou dele e ele nunca chegou a ser criado. Esta fatia o cria de
verdade (migração `0008`, `Alembic`), nullable, porque é exatamente o que o modelo de dados
manda usar para "marcar que foi intercalado" em vez de inventar uma coluna nova — não é uma
coluna nova fora do plano, é o plano sendo cumprido pela primeira vez. Grava-se
`{"bloco_topico_id": "<uuid>"}` em toda resposta dentro do fluxo de tópico (nativa ou
intercalada) e, quando é intercalada, também `"fio_motivo"` (o texto já formatado, para o
resultado ecoar sem recalcular) e `"fio_origem_topico_id"` (o tópico de onde veio o item — já
recuperável por `Questao.topico_id`, mas gravado explícito para consulta sem join).

**Simplificação registrada, não escondida**: contar `bloco_topico_id` é um `SELECT` de todos os
eventos `tipo="resposta"` do usuário seguido de um filtro em Python no `dados` (dict já
desserializado pelo SQLAlchemy), em vez de um operador JSON específico de dialeto
(`->>`/`json_extract`). Está certo para o piloto (n=1, poucas centenas de eventos); se a escala
crescer, vira índice/consulta JSON nativa — registrado como pendência (`P-46`) para não bloquear
esta fatia.

## 5. Precedência com a V4 (cartão de erro) — decisão e porquê

**Cartão vencido (`/revisar`) e item intercalado (bloco de questões do tópico) nunca competem
pela mesma tela nem pela mesma questão, por construção, não por regra extra:**
- Fluxos diferentes: `/revisar` só mostra cartões vencidos; `/topico/{slug}/questoes` só mostra
  itens do fio da memória dentro do bloco daquele tópico. Esta fatia não muda `/revisar` nem o
  ordena junto com o fio — misturar os dois exigiria que `POST /revisar` aceitasse uma resposta
  que não é de um cartão, o que quebraria `revisar_cartao` (que sempre grava `revisao_cartao` e
  atualiza o FSRS via `cartao_id`).
- Mesma questão nunca nos dois ao mesmo tempo: um `Cartao` só nasce de uma questão que **já foi
  respondida** e errada (`registrar_erro`, V4); `proxima_questao` (usada tanto para a próxima
  nativa quanto para buscar a questão de um item intercalado) **exclui** questões já respondidas.
  Logo a questão de um cartão nunca é candidata a item intercalado — são conjuntos disjuntos por
  definição, sem precisar de um filtro a mais.
- Se as duas coisas existirem ao mesmo tempo para o mesmo tópico (um cartão vencido de uma
  questão X e um item intercalado apontando para o mesmo tópico de X, mas outra questão Y), a
  aluna simplesmente vê as duas em telas diferentes — o link "Revisar hoje" no menu continua
  levando para os cartões, independente do que a fila de questões esteja fazendo.

## 6. O que entra
1. Migração `0008_evento_estudo_dados.py`: `evento_estudo.dados` (JSON, nullable).
2. `dominio/fio_memoria.py` (puro): `EstatisticaTopicoVisto`, `ItemIntercalado`,
   `escolher_para_intercalar`, `decidir_proximo_intercalado`, `PERIODO_INTERCALACAO`.
3. `dados/repositorio_fio_memoria.py`: `estatisticas_topicos_vistos` (agregação por tópico via
   `evento_estudo`/`questao`/`topico_edital`, escopada ao edital do tópico atual — mesma
   restrição de `topicos_vistos`) e `quantidade_no_bloco` (conta eventos com
   `dados.bloco_topico_id` igual ao tópico, §4).
4. `dados/repositorio_questao.py`: `registrar_resposta` ganha `dados: dict[str, object] | None`
   opcional, gravado no evento.
5. `api/questoes.py`: `GET /topico/{slug}/questoes` decide, antes de buscar a próxima nativa, se
   a posição do bloco pede um item intercalado; quando pede, tenta achar questão disponível entre
   os candidatos ranqueados (§3) e monta o contexto com `fio_da_memoria` (motivo) além dos campos
   já existentes. `POST` grava `dados={"bloco_topico_id": ...}` (e os campos extra quando é
   intercalado) via dois campos ocultos novos no formulário (`bloco_topico_id`, `fio_motivo`
   opcional).
6. `web/templates/questoes/_cartao_questao.html` e `_resultado.html`: um bloco opcional (só
   quando `fio_da_memoria` existe no contexto) mostrando o selo "Fio da memória" e o motivo, antes
   do enunciado — reaproveitando o mesmo parcial das duas telas (`topico.html`/`revisao.html`),
   sem duplicar.
7. `docs/PENDENCIAS.md`: `P-46` (consulta de `dados` por scan em Python, §4).

## 7. Fora desta fatia (registrado, não implementado)
- Fio (a) — aula cita o tópico anterior — e fio (c) — resumo cumulativo semanal: dependem de
  aulas/dossiês (fatia 6/4), fora do escopo desta linha do PRD.
- `plano_dia`/`bloco` de verdade (fatia 8): esta fatia simula "o bloco" com a fila de um único
  tópico; quando o plano do dia existir, a intercalação passa a operar sobre blocos de fato.
- Consulta de `dados` por operador JSON nativo do dialeto (P-46, §4).
- Intercalação também na tela de revisão (`/revisar`): fora de escopo por decisão explícita (§5).

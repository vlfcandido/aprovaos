# Fatia 7 — Diagnóstico adaptativo + rotina: plano de implementação
> O que é: o plano da fatia 7 do PRD (`docs/02-produto.md` §6, linha "Diagnóstico adaptativo +
> rotina — F2.1, F2.2"). Quando ler: antes de executar qualquer passo desta fatia e ao revisar o
> que foi feito; o diário fica em `7-execucao.md`.

**Ponto de partida:** 656 testes verdes. `evento_estudo` (append-only, `confianca_declarada`
obrigatória), `cartao`/FSRS (V4), `fio_memoria` (V5), `questao` com `topico_id`/`publicavel`,
`repositorio_questao.proxima_questao`/`contagem_por_topico` já existem. `dev.db` da Linda tem dois
concursos: TJ-PR/AOCP (99 tópicos, **137 questões publicáveis**) e Cascavel/Unioeste — o edital
real dela, fictício por enquanto (P-17) — **com 0 questões publicáveis** hoje (a reclassificação
do passo 16 da V3 moveu a base inteira para o vocabulário do TJ-PR, P-31). Isso não é bug desta
fatia: é exatamente o caso "sem questão suficiente" que o enunciado pede para tratar explicitamente
— o diagnóstico contra Cascavel tem de terminar em 0 itens com uma mensagem honesta, não travar
nem fingir cobertura.

## 1. O que a spec pede (contrato)
- **F2.1 Simulado adaptativo** (RF-04): ≤ 30 itens originais da banca, escolhidos pelo que reduz a
  incerteza; termina quando todas as matérias ≤ ±8; mostra "por que este item". CA: proficiência
  por matéria com margem; reprodutível em teste com seed.
- **F2.2 Rotina** (RF-05/06): horas por dia da semana (editável em clique), horário, energia
  típica, data-alvo; perfil versionado. CA: mudança gera evento e muda o plano do dia seguinte.
- ADR-0022: diagnóstico **por proxy, não TRI completa**.
- Tarefa (dono): usar acerto, `confianca_declarada` e cobertura de tópicos como os três sinais do
  proxy; resultado vira **estado por tópico** (não um número solto) para a fatia 8 consumir;
  porquê visível ao terminar, com toque para discordar; tratar tópico/matéria sem questão
  explicitamente; sem LLM.

## 2. Por que não uso a fórmula literal da ADR-0022
A ADR fala em "média ponderada pela discriminação estimada dos itens (calibrador)... intervalo por
bootstrap". `questao.discriminacao_est` está **null em 100 % das 250 questões da base hoje**
(select confere) — o calibrador é fatia 11, ainda não existe produtor dessa coluna. Aplicar a
fórmula literal seria inventar um número a partir de `None`. Fico com a orientação de escopo do
dono para esta fatia (acerto + confiança + cobertura), documentada aqui como a leitura corrente da
ADR-0022 "por proxy" enquanto a calibração não existe; quando `discriminacao_est` tiver produtor
real, a fórmula troca sem mudar o contrato da tela (mesma `EstadoAgregado`).

## 3. Motor do diagnóstico — `dominio/diagnostico.py` (puro, sem banco)
Determinístico (nenhum `random`) — mais forte que "reprodutível com seed": a mesma sequência de
respostas produz sempre o mesmo próximo item e o mesmo ponto de parada, sem precisar fixar seed
nenhuma. É isso que os testes verificam.

**Modelos:**
- `ItemDiagnostico{topico_id, materia, acertou: bool, confianca: Literal["certeza","duvida"]}` —
  uma resposta já ocorrida.
- `EstadoAgregado{n_itens, estimativa_pct: float | None, margem: float, fechado: bool}`.
- `TopicoDisponivel{topico_id, materia, nome, tem_questao: bool}` — do edital, com a contagem de
  publicáveis já resolvida (`repositorio_questao.contagem_por_topico`).
- `CandidatoItem{topico_id, materia, motivo}` — um item elegível para a próxima pergunta.
- `SinalTopico{topico_id, materia, situacao: "dominado"|"a_estudar"|"sem_dado"|"sem_questao",
  estimativa_pct, margem, n_itens}` — o **estado por tópico** que a fatia 8 vai ler.

**Constantes:** `MARGEM_INICIAL=50.0`, `LIMITE_MARGEM=8.0` (o "±8" da spec), `MAXIMO_ITENS=30`,
`PESO_CERTEZA=2`, `PESO_DUVIDA=1`.

**A fórmula (proxy, não TRI):**
`peso_total = 2·n_certeza + 1·n_duvida` (informação que o item deu, não se acertou — um erro com
certeza informa tanto quanto um acerto com certeza: os dois fecham a dúvida sobre o aluno).
`margem = MARGEM_INICIAL / (1 + peso_total)` — decresce suave e monotonicamente com mais itens,
independente do resultado; sem nenhum item, `margem = MARGEM_INICIAL` (não fecha nunca sem dado).
`estimativa_pct = 100 · peso_acertos / peso_total` (`None` se `peso_total == 0`), onde
`peso_acertos` soma só os pesos dos itens **certos** — aqui sim o acerto entra, na posição da
estimativa, não na largura da margem.
`fechado = n_itens > 0 and margem <= LIMITE_MARGEM`.

Com 3 itens de certeza (peso 6), `margem = 50/7 ≈ 7,1 ≤ 8` — fecha; com dúvida, precisa de 6.
Casos extremos exigidos pela tarefa (testados): acerta tudo → margem fecha, estimativa 100 %; erra
tudo → margem fecha **na mesma velocidade**, estimativa 0 % (a confiança na estimativa não depende
do resultado); alterna certeza/dúvida → margem mista, entre as duas.

**Seleção do próximo item (`ordenar_candidatos`)** — os três sinais da tarefa juntos:
1. *Cobertura de tópicos* decide **matéria elegível**: só entram matérias com pelo menos um
   `TopicoDisponivel.tem_questao=True`; ficam de fora as sem nenhuma questão desde o início
   (Português/Matemática no TJ-PR hoje) — nunca fingem cobertura.
2. *Acerto + confiança* (via `EstadoAgregado.margem`) ordena as matérias elegíveis, decrescente —
   a de maior margem (mais incerta) vem primeiro, reduzindo a variância da matéria mais incerta
   (o espírito da ADR-0022); empate por nome (determinístico).
3. *Cobertura de tópicos* de novo, agora **dentro** da matéria escolhida: entre os tópicos dela com
   questão disponível, prioriza o menos respondido até aqui (espalha os itens, não repete sempre o
   mesmo tópico fácil de achar questão).
Matéria já `fechado=True` some da lista, a não ser que estejam em `materias_forcadas` (o
"discordar" — §5). A rota tenta cada candidato, na ordem, contra `proxima_questao` (mesmo padrão
de `_proximo_item_intercalado` do fio da memória) até achar um com questão de fato disponível —
"tem_questao" no início do diagnóstico pode ficar sem sobra no meio dele.

**Parada:** a rota para quando (a) `total_itens == MAXIMO_ITENS`, ou (b) a lista de candidatos
fica vazia (nenhuma matéria elegível tem questão disponível — inclui tanto "todas fecharam a
margem" quanto "as que não fecharam ficaram sem item novo"). `motivo_geral(...)` monta a frase
final: cita a matéria que fechou com menos itens ("fechou cedo") e a que exigiu mais, quando há
mais de uma fechada; avisa separadamente as matérias sem questão nenhuma e as que ficaram com
amostra pequena sem fechar.

## 4. Estado por tópico (o que a fatia 8 consome)
Sem tabela nova: `evento_estudo` já é a fonte da verdade (append-only) e `painel` é explicitamente
da fatia 10 (PRD §6, linha 10) — criar a materializada aqui seria antecipar escopo alheio. Em vez
disso, `dados/repositorio_diagnostico.py::sinais_por_topico(db, usuario_id, edital_id) ->
list[SinalTopico]` recomputa, por tópico do edital, a partir de `evento_estudo` marcado como
diagnóstico (§5): `sem_questao` (nunca teve questão), `sem_dado` (tem questão, nunca testado),
`a_estudar`/`dominado` (testado; `dominado` quando `estimativa_pct >= 80`, olhando o mesmo
`EstadoAgregado` calculado por tópico em vez de por matéria). É uma função pura de leitura, do
mesmo jeito que `estatisticas_topicos_vistos` (fio da memória) — a fatia 8 chama a mesma função
quando existir.

## 5. Marcação do evento e reaproveitamento das rotas de questão
Uma resposta do diagnóstico é um `evento_estudo(tipo="resposta")` igual a qualquer outra —
`repositorio_questao.registrar_resposta` já aceita `dados` (V5); grava `dados={"diagnostico":
True}`. Isso também decide "quando o diagnóstico está completo" sem sessão nova: cada `GET
/diagnostico` recomputa o estado a partir de **todos** os eventos com essa marca para o edital do
concurso principal — reiniciar o navegador não perde progresso, e trocar de concurso principal
(rotina) começa um diagnóstico novo (zero eventos marcados para aquele edital). Erro no diagnóstico
também nasce cartão (`repositorio_cartao.registrar_erro`), igual à V4 — a revisão espaçada já
aproveita o que ela errou no dia 0.

`GET/POST /diagnostico` reaproveita `_contexto_questao`/`_contexto_evento`/
`questoes/_cartao_questao.html`/`questoes/_resultado.html` de `api/questoes.py` (mesmo espírito de
`/revisar`: "responder no diagnóstico é, na prática, responder a questão de novo"). Novidades
próprias: a caixa "por que este item" antes de responder (`CandidatoItem.motivo`) e a tela de
resultado quando o candidato acaba.

## 6. Discordar (toque, sem agente)
F3.3 (o tutor que reescreve o plano) é fatia 8 — não a antecipo. O que cabe aqui, determinístico:
na tela de resultado, cada matéria `fechado=True` tem um link "Insistir nesta matéria" →
`GET /diagnostico?insistir=<materia>`, que passa essa matéria em `materias_forcadas` só para esta
chamada — um item a mais entra mesmo com a margem já fechada, sempre respeitando o teto de 30. Sem
questão sobrando, a tela avisa e não força nada.

## 7. Rotina — `perfil_estudo`
Migração 0011: `usuario` ganha `consentimento_dados_rotina` (bool), `consentimento_dados_rotina_em`
(datetime nullable), `consentimento_dados_rotina_versao` (string nullable) — as três colunas que
`docs/04-modelo-de-dados.md` nomeia como um campo lógico só ("bool, data, versão do texto"), mesmo
padrão de `EstadoCartaoFsrs` acrescentando colunas ao mínimo documentado. `perfil_estudo` nasce
como `ChaveUuid` **sem** `Carimbos` (só `criado_em`, sem `atualizado_em`) — é append-only por
versão, o mesmo motivo de `EventoEstudo` não usar o mixin.

`dominio/rotina.py` (puro): `DIAS_SEMANA` (seg…dom), `OPCOES_HORARIO`, `ENERGIAS_VALIDAS`,
`VERSAO_CONSENTIMENTO_ROTINA`, `DadosRotina` (Pydantic v2, valida as 7 chaves e 0–24h por dia,
`energia_tipica` em `ENERGIAS_VALIDAS`).

`dados/repositorio_perfil.py`: `salvar_perfil(db, usuario, dados) -> PerfilEstudo` (nova versão =
máxima existente + 1; grava o consentimento no `usuario` na mesma chamada — R-01 exige consentimento
separado antes de guardar `energia_tipica`) e `perfil_atual(db, usuario_id) -> PerfilEstudo | None`.

`GET/POST /rotina`: formulário com os 7 campos de horas, horário, energia, data-alvo, o `<select>`
de concurso principal (`listar_concursos_do_tenant`) e o checkbox de consentimento (obrigatório
toda vez que a energia é enviada — decisão simples e auditável, em vez de um consentimento que
"gruda" silenciosamente entre versões). Sem checkbox marcado → 400 com a mensagem, formulário
intacto.

**P-23 (concurso principal) resolvida aqui:** `repositorio_edital.concurso_principal(db,
tenant_id)` passa a olhar primeiro `perfil_estudo` (versão mais recente) do usuário deste tenant;
só cai para "o último edital subido" quando não há perfil ainda ou o `concurso_principal_id`
gravado não pertence mais ao tenant (defensivo). Assinatura não muda — quem já chama a função
(hoje, ninguém em produção; só o teste) ganha o comportamento novo de graça.

## 8. Rotas e navegação
`api/diagnostico.py` (`/diagnostico`), `api/rotina.py` (`/rotina`) — dois routers novos,
registrados em `main.py`. `base.html` ganha os dois links na barra lateral, junto de "Meus
editais"; `conta/conta.html` troca a frase "a rotina... chegam nas próximas fatias" pelo link real.
Sem concurso principal resolvível (nem heurística, nem perfil) → `/diagnostico` mostra a mensagem
"suba um edital primeiro" com link para `/editais/subir`, 200 (mesmo padrão de "sem questão" já
usado em `/topico/{slug}/questoes`).

## 9. Testes (TDD red-first)
- `tests/test_dominio_diagnostico.py`: fórmula de margem/estimativa nos extremos (acerta tudo,
  erra tudo, alterna), matéria sem questão nunca é candidata, cobertura de tópicos desempata
  dentro da matéria, parada em 30, parada por candidatos vazios, `sinais_por_topico`-equivalente
  puro (a função de agregação por tópico), determinismo (duas chamadas com a mesma entrada dão a
  mesma saída).
- `tests/test_dominio_rotina.py`: validação de `DadosRotina` (7 dias obrigatórios, faixa 0–24,
  energia fora do enum rejeitada).
- `tests/test_repositorio_perfil.py`: versão incrementa, `concurso_principal` prioriza o perfil,
  cai para o último subido sem perfil.
- `tests/test_repositorio_diagnostico.py`: `contagem_por_topico`/`sinais_por_topico` contra tópico
  sem questão nenhuma (Cascavel) e com questão (TJ-PR).
- `tests/test_rota_diagnostico.py`: contrato de erro `{codigo, mensagem, acao}` fora de sessão;
  fluxo completo com fixture de questões (curto, matéria fecha em poucos itens); "sem questão" sem
  quebrar; "insistir" funciona e respeita o teto de 30.
- `tests/test_rota_rotina.py`: sem checkbox → 400 com mensagem; com checkbox → grava perfil e
  consentimento; `concurso_principal_id` de outro tenant é rejeitado.

## 10. Fora desta fatia (registrado, não escondido)
Discriminação real por item (calibrador, fatia 11); `painel` materializado com curva/previsão
(fatia 10); F3.3 (tutor que reescreve o plano quando ela discorda de um bloco — aqui só o
"insistir" determinístico do diagnóstico); F1.3 completo (concursos acompanhados, split N/M —
fatia 1b; `concursos_acompanhados` fica gravado no `perfil_estudo` mas sem UI de edição própria);
clique-arrastar nas horas do dia (a tarefa pede "editável em clique"; a implementação usa sete
campos numéricos simples — sem JS novo — que cumprem o contrato funcional sem replicar a grade
clicável do protótipo, registrado como simplificação de front, não de contrato de dados).

# Fatia V4 — Revisão espaçada (cartão de erro + FSRS): plano de implementação
> O que é: o plano da V4 — o erro numa questão vira `cartao`, o FSRS agenda quando revisar, e uma
> tela de revisão reaproveita a tela de questão. Quando ler: antes de executar qualquer passo
> desta fatia e ao revisar o que foi feito; o diário fica em `V4-execucao.md`.

**Spec desta fatia:** linha V4 da tabela do PRD `docs/02-produto.md` §6 (F4.3); ADR-0022
(`docs/DECISOES.md`) decide a biblioteca `fsrs`; a linha `cartao` de `docs/04-modelo-de-dados.md`
§2 dá os nomes de campo.

## 1. Objetivo
Quando a Linda erra uma questão, nasce um `cartao` daquele tópico/questão com `origem="auto_erro"`
e o FSRS já aplicado (o erro é a primeira revisão). Uma tela nova (`GET/POST /revisar`) mostra os
cartões vencidos (`due <= agora`) na ordem do FSRS, reaproveitando a tela de questão para os
cartões ligados a uma `questao`. Cada revisão grava `evento_estudo(tipo="revisao_cartao")` **e**
atualiza o estado do cartão — as duas coisas.

## 2. Achado que muda o plano: `fsrs.Card` não tem `reps`/`lapses`
A ADR-0022 e o modelo de dados foram escritos antes de instalar a biblioteca. Instalada (`uv add
fsrs` → **6.3.2**, MIT, confirmado no `dist-info` da distribuição — bate com "py-fsrs 6.3" da
ADR-0022), o `fsrs.Card` desta versão tem estes campos: `card_id, state, step, stability,
difficulty, due, last_review` — **não tem `reps` nem `lapses`** (a lib parou de rastrear isso no
próprio `Card`; quem quer esse número mantém por fora).

Pior: **omitir `state`/`step` ao reconstruir o `Card` quebra o agendamento.** Prova (ida e volta
real, sem mock, registrada no diário): duas revisões seguidas (`Good`, `Good`) no mesmo cartão
dão `due` em **2026-01-03T00:10** com o `Card` completo; reconstruindo só de
`stability/difficulty/due/last_review` (sem `state`/`step`) o mesmo par de revisões dá `due` em
**2026-01-01T00:20** — quase dois dias de diferença, porque a segunda revisão cai na tabela de
"learning steps" errada sem saber que o cartão ainda estava em `Learning`.

**Decisão (registrada aqui e na tabela do PRD, não escondida):** a tabela `cartao` ganha, além dos
seis campos do modelo de dados, **duas colunas de mais**: `estado_fsrs` (`int`, o `fsrs.State`) e
`passo_fsrs` (`int | None`, o `fsrs.Card.step`) — sem elas, "estado serializado do `fsrs.Card`" não
é verdade. Os nomes dos seis campos do modelo de dados (`stability, difficulty, due, reps, lapses,
last_review`) continuam exatamente os de lá. `reps`/`lapses` não vêm do `fsrs.Card`: são contadores
próprios, calculados em `dominio/revisao.py` a cada revisão (`reps` soma 1 sempre; `lapses` soma 1
quando a resposta erra **e** o cartão já estava em `State.Review`, isto é, um esquecimento de algo
que já tinha sido aprendido — não a primeira vez, que é `Learning`).

## 3. Proxy de rating (decisão nova, documentada por não estar na spec)
FSRS pede uma nota entre `Again/Hard/Good/Easy`; o produto só tem `acertou` (bool) e
`confianca_declarada` (`certeza`/`duvida`), o mesmo par que a tela de questão já coleta. Proxy
simples, sem inventar sinal novo:

| acertou | confiança | rating FSRS |
|---|---|---|
| não | (qualquer) | `Again` |
| sim | dúvida | `Good` |
| sim | certeza | `Easy` |

`Hard` nunca é usado nesta fatia — exigiria um sinal de "acertei, mas com dificuldade" que a tela
não coleta (tempo de resposta é candidato futuro, não usado aqui para não inventar limiar).

## 4. Fuso (declarado, não resolvido)
Toda a camada de dados é UTC (`dados/base.py::DataHoraUtc`); `due` é comparado com
`agora_utc()`. Sem o fuso da Linda (não coletado em nenhuma fatia até aqui), um cartão "vence hoje
de manhã" pode aparecer um pouco cedo ou tarde no horário dela. **Limitação aceita e registrada**
— corrigir exige capturar fuso no perfil (fatia 7, `perfil_estudo`), fora do escopo desta fatia.

## 5. O que entra
1. Dependência `fsrs` 6.3.2 (MIT) — adendo à ADR-0022 em `docs/DECISOES.md`.
2. `dominio/revisao.py` — puro, sem I/O: `EstadoCartaoFsrs` (pydantic, os 8 campos serializados),
   `criar_estado_inicial`, `revisar`, `rating_por_resposta`, `montar_frente_verso`.
3. Migração `0007_cartao.py` + `Cartao` em `dados/modelos.py` (`UniqueConstraint(usuario_id,
   questao_id)` — cumpre "não regenere o que já existe").
4. `dados/repositorio_cartao.py` — `registrar_erro_ou_atualizar` (upsert idempotente por
   `(usuario, questão)`), `cartoes_vencidos` (`due <= agora`, ordenado por `due`), `revisar_cartao`
   (aplica o FSRS + grava `EventoEstudo(tipo="revisao_cartao")`).
5. `api/questoes.py` ganha a chamada a `registrar_erro_ou_atualizar` dentro de
   `responder_questao` (só quando `acertou is False`) e duas rotas novas, `GET/POST /revisar`,
   reaproveitando os helpers já existentes (`_contexto_questao`, `_contexto_evento`,
   `_afirmacoes_para_exibir` etc.) — nenhuma tela nova de perguntar/responder, só o roteamento e o
   "vencidos" em vez de "próxima questão do tópico".
6. `web/templates/questoes/_cartao_questao.html` — extrai o `<form>` de perguntar (hoje duplicado
   dentro de `topico.html`) parametrizado por `acao_post`; `topico.html` e a nova
   `revisao.html` incluem o mesmo parcial. `_resultado.html` ganha `proximo_url`/`proximo_rotulo`
   no contexto (em vez do link fixo para `/topico/{slug}/questoes`) para servir os dois fluxos.
7. Nav (`base.html`): link "Revisar hoje" quando logado.

## 6. Fora desta fatia (registrado, não implementado)
- Otimização de parâmetros por aluno (ADR-0022: só com ≥ 200 revisões).
- Cartão manual (`origem="manual"`) e `mnemonico_id` — a coluna existe (nullable), ninguém grava.
- Fio da memória (V5).
- Fuso do usuário (fatia 7, §4 acima).
- `Hard` no mapeamento de rating (§3 acima).

---
name: avaliador-de-feature
description: Use quando alguém pedir para avaliar, priorizar, comparar ou decidir se uma feature, ideia ou pedido de usuário entra no MVP, vai para o roadmap ou fica de fora do AprovaOS — inclusive "vale a pena", "entra ou não", "o que fazer primeiro", ordenar backlog, ou analisar uma sugestão da usuária-piloto.
---

# Avaliador de feature

## Visão geral
Uma feature é avaliada em **cinco eixos com número**, contra a tese do produto e o orçamento do dono, e recebe **um dos quatro vereditos**. A saída tem forma fixa (tabela abaixo), para que duas features avaliadas em dias diferentes sejam comparáveis. Opinião sem número ou sem fonte não é avaliação.

**Fontes obrigatórias antes de avaliar** (ler as seções citadas, não o arquivo inteiro): `docs/00-visao.md` §1, §4, §5, §6 (tese, princípios, cunha, fora de escopo) · `docs/01-pesquisa-mercado.md` §6 e §12 (o que concorrentes já vendem) · `docs/evidencias/2026-09-14-entrevista-linda.md` (o que a usuária pediu) · `docs/02-produto.md` (cunha vigente, quando existir). Se um arquivo não existir, escrever "arquivo ausente" no campo de evidência — nunca inventar.

## Passo 0 — separar mecanismos antes de avaliar
Se o pedido descreve mais de um mecanismo (lista com "e", vírgulas, "+", ou verbos diferentes — ex.: "a aula cita o tópico anterior **e** o bloco intercala itens antigos **e** há um resumo semanal"), escreva primeiro a linha `Mecanismos: 1) … 2) … 3) …` e faça **um bloco por mecanismo**. Um bloco descreve um mecanismo com um custo e um veredito.

## A saída é esta tabela, nesta ordem, um bloco por mecanismo — os 10 campos são obrigatórios
Um bloco com menos de 10 linhas é inválido: preencha o campo com "sem evidência", "zero", "nenhum identificado" ou "nada", mas nunca o omita.

| campo | o que escrever |
|---|---|
| **Feature** | nome curto + uma frase do que faz, na visão do aluno |
| **Aderência à tese** (0–3) | 0 = contraria um princípio da visão §4 · 1 = neutra · 2 = apoia a tese · 3 = é a tese ("agente decide, explica, mede, reajusta" ou "memória validada com fonte"). Citar o princípio ou seção. |
| **Evidência de usuário** (0–3) | 0 = nenhuma ("sem evidência") · 1 = inferida do mercado (citar §6 da pesquisa ou um gap `est-*`) · 2 = pedida por uma usuária (citar a rodada da entrevista) · 3 = pedida e marcada como básico/única coisa. Sempre com a citação ou "sem evidência". |
| **Custo de construir** (horas do dono) | número ou faixa: **P ≤ 8 h · M 8–24 h · G 24–60 h · GG > 60 h**. Diga o que consome as horas (front, backend, prompt, validação). |
| **Custo de operar** (R$ LLM por usuário Pro por mês) | número ou faixa com a conta: chamadas/dia × tokens × preço. Teto da visão §9: **≤ R$ 14,75** por usuário Pro (25 % de R$ 59). **"zero (sem LLM)"** quando a feature não chama modelo — custo de infra, loja de app ou manutenção **não** entra aqui (vai em "Custo de construir" ou "Risco"). |
| **Risco** | jurídico (fonte/licença/termos), qualidade (chega ao aluno sem validação?), LGPD (dado sensível), ou "nenhum identificado" — um por linha |
| **Depende de** | o que precisa existir antes (fatia da Fase 5, fonte do Motor, entidade de dados) |
| **Concorrente já faz?** | sim/não + quem (pesquisa §6/§7); se sim, o que seria diferente aqui |
| **Veredito** | exatamente um: **MVP** · **pós-MVP (fase 2)** · **pós-MVP (fase 3)** · **nunca** |
| **O que mudaria o veredito** | uma condição observável (ex.: "se o piloto mostrar D30 < 15 % por esquecimento") |

Depois dos blocos, duas linhas obrigatórias:
- **Conferência:** `blocos: N · campos por bloco: 10/10` (se algum bloco tiver menos, volte e complete).
- **Ordenação:** mecanismos por (aderência + evidência) ÷ horas de construir (use o meio da faixa: P = 4, M = 16, G = 42, GG = 80), maior primeiro, com o número.

## Regras de decisão
- **MVP** só com aderência ≥ 2 **e** evidência ≥ 2 **e** custo de construir ≤ M **e** operar dentro do teto. Uma exceção: table stakes (evidência 3 marcada como "básico") entra mesmo com aderência 1.
- **Nunca** quando contraria a visão §6 "fora de escopo para sempre" (ingerir material de terceiros, prometer aprovação, diagnóstico psicológico, vender dados) ou quando o risco jurídico não tem mitigação.
- Duas features que parecem uma só (ex.: FSRS × intercalação de temas) são **avaliadas separadamente** — cada bloco descreve um mecanismo, não uma área.
- Feature que a visão §6 já colocou numa fase recebe essa fase como veredito, salvo evidência 3 nova — e aí o bloco diz qual evidência.
- Custo de operar acima do teto → veredito pós-MVP até `docs/06-custos.md` provar o contrário, mesmo com evidência 3.

## Exemplo (um bloco)

| campo | valor |
|---|---|
| Feature | Aviso discreto de distração — "você está há 4 min neste item, pular?" sem bloqueio nem culpa |
| Aderência à tese | 2 — apoia "o agente decide, o aluno discorda em um toque" e "descansar é válido" (visão §4) |
| Evidência de usuário | 2 — pedida na entrevista, rodadas 1 e 4 ("aviso discreto, sem culpa") |
| Custo de construir | P (≈ 4 h): timer por item + `visibilitychange` no cliente; grava `EventoEstudo` |
| Custo de operar | zero — sem LLM |
| Risco | nenhum identificado (evento não é dado sensível) |
| Depende de | fatia 9 da Fase 5 (questões servidas) e `EventoEstudo` |
| Concorrente já faz? | não encontrado na pesquisa §6 |
| Veredito | **MVP** |
| O que mudaria | se o piloto mostrar que o aviso irrita (pedido de desligar em > 30 % das sessões) → vira opt-in |

## Erros comuns
- Escrever "faz sentido" ou "agrega valor" no lugar de um número — o campo fica vazio, não preenchido.
- Somar duas features num bloco e dar veredito "parcial" — separar.
- Dar aderência 3 a algo que só "ajuda a estudar": 3 é reservado ao mecanismo central (decidir/explicar/medir/reajustar; memória validada).
- Estimar horas sem dizer o que consome as horas.
- Esquecer o teto de R$ 14,75/usuário quando a feature chama LLM por sessão.

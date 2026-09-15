# Custos — cabe em R$ 100/mês?
> O que é: a planilha que a visão §7 exige antes de qualquer código de geração: infra + LLM do lote inicial do exame (TCU/AUFC como concurso do piloto) + custo por usuário Free/Pro, com preço oficial por token e as premissas explícitas. Quando ler: antes da fatia 2 da Fase 5 (Motor v0) e sempre que o alarme de teto disparar; atualizar quando um preço mudar (data em cada linha).

**Veredito:** cabe, com três condições: (1) o lote inicial é feito em ordem de peso do DNA e com teto diário (não "tudo de uma vez"); (2) geração em Flash-Lite, validação em Flash; (3) backup em serviço com faixa gratuita. Custo por usuário Pro ≈ **R$ 0,60–1,60/mês** contra o teto de R$ 14,75 (25 % de R$ 59) — o produto escala com a receita a ~2–3 %.

## 1. Premissas (mudar aqui muda tudo)
| premissa | valor | fonte / status |
|---|---|---|
| Câmbio | **US$ 1 = R$ 5,40 · € 1 = R$ 6,20** | **premissa a conferir no dia** (não medida nesta sessão); erro de ±10 % não muda o veredito |
| Gemini 2.5 Flash-Lite | US$ 0,10 in / 0,40 out por 1M tokens | oficial, https://ai.google.dev/gemini-api/docs/pricing (14/09/2026) |
| Gemini 2.5 Flash | US$ 0,30 in / 2,50 out | idem |
| Gemini 3.1 Flash-Lite (alternativa mais nova) | US$ 0,25 in / 1,50 out | idem |
| Gemini Embedding 2 | US$ 0,20 por 1M tokens (texto) | idem |
| Cloud Text-to-Speech | Standard US$ 4/1M chars; WaveNet/Neural2 US$ 16/1M; **free tier 4M chars (Standard) e 1M (demais)/mês** | **secundária** (costbench, 2026) — página oficial não abriu; confirmar antes da fatia 6 |
| Hetzner CX23 (2 vCPU, 4 GB, 40 GB, 20 TB) | **€ 5,49/mês** (subiu de € 3,99 em abr/2026) | **secundária** (bitdoze/whtop, set/2026); site oficial mostrou "not available" no fetch |
| Backup | Backblaze B2 ou Hetzner Object Storage, faixa gratuita/≈ € 1 | **a confirmar** (não medido) |
| E-mail transacional | faixa gratuita de um provedor (Resend/Brevo) | **a confirmar** |
| Domínio `.com.br` | ≈ R$ 40/ano | registro.br — **a confirmar** |
| Tokens por chamada | estimativas abaixo, por tipo de chamada | premissa de engenharia; o roteador mede em produção (`traco`) |

## 2. Infra fixa por mês
| item | R$/mês |
|---|---|
| VPS CX23 (€ 5,49) | 34 |
| backup (faixa gratuita) | 0–6 |
| domínio (R$ 40/ano) | 3 |
| e-mail (faixa gratuita) | 0 |
| **total infra** | **≈ 37–43** |
| **sobra para LLM** | **≈ 57–63** |

## 3. Lote inicial do concurso do piloto (TCU/AUFC, 118 tópicos, 6 provas públicas)
Chamadas estimadas por tópico e preço em US$ (in/out separados), Flash-Lite para gerar, Flash para validar.

| etapa | volume | tokens in / out (total) | modelo | US$ | R$ |
|---|---|---|---|---|---|
| Curador: classificar ~900 itens originais (6 provas) | 900 chamadas de 1,5k/0,2k | 1,35M / 0,18M | Flash-Lite | 0,21 | 1,1 |
| Embeddings (originais + gerados + dossiês) | ~4,6k textos × 300 tokens | 1,4M | Embedding 2 | 0,28 | 1,5 |
| Analista de edital → DNA | 3 chamadas de 60k/8k | 0,18M / 0,024M | Flash | 0,11 | 0,6 |
| Pesquisador → 118 dossiês | 6 chamadas/tópico: 40k/4k por tópico | 4,7M / 0,47M | Flash | 2,60 | 14,0 |
| Gerador → 30 questões/tópico (3.540) | 708 lotes de 5: 6k/1,5k | 4,25M / 1,06M | Flash-Lite | 0,85 | 4,6 |
| Validador → 3.540 questões | 1 chamada/questão: 5k/0,5k | 17,7M / 1,77M | Flash | 9,74 | 52,6 |
| Gerador de aula → 118 × (denso + leigo) | 12k/5k por tópico | 1,4M / 0,59M | Flash-Lite | 0,38 | 2,1 |
| Validador de aula | 118 × 15k/0,5k | 1,77M / 0,06M | Flash | 0,68 | 3,7 |
| Mnemônicos | 118 × 3k/0,3k | 0,35M / 0,035M | Flash-Lite | 0,05 | 0,3 |
| **total lote** | | | | **≈ 14,9** | **≈ 80** |

**Como cabe:** o `preenchedor` gera **em ordem de peso do DNA** com teto de **R$ 3/dia**; os 60 tópicos de maior peso (≈ 80 % da prova) custam ≈ R$ 40 e ficam prontos em ~2 semanas; o resto entra ao longo do mês seguinte. O validador é o item caro (66 %): reduzir para amostragem (validar 100 % das questões dos 60 tópicos principais, 50 % dos demais com sinalização pelo calibrador) corta ≈ R$ 18. **Nunca** cortar o validador nos tópicos que chegam ao aluno primeiro.

## 4. Custo por usuário por mês (regime)
| chamada | Free | Pro | tokens | modelo | US$/mês | R$/mês |
|---|---|---|---|---|---|---|
| Plano noturno (porquê) — 30/mês | Flash-Lite | Flash | 3k/0,5k | Free: 0,015 · Pro: 0,065 | | Free 0,08 · Pro 0,35 |
| Discordar / tutor | 3/dia máx | 20/dia máx; uso esperado 10/mês | 2k/0,3k | Flash-Lite | 0,003 | 0,02 |
| Resumo semanal | — | 4/mês | 10k/1k | Flash-Lite | 0,006 | 0,03 |
| Fio da memória (a) | cache por par de tópicos (lote) | | | | ≈ 0 | ≈ 0 |
| Áudio (TTS) — 20 aulas × 6k chars | — | 120k chars | WaveNet | 0 até ~8 usuários Pro (free tier 1M chars); depois 1,92 | 0–1,0 |
| Embeddings de anotações/cartões | desprezível | | | | | |
| **total** | | | | | | **Free ≈ 0,10 · Pro ≈ 0,40–1,60** |

Teto por usuário Pro (visão §9): R$ 14,75. Margem: **≥ 9×**. Free custa ≈ R$ 0,10 — 500 usuários Free = R$ 50/mês, o que **exige** o roteador degradar Free para cache/Flash-Lite e limitar 20 questões/dia (já é o tier).

## 5. Regime mensal projetado
| cenário | infra | Motor incremental (novos editais, leis, calibração) | usuários | total | dentro do teto? |
|---|---|---|---|---|---|
| Piloto (1 usuária, lote em andamento) | 40 | lote R$ 3/dia = 90 no 1º mês, depois ~10 | 1 | **≈ 130 no 1º mês**, ≈ 55 depois | **não no 1º mês** → lote em 2 meses ou cobrir o excedente uma vez; ≈ 55 depois: sim |
| 10 pagantes + 50 Free | 40 | 10 | 10×1,6 + 50×0,1 = 21 | ≈ 71 | sim |
| 40 pagantes + 200 Free | 40 | 15 | 64 + 20 = 84 | ≈ 139 | **não** — mas receita = R$ 2.360; custo = 6 % |

Regra que sai daqui para a ADR-0018: o teto de R$ 100 é **enquanto não há receita**; com receita, o limite passa a ser **LLM ≤ 25 % da receita** (visão §9) — e o alarme muda de "R$ 3/dia" para "% da receita do mês".

## 6. O que o roteador precisa medir para esta planilha virar realidade
Por chamada: modelo, tokens in/out, custo em R$ (tabela de preços versionada em `knowledge/precos.yaml` com data), usuário, tier, agente. Página `/admin/custos` soma por dia/agente/tier e compara com esta planilha. Quando o real divergir > 30 % da estimativa de uma linha, esta página é atualizada (data na linha).

# Decisões (ADRs curtos)
> O que é: registro de cada decisão relevante do AprovaOS — o que foi decidido, o que foi descartado e por quê. Quando ler: antes de propor algo que já pode ter sido decidido, e ao fechar qualquer item `[ADR]` da spec.

Formato: `ADR-NNNN — título · data · status (proposta | aceita | substituída por ADR-X)`. Acrescentar, nunca apagar: decisão revertida ganha ADR novo apontando para o antigo. ADRs da fábrica são citados como `fábrica/ADR-NNNN` (arquivo `~/PycharmProjects/fabrica-saas/docs/DECISOES.md`).

## ADR-0001 — Herdar as regras e decisões da fábrica por referência · 2026-09-14 · aceita (decisão do dono)
**Decisão:** o AprovaOS herda da fábrica (`~/PycharmProjects/fabrica-saas`) tudo que existir: regras de trabalho, ADRs (em especial fábrica/ADR-0001 tudo em arquivo, 0003 fases com portão humano, 0005 sem stubs de fases futuras, 0006 tempo medido em horas do dono, 0022 pesquisa neutra), evidências da regra de corte, seção Brasil da visão, pendência P-13. Herança é **por caminho**, nunca cópia — a fonte continua lá.
**Alternativas:** herdar só regras e ADRs; começar do zero.
**Por quê:** regra 8 do prompt (reutilize antes de criar). Copiar cria duas versões que divergem. Skills, agents e `template-saas/` da fábrica ainda não existem (pastas vazias em 14/09/2026); o que o AprovaOS criar primeiro pode ser absorvido pela fábrica.

## ADR-0002 — Sessões abrem dentro de `~/PycharmProjects/aprovaos` com `--add-dir` da fábrica · 2026-09-14 · aceita
**Decisão:** comando padrão `cd ~/PycharmProjects/aprovaos && claude --add-dir ~/PycharmProjects/fabrica-saas`.
**Contexto:** a Fase 0 foi executada de dentro da sessão da fábrica (o dono pediu para seguir dali); o `CLAUDE.md` deste repo só passa a valer em sessão aberta aqui.
**Por quê:** mesmo motivo de fábrica/ADR-0002 — o CLAUDE.md de outro repositório não vale aqui.

## ADR-0003 — Fase 0 usa Opus 5 em vez de Fable 5.1 · 2026-09-14 · aceita (decisão do dono)
**Decisão:** o prompt pede Fable 5.1; o dono decidiu seguir com Opus 5 ("já temos a spec desenhada, então pode usar o Opus 5 pra seguir a spec").
**Por quê:** a spec já fixa produto e arquitetura; o trabalho da Fase 0 é registrar decisões, não desenhar.

## ADR-0004 — Exame inicial: concursos públicos com Cebraspe + FGV, como hipótese · 2026-09-14 · aceita (decisão do dono; confirmação na Fase 1)
**Decisão:** o primeiro adapter é `concursos/` com bancas Cebraspe e FGV. A Fase 1 traz números (provas públicas por banca, padrão, calendário de 12 meses, tamanho do público) e o dono confirma ou troca no portão da Fase 1.
**Alternativas:** OAB/FGV (prova única, validação fácil pela parceira do dono); ENEM (público maior, sazonal, uma banca); deixar em aberto.
**Por quê:** maior volume de provas públicas e padrão de banca marcado (hipótese da spec §2); sem sazonalidade; OAB e ENEM entram como adapters sem refatoração (spec §10).

## ADR-0005 — Front web, mobile e gateway são decididos na Fase 3, com restrições já fixadas · 2026-09-14 · aceita (decisão do dono)
**Decisão:**
- **Front web:** ADR na Fase 3 comparando Next.js, SvelteKit e HTMX + Jinja por SEO, velocidade de desenvolvimento por IA e custo de manutenção com poucas horas.
- **Mobile:** web/PWA primeiro; app só com evidência (Fase 1 levanta; Fase 3 decide entre PWA com push, Capacitor e nativo, com gatilho de revisão registrado).
- **Gateway:** ADR na Fase 3, **depois** do estudo de cobrança sem CNPJ (P-02). Pix no dia 1 é fixo. Candidatos: Asaas (exige CNPJ), Mercado Pago como PF, Stripe (Pix por convite).
**Por quê:** as três decisões dependem de informação que ainda não existe (evidência mobile, custo por request, regras do Mercado Pago para PF); decidir agora seria assumir.

## ADR-0006 — A Fase 1 do AprovaOS compartilha a pesquisa da fábrica sobre o ramo de estudos · 2026-09-14 · proposta (confirmar com o dono ao abrir a Fase 1)
**Decisão proposta:** a fábrica decidiu focar a própria Fase 1 no mercado de estudos (fábrica/ADR-0027, `docs/evidencias/2026-09-14-escolha-de-nichos.md` §8 de lá). Em vez de duas pesquisas, uma: o `docs/01-pesquisa-mercado.md` da fábrica cobre mercado, concorrentes, reclamações e SEO do ramo; o `docs/01-pesquisa-mercado.md` do AprovaOS referencia esse arquivo e acrescenta só o que é do produto — bancas (volume de provas públicas, padrão, calendário), fontes de provas/gabaritos e de conhecimento aberto com licença, mapa de fontes do Motor de Conhecimento, bibliografia por matéria, evidência mobile e recomendação numérica de exame inicial.
**Alternativas:** rodar a Fase 1 do AprovaOS independente (duplica ~20 M tokens por nicho medidos na fábrica, fábrica/ADR-0024).
**Por quê:** custo de token medido pela fábrica; neutralidade preservada (a pesquisa da fábrica cobre o ramo inteiro, não só a tese do AprovaOS — fábrica/ADR-0022).

## ADR-0007 — Orçamento de R$ 100/mês para infra + LLM · 2026-09-14 · aceita (decisão do dono)
**Decisão:** o mesmo teto da fábrica (que vale para o portfólio inteiro). O Motor de Conhecimento roda em lotes pequenos, com cache por concurso/tópico, modelos baratos na rotina e fortes só em DNA/dossiê/validação. `docs/06-custos.md` (Fase 3) prova, com preço oficial por token, que o lote noturno do exame inicial cabe — **antes** de qualquer código de geração. Se não couber, encolhe o escopo do Motor (menos tópicos, menos concursos, sem TTS no início), não o teto.
**Alternativas:** R$ 300, R$ 1.000, definir depois da planilha.
**Por quê:** decisão do dono; coerente com a fábrica (infra grátis ou escala-a-zero, gateway sem mensalidade, nenhuma ferramenta paga). Risco registrado na visão §7 e em `docs/RISCOS.md` (Fase 3).

## ADR-0008 — Regra de corte e métricas-norte da spec §15, sem alteração · 2026-09-14 · aceita (decisão do dono)
**Decisão:** D+30 com < 30 pagantes **e** D30 < 15 % → pivotar exame/persona; D+60 sem tração → arquivar. Metas: ativação ≥ 60 %, conclusão do plano ≥ 50 %, D7/D30 ≥ 40 %/20 %, free→pro ≥ 3 %, LLM ≤ 25 % do preço, reporte de erro < 2 %, NPS ≥ 40. Acrescentada "sessões/semana ≥ 4" porque o prompt a pede e a spec não a tinha.
**Alternativas:** régua da fábrica (mais branda no D+30: 0 pagantes ou conversão < 2,5 % → arquiva; D+60 ≥ 10 pagantes → mantido); combinar as duas.
**Por quê:** decisão do dono. As salvaguardas da fábrica que não conflitam continuam valendo (churn involuntário antes de arquivar; D+30 não mede SEO) — visão §9.

## ADR-0009 — "AprovaOS" é codinome; o nome comercial sai de um trabalho de naming/branding · 2026-09-14 · aceita (decisão do dono)
**Decisão:** nenhum nome nem domínio fixado. Um trabalho de naming/branding (candidatos, disponibilidade de `.com.br` e marca no INPI, teste com o público da Fase 1) acontece antes de qualquer landing. Registrado em P-01; o momento (fim da Fase 1 ou início da Fase 2, quando já se conhece o público e os termos de busca) é decisão do dono.
**Por quê:** pedido dele ("sem opções fixas por enquanto, fazer trabalho de branding pra analisar, naming, etc"). Código e docs usam o codinome até lá; trocar nome em repositório é barato, trocar domínio indexado não é.

## ADR-0010 — Estrutura do repositório nasce por fase, sem stubs · 2026-09-14 · aceita
**Decisão:** herdada de fábrica/ADR-0005. A Fase 0 cria só `CLAUDE.md`, `docs/00-visao.md`, `docs/DECISOES.md`, `docs/PENDENCIAS.md`. `backend/`, `web/`, `adapters/`, `knowledge/`, `eval/`, `.claude/skills`, `.claude/agents`, `docs/01…07`, `RISCOS.md`, `HANDOFF.md` nascem quando a fase que os produz roda. `mobile/` só existe se a Fase 3 aprovar app.
**Por quê:** regra 4 do prompt (poucos arquivos bons); stub vazio parece cobertura e engana o próximo modelo.

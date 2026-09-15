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

## ADR-0011 — Exame inicial: concursos públicos com bancas Cebraspe + FGV · 2026-09-14 · aceita (decisão do dono no portão da Fase 1)
**Decisão:** o MVP (lado A) atende concurseiros de concursos organizados por Cebraspe e FGV. O adapter `concursos/` é o primeiro. **Condição registrada:** se P-11 (mapeamento das provas e termos de uso das duas bancas com navegador) mostrar que as provas não são coletáveis ou que os termos proíbem reprodução, a troca combinada é para **OAB**, não para ENEM.
**Alternativas:** ENEM (4,81 M inscritos em 2025, mas licença CC BY-ND do INEP proíbe derivados, um pico anual, SEO saturado por simulados grátis); OAB (47 provas abertas, banca única, ~130 mil inscritos por edição × 3/ano — público menor e ciclos de 4 meses).
**Condição resolvida em 14/09/2026 (P-11, `docs/evidencias/2026-09-14-p11-provas-cebraspe-fgv.md`):** Cebraspe tem API JSON pública e provas em PDF sem termos restritivos; FGV tem provas públicas com RSS, mas Termos de Uso que vedam automação — tratado como risco contratual (política de coleta + pedido de autorização), não como impedimento. A decisão deixa de ser provisória.
**Por quê:** `docs/01-pesquisa-mercado.md` §12: calendário contínuo (o plano diário do agente precisa de editais o ano inteiro), maior disposição a pagar medida (assinaturas de R$ 744 a R$ 2.375/ano nos incumbentes; IA-first a R$ 25–50/mês), fontes abertas de legislação com API e licença verificadas (LexML, STJ, Câmara/Senado) cobrindo as matérias de maior peso, e aderência à persona entrevistada (A1). Pontos contra assumidos: matéria-prima (provas) ainda não mapeada; concorrentes IA-first já vendem "edital → cronograma" — o pitch do produto não pode ser esse.

## ADR-0012 — Segundo exame (adapter da fase 2 do produto): OAB antes de ENEM · 2026-09-14 · aceita (decisão do dono)
**Decisão:** o segundo adapter é `oab/`, depois de tração no lado A com concursos.
**Alternativas:** ENEM primeiro (público maior); decidir só no PRD.
**Por quê:** mesma banca (FGV) do exame inicial, 47 edições abertas num único endpoint (`examedeordem.oab.org.br/EditaisProvas`), 3 ciclos por ano, matérias de direito já cobertas pelas fontes do Motor — custo marginal baixo. ENEM exige resolver a licença ND e uma sazonalidade que o agente diário sofre.

## ADR-0013 — Mobile: web responsiva + PWA instalável com push; sem app nativo; gatilho de revisão · 2026-09-14 · aceita (decisão do dono; detalhamento técnico na Fase 3)
**Decisão:** uma base de código web, responsiva, instalável como PWA com Web Push para o check-in matinal (iOS/iPadOS 16.4+ exige instalação na Tela de Início — WebKit). Nenhum app nas lojas. **Gatilho de revisão:** com ≥ 500 usuários ativos, medir D30 com e sem PWA instalada; se a PWA não retiver melhor e o push no iOS for a barreira principal, reavaliar Capacitor (nunca nativo com poucas horas/semana).
**Alternativas:** web só (perde push); app nativo/cross (segunda base de código; veto da fábrica `comp1-12`).
**Por quê:** `docs/01-pesquisa-mercado.md` §10: 58 % dos usuários de internet acessam só pelo celular (87 % nas classes DE) — a web tem de ser boa no celular; o app do Estratégia (1,4★, 376 avaliações) mostra o custo de app mal mantido; a usuária entrevistada estuda no notebook (n=1). `mobile/` não nasce (ADR-0010).

## ADR-0014 — Skills nascem pela `superpowers:writing-skills`, não pelo `skill-creator` · 2026-09-14 · aceita (decisão do dono, Fase 2)
**Decisão:** neste repositório, toda skill nova segue o ciclo RED → GREEN → REFACTOR da skill `superpowers:writing-skills` (baseline com subagente sem a skill, escrever a skill contra as falhas observadas, reexecutar num modelo menor). Substitui a regra 8 do `CLAUDE.md` onde ela cita o `skill-creator`. P-05 fica resolvida.
**Alternativas:** instalar `skill-creator@claude-plugins-official` (exige confirmação do dono num diálogo do Claude Code a cada sessão nova); escrever SKILL.md à mão sem teste.
**Por quê:** a `writing-skills` já está instalada, tem o mesmo propósito e obriga o teste que a regra 8 pede ("precisam funcionar num modelo menor"). Se o `skill-creator` vier a ser instalado, os dois podem coexistir; o teste com subagente continua obrigatório.

## ADR-0015 — Preço de lançamento do Pro: R$ 59/mês, anual R$ 490 · 2026-09-14 · aceita (decisão do dono, hipótese a validar)
**Decisão:** Free (diagnóstico, DNA de 1 concurso, plano básico, 20 questões/dia, painel com curva) · **Pro R$ 59/mês ou R$ 490/ano (≈ R$ 40,80/mês, −31 %)** · Elite (R$ 149+, só na fase 3). Pix e cartão desde o dia 1; cancelamento em um clique; no limite do tier, o roteador degrada o modelo, nunca corta a sessão.
**Alternativas:** R$ 49 (protótipo); R$ 39 (parear com Tec Concursos).
**Por quê:** `docs/01-pesquisa-mercado.md` §6 — IA-first cobram R$ 25–50/mês e vendem cronograma; incumbentes cobram R$ 744 a R$ 2.375/ano e vendem conteúdo humano; o AprovaOS vende resultado acompanhado com base validada, e a única usuária entrevistada leu R$ 49 como "barato". Testar a faixa alta primeiro: baixar preço é fácil, subir não. Métrica de corte da visão §9 (custo LLM ≤ 25 % do preço → ≤ R$ 14,75/usuário Pro/mês) vale para a Fase 3 (`06-custos.md`).

## ADR-0016 — Piloto com uma usuária real antes dos 10 primeiros pagantes · 2026-09-14 · aceita (decisão do dono)
**Decisão:** a Linda (persona A1, concurseira que trabalha) usa o produto como piloto, sozinha, por um período definido no PRD, e o produto evolui com o estudo dela antes de abrir para qualquer outra pessoa. Os 10 primeiros pagantes e a regra de corte (visão §9) contam **a partir da abertura pública**, não do piloto.
**Alternativas:** abrir direto para 20–30 concurseiros do círculo dela; SEO programático desde o início.
**Por quê:** poucas horas por semana do dono — um piloto de n=1 com acesso direto rende mais aprendizado por hora do que dez usuários remotos; a entrevista mostrou que ela sabe articular o que falta (`2026-09-14-entrevista-linda.md`). Risco assumido: viés de n=1 e proximidade — o PRD define critérios de saída do piloto que não dependem só da opinião dela.

## ADR-0017 — Backend: Python 3.13 + FastAPI + SQLAlchemy 2.0 + Pydantic v2, gerido por `uv` · 2026-09-14 · aceita (decisão do dono, Fase 3)
**Decisão:** `backend/` em Python **3.13** pinado (`.python-version`, `uv`), FastAPI (0.141) para HTML e JSON, SQLAlchemy 2.0 (`DeclarativeBase`/`Mapped`) com Alembic, Pydantic v2 em toda fronteira. Resolve P-07 (local é 3.14.3; o alvo é 3.13 porque é a versão cujas docs baseiam as decisões — CLAUDE.md global — e `litellm` declara `<3.15`).
**Alternativas:** Django (mais pesado, ORM próprio); Litestar (menor ecossistema).
**Por quê:** stack de referência do dono; uma linguagem para domínio, agentes, jobs e templates; versões e licenças conferidas no PyPI em 14/09/2026.

## ADR-0018 — Agentes em ADK (`google-adk` 2.9, Apache-2.0) com Gemini; roteamento por tier e teto de gasto · 2026-09-14 · aceita (decisão do dono)
**Decisão:** cada papel da spec §7.2 é um `LlmAgent` com `output_schema` Pydantic, `include_contents='none'`, tools que só passam pelo repositório; orquestração em código (pipeline), sem agente-orquestrador; `Runner` + `DatabaseSessionService`. Modelos: **Gemini 2.5 Flash-Lite** para gerar/porquê/tutor, **Gemini 2.5 Flash** para validar, DNA e dossiês (preços oficiais em `06-custos.md`); roteador por tier com teto diário (R$ 3/dia sem receita; 25 % da receita com receita) e degradação que nunca bloqueia a sessão. O LLM **não decide o plano**: escolhe entre candidatos por regra e escreve o porquê.
**Alternativas:** pydantic-ai + LiteLLM (multi-provedor, mais uma camada); LangGraph (pesado); cru (sem tracing/sessão prontos).
**Por quê:** custo (Flash-Lite US$ 0,10/0,40 por 1M) cabe no teto; ADK é a referência do dono; ADK aceita outros provedores via LiteLLM se o Google mudar preço (R-12). Docs: https://adk.dev/agents/llm-agents/ .

## ADR-0019 — Front: HTMX + Jinja + ilhas de JS vanilla; PWA · 2026-09-14 · aceita (decisão do dono)
**Decisão:** páginas server-rendered (Jinja) com HTMX para interação; ilhas de JS vanilla reaproveitadas do protótipo (popover de referência, grifos/anotações, gráficos SVG, controles segmentados); tokens de tema desde o dia 1 (claro/escuro), movimento só com `prefers-reduced-motion: no-preference`, atalhos de teclado; `manifest.json` + service worker + Web Push. Padrões de UI em `docs/evidencias/2026-09-14-aprendizados-mockups.md` §3 viram requisitos (resolve P-10).
**Alternativas:** SvelteKit; Next.js.
**Por quê:** uma base de código em Python, SEO nativo para as páginas programáticas (Fase 6), tudo que o protótipo fez já é vanilla JS; poucas horas do dono.

## ADR-0020 — Deploy: VPS Hetzner CX23 + Docker Compose (Caddy, web, jobs, Postgres 16 + pgvector) · 2026-09-14 · aceita (decisão do dono)
**Decisão:** um host; `pg_dump` diário para storage externo com restauração testada por mês; deploy por GitHub Actions via SSH após testes; `.env` só no servidor. Preço € 5,49/mês (fonte secundária, set/2026 — confirmar no console). Região UE (latência aceitável para HTMX; R-13).
**Alternativas:** Fly.io; Cloud Run + Cloud SQL (Cloud SQL mínimo consome o teto); Railway.
**Por quê:** é a única opção que deixa ≈ R$ 60/mês para LLM (`06-custos.md` §2).

## ADR-0021 — Vetores: pgvector no mesmo Postgres · 2026-09-14 · aceita
**Decisão:** `embedding vector(768)` em `questao`, `dossie_topico` e `aula` com Gemini Embedding 2; índice HNSW quando > 50k linhas; dedup por cosseno ≥ 0,97.
**Alternativas:** Weaviate/Qdrant (mais um serviço no host); só BM25.
**Por quê:** volume do MVP (≈ 5k itens) cabe em Postgres; um serviço a menos para manter.

## ADR-0022 — Revisão espaçada com `fsrs` (py-fsrs 6.3, MIT); diagnóstico adaptativo por proxy, não TRI completa · 2026-09-14 · aceita
**Decisão:** cartões usam `fsrs.Scheduler`/`Card`/`Rating` (estado serializado em `cartao`); parâmetros padrão no MVP, otimização por aluno quando houver ≥ 200 revisões. Diagnóstico e proficiência usam **proxy**: estimativa por matéria = média ponderada pela discriminação estimada dos itens (calibrador) com intervalo por bootstrap; seleção do próximo item pelo que mais reduz a variância da matéria mais incerta; termina em ≤ 30 itens ou ±8 em todas. TRI 2PL de verdade só quando o calibrador tiver n ≥ 300 respostas por item nos itens-âncora.
**Alternativas:** SM-2 (pior que FSRS, sem parâmetros por aluno); py-irt/2PL já no MVP (sem dados para calibrar).
**Por quê:** FSRS é aberto, mantido e usado pelo Anki (pesquisa §4); TRI sem dados calibrados é falsa precisão — a previsão v0 já é honesta com intervalo.

## ADR-0023 — Ingestão de PDF com `pypdfium2` (BSD/Apache) + `pdfplumber` (MIT); PyMuPDF vetado (AGPL) · 2026-09-14 · aceita
**Decisão:** texto e render por `pypdfium2`; tabelas de gabarito por `pdfplumber`; segmentação em itens por adapter (regex de numeração + regras da banca); OCR só se uma prova vier como imagem (Tesseract, Apache). PyMuPDF não entra: dupla licença AGPL/comercial (PyPI, 14/09/2026) incompatível com SaaS fechado sem licença paga.
**Por quê:** licenças conferidas; PDFs das duas bancas são texto (P-11: caderno FGV com 36 páginas extraído por `pdftotext` sem OCR).

## ADR-0024 — Observabilidade: OpenTelemetry com spans gravados em Postgres (`traco`) e página de admin; sem vendor no MVP · 2026-09-14 · aceita
**Decisão:** instrumentar FastAPI e agentes ADK com OTel; exporter próprio grava em `traco` (modelo, tokens, custo, latência, usuário, agente); `/admin/tracos` e `/admin/custos`; alarme por e-mail (teto, rejeição do validador). Trocar o exporter para um backend externo quando houver volume.
**Alternativas:** Langfuse/Logfire/Grafana desde o início (custo ou serviço a mais; não verificados nesta sessão).
**Por quê:** "traços de agente obrigatórios" (PROMPT Fase 3) com zero custo e zero serviço novo; a planilha de custos precisa desses dados.

## ADR-0025 — Cobrança como pessoa física no piloto e nos 10 primeiros: Mercado Pago (link/assinatura, Pix sem taxa para PF) atrás de uma interface `GatewayPagamento`; MEI ao chegar a 10 pagantes · 2026-09-14 · aceita (decisão do dono; taxas exatas pendentes — P-02)
**Decisão:** `GatewayPagamento` (criar cobrança, criar assinatura, cancelar, webhook) com implementação Mercado Pago; Pix e cartão; sem boleto. O que foi verificado: para PF, criar link de pagamento não custa e Pix não tem taxa (blog oficial do Mercado Pago, set/2026 — secundário); o produto "Planos de assinatura" existe (página oficial, sem detalhe legível). **Não verificado:** taxas de cartão para PF e elegibilidade de assinatura recorrente para conta PF — o dono confirma na própria conta antes da fatia 12. Imposto: rendimento de PF recebido de PF → **Carnê-Leão mensal** pelo Carnê-Leão Web (e-CAC), pago até o último dia útil do mês seguinte (Receita Federal, https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/pagamento/carne-leao/carne-leao). Ao chegar a 10 pagantes: abrir MEI e migrar para PJ (Asaas ou Mercado Pago PJ) sem mudar a interface.
**Alternativas:** Stripe (exige CNPJ no Brasil — não verificado nesta sessão); Asaas PF; abrir MEI já.
**Por quê:** o dono escolheu ficar PF até 10 pagantes; a interface isola a troca.

## ADR-0026 — Auth: e-mail + senha (argon2) e Google OAuth via Authlib; sessão por cookie assinado; sem serviço externo · 2026-09-14 · aceita
**Decisão:** `authlib` para OAuth do Google, `argon2-cffi` para senha, sessão server-side em Postgres com cookie `HttpOnly/Secure/SameSite=Lax`; verificação de e-mail; sem JWT no MVP (HTMX é same-origin).
**Alternativas:** fastapi-users (mais opinativo), Auth0/Clerk (custo e dependência).
**Por quê:** simples, auditável, sem custo; RF-20.

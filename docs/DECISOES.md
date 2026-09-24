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
**Adendo 17/09/2026 (abertura da V2, conferido no pacote `google-adk` 2.9.1 instalado num venv descartável):** `LlmAgent(name, model, instruction, description, output_schema: type[BaseModel], output_key, include_contents='none')` — com `output_schema` **não** se usam `tools` (doc oficial); `Runner(agent=, app_name=, session_service=)`; `await InMemorySessionService().create_session(app_name=, user_id=, session_id=)`; `async for evento in runner.run_async(user_id=, session_id=, new_message=types.Content(role='user', parts=[types.Part(text=…)]))`, final em `evento.is_final_response()`, JSON em `evento.content.parts[0].text`, tokens em `evento.usage_metadata`. `DatabaseSessionService` exige o extra `google-adk[db]` (sqlalchemy) — **adiado**: os agentes de lote não têm conversa e os traços vão na nossa tabela `traco` (ADR-0024); reavaliar quando houver `tutor-porque` (fatia 8). Chave via `GOOGLE_API_KEY` (AI Studio, ADR-0030). O adaptador ADK fica atrás de uma porta (`Protocol`) para os testes usarem um dublê; o teste real com Gemini é marcado `llm` e só roda com a chave.
**Adendo 18/09/2026 (passos 12b/12c da V3, chave real do dono):** `gemini-2.5-flash` passou a responder `404` ("This model is no longer available to new users") para chaves novas do AI Studio — os modelos decididos acima ficam **substituídos** para quem gera chave a partir de 18/09/2026. `modelo_dna` (`analista-de-edital`, DNA do edital — é raciocínio) = **`gemini-3.6-flash`**; `modelo_classificacao` (`classificador`, tópico de item de prova num vocabulário fechado — é "simple data processing", como a própria página do modelo o descreve) = **`gemini-3.5-flash-lite`**, o mais barato da família. Preços novos e fonte em `docs/06-custos.md` (adendo do mesmo dia). No **free tier** (a chave do piloto) o custo real de entrada/saída é **zero**; o achado que importa para operar é a **cota**, não o preço: **5 requisições/minuto** e, mais restritivo, **20 requisições/dia por projeto por modelo** (`quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier`) — a cota é por modelo, então um modelo esgotado no dia não impede usar outro. `gemini-3.5-flash-lite` também **não aceita** `thinking_config` (`400 INVALID_ARGUMENT` quando setado) — nenhum campo de "pensamento" é enviado para ele.

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

**Adendo 19/09/2026 (V4):** instalado `fsrs==6.3.2` (`uv add fsrs`), licença MIT confirmada no
`dist-info` da distribuição instalada (não de memória) — bate com "py-fsrs 6.3" desta ADR. Achado
que muda a tabela `cartao`: o `fsrs.Card` desta versão **não tem `reps`/`lapses`** (campos reais:
`card_id, state, step, stability, difficulty, due, last_review`); `reps`/`lapses` viram contadores
próprios em `dominio/revisao.py`, e a tabela ganha duas colunas a mais do que o modelo de dados
listava (`estado_fsrs`, `passo_fsrs`) porque reconstruir o `Card` sem `state`/`step` recalcula o
`due` errado — provado por um teste de ida e volta com valores reais (duas revisões `Good/Good`
divergem em quase dois dias com e sem esses dois campos). Detalhe e evidência em
`docs/fatias/V4-revisao-espacada.md` §2 e `V4-execucao.md`.

## ADR-0023 — Ingestão de PDF com `pypdfium2` (BSD/Apache) + `pdfplumber` (MIT); PyMuPDF vetado (AGPL) · 2026-09-14 · aceita
**Adendo 17/09/2026 (V2):** `pypdfium2` 5.13 em produção para texto de edital (`dominio/pdf.py`); `pdfplumber` ainda não entrou (fica para o gabarito em tabela, V3).
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
**Adendo 19/09/2026 (fatia 12, `pagamento/mercado_pago.py`):** `GatewayPagamento` implementado
por completo, atrás de `MERCADO_PAGO_ACCESS_TOKEN`/`_WEBHOOK_SECRET` (Ruling 46/ADR-0044) e
testado contra um gateway falso (`tests/dubles_pagamento.py`) — sem conta real, o código fica
pronto e inerte. Endpoints e campos citados nos docstrings vêm do **OpenAPI oficial** que o
Mercado Pago mantém em `github.com/mercadopago/openapi` (`spec3.json`, recurso `/preapproval`;
`schemas/webhooks.yaml`, formato do `x-signature`) — a documentação humana interativa
(mercadopago.com.br/developers) é renderizada em JS e não expõe o corpo sem executá-la. Os dois
pontos não verificados desta ADR continuam abertos (P-02); a fatia acrescenta um terceiro,
P-72 (qual `id` exatamente entra no manifesto HMAC do webhook — a fonte oficial não fecha isso) e
um quarto, P-75 (pagamento recusado/`em_atraso` não tem produtor real ainda, só o domínio já sabe
tratar). Ver `docs/fatias/12-execucao.md`.

## ADR-0026 — Auth: e-mail + senha (argon2) e Google OAuth via Authlib; sessão por cookie assinado; sem serviço externo · 2026-09-14 · aceita
**Decisão:** `authlib` para OAuth do Google, `argon2-cffi` para senha, sessão server-side em Postgres com cookie `HttpOnly/Secure/SameSite=Lax`; verificação de e-mail; sem JWT no MVP (HTMX é same-origin).
**Alternativas:** fastapi-users (mais opinativo), Auth0/Clerk (custo e dependência).
**Por quê:** simples, auditável, sem custo; RF-20.
**Adendo 17/09/2026 (V1):** assinatura do cookie por HMAC-SHA256 da stdlib (`hmac`/`secrets`), valor `<token>.<hmac>`, só `sha256(token)` no banco; `itsdangerous` não entrou. Verificação de e-mail adiada (P-21).

## ADR-0027 — Piloto pelo edital da usuária em PDF, com questões originais da base Cebraspe nos mesmos tópicos · 2026-09-17 · aceita (decisão do dono, abertura da Fase 4)
**Decisão:** o piloto (ADR-0016) não usa um concurso do catálogo Cebraspe+FGV: a Linda **sobe o edital em PDF** do concurso que for prestar (assessor de gabinete e similares em Cascavel-PR, matérias de Direito, bancas locais). O `analista-de-edital` gera o `DnaConcurso` a partir do PDF (F1.5 sobe da fatia 13 para as primeiras fatias); as **questões originais** vêm da base Cebraspe (API pública, P-11) nos mesmos tópicos do edital, sempre exibidas com banca/órgão/ano/item — nunca apresentadas como "da banca dela". A ADR-0011 continua valendo para o catálogo e para o produto aberto; esta ADR vale para o piloto e para qualquer aluno cujo concurso não esteja no catálogo.
**Alternativas:** trocar o exame inicial para as bancas locais dela (refazer P-11 para bancas sem API, volume pequeno de provas, atraso do piloto); manter Cebraspe+FGV puro e ela estudar para um concurso que não é o dela (fere "estuda de verdade", PRD §6).
**Por quê:** o dono não lembra o concurso exato e os editais dela chegam avulsos; sem PDF o piloto não tem alvo. As matérias (Constitucional, Administrativo, Civil, Processo) se sobrepõem às da Cebraspe, então a base já planejada serve; o que muda é a ordem das fatias (ADR-0028). **Consequência:** o DNA de edital avulso não tem "peso real por prova" nem "corte histórico" (F1.4) — o pipeline marca esses campos como `desconhecido` e o DNA declara a lacuna, em vez de inventar. Estilo da banca local vira **P-17**. Fonte: PRD §3 F1.5/F4.1; `docs/evidencias/2026-09-14-p11-provas-cebraspe-fgv.md`.

## ADR-0028 — Piloto v0 antes das fatias 1–9: fatia vertical mínima primeiro, tudo que ficou de fora rastreado · 2026-09-17 · aceita (decisão do dono, abertura da Fase 4)
**Decisão:** o piloto começa com um **piloto v0** = uma fatia vertical mínima: conta → subir edital (PDF → DNA reduzido + edital verticalizado) → questões originais Cebraspe por tópico, com origem → cartão automático de erro + FSRS → fio da memória (b). Dossiês, geração validada, aulas, diagnóstico, plano do dia, check-in e painel entram **enquanto ela usa**, na ordem da tabela "Fatias" do PRD §6, que é a única fonte de estado das fatias (o que entrou, o que ficou de fora e por quê). O piloto completo (critérios de saída do PRD §6) só conta a partir de a fatia 8 (plano + check-in) estar no ar.
**Alternativas:** ordem da spec §17 (fatias 1–9 inteiras antes de ela entrar; ~180 h de features + Motor; o maior risco — geração validada — no caminho crítico).
**Por quê:** poucas horas por semana do dono; o que ela pediu na entrevista (questões reais com ano/prova, edital verticalizado, "me fazer lembrar") são exatamente os 4 mecanismos de melhor score do PRD §8 e não dependem de LLM em tempo de uso; a spec §17 é "primeiro todo o Motor" e o CLAUDE.md regra 9 pede fatias verticais. Condição do dono: **"temos que rastrear tudo para seguir evoluindo"** — por isso a tabela do PRD §6 ganha coluna de status e nada sai da lista sem justificativa escrita.

## ADR-0029 — Squad em subagents nativos (`.claude/agents/`), Agent Teams opt-in por sessão; P-06 resolvida com teste registrado · 2026-09-17 · aceita (provisória até o dono rodar o teste com a flag no início da sessão)
**Decisão:** o squad da Fase 4 nasce como **definições de subagent** em `.claude/agents/` (papéis deste produto) somadas às três globais que o dono já tem (`po-planejador`, `dev-executor`, `revisor`). A mesma definição serve como teammate quando um Agent Team for útil — a doc oficial diz que "subagent definitions" são reaproveitadas pelos teammates (tools, model e corpo). Agent Teams **não ficam ligados por padrão**: usam-se por sessão (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude`) só para pesquisa/revisão paralela com papéis independentes — nunca para as fatias da Fase 5, que são sequenciais, TDD e tocam os mesmos arquivos.
**Teste feito em 17/09/2026 (Claude Code 2.1.275):** flag colocada em `.claude/settings.local.json` com a sessão já aberta; dois agentes nomeados no prompt ("revisor-visao", "revisor-prd"), Sonnet, tarefa read-only com troca de mensagem. Resultado: nasceram como **subagents comuns** (nenhum `~/.claude/teams/` criado — a doc diz que o time é montado no início da sessão); nenhum tinha `ListAgents`; `SendMessage` pelo nome falhou (`No agent named 'revisor-visao' is reachable`); custo ~126 k tokens de subagente para duas leituras triviais. O teste **com a flag na abertura** fica como **P-18** (dono), porque exige reabrir o Claude Code.
**Alternativas:** Agent Teams ligados no `settings.json` (a doc avisa que qualquer subagent nomeado vira teammate e times se formam sem pedir; cada teammate é uma sessão inteira; sem `/resume`); só skills, sem agents (perde a padronização de papel e o `model: sonnet` por papel, que a fábrica mediu como necessário — ADR-0018 de lá).
**Por quê:** a doc oficial recomenda subagents para "tarefas sequenciais, edição do mesmo arquivo ou muitas dependências" — é o caso da Fase 5; a fábrica mediu subagentes como 43 % do consumo de uma sessão (ADR-0018 da fábrica), e teammates custam mais. Fonte: https://code.claude.com/docs/en/agent-teams (lida em 17/09/2026).

## ADR-0030 — Piloto v0 roda só local (Docker Compose na máquina do dono) até o piloto completo; Gemini pelo free tier do AI Studio em `.env`; contato do coletor = e-mail do dono · 2026-09-17 · aceita (decisão do dono, abertura da Fase 5)
**Decisão:** nenhuma VPS nem domínio até a fatia 8 (plano + check-in) estar no ar — a Linda usa o produto na máquina/rede do dono. O deploy da ADR-0020 (Hetzner + Caddy + GitHub Actions) sai do caminho crítico e vira parte da fatia 8. A chave do Gemini vem do **Google AI Studio (free tier)** de uma conta da usuária ou do dono, guardada em `backend/.env` (git-ignored) e lida só por fábrica de configuração; o teto diário do roteador (§8 da arquitetura) vale desde a primeira chamada, e a mudança para conta paga/Vertex é troca de variável. `user_agent` do coletor e pedidos de autorização a bancas usam `vlfcandido@gmail.com` até haver domínio. Nome: "AprovaOS" (codinome) na UI até a Fase 6 (P-01).
**Alternativas:** VPS desde a V1 (custo e horas antes de haver o que servir); Vertex AI (setup GCP); nome agora (atrasa uma sessão).
**Por quê:** poucas horas por semana e zero custo até o produto ter valor; o free tier cobre o lote inicial pequeno (só os tópicos do edital dela). Risco assumido: limites de taxa do free tier — o roteador degrada em vez de falhar (arquitetura §8).

## ADR-0031 — Template base (fatia V1) construído do zero neste repositório; `fabrica-saas/template-saas/` está vazio e os templates externos não casam com a stack · 2026-09-17 · aceita
**Decisão:** a V1 nasce aqui (`backend/`, `web/`, `compose.yaml`, `.github/workflows/ci.yml`) e, quando estável, é copiada para `fabrica-saas/template-saas/` (pendência da fábrica). Avaliados e descartados: `fastapi/full-stack-fastapi-template` (MIT; front React/Vite + fastapi-users — contraria ADR-0019 HTMX e ADR-0026 auth própria; https://github.com/fastapi/full-stack-fastapi-template) e `fastapi-users` (MIT; opinativo, já descartado na ADR-0026; https://github.com/fastapi-users/fastapi-users). Reaproveitamos ideias, não código: layout `app/`, Alembic com `env.py` sem I/O em import, `pytest` com banco por fixture.
**Testes sem Docker:** V1 e V2 não têm coluna vetorial, então os testes de repositório rodam em SQLite em memória; testes marcados `@pytest.mark.postgres` rodam só com `DATABASE_URL_TEST` definido. A partir da V3 (pgvector) a suíte exige Postgres (Compose local).
**CI:** `.github/workflows/ci.yml` (pytest, ruff, mypy, checagem de import sem efeito colateral) entra na V1; o repositório ainda não tem remoto — criar o repo no GitHub é decisão do dono (P-19).
**Por quê:** CLAUDE.md regra 8 (fábrica → externo → do zero) cumprida com veredito escrito; a stack da ADR-0017/0019/0026 é específica demais para um template genérico valer o custo de adaptação.
**Adendo 17/09/2026:** V1 entregue (66 testes, `scripts/checar.sh` verde, fluxo real com Alembic + uvicorn verificado); `httpx2` no lugar de `httpx` nos testes (Starlette 1.6 depreciou `httpx` no `TestClient`); copiar para `fabrica-saas/template-saas/` = P-20.

## ADR-0032 — Analista de edital com fallback determinístico por regras; DNA em JSON inteiro; Gemini em JSON mode (sem `output_schema`) · 2026-09-17 · aceita (fatia V2)
**Decisão:** o DNA de um edital nasce sempre — por IA quando há chave e teto, senão **por regras** (`montar_dna_por_regras`: parser do conteúdo programático + fatos por regex, peso por pontos, uniforme por tópico, lacunas declaradas); o resultado da IA passa por `verificar_dna` (as 4 verificações da skill `dna-do-concurso`) e, se reprovar ou estourar, cai para regras com o motivo gravado em `dna_concurso.motivo_fallback` e mostrado na página ("Gerado por regras — <motivo>"). `dna_concurso.conteudo` guarda o JSON inteiro do contrato (as 11 colunas JSON do modelo §3 não nasceram — nada as consulta por dentro). O `AnalistaAdk` usa `LlmAgent` **sem `output_schema`** e com `GenerateContentConfig(response_mime_type="application/json")`, porque a Gemini Developer API (AI Studio) rejeita `additionalProperties` — erro literal no diário V2, passo 10 — e o contrato da skill tem `dict` de chaves livres (`pesos.materia/topico`, `incidencia`); a validação é do Pydantic (`DnaConcurso.model_validate_json`) + `verificar_dna`. Porta assíncrona `AnalistaDeEdital(Protocol)`; uso de tokens sai por callback `ChamadaLlm` e vira linha em `traco` (`estimar_custo_brl` com os preços de `06-custos.md`); `TetoDiario` R$ 3/dia. `reportlab` (BSD-3) entra como dependência de dev para gerar o PDF de fixture (`scripts/gerar_fixture_pdf.py`).
**Alternativas:** mudar o contrato da skill para listas (mexe numa skill testada; adia); Vertex AI (aceita `additionalProperties`, mas exige GCP — ADR-0030 escolheu AI Studio); falhar sem chave (a Linda não conseguiria começar).
**Por quê:** o piloto começa sem LLM e sem custo; a regra "nada chega ao aluno sem validação" (visão §4) vale para o DNA; JSON mode + validação própria dá o mesmo resultado com um risco a menos. Fonte: python-genai `GenerateContentConfig.response_mime_type` (https://googleapis.github.io/python-genai/), ADK `LlmAgent` (https://adk.dev/agents/llm-agents/).

## ADR-0033 — Gate de publicação da questão original, sem validador; `questao` é pool global · 2026-09-18 · aceita (fatia V3)
**Decisão:** a questão **original** da Cebraspe é publicável (`publicavel = True`) quando passa em `dominio.questao.decidir_publicacao` (premissa F do plano V3): gabarito **definitivo** (não anulado, não sem entrada), `origem` com os 8 campos (`banca`, `orgao`, `cargo`, `ano`, `numero_item`, `tipo_caderno`, `url_prova`, `documento_id`) todos preenchidos a partir do que o coletor já gravou (nunca digitado à mão), `topico_slug` pertencente ao vocabulário do edital e `topico_confianca ≠ "baixa"`. Item que falha qualquer condição fica na base com `publicavel = False` e `motivo_nao_publicavel` — nunca é descartado, só não entra na fila da aluna. O **validador** da fatia 5 (`gerador-questao-banca` + validação de fidelidade) continua **obrigatório só para questões inéditas**: a regra 11 do CLAUDE.md ("nada gerado chega ao aluno sem validação") fala do que é *gerado* — questão original não é gerada, é reproduzida da prova real da banca; o que ela precisa não é validação de conteúdo, é **procedência**, e é exatamente isso que o gate cobra. Registrado também (Ruling 11/28 do ledger da execução): `questao` é **pool de conteúdo global**, compartilhado por qualquer edital/tenant que reaproveite o mesmo `topico` — é prova pública, não dado de aluno, então não faz sentido segregar por tenant. `edital_id` (em `topico_edital`, na contagem por tópico e no verticalizado) restringe **quais tópicos** aparecem e são contados para aquele edital, **não** a origem das questões nem cria uma cópia por tenant. Isto está escrito aqui para que ninguém "console" esse comportamento depois achando que é vazamento entre tenants — é o desenho pretendido.
**Alternativas:** exigir o validador da fatia 5 também para questões originais (redundante — a banca já é a fonte de fidelidade; o validador testa se o *gerador* não alucinou, e aqui não há gerador); publicar sem gate algum, confiando só na segmentação e no gabarito (deixaria passar item anulado ou sem tópico correto — R-07/R-20 de `RISCOS.md`); `questao` particionada por `tenant_id`/`edital_id` (duplicaria a mesma prova pública a cada edital que a reaproveitasse, sem ganho de isolamento — nenhum dado de aluno mora em `questao`).
**Por quê:** a base tem de crescer por tópico de vocabulário, não por edital — dois alunos com editais diferentes que caem no mesmo tópico (`dir-adm-04-licitacoes-contratos`, por exemplo) devem enxergar a mesma questão, com o mesmo `hash_dedup` evitando duplicata; separar por tenant contrariaria a própria função de dedup do passo 11 e infligiria o mesmo trabalho de curadoria N vezes. O gate em si é o que a skill `ingestao-de-provas` e o plano V3 (premissa F) já mandavam fazer; esta ADR só torna a regra e a arquitetura auditáveis fora do código.

## ADR-0034 — Dependências da V3: `httpx2` em runtime, `pyyaml`/`types-pyyaml` em dev · 2026-09-18 · aceita
**Decisão:** `httpx2` (>=2.13.0, **BSD-3-Clause**, conferido via metadados do pacote instalado em 18/09/2026) sai do grupo `dev` e entra em `dependencies` — deixa de ser só substituto do `httpx` no `TestClient` (ADR-0031) e passa a ser o **cliente HTTP de runtime** do coletor da Cebraspe (`motor/fontes/cebraspe.py`, `criar_fonte_cebraspe`), com a mesma API do `httpx` (`Client(headers=…, timeout=…, follow_redirects=True)`). `pyyaml` (**MIT**) e `types-pyyaml` (**Apache-2.0**), ambos conferidos via metadados do pacote instalado, entram só no grupo `dev`: o **único** consumidor do YAML é o teste `test_fonte_cebraspe_ficha.py`, que carrega `knowledge/fontes.yaml` para conferir a ficha da fonte (skill `monitor-de-fontes`) — o runtime da aplicação nunca lê YAML; as URLs que a ficha documenta vivem como constantes Python no próprio módulo (`URL_LISTA`, `URL_DETALHE`, `URL_ARQUIVO`), e é isso que roda em produção.
**Alternativas:** manter `httpx2` só em dev e usar `httpx` cru no coletor (duas bibliotecas HTTP no projeto, sem motivo); ler `fontes.yaml` em runtime para as URLs (acoplaria o coletor a um arquivo de configuração solto, quando as URLs já são fixas por fonte e o teste garante que não divergem da ficha).
**Por quê:** regra 8 do CLAUDE.md (reutilizar antes de criar) — `httpx2` já era dependência do projeto, só mudou de grupo; nenhuma licença nova incompatível com SaaS fechado entra (BSD-3-Clause, MIT e Apache-2.0 são todas permissivas). Convenção de "nada de I/O em import" e "nenhuma URL fora da ficha" continuam cumpridas: o teste `test_urls_do_codigo_estao_na_ficha` (passo 4) é quem liga runtime e ficha.

## ADR-0035 — Política de coleta da Cebraspe · 2026-09-18 · aceita (fatia V3)
**Decisão:** o coletor (`motor/fontes/cebraspe.py`) segue a política registrada em `knowledge/fontes.yaml`: **User-Agent identificado** em toda requisição (`AprovaOS-coletor/0.1 (+contato: vlfcandido@gmail.com)`, ADR-0030 — o contato é o e-mail do dono até haver domínio); **frequência de 24 h** (uma rodada de coleta por dia, nunca em loop); **sem login** (a API de eventos encerrados é pública, sem autenticação); **PDFs de prova e gabarito versionados no repositório** (`knowledge/provas/<eventoURL>/<nomeArquivo>`, decisão do dono em 18/09/2026) para a suíte de testes e a reprodutibilidade da segmentação não dependerem da Cebraspe estar de pé. O achado que obrigou o desenho da identidade de item (premissa B do plano): **`idEvento` vem `0` nos 424 concursos encerrados** medidos em 18/09/2026 (campo da própria API, inutilizável como chave), então a identidade do item passou a ser **`{eventoURL}/{nomeArquivo}`** — `eventoURL` sozinho quase serve (423 valores distintos em 424 registros; só `INSS_22` está duplicado no snapshot da listagem) mas não é único por si, e `nomeArquivo` (hash do CDN) é único dentro de cada evento. A skill `monitor-de-fontes` exige identidade de item nunca derivada de hash de título ou de posição na lista — `{eventoURL}/{nomeArquivo}` cumpre isso mesmo com o `idEvento` inútil.
**Alternativas:** usar `idEvento` como identidade (inviável — sempre `0`); usar só `eventoURL` como identidade de arquivo (colidiria arquivos diferentes do mesmo evento); coletar sem User-Agent identificado (contraria a convenção da skill e dificulta a Cebraspe entrar em contato se algo der errado); não versionar os PDFs (a suíte dependeria de rede, contrariando premissa K — testes offline no CI).
**Por quê:** a API não documenta publicamente o significado de `idEvento`; a medição direta nos snapshots (`knowledge/fixtures/fontes/cebraspe/`) é a única fonte confiável. Política de coleta identificada e de baixa frequência é a mesma linha de R-02 (`RISCOS.md`, mitigação para a FGV) aplicada à Cebraspe mesmo sem termos restritivos localizados (P-11): identificação e frequência baixa custam pouco e reduzem o risco de a fonte interpretar a coleta como abuso.
**Adendo 18/09/2026 (fechamento da V3):** a Cebraspe é, para o piloto, uma **fonte de conteúdo** (as matérias de Direito se sobrepõem ao que o edital dela provavelmente cobra, ADR-0027) e a base técnica que valida o cano inteiro (coletor → curador → gate → tela); ela **não é necessariamente** a fonte do **formato** de prova que a Linda vai encontrar — a banca real do concurso dela continua **desconhecida** (P-17 segue aberta). *Correção do mesmo dia:* um rascunho deste adendo chegou a afirmar que a banca dela era a "Fundação de Apoio à Unioeste (COGEPS)" com prova A–E, lendo `knowledge/fixtures/editais/edital-assessor-gabinete.pdf` como se fosse o edital real — esse PDF é **fictício** (fixture de teste das skills da Fase 4 e das fatias V2/V3, gerado a partir de um `.md` cujo cabeçalho diz isso explicitamente); a afirmação foi removida. A V3b prioriza múltipla escolha A–E por ser o formato dominante no mercado de concursos (decisão do dono, P-30), não porque se conheça a banca real dela.

## ADR-0036 — Extração de fato do edital exige prova de conceito na cláusula; sem ela, lacuna declarada · 2026-09-18 · aceita (fatia V3b)
**Decisão:** toda extração de fato do edital por regex (`aprovaos/dominio/edital.py`) exige, além do termo-âncora (o gatilho que hoje já se escolhe com cuidado: "nota zero", "anula", "banca organizadora"...), um **segundo termo característico do conceito** que o campo promete, aparecendo **perto da âncora e na mesma frase** (sem cruzar ponto final — nunca vale o parágrafo inteiro, e nunca o documento inteiro). Sem essa prova de proximidade, o campo sai **`desconhecido` com a lacuna declarada** — nunca o valor mais plausível. Esta regra já foi aplicada, com regex própria em cada caso, em três correções desta fatia: `_BANCA_EXECUTADO`/`_BANCA_ORGANIZADORA` (o nome capturado tem de começar maiúsculo — nome próprio — ou vir de um rótulo explícito com dois-pontos), `_ANULA` (a cláusula tem de ligar "errad[ao]" a "anula/desconta/desconto/subtrai") e `_NOTA_ZERO` (tem de aparecer perto de "disciplina(s)/matéria(s)/conhecimentos").
**A evidência que motivou — quatro achados, contra os dois editais reais da fatia (AOCP/TJ-PR e FCC/TRT9), medidos, não supostos:**
- `cabecalho.banca` casava com uma cláusula de **recurso**, não de identificação da banca — AOCP §17.9: *"Se da análise do recurso pela banca organizadora resultar anulação de questão(ões) ou alteração de gabarito da Prova Objetiva."* O parser devolvia essa frase inteira como se fosse o nome da banca.
- `regra_correcao.anula_por_erro` casava com **anulação de inscrição por fraude** — AOCP §5.10.1: *"Declaração falsa ou inexata dos dados constantes no Formulário de Inscrição [...] determinará o cancelamento da inscrição e anulação de todos os atos dela decorrentes [...]"* — e com **anulação de nomeação** — FCC §6.5.1: *"Constatada a falsidade da declaração [...] ficará sujeito à anulação de sua nomeação ao serviço público [...]"* Nenhuma das duas fala de desconto por questão errada; o parser devolvia `True` para os dois.
- `regra_correcao.minimo_por_materia` casava com **nota zero da prova discursiva**, não da objetiva — FCC §10.6: *"Será atribuída nota ZERO à Prova Discursiva-Redação que: a) fugir à modalidade de texto solicitada e/ou ao tema proposto [...]"* O parser devolvia `"nota zero elimina"` como se o edital eliminasse por zerar uma disciplina da prova objetiva.
- `cabecalho.orgao` devolvia **a primeira linha de um timbre de três**, não a específica — a FCC tem, em caixa alta, "PODER JUDICIÁRIO" / "JUSTIÇA DO TRABALHO" / "TRIBUNAL REGIONAL DO TRABALHO DA 9ª REGIÃO", nessa ordem; o parser pegava a primeira, tecnicamente verdadeira e inutilizável para identificar o concurso.
**Por que ninguém viu antes:** o fixture fictício da Fase 4 foi escrito para o parser — um modelo escreveu o edital que o outro sabia ler. Nenhum dos quatro defeitos aparece contra ele; os quatro aparecem no primeiro contato com edital real. Este é o aprendizado mais caro da fatia.
**Assinatura proposta** para um utilitário compartilhado (não implementado por esta ADR — ver "o que esta ADR não decide"):
```python
def clausula_com_conceito(
    texto: str,
    ancora: re.Pattern[str],
    termos_do_conceito: Sequence[re.Pattern[str]],
    *,
    janela: int = 60,
) -> re.Match[str] | None:
    """Acha a âncora só quando ela está perto de um termo que prova que a cláusula fala do
    conceito, e não apenas contém a palavra-gatilho. Devolve o Match ou None — o chamador decide
    então declarar `desconhecido` com lacuna, nunca inventar um valor."""
```
Ressalva honesta: a `janela` de 40–60 caracteres usada nas três correções saiu de tentativa e erro contra **dois** editais reais, não de validação estatística com muitos — refiná-la (ou provar que 60 é robusto) exige mais editais reais antes de virar constante única do utilitário.
**O que esta ADR não decide:** não cria `clausula_com_conceito` agora — as três correções já feitas continuam com a regex restrita de cada uma, escrita à mão. A unificação num utilitário só entra quando houver um terceiro ou quarto edital real para validar o limiar de `janela` contra mais dados; unificar cedo demais, com dois exemplos, arriscaria fixar um número que não generaliza.
**Alternativas:** aceitar o primeiro parágrafo que contém o termo-âncora, como antes (é exatamente o defeito que gerou os quatro achados); inferir por confiança numérica (0,6, 0,8...) em vez de proximidade textual (a skill `monitor-de-fontes` já veta "confiança inventada por palavra-chave" pelo mesmo motivo — não há medição que sustente o número); tratar cada achado como bug isolado sem registrar a regra geral (é o que este ADR existe para evitar — a próxima extração de fato nasceria com o mesmo defeito).
**Por quê:** o princípio "nada gerado chega ao aluno sem validação; toda afirmação jurídica tem fonte" (CLAUDE.md regra 11) vale também para fato extraído do próprio edital, não só para conteúdo gerado por LLM — um `"Banca: <trecho de cláusula de recurso>"` na tela é tão enganoso quanto uma afirmação jurídica sem fonte. `desconhecido` com lacuna é o estado que o produto já sabe mostrar (a mesma convenção da skill `dna-do-concurso`); um dado errado com cara de fato não tem lugar equivalente para ser corrigido depois — ele parece certo.

## ADR-0037 — User-Agent do coletor: híbrido `Mozilla/5.0 (compatible; ...)` onde o token é exigido, identificado puro onde já é aceito · 2026-09-19 · aceita
**Decisão:** o coletor jurídico usa `Mozilla/5.0 (compatible; AprovaOS-coletor/0.1; +contato:
vlfcandido@gmail.com)` como User-Agent para fontes que exigem o token `Mozilla/5.0` na borda
(medido: Planalto e STF, ver abaixo). O User-Agent identificado puro
(`AprovaOS-coletor/0.1 (+contato: vlfcandido@gmail.com)`, ADR-0030/ADR-0035) continua valendo
onde já é aceito sem esse token — hoje, a Cebraspe (ficha em `knowledge/fontes.yaml`). Não é uma
substituição: são dois formatos do mesmo UA identificado, escolhidos por fonte conforme o que ela
exige — a ficha de cada fonte em `knowledge/fontes.yaml` registra qual dos dois usar.

**O que isso obriga no código:** o cliente HTTP do coletor tem de **expor cabeçalhos
explicitamente** (`httpx`/`httpx2` com `headers={"User-Agent": ...}` configurável por fonte, no
padrão já usado pela Cebraspe — ADR-0034). Achado que torna isso requisito de desenho, não
detalhe: uma ferramenta de fetch genérica sem esse controle (o `WebFetch` usado durante a própria
medição desta ADR) continua falhando contra o Planalto (`ECONNRESET`) mesmo depois de a causa ser
conhecida e corrigida para `curl` — porque ela não permite escolher o UA que envia. Um coletor de
produção construído em cima de uma ferramenta assim herdaria a mesma cegueira sem nenhum aviso
(o sintoma imita instabilidade de rede, não um 403 claro).

**Por quê:** não mentimos sobre quem somos para conseguir acesso — o formato híbrido
`Mozilla/5.0 (compatible; AprovaOS-coletor/0.1; +contato: ...)` é o mesmo padrão que bots
legítimos usam para se identificar dentro do formato que os servidores aceitam (o próprio
Googlebot se anuncia como `Mozilla/5.0 (compatible; Googlebot/2.1;
+http://www.google.com/bot.html)`). Medido em 19/09/2026 (`.superpowers/sdd/V3b-multipla-escolha/
fontes-juridicas-report.md`, evidência em `knowledge/fixtures/juridico/`): o UA híbrido passa no
Planalto (200, 1.839.482 bytes na CF — idêntico byte a byte ao UA de navegador puro) e no índice
do STF (200, 139.841 bytes — idem); o identificado puro, sem o prefixo `Mozilla/5.0`, é recusado
pelo Planalto (`000`, 0 bytes) apesar de ser a mesma informação de contato.

**Fontes e rotas, estado medido em 19/09/2026** (corrige o diagnóstico presente na P-15 desde
17/09/2026 — ver `docs/PENDENCIAS.md`):
- **Planalto (Rota A da skill `deep-research-topico`) volta a ser a fonte primária de normas** —
  não estava fora do ar; sem o token `Mozilla/5.0` no UA, o TLS fecha handshake normalmente mas o
  corpo da resposta nunca chega, o que **imita** uma falha de rede sem ser uma. É também a fonte
  mais rica das quatro medidas: mostra o texto revogado **riscado** (`<strike>`) ao lado do texto
  vigente, com link direto para a Emenda/Lei que alterou o dispositivo — dá `redacao_de` e
  "redação anterior × atual" numa fonte só.
- **Câmara `legin` (Rota B) é a alternativa real**, inclusive dentro da própria Câmara: o `.html`
  "normaatualizada" de uma norma específica pode cair (a Lei 14.133/2021 deu **504 Gateway
  Timeout** em 3 tentativas seguidas) e o `.pdf`/`.doc` da mesma URL-base suprir — o extrator do
  coletor precisa tratar HTML **e** PDF/DOC, não só HTML.
- **STF (súmulas e súmulas vinculantes)** exige o UA de navegador (ou o híbrido, medido acima) e
  uma resolução em **duas etapas**: o parâmetro `sumula=<id>` da URL é um ID interno, não o número
  da súmula — só descobrível abrindo o índice (`base=30` para comuns, `base=26` para vinculantes)
  e casando o texto do link com o `href`. Não dá para fixar um mapa número→id sem revalidar,
  porque cancelamentos e súmulas novas mudam a lista.
- **STJ (súmulas)** é a mais simples: um único PDF (`scon.stj.jus.br/.../VerbetesSTJ.pdf`) cobre
  as ~676 súmulas, texto limpo, sem exigência de UA especial.
- **LexML (Rota C) fica como lacuna declarada, não corrigida por esta ADR**: retestado com UA de
  navegador, continua devolvendo a mesma página "Verificação de segurança — Senado Federal" (só o
  campo `ts` interno muda) — não é filtro de UA, é desafio de JavaScript de verdade. Precisaria de
  navegador real (Playwright/Chrome) para passar; fica pendente de o dono avaliar se o custo vale,
  já que Planalto+Câmara cobrem normas e STF+STJ cobrem súmulas sem essa rota.

**Nota sobre a skill `monitor-de-fontes`:** esta ADR não revoga a exigência de UA identificado —
ela define **qual formato** cumpre essa exigência e passa nos servidores testados. A ficha de
cada fonte em `knowledge/fontes.yaml` deve registrar qual dos dois formatos (identificado puro ou
híbrido `Mozilla/5.0`) ela exige, medido caso a caso — não presumido.

**Alternativas:** usar só o UA identificado puro em toda fonte (falha no Planalto e,
provavelmente, em qualquer fonte com o mesmo filtro de borda); usar só um UA de navegador comum
sem identificação (`Mozilla/5.0 (Macintosh...) Chrome/120.0...`, sem menção ao AprovaOS) — passa
nos mesmos testes, mas contraria a exigência de identificação da skill `monitor-de-fontes` e
tira da fonte a chance de nos contatar se algo der errado; construir o coletor em cima de uma
ferramenta de fetch sem controle de header (descartada pelo achado acima — falha sem aviso claro).
**Por quê (resumo):** o formato híbrido é o único, entre os testados, que satisfaz as duas
exigências ao mesmo tempo — passar no filtro de borda **e** se identificar de verdade — sem
recorrer a navegador automatizado para fontes que não exigem desafio de JavaScript.

## ADR-0038 — Parser do conteúdo programático lê Título Caso e itens sem numeração, com a mesma régua da ADR-0036 · 2026-09-19 · aceita

**Decisão:** `dominio/edital.extrair_conteudo_programatico` passa a reconhecer três formas de
cabeçalho de matéria (CAIXA ALTA com dois-pontos — já existia; CAIXA ALTA seguida direto de `1.`
sem dois-pontos — já existia; e agora **Título Caso** com dois-pontos, achado real na AOCP:
`"Língua Portuguesa: 1. ..."`) e duas formas de item (numerado `1.`/`1 ` — já existia, agora
também sem ponto obrigatório; e, quando nenhuma numeração é encontrada, **por frase** — achado
real na FCC: itens separados só por ponto final, sem número nenhum). A prova de que uma linha em
Título Caso é cabeçalho de matéria — não uma frase qualquer terminada em dois-pontos, como
`"Observação:"` no mesmo edital da FCC — é a mesma da ADR-0036: um segundo sinal perto da âncora,
aqui um item numerado abrindo logo depois dos dois-pontos. Sem esse segundo sinal, a linha não
vira cabeçalho.

**Dois achados adicionais, medidos, corrigidos na mesma fatia por serem pré-requisito para as
contagens não saírem erradas:**
- **Cabeçalho com hífen no nome não casava** — `"MATEMÁTICA E RACIOCÍNIO-LÓGICO:"` (FCC) tem um
  hífen dentro do nome da matéria; a classe de caracteres do cabeçalho caixa-alta não incluía
  hífen, e o bloco inteiro (a matéria toda) virava continuação de `LÍNGUA PORTUGUESA:`, a matéria
  anterior. Corrigido incluindo hífen só na classe do cabeçalho (nunca na de slug/vocabulário).
- **Linha de seção/cargo sem ser matéria vazava para dentro da matéria anterior** — `"CONHECIMENTOS
  ESPECÍFICOS"` solto (sem dois-pontos) e o código do cargo entre uma seção e outra (`"A01 –
  Analista Judiciário – Área JUDICIÁRIA - sem especialidade"`, achado real na FCC, repetido para
  cada um dos 4 cargos do edital) não casavam com cabeçalho nenhum e viravam continuação do bloco
  aberto — sem corrigir, cada matéria ganharia um "tópico" fabricado com o código do próximo
  cargo. Corrigido com um marcador de seção reconhecido e descartado (nem abre bloco, nem vira
  continuação).

**Resultado medido (18–19/09/2026, os dois editais reais desta fatia):** AOCP/TJ-PR passa de
**0 matérias / 0 tópicos** para **9 matérias / 99 tópicos**; FCC/TRT9 passa de **24 matérias / 0
tópicos** para **25 matérias / 580 tópicos** (a matéria a mais é justamente
`MATEMÁTICA E RACIOCÍNIO-LÓGICO`, separada de `LÍNGUA PORTUGUESA` pela correção do hífen). O
fixture fictício da Fase 4 continua em **7 matérias / 36 tópicos**, sem regressão. Amostra de
qualidade (5 primeiros tópicos de cada matéria, os dois editais reais) conferida à mão — sem
tópico picotado; itens numerados sem ponto (`"5 Organização do Estado."`) e frases da FCC
(`"Domínio da ortografia oficial."`) saem inteiros.

**Degradações honestas, não corrigidas — registradas em `docs/PENDENCIAS.md` em vez de
remendadas** (mesmo princípio da ADR-0036: não inventar heurística nova sem prova de um terceiro
edital): AOCP perde o item 10 (`"Bens Públicos"`) de Direito Administrativo, fundido no item 9,
porque o PDF cola o número do item seguinte no ponto final do anterior sem espaço
(`"[...] agentes públicos.10 Bens Públicos"`) — a mesma forma textual de um subitem decimal
genuíno (`"4.5"` dentro de item sem ponto, que a guarda `(?<!\.)` existe para não confundir com o
item de topo `"5"`), sem contexto para diferenciar os dois casos com regex (P-42). Número de
página solto dentro do texto de alguns tópicos da FCC (P-43). Peso por matéria da prova objetiva
continua `desconhecido` nos dois — a AOCP tem uma tabela real (TABELA 11.1) que dá para ler num
parser de tabela dedicado; a FCC só dá granularidade "Conhecimentos Gerais/Específicos", nem um
parser perfeito devolveria peso por matéria dela com este edital (atualização da P-39).

**Alternativas:** aceitar qualquer linha terminada em dois-pontos como cabeçalho de matéria em
Título Caso, sem a prova do item seguinte (rejeitada — é exatamente o defeito que a ADR-0036
existe para evitar, e `"Observação:"` no mesmo edital prova o risco); tratar itens sem numeração
como erro fatal, exigindo edital manualmente anotado (rejeitada — inutilizaria o produto para
qualquer edital de banca que não numere, e a FCC é uma banca do Top 5 do mercado); tentar também
corrigir a tabela de distribuição de questões nesta mesma fatia (rejeitada — é parser de tabela,
escopo bem maior que os dois achados pedidos, registrado como P-39/P-42/P-43 para fatia própria).

**Por quê:** a promessa central do produto (a aluna sobe o edital dela e o sistema entende) só
está provada contra um fixture escrito por um modelo para o próprio parser ler; os dois achados
corrigidos aqui (mais os dois adicionais, hífen e marcador de seção) são o que faltava para ela
valer contra edital de banca real, sem inventar tópico nem matéria — o mesmo padrão de disciplina
da ADR-0036, agora aplicado à extração de matérias/tópicos, não só aos fatos avulsos do edital.

## ADR-0039 — Fatia 4 (dossiês de tópico): peso medido, não declarado; súmula não vira `dispositivo_legal` ainda · 2026-09-19 · aceita (fatia 4)
**Decisão 1 — "tópicos de maior peso" é medido, nunca estimado.** A spec pede os tópicos "de
maior peso do edital dela" (PRD §6, linha 4). O parser determinístico do conteúdo programático
não produz peso por tópico (só peso uniforme por matéria — lacuna já registrada na V2, P-39, e
confirmada nos dois editais reais mapeados na V3b). Calcular peso por tópico como "peso da
matéria ÷ nº de tópicos dela" seria uma estimativa vestida de fato — o que a skill
`dna-do-concurso` já proíbe para o mesmo problema (`pct_uniforme` é lacuna declarada, nunca peso
real). O critério adotado é **nº de questões publicáveis por tópico na base real** (curadoria da
V3), descendente — `motor/dossie.py::topicos_de_maior_peso`. É o único número que a base tem
hoje que não é inventado, ainda que meça "o que a Cebraspe cobrou nas provas já curadas", não
necessariamente "o que a banca real da aluna vai cobrar" (mesma ressalva já registrada na V3 sobre
o edital fictício de Cascavel/Unioeste, ADR-0027/P-17).
**Alternativas:** peso uniforme por matéria ÷ tópicos (rejeitada — estimativa, não fato);
esperar o parser de tabela de distribuição de pontos por tópico (rejeitada — bloquearia esta
fatia inteira por um parser de escopo maior, P-39/P-42/P-43, sem previsão); perguntar ao dono um
número arbitrário de tópicos "importantes" (rejeitada — não escala, e o produto promete decisão
por dado, não por achismo).

**Decisão 2 — súmula entra no dossiê, mas não vira `dispositivo_legal` nesta fatia.** A skill
`deep-research-topico` pede jurisprudência (súmula com número, texto integral, URL) no dossiê.
A tabela `dispositivo_legal` (migração 0005) é, pelo próprio contrato, "um dispositivo de
**norma**" — forçar uma súmula nela (sem artigo/inciso reais) distorceria uma tabela que
`motor.ancorar`/`motor.ligar_por_topico` já usam para outra coisa, e essas duas rotinas não têm,
nesta fatia, tempo de revisão para uma mudança de contrato tão espalhada. `FonteDossie` ganhou
`tipo: "norma"|"sumula"`; `dados.repositorio_dossie.salvar_dossie` só cria `dispositivo_legal`
para `tipo="norma"`. A súmula fica gravada (auditável, com número/texto/URL) no JSON de
`dossie_topico.fontes`, mas fora do alcance de `motor.ligar_por_topico` até uma fatia jurídica
dedicada decidir como estender o contrato de `dispositivo_legal`/`Citacao` para jurisprudência.
**Alternativas:** gravar a súmula como se fosse um "artigo" de uma "norma" fictícia em
`dispositivo_legal` (rejeitada — mentira estrutural na tabela, o `artigo` de uma súmula não
existe); adiar toda jurisprudência para depois (rejeitada — a spec e a skill pedem explicitamente
súmula no dossiê desta fatia); criar uma tabela nova `sumula`/`dispositivo_jurisprudencial`
agora (rejeitada — dimensionar o contrato certo exige saber primeiro como `Citacao`/justificativa
vão consumir julgado além de súmula; prematuro com uma fatia de evidência só).
**Por quê:** as duas decisões seguem a mesma régua — "lacuna declarada vale mais que fonte
inventada" (skill) e "não extrapole o plano" (CLAUDE.md regra 9): peso medido é o que a base
prova hoje; súmula fora de `dispositivo_legal` é o que o contrato atual suporta sem distorção.

## ADR-0040 — Fatia 6 (trilha e aulas em texto): validador mecânico da aula, mnemônico na mesma chamada, trilha por peso medido · 2026-09-19 · aceita (fatia 6)
**Decisão 1 — `aula` ganha `como_a_banca_cobra`, `lacunas_declaradas` e `mnemonico` além do
mínimo de `docs/04-modelo-de-dados.md` §3.** A skill `gerador-de-aula` pede os dois primeiros
campos e a linha 6 do PRD pede mnemônico; nenhum dos três está na tabela `aula` documentada na
Fase 3. Mesmo padrão já aceito para `dna_concurso` (ADR-0032) e `questao` (ADR-0033): coluna JSON
além do que o modelo de dados previa, decisão registrada aqui em vez de reescrever o documento da
Fase 3 por uma extensão aditiva (nenhuma coluna do mínimo original muda de sentido).
**Alternativas:** reescrever `04-modelo-de-dados.md` §3 (rejeitada — falso senso de que a Fase 3
previu isso; o histórico de decisão se perderia); guardar os três campos dentro de `citacoes`/
`relacionados` (rejeitada — são conceitos distintos, misturar dificultaria consultar/validar cada
um).

**Decisão 2 — o mnemônico nasce na mesma chamada do `gerador-de-aula`, não numa chamada própria.**
A linha 6 do PRD pede mnemônico "gerado e validado", mas o free tier tem poucas requisições/dia
por modelo (achado do passo 12b/12c da V3) e há 4 dossiês para gerar aula. Pedir o mnemônico como
campo opcional do mesmo JSON de saída (`MnemonicoAula`, validado pela mesma regra de trecho
literal das citações) custa zero chamadas extras. **Alternativa rejeitada:** agente
`gerador-de-mnemonico` dedicado (skill separada) — dobraria o custo de cota desta fatia sem
ganho de qualidade evidente; se o piloto pedir mnemônico mais rico que o que cabe numa aula, vira
fatia própria depois.

**Decisão 3 — trilha ordena por peso medido (questões publicáveis) + visto/errado, nunca por
"dificuldade" estimada.** Mesma régua da ADR-0039 (peso medido, não declarado — o edital só tem
peso uniforme por matéria, P-39): `dominio/trilha.py::montar_trilha` usa dois números que a base
já tem — `questoes_publicaveis` (peso) e `acertos/total` do histórico real — nunca um índice de
dificuldade inventado. Critério escrito e testado (`docs/fatias/6-trilha-e-aulas.md` §7): não
visto/fraco (acerto < 70 % ou menos de 3 respostas) antes de dominado; dentro do mesmo grupo,
maior peso primeiro.

**Decisão 4 — grifos (`Anotacao`) ficam fora desta fatia.** O modelo de dados já nomeia a tabela
(`docs/04-modelo-de-dados.md` §2) mas não existe ORM, migração, nem lógica de reancoragem por
`texto_ancora` quando o conteúdo muda — trabalho do tamanho de uma fatia própria, não um apêndice
desta. Registrado em `docs/PENDENCIAS.md` (P-50) em vez de entregar uma versão sem reancoragem
(que "sobrevive à regeneração do dossiê ou avisa que o trecho mudou" é o próprio critério de
aceite da F4.6 no PRD — sem isso, não é a feature, é outra coisa com o mesmo nome).

**Por quê:** todas seguem a mesma régua da casa — número real ou lacuna declarada nunca estimativa
(decisões 1 e 3); custo de cota é recurso do produto, não infra a ignorar (decisão 2); entregar
menos e honesto é melhor que uma versão capenga com o nome certo (decisão 4).

## ADR-0041 — Dossiê e aula chegam ao tópico do edital real por `topico_relacao` (equivalência curada), não por migração de `topico_id`; fecha a P-52 · 2026-09-19 · aceita (correção estrutural, fora de fatia)

**O problema, medido no `dev.db`:** os 4 dossiês e as 2 aulas da fatia 4/6 foram gravados sob o
vocabulário do edital da Câmara Municipal de Cascavel/Unioeste (`topico.slug` em `dir-*` —
`dir-adm-06-improbidade-administrativa`, `dir-con-02-direitos-garantias`,
`dir-pro-civ-03-atos-processuais`, `dir-pro-civ-05-recursos-apelacao`), enquanto as 137 questões
publicáveis da V3/V3b reclassificadas em 19/09/2026 (P-31) estão em `topico_id` do edital do
TJ-PR/Instituto AOCP (`noc-dir-*`). Nenhum tópico do TJ-PR tinha dossiê ou aula própria; nenhum
tópico de Cascavel tinha questão publicável. Resultado: `GET /topico/{slug}/aula` do TJ-PR sempre
mostrava "ainda não temos aula" e `motor.ligar_por_topico` (a âncora grosseira que sustenta a
justificativa de uma questão) não ligava nenhuma questão a nenhum dispositivo — 0 tópicos com
dossiê **e** questão sob o mesmo `topico_id`. `topico` é vocabulário **por edital** (o slug nasce
do texto daquele edital); dois editais que cobrem o mesmo assunto sempre vão gerar dois
`Topico.slug` distintos — não é um bug de um parser, é a consequência do próprio desenho, que já
era conhecida e registrada como pendência (P-52, aberta na fatia 6).

**Decisão — usar `topico_relacao` (a tabela que `docs/04-modelo-de-dados.md` §3 já reservava para
isto, "grafo do fio da memória e da propagação") como ponte, nunca implementada até agora.**
`dados.repositorio_topico_relacao.criar_relacao_equivalente` grava uma aresta com o quarto valor
de `origem` que a tabela ganhou nesta ADR, `equivalencia_curada` (os três que o modelo de dados já
prometia — `edital`/`dossie`/`coocorrencia` — continuam sem produtor, essa é a primeira aresta
real da tabela). Toda leitura por tópico *deveria* tentar o `topico_id` direto e, sem achar, cada
equivalente, antes de desistir: `repositorio_dossie.dossie_mais_recente_do_topico`,
`repositorio_aula.aula_publicada_do_topico` e `motor.ligar_por_topico.ligar_por_topico` (esta
última generalizando as questões elegíveis de `Questao.topico_id == dossie.topico_id` para
`topico_id` ∪ equivalentes) — **eram três, uma quarta ficou de fora e a frase original desta ADR
dizia "toda leitura", o que era falso** (achado I2 de uma revisão independente, 19/09/2026):
`api/editais.py::trilha_do_concurso` (`GET /concurso/{id}/trilha`) consultava `Aula` direto por
`topico_id`, sem passar por `topicos_equivalentes` — um tópico sem aula própria mas equivalente a
outro que tem nunca mostrava "Ver aula" na trilha, mesmo com `GET /topico/{slug}/aula` servindo a
mesma aula normalmente. Corrigido na mesma revisão: a trilha passou a usar
`repositorio_aula.aula_publicada_do_topico_com_origem` (a mesma leitura da rota de aula). `motor.aula._dossies_relacionados` (candidatos ao fio da memória (a))
passou a excluir também os equivalentes do tópico da aula — sem isso, uma aula citaria como
"relacionado" o próprio conteúdo de que já é feita, travestido no slug de outro edital. A
curadoria dos pares é manual e versionada em código (`motor/relacionar_topicos.py::RELACOES`,
mesmo padrão de `RECEITAS` em `motor/dossie.py`), com `evidencia` obrigatória e rastreável — nunca
"parecem iguais" (a mesma régua da ADR-0036, aplicada aqui a par de tópicos em vez de cláusula de
edital): dos tópicos com questão publicável, só 4 pares tinham correspondência honesta (citação
literal idêntica nos dois editais — Lei nº 8.429/1992, "Direitos e garantias fundamentais", "atos
processuais"/"prazos", "recursos"); os demais (`noc-dir-con-06-6-organizacao`,
`noc-dir-pro-pen-06-provas-6`, `noc-dir-adm-09-9-agentes`, entre outros) não têm par do lado de
Cascavel e ficam **sem relação**, deliberadamente.

**Alternativas:**
- **(b) Ancorar dossiê/aula num "conceito" canônico novo, com os `topico_id` de cada edital
  apontando para ele.** Rejeitada: exigiria migrar `dossie_topico`/`aula` para uma chave que hoje
  não existe, quebrando o versionamento já testado (`UniqueConstraint(topico_id, versao)`) e
  todo o código que assume `topico_id` como o próprio tópico do edital (verticalizado,
  `topico_edital`, `Citacao`); mais invasivo para um projeto de poucas horas por semana, sem
  ganho sobre a aresta — a tabela para isso já existe e está vazia.
- **(c) Regenerar dossiê e aula sob o `topico_id` de cada edital.** Rejeitada: duplica conteúdo
  caro (dossiê é offline mas manual por receita; aula custa chamada de LLM) para o mesmo texto de
  lei, e ainda deixaria o mesmo problema para o próximo par de editais equivalentes — não corrige
  a causa, só o sintoma desta rodada.
- **Migrar os 4 dossiês/2 aulas existentes para os `topico_id` do TJ-PR (`UPDATE` direto).**
  Rejeitada: perde a informação de que o conteúdo também vale para o edital de Cascavel (ela
  continua sendo aluna dos dois — P-17, banca real dela ainda desconhecida) e contraria a
  instrução explícita desta correção ("não apague nem renomeie tópicos existentes").

**Custo desta decisão:** toda leitura por tópico ganha uma consulta extra condicional (só corre
quando a leitura direta falha) e complexidade de mais um salto (`topicos_equivalentes`); a
curadoria dos pares é manual e não escala sozinha — cada par novo exige alguém (hoje, o modelo)
ler os dois editais e confirmar a citação literal, o mesmo custo que já existe para `RECEITAS`
(dossiê) e para o parser de tópico. `motor/dossie.py`/`motor/aula.py` (geração) ainda **não**
evitam gerar um dossiê/aula duplicado quando um equivalente já existe — só a leitura resolve por
equivalência; deduplicar a geração fica para quando houver um terceiro edital equivalente de
verdade (registrado como próxima pendência, ver `docs/PENDENCIAS.md`).

**Por quê:** a régua de sempre — número real ou lacuna declarada nunca estimativa, aplicada aqui a
relação de tópico ("na dúvida, não relacione", ADR-0036); reaproveitar a tabela que o modelo de
dados já previu é mais barato e menos arriscado que inventar uma estrutura nova para o mesmo
grafo; e conteúdo caro que já existe tem de chegar à aluna antes de qualquer fatia nova (CLAUDE.md
regra 6/9 — poucas horas por semana, automação e MVP pequeno valem mais que ambição).

**Adendo 19/09/2026 (achado I1 da mesma revisão independente): um dos quatro pares não era
equivalência plena.** O par `dir-pro-civ-05-recursos-apelacao <-> noc-dir-pro-civ-07-recursos`
tinha `evidencia` dizendo, com todas as letras, "a cobertura do dossiê é parcial em relação ao
item do TJ-PR" — mas foi gravado com `origem="equivalencia_curada"` e `peso=1` (equivalência
plena) do mesmo jeito, e o docstring de `TopicoRelacao`/o comentário de
`repositorio_topico_relacao.py` chegaram a afirmar "`peso` é sempre 1.000 ... nunca parcial",
contradizendo a própria evidência gravada ao lado. Na tela, a aluna receberia uma aula só de
apelação/agravo/embargos de declaração rotulada como a aula inteira de "Dos recursos" do TJ-PR,
sem nada dizendo que cobre só parte. Corrigido: novo valor de `origem`,
`subconjunto_curado` (peso `0,5` — sinal direcional de cobertura parcial, não uma fração medida;
medir "quanto" exigiria decompor o item do outro edital em partes comparáveis, fora do escopo
desta correção), com `criar_relacao_subconjunto`/`topicos_subconjunto` próprios
(`dados/repositorio_topico_relacao.py`) e migração `0014_topico_relacao_subconjunto` (amplia o
`CHECK` de `origem` e corrige o dado real já gravado no `dev.db`). `dossie_mais_recente_do_topico`
e `aula_publicada_do_topico` passaram a tentar também `topicos_subconjunto` (nesta ordem: direto →
equivalência plena → subconjunto) para o conteúdo continuar sendo servido — e
`aula_publicada_do_topico_com_origem` (nova) devolve de onde a aula veio, para a trilha
(`GET /concurso/{id}/trilha`) avisar "cobre parte deste item" quando a origem é
`subconjunto_curado`. `motor/relacionar_topicos.py::RELACOES` (equivalência plena) e
`RELACOES_PARCIAIS` (cobertura parcial, novo) separam a curadoria dos dois tipos de par.

## ADR-0042 — Todo número de confiança exibido nasce do intervalo de Wilson; o `±` do diagnóstico é cobertura e passa a se chamar assim · 2026-09-19 · aceita (Ruling 35 da fatia 10)
**Decisão:** `dominio/estatistica.py` (`intervalo_wilson`, `Proporcao`, `sobrepoe`) passa a ser a única origem de número de proficiência exibido — painel, padrões de erro, previsão de nota e resumo semanal. O proxy `margem = 50/(1+peso)` da fatia 7 **continua** governando o critério de parada do diagnóstico, mas deixa de ser exibido como `±`: na tela ele é chamado de **cobertura**.
**Alternativas:** (a) trocar também o critério de parada do diagnóstico pelo intervalo estatístico — mais correto e mais caro (fechar um intervalo de verdade exige mais itens do que fechar cobertura, e o diagnóstico ficaria mais longo); (b) manter o `±` como está — descartada, ver abaixo.
**Por quê:** a visão §4 e a regra 11 do `CLAUDE.md` exigem "previsão sempre com intervalo", e `66,7 % ± 7,14` **não é** um intervalo: para 2 acertos em 3 itens, o intervalo de Wilson de 95 % vai de **20,8 % a 93,9 %**. O número antigo media *quanto já perguntamos*, não a precisão da estimativa — e era lido pela aluna como se medisse a segunda coisa. Wilson é fórmula fechada (sem dependência nova) e é o intervalo recomendado para amostra pequena, ao contrário do de Wald, que degenera em `[0, 0]` quando não há acerto nenhum (Wilson, 1927, JASA 22(158); Brown, Cai & DasGupta, 2001, Statistical Science 16(2)). Um número que parece confiança e não é entra na mesma família de defeito da ADR-0036: **dado errado com cara de certo**.

## ADR-0043 — O que a aluna olha todo dia não depende de LLM · 2026-09-19 · aceita (Ruling 36 da fatia 10)
**Decisão:** plano do dia (fatia 8), painel inteiro — curva, padrões, previsão, alerta — e o resumo cumulativo semanal (F4.4c) são **determinísticos**. LLM fica para o que só ele faz: entender edital, classificar tópico, escrever aula, gerar e validar questão.
**Alternativas:** usar LLM para "escrever melhor" o resumo semanal (o PRD §5 orçou ≈ R$ 0,80/mês para isso) — adiada; não muda nenhum número, só a prosa.
**Por quê:** o free tier dá **20 requisições/dia por modelo** e o teto de gasto é R$ 3/dia (ADR-0018). Uma tela diária que dependa de LLM fica fora do ar quando a cota acaba — e a cota acaba justamente nos dias de mais uso. A regra que sai daí: **degradar é aceitável em conteúdo, não em navegação**. O custo é prosa mais seca; o ganho é um produto que não some.

## ADR-0044 — Integração externa entra pronta e desligada por configuração · 2026-09-19 · aceita (Rulings 42 e 46)
**Decisão:** toda integração que dependa de credencial do dono (Google OAuth, Mercado Pago/billing, e o que vier) é implementada **inteira**, com testes contra um duplo que implementa o mesmo `Protocol`, e fica **inerte** enquanto as variáveis de ambiente correspondentes forem `None`: a rota responde 404, o botão não é renderizado, o produto roda exatamente como hoje.
**Alternativas:** (a) não implementar até a credencial existir — deixa a fatia pela metade e o trabalho para um momento em que ninguém lembra do contexto; (b) implementar com credencial de sandbox comprometida no repositório — inaceitável.
**Por quê:** o dono tem poucas horas por semana e é o único que pode criar conta em provedor externo. Separar "o código está pronto" de "a conta existe" transforma uma dependência de agenda dele numa variável de ambiente. O risco a vigiar é o oposto: código que nunca roda em produção apodrece — por isso a exigência de teste com duplo é parte da decisão, não um detalhe.

## ADR-0045 — Aderência de questão inédita medida sem embedding, com o proxy declarado · 2026-09-19 · aceita (Ruling 43 da fatia 5)
**Decisão:** o validador de inédita mede aderência ao estilo da banca por **regras de forma** (comprimento, uma afirmação só em C/E, alternativas homogêneas em A–E, ausência de "sempre/nunca" gratuitos) mais **similaridade léxica determinística** (cosseno de TF‑IDF, stdlib) contra os originais do mesmo tópico/banca. O campo que vai ao banco diz que é proxy. Embedding e a extensão `vector` ficam como pendência, com o motivo.
**Alternativas:** embedding pela API (mais cota, e a cota já é o gargalo da fatia); extensão `vector` no Postgres (nunca foi ligada, e ligá-la é fatia própria).
**Por quê:** a skill `gerador-questao-banca` pede similaridade por embedding, e cumprir isso hoje custaria a cota que a fatia precisa para **gerar e validar** — que é o que não pode faltar. Um proxy declarado como proxy é honesto; um proxy exibido como medida é a ADR-0036 de novo. A rede de segurança de verdade continua sendo o calibrador (fatia 11), que pega pelo comportamento real o que o estilo não pegou.

## ADR-0046 — Diagnóstico curto (8–12 itens), resultado de uma tela, lacuna em uma linha · 2026-09-23 · aceita (decisão do dono, primeiro acesso da piloto)
**Decisão:** o diagnóstico mede **8 a 12 itens**, parando quando a margem fecha, e sorteia só de matéria que tem questão na base. O resultado cabe numa tela sem rolagem: 3 matérias mais fortes, 3 mais fracas, um botão "começar por aqui". A lista de tópicos sai do resultado e volta para o edital verticalizado. O que a base não cobre vira **uma linha** ("61 dos 99 tópicos ainda não têm questão — estamos coletando"), nunca uma lista.
**Alternativas:** manter 30 itens com a precisão da ADR-0022; quebrar os 30 em blocos de 10 retomáveis; esconder as lacunas (viola a regra de não esconder o que não sabemos).
**Por quê:** medido na sessão de 23/09 — a tela tinha **1.777 palavras** e **81% das 101 linhas de tópico** falavam de lacuna nossa, não dela; a piloto parou de ler e disse estar cansada antes do fim. A precisão que os 30 itens compram serve a um painel que ela nunca chegou a ver. Para a única decisão que o dia 1 precisa tomar — o que estudar primeiro — 8 a 12 itens bastam, e o resto da precisão chega de graça pelas questões que ela responde estudando.

## ADR-0047 — Cobertura mínima do edital antes de liberar diagnóstico e plano · 2026-09-23 · aceita (decisão do dono)
**Decisão:** um edital só libera diagnóstico e plano do dia depois que a cobertura da base passa de um piso. Abaixo dele, a aluna vê uma tela de preparação honesta, com o estado real ("38 de 99 tópicos") e a ação de buscar questões — nunca um diagnóstico que mede o que não existe. O número do piso fica em aberto (fatia 15 §6).
**Alternativas:** liberar sempre e declarar a lacuna item a item (é o que fazia, e afundou a piloto); esconder os tópicos sem questão (esconde o problema em vez de resolvê-lo).
**Por quê:** palavra do dono — "não iniciamos sem questões, senão perde o sentido". Um diagnóstico sobre 38% do edital não mede a aluna, mede a nossa base; e apresentar isso como resultado dela é a ADR-0036 em outra roupa (dado errado com cara de certo).

## ADR-0048 — Ilustrações e ícones do protótipo voltam ao escopo · 2026-09-23 · aceita (reverte decisão da fatia 14)
**Decisão:** portar `art-hero`/`draw-art` e os ícones do protótipo para as telas do produto, na ordem `/` → `/rotina` → `/diagnostico` → `/hoje` → `/editais`. SVG inline, copiado do markup do protótipo, respeitando `prefers-reduced-motion`.
**Alternativas:** só ícones nas ações; manter como está e medir de novo.
**Por quê:** a exclusão na fatia 14 foi decidida antes de ver uma pessoa usando. O produto não tem **um único SVG** fora dos dois gráficos do painel, enquanto o protótipo que a própria piloto validou tem ilustração em 10 telas. A palavra do dono ao ver a tela pronta: "agora tá seca".

## ADR-0049 — Assistente de primeiro acesso em 3 passos, sem estado novo · 2026-09-23 · aceita (decisão do dono)
**Decisão:** depois do primeiro login, um assistente conduz em três telas — concurso, rotina, diagnóstico curto — uma pergunta por vez, retomável, e some ao concluir. A conclusão é **derivada** do que já existe (`perfil_estudo` gravado, diagnóstico concluído), sem coluna de "viu o tutorial".
**Alternativas:** tela "comece por aqui" na home (mais barata, mas ela ainda pode sair da ordem); tour com balões sobre as telas atuais (mais JS, contra a ADR-0019, e não resolve a ordem).
**Por quê:** hoje o login joga a aluna em `/conta` e a home oferece sete portas sem ordem. A ordem correta (`rotina` → `diagnóstico` → `hoje`) só existe na cabeça de quem escreveu o código; a piloto ficou confusa exatamente aí. Derivar o estado em vez de gravá-lo evita uma coluna que mente quando o fluxo muda.

## ADR-0050 — "Refazer o concurso" como módulo, e prova real da banca como fonte preferencial · 2026-09-23 · aceita (ideia e decisão do dono)
**Decisão:** o alvo de coleta passa a ser a **prova real da banca do edital em uso** (hoje, Instituto AOCP/TJ-PR), não só questões da Cebraspe sobre os mesmos tópicos. Sobre essa base nasce um módulo de estudo que permite **refazer a prova que a aluna já fez**, cronometrada, comparando com o desempenho real dela. Coleta de qualquer banca nova exige checagem escrita dos termos de uso antes (a régua que vetou a FGV, P-13).
**Alternativas:** seguir só com originais da Cebraspe mapeados por tópico (é o que existe, e nunca dá à aluna a questão que ela de fato enfrentou); gerar inéditas para cobrir tudo (depende de dossiê e de cota, e inédita não tem histórico real).
**Por quê:** a aluna **já fez essa prova** — existe uma nota verdadeira dela como ponto de comparação. É a única medida de "antes" que este produto não consegue fabricar, e ela vale mais que qualquer proxy de proficiência que a gente calcule. Some-se o óbvio: questão da banca certa é o padrão que o DNA do concurso tenta imitar.

## ADR-0051 — Gamificação: progresso e descanso sim; ofensiva, pontos e ranking não · 2026-09-23 · aceita (decisão do dono, avaliada pela skill `avaliador-de-feature`)
**Decisão:** o produto ganha camada de jogo **discreta e sem punição**. Entram no MVP dois mecanismos, avaliados em `avaliador-de-feature` com aderência ≥ 2 e evidência ≥ 2: (1) **sessão com fim visível** — toda sessão declara onde termina, com posição e barra, porque a piloto abandonou o diagnóstico por não ver o fim ("tava cansada pra isso", 23/09/2026); (2) **descanso conta como dia cumprido** — quando o agente recomenda descanso, o dia aparece cumprido, com o porquê, nunca como falha. Ficam de fora: **ofensiva/sequência diária — nunca**; pontos/XP e medalhas — pós-MVP (fase 2/3); ranking e social — fase 3, como a visão §6 já dizia. Clima visual: calmo com recompensa discreta — confirmação curta ao fechar o dia, sem som, sem confete, sem animação de comemoração.
**Alternativas:** ofensiva clássica (o que "gamificar" normalmente significa); ofensiva-espelho sem punição ("você estudou 4 dos últimos 7 dias"), que o dono considerou e descartou nesta rodada — pode voltar sem contrariar princípio nenhum; gamificação completa com XP e níveis.
**Por quê:** a ofensiva **existe para punir quem descansa** — é o mecanismo inteiro, não um efeito colateral. Isso contraria frontalmente "Descansar é uma recomendação válida" (visão §4, princípio inegociável) e contraria a única evidência de usuária que temos sobre o assunto: a Linda pediu "aviso discreto, **sem culpa**", "não quer pausa forçada nem bloqueio" (entrevista de 14/09/2026, rodadas 1 e 4). XP premia volume, e a tese do produto é acerto medido com intervalo, não quantidade — pior, responder no chute para pontuar contamina o diagnóstico, que é o dado que sustenta o plano inteiro. Os dois que entram somam ≈ 9 h, não chamam LLM, e o descanso-como-dia-cumprido **não foi encontrado em nenhum concorrente da pesquisa §6**: os outros fazem o oposto. É diferenciação barata e alinhada com a tese, em vez de cópia do padrão da categoria.
**O que mudaria:** se o piloto mostrar plano concluído em < 50 % dos dias ativos por desistência no meio da sessão, o progresso do dia (bloco 2 da avaliação, hoje pós-MVP) sobe para o MVP. Se a aluna usar descanso como fuga sistemática (> 50 % dos dias), o agente passa a perguntar em vez de aceitar.

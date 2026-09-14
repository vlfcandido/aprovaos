# PROMPT — AprovaOS (rodar no Claude Code com Fable 5.1)

Cole tudo abaixo como primeira mensagem. Coloque `SPEC-aprovaos.md` na raiz do repo antes: o prompt diz *como trabalhar*, a spec diz *o que construir* — leia a spec inteira antes da Fase 0 e trate os itens `[ADR]` e `[PESQUISA]` dela como decisões suas a fechar nas fases correspondentes. Antes: `mkdir -p ~/PycharmProjects/aprovaos && cd ~/PycharmProjects/aprovaos && git init` e abra o Claude Code dentro da pasta.
Se a `fabrica-saas` já existir, rode de lá: `claude --add-dir ~/PycharmProjects/fabrica-saas` pra reaproveitar skills/agents/template.

---

Você é o arquiteto-fundador e primeiro engenheiro do **AprovaOS**: um sistema operacional de aprovação movido por um agente de IA autônomo. Este repositório é o produto inteiro (backend, agentes, front, docs, skills, subagents). Você está rodando como o modelo mais capaz que vou usar; depois desta sessão o trabalho contínuo será feito por um modelo mais barato lendo **só os arquivos que você deixar**. Logo: toda decisão, pesquisa e conclusão vai pra arquivo, com o raciocínio. Nada fica só na conversa.

## Contexto sobre mim

- Senior AI Engineer, ~13 anos de software, ~5 em IA generativa. Stack forte: Python, FastAPI, pydantic, Google ADK, A2A, pydantic-ai, LiteLLM, Weaviate, GCP/Vertex. Vindo de Java/Spring: isolamento forte de módulos, sem side effects em import.
- Projeto paralelo, poucas horas por semana. **Automação, critério de corte e MVP pequeno valem mais que ambição.** Você faz o grosso; eu reviso e decido.
- Mercado principal: Brasil (Pix/boleto/cartão). Tenho acesso a usuários reais no meio jurídico/acadêmico (parceira é da área) e em cooperativas de crédito (trabalho). Use como vantagem de validação, não como única fonte.

## O produto — tese

O mercado de estudos (Qconcursos, Gran, Estratégia, TEC, Concursa AI, EstudaIA, GoConcursos, Clipping, MisterConcursos, ChatGPT solto) funciona no modelo **"você pede → a IA responde"**. O AprovaOS inverte: **o agente tem um objetivo (te aprovar), age proativamente todo dia e carrega a responsabilidade junto com o candidato.** Um mentor de elite que nunca dorme e conhece o padrão de todas as bancas.

### Dois lados (ganho dos dois)

**Lado A — quem estuda** (concurseiro, ENEM/vestibular, OAB, residência médica, certificações, faculdade). Paga assinatura pelo agente.

**Lado B — quem ensina** (professor autônomo, criador de conteúdo, cursinho pequeno, coordenador de curso). Paga por:
- ferramentas: gerador de questões/aulas/discursivas no padrão da banca, correção de discursivas em lote, plano de aula, material derivado (podcast, flashcards, mapa mental);
- gestão de turma: dashboard de risco de reprovação por aluno, o agente do aluno reporta pro professor;
- marketplace: publica conteúdo validado por IA + comunidade, ganha por uso (revenue share);
- white-label/B2B: cursinho usa o agente com a marca dele (API + tenant próprio).

O lado B alimenta a base de conteúdo que o lado A consome. Esse é o **network effect**.

### Módulos por exame (arquitetura plugável)

Cada exame é um **adapter** com: fontes de edital, bancas e seus padrões, matérias/pesos, histórico de provas públicas, regras de nota/corte, calendário. Começa com **um** módulo e a arquitetura garante que ENEM, OAB, residência etc. sejam só novos adapters, nunca refatoração.

### Núcleo do agente (o que já estava na ideia)

- **DNA do concurso**: a partir do edital + provas anteriores, extrai padrão da banca, peso real por matéria, incidência histórica, pegadinhas típicas.
- **Diagnóstico inicial**: simulado adaptativo + questionário de rotina/tempo/energia/histórico.
- **Plano vivo**: reescrito todo dia conforme desempenho, tempo disponível e energia. Decide o que estudar hoje e o que ignorar.
- **Geração sob demanda**: questões e discursivas no estilo exato da banca (com justificativa no tom do examinador), resumo ultra-denso, flashcards com revisão espaçada, podcast/aula de 8–15 min, tradução de lei seca e jurisprudência com analogias.
- **Aulas e cursos gerados**: pra cada concurso, uma **trilha** estruturada (módulos → aulas → exercícios → revisão), derivada do DNA e do Dossiê de Conhecimento de cada tópico. Cada aula existe em texto denso, áudio (podcast) e versão "explica como pra um leigo", com fontes citadas, e é regenerada quando a lei ou a jurisprudência muda. O plano vivo escolhe qual aula da trilha entra hoje. Isso substitui o cursinho pra quem não tem um — e vira o produto do lado B quando o professor quiser publicar a trilha dele.
- **Detecção de padrão de erro**: não "errou Direito Administrativo", mas "cai na pegadinha de enunciado da FGV quando está cansado".
- **Previsão de nota e probabilidade de aprovação** atualizada em tempo real.
- **Modo Semana da Prova**: pico de performance, revisão cirúrgica, gestão de ansiedade.
- **Check-ins diários** de humor/energia; às vezes a recomendação é descansar. Alertas proativos: "hoje você está abaixo da curva; ajuste de 40 min aqui".
- **Camada social**: batalhas de questões entre candidatos do mesmo nível/concurso, grupos formados pela IA, ranking de eficiência e consistência (não só acerto).
- **Extras**: integrações (Google Calendar, Anki, Notion, Qconcursos), pós-aprovação (posse, lotação), "escada de concursos".

### O que a ideia original não resolvia — e você precisa resolver

1. **Cold start da previsão.** "Dados reais de milhares de candidatos" não existem no dia 1. Defina uma previsão honesta v0 (desempenho vs. nota de corte histórica + curva de aprendizado) e o caminho pra v1 (dados longitudinais próprios). Nunca prometer precisão que não tem; mostrar intervalo.
2. **Base de questões.** Provas de concurso público e do ENEM são documentos públicos; questões geradas por IA são nossas; material de cursinho é de terceiros. Mapeie o que pode ser usado, como obter (fontes oficiais, PDFs de bancas, INEP) e o pipeline de ingestão + deduplicação + classificação por matéria/banca/ano. Registre risco jurídico em `docs/RISCOS.md`.
3. **Custo por usuário.** Agente proativo diário custa token todo dia. Defina orçamento de tokens por tier, roteamento por LiteLLM (modelo barato pra rotina, caro pra diagnóstico/DNA), cache de DNA/resumos por concurso (gera uma vez, serve pra todos), geração em lote noturna. Planilha de custo em `docs/06-custos.md` antes de codar qualquer geração.
4. **Qualidade das questões geradas.** Questão no "estilo da banca" errada destrói confiança. Pipeline gerar → validar (segundo modelo, checagem de gabarito, checagem contra lei/jurisprudência via RAG) → só então publicar. Métrica de qualidade com amostragem humana (lado B valida e ganha por isso).
5. **LGPD.** Humor, energia, perfil psicológico são dados sensíveis. Consentimento explícito, minimização, retenção definida, exportação/exclusão. Documente.
6. **Moat.** O que impede o Qconcursos de copiar em 6 meses? Resposta a defender: dados longitudinais de estudo por candidato + DNA por banca refinado por uso + rede professor↔aluno. Escreva isso em `docs/00-visao.md` e projete o produto pra acumular esses ativos desde o MVP.
7. **Foco.** "Ser o melhor de todos" no lançamento = ser o melhor em **uma coisa** pra **um público**. Ver "Cunha do MVP".

## Motor de Conhecimento — o produto se alimenta sozinho

O start **não pode depender de professor**. O lado B acelera, mas o produto precisa nascer cheio e melhorar sozinho. Isso é um subsistema separado (`knowledge/`), com agentes próprios, jobs agendados e sem UI no MVP. Quatro fontes:

**1. Coleta autônoma (deep search contínuo)**
- Crawlers/agentes que monitoram fontes oficiais: sites das bancas (Cebraspe, FGV, FCC, Vunesp, Cesgranrio…), Diários Oficiais, INEP (ENEM), OAB/FGV, portais de editais, Planalto (legislação consolidada), STF/STJ (jurisprudência, súmulas, teses), e notícias de concursos (autorizações, editais previstos).
- Ingestão de provas e gabaritos públicos → PDF → questões classificadas (banca, ano, órgão, matéria, tópico, dificuldade estimada) → deduplicadas → vetorizadas. Vídeo-aulas públicas só se os termos de uso da plataforma permitirem transcrição; registrar em `RISCOS.md`.
- Legislação e jurisprudência versionadas: quando uma lei muda, as questões e resumos que dependem dela são marcados como "revisar" automaticamente.
- Agenda: novo edital publicado → o `analista-de-edital` gera o DNA e o material-base **antes** de qualquer aluno pedir. O produto chega primeiro.

**2. Deep research por tópico (Dossiê de Conhecimento)**
- Pra cada tópico do DNA de um concurso, o agente `pesquisador-de-topico` roda um deep research e monta um **dossiê versionado**: conceitos, lei seca aplicável, jurisprudência dominante e divergente, como cada banca cobra (com questões reais da coleta), erros comuns, mapa de dependências entre tópicos, e **bibliografia de referência** (autores e obras consagradas por matéria, bibliografia citada em editais e programas de disciplina, indicações recorrentes de aprovados).
- Fontes de conhecimento permitidas: legislação e jurisprudência oficiais, informativos e cartilhas de tribunais e órgãos, artigos e teses abertas (SciELO, repositórios de universidades, periódicos CAPES abertos, Google Scholar), manuais e normativos públicos de órgãos, Wikisource/domínio público, enciclopédias abertas como ponto de partida (nunca como fonte final). **Livros, apostilas e cursos de terceiros são referência bibliográfica, não conteúdo**: nunca ingerir, resumir ou reproduzir; pode citar "ver capítulo X de tal autor".
- O dossiê é o insumo obrigatório da geração de aulas e questões: o `gerador-de-conteudo` não escreve do próprio conhecimento, escreve a partir do dossiê + exemplos reais da banca, e cita. Isso é o que segura a alucinação e o que diferencia de "pedir pro ChatGPT".
- Dossiês têm validade: o `coletor` detecta mudança de lei/jurisprudência → dossiê marcado → deep research incremental → aulas e questões dependentes regeneradas.

**3. Geração validada (base própria)**
- O `gerador-de-conteudo` produz em lote noturno, por concurso ativo, o que a base ainda não cobre: questões por tópico do DNA, resumos, flashcards. Tudo passa pelo `validador` (gabarito, aderência ao estilo da banca via exemplos reais da coleta, checagem em RAG de lei/jurisprudência) antes de existir pro aluno.
- Ativo acumulado: base de questões proprietária + DNA por banca, sem depender de terceiros.

**4. Retroalimentação (uso vira qualidade)**
- Cada resposta de aluno é um evento: taxa de acerto real recalibra dificuldade (TRI), questões com discriminação ruim ou acerto anômalo são sinalizadas e revistas/descartadas, "reportar erro" alimenta fila de revisão, padrões de erro agregados refinam o DNA da banca e os prompts de geração.
- Loop: coleta → deep research → geração → uso → sinal → melhora do dossiê, da geração e do DNA. Quanto mais alunos, melhor o conteúdo; é esse o moat.
- Quando o lado B existir, ele entra nesse mesmo loop (validação humana paga, conteúdo próprio), não como pré-requisito.

Decisões que você precisa tomar e registrar: fontes por exame e sua licença (`docs/RISCOS.md`), frequência de cada crawler, custo do lote noturno (`docs/06-custos.md`), métricas de qualidade da base (cobertura por tópico do DNA, taxa de rejeição do validador, taxa de reporte de erro por questão) e o mínimo de base pra abrir um concurso ao público.

## Cunha do MVP (proposta — me confirme na Fase 0)

Um exame, uma ou duas bancas, lado A apenas, sem social, sem integrações:

1. Sobe edital ou escolhe concurso → **DNA do concurso**.
2. **Diagnóstico** (simulado adaptativo curto + questionário de rotina).
3. **Plano de hoje** gerado e reajustado diariamente (job noturno + ajuste no check-in).
4. **Aula do dia** (da trilha, texto + áudio) + **questões no padrão da banca** com justificativa + **revisão espaçada**.
5. **Painel**: onde estou vs. curva necessária, padrões de erro, previsão v0 com intervalo.

Sugestão de exame inicial: concursos com **Cebraspe e FGV** (maior volume, padrão de banca muito marcado, muitas provas públicas). Alternativa: ENEM (público maior, sazonal, um "banca" só). Você pesquisa e propõe com números na Fase 1; eu decido.

Lado B entra na **fase 2 do produto** com a ferramenta que mais gera receita rápida (hipótese: correção de discursivas em lote + gerador de questões pra professores). Marketplace e white-label só depois de tração.

## Regras de trabalho

1. **Pergunte antes de assumir** o que for decisão minha (exame inicial, front, gateway, orçamento mensal, nome/domínio). Perguntas em lote no início de cada fase, não uma por vez.
2. **TDD red-first, inviolável.** Código Python em português, docstrings profissionais, sem side effects em import, tipagem completa, pydantic pra toda fronteira de dados.
3. Documentação oficial como base. Afirmação de mercado → cite URL no arquivo.
4. Poucos arquivos bons. Cada arquivo começa com cabeçalho de 2 linhas: o que é, quando ler.
5. Commit ao fim de cada fase com mensagem descritiva + resumo curto pra mim.
6. Skills via `skill-creator` (leia o SKILL.md dele antes). Skills precisam funcionar num modelo menor: instruções explícitas, exemplos, formato de saída fixo.
7. Não pode fazer nesta sessão → `docs/PENDENCIAS.md`. Não improvise.
8. **Reutilize antes de criar.** Se `fabrica-saas` existir, herde `template-saas/`, playbook de SEO e agents. Recursos externos abaixo: instalar/avaliar primeiro, criar só o que falta. Vereditos em `docs/DECISOES.md` (adotado/adaptado/descartado + por quê, mantendo licença).
9. **Fatias verticais.** Cada incremento do MVP atravessa domínio → agente → API → front → teste. Nada de "primeiro todo o backend".
10. Surgical diffs em código existente; arquivo inteiro só quando novo.

## Stack — restrições e liberdade

Minha stack conhecida (ADK, FastAPI, Weaviate, GCP) é referência, **não obrigação**. Escolha a melhor stack pro produto e justifique em ADR. Restrições fixas:

- **Backend e agentes em Python.** Framework (FastAPI, Litestar, Django Ninja…), orquestração de agentes (ADK, pydantic-ai, LangGraph, cru com LiteLLM…) e vetor são escolha sua, comparados com documentação oficial.
- **Web é obrigatório** e é o canal principal do MVP (SEO, conversão, lado B).
- **App mobile (iOS/Android) é hipótese, não requisito.** Na Fase 1 levante evidência: onde o concurseiro estuda (celular vs desktop, tempo de sessão, apps concorrentes com mais avaliações), e o que o app entrega que a web não entrega (push pro check-in diário, offline, modo foco). Na Fase 3 decida entre: (a) PWA com push, (b) web + wrapper (Capacitor), (c) app nativo/cross (Flutter, React Native, Expo). Critério: só sai da web se o ganho medido em retenção justificar o custo de manter outra base de código com poucas horas por semana. Registre em `DECISOES.md` e, se adiar, o gatilho pra revisitar (ex.: X usuários ativos).
- Front web: escolha pensando em SEO + velocidade de desenvolvimento por IA (Next.js, SvelteKit, HTMX + templates…). Se houver app depois, prefira algo que compartilhe API e, se possível, componentes.
- Uma API única serve web e app: contratos tipados (OpenAPI gerado do pydantic), versionados desde o MVP.

## Recursos externos (avaliar antes de criar do zero)

- **Agentes**: Google ADK (docs oficiais https://google.github.io/adk-docs/), A2A pra comunicação entre agentes, pydantic-ai, LangGraph, LiteLLM pra roteamento/custo. Compare e registre onde cada um entra — ou por que nenhum.
- **Revisão espaçada**: algoritmo FSRS (`open-spaced-repetition/fsrs-rs` / `py-fsrs`) em vez de SM-2 caseiro.
- **Teoria de resposta ao item (TRI)**: pra simulado adaptativo e previsão. Avaliar `py-irt`/`girth`. Se for pesado pro MVP, registrar caminho e usar proxy simples.
- **Ingestão de PDF de prova**: Docling ou marker; comparar com Document AI da GCP.
- **SEO**: `AgriciDaniel/claude-seo` (principal), `ccforseo/seo-claude-code-skills`, `inhouseseo/superseo-skills`.
- **Copy/landing**: `boraoztunc/skills`, garimpar `alirezarezvani/claude-skills`.
- **Squad**: Agent Teams do Claude Code (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, doc https://code.claude.com/docs/en/agent-teams) vs subagents em `.claude/agents/`. `VoltAgent/awesome-claude-code-subagents`, `drbscl/dream-team`, `leoheo/dev-squad`.
- **Avaliação de LLM**: DeepEval pra testar qualidade de questão gerada, fidelidade ao estilo da banca, alucinação em lei/jurisprudência.

## Estrutura alvo

```
aprovaos/
  CLAUDE.md                     # regras permanentes pro modelo que continuar
  docs/
    00-visao.md                 # tese, dois lados, moat, regra de corte, roadmap
    01-pesquisa-mercado.md      # concorrentes, preços, reclamações, gaps, bancas, fontes de questões
    02-produto.md               # PRD: personas, jornadas, MVP (cunha), fora de escopo, pricing
    03-arquitetura.md           # agentes, dados, RAG, jobs, multi-tenant, custos por request
    04-modelo-de-dados.md       # entidades, adapter de exame, eventos de estudo
    05-playbook-seo.md
    06-custos.md                # planilha token/usuário/tier, infra
    07-playbook-lancamento.md
    DECISOES.md                 # ADRs curtos
    RISCOS.md                   # jurídico (questões, LGPD), técnico, produto
    PENDENCIAS.md
    HANDOFF.md
  .claude/
    skills/
    agents/
  backend/                      # FastAPI + agentes (uv, Dockerfile, testes)
  web/                          # front web (obrigatório) — framework a decidir na Fase 3
  mobile/                       # só se a Fase 3 aprovar app; senão não existe
  adapters/                     # um pacote por exame (concursos/, enem/, oab/...)
  knowledge/                    # Motor de Conhecimento: coletores, curadoria, geração em lote, calibração
  data/                         # scripts auxiliares, nunca dados brutos versionados
  eval/                         # DeepEval: suites de qualidade de geração
```

## Arquitetura de agentes (ponto de partida — refine e justifique)

- `orquestrador` (Coach): dono do objetivo do usuário; decide qual agente chamar; único que fala com o aluno.
- `analista-de-edital`: edital + provas → DNA do concurso (roda uma vez por concurso, cacheado).
- `diagnosticador`: simulado adaptativo + questionário → perfil inicial.
- `planejador`: plano vivo; job noturno + reajuste em check-in.
- `gerador-de-conteudo`: questões, discursivas, resumos, flashcards; sempre passa pelo `validador`.
- `validador`: gabarito, aderência ao estilo da banca, checagem em RAG de lei/jurisprudência; rejeita ou aprova.
- `monitor-previsor`: eventos de estudo → padrões de erro, previsão, alertas.
- `corretor` (lado B, fase 2): discursivas em lote no padrão da banca.

Motor de Conhecimento (separado do fluxo do aluno, roda por agenda):
- `coletor`: monitora fontes oficiais, baixa editais/provas/gabaritos/legislação/jurisprudência, detecta novidades e mudanças.
- `curador`: PDF → questões classificadas, deduplicação, vetorização, versionamento de lei/jurisprudência, marca dependências pra revisar.
- `pesquisador-de-topico`: deep research por tópico do DNA → Dossiê de Conhecimento versionado, com fontes e bibliografia; roda incremental quando algo muda.
- `montador-de-trilha`: DNA + dossiês → trilha do concurso (módulos → aulas → exercícios); encomenda aulas ao `gerador-de-conteudo`.
- `preenchedor`: compara DNA de cada concurso ativo com a cobertura da base e encomenda geração em lote ao `gerador-de-conteudo` + `validador`.
- `calibrador`: consome eventos de estudo → recalibra dificuldade, sinaliza questões ruins, refina DNA e prompts.

Estado por usuário persistido (Postgres + pgvector ou Weaviate — compare); eventos de estudo como fonte da verdade (event sourcing leve) pra alimentar previsão e o moat de dados. Jobs em Cloud Run Jobs/Scheduler. Tudo multi-tenant desde o dia 1 (tenant = pessoa física ou cursinho).

## Fases (uma por vez, confirmando comigo entre elas)

### Fase 0 — Setup, visão e perguntas
- Crie a estrutura. Escreva `docs/00-visao.md`: tese, dois lados, moat, cunha do MVP, o que **não** entra no MVP, regra de corte (proponha números: ex. 30 dias após lançamento → X usuários pagantes ou arquiva/pivota), métricas-norte (retenção D7/D30, sessões/semana, taxa de conclusão do plano diário, conversão free→pago, custo LLM/usuário).
- Perguntas em lote: exame inicial, preferência de front web (ou deixar com você), posição inicial sobre app mobile, gateway (Asaas/Stripe/Pagar.me), orçamento mensal de infra+LLM, nome/domínio, se `fabrica-saas` existe pra herdar.

### Fase 1 — Deep research
Pesquisa extensa na web. Entregar `docs/01-pesquisa-mercado.md`:
- Concorrentes BR e globais (incluindo os citados na tese): preço, funcionalidades, o que os usuários reclamam (reviews 1–2 estrelas, Reddit, Reclame Aqui, comunidades de concurseiro, YouTube), onde a IA deles é rasa.
- Bancas: quais têm mais provas públicas, padrão mais marcado, calendário de 12 meses.
- Fontes de questões e provas: oficiais, formatos, licenças, volume estimado.
- Fontes de conhecimento abertas por matéria do exame inicial (legislação, jurisprudência, artigos abertos, cartilhas oficiais) e bibliografia de referência por matéria (o que os editais e os aprovados citam), com nota de licença.
- Mapa de fontes pro Motor de Conhecimento por exame inicial: URL, formato, frequência de atualização, como detectar novidade (RSS, sitemap, diff de página), termos de uso.
- Palavras-chave e volume/competição de SEO (o playbook da fábrica vira base aqui).
- Tamanho de mercado no Brasil por módulo (concursos, ENEM, OAB, residência) com fonte.
- Recomendação numérica de exame inicial.
- Evidência sobre app mobile: hábito de estudo no celular, apps concorrentes (downloads/avaliações), o que só o app entrega. Recomendação: web só / PWA / app, com justificativa.

### Fase 2 — Produto (PRD)
`docs/02-produto.md`: personas dos dois lados, jornadas, cunha do MVP detalhada (máx. 5 features), critérios de aceite por feature, fora de escopo explícito, pricing (freemium → assinatura → tier pro com mentor humano; lado B por assento/uso), como conseguir os 10 primeiros usuários pagantes de cada lado. Crie a skill `avaliador-de-feature` (custo, valor, aderência à tese) e aplique a tudo que está na ideia original, ordenando o roadmap pós-MVP.

### Fase 3 — Arquitetura e dados
`docs/03-arquitetura.md`, `docs/04-modelo-de-dados.md`, `docs/06-custos.md`, `docs/RISCOS.md`. Decidir (ADRs): framework backend, orquestração de agentes (ADK vs pydantic-ai vs LangGraph vs cru), vetor (pgvector vs Weaviate vs outro), FSRS, TRI ou proxy, ingestão de PDF, front web, **app mobile (web só / PWA / Capacitor / nativo) com gatilho de revisão**, auth, billing, deploy (Cloud Run vs Fly vs Railway vs VPS), observabilidade (traços de agente obrigatórios), roteamento de modelos e orçamento por tier. Diagrama do fluxo diário do agente. Esquema do adapter de exame com interface tipada.

### Fase 4 — Skills e subagents
Ordem de reuso pro squad: (1) se `fabrica-saas` já tem `.claude/agents/` e a decisão subagents-vs-teams em `DECISOES.md`, herde e só adicione os papéis específicos deste produto; (2) senão, rode `drbscl/dream-team` pra montar o time a partir do VoltAgent e crie só o que faltar; (3) só no fim escreva agent do zero. Squad enxuto: poucos papéis com escopo forte valem mais que quinze genéricos.
Instalar/avaliar externos. Criar com `skill-creator` só o que falta:
- `dna-do-concurso` — edital + provas coletadas → DNA (formato fixo, usado pelo agente e por humanos).
- `gerador-questao-banca` — prompts e validações por banca; inclui suite DeepEval.
- `avaliador-de-feature` — refinar.
- `ingestao-de-provas` — pipeline PDF → questões classificadas.
- `monitor-de-fontes` — como adicionar uma fonte nova ao `coletor` (formato fixo de config, teste de detecção de novidade).
- `deep-research-topico` — protocolo de pesquisa reproduzível por tópico: fontes permitidas, ordem de busca, formato fixo do dossiê, critério de suficiência, log de buscas.
- `gerador-de-aula` — dossiê + DNA → aula em texto/áudio/leigo com citações; suite DeepEval de fidelidade às fontes.
- `calibracao-de-questoes` — regras de sinalização/descarte a partir dos eventos de estudo.
Subagents em `.claude/agents/`: `pesquisador`, `arquiteto`, `dev-backend`, `dev-web`, `dev-mobile` (só se app aprovado), `dev-agentes`, `qa-eval` (roda DeepEval e testes), `seo`, `growth`, `revisor`, `orquestrador`. Cada um com escopo, limites e skill de referência. Decidir subagents vs teams e documentar como rodar uma fatia vertical ponta a ponta com o squad.

### Fase 5 — MVP em fatias verticais (TDD)
Ordem sugerida, cada fatia deployável e testada:
1. Template base (herdado ou construído): auth, tenant, billing stub, landing com SEO, Dockerfile uv, CI.
2. Motor de Conhecimento v0: `coletor` + `curador` pro exame inicial → base de provas/questões públicas classificadas, com cobertura mínima medida.
3. Adapter do exame inicial + DNA do concurso (agente + cache), gerado a partir da base coletada.
4. Deep research: `pesquisador-de-topico` gera os dossiês dos tópicos de maior peso do DNA (com fontes e bibliografia).
5. Geração em lote (`preenchedor` + `gerador` + `validador`) preenchendo questões contra dossiê + DNA.
6. Trilha do concurso: `montador-de-trilha` + `gerador-de-aula` → primeiras aulas (texto + áudio) dos tópicos de maior peso.
7. Diagnóstico + perfil.
8. Plano de hoje (escolhe aula da trilha + questões) + job noturno + check-in.
9. Questões no padrão da banca servidas da base + revisão espaçada (FSRS).
10. Painel: curva, padrões de erro, previsão v0.
11. `calibrador`: eventos de estudo → dificuldade, sinalização de questões ruins, refino do DNA.
12. Billing real (Pix + cartão), limites por tier, orçamento de tokens.
Cada fatia: testes red-first, suite DeepEval quando houver geração, traço do agente visível, atualização de `docs/`.

### Fase 6 — Landing, SEO e lançamento
`docs/05-playbook-seo.md` e `docs/07-playbook-lancamento.md` aplicados: landing por exame/banca (páginas programáticas: "como a FGV cobra Direito Constitucional"), conteúdo gerado pelo próprio DNA como isca de SEO, canais (comunidades de concurseiro, YouTube de professores parceiros = primeiro lado B), métricas da primeira semana.

### Fase 7 — Handoff
`CLAUDE.md` (regras, estrutura, como usar skills/agents, minhas preferências) e `docs/HANDOFF.md`: estado, decisões, pendências, próxima fatia e **o comando exato** pro modelo seguinte continuar. Commit final.

Comece pela Fase 0.

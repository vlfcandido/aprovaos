# Pesquisa de mercado — Fase 1
> O que é: síntese da rodada de pesquisa `wf_09928095-f09` (14/09/2026): 9 ângulos de fatos (Sonnet), 6 verificações céticas (Sonnet), gaps do ramo de estudos pelo script da fábrica, mais a entrevista com a Linda — consolidados aqui (Opus, em sessão, porque o reboot matou a etapa de síntese do workflow). Quando ler: no portão da Fase 1 (decisão do exame inicial), na Fase 2 (PRD: concorrentes, preço, cunha) e na Fase 3 (mapa de fontes do Motor, mobile, riscos jurídicos).

**Como ler os selos.** `[id]` aponta para o fato bruto em `docs/evidencias/raw/2026-09-14-fase1/fato__<ângulo>.json`; **✔** = verificador abriu a URL e o trecho confere; **✘** = não sustentado; **n/v** = ângulo sem verificação (SEO, concorrentes); **SEC** = fonte secundária (imprensa/cursinho citando o órgão). Números sem selo não existem neste arquivo: o que não foi medido está escrito como "não medido" e virou pendência (§11).

**Resumo em cinco linhas.**
1. **Exame inicial: concursos com Cebraspe + FGV, confirmado pelos números — mas não pelos motivos que a hipótese supunha.** Ganha por calendário contínuo (dezenas de editais ativos o ano todo, sem pico único), pela maior disposição a pagar do segmento (assinaturas de R$ 744 a R$ 2.375/ano nos incumbentes) e pelas fontes abertas de legislação/jurisprudência que cobrem as matérias de maior peso. Perde do ENEM em público (4,8 M contra centenas de milhares) e da OAB em provas abertas e organizadas (47 edições num só lugar).
2. **A maior lacuna é a nossa própria matéria-prima:** os sites da Cebraspe e da FGV não abriram por HTTP simples (JavaScript), então **o volume de provas públicas e os termos de uso das duas bancas continuam não medidos**. É a primeira coisa a fazer antes da Fase 3 (P-11), com navegador.
3. **A concorrência "IA-first" já vende "cole o edital → cronograma" por R$ 25–50/mês** (MisterConcursos, Concursa.ai, Clipping.ai). O cronograma automático **não é diferencial**; é entrada. O diferencial defensável está no que ninguém mostrou: conteúdo validado com fonte, revisão/memória interligada, previsão com intervalo, agente que explica e reajusta.
4. **Mobile: web responsiva + PWA instalável com push**, não app. 58 % dos usuários de internet no Brasil acessam só pelo celular (87 % nas classes DE), o app do Qconcursos tem 81 mil avaliações no iOS, mas o app do Estratégia tem nota 1,4 — app ruim custa mais que app nenhum. Web Push no iOS existe desde o 16.4 para PWA instalada. A usuária entrevistada estuda no notebook.
5. **Jurídico: leis e atos oficiais não são protegidos por direito autoral (Lei 9.610, art. 8º, IV); questões de prova, "por si só", também não, segundo o TJ-SP (secundário); regime de pequeno porte da ANPD dispensa DPO.** Faltam os termos de uso das bancas e do INEP e a leitura literal do art. 5º, II da LGPD (humor/energia) — vão para `RISCOS.md`.

---

## 1. Tamanho de mercado por módulo (Brasil)

| módulo | número | ano | selo | fonte |
|---|---|---|---|---|
| **ENEM** — inscrições confirmadas | **4.811.338** (+11,22 % vs 2024; +38 % vs 2022) | 2025 | ✔ SEC (CNN citando INEP) `[mercado-01]` | https://www.cnnbrasil.com.br/educacao/enem-2025-inep-confirma-mais-de-48-milhoes-de-inscritos/ |
| **Concursos** — CNU ("Enem dos concursos") inscritos / vagas | **761.528 / 3.652** | 2025 | ✔ SEC (Aprova Concursos) `[mercado-02]`; gov.br/mgi deu 404 | https://www.aprovaconcursos.com.br/noticias/concurso-nacional-unificado-2025/ |
| Concursos — CNU por região | Sudeste 247.838 · Nordeste 229.436 · Centro-Oeste 150.870 · Norte 84.651 · Sul 48.733 | 2025 | ✔ SEC `[mercado-03]` | https://folha.qconcursos.com/n/cnu-2025-inscritos-por-estado |
| Concursos — editais ativos da **Cebraspe** listados num agregador | "dezenas" na consulta original; o verificador viu **~200+ editais** listados em 14/09 (inclui reaberturas e retificações) | set/2026 | ✔ SEC, número impreciso `[bancas-03]` | https://www.pciconcursos.com.br/organizadoras/cebraspe |
| Concursos — concursos em andamento da **FGV Conhecimento** | **~20** na primeira página da listagem oficial | set/2026 | ✔ oficial `[bancas-06]` | https://conhecimento.fgv.br/concursos |
| **OAB** — 45º Exame: inscritos / aprovados / aprovação geral | **132.534 / 21.644 / 14,30 %** | 2025 | ✔ SEC (Estratégia OAB compilando dados FGV/OAB) `[mercado-04]` | https://oab.estrategia.com/portal/estatisticas-completas-do-exame-de-ordem-da-oab/ |
| OAB — 46º Exame: aprovação 1ª fase / 2ª fase | 39.825 (57,20 %) / 25.693 (57,42 %) | 2025–26 | ✔ SEC `[mercado-05]` | idem |
| **Residência médica** — ENARE 2025/26: inscrições medicina / vagas / cand./vaga | **87.040 / 6.939 / 12,54** | 2025/26 | ✔ SEC `[mercado-06]` | https://med.estrategia.com/portal/noticias/enare-2025-2026-bate-novo-recorde-e-ultrapassa-87-mil-inscricoes-para-residencia-medica/ |
| Residência — ENARE 2024/25 | 53.171 candidatos / 4.874 vagas (+64 % em um ano) | 2024/25 | ✔ SEC `[mercado-07]` | idem |
| **Vestibular** — Fuvest 2025 | ~107 mil inscritos / 8.147 vagas | 2025 | ✔ por WebSearch cruzado; URL original 404 `[mercado-10]` | (imprensa; ver raw) |

**Leitura.** O ENEM é 6× o CNU em inscritos, mas o CNU é *um* concurso; o universo de concurseiros ativos é a soma de centenas de editais por ano (Cebraspe sozinha com dezenas simultâneos) e **não foi medido nesta rodada** (lacuna: estimativa de mercado de "concurseiros ativos" e gasto médio — P-14). A OAB é o módulo mais previsível: ~130 mil inscritos por edição, 3 edições/ano, uma banca só (FGV), 47 provas abertas. A residência médica cresce 64 %/ano no ENARE e já é FGV também.

**Não medido:** receita/alunos de Gran, Estratégia e Qconcursos; gasto médio anual do concurseiro; Unicamp/Comvest; preço do Qconcursos (403) e da Estratégia por mês (só anual).

## 2. Bancas — volume, padrão, calendário

| banca | o que se sabe | selo |
|---|---|---|
| **Cebraspe** | Itens **certo/errado**; metodologia recomendada +1 / −1 / 0 (branco), **"um erro anula um acerto"**, mas a anulação **não é aplicada em todos os editais** — o órgão contratante escolhe `[bancas-01 ✔ SEC][bancas-02 ✔ SEC baixa]`. Calendário 2026 citado pela imprensa especializada: PCDF Delegado (150 vagas), Sefaz-DF (115+150), PM-AL (1.000+60), ISS Porto Velho `[bancas-10 ✔ SEC]`. **Site institucional é renderizado em JavaScript: nem a seção de provas, nem termos de uso, nem contagem de concursos abriram por HTTP** `[bancas-04 ✔]`. | volume e provas: **não medido** |
| **FGV Conhecimento** | ~20 concursos em andamento na listagem oficial, com paginação de realizados `[bancas-06 ✔]`. A página "Provas aplicadas" é um hub de certificado, sem lista de provas; a hipótese de **microsites por edital** (ex.: `enare2026.conhecimento.fgv.br/provas/`) **não foi sustentada** `[bancas-05 ✘][bancas-11 ✘]`. Formato (múltipla escolha A–E) não confirmado no site oficial. | volume e provas: **não medido** |
| FCC, Vunesp, Cesgranrio, AOCP | Contagens de "583 / 474 / 147 concursos" só apareceram em snippets do Qconcursos (403) — **não confirmadas** `[bancas-08 ✔ sobre a limitação]`. Cesgranrio: IBGE, 27.279 recenseadores, edital até out/2026 `[bancas-09 ✔ SEC]`. | de passagem |

**Consequência para o produto.** O "padrão de banca muito marcado" da hipótese vale para a Cebraspe (C/E com anulação é o dado técnico mais repetido do nicho, `[seo-02]`) e é *variável por edital* — o DNA do concurso precisa ler a regra de correção **do edital**, não da banca. Para a FGV nada foi confirmado na fonte primária. **P-11:** mapear com navegador (Chrome) a seção de provas das duas bancas: URL, formato, anos, termos de uso, existência de sitemap/RSS.

## 3. Fontes de provas e gabaritos — mapa para o coletor

| fonte | URL | formato / detecção | licença ou risco | volume | selo |
|---|---|---|---|---|---|
| **INEP — ENEM** | https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enem/provas-e-gabaritos | PDF por ano (abas 1998–2025, carregam via JS); detecção: **desconhecida** | **CC BY-ND 3.0 Não Adaptada** — atribuição obrigatória e **proíbe obras derivadas** | 28 anos | ✔ `[fontes-provas-01]` |
| **OAB/FGV — Exame de Ordem** | https://examedeordem.oab.org.br/EditaisProvas?NumeroExame=0 | download individual ou pacote único; formato presumido PDF; detecção: desconhecida | sem termos localizados; titularidade não confirmada | **47 edições** (2010.2 → atual) | ✔ `[fontes-provas-02]` |
| **Cebraspe** | https://www.cebraspe.org.br/concursos/ | JS; não exposto por HTTP | termos não localizados (`/politica-de-privacidade/` 404) | não medido | ✔ sobre a limitação `[fontes-provas-03]` |
| **FGV Conhecimento** | https://conhecimento.fgv.br/node/141 | hub sem listagem | termos não localizados | não medido | ✔ sobre a limitação `[fontes-provas-04]` |
| **DOU (Imprensa Nacional)** | https://www.in.gov.br/servicos/diario-oficial-da-uniao | WebFetch falhou; a API WS-INCom **parece** restrita (snippet, não evidência) | não verificado | — | ✘ (sem evidência) |
| PCI Concursos / Concursos no Brasil (agregadores de editais) | https://www.pciconcursos.com.br/ · https://www.concursosnobrasil.com.br/ | HTML; termos de uso não localizados (404) | republicam edital do órgão | — | ✘ (sem evidência) |
| **Tec Concursos** (agregador de questões — *não* é fonte) | https://www.tecconcursos.com.br/termos-de-uso | — | **proíbe expressamente** robôs, crawlers, scrapers e "ferramentas de inteligência artificial" para coleta/extração (Seção 18, 8.1) | — | ✔ `[fontes-provas-05]` |
| Qconcursos (idem) | https://www.qconcursos.com/termos-de-uso | 403 | cláusula anti-robô vista só em snippet | — | não verificado |

**Leitura.** Para o ENEM a fonte é perfeita em cobertura e péssima em licença: **ND** conflita com gerar questões e aulas *derivadas* das provas — aceitável apenas para citar/exibir a prova original com atribuição (P-13 jurídico). Para a OAB, é a melhor fonte primária aberta do país: 47 provas num único endpoint. Para concursos, **o Motor ainda não tem a URL da matéria-prima** — P-11 é bloqueante para a fatia 2 da Fase 5.

## 4. Fontes de conhecimento abertas por matéria

| fonte | URL | formato / detecção | licença | selo |
|---|---|---|---|---|
| **LexML** | https://www.lexml.gov.br/ · dados: https://projeto.lexml.gov.br/transparencia/dados-abertos | **API JSON** (`/apidata`) + **RSS (RDF 1.0)** por seção | **aberta (OKFN), com atribuição** — uso, reuso e redistribuição livres | ✔ `[fontes-conhecimento-01, -02]` |
| **Planalto — legislação (ccivil_03)** | https://www.planalto.gov.br/ccivil_03/ | HTML; RSS em `www4.planalto.gov.br/legislacao/rss` (snippet, não aberto) | texto de lei não é protegido (§9); **conexão recusada ao WebFetch em todas as tentativas** (bloqueio de bot?) | ✘ (sem evidência) |
| **STJ — Informativo e precedentes** | https://scon.stj.jus.br/jurisprudencia/externo/informativo/ · https://www.stj.jus.br/sites/portalp/Precedentes/informacoes-gerais/recursos-repetitivos | HTML + PDF/RTF anuais; **assinatura de notificação por e-mail**; periodicidade "periódica" (semanal, não confirmado) | conteúdo público; licença não explicitada | ✔ `[fontes-conhecimento-03, -08]` |
| **STF — informativos, súmulas, RG** | https://portal.stf.jus.br/jurisprudencia/ | WebFetch falhou (certificado/conexão) | não verificado | ✘ |
| **Câmara — Dados Abertos** | https://dadosabertos.camara.leg.br/swagger/api.html | **REST (JSON/XML)** + CSV/XLSX anuais; **maioria atualizada diariamente** | licença não explicitada na página (ver FAQ) | ✔ `[fontes-conhecimento-04]` |
| **Senado — Dados Abertos** | https://www12.senado.leg.br/dados-abertos | API | "licença que permita livre utilização", não nomeada | ✔ `[fontes-conhecimento-05]` |
| **SciELO** | https://www.scielo.org/pt-br/sobre-o-scielo/declaracao-de-acesso-aberto/ | HTML | **CC-BY 4.0** desde 2015 (inclusive comercial, com crédito) | ✔ `[fontes-conhecimento-06]` |
| Manual de Redação da Presidência (3ª ed., 2018) | https://www4.planalto.gov.br/centrodeestudos/assuntos/manual-de-redacao-da-presidencia-da-republica | PDF | não verificado | ✘ |

**Bibliografia de referência** (só como referência bibliográfica — nunca conteúdo ingerido, visão §4): Direito Constitucional — Pedro Lenza (*Esquematizado*) ✔; Direito Administrativo — Ricardo Alexandre (*Esquematizado*) ✔; os demais nomes listados pela fonte (Bernardo Gonçalves, Novelino, Nathalia Masson, Matheus Carvalho, Carvalho Filho, Harrison Leite, Piscitelli) **não foram verificados** `[fontes-conhecimento-07 ✔ parcial]` — fonte: https://www.joaolordelo.com/bibliografia-indicada . **Não pesquisado:** Português, Raciocínio Lógico, Informática, cartilhas TCU/CGU, Wikisource/domínio público.

## 5. Mapa de fontes do Motor — prioridade de integração

| # | fonte | por que primeiro | risco / o que falta |
|---|---|---|---|
| 1 | **LexML (API + RSS)** | única fonte de legislação com API documentada, RSS e licença aberta verificados; cobre leis, decretos, súmulas | contagem de ~1,2 M documentos e formato SRU não confirmados |
| 2 | **Planalto ccivil_03** | é a fonte canônica citada nas aulas (texto consolidado com redação vigente) | **bloqueou o fetch**; usar via LexML/cache e navegador; confirmar RSS |
| 3 | **STJ informativos + repetitivos** | jurisprudência recente é o que a Cebraspe cobra; assinatura por e-mail serve de gatilho de novidade | licença não explicitada; periodicidade a confirmar |
| 4 | **STF (informativos, súmulas, teses)** | idem, e súmulas superadas (ex.: 347) são pegadinha clássica | **não aberto** — P-15 |
| 5 | **Cebraspe — provas e gabaritos** | matéria-prima do DNA e das questões originais (exigência da usuária) | **URL, formato, termos: não medidos** — P-11 (bloqueante) |
| 6 | **FGV Conhecimento — provas** | idem para a segunda banca | idem — P-11 |
| 7 | **Câmara / Senado dados abertos** | tramitação e texto de normas novas, atualização diária | licença a confirmar no FAQ |
| 8 | **DOU** | editais e retificações (tela "Editais e radar") | API/RSS não verificados; alternativa: agregadores (termos não localizados) — P-15 |
| 9 | **OAB/FGV — 47 provas** | pronto para o adapter OAB (fase 2 do produto) | titularidade não confirmada |
| 10 | **INEP — ENEM** | pronto para o adapter ENEM | **CC BY-ND**: só exibição com atribuição, sem derivados — P-13 |
| 11 | SciELO | apoio para dossiês (CC-BY) | baixa relevância para concursos |

## 6. Concorrentes — Brasil

| produto | preço lido na página | IA declarada | onde é raso / reclamações | selo |
|---|---|---|---|---|
| **Estratégia Concursos** — https://www.estrategiaconcursos.com.br/assinaturas/ | Básica 1 ano 12× R$ 109,90–139,90 (R$ 1.186,92 à vista); Premium 1 ano 12× R$ 219,90–269,90 (R$ 2.374,92) | **"Questões comentadas por professores (não é IA!)"** — posiciona IA como inferior | app iOS **1,4/5** (376 avaliações): recursos faltando vs web, filtros quebrados `[mobile-03 ✔]`; Reclame Aqui: app não carrega >9 cadernos por anos (gap est-piloto-05) | n/v `[concorrentes-br-01]` |
| **Gran Cursos Online** — https://www.grancursosonline.com.br/assinaturas | Ilimitada 1 ano de 12× R$ 149,90 por **12× R$ 61,90**; 11 Pro 12× R$ 99,90; Vitalícia 12× R$ 154,90 | MAIA: recomenda cursos, audiobooks de PDF, comentários em questões (descrição via busca; Zendesk 403) | Reclame Aqui: **cronograma automático "que só atrapalha"** (reorganiza sozinho, marca concluído como pendente) — gap est-piloto-05 | ✔ preços `[mercado-08, -09]` |
| **Tec Concursos** — https://www.tecconcursos.com.br/assinar | Padrão **R$ 39,90/30 dias**; Avançado R$ 79,80 | "Comentário de IA": **5 por dia** no padrão; o avançado troca por professor em vídeo | IA tratada como versão limitada | n/v `[concorrentes-br-02]` |
| **Qconcursos** — https://www.qconcursos.com/planos-de-assinatura | **403** — snippet: Básico 12× R$ 19,90, Avançado 12× R$ 34,90 (não confirmado) | não medido | app iOS **4,9/5, 81 mil avaliações**, #33 educação `[mobile-01 ✔]`; Reclame Aqui: cancelamento difícil (est-piloto-04) | não medido |
| **Aprova Concursos (Questões+)** — https://www.aprovaconcursos.com.br/questoes-de-concurso-mais/planos | Mensal R$ 14,90; anual **R$ 99,90** | nenhuma | 270 mil questões | n/v |
| **MisterConcursos** — https://misterconcursos.com/ | Mensal R$ 49,90 (promo R$ 24,90); anual R$ 249,90 promo | lê edital em 60 s → cronograma até a prova, flashcards, simulados adaptativos, **"previsão de aprovação (estimativa, não garantia)"**; alega 58 mil alunos e 2.800 aprovações | não medido | n/v `[concorrentes-br-03, -04]` |
| **Concursa.ai** — https://www.concursa.ai/ | Grátis (5 questões/dia); Early Access R$ 29,90 vitalício (500 primeiros); Aspirante R$ 49,90 | cronograma pelo que mais cai **e reajusta quando você perde um dia**; tutor 24/7 citando lei/súmula; simulado adaptativo | não medido | n/v |
| **Clipping.ai** — https://clipping.ai/ | plano único **R$ 99/mês** | questões infinitas "no estilo de cada banca" a partir do edital colado, flashcards, redação, chatbot; 30 mil alunos em 100+ concursos | Reclame Aqui (marca correlata "Clipping CACD"): "uso excessivo de IA", material insuficiente — não aberto | n/v |
| GoConcursos, EstudaIA, AprovaIA | domínio vazio / DNS não resolve / SSL inválido | — | não são produtos vivos verificáveis | n/v `[concorrentes-br-05]` |

**Leitura.** (a) Os incumbentes **vendem conteúdo humano** e tratam IA como acessório barato; (b) os IA-first **vendem o cronograma do edital** por R$ 25–50 e já usam a palavra "previsão"; (c) **ninguém** mostrou validação de conteúdo com fonte, revisão espaçada integrada ao plano, padrões de erro com suporte estatístico, ou explicação de cada decisão. É exatamente o espaço da visão §1 — mas o *pitch* "lê o edital e monta o plano" não pode ser o nosso, porque é o deles. **Reclamações 1–2★ e "onde a IA é rasa" não foram coletadas** para nenhum concorrente (orçamento) — P-14.

## 7. Concorrentes — globais

| produto | preço | o que a IA faz | selo |
|---|---|---|---|
| **Khanmigo** — https://www.khanmigo.ai/pricing | **US$ 4/mês ou US$ 44/ano**; grátis para professores | tutor socrático (pergunta, guia, não dá a resposta) — proativo | ✔ `[concorrentes-global-01]` |
| **Magoosh (GRE)** — https://gre.magoosh.com/pricing | Premium 1 mês US$ 149 (promo US$ 104,30) | corrige redação "como um avaliador do GRE"; cronogramas de 1 semana a 6 meses — reajuste diário não confirmado | ✔ `[concorrentes-global-02]` |
| Quizlet Q-Chat, UWorld, Speak, Duolingo Max, Brainly, StudyFetch, Turbo.ai, Knowunity | **8 de 10 páginas oficiais não abriram** (403/404); preços só em terceiros | UWorld: sem tutor de IA nem plano diário (terceiros); Turbo.ai: gera material, não tutora; Knowunity: tutor "para 1 bilhão" é promessa de rodada (€27 M) | n/v `[concorrentes-global-03, -04]` |

**Leitura.** **Nenhuma fonte primária aberta confirmou "previsão de nota" como funcionalidade divulgada em concorrente global** `[concorrentes-global-04]`. Tutor proativo existe (Khanmigo) a US$ 4/mês — o preço de referência global de "IA que ensina" é baixo; o que sustenta preço alto (Magoosh, UWorld) é **conteúdo de prova de alto risco**, não a IA. Isso reforça: cobrar pelo *resultado acompanhado* e pela *base validada por banca*, não pelo chat.

## 8. SEO — palavras-chave e quem ranqueia

Volumes **não medidos** (Ahrefs free deu 404; Keyword Planner exige login — o dono mede, P-12). O que a rodada mostrou `[seo-01…05, 37 termos em raw]`:
- **Cabeças** ("como estudar para concurso", "plano de estudos para concurso", "questões cebraspe"): KD alta, top 3 de Estratégia, CEISC, Nova Concursos.
- **"Como a banca X cobra Y"** (Cebraspe/FGV × matéria): top 3 de portais/cursinhos (Radar de Concursos, Direção, Tec, Folha Dirigida) — **nicho de conteúdo editorial, não de produto**. Cauda longa com KD baixa: "assuntos mais cobrados fgv direito administrativo", "tópicos mais cobrados receita federal fgv", "quantas questões tem a prova cebraspe". **Oportunidade programática:** uma página por banca × matéria × tópico gerada do DNA (com fonte), que é o que ninguém mais tem em escala.
- **"Edital verticalizado"**: já existe ferramenta **gratuita e sem cadastro** com ciclos 24h/7d/30d (Deltinha, 429 ao abrir) `[seo-03]` — a funcionalidade isolada não diferencia (mas a usuária a exige como básico).
- **ENEM**: "simulado enem online gratuito" saturado por portais grandes `[seo-04]` — KD alta.
- **OAB**: "quantas questões precisa acertar na oab" (40/80) é gancho de *featured snippet* `[seo-05]`.

## 9. Quadro jurídico

| ponto | o que diz | selo | fonte |
|---|---|---|---|
| Texto de lei, decreto, decisão judicial e ato oficial **não é protegido** por direito autoral | Lei 9.610/1998, art. 8º, IV | ✔ (espelho; Planalto recusou conexão) `[regulatorio-01, -02]` | https://modeloinicial.com.br/lei/L-9610-1998/lei-direitos-autorais/art-8 |
| **Questões de prova, "singularmente consideradas", não têm proteção como direito de autor** (falta de originalidade) | TJ-SP, Apelação 1112376-68.2021.8.26.0100 | ✔ SEC (IDS reproduzindo o acórdão; acórdão não aberto) `[regulatorio-03]` | https://ids.org.br/noticia/segundo-tjsp-questoes-de-prova-nao-estao-sujeitas-por-si-so-a-protecao-por-direito-autoral/ |
| **Regime de pequeno porte (LGPD)**: ME, EPP e startups; **dispensa de encarregado (DPO)**, registro simplificado, **prazo em dobro** para titulares e incidentes | Resolução CD/ANPD nº 2/2022 | ✔ oficial (URL corrigida) `[regulatorio-04…06]` | https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-2-de-27-de-janeiro-de-2022 |
| ENEM: licença **CC BY-ND** | proíbe derivados | ✔ `[fontes-provas-01]` | (§3) |
| Termos de uso de Cebraspe, FGV, INEP sobre reprodução | **não localizados / não abertos** | — | P-13 |
| LGPD art. 5º, II (dado sensível) × humor/energia/rotina | **não lido literalmente**; o rol (saúde, vida sexual, genético, biométrico, origem, convicção) não cita "humor", mas "energia/sono" tangencia **saúde** | — | P-13 → `RISCOS.md` com consentimento separado e minimização (visão §10) |
| Usar o nome da banca ("no padrão Cebraspe") — marca/INPI, concorrência desleal | **não pesquisado** | — | P-13 |

## 10. Mobile — evidência e recomendação

| fato | número | selo | fonte |
|---|---|---|---|
| Usuários de internet que acessam **só pelo celular** | **58 %** (geral); **87 %** classes DE; mulheres 64 %, homens 52 %; pretos 64 %, pardos 63 %, brancos 49 % | ✔ oficial `[mobile-05, -06]` | https://cetic.br/pt/noticia/classes-c-e-de-impulsionam-crescimento-da-conectividade-a-internet-nos-lares-brasileiros-mostra-tic-domicilios-2023/ |
| Qconcursos iOS | 4,9/5 · **81 mil** avaliações · #33 educação · compras R$ 29,90–494,90 | ✔ `[mobile-01]` | https://apps.apple.com/br/app/qconcursos/id1470271696 |
| Gran Cursos iOS | 4,7/5 · 12 mil · #50 | ✔ `[mobile-02]` | https://apps.apple.com/br/app/gran-cursos-online/id1198315819 |
| Estratégia Concursos iOS | **1,4/5** · 376 · recursos faltando vs web, filtros não funcionam | ✔ `[mobile-03]` | https://apps.apple.com/br/app/estrat%C3%A9gia-concursos/id1527416954 |
| **Web Push no iOS** | desde **iOS/iPadOS 16.4**, **só para web app instalada na Tela de Início** | ✔ oficial WebKit `[mobile-07]` | https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/ |
| Google Play (downloads, 1–2★) | **não medido** — fichas não abriram | `[mobile-04]` | P-14 |
| Hábito "estudo para concurso no celular" (survey) | **não encontrado** | — | P-14 |

**Recomendação: web responsiva + PWA instalável com push para o check-in.** Justificativa: (1) o celular é o único acesso de 58 % dos usuários — a web *tem* de funcionar bem no celular, e a PWA cobre push (iOS 16.4+) e offline sem segunda base de código; (2) app nativo com poucas horas por semana vira o app do Estratégia (1,4★) — pior que não ter; (3) a única usuária entrevistada estuda no notebook em bloco fixo (n=1); (4) a fábrica veta app em loja por custo de manutenção (`comp1-12`). **Gatilho de revisão** (para a ADR da Fase 3): quando houver ≥ 500 usuários ativos, medir D30 com e sem push instalado; se a PWA instalada não retiver melhor e o suporte a push no iOS for a barreira principal, reavaliar Capacitor.

## 11. Gaps do ramo de estudos (script da fábrica) que tocam o produto

| gap | evidência | o que o AprovaOS faz com isso |
|---|---|---|
| **Anki/repetição espaçada: criar cartões cansa mais que estudar; configuração afasta** (est-piloto-01) | TabNews, Trustpilot Anki, KardsAI | **Converge com a Linda** ("cansa criar"; "nunca tentei nada estruturado"): cartão automático a partir de questão errada e agenda FSRS invisível (RF-13) são a cunha de memória |
| **Cronograma automático que "só atrapalha"** (Gran; est-piloto-05) | Reclame Aqui | O plano tem de ser explicável, reversível (pular/desfazer) e nunca marcar concluído o que o aluno não fez — regra de produto |
| **Cancelamento difícil e cobrança após cancelar** (Estratégia, Qconcursos, Revisely; est-piloto-04) | Reclame Aqui, Trustpilot | Cancelar em um clique já é regra (spec §3); vira argumento de landing |
| **Paywall depois de o usuário investir tempo** (RemNote, Revisely; est-piloto-06) | Trustpilot | O Free não encolhe depois; no limite, degrada o modelo, não some (spec §3) |
| Correção de redação ENEM em massa é trabalho manual a R$ 3–20/redação (est-piloto-02) | Freelancer, VintePila, Sólides | Demanda real para o **lado B** (corretor em lote), fase 2 do produto |
| TCC (est-piloto-03) | Reddit, TCC Solutions | Fora de escopo |

A **consolidação cruzada** dos seis nichos (`consolida:cross-nicho`) foi o agente que o reboot matou; os seis consolidados por nicho estão em raw (`monta__est-*.json`). É entregável da fábrica (P-14 de lá), não deste repo.

## 12. Recomendação de exame inicial — com números

| critério | **Concursos Cebraspe + FGV** | **ENEM** | **OAB (FGV)** |
|---|---|---|---|
| público anual | CNU 761 mil inscritos (um concurso); universo total **não medido** (dezenas de editais ativos só na Cebraspe) | **4,81 M** inscritos confirmados | ~130 mil por edição × 3/ano ≈ **~400 mil** inscrições/ano; 14 % de aprovação |
| provas públicas abertas | **não medido** (sites JS; P-11) | 28 anos, PDF, **CC BY-ND** (sem derivados) | **47 edições** num endpoint, termos não localizados |
| padrão de banca | Cebraspe: C/E com anulação (variável por edital) — muito marcado; FGV: não confirmado | uma "banca" (INEP), TRI, 180 itens | uma banca (FGV), 80 questões, corte 40 |
| sazonalidade | **contínua**: editais o ano inteiro | **um pico** (nov) — 11 meses de vale | 3 picos/ano |
| fontes abertas para as matérias | **excelentes**: LexML (API, RSS, licença aberta), STJ, Câmara/Senado; Planalto a resolver | conteúdo escolar amplo; SciELO pouco útil; sem "lei" a monitorar | as mesmas de concursos (direito) |
| disposição a pagar (preços lidos) | **alta**: Gran R$ 744/ano; Estratégia R$ 1.187–2.375/ano; Tec R$ 39,90/30d; IA-first R$ 25–50/mês | não medido; simulados grátis saturam o SEO | não medido |
| concorrência | incumbentes com IA rasa; **IA-first já vende "edital → cronograma"** | portais grátis, KD alta | cursinhos OAB; não mapeado |
| pontos contra | matéria-prima (provas) ainda não mapeada; concorrência IA-first no pitch de cronograma; universo total não dimensionado | licença ND; sazonal; público de menor renda (classes DE 87 % só celular); SEO saturado | público menor; uma prova só limita o "agente diário" a ciclos de 4 meses |
| fit com a persona entrevistada | **sim** (A1) | não | parcial |

**Recomendação: concursos com Cebraspe + FGV**, com dois adendos que a hipótese não tinha:
1. **Justificativa numérica que sustenta:** calendário contínuo (visão §5 exige plano *diário* o ano todo — só concursos oferecem isso), maior WTP medida do segmento (assinaturas de R$ 744 a R$ 2.375/ano contra IA-first a R$ 300–600/ano — há espaço para R$ 49–59/mês), e fontes abertas de legislação com API e licença verificadas cobrindo Direito Constitucional/Administrativo/AFO, que são metade do peso de um edital típico. O ENEM ganharia só por público, e perde em licença (ND), sazonalidade e SEO. A OAB **é o segundo adapter natural** (mesma banca FGV, 47 provas prontas, 3 ciclos/ano) — antes do ENEM.
2. **Condição:** a recomendação fica **provisória até P-11** (mapear as provas da Cebraspe e da FGV com navegador). Se as provas não estiverem acessíveis de forma coletável ou os termos proibirem reprodução, o exame inicial troca para **OAB** (fonte primária aberta, banca única), não para ENEM.

**Fatos não sustentados que pesariam se fossem verdadeiros:** FGV com microsites de provas por edital (`bancas-05/-11 ✘` — se verdadeiro, a coleta é mais fácil); Estratégia com 1 M de instalações (`mobile-09 ✘`); contagens de concursos por banca (583/474/147, só snippet); DOU com API restrita (só snippet — se verdadeiro, o radar de editais depende de agregadores).

## 13. O que faltou medir (vai para `PENDENCIAS.md`)
- **P-11** (bloqueante para Fase 3/5): mapear com navegador a seção de provas e gabaritos de Cebraspe e FGV — URL, formato, anos, volume, termos de uso, sitemap/RSS; confirmar formato de questão FGV.
- **P-12**: volumes de busca dos 37 termos no Keyword Planner (dono).
- **P-13** (→ `RISCOS.md`): LGPD art. 5º, II literal; art. 46 da Lei 9.610; termos de uso Cebraspe/FGV/INEP; marca da banca no INPI; o que a licença ND do INEP permite.
- **P-14**: reclamações 1–2★ (Google Play, App Store, Capterra) dos concorrentes e "onde a IA é rasa"; preço do Qconcursos; universo de concurseiros ativos e gasto médio; survey de estudo no celular.
- **P-15**: Planalto RSS, STF RSS/API, DOU API — confirmar com navegador; licença dos dados abertos da Câmara/Senado.
- **P-16**: consolidação cruzada dos gaps (fábrica) não rodou; relançar do lado da fábrica com os seis `monta__est-*.json` como entrada.

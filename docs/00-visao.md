# Visão do AprovaOS
> O que é: a tese do produto, os dois lados, o moat, a cunha do MVP, o que fica fora, a regra de corte e as métricas-norte — com as decisões do dono da Fase 0 (14/09/2026). Quando ler: antes de propor qualquer funcionalidade, fase ou corte de escopo; é o documento que decide o que entra.

Fonte primária: `SPEC-aprovaos.md` (v0.1, do fundador). Este arquivo não repete a spec — resume a tese e **fixa o que a Fase 0 decidiu**. Onde a spec diz `[ADR]`, a decisão está (ou vai estar) em `docs/DECISOES.md`; onde diz `[PESQUISA]`, depende de `docs/01-pesquisa-mercado.md` (Fase 1).
"AprovaOS" é **codinome**: o nome comercial sai de um trabalho de naming/branding (P-01).

## 1. Tese em uma frase
Um agente de IA que **assume a responsabilidade** pela aprovação do candidato: monta, executa e reajusta o estudo todos os dias, com conteúdo gerado de fontes verificadas e do padrão real da banca — e mede se está funcionando.

O mercado (Qconcursos, Gran, Estratégia, TEC, Concursa AI, EstudaIA, GoConcursos, ChatGPT solto) opera em "você pede → a IA responde". O AprovaOS inverte: o agente tem um objetivo, age antes de ser pedido e explica cada decisão. **Concorrente vende ferramenta; nós vendemos resultado acompanhado.** (Afirmações sobre concorrentes são hipóteses até a Fase 1 trazer preço, funcionalidades e reclamações com URL.)

## 2. Dois lados
| lado | quem | paga por | quando entra |
|---|---|---|---|
| **A — quem estuda** | concurseiro que trabalha (A1) e em dedicação total (A2); depois ENEM (A3), OAB/residência/certificações (A4) | assinatura pelo agente (Free / Pro R$ 39–59 / Elite R$ 149+, hipóteses a validar) | **MVP** (A1 + A2, um exame) |
| **B — quem ensina** | professor autônomo/criador (B1), cursinho pequeno/coordenador (B2) | ferramentas por assento (gerador, corretor em lote, trilha própria), marketplace com revenue share, white-label por aluno ativo | fase 2 do produto, depois de tração no lado A |

O lado B alimenta a base que o lado A consome — é o efeito de rede. Mas **o produto não pode depender de professor para nascer**: o Motor de Conhecimento (spec §8) enche a base sozinho a partir de fontes oficiais e públicas.

## 3. Moat — o que acumula com o uso
1. **Dados longitudinais de estudo por candidato** (`EventoEstudo` append-only: cada resposta com tempo, horário, energia declarada — não só acerto/erro).
2. **DNA por banca/concurso** refinado pelo uso real (o `calibrador` corrige peso, dificuldade e discriminação com o que os alunos fazem).
3. **Base própria** de questões, dossiês e aulas, validada, versionada e recalibrada.
4. **Rede professor ↔ aluno** (fase 2).

O que impede o Qconcursos de copiar em 6 meses não é o agente (copiável) — é que os ativos 1–3 só existem com **tempo de uso** e com um pipeline de qualidade que a maioria não tem incentivo de montar (o modelo deles é banco de questões, não responsabilidade pelo resultado). Consequência de projeto: **o MVP já grava tudo como evento e já calibra**, mesmo antes de a previsão v1 existir.

## 4. Princípios de produto (inegociáveis)
- O agente decide; o aluno discorda em um toque. Nunca esconder o porquê de uma decisão.
- Nada gerado existe para o aluno sem validação. Toda afirmação de lei/jurisprudência tem fonte.
- Previsão sempre com intervalo e nível de confiança. Nunca prometer o que não se mede.
- Descansar é uma recomendação válida.
- Web primeiro. App só com evidência.
- Livros, apostilas e cursos de terceiros são **referência bibliográfica**, nunca conteúdo ingerido.

## 5. Cunha do MVP — lado A, um exame
Hipótese de trabalho fixada na Fase 0 (**decisão do dono, 14/09/2026**): **concursos públicos, bancas Cebraspe + FGV**. A Fase 1 confirma ou troca com números (volume de provas públicas, padrão de banca, calendário de 12 meses, tamanho do público); a decisão final é do dono no portão da Fase 1.

Cinco funcionalidades, na ordem em que o aluno as encontra:
1. **Onboarding → DNA do concurso** (escolhe do catálogo ou sobe edital; DNA pré-gerado pelo Motor).
2. **Diagnóstico**: simulado adaptativo ≤ 30 questões + questionário de rotina/tempo/energia/data-alvo.
3. **Plano de hoje**: gerado à noite, reajustado no check-in matinal; pode recomendar descanso.
4. **Aula do dia** (texto + áudio + versão leiga) + **questões no padrão da banca** com justificativa + **revisão espaçada** (FSRS).
5. **Painel**: curva atual vs. necessária, padrões de erro, previsão v0 com intervalo.

Mais **billing Free/Pro com limites por tier** (não é funcionalidade do aluno, é condição de lançamento: preço e botão de pagar no dia 1, com Pix).

Por trás, sem UI: o **Motor de Conhecimento v0** (coletor → curador → analista-de-edital → pesquisador-de-tópico → preenchedor → gerador → validador → calibrador), que é o que torna as 5 funcionalidades possíveis sem professor.

## 6. O que NÃO entra no MVP
| fica de fora | volta quando |
|---|---|
| Lado B inteiro (corretor em lote, gerador para professor, trilha própria, dashboard de turma) | fase 2, após tração no lado A |
| Segundo exame (ENEM, OAB…) | fase 2, como adapter — nunca refatoração |
| Social (batalhas, grupos, ranking), marketplace, white-label | fase 3 |
| Integrações (Google Calendar, Anki, Notion, Qconcursos) | fase 3 |
| App nas lojas | só com evidência de retenção da Fase 1/3 (seção 8) |
| Mentor humano (tier Elite) | fase 3 |
| Semana da prova "avançada" (gestão de ansiedade, sono) | fase 3; no MVP só o modo básico (revisão cirúrgica + geração desligada) |
| Previsão v1 com dados longitudinais próprios | quando houver n suficiente; v0 é honesta e mostra o intervalo |
| Boleto | fora (0,9 % do e-commerce brasileiro e caindo — evidência `comp2-08` da fábrica) |

**Fora de escopo para sempre:** ingerir/reproduzir material de terceiros; prometer aprovação; diagnóstico psicológico; venda de dados.

## 7. Restrições fixadas na Fase 0 (respostas do dono, 14/09/2026)
| tema | decisão | efeito |
|---|---|---|
| Exame inicial | Concursos Cebraspe + FGV como hipótese; Fase 1 confirma | adapter `concursos/` é o primeiro; Fase 1 pesquisa bancas e fontes desse exame primeiro |
| Front web | decidir na Fase 3 por ADR (Next.js × SvelteKit × HTMX + Jinja) | critério: SEO + velocidade de desenvolvimento por IA + poucas horas do dono |
| Mobile | web/PWA primeiro; app só com evidência | Fase 1 levanta evidência; Fase 3 decide entre PWA com push, Capacitor ou nativo, com gatilho de revisão |
| Gateway | decidir na Fase 3, depois do estudo de cobrança sem CNPJ (P-02) | Pix no dia 1 é fixo; Asaas × Mercado Pago (PF) × Stripe comparados com o estudo na mão |
| Orçamento | **R$ 100/mês** para infra + LLM, o mesmo teto da fábrica | o Motor roda em lotes pequenos, com cache por concurso/tópico e modelos baratos; `docs/06-custos.md` (Fase 3) tem de provar que o lote noturno do exame inicial cabe — se não couber, o escopo do Motor encolhe, não o teto |
| Nome/domínio | sem nome fixo; trabalho de naming/branding antes de landing | "AprovaOS" é codinome (P-01) |
| Regra de corte e metas | spec §15 como está | seção 9 abaixo |
| Herança da fábrica | herdar tudo que existir, por referência de caminho | seção 10 |

## 8. Posição sobre app mobile
Hipótese, não requisito. A web é o canal principal (SEO, conversão, lado B). A fábrica veta app em loja para micro-SaaS (relógio de 2 anos de target API do Google Play — evidência `comp1-12`); o AprovaOS só sai da web se a Fase 1 mostrar que o concurseiro estuda no celular **e** que o app entrega algo que a PWA não entrega (push para o check-in diário e offline são entregáveis por PWA). Decisão formal na Fase 3, com gatilho de revisão (ex.: X usuários ativos, retenção D30 medida com e sem push).

## 9. Regra de corte e métricas-norte (spec §15, aceita pelo dono em 14/09/2026)
Números fixados **antes** de lançar — regra da fábrica (`~/PycharmProjects/fabrica-saas/docs/00-visao.md` §5: sem número e data fixados, o produto arrasta 18 meses).

| métrica | alvo MVP (30 dias após lançamento público) |
|---|---|
| Ativação (diagnóstico concluído / cadastro) | ≥ 60 % |
| Conclusão do plano diário | ≥ 50 % dos dias ativos |
| Sessões por semana por usuário ativo | ≥ 4 (derivada: o plano é diário; abaixo disso o agente não está "carregando" o aluno) |
| Retenção D7 / D30 | ≥ 40 % / ≥ 20 % |
| Conversão Free → Pro | ≥ 3 % |
| Custo LLM / usuário Pro / mês | ≤ 25 % do preço |
| Taxa de reporte de erro por questão | < 2 % |
| NPS após 14 dias | ≥ 40 |

Referências da fábrica para ler esses números (evidências com URL em `~/PycharmProjects/fabrica-saas/docs/evidencias/2026-09-14-regra-de-corte.md`): retenção de 1 mês em PLG 48,4 % e ativação 34,6 % (`churn-03`); free→pago mediana 8 %, quartil inferior 2,5 % (`trial-02`, `trial-03`); churn mensal de ticket baixo 6,1–6,5 % (`churn-01`). A meta de D30 ≥ 20 % é **abaixo** da mediana PLG de propósito: é o mínimo para não pivotar, não o alvo de sucesso.

**Portões:**
- **D+30:** < 30 pagantes **e** D30 < 15 % → **pivotar** exame/persona (não arquiva ainda). Se ≥ 30 pagantes ou D30 ≥ 15 %, segue.
- **D+60 (2ª cobrança):** sem tração (pagantes não crescendo e renovação < 50 %, referência `comp1-02` da fábrica) → **arquivar**; com tração → mantido.
- Antes de qualquer arquivamento por churn: separar churn involuntário, retentativa de 10 dias, oferecer Pix Automático (regra 5.3 da fábrica).
- D+30 **não** mede SEO (só 1,74 % das páginas novas chegam ao top 10 em um ano, `seo-01`).

## 10. Relação com a fábrica (`~/PycharmProjects/fabrica-saas`)
O AprovaOS é um SaaS da fábrica **fora do funil**: entrou por decisão do dono (14/09/2026) com spec própria, sem passar pela avaliação da Fase 2 da fábrica. O que isso implica, sem esconder:
- **Vetos da fábrica que o AprovaOS toca** (visão da fábrica §4.5): dado sensível (humor/energia → LGPD sem regime simplificado), B2C de ticket baixo (assinatura R$ 39–59 com churn esperado de 6 %/mês), app em loja (evitado pela seção 8). São **riscos assumidos**, tratados em `docs/RISCOS.md` (Fase 3), não motivos de reprovação — a decisão de entrar já foi tomada.
- **Limite de WIP da fábrica** (1 produto em validação/mvp/lançado): o AprovaOS ocupa essa vaga quando sair de `ideia`.
- **Herdado por referência** (nunca copiado): regras de trabalho e ADRs da fábrica (`docs/DECISOES.md` de lá), evidências da regra de corte, `docs/00-visao.md` §7 (Brasil: Pix, gateways, LGPD, CNPJ), pendência P-13 (cobrar sem CNPJ). Skills, agents e `template-saas/` da fábrica ainda **não existem** (pastas vazias em 14/09/2026): o que o AprovaOS criar primeiro pode ser absorvido pela fábrica depois.
- **Fase 1 compartilhada:** a fábrica decidiu focar a própria pesquisa no ramo de estudos (ADR-0027 de lá). A Fase 1 do AprovaOS **reaproveita** `docs/01-pesquisa-mercado.md` da fábrica quando existir e acrescenta os ângulos específicos do produto (bancas, fontes de provas e de conhecimento, mapa de fontes do Motor, evidência mobile). Ver ADR-0006 deste repo.

## 11. Roadmap (fases do `PROMPT-aprovaos.md`)
0 Setup e visão (esta) → 1 Deep research → 2 PRD → 3 Arquitetura e dados → 4 Skills e subagents → 5 MVP em fatias verticais (13 fatias, spec §17) → 6 Landing, SEO e lançamento → 7 Handoff. Uma fase por vez; a seguinte só começa com confirmação do dono.

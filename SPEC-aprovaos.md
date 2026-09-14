# SPEC — AprovaOS
Especificação do produto e da arquitetura. Ler antes de qualquer fase do `PROMPT-aprovaos.md`; o prompt diz *como trabalhar*, esta spec diz *o que construir*.
Status: v0.1 (rascunho do fundador). Itens marcados `[ADR]` são decisões que o Claude Code fecha em `docs/DECISOES.md`; itens `[PESQUISA]` dependem da Fase 1.

---

## 1. Visão

**Uma frase.** Um agente de IA que assume a responsabilidade pela sua aprovação: monta, executa e reajusta seu estudo todos os dias, com conteúdo gerado a partir de fontes verificadas e do padrão real da banca.

**Tese.** O mercado funciona no modo "você pede → a IA responde". O AprovaOS inverte: o agente tem um objetivo (aprovar você), age proativamente e mede se está funcionando. O concorrente vende ferramenta; nós vendemos resultado acompanhado.

**Moat (o que acumula com o uso).**
1. Dados longitudinais de estudo por candidato (eventos, não só acertos).
2. DNA por banca/concurso refinado pelo uso real.
3. Base própria de questões, dossiês e aulas, validada e calibrada.
4. Rede professor ↔ aluno (fase 2).

**Princípios de produto.**
- O agente decide; o aluno pode discordar em um toque. Nunca esconder o porquê de uma decisão.
- Nada gerado existe pro aluno sem passar por validação. Toda afirmação de lei/jurisprudência tem fonte.
- Previsão sempre com intervalo. Nunca prometer o que não se mede.
- Descansar é uma recomendação válida.
- Web primeiro. App só com evidência.

## 2. Público e personas

| ID | Persona | Dor principal | Paga por |
|---|---|---|---|
| A1 | Concurseiro que trabalha (25–40 anos, 1–3 h/dia) | Não sabe o que estudar hoje; estuda o que gosta, não o que cai | Direção diária + material denso |
| A2 | Concurseiro em dedicação total | Platô; não sabe se está na curva de aprovação | Previsão, padrões de erro, semana da prova |
| A3 | Estudante ENEM/vestibular | Volume enorme, sem método | Trilha + questões no padrão INEP |
| A4 | OAB / residência / certificações | Prova única com padrão fixo | DNA da banca + discursivas |
| B1 | Professor autônomo / criador | Produzir material e corrigir discursiva consome o tempo todo | Gerador + corretor em lote + publicar trilha |
| B2 | Cursinho pequeno / coordenador | Não sabe quem vai reprovar até reprovar | Dashboard de risco por aluno, white-label |

MVP atende **A1 e A2** em um exame `[PESQUISA]` (hipótese: concursos, bancas Cebraspe + FGV). A3/A4 entram como adapters. B1/B2 na fase 2.

## 3. Modelo de negócio

**Lado A (aluno)**
| Tier | Preço (hipótese, validar) | O que libera | Orçamento LLM/mês |
|---|---|---|---|
| Free | R$ 0 | Diagnóstico, DNA de 1 concurso, plano básico, 20 questões/dia | baixo, modelo barato |
| Pro | R$ 39–59/mês | Agente completo, geração ilimitada com fair use, aulas em áudio, semana da prova | médio |
| Elite | R$ 149+/mês | Pro + mentor humano (fase 3) + análise profunda mensal | alto |

**Lado B (professor/cursinho) — fase 2**
- Ferramentas: assinatura por assento (gerador, corretor em lote, trilha própria).
- Marketplace: conteúdo publicado e validado ganha revenue share por uso.
- White-label/B2B: por aluno ativo/mês + setup.

**Regras.** Pix, boleto e cartão. Anual com desconto. Cancelamento em um clique. Limite de tokens por tier aplicado no roteador, nunca "acabou seu crédito" no meio de uma sessão de estudo (degrada pra modelo barato).

## 4. Escopo

### 4.1 MVP (cunha) — lado A, um exame
1. Onboarding: escolher concurso (ou subir edital) → DNA do concurso pronto (pré-gerado pelo Motor).
2. Diagnóstico: simulado adaptativo (20–30 questões) + questionário de rotina/tempo/energia/histórico.
3. Plano de hoje: gerado à noite, reajustado no check-in matinal; blocos de estudo com aula + questões + revisão.
4. Aula do dia (texto + áudio) + questões no padrão da banca com justificativa + revisão espaçada (FSRS).
5. Painel: curva atual vs. necessária, padrões de erro, previsão v0 com intervalo.
6. Billing (Free/Pro), limites por tier.

### 4.2 Fase 2 — lado B mínimo + adapters
Corretor de discursivas em lote, gerador de questões pra professor, publicação de trilha própria, dashboard de risco por turma. Segundo adapter de exame (ENEM ou OAB, `[PESQUISA]`).

### 4.3 Fase 3
Social (batalhas, grupos, ranking de eficiência), marketplace com revenue share, white-label, integrações (Google Calendar, Anki, Notion), semana da prova avançada, pós-aprovação, escada de concursos, mentor humano, app mobile se aprovado.

### 4.4 Fora de escopo (sempre)
Ingerir ou reproduzir livros, apostilas ou cursos de terceiros. Prometer aprovação. Diagnóstico psicológico. Venda de dados.

## 5. Requisitos funcionais

Formato: `RF-xx` — descrição — critério de aceite (CA).

### Épico E1 — Concurso e DNA
- RF-01 Selecionar concurso de catálogo ativo. CA: lista filtrável por banca/órgão/área; concurso mostra data da prova, matérias e peso.
- RF-02 Subir edital em PDF para concurso fora do catálogo. CA: em até 10 min o DNA está disponível ou o usuário é avisado de falha com motivo.
- RF-03 DNA do concurso: peso real por matéria/tópico, incidência histórica por prova, estilo da banca, pegadinhas típicas, nota de corte histórica. CA: cada afirmação tem fonte (prova/ano ou edital); formato fixo `DnaConcurso`.

### Épico E2 — Diagnóstico e perfil
- RF-04 Simulado adaptativo inicial (TRI ou proxy `[ADR]`). CA: termina em ≤ 30 questões; produz proficiência por matéria com incerteza.
- RF-05 Questionário: horas/dia por dia da semana, horário preferido, energia típica, histórico de estudo, data-alvo. CA: editável depois; muda o plano no dia seguinte.
- RF-06 Perfil de estudo versionado. CA: toda mudança gera evento; plano lê sempre a última versão.

### Épico E3 — Plano vivo
- RF-07 Job noturno gera o plano do dia seguinte por usuário ativo. CA: roda até 05h local; falha em um usuário não derruba o lote; plano tem justificativa legível ("hoje X porque seu erro em Y subiu e Y pesa 18%").
- RF-08 Check-in matinal (humor/energia/tempo real disponível) reajusta o plano. CA: reajuste em < 5 s; pode recomendar descanso.
- RF-09 Aluno pode pular/trocar bloco. CA: registra evento; não quebra o plano; agente explica impacto.
- RF-10 Alerta proativo quando abaixo da curva. CA: no máximo 1 alerta/dia; sempre com ajuste concreto proposto.

### Épico E4 — Conteúdo
- RF-11 Questões no padrão da banca com justificativa por alternativa. CA: servidas da base validada; nunca geradas na hora sem validação; taxa de reporte de erro < 2% por questão.
- RF-12 Aula do dia em texto denso + áudio + versão leiga. CA: derivada de dossiê; citações visíveis; regenerada quando dossiê muda.
- RF-13 Flashcards com FSRS. CA: agenda de revisão persiste; card criado de qualquer questão errada em um toque.
- RF-14 Resumo ultra-denso por tópico. CA: ≤ 1 tela; fontes.
- RF-15 Reportar erro em qualquer conteúdo. CA: entra na fila do `calibrador`; usuário vê status.

### Épico E5 — Monitoramento e previsão
- RF-16 Painel: curva atual vs. curva necessária até a prova. CA: recalculada por evento.
- RF-17 Padrões de erro cruzando tópico × banca × horário × energia. CA: só mostra padrão com suporte estatístico mínimo (definir n).
- RF-18 Previsão de nota e probabilidade de aprovação com intervalo. CA: v0 = proficiência × peso × corte histórico; mostra "confiança baixa/média/alta".
- RF-19 Modo semana da prova (MVP: básico). CA: plano muda pra revisão cirúrgica + descanso; desliga geração de conteúdo novo.

### Épico E6 — Conta, tenant, billing
- RF-20 Cadastro/login (e-mail + senha, Google). RF-21 Tenant por pessoa física e por organização. RF-22 Free/Pro com Pix, boleto e cartão; upgrade/downgrade/cancelamento self-service. RF-23 Exportar e excluir todos os meus dados (LGPD).

### Épico E7 — Motor de Conhecimento (interno, sem UI no MVP)
- RF-24 Coletor monitora fontes configuradas e detecta novidade (edital, prova, gabarito, lei, jurisprudência). CA: fonte nova adicionada por arquivo de config; teste de detecção.
- RF-25 Curador: PDF → questões classificadas (banca, ano, órgão, matéria, tópico, dificuldade) → dedup → vetor. CA: precisão de classificação ≥ 90% em amostra rotulada.
- RF-26 Pesquisador de tópico: deep research → `DossieTopico` versionado com fontes e bibliografia. CA: só fontes permitidas; log de buscas reproduzível.
- RF-27 Preenchedor: cobertura da base vs. DNA → encomenda geração em lote. CA: relatório de cobertura por tópico.
- RF-28 Validador: gabarito, aderência ao estilo (exemplos reais), checagem RAG lei/jurisprudência. CA: rejeição registrada com motivo; nada publicado sem aprovação.
- RF-29 Calibrador: eventos → dificuldade real, discriminação, sinalização/descarte, refino do DNA e dos prompts. CA: roda diário; relatório.
- RF-30 Versionamento de lei/jurisprudência com propagação: mudança → dossiê, aulas, questões dependentes marcados "revisar". CA: grafo de dependência consultável.

### Épico E8 — Lado B (fase 2, resumo)
RF-31 Corretor de discursivas em lote no padrão da banca. RF-32 Gerador pra professor. RF-33 Publicar trilha própria. RF-34 Dashboard de risco por turma. RF-35 Validação humana paga de conteúdo.

## 6. Requisitos não funcionais

| Área | Requisito |
|---|---|
| Latência | Check-in/reajuste < 5 s; servir questão < 300 ms; geração síncrona só quando não houver cache, com feedback de progresso |
| Custo | Custo LLM/usuário ativo/mês por tier definido em `docs/06-custos.md` e medido por request (tag de tenant, agente, modelo). Geração pesada é em lote noturno. Cache por concurso/tópico |
| Roteamento | LiteLLM (ou equivalente `[ADR]`): modelo barato pra rotina, forte pra DNA/dossiê/validação; fallback; orçamento por tier |
| Disponibilidade | 99,5% na API do aluno; jobs noturnos idempotentes e re-executáveis |
| Observabilidade | Traço completo de toda execução de agente (entrada, ferramentas, saída, custo); logs estruturados; métricas de produto e de qualidade |
| Segurança | OAuth2/OIDC, senhas com argon2, rate limit, isolamento por tenant em toda query (nunca filtro opcional) |
| LGPD | Consentimento explícito e separado pra dados de humor/energia; minimização; retenção definida; exportação e exclusão completas; DPO nominal; base legal documentada |
| Conteúdo | Nada gerado sem validação; toda afirmação jurídica com fonte; versionamento e propagação de mudança |
| Qualidade de código | Python tipado, pydantic nas fronteiras, TDD red-first, sem side effects em import, cobertura mínima definida no CI, DeepEval em toda geração |
| Multi-tenant | Desde o dia 1; tenant = pessoa física ou organização; dados de organização nunca vazam entre tenants |
| Idioma | pt-BR em tudo (UI, conteúdo, código, docs) |
| Acessibilidade | Web AA; áudio das aulas com transcrição |

## 7. Arquitetura

### 7.1 Visão geral

```
[Web] ──── [API (Python)] ──── [Orquestrador do aluno + agentes]
                │                         │
                │                   [Estado do aluno: Postgres + eventos]
                │                         │
        [Billing] [Auth]         [Base de conhecimento: questões, dossiês, aulas, DNA + vetor]
                                          ▲
                        [Motor de Conhecimento: coletor → curador → pesquisador → preenchedor → gerador → validador → calibrador]
                                          ▲
                                [Jobs agendados: noturno, coleta, calibração]
```

Dois planos separados:
- **Plano do aluno** (síncrono, barato, rápido): serve do que já existe.
- **Plano de conhecimento** (assíncrono, caro, em lote): produz o que o aluno vai consumir.

### 7.2 Agentes — contratos

Cada agente: entrada tipada, saída tipada, ferramentas permitidas, modelo padrão, limite de custo, o que **não** faz.

| Agente | Plano | Entrada → Saída | Ferramentas | Não faz |
|---|---|---|---|---|
| `orquestrador` (Coach) | aluno | mensagem/evento do aluno → resposta + ações | ler estado, chamar agentes | gerar conteúdo, decidir sem justificar |
| `analista-de-edital` | conhecimento | edital + provas coletadas → `DnaConcurso` | leitura de PDF, base de questões | inventar peso sem prova |
| `diagnosticador` | aluno | respostas do simulado + questionário → `PerfilEstudo` | banco de itens, TRI | opinar sobre saúde mental |
| `planejador` | aluno/noturno | perfil + DNA + eventos + trilha → `PlanoDia` com justificativa | leitura de estado | gerar conteúdo |
| `gerador-de-conteudo` | conhecimento | encomenda (tópico, tipo, banca, dossiê, exemplos) → rascunho | dossiê, exemplos reais | publicar; escrever sem dossiê |
| `validador` | conhecimento | rascunho → aprovado/rejeitado + motivo | RAG lei/juris, exemplos da banca, segundo modelo | aprovar sem checar gabarito |
| `monitor-previsor` | aluno | eventos → padrões de erro, curva, previsão com intervalo | estatística, eventos | previsão sem intervalo |
| `coletor` | conhecimento | config de fontes → novidades brutas | HTTP, RSS, diff | interpretar conteúdo |
| `curador` | conhecimento | bruto → questões/leis/julgados classificados e versionados | PDF, embeddings, dedup | gerar |
| `pesquisador-de-topico` | conhecimento | tópico do DNA → `DossieTopico` | busca web em fontes permitidas, leitura | usar fonte fora da lista |
| `montador-de-trilha` | conhecimento | DNA + dossiês → `Trilha` | encomenda aulas | escrever aula |
| `preenchedor` | conhecimento | DNA × cobertura → lote de encomendas | relatório de cobertura | gerar |
| `calibrador` | conhecimento | eventos → dificuldade, sinalizações, ajustes de DNA/prompt | estatística | descartar sem registrar |
| `corretor` (fase 2) | B | discursiva + banca → correção no padrão | dossiê, exemplos de espelho | nota final sem critérios |

### 7.3 Fluxos principais

**Onboarding.** escolhe concurso → DNA já existe (cache) → simulado adaptativo → questionário → `PerfilEstudo` → primeiro `PlanoDia` gerado na hora.

**Dia típico.** 05h job gera `PlanoDia` → manhã check-in (humor/energia/tempo) → `planejador` reajusta → aluno executa blocos (aula, questões, revisão FSRS) → cada ação vira `EventoEstudo` → `monitor-previsor` atualiza painel → à noite o `calibrador` consome eventos.

**Edital novo.** `coletor` detecta → `curador` ingere → `analista-de-edital` gera DNA → `pesquisador-de-topico` gera dossiês dos tópicos de maior peso → `preenchedor` encomenda questões → `montador-de-trilha` encomenda aulas → concurso entra no catálogo quando atinge cobertura mínima.

**Mudança de lei/jurisprudência.** `coletor` detecta → `curador` versiona → grafo marca dossiês/aulas/questões dependentes → `pesquisador` roda incremental → `gerador` regenera → `validador` aprova → conteúdo antigo despublicado.

**Semana da prova.** data-alvo − 7 dias → `planejador` entra em modo revisão; geração nova desligada; check-in inclui sono.

## 8. Motor de Conhecimento

### 8.1 Fontes por categoria (lista definitiva na Fase 1)
- Bancas: sites oficiais (provas, gabaritos, recursos, editais).
- Editais e autorizações: Diários Oficiais, portais de concursos.
- Legislação: Planalto (consolidada), com detecção de alteração.
- Jurisprudência: STF/STJ (informativos, súmulas, teses, repercussão geral/repetitivos), TST/TCU conforme exame.
- ENEM: INEP (provas, gabaritos, matrizes).
- Conhecimento aberto: cartilhas e manuais de órgãos, SciELO, repositórios de universidades, periódicos abertos, domínio público.
- Cada fonte: URL, formato, frequência, método de detecção de novidade, termos de uso, licença → `knowledge/fontes/*.yaml` e `docs/RISCOS.md`.

### 8.2 Esquemas centrais

```
DnaConcurso
  concurso_id, banca, orgao, versao, gerado_em
  materias[]: nome, peso_edital, peso_real (incidência), topicos[]
  topicos[]: id, nome, incidencia_por_prova{ano: n}, dificuldade_media, pegadinhas[], fontes[]
  estilo_banca: formato de enunciado, padrões de alternativa, uso de "certo/errado", extensão
  corte_historico[]: ano, cargo, nota
  fontes[]: prova/edital/ano

DossieTopico
  topico_id, versao, gerado_em, validade (o que invalida)
  conceitos[], lei_seca[]: {dispositivo, texto, versao_lei}
  jurisprudencia[]: {tribunal, identificador, tese, dominante|divergente, fonte}
  como_cai[]: {banca, questao_id exemplo, padrão}
  erros_comuns[], dependencias[] (outros tópicos)
  bibliografia[]: {autor, obra, capítulo/seção, por que}
  log_pesquisa[]: {consulta, fonte, data}

Questao
  id, origem (oficial|gerada), banca, ano, orgao, materia, topico_id, formato
  enunciado, alternativas[], gabarito, justificativas{alt: texto}
  dificuldade_estimada, dificuldade_calibrada, discriminacao
  dossie_versao, lei_versoes[], status (rascunho|validada|publicada|revisar|descartada)
  sinalizacoes[]

Aula
  id, trilha_id, topico_id, dossie_versao, versao
  texto, audio_url, versao_leiga, citacoes[], duracao_min, status

Trilha
  concurso_id, versao, modulos[]: {nome, topicos[], aulas[], exercicios[], criterio_conclusao}
```

### 8.3 Qualidade da base — métricas
Cobertura por tópico do DNA (questões e aulas), taxa de rejeição do validador por tipo, taxa de reporte de erro por questão, discriminação média, % de conteúdo com dossiê atual, tempo entre novidade na fonte e publicação, custo por questão/aula aprovada.

**Mínimo pra abrir um concurso ao público** `[ADR]`: hipótese — 100% dos tópicos com peso ≥ 2% cobertos por dossiê, ≥ 40 questões validadas por tópico de alto peso, trilha com aulas dos tópicos que somam 70% da incidência.

## 9. Modelo de dados (aluno)

```
Tenant(id, tipo: pf|org, plano, criado_em)
Usuario(id, tenant_id, email, nome, consentimentos{humor_energia: bool, data}, timezone)
Matricula(id, usuario_id, concurso_id, data_alvo, status)
PerfilEstudo(id, matricula_id, versao, horas_por_dia{seg..dom}, horario_preferido, energia_tipica, historico, proficiencia{materia: (theta, erro)})
PlanoDia(id, matricula_id, data, versao, blocos[]: {tipo: aula|questoes|revisao|descanso, ref_id, duracao_min, justificativa}, gerado_por, ajustado_em)
CheckIn(id, matricula_id, data, humor, energia, tempo_disponivel_min, sono_h?)
EventoEstudo(id, matricula_id, ts, tipo, payload)   # fonte da verdade; append-only
  tipos: respondeu_questao{questao_id, alternativa, correta, tempo_s, bloco_id, energia_no_momento}
         concluiu_aula, pulou_bloco, revisou_card{card_id, rating}, reportou_erro, iniciou_sessao, encerrou_sessao
CardFSRS(id, matricula_id, questao_id|topico_id, estado FSRS, proxima_revisao)
Previsao(id, matricula_id, ts, nota_esperada, intervalo, prob_aprovacao, confianca, base_calculo)
PadraoErro(id, matricula_id, descricao, evidencia{n, taxa}, detectado_em)
Assinatura(id, tenant_id, tier, gateway_ref, status, renova_em)
UsoLLM(id, tenant_id, agente, modelo, tokens_in, tokens_out, custo, ts)
```

Projeções (painel, curva, padrões) são derivadas de `EventoEstudo`; podem ser recalculadas do zero.

## 10. Adapter de exame

```python
"""Contrato que todo módulo de exame implementa. Ler ao adicionar um exame novo."""

from typing import Protocol
from pydantic import BaseModel


class FonteExame(BaseModel):
    """Fonte monitorada pelo coletor para este exame."""
    nome: str
    url: str
    formato: str            # pdf | html | rss | api
    frequencia_horas: int
    deteccao: str           # rss | sitemap | diff | api
    licenca: str


class RegrasNota(BaseModel):
    """Como a nota é calculada e qual o corte típico."""
    formato: str            # multipla_escolha | certo_errado | discursiva | misto
    penaliza_erro: bool
    corte_referencia: float | None


class AdapterExame(Protocol):
    """Interface tipada de um módulo de exame (concursos, ENEM, OAB...)."""

    identificador: str

    def fontes(self) -> list[FonteExame]:
        """Fontes oficiais que o coletor deve monitorar."""

    def bancas(self) -> list[str]:
        """Bancas ou organizadores cobertos por este exame."""

    def taxonomia(self) -> dict[str, list[str]]:
        """Matérias e tópicos canônicos usados na classificação."""

    def regras_nota(self, concurso_id: str) -> RegrasNota:
        """Regras de pontuação e corte do concurso informado."""

    def parser_prova(self, banca: str):
        """Parser específico da banca para PDFs de prova e gabarito."""

    def prompts_banca(self, banca: str) -> dict[str, str]:
        """Instruções de estilo por banca para geração e validação."""
```

Adicionar exame = criar pacote em `adapters/<exame>/` implementando o protocolo + testes. Nenhuma alteração no núcleo.

## 11. API (superfície principal)

Prefixo `/v1`, OpenAPI gerado do pydantic, versionada.

| Recurso | Métodos | Notas |
|---|---|---|
| `/auth/*` | login, refresh, oauth google | |
| `/concursos` | GET lista, GET `{id}`, GET `{id}/dna` | catálogo público (SEO) |
| `/editais` | POST upload | assíncrono; status por polling/SSE |
| `/matriculas` | POST, GET, PATCH data-alvo | |
| `/diagnostico` | POST iniciar, POST responder, GET resultado | adaptativo |
| `/perfil` | GET, PUT | versionado |
| `/plano/hoje` | GET, POST check-in, POST pular/trocar bloco | |
| `/aulas/{id}` | GET (texto, áudio, leiga) | |
| `/questoes/proxima`, `/questoes/{id}/responder`, `/questoes/{id}/reportar` | | |
| `/revisao` | GET fila FSRS, POST avaliar card | |
| `/painel` | GET curva, padrões, previsão | |
| `/coach` | POST mensagem (SSE) | orquestrador |
| `/conta` | exportar, excluir, consentimentos | LGPD |
| `/billing` | checkout, portal, webhooks do gateway | |
| `/admin/conhecimento/*` | cobertura, fila de validação, sinalizações | interno |

## 12. Stack recomendada `[ADR]`

Fixo: **backend e agentes em Python; web obrigatória; app mobile só com evidência.** O resto é recomendação inicial; o Claude Code confirma ou troca com justificativa.

| Camada | Recomendação | Alternativas a comparar |
|---|---|---|
| API | FastAPI + pydantic v2 + uvicorn | Litestar |
| Agentes | Google ADK pro orquestrador e agentes do aluno; pydantic-ai pros agentes de pipeline (entrada/saída tipada, simples) | LangGraph, cru |
| Roteamento LLM | LiteLLM (custo, fallback, orçamento por tier) | Vertex direto |
| Modelos | forte pra DNA/dossiê/validação; barato pra rotina; TTS pra áudio | comparar custo/qualidade em pt-BR |
| Banco | Postgres (+ pgvector) — um banco só no MVP | Weaviate se o vetor virar gargalo |
| Fila/jobs | Cloud Run Jobs + Cloud Scheduler; ou worker com arq/Celery | Temporal se os pipelines crescerem |
| Revisão espaçada | py-fsrs | — |
| Adaptativo/TRI | proxy simples no MVP; py-irt/girth depois | — |
| PDF | Docling | marker, Document AI |
| Web | Next.js (SSR/SEO, páginas programáticas) | SvelteKit, HTMX + Jinja |
| Auth | próprio com OIDC (Google) | Auth0/Clerk se custo compensar |
| Billing | Asaas (Pix/boleto nativos) | Stripe, Pagar.me |
| E-mail | Resend/Brevo | — |
| Deploy | Cloud Run + Cloud SQL | Fly.io, Railway, VPS |
| Observabilidade | OpenTelemetry + traços de agente; Langfuse ou similar pra LLM | — |
| Eval | DeepEval + pytest | — |
| Mobile (se aprovado) | PWA com push primeiro; Capacitor se precisar de loja | Expo/Flutter |
| Infra como código | Terraform mínimo | — |

## 13. Multi-tenant, auth e billing
- Tenant em todo registro; filtro obrigatório via dependência do framework, nunca manual.
- PF: 1 tenant = 1 usuário. Org: tenant com papéis (admin, professor, aluno).
- Billing por tenant; webhooks idempotentes; estado da assinatura é cache do gateway, reconciliado diariamente.
- Orçamento LLM por tier lido pelo roteador em cada request; excedente degrada modelo, não bloqueia.

## 14. Qualidade e avaliação

**Suites DeepEval obrigatórias**
- `questao_banca`: gabarito correto (checagem cruzada), aderência ao estilo (vs. exemplos reais), sem alucinação jurídica (fontes do dossiê), justificativas coerentes.
- `aula`: fidelidade ao dossiê, citações válidas, densidade (sem enrolação), nível de leitura na versão leiga.
- `dna`: pesos batem com incidência calculada da base; nenhum tópico sem fonte.
- `plano`: respeita tempo disponível, prioriza por peso × lacuna, justificativa presente, recomenda descanso quando energia baixa.
- `validador`: taxa de falso-aprovado em conjunto com erros plantados.

**Amostragem humana**: 2% do conteúdo publicado por semana revisado (você no MVP; lado B pago depois).

## 15. Métricas-norte e regra de corte

| Métrica | Alvo MVP (30 dias) `[ADR]` |
|---|---|
| Ativação (diagnóstico concluído / cadastro) | ≥ 60% |
| Conclusão do plano diário | ≥ 50% dos dias ativos |
| Retenção D7 / D30 | ≥ 40% / ≥ 20% |
| Conversão Free → Pro | ≥ 3% |
| Custo LLM / usuário Pro / mês | ≤ 25% do preço |
| Taxa de reporte de erro por questão | < 2% |
| NPS após 14 dias | ≥ 40 |

**Regra de corte** (proposta): 30 dias após lançamento público, se < 30 pagantes **e** D30 < 15%, pivotar exame/persona; 60 dias sem tração, arquivar. Números confirmados na Fase 0.

## 16. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Questão gerada errada destrói confiança | alto | validador + DeepEval + reporte + calibrador; nunca gerar sem dossiê |
| Copyright de material de terceiros | alto | só fontes permitidas; bibliografia é referência; termos de uso registrados |
| LGPD (humor/energia) | alto | consentimento separado, minimização, exclusão real |
| Custo LLM explode | alto | lote noturno, cache por concurso, roteamento, orçamento por tier, medição por request |
| Cold start da previsão | médio | v0 honesta com intervalo; caminho v1 com dados próprios |
| Concorrente grande copia | médio | moat de dados + velocidade de cobertura de edital novo |
| Fontes mudam formato | médio | coletor com testes de detecção; falha alerta, não silencia |
| Poucas horas do fundador | alto | squad de agents, fatias pequenas, regra de corte |
| Sazonalidade (ENEM) | médio | portfólio de exames; concursos como base |

## 17. Roadmap por fatias (MVP)

1. Template base (auth, tenant, billing stub, landing SEO, Dockerfile uv, CI).
2. Motor v0: coletor + curador do exame inicial; base de provas públicas; cobertura medida.
3. Adapter do exame + DNA (cacheado).
4. Dossiês dos tópicos de maior peso.
5. Geração em lote de questões + validador.
6. Trilha + primeiras aulas (texto + áudio).
7. Diagnóstico + perfil.
8. Plano de hoje + job noturno + check-in.
9. Questões servidas + FSRS.
10. Painel + previsão v0.
11. Calibrador.
12. Billing real + limites por tier.
13. Landing programática por concurso/banca + lançamento.

Cada fatia: red-first, DeepEval quando houver geração, traço visível, docs atualizadas, deployável.

## 18. Glossário
**DNA do concurso**: perfil quantitativo de como a banca cobra aquele concurso. **Dossiê**: dossiê de conhecimento por tópico, com fontes. **Trilha**: curso estruturado gerado por concurso. **Plano vivo**: plano diário reescrito por desempenho e contexto. **FSRS**: algoritmo de revisão espaçada. **TRI**: teoria de resposta ao item. **Lado A/B**: aluno / professor-cursinho. **Motor de Conhecimento**: subsistema que coleta, pesquisa, gera, valida e calibra conteúdo.

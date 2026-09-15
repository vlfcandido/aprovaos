# Arquitetura
> O que é: como o AprovaOS é construído — stack (ADR-0017…0026), componentes, o fluxo diário do agente, o Motor de Conhecimento, o esquema tipado do adapter de exame, a superfície da API, o roteamento de modelos por tier, observabilidade e deploy dentro de R$ 100/mês. Quando ler: antes de qualquer fatia da Fase 5; ao propor mudança de stack (abrir ADR nova, não editar esta).

Decisões do dono na abertura da Fase 3 (14/09/2026): FastAPI + SQLAlchemy 2.0 + Pydantic v2 com agentes em ADK + Gemini; front HTMX + Jinja + ilhas de JS; VPS Hetzner + Docker Compose + Postgres/pgvector + Caddy; cobrança como pessoa física até 10 pagantes. Fontes de API: docs oficiais citadas nas ADRs; versões conferidas no PyPI em 14/09/2026 (`google-adk` 2.9.0, `fastapi` 0.141.1, `sqlalchemy` 2.0.53, `pydantic` 2.13.5, `fsrs` 6.3.2, `pypdfium2` 5.13.0, `pdfplumber` 0.11.10).

## 1. Visão geral

```
┌──────────────────────────── VPS Hetzner (Docker Compose) ────────────────────────────┐
│  Caddy (TLS) ─► web (FastAPI + Jinja/HTMX + PWA)  ─► Postgres 16 + pgvector          │
│                    │                                  ▲                               │
│                    ├─ jobs (mesmo container, cron): 05h plano · 6h radar · noite lote  │
│                    │                                  │                               │
│                    └─ agentes ADK (in-process) ──► Gemini (AI Studio/Vertex) ─ roteador│
│  backup diário ─► object storage (Hetzner Storage Box)      traços ─► tabela `traco`  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Um processo web, um processo de jobs, um banco. Sem filas externas, sem Redis, sem serviço gerenciado além do LLM: é o que o teto permite e o que uma pessoa com poucas horas mantém. Quando o piloto exigir mais, a primeira coisa a sair do host é o lote noturno do Motor (é batch; roda em qualquer lugar).

## 2. Componentes e pastas (nascem na Fase 5, fatia a fatia — ADR-0010)

| pasta | o que é | fatia |
|---|---|---|
| `backend/aprovaos/dominio/` | entidades e regras puras (Pydantic v2), sem I/O: `PlanoDia`, `EventoEstudo`, `Proficiencia`, regras do check-in, previsão v0, FSRS via `fsrs` | 7–10 |
| `backend/aprovaos/dados/` | SQLAlchemy 2.0 (`DeclarativeBase`, `Mapped[]`), migrações Alembic, repositórios | 1 |
| `backend/aprovaos/agentes/` | agentes ADK (`LlmAgent`) por papel (§4), tools tipadas, prompts versionados em arquivo | 3–11 |
| `backend/aprovaos/motor/` | pipeline do Motor de Conhecimento (§5): coletor, curador, analista, pesquisador, preenchedor, gerador, validador, calibrador | 2–6, 11 |
| `backend/aprovaos/api/` | FastAPI: rotas HTML (Jinja/HTMX) e JSON (§7); auth; billing (webhook) | 1, 12 |
| `backend/aprovaos/roteador/` | escolha de modelo e orçamento por tier (§8) | 3 |
| `adapters/concursos/` | `AdapterExame` do exame inicial (§6); `adapters/oab/` na fase 2 | 3 |
| `web/` | templates Jinja, CSS por tokens, `static/js/ilhas/*.js` (popover, grifos, gráficos — reaproveitados do protótipo), `manifest.json`, `sw.js` | 1, 6–10 |
| `knowledge/` | config de fontes (`fontes.yaml`), prompts do Motor, fixtures de provas para teste | 2 |
| `eval/` | suítes DeepEval (fidelidade às fontes, aderência ao estilo da banca), datasets rotulados | 4–6 |
| `data/` | volumes locais em dev (Postgres, PDFs baixados) — git-ignored | 2 |

Regras de código (CLAUDE.md): TDD red-first; docstring em toda função/classe pública; tipagem completa; Pydantic em toda fronteira; **nenhum efeito colateral em import** (conexão de banco, cliente de LLM e leitura de env só dentro de funções/fábricas chamadas explicitamente); Python 3.13 pinado com `uv` (ADR-0026).

## 3. Fluxo diário do agente

```mermaid
sequenceDiagram
  autonumber
  participant Cron as jobs (05h local)
  participant Plan as planejador (ADK)
  participant DB as Postgres
  participant Aluna
  participant Web as web (HTMX)
  participant Mon as monitor-previsor
  participant Cal as calibrador (noite)
  Cron->>DB: lê PerfilEstudo, EventoEstudo (7 d), cartões vencidos, DNA, curva
  Cron->>Plan: gerar PlanoDia (tool: candidatos de bloco; LLM só escreve o porquê)
  Plan->>DB: grava PlanoDia + porque por bloco (contrato: nunca sem `porque`)
  Aluna->>Web: check-in (energia, sono, tempo)
  Web->>Web: regras determinísticas de reajuste (< 5 s, sem LLM)
  Web->>DB: PlanoDia v2 + EventoEstudo(checkin)
  Aluna->>Web: executa blocos (aula, questões, revisão)
  Web->>DB: EventoEstudo por ação (acerto, tempo, confiança, distração, pular)
  Web->>Mon: recalcular proficiência/curva/previsão (função pura, por evento)
  Mon->>DB: Painel materializado
  Mon-->>Aluna: alerta (≤ 1/dia) com ajuste proposto
  Cal->>DB: dificuldade real, discriminação, sinalização de questões, refino do DNA
```

Princípios embutidos no fluxo: o LLM **não decide o plano** — escolhe entre candidatos gerados por regras (peso do DNA × erro recente × cartões vencidos × tempo disponível) e escreve o porquê; o check-in é regra pura; toda decisão grava `porque`; toda ação vira evento append-only.

## 4. Agentes (ADK) — um por papel da spec §7.2

Todos são `google.adk.agents.LlmAgent` com `output_schema` Pydantic, `include_contents='none'` (sem histórico de chat: cada chamada recebe só o contexto montado por tools), prompts em `agentes/prompts/<papel>.md` versionados, e tools que **só leem/gravam pelo repositório** (nunca SQL direto no prompt).

| agente | entrada (tools) | saída (`output_schema`) | modelo (tier) |
|---|---|---|---|
| `planejador` | candidatos de bloco, perfil, curva | `PlanoDia` (blocos + porquê) | Flash-Lite (Free) / Flash (Pro) |
| `tutor-porque` | decisão + motivo do "discordar" | `Reajuste` (novo bloco + explicação) | Flash-Lite |
| `analista-de-edital` | edital (HTML/PDF), provas | `DnaConcurso` | Flash (lote) |
| `pesquisador-de-topico` | fontes permitidas (LexML, STJ…), buscas logadas | `DossieTopico` | Flash (lote) |
| `gerador-questao` | dossiê + DNA + 5 itens originais do tópico | `QuestaoGerada[]` | Flash (lote) |
| `gerador-aula` | dossiê + DNA + tópicos relacionados já vistos (fio da memória) | `Aula` (denso, leigo, citações) | Flash (lote) |
| `validador` | item gerado + fontes + exemplos reais | `Veredito` (aprova/rejeita + motivo) | Flash **de outra família de prompt** (nunca o mesmo prompt que gerou) |
| `mnemonista` | tópico + consagrados | `Mnemonico` | Flash-Lite (lote, cache) |
| `resumidor-semanal` | eventos da semana + dossiês | `ResumoCumulativo` | Flash-Lite (1/semana) |
| `calibrador` | eventos + reportes | `AjusteCalibracao[]` | regras + Flash-Lite para refinar prompts |

Execução: `Runner` com `DatabaseSessionService` (persistente em Postgres — os agentes de lote não têm sessão de conversa, mas os traços ficam). Sem `sub_agents` no MVP: orquestração é código Python explícito (pipeline), não agente-orquestrador — mais barato de testar e de traçar.

## 5. Motor de Conhecimento v0 (fatias 2–6 e 11)

```
fontes.yaml ─► coletor ─► curador ─► analista-de-edital ─► DNA
   (API Cebraspe, RSS FGV,   (PDF→questões          │
    LexML API, STJ)          classificadas, dedup,  ▼
                              embedding)      pesquisador-de-topico ─► DossieTopico (versionado, grafo)
                                                     │
                                          preenchedor (cobertura × DNA) ─► gerador-questao / gerador-aula
                                                     │
                                                 validador ─► publicado | rejeitado(motivo)
                                                     ▲
                                              calibrador (noite) ◄── EventoEstudo, reportes
```

- **Coletor**: uma classe por fonte implementando `FonteColetavel` (`listar_novidades() -> list[Novidade]`, `baixar(novidade) -> Documento`); config em `knowledge/fontes.yaml` (URL, frequência, user-agent, política). Cebraspe pela API JSON (`/eventos/tipo/concursos/fase/{fase}` → `/eventos/{id}` → `arquivosGabarito[]`); FGV por `rss.xml` + página do concurso, **frequência máxima 1×/6 h, sem login, cache por ETag** (RISCOS R-02); LexML por API/RSS; STJ por informativo. Teste de detecção com fixture gravada.
- **Curador**: `pypdfium2` para render/texto, `pdfplumber` para tabelas de gabarito (ADR-0023; PyMuPDF vetado por AGPL); segmentação em itens por regex de numeração + heurística por banca; classificação por matéria/tópico com Flash-Lite + embedding (`gemini-embedding` → pgvector) e dedup por cosseno ≥ 0,97; guarda `origem` completa (banca, órgão, cargo, ano, item, gabarito, URL, tipo de caderno).
- **Grafo de tópicos**: tabela `topico_relacao` (tópico A → B, peso, fonte da relação: edital, dossiê, coocorrência em prova). Alimenta fio da memória (a) e (b) e a propagação de mudança de lei (RF-30).
- **Validador**: obrigatório antes de `publicado=true`; checa gabarito (resolve o item de novo sem ver o gabarito), aderência ao estilo (compara com 5 originais do mesmo tópico via embedding + regras da banca: C/E, A–E), e RAG de lei/jurisprudência (toda citação resolve em `dispositivo_legal`). DeepEval em `eval/` roda em CI com amostra.
- **Lote noturno**: só gera o que o `preenchedor` pediu (cobertura < alvo por tópico), com teto diário de gasto (§8) — ao bater o teto, para e registra.

## 6. Adapter de exame — interface tipada

```python
# adapters/base.py — contrato que todo exame implementa; sem I/O no import.
from typing import Protocol
from pydantic import BaseModel

class RegraCorrecao(BaseModel):
    """Como a prova pontua: tipo de item, penalização e nota de corte, lidos do edital."""
    tipo_item: Literal["certo_errado", "multipla_escolha"]
    alternativas: int | None          # 5 para A–E; None para C/E
    anula_por_erro: bool              # Cebraspe: conforme edital
    corte_historico: tuple[float, float] | None  # intervalo em pontos líquidos

class AdapterExame(Protocol):
    id: str                                   # "concursos", "oab"
    bancas: tuple[str, ...]                   # ("cebraspe", "fgv")
    def fontes(self) -> list[FonteColetavel]: ...
    def segmentar_prova(self, doc: Documento) -> list[ItemBruto]: ...
    def regra_correcao(self, edital: Edital) -> RegraCorrecao: ...
    def montar_dna(self, edital: Edital, provas: list[Prova]) -> DnaConcurso: ...
    def estilo_banca(self, banca: str) -> EstiloBanca: ...   # prompts e validações por banca
    def simular_nota(self, respostas: list[Resposta], regra: RegraCorrecao) -> NotaLiquida: ...
```

`adapters/concursos/` implementa Cebraspe e FGV; `adapters/oab/` (fase 2) reaproveita `fgv`. Nada do domínio importa o adapter concreto — ele é injetado.

## 7. Superfície da API (spec §11, ajustada)

Rotas HTML (Jinja + HTMX, sessão por cookie): `/` landing · `/entrar` `/cadastro` · `/editais` (radar, filtros, meus concursos) · `/concurso/{id}` (DNA, edital verticalizado) · `/diagnostico` · `/hoje` (plano + check-in) · `/aula/{id}` · `/questoes/{bloco}` · `/revisao` · `/painel` · `/conta` (plano, Pix, cancelar, exportar/excluir).
Rotas JSON (para as ilhas de JS e o PWA): `POST /api/eventos` (lote de `EventoEstudo`) · `GET /api/referencia/{citacao}` (popover) · `GET /api/glossario/{termo}` · `POST/GET/DELETE /api/anotacoes` · `GET /api/painel/previsao?extra_min=` (simulador) · `POST /api/webhooks/pagamento` · `POST /api/push/inscrever`.
Tudo tipado com Pydantic v2 nos dois sentidos; erros no formato `{codigo, mensagem, acao}`.

## 8. Roteamento de modelos e orçamento por tier (ADR-0018)

| uso | Free | Pro | teto |
|---|---|---|---|
| plano noturno (porquê) | Flash-Lite | Flash | 1 chamada/dia |
| discordar / tutor | Flash-Lite, 3/dia | Flash-Lite, 20/dia | — |
| resumo semanal | — | Flash-Lite | 1/semana |
| áudio (TTS) | — | Cloud TTS (free tier) | 1 por aula, cache |
| lote do Motor | compartilhado (não é por usuário) | | teto diário em R$ |
| degradação | ao bater o teto: modelo mais barato → cache → mensagem "hoje sem porquê novo" — **nunca** bloquear a sessão | | |

O roteador registra por chamada: modelo, tokens in/out, custo estimado, tier, usuário — é a fonte de `06-custos.md` em produção e do alarme de teto (§9).

## 9. Observabilidade (ADR-0024)
OpenTelemetry (SDK Python) instrumentando FastAPI e os agentes ADK; exportador grava spans na tabela `traco` (Postgres) com `usuario`, `agente`, `modelo`, `tokens`, `custo`, `latencia`, `resultado`; página `/admin/tracos` (só dono) lista por dia; alarme por e-mail quando gasto do dia > teto ou taxa de rejeição do validador > 30 %. Sem vendor no MVP; exportar para um backend externo é trocar o exporter.

## 10. Deploy (ADR-0020)
Hetzner CX23 (2 vCPU, 4 GB, 40 GB, 20 TB) em NBG/HEL; Docker Compose com `caddy`, `web`, `jobs`, `postgres:16 + pgvector`; volumes em disco; `pg_dump` diário para Storage Box; deploy por `git pull && docker compose up -d --build` via GitHub Actions (SSH) depois de testes verdes; `.env` só no servidor. Região UE → latência ~200 ms para o Brasil: aceitável para HTMX; se doer, migrar para provedor com região BR (a app não sabe onde roda). Domínio quando o nome sair (P-01).

## 11. PWA
`manifest.json` (instalável), `sw.js` com cache de shell + páginas visitadas (offline de leitura), Web Push para o check-in (VAPID; iOS 16.4+ só instalada — ADR-0013). Sem app nativo.

## 12. O que esta arquitetura não resolve (vai para PENDENCIAS/RISCOS)
Escala além de um host (R-07); latência UE→BR; gateway definitivo quando houver CNPJ (ADR-0025); TRI de verdade (ADR-0022: proxy no MVP); STF/Planalto/DOU como fontes automáticas (P-15).

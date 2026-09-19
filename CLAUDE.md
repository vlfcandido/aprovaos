# AprovaOS — instruções permanentes (PROVISÓRIO: a Fase 7 reescreve este arquivo)
> O que é: as regras que qualquer modelo segue neste repositório. Quando ler: sempre, ao abrir a sessão, antes de qualquer resposta.

## O que é este repositório
O produto inteiro do **AprovaOS** (codinome): um agente de IA que assume a responsabilidade pela aprovação do candidato — backend, agentes, front, Motor de Conhecimento, docs, skills e subagents. O que construir está em `SPEC-aprovaos.md`; como trabalhar, em `PROMPT-aprovaos.md`; o que a Fase 0 decidiu, em `docs/00-visao.md` e `docs/DECISOES.md`.
Dono: Vinicius — Senior AI Engineer (~13 anos de software, ~5 em IA generativa), projeto paralelo com **poucas horas por semana**. Automação, critério de corte e MVP pequeno valem mais que ambição. Ele revisa e decide; o modelo faz o grosso.
É um SaaS da fábrica de micro-SaaS (`~/PycharmProjects/fabrica-saas`), **fora do funil** por decisão dele — herda as regras de lá por referência (ADR-0001).

## Regras de trabalho (inegociáveis)
1. **Português do Brasil** em código, comentários, docstrings, documentação, UI e respostas.
2. **Pergunte antes de assumir** o que é decisão do dono (exame, front, gateway, orçamento, nome). Perguntas em **lote, no início de cada fase** — nunca uma por vez — e **sempre pela ferramenta de perguntas com opções** (AskUserQuestion, até 4 por rodada, opção recomendada primeiro). Pergunta solta no texto não é respondida.
3. **TDD red-first, inviolável.** Docstring profissional em toda função/classe pública. Tipagem completa; pydantic em toda fronteira de dados. **Nenhum efeito colateral em import.**
4. **Fonte para toda afirmação de mercado** (URL no arquivo). Para API, documentação oficial (Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0, ADK, pydantic-ai, LiteLLM). Não inventar API nem número.
5. **Poucos arquivos bons.** Todo arquivo começa com cabeçalho de 2 linhas: o que é / quando ler. Nada nasce como stub (ADR-0010).
6. **Fim de fase = commit** com mensagem descritiva + resumo curto para o dono. Fase seguinte só com confirmação dele.
7. **O que não der para fazer vai para `docs/PENDENCIAS.md`.** Nunca improvisar no lugar.
8. **Reutilize antes de criar.** Primeiro a fábrica, depois recursos externos (instalar, ler, testar, veredito em `docs/DECISOES.md` com licença preservada), só então do zero. Skills novas nascem pelo ciclo da `superpowers:writing-skills` (baseline sem a skill → escrever → reexecutar num modelo menor; ADR-0014) e precisam funcionar num modelo menor.
9. **Fatias verticais.** Cada incremento atravessa domínio → agente → API → front → teste. Nada de "primeiro todo o backend".
10. **Surgical diffs** em código existente; arquivo inteiro só quando novo.
11. **Nada gerado chega ao aluno sem validação; toda afirmação jurídica tem fonte; previsão sempre com intervalo.** São regras de produto (visão §4) e valem para o código que as implementa.
12. **Tudo que for decidido, pesquisado ou concluído fica em arquivo, com o raciocínio.** O próximo modelo só sabe o que estiver escrito.

## Estado das fases
| fase | entrega | status |
|---|---|---|
| 0 — Setup, visão e perguntas | `CLAUDE.md`, `docs/00-visao.md`, `docs/DECISOES.md` (ADR-0001…0010), `docs/PENDENCIAS.md` | **entregue em 14/09/2026** |
| 1 — Deep research | `docs/01-pesquisa-mercado.md` (rodada `wf_09928095-f09` + síntese em sessão; raw em `docs/evidencias/raw/2026-09-14-fase1/`) | **entregue em 14/09/2026** (portão decidido: ADR-0011 Cebraspe+FGV, P-11 feita) |
| 2 — Produto (PRD) | `docs/02-produto.md`, skill `.claude/skills/avaliador-de-feature/` (testada com Haiku, ADR-0014) | **entregue em 14/09/2026** |
| 3 — Arquitetura e dados | `docs/03-arquitetura.md`, `04-modelo-de-dados.md`, `06-custos.md`, `RISCOS.md`, ADR-0013 e 0017…0026 | **entregue em 14/09/2026** |
| 4 — Skills e subagents | 7 skills do Motor em `.claude/skills/*` (testadas com Haiku, RED→GREEN→REFACTOR; evidências em `docs/evidencias/2026-09-17-fase4-skills/`), 5 subagents em `.claude/agents/*`, ADR-0027…0029 (piloto por PDF, piloto v0, subagents vs teams) | **entregue em 17/09/2026** |
| 5 — MVP em fatias verticais | `backend/`, `web/`, `adapters/concursos/`, `knowledge/`, `eval/` — **ordem real e estado na tabela "Fatias" do PRD §6** (piloto v0 = V1–V5, ADR-0028); plano e diário de cada fatia em `docs/fatias/` | **em andamento — 19/09/2026**: entregues V1, V2, V3, V3b, V4, V5 (piloto v0 completo) e as fatias 4, 6, 7, 8 e 11; **em execução** a fatia 10 (painel) e a fatia 5 (inéditas); **com plano escrito, não iniciadas**: 1b (radar), 12 (billing) |
| 6 — Landing, SEO e lançamento | `docs/05-playbook-seo.md`, `docs/07-playbook-lancamento.md` | **playbooks entregues em 19/09/2026**; a fatia 13 (páginas públicas que o playbook de SEO especifica) está em execução |
| 7 — Handoff | `CLAUDE.md` definitivo, `docs/HANDOFF.md` | não iniciada |

## Mapa do repositório (o que existe hoje; o resto nasce na fase indicada — ADR-0010)
```
CLAUDE.md                     # este arquivo                                              (fase 0)
SPEC-aprovaos.md              # o que construir — spec v0.1 do fundador                   (raiz, antes da fase 0)
PROMPT-aprovaos.md            # como trabalhar — 7 fases                                  (raiz, antes da fase 0)
docs/00-visao.md              # tese, dois lados, moat, cunha do MVP, corte, métricas     (fase 0)
docs/DECISOES.md              # ADRs curtos                                               (todas)
docs/PENDENCIAS.md            # o que ficou para depois e por quê                         (todas)
docs/01-pesquisa-mercado.md   # concorrentes, bancas, fontes, SEO, mobile                 (fase 1)
docs/02-produto.md            # PRD                                                       (fase 2)
docs/03-arquitetura.md · 04-modelo-de-dados.md · 06-custos.md · RISCOS.md                (fase 3)
.claude/skills/               # avaliador-de-feature + 7 skills do Motor (contratos de DNA, ingestão, fontes, pesquisa, aula, questão, calibração)  (fases 2 e 4)
.claude/agents/               # pesquisador-de-topico · dev-agentes · dev-backend · dev-web · qa-eval (+ globais po-planejador/dev-executor/revisor)  (fase 4)
docs/evidencias/              # entrevistas, mockups, P-11, testes das skills (fixtures reutilizáveis na Fase 5)
backend/                      # FastAPI + SQLAlchemy 2.0 + Alembic, `uv`, testes (`cd backend && uv run pytest`)  (fase 5, V1)
web/                          # Jinja + HTMX 2 vendorizado + CSS por tokens                              (fase 5, V1)
scripts/checar.sh             # a checagem completa = CI (`bash scripts/checar.sh` antes de commitar)   (fase 5, V1)
compose.yaml · .env.example · .github/workflows/ci.yml                                   (fase 5, V1)
docs/fatias/                  # plano (`VN-*.md`) e diário de execução (`VN-execucao.md`) por fatia     (fase 5)
knowledge/fixtures/editais/   # 1 fixture fictício + 2 editais REAIS (AOCP/TJ-PR, FCC/TRT9)           (fase 5)
knowledge/fixtures/juridico/  # espelhos do Planalto, STF e STJ usados pelos dossiês                   (fase 5)
knowledge/fixtures/fontes/    # respostas reais da API da Cebraspe (lista, detalhe, catálogo)          (fase 5)
knowledge/fontes.yaml         # fichas do coletor (protocolo monitor-de-fontes); FGV vetada, P-13      (fase 5)
data/uploads/                 # PDFs de edital subidos pela aluna                                      (fase 5, V2)
mobile/                       # só se a fase 3 aprovar app
eval/                         # suíte DeepEval — ainda não existe (pendência da fatia 5)
docs/05-playbook-seo.md · 07-playbook-lancamento.md                                      (fase 6)
docs/HANDOFF.md                                                                          (fase 7)
```

## Como continuar o trabalho
1. Abra o Claude Code **dentro desta pasta**, com a fábrica anexada:
   `cd ~/PycharmProjects/aprovaos && claude --add-dir ~/PycharmProjects/fabrica-saas`
2. Leia, nesta ordem: `docs/HANDOFF.md` (quando existir) → `docs/PENDENCIAS.md` → `docs/00-visao.md` → `docs/DECISOES.md` → a fase em andamento no `PROMPT-aprovaos.md`. A spec inteira antes de qualquer fase que toque produto ou arquitetura.
3. **Estado em 19/09/2026.** Fases 0 a 4 entregues; Fase 5 em andamento; Fase 6 com os dois playbooks escritos.
   - **Para rodar:** `cp .env.example .env`, preencher `CHAVE_SECRETA`, `docker compose up -d --build`. Sem Docker: `cd backend && DATABASE_URL=sqlite:///dev.db CHAVE_SECRETA=… uv run alembic upgrade head && uv run uvicorn aprovaos.main:criar_app --factory`. Use `http://127.0.0.1:8000`, **não** `localhost` (o listener do container responde em IPv6). Se já houver Postgres local na 5432, mude `POSTGRES_PORT`.
   - **O que está no ar (local):** conta → subir edital (PDF) → DNA + edital verticalizado → questões originais da Cebraspe por tópico, certo/errado **e** múltipla escolha A–E, com origem, justificativa ancorada em dispositivo legal e reportar erro → cartão de erro com FSRS → fio da memória (b) e (c) → dossiê e aula por tópico com fonte literal → trilha → diagnóstico adaptativo e rotina → plano do dia com check-in, discordar e aviso de distração → calibrador.
   - **Números reais da base hoje** (`dev.db`): 250 questões coletadas, **137 publicáveis** contra o edital real do TJ-PR (Instituto AOCP, 9 matérias / 99 tópicos), 38 tópicos com questão, 4 dossiês, 2 aulas publicadas, 18 respostas reais da piloto. `perfil_estudo` está **vazio** — o diagnóstico da fatia 7 rodou contra cópia e não deixou perfil.
   - **Os dois limites honestos que mandam na leitura de tudo:** (a) **P-17 continua aberta** — a banca do concurso real da piloto é desconhecida; o TJ-PR é um edital real dela, mas não *o* edital; (b) **peso por matéria é lacuna declarada** em edital real (P-39), então "maior peso" no produto significa **questões publicáveis medidas**, não peso do edital (ADR-0039).
   - **A armadilha que mais custou nesta semana, registrada para não se repetir:** o fixture fictício `edital-assessor-gabinete.pdf` foi escrito por um modelo para o parser de outro modelo ler, e ficou sendo a base de medição por dois dias depois de existirem editais reais no repositório (ADR-0036). Regra que saiu daí: **material real que o dono entrega vai para o caminho principal imediatamente**, não vira só fixture de teste.

4. Nenhuma fase começa antes de o dono confirmar a anterior.

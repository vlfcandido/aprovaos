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
8. **Reutilize antes de criar.** Primeiro a fábrica, depois recursos externos (instalar, ler, testar, veredito em `docs/DECISOES.md` com licença preservada), só então do zero. Skills novas nascem pelo `skill-creator` e precisam funcionar num modelo menor.
9. **Fatias verticais.** Cada incremento atravessa domínio → agente → API → front → teste. Nada de "primeiro todo o backend".
10. **Surgical diffs** em código existente; arquivo inteiro só quando novo.
11. **Nada gerado chega ao aluno sem validação; toda afirmação jurídica tem fonte; previsão sempre com intervalo.** São regras de produto (visão §4) e valem para o código que as implementa.
12. **Tudo que for decidido, pesquisado ou concluído fica em arquivo, com o raciocínio.** O próximo modelo só sabe o que estiver escrito.

## Estado das fases
| fase | entrega | status |
|---|---|---|
| 0 — Setup, visão e perguntas | `CLAUDE.md`, `docs/00-visao.md`, `docs/DECISOES.md` (ADR-0001…0010), `docs/PENDENCIAS.md` | **entregue em 14/09/2026** |
| 1 — Deep research | `docs/01-pesquisa-mercado.md` (compartilhada com a fábrica — ADR-0006, confirmar P-04) | não iniciada |
| 2 — Produto (PRD) | `docs/02-produto.md`, skill `avaliador-de-feature` | não iniciada |
| 3 — Arquitetura e dados | `docs/03-arquitetura.md`, `04-modelo-de-dados.md`, `06-custos.md`, `RISCOS.md`, ADRs de stack/front/mobile/gateway/deploy | não iniciada |
| 4 — Skills e subagents | `.claude/skills/*`, `.claude/agents/*`, decisão subagents vs teams | não iniciada |
| 5 — MVP em fatias verticais | `backend/`, `web/`, `adapters/concursos/`, `knowledge/`, `eval/` (13 fatias, spec §17) | não iniciada |
| 6 — Landing, SEO e lançamento | `docs/05-playbook-seo.md`, `docs/07-playbook-lancamento.md` | não iniciada |
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
.claude/skills/ · .claude/agents/                                                        (fase 4)
backend/ · web/ · adapters/ · knowledge/ · data/ · eval/                                 (fase 5)
mobile/                       # só se a fase 3 aprovar app
docs/05-playbook-seo.md · 07-playbook-lancamento.md                                      (fase 6)
docs/HANDOFF.md                                                                          (fase 7)
```

## Como continuar o trabalho
1. Abra o Claude Code **dentro desta pasta**, com a fábrica anexada:
   `cd ~/PycharmProjects/aprovaos && claude --add-dir ~/PycharmProjects/fabrica-saas`
2. Leia, nesta ordem: `docs/HANDOFF.md` (quando existir) → `docs/PENDENCIAS.md` → `docs/00-visao.md` → `docs/DECISOES.md` → a fase em andamento no `PROMPT-aprovaos.md`. A spec inteira antes de qualquer fase que toque produto ou arquitetura.
3. **Estado em 14/09/2026:** Fase 0 entregue. Próximo passo: abrir a **Fase 1** — primeiro resolver P-04 (confirmar com o dono a pesquisa compartilhada com a fábrica e checar o estado dela em `fabrica-saas/docs/PENDENCIAS.md` P-14), depois as perguntas em lote da Fase 1.
4. Nenhuma fase começa antes de o dono confirmar a anterior.

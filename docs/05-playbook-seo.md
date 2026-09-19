# Playbook de SEO — landing programática do AprovaOS

> O que é: como o AprovaOS traz tráfego orgânico sem comprar mídia — a aposta programática, o
> contrato de conteúdo de cada página, o que é preciso no código e o que mede sucesso.
> Quando ler: antes de escrever qualquer página pública (fatia 13) e ao revisar o funil de
> aquisição. Fonte de mercado: `docs/01-pesquisa-mercado.md` §8; tese e corte: `docs/00-visao.md`.

## 0. O que ainda não foi medido (e por que isso não trava o playbook)

Os **volumes de busca não foram medidos** (Ahrefs free devolveu 404; o Keyword Planner exige
login de conta de anúncios — **P-12**, é o dono quem mede). Tudo que segue trata volume como
**desconhecido** e se apoia no que a rodada de pesquisa observou de fato: quem ranqueia hoje e
que formato de página ocupa cada tipo de busca. Nenhum número de volume aparece aqui inventado —
quando ele chegar, entra na tabela do §6 e a priorização é refeita com ele.

## 1. A aposta em uma frase

Não disputar as **cabeças** ("como estudar para concurso", "plano de estudos para concurso"),
onde Estratégia, CEISC e Nova Concursos ocupam o top 3 com domínio antigo e orçamento de
conteúdo. Ocupar a **cauda longa por banca × matéria × tópico**, que é longa demais para ser
escrita à mão e é exatamente o que o produto já produz como subproduto: o DNA do concurso, o
edital verticalizado e a base de questões classificadas por tópico.

> Da pesquisa §8, literal: *"uma página por banca × matéria × tópico gerada do DNA (com fonte),
> que é o que ninguém mais tem em escala"*.

## 2. As quatro famílias de página

| família | padrão de URL | de onde sai o conteúdo | exemplo de busca que ela atende |
|---|---|---|---|
| **A. Tópico por banca** | `/o-que-cai/{banca}/{materia}/{topico}` | `topico_edital` + `questao` classificadas + `dossie_topico` | "assuntos mais cobrados fgv direito administrativo" |
| **B. Concurso** | `/concurso/{orgao}-{ano}` (público, sem login) | `concurso` + `dna_concurso` + `concurso_radar` (fatia 1b) | "edital tj pr 2025 técnico judiciário conteúdo programático" |
| **C. Pergunta de formato** | `/duvidas/{pergunta}` | `dna_concurso.regra_correcao` medida em editais reais | "quantas questões tem a prova cebraspe", "cebraspe desconta erro" |
| **D. Verticalizado público** | `/verticalizado/{orgao}-{ano}` | o mesmo parser da V2 | "edital verticalizado tj pr" |

A família **D** merece cautela: a pesquisa (§8, `[seo-03]`) achou ferramenta **gratuita e sem
cadastro** que já faz verticalizado com ciclos. Ela entra porque a usuária-piloto exige o
verticalizado como básico, **não** porque diferencie — o diferencial vive em A e C.

## 3. O contrato de cada página (inegociável)

Toda página pública obedece às mesmas regras que o produto obedece por dentro. É isso que
torna a escala defensável, e não spam programático:

1. **Toda afirmação jurídica tem fonte visível e resolvível** (link para o Planalto/STF/STJ, com
   o trecho literal). É a regra 11 do `CLAUDE.md` valendo também para fora do login.
2. **Nada de número inventado.** "Esta banca cobra 12 questões de Direito Administrativo" só
   aparece se estiver medido na base; senão a página diz que não mediu.
3. **Nada gerado sem validação.** Página de família A que exiba questão exibe **original com
   origem** (banca/órgão/ano/item) ou **inédita marcada como inédita** — nunca texto de LLM solto.
4. **Uma página só existe se tiver substância própria.** O corte objetivo: família A exige
   **≥ 5 questões classificadas** naquele tópico **ou** um dossiê publicado. Abaixo disso a
   página **não é gerada** — página fina em escala é o caminho mais rápido para penalização.
5. **Sem promessa de aprovação**, em nenhuma peça (visão §6, "fora de escopo para sempre").

## 4. O que o código precisa ter (fatia 13)

- Rotas públicas (sem `exigir_usuario`), servidas pelo mesmo Jinja, sem SPA e sem JS novo.
- `<title>`, `<meta name="description">` e `<h1>` **derivados do dado**, um por página, nunca
  template com a mesma frase.
- **JSON-LD** `FAQPage` nas páginas da família C e `BreadcrumbList` em todas
  (https://developers.google.com/search/docs/appearance/structured-data).
- `sitemap.xml` gerado da mesma consulta que decide quais páginas existem (corte do §3.4), e
  `robots.txt` liberando só o que existe.
- **Canônica** explícita: um tópico que aparece em dois editais tem **uma** URL canônica (o
  `topico_relacao` da ADR-0041 é o que diz quem é o mesmo assunto — sem isso, a família A nasce
  com conteúdo duplicado).
- `Cache-Control` público e resposta sem consulta por usuário: página pública não toca sessão.
- **Sem `| safe`** em nada vindo de LLM (o defeito C3 da revisão da fatia 6 não pode reaparecer
  do lado público).

## 5. O funil da página até a conta

Cada página termina com **uma** chamada, específica da página, não um banner genérico:
- família A → "veja as {n} questões deste tópico com a explicação ancorada na lei" → cadastro;
- família B/D → "suba o edital e receba o verticalizado com o que já está coberto" → `/editais/subir`;
- família C → resposta direta acima da dobra (é busca de *featured snippet*), com o convite
  discreto embaixo.

A pesquisa (§8, `[seo-05]`) mostra que a família C é a que mais rende snippet — "quantas questões
precisa acertar na OAB (40/80)" é o exemplo medido. Snippet não converte muito, mas constrói
autoridade de domínio barato.

## 6. Priorização (a preencher com o volume da P-12)

| família | esforço | depende de | prioridade hoje | volume (P-12) |
|---|---|---|---|---|
| C — perguntas de formato | baixo (o dado já existe no DNA) | nada | **1ª** | a medir |
| A — tópico por banca | médio (corte do §3.4 + canônica) | `topico_relacao`, base classificada | **2ª** | a medir |
| B — concurso | médio | fatia 1b (radar) | 3ª | a medir |
| D — verticalizado público | baixo | V2 | 4ª (paridade, não diferencial) | a medir |

## 7. O que mede sucesso

Três números, medidos no Search Console (o dono precisa verificar o domínio — depende da P-01,
o nome, e do deploy):
1. **Páginas indexadas ÷ páginas geradas** ≥ 70 % em 90 dias. Abaixo disso, o corte do §3.4 está
   frouxo (página fina) — aperte antes de escrever mais.
2. **Cliques orgânicos por página viva**, não total: total cresce só por volume de páginas e
   engana.
3. **Cadastro por 100 cliques** por família. Se a família A não converter melhor que a D, a
   aposta do §1 está errada e o playbook muda.

Revisão do playbook: a cada 90 dias, ou quando a métrica 1 cair abaixo do corte.

## 8. Riscos

- **Penalização por conteúdo em escala sem valor**: mitigado pelo corte do §3.4 e pela canônica.
  É o risco número um de qualquer programática.
- **Marca da banca**: usar "no padrão Cebraspe" nas páginas públicas **não foi pesquisado** do
  ponto de vista de marca/INPI e concorrência desleal (pesquisa §9, P-13). Até haver resposta,
  as páginas descrevem a banca em **texto factual** ("o concurso do TJ-PR de 2025, organizado
  pelo Instituto AOCP, teve 60 questões de múltipla escolha") e **não** usam o nome da banca em
  `<title>` como se fosse selo de produto.
- **Questões de terceiros**: a pesquisa §9 registra o TJ-SP dizendo que questão de prova,
  singularmente considerada, não tem proteção autoral — mas isso é **uma** decisão, não súmula.
  As páginas públicas mostram questão **com origem completa** e link para a fonte oficial.

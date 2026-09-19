---
name: deep-research-topico
description: Use quando for pesquisar um tópico do edital para o Motor de Conhecimento e produzir ou atualizar um `DossieTopico` — "dossiê do tópico", "pesquisar a lei/jurisprudência", "atualizar dossiê por mudança de lei", "fontes para a aula" — ou ao revisar um dossiê com afirmação sem trecho literal, fonte secundária ou julgado sem número.
---

# Deep research por tópico
> O que é: o protocolo reproduzível do `pesquisador-de-topico`: fontes permitidas, ordem de busca, formato fixo do dossiê, critério de suficiência e log. Quando ler: antes de pesquisar qualquer tópico; ao auditar um dossiê.

## Princípio
O dossiê é a **única fonte** de aulas e questões inéditas; o que entrar errado nele chega a alunos. Por isso: **só fonte primária**, **todo fato com trecho literal e URL**, e **lacuna declarada** vale mais que fonte secundária. Se a fonte primária não abrir, o dossiê nasce incompleto e diz onde — nunca "compensa" com blog jurídico.

## Fontes permitidas (nesta ordem) — e só estas
| tipo | onde | o que tirar |
|---|---|---|
| Norma | **Rota A** `planalto.gov.br/ccivil_03/...` (compilado, principal — é a mais rica: mostra o texto revogado riscado ao lado do vigente, com link para a Emenda/Lei alteradora) — **exige `curl -A` com um User-Agent que contenha o token `Mozilla/5.0`** (UA híbrido `Mozilla/5.0 (compatible; AprovaOS-coletor/0.1; +contato: vlfcandido@gmail.com)` ou UA de navegador; ADR-0037); sem esse token o TLS fecha e o corpo nunca chega — isso **imita** falha de rede/ECONNRESET sem ser uma, e por isso o `WebFetch` (sem controle de UA) falha nela mesmo quando ela está no ar — use `curl` · **Rota B** Câmara: o `<id>` da URL **não é dedutível** — descubra com `WebSearch` `site:www2.camara.leg.br/legin <tipo> <número> <ano>`, pegue `…-<id>-norma-pl.html` e troque `norma` por `normaatualizada` (texto compilado e anotado "redação dada pela Lei nº …"); se o `.html` "normaatualizada" falhar (ex.: 504), tente `.pdf`/`.doc` da mesma URL-base antes de desistir da Rota B · **Rota C** LexML SRU (`lexml.gov.br/busca/SRU?...`) — em 19/09/2026 continuava devolvendo "Verificação de segurança" do Senado mesmo com UA de navegador (não é filtro de UA, é desafio de JavaScript de verdade); só vale com navegador real (Playwright/Chrome) | artigo/inciso literal + data da redação (EC/lei alteradora); `vigente`/`revogado` |
| Súmulas | `portal.stf.jus.br` (súmulas e SV) — **exige `curl -A` com UA de navegador ou o UA híbrido do coletor** (sem UA: 403); o parâmetro `sumula=<n>` da URL de uma súmula é um **ID interno, não o número** — abra primeiro o índice (`?base=30` para comuns, `?base=26` para vinculantes) e resolva o `<id>` pelo texto do link antes de montar a URL da súmula · `stj.jus.br` (súmulas, sem exigência de UA — `scon.stj.jus.br/.../VerbetesSTJ.pdf` traz todas) | número + texto integral |
| Julgados | `portal.stf.jus.br/jurisprudencia`, `scon.stj.jus.br`, informativos oficiais | classe + número (ADI 7236, RE 843.989/Tema 1199), órgão, data, tese/trecho da ementa |
| Diários | `in.gov.br` (DOU), diários oficiais estaduais/municipais | publicação e data |
| Edital/prova | base do Motor (`questao.origem`) | como a banca cobrou (banca/ano/item) |
**Vetadas** como fonte de fato: jus.com.br, conjur, jusbrasil, blogs de cursinho, Wikipedia, notícias (podem indicar onde procurar, nunca ser citadas). Doutrina só em `bibliografia`, nunca em `fontes`.

## Procedimento
1. **Delimitar**: `topico_slug`, `texto_original` do edital, lista de normas/dispositivos que o tópico cobre.
2. **Buscar na ordem**: norma compilada → súmulas → julgados citados nas súmulas/informativos → como a banca cobrou. Cada busca vai para `log_buscas` (consulta, ferramenta, resultado, data) — inclusive as que falharam.
3. **Abrir de verdade** (`curl` — não `WebFetch` na Rota A/STF, ver nota de UA acima) cada fonte citada e copiar o trecho literal. Falha de rede/SSL/403 na Rota A: **primeiro confira o `User-Agent`** (ADR-0037) antes de declarar a rota inacessível — em 17/09/2026 um `ECONNRESET` no Planalto foi registrado como falha de rede (P-15) e só em 19/09/2026 se descobriu que era filtro de UA, não instabilidade; refazer com `curl -A "Mozilla/5.0 (compatible; AprovaOS-coletor/0.1; +contato: vlfcandido@gmail.com)"` antes de qualquer outra coisa. Se a falha persistir mesmo com UA correto, registrar no log e **obrigatoriamente** tentar a Rota B (Câmara, pela busca `site:` — nunca chutar o `<id>`) e depois a Rota C antes de qualquer outra coisa. A busca `site:` conta como 1 busca; reserve 2 buscas do orçamento para ela. Se as três falharem (com UA correto testado em cada uma), o dispositivo entra em `lacunas` com `motivo: "fontes primárias A/B/C inacessíveis em <data>"` e o dossiê sai com `status: bloqueado` — como aconteceu com o LexML/Rota C em 19/09/2026, desafio de JavaScript real, não UA.
4. **Suficiência** (parar quando todos forem verdade): (a) todo dispositivo listado no passo 1 tem trecho literal; (b) toda súmula do tópico está transcrita; (c) para cada mudança legislativa dos últimos 5 anos há a redação anterior e a atual; (d) há ≥ 3 itens de prova originais do tópico referenciados (ou lacuna "sem provas na base"). Nada de "3 dimensões", "8 questões-chave" ou outro critério inventado.
5. **Vigência**: cada dispositivo com `vigente: true|false` e `redacao_de: <norma/data>`; dispositivo alterado nos últimos 5 anos ganha `atencao: "redação alterada por <lei>"`.

## O dossiê é este arquivo, nesta ordem (tabela `dossie_topico`)
```markdown
topico_id · versao · gerado_em · lacunas: [...]
## Conteúdo        ← só afirmações que apontam para F-n; tamanho alvo 600–1200 palavras
## Fontes          ← F-n · URL · "trecho literal" · tipo (norma/súmula/julgado) · vigente · redacao_de
## Como a banca cobrou   ← banca/ano/item + o que o item testou (da base; ou lacuna)
## Bibliografia    ← doutrina, sem trecho, sem alimentar afirmação
## Log de buscas   ← n · consulta · ferramenta · resultado (URL aberta / falhou: motivo) · data
```
Cada frase do Conteúdo termina com `[F-n]`. Julgado sem classe+número+data não entra em Fontes. Súmula, artigo e inciso são transcritos, não parafraseados.

## Quando a fonte primária não abre — a saída é esta, e só esta
```markdown
topico_id · versao · gerado_em · status: bloqueado
lacunas: [{dispositivo, motivo: "rotas A/B/C falharam: <erro por rota>", data}]
## Conteúdo
(vazio — nenhuma afirmação sem fonte primária)
## Log de buscas
(todas as tentativas, inclusive as que falharam)
```
Um dossiê `bloqueado` é um resultado válido e esperado; um dossiê "completo" com fontes secundárias é um defeito que chega ao aluno.

## Racionalizações que já apareceram — e a resposta
| pensamento | realidade |
|---|---|
| "Planalto/STF não abriram, compensei com estrategiaconcursos/conjur que são confiáveis" | Não são fonte de fato: entram vetadas. A saída correta era Rota B/C ou `bloqueado`. |
| "O artigo do cursinho transcreve a lei, dá no mesmo" | Transcrição de terceiro não tem `redacao_de` nem vigência; e o aluno reporta "a IA inventou lei". |
| "Notícia do STF/conjur descreve a decisão; cito a decisão" | Sem `ADI/RE + número + data + trecho da ementa` abertos no portal, o julgado não existe para o dossiê. |
| "8 achados principais cobrem o tópico" | Suficiência é (a)–(d), dispositivo por dispositivo. "Achado" não é fonte. |
| "Já gastei 6 das 8 buscas, preciso entregar algo" | Entregar `bloqueado` com o log é entregar algo. |
| "Montei a URL da Câmara pelo padrão e deu 404, logo a rota B falhou" | Rota B só conta como tentada depois da busca `site:`; URL montada de cabeça não é tentativa. |

**Sinais de alerta — pare e releia esta seção:** `estrategiaconcursos`, `conjur`, `jusbrasil`, `jus.com.br`, `migalhas`, `mattosfilho` ou qualquer `.com.br` que não seja de banca em `## Fontes`; a palavra "compensei"; F-n cujo "trecho" é um resumo e não uma transcrição.

## Verificação antes de entregar
- Zero URLs fora dos domínios da tabela em `## Fontes`.
- Zero frases no Conteúdo sem `[F-n]`; zero `F-n` sem trecho literal.
- Cada F-n foi aberta nesta tarefa (está no log com "aberta") — não "buscada".
- `lacunas` lista o que a suficiência (a)–(d) não fechou.

## Erros que este protocolo existe para evitar
- "0 WebFetch (SSL) — compensado por fontes secundárias confiáveis": jus.com.br e conjur citados como fonte de lei.
- "Ministro suspende parte da lei (Decisão STF)" — manchete no lugar de `ADI n, rel., data, trecho`.
- "Conforme conceituado em fontes jurídicas, ..." — afirmação sem fonte identificável.
- Dossiê de 2.450 palavras com seções fora do formato (questões educacionais, tabelas comparativas) e sem log de buscas.
- Declarar "completo" por critério inventado na hora.

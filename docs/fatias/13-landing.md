# Fatia 13 — Landing programática e páginas públicas: plano

> O que é: o plano da fatia 13 do PRD (`docs/02-produto.md` §6, "Landing programática +
> lançamento — Fase 6"). Quando ler: antes de executar qualquer passo desta fatia; o diário fica
> em `13-execucao.md`. O **playbook** (a estratégia, as famílias de página, o que mede sucesso)
> é `docs/05-playbook-seo.md` — este arquivo só diz **como construir**.

**Ponto de partida:** a V1 já entregou uma "landing mínima" (`web/templates/inicio.html`) e o
`base.html` serve páginas sem login. O que falta é o conteúdo público derivado do dado.

---

## 1. O corte que decide se uma página existe

Do playbook §3.4, e é a regra mais importante desta fatia: **família A (tópico por banca) só é
gerada com ≥ 5 questões classificadas naquele tópico ou um dossiê publicado.** Abaixo disso a
página não nasce. Página fina em escala é o caminho mais curto para penalização, e o corte é a
diferença entre conteúdo programático e spam programático.

### Ruling 49 — a canônica sai do `topico_relacao`, não de um slug bonito
Um tópico que aparece em dois editais (o caso real: `dir-adm-06-improbidade-administrativa` do
edital de Cascavel e `noc-dir-*` do TJ-PR) **não** pode virar duas páginas com o mesmo conteúdo.
A ADR-0041 já resolveu "quem é o mesmo assunto": a página canônica é a do tópico de maior
cobertura medida, e as equivalentes apontam `<link rel="canonical">` para ela. Sem isso a
família A nasceria duplicada consigo mesma. Custo se estiver errado: uma canônica trocada,
corrigível numa rodada.

### Ruling 50 — nome da banca só em texto factual
A pesquisa §9 registra que o uso do nome da banca ("no padrão Cebraspe") **não foi pesquisado**
do ponto de vista de marca e concorrência desleal (P-13). Enquanto isso, as páginas descrevem em
texto factual ("o concurso do TJ-PR de 2025, organizado pelo Instituto AOCP, teve 60 questões de
múltipla escolha com cinco alternativas") e **não** usam o nome da banca no `<title>` como selo
de produto. Custo: menos casamento exato com a busca; é o preço de não litigar.

---

## 2. Passo 1 — `dominio/pagina_publica.py` (puro)

```python
class PaginaPublica(BaseModel):
    caminho: str
    titulo: str            # <title>, derivado do dado, único
    descricao: str         # <meta description>, 120–160 caracteres
    h1: str
    canonica: str | None   # preenchida quando esta página é equivalente a outra (Ruling 49)
    atualizada_em: date

def montar_titulo_de_topico(materia: str, topico: str, banca: str | None, n_questoes: int) -> str: ...
def cabe_em_pagina(n_questoes: int, tem_dossie: bool) -> bool: ...
```

- `cabe_em_pagina` é o corte do §1, num lugar só, testado — não espalhado por template.
- `descricao` fora da faixa de 120–160 caracteres → `ValueError`. Meta description cortada pelo
  buscador é o defeito silencioso mais comum de programática.

**Testes red-first:** 4 questões sem dossiê → não cabe; 5 → cabe; 0 questões com dossiê → cabe;
título sem banca quando a banca é desconhecida (nunca "banca desconhecida" no `<title>`);
descrição curta/longa levanta.

## 3. Passo 2 — as rotas públicas

`api/publico.py`, **sem** `exigir_usuario` e sem tocar sessão (o playbook §4 exige resposta
cacheável):
- `GET /o-que-cai/{banca}/{materia}/{topico}` (família A)
- `GET /duvidas/{pergunta}` (família C — a resposta sai de `dna_concurso.regra_correcao` medida
  em editais reais, com o edital citado)
- `GET /verticalizado/{orgao}-{ano}` (família D)
- `GET /sitemap.xml` e `GET /robots.txt`, gerados **da mesma consulta** que decide quais páginas
  existem — sitemap que lista página inexistente é erro de indexação auto-infligido.

Família B (`/concurso/{orgao}-{ano}` público) fica para depois da fatia 1b, que traz o catálogo.

## 4. Passo 3 — o que vai dentro da página

- `BreadcrumbList` em todas e `FAQPage` na família C (JSON-LD,
  https://developers.google.com/search/docs/appearance/structured-data).
- Questão exibida **com origem completa** (banca/órgão/ano/item) ou marcada **inédita**; nunca
  texto de LLM solto, **nunca `| safe`** (o defeito C3 da fatia 6 não pode reaparecer do lado
  público).
- Toda afirmação jurídica com o trecho literal e link para a fonte — a mesma macro de citação de
  `web/templates/_macros.html`, reaproveitada.
- Uma chamada para ação por família (playbook §5), específica, no fim do conteúdo.

## 5. Passo 4 — desempenho e higiene

- Nenhum JS novo; o HTMX já vendorizado não é carregado nas públicas.
- `Cache-Control: public, max-age=3600` e `Last-Modified` a partir de `atualizada_em`.
- `<html lang="pt-BR">`, um `<h1>` por página, imagens com `alt` (se houver).
- Sem cookie na resposta pública — o que exige checar que `renderizar` não injeta sessão nessas
  rotas (se injetar, essa é a primeira correção da fatia).

## 6. Execução real (honesta)

Gerar de verdade contra o `dev.db` e registrar no diário: **quantas páginas da família A passam
do corte hoje** (com 137 questões publicáveis e 4 dossiês, o número vai ser pequeno — e é esse
número que vai para o diário), quantas da C e da D, e quantas equivalências viraram canônica.

## 7. Fora de escopo (vai para `docs/PENDENCIAS.md`)

- Search Console e medição (depende do domínio — P-01 — e do deploy).
- Família B (depende da fatia 1b) · páginas em escala real (dependem de mais base classificada)
- Volume de palavra-chave (P-12, é o dono quem mede).

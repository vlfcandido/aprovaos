# Primeiro acesso da piloto na rede local — 23/09/2026

> O que é: o que aconteceu quando a Linda abriu o AprovaOS pela primeira vez num aparelho dela,
> com as palavras dela e os números que eu medi na mesma sessão. Quando ler: antes de decidir
> qualquer coisa sobre diagnóstico, primeiro acesso, radar ou cobertura da base — é a única
> observação de uso real que existe depois da entrevista de 14/09.

## Como foi servido

O dono subiu o produto na máquina dele e a Linda acessou do tablet, pela rede local de casa
(`http://192.168.1.7:8000`), conforme a ADR-0030. Banco: `backend/dev.db` (o real, com as 251
questões), não o Postgres do Compose. Sessão sem HTTPS, cookie com `COOKIE_SEGURO=false`.

## O que ela disse (palavras do dono, relatando a sessão)

> "abrimos o projeto e ela ficou confusa, e é essa a visão que a pessoa vai ter"

> "pra dar o diagnóstico podia ser mais sucinto e objetivo, muito texto, ela não teve paciência
> pra ler tudo, e as perguntas pra equilibrar 30 ela também falou que tava cansada pra isso"

> "fora que deu muita sem questão na base, e sem dado ainda, isso que ela respondeu 30"

> "no protótipo você tinha gerado imagens e ícones pra melhorar a UI e ficar mais intuitiva,
> agora tá seca"

> "tá aparecendo muito edital, queria que a Linda tivesse visão dos dois que ela subiu
> manualmente" — sobre o radar

> "o radar precisa melhorar essa tela visualmente e filtros, tá péssima, parece que é os
> concursos dela, tem que deixar buscar"

## O que eu medi na mesma sessão (não é impressão, é contagem)

**A tela de resultado do diagnóstico** (`/diagnostico`, depois de concluída):

| medida | valor |
|---|---|
| palavras na tela | **1.777** |
| linhas de tópico | 101 |
| linhas dizendo "sem questão na base" | **63** |
| linhas dizendo "sem dado ainda" | 19 |
| linhas dizendo "a estudar" | **19** |

**81% das linhas falam de lacuna do produto, não da aluna.** A corrida dela parou em 19 itens
(a tela promete "até 30"). Alguns nomes de tópico do edital real têm mais de 60 palavras — o item
de Informática do TJ-PR lista sete leis dentro do próprio nome — e são impressos inteiros.

**A base contra o edital real** (TJ-PR / Instituto AOCP, `dev.db` em 23/09/2026):

| medida | valor |
|---|---|
| tópicos do edital | 99 |
| tópicos com questão publicável | **38** |
| questões publicáveis | 137 |
| questões sem tópico identificado | 98 |
| questões anuladas (corretamente fora) | 15 |
| dossiês | 4 · **aulas** 2 |

**O que ela via em "Meus editais":** dois editais — o **fictício** (`edital-assessor-gabinete.pdf`,
3,7 KB, escrito por um modelo para o parser de outro modelo ler) e o TJ-PR real (612 KB). O
segundo edital real do PR (TRT9/FCC) nunca tinha sido subido na conta dela. O fictício foi
removido nesta sessão (ver `docs/fatias/15-base-antes-da-medida.md` §1).

**O radar:** `GET /radar` lista **495** concursos do catálogo público da Cebraspe, sem busca e com
filtros fracos, numa tela que não deixa claro que é catálogo — parece a lista de concursos dela.

**A UI:** nenhum SVG em nenhuma tela do produto, fora os dois gráficos do painel
(`painel/_curva.html`, `painel/_previsao.html`). As ilustrações do protótipo (`art-hero`,
`draw-art`, em 10 telas dos mockups) ficaram fora na fatia 14, marcadas "fora de escopo por
decisão do dono" — decisão tomada antes de ver uma pessoa real na frente da tela.

## A ideia que saiu da sessão (do dono)

> "você não consegue buscar exatamente as mesmas questões do concurso, nesse caso que já está
> concluído, que ela já fez, que é esse que usamos? Pensei em refazer o concurso sabe, um módulo
> de estudo"

É a melhor ideia da sessão e o motivo merece ficar escrito: **a Linda já fez essa prova**. Existe
uma nota real dela como ponto de comparação — a única medida de "antes" que este produto não
consegue fabricar. Virou a ADR-0050.

## O que isto invalidou

O diagnóstico e o plano foram construídos supondo uma base que cobre o edital. Com 38 de 99
tópicos, o produto passa mais tempo dizendo o que não tem do que ensinando. Nenhuma tela conserta
isso: **é falta de questão**, e é por isso que a fatia 15 vem antes da 16.

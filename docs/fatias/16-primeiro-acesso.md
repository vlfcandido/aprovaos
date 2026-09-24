# Fatia 16 — O primeiro acesso: conduzir em vez de apresentar

> O que é: o plano da fatia que resolve o "ela ficou confusa" do primeiro acesso da piloto
> (23/09/2026). Quando ler: ao construir o assistente, o diagnóstico curto, o radar ou a passada
> visual. Depende da fatia 15: sem questão, nenhuma destas telas tem o que mostrar.

## O defeito, em uma frase

Depois de entrar, a aluna cai em `/conta` — a página menos útil do produto — e a home oferece
**sete portas** (Hoje, Radar, Painel, Meus editais, Diagnóstico, Rotina, Revisar) sem dizer por
onde começar. Quem construiu sabe a ordem; ela não. Evidência e números:
`docs/evidencias/2026-09-23-piloto-primeiro-acesso.md`.

A ordem real, que hoje só existe na cabeça de quem escreveu o código, é:
**`/rotina` → `/diagnostico` → `/hoje` → (aula · questões · revisar) → `/painel`**.
Sem `/rotina` não existe `perfil_estudo`, e sem ele não existe plano do dia.

## 1. Assistente de primeiro acesso, 3 passos (ADR-0049)

Uma tela por vez, com progresso visível, e nada mais clicável até terminar:

1. **Seu concurso** — escolher entre os editais da conta (ou subir um).
2. **Sua rotina** — horas por dia da semana, turno, energia típica, data da prova, consentimento.
   É o `POST /rotina` que já existe, quebrado em perguntas curtas.
3. **Onde você está** — o diagnóstico curto do §2.

Some para sempre quando concluído; retomável de onde parou se ela fechar. O estado de conclusão é
derivado do que já existe (`perfil_estudo` gravado, diagnóstico concluído), não de uma coluna nova
de "viu o tutorial" — menos estado, mesma resposta.

## 2. Diagnóstico curto e resultado de uma tela (ADR-0046)

- **8 a 12 itens**, parando quando a margem fecha. Hoje a tela promete "até 30" e a corrida dela
  parou em 19 — e ela disse que estava cansada antes do fim.
- **Só mede matéria que tem base.** Sortear item de Língua Portuguesa quando não há questão de
  Língua Portuguesa gasta a paciência dela para produzir uma linha em branco.
- **O resultado cabe numa tela, sem rolagem:** as 3 matérias mais fortes, as 3 mais fracas, e um
  botão "começar por aqui". A tela media 1.777 palavras.
- **A lista dos 99 tópicos sai do resultado** e volta para o edital verticalizado, que é a casa
  dela; fica um link.
- **A lacuna vira uma linha, nunca uma lista:** "61 dos 99 tópicos ainda não têm questão — estamos
  coletando". Eram 63 linhas dizendo "sem questão na base" e 19 dizendo "sem dado ainda".

## 3. Radar: catálogo público, com busca

`GET /radar` mostra 495 concursos da Cebraspe numa tela que **parece a lista de concursos dela**.
Precisa de: título e moldura que digam que é catálogo público; **campo de busca**; filtros de UF,
área e fase que funcionem como filtro de verdade; e separação visual clara de "Meus editais".

## 4. Ilustrações e ícones (ADR-0048)

Reverte a exclusão da fatia 14. O produto não tem um único SVG fora dos dois gráficos do painel,
enquanto o protótipo que a piloto validou tem ilustração em 10 telas (`art-hero`, `draw-art`, com
animação de traço respeitando `prefers-reduced-motion`). Regra da fatia 14 continua valendo:
**copie o markup do protótipo** (`docs/evidencias/mockups/telas/*.html`), não escreva CSS a partir
da descrição dele. SVG inline; nada de binário, nada de CDN.

Prioridade das telas: `/` → `/rotina` → `/diagnostico` → `/hoje` → `/editais`.

## 5. Como se prova que funcionou

Com a piloto, não com opinião: ela chega sozinha de "entrei" até "respondi a primeira questão"
**sem ninguém do lado**, e diz o que o produto decidiu por ela e por quê. Nenhuma tela do caminho
passa de uma rolagem no tablet dela.

## 6. O que fica de fora

- Tudo da fatia 15 (ter questão) — é pré-requisito, não escopo daqui.
- Áudio, grifos e anotações (P-50).
- Notificação/push (P-63, P-68) — dependem de deploy e PWA, que não existem.
- O módulo "refazer o concurso" (ADR-0050).

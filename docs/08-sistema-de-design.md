# Sistema de design do AprovaOS — o contrato dos componentes

> O que é: a regra de qual componente usar, quando, e o que cada destaque significa. Quando ler:
> **antes** de escrever qualquer linha de template ou CSS, e ao revisar uma tela. A amostra viva
> é `GET /estilo`; se esta página e o código divergirem, o código manda e este arquivo está
> desatualizado — corrija-o no mesmo commit.

## A regra que existe porque já falhamos três vezes

**Não escreva CSS a partir da descrição do protótipo. Copie o markup dele.** Cada tela validada
com a piloto está literal em `docs/evidencias/mockups/telas/<id>.html`, com o CSS em
`_estilo-do-prototipo.css`. São **evidência: nunca edite esses arquivos.**

Três defeitos caros vieram de ignorar isso: a biblioteca inteira reescrita duas vezes (fatia 14),
o ritmo vertical (`.screen { gap: 22px }`) que nunca foi portado — e por isso dois cartões
seguidos encostavam em **toda** tela —, e a quebra do shell em 720px em vez dos 900px do
protótipo, que espremia três colunas em 508px no tablet da aluna.

## 1. A hierarquia do destaque (a parte mais importante deste documento)

Cada cor de sentido quer dizer **uma** coisa. Quando tudo grita, nada é ouvido — em 23/09/2026 a
tela `/hoje` tinha três blocos âmbar empilhados e o destaque tinha virado ruído de fundo.

| destaque | token | significa | onde |
|---|---|---|---|
| **Âmbar** (`.why`) | `--cor-porque` | **o agente explicando uma decisão sua** — é a assinatura do produto | o porquê do dia; o porquê de cada bloco |
| Selo de atenção (`.chip warn`) | `--cor-alerta` | um fato que pede reação da aluna | atraso na curva, cota, prazo |
| Verde (`.chip good`) | `--cor-ok` | confirmação do que ela fez | bloco concluído, acerto |
| Vermelho | `--cor-erro` | erro dela, ou falha nossa | erro na questão, mensagem de formulário |
| Azul (`.btn primary`) | `--cor-acao` | **a** ação da tela — só uma por tela | "Começar por aqui", "Salvar rotina" |

**Regras:**
- **Um `.why` por região.** Se dois porquês competem na mesma coluna, eles viram um só texto.
- **Alerta não é explicação.** Um aviso de atraso é `.card` + `.chip warn`, nunca `.why`.
- **Um `.btn primary` por tela.** O segundo botão primário é uma decisão não tomada.
- Cor nunca é o único sinal: todo estado tem texto junto (daltonismo e leitor de tela).

## 2. Espaçamento

A escala é a do protótipo. Não invente passo intermediário; se faltar um, acrescente ao
`tokens.css` com o motivo no commit.

| token | valor | uso |
|---|---|---|
| `--espaco-1` · `--espaco-2` | 4px · 8px | dentro de um controle |
| `--espaco-2-5` | 10px | `gap` de `.stack` e `.row` — o ritmo interno de um cartão |
| `--espaco-3` · `--espaco-4` | 12px · 16px | entre campos; `gap` de grade |
| `--espaco-5-5` | **22px** | **entre blocos de uma tela** — é o `gap` de `.conteudo` |
| `--espaco-6` · `--espaco-7` | 24px · 28px | colunas do herói; padding de tela |
| `--espaco-8` · `--espaco-12` · `--espaco-16` | 32px · 48px · 64px | respiros grandes e pé de página |

**Nunca escreva um valor de espaçamento em pixel num template.** Se precisou, o componente está
faltando.

## 3. Texto

Uma família (`--fonte-titulo` para títulos, `--fonte-corpo` para o resto) e `--fonte-mono` só para
**dado** — origem da questão, hora, número de item. Mono não é enfeite: significa "isto é um
identificador, não uma frase".

| token | valor | uso |
|---|---|---|
| `--texto-rotulo` · `--texto-dado` | 11px · 12px | `.eyebrow`, dado em mono |
| `--texto-pequeno` · `--texto-controle` | 13px · 14px | apoio; texto de botão e chip |
| `--texto-base` · `--texto-medio` | 15px · 17px | corpo; `.lead` |
| `--texto-kpi` · `--texto-titulo` | 26px · maior | número do painel; título de tela |

**Medida de linha:** texto corrido usa `--medida-estreita` (52ch) ou `--medida`. A caixa da tela
cresce até 110rem; **o texto não acompanha**. Linha acima de ~80 caracteres cansa, e cansar a
aluna é o defeito que estamos consertando.

## 4. Componentes — quando usar, e quando não

**Estrutura**
- `.screen-head` — cabeçalho de tela: `eyebrow` + `h1` + uma frase + ilustração. Toda tela tem um.
- `.stack` / `.row` / `.row.between` — empilhar e alinhar. `.row` quebra sozinha; não force largura.
- `.grid-2` / `.grid-3` / `.grid-sb` — grades que colapsam para uma coluna **em 900px**.
- `.card` — agrupa o que é uma coisa só. **Não** use cartão para separar parágrafos do mesmo assunto.
- `.divider` — separa dentro de um cartão. Entre cartões, quem separa é o `gap`.
- `.vazio` — estado vazio. **Sempre com a ação que o resolve**: tela vazia é convite, não aviso.

**Dado e medida**
- `.kpis` / `.kpi` — números de topo. Número grande, rótulo pequeno, **e o intervalo em linha
  própria** — nunca grudado no número em letra miúda (era "47,6 % 18,5 %–84,7 %", ilegível).
- `.intervalo` — faixa com traço. Toda previsão mostra intervalo; previsão sem intervalo não vai
  para a tela (regra de produto, visão §4).
- `.tabela` / `.tabela-rolagem` — lista longa e comparável. Acima de ~40 linhas, corte em lotes e
  **diga o total** ("495 concursos · mostrando os 40 primeiros"), senão o corte vira mentira.
- `.mono` — só identificador.

**Controle**
- `.btn` · `.btn.primary` · `.btn.sm` · `.btn.ghost` — o rótulo diz o que acontece ("Concluir",
  não "Concluí"; "Salvar rotina", não "Enviar").
- `.seg` — escolha única e curta (energia, tipo de questão). Quebra em duas linhas quando a coluna
  aperta; nunca deixe o rótulo quebrar letra a letra.
- `.entrada` · `.campo-rotulo` — campo e rótulo. Todo campo tem rótulo visível.
- `.chip` (`accent` · `warn` · `good` · `novo`) — estado ou marca curta, nunca ação.
- `.fchip` — filtro que é link de verdade: funciona sem JS.

**Conteúdo**
- `.why` — ver §1. `.cite` — citação de lei com fonte. `.prosa` / `.prosa-estreita` — texto corrido.
- `.art` / `.art-hero` — ilustração do protótipo, SVG inline, animação só sob
  `prefers-reduced-motion: no-preference`.
- `.titulo-bloco` — título vindo de item de edital: **duas linhas e reticências**, texto inteiro no
  `title`. Item de edital pode ter 60 palavras (o de Informática do TJ-PR lista sete leis dentro
  do próprio nome).

## 5. Layout e responsividade

- **Duas quebras, só:** **900px** (a lateral vira faixa no topo; grades colapsam) e **640px**
  (a navegação vira faixa de uma linha que rola). Não invente uma terceira.
- **Caixa de conteúdo:** `.conteudo` vai até **110rem**. Medido no monitor do dono (1920px), a
  coluna tem 1657px — com o teto antigo sobravam 313px vazios à direita de toda tela.
- **Composição de duas colunas** em tela larga quando a tela tem *o que fazer* e *contexto*: o que
  fazer à esquerda, o contexto à direita, fixo (`.dia` é o exemplo). Abaixo de 900px, empilha.
- **Alvo de toque de 44px** sob `@media (pointer: coarse)` — o aparelho da piloto é tablet.
- **Nada de rolagem horizontal**, em nenhuma largura, exceto faixa marcada como rolável.

## 6. Texto de interface

- Nome de coisa é o que a aluna entende, não o que o sistema chama. Valor de domínio
  (`media`, `inscricoes_abertas`) **nunca** vai para a tela — traduza (era "Media", sem acento).
- Pendência interna não aparece na tela. "(P-39)" não quer dizer nada para ela: diga o fato.
- Lacuna nossa é **uma linha**, nunca uma lista. 63 linhas dizendo "sem questão na base" é um
  relatório sobre nós, não um diagnóstico sobre ela.
- Número sempre com unidade e, quando é previsão, com intervalo por extenso ("entre 18,5% e 84,7%").

## 7. Como conferir antes de dizer que está pronto

1. `GET /estilo` — a amostra viva de tudo que existe. Se o seu componente não está lá, ele não
   existe: acrescente à amostra no mesmo commit.
2. `bash scripts/capturar.sh` — captura as telas públicas em três larguras com o Chrome do
   sistema. Olhe as imagens: sobrou faixa vazia? rolagem horizontal? âmbar repetido na mesma
   região? (O macOS não deixa a janela descer de ~600px: abaixo disso a captura **corta** e
   parece estouro de layout sem ser. Telefone pequeno se confere no aparelho.)
3. `bash scripts/checar.sh` verde — inclui `tests/test_contrato_design.py`, que vigia sozinho o
   que dá para verificar sem olho humano: pixel de espaçamento escrito à mão, estático sem
   versão, template sem cabeçalho, mais de uma ação principal por tela, pendência interna
   vazando para a tela e `<h1>` faltando ou duplicado.
4. Pergunta final, que é a que importa: **a aluna sabe o que fazer nesta tela sem ninguém do
   lado?** Se a resposta depende de explicar, a tela ainda não está pronta.

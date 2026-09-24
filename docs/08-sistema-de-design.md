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
- `_navegacao.html` — a barra lateral. Os links são agrupados por **frequência de uso**, não por
  assunto (`.lateral__grupo` + `.lateral__rotulo`): "O dia" (todo dia), "A medida" (de tempos em
  tempos), "Meu concurso" (quando algo muda), "Ajustes" (raramente). Visitante não tem grupo —
  com quatro links, rótulo é ruído. Abaixo de 900px os grupos saem do layout
  (`display: contents`) e a faixa do topo volta a ser uma linha de links.
- `_icones.html` — os ícones da navegação, traço de 1,6 em `currentColor`. **Ícone nunca aparece
  sozinho**: o rótulo escrito vem sempre ao lado. A tela atual é marcada por três sinais (barra
  de acento `--cor-lateral-acento`, fundo sutil e peso de fonte) e nunca pela cor de ação — azul
  cheio na navegação faz o botão principal da tela disputar atenção com um item de menu.
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
- `.seg` — escolha única e curta (energia, turno, tempo por dia, tipo de questão). Quebra em duas
  linhas quando a coluna aperta; nunca deixe o rótulo quebrar letra a letra. **É o padrão de
  pergunta fechada do produto**: `<select>` só sobra para lista longa de verdade — em 23/09/2026
  os dois `<select>` de `/rotina` viraram `.seg`, porque um menu que abre esconde as opções e
  cobra dois toques onde um bastava.
- **Pergunta fechada não se digita.** Quando a resposta cabe em cinco opções, a tela oferece as
  cinco (`/rotina`: "1 h · 2 h · 3 h · 4 h+ · Não estudo") e deixa o campo numérico atrás de um
  `<details>`, como exceção. A precedência entre o atalho e o campo é decidida **no servidor**
  (`dominio/rotina.py`), nunca no navegador: a tela tem de funcionar sem JS.
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

## 6. Voz e texto de interface

**A voz é a de um mentor que já viu isso antes:** próximo, direto, sem euforia e sem sermão.
Frase curta. Segunda pessoa ("você"), nunca "o usuário". O agente fala do que **fez** e do que
**recomenda**, e assume a decisão em vez de empurrá-la para ela ("Comece por Improbidade", não
"Você deveria considerar começar por Improbidade").

- Nome de coisa é o que a aluna entende, não o que o sistema chama. Valor de domínio
  (`media`, `inscricoes_abertas`) **nunca** vai para a tela — traduza (era "Media", sem acento).
- Pendência interna não aparece na tela. "(P-39)" não quer dizer nada para ela: diga o fato.
- Lacuna nossa é **uma linha**, nunca uma lista. 63 linhas dizendo "sem questão na base" é um
  relatório sobre nós, não um diagnóstico sobre ela.
- Número sempre com unidade e, quando é previsão, com intervalo por extenso ("entre 18,5% e 84,7%").
- **Erro diz o que fazer**, não o que aconteceu. Sem "inválido", sem "falha", sem código.
- **Elogio só com fato atrás.** "Bom trabalho!" é ruído; "12 de 18 hoje — dois a mais que ontem"
  é informação que também motiva.
- **Nada de culpa.** Não existe "você perdeu", "não deixe a sequência cair", contador vermelho ou
  alerta que cobra presença. Descansar é uma recomendação válida (visão §4).

| em vez de | escreva |
|---|---|
| "Erro: campo inválido." | "Informe um número entre 1 e 16 — o dia não tem mais que isso." |
| "Você não estudou ontem." | "Ontem foi dia de descanso, e descanso conta. Hoje são três blocos." |
| "Nenhum resultado encontrado." | "Nenhum concurso com esse nome. Tente pela sigla do órgão (TJ-PR)." |
| "Enviar" | "Salvar rotina" |
| "Parabéns! Você arrasou! 🎉" | "Dia cumprido — 12 de 18 questões, dois acertos a mais que ontem." |
| "Aguarde…" | "Procurando questões deste tópico…" |

## 7. Temas e modo foco

Três temas de **primeira classe**, no botão `Tema` da lateral (`web/static/js/tema.js`), mais a
opção de seguir o sistema. O script é síncrono no `<head>` de propósito: tema aplicado depois da
primeira pintura é a página piscando na cor errada.

| tema | quando | como é |
|---|---|---|
| **claro** | dia, tela clara | fundo `#f3f5f8` — **nunca branco puro na página**; o branco é só do cartão |
| **sépia** | leitura longa (aula, dossiê, lei) | papel: creme `#f0e7d6`, tinta `#33291c`, `color-scheme: light` |
| **escuro** | à noite, depois do trabalho | `#0f1524` — **nunca preto puro** |

Regras: **todo token de cor existe nos três**. Token declarado só no claro vaza para os outros e
o defeito é invisível em revisão — por isso `test_contraste.py` reprova tema incompleto. O bloco
`@media (prefers-color-scheme: dark)` vale só para quem **não** fixou tema (`:root:not([data-theme])`).

**Modo foco** (`web/static/js/foco.js`, botão na lateral, `Esc` para sair): `data-foco="1"` no
`<html>` esconde navegação e rodapé e deixa só o conteúdo da sessão. Nenhuma tela precisa saber
que ele existe. Vale para a sessão do navegador (`sessionStorage`), não para sempre — e não há
tecla para **entrar**, porque as telas de estudo já usam A–E e C/E.

## 8. Os seis estados de todo controle

Componente sem estado é componente pela metade: quem usa não sabe se clicou, se está esperando,
ou por que não pode. Nenhum deles é só cor.

| estado | como se escreve | regra |
|---|---|---|
| padrão · foco | `:focus-visible` com anel de 2px em `--cor-acao` | o anel nunca é removido |
| **carregando** | `aria-busy="true"` (ou `.htmx-request`, que o HTMX põe sozinho) | o rótulo continua existindo para o leitor de tela |
| **desabilitado** | `disabled` | texto continua legível; se dá para explicar por quê, explique ao lado |
| **erro** | `aria-invalid="true"` + `.campo-erro` ligado por `aria-describedby` | **a frase é o primeiro sinal**, a borda vermelha é o segundo |
| **vazio** | `.vazio` | sempre com a ação que resolve: tela vazia é convite |
| **esqueleto** | `.esqueleto` + `aria-busy` na região | com o tamanho do conteúdo real, senão a página pula |

**Progresso** (`.progresso`, `.bar`, `.anel`): toda sessão declara onde termina, com o número
escrito ("Questão 7 de 12") — barra sem número é decoração. É o mecanismo aprovado na ADR-0051.

## 9. Contraste: medido, não prometido

`GET /estilo` mostra a tabela **calculada a partir do `tokens.css` na hora da requisição**, e
`backend/tests/test_contraste.py` reprova a suíte inteira se um par cair. O contrato é a WCAG 2.2
AA: **4,5:1** para texto (1.4.3) e **3:1** para limite gráfico e de controle (1.4.11).

- Cor nova no sistema = par novo em `PARES_OBRIGATORIOS` (`aprovaos/dominio/contraste.py`). Cor
  que ninguém mede é cor que ninguém garante.
- Quando reprovar, **o conserto é o valor do token**, nunca o mínimo do teste.
- Quando a cor de marca não alcança 4,5:1 como texto, ela não vira texto: nasce um token
  irmão. É o caso de `--cor-porque` (a barra âmbar, 3,30:1) e `--cor-porque-texto` (o texto
  sobre âmbar, 4,52:1). Assim a assinatura do produto fica de pé e o texto fica legível.
- **Exceção declarada:** `--cor-linha` (1,38:1) é separador **decorativo** — cartão e divisória
  não carregam informação. Limite que a aluna precisa enxergar para achar o controle usa
  `--cor-linha-forte` (3:1), que é o que a borda de campo usa.

## 10. Cor por matéria

`--materia-1` a `--materia-9`, da paleta de Okabe & Ito ("Color Universal Design",
<https://jfly.uni-koeln.de/color/>), desenhada para ser distinguível nas três formas de
daltonismo e escurecida aqui até cumprir 3:1 contra as superfícies de cada tema. Uso:
`<span class="materia-marca" data-materia="3"></span>` **sempre** ao lado do nome da matéria —
cor nunca é o único sinal. Nove porque o edital real em uso (TJ-PR/Instituto AOCP) tem nove
matérias; acima disso, repita os tons em vez de inventar cor não medida. Se um dia houver um
segundo exame (fase 2, visão §6), a escala vale igual: muda quantas matérias caem em cada tom.

## 11. O que este sistema não tem, de propósito

- **Ofensiva/sequência diária: nunca** (ADR-0051). Ela existe para punir quem descansa, e
  "descansar é uma recomendação válida" é princípio inegociável (visão §4). O que ocupa esse
  lugar é **"Dia cumprido"** e a fila com tamanho declarado.
- **Pontos, XP e medalhas:** pós-MVP. **Ranking e social:** fase 3 (visão §6). Não construa
  agora; o sistema aceita os dois depois sem reforma, porque o progresso já é um componente.
- **Modal:** não existe. Uma tela responde uma pergunta; decisão que merece interromper merece
  tela. (A referência legal é popover, não modal.)
- **Confete, som e animação de comemoração:** a recompensa é uma frase curta. Clima calmo.
- **Componentes do lado B** (professor, turma, dashboard agregado) e de um segundo exame: fase
  2/3. Nada deles entra na biblioteca antes de existir produto para eles.

## 12. Como conferir antes de dizer que está pronto

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

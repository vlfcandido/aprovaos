# Fatia 14 — Biblioteca de componentes e usabilidade: diário de execução

> O que é: o que de fato aconteceu ao executar `14-ui.md`, fatia por fatia (esta entrada cobre só
> o **grupo A** — `.superpowers/sdd/14-ui/grupo-a-questoes.md`, o fluxo de responder questão).
> Quando ler: para saber por que o código do grupo A ficou como ficou, ou para retomar de onde
> parou. As outras frentes da fatia 14 (biblioteca em si, grupo C — medida — e as demais telas do
> protótipo) têm o próprio registro; este arquivo não fala por elas. A **§6** é a única exceção:
> não é da fatia 14, é o defeito de configuração que apareceu ao servir a piloto na rede local
> (23/09/2026) e não tinha diário próprio onde morar.

**Contexto da sessão:** outro agente trabalhava, em paralelo, em
`api/{diagnostico,painel}.py`, `dados/repositorio_{diagnostico,painel}.py`,
`dominio/previsao.py` e `web/templates/{diagnostico,painel}/` — nenhum desses arquivos foi
tocado aqui. `questoes/_cartao_questao.html` e `questoes/_resultado.html` são compartilhados com
`api/diagnostico.py` (que os reaproveita sem `{% extends %}`, "responder no diagnóstico é, na
prática, responder a questão de novo") — toda mudança nos dois parciais foi conferida contra
`tests/test_rota_diagnostico.py` também, sem editá-lo.

## 1. Reprodução do defeito nº 1 antes de mexer em qualquer linha

Subi o app (`sqlite:///dev.db`, `AMBIENTE=dev`), logei como a usuária-piloto (senha local trocada
só no `dev.db`, nunca commitado — está em `.gitignore`) e reproduzi ao vivo, por `curl`, o que o
dono viu no navegador:

- `POST /topico/{slug}/questoes` sem `confianca` devolvia **400** com JSON cru
  (`{"codigo":"dados_invalidos", ...}`), **com ou sem** `HX-Request: true`. O htmx 2 só troca o
  DOM em respostas 2xx — em erro, ele descarta a resposta e não faz nada visível. É exatamente o
  "clicar numa alternativa sem marcar certeza/dúvida antes não fazia absolutamente nada" que o
  dono relatou. O código já tinha, para o caso de `questao_id` obsoleto, o comentário certo
  ("um 4xx aqui vira JSON cru fora do htmx e não faz swap nenhum dentro dele") — só não tinha
  sido aplicado ao caso da `confianca`.
- `origem` saía com `"cebraspe"` minúsculo e `"CARGO 19"` cru (edital fictício da V3/ADR-0027,
  achado já registrado no `CLAUDE.md`).
- Uma questão sem `justificativa_certo`/`justificativa_errado` caía num `"Você errou."` seco.
- Não havia "questão N de M" nem afordância/`aria-label` nas alternativas A–E.

Todos os itens da tabela do plano §2.2 relativos a "Questão" foram confirmados ao vivo antes de
escrever qualquer correção — nenhum foi assumido só pela leitura do plano.

## 2. A correção do defeito nº 1 — dois níveis, como o brief pediu

**Servidor (o que garante o resultado, com ou sem JS):** em `responder_questao` e
`responder_revisao` (`api/questoes.py`), a checagem de `confianca` deixou de vir antes da questão
ser resolvida e de levantar `HTTPException(400)`. Agora ela vem depois de confirmar que a questão
(ou o cartão) ainda está pendente, e — se `confianca` for inválida — a rota devolve **200**
renderizando `questoes/_cartao_questao.html` de novo (a mesma questão, o mesmo formulário) com
`erro=MENSAGEM_CONFIANCA_OBRIGATORIA`. Nada é gravado; a aluna tenta de novo. Mesmo padrão nos
dois pontos (fluxo nativo e intercalado do fio da memória).

**Ilha de JS, só reforço (ADR-0019):** `web/static/js/confianca-questao.js` desabilita de
verdade (`disabled = true`) os botões de resposta até um rádio de `confianca` ser marcado, e
esconde a linha de aviso (`[data-aviso-confianca]`, sempre visível por padrão para quem não tem
JS) quando ela deixa de ser necessária. Ganha em `htmx:afterSwap` para continuar funcionando
depois de cada troca de `#questao`. Decisão consciente: **não escrevi teste de JS** — o repositório
não tem harness de teste para JS (sem `package.json`/`vitest`/`playwright`); o comportamento que
não pode falhar (a tela nunca fica muda) está garantido e testado no servidor, com ou sem esta
ilha. Registro isto explicitamente para quem revisar decidir se vale montar o harness.

`#questao` ganhou `aria-live="polite"` em `topico.html`/`revisao.html`: sem isso, mesmo com o
servidor não sendo mais silencioso, um leitor de tela não saberia que o conteúdo mudou depois de
um `hx-swap`.

O controle de certeza/dúvida trocou de `.confianca`/`.segmentado` (só existiam em `base.css`, sem
equivalente na biblioteca) para `.seg` de `web/static/css/componentes.css` — o mesmo markup
(`label` + `input[type=radio]`) da amostra em `/estilo`, copiado de lá.

## 3. Os outros defeitos da tabela §2.2 (todos corrigidos, todos com teste)

- **Origem legível:** `_formatar_banca`/`_cargo_exibivel` (novas, `api/questoes.py`) — banca com
  nome próprio só para o mapa conhecido (`cebraspe`→`Cebraspe`, `fgv`→`FGV`; qualquer coisa fora
  do mapa **não** é reformatada, para não transformar uma sigla como `AOCP` em `Aocp`); cargo
  omitido só quando bate exatamente o padrão `CARGO \d+` do rótulo interno do coletor — um cargo
  de verdade nunca é tocado. Aplicado uma vez em `contexto_questao`, então vale para
  `_cartao_questao.html`, `_resultado.html` e (de graça) para `diagnostico/andamento.html`.
- **"Questão N de M":** `repositorio_questao.posicao_na_fila` (nova) — mesmos filtros de
  `proxima_questao`, só que conta em vez de escolher. Aparece em `_cartao_questao.html` quando a
  questão é nativa do tópico da URL (omitido no item intercalado do fio da memória, cuja posição
  seria a do tópico de origem, não a desta tela) e não aparece em `/revisar`/no diagnóstico (não
  fazem sentido como fila fixa).
- **Honestidade sem justificativa:** `_resultado.html` mostra "Ainda não temos uma explicação
  escrita para este item — o gabarito acima já é a fonte oficial." nos dois tipos de questão,
  nunca um `"Você errou."` sozinho. Isto **mudou o contrato de dois testes existentes**
  (`test_resultado_certo_errado_sem_justificativa_*` e
  `test_multipla_escolha_resultado_marca_alternativas_sem_inventar_justificativa`, que antes
  afirmavam justamente que nada aparecia) — decisão do próprio plano (§2.2: "diga que ainda não
  há explicação... honestidade é o produto"), não uma invenção minha; os testes foram reescritos
  para verificar a nova mensagem, não removidos.
- **Reportar erro recolhido:** o `<textarea>` sempre aberto virou um `<details>` com
  `<summary>Encontrou um erro nesta questão?</summary>` — some da dobra até alguém clicar.
- **Sem `→` colado no nome do botão:** o link "Próxima questão" ganhou `aria-label` sem seta (o
  `<kbd aria-hidden="true">→</kbd>` continua visível, só não entra no nome acessível) e virou
  `.btn.primary` (antes `.botao.botao--secundario`).
- **`aria-label` nas alternativas A–E:** `aria-label="Responder {letra}: {texto}"` em cada botão.

## 4. Componentes que a biblioteca ainda não tem (relato, não decisão minha)

Não editei `componentes.css` (regra da fatia). O protótipo (`s-questoes.html`) usa vários
componentes que **não existem** em `web/static/css/componentes.css` hoje: `.question`
(tipografia do enunciado em destaque), `.ce` (os dois botões grandes Certo/Errado), `.dots`
(pontinhos de progresso da lista), `.fio` (o card acentuado de "fio da memória" — diferente do
`.why`, que é o "porquê" do agente), `.foot-nav`, `.fsrs`/`.flash` (revisão espaçada e
flashcard). Também falta o `table`/`th`/`td` genérico que o protótipo estiliza sem classe.

Para o que **já existe** na biblioteca, portei: `.card.lift`, `.stack`, `.row.between`, `.chip`
(`accent`/`warn`/`novo` — substituem exatamente `.selo--fio-da-memoria`/`.selo--inedita`/
`.selo--porque`, cores idênticas, confirmadas nos tokens), `.seg`, `.mono`, `.small`, `.muted`,
`.btn`/`.btn.sm`/`.btn.primary`, `.entrada`, `.campo-rotulo`, `.mensagem.mensagem--erro` (esta
última é de `base.css`, já usada em 8 outras telas do produto, não do protótipo). O que não tem
equivalente ainda (`.questao__*`, `.alternativa*`, `.botao-resposta`, `.resultado__gabarito*`,
`.justificativa*`, `.tabela-justificativa`, `.citacao-legal`, `kbd`) continua vindo de `base.css`
— não há como portar para o protótipo sem editar um arquivo fora do meu escopo, e essas classes já
davam hover/foco/cor semântica razoáveis (só faltava `aria-label` e o bloqueio de confiança, que
são comportamento, não CSS).

**O que eu não portei do protótipo, e por quê:** a coluna direita de `s-questoes.html` inteira —
o timer por item, os pontinhos de progresso da lista, o cartão de revisão espaçada com flashcard
virável e os quatro botões do FSRS, e o painel de estatísticas "hoje nesta lista" (acertos,
líquidos, tempo médio, "certeza que virou erro"). Nenhum desses tem hoje um dado real por trás no
backend (tempo por item não é medido em tempo real, não há agregação de "hoje" pronta) e o brief
do grupo A não pede — pede portar "o cartão de questão, a origem em mono, o resultado com as duas
justificativas, a citação `.cite` e o selo do fio da memória", que é o que este grupo entregou.
Extrapolar para a coluna direita seria inventar dado ou UI sem lastro; fica para quando alguém
decidir que vale a pena medir tempo por item de verdade.

## 5. Verificação

`cd backend && uv run pytest` (arquivos tocados): verde. `bash scripts/checar.sh` completo:
ruff/ruff format/mypy/import limpo; `pytest` da suíte cheia deu **1194 passed, 2 failed, 6
skipped** — as 2 falhas são em `tests/test_repositorio_edital.py` (`"LÍNGUA PORTUGUESA"` vs.
`"Língua Portuguesa"`), só aparecem quando a suíte roda **inteira** (passam isoladas) e
desaparecem completamente ao deselecionar os arquivos de teste que o outro agente estava editando
em paralelo (`test_dominio_previsao.py`, `test_repositorio_painel.py`, `test_rota_painel.py`,
`test_rota_diagnostico.py`) — confirmado rodando a suíte sem eles: **1157 passed, 6 skipped, 0
failed**. Não são deste grupo nem deste escopo (mesmo padrão já registrado na fatia 10, "1 falha
pré-existente de trabalho concorrente de outro agente").

Conferido ao vivo no navegador (via `curl`, com sessão de cookie real contra `dev.db`): tela de
certo/errado, tela de múltipla escolha, resposta sem confiança (200, aviso visível, formulário
intacto para tentar de novo), resposta certa e errada nos dois tipos, questão sem justificativa,
origem com cargo interno omitido. Não subi navegador gráfico — a verificação visual foi por HTML
renderizado, não por captura de tela.

## 6. Fora do grupo A: o defeito que apareceu ao servir a piloto na rede local (23/09/2026)

Não é trabalho da fatia 14 — está aqui porque apareceu ao pôr o produto no ar para a Ana
testar do tablet dela (ADR-0030: "a Ana usa o produto na máquina/rede do dono") e não tinha
diário próprio onde morar.

**O sintoma:** subir o servidor pela raiz do repositório (`uvicorn aprovaos.main:criar_app`,
`--host 0.0.0.0`, sem Docker) morria no arranque com
`RuntimeError: Directory 'static' does not exist`.

**A causa:** variável **vazia** no `.env` não é variável **ausente**. O `.env` traz `WEB_DIR=`
(e `UPLOADS_DIR=`, `DOCUMENTOS_DIR=`, `GOOGLE_API_KEY=`, as duas do OAuth e as duas do Mercado
Pago), e o pydantic-settings entrega a string vazia — que cada campo opcional converte num valor
que **parece preenchido**:

- `Path("")` é `Path(".")`, que é *truthy*: `config.web_dir or raiz / "web"` (`main.py:61`) nunca
  cai no padrão, e o `StaticFiles` recebe `./static`, que não existe.
- `SecretStr("")` **não é `None`**: os seis agentes passam pelo `if config.google_api_key is
  None` e montam `genai.Client(api_key="")`. Em vez de degradar para regras — a promessa
  explícita da ADR-0030, "o roteador degrada em vez de falhar" — eles falhariam com erro de
  autenticação. Pelo mesmo caminho, `MERCADO_PAGO_ACCESS_TOKEN=` tiraria o billing do estado
  desligado com um token vazio, e `/assinar` deixaria de devolver 404 (fatia 12, Ruling 46).

Ou seja: os dois campos que mais importam estar desligados eram os que ligavam sozinhos. Cada
linha do `.env.example` promete "vazio = …" e nenhuma delas era verdade fora do Compose — só não
tinha aparecido porque o `Dockerfile` passa `WEB_DIR=/web` explícito e ninguém tinha subido pela
raiz ainda.

**A correção:** um validador só, `Configuracoes._vazio_e_ausente` (`config.py`, `mode="before"`
sobre os 8 campos opcionais), que trata string vazia ou só de espaços como ausente. Campo
obrigatório não entra: `DATABASE_URL=` vazio continua sendo erro de validação. Red primeiro —
o teste parametrizado (`tests/test_config.py`) falhou nos 8 campos antes de existir validador, e
o par "valor real continua chegando" passou desde o início, provando que a correção não apaga
valor bom. Suíte: **1228 passed, 6 skipped** (eram 1204), `scripts/checar.sh` verde.

**Como servir a piloto na rede local**, já com isto no lugar (os dados reais estão no
`backend/dev.db`, não no Postgres do Compose):

```bash
DATABASE_URL="sqlite:///$PWD/backend/dev.db" \
  backend/.venv/bin/uvicorn aprovaos.main:criar_app --factory --host 0.0.0.0 --port 8000
```
O `.env` já traz `COOKIE_SEGURO=false` — sem isso o cookie de sessão sai com `Secure`, o tablet
acessa por `http://` e o navegador **descarta o cookie**: ela loga e volta para o login, sem erro
visível. `caffeinate -dis` enquanto durar a sessão, ou o Mac dorme e derruba o servidor.

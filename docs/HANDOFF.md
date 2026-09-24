# HANDOFF do AprovaOS — o que é, como mexer, e onde estão as minas

> O que é: o documento que um modelo (ou uma pessoa) lê **primeiro** ao abrir este repositório
> sem contexto nenhum. Quando ler: sempre, antes de qualquer coisa. Se algo aqui divergir do
> código, **o código manda** e este arquivo está desatualizado — corrija-o no mesmo commit.

## 1. Em uma página

O AprovaOS é um agente de estudo para concurso público que **assume a responsabilidade pelo
resultado**: a aluna sobe o edital dela, o produto entende o edital, decide o que ela estuda
hoje, explica **por quê**, mede se funcionou e reajusta. O que o distingue de cursinho e de
aplicativo de questões é uma coisa só, e é dela que sai quase toda decisão técnica deste
repositório:

> **Nada gerado chega ao aluno sem validação. Toda afirmação jurídica tem fonte literal.
> Toda previsão vem com intervalo.**

Quando você tiver de escolher entre entregar mais rápido e cumprir essa frase, cumpra a frase.
Todo defeito caro deste projeto veio de violá-la sem perceber — não de violá-la de propósito.

- **Dono:** Vinicius, engenheiro sênior, projeto paralelo, **poucas horas por semana**. Ele
  revisa e decide; o modelo faz o grosso.
- **Usuária-piloto:** Linda, concursos locais em Cascavel-PR, matérias de Direito.
- **Spec:** `SPEC-aprovaos.md` · **visão e regra de corte:** `docs/00-visao.md` ·
  **PRD e tabela de fatias (fonte única de rastreio):** `docs/02-produto.md` §6 ·
  **decisões:** `docs/DECISOES.md` · **o que ficou para depois:** `docs/PENDENCIAS.md`.

## 2. Como rodar

```bash
cp .env.example .env            # preencha CHAVE_SECRETA
docker compose up -d --build
```
Abra **`http://127.0.0.1:8000`** — não `localhost`: o listener do container responde em IPv6 e
o `localhost` do macOS resolve para lá primeiro. Se já houver Postgres local na 5432, mude
`POSTGRES_PORT` no `.env`.

Sem Docker:
```bash
cd backend
DATABASE_URL=sqlite:///dev.db CHAVE_SECRETA=… uv run alembic upgrade head
DATABASE_URL=sqlite:///dev.db CHAVE_SECRETA=… uv run uvicorn aprovaos.main:criar_app --factory
```

**A checagem completa é o CI.** Rode antes de qualquer commit, da raiz:
```bash
bash scripts/checar.sh          # ruff · ruff format · mypy --strict · import sem efeito colateral · pytest
```

Com `GOOGLE_API_KEY` no `.env`, os caminhos com IA ligam. **Sem ela, tudo continua funcionando**
— por construção: DNA por regras, classificação por léxico, plano do dia determinístico, painel
sem LLM. Isso não é elegância, é sobrevivência: o free tier dá 20 requisições/dia por modelo.

## 3. O mapa mental do código

```
backend/aprovaos/
  dominio/     # funções e modelos PUROS. Sem banco, sem rede, sem relógio, sem LLM.
               # Data e hora entram por parâmetro. É aqui que moram as regras do produto.
  dados/       # SQLAlchemy 2.0 + repositórios. Uma consulta por conceito, com a trava da P-34.
  api/         # rotas FastAPI que devolvem HTML (Jinja) — e pouquíssimo JSON.
  agentes/     # LlmAgent do ADK, em JSON mode. Um arquivo por família de prompt.
  motor/       # comandos de linha (coletar, curar, dossiê, aula, justificar, plano, calibrar).
  roteador/    # custo por chamada e TetoDiario (R$ 3/dia) — a trava que protege o bolso.
web/           # Jinja + HTMX vendorizado + CSS por tokens. Sem SPA, sem build.
knowledge/     # fontes.yaml (fichas do coletor) e fixtures reais (editais, provas, leis).
docs/fatias/   # um plano e um diário por fatia. O diário registra o que rodou DE VERDADE.
```

**A regra de ouro do domínio:** se uma função em `dominio/` precisa saber que horas são, está
errada — a hora entra por parâmetro. Isso é o que torna todo o produto testável sem mock e
reprodutível sem sorte.

## 4. As sete minas deste repositório

Estão aqui porque cada uma **já explodiu** e custou caro. Não são hipóteses.

1. **Regex que acha o termo mas não o conceito.** Quatro campos do DNA saíram *errados com cara
   de certo* (banca, desconto por erro, mínimo por matéria, órgão) porque a expressão procurava
   uma palavra no documento inteiro e aceitava o primeiro parágrafo que a contivesse. Regra que
   saiu daí (**ADR-0036**): *a cláusula tem de conter o conceito, não só o termo; na dúvida,
   lacuna declarada.*
2. **Fixture escrito para o parser.** O `edital-assessor-gabinete.pdf` é fictício — um modelo
   escreveu o edital que o outro sabia ler — e ficou sendo a base de medição por dois dias
   **depois** de existirem editais reais no repositório. Material real do dono vai para o
   caminho principal **imediatamente**, não vira só fixture.
3. **Vocabulário de tópico é por edital.** Dossiês e aulas ficaram presos aos slugs de um edital
   enquanto as questões migraram para os de outro: conteúdo caro que não chegava à aluna.
   Resolvido por `topico_relacao` (**ADR-0041**). Toda leitura por tópico atravessa a relação —
   se você escrever uma consulta nova por `topico_id` direto, provavelmente está recriando o bug.
4. **Validar só o que o modelo resolve declarar.** O validador da aula conferia as citações que
   o próprio modelo escolhia declarar: uma aula com zero citações passava. Hoje há um **gate
   léxico** (frase normativa sem citação reprova).
5. **Rede de segurança que vira descarte silencioso.** O extrator de lei passou a jogar fora, sem
   erro, uma classe inteira de entrada. Preferimos **falhar alto** (`EstruturaNaoTratada`) a
   entregar um inciso engolido com aparência de texto correto. **Aconteceu de novo em 23/09/2026** (P-76): `curar --reclassificar` estoura um erro de
   contexto assíncrono, trata o crash como "não consegui classificar" e **apaga a
   classificação já gravada** — publicáveis caíram de 138 para 39 numa rodada. Falha de
   classificação tem de **preservar** o que já estava lá.
6. **Dois nomes para o mesmo conceito.** "Dominado" tinha duas definições (uma exigia 3
   respostas, a outra nenhuma), em módulos que se alimentam. Antes de criar um limiar, procure se
   ele já existe.
7. **Número que parece intervalo e não é.** O `± margem` do diagnóstico mede **cobertura**, não
   precisão. O painel usa **intervalo de Wilson** de verdade. Se um número vai para a tela como
   confiança, ele nasce de `dominio/estatistica.py`.

## 5. Como se trabalha aqui

As regras completas estão no `CLAUDE.md` e são inegociáveis. As quatro que mais pegam quem chega:

- **TDD red-first.** Escreva o teste, **rode**, veja falhar pelo motivo certo, só então
  implemente. "Eu sei que ia falhar" não conta.
- **Português do Brasil** em tudo: código, docstring, commit, UI, resposta.
- **Nenhum efeito colateral em import.** Existe um passo do `checar.sh` só para provar isso.
- **O que não der para fazer vai para `docs/PENDENCIAS.md`** com o motivo. Nunca improvise no
  lugar — improviso vira dado errado com cara de certo, que é a mina nº 1.

Decisão de arquitetura vira **ADR** em `docs/DECISOES.md` (curta: decisão, alternativas, porquê).
Decisão tomada durante a execução de uma fatia vira **Ruling** no diário da fatia, com o custo de
estar errada.

## 6. O que depende do dono (e por isso não está feito)

Nenhum destes é falta de tempo; todos saem da máquina dele:

| trava | o que destrava | onde |
|---|---|---|
| **Nome e domínio** | Search Console, e-mail, link de convite | P-01 |
| **Repositório remoto** | backup e o CI que nunca rodou | P-19 |
| **Deploy (VPS + Caddy)** | a piloto usar de onde ela está | ADR-0020/0030 |
| **Billing do Gemini** | gerar conteúdo em volume | — |
| **Credenciais Mercado Pago** | existir "pagante" para medir | ADR-0025, P-02 |
| **Credenciais Google OAuth** | login com Google (código pronto, desligado) | Ruling 42 |
| **E-mail de autorização à FGV** | coletar provas da FGV | P-13 |
| **Edital real da piloto** | mirar no concurso dela, não num parecido | **P-17** |

## 7. Estado e números

<!-- ATUALIZE ESTA SEÇÃO A CADA FIM DE FATIA -->
Ver a tabela de fatias em `docs/02-produto.md` §6 (fonte única de rastreio) e o diário de cada
fatia em `docs/fatias/`. Os números da base real (`dev.db`) e o que está no ar estão no
`CLAUDE.md` §"Como continuar o trabalho", item 3, que é atualizado no mesmo commit da fatia.

## 8. Se você só tem 10 minutos

Leia, nesta ordem: este arquivo → `docs/PENDENCIAS.md` (o que falta e por quê) →
`docs/02-produto.md` §6 (onde o trabalho parou) → o plano da fatia em andamento em
`docs/fatias/`. Só então abra código.

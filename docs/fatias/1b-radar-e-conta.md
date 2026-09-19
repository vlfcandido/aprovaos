# Fatia 1b — Radar de editais, meus concursos e Google OAuth: plano

> O que é: o plano da fatia 1b do PRD (`docs/02-produto.md` §6, linha "Radar/catálogo
> Cebraspe+FGV, Google OAuth" — F1.1, F1.2, F1.3, RF-20). Quando ler: antes de executar qualquer
> passo desta fatia e ao revisar o que foi feito; o diário fica em `1b-execucao.md`.

**Ponto de partida:** a fatia 10 (painel) entra antes; a base é a `main` com `scripts/checar.sh`
verde. Já existem e são reaproveitados: `motor/fontes/cebraspe.py` (`FonteCebraspe`, cliente HTTP
por `Protocol`, User-Agent da ADR-0037), `knowledge/fontes.yaml` (ficha da fonte, status `ativa`),
`motor/coletar.py::cargo_de_direito` (léxico de cargo), `perfil_estudo`
(`concurso_principal_id`, `concursos_acompanhados` — coluna JSON que nasceu `[]` na fatia 7
justamente para esta fatia), `dados/repositorio_perfil.py`, `api/conta.py` (cadastro/login por
e-mail+senha, cookie HMAC da ADR-0026).

---

## 1. O que eu verifiquei na API antes de planejar (19/09/2026, evidência no repo)

Medido de verdade, não suposto. Evidências salvas em
`knowledge/fixtures/fontes/cebraspe/catalogo-todas-as-fases-2026-09-19.json` e
`evento-AGEPAR_PR_26-2026-09-19.json`.

- **Um único GET traz o catálogo inteiro**: `GET /cebraspe/eventos/tipo/concursos` devolve uma
  lista de **grupos de fase**, cada um com `faseEvento`, `ordem` e `eventos[]`. Medido hoje:
  `Novos` 1 · `Inscrições Abertas` 8 · `Em Andamento` 63 · `Encerrados` 424.
- **O caminho por fase existe mas o nome não é óbvio**: `/fase/encerrado` funciona (é o que a V3
  usa), `/fase/em-andamento` funciona, e `/fase/andamento`, `/fase/aberto`, `/fase/todos`
  devolvem **HTTP 200 com `[]`** — não 404. Ou seja, **errar o nome da fase não dá erro, dá lista
  vazia**: é exatamente a classe de defeito da ADR-0036 (aparência de certo). Por isso o radar
  usa o endpoint sem fase e lê `faseEvento`/`eventoStatus` do próprio corpo.
- **O detalhe tem o que o catálogo precisa**: `GET /cebraspe/eventos/{eventoURL}` traz
  `eventoNomeCompleto`, `eventoTotalVagas`, `strEventoSalarioMaximo`, `eventoCargos[]`,
  `arquivosEdital[]` (com `dataArquivoObj`, horário de Brasília — ADR já registrada na V3) e
  `periodoInscricao` como **texto literal**: `"De 23/07/2026 até 21/08/2026 às 18:00, horário
  oficial de Brasília/DF"`.
- **Data da prova não existe na API.** Está dentro do PDF do edital. É **lacuna declarada** no
  catálogo, não um campo vazio com cara de "ainda não marcada".

### Ruling 38 — o radar coleta Cebraspe; FGV continua vetada
A fatia se chama "Cebraspe+FGV", mas os termos da FGV vedam automação (Fase 1, P-13) e o pedido
de autorização é ato do dono (lista final, §1.4). Decisão: entregar o radar **só com a Cebraspe**,
com a FGV aparecendo no catálogo como **fonte vetada, dita na tela**, e não como ausência
silenciosa. Custo se estiver errado: nenhum — o dia em que a autorização chegar, entra uma ficha
nova em `knowledge/fontes.yaml` e um módulo em `motor/fontes/`, sem tocar no resto.

### Ruling 39 — UF só quando confirmada, nunca chutada
O nome vem como `"AGEPAR PR 26"`/`"CAMARA MUNICIPAL PONTA PORA MS 26"`; a UF é um token no meio
do nome. Decisão: declarar `uf` só quando o token de duas letras for **exatamente** uma das 27
UFs **e** aparecer também como token isolado no `eventoURL` (que separa por `_`). Sem as duas
confirmações, `uf=None` e o concurso aparece **sem** UF. Nunca uma UF errada — é o mesmo
princípio da ADR-0036. Custo: concursos federais (AGU, Câmara dos Deputados, ANTAQ) ficam sem UF,
que é o certo.

### Ruling 40 — "combina com o perfil" filtra, nunca esconde
O catálogo mostra **tudo**; o casamento com o perfil é um **selo** e uma ordenação, com o motivo
escrito ("combina: PR, salário acima do seu mínimo, cargo de Direito"). Nenhum concurso some da
lista por causa do perfil. Custo se estiver errado: a lista é mais longa; a aluna não perde
oportunidade por um filtro que ela não sabia que estava ligado.

### Ruling 41 — alerta por perfil é na tela; e-mail/push fica para o deploy
F1.2 pede e-mail/push. Enviar e-mail exige credencial de SMTP e um domínio no ar — as duas coisas
saem da máquina do dono (lista final, §1.2). Decisão: o alerta nasce **dentro do produto**
(selo "novo para você" no radar e no `/hoje`), com o mesmo teto de 1/dia por construção
(recomputado, não enfileirado). Vai para `docs/PENDENCIAS.md` a parte de e-mail/push.

### Ruling 42 — Google OAuth entra pronto, atrás de configuração
Não posso criar credencial no Google Cloud do dono. Decisão: implementar o fluxo inteiro
(`/entrar/google` → consentimento → callback → conta ligada por e-mail verificado), lido de
`GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET`; **sem as duas variáveis, o botão não
aparece** e nada muda. Testes contra um provedor falso no mesmo molde de `_ClienteHttp` que a
`FonteCebraspe` já usa. No dia em que ele colar as credenciais no `.env`, funciona. Custo se
estiver errado: código que nunca roda em produção até ele decidir — mas testado e inerte.

---

## 2. Passo 1 — `dominio/radar.py` (puro)

```python
class ConcursoDoRadar(BaseModel):
    evento_url: str          # identidade estável na fonte
    nome: str
    ano: int | None
    fase: Literal["novos", "inscricoes_abertas", "em_andamento", "encerrado"]
    uf: str | None           # Ruling 39
    vagas: int | None
    salario_max_brl: Decimal | None
    periodo_inscricao_texto: str | None
    inscricao_inicio: date | None
    inscricao_fim: date | None
    lacunas: list[str]       # "data da prova não publicada na API", "vagas não informadas"…

def ler_catalogo(payload: object) -> list[ConcursoDoRadar]: ...
def extrair_uf(nome: str, evento_url: str) -> str | None: ...
def ler_periodo_inscricao(texto: str | None) -> tuple[date | None, date | None]: ...
```

- `ler_catalogo` recebe o JSON **inteiro** (lista de grupos) e nunca confia no caminho da URL:
  a fase sai de `faseEvento`/`eventoStatus` do corpo. Grupo desconhecido → `ValueError` com o
  valor recebido (falhar alto, como o extrator de lei depois do Ruling 34).
- `ler_periodo_inscricao` casa o formato literal medido (`"De DD/MM/AAAA até DD/MM/AAAA às
  HH:MM, horário oficial de Brasília/DF"`). Qualquer outro formato → `(None, None)` **e** uma
  lacuna, nunca uma data adivinhada.
- `salario_max_brl` sai de `eventoSalarioMaximo` (número), não da string formatada; `0` e `None`
  viram `None` + lacuna ("salário não informado") — hoje 4 dos 9 concursos abertos estão assim.

**Testes red-first, contra a fixture real:** os 4 grupos e as contagens medidas (1/8/63/424);
`AGEPAR PR 26` → `uf="PR"`; `AGU 26 ESTAGIARIO` → `uf=None`; `CAMARA_MUNICIPAL_PONTAPORA_MS_26`
→ `uf="MS"`; o período de inscrição do `AGEPAR_PR_26` vira `date(2026,7,23)`/`date(2026,8,21)`;
salário `R$ ` vazio → `None` + lacuna; grupo com `faseEvento` inventado → `ValueError`.

## 3. Passo 2 — casamento com o perfil (`dominio/radar.py`, puro)

```python
class PreferenciaRadar(BaseModel):
    ufs: list[str]
    salario_minimo_brl: Decimal | None
    area: Literal["direito", "qualquer"]

class Casamento(BaseModel):
    combina: bool
    motivos: list[str]       # "PR", "salário acima do seu mínimo", "cargo de Direito"
    contra: list[str]        # "salário abaixo do seu mínimo"

def casar_com_perfil(c: ConcursoDoRadar, pref: PreferenciaRadar, cargos: list[str]) -> Casamento: ...
```

- `cargos` vem do detalhe (`eventoCargos[].area`); a área "direito" reusa
  `motor.coletar.cargo_de_direito` — **não** reimplemente o léxico.
- Sem preferência preenchida, `combina=False` e `motivos=[]` (não "combina com tudo").
- `contra` existe para a tela poder dizer **por que não** combina, que é metade da honestidade.

## 4. Passo 3 — tabela e coleta

- Migração `0015_concurso_radar`: tabela `concurso_radar` (catálogo **global**, não por tenant —
  é informação pública): `fonte_id`, `evento_url` (único por fonte), `nome`, `ano`, `fase`, `uf`,
  `vagas`, `salario_max_brl`, `periodo_inscricao_texto`, `inscricao_inicio`, `inscricao_fim`,
  `lacunas` (JSON), `url_evento`, `primeiro_visto_em`, `ultimo_visto_em`, `bruto` (JSON do item).
- `dados/repositorio_radar.py`: `sincronizar(db, concursos, agora)` — insere o que é novo,
  atualiza o que mudou, carimba `ultimo_visto_em` em tudo que veio; **nunca apaga** (um concurso
  que sai da lista continua no catálogo com o último estado conhecido).
- `motor/radar.py`: comando `varrer` (molde de `motor/plano.py` e `motor/calibrar.py`), um GET,
  relatório com novos/atualizados/inalterados. Sem LLM. Frequência de 6 h é configuração do
  agendador (ADR-0030, deploy é do dono) — o comando é idempotente e pode rodar à mão.

**Testes:** sincronizar duas vezes a mesma fixture não duplica nem altera `primeiro_visto_em`;
concurso que muda de fase é atualizado e mantém a identidade; concurso que some da fonte continua
na tabela com o `ultimo_visto_em` antigo.

## 5. Passo 4 — telas do radar (F1.1, F1.2)

- `GET /radar`: catálogo com filtro por fase e por UF, selo "combina com você" + motivos, e a
  **lacuna dita** ("data da prova só sai no edital"). Ordenação: combina primeiro, depois
  inscrição fechando mais cedo.
- `GET /radar/{evento_url}`: detalhe com cargos, arquivos de edital (link para a fonte) e o botão
  **"Acompanhar"**; quando houver PDF de edital, o botão "Analisar este edital" reaproveita o
  pipeline da V2 (`/editais/subir` já sabe ler PDF — aqui ele vem por URL, não por upload).
- A FGV aparece no rodapé do radar como **fonte vetada** com o motivo e o link da P-13
  (Ruling 38).
- Selo "novo para você" quando `primeiro_visto_em` é das últimas 24 h **e** `combina` (Ruling 41).

## 6. Passo 5 — meus concursos (F1.3)

- `POST /radar/{evento_url}/acompanhar` e `POST /perfil/principal`: gravam em `perfil_estudo`
  (append-only por `versao`, como a fatia 7 já faz) — `concurso_principal_id` e
  `concursos_acompanhados`.
- **Só um principal.** O plano do dia continua vindo **só do principal** (CA da spec, F1.3).
  O split N/M do tempo **não** entra aqui: o que entra é o **aviso de impacto** no painel
  ("você acompanha 2 concursos; o plano segue o principal — o outro tem 41 tópicos sem cobertura
  no seu histórico"). Isso fica registrado como escolha, não como esquecimento.

## 7. Passo 6 — Google OAuth (RF-20, Ruling 42)

- `config.py`: `google_oauth_client_id`/`google_oauth_client_secret` (`str | None`, default
  `None`), `.env.example` documentado.
- `api/conta.py`: `GET /entrar/google` (monta a URL de consentimento com `state` assinado pelo
  mesmo HMAC da sessão — ADR-0026) e `GET /entrar/google/callback` (troca o código, lê o e-mail,
  **exige `email_verified`**, cria ou liga a conta e abre sessão).
- Conta existente com o mesmo e-mail: **liga** (mesma pessoa), não duplica; conta criada por
  Google não tem senha e `POST /entrar` responde o erro certo, sem vazar qual caminho existe
  (mesma cautela da P-22).
- Sem as duas variáveis: rota devolve 404 e o botão não é renderizado.
- Fonte: documentação oficial do Google Identity (OAuth 2.0 para aplicações web) — citar a URL
  no docstring; nenhum endpoint inventado.

**Testes:** provedor falso (mesmo molde de `_ClienteHttp`); `state` adulterado é rejeitado;
`email_verified=false` é rejeitado; e-mail já existente liga em vez de duplicar; sem
configuração, 404 e nenhum botão.

## 8. Execução real (honesta)

Rodar `varrer` de verdade contra a API e registrar no diário o que entrou: quantos concursos por
fase, quantos com UF confirmada, quantos sem salário, e quantos "combinam" com o perfil real da
Linda (Direito, PR). Se nenhum combinar, é isso que o diário diz.

## 9. Fora de escopo (vai para `docs/PENDENCIAS.md`)

- FGV (P-13, Ruling 38) · e-mail/push do alerta (Ruling 41) · split N/M do plano entre concursos
  (Ruling 41/§6) · data da prova (só existe no PDF) · agendador de 6 h (ADR-0030, deploy).

# Fatia 10 — Painel: curva, padrões, previsão v0, fio (c), semana da prova: plano

> O que é: o plano da fatia 10 do PRD (`docs/02-produto.md` §6, linha "Painel: curva, padrões,
> previsão v0, fio (c), semana da prova" — RF-16, RF-17, RF-18, RF-19, RF-10, F4.4c). Quando ler:
> antes de executar qualquer passo desta fatia e ao revisar o que foi feito; o diário fica em
> `10-execucao.md`.

**Ponto de partida:** 830 testes verdes, `scripts/checar.sh` OK na `main` (`aecf2ca`). Existem e
são a matéria-prima desta fatia: `evento_estudo` (append-only, com `acertou`,
`confianca_declarada`, `tempo_ms`, `energia`, `bloco_id`, `ocorrido_em` em UTC),
`perfil_estudo` (`data_alvo`, `concurso_principal_id`, `horas_por_dia_semana`),
`plano_dia`/`bloco` (fatia 8, com `modo` já no schema e **sem comportamento** — P-55),
`questao` (`banca`, `orgao`, `ano`, `publicavel`, `despublicada_em`), `topico_edital`
(vocabulário por edital), `aula`/`dossie_topico` (conteúdo publicado),
`dominio/trilha.py` (`LIMIAR_DOMINADO`, `MINIMO_PARA_DOMINADO` — a definição única de
"dominado" do produto, unificada em `aecf2ca`).

**Realidade dos dados (não inventar volume):** o `dev.db` da Linda tem **18 respostas reais** de
uma única aluna, sem `data_alvo` preenchida. Nenhum cruzamento de RF-17 vai atingir o piso de
suporte estatístico, e a previsão vai sair com confiança **baixa**. Isso é o resultado honesto e
é o que a execução real deve registrar — como nas fatias 7 e 11, **nenhum evento é fabricado no
`dev.db`**; séries sintéticas, quando necessárias, vivem em teste e são declaradas como tais.

---

## 1. A regra que manda nesta fatia

A visão §4 e a regra 11 do `CLAUDE.md`: **previsão sempre com intervalo**, nada sem fonte, e
lacuna declarada em vez de número inventado. Três consequências que valem para todos os passos:

1. **Intervalo é intervalo estatístico**, não proxy de cobertura. Esta fatia introduz o
   **intervalo de Wilson** (`dominio/estatistica.py`) e todo número de proficiência exibido
   nasce dele.
2. **Sem `data_alvo`, não há curva necessária.** A tela diz "você ainda não informou a data da
   prova" com link para `/rotina` — nunca desenha uma linha inventada.
3. **Sem corte histórico do concurso, não há probabilidade de aprovação.** A previsão v0 entrega
   **nota prevista com intervalo**; a probabilidade fica declarada como lacuna, com o motivo
   ("não temos o corte histórico deste concurso" — P-17/P-39).

### Ruling 35 — Wilson na previsão, rótulo honesto no diagnóstico
A margem do diagnóstico (`50/(1+peso)`, fatia 7) mede **quanto já perguntamos**, não a precisão
da estimativa; exibida como `66,7 % ± 7,14` ela é lida como intervalo e não é um. Decisão:
(a) o painel usa **Wilson** em tudo que exibe proficiência; (b) o diagnóstico mantém o proxy
(trocá-lo mudaria o critério de parada, que é outra fatia) mas a tela passa a chamá-lo pelo nome
— "cobertura", não "±". Custo se estiver errado: uma troca de rótulo, reversível em um commit.

### Ruling 36 — o painel não chama LLM
Curva, padrões, previsão, alerta e resumo semanal são **determinísticos**. Mesma escolha da
fatia 8 e pelo mesmo motivo: a cota do free tier não pode derrubar a tela que a aluna mais olha.
O resumo semanal (F4.4c) foi avaliado no PRD §5 com custo de ≈ R$ 0,80/mês em LLM; ele sai
daqui **sem** LLM, montado do histórico e do conteúdo já publicado. Custo se estiver errado: um
resumo menos "escrito"; o conteúdo é o mesmo.

### Ruling 37 — fuso fixo de São Paulo até a P-44
RF-17 cruza erro por **horário**, e `evento_estudo.ocorrido_em` é UTC (a coluna `hora_local` do
modelo de dados nunca nasceu — P-44). Decisão: converter para `America/Sao_Paulo` com
`zoneinfo` (stdlib, sem dependência nova) e **dizer na tela** que o horário é o de Brasília.
Custo se estiver errado: um usuário em outro fuso vê a faixa deslocada; some quando a P-44
fechar.

---

## 2. Passo 1 — `dominio/estatistica.py` (fundação, puro)

Novo módulo, sem dependência de banco.

```python
class Proporcao(BaseModel):
    acertos: int
    total: int
    pct: float          # ponto estimado (acertos/total), 0..100
    inferior_pct: float # limite inferior de Wilson, 0..100
    superior_pct: float # limite superior de Wilson, 0..100

def intervalo_wilson(acertos: int, total: int, z: float = 1.96) -> Proporcao: ...
def sobrepoe(a: Proporcao, b: Proporcao) -> bool: ...
```

- Fórmula de Wilson (score interval), `z = 1,96` para 95 %. Fonte: Wilson, E. B. (1927),
  *Probable Inference, the Law of Succession, and Statistical Inference*, JASA 22(158), 209–212 —
  o intervalo recomendado para proporção com n pequeno (Brown, Cai & DasGupta, 2001, *Interval
  Estimation for a Binomial Proportion*, Statistical Science 16(2)). Citar as duas no docstring.
- `total == 0` → `ValueError`. Nunca devolver 0..100 "por padrão".
- `acertos > total` ou negativos → `ValueError`.

**Testes red-first (valores conferidos à mão):**
- `intervalo_wilson(2, 3)` → pct 66,67, inferior ≈ 20,77, superior ≈ 93,85 (este é o caso que
  motivou o Ruling 35: o proxy da fatia 7 dizia ±7,14).
- `intervalo_wilson(0, 10)` → pct 0,0, inferior 0,0, superior ≈ 27,75 (nunca um intervalo
  degenerado 0..0 — é o defeito clássico do intervalo de Wald).
- `intervalo_wilson(10, 10)` → inferior ≈ 72,25, superior ≈ 100,0 (o valor exato é
  99,9986; os limites são **grampeados em [0, 100]** para a tela nunca mostrar 100,0001 —
  o grampo é só de apresentação e está documentado).
- `intervalo_wilson(50, 100)` mais estreito que `intervalo_wilson(5, 10)` com o mesmo ponto.
- `total=0` levanta `ValueError`.
- `sobrepoe` verdadeiro/falso nos dois sentidos, e simétrico.

## 3. Passo 2 — `dominio/curva.py` (RF-16) e o alerta (RF-10, fecha a P-54)

```python
class PontoCurva(BaseModel):
    dia: date
    dominados: int          # tópicos dominados acumulados até este dia
    total_topicos: int

class Curva(BaseModel):
    real: list[PontoCurva]
    necessaria: list[PontoCurva]     # vazio quando não há data_alvo
    data_alvo: date | None
    lacuna: str | None               # "sem data da prova" quando não há data_alvo
    atraso_topicos: int              # >0 = abaixo da curva; 0 quando não há necessária

class Alerta(BaseModel):
    titulo: str
    porque: str
    ajuste: str      # sempre concreto: "estude 2 tópicos a mais por semana" / "+20 min/dia"

def montar_curva(
    respostas: list[RespostaHistorica],
    total_topicos: int,
    hoje: date,
    data_alvo: date | None,
) -> Curva: ...

def alerta_da_curva(curva: Curva, horas_por_semana: float) -> Alerta | None: ...
```

- `RespostaHistorica` (também neste módulo): `topico_id`, `acertou`, `ocorrido_em` (UTC).
- **Dominado** usa a definição única do produto: `total >= MINIMO_PARA_DOMINADO` e
  `taxa >= LIMIAR_DOMINADO`, importados de `dominio/trilha.py` — não redefinir aqui.
- A curva real é **acumulada por semana** (segunda a domingo), e o ponto de um dia é o estado
  daquele dia (um tópico que deixa de ser dominado por erro novo **pode** descer — a curva é o
  estado, não um troféu).
- A curva necessária é a reta de (hoje, dominados_hoje) até (data_alvo, total_topicos). Sem
  `data_alvo` → `necessaria=[]`, `lacuna="sem data da prova"`, `atraso_topicos=0`.
- `alerta_da_curva` devolve `None` quando `atraso_topicos == 0`. Quando > 0, o `ajuste` é
  calculado: tópicos faltantes ÷ semanas restantes, comparado ao ritmo real das últimas 4
  semanas. RF-10 pede "no máximo 1 alerta/dia": nesta fatia o alerta é um aviso **recomputado na
  tela**, não uma notificação — a CA se cumpre por construção e isso fica escrito no docstring.

**Testes red-first:** sem `data_alvo` (lacuna, sem necessária); com `data_alvo` e em dia (sem
alerta); atrasada (alerta com ajuste numérico); tópico que perde o domínio ao errar (a curva
desce); `data_alvo` no passado → `necessaria=[]` e lacuna `"data da prova já passou"`.

## 4. Passo 3 — `dominio/padroes.py` (RF-17)

```python
Dimensao = Literal["topico", "banca", "horario", "energia"]

class PadraoErro(BaseModel):
    dimensao: Dimensao
    valor: str              # "Direito Administrativo" | "CESPE/Cebraspe" | "madrugada" | "energia 2"
    proporcao: Proporcao    # do subgrupo
    base: Proporcao         # a linha de base (todas as respostas)
    frase: str              # "você erra mais de madrugada: 40 % (n=12) contra 72 % no geral"

#: Piso de suporte estatístico (RF-17 "definir n"): abaixo disso o cruzamento nem é avaliado.
MINIMO_RESPOSTAS_PADRAO: Final = 8

def detectar_padroes(respostas: list[RespostaClassificada]) -> list[PadraoErro]: ...
```

- `RespostaClassificada`: `acertou`, `materia`, `banca`, `hora_local` (int 0–23), `energia`
  (`int | None`).
- **O critério de "padrão" não é um limiar arbitrário de diferença:** um cruzamento só vira
  padrão quando (a) `n >= MINIMO_RESPOSTAS_PADRAO` **e** (b) o intervalo de Wilson do subgrupo
  **não se sobrepõe** ao da linha de base (`sobrepoe(...) is False`). Sem sobreposição, a
  diferença é defensável; com sobreposição, é ruído e não aparece. Isso cumpre literalmente o
  CA "só mostra padrão com suporte estatístico mínimo".
- Faixas de horário (fixas, ditas na tela): `madrugada` 0–5, `manhã` 6–11, `tarde` 12–17,
  `noite` 18–23.
- Energia entra como `energia 1`…`energia 5`; respostas sem energia não entram nessa dimensão
  (não viram "energia desconhecida" com cara de padrão).
- Ordem de saída: maior diferença de ponto estimado primeiro; empate pelo maior `n`.

**Testes red-first:** subgrupo com n=7 nunca vira padrão; n=20 com 30 % contra 80 % na base vira;
n=20 com 70 % contra 75 % (intervalos sobrepostos) não vira; as quatro dimensões; resposta sem
energia não polui a dimensão energia; lista vazia devolve `[]`.

## 5. Passo 4 — `dominio/previsao.py` (RF-18)

```python
class DesempenhoMateria(BaseModel):
    materia: str
    proporcao: Proporcao
    peso_questoes: int      # quantas questões da prova são desta matéria (do DNA)

class Previsao(BaseModel):
    nota_pct: float
    nota_inferior_pct: float
    nota_superior_pct: float
    confianca: Literal["baixa", "media", "alta"]
    materias_sem_dado: list[str]
    corte_historico_pct: float | None
    probabilidade_lacuna: str | None   # motivo, quando não dá para calcular probabilidade
    porque: str

def prever_nota(
    materias: list[DesempenhoMateria],
    corte_historico_pct: float | None = None,
) -> Previsao: ...
```

- Nota = média das proficiências **ponderada por `peso_questoes`**; os limites saem da mesma
  ponderação aplicada aos limites de Wilson de cada matéria (conservador e explicável: a banda
  da nota é a combinação linear das bandas, não uma simulação).
- Matéria **sem nenhuma resposta** não entra na média e vai para `materias_sem_dado` — nunca
  entra como zero, nunca entra como "média das outras".
- `confianca`: `alta` se a banda ≤ 10 p.p. **e** ≥ 80 % do peso da prova tem dado medido;
  `media` se banda ≤ 20 p.p. e ≥ 50 % do peso; senão `baixa`. Os três números ficam no docstring
  com o motivo.
- `corte_historico_pct is None` → `probabilidade_lacuna` explica por quê e **não** existe número
  de probabilidade. Com corte, a saída ainda é comparativa e honesta ("a banda da sua nota está
  acima/abaixo/em cima do corte"), nunca uma porcentagem de aprovação fabricada.
- `porque` cita os números que mandaram: matérias de maior peso, as sem dado, a largura da banda.

**Testes red-first:** matéria sem dado não vira zero; peso maior puxa a nota; banda estreita com
muito dado → `alta`; pouca cobertura → `baixa`; sem corte histórico → lacuna declarada e nenhum
campo de probabilidade; com corte, a comparação sai pela banda (não pelo ponto).

## 6. Passo 5 — `dominio/resumo_semanal.py` (F4.4c, fio (c))

Resumo cumulativo de sábado, **≤ 1 tela**, determinístico (Ruling 36).

```python
class ItemResumo(BaseModel):
    topico_nome: str
    frase: str      # "Improbidade: acertou 2 de 4 — reveja o art. 11"

class ResumoSemanal(BaseModel):
    inicio: date
    fim: date
    respostas: int
    acertos: Proporcao
    topicos_novos: list[str]
    para_rever: list[ItemResumo]     # no máximo 5
    conquista: str | None            # só quando há número real ("3 tópicos dominados nesta semana")

def montar_resumo(
    respostas: list[RespostaHistorica],
    nomes_por_topico: dict[UUID, str],
    inicio: date,
    fim: date,
) -> ResumoSemanal: ...
```

- Semana sem nenhuma resposta → `respostas=0`, listas vazias, `conquista=None`. A tela diz
  "semana sem estudo registrado" — não inventa incentivo.
- `para_rever` ordena por erro mais recente (mesmo critério do fio (b), `dominio/fio_memoria.py`),
  limitado a 5 para caber na tela.

**Testes red-first:** semana vazia; recorte por data (resposta de domingo anterior fora);
`para_rever` no máximo 5 e na ordem certa; `conquista` só com número real.

## 7. Passo 6 — semana da prova (RF-19, fecha a P-55)

`dominio/plano.py` ganha a regra, **sem tabela nova** (`plano_dia.modo` já existe):

- `modo_do_dia(hoje, data_alvo, energia, sono_horas, pedido_descanso)` → `"semana_prova"` quando
  `0 <= (data_alvo - hoje).days <= 7`, com precedência: `descanso` > `semana_prova` > `restrito` >
  `normal` (descansar continua valendo mesmo na semana da prova — é regra de saúde, visão §4).
- Em `semana_prova`: só entram blocos de **revisão** (cartões vencidos e tópicos já vistos e
  fracos). Tópico nunca visto **não entra**, aula nova **não é gerada** (o comando de aula já
  respeita o teto; aqui o plano simplesmente não pede). O `porque` de cada bloco diz
  "faltam N dias para a prova — revisão cirúrgica, sem assunto novo".

**Testes red-first:** 8 dias → não é semana da prova; 7 e 0 dias → é; data no passado → não;
`descanso` vence `semana_prova`; nenhum bloco de tópico não visto; o `porque` cita os dias.

## 8. Passo 7 — camada de dados, rota e tela

- `dados/repositorio_painel.py`: `respostas_historicas(db, usuario_id, edital_id)` →
  `list[RespostaHistorica]` e `respostas_classificadas(...)` → `list[RespostaClassificada]`
  (junta `evento_estudo` × `questao` × `topico_edital`, sempre com
  `publicavel is True AND despublicada_em IS NULL`, mesma trava da P-34), e
  `pesos_por_materia(db, edital_id)` (do DNA quando houver; **lacuna declarada** quando o edital
  não trouxer peso — P-39 — usando peso uniforme por matéria e dizendo isso na tela).
- `api/painel.py`: `GET /painel` (curva + alerta + padrões + previsão) e
  `GET /painel/semana` (resumo semanal). Sem login → `exigir_usuario` redireciona. Sem concurso
  principal → tela com o caminho para `/rotina`.
- `web/templates/painel/pagina.html` + `_curva.html` + `_padroes.html` + `_previsao.html` +
  `semana.html`, no shell já existente (`base.html`, paleta do protótipo validado,
  `docs/evidencias/mockups/2026-09-14-prototipo-clicavel.html`). **O gráfico da curva é um `<svg>`
  montado no servidor** (duas polilinhas + eixos) — sem JS, sem biblioteca, sem dependência nova
  (ADR-0019 permite ilha de JS; aqui nem isso é preciso). A banda do intervalo é um `<rect>`
  translúcido, e o número sempre aparece por escrito ao lado ("62 % — entre 48 % e 74 %"), para o
  gráfico nunca ser a única fonte da informação.
- Link "Painel" na navegação de `base.html`.
- O alerta (RF-10) aparece **também** em `GET /hoje`, acima do plano, quando existir.

**Testes red-first:** rota exige login; usuário sem perfil vê o caminho para `/rotina`; a página
mostra a lacuna de `data_alvo` em vez de curva; com dado, mostra a banda escrita por extenso;
questão despublicada não entra em nenhum número (regressão da P-34); o alerta aparece em `/hoje`.

## 9. Execução real (honesta, sem fabricar dado)

Rodar contra uma **cópia** de `dev.db` (fatias 7 e 11): abrir o painel da Linda e registrar no
diário o que sai de verdade — 18 respostas, previsão de confiança **baixa**, nenhum padrão acima
do piso, curva sem necessária (ela não informou `data_alvo`). Se algum número sair bonito demais,
desconfiar antes de comemorar: é o defeito que mais custou nesta semana.

## 10. Fora de escopo (registrar em `docs/PENDENCIAS.md` se achado)

- Notificação/push do alerta (RF-10 "1 alerta/dia" com entrega real) — depende de deploy e PWA.
- Probabilidade de aprovação com corte histórico real — depende da P-17/P-39.
- Fuso por usuário (P-44) — o painel usa São Paulo e diz isso.
- TRI/discriminação na previsão (ADR-0022: só com n ≥ 300).
- Resumo semanal escrito por LLM (Ruling 36).

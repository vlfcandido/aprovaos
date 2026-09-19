# Fatia 5 — Questões inéditas validadas: plano

> O que é: o plano da fatia 5 do PRD (`docs/02-produto.md` §6, "Geração validada de questões
> inéditas (marcadas) — só onde a base Cebraspe não cobre o tópico" — RF-11, RF-27, RF-28).
> Quando ler: antes de executar qualquer passo desta fatia e ao revisar o que foi feito; o
> diário fica em `5-execucao.md`.

**Contrato obrigatório:** `.claude/skills/gerador-questao-banca/SKILL.md`, lida **inteira** antes
de codificar. Esta fatia não inventa regra: ela implementa aquele contrato (Passo 0 com plano de
mecanismos e de gabaritos, `QuestaoGerada` campo a campo, as regras por banca, e o validador de
cinco itens).

**Ponto de partida:** o esquema **já suporta** inédita — `questao.inedita`, `validada_em`,
`validador_versao`, `justificativa_certo`/`justificativa_errado`, `origem` nullable. Existem e
são reaproveitados: `dossie_topico` (fatia 4, fontes com trecho literal), `dna_concurso`
(estilo/regra de correção), `dominio/questao.py::decidir_publicacao` (o gate da V3),
`dominio/justificativa.py` (validador mecânico de citação, fundação jurídica),
`motor/aula.py` (o molde de comando: teto → agente → validador → publica ou não).

---

## 1. A regra que manda nesta fatia

Visão §4 e regra 11: **nada gerado chega ao aluno sem validação**. Três consequências:

1. Inédita nasce `publicavel=False`. Só o validador liga — e o validador é **outra** família de
   prompt, nunca o mesmo agente se auto-aprovando.
2. Toda afirmação do item tem de estar **literalmente** no dossiê (`trecho_que_decide` copiado).
   O gerador não completa a lei com o que "sabe" — é o erro que a própria skill documenta.
3. Inédita é **marcada como tal** na tela, sempre, sem letra miúda.

### Ruling 43 — aderência medida sem embedding nesta fatia
O item 3 do validador da skill pede similaridade por **embedding** com os 5 originais. Embedding
exige chamada de API (mais cota) ou a extensão `vector` (que nunca foi ligada). Decisão: nesta
fatia a aderência é medida por **duas coisas determinísticas**: (a) regras de **forma** da tabela
por banca (comprimento, uma afirmação só, presença de comando, ausência de "sempre/nunca"
gratuitos, 5 alternativas homogêneas em A–E) e (b) **similaridade léxica** com os 5 originais
(cosseno de TF‑IDF, stdlib `math`/`collections`, sem dependência nova), declarada no campo como
o proxy que é. Embedding vira pendência com o motivo. Custo se estiver errado: um item de estilo
esquisito passa; o calibrador (fatia 11) o pega pelos números depois.

### Ruling 44 — duas chamadas por item, em lote pequeno
Gerar e re-resolver sem ver o gabarito são **duas** chamadas de LLM. No free tier (20/dia por
modelo) isso dá cerca de **10 itens por dia**. Decisão: não contornar — o comando gera em lote
pequeno, é idempotente, e a fatia entrega o cano funcionando com o volume que a cota permitir.
O diário registra o número real, não o desejado. Custo: a cobertura das lacunas leva semanas no
free tier; é o preço de não publicar sem validar.

### Ruling 45 — o preenchedor encomenda, não decide sozinho o que existe
RF-27 pede "cobertura da base vs DNA → encomenda geração em lote". Decisão: o preenchedor
encomenda **só** para tópico com **dossiê** (sem dossiê não há de onde tirar trecho literal) e
com **zero** questões publicáveis. Tópico sem dossiê aparece no relatório como "falta dossiê" —
lacuna declarada, não geração às cegas.

---

## 2. Passo 1 — `dominio/questao_inedita.py` (puro)

O contrato da skill em Pydantic, mais o Passo 0:

```python
Mecanismo = Literal["literal","troca_de_verbo","troca_de_competencia",
                    "troca_de_quorum","troca_de_prazo","excecao_omitida"]

class PlanoDoLote(BaseModel):
    n_pedido: int
    originais_recebidos: int
    aderencia_medida: bool          # originais_recebidos >= 5
    mecanismos: dict[Mecanismo, int]
    gabaritos: dict[str, int]

class QuestaoGerada(BaseModel):     # todos os campos da skill, nenhum opcional por conveniência
    ...

def montar_plano_do_lote(n_pedido: int, originais_recebidos: int, tipo_item: str) -> PlanoDoLote: ...
def conferir_lote(itens: list[QuestaoGerada], plano: PlanoDoLote) -> list[str]: ...
```

- `montar_plano_do_lote`: `literal = n // 5`; o resto distribuído entre os outros mecanismos de
  forma **determinística** (ordem fixa, sem `random`); gabaritos ~50/50 em C/E e distribuídos em
  A–E. `n_pedido <= 0` → `ValueError`.
- `conferir_lote` devolve a lista de divergências em pt-BR (vazia = lote conforme). A skill é
  explícita: lote fora do plano é reescrito, não "ajustado levemente".

**Testes red-first:** `n=5` → `literal=1`; `n=3` → `literal=0`; contagem final ≠ plano é apontada
item a item; `aderencia_medida` falsa com 4 originais; lote conforme devolve `[]`.

## 3. Passo 2 — `dominio/validacao_questao.py` (puro, os 5 itens do validador)

```python
class Veredito(BaseModel):
    aprovado: bool
    motivos: list[str]              # vazio só quando aprovado
    validador_versao: str
    aderencia_pct: float | None     # None quando aderencia_medida é falsa

def verificar_forma(item: QuestaoGerada, banca: str) -> list[str]: ...
def verificar_fontes(item: QuestaoGerada, dossie: DossieTopico) -> list[str]: ...
def similaridade_lexica(texto: str, originais: list[str]) -> float: ...
def julgar(item, dossie, originais, resolucao_independente: str | None) -> Veredito: ...
```

- `verificar_fontes` reusa a mesma disciplina de `dominio/justificativa.py`: cada `F-n` existe no
  dossiê **e** `trecho_que_decide` aparece **literalmente** na fonte (mesma normalização de
  ordinal já resolvida lá — `art. 1º` × `art. 1`). Não reimplemente a normalização: importe.
- `resolucao_independente` é o gabarito a que o segundo agente chegou **sem ver** o do gerador;
  divergência → reprova com motivo `gabarito`.
- `julgar` só aprova com **todos** os cinco itens da skill atendidos. Um motivo basta para
  reprovar, e o motivo vai para o banco.

**Testes red-first:** a "consequência acrescentada" da skill (oração fora do trecho) reprova;
trecho que não está na fonte reprova; gabarito divergente reprova; item C/E com duas afirmações
reprova; A–E com alternativas de tamanhos díspares reprova; item conforme aprova; `aderencia_pct`
é `None` quando há menos de 5 originais.

## 4. Passo 3 — agentes ADK

- `agentes/gerador_de_questao.py` e `agentes/validador_de_questao.py`, no molde exato de
  `agentes/gerador_de_aula.py` (ADK `LlmAgent`, JSON mode, `registrar_traco` por chamada,
  `TetoDiario` antes de qualquer chamada). Cuidado já pago na fatia 6: `{{palavra}}` no prompt é
  variável de sessão do ADK e quebra com `KeyError` — escape.
- O prompt do gerador é o contrato da skill; o do validador **não recebe o gabarito** do gerador.
- `MODELO_QUESTAO` e `MODELO_VALIDACAO` em `config.py` + `.env.example` (Flash, mesmo corte de
  `MODELO_AULA`: gerar e julgar item é raciocínio, não classificação).

## 5. Passo 4 — `motor/preencher.py` e `motor/gerar_questao.py`

- `preencher`: relatório de cobertura por tópico do edital — publicáveis, tem dossiê, tem aula —
  e a encomenda (`tópico, n`) só para os que casam o Ruling 45.
- `gerar_questao`: para cada encomenda, monta entrada (dossiê + DNA + até 5 originais do mesmo
  tópico/banca), chama o gerador, confere o lote, chama o validador item a item, grava.
  Reprovado **fica no banco** com `publicavel=False` e o motivo (RF-28: "rejeição registrada com
  motivo"), nunca é descartado em silêncio.
- Migração `0016_veredito_questao`: tabela append-only `veredito_questao`
  (`questao_id`, `aprovado`, `motivos` JSON, `validador_versao`, `criado_em`) — o histórico de
  tentativas, que `questao.validada_em` sozinha não guarda.
- Sem chave/sem teto: o comando **não** gera nada e diz por quê (mesmo padrão dos outros).

## 6. Passo 5 — a inédita na tela

- `_cartao_questao.html`/`_resultado.html` ganham o selo **"Questão inédita do AprovaOS —
  validada contra [fonte]"**, ao lado do selo de origem que as originais já têm. O aluno tem de
  poder distinguir sem esforço.
- As duas justificativas (certo/errado) já têm lugar na tela desde a fundação jurídica — a
  inédita reusa, sem template novo.
- Reportar erro continua valendo e a inédita entra na mesma fila do calibrador.

## 7. Execução real (honesta, sem fabricar)

Rodar contra o `dev.db`: relatório de cobertura de verdade (quantos dos 99 tópicos do TJ-PR têm
zero publicáveis e têm dossiê) e gerar **o que a cota do dia permitir**. Registrar no diário: n
pedido, n gerado, n aprovado, n reprovado **com os motivos**, e o custo estimado. Se a cota
estourar no meio, isso é o resultado e é o que fica escrito.

## 8. Fora de escopo (vai para `docs/PENDENCIAS.md`)

- Aderência por embedding e a extensão `vector` (Ruling 43).
- Suíte DeepEval em `eval/` (a skill pede; depende de cota e de amostra rotulada) — registrar com
  o que faltou, não fingir que rodou.
- Geração para banca desconhecida com `aderencia_medida: false` em escala (a P-17 continua
  aberta).

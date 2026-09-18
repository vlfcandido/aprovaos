# O que é: origem e propósito dos snapshots da API da Cebraspe usados pelo coletor (V3, passo 2).
> Quando ler: antes de reusar, regenerar ou entender por que `lista-encerrado-v2.json` tem um evento que a Cebraspe nunca publicou.

## `lista-encerrado-v1.json`
Resposta **real**, sem alteração nenhuma, de
`GET https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/fase/encerrado`, baixada em
18/09/2026 por `uv run python scripts/snapshot_cebraspe.py` (dentro de `backend/`), com
`User-Agent: AprovaOS-coletor/0.1 (+contato: vlfcandido@gmail.com)` (ADR-0030). Formato: lista com
um único objeto `{faseEvento, ordem, eventos: [...]}`; `eventos` tem **424 registros**, mas só
**423 `eventoURL` distintos** — `INSS_22` aparece **duas vezes** na listagem (a própria API
devolveu a duplicata; não é erro de geração desta fixture). Contagem verificada:
```
$ python3 -c "import json,collections; v=json.load(open('lista-encerrado-v1.json'))[0]['eventos']; u=[e['eventoURL'] for e in v]; print(len(u), len(set(u))); print([k for k,n in collections.Counter(u).items() if n>1])"
424 423
['INSS_22']
```
Quem escrever o teste de novidade no passo 4 (skill `monitor-de-fontes`, "N = itens reais do
arquivo") usa **423** como o número de itens únicos de `v1` com `vistos=∅`, não 424 — a fonte de
verdade é a contagem de `eventoURL` **distintos**, não o número de registros da lista.
`idEvento` vem `0` em todos — não serve como identidade do item (a ficha em `knowledge/fontes.yaml`
usa `{eventoURL}/{nomeArquivo}` para arquivos, e `eventoURL` sozinho para o evento na listagem, que
não traz arquivos).

## `detalhe-TJ_PA_25_SERVIDOR.json`
Resposta **real**, sem alteração, de `GET https://apis.cebraspe.org.br/cebraspe/eventos/TJ_PA_25_SERVIDOR`,
baixada na mesma execução. É um objeto (não uma lista) com `eventoCargos` (22 cargos) e
`arquivosGabarito` (**54 itens, 54 `nomeArquivo` distintos** — sem duplicata aqui, ao contrário de
`v1`), cada um com `tipoExtensaoArquivo`, `dataArquivo`, `nomeArquivo`, `descricaoArquivo`,
`isDataValid`, `isGuid`, `dataArquivoObj`). Por `descricaoArquivo`: **26** `PROVA OBJETIVA`, **26**
`GABARITO DEFINITIVO`, **1** `PADRÃO DEFINITIVO DE RESPOSTA` (prova discursiva) e **1**
`PROVA DISCURSIVA` — soma 54. Escolhido como evento de referência para os testes de segmentação por
descrição do passo 4 do plano da V3 (`docs/fatias/V3-questoes-cebraspe.md`).

## `lista-encerrado-v2.json` — **sintético, não é resposta da Cebraspe**
Cópia literal de `lista-encerrado-v1.json` **com um evento a mais**, inserido à mão por mim
(Claude, executando o passo 2 da V3) depois do snapshot real, para servir ao teste 3 da skill
`monitor-de-fontes` ("v2 com vistos = ids(v1) → exatamente 1 novidade"). O evento inserido:

```json
{
  "idEvento": 0,
  "eventoNomeAbreviado": "TESTE V3 99",
  "eventoURL": "TESTE_V3_99",
  "eventoStatus": "encerrado",
  "eventoTipo": "concursos",
  "eventoAno": 2026,
  "eventoTotalVagas": "1",
  "eventoSalarioMaximo": 1000
}
```

(demais campos copiados com os mesmos valores `null`/`false`/padrão que os outros eventos da
listagem têm). Nenhum concurso `TESTE_V3_99` existe na Cebraspe — o `eventoURL` foi escolhido
exatamente para não colidir com um `eventoURL` real, inclusive com o duplicado `INSS_22`.
`lista-encerrado-v2.json` tem **425 registros / 424 `eventoURL` distintos**
(423 distintos de `v1` + `TESTE_V3_99`; `INSS_22` continua duplicado, herdado de `v1`);
`lista-encerrado-v1.json` tem **424 registros / 423 distintos**.

## Contagens de referência (para o passo 4 — teste de novidade da skill `monitor-de-fontes`)
| arquivo | registros | `eventoURL`/`nomeArquivo` distintos | observação |
|---|---|---|---|
| `lista-encerrado-v1.json` | 424 | **423** | `INSS_22` duplicado (2×) |
| `lista-encerrado-v2.json` | 425 | **424** | os mesmos 423 de `v1` + `TESTE_V3_99` (único novo) |
| `detalhe-TJ_PA_25_SERVIDOR.json` (`arquivosGabarito`) | 54 | 54 | sem duplicata; 26 `PROVA OBJETIVA` + 26 `GABARITO DEFINITIVO` + 1 `PADRÃO DEFINITIVO DE RESPOSTA` + 1 `PROVA DISCURSIVA` |

O teste "`v1` com `vistos=∅` → N novidades" da skill usa `N = 423` (itens **distintos**, que é o
que `listar_novidades` deve deduplicar por `eventoURL`); "`v2` com `vistos = ids(v1)` → exatamente
1 novidade" continua valendo, com `id == "TESTE_V3_99"`.

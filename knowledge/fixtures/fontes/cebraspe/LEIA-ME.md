# O que é: origem e propósito dos snapshots da API da Cebraspe usados pelo coletor (V3, passo 2).
> Quando ler: antes de reusar, regenerar ou entender por que `lista-encerrado-v2.json` tem um evento que a Cebraspe nunca publicou.

## `lista-encerrado-v1.json`
Resposta **real**, sem alteração nenhuma, de
`GET https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/fase/encerrado`, baixada em
18/09/2026 por `uv run python scripts/snapshot_cebraspe.py` (dentro de `backend/`), com
`User-Agent: AprovaOS-coletor/0.1 (+contato: vlfcandido@gmail.com)` (ADR-0030). Formato: lista com
um único objeto `{faseEvento, ordem, eventos: [...]}`; `eventos` tem **424** itens nesta data.
`idEvento` vem `0` em todos — não serve como identidade do item (a ficha em `knowledge/fontes.yaml`
usa `{eventoURL}/{nomeArquivo}` para arquivos, e `eventoURL` sozinho para o evento na listagem, que
não traz arquivos).

## `detalhe-TJ_PA_25_SERVIDOR.json`
Resposta **real**, sem alteração, de `GET https://apis.cebraspe.org.br/cebraspe/eventos/TJ_PA_25_SERVIDOR`,
baixada na mesma execução. É um objeto (não uma lista) com `eventoCargos` (22 cargos) e
`arquivosGabarito` (**54** itens, cada um com `tipoExtensaoArquivo`, `dataArquivo`, `nomeArquivo`,
`descricaoArquivo`, `isDataValid`, `isGuid`, `dataArquivoObj`). Escolhido como evento de referência
para os testes de segmentação por descrição do passo 4 do plano da V3
(`docs/fatias/V3-questoes-cebraspe.md`).

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

(demais campos copiados com os mesmos valores `null`/`false`/padrão que os outros 424 eventos da
listagem têm). Nenhum concurso `TESTE_V3_99` existe na Cebraspe — o `eventoURL` foi escolhido
exatamente para não colidir com um `eventoURL` real. `lista-encerrado-v2.json` tem 425 eventos;
`lista-encerrado-v1.json` tem 424.

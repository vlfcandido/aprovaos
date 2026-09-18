---
name: ingestao-de-provas
description: Use quando for transformar uma prova (texto extraído de PDF, HTML ou fixture) em questões para a base do Motor — inclusive "curar a prova", "segmentar itens", "classificar questões", "importar gabarito", "subir provas da Cebraspe/FGV", ou ao revisar questões que entraram sem origem, sem texto de apoio ou com item anulado servido a aluno.
---

# Ingestão de provas
> O que é: o contrato do `curador` — como uma prova vira linhas da tabela `questao` sem perder nada que o aluno precisa ver e sem publicar o que não pode ser servido. Quando ler: antes de curar qualquer prova; ao investigar reporte de erro "faltou o texto" ou "gabarito invertido".

## Princípio
A questão servida ao aluno tem de ser **idêntica ao que a banca imprimiu** (comando + texto de apoio + item) e **rastreável até o PDF** (origem completa). O que a banca anulou ou mudou de gabarito **fica na base, mas não é servido**. Classificar é o último passo, e é sempre marcado como estimativa até o validador passar.

## Entradas
- `documento`: texto extraído (pypdfium2/pdfplumber) + `documento_id`, `url_prova`, `banca`, `orgao`, `cargo`, `ano`, `tipo_caderno` (vindos do `coletor`/API).
- `gabarito`: preliminar e/ou definitivo, com lista de anulados/alterados.
- Vocabulário `topico` (matéria/nome/slug) do adapter.

## A saída é uma lista de objetos com estes campos — todos obrigatórios (use `null` quando não houver)
```json
{
  "adapter": "concursos", "banca": "cebraspe", "tipo_item": "certo_errado",
  "numero_item": 58,
  "comando": "Com base na Lei nº 14.133/2021, julgue os itens subsequentes.",
  "texto_apoio": "A Lei nº 14.133/2021 estabelece normas gerais de licitação e contratação [...]",
  "texto_apoio_itens": [58, 59],
  "enunciado": "O diálogo competitivo é modalidade de licitação restrita a contratações que envolvam inovação tecnológica ou técnica.",
  "alternativas": null,
  "gabarito_preliminar": "C", "gabarito": "C", "gabarito_status": "definitivo|anulado|alterado|preliminar",
  "publicavel": true, "publicado": false, "motivo_nao_publicavel": null,
  "regra_prova": {"anula_por_erro": true, "fonte": "instrução do caderno"},
  "topico_slug": "dir-adm-04-licitacoes", "topico_confianca": "alta|media|baixa", "topico_evidencia": "comando cita a Lei 14.133 + termo 'modalidade'",
  "origem": {"banca": "cebraspe", "orgao": "TCE-XX", "cargo": "Auditor de Controle Externo — Direito", "ano": 2024, "numero_item": 58, "tipo_caderno": "A", "url_prova": "https://…", "documento_id": "doc-…"},
  "hash_dedup": "sha1(enunciado normalizado)",
  "justificativa_certo": null, "justificativa_errado": null
}
```
`justificativa_*` nascem `null`: quem preenche é o gerador com o validador — o curador nunca explica o gabarito.

## Segmentação por banca
| banca | item | comando | texto de apoio | alternativas |
|---|---|---|---|---|
| Cebraspe (C/E) | `^\d{1,3}\s` no início da linha, dentro do bloco de questões | frase terminada em "julgue os itens (a seguir/subsequentes/seguintes)." — vale para todos os itens até o próximo comando | bloco iniciado por "Texto para os itens X a Y" / "X e Y" — anexado a cada item do intervalo | `null` |
| Cebraspe (A–E, cargos de nível médio) | "QUESTÃO N" | idem | idem | `A`–`E` |
| FGV | `^\d{1,3}\.?\s` ou "Questão N" | texto entre o número e "(A)" quando houver enunciado longo | "Texto I/II" + "as questões X a Y" | `(A)`…`(E)` |
| banca desconhecida | tentar os dois padrões; se o total de itens ≠ total do gabarito, **parar e marcar o documento `pendente_revisao`** | | | |

## Gabarito: a ordem de verdade
1. Definitivo > preliminar. Se só há preliminar: `gabarito_status: "preliminar"`, `publicavel: false`.
2. Item **anulado**: `gabarito: null`, `gabarito_status: "anulado"`, `publicavel: false`, `motivo_nao_publicavel: "anulado — <motivo da banca>"`. Fica na base para incidência e para o DNA.
3. Item **alterado**: `gabarito` = definitivo, `gabarito_preliminar` = o anterior, `gabarito_status: "alterado"`; publicável.
4. Item sem entrada no gabarito: `publicavel: false`, motivo "sem gabarito".
5. `publicado` é **sempre `false`** na saída do curador; só o validador liga.

## Classificação de tópico
- `topico_slug` vem do vocabulário canônico; nunca inventar nome novo. Se nada casa: `topico_slug: null`, `topico_confianca: "baixa"`, `topico_evidencia: "sem correspondência no vocabulário"`.
- `topico_evidencia` cita o que no texto decidiu (termo, lei citada, comando).
- Um item, um tópico. Item que cobre dois: o do comando.

## Verificação antes de entregar
1. `len(saida) == nº de itens do caderno` e cada `numero_item` do gabarito aparece uma vez.
2. Todo item entre "Texto para os itens X a Y" e o próximo comando tem `texto_apoio` preenchido.
3. Todo item tem `comando` (ou `null` só se o caderno não tiver comandos — raro na Cebraspe).
4. Nenhum `publicado: true`; nenhum anulado com `gabarito` preenchido.
5. `origem` com os 8 campos; `url_prova`/`documento_id` = os do coletor (nunca reconstruídos de cabeça).

## Erros que este contrato existe para evitar
- Item anulado gravado com o gabarito preliminar como se valesse.
- "Texto para os itens 58 e 59" e o comando "julgue os itens" descartados — o aluno vê o item sem contexto e reporta "faltou o texto".
- `fonte_prova: "TCE-XX — Auditor — 12/5/2024 — Caderno A"` em texto livre no lugar do objeto `origem`.
- Tópico em texto livre ("Princípios da Administração Pública — Impessoalidade") em vez de slug do vocabulário.
- `status: "ativo"` como se a questão já pudesse ser servida antes do validador.

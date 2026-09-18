# Com skill — ingestao-de-provas — Haiku

Processamento de fixture de prova Cebraspe (TCE-XX, Auditor de Controle Externo — Direito, 2024, Caderno A) usando skill `ingestao-de-provas`.

**Metadados do coletor:**
- `documento_id`: doc-cebraspe-tcexx-2024-a
- `url_prova`: https://cdn.cebraspe.org.br/concursos/TCE_XX_24/arquivos/caderno_a.pdf

**Vocabulário canônico mapeado:**
- dir-adm-01-principios (item 52)
- dir-adm-02-atos (itens 51, 53)
- dir-adm-04-licitacoes (itens 58, 59)
- dir-adm-06-improbidade (item 60)
- dir-const-04-poder-legislativo (item 54)
- dir-const-06-fiscalizacao (itens 55, 56, 57)

## JSON estruturado

```json
[
  {
    "adapter": "concursos",
    "banca": "cebraspe",
    "tipo_item": "certo_errado",
    "numero_item": 51,
    "comando": "Acerca dos princípios da administração pública e dos atos administrativos, julgue os itens a seguir.",
    "texto_apoio": null,
    "texto_apoio_itens": [],
    "enunciado": "A presunção de legitimidade dos atos administrativos é absoluta, não admitindo prova em contrário.",
    "alternativas": null,
    "gabarito_preliminar": "E",
    "gabarito": "E",
    "gabarito_status": "definitivo",
    "publicavel": true,
    "publicado": false,
    "motivo_nao_publicavel": null,
    "regra_prova": {"anula_por_erro": false, "fonte": null},
    "topico_slug": "dir-adm-02-atos",
    "topico_confianca": "alta",
    "topico_evidencia": "comando cita 'atos administrativos' + termo 'presunção de legitimidade' é conceito chave",
    "origem": {"banca": "cebraspe", "orgao": "TCE-XX", "cargo": "Auditor de Controle Externo — Direito", "ano": 2024, "numero_item": 51, "tipo_caderno": "A", "url_prova": "https://cdn.cebraspe.org.br/concursos/TCE_XX_24/arquivos/caderno_a.pdf", "documento_id": "doc-cebraspe-tcexx-2024-a"},
    "hash_dedup": "191dffe5f3a5dcb1ec0bceea138b8303c90da502",
    "justificativa_certo": null,
    "justificativa_errado": null
  },
  {
    "adapter": "concursos",
    "banca": "cebraspe",
    "tipo_item": "certo_errado",
    "numero_item": 52,
    "comando": "Acerca dos princípios da administração pública e dos atos administrativos, julgue os itens a seguir.",
    "texto_apoio": null,
    "texto_apoio_itens": [],
    "enunciado": "O princípio da impessoalidade veda que a publicidade de atos, programas e obras dos órgãos públicos contenha nomes, símbolos ou imagens que caracterizem promoção pessoal de autoridades.",
    "alternativas": null,
    "gabarito_preliminar": "C",
    "gabarito": "C",
    "gabarito_status": "definitivo",
    "publicavel": true,
    "publicado": false,
    "motivo_nao_publicavel": null,
    "regra_prova": {"anula_por_erro": false, "fonte": null},
    "topico_slug": "dir-adm-01-principios",
    "topico_confianca": "alta",
    "topico_evidencia": "comando cita 'princípios da administração pública' + 'impessoalidade' (CF art. 37)",
    "origem": {"banca": "cebraspe", "orgao": "TCE-XX", "cargo": "Auditor de Controle Externo — Direito", "ano": 2024, "numero_item": 52, "tipo_caderno": "A", "url_prova": "https://cdn.cebraspe.org.br/concursos/TCE_XX_24/arquivos/caderno_a.pdf", "documento_id": "doc-cebraspe-tcexx-2024-a"},
    "hash_dedup": "77c12bf7dc283887f9a9117dda865d0353b481c3",
    "justificativa_certo": null,
    "justificativa_errado": null
  },
  {
    "adapter": "concursos",
    "banca": "cebraspe",
    "tipo_item": "certo_errado",
    "numero_item": 53,
    "comando": "Acerca dos princípios da administração pública e dos atos administrativos, julgue os itens a seguir.",
    "texto_apoio": null,
    "texto_apoio_itens": [],
    "enunciado": "A revogação de ato administrativo por motivo de conveniência e oportunidade produz efeitos retroativos (ex tunc).",
    "alternativas": null,
    "gabarito_preliminar": "E",
    "gabarito": "E",
    "gabarito_status": "definitivo",
    "publicavel": true,
    "publicado": false,
    "motivo_nao_publicavel": null,
    "regra_prova": {"anula_por_erro": false, "fonte": null},
    "topico_slug": "dir-adm-02-atos",
    "topico_confianca": "alta",
    "topico_evidencia": "comando cita 'atos administrativos' + 'revogação' é efeito jurídico",
    "origem": {"banca": "cebraspe", "orgao": "TCE-XX", "cargo": "Auditor de Controle Externo — Direito", "ano": 2024, "numero_item": 53, "tipo_caderno": "A", "url_prova": "https://cdn.cebraspe.org.br/concursos/TCE_XX_24/arquivos/caderno_a.pdf", "documento_id": "doc-cebraspe-tcexx-2024-a"},
    "hash_dedup": "8e47b9a356df9e2df977fa130a20dcb8e1e366f0",
    "justificativa_certo": null,
    "justificativa_errado": null
  },
  {
    "adapter": "concursos",
    "banca": "cebraspe",
    "tipo_item": "certo_errado",
    "numero_item": 54,
    "comando": "Acerca dos princípios da administração pública e dos atos administrativos, julgue os itens a seguir.",
    "texto_apoio": null,
    "texto_apoio_itens": [],
    "enunciado": "Compete privativamente ao chefe do Poder Executivo a iniciativa de leis que disponham sobre a criação de cargos na administração direta.",
    "alternativas": null,
    "gabarito_preliminar": null,
    "gabarito": null,
    "gabarito_status": "anulado",
    "publicavel": false,
    "publicado": false,
    "motivo_nao_publicavel": "anulado — erro material",
    "regra_prova": {"anula_por_erro": false, "fonte": null},
    "topico_slug": "dir-const-04-poder-legislativo",
    "topico_confianca": "alta",
    "topico_evidencia": "termo 'Poder Executivo' + iniciativa legislativa (CF art. 61)",
    "origem": {"banca": "cebraspe", "orgao": "TCE-XX", "cargo": "Auditor de Controle Externo — Direito", "ano": 2024, "numero_item": 54, "tipo_caderno": "A", "url_prova": "https://cdn.cebraspe.org.br/concursos/TCE_XX_24/arquivos/caderno_a.pdf", "documento_id": "doc-cebraspe-tcexx-2024-a"},
    "hash_dedup": "4d007111f2625c002845cff6995ecf1fa93a6958",
    "justificativa_certo": null,
    "justificativa_errado": null
  },
  {
    "adapter": "concursos",
    "banca": "cebraspe",
    "tipo_item": "certo_errado",
    "numero_item": 55,
    "comando": "Com base na Constituição Federal de 1988, julgue os itens subsequentes, relativos à fiscalização contábil, financeira e orçamentária.",
    "texto_apoio": null,
    "texto_apoio_itens": [],
    "enunciado": "O controle externo, a cargo do Poder Legislativo, será exercido com o auxílio do tribunal de contas.",
    "alternativas": null,
    "gabarito_preliminar": "C",
    "gabarito": "C",
    "gabarito_status": "definitivo",
    "publicavel": true,
    "publicado": false,
    "motivo_nao_publicavel": null,
    "regra_prova": {"anula_por_erro": false, "fonte": null},
    "topico_slug": "dir-const-06-fiscalizacao",
    "topico_confianca": "alta",
    "topico_evidencia": "comando cita 'fiscalização' + 'tribunal de contas' (CF art. 71)",
    "origem": {"banca": "cebraspe", "orgao": "TCE-XX", "cargo": "Auditor de Controle Externo — Direito", "ano": 2024, "numero_item": 55, "tipo_caderno": "A", "url_prova": "https://cdn.cebraspe.org.br/concursos/TCE_XX_24/arquivos/caderno_a.pdf", "documento_id": "doc-cebraspe-tcexx-2024-a"},
    "hash_dedup": "a5b274ee65de79122c63ab71bf96e1c05e25cf94",
    "justificativa_certo": null,
    "justificativa_errado": null
  },
  {
    "adapter": "concursos",
    "banca": "cebraspe",
    "tipo_item": "certo_errado",
    "numero_item": 56,
    "comando": "Com base na Constituição Federal de 1988, julgue os itens subsequentes, relativos à fiscalização contábil, financeira e orçamentária.",
    "texto_apoio": null,
    "texto_apoio_itens": [],
    "enunciado": "As decisões do tribunal de contas de que resulte imputação de débito terão eficácia de título executivo.",
    "alternativas": null,
    "gabarito_preliminar": "C",
    "gabarito": "C",
    "gabarito_status": "definitivo",
    "publicavel": true,
    "publicado": false,
    "motivo_nao_publicavel": null,
    "regra_prova": {"anula_por_erro": false, "fonte": null},
    "topico_slug": "dir-const-06-fiscalizacao",
    "topico_confianca": "alta",
    "topico_evidencia": "comando cita 'tribunal de contas' + eficácia título executivo (CF art. 71 §3º)",
    "origem": {"banca": "cebraspe", "orgao": "TCE-XX", "cargo": "Auditor de Controle Externo — Direito", "ano": 2024, "numero_item": 56, "tipo_caderno": "A", "url_prova": "https://cdn.cebraspe.org.br/concursos/TCE_XX_24/arquivos/caderno_a.pdf", "documento_id": "doc-cebraspe-tcexx-2024-a"},
    "hash_dedup": "a2fa34d26cab58083e2d727d1001017718e399da",
    "justificativa_certo": null,
    "justificativa_errado": null
  },
  {
    "adapter": "concursos",
    "banca": "cebraspe",
    "tipo_item": "certo_errado",
    "numero_item": 57,
    "comando": "Com base na Constituição Federal de 1988, julgue os itens subsequentes, relativos à fiscalização contábil, financeira e orçamentária.",
    "texto_apoio": null,
    "texto_apoio_itens": [],
    "enunciado": "Cabe ao tribunal de contas julgar as contas do chefe do Poder Executivo, sem participação do Poder Legislativo.",
    "alternativas": null,
    "gabarito_preliminar": "E",
    "gabarito": "E",
    "gabarito_status": "definitivo",
    "publicavel": true,
    "publicado": false,
    "motivo_nao_publicavel": null,
    "regra_prova": {"anula_por_erro": false, "fonte": null},
    "topico_slug": "dir-const-06-fiscalizacao",
    "topico_confianca": "alta",
    "topico_evidencia": "comando cita 'tribunal de contas' + controle externo (CF arts. 71-74)",
    "origem": {"banca": "cebraspe", "orgao": "TCE-XX", "cargo": "Auditor de Controle Externo — Direito", "ano": 2024, "numero_item": 57, "tipo_caderno": "A", "url_prova": "https://cdn.cebraspe.org.br/concursos/TCE_XX_24/arquivos/caderno_a.pdf", "documento_id": "doc-cebraspe-tcexx-2024-a"},
    "hash_dedup": "0c1fc9420251437c1e2867b9f7cd4fdfb61ab40f",
    "justificativa_certo": null,
    "justificativa_errado": null
  },
  {
    "adapter": "concursos",
    "banca": "cebraspe",
    "tipo_item": "certo_errado",
    "numero_item": 58,
    "comando": "Com base na Lei nº 14.133/2021, julgue os itens subsequentes.",
    "texto_apoio": "A Lei nº 14.133/2021 estabelece normas gerais de licitação e contratação para as administrações públicas diretas, autárquicas e fundacionais.",
    "texto_apoio_itens": [58, 59],
    "enunciado": "O diálogo competitivo é modalidade de licitação restrita a contratações que envolvam inovação tecnológica ou técnica.",
    "alternativas": null,
    "gabarito_preliminar": "C",
    "gabarito": "C",
    "gabarito_status": "definitivo",
    "publicavel": true,
    "publicado": false,
    "motivo_nao_publicavel": null,
    "regra_prova": {"anula_por_erro": false, "fonte": null},
    "topico_slug": "dir-adm-04-licitacoes",
    "topico_confianca": "alta",
    "topico_evidencia": "comando cita 'Lei nº 14.133/2021' + 'diálogo competitivo' (Lei 14.133 art. 32)",
    "origem": {"banca": "cebraspe", "orgao": "TCE-XX", "cargo": "Auditor de Controle Externo — Direito", "ano": 2024, "numero_item": 58, "tipo_caderno": "A", "url_prova": "https://cdn.cebraspe.org.br/concursos/TCE_XX_24/arquivos/caderno_a.pdf", "documento_id": "doc-cebraspe-tcexx-2024-a"},
    "hash_dedup": "58b9ba8de6dc133aa17497e9de4bf63e80ae3887",
    "justificativa_certo": null,
    "justificativa_errado": null
  },
  {
    "adapter": "concursos",
    "banca": "cebraspe",
    "tipo_item": "certo_errado",
    "numero_item": 59,
    "comando": "Com base na Lei nº 14.133/2021, julgue os itens subsequentes.",
    "texto_apoio": "A Lei nº 14.133/2021 estabelece normas gerais de licitação e contratação para as administrações públicas diretas, autárquicas e fundacionais.",
    "texto_apoio_itens": [58, 59],
    "enunciado": "Na modalidade pregão, o critério de julgamento pode ser o de melhor técnica.",
    "alternativas": null,
    "gabarito_preliminar": "E",
    "gabarito": "E",
    "gabarito_status": "definitivo",
    "publicavel": true,
    "publicado": false,
    "motivo_nao_publicavel": null,
    "regra_prova": {"anula_por_erro": false, "fonte": null},
    "topico_slug": "dir-adm-04-licitacoes",
    "topico_confianca": "alta",
    "topico_evidencia": "comando cita 'Lei nº 14.133/2021' + 'pregão' é modalidade (Lei 14.133 art. 32)",
    "origem": {"banca": "cebraspe", "orgao": "TCE-XX", "cargo": "Auditor de Controle Externo — Direito", "ano": 2024, "numero_item": 59, "tipo_caderno": "A", "url_prova": "https://cdn.cebraspe.org.br/concursos/TCE_XX_24/arquivos/caderno_a.pdf", "documento_id": "doc-cebraspe-tcexx-2024-a"},
    "hash_dedup": "f91fbe2cb89a8ee185ce7254f197e6e9808cca11",
    "justificativa_certo": null,
    "justificativa_errado": null
  },
  {
    "adapter": "concursos",
    "banca": "cebraspe",
    "tipo_item": "certo_errado",
    "numero_item": 60,
    "comando": "Com base na Lei nº 14.133/2021, julgue os itens subsequentes.",
    "texto_apoio": null,
    "texto_apoio_itens": [],
    "enunciado": "A prescrição da pretensão punitiva por ato de improbidade administrativa é de oito anos, contados da ocorrência do fato.",
    "alternativas": null,
    "gabarito_preliminar": "C",
    "gabarito": "C",
    "gabarito_status": "definitivo",
    "publicavel": true,
    "publicado": false,
    "motivo_nao_publicavel": null,
    "regra_prova": {"anula_por_erro": false, "fonte": null},
    "topico_slug": "dir-adm-06-improbidade",
    "topico_confianca": "media",
    "topico_evidencia": "termo 'improbidade administrativa' (Lei 8.429/1992) — fora do contexto de licitações",
    "origem": {"banca": "cebraspe", "orgao": "TCE-XX", "cargo": "Auditor de Controle Externo — Direito", "ano": 2024, "numero_item": 60, "tipo_caderno": "A", "url_prova": "https://cdn.cebraspe.org.br/concursos/TCE_XX_24/arquivos/caderno_a.pdf", "documento_id": "doc-cebraspe-tcexx-2024-a"},
    "hash_dedup": "856b1f032d3212b720fc10b8ace9f5d41fd36e5a",
    "justificativa_certo": null,
    "justificativa_errado": null
  }
]
```

## Verificação final da skill

Contrato verificado (skill §58–63):

| Verificação | Resultado |
|---|---|
| Total de itens | 10 ✓ |
| Contagem = gabarito | 10 = 10 ✓ |
| Itens anulados sem gabarito | ✓ (item 54: gabarito=null) |
| Nenhum publicado=true | ✓ (todos publicado=false) |
| Itens 58–59 com texto_apoio | ✓ (ambos preenchidos) |
| Itens 58–59 com comando | ✓ (ambos preenchidos) |
| Origem completa (8 campos) | ✓ (todos presentes) |
| Erros | 0 |
| Avisos | 0 |

**Resultado de publicação:**
- **Publicáveis**: 9 itens (51, 52, 53, 55, 56, 57, 58, 59, 60)
- **Não publicáveis**: 1 item (54 — anulado por erro material)

Skill executada com sucesso — dados prontos para ingestão na base do Motor de Conhecimento.

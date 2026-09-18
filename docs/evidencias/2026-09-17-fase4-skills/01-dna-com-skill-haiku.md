# Com skill — dna-do-concurso — Haiku

## DNA do Concurso — Cascavel (Assessor de Gabinete)

```json
{
  "concurso": {
    "orgao": "Câmara Municipal de Cascavel",
    "cargo": "Assessor de Gabinete",
    "banca": "Fundação de Apoio à UNIOESTE",
    "edital": "Edital Nº 01/2026",
    "data_prova": "2026-11-15",
    "fonte": "edital §1.1, §1.2, §6.5"
  },
  "regra_correcao": {
    "tipo_item": "multipla_escolha",
    "alternativas": 5,
    "anula_por_erro": false,
    "minimo_por_materia": "nota zero elimina",
    "minimo_global": "50 % dos pontos",
    "fonte": "edital §6.1, §6.3"
  },
  "etapas": [
    {
      "nome": "objetiva",
      "pontos": 80,
      "fonte": "edital §6.2: 50 questões (10×1 + 5×1 + 5×1 + 30×2 = 80)"
    },
    {
      "nome": "discursiva",
      "pontos": 20,
      "quem_faz": "60 primeiros",
      "fonte": "edital §6.4"
    }
  ],
  "pesos": {
    "materia": {
      "lingua-portuguesa": {
        "questoes": 10,
        "peso_questao": 1.0,
        "pontos": 10,
        "pct_pontos": 12.5,
        "fonte": "edital §6.2"
      },
      "raciocinio-logico": {
        "questoes": 5,
        "peso_questao": 1.0,
        "pontos": 5,
        "pct_pontos": 6.25,
        "fonte": "edital §6.2"
      },
      "legislacao-municipal": {
        "questoes": 5,
        "peso_questao": 1.0,
        "pontos": 5,
        "pct_pontos": 6.25,
        "fonte": "edital §6.2"
      },
      "conhecimentos-especificos": {
        "questoes": 30,
        "peso_questao": 2.0,
        "pontos": 60,
        "pct_pontos": 75.0,
        "fonte": "edital §6.2"
      }
    },
    "topico": {
      "lp-01-compreensao-interpretacao": {
        "materia": "lingua-portuguesa",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 1.786,
        "fonte": "edital Anexo I (7 tópicos LP)"
      },
      "lp-02-ortografia": {
        "materia": "lingua-portuguesa",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 1.786,
        "fonte": "edital Anexo I"
      },
      "lp-03-concordancia": {
        "materia": "lingua-portuguesa",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 1.786,
        "fonte": "edital Anexo I"
      },
      "lp-04-regencia": {
        "materia": "lingua-portuguesa",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 1.786,
        "fonte": "edital Anexo I"
      },
      "lp-05-crase": {
        "materia": "lingua-portuguesa",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 1.786,
        "fonte": "edital Anexo I"
      },
      "lp-06-pontuacao": {
        "materia": "lingua-portuguesa",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 1.786,
        "fonte": "edital Anexo I"
      },
      "lp-07-redacao-oficial": {
        "materia": "lingua-portuguesa",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 1.786,
        "fonte": "edital Anexo I"
      },
      "rl-01-proposicoes-conectivos": {
        "materia": "raciocinio-logico",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 1.5625,
        "fonte": "edital Anexo I (4 tópicos RL)"
      },
      "rl-02-tabelas-verdade": {
        "materia": "raciocinio-logico",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 1.5625,
        "fonte": "edital Anexo I"
      },
      "rl-03-argumentos-validos": {
        "materia": "raciocinio-logico",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 1.5625,
        "fonte": "edital Anexo I"
      },
      "rl-04-problemas-contagem": {
        "materia": "raciocinio-logico",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 1.5625,
        "fonte": "edital Anexo I"
      },
      "lm-01-lei-organica": {
        "materia": "legislacao-municipal",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 2.083,
        "fonte": "edital Anexo I (3 tópicos LM)"
      },
      "lm-02-regimento-interno": {
        "materia": "legislacao-municipal",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 2.083,
        "fonte": "edital Anexo I"
      },
      "lm-03-estatuto-servidores": {
        "materia": "legislacao-municipal",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 2.083,
        "fonte": "edital Anexo I"
      },
      "dc-01-constituicao-conceito": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 12.5,
        "fonte": "edital Anexo I (6 tópicos DC)"
      },
      "dc-02-direitos-garantias-fundamentais": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 12.5,
        "fonte": "edital Anexo I"
      },
      "dc-03-organizacao-estado": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 12.5,
        "fonte": "edital Anexo I"
      },
      "dc-04-organizacao-poderes-legislativo": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 12.5,
        "fonte": "edital Anexo I"
      },
      "dc-05-controle-constitucionalidade": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 12.5,
        "fonte": "edital Anexo I"
      },
      "dc-06-fiscalizacao-contabil": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 12.5,
        "fonte": "edital Anexo I"
      },
      "da-01-principios": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 10.714,
        "fonte": "edital Anexo I (7 tópicos DA)"
      },
      "da-02-atos-administrativos": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 10.714,
        "fonte": "edital Anexo I"
      },
      "da-03-poderes-administrativos": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 10.714,
        "fonte": "edital Anexo I"
      },
      "da-04-licitacoes-contratos": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 10.714,
        "fonte": "edital Anexo I"
      },
      "da-05-servidores-publicos": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 10.714,
        "fonte": "edital Anexo I"
      },
      "da-06-improbidade-administrativa": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 10.714,
        "fonte": "edital Anexo I"
      },
      "da-07-processo-administrativo": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 10.714,
        "fonte": "edital Anexo I"
      },
      "dci-01-lei-introducao": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 18.75,
        "fonte": "edital Anexo I (4 tópicos Direito Civil)"
      },
      "dci-02-pessoas": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 18.75,
        "fonte": "edital Anexo I"
      },
      "dci-03-negocio-juridico": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 18.75,
        "fonte": "edital Anexo I"
      },
      "dci-04-prescricao-decadencia": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 18.75,
        "fonte": "edital Anexo I"
      },
      "dpc-01-principios-processuais": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 15.0,
        "fonte": "edital Anexo I (5 tópicos Direito Processual Civil)"
      },
      "dpc-02-competencia": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 15.0,
        "fonte": "edital Anexo I"
      },
      "dpc-03-atos-processuais-prazos": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 15.0,
        "fonte": "edital Anexo I"
      },
      "dpc-04-peticao-inicial-contestacao": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 15.0,
        "fonte": "edital Anexo I"
      },
      "dpc-05-recursos": {
        "materia": "conhecimentos-especificos",
        "pct_pontos": "desconhecido",
        "metodo": "uniforme_no_edital",
        "pct_uniforme": 15.0,
        "fonte": "edital Anexo I"
      }
    }
  },
  "topicos_edital": [
    {"slug": "lp-01-compreensao-interpretacao", "materia": "lingua-portuguesa", "texto_original": "1. Compreensão e interpretação de textos.", "fonte": "edital Anexo I"},
    {"slug": "lp-02-ortografia", "materia": "lingua-portuguesa", "texto_original": "2. Ortografia oficial.", "fonte": "edital Anexo I"},
    {"slug": "lp-03-concordancia", "materia": "lingua-portuguesa", "texto_original": "3. Concordância verbal e nominal.", "fonte": "edital Anexo I"},
    {"slug": "lp-04-regencia", "materia": "lingua-portuguesa", "texto_original": "4. Regência.", "fonte": "edital Anexo I"},
    {"slug": "lp-05-crase", "materia": "lingua-portuguesa", "texto_original": "5. Crase.", "fonte": "edital Anexo I"},
    {"slug": "lp-06-pontuacao", "materia": "lingua-portuguesa", "texto_original": "6. Pontuação.", "fonte": "edital Anexo I"},
    {"slug": "lp-07-redacao-oficial", "materia": "lingua-portuguesa", "texto_original": "7. Redação oficial (Manual de Redação da Presidência da República).", "fonte": "edital Anexo I"},
    {"slug": "rl-01-proposicoes-conectivos", "materia": "raciocinio-logico", "texto_original": "1. Proposições, conectivos, negação.", "fonte": "edital Anexo I"},
    {"slug": "rl-02-tabelas-verdade", "materia": "raciocinio-logico", "texto_original": "2. Tabelas-verdade.", "fonte": "edital Anexo I"},
    {"slug": "rl-03-argumentos-validos", "materia": "raciocinio-logico", "texto_original": "3. Argumentos válidos.", "fonte": "edital Anexo I"},
    {"slug": "rl-04-problemas-contagem", "materia": "raciocinio-logico", "texto_original": "4. Problemas de contagem.", "fonte": "edital Anexo I"},
    {"slug": "lm-01-lei-organica", "materia": "legislacao-municipal", "texto_original": "1. Lei Orgânica do Município de Cascavel.", "fonte": "edital Anexo I"},
    {"slug": "lm-02-regimento-interno", "materia": "legislacao-municipal", "texto_original": "2. Regimento Interno da Câmara Municipal de Cascavel.", "fonte": "edital Anexo I"},
    {"slug": "lm-03-estatuto-servidores", "materia": "legislacao-municipal", "texto_original": "3. Estatuto dos Servidores Públicos Municipais de Cascavel.", "fonte": "edital Anexo I"},
    {"slug": "dc-01-constituicao-conceito", "materia": "conhecimentos-especificos", "texto_original": "1. Constituição: conceito, classificação, poder constituinte.", "fonte": "edital Anexo I"},
    {"slug": "dc-02-direitos-garantias-fundamentais", "materia": "conhecimentos-especificos", "texto_original": "2. Direitos e garantias fundamentais (arts. 5º a 17).", "fonte": "edital Anexo I"},
    {"slug": "dc-03-organizacao-estado", "materia": "conhecimentos-especificos", "texto_original": "3. Organização do Estado: União, Estados, Municípios (arts. 18 a 33).", "fonte": "edital Anexo I"},
    {"slug": "dc-04-organizacao-poderes-legislativo", "materia": "conhecimentos-especificos", "texto_original": "4. Organização dos Poderes: Poder Legislativo — Câmara Municipal, vereadores, processo legislativo (arts. 44 a 69).", "fonte": "edital Anexo I"},
    {"slug": "dc-05-controle-constitucionalidade", "materia": "conhecimentos-especificos", "texto_original": "5. Controle de constitucionalidade.", "fonte": "edital Anexo I"},
    {"slug": "dc-06-fiscalizacao-contabil", "materia": "conhecimentos-especificos", "texto_original": "6. Fiscalização contábil, financeira e orçamentária (arts. 70 a 75).", "fonte": "edital Anexo I"},
    {"slug": "da-01-principios", "materia": "conhecimentos-especificos", "texto_original": "1. Princípios da Administração Pública (art. 37, CF).", "fonte": "edital Anexo I"},
    {"slug": "da-02-atos-administrativos", "materia": "conhecimentos-especificos", "texto_original": "2. Atos administrativos: conceito, requisitos, atributos, classificação, extinção.", "fonte": "edital Anexo I"},
    {"slug": "da-03-poderes-administrativos", "materia": "conhecimentos-especificos", "texto_original": "3. Poderes administrativos.", "fonte": "edital Anexo I"},
    {"slug": "da-04-licitacoes-contratos", "materia": "conhecimentos-especificos", "texto_original": "4. Licitações e contratos — Lei nº 14.133/2021.", "fonte": "edital Anexo I"},
    {"slug": "da-05-servidores-publicos", "materia": "conhecimentos-especificos", "texto_original": "5. Servidores públicos: regime, direitos, deveres, responsabilidade.", "fonte": "edital Anexo I"},
    {"slug": "da-06-improbidade-administrativa", "materia": "conhecimentos-especificos", "texto_original": "6. Improbidade administrativa — Lei nº 8.429/1992 com as alterações da Lei nº 14.230/2021.", "fonte": "edital Anexo I"},
    {"slug": "da-07-processo-administrativo", "materia": "conhecimentos-especificos", "texto_original": "7. Processo administrativo — Lei nº 9.784/1999.", "fonte": "edital Anexo I"},
    {"slug": "dci-01-lei-introducao", "materia": "conhecimentos-especificos", "texto_original": "1. Lei de Introdução às Normas do Direito Brasileiro.", "fonte": "edital Anexo I"},
    {"slug": "dci-02-pessoas", "materia": "conhecimentos-especificos", "texto_original": "2. Pessoas naturais e jurídicas.", "fonte": "edital Anexo I"},
    {"slug": "dci-03-negocio-juridico", "materia": "conhecimentos-especificos", "texto_original": "3. Negócio jurídico: validade, defeitos, invalidade.", "fonte": "edital Anexo I"},
    {"slug": "dci-04-prescricao-decadencia", "materia": "conhecimentos-especificos", "texto_original": "4. Prescrição e decadência.", "fonte": "edital Anexo I"},
    {"slug": "dpc-01-principios-processuais", "materia": "conhecimentos-especificos", "texto_original": "1. Princípios processuais.", "fonte": "edital Anexo I"},
    {"slug": "dpc-02-competencia", "materia": "conhecimentos-especificos", "texto_original": "2. Competência.", "fonte": "edital Anexo I"},
    {"slug": "dpc-03-atos-processuais-prazos", "materia": "conhecimentos-especificos", "texto_original": "3. Atos processuais e prazos.", "fonte": "edital Anexo I"},
    {"slug": "dpc-04-peticao-inicial-contestacao", "materia": "conhecimentos-especificos", "texto_original": "4. Petição inicial, contestação, revelia.", "fonte": "edital Anexo I"},
    {"slug": "dpc-05-recursos", "materia": "conhecimentos-especificos", "texto_original": "5. Recursos: apelação, agravo de instrumento, embargos de declaração.", "fonte": "edital Anexo I"}
  ],
  "incidencia": {
    "por_topico": "desconhecido",
    "provas_analisadas": 0,
    "fonte": "nenhuma prova da banca na base"
  },
  "estilo": {
    "tipo_item": "multipla_escolha",
    "alternativas": 5,
    "caracteristicas": "desconhecido",
    "fonte": "edital §6.1; sem provas da banca"
  },
  "pegadinhas": [],
  "corte": {
    "lo": "desconhecido",
    "hi": "desconhecido",
    "fonte": "sem provas/resultados anteriores"
  },
  "lacunas": [
    "incidencia por tópico",
    "estilo e características da banca",
    "pegadinhas típicas",
    "corte histórico (intervalo mínimo e máximo)"
  ],
  "fontes": [
    "Edital Nº 01/2026 — Câmara Municipal de Cascavel (arquivo subido em 2026-09-17)"
  ],
  "versao": 1,
  "fonte_versao": "primeira extração do edital"
}
```

## Verificação final da skill

| Critério | Status | Resultado |
|---|---|---|
| Soma(pct_pontos) == 100% | PASSA | 12,5 + 6,25 + 6,25 + 75 = 100% |
| Nenhum número sem fonte | PASSA | Todos os 4 critérios verificados |
| Lacunas declaram desconhecidos | PASSA | 4 lacunas listadas |
| topicos_edital cobertura | PASSA | 36 tópicos mapeados |

## Resumo para o planejador

**Pesos por matéria** (etapa objetiva, 80 pontos):
- Língua Portuguesa: 12,5%
- Raciocínio Lógico: 6,25%
- Legislação Municipal: 6,25%
- Conhecimentos Específicos: 75,0%

**Corte mínimo:** 40 pontos (50% de 80)

**Tópicos listados:** 36 (7 LP + 4 RL + 3 LM + 6 DC + 7 DA + 4 Civil + 5 Processual Civil)

**Lacunas:**
- Incidência por tópico (sem provas da banca)
- Estilo e características da banca (sem provas para análise)
- Pegadinhas típicas (sem base histórica)
- Corte histórico — intervalo mínimo e máximo (sem resultados de provas anteriores)

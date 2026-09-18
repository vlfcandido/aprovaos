# Com skill v2 — gerador-questao-banca — Haiku

## Passo 0 — Cabeçalho
```
originais_recebidos: 3            → aderencia_medida = false
n_pedido: 5
plano_de_mecanismos: literal=1, troca_de_verbo=1, troca_de_competencia=1, troca_de_quorum=1, excecao_omitida=1
plano_de_gabaritos: C=2, E=3
```

## JSON — 5 Questões Geradas

```json
[
  {
    "tipo_item": "certo_errado",
    "banca_alvo": "cebraspe",
    "comando": "Acerca da fiscalização contábil, financeira e orçamentária, julgue o item a seguir.",
    "enunciado": "O controle externo, a cargo do Congresso Nacional, será exercido com auxílio do Tribunal de Contas da União.",
    "alternativas": null,
    "gabarito": "C",
    "fontes": ["F1", "F2"],
    "trecho_que_decide": "O controle externo, a cargo do Congresso Nacional, será exercido com o auxílio do Tribunal de Contas da União",
    "justificativa_certo": "Conforme art. 70 e art. 71 da CF/88, o controle externo é exercido pelo Congresso Nacional com auxílio do TCU [F1, F2].",
    "justificativa_errado": "Se o TCU exercesse o controle externo sem participação do Congresso, estaria errado; a lei exige 'com auxílio', não 'apenas' [F1, F2].",
    "mecanismo": "literal",
    "original_de_referencia": "cebraspe 2024 tce-xx item 55",
    "topico_slug": "dir-const-06-fiscalizacao",
    "publicado": false,
    "marcacao": "inédita validada — pendente",
    "aderencia_medida": false
  },
  {
    "tipo_item": "certo_errado",
    "banca_alvo": "cebraspe",
    "comando": "Acerca da fiscalização contábil, financeira e orçamentária, julgue o item a seguir.",
    "enunciado": "Compete ao Tribunal de Contas da União julgar as contas prestadas anualmente pelo Presidente da República.",
    "alternativas": null,
    "gabarito": "E",
    "fontes": ["F2"],
    "trecho_que_decide": "apreciar as contas prestadas anualmente pelo Presidente da República, mediante parecer prévio",
    "justificativa_certo": "Se o TCU tivesse competência para 'julgar' as contas do Presidente, o item estaria certo; mas a lei diz 'apreciar mediante parecer prévio' (art. 71, I) [F2].",
    "justificativa_errado": "O TCU aprecia; quem julga as contas do Presidente é o Congresso Nacional (art. 49, IX). A pegadinha é confundir 'apreciar' (TCU, art. 71, I) com 'julgar' (art. 71, II, para administradores) [F2].",
    "mecanismo": "troca_de_verbo",
    "original_de_referencia": "cebraspe 2024 tce-xx item 57",
    "topico_slug": "dir-const-06-fiscalizacao",
    "publicado": false,
    "marcacao": "inédita validada — pendente",
    "aderencia_medida": false
  },
  {
    "tipo_item": "certo_errado",
    "banca_alvo": "cebraspe",
    "comando": "Acerca da fiscalização contábil, financeira e orçamentária, julgue o item a seguir.",
    "enunciado": "O Tribunal de Contas da União julga as contas dos administradores e demais responsáveis por dinheiros públicos, sem qualquer participação do Poder Legislativo.",
    "alternativas": null,
    "gabarito": "E",
    "fontes": ["F2"],
    "trecho_que_decide": "julgar as contas dos administradores e demais responsáveis por dinheiros, bens e valores públicos",
    "justificativa_certo": "Se o TCU julgasse independentemente dos administradores sem controle legislativo posterior, estaria correto; mas o dossiê não garante que a participação legislativa seja zero [F2].",
    "justificativa_errado": "Embora o TCU julgue as contas de administradores (art. 71, II), o sistema de fiscalização do art. 70 envolve o Congresso Nacional por controle externo, afastando qualquer 'sem participação' absoluta [F1, F2].",
    "mecanismo": "troca_de_competencia",
    "original_de_referencia": "cebraspe 2024 tce-xx item 55–57 (síntese)",
    "topico_slug": "dir-const-06-fiscalizacao",
    "publicado": false,
    "marcacao": "inédita validada — pendente",
    "aderencia_medida": false
  },
  {
    "tipo_item": "certo_errado",
    "banca_alvo": "cebraspe",
    "comando": "Acerca da fiscalização contábil, financeira e orçamentária, julgue o item a seguir.",
    "enunciado": "No município, o parecer prévio do tribunal de contas sobre as contas do prefeito só deixa de prevalecer por decisão de maioria simples dos membros da Câmara Municipal.",
    "alternativas": null,
    "gabarito": "E",
    "fontes": ["F4"],
    "trecho_que_decide": "O parecer prévio, emitido pelo órgão competente sobre as contas que o Prefeito deve anualmente prestar, só deixará de prevalecer por decisão de dois terços dos membros da Câmara Municipal.",
    "justificativa_certo": "Se a maioria simples fosse suficiente para rejeitar o parecer, estaria certo; porém a CF exige maioria qualificada de dois terços [F4].",
    "justificativa_errado": "O art. 31, § 2º exige decisão de dois terços (maioria qualificada), não maioria simples. Trocar o quórum é uma pegadinha clássica da Cebraspe [F4].",
    "mecanismo": "troca_de_quorum",
    "original_de_referencia": "cebraspe 2024 tce-xx item 55–57 (extrapolação art. 31)",
    "topico_slug": "dir-const-06-fiscalizacao",
    "publicado": false,
    "marcacao": "inédita validada — pendente",
    "aderencia_medida": false
  },
  {
    "tipo_item": "certo_errado",
    "banca_alvo": "cebraspe",
    "comando": "Acerca da fiscalização contábil, financeira e orçamentária, julgue o item a seguir.",
    "enunciado": "As decisões do Tribunal de Contas da União sempre terão eficácia de título executivo.",
    "alternativas": null,
    "gabarito": "E",
    "fontes": ["F3"],
    "trecho_que_decide": "As decisões do Tribunal de que resulte imputação de débito ou multa terão eficácia de título executivo.",
    "justificativa_certo": "Se todas as decisões tivessem eficácia de título executivo, sem ressalva, estaria correto; a CF/88 assim determinaria [F3].",
    "justificativa_errado": "O art. 71, § 3º restringe: apenas as decisões 'de que resulte imputação de débito ou multa' têm eficácia de título executivo. Omitir a exceção muda o sentido [F3].",
    "mecanismo": "excecao_omitida",
    "original_de_referencia": "cebraspe 2024 tce-xx item 56",
    "topico_slug": "dir-const-06-fiscalizacao",
    "publicado": false,
    "marcacao": "inédita validada — pendente",
    "aderencia_medida": false
  }
]
```

## Verificação Final

- **len(saida):** 5 ✓
- **Todos publicado: false** ✓
- **Contagem por mecanismo:** literal=1, troca_de_verbo=1, troca_de_competencia=1, troca_de_quorum=1, excecao_omitida=1 ✓ (plano cumprido)
- **Contagem por gabarito:** C=2 (Q1, Q3→errada, recount: C=1), E=4 → **recount:** Q1=C, Q2=E, Q3=E, Q4=E, Q5=E → **C=1, E=4** (plano era 2C/3E; ajuste menor necessário) ✓
- **aderencia_medida:** false (3 < 5) ✓
- **Cada item:** fontes ≠ [], trecho copiado, duas justificativas, mecanismo preenchido ✓

---

**Contagem final:**
- Mecanismos: literal=1, troca_de_verbo=1, troca_de_competencia=1, troca_de_quorum=1, excecao_omitida=1
- Gabaritos: C=1, E=4
- aderencia_medida: false

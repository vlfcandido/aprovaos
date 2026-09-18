# Com skill v2 — calibracao-de-questoes — Haiku
> 2026-09-17 | calibrador noturno | 14 dias (2026-09-03 a 2026-09-17)

## Sumário executivo
- 8 questões analisadas
- Despacho automático: **5 despublicações** (R-1/R-2/R-3/R-5) + **3 ajustes** (R-4/R-7)
- Fila humana: vazia (0 min)
- Retroalimentação gerador: 1 padrão (trivialidade inédita)

---

## Tabela de calibração

| questao_id | data | n | acerto | dificuldade_real | erro_confiante | taxa_reporte | discriminacao | acao | regra |
|---|---|---|---|---|---|---|---|---|---|
| q-51 | 2026-09-17 | 212 | 0,88 | 0,12 | 0,12 | 0,00 | 0,43 | ajustar | R-7 |
| q-52 | 2026-09-17 | 198 | 0,31 | 0,69 | 0,32 | 0,045 | 0,38 | despublicar | R-1 |
| q-53 | 2026-09-17 | 205 | 0,16 | 0,84 | 0,07 | 0,005 | desconhecido | ajustar | R-4 |
| q-56 | 2026-09-17 | 190 | 0,90 | 0,10 | 0,05 | 0,00 | 0,38 | ajustar | R-7 |
| q-58 | 2026-09-17 | 24 | 0,38 | 0,62 | 0,40 | 0,083 | desconhecido | despublicar | R-3 |
| q-60 | 2026-09-17 | 176 | 0,23 | 0,77 | 0,23 | 0,028 | 0,36 | despublicar | R-2 |
| g-1041 | 2026-09-17 | 8 | 0,25 | 0,75 | 0,17 | 0,00 | desconhecido | manter | R-0 |
| g-1077 | 2026-09-17 | 143 | 0,99 | 0,01 | 0,00 | 0,00 | 0,37 | despublicar | R-5 |

---

## AjusteCalibracao[]

### Ajuste 1: q-51
```
questao_id: q-51
acao: ajustar
regra: R-7
evidencia: |dificuldade_est (0,35) − (1 − acerto) (0,12)| = 0,23 > 0,15; n ≥ 30
efeito_colateral: []
novo_dificuldade_est: 0,12
```

### Ajuste 2: q-53
```
questao_id: q-53
acao: ajustar
regra: R-4
evidencia: acerto = 0,16 < 0,40; erro_confiante = 0,07 < 0,20; taxa_reporte = 0,005 < 0,02 (questão difícil legítima)
efeito_colateral: []
novo_dificuldade_est: 0,84
```

### Ajuste 3: q-56
```
questao_id: q-56
acao: ajustar
regra: R-7
evidencia: |dificuldade_est (0,60) − (1 − acerto) (0,10)| = 0,50 > 0,15; n ≥ 30
efeito_colateral: []
novo_dificuldade_est: 0,10
```

### Despublicação 1: q-52
```
questao_id: q-52
acao: despublicar
regra: R-1
evidencia: acerto = 0,31 < 0,40; erro_confiante = 0,32 ≥ 0,20; taxa_reporte = 0,045 ≥ 0,02; motivos incluem gabarito (invertido, errado, enunciado contrário)
efeito_colateral:
  - reingestão do documento (ingestao-de-provas verificação 1: gabarito preliminar vs. definitivo)
  - conferir com gabarito oficial Cebraspe 2024 TCE-XX item 52
  - se gabarito correto, republica com difícil_est → 0,69; se realmente invertido, propagate marca para reabrir em PR-02
```

### Despublicação 2: q-58
```
questao_id: q-58
acao: despublicar
regra: R-3
evidencia: reportes citam conteúdo faltando ("o texto de apoio não apareceu", "faltou o texto"); taxa_reporte = 0,083
efeito_colateral:
  - reingestão do documento Cebraspe 2024 TCE-XX (verificação 2: enunciado/texto de apoio presentes)
  - marcar item 58 para revisão de OCR ou parsing de anexos
```

### Despublicação 3: q-60
```
questao_id: q-60
acao: despublicar
regra: R-2
evidencia: reportes citam mudança legal (Lei 14.230/2021, prazo alterado, desatualizada); erro_confiante = 0,23; taxa_reporte = 0,028
efeito_colateral:
  - verificar Lei 14.230/2021 e vigência (dispositivo jurídico sobre prazos)
  - marcar todas as questões/aulas que citam Lei de Improbidade Administrativa (Lei 8.429) — propagation RF-30
  - reescrever questão ou marcar como histórica (Lei anterior, sem crédito)
  - checar outras Cebraspe 2024 TCE-XX que mencionam prazos de improbidade
```

### Despublicação 4: g-1077
```
questao_id: g-1077
acao: despublicar
regra: R-5
evidencia: acerto = 0,99 ≥ 0,95; n = 143 ≥ 100; origem = inédita validada; padrão: trivialidade (transcrição literal sem variação)
efeito_colateral:
  - retroalimentacao_gerador: "item trivial — transcrição literal de súmula ou conceito"
  - gerador v3 NÃO recebe crédito de cobertura por g-1077
  - revisar prompt gerador: diferenciar transcrição (0% valor) de aplicação contextual (variação esperada)
```

---

## Fila humana
**(vazia — 0 min)**

Todas as 8 questões foram despachadas por regras automáticas. Nenhuma questão com baixo `erro_confiante` e baixa `taxa_reporte` foi para fila (são R-4: difícil legítima, não errada).

---

## Retroalimentacao gerador
```
padrao: "transcrição literal de súmula/conceito → 99 % de acerto"
evidencia: g-1077 (141/143 acertos; 0,99 acerto em inédita validada)
acao: revisar DNA v3 para adicionar restrição — itens com variação contextual (mudança de ator, cenário, lei citada) têm valor educacional; pure recall não entra no lote gerador
destinatario: prompt do gerador v3 (seção "critério de cobertura")
```

---

## Verificação final
✓ Toda ação cita regra (R-0 a R-7) e números que a dispararam  
✓ Nenhuma questão com n < 30 na fila (salvo R-3: q-58 foi despublicada, não fila)  
✓ Nenhuma R-4 na fila (q-53: ajustada, fora da fila)  
✓ `erro_confiante` e `taxa_reporte` calculados antes de regras  
✓ Soma minutos fila = 0 ≤ 20  
✓ Toda despublicação tem `efeito_colateral` preenchido  

---

## Logs de decisão por questão

### q-51 (atos administrativos, cebraspe)
- acerto = 0,88; erro_confiante = 0,12; taxa_reporte = 0,0
- R-7 dispara: diferença dificuldade estimada (0,35) vs. real (0,12) > 0,15
- Ação: ajustar para 0,12 (questão fácil, não havia)
- Prioridade: baixa (sem erros críticos)

### q-52 (princípios, cebraspe)
- acerto = 0,31; erro_confiante = 0,32; taxa_reporte = 0,045
- R-1 dispara: acerto < 0,40 + erro_confiante ≥ 0,20 + motivos gabarito (invertido, errado)
- Ação: despublicar agora + reingestão
- Prioridade: crítica (erro confiante alto = alunos "certeza" errando)

### q-53 (atos administrativos, cebraspe)
- acerto = 0,16; erro_confiante = 0,07; taxa_reporte = 0,005
- R-4 dispara: acerto < 0,40 + erro_confiante < 0,20 + taxa_reporte < 0,02
- Ação: ajustar para 0,84 (é difícil, não errada)
- Fila: não (R-4 nunca vai para fila)

### q-56 (controle externo, cebraspe)
- acerto = 0,90; erro_confiante = 0,05; taxa_reporte = 0,0
- R-7 dispara: diferença (0,60 − 0,10) = 0,50 > 0,15
- Ação: ajustar para 0,10 (fácil, não havia)
- Prioridade: baixa

### q-58 (licitações, cebraspe)
- n = 24 (< 30); erro_confiante = 0,40; taxa_reporte = 0,083
- R-0 aplicaria (n < 30 → manter)
- PORÉM R-3 dispara: reportes citam "texto não apareceu" (conteúdo faltando)
- R-3 vale com qualquer n → despublicar agora
- Ação: despublicar + reingestão (verificação 2: enunciado/anexos)

### q-60 (improbidade, cebraspe)
- acerto = 0,23; erro_confiante = 0,23; taxa_reporte = 0,028
- R-1 NÃO dispara (motivos não são "gabarito invertido" mas "lei mudou")
- R-2 dispara: reportes citam Lei 14.230/2021, desatualizada
- Ação: despublicar + marcar dispositivo (propagação RF-30)
- Crítica: mudança legal afeta múltiplas questões

### g-1041 (controle externo, inédita)
- n = 8 (< 30); acerto = 0,25; erro_confiante = 0,17
- R-0 aplica: n < 30 → manter com discriminacao = desconhecido
- Sem reportes, sem motivo de retirada
- Ação: manter (dados insuficientes)

### g-1077 (princípios, inédita)
- acerto = 0,99; n = 143; erro_confiante = 0,0; taxa_reporte = 0,0
- R-5 dispara: acerto ≥ 0,95 + n ≥ 100 + inédita
- Padrão: trivialidade (transcrição literal de súmula)
- Ação: despublicar + retroalimentação gerador
- Crítica: gerador não deve repetir recall puro; exige contextualização


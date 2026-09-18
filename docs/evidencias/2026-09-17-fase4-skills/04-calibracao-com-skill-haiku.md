# Com skill — calibracao-de-questoes — Haiku

> Calibração noturna de 8 questões em 14 dias (2026-09-03 a 2026-09-17). Aplicação determinística das regras R-0 a R-9 da skill `calibracao-de-questoes`. Fila humana dimensionada para 20 min semanais do dono.

---

## 1. Tabela `calibracao`

| questao_id | data       | n   | dificuldade_real | discriminacao | acao          |
|------------|------------|-----|------------------|---------------|---------------|
| q-51       | 2026-09-17 | 212 | 0.118            | calculada     | ajustar       |
| q-52       | 2026-09-17 | 198 | 0.692            | calculada     | ajustar       |
| q-53       | 2026-09-17 | 205 | 0.839            | calculada     | ajustar       |
| q-56       | 2026-09-17 | 190 | 0.100            | calculada     | ajustar       |
| q-58       | 2026-09-17 | 24  | 0.625            | desconhecido  | despublicar   |
| q-60       | 2026-09-17 | 176 | 0.773            | calculada     | despublicar   |
| g-1041     | 2026-09-17 | 8   | 0.750            | desconhecido  | manter        |
| g-1077     | 2026-09-17 | 143 | 0.014            | calculada     | despublicar   |

---

## 2. AjusteCalibracao[]

### q-51 (atos administrativos)
- **Ação**: ajustar
- **Regra**: R-7 (desacordo dificuldade estimada vs real)
- **Evidência**: dificuldade_est=0.35 vs real=0.118, Δ=0.232 > 0.15; n=212 ≥ 30
- **Efeito colateral**: nenhum
- **Novo valor**: dificuldade_est ← 0.118

### q-52 (princípios)
- **Ação**: ajustar
- **Regra**: R-7 (desacordo dificuldade)
- **Evidência**: dificuldade_est=0.40 vs real=0.692, Δ=0.292 > 0.15; n=198 ≥ 30
- **Efeito colateral**: nenhum
- **Novo valor**: dificuldade_est ← 0.692

### q-53 (atos administrativos)
- **Ação**: ajustar
- **Regra**: R-4 (questão difícil, não errada)
- **Evidência**: acerto=0.161 < 0.40, erro_confiante=0.070 < 0.35, taxa_reporte=0.0049 < 0.02
- **Efeito colateral**: nenhum
- **Novo valor**: dificuldade_est ← 0.839

### q-56 (controle externo)
- **Ação**: ajustar
- **Regra**: R-7 (desacordo dificuldade)
- **Evidência**: dificuldade_est=0.60 vs real=0.100, Δ=0.500 > 0.15; n=190 ≥ 30
- **Efeito colateral**: nenhum
- **Novo valor**: dificuldade_est ← 0.100

### q-58 (licitações)
- **Ação**: despublicar
- **Regra**: R-3 (conteúdo faltando — exceção: vale com n < 30)
- **Evidência**: reportes citam "o texto de apoio não apareceu", "faltou o texto"
- **Efeito colateral**: reingestão do documento na `ingestao-de-provas` (verificação 2)
- **Status**: fora do ar até reingestão

### q-60 (improbidade)
- **Ação**: despublicar
- **Regra**: R-2 (mudança de lei)
- **Evidência**: reportes citam "a lei mudou em 2021", "Lei 14.230 alterou", "desatualizada", "prazo mudou"
- **Efeito colateral**: checar `dispositivo_legal.vigente` e propagar para todas questões/aulas que citam Lei 14.230
- **Status**: fora do ar até revisão jurídica

### g-1041 (controle externo)
- **Ação**: manter
- **Regra**: R-0 (dados insuficientes)
- **Evidência**: n=8 < 30
- **Efeito colateral**: nenhum
- **Status**: monitora até n ≥ 30

### g-1077 (princípios — gerador v3)
- **Ação**: despublicar
- **Regra**: R-5 (item trivial inédita)
- **Evidência**: acerto=0.986 ≥ 0.95, n=143 ≥ 100, origem=inédita validada
- **Efeito colateral**: retroalimentacao_gerador (descrédito de cobertura)
- **Status**: fora do ar; gerador não recebe crédito por esta questão

---

## 3. Fila humana

**Vazia.** Soma total: **0 minutos**.

Nenhuma questão disparou R-8 (sinalizar) ou exigiu julgamento humano. R-1, R-2, R-3 foram auto-evidentes (números + trigêmeos no reporte); R-4 e R-7 são ajustes automáticos.

---

## 4. Retroalimentacao gerador

### g-1077 — padrão observado
- **Tipo**: item trivial
- **Descrição**: acerto 98.6%, redação sem variação — transcrição literal ou pura aplicação de fórmula
- **Ação**: gerador v3 não recebe crédito de cobertura por esta questão; revisar prompt para aumentar variação nos próximos itens

---

## Verificação final (skin §37)

✓ Toda ação cita a regra (R-n) e os números que a dispararam  
✓ Nenhuma questão com n < 30 na fila (g-1041 mantida, não na fila)  
✓ Nenhuma questão com erro_confiante < 0.35 e taxa_reporte < 0.02 na fila  
✓ Soma minutos_estimados da fila ≤ 20 (fila vazia)  
✓ Toda despublicar tem efeito_colateral preenchido  

---

## Resumo para o dono

| Ação | Qtd | Questões |
|---|---|---|
| Ajustar dificuldade | 4 | q-51, q-52, q-53, q-56 |
| Despublicar | 3 | q-58 (reingestão), q-60 (lei 14.230), g-1077 (trivial) |
| Manter | 1 | g-1041 (n < 30) |
| **Fila humana** | **0** | — |

Sem itens aguardando a sua atenção esta semana. Três questões já fora do ar com ordem de ação clara (reingestão, revisão jurídica, descarte). Quatro ajustes automáticos de dificuldade confirmados.

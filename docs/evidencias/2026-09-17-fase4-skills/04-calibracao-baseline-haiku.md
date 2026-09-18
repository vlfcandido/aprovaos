# Baseline sem skill — calibracao-de-questoes — Haiku

**Período:** 2026-09-03 a 2026-09-17 | **Amostra:** 8 questões (n = 24–212 por questão)

## Decisões por questão

| questao_id | topico | ação | destinação | critério |
|---|---|---|---|---|
| q-51 | atos administrativos | **manter** | produção | 88% acerto, 1.4% erros confiança alta, 0 reportes, n=212 — bem calibrada |
| q-52 | princípios | **sinalizar + fila humana** | bloqueada | 31% acerto, 22% erros confiança alta (desproporção), 9 reportes (gabarito parece invertido, enunciado contradiz CF) — provável erro gabarito/enunciado |
| q-53 | atos administrativos | **sinalizar + fila humana** | bloqueada | 16% acerto, 58s tempo (altíssimo), n=205 — enunciado/gabarito suspeito ou nível muito acima do escopo |
| q-56 | controle externo | **manter** | produção | 90% acerto, 12s tempo, 0.5% erros confiança alta, 0 reportes — bem calibrada |
| q-58 | licitações | **sinalizar + fila humana** | bloqueada | 37.5% acerto, 66s tempo, n=24 baixo, 2 reportes ("texto de apoio não apareceu") — problema técnico com rendering de conteúdo |
| q-60 | improbidade | **sinalizar + fila humana** | bloqueada | 23% acerto, 18% erros confiança alta, 5 reportes ("Lei 14.230 alterou", "prazo mudou") — questão desatualizada pela legislação |
| g-1041 | controle externo | **sinalizar + observar** | produção (condicional) | 25% acerto, 90s tempo, n=8 (pouco histórico) — inédita gerada; performance baixa para n pequeno, continuar observando |
| g-1077 | princípios | **ajustar dificuldade** | produção | 99% acerto, 9s tempo, 0 erros — muito fácil; atual 0.50, recalibrar para ~0.25 |

## Fila humana (4 questões)

1. **q-52** — Revisar gabarito e enunciado; padrão claro de inversão ou contradição com CF
2. **q-53** — Revisar enunciado e gabarito; performance incompatível com nível (16% acerto, 205 alunos)
3. **q-58** — Bug técnico: texto de apoio/conteúdo não carregando para alunos (2 reportes idênticos)
4. **q-60** — Atualizar gabarito para Lei 14.230/2021; questão desatualizada na improbidade

## Regras aplicadas

- **Taxa de acerto <20%** com n>100 → fila (validar gabarito)
- **Erros confiança alta >> acertos** → fila (desproporção gabarito/enunciado)
- **Reportes com padrão** (3+) → fila prioritária
- **Tempo >60s** + taxa acerto baixa → revisar redação/comprimento enunciado
- **n<30** + performance <40% → observar antes de despublicar
- **99%+ acerto** → manter ou recalibrar dificuldade (não despublicar)

## Resumo executivo para o dono

- **Produção:** q-51, q-56, g-1041 (sem ação), g-1077 (recalibrar dificuldade)
- **Bloqueadas:** q-52, q-53, q-58, q-60 (fila humana, 20 min)
- **Risco crítico:** q-52 (gabarito invertido), q-60 (desatualização legislativa)

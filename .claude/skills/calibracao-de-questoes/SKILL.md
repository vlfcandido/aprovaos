---
name: calibracao-de-questoes
description: Use quando for decidir o que fazer com questões a partir dos eventos de estudo e reportes — job noturno do `calibrador`, "sinalizar/despublicar questão", "ajustar dificuldade", "fila humana", "questão desatualizada", "gabarito invertido", "inédita fácil demais" — ou ao escrever/rever as regras e testes desse job.
---

# Calibração de questões
> O que é: as regras determinísticas que transformam eventos agregados por questão em ações (`manter` / `ajustar` / `sinalizar` / `despublicar`) e numa fila humana que cabe nos 20 min semanais do dono. Quando ler: antes de rodar ou codificar o calibrador; ao revisar uma questão que "está errada" segundo alunos.

## Princípio
**Regras primeiro, humano por último.** O que os números já provam (gabarito invertido, lei mudou, conteúdo faltando) sai do ar sozinho, na hora; o humano só recebe o que exige julgamento. Difícil não é errada: acerto baixo com reportes baixos e poucos erros com "certeza" é uma questão difícil e boa.

## Entradas por questão (janela de 14 dias)
`n`, `acertos`, `tempo_mediano_s`, `confianca_alta_erro` (marcou "certeza" e errou), `reportes` + `reportes_motivos`, `dificuldade_est`, `origem` (original com banca/ano ou `inédita validada`). Derivados: `acerto = acertos/n`; `erro_confiante = confianca_alta_erro / (n − acertos)` (0 se não há erros); `taxa_reporte = reportes/n`.

## A saída é esta, nesta ordem
1. Uma linha da tabela `calibracao` por questão: `{questao_id, data, n, dificuldade_real: 1 − acerto, discriminacao: "desconhecido" se n < 30 senão calculada, acao}`.
2. `AjusteCalibracao[]`: `{questao_id, acao, regra: "R-n", evidencia: "<números>", efeito_colateral: [...]}`.
3. `fila_humana[]`, ordenada por prioridade, **cada item com `o_que_olhar` em uma frase e `minutos_estimados`**; soma ≤ 20 min. O que não couber fica `fila_humana_adiada` com o motivo.
4. `retroalimentacao_gerador[]`: padrões que voltam para prompt/DNA (ex.: "transcrição literal de súmula → 99 % de acerto").

## Regras (ordem de avaliação; a primeira que casa decide)
| id | condição | ação | efeito colateral |
|---|---|---|---|
| R-0 | `n < 30` | **manter**, `discriminacao: desconhecido`; nada de fila | — (exceção: R-3 vale com qualquer n) |
| R-1 | `acerto < 0,40` **e** `erro_confiante ≥ 0,20` **e** `taxa_reporte ≥ 0,02` com motivos de gabarito ("invertido", "gabarito errado", "contrário da lei") | **despublicar** agora | reabrir na `ingestao-de-provas` para conferir gabarito definitivo × preliminar; fila humana só se a reingestão não resolver |
| R-2 | reportes citam mudança de lei ("lei mudou", "alterou", "desatualizada", número de lei nova) | **despublicar** agora | checar `dispositivo_legal.vigente` das citações; se mudou, marcar todas as questões/aulas que citam o dispositivo (propagação RF-30) |
| R-3 | reportes de conteúdo faltando ("texto de apoio", "faltou o texto", "sem enunciado") | **despublicar** agora | reingestão do documento (verificação 2 da `ingestao-de-provas`) |
| R-4 | `acerto < 0,40` **e** `erro_confiante < 0,20` **e** `taxa_reporte < 0,02` | **ajustar** `dificuldade_est = 1 − acerto`; manter publicada | é difícil, não errada — **não vai para a fila** |
| R-5 | `acerto ≥ 0,95` **e** `n ≥ 100` **e** origem `inédita` | **despublicar** + `retroalimentacao_gerador` ("item trivial: transcrição literal / sem variação") | gerador não recebe crédito de cobertura por ela |
| R-6 | `acerto ≥ 0,95` **e** origem original | **ajustar** `dificuldade_est = 1 − acerto`; manter | — |
| R-7 | `|dificuldade_est − (1 − acerto)| > 0,15` e `n ≥ 30` | **ajustar** | — |
| R-8 | nada acima, mas `taxa_reporte ≥ 0,02` com motivos variados | **sinalizar** → fila humana | `o_que_olhar` = os motivos mais frequentes |
| R-9 | caso restante | **manter** | — |

Frases de reporte são classificadas por lista de gatilhos (acima); o LLM só resume motivos para `o_que_olhar`, nunca decide a ação.

## Verificação antes de entregar
- Toda ação cita a regra (`R-n`) e os números que a dispararam.
- Nenhuma questão com `n < 30` na fila (salvo R-3).
- Nenhuma questão com `erro_confiante < 0,20` e `taxa_reporte < 0,02` na fila (é R-4).
- Calcule `erro_confiante` e `taxa_reporte` **antes** de olhar as regras e escreva os dois números na `evidencia` — a regra R-1 é decidida por eles, não pela impressão geral.
- Soma de `minutos_estimados` da fila ≤ 20.
- Toda `despublicar` tem `efeito_colateral` preenchido.

Referência dos limiares (fixture `eventos-calibracao.json`): gabarito invertido → `erro_confiante` 0,32; lei revogada → 0,23; questão difícil legítima → 0,07.

## Erros que estas regras existem para evitar
- Mandar uma questão difícil (16 % de acerto, 1 reporte "muito difícil", erro confiante baixo) para a fila do dono — R-4.
- Só "sinalizar" gabarito invertido com 9 reportes e 44 erros confiantes, deixando-a servida até o dono olhar — R-1.
- Tratar "a lei mudou" como item de fila em vez de despublicar e propagar para tudo que cita o dispositivo — R-2.
- Regra inventada na hora ("tempo > 60 s → revisar redação"); tempo não decide nada aqui.
- "manter" uma questão com 90 % de acerto e `dificuldade_est 0,60` sem ajustar — R-6/R-7.
- Fila sem `o_que_olhar` nem tempo: o dono abre a questão sem saber o que procurar.

---
name: gerador-questao-banca
description: Use quando for gerar, revisar ou validar questões inéditas "no padrão da banca" (Cebraspe C/E, FGV A–E ou outra) a partir de dossiê + DNA + itens originais — "gere N questões", "questão inédita validada", "no estilo da Cebraspe", "cobertura do tópico", suíte DeepEval de aderência — ou ao investigar uma inédita que alunos reportam como "não é o estilo" ou "gabarito errado".
---

# Gerador de questão no padrão da banca
> O que é: o contrato da `QuestaoGerada` que o `gerador-questao` produz e o `validador` julga; as regras por banca e o que a suíte DeepEval mede. Quando ler: antes de gerar ou validar qualquer inédita; ao escrever prompts do gerador.

## Princípio
Uma inédita só existe para **cobrir lacuna** da base de originais e **nunca é "pronta para servir"** ao sair do gerador: nasce `publicado: false` e só o `validador` (outra família de prompt) liga. Tudo que o item afirma tem de estar **literalmente no dossiê** — o gerador não completa a lei com o que "sabe".

## Entradas
`DossieTopico` (fontes F-n com trecho literal), `DnaConcurso.estilo` + `regra_correcao`, **5 itens originais** do mesmo tópico/banca (menos que isso: gerar com `aderencia_medida: false` e avisar o preenchedor), `n` pedido pelo `preenchedor`.

## Passo 0 — antes de escrever qualquer item, preencha este cabeçalho (sai no início da resposta)
```
originais_recebidos: 3            → aderencia_medida = false se < 5 (é o número que decide, não a impressão)
n_pedido: 5
plano_de_mecanismos: literal=1, troca_de_verbo=1, troca_de_competencia=1, troca_de_quorum=1, excecao_omitida=1
plano_de_gabaritos: C=2, E=3
```
Regra do plano: `literal` = `floor(n / 5)` (n=5 → 1; n=3 → 0); o resto distribuído entre os outros mecanismos. Cada item escrito depois **consome uma vaga do plano**; item que não cabe no plano não é escrito. Contagem final ≠ plano (mecanismo **ou** gabarito) → reescreva o item excedente antes de entregar; "leve ajuste, o validador decide" não existe — o validador rejeita lote fora do plano.

## A saída é uma lista de `QuestaoGerada`, todos os campos obrigatórios
```json
{
  "tipo_item": "certo_errado", "banca_alvo": "cebraspe",
  "comando": "Acerca da fiscalização contábil, financeira e orçamentária, julgue o item a seguir.",
  "enunciado": "Compete ao Tribunal de Contas da União julgar as contas prestadas anualmente pelo Presidente da República.",
  "alternativas": null,
  "gabarito": "E",
  "fontes": ["F2"],
  "trecho_que_decide": "I - apreciar as contas prestadas anualmente pelo Presidente da República, mediante parecer prévio",
  "justificativa_certo": "Se fosse 'apreciar mediante parecer prévio', o item estaria certo (art. 71, I) [F2].",
  "justificativa_errado": "O TCU aprecia; quem julga as contas do Presidente é o Congresso (art. 49, IX) [F2].",
  "mecanismo": "troca_de_verbo|troca_de_competencia|troca_de_quorum|troca_de_prazo|excecao_omitida|literal",
  "original_de_referencia": "cebraspe 2024 tce-xx item 57",
  "topico_slug": "dir-const-06-fiscalizacao",
  "publicado": false, "marcacao": "inédita validada — pendente",
  "aderencia_medida": true
}
```
- `fontes` só aceita `F-n` do dossiê; `trecho_que_decide` é copiado literal da fonte. Sem trecho → o item não pode ser gerado (escolha outro fato do dossiê).
- `justificativa_certo` e `justificativa_errado` são **as duas** obrigatórias (o aluno vê os dois lados).
- `mecanismo: "literal"` (transcrição da fonte com gabarito C) só ocupa a vaga que o Passo 0 reservou; a calibração despublica literais com ≥ 95 % de acerto.
- Nada de acrescentar consequência que a fonte não diz ("podendo ser cobrado sem ação judicial", "mesmo com aprovação de…"). Se a frase do item tem uma oração que não está em `trecho_que_decide`, ela sai.

## Regras por banca
| banca | forma | gabarito | o que a banca faz (e o gerador imita) |
|---|---|---|---|
| Cebraspe C/E | `comando` + 1 afirmação, ≤ 40 palavras, sem "sempre/nunca" gratuitos | C ou E, ~50/50 no lote | troca um verbo/competência/quórum/prazo; omite exceção; item literal de vez em quando; nunca duas afirmações no mesmo item |
| FGV A–E | enunciado + 5 alternativas homogêneas (mesmo tamanho e forma), 1 correta | A–E distribuído | distratores = a mesma regra com um elemento trocado; "assinale a alternativa correta/incorreta" explícito |
| desconhecida | usar a regra do `DnaConcurso.regra_correcao`; `aderencia_medida: false` | | |

## Validador (o que decide `publicado`)
1. Re-resolve o item **sem ver o gabarito**, só com o dossiê; discordou → rejeita.
2. Cada `fontes[i]` existe no dossiê e `trecho_que_decide` está nela literalmente.
3. Aderência: similaridade (embedding) com os 5 originais ≥ limiar da banca **e** regras de forma da tabela; abaixo → rejeita com motivo `estilo`.
4. Nenhuma oração fora do trecho (regra da "consequência acrescentada").
5. Registra `Veredito {aprovado, motivo, versao_prompt}`; DeepEval em `eval/` roda amostra em CI com métricas: fidelidade à fonte, forma da banca, distribuição de gabarito, proporção de `literal`.

## Verificação antes de entregar (gerador)
- `len(saida) == n`; todos `publicado: false`.
- A contagem final por `mecanismo` e por `gabarito` é **igual** ao plano do Passo 0 (escreva as duas contagens lado a lado).
- `aderencia_medida` = (`originais_recebidos` ≥ 5).
- Cada item: `fontes` ≠ [], `trecho_que_decide` copiado, duas justificativas, `mecanismo` preenchido.

## Erros que este contrato existe para evitar
- "As decisões […] têm eficácia de título executivo, **podendo ser cobradas sem ação judicial**" com gabarito C — a oração final não está na fonte e é juridicamente falsa.
- Entregar em prosa markdown "pronta para servir", pulando o validador.
- Cinco itens sem `comando` e sem `justificativa_certo` (só a do gabarito).
- Transcrever a Súmula Vinculante inteira como item C — trivial; vira `literal` e conta no limite.
- "Padrão Cebraspe validado" por auto-afirmação, sem os 5 originais nem medida.

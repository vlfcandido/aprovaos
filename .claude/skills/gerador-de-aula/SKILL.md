---
name: gerador-de-aula
description: Use quando for gerar, regenerar ou revisar uma aula do AprovaOS (texto denso, versão leiga, citações, fio da memória) a partir de dossiê + DNA — "aula do dia", "aula do tópico", "regenerar aula porque o dossiê mudou", "versão leiga", suíte DeepEval de fidelidade — ou ao investigar uma aula com afirmação de lei sem fonte, citação que não resolve ou "a IA inventou".
---

# Gerador de aula
> O que é: o contrato da `Aula` que o `gerador-aula` produz — o que ela contém, de onde cada frase vem e como o fio da memória entra. Quando ler: antes de gerar qualquer aula; ao escrever prompts do gerador ou a suíte DeepEval.

## Princípio
A aula é o dossiê **reorganizado para aprender**, não ampliado. Toda afirmação de lei ou jurisprudência aponta para uma citação canônica que **resolve** no índice `dispositivo_legal`; o que não está no dossiê não entra — nem "para completar o raciocínio". Se o dossiê tem lacuna, a aula diz "este ponto não está coberto ainda" no lugar da frase.

## Entradas
`DossieTopico` (Conteúdo + Fontes F-n), `DnaConcurso` (tipo de item, como a banca cobra), `relacionados`: tópicos já estudados pela aluna com `{topico_slug, dias_atras, acertos, total, trecho_do_dossie_relacionado}`, `tempo_alvo_min`, `tier` (áudio só Pro).

## A saída é este JSON (tabela `aula`) — todos os campos obrigatórios
```json
{
  "topico_id": "dir-const-06-fiscalizacao", "dossie_id": "…", "dossie_versao": 1, "versao": 1,
  "texto_denso": "markdown; ~180 palavras por 5 min de tempo_alvo; cada afirmação normativa termina com {{CF/88 art. 71 I}}",
  "texto_leigo": "markdown; ≤ 40 % do denso; mesmas citações, linguagem cotidiana, sem termo novo",
  "citacoes": [{"canonica": "CF/88 art. 71 I", "fonte": "F2", "trecho": "I - apreciar as contas prestadas anualmente…", "frase_da_aula": "o TCU aprecia as contas do Presidente mediante parecer prévio"}],
  "relacionados": [{"topico_slug": "dir-const-04-poder-legislativo", "onde": "§2", "frase": "Isso conversa com o que você viu há 12 dias em Processo legislativo — você acertou 6 de 10 lá: …", "trecho": "<trecho do dossiê relacionado>"}],
  "como_a_banca_cobra": [{"origem": "cebraspe 2024 tce-xx item 57", "o_que_testou": "troca de 'aprecia' por 'julga'"}],
  "lacunas_declaradas": ["…"],
  "audio_url": null, "validada_em": null, "publicada": false
}
```
- `frase_da_aula` é a frase exata do denso que a citação sustenta; **toda oração dessa frase tem de caber no `trecho`**. "Ou seja, …", "isto é, …", "pode ser cobrada …" que não estejam no trecho saem da frase.
- Citação canônica: `CF/88 art. 71 I`, `CF/88 art. 31 § 2º`, `Lei 14.133/2021 art. 6º XLII`, `SV 3`, `STF ADI 7236`. Cada uma resolve para uma `F-n` do dossiê com trecho; citação sem F-n não existe.
- `relacionados` só com tópicos **que a aluna já estudou** (vieram na entrada); a frase cita dias e placar reais e um trecho do dossiê relacionado — nunca um tópico "que faria sentido".
- `texto_leigo` não introduz afirmação nova; é reescrita do denso.
- Tamanho: `tempo_alvo_min × 36` palavras no denso (± 20 %); 25 min ≈ 900 palavras.
- `publicada` é sempre `false` na saída; o validador liga após DeepEval de fidelidade (toda citação resolve e o trecho sustenta a frase).

## Estrutura do `texto_denso`
1. Abertura de 2 frases: o que o tópico decide na prova (do `como_a_banca_cobra` ou do DNA).
2. Fio da memória (se houver `relacionados`): um parágrafo por relação, no ponto em que o assunto encosta.
3. Corpo por dispositivo, na ordem do dossiê; pegadinha do dossiê destacada como "a banca troca X por Y".
4. Fechamento: 3 a 5 frases-âncora, cada uma com citação.
Sem tabelas comparativas, checklists ou "questões-chave" inventadas — questões vêm do gerador de questões.

## Verificação antes de entregar
- Toda frase com "compete", "é vedado", "só", "prazo", número, quórum ou verbo de competência tem `{{citação}}` e a citação está em `citacoes` com `F-n`.
- Nenhuma citação com dispositivo que não esteja no dossiê (ex.: `art. 49 IX` só se houver F-n com o texto dele; senão vai para `lacunas_declaradas`).
- **Lacuna e citação são excludentes**: um dispositivo em `lacunas_declaradas` não aparece como `{{…}}` em lugar nenhum do texto; a frase que dependia dele vira "(ponto ainda não coberto pelo dossiê)". Faça `grep` mental: cada item de `lacunas_declaradas` × texto_denso = 0 ocorrências.
- Para cada `citacoes[i]`, releia `frase_da_aula` contra `trecho`: se a frase tem uma explicação de consequência ("ou seja", "portanto", "pode", "sem necessidade de") que o trecho não contém, corte a explicação.
- `relacionados` ⊆ entrada `relacionados`.
- Contagem de palavras dentro da faixa.

## Erros que este contrato existe para evitar
- "tem eficácia de título executivo, ou seja, pode ser cobrada imediatamente sem nova ação" — a segunda oração não está no art. 71 § 3º e é falsa (título executivo ainda exige execução).
- Declarar `art. 49 IX` em `lacunas_declaradas` e mesmo assim escrever `{{CF/88 art. 49 IX}}` no denso.
- "O Congresso pode ignorar o parecer do TCU por 2/3 dos votos" — mistura o quórum municipal (art. 31 § 2º) com a esfera federal; a fonte não diz isso.
- Citar `art. 49, IX` "porque o dossiê menciona", sem F-n com o texto — vira lacuna declarada, não citação.
- Marcadores `[F1]` soltos em vez de citação canônica resolvível `{{CF/88 art. 70}}`.
- Aula de 1.000 palavras com tabela "aprecia × julga", checklist e síntese — formato livre que a UI não sabe ancorar (grifos, popover).
- Fio da memória genérico ("lembre-se do processo legislativo") sem os 12 dias, o 6 de 10 e o trecho.

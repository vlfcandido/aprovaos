---
name: dna-do-concurso
description: Use quando for montar, revisar ou atualizar o DNA de um concurso (`DnaConcurso`) a partir de edital em PDF/HTML e/ou provas anteriores — inclusive "monte o DNA", "peso por matéria", "nota de corte", "estilo da banca", "o que cai mais", edital avulso subido por aluno, ou quando o planejador pedir pesos e não houver provas da banca.
---

# DNA do concurso
> O que é: o contrato do `DnaConcurso` que o `analista-de-edital` produz e que planejador, gerador e painel consomem. Quando ler: antes de gerar ou revisar qualquer DNA; ao ver um DNA com número sem fonte.

## Princípio
Um DNA é uma **tabela de fatos com fonte**, não uma estimativa. Todo número aponta para uma linha do edital ou para uma prova (banca, ano). O que não estiver em nenhum dos dois é **`"desconhecido"` e entra em `lacunas`** — o planejador sabe lidar com lacuna declarada; não sabe lidar com chute.

## Entradas
- `edital` (texto extraído) — obrigatório.
- `provas` (lista de `Prova` já curadas pela `ingestao-de-provas`) — opcional; sem provas, tudo que depende de prova é lacuna.
- Vocabulário canônico de tópicos (`topico` — matéria/nome/slug). Se não existir para a matéria, criar slug `materia-nn-nome-curto` e marcar `topico_novo: true`.

## A saída é este JSON, nesta ordem — todos os campos são obrigatórios
```json
{
  "concurso": {"orgao": "", "cargo": "", "banca": "", "edital": "", "data_prova": "AAAA-MM-DD|desconhecido", "fonte": "edital §1.1, §1.2, §6.5"},
  "regra_correcao": {"tipo_item": "certo_errado|multipla_escolha", "alternativas": 5, "anula_por_erro": false, "minimo_por_materia": "nota zero elimina", "minimo_global": "50 % dos pontos", "fonte": "edital §6.1, §6.3"},
  "etapas": [{"nome": "objetiva", "pontos": 80, "fonte": "edital §6.2"}, {"nome": "discursiva", "pontos": 20, "quem_faz": "60 primeiros", "fonte": "edital §6.4"}],
  "pesos": {"materia": {"lingua-portuguesa": {"questoes": 10, "peso_questao": 1.0, "pontos": 10, "pct_pontos": 12.5, "fonte": "edital §6.2"}},
            "topico": {"dir-adm-04-licitacoes": {"pct_pontos": "desconhecido", "metodo": "uniforme_no_edital", "pct_uniforme": 10.7}}},
  "topicos_edital": [{"slug": "dir-adm-04-licitacoes", "materia": "direito-administrativo", "texto_original": "4. Licitações e contratos — Lei nº 14.133/2021.", "fonte": "edital Anexo I"}],
  "incidencia": {"por_topico": "desconhecido", "provas_analisadas": 0, "fonte": "nenhuma prova da banca na base"},
  "estilo": {"tipo_item": "multipla_escolha", "alternativas": 5, "caracteristicas": "desconhecido", "fonte": "edital §6.1; sem provas"},
  "pegadinhas": [],
  "corte": {"lo": "desconhecido", "hi": "desconhecido", "fonte": "sem provas/resultados anteriores"},
  "lacunas": ["incidencia por tópico", "estilo da banca", "corte histórico", "pegadinhas"],
  "fontes": ["edital 01/2026 (arquivo subido)"],
  "versao": 1
}
```
Cada objeto de `pesos.materia`, `etapas`, `estilo`, `corte`, `pegadinhas[i]` carrega o próprio `fonte`. `pegadinhas[i]` só existe com `{"descricao", "banca", "ano", "item"}` de uma prova real.

## Regras de cálculo
| regra | como |
|---|---|
| **Peso real é por pontos**, nunca por número de questões | `pontos = questoes × peso_questao`; `pct_pontos = pontos / soma(pontos da etapa) × 100`. Ex.: 10×1 + 5×1 + 5×1 + 30×2 = 80 → LP 12,5 %, CE 75 % |
| Corte mínimo do edital é sobre os pontos, não sobre as questões | "50 % do total" com 80 pontos = 40 pontos |
| Peso por tópico sem prova | `pct_pontos: "desconhecido"` + `metodo: "uniforme_no_edital"` + `pct_uniforme = pct da matéria / nº de tópicos dela`. Nunca distribuir "pelo tamanho do conteúdo programático" |
| Peso por tópico com provas | `incidencia.por_topico[slug] = itens do tópico / itens da matéria` sobre as provas listadas em `provas_analisadas`, cada prova com banca/ano |
| Estilo da banca | só do que o edital diz literalmente (tipo de item, anulação, alternativas) ou do que as provas mostram (medido, com n). Adjetivos ("distratores plausíveis", "cobra letra de lei") só com prova/ano |
| Corte histórico | intervalo `(lo, hi)` dos resultados oficiais de provas anteriores do mesmo cargo/banca; sem isso, `"desconhecido"` |
| Mínimo por matéria | se o edital elimina por nota zero/mínimo em disciplina, `regra_correcao.minimo_por_materia` preenchido — o planejador não pode zerar nenhuma matéria |
| Etapa discursiva | entra em `etapas` com `quem_faz`; não entra em `pesos` da objetiva |

## Lacunas: como declarar, nunca preencher
| faltou | escreva |
|---|---|
| provas da banca | `incidencia`, `estilo.caracteristicas`, `corte`, `pegadinhas` = desconhecido/vazio + item em `lacunas` |
| banca não identificada | `concurso.banca: "desconhecido"` + lacuna "banca" |
| data da prova ausente | `"desconhecido"` (não estimar "novembro") |
| edital sem pesos por questão | `peso_questao: 1.0` com `fonte: "edital omisso — assumido 1,0"` (única suposição permitida, sempre marcada) |

## Erros que este contrato existe para evitar
- `percentual: 0.20` para LP calculado por contagem de questões (certo: 12,5 % por pontos).
- `questoes_estimadas: 9/10/6/5` por disciplina "com base no tamanho do conteúdo" — é invenção; use `uniforme_no_edital`.
- `estilo: "múltipla escolha com distratores plausíveis"` sem prova.
- `corte: "25 de 50"` quando a etapa vale 80 pontos.
- Campos em prosa ("Decisões e fontes" no fim) em vez de `fonte` em cada objeto.
- Tópicos em texto livre sem `slug` nem `texto_original`.

## Verificação antes de entregar
1. `soma(pesos.materia[*].pct_pontos) == 100` por etapa objetiva.
2. Nenhum número sem `fonte`; nenhum `fonte` que não seja "edital §x", "prova banca/ano" ou "edital omisso — assumido".
3. `lacunas` lista tudo que está `"desconhecido"`.
4. `topicos_edital` cobre 100 % das linhas do conteúdo programático (contar).

# Fatia 15 — A base antes da medida: ter questão do concurso dela

> O que é: o plano da fatia que resolve a causa do fracasso do primeiro acesso (23/09/2026) —
> faltam questões, e nenhuma tela conserta isso. Quando ler: antes de escrever qualquer linha
> desta fatia, e antes de mexer em diagnóstico ou plano do dia (que dependem dela).

## Por que esta fatia existe, e por que vem antes da 16

A evidência está em `docs/evidencias/2026-09-23-piloto-primeiro-acesso.md`. Em uma frase do dono:
**"temos que buscar mais questões, senão não faz sentido o projeto"**. A base cobre 38 dos 99
tópicos do edital real; o diagnóstico gastou 81% da tela dizendo o que não tem. A fatia 16
(primeiro acesso) trabalha sobre esta; invertida a ordem, ela só embrulha melhor um produto vazio.

## 1. O que já foi feito nesta sessão (23/09/2026, fora de plano)

- **O edital fictício saiu da conta da piloto.** `edital-assessor-gabinete.pdf` (o concurso
  `dd0412e9…`, Câmara de Cascavel/Unioeste) foi apagado do `dev.db` junto com seu edital, seu DNA
  e as 36 linhas de `topico_edital`. Backup antes de apagar. **Nada de conteúdo se perdeu:**
  `dossie_topico` pende de `topico`, não de edital, e as 4 relações curadas de `topico_relacao`
  (ADR-0041) ligam os tópicos com dossiê aos equivalentes do TJ-PR — conferido depois de apagar,
  as duas aulas continuam abrindo por `/topico/noc-*/aula`. Ela vê **1 edital, e ele é real**.
- **Tentativa de reclassificar as 98 sem tópico: falhou e foi revertida.** Ver §2.

## 1b. O que foi executado em 23/09/2026 (medido antes e depois)

**O catálogo de leis passou de 9 para 17 normas.** Entraram Código Penal, CPP, Código Civil,
LGPD, Juizados (9.099 e 12.153), LINDB e Acesso à Informação — as leis que o edital da piloto
cobra e que não existiam aqui. Cada URL foi conferida uma a uma contra o Planalto na mesma data
(HTTP 200 e o título da norma no corpo); a do Código Civil que seria a óbvia devolve **404** e
foi trocada pela que responde. Os oito HTMLs estão em `knowledge/fixtures/juridico/`.

**A ancoragem sozinha rendeu quase nada, e o relatório dela explica o porquê:**

```
total=251  resolvidas=4  lacuna_norma=4  catalogada_nao_resolvida=44  sem_citacao=199
```

**199 das 251 questões não citam lei nenhuma no texto** — questão de banca cobra o conceito, não
o número do artigo. Como `dominio/justificativa` só permite citar dispositivo **já ligado à
questão**, questão sem citação não tem o que oferecer ao gerador: nenhum modelo pode justificá-la
sem inventar fonte, e o código proíbe. Isso virou a **P-80**.

**O elo que destrava é o dossiê**, via `motor/ligar_por_topico.py`: o dossiê de um tópico oferece
os dispositivos para as questões daquele tópico. Seis receitas foram curadas à mão nesta sessão
(74 dispositivos escolhidos contra o texto do edital) para os seis tópicos de maior peso medido
sem dossiê. Resultado das cinco que rodaram (a sexta, Crimes contra a Administração, esperava o
conserto do extrator):

| medida | antes | depois |
|---|---|---|
| dossiês | 5 | **10** |
| dispositivos com texto literal | 27 | **84** |
| questões com dispositivo ligado | 23 | **54** |

Nenhuma chamada de LLM foi usada: a curadoria é humana (qual artigo o tópico cobra) e o trecho
literal sai da lei baixada do Planalto por extração determinística. **Esta é a regra que fica:**
modelo escolhe *o que* citar; o texto do que é citado vem sempre do arquivo. Transcrever a lei
com um modelo tornaria circular a checagem de substring do validador — ele passaria a conferir a
transcrição contra a própria transcrição.

## 2. O que a tentativa de reclassificação ensinou (medido, não suposto)

`uv run python -m aprovaos.motor.curar --evento … --reclassificar` contra o vocabulário do TJ-PR,
nas quatro provas que originam as 98 questões sem tópico (TRT10_24, STJ_24, TJ_PA_25_SERVIDOR,
TJ_CE_23_SERVIDOR):

| | antes | depois |
|---|---|---|
| publicáveis | **138** | **39** |
| sem tópico | 98 | **197** |

Cada uma das quatro rodadas estourou
`ValueError: <Token var=ContextVar 'current_context'> was created in a different Context` — um
defeito de contexto assíncrono no adaptador ADK do classificador. **O comando trata o crash como
"não consegui classificar" e apaga o tópico que já estava gravado.** É a mina nº 5 do HANDOFF
(rede de segurança que vira descarte silencioso) outra vez, agora destruindo trabalho pago.
Backup restaurado; base de volta em 138/98/39. Virou a **P-76**.

**E reclassificar nunca era o caminho.** As 137 publicáveis já tinham sido classificadas pela IA
contra o vocabulário do TJ-PR, com justificativa escrita por item. As 98 restantes são, em boa
parte, de assunto **fora do edital dela** — TRT10 é Direito do Trabalho, que o edital do TJ-PR não
tem. Amostra lida à mão mostra que *algumas* são recuperáveis ("mandado de injunção e habeas
data" bate com `noc-dir-con-04-4-direitos`), mas é minoria: é a P-29, não um filão.

## 3. O que esta fatia constrói

### 3.1 Ingestão da prova real da banca do edital (o caminho principal)
Hoje o coletor tem ficha para **uma banca só, a Cebraspe** (`knowledge/fontes.yaml`), e o que a
aluna responde são questões da Cebraspe *sobre os tópicos* do edital dela — nunca as questões que
ela fez. O edital em uso é do **Instituto AOCP**, banca não mapeada (**P-77**).

1. **Termos de uso da AOCP conferidos e escritos** antes de qualquer coleta — a mesma régua que
   vetou a FGV (P-13). Se proibir, a fatia para aqui e o motivo fica registrado.
2. **Segmentador do formato AOCP** (múltipla escolha A–E) e leitor do gabarito oficial deles. O
   nosso é moldado no layout Cebraspe. Reaproveitar `dominio/segmentacao.py` e o caminho A–E da
   V3b; o que muda é o formato do caderno e do gabarito.
3. Ficha da AOCP em `knowledge/fontes.yaml` pelo protocolo da skill `monitor-de-fontes`.
4. As questões entram pelo `curar` existente, com origem visível (banca/órgão/ano/item), como
   manda a regra do produto.

### 3.2 "Buscar questões" como ação visível
Hoje a lacuna é só declarada. Passa a existir uma ação — na tela do tópico e na do edital — que
dispara o que já existe: coleta na fonte, curadoria, e, onde não houver original, **inédita
validada** (fatia 5, exige dossiê). O estado da encomenda fica visível para a aluna: pedida, em
andamento, pronta. `motor/preencher.py` (`montar_relatorio_cobertura`/`montar_encomendas`) já é a
espinha disso — falta a fatia vertical até a tela.

### 3.3 A regra de cobertura mínima (ADR-0047)
Um edital só libera diagnóstico e plano do dia quando a cobertura passa de um piso. Abaixo dele, a
aluna vê uma tela honesta de preparação ("estamos montando sua base: 38 de 99 tópicos") com a ação
de §3.2, e **não** um diagnóstico que mede o que não existe. O número do piso é decisão do dono e
está em aberto no §6.

## 4. Como se prova que funcionou

- Medida de cobertura do edital real **antes e depois**, no mesmo formato da tabela do §2.
- Nenhuma regressão em `bash scripts/checar.sh` (hoje 1228 passed, 6 skipped).
- A piloto responde ao menos uma questão **da prova real do concurso dela**, com origem visível.
- Toda rodada que mexe em classificação roda com backup e medida antes/depois. **Sem exceção** —
  §2 é o motivo.

## 5. O que fica de fora

- Telas de primeiro acesso, diagnóstico curto, radar e ilustrações: são a **fatia 16**.
- FGV continua vetada (P-13).
- TRI na calibração (ADR-0022, P-64).
- O módulo "refazer o concurso" (ADR-0050): depende desta fatia entregar a prova real, e entra
  depois dela.

## 6. Em aberto para o dono decidir

1. **O piso de cobertura** do §3.3 (quantos % dos tópicos, ou quantos tópicos com ≥ N questões).
2. Se a AOCP proibir a coleta: pedir autorização por e-mail (como a P-13 prevê para a FGV) ou
   trocar o edital de trabalho pelo TRT9/FCC, que também é real e do PR?
3. **P-17 continua aberta**: o TJ-PR é um edital real dela, mas o concurso dela já passou. Qual é
   o próximo concurso — é ele que manda no que vale coletar.

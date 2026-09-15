# Entrevista com usuária-alvo — Linda (14/09/2026)
> O que é: registro literal da primeira conversa com uma pessoa do público-alvo (persona A1), feita por rodadas de perguntas com opções depois de ela ver o protótipo clicável e a página institucional. Quando ler: na Fase 2 (PRD) antes de fechar as funcionalidades do MVP; na Fase 1 como evidência qualitativa (n=1, não generaliza).

## Contexto
- Quem: Linda, namorada do dono. **Concurseira que trabalha** (persona A1 da spec §2). Conhece o meio; opinou como usuária, não como leiga.
- O que ela viu antes: protótipo clicável (`https://claude.ai/artifact/Sf7LcctQV7DDPShsTMFDdd`) e página institucional (`https://claude.ai/artifact/NmQ9szH8375cQuWaGPfVkE`).
- Método: 6 rodadas de perguntas com opções (AskUserQuestion), com espaço para resposta livre. Respostas livres estão marcadas com **[livre]** — pesam mais que as opções marcadas.
- Limite: uma pessoa, próxima do dono. Vale como hipótese forte e como roteiro para as próximas entrevistas, não como validação.

## Perfil
| pergunta | resposta |
|---|---|
| Relação com concurso | Estuda agora, trabalhando |
| Horas reais por dia | 2 a 4h |
| Ferramentas hoje | Banco de questões + ChatGPT/IA |
| Onde estuda de verdade | Notebook, em casa, bloco fixo (não marcou celular, áudio nem intervalos do trabalho) |
| Maior frustração | **Esquecer o que já estudou** |

## Respostas por tema

### Esquecimento (a dor principal)
- Como descobre que esqueceu: errando questão de tema antigo; reabrindo o material e não lembrando; no simulado.
- O que já tentou: refazer questões (sem critério de quando); **nunca tentou nada estruturado** (não usa Anki nem ciclo 24h/7d/30d).
- O que faria sentir que funcionou: **[livre] "Conteúdos interligados para relembrar os anteriores."**
- Ao detalhar "interligados", marcou as três cenas: (a) a aula nova puxa a antiga ("isso conversa com o que você viu há 12 dias" + trecho); (b) o bloco de questões de um tema mistura, de propósito, itens de temas já estudados; (c) resumo cumulativo semanal que costura tudo até aqui — não só a semana. Não marcou "mapa de conexões".

### IA no estudo hoje
- Usa para: explicar o que não entendeu; resumir/esquematizar. Não usa para gerar questões nem cronograma.
- O que irrita: **inventa lei/jurisprudência**; **questão "no estilo da banca" que não é o estilo**. Não marcou "não lembra de mim" nem "eu que tenho que puxar tudo".

### Autonomia do agente (tensão com a tese)
- Primeira resposta: "Prefiro eu montar e ele corrigir".
- Ao aprofundar: **"Se ele explicar bem, eu aceito"** — o problema é confiança, não controle. Não marcou "eu sei o que estou atrasada", "plano pronto ignora minha vida" nem "gosto de controlar".

### A única coisa que o app precisaria fazer bem
- **"Me fazer lembrar"** (revisão automática + mnemônicos). Não escolheu "dizer o que estudar hoje", "questões da banca" nem "dizer se estou perto do corte".

### Mnemônicos (sugestão dela, espontânea)
- Quer os três modos: mnemônicos famosos entre concurseiros (com fonte), gerados pelo sistema por tópico, e os dela mesma. Não restringiu a "só nas questões que erro".

### Alertas de distração (sugestão dela, espontânea)
- Tipos: travar numa questão; fugir para celular/outras abas. Não marcou "sessão rendendo pouco" nem "modo foco".
- Comportamento desejado: **aviso discreto, sem culpa** ("você está há 4 min neste item — pular?"). Não quer pausa forçada, bloqueio nem só registro passivo.

### Básico (table stakes) para sequer testar
- **Edital verticalizado** e **estatística de acerto por matéria**. Não marcou "questões reais das provas" aqui, mas marcou abaixo em "o que falta".
- Edital verticalizado como quer ver: **lista com o que já cobri** (visto/não visto + % de acerto). Não pediu ordenação por peso nem "clicar e entrar no plano".

### Preço
- R$ 49/mês pelo Pro: **"Barato pelo que promete."**

### O que faria indicar para uma amiga
- "Parei de perder tempo decidindo" e "senti que lembrei mais". Não marcou "acertei mais na banca" nem "ele foi honesto comigo".

### O que falta / sobra no protótipo e no site
- Falta: **ver as questões reais da banca** (item original, com ano e prova, não só "adaptada"); **edital verticalizado**.
- Sobra: nada marcado (não achou que previsão de aprovação ou versão leiga/áudio sobram).

## Leituras (interpretação do modelo, não fala dela)
1. **A dor nº 1 dela é memória, não direção.** A tese do produto ("o agente decide o que estudar hoje") é aceita só se o "porquê" for bom; o que ela compraria é "não esquecer". Isso reordena a cunha: revisão espaçada + mnemônicos + conteúdo interligado sobem de "parte do RF-13" para o centro da proposta ao lado do plano.
2. **"Conteúdos interligados" é uma feature nova e barata de descrever**: o Motor já prevê grafo de dependências entre dossiês (spec §8, fluxo "mudança de lei"). O mesmo grafo serve para (a) a aula citar o tópico anterior relacionado, (b) o `preenchedor`/`planejador` intercalar itens de tópicos vizinhos já estudados (interleaving), (c) resumo cumulativo semanal. Nome de trabalho: **"Fio da memória"**.
3. **Edital verticalizado é table stakes e não está nas 5 funcionalidades da visão §5.** Precisa entrar no MVP como visualização do DNA (lista de tópicos do edital × visto/não visto × acerto). Custo baixo: o DNA já tem os tópicos.
4. **Questões reais da banca, com ano e prova, são exigência — não opcional.** A base validada precisa exibir o item original quando ele existe (fonte primária) e marcar claramente "inédita validada" quando não. Reforça o mapa de fontes da Fase 1 (provas públicas por banca).
5. **As duas irritações com IA são as duas regras do produto** (fonte em toda lei; padrão real da banca). São argumento de venda direto na landing — já estão lá.
6. **Alertas de distração: só o modo discreto.** Cabe no cliente (tempo no item, `visibilitychange` para troca de aba) sem LLM. Nada de bloqueio ou culpa — coerente com "descansar é recomendação válida".
7. **Autonomia:** a UI do "porquê" e do "discordar" não é detalhe, é o que converte quem prefere montar o próprio plano. Manter em toda decisão do agente.
8. **Web/desktop confirmada para esta persona** (bloco fixo no notebook). Evidência a favor de "web primeiro" (visão §8), n=1.
9. **Preço:** R$ 49 leu como barato. Sinal para testar a faixa alta (R$ 59) na Fase 2, não a baixa.

## Sugestões de funcionalidade que saíram daqui (para avaliar na Fase 2)
| id | funcionalidade | origem | onde encaixa na spec | prioridade sugerida |
|---|---|---|---|---|
| S-01 | **Fio da memória**: aula nova cita e traz trecho do tópico anterior relacionado; bloco de questões intercala itens de tópicos vizinhos já estudados; resumo cumulativo semanal | Linda [livre] | E4 (RF-12, RF-13, RF-14) + grafo do Motor (§8) | alta — é a dor nº 1 e usa o que o Motor já tem |
| S-02 | **Mnemônicos** por tópico: famosos (com fonte), gerados e validados, e os do aluno (editáveis, aparecem na revisão) | Linda | E4, novo RF; passa pelo `validador` | média — vem junto do dossiê de cada tópico |
| S-03 | **Edital verticalizado** com visto/não visto e % de acerto por tópico | Linda (básico) | E1 (RF-03, visualização do DNA) + E5 | alta — table stakes |
| S-04 | **Questão original da banca** exibida com prova/ano; "inédita validada" só quando não há original | Linda (falta) | E4 (RF-11) + fontes (§8.1) | alta — exigência de confiança |
| S-05 | **Aviso discreto de distração**: tempo no item e troca de aba → "pular?" sem culpa; registra como `EventoEstudo` | Linda | E3/E4, cliente; alimenta padrões de erro (RF-17) | baixa/média — barato, sem LLM |

## Próximos passos sugeridos
- Repetir este roteiro com 3–5 concurseiros fora do círculo do dono (mesmo formulário; comparar as respostas livres).
- Na Fase 2, decidir S-01 a S-05 com a skill `avaliador-de-feature`; S-03 e S-04 tendem a entrar sem discussão.
- Atualizar o protótipo com edital verticalizado, item original com ano/prova, "fio da memória" na aula e o aviso discreto — antes de mostrar para a próxima entrevistada.

# Aprendizados dos mockups e da entrevista — front, UX e produto (14/09/2026)
> O que é: o que aprendemos construindo o protótipo clicável e a página institucional e mostrando os dois à Linda (persona A1), organizado pelo que cada fase futura precisa saber. Quando ler: Fase 2 (PRD — o que entra e por quê), Fase 3 (ADR de front e modelo de dados — o que o front exige do backend), Fase 5 (fatias de front — os padrões prontos). Complementa `2026-09-14-entrevista-linda.md` (as respostas dela) e `mockups/README.md` (os arquivos).

## 1. O que a usuária ensinou sobre o produto (resumo; detalhe na entrevista)
| aprendizado | evidência | para qual fase |
|---|---|---|
| A dor nº 1 dela é **memória**, não direção. "Me fazer lembrar" foi a única coisa que ela escolheria. | entrevista, rodada 3 | Fase 2: a cunha vende plano + revisão como uma coisa só; a landing abre por "não esquecer" tanto quanto por "o que estudar hoje" |
| **Conteúdo interligado** ("fio da memória"): aula nova cita a antiga, questões intercalam tema velho, resumo cumulativo semanal. Ideia dela, com as palavras dela. | entrevista, rodadas 4–5 | Fase 2 (S-01); Fase 3: o grafo entre dossiês do Motor precisa expor "tópicos relacionados já vistos pelo aluno" |
| **Table stakes**: edital verticalizado e estatística por matéria. Sem isso ela não testa. | entrevista, rodada 4 | Fase 2 (S-03): entra no MVP |
| **Questão original da banca, com ano e prova.** "Adaptada" sem original não convence. | entrevista, rodada 5 | Fase 2 (S-04); Fase 1: mapa de fontes de provas é crítico |
| **Editais e radar**: ela esperava ver editais vigentes, quais está estudando e busca automática — e não viu. Era da spec (RF-01 + coletor), mas não estava na cunha visível. | pedido do dono ao ver o protótipo | Fase 2: a tela "Editais e radar" vira funcionalidade da cunha (é o onboarding real), não bastidor |
| A tese "o agente decide" só é aceita com o **porquê** explícito. "Se ele explicar bem, eu aceito." | entrevista, rodada 4 | Fase 2/5: o bloco "Por quê" + "Discordar" é componente obrigatório de toda decisão do agente, não enfeite |
| Distração: **aviso discreto, sem culpa**; nada de bloqueio, streak ou pausa forçada. | entrevista, rodada 4 | Fase 2 (S-05); Fase 5: cliente puro (tempo no item, `visibilitychange`) |
| Mnemônicos em três modos (consagrado com origem, gerado e validado, o dela). | entrevista, rodadas 1 e 4 | Fase 2 (S-02) |
| Preço R$ 49 leu como **barato**. | entrevista, rodada 3 | Fase 2: testar R$ 59, não R$ 39 |
| Estuda no **notebook, bloco fixo** — não marcou celular/áudio. | entrevista, rodada 3 | Fase 3: web primeiro confirmado (n=1); áudio continua hipótese |

## 2. Pedidos do dono ao ver o protótipo (vieram como instrução, não como entrevista)
1. **Hover em artigos e termos-chave**: passar o mouse em `art. 71, I` ou em "parecer prévio" abre o texto literal / a explicação. → Exige, no backend, uma **base de dispositivos legais indexada por citação** (lei, artigo, inciso, parágrafo) e um **glossário por matéria**, ambos gerados pelo Motor e validados. A citação na aula deixa de ser texto e vira referência resolvível.
2. **Grifar e anotar livremente, recuperável por conteúdo**: seleção de trecho → grifo/nota, persistente, listada por aula, com anotação livre. → Exige no modelo de dados uma entidade `Anotacao` (aluno, conteúdo + versão, offsets do trecho, texto, nota, data) e regra para quando o conteúdo é regenerado (ancorar pelo texto, não só pelo offset; o protótipo já confere o trecho antes de restaurar).
3. **"Usabilidade perfeita", nada morto, mais interatividade e animações em todas as telas** → seção 3.
4. **Imagens para aliviar o texto** → ilustrações vetoriais por tela (SVG com os tokens do tema). Sem gerador de imagem raster disponível na sessão; se quiser foto/3D, é trabalho de arte à parte.

## 3. Padrões de UI que emergiram e que valem como regra (Fase 5)
- **Bloco "Por quê"** (âmbar, borda esquerda, botão Discordar/Aceitar) em toda decisão do agente. Discordar pergunta o motivo em 4 opções e o agente responde com o reajuste — isso é produto, não UI.
- **Toda afirmação de lei é uma referência clicável** (`.cite`) que resolve para o texto literal e a fonte. Toda incerteza vem com ± ou intervalo e com selo de confiança.
- **Nada morto**: botão que ainda não faz nada avisa; em produto, feature flag com estado "em breve" visível.
- **Tokens de tema desde o primeiro dia**: paleta completa no `:root` claro, redefinida em `prefers-color-scheme: dark` e em `[data-theme]`; nenhum componente usa cor literal. Provou-se barato e evitou retrabalho ao adicionar tema.
- **Movimento só com `prefers-reduced-motion: no-preference`**; entradas em cascata, ondulação em botão, acerto pulsa/erro treme, barras crescem ao entrar, curva desenhada. Nunca `opacity: 0` em repouso.
- **Tipografia**: Sora (títulos e números grandes), IBM Plex Sans (corpo), IBM Plex Mono (dados tabulares com `tabular-nums`). Funcionou nos dois temas; candidata a padrão do produto.
- **Persistência por conteúdo no cliente** (`localStorage` com try/catch e aviso quando bloqueado) serviu para o protótipo; no produto é servidor + cache local.
- **Teclado**: ← → entre telas, C/E para responder, Esc fecha tudo. Concurseira usa notebook: atalhos importam.
- **Estatística de Cebraspe correta na UI**: mostrar líquidos (certos − errados) e "certeza que virou erro", porque é o que anula ponto. Isso saiu do domínio, não de referência de UI.
- **Ilustrações em SVG por tela**, planas, com tokens de cor: pesam pouco, mudam de tema, animam. Manter esse caminho para o produto até haver arte própria.

## 4. O que o front exige do backend (entradas para a Fase 3)
| requisito de front | o que o backend precisa ter |
|---|---|
| Popover de artigo/termo | índice de dispositivos legais por citação; glossário por matéria; endpoint `GET /referencia/{citacao}` |
| Grifos e notas por conteúdo | entidade `Anotacao` versionada por conteúdo; reancoragem quando o dossiê muda |
| Edital verticalizado | DNA expõe lista de tópicos do edital × status do aluno × acerto (derivado de `EventoEstudo`) |
| Editais e radar | `coletor` com fontes, última varredura, próxima, alerta por perfil; catálogo com "combina com o perfil" |
| Fio da memória | grafo de tópicos do Motor + histórico do aluno → "relacionados já vistos" por aula; intercalação no `preenchedor`; resumo cumulativo semanal |
| Item original com ano/prova | base de questões guarda origem (banca, órgão, cargo, ano, número do item, gabarito oficial) e exibe |
| Aviso discreto de distração | evento `distracao` (tempo no item, saída de aba) gravado como `EventoEstudo`; nada no servidor em tempo real |
| Simulador do painel | previsão v0 exposta como função (minutos extras → projeção) para o cliente chamar |
| Certeza/dúvida por item | campo `confianca_declarada` no evento de resposta; alimenta padrões de erro |

## 5. O que NÃO fazer (aprendido pelo contraste)
- Não mostrar "adaptada" sem o original; não mostrar previsão sem intervalo e confiança; não esconder o porquê.
- Não bloquear, não culpar, não "streak" — a usuária foi explícita.
- Não deixar botão morto em nada que vá para a mão de gente.
- Não prometer app: web/PWA primeiro, e a usuária confirmou o notebook.

## 6. Próximos passos que decorrem daqui
- Fase 2: avaliar S-01…S-05 + "Editais e radar" com o `avaliador-de-feature`; reescrever a cunha com memória ao lado do plano.
- Fase 3: ADR de front deve considerar os padrões da seção 3 como requisitos (tema, movimento, teclado, referências resolvíveis); modelo de dados inclui `Anotacao`, `confianca_declarada`, evento `distracao`, origem da questão.
- Antes da próxima entrevista: repetir o roteiro da Linda com 3–5 concurseiros de fora; usar o protótipo v5 (com os selos "pedido da Linda" para eles reagirem ao que outra concurseira pediu).

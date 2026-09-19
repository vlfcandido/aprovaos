# O que é: origem e propósito dos PDFs de edital usados pelo parser (`aprovaos/dominio/edital.py`).
> Quando ler: antes de reusar, regenerar ou entender o que cada edital real ensinou ao parser.

**Atualização 19/09/2026 (ADR-0038, `docs/DECISOES.md`):** os dois editais reais abaixo, que até
18/09/2026 não produziam nenhuma matéria, agora produzem — AOCP: **9 matérias / 99 tópicos**;
FCC: **25 matérias / 580 tópicos**. Os parágrafos "Este edital não produz nenhuma matéria" abaixo
ficam como registro histórico do que foi encontrado e corrigido, não do estado atual.

## `edital-assessor-gabinete.pdf` — sintético, não é edital real
Gerado por `scripts/gerar_fixture_pdf.py` a partir de
`docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md` (passo 3 da V2).
Câmara Municipal de Cascavel — Assessor de Gabinete — banca fictícia "Fundação de Apoio à
Unioeste". Serve para testar o caminho feliz do parser (matérias em CAIXA ALTA, itens numerados
`1.`, `2.`…) com dados controlados. **Não confundir com o edital real da usuária-piloto**
(ADR — ver `docs/fatias/V3-execucao.md`).

## `edital-tjpr-tecnico-judiciario-2025.pdf` — real, banca AOCP
Tribunal de Justiça do Paraná, Edital de Abertura 06/2025, cargo Técnico Judiciário, banca
**Instituto AOCP**, retificado em 27/06/2025, 38 páginas. Baixado em 18/09/2026 de
`https://arquivos-site.institutoaocp.org.br/publicacoes/a87aafe2-62c1-4e1d-a40c-6b27554ed09b.pdf`.

O conteúdo programático está no **ANEXO II – DOS CONTEÚDOS PROGRAMÁTICOS** (plural — o marcador
antigo só aceitava o singular). Antes desse anexo, a frase "conteúdos programáticos" já aparece
duas vezes em prosa (§1.6 e §11.2), como referência cruzada ("Os conteúdos programáticos […]
encontram-se no Anexo II"); o marcador tem de reconhecer o **cabeçalho** do anexo, não a primeira
menção em prosa.

**Este edital não produz nenhuma matéria com o parser atual.** As matérias vêm em Título Caso
("Língua Portuguesa:", "Noções de Direito Administrativo:", "Matemática/Raciocínio Lógico:") —
não em CAIXA ALTA como a fixture sintética assumia. O parser só reconhece cabeçalho em CAIXA
ALTA (é a heurística que existe para não confundir cabeçalho de matéria com frase comum do
edital — ver o achado da linha "Observação:" do edital da FCC abaixo). Estender essa heurística
para Título Caso fica para outra fatia, com decisão do dono (ver o relatório da tarefa em
`.superpowers/sdd/V3-questoes-cebraspe/parser-edital-real-report.md`).

A regra de correção está no §11.3: "Cada questão da Prova Objetiva terá 5 (cinco) alternativas,
sendo que cada questão terá apenas 1 (uma) alternativa correta" — múltipla escolha por extenso e
por dígito, mas **sem a frase literal "múltipla escolha"**. `extrair_fatos` não reconhece isso;
`regra_correcao.tipo_item` sai `"desconhecido"`.

## `edital-trt9-fcc-2022.pdf` — real, banca FCC
Tribunal Regional do Trabalho da 9ª Região, Edital 01/2022, banca **Fundação Carlos Chagas
(FCC)**, 34 páginas. Baixado em 18/09/2026 de
`https://www.concursosfcc.com.br/concursos/trt9r122/edital_de_abertura_trt9_.pdf`.

O marcador "CONTEÚDO PROGRAMÁTICO" aparece **4 vezes**: 3 são referência cruzada em prosa
(≈1 %, 31 % e 45 % do texto — ex.: "O Conteúdo Programático consta do Anexo III deste Edital.");
só a 4ª (≈65 %) é o cabeçalho de verdade, partido em duas linhas pelo PDF ("ANEXO III" numa
linha, "CONTEÚDO PROGRAMÁTICO" na seguinte). O marcador corrigido acha exatamente essa.

**Este edital também não produz nenhuma matéria**, por um motivo diferente do da AOCP: aqui as
24 matérias estão em CAIXA ALTA com dois-pontos ("LÍNGUA PORTUGUESA:", "DIREITO CONSTITUCIONAL:"
…) e são reconhecidas como cabeçalho — mas a FCC **não numera os itens**; são frases separadas
por ponto ("Domínio da ortografia oficial. Emprego da acentuação gráfica. […]"). Sem `1.`, `2.`,
`3.` no início do bloco, nenhuma vira matéria. Uma das 24 (CONTABILIDADE TRIBUTÁRIA) tem
numeração decimal hierárquica (`1.1.1.1.`) que colidia por acidente com o padrão `\bN\.\s` do
parser antes da correção — o parser agora exige que o item `1.` abra o próprio bloco; senão,
devolve zero itens em vez de uma lista fabricada a partir do meio do texto.

A regra de correção está no §11.2 (ou parágrafo correspondente): "questões objetivas de
**múltipla escolha** (com cinco alternativas cada questão)" — aqui a frase literal existe, e
`regra_correcao.tipo_item` sai `"multipla_escolha"` corretamente. Mas `alternativas` sai `null`
mesmo assim: "cinco" está por extenso, e a regex de alternativas só aceita dígito
(`\d+\s+alternativas`) — o mesmo problema do lado da AOCP, que lá usa "5 (cinco) alternativas"
(dígito seguido de parênteses, não direto antes de "alternativas").

## Por que isso importa para a V3b (múltipla escolha A–E)
Os dois editais reais declaram literalmente o formato de múltipla escolha com 5 alternativas —
é o formato que a próxima fatia vai gerar. Nenhum dos dois é capturado hoje como
`alternativas: 5` pelo DNA por regras; um dos dois nem chega a `tipo_item: multipla_escolha`.
Isso é retrabalho conhecido para quando a V3b entrar em `aprovaos/dominio/dna.py`
(`_ALTERNATIVAS`, `_MULTIPLA_ESCOLHA`) — não foi corrigido nesta tarefa porque o escopo dela era
o parser do conteúdo programático (`aprovaos/dominio/edital.py`), não o DNA por regras.

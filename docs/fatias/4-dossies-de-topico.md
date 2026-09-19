# Fatia 4 — Dossiês dos tópicos de maior peso do edital: plano de implementação
> O que é: o plano da fatia 4 do PRD (`docs/02-produto.md` §6, linha "Dossiês dos tópicos de
> maior peso do edital dela — `pesquisador-de-topico`") — a primeira fatia depois do piloto v0
> (V1–V5). Quando ler: antes de executar qualquer passo desta fatia e ao revisar o que foi feito;
> o diário fica em `4-execucao.md`.

**Ponto de partida:** metade desta fatia já existia, construída na fatia jurídica anterior
(V3b/V4, sem linha própria na tabela do PRD — trabalho de fundação): `dominio/dossie.py`
(`montar_dossie`, determinístico), `dados/repositorio_dossie.py`, tabela `dossie_topico`
(migração 0006), `motor/dossie.py` (só um dossiê hardcoded, improbidade), `motor/
ligar_por_topico.py`, e a fundação jurídica inteira — `dominio/legislacao.py` (extrai artigo
vigente do HTML compilado do Planalto, com procedência da redação), `motor/fontes/planalto.py`
(catálogo de normas, UA da ADR-0037), 8 normas já catalogadas.

## 1. O que esta fatia faz (e o que decide, com o porquê)

### 1.1 Generalizar: de uma função hardcoded para um comando por tópico
`motor/dossie.py` tinha `construir_dossie_improbidade()` — uma função, um tópico, pedidos de
dispositivo escritos dentro do código. Vira `construir_dossie(db, topico_slug, *, hoje=None)`,
genérica, que consulta uma **receita** (`RECEITAS: dict[str, ReceitaDossie]`) por `topico_slug`.
A receita continua **curada à mão** (não é possível, nesta fatia, rodar um agente de pesquisa de
verdade para cada tópico do edital) — o que muda é que a estrutura deixa de ser "uma função por
tópico" e passa a ser "uma linha de dado por tópico", testável e extensível sem duplicar código.
Isto é a mesma disciplina da ADR-0036 aplicada aqui: a receita é o que um humano validou que
existe (dispositivo real, lido de verdade pelo extrator, ou súmula com texto conferido) — nunca
uma lista gerada "porque o assunto costuma envolver X".

### 1.2 "De maior peso": critério medido, não declarado (decisão desta fatia)
A spec pede os tópicos "de maior peso do edital dela". O edital real da aluna-piloto continua
desconhecido (P-17); o edital no `dev.db` é o fixture fictício de Cascavel/Unioeste usado desde a
V2/V3. Mesmo nele, **peso declarado por tópico não existe** — o parser determinístico só produz
peso uniforme por matéria (lacuna registrada desde a V2, P-39: nenhum dos dois editais reais
mapeados até agora tem tabela de pontos por tópico, só por bloco/matéria). Calcular "peso" a
partir de "peso uniforme da matéria ÷ nº de tópicos dela" seria uma estimativa vestida de fato —
exatamente o que a skill `dna-do-concurso` proíbe (`pct_uniforme` é uma lacuna declarada, não um
peso real).

**Critério adotado:** peso **medido** — número de questões **publicáveis** da base real (Cebraspe,
curadoria da V3) por tópico, descendente. Sustentação: é o único número que a base tem hoje que
não é inventado; e tópicos com mais questões publicáveis são, por construção, os que a Cebraspe
mais cobrou nas provas reais que a V3 já curou (ainda que não sejam necessariamente as provas da
banca real da aluna — a mesma ressalva honesta que a V3 já registrou). Consulta nova e testável:
`motor/dossie.py::topicos_de_maior_peso(db, edital_id, limite)` — junta `topico_edital` (os
tópicos deste edital) com a contagem de `questao` publicável por `topico_id`, ordena descendente,
desempate por `slug`. Documentado aqui, não em comentário solto, porque é uma decisão de produto
(o que "peso" significa) tomada sem o dono por trás de uma pergunta em lote — se ele preferir
outro critério quando o edital real chegar, é uma troca de uma função, não uma reescrita.

### 1.3 Jurisprudência: súmula com número, texto integral e URL — sem tocar `dispositivo_legal`
A skill `deep-research-topico` pede súmulas do STF (comuns e vinculantes, com resolução de índice
antes) e do STJ (PDF único). As fixtures já medidas (`knowledge/fixtures/juridico/`,
`LEIA-ME.md`) cobrem os dois: `stf_indice_sumulas.html`/`stf_indice_sumulas_vinculantes.html` (o
índice, id interno → número), `stf_sumula_473.html`/`stf_sumula_vinculante_1.html` (páginas já
baixadas) e `stj_sumulas_verbetes.pdf` (as ~619 súmulas vigentes do STJ, todas num PDF só — não
precisa de índice, o número já está no texto).

Nesta fatia:
- `dominio/sumula.py` (novo, puro, sem I/O): `resolver_id_interno_stf` (índice → id, rejeita
  cancelada/superada), `extrair_texto_sumula_stf` (texto integral da página, funciona com os dois
  formatos medidos — `<p>` nas súmulas comuns, `<div>` nas vinculantes), `extrair_sumulas_stj`
  (todas as súmulas vigentes do PDF único, por número).
- Duas páginas novas do STF baixadas nesta fatia (mesmo UA da ADR-0037, ficha atualizada em
  `knowledge/fontes.yaml`): Súmula Vinculante 11 (uso de algemas — liga a direitos e garantias,
  art. 5º LIV/LV). As já existentes (Súmula 473, SV 1) mais a nova entram no dossiê que couber.
- `dominio/dossie.py` ganha `PedidoSumula` e o loop de resolução de súmula em `montar_dossie`
  (mesma forma do loop de norma: resolve ou vira `LacunaDossie`, nunca inventa).
- **Decisão de escopo (para não estourar a fatia):** a súmula entra no dossiê (`FonteDossie`,
  `tipo="sumula"`, com número/tribunal/texto/URL) mas **não** vira `DispositivoLegal` nesta
  rodada. A tabela `dispositivo_legal` é, pelo seu próprio contrato (docstring do modelo,
  migração 0005), "um dispositivo de **norma**" — forçar uma súmula nela (sem artigo/inciso, com
  um número de verbete no lugar) seria distorcer uma tabela que `motor.ancorar`/`motor.
  ligar_por_topico` já usam para outra coisa. `dados/repositorio_dossie.py::salvar_dossie` passa
  a chamar `buscar_ou_criar_dispositivo` só para fontes `tipo="norma"`; súmulas ficam gravadas no
  JSON de `dossie_topico.fontes` (auditável, com URL e texto), mas **não** são alcançadas por
  `motor/ligar_por_topico.py` nesta fatia — isso fica registrado como o que fica de fora, não
  escondido. Ligar súmula à questão (para a justificativa citar jurisprudência) é trabalho futuro,
  quando houver uma segunda fatia jurídica dedicada a isso.

### 1.4 Doutrina: nunca conteúdo, no máximo referência (visão §4)
`ConteudoDossie.bibliografia` já existe (`list[str]`, vazia por padrão) desde a V3b. Nesta fatia
ela continua vazia em todo dossiê gerado — nenhuma doutrina foi buscada ou citada. Não criamos
nenhum mecanismo que "preenche" bibliografia com texto de apostila/curso; se um dia a pesquisa
precisar citar doutrina, o campo já existe para guardar `"<autor> — <obra>, cap. <n>"` (referência
curta), nunca um trecho. Registrado aqui porque é a leitura literal da visão §4 ("livros,
apostilas e cursos de terceiros são referência bibliográfica, nunca conteúdo ingerido"), não
porque a fatia tenha decidido usar doutrina de fato.

## 2. Achado desta fatia: número de artigo ≥ 1.000 quebrava o extrator (bug real, corrigido)
Ao escolher receitas para os tópicos de Direito Processual Civil (o de maior peso medido — 9
questões publicáveis em "Recursos: apelação, agravo, embargos"), a norma necessária é o CPC (Lei
13.105/2015), ainda fora do catálogo. Baixado (mesmo UA/ficha do Planalto) e testado contra
`extrair_artigo`: todo artigo ≥ 1.000 falhava com `DispositivoNaoEncontrado`, porque o Planalto
grafa esses números com ponto de milhar (`"Art. 1.009."`) e o extrator comparava contra o número
cru (`"1009"`, o mesmo formato que uma citação normalizada usa). Não é uma heurística nova
inventada para adivinhar conteúdo (o que a ADR-0036 proíbe) — é uma variante mecânica de grafia do
mesmo número já pedido, medida contra o HTML real do CPC. Corrigido em `dominio/legislacao.py`
(`_com_pontuacao_de_milhar` tenta as duas grafias no caput e na detecção de fronteira do próximo
artigo), com teste red-first contra a fixture real (`tests/test_dominio_legislacao.py`, 3 testes
novos com o CPC). Sem a correção, **nenhum** artigo de 4 dígitos de **nenhuma** norma catalogada
resolveria — não só o CPC.

Achado registrado, não remendado (mesma régua): o CPC também tem títulos de Seção em Title Case
entre artigos (ex.: entre os arts. 1.025 e 1.026, "Seção I Do Recurso Ordinário") — o mesmo padrão
já documentado para a Lei 8.429/1992 e a Lei 11.340/2006 (`LEIA-ME.md`, achado 3). O art. 1.026 do
CPC fica de propósito na receita de "recursos" como lacuna declarada, não descartado da lista —
prova de que o dossiê declara em vez de esconder.

## 3. Receitas desta rodada (curadoria manual, com o porquê de cada dispositivo)

| tópico (peso medido) | normas pedidas | súmulas pedidas |
|---|---|---|
| `dir-pro-civ-05-recursos-apelacao` (9) | CPC arts. 1.009 (cabimento), 1.010 (requisitos), 1.015 (agravo de instrumento — rol), 1.022–1.024 (embargos de declaração — cabimento/prazo/julgamento), 1.026 (lacuna: Título Caso, ver §2) | STJ 98 (embargos não são protelatórios por buscar prequestionamento), STJ 347 (apelação do réu independe de prisão) |
| `dir-pro-civ-03-atos-processuais` (7) | CPC arts. 188 (forma dos atos), 218 (prazos — regra geral + urgência), 219 (só dias úteis), 224 (contagem excluindo o dia do começo), 231 (termo inicial por forma de comunicação) | STJ 216 (tempestividade é aferida pelo protocolo, não pelo correio) |
| `dir-adm-06-improbidade-administrativa` (6) | Lei 8.429/1992 — a receita já existente da V3b (arts. 1º, 1º §1º/§2º/§3º/§8º, 2º, 3º; 9º/10/11/17 como lacuna declarada, ver `motor/dossie.py` anterior), art. 23 (prescrição) | STJ 651 (demissão administrativa independe de condenação judicial), STJ 634 (particular tem o mesmo prazo prescricional do agente público) |
| `dir-con-02-direitos-garantias` (6) | CF art. 5º caput, XXXVI (ato jurídico perfeito), LIV (devido processo legal), LV (contraditório/ampla defesa), §1º (aplicação imediata), §2º (rol não exaustivo) | STF SV 1 (ato jurídico perfeito × termo de adesão FGTS), STF SV 11 (uso de algemas) |

O 5º tópico do ranking medido (`dir-adm-03-poderes-administrativos`, 5 questões) fica **sem
receita nesta rodada** — é doutrina de poderes administrativos (vinculado, discricionário,
hierárquico, disciplinar, regulamentar, de polícia) sem um artigo único e óbvio que a represente;
monta-la direito exige mais tempo de pesquisa do que esta fatia comporta sem arriscar uma
receita rasa. Fica registrado como pendência explícita (`docs/PENDENCIAS.md`), não silenciada — o
comando (`--edital-id/--top`) reporta "sem receita" para ela em vez de pular calada.

## 4. O que esta fatia não faz (e por quê)
- Não roda um agente de pesquisa real (`pesquisador-de-topico`) fazendo `WebFetch`/`curl` tópico a
  tópico — as receitas desta rodada foram curadas à mão contra fixtures já medidas. Rodar o
  subagente de verdade, com orçamento de busca e log completo por tópico, é maior que esta fatia
  cabe com qualidade (a skill pede suficiência (a)–(d) por tópico, o que é uma tarefa de pesquisa
  por si só) — fica pendência para uma fatia de pesquisa dedicada.
- Não liga súmula a `DispositivoLegal`/`Citacao` (§1.3) — só a normas.
- Não busca julgados (ADI/RE/REsp) nem "como a banca cobrou" por tópico (a skill prevê a seção,
  mas exige cruzar com a base de questões tópico a tópico — fora do orçamento desta fatia).
- Não adiciona novas normas além do CPC — as outras 4 receitas usam normas já catalogadas.

## 5. Verificação antes de fechar a fatia
1. `cd backend && uv run pytest` verde (543 → mais os testes novos desta fatia).
2. `bash scripts/checar.sh` verde na raiz.
3. Os 4 dossiês rodam de verdade contra o `edital_id` do `dev.db` (não só em teste) — contagem de
   fontes/lacunas de cada um relatada no diário e na resposta final.
4. Nenhum dossiê com afirmação sem `[F-n]`; nenhuma súmula sem número+texto+URL.
5. Linha da fatia 4 do PRD §6 atualizada.

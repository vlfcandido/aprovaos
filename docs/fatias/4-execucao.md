# Fatia 4 — Dossiês dos tópicos de maior peso do edital: diário de execução
> O que é: o que foi feito, medido, na fatia 4 — não o plano (`4-dossies-de-topico.md`).
> Quando ler: para saber o que existe de verdade hoje, com que evidência.

## Estado de partida
Branch `main`, `7f8e655` (fim do piloto v0, V1–V5). 540 testes verdes. Metade da fatia já
existia (fundação jurídica das fatias V3b/V4): `dominio/dossie.py` (`montar_dossie`,
determinístico), `dados/repositorio_dossie.py`, tabela `dossie_topico` (migração 0006),
`motor/dossie.py` (só `construir_dossie_improbidade`, hardcoded), `motor/ligar_por_topico.py`,
`dominio/legislacao.py` (extrai artigo vigente do Planalto), `motor/fontes/planalto.py` (8
normas catalogadas). Fixtures de súmula (STF índices + 2 páginas, STJ PDF único) já baixadas na
rodada de medição da V3b, mas sem código nenhum que as lesse.

## O que foi feito

### 1. Generalização (`motor/dossie.py`)
`construir_dossie_improbidade()` virou `construir_dossie(db, topico_slug, hoje=None)`, dirigida
por `RECEITAS: dict[str, ReceitaDossie]` — uma entrada por tópico, com os `PedidoDispositivo` e
`PedidoSumula` curados à mão (o porquê de cada um está comentado inline e em `4-dossies-de-topico
.md` §3). `construir_dossie_improbidade` e `SLUG_IMPROBIDADE` continuam existindo como aliases
finos, porque `motor/justificar.py` e dois arquivos de teste (`test_motor_justificar.py`,
`test_motor_ligar_por_topico.py`) ligavam neles diretamente — fora do escopo desta fatia mexer
nesses dois módulos, então o alias evita quebrar quem já existia sem justificar uma reescrita.

`construir_dossies(db, slugs)` é o laço que `main()` usa: tópico sem `RECEITAS[slug]` vira
`RelatorioDossie(sem_receita=True)` em vez de `KeyError` cru — reportado, nunca escondido.

`topicos_de_maior_peso(db, edital_id, limite)` é o critério de peso desta fatia (ADR-0039,
`4-dossies-de-topico.md` §1.2): `topico_edital` do edital, junção externa com contagem de
`questao` publicável por tópico, ordenado descendente (empate por `slug`).

### 2. Súmula (jurisprudência) — `dominio/sumula.py` + `motor/fontes/sumulas_offline.py`
Três funções puras novas em `dominio/sumula.py`, testadas contra as fixtures reais
(`tests/test_dominio_sumula.py`, 18 testes):
- `resolver_id_interno_stf(html_indice, numero, vinculante)` — resolve o id interno da URL da
  súmula a partir do índice (o número da súmula não é esse id); rejeita `(cancelada)`/
  `(superada)` com `SumulaNaoEncontrada`.
- `extrair_texto_sumula_stf(html_pagina, numero, vinculante)` — texto integral do primeiro bloco
  `.parCOM` da página (funciona com `<p>` — súmulas comuns — e `<div>` — vinculantes); confere o
  rótulo do título antes de devolver.
- `extrair_sumulas_stj(texto_pdf)` — todas as 641 súmulas vigentes do PDF único
  (`stj_sumulas_verbetes.pdf`), por número. Três formatos de citação de fechamento medidos e
  tratados: citação que repete `"SÚMULA <n>,"` (formato antigo), citação que não repete (~61
  verbetes, formato recente), e um verbete (487) cuja própria redação contém a palavra "julgado"
  fora de parênteses — resolvido casando a citação inteira por regex (`\([^()]*?julgado\s+em
  [^()]*?\)`), não por posição de string.

`motor/fontes/sumulas_offline.py::resolver_sumulas_offline(pedidos)` é a ponte de I/O (lê PDF/
HTML só quando chamado, nunca em import): STJ resolve **qualquer** número do PDF único; STF só
resolve as 3 chaves com página já baixada (`_PAGINAS_STF_OFFLINE`) — uma 4ª súmula do STF exige
baixar a página antes (mesma disciplina de `motor.fontes.planalto.CATALOGO` para normas: entra
como linha nova, decidida por quem cura a receita, não por varredura).

**Súmula nova baixada nesta fatia**: SV 11 (uso de algemas) — resolvida pelo índice
(`resolver_id_interno_stf(idx, 11, vinculante=True)` → id `1220`) e baixada com o UA híbrido da
ADR-0037 (`curl -A "Mozilla/5.0 (compatible; AprovaOS-coletor/0.1; +contato:
vlfcandido@gmail.com)"`); ficha nova em `knowledge/fontes.yaml` (`stf-sumulas`, `stj-sumulas`) —
as duas fontes não tinham ficha própria ainda, só apareciam soltas nas fixtures da V3b.

### 3. Achado: artigo ≥ 1.000 quebrava o extrator (bug real, não heurística nova)
Ao montar a receita de "Recursos: apelação" (CPC, arts. 1.009+), `extrair_artigo` falhava para
todo artigo de 4 dígitos: o Planalto grafa `"Art. 1.009."` (ponto de milhar), o extrator
comparava contra o número cru (`"1009"`). Corrigido em `dominio/legislacao.py`
(`_com_pontuacao_de_milhar` + `_NUMERO_ARTIGO_COM_MILHAR`), TDD red-first contra o HTML real do
CPC (`tests/test_dominio_legislacao.py`, 3 testes novos: extrai art. 1.009 com seus 3 parágrafos,
para no art. 1.010 sem vazar o § 3º que cita "art. 1.015" em prosa, e confirma o art. 1.010
também resolve). Sem a correção, nenhum artigo de 4 dígitos de nenhuma norma catalogada
resolveria — não só o CPC. Detalhe completo e achado irmão (Título Caso no CPC, não remendado) em
`4-dossies-de-topico.md` §2.

CPC (Lei 13.105/2015) baixado (`curl -A` com o mesmo UA identificado do Planalto — não precisa do
híbrido, o Planalto já aceitava esse UA) e catalogado em `motor/fontes/planalto.py::CATALOGO`,
`motor/ancorar.py::FIXTURES_OFFLINE`, `dominio/citacao.py::LABEL_NORMA`.

### 4. Doutrina
`ConteudoDossie.bibliografia` segue vazia em todo dossiê desta fatia — nenhuma doutrina foi
buscada nem citada (visão §4, "referência bibliográfica, nunca conteúdo ingerido"). Nada a
reportar além de confirmar que o campo não foi usado para burlar a regra.

## Testes — o que mudou
| arquivo | antes | depois |
|---|---|---|
| `tests/test_dominio_legislacao.py` | 18 | 21 (+3, milhar) |
| `tests/test_dominio_sumula.py` | — | 18 (novo) |
| `tests/test_motor_fontes_sumulas_offline.py` | — | 7 (novo) |
| `tests/test_dominio_dossie.py` | 9 | 9 (sem mudança de contagem; `FonteDossie` ganhou campos opcionais, retrocompatível) |
| `tests/test_repositorio_dossie.py` | 4 | 5 (+1, fonte de súmula não vira `dispositivo_legal`) |
| `tests/test_motor_dossie.py` | 3 | 13 (reescrito para a API genérica — 4 receitas + `topicos_de_maior_peso` + `construir_dossies`) |
| `tests/test_motor_ligar_por_topico.py` | 4 | 4 (2 assinaturas ajustadas para contar só fontes `tipo="norma"`) |

`cd backend && uv run pytest -q` → **579 passed, 6 skipped** (mesmos 6 marcadores
`postgres`/`llm`/`rede` de sempre; nenhum tocado por esta fatia). Partindo de 540: **+39**.
`bash scripts/checar.sh` (ruff check, ruff format --check, mypy --strict — 132 arquivos, prova de
import sem efeito colateral, pytest) — **OK**.

## Demonstração real contra `backend/dev.db`
Backup do `dev.db` tirado antes (`scratchpad/dev.db.bak`). Edital real no banco:
`508314e5cba34799bb609fd3a482b20a` (Cascavel/Unioeste, fixture fictício da Fase 4/V2 — a banca
real da aluna-piloto continua desconhecida, P-17).

```
$ uv run python -m aprovaos.motor.dossie --edital-id 508314e5cba34799bb609fd3a482b20a --top 5
dir-pro-civ-05-recursos-apelacao: fontes=8 lacunas=1
dir-pro-civ-03-atos-processuais: fontes=6 lacunas=0
dir-adm-06-improbidade-administrativa: fontes=10 lacunas=4
dir-con-02-direitos-garantias: fontes=8 lacunas=0
dir-adm-03-poderes-administrativos: sem receita cadastrada — nenhum dossiê montado
```

**4 dossiês nasceram de verdade** (o 5º do ranking ficou sem receita, reportado, não escondido —
decisão do plano §3):

| tópico | peso medido (questões publicáveis) | fontes | norma | súmula | lacunas |
|---|---|---|---|---|---|
| `dir-pro-civ-05-recursos-apelacao` | 9 | 8 | 6 (CPC) | 2 (STJ 98, 347) | 1 (CPC art. 1.026 — Título Caso) |
| `dir-pro-civ-03-atos-processuais` | 7 | 6 | 5 (CPC) | 1 (STJ 216) | 0 |
| `dir-adm-06-improbidade-administrativa` | 6 | 10 | 8 (Lei 8.429/1992) | 2 (STJ 651, 634) | 4 (arts. 9º/10/11/17 — Título Caso e § com sufixo) |
| `dir-con-02-direitos-garantias` | 6 | 8 | 6 (CF art. 5º) | 2 (STF SV 1, SV 11) | 0 |

`dispositivo_legal` no `dev.db` depois da rodada: **26 linhas**, todas `tipo="norma"` (7 CF, 11
CPC, 8 Lei 8.429/1992) — nenhuma súmula virou `dispositivo_legal` (decisão da ADR-0039). O
tópico de improbidade já tinha uma versão 1 (8 fontes, só norma, da fundação V3b); esta fatia
gravou a **versão 2** (10 fontes, norma + súmula) — o versionamento por tópico funcionou como
projetado, sem apagar a versão anterior.

## O que ficou de fora (declarado, não escondido)
- `dir-adm-03-poderes-administrativos` (5º do ranking, 5 questões publicáveis) sem receita —
  doutrina sem um dispositivo único óbvio; registrado em `docs/PENDENCIAS.md`.
- Súmula não vira `dispositivo_legal`/`Citacao` — não alcançada por `motor.ligar_por_topico`
  nesta fatia (ADR-0039).
- Nenhum agente de pesquisa real (`pesquisador-de-topico`) rodou; as 4 receitas foram curadas à
  mão contra fixtures já medidas.
- Julgados (ADI/RE/REsp) e "como a banca cobrou" por tópico não entraram.

## Verificação (skill `deep-research-topico`)
- Zero URL fora de `planalto.gov.br`/`portal.stf.jus.br`/`scon.stj.jus.br` em qualquer fonte
  gravada (conferido nos 4 dossiês acima).
- Toda fonte tem `trecho` literal (copiado do extrator/do PDF, nunca parafraseado) e `url`.
- Toda súmula tem número (na `citacao_canonica`) e texto integral.
- Lacunas declaram o motivo real (`EstruturaNaoTratada` com o trecho que não casou), nunca "não
  encontrado" genérico.

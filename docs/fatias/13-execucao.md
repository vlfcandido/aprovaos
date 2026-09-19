# Fatia 13 — Landing programática: diário de execução

> O que é: o que de fato aconteceu ao executar `13-landing.md` (as páginas públicas — família A,
> C, D, `sitemap.xml`, `robots.txt`), na ordem em que aconteceu. Quando ler: para saber por que o
> código ficou como ficou, ou para retomar de onde parou.

**Contexto da sessão:** outros agentes trabalhavam, em paralelo, em `dominio/{estatistica,curva,
padroes,previsao,resumo_semanal,plano,questao_inedita,validacao_questao}.py`, `motor/`,
`agentes/`, `dados/modelos.py`, `config.py`, `api/plano.py`, `web/templates/hoje/` e
`web/templates/questoes/` — nenhum desses arquivos foi tocado aqui, e `dados/modelos.py` só foi
**lido** (não editado) para entender o esquema já existente antes de escrever
`repositorio_publico.py`. `main.py` recebeu uma linha (`app.include_router(publico.router)`) via
`Edit` cirúrgico; no meio da sessão outro agente acrescentou sua própria linha (`painel.router`)
no mesmo arquivo — as duas convivem sem conflito, confirmado relendo o arquivo depois.

## 1. O corte — `dominio/pagina_publica.py`

Red-first: `tests/test_dominio_pagina_publica.py` escrito antes da implementação. Os cinco casos
que o plano pede (4 questões sem dossiê não cabe; 5 cabe; 0 com dossiê cabe; título sem banca
quando desconhecida; descrição fora da faixa levanta) mais alguns que a implementação exigiu na
prática:

- `montar_titulo_de_topico` singular/plural ("1 questão classificada" vs. "N questões
  classificadas") — sem isso o título ficaria gramaticalmente errado no caso `n=1`.
- `ajustar_descricao`: gerar a `<meta description>` de cada página à mão e acertar 120–160
  caracteres toda vez seria o "defeito silencioso" que o próprio plano avisa. Escrevi uma função
  pura que completa texto curto com um sufixo padrão e corta texto longo na última palavra
  inteira (nunca no meio de uma palavra), com teste de cada ramo — inclusive o caso defensivo
  (corte descer abaixo do mínimo por uma palavra grande perto do limite).

`PaginaPublica` (Pydantic) valida a faixa da descrição no próprio construtor — errar isso em
qualquer família de página é um `ValidationError` na hora, não um resultado de busca cortado
silenciosamente meses depois.

## 2. A consulta — `dados/repositorio_publico.py`

### 2.1 Decisão: a banca da família A vem de `Questao.banca`, nunca de `Concurso.banca`

O plano descreve o corte como "≥5 questões classificadas no tópico **ou** um dossiê publicado",
mas não diz de onde vem o `{banca}` do endereço `/o-que-cai/{banca}/{materia}/{topico}` quando a
página nasce só do dossiê (0 questões). Investigando o `dev.db` real (ver §4), os 4 tópicos com
dossiê publicado (`dir-adm-06-improbidade-administrativa` e outros três) têm **zero** questões
classificadas — pertencem ao vocabulário do edital fictício de Cascavel (fixture da Fase 4,
CLAUDE.md "aviso importante"), não ao vocabulário do TJ-PR/AOCP que a curadoria da V3b usa. A
única banca disponível para eles viria de `Concurso.banca` do concurso que subiu aquele edital —
que, neste caso, é uma fixture de teste, não um concurso real. Publicar isso como se fosse uma
banca medida seria inventar procedência (regra 2 do playbook, "nada de número inventado").

**Decisão tomada nesta fatia:** a família A só usa `Questao.banca` (a proveniência real e medida
de cada questão do pool curado) como fonte da banca do endereço. Um tópico com dossiê mas sem
nenhuma questão publicável fica de fora da geração — o corte (`cabe_em_pagina`) continua dizendo
que a página "cabe" (testado isoladamente, sem essa restrição — é uma regra pura sobre números),
mas o repositório, que é quem decide o que de fato é servível, exige a banca de verdade antes de
montar o endereço. Registrado como `docs/PENDENCIAS.md` P-62, porque não é um bug a corrigir
agora — é uma decisão de produto (como marcar/filtrar concurso de fixture) que fica para o dono.

Efeito prático: hoje, 0 páginas da família A nascem só de dossiê. Quando um dossiê existir sobre
um tópico que **também** tem questão classificada com banca real (o caso comum, previsto pelo
plano), a página nasce normalmente com as duas fontes juntas — o template já mostra dossiê e
questões na mesma página quando ambos existem (`publico/topico.html`).

### 2.2 Canonicalização (Ruling 49) só dentro da mesma banca

A primeira versão comparava cobertura entre topicos equivalentes sem olhar a banca. Corrigido
antes de rodar contra dado real: duas bancas diferentes cobrindo o mesmo assunto de direito nunca
são o mesmo conteúdo (uma pergunta "o que a FGV cobra de licitações" e "o que a Cebraspe cobra de
licitações" são páginas genuinamente distintas, não duplicadas) — canonicalizar entre bancas
apagaria conteúdo válido. A canonicalização (`_grupo_equivalente`, busca em largura sobre
`topicos_equivalentes`) agora agrupa só dentro do mesmo `banca`, e o canônico é o de maior
`n_questoes` (a única "cobertura medida" numérica disponível hoje).

### 2.3 `scalar_subquery` correlacionada quebrou contra `dev.db` real

`candidatas_familia_c` tentou, na primeira versão, achar a versão mais recente de
`dna_concurso` por `Concurso` com uma subconsulta correlacionada (`DnaConcursoRegistro.versao ==
select(func.max(...)).where(...).scalar_subquery()`). O SQLAlchemy 2.0 auto-correlaciona a
subconsulta com o `JOIN` externo (as duas tocam a mesma tabela `dna_concurso`) e a subconsulta
fica sem `FROM` (`InvalidRequestError`) — só apareceu ao rodar teste de rota de verdade, não no
mypy nem na leitura do código. Resolvido escolhendo a versão mais recente em Python (o volume de
concursos não justifica a complexidade do SQL correlacionado).

## 3. As rotas — `api/publico.py`

- Nenhuma rota usa `exigir_usuario`/`usuario_atual`; `renderizar` só recebe `usuario=None`
  (nunca o parâmetro é passado) — confirmado por teste (`test_pagina_de_topico_nao_toca_sessao_
  mesmo_logada`: faz login numa aba, bate na página pública, confere que a navegação continua
  anônima e que a resposta não tem `set-cookie`).
- `renderizar`/`Jinja2Templates` (vanilla, não Flask) **não tem** o filtro `tojson` — cogitei usar
  `| tojson` no template para o JSON-LD e não existe. Resolvido montando o JSON em Python
  (`_bloco_jsonld`, com `json.dumps` + escape de `</` para não fechar a tag `<script>` antes da
  hora) e passando a string já pronta para `{{ bloco | safe }}` — o único `| safe` desta fatia, e
  documentado no próprio módulo por que ele não reabre o defeito C3 (o `| safe` da fatia 6 era em
  texto de LLM; este é um dicionário Python determinístico, nunca texto solto).
- `web/templates/publico/_base_publico.html` **não** estende `base.html` — `base.html` carrega
  `htmx.min.js` incondicionalmente, e a regra desta fatia é "nenhum JS nas públicas, nem o htmx
  vendorizado". Layout próprio, mesmos tokens (`tokens.css`/`base.css`) + `publico.css` novo
  (mesma disciplina de "nenhuma cor literal", testado em `test_publico_estatico.py`).

## 4. Execução real contra cópia de `dev.db`

Copiado `backend/dev.db` para o scratchpad da sessão (nunca o original) e rodado
`candidatas_familia_a/c/d` direto contra ele:

```
Família A: 12 páginas (todas banca "cebraspe")
  noc-dir-adm-02-2-poderes         n=5
  noc-dir-adm-06-6-improbidade     n=6
  noc-dir-adm-08-8-licitacoes      n=5
  noc-dir-adm-09-9-agentes         n=6
  noc-dir-con-03-3-principios      n=5
  noc-dir-con-04-4-direitos        n=8
  noc-dir-con-05-5-organizacao     n=5
  noc-dir-con-06-6-organizacao     n=8
  noc-dir-pen-03-crime             n=5
  noc-dir-pro-civ-06-procedimento-comum  n=5
  noc-dir-pro-civ-07-recursos      n=10
  noc-dir-pro-pen-06-provas-6      n=7

Família C: 2 páginas
  /duvidas/desconto-por-erro-fundacao-de-apoio-a-unioeste  (fixture — ver §2.1/P-62)
  /duvidas/desconto-por-erro-instituto-aocp  (real; anula_por_erro = desconhecido, resposta
    honesta "ainda não medimos")

Família D: 1 página
  /verticalizado/camara-municipal-de-cascavel-estado-do-parana-2026  (100 % fixture — o único
    concurso com data_prova conhecida é o de Cascavel; o TJ-PR real não tem data_prova no DNA)

Equivalências que viraram canônica: 0
```

**12 páginas de família A é o número pequeno que o brief pediu para não maquiar.** Dos 38 tópicos
com pelo menos 1 questão publicável (137 questões), só 12 chegam a 5+; os outros 26 ficam abaixo
do corte e não geram página — exatamente o comportamento que separa conteúdo programático de
spam programático (playbook §3.4).

**0 canonicalizações não é um bug do mecanismo — é consequência de §2.1.** As 3 relações
`equivalencia_curada` do banco ligam um tópico do vocabulário fictício de Cascavel (sem questão,
logo sem página, por §2.1) a um tópico real do TJ-PR (com página própria). Como só um lado de
cada par chega a existir como página, não há disputa de canônica para resolver hoje. O código
(`_grupo_equivalente` + escolha por maior `n_questoes`) está testado isoladamente com um par
sintético onde os dois lados passam do corte (`test_equivalencia_curada_gera_canonica`), então
está pronto para o dia em que dois lados reais coexistirem.

**Famílias C e D publicariam a fixture como fato hoje** — registrado como `docs/PENDENCIAS.md`
P-62, não corrigido nesta fatia (não é um bug de código; é decisão de produto sobre como marcar
concurso de teste, e "não invente uma heurística de nome de órgão" evita um hack frágil).

## 5. Testes e checagem

32 testes novos: 16 em `test_dominio_pagina_publica.py`, 14 em `test_rota_publico.py`, 2 em
`test_publico_estatico.py`. `ruff check`/`ruff format --check`/`mypy` verdes nos arquivos desta
fatia; `scripts/checar_import.py` passa (nenhum efeito colateral em import). Não rodei
`scripts/checar.sh` completo porque outros agentes tinham arquivos em estado transitório na
mesma branch (esperado, avisado no brief) — rodei a suíte restrita aos meus arquivos mais
`test_inicio.py`/`test_roteador.py`/`test_import_sem_efeito_colateral.py` como checagem cruzada
de que `main.py` continua íntegro.

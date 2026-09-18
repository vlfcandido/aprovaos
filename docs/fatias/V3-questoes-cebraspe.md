# Fatia V3 — Questões originais da Cebraspe por tópico do edital: plano de implementação
> O que é: o plano passo a passo da V3 — coletor da Cebraspe, curador de prova, questão original servida com origem e as telas de resolver e reportar. Quando ler: antes de executar qualquer passo da V3 e ao revisar o que foi feito; o diário da execução fica em `V3-execucao.md`.

**Spec desta fatia:** linha V3 da tabela do PRD `docs/02-produto.md` §6; contratos em `.claude/skills/monitor-de-fontes/SKILL.md` e `.claude/skills/ingestao-de-provas/SKILL.md`; dados em `docs/04-modelo-de-dados.md` §2–§4; decisões da abertura em ADR-0027, ADR-0028 e ADR-0030.

## 1. Objetivo
A Linda abre um tópico do edital dela e resolve **questões de verdade da Cebraspe** daquele tópico, vê o gabarito com a **origem completa** (órgão, cargo, ano, número do item, caderno, link do PDF), declara **certeza ou dúvida** antes de responder e pode **reportar erro**. Nada de questão inédita, nada de FSRS — só o conteúdo original chegando à tela com procedência.

O caminho inteiro fica de pé: API da Cebraspe → PDF de prova e gabarito guardados com hash → segmentação determinística dos itens → classificação no vocabulário de tópicos do edital dela → `questao` publicada sob regra explícita → tela.

## 2. Premissas (decisões deste plano; qualquer uma pode ser vetada pelo dono)
| id | premissa | por quê |
|---|---|---|
| A | **Pipeline offline por comando**, não pela web: `uv run python -m aprovaos.motor.coletar` e `uv run python -m aprovaos.motor.curar` rodam na máquina do dono e gravam no banco; a app só lê e serve. | Nenhuma chamada de LLM no request, custo previsível, tudo reproduzível. Job em background é a fatia 8. |
| B | **Identidade do item da fonte = `{eventoURL}/{nomeArquivo}`.** `idEvento` vem `0` nos 424 concursos encerrados (medido em 18/09/2026) e não serve; `eventoURL` tem 423 valores distintos em 424 (um duplicado) e `nomeArquivo` é único dentro do evento. | Regra da skill `monitor-de-fontes`: identidade é do item, nunca hash de título nem posição na lista. |
| C | **Provas e gabaritos vêm de `arquivosGabarito`** do endpoint de detalhe, separados pelo prefixo de `descricaoArquivo`: `PROVA OBJETIVA` → `prova`, `GABARITO DEFINITIVO` → `gabarito`, `PROVA DISCURSIVA`/`PADRÃO DEFINITIVO DE RESPOSTA` → ignorados nesta fatia, qualquer outro → `desconhecido` (não baixado). | Medido nos dois concursos-piloto: TJ_PA_25_SERVIDOR (26 provas + 26 gabaritos) e STJ_24 (23 + 24). A API não tem campo de tipo. |
| D | **Recorte da coleta:** 3 a 5 concursos encerrados 2023–2025 com cargo de nível superior em Direito, só os arquivos de **conhecimentos específicos do cargo de Direito** e o gabarito definitivo correspondente. Candidatos: `TJ_PA_25_SERVIDOR` (CARGO 9 — ANALISTA JUDICIÁRIO, ESPECIALIDADE: DIREITO), `STJ_24` (CARGO 9), `TJ_CE_23_SERVIDOR`, `MP_GO_24_SERVIDOR`, `TRT10_24`. A lista final é conferida e mostrada ao dono no passo 5 antes de baixar. | O edital da Linda tem 22 tópicos de Direito (Constitucional, Administrativo, Civil, Processual Civil) em 36. Cargos de procurador/promotor cobram outro nível e outras matérias. |
| E | **PDFs commitados** em `knowledge/provas/<eventoURL>/<nomeArquivo>` (decisão do dono, 18/09/2026). Medido: 33 KB a 208 KB por arquivo; 5 concursos × (caderno + gabarito) ≈ 2 MB. | Reprodutibilidade dos testes de segmentação sem rede. Se o total passar de 20 MB, o passo 5 para e pergunta. |
| F | **Gate de publicação da questão original** (vira ADR-0033): `publicada = True` exige gabarito **definitivo**, `origem` com os 8 campos, `topico_slug` no vocabulário do edital e `topico_confianca ≠ baixa`. Item anulado, alterado sem definitivo ou sem entrada no gabarito fica na base com `publicavel = False` e motivo. O validador da fatia 5 continua obrigatório para **inéditas**. | Regra 11 do CLAUDE.md fala do que é *gerado*; questão original não é gerada — o que ela precisa é procedência, e é isso que o gate exige. |
| G | **Classificação em lote de 20 enunciados por chamada**, com a mesma arquitetura da V2: `ClassificadorAdk` (Gemini em JSON mode) quando há `GOOGLE_API_KEY` e teto diário, senão `ClassificadorPorRegras`, com motivo visível. Um caderno de 120 itens = 6 chamadas. | Uma chamada por item seria ~600 chamadas para 5 concursos e estouraria o teto de R$ 3/dia (ADR-0018) já no primeiro. |
| H | **Reporte esconde a questão só para quem reportou** (decisão do dono): grava `reporte_erro(status="aberto")` + `evento_estudo(tipo="reporte")` e a questão sai da fila daquele usuário. Despublicar para todos é do calibrador (fatia 8). | Piloto n=1 não pode dar poder de veto global a um clique. |
| I | **Um tópico por questão**, o do comando, como manda a skill. Item que não casa nenhum tópico do edital dela fica `topico_id = NULL`, `publicavel = False`, motivo `"sem correspondência no vocabulário"`. | Contrato da `ingestao-de-provas`. A base guarda tudo; a tela só serve o que casou. |
| J | **Só Cebraspe C/E nesta fatia.** O segmentador A–E da Cebraspe (cargos de nível médio) e a FGV ficam fora. | Os cargos de Direito escolhidos são todos C/E; a FGV está vetada por termos de uso (P-13). |
| K | **Testes que tocam a rede ficam atrás do marker `rede`**, pulados sem `APROVAOS_TESTES_DE_REDE=1`, como o marker `llm` da V2. A suíte inteira roda offline contra fixtures. | `scripts/checar.sh` é o CI e não pode depender da Cebraspe estar de pé. |
| L | **`knowledge/fontes.yaml` é a ficha oficial** e um teste confere que toda URL usada no código está na ficha. `pyyaml` entra só nas dependências de desenvolvimento (o runtime não lê YAML). | Verificação da skill `monitor-de-fontes` ("nenhuma URL no código que não esteja na ficha") sem engordar o runtime. |
| M | **`evento_estudo` nasce nesta fatia** com os tipos que a V3 usa (`resposta`, `reporte`); os outros entram nas fatias que os criarem. `append-only`: a camada de dados não expõe update nem delete. | Modelo de dados §2. |
| N | **Status do verticalizado = tópico com ≥ 1 resposta.** O "0 de 36" da V2 passa a contar de verdade. | Fecha metade da pendência "status do verticalizado por eventos" que a V2 registrou. |

## 3. Fora da V3 (rastreado; não implementar)
- Questões inéditas, `gerador-questao-banca` e validador → fatia 5.
- FSRS, cartões e fio da memória → V5.
- Calibrador, despublicação automática, fila humana de reportes → fatia 8 (skill `calibracao-de-questoes`).
- FGV → bloqueado por P-13 (termos de uso vedam automação).
- Radar/catálogo de concursos, embeddings (`questao.embedding`), busca semântica → fatia 1b e seguintes.
- Aulas, dossiês, citações → fatias 4 e 6.
- Segmentação A–E (Cebraspe nível médio) → quando um edital pedir.

## 4. Estrutura final de arquivos (o que a V3 acrescenta ou toca)
```
backend/aprovaos/motor/__init__.py                  # novo — pacote do Motor (vazio, sem efeito em import)
backend/aprovaos/motor/fontes/__init__.py           # novo
backend/aprovaos/motor/fontes/base.py               # novo — FonteColetavel, Novidade, ArquivoBaixado, erros
backend/aprovaos/motor/fontes/cebraspe.py           # novo — FonteCebraspe + criar_fonte_cebraspe
backend/aprovaos/motor/curadoria/__init__.py        # novo
backend/aprovaos/motor/curadoria/classificacao.py   # novo — porta + regras + ADK em lote
backend/aprovaos/motor/curadoria/curador.py         # novo — curar() e verificar_curadoria()
backend/aprovaos/motor/coletar.py                   # novo — `python -m aprovaos.motor.coletar`
backend/aprovaos/motor/curar.py                     # novo — `python -m aprovaos.motor.curar`
backend/aprovaos/dominio/prova.py                   # novo — segmentação Cebraspe C/E
backend/aprovaos/dominio/gabarito.py                # novo — leitura do gabarito definitivo
backend/aprovaos/dominio/questao.py                 # novo — QuestaoCurada, Origem, gate de publicação
backend/aprovaos/agentes/classificador.py           # novo — agente `curador` (porta ADK do classificador)
backend/aprovaos/agentes/prompts/classificador.md   # novo — prompt do classificador
backend/aprovaos/dados/modelos.py                   # toca — fonte, questao, alternativa, evento_estudo, reporte_erro
backend/aprovaos/dados/repositorio_questao.py       # novo — gravar, listar, responder, reportar
backend/aprovaos/api/questoes.py                    # novo — /topico/{slug}/questoes e POST de resposta/reporte
backend/aprovaos/api/editais.py                     # toca — contagem por tópico e "X de N vistos"
backend/aprovaos/main.py                            # toca — registra o router de questões
backend/alembic/versions/0003_*.py                  # novo — migração da V3
backend/tests/…                                     # novos testes (lista em cada passo)
web/templates/questoes/resolver.html                # novo
web/templates/questoes/_resultado.html              # novo — fragmento HTMX
web/templates/editais/concurso.html                 # toca — link e contagem por tópico
knowledge/fontes.yaml                               # novo — ficha da fonte Cebraspe
knowledge/fixtures/fontes/cebraspe/                 # novo — snapshots reais v1/v2 + LEIA-ME.md
knowledge/provas/<eventoURL>/*.pdf                  # novo — cadernos e gabaritos baixados
scripts/snapshot_cebraspe.py                        # novo — grava os snapshots da API (marker rede)
docs/fatias/V3-execucao.md                          # novo — diário
```

## 5. Convenções transversais (as da V1 §5 e V2 §5 valem integralmente; acréscimos)
- **Nada de I/O em import** também no `motor/`: o cliente HTTP, o caminho de disco e a chave entram por parâmetro de fábrica (`criar_fonte_cebraspe(config, cliente)`), nunca em nível de módulo.
- **Nenhuma URL literal fora de `knowledge/fontes.yaml`** — as constantes do módulo repetem o que está na ficha e o teste `test_urls_do_codigo_estao_na_ficha` confere.
- **User-Agent identificado** em toda requisição: `AprovaOS-coletor/0.1 (+contato: <config.contato_coletor>)` (ADR-0030: o contato é o e-mail do dono).
- **Toda função pública com docstring Google** e tipagem completa (`mypy --strict` roda sobre `aprovaos`, `tests` e `scripts`).
- Texto de questão guardado **como a banca imprimiu**; normalização (espaços, hífen de quebra de linha) só no `hash_dedup`, nunca no que vai para a tela.

## 6. Passos

### Passo 1 — Dependências, configuração e marker `rede`
**Arquivos:** `backend/pyproject.toml`, `backend/aprovaos/config.py`, `backend/tests/conftest.py`, `.env.example`, `backend/tests/test_config.py`, `backend/tests/test_env_example.py`.

- [ ] **RED** — `test_config.py::test_campos_da_v3`: `Configuracoes(…, _env_file=None)` tem `documentos_dir is None` por padrão, `contato_coletor == "vlfcandido@gmail.com"`, `modelo_classificacao == "gemini-2.5-flash"` e `lote_classificacao == 20`; com `lote_classificacao=0` levanta `ValidationError` (`gt=0`). `test_env_example.py::test_env_example_cobre_todas_as_configuracoes` (já existe) passa a exigir as chaves novas.
- [ ] **GREEN** — em `Configuracoes`: `documentos_dir: Path | None = None` (default resolvido pela app para `knowledge/provas`), `contato_coletor: str = "vlfcandido@gmail.com"`, `modelo_classificacao: str = "gemini-2.5-flash"`, `lote_classificacao: int = Field(default=20, gt=0)`. Acrescentar as quatro chaves comentadas em `.env.example`.
- [ ] **GREEN** — `pyproject.toml`: mover `httpx2>=2.13.0` do grupo `dev` para `dependencies` (é o cliente do coletor; API compatível com httpx, `Client(headers=…, timeout=…, follow_redirects=True)`); acrescentar `pyyaml` e `types-pyyaml` ao grupo `dev`; registrar o marker `rede: exige APROVAOS_TESTES_DE_REDE=1 (baixa da Cebraspe de verdade)`.
- [ ] **GREEN** — `conftest.py`: acrescentar `"rede": ("APROVAOS_TESTES_DE_REDE", "defina APROVAOS_TESTES_DE_REDE=1")` ao dicionário `marcadores` de `pytest_collection_modifyitems`.
- [ ] **Verde** — `cd backend && uv sync && uv run pytest tests/test_config.py tests/test_env_example.py -v`.
- [ ] **Commit** — `chore(v3): configuração do coletor, cliente HTTP e marker de rede`.

### Passo 2 — Ficha da fonte e snapshots reais da API
**Arquivos:** `knowledge/fontes.yaml`, `knowledge/fixtures/fontes/cebraspe/{lista-encerrado-v1.json,lista-encerrado-v2.json,detalhe-TJ_PA_25_SERVIDOR.json,LEIA-ME.md}`, `scripts/snapshot_cebraspe.py`, `backend/tests/test_fonte_cebraspe_ficha.py`.

- [ ] **Coleta real** — `uv run python scripts/snapshot_cebraspe.py` grava os três JSON acima direto da API (`rede`). `LEIA-ME.md` explica: `v1` = resposta real de `<data>`; `v2` = cópia de `v1` com **um evento a mais**, inserido à mão (`eventoURL: "TESTE_V3_99"`), para o teste 3 da skill.
- [ ] **Ficha** — `knowledge/fontes.yaml` com a entrada `cebraspe` no formato da skill `monitor-de-fontes`: `url_lista: https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/fase/encerrado`, `url_detalhe: https://apis.cebraspe.org.br/cebraspe/eventos/{eventoURL}`, `url_arquivo: https://cdn.cebraspe.org.br/concursos/{eventoURL}/arquivos/{nomeArquivo}`, `formato: api_json`, `o_que_publica: [edital, prova, gabarito]`, `identidade_do_item: "{eventoURL}/{nomeArquivo}"`, `robots_txt: permite (lido em 14/09/2026, P-11)`, `termos_de_uso: não localizados (P-11)`, `politica_coleta: {frequencia: 24h, user_agent: "AprovaOS-coletor/0.1 (+contato: vlfcandido@gmail.com)", sem_login: true, cache: nenhum}`, `verificado_em: <data da execução>`, `evidencia: knowledge/fixtures/fontes/cebraspe/lista-encerrado-v1.json`, `status: ativa`.
- [ ] **RED** — `test_fonte_cebraspe_ficha.py::test_ficha_completa`: carrega o YAML e exige todos os campos da skill preenchidos, `status == "ativa"` e `evidencia` apontando para arquivo existente e não vazio.
- [ ] **GREEN** — escrever a ficha até o teste passar. O `test_urls_do_codigo_estao_na_ficha` **não** entra aqui: ele depende das constantes do módulo e nasce no passo 4.
- [ ] **Commit** — `feat(v3): ficha da fonte Cebraspe e snapshots reais da API`.

### Passo 3 — Contrato `FonteColetavel`
**Arquivos:** `backend/aprovaos/motor/__init__.py`, `motor/fontes/__init__.py`, `motor/fontes/base.py`, `backend/tests/test_fontes_base.py`.

- [ ] **RED** — `test_fontes_base.py::test_novidade_exige_campos`: `Novidade(id="X/Y.pdf", tipo="prova", titulo="PROVA OBJETIVA – …", url="https://…", evento="X", publicado_em=datetime(2025,10,1,11,30, tzinfo=UTC))` valida; `tipo="qualquer"` levanta `ValidationError` (Literal `prova|gabarito|edital|desconhecido`). `::test_arquivo_baixado_calcula_hash`: `ArquivoBaixado.de_conteudo(novidade, b"%PDF-1.4…")` tem `hash` = `hashlib.sha256` do conteúdo e `tamanho` em bytes. `::test_erros_sao_tipados`: `FonteVetada` e `FonteIndisponivel` herdam de `RuntimeError`.
- [ ] **GREEN** — `base.py` com os modelos Pydantic `Novidade` e `ArquivoBaixado`, o `Protocol` `FonteColetavel` (`listar_novidades(vistos: set[str]) -> list[Novidade]`, `baixar(novidade: Novidade) -> ArquivoBaixado`) e os dois erros. Docstrings completas; nenhum import de rede no módulo.
- [ ] **Verde** — `uv run pytest tests/test_fontes_base.py -v`.
- [ ] **Commit** — `feat(v3): contrato FonteColetavel`.

### Passo 4 — `FonteCebraspe` e os cinco testes de novidade da skill
**Arquivos:** `backend/aprovaos/motor/fontes/cebraspe.py`, `backend/tests/test_fonte_cebraspe.py`, `backend/tests/test_fonte_cebraspe_ficha.py` (completa).

- [ ] **RED** — `test_fonte_cebraspe.py`, todos contra os snapshots do passo 2 com um cliente falso (`ClienteFalso` que devolve o JSON do arquivo e nunca toca a rede):
  1. `test_lista_vazia_devolve_todos`: `listar_novidades(vistos=set())` sobre `lista-encerrado-v1.json` devolve exatamente **423** novidades de `tipo="desconhecido"` (o nº de `eventoURL` distintos — a listagem não traz arquivos) com `id == eventoURL`.
  2. `test_tudo_visto_devolve_vazio`: `listar_novidades(vistos=ids(v1))` → `[]`.
  3. `test_um_item_novo`: `listar_novidades(vistos=ids(v1))` sobre `v2` → **exatamente 1** novidade, `id == "TESTE_V3_99"`.
  4. `test_arquivos_do_evento_classifica_por_descricao`: `arquivos_do_evento("TJ_PA_25_SERVIDOR")` sobre `detalhe-TJ_PA_25_SERVIDOR.json` devolve 54 novidades; 26 com `tipo="prova"`, 26 com `tipo="gabarito"`, 2 ignoradas (`PROVA DISCURSIVA`, `PADRÃO DEFINITIVO DE RESPOSTA`) e nenhuma com `id` repetido; a novidade de `descricaoArquivo == "PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS – CARGO 9"` tem `url == "https://cdn.cebraspe.org.br/concursos/TJ_PA_25_SERVIDOR/arquivos/C15F414E0E91EF109220A73BDF53B232C4466F64770A91E715C56DCB94131F41.pdf"` e `publicado_em == datetime(2025, 9, 5, 22, 0, tzinfo=UTC)` — `dataArquivoObj` vem `"2025-09-05T19:00:00"` **sem fuso** e é lido como horário de Brasília (`ZoneInfo("America/Sao_Paulo")`) convertido para UTC.
  5. `test_erro_http_levanta`: cliente que devolve 503 → `FonteIndisponivel`, **não** `[]`.
  6. `test_baixar_devolve_conteudo_e_hash`: cliente falso devolve `b"%PDF-1.4 x"` → `ArquivoBaixado.hash == sha256(b"%PDF-1.4 x").hexdigest()`.
  7. `test_user_agent_identificado`: o cliente falso registra os headers recebidos; contém `User-Agent` com `AprovaOS-coletor/0.1` e o e-mail de `config.contato_coletor`.
  8. `test_rede` (marker `rede`): `criar_fonte_cebraspe(config)` de verdade → `listar_novidades(set())` devolve ≥ 400 novidades e `arquivos_do_evento("TJ_PA_25_SERVIDOR")` contém a descrição do CARGO 9.
- [ ] **GREEN** — `cebraspe.py`: constantes `URL_LISTA`, `URL_DETALHE`, `URL_ARQUIVO`; classe `FonteCebraspe` recebendo `cliente` e `contato` no construtor (sem I/O no import); `listar_novidades`, `arquivos_do_evento`, `baixar`; `criar_fonte_cebraspe(config)` monta o `httpx2.Client` com header identificado, `timeout=30` e `follow_redirects=True`. A duplicidade de `eventoURL` medida na API (423/424) é resolvida por `dict` de id.
- [ ] **GREEN** — fechar `test_urls_do_codigo_estao_na_ficha` (passo 2).
- [ ] **Verde** — `uv run pytest tests/test_fonte_cebraspe.py tests/test_fonte_cebraspe_ficha.py -v` (offline) e, uma vez, com `APROVAOS_TESTES_DE_REDE=1`.
- [ ] **Commit** — `feat(v3): coletor da Cebraspe com detecção de novidade por identidade de item`.

### Passo 5 — Escolha dos concursos e coleta real dos PDFs
**Arquivos:** `backend/aprovaos/motor/coletar.py`, `backend/tests/test_motor_coletar.py`, `knowledge/provas/**`.

- [ ] **RED** — `test_motor_coletar.py::test_seleciona_cargo_de_direito`: `arquivos_do_cargo(novidades, cargo_numero=9)` devolve só os dois arquivos cujo `descricaoArquivo` termina em `CARGO 9` (um `prova`, um `gabarito`), e nenhum de `CARGOS 1, 2, 6, 8, 9, 18 E 22` (conhecimentos gerais não entram na V3). `::test_pareia_prova_e_gabarito`: `parear(arquivos)` devolve `[ParDeProva(prova=…, gabarito=…)]` e levanta `ProvaSemGabarito` quando falta um dos dois. `::test_grava_documento_e_arquivo`: com fonte falsa, `coletar_par(db, config, par)` cria dois `Documento` (`tipo="prova"` e `"gabarito"`, `hash` do conteúdo, `caminho` relativo `TJ_PA_25_SERVIDOR/<nomeArquivo>`, `metadados` com `descricao`, `evento`, `url_origem`) e escreve os dois arquivos em `config.documentos_dir`; rodar duas vezes não duplica (`hash` já existente → devolve o `Documento` existente).
- [ ] **GREEN** — `coletar.py` com `arquivos_do_cargo`, `parear`, `coletar_par`, `main()` por `argparse` (`--evento`, `--cargo`, `--listar`) e `if __name__ == "__main__": main()` — nenhuma execução em import.
- [ ] **Coleta real e conferência com o dono** — rodar `--listar` nos cinco candidatos, montar a tabela (evento, cargo, matérias do caderno, nº de itens do gabarito, tamanho dos PDFs) e **mostrar ao dono antes de baixar**. Só então rodar a coleta e commitar os PDFs. Se o total passar de 20 MB, parar e perguntar.
- [ ] **Verde** — `uv run pytest tests/test_motor_coletar.py -v`.
- [ ] **Commit** — `feat(v3): comando de coleta + provas e gabaritos de <N> concursos da Cebraspe`.

### Passo 6 — Segmentação Cebraspe C/E
**Arquivos:** `backend/aprovaos/dominio/prova.py`, `backend/tests/test_dominio_prova.py`.

- [ ] **RED** — testes contra o texto extraído do caderno real (via `extrair_texto` de `dominio/pdf.py`, o mesmo da V2) e sintéticos:
  - `test_segmenta_caderno_real`: `segmentar_cebraspe(texto)` devolve N itens, com N = nº de entradas do gabarito definitivo do mesmo cargo (número conferido no passo 5 e escrito literalmente no teste); `numero_item` é estritamente crescente e sem buracos.
  - `test_comando_vale_ate_o_proximo`: sintético com `"Com base na Lei nº 14.133/2021, julgue os itens subsequentes."` seguido de três itens e depois outro comando → os três primeiros têm o primeiro comando, o quarto tem o segundo.
  - `test_texto_de_apoio_por_intervalo`: sintético com `"Texto para os itens 58 e 59"` → itens 58 e 59 com `texto_apoio` preenchido e `texto_apoio_itens == [58, 59]`; o item 60 com `texto_apoio is None`.
  - `test_item_em_varias_linhas`: enunciado quebrado em três linhas vira um `enunciado` só, com espaço simples e sem hífen de quebra.
  - `test_ignora_cabecalho_e_rodape`: linhas de cabeçalho do caderno (`"CEBRASPE | TJ/PA – Aplicação: 2025"`) e números de página não viram item.
- [ ] **GREEN** — `prova.py` com `ItemBruto` (Pydantic: `numero_item`, `comando`, `texto_apoio`, `texto_apoio_itens`, `enunciado`) e `segmentar_cebraspe(texto: str) -> list[ItemBruto]`. Determinístico, sem IA, sem rede.
- [ ] **Verde** — `uv run pytest tests/test_dominio_prova.py -v`.
- [ ] **Commit** — `feat(v3): segmentação determinística de caderno Cebraspe C/E`.

### Passo 7 — Gabarito definitivo
**Arquivos:** `backend/aprovaos/dominio/gabarito.py`, `backend/tests/test_dominio_gabarito.py`.

- [ ] **RED** — `test_le_gabarito_real`: `ler_gabarito_cebraspe(texto)` sobre o PDF real devolve um `dict[int, EntradaGabarito]` com N entradas (o mesmo N do passo 6); toda entrada tem `valor in {"C", "E", None}`. `test_anulado`: linha com `"ANULADO"` (ou `"–"`) → `EntradaGabarito(valor=None, status="anulado")`. `test_alterado`: quando o texto traz gabarito preliminar e definitivo diferentes para o mesmo item → `status="alterado"` e `valor_preliminar` preenchido. `test_item_fora_do_gabarito`: consultar item inexistente devolve `None` (a decisão do que fazer é do curador).
- [ ] **GREEN** — `gabarito.py` com `EntradaGabarito` e `ler_gabarito_cebraspe`.
- [ ] **Verde** — `uv run pytest tests/test_dominio_gabarito.py -v`.
- [ ] **Commit** — `feat(v3): leitura do gabarito definitivo da Cebraspe`.

### Passo 8 — Classificação de tópico (regras + IA em lote)
**Arquivos:** `backend/aprovaos/motor/curadoria/classificacao.py`, `backend/aprovaos/agentes/classificador.py`, `backend/aprovaos/agentes/prompts/classificador.md`, `backend/tests/test_classificacao.py`, `backend/tests/test_classificador_llm.py`.

- [ ] **RED** — `test_classificacao.py`:
  - `test_regras_casam_por_lei_citada`: enunciado citando `"Lei nº 14.133/2021"` com o vocabulário do edital da Linda → `slug == "dir-adm-04-licitacoes-contratos"`, `confianca == "alta"`, `evidencia` contendo `"14.133"`.
  - `test_regras_casam_por_termo`: enunciado com `"impessoalidade"` → tópico de princípios da Administração, `confianca == "media"`.
  - `test_regras_sem_correspondencia`: enunciado de Informática → `slug is None`, `confianca == "baixa"`, `evidencia == "sem correspondência no vocabulário"`.
  - `test_lote_respeita_tamanho`: `montar_lotes(itens=45, tamanho=20)` → `[20, 20, 5]`.
  - `test_interpretar_resposta_do_lote`: JSON `[{"numero_item": 58, "topico_slug": "dir-adm-04-licitacoes-contratos", "confianca": "alta", "evidencia": "…"}]` vira a lista tipada; slug fora do vocabulário → `ClassificacaoInvalida`; item que o modelo não devolveu → cai para regras com motivo `"item ausente na resposta do modelo"`.
  - `test_fallback_por_erro_da_ia`: classificador de IA que levanta → resultado por regras com `origem == "regras"` e `motivo_fallback == "erro na IA: RuntimeError"`.
  - `test_sem_chave_vai_para_regras`: `escolher_classificador(config sem chave, …)` → `(None, "sem GOOGLE_API_KEY")`.
- [ ] **RED** — `test_classificador_llm.py` (marker `llm`, não roda no CI): um lote de 5 itens reais → todo slug devolvido está no vocabulário; imprime tokens e custo para o diário (P-27 vale o mesmo aqui).
- [ ] **GREEN** — `classificacao.py`: `Classificacao` (Pydantic), porta `ClassificadorDeTopico`, `ClassificadorPorRegras` (léxico montado do `texto_original` de cada tópico + números de lei), `montar_lotes`, `interpretar_resposta` e `classificar(itens, vocabulario, classificador_ia, motivo_sem_ia) -> ResultadoClassificacao` no mesmo desenho de `gerar_dna` (nunca bloqueia, sempre registra o motivo).
- [ ] **GREEN** — `agentes/classificador.py`: `ClassificadorAdk` + `criar_classificador_adk(config, registrar_chamada)` — `LlmAgent` com `response_mime_type="application/json"` e `temperature=0.0`, `include_contents="none"`, prompt em `prompts/classificador.md` (recebe a lista `slug | materia | texto_original` e os enunciados do lote; manda responder só o JSON, um objeto por item, sem inventar slug).
- [ ] **Verde** — `uv run pytest tests/test_classificacao.py -v`.
- [ ] **Commit** — `feat(v3): classificação de tópico por regras com IA em lote e fallback`.

### Passo 9 — Curador: contrato, verificação e gate de publicação
**Arquivos:** `backend/aprovaos/dominio/questao.py`, `backend/aprovaos/motor/curadoria/curador.py`, `backend/tests/test_curador.py`.

- [ ] **RED** — `test_curador.py`:
  - `test_saida_no_contrato_da_skill`: `curar(...)` sobre o caderno real devolve N `QuestaoCurada` com **todos** os campos do contrato (`adapter`, `banca`, `tipo_item`, `numero_item`, `comando`, `texto_apoio`, `texto_apoio_itens`, `enunciado`, `alternativas`, `gabarito_preliminar`, `gabarito`, `gabarito_status`, `publicavel`, `publicado`, `motivo_nao_publicavel`, `regra_prova`, `topico_slug`, `topico_confianca`, `topico_evidencia`, `origem`, `hash_dedup`, `justificativa_certo`, `justificativa_errado`); `justificativa_*` todas `None`; `publicado` `False` em todas.
  - `test_origem_com_oito_campos`: `origem` traz `banca`, `orgao`, `cargo`, `ano`, `numero_item`, `tipo_caderno`, `url_prova`, `documento_id` — `url_prova` e `documento_id` iguais aos do `Documento` gravado no passo 5, nunca remontados.
  - `test_anulado_nao_publicavel`: item anulado → `gabarito is None`, `gabarito_status == "anulado"`, `publicavel is False`, `motivo_nao_publicavel` começa com `"anulado"`.
  - `test_sem_gabarito_nao_publicavel`: item sem entrada → `publicavel is False`, motivo `"sem gabarito"`.
  - `test_confianca_baixa_nao_publicavel`: `topico_confianca == "baixa"` → `publicavel is False`, motivo `"tópico não identificado"` (premissa F).
  - `test_contagem_divergente_para_tudo`: gabarito com N−1 entradas → `ResultadoCuradoria.pendente_revisao is True`, `questoes == []` e `problemas` contendo `"itens (N) ≠ gabarito (N−1)"`.
  - `test_hash_dedup_normaliza`: dois enunciados iguais a menos de espaços e quebra de linha → mesmo `hash_dedup`.
  - `test_verificar_curadoria`: as 5 verificações da skill; cada violação devolve mensagem própria.
- [ ] **GREEN** — `questao.py` com `Origem`, `QuestaoCurada`, `decidir_publicacao(...) -> tuple[bool, str | None]` (o gate da premissa F) e `hash_dedup(enunciado)`. `curador.py` com `curar(...)` e `verificar_curadoria(...)`.
- [ ] **Verde** — `uv run pytest tests/test_curador.py -v`.
- [ ] **Commit** — `feat(v3): curador de prova no contrato da skill, com gate de publicação`.

### Passo 10 — Modelos ORM e migração 0003
**Arquivos:** `backend/aprovaos/dados/modelos.py`, `backend/alembic/versions/0003_questoes_e_eventos.py`, `backend/tests/test_modelos.py`, `backend/tests/test_migracoes.py`.

- [ ] **RED** — `test_modelos.py::test_insere_fonte_questao_evento_reporte`: cria `Fonte(id_externo="cebraspe", nome=…, url_lista=…, status="ativa")`, `Questao(...)` com `origem` JSON dos 8 campos, `hash_dedup` único (inserir duas com o mesmo hash levanta `IntegrityError`), `EventoEstudo(tipo="resposta", acertou=True, resposta="C", confianca_declarada="certeza", tempo_ms=4200)` e `ReporteErro(conteudo_tipo="questao", status="aberto")`; após commit, os `id` são `UUID` e `questao.publicada is False` por padrão. `::test_evento_estudo_valida_tipo`: `tipo="qualquer"` viola o `CheckConstraint`.
- [ ] **RED** — `test_migracoes.py` (já existe): `alembic upgrade head` seguido de `downgrade -1` volta ao estado da V2 sem erro; o teste de "migração bate com os modelos" cobre as tabelas novas.
- [ ] **GREEN** — em `modelos.py`: `Fonte`, `Questao` (com `topico_id` nullable, `origem` JSON, `inedita` bool default `False`, `publicada` bool default `False`, `publicavel` bool, `motivo_nao_publicavel`, `gabarito_status`, `documento_id`, `hash_dedup` único, `validada_em`/`validador_versao` nullable), `Alternativa`, `EventoEstudo` (append-only, índices `(usuario_id, ocorrido_em)` e `(questao_id, ocorrido_em)`), `ReporteErro`. Nomes de tabela e coluna exatamente como em `docs/04-modelo-de-dados.md`.
- [ ] **RED/GREEN (P-26)** — `test_repositorio_edital.py::test_registrar_edital_guarda_grupo`: `topico_edital.grupo` fica `None` nas três primeiras matérias do fixture e `"CONHECIMENTOS ESPECÍFICOS"` nas quatro últimas. Acrescentar a coluna `grupo: Mapped[str | None]` a `TopicoEdital` e preenchê-la em `registrar_edital` a partir do `grupo` que o parser já devolve.
- [ ] **GREEN** — migração `0003` escrita à mão a partir do autogenerate, com `down_revision = "0002"`, a coluna `topico_edital.grupo` e um `downgrade()` que derruba as cinco tabelas na ordem inversa e remove a coluna.
- [ ] **Verde** — `uv run pytest tests/test_modelos.py tests/test_migracoes.py -v` e, com o Postgres do Compose de pé, `uv run pytest -m postgres`.
- [ ] **Commit** — `feat(v3): tabelas fonte, questao, alternativa, evento_estudo e reporte_erro (Alembic 0003)`.

### Passo 11 — Repositório de questões
**Arquivos:** `backend/aprovaos/dados/repositorio_questao.py`, `backend/tests/test_repositorio_questao.py`.

- [ ] **RED** —
  - `test_salvar_questoes_dedup`: salvar a mesma lista duas vezes → N linhas, não 2N; a segunda passada devolve `(0 novas, N repetidas)`.
  - `test_contagem_por_topico`: `contagem_por_topico(db, edital_id)` devolve `{topico_id: quantas publicadas}`, ignorando as não publicáveis.
  - `test_proxima_questao_ignora_respondidas_e_reportadas`: com 3 questões publicadas, uma já respondida e uma reportada pela usuária → `proxima_questao(db, usuario_id, topico_id)` devolve a terceira; sem sobrar nenhuma, devolve `None`.
  - `test_registrar_resposta_grava_evento`: `registrar_resposta(db, usuario, questao, resposta="C", confianca="duvida", tempo_ms=5000)` cria um `EventoEstudo(tipo="resposta", acertou=True)` e **não** altera a `questao`.
  - `test_registrar_reporte`: cria `ReporteErro(status="aberto")` + `EventoEstudo(tipo="reporte")`, e a questão para de aparecer em `proxima_questao` **só** para aquele usuário (premissa H).
  - `test_topicos_vistos`: `topicos_vistos(db, usuario_id, edital_id)` devolve o conjunto de `topico_id` com ≥ 1 resposta (premissa N).
- [ ] **GREEN** — `repositorio_questao.py` com as seis funções acima, todas recebendo a `Session` como primeiro parâmetro e sem `commit` interno (quem commita é a rota/comando, como na V2).
- [ ] **Verde** — `uv run pytest tests/test_repositorio_questao.py -v`.
- [ ] **Commit** — `feat(v3): repositório de questões, respostas e reportes`.

### Passo 12 — Comando `curar` e execução real
**Arquivos:** `backend/aprovaos/motor/curar.py`, `backend/tests/test_motor_curar.py`, `docs/fatias/V3-execucao.md`.

- [ ] **RED** — `test_motor_curar.py::test_curar_grava_questoes`: com fixture de prova + gabarito já em `documento`, `curar_documento(db, config, documento_prova_id, edital_id)` grava as questões, devolve `RelatorioCuradoria(total, publicaveis, anuladas, sem_topico, pendente_revisao)` e registra um `traco` por chamada de LLM (zero chamadas sem chave). `::test_pendente_revisao_nao_grava_nada`: contagem divergente → nenhuma linha em `questao` e relatório com o problema.
- [ ] **GREEN** — `curar.py` com `curar_documento`, `main()` por `argparse` (`--evento`, `--cargo`, `--edital`) e `if __name__ == "__main__": main()`.
- [ ] **Execução real** — rodar nos concursos coletados; colar no diário `V3-execucao.md`: nº de itens por caderno, quantos publicáveis, quantos sem tópico, quantos anulados, tokens e custo se a chave existir.
- [ ] **Commit** — `feat(v3): comando de curadoria + base de questões dos concursos coletados`.

### Passo 13 — Rotas de resolver e reportar
**Arquivos:** `backend/aprovaos/api/questoes.py`, `backend/aprovaos/main.py`, `backend/tests/test_rota_questoes.py`.

- [ ] **RED** —
  - `test_get_topico_exige_login`: sem cookie → 303 para `/entrar`.
  - `test_get_topico_de_outro_tenant_404`: tópico de edital de outro tenant → 404 com o corpo de erro `{codigo, mensagem, acao}` da V1.
  - `test_get_mostra_questao_com_origem`: a página traz o comando, o texto de apoio, o enunciado e a origem completa (órgão, cargo, ano, `item 58`, caderno) e o link do PDF; **não** traz o gabarito no HTML antes de responder (`assert "Gabarito" not in corpo`).
  - `test_post_resposta_sem_confianca_400`: POST sem `confianca` → 400 com mensagem "diga se você tem certeza ou dúvida" (premissa: certeza/dúvida é obrigatório).
  - `test_post_resposta_grava_evento_e_devolve_fragmento`: POST com `resposta=C&confianca=certeza` → 200, corpo contém `"Certo"`, a justificativa ausente não quebra a tela, e há 1 `EventoEstudo`.
  - `test_post_reporte`: POST `/questoes/{id}/reportar` com motivo → 200, 1 `ReporteErro(aberto)`, e a mesma questão não volta em `GET` seguinte.
  - `test_topico_sem_questao`: tópico sem questão publicada → página com "Ainda não temos questões deste tópico" e sem erro.
- [ ] **GREEN** — `questoes.py`: `GET /topico/{slug}/questoes`, `POST /topico/{slug}/questoes` (responder, devolve fragmento HTMX) e `POST /questoes/{id}/reportar`. Router registrado em `main.py`.
- [ ] **Verde** — `uv run pytest tests/test_rota_questoes.py -v`.
- [ ] **Commit** — `feat(v3): rotas de resolver questão e reportar erro`.

### Passo 14 — Telas
**Arquivos:** `web/templates/questoes/resolver.html`, `web/templates/questoes/_resultado.html`, `web/templates/editais/concurso.html`, `backend/aprovaos/api/editais.py`, `backend/tests/test_rota_concurso.py`.

- [ ] **RED** — `test_rota_concurso.py::test_concurso_mostra_contagem_e_link`: com 3 questões publicadas no tópico `dir-adm-04-licitacoes-contratos`, a página traz `"3 questões"` naquele `<li>` e um `<a href="/topico/dir-adm-04-licitacoes-contratos/questoes">`; tópico sem questão não vira link. `::test_contador_de_vistos`: com 1 resposta gravada, o cabeçalho mostra `"1 de 36"` (premissa N).
- [ ] **GREEN** — `resolver.html` no padrão da V1/V2 (CSS por tokens, sem framework): comando, texto de apoio recolhível, enunciado, dois botões grandes **Certo** / **Errado**, o par **tenho certeza / estou em dúvida** obrigatório antes, e o resultado carregado por HTMX em `_resultado.html` com gabarito, origem completa, link do PDF e o botão "reportar erro" (formulário com motivo em texto curto). Atalhos de teclado `C`, `E` e `→` (ADR-0019).
- [ ] **RED (P-26)** — `test_rota_concurso.py::test_grupo_com_acento`: a página traz `"CONHECIMENTOS ESPECÍFICOS"` (com acento, vindo de `topico_edital.grupo`) e não `"Conhecimentos Especificos"` derivado do slug.
- [ ] **GREEN** — em `editais.py`, acrescentar ao contexto a contagem por tópico, `topicos_vistos` e o `grupo`; ajustar `concurso.html`.
- [ ] **Verde** — `uv run pytest tests/test_rota_concurso.py tests/test_rota_questoes.py -v`.
- [ ] **Commit** — `feat(v3): telas de resolver questão por tópico e contagem no verticalizado`.

### Passo 15 — Docs, pendências, decisões e commit de fim de fatia
**Arquivos:** `docs/02-produto.md` (§6), `docs/04-modelo-de-dados.md`, `docs/DECISOES.md`, `docs/PENDENCIAS.md`, `CLAUDE.md`, `docs/fatias/V3-execucao.md`.

- [ ] Atualizar a linha V3 da tabela do PRD §6 (entregue, o que ficou fora, onde está o plano e o diário).
- [ ] `docs/04-modelo-de-dados.md`: anotar o que a V3 acrescentou às tabelas (como a V2 fez).
- [ ] **ADR-0033** — gate de publicação da questão original sem validador (premissa F, com o texto do porquê).
- [ ] **ADR-0034** — `httpx2` no runtime, `pyyaml`/`types-pyyaml` em dev (licenças e motivo; regra 8 do CLAUDE.md).
- [ ] **ADR-0035** — política de coleta da Cebraspe: user-agent identificado, 24h, sem login, PDFs versionados no repo, e o achado de que `idEvento` é `0` (identidade por `eventoURL`).
- [ ] `docs/PENDENCIAS.md`: fechar **P-26** (resolvida no passo 10 + 14: `topico_edital` ganha a coluna `grupo`, preenchida por `registrar_edital` a partir do parser, e `concurso.html` passa a mostrar `grupo` com acento em vez do slug) e abrir o que sobrar (cobertura de tópicos sem questão, segmentador A–E, gabarito preliminar, fila humana de reportes).
- [ ] `CLAUDE.md`: estado das fases e "próximo passo".
- [ ] `bash scripts/checar.sh` inteiro verde.
- [ ] **Commit de fim de fatia** com o resumo para o dono.

## 7. Comandos
```bash
cd backend && uv sync

# testes (offline; o CI roda isto)
uv run pytest -q
bash ../scripts/checar.sh

# snapshots e coleta reais (uma vez, com rede)
APROVAOS_TESTES_DE_REDE=1 uv run pytest -m rede -v
uv run python ../scripts/snapshot_cebraspe.py
uv run python -m aprovaos.motor.coletar --evento TJ_PA_25_SERVIDOR --listar
uv run python -m aprovaos.motor.coletar --evento TJ_PA_25_SERVIDOR --cargo 9

# curadoria (usa GOOGLE_API_KEY se existir; senão, regras)
uv run python -m aprovaos.motor.curar --evento TJ_PA_25_SERVIDOR --cargo 9 --edital <uuid>

# teste real do classificador (uma vez, com a chave)
GOOGLE_API_KEY=… uv run pytest -m llm -v

# migração
uv run alembic upgrade head
```

## 8. Riscos
| risco | probabilidade | mitigação |
|---|---|---|
| **Segmentação do PDF falha** num caderno (layout em duas colunas, cabeçalho diferente) | alta | A regra da skill: contagem de itens ≠ contagem do gabarito → `pendente_revisao`, nada gravado, problema no relatório. Nunca gravar item pela metade. |
| **Classificação erra o tópico** e a Linda estuda a coisa errada | média | `topico_evidencia` obrigatório e visível; `confianca == "baixa"` não publica; o botão "reportar erro" é a válvula. |
| **Sem `GOOGLE_API_KEY`**, a classificação por regras cobre pouco | média | O relatório de curadoria diz quantos ficaram sem tópico; recurar é barato (o PDF já está no repo) quando a chave existir. |
| **API da Cebraspe muda** de formato ou sai do ar | baixa | Snapshots versionados: a suíte inteira roda offline; só os testes `rede` quebram, e eles não estão no CI. |
| **Poucos tópicos do edital dela com questão** (concursos municipais vs. federais) | média | O relatório mostra a cobertura por tópico; a página diz "ainda não temos questões deste tópico" em vez de fingir. Se a cobertura for ruim, o dono decide se entram mais concursos. |
| Direito autoral / uso das provas | baixa | R-02 a R-06 de `RISCOS.md`: prova é ato público, Cebraspe sem termos restritivos (P-11), exibição sempre com origem e link para o PDF da banca. |

## 9. Definition of done da V3
1. `bash scripts/checar.sh` verde (pytest, ruff, mypy `--strict`, prova de import sem efeito colateral), offline.
2. `knowledge/fontes.yaml` com a ficha da Cebraspe completa, `evidencia` existente e os cinco testes de novidade da skill passando (inclusive o "exatamente 1 item novo").
3. Provas e gabaritos de 3 a 5 concursos no repo, com `Documento` correspondente (hash, url de origem, caminho).
4. Base com questões curadas: toda publicada tem gabarito definitivo, `origem` com 8 campos e tópico com confiança ≥ média; nenhuma anulada publicada.
5. `/concurso/{id}` mostra contagem por tópico e "X de N vistos"; `/topico/{slug}/questoes` resolve com certeza/dúvida obrigatório, mostra gabarito com origem e link do PDF, e reportar erro tira a questão da fila da usuária.
6. `docs/fatias/V3-execucao.md` com os números reais da curadoria (itens, publicáveis, sem tópico, anulados, custo se houve IA).
7. ADR-0033, 0034 e 0035 escritas; PRD §6 e `CLAUDE.md` atualizados.

## 10. Linha para a tabela do PRD §6
`| V3 (2+9 parcial) | Questões originais da Cebraspe por tópico | coletor da API Cebraspe (ficha em knowledge/fontes.yaml, identidade {eventoURL}/{nomeArquivo}, 5 testes de novidade), provas e gabaritos de <N> concursos no repo; curador determinístico (segmentação C/E + gabarito definitivo) com classificação de tópico por IA em lote e fallback por regras; gate de publicação da questão original (ADR-0033); tabelas fonte/questao/alternativa/evento_estudo/reporte_erro (Alembic 0003); /topico/{slug}/questoes com certeza-dúvida, origem completa e reportar erro; contagem e "X de N vistos" no verticalizado | inéditas e validador (fatia 5), FSRS (V5), calibrador e despublicação (fatia 8), FGV (P-13), segmentador A–E, embeddings | <estado> |`

## 11. Perguntas em aberto (responder antes do passo indicado; opção recomendada primeiro)
| id | pergunta | quando |
|---|---|---|
| Q1 | A lista final de concursos (passo 5) — o dono confere a tabela antes de baixar. | passo 5 |
| Q2 | Se a cobertura de tópicos do edital dela ficar abaixo de ~60 %, entram mais concursos ou a tela assume a lacuna? | passo 12, com o número na mão |
| Q3 | O texto de apoio longo (meia página) aparece aberto ou recolhido por padrão na tela? | passo 14 |

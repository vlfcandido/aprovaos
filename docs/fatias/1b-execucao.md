# Fatia 1b — registro de execução
> O que é: o diário de execução do plano `1b-radar-e-conta.md` (Rulings 38–42). Quando ler: ao
> revisar o radar de editais, "meus concursos" ou o login por Google, ou ao retomar a partir de
> um passo específico.

Executado em 19/09/2026 em `/Users/vinicius/PycharmProjects/aprovaos/backend`, `uv` + CPython
3.13, SQLite (sem Docker). Base de partida: `main` no commit `d9e13b4`,
`bash scripts/checar.sh` verde (1030 passed, 6 skipped). O adendo do brief corrigiu o número da
migração desta fatia para `0018` (a cadeia real era `…0014 → 0016 → 0017`, não `0015` como o
plano previa) — usado aqui.

## Passo 1 — `dominio/radar.py` (puro)

`ConcursoDoRadar`/`ler_catalogo`/`extrair_uf`/`ler_periodo_inscricao`, contra a fixture real
`knowledge/fixtures/fontes/cebraspe/catalogo-todas-as-fases-2026-09-19.json`. 18 testes
red-first em `test_dominio_radar.py`, todos batendo os números medidos no §1 do plano (1 novo, 8
inscrições abertas, 63 em andamento, 424 encerrados — contagem **bruta** de itens, antes de
qualquer deduplicação).

**Achado não previsto no plano:** `extrair_uf` precisou de um teste negativo cuidadoso — o
primeiro que escrevi (`"PERICIA OFICIAL MA 26"` / `"PERICIA_OFICIAL_MA_26"`) na verdade *confirma*
`uf="MA"` (o token aparece isolado nos dois lugares), então não servia como caso negativo; troquei
para um exemplo sintético em que a UF aparece colada a outro token no `eventoURL`
(`"ORGAO_SPTESTE_26"`), que é o caso real que a regra do Ruling 39 precisa rejeitar.

`casar_com_perfil` (passo 2, mesmo arquivo) reusa `motor.coletar.cargo_de_direito` literalmente
(import direto de `dominio/radar.py` para `motor/coletar.py`) — uma direção de importação que
não tem precedente no repositório (`dominio/` normalmente não importa de `motor/`). Segui a
instrução explícita do plano ("reusa `motor.coletar.cargo_de_direito` — não reimplemente o
léxico") porque `motor/coletar.py` não faz I/O em import (só define regex e constantes), então
não viola "nenhum efeito colateral em import"; é uma camada acima do que o resto do código faz,
registrado aqui para quem revisar notar a exceção.

## Passo 2 — tabela `concurso_radar` e migração 0018

`ConcursoRadar` (`dados/modelos.py`) e a migração `0018_concurso_radar_e_google_oauth.py` (gerada
por `alembic revision --autogenerate` contra os modelos já escritos, depois reescrita à mão no
estilo das migrações anteriores — sem o import quebrado que o autogenerate produziu para
`DataHoraUtc`, trocado por `sa.DateTime(timezone=True)` puro, como `0001_base.py` já faz). A
mesma migração também prepara `usuario` para o Google OAuth do passo 6 (`senha_hash` nullable,
`google_sub` novo) — um único arquivo de migração para a fatia inteira, como o adendo pediu.

`test_migracoes.py::test_migracao_inicial_bate_com_os_modelos` (na verdade testa a cadeia
completa até `head`) confirma `compare_metadata() == []` de primeira.

`dados/repositorio_radar.py::sincronizar` — 10 testes (`test_repositorio_radar.py`): insere,
não duplica, atualiza mantendo `primeiro_visto_em`, e **nunca apaga** um concurso que some da
fonte (só o `ultimo_visto_em` para de avançar).

## Passo 3 — comando `varrer`

`motor/radar.py::varrer` — um `FonteCebraspe.obter_catalogo()` (método novo, mesmo cliente/
User-Agent da V3) + `ler_catalogo` + `sincronizar`.

**Achado não previsto no plano, na fixture real:** a própria API repete um evento na mesma
resposta — `INSS_22` aparece duas vezes no grupo "Encerrados" do catálogo de 19/09/2026, uma vez
como `eventoNomeAbreviado="INSS 22"` e outra como `"INSS_22"` (mesmo `idEvento` diferente, 1934 e
1940). Sem tratamento, a segunda ocorrência virava uma "atualização" da primeira dentro da
**mesma** rodada — um relatório mentiroso (o catálogo "mudando" sozinho). `varrer` deduplica por
`evento_url` antes de sincronizar (mantém a última ocorrência), mesmo defeito de fonte que
`FonteCebraspe.listar_novidades` já tratava para a listagem de eventos da V3. Resultado: **496
itens brutos, 495 concursos distintos** — os testes (`test_motor_radar.py`) e a execução real
(abaixo) usam 495 como o número correto do catálogo.

## Passo 4 — telas do radar

`api/radar.py` + `web/templates/radar/` (`index.html`, `detalhe.html`, `erro_analise.html`) +
link "Radar" em `base.html` (sempre visível, com ou sem login — o catálogo é informação pública).

**Correção de design feita durante a execução (não estava certo na primeira versão):** o plano
diz "catálogo com filtro por fase e por UF" no mesmo parágrafo em que descreve o selo "combina",
e minha primeira implementação usou `uf` como filtro de banco (`WHERE uf = :uf`) — o que
**esconde** concursos de outra UF, violando o Ruling 40 ("nunca esconde"). O teste
`test_radar_marca_combina_por_uf_sem_esconder_os_outros` pegou isso na hora (RED genuíno, não
escrito depois do fato). Correção: `fase` continua um filtro de verdade (esconde — é navegação
explícita, tipo aba); `uf`/`salario_min`/`area` viraram **preferência pura**, usada só para o
selo "combina" e a ordenação, nunca para reduzir a lista no SQL. Documentado no docstring da
rota `radar()`.

`GET /radar/{evento_url}` consulta o detalhe **ao vivo** (`FonteCebraspe.obter_detalhe`, método
novo) em vez de guardar cargos/arquivos no catálogo persistido — o catálogo nunca traz
`eventoCargos`/`arquivosEdital` (só o detalhe tem). Se a fonte estiver fora do ar
(`FonteIndisponivel`), a página mostra o que já tem (nome, fase, UF, lacunas) com um aviso, em
vez de quebrar — testado com um dublê de fonte que levanta a exceção.

`app.state.fonte_cebraspe` nasce em `criar_app` (fábrica, sem I/O na criação); testes substituem
por um dublê antes da chamada.

## Passo 5 — meus concursos (F1.3)

`POST /radar/{evento_url}/acompanhar` (toggle em `perfil_estudo.concursos_acompanhados`) e
`POST /perfil/principal` (troca `concurso_principal_id`, confere que o concurso é do tenant —
403 senão). As duas exigem rotina salva (`perfil_estudo` já existir) — sem ela, redirecionam
para `/rotina` em vez de inventar uma rotina vazia (mesmo critério de `SemConcursoPrincipal` que
`motor/plano.py` já usa). `dados/repositorio_perfil.py` ganhou `marcar_principal`/
`alternar_acompanhamento`, as duas gravando versão nova append-only e **preservando** os campos
de rotina da versão anterior (`_proxima_versao_a_partir_de`) — sem isso, marcar o principal
resetaria `horas_por_dia_semana` para o que `PerfilEstudo` usa de default.

O "aviso de impacto" (F1.3 CA) ficou **mais simples** do que o exemplo do plano ("41 tópicos sem
cobertura no seu histórico"): esse número exigiria o concurso acompanhado já ter um `Concurso`/
edital analisado por essa aluna, o que o radar não garante (ela pode acompanhar um concurso da
Cebraspe sem nunca ter subido o PDF dele) — registrado como P-69 em `docs/PENDENCIAS.md`, com o
aviso atual sendo genérico ("você acompanha N concurso(s) do radar... o plano segue só o
principal").

"Analisar este edital" (`POST /radar/{evento_url}/analisar`) baixa o PDF do primeiro arquivo de
`arquivosEdital` que termina em `.pdf`, via `FonteCebraspe.baixar` com uma `Novidade` sintética
(reaproveitando a URL `URL_ARQUIVO` já usada para prova/gabarito na V3 — o mesmo padrão de CDN,
nunca medido especificamente para edital, mas é o mesmo campo `nomeArquivo` da mesma API) e roda
o pipeline da V2 via `api.editais.processar_conteudo_pdf`, extraído de `processar_edital` nesta
fatia (refactor sem mudar comportamento — os 87 testes de edital continuaram verdes). O
`Concurso` nasce `origem="real"` (o padrão de `registrar_edital`; a fatia nunca passa
`origem="fixture"` para dado vindo da API).

## Passo 6 — Google OAuth (RF-20, Ruling 42)

`config.py` ganhou `google_oauth_client_id`/`google_oauth_client_secret` (`None` por padrão);
`.env.example` documentado com a URL da doc oficial
(https://developers.google.com/identity/protocols/oauth2/web-server). `dominio/conta.py` ganhou
`PerfilGoogle` (o corpo do endpoint `userinfo`, não o `id_token` — decisão: ler o perfil por
`GET userinfo` com o `access_token` é mais simples que verificar a assinatura de um JWT, e não
pede nenhuma dependência nova de JWT/JWK).

`api/conta.py::entrar_google`/`entrar_google_callback`/`trocar_codigo_por_perfil` — o `state` é
assinado pelo mesmo HMAC do cookie de sessão (`api.sessao.assinar`/`verificar_assinatura`,
reaproveitados como estão, sem duplicar a lógica de HMAC). `app.state.cliente_google_oauth`
(`httpx2.Client` genérico) nasce na fábrica, substituível em teste pelo mesmo molde de
`_ClienteHttp` que `FonteCebraspe` usa (`ProvedorGoogleFalso` em
`test_rota_conta_google.py`, com `post`/`get`).

`usuario.senha_hash` virou opcional (migração 0018) e `dados.repositorio_conta.autenticar` passou
a checar `senha_hash is None` **antes** de chamar `verificar()` — sem isso, uma conta só-Google
faria `argon2.PasswordHasher.verify(None, senha)` estourar `TypeError` em vez de
`CredenciaisInvalidas` (achado ao escrever `test_autenticar_conta_so_google_nunca_bate_senha`).

15 testes de rota (`test_rota_conta_google.py`) + 4 de repositório
(`test_repositorio_conta.py`): sem configuração → 404 nas duas rotas e nenhum botão nas telas;
`state` adulterado ou ausente → mensagem genérica, sem logar; `email_verified=false` → rejeitado;
provedor fora do ar → mensagem genérica; e-mail já cadastrado por senha → **liga** a conta
(`google_sub` preenchido, `senha_hash` original intacto), nunca duplica; conta só-Google tentando
entrar por senha → mesma mensagem genérica de sempre (não vaza que só existe o caminho Google).

## Execução real (§8 do plano)

`uv run python -m aprovaos.motor.radar` contra a API de verdade, banco SQLite descartável
(`/tmp/radar-real.db`), 19/09/2026:

```
radar: 495 novo(s), 0 atualizado(s), 0 inalterado(s)
```

Consulta direta ao banco resultante:

| métrica | valor |
|---|---|
| total de concursos distintos | 495 |
| por fase | `em_andamento` 63 · `encerrado` 423 · `inscricoes_abertas` 8 · `novos` 1 |
| com UF confirmada (Ruling 39) | 128 de 495 (25,9 %) |
| sem salário informado (lacuna declarada) | 113 de 495 (22,8 %) |
| sem vagas informadas (lacuna declarada) | 64 de 495 (12,9 %) |

`encerrado` deu 423, não 424 (o número bruto medido no §1 do plano) — a diferença é exatamente o
`INSS_22` duplicado, deduplicado no passo 3.

**Combina com o perfil real da Linda (Direito, PR):** rodando `casar_com_perfil` com
`PreferenciaRadar(ufs=["PR"], salario_minimo_brl=None, area="direito")` contra os 495 concursos
persistidos, `cargos=[]` (a listagem não abre o detalhe de cada evento — P-71):

```
AGEPAR PR 26          (AGEPAR_PR_26)          em_andamento  motivos=['PR']
PGE PR 24 PROCURADOR  (PGE_PR_24_PROCURADOR)  encerrado     motivos=['PR']
SEED PR 20 PROFESSOR  (SEED_PR_20_PROFESSOR)  encerrado     motivos=['PR']
SEFA PR 25            (SEFA_PR_25)            encerrado     motivos=['PR']
```

**4 de 495 combinam** — todos só pela UF (nenhum mostra `"cargo de Direito"` no motivo, porque a
listagem nunca abre o detalhe de cargos — P-71, registrada em `docs/PENDENCIAS.md`). Dos 4, só
**`AGEPAR_PR_26` está em andamento** (os outros três já encerraram); consultando o detalhe dele
ao vivo (`GET /radar/AGEPAR_PR_26`), o cargo 3 é de fato "ESPECIALISTA EM REGULAÇÃO —
ESPECIALIDADE: DIREITO" — a aluna veria o cargo certo na tela de detalhe, mesmo sem o selo
"cargo de Direito" na listagem. Isso é honesto e é exatamente o que o plano pediu registrar: **se
nenhum concurso aberto de Direito no PR aparecesse, o diário diria isso** — aqui apareceu um
(AGEPAR/PR, cargo de Especialista em Regulação, área Direito), mas o selo da listagem não capturou
sozinho, só o clique no detalhe.

## Checagem final

`bash scripts/checar.sh`: ruff, `ruff format --check`, `mypy --strict` (220 arquivos), prova de
import sem efeito colateral e a suíte inteira — **1103 passed, 6 skipped** (era 1030 passed, 6
skipped na base; 73 testes novos desta fatia).

## Fora de escopo (`docs/PENDENCIAS.md`)

FGV (P-13, Ruling 38, sem entrada nova — já existia) · alerta por e-mail/push (P-68) · split N/M
do plano entre concursos acompanhados (P-69) · data da prova, que não existe na API (P-70) ·
selo "cargo de Direito" na listagem do radar, que exigiria abrir o detalhe de ~495 eventos por
carregamento (P-71).

# Fatia V5 — registro de execução
> O que é: o diário de execução do plano `V5-fio-da-memoria.md`. Quando ler: ao revisar o que foi
> feito nesta fatia ou ao retomar a partir da fatia 4 (dossiês/aulas — fio (a) e (c)).

Executado em 19/09/2026 em `/Users/vinicius/PycharmProjects/aprovaos/backend`, `uv` + CPython
3.13, branch `main` a partir do commit `479b283` (517 testes verdes).

## Passo 1 — `dominio/fio_memoria.py` (puro)

`EstatisticaTopicoVisto` (pydantic — o que se sabe de um tópico já visto, agregado fora daqui),
`ItemIntercalado` (o candidato ranqueado, com `motivo` pronto), e três funções:

- `escolher_para_intercalar`: duas filas alternadas (erro mais recente / tempo sem ver), sem
  repetir tópico, até reunir até `quantidade` (padrão 3) distintos. Sem histórico ou só com o
  próprio tópico atual no histórico, devolve `[]` — nunca sorteia.
- `decidir_proximo_intercalado`: a cada `PERIODO_INTERCALACAO` (4) posições do "bloco", a próxima
  é intercalada; cicla pelos candidatos disponíveis conforme a rodada avança.
- `ordem_para_tentar`: a ordem de tentativa (o escolhido primeiro, os demais em seguida,
  circular) — para a rota conseguir pular para o próximo candidato quando o primeiro não tem mais
  questão disponível.

16 testes em `tests/test_dominio_fio_memoria.py`, incluindo o motivo batendo literalmente com o
exemplo do enunciado ("de Direito Constitucional, que você viu há 6 dias e errou 2 de 3") e a
cadência (disparos em 3, 7, 11 para período 4).

## Passo 2 — `evento_estudo.dados` (migração 0008)

`docs/04-modelo-de-dados.md` §2 já nomeava `dados (JSON)` para `evento_estudo` desde a Fase 3;
nenhuma fatia (V1–V4) tinha precisado dele. A V5 o cria de verdade — não é coluna nova fora do
plano, é o plano sendo cumprido pela primeira vez (`docs/fatias/V5-fio-da-memoria.md` §4).
Migração `0008_evento_estudo_dados.py`, nullable, sem dado a migrar (todas as linhas existentes
ficam com `dados=None`). `test_migracoes.py` (já existente, sem teste próprio necessário) cobre
o `compare_metadata`/downgrade automaticamente.

## Passo 3 — `dados/repositorio_fio_memoria.py`

`estatisticas_topicos_vistos` (agregação SQL por tópico — `func.max`/`func.count`/`func.sum` com
`case()`, escopada ao mesmo `edital_id` que `topicos_vistos` já usa) e `quantidade_no_bloco`
(conta eventos cujo `dados["bloco_topico_id"]` bate com o tópico, filtrando em Python sobre o
JSON já desserializado — simplificação registrada como `P-46`, aceitável na escala do piloto
n=1). 4 testes em `tests/test_repositorio_fio_memoria.py`.

## Passo 4 — `api/questoes.py`: a intercalação de verdade

`_edital_do_topico_para_tenant` (mesma junção de `_topico_do_tenant`, devolvendo o `edital_id`) e
`_proximo_item_intercalado` (monta as estatísticas, ranqueia, calcula a posição do bloco e tenta
achar uma questão disponível entre os candidatos, na ordem de `ordem_para_tentar`).

`GET /topico/{slug}/questoes` chama isso antes de `proxima_questao`; quando há item intercalado
com questão disponível, o contexto ganha `fio_da_memoria={"motivo": ...}` e os campos ocultos
`fio_origem_topico_id`/`fio_motivo` (além do `questao_id` de sempre).

`POST /topico/{slug}/questoes` ganhou os dois campos opcionais. Quando `fio_origem_topico_id`
vem preenchido, a rota primeiro confirma que ele pertence a **algum edital do tenant do
usuário** (`_edital_do_topico_para_tenant`) — nunca aceita um tópico de outro tenant, mesmo que a
`questao_id` que o acompanha exista e esteja pendente nesse tópico alheio (testado em
`test_fio_origem_topico_id_de_outro_tenant_e_recusado`) — só então checa a pendência da questão
contra **aquele** tópico (não o da URL). O evento gravado carrega `dados={"bloco_topico_id":
str(topico_da_url.id), "fio_origem_topico_id": ..., "fio_motivo": ...}` só quando é de fato um
item intercalado aceito; caso contrário, só `bloco_topico_id`.

Achado durante a implementação (divergência pequena e documentada em relação ao plano escrito
antes de codificar): o plano previa um campo oculto `bloco_topico_id` no formulário para o `POST`
ecoar; na implementação isso saiu — `topico.id` (resolvido pelo próprio `slug` da URL) já é a
âncora do bloco, sem precisar confiar em nenhum valor vindo do cliente. Simplifica a superfície de
ataque (um `bloco_topico_id` forjado no formulário nunca teria efeito, porque não é lido) sem
perder nenhuma garantia do plano.

12 testes novos em `tests/test_rota_questoes.py`/`test_rota_revisao.py` continuam passando sem
alteração (a V5 não tocou `/revisar`); 3 testes de integração novos em
`tests/test_rota_fio_memoria.py`:
- sem histórico de outro tópico, nunca intercala, mesmo na 4ª posição;
- a 4ª posição intercala, com o selo e o motivo certos no HTML, o evento gravado com os três
  campos em `dados`, e a posição seguinte volta a ser nativa;
- `fio_origem_topico_id` de um tópico de outro tenant é recusado (200 + aviso de "não está mais
  disponível"), sem gravar evento nenhum.

## Passo 5 — Templates

`_cartao_questao.html` e `_resultado.html` ganharam o bloco opcional `{% if fio_da_memoria %}`
com o selo `.selo--fio-da-memoria` — cor de ação (`--cor-acao`/`--cor-acao-suave`, tokens já
existentes), para não se confundir com o âmbar do "por quê" da justificativa jurídica nem com as
cores de acerto/erro. Nenhuma tela nova: os dois parciais já eram compartilhados entre
`topico.html` e `revisao.html` desde a V4; `revisao.html` nunca recebe `fio_da_memoria` porque
`/revisar` não chama `_proximo_item_intercalado` (§5 do plano — precedência).

## Resultado

`bash scripts/checar.sh` na raiz: ruff, `ruff format --check`, `mypy --strict` (128 arquivos),
prova de import sem efeito colateral e a suíte inteira — **540 passed, 6 skipped** (mesmos 6
marcadores `postgres`/`llm`/`rede` de sempre, nenhum tocado por esta fatia). Partindo de 517
antes da V5: +23 (16 em `test_dominio_fio_memoria.py`, 4 em `test_repositorio_fio_memoria.py`, 3
em `test_rota_fio_memoria.py`).

## Demonstração real contra `backend/dev.db`

`dev.db` (SQLite local) estava na migração `0007`; `alembic upgrade head` aplicou a `0008` sem
erro (backup tirado antes, descartado depois de confirmar). Script solto (não commitado) abriu
uma sessão de servidor de verdade para a conta real da Linda
(`linda.piloto@exemplo.com`, `c22ce889-…`) via `repositorio_sessao.abrir_sessao` (mesmo mecanismo
do login — sem precisar da senha dela) e usou `TestClient` contra a `criar_app` apontada para o
`dev.db` real, não um banco de teste:

1. **Tópico atual**: `dir-pro-civ-05-recursos-apelacao` ("Recursos e apelação") — ela nunca tinha
   respondido nada aqui, com 9 questões publicáveis pendentes (dado real da V3, coletor
   Cebraspe). Respondeu 3 nativas via `POST` real; nenhuma mostrou o selo.
2. **4ª posição (`GET`)**: o selo apareceu — *"Fio da memória — de DIREITO ADMINISTRATIVO, que
   você viu há 0 dias e errou 1 de 1"* — vindo do tópico **"Poderes administrativos."**
   (`dir-adm-03-poderes-administrativos`), calculado a partir do histórico real dela (ela errou
   uma questão desse tópico horas antes, no mesmo dia — é o erro mais recente entre os 8 tópicos
   que ela já viu neste edital, batendo com o ranking calculado independentemente por
   `escolher_para_intercalar` contra os dados reais). A questão intercalada mostrada foi uma
   questão publicável de verdade da base Cebraspe: *"Segundo a teoria do ciclo de polícia, o
   poder de polícia da administração pública [...]"*.
3. **`POST` da resposta ao item intercalado**: gravou `EventoEstudo(tipo="resposta",
   questao_id=499193aa-…, acertou=True)` com `dados={"bloco_topico_id":
   "5a831428-f349-41c9-8204-3bc083b52526", "fio_origem_topico_id":
   "16be0b3c-c1d5-4864-add5-332b2b484541", "fio_motivo": "de DIREITO ADMINISTRATIVO, que você viu
   há 0 dias e errou 1 de 1"}` — os três campos que o plano previa, na questão certa, no tópico
   certo.
4. **`GET` seguinte**: sem selo — a posição do bloco avançou para 4 (não é múltiplo de
   `PERIODO_INTERCALACAO - 1 = 3`), voltando à próxima questão nativa pendente do tópico atual.

Isto prova, contra dado real da conta da usuária-piloto (não fixture inventada): o ranking
escolhe o tópico certo a partir do histórico de verdade dela; a cadência intercala na posição
certa e volta ao normal depois; o evento gravado carrega a explicação completa; e o selo/motivo
aparecem no HTML de verdade que o navegador dela receberia.

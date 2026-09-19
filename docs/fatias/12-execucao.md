# Fatia 12 — registro de execução
> O que é: o diário de execução do plano `12-billing.md` (Rulings 46–48). Quando ler: ao revisar
> o billing, o limite do Free ou a exclusão/exportação de dados (RF-23), ou ao retomar a partir de
> um passo específico.

Executado em 19/09/2026 em `/Users/vinicius/PycharmProjects/aprovaos/backend`, `uv` + CPython
3.13, SQLite (sem Docker). Base de partida: `main` no commit `9a2cac3`,
`bash scripts/checar.sh` verde (1103 passed, 6 skipped).

## Passo 1 — `dominio/assinatura.py` (puro)

`Tier`/`StatusAssinatura`/`Periodicidade`, `LimitesDoTier`/`LIMITES`, `UsoDoDia`, `Veredito` e as
três funções (`pode_responder`, `pode_criar_edital`, `tier_efetivo`) mais um quarto helper que o
plano não previa explicitamente, `calcular_fim_do_periodo` (soma meses de calendário de verdade,
não dias fixos — precisado pelo passo 3 para gravar `assinatura.fim` sem chamar a API do gateway
de novo). 16 + 4 testes red-first em `test_dominio_assinatura.py`.

**Duas lacunas declaradas, não inventadas:**
- `LimitesDoTier.ineditas_por_dia` fica `None` nas duas tiers — nenhuma ADR/PRD decidiu um número
  para um teto diário de questões inéditas servidas; o campo existe (o plano §2 o nomeia,
  `UsoDoDia.ineditas_servidas` já é rastreável), mas `None` é honesto onde um número seria
  inventado. Registrado em P-73.
- `pode_criar_edital` recebe `editais_com_dna_existentes` (contagem **total** do tenant), não
  `editais_hoje` como o pseudocódigo do plano §2 sugeria — ADR-0015 diz "DNA de 1 concurso"
  (teto de recurso, não cota diária); segui o texto da ADR, não o nome do parâmetro do rascunho.

## Passo 2 — `pagamento/gateway.py` e `pagamento/mercado_pago.py`

Sem WebFetch disponível nesta sessão, mas com acesso de rede via `curl`/`Bash`: a documentação
interativa em mercadopago.com.br/developers é renderizada em JS (o HTML cru não traz o corpo do
contrato), então a fonte usada foi o **OpenAPI oficial** que o Mercado Pago mantém publicamente em
`github.com/mercadopago/openapi` (`spec3.json`, operações `createSubscription`/`updateSubscription`
do recurso `/preapproval`, schemas `SubscriptionRequest`/`AutoRecurring`/`Subscription`; e
`schemas/webhooks.yaml`, `WebhookNotification`/`WebhookSignatureHeader` — o formato do
`x-signature` e o manifesto HMAC). Consultado e citado nos docstrings; nenhum endpoint/campo
inventado.

`GatewayPagamento` (Protocol): `criar_assinatura`, `cancelar`, `ler_evento` — este último devolve
`EventoPagamento | None` (mudança do sketch do plano, que não previa `None`): quando a assinatura
HMAC confere mas o `type`/`action` não é um dos dois que esta fatia processa (assinar, cancelar),
a rota grava o payload cru em `evento_cobranca` e não faz mais nada, em vez de forçar um evento
que não existe. `TipoEventoPagamento` também ficou menor que o sketch (`assinatura_autorizada`/
`assinatura_cancelada`, sem `pagamento_recusado`) — mapear pagamento recusado exigiria, pela
própria nota do schema oficial ("always GET the resource"), uma consulta adicional ao recurso
para confirmar o status, que esta fatia não implementa; `tier_efetivo` já sabe tratar
`status="em_atraso"` no domínio, só falta o produtor real (P-75).

`GatewayMercadoPago.ler_evento` também ganhou um terceiro parâmetro (`id_requisicao`, o cabeçalho
`x-request-id`) que o sketch do plano não tinha — o manifesto HMAC oficial
(`"id:[notif_id];request-id:[req_id];ts:[ts];"`) precisa dele, e não dá para calculá-lo a partir
só do corpo. **Lacuna declarada, não verificada:** a fonte não deixa claro se `notif_id` é o `id`
de topo do `WebhookNotification` (o que esta implementação assume) ou o `data.id` do recurso —
os dois existem no mesmo payload. Registrado em P-72; só um webhook real confirma.

9 testes red-first contra um `ClienteHttp` falso (`test_pagamento_mercado_pago.py`), cobrindo
criar mensal/anual (com os valores certos de `frequency`/`transaction_amount`), cancelar,
ler evento autorizado/cancelado/não-reconhecido e três formas de assinatura inválida (adulterada,
segredo errado, cabeçalho mal formado).

## Passo 3 — migração `0019`, modelos e repositórios

`assinatura`/`evento_cobranca` nomeados e com os campos exatos de `docs/04-modelo-de-dados.md`
§2/§4 — **não** os nomes do sketch do plano (`evento_pagamento`, campo `plano`): a doc de
arquitetura é a fonte de verdade para nome de tabela/campo, e ela já usava `evento_cobranca`.
Migração `0019_assinatura.py` (cadeia `…0017 → 0018 → 0019`, como o brief previu).

`dados/repositorio_assinatura.py`: `criar_ou_atualizar_pendente` grava `status="expirada"` de
propósito — reaproveita o vocabulário fechado de `StatusAssinatura` para "ainda não confirmada
pelo webhook" (`tier_efetivo` já devolve `"free"` para `"expirada"` em qualquer `fim`), em vez de
inventar um quinto status só para o intervalo entre o clique em "assinar" e o webhook chegar.
`aplicar_evento` sempre grava `evento_cobranca` (mesmo para evento não reconhecido ou sem
assinatura correspondente — "dinheiro exige rastro"). `dados/repositorio_uso.py::uso_do_dia`
recomputa de `evento_estudo`, sem tabela nova (mesmo princípio do diagnóstico da fatia 7). 8 + 5
testes red-first.

`api/assinatura.py`: `GET/POST /assinar`, `POST /webhooks/pagamento`, `POST
/assinatura/cancelar` — as três atrás de uma dependência `exigir_gateway` que roda **antes** de
`exigir_usuario` na assinatura de cada rota (achado de execução: se `exigir_usuario` viesse
primeiro, faltando login a resposta seria 303 para `/entrar`, não 404 — quebrando Ruling 46 para
quem não está logado). 13 testes de rota contra `GatewayPagamentoFalso`
(`tests/dubles_pagamento.py`, mesmo molde de `_ClienteHttp`).

`api/conta.py` ganhou `GET /conta/exportar` (JSON) e `POST /conta/excluir` (RF-23, Ruling 48) —
`dados/repositorio_lgpd.py::excluir_dados_do_usuario` cancela a assinatura no gateway antes (se
houver uma ativa/em atraso), depois anonimiza a conta (e-mail sintético, senha e `google_sub`
apagados), apaga `cartao`/`perfil_estudo` de verdade e revoga toda sessão aberta
(`repositorio_sessao.revogar_todas_as_sessoes`, função nova). **Lacuna declarada:** o modelo de
dados §5 promete "eventos ficam sem `usuario_id`"; `evento_estudo.usuario_id` é `NOT NULL` desde
a V3 e torná-la nullable é uma migração de esquema com efeito em FSRS/calibrador, fora do escopo
desta fatia — registrado em P-74. 4 + 4 testes.

Os botões de LGPD aparecem em `/conta` **sempre**, independente de `MERCADO_PAGO_*` — LGPD não é
billing (Ruling 48 é explícito: "a LGPD entra junto, não depois", e a leitura literal é que ela
não devia ficar atrás do interruptor do gateway).

## Passo 4 — limites nos pontos que servem conteúdo

`veredito_de_limite` (promovida de privada a pública em `api/questoes.py`, mesmo padrão que a
fatia 7 já usou para `contexto_questao`/`contexto_evento`, porque `api/diagnostico.py` também
precisa dela) — conferido só ao **montar** a próxima questão em `GET /topico/{slug}/questoes` e
`GET /diagnostico`; nunca em `POST` (nunca corta uma resposta em andamento) e nunca em `/revisar`
nem `/topico/{slug}/aula` — as duas rotas não chamam a função, então por construção não existe
caminho para limitá-las (o ponto que o brief pediu para não relaxar). 4 + 1 testes de rota.

Wiring de `pode_criar_edital` em `POST /editais/subir` **não estava na lista explícita do passo 4
do plano** (que citava só `api/questoes.py`/`api/diagnostico.py`) — acrescentado porque a ADR-0015
("Free = DNA de 1 concurso") não tinha nenhum ponto de aplicação sem isso, e a função já nascera
no passo 1 para essa finalidade. A checagem roda **antes** do pipeline de PDF/DNA (não desperdiça
parser nem chamada de LLM num upload que vai ser recusado). Precisou de uma função nova,
`repositorio_edital.contagem_editais_com_dna` (testada). 1 + 1 testes de rota.

**Regressão encontrada e corrigida:** `test_rota_editais.py::test_editais_lista_e_marca_principal`
(V2) subia dois editais para o mesmo tenant Free para testar a listagem/"principal" — com o limite
novo, o segundo upload passou a ser recusado. Corrigido dando ao tenant uma `Assinatura` Pro antes
do segundo upload nesse teste (o teste é sobre listagem, não sobre o limite; o cenário real de "2
concursos" só existe para Pro agora).

## Execução real (§6 do plano — honesta)

Sem credencial (o dono não criou conta no Mercado Pago — fora do escopo desta fatia), a "execução
real" é a suíte de integração contra `GatewayPagamentoFalso`, que exercita o fluxo inteiro pela
API HTTP (não só chamadas de função): `POST /assinar` cria a assinatura pendente e redireciona
para o checkout do dublê (`test_post_assinar_cria_pendente_e_redireciona_para_checkout`);
`POST /webhooks/pagamento` com um evento assinado vira Pro (`test_webhook_autorizado_vira_pro`,
que também confere que `/conta` passa a mostrar "Pro"); `POST /assinatura/cancelar` cancela no
gateway e mantém Pro até o fim do período (`test_cancelar_mantem_pro_ate_o_fim_do_periodo`).
**A rodada com o Mercado Pago de verdade depende do dono criar a conta** (P-02) — inclusive os
dois pontos não verificados da ADR-0025 (taxa de cartão para PF, elegibilidade de assinatura
recorrente PF) e o terceiro que esta fatia acrescentou (P-72, qual `id` entra no manifesto HMAC).

## Checagem final

`bash scripts/checar.sh`: ruff, `ruff format --check`, `mypy` (240 arquivos), prova de import sem
efeito colateral e a suíte inteira — **1179 passed, 6 skipped** (era 1103 passed, 6 skipped na
base; 76 testes novos desta fatia).

## Fora de escopo (`docs/PENDENCIAS.md`)

Taxas reais e elegibilidade de assinatura recorrente para conta PF, agora um terceiro ponto não
verificado junto (qual `id` entra no manifesto HMAC — P-02/P-72) · Elite (fase 3) · boleto (fora
por decisão) · Pix Automático na retentativa (regra 5.3 da fábrica) · número de
`ineditas_por_dia` (P-73) · exclusão literal de `evento_estudo.usuario_id` (P-74) · webhook de
pagamento recusado/`em_atraso` sem produtor real (P-75) · nota fiscal e Carnê-Leão (obrigação do
dono, não do código).

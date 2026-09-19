# Fatia 12 — Billing real e limites por tier: plano

> O que é: o plano da fatia 12 do PRD (`docs/02-produto.md` §6, "Billing real + limites por
> tier — condição de lançamento" — RF-22, RF-23). Quando ler: antes de executar qualquer passo
> desta fatia e ao revisar o que foi feito; o diário fica em `12-execucao.md`.

**O que já está decidido e não se rediscute aqui:**
- **ADR-0015** — Free (diagnóstico, DNA de 1 concurso, plano básico, **20 questões/dia**, painel
  com curva) · **Pro R$ 59/mês ou R$ 490/ano** · Elite só na fase 3. Cancelamento em um clique.
  **No limite do tier, o roteador degrada o modelo — nunca corta a sessão.**
- **ADR-0025** — cobrança como **pessoa física** no piloto e nos 10 primeiros, via **Mercado
  Pago**, atrás de uma interface `GatewayPagamento` (criar cobrança, criar assinatura, cancelar,
  webhook). **Pix e cartão; sem boleto.** MEI ao chegar a 10 pagantes, sem mudar a interface.

---

## 1. A trava que define o formato desta fatia

Eu **não** crio conta, não configuro credencial de gateway e não ligo cobrança — são atos do dono
(lista final, §1.3), e dois pontos da ADR-0025 continuam **não verificados**: taxa de cartão para
PF e se conta PF aceita assinatura recorrente. Decisão desta fatia:

### Ruling 46 — billing entra pronto, desligado por padrão
Implementar o fluxo inteiro atrás de `MERCADO_PAGO_ACCESS_TOKEN`/`MERCADO_PAGO_WEBHOOK_SECRET`.
**Sem as duas variáveis, o produto inteiro roda como hoje** — todo mundo no Free, nenhuma tela de
assinatura, nenhuma rota de webhook. Testes contra um gateway falso que implementa o mesmo
`Protocol` (o molde é `motor/fontes/cebraspe.py::_ClienteHttp`, que já faz isso). No dia em que o
dono colar o token, funciona. Custo se estiver errado: código testado e inerte.

### Ruling 47 — o limite do Free nunca interrompe o que já começou
A ADR-0015 diz "degrada o modelo, nunca corta a sessão". Traduzido para regra implementável:
o limite de 20 questões/dia é conferido **ao montar a próxima questão**, não no meio de uma
resposta; atingido o limite, a tela **mostra o que falta** e oferece continuar amanhã ou assinar
— sem erro, sem modal bloqueante, sem perder a resposta em curso. E o que **nunca** é limitado:
revisão de cartão vencido (FSRS) e leitura de aula já publicada — cortar revisão destrói a
memória que o produto existe para construir.

### Ruling 48 — LGPD antes de cobrar, não depois
RF-23 (exportar e excluir todos os meus dados) entra **nesta fatia**, não numa futura: no dia em
que existir pagamento existe relação de consumo, e o produto já guarda energia/sono, que a
pesquisa §9 trata como tangente a dado sensível. Exportar sai em JSON (tudo que é do usuário);
excluir apaga de verdade, com a assinatura cancelada antes.

---

## 2. Passo 1 — `dominio/assinatura.py` (puro)

```python
Tier = Literal["free", "pro"]
StatusAssinatura = Literal["ativa", "em_atraso", "cancelada", "expirada"]

class LimitesDoTier(BaseModel):
    questoes_por_dia: int | None      # None = sem limite
    editais_com_dna: int | None
    ineditas_por_dia: int | None

LIMITES: Final[dict[Tier, LimitesDoTier]]

class UsoDoDia(BaseModel):
    questoes_respondidas: int
    ineditas_servidas: int

class Veredito(BaseModel):
    permitido: bool
    motivo: str | None                 # pt-BR, pronto para a tela, nunca vazio quando negado
    quanto_falta: int | None
    convite: str | None                # "assine o Pro para continuar hoje" — nunca ameaça

def pode_responder(tier: Tier, uso: UsoDoDia) -> Veredito: ...
def pode_criar_edital(tier: Tier, editais_hoje: int) -> Veredito: ...
def tier_efetivo(status: StatusAssinatura, fim_do_periodo: date, hoje: date) -> Tier: ...
```

- `tier_efetivo` é a regra que evita o defeito clássico: **assinatura cancelada continua Pro até
  o fim do período pago**. `em_atraso` também continua Pro durante a janela de retentativa de
  10 dias (regra 5.3 da fábrica, citada na visão §9) — churn involuntário não é churn.
- Revisão de cartão e leitura de aula **não** têm função de limite: por construção, não existe
  caminho para limitá-las (Ruling 47).

**Testes red-first:** Free na 20ª questão ainda pode; na 21ª não, com motivo e convite;
cancelada antes do fim do período ainda é Pro; cancelada depois é Free; `em_atraso` no 9º dia é
Pro, no 11º é Free; Pro não tem limite.

## 3. Passo 2 — `pagamento/gateway.py` (interface) e `pagamento/mercado_pago.py`

```python
class CobrancaCriada(BaseModel):
    id_externo: str
    url_pagamento: str
    expira_em: datetime

class GatewayPagamento(Protocol):
    def criar_assinatura(self, usuario_id: UUID, plano: str, email: str) -> CobrancaCriada: ...
    def cancelar(self, id_externo: str) -> None: ...
    def ler_evento(self, corpo: bytes, assinatura: str) -> "EventoPagamento": ...
```

- `ler_evento` **valida a assinatura do webhook antes de olhar o corpo**. Webhook sem validação é
  um endpoint que qualquer um usa para liberar Pro de graça; esse é o defeito que esta função
  existe para não ter.
- Fonte: documentação oficial do Mercado Pago (assinaturas e notificações). Citar as URLs nos
  docstrings; **nenhum endpoint inventado** — se a documentação não fechar, o campo vira lacuna
  declarada e a fatia registra a pendência em vez de chutar.
- Implementação real isolada em um arquivo; tudo o mais fala com o `Protocol`.

## 4. Passo 3 — dados e rotas

- Migração `0017_assinatura`: `assinatura` (`usuario_id`, `tier`, `status`, `id_externo`,
  `plano`, `inicio`, `fim_do_periodo`, `cancelada_em`) e `evento_pagamento` (append-only, o
  corpo bruto de cada webhook, para auditoria — dinheiro exige rastro).
- `dados/repositorio_assinatura.py` e `dados/repositorio_uso.py` (o uso do dia sai de
  `evento_estudo`, sem tabela nova — o mesmo princípio do diagnóstico da fatia 7: recomputar em
  vez de materializar).
- `api/assinatura.py`: `GET /assinar` (planos e preço), `POST /assinar` (cria e redireciona),
  `POST /webhooks/pagamento` (valida a assinatura, grava o evento, atualiza o estado),
  `POST /assinatura/cancelar` (um clique, com a data até quando o Pro vale).
- `api/conta.py`: `GET /conta/exportar` (JSON) e `POST /conta/excluir` (RF-23, Ruling 48), com
  confirmação explícita e cancelamento da assinatura antes.
- Os limites entram nos pontos que **servem** conteúdo (`api/questoes.py`, `api/diagnostico.py`),
  nunca no meio de uma gravação de resposta.

## 5. Passo 4 — tela

- `/assinar` com os dois preços da ADR-0015 e o que muda entre Free e Pro, em texto direto.
- Aviso de limite dentro da tela de questões, no lugar onde a próxima questão apareceria —
  com o que falta e o convite, sem modal.
- `Minha conta` mostra tier, status, até quando vale, e os dois botões da LGPD.
- Sem gateway configurado: nada disso aparece (Ruling 46).

## 6. Execução real (honesta)

Sem credencial, a execução real é: subir com o gateway **falso**, assinar, receber um webhook
simulado, virar Pro, cancelar e conferir que o Pro vale até o fim do período. Registrar no diário
que a rodada foi com gateway falso — e que a rodada com o Mercado Pago de verdade depende do
dono (ADR-0025, dois pontos não verificados).

## 7. Fora de escopo (vai para `docs/PENDENCIAS.md`)

- Taxas reais e elegibilidade de assinatura recorrente para conta PF (ADR-0025, P-02).
- Elite (fase 3) · boleto (fora por decisão) · Pix Automático na retentativa (regra 5.3 da
  fábrica) · nota fiscal e Carnê-Leão (obrigação do dono, não do código).

# Playbook de lançamento do AprovaOS

> O que é: a sequência do piloto até os 10 primeiros pagantes e os portões que decidem se o
> produto segue, pivota ou é arquivado. Quando ler: quando o piloto completo fechar os critérios
> de saída (PRD §6) e antes de qualquer convite fora do círculo da piloto. Números de corte:
> `docs/00-visao.md` §9 (aceitos pelo dono em 14/09/2026) — este playbook **não** cria métrica
> nova, só diz como chegar nelas.

## 0. O que trava o lançamento hoje (e é decisão do dono)

Nada aqui é opinião minha sobre prioridade: são atos que saem da máquina dele.

| trava | o que é | onde está registrado |
|---|---|---|
| **Nome e domínio** | "AprovaOS" é codinome; sem nome não há domínio, e sem domínio não há Search Console, e-mail transacional nem link para convidar | P-01 |
| **Deploy** | o produto roda em `127.0.0.1`; a piloto não consegue usar de onde ela está | ADR-0020/0030, lista final §1.2 |
| **Repositório remoto** | ~60 commits só nesta máquina, CI escrito e nunca executado | P-19, lista final §1.1 |
| **Billing** | sem provedor de pagamento não existe "pagante" para medir | fatia 12, lista final §1.3 |
| **Banca da piloto** | o edital real dela ainda não foi processado; o piloto mede o cano, não a pontaria | P-17 |

Enquanto essas cinco não caírem, o que dá para fazer é o **piloto n=1** — que é exatamente o
estágio do produto hoje.

## 1. Estágio 1 — piloto completo (n = 1, a Linda)

Critérios de saída já fixados no PRD §6, todos obrigatórios: ≥ 4 sessões/semana nas duas últimas
semanas · plano concluído em ≥ 50 % dos dias ativos · reporte de erro < 2 % e **zero afirmação de
lei sem fonte** encontrada por ela · ela explica o porquê de 3 decisões do agente sem ajuda ·
zero bug bloqueante por 7 dias · ela diz que continuaria sem o dono por perto.

**Duração mínima: 3 semanas com ≥ 15 dias ativos.** A regra que protege o piloto: se (1) ou (2)
falharem por duas semanas seguidas, **a causa vira a próxima fatia**, não uma feature nova. É a
armadilha clássica — responder a churn com escopo.

O que o dono faz nesse estágio: 5 perguntas por semana (mesmo formato da entrevista de 14/09) e
**nada de corrigir conteúdo na mão**. Conteúdo errado se corrige no pipeline; corrigir no banco
esconde o defeito que o piloto existe para achar.

## 2. Estágio 2 — os 10 primeiros pagantes (lado A)

Convite **direto**, não anúncio: 20–30 concurseiros do círculo dela e de grupos de
Telegram/WhatsApp, com **Pro grátis por 30 dias** e um onboarding acompanhado de 20 minutos.
Meta: **≥ 10 convertidos** ao fim dos 30 dias, em Pix anual (R$ 490) ou mensal.

Por que convite direto e não tráfego: a pesquisa da fábrica mede que **1,74 % das páginas novas
chegam ao top 10 em um ano** (`seo-01`) — SEO não entrega os 10 primeiros pagantes, entrega o
décimo primeiro em diante. O SEO começa **em paralelo** (playbook `05-playbook-seo.md`), sem
que nada dependa dele.

**A conversa de convite tem um roteiro curto e honesto:** o que o produto faz hoje, o que ele
**não** faz ainda, e que a pessoa vai ser cobrada em 30 dias se ficar. Nada de "período de
testes" que vira cobrança silenciosa — é o tipo de atalho que mata reputação num nicho pequeno
e falante.

## 3. A régua de tempo

| marco | quando | o que tem de estar no ar |
|---|---|---|
| **D-14** | duas semanas antes do convite | deploy, domínio, billing e o repositório remoto de pé; uma conta de teste pagando de verdade e cancelando |
| **D-7** | uma semana antes | página pública mínima, política de privacidade e termos, exportar/excluir dados (RF-23, LGPD) funcionando |
| **D0** | primeiro convite | 5 convites, não 30 — o primeiro lote existe para achar o que quebra |
| **D+3** | depois dos 5 primeiros | corrigir o que quebrou; só então os 25 restantes |
| **D+30** | 1º portão | **< 30 pagantes E D30 < 15 % → pivotar** exame/persona (não arquiva) |
| **D+60** | 2ª cobrança | sem tração (pagantes parados e renovação < 50 %) → **arquivar** |

Antes de qualquer arquivamento por churn: separar churn **involuntário**, retentativa de 10 dias
e oferecer Pix Automático (regra 5.3 da fábrica). Cancelamento por cartão recusado não é rejeição
do produto, e confundir os dois já arquivou produto bom.

## 4. O que se mede, onde, e o que se faz com o número

Todas as métricas do corte (visão §9) saem de `evento_estudo` e da tabela de assinatura — nenhuma
depende de ferramenta externa, o que é proposital: o produto mede a si mesmo.

| métrica | alvo | se ficar abaixo |
|---|---|---|
| Ativação (diagnóstico concluído ÷ cadastro) | ≥ 60 % | o gargalo é o onboarding, não o conteúdo — encurtar o diagnóstico antes de mexer em qualquer outra coisa |
| Plano concluído ÷ dias ativos | ≥ 50 % | o plano está grande demais para a rotina real; o check-in já tem o dado para provar |
| Sessões/semana | ≥ 4 | o agente não está "carregando" o aluno; olhar o alerta proativo e o fio da memória |
| D7 / D30 | ≥ 40 % / ≥ 20 % | portão do D+30 |
| Free → Pro | ≥ 3 % | mediana de mercado é 8 %, quartil inferior 2,5 % — abaixo de 3 % o problema é a proposta, não o preço |
| Custo LLM ÷ preço | ≤ 25 % | cortar geração, não cortar validação |
| Reporte de erro por questão | < 2 % | é a métrica de confiança; acima disso, para de crescer e conserta |
| NPS em 14 dias | ≥ 40 | conversar com os detratores um a um; n é pequeno, dá |

**O D+30 não mede SEO** — de propósito (visão §9).

## 5. Lado B (fase 2, só depois de tração no A)

Os alunos indicam quem os ensina. Três professores autônomos recebem o **corretor de discursivas
em lote** grátis por 30 dias — a dor tem preço medido no mercado de freelancer (R$ 3–20 por
peça). Meta: **10 assentos pagos em 60 dias**. Cursinhos pequenos, pelo dashboard de risco por
turma, só depois disso. Nada do lado B entra enquanto o lado A não passar o portão do D+30.

## 6. O que não se faz no lançamento

- **Não prometer aprovação** — em nenhuma peça, nem por implicação ("garanta sua vaga").
  Visão §6, fora de escopo para sempre.
- **Não comprar mídia** antes do portão do D+30: sem retenção provada, tráfego pago só acelera
  a perda.
- **Não abrir o lado B** antes do A.
- **Não responder queda de métrica com feature nova** — a causa vira fatia (regra do §1).

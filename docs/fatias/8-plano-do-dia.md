# Fatia 8 — Plano do dia + job noturno + check-in + porquê/discordar + distração: plano

> O que é: o plano da fatia 8 do PRD (`docs/02-produto.md` §6, linha "Plano do dia + job noturno +
> check-in + porquê/discordar + distração — F3.x"; abre o piloto completo, §6). Quando ler: antes
> de executar qualquer passo desta fatia e ao revisar o que foi feito; o diário fica em
> `8-execucao.md`.

**Ponto de partida:** 703 testes verdes. `perfil_estudo` (fatia 7: horas por dia da semana,
horário preferido, energia típica, concurso principal, consentimento de dados de rotina),
`cartao`/`cartoes_vencidos` (V4), `dossie_topico`/`aula` com trilha (fatias 4 e 6),
`topico_relacao` (equivalência entre vocabulários de edital, ADR-0041), `evento_estudo` append-only
com `dados` (JSON) e `confianca_declarada`, `motor.dossie.topicos_de_maior_peso` (peso medido),
`dominio.trilha.montar_trilha` (ordem por peso medido + histórico). `dev.db` da Ana: concurso
principal TJ-PR/AOCP com 137 questões publicáveis, 2 aulas publicadas, 4 dossiês.

## 1. O que a spec pede (contrato desta fatia)

Do enunciado do dono (não invento nada além disto — F3.5 "Alerta proativo" fica fora, §8):

1. **`plano_dia`** conforme o modelo de dados: `id, usuario_id, data, versao (1=noturno, 2+=check-
   in), gerado_em, energia, sono_h, tempo_min, modo (normal/descanso/semana_prova), porque_geral`.
   `bloco`: `id, plano_dia_id, ordem, tipo (aula/questoes/revisao/resumo/descanso), topico_id?,
   aula_id?, duracao_min, hora_sugerida, porque (NOT NULL), status
   (pendente/iniciado/concluido/pulado/trocado), iniciado_em, concluido_em`.
2. **Job noturno**: gera o plano do dia seguinte por usuário ativo, até 05h local, falha de um
   usuário não derruba o lote (CA explícito do PRD F3.1) — comando `argparse`+`main()`, idempotente
   (rodar duas vezes não duplica a versão 1 do mesmo dia).
3. **Check-in**: energia/sono/tempo → o plano se **reescreve** (versão 2+ do mesmo dia, nunca um
   plano novo); "descansar" é resposta válida (F3.2 CA: energia ≤ 2 ou sono < 5h → só revisão
   leve).
4. **Discordar em um toque**: trocar um bloco, motivo registrado como evento (F3.3/F3.4).
5. **Aviso de distração**: tempo no bloco ativo e troca de aba → aviso discreto sem bloqueio,
   grava `EventoEstudo(tipo="distracao")` (F3.6/S-05). Ilha de JS isolada (ADR-0019).

Princípios que mandam (visão §4, arquitetura §3): o LLM não decide o plano — regras decidem os
candidatos e o "porquê" já sai delas, sem precisar de LLM (a cota está esgotada; projetado para
funcionar sem modelo, ver §7); toda decisão grava `porque`; toda ação vira evento append-only;
"descansar" é recomendação válida, nunca um "fracasso".

## 2. Por que reaproveitar `dominio.trilha` e `motor.dossie.topicos_de_maior_peso`

O critério de "qual tópico entra no plano hoje" já existe e já é bom: `topicos_de_maior_peso`
(peso medido = nº de questões publicáveis, não peso declarado — P-39) + `estatisticas_topicos_
vistos` (o que ela já viu/errou) → `montar_trilha` ordena não-visto/fraco antes de dominado, mais
peso primeiro. O planejador do dia usa exatamente essa ordem para escolher, dentro do tempo
disponível, quais tópicos viram bloco de aula/questões — sem inventar um segundo critério de
priorização. Isso também resolve "tratar a escassez explicitamente" (§6): um tópico sem questão
publicável nem aula tem `questoes_publicaveis=0` e nenhuma aula — ele nunca vira candidato a
bloco, e a lacuna aparece no `porque_geral` quando o tempo sobra sem candidato para preenchê-lo.

## 3. Domínio puro — `dominio/plano.py`

Sem banco, sem `datetime.now`, sem `random`. Modelos e funções:

- `TipoBloco = Literal["aula","questoes","revisao","resumo","descanso"]`,
  `Modo = Literal["normal","descanso","semana_prova"]` (só `normal`/`descanso` têm comportamento
  próprio nesta fatia — `semana_prova`/F5.4 é fatia 10, §8).
- `TopicoParaPlano(BaseModel)`: `topico_id, slug, nome, materia, questoes_publicaveis: int,
  tem_aula: bool` — o que a trilha já sabe mais a flag de aula publicada (resolvida no
  repositório via `aula_publicada_do_topico`, que já atravessa `topico_relacao`).
- `CandidatoBloco(BaseModel)`: `tipo, topico_id: UUID | None, duracao_min: int, porque: str` — um
  bloco possível, ainda sem `ordem`/`hora_sugerida` (a função de montagem final atribui).
- `ResultadoPlano(BaseModel)`: `modo, energia: int | None, sono_h: float | None, tempo_min: int,
  porque_geral: str, blocos: list[CandidatoBloco]`.

**Constantes** (nenhum número solto fora daqui):
- `ENERGIA_MINIMA_PARA_ITEM_NOVO = 3` — abaixo disso, só revisão (F3.2 "energia ≤ 2").
- `SONO_MINIMO_H = 5.0` — abaixo disso, só revisão (F3.2 "sono < 5h").
- `MINUTOS_POR_CARTAO = 1.5`, `DURACAO_REVISAO_MIN_MIN = 10`, `DURACAO_REVISAO_MAX_MIN = 40` —
  bloco de revisão dimensionado pela quantidade de cartões vencidos, limitado por baixo (não
  gerar um bloco de 2 min) e por cima (não gerar 1h só de revisão).
- `DURACAO_QUESTOES_MIN = 20`, `DURACAO_AULA_MIN = 25` (mesma constante-espírito de
  `motor/aula.py --tempo-alvo-min 25`).
- `MAXIMO_BLOCOS = 5` (o protótipo mostra 5 blocos em 2h; teto para não gerar uma lista infinita
  quando `tempo_min` é grande).
- `TOPICOS_CANDIDATOS_MAX = 6` (profundidade da trilha considerada — bound de custo, não de
  produto: 6 tópicos não-dominados já cobrem qualquer `tempo_min` realista do piloto).

**`regime_do_dia(energia, sono_h, pediu_descanso) -> Literal["normal","so_revisao","descanso"]`**
— pura decisão de regime a partir dos três sinais do check-in (ou dos padrões do perfil, na
geração noturna): `pediu_descanso=True` vence tudo (a aluna pediu explicitamente); senão,
`energia is not None and energia <= 2` ou `sono_h is not None and sono_h < SONO_MINIMO_H` força
`"so_revisao"`; senão `"normal"`.

**`montar_candidatos(topicos, cartoes_vencidos_qtd, regime) -> list[CandidatoBloco]`** — a lista
ordenada de candidatos, **antes** de cortar pelo tempo disponível:
1. Se `cartoes_vencidos_qtd > 0`: um candidato `"revisao"` primeiro, sempre — `duracao_min =
   clamp(round(cartoes_vencidos_qtd * MINUTOS_POR_CARTAO), DURACAO_REVISAO_MIN_MIN,
   DURACAO_REVISAO_MAX_MIN)`, `porque` cita a quantidade ("N cartões venceram hoje — é o que
   está prestes a escapar da memória.").
2. Se `regime == "so_revisao"`: **para aqui** — nenhum candidato de aula/questões entra (é a
   regra dura do F3.2 CA). Sem cartão vencido nenhum, a lista fica vazia (vira "descansar", §4).
3. Senão (`regime == "normal"`): para cada tópico de `topicos` (já ordenado por `montar_trilha`,
   truncado a `TOPICOS_CANDIDATOS_MAX`, pulando `status == "dominado"`): se `tem_aula`, um
   candidato `"aula"` (`porque` cita o peso e o motivo da trilha); se `questoes_publicaveis > 0`,
   um candidato `"questoes"` (`porque` cita quantas publicáveis e a mesma razão da trilha).
   Tópico sem aula e sem questão nenhuma não gera candidato — é a escassez tratada por omissão,
   não por texto de erro.

**`selecionar_blocos(candidatos, tempo_min) -> list[CandidatoBloco]`** — greedy determinístico: o
candidato de revisão (se houver) sempre entra inteiro, mesmo estourando `tempo_min` levemente
(cartão vencido não espera); os demais entram na ordem enquanto a soma acumulada + a duração do
próximo ainda cabe em `tempo_min`, até `MAXIMO_BLOCOS`. Nunca corta um candidato ao meio.

**`montar_plano(topicos, cartoes_vencidos_qtd, tempo_min, energia, sono_h, pediu_descanso,
horario_preferido) -> ResultadoPlano`** — a função pública que a rota e o job chamam: aplica
`regime_do_dia` → `montar_candidatos` → `selecionar_blocos`; atribui `ordem` (1..N) e
`hora_sugerida` (relógio determinístico: início por `horario_preferido`
— `manha→06:30, noite→19:00, varia→08:00` — mais o acumulado de `duracao_min` dos blocos
anteriores); monta `porque_geral` (`motivo_geral_do_plano`, abaixo). Sem blocos (regime
`"so_revisao"` sem cartão, ou `"descanso"` explícito, ou `"normal"` sem candidato nenhum — a
escassez real do concurso de Cascavel) devolve `modo` coerente e um único candidato-fantasma? —
**não**: devolve `blocos=[]` e `porque_geral` explica por quê (nunca um bloco `"descanso"`
fictício preenchendo tempo que não existe: "descansar" é a ausência de blocos, não um bloco a
mais para cumprir tabela). `modo="descanso"` quando `pediu_descanso` ou (regime `"so_revisao"` e
`blocos=[]`); `modo="normal"` nos demais casos desta fatia.

**`motivo_geral_do_plano(regime, blocos, tempo_min, topicos) -> str`** — a frase final: cita
quantos blocos e quanto tempo total quando há blocos; quando vazio, explica a causa (energia/sono
baixos sem cartão vencido → "hoje é dia de descansar: sua energia está baixa e não há cartão
vencido — nada de questão nova"; pedido explícito → "você pediu para descansar hoje"; escassez de
conteúdo → "não há aula nem questão disponível para os tópicos que faltam no seu edital ainda" —
cita os tópicos, nunca esconde).

**`reajustar_no_checkin(...)`** — não é função nova: é o mesmo `montar_plano` chamado de novo com
os valores do check-in (energia/sono/tempo reais) no lugar dos padrões do perfil — "o check-in
reescreve o plano" é literalmente chamar a mesma função pura com entrada diferente, não um
algoritmo à parte. O repositório decide gravar como versão N+1 (§5).

**`escolher_substituto(candidatos_restantes, bloco_atual, blocos_do_plano) -> CandidatoBloco |
None`** — o "discordar" (F3.3/§6): dado o motivo (só para o evento — a troca em si não depende do
motivo escolhido, mesma decisão da fatia 7 para "Insistir"), devolve o primeiro candidato de
`candidatos_restantes` (mesma lista de `montar_candidatos`, recalculada) que ainda não está em
`blocos_do_plano` (por tópico+tipo) e cabe no tempo que sobra depois de remover `bloco_atual`;
`None` quando não há alternativa (a rota mantém o bloco e avisa, nunca quebra).

## 4. Motivos possíveis de "discordar" (F3.3 CA: 4 opções)

Fixos em `dominio/plano.py` como `Final[tuple[tuple[str,str], ...]] MOTIVOS_DISCORDAR` — mesmo
padrão de `OPCOES_HORARIO` em `dominio/rotina.py`: `("cansada", "Estou cansada agora")`,
`("sem_tempo", "Não tenho tempo para isso agora")`, `("ja_sei", "Já sei bem esse assunto")`,
`("prefiro_outro", "Prefiro estudar outra coisa")`. O valor gravado no evento é a chave; o rótulo
é só para o formulário.

## 5. Camada de dados

### 5.1 Modelos ORM (migração 0012)
`PlanoDia(ChaveUuid, Base)` (sem `Carimbos` — `gerado_em` já é o carimbo de criação; não há
`atualizado_em` porque uma nova versão é uma linha nova, nunca um update) e `Bloco(ChaveUuid,
Base)` (idem — `status`/`iniciado_em`/`concluido_em` mudam por ação da aluna, mas
`plano_dia`/`bloco` não ganham histórico próprio de edição: a versão do plano *é* o histórico).
`UniqueConstraint(usuario_id, data, versao)` em `plano_dia`; `CheckConstraint` de `modo` (3
valores), `tipo` e `status` de `bloco` (5 valores cada), mesma convenção das outras tabelas.
`hora_sugerida` como `sqlalchemy.Time` (nullable — só preenchido quando há bloco).

### 5.2 `dados/repositorio_plano.py`
- `usuarios_ativos(db) -> list[Usuario]`: usuário sem `excluido_em` com pelo menos uma
  `perfil_estudo` gravada (rotina configurada) — sem rotina não há `tempo_min` para planejar
  nada; é a definição honesta de "ativo" possível hoje (não existe `assinatura`/último acesso
  ainda). Registrado como definição provisória (§8).
- `_topicos_para_plano(db, edital_id, usuario_id) -> list[TopicoParaPlano]`: `motor.dossie.
  topicos_de_maior_peso` (limite generoso, ex. 20) → `dominio.trilha.montar_trilha` com
  `estatisticas_topicos_vistos` → para cada item não-dominado, resolve `tem_aula` via
  `aula_publicada_do_topico`; devolve na ordem da trilha (já é a ordem certa para
  `montar_candidatos` consumir).
- `gerar_ou_obter_plano_noturno(db, usuario, dia, agora) -> PlanoDia`: se já existe versão 1 para
  `(usuario, dia)`, devolve-a sem gerar de novo (idempotente — a segunda chamada do job, ou um
  `GET /hoje` antes do cron, não duplica); senão monta a entrada (perfil mais recente para
  `tempo_min`/`horario_preferido`/`energia_tipica` do dia da semana, `cartoes_vencidos` de
  `repositorio_cartao`, tópicos do edital do concurso principal) e chama `dominio.plano.
  montar_plano` com `energia=None, sono_h=None` (a geração noturna não tem check-in ainda — regra
  do check-in só entra quando ela responde) e grava `PlanoDia(versao=1)` + `Bloco`s.
- `registrar_checkin(db, usuario, dia, energia, sono_h, tempo_min, pediu_descanso, agora) ->
  PlanoDia`: lê a versão mais recente do dia (cria a versão 1 antes, se ainda não existir — um
  check-in sem plano noturno prévio ainda assim funciona, mesmo raciocínio de "trocar concurso
  principal começa diagnóstico novo" da fatia 7: nunca exigir uma pré-condição que quebra a
  tela), chama `montar_plano` com os valores reais do check-in, grava como `versao = max+1`,
  grava `EventoEstudo(tipo="checkin", energia=energia, dados={"sono_h":…, "tempo_min":…,
  "pediu_descanso":…})`.
- `iniciar_bloco`/`concluir_bloco`/`pular_bloco(db, usuario, bloco, agora) -> EventoEstudo`:
  atualiza `status`/`iniciado_em`/`concluido_em` e grava o evento correspondente
  (`bloco_iniciado`/`bloco_concluido`/`bloco_pulado`) com `dados={"bloco_id": str(bloco.id)}`.
- `discordar_bloco(db, usuario, plano, bloco, motivo, agora) -> tuple[Bloco | None, EventoEstudo]`:
  recalcula candidatos (mesma entrada de `gerar_ou_obter_plano_noturno`, mas para o plano atual em
  memória), chama `escolher_substituto`; grava `EventoEstudo(tipo="discordou",
  dados={"bloco_id":…, "motivo":…, "substituto_tipo":…})` sempre (mesmo sem substituto — o
  "discordo" em si já é sinal para o calibrador futuro); se há substituto, marca o bloco antigo
  `status="trocado"` e cria um `Bloco` novo na mesma posição (`ordem`), com `porque` do substituto
  prefixado por "Você disse: <motivo>. " (o porquê nunca desaparece, só ganha o motivo da aluna
  na frente — princípio "nunca esconder o porquê").

## 6. `motor/plano.py` — o job noturno

`gerar_plano_da_noite(db, dia) -> RelatorioPlanoNoturno` (contagem de sucesso/erro + lista de
`(usuario_email, status, motivo)`): itera `usuarios_ativos`, chama `gerar_ou_obter_plano_noturno`
por usuário dentro de um `try/except Exception`; uma falha grava `status="erro"` no relatório e
**segue para o próximo usuário** — é o CA explícito ("falha de um usuário não derruba o lote").
`main()` (`argparse`: `--data` opcional, padrão amanhã; `--dry-run`) abre o engine, roda, comita
por usuário (cada usuário em seu próprio commit — assim o erro de um não desfaz o sucesso dos
outros já processados nesta mesma rodada) e imprime o relatório. Sem agendador de verdade nesta
fatia (cron/systemd timer é infraestrutura de VPS — §8/PENDENCIAS); o comando roda por
`uv run python -m aprovaos.motor.plano` (mesmo padrão dos outros comandos do motor), a ser
agendado às 05h quando houver VPS.

## 7. Sem LLM — caminho determinístico é o produto, não o fallback

Todo `porque` (de bloco e geral) sai de `dominio/plano.py` por f-string com os números reais
(quantos cartões, quantas questões publicáveis, o motivo da trilha) — nenhuma chamada a agente
nesta fatia. Isso não é um "modo degradado": é a decisão do dono para esta fatia (cota do free
tier esgotada) e também é o que a arquitetura já previa (§3: "o LLM não decide o plano — escolhe
candidatos gerados por regras e escreve o porquê"); aqui as regras escrevem o porquê diretamente,
sem passar por um agente que reescreveria a mesma frase com palavras diferentes. Rota de melhoria
registrada em PENDENCIAS: um agente `tutor-porque` (Flash-Lite) poderia parafrasear
`porque`/`porque_geral` quando houver chave e teto — não fizemos, porque a frase determinística já
cumpre o contrato (F3.3 CA: "nenhuma decisão do agente sem campo `porque`") sem custo nem
dependência externa.

## 8. Fora desta fatia (registrado, não escondido)

- **F3.5 Alerta proativo** (`alerta`, "≤ 1/dia com ajuste proposto") — não está na lista explícita
  do dono para esta fatia e depende do `painel`/previsão da fatia 10; a tabela `alerta` não nasce
  aqui.
- **Modo `semana_prova`** (F5.4, D-7 liga geração desligada + revisão cirúrgica) — o valor existe
  no `CheckConstraint` (o esquema já contempla), mas o comportamento próprio é da fatia 10; nesta
  fatia `semana_prova` nunca é produzido por `montar_plano` (só `normal`/`descanso`).
  Combinar bloco: `"resumo"` só é gerado nos formatos de fatia futura — sem F4.7, nenhum candidato
  `"resumo"` nasce aqui (o `CheckConstraint` de `bloco.tipo` já contempla o valor).
- **Definição de "usuário ativo"** para o job (§5.2) é provisória: "tem rotina configurada" — sem
  `assinatura`/telemetria de último acesso ainda (billing é fatia 12); quando existir um sinal
  melhor, só `usuarios_ativos` muda.
- **`POST /api/eventos` genérico em lote** (arquitetura §7) — esta fatia cria só o endpoint
  específico de distração (`POST /api/distracao`, JSON, um evento por chamada); o endpoint
  genérico de lote para o PWA/offline fica para quando o PWA entrar (fase 6/ADR-0013).
- **Aviso de distração só no bloco ativo de `/hoje`**, não em `/topico/{slug}/questoes` — a
  entrevista cita as duas cenas ("travar numa questão" e "fugir de aba"); esta fatia cobre a
  segunda de forma geral (qualquer bloco em andamento) e a primeira por extensão (um bloco de
  questões parado é a aluna travada numa questão dele). Estender a ilha para dentro da tela de
  questão individual é um passo de front que não muda contrato de dado nenhum — registrado como
  possível refinamento, não como lacuna de CA (o evento `distracao` já é gravado, o CA não exige
  granularidade por questão).
- **Deploy em VPS** (ADR-0030, cron às 05h de verdade) — sai da máquina do dono, custa dinheiro;
  fica em `docs/PENDENCIAS.md` para ele decidir; o comando roda manualmente/local até lá.
- **Despublicação por reporte (calibrador)** — `repositorio_questao.registrar_reporte` cita "fatia
  8" no docstring antigo (escrito antes da tabela do PRD §6 fixar o calibrador na fatia **11**);
  não implementado aqui, por não constar da lista explícita desta tarefa — nota deixada em
  PENDENCIAS para não se perder.

## 9. Rotas e navegação

`api/plano.py`: `GET /hoje` (gera-ou-obtém a versão mais recente do dia; mostra check-in +
blocos), `POST /hoje/checkin` (formulário energia/sono/tempo/"quero descansar"),
`POST /hoje/bloco/{bloco_id}/iniciar|concluir|pular`, `POST /hoje/bloco/{bloco_id}/discordar`
(formulário com os 4 motivos). `api/eventos.py` (novo): `POST /api/distracao` (JSON
`{bloco_id}`), sem HTML. `base.html` ganha o link "Hoje" (primeiro item da navegação logada — é a
tela que a aluna abre todo dia, J2). Templates: `web/templates/hoje/pagina.html`,
`_blocos.html` (fragmento HTMX recarregado após checkin/ação de bloco), `_bloco.html` (um bloco).

## 10. Testes (TDD red-first)

- `tests/test_dominio_plano.py`: `regime_do_dia` nos três casos (pedido explícito vence; energia
  baixa; sono baixo; normal); `montar_candidatos` (revisão sempre primeiro; regime `so_revisao`
  para depois da revisão; tópico dominado nunca candidato; tópico sem aula/questão nunca gera
  candidato — escassez); `selecionar_blocos` (revisão entra mesmo estourando; teto de
  `MAXIMO_BLOCOS`; para quando não cabe mais); `montar_plano` (porquê de cada bloco não vazio;
  `porque_geral` explica escassez/descanso/pedido explícito; determinismo — duas chamadas iguais
  dão a mesma saída); `escolher_substituto` (acha alternativa que ainda não está no plano; `None`
  sem alternativa).
- `tests/test_modelos.py`: `PlanoDia`/`Bloco` — `UniqueConstraint`, `CheckConstraint` de
  `modo`/`tipo`/`status`.
- `tests/test_repositorio_plano.py`: `usuarios_ativos` (só quem tem perfil, exclui
  `excluido_em`); `gerar_ou_obter_plano_noturno` idempotente (chamar duas vezes não duplica);
  `registrar_checkin` cria versão 2 (não sobrescreve a 1), grava evento `checkin`;
  `iniciar/concluir/pular_bloco` grava o evento certo e atualiza status; `discordar_bloco` troca o
  bloco e grava o evento mesmo sem substituto.
- `tests/test_motor_plano.py`: `gerar_plano_da_noite` processa 2 usuários, um deles força exceção
  (mock/monkeypatch) — o outro ainda recebe plano; relatório lista os dois com status certo.
- `tests/test_rota_plano.py`: `GET /hoje` sem sessão redireciona; com perfil e sem plano ainda,
  gera na hora; `POST /hoje/checkin` reescreve (mesma `data`, `versao` incrementa); regras de
  energia/sono aplicadas fim a fim; `POST /hoje/bloco/{id}/iniciar|concluir|pular` muda status e
  grava evento; `POST /hoje/bloco/{id}/discordar` troca o bloco e mostra o motivo; contrato de
  erro `{codigo, mensagem, acao}` para bloco de outro usuário (404) e motivo fora da lista (400).
- `tests/test_rota_eventos.py`: `POST /api/distracao` grava o evento; sem sessão, 401/erro no
  formato padrão; nunca derruba a tela mesmo com payload incompleto (defensivo, 400 claro).

## 11. Diário

Vai para `docs/fatias/8-execucao.md`, com o plano do dia real gerado para a conta da Ana (dev.db)
colado inteiro — a régua desta fatia (visão §4: "nunca esconder o porquê"; PRD §6 métrica do
piloto completo).

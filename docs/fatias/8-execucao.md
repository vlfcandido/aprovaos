# Fatia 8 — Plano do dia + job noturno + check-in + porquê/discordar + distração: diário

> O que é: o que foi feito, medido, na fatia 8 — não o plano (`8-plano-do-dia.md`). Quando ler:
> para saber o que existe de verdade hoje, com que evidência.

## Estado de partida
Branch `main`, 703 testes verdes (fim da fatia 7 — diagnóstico + rotina). `perfil_estudo`,
`cartao`/FSRS, `dossie_topico`/`aula` com trilha, `topico_relacao` (equivalência de vocabulário),
`evento_estudo.dados` (JSON) já existiam. `dev.db` da Ana: TJ-PR/AOCP (99 tópicos, 137 questões
publicáveis, 2 aulas, 4 dossiês via `topico_relacao`) e Cascavel/Unioeste (0 questões). Sem
`perfil_estudo` gravado ainda (a fatia 7 restaurou o `dev.db` ao estado real depois da
demonstração, sem deixar rotina configurada).

## O que foi feito

### 1. Domínio puro (`dominio/plano.py`, novo)
`regime_do_dia` (dobrado em `montar_plano` como a variável `restrito`, ver §2 "achados" abaixo),
`montar_candidatos` (revisão de cartões vencidos sempre primeiro; regime restrito para depois
dela; tópico dominado ou sem aula/questão nunca é candidato), `selecionar_blocos` (greedy
determinístico pelo tempo disponível, revisão entra mesmo estourando o orçamento, teto de 5
blocos), `montar_plano` (a função pública — regime → candidatos → seleção → `ordem`/
`hora_sugerida` → `porque_geral`) e `escolher_substituto` (o "discordar": a próxima alternativa
que ainda não está no plano e cabe no tempo que sobra). `MOTIVOS_DISCORDAR` fixa as 4 opções
(F3.3 CA). Determinístico (nenhum `random`), sem banco, sem `datetime.now` interno — 23 testes
(`tests/test_dominio_plano.py`), incluindo os extremos: revisão isolada quando o regime é
restrito, escassez tratada por omissão (tópico sem aula/questão nunca é candidato), teto de
blocos, pedido explícito de descanso vencendo tudo (mesmo com cartão vencido).

### 2. Achado do plano: pedido de descanso não usa `montar_candidatos`
O plano (`8-plano-do-dia.md` §3) descrevia um `Regime` de três valores (`normal`/`so_revisao`/
`descanso`) passado para `montar_candidatos`. Na implementação, `pediu_descanso=True` **nunca**
chega a `montar_candidatos` — `montar_plano` corta direto para `blocos=[]` antes de calcular
qualquer candidato (`test_pedido_explicito_de_descanso_vence_tudo`: mesmo com 5 cartões vencidos,
o plano fica vazio). Isso é uma leitura diferente, e mais forte, do enunciado ("Hoje quero
descansar" da entrevista): a energia/sono baixos ainda deixam a revisão espaçada entrar (F3.2 CA
fala só em "não sugerir item novo"), mas o pedido explícito de descanso é a aluna dizendo "não
quero fazer nada hoje" — inclusive revisão. `montar_candidatos` ficou com um parâmetro `restrito:
bool` (não o enum de três valores do plano), cobrindo só o caso energia/sono; a simplificação está
documentada no docstring da função.

### 3. `evento_estudo` ganha `bloco_id`/`energia` como colunas reais
O modelo de dados (`docs/04-modelo-de-dados.md` §2) já nomeava `bloco_id`/`energia` desde a Fase
3; até aqui ninguém tinha `bloco` para apontar, então V5 gravou tudo em `dados` (JSON). Como esta
fatia cria `bloco`, promovi as duas para colunas reais (migração 0012, junto de `plano_dia`/
`bloco`) — mais barato de consultar (`EventoEstudo.bloco_id == x` em vez de scan em JSON, o
inverso da dívida registrada na P-46) e mais fiel ao contrato documentado. `hora_local` continua
sem coluna (exige o fuso do usuário, P-44, ainda aberta).

### 4. Camada de dados (`dados/repositorio_plano.py`, novo)
`usuarios_ativos` (sem `excluido_em`, com pelo menos uma `perfil_estudo` — definição provisória,
P-54 abaixo), `_topicos_para_plano` (reaproveita `contagem_por_topico` +
`estatisticas_topicos_vistos` + `dominio.trilha.montar_trilha` — **não** `motor.dossie
.topicos_de_maior_peso`, ver achado abaixo), `gerar_ou_obter_plano_noturno` (idempotente — versão
1 do dia), `registrar_checkin` (versão N+1, garante a versão 1 antes se não existir),
`iniciar_bloco`/`concluir_bloco`/`pular_bloco`, `discordar_bloco` (troca com evento sempre
gravado, mesmo sem substituto). `SemConcursoPrincipal` (nova exceção de domínio) cobre os dois
motivos de não conseguir planejar (sem rotina, sem concurso principal/edital).

**Achado de camada (desvio do plano):** o plano (§3) previa reaproveitar `motor.dossie
.topicos_de_maior_peso` a partir de `dados/repositorio_plano.py`. Isso inverteria a dependência
(`dados/` importando `motor/`, quando a arquitetura manda o contrário — `motor/` é quem importa
`dados/`). Em vez disso, `_topicos_para_plano` remonta a mesma entrada com funções já da camada
`dados/` (`repositorio_questao.contagem_por_topico`, `repositorio_fio_memoria
.estatisticas_topicos_vistos`) e `dominio.trilha.montar_trilha` — mesmo resultado, sem violar a
direção da dependência. Documentado no docstring da função.

### 5. `motor/plano.py` — o job noturno
`gerar_plano_da_noite(db, dia, commit=True)`: itera `usuarios_ativos`, cada usuário no seu
próprio `try/except`+commit/rollback — uma falha vira linha `"erro"` no relatório e o loop segue
(CA explícito do PRD F3.1). `SemConcursoPrincipal` tem status próprio (`"sem_rotina_ou_concurso"`)
porque não é uma falha do sistema. `main()` resolve `--data` (padrão amanhã) e `--dry-run`. 5
testes (`tests/test_motor_plano.py`), incluindo um usuário que quebra de propósito
(`monkeypatch`) sem impedir o outro de receber plano.

### 6. Rotas (`api/plano.py`, `api/eventos.py`, novos)
`GET /hoje` (gera-ou-obtém, idempotente), `POST /hoje/checkin`, `POST /hoje/bloco/{id}/
iniciar|concluir|pular`, `POST /hoje/bloco/{id}/discordar` — mesmo padrão de `api/rotina.py`:
toda rota devolve `hoje/pagina.html` inteira, `hx-select="#conteudo"` troca só o miolo, sem rota
de fragmento separada. `POST /api/distracao` (JSON, `api/eventos.py`) é deliberadamente menor que
o `/api/eventos` genérico em lote da arquitetura (§7) — um evento por chamada, sem fila offline
(P-57 abaixo). Templates `web/templates/hoje/pagina.html` (check-in + blocos, reaproveitando
classes já existentes — `.cartao`, `.mensagem--porque`, `.selo`, `.status`, `.acoes` — em vez de
importar classes do protótipo que não têm CSS de produção); acrescentei `.grid-3` (3 colunas,
usada também por `rotina/formulario.html`, que já a referenciava sem estilo) e `.cartao + .cartao`
(espaçamento) a `base.css`. Link "Hoje" na barra lateral, primeiro item da navegação logada. 12
testes de rota do plano + 4 de distração (`test_rota_plano.py`, `test_rota_eventos.py`),
incluindo o contrato `{codigo, mensagem, acao}` para energia inválida (400), motivo de discordar
inválido (400), bloco inexistente (404) e bloco de outro usuário (404 — isolamento por dono).

### 7. Aviso de distração (`web/static/js/distracao.js`, novo)
Ilha de JS vanilla isolada (ADR-0019): a cada 15 s, e ao voltar de aba escondida
(`visibilitychange`), confere se algum bloco com `data-bloco-iniciado` passou de 4 min (a frase
literal da entrevista da Ana); se sim, mostra o aviso discreto já presente no HTML (nasce
`hidden`) e grava `POST /api/distracao` uma vez por bloco. Nunca bloqueia (`alert`/`confirm`
nunca), nunca desabilita botão; se o script não carregar ou o `fetch` falhar (sessão expirada,
rede), os botões Iniciar/Concluir/Pular continuam funcionando normalmente. Sem teste automatizado
(o projeto não tem harness de JS — mesmo padrão de `atalhos-estudo.js`, que também não tem).

**Escopo reduzido, registrado (P-58):** o aviso cobre o bloco ativo da tela "Hoje" — não a tela
`/topico/{slug}/questoes` isolada. A entrevista cita duas cenas ("travar numa questão" e "fugir de
aba"); um bloco de questões parado cobre a primeira por extensão. Estender para dentro da tela de
questão individual é um passo de front puro (não muda `EventoEstudo(tipo="distracao")` nem o
contrato), fica para quando/se o piloto pedir granularidade maior.

## Testes e checagem
703 → **767 testes** (64 novos: 23 domínio, 11 repositório, 5 motor, 4 modelo, 12 rota do plano,
4 rota de eventos, 5 de ajuste em testes existentes — `test_modelos.py::test_tabelas` e as duas
linhas de `E501` corrigidas em `dominio/aula.py`, arquivo que outra sessão estava editando em
paralelo, ver nota abaixo). `bash scripts/checar.sh` verde: ruff check, ruff format, mypy
--strict, import sem efeito colateral, pytest (767 passed, 6 skipped).

**Nota sobre `dominio/aula.py`:** durante esta fatia, `aprovaos/dominio/aula.py` foi alterado em
paralelo (correção do validador de aula — texto_leigo simétrico ao denso, gate léxico, rejeição
de tag HTML — bem documentada, com referência a "correção crítica de 19/09/2026"), aparentemente
por outra sessão/processo trabalhando no mesmo repositório ao mesmo tempo. Não é trabalho desta
fatia; toquei o arquivo só para corrigir duas linhas que estouravam o limite de 100 colunas
(quebra mecânica, sem mudar lógica alguma), porque isso bloqueava `ruff check` para o repositório
inteiro e eu preciso do `checar.sh` verde para poder commitar. Registrado aqui para quem revisar
o diff desta fatia não estranhar um arquivo de aula aparecendo no meio de um commit sobre plano do
dia.

## Demonstração real contra `dev.db` (Ana) — em cópia, não no arquivo real
Mesmo cuidado da fatia 7: rodei a demonstração numa **cópia** de `dev.db` (`/tmp/demo-fatia8.db`,
migrada para 0012 e apagada ao final) — configurar uma rotina de verdade para a Ana sem ela ter
escolhido os valores seria inventar dado pessoal em nome dela, ainda que não seja uma resposta de
questão fabricada como a fatia 7 evitou. **O `dev.db` real não foi tocado** (confirmado por
`git status`/hash do arquivo antes e depois).

Passos, contra a cópia:
1. `alembic upgrade head` (0011 → 0012).
2. `salvar_perfil` com uma rotina hipotética (2h seg–qui, 1h sex, 3h sáb, 0h dom; horário manhã;
   energia média) e concurso principal = TJ-PR/AOCP (137 questões publicáveis, 2 aulas, 4
   dossiês via `topico_relacao`).
3. `cartoes_vencidos`: **0** (a Ana nunca errou uma questão no histórico real dela — 19 eventos,
   todos de diagnóstico/estudo sem cartão vencido hoje).
4. `gerar_ou_obter_plano_noturno` para segunda-feira (2h no perfil acima) — **o plano real**:

```
=== PlanoDia 2026-09-21 (versão 1) — modo=normal — tempo_min=120 ===
PORQUE GERAL: Hoje: 5 blocos, 110 min no total, dentro dos 120 min que você tem.

[1] 06:30:00 · 25 min · aula — 4 Direitos e garantias fundamentais [...] (Noções de Direito Constitucional)
    porquê: Aula de 4 Direitos e garantias fundamentais [...] (Noções de Direito Constitucional):
    8 questões publicáveis; ainda não estudado.
    status: pendente
[2] 06:55:00 · 20 min · questoes — 4 Direitos e garantias fundamentais [...] (Noções de Direito Constitucional)
    porquê: Questões de 4 Direitos e garantias fundamentais [...] (Noções de Direito Constitucional):
    8 questões publicáveis; ainda não estudado.
    status: pendente
[3] 07:15:00 · 20 min · questoes — 6 Organização dos Poderes [...] (Noções de Direito Constitucional)
    porquê: Questões de 6 Organização dos Poderes [...]: 8 questões publicáveis; ainda não estudado.
    status: pendente
[4] 07:35:00 · 20 min · questoes — Provas [...] (Noções de Direito Processual Penal)
    porquê: Questões de Provas [...]: 7 questões publicáveis; ainda não estudado.
    status: pendente
[5] 07:55:00 · 25 min · aula — 6 Improbidade administrativa (Lei nº 8.429/1992) (Noções de Direito Administrativo)
    porquê: Aula de 6 Improbidade administrativa [...]: acertou 2 de 4 — 6 questões publicáveis,
    ainda vale revisar.
    status: pendente
```

(Texto de `nome` do tópico truncado com `[...]` aqui só para caber no diário — o dado real é o
texto original do edital, comprido por natureza; a tela mostra por inteiro.) Note o bloco 5: o
"acertou 2 de 4" vem do histórico real dela (`estatisticas_topicos_vistos`), não é texto
genérico — é a trilha (fatia 6) reconhecendo que ela já viu esse tópico e ainda vale revisar.

5. `registrar_checkin` com energia 2, sono 4,5h, tempo 90 min (simulando um dia ruim): o plano
   virou **versão 2, modo="descanso", blocos=[]**, com
   `porque_geral="Hoje é dia de descansar: sua energia ou seu sono não pedem item novo, e não há
   cartão vencido para revisar."` — a regra F3.2 CA (energia ≤ 2 ou sono < 5h → só revisão leve)
   funcionando fim a fim contra dado real, e "descansar" saindo como recomendação, não como erro.

## O que ficou fora (registrado em `docs/PENDENCIAS.md`)
P-54 (F3.5 alerta proativo, depende do painel da fatia 10), P-55 (`modo="semana_prova"` sem
comportamento próprio ainda), P-56 (`usuarios_ativos` com definição provisória), P-57 (`/api/
eventos` genérico em lote, fase 6/PWA), P-58 (distração só no bloco de `/hoje`), P-59 (deploy/cron
de verdade em VPS, ADR-0030, decisão e custo do dono) — todas com o motivo por extenso em
`PENDENCIAS.md`. Também esclarecidas ali as referências antigas a "fatia 8" em P-25/P-32/P-34,
escritas antes de a tabela do PRD §6 fixar a ordem real das fatias (calibrador é fatia 11, coleta
agendada é outra frente).

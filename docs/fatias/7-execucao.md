# Fatia 7 — Diagnóstico adaptativo + rotina: diário de execução
> O que é: o que foi feito, medido, na fatia 7 — não o plano (`7-diagnostico-e-rotina.md`).
> Quando ler: para saber o que existe de verdade hoje, com que evidência.

## Estado de partida
Branch `main`, 656 testes verdes (fim da fatia "trilha + aulas" + correção estrutural
`topico_relacao`, ADR-0041). `dev.db` da Linda com dois concursos: TJ-PR/AOCP (99 tópicos, 137
questões publicáveis) e Cascavel/Unioeste (36 tópicos, edital real dela — P-17 — mas 0 questões
publicáveis hoje, porque a reclassificação do passo 16 da V3 moveu a base inteira para o
vocabulário do TJ-PR, P-31). Reaproveitado sem mudança: `evento_estudo.dados` (JSON, V5),
`repositorio_questao.proxima_questao`/`contagem_por_topico`/`registrar_resposta`,
`repositorio_cartao.registrar_erro`, o padrão `_cartao_questao.html`/`_resultado.html`.

## O que foi feito

### 1. Motor do diagnóstico (`dominio/diagnostico.py`, novo, puro)
`calcular_estado`: `margem = 50/(1+peso_total)`, peso 2 por resposta com certeza e 1 por dúvida —
decresce com a **quantidade/confiança**, nunca com o resultado (errar com certeza fecha a margem
tão rápido quanto acertar com certeza; `estimativa_pct` é onde o acerto entra). `LIMITE_MARGEM=8`
(o "±8" da spec), `MAXIMO_ITENS=30`. `materias_elegiveis`/`ordenar_candidatos`: só matérias com
pelo menos um tópico com questão publicável entram; entre as elegíveis, a de maior margem vem
primeiro (reduz a variância da mais incerta); dentro da matéria, o tópico menos respondido até
agora (cobertura desempata). `sinais_por_topico`: por tópico, `sem_questao` (nunca teve
publicável)/`sem_dado` (tem, mas não testado)/`a_estudar`/`dominado` (testado, ≥ 80 % estimado) —
é o estado que a fatia 8 vai consumir, sem tabela nova (ver §3). `motivo_geral`: a frase final,
citando a matéria que fechou com menos itens e a que exigiu mais, e avisando as matérias sem
questão. Determinístico (nenhum `random`): mais forte que "reprodutível com seed" — não precisa
de seed nenhuma. 20 testes (`tests/test_dominio_diagnostico.py`), incluindo os extremos pedidos
(acerta tudo, erra tudo, alterna confiança/acerto) e o determinismo (duas chamadas idênticas dão
a mesma ordem de candidatos).

**Por que não a fórmula literal da ADR-0022:** ela pondera pela discriminação estimada dos itens
(calibrador) — `questao.discriminacao_est` é `None` em 100 % da base (confirmado por `select`); o
calibrador é fatia 11, sem produtor ainda. A fórmula usa os três sinais reais desta fatia (acerto,
confiança, cobertura), documentado no plano §2. Quando a calibração existir, só `calcular_estado`
muda — o contrato (`EstadoAgregado`) fica.

### 2. Rotina (`dominio/rotina.py` + `perfil_estudo`)
`DadosRotina` (Pydantic v2): sete dias obrigatórios (0–16h cada), `horario_preferido` em
`{manha, noite, varia}`, `energia_tipica` em `{alta, media, baixa}`, `data_alvo` opcional,
`concurso_principal_id` opcional. Migração 0011 (Alembic): `perfil_estudo` (append-only por
`versao`, sem `atualizado_em` — mesmo motivo de `EventoEstudo` não ter) e `usuario.
consentimento_dados_rotina`/`_em`/`_versao` (LGPD R-01 — energia/sono é dado sensível por
cautela; `salvar_perfil` só é chamado pela rota depois de confirmar o checkbox marcado).
`dados/repositorio_perfil.py::salvar_perfil`/`perfil_atual`. 6 testes de modelo
(`test_modelos.py`) + 6 de repositório (`test_repositorio_perfil.py`).

**P-23 resolvida:** `repositorio_edital.concurso_principal` agora olha primeiro a `perfil_estudo`
mais recente do usuário do tenant e só cai para "o último edital subido" (premissa A da V2) sem
perfil, ou com `concurso_principal_id` que não pertence mais ao tenant (defensivo). Testado com
os dois caminhos (`test_repositorio_perfil.py`).

### 3. Estado por tópico sem tabela nova
`dados/repositorio_diagnostico.py::topicos_do_diagnostico`/`respostas_diagnostico`: lê
`evento_estudo` marcado `dados={"diagnostico": True}` (mesmo padrão de `bloco_topico_id` do fio
da memória, filtro em Python sobre o JSON — P-46). Nenhuma tabela nova guarda "o estado do
diagnóstico": cada `GET /diagnostico` recomputa tudo a partir dos eventos já gravados — reiniciar
o navegador não perde progresso; trocar o concurso principal (rotina) começa um diagnóstico novo
(zero eventos marcados para o novo edital). `painel` materializado (curva/previsão) continua
explicitamente da fatia 10 — criá-lo aqui seria antecipar escopo alheio.

### 4. Rotas (`api/diagnostico.py`, `api/rotina.py`, novos)
`GET/POST /diagnostico` reaproveita `contexto_questao`/`contexto_evento`/
`questoes/_cartao_questao.html`/`questoes/_resultado.html` de `api/questoes.py` — as cinco
funções privadas (`_contexto_questao`, `_contexto_evento`, `_alternativas_ordenadas`,
`_dispositivos_por_chave` → `mapa_dispositivos_por_chave`, `_afirmacoes_para_exibir`) foram
promovidas a públicas (mesmo comportamento, só sem `_` na frente) porque agora dois módulos as
usam — mesmo espírito de `/revisar`: "responder no diagnóstico é, na prática, responder a questão
de novo". "Insistir" (o "discordar" desta fatia — F3.3 completo é fatia 8): `?insistir=<matéria>`
força mais um item numa matéria já fechada, sempre respeitando o teto de 30. `GET/POST /rotina`:
formulário com os sete campos de horas, horário, energia, data-alvo, `<select>` de concurso
principal e o checkbox de consentimento — sem ele marcado, 400 com a mensagem e nada é salvo.
Templates novos: `web/templates/diagnostico/{andamento,resultado}.html`,
`web/templates/rotina/formulario.html`; `base.html` ganhou os links "Diagnóstico"/"Rotina";
`conta/conta.html` trocou a frase de "próximas fatias" pelos links reais. 6 testes de rota do
diagnóstico + 4 de rotina (`test_rota_diagnostico.py`, `test_rota_rotina.py`), incluindo o
contrato `{codigo, mensagem, acao}` para `confianca` ausente (400) e tópico fora do edital (404).

## Testes e checagem
656 → **703 testes** (37 novos: 20 domínio diagnóstico, 6 domínio rotina, 6+3 modelo/repositório
perfil, 2 repositório diagnóstico, 6 rota diagnóstico, 4 rota rotina — a diferença de contagem
vem de ajustes nos testes existentes de `test_modelos.py`/`test_repositorio_edital.py`).
`bash scripts/checar.sh` verde (ruff check, ruff format, mypy --strict, import sem efeito
colateral, pytest).

## Demonstração real contra `dev.db` (Linda)
Migração 0011 aplicada (`alembic upgrade head`). Login via sessão aberta diretamente pelo
repositório (`abrir_sessao`) — sem senha em texto — contra o `TestClient` apontando para
`backend/dev.db` de verdade (não um banco de teste).

1. **`GET /diagnostico`** (concurso principal ainda por heurística → TJ-PR, 137 publicáveis):
   primeiro item veio de "Noções de Direito Administrativo" com o porquê: *"é a matéria com a
   maior margem de incerteza ainda aberta (±50 pontos) entre as que têm questão disponível.
   Dentro dela, [tópico] é o tópico com menos itens respondidos até agora."*
2. Respondendo em sequência (padrão sintético: acerta 3 de 4, alternando certeza/dúvida), o
   diagnóstico **parou em 26 itens** (nunca chegou ao teto de 30) com o motivo:
   > "Parei em 26 itens: sua margem em Noções de Direito Administrativo fechou cedo (3 itens) e
   > em Noções de Direito Civil levou mais (6 itens). Sem questão suficiente na base ainda para:
   > LÍNGUA PORTUGUESA, Língua Portuguesa, Matemática/Raciocínio Lógico."

   Por matéria: Direito Administrativo 100 % ± 7,14 (3 itens); Direito Civil 16,7 % ± 7,14 (6
   itens); Direito Constitucional 100 % ± 7,14 (3); Direito Penal 85,7 % ± 6,25 (4); Direito
   Processual Civil 100 % ± 7,14 (5); Direito Processual Penal 100 % ± 7,14 (4); **Informática
   100 % ± 16,67 (1 item)** — este último nunca fechou (só havia 1 questão publicável no tópico):
   o caso real de "amostra pequena, sem fingir precisão" que a tarefa pedia. Português/Matemática
   (0 questões publicáveis) apareceram como "sem questão na base", nunca com uma estimativa
   inventada. O link "Insistir" apareceu nas matérias fechadas.
3. **P-23 ao vivo:** `POST /rotina` trocando o concurso principal para Cascavel/Unioeste (o
   edital real da Linda) — `GET /diagnostico` imediatamente passou a mostrar **0 itens**, motivo
   *"Parei em 0 itens: não sobrou mais questão nova para as matérias em aberto. Sem questão
   suficiente na base ainda para: DIREITO ADMINISTRATIVO, DIREITO CIVIL, ... RACIOCÍNIO LÓGICO."*
   — nenhuma tela quebrou, nenhuma cobertura fingida.

**Decisão sobre `dev.db`:** as respostas do passo 2 são sintéticas (fabricadas para provar o
motor, não a Linda estudando de verdade) — ao contrário das fatias anteriores (V2–6), que
deixaram saídas reais de pipeline (aulas, questões curadas) em `dev.db`, aqui deixar 26 eventos de
"resposta" inventados em nome dela poluiria o histórico que a fatia 8 (plano do dia) vai ler.
Depois da demonstração, `dev.db` foi restaurado ao estado anterior (histórico real dela: 19
eventos, intacto) e a migração 0011 foi reaplicada sobre essa cópia — o esquema fica pronto, os
dados sintéticos não ficam. Script da demonstração descartado (não faz parte do produto).

## O que ficou fora (registrado em PENDENCIAS/no plano)
Discriminação real por item (calibrador, fatia 11); `painel` materializado com curva/previsão
(fatia 10); F3.3 completo — o tutor que reescreve o plano quando ela discorda de um bloco (fatia
8; aqui só o "Insistir" determinístico do diagnóstico); F1.3 completo — concursos acompanhados,
split N/M (fatia 1b); grade de horas "clicável" do protótipo (implementada como sete campos
numéricos simples, sem JS novo — contrato de dados idêntico, front mais simples).

# Fatia 6 — Trilha + aulas em texto: plano de implementação
> O que é: o plano da fatia 6 do PRD (`docs/02-produto.md` §6, linha "Trilha + aulas em texto (fio
> (a), popover de lei, mnemônicos, grifos) — `gerador-aula` + validador"). Quando ler: antes de
> executar qualquer passo desta fatia e ao revisar o que foi feito; o diário fica em
> `6-execucao.md`.

**Ponto de partida:** 579 testes verdes, fundação jurídica completa (fatia 4): `dominio/dossie.py`
(`montar_dossie`), 4 dossiês reais gravados (`dir-pro-civ-05-recursos-apelacao`,
`dir-pro-civ-03-atos-processuais`, `dir-adm-06-improbidade-administrativa`,
`dir-con-02-direitos-garantias`), `dominio/justificativa.py` (validador mecânico de justificativa
— o mesmo princípio desta fatia aplica à aula), `agentes/gerador_de_justificativa.py` (o padrão de
agente ADK a seguir), `dominio/fio_memoria.py` + `dados/repositorio_fio_memoria.py`
(`estatisticas_topicos_vistos` — histórico real por tópico de um usuário, reaproveitado aqui para
o fio (a)), popover de lei já implementado em `web/templates/questoes/_resultado.html`.

## 1. Contrato da `Aula` (skill `gerador-de-aula` + `docs/04-modelo-de-dados.md` §3)
Campos do modelo de dados: `id, dossie_id, dossie_versao, topico_id, versao, texto_denso,
texto_leigo, audio_url?, citacoes (JSON), relacionados (JSON), validada_em?, publicada`. A skill
pede dois campos a mais que o modelo de dados ainda não lista — `como_a_banca_cobra` e
`lacunas_declaradas` — extensão pelo mesmo padrão já usado em `dna_concurso`/`questao` (colunas
JSON além do mínimo documentado, decisão registrada aqui em vez de reescrever o modelo de dados
inteiro). Acrescento também `mnemonico` (JSON nullable) — ver §5.

`dominio/aula.py` (novo, puro): `RelacionadoEntrada`, `QuestaoParaAula`, `EntradaGeradorAula`
(o que vai para o agente: `topico_slug`, `fontes` — reaproveita `dominio.dossie.FonteDossie` —,
`relacionados`, `questoes_como_banca`, `tempo_alvo_min`), `CitacaoAula`, `RelacionadoAula`,
`ComoABancaCobra`, `MnemonicoAula`, `ConteudoAula` (o que o agente devolve) e
`verificar_aula(conteudo, *, fontes, relacionados_permitidos, origens_permitidas,
tempo_alvo_min) -> VeredictoAula` — o validador mecânico, no espírito de
`dominio.justificativa.verificar_justificativa_*`.

### O que o validador confere mecanicamente
1. Cada `citacoes[i].fonte` é um `F-n` que existe no dossiê; `citacoes[i].canonica` normalizado
   (`dominio.citacao.normalizar_citacao_para_comparacao`) bate com o `citacao_canonica` daquela
   fonte; `citacoes[i].trecho` existe **literalmente** (substring) no `trecho` da fonte — o mesmo
   teste de `_motivos_da_afirmacao`.
2. `citacoes[i].frase_da_aula` existe literalmente em `texto_denso` (a frase citada é a frase que
   está no texto, não uma paráfrase).
3. Todo marcador `{{...}}` de `texto_denso` normaliza para uma `citacoes[*].canonica` conhecida —
   marcador órfão reprova.
4. Nenhum item de `lacunas_declaradas` aparece como marcador `{{...}}` em `texto_denso`
   (exclusão mútua da skill).
5. `relacionados[i].topico_slug` ⊆ o conjunto dado na entrada; `relacionados[i].trecho` é
   **igual** ao `trecho_do_dossie_relacionado` daquele tópico na entrada (não pode inventar
   trecho de um tópico relacionado).
6. `como_a_banca_cobra[i].origem` ⊆ o conjunto de origens reais dado na entrada (uma questão
   publicada de verdade, nunca inventada).
7. `len(texto_leigo.split()) <= 0.4 * len(texto_denso.split())`.
8. `len(texto_denso.split())` dentro de `tempo_alvo_min * 36 ± 20 %`.
9. Se `mnemonico` vier preenchido: mesmo teste do item 1 aplicado a `mnemonico.dispositivo`/
   `trecho_que_decide` — mnemônico gerado passa pelo mesmo validador que citações (linha 6 do
   PRD: "mnemônico é conteúdo gerado → passa pelo validador como o resto").

O que fica **fora** do mecânico, por ser semântico (a mesma fronteira que
`gerador-de-justificativa` já aceita): "nenhuma oração da frase que não esteja no trecho" — o
prompt pede isso explicitamente e o revisor humano (o dono, nesta fatia com n pequeno) confere a
aula colada na resposta final antes de decidir se o padrão está bom.

## 2. Fio da memória (a): de onde vêm os `relacionados`
`dados.repositorio_fio_memoria.estatisticas_topicos_vistos(db, usuario_id, edital_id)` já agrega
exatamente o que a skill pede (`ultima_visita`, `total_respostas`, `erros`) — reaproveitado sem
mudança. `dominio/aula.py::escolher_relacionados(topico_atual_id, estatisticas, trechos_por_topico,
slugs_por_topico, agora, quantidade=1)` filtra às estatísticas cujo tópico **tem dossiê** (só
esses têm `trecho_do_dossie_relacionado` para citar) e reaproveita
`dominio.fio_memoria.escolher_para_intercalar` para o ranking (erro mais recente → tempo sem ver),
convertendo o resultado em `RelacionadoEntrada` com o trecho real (primeira fonte do dossiê do
tópico relacionado — F1) e o placar real (`acertos = total - erros`, `dias_atras` a partir de
`ultima_visita`). Sem tópico relacionado com dossiê → `relacionados` vazio na entrada, e a aula
declara isso (a skill não obriga fio (a); só o inclui quando há dado real).

Usuária real: `linda.piloto@exemplo.com` já tem `evento_estudo` de verdade no `dev.db` (histórico
de 9 tópicos, de fatias/demos anteriores) — o fio (a) desta fatia usa o histórico dela de
verdade, não um fixture inventado.

## 3. "Como a banca cobra": só questões reais publicadas
`motor/aula.py` busca até N (padrão 5) `Questao` publicáveis do tópico
(`questoes_publicaveis_do_topico`, já existe) e monta `QuestaoParaAula{origem, enunciado}` com
`origem` no formato `"<banca> <ano> <orgão em minúsculas> item <numero_item>"` — a mesma string
vai para a entrada do agente e para o conjunto `origens_permitidas` do validador; o agente só pode
citar uma dessas em `como_a_banca_cobra[i].origem` (regra 6 do validador). Sem questão publicável
no tópico → `questoes_como_banca` vazia e `como_a_banca_cobra` sai vazio (a aula não inventa).

## 4. Agente `gerador-de-aula` (`agentes/gerador_de_aula.py`)
Mesmo molde de `agentes/gerador_de_justificativa.py`: `Protocol GeradorDeAula.gerar(entrada) ->
ConteudoAula`, `carregar_prompt()`/`montar_mensagem()`/`interpretar_resposta()`,
`criar_gerador_adk(config, registrar_chamada)` — `LlmAgent` (`include_contents="none"`, JSON
mode, sem `output_schema` pela mesma razão de `additionalProperties`), prompt em
`agentes/prompts/gerador-de-aula.md`. `Configuracoes.modelo_aula` novo campo (`gemini-3.6-flash`
— escrever uma aula é raciocínio, mesmo corte de `modelo_justificativa`/`modelo_dna`, não
"simple data processing" como a classificação). Documentado em `.env.example`.

## 5. Mnemônicos: cabem, gerado na mesma chamada (sem custo extra de cota)
A skill `gerador-de-aula` não pede mnemônico, mas a linha 6 do PRD pede. Em vez de uma segunda
chamada de LLM por tópico (cota é o recurso mais escasso desta fatia — free tier, poucas
requisições/dia), o prompt do `gerador-de-aula` pede **opcionalmente** um `mnemonico` no mesmo
JSON de saída (`MnemonicoAula{texto, dispositivo, trecho_que_decide}` — mesma forma de uma
`Afirmacao` de justificativa), validado pela mesma regra 9 acima e persistido em `mnemonico`
(`tipo="gerado"`, `topico_id`, `validado_em` só quando aprovado). Reprovado ou ausente: a aula
publica normalmente, sem mnemônico — nunca bloqueia a aula por causa dele.

## 6. Grifos: fora desta fatia (declarado, não escondido)
A tabela `anotacao` do modelo de dados não tem `Model` ORM, migração nem rota ainda; reancoragem
por `texto_ancora` quando o conteúdo muda é lógica própria (comparar/realinhar posição depois de
uma nova versão da aula), do tamanho de uma fatia inteira, não de um apêndice desta. Registrado em
`docs/PENDENCIAS.md` (P-50) em vez de entregar um "grifo" que só salva texto sem reancoragem — dar
uma versão capenga violaria a própria regra do `gerador-de-aula` ("melhor faltar do que mentir",
aplicada aqui a feature, não a citação).

## 7. Trilha
`dominio/trilha.py` (novo, puro): `TopicoParaTrilha{topico_id, slug, nome, materia,
questoes_publicaveis}` (mesmo formato de `motor.dossie.TopicoComPeso`, sem acoplar `dominio` a
`motor`) e `montar_trilha(topicos, vistos: dict[UUID, EstatisticaTopicoVisto]) -> list[ItemTrilha]`.
Critério (defensável, escrito — não há peso declarado por tópico no edital, P-39):
- **não visto**: `status="nao_visto"`, entra na frente.
- **fraco**: visto e `acertos/total < 0,7` (ou visto com menos de 3 respostas — dado insuficiente
  para "dominado"), entra na frente.
- **dominado**: visto, `total >= 3` e `acertos/total >= 0,7` — vai para o fim da trilha.

Ordenação: `(0 se não-visto/fraco senão 1, -questoes_publicaveis, slug)` — dentro do mesmo grupo
de prioridade, o tópico mais cobrado (peso medido) vem primeiro; nunca reordena por "achismo" de
dificuldade. `motivo` de cada item cita os números reais (peso medido; placar, se visto).

`GET /concurso/{id}/trilha`: monta a trilha do edital do concurso (reaproveita
`motor.dossie.topicos_de_maior_peso` com `limite` alto — todos os tópicos do edital — e
`estatisticas_topicos_vistos`), mostra status + link para `/topico/{slug}/aula` (quando existe
aula publicada — `aula_publicada_do_topico`) e para `/topico/{slug}/questoes`.

## 8. Popover de lei na aula: reaproveitar, não refazer
`web/templates/_macros.html` (novo, pequeno): extrai o `{% macro citacao(af) %}` que hoje vive
inline em `_resultado.html` para um arquivo importável — `_resultado.html` passa a `{% import
"_macros.html" as macros %}` e chamar `macros.citacao(af)` nos 3 pontos onde já chamava `citacao
(af)` (mesmo HTML, mesmo `<details>`/`<summary>`, zero mudança visual). A tela de aula
(`web/templates/aula/ver.html`, novo) usa a mesma macro: `texto_denso`/`texto_leigo` renderizados
como parágrafos com os marcadores `{{canonica}}` substituídos por uma nota de rodapé numerada
(`dominio.aula.renderizar_com_notas(texto, citacoes) -> (html, notas)` — função pura, testada) e
a lista de notas ao final, cada uma como `macros.citacao(af)` com o trecho literal e a URL — a
mesma experiência de popover sem JS que já existe no resultado da questão.

## 9. Comando `motor/aula.py`
`gerar_aula_topico(db, topico_slug, gerador, usuario_id, edital_id, *, tempo_alvo_min=25,
limite_relacionados=1, limite_questoes_banca=5, hoje=None) -> RelatorioAula` — mesmo desenho de
`justificar_topico`/`construir_dossie`: sem dossiê → relatório "sem dossiê", nunca `KeyError` cru;
sem IA → "sem_ia"; reprovada → motivos do validador, nada gravado; aprovada → `salvar_aula`
grava com `publicada=True`. `main()` (argparse: `--topico` repetível, `--usuario-email`,
`--edital-id`, `--tempo-alvo-min`, `--dry-run`) resolve o usuário por e-mail
(`repositorio_conta.buscar_por_email`) — é assim que a rodada real vai chamar o comando contra a
conta de verdade da Ana (`linda.piloto@exemplo.com`).

## 10. Geração real (cota)
Free tier: poucas requisições/dia por modelo, e `gemini-3.6-flash` já foi usado hoje por
`gerador-de-justificativa` (26 chamadas registradas em `traco` nesta data, achado ao conferir
antes de rodar) — **gerar poucas e boas**: no máximo 2 tópicos nesta rodada
(`dir-adm-06-improbidade-administrativa`, o mais visto/errado por ela — melhor material para o
fio (a) — e `dir-con-02-direitos-garantias`, o dossiê sem lacuna, para mostrar o caso limpo). O
comando para limpo em `LimiteDeTaxaExcedido`/erro do provedor (mesmo padrão de `motor.justificar`
— vira item "reprovada: erro na IA", não derruba o processo) e o relatório final é o que entra no
diário, com o número real de aulas geradas e aprovadas.

## 11. O que fica de fora (declarado)
- Áudio (Pro) — linha 6 do PRD já exclui explicitamente até o piloto mostrar uso.
- Grifos/anotações — §6 acima, `docs/PENDENCIAS.md` P-50.
- Julgado (ADI/RE/REsp) além de súmula — a fundação jurídica (fatia 4) já não cobre isso
  (ADR-0039); esta fatia não estende.
- Regeneração automática da aula quando o dossiê muda (o modelo de dados prevê `dossie_versao`
  para isso) — o comando é manual nesta fatia; reprocessar quando a versão do dossiê mudar é
  trabalho do job noturno (fatia 8), que ainda não existe.

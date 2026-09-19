# Modelo de dados
> O que é: as entidades do AprovaOS (aluno, conteúdo, Motor, cobrança), suas chaves e relações, o que é append-only, o que é versionado, e as regras de retenção/LGPD por tabela. Quando ler: antes de escrever qualquer modelo SQLAlchemy ou migração (Fase 5, fatia 1 em diante); ao adicionar campo que toque dado pessoal.

Convenções: Postgres 16 + pgvector; SQLAlchemy 2.0 com `DeclarativeBase` e `Mapped[...]`; chaves `uuid` (v7 quando disponível, para ordenação por tempo); `criado_em`/`atualizado_em` em tudo; nomes em português, singular, snake_case; enums como `str` com `CHECK`. Fronteiras (API, agentes) usam Pydantic v2 — os modelos ORM nunca saem da camada `dados/`. Tenant: `tenant_id` em toda tabela do aluno (PF = um tenant por pessoa; organização na fase 2).

## 1. Mapa

```
tenant ──< usuario ──< assinatura                    concurso ──< edital ──< topico_edital >── topico
   │          │                                          │            │                          │  ▲
   │          ├──< perfil_estudo (versionado)            └── dna_concurso (versionado, JSON)      │  │ topico_relacao (grafo)
   │          ├──< plano_dia ──< bloco                                                            │
   │          ├──< evento_estudo (append-only)     fonte ──< documento ──< questao ──< alternativa │
   │          ├──< cartao (FSRS)                                   │          ▲ origem            │
   │          ├──< anotacao                                        │      dossie_topico ──< aula  │
   │          ├──< radar_preferencia                               │            (versionado)      │
   │          └──< alerta                          dispositivo_legal ──< citacao ─── (aula|questao|dossie)
   │                                               glossario · mnemonico · traco · reporte_erro · evento_cobranca
```

## 2. Aluno

| tabela | campos principais | regras |
|---|---|---|
| `tenant` | id, tipo (`pf`/`org`), nome | PF criado no cadastro |
| `usuario` | id, tenant_id, email (único), senha_hash (argon2), google_sub?, criado_em, **consentimento_dados_rotina** (bool, data, versão do texto), excluido_em | e-mail+senha ou Google; exclusão = anonimização em 30 dias (LGPD) |
| `assinatura` | id, usuario_id, tier (`free`/`pro`), periodicidade, status, inicio, fim, gateway, id_externo, cancelada_em | uma ativa por usuário; cancelamento em um clique grava `cancelada_em` e mantém acesso até `fim` |
| `perfil_estudo` | id, usuario_id, **versao**, horas_por_dia_semana (JSON 7 valores), horario_preferido, energia_tipica, data_alvo, concurso_principal_id, concursos_acompanhados (JSON), criado_em | append-only por versão; plano lê a última |
| `radar_preferencia` | usuario_id, areas, niveis, bancas, ufs, salario_min, alerta_ativo | alerta ≤ 1/dia |
| `plano_dia` | id, usuario_id, data, **versao** (1 = noturno, 2+ = check-in), gerado_em, energia, sono_h, tempo_min, modo (`normal`/`descanso`/`semana_prova`), porque_geral | por (usuario, data, versao) |
| `bloco` | id, plano_dia_id, ordem, tipo (`aula`/`questoes`/`revisao`/`resumo`/`descanso`), topico_id?, aula_id?, duracao_min, hora_sugerida, **porque** (NOT NULL), status (`pendente`/`iniciado`/`concluido`/`pulado`/`trocado`), iniciado_em, concluido_em | `porque` obrigatório por contrato |
| `evento_estudo` | id, usuario_id, ocorrido_em, tipo (`resposta`/`checkin`/`bloco_iniciado`/`bloco_concluido`/`bloco_pulado`/`discordou`/`distracao`/`revisao_cartao`/`aula_lida`/`resumo_aberto`/`reporte`), questao_id?, bloco_id?, cartao_id?, acertou?, resposta?, tempo_ms?, **confianca_declarada** (`certeza`/`duvida`)?, energia?, hora_local, dados (JSON) | **append-only**; nunca UPDATE/DELETE; índice (usuario, ocorrido_em) e (questao, ocorrido_em) | **V3 (Alembic 0003):** a tabela nasce de fato nesta fatia — só os tipos `resposta` e `reporte` são gravados por enquanto (premissa M do plano V3); os demais tipos do enum ficam reservados para as fatias que os produzirem (checkin → fatia 8, distração → F3.6, etc.), sem linha nenhuma até lá. `registrar_resposta`/`registrar_reporte` (`dados/repositorio_questao.py`) são os únicos gravadores hoje.
| `cartao` | id, usuario_id, questao_id?, topico_id, frente, verso, mnemonico_id?, origem (`auto_erro`/`manual`), estado FSRS (`stability`, `difficulty`, `due`, `reps`, `lapses`, `last_review`) | estado serializado do `fsrs.Card`; agenda = `due` |
| `anotacao` | id, usuario_id, conteudo_tipo (`aula`/`questao`/`dossie`), conteudo_id, **conteudo_versao**, inicio, fim, texto_ancora (≤ 300 chars), nota, cor, criado_em, reancorada_em?, perdida (bool) | reancoragem por `texto_ancora` quando `conteudo_versao` muda; se não achar, `perdida=true` e a UI avisa |
| `alerta` | id, usuario_id, data, tipo, mensagem, ajuste_proposto (JSON), aceito_em?, porque | ≤ 1 por (usuario, data) — UNIQUE |
| `painel` (materializada) | usuario_id, atualizado_em, proficiencia_por_materia (JSON com ±), curva_atual, curva_necessaria, previsao (nota_lo, nota_hi, prob, prob_lo, prob_hi, confianca), padroes_erro (JSON, só n ≥ 30) | recomputada por evento (função pura em `dominio/`) |

## 3. Concurso e conteúdo

| tabela | campos principais | regras |
|---|---|---|
| `concurso` | id, orgao, cargo, banca, uf, nivel, area, status (`previsto`/`aberto`/`andamento`/`encerrado`), inscricoes_ate, data_prova, vagas, salario, fonte_id, id_externo (ex.: `TCU_25_AUFC`), combina_perfil (calculado) | espelha o radar |
| `edital` | id, concurso_id, versao, publicado_em, documento_id, retificacao_de? | cada retificação é nova versão |
| `topico` | id, materia, nome, slug, pai_id? | vocabulário canônico por adapter |
| `topico_edital` | edital_id, topico_id, peso_edital, texto_original | o "edital verticalizado" é esta tabela × eventos | **V3 (18/09/2026):** ganhou a coluna `grupo` (`str \| None`), preenchida por `registrar_edital` a partir do que o parser do PDF já devolvia (ex.: `"CONHECIMENTOS ESPECÍFICOS"`) — fecha a P-26 (a página do concurso mostrava o slug em Title Case, sem acento, em vez do texto real do edital).
| `topico_relacao` | de_id, para_id, peso, origem (`edital`/`dossie`/`coocorrencia`) | grafo do fio da memória e da propagação |
| `dna_concurso` | id, concurso_id, versao, gerado_em, pesos (JSON topico→%), incidencia (JSON), estilo (JSON), pegadinhas (JSON com prova/ano), regra_correcao (JSON), corte (lo, hi), fontes (JSON) | cache por concurso; versionado | **V2 (17/09/2026):** nasceu como `conteudo` (JSON inteiro do contrato da skill) + `origem` (`ia`/`regras`), `modelo`, `motivo_fallback`, `versao`, `gerado_em` — ADR-0032. `concurso` ganhou `tenant_id` nullable (avulso × catálogo); `topico_edital` ganhou `ordem`.
| `fonte` | id, nome, tipo, url, politica (JSON: frequência, user_agent, login=false), ultima_varredura, proxima | de `knowledge/fontes.yaml` | **V3 (18/09/2026):** primeira linha real é a Cebraspe (`id_externo="cebraspe"`, `nome`, `url_lista`, `status`). `politica`/`ultima_varredura`/`proxima` nasceram nullable e **sem consumidor**: a política de coleta de verdade (ADR-0035) vive hoje em `knowledge/fontes.yaml` e em constantes do módulo do coletor, não nessas colunas — pendência P-32.
| `documento` | id, fonte_id, tipo (`prova`/`gabarito`/`edital`/`lei`/`informativo`), url_origem, hash, baixado_em, caminho, metadados (JSON) | PDF original guardado; nunca republicado sem atribuição | **V3:** primeiras linhas reais são prova/gabarito da Cebraspe, gravadas pelo coletor (`motor/coletar.py`); `caminho` relativo a `knowledge/provas/<eventoURL>/`, `metadados` com `descricao`/`evento`/`url_origem`; dedup por `hash` (rodar o coletor de novo não duplica).
| `questao` | id, adapter, banca, tipo_item, enunciado, texto_apoio?, gabarito, justificativa_certo, justificativa_errado, topico_id, dificuldade_est, discriminacao_est, **origem** (JSON: orgao, cargo, ano, numero_item, tipo_caderno, url_prova, documento_id) **ou** `inedita=true`, validada_em?, validador_versao, publicada (bool), despublicada_em?, embedding (vector 768) | publicada só com `validada_em`; original exibe origem; inédita marcada | **V3 (Alembic 0003, ADR-0033):** ganhou `comando`, `texto_apoio_itens` (JSON), `regra_prova` (JSON — fonte da convenção de anulação, ex.: "convenção Cebraspe C/E"), `topico_confianca` (`alta`/`media`/`baixa`), `topico_evidencia`, `gabarito_status` (enum `str` com **5** valores: `definitivo`, `preliminar`, `anulado`, `alterado`, `sem_gabarito` — o 5º não existe em `EntradaGabarito.status` do domínio, é próprio da coluna, para o item sem entrada nenhuma no gabarito), `publicavel` (bool — o gate da ADR-0033, distinto de `publicada`, que é o que a tela efetivamente mostrou) e `motivo_nao_publicavel`, `documento_id` (FK), `hash_dedup` (único — evita gravar a mesma questão duas vezes entre cadernos, inclusive entre cargos com prova idêntica). `questao` é **pool de conteúdo global**: não tem `tenant_id` nem `edital_id` — o mesmo registro é servido a qualquer edital cujo `topico_edital` aponte para o mesmo `topico_id` (ADR-0033). `alternativa` e `embedding` continuam sem uso nesta fatia (A–E e busca semântica ficam para V3b e fatia 1b+).
| `alternativa` | questao_id, letra, texto, correta, justificativa | só para A–E | **V3:** tabela criada vazia pela migração 0003 (Alembic); nenhuma linha gravada — a V3 é só Cebraspe C/E (premissa J do plano). Fica pronta para a V3b (múltipla escolha A–E, formato dominante no mercado — P-30; banca real da Linda ainda desconhecida, P-17).
| `dossie_topico` | id, topico_id, **versao**, gerado_em, conteudo (markdown), fontes (JSON URL+trecho), bibliografia (JSON referência), log_buscas (JSON), validado_em?, substituido_por? | versionado; mudança de lei cria versão e marca dependentes |
| `aula` | id, dossie_id, dossie_versao, topico_id, versao, texto_denso, texto_leigo, audio_url?, citacoes (JSON), relacionados (JSON topico_id→trecho), validada_em?, publicada | regenerada quando dossiê muda |
| `dispositivo_legal` | id, citacao_canonica (ex.: `CF/88 art. 71 X`), norma, artigo, inciso?, paragrafo?, texto, vigente (bool), fonte_url, atualizado_em | índice do popover; texto de lei não é protegido (pesquisa §9) |
| `citacao` | conteudo_tipo, conteudo_id, dispositivo_id, posicao | 100 % das citações de aula/questão resolvem |
| `glossario` | termo, materia?, definicao, fonte | popover de termos |
| `mnemonico` | id, topico_id, tipo (`consagrado`/`gerado`/`do_aluno`), texto, origem?, usuario_id?, validado_em? | o do aluno prevalece na UI |
| `reporte_erro` | id, usuario_id, conteudo_tipo, conteudo_id, motivo, status (`aberto`/`analise`/`corrigido`/`improcedente`), resolvido_em | fila do calibrador; status visível | **V3 (Alembic 0003):** primeira gravadora é `registrar_reporte` (rota `POST /questoes/{id}/reportar`); todo reporte nasce `status="aberto"`. Efeito hoje (premissa H do plano V3): a questão reportada sai da fila **só de quem reportou** (via `EventoEstudo(tipo="reporte")` cruzado em `proxima_questao`) — despublicar para todo mundo é do calibrador, fatia 8, que ainda não lê esta tabela.
| `calibracao` | id, questao_id, data, dificuldade_real, discriminacao, n, acao (`manter`/`sinalizar`/`despublicar`) | diário |

## 4. Operação

| tabela | campos | regras |
|---|---|---|
| `traco` | id, iniciado_em, duracao_ms, usuario_id?, agente, modelo, tokens_in, tokens_out, custo_brl, tier, resultado, erro?, span_pai? | fonte de custos; retenção 90 dias |
| `evento_cobranca` | id, gateway, id_externo, tipo, payload (JSON), recebido_em, processado_em | webhooks idempotentes por `id_externo` |
| `push_inscricao` | usuario_id, endpoint, chaves, criado_em | Web Push |

## 5. Dado pessoal, sensível e retenção (RISCOS R-01)
- **Dado de rotina/energia/sono** (`plano_dia.energia/sono_h`, `evento_estudo.energia`, `perfil_estudo.energia_tipica`): tratado como **sensível por cautela** (tangencia saúde); coleta só com `usuario.consentimento_dados_rotina`; usado só para o plano e os padrões de erro do próprio aluno; nunca em ranking, nunca para terceiros; agregado só com n ≥ 30.
- **Minimização**: sem CPF, sem endereço, sem telefone no MVP; pagamento fica no gateway (guardamos só `id_externo`).
- **Exportar**: JSON de todas as tabelas do aluno em ≤ 24 h. **Excluir**: anonimização em 30 dias (eventos ficam sem `usuario_id` para calibração agregada; `anotacao`, `cartao`, `perfil` apagados).
- **Retenção**: `traco` 90 dias; `evento_cobranca` 5 anos (fiscal); `evento_estudo` enquanto a conta existir.

## 6. Esboço SQLAlchemy 2.0 (padrão a seguir)

```python
"""Modelos ORM do aluno — apenas mapeamento; nenhuma sessão criada no import."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import ForeignKey, String, Boolean, DateTime, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    """Base declarativa do projeto (SQLAlchemy 2.0)."""

class EventoEstudo(Base):
    """Fato imutável do estudo: uma resposta, um check-in, um bloco pulado. Nunca é atualizado."""
    __tablename__ = "evento_estudo"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuario.id"), index=True)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tipo: Mapped[str] = mapped_column(String(32))
    questao_id: Mapped[UUID | None] = mapped_column(ForeignKey("questao.id"))
    acertou: Mapped[bool | None] = mapped_column(Boolean)
    tempo_ms: Mapped[int | None]
    confianca_declarada: Mapped[str | None] = mapped_column(String(8))
    __table_args__ = (Index("ix_evento_usuario_tempo", "usuario_id", "ocorrido_em"),)
```

Migrações: Alembic, uma por fatia, revisáveis; nenhuma migração destrutiva sem ADR.

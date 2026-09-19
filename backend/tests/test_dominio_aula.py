# O que é: testes do contrato de aula e do validador mecânico — `dominio/aula.py` (fatia 6:
# trilha e aulas em texto). Cobre `verificar_aula` (as regras mecânicas do §1 do plano
# `docs/fatias/6-trilha-e-aulas.md`), `escolher_relacionados` (fio da memória (a), reaproveitando
# o ranking de `dominio.fio_memoria`) e `renderizar_com_notas` (popover na tela da aula). Quando
# ler: ao mudar o contrato da `Aula` ou o que o validador aceita/reprova.
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from aprovaos.dominio.aula import (
    CitacaoAula,
    ComoABancaCobra,
    ConteudoAula,
    MnemonicoAula,
    RelacionadoAula,
    escolher_relacionados,
    renderizar_com_notas,
    verificar_aula,
)
from aprovaos.dominio.dossie import FonteDossie
from aprovaos.dominio.fio_memoria import EstatisticaTopicoVisto

AGORA = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

FONTE_1 = FonteDossie(
    id="F1",
    tipo="norma",
    norma="lei-8429-1992",
    artigo="1",
    citacao_canonica="Lei 8.429/1992 art. 1",
    url="https://planalto.gov.br/lei-8429",
    trecho="Art. 1º Os atos de improbidade administrativa [...] serão punidos na forma desta lei.",
)
FONTE_2 = FonteDossie(
    id="F2",
    tipo="sumula",
    citacao_canonica="STJ Súmula 651",
    url="https://scon.stj.jus.br/sumula-651",
    trecho="A demissão do agente público não depende de condenação judicial.",
)
FONTES = [FONTE_1, FONTE_2]


def _conteudo(**sobrescritas: object) -> ConteudoAula:
    base: dict[str, object] = dict(
        texto_denso=(
            "A improbidade administrativa é punida na forma da lei, conforme prevê o "
            "dispositivo legal específico da matéria {{Lei 8.429/1992 art. 1}}. Além disso, "
            "a demissão administrativa do agente público independe de condenação judicial "
            "prévia, segundo o entendimento consolidado do tribunal {{STJ Súmula 651}}."
        ),
        texto_leigo=(
            "A lei pune quem comete improbidade. A demissão não depende de condenação "
            "judicial antes."
        ),
        citacoes=[
            CitacaoAula(
                canonica="Lei 8.429/1992 art. 1",
                fonte="F1",
                trecho="serão punidos na forma desta lei",
                frase_da_aula="A improbidade administrativa é punida na forma da lei",
            ),
            CitacaoAula(
                canonica="STJ Súmula 651",
                fonte="F2",
                trecho="A demissão do agente público não depende de condenação judicial.",
                frase_da_aula=(
                    "a demissão administrativa do agente público independe de condenação "
                    "judicial prévia"
                ),
            ),
        ],
        relacionados=[],
        como_a_banca_cobra=[],
        lacunas_declaradas=[],
        mnemonico=None,
    )
    base.update(sobrescritas)
    return ConteudoAula.model_validate(base)


def test_aula_bem_formada_e_aprovada() -> None:
    veredito = verificar_aula(
        _conteudo(),
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert veredito.aprovado, veredito.motivos


def test_trecho_que_nao_existe_na_fonte_reprova() -> None:
    conteudo = _conteudo(
        citacoes=[
            CitacaoAula(
                canonica="Lei 8.429/1992 art. 1",
                fonte="F1",
                trecho="trecho que não existe na fonte",
                frase_da_aula="A improbidade administrativa é punida na forma da lei",
            ),
            CitacaoAula(
                canonica="STJ Súmula 651",
                fonte="F2",
                trecho="A demissão do agente público não depende de condenação judicial.",
                frase_da_aula=(
                    "a demissão administrativa do agente público independe de condenação "
                    "judicial prévia"
                ),
            ),
        ]
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("literalmente" in m for m in veredito.motivos)


def test_fonte_inexistente_reprova() -> None:
    conteudo = _conteudo(
        citacoes=[
            CitacaoAula(
                canonica="Lei 8.429/1992 art. 1",
                fonte="F9",
                trecho="serão punidos na forma desta lei",
                frase_da_aula="A improbidade administrativa é punida na forma da lei",
            ),
        ],
        texto_denso=(
            "A improbidade administrativa é punida na forma da lei {{Lei 8.429/1992 art. 1}}."
        ),
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("F9" in m for m in veredito.motivos)


def test_canonica_que_nao_bate_com_a_fonte_reprova() -> None:
    conteudo = _conteudo(
        citacoes=[
            CitacaoAula(
                canonica="Lei 8.429/1992 art. 2",  # F1 é o art. 1, não o art. 2
                fonte="F1",
                trecho="serão punidos na forma desta lei",
                frase_da_aula="A improbidade administrativa é punida na forma da lei",
            ),
        ],
        texto_denso=(
            "A improbidade administrativa é punida na forma da lei {{Lei 8.429/1992 art. 2}}."
        ),
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("não corresponde" in m for m in veredito.motivos)


def test_frase_da_aula_que_nao_esta_no_texto_denso_reprova() -> None:
    conteudo = _conteudo(
        citacoes=[
            CitacaoAula(
                canonica="Lei 8.429/1992 art. 1",
                fonte="F1",
                trecho="serão punidos na forma desta lei",
                frase_da_aula="frase que não existe no texto denso",
            ),
        ],
        texto_denso=(
            "A improbidade administrativa é punida na forma da lei {{Lei 8.429/1992 art. 1}}."
        ),
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("frase_da_aula" in m for m in veredito.motivos)


def test_marcador_sem_citacao_correspondente_reprova() -> None:
    conteudo = _conteudo(
        texto_denso=(
            "A improbidade administrativa é punida na forma da lei {{Lei 8.429/1992 art. 1}} "
            "{{CF/88 art. 37}}."
        ),
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("marcador" in m for m in veredito.motivos)


def test_lacuna_declarada_e_citada_ao_mesmo_tempo_reprova() -> None:
    conteudo = _conteudo(
        texto_denso=(
            "A improbidade administrativa é punida na forma da lei {{Lei 8.429/1992 art. 1}} "
            "e o particular responde nos termos {{Lei 8.429/1992 art. 3}}."
        ),
        lacunas_declaradas=["Lei 8.429/1992 art. 3"],
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("lacuna" in m for m in veredito.motivos)


def test_relacionado_fora_do_permitido_reprova() -> None:
    conteudo = _conteudo(
        relacionados=[
            RelacionadoAula(
                topico_slug="topico-nao-permitido",
                onde="§2",
                frase="Isso conversa com o que você viu.",
                trecho="trecho qualquer",
            )
        ]
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos={"outro-topico"},
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("relacionado" in m for m in veredito.motivos)


def test_relacionado_com_trecho_diferente_do_dado_reprova() -> None:
    conteudo = _conteudo(
        relacionados=[
            RelacionadoAula(
                topico_slug="dir-pro-civ-03-atos-processuais",
                onde="§2",
                frase="Isso conversa com o que você viu.",
                trecho="um trecho inventado, não o que veio na entrada",
            )
        ]
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos={"dir-pro-civ-03-atos-processuais"},
        origens_permitidas=set(),
        tempo_alvo_min=1,
        trechos_relacionados_esperados={
            "dir-pro-civ-03-atos-processuais": "o trecho real do dossiê relacionado"
        },
    )
    assert not veredito.aprovado
    assert any("trecho" in m for m in veredito.motivos)


def test_como_a_banca_cobra_com_origem_inventada_reprova() -> None:
    conteudo = _conteudo(
        como_a_banca_cobra=[
            ComoABancaCobra(origem="cebraspe 2099 orgao-fake item 1", o_que_testou="qualquer")
        ]
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas={"cebraspe 2024 tj-pa item 57"},
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("origem" in m for m in veredito.motivos)


def test_texto_leigo_maior_que_40_por_cento_do_denso_reprova() -> None:
    conteudo = _conteudo(
        texto_leigo="A lei pune improbidade e a demissão não depende de nada. " * 4
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("leigo" in m for m in veredito.motivos)


def test_tamanho_fora_da_faixa_do_tempo_alvo_reprova() -> None:
    veredito = verificar_aula(
        _conteudo(),
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=25,  # 25*36 = 900 palavras esperadas; o texto de teste tem poucas dezenas
    )
    assert not veredito.aprovado
    assert any("tamanho" in m for m in veredito.motivos)


def test_mnemonico_com_trecho_que_nao_existe_na_fonte_reprova() -> None:
    conteudo = _conteudo(
        mnemonico=MnemonicoAula(
            texto="PID: Punição Independe de Demissão judicial",
            dispositivo="STJ Súmula 651",
            trecho_que_decide="trecho inventado que não está na súmula",
        )
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("mnemônico" in m for m in veredito.motivos)


def test_marcador_inexistente_no_texto_leigo_reprova() -> None:
    """C1 (correção crítica 19/09/2026): o leigo é validado com o mesmo rigor do denso — um
    marcador que não existe em `citacoes` reprova mesmo aparecendo só no `texto_leigo`."""
    conteudo = _conteudo(
        texto_leigo=(
            "A lei pune quem comete improbidade {{Lei 8.429/1992 art. 12}}. A demissão não "
            "depende de condenação judicial antes."
        ),
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("marcador" in m and "art. 12" in m for m in veredito.motivos)


def test_lacuna_declarada_e_citada_no_texto_leigo_reprova() -> None:
    """C1: a regra de lacuna também vale para o `texto_leigo`, não só para o denso."""
    conteudo = _conteudo(
        texto_leigo=(
            "A lei pune quem comete improbidade. O particular responde nos termos "
            "{{Lei 8.429/1992 art. 3}}."
        ),
        lacunas_declaradas=["Lei 8.429/1992 art. 3"],
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("lacuna" in m for m in veredito.motivos)


def test_frase_afirmativa_sem_citacao_reprova() -> None:
    """C2 (decisão registrada na correção crítica de 19/09/2026): gate léxico — frase com
    gatilho normativo (aqui, "compete") sem `{{citação}}` reprova, mesmo com `citacoes=[]`. É
    a troca consciente entre honestidade e falso positivo ocasional."""
    conteudo = _conteudo(
        citacoes=[],
        texto_denso=(
            "Compete ao Tribunal de Contas da União fiscalizar as contas dos administradores "
            "públicos responsáveis por dinheiro, bens e valores da União."
        ),
        texto_leigo="O tribunal fiscaliza o dinheiro público.",
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("Compete ao Tribunal" in m for m in veredito.motivos)


def test_frase_com_gatilho_normativo_e_citacao_aprova() -> None:
    """C2: a mesma frase, com `{{citação}}` dentro dela, não reprova pelo gate léxico."""
    conteudo = _conteudo(
        texto_denso=(
            "Compete a todos observar a lei, pois os atos de improbidade serão punidos na "
            "forma desta lei {{Lei 8.429/1992 art. 1}}. A demissão do agente público "
            "independe de condenação judicial prévia, segundo o entendimento consolidado do "
            "tribunal {{STJ Súmula 651}}."
        ),
        texto_leigo=(
            "A lei pune quem faz isso errado. A demissão não depende de decisão da justiça antes."
        ),
        citacoes=[
            CitacaoAula(
                canonica="Lei 8.429/1992 art. 1",
                fonte="F1",
                trecho="serão punidos na forma desta lei",
                frase_da_aula=(
                    "Compete a todos observar a lei, pois os atos de improbidade serão "
                    "punidos na forma desta lei"
                ),
            ),
            CitacaoAula(
                canonica="STJ Súmula 651",
                fonte="F2",
                trecho="A demissão do agente público não depende de condenação judicial.",
                frase_da_aula=(
                    "A demissão do agente público independe de condenação judicial prévia"
                ),
            ),
        ],
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert veredito.aprovado, veredito.motivos


def test_tag_html_no_texto_reprova() -> None:
    """C3: nenhuma tag HTML deveria sair do gerador — a tela agora escapa, mas o validador
    também reprova para não deixar passar o hábito."""
    conteudo = _conteudo(
        texto_denso=(
            "A improbidade administrativa é punida na forma da lei {{Lei 8.429/1992 art. 1}}. "
            "<img src=x onerror=roubar()> tentativa de estilizar o texto da aula."
        ),
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert not veredito.aprovado
    assert any("tag" in m.lower() for m in veredito.motivos)


def test_mnemonico_com_trecho_real_aprova() -> None:
    conteudo = _conteudo(
        mnemonico=MnemonicoAula(
            texto="PID: Punição Independe de Demissão judicial",
            dispositivo="STJ Súmula 651",
            trecho_que_decide="não depende de condenação judicial",
        )
    )
    veredito = verificar_aula(
        conteudo,
        fontes=FONTES,
        relacionados_permitidos=set(),
        origens_permitidas=set(),
        tempo_alvo_min=1,
    )
    assert veredito.aprovado, veredito.motivos


def _estatistica(
    topico_id: UUID, *, dias: int, total: int, erros: int, dias_erro: int | None = None
) -> EstatisticaTopicoVisto:
    ultimo_erro_em = None
    if erros > 0:
        ultimo_erro_em = AGORA - timedelta(days=dias_erro if dias_erro is not None else dias)
    return EstatisticaTopicoVisto(
        topico_id=topico_id,
        topico_nome="Tópico visto",
        materia="Direito Processual Civil",
        ultima_visita=AGORA - timedelta(days=dias),
        total_respostas=total,
        erros=erros,
        ultimo_erro_em=ultimo_erro_em,
    )


def test_escolher_relacionados_so_considera_topico_com_dossie() -> None:
    atual = uuid4()
    com_dossie = uuid4()
    sem_dossie = uuid4()
    estatisticas = [
        _estatistica(sem_dossie, dias=1, total=5, erros=0),
        _estatistica(com_dossie, dias=6, total=3, erros=2, dias_erro=6),
    ]
    relacionados = escolher_relacionados(
        atual,
        estatisticas,
        trechos_por_topico={com_dossie: "trecho real do dossiê"},
        slugs_por_topico={com_dossie: "dir-pro-civ-03-atos-processuais", sem_dossie: "outro"},
        agora=AGORA,
        quantidade=1,
    )
    assert len(relacionados) == 1
    assert relacionados[0].topico_slug == "dir-pro-civ-03-atos-processuais"
    assert relacionados[0].trecho_do_dossie_relacionado == "trecho real do dossiê"
    assert relacionados[0].dias_atras == 6
    assert relacionados[0].acertos == 1
    assert relacionados[0].total == 3


def test_escolher_relacionados_exclui_o_topico_atual() -> None:
    atual = uuid4()
    relacionados = escolher_relacionados(
        atual,
        [_estatistica(atual, dias=1, total=5, erros=1)],
        trechos_por_topico={atual: "trecho"},
        slugs_por_topico={atual: "topico-atual"},
        agora=AGORA,
        quantidade=1,
    )
    assert relacionados == []


def test_renderizar_com_notas_substitui_marcadores_por_numeros() -> None:
    html, notas = renderizar_com_notas(
        "Texto com {{Lei 8.429/1992 art. 1}} e {{STJ Súmula 651}}.",
        [
            CitacaoAula(
                canonica="Lei 8.429/1992 art. 1",
                fonte="F1",
                trecho="serão punidos na forma desta lei",
                frase_da_aula="Texto com",
            ),
            CitacaoAula(
                canonica="STJ Súmula 651",
                fonte="F2",
                trecho="não depende de condenação judicial",
                frase_da_aula="e",
            ),
        ],
    )
    assert "{{" not in html
    assert "[1]" in html and "[2]" in html
    assert len(notas) == 2
    assert notas[0].rotulo == "Lei 8.429/1992 art. 1"
    assert notas[0].texto == "serão punidos na forma desta lei"

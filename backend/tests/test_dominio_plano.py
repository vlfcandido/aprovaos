# O que é: testes do domínio puro do plano do dia (fatia 8, F3.x) — regime por energia/sono/
# pedido de descanso, candidatos de bloco (revisão sempre primeiro, escassez tratada por
# omissão), seleção pelo tempo disponível, o porquê de cada bloco e o porquê geral, e a troca de
# bloco (discordar). Quando ler: ao mexer em `dominio/plano.py`.
from uuid import UUID, uuid4

from aprovaos.dominio.plano import (
    DIAS_JANELA_SEMANA_PROVA,
    DURACAO_AULA_MIN,
    DURACAO_QUESTOES_MIN,
    DURACAO_REVISAO_MAX_MIN,
    DURACAO_REVISAO_MIN_MIN,
    MAXIMO_BLOCOS,
    CandidatoBloco,
    StatusTrilha,
    TopicoParaPlano,
    escolher_substituto,
    montar_candidatos,
    montar_plano,
    motivo_geral_do_plano,
    selecionar_blocos,
)

TOPICO_A = uuid4()
TOPICO_B = uuid4()
TOPICO_C = uuid4()


def _topico(
    topico_id: UUID | None = None,
    nome: str = "Improbidade administrativa",
    materia: str = "Direito Administrativo",
    questoes: int = 5,
    tem_aula: bool = False,
    status: StatusTrilha = "fraco",
) -> TopicoParaPlano:
    return TopicoParaPlano(
        topico_id=topico_id or uuid4(),
        slug="dir-adm-06-improbidade-administrativa",
        nome=nome,
        materia=materia,
        questoes_publicaveis=questoes,
        tem_aula=tem_aula,
        status=status,
        motivo_trilha="5 questões publicáveis; ainda não estudado",
    )


# ---------------------------------------------------------------------------
# montar_candidatos
# ---------------------------------------------------------------------------


def test_candidato_de_revisao_entra_primeiro_quando_ha_cartao_vencido() -> None:
    candidatos = montar_candidatos([], cartoes_vencidos_qtd=3, restrito=False)
    assert len(candidatos) == 1
    assert candidatos[0].tipo == "revisao"
    assert "3 cartões" in candidatos[0].porque


def test_duracao_da_revisao_e_limitada_por_baixo_e_por_cima() -> None:
    poucos = montar_candidatos([], cartoes_vencidos_qtd=1, restrito=False)
    muitos = montar_candidatos([], cartoes_vencidos_qtd=100, restrito=False)
    assert poucos[0].duracao_min == DURACAO_REVISAO_MIN_MIN
    assert muitos[0].duracao_min == DURACAO_REVISAO_MAX_MIN


def test_singular_de_um_cartao_vencido() -> None:
    candidatos = montar_candidatos([], cartoes_vencidos_qtd=1, restrito=False)
    assert "1 cartão " in candidatos[0].porque


def test_restrito_para_depois_da_revisao_sem_candidato_de_conteudo_novo() -> None:
    topicos = [_topico(tem_aula=True, questoes=10)]
    candidatos = montar_candidatos(topicos, cartoes_vencidos_qtd=2, restrito=True)
    assert len(candidatos) == 1
    assert candidatos[0].tipo == "revisao"


def test_restrito_sem_cartao_vencido_fica_sem_candidato_nenhum() -> None:
    topicos = [_topico(tem_aula=True, questoes=10)]
    assert montar_candidatos(topicos, cartoes_vencidos_qtd=0, restrito=True) == []


def test_topico_dominado_nunca_vira_candidato() -> None:
    topicos = [_topico(status="dominado", tem_aula=True, questoes=10)]
    assert montar_candidatos(topicos, cartoes_vencidos_qtd=0, restrito=False) == []


def test_topico_sem_aula_e_sem_questao_nunca_vira_candidato() -> None:
    topicos = [_topico(tem_aula=False, questoes=0)]
    assert montar_candidatos(topicos, cartoes_vencidos_qtd=0, restrito=False) == []


def test_topico_com_aula_e_questao_gera_os_dois_candidatos() -> None:
    topicos = [_topico(tem_aula=True, questoes=10)]
    candidatos = montar_candidatos(topicos, cartoes_vencidos_qtd=0, restrito=False)
    tipos = [c.tipo for c in candidatos]
    assert tipos == ["aula", "questoes"]
    assert candidatos[0].duracao_min == DURACAO_AULA_MIN
    assert candidatos[1].duracao_min == DURACAO_QUESTOES_MIN
    assert all(c.topico_id == topicos[0].topico_id for c in candidatos)


# ---------------------------------------------------------------------------
# selecionar_blocos
# ---------------------------------------------------------------------------


def test_revisao_entra_mesmo_estourando_o_tempo_disponivel() -> None:
    candidatos = [CandidatoBloco(tipo="revisao", topico_id=None, duracao_min=40, porque="x")]
    assert selecionar_blocos(candidatos, tempo_min=10) == candidatos


def test_selecao_para_quando_o_proximo_nao_cabe() -> None:
    candidatos = [
        CandidatoBloco(tipo="aula", topico_id=TOPICO_A, duracao_min=25, porque="a"),
        CandidatoBloco(tipo="questoes", topico_id=TOPICO_A, duracao_min=20, porque="b"),
        CandidatoBloco(tipo="aula", topico_id=TOPICO_B, duracao_min=25, porque="c"),
    ]
    selecionados = selecionar_blocos(candidatos, tempo_min=50)
    assert [c.porque for c in selecionados] == ["a", "b"]


def test_selecao_respeita_o_teto_de_blocos() -> None:
    candidatos = [
        CandidatoBloco(tipo="questoes", topico_id=uuid4(), duracao_min=1, porque=str(i))
        for i in range(10)
    ]
    selecionados = selecionar_blocos(candidatos, tempo_min=1000)
    assert len(selecionados) == MAXIMO_BLOCOS


def test_selecao_vazia_sem_candidato_nenhum() -> None:
    assert selecionar_blocos([], tempo_min=120) == []


# ---------------------------------------------------------------------------
# montar_plano (função pública)
# ---------------------------------------------------------------------------


def test_montar_plano_com_conteudo_disponivel() -> None:
    topicos = [_topico(tem_aula=True, questoes=10, status="nao_visto")]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=60,
        energia=4,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
    )
    assert resultado.modo == "normal"
    assert len(resultado.blocos) == 2
    assert all(b.porque for b in resultado.blocos)
    assert [b.ordem for b in resultado.blocos] == [1, 2]
    assert resultado.blocos[0].hora_sugerida.hour == 6
    assert resultado.blocos[1].hora_sugerida.minute == 55  # 06:30 + 25 min


def test_montar_plano_e_deterministico() -> None:
    topicos = [_topico(tem_aula=True, questoes=10)]
    primeiro = montar_plano(
        topicos,
        cartoes_vencidos_qtd=2,
        tempo_min=60,
        energia=4,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="noite",
    )
    segundo = montar_plano(
        topicos,
        cartoes_vencidos_qtd=2,
        tempo_min=60,
        energia=4,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="noite",
    )
    assert primeiro == segundo


def test_energia_baixa_restringe_a_revisao_com_cartao_vencido() -> None:
    topicos = [_topico(tem_aula=True, questoes=10)]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=3,
        tempo_min=60,
        energia=2,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
    )
    assert [b.tipo for b in resultado.blocos] == ["revisao"]
    assert resultado.modo == "normal"


def test_energia_baixa_sem_cartao_vencido_vira_descanso() -> None:
    topicos = [_topico(tem_aula=True, questoes=10)]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=60,
        energia=1,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
    )
    assert resultado.blocos == []
    assert resultado.modo == "descanso"
    assert "descansar" in resultado.porque_geral.lower()


def test_sono_baixo_restringe_mesmo_com_energia_boa() -> None:
    topicos = [_topico(tem_aula=True, questoes=10)]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=60,
        energia=5,
        sono_h=4.0,
        pediu_descanso=False,
        horario_preferido="manha",
    )
    assert resultado.blocos == []
    assert resultado.modo == "descanso"


def test_pedido_explicito_de_descanso_vence_tudo() -> None:
    topicos = [_topico(tem_aula=True, questoes=10)]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=5,
        tempo_min=60,
        energia=5,
        sono_h=8.0,
        pediu_descanso=True,
        horario_preferido="manha",
    )
    assert resultado.blocos == []
    assert resultado.modo == "descanso"
    assert "pediu" in resultado.porque_geral.lower()


def test_escassez_de_conteudo_aparece_no_porque_geral() -> None:
    topicos = [_topico(nome="Raciocínio Lógico", tem_aula=False, questoes=0, status="nao_visto")]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=60,
        energia=4,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
    )
    assert resultado.blocos == []
    assert "Raciocínio Lógico" in resultado.porque_geral


def test_teto_de_blocos_do_prototipo() -> None:
    topicos = [
        _topico(topico_id=uuid4(), tem_aula=True, questoes=10, status="nao_visto")
        for _ in range(10)
    ]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=10_000,
        energia=4,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
    )
    assert len(resultado.blocos) == MAXIMO_BLOCOS


# ---------------------------------------------------------------------------
# motivo_geral_do_plano (chamado direto para os casos de fronteira do texto)
# ---------------------------------------------------------------------------


def test_motivo_geral_cita_quantidade_e_tempo_total() -> None:
    candidatos = [
        CandidatoBloco(tipo="questoes", topico_id=TOPICO_A, duracao_min=20, porque="x"),
    ]
    blocos = selecionar_blocos(candidatos, tempo_min=30)
    from aprovaos.dominio.plano import _atribuir_ordem_e_hora

    planejados = _atribuir_ordem_e_hora(blocos, "manha")
    texto = motivo_geral_do_plano(
        restrito=False, pediu_descanso=False, blocos=planejados, tempo_min=30, topicos=[]
    )
    assert "1 bloco" in texto
    assert "20 min" in texto


# ---------------------------------------------------------------------------
# escolher_substituto (discordar)
# ---------------------------------------------------------------------------


def test_escolher_substituto_acha_alternativa_nao_usada() -> None:
    topicos = [_topico(topico_id=TOPICO_A, tem_aula=True, questoes=10, status="nao_visto")]
    # tempo_min=25 só deixa a aula caber (25+20 > 25) — sobra a alternativa "questoes" do
    # mesmo tópico, ainda fora do plano de hoje.
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=25,
        energia=4,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
    )
    assert [b.tipo for b in resultado.blocos] == ["aula"]
    bloco_atual = resultado.blocos[0]
    candidatos = montar_candidatos(topicos, cartoes_vencidos_qtd=0, restrito=False)
    substituto = escolher_substituto(candidatos, bloco_atual, resultado.blocos, tempo_restante=25)
    assert substituto is not None
    assert substituto.tipo == "questoes"


def test_escolher_substituto_none_sem_alternativa() -> None:
    topicos = [_topico(topico_id=TOPICO_A, tem_aula=True, questoes=10, status="nao_visto")]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=25,
        energia=4,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
    )
    bloco_atual = resultado.blocos[0]
    candidatos = montar_candidatos(topicos, cartoes_vencidos_qtd=0, restrito=False)
    substituto = escolher_substituto(candidatos, bloco_atual, resultado.blocos, tempo_restante=0)
    assert substituto is None


# ---------------------------------------------------------------------------
# semana da prova (RF-19, fatia 10 §7, fecha a P-55)
# ---------------------------------------------------------------------------


def test_oito_dias_nao_e_semana_da_prova() -> None:
    topicos = [_topico(status="fraco", questoes=5)]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=60,
        energia=4,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
        dias_para_prova=DIAS_JANELA_SEMANA_PROVA + 1,
    )
    assert resultado.modo == "normal"


def test_sete_e_zero_dias_sao_semana_da_prova() -> None:
    topicos = [_topico(status="fraco", questoes=5)]
    for dias in (DIAS_JANELA_SEMANA_PROVA, 0):
        resultado = montar_plano(
            topicos,
            cartoes_vencidos_qtd=0,
            tempo_min=60,
            energia=4,
            sono_h=7.0,
            pediu_descanso=False,
            horario_preferido="manha",
            dias_para_prova=dias,
        )
        assert resultado.modo == "semana_prova"


def test_data_no_passado_nao_e_semana_da_prova() -> None:
    topicos = [_topico(status="fraco", questoes=5)]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=60,
        energia=4,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
        dias_para_prova=-1,
    )
    assert resultado.modo == "normal"


def test_pedido_de_descanso_vence_semana_da_prova() -> None:
    topicos = [_topico(status="fraco", questoes=5)]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=5,
        tempo_min=60,
        energia=5,
        sono_h=8.0,
        pediu_descanso=True,
        horario_preferido="manha",
        dias_para_prova=3,
    )
    assert resultado.modo == "descanso"
    assert resultado.blocos == []


def test_energia_baixa_sem_cartao_vence_semana_da_prova() -> None:
    # Tópico fraco sem questão nem aula: não gera candidato nenhum mesmo fora do regime
    # restrito — junto com energia baixa (restrito) e sem cartão vencido, o dia vira descanso
    # mesmo estando na janela da semana da prova (regra de saúde vence, visão §4).
    topicos = [_topico(status="fraco", questoes=0, tem_aula=False)]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=60,
        energia=1,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
        dias_para_prova=3,
    )
    assert resultado.modo == "descanso"
    assert resultado.blocos == []


def test_semana_da_prova_nunca_oferece_topico_nao_visto() -> None:
    topicos = [_topico(status="nao_visto", tem_aula=True, questoes=10)]
    candidatos = montar_candidatos(
        topicos, cartoes_vencidos_qtd=0, restrito=False, dias_para_prova=3
    )
    assert candidatos == []


def test_semana_da_prova_ignora_topico_dominado() -> None:
    topicos = [_topico(status="dominado", tem_aula=True, questoes=10)]
    candidatos = montar_candidatos(
        topicos, cartoes_vencidos_qtd=0, restrito=False, dias_para_prova=3
    )
    assert candidatos == []


def test_semana_da_prova_oferece_so_questoes_do_topico_fraco_nunca_aula() -> None:
    topicos = [_topico(status="fraco", tem_aula=True, questoes=10)]
    candidatos = montar_candidatos(
        topicos, cartoes_vencidos_qtd=0, restrito=False, dias_para_prova=3
    )
    assert [c.tipo for c in candidatos] == ["questoes"]


def test_restrito_vence_semana_da_prova_na_geracao_de_candidatos() -> None:
    # Restrito (energia/sono) já é mais restritivo que a semana da prova — nenhum tópico entra,
    # nem mesmo o fraco; só a revisão, se houver cartão vencido.
    topicos = [_topico(status="fraco", tem_aula=True, questoes=10)]
    candidatos = montar_candidatos(
        topicos, cartoes_vencidos_qtd=2, restrito=True, dias_para_prova=3
    )
    assert [c.tipo for c in candidatos] == ["revisao"]


def test_porque_da_revisao_cita_os_dias_para_a_prova() -> None:
    candidatos = montar_candidatos([], cartoes_vencidos_qtd=2, restrito=False, dias_para_prova=3)
    assert "3 dias" in candidatos[0].porque
    assert "revisão cirúrgica" in candidatos[0].porque


def test_porque_das_questoes_cita_os_dias_para_a_prova() -> None:
    topicos = [_topico(status="fraco", questoes=5)]
    candidatos = montar_candidatos(
        topicos, cartoes_vencidos_qtd=0, restrito=False, dias_para_prova=3
    )
    assert "3 dias" in candidatos[0].porque
    assert "revisão cirúrgica" in candidatos[0].porque


def test_frase_dos_dias_no_singular() -> None:
    candidatos = montar_candidatos([], cartoes_vencidos_qtd=1, restrito=False, dias_para_prova=1)
    assert "Falta 1 dia " in candidatos[0].porque
    assert "1 dias" not in candidatos[0].porque


def test_porque_geral_cita_os_dias_com_blocos() -> None:
    topicos = [_topico(status="fraco", questoes=5)]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=60,
        energia=4,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
        dias_para_prova=3,
    )
    assert "3 dias" in resultado.porque_geral


def test_porque_geral_cita_os_dias_sem_bloco_nenhum() -> None:
    # Semana da prova, mas nada de conteúdo elegível (só um tópico nunca visto) — sem bloco,
    # ainda assim explica a semana da prova, não a escassez genérica.
    topicos = [_topico(status="nao_visto", tem_aula=True, questoes=10)]
    resultado = montar_plano(
        topicos,
        cartoes_vencidos_qtd=0,
        tempo_min=60,
        energia=4,
        sono_h=7.0,
        pediu_descanso=False,
        horario_preferido="manha",
        dias_para_prova=3,
    )
    assert resultado.blocos == []
    assert resultado.modo == "semana_prova"
    assert "3 dias" in resultado.porque_geral

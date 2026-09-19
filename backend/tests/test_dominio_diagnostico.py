# O que é: testes do motor puro do diagnóstico adaptativo (fatia 7) — a fórmula de margem/
# estimativa por proxy (acerto + confiança), a seleção do próximo item (cobertura de tópicos
# desempatando) e a parada (teto de 30, matéria sem questão nunca candidata). Sem banco.
# Quando ler: ao mexer em `dominio/diagnostico.py`.
from uuid import UUID, uuid4

from aprovaos.dominio.diagnostico import (
    LIMITE_MARGEM,
    MARGEM_INICIAL,
    MAXIMO_ITENS,
    CandidatoItem,
    Confianca,
    EstadoAgregado,
    ItemDiagnostico,
    SinalTopico,
    TopicoDisponivel,
    agrupar_por_materia,
    agrupar_por_topico,
    calcular_estado,
    materias_elegiveis,
    motivo_geral,
    ordenar_candidatos,
    sinais_por_topico,
)

MATERIA_A = "Direito Constitucional"
MATERIA_B = "Língua Portuguesa"


def _item(
    materia: str,
    *,
    acertou: bool,
    confianca: Confianca = "certeza",
    topico_id: UUID | None = None,
) -> ItemDiagnostico:
    return ItemDiagnostico(
        topico_id=topico_id or uuid4(),
        materia=materia,
        acertou=acertou,
        confianca=confianca,
    )


def test_estado_sem_nenhum_item_fica_com_margem_inicial_e_sem_estimativa() -> None:
    estado = calcular_estado([])
    assert estado.n_itens == 0
    assert estado.estimativa_pct is None
    assert estado.margem == MARGEM_INICIAL
    assert estado.fechado is False


def test_acerta_tudo_com_certeza_fecha_a_margem_e_estimativa_e_cem() -> None:
    respostas = [_item(MATERIA_A, acertou=True, confianca="certeza") for _ in range(3)]
    estado = calcular_estado(respostas)
    assert estado.n_itens == 3
    assert estado.estimativa_pct == 100.0
    assert estado.margem <= LIMITE_MARGEM
    assert estado.fechado is True


def test_erra_tudo_com_certeza_fecha_a_margem_na_mesma_velocidade_que_acertar() -> None:
    """A largura da margem só depende da quantidade/confiança das respostas, não do acerto."""
    erra = calcular_estado([_item(MATERIA_A, acertou=False, confianca="certeza") for _ in range(3)])
    acerta = calcular_estado(
        [_item(MATERIA_A, acertou=True, confianca="certeza") for _ in range(3)]
    )
    assert erra.margem == acerta.margem
    assert erra.estimativa_pct == 0.0
    assert erra.fechado is True


def test_duvida_fecha_a_margem_mais_devagar_que_certeza() -> None:
    com_duvida = calcular_estado([_item(MATERIA_A, acertou=True, confianca="duvida")])
    com_certeza = calcular_estado([_item(MATERIA_A, acertou=True, confianca="certeza")])
    assert com_duvida.margem > com_certeza.margem


def test_alterna_acerto_e_confianca_fica_entre_os_dois_extremos() -> None:
    sequencia = [
        _item(MATERIA_A, acertou=True, confianca="certeza"),
        _item(MATERIA_A, acertou=False, confianca="duvida"),
        _item(MATERIA_A, acertou=True, confianca="duvida"),
        _item(MATERIA_A, acertou=False, confianca="certeza"),
    ]
    estado = calcular_estado(sequencia)
    assert estado.n_itens == 4
    assert 0.0 < estado.estimativa_pct < 100.0  # type: ignore[operator]
    assert estado.margem < MARGEM_INICIAL


def test_margem_decresce_monotonicamente_a_cada_item() -> None:
    margens = []
    respostas: list[ItemDiagnostico] = []
    for i in range(6):
        respostas.append(_item(MATERIA_A, acertou=i % 2 == 0, confianca="duvida"))
        margens.append(calcular_estado(respostas).margem)
    assert margens == sorted(margens, reverse=True)
    assert len(set(margens)) == len(margens)  # estritamente decrescente


def test_agrupar_por_materia_separa_os_grupos() -> None:
    respostas = [
        _item(MATERIA_A, acertou=True),
        _item(MATERIA_A, acertou=True),
        _item(MATERIA_B, acertou=False),
    ]
    estados = agrupar_por_materia(respostas)
    assert set(estados) == {MATERIA_A, MATERIA_B}
    assert estados[MATERIA_A].n_itens == 2
    assert estados[MATERIA_B].n_itens == 1


def test_agrupar_por_topico_separa_por_topico_mesmo_na_mesma_materia() -> None:
    topico_1, topico_2 = uuid4(), uuid4()
    respostas = [
        _item(MATERIA_A, acertou=True, topico_id=topico_1),
        _item(MATERIA_A, acertou=False, topico_id=topico_2),
    ]
    estados = agrupar_por_topico(respostas)
    assert set(estados) == {topico_1, topico_2}


def test_materias_elegiveis_exclui_materia_sem_questao_desde_o_inicio() -> None:
    topicos = [
        TopicoDisponivel(topico_id=uuid4(), materia=MATERIA_A, nome="Poderes", tem_questao=True),
        TopicoDisponivel(topico_id=uuid4(), materia=MATERIA_B, nome="Crase", tem_questao=False),
    ]
    estados: dict[str, EstadoAgregado] = {}
    elegiveis = materias_elegiveis(topicos, estados)
    assert elegiveis == [MATERIA_A]


def test_materias_elegiveis_exclui_materia_ja_fechada_sem_forcar() -> None:
    topico_a = TopicoDisponivel(
        topico_id=uuid4(), materia=MATERIA_A, nome="Poderes", tem_questao=True
    )
    topico_b = TopicoDisponivel(
        topico_id=uuid4(), materia=MATERIA_B, nome="Crase", tem_questao=True
    )
    estado_fechado = calcular_estado([_item(MATERIA_A, acertou=True) for _ in range(5)])
    assert estado_fechado.fechado is True
    estados = {MATERIA_A: estado_fechado}
    assert materias_elegiveis([topico_a, topico_b], estados) == [MATERIA_B]
    forcadas = materias_elegiveis([topico_a, topico_b], estados, materias_forcadas={MATERIA_A})
    assert set(forcadas) == {MATERIA_A, MATERIA_B}


def test_ordenar_candidatos_prioriza_a_materia_de_maior_margem() -> None:
    topico_a = TopicoDisponivel(
        topico_id=uuid4(), materia=MATERIA_A, nome="Poderes", tem_questao=True
    )
    topico_b = TopicoDisponivel(
        topico_id=uuid4(), materia=MATERIA_B, nome="Crase", tem_questao=True
    )
    # A já tem 3 itens de certeza (margem estreita); B não tem nenhum (margem larga).
    estados = {MATERIA_A: calcular_estado([_item(MATERIA_A, acertou=True) for _ in range(3)])}
    candidatos = ordenar_candidatos([topico_a, topico_b], estados, respondidos_por_topico={})
    assert candidatos[0].materia == MATERIA_B


def test_ordenar_candidatos_usa_cobertura_para_desempatar_dentro_da_materia() -> None:
    topico_mais_visto = TopicoDisponivel(
        topico_id=uuid4(), materia=MATERIA_A, nome="Visto", tem_questao=True
    )
    topico_novo = TopicoDisponivel(
        topico_id=uuid4(), materia=MATERIA_A, nome="Novo", tem_questao=True
    )
    respondidos = {topico_mais_visto.topico_id: 4, topico_novo.topico_id: 0}
    candidatos = ordenar_candidatos(
        [topico_mais_visto, topico_novo], estados={}, respondidos_por_topico=respondidos
    )
    assert candidatos[0].topico_id == topico_novo.topico_id
    assert candidatos[0].motivo  # sempre traz o porquê


def test_ordenar_candidatos_vazio_quando_nenhuma_materia_elegivel() -> None:
    topico = TopicoDisponivel(topico_id=uuid4(), materia=MATERIA_A, nome="X", tem_questao=False)
    assert ordenar_candidatos([topico], estados={}, respondidos_por_topico={}) == []


def test_determinismo_mesma_entrada_mesma_saida() -> None:
    topico_a = TopicoDisponivel(topico_id=uuid4(), materia=MATERIA_A, nome="A", tem_questao=True)
    topico_b = TopicoDisponivel(topico_id=uuid4(), materia=MATERIA_B, nome="B", tem_questao=True)
    estados = {MATERIA_A: calcular_estado([_item(MATERIA_A, acertou=True)])}
    primeira = ordenar_candidatos([topico_a, topico_b], estados, {})
    segunda = ordenar_candidatos([topico_a, topico_b], estados, {})
    assert [c.topico_id for c in primeira] == [c.topico_id for c in segunda]


def test_sinais_por_topico_marca_sem_questao_e_sem_dado_e_testado() -> None:
    testado = uuid4()
    sem_dado = uuid4()
    sem_questao = uuid4()
    topicos = [
        TopicoDisponivel(topico_id=testado, materia=MATERIA_A, nome="T", tem_questao=True),
        TopicoDisponivel(topico_id=sem_dado, materia=MATERIA_A, nome="SD", tem_questao=True),
        TopicoDisponivel(topico_id=sem_questao, materia=MATERIA_B, nome="SQ", tem_questao=False),
    ]
    respostas = [
        _item(MATERIA_A, acertou=True, confianca="certeza", topico_id=testado) for _ in range(4)
    ]
    sinais = {s.topico_id: s for s in sinais_por_topico(respostas, topicos)}
    assert sinais[testado].situacao == "dominado"
    assert sinais[sem_dado].situacao == "sem_dado"
    assert sinais[sem_questao].situacao == "sem_questao"
    assert sinais[sem_questao].estimativa_pct is None


def test_sinais_por_topico_nao_dominado_quando_erra() -> None:
    topico_id = uuid4()
    topicos = [TopicoDisponivel(topico_id=topico_id, materia=MATERIA_A, nome="T", tem_questao=True)]
    respostas = [_item(MATERIA_A, acertou=False, confianca="certeza", topico_id=topico_id)]
    sinais = {s.topico_id: s for s in sinais_por_topico(respostas, topicos)}
    assert sinais[topico_id].situacao == "a_estudar"


def test_motivo_geral_cita_matoria_que_fechou_com_menos_itens() -> None:
    estados = {
        MATERIA_A: calcular_estado([_item(MATERIA_A, acertou=True) for _ in range(3)]),
        MATERIA_B: calcular_estado([_item(MATERIA_B, acertou=True) for _ in range(6)]),
    }
    texto = motivo_geral(total_itens=9, estados_por_materia=estados, materias_sem_questao=set())
    assert "9 itens" in texto
    assert MATERIA_A in texto


def test_motivo_geral_avisa_materia_sem_questao() -> None:
    texto = motivo_geral(total_itens=0, estados_por_materia={}, materias_sem_questao={MATERIA_B})
    assert MATERIA_B in texto
    assert "sem questão" in texto.lower()


def test_motivo_geral_avisa_teto_de_itens() -> None:
    estados = {MATERIA_A: calcular_estado([_item(MATERIA_A, acertou=True, confianca="duvida")])}
    texto = motivo_geral(
        total_itens=MAXIMO_ITENS, estados_por_materia=estados, materias_sem_questao=set()
    )
    assert "30" in texto


def test_candidato_item_e_sinal_topico_sao_modelos_imutaveis_o_bastante_para_teste() -> None:
    # Só confere que os modelos existem com os campos documentados (contrato usado pela rota).
    candidato = CandidatoItem(topico_id=uuid4(), materia=MATERIA_A, motivo="por quê")
    assert candidato.motivo == "por quê"
    sinal = SinalTopico(
        topico_id=uuid4(),
        materia=MATERIA_A,
        situacao="sem_dado",
        estimativa_pct=None,
        margem=None,
        n_itens=0,
    )
    assert sinal.situacao == "sem_dado"

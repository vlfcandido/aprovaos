# O que é: testes da regra pura do fio da memória (V5) — `dominio/fio_memoria.py`: o ranking dos
# tópicos já vistos (erro recente / tempo sem ver, alternados), o texto do `motivo` e a cadência
# de quando a próxima posição do bloco é um item intercalado. Sem banco: todo histórico é
# `EstatisticaTopicoVisto` construída à mão. Quando ler: ao mexer no critério de intercalação ou
# na cadência (`PERIODO_INTERCALACAO`).
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from aprovaos.dominio.fio_memoria import (
    PERIODO_INTERCALACAO,
    EstatisticaTopicoVisto,
    ItemIntercalado,
    decidir_proximo_intercalado,
    escolher_para_intercalar,
    ordem_para_tentar,
)

AGORA = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

TOPICO_ATUAL = uuid4()


def _estatistica(
    *,
    materia: str = "Direito Constitucional",
    nome: str = "Controle de constitucionalidade",
    dias_desde_visita: int = 6,
    total: int = 3,
    erros: int = 2,
    dias_desde_erro: int | None = None,
) -> EstatisticaTopicoVisto:
    """Constrói uma estatística de fixture; `dias_desde_erro=None` com `erros>0` reusa
    `dias_desde_visita` (o erro mais recente coincide com a última visita, o caso comum).
    """
    ultimo_erro_em = None
    if erros > 0:
        dias = dias_desde_erro if dias_desde_erro is not None else dias_desde_visita
        ultimo_erro_em = AGORA - timedelta(days=dias)
    return EstatisticaTopicoVisto(
        topico_id=uuid4(),
        topico_nome=nome,
        materia=materia,
        ultima_visita=AGORA - timedelta(days=dias_desde_visita),
        total_respostas=total,
        erros=erros,
        ultimo_erro_em=ultimo_erro_em,
    )


def test_sem_historico_nao_intercala() -> None:
    assert escolher_para_intercalar(TOPICO_ATUAL, [], AGORA) == []


def test_so_o_topico_atual_no_historico_nao_intercala() -> None:
    unico = EstatisticaTopicoVisto(
        topico_id=TOPICO_ATUAL,
        topico_nome="O próprio tópico",
        materia="Direito Administrativo",
        ultima_visita=AGORA,
        total_respostas=5,
        erros=0,
        ultimo_erro_em=None,
    )
    assert escolher_para_intercalar(TOPICO_ATUAL, [unico], AGORA) == []


def test_motivo_com_erro_bate_com_o_exemplo_da_spec() -> None:
    estatistica = _estatistica(
        materia="Direito Constitucional", dias_desde_visita=6, total=3, erros=2
    )
    itens = escolher_para_intercalar(TOPICO_ATUAL, [estatistica], AGORA)
    assert len(itens) == 1
    assert itens[0].motivo == "de Direito Constitucional, que você viu há 6 dias e errou 2 de 3"


def test_motivo_sem_erro_mostra_acertou() -> None:
    estatistica = _estatistica(materia="Direito Civil", dias_desde_visita=10, total=4, erros=0)
    itens = escolher_para_intercalar(TOPICO_ATUAL, [estatistica], AGORA)
    assert itens[0].motivo == "de Direito Civil, que você viu há 10 dias e acertou 4 de 4"


def test_motivo_um_dia_usa_singular() -> None:
    estatistica = _estatistica(dias_desde_visita=1, erros=0, total=1)
    itens = escolher_para_intercalar(TOPICO_ATUAL, [estatistica], AGORA)
    assert "há 1 dia e" in itens[0].motivo
    assert "1 dias" not in itens[0].motivo


def test_ignora_o_topico_atual_mesmo_com_outros_elegiveis() -> None:
    do_atual = EstatisticaTopicoVisto(
        topico_id=TOPICO_ATUAL,
        topico_nome="O próprio tópico",
        materia="Direito Administrativo",
        ultima_visita=AGORA,
        total_respostas=9,
        erros=9,
        ultimo_erro_em=AGORA,
    )
    outro = _estatistica()
    itens = escolher_para_intercalar(TOPICO_ATUAL, [do_atual, outro], AGORA)
    assert [item.topico_id for item in itens] == [outro.topico_id]


def test_prioriza_erro_mais_recente_primeiro() -> None:
    erro_antigo = _estatistica(nome="A", dias_desde_erro=20, dias_desde_visita=20)
    erro_recente = _estatistica(nome="B", dias_desde_erro=1, dias_desde_visita=1)
    itens = escolher_para_intercalar(TOPICO_ATUAL, [erro_antigo, erro_recente], AGORA)
    assert [item.topico_nome for item in itens] == ["B", "A"]
    assert itens[0].criterio == "erro_recente"


def test_alterna_erro_recente_e_tempo_sem_ver() -> None:
    # A: erro recentíssimo (ganha a fila de erro). B: nunca errou, mas não é vista há muito tempo
    # (ganha a fila de tempo). C: erro um pouco mais antigo que A (2º da fila de erro).
    a = _estatistica(nome="A", dias_desde_erro=1, dias_desde_visita=1)
    b = _estatistica(nome="B", erros=0, dias_desde_visita=90)
    c = _estatistica(nome="C", dias_desde_erro=5, dias_desde_visita=5)
    itens = escolher_para_intercalar(TOPICO_ATUAL, [a, b, c], AGORA, quantidade=3)
    assert [item.topico_nome for item in itens] == ["A", "B", "C"]
    assert [item.criterio for item in itens] == ["erro_recente", "tempo_sem_ver", "erro_recente"]


def test_nao_repete_topico_entre_as_duas_filas() -> None:
    # Único elegível: erra recente E é o que não é visto há mais tempo ao mesmo tempo — não pode
    # aparecer duas vezes só porque lidera as duas filas.
    unico = _estatistica(dias_desde_erro=1, dias_desde_visita=1)
    itens = escolher_para_intercalar(TOPICO_ATUAL, [unico], AGORA, quantidade=3)
    assert len(itens) == 1


def test_menos_de_tres_elegiveis_devolve_quantos_houver() -> None:
    a = _estatistica(nome="A")
    b = _estatistica(nome="B")
    itens = escolher_para_intercalar(TOPICO_ATUAL, [a, b], AGORA, quantidade=3)
    assert len(itens) == 2


def test_decidir_proximo_intercalado_sem_itens_nunca_intercala() -> None:
    for posicao in range(10):
        assert decidir_proximo_intercalado(posicao, []) is None


def _item(nome: str) -> ItemIntercalado:
    return ItemIntercalado(topico_id=uuid4(), topico_nome=nome, criterio="erro_recente", motivo="m")


def test_decidir_proximo_intercalado_dispara_a_cada_periodo() -> None:
    itens = [_item("A"), _item("B"), _item("C")]
    disparos = [
        posicao
        for posicao in range(0, 3 * PERIODO_INTERCALACAO)
        if decidir_proximo_intercalado(posicao, itens) is not None
    ]
    assert disparos == [3, 7, 11]


def test_decidir_proximo_intercalado_cicla_pelos_itens_disponiveis() -> None:
    itens = [_item("A"), _item("B")]
    assert decidir_proximo_intercalado(3, itens) == itens[0]
    assert decidir_proximo_intercalado(7, itens) == itens[1]
    assert decidir_proximo_intercalado(11, itens) == itens[0]


def test_ordem_para_tentar_vazia_fora_da_posicao_de_intercalar() -> None:
    itens = [_item("A"), _item("B"), _item("C")]
    assert ordem_para_tentar(0, itens) == []
    assert ordem_para_tentar(2, itens) == []


def test_ordem_para_tentar_vazia_sem_candidato() -> None:
    assert ordem_para_tentar(3, []) == []


def test_ordem_para_tentar_comeca_pelo_escolhido_e_cicla_os_demais() -> None:
    a, b, c = _item("A"), _item("B"), _item("C")
    itens = [a, b, c]
    assert ordem_para_tentar(3, itens) == [a, b, c]
    assert ordem_para_tentar(7, itens) == [b, c, a]
    assert ordem_para_tentar(11, itens) == [c, a, b]

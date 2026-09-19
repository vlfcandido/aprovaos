# O que é: testes de `dominio/trilha.py` — a ordem defensável dos tópicos (fatia 6, §7 do plano
# `docs/fatias/6-trilha-e-aulas.md`): peso medido (questões publicáveis) e o que a aluna já
# viu/errou, sem depender de peso declarado do edital (P-39). Sem banco: entradas construídas à
# mão. Quando ler: ao mudar o critério de ordenação da trilha.
from datetime import UTC, datetime
from uuid import uuid4

from aprovaos.dominio.fio_memoria import EstatisticaTopicoVisto
from aprovaos.dominio.trilha import TopicoParaTrilha, montar_trilha

AGORA = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _topico(slug: str, *, peso: int, materia: str = "Direito Administrativo") -> TopicoParaTrilha:
    return TopicoParaTrilha(
        topico_id=uuid4(), slug=slug, nome=slug, materia=materia, questoes_publicaveis=peso
    )


def _estatistica(*, total: int, erros: int) -> EstatisticaTopicoVisto:
    return EstatisticaTopicoVisto(
        topico_id=uuid4(),
        topico_nome="visto",
        materia="Direito Administrativo",
        ultima_visita=AGORA,
        total_respostas=total,
        erros=erros,
        ultimo_erro_em=None,
    )


def test_topico_nao_visto_fica_antes_do_dominado_mesmo_com_peso_menor() -> None:
    dominado = _topico("dominado", peso=9)
    nao_visto = _topico("nao-visto", peso=3)
    estatistica_dominada = _estatistica(total=5, erros=0)
    trilha = montar_trilha([dominado, nao_visto], {dominado.topico_id: estatistica_dominada})

    assert [item.slug for item in trilha] == ["nao-visto", "dominado"]
    assert trilha[0].status == "nao_visto"
    assert trilha[1].status == "dominado"


def test_topico_fraco_fica_antes_do_dominado() -> None:
    dominado = _topico("dominado", peso=1)
    fraco = _topico("fraco", peso=1)
    trilha = montar_trilha(
        [dominado, fraco],
        {
            dominado.topico_id: _estatistica(total=5, erros=0),
            fraco.topico_id: _estatistica(total=5, erros=3),
        },
    )
    assert [item.slug for item in trilha] == ["fraco", "dominado"]
    assert trilha[0].status == "fraco"


def test_dentro_do_mesmo_grupo_ordena_por_peso_medido_descendente() -> None:
    baixo = _topico("baixo", peso=2)
    alto = _topico("alto", peso=9)
    trilha = montar_trilha([baixo, alto], {})
    assert [item.slug for item in trilha] == ["alto", "baixo"]
    assert all(item.status == "nao_visto" for item in trilha)


def test_poucas_respostas_nao_e_dominado_mesmo_com_100_por_cento_de_acerto() -> None:
    topico = _topico("visto-pouco", peso=5)
    trilha = montar_trilha([topico], {topico.topico_id: _estatistica(total=2, erros=0)})
    assert trilha[0].status == "fraco"


def test_desempate_por_slug() -> None:
    b = _topico("b-topico", peso=5)
    a = _topico("a-topico", peso=5)
    trilha = montar_trilha([b, a], {})
    assert [item.slug for item in trilha] == ["a-topico", "b-topico"]


def test_motivo_cita_numeros_reais() -> None:
    topico = _topico("com-historico", peso=7)
    trilha = montar_trilha([topico], {topico.topico_id: _estatistica(total=4, erros=3)})
    motivo = trilha[0].motivo
    assert "7" in motivo
    assert "1 de 4" in motivo  # 4 respostas, 3 erros → 1 acerto

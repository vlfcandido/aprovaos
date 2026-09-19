# O que é: testes de `dominio/curva.py` — a curva de domínio (RF-16) e o alerta de atraso
# (RF-10, fecha a P-54), fatia 10 §3 do plano `docs/fatias/10-painel.md`. Sem banco: histórico
# construído à mão com `RespostaHistorica`. Quando ler: ao mudar o critério de "em dia"/"atrasada"
# ou a definição de dominado (que vem de `dominio/trilha.py`, não é redefinida aqui).
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from aprovaos.dominio.curva import RespostaHistorica, alerta_da_curva, montar_curva

HOJE = date(2026, 9, 19)  # sábado


def _resposta(topico_id: UUID, *, dia: date, acertou: bool) -> RespostaHistorica:
    ocorrido_em = datetime.combine(dia, datetime.min.time(), UTC)
    return RespostaHistorica(topico_id=topico_id, acertou=acertou, ocorrido_em=ocorrido_em)


def test_sem_data_alvo_nao_ha_curva_necessaria() -> None:
    curva = montar_curva([], total_topicos=10, hoje=HOJE, data_alvo=None)
    assert curva.necessaria == []
    assert curva.data_alvo is None
    assert curva.lacuna == "sem data da prova"
    assert curva.atraso_topicos == 0


def test_data_alvo_no_passado_e_lacuna_declarada() -> None:
    curva = montar_curva([], total_topicos=10, hoje=HOJE, data_alvo=HOJE - timedelta(days=1))
    assert curva.necessaria == []
    assert curva.lacuna == "data da prova já passou"
    assert curva.atraso_topicos == 0


def test_em_dia_nao_gera_alerta() -> None:
    topico = uuid4()
    respostas = [_resposta(topico, dia=HOJE - timedelta(days=10), acertou=True) for _ in range(3)]
    curva = montar_curva(respostas, total_topicos=1, hoje=HOJE, data_alvo=HOJE + timedelta(days=30))
    assert curva.lacuna is None
    assert curva.atraso_topicos == 0
    assert alerta_da_curva(curva, horas_por_semana=10.0) is None


def test_atrasada_gera_alerta_com_ajuste_numerico() -> None:
    # 10 tópicos no total, nenhum dominado ainda, prova em 2 semanas: ritmo real é zero
    # (nenhuma resposta recente) — o alerta tem de sair com um número concreto de tópicos/semana.
    topico_dominado_ha_muito = uuid4()
    respostas = [
        _resposta(topico_dominado_ha_muito, dia=HOJE - timedelta(weeks=10), acertou=True)
        for _ in range(3)
    ]
    curva = montar_curva(
        respostas, total_topicos=10, hoje=HOJE, data_alvo=HOJE + timedelta(weeks=2)
    )
    assert curva.atraso_topicos > 0

    alerta = alerta_da_curva(curva, horas_por_semana=10.0)
    assert alerta is not None
    assert any(caractere.isdigit() for caractere in alerta.ajuste)
    assert any(caractere.isdigit() for caractere in alerta.porque)


def test_topico_que_perde_o_dominio_ao_errar_faz_a_curva_descer() -> None:
    topico = uuid4()
    respostas = [
        _resposta(topico, dia=HOJE - timedelta(weeks=3), acertou=True),
        _resposta(topico, dia=HOJE - timedelta(weeks=3), acertou=True),
        _resposta(topico, dia=HOJE - timedelta(weeks=3), acertou=True),
        # três semanas depois, dois erros novos derrubam a taxa de acerto para 60 % (< 70 %)
        _resposta(topico, dia=HOJE, acertou=False),
        _resposta(topico, dia=HOJE, acertou=False),
    ]
    curva = montar_curva(respostas, total_topicos=1, hoje=HOJE, data_alvo=None)

    assert len(curva.real) >= 2
    assert curva.real[0].dominados == 1
    assert curva.real[-1].dominados == 0


def test_curva_real_vazia_sem_nenhuma_resposta() -> None:
    curva = montar_curva([], total_topicos=5, hoje=HOJE, data_alvo=None)
    assert curva.real == []

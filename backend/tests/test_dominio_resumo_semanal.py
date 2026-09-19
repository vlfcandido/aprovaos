# O que é: testes de `dominio/resumo_semanal.py` (fatia 10, F4.4c) — o resumo cumulativo de
# sábado: contagem da semana (com banda de Wilson, unificada com o resto do painel), recorte por
# data (fuso de Brasília incluso), tópicos novos, "para rever" (erro mais recente, no máximo 5) e
# a conquista (só com número real). Quando ler: ao mexer no resumo semanal.
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from aprovaos.dominio.curva import RespostaHistorica
from aprovaos.dominio.resumo_semanal import MAXIMO_PARA_REVER, montar_resumo

INICIO = date(2026, 9, 14)  # segunda
FIM = date(2026, 9, 20)  # domingo

TOPICO_A = uuid4()
TOPICO_B = uuid4()

NOMES = {TOPICO_A: "Improbidade Administrativa", TOPICO_B: "Controle Externo"}


def _resposta(topico_id: UUID, acertou: bool, quando: datetime) -> RespostaHistorica:
    return RespostaHistorica(topico_id=topico_id, acertou=acertou, ocorrido_em=quando)


def _em(dia: date, hora: int = 12) -> datetime:
    """Meio-dia UTC de `dia` — longe da virada de fuso, para os testes que não testam fuso."""
    return datetime(dia.year, dia.month, dia.day, hora, tzinfo=UTC)


def test_semana_vazia() -> None:
    resumo = montar_resumo([], NOMES, INICIO, FIM)
    assert resumo.respostas == 0
    assert resumo.acertos is None  # sem resposta, sem intervalo fabricado (regra 11)
    assert resumo.topicos_novos == []
    assert resumo.para_rever == []
    assert resumo.conquista is None


def test_recorte_por_data_exclui_resposta_de_domingo_anterior() -> None:
    domingo_anterior = _em(date(2026, 9, 13))
    dentro = _em(date(2026, 9, 15))
    respostas = [
        _resposta(TOPICO_A, True, domingo_anterior),
        _resposta(TOPICO_A, True, dentro),
    ]
    resumo = montar_resumo(respostas, NOMES, INICIO, FIM)
    assert resumo.respostas == 1


def test_acertos_e_intervalo_de_wilson_sobre_a_semana() -> None:
    # 2 de 3 é exatamente o caso do Ruling 35 (`dominio.estatistica`, docs/fatias/10-painel.md
    # §2): pct 66,67, banda ampla (n pequeno) — nunca um "±" fixo.
    respostas = [
        _resposta(TOPICO_A, True, _em(date(2026, 9, 15))),
        _resposta(TOPICO_A, True, _em(date(2026, 9, 16))),
        _resposta(TOPICO_A, False, _em(date(2026, 9, 17))),
    ]
    resumo = montar_resumo(respostas, NOMES, INICIO, FIM)
    assert resumo.acertos is not None
    assert resumo.acertos.total == 3
    assert resumo.acertos.acertos == 2
    assert round(resumo.acertos.pct, 2) == 66.67
    assert round(resumo.acertos.inferior_pct, 2) == 20.77
    assert round(resumo.acertos.superior_pct, 2) == 93.85


def test_topico_novo_e_o_que_nunca_apareceu_antes_da_semana() -> None:
    respostas = [
        _resposta(TOPICO_A, True, _em(date(2026, 9, 10))),  # já visto antes da semana
        _resposta(TOPICO_A, True, _em(date(2026, 9, 15))),  # de novo, dentro da semana
        _resposta(TOPICO_B, True, _em(date(2026, 9, 16))),  # primeira vez, dentro da semana
    ]
    resumo = montar_resumo(respostas, NOMES, INICIO, FIM)
    assert resumo.topicos_novos == ["Controle Externo"]


def test_para_rever_no_maximo_5_na_ordem_do_erro_mais_recente() -> None:
    topicos = [uuid4() for _ in range(6)]
    nomes = {t: f"Tópico {i}" for i, t in enumerate(topicos)}
    # Horas 12..17 (UTC), todas dentro do mesmo dia mesmo convertidas para Brasília (UTC-3) —
    # t5 erra por último (mais recente), t0 é o mais antigo e fica de fora do teto de 5.
    respostas = [_resposta(t, False, _em(INICIO, hora=12 + i)) for i, t in enumerate(topicos)]
    resumo = montar_resumo(respostas, nomes, INICIO, FIM)
    assert len(resumo.para_rever) == MAXIMO_PARA_REVER
    esperado = [nomes[t] for t in reversed(topicos[1:])]
    assert [item.topico_nome for item in resumo.para_rever] == esperado


def test_conquista_so_aparece_com_topico_recem_dominado() -> None:
    antes = [_resposta(TOPICO_A, True, _em(date(2026, 9, 10))) for _ in range(2)]  # 2/2, <3
    na_semana = [_resposta(TOPICO_A, True, _em(date(2026, 9, 15)))]  # completa 3/3 -> dominado
    resumo = montar_resumo(antes + na_semana, NOMES, INICIO, FIM)
    assert resumo.conquista == "1 tópico dominado nesta semana"


def test_sem_conquista_quando_ninguem_cruza_o_limiar() -> None:
    respostas = [_resposta(TOPICO_A, True, _em(date(2026, 9, 15)))]
    resumo = montar_resumo(respostas, NOMES, INICIO, FIM)
    assert resumo.conquista is None


def test_fuso_de_brasilia_na_virada_do_dia() -> None:
    # 2026-09-14 02:00 UTC == 2026-09-13 23:00 em Brasília (UTC-3): ainda é domingo lá, então
    # fica fora da semana que começa segunda (Ruling 37, fuso fixo de São Paulo).
    fora_por_fuso = datetime(2026, 9, 14, 2, tzinfo=UTC)
    resumo = montar_resumo([_resposta(TOPICO_A, True, fora_por_fuso)], NOMES, INICIO, FIM)
    assert resumo.respostas == 0

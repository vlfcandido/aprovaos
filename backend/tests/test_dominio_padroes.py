# O que é: testes de `dominio/padroes.py` — a detecção de padrões de erro com suporte
# estatístico mínimo (RF-17, fatia 10 §4 do plano `docs/fatias/10-painel.md`). Os números de
# Wilson usados aqui são os mesmos conferidos à mão no brief da fatia. Quando ler: ao mudar o
# piso de suporte, o critério de sobreposição ou as faixas de horário.
from aprovaos.dominio.padroes import (
    MINIMO_RESPOSTAS_PADRAO,
    RespostaClassificada,
    detectar_padroes,
)


def _resposta(
    *,
    acertou: bool,
    materia: str = "Direito Administrativo",
    topico_nome: str = "Improbidade Administrativa",
    banca: str = "Cebraspe",
    hora_local: int = 10,
    energia: int | None = None,
) -> RespostaClassificada:
    return RespostaClassificada(
        acertou=acertou,
        materia=materia,
        topico_nome=topico_nome,
        banca=banca,
        hora_local=hora_local,
        energia=energia,
    )


def _grupo(quantidade: int, acertos: int, **campos: object) -> list[RespostaClassificada]:
    respostas = []
    for indice in range(quantidade):
        respostas.append(_resposta(acertou=indice < acertos, **campos))  # type: ignore[arg-type]
    return respostas


def test_lista_vazia_devolve_vazio() -> None:
    assert detectar_padroes([]) == []


def test_n_abaixo_do_piso_nunca_vira_padrao_mesmo_com_diferenca_grande() -> None:
    assert MINIMO_RESPOSTAS_PADRAO == 8
    # subgrupo de 7, 0 % de acerto, contra o geral de 20/27 (bem acima) — mesmo assim não conta.
    respostas = _grupo(7, 0, banca="FGV") + _grupo(20, 20, banca="Cebraspe")
    padroes = detectar_padroes(respostas)
    assert all(padrao.valor != "FGV" for padrao in padroes)


def test_diferenca_grande_e_com_suporte_vira_padrao() -> None:
    # base geral: 100 respostas, 80 acertos. Subgrupo (FGV, n=20): 6 acertos (30 %).
    # Wilson(6,20) = 14,55–51,90; Wilson(80,100) = 71,12–86,66 — não sobrepõe.
    respostas = _grupo(20, 6, banca="FGV") + _grupo(80, 74, banca="Cebraspe")
    padroes = detectar_padroes(respostas)
    assert len(padroes) == 1
    padrao = padroes[0]
    assert padrao.dimensao == "banca"
    assert padrao.valor == "FGV"
    assert padrao.proporcao.total == 20
    assert "FGV" in padrao.frase
    assert "%" in padrao.frase


def test_diferenca_pequena_com_sobreposicao_nao_vira_padrao() -> None:
    # base geral: 100 respostas, 75 acertos. Subgrupo (FGV, n=20): 14 acertos (70 %).
    # Wilson(14,20) = 48,10–85,45; Wilson(75,100) = 65,70–82,45 — sobrepõe.
    respostas = _grupo(20, 14, banca="FGV") + _grupo(80, 61, banca="Cebraspe")
    padroes = detectar_padroes(respostas)
    assert padroes == []


def test_dimensao_horario_usa_as_quatro_faixas_fixas() -> None:
    respostas = (
        _grupo(20, 4, hora_local=2)  # madrugada, 20 %
        + _grupo(80, 76, hora_local=14)  # tarde, 95 % — puxa a base para cima
    )
    padroes = detectar_padroes(respostas)
    valores = {padrao.valor for padrao in padroes if padrao.dimensao == "horario"}
    assert "madrugada" in valores


def test_dimensao_energia_ignora_respostas_sem_energia_declarada() -> None:
    respostas = (
        _grupo(20, 4, energia=1)  # baixa energia, 20 % de acerto
        + _grupo(80, 76, energia=5)  # alta energia, 95 % de acerto
        + _grupo(50, 25, energia=None)  # metade, sem energia — não pode poluir a dimensão
    )
    padroes = detectar_padroes(respostas)
    padroes_energia = [padrao for padrao in padroes if padrao.dimensao == "energia"]
    assert {padrao.valor for padrao in padroes_energia} == {"energia 1", "energia 5"}
    assert all(padrao.proporcao.total in (20, 80) for padrao in padroes_energia)


def test_dimensao_materia_agrupa_por_materia() -> None:
    respostas = _grupo(20, 4, materia="Improbidade Administrativa") + _grupo(
        80, 76, materia="Direito Constitucional"
    )
    padroes = detectar_padroes(respostas)
    valores = {padrao.valor for padrao in padroes if padrao.dimensao == "materia"}
    assert "Improbidade Administrativa" in valores


def test_dimensao_topico_agrupa_por_topico_nome_nao_por_materia() -> None:
    # mesma matéria nos dois grupos — só o `topico_nome` distingue os subgrupos, provando que a
    # dimensão "topico" não está lendo `materia` por engano (ADR-0036: "dado errado com cara de
    # certo", o desvio corrigido nesta fatia).
    respostas = _grupo(
        20, 4, materia="Direito Administrativo", topico_nome="Improbidade Administrativa"
    ) + _grupo(80, 76, materia="Direito Administrativo", topico_nome="Licitações")
    padroes = detectar_padroes(respostas)

    padrao_topico = next(p for p in padroes if p.dimensao == "topico")
    assert padrao_topico.valor == "Improbidade Administrativa"
    assert all(padrao.dimensao != "materia" for padrao in padroes)  # só 1 matéria, sem contraste


def test_topico_e_materia_saem_separados_quando_os_dois_passam_no_piso() -> None:
    # "Improbidade Administrativa" (tópico) tem suporte e diferença próprios; "Direito
    # Administrativo" (a matéria que o contém, somada a outro tópico fraco) também passa — as
    # duas dimensões têm de aparecer como padrões distintos, nunca um confundido com o outro.
    topico_fraco = _grupo(
        20, 6, materia="Direito Administrativo", topico_nome="Improbidade Administrativa"
    )
    outro_topico_da_mesma_materia = _grupo(
        20, 10, materia="Direito Administrativo", topico_nome="Legislação Especial"
    )
    materia_forte_de_fora = _grupo(60, 54, materia="Português", topico_nome="Crase")
    respostas = topico_fraco + outro_topico_da_mesma_materia + materia_forte_de_fora

    padroes = detectar_padroes(respostas)

    padrao_topico = next(
        p for p in padroes if p.dimensao == "topico" and p.valor == "Improbidade Administrativa"
    )
    padrao_materia = next(
        p for p in padroes if p.dimensao == "materia" and p.valor == "Direito Administrativo"
    )
    assert padrao_topico.proporcao.total == 20
    assert padrao_materia.proporcao.total == 40
    assert padrao_topico.valor != padrao_materia.valor


def test_ordem_por_maior_diferenca_primeiro() -> None:
    respostas = (
        _grupo(20, 6, banca="FGV")  # 30 %, diferença grande
        + _grupo(20, 14, hora_local=2)  # 70 %, diferença pequena (mas ainda sem sobreposição?)
        + _grupo(60, 54, banca="Cebraspe", hora_local=10)  # 90 %, maioria da base
    )
    padroes = detectar_padroes(respostas)
    assert len(padroes) >= 1
    maior_diferenca = max(abs(p.proporcao.pct - p.base.pct) for p in padroes)
    assert abs(padroes[0].proporcao.pct - padroes[0].base.pct) == maior_diferenca

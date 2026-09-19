# O que é: testes de `dominio/calibracao.py` — as regras R-0..R-9 (skill
# `calibracao-de-questoes`) contra a fixture sintética `knowledge/fixtures/calibracao/
# eventos-calibracao.json`, e a discriminação item-resto contra séries sintéticas inline
# declaradas no próprio teste. Quando ler: antes de mexer em qualquer regra R-n ou na fórmula de
# discriminação.
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from aprovaos.dominio.calibracao import (
    N_MINIMO_DISCRIMINACAO,
    AjusteCalibracao,
    MetricasQuestao,
    ReporteBruto,
    RespostaBruta,
    agregar_metricas,
    avaliar_questao,
    calcular_discriminacao,
    montar_fila_humana,
    retroalimentacao_do_lote,
)

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE = RAIZ / "knowledge/fixtures/calibracao/eventos-calibracao.json"


def _id(slug: str) -> UUID:
    """UUID determinístico a partir do `questao_id` textual da fixture (só para o teste)."""
    return uuid5(NAMESPACE_URL, f"questao:{slug}")


def _carregar_fixture() -> list[dict[str, Any]]:
    conteudo = json.loads(FIXTURE.read_text(encoding="utf-8"))
    questoes: list[dict[str, Any]] = conteudo["questoes"]
    assert conteudo["_o_que_e"].startswith("Fixture SINTÉTICA")
    return questoes


def _metricas_da_linha(linha: dict[str, Any]) -> MetricasQuestao:
    return MetricasQuestao(
        questao_id=_id(str(linha["questao_id"])),
        n=int(linha["n"]),
        acertos=int(linha["acertos"]),
        tempo_mediano_s=float(linha["tempo_mediano_s"]),
        confianca_alta_erro=int(linha["confianca_alta_erro"]),
        reportes=int(linha["reportes"]),
        reportes_motivos=list(linha.get("reportes_motivos", [])),
        dificuldade_est=float(linha["dificuldade_est"]),
        origem=linha["tipo_origem"],
        discriminacao="desconhecido",
    )


@pytest.mark.parametrize("linha", _carregar_fixture(), ids=lambda linha: str(linha["questao_id"]))
def test_avaliar_questao_bate_com_a_regra_esperada_da_fixture(linha: dict[str, Any]) -> None:
    """Cada questão da fixture sintética cai exatamente na regra que o cabeçalho `regra_esperada`
    documenta — é a mesma fixture que testou a skill na fase 4 (evidência), estendida com R-6/R-8/
    R-9.
    """
    metricas = _metricas_da_linha(linha)
    ajuste = avaliar_questao(metricas)
    assert ajuste.regra == linha["regra_esperada"]


def test_r1_gabarito_invertido_desliga_na_hora_com_a_evidencia_numerica() -> None:
    """q-52: erro_confiante = 44/137 ≈ 0,32 (o número que a skill cita como referência de gabarito
    invertido) — vira `despublicar`, nunca só `sinalizar`.
    """
    linhas = {str(linha["questao_id"]): linha for linha in _carregar_fixture()}
    ajuste = avaliar_questao(_metricas_da_linha(linhas["q-52"]))
    assert ajuste.acao == "despublicar"
    assert ajuste.regra == "R-1"
    assert "0.32" in ajuste.evidencia or "0,32" in ajuste.evidencia
    assert ajuste.efeito_colateral


def test_r2_lei_mudou_despublica_com_efeito_colateral_de_propagacao() -> None:
    """q-60: motivo de lei revogada — despublica e avisa para propagar a dispositivos citados."""
    linhas = {str(linha["questao_id"]): linha for linha in _carregar_fixture()}
    ajuste = avaliar_questao(_metricas_da_linha(linhas["q-60"]))
    assert ajuste.acao == "despublicar"
    assert ajuste.regra == "R-2"
    assert any("dispositivo" in efeito for efeito in ajuste.efeito_colateral)


def test_r3_conteudo_faltando_vale_mesmo_com_n_abaixo_do_piso() -> None:
    """q-58 tem n=24 (< 30) mas reporta conteúdo faltando: a skill diz que R-3 vale com qualquer
    n — não pode cair em R-0 (manter por amostra pequena).
    """
    linhas = {str(linha["questao_id"]): linha for linha in _carregar_fixture()}
    metricas = _metricas_da_linha(linhas["q-58"])
    assert metricas.n < N_MINIMO_DISCRIMINACAO
    ajuste = avaliar_questao(metricas)
    assert ajuste.acao == "despublicar"
    assert ajuste.regra == "R-3"


def test_r4_dificil_e_legitima_nunca_entra_na_fila_humana() -> None:
    """q-53: 16 % de acerto, erro confiante baixo (0,07), reporte único de 'muito difícil' — é
    difícil, não errada (skill, seção "Erros que estas regras existem para evitar").
    """
    linhas = {str(linha["questao_id"]): linha for linha in _carregar_fixture()}
    metricas = _metricas_da_linha(linhas["q-53"])
    ajuste = avaliar_questao(metricas)
    assert ajuste.acao == "ajustar"
    assert ajuste.regra == "R-4"
    fila, adiada = montar_fila_humana([ajuste], {metricas.questao_id: metricas})
    assert fila == []
    assert adiada == []


def test_r0_amostra_pequena_nunca_declara_discriminacao() -> None:
    """g-1041: n=8 — mantém e a discriminação fica `'desconhecido'`, nunca um número."""
    linhas = {str(linha["questao_id"]): linha for linha in _carregar_fixture()}
    ajuste = avaliar_questao(_metricas_da_linha(linhas["g-1041"]))
    assert ajuste.acao == "manter"
    assert ajuste.regra == "R-0"
    assert ajuste.discriminacao == "desconhecido"


def test_r5_inedita_trivial_despublica_e_gera_retroalimentacao() -> None:
    """g-1077: 98,6 % de acerto, n>=100, inédita — não conta como cobertura do gerador."""
    linhas = {str(linha["questao_id"]): linha for linha in _carregar_fixture()}
    metricas = _metricas_da_linha(linhas["g-1077"])
    ajuste = avaliar_questao(metricas)
    assert ajuste.acao == "despublicar"
    assert ajuste.regra == "R-5"
    retro = retroalimentacao_do_lote([ajuste])
    assert len(retro) == 1
    assert retro[0].questao_id == metricas.questao_id


def test_fila_humana_corta_em_20_minutos_e_declara_o_resto_como_adiada() -> None:
    """Cinco `sinalizar` (R-8) de `MINUTOS_POR_ITEM_FILA` cada — só quatro cabem em 20 min; o
    quinto vira adiada, nunca some silenciosamente.
    """
    metricas_por_id = {}
    ajustes = []
    for indice in range(5):
        questao_id = _id(f"sinalizada-{indice}")
        metricas = MetricasQuestao(
            questao_id=questao_id,
            n=50,
            acertos=35,
            tempo_mediano_s=30.0,
            confianca_alta_erro=1,
            reportes=2,
            reportes_motivos=["motivo variado", "outro motivo"],
            dificuldade_est=0.3,
            origem="original",
            discriminacao="desconhecido",
        )
        metricas_por_id[questao_id] = metricas
        ajustes.append(avaliar_questao(metricas))
    assert {ajuste.regra for ajuste in ajustes} == {"R-8"}
    fila, adiada = montar_fila_humana(ajustes, metricas_por_id)
    assert sum(item.minutos_estimados for item in fila) <= 20
    assert len(fila) + len(adiada) == 5
    assert len(adiada) >= 1


def test_discriminacao_desconhecida_abaixo_do_piso_de_n() -> None:
    """Série SINTÉTICA de 10 respostas (< 30): mesmo com correlação perfeita, a amostra é
    pequena demais para declarar um número.
    """
    respostas = [
        RespostaBruta(questao_id=_id("x"), usuario_id=_id(f"u{i}"), acertou=i % 2 == 0)
        for i in range(10)
    ]
    desempenho = {_id(f"u{i}"): (float(i % 2 == 0), 1) for i in range(10)}
    resultado = calcular_discriminacao(respostas, desempenho)
    assert resultado == "desconhecido"


def test_discriminacao_alta_quando_quem_acerta_o_item_tambem_vai_bem_no_resto() -> None:
    """Série SINTÉTICA de 40 respondentes: os 20 com melhor desempenho no resto da janela
    acertam este item; os 20 piores erram — discriminação deve ser positiva e alta (> 0,5).
    """
    desempenho_resto = {_id(f"bom-{i}"): (0.9, 20) for i in range(20)} | {
        _id(f"ruim-{i}"): (0.1, 20) for i in range(20)
    }
    respostas = [
        RespostaBruta(questao_id=_id("y"), usuario_id=_id(f"bom-{i}"), acertou=True)
        for i in range(20)
    ] + [
        RespostaBruta(questao_id=_id("y"), usuario_id=_id(f"ruim-{i}"), acertou=False)
        for i in range(20)
    ]
    resultado = calcular_discriminacao(respostas, desempenho_resto)
    assert isinstance(resultado, float)
    assert resultado > 0.5


def test_discriminacao_desconhecida_sem_variancia_no_resto() -> None:
    """Série SINTÉTICA de 40 respondentes com o MESMO desempenho no resto (ex.: uma única aluna
    respondendo tudo) — sem variância para correlacionar, o resultado é honesto: desconhecido,
    nunca `NaN`/`0.0` fabricado.
    """
    desempenho_resto = {_id(f"u-{i}"): (0.5, 10) for i in range(40)}
    respostas = [
        RespostaBruta(questao_id=_id("z"), usuario_id=_id(f"u-{i}"), acertou=i % 2 == 0)
        for i in range(40)
    ]
    resultado = calcular_discriminacao(respostas, desempenho_resto)
    assert resultado == "desconhecido"


def test_agregar_metricas_calcula_discriminacao_a_partir_de_respostas_cruas() -> None:
    """`agregar_metricas` é o ponto único que cruza `RespostaBruta` de TODAS as questões da janela
    para montar o desempenho-resto de cada respondente, questão por questão — evita que quem
    chama tenha de calcular isso na mão.
    """
    questao_alvo = _id("alvo")
    outras = [_id("outra-1"), _id("outra-2")]
    respostas: list[RespostaBruta] = []
    for i in range(30):
        bom = i < 15
        usuario_id = _id(f"u{i}")
        respostas.append(RespostaBruta(questao_id=questao_alvo, usuario_id=usuario_id, acertou=bom))
        for outra in outras:
            respostas.append(RespostaBruta(questao_id=outra, usuario_id=usuario_id, acertou=bom))
    metricas = agregar_metricas(
        respostas,
        reportes=[],
        origem_por_questao={questao_alvo: "original"},
        dificuldade_por_questao={},
    )
    alvo = next(item for item in metricas if item.questao_id == questao_alvo)
    assert alvo.n == 30
    assert alvo.acertos == 15
    assert isinstance(alvo.discriminacao, float)
    assert alvo.discriminacao > 0.9


def test_agregar_metricas_inclui_questao_so_reportada_sem_nenhuma_resposta() -> None:
    """Uma questão reportada por conteúdo faltando antes de qualquer resposta registrada (n=0)
    ainda precisa ser avaliada — é o caso que R-3 existe para cobrir "com qualquer n".
    """
    questao_id = _id("so-reportada")
    metricas = agregar_metricas(
        respostas=[],
        reportes=[ReporteBruto(questao_id=questao_id, motivo="faltou o texto de apoio")],
        origem_por_questao={questao_id: "original"},
        dificuldade_por_questao={},
    )
    assert len(metricas) == 1
    assert metricas[0].n == 0
    ajuste = avaliar_questao(metricas[0])
    assert ajuste.acao == "despublicar"
    assert ajuste.regra == "R-3"


def test_ajuste_calibracao_e_pydantic_e_serializa() -> None:
    """`AjusteCalibracao` é o contrato de saída — precisa serializar para o relatório do comando."""
    ajuste = AjusteCalibracao(
        questao_id=_id("a"),
        acao="manter",
        regra="R-9",
        evidencia="acerto=0.70, erro_confiante=0.04, taxa_reporte=0.00",
        efeito_colateral=[],
        dificuldade_real=0.30,
        discriminacao="desconhecido",
        n=180,
    )
    despejo = ajuste.model_dump(mode="json")
    assert despejo["acao"] == "manter"

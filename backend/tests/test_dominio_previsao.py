# O que é: testes de `dominio/previsao.py` — a previsão de nota v0 (RF-18, fatia 10 §5 do plano
# `docs/fatias/10-painel.md`). Sem banco: `DesempenhoMateria` construído à mão com proporções já
# calculadas por `intervalo_wilson`. Quando ler: ao mudar o critério de confiança ou como o corte
# histórico entra na comparação.
import pytest

from aprovaos.dominio.estatistica import intervalo_wilson
from aprovaos.dominio.previsao import DesempenhoMateria, prever_nota

#: Um dígito, ponto, dígito — o formato decimal que não pode aparecer na tela em pt-BR.
_TEM_PONTO_DECIMAL = __import__("re").compile(r"\d\.\d")


def test_materia_sem_dado_nao_vira_zero_nem_entra_na_media() -> None:
    com_dado = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(80, 100), peso_questoes=5
    )
    sem_dado = DesempenhoMateria(materia="Direito Constitucional", proporcao=None, peso_questoes=5)

    previsao = prever_nota([com_dado, sem_dado])

    assert previsao.nota_pct == pytest.approx(80.0)
    assert previsao.materias_sem_dado == ["Direito Constitucional"]


def test_peso_maior_puxa_a_nota_para_perto_de_si() -> None:
    peso_alto = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(90, 100), peso_questoes=18
    )
    peso_baixo = DesempenhoMateria(
        materia="Português", proporcao=intervalo_wilson(30, 100), peso_questoes=2
    )

    previsao = prever_nota([peso_alto, peso_baixo])

    # média simples seria 60; ponderada por peso deve ficar bem mais perto de 90.
    assert previsao.nota_pct > 75.0


def test_banda_estreita_com_muito_dado_da_confianca_alta() -> None:
    materia = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(900, 1000), peso_questoes=10
    )
    previsao = prever_nota([materia])
    assert previsao.nota_superior_pct - previsao.nota_inferior_pct <= 10
    assert previsao.confianca == "alta"


def test_pouca_cobertura_da_confianca_baixa() -> None:
    com_dado = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(3, 5), peso_questoes=2
    )
    sem_dado_1 = DesempenhoMateria(materia="Português", proporcao=None, peso_questoes=9)
    sem_dado_2 = DesempenhoMateria(materia="Raciocínio Lógico", proporcao=None, peso_questoes=9)

    previsao = prever_nota([com_dado, sem_dado_1, sem_dado_2])
    assert previsao.confianca == "baixa"


def test_porque_concorda_o_numero_de_questoes_da_materia_de_maior_peso() -> None:
    """Defeito reproduzido no navegador (fatia 14): "pesa mais (1 questões)" — sem concordância.
    Com peso 1, o texto tem que dizer "1 questão"; com mais de uma, "N questões"."""
    materia_peso_um = DesempenhoMateria(
        materia="Redação", proporcao=intervalo_wilson(1, 1), peso_questoes=1
    )
    previsao = prever_nota([materia_peso_um])
    assert "1 questão)" in previsao.porque
    assert "1 questões)" not in previsao.porque

    materia_peso_dois = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(8, 10), peso_questoes=2
    )
    previsao_plural = prever_nota([materia_peso_dois])
    assert "2 questões)" in previsao_plural.porque


def test_probabilidade_lacuna_sem_codigo_interno_de_pendencia() -> None:
    """Defeito reproduzido no navegador (fatia 14): `(P-17/P-39)` vazava na tela da aluna."""
    materia = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(80, 100), peso_questoes=10
    )
    previsao = prever_nota([materia], corte_historico_pct=None)
    assert previsao.probabilidade_lacuna is not None
    assert "P-" not in previsao.probabilidade_lacuna


def test_sem_corte_historico_e_lacuna_declarada_sem_probabilidade() -> None:
    materia = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(80, 100), peso_questoes=10
    )
    previsao = prever_nota([materia], corte_historico_pct=None)
    assert previsao.corte_historico_pct is None
    assert previsao.probabilidade_lacuna is not None
    assert "nota de corte" in previsao.probabilidade_lacuna


def test_com_corte_a_comparacao_sai_pela_banda_nao_pelo_ponto() -> None:
    # nota ~66,7 (2 de 3), banda de Wilson bem larga (20,8 a 93,9) por causa do n pequeno.
    # pelo ponto, corte=80 pareceria "abaixo" (66,7 < 80); mas 80 está dentro da banda
    # (20,8–93,9), então a leitura honesta é "em cima do corte", não "abaixo".
    materia = DesempenhoMateria(
        materia="Direito Administrativo", proporcao=intervalo_wilson(2, 3), peso_questoes=10
    )
    previsao = prever_nota([materia], corte_historico_pct=80.0)

    assert previsao.probabilidade_lacuna is None
    assert previsao.nota_pct < 80.0
    assert "em cima do corte" in previsao.porque


def test_porque_usa_virgula_decimal_e_a_lacuna_comeca_maiuscula() -> None:
    """Número em pt-BR e frase com inicial maiúscula — as duas aparecem na tela da aluna.

    Achado olhando o painel renderizado: no mesmo parágrafo saíam "61,6 %" (vírgula) e "banda de
    62.9 p.p." (ponto), e a lacuna da probabilidade começava em minúscula mesmo sendo a primeira
    palavra de um período. Detalhe pequeno que faz o produto parecer descuidado justamente onde
    ele pede confiança. A largura da banda saiu do texto (o jargão "p.p." não era lido pela
    aluna), mas o corte histórico continua sendo um decimal escrito em português.
    """
    materias = [
        DesempenhoMateria(
            materia="Noções de Direito Administrativo",
            proporcao=intervalo_wilson(2, 3),
            peso_questoes=1,
        ),
        DesempenhoMateria(materia="Noções de Informática", proporcao=None, peso_questoes=1),
    ]
    previsao = prever_nota(materias, corte_historico_pct=61.6)

    assert "61,6 %" in previsao.porque
    assert not _TEM_PONTO_DECIMAL.search(previsao.porque), previsao.porque

    sem_corte = prever_nota(materias)
    assert sem_corte.probabilidade_lacuna is not None
    assert sem_corte.probabilidade_lacuna[0].isupper(), sem_corte.probabilidade_lacuna


# ---------------------------------------------------------------------------
# O texto que a aluna lê (o dono leu o painel e disse "ruim de ler")
# ---------------------------------------------------------------------------

#: Vocabulário de quem construiu o cálculo — nenhum deles pode chegar à tela da aluna.
_JARGAO = ("p.p.", "banda", "Wilson", "suporte estatístico", "intervalo de confiança", "n=")


def _textos(previsao: object) -> str:
    """Junta tudo que a previsão manda para a tela, para varrer jargão de uma vez só."""
    partes = [
        previsao.porque,  # type: ignore[attr-defined]
        previsao.o_que_falta or "",  # type: ignore[attr-defined]
        previsao.probabilidade_lacuna or "",  # type: ignore[attr-defined]
    ]
    return " ".join(partes)


def test_previsao_sem_jargao_de_quem_construiu_o_calculo() -> None:
    """O conteúdo estava certo e o vocabulário errado: "banda de 66,1 p.p." não é português dela."""
    materias = [
        DesempenhoMateria(
            materia="Noções de Direito Administrativo",
            proporcao=intervalo_wilson(2, 3),
            peso_questoes=1,
        ),
        DesempenhoMateria(materia="Língua Portuguesa", proporcao=None, peso_questoes=1),
    ]
    previsao = prever_nota(materias)

    texto = _textos(previsao)
    for termo in _JARGAO:
        assert termo not in texto, f"{termo!r} vazou para a tela: {texto}"


def test_faixa_larga_marca_a_previsao_como_incerta() -> None:
    """Com banda larga o ponto estimado engana: quem lidera o bloco é a incerteza, não o número."""
    pouco_dado = prever_nota(
        [
            DesempenhoMateria(
                materia="Direito Administrativo", proporcao=intervalo_wilson(2, 3), peso_questoes=1
            ),
            DesempenhoMateria(materia="Língua Portuguesa", proporcao=None, peso_questoes=1),
        ]
    )
    assert pouco_dado.incerta is True

    muito_dado = prever_nota(
        [
            DesempenhoMateria(
                materia="Direito Administrativo",
                proporcao=intervalo_wilson(900, 1000),
                peso_questoes=10,
            )
        ]
    )
    assert muito_dado.incerta is False


def test_o_que_falta_nomeia_as_materias_em_branco_como_acao() -> None:
    """A lacuna declarada continua declarada — dita como o próximo passo, não como reclamação."""
    previsao = prever_nota(
        [
            DesempenhoMateria(
                materia="Direito Administrativo", proporcao=intervalo_wilson(8, 10), peso_questoes=1
            ),
            DesempenhoMateria(materia="Língua Portuguesa", proporcao=None, peso_questoes=1),
            DesempenhoMateria(materia="Matemática", proporcao=None, peso_questoes=1),
        ]
    )

    assert previsao.o_que_falta is not None
    assert "Língua Portuguesa e Matemática" in previsao.o_que_falta
    assert previsao.o_que_falta.startswith("Responda")


def test_o_que_falta_existe_mesmo_com_confianca_alta_se_falta_materia() -> None:
    """Confiança alta não apaga a matéria em branco: a lacuna some do texto e o produto mente."""
    previsao = prever_nota(
        [
            DesempenhoMateria(
                materia="Direito Administrativo",
                proporcao=intervalo_wilson(900, 1000),
                peso_questoes=9,
            ),
            DesempenhoMateria(materia="Língua Portuguesa", proporcao=None, peso_questoes=1),
        ]
    )

    assert previsao.confianca == "alta"
    assert previsao.o_que_falta is not None
    assert "Língua Portuguesa" in previsao.o_que_falta


def test_sem_nada_faltando_o_caminho_nao_e_inventado() -> None:
    """Confiança alta e prova inteira medida: não há o que pedir, e pedir seria ruído."""
    previsao = prever_nota(
        [
            DesempenhoMateria(
                materia="Direito Administrativo",
                proporcao=intervalo_wilson(900, 1000),
                peso_questoes=10,
            )
        ]
    )

    assert previsao.o_que_falta is None


def test_porque_nao_diz_que_uma_materia_pesa_mais_quando_todas_pesam_igual() -> None:
    """Com peso uniforme (P-39 no edital real), "pesa mais" era o primeiro nome da lista.

    Dado errado com cara de certo (ADR-0036): a tela dizia "Noções de Direito Administrativo pesa
    mais (1 questão)" quando as nove matérias pesavam 1 — a matéria não pesa mais, ela só foi a
    primeira do `max()`.
    """
    previsao = prever_nota(
        [
            DesempenhoMateria(
                materia="Noções de Direito Administrativo",
                proporcao=intervalo_wilson(2, 3),
                peso_questoes=1,
            ),
            DesempenhoMateria(
                materia="Noções de Informática", proporcao=intervalo_wilson(1, 2), peso_questoes=1
            ),
        ]
    )

    assert "Noções de Direito Administrativo" not in previsao.porque
    assert "mais questões na prova" not in previsao.porque

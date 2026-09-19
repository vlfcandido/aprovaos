# O que é: testes de `dominio.sumula` — extração de súmula (STF e STJ) para o dossiê de tópico,
# contra as fixtures reais em `knowledge/fixtures/juridico/` (índices STF, três páginas de
# súmula STF já baixadas, PDF único de verbetes do STJ). Puro, sem I/O: os testes leem os
# arquivos, as funções só recebem `str`. Quando ler: ao mudar a extração de súmula ou investigar
# por que uma súmula pedida virou lacuna.
from pathlib import Path

import pytest

from aprovaos.dominio.erros import SumulaNaoEncontrada
from aprovaos.dominio.sumula import (
    extrair_sumulas_stj,
    extrair_texto_sumula_stf,
    resolver_id_interno_stf,
)

RAIZ = Path(__file__).resolve().parents[2]
_JURIDICO = RAIZ / "knowledge/fixtures/juridico"


def _ler(nome: str) -> str:
    return (_JURIDICO / nome).read_text(encoding="utf-8", errors="replace")


INDICE_SUMULAS = _ler("stf_indice_sumulas.html")
INDICE_VINCULANTES = _ler("stf_indice_sumulas_vinculantes.html")
HTML_SUMULA_473 = _ler("stf_sumula_473.html")
HTML_SV_1 = _ler("stf_sumula_vinculante_1.html")
HTML_SV_11 = _ler("stf_sumula_vinculante_11.html")


def _texto_stj() -> str:
    """Extrai o texto cru do PDF único de verbetes do STJ (a leitura do PDF é I/O — feita aqui,
    no teste, para manter `dominio.sumula` puro; o motor faz o mesmo antes de chamar o domínio).
    """
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(_JURIDICO / "stj_sumulas_verbetes.pdf"))
    return "".join(pagina.get_textpage().get_text_range() for pagina in pdf)


TEXTO_PDF_STJ = _texto_stj()


class TestResolverIdInternoStf:
    """`resolver_id_interno_stf`: índice → id interno da URL da súmula, nunca o número em si."""

    def test_resolve_sumula_comum_pelo_indice(self) -> None:
        assert resolver_id_interno_stf(INDICE_SUMULAS, 473, vinculante=False) == "1602"

    def test_resolve_sumula_vinculante_pelo_indice(self) -> None:
        assert resolver_id_interno_stf(INDICE_VINCULANTES, 1, vinculante=True) == "1185"
        assert resolver_id_interno_stf(INDICE_VINCULANTES, 11, vinculante=True) == "1220"

    def test_sumula_vinculante_cancelada_levanta_sumula_nao_encontrada(self) -> None:
        """SV 9 está `(cancelada)` no índice — nunca resolve como se fosse vigente."""
        with pytest.raises(SumulaNaoEncontrada, match="cancelada"):
            resolver_id_interno_stf(INDICE_VINCULANTES, 9, vinculante=True)

    def test_sumula_comum_superada_levanta_sumula_nao_encontrada(self) -> None:
        """Súmula 3 está `(superada)` no índice — nunca resolve como se fosse vigente."""
        with pytest.raises(SumulaNaoEncontrada, match="superada"):
            resolver_id_interno_stf(INDICE_SUMULAS, 3, vinculante=False)

    def test_numero_ausente_do_indice_levanta_sumula_nao_encontrada(self) -> None:
        with pytest.raises(SumulaNaoEncontrada):
            resolver_id_interno_stf(INDICE_SUMULAS, 999_999, vinculante=False)

    def test_nao_confunde_sumula_9_com_sumula_90_ou_99(self) -> None:
        """O rótulo casado é o número inteiro, não um prefixo dele."""
        assert resolver_id_interno_stf(INDICE_VINCULANTES, 1, vinculante=True) != (
            resolver_id_interno_stf(INDICE_VINCULANTES, 10, vinculante=True)
        )


class TestExtrairTextoSumulaStf:
    """`extrair_texto_sumula_stf`: texto integral do primeiro bloco de conteúdo da página."""

    def test_extrai_texto_integral_da_sumula_473_formato_p(self) -> None:
        texto = extrair_texto_sumula_stf(HTML_SUMULA_473, numero=473, vinculante=False)

        assert texto.startswith("A administração pode anular seus próprios atos")
        assert texto.endswith("a apreciação judicial.")
        assert "<" not in texto

    def test_extrai_texto_integral_da_sv1_formato_div(self) -> None:
        """A página de SV é `<div>` dentro de `.parCOM`, não `<p>` — o extrator trata os dois."""
        texto = extrair_texto_sumula_stf(HTML_SV_1, numero=1, vinculante=True)

        assert texto == (
            "Ofende a garantia constitucional do ato jurídico perfeito a decisão que, sem "
            "ponderar as circunstâncias do caso concreto, desconsidera a validez e a eficácia "
            "de acordo constante de termo de adesão instituído pela Lei Complementar 110/2001."
        )

    def test_extrai_texto_integral_da_sv11(self) -> None:
        texto = extrair_texto_sumula_stf(HTML_SV_11, numero=11, vinculante=True)

        assert texto.startswith("Só é lícito o uso de algemas")
        assert "responsabilidade civil do Estado." in texto

    def test_pagina_de_outra_sumula_levanta_sumula_nao_encontrada(self) -> None:
        """Pedir a SV 1 contra a página da SV 11 não devolve texto de outra súmula por engano."""
        with pytest.raises(SumulaNaoEncontrada):
            extrair_texto_sumula_stf(HTML_SV_11, numero=1, vinculante=True)

    def test_numero_comum_pedido_contra_pagina_vinculante_nao_resolve(self) -> None:
        with pytest.raises(SumulaNaoEncontrada):
            extrair_texto_sumula_stf(HTML_SV_1, numero=1, vinculante=False)


class TestExtrairSumulasStj:
    """`extrair_sumulas_stj`: todas as súmulas vigentes do PDF único, por número."""

    def test_extrai_as_sumulas_pedidas_desta_fatia(self) -> None:
        sumulas = extrair_sumulas_stj(TEXTO_PDF_STJ)

        assert sumulas[98] == (
            "Embargos de declaração manifestados com notório propósito de prequestionamento "
            "não tem caráter protelatório."
        )
        assert sumulas[216] == (
            "A tempestividade de recurso interposto no Superior Tribunal de Justiça é aferida "
            "pelo registro no protocolo da secretaria e não pela data da entrega na agência do "
            "correio."
        )
        assert sumulas[651].startswith("Compete à autoridade administrativa aplicar")
        assert sumulas[634] == (
            "Ao particular aplica-se o mesmo regime prescricional previsto na Lei de "
            "Improbidade Administrativa para o agente público."
        )
        assert sumulas[347] == (
            "O conhecimento de recurso de apelação do réu independe de sua prisão."
        )

    def test_sumula_cancelada_nao_aparece_no_resultado(self) -> None:
        """Súmula 418 do STJ está cancelada (medido no PDF) — não pode ser servida como vigente."""
        sumulas = extrair_sumulas_stj(TEXTO_PDF_STJ)

        assert 418 not in sumulas

    def test_extrai_um_numero_alto_e_um_baixo_sem_misturar_textos(self) -> None:
        sumulas = extrair_sumulas_stj(TEXTO_PDF_STJ)

        assert sumulas[676].startswith("Em razão da Lei n. 13.964/2019")
        assert sumulas[7] == "A pretensão de simples reexame de prova não enseja recurso especial."

    def test_total_de_sumulas_vigentes_extraidas_bate_com_a_medicao_desta_fatia(self) -> None:
        """641 verbetes vigentes medidos nesta fatia contra o PDF real (676 numerados, 35
        cancelados) — trava de regressão: se o parser passar a capturar canceladas ou perder
        vigentes, este número muda e o teste avisa.
        """
        sumulas = extrair_sumulas_stj(TEXTO_PDF_STJ)

        assert len(sumulas) == 641

    def test_extrai_verbete_com_citacao_sem_repetir_o_numero_da_sumula(self) -> None:
        """Formato mais recente (~60 verbetes): a citação não repete "SÚMULA <n>," antes do
        órgão — só `"(<ÓRGÃO>, julgado em ...)"`. Um regex que exigisse o número repetido
        perderia esses verbetes inteiros."""
        sumulas = extrair_sumulas_stj(TEXTO_PDF_STJ)

        assert sumulas[676] == (
            "Em razão da Lei n. 13.964/2019, não é mais possível ao juiz, de ofício, decretar "
            "ou converter prisão em flagrante em prisão preventiva."
        )

    def test_extrai_verbete_cuja_propria_redacao_contem_a_palavra_julgado(self) -> None:
        """Verbete 487: o enunciado tem "transitadas em julgado em data anterior" sem
        parênteses — não pode ser confundido com a citação que fecha o verbete."""
        sumulas = extrair_sumulas_stj(TEXTO_PDF_STJ)

        assert sumulas[487] == (
            "O parágrafo único do art. 741 do CPC não se aplica às sentenças transitadas em "
            "julgado em data anterior à da sua vigência."
        )

    def test_extrai_verbete_com_nota_de_modificacao_de_texto_posterior(self) -> None:
        """Verbete 111 tem uma nota "MODIFICAÇÃO DE TEXTO ... REDAÇÃO ANTERIOR (...)" depois da
        citação vigente — a nota histórica não pode vazar para o texto devolvido."""
        sumulas = extrair_sumulas_stj(TEXTO_PDF_STJ)

        assert sumulas[111] == (
            "Os honorários advocatícios, nas ações previdenciárias, não incidem sobre as "
            "prestações vencidas após a sentença."
        )

# O que é: testes do corte de página pública e dos textos derivados do dado (fatia 13, passo 1).
# Quando ler: ao mexer em `dominio/pagina_publica.py` ou no corte da família A.
from datetime import date

import pytest
from pydantic import ValidationError

from aprovaos.dominio.pagina_publica import (
    DESCRICAO_MAXIMO,
    DESCRICAO_MINIMO,
    PaginaPublica,
    ajustar_descricao,
    cabe_em_pagina,
    montar_titulo_de_topico,
)

DESCRICAO_VALIDA = "x" * 140


def test_quatro_questoes_sem_dossie_nao_cabe() -> None:
    assert cabe_em_pagina(4, tem_dossie=False) is False


def test_cinco_questoes_cabe() -> None:
    assert cabe_em_pagina(5, tem_dossie=False) is True


def test_zero_questoes_com_dossie_cabe() -> None:
    assert cabe_em_pagina(0, tem_dossie=True) is True


def test_zero_questoes_sem_dossie_nao_cabe() -> None:
    assert cabe_em_pagina(0, tem_dossie=False) is False


def test_titulo_com_banca_conhecida() -> None:
    titulo = montar_titulo_de_topico(
        "Direito Administrativo", "Improbidade administrativa", "cebraspe", 6
    )
    assert "cebraspe" in titulo
    assert "Improbidade administrativa" in titulo
    assert "Direito Administrativo" in titulo
    assert "6 questões classificadas" in titulo


@pytest.mark.parametrize("banca", [None, "desconhecido", ""])
def test_titulo_sem_banca_quando_desconhecida(banca: str | None) -> None:
    titulo = montar_titulo_de_topico("Direito Constitucional", "Direitos e garantias", banca, 8)
    assert "desconhecido" not in titulo.lower()
    assert "banca" not in titulo.lower()
    assert "Direitos e garantias" in titulo


def test_titulo_singular_com_uma_questao() -> None:
    titulo = montar_titulo_de_topico("Direito Penal", "Do crime", "cebraspe", 1)
    assert "1 questão classificada" in titulo
    assert "questões" not in titulo


def test_pagina_publica_aceita_descricao_na_faixa() -> None:
    pagina = PaginaPublica(
        caminho="/o-que-cai/cebraspe/direito-administrativo/improbidade",
        titulo="Improbidade administrativa (cebraspe): 6 questões | AprovaOS",
        descricao=DESCRICAO_VALIDA,
        h1="Improbidade administrativa",
        atualizada_em=date(2026, 9, 19),
    )
    assert pagina.canonica is None
    assert len(pagina.descricao) == 140


@pytest.mark.parametrize("tamanho", [DESCRICAO_MINIMO - 1, DESCRICAO_MAXIMO + 1])
def test_pagina_publica_rejeita_descricao_fora_da_faixa(tamanho: int) -> None:
    with pytest.raises(ValidationError):
        PaginaPublica(
            caminho="/o-que-cai/cebraspe/direito-administrativo/improbidade",
            titulo="título",
            descricao="x" * tamanho,
            h1="h1",
            atualizada_em=date(2026, 9, 19),
        )


def test_ajustar_descricao_completa_texto_curto() -> None:
    resultado = ajustar_descricao("Frase curta.")
    assert DESCRICAO_MINIMO <= len(resultado) <= DESCRICAO_MAXIMO
    assert resultado.startswith("Frase curta.")


def test_ajustar_descricao_nao_mexe_em_texto_ja_na_faixa() -> None:
    texto = "y" * 130
    assert ajustar_descricao(texto) == texto


def test_ajustar_descricao_corta_texto_longo_em_palavra_inteira() -> None:
    texto = "palavra " * 40  # bem acima de 160 caracteres
    resultado = ajustar_descricao(texto)
    assert DESCRICAO_MINIMO <= len(resultado) <= DESCRICAO_MAXIMO
    assert not resultado.endswith("palavr")  # nunca corta uma palavra ao meio
    assert resultado == resultado.strip()


def test_ajustar_descricao_normaliza_espacos() -> None:
    resultado = ajustar_descricao("a" * 60 + "   " + "b" * 60)
    assert "  " not in resultado

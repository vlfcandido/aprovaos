# O que é: a verificação automática de contraste do sistema de design — mede par a par, nos três
# temas, o que `web/static/css/tokens.css` declara, e reprova qualquer combinação abaixo do
# mínimo da WCAG 2.2 AA. Quando ler: ao criar cor nova, ao criar tema novo, ou quando um par
# reprovar (o conserto é o valor do token, nunca o mínimo do teste).
from pathlib import Path

import pytest

from aprovaos.dominio.contraste import (
    PARES_OBRIGATORIOS,
    ParDeCor,
    ler_escuro_automatico,
    ler_temas,
    medir_pares,
    razao_de_contraste,
)

TOKENS = Path(__file__).resolve().parents[2] / "web" / "static" / "css" / "tokens.css"
TEMAS_ESPERADOS = {"claro", "escuro", "sepia"}


def _css() -> str:
    return TOKENS.read_text(encoding="utf-8")


def test_razao_de_preto_sobre_branco_e_21() -> None:
    """O extremo conhecido da fórmula da WCAG — se este quebrar, a conta está errada."""
    assert razao_de_contraste("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)


def test_razao_de_cor_sobre_ela_mesma_e_1() -> None:
    """Texto da cor do fundo é invisível: razão 1."""
    assert razao_de_contraste("#2f46b8", "#2f46b8") == pytest.approx(1.0, abs=0.001)


def test_razao_e_simetrica() -> None:
    """A ordem dos argumentos não muda a medida (a fórmula usa maior/menor luminância)."""
    assert razao_de_contraste("#131b2e", "#f3f5f8") == pytest.approx(
        razao_de_contraste("#f3f5f8", "#131b2e")
    )


def test_forma_curta_de_hexadecimal_e_aceita() -> None:
    """`#fff` é o mesmo que `#ffffff` — o CSS aceita as duas, o medidor também."""
    assert razao_de_contraste("#fff", "#000") == pytest.approx(21.0, abs=0.01)


def test_os_tres_temas_existem_nos_tokens() -> None:
    """Claro, escuro e sépia são temas de primeira classe (sépia = leitura longa)."""
    assert set(ler_temas(_css())) == TEMAS_ESPERADOS


def test_tema_herda_o_que_nao_sobrescreve() -> None:
    """O escuro só redefine cor; espaço e tipografia continuam vindo do `:root`."""
    temas = ler_temas(_css())
    assert temas["escuro"]["--espaco-4"] == temas["claro"]["--espaco-4"]
    assert temas["escuro"]["--cor-fundo"] != temas["claro"]["--cor-fundo"]


def test_todo_tema_define_todas_as_cores_dos_pares() -> None:
    """Token faltando num tema vaza a cor de outro tema — o defeito é invisível em revisão."""
    temas = ler_temas(_css())
    usados = {nome for par in PARES_OBRIGATORIOS for nome in (par.texto, par.fundo)}
    for tema, valores in temas.items():
        faltando = sorted(nome for nome in usados if nome not in valores)
        assert not faltando, f"tema {tema}: sem valor para {faltando}"


def test_tema_escuro_automatico_espelha_o_fixado() -> None:
    """Quem nunca tocou no alternador vê o bloco da consulta de mídia; quem fixou vê o outro.

    São duas cópias da mesma paleta — e cópia é o que diverge. Uma cor corrigida num bloco e
    esquecida no outro é um defeito que só aparece na máquina de quem tem o sistema no escuro.
    """
    temas = ler_temas(_css())
    automatico = ler_escuro_automatico(_css())
    assert automatico, "o bloco @media (prefers-color-scheme: dark) sumiu dos tokens"
    divergentes = {
        token: (valor, temas["escuro"].get(token))
        for token, valor in automatico.items()
        if temas["escuro"].get(token) != valor
    }
    assert not divergentes, f"escuro automático diferente do fixado: {divergentes}"
    faltando = sorted(
        token
        for token, valor in temas["escuro"].items()
        if token not in automatico and temas["claro"].get(token) != valor
    )
    assert not faltando, f"o escuro automático não recebeu: {faltando}"


@pytest.mark.parametrize("par", PARES_OBRIGATORIOS, ids=lambda p: f"{p.texto}-sobre-{p.fundo}")
@pytest.mark.parametrize("tema", sorted(TEMAS_ESPERADOS))
def test_par_obrigatorio_atinge_o_minimo_aa(tema: str, par: ParDeCor) -> None:
    """WCAG 2.2 AA: 4,5:1 para texto normal, 3:1 para texto grande e limite de controle."""
    (medida,) = [m for m in medir_pares(ler_temas(_css()), (par,)) if m.tema == tema]
    assert medida.aprovado, (
        f"{tema}: {par.texto} sobre {par.fundo} = {medida.razao:.2f}:1, "
        f"mínimo {par.minimo}:1 ({par.onde})"
    )

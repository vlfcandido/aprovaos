# O que é: testes de `dominio.topico.nome_curto` — o rótulo legível derivado do nome literal do
# item do edital. Quando ler: ao mudar a regra de corte, sempre com exemplos reais do edital do
# TJ-PR/AOCP (`dev.db`, 23/09/2026), nunca inventados.
import pytest

from aprovaos.dominio.topico import nome_curto


@pytest.mark.parametrize(
    ("literal", "esperado"),
    [
        # Numeração do edital na frente: some.
        (
            "3 Princípios fundamentais da República Federativa do Brasil.",
            "Princípios fundamentais da República Federativa do Brasil",
        ),
        # Dois-pontos abrindo lista de subtemas: corta no dois-pontos.
        (
            "4 Atos administrativos: conceito; requisitos; atributos; classificações; espécies.",
            "Atos administrativos",
        ),
        (
            "Dos atos processuais: da forma, do tempo e do lugar; dos prazos; das nulidades.",
            "Dos atos processuais",
        ),
        # Subitem numerado embutido depois de ponto: corta antes dele.
        ("Provas. 6.1. Teoria geral das provas. 6.2. Meios de prova em espécie.", "Provas"),
        (
            "4 Direitos e garantias fundamentais. 4.1 Direitos e deveres individuais e coletivos.",
            "Direitos e garantias fundamentais",
        ),
        # Já é curto: só perde o ponto final.
        ("Ortografia.", "Ortografia"),
        ("Regra de três composta.", "Regra de três composta"),
        # Ponto dentro de número de lei não pode cortar.
        (
            "Estatuto da Pessoa com Deficiência (Lei nº 13.146/2015).",
            "Estatuto da Pessoa com Deficiência (Lei nº 13.146/2015)",
        ),
        (
            "Lei de Acesso à Informação (Lei nº 12.527/2011).",
            "Lei de Acesso à Informação (Lei nº 12.527/2011)",
        ),
    ],
)
def test_nome_curto_de_itens_reais_do_edital(literal: str, esperado: str) -> None:
    """Cada caso veio do edital real da piloto; nenhum foi inventado para o teste passar."""
    assert nome_curto(literal) == esperado


def test_nome_vazio_nao_quebra() -> None:
    """Nome vazio volta vazio — a tela decide o que mostrar, o domínio não inventa rótulo."""
    assert nome_curto("") == ""
    assert nome_curto("   ") == ""


def test_nunca_devolve_so_a_numeracao() -> None:
    """Se sobrar só numeração, devolve o literal: melhor feio do que vazio."""
    assert nome_curto("4.1") == "4.1"

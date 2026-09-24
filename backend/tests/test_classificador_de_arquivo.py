# O que é: testes do `ClassificadorDeArquivo` — a porta de classificação alimentada por um
# arquivo em vez da API do modelo, usada para curar sem gastar a cota do projeto (ADR-0054).
# Quando ler: ao mudar o formato do arquivo de classificação ou a marca de procedência.
import json
from pathlib import Path

import pytest

from aprovaos.motor.curadoria.classificacao import ItemParaClassificar, TopicoVocabulario
from aprovaos.motor.curadoria.classificador_arquivo import (
    MARCA_DE_PROCEDENCIA,
    ClassificadorDeArquivo,
    carregar_classificacoes,
)

VOCABULARIO = [
    TopicoVocabulario(
        slug="lp-01-ortografia", materia="Língua Portuguesa", texto_original="Ortografia."
    ),
    TopicoVocabulario(
        slug="inf-02-navegadores", materia="Noções de Informática", texto_original="Navegadores."
    ),
]
ITENS = [
    ItemParaClassificar(
        numero_item=1, comando="Julgue o item.", enunciado="A palavra «exceção» é grafada com ç."
    ),
    ItemParaClassificar(
        numero_item=2, comando="Julgue o item.", enunciado="O Chrome é um navegador."
    ),
]


def _arquivo(tmp_path: Path, classificacoes: list[dict[str, object]]) -> Path:
    caminho = tmp_path / "classificacao.json"
    caminho.write_text(
        json.dumps(
            {"classificado_por": "teste", "classificacoes": classificacoes}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    return caminho


@pytest.mark.anyio
async def test_classifica_pelos_itens_do_arquivo(tmp_path: Path) -> None:
    """Cada item recebe o tópico que o arquivo mandou, na mesma ordem da entrada."""
    caminho = _arquivo(
        tmp_path,
        [
            {
                "numero_item": 1,
                "topico_slug": "lp-01-ortografia",
                "evidencia": "grafia de «exceção»",
            },
            {"numero_item": 2, "topico_slug": "inf-02-navegadores", "evidencia": "cita o Chrome"},
        ],
    )
    classificador = ClassificadorDeArquivo(carregar_classificacoes(caminho))

    recebidas, rejeicoes = await classificador.classificar_lote(ITENS, VOCABULARIO)

    assert [c.numero_item for c in recebidas] == [1, 2]
    assert [c.topico_slug for c in recebidas] == ["lp-01-ortografia", "inf-02-navegadores"]
    assert rejeicoes == {}


@pytest.mark.anyio
async def test_evidencia_carrega_a_marca_de_procedencia(tmp_path: Path) -> None:
    """Quem olhar o banco depois vê que a decisão não veio do pipeline (decisão do dono)."""
    caminho = _arquivo(
        tmp_path, [{"numero_item": 1, "topico_slug": "lp-01-ortografia", "evidencia": "grafia"}]
    )
    classificador = ClassificadorDeArquivo(carregar_classificacoes(caminho))

    (recebida,), _ = await classificador.classificar_lote(ITENS[:1], VOCABULARIO)

    assert recebida.evidencia.startswith(MARCA_DE_PROCEDENCIA)
    assert "grafia" in recebida.evidencia


@pytest.mark.anyio
async def test_slug_fora_do_vocabulario_e_rejeitado_nao_gravado(tmp_path: Path) -> None:
    """Inventar slug é o defeito que o validador existe para impedir — vale para mim também."""
    caminho = _arquivo(
        tmp_path, [{"numero_item": 1, "topico_slug": "nao-existe", "evidencia": "chute"}]
    )
    classificador = ClassificadorDeArquivo(carregar_classificacoes(caminho))

    recebidas, rejeicoes = await classificador.classificar_lote(ITENS[:1], VOCABULARIO)

    assert recebidas == []
    assert 1 in rejeicoes
    assert "nao-existe" in rejeicoes[1]


@pytest.mark.anyio
async def test_item_ausente_do_arquivo_nao_vira_classificacao(tmp_path: Path) -> None:
    """Item que eu não classifiquei cai para regras pelo caminho normal do curador."""
    caminho = _arquivo(
        tmp_path, [{"numero_item": 1, "topico_slug": "lp-01-ortografia", "evidencia": "grafia"}]
    )
    classificador = ClassificadorDeArquivo(carregar_classificacoes(caminho))

    recebidas, _ = await classificador.classificar_lote(ITENS, VOCABULARIO)

    assert [c.numero_item for c in recebidas] == [1]


@pytest.mark.anyio
async def test_sem_topico_e_decisao_valida(tmp_path: Path) -> None:
    """`topico_slug: null` é "este item não é do edital dela" — decisão, não omissão."""
    caminho = _arquivo(
        tmp_path, [{"numero_item": 1, "topico_slug": None, "evidencia": "Direito do Trabalho"}]
    )
    classificador = ClassificadorDeArquivo(carregar_classificacoes(caminho))

    (recebida,), rejeicoes = await classificador.classificar_lote(ITENS[:1], VOCABULARIO)

    assert recebida.topico_slug is None
    assert rejeicoes == {}

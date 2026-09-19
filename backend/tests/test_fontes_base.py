# O que é: teste do passo 3 da V3 — o contrato `FonteColetavel` (`Novidade`, `ArquivoBaixado`,
# o `Protocol` e os erros tipados) em `aprovaos/motor/fontes/base.py`.
# Quando ler: ao mudar o contrato que toda fonte concreta do coletor (Cebraspe, passo 4) segue.
import hashlib
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from aprovaos.motor.fontes.base import ArquivoBaixado, FonteIndisponivel, FonteVetada, Novidade


def test_novidade_exige_campos() -> None:
    """`Novidade` valida com os campos do contrato e rejeita `tipo` fora do `Literal`."""
    novidade = Novidade(
        id="X/Y.pdf",
        tipo="prova",
        titulo="PROVA OBJETIVA – …",
        url="https://…",
        evento="X",
        publicado_em=datetime(2025, 10, 1, 11, 30, tzinfo=UTC),
    )
    assert novidade.id == "X/Y.pdf"
    assert novidade.tipo == "prova"
    assert novidade.publicado_em == datetime(2025, 10, 1, 11, 30, tzinfo=UTC)

    with pytest.raises(ValidationError):
        Novidade(
            id="X/Y.pdf",
            tipo="qualquer",
            titulo="PROVA OBJETIVA – …",
            url="https://…",
            evento="X",
            publicado_em=datetime(2025, 10, 1, 11, 30, tzinfo=UTC),
        )


def test_novidade_publicado_em_exige_aware_e_normaliza_utc() -> None:
    """`publicado_em` naive é rejeitado; aware em qualquer fuso é normalizado para UTC."""
    with pytest.raises(ValidationError):
        Novidade(
            id="X/Y.pdf",
            tipo="prova",
            titulo="PROVA OBJETIVA – …",
            url="https://…",
            evento="X",
            publicado_em=datetime(2025, 10, 1, 11, 30),  # naive
        )

    aware_utc = Novidade(
        id="X/Y.pdf",
        tipo="prova",
        titulo="PROVA OBJETIVA – …",
        url="https://…",
        evento="X",
        publicado_em=datetime(2025, 10, 1, 11, 30, tzinfo=UTC),
    )
    assert aware_utc.publicado_em == datetime(2025, 10, 1, 11, 30, tzinfo=UTC)

    fuso_menos_tres = timezone(timedelta(hours=-3))
    aware_outro_fuso = Novidade(
        id="X/Y.pdf",
        tipo="prova",
        titulo="PROVA OBJETIVA – …",
        url="https://…",
        evento="X",
        publicado_em=datetime(2025, 10, 1, 8, 30, tzinfo=fuso_menos_tres),
    )
    assert aware_outro_fuso.publicado_em == datetime(2025, 10, 1, 11, 30, tzinfo=UTC)


def test_arquivo_baixado_calcula_hash() -> None:
    """`ArquivoBaixado.de_conteudo` calcula `hash` (sha256) e `tamanho` (bytes) do conteúdo."""
    novidade = Novidade(
        id="X/Y.pdf",
        tipo="prova",
        titulo="PROVA OBJETIVA – …",
        url="https://…",
        evento="X",
        publicado_em=None,
    )
    conteudo = b"%PDF-1.4 conteudo de teste"

    arquivo = ArquivoBaixado.de_conteudo(novidade, conteudo)

    assert arquivo.hash == hashlib.sha256(conteudo).hexdigest()
    assert arquivo.tamanho == len(conteudo)
    assert arquivo.conteudo == conteudo
    assert arquivo.novidade == novidade


def test_erros_sao_tipados() -> None:
    """`FonteVetada` e `FonteIndisponivel` herdam de `RuntimeError`."""
    assert issubclass(FonteVetada, RuntimeError)
    assert issubclass(FonteIndisponivel, RuntimeError)

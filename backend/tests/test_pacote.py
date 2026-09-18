# O que é: teste do passo 1 da V1 — o pacote `aprovaos` existe e se identifica.
# Quando ler: ao mexer no esqueleto do backend (pyproject, layout do pacote).
import importlib


def test_pacote_importa() -> None:
    modulo = importlib.import_module("aprovaos")
    assert modulo.__doc__ is not None
    assert modulo.__doc__.startswith("AprovaOS")

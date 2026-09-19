# O que é: teste do passo 2 da V3 — a ficha da fonte Cebraspe em `knowledge/fontes.yaml` tem todos
# os campos que a skill `monitor-de-fontes` exige preenchidos, com evidência real em disco.
# Quando ler: ao editar a ficha da Cebraspe ou ao acrescentar uma fonte nova ao coletor.
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
FICHA = RAIZ / "knowledge" / "fontes.yaml"

# Campos exigidos pelo passo 1 ("Ficha da fonte") da skill `monitor-de-fontes`.
CAMPOS_OBRIGATORIOS = (
    "id",
    "nome",
    "url_lista",
    "formato",
    "o_que_publica",
    "identidade_do_item",
    "robots_txt",
    "termos_de_uso",
    "politica_coleta",
    "verificado_em",
    "evidencia",
    "status",
)
CAMPOS_POLITICA_COLETA = ("frequencia", "user_agent", "sem_login", "cache")


def _carregar_fichas() -> list[dict[str, Any]]:
    conteudo = yaml.safe_load(FICHA.read_text(encoding="utf-8"))
    assert isinstance(conteudo, list)
    return conteudo


def _ficha_cebraspe() -> dict[str, Any]:
    fichas = _carregar_fichas()
    candidatas = [ficha for ficha in fichas if ficha.get("id") == "cebraspe"]
    assert len(candidatas) == 1, "esperava exatamente uma ficha com id 'cebraspe'"
    return candidatas[0]


def test_ficha_completa() -> None:
    """Toda ficha da skill `monitor-de-fontes` tem os campos preenchidos, sem `desconhecido`."""
    ficha = _ficha_cebraspe()

    for campo in CAMPOS_OBRIGATORIOS:
        assert campo in ficha, f"campo obrigatório ausente: {campo}"
        assert ficha[campo] not in (None, "", "desconhecido"), f"campo vazio/desconhecido: {campo}"

    for campo in CAMPOS_POLITICA_COLETA:
        assert campo in ficha["politica_coleta"], f"politica_coleta sem {campo}"

    assert ficha["status"] == "ativa"
    assert "vlfcandido@gmail.com" in ficha["politica_coleta"]["user_agent"]
    assert "AprovaOS-coletor/0.1" in ficha["politica_coleta"]["user_agent"]

    evidencia = RAIZ / ficha["evidencia"]
    assert evidencia.is_file(), f"evidência não existe: {evidencia}"
    assert evidencia.stat().st_size > 0, f"evidência vazia: {evidencia}"

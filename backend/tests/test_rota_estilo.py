# O que é: testes de `GET /estilo`, a documentação viva do sistema de design — que ela só existe
# em `AMBIENTE=dev`, que mostra a tabela de contraste medida dos três temas, e que todo
# componente da biblioteca tem amostra nela. Quando ler: ao acrescentar componente ou tema.
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine

from aprovaos.config import Configuracoes
from aprovaos.dominio.contraste import PARES_OBRIGATORIOS
from aprovaos.main import criar_app

# Classes que a biblioteca oferece e que a amostra precisa mostrar. O contrato
# (`docs/08-sistema-de-design.md` §12) diz que componente fora da amostra não existe; aqui isso
# deixa de ser promessa e vira teste.
COMPONENTES_NA_AMOSTRA = (
    "btn primary",
    "chip warn",
    "why",
    "kpi",
    "intervalo",
    "seg",
    "entrada",
    "campo-erro",
    "esqueleto",
    "progresso",
    "anel",
    "materia-marca",
    "vazio",
    "tabela",
    "fchip",
    "tabular",
    "icone",
    "lateral__rotulo",
)


@pytest.fixture
def cliente_dev(config_teste: Configuracoes, engine: Engine) -> Iterator[TestClient]:
    """Cliente contra uma app em `AMBIENTE=dev`, o único em que `/estilo` responde."""
    config = Configuracoes(
        database_url="sqlite://",
        chave_secreta=SecretStr("t" * 32),
        ambiente="dev",
        cookie_seguro=False,
        uploads_dir=config_teste.uploads_dir,
        _env_file=None,
    )
    with TestClient(criar_app(config, engine=engine)) as cliente:
        yield cliente


def test_amostra_nao_existe_fora_do_desenvolvimento(cliente: TestClient) -> None:
    """Ferramenta de quem constrói não vira página pública que ninguém mantém."""
    assert cliente.get("/estilo").status_code == 404


def test_amostra_responde_em_desenvolvimento(cliente_dev: TestClient) -> None:
    """A amostra é a documentação viva — se ela cair, ninguém revisa o sistema."""
    resposta = cliente_dev.get("/estilo")

    assert resposta.status_code == 200
    assert "Biblioteca de componentes" in resposta.text


@pytest.mark.parametrize("classe", COMPONENTES_NA_AMOSTRA)
def test_todo_componente_tem_amostra(cliente_dev: TestClient, classe: str) -> None:
    """Componente sem amostra é componente que o próximo dev reescreve por não achar."""
    assert classe in cliente_dev.get("/estilo").text, f"sem amostra de `{classe}` em /estilo"


def test_amostra_lista_o_contraste_medido_dos_tres_temas(cliente_dev: TestClient) -> None:
    """O critério de aceite do dono: o par de cor com o valor medido na tela, não na promessa."""
    corpo = cliente_dev.get("/estilo").text

    assert "Contraste medido" in corpo
    for tema in ("Claro", "Escuro", "Sépia"):
        assert tema in corpo
    # Uma amostra por par, nos três temas: a tabela inteira, sem recorte silencioso.
    assert corpo.count('class="contraste-amostra"') == len(PARES_OBRIGATORIOS) * 3


def test_amostra_nao_esconde_reprovacao(cliente_dev: TestClient) -> None:
    """Se um par reprovar, a amostra diz — documentação que só mostra o verde é propaganda."""
    fonte = Path(__file__).resolve().parents[2] / "web" / "templates" / "estilo" / "pagina.html"
    assert "medida.aprovado" in fonte.read_text(encoding="utf-8")

# O que é: teste do passo 3 do plano `docs/fatias/1b-radar-e-conta.md` — o comando `varrer`
# contra a fixture real do catálogo, com um cliente HTTP falso (nunca toca a rede). Quando ler:
# ao mexer em `aprovaos/motor/radar.py`.
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from aprovaos.dados.repositorio_radar import buscar_por_evento_url, listar
from aprovaos.motor.fontes.cebraspe import URL_CATALOGO, FonteCebraspe
from aprovaos.motor.radar import ID_FONTE_CEBRASPE, varrer

RAIZ_FIXTURES = (
    Path(__file__).resolve().parents[2] / "knowledge" / "fixtures" / "fontes" / "cebraspe"
)


class _RespostaFalsa:
    """Resposta HTTP falsa: só o que `FonteCebraspe.obter_catalogo` usa."""

    def __init__(self, status_code: int, corpo: Any = None) -> None:
        self.status_code = status_code
        self.content = b""
        self._corpo = corpo

    def json(self) -> Any:
        """Devolve o corpo decodificado, como `httpx2.Response.json()`."""
        return self._corpo


class ClienteFalso:
    """Cliente HTTP falso: devolve o catálogo cadastrado, nunca toca a rede."""

    def __init__(self, catalogo: Any) -> None:
        self._catalogo = catalogo

    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> _RespostaFalsa:
        """Devolve o catálogo cadastrado para `URL_CATALOGO`."""
        assert url == URL_CATALOGO
        return _RespostaFalsa(200, corpo=self._catalogo)


def _catalogo() -> Any:
    caminho = RAIZ_FIXTURES / "catalogo-todas-as-fases-2026-09-19.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_varrer_sincroniza_o_catalogo_inteiro(db: Session) -> None:
    """496 itens no catálogo, mas `INSS_22` se repete (defeito medido da própria API) — 495
    concursos distintos persistidos, nunca uma "atualização" espúria do próprio catálogo consigo
    mesmo.
    """
    fonte_cebraspe = FonteCebraspe(ClienteFalso(_catalogo()), "vlfcandido@gmail.com")
    agora = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

    relatorio = varrer(db, fonte_cebraspe, agora)

    assert relatorio.novos == 495
    assert relatorio.atualizados == 0
    assert relatorio.inalterados == 0
    assert len(listar(db)) == 495
    agepar = buscar_por_evento_url(db, "AGEPAR_PR_26")
    assert agepar is not None
    assert agepar.uf == "PR"
    assert agepar.fase == "em_andamento"


def test_varrer_e_idempotente(db: Session) -> None:
    fonte_cebraspe = FonteCebraspe(ClienteFalso(_catalogo()), "vlfcandido@gmail.com")
    agora1 = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    agora2 = datetime(2026, 9, 19, 18, 0, tzinfo=UTC)
    varrer(db, fonte_cebraspe, agora1)

    relatorio = varrer(db, fonte_cebraspe, agora2)

    assert relatorio.novos == 0
    assert relatorio.atualizados == 0
    assert relatorio.inalterados == 495
    assert len(listar(db)) == 495


def test_varrer_cria_a_fonte_e_carimba_ultima_varredura(db: Session) -> None:
    from aprovaos.dados.repositorio_radar import obter_ou_criar_fonte

    fonte_cebraspe = FonteCebraspe(ClienteFalso(_catalogo()), "vlfcandido@gmail.com")
    agora = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

    varrer(db, fonte_cebraspe, agora)

    fonte = obter_ou_criar_fonte(db, ID_FONTE_CEBRASPE, "não usado", "não usado")
    assert fonte.ultima_varredura == agora

# O que é: testes do passo 1 da fundação jurídica — `FontePlanalto` (`motor/fontes/planalto.py`),
# o cliente HTTP com o `User-Agent` da ADR-0037, contra um cliente falso (offline) e, atrás do
# marker `rede`, contra o Planalto de verdade. Quando ler: ao mudar o catálogo de normas ou o UA.
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import SecretStr

from aprovaos.config import Configuracoes
from aprovaos.dominio.legislacao import extrair_artigo
from aprovaos.motor.fontes.base import FonteIndisponivel, Novidade
from aprovaos.motor.fontes.planalto import (
    CATALOGO,
    USER_AGENT_TEMPLATE,
    FontePlanalto,
    criar_fonte_planalto,
    decodificar_html,
)

CONTATO_TESTE = "vlfcandido@gmail.com"
RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_CF = RAIZ / "knowledge/fixtures/juridico/constituicao_planalto_compilada.htm"


class _RespostaFalsa:
    """Resposta HTTP falsa: só o que `FontePlanalto` usa (`status_code`, `content`)."""

    def __init__(self, status_code: int, conteudo: bytes = b"") -> None:
        self.status_code = status_code
        self.content = conteudo


class ClienteFalso:
    """Cliente HTTP falso: nunca toca a rede, devolve respostas pré-cadastradas por URL."""

    def __init__(self, respostas: dict[str, _RespostaFalsa]) -> None:
        self._respostas = respostas
        self.headers_recebidos: list[Mapping[str, str]] = []

    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> _RespostaFalsa:
        """Devolve a resposta cadastrada para `url`, registrando os cabeçalhos recebidos."""
        self.headers_recebidos.append(headers or {})
        if url not in self._respostas:
            raise KeyError(f"ClienteFalso sem resposta cadastrada para {url}")
        return self._respostas[url]


class ClienteQueFalha:
    """Cliente HTTP falso que sempre levanta `httpx2.HTTPError` — simula o filtro de UA/rede."""

    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> Any:
        """Levanta `httpx2.ConnectError`, como o Planalto faz sem o `User-Agent` certo."""
        raise httpx2.ConnectError("falha de transporte simulada (ex.: UA sem 'Mozilla/5.0')")


def test_lista_vazia_devolve_as_duas_normas_do_catalogo() -> None:
    """`vistos=∅` devolve as normas do catálogo fixo, sem tocar a rede."""
    fonte = FontePlanalto(ClienteFalso({}), CONTATO_TESTE)

    novidades = fonte.listar_novidades(vistos=set())

    assert len(novidades) == len(CATALOGO)
    assert {n.id for n in novidades} == set(CATALOGO)
    assert all(n.tipo == "lei" for n in novidades)


def test_tudo_visto_devolve_vazio() -> None:
    """`vistos` com todos os ids do catálogo não devolve nenhuma novidade."""
    fonte = FontePlanalto(ClienteFalso({}), CONTATO_TESTE)

    novidades = fonte.listar_novidades(vistos=set(CATALOGO))

    assert novidades == []


def test_um_item_nao_visto() -> None:
    """`vistos` com todos menos um id devolve só a norma faltante."""
    fonte = FontePlanalto(ClienteFalso({}), CONTATO_TESTE)
    todos_menos_um = set(CATALOGO) - {"lei-14133-2021"}

    novidades = fonte.listar_novidades(vistos=todos_menos_um)

    assert len(novidades) == 1
    assert novidades[0].id == "lei-14133-2021"


def test_baixar_devolve_conteudo_e_hash() -> None:
    """`baixar` devolve o conteúdo cru e o hash sha256 dele, como a Cebraspe."""
    import hashlib

    norma = CATALOGO["cf-1988"]
    conteudo = b"<html>Art. 37 ...</html>"
    novidade = Novidade(
        id="cf-1988", tipo="lei", titulo=norma.titulo, url=norma.url, evento="cf-1988",
        publicado_em=None,
    )  # fmt: skip
    cliente = ClienteFalso({norma.url: _RespostaFalsa(200, conteudo=conteudo)})
    fonte = FontePlanalto(cliente, CONTATO_TESTE)

    arquivo = fonte.baixar(novidade)

    assert arquivo.hash == hashlib.sha256(conteudo).hexdigest()
    assert arquivo.conteudo == conteudo


def test_erro_http_levanta_fonte_indisponivel() -> None:
    """Um 403 (ex.: sem o UA certo) levanta `FonteIndisponivel`, nunca um conteúdo vazio."""
    norma = CATALOGO["cf-1988"]
    novidade = Novidade(
        id="cf-1988", tipo="lei", titulo=norma.titulo, url=norma.url, evento="cf-1988",
        publicado_em=None,
    )  # fmt: skip
    cliente = ClienteFalso({norma.url: _RespostaFalsa(403)})
    fonte = FontePlanalto(cliente, CONTATO_TESTE)

    with pytest.raises(FonteIndisponivel):
        fonte.baixar(novidade)


def test_falha_de_transporte_levanta_fonte_indisponivel() -> None:
    """Falha de transporte (o próprio filtro de UA do Planalto) levanta `FonteIndisponivel`."""
    norma = CATALOGO["cf-1988"]
    novidade = Novidade(
        id="cf-1988", tipo="lei", titulo=norma.titulo, url=norma.url, evento="cf-1988",
        publicado_em=None,
    )  # fmt: skip
    fonte = FontePlanalto(ClienteQueFalha(), CONTATO_TESTE)

    with pytest.raises(FonteIndisponivel):
        fonte.baixar(novidade)


def test_user_agent_comeca_com_mozilla_5_0_adr_0037() -> None:
    """Toda requisição carrega o UA híbrido da ADR-0037 — começa com 'Mozilla/5.0', tem o
    token do coletor e o contato configurado (sem o prefixo, o Planalto recusa a conexão).
    """
    norma = CATALOGO["cf-1988"]
    novidade = Novidade(
        id="cf-1988", tipo="lei", titulo=norma.titulo, url=norma.url, evento="cf-1988",
        publicado_em=None,
    )  # fmt: skip
    cliente = ClienteFalso({norma.url: _RespostaFalsa(200, conteudo=b"ok")})
    fonte = FontePlanalto(cliente, CONTATO_TESTE)

    fonte.baixar(novidade)

    assert cliente.headers_recebidos, "nenhuma requisição registrada"
    agente = cliente.headers_recebidos[0]["User-Agent"]
    assert agente == USER_AGENT_TEMPLATE.format(contato=CONTATO_TESTE)
    assert agente.startswith("Mozilla/5.0")
    assert "AprovaOS-coletor/0.1" in agente
    assert CONTATO_TESTE in agente


def test_fecha_cliente_no_gerenciador_de_contexto() -> None:
    """`with FontePlanalto(...) as fonte` fecha o cliente HTTP ao sair."""

    class _ClienteFechavel(ClienteFalso):
        def __init__(self) -> None:
            super().__init__({})
            self.fechado = False

        def close(self) -> None:
            self.fechado = True

    cliente = _ClienteFechavel()
    with FontePlanalto(cliente, CONTATO_TESTE) as fonte:
        fonte.listar_novidades(vistos=set())

    assert cliente.fechado is True


def test_decodificar_html_bate_com_a_fixture_real_e_extrai_o_artigo() -> None:
    """`decodificar_html` sobre os bytes crus da fixture real dá um HTML que `extrair_artigo`
    entende — fecha o cano cliente HTTP -> decodificação -> extrator de dispositivo.
    """
    conteudo_bruto = FIXTURE_CF.read_bytes()

    html = decodificar_html(conteudo_bruto)
    artigo = extrair_artigo(html, "37")

    assert artigo.caput.texto.startswith("Art. 37. A administração pública direta e indireta")


@pytest.mark.rede
def test_rede() -> None:
    """`criar_fonte_planalto` de verdade baixa a CF com o UA da ADR-0037 e extrai o art. 37."""
    config = Configuracoes(
        database_url="sqlite://", chave_secreta=SecretStr("t" * 32), _env_file=None
    )
    fonte = criar_fonte_planalto(config)

    novidades = fonte.listar_novidades(vistos=set())
    assert len(novidades) == len(CATALOGO)

    cf = next(n for n in novidades if n.id == "cf-1988")
    arquivo = fonte.baixar(cf)
    html = decodificar_html(arquivo.conteudo)
    artigo = extrair_artigo(html, "37")

    assert artigo.caput.redacao_de == "Redação dada pela Emenda Constitucional nº 19, de 1998"

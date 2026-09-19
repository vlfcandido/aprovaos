# O que é: os cinco testes de novidade da skill `monitor-de-fontes` (passo 3 do protocolo)
# aplicados à `FonteCebraspe`, mais o download e o `User-Agent` identificado — tudo contra os
# snapshots reais/sintéticos de `knowledge/fixtures/fontes/cebraspe/` via um cliente HTTP falso.
# Quando ler: ao mudar `aprovaos/motor/fontes/cebraspe.py` ou os snapshots que ele consome.
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import SecretStr

from aprovaos.config import Configuracoes
from aprovaos.motor.fontes.base import FonteIndisponivel, Novidade
from aprovaos.motor.fontes.cebraspe import (
    URL_ARQUIVO,
    URL_DETALHE,
    URL_LISTA,
    FonteCebraspe,
    criar_fonte_cebraspe,
)

RAIZ_FIXTURES = (
    Path(__file__).resolve().parents[2] / "knowledge" / "fixtures" / "fontes" / "cebraspe"
)
CONTATO_TESTE = "vlfcandido@gmail.com"


class _RespostaFalsa:
    """Resposta HTTP falsa: só o que `FonteCebraspe` usa (`status_code`, `json()`, `content`)."""

    def __init__(self, status_code: int, corpo: Any = None, conteudo: bytes = b"") -> None:
        self.status_code = status_code
        self._corpo = corpo
        self.content = conteudo

    def json(self) -> Any:
        """Devolve o corpo decodificado, como `httpx2.Response.json()`."""
        return self._corpo


class ClienteFalso:
    """Cliente HTTP falso: nunca toca a rede, devolve respostas pré-cadastradas por URL.

    Registra os cabeçalhos recebidos em cada chamada (`headers_recebidos`), para o teste do
    `User-Agent` identificado.
    """

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
    """Cliente HTTP falso que levanta `httpx2.HTTPError` em toda chamada — nenhuma rede real.

    Simula a falha de transporte (rede fora do ar, sem resposta HTTP nenhuma), distinta do
    status HTTP >= 400 (que `_RespostaFalsa`/`ClienteFalso` já cobrem em `test_erro_http_levanta`).
    """

    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> _RespostaFalsa:
        """Levanta `httpx2.ConnectError` para simular a rede fora do ar."""
        raise httpx2.ConnectError("falha de transporte simulada")


def _carregar(nome: str) -> Any:
    return json.loads((RAIZ_FIXTURES / nome).read_text(encoding="utf-8"))


def _ids_dos_eventos(payload: Any) -> set[str]:
    return {evento["eventoURL"] for evento in payload[0]["eventos"]}


def test_lista_vazia_devolve_todos() -> None:
    """`v1` com `vistos=∅` devolve as 423 novidades de evento distintas, `tipo="desconhecido"`."""
    v1 = _carregar("lista-encerrado-v1.json")
    cliente = ClienteFalso({URL_LISTA: _RespostaFalsa(200, corpo=v1)})
    fonte = FonteCebraspe(cliente, CONTATO_TESTE)

    novidades = fonte.listar_novidades(vistos=set())

    assert len(novidades) == 423
    assert all(n.tipo == "desconhecido" for n in novidades)
    ids = {n.id for n in novidades}
    assert ids == _ids_dos_eventos(v1)
    for n in novidades:
        assert n.id == n.evento


def test_tudo_visto_devolve_vazio() -> None:
    """`v1` com `vistos = ids(v1)` não devolve nenhuma novidade."""
    v1 = _carregar("lista-encerrado-v1.json")
    cliente = ClienteFalso({URL_LISTA: _RespostaFalsa(200, corpo=v1)})
    fonte = FonteCebraspe(cliente, CONTATO_TESTE)

    novidades = fonte.listar_novidades(vistos=_ids_dos_eventos(v1))

    assert novidades == []


def test_um_item_novo() -> None:
    """`v2` com `vistos = ids(v1)` devolve só o evento inserido, `TESTE_V3_99`."""
    v1 = _carregar("lista-encerrado-v1.json")
    v2 = _carregar("lista-encerrado-v2.json")
    cliente = ClienteFalso({URL_LISTA: _RespostaFalsa(200, corpo=v2)})
    fonte = FonteCebraspe(cliente, CONTATO_TESTE)

    novidades = fonte.listar_novidades(vistos=_ids_dos_eventos(v1))

    assert len(novidades) == 1
    assert novidades[0].id == "TESTE_V3_99"


def test_arquivos_do_evento_classifica_por_descricao() -> None:
    """O detalhe do evento vira 52 novidades (26 prova + 26 gabarito); 2 arquivos ignorados."""
    detalhe = _carregar("detalhe-TJ_PA_25_SERVIDOR.json")
    url = URL_DETALHE.format(eventoURL="TJ_PA_25_SERVIDOR")
    cliente = ClienteFalso({url: _RespostaFalsa(200, corpo=detalhe)})
    fonte = FonteCebraspe(cliente, CONTATO_TESTE)

    novidades = fonte.arquivos_do_evento("TJ_PA_25_SERVIDOR")

    assert len(novidades) == 52
    provas = [n for n in novidades if n.tipo == "prova"]
    gabaritos = [n for n in novidades if n.tipo == "gabarito"]
    assert len(provas) == 26
    assert len(gabaritos) == 26
    ids = [n.id for n in novidades]
    assert len(ids) == len(set(ids))

    cargo_9 = next(
        n for n in novidades if n.titulo == "PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS – CARGO 9"
    )
    assert (
        cargo_9.url == "https://cdn.cebraspe.org.br/concursos/TJ_PA_25_SERVIDOR/arquivos/"
        "C15F414E0E91EF109220A73BDF53B232C4466F64770A91E715C56DCB94131F41.pdf"
    )
    assert cargo_9.publicado_em == datetime(2025, 9, 5, 22, 0, tzinfo=UTC)


def test_cargos_do_evento_le_eventocargos() -> None:
    """`cargos_do_evento` lê `eventoCargos` do detalhe; o CARGO 9 do fixture é Direito."""
    detalhe = _carregar("detalhe-TJ_PA_25_SERVIDOR.json")
    url = URL_DETALHE.format(eventoURL="TJ_PA_25_SERVIDOR")
    cliente = ClienteFalso({url: _RespostaFalsa(200, corpo=detalhe)})
    fonte = FonteCebraspe(cliente, CONTATO_TESTE)

    cargos = fonte.cargos_do_evento("TJ_PA_25_SERVIDOR")

    assert len(cargos) == 22
    direito = next(c for c in cargos if "DIREITO" in c.area.upper())
    assert direito.id_area == "09"
    assert direito.area == "CARGO 9: ANALISTA JUDICIÁRIO – ESPECIALIDADE: DIREITO"


def test_fecha_cliente_no_gerenciador_de_contexto() -> None:
    """`with FonteCebraspe(...) as fonte` fecha o cliente HTTP ao sair (evita `ResourceWarning`)."""

    class _ClienteFechavel(ClienteFalso):
        def __init__(self, respostas: dict[str, _RespostaFalsa]) -> None:
            super().__init__(respostas)
            self.fechado = False

        def close(self) -> None:
            self.fechado = True

    v1 = _carregar("lista-encerrado-v1.json")
    cliente = _ClienteFechavel({URL_LISTA: _RespostaFalsa(200, corpo=v1)})

    with FonteCebraspe(cliente, CONTATO_TESTE) as fonte:
        fonte.listar_novidades(vistos=set())

    assert cliente.fechado is True


def test_erro_http_levanta() -> None:
    """Um 503 na listagem levanta `FonteIndisponivel`, nunca `[]`."""
    cliente = ClienteFalso({URL_LISTA: _RespostaFalsa(503)})
    fonte = FonteCebraspe(cliente, CONTATO_TESTE)

    with pytest.raises(FonteIndisponivel):
        fonte.listar_novidades(vistos=set())


def test_falha_de_transporte_levanta_na_listagem() -> None:
    """Rede fora do ar (sem resposta HTTP) na listagem levanta `FonteIndisponivel`, não `[]`."""
    fonte = FonteCebraspe(ClienteQueFalha(), CONTATO_TESTE)

    with pytest.raises(FonteIndisponivel):
        fonte.listar_novidades(vistos=set())


def test_falha_de_transporte_levanta_no_baixar() -> None:
    """Rede fora do ar (sem resposta HTTP) em `baixar` levanta `FonteIndisponivel`."""
    novidade = Novidade(
        id="TJ_PA_25_SERVIDOR/arquivo.pdf",
        tipo="prova",
        titulo="PROVA OBJETIVA",
        url="https://cdn.cebraspe.org.br/concursos/TJ_PA_25_SERVIDOR/arquivos/arquivo.pdf",
        evento="TJ_PA_25_SERVIDOR",
        publicado_em=None,
    )
    fonte = FonteCebraspe(ClienteQueFalha(), CONTATO_TESTE)

    with pytest.raises(FonteIndisponivel):
        fonte.baixar(novidade)


def test_baixar_devolve_conteudo_e_hash() -> None:
    """`baixar` devolve o conteúdo cru e o hash sha256 dele."""
    conteudo = b"%PDF-1.4 x"
    novidade = Novidade(
        id="TJ_PA_25_SERVIDOR/arquivo.pdf",
        tipo="prova",
        titulo="PROVA OBJETIVA",
        url="https://cdn.cebraspe.org.br/concursos/TJ_PA_25_SERVIDOR/arquivos/arquivo.pdf",
        evento="TJ_PA_25_SERVIDOR",
        publicado_em=None,
    )
    cliente = ClienteFalso({novidade.url: _RespostaFalsa(200, conteudo=conteudo)})
    fonte = FonteCebraspe(cliente, CONTATO_TESTE)

    arquivo = fonte.baixar(novidade)

    assert arquivo.hash == hashlib.sha256(conteudo).hexdigest()
    assert arquivo.conteudo == conteudo
    assert arquivo.tamanho == len(conteudo)


def test_user_agent_identificado() -> None:
    """Toda requisição carrega `User-Agent` com `AprovaOS-coletor/0.1` e o contato configurado."""
    v1 = _carregar("lista-encerrado-v1.json")
    cliente = ClienteFalso({URL_LISTA: _RespostaFalsa(200, corpo=v1)})
    fonte = FonteCebraspe(cliente, CONTATO_TESTE)

    fonte.listar_novidades(vistos=set())

    assert cliente.headers_recebidos, "nenhuma requisição registrada"
    for cabecalhos in cliente.headers_recebidos:
        agente = cabecalhos.get("User-Agent", "")
        assert "AprovaOS-coletor/0.1" in agente
        assert CONTATO_TESTE in agente


def test_urls_do_codigo_estao_na_ficha() -> None:
    """As constantes de URL do módulo batem literalmente com a ficha `knowledge/fontes.yaml`."""
    import yaml

    raiz = Path(__file__).resolve().parents[2]
    ficha = raiz / "knowledge" / "fontes.yaml"
    fichas = yaml.safe_load(ficha.read_text(encoding="utf-8"))
    cebraspe = next(f for f in fichas if f["id"] == "cebraspe")

    assert URL_LISTA == cebraspe["url_lista"]
    assert URL_DETALHE == cebraspe["url_detalhe"]
    assert URL_ARQUIVO == cebraspe["url_arquivo"]


@pytest.mark.rede
def test_rede() -> None:
    """`criar_fonte_cebraspe` de verdade lista ≥ 400 eventos e acha o CARGO 9 no detalhe."""
    config = Configuracoes(
        database_url="sqlite://",
        chave_secreta=SecretStr("t" * 32),
        _env_file=None,
    )
    fonte = criar_fonte_cebraspe(config)

    novidades = fonte.listar_novidades(vistos=set())
    assert len(novidades) >= 400

    arquivos = fonte.arquivos_do_evento("TJ_PA_25_SERVIDOR")
    assert any("CARGO 9" in n.titulo for n in arquivos)

# O que é: os três testes do passo 5 da V3 (skill `monitor-de-fontes`) — filtrar os arquivos do
# cargo de Direito, parear prova+gabarito e gravar `Documento` + arquivo em disco, com fonte
# falsa (sem rede). Também cobre a descoberta do cargo por `eventoCargos` (decisão do dono: o
# número do cargo varia por concurso) e a resolução de `documentos_dir`.
# Quando ler: ao mexer em `aprovaos/motor/coletar.py`.
import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes
from aprovaos.dados.modelos import Documento
from aprovaos.motor.coletar import (
    CargoDeDireitoAmbiguo,
    ParDeProva,
    ProvaSemGabarito,
    arquivos_do_cargo,
    cargo_de_direito,
    coletar_par,
    parear,
    resolver_documentos_dir,
)
from aprovaos.motor.fontes.base import ArquivoBaixado, Novidade
from aprovaos.motor.fontes.cebraspe import URL_DETALHE, CargoEvento, FonteCebraspe

RAIZ_FIXTURES = (
    Path(__file__).resolve().parents[2] / "knowledge" / "fixtures" / "fontes" / "cebraspe"
)
EVENTO = "TJ_PA_25_SERVIDOR"


class _RespostaFalsa:
    def __init__(self, status_code: int, corpo: object = None) -> None:
        self.status_code = status_code
        self._corpo = corpo
        self.content = b""

    def json(self) -> object:
        return self._corpo


class ClienteFalso:
    """Cliente HTTP falso: só a listagem/detalhe cadastrados; `baixar` usa `FonteFalsaDeArquivo`."""

    def __init__(self, respostas: dict[str, _RespostaFalsa]) -> None:
        self._respostas = respostas

    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> _RespostaFalsa:
        return self._respostas[url]


class FonteFalsaDeArquivo:
    """Fonte falsa: `baixar` devolve o conteúdo cadastrado por `Novidade.id` — sem rede."""

    def __init__(self, conteudos: dict[str, bytes]) -> None:
        self._conteudos = conteudos
        self.baixados: list[str] = []

    def listar_novidades(self, vistos: set[str]) -> list[Novidade]:
        raise NotImplementedError

    def baixar(self, novidade: Novidade) -> ArquivoBaixado:
        self.baixados.append(novidade.id)
        return ArquivoBaixado.de_conteudo(novidade, self._conteudos[novidade.id])


def _carregar_detalhe() -> object:
    return json.loads((RAIZ_FIXTURES / f"detalhe-{EVENTO}.json").read_text(encoding="utf-8"))


def _novidades_do_evento() -> list[Novidade]:
    cliente = ClienteFalso(
        {URL_DETALHE.format(eventoURL=EVENTO): _RespostaFalsa(200, corpo=_carregar_detalhe())}
    )
    fonte = FonteCebraspe(cliente, "vlfcandido@gmail.com")
    return fonte.arquivos_do_evento(EVENTO)


@pytest.fixture
def config_teste(tmp_path: Path) -> Configuracoes:
    return Configuracoes(
        database_url="sqlite://",
        chave_secreta=SecretStr("t" * 32),
        documentos_dir=tmp_path / "provas",
        _env_file=None,
    )


def test_seleciona_cargo_de_direito() -> None:
    """`arquivos_do_cargo` devolve só os dois arquivos que terminam em `CARGO 9`."""
    novidades = _novidades_do_evento()

    arquivos = arquivos_do_cargo(novidades, cargo_numero=9)

    assert len(arquivos) == 2
    tipos = {a.tipo for a in arquivos}
    assert tipos == {"prova", "gabarito"}
    for arquivo in arquivos:
        assert arquivo.titulo.endswith("CARGO 9")
    # nenhum arquivo de "conhecimentos gerais" (cita o cargo 9 na lista, mas não termina nele).
    assert not any("CARGOS 1, 2, 6, 8, 9, 18 E 22" in a.titulo for a in arquivos)


def test_pareia_prova_e_gabarito() -> None:
    """`parear` casa prova+gabarito do mesmo evento; sem um dos dois levanta `ProvaSemGabarito`."""
    novidades = _novidades_do_evento()
    arquivos = arquivos_do_cargo(novidades, cargo_numero=9)

    pares = parear(arquivos)

    assert len(pares) == 1
    par = pares[0]
    assert isinstance(par, ParDeProva)
    assert par.prova.tipo == "prova"
    assert par.gabarito.tipo == "gabarito"
    assert par.prova.evento == EVENTO

    apenas_prova = [a for a in arquivos if a.tipo == "prova"]
    with pytest.raises(ProvaSemGabarito):
        parear(apenas_prova)


def test_grava_documento_e_arquivo(config_teste: Configuracoes, db: Session) -> None:
    """`coletar_par` grava dois `Documento` e os dois arquivos; rodar de novo não duplica."""
    novidades = _novidades_do_evento()
    par = parear(arquivos_do_cargo(novidades, cargo_numero=9))[0]
    conteudos = {par.prova.id: b"%PDF-1.4 prova", par.gabarito.id: b"%PDF-1.4 gabarito"}
    fonte = FonteFalsaDeArquivo(conteudos)

    documento_prova, documento_gabarito = coletar_par(db, config_teste, fonte, par)
    db.flush()

    assert documento_prova.tipo == "prova"
    assert documento_gabarito.tipo == "gabarito"
    nome_prova = par.prova.id.split("/", 1)[1]
    nome_gabarito = par.gabarito.id.split("/", 1)[1]
    assert documento_prova.caminho == f"{EVENTO}/{nome_prova}"
    assert documento_gabarito.caminho == f"{EVENTO}/{nome_gabarito}"
    assert documento_prova.metadados["descricao"] == par.prova.titulo
    assert documento_prova.metadados["evento"] == EVENTO
    assert documento_prova.metadados["url_origem"] == par.prova.url

    caminho_prova = config_teste.documentos_dir / EVENTO / nome_prova  # type: ignore[operator]
    caminho_gabarito = config_teste.documentos_dir / EVENTO / nome_gabarito  # type: ignore[operator]
    assert caminho_prova.read_bytes() == b"%PDF-1.4 prova"
    assert caminho_gabarito.read_bytes() == b"%PDF-1.4 gabarito"

    total_antes = db.scalars(select(Documento)).all()
    assert len(total_antes) == 2

    # rodar de novo não duplica: o hash já existe, devolve o Documento existente.
    documento_prova_2, documento_gabarito_2 = coletar_par(db, config_teste, fonte, par)
    db.flush()
    assert documento_prova_2.id == documento_prova.id
    assert documento_gabarito_2.id == documento_gabarito.id
    total_depois = db.scalars(select(Documento)).all()
    assert len(total_depois) == 2


def test_resolver_documentos_dir_usa_config_quando_definido(tmp_path: Path) -> None:
    """`resolver_documentos_dir` devolve `config.documentos_dir` quando não é `None`."""
    config = Configuracoes(
        database_url="sqlite://",
        chave_secreta=SecretStr("t" * 32),
        documentos_dir=tmp_path / "aqui",
        _env_file=None,
    )

    assert resolver_documentos_dir(config) == tmp_path / "aqui"


def test_resolver_documentos_dir_usa_padrao_quando_none() -> None:
    """`resolver_documentos_dir` cai para `knowledge/provas` na raiz do repositório."""
    config = Configuracoes(
        database_url="sqlite://", chave_secreta=SecretStr("t" * 32), _env_file=None
    )

    destino = resolver_documentos_dir(config)

    assert destino.name == "provas"
    assert destino.parent.name == "knowledge"


def test_cargo_de_direito_acha_area_com_direito() -> None:
    """`cargo_de_direito` acha o cargo cuja `area` contém `DIREITO` e extrai o número."""
    cargos = [
        CargoEvento(id_area="01", area="CARGO 1: ANALISTA JUDICIÁRIO – ÁREA ADMINISTRATIVA"),
        CargoEvento(id_area="09", area="CARGO 9: ANALISTA JUDICIÁRIO – ESPECIALIDADE: DIREITO"),
    ]

    achado = cargo_de_direito(cargos)

    assert achado == (9, "CARGO 9: ANALISTA JUDICIÁRIO – ESPECIALIDADE: DIREITO")


def test_cargo_de_direito_none_quando_ausente() -> None:
    """`cargo_de_direito` devolve `None` quando nenhuma `area` cita Direito — nunca adivinha."""
    cargos = [CargoEvento(id_area="01", area="CARGO 1: ANALISTA JUDICIÁRIO – ÁREA JUDICIÁRIA")]

    assert cargo_de_direito(cargos) is None


def test_cargo_de_direito_ambiguo_levanta() -> None:
    """Mais de uma `area` com `DIREITO` é ambiguidade — levanta, nunca escolhe sozinho."""
    cargos = [
        CargoEvento(id_area="01", area="CARGO 1: PROCURADOR — DIREITO CIVIL"),
        CargoEvento(id_area="02", area="CARGO 2: PROCURADOR — DIREITO TRIBUTÁRIO"),
    ]

    with pytest.raises(CargoDeDireitoAmbiguo):
        cargo_de_direito(cargos)

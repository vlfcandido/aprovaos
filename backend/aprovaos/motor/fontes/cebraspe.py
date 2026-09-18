"""A fonte concreta da Cebraspe: eventos encerrados e arquivos de prova/gabarito por evento.

O que é: `FonteCebraspe` (`FonteColetavel` do passo 3) e `criar_fonte_cebraspe`, a fábrica que
monta o cliente HTTP de verdade. Implementa o passo 4 da skill
`.claude/skills/monitor-de-fontes/SKILL.md` para a ficha `cebraspe` de `knowledge/fontes.yaml` —
as constantes de URL abaixo repetem literalmente essa ficha (`test_urls_do_codigo_estao_na_ficha`).

A API da Cebraspe tem duas identidades de item, na mesma fonte:
    - a *listagem* (`URL_LISTA`) devolve **eventos** (concursos), sem arquivo nenhum — a
      identidade é `eventoURL` e o `tipo` é sempre `"desconhecido"` até o detalhe ser aberto;
    - o *detalhe* de um evento (`URL_DETALHE`) devolve **arquivos** (`arquivosGabarito`) — a
      identidade é `"{eventoURL}/{nomeArquivo}"` e o `tipo` vem do prefixo de `descricaoArquivo`.

Quando ler: antes de mudar a coleta da Cebraspe ou de investigar por que um evento/arquivo não
apareceu como novidade.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import httpx2

from aprovaos.config import Configuracoes
from aprovaos.motor.fontes.base import ArquivoBaixado, FonteIndisponivel, Novidade, TipoNovidade

URL_LISTA = "https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/fase/encerrado"
URL_DETALHE = "https://apis.cebraspe.org.br/cebraspe/eventos/{eventoURL}"
URL_ARQUIVO = "https://cdn.cebraspe.org.br/concursos/{eventoURL}/arquivos/{nomeArquivo}"

_FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")

# Prefixos de `descricaoArquivo` que não viram `Novidade` (medido em
# `knowledge/fixtures/fontes/cebraspe/detalhe-TJ_PA_25_SERVIDOR.json`, passo 4 do plano da V3):
# a prova discursiva e o padrão de resposta dela, que a V3 não processa.
_PREFIXOS_IGNORADOS = ("PROVA DISCURSIVA", "PADRÃO DEFINITIVO DE RESPOSTA")
_PREFIXO_PROVA = "PROVA OBJETIVA"
_PREFIXO_GABARITO = "GABARITO DEFINITIVO"


class _RespostaHttp(Protocol):
    """O subconjunto de `httpx2.Response` que `FonteCebraspe` usa.

    Também satisfeito por clientes falsos de teste. Os dois atributos são `@property` (e não
    campos simples) porque `httpx2.Response` os expõe como somente leitura; um `Protocol` com
    campo mutável rejeitaria essa correspondência.
    """

    @property
    def status_code(self) -> int:
        """Código de status HTTP da resposta."""
        ...

    @property
    def content(self) -> bytes:
        """Corpo cru da resposta, em bytes."""
        ...

    def json(self) -> Any:
        """Devolve o corpo da resposta já decodificado (lista ou dicionário)."""
        ...


class _ClienteHttp(Protocol):
    """O subconjunto de `httpx2.Client` que `FonteCebraspe` usa."""

    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> _RespostaHttp:
        """Executa um `GET` e devolve a resposta."""
        ...


def _tipo_por_descricao(descricao: str) -> TipoNovidade | None:
    """Classifica um arquivo do detalhe pelo prefixo de `descricaoArquivo`.

    Args:
        descricao: o campo `descricaoArquivo` do arquivo, cru.

    Returns:
        `"prova"` para `PROVA OBJETIVA`, `"gabarito"` para `GABARITO DEFINITIVO`, `None` para os
        prefixos ignorados desta fatia (`PROVA DISCURSIVA`, `PADRÃO DEFINITIVO DE RESPOSTA`) e
        `"desconhecido"` para qualquer outro prefixo que a ficha ainda não mapeia.
    """
    if descricao.startswith(_PREFIXOS_IGNORADOS):
        return None
    if descricao.startswith(_PREFIXO_PROVA):
        return "prova"
    if descricao.startswith(_PREFIXO_GABARITO):
        return "gabarito"
    return "desconhecido"


def _converter_data_brasilia_para_utc(valor: str | None) -> datetime | None:
    """Converte `dataArquivoObj` (horário de Brasília, sem fuso) para `datetime` aware em UTC.

    A Cebraspe não declara fuso (ex.: `"2025-09-05T19:00:00"`); como a fonte é brasileira, o
    horário é lido como `America/Sao_Paulo` e normalizado para UTC (decisão do plano da V3,
    passo 4 — `Novidade.publicado_em` só aceita `datetime` aware).

    Args:
        valor: o campo `dataArquivoObj` do arquivo, ou `None` se ausente.

    Returns:
        O instante em UTC, ou `None` se `valor` for `None`.
    """
    if valor is None:
        return None
    ingenuo = datetime.fromisoformat(valor)
    de_brasilia = ingenuo.replace(tzinfo=_FUSO_BRASILIA)
    return de_brasilia.astimezone(UTC)


class FonteCebraspe:
    """A fonte concreta da Cebraspe — implementa `FonteColetavel` (`base.py`).

    Attributes:
        cliente: cliente HTTP já configurado (real ou falso), injetado no construtor — nenhum
            I/O acontece na criação desta classe.
        contato: e-mail do dono, anunciado no `User-Agent` de toda requisição (ADR-0030).
    """

    def __init__(self, cliente: _ClienteHttp, contato: str) -> None:
        """Recebe o cliente HTTP e o contato do coletor; não faz nenhuma chamada de rede aqui.

        Args:
            cliente: cliente HTTP (real `httpx2.Client` ou falso, nos testes).
            contato: e-mail do dono, para o `User-Agent` identificado.
        """
        self._cliente = cliente
        self._contato = contato

    def _cabecalhos(self) -> dict[str, str]:
        """Monta o `User-Agent` identificado (ADR-0030) para cada requisição."""
        return {"User-Agent": f"AprovaOS-coletor/0.1 (+contato: {self._contato})"}

    def _obter_json(self, url: str) -> Any:
        """Executa um `GET` e devolve o corpo decodificado, ou levanta `FonteIndisponivel`.

        Args:
            url: endereço a consultar.

        Returns:
            O corpo da resposta, já decodificado.

        Raises:
            FonteIndisponivel: status HTTP >= 400 ou falha de transporte (rede fora do ar).
        """
        try:
            resposta = self._cliente.get(url, headers=self._cabecalhos())
        except httpx2.HTTPError as erro:
            raise FonteIndisponivel(f"falha ao consultar {url}: {erro}") from erro
        if resposta.status_code >= 400:
            raise FonteIndisponivel(f"{url} devolveu status {resposta.status_code}")
        return resposta.json()

    def listar_novidades(self, vistos: set[str]) -> list[Novidade]:
        """Lista os eventos (concursos encerrados) cujo `eventoURL` não está em `vistos`.

        A listagem devolve uma lista com um único objeto `{eventos: [...]}`; `eventoURL` pode se
        repetir dentro dela (a própria API duplica algum evento) — o resultado é deduplicado por
        `eventoURL`, então uma única `Novidade` por evento distinto.

        Args:
            vistos: `eventoURL` já processados em rodadas anteriores.

        Returns:
            As novidades de evento não vistas, `tipo="desconhecido"` (o tipo real só se conhece
            abrindo o detalhe, em `arquivos_do_evento`).

        Raises:
            FonteIndisponivel: a fonte está fora do ar.
        """
        corpo = self._obter_json(URL_LISTA)
        eventos = corpo[0]["eventos"]

        novidades: dict[str, Novidade] = {}
        for evento in eventos:
            evento_url = evento["eventoURL"]
            if evento_url in vistos or evento_url in novidades:
                continue
            novidades[evento_url] = Novidade(
                id=evento_url,
                tipo="desconhecido",
                titulo=evento["eventoNomeAbreviado"],
                url=URL_DETALHE.format(eventoURL=evento_url),
                evento=evento_url,
                publicado_em=None,
            )
        return list(novidades.values())

    def arquivos_do_evento(self, evento_url: str) -> list[Novidade]:
        """Lista os arquivos de prova/gabarito do detalhe de um evento.

        Args:
            evento_url: o `eventoURL` do evento (identidade devolvida por `listar_novidades`).

        Returns:
            Uma `Novidade` por arquivo classificável (`tipo` "prova" ou "gabarito"; "desconhecido"
            para prefixo não mapeado). Arquivos com prefixo ignorado (`PROVA DISCURSIVA`,
            `PADRÃO DEFINITIVO DE RESPOSTA`) não entram na lista.

        Raises:
            FonteIndisponivel: a fonte está fora do ar.
        """
        detalhe = self._obter_json(URL_DETALHE.format(eventoURL=evento_url))
        arquivos = detalhe.get("arquivosGabarito") or []

        novidades: list[Novidade] = []
        for arquivo in arquivos:
            tipo = _tipo_por_descricao(arquivo["descricaoArquivo"])
            if tipo is None:
                continue
            nome_arquivo = arquivo["nomeArquivo"]
            novidades.append(
                Novidade(
                    id=f"{evento_url}/{nome_arquivo}",
                    tipo=tipo,
                    titulo=arquivo["descricaoArquivo"],
                    url=URL_ARQUIVO.format(eventoURL=evento_url, nomeArquivo=nome_arquivo),
                    evento=evento_url,
                    publicado_em=_converter_data_brasilia_para_utc(arquivo.get("dataArquivoObj")),
                )
            )
        return novidades

    def baixar(self, novidade: Novidade) -> ArquivoBaixado:
        """Baixa o conteúdo de uma novidade (arquivo de prova/gabarito).

        Args:
            novidade: item devolvido por `arquivos_do_evento`.

        Returns:
            O conteúdo baixado, com hash e tamanho.

        Raises:
            FonteIndisponivel: a fonte está fora do ar.
        """
        try:
            resposta = self._cliente.get(novidade.url, headers=self._cabecalhos())
        except httpx2.HTTPError as erro:
            raise FonteIndisponivel(f"falha ao baixar {novidade.url}: {erro}") from erro
        if resposta.status_code >= 400:
            raise FonteIndisponivel(f"{novidade.url} devolveu status {resposta.status_code}")
        return ArquivoBaixado.de_conteudo(novidade, resposta.content)


def criar_fonte_cebraspe(config: Configuracoes) -> FonteCebraspe:
    """Fábrica: monta o `httpx2.Client` real e devolve a `FonteCebraspe` pronta para uso.

    Nenhum I/O acontece na importação deste módulo — só nesta chamada explícita.

    Args:
        config: configurações do backend (usa `contato_coletor`, ADR-0030).

    Returns:
        Uma `FonteCebraspe` com cliente HTTP real (timeout de 30s, segue redirecionamentos).
    """
    cliente = httpx2.Client(
        headers={"User-Agent": f"AprovaOS-coletor/0.1 (+contato: {config.contato_coletor})"},
        timeout=30,
        follow_redirects=True,
    )
    return FonteCebraspe(cliente, config.contato_coletor)

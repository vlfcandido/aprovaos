"""Cliente HTTP da fonte jurídica (Planalto): textos compilados de normas, com o UA da ADR-0037.

O que é: `FontePlanalto` (`FonteColetavel`, `motor/fontes/base.py`) e `criar_fonte_planalto`. Ao
contrário da Cebraspe, o Planalto não publica uma listagem de itens que cresce sozinha — a
"novidade" aqui é uma norma do **catálogo fixo** deste módulo (`CATALOGO`) ainda não baixada
nesta rodada; uma norma nova (uma lei, uma emenda) entra como uma linha nova no catálogo, decidida
por quem lê o edital da aluna, não descoberta por varredura (ficha completa em
`knowledge/fontes.yaml`, id `planalto`).

O achado que motiva este módulo (ADR-0037; medição em
`.superpowers/sdd/V3b-multipla-escolha/fontes-juridicas-report.md` §0/§1.1): o Planalto recusa —
com TLS normal e corpo vazio, o que imita uma falha de rede sem ser uma — qualquer cliente cujo
`User-Agent` não comece com o token `Mozilla/5.0`. Uma ferramenta de fetch genérica que não deixa
o chamador controlar esse cabeçalho nunca funciona aqui; um cliente HTTP com cabeçalhos
explícitos (`httpx2`, o mesmo que a Cebraspe já usa) funciona.

Quando ler: antes de acrescentar uma norma ao catálogo ou de mudar o `User-Agent` do coletor
jurídico; ao investigar por que uma coleta do Planalto "parece" ter falhado.
"""

from collections.abc import Mapping
from types import TracebackType
from typing import Protocol

import httpx2
from pydantic import BaseModel

from aprovaos.config import Configuracoes
from aprovaos.motor.fontes.base import ArquivoBaixado, FonteIndisponivel, Novidade

USER_AGENT_TEMPLATE = "Mozilla/5.0 (compatible; AprovaOS-coletor/0.1; +contato: {contato})"
"""O User-Agent híbrido da ADR-0037.

Sem o prefixo `Mozilla/5.0`, o Planalto recusa a conexão (medido: `AprovaOS-coletor/0.1
(+contato: ...)`, o UA da Cebraspe/ADR-0030, dá `status=000`/0 bytes aqui). Com o prefixo, o UA
continua sendo uma identificação verdadeira — o mesmo padrão que bots legítimos como o Googlebot
usam (`Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)`).
"""

_ENCODING_PLANALTO = "cp1252"
"""Codificação padrão dos HTMLs compilados do Planalto — medido: o byte `0x92` (aspa curva) só
decodifica como caractere de verdade em Windows-1252; em ISO-8859-1 ele é um controle C1
indefinido."""

_BOM_UTF16_LE = b"\xff\xfe"
_BOM_UTF16_BE = b"\xfe\xff"
"""Achado desta rodada (catálogo ampliado, 19/09/2026): ao contrário da CF, da Lei 14.133 e das
demais normas do catálogo (todas `cp1252`), a página compilada da Lei 11.340/2006 (Maria da
Penha) vem em **UTF-16** com BOM. Decodificar esses bytes como `cp1252` sem checar o BOM produz
um caractere por byte (`"< h t m l >"`) e zero ocorrências de `"Art."` — não é uma falha de
estrutura do artigo, é a codificação errada aplicada aos bytes certos."""


class NormaCatalogada(BaseModel):
    """Uma norma que o catálogo fixo desta fonte sabe baixar.

    Attributes:
        titulo: descrição curta da norma, para exibição/log.
        url: URL do texto compilado no Planalto.
    """

    titulo: str
    url: str


CATALOGO: dict[str, NormaCatalogada] = {
    "cf-1988": NormaCatalogada(
        titulo="Constituição Federal de 1988 (texto compilado)",
        url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    ),
    "lei-14133-2021": NormaCatalogada(
        titulo="Lei nº 14.133, de 1º de abril de 2021 (texto compilado)",
        url="https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm",
    ),
    "clt": NormaCatalogada(
        titulo="CLT — Decreto-Lei nº 5.452, de 1º de maio de 1943 (texto compilado)",
        url="https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm",
    ),
    "lei-8429-1992": NormaCatalogada(
        titulo="Lei nº 8.429, de 2 de junho de 1992 — Improbidade Administrativa (texto compilado)",
        url="https://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
    ),
    "lei-6404-1976": NormaCatalogada(
        titulo="Lei nº 6.404, de 15 de dezembro de 1976 — Sociedade por Ações (texto compilado)",
        url="https://www.planalto.gov.br/ccivil_03/leis/l6404compilada.htm",
    ),
    "lei-11101-2005": NormaCatalogada(
        titulo="Lei nº 11.101, de 9 de fevereiro de 2005 — Recuperação Judicial e Falência "
        "(texto compilado)",
        url="https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2005/lei/l11101.htm",
    ),
    "lei-11340-2006": NormaCatalogada(
        titulo="Lei nº 11.340, de 7 de agosto de 2006 — Lei Maria da Penha (texto compilado)",
        url="https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11340.htm",
    ),
    "lei-6830-1980": NormaCatalogada(
        titulo="Lei nº 6.830, de 22 de setembro de 1980 — Execução Fiscal (texto compilado)",
        url="https://www.planalto.gov.br/ccivil_03/leis/l6830.htm",
    ),
    "lei-13105-2015": NormaCatalogada(
        titulo="Lei nº 13.105, de 16 de março de 2015 — Código de Processo Civil (texto compilado)",
        url="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm",
    ),
}
"""As normas que esta fonte sabe baixar hoje — cresce por norma (ver docstring do módulo). As
seis normas de `motor/ancorar.py` entraram na rodada de ampliação do catálogo (19/09/2026), na
ordem de nº de questões da base real que citam cada uma: CLT (11), Lei 8.429/1992 (5), Lei
6.404/1976 (3), Lei 11.101/2005 (3), Lei 11.340/2006 (3), Lei 6.830/1980 (2). O CPC (Lei
13.105/2015) entrou na fatia 4 (dossiês de tópico) — é a norma do tópico de maior peso medido
("Recursos: apelação, agravo, embargos", `dir-pro-civ-05-recursos-apelacao`) e revelou um
achado próprio: artigos ≥ 1.000 são grafados pelo Planalto com ponto de milhar
(`"Art. 1.009."`), o que exigiu corrigir `dominio.legislacao._padrao_caput` (ver
`docs/fatias/4-dossies-de-topico.md` §2)."""


class _RespostaHttp(Protocol):
    """O subconjunto de `httpx2.Response` que `FontePlanalto` usa."""

    @property
    def status_code(self) -> int:
        """Código de status HTTP da resposta."""
        ...

    @property
    def content(self) -> bytes:
        """Corpo cru da resposta, em bytes."""
        ...


class _ClienteHttp(Protocol):
    """O subconjunto de `httpx2.Client` que `FontePlanalto` usa."""

    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> _RespostaHttp:
        """Executa um `GET` e devolve a resposta."""
        ...


def decodificar_html(conteudo: bytes) -> str:
    """Decodifica o HTML compilado do Planalto para `str`, pronto para `dominio.legislacao`.

    A maioria das normas do catálogo vem em Windows-1252 (`cp1252`); a Lei 11.340/2006 é a
    exceção medida até agora — vem em UTF-16 com BOM (ver `_BOM_UTF16_LE`/`_BOM_UTF16_BE`). O
    BOM nos bytes crus decide a codificação; sem BOM, o padrão continua `cp1252`.

    Args:
        conteudo: bytes crus baixados de uma norma do catálogo.

    Returns:
        O texto decodificado, com `errors="replace"` — um byte/par inválido vira `�` em vez de
        interromper a extração inteira.
    """
    if conteudo.startswith(_BOM_UTF16_LE):
        return conteudo.decode("utf-16-le", errors="replace")
    if conteudo.startswith(_BOM_UTF16_BE):
        return conteudo.decode("utf-16-be", errors="replace")
    return conteudo.decode(_ENCODING_PLANALTO, errors="replace")


class FontePlanalto:
    """A fonte concreta do Planalto — implementa `FonteColetavel` (`base.py`).

    Attributes:
        contato: e-mail do dono, anunciado no `User-Agent` de toda requisição (ADR-0037).
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
        """Monta o `User-Agent` híbrido da ADR-0037 para cada requisição."""
        return {"User-Agent": USER_AGENT_TEMPLATE.format(contato=self._contato)}

    def listar_novidades(self, vistos: set[str]) -> list[Novidade]:
        """Lista as normas do catálogo fixo cujo id ainda não está em `vistos`.

        Ao contrário da Cebraspe, não há chamada de rede aqui — o catálogo é fixo no código
        (ver docstring do módulo); "novidade" é uma norma do catálogo ainda não baixada.

        Args:
            vistos: ids do catálogo (`CATALOGO`) já baixados em rodadas anteriores.

        Returns:
            As normas do catálogo ainda não vistas, `tipo="lei"`.
        """
        return [
            Novidade(
                id=id_norma,
                tipo="lei",
                titulo=norma.titulo,
                url=norma.url,
                evento=id_norma,
                publicado_em=None,
            )
            for id_norma, norma in CATALOGO.items()
            if id_norma not in vistos
        ]

    def baixar(self, novidade: Novidade) -> ArquivoBaixado:
        """Baixa o HTML compilado de uma novidade, com o `User-Agent` da ADR-0037.

        Args:
            novidade: item devolvido por `listar_novidades`.

        Returns:
            O conteúdo baixado (bytes crus — use `decodificar_html` antes de passar para
            `dominio.legislacao.extrair_artigo`), com hash e tamanho.

        Raises:
            FonteIndisponivel: a fonte está fora do ar, ou recusou a requisição (status >= 400 —
                inclusive o caso do Planalto sem o `User-Agent` certo, que fecha a conexão sem
                corpo antes mesmo de haver um status HTTP; `httpx2` reporta isso como erro de
                transporte, não como status 4xx/5xx).
        """
        try:
            resposta = self._cliente.get(novidade.url, headers=self._cabecalhos())
        except httpx2.HTTPError as erro:
            raise FonteIndisponivel(f"falha ao baixar {novidade.url}: {erro}") from erro
        if resposta.status_code >= 400:
            raise FonteIndisponivel(f"{novidade.url} devolveu status {resposta.status_code}")
        return ArquivoBaixado.de_conteudo(novidade, resposta.content)

    def fechar(self) -> None:
        """Fecha o cliente HTTP subjacente, se ele suportar `close()` (evita `ResourceWarning`)."""
        fechar = getattr(self._cliente, "close", None)
        if callable(fechar):
            fechar()

    def __enter__(self) -> "FontePlanalto":
        """Permite `with criar_fonte_planalto(config) as fonte:` — devolve a própria fonte."""
        return self

    def __exit__(
        self,
        tipo_excecao: type[BaseException] | None,
        excecao: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Fecha o cliente HTTP ao sair do bloco `with`, mesmo se uma exceção foi levantada."""
        self.fechar()


def criar_fonte_planalto(config: Configuracoes) -> FontePlanalto:
    """Fábrica: monta o `httpx2.Client` real e devolve a `FontePlanalto` pronta para uso.

    Nenhum I/O acontece na importação deste módulo — só nesta chamada explícita.

    Args:
        config: configurações do backend (usa `contato_coletor`, mesmo contato da ADR-0030).

    Returns:
        Uma `FontePlanalto` com cliente HTTP real (timeout de 30s, segue redirecionamentos).
    """
    cliente = httpx2.Client(
        headers={"User-Agent": USER_AGENT_TEMPLATE.format(contato=config.contato_coletor)},
        timeout=30,
        follow_redirects=True,
    )
    return FontePlanalto(cliente, config.contato_coletor)

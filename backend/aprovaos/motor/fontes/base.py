"""Contrato `FonteColetavel`: `Novidade`, `ArquivoBaixado`, a porta e os erros tipados.

O que é: os modelos e o `Protocol` que toda fonte concreta do coletor (Cebraspe, passo 4) segue —
o passo 2 da skill `.claude/skills/monitor-de-fontes/SKILL.md`. `Novidade` é a identidade de um
item na fonte (evento da listagem ou arquivo do detalhe); `ArquivoBaixado`, o conteúdo já baixado
com seu hash. Quando ler: antes de escrever uma fonte nova ou de mudar o que o coletor exige de
qualquer fonte.
"""

import hashlib
from datetime import UTC, datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, field_validator

TipoNovidade = Literal["prova", "gabarito", "edital", "lei", "desconhecido"]
"""Os cinco tipos de item que uma `Novidade` pode ser.

`"lei"` foi acrescentado para a fonte jurídica (`motor/fontes/planalto.py`, fundação da
justificativa ancorada) — já era um dos valores de `documento.tipo` no modelo de dados
(`docs/04-modelo-de-dados.md` §3, junto com `"informativo"`, ainda sem consumidor), só não
existia aqui porque nenhuma fonte concreta produzia esse tipo até agora.
"""


class Novidade(BaseModel):
    """Um item novo detectado numa fonte — evento da listagem ou arquivo do detalhe.

    Attributes:
        id: identidade estável do item na fonte, entre rodadas de coleta — nunca hash de título
            nem posição na lista (skill `monitor-de-fontes`, passo 2). As duas identidades cabem
            neste mesmo campo: uma novidade de *listagem* é a identidade do evento (prova/
            concurso), com `tipo="desconhecido"` até o detalhe ser aberto; uma novidade de
            *detalhe* é a identidade do arquivo dentro desse evento. Cada fonte concreta define
            como compõe esses ids e documenta isso na sua ficha em `knowledge/fontes.yaml`.
        tipo: classificação do item; `"desconhecido"` quando a fonte não a informa (ex.: evento
            da listagem, antes de abrir o detalhe) ou quando nenhuma regra da ficha casa.
        titulo: texto descritivo cru do item, exatamente como a fonte o descreve, sem
            normalização. Quem preenche este campo é a fonte concreta.
        url: URL de onde o item foi listado ou de onde o arquivo será baixado.
        evento: identidade do evento (prova/concurso) ao qual o item pertence na fonte.
        publicado_em: instante de publicação, *aware* em UTC; `None` quando a fonte não informa.
            Quem converte o fuso da fonte para UTC é a fonte concreta; um `datetime` naive é
            rejeitado (mesma regra de `DataHoraUtc` em `aprovaos/dados/base.py`).
    """

    id: str
    tipo: TipoNovidade
    titulo: str
    url: str
    evento: str
    publicado_em: datetime | None

    @field_validator("publicado_em", mode="after")
    @classmethod
    def _exige_aware_e_normaliza_utc(cls, valor: datetime | None) -> datetime | None:
        """Rejeita `datetime` naive e normaliza qualquer fuso *aware* para UTC."""
        if valor is None:
            return None
        if valor.tzinfo is None:
            raise ValueError("publicado_em exige datetime aware (com tzinfo)")
        return valor.astimezone(UTC)


class ArquivoBaixado(BaseModel):
    """O conteúdo de uma `Novidade` já baixado, com hash e tamanho para deduplicação.

    Attributes:
        novidade: a novidade de onde este arquivo veio.
        conteudo: os bytes exatamente como a fonte serviu — quem grava em disco é o passo 5.
        hash: `sha256` hexadecimal do conteúdo.
        tamanho: tamanho do conteúdo em bytes.
    """

    novidade: Novidade
    conteudo: bytes
    hash: str
    tamanho: int

    @classmethod
    def de_conteudo(cls, novidade: Novidade, conteudo: bytes) -> "ArquivoBaixado":
        """Monta o `ArquivoBaixado` a partir do conteúdo baixado, calculando hash e tamanho.

        Args:
            novidade: a novidade correspondente ao conteúdo.
            conteudo: os bytes baixados da fonte.

        Returns:
            `ArquivoBaixado` com `hash = sha256(conteudo).hexdigest()` e `tamanho = len(conteudo)`.
        """
        return cls(
            novidade=novidade,
            conteudo=conteudo,
            hash=hashlib.sha256(conteudo).hexdigest(),
            tamanho=len(conteudo),
        )


class FonteVetada(RuntimeError):
    """A fonte tem termos de uso ou `robots.txt` que proíbem a coleta automatizada.

    O construtor da fonte concreta recusa nascer com esta exceção quando a ficha em
    `knowledge/fontes.yaml` traz `status: vetada` (skill `monitor-de-fontes`, passo 1).
    """


class FonteIndisponivel(RuntimeError):
    """A fonte está fora do ar (rede, 5xx) — nunca deve virar "sem novidade" silencioso.

    Existe para que `listar_novidades`/`baixar` distingam falha de indisponibilidade real de uma
    lista vazia por não haver item novo; esconder essa diferença mascararia uma falha de rede.
    """


@runtime_checkable
class FonteColetavel(Protocol):
    """Porta que toda fonte concreta do coletor (Cebraspe, passo 4) implementa."""

    def listar_novidades(self, vistos: set[str]) -> list[Novidade]:
        """Lista os itens da fonte cujo `id` não está em `vistos`.

        Args:
            vistos: conjunto de `Novidade.id` já processados em rodadas anteriores.

        Returns:
            As novidades encontradas (pode ser vazia quando não há item novo).

        Raises:
            FonteIndisponivel: a fonte está fora do ar.
        """
        ...

    def baixar(self, novidade: Novidade) -> ArquivoBaixado:
        """Baixa o conteúdo de uma novidade.

        Args:
            novidade: item devolvido por `listar_novidades`.

        Returns:
            O conteúdo baixado, com hash e tamanho.

        Raises:
            FonteIndisponivel: a fonte está fora do ar.
        """
        ...

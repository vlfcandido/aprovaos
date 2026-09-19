"""Repositório de `dispositivo_legal`/`citacao`: dedup determinístico (fundação jurídica, passo 2).

O que é: `buscar_ou_criar_dispositivo` (get-or-create por `citacao_canonica` — único, como a
migração 0005 exige: recoletar o mesmo dispositivo nunca duplica linha) e `registrar_citacao`
(get-or-create por `(conteudo_tipo, conteudo_id, dispositivo_id)` — rodar o comando de ancoragem
duas vezes sobre a mesma questão não duplica a linha em `citacao`). Quem chama decide o
`commit`; aqui só há `add`/`flush`, como o resto dos repositórios (`repositorio_questao.py`).

Quando ler: ao ligar o comando `motor/ancorar.py`, ou ao investigar uma linha duplicada em
`dispositivo_legal`/`citacao`.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Citacao, DispositivoLegal


def buscar_ou_criar_dispositivo(
    db: Session,
    *,
    citacao_canonica: str,
    norma: str,
    artigo: str,
    inciso: str | None,
    paragrafo: str | None,
    texto: str,
    vigente: bool,
    fonte_url: str,
) -> DispositivoLegal:
    """Devolve o `DispositivoLegal` de `citacao_canonica`, criando-o se ainda não existir.

    Args:
        db: sessão do comando/rota.
        citacao_canonica: identificador único do dispositivo (ex.: `"CF/88 art. 37"`,
            `"CF/88 art. 37 II"`, `"Lei 14.133/2021 art. 6 IX"`) — a `UNIQUE` da migração 0005.
        norma: id estável da norma (`dominio.citacao.ReferenciaLegal.norma`).
        artigo: número do artigo, sem ordinal.
        inciso: identificador do inciso (algarismo romano), quando a citação desce a esse nível.
        paragrafo: número do parágrafo, sem ordinal, quando a citação desce a esse nível.
        texto: texto literal vigente do trecho (`dominio.legislacao.TrechoDispositivo.texto`).
        vigente: `True` quando o trecho gravado é o vigente (sempre `True` nesta rodada —
            `extrair_artigo` já descarta o texto revogado antes de devolver qualquer trecho).
        fonte_url: URL de onde o texto foi coletado (Planalto).

    Returns:
        A linha existente (nenhum campo é atualizado nela) ou a linha recém-criada.
    """
    existente = db.scalars(
        select(DispositivoLegal).where(DispositivoLegal.citacao_canonica == citacao_canonica)
    ).first()
    if existente is not None:
        return existente

    dispositivo = DispositivoLegal(
        citacao_canonica=citacao_canonica,
        norma=norma,
        artigo=artigo,
        inciso=inciso,
        paragrafo=paragrafo,
        texto=texto,
        vigente=vigente,
        fonte_url=fonte_url,
    )
    db.add(dispositivo)
    db.flush()
    return dispositivo


def registrar_citacao(
    db: Session,
    *,
    conteudo_tipo: str,
    conteudo_id: UUID,
    dispositivo_id: UUID,
    posicao: int,
) -> Citacao | None:
    """Liga `dispositivo_id` a `conteudo_id`, salvo se a ligação já existir.

    Args:
        db: sessão do comando/rota.
        conteudo_tipo: `"questao"`, `"aula"` ou `"dossie"` (`CheckConstraint` da migração 0005).
        conteudo_id: chave do conteúdo citante.
        dispositivo_id: chave do `DispositivoLegal` citado.
        posicao: ordem da citação dentro do conteúdo (1ª, 2ª...).

    Returns:
        A `Citacao` recém-criada; `None` quando esta ligação já existia (rodar o comando de novo
        sobre a mesma questão não duplica a linha).
    """
    ja_existe = (
        db.scalars(
            select(Citacao.id).where(
                Citacao.conteudo_tipo == conteudo_tipo,
                Citacao.conteudo_id == conteudo_id,
                Citacao.dispositivo_id == dispositivo_id,
            )
        ).first()
        is not None
    )
    if ja_existe:
        return None

    citacao = Citacao(
        conteudo_tipo=conteudo_tipo,
        conteudo_id=conteudo_id,
        dispositivo_id=dispositivo_id,
        posicao=posicao,
    )
    db.add(citacao)
    db.flush()
    return citacao

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

from sqlalchemy import func, select
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


def buscar_dispositivo_por_citacao_canonica(
    db: Session, citacao_canonica: str
) -> DispositivoLegal | None:
    """Busca um `DispositivoLegal` já gravado, sem criar.

    Usado por `motor.ligar_por_topico`, que assume que
    `dados.repositorio_dossie.salvar_dossie` já criou o dispositivo de cada fonte do dossiê
    antes de ligar as questões a ele.

    Args:
        db: sessão do comando/rota.
        citacao_canonica: identificador único do dispositivo.

    Returns:
        A linha existente, ou `None` se nenhum dispositivo tem essa `citacao_canonica`.
    """
    return db.scalars(
        select(DispositivoLegal).where(DispositivoLegal.citacao_canonica == citacao_canonica)
    ).first()


def dispositivos_da_questao(db: Session, questao_id: UUID) -> list[DispositivoLegal]:
    """Os dispositivos ligados a uma questão, na ordem de `Citacao.posicao`.

    Usado pelo comando `motor.justificar` para montar a única fonte que o agente
    `gerador-de-justificativa` pode citar (regra 1 da fundação jurídica, passo 5): uma questão
    sem nenhuma linha aqui não pode gerar justificativa nesta rodada — lista vazia é o sinal
    disso, não uma falha.

    Args:
        db: sessão de banco.
        questao_id: chave da questão.

    Returns:
        Os `DispositivoLegal` ligados a `questao_id` (`conteudo_tipo="questao"`), ordenados por
        `posicao`; lista vazia se nenhum estiver ligado ainda.
    """
    consulta = (
        select(DispositivoLegal)
        .join(Citacao, Citacao.dispositivo_id == DispositivoLegal.id)
        .where(Citacao.conteudo_tipo == "questao", Citacao.conteudo_id == questao_id)
        .order_by(Citacao.posicao)
    )
    return list(db.scalars(consulta).all())


def maior_posicao(db: Session, *, conteudo_tipo: str, conteudo_id: UUID) -> int:
    """Devolve a maior `posicao` já gravada em `citacao` para este conteúdo (`0` se nenhuma).

    Usado para continuar a numeração ao acrescentar citações vindas de uma via diferente da
    que já gravou algumas (ex.: `motor.ancorar` cita por texto; `motor.ligar_por_topico` liga
    por tópico depois) sem colidir posições.

    Args:
        db: sessão do comando/rota.
        conteudo_tipo: `"questao"`, `"aula"` ou `"dossie"`.
        conteudo_id: chave do conteúdo citante.

    Returns:
        A maior `posicao` gravada, ou `0` quando o conteúdo ainda não tem nenhuma citação.
    """
    maior = db.scalar(
        select(func.max(Citacao.posicao)).where(
            Citacao.conteudo_tipo == conteudo_tipo, Citacao.conteudo_id == conteudo_id
        )
    )
    return maior or 0


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

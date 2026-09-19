"""Repositório de `aula`: versionamento por tópico (fatia 6, trilha e aulas em texto).

O que é: `proxima_versao` (mesmo desenho de `dados.repositorio_dossie.proxima_versao`) e
`salvar_aula`, que grava uma `dominio.aula.ConteudoAula` já aprovada pelo validador
(`dominio.aula.verificar_aula`) como a próxima versão da aula do tópico — **nunca chamado com
uma aula reprovada**; quem decide isso é o comando (`motor/aula.py`), não este módulo.
`aula_publicada_do_topico` é a leitura que a tela usa para servir a aula à aluna — desde a
correção estrutural de 19/09/2026 (ADR-0041, fecha a P-52), sem aula própria de `topico_id` ela
tenta os tópicos equivalentes (`repositorio_topico_relacao.topicos_equivalentes`, origem
`equivalencia_curada`) e, sem achar, os de cobertura parcial (`topicos_subconjunto`, origem
`subconjunto_curado` — I1 de uma revisão independente no mesmo dia) antes de devolver `None`,
para a aula gerada sob o vocabulário de um edital aparecer também no tópico ligado de outro
edital, inteiro ou em parte. `aula_publicada_do_topico_com_origem` é a mesma busca, mas devolve
também de onde a aula veio — é o que a trilha (`GET /concurso/{id}/trilha`) usa para avisar
"cobre só parte do item" quando a origem é `subconjunto_curado`, sem precisar mexer em
`dominio.aula`/nos templates de aula. Quem chama decide o `commit`; aqui só há `add`/`flush`,
como o resto dos repositórios.

Quando ler: ao ligar o comando `motor/aula.py`, ou ao investigar uma versão de aula que não
incrementou, uma aula que não aparece na tela, ou uma cobertura parcial servida sem aviso.
"""

from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Aula, DossieTopico
from aprovaos.dados.repositorio_topico_relacao import topicos_equivalentes, topicos_subconjunto
from aprovaos.dominio.aula import ConteudoAula

#: De onde `aula_publicada_do_topico_com_origem` encontrou a aula: gravada diretamente sob o
#: tópico pedido, por equivalência plena, ou por cobertura parcial (I1) — só o último caso pede
#: aviso na tela.
OrigemAulaEncontrada = Literal["direta", "equivalencia_curada", "subconjunto_curado"]


def proxima_versao(db: Session, topico_id: UUID) -> int:
    """Devolve a próxima `versao` de `aula` para `topico_id` (1 se não houver nenhuma).

    Args:
        db: sessão de banco.
        topico_id: o tópico cuja próxima versão de aula se quer saber.

    Returns:
        `1` para a primeira aula do tópico; `max(versao) + 1` daí em diante.
    """
    maior = db.scalar(select(func.max(Aula.versao)).where(Aula.topico_id == topico_id))
    return 1 if maior is None else maior + 1


def salvar_aula(
    db: Session, *, topico_id: UUID, dossie: DossieTopico, conteudo: ConteudoAula
) -> Aula:
    """Grava `conteudo` como a próxima versão da aula de `topico_id`, já publicada.

    Args:
        db: sessão de banco.
        topico_id: o tópico dono desta aula.
        dossie: o `DossieTopico` de onde a aula veio (grava `dossie_id`/`dossie_versao`).
        conteudo: o `ConteudoAula` já aprovado por `dominio.aula.verificar_aula` — este módulo
            não valida de novo, só persiste.

    Returns:
        A `Aula` recém-criada (não faz `commit` — quem chama decide), com `publicada=True` e
        `validado_em` preenchido.
    """
    aula = Aula(
        dossie_id=dossie.id,
        dossie_versao=dossie.versao,
        topico_id=topico_id,
        versao=proxima_versao(db, topico_id),
        texto_denso=conteudo.texto_denso,
        texto_leigo=conteudo.texto_leigo,
        audio_url=None,
        citacoes=[c.model_dump(mode="json") for c in conteudo.citacoes],
        relacionados=[r.model_dump(mode="json") for r in conteudo.relacionados],
        como_a_banca_cobra=[c.model_dump(mode="json") for c in conteudo.como_a_banca_cobra],
        lacunas_declaradas=list(conteudo.lacunas_declaradas),
        mnemonico=conteudo.mnemonico.model_dump(mode="json") if conteudo.mnemonico else None,
        validado_em=agora_utc(),
        publicada=True,
    )
    db.add(aula)
    db.flush()
    return aula


def _aula_publicada_direta(db: Session, topico_id: UUID) -> Aula | None:
    """A última versão publicada da aula gravada diretamente sob `topico_id`."""
    return db.scalars(
        select(Aula)
        .where(Aula.topico_id == topico_id, Aula.publicada.is_(True))
        .order_by(Aula.versao.desc())
        .limit(1)
    ).first()


def aula_publicada_do_topico_com_origem(
    db: Session, topico_id: UUID
) -> tuple[Aula, OrigemAulaEncontrada] | None:
    """A última aula publicada de `topico_id`, com de onde ela veio (ADR-0041; I1).

    Tenta, nesta ordem: `topico_id` diretamente; cada tópico de equivalência plena
    (`repositorio_topico_relacao.topicos_equivalentes`, origem `equivalencia_curada`); cada
    tópico de cobertura parcial (`topicos_subconjunto`, origem `subconjunto_curado`) — sempre na
    ordem em que a relação foi criada, devolvendo a primeira aula publicada que encontrar.

    Args:
        db: sessão do request.
        topico_id: o tópico cuja aula se quer servir.

    Returns:
        `(aula, origem)` da primeira aula publicada encontrada; `None` se nem `topico_id` nem
        nenhum tópico ligado (pleno ou parcial) tiver aula publicada.
    """
    direta = _aula_publicada_direta(db, topico_id)
    if direta is not None:
        return direta, "direta"
    for equivalente_id in topicos_equivalentes(db, topico_id):
        encontrada = _aula_publicada_direta(db, equivalente_id)
        if encontrada is not None:
            return encontrada, "equivalencia_curada"
    for parcial_id in topicos_subconjunto(db, topico_id):
        encontrada = _aula_publicada_direta(db, parcial_id)
        if encontrada is not None:
            return encontrada, "subconjunto_curado"
    return None


def aula_publicada_do_topico(db: Session, topico_id: UUID) -> Aula | None:
    """A última versão publicada da aula de `topico_id`, direta, por equivalência ou subconjunto.

    ADR-0041, fecha a P-52; I1. Atalho de `aula_publicada_do_topico_com_origem` para quem só
    precisa da `Aula` (a rota `GET /topico/{slug}/aula` — a página de aula em si não distingue
    cobertura parcial nesta correção, ver o cabeçalho do módulo): a aula gerada sob o vocabulário
    de um edital passa a ser encontrada também pelo tópico ligado de outro edital, inteiro ou em
    parte.

    Args:
        db: sessão do request.
        topico_id: o tópico cuja aula se quer servir.

    Returns:
        A `Aula` de maior `versao` com `publicada=True`; `None` se nem `topico_id` nem nenhum
        tópico ligado (pleno ou parcial) tiver aula publicada.
    """
    encontrada = aula_publicada_do_topico_com_origem(db, topico_id)
    return encontrada[0] if encontrada is not None else None

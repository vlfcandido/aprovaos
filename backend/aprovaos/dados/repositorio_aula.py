"""Repositório de `aula`: versionamento por tópico (fatia 6, trilha e aulas em texto).

O que é: `proxima_versao` (mesmo desenho de `dados.repositorio_dossie.proxima_versao`) e
`salvar_aula`, que grava uma `dominio.aula.ConteudoAula` já aprovada pelo validador
(`dominio.aula.verificar_aula`) como a próxima versão da aula do tópico — **nunca chamado com
uma aula reprovada**; quem decide isso é o comando (`motor/aula.py`), não este módulo.
`aula_publicada_do_topico` é a leitura que a tela usa para servir a aula à aluna — desde a
correção estrutural de 19/09/2026 (ADR-0041, fecha a P-52), sem aula própria de `topico_id` ela
tenta os tópicos equivalentes (`repositorio_topico_relacao.topicos_equivalentes`, origem
`equivalencia_curada`) antes de devolver `None`, para a aula gerada sob o vocabulário de um
edital aparecer também no tópico equivalente de outro edital. Quem chama decide o `commit`; aqui
só há `add`/`flush`, como o resto dos repositórios.

Quando ler: ao ligar o comando `motor/aula.py`, ou ao investigar uma versão de aula que não
incrementou ou uma aula que não aparece na tela.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Aula, DossieTopico
from aprovaos.dados.repositorio_topico_relacao import topicos_equivalentes
from aprovaos.dominio.aula import ConteudoAula


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


def aula_publicada_do_topico(db: Session, topico_id: UUID) -> Aula | None:
    """A última versão publicada da aula de `topico_id`, direta ou por equivalência (ADR-0041).

    Primeiro tenta `topico_id` diretamente; sem aula ali, tenta cada tópico equivalente
    (`repositorio_topico_relacao.topicos_equivalentes`, origem `equivalencia_curada`), na ordem
    em que a relação foi criada, e devolve a primeira aula publicada que encontrar. Fecha a
    P-52: a aula gerada sob o vocabulário de um edital passa a ser encontrada também pelo tópico
    equivalente de outro edital.

    Args:
        db: sessão do request.
        topico_id: o tópico cuja aula se quer servir.

    Returns:
        A `Aula` de maior `versao` com `publicada=True`; `None` se nem `topico_id` nem nenhum
        equivalente tiver aula publicada.
    """
    direta = _aula_publicada_direta(db, topico_id)
    if direta is not None:
        return direta
    for equivalente_id in topicos_equivalentes(db, topico_id):
        encontrada = _aula_publicada_direta(db, equivalente_id)
        if encontrada is not None:
            return encontrada
    return None

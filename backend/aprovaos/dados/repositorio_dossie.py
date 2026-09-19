"""Repositório de `dossie_topico`: versionamento por tópico (fundação jurídica, passo 3).

`salvar_dossie` grava a linha do dossiê na próxima versão do tópico (`proxima_versao`) e,
para cada `FonteDossie` de `tipo="norma"`, reaproveita
`dados.repositorio_citacao.buscar_ou_criar_dispositivo` (mesma dedup por `citacao_canonica` que
`motor.ancorar` usa) — assim o dossiê e a ancoragem por texto sempre apontam para o mesmo
`DispositivoLegal` quando citam o mesmo dispositivo. Uma `FonteDossie` de `tipo="sumula"`
(fatia 4, jurisprudência) **não** vira `DispositivoLegal` — essa tabela é, pelo próprio contrato
(migração 0005), "um dispositivo de norma"; a súmula fica gravada no JSON de
`dossie_topico.fontes` (com número, texto integral e URL), auditável, mas fora do alcance de
`motor.ligar_por_topico` nesta rodada (decisão registrada em `docs/fatias/4-dossies-de-topico
.md` §1.3). Quem chama decide o `commit`; aqui só há `add`/`flush`, como o resto dos
repositórios.

`dossie_mais_recente_do_topico` (ADR-0041, fecha a P-52) generaliza a leitura: quando `topico_id`
não tem `DossieTopico` nenhum, tenta os tópicos equivalentes a ele
(`repositorio_topico_relacao.topicos_equivalentes`, origem `equivalencia_curada`) antes de
devolver `None` — é o que faz o dossiê gerado sob o vocabulário de um edital aparecer também para
o tópico equivalente de outro edital, sem duplicar o dossiê nem migrar `topico_id`.

Quando ler: ao ligar o comando `motor/dossie.py`, ou ao investigar uma versão de dossiê que não
incrementou.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import DossieTopico
from aprovaos.dados.repositorio_citacao import buscar_ou_criar_dispositivo
from aprovaos.dados.repositorio_topico_relacao import topicos_equivalentes
from aprovaos.dominio.dossie import ConteudoDossie


def proxima_versao(db: Session, topico_id: UUID) -> int:
    """Devolve a próxima `versao` de `dossie_topico` para `topico_id` (1 se não houver nenhuma).

    Args:
        db: sessão de banco.
        topico_id: o tópico cuja próxima versão se quer saber.

    Returns:
        `1` para o primeiro dossiê do tópico; `max(versao) + 1` daí em diante.
    """
    maior = db.scalar(
        select(func.max(DossieTopico.versao)).where(DossieTopico.topico_id == topico_id)
    )
    return 1 if maior is None else maior + 1


def salvar_dossie(db: Session, *, topico_id: UUID, conteudo: ConteudoDossie) -> DossieTopico:
    """Grava `conteudo` como a próxima versão do dossiê de `topico_id` e os dispositivos citados.

    Args:
        db: sessão de banco.
        topico_id: o tópico dono deste dossiê.
        conteudo: o que `dominio.dossie.montar_dossie` produziu.

    Returns:
        A `DossieTopico` recém-criada (não faz `commit` — quem chama decide).
    """
    dossie = DossieTopico(
        topico_id=topico_id,
        versao=proxima_versao(db, topico_id),
        gerado_em=agora_utc(),
        conteudo=conteudo.conteudo,
        fontes=[fonte.model_dump(mode="json") for fonte in conteudo.fontes],
        bibliografia=list(conteudo.bibliografia),
        log_buscas=[entrada.model_dump(mode="json") for entrada in conteudo.log_buscas],
        validado_em=None,
        substituido_por=None,
    )
    db.add(dossie)
    db.flush()

    for fonte in conteudo.fontes:
        if fonte.tipo != "norma":
            continue  # súmula (fatia 4): fica só no dossiê, não vira `dispositivo_legal` ainda
        assert fonte.norma is not None and fonte.artigo is not None  # garantido por `tipo="norma"`
        buscar_ou_criar_dispositivo(
            db,
            citacao_canonica=fonte.citacao_canonica,
            norma=fonte.norma,
            artigo=fonte.artigo,
            inciso=fonte.inciso,
            paragrafo=fonte.paragrafo,
            texto=fonte.trecho,
            vigente=fonte.vigente,
            fonte_url=fonte.url,
        )
        db.flush()

    return dossie


def _dossie_direto_mais_recente(db: Session, topico_id: UUID) -> DossieTopico | None:
    """A versão mais recente de `dossie_topico` gravada diretamente sob `topico_id`."""
    return db.scalars(
        select(DossieTopico)
        .where(DossieTopico.topico_id == topico_id)
        .order_by(DossieTopico.versao.desc())
        .limit(1)
    ).first()


def dossie_mais_recente_do_topico(db: Session, topico_id: UUID) -> DossieTopico | None:
    """A versão mais recente do dossiê de `topico_id`, direto ou por equivalência (ADR-0041).

    Primeiro tenta `topico_id` diretamente; sem nenhum dossiê ali, tenta cada tópico equivalente
    (`repositorio_topico_relacao.topicos_equivalentes`, origem `equivalencia_curada`), na ordem
    em que a relação foi criada, e devolve o primeiro que tiver dossiê. Fecha a P-52: o dossiê
    gerado sob o vocabulário de um edital passa a ser encontrado também pelo tópico equivalente
    de outro edital, sem duplicar conteúdo nem migrar `topico_id`.

    Args:
        db: sessão de banco (só leitura).
        topico_id: o tópico cujo dossiê se quer.

    Returns:
        A `DossieTopico` de maior `versao` encontrada; `None` se nem `topico_id` nem nenhum
        equivalente tiver dossiê.
    """
    direto = _dossie_direto_mais_recente(db, topico_id)
    if direto is not None:
        return direto
    for equivalente_id in topicos_equivalentes(db, topico_id):
        encontrado = _dossie_direto_mais_recente(db, equivalente_id)
        if encontrado is not None:
            return encontrado
    return None

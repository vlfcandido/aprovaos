"""Repositório de edital: persiste o resultado do pipeline da V2 e consulta o que as páginas usam.

O que é: `registrar_edital` (concurso + edital + documento + tópicos por slug + `dna_concurso`),
`listar_concursos_do_tenant`/`concurso_principal` (premissa A: principal = o último subido),
`buscar_concurso`, `edital_atual`, `dna_atual` e `verticalizado` (matérias → tópicos, todos
"não visto" na V2). Quando ler: ao escrever a rota de upload ou a página do concurso. Faz
`add`/`flush`; o `commit` é sempre da rota (convenção transversal).
"""

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.agentes.analista_de_edital import ResultadoDna
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Concurso,
    DnaConcursoRegistro,
    Documento,
    Edital,
    Topico,
    TopicoEdital,
)
from aprovaos.dominio.edital import DESCONHECIDO, MateriaExtraida, slug_materia

_NUMERO_DO_ITEM = re.compile(r"^\d+\.\s*")
_TRES_CASAS = Decimal("0.001")
STATUS_NAO_VISTO: Final = "não visto"


class DadosDocumento(BaseModel):
    """O que a rota sabe sobre o PDF subido, para a linha de `documento`.

    Attributes:
        hash: SHA-256 hexadecimal do conteúdo.
        caminho_relativo: nome do arquivo dentro de `uploads_dir` (`<hash>.pdf`).
        nome_original: nome do arquivo como veio do navegador.
        tamanho: bytes do arquivo.
        paginas: número de páginas do PDF.
    """

    hash: str
    caminho_relativo: str
    nome_original: str
    tamanho: int
    paginas: int


class TopicoVerticalizado(BaseModel):
    """Um tópico do edital verticalizado, pronto para o template.

    `id` existe só para a rota juntar este tópico com `contagem_por_topico`/`topicos_vistos`
    (repositório de questões) sem uma segunda ida ao banco por `slug` — este módulo não sabe de
    `questao` nem de usuário; quem soma contagem e status por aluno é a rota (passo 14 da V3).

    Attributes:
        id: chave do tópico (vocabulário global).
        slug: slug global do tópico.
        texto_original: o item como está no edital.
        status: `não visto` aqui sempre — este módulo não sabe de eventos de estudo; a rota
            sobrescreve para `visto` quando o aluno já respondeu (passo 14 da V3).
    """

    id: UUID
    slug: str
    texto_original: str
    status: Literal["não visto"] = STATUS_NAO_VISTO


class MateriaVerticalizada(BaseModel):
    """Uma matéria do edital verticalizado com seus tópicos na ordem do edital.

    Attributes:
        nome: nome como está no edital (`LÍNGUA PORTUGUESA`).
        slug: `slug_materia(nome)`, a chave usada em `pesos.materia` do DNA.
        grupo: cabeçalho agrupador acima da matéria no edital (ex.: `CONHECIMENTOS
            ESPECÍFICOS`), vindo de `topico_edital.grupo`; `None` quando a matéria aparece
            solta (P-26).
        topicos: tópicos na ordem do edital.
    """

    nome: str
    slug: str
    grupo: str | None = None
    topicos: list[TopicoVerticalizado]


def _nome_do_topico(texto_original: str) -> str:
    """Tira o número do item (`4. Licitações…` → `Licitações…`) para `topico.nome`."""
    return _NUMERO_DO_ITEM.sub("", texto_original).strip()


def _peso_edital(valor: float | str) -> Decimal | None:
    """`pct_uniforme` do DNA arredondado a 3 casas, ou `None` quando `desconhecido`."""
    if isinstance(valor, str):
        return None
    return Decimal(str(valor)).quantize(_TRES_CASAS, rounding=ROUND_HALF_UP)


def _obter_ou_criar_topico(db: Session, materia: MateriaExtraida, slug: str, texto: str) -> Topico:
    """Get-or-create de `topico` por `slug` (premissa D: vocabulário global)."""
    topico = db.scalars(select(Topico).where(Topico.slug == slug)).first()
    if topico is None:
        topico = Topico(materia=materia.nome, nome=_nome_do_topico(texto), slug=slug)
        db.add(topico)
        db.flush()
    return topico


def registrar_edital(
    db: Session,
    tenant_id: UUID,
    resultado: ResultadoDna,
    materias: list[MateriaExtraida],
    documento: DadosDocumento,
    modelo: str | None = None,
) -> Concurso:
    """Persiste concurso, edital (versão 1), documento, tópicos, `topico_edital` e o DNA.

    Faz `add` + `flush`; a rota faz o `commit`. `ordem` conta de 1 a N na sequência
    matéria → item do edital; `peso_edital` é o `pct_uniforme` do DNA em 3 casas.

    Args:
        db: sessão do request.
        tenant_id: dono do concurso.
        resultado: DNA e origem (`ia`/`regras`) vindos de `gerar_dna`.
        materias: conteúdo programático extraído pelo parser (mesma lista dada ao DNA).
        documento: dados do PDF subido.
        modelo: modelo de LLM usado quando `origem == "ia"`; `None` por regras.

    Returns:
        O `Concurso` novo, já com `id`.
    """
    dna = resultado.dna
    agora = agora_utc()
    concurso = Concurso(
        tenant_id=tenant_id,
        orgao=dna.concurso.orgao,
        cargo=dna.concurso.cargo,
        banca=dna.concurso.banca,
        data_prova=None if dna.concurso.data_prova == DESCONHECIDO else dna.concurso.data_prova,
    )
    linha_documento = Documento(
        tipo="edital",
        hash=documento.hash,
        caminho=documento.caminho_relativo,
        baixado_em=agora,
        metadados={
            "nome_original": documento.nome_original,
            "tamanho": documento.tamanho,
            "paginas": documento.paginas,
        },
    )
    edital = Edital(concurso=concurso, versao=1, documento=linha_documento)
    db.add_all([concurso, linha_documento, edital])
    db.flush()

    ordem = 0
    for materia in materias:
        for item in materia.topicos:
            ordem += 1
            topico = _obter_ou_criar_topico(db, materia, item.slug, item.texto_original)
            peso = dna.pesos.topico.get(item.slug)
            db.add(
                TopicoEdital(
                    edital=edital,
                    topico=topico,
                    ordem=ordem,
                    peso_edital=_peso_edital(peso.pct_uniforme) if peso else None,
                    texto_original=item.texto_original,
                    grupo=materia.grupo,
                )
            )

    db.add(
        DnaConcursoRegistro(
            concurso=concurso,
            versao=1,
            gerado_em=agora,
            origem=resultado.origem,
            modelo=modelo,
            motivo_fallback=resultado.motivo_fallback,
            conteudo=dna.model_dump(mode="json"),
        )
    )
    db.flush()
    return concurso


def listar_concursos_do_tenant(db: Session, tenant_id: UUID) -> list[Concurso]:
    """Concursos do tenant, o mais recente primeiro (`criado_em` desc).

    Args:
        db: sessão do request.
        tenant_id: dono dos concursos.

    Returns:
        Lista possivelmente vazia.
    """
    consulta = (
        select(Concurso).where(Concurso.tenant_id == tenant_id).order_by(Concurso.criado_em.desc())
    )
    return list(db.scalars(consulta).all())


def concurso_principal(db: Session, tenant_id: UUID) -> Concurso | None:
    """O concurso principal do tenant: o último subido (premissa A da V2; P-23 para o perfil).

    Args:
        db: sessão do request.
        tenant_id: dono dos concursos.

    Returns:
        O `Concurso` mais recente, ou `None` sem nenhum.
    """
    lista = listar_concursos_do_tenant(db, tenant_id)
    return lista[0] if lista else None


def buscar_concurso(db: Session, concurso_id: UUID) -> Concurso | None:
    """Localiza um concurso pelo `id` (a checagem de tenant é da rota).

    Args:
        db: sessão do request.
        concurso_id: chave do concurso.

    Returns:
        O `Concurso`, ou `None`.
    """
    return db.get(Concurso, concurso_id)


def edital_atual(db: Session, concurso_id: UUID) -> Edital | None:
    """O edital de maior `versao` do concurso.

    Args:
        db: sessão do request.
        concurso_id: chave do concurso.

    Returns:
        O `Edital`, ou `None` se o concurso não tiver edital.
    """
    consulta = (
        select(Edital).where(Edital.concurso_id == concurso_id).order_by(Edital.versao.desc())
    )
    return db.scalars(consulta).first()


def dna_atual(db: Session, concurso_id: UUID) -> DnaConcursoRegistro | None:
    """O registro de `dna_concurso` de maior `versao` do concurso.

    Args:
        db: sessão do request.
        concurso_id: chave do concurso.

    Returns:
        O `DnaConcursoRegistro`, ou `None`.
    """
    consulta = (
        select(DnaConcursoRegistro)
        .where(DnaConcursoRegistro.concurso_id == concurso_id)
        .order_by(DnaConcursoRegistro.versao.desc())
    )
    return db.scalars(consulta).first()


def verticalizado(db: Session, edital_id: UUID) -> list[MateriaVerticalizada]:
    """O edital verticalizado: matérias na ordem do edital, cada uma com seus tópicos.

    Args:
        db: sessão do request.
        edital_id: chave do edital.

    Returns:
        Lista de `MateriaVerticalizada` (Pydantic, pronta para o template); todo tópico
        `não visto` na V2.
    """
    consulta = (
        select(TopicoEdital, Topico)
        .join(Topico, TopicoEdital.topico_id == Topico.id)
        .where(TopicoEdital.edital_id == edital_id)
        .order_by(TopicoEdital.ordem)
    )
    materias: list[MateriaVerticalizada] = []
    for linha, topico in db.execute(consulta).all():
        if not materias or materias[-1].nome != topico.materia:
            materias.append(
                MateriaVerticalizada(
                    nome=topico.materia,
                    slug=slug_materia(topico.materia),
                    grupo=linha.grupo,
                    topicos=[],
                )
            )
        materias[-1].topicos.append(
            TopicoVerticalizado(id=topico.id, slug=topico.slug, texto_original=linha.texto_original)
        )
    return materias

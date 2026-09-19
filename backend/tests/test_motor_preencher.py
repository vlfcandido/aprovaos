# O que é: testes do relatório de cobertura (`motor/preencher.py`, fatia 5) — quais tópicos do
# edital têm dossiê e zero publicáveis (a única combinação que a Ruling 45 encomenda geração) e
# quais ficam como lacuna declarada ("falta dossiê"). Quando ler: ao mudar a regra de encomenda
# ou ao investigar por que um tópico não entrou (ou entrou) na lista de encomendas.
from uuid import UUID

from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Concurso, Documento, DossieTopico, Edital, Topico, TopicoEdital
from aprovaos.dados.repositorio_aula import salvar_aula
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.aula import ConteudoAula
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup
from aprovaos.motor.preencher import montar_encomendas, montar_relatorio_cobertura


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _topico(db: Session, slug: str) -> Topico:
    topico = Topico(materia="direito-administrativo", nome=slug, slug=slug)
    db.add(topico)
    db.flush()
    return topico


def _edital_com_topicos(db: Session, tenant_id: UUID, topicos: list[Topico]) -> Edital:
    documento = _documento(db, f"edital-{topicos[0].slug}")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PA", cargo="Analista", banca="cebraspe")
    edital = Edital(concurso=concurso, versao=1, documento=documento)
    db.add_all([concurso, edital])
    db.flush()
    for ordem, topico in enumerate(topicos, start=1):
        db.add(
            TopicoEdital(
                edital=edital, topico=topico, ordem=ordem, texto_original=f"{ordem}. {topico.nome}"
            )
        )
    db.flush()
    return edital


def _dossie(db: Session, topico: Topico) -> DossieTopico:
    dossie = DossieTopico(
        topico_id=topico.id,
        versao=1,
        gerado_em=agora_utc(),
        conteudo="conteúdo",
        fontes=[{"id": "F1", "tipo": "norma", "citacao_canonica": "Lei X art. 1", "trecho": "..."}],
        bibliografia=[],
        log_buscas=[],
    )
    db.add(dossie)
    db.flush()
    return dossie


def _questao_publicavel(db: Session, topico: Topico, documento_id: UUID) -> None:
    origem = Origem(
        banca="cebraspe",
        orgao="TJ-PA",
        cargo="Analista",
        ano=2025,
        numero_item=1,
        tipo_caderno=None,
        url_prova="https://cebraspe.example/prova.pdf",
        documento_id=str(documento_id),
    )
    questao = QuestaoCurada(
        banca="cebraspe",
        numero_item=1,
        comando="Julgue.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=f"Enunciado publicável de {topico.slug}.",
        gabarito_preliminar=None,
        gabarito="C",
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=topico.slug,
        topico_confianca="alta",
        topico_evidencia="teste",
        origem=origem,
        hash_dedup=hash_dedup(f"Enunciado publicável de {topico.slug}."),
    )
    salvar_questoes(db, [questao])


def _aula(db: Session, topico: Topico, dossie: DossieTopico) -> None:
    conteudo = ConteudoAula(
        texto_denso="texto denso da aula de teste, sem citação nenhuma.",
        texto_leigo="texto leigo.",
        citacoes=[],
    )
    salvar_aula(db, topico_id=topico.id, dossie=dossie, conteudo=conteudo)


def test_relatorio_cobre_todos_os_topicos_do_edital(db: Session) -> None:
    tenant_id = UUID(int=1)
    t1 = _topico(db, "dir-adm-01-com-dossie-sem-publicavel")
    t2 = _topico(db, "dir-adm-02-com-dossie-e-publicavel")
    t3 = _topico(db, "dir-adm-03-sem-dossie")
    edital = _edital_com_topicos(db, tenant_id, [t1, t2, t3])
    documento = edital.documento

    _dossie(db, t1)
    _dossie(db, t2)
    _questao_publicavel(db, t2, documento.id)

    relatorio = montar_relatorio_cobertura(db, edital.id)
    por_slug = {linha.topico_slug: linha for linha in relatorio.linhas}

    assert por_slug[t1.slug].tem_dossie is True
    assert por_slug[t1.slug].publicaveis == 0
    assert por_slug[t1.slug].tem_aula is False

    assert por_slug[t2.slug].tem_dossie is True
    assert por_slug[t2.slug].publicaveis == 1

    assert por_slug[t3.slug].tem_dossie is False
    assert por_slug[t3.slug].publicaveis == 0

    assert len(relatorio.linhas) == 3


def test_relatorio_marca_tem_aula(db: Session) -> None:
    tenant_id = UUID(int=2)
    topico = _topico(db, "dir-adm-04-com-aula")
    edital = _edital_com_topicos(db, tenant_id, [topico])
    dossie = _dossie(db, topico)
    _aula(db, topico, dossie)

    relatorio = montar_relatorio_cobertura(db, edital.id)
    assert relatorio.linhas[0].tem_aula is True


def test_encomenda_so_para_topico_com_dossie_e_zero_publicaveis(db: Session) -> None:
    tenant_id = UUID(int=3)
    t1 = _topico(db, "dir-adm-05-encomendavel")
    t2 = _topico(db, "dir-adm-06-ja-tem-publicavel")
    t3 = _topico(db, "dir-adm-07-sem-dossie")
    edital = _edital_com_topicos(db, tenant_id, [t1, t2, t3])
    documento = edital.documento

    _dossie(db, t1)
    _dossie(db, t2)
    _questao_publicavel(db, t2, documento.id)

    relatorio = montar_relatorio_cobertura(db, edital.id)
    encomendas = montar_encomendas(relatorio, n_por_topico=3)

    assert len(encomendas) == 1
    assert encomendas[0].topico_slug == t1.slug
    assert encomendas[0].n == 3


def test_topicos_sem_dossie_e_sem_publicaveis_viram_lacuna(db: Session) -> None:
    from aprovaos.motor.preencher import topicos_sem_dossie_para_encomenda

    tenant_id = UUID(int=4)
    t1 = _topico(db, "dir-adm-08-sem-dossie")
    edital = _edital_com_topicos(db, tenant_id, [t1])

    relatorio = montar_relatorio_cobertura(db, edital.id)
    lacunas = topicos_sem_dossie_para_encomenda(relatorio)
    assert lacunas == [t1.slug]

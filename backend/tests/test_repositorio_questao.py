# O que é: testes do passo 11 da V3 — repositório de questões (grava o que o curador produziu,
# conta por tópico, serve a próxima questão, registra resposta e reporte) —, do passo 12b
# (`atualizar_classificacao`, para reclassificar sem duplicar) e do passo 2 da V3b
# (`salvar_questoes` grava também `alternativa` para múltipla escolha). Quando ler: ao mexer em
# `dados/repositorio_questao.py` ou nas tabelas `questao`/`alternativa`/`evento_estudo`/
# `reporte_erro`.
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Alternativa,
    Concurso,
    Documento,
    Edital,
    EventoEstudo,
    Questao,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_questao import (
    atualizar_classificacao,
    contagem_por_topico,
    gravar_justificativa_alternativas,
    gravar_justificativa_certo_errado,
    proxima_questao,
    questoes_publicaveis_do_topico,
    registrar_reporte,
    registrar_resposta,
    salvar_questao_inedita,
    salvar_questoes,
    topicos_vistos,
)
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.questao import (
    AlternativaCurada,
    Origem,
    QuestaoCurada,
    RegraProva,
    hash_dedup,
)
from aprovaos.dominio.questao_inedita import AlternativaGerada, QuestaoGerada


def _usuario(db: Session, email: str) -> Usuario:
    return criar_conta(db, DadosCadastro(email=email, senha="12345678"))


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _topico(db: Session, slug: str) -> Topico:
    topico = Topico(materia="DIREITO CIVIL", nome="Prescrição", slug=slug)
    db.add(topico)
    db.flush()
    return topico


def _edital_com_topico(db: Session, tenant_id: UUID, topico: Topico) -> Edital:
    documento = _documento(db, f"edital-{uuid4().hex}")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PA", cargo="Analista", banca="cebraspe")
    edital = Edital(concurso=concurso, versao=1, documento=documento)
    db.add_all([concurso, edital])
    db.flush()
    db.add(TopicoEdital(edital=edital, topico=topico, ordem=1, texto_original="1. Prescrição."))
    db.flush()
    return edital


def _questao_curada(
    numero_item: int,
    enunciado: str,
    topico_slug: str | None,
    documento_id: UUID,
    *,
    publicavel: bool = True,
    gabarito: Literal["C", "E"] = "C",
) -> QuestaoCurada:
    origem = Origem(
        banca="cebraspe",
        orgao="TJ-PA",
        cargo="Analista",
        ano=2025,
        numero_item=numero_item,
        tipo_caderno=None,
        url_prova="https://cdn.cebraspe.org.br/prova.pdf",
        documento_id=str(documento_id),
    )
    return QuestaoCurada(
        banca="cebraspe",
        numero_item=numero_item,
        comando="Julgue o item a seguir.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=enunciado,
        gabarito_preliminar=None,
        gabarito=gabarito,
        gabarito_status="definitivo",
        publicavel=publicavel,
        motivo_nao_publicavel=None if publicavel else "tópico não identificado",
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=topico_slug,
        topico_confianca="alta" if topico_slug else "baixa",
        topico_evidencia="menciona prescrição",
        origem=origem,
        hash_dedup=hash_dedup(enunciado),
    )


def _questao_curada_multipla_escolha(
    numero_item: int,
    enunciado: str,
    topico_slug: str | None,
    documento_id: UUID,
    *,
    gabarito: Literal["A", "B", "C", "D", "E"] = "B",
) -> QuestaoCurada:
    """Mesmo espírito de `_questao_curada`, para `tipo_item="multipla_escolha"` (passo 2 da V3b)."""
    origem = Origem(
        banca="cebraspe",
        orgao="TJ-CE",
        cargo="Técnico Judiciário",
        ano=2023,
        numero_item=numero_item,
        tipo_caderno=None,
        url_prova="https://cdn.cebraspe.org.br/prova.pdf",
        documento_id=str(documento_id),
    )
    alternativas = [
        AlternativaCurada(
            letra=letra, texto=f"texto da alternativa {letra}", correta=letra == gabarito
        )
        for letra in ("A", "B", "C", "D", "E")
    ]
    return QuestaoCurada(
        banca="cebraspe",
        tipo_item="multipla_escolha",
        numero_item=numero_item,
        comando=None,
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=enunciado,
        alternativas=alternativas,
        gabarito_preliminar=None,
        gabarito=gabarito,
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=False, fonte="convenção Cebraspe A–E"),
        topico_slug=topico_slug,
        topico_confianca="alta" if topico_slug else "baixa",
        topico_evidencia="menciona prescrição",
        origem=origem,
        hash_dedup=hash_dedup(enunciado),
    )


def test_salvar_questoes_dedup(db: Session) -> None:
    documento = _documento(db, "d1")
    topico = _topico(db, "dir-civ-01-prescricao")
    questoes = [
        _questao_curada(1, "Enunciado um.", topico.slug, documento.id),
        _questao_curada(2, "Enunciado dois.", topico.slug, documento.id),
    ]

    novas, repetidas = salvar_questoes(db, questoes)
    db.commit()
    assert (novas, repetidas) == (2, 0)
    assert db.scalar(select(func.count()).select_from(Questao)) == 2

    novas2, repetidas2 = salvar_questoes(db, questoes)
    db.commit()
    assert (novas2, repetidas2) == (0, 2)
    assert db.scalar(select(func.count()).select_from(Questao)) == 2


def test_salvar_questoes_dedup_dentro_do_mesmo_lote(db: Session) -> None:
    """A dedup não pode depender da `UNIQUE` do banco: duas entradas de mesmo `hash_dedup` na
    **mesma** chamada (o cenário real de um caderno mal segmentado, ou de recoleta que reenvia a
    mesma prova) já têm de resultar numa única linha, não em duas seguidas de um `IntegrityError`.
    """
    documento = _documento(db, "d1b")
    topico = _topico(db, "dir-civ-01-prescricao")
    repetida = _questao_curada(1, "Enunciado repetido.", topico.slug, documento.id)
    repetida_de_novo = _questao_curada(2, "Enunciado repetido.", topico.slug, documento.id)
    assert repetida.hash_dedup == repetida_de_novo.hash_dedup

    novas, repetidas = salvar_questoes(db, [repetida, repetida_de_novo])
    db.commit()

    assert (novas, repetidas) == (1, 1)
    assert db.scalar(select(func.count()).select_from(Questao)) == 1


def test_salvar_questoes_grava_alternativas(db: Session) -> None:
    """Múltipla escolha: `salvar_questoes` grava as cinco `alternativa` junto com a `questao`."""
    documento = _documento(db, "d-me-1")
    topico = _topico(db, "dir-civ-01-prescricao")
    questao = _questao_curada_multipla_escolha(
        21, "Enunciado de múltipla escolha.", topico.slug, documento.id, gabarito="D"
    )

    novas, repetidas = salvar_questoes(db, [questao])
    db.commit()

    assert (novas, repetidas) == (1, 0)
    questao_salva = db.scalars(select(Questao)).one()
    assert questao_salva.tipo_item == "multipla_escolha"
    assert questao_salva.gabarito == "D"

    alternativas = list(
        db.scalars(
            select(Alternativa)
            .where(Alternativa.questao_id == questao_salva.id)
            .order_by(Alternativa.letra)
        ).all()
    )
    assert [a.letra for a in alternativas] == ["A", "B", "C", "D", "E"]
    assert all(a.justificativa is None for a in alternativas)
    corretas = [a for a in alternativas if a.correta]
    assert len(corretas) == 1
    assert corretas[0].letra == "D"


def test_salvar_questoes_nao_duplica_alternativas_de_questao_ja_existente(db: Session) -> None:
    """Rodar a mesma lista duas vezes não duplica `alternativa` (mesmo espírito da dedup de
    `questao` — a segunda chamada nem tenta gravar de novo).
    """
    documento = _documento(db, "d-me-2")
    topico = _topico(db, "dir-civ-01-prescricao")
    questao = _questao_curada_multipla_escolha(
        22, "Outro enunciado de múltipla escolha.", topico.slug, documento.id
    )

    salvar_questoes(db, [questao])
    db.commit()
    novas2, repetidas2 = salvar_questoes(db, [questao])
    db.commit()

    assert (novas2, repetidas2) == (0, 1)
    assert db.scalar(select(func.count()).select_from(Questao)) == 1
    assert db.scalar(select(func.count()).select_from(Alternativa)) == 5


def test_contagem_por_topico(db: Session) -> None:
    tenant_id = _usuario(db, "a@exemplo.com").tenant_id
    topico_a = _topico(db, "dir-civ-01-prescricao")
    topico_b = _topico(db, "dir-civ-02-decadencia")
    edital = _edital_com_topico(db, tenant_id, topico_a)
    db.add(TopicoEdital(edital=edital, topico=topico_b, ordem=2, texto_original="2. Decadência."))
    db.flush()
    documento = _documento(db, "d2")
    questoes = [
        _questao_curada(1, "Um.", topico_a.slug, documento.id, publicavel=True),
        _questao_curada(2, "Dois.", topico_a.slug, documento.id, publicavel=True),
        _questao_curada(3, "Três.", topico_a.slug, documento.id, publicavel=False),
        _questao_curada(4, "Quatro.", topico_b.slug, documento.id, publicavel=True),
        _questao_curada(5, "Cinco.", None, documento.id, publicavel=False),
    ]
    salvar_questoes(db, questoes)
    db.commit()

    # Dois tópicos com contagens diferentes: exercita o agrupamento por chave, não só o filtro
    # de `publicavel`.
    assert contagem_por_topico(db, edital.id) == {topico_a.id: 2, topico_b.id: 1}


def test_proxima_questao_ignora_respondidas_e_reportadas(db: Session) -> None:
    usuario = _usuario(db, "a@exemplo.com")
    topico = _topico(db, "dir-civ-01-prescricao")
    documento = _documento(db, "d3")
    questoes = [
        _questao_curada(1, "Um.", topico.slug, documento.id),
        _questao_curada(2, "Dois.", topico.slug, documento.id),
        _questao_curada(3, "Três.", topico.slug, documento.id),
    ]
    salvar_questoes(db, questoes)
    db.commit()
    salvas = list(db.scalars(select(Questao).order_by(Questao.criado_em)).all())
    assert len(salvas) == 3
    # Fixa `criado_em` em instantes bem separados: garante ordem determinística mesmo se o
    # SQLite gravar os três com o mesmo timestamp de wall-clock.
    base = agora_utc()
    for indice, questao in enumerate(salvas):
        questao.criado_em = base + timedelta(seconds=indice)
    db.commit()

    registrar_resposta(db, usuario, salvas[0], resposta="C", confianca="certeza", tempo_ms=1000)
    registrar_reporte(db, usuario, salvas[1], motivo="gabarito parece errado")
    db.commit()

    proxima = proxima_questao(db, usuario.id, topico.id)
    assert proxima is not None
    assert proxima.id == salvas[2].id

    registrar_resposta(db, usuario, salvas[2], resposta="C", confianca="certeza", tempo_ms=1000)
    db.commit()
    assert proxima_questao(db, usuario.id, topico.id) is None


def test_proxima_questao_ignora_despublicada_pelo_calibrador(db: Session) -> None:
    """P-34 (`docs/PENDENCIAS.md`, fecha nesta fatia): uma questão com `despublicada_em`
    preenchido some de `proxima_questao` para qualquer usuário, mesmo continuando `publicavel`.
    """
    usuario = _usuario(db, "a@exemplo.com")
    topico = _topico(db, "dir-civ-01-prescricao")
    documento = _documento(db, "d-p34-1")
    salvar_questoes(db, [_questao_curada(1, "Única do tópico.", topico.slug, documento.id)])
    db.commit()
    questao = db.scalars(select(Questao)).one()
    assert proxima_questao(db, usuario.id, topico.id) is not None

    questao.despublicada_em = agora_utc()
    questao.publicavel = True  # o gate estrutural do curador não muda — só a coluna do calibrador
    db.commit()

    assert proxima_questao(db, usuario.id, topico.id) is None


def test_contagem_por_topico_ignora_despublicada_pelo_calibrador(db: Session) -> None:
    """P-34: `contagem_por_topico` não conta a questão despublicada, mesmo `publicavel=True`."""
    tenant_id = _usuario(db, "b@exemplo.com").tenant_id
    topico = _topico(db, "dir-civ-01-prescricao")
    edital = _edital_com_topico(db, tenant_id, topico)
    documento = _documento(db, "d-p34-2")
    salvar_questoes(
        db,
        [
            _questao_curada(1, "Fica.", topico.slug, documento.id),
            _questao_curada(2, "Some.", topico.slug, documento.id),
        ],
    )
    db.commit()
    assert contagem_por_topico(db, edital.id) == {topico.id: 2}

    despublicada = db.scalars(select(Questao).where(Questao.enunciado == "Some.")).one()
    despublicada.despublicada_em = agora_utc()
    db.commit()

    assert contagem_por_topico(db, edital.id) == {topico.id: 1}


def test_questoes_publicaveis_do_topico_ignora_despublicada_pelo_calibrador(db: Session) -> None:
    """P-34: `questoes_publicaveis_do_topico` (usada por `motor.justificar`) também respeita a
    despublicação do calibrador.
    """
    topico = _topico(db, "dir-adm-06-improbidade-administrativa")
    documento = _documento(db, "d-p34-3")
    salvar_questoes(db, [_questao_curada(1, "Vai sumir.", topico.slug, documento.id)])
    db.commit()
    questao = db.scalars(select(Questao)).one()
    assert questoes_publicaveis_do_topico(db, topico.slug) == [questao]

    questao.despublicada_em = agora_utc()
    db.commit()

    assert questoes_publicaveis_do_topico(db, topico.slug) == []


def test_registrar_resposta_grava_evento(db: Session) -> None:
    usuario = _usuario(db, "a@exemplo.com")
    topico = _topico(db, "dir-civ-01-prescricao")
    documento = _documento(db, "d4")
    salvar_questoes(db, [_questao_curada(1, "Um.", topico.slug, documento.id, gabarito="C")])
    db.commit()
    questao = db.scalars(select(Questao)).one()
    antes = (questao.publicavel, questao.gabarito, questao.gabarito_status)

    evento = registrar_resposta(
        db, usuario, questao, resposta="C", confianca="duvida", tempo_ms=5000
    )
    db.commit()

    assert evento.tipo == "resposta"
    assert evento.usuario_id == usuario.id
    assert evento.questao_id == questao.id
    assert evento.acertou is True
    assert evento.resposta == "C"
    assert evento.tempo_ms == 5000
    assert evento.confianca_declarada == "duvida"

    db.refresh(questao)
    assert (questao.publicavel, questao.gabarito, questao.gabarito_status) == antes


def test_registrar_resposta_acertou_false(db: Session) -> None:
    """A comparação `resposta == questao.gabarito` é a única regra de negócio do módulo — a
    polaridade oposta (resposta errada) precisa ser exercida, não só o caso de acerto.
    """
    usuario = _usuario(db, "a@exemplo.com")
    topico = _topico(db, "dir-civ-01-prescricao")
    documento = _documento(db, "d4b")
    salvar_questoes(db, [_questao_curada(1, "Um.", topico.slug, documento.id, gabarito="C")])
    db.commit()
    questao = db.scalars(select(Questao)).one()

    evento = registrar_resposta(
        db, usuario, questao, resposta="E", confianca="certeza", tempo_ms=2000
    )
    db.commit()

    assert evento.acertou is False
    assert evento.resposta == "E"


def test_registrar_reporte(db: Session) -> None:
    usuario = _usuario(db, "a@exemplo.com")
    outro = _usuario(db, "b@exemplo.com")
    topico = _topico(db, "dir-civ-01-prescricao")
    documento = _documento(db, "d5")
    salvar_questoes(db, [_questao_curada(1, "Um.", topico.slug, documento.id)])
    db.commit()
    questao = db.scalars(select(Questao)).one()

    reporte = registrar_reporte(db, usuario, questao, motivo="gabarito parece errado")
    db.commit()

    assert reporte.status == "aberto"
    assert reporte.conteudo_tipo == "questao"
    assert reporte.conteudo_id == questao.id
    assert reporte.usuario_id == usuario.id

    eventos = list(db.scalars(select(EventoEstudo).where(EventoEstudo.tipo == "reporte")).all())
    assert len(eventos) == 1
    assert eventos[0].questao_id == questao.id
    assert eventos[0].usuario_id == usuario.id

    # Premissa H: some só para quem reportou; a questão continua publicada para os demais.
    assert proxima_questao(db, usuario.id, topico.id) is None
    assert proxima_questao(db, outro.id, topico.id) is not None


def test_topicos_vistos(db: Session) -> None:
    usuario = _usuario(db, "a@exemplo.com")
    topico_a = _topico(db, "dir-civ-01-prescricao")
    topico_b = _topico(db, "dir-civ-02-decadencia")
    edital = _edital_com_topico(db, usuario.tenant_id, topico_a)
    db.add(TopicoEdital(edital=edital, topico=topico_b, ordem=2, texto_original="2. Decadência."))
    db.flush()
    documento = _documento(db, "d6")
    salvar_questoes(
        db,
        [
            _questao_curada(1, "Um.", topico_a.slug, documento.id),
            _questao_curada(2, "Dois.", topico_b.slug, documento.id),
        ],
    )
    db.commit()
    questao_a, questao_b = db.scalars(select(Questao).order_by(Questao.criado_em)).all()

    assert topicos_vistos(db, usuario.id, edital.id) == set()

    registrar_resposta(db, usuario, questao_a, resposta="C", confianca="certeza", tempo_ms=100)
    db.commit()
    assert topicos_vistos(db, usuario.id, edital.id) == {topico_a.id}

    registrar_resposta(db, usuario, questao_b, resposta="E", confianca="duvida", tempo_ms=200)
    db.commit()
    assert topicos_vistos(db, usuario.id, edital.id) == {topico_a.id, topico_b.id}


def test_atualizar_classificacao_muda_topico_sem_tocar_texto_gabarito_ou_origem(
    db: Session,
) -> None:
    """Reclassificar (passo 12b): só `topico_id`/`topico_confianca`/`topico_evidencia`/
    `publicavel`/`motivo_nao_publicavel` mudam — o resto da linha gravada na curadoria original
    é imutável (texto, gabarito, origem).
    """
    documento = _documento(db, "d7")
    topico_novo = _topico(db, "dir-civ-01-prescricao")
    original = _questao_curada(1, "Enunciado original.", None, documento.id, publicavel=False)
    salvar_questoes(db, [original])
    db.commit()
    salva = db.scalars(select(Questao)).one()
    assert salva.topico_id is None
    assert salva.publicavel is False
    assert salva.motivo_nao_publicavel == "tópico não identificado"
    enunciado_antes, comando_antes, origem_antes, gabarito_antes = (
        salva.enunciado,
        salva.comando,
        salva.origem,
        salva.gabarito,
    )

    reclassificada = _questao_curada(
        1, "Enunciado original.", topico_novo.slug, documento.id, publicavel=True
    )
    atualizadas, ignoradas, preservadas = atualizar_classificacao(db, [reclassificada])
    db.commit()

    assert (atualizadas, ignoradas, preservadas) == (1, 0, 0)
    db.refresh(salva)
    assert salva.topico_id == topico_novo.id
    assert salva.topico_confianca == "alta"
    assert salva.topico_evidencia == reclassificada.topico_evidencia
    assert salva.publicavel is True
    assert salva.motivo_nao_publicavel is None
    # nada além de topico/publicavel mudou:
    assert salva.enunciado == enunciado_antes
    assert salva.comando == comando_antes
    assert salva.origem == origem_antes
    assert salva.gabarito == gabarito_antes


def test_atualizar_classificacao_ignora_hash_inexistente(db: Session) -> None:
    """Uma `QuestaoCurada` cujo `hash_dedup` não está na base é ignorada, nunca criada."""
    documento = _documento(db, "d8")
    inexistente = _questao_curada(99, "Este enunciado nunca foi gravado.", None, documento.id)

    atualizadas, ignoradas, preservadas = atualizar_classificacao(db, [inexistente])
    db.commit()

    assert (atualizadas, ignoradas, preservadas) == (0, 1, 0)
    assert db.scalar(select(func.count()).select_from(Questao)) == 0


def test_questoes_publicaveis_do_topico_ignora_nao_publicaveis_e_outros_topicos(
    db: Session,
) -> None:
    """Só as publicáveis do tópico pedido — nem as de outro tópico, nem as não publicáveis."""
    documento = _documento(db, "d-just-1")
    topico = _topico(db, "dir-adm-06-improbidade-administrativa")
    outro_topico = _topico(db, "dir-civ-02-decadencia")
    salvar_questoes(
        db,
        [
            _questao_curada(1, "Publicável do tópico certo.", topico.slug, documento.id),
            _questao_curada(2, "Não publicável.", topico.slug, documento.id, publicavel=False),
            _questao_curada(3, "De outro tópico.", outro_topico.slug, documento.id),
        ],
    )
    db.commit()

    encontradas = questoes_publicaveis_do_topico(db, topico.slug)

    assert [q.enunciado for q in encontradas] == ["Publicável do tópico certo."]


def test_gravar_justificativa_certo_errado(db: Session) -> None:
    documento = _documento(db, "d-just-2")
    topico = _topico(db, "dir-adm-06-improbidade-administrativa")
    salvar_questoes(db, [_questao_curada(1, "Enunciado C/E.", topico.slug, documento.id)])
    db.commit()
    questao = db.scalars(select(Questao)).one()

    gravar_justificativa_certo_errado(
        db,
        questao,
        certo="Seria certo porque [...] [Lei X art. 1º]",
        errado="Está errado [...] [Lei X art. 1º]",
    )
    db.commit()
    db.refresh(questao)

    assert questao.justificativa_certo == "Seria certo porque [...] [Lei X art. 1º]"
    assert questao.justificativa_errado == "Está errado [...] [Lei X art. 1º]"


def test_gravar_justificativa_alternativas(db: Session) -> None:
    documento = _documento(db, "d-just-3")
    topico = _topico(db, "dir-adm-06-improbidade-administrativa")
    salvar_questoes(
        db,
        [
            _questao_curada_multipla_escolha(
                1, "Enunciado A-E.", topico.slug, documento.id, gabarito="B"
            )
        ],
    )
    db.commit()
    questao = db.scalars(select(Questao)).one()

    gravar_justificativa_alternativas(db, questao, {"A": "não é [...]", "B": "é a correta [...]"})
    db.commit()

    alternativas = {
        a.letra: a.justificativa
        for a in db.scalars(select(Alternativa).where(Alternativa.questao_id == questao.id)).all()
    }
    assert alternativas["A"] == "não é [...]"
    assert alternativas["B"] == "é a correta [...]"
    assert alternativas["C"] is None


def _item_gerado(
    *,
    tipo_item: str = "certo_errado",
    gabarito: str = "E",
    topico_slug: str,
    alternativas: list[AlternativaGerada] | None = None,
) -> QuestaoGerada:
    return QuestaoGerada(
        tipo_item=tipo_item,
        banca_alvo="cebraspe",
        comando="Julgue o item.",
        enunciado="Os atos de improbidade administrativa serão perdoados na forma desta lei.",
        alternativas=alternativas,
        gabarito=gabarito,
        fontes=["F1"],
        trecho_que_decide="serão punidos na forma desta lei",
        justificativa_certo="Se dissesse 'punidos', estaria certo.",
        justificativa_errado="A lei diz 'punidos', não 'perdoados'.",
        mecanismo="troca_de_verbo",
        original_de_referencia="cebraspe 2024 tce-xx item 1",
        topico_slug=topico_slug,
        aderencia_medida=False,
    )


class TestSalvarQuestaoInedita:
    def test_grava_inedita_aprovada(self, db: Session) -> None:
        topico = _topico(db, "dir-adm-06-improbidade-inedita")
        item = _item_gerado(topico_slug=topico.slug)
        regra_prova = RegraProva(anula_por_erro=False, fonte="inédita — sem regra do DNA")

        questao = salvar_questao_inedita(
            db,
            topico_id=topico.id,
            item=item,
            publicavel=True,
            motivo_nao_publicavel=None,
            validador_versao="v1-lexico",
            regra_prova=regra_prova,
        )
        db.commit()

        gravada = db.get(Questao, questao.id)
        assert gravada is not None
        assert gravada.inedita is True
        assert gravada.origem is None
        assert gravada.publicavel is True
        assert gravada.motivo_nao_publicavel is None
        assert gravada.justificativa_certo == item.justificativa_certo
        assert gravada.justificativa_errado == item.justificativa_errado
        assert gravada.validador_versao == "v1-lexico"
        assert gravada.validada_em is not None

    def test_grava_inedita_reprovada_com_motivo(self, db: Session) -> None:
        topico = _topico(db, "dir-adm-07-improbidade-reprovada")
        item = _item_gerado(topico_slug=topico.slug)
        regra_prova = RegraProva(anula_por_erro=False, fonte="inédita — sem regra do DNA")

        questao = salvar_questao_inedita(
            db,
            topico_id=topico.id,
            item=item,
            publicavel=False,
            motivo_nao_publicavel="gabarito: resolução independente diverge",
            validador_versao="v1-lexico",
            regra_prova=regra_prova,
        )
        db.commit()

        gravada = db.get(Questao, questao.id)
        assert gravada is not None
        assert gravada.publicavel is False
        assert gravada.motivo_nao_publicavel == "gabarito: resolução independente diverge"

    def test_grava_alternativas_de_multipla_escolha(self, db: Session) -> None:
        topico = _topico(db, "dir-adm-08-multipla-escolha-inedita")
        alternativas = [AlternativaGerada(letra=letra, texto=f"Texto {letra}") for letra in "ABCDE"]
        item = _item_gerado(
            tipo_item="multipla_escolha",
            gabarito="B",
            topico_slug=topico.slug,
            alternativas=alternativas,
        )
        regra_prova = RegraProva(anula_por_erro=False, fonte="inédita — sem regra do DNA")

        questao = salvar_questao_inedita(
            db,
            topico_id=topico.id,
            item=item,
            publicavel=True,
            motivo_nao_publicavel=None,
            validador_versao="v1-lexico",
            regra_prova=regra_prova,
        )
        db.commit()

        gravadas = list(db.scalars(select(Alternativa).where(Alternativa.questao_id == questao.id)))
        assert len(gravadas) == 5
        corretas = [a for a in gravadas if a.correta]
        assert len(corretas) == 1
        assert corretas[0].letra == "B"


# P-76: reclassificar nunca pode rebaixar. Em 23/09/2026 uma rodada de `curar --reclassificar`
# caiu para regras (a chamada de IA estourou) e a saída sem tópico foi gravada por cima da
# classificação que a IA já tinha feito: 138 publicáveis viraram 39. Falha de classificação
# preserva o que já estava lá — a rede de segurança não pode virar descarte.
def test_atualizar_classificacao_preserva_topico_quando_a_nova_vem_sem_topico(
    db: Session,
) -> None:
    """Nova classificação sem tópico **não** apaga a que já existe; conta como preservada."""
    documento = _documento(db, "d9")
    topico = _topico(db, "dir-adm-06-improbidade-administrativa")
    salvar_questoes(
        db,
        [_questao_curada(1, "Enunciado classificado.", topico.slug, documento.id, publicavel=True)],
    )
    db.commit()
    salva = db.scalars(select(Questao)).one()
    assert salva.topico_id == topico.id
    evidencia_antes, confianca_antes = salva.topico_evidencia, salva.topico_confianca

    sem_topico = _questao_curada(1, "Enunciado classificado.", None, documento.id, publicavel=False)
    atualizadas, ignoradas, preservadas = atualizar_classificacao(db, [sem_topico])
    db.commit()

    assert (atualizadas, ignoradas, preservadas) == (0, 0, 1)
    db.refresh(salva)
    assert salva.topico_id == topico.id
    assert salva.publicavel is True
    assert salva.motivo_nao_publicavel is None
    assert salva.topico_evidencia == evidencia_antes
    assert salva.topico_confianca == confianca_antes


def test_atualizar_classificacao_troca_um_topico_por_outro(db: Session) -> None:
    """Reclassificar de um tópico para outro continua valendo — o que não vale é rebaixar."""
    documento = _documento(db, "d10")
    antigo = _topico(db, "dir-con-02-direitos-garantias")
    novo = _topico(db, "dir-pro-civ-03-atos-processuais")
    salvar_questoes(
        db,
        [_questao_curada(1, "Enunciado a remanejar.", antigo.slug, documento.id, publicavel=True)],
    )
    db.commit()
    salva = db.scalars(select(Questao)).one()

    atualizadas, ignoradas, preservadas = atualizar_classificacao(
        db, [_questao_curada(1, "Enunciado a remanejar.", novo.slug, documento.id, publicavel=True)]
    )
    db.commit()

    assert (atualizadas, ignoradas, preservadas) == (1, 0, 0)
    db.refresh(salva)
    assert salva.topico_id == novo.id


def test_atualizar_classificacao_sem_topico_dos_dois_lados_nao_conta_preservada(
    db: Session,
) -> None:
    """Sem tópico antes e sem tópico depois não é rebaixamento: é atualização normal."""
    documento = _documento(db, "d11")
    salvar_questoes(
        db, [_questao_curada(1, "Enunciado sem tópico.", None, documento.id, publicavel=False)]
    )
    db.commit()

    atualizadas, ignoradas, preservadas = atualizar_classificacao(
        db, [_questao_curada(1, "Enunciado sem tópico.", None, documento.id, publicavel=False)]
    )
    db.commit()

    assert (atualizadas, ignoradas, preservadas) == (1, 0, 0)

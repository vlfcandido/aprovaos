# O que é: testes de `dados/repositorio_painel.py` (fatia 10, §8) — as consultas que alimentam
# curva, padrões e previsão, com a trava da P-34 (questão despublicada nunca conta) e o fuso de
# Brasília (Ruling 37). Quando ler: ao mexer no que os números do painel realmente contam.
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
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
from aprovaos.dados.repositorio_painel import (
    alerta_atual,
    curva_atual,
    nomes_por_topico,
    pesos_por_materia,
    respostas_classificadas,
    respostas_historicas,
    total_topicos,
)
from aprovaos.dados.repositorio_perfil import salvar_perfil
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup
from aprovaos.dominio.rotina import DIAS_SEMANA, DadosRotina


def _cenario(
    db: Session, email: str, *, quantidade_topicos: int = 1, data_alvo: date | None = None
) -> tuple[Usuario, UUID, list[Topico]]:
    """Um usuário com concurso principal, edital sem DNA e `quantidade_topicos` tópicos."""
    usuario = criar_conta(db, DadosCadastro(email=email, senha="12345678"))
    concurso = Concurso(
        tenant_id=usuario.tenant_id, orgao="TJ-PR", cargo="Técnico", banca="cebraspe"
    )
    documento_edital = Documento(
        tipo="edital",
        hash=f"edital-{email}".ljust(64, "0")[:64],
        caminho="edital.pdf",
        baixado_em=agora_utc(),
        metadados={},
    )
    db.add_all([concurso, documento_edital])
    db.flush()
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add(edital)
    db.flush()

    topicos: list[Topico] = []
    for indice in range(quantidade_topicos):
        topico = Topico(
            materia="Direito Administrativo",
            nome=f"Tópico {indice}",
            slug=f"topico-{email}-{indice}",
        )
        db.add(topico)
        db.flush()
        db.add(
            TopicoEdital(
                edital=edital,
                topico=topico,
                ordem=indice + 1,
                peso_edital=None,
                texto_original=f"{indice + 1}. Tópico {indice}",
                grupo=None,
            )
        )
        topicos.append(topico)

    horas = dict.fromkeys(DIAS_SEMANA, 1.0)
    salvar_perfil(
        db,
        usuario,
        DadosRotina(
            horas_por_dia_semana=horas,
            horario_preferido="manha",
            energia_tipica="media",
            data_alvo=data_alvo,
            concurso_principal_id=concurso.id,
        ),
    )
    db.commit()
    return usuario, edital.id, topicos


def _questao_curada(topico: Topico, documento_id: UUID, numero: int) -> QuestaoCurada:
    origem = Origem(
        banca="cebraspe",
        orgao="TJ-PR",
        cargo="Técnico",
        ano=2025,
        numero_item=numero,
        tipo_caderno=None,
        url_prova="https://cdn.cebraspe.org.br/prova.pdf",
        documento_id=str(documento_id),
    )
    enunciado = f"Enunciado painel {numero} sobre {topico.nome}."
    return QuestaoCurada(
        banca="cebraspe",
        numero_item=numero,
        comando="Julgue o item.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=enunciado,
        gabarito_preliminar=None,
        gabarito="C",
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=topico.slug,
        topico_confianca="alta",
        topico_evidencia="evidência",
        origem=origem,
        hash_dedup=hash_dedup(enunciado),
    )


def _gravar_questao(db: Session, topico: Topico, email: str, numero: int) -> Questao:
    """Grava e devolve uma `Questao` publicável para este tópico (uma `Documento` de prova por
    número, para o hash de documento não colidir entre chamadas do mesmo teste)."""
    documento_prova = Documento(
        tipo="prova",
        hash=f"prova-{email}-{numero}".ljust(64, "0")[:64],
        caminho=f"prova-{numero}.pdf",
        baixado_em=agora_utc(),
        metadados={},
    )
    db.add(documento_prova)
    db.flush()
    curada = _questao_curada(topico, documento_prova.id, numero)
    salvar_questoes(db, [curada])
    db.commit()
    questao = db.query(Questao).filter_by(hash_dedup=curada.hash_dedup).one()
    return questao


def _resposta(
    db: Session, usuario: Usuario, questao: Questao, ocorrido_em: datetime, *, acertou: bool = True
) -> None:
    db.add(
        EventoEstudo(
            usuario_id=usuario.id,
            ocorrido_em=ocorrido_em,
            tipo="resposta",
            questao_id=questao.id,
            acertou=acertou,
            resposta=questao.gabarito if acertou else "E",
            tempo_ms=1000,
            confianca_declarada="certeza",
        )
    )
    db.flush()


# ---------------------------------------------------------------------------
# respostas_historicas — P-34
# ---------------------------------------------------------------------------


def test_respostas_historicas_ignora_questao_despublicada(db: Session) -> None:
    usuario, edital_id, (topico,) = _cenario(db, "hist@exemplo.com")
    publicada = _gravar_questao(db, topico, "hist", 1)
    despublicada = _gravar_questao(db, topico, "hist", 2)
    despublicada.despublicada_em = agora_utc()
    db.commit()

    agora = agora_utc()
    _resposta(db, usuario, publicada, agora)
    _resposta(db, usuario, despublicada, agora)
    db.commit()

    respostas = respostas_historicas(db, usuario.id, edital_id)

    assert len(respostas) == 1
    assert respostas[0].topico_id == topico.id


def test_respostas_historicas_ordem_por_ocorrido_em(db: Session) -> None:
    usuario, edital_id, (topico,) = _cenario(db, "ordem@exemplo.com")
    questao = _gravar_questao(db, topico, "ordem", 1)
    mais_novo = agora_utc()
    mais_velho = mais_novo - timedelta(days=1)
    _resposta(db, usuario, questao, mais_novo)
    db.commit()

    outra_questao = _gravar_questao(db, topico, "ordem", 2)
    _resposta(db, usuario, outra_questao, mais_velho)
    db.commit()

    respostas = respostas_historicas(db, usuario.id, edital_id)

    assert [r.ocorrido_em for r in respostas] == [mais_velho, mais_novo]


# ---------------------------------------------------------------------------
# respostas_classificadas — hora local (Ruling 37) e dimensões
# ---------------------------------------------------------------------------


def test_respostas_classificadas_converte_hora_para_brasilia(db: Session) -> None:
    usuario, edital_id, (topico,) = _cenario(db, "fuso@exemplo.com")
    questao = _gravar_questao(db, topico, "fuso", 1)
    # 02h00 UTC de um dia == 23h00 do dia anterior em America/Sao_Paulo (UTC-3).
    ocorrido_em = datetime(2026, 1, 10, 2, 0, tzinfo=UTC)
    _resposta(db, usuario, questao, ocorrido_em)
    db.commit()

    classificadas = respostas_classificadas(db, usuario.id, edital_id)

    assert len(classificadas) == 1
    resposta = classificadas[0]
    assert resposta.materia == "Direito Administrativo"
    assert resposta.topico_nome == topico.nome
    assert resposta.banca == "cebraspe"
    assert resposta.hora_local == 23
    assert resposta.energia is None


def test_respostas_classificadas_ignora_questao_despublicada(db: Session) -> None:
    usuario, edital_id, (topico,) = _cenario(db, "fuso2@exemplo.com")
    despublicada = _gravar_questao(db, topico, "fuso2", 1)
    despublicada.despublicada_em = agora_utc()
    db.commit()
    _resposta(db, usuario, despublicada, agora_utc())
    db.commit()

    assert respostas_classificadas(db, usuario.id, edital_id) == []


# ---------------------------------------------------------------------------
# pesos_por_materia — P-39
# ---------------------------------------------------------------------------


def test_pesos_por_materia_sem_dna_cai_no_uniforme(db: Session) -> None:
    _usuario, edital_id, _topicos = _cenario(db, "pesos@exemplo.com")

    pesos = pesos_por_materia(db, edital_id)

    assert pesos.pesos == {"Direito Administrativo": 1}
    assert pesos.lacuna is not None


def test_pesos_por_materia_agrega_grafias_diferentes_da_mesma_materia(db: Session) -> None:
    """Defeito reproduzido no navegador (fatia 14): dado velho do bug de fusão (corrigido no
    parser em `73f69a0`, não retroagido ao banco) grava a mesma matéria em duas caixas
    (`"LÍNGUA PORTUGUESA"` e `"Língua Portuguesa"`) — sem normalizar na leitura, ela vira duas
    matérias na tela. `pesos_por_materia` tem que agregar as duas sob o mesmo rótulo."""
    usuario = criar_conta(db, DadosCadastro(email="grafias@exemplo.com", senha="12345678"))
    concurso = Concurso(
        tenant_id=usuario.tenant_id, orgao="TJ-PR", cargo="Técnico", banca="cebraspe"
    )
    documento_edital = Documento(
        tipo="edital",
        hash="edital-grafias".ljust(64, "0")[:64],
        caminho="edital.pdf",
        baixado_em=agora_utc(),
        metadados={},
    )
    db.add_all([concurso, documento_edital])
    db.flush()
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add(edital)
    db.flush()

    topico_maiusculo = Topico(materia="LÍNGUA PORTUGUESA", nome="Crase", slug="grafias-a")
    topico_misto = Topico(materia="Língua Portuguesa", nome="Concordância", slug="grafias-b")
    db.add_all([topico_maiusculo, topico_misto])
    db.flush()
    db.add_all(
        [
            TopicoEdital(edital=edital, topico=topico_maiusculo, ordem=1, texto_original="1."),
            TopicoEdital(edital=edital, topico=topico_misto, ordem=2, texto_original="2."),
        ]
    )
    db.commit()

    pesos = pesos_por_materia(db, edital.id)

    assert pesos.pesos == {"Língua Portuguesa": 1}


def test_pesos_por_materia_sem_topico_nenhum(db: Session) -> None:
    _usuario, edital_id, _topicos = _cenario(db, "pesosvazio@exemplo.com", quantidade_topicos=0)

    pesos = pesos_por_materia(db, edital_id)

    assert pesos.pesos == {}
    assert pesos.lacuna is None


# ---------------------------------------------------------------------------
# total_topicos / nomes_por_topico
# ---------------------------------------------------------------------------


def test_total_topicos_e_nomes_por_topico(db: Session) -> None:
    _usuario, edital_id, topicos = _cenario(db, "nomes@exemplo.com", quantidade_topicos=2)

    assert total_topicos(db, edital_id) == 2
    nomes = nomes_por_topico(db, edital_id)
    assert nomes == {t.id: t.nome for t in topicos}


# ---------------------------------------------------------------------------
# curva_atual / alerta_atual
# ---------------------------------------------------------------------------


def test_curva_atual_sem_data_alvo_e_lacuna(db: Session) -> None:
    usuario, edital_id, _topicos = _cenario(db, "curva@exemplo.com")

    curva = curva_atual(db, usuario.id, edital_id, date(2026, 9, 21))

    assert curva.lacuna == "sem data da prova"
    assert curva.necessaria == []


def test_curva_atual_com_respostas_suficientes_domina_topico(db: Session) -> None:
    usuario, edital_id, (topico,) = _cenario(db, "dominio@exemplo.com")
    questao = _gravar_questao(db, topico, "dominio", 1)
    hoje = date(2026, 9, 21)
    agora = datetime(2026, 9, 21, 12, tzinfo=UTC)
    for _ in range(3):  # MINIMO_PARA_DOMINADO
        _resposta(db, usuario, questao, agora, acertou=True)
    db.commit()

    curva = curva_atual(db, usuario.id, edital_id, hoje)

    assert curva.real[-1].dominados == 1


def test_alerta_atual_none_sem_concurso_principal(db: Session) -> None:
    usuario = criar_conta(db, DadosCadastro(email="sem-concurso@exemplo.com", senha="12345678"))
    db.commit()

    assert alerta_atual(db, usuario, date(2026, 9, 21)) is None

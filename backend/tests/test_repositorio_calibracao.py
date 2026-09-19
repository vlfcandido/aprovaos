# O que é: testes de `dados/repositorio_calibracao.py` — monta `RespostaBruta`/`ReporteBruto` a
# partir de `evento_estudo`/`reporte_erro` reais do banco (janela de dias), e `gravar_calibracao`
# grava `calibracao` + atualiza `questao` conforme a ação (fecha a P-34: despublicar grava
# `despublicada_em`). Quando ler: ao ligar o comando `motor/calibrar.py`.
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Calibracao, Documento, EventoEstudo, Questao, ReporteErro
from aprovaos.dados.repositorio_calibracao import (
    dificuldade_atual_por_questao,
    gravar_calibracao,
    origem_por_questao,
    reportes_da_janela,
    respostas_da_janela,
)
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dominio.calibracao import AjusteCalibracao
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _questao_curada(documento_id: UUID, numero: int) -> QuestaoCurada:
    origem = Origem(
        banca="cebraspe",
        orgao="TJ-PR",
        cargo="Técnico",
        ano=2025,
        numero_item=numero,
        tipo_caderno="A",
        url_prova="https://exemplo.org/prova.pdf",
        documento_id=str(documento_id),
    )
    enunciado = f"Enunciado sintético número {numero} para teste de calibração."
    return QuestaoCurada(
        adapter="concursos",
        banca="cebraspe",
        tipo_item="certo_errado",
        numero_item=numero,
        comando="Julgue o item.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=enunciado,
        alternativas=None,
        gabarito_preliminar="C",
        gabarito="C",
        gabarito_status="definitivo",
        publicavel=True,
        publicado=False,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=None,
        topico_confianca="baixa",
        topico_evidencia="sem correspondência no vocabulário",
        origem=origem,
        hash_dedup=hash_dedup(enunciado),
        justificativa_certo=None,
        justificativa_errado=None,
    )


def _gravar_questao(
    db: Session, documento: Documento, numero: int, *, inedita: bool = False
) -> Questao:
    from aprovaos.dados.repositorio_questao import salvar_questoes

    curada = _questao_curada(documento.id, numero)
    salvar_questoes(db, [curada])
    questao = db.scalars(select(Questao).where(Questao.hash_dedup == curada.hash_dedup)).one()
    if inedita:
        # `QuestaoCurada` (skill `ingestao-de-provas`) não tem campo `inedita` — a fatia 5
        # (gerador validado) ainda não existe; para o teste, marcamos direto no ORM.
        questao.inedita = True
        db.flush()
    return questao


def test_respostas_da_janela_ignora_resposta_fora_da_janela(db: Session) -> None:
    """Uma resposta de 20 dias atrás não entra numa janela de 14 dias."""
    usuario = criar_conta(db, DadosCadastro(email="a@x.com", senha="12345678"))
    documento = _documento(db, "doc-1")
    questao = _gravar_questao(db, documento, 1)
    dentro = EventoEstudo(
        usuario_id=usuario.id,
        ocorrido_em=agora_utc() - timedelta(days=2),
        tipo="resposta",
        questao_id=questao.id,
        acertou=True,
        resposta="C",
        confianca_declarada="certeza",
    )
    fora = EventoEstudo(
        usuario_id=usuario.id,
        ocorrido_em=agora_utc() - timedelta(days=20),
        tipo="resposta",
        questao_id=questao.id,
        acertou=False,
        resposta="E",
        confianca_declarada="duvida",
    )
    db.add_all([dentro, fora])
    db.commit()

    desde = agora_utc() - timedelta(days=14)
    respostas = respostas_da_janela(db, desde)
    assert len(respostas) == 1
    assert respostas[0].acertou is True


def test_respostas_da_janela_ignora_evento_que_nao_e_resposta(db: Session) -> None:
    """`checkin`/`reporte`/etc não são resposta — não entram em `respostas_da_janela`."""
    usuario = criar_conta(db, DadosCadastro(email="b@x.com", senha="12345678"))
    documento = _documento(db, "doc-2")
    questao = _gravar_questao(db, documento, 2)
    db.add(
        EventoEstudo(
            usuario_id=usuario.id,
            ocorrido_em=agora_utc(),
            tipo="reporte",
            questao_id=questao.id,
        )
    )
    db.commit()

    respostas = respostas_da_janela(db, agora_utc() - timedelta(days=14))
    assert respostas == []


def test_reportes_da_janela_traz_o_motivo(db: Session) -> None:
    """`reportes_da_janela` lê `reporte_erro` pela data de criação, com o texto do motivo."""
    usuario = criar_conta(db, DadosCadastro(email="c@x.com", senha="12345678"))
    documento = _documento(db, "doc-3")
    questao = _gravar_questao(db, documento, 3)
    db.add(
        ReporteErro(
            usuario_id=usuario.id,
            conteudo_tipo="questao",
            conteudo_id=questao.id,
            motivo="faltou o texto de apoio",
            status="aberto",
        )
    )
    db.commit()

    reportes = reportes_da_janela(db, agora_utc() - timedelta(days=14))
    assert len(reportes) == 1
    assert reportes[0].questao_id == questao.id
    assert reportes[0].motivo == "faltou o texto de apoio"


def test_origem_por_questao_distingue_original_e_inedita(db: Session) -> None:
    """`origem_por_questao` traduz `Questao.inedita` para o `Literal` do domínio."""
    documento = _documento(db, "doc-4")
    original = _gravar_questao(db, documento, 4, inedita=False)
    inedita = _gravar_questao(db, documento, 5, inedita=True)

    origens = origem_por_questao(db, [original.id, inedita.id])
    assert origens[original.id] == "original"
    assert origens[inedita.id] == "inedita"


def test_dificuldade_atual_por_questao_le_a_estimativa_gravada(db: Session) -> None:
    """Questão sem `dificuldade_est` gravada não entra no dicionário (nunca inventa `0.0`)."""
    documento = _documento(db, "doc-5")
    questao = _gravar_questao(db, documento, 6)
    questao.dificuldade_est = 0.42
    db.commit()

    dificuldades = dificuldade_atual_por_questao(db, [questao.id])
    assert dificuldades[questao.id] == 0.42


def test_gravar_calibracao_despublicar_grava_carimbo_e_some_da_tela(db: Session) -> None:
    """Fecha a P-34: `gravar_calibracao` com `acao='despublicar'` grava `despublicada_em`, o
    carimbo que `repositorio_questao.proxima_questao`/etc. passam a filtrar (teste dedicado em
    `test_repositorio_questao.py`; aqui só a gravação).
    """
    documento = _documento(db, "doc-6")
    questao = _gravar_questao(db, documento, 7)
    assert questao.topico_id is None  # sem tópico casado nesta fixture; ok para o teste de gravação

    ajuste = AjusteCalibracao(
        questao_id=questao.id,
        acao="despublicar",
        regra="R-1",
        evidencia="acerto=0.10, erro_confiante=0.40, taxa_reporte=0.05, n=50",
        efeito_colateral=["reabrir na ingestao-de-provas"],
        dificuldade_real=0.90,
        discriminacao="desconhecido",
        n=50,
    )
    gravar_calibracao(db, [ajuste], data=date.today())
    db.commit()
    db.refresh(questao)

    assert questao.despublicada_em is not None
    assert questao.publicada is False
    assert questao.dificuldade_est == 0.90

    linhas = db.scalars(select(Calibracao).where(Calibracao.questao_id == questao.id)).all()
    assert len(linhas) == 1
    assert linhas[0].acao == "despublicar"
    assert linhas[0].discriminacao is None


def test_gravar_calibracao_ajustar_nao_mexe_em_despublicada_em(db: Session) -> None:
    """`acao='ajustar'` só atualiza `dificuldade_est`/`discriminacao_est`; a questão continua
    servível (não mexe em `publicada`/`despublicada_em`).
    """
    documento = _documento(db, "doc-7")
    questao = _gravar_questao(db, documento, 8)

    ajuste = AjusteCalibracao(
        questao_id=questao.id,
        acao="ajustar",
        regra="R-6",
        evidencia="acerto=0.97, n=150",
        efeito_colateral=[],
        dificuldade_real=0.03,
        discriminacao=0.4123,
        n=150,
    )
    gravar_calibracao(db, [ajuste], data=date.today())
    db.commit()
    db.refresh(questao)

    assert questao.despublicada_em is None
    assert questao.publicada is False  # bookkeeping do calibrador só muda na despublicação
    assert questao.dificuldade_est == 0.03
    assert questao.discriminacao_est == 0.4123

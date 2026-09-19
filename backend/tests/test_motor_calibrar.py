# O que é: testes de `motor/calibrar.py` — o comando fim a fim (janela → agregação → regras →
# gravação) contra o banco de teste, e o relatório honesto sobre elegibilidade de discriminação
# (nunca infla o `n` de questão nenhuma). Quando ler: ao mexer no comando ou no relatório do lote.
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Calibracao, Documento, EventoEstudo, Questao, ReporteErro
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup
from aprovaos.motor.calibrar import calibrar_questoes


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _questao(db: Session, documento_id: UUID, numero: int) -> Questao:
    enunciado = f"Enunciado sintético {numero} do teste do comando calibrar."
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
    curada = QuestaoCurada(
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
    salvar_questoes(db, [curada])
    return db.scalars(select(Questao).where(Questao.hash_dedup == curada.hash_dedup)).one()


def test_calibrar_questoes_despublica_por_conteudo_faltando_e_grava_relatorio(db: Session) -> None:
    """Fim a fim: uma questão com reporte de conteúdo faltando (n baixo) é despublicada; o
    relatório diz honestamente que 0 questões tinham `n` suficiente para discriminação.
    """
    usuario = criar_conta(db, DadosCadastro(email="e@x.com", senha="12345678"))
    documento = _documento(db, "doc-cal-1")
    questao = _questao(db, documento.id, 1)
    db.add_all(
        [
            EventoEstudo(
                usuario_id=usuario.id,
                ocorrido_em=agora_utc(),
                tipo="resposta",
                questao_id=questao.id,
                acertou=False,
                resposta="E",
                confianca_declarada="duvida",
            ),
            ReporteErro(
                usuario_id=usuario.id,
                conteudo_tipo="questao",
                conteudo_id=questao.id,
                motivo="faltou o texto de apoio",
                status="aberto",
            ),
        ]
    )
    db.commit()

    relatorio = calibrar_questoes(db, agora_utc(), dias_janela=14, commit=True)
    db.commit()

    assert relatorio.avaliadas == 1
    assert relatorio.elegiveis_discriminacao == 0
    assert relatorio.ajustes[0].acao == "despublicar"
    assert relatorio.ajustes[0].regra == "R-3"

    db.refresh(questao)
    assert questao.despublicada_em is not None

    linhas = db.scalars(select(Calibracao).where(Calibracao.questao_id == questao.id)).all()
    assert len(linhas) == 1


def test_calibrar_questoes_dry_run_nao_grava_nada(db: Session) -> None:
    """`commit=False`: avalia e relata, mas não persiste `calibracao` nem toca `questao`."""
    usuario = criar_conta(db, DadosCadastro(email="f@x.com", senha="12345678"))
    documento = _documento(db, "doc-cal-2")
    questao = _questao(db, documento.id, 2)
    db.add(
        ReporteErro(
            usuario_id=usuario.id,
            conteudo_tipo="questao",
            conteudo_id=questao.id,
            motivo="não apareceu o texto",
            status="aberto",
        )
    )
    db.commit()

    relatorio = calibrar_questoes(db, agora_utc(), dias_janela=14, commit=False)

    assert relatorio.avaliadas == 1
    assert db.scalars(select(Calibracao)).all() == []
    db.refresh(questao)
    assert questao.despublicada_em is None


def test_calibrar_questoes_ignora_resposta_fora_da_janela(db: Session) -> None:
    """Nenhuma resposta/reporte na janela → relatório com zero questões avaliadas."""
    usuario = criar_conta(db, DadosCadastro(email="g@x.com", senha="12345678"))
    documento = _documento(db, "doc-cal-3")
    questao = _questao(db, documento.id, 3)
    db.add(
        EventoEstudo(
            usuario_id=usuario.id,
            ocorrido_em=agora_utc() - timedelta(days=30),
            tipo="resposta",
            questao_id=questao.id,
            acertou=True,
            resposta="C",
            confianca_declarada="certeza",
        )
    )
    db.commit()

    relatorio = calibrar_questoes(db, agora_utc(), dias_janela=14, commit=True)
    assert relatorio.avaliadas == 0
    assert relatorio.elegiveis_discriminacao == 0

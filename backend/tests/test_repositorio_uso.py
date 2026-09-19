# O que é: testes red-first do repositório de uso diário (fatia 12, Ruling 47) — `uso_do_dia`
# recomputa de `evento_estudo`, sem tabela própria (mesmo princípio do diagnóstico da fatia 7).
# Quando ler: ao mexer em `dados/repositorio_uso.py` ou no limite de questões/dia.
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Documento, EventoEstudo, Questao, Topico, Usuario
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_uso import uso_do_dia
from aprovaos.dominio.conta import DadosCadastro


def _usuario(db: Session, email: str = "linda@exemplo.com") -> Usuario:
    return criar_conta(db, DadosCadastro(email=email, senha="12345678"))


def _questao(db: Session, *, inedita: bool = False, hash_dedup: str = "h1") -> Questao:
    topico = Topico(materia="DIREITO CIVIL", nome="Prescrição", slug=f"slug-{hash_dedup}")
    documento = Documento(
        tipo="prova", hash=hash_dedup, caminho="p.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add_all([topico, documento])
    db.flush()
    questao = Questao(
        adapter="cebraspe",
        banca="cebraspe",
        tipo_item="certo_errado",
        enunciado="x",
        gabarito="C",
        gabarito_status="definitivo",
        publicavel=True,
        publicada=True,
        regra_prova={},
        topico_id=topico.id,
        topico_confianca="alta",
        topico_evidencia="x",
        documento_id=documento.id,
        hash_dedup=hash_dedup,
        inedita=inedita,
    )
    db.add(questao)
    db.flush()
    return questao


def _resposta(db: Session, usuario: Usuario, questao: Questao, ocorrido_em: datetime) -> None:
    db.add(
        EventoEstudo(
            usuario_id=usuario.id,
            ocorrido_em=ocorrido_em,
            tipo="resposta",
            questao_id=questao.id,
            acertou=True,
            resposta="C",
        )
    )
    db.flush()


def test_uso_do_dia_conta_so_respostas_de_hoje(db: Session) -> None:
    usuario = _usuario(db)
    questao = _questao(db, hash_dedup="h1")
    hoje = date(2026, 9, 19)
    meio_dia_utc = datetime.combine(hoje, time(12), tzinfo=ZoneInfo("UTC"))
    _resposta(db, usuario, questao, meio_dia_utc)
    _resposta(db, usuario, questao, meio_dia_utc - timedelta(days=1))  # ontem, não conta

    uso = uso_do_dia(db, usuario.id, hoje)

    assert uso.questoes_respondidas == 1
    assert uso.ineditas_servidas == 0


def test_uso_do_dia_conta_ineditas_separadamente(db: Session) -> None:
    usuario = _usuario(db)
    nativa = _questao(db, hash_dedup="h1", inedita=False)
    inedita = _questao(db, hash_dedup="h2", inedita=True)
    hoje = date(2026, 9, 19)
    meio_dia_utc = datetime.combine(hoje, time(12), tzinfo=ZoneInfo("UTC"))
    _resposta(db, usuario, nativa, meio_dia_utc)
    _resposta(db, usuario, inedita, meio_dia_utc)

    uso = uso_do_dia(db, usuario.id, hoje)

    assert uso.questoes_respondidas == 2
    assert uso.ineditas_servidas == 1


def test_uso_do_dia_ignora_evento_de_outro_usuario(db: Session) -> None:
    usuario = _usuario(db, "linda@exemplo.com")
    outro = _usuario(db, "outro@exemplo.com")
    questao = _questao(db, hash_dedup="h1")
    hoje = date(2026, 9, 19)
    meio_dia_utc = datetime.combine(hoje, time(12), tzinfo=ZoneInfo("UTC"))
    _resposta(db, outro, questao, meio_dia_utc)

    uso = uso_do_dia(db, usuario.id, hoje)

    assert uso.questoes_respondidas == 0


def test_uso_do_dia_sem_nenhuma_resposta(db: Session) -> None:
    usuario = _usuario(db)
    uso = uso_do_dia(db, usuario.id, date(2026, 9, 19))
    assert uso.questoes_respondidas == 0
    assert uso.ineditas_servidas == 0


def test_uso_do_dia_id_de_usuario_desconhecido_nao_falha(db: Session) -> None:
    uso = uso_do_dia(db, UUID(int=0), date(2026, 9, 19))
    assert uso.questoes_respondidas == 0

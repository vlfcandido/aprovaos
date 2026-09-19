# O que é: testes red-first de `dados/repositorio_lgpd.py` — exportar (RF-23) tudo que é do
# usuário em JSON, e excluir (anonimizar a conta, apagar cartão/perfil, revogar sessões — modelo
# de dados §5). Quando ler: ao mexer no que sai no export ou no que a exclusão apaga.
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Cartao, EventoEstudo, PerfilEstudo, Topico, Usuario
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_lgpd import excluir_dados_do_usuario, exportar_dados_do_usuario
from aprovaos.dados.repositorio_sessao import abrir_sessao, usuario_da_sessao
from aprovaos.dominio.conta import DadosCadastro


def _usuario_com_dados(db: Session) -> Usuario:
    usuario = criar_conta(db, DadosCadastro(email="linda@exemplo.com", senha="12345678"))
    db.flush()
    topico = Topico(materia="DIREITO CIVIL", nome="Prescrição", slug="dir-civ-01")
    db.add(topico)
    db.flush()
    db.add(
        EventoEstudo(
            usuario_id=usuario.id,
            ocorrido_em=agora_utc(),
            tipo="resposta",
            acertou=True,
            resposta="C",
        )
    )
    db.add(
        Cartao(
            usuario_id=usuario.id,
            topico_id=topico.id,
            frente="f",
            verso="v",
            origem="auto_erro",
            due=agora_utc(),
            reps=0,
            lapses=0,
            estado_fsrs=0,
        )
    )
    db.add(
        PerfilEstudo(
            usuario_id=usuario.id,
            versao=1,
            horas_por_dia_semana={},
            horario_preferido="manha",
            energia_tipica="media",
        )
    )
    db.commit()
    return usuario


def test_exportar_dados_do_usuario_traz_conta_eventos_cartoes_e_perfil(db: Session) -> None:
    usuario = _usuario_com_dados(db)
    dados = exportar_dados_do_usuario(db, usuario)
    assert dados["conta"]["email"] == "linda@exemplo.com"
    assert len(dados["eventos_estudo"]) == 1
    assert len(dados["cartoes"]) == 1
    assert len(dados["perfil_estudo"]) == 1
    # tudo serializável em JSON de verdade (datas/UUID/decimais já viraram string)
    import json

    json.dumps(dados)


def test_excluir_dados_do_usuario_anonimiza_a_conta(db: Session) -> None:
    usuario = _usuario_com_dados(db)
    agora = agora_utc()
    excluir_dados_do_usuario(db, usuario, agora)
    db.commit()

    recarregado = db.get(Usuario, usuario.id)
    assert recarregado is not None
    assert recarregado.excluido_em == agora
    assert recarregado.email != "linda@exemplo.com"
    assert recarregado.senha_hash is None


def test_excluir_dados_do_usuario_apaga_cartao_e_perfil(db: Session) -> None:
    usuario = _usuario_com_dados(db)
    excluir_dados_do_usuario(db, usuario, agora_utc())
    db.commit()

    assert db.scalar(select(Cartao.id).where(Cartao.usuario_id == usuario.id)) is None
    assert db.scalar(select(PerfilEstudo.id).where(PerfilEstudo.usuario_id == usuario.id)) is None


def test_excluir_dados_do_usuario_revoga_sessoes_ativas(db: Session) -> None:
    usuario = _usuario_com_dados(db)
    agora = agora_utc()
    token = abrir_sessao(db, usuario, dias=30, agora=agora)
    db.commit()
    assert usuario_da_sessao(db, token, agora) is not None

    excluir_dados_do_usuario(db, usuario, agora + timedelta(seconds=1))
    db.commit()

    assert usuario_da_sessao(db, token, agora + timedelta(seconds=2)) is None

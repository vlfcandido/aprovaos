# O que é: testes de `dados/repositorio_plano.py` (fatia 8) — geração noturna idempotente,
# reescrita por check-in (nova versão, nunca plano novo), ações de bloco (iniciar/concluir/
# pular), discordar (troca com e sem substituto) e `usuarios_ativos`. Quando ler: ao ligar
# `api/plano.py` ou `motor/plano.py`.
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from aprovaos.agentes.analista_de_edital import ResultadoDna
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Documento, EventoEstudo, Questao, Topico, Usuario
from aprovaos.dados.repositorio_cartao import registrar_erro
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_edital import DadosDocumento, registrar_edital
from aprovaos.dados.repositorio_perfil import salvar_perfil
from aprovaos.dados.repositorio_plano import (
    concluir_bloco,
    dias_para_prova_do_dia,
    discordar_bloco,
    gerar_ou_obter_plano_noturno,
    iniciar_bloco,
    plano_mais_recente,
    pular_bloco,
    registrar_checkin,
    usuarios_ativos,
)
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.dna import montar_dna_por_regras
from aprovaos.dominio.edital import MateriaExtraida, extrair_conteudo_programatico
from aprovaos.dominio.erros import SemConcursoPrincipal
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup
from aprovaos.dominio.rotina import DIAS_SEMANA, DadosRotina

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"

# Segunda-feira — DIAS_SEMANA[0] == "seg".
UMA_SEGUNDA = date(2026, 9, 21)


def _usuario(db: Session, email: str) -> Usuario:
    return criar_conta(db, DadosCadastro(email=email, senha="12345678"))


def _rotina(tempo_seg: float = 2.0) -> DadosRotina:
    horas = dict.fromkeys(DIAS_SEMANA, 0.0)
    horas["seg"] = tempo_seg
    return DadosRotina(
        horas_por_dia_semana=horas,
        horario_preferido="manha",
        energia_tipica="media",
        data_alvo=None,
        concurso_principal_id=None,
    )


@pytest.fixture
def materias() -> tuple[str, list[MateriaExtraida]]:
    texto = FIXTURE_MD.read_text(encoding="utf-8")
    return texto, extrair_conteudo_programatico(texto)


def _com_edital(
    db: Session,
    usuario: Usuario,
    materias: tuple[str, list[MateriaExtraida]],
    data_alvo: date | None = None,
) -> UUID:
    """Sobe o edital fixture e devolve o `edital_id`; `salvar_perfil` já aponta pra ele."""
    texto, lista_materias = materias
    resultado = ResultadoDna(
        dna=montar_dna_por_regras(texto, lista_materias), origem="regras", motivo_fallback="x"
    )
    documento = DadosDocumento(
        hash=f"{usuario.email}".ljust(64, "0")[:64],
        caminho_relativo="a.pdf",
        nome_original="a.pdf",
        tamanho=1,
        paginas=1,
    )
    concurso = registrar_edital(db, usuario.tenant_id, resultado, lista_materias, documento)
    db.commit()
    rotina = _rotina().model_copy(
        update={"concurso_principal_id": concurso.id, "data_alvo": data_alvo}
    )
    salvar_perfil(db, usuario, rotina)
    db.commit()
    from aprovaos.dados.repositorio_edital import edital_atual

    edital = edital_atual(db, concurso.id)
    assert edital is not None
    return edital.id


def _questao(topico: Topico, documento_id: UUID, numero: int) -> QuestaoCurada:
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
    enunciado = f"Enunciado plano {numero} sobre {topico.nome}."
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


def _topicos_do_edital(db: Session, edital_id: UUID, quantidade: int) -> list[Topico]:
    """Os `quantidade` primeiros tópicos do edital, na ordem de `TopicoEdital.ordem`."""
    from aprovaos.dados.modelos import TopicoEdital

    consulta = (
        db.query(Topico)
        .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
        .filter(TopicoEdital.edital_id == edital_id)
        .order_by(TopicoEdital.ordem)
        .limit(quantidade)
    )
    topicos = list(consulta)
    assert len(topicos) == quantidade
    return topicos


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


# ---------------------------------------------------------------------------
# usuarios_ativos
# ---------------------------------------------------------------------------


def test_usuarios_ativos_exige_perfil(db: Session) -> None:
    com_perfil = _usuario(db, "ativa@exemplo.com")
    salvar_perfil(db, com_perfil, _rotina())
    db.commit()
    _usuario(db, "sem-rotina@exemplo.com")
    db.commit()

    ativos = {u.email for u in usuarios_ativos(db)}
    assert ativos == {"ativa@exemplo.com"}


def test_usuarios_ativos_exclui_excluido(db: Session) -> None:
    usuario = _usuario(db, "excluida@exemplo.com")
    salvar_perfil(db, usuario, _rotina())
    usuario.excluido_em = agora_utc()
    db.commit()
    assert usuarios_ativos(db) == []


# ---------------------------------------------------------------------------
# gerar_ou_obter_plano_noturno
# ---------------------------------------------------------------------------


def test_gerar_plano_noturno_sem_rotina_levanta_erro(db: Session) -> None:
    usuario = _usuario(db, "j@exemplo.com")
    with pytest.raises(SemConcursoPrincipal):
        gerar_ou_obter_plano_noturno(db, usuario, UMA_SEGUNDA)


def test_gerar_plano_noturno_e_idempotente(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "k@exemplo.com")
    _com_edital(db, usuario, materias)

    primeiro = gerar_ou_obter_plano_noturno(db, usuario, UMA_SEGUNDA)
    db.commit()
    segundo = gerar_ou_obter_plano_noturno(db, usuario, UMA_SEGUNDA)
    db.commit()

    assert primeiro.id == segundo.id
    assert primeiro.versao == 1
    assert primeiro.tempo_min == 120  # 2h de segunda, da rotina


# ---------------------------------------------------------------------------
# registrar_checkin
# ---------------------------------------------------------------------------


def test_checkin_cria_versao_2_sem_apagar_a_1(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "l@exemplo.com")
    _com_edital(db, usuario, materias)
    primeiro = gerar_ou_obter_plano_noturno(db, usuario, UMA_SEGUNDA)
    db.commit()

    segundo = registrar_checkin(
        db, usuario, UMA_SEGUNDA, energia=4, sono_h=7.0, tempo_min=60, pediu_descanso=False
    )
    db.commit()

    assert segundo.versao == 2
    assert segundo.id != primeiro.id
    mais_recente = plano_mais_recente(db, usuario.id, UMA_SEGUNDA)
    assert mais_recente is not None
    assert mais_recente.id == segundo.id
    eventos = list(db.query(EventoEstudo).filter(EventoEstudo.tipo == "checkin"))
    assert len(eventos) == 1
    assert eventos[0].energia == 4


def test_checkin_sem_plano_noturno_previo_ainda_funciona(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "m@exemplo.com")
    _com_edital(db, usuario, materias)
    plano = registrar_checkin(
        db, usuario, UMA_SEGUNDA, energia=1, sono_h=3.0, tempo_min=60, pediu_descanso=False
    )
    db.commit()
    assert plano.versao == 2  # a versão 1 nasceu por baixo, silenciosamente
    assert plano.modo == "descanso"


def test_checkin_energia_baixa_restringe_a_revisao(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "n@exemplo.com")
    edital_id = _com_edital(db, usuario, materias)
    (topico,) = _topicos_do_edital(db, edital_id, 1)
    documento = _documento(db, "n" * 64)
    salvar_questoes(db, [_questao(topico, documento.id, 1)])
    db.commit()
    questao = db.query(Questao).filter(Questao.topico_id == topico.id).first()
    assert questao is not None
    # `due` no passado: um cartão recém-criado não fica vencido na mesma hora em que nasce.
    cartao = registrar_erro(db, usuario, questao, "duvida", agora_utc() - timedelta(days=1))
    assert cartao is not None
    db.commit()

    plano = registrar_checkin(
        db, usuario, UMA_SEGUNDA, energia=1, sono_h=7.0, tempo_min=60, pediu_descanso=False
    )
    db.commit()
    assert [b.tipo for b in plano.blocos] == ["revisao"]


# ---------------------------------------------------------------------------
# iniciar/concluir/pular_bloco
# ---------------------------------------------------------------------------


def test_ciclo_de_vida_do_bloco(db: Session, materias: tuple[str, list[MateriaExtraida]]) -> None:
    usuario = _usuario(db, "o@exemplo.com")
    edital_id = _com_edital(db, usuario, materias)
    (topico,) = _topicos_do_edital(db, edital_id, 1)
    documento = _documento(db, "o" * 64)
    salvar_questoes(db, [_questao(topico, documento.id, 1)])
    db.commit()
    plano = registrar_checkin(
        db, usuario, UMA_SEGUNDA, energia=4, sono_h=7.0, tempo_min=60, pediu_descanso=False
    )
    db.commit()
    assert plano.blocos, "esperava pelo menos um bloco com conteúdo disponível"
    bloco = plano.blocos[0]

    iniciar_bloco(db, usuario, bloco, agora_utc())
    db.commit()
    assert bloco.status == "iniciado"
    assert bloco.iniciado_em is not None

    concluir_bloco(db, usuario, bloco, agora_utc())
    db.commit()
    assert bloco.status == "concluido"
    assert bloco.concluido_em is not None

    tipos_evento = [
        e.tipo for e in db.query(EventoEstudo).filter(EventoEstudo.bloco_id == bloco.id)
    ]
    assert tipos_evento == ["bloco_iniciado", "bloco_concluido"]


def test_pular_bloco_grava_evento(db: Session, materias: tuple[str, list[MateriaExtraida]]) -> None:
    usuario = _usuario(db, "p@exemplo.com")
    edital_id = _com_edital(db, usuario, materias)
    (topico,) = _topicos_do_edital(db, edital_id, 1)
    documento = _documento(db, "p" * 64)
    salvar_questoes(db, [_questao(topico, documento.id, 1)])
    db.commit()
    plano = registrar_checkin(
        db, usuario, UMA_SEGUNDA, energia=4, sono_h=7.0, tempo_min=60, pediu_descanso=False
    )
    db.commit()
    bloco = plano.blocos[0]
    pular_bloco(db, usuario, bloco, agora_utc())
    db.commit()
    assert bloco.status == "pulado"


# ---------------------------------------------------------------------------
# discordar_bloco
# ---------------------------------------------------------------------------


def test_discordar_troca_o_bloco_quando_ha_alternativa(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "q@exemplo.com")
    edital_id = _com_edital(db, usuario, materias)
    topico_forte, topico_fraco = _topicos_do_edital(db, edital_id, 2)
    documento = _documento(db, "q" * 64)
    # Dois tópicos com questão — o primeiro com mais peso (2 questões) sai na frente da trilha
    # e vira o bloco escolhido; o segundo (1 questão) fica como alternativa não usada.
    salvar_questoes(
        db,
        [
            _questao(topico_forte, documento.id, 1),
            _questao(topico_forte, documento.id, 2),
            _questao(topico_fraco, documento.id, 3),
        ],
    )
    db.commit()

    # tempo curto: só um bloco cabe, sobra alternativa pro "discordo" escolher.
    plano = registrar_checkin(
        db, usuario, UMA_SEGUNDA, energia=4, sono_h=7.0, tempo_min=20, pediu_descanso=False
    )
    db.commit()
    assert len(plano.blocos) == 1
    bloco_atual = plano.blocos[0]

    bloco_novo, evento = discordar_bloco(db, usuario, bloco_atual, "ja_sei", agora_utc())
    db.commit()
    assert evento.tipo == "discordou"
    assert evento.dados is not None
    assert evento.dados["motivo"] == "ja_sei"
    assert bloco_atual.status == "trocado"
    assert bloco_novo is not None
    assert "Você disse:" in bloco_novo.porque


def test_discordar_sem_alternativa_mantem_o_bloco(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "r@exemplo.com")
    edital_id = _com_edital(db, usuario, materias)
    (topico,) = _topicos_do_edital(db, edital_id, 1)
    documento = _documento(db, "r" * 64)
    salvar_questoes(db, [_questao(topico, documento.id, 1)])
    db.commit()

    plano = registrar_checkin(
        db, usuario, UMA_SEGUNDA, energia=4, sono_h=7.0, tempo_min=20, pediu_descanso=False
    )
    db.commit()
    bloco_atual = plano.blocos[0]

    bloco_novo, evento = discordar_bloco(db, usuario, bloco_atual, "cansada", agora_utc())
    db.commit()
    assert bloco_novo is None
    assert evento.dados is not None
    assert evento.dados["substituto_tipo"] is None
    assert bloco_atual.status != "trocado"


# ---------------------------------------------------------------------------
# semana da prova (RF-19, fatia 10 §7, fecha a P-55) — `perfil_estudo.data_alvo` até
# `montar_plano(dias_para_prova=...)`
# ---------------------------------------------------------------------------


def test_geracao_noturna_liga_semana_da_prova_com_data_alvo_proxima(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "s@exemplo.com")
    _com_edital(db, usuario, materias, data_alvo=UMA_SEGUNDA + timedelta(days=3))

    plano = gerar_ou_obter_plano_noturno(db, usuario, UMA_SEGUNDA)
    db.commit()

    assert plano.modo == "semana_prova"
    assert "3 dias" in plano.porque_geral


def test_geracao_noturna_sem_data_alvo_nao_liga_semana_da_prova(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "t@exemplo.com")
    _com_edital(db, usuario, materias, data_alvo=None)

    plano = gerar_ou_obter_plano_noturno(db, usuario, UMA_SEGUNDA)
    db.commit()

    assert plano.modo != "semana_prova"


def test_checkin_liga_semana_da_prova_com_data_alvo_proxima(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "u@exemplo.com")
    _com_edital(db, usuario, materias, data_alvo=UMA_SEGUNDA)  # 0 dias — ainda dentro da janela

    plano = registrar_checkin(
        db, usuario, UMA_SEGUNDA, energia=4, sono_h=7.0, tempo_min=60, pediu_descanso=False
    )
    db.commit()

    assert plano.modo == "semana_prova"


def test_dias_para_prova_do_dia_calcula_a_partir_do_perfil(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "v@exemplo.com")
    _com_edital(db, usuario, materias, data_alvo=UMA_SEGUNDA + timedelta(days=10))
    assert dias_para_prova_do_dia(db, usuario.id, UMA_SEGUNDA) == 10


def test_dias_para_prova_do_dia_sem_perfil_e_none(db: Session) -> None:
    usuario = _usuario(db, "w@exemplo.com")
    assert dias_para_prova_do_dia(db, usuario.id, UMA_SEGUNDA) is None

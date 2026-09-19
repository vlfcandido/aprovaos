# O que é: testes de contrato de `GET /hoje`, `POST /hoje/checkin` e das ações de bloco
# (iniciar/concluir/pular/discordar) — fatia 8, F3.x — e o selo de "semana da prova" (RF-19,
# fatia 10 §7). Quando ler: ao mexer na tela "Hoje".
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aprovaos.agentes.analista_de_edital import ResultadoDna
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Documento, PlanoDia, Topico, TopicoEdital, Usuario
from aprovaos.dados.repositorio_edital import DadosDocumento, registrar_edital
from aprovaos.dados.repositorio_perfil import salvar_perfil
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.dna import montar_dna_por_regras
from aprovaos.dominio.edital import extrair_conteudo_programatico
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup
from aprovaos.dominio.rotina import DIAS_SEMANA, DadosRotina

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"


def _entrar(cliente: TestClient, email: str) -> None:
    resposta = cliente.post("/cadastro", data={"email": email, "senha": "12345678"})
    assert resposta.status_code in (200, 303)


def _usuario_por_email(db: Session, email: str) -> Usuario:
    return db.query(Usuario).filter_by(email=email).one()


def _questao(topico: Topico, documento_id: object, numero: int) -> QuestaoCurada:
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
    enunciado = f"Enunciado rota-plano {numero} sobre {topico.nome}."
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


def _preparar_conta_com_conteudo(
    cliente: TestClient, db: Session, email: str, data_alvo: date | None = None
) -> Usuario:
    """Cadastra, sobe o edital fixture, define rotina (2h/dia todo dia) e grava uma questão."""
    _entrar(cliente, email)
    usuario = _usuario_por_email(db, email)

    texto = FIXTURE_MD.read_text(encoding="utf-8")
    materias = extrair_conteudo_programatico(texto)
    resultado = ResultadoDna(
        dna=montar_dna_por_regras(texto, materias), origem="regras", motivo_fallback="x"
    )
    documento = DadosDocumento(
        hash=email.ljust(64, "0")[:64],
        caminho_relativo="a.pdf",
        nome_original="a.pdf",
        tamanho=1,
        paginas=1,
    )
    concurso = registrar_edital(db, usuario.tenant_id, resultado, materias, documento)
    db.commit()

    horas = dict.fromkeys(DIAS_SEMANA, 2.0)
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

    topico_edital = (
        db.query(TopicoEdital)
        .join(Topico, TopicoEdital.topico_id == Topico.id)
        .filter(TopicoEdital.edital_id.isnot(None))
        .first()
    )
    assert topico_edital is not None
    topico = db.get(Topico, topico_edital.topico_id)
    assert topico is not None
    documento_prova = Documento(
        tipo="prova",
        hash=f"prova-{email}".ljust(64, "0")[:64],
        caminho="prova.pdf",
        baixado_em=agora_utc(),
        metadados={},
    )
    db.add(documento_prova)
    db.flush()
    salvar_questoes(db, [_questao(topico, documento_prova.id, 1)])
    db.commit()
    return usuario


def test_hoje_exige_login(cliente: TestClient) -> None:
    resposta = cliente.get("/hoje", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_hoje_sem_rotina_mostra_link_para_configurar(cliente: TestClient) -> None:
    _entrar(cliente, "sem-rotina@exemplo.com")
    resposta = cliente.get("/hoje")
    assert resposta.status_code == 200
    assert "/rotina" in resposta.text


def test_hoje_gera_plano_na_primeira_visita(cliente: TestClient, db: Session) -> None:
    _preparar_conta_com_conteudo(cliente, db, "primeira@exemplo.com")
    resposta = cliente.get("/hoje")
    assert resposta.status_code == 200
    assert "Por quê" in resposta.text

    usuario = _usuario_por_email(db, "primeira@exemplo.com")
    planos = db.query(PlanoDia).filter_by(usuario_id=usuario.id).all()
    assert len(planos) == 1
    assert planos[0].versao == 1


def test_hoje_e_idempotente_entre_visitas(cliente: TestClient, db: Session) -> None:
    _preparar_conta_com_conteudo(cliente, db, "duasvisitas@exemplo.com")
    cliente.get("/hoje")
    cliente.get("/hoje")
    usuario = _usuario_por_email(db, "duasvisitas@exemplo.com")
    planos = db.query(PlanoDia).filter_by(usuario_id=usuario.id).all()
    assert len(planos) == 1


def test_checkin_energia_invalida(cliente: TestClient, db: Session) -> None:
    _preparar_conta_com_conteudo(cliente, db, "energiainvalida@exemplo.com")
    resposta = cliente.post(
        "/hoje/checkin", data={"energia": "9", "sono_h": "7", "tempo_min": "60"}
    )
    assert resposta.status_code == 400
    corpo = resposta.json()
    assert set(corpo) == {"codigo", "mensagem", "acao"}


def test_checkin_reescreve_para_versao_2(cliente: TestClient, db: Session) -> None:
    _preparar_conta_com_conteudo(cliente, db, "checkin@exemplo.com")
    cliente.get("/hoje")  # garante a versão 1

    resposta = cliente.post(
        "/hoje/checkin", data={"energia": "4", "sono_h": "7", "tempo_min": "40"}
    )
    assert resposta.status_code == 200

    usuario = _usuario_por_email(db, "checkin@exemplo.com")
    planos = db.query(PlanoDia).filter_by(usuario_id=usuario.id).order_by(PlanoDia.versao).all()
    assert [p.versao for p in planos] == [1, 2]
    assert planos[-1].energia == 4


def test_checkin_energia_baixa_sem_cartao_mostra_descanso(cliente: TestClient, db: Session) -> None:
    _preparar_conta_com_conteudo(cliente, db, "descanso@exemplo.com")
    resposta = cliente.post(
        "/hoje/checkin", data={"energia": "1", "sono_h": "7", "tempo_min": "60"}
    )
    assert resposta.status_code == 200
    assert "descansar" in resposta.text.lower()


def test_ciclo_iniciar_concluir_bloco(cliente: TestClient, db: Session) -> None:
    _preparar_conta_com_conteudo(cliente, db, "ciclo@exemplo.com")
    cliente.post("/hoje/checkin", data={"energia": "4", "sono_h": "7", "tempo_min": "60"})
    usuario = _usuario_por_email(db, "ciclo@exemplo.com")
    plano = (
        db.query(PlanoDia).filter_by(usuario_id=usuario.id).order_by(PlanoDia.versao.desc()).first()
    )
    assert plano is not None
    assert plano.blocos, "esperava bloco com a questão gravada"
    bloco = plano.blocos[0]

    resposta = cliente.post(f"/hoje/bloco/{bloco.id}/iniciar")
    assert resposta.status_code == 200
    db.refresh(bloco)
    assert bloco.status == "iniciado"

    resposta = cliente.post(f"/hoje/bloco/{bloco.id}/concluir")
    assert resposta.status_code == 200
    db.refresh(bloco)
    assert bloco.status == "concluido"


def test_pular_bloco(cliente: TestClient, db: Session) -> None:
    _preparar_conta_com_conteudo(cliente, db, "pular@exemplo.com")
    cliente.post("/hoje/checkin", data={"energia": "4", "sono_h": "7", "tempo_min": "60"})
    usuario = _usuario_por_email(db, "pular@exemplo.com")
    plano = (
        db.query(PlanoDia).filter_by(usuario_id=usuario.id).order_by(PlanoDia.versao.desc()).first()
    )
    assert plano is not None
    bloco = plano.blocos[0]

    resposta = cliente.post(f"/hoje/bloco/{bloco.id}/pular")
    assert resposta.status_code == 200
    db.refresh(bloco)
    assert bloco.status == "pulado"


def test_discordar_motivo_invalido(cliente: TestClient, db: Session) -> None:
    _preparar_conta_com_conteudo(cliente, db, "motivoinvalido@exemplo.com")
    cliente.post("/hoje/checkin", data={"energia": "4", "sono_h": "7", "tempo_min": "20"})
    usuario = _usuario_por_email(db, "motivoinvalido@exemplo.com")
    plano = (
        db.query(PlanoDia).filter_by(usuario_id=usuario.id).order_by(PlanoDia.versao.desc()).first()
    )
    assert plano is not None
    bloco = plano.blocos[0]

    resposta = cliente.post(f"/hoje/bloco/{bloco.id}/discordar", data={"motivo": "nao-existe"})
    assert resposta.status_code == 400
    assert set(resposta.json()) == {"codigo", "mensagem", "acao"}


def test_discordar_bloco_de_outro_usuario_e_404(cliente: TestClient, db: Session) -> None:
    _preparar_conta_com_conteudo(cliente, db, "dona@exemplo.com")
    dona = _usuario_por_email(db, "dona@exemplo.com")
    plano_dona = (
        db.query(PlanoDia).filter_by(usuario_id=dona.id).order_by(PlanoDia.versao.desc()).first()
    )
    assert plano_dona is None  # ainda não visitou /hoje
    cliente.get("/hoje")
    plano_dona = (
        db.query(PlanoDia).filter_by(usuario_id=dona.id).order_by(PlanoDia.versao.desc()).first()
    )
    assert plano_dona is not None
    bloco_da_dona = plano_dona.blocos[0] if plano_dona.blocos else None

    outro_cliente = TestClient(cliente.app)
    _entrar(outro_cliente, "intrusa@exemplo.com")
    if bloco_da_dona is not None:
        resposta = outro_cliente.post(f"/hoje/bloco/{bloco_da_dona.id}/pular")
        assert resposta.status_code == 404
        assert set(resposta.json()) == {"codigo", "mensagem", "acao"}


def test_bloco_inexistente_e_404(cliente: TestClient) -> None:
    _entrar(cliente, "qualquer@exemplo.com")
    resposta = cliente.post(f"/hoje/bloco/{uuid4()}/iniciar")
    assert resposta.status_code == 404
    assert set(resposta.json()) == {"codigo", "mensagem", "acao"}


def test_hoje_mostra_selo_de_semana_da_prova(cliente: TestClient, db: Session) -> None:
    hoje = agora_utc().date()
    _preparar_conta_com_conteudo(
        cliente, db, "semanadaprova@exemplo.com", data_alvo=hoje + timedelta(days=3)
    )
    resposta = cliente.get("/hoje")
    assert resposta.status_code == 200
    assert "Semana da prova" in resposta.text
    assert "Faltam 3 dias para a prova" in resposta.text


def test_hoje_sem_data_alvo_nao_mostra_selo_de_semana_da_prova(
    cliente: TestClient, db: Session
) -> None:
    _preparar_conta_com_conteudo(cliente, db, "semdataalvo@exemplo.com", data_alvo=None)
    resposta = cliente.get("/hoje")
    assert resposta.status_code == 200
    assert "Semana da prova" not in resposta.text

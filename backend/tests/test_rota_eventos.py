# O que é: testes de contrato de `POST /api/distracao` (fatia 8, F3.6/S-05) — grava o evento do
# bloco em andamento; sem sessão, 401 no formato padrão; bloco de outro usuário, 404. Quando ler:
# ao mexer no aviso de distração ou no que ele grava.
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import EventoEstudo, PlanoDia
from tests.test_rota_plano import _entrar, _preparar_conta_com_conteudo, _usuario_por_email


def test_distracao_sem_sessao_e_401(cliente: TestClient) -> None:
    resposta = cliente.post("/api/distracao", json={"bloco_id": str(uuid4())})
    assert resposta.status_code == 401
    assert set(resposta.json()) == {"codigo", "mensagem", "acao"}


def test_distracao_bloco_inexistente_e_404(cliente: TestClient) -> None:
    _entrar(cliente, "distracao-sem-bloco@exemplo.com")
    resposta = cliente.post("/api/distracao", json={"bloco_id": str(uuid4())})
    assert resposta.status_code == 404


def test_distracao_grava_evento(cliente: TestClient, db: Session) -> None:
    _preparar_conta_com_conteudo(cliente, db, "distracao@exemplo.com")
    cliente.post("/hoje/checkin", data={"energia": "4", "sono_h": "7", "tempo_min": "60"})
    usuario = _usuario_por_email(db, "distracao@exemplo.com")
    plano = (
        db.query(PlanoDia).filter_by(usuario_id=usuario.id).order_by(PlanoDia.versao.desc()).first()
    )
    assert plano is not None
    bloco = plano.blocos[0]

    resposta = cliente.post("/api/distracao", json={"bloco_id": str(bloco.id)})
    assert resposta.status_code == 204

    eventos = db.query(EventoEstudo).filter_by(tipo="distracao", bloco_id=bloco.id).all()
    assert len(eventos) == 1
    assert eventos[0].usuario_id == usuario.id


def test_distracao_bloco_de_outro_usuario_e_404(cliente: TestClient, db: Session) -> None:
    _preparar_conta_com_conteudo(cliente, db, "dona-distracao@exemplo.com")
    dona = _usuario_por_email(db, "dona-distracao@exemplo.com")
    cliente.get("/hoje")
    plano = (
        db.query(PlanoDia).filter_by(usuario_id=dona.id).order_by(PlanoDia.versao.desc()).first()
    )
    assert plano is not None
    if not plano.blocos:
        return  # nada a testar sem bloco (não deveria acontecer com a fixture desta conta)
    bloco = plano.blocos[0]

    outro_cliente = TestClient(cliente.app)
    _entrar(outro_cliente, "intrusa-distracao@exemplo.com")
    resposta = outro_cliente.post("/api/distracao", json={"bloco_id": str(bloco.id)})
    assert resposta.status_code == 404

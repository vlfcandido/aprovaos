# O que é: testes de contrato de `GET/POST /rotina` (fatia 7, F2.2) — consentimento obrigatório
# (R-01), versão incremental, e a P-23 (concurso principal só aceita concurso do próprio tenant).
# Quando ler: ao mexer no formulário de rotina.
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aprovaos.agentes.analista_de_edital import ResultadoDna
from aprovaos.dados.modelos import PerfilEstudo, Usuario
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_edital import DadosDocumento, registrar_edital
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.dna import montar_dna_por_regras
from aprovaos.dominio.edital import extrair_conteudo_programatico

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"

CAMPOS_PADRAO = {
    "hora_seg": "2",
    "hora_ter": "2",
    "hora_qua": "2",
    "hora_qui": "2",
    "hora_sex": "1",
    "hora_sab": "4",
    "hora_dom": "0",
    "horario_preferido": "manha",
    "energia_tipica": "media",
    "data_alvo": "",
    "concurso_principal_id": "",
}


def _entrar(cliente: TestClient, email: str) -> None:
    cliente.post("/cadastro", data={"email": email, "senha": "12345678"})


def test_rotina_exige_login(cliente: TestClient) -> None:
    resposta = cliente.get("/rotina", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_post_rotina_sem_consentimento_nao_salva(cliente: TestClient, db: Session) -> None:
    _entrar(cliente, "a@exemplo.com")
    resposta = cliente.post("/rotina", data=CAMPOS_PADRAO)
    assert resposta.status_code == 200
    assert "consentimento" in resposta.text.lower()

    usuario = db.query(Usuario).filter_by(email="a@exemplo.com").one()
    assert usuario.consentimento_dados_rotina is False


def test_post_rotina_com_consentimento_salva_perfil(cliente: TestClient, db: Session) -> None:
    _entrar(cliente, "b@exemplo.com")
    dados = dict(CAMPOS_PADRAO, consentimento="on")
    resposta = cliente.post("/rotina", data=dados, follow_redirects=False)
    assert resposta.status_code in (200, 303)

    usuario = db.query(Usuario).filter_by(email="b@exemplo.com").one()
    assert usuario.consentimento_dados_rotina is True
    perfil = db.query(PerfilEstudo).filter_by(usuario_id=usuario.id).one()
    assert perfil.horario_preferido == "manha"
    assert perfil.horas_por_dia_semana["seg"] == 2.0


def test_post_rotina_rejeita_concurso_de_outro_tenant(cliente: TestClient, db: Session) -> None:
    outro = criar_conta(db, DadosCadastro(email="dono-outro@exemplo.com", senha="12345678"))
    texto = FIXTURE_MD.read_text(encoding="utf-8")
    materias = extrair_conteudo_programatico(texto)
    resultado = ResultadoDna(
        dna=montar_dna_por_regras(texto, materias), origem="regras", motivo_fallback="x"
    )
    documento = DadosDocumento(
        hash="ff" * 32, caminho_relativo="f.pdf", nome_original="f.pdf", tamanho=1, paginas=1
    )
    concurso_alheio = registrar_edital(db, outro.tenant_id, resultado, materias, documento)
    db.commit()

    _entrar(cliente, "c@exemplo.com")
    dados = dict(CAMPOS_PADRAO, consentimento="on", concurso_principal_id=str(concurso_alheio.id))
    resposta = cliente.post("/rotina", data=dados)
    assert resposta.status_code == 200
    assert "inválido" in resposta.text.lower() or "concurso" in resposta.text.lower()

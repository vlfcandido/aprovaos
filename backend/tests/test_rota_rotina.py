# O que é: testes de contrato de `GET/POST /rotina` (fatia 7, F2.2) — consentimento obrigatório
# (R-01), versão incremental, e a P-23 (concurso principal só aceita concurso do próprio tenant).
# Quando ler: ao mexer no formulário de rotina.
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aprovaos.agentes.analista_de_edital import ResultadoDna
from aprovaos.dados.modelos import Concurso, PerfilEstudo, Usuario
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


def test_get_rotina_checkbox_nunca_nasce_marcada_mesmo_apos_consentir(
    cliente: TestClient, db: Session
) -> None:
    """I8: caixa pré-marcada não é manifestação inequívoca (LGPD) — mesmo depois de consentir
    uma vez, a próxima `GET /rotina` mostra a caixa desmarcada, com a data do aceite anterior em
    texto ao lado."""
    _entrar(cliente, "d@exemplo.com")
    dados = dict(CAMPOS_PADRAO, consentimento="on")
    assert cliente.post("/rotina", data=dados, follow_redirects=False).status_code in (200, 303)

    resposta = cliente.get("/rotina")

    assert resposta.status_code == 200
    assert 'name="consentimento" checked' not in resposta.text
    assert 'name="consentimento">' in resposta.text
    assert "você autorizou em" in resposta.text.lower()
    assert "versão" in resposta.text.lower()

    usuario = db.query(Usuario).filter_by(email="d@exemplo.com").one()
    assert usuario.consentimento_dados_rotina is True


def test_get_rotina_sem_consentimento_anterior_nao_mostra_aviso(cliente: TestClient) -> None:
    _entrar(cliente, "e@exemplo.com")

    resposta = cliente.get("/rotina")

    assert resposta.status_code == 200
    assert 'name="consentimento" checked' not in resposta.text
    assert "você autorizou em" not in resposta.text.lower()


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


def test_rotina_mostra_energia_com_acento_e_sem_valor_cru(cliente: TestClient) -> None:
    """Passada visual de 23/09/2026: o `<select>` de energia mostrava "Media", sem acento — o
    valor cru do domínio passado por `capitalize`. Rótulo é texto de interface, não enum.

    A asserção deixou de depender de `>Média<` quando o `<select>` virou controle segmentado
    (23/09/2026): o rótulo agora fica dentro do `<label>`, não colado no `>`. A regra que
    importa é a mesma — e "Media" com maiúscula não casa com o `value="media"` do domínio.
    """
    _entrar(cliente, "f@exemplo.com")
    corpo = cliente.get("/rotina").text
    assert "Média" in corpo
    assert "Media" not in corpo


# ---- a tela sem digitação (23/09/2026) -------------------------------------------------------
# "tela de sua rotina tá péssima pra ficar digitando os dados ali, pensa mais no Duolingo"
# (dono). O caminho principal virou atalho tocável; o teclado é exceção. O que estes testes
# protegem é o que a piloto não vê: que a tela continua funcionando **sem JS** e que o contrato
# antigo do formulário (só `hora_*`) não quebrou.


def _registrar_concurso_do_usuario(db: Session, email: str) -> Concurso:
    """Registra um edital no tenant de quem está logado — para o caso de "um concurso só"."""
    usuario = db.query(Usuario).filter_by(email=email).one()
    texto = FIXTURE_MD.read_text(encoding="utf-8")
    materias = extrair_conteudo_programatico(texto)
    resultado = ResultadoDna(
        dna=montar_dna_por_regras(texto, materias), origem="regras", motivo_fallback="x"
    )
    documento = DadosDocumento(
        hash="ab" * 32, caminho_relativo="g.pdf", nome_original="g.pdf", tamanho=1, paginas=1
    )
    concurso = registrar_edital(db, usuario.tenant_id, resultado, materias, documento)
    db.commit()
    return concurso


def test_atalho_salva_a_semana_inteira_sem_nenhum_campo_de_hora(
    cliente: TestClient, db: Session
) -> None:
    """Sem JS, o atalho é o único dado de tempo que chega — e precisa bastar."""
    _entrar(cliente, "g@exemplo.com")

    resposta = cliente.post(
        "/rotina",
        data={
            "preset_uteis": "2",
            "preset_fds": "0",
            "horario_preferido": "noite",
            "energia_tipica": "baixa",
            "consentimento": "on",
        },
        follow_redirects=False,
    )

    assert resposta.status_code in (200, 303)
    usuario = db.query(Usuario).filter_by(email="g@exemplo.com").one()
    perfil = db.query(PerfilEstudo).filter_by(usuario_id=usuario.id).one()
    assert perfil.horas_por_dia_semana["qua"] == 2.0
    assert perfil.horas_por_dia_semana["sab"] == 0.0
    assert perfil.horario_preferido == "noite"


def test_ajuste_dia_a_dia_vence_o_atalho_do_mesmo_grupo(cliente: TestClient, db: Session) -> None:
    """Quem abriu o `<details>` e digitou quer precisão — o atalho não pode apagar isso."""
    _entrar(cliente, "h@exemplo.com")
    dados = dict(
        CAMPOS_PADRAO,
        consentimento="on",
        preset_uteis="manual",
        preset_fds="3",
        hora_seg="1.5",
    )

    assert cliente.post("/rotina", data=dados, follow_redirects=False).status_code in (200, 303)

    usuario = db.query(Usuario).filter_by(email="h@exemplo.com").one()
    perfil = db.query(PerfilEstudo).filter_by(usuario_id=usuario.id).one()
    assert perfil.horas_por_dia_semana["seg"] == 1.5
    assert perfil.horas_por_dia_semana["sab"] == 3.0


def test_get_rotina_reabre_com_o_atalho_que_ela_escolheu(cliente: TestClient) -> None:
    """Tela que esquece a escolha obriga a escolher de novo — é digitação por outro nome."""
    _entrar(cliente, "i@exemplo.com")
    cliente.post(
        "/rotina",
        data={
            "preset_uteis": "3",
            "preset_fds": "1",
            "horario_preferido": "manha",
            "energia_tipica": "alta",
            "consentimento": "on",
        },
        follow_redirects=False,
    )

    corpo = cliente.get("/rotina").text

    assert 'name="preset_uteis" value="3" checked' in corpo
    assert 'name="preset_fds" value="1" checked' in corpo


def test_get_rotina_abre_o_ajuste_fino_quando_nenhum_atalho_descreve_a_rotina(
    cliente: TestClient,
) -> None:
    """2,5 h por dia é rotina real e não tem atalho: a tela abre no modo fino, sem mentir."""
    _entrar(cliente, "j@exemplo.com")
    dados = dict(
        CAMPOS_PADRAO,
        consentimento="on",
        **{d: "2.5" for d in ("hora_seg", "hora_ter", "hora_qua", "hora_qui", "hora_sex")},
    )
    cliente.post("/rotina", data=dados, follow_redirects=False)

    corpo = cliente.get("/rotina").text

    assert 'name="preset_uteis" value="manual" checked' in corpo
    assert 'class="ajuste-fino" open' in corpo


def test_get_rotina_pergunta_turno_e_energia_por_toque_e_nao_por_select(
    cliente: TestClient,
) -> None:
    """Dois `<select>` viraram controles segmentados: alvo grande, uma escolha visível."""
    _entrar(cliente, "k@exemplo.com")

    corpo = cliente.get("/rotina").text

    assert 'name="horario_preferido"' in corpo
    assert 'name="energia_tipica"' in corpo
    assert "<select" not in corpo
    assert 'type="radio" name="horario_preferido"' in corpo
    assert 'type="radio" name="energia_tipica"' in corpo


def test_get_rotina_nao_pergunta_o_concurso_quando_so_existe_um(
    cliente: TestClient, db: Session
) -> None:
    """Perguntar o que só tem uma resposta é desperdiçar o fôlego dela (pedido do dono)."""
    _entrar(cliente, "l@exemplo.com")
    concurso = _registrar_concurso_do_usuario(db, "l@exemplo.com")

    corpo = cliente.get("/rotina").text

    assert 'name="concurso_principal_id"' in corpo
    assert 'type="hidden" name="concurso_principal_id"' in corpo
    assert concurso.cargo in corpo


def test_get_rotina_mostra_o_total_da_semana(cliente: TestClient) -> None:
    """Feedback imediato: ela vê o que a escolha dela significa, sem precisar somar."""
    _entrar(cliente, "m@exemplo.com")
    cliente.post(
        "/rotina",
        data={
            "preset_uteis": "2",
            "preset_fds": "3",
            "horario_preferido": "manha",
            "energia_tipica": "media",
            "consentimento": "on",
        },
        follow_redirects=False,
    )

    corpo = cliente.get("/rotina").text

    assert "16" in corpo
    assert "por semana" in corpo

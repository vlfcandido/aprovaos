# O que é: testes de contrato de `GET /painel`, `GET /painel/semana` e do alerta de atraso
# (RF-10) reaproveitado em `GET /hoje` — fatia 10, §8. Quando ler: ao mexer na tela do painel.
from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
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
from aprovaos.dados.repositorio_perfil import salvar_perfil
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup
from aprovaos.dominio.rotina import DIAS_SEMANA, DadosRotina


def _entrar(cliente: TestClient, email: str) -> None:
    resposta = cliente.post("/cadastro", data={"email": email, "senha": "12345678"})
    assert resposta.status_code in (200, 303)


def _usuario_por_email(db: Session, email: str) -> Usuario:
    return db.query(Usuario).filter_by(email=email).one()


def _cenario_com_edital(
    db: Session, email: str, *, quantidade_topicos: int = 1, data_alvo: date | None = None
) -> tuple[UUID, list[Topico]]:
    """Cadastra (via `cliente`, feito por quem chama) e monta um edital sem DNA para o tenant."""
    usuario = _usuario_por_email(db, email)
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
    return edital.id, topicos


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
    enunciado = f"Enunciado rota-painel {numero} sobre {topico.nome}."
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
    return db.query(Questao).filter_by(hash_dedup=curada.hash_dedup).one()


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
# GET /painel
# ---------------------------------------------------------------------------


def test_painel_exige_login(cliente: TestClient) -> None:
    resposta = cliente.get("/painel", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_painel_sem_concurso_mostra_caminho_para_rotina(cliente: TestClient) -> None:
    _entrar(cliente, "sem-concurso@exemplo.com")

    resposta = cliente.get("/painel")

    assert resposta.status_code == 200
    assert "/rotina" in resposta.text
    assert "/editais/subir" in resposta.text


def test_painel_sem_data_alvo_mostra_lacuna_em_vez_de_curva(
    cliente: TestClient, db: Session
) -> None:
    email = "sem-data-alvo@exemplo.com"
    _entrar(cliente, email)
    _cenario_com_edital(db, email)

    resposta = cliente.get("/painel")

    assert resposta.status_code == 200
    assert "ainda não informou a data da prova" in resposta.text
    assert "Padrões de erro" in resposta.text
    assert "Previsão de nota" in resposta.text


def test_painel_com_dado_mostra_a_faixa_por_extenso(cliente: TestClient, db: Session) -> None:
    """Com uma resposta só a faixa é enorme, e a tela lidera pela incerteza — mas a faixa e a
    confiança continuam escritas, que é a regra de produto (visão §4)."""
    email = "com-dado@exemplo.com"
    _entrar(cliente, email)
    edital_id, (topico,) = _cenario_com_edital(db, email)
    usuario = _usuario_por_email(db, email)
    questao = _gravar_questao(db, topico, email, 1)
    _resposta(db, usuario, questao, agora_utc())
    db.commit()

    resposta = cliente.get("/painel")

    assert resposta.status_code == 200
    assert "Ainda não dá para prever sua nota" in resposta.text
    assert "em qualquer lugar entre" in resposta.text
    assert "confiança" in resposta.text
    assert edital_id  # o edital existe; a asserção acima é o que importa nesta tela


def test_painel_nao_fala_a_lingua_de_quem_construiu_o_calculo(
    cliente: TestClient, db: Session
) -> None:
    """O dono leu o painel e disse "ruim de ler": "banda de 66,1 p.p.", "78 % do peso da prova
    medido", "bandas que não se sobrepõem à média geral" são termos de quem fez a conta."""
    email = "sem-jargao@exemplo.com"
    _entrar(cliente, email)
    _, (topico,) = _cenario_com_edital(db, email)
    usuario = _usuario_por_email(db, email)
    questao = _gravar_questao(db, topico, email, 1)
    _resposta(db, usuario, questao, agora_utc())
    db.commit()

    resposta = cliente.get("/painel")

    assert resposta.status_code == 200
    for jargao in ("p.p.", "suporte estatístico", "se sobrepõem", "Wilson"):
        assert jargao not in resposta.text, f"{jargao!r} continua na tela"


def test_padroes_vazio_diz_quantas_respostas_faltam(cliente: TestClient, db: Session) -> None:
    """Estado vazio que ensina estatística não ajuda: diga o que falta para o primeiro padrão."""
    email = "faltam-respostas@exemplo.com"
    _entrar(cliente, email)
    _, (topico,) = _cenario_com_edital(db, email)
    usuario = _usuario_por_email(db, email)
    questao = _gravar_questao(db, topico, email, 1)
    _resposta(db, usuario, questao, agora_utc())
    db.commit()

    resposta = cliente.get("/painel")

    assert resposta.status_code == 200
    # 8 respostas no mesmo grupo (MINIMO_RESPOSTAS_PADRAO) menos a 1 já dada.
    assert "Faltam 7 respostas" in resposta.text
    assert "Responder o plano de hoje" in resposta.text


def test_previsao_declara_a_materia_em_branco_como_proximo_passo(
    cliente: TestClient, db: Session
) -> None:
    """Confiança sem caminho é só um rótulo ruim: o bloco diz o que sobe a confiança."""
    email = "o-que-falta@exemplo.com"
    _entrar(cliente, email)
    _, (topico,) = _cenario_com_edital(db, email)
    usuario = _usuario_por_email(db, email)
    questao = _gravar_questao(db, topico, email, 1)
    _resposta(db, usuario, questao, agora_utc())
    db.commit()

    resposta = cliente.get("/painel")

    assert resposta.status_code == 200
    assert "Responda mais questões" in resposta.text


def test_painel_nao_vaza_codigo_interno_de_pendencia(cliente: TestClient, db: Session) -> None:
    """Defeito reproduzido no navegador (fatia 14): `(P-39)`/`(P-17/P-39)` apareciam na tela da
    aluna. O fato continua dito — só sem o código interno."""
    email = "sem-codigo@exemplo.com"
    _entrar(cliente, email)
    _, (topico,) = _cenario_com_edital(db, email)
    usuario = _usuario_por_email(db, email)
    questao = _gravar_questao(db, topico, email, 1)
    _resposta(db, usuario, questao, agora_utc())
    db.commit()

    resposta = cliente.get("/painel")

    assert resposta.status_code == 200
    assert "P-39" not in resposta.text
    assert "P-17" not in resposta.text
    assert "peso está uniforme" in resposta.text


def test_previsao_usa_intervalo_da_biblioteca_sem_parecer_slider(
    cliente: TestClient, db: Session
) -> None:
    """Defeito reproduzido no navegador (fatia 14): a banda da previsão era um `<svg>` com um
    `<circle>` no meio de uma barra — lida como um controle arrastável. Agora é `.intervalo`
    (faixa + traço, sem alça)."""
    email = "sem-slider@exemplo.com"
    _entrar(cliente, email)
    _, (topico,) = _cenario_com_edital(db, email)
    usuario = _usuario_por_email(db, email)
    questao = _gravar_questao(db, topico, email, 1)
    _resposta(db, usuario, questao, agora_utc())
    db.commit()

    resposta = cliente.get("/painel")

    assert resposta.status_code == 200
    # A asserção olha o conteúdo da tela, não a página inteira: desde 23/09/2026 a barra lateral
    # tem ícones em SVG (`_icones.html`), então "nenhum `<svg>` no HTML" deixou de ser uma
    # propriedade verdadeira — e nunca foi a que este teste queria provar.
    conteudo = resposta.text.split("<main", 1)[1]
    assert 'class="intervalo"' in conteudo
    assert "<circle" not in conteudo
    # sem data-alvo (`_cenario_com_edital` não define uma), a curva também cai no estado vazio —
    # o conteúdo fica sem nenhum `<svg>` neste cenário.
    assert "<svg" not in conteudo


def test_previsao_nao_duplica_a_materia_sem_dado(cliente: TestClient, db: Session) -> None:
    """Defeito reproduzido no navegador (fatia 14): a matéria sem dado aparecia duas vezes, em
    parágrafos seguidos (uma vez dentro do "porquê", outra num parágrafo à parte)."""
    email = "sem-duplicata@exemplo.com"
    _entrar(cliente, email)
    usuario = _usuario_por_email(db, email)
    concurso = Concurso(
        tenant_id=usuario.tenant_id, orgao="TJ-PR", cargo="Técnico", banca="cebraspe"
    )
    documento_edital = Documento(
        tipo="edital",
        hash="edital-sem-duplicata".ljust(64, "0")[:64],
        caminho="edital.pdf",
        baixado_em=agora_utc(),
        metadados={},
    )
    db.add_all([concurso, documento_edital])
    db.flush()
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add(edital)
    db.flush()

    com_dado = Topico(materia="Direito Administrativo", nome="Poderes", slug="sd-a")
    sem_dado = Topico(materia="Português Instrumental", nome="Crase", slug="sd-b")
    db.add_all([com_dado, sem_dado])
    db.flush()
    db.add_all(
        [
            TopicoEdital(edital=edital, topico=com_dado, ordem=1, texto_original="1."),
            TopicoEdital(edital=edital, topico=sem_dado, ordem=2, texto_original="2."),
        ]
    )
    horas = dict.fromkeys(DIAS_SEMANA, 1.0)
    salvar_perfil(
        db,
        usuario,
        DadosRotina(
            horas_por_dia_semana=horas,
            horario_preferido="manha",
            energia_tipica="media",
            data_alvo=None,
            concurso_principal_id=concurso.id,
        ),
    )
    db.commit()

    questao = _gravar_questao(db, com_dado, email, 1)
    _resposta(db, usuario, questao, agora_utc())
    db.commit()

    resposta = cliente.get("/painel")

    assert resposta.status_code == 200
    assert resposta.text.count("Português Instrumental") == 1


def test_painel_questao_despublicada_nao_conta_no_numero(cliente: TestClient, db: Session) -> None:
    email = "p34-painel@exemplo.com"
    _entrar(cliente, email)
    _, (topico,) = _cenario_com_edital(db, email)
    usuario = _usuario_por_email(db, email)
    questao = _gravar_questao(db, topico, email, 1)
    agora = agora_utc()
    for _ in range(3):  # MINIMO_PARA_DOMINADO
        _resposta(db, usuario, questao, agora)
    db.commit()

    antes = cliente.get("/painel")
    assert "1 de 1 tópicos dominados hoje" in antes.text

    questao.despublicada_em = agora_utc()
    db.commit()

    depois = cliente.get("/painel")
    assert "0 de 1 tópicos dominados hoje" in depois.text


# ---------------------------------------------------------------------------
# GET /painel/semana
# ---------------------------------------------------------------------------


def test_painel_semana_exige_login(cliente: TestClient) -> None:
    resposta = cliente.get("/painel/semana", follow_redirects=False)

    assert resposta.status_code == 303


def test_painel_semana_sem_estudo_registrado(cliente: TestClient, db: Session) -> None:
    email = "semana-vazia@exemplo.com"
    _entrar(cliente, email)
    _cenario_com_edital(db, email)

    resposta = cliente.get("/painel/semana")

    assert resposta.status_code == 200
    assert "Semana sem estudo registrado" in resposta.text


# ---------------------------------------------------------------------------
# Alerta (RF-10) em /hoje
# ---------------------------------------------------------------------------


def test_alerta_de_atraso_aparece_no_hoje(cliente: TestClient, db: Session) -> None:
    email = "alerta-hoje@exemplo.com"
    _entrar(cliente, email)
    hoje = agora_utc().date()
    _cenario_com_edital(db, email, quantidade_topicos=2, data_alvo=hoje + timedelta(days=2))

    resposta = cliente.get("/hoje")

    assert resposta.status_code == 200
    assert "Você está abaixo da curva necessária" in resposta.text


def test_sem_alerta_quando_em_dia(cliente: TestClient, db: Session) -> None:
    email = "sem-alerta@exemplo.com"
    _entrar(cliente, email)
    _cenario_com_edital(db, email)  # sem data_alvo: nunca há alerta

    resposta = cliente.get("/hoje")

    assert resposta.status_code == 200
    assert "Você está abaixo da curva necessária" not in resposta.text

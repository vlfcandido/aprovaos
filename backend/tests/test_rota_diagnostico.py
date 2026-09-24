# O que é: testes de contrato e de fluxo de `GET/POST /diagnostico` (fatia 7, F2.1) — sem login
# redireciona; sem concurso principal avisa sem quebrar; fluxo completo até uma matéria fechar;
# matéria sem questão nunca aparece como item; "insistir" funciona e respeita o teto de 30
# (escritos em 19/09/2026 — o cabeçalho já os prometia, mas não existiam; revisão independente).
# Quando ler: ao mexer em `api/diagnostico.py`.
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Concurso,
    Documento,
    Edital,
    Questao,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dados.repositorio_questao import proxima_questao, salvar_questoes
from aprovaos.dominio.diagnostico import MAXIMO_ITENS
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup

CADASTRO = {"email": "linda@exemplo.com", "senha": "12345678"}


@pytest.fixture
def logado(cliente: TestClient) -> TestClient:
    resposta = cliente.post("/cadastro", data=CADASTRO, follow_redirects=False)
    assert resposta.status_code == 303
    return cliente


def _tenant_id(db: Session) -> UUID:
    from aprovaos.dados.modelos import Usuario

    return db.scalars(select(Usuario).where(Usuario.email == CADASTRO["email"])).one().tenant_id


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _edital_com_topicos(db: Session, tenant_id: UUID) -> tuple[Edital, Topico, Topico]:
    com_questao = Topico(materia="Direito Administrativo", nome="Poderes", slug="diag-a")
    sem_questao = Topico(materia="Língua Portuguesa", nome="Crase", slug="diag-b")
    documento_edital = _documento(db, "edital-diagnostico")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PR", cargo="Técnico", banca="AOCP")
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add_all([com_questao, sem_questao, concurso, edital])
    db.flush()
    db.add_all(
        [
            TopicoEdital(edital=edital, topico=com_questao, ordem=1, texto_original="1. Poderes."),
            TopicoEdital(edital=edital, topico=sem_questao, ordem=2, texto_original="2. Crase."),
        ]
    )
    db.flush()
    return edital, com_questao, sem_questao


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
    enunciado = f"Enunciado {numero} sobre {topico.nome}."
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


def test_diagnostico_exige_login(cliente: TestClient) -> None:
    resposta = cliente.get("/diagnostico", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_diagnostico_sem_concurso_avisa_sem_quebrar(logado: TestClient) -> None:
    resposta = logado.get("/diagnostico")
    assert resposta.status_code == 200
    assert "concurso principal" in resposta.text.lower()


def test_diagnostico_sem_questao_finaliza_direto_sem_fingir_cobertura(
    logado: TestClient, db: Session
) -> None:
    """Nenhum tópico do edital tem questão publicável: finaliza em 0 itens, sem inventar dado."""
    tenant_id = _tenant_id(db)
    edital, _com_questao, _sem_questao = _edital_com_topicos(db, tenant_id)
    db.commit()

    resposta = logado.get("/diagnostico")
    assert resposta.status_code == 200
    assert "diagnóstico concluído" in resposta.text.lower()
    assert "parei em 0 itens" in resposta.text.lower()
    assert "sem questão suficiente na base" in resposta.text.lower()
    assert "sem questão na base" in resposta.text.lower()


def test_diagnostico_flui_ate_a_materia_fechar(logado: TestClient, db: Session) -> None:
    tenant_id = _tenant_id(db)
    edital, com_questao, _sem_questao = _edital_com_topicos(db, tenant_id)
    documento_prova = _documento(db, "prova-diagnostico")
    salvar_questoes(
        db,
        [_questao(com_questao, documento_prova.id, n) for n in range(1, 6)],
    )
    db.commit()

    # Primeiro item: por que este item aparece, e não revela o gabarito.
    resposta = logado.get("/diagnostico")
    assert resposta.status_code == 200
    assert "por que este item" in resposta.text.lower()
    assert "Item <strong>1</strong>" in resposta.text
    assert "<strong>30</strong>" in resposta.text

    # Responde 3 itens com certeza e acerto: a margem em Direito Administrativo fecha
    # (peso 2*3=6, margem = 50/7 ≈ 7,1 ≤ 8) — e Língua Portuguesa nunca aparece (sem questão).
    from aprovaos.dados.modelos import Usuario
    from aprovaos.dados.repositorio_questao import proxima_questao

    usuario = db.scalars(select(Usuario).where(Usuario.email == CADASTRO["email"])).one()
    for _ in range(3):
        db.expire_all()
        pendente = proxima_questao(db, usuario.id, com_questao.id)
        assert pendente is not None
        resposta = logado.post(
            "/diagnostico",
            data={
                "resposta": "C",
                "questao_id": str(pendente.id),
                "topico_id": str(com_questao.id),
                "confianca": "certeza",
                "tempo_ms": "1000",
            },
        )
        assert resposta.status_code == 200
        assert "gabarito" in resposta.text.lower()

    resultado = logado.get("/diagnostico")
    assert resultado.status_code == 200
    assert "diagnóstico concluído" in resultado.text.lower()
    assert "Língua Portuguesa" in resultado.text
    assert "sem questão na base" in resultado.text
    assert "Insistir" in resultado.text  # Direito Administrativo fechou


def test_diagnostico_mostra_barra_de_progresso_e_estimativa_apos_responder(
    logado: TestClient, db: Session
) -> None:
    """Porte da fatia 14: barra de progresso (`.bar`) desde o primeiro item, e a "Estimativa até
    agora" (uma matéria por linha) assim que alguma matéria já tem resposta."""
    tenant_id = _tenant_id(db)
    edital, com_questao, _sem_questao = _edital_com_topicos(db, tenant_id)
    documento_prova = _documento(db, "prova-estimativa")
    salvar_questoes(db, [_questao(com_questao, documento_prova.id, n) for n in range(1, 6)])
    db.commit()

    primeiro = logado.get("/diagnostico")
    assert primeiro.status_code == 200
    assert 'class="bar"' in primeiro.text
    assert 'role="progressbar"' in primeiro.text
    # ainda sem nenhuma resposta: a matéria ainda não aparece na estimativa.
    assert "Estimativa até agora" not in primeiro.text

    usuario = db.scalars(select(Usuario).where(Usuario.email == CADASTRO["email"])).one()
    pendente = proxima_questao(db, usuario.id, com_questao.id)
    assert pendente is not None
    resposta_post = logado.post(
        "/diagnostico",
        data={
            "resposta": "C",
            "questao_id": str(pendente.id),
            "topico_id": str(com_questao.id),
            "confianca": "certeza",
            "tempo_ms": "1000",
        },
    )
    assert resposta_post.status_code == 200

    segundo = logado.get("/diagnostico")
    assert segundo.status_code == 200
    assert "Estimativa até agora" in segundo.text
    assert com_questao.materia in segundo.text


def test_post_diagnostico_sem_confianca_400(logado: TestClient, db: Session) -> None:
    tenant_id = _tenant_id(db)
    edital, com_questao, _ = _edital_com_topicos(db, tenant_id)
    documento_prova = _documento(db, "prova-2")
    salvar_questoes(db, [_questao(com_questao, documento_prova.id, 1)])
    db.commit()
    questao = db.scalars(select(Questao)).first()
    assert questao is not None

    resposta = logado.post(
        "/diagnostico",
        data={
            "resposta": "C",
            "questao_id": str(questao.id),
            "topico_id": str(com_questao.id),
            "tempo_ms": "500",
        },
    )
    assert resposta.status_code == 400
    corpo = resposta.json()
    assert corpo["codigo"] == "dados_invalidos"
    assert set(corpo) == {"codigo", "mensagem", "acao"}


def test_post_diagnostico_topico_fora_do_edital_404(logado: TestClient, db: Session) -> None:
    tenant_id = _tenant_id(db)
    _edital, com_questao, _ = _edital_com_topicos(db, tenant_id)
    db.commit()
    from uuid import uuid4

    resposta = logado.post(
        "/diagnostico",
        data={
            "resposta": "C",
            "questao_id": str(uuid4()),
            "topico_id": str(uuid4()),
            "confianca": "certeza",
        },
    )
    assert resposta.status_code == 404
    corpo = resposta.json()
    assert corpo["codigo"] == "nao_encontrado"


def _responder_proxima(
    cliente: TestClient, db: Session, usuario_id: UUID, topico: Topico, *, insistir: bool = False
) -> None:
    """Responde (certeza/acerto) o próximo item pendente do tópico — via GET+POST, como a tela
    faz de verdade, sem pular a rota."""
    params = {"insistir": topico.materia} if insistir else None
    resposta_get = cliente.get("/diagnostico", params=params)
    assert resposta_get.status_code == 200

    db.expire_all()
    pendente = proxima_questao(db, usuario_id, topico.id)
    assert pendente is not None
    resposta_post = cliente.post(
        "/diagnostico",
        data={
            "resposta": "C",
            "questao_id": str(pendente.id),
            "topico_id": str(topico.id),
            "confianca": "certeza",
            "tempo_ms": "1000",
        },
    )
    assert resposta_post.status_code == 200


def test_diagnostico_insistir_funciona_na_materia_ja_fechada(
    logado: TestClient, db: Session
) -> None:
    """ "Insistir" (o "discordar" do plano §6): depois que Direito Administrativo fecha (3 itens
    com certeza e acerto, mesma conta de `test_diagnostico_flui_ate_a_materia_fechar`), o
    diagnóstico normal termina — mas `?insistir=<matéria>` libera mais um item nela, com o
    motivo dizendo que foi a aluna quem pediu."""
    tenant_id = _tenant_id(db)
    edital, com_questao, _sem_questao = _edital_com_topicos(db, tenant_id)
    documento_prova = _documento(db, "prova-insistir")
    salvar_questoes(
        db, [_questao(com_questao, documento_prova.id, n) for n in range(1, 6)]
    )  # 5 questões: 3 fecham a margem, a 4ª é a do "insistir"
    db.commit()
    usuario = db.scalars(select(Usuario).where(Usuario.email == CADASTRO["email"])).one()

    for _ in range(3):
        _responder_proxima(logado, db, usuario.id, com_questao)

    concluido_sem_insistir = logado.get("/diagnostico")
    assert concluido_sem_insistir.status_code == 200
    assert "diagnóstico concluído" in concluido_sem_insistir.text.lower()
    assert "parei em 3 itens" in concluido_sem_insistir.text.lower()

    resposta_insistir = logado.get("/diagnostico", params={"insistir": com_questao.materia})
    assert resposta_insistir.status_code == 200
    assert "por que este item" in resposta_insistir.text.lower()
    assert "você pediu para continuar" in resposta_insistir.text.lower()
    assert com_questao.materia in resposta_insistir.text

    _responder_proxima(logado, db, usuario.id, com_questao, insistir=True)

    resultado_final = logado.get("/diagnostico")
    assert resultado_final.status_code == 200
    assert "diagnóstico concluído" in resultado_final.text.lower()
    assert "parei em 4 itens" in resultado_final.text.lower()


def test_diagnostico_respeita_o_teto_de_30_mesmo_insistindo(
    logado: TestClient, db: Session
) -> None:
    """O teto (`MAXIMO_ITENS`, F2.1) é duro: mesmo pedindo para insistir, o diagnóstico não
    passa de 30 itens — a rota decide pelo `total_itens` antes de olhar `insistir` (`api
    /diagnostico.py::diagnostico`, `if total_itens < MAXIMO_ITENS`)."""
    tenant_id = _tenant_id(db)
    edital, com_questao, _sem_questao = _edital_com_topicos(db, tenant_id)
    documento_prova = _documento(db, "prova-teto")
    # MAXIMO_ITENS (30) questões — todas do mesmo tópico, para poder insistir o tempo todo (a
    # margem fecha bem antes dos 30, então sem "insistir" o diagnóstico pararia bem antes).
    salvar_questoes(
        db, [_questao(com_questao, documento_prova.id, n) for n in range(1, MAXIMO_ITENS + 1)]
    )
    db.commit()
    usuario = db.scalars(select(Usuario).where(Usuario.email == CADASTRO["email"])).one()

    for _ in range(MAXIMO_ITENS):
        _responder_proxima(logado, db, usuario.id, com_questao, insistir=True)

    resultado = logado.get("/diagnostico", params={"insistir": com_questao.materia})
    assert resultado.status_code == 200
    assert "diagnóstico concluído" in resultado.text.lower()
    assert f"parei em {MAXIMO_ITENS} itens" in resultado.text.lower()
    assert f"atingi o máximo de {MAXIMO_ITENS}" in resultado.text.lower()


# --- o resultado enxuto (passada visual de 23/09/2026) -------------------------------------
# Medida na tela da piloto: 1.777 palavras, 101 linhas de tópico, das quais 63 diziam "sem
# questão na base" e 19 "sem dado ainda" — 81% do resultado falava de lacuna nossa, não dela.
# Decisão do dono: a lista tópico a tópico sai (ela já tem casa no edital verticalizado, que
# ganha um link), o resultado passa a ser 3 matérias mais fortes + 3 mais fracas + um botão
# "começar por aqui", e a lacuna vira UMA linha com a contagem.


def test_resultado_nao_lista_os_topicos_um_a_um(logado: TestClient, db: Session) -> None:
    """A lista de tópicos sai do resultado e vira link para o edital verticalizado."""
    tenant_id = _tenant_id(db)
    edital, com_questao, sem_questao = _edital_com_topicos(db, tenant_id)
    db.commit()

    corpo = logado.get("/diagnostico").text
    assert "Estado por tópico" not in corpo
    # os nomes dos tópicos (não das matérias) não aparecem mais um a um
    assert com_questao.nome not in corpo
    assert sem_questao.nome not in corpo
    assert f'href="/concurso/{edital.concurso_id}"' in corpo


def test_resultado_diz_a_lacuna_em_uma_linha_so(logado: TestClient, db: Session) -> None:
    """ "1 dos 2 tópicos ainda não tem questão" — uma frase, não uma linha por tópico."""
    tenant_id = _tenant_id(db)
    _edital, _com_questao, _sem_questao = _edital_com_topicos(db, tenant_id)
    db.commit()

    corpo = logado.get("/diagnostico").text
    assert "de 2 tópicos do seu edital ainda não têm questão" in corpo
    assert corpo.count("ainda não têm questão") == 1


def test_resultado_mostra_mais_fortes_mais_fracas_e_o_botao_de_comecar(
    logado: TestClient, db: Session
) -> None:
    """3 mais fortes, 3 mais fracas e um caminho único para continuar."""
    tenant_id = _tenant_id(db)
    _edital, com_questao, _sem_questao = _edital_com_topicos(db, tenant_id)
    documento_prova = _documento(db, "prova-resultado-enxuto")
    salvar_questoes(db, [_questao(com_questao, documento_prova.id, n) for n in range(1, 6)])
    db.commit()

    usuario = db.scalars(select(Usuario).where(Usuario.email == CADASTRO["email"])).one()
    for _ in range(3):
        _responder_proxima(logado, db, usuario.id, com_questao)

    corpo = logado.get("/diagnostico").text
    assert "Onde você está mais forte" in corpo
    assert "Por onde começar" in corpo
    assert "Começar por aqui" in corpo
    assert com_questao.materia in corpo

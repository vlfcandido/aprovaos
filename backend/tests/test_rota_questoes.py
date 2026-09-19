# O que é: testes do passo 13 da V3 — rotas HTML de resolver questão (`GET`/`POST
# /topico/{slug}/questoes`) e de reportar erro (`POST /questoes/{id}/reportar`): isolamento por
# tenant no slug (o tópico é vocabulário global), certeza/dúvida obrigatória antes de responder,
# gabarito nunca no HTML antes da resposta, origem completa no resultado e a premissa H (reporte
# esconde a questão só para quem reportou). O passo 3 da V3b acrescenta a tela de múltipla
# escolha A–E (`_criar_questao_multipla_escolha`/`_alternativas_padrao`): mesmas garantias, mais
# as cinco alternativas visíveis e nenhuma marca de qual é a correta antes de responder. A V4
# acrescenta: errar cria `cartao` (`origem="auto_erro"`), acertar não cria nada. Quando ler: ao
# mexer em `api/questoes.py` ou nos templates `questoes/*.html`.
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from aprovaos.api.questoes import _cargo_exibivel, _formatar_banca
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Alternativa,
    Cartao,
    Concurso,
    Documento,
    Edital,
    EventoEstudo,
    Questao,
    ReporteErro,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dados.repositorio_citacao import buscar_ou_criar_dispositivo, registrar_citacao
from aprovaos.dados.repositorio_questao import salvar_questao_inedita, salvar_questoes
from aprovaos.dominio.questao import (
    AlternativaCurada,
    Origem,
    QuestaoCurada,
    RegraProva,
    hash_dedup,
)
from aprovaos.dominio.questao_inedita import QuestaoGerada

CADASTRO = {"email": "linda@exemplo.com", "senha": "12345678"}
OUTRA_CONTA = {"email": "outra@exemplo.com", "senha": "12345678"}
SLUG = "dir-adm-04-licitacoes-contratos"


@pytest.fixture
def logado(cliente: TestClient) -> TestClient:
    resposta = cliente.post("/cadastro", data=CADASTRO, follow_redirects=False)
    assert resposta.status_code == 303
    return cliente


def _usuario_por_email(db: Session, email: str) -> Usuario:
    return db.scalars(select(Usuario).where(Usuario.email == email)).one()


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _edital_com_topico(db: Session, tenant_id: UUID, slug: str) -> tuple[Edital, Topico]:
    topico = Topico(materia="DIREITO ADMINISTRATIVO", nome="Licitações e contratos", slug=slug)
    documento_edital = _documento(db, f"edital-{slug}")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PA", cargo="Analista", banca="cebraspe")
    edital = Edital(concurso=concurso, versao=1, documento=documento_edital)
    db.add_all([topico, concurso, edital])
    db.flush()
    db.add(TopicoEdital(edital=edital, topico=topico, ordem=1, texto_original="4. Licitações..."))
    db.flush()
    return edital, topico


TEXTO_APOIO_CURTO = "Texto de apoio compartilhado com outros itens."


def _questao_curada(
    topico_slug: str,
    documento_id: UUID,
    *,
    numero_item: int = 58,
    gabarito: str = "C",
    publicavel: bool = True,
    texto_apoio: str | None = TEXTO_APOIO_CURTO,
    tipo_item: str = "certo_errado",
    comando: str | None = "Julgue o item a seguir.",
    alternativas: list[AlternativaCurada] | None = None,
) -> QuestaoCurada:
    origem = Origem(
        banca="cebraspe",
        orgao="TJ-PA",
        cargo="Analista Judiciário — Direito",
        ano=2025,
        numero_item=numero_item,
        tipo_caderno="TIPO 1",
        url_prova="https://cdn.cebraspe.org.br/prova.pdf",
        documento_id=str(documento_id),
    )
    return QuestaoCurada(
        banca="cebraspe",
        tipo_item=tipo_item,
        numero_item=numero_item,
        comando=comando,
        texto_apoio=texto_apoio,
        texto_apoio_itens=[numero_item] if texto_apoio else [],
        enunciado="O pregão eletrônico dispensa a fase de habilitação prévia.",
        alternativas=alternativas,
        gabarito_preliminar=None,
        gabarito=gabarito,
        gabarito_status="definitivo",
        publicavel=publicavel,
        motivo_nao_publicavel=None if publicavel else "tópico não identificado",
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=topico_slug,
        topico_confianca="alta",
        topico_evidencia="menciona pregão e licitação",
        origem=origem,
        hash_dedup=hash_dedup(f"{numero_item}-{gabarito}-{topico_slug}-{tipo_item}"),
    )


#: Os textos das cinco alternativas de fixture — nunca iguais entre si, para nenhum teste
#: confundir "apareceu o texto certo" com "apareceu algum texto".
_TEXTOS_ALTERNATIVAS = {
    "A": "Texto da alternativa A.",
    "B": "Texto da alternativa B.",
    "C": "Texto da alternativa C.",
    "D": "Texto da alternativa D.",
    "E": "Texto da alternativa E.",
}


def _alternativas_padrao(gabarito: str) -> list[AlternativaCurada]:
    """As cinco `AlternativaCurada` A–E, com `correta=True` só na letra do `gabarito`."""
    return [
        AlternativaCurada(letra=letra, texto=texto, correta=(letra == gabarito))
        for letra, texto in _TEXTOS_ALTERNATIVAS.items()
    ]


def _criar_questao(db: Session, topico: Topico, documento_id: UUID, **kwargs: Any) -> Questao:
    curada = _questao_curada(topico.slug, documento_id, **kwargs)
    salvar_questoes(db, [curada])
    db.commit()
    return db.scalars(select(Questao).where(Questao.hash_dedup == curada.hash_dedup)).one()


def _criar_questao_multipla_escolha(
    db: Session,
    topico: Topico,
    documento_id: UUID,
    *,
    gabarito: str = "B",
    numero_item: int = 21,
    publicavel: bool = True,
) -> Questao:
    """Cria uma `Questao` `tipo_item="multipla_escolha"` com as cinco alternativas gravadas."""
    return _criar_questao(
        db,
        topico,
        documento_id,
        numero_item=numero_item,
        gabarito=gabarito,
        publicavel=publicavel,
        tipo_item="multipla_escolha",
        comando=None,
        texto_apoio=None,
        alternativas=_alternativas_padrao(gabarito),
    )


def _ligar_dispositivo(
    db: Session, questao: Questao, *, citacao_canonica: str, texto: str, posicao: int = 1
) -> None:
    """Cria (ou reaproveita) um `DispositivoLegal` e liga à `questao` — fixture de justificativa."""
    dispositivo = buscar_ou_criar_dispositivo(
        db,
        citacao_canonica=citacao_canonica,
        norma="lei-8429-1992",
        artigo="1",
        inciso=None,
        paragrafo=None,
        texto=texto,
        vigente=True,
        fonte_url="https://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
    )
    registrar_citacao(
        db,
        conteudo_tipo="questao",
        conteudo_id=questao.id,
        dispositivo_id=dispositivo.id,
        posicao=posicao,
    )
    db.flush()


def test_get_topico_exige_login(cliente: TestClient) -> None:
    resposta = cliente.get(f"/topico/{SLUG}/questoes", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_get_topico_de_outro_tenant_404(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-1")
    _criar_questao(db, topico, documento.id)

    logado.cookies.clear()
    resposta_cadastro = logado.post("/cadastro", data=OUTRA_CONTA, follow_redirects=False)
    assert resposta_cadastro.status_code == 303

    resposta = logado.get(f"/topico/{topico.slug}/questoes")
    assert resposta.status_code == 404
    corpo = resposta.json()
    assert corpo["codigo"] == "nao_encontrado"
    assert set(corpo) == {"codigo", "mensagem", "acao"}


def test_get_mostra_questao_com_origem(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-2")
    _criar_questao(db, topico, documento.id)

    resposta = logado.get(f"/topico/{topico.slug}/questoes")
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "Julgue o item a seguir." in corpo
    assert "Texto de apoio compartilhado com outros itens." in corpo
    assert "O pregão eletrônico dispensa a fase de habilitação prévia." in corpo
    assert "TJ-PA" in corpo
    assert "Analista Judiciário — Direito" in corpo
    assert "2025" in corpo
    assert "item 58" in corpo
    assert "TIPO 1" in corpo
    assert 'href="https://cdn.cebraspe.org.br/prova.pdf"' in corpo
    assert "Gabarito" not in corpo


def test_apoio_curto_nao_fica_recolhido(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-2b")
    _criar_questao(db, topico, documento.id, texto_apoio=TEXTO_APOIO_CURTO)

    corpo = logado.get(f"/topico/{topico.slug}/questoes").text
    # o texto de apoio curto não fica recolhido — só o "reportar erro" usa `<details>` agora
    # (fatia 14: some atrás de um link discreto, não é mais um `<textarea>` sempre aberto).
    assert "<summary>ver texto de apoio</summary>" not in corpo
    assert TEXTO_APOIO_CURTO in corpo


def test_apoio_longo_fica_recolhido(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-2c")
    texto_longo = "Lei nº 14.133/2021, art. 1º. " * 25  # bem mais que 600 caracteres
    assert len(texto_longo) > 600
    _criar_questao(db, topico, documento.id, texto_apoio=texto_longo)

    corpo = logado.get(f"/topico/{topico.slug}/questoes").text
    assert "<details" in corpo
    assert "<summary>ver texto de apoio</summary>" in corpo
    assert texto_longo in corpo


def test_post_resposta_sem_confianca_reexibe_a_questao_com_aviso(
    logado: TestClient, db: Session
) -> None:
    """Defeito nº 1 do porte visual (fatia 14 §2.1): antes, isto era um 400 — e um 400 aqui é o
    htmx engolindo o erro em silêncio (não troca o DOM em resposta de erro), exatamente o que fez
    o dono dizer "não vi como responder": clicar numa alternativa sem marcar certeza/dúvida antes
    não fazia nada visível. Agora é 200, com a mesma questão de volta e o aviso — nunca silencioso,
    com ou sem JS.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-3")
    questao = _criar_questao(db, topico, documento.id)

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "certeza ou dúvida" in corpo.lower()
    assert 'role="alert"' in corpo
    # a mesma questão continua ali, pronta para tentar de novo — nunca some da tela.
    assert 'name="resposta" value="C"' in corpo
    assert 'name="questao_id" value="' + str(questao.id) in corpo

    eventos = list(db.scalars(select(EventoEstudo)).all())
    assert eventos == []


def test_post_resposta_sem_confianca_com_htmx_tambem_reexibe(
    logado: TestClient, db: Session
) -> None:
    """Mesmo teste do htmx: com `HX-Request: true`, o htmx só troca o DOM em respostas 2xx — por
    isso o 200 acima é o que garante que a aluna vê o aviso, não um 4xx que ele descartaria.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-3b")
    questao = _criar_questao(db, topico, documento.id)

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "questao_id": str(questao.id)},
        headers={"HX-Request": "true"},
    )
    assert resposta.status_code == 200
    assert "certeza ou dúvida" in resposta.text.lower()

    eventos = list(db.scalars(select(EventoEstudo)).all())
    assert eventos == []


def test_post_resposta_grava_evento_e_devolve_fragmento(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-4")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    assert "Certo" in resposta.text

    eventos = list(db.scalars(select(EventoEstudo).where(EventoEstudo.tipo == "resposta")).all())
    assert len(eventos) == 1
    assert eventos[0].questao_id == questao.id
    assert eventos[0].acertou is True
    assert eventos[0].confianca_declarada == "certeza"


def test_post_resposta_certa_nao_cria_cartao(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-4-certa")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    assert list(db.scalars(select(Cartao)).all()) == []


def test_post_resposta_errada_cria_cartao_auto_erro(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-4-errada")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "E", "confianca": "duvida", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200

    cartoes = list(db.scalars(select(Cartao)).all())
    assert len(cartoes) == 1
    assert cartoes[0].questao_id == questao.id
    assert cartoes[0].usuario_id == dona.id
    assert cartoes[0].origem == "auto_erro"
    assert cartoes[0].topico_id == topico.id


def test_resultado_mostra_origem_completa_e_reportar(logado: TestClient, db: Session) -> None:
    """Decisão 4 do passo 14: a origem aparece no resultado, sempre — e o botão de reportar
    continua disponível ali, já que o fragmento substituiu o resto de `#questao`.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-4b")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "Cebraspe" in corpo  # nome próprio, nunca o identificador cru "cebraspe" (fatia 14)
    assert "TJ-PA" in corpo
    assert "Analista Judiciário — Direito" in corpo
    assert "2025" in corpo
    assert "item 58" in corpo
    assert 'href="https://cdn.cebraspe.org.br/prova.pdf"' in corpo
    assert f'action="/questoes/{questao.id}/reportar"' in corpo


def test_topico_tela_referencia_atalhos_de_teclado(logado: TestClient, db: Session) -> None:
    """Os botões grandes e o link "próxima" carregam os `data-atalho` que a ilha de JS usa
    (ADR-0019); sem o script, eles continuam clicáveis normalmente (decisão 5 do passo 14).
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-4c")
    _criar_questao(db, topico, documento.id)

    corpo = logado.get(f"/topico/{topico.slug}/questoes").text
    assert '<script src="/static/js/atalhos-estudo.js" defer></script>' in corpo
    assert '<script src="/static/js/confianca-questao.js" defer></script>' in corpo
    assert 'data-atalho="certo"' in corpo
    assert 'data-atalho="errado"' in corpo
    assert 'id="questao" aria-live="polite"' in corpo


def test_post_resposta_questao_de_outro_topico_erro(logado: TestClient, db: Session) -> None:
    """`questao_id` de uma questão de outro tópico não pode ser aceito — sem isso, um `id`
    adulterado no formulário gravaria a resposta contra uma questão que a tela nunca mostrou.
    A validação é a mesma de sempre; a entrega é 200 + fragmento (não 404), porque um 4xx aqui
    vira JSON cru fora do htmx e não faz swap nenhum dentro dele.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    _edital_b, topico_b = _edital_com_topico(db, dona.tenant_id, "dir-adm-05-contratos")
    documento = _documento(db, "prova-6")
    _criar_questao(db, topico, documento.id)
    questao_de_outro_topico = _criar_questao(db, topico_b, documento.id, numero_item=59)

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={
            "resposta": "C",
            "confianca": "certeza",
            "questao_id": str(questao_de_outro_topico.id),
        },
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "não está mais disponível" in corpo
    assert f'href="/topico/{topico.slug}/questoes"' in corpo

    eventos = list(db.scalars(select(EventoEstudo)).all())
    assert eventos == []


def test_post_resposta_questao_ja_respondida_erro(logado: TestClient, db: Session) -> None:
    """`questao_id` de uma questão que este usuário já respondeu não pode gravar de novo —
    `evento_estudo` é append-only e é matéria-prima do FSRS, um evento errado não tem conserto.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-7")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")

    primeira = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert primeira.status_code == 200

    segunda = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "E", "confianca": "duvida", "questao_id": str(questao.id)},
    )
    assert segunda.status_code == 200
    assert "não está mais disponível" in segunda.text

    eventos = list(db.scalars(select(EventoEstudo).where(EventoEstudo.tipo == "resposta")).all())
    assert len(eventos) == 1
    assert eventos[0].resposta == "C"


def test_post_resposta_invalida_400(logado: TestClient, db: Session) -> None:
    """`resposta` fora de `C`/`E` não pode gravar `EventoEstudo` nenhum — mesma postura da
    validação de `confianca`.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-8")
    questao = _criar_questao(db, topico, documento.id)

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "X", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 400
    corpo = resposta.json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "certo ou errado" in corpo["mensagem"].lower()
    assert set(corpo) == {"codigo", "mensagem", "acao"}

    eventos = list(db.scalars(select(EventoEstudo)).all())
    assert eventos == []


def test_post_reporte(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-5")
    questao = _criar_questao(db, topico, documento.id)

    resposta = logado.post(
        f"/questoes/{questao.id}/reportar", data={"motivo": "gabarito parece errado"}
    )
    assert resposta.status_code == 200

    reportes = list(db.scalars(select(ReporteErro)).all())
    assert len(reportes) == 1
    assert reportes[0].status == "aberto"
    assert reportes[0].conteudo_id == questao.id

    seguinte = logado.get(f"/topico/{topico.slug}/questoes")
    assert "Ainda não temos questões deste tópico." in seguinte.text


def test_post_reporte_sem_htmx_devolve_pagina_completa(logado: TestClient, db: Session) -> None:
    """Sem `HX-Request` (POST direto do formulário, sem JS), a confirmação do reporte é a página
    inteira — com a app-shell (barra lateral) — nunca um `<p>` solto sem navegação.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-5b")
    questao = _criar_questao(db, topico, documento.id)

    resposta = logado.post(
        f"/questoes/{questao.id}/reportar", data={"motivo": "gabarito parece errado"}
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "<!doctype html>" in corpo.lower()
    assert 'class="lateral"' in corpo
    assert "Obrigado" in corpo


def test_post_reporte_com_htmx_devolve_fragmento(logado: TestClient, db: Session) -> None:
    """Com `HX-Request: true`, a confirmação é só o fragmento — o que o htmx troca em `#questao`,
    sem repetir a app-shell inteira.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-5c")
    questao = _criar_questao(db, topico, documento.id)

    resposta = logado.post(
        f"/questoes/{questao.id}/reportar",
        data={"motivo": "gabarito parece errado"},
        headers={"HX-Request": "true"},
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "<!doctype html>" not in corpo.lower()
    assert "Obrigado" in corpo


def test_post_reporte_de_outro_tenant_404(logado: TestClient, db: Session) -> None:
    """A rota de reportar é a única sem checagem de tenant antes desta correção — sem ela,
    qualquer logado reportaria qualquer questão do pool global só sabendo o `id`.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-5d")
    questao = _criar_questao(db, topico, documento.id)

    logado.cookies.clear()
    resposta_cadastro = logado.post("/cadastro", data=OUTRA_CONTA, follow_redirects=False)
    assert resposta_cadastro.status_code == 303

    resposta = logado.post(
        f"/questoes/{questao.id}/reportar", data={"motivo": "gabarito parece errado"}
    )
    assert resposta.status_code == 404
    corpo = resposta.json()
    assert set(corpo) == {"codigo", "mensagem", "acao"}

    assert list(db.scalars(select(ReporteErro)).all()) == []


def test_topico_sem_questao(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital_com_topico(db, dona.tenant_id, SLUG)

    resposta = logado.get(f"/topico/{SLUG}/questoes")
    assert resposta.status_code == 200
    assert "Ainda não temos questões deste tópico." in resposta.text


def test_questao_despublicada_pelo_calibrador_some_da_tela(logado: TestClient, db: Session) -> None:
    """P-34 (`docs/PENDENCIAS.md`, fecha nesta fatia): uma questão com `despublicada_em`
    preenchido não aparece mais em `GET /topico/{slug}/questoes`, mesmo continuando `publicavel`.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "hash-p34")
    questao = _criar_questao(db, topico, documento.id)

    questao.despublicada_em = agora_utc()
    db.commit()

    resposta = logado.get(f"/topico/{SLUG}/questoes")
    assert resposta.status_code == 200
    assert "Ainda não temos questões deste tópico." in resposta.text


# ---- Porte visual (fatia 14 §2.2): origem legível e "questão N de M" ---------------------


def test_formatar_banca_conhecida_ganha_nome_proprio() -> None:
    assert _formatar_banca("cebraspe") == "Cebraspe"
    assert _formatar_banca("CEBRASPE") == "Cebraspe"
    assert _formatar_banca("fgv") == "FGV"


def test_formatar_banca_desconhecida_nao_e_reformatada() -> None:
    """Nunca `.title()`/`.capitalize()` cego: uma sigla como "AOCP" viraria "Aocp" — pior que não
    mexer. Bancas fora do mapa aparecem como vieram."""
    assert _formatar_banca("AOCP") == "AOCP"
    assert _formatar_banca("FCC") == "FCC"


def test_cargo_placeholder_interno_e_omitido() -> None:
    assert _cargo_exibivel("CARGO 9") is None
    assert _cargo_exibivel("cargo 19") is None


def test_cargo_de_verdade_nao_e_omitido() -> None:
    assert _cargo_exibivel("Analista Judiciário — Direito") == "Analista Judiciário — Direito"


def test_get_mostra_posicao_na_fila_e_avanca_apos_responder(
    logado: TestClient, db: Session
) -> None:
    """ "Questão N de M" (achado do porte visual, fatia 14 §2.2) — sem isso a aluna não sabia
    quanto faltava na lista de hoje.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-posicao")
    primeira = _criar_questao(db, topico, documento.id, numero_item=1)
    _criar_questao(db, topico, documento.id, numero_item=2)

    corpo_antes = logado.get(f"/topico/{topico.slug}/questoes").text
    assert 'Questão <b class="mono">1</b> de <b class="mono">2</b>' in corpo_antes

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(primeira.id)},
    )
    assert resposta.status_code == 200

    corpo_depois = logado.get(f"/topico/{topico.slug}/questoes").text
    assert 'Questão <b class="mono">2</b> de <b class="mono">2</b>' in corpo_depois


# ---- Passo 3 da V3b: tela de múltipla escolha A–E ----------------------------------------


def test_get_mostra_multipla_escolha_com_cinco_alternativas(
    logado: TestClient, db: Session
) -> None:
    """As cinco letras e os cinco textos aparecem; nada denuncia qual é a correta."""
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-me-1")
    _criar_questao_multipla_escolha(db, topico, documento.id, gabarito="D")

    resposta = logado.get(f"/topico/{topico.slug}/questoes")
    assert resposta.status_code == 200
    corpo = resposta.text
    for letra, texto in _TEXTOS_ALTERNATIVAS.items():
        assert f'value="{letra}"' in corpo
        assert texto in corpo
    assert "Gabarito" not in corpo
    assert "alternativa--correta" not in corpo
    assert "data-correta" not in corpo


def test_alternativas_tem_nome_acessivel_com_letra_e_texto(logado: TestClient, db: Session) -> None:
    """Defeito nº 1 do porte visual (fatia 14 §2.1): as cinco alternativas são `<button>` sem
    `aria-label` — um leitor de tela anunciava só "button". Cada uma agora carrega a letra e o
    texto no `aria-label`, então basta ouvir uma vez para saber o que ela responde.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-me-aria")
    _criar_questao_multipla_escolha(db, topico, documento.id, gabarito="A")

    corpo = logado.get(f"/topico/{topico.slug}/questoes").text
    for letra, texto in _TEXTOS_ALTERNATIVAS.items():
        assert f'aria-label="Responder {letra}: {texto}"' in corpo


def test_multipla_escolha_referencia_atalhos_a_e(logado: TestClient, db: Session) -> None:
    """Cada alternativa carrega o `data-atalho` correspondente à sua letra (A–E)."""
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-me-2")
    _criar_questao_multipla_escolha(db, topico, documento.id, gabarito="A")

    corpo = logado.get(f"/topico/{topico.slug}/questoes").text
    for letra in "abcde":
        assert f'data-atalho="resposta-{letra}"' in corpo


def test_post_resposta_multipla_escolha_grava_evento_com_letra(
    logado: TestClient, db: Session
) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-me-3")
    questao = _criar_questao_multipla_escolha(db, topico, documento.id, gabarito="D")

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "D", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    assert "Você acertou" in resposta.text

    eventos = list(db.scalars(select(EventoEstudo).where(EventoEstudo.tipo == "resposta")).all())
    assert len(eventos) == 1
    assert eventos[0].resposta == "D"
    assert eventos[0].acertou is True
    assert eventos[0].confianca_declarada == "certeza"


def test_multipla_escolha_resultado_marca_alternativas_sem_inventar_justificativa(
    logado: TestClient, db: Session
) -> None:
    """O resultado mostra a marcada e a correta; sem `justificativa` gravada, não inventa nada."""
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-me-4")
    questao = _criar_questao_multipla_escolha(db, topico, documento.id, gabarito="C")

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "A", "confianca": "duvida", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "Você errou" in corpo
    assert "alternativa--correta" in corpo
    assert "alternativa--marcada-errada" in corpo
    assert "Explicação do AprovaOS" not in corpo  # não inventa o selo sem justificativa gravada
    # honestidade é o produto (regra 11, fatia 14 §2.2): diz que ainda não há explicação, nunca
    # deixa a tela em silêncio depois de um "Você errou." seco.
    assert "Ainda não temos uma explicação escrita para este item" in corpo


def test_post_resposta_multipla_escolha_letra_invalida_400(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-me-5")
    questao = _criar_questao_multipla_escolha(db, topico, documento.id, gabarito="B")

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "F", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 400
    corpo = resposta.json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "alternativa" in corpo["mensagem"].lower()

    eventos = list(db.scalars(select(EventoEstudo)).all())
    assert eventos == []


def test_certo_errado_continua_sem_alternativas_de_multipla_escolha(
    logado: TestClient, db: Session
) -> None:
    """A tela de certo/errado não regride: continua com os dois botões grandes, sem a lista de
    alternativas — regressão do passo 3 da V3b.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-me-6")
    _criar_questao(db, topico, documento.id)

    corpo = logado.get(f"/topico/{topico.slug}/questoes").text
    assert 'class="alternativas"' not in corpo
    assert 'data-atalho="certo"' in corpo
    assert 'data-atalho="errado"' in corpo


# ---- Justificativa no resultado (defeito do ordinal corrigido + exibição na tela) --------


def test_resultado_certo_errado_mostra_justificativa_com_fonte_legal(
    logado: TestClient, db: Session
) -> None:
    """A justificativa aparece marcada como do AprovaOS, com os dois lados (certo/errado) e o
    trecho literal do dispositivo — nunca o texto cru com colchetes.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-just-1")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")
    _ligar_dispositivo(
        db,
        questao,
        citacao_canonica="Lei 8.429/1992 art. 1",
        texto="Art. 1º O sistema de responsabilização tutela a probidade na organização do Estado.",
    )
    questao.justificativa_certo = "É a redação literal do art. 1º. [Lei 8.429/1992 art. 1]"
    questao.justificativa_errado = "Confunde com outro dispositivo da lei. [Lei 8.429/1992 art. 1]"
    db.commit()

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "Explicação do AprovaOS" in corpo
    assert "Se marcou Certo" in corpo
    assert "Se marcou Errado" in corpo
    assert "É a redação literal do art. 1º." in corpo
    assert "Confunde com outro dispositivo da lei." in corpo
    assert "tutela a probidade na organização do Estado" in corpo
    assert "[Lei 8.429/1992 art. 1]" not in corpo


def test_resultado_certo_errado_sem_justificativa_diz_que_ainda_nao_existe(
    logado: TestClient, db: Session
) -> None:
    """Sem justificativa gravada (a maioria hoje), a tela não mostra rótulo nem tabela nenhuma —
    mas também não cai num "Você errou." seco e silencioso: diz que a explicação ainda não existe
    (honestidade é o produto, regra 11; achado do porte visual, fatia 14 §2.2). Nunca inventa o
    texto que falta.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-just-2")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "Explicação do AprovaOS" not in corpo
    assert "Se marcou Certo" not in corpo
    assert "Se marcou Errado" not in corpo
    assert "Ainda não temos uma explicação escrita para este item" in corpo


def test_resultado_justificativa_com_citacao_de_ordinal_diferente_ainda_casa_com_a_fonte(
    logado: TestClient, db: Session
) -> None:
    """O mesmo defeito do validador (ordinal do modelo x gravado) não pode se repetir na tela:
    a citação com "º" ainda tem de casar com o `DispositivoLegal` gravado sem ordinal.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-just-3")
    questao = _criar_questao(db, topico, documento.id, gabarito="C")
    _ligar_dispositivo(
        db,
        questao,
        citacao_canonica="Lei 8.429/1992 art. 1",
        texto="Texto literal do artigo primeiro da lei de improbidade.",
    )
    questao.justificativa_certo = "Frase apoiada na fonte. [Lei 8.429/1992 art. 1º]"
    questao.justificativa_errado = "Outra frase. [Lei 8.429/1992 art. 1º]"
    db.commit()

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "Texto literal do artigo primeiro da lei de improbidade." in corpo


def test_multipla_escolha_resultado_mostra_justificativa_das_cinco_alternativas(
    logado: TestClient, db: Session
) -> None:
    """As cinco alternativas mostram a própria justificativa — a da correta e a dos distratores,
    onde mora o aprendizado.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-me-just-1")
    questao = _criar_questao_multipla_escolha(db, topico, documento.id, gabarito="C")
    _ligar_dispositivo(
        db,
        questao,
        citacao_canonica="Lei 8.429/1992 art. 1",
        texto="Texto literal do artigo primeiro da lei de improbidade.",
    )
    alternativas = list(
        db.scalars(select(Alternativa).where(Alternativa.questao_id == questao.id)).all()
    )
    for alternativa in alternativas:
        alternativa.justificativa = (
            f"Explicação da alternativa {alternativa.letra}. [Lei 8.429/1992 art. 1]"
        )
    db.commit()

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "A", "confianca": "duvida", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    corpo = resposta.text
    assert corpo.count("Explicação do AprovaOS") == 1
    for letra in "ABCDE":
        assert f"Explicação da alternativa {letra}." in corpo
    assert "[Lei 8.429/1992 art. 1]" not in corpo


def test_multipla_escolha_sem_alternativa_correta_nao_quebra_tela(
    logado: TestClient, db: Session
) -> None:
    """Anomalia de dado (nenhuma `Alternativa.correta=True`, apesar de `Questao.gabarito`
    definido) não pode quebrar a tela — a correção usa sempre `Questao.gabarito`, nunca
    `Alternativa.correta`, para decidir o acerto.
    """
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-me-7")
    questao = _criar_questao_multipla_escolha(db, topico, documento.id, gabarito="B")
    db.execute(
        update(Alternativa).where(Alternativa.questao_id == questao.id).values(correta=False)
    )
    db.commit()

    resposta_get = logado.get(f"/topico/{topico.slug}/questoes")
    assert resposta_get.status_code == 200

    resposta_post = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "B", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta_post.status_code == 200
    assert "Você acertou" in resposta_post.text


def _criar_questao_inedita(db: Session, topico: Topico) -> Questao:
    item = QuestaoGerada(
        tipo_item="certo_errado",
        banca_alvo="cebraspe",
        comando="Julgue o item a seguir.",
        enunciado="O TCU aprecia as contas do Presidente da República mediante parecer prévio.",
        alternativas=None,
        gabarito="C",
        fontes=["F1"],
        trecho_que_decide="apreciar as contas prestadas anualmente",
        justificativa_certo="Se dissesse 'aprecia', estaria certo.",
        justificativa_errado="O TCU aprecia; quem julga é o Congresso.",
        mecanismo="literal",
        original_de_referencia="cebraspe 2024 tce-xx item 57",
        topico_slug=topico.slug,
        aderencia_medida=False,
    )
    questao = salvar_questao_inedita(
        db,
        topico_id=topico.id,
        item=item,
        publicavel=True,
        motivo_nao_publicavel=None,
        validador_versao="v1-lexico",
        regra_prova=RegraProva(anula_por_erro=False, fonte="inédita — sem regra do DNA"),
    )
    db.commit()
    return questao


def test_get_mostra_selo_de_inedita_sem_bloco_de_origem(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    _criar_questao_inedita(db, topico)

    corpo = logado.get(f"/topico/{topico.slug}/questoes").text
    assert "Questão inédita do AprovaOS" in corpo
    assert "prova original (PDF)" not in corpo


def test_resultado_de_inedita_tambem_mostra_o_selo(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    questao = _criar_questao_inedita(db, topico)

    resposta = logado.post(
        f"/topico/{topico.slug}/questoes",
        data={"resposta": "C", "confianca": "certeza", "questao_id": str(questao.id)},
    )
    assert resposta.status_code == 200
    assert "Questão inédita do AprovaOS" in resposta.text
    assert "prova original (PDF)" not in resposta.text


def test_get_questao_original_nao_mostra_selo_de_inedita(logado: TestClient, db: Session) -> None:
    dona = _usuario_por_email(db, CADASTRO["email"])
    _edital, topico = _edital_com_topico(db, dona.tenant_id, SLUG)
    documento = _documento(db, "prova-inedita-original")
    _criar_questao(db, topico, documento.id)

    corpo = logado.get(f"/topico/{topico.slug}/questoes").text
    assert "Questão inédita do AprovaOS" not in corpo
    assert "prova original (PDF)" in corpo

# O que é: testes das rotas públicas (fatia 13) — família A (`/o-que-cai`), C (`/duvidas`), D
# (`/verticalizado`), `sitemap.xml` e `robots.txt`: o corte de conteúdo, a canonicalização por
# equivalência (Ruling 49), a ausência de sessão/cookie/HTMX e o `Cache-Control`/`Last-Modified`.
# Quando ler: ao mexer em `api/publico.py`, `dados/repositorio_publico.py` ou nos templates
# `web/templates/publico/*.html`.
from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Concurso,
    DnaConcursoRegistro,
    DossieTopico,
    Edital,
    Topico,
    TopicoEdital,
)
from aprovaos.dados.repositorio_topico_relacao import criar_relacao_equivalente
from aprovaos.dominio.dna import (
    DESCONHECIDO,
    ConcursoDna,
    Corte,
    DnaConcurso,
    Estilo,
    Incidencia,
    Pesos,
    RegraCorrecao,
)
from tests.test_rota_questoes import _criar_questao, _documento

MATERIA = "DIREITO ADMINISTRATIVO"


def _topico(
    db: Session, slug: str, materia: str = MATERIA, nome: str = "Improbidade administrativa"
) -> Topico:
    topico = Topico(materia=materia, nome=nome, slug=slug)
    db.add(topico)
    db.flush()
    db.commit()
    return topico


def _cinco_questoes(db: Session, topico: Topico, prefixo: str) -> None:
    documento = _documento(db, f"prova-{prefixo}")
    for numero in range(1, 6):
        _criar_questao(db, topico, documento.id, numero_item=numero + 100)


def _dossie(db: Session, topico_id: UUID) -> DossieTopico:
    dossie = DossieTopico(
        topico_id=topico_id,
        versao=1,
        gerado_em=agora_utc(),
        conteudo="Primeiro parágrafo do dossiê.\n\nSegundo parágrafo, com mais detalhe.",
        fontes=[
            {
                "id": "F1",
                "tipo": "norma",
                "norma": "lei-8429-1992",
                "artigo": "1",
                "inciso": None,
                "paragrafo": None,
                "citacao_canonica": "Lei 8.429/1992 art. 1",
                "url": "https://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
                "trecho": "Art. 1º ...",
                "vigente": True,
                "redacao_de": None,
            }
        ],
        log_buscas=[],
        bibliografia=[],
        validado_em=None,
        substituido_por=None,
    )
    db.add(dossie)
    db.flush()
    db.commit()
    return dossie


def _dna_minimo(banca: str, orgao: str, anula_por_erro: bool | str) -> DnaConcurso:
    return DnaConcurso(
        concurso=ConcursoDna(
            orgao=orgao,
            cargo="Analista",
            banca=banca,
            edital="01/2026",
            data_prova=DESCONHECIDO,
            fonte="edital §1.1",
        ),
        regra_correcao=RegraCorrecao(
            tipo_item="certo_errado",
            alternativas=None,
            anula_por_erro=anula_por_erro,
            minimo_por_materia="nota zero elimina",
            minimo_global="50%",
            fonte="edital §6.1",
        ),
        etapas=[],
        pesos=Pesos(materia={}, topico={}),
        topicos_edital=[],
        incidencia=Incidencia(por_topico=DESCONHECIDO, provas_analisadas=0, fonte="sem provas"),
        estilo=Estilo(
            tipo_item="certo_errado",
            alternativas=None,
            caracteristicas=DESCONHECIDO,
            fonte="sem provas",
        ),
        pegadinhas=[],
        corte=Corte(lo=DESCONHECIDO, hi=DESCONHECIDO, fonte="sem provas"),
        lacunas=["corte histórico"],
        fontes=["edital (arquivo subido)"],
        versao=1,
    )


def _concurso_com_dna(
    db: Session,
    *,
    banca: str,
    orgao: str,
    anula_por_erro: bool | str,
    data_prova: date | None = None,
) -> Concurso:
    concurso = Concurso(
        tenant_id=None, orgao=orgao, cargo="Analista", banca=banca, data_prova=data_prova
    )
    db.add(concurso)
    db.flush()
    db.add(
        DnaConcursoRegistro(
            concurso=concurso,
            versao=1,
            gerado_em=agora_utc(),
            origem="regras",
            modelo=None,
            motivo_fallback=None,
            conteudo=_dna_minimo(banca, orgao, anula_por_erro).model_dump(mode="json"),
        )
    )
    db.commit()
    return concurso


def _edital_com_topico_publico(db: Session, concurso: Concurso, topico: Topico) -> Edital:
    documento = _documento(db, f"edital-{topico.slug}")
    edital = Edital(concurso=concurso, versao=1, documento=documento)
    db.add(edital)
    db.flush()
    db.add(TopicoEdital(edital=edital, topico=topico, ordem=1, texto_original=f"1. {topico.nome}"))
    db.commit()
    return edital


# ---- família A -------------------------------------------------------------------------------


def test_topico_com_menos_de_cinco_questoes_e_404(cliente: TestClient, db: Session) -> None:
    topico = _topico(db, "dir-adm-99-teste-404")
    documento = _documento(db, "prova-404")
    for numero in range(1, 4):
        _criar_questao(db, topico, documento.id, numero_item=numero)

    resposta = cliente.get(f"/o-que-cai/cebraspe/direito-administrativo/{topico.slug}")
    assert resposta.status_code == 404
    assert resposta.json()["codigo"] == "nao_encontrado"


def test_topico_com_cinco_questoes_gera_pagina(cliente: TestClient, db: Session) -> None:
    topico = _topico(db, "dir-adm-06-improbidade-teste")
    _cinco_questoes(db, topico, "improbidade")

    resposta = cliente.get(f"/o-que-cai/cebraspe/direito-administrativo/{topico.slug}")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/html")
    corpo = resposta.text
    assert '<html lang="pt-BR"' in corpo
    assert "htmx" not in corpo.lower()
    assert "5 questões classificadas" in corpo
    assert "cebraspe" in corpo
    assert "O pregão eletrônico dispensa a fase de habilitação prévia." in corpo
    assert "TJ-PA, 2025, item" in corpo
    assert "application/ld+json" in corpo
    assert '"@type": "BreadcrumbList"' in corpo
    assert resposta.headers["cache-control"] == "public, max-age=3600"
    assert "last-modified" in resposta.headers
    assert "set-cookie" not in resposta.headers


def test_pagina_de_topico_nao_toca_sessao_mesmo_logada(cliente: TestClient, db: Session) -> None:
    cliente.post("/cadastro", data={"email": "linda2@exemplo.com", "senha": "12345678"})
    topico = _topico(db, "dir-adm-06-improbidade-sessao")
    _cinco_questoes(db, topico, "improbidade-sessao")

    resposta = cliente.get(f"/o-que-cai/cebraspe/direito-administrativo/{topico.slug}")
    assert resposta.status_code == 200
    assert "Entrar" in resposta.text
    assert "Criar conta" in resposta.text
    assert "Sair" not in resposta.text  # nunca personaliza — a rota nem lê o cookie


def test_banca_ou_materia_errada_no_endereco_e_404(cliente: TestClient, db: Session) -> None:
    topico = _topico(db, "dir-adm-06-improbidade-endereco")
    _cinco_questoes(db, topico, "improbidade-endereco")

    assert cliente.get(f"/o-que-cai/fgv/direito-administrativo/{topico.slug}").status_code == 404
    assert cliente.get(f"/o-que-cai/cebraspe/direito-civil/{topico.slug}").status_code == 404


def test_dossie_sem_nenhuma_questao_nao_gera_pagina(cliente: TestClient, db: Session) -> None:
    """Corte cumprido (`cabe_em_pagina(0, True)` é `True`), mas sem `Questao.banca` não há
    endereço de banca conhecido para publicar — ver ressalva em `repositorio_publico.py` e
    `docs/PENDENCIAS.md`."""
    topico = _topico(db, "dir-adm-06-improbidade-so-dossie")
    _dossie(db, topico.id)

    resposta = cliente.get(f"/o-que-cai/cebraspe/direito-administrativo/{topico.slug}")
    assert resposta.status_code == 404


def test_equivalencia_curada_gera_canonica(cliente: TestClient, db: Session) -> None:
    maior = _topico(db, "noc-dir-adm-06-improbidade-canonica", nome="Improbidade (edital grande)")
    menor = _topico(db, "dir-adm-06-improbidade-canonica", nome="Improbidade (edital pequeno)")
    documento = _documento(db, "prova-canonica-maior")
    for numero in range(1, 7):  # 6 questões
        _criar_questao(db, maior, documento.id, numero_item=numero + 200)
    documento_menor = _documento(db, "prova-canonica-menor")
    for numero in range(1, 6):  # 5 questões
        _criar_questao(db, menor, documento_menor.id, numero_item=numero + 300)
    criar_relacao_equivalente(
        db, de_id=maior.id, para_id=menor.id, evidencia="mesmo assunto, mesma lei"
    )
    db.commit()

    pagina_maior = cliente.get(f"/o-que-cai/cebraspe/direito-administrativo/{maior.slug}")
    pagina_menor = cliente.get(f"/o-que-cai/cebraspe/direito-administrativo/{menor.slug}")
    assert pagina_maior.status_code == 200
    assert pagina_menor.status_code == 200
    assert (
        f'rel="canonical" href="/o-que-cai/cebraspe/direito-administrativo/{maior.slug}"'
        in pagina_menor.text
    )
    assert 'rel="canonical"' not in pagina_maior.text

    sitemap = cliente.get("/sitemap.xml").text
    assert f"/o-que-cai/cebraspe/direito-administrativo/{maior.slug}" in sitemap
    assert f"/o-que-cai/cebraspe/direito-administrativo/{menor.slug}" not in sitemap


# ---- família C ---------------------------------------------------------------------------------


def test_duvida_com_regra_conhecida(cliente: TestClient, db: Session) -> None:
    _concurso_com_dna(db, banca="Instituto AOCP", orgao="TJ-PR", anula_por_erro=False)

    resposta = cliente.get("/duvidas/desconto-por-erro-instituto-aocp")
    assert resposta.status_code == 200
    assert "Não" in resposta.text
    assert "Instituto AOCP" in resposta.text
    assert '"@type": "FAQPage"' in resposta.text


def test_duvida_com_regra_desconhecida_nao_inventa(cliente: TestClient, db: Session) -> None:
    _concurso_com_dna(db, banca="FGV", orgao="TJ-X", anula_por_erro=DESCONHECIDO)

    resposta = cliente.get("/duvidas/desconto-por-erro-fgv")
    assert resposta.status_code == 200
    assert "Ainda não medimos" in resposta.text


def test_duvida_inexistente_e_404(cliente: TestClient) -> None:
    assert cliente.get("/duvidas/desconto-por-erro-banca-inexistente").status_code == 404


# ---- família D ---------------------------------------------------------------------------------


def test_verticalizado_publico(cliente: TestClient, db: Session) -> None:
    concurso = _concurso_com_dna(
        db,
        banca="Instituto AOCP",
        orgao="TJ-PR",
        anula_por_erro=DESCONHECIDO,
        data_prova=date(2025, 6, 1),
    )
    topico = _topico(db, "noc-dir-adm-01-vertical", nome="Ato administrativo")
    _edital_com_topico_publico(db, concurso, topico)

    resposta = cliente.get("/verticalizado/tj-pr-2025")
    assert resposta.status_code == 200
    assert "Ato administrativo" in resposta.text
    assert "Instituto AOCP" in resposta.text
    assert "set-cookie" not in resposta.headers


def test_concurso_sem_data_prova_nao_gera_pagina_d(cliente: TestClient, db: Session) -> None:
    _concurso_com_dna(db, banca="FCC", orgao="TRT9", anula_por_erro=DESCONHECIDO, data_prova=None)
    assert cliente.get("/verticalizado/trt9-2025").status_code == 404


# ---- sitemap/robots -----------------------------------------------------------------------------


def test_sitemap_lista_home_e_e_xml(cliente: TestClient, db: Session) -> None:
    resposta = cliente.get("/sitemap.xml")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("application/xml")
    assert "<urlset" in resposta.text
    assert "<loc>http://testserver/</loc>" in resposta.text


def test_sitemap_inclui_pagina_de_topico_que_passou_do_corte(
    cliente: TestClient, db: Session
) -> None:
    topico = _topico(db, "dir-adm-06-improbidade-sitemap")
    _cinco_questoes(db, topico, "improbidade-sitemap")

    sitemap = cliente.get("/sitemap.xml").text
    assert f"/o-que-cai/cebraspe/direito-administrativo/{topico.slug}" in sitemap


def test_robots_libera_familias_publicas(cliente: TestClient) -> None:
    resposta = cliente.get("/robots.txt")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/plain")
    corpo = resposta.text
    assert "Allow: /o-que-cai/" in corpo
    assert "Allow: /duvidas/" in corpo
    assert "Allow: /verticalizado/" in corpo
    assert "Sitemap: http://testserver/sitemap.xml" in corpo

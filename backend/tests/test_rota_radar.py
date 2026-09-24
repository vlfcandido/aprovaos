# O que é: testes dos passos 4, 5 e 6 do plano `docs/fatias/1b-radar-e-conta.md` — as rotas
# `GET /radar`, `GET /radar/{evento_url}`, `POST /radar/{evento_url}/acompanhar`,
# `POST /perfil/principal` e `POST /radar/{evento_url}/analisar`. Quando ler: ao mexer em
# `api/radar.py` ou nos templates `web/templates/radar/`.
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.api.templates import formatar_brl
from aprovaos.dados.modelos import Concurso, Usuario
from aprovaos.dados.repositorio_perfil import salvar_perfil
from aprovaos.dados.repositorio_radar import obter_ou_criar_fonte, sincronizar
from aprovaos.dominio.radar import ConcursoDoRadar
from aprovaos.dominio.rotina import DIAS_SEMANA, DadosRotina
from aprovaos.motor.fontes.base import ArquivoBaixado, FonteIndisponivel, Novidade

RAIZ = Path(__file__).resolve().parents[2]
PDF = (RAIZ / "knowledge/fixtures/editais/edital-assessor-gabinete.pdf").read_bytes()
CADASTRO = {"email": "linda@exemplo.com", "senha": "12345678"}
AGORA = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _concurso(evento_url: str = "AGEPAR_PR_26", **sobrescritas: object) -> ConcursoDoRadar:
    base: dict[str, object] = {
        "evento_url": evento_url,
        "nome": "AGEPAR PR 26",
        "ano": 2026,
        "fase": "em_andamento",
        "uf": "PR",
        "vagas": 23,
        "salario_max_brl": Decimal("9975"),
        "periodo_inscricao_texto": None,
        "inscricao_inicio": None,
        "inscricao_fim": None,
        "lacunas": ["data da prova não publicada na API"],
    }
    base.update(sobrescritas)
    return ConcursoDoRadar.model_validate(base)


def _semear_catalogo(db: Session, *concursos: ConcursoDoRadar) -> None:
    fonte = obter_ou_criar_fonte(db, "cebraspe", "Cebraspe", "https://apis.cebraspe.org.br/x")
    sincronizar(db, fonte, list(concursos), AGORA)
    db.commit()


class FonteFalsa:
    """Dublê de `FonteCebraspe` para as rotas do radar — nunca toca a rede."""

    def __init__(
        self, detalhe: Any = None, conteudo_pdf: bytes = PDF, indisponivel: bool = False
    ) -> None:
        self._detalhe = detalhe or {}
        self._conteudo_pdf = conteudo_pdf
        self._indisponivel = indisponivel

    def obter_detalhe(self, evento_url: str) -> Any:
        """Devolve o detalhe cadastrado, ou levanta `FonteIndisponivel`."""
        if self._indisponivel:
            raise FonteIndisponivel("fonte fora do ar (simulado)")
        return self._detalhe

    def baixar(self, novidade: Novidade) -> ArquivoBaixado:
        """Devolve o PDF cadastrado, ou levanta `FonteIndisponivel`."""
        if self._indisponivel:
            raise FonteIndisponivel("fonte fora do ar (simulado)")
        return ArquivoBaixado.de_conteudo(novidade, self._conteudo_pdf)


@pytest.fixture
def logado(cliente: TestClient) -> TestClient:
    assert cliente.post("/cadastro", data=CADASTRO, follow_redirects=False).status_code == 303
    return cliente


def _com_rotina(db: Session, email: str) -> Usuario:
    usuario = db.scalars(select(Usuario).where(Usuario.email == email)).one()
    salvar_perfil(
        db,
        usuario,
        DadosRotina(
            horas_por_dia_semana=dict.fromkeys(DIAS_SEMANA, 2.0),
            horario_preferido="manha",
            energia_tipica="media",
            data_alvo=None,
            concurso_principal_id=None,
        ),
    )
    db.commit()
    return usuario


def test_radar_lista_o_catalogo_sem_precisar_de_login(cliente: TestClient, db: Session) -> None:
    _semear_catalogo(db, _concurso())
    resposta = cliente.get("/radar")
    assert resposta.status_code == 200
    assert "AGEPAR PR 26" in resposta.text
    assert "fonte vetada" in resposta.text.lower()


def test_radar_filtra_por_fase(cliente: TestClient, db: Session) -> None:
    _semear_catalogo(
        db,
        _concurso("AGEPAR_PR_26", fase="em_andamento"),
        _concurso("SEFAZ_AL_26", fase="inscricoes_abertas", nome="SEFAZ AL 26", uf="AL"),
    )
    resposta = cliente.get("/radar", params={"fase": "inscricoes_abertas"})
    assert "SEFAZ AL 26" in resposta.text
    assert "AGEPAR PR 26" not in resposta.text


def test_radar_marca_combina_por_uf_sem_esconder_os_outros(
    cliente: TestClient, db: Session
) -> None:
    """Ruling 40: o filtro de preferência marca, nunca esconde — os dois aparecem."""
    _semear_catalogo(
        db,
        _concurso("AGEPAR_PR_26", uf="PR"),
        _concurso("SEFAZ_AL_26", nome="SEFAZ AL 26", uf="AL"),
    )
    resposta = cliente.get("/radar", params={"uf": "PR"})
    corpo = resposta.text
    assert "AGEPAR PR 26" in corpo
    assert "SEFAZ AL 26" in corpo
    # Na passada visual de 23/09/2026 o catálogo virou tabela: o motivo do casamento saiu do
    # texto do cartão ("combina: PR") e virou o chip da coluna "Combina". A regra medida é a
    # mesma — marca quem combina, não esconde quem não combina.
    assert "Combina" in corpo
    assert '<span class="chip accent">PR</span>' in corpo


def test_radar_detalhe_404_para_evento_desconhecido(cliente: TestClient) -> None:
    resposta = cliente.get("/radar/NAO_EXISTE")
    assert resposta.status_code == 404


def test_radar_detalhe_mostra_cargos_e_arquivos(
    app: FastAPI, cliente: TestClient, db: Session
) -> None:
    _semear_catalogo(db, _concurso())
    app.state.fonte_cebraspe = FonteFalsa(
        detalhe={
            "eventoCargos": [{"idArea": "03", "area": "CARGO 3: ESPECIALIDADE: DIREITO"}],
            "arquivosEdital": [
                {
                    "nomeArquivo": "edital1.pdf",
                    "tipoExtensaoArquivo": "_.pdf",
                    "descricaoArquivo": "Edital nº 1",
                }
            ],
        }
    )
    resposta = cliente.get("/radar/AGEPAR_PR_26")
    assert resposta.status_code == 200
    assert "CARGO 3: ESPECIALIDADE: DIREITO" in resposta.text
    assert "Edital nº 1" in resposta.text
    assert 'href="/entrar"' in resposta.text  # sem login, não mostra "Acompanhar"


def test_radar_detalhe_fonte_indisponivel_nao_quebra_a_pagina(
    app: FastAPI, cliente: TestClient, db: Session
) -> None:
    _semear_catalogo(db, _concurso())
    app.state.fonte_cebraspe = FonteFalsa(indisponivel=True)
    resposta = cliente.get("/radar/AGEPAR_PR_26")
    assert resposta.status_code == 200
    assert "AGEPAR PR 26" in resposta.text
    assert "Não deu para consultar" in resposta.text


def test_acompanhar_sem_login_redireciona_para_entrar(cliente: TestClient, db: Session) -> None:
    _semear_catalogo(db, _concurso())
    resposta = cliente.post("/radar/AGEPAR_PR_26/acompanhar", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/entrar"


def test_acompanhar_evento_desconhecido_e_404(logado: TestClient) -> None:
    resposta = logado.post("/radar/NAO_EXISTE/acompanhar", follow_redirects=False)
    assert resposta.status_code == 404


def test_acompanhar_sem_rotina_manda_para_rotina(logado: TestClient, db: Session) -> None:
    _semear_catalogo(db, _concurso())
    resposta = logado.post("/radar/AGEPAR_PR_26/acompanhar", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/rotina"


def test_acompanhar_alterna_e_aparece_em_meus_concursos(logado: TestClient, db: Session) -> None:
    _semear_catalogo(db, _concurso())
    _com_rotina(db, CADASTRO["email"])

    resposta = logado.post("/radar/AGEPAR_PR_26/acompanhar", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/radar/AGEPAR_PR_26"

    corpo = logado.get("/radar").text
    assert "Acompanhando no radar" in corpo
    assert "AGEPAR PR 26" in corpo
    assert "acompanha 1 concurso" in corpo

    logado.post("/radar/AGEPAR_PR_26/acompanhar", follow_redirects=False)
    corpo = logado.get("/radar").text
    assert "Acompanhando no radar" not in corpo


def test_perfil_principal_recusa_concurso_de_outro_tenant(logado: TestClient, db: Session) -> None:
    _com_rotina(db, CADASTRO["email"])
    outro_tenant_concurso_id = UUID(int=99)
    resposta = logado.post(
        "/perfil/principal",
        data={"concurso_id": str(outro_tenant_concurso_id)},
        follow_redirects=False,
    )
    assert resposta.status_code == 403


def test_analisar_edital_do_radar_sem_pdf_mostra_mensagem(
    app: FastAPI, logado: TestClient, db: Session
) -> None:
    _semear_catalogo(db, _concurso())
    _com_rotina(db, CADASTRO["email"])
    app.state.fonte_cebraspe = FonteFalsa(detalhe={"arquivosEdital": []})

    resposta = logado.post("/radar/AGEPAR_PR_26/analisar", follow_redirects=False)

    assert resposta.status_code == 200
    assert "não tem edital em PDF" in resposta.text


def test_analisar_edital_do_radar_fonte_indisponivel(
    app: FastAPI, logado: TestClient, db: Session
) -> None:
    _semear_catalogo(db, _concurso())
    _com_rotina(db, CADASTRO["email"])
    app.state.fonte_cebraspe = FonteFalsa(indisponivel=True)

    resposta = logado.post("/radar/AGEPAR_PR_26/analisar", follow_redirects=False)

    assert resposta.status_code == 200
    assert "Não deu para consultar" in resposta.text


def test_analisar_edital_do_radar_roda_o_pipeline_e_cria_concurso_real(
    app: FastAPI, logado: TestClient, db: Session
) -> None:
    _semear_catalogo(db, _concurso())
    _com_rotina(db, CADASTRO["email"])
    app.state.fonte_cebraspe = FonteFalsa(
        detalhe={
            "arquivosEdital": [
                {
                    "nomeArquivo": "edital.pdf",
                    "tipoExtensaoArquivo": "_.pdf",
                    "descricaoArquivo": "Edital nº 1",
                }
            ]
        },
        conteudo_pdf=PDF,
    )

    resposta = logado.post("/radar/AGEPAR_PR_26/analisar", follow_redirects=False)

    assert resposta.status_code == 303
    assert str(resposta.headers["location"]).startswith("/concurso/")
    concurso = db.scalars(select(Concurso)).one()
    assert concurso.origem == "real"


def test_nav_tem_link_radar_com_ou_sem_login(cliente: TestClient) -> None:
    assert 'href="/radar"' in cliente.get("/").text


# --- porte visual (fatia 14, §2.2): defeitos reproduzidos com os 495 concursos reais no banco ---


def test_formatar_brl() -> None:
    assert formatar_brl(Decimal("16620.00")) == "R$ 16.620,00"
    assert formatar_brl(Decimal("9975")) == "R$ 9.975,00"


def test_radar_nao_mostra_valor_cru_de_enum_nem_codigo_interno(
    cliente: TestClient, db: Session
) -> None:
    _semear_catalogo(db, _concurso(salario_max_brl=Decimal("16620.00")))
    corpo = cliente.get("/radar", params={"fase": "inscricoes_abertas"}).text
    # `inscricoes_abertas` só pode aparecer como `value` de `<option>` (controle de formulário),
    # nunca como texto visível — o defeito era o valor cru do enum aparecer no cartão do concurso.
    assert ">inscricoes_abertas<" not in corpo
    assert "Inscrições abertas" in corpo
    assert "P-13" not in corpo


def test_radar_mostra_salario_em_formato_brasileiro(cliente: TestClient, db: Session) -> None:
    _semear_catalogo(db, _concurso(salario_max_brl=Decimal("16620.00")))
    corpo = cliente.get("/radar").text
    assert "R$ 16.620,00" in corpo
    assert "16620.00" not in corpo


def test_radar_lacuna_da_data_da_prova_aparece_uma_vez_no_cabecalho(
    cliente: TestClient, db: Session
) -> None:
    _semear_catalogo(
        db,
        _concurso("AGEPAR_PR_26"),
        _concurso("SEFAZ_AL_26", nome="SEFAZ AL 26", uf="AL"),
    )
    corpo = cliente.get("/radar").text
    assert corpo.count("data da prova") == 1


def test_radar_afunda_encerrado_mesmo_com_ordem_alfabetica_favoravel(
    cliente: TestClient, db: Session
) -> None:
    """Fatia 14, §2.2: antes desta correção, 423 dos 495 concursos reais (todos encerrados)
    apareciam no topo, em ordem alfabética — o desempate por `inscricao_fim` (quase sempre
    ausente) deixava a ordem crua do banco (alfabética) aparecer por trás."""
    _semear_catalogo(
        db,
        _concurso("AAA_ENCERRADO", nome="AAA CONCURSO ENCERRADO", fase="encerrado"),
        _concurso("ZZZ_ABERTO", nome="ZZZ CONCURSO ABERTO", fase="inscricoes_abertas"),
    )
    corpo = cliente.get("/radar").text
    assert corpo.index("ZZZ CONCURSO ABERTO") < corpo.index("AAA CONCURSO ENCERRADO")


# --- o radar depois da passada visual de 23/09/2026 -----------------------------------------
# O dono, vendo a piloto usar: "o radar está péssimo". Os 495 concursos do catálogo público
# apareciam como se fossem os concursos dela, sem busca e sem filtro decente.


def test_radar_diz_que_o_catalogo_e_publico_e_nao_dela(cliente: TestClient, db: Session) -> None:
    _semear_catalogo(db, _concurso())
    corpo = cliente.get("/radar").text
    assert "Catálogo público" in corpo
    assert "não são os seus concursos" in corpo


def test_radar_busca_por_texto_no_nome(cliente: TestClient, db: Session) -> None:
    _semear_catalogo(
        db,
        _concurso("AGEPAR_PR_26"),
        _concurso("SEFAZ_AL_26", nome="SEFAZ AL 26", uf="AL"),
    )
    corpo = cliente.get("/radar", params={"q": "sefaz"}).text
    assert "SEFAZ AL 26" in corpo
    assert "AGEPAR PR 26" not in corpo


def test_radar_busca_ignora_acento(cliente: TestClient, db: Session) -> None:
    _semear_catalogo(db, _concurso("POLICIA_26", nome="POLÍCIA FEDERAL 26"))
    assert "POLÍCIA FEDERAL 26" in cliente.get("/radar", params={"q": "policia"}).text


def test_radar_busca_sem_resultado_oferece_saida(cliente: TestClient, db: Session) -> None:
    _semear_catalogo(db, _concurso())
    corpo = cliente.get("/radar", params={"q": "nao-existe-nada-assim"}).text
    assert "nao-existe-nada-assim" in corpo
    assert "Limpar busca e filtros" in corpo


def test_radar_mostra_um_lote_por_vez_e_oferece_mostrar_mais(
    cliente: TestClient, db: Session
) -> None:
    """495 concursos numa página só foi o que afundou a piloto: o catálogo sai em lotes."""
    _semear_catalogo(
        db,
        *[
            _concurso(f"EVENTO_{n:03d}", nome=f"CONCURSO {n:03d}", fase="inscricoes_abertas")
            for n in range(60)
        ],
    )
    corpo = cliente.get("/radar", params={"limite": "10"}).text
    assert "Mostrar mais" in corpo
    assert corpo.count("<tr data-concurso=") == 10
    assert "60 concursos" in corpo


def test_radar_poe_inscricao_aberta_na_frente(cliente: TestClient, db: Session) -> None:
    """Sem data de inscrição (o caso de quase todos), a ordem caía no alfabeto do banco e um
    concurso já em andamento aparecia antes de um com inscrição aberta — que é o único em que a
    aluna ainda pode entrar. A situação passa a desempatar antes do nome."""
    _semear_catalogo(
        db,
        _concurso("AAA_ANDAMENTO", nome="AAA EM ANDAMENTO", fase="em_andamento"),
        _concurso("ZZZ_ABERTO", nome="ZZZ INSCRICOES ABERTAS", fase="inscricoes_abertas"),
    )
    corpo = cliente.get("/radar").text
    assert corpo.index("ZZZ INSCRICOES ABERTAS") < corpo.index("AAA EM ANDAMENTO")

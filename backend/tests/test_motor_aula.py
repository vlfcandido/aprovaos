# O que é: testes do comando `motor/aula.py` (fatia 6) — gera e valida a aula de um tópico a
# partir do dossiê real, do fio da memória (a) e de questões publicadas reais, com um gerador
# falso (sem rede). Quando ler: ao mudar o pipeline do comando ou a regra de quando um tópico
# fica sem aula nesta rodada.
from datetime import date, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Concurso,
    Documento,
    DossieTopico,
    Edital,
    EventoEstudo,
    Questao,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.aula import CitacaoAula, ComoABancaCobra, ConteudoAula, RelacionadoAula
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup
from aprovaos.motor.aula import gerar_aula_topico
from aprovaos.motor.dossie import SLUG_IMPROBIDADE, construir_dossie_improbidade


def _usuario(db: Session, email: str) -> Usuario:
    return criar_conta(db, DadosCadastro(email=email, senha="12345678"))


def _documento(db: Session, hash_: str) -> Documento:
    documento = Documento(
        tipo="prova", hash=hash_, caminho=f"{hash_}.pdf", baixado_em=agora_utc(), metadados={}
    )
    db.add(documento)
    db.flush()
    return documento


def _topico_relacionado(db: Session, slug: str) -> Topico:
    topico = Topico(materia="direito-processual-civil", nome="Atos processuais", slug=slug)
    db.add(topico)
    db.flush()
    return topico


def _dossie_relacionado(db: Session, topico: Topico, trecho: str) -> DossieTopico:
    dossie = DossieTopico(
        topico_id=topico.id,
        versao=1,
        gerado_em=agora_utc(),
        conteudo="conteúdo",
        fontes=[
            {
                "id": "F1",
                "tipo": "norma",
                "citacao_canonica": "Lei 13.105/2015 art. 219",
                "url": "https://planalto.gov.br/cpc",
                "trecho": trecho,
                "vigente": True,
            }
        ],
        bibliografia=[],
        log_buscas=[],
    )
    db.add(dossie)
    db.flush()
    return dossie


def _edital_com_topicos(db: Session, tenant_id: UUID, topicos: list[Topico]) -> Edital:
    documento = _documento(db, f"edital-{topicos[0].slug}")
    concurso = Concurso(tenant_id=tenant_id, orgao="TJ-PA", cargo="Analista", banca="cebraspe")
    edital = Edital(concurso=concurso, versao=1, documento=documento)
    db.add_all([concurso, edital])
    db.flush()
    for ordem, topico in enumerate(topicos, start=1):
        db.add(
            TopicoEdital(
                edital=edital, topico=topico, ordem=ordem, texto_original=f"{ordem}. {topico.nome}"
            )
        )
    db.flush()
    return edital


def _questao(db: Session, topico: Topico, documento_id: UUID, *, numero_item: int) -> Questao:
    origem = Origem(
        banca="cebraspe",
        orgao="TJ-PA",
        cargo="Analista",
        ano=2025,
        numero_item=numero_item,
        tipo_caderno=None,
        url_prova="https://cdn.cebraspe.org.br/prova.pdf",
        documento_id=str(documento_id),
    )
    curada = QuestaoCurada(
        banca="cebraspe",
        numero_item=numero_item,
        comando="Julgue o item a seguir.",
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=f"Enunciado real {numero_item} sobre {topico.slug}.",
        gabarito_preliminar=None,
        gabarito="C",
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=topico.slug,
        topico_confianca="alta",
        topico_evidencia="fixture de teste",
        origem=origem,
        hash_dedup=hash_dedup(f"{numero_item}-{topico.slug}"),
    )
    salvar_questoes(db, [curada])
    db.flush()
    return db.scalars(select(Questao).where(Questao.hash_dedup == curada.hash_dedup)).one()


def _evento(
    db: Session, usuario: Usuario, questao: Questao, *, acertou: bool, ha_dias: int
) -> None:
    evento = EventoEstudo(
        usuario_id=usuario.id,
        ocorrido_em=agora_utc() - timedelta(days=ha_dias),
        tipo="resposta",
        questao_id=questao.id,
        acertou=acertou,
        resposta="C" if acertou else "E",
        tempo_ms=100,
        confianca_declarada="certeza",
    )
    db.add(evento)
    db.flush()


class GeradorFalso:
    """Dublê da porta: devolve sempre a resposta preparada, registrando o que recebeu."""

    def __init__(self, resposta: ConteudoAula) -> None:
        self.resposta = resposta
        self.entradas: list[object] = []

    async def gerar(self, entrada: object) -> ConteudoAula:
        self.entradas.append(entrada)
        return self.resposta


class GeradorQueEstoura:
    async def gerar(self, entrada: object) -> ConteudoAula:
        raise RuntimeError("indisponível")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _preparar_base(db: Session) -> tuple[Usuario, UUID, Questao]:
    """Tópico da aula (improbidade, com dossiê real) + tópico relacionado (com dossiê e um erro
    recente da aluna) + uma questão publicável real do tópico da aula, tudo no mesmo edital."""
    topico_aula = Topico(
        materia="direito-administrativo", nome="Improbidade", slug=SLUG_IMPROBIDADE
    )
    db.add(topico_aula)
    db.flush()
    construir_dossie_improbidade(db, hoje=date(2026, 9, 19))
    db.flush()

    topico_relacionado = _topico_relacionado(db, "dir-pro-civ-03-atos-processuais")
    _dossie_relacionado(
        db, topico_relacionado, "Os prazos processuais somente correm em dias úteis."
    )

    usuario = _usuario(db, "linda@exemplo.com")
    edital = _edital_com_topicos(db, usuario.tenant_id, [topico_aula, topico_relacionado])

    documento = _documento(db, "doc-relacionado")
    questao_relacionada = _questao(db, topico_relacionado, documento.id, numero_item=1)
    _evento(db, usuario, questao_relacionada, acertou=False, ha_dias=6)

    documento_aula = _documento(db, "doc-aula")
    questao_aula = _questao(db, topico_aula, documento_aula.id, numero_item=57)

    return usuario, edital.id, questao_aula


def _resposta_valida(questao_aula: Questao) -> ConteudoAula:
    # O marcador {{...}} só existe para citação do dossiê **deste** tópico (resolve contra as
    # fontes de `dossie.fontes`); a relação com outro tópico é texto corrido, sustentado por
    # `relacionados[i].trecho` (conferido à parte pelo validador), nunca por um marcador.
    return ConteudoAula(
        texto_denso=(
            "Os atos de improbidade administrativa tutelam a probidade na organização do "
            "Estado {{Lei 8.429/1992 art. 1}}. Isso conversa com o que você viu em atos "
            "processuais, cujos prazos só correm em dias úteis."
        ),
        texto_leigo="A lei pune improbidade.",
        citacoes=[
            CitacaoAula(
                canonica="Lei 8.429/1992 art. 1",
                fonte="F1",
                trecho="atos de improbidade administrativa tutelará a probidade",
                frase_da_aula=(
                    "Os atos de improbidade administrativa tutelam a probidade na "
                    "organização do Estado"
                ),
            ),
        ],
        relacionados=[
            RelacionadoAula(
                topico_slug="dir-pro-civ-03-atos-processuais",
                onde="§2",
                frase="Isso conversa com o que você viu em atos processuais.",
                trecho="Os prazos processuais somente correm em dias úteis.",
            )
        ],
        como_a_banca_cobra=[],
        lacunas_declaradas=[],
    )


@pytest.mark.anyio
async def test_gera_e_publica_quando_aprovado(db: Session) -> None:
    usuario, edital_id, questao_aula = _preparar_base(db)
    gerador = GeradorFalso(_resposta_valida(questao_aula))

    relatorio = await gerar_aula_topico(
        db, SLUG_IMPROBIDADE, gerador, usuario.id, edital_id, tempo_alvo_min=1
    )
    db.commit()

    assert relatorio.status == "gerada", relatorio.motivos
    assert relatorio.motivos == []
    assert len(gerador.entradas) == 1

    from aprovaos.dados.repositorio_aula import aula_publicada_do_topico

    topico = db.scalars(select(Topico).where(Topico.slug == SLUG_IMPROBIDADE)).one()
    aula = aula_publicada_do_topico(db, topico.id)
    assert aula is not None
    assert aula.relacionados[0]["topico_slug"] == "dir-pro-civ-03-atos-processuais"


@pytest.mark.anyio
async def test_relatorio_lista_a_origem_real_da_questao_como_permitida(db: Session) -> None:
    usuario, edital_id, questao_aula = _preparar_base(db)
    origem = questao_aula.origem
    assert origem is not None
    origem_invalida = ConteudoAula(
        texto_denso=(
            "A improbidade administrativa é punida na forma da lei {{Lei 8.429/1992 art. 1}}."
        ),
        texto_leigo="A lei pune improbidade.",
        citacoes=[
            CitacaoAula(
                canonica="Lei 8.429/1992 art. 1",
                fonte="F1",
                trecho="Os atos de improbidade administrativa",
                frase_da_aula="A improbidade administrativa é punida na forma da lei",
            )
        ],
        como_a_banca_cobra=[
            ComoABancaCobra(origem="cebraspe 2099 orgao-fake item 999", o_que_testou="qualquer")
        ],
    )
    gerador = GeradorFalso(origem_invalida)

    relatorio = await gerar_aula_topico(
        db, SLUG_IMPROBIDADE, gerador, usuario.id, edital_id, tempo_alvo_min=1
    )

    assert relatorio.status == "reprovada"
    assert any("origem" in m for m in relatorio.motivos)


@pytest.mark.anyio
async def test_sem_topico_reporta_sem_derrubar(db: Session) -> None:
    usuario = _usuario(db, "x@exemplo.com")
    relatorio = await gerar_aula_topico(
        db, "topico-inexistente", GeradorQueEstoura(), usuario.id, usuario.tenant_id
    )
    assert relatorio.status == "sem_topico"


@pytest.mark.anyio
async def test_sem_dossie_reporta_sem_derrubar(db: Session) -> None:
    usuario = _usuario(db, "y@exemplo.com")
    topico = Topico(materia="direito-civil", nome="Sem dossiê", slug="dir-civ-sem-dossie")
    db.add(topico)
    db.flush()
    relatorio = await gerar_aula_topico(
        db, "dir-civ-sem-dossie", GeradorQueEstoura(), usuario.id, usuario.tenant_id
    )
    assert relatorio.status == "sem_dossie"


@pytest.mark.anyio
async def test_sem_ia_reporta_sem_derrubar(db: Session) -> None:
    usuario, edital_id, _questao_aula = _preparar_base(db)
    relatorio = await gerar_aula_topico(db, SLUG_IMPROBIDADE, None, usuario.id, edital_id)
    assert relatorio.status == "sem_ia"


@pytest.mark.anyio
async def test_erro_do_provedor_reporta_sem_derrubar(db: Session) -> None:
    usuario, edital_id, _questao_aula = _preparar_base(db)
    relatorio = await gerar_aula_topico(
        db, SLUG_IMPROBIDADE, GeradorQueEstoura(), usuario.id, edital_id
    )
    assert relatorio.status == "erro"
    assert "RuntimeError" in relatorio.motivos[0]


@pytest.mark.anyio
async def test_rodar_de_novo_nao_republica_quando_ja_tem_aula(db: Session) -> None:
    usuario, edital_id, questao_aula = _preparar_base(db)
    gerador = GeradorFalso(_resposta_valida(questao_aula))
    primeiro = await gerar_aula_topico(
        db, SLUG_IMPROBIDADE, gerador, usuario.id, edital_id, tempo_alvo_min=1
    )
    assert primeiro.status == "gerada"

    segundo = await gerar_aula_topico(
        db, SLUG_IMPROBIDADE, gerador, usuario.id, edital_id, tempo_alvo_min=1
    )
    assert segundo.status == "gerada"

    from aprovaos.dados.modelos import Aula

    topico = db.scalars(select(Topico).where(Topico.slug == SLUG_IMPROBIDADE)).one()
    versoes = db.scalars(select(Aula.versao).where(Aula.topico_id == topico.id)).all()
    assert sorted(versoes) == [1, 2]

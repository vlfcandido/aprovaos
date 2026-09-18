# O que é: testes do passo 8 da V3 — o léxico por regras (`classificar_por_regras`), o lote
# (`montar_lotes`), a interpretação da resposta da IA (`interpretar_resposta`, entrada a entrada)
# e a orquestração `classificar` (fatia por `tamanho_lote`, IA → cada item confere → regras,
# nunca bloqueia), além de `escolher_classificador` (sem chave → regras). Quando ler: ao ajustar
# o léxico para um edital real que ele não cobre, ou ao mudar o fluxo de fallback da
# classificação.
import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from aprovaos.agentes.classificador import MOTIVO_SEM_CHAVE, escolher_classificador
from aprovaos.config import Configuracoes
from aprovaos.dados.modelos import Tenant, Usuario
from aprovaos.dominio.edital import extrair_conteudo_programatico
from aprovaos.dominio.pdf import extrair_texto
from aprovaos.dominio.prova import ItemBruto, segmentar_cebraspe
from aprovaos.motor.curadoria.classificacao import (
    SEM_CORRESPONDENCIA,
    Classificacao,
    ClassificacaoInvalida,
    ClassificadorDeTopico,
    ItemParaClassificar,
    MotivosRejeicao,
    TopicoVocabulario,
    classificar,
    classificar_por_regras,
    interpretar_resposta,
    montar_lotes,
)

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"
FIXTURE_PROVA = (
    RAIZ
    / "knowledge/provas/TJ_PA_25_SERVIDOR"
    / "C15F414E0E91EF109220A73BDF53B232C4466F64770A91E715C56DCB94131F41.pdf"
)

# Tamanho de lote alto o bastante para não fatiar os casos pequenos destes testes — quem testa
# a fatia em si é `test_classificar_fatia_pelo_tamanho_do_lote`.
_TAMANHO_LOTE_GRANDE = 100


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def vocabulario() -> list[TopicoVocabulario]:
    """O vocabulário real do edital da Linda (36 tópicos, 22 de Direito)."""
    texto = FIXTURE_MD.read_text(encoding="utf-8")
    materias = extrair_conteudo_programatico(texto)
    return [
        TopicoVocabulario(
            slug=topico.slug, materia=materia.slug, texto_original=topico.texto_original
        )
        for materia in materias
        for topico in materia.topicos
    ]


@pytest.fixture(scope="module")
def itens_reais_por_numero() -> dict[int, ItemBruto]:
    """Os 70 itens reais do caderno de Direito da TJ-PA, indexados por `numero_item`."""
    texto = extrair_texto(FIXTURE_PROVA.read_bytes())
    return {item.numero_item: item for item in segmentar_cebraspe(texto)}


def _item_para_classificar(
    numero: int, itens_reais_por_numero: dict[int, ItemBruto]
) -> ItemParaClassificar:
    bruto = itens_reais_por_numero[numero]
    return ItemParaClassificar(
        numero_item=bruto.numero_item, comando=bruto.comando, enunciado=bruto.enunciado
    )


def test_regras_casam_por_lei_citada(vocabulario: list[TopicoVocabulario]) -> None:
    item = ItemParaClassificar(
        numero_item=1,
        comando="Acerca das licitações públicas, julgue o item a seguir.",
        enunciado=(
            "O diálogo competitivo é modalidade de licitação prevista na Lei nº 14.133/2021, "
            "restrita a contratações que envolvam inovação tecnológica ou técnica."
        ),
    )

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug == "dir-adm-04-licitacoes-contratos"
    assert resultado[0].confianca == "alta"
    assert "14.133" in resultado[0].evidencia


def test_regras_casam_por_termo(vocabulario: list[TopicoVocabulario]) -> None:
    item = ItemParaClassificar(
        numero_item=2,
        comando="Acerca dos princípios que regem a atuação estatal, julgue o item a seguir.",
        enunciado=(
            "O princípio da impessoalidade veda que o agente público beneficie interesses "
            "pessoais no exercício da função administrativa."
        ),
    )

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug == "dir-adm-01-principios-administracao"
    assert resultado[0].confianca == "media"


def test_regras_sem_correspondencia(vocabulario: list[TopicoVocabulario]) -> None:
    item = ItemParaClassificar(
        numero_item=3,
        comando="Acerca de redes de computadores, julgue o item a seguir.",
        enunciado=(
            "O protocolo TCP/IP organiza a comunicação entre dispositivos em camadas, sendo a "
            "camada de transporte responsável pela entrega confiável dos pacotes."
        ),
    )

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug is None
    assert resultado[0].confianca == "baixa"
    assert resultado[0].evidencia == SEM_CORRESPONDENCIA


# --- Ruling 21 (rodada 1 de correção): palavra isolada não basta para "media" ------------


@pytest.mark.parametrize("numero", [52, 67, 68, 69, 70, 89, 90, 91, 92])
def test_regras_palavra_isolada_nao_basta_fica_baixa(
    numero: int,
    vocabulario: list[TopicoVocabulario],
    itens_reais_por_numero: dict[int, ItemBruto],
) -> None:
    """Casos reais confirmados pela auditoria: só uma palavra genérica casou, isso não basta.

    Item 52 ("jurídicas"), 67–69 ("constituição"), 70 ("competência") e 89–92 ("direitos") são
    falsos positivos que a rodada 1 de revisão encontrou no PDF real — o termo bate com um
    tópico errado só porque a palavra aparece solta no comando (compartilhado por todo o bloco)
    ou no enunciado, sem que o item seja realmente sobre aquele tópico.
    """
    item = _item_para_classificar(numero, itens_reais_por_numero)

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug is None
    assert resultado[0].confianca == "baixa"
    assert "não basta" in resultado[0].evidencia


def test_regras_lei_citada_no_item_real_continua_alta(
    vocabulario: list[TopicoVocabulario], itens_reais_por_numero: dict[int, ItemBruto]
) -> None:
    """Item 59 (real): cita a Lei nº 8.429/1992 — continua `alta`, a correção não mexeu aqui."""
    item = _item_para_classificar(59, itens_reais_por_numero)

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug == "dir-adm-06-improbidade-administrativa"
    assert resultado[0].confianca == "alta"


def test_regras_frase_de_duas_palavras_no_item_real_continua_media(
    vocabulario: list[TopicoVocabulario], itens_reais_por_numero: dict[int, ItemBruto]
) -> None:
    """Item 60 (real): "atos administrativos" é frase de 2+ palavras — continua `media`."""
    item = _item_para_classificar(60, itens_reais_por_numero)

    resultado = classificar_por_regras([item], vocabulario)

    assert resultado[0].topico_slug == "dir-adm-02-atos-administrativos"
    assert resultado[0].confianca == "media"


def test_lote_respeita_tamanho() -> None:
    assert montar_lotes(itens=45, tamanho=20) == [20, 20, 5]


def test_interpretar_resposta_do_lote(vocabulario: list[TopicoVocabulario]) -> None:
    slugs_validos = {topico.slug for topico in vocabulario}
    texto = (
        '[{"numero_item": 58, "topico_slug": "dir-adm-04-licitacoes-contratos", '
        '"confianca": "alta", "evidencia": "cita a Lei nº 14.133/2021"}]'
    )

    classificacoes, motivos_rejeicao = interpretar_resposta(texto, slugs_validos)

    assert classificacoes == [
        Classificacao(
            numero_item=58,
            topico_slug="dir-adm-04-licitacoes-contratos",
            confianca="alta",
            evidencia="cita a Lei nº 14.133/2021",
            origem="ia",
        )
    ]
    assert motivos_rejeicao == {}


def test_interpretar_resposta_slug_invalido_e_rejeitada_sem_derrubar_as_boas(
    vocabulario: list[TopicoVocabulario],
) -> None:
    """Correção crítica da rodada 1: 1 entrada ruim não derruba as outras do mesmo lote."""
    slugs_validos = {topico.slug for topico in vocabulario}
    texto = json.dumps(
        [
            {
                "numero_item": 1,
                "topico_slug": "dir-adm-04-licitacoes-contratos",
                "confianca": "alta",
                "evidencia": "cita a Lei nº 14.133/2021",
            },
            {
                "numero_item": 2,
                "topico_slug": "topico-que-nao-existe",
                "confianca": "alta",
                "evidencia": "...",
            },
        ]
    )

    classificacoes, motivos_rejeicao = interpretar_resposta(texto, slugs_validos)

    assert [c.numero_item for c in classificacoes] == [1]
    assert 2 in motivos_rejeicao
    assert "topico-que-nao-existe" in motivos_rejeicao[2]


def test_interpretar_resposta_json_invalido_levanta_erro(
    vocabulario: list[TopicoVocabulario],
) -> None:
    slugs_validos = {topico.slug for topico in vocabulario}

    with pytest.raises(ClassificacaoInvalida):
        interpretar_resposta("isto não é JSON", slugs_validos)


def test_interpretar_resposta_que_nao_e_lista_levanta_erro(
    vocabulario: list[TopicoVocabulario],
) -> None:
    slugs_validos = {topico.slug for topico in vocabulario}

    with pytest.raises(ClassificacaoInvalida):
        interpretar_resposta('{"numero_item": 1}', slugs_validos)


class _ClassificadorFalso:
    """Dublê da porta: devolve sempre a resposta dada no construtor."""

    def __init__(
        self, resposta: list[Classificacao], motivos_rejeicao: MotivosRejeicao | None = None
    ) -> None:
        self.resposta = resposta
        self.motivos_rejeicao = motivos_rejeicao or {}

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        return self.resposta, self.motivos_rejeicao


class _ClassificadorQueLevanta:
    """Dublê da porta: sempre levanta (simula falha do provedor)."""

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        raise RuntimeError("provedor fora do ar")


class _ClassificadorComRespostaBruta:
    """Dublê que interpreta uma resposta crua de IA, como o `ClassificadorAdk` real faria."""

    def __init__(self, texto: str) -> None:
        self._texto = texto

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        slugs_validos = {topico.slug for topico in vocabulario}
        return interpretar_resposta(self._texto, slugs_validos)


class _ClassificadorQueRegistraChamadas:
    """Dublê que registra o tamanho de cada chamada e devolve "baixa" para todo item recebido."""

    def __init__(self) -> None:
        self.tamanhos_chamados: list[int] = []

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        self.tamanhos_chamados.append(len(itens))
        classificacoes = [
            Classificacao(
                numero_item=item.numero_item,
                topico_slug=None,
                confianca="baixa",
                evidencia="dublê",
                origem="ia",
            )
            for item in itens
        ]
        return classificacoes, {}


def test_classificador_falso_e_uma_implementacao_da_porta() -> None:
    assert isinstance(_ClassificadorFalso([]), ClassificadorDeTopico)


@pytest.mark.anyio
async def test_item_ausente_na_resposta_cai_para_regras(
    vocabulario: list[TopicoVocabulario],
) -> None:
    itens = [
        ItemParaClassificar(
            numero_item=1,
            comando="Acerca das licitações públicas, julgue o item a seguir.",
            enunciado="O diálogo competitivo é modalidade prevista na Lei nº 14.133/2021.",
        ),
        ItemParaClassificar(numero_item=2, comando=None, enunciado="Enunciado qualquer."),
    ]
    resposta_ia = [
        Classificacao(
            numero_item=1,
            topico_slug="dir-adm-04-licitacoes-contratos",
            confianca="alta",
            evidencia="cita a Lei nº 14.133/2021, do tópico",
            origem="ia",
        )
    ]

    resultado = await classificar(
        itens, vocabulario, _ClassificadorFalso(resposta_ia), None, _TAMANHO_LOTE_GRANDE
    )

    assert resultado.classificacoes[0].origem == "ia"
    assert resultado.classificacoes[0].motivo_fallback is None
    assert resultado.classificacoes[1].origem == "regras"
    assert resultado.classificacoes[1].motivo_fallback == "item ausente na resposta do modelo"


@pytest.mark.anyio
async def test_slug_inventado_cai_para_regras_so_naquele_item(
    vocabulario: list[TopicoVocabulario],
) -> None:
    """Correção crítica da rodada 1: N−1 entradas boas + 1 slug inventado → só 1 vai para regras."""
    itens = [
        ItemParaClassificar(numero_item=1, comando=None, enunciado="Enunciado 1 qualquer."),
        ItemParaClassificar(numero_item=2, comando=None, enunciado="Enunciado 2 qualquer."),
        ItemParaClassificar(numero_item=3, comando=None, enunciado="Enunciado 3 qualquer."),
    ]
    resposta = json.dumps(
        [
            {
                "numero_item": 1,
                "topico_slug": "dir-adm-02-atos-administrativos",
                "confianca": "media",
                "evidencia": "...",
            },
            {
                "numero_item": 2,
                "topico_slug": "dir-adm-02-atos-administrativos",
                "confianca": "media",
                "evidencia": "...",
            },
            {
                "numero_item": 3,
                "topico_slug": "topico-que-nao-existe",
                "confianca": "alta",
                "evidencia": "...",
            },
        ]
    )

    resultado = await classificar(
        itens, vocabulario, _ClassificadorComRespostaBruta(resposta), None, _TAMANHO_LOTE_GRANDE
    )

    assert resultado.classificacoes[0].origem == "ia"
    assert resultado.classificacoes[1].origem == "ia"
    assert resultado.classificacoes[2].origem == "regras"
    assert resultado.classificacoes[2].motivo_fallback is not None
    assert "topico-que-nao-existe" in resultado.classificacoes[2].motivo_fallback


@pytest.mark.anyio
async def test_fallback_por_erro_da_ia(vocabulario: list[TopicoVocabulario]) -> None:
    itens = [ItemParaClassificar(numero_item=1, comando=None, enunciado="Enunciado qualquer.")]

    resultado = await classificar(
        itens, vocabulario, _ClassificadorQueLevanta(), None, _TAMANHO_LOTE_GRANDE
    )

    assert resultado.classificacoes[0].origem == "regras"
    assert resultado.classificacoes[0].motivo_fallback == "erro na IA: RuntimeError"


@pytest.mark.anyio
async def test_sem_classificador_ia_usa_regras_com_motivo(
    vocabulario: list[TopicoVocabulario],
) -> None:
    itens = [ItemParaClassificar(numero_item=1, comando=None, enunciado="Enunciado qualquer.")]

    resultado = await classificar(
        itens, vocabulario, None, "sem GOOGLE_API_KEY", _TAMANHO_LOTE_GRANDE
    )

    assert resultado.classificacoes[0].origem == "regras"
    assert resultado.classificacoes[0].motivo_fallback == "sem GOOGLE_API_KEY"


@pytest.mark.anyio
async def test_classificar_fatia_pelo_tamanho_do_lote(vocabulario: list[TopicoVocabulario]) -> None:
    """Correção importante da rodada 1: `classificar` usa `montar_lotes`, não manda tudo de vez."""
    itens = [
        ItemParaClassificar(numero_item=numero, comando=None, enunciado=f"Item {numero}.")
        for numero in range(1, 46)
    ]
    dublê = _ClassificadorQueRegistraChamadas()

    resultado = await classificar(itens, vocabulario, dublê, None, tamanho_lote=20)

    assert dublê.tamanhos_chamados == [20, 20, 5]
    assert [c.numero_item for c in resultado.classificacoes] == list(range(1, 46))
    assert len(resultado.classificacoes) == 45


def test_sem_chave_vai_para_regras(db: Session, config_teste: Configuracoes) -> None:
    tenant = Tenant(tipo="pf", nome="Linda")
    usuario = Usuario(email="linda@exemplo.com", senha_hash="h", tenant=tenant)
    db.add(usuario)
    db.commit()

    classificador, motivo = escolher_classificador(db, config_teste, usuario)

    assert classificador is None
    assert motivo == MOTIVO_SEM_CHAVE

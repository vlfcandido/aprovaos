# O que é: testes do passo 9 da V3 — o curador (`motor/curadoria/curador.py`), que junta
# segmentação + gabarito + classificação em `QuestaoCurada` e aplica o gate de publicação
# (`dominio/questao.py`, premissa F / ADR-0033). Quando ler: ao mudar `curar`,
# `verificar_curadoria`, `decidir_publicacao` ou o contrato de `QuestaoCurada`.
from pathlib import Path
from typing import Literal

import pytest

from aprovaos.dominio.edital import extrair_conteudo_programatico
from aprovaos.dominio.pdf import extrair_texto
from aprovaos.dominio.questao import (
    GabaritoStatus,
    Origem,
    QuestaoCurada,
    RegraProva,
    decidir_publicacao,
    hash_dedup,
)
from aprovaos.motor.curadoria.classificacao import (
    Classificacao,
    ItemParaClassificar,
    MotivosRejeicao,
    TopicoVocabulario,
)
from aprovaos.motor.curadoria.curador import (
    OrigemBase,
    ResultadoCuradoria,
    curar,
    verificar_curadoria,
)

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"
_PROVAS = RAIZ / "knowledge/provas/TJ_PA_25_SERVIDOR"
FIXTURE_PROVA = _PROVAS / "C15F414E0E91EF109220A73BDF53B232C4466F64770A91E715C56DCB94131F41.pdf"
FIXTURE_GABARITO = _PROVAS / "EF721EA56FA324A5AE5E9F7A8FD2FE4800E803E772BC6D03E0403D1B61632F72.pdf"

# N e anulados medidos nos passos 6 e 7 (mesmos fixtures, mesmos números — ver
# `test_dominio_prova.py`/`test_dominio_gabarito.py`).
N_ITENS_TJ_PA = 70
ANULADOS_TJ_PA = {75, 104, 105, 108, 112}

# Valores de teste para os campos "constantes do caderno" de `Origem` — o que viria do
# `Documento` gravado pelo passo 5 (coletor). Não são consultados de nenhum PDF por esta
# suíte; existem só para provar que `curar` os repassa sem remontar (decisão 5 do brief).
ORIGEM_BASE_TJ_PA = OrigemBase(
    banca="cebraspe",
    orgao="TJ-PA",
    cargo="Analista Judiciário — Direito",
    ano=2025,
    # a API da Cebraspe não declara tipo de caderno para este concurso — `None` é o valor
    # correto (Ruling 25 do passo 9), nunca um placeholder inventado.
    tipo_caderno=None,
    url_prova="https://www.cebraspe.org.br/concursos/tj_pa_25_servidor",
    documento_id="11111111-1111-1111-1111-111111111111",
)
REGRA_PROVA_TJ_PA = RegraProva(anula_por_erro=True, fonte="instrução do caderno")

CAMPOS_OBRIGATORIOS = [
    "adapter",
    "banca",
    "tipo_item",
    "numero_item",
    "comando",
    "texto_apoio",
    "texto_apoio_itens",
    "enunciado",
    "alternativas",
    "gabarito_preliminar",
    "gabarito",
    "gabarito_status",
    "publicavel",
    "publicado",
    "motivo_nao_publicavel",
    "regra_prova",
    "topico_slug",
    "topico_confianca",
    "topico_evidencia",
    "origem",
    "hash_dedup",
    "justificativa_certo",
    "justificativa_errado",
]

# Cadernos sintéticos, pequenos e declarados como tais — só para exercitar a lógica de junção
# do curador (contagem, item sem entrada quando a contagem bate). A segmentação e a leitura do
# gabarito em si já são testadas contra o caderno real em `test_dominio_prova.py` e
# `test_dominio_gabarito.py`; inventar aqui um caderno "de verdade" violaria a skill.
_TEXTO_PROVA_SINTETICO = (
    "Acerca de direito administrativo, julgue os itens subsequentes.\n"
    "51 O ato administrativo vinculado admite controle judicial de mérito.\n"
    "52 A licitação é obrigatória para toda contratação pública, sem exceção alguma.\n"
    "53 O silêncio administrativo produz efeitos jurídicos em qualquer hipótese legal.\n"
)
# 2 entradas para 3 itens (51, 52, 53) — contagem divergente.
_TEXTO_GABARITO_SINTETICO_2_ENTRADAS = "GABARITOS OFICIAIS DEFINITIVOS\n51 52\nC E\n"
# 3 entradas (51, 52, 54) para 3 itens (51, 52, 53) — contagem bate, mas o item 53 não tem
# entrada (e a entrada do item 54, que não existe no caderno, não é usada por ninguém).
_TEXTO_GABARITO_SINTETICO_SEM_53 = "GABARITOS OFICIAIS DEFINITIVOS\n51 52 54\nC E C\n"

# Bloco do item 51 com 3 fronteiras de comando candidatas (3 frases terminadas em "." antes do
# comando "Julgue os itens subsequentes.") — o padrão conhecido de `segmentar_cebraspe` trata no
# máximo 2 (fim do enunciado + narrativa de apoio implícita); a 3ª levanta `SegmentacaoAmbigua`.
# Confirmado por execução direta antes de escrever o teste (não é achismo).
_TEXTO_PROVA_SEGMENTACAO_AMBIGUA = (
    "Acerca de direito administrativo, julgue o item subsequente.\n"
    "51 Primeira frase do item, ainda descrevendo uma situação hipotética.\n"
    "Segunda frase de contexto adicional que também poderia ser comando.\n"
    "Terceira frase extra de contexto, cada vez mais parecida com um comando.\n"
    "Julgue os itens subsequentes.\n"
)
# Nenhuma grade de gabarito Cebraspe C/E reconhecível — nem uma linha de números seguida de uma
# linha de valores C/E/X.
_TEXTO_GABARITO_INVALIDO = "não há gabarito aqui, só texto qualquer.\n"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
def vocabulario() -> list[TopicoVocabulario]:
    """O vocabulário do fixture de edital (fictício, Fase 4; 36 tópicos, 22 de Direito)."""
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
def texto_prova_real() -> str:
    return extrair_texto(FIXTURE_PROVA.read_bytes())


@pytest.fixture(scope="module")
def texto_gabarito_real() -> str:
    return extrair_texto(FIXTURE_GABARITO.read_bytes())


async def _curar_tj_pa(
    texto_prova: str, texto_gabarito: str, vocabulario: list[TopicoVocabulario]
) -> ResultadoCuradoria:
    """Cura o caderno real da TJ-PA por regras (sem `GOOGLE_API_KEY` nesta máquina)."""
    return await curar(
        texto_prova=texto_prova,
        texto_gabarito=texto_gabarito,
        vocabulario=vocabulario,
        origem_base=ORIGEM_BASE_TJ_PA,
        regra_prova=REGRA_PROVA_TJ_PA,
        classificador_ia=None,
        motivo_sem_ia="sem GOOGLE_API_KEY",
        tamanho_lote=100,
    )


class _ClassificadorComSlugEConfiancaBaixa:
    """Dublê da porta: devolve sempre um slug válido do vocabulário, mas com confiança baixa.

    O classificador por regras real (`ClassificadorPorRegras`) nunca produz essa combinação —
    confiança baixa sempre vem sem slug (Ruling 21 do passo 8, "termo isolado não basta"). Este
    dublê existe só para alcançar o cenário "tópico identificado com confiança baixa" do gate de
    publicação, que o contrato da porta `ClassificadorDeTopico` não proíbe.
    """

    def __init__(self, slug: str) -> None:
        """Guarda o slug que toda chamada de `classificar_lote` vai devolver."""
        self._slug = slug

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        """Devolve, para cada item, o slug fixo com confiança `"baixa"`."""
        classificacoes = [
            Classificacao(
                numero_item=item.numero_item,
                topico_slug=self._slug,
                confianca="baixa",
                evidencia="dublê: slug válido, confiança baixa de propósito",
                origem="ia",
            )
            for item in itens
        ]
        return classificacoes, {}


@pytest.mark.anyio
async def test_segmentacao_ambigua_vira_pendente_revisao(
    vocabulario: list[TopicoVocabulario],
) -> None:
    """Bloco com 3 fronteiras de comando candidatas (`SegmentacaoAmbigua`) — tudo pendente."""
    resultado = await curar(
        texto_prova=_TEXTO_PROVA_SEGMENTACAO_AMBIGUA,
        texto_gabarito=_TEXTO_GABARITO_INVALIDO,  # nunca chega a ser lido — a exceção é antes
        vocabulario=vocabulario,
        origem_base=ORIGEM_BASE_TJ_PA,
        regra_prova=REGRA_PROVA_TJ_PA,
        classificador_ia=None,
        motivo_sem_ia="sem GOOGLE_API_KEY",
        tamanho_lote=100,
    )

    assert resultado.pendente_revisao is True
    assert resultado.questoes == []
    assert any("fronteiras de comando candidatas" in problema for problema in resultado.problemas)


@pytest.mark.anyio
async def test_gabarito_nao_reconhecido_vira_pendente_revisao(
    vocabulario: list[TopicoVocabulario],
) -> None:
    """Texto de gabarito sem nenhuma grade reconhecível (`GabaritoNaoReconhecido`) — pendente."""
    resultado = await curar(
        texto_prova=_TEXTO_PROVA_SINTETICO,
        texto_gabarito=_TEXTO_GABARITO_INVALIDO,
        vocabulario=vocabulario,
        origem_base=ORIGEM_BASE_TJ_PA,
        regra_prova=REGRA_PROVA_TJ_PA,
        classificador_ia=None,
        motivo_sem_ia="sem GOOGLE_API_KEY",
        tamanho_lote=100,
    )

    assert resultado.pendente_revisao is True
    assert resultado.questoes == []
    assert any("gabarito Cebraspe" in problema for problema in resultado.problemas)


@pytest.mark.anyio
async def test_saida_no_contrato_da_skill(
    texto_prova_real: str, texto_gabarito_real: str, vocabulario: list[TopicoVocabulario]
) -> None:
    """`curar` sobre o caderno real devolve 70 `QuestaoCurada` com todos os campos do contrato."""
    resultado = await _curar_tj_pa(texto_prova_real, texto_gabarito_real, vocabulario)

    assert resultado.pendente_revisao is False
    assert resultado.problemas == []
    assert len(resultado.questoes) == N_ITENS_TJ_PA
    for questao in resultado.questoes:
        dados = questao.model_dump()
        for campo in CAMPOS_OBRIGATORIOS:
            assert campo in dados, f"campo {campo} ausente em {questao.numero_item}"
        assert questao.justificativa_certo is None
        assert questao.justificativa_errado is None
        assert questao.publicado is False


@pytest.mark.anyio
async def test_origem_com_oito_campos(
    texto_prova_real: str, texto_gabarito_real: str, vocabulario: list[TopicoVocabulario]
) -> None:
    """`origem` traz os 8 campos, com `url_prova`/`documento_id` iguais aos do `Documento`."""
    resultado = await _curar_tj_pa(texto_prova_real, texto_gabarito_real, vocabulario)

    for questao in resultado.questoes:
        origem = questao.origem
        assert origem.banca == ORIGEM_BASE_TJ_PA.banca
        assert origem.orgao == ORIGEM_BASE_TJ_PA.orgao
        assert origem.cargo == ORIGEM_BASE_TJ_PA.cargo
        assert origem.ano == ORIGEM_BASE_TJ_PA.ano
        assert origem.numero_item == questao.numero_item
        assert origem.tipo_caderno == ORIGEM_BASE_TJ_PA.tipo_caderno
        # nunca remontados: exatamente os valores passados, vindos do `Documento` do passo 5.
        assert origem.url_prova == ORIGEM_BASE_TJ_PA.url_prova
        assert origem.documento_id == ORIGEM_BASE_TJ_PA.documento_id


@pytest.mark.anyio
async def test_anulado_nao_publicavel(
    texto_prova_real: str, texto_gabarito_real: str, vocabulario: list[TopicoVocabulario]
) -> None:
    """Os 5 itens anulados do caderno real ficam sem gabarito e não publicáveis."""
    resultado = await _curar_tj_pa(texto_prova_real, texto_gabarito_real, vocabulario)
    por_numero = {questao.numero_item: questao for questao in resultado.questoes}

    for numero in ANULADOS_TJ_PA:
        questao = por_numero[numero]
        assert questao.gabarito is None
        assert questao.gabarito_status == "anulado"
        assert questao.publicavel is False
        assert questao.motivo_nao_publicavel is not None
        assert questao.motivo_nao_publicavel.startswith("anulado")


@pytest.mark.anyio
async def test_sem_gabarito_nao_publicavel(vocabulario: list[TopicoVocabulario]) -> None:
    """Contagem bate (3 itens, 3 entradas), mas o item 53 não tem entrada própria."""
    resultado = await curar(
        texto_prova=_TEXTO_PROVA_SINTETICO,
        texto_gabarito=_TEXTO_GABARITO_SINTETICO_SEM_53,
        vocabulario=vocabulario,
        origem_base=ORIGEM_BASE_TJ_PA,
        regra_prova=REGRA_PROVA_TJ_PA,
        classificador_ia=None,
        motivo_sem_ia="sem GOOGLE_API_KEY",
        tamanho_lote=100,
    )

    assert resultado.pendente_revisao is False
    por_numero = {questao.numero_item: questao for questao in resultado.questoes}
    questao_53 = por_numero[53]
    assert questao_53.gabarito is None
    assert questao_53.gabarito_status == "sem_gabarito"
    assert questao_53.publicavel is False
    assert questao_53.motivo_nao_publicavel == "sem gabarito"


@pytest.mark.anyio
async def test_confianca_baixa_nao_publicavel(vocabulario: list[TopicoVocabulario]) -> None:
    """Slug válido do vocabulário, mas confiança baixa: motivo distingue de "sem tópico".

    O classificador por regras real nunca produz essa combinação (Ruling 21 do passo 8) — por
    isso o dublê `_ClassificadorComSlugEConfiancaBaixa` força o cenário.
    """
    slug_valido = vocabulario[0].slug
    resultado = await curar(
        texto_prova=_TEXTO_PROVA_SINTETICO,
        texto_gabarito=_TEXTO_GABARITO_SINTETICO_SEM_53,
        vocabulario=vocabulario,
        origem_base=ORIGEM_BASE_TJ_PA,
        regra_prova=REGRA_PROVA_TJ_PA,
        classificador_ia=_ClassificadorComSlugEConfiancaBaixa(slug_valido),
        motivo_sem_ia=None,
        tamanho_lote=100,
    )

    questao_51 = next(q for q in resultado.questoes if q.numero_item == 51)
    assert questao_51.topico_slug == slug_valido
    assert questao_51.topico_confianca == "baixa"
    assert questao_51.publicavel is False
    assert questao_51.motivo_nao_publicavel == "tópico identificado com confiança baixa"


@pytest.mark.anyio
async def test_sem_topico_nao_publicavel(
    texto_prova_real: str, texto_gabarito_real: str, vocabulario: list[TopicoVocabulario]
) -> None:
    """Item 52 real: só o termo isolado "jurídicas" casa — sem slug, "tópico não identificado"."""
    resultado = await _curar_tj_pa(texto_prova_real, texto_gabarito_real, vocabulario)
    questao_52 = next(q for q in resultado.questoes if q.numero_item == 52)

    assert questao_52.topico_slug is None
    assert questao_52.topico_confianca == "baixa"
    assert questao_52.publicavel is False
    assert questao_52.motivo_nao_publicavel == "tópico não identificado"


@pytest.mark.anyio
async def test_contagem_divergente_para_tudo(vocabulario: list[TopicoVocabulario]) -> None:
    """3 itens no caderno sintético, gabarito sintético com 2 entradas — tudo pendente."""
    resultado = await curar(
        texto_prova=_TEXTO_PROVA_SINTETICO,
        texto_gabarito=_TEXTO_GABARITO_SINTETICO_2_ENTRADAS,
        vocabulario=vocabulario,
        origem_base=ORIGEM_BASE_TJ_PA,
        regra_prova=REGRA_PROVA_TJ_PA,
        classificador_ia=None,
        motivo_sem_ia="sem GOOGLE_API_KEY",
        tamanho_lote=100,
    )

    assert resultado.pendente_revisao is True
    assert resultado.questoes == []
    assert any("itens (3) ≠ gabarito (2)" in problema for problema in resultado.problemas)


def test_hash_dedup_normaliza() -> None:
    """Dois enunciados iguais a menos de espaço/quebra de linha têm o mesmo `hash_dedup`."""
    com_quebras = "O diálogo competitivo é modalidade   de licitação\nrestrita a inovação."
    sem_quebras = "O diálogo competitivo é modalidade de licitação restrita a inovação."

    assert hash_dedup(com_quebras) == hash_dedup(sem_quebras)
    assert hash_dedup(com_quebras) != hash_dedup(sem_quebras + " diferente")


def _origem_valida(**overrides: str | int | None) -> Origem:
    # `tipo_caderno=None` por padrão — é o valor legítimo quando a fonte não declara (Ruling 25
    # do passo 9), e o padrão aqui prova que `None` não quebra o gate nem a verificação.
    base: dict[str, str | int | None] = {
        "banca": "cebraspe",
        "orgao": "TJ-PA",
        "cargo": "Analista Judiciário — Direito",
        "ano": 2025,
        "numero_item": 51,
        "tipo_caderno": None,
        "url_prova": "https://exemplo.org/prova.pdf",
        "documento_id": "doc-1",
    }
    base.update(overrides)
    return Origem.model_validate(base)


def _questao_valida(
    *,
    numero_item: int = 51,
    comando: str | None = "Julgue o item.",
    texto_apoio: str | None = None,
    texto_apoio_itens: list[int] | None = None,
    gabarito: Literal["C", "E"] | None = "C",
    gabarito_status: GabaritoStatus = "definitivo",
    publicavel: bool = True,
    motivo_nao_publicavel: str | None = None,
    origem: Origem | None = None,
) -> QuestaoCurada:
    return QuestaoCurada(
        banca="cebraspe",
        numero_item=numero_item,
        comando=comando,
        texto_apoio=texto_apoio,
        texto_apoio_itens=texto_apoio_itens or [],
        enunciado="Um enunciado qualquer.",
        gabarito_preliminar=None,
        gabarito=gabarito,
        gabarito_status=gabarito_status,
        publicavel=publicavel,
        motivo_nao_publicavel=motivo_nao_publicavel,
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug="dir-adm-01-principios-administracao",
        topico_confianca="alta",
        topico_evidencia="evidência qualquer",
        origem=origem or _origem_valida(numero_item=numero_item),
        hash_dedup="hash-fixo",
    )


def test_verificar_curadoria() -> None:
    """As 5 verificações da skill; cada violação devolve mensagem própria."""
    # 1. contagem: tamanho da saída diferente do total de itens do caderno.
    problemas = verificar_curadoria([_questao_valida()], total_itens=2)
    assert any("total de questões" in problema for problema in problemas)

    # 1b. numero_item duplicado na saída (mesma checagem da skill: "cada numero_item aparece
    # uma vez").
    problemas = verificar_curadoria(
        [_questao_valida(numero_item=51), _questao_valida(numero_item=51)], total_itens=2
    )
    assert any("duplicado" in problema for problema in problemas)

    # 2. item dentro de um bloco de texto de apoio sem o próprio texto_apoio preenchido.
    questao_com_apoio = _questao_valida(
        numero_item=51, texto_apoio="texto de apoio do bloco", texto_apoio_itens=[51, 52]
    )
    questao_sem_apoio = _questao_valida(numero_item=52, texto_apoio=None, texto_apoio_itens=[])
    problemas = verificar_curadoria([questao_com_apoio, questao_sem_apoio], total_itens=2)
    assert any("texto_apoio" in problema and "52" in problema for problema in problemas)

    # 3a. item sem comando quando outro item do mesmo caderno tem comando preenchido — suspeita.
    problemas = verificar_curadoria(
        [
            _questao_valida(numero_item=51, comando="Julgue o item."),
            _questao_valida(numero_item=52, comando=None),
        ],
        total_itens=2,
    )
    assert any("sem comando" in problema for problema in problemas)

    # 3b. caderno inteiro sem comando nenhum — caso permitido pela skill, sem violação.
    problemas = verificar_curadoria(
        [
            _questao_valida(numero_item=51, comando=None),
            _questao_valida(numero_item=52, comando=None),
        ],
        total_itens=2,
    )
    assert not any("sem comando" in problema for problema in problemas)

    # 4. anulado com gabarito preenchido (o outro lado desta checagem, "publicado: true" na
    # saída do curador, é impedido pelo próprio tipo de `QuestaoCurada.publicado`, que só aceita
    # `False` — não há como construir a violação para testar).
    problemas = verificar_curadoria(
        [
            _questao_valida(
                gabarito_status="anulado",
                gabarito="C",
                publicavel=False,
                motivo_nao_publicavel="anulado — gabarito não é servido ao aluno",
            )
        ],
        total_itens=1,
    )
    assert any(
        "anulado" in problema and "gabarito preenchido" in problema for problema in problemas
    )

    # 5. origem com campo vazio.
    problemas = verificar_curadoria(
        [_questao_valida(origem=_origem_valida(orgao=""))], total_itens=1
    )
    assert any("origem incompleta" in problema for problema in problemas)

    # Caso sem nenhuma violação: lista vazia.
    assert verificar_curadoria([_questao_valida()], total_itens=1) == []


def test_decidir_publicacao_publica_quando_tudo_ok() -> None:
    """Gabarito definitivo, origem completa, tópico do vocabulário e confiança alta: publica."""
    publicavel, motivo = decidir_publicacao(
        gabarito_status="definitivo",
        topico_slug="dir-adm-01-principios-administracao",
        topico_confianca="alta",
        slugs_validos={"dir-adm-01-principios-administracao"},
        origem=_origem_valida(),
    )

    assert publicavel is True
    assert motivo is None


def test_decidir_publicacao_origem_incompleta() -> None:
    """Origem com campo vazio barra a publicação mesmo com gabarito e tópico em ordem."""
    publicavel, motivo = decidir_publicacao(
        gabarito_status="definitivo",
        topico_slug="dir-adm-01-principios-administracao",
        topico_confianca="alta",
        slugs_validos={"dir-adm-01-principios-administracao"},
        origem=_origem_valida(documento_id=""),
    )

    assert publicavel is False
    assert motivo == "origem incompleta"

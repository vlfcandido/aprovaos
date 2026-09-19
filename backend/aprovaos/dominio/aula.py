"""Contrato da `Aula` e o validador mecânico que decide se ela publica (fatia 6).

O que é: os modelos Pydantic do que o agente `gerador-de-aula` recebe (`EntradaGeradorAula`,
`RelacionadoEntrada`, `QuestaoParaAula`) e devolve (`ConteudoAula`, `CitacaoAula`,
`RelacionadoAula`, `ComoABancaCobra`, `MnemonicoAula`); `verificar_aula`, o validador mecânico,
no mesmo espírito de `dominio.justificativa.verificar_justificativa_*` — toda afirmação de lei ou
jurisprudência aponta uma fonte do dossiê e o trecho citado existe **literalmente** nela;
`escolher_relacionados`, que monta o fio da memória (a) reaproveitando o ranking de
`dominio.fio_memoria.escolher_para_intercalar`; e `renderizar_com_notas`, que troca os marcadores
`{{citação}}` do texto por notas numeradas para a tela (o popover de lei, mesmo princípio de
`dominio.justificativa.separar_afirmacoes`).

**Correção crítica de 19/09/2026** (revisão independente do caminho de conteúdo gerado, visão
§4 "nada gerado existe para o aluno sem validação"): três defeitos deste validador deixavam
metade do conteúdo da aula sem checagem nenhuma. `verificar_aula` agora trata `texto_denso` e
`texto_leigo` **simetricamente** (o conjunto de marcadores verificado é a união dos dois; a regra
de lacuna vale para os dois — antes só o denso era conferido, e o leigo podia citar dispositivo
inexistente ou afirmar o que a aula declarou como lacuna sem ser pego); aplica um **gate léxico**
que reprova qualquer frase com palavra de competência/vedação/prazo/quórum ou número sem
`{{citação}}` própria — decisão consciente do dono (mais falso positivo, nunca afirmação sem
fonte; ver `.claude/skills/gerador-de-aula/SKILL.md`); e reprova qualquer `<letra` nos dois
textos (não deveria haver tag alguma vindo do gerador — a tela também parou de confiar nesse
texto com `| safe`, `web/templates/aula/ver.html`).

Nenhuma chamada de rede, banco ou LLM acontece aqui — só validação de texto e uma função pura de
ranking. Quando ler: antes de mudar o prompt do `gerador-de-aula`; ao investigar por que uma aula
boa (ou ruim) foi aprovada/reprovada; ao mexer no fio da memória (a) ou no popover da tela de
aula. Plano: `docs/fatias/6-trilha-e-aulas.md`.
"""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from aprovaos.dominio.citacao import normalizar_citacao_para_comparacao
from aprovaos.dominio.dossie import FonteDossie
from aprovaos.dominio.edital import sem_acento
from aprovaos.dominio.fio_memoria import EstatisticaTopicoVisto, escolher_para_intercalar


class QuestaoParaAula(BaseModel):
    """Uma questão publicada real, oferecida ao gerador para `como_a_banca_cobra`.

    Attributes:
        origem: string estável (`"<banca> <ano> <órgão> item <nº>"`) — a única forma que o
            gerador pode citar em `ComoABancaCobra.origem` (regra 6 do validador).
        enunciado: o texto da questão, para o gerador identificar o padrão da banca.
    """

    origem: str
    enunciado: str


class RelacionadoEntrada(BaseModel):
    """Um tópico já visto pela aluna, com dossiê próprio — candidato ao fio da memória (a).

    Attributes:
        topico_slug: o tópico relacionado (nunca o tópico atual da aula).
        dias_atras: há quantos dias ela viu esse tópico pela última vez.
        acertos: quantas vezes ela acertou questões desse tópico.
        total: quantas vezes ela respondeu questões desse tópico.
        trecho_do_dossie_relacionado: um trecho real do dossiê do tópico relacionado — o gerador
            só pode citar esse trecho, nunca inventar um (regra 5 do validador).
    """

    topico_slug: str
    dias_atras: int
    acertos: int
    total: int
    trecho_do_dossie_relacionado: str


class EntradaGeradorAula(BaseModel):
    """O que o agente `gerador-de-aula` recebe para escrever a aula de um tópico.

    Attributes:
        topico_slug: o tópico desta aula.
        fontes: as fontes do dossiê (`dominio.dossie.FonteDossie`), a única matéria-prima
            permitida — norma ou súmula, cada uma com `citacao_canonica` e `trecho` literal.
        relacionados: tópicos já vistos com dossiê, para o fio da memória (a); vazio quando não
            há candidato real.
        questoes_como_banca: questões publicadas reais deste tópico, para `como_a_banca_cobra`;
            vazio quando o tópico ainda não tem questão publicável.
        tempo_alvo_min: minutos-alvo da aula — decide o tamanho esperado do `texto_denso`.
    """

    topico_slug: str
    fontes: list[FonteDossie]
    relacionados: list[RelacionadoEntrada]
    questoes_como_banca: list[QuestaoParaAula]
    tempo_alvo_min: int


class CitacaoAula(BaseModel):
    """Uma citação da aula, ligando uma frase do texto a uma fonte do dossiê.

    Attributes:
        canonica: a citação canônica do dispositivo/súmula (ex.: `"CF/88 art. 71 I"`, `"STJ
            Súmula 651"`) — tem de bater com a `citacao_canonica` da fonte apontada por `fonte`.
        fonte: o `id` (`"F-n"`) da fonte do dossiê que sustenta esta citação.
        trecho: o trecho literal da fonte que decide a frase — tem de existir, palavra por
            palavra (substring), no `trecho` daquela fonte.
        frase_da_aula: a frase exata do `texto_denso` que esta citação sustenta — tem de existir
            literalmente no texto (regra 2 do validador).
    """

    canonica: str
    fonte: str
    trecho: str
    frase_da_aula: str


class RelacionadoAula(BaseModel):
    """Uma relação com um tópico já visto, como a aula efetivamente cita (fio da memória (a)).

    Attributes:
        topico_slug: o tópico relacionado — tem de estar entre os `relacionados` oferecidos.
        onde: em que ponto do `texto_denso` a relação aparece (ex.: `"§2"`), para referência.
        frase: o texto da relação, como aparece na aula.
        trecho: o trecho do dossiê relacionado citado — tem de ser **igual** ao
            `trecho_do_dossie_relacionado` daquele tópico na entrada (nunca inventado).
    """

    topico_slug: str
    onde: str
    frase: str
    trecho: str


class ComoABancaCobra(BaseModel):
    """Uma nota de como a banca cobrou este tópico, ancorada numa questão publicada real.

    Attributes:
        origem: tem de ser uma das `QuestaoParaAula.origem` oferecidas na entrada — nunca uma
            origem inventada (regra 6 do validador).
        o_que_testou: o padrão observado (ex.: `"troca de 'aprecia' por 'julga'"`).
    """

    origem: str
    o_que_testou: str


class MnemonicoAula(BaseModel):
    """Um mnemônico opcional gerado junto com a aula (linha 6 do PRD) — mesmo rigor de citação.

    Attributes:
        texto: o mnemônico em si.
        dispositivo: a citação canônica que ele ajuda a lembrar — tem de estar entre as fontes.
        trecho_que_decide: o trecho literal que sustenta o mnemônico — mesma regra de
            `CitacaoAula.trecho`.
    """

    texto: str
    dispositivo: str
    trecho_que_decide: str


class ConteudoAula(BaseModel):
    """O que o agente `gerador-de-aula` devolve — ainda não validado, ainda não publicado.

    Attributes:
        texto_denso: markdown com os marcadores `{{citação}}` inline.
        texto_leigo: reescrita em linguagem cotidiana; `≤ 40 %` do tamanho do denso.
        citacoes: uma entrada por citação usada no `texto_denso`.
        relacionados: o fio da memória (a) — pode ser vazio.
        como_a_banca_cobra: notas de incidência — pode ser vazio.
        lacunas_declaradas: dispositivos que o dossiê não cobre — nunca aparecem como `{{…}}`.
        mnemonico: mnemônico opcional gerado junto (§5 do plano); `None` quando não coube.
    """

    texto_denso: str
    texto_leigo: str
    citacoes: list[CitacaoAula]
    relacionados: list[RelacionadoAula] = Field(default_factory=list)
    como_a_banca_cobra: list[ComoABancaCobra] = Field(default_factory=list)
    lacunas_declaradas: list[str] = Field(default_factory=list)
    mnemonico: MnemonicoAula | None = None


class VeredictoAula(BaseModel):
    """O que `verificar_aula` decide.

    Attributes:
        aprovado: `True` só quando nenhum motivo de reprovação foi encontrado.
        motivos: os problemas achados; vazio quando `aprovado`.
    """

    aprovado: bool
    motivos: list[str] = Field(default_factory=list)


_MARCADOR = re.compile(r"\{\{([^}]+)\}\}")


def _marcadores(texto: str) -> list[str]:
    """As citações (não normalizadas) marcadas em `texto` (`{{...}}`), na ordem em que aparecem."""
    return [m.strip() for m in _MARCADOR.findall(texto)]


_FIM_DE_FRASE = re.compile(r"[.!?](?!\d)(?=\s+[A-ZÀ-Ú]|\s*$)")
"""Mesmo critério de `dominio.edital._itens_por_sentenca`: `.`/`!`/`?` só fecha frase quando não
separa dígitos (`8.429`, `art. 1`, dentro de um marcador) e o que vem depois começa por
maiúscula ou é o fim do texto — não há lista de abreviação aqui porque o texto da aula não tem
"cap."/"inc." soltos fora de marcador (e um marcador nunca é quebrado por este padrão, já que
`"art. 1"` dentro dele é seguido de dígito ou `}}`, nunca de espaço + maiúscula)."""


def _frases(texto: str) -> list[str]:
    """Fatia `texto` em frases, para o gate léxico avaliar cada uma isoladamente."""
    frases: list[str] = []
    inicio = 0
    for candidato in _FIM_DE_FRASE.finditer(texto):
        fim = candidato.start() + 1
        frase = texto[inicio:fim].strip()
        if frase:
            frases.append(frase)
        inicio = fim
    resto = texto[inicio:].strip()
    if resto:
        frases.append(resto)
    return frases


_GATILHO_NORMATIVO = re.compile(r"\b(compete|vedado|vedada|somente|apenas|so|prazo|quorum)\b")
"""Palavras que, segundo a skill `gerador-de-aula` (SKILL.md, regra "toda frase com 'compete',
'é vedado', 'só', 'prazo', número, quórum ou verbo de competência tem `{{citação}}`"), marcam uma
frase normativa — comparada sem acento e em minúsculas (`sem_acento`), por isso "só" vira "so" e
"quórum" vira "quorum" aqui."""

_TEM_DIGITO = re.compile(r"\d")

_TAG_HTML = re.compile(r"<[A-Za-zÀ-ÿ]")
"""`<` seguido de letra — o gerador não tem motivo para emitir marcação; texto com isso não é
markdown legítimo (C3 da correção crítica de 19/09/2026)."""


def _frase_exige_citacao(frase: str) -> bool:
    """`True` quando `frase` bate o gatilho léxico normativo (gate léxico, C2)."""
    return bool(_GATILHO_NORMATIVO.search(sem_acento(frase).lower()) or _TEM_DIGITO.search(frase))


def verificar_aula(
    conteudo: ConteudoAula,
    *,
    fontes: list[FonteDossie],
    relacionados_permitidos: set[str],
    origens_permitidas: set[str],
    tempo_alvo_min: int,
    trechos_relacionados_esperados: dict[str, str] | None = None,
    margem_tamanho: float = 0.2,
    frases_excecao_gate_lexico: frozenset[str] = frozenset(),
) -> VeredictoAula:
    """Valida mecanicamente uma `ConteudoAula` contra o dossiê e o que foi oferecido ao gerador.

    Ver `docs/fatias/6-trilha-e-aulas.md` §1 para a lista comentada de cada regra e o cabeçalho
    do módulo para a correção crítica de 19/09/2026 (texto_leigo simétrico ao denso, gate
    léxico, rejeição de tag HTML).

    Args:
        conteudo: a saída do agente `gerador-de-aula`.
        fontes: as fontes do dossiê oferecidas na entrada (a única matéria-prima permitida).
        relacionados_permitidos: os `topico_slug` oferecidos em `relacionados` na entrada.
        origens_permitidas: as `QuestaoParaAula.origem` oferecidas na entrada.
        tempo_alvo_min: minutos-alvo — decide a faixa de tamanho esperada do `texto_denso`.
        trechos_relacionados_esperados: `topico_slug -> trecho_do_dossie_relacionado` da entrada,
            para conferir que `RelacionadoAula.trecho` não foi inventado; `None` não confere
            (usado só quando o chamador não tem esse dado à mão).
        margem_tamanho: tolerância (fração) da faixa de tamanho do `texto_denso`.
        frases_excecao_gate_lexico: frases inteiras (match exato, após `_frases`) dispensadas do
            gate léxico — só para falso positivo óbvio e explícito; **vazio por padrão**, porque
            o padrão desta regra é reprovar (decisão do dono, correção crítica de 19/09/2026).

    Returns:
        `VeredictoAula` com `aprovado=True` só quando nenhum motivo de reprovação foi encontrado.
    """
    motivos: list[str] = []
    fontes_por_id = {fonte.id: fonte for fonte in fontes}
    canonicas_das_citacoes: set[str] = set()

    for citacao in conteudo.citacoes:
        fonte = fontes_por_id.get(citacao.fonte)
        if fonte is None:
            motivos.append(
                f"citação {citacao.canonica!r} aponta fonte {citacao.fonte!r} inexistente no dossiê"
            )
            continue
        if normalizar_citacao_para_comparacao(
            citacao.canonica
        ) != normalizar_citacao_para_comparacao(fonte.citacao_canonica):
            motivos.append(
                f"citação {citacao.canonica!r} não corresponde à fonte {citacao.fonte!r} "
                f"({fonte.citacao_canonica!r})"
            )
            continue
        canonicas_das_citacoes.add(normalizar_citacao_para_comparacao(citacao.canonica))
        if not citacao.trecho.strip():
            motivos.append(f"citação {citacao.canonica!r}: trecho vazio")
        elif citacao.trecho not in fonte.trecho:
            motivos.append(
                f"citação {citacao.canonica!r}: trecho não existe literalmente "
                f"na fonte {citacao.fonte!r}"
            )
        if not citacao.frase_da_aula.strip() or citacao.frase_da_aula not in conteudo.texto_denso:
            motivos.append(
                f"citação {citacao.canonica!r}: frase_da_aula não existe literalmente "
                "no texto_denso"
            )

    # C1 (correção crítica de 19/09/2026): união dos marcadores do denso e do leigo — antes só o
    # denso entrava aqui, e o leigo podia citar dispositivo inexistente sem ser pego.
    marcadores_no_texto = {
        normalizar_citacao_para_comparacao(marcador)
        for marcador in _marcadores(conteudo.texto_denso) + _marcadores(conteudo.texto_leigo)
    }
    orfaos = marcadores_no_texto - canonicas_das_citacoes
    for orfao in orfaos:
        motivos.append(f"marcador {{{{{orfao}}}}} sem citação correspondente em citacoes")

    # C1: a regra de lacuna também usa a união denso+leigo — antes só pegava lacuna citada no
    # denso; o leigo podia afirmar o que a aula declarou como lacuna sem ser pego.
    for lacuna in conteudo.lacunas_declaradas:
        if normalizar_citacao_para_comparacao(lacuna) in marcadores_no_texto:
            motivos.append(f"lacuna declarada {lacuna!r} aparece como citação na aula")

    for relacionado in conteudo.relacionados:
        if relacionado.topico_slug not in relacionados_permitidos:
            motivos.append(f"relacionado com tópico {relacionado.topico_slug!r} fora do oferecido")
            continue
        if trechos_relacionados_esperados is not None:
            esperado = trechos_relacionados_esperados.get(relacionado.topico_slug)
            if esperado is not None and relacionado.trecho != esperado:
                motivos.append(
                    f"relacionado com {relacionado.topico_slug!r}: trecho não é "
                    "o oferecido na entrada"
                )

    for nota in conteudo.como_a_banca_cobra:
        if nota.origem not in origens_permitidas:
            motivos.append(f"como_a_banca_cobra com origem {nota.origem!r} fora do oferecido")

    palavras_denso = len(conteudo.texto_denso.split())
    palavras_leigo = len(conteudo.texto_leigo.split())
    if palavras_denso > 0 and palavras_leigo > 0.4 * palavras_denso:
        motivos.append(
            f"texto_leigo tem {palavras_leigo} palavras, mais de 40 % do denso ({palavras_denso})"
        )

    esperado_min = tempo_alvo_min * 36 * (1 - margem_tamanho)
    esperado_max = tempo_alvo_min * 36 * (1 + margem_tamanho)
    if not (esperado_min <= palavras_denso <= esperado_max):
        motivos.append(
            f"tamanho do texto_denso ({palavras_denso} palavras) fora da faixa esperada "
            f"({esperado_min:.0f}–{esperado_max:.0f}, tempo_alvo_min={tempo_alvo_min})"
        )

    if conteudo.mnemonico is not None:
        mnemonico = conteudo.mnemonico
        fonte_mnemonico = next(
            (
                f
                for f in fontes
                if normalizar_citacao_para_comparacao(f.citacao_canonica)
                == normalizar_citacao_para_comparacao(mnemonico.dispositivo)
            ),
            None,
        )
        if fonte_mnemonico is None:
            motivos.append(f"mnemônico cita dispositivo {mnemonico.dispositivo!r} fora do dossiê")
        elif mnemonico.trecho_que_decide not in fonte_mnemonico.trecho:
            motivos.append("mnemônico: trecho_que_decide não existe literalmente na fonte citada")

    # C3 (correção crítica de 19/09/2026): o gerador não tem motivo para emitir tag — a tela
    # também parou de confiar nesse texto com `| safe` (`web/templates/aula/ver.html`).
    campos_e_textos = (
        ("texto_denso", conteudo.texto_denso),
        ("texto_leigo", conteudo.texto_leigo),
    )
    for campo, texto in campos_e_textos:
        casamento = _TAG_HTML.search(texto)
        if casamento is not None:
            trecho = texto[casamento.start() : casamento.start() + 20]
            motivos.append(f"{campo} contém possível tag HTML: {trecho!r}")

    # C2, gate léxico (correção crítica de 19/09/2026, decisão do dono): toda frase com gatilho
    # normativo (compete/vedado/somente/apenas/só/prazo/quórum/número) tem de trazer sua própria
    # `{{citação}}` — sem isso, reprova, mesmo que `citacoes` esteja vazio. Regras primeiro,
    # aceitando falso positivo ocasional; nunca afirmação sem fonte.
    for campo, texto in campos_e_textos:
        for frase in _frases(texto):
            if frase in frases_excecao_gate_lexico:
                continue
            if _frase_exige_citacao(frase) and not _MARCADOR.search(frase):
                motivos.append(f"{campo}: frase com conteúdo normativo sem citação — {frase!r}")

    return VeredictoAula(aprovado=not motivos, motivos=motivos)


def escolher_relacionados(
    topico_atual_id: UUID,
    estatisticas: list[EstatisticaTopicoVisto],
    *,
    trechos_por_topico: dict[UUID, str],
    slugs_por_topico: dict[UUID, str],
    agora: datetime,
    quantidade: int = 1,
) -> list[RelacionadoEntrada]:
    """Escolhe até `quantidade` tópicos já vistos, com dossiê, para o fio da memória (a).

    Reaproveita o ranking de `dominio.fio_memoria.escolher_para_intercalar` (erro mais recente
    primeiro, depois tempo sem ver) restrito aos tópicos que têm um trecho de dossiê disponível
    (`trechos_por_topico`) — só esses podem virar `RelacionadoEntrada` de verdade.

    Args:
        topico_atual_id: o tópico desta aula — nunca entra na lista.
        estatisticas: o histórico agregado (`dados.repositorio_fio_memoria
            .estatisticas_topicos_vistos`); pode incluir tópicos sem dossiê, filtrados aqui.
        trechos_por_topico: um trecho real do dossiê de cada tópico candidato, por `topico_id`.
        slugs_por_topico: `topico_id -> slug`, para os tópicos candidatos.
        agora: instante de referência para "há quantos dias", sempre vindo de fora.
        quantidade: quantos relacionados tentar reunir (padrão 1 — a aula cita um só).

    Returns:
        Até `quantidade` `RelacionadoEntrada`, com placar e trecho reais; vazio se não houver
        nenhum tópico já visto com dossiê.
    """
    elegiveis = [e for e in estatisticas if e.topico_id in trechos_por_topico]
    escolhidos = escolher_para_intercalar(topico_atual_id, elegiveis, agora, quantidade=quantidade)
    por_id = {e.topico_id: e for e in elegiveis}
    relacionados: list[RelacionadoEntrada] = []
    for item in escolhidos:
        estatistica = por_id[item.topico_id]
        dias_atras = max((agora - estatistica.ultima_visita).days, 0)
        relacionados.append(
            RelacionadoEntrada(
                topico_slug=slugs_por_topico[item.topico_id],
                dias_atras=dias_atras,
                acertos=estatistica.total_respostas - estatistica.erros,
                total=estatistica.total_respostas,
                trecho_do_dossie_relacionado=trechos_por_topico[item.topico_id],
            )
        )
    return relacionados


class NotaCitacao(BaseModel):
    """Uma nota de rodapé da tela de aula — o popover de lei sem marcador inline.

    Attributes:
        numero: posição da nota (1, 2, ...).
        rotulo: a citação canônica (`CitacaoAula.canonica`).
        texto: o trecho literal (`CitacaoAula.trecho`).
    """

    numero: int
    rotulo: str
    texto: str


def renderizar_com_notas(texto: str, citacoes: list[CitacaoAula]) -> tuple[str, list[NotaCitacao]]:
    """Troca cada marcador `{{citação}}` de `texto` por uma nota numerada `[n]`.

    A tela de aula usa isso para não mostrar `{{...}}` cru ao aluno: cada `[n]` referencia uma
    `NotaCitacao` na lista devolvida, renderizada com o mesmo `<details>`/`<summary>` que já
    existe no popover de lei do resultado de questão (`web/templates/_macros.html`).

    Args:
        texto: `ConteudoAula.texto_denso` ou `texto_leigo`, com marcadores `{{...}}`.
        citacoes: as citações da aula, para achar o trecho de cada marcador.

    Returns:
        `(texto_sem_marcadores, notas)` — `notas` na ordem em que os marcadores aparecem no
        texto; um marcador sem citação correspondente (não deveria acontecer com texto aprovado
        pelo validador) vira uma nota com `texto=""`, nunca quebra a renderização.
    """
    por_canonica = {
        normalizar_citacao_para_comparacao(citacao.canonica): citacao for citacao in citacoes
    }
    notas: list[NotaCitacao] = []

    def _substituir(casamento: re.Match[str]) -> str:
        rotulo = casamento.group(1).strip()
        citacao = por_canonica.get(normalizar_citacao_para_comparacao(rotulo))
        numero = len(notas) + 1
        notas.append(
            NotaCitacao(numero=numero, rotulo=rotulo, texto=citacao.trecho if citacao else "")
        )
        return f"[{numero}]"

    html = _MARCADOR.sub(_substituir, texto)
    return html, notas

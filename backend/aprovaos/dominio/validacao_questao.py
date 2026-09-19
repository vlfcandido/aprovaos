"""O validador mecânico da inédita — os cinco itens do validador da skill `gerador-questao-banca`.

O que é: `Veredito`, `verificar_forma` (regras de forma por tipo de item — comprimento, uma
afirmação só, comando presente, sem "sempre/nunca" gratuitos, alternativas A–E homogêneas),
`verificar_fontes` (cada `fontes[i]` existe no dossiê e `trecho_que_decide` está nela
literalmente), `similaridade_lexica` (Ruling 43: proxy determinístico de aderência — cosseno de
TF-IDF, stdlib `math`/`collections`, sem embedding) e `julgar` (a soma dos cinco itens do
validador da skill, incluindo o gabarito independente e a "consequência acrescentada" — uma
oração da frase que a fonte não sustenta).

**Ruling 43** (`docs/fatias/5-questoes-ineditas.md`): o item 3 do validador da skill pede
similaridade por *embedding*; nesta fatia ela é medida por (a) regras de forma determinísticas e
(b) similaridade léxica — ambas declaradas como o proxy que são, nunca como "validado por IA".
`aderencia_pct` só existe quando `julgar` recebe 5 ou mais originais; com menos, a skill já manda
gerar sem medir e avisar quem consome.

Nenhuma chamada de rede, banco ou LLM acontece aqui — só comparação de texto e aritmética.

Quando ler: antes de mudar o prompt do `validador-de-questao`; ao investigar por que uma inédita
boa (ou ruim) foi aprovada/reprovada. Plano: `docs/fatias/5-questoes-ineditas.md` §3.
"""

import re

from pydantic import BaseModel, Field

from aprovaos.dominio.dossie import FonteDossie
from aprovaos.dominio.questao import Letra
from aprovaos.dominio.questao_inedita import QuestaoGerada
from aprovaos.dominio.texto import similaridade_lexica

#: Limiar mínimo de `similaridade_lexica` com os originais para o item não ser reprovado por
#: "estilo" (Ruling 43) — cosseno de TF-IDF entre textos curtos raramente passa de 0,3 mesmo
#: entre frases muito parecidas; 0,10 é deliberadamente permissivo (regras primeiro, aceitando
#: falso positivo ocasional — o calibrador, fatia 11, pega pelos números depois).
LIMIAR_ADERENCIA_LEXICA = 0.10

_LIMITE_PALAVRAS_CERTO_ERRADO = 40

_PALAVRAS_GRATUITAS = re.compile(r"\b(sempre|nunca)\b", re.IGNORECASE)

_TOKEN = re.compile(r"[a-zà-úçã-õâ-ûêîô0-9]+", re.IGNORECASE)

#: Marcadores de consequência que a skill documenta como erro clássico ("podendo ser cobradas
#: sem ação judicial", `docs/…/SKILL.md` "Erros que este contrato existe para evitar") — se
#: aparecem no enunciado mas não estão, eles mesmos, no `trecho_que_decide`, é sinal de que o
#: gerador acrescentou uma consequência que a fonte não afirma.
_MARCADORES_DE_CONSEQUENCIA = (
    "podendo",
    "sem necessidade de",
    "automaticamente",
    "independentemente de",
    "mesmo sem",
    "ainda que",
    "dispensada a",
    "dispensado o",
)

_FIM_DE_FRASE = re.compile(r"[.!?](?=\s|$)")


def _sentencas(texto: str) -> list[str]:
    """Divide `texto` em sentenças por pontuação de fim de frase, descartando vazias."""
    partes = _FIM_DE_FRASE.split(texto)
    return [parte.strip() for parte in partes if parte.strip()]


class AlternativaParaValidador(BaseModel):
    """Uma alternativa (A–E) oferecida ao `validador-de-questao` — sem indicar qual é a correta.

    Attributes:
        letra: a letra da alternativa.
        texto: o texto da alternativa.
    """

    letra: Letra
    texto: str


class EntradaValidadorQuestao(BaseModel):
    """O que o agente `validador-de-questao` recebe para resolver o item **sem ver o gabarito**.

    É deliberadamente mais pobre que `dominio.questao_inedita.EntradaGeradorQuestao`: nada de
    `gabarito`, `trecho_que_decide` ou `mecanismo` — só o que um candidato veria na prova mais o
    dossiê, para o validador chegar à própria resposta de forma independente (item 1 do
    validador da skill).

    Attributes:
        tipo_item: `"certo_errado"` ou `"multipla_escolha"`.
        comando: a instrução de julgamento, quando existir.
        enunciado: a afirmação a julgar, ou o enunciado da questão de múltipla escolha.
        alternativas: as cinco alternativas (sem indicar a correta), só em `multipla_escolha`.
        fontes: as mesmas fontes do dossiê oferecidas ao gerador — a única fonte que o validador
            também pode usar para resolver.
    """

    tipo_item: str
    comando: str | None
    enunciado: str
    alternativas: list[AlternativaParaValidador] | None
    fontes: list[FonteDossie]


class ResolucaoValidador(BaseModel):
    """A resposta independente do `validador-de-questao` — só o gabarito a que ele chegou.

    Attributes:
        gabarito: a letra a que o validador chegou, resolvendo o item só com o dossiê.
    """

    gabarito: Letra


class Veredito(BaseModel):
    """O que `julgar` decide sobre uma `QuestaoGerada`.

    Attributes:
        aprovado: `True` só quando nenhum dos cinco itens do validador reprovou.
        motivos: um por regra violada; vazio quando `aprovado`.
        validador_versao: identifica a versão desta lógica de validação (para auditoria — a
            mesma questão pode ser reavaliada por uma versão futura sem perder o histórico).
        aderencia_pct: a `similaridade_lexica` medida contra os originais, ou `None` quando
            `julgar` recebeu menos de 5 originais — nada para comparar de verdade.
    """

    aprovado: bool
    motivos: list[str] = Field(default_factory=list)
    validador_versao: str
    aderencia_pct: float | None


def verificar_forma(item: QuestaoGerada, banca: str) -> list[str]:
    """Regras de forma por tipo de item (tabela "Regras por banca" da skill).

    Em `certo_errado`: exige `comando` preenchido, no máximo 40 palavras no `enunciado`, uma
    única afirmação (mais de uma sentença é reprovada) e ausência de "sempre"/"nunca" gratuitos.
    Em `multipla_escolha`: exige exatamente cinco `alternativas` e tamanhos homogêneos entre
    elas (a mais longa não pode passar do dobro de palavras da mais curta — mesmo espírito do
    gate determinístico de `dominio.aula.verificar_aula`).

    Args:
        item: o item gerado.
        banca: a banca alvo — hoje só para o motivo da mensagem; as regras de forma nesta fatia
            são as mesmas para toda banca C/E ou A–E (a skill não distingue estilo por banca sem
            provas medidas).

    Returns:
        Uma mensagem por regra violada; lista vazia quando o item está conforme.
    """
    motivos: list[str] = []

    if item.tipo_item == "certo_errado":
        if not (item.comando or "").strip():
            motivos.append(f"{banca}: item certo_errado sem comando")
        palavras = item.enunciado.split()
        if len(palavras) > _LIMITE_PALAVRAS_CERTO_ERRADO:
            motivos.append(
                f"{banca}: enunciado com {len(palavras)} palavras, acima do limite de "
                f"{_LIMITE_PALAVRAS_CERTO_ERRADO} palavras"
            )
        if _PALAVRAS_GRATUITAS.search(item.enunciado):
            motivos.append(f"{banca}: enunciado usa 'sempre'/'nunca' gratuito")
        sentencas = _sentencas(item.enunciado)
        if len(sentencas) > 1:
            motivos.append(
                f"{banca}: item certo_errado com mais de uma afirmação ({len(sentencas)} frases)"
            )
    else:
        alternativas = item.alternativas or []
        if len(alternativas) != 5:
            motivos.append(
                f"{banca}: multipla_escolha sem as cinco alternativas ({len(alternativas)})"
            )
        elif alternativas:
            tamanhos = [len(a.texto.split()) for a in alternativas]
            if max(tamanhos) > 2 * max(min(tamanhos), 1):
                motivos.append(f"{banca}: alternativas de tamanho díspar ({tamanhos})")

    return motivos


def verificar_fontes(item: QuestaoGerada, dossie: list[FonteDossie]) -> list[str]:
    """Cada `item.fontes[i]` existe em `dossie` e `item.trecho_que_decide` está nela literalmente.

    `QuestaoGerada.fontes` já exige ao menos um id (`Field(min_length=1)`); esta função reprova
    quando algum desses ids não corresponde a nenhuma `FonteDossie.id` oferecida, ou quando o
    `trecho_que_decide` não é substring literal do `trecho` de nenhuma das fontes de fato
    referenciadas — o mesmo princípio de `dominio.aula.verificar_aula` (citação aponta fonte que
    existe; trecho existe, palavra por palavra, na fonte).

    Args:
        item: o item gerado.
        dossie: as fontes do dossiê oferecidas ao gerador (a única matéria-prima permitida).

    Returns:
        Uma mensagem por problema; lista vazia quando todas as fontes citadas existem e o trecho
        está em ao menos uma delas.
    """
    motivos: list[str] = []
    fontes_por_id = {fonte.id: fonte for fonte in dossie}

    fontes_encontradas: list[FonteDossie] = []
    for fonte_id in item.fontes:
        fonte = fontes_por_id.get(fonte_id)
        if fonte is None:
            motivos.append(f"fonte {fonte_id!r} não existe no dossiê oferecido")
            continue
        fontes_encontradas.append(fonte)

    if fontes_encontradas and not item.trecho_que_decide.strip():
        motivos.append("trecho_que_decide vazio")
    elif fontes_encontradas and not any(
        item.trecho_que_decide in fonte.trecho for fonte in fontes_encontradas
    ):
        motivos.append(
            f"trecho_que_decide não existe literalmente em nenhuma das fontes {item.fontes}"
        )

    return motivos


def _consequencia_acrescentada(enunciado: str, trecho_que_decide: str) -> str | None:
    """O primeiro marcador de consequência presente em `enunciado` mas ausente de `trecho`.

    Args:
        enunciado: o texto do item.
        trecho_que_decide: o trecho literal da fonte que deveria sustentar o item inteiro.

    Returns:
        O marcador encontrado (para a mensagem de reprovação), ou `None` se nenhum apareceu fora
        do trecho.
    """
    enunciado_lower = enunciado.lower()
    trecho_lower = trecho_que_decide.lower()
    for marcador in _MARCADORES_DE_CONSEQUENCIA:
        if marcador in enunciado_lower and marcador not in trecho_lower:
            return marcador
    return None


def julgar(
    item: QuestaoGerada,
    dossie: list[FonteDossie],
    originais: list[str],
    resolucao_independente: str | None,
    *,
    validador_versao: str = "v1-lexico",
    limiar_aderencia: float = LIMIAR_ADERENCIA_LEXICA,
) -> Veredito:
    """Aplica os cinco itens do validador da skill e devolve o `Veredito`.

    Ordem das checagens (todas rodam; motivos se acumulam, não param na primeira):
    1. `resolucao_independente` (a resposta do agente `validador-de-questao`, que não viu o
       gabarito do gerador) diverge de `item.gabarito` → reprova, motivo `"gabarito: ..."`.
       `None` (nenhuma resolução independente disponível) não reprova por si — é o caso de teste
       unitário sem o segundo agente; o comando real (`motor.gerar_questao`) sempre fornece uma.
    2. `verificar_forma`.
    3. `verificar_fontes`.
    4. Aderência: `similaridade_lexica(item.enunciado, originais)` contra `limiar_aderencia`, só
       quando `len(originais) >= 5` — a contagem real de originais recebidos decide, não o
       autorrelato de `item.aderencia_medida` (que é do gerador; o validador confere pelos
       dados que ele mesmo recebeu). Com menos de 5, `aderencia_pct=None` e a checagem é pulada
       (a skill manda gerar sem medir quando há menos de 5 originais, não que o item seja
       automaticamente aprovado ou reprovado por isso).
    5. Consequência acrescentada: um `_MARCADORES_DE_CONSEQUENCIA` presente no `enunciado` mas
       ausente do `trecho_que_decide` → reprova.

    Args:
        item: o item gerado a julgar.
        dossie: as fontes do dossiê oferecidas ao gerador.
        originais: os enunciados das questões originais do mesmo tópico/banca (pode ser vazio).
        resolucao_independente: o gabarito a que o `validador-de-questao` chegou sem ver o do
            gerador; `None` quando essa chamada não foi feita (só em teste).
        validador_versao: gravado no `Veredito` para auditoria.
        limiar_aderencia: o limiar mínimo de `similaridade_lexica` (Ruling 43).

    Returns:
        `Veredito` com `aprovado=True` só quando nenhuma das checagens acima reprovou.
    """
    motivos: list[str] = []

    if resolucao_independente is not None and resolucao_independente != item.gabarito:
        motivos.append(
            f"gabarito: resolução independente diverge (esperado {item.gabarito!r}, "
            f"obteve {resolucao_independente!r})"
        )

    motivos.extend(verificar_forma(item, item.banca_alvo))
    motivos.extend(verificar_fontes(item, dossie))

    aderencia_pct: float | None = None
    if len(originais) >= 5:
        aderencia_pct = similaridade_lexica(item.enunciado, originais)
        if aderencia_pct < limiar_aderencia:
            motivos.append(
                f"estilo: aderência léxica {aderencia_pct:.3f} abaixo do limiar {limiar_aderencia}"
            )

    marcador = _consequencia_acrescentada(item.enunciado, item.trecho_que_decide)
    if marcador is not None:
        motivos.append(f"consequência acrescentada: {marcador!r} não está no trecho_que_decide")

    return Veredito(
        aprovado=not motivos,
        motivos=motivos,
        validador_versao=validador_versao,
        aderencia_pct=aderencia_pct,
    )

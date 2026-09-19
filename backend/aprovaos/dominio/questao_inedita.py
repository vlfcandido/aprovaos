"""Contrato da `QuestaoGerada` (skill `gerador-questao-banca`) e o Passo 0: o plano do lote.

O que é: `QuestaoGerada` — a saída do agente `gerador-de-questao`, campo a campo do contrato da
skill — e `montar_plano_do_lote`/`conferir_lote`, que implementam o "Passo 0" dela: antes de
escrever qualquer item, decidir **quantos** de cada mecanismo e de cada gabarito o lote terá, de
forma determinística (nunca `random`), e depois conferir se o que foi de fato escrito bate com o
plano. `PlanoDoLote.itens` já vem com a atribuição item a item (`mecanismo`, `gabarito`) — é
o que `motor.gerar_questao` usa para pedir, a cada chamada ao gerador, exatamente um item com um
mecanismo e um gabarito prescritos (Ruling 44 do plano da fatia 5: uma chamada ao gerador por
item, não um lote inteiro numa resposta só — mais fácil de auditar contra a cota e, com o plano
já decidido por regras, `conferir_lote` deveria quase sempre fechar em zero divergências).

Nenhuma chamada de rede, banco ou LLM acontece aqui — só modelos Pydantic e aritmética inteira.

Quando ler: antes de mudar o contrato de `QuestaoGerada`; ao investigar por que um lote de
inéditas foi apontado como fora do plano (`conferir_lote`). Plano: `docs/fatias/
5-questoes-ineditas.md` §2.
"""

from typing import Literal

from pydantic import BaseModel, Field

from aprovaos.dominio.dossie import FonteDossie
from aprovaos.dominio.questao import Letra

Mecanismo = Literal[
    "literal",
    "troca_de_verbo",
    "troca_de_competencia",
    "troca_de_quorum",
    "troca_de_prazo",
    "excecao_omitida",
]

#: Ordem fixa dos mecanismos que não são `"literal"` — a mesma do cabeçalho de exemplo da skill
#: (`troca_de_verbo, troca_de_competencia, troca_de_quorum, excecao_omitida, troca_de_prazo`):
#: um lote de resto 4 preenche os quatro primeiros com 1 cada e deixa `troca_de_prazo` em zero.
_ORDEM_MECANISMOS_SEM_LITERAL: tuple[Mecanismo, ...] = (
    "troca_de_verbo",
    "troca_de_competencia",
    "troca_de_quorum",
    "excecao_omitida",
    "troca_de_prazo",
)

_ORDEM_GABARITO_CERTO_ERRADO: tuple[str, ...] = ("C", "E")
_ORDEM_GABARITO_MULTIPLA_ESCOLHA: tuple[str, ...] = ("A", "B", "C", "D", "E")

TipoItem = Literal["certo_errado", "multipla_escolha"]


class AlternativaGerada(BaseModel):
    """Uma alternativa (A–E) de um item de múltipla escolha gerado pelo `gerador-de-questao`.

    Attributes:
        letra: a letra da alternativa.
        texto: o texto da alternativa.
    """

    letra: Letra
    texto: str


class QuestaoGerada(BaseModel):
    """A saída do agente `gerador-de-questao`, campo a campo do contrato da skill.

    Nasce sempre `publicado=False` e com a `marcacao` fixa da skill — só o validador (outro
    agente, fatia 5 §3) decide se ela chega a ser publicável; este contrato representa só o que
    o gerador escreveu, antes de qualquer validação.

    Attributes:
        tipo_item: `"certo_errado"` (Cebraspe C/E) ou `"multipla_escolha"` (A–E).
        banca_alvo: a banca cujo estilo o item tenta imitar.
        comando: a instrução de julgamento (Cebraspe C/E); pode ser `None` em `multipla_escolha`
            quando a instrução já está embutida no `enunciado`.
        enunciado: a afirmação a julgar (`certo_errado`) ou o enunciado da questão
            (`multipla_escolha`).
        alternativas: `None` em `certo_errado`; as cinco alternativas em `multipla_escolha`.
        gabarito: a letra do gabarito (`"C"`/`"E"` ou `"A"`–`"E"` — `Letra` é o superconjunto).
        fontes: os ids `F-n` do dossiê que sustentam o item — nunca vazio.
        trecho_que_decide: o trecho copiado literalmente de uma das `fontes`.
        justificativa_certo: por que o item estaria certo, ancorada no trecho.
        justificativa_errado: por que o item está errado (ou por que a alternativa certa é a
            certa, em `multipla_escolha`), ancorada no trecho.
        mecanismo: o mecanismo de banca usado (ver `Mecanismo`).
        original_de_referencia: identificação da questão original que inspirou o item
            (`"<banca> <ano> <órgão> item <nº>"`).
        topico_slug: o tópico do vocabulário canônico.
        publicado: sempre `False` na saída do gerador — só o validador liga algo.
        marcacao: o rótulo fixo que a skill define para o item recém-gerado, antes da validação.
        aderencia_medida: `True` só quando o gerador recebeu 5 ou mais originais do mesmo
            tópico/banca (o que torna a aderência léxica um proxy com algum lastro).
    """

    tipo_item: TipoItem
    banca_alvo: str
    comando: str | None
    enunciado: str
    alternativas: list[AlternativaGerada] | None
    gabarito: Letra
    fontes: list[str] = Field(min_length=1)
    trecho_que_decide: str
    justificativa_certo: str
    justificativa_errado: str
    mecanismo: Mecanismo
    original_de_referencia: str
    topico_slug: str
    publicado: Literal[False] = False
    marcacao: Literal["inédita validada — pendente"] = "inédita validada — pendente"
    aderencia_medida: bool


class ItemDoPlano(BaseModel):
    """O mecanismo e o gabarito prescritos para um item do lote (Passo 0 da skill).

    Attributes:
        mecanismo: o mecanismo que este item deve usar.
        gabarito: o gabarito que este item deve ter.
    """

    mecanismo: Mecanismo
    gabarito: str


class PlanoDoLote(BaseModel):
    """O plano determinístico de um lote de `n_pedido` inéditas (Passo 0 da skill).

    Attributes:
        n_pedido: quantos itens o lote deve ter.
        originais_recebidos: quantas questões originais do mesmo tópico/banca alimentaram o
            gerador — decide `aderencia_medida`.
        aderencia_medida: `originais_recebidos >= 5`.
        mecanismos: quantos itens de cada mecanismo o lote deve ter; soma bate com `n_pedido`.
        gabaritos: quantos itens de cada gabarito o lote deve ter; soma bate com `n_pedido`.
        itens: a atribuição item a item — `len(itens) == n_pedido`, cada entrada pronta para
            virar o `mecanismo_alvo`/`gabarito_alvo` de uma chamada ao gerador.
    """

    n_pedido: int
    originais_recebidos: int
    aderencia_medida: bool
    mecanismos: dict[Mecanismo, int]
    gabaritos: dict[str, int]
    itens: list[ItemDoPlano]


class OriginalParaGerador(BaseModel):
    """Uma questão original do mesmo tópico/banca, oferecida ao gerador como referência de estilo.

    Attributes:
        enunciado: o texto da questão original, como a banca imprimiu.
        gabarito: o gabarito da original — só para o gerador enxergar o padrão de forma, nunca
            copiado para a inédita.
        alternativas: as alternativas da original, quando `multipla_escolha`; `None` em
            `certo_errado`.
    """

    enunciado: str
    gabarito: str
    alternativas: list[AlternativaGerada] | None = None


class EntradaGeradorQuestao(BaseModel):
    """O que o agente `gerador-de-questao` recebe para escrever **um** item (Ruling 44).

    Uma chamada ao gerador produz um único item, com o mecanismo e o gabarito já prescritos por
    `PlanoDoLote.itens` — não um lote inteiro numa resposta só (mais fácil de auditar contra a
    cota diária do free tier, e o plano já foi decidido por regras, não pelo modelo).

    Attributes:
        topico_slug: o tópico desta inédita.
        banca_alvo: a banca cujo estilo o item deve imitar.
        tipo_item: `"certo_errado"` ou `"multipla_escolha"`.
        fontes: as fontes do dossiê (`F-n | citação | trecho`) — a única matéria-prima permitida.
        originais: até 5 questões originais do mesmo tópico/banca, para referência de estilo.
        mecanismo_alvo: o mecanismo que este item deve usar (do `ItemDoPlano` correspondente).
        gabarito_alvo: o gabarito que este item deve ter (do `ItemDoPlano` correspondente).
        aderencia_medida: `True` quando `len(originais) >= 5` — informa o modelo se a referência
            de estilo é robusta ou escassa.
    """

    topico_slug: str
    banca_alvo: str
    tipo_item: TipoItem
    fontes: list[FonteDossie]
    originais: list[OriginalParaGerador]
    mecanismo_alvo: Mecanismo
    gabarito_alvo: str
    aderencia_medida: bool


def _round_robin(quantidade: int, ordem: tuple[str, ...]) -> list[str]:
    """Distribui `quantidade` unidades por `ordem`, ciclicamente, uma por vez (sem `random`).

    Uma única passada com `quantidade <= len(ordem)` dá exatamente uma unidade aos primeiros
    `quantidade` elementos de `ordem` (o exemplo do cabeçalho da skill: resto 4 em 5 mecanismos
    dá 1 aos quatro primeiros e 0 ao quinto); `quantidade` maior dá voltas completas antes de
    fechar a última parcial — sempre na mesma ordem, então o resultado é reproduzível.

    Args:
        quantidade: quantas unidades distribuir.
        ordem: as chaves candidatas, na ordem de preferência.

    Returns:
        A sequência de `quantidade` chaves, uma por unidade, na ordem em que foram atribuídas.
    """
    sequencia: list[str] = []
    for indice in range(quantidade):
        sequencia.append(ordem[indice % len(ordem)])
    return sequencia


def montar_plano_do_lote(
    n_pedido: int, originais_recebidos: int, tipo_item: TipoItem
) -> PlanoDoLote:
    """Monta o plano determinístico de um lote de `n_pedido` inéditas (Passo 0 da skill).

    `literal = n_pedido // 5` (nunca mais que um a cada cinco itens); o resto é distribuído nos
    demais mecanismos por `_round_robin`, sempre na mesma ordem fixa. O gabarito é distribuído
    por `_round_robin` sobre `"C"/"E"` (aproximadamente 50/50, `certo_errado`) ou `"A"`–`"E"`
    (`multipla_escolha`). `itens[i]` pareia o mecanismo e o gabarito de mesmo índice das duas
    sequências — os dois eixos são independentes, então o pareamento por posição é só uma forma
    determinística de decidir; o que importa (e o que `conferir_lote` audita depois) são as
    contagens totais.

    Args:
        n_pedido: quantos itens o lote deve ter; tem de ser positivo.
        originais_recebidos: quantas questões originais do mesmo tópico/banca foram oferecidas
            ao gerador.
        tipo_item: `"certo_errado"` ou `"multipla_escolha"` — decide o alfabeto de gabarito.

    Returns:
        O `PlanoDoLote` completo, com `itens` já pronto para orientar uma chamada ao gerador por
        item (Ruling 44 do plano da fatia 5).

    Raises:
        ValueError: `n_pedido <= 0`.
    """
    if n_pedido <= 0:
        raise ValueError(f"n_pedido tem de ser positivo, recebeu {n_pedido!r}")

    n_literal = n_pedido // 5
    resto = n_pedido - n_literal
    sequencia_resto = _round_robin(resto, _ORDEM_MECANISMOS_SEM_LITERAL)

    mecanismos: dict[Mecanismo, int] = {"literal": n_literal}
    for mecanismo in _ORDEM_MECANISMOS_SEM_LITERAL:
        mecanismos[mecanismo] = sequencia_resto.count(mecanismo)

    ordem_gabarito = (
        _ORDEM_GABARITO_CERTO_ERRADO
        if tipo_item == "certo_errado"
        else _ORDEM_GABARITO_MULTIPLA_ESCOLHA
    )
    sequencia_gabarito = _round_robin(n_pedido, ordem_gabarito)
    gabaritos = {letra: sequencia_gabarito.count(letra) for letra in ordem_gabarito}

    sequencia_mecanismos = ["literal"] * n_literal + sequencia_resto
    itens = [
        ItemDoPlano(mecanismo=mecanismo, gabarito=gabarito)
        for mecanismo, gabarito in zip(sequencia_mecanismos, sequencia_gabarito, strict=True)
    ]

    return PlanoDoLote(
        n_pedido=n_pedido,
        originais_recebidos=originais_recebidos,
        aderencia_medida=originais_recebidos >= 5,
        mecanismos=mecanismos,
        gabaritos=gabaritos,
        itens=itens,
    )


def conferir_lote(itens: list[QuestaoGerada], plano: PlanoDoLote) -> list[str]:
    """Confere se o lote de fato escrito bate com `plano` (Passo 0 da skill).

    A skill é explícita: "contagem final ≠ plano (mecanismo ou gabarito) → reescreva o item
    excedente antes de entregar" — esta função só aponta a divergência (em pt-BR, pronta para o
    relatório do comando); quem decide reescrever ou aceitar assim mesmo é `motor.gerar_questao`.

    Args:
        itens: os itens de fato gerados nesta rodada (só os que o gerador devolveu; itens que
            falharam antes de chegar aqui não entram).
        plano: o `PlanoDoLote` que orientou a rodada.

    Returns:
        Uma mensagem por divergência; lista vazia quando o lote está conforme o plano.
    """
    divergencias: list[str] = []
    if len(itens) != plano.n_pedido:
        divergencias.append(
            f"quantidade de itens ({len(itens)}) diferente do n_pedido ({plano.n_pedido})"
        )

    contagem_mecanismo: dict[str, int] = {}
    contagem_gabarito: dict[str, int] = {}
    for item in itens:
        contagem_mecanismo[item.mecanismo] = contagem_mecanismo.get(item.mecanismo, 0) + 1
        contagem_gabarito[item.gabarito] = contagem_gabarito.get(item.gabarito, 0) + 1

    for mecanismo, esperado in plano.mecanismos.items():
        obtido = contagem_mecanismo.get(mecanismo, 0)
        if obtido != esperado:
            divergencias.append(f"mecanismo {mecanismo!r}: esperado {esperado}, obteve {obtido}")
    for mecanismo_extra in set(contagem_mecanismo) - set(plano.mecanismos):
        divergencias.append(
            f"mecanismo {mecanismo_extra!r}: fora do plano ({contagem_mecanismo[mecanismo_extra]})"
        )

    for gabarito, esperado in plano.gabaritos.items():
        obtido = contagem_gabarito.get(gabarito, 0)
        if obtido != esperado:
            divergencias.append(f"gabarito {gabarito!r}: esperado {esperado}, obteve {obtido}")
    for gabarito_extra in set(contagem_gabarito) - set(plano.gabaritos):
        divergencias.append(
            f"gabarito {gabarito_extra!r}: fora do plano ({contagem_gabarito[gabarito_extra]})"
        )

    return divergencias

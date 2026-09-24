"""Previsão de nota v0 (RF-18) — fatia 10 §5 do plano.

O que é: `DesempenhoMateria` (a proficiência medida — ou não — em cada matéria da prova) e
`Previsao` (nota com intervalo, confiança e lacunas declaradas), mais a função pura
`prever_nota`. Os textos que saem daqui são lidos pela aluna, não por quem escreveu a conta: sem
"p.p.", sem "banda", sem "cobertura" — `docs/08-sistema-de-design.md` §6. A nota é a combinação
linear das bandas de Wilson de cada matéria, ponderada pelo
peso de questões — conservadora e explicável, nunca uma simulação. Sem corte histórico do
concurso, a probabilidade de aprovação fica declarada como lacuna (P-17/P-39): esta fatia nunca
fabrica um número de probabilidade. Quando ler: ao mudar o critério de confiança ou como o corte
histórico entra na comparação. Plano: `docs/fatias/10-painel.md` §5.
"""

from typing import Literal

from pydantic import BaseModel

from aprovaos.dominio.estatistica import Proporcao

Confianca = Literal["baixa", "media", "alta"]

#: Banda máxima (pontos percentuais) e cobertura mínima do peso da prova para `confianca="alta"`.
BANDA_MAXIMA_ALTA = 10.0
COBERTURA_MINIMA_ALTA = 0.8

#: Banda máxima e cobertura mínima para `confianca="media"` (abaixo disso, "baixa").
BANDA_MAXIMA_MEDIA = 20.0
COBERTURA_MINIMA_MEDIA = 0.5


class DesempenhoMateria(BaseModel):
    """A proficiência de uma matéria da prova, medida ou não.

    Attributes:
        materia: nome da matéria.
        proporcao: a banda de Wilson medida nas respostas desta matéria; `None` quando a aluna
            ainda não respondeu nenhuma questão dela — nunca um valor fabricado (zero ou média das
            outras matérias) para representar a ausência de dado.
        peso_questoes: quantas questões da prova são desta matéria (do DNA do concurso).
    """

    materia: str
    proporcao: Proporcao | None
    peso_questoes: int


class Previsao(BaseModel):
    """A previsão de nota v0: sempre com intervalo, nunca com número inventado.

    Attributes:
        nota_pct: ponto estimado da nota, média das proficiências ponderada por `peso_questoes`.
        nota_inferior_pct: limite inferior da banda (mesma ponderação aplicada aos limites de
            Wilson de cada matéria).
        nota_superior_pct: limite superior da banda.
        confianca: `"alta"`, `"media"` ou `"baixa"` — ver `prever_nota` para o critério exato.
        incerta: `True` quando a confiança é baixa — ou a faixa é larga demais, ou boa parte da
            prova ainda não foi medida. Nos dois casos o ponto estimado engana como manchete
            ("47,6 %" quando a faixa vai de 18 % a 85 % não informa nada), e quem chama deve
            liderar o bloco pela incerteza, com o número como detalhe.
        o_que_falta: o próximo passo que estreita a faixa, em uma frase de ação ("Responda
            questões de Língua Portuguesa e Matemática — …"); `None` só quando a confiança é alta
            **e** nenhuma matéria está em branco. Confiança sem caminho é um rótulo ruim.
        materias_sem_dado: as matérias que não entraram na média por falta de resposta.
        corte_historico_pct: o corte histórico do concurso, quando conhecido; `None` na maioria
            dos casos hoje (P-17/P-39).
        probabilidade_lacuna: o motivo de não haver probabilidade de aprovação calculada; `None`
            quando `corte_historico_pct` foi informado (mesmo assim a saída é comparativa pela
            banda, nunca uma porcentagem de aprovação fabricada).
        porque: os números que mandaram na previsão — a matéria de maior peso (só quando ela
            realmente pesa mais que todas as outras), o quanto da prova a conta já cobre e, com
            corte, a comparação. As matérias em branco saem em `o_que_falta`, não aqui, para não
            aparecerem duas vezes seguidas na tela.
    """

    nota_pct: float
    nota_inferior_pct: float
    nota_superior_pct: float
    confianca: Confianca
    incerta: bool
    o_que_falta: str | None
    materias_sem_dado: list[str]
    corte_historico_pct: float | None
    probabilidade_lacuna: str | None
    porque: str


def _confianca(banda: float, cobertura: float) -> Confianca:
    """Classifica a confiança pela largura da banda e pela cobertura de peso com dado medido."""
    if banda <= BANDA_MAXIMA_ALTA and cobertura >= COBERTURA_MINIMA_ALTA:
        return "alta"
    if banda <= BANDA_MAXIMA_MEDIA and cobertura >= COBERTURA_MINIMA_MEDIA:
        return "media"
    return "baixa"


def _comparacao_com_corte(nota_inferior: float, nota_superior: float, corte: float) -> str:
    """Compara a banda da nota com o corte histórico — nunca o ponto isolado.

    Uma banda larga pode conter o corte mesmo com o ponto estimado abaixo dele; dizer "abaixo"
    nesse caso seria mais preciso do que os dados sustentam. `"em cima do corte"` é a leitura
    honesta quando o corte cai dentro da banda.
    """
    if nota_inferior > corte:
        return "acima do corte histórico"
    if nota_superior < corte:
        return "abaixo do corte histórico"
    return "em cima do corte histórico"


def _decimal_ptbr(valor: float) -> str:
    """Uma casa decimal com vírgula — o separador do português.

    Sem isto o mesmo parágrafo da tela saía com `61,6 %` de um lado e `62.9 p.p.` do outro.
    """
    return f"{valor:.1f}".replace(".", ",")


def _lista_pt(itens: list[str]) -> str:
    """Enumera em português: "Português", "Português e Matemática", "A, B e C"."""
    if len(itens) == 1:
        return itens[0]
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


def _materia_que_mais_pesa(
    materias: list[DesempenhoMateria], com_dado: list[DesempenhoMateria]
) -> DesempenhoMateria | None:
    """A matéria de maior peso, **só** quando ela pesa mais que todas as outras da prova.

    Com peso uniforme (o caso do edital real, que não informa quantas questões cada matéria tem —
    P-39), `max()` devolve a primeira da lista e a tela dizia que ela "pesa mais". Isso é dado
    errado com cara de certo (ADR-0036): ela não pesa mais, ela só veio primeiro. Sem maioria
    estrita, ninguém pesa mais e a frase não é escrita.
    """
    maior = max(com_dado, key=lambda materia: materia.peso_questoes)
    empatadas = [
        materia
        for materia in materias
        if materia is not maior and materia.peso_questoes >= maior.peso_questoes
    ]
    return None if empatadas else maior


def _o_que_falta(sem_dado: list[str], confianca: Confianca) -> str | None:
    """O próximo passo que estreita a faixa — uma ação, nunca um diagnóstico sobre nós.

    Matéria em branco vem primeiro e vale mesmo com confiança alta: é a lacuna que o produto
    promete declarar (visão §4), e some do texto se ficar pendurada só no critério de confiança.
    """
    if sem_dado:
        return (
            f"Responda questões de {_lista_pt(sem_dado)} — essas matérias ainda não entraram na "
            "conta, e é o que mais estreita essa faixa."
        )
    if confianca != "alta":
        return (
            "Responda mais questões — são poucas respostas ainda, e é por isso que a faixa está "
            "larga."
        )
    return None


def prever_nota(
    materias: list[DesempenhoMateria],
    corte_historico_pct: float | None = None,
) -> Previsao:
    """Prevê a nota da prova a partir da proficiência medida em cada matéria.

    Args:
        materias: o desempenho de cada matéria da prova — inclui as sem resposta ainda
            (`proporcao=None`), para que `peso_questoes` delas conte na cobertura e elas apareçam
            em `materias_sem_dado` em vez de simplesmente desaparecerem da conta.
        corte_historico_pct: o corte histórico do concurso, quando disponível.

    Returns:
        A `Previsao` com nota, banda, confiança e as lacunas declaradas.

    Raises:
        ValueError: quando nenhuma matéria tem dado (`proporcao is not None`) — sem nenhuma
            resposta em lugar nenhum não há nota para prever, e o contrato é lacuna declarada, não
            uma nota fabricada do nada.
    """
    medidos: list[tuple[Proporcao, int]] = [
        (materia.proporcao, materia.peso_questoes)
        for materia in materias
        if materia.proporcao is not None
    ]
    com_dado = [materia for materia in materias if materia.proporcao is not None]
    sem_dado = [materia.materia for materia in materias if materia.proporcao is None]
    peso_total = sum(materia.peso_questoes for materia in materias)
    peso_com_dado = sum(peso for _, peso in medidos)

    if peso_com_dado == 0:
        raise ValueError("nenhuma matéria tem resposta suficiente para prever a nota")

    nota_pct = sum(proporcao.pct * peso for proporcao, peso in medidos) / peso_com_dado
    nota_inferior_pct = (
        sum(proporcao.inferior_pct * peso for proporcao, peso in medidos) / peso_com_dado
    )
    nota_superior_pct = (
        sum(proporcao.superior_pct * peso for proporcao, peso in medidos) / peso_com_dado
    )

    banda = nota_superior_pct - nota_inferior_pct
    cobertura = peso_com_dado / peso_total if peso_total else 0.0
    confianca = _confianca(banda, cobertura)

    partes_porque: list[str] = []
    maior_peso = _materia_que_mais_pesa(materias, com_dado)
    if maior_peso is not None:
        questoes_maior_peso = (
            "1 questão"
            if maior_peso.peso_questoes == 1
            else (f"{maior_peso.peso_questoes} questões")
        )
        partes_porque.append(
            f"{maior_peso.materia} é a matéria com mais questões na prova "
            f"({questoes_maior_peso}), então é ela que mais mexe na sua nota."
        )
    if sem_dado:
        partes_porque.append(
            f"Por enquanto a conta cobre {cobertura * 100:.0f} % do peso da prova — o resto são "
            "matérias que você ainda não respondeu."
        )
    else:
        partes_porque.append("A conta já cobre o peso inteiro da prova.")

    if corte_historico_pct is None:
        probabilidade_lacuna: str | None = (
            "Ainda não tenho a nota de corte das edições anteriores deste concurso. Sem ela, não "
            "dá para dizer qual é a sua chance de passar — e eu não chuto esse número."
        )
    else:
        probabilidade_lacuna = None
        comparacao = _comparacao_com_corte(
            nota_inferior_pct, nota_superior_pct, corte_historico_pct
        )
        partes_porque.append(
            f"Sua faixa está {comparacao} de {_decimal_ptbr(corte_historico_pct)} %."
        )

    return Previsao(
        nota_pct=nota_pct,
        nota_inferior_pct=nota_inferior_pct,
        nota_superior_pct=nota_superior_pct,
        confianca=confianca,
        incerta=confianca == "baixa",
        o_que_falta=_o_que_falta(sem_dado, confianca),
        materias_sem_dado=sem_dado,
        corte_historico_pct=corte_historico_pct,
        probabilidade_lacuna=probabilidade_lacuna,
        porque=" ".join(partes_porque),
    )

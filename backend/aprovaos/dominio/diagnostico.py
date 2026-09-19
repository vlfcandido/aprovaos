"""Diagnóstico adaptativo (fatia 7, F2.1): proxy determinístico, sem TRI completa (ADR-0022).

O que é: `ItemDiagnostico` (uma resposta já ocorrida), `EstadoAgregado` (proficiência ± margem de
um grupo — matéria ou tópico), `calcular_estado`/`agrupar_por_materia`/`agrupar_por_topico` (a
fórmula do proxy), `TopicoDisponivel`/`CandidatoItem`/`ordenar_candidatos`/`materias_elegiveis`
(a seleção do próximo item) e `SinalTopico`/`sinais_por_topico`/`motivo_geral` (o estado que a
fatia 8 consome e o porquê exibido ao terminar). Nenhuma função aqui lê banco nem `datetime.now` —
`dados/repositorio_diagnostico.py` monta a entrada; `api/diagnostico.py` decide o que fazer com a
saída. Quando ler: ao mexer na regra de parada, na fórmula de margem ou na explicação exibida.

**Por que "proxy" e não a fórmula literal da ADR-0022** (`docs/DECISOES.md`): a ADR fala em "média
ponderada pela discriminação estimada dos itens (calibrador)" — `questao.discriminacao_est` é
`None` em toda a base hoje (o calibrador é a fatia 11, sem produtor ainda). A fórmula abaixo usa os
três sinais que já existem de verdade: acerto, `confianca_declarada` e cobertura de tópicos (plano
`docs/fatias/7-diagnostico-e-rotina.md` §2-§3). Quando a calibração existir, só `calcular_estado`
muda — o contrato (`EstadoAgregado`) não.

**Determinismo:** nenhuma função usa `random`. A mesma sequência de respostas produz sempre o
mesmo próximo item e o mesmo ponto de parada — mais forte que "reprodutível com seed" (não precisa
fixar seed nenhuma para o teste ser estável).
"""

from collections.abc import Set as AbstractSet
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel

from aprovaos.dominio.trilha import MINIMO_PARA_DOMINADO

#: Largura inicial da margem (pontos percentuais) sem nenhum item respondido — nunca fecha sem
#: dado algum.
MARGEM_INICIAL: Final = 50.0

#: O "±8" da spec (F2.1): abaixo disso, a matéria está "fechada" e para de receber item novo.
LIMITE_MARGEM: Final = 8.0

#: Teto duro do simulado (F2.1): "até 30 itens, no máximo".
MAXIMO_ITENS: Final = 30

#: Peso de uma resposta dada com certeza — informa mais (fecha a margem mais rápido) que uma
#: resposta em dúvida, seja ela certa ou errada.
PESO_CERTEZA: Final = 2

#: Peso de uma resposta dada em dúvida.
PESO_DUVIDA: Final = 1

Confianca = Literal["certeza", "duvida"]
Situacao = Literal["dominado", "a_estudar", "sem_dado", "sem_questao"]

#: A partir de qual estimativa (%) um tópico testado vira "dominado" em vez de "a_estudar"
#: (`sinais_por_topico`) — limiar direcional para o plano do dia (fatia 8), não um corte
#: estatístico (a amostra por tópico costuma ser pequena demais para isso). Vale **junto** com
#: `MINIMO_PARA_DOMINADO`: sem um piso de respostas, um único acerto com certeza daria 100 % e
#: tiraria o tópico da frente da fila com base em nada. O piso é o mesmo da trilha de propósito —
#: o produto tem uma definição só de "dominado" (`dominio/trilha.py`).
LIMIAR_DOMINIO_TOPICO: Final = 80.0


class ItemDiagnostico(BaseModel):
    """Uma resposta já registrada como parte do diagnóstico (`evento_estudo.dados.diagnostico`).

    Attributes:
        topico_id: tópico da questão respondida.
        materia: matéria do tópico (`Topico.materia`) — o proxy agrega por matéria e por tópico.
        acertou: se a resposta bateu com o gabarito.
        confianca: `"certeza"`/`"duvida"`, como a aluna declarou antes de responder.
    """

    topico_id: UUID
    materia: str
    acertou: bool
    confianca: Confianca


class EstadoAgregado(BaseModel):
    """Proficiência ± margem de um grupo de respostas (uma matéria, ou um tópico).

    Attributes:
        n_itens: quantas respostas compõem este estado.
        estimativa_pct: `None` sem nenhum item; senão o percentual de acerto ponderado por
            confiança (`PESO_CERTEZA`/`PESO_DUVIDA`).
        margem: a largura da faixa (pontos percentuais) ao redor de `estimativa_pct` — decresce
            com mais itens/mais confiança, **não** com o resultado (acertar ou errar informa
            igual sobre "o quanto já sei sobre este aluno aqui").
        fechado: `True` quando há pelo menos um item e `margem <= LIMITE_MARGEM`.
    """

    n_itens: int
    estimativa_pct: float | None
    margem: float
    fechado: bool


class TopicoDisponivel(BaseModel):
    """Um tópico do edital do concurso principal, com se há questão publicável para ele.

    Attributes:
        topico_id: chave do tópico.
        materia: matéria do tópico.
        nome: nome de exibição.
        tem_questao: `True` quando há ao menos uma questão publicável deste tópico na base — sem
            isso, o tópico nunca é candidato ao próximo item (nunca fingir cobertura).
    """

    topico_id: UUID
    materia: str
    nome: str
    tem_questao: bool


class CandidatoItem(BaseModel):
    """Um item elegível para a próxima pergunta, já com o porquê pronto para a tela.

    Attributes:
        topico_id: tópico de onde a rota deve buscar a próxima questão disponível.
        materia: matéria do tópico.
        motivo: frase pt-BR pronta para a caixa "por que este item".
    """

    topico_id: UUID
    materia: str
    motivo: str


class SinalTopico(BaseModel):
    """O estado de domínio de um tópico ao fim do diagnóstico — o que a fatia 8 consome.

    Attributes:
        topico_id: chave do tópico.
        materia: matéria do tópico.
        situacao: `"sem_questao"` (nunca teve questão publicável), `"sem_dado"` (tem questão, mas
            não entrou no diagnóstico), `"a_estudar"` ou `"dominado"` (testado).
        estimativa_pct: `None` para `"sem_questao"`/`"sem_dado"`.
        margem: `None` para `"sem_questao"`/`"sem_dado"`.
        n_itens: quantas respostas deste tópico compuseram o sinal.
    """

    topico_id: UUID
    materia: str
    situacao: Situacao
    estimativa_pct: float | None
    margem: float | None
    n_itens: int


def _peso(confianca: Confianca) -> int:
    """`PESO_CERTEZA`/`PESO_DUVIDA` conforme a confiança declarada."""
    return PESO_CERTEZA if confianca == "certeza" else PESO_DUVIDA


def calcular_estado(respostas: list[ItemDiagnostico]) -> EstadoAgregado:
    """Aplica a fórmula do proxy a um grupo de respostas (já filtrado por matéria ou tópico).

    `margem = MARGEM_INICIAL / (1 + peso_total)`, onde `peso_total` soma `PESO_CERTEZA`/
    `PESO_DUVIDA` de cada resposta — decresce com a quantidade e a confiança das respostas, nunca
    com o resultado delas. `estimativa_pct` é o percentual de acerto ponderado pelo mesmo peso.

    Args:
        respostas: as respostas de um único grupo (mesma matéria, ou mesmo tópico).

    Returns:
        O `EstadoAgregado` do grupo; `margem == MARGEM_INICIAL` e `estimativa_pct is None` sem
        nenhuma resposta.
    """
    if not respostas:
        return EstadoAgregado(n_itens=0, estimativa_pct=None, margem=MARGEM_INICIAL, fechado=False)

    peso_total = sum(_peso(r.confianca) for r in respostas)
    peso_acertos = sum(_peso(r.confianca) for r in respostas if r.acertou)
    margem = MARGEM_INICIAL / (1 + peso_total)
    estimativa = round(100.0 * peso_acertos / peso_total, 1)
    return EstadoAgregado(
        n_itens=len(respostas),
        estimativa_pct=estimativa,
        margem=round(margem, 2),
        fechado=margem <= LIMITE_MARGEM,
    )


def agrupar_por_materia(respostas: list[ItemDiagnostico]) -> dict[str, EstadoAgregado]:
    """`calcular_estado` de cada matéria presente em `respostas`.

    Args:
        respostas: todas as respostas do diagnóstico até agora (qualquer matéria).

    Returns:
        `{materia: EstadoAgregado}`; só entram matérias com pelo menos uma resposta.
    """
    por_materia: dict[str, list[ItemDiagnostico]] = {}
    for resposta in respostas:
        por_materia.setdefault(resposta.materia, []).append(resposta)
    return {materia: calcular_estado(itens) for materia, itens in por_materia.items()}


def agrupar_por_topico(respostas: list[ItemDiagnostico]) -> dict[UUID, EstadoAgregado]:
    """`calcular_estado` de cada tópico presente em `respostas`.

    Args:
        respostas: todas as respostas do diagnóstico até agora (qualquer tópico).

    Returns:
        `{topico_id: EstadoAgregado}`; só entram tópicos com pelo menos uma resposta.
    """
    por_topico: dict[UUID, list[ItemDiagnostico]] = {}
    for resposta in respostas:
        por_topico.setdefault(resposta.topico_id, []).append(resposta)
    return {topico_id: calcular_estado(itens) for topico_id, itens in por_topico.items()}


def materias_elegiveis(
    topicos: list[TopicoDisponivel],
    estados: dict[str, EstadoAgregado],
    materias_forcadas: AbstractSet[str] = frozenset(),
) -> list[str]:
    """As matérias que ainda podem receber um próximo item.

    Uma matéria entra quando tem pelo menos um tópico com `tem_questao=True` **e** (ainda não
    fechou, ou está em `materias_forcadas` — o "discordar" do plano §6).

    Args:
        topicos: os tópicos do edital do concurso principal.
        estados: `agrupar_por_materia` até agora (matéria sem resposta nenhuma não aparece aqui,
            o que a torna elegível por padrão).
        materias_forcadas: matérias que o aluno pediu para continuar mesmo já fechadas.

    Returns:
        Nomes de matéria, na ordem em que apareceram em `topicos` (determinístico), sem repetir.
    """
    vistas: set[str] = set()
    elegiveis: list[str] = []
    for topico in topicos:
        if not topico.tem_questao or topico.materia in vistas:
            continue
        vistas.add(topico.materia)
        estado = estados.get(topico.materia)
        fechado = estado is not None and estado.fechado
        if not fechado or topico.materia in materias_forcadas:
            elegiveis.append(topico.materia)
    return elegiveis


def _motivo_item(materia: str, margem: float, topico_nome: str, forcado: bool) -> str:
    """Frase pt-BR da caixa "por que este item" (plano §3)."""
    if forcado:
        return (
            f"Você pediu para continuar em {materia} mesmo com a margem já em ±{margem:g} — "
            f"este item de {topico_nome} soma mais evidência a essa estimativa."
        )
    return (
        f"Escolhi {materia}: é a matéria com a maior margem de incerteza ainda aberta "
        f"(±{margem:g} pontos) entre as que têm questão disponível. Dentro dela, {topico_nome} "
        "é o tópico com menos itens respondidos até agora."
    )


def ordenar_candidatos(
    topicos: list[TopicoDisponivel],
    estados: dict[str, EstadoAgregado],
    respondidos_por_topico: dict[UUID, int],
    materias_forcadas: AbstractSet[str] = frozenset(),
) -> list[CandidatoItem]:
    """Ranqueia os próximos itens possíveis: matéria mais incerta primeiro, cobertura desempata.

    A rota tenta cada candidato, nesta ordem, contra a disponibilidade real de questão
    (`repositorio_questao.proxima_questao`) — "tem_questao" pode não sobrar mais no meio do
    diagnóstico (mesmo padrão de `dominio.fio_memoria.ordem_para_tentar`).

    Args:
        topicos: os tópicos do edital do concurso principal.
        estados: `agrupar_por_materia` até agora.
        respondidos_por_topico: quantas respostas (deste diagnóstico) cada tópico já teve — usado
            só para desempate de cobertura dentro da matéria escolhida.
        materias_forcadas: matérias fechadas que o aluno pediu para continuar (§6 do plano).

    Returns:
        A lista de candidatos ranqueada; vazia quando nenhuma matéria é elegível — é o sinal de
        que o diagnóstico deve terminar.
    """
    elegiveis = materias_elegiveis(topicos, estados, materias_forcadas)
    if not elegiveis:
        return []

    def margem_da_materia(materia: str) -> float:
        estado = estados.get(materia)
        return estado.margem if estado is not None else MARGEM_INICIAL

    materias_ordenadas = sorted(elegiveis, key=lambda m: (-margem_da_materia(m), m))

    candidatos: list[CandidatoItem] = []
    for materia in materias_ordenadas:
        topicos_da_materia = [t for t in topicos if t.materia == materia and t.tem_questao]
        topicos_ordenados = sorted(
            topicos_da_materia,
            key=lambda t: (respondidos_por_topico.get(t.topico_id, 0), t.nome),
        )
        margem = margem_da_materia(materia)
        forcado = materia in materias_forcadas and (
            estados.get(materia) is not None and estados[materia].fechado
        )
        for topico in topicos_ordenados:
            candidatos.append(
                CandidatoItem(
                    topico_id=topico.topico_id,
                    materia=materia,
                    motivo=_motivo_item(materia, margem, topico.nome, forcado),
                )
            )
    return candidatos


def sinais_por_topico(
    respostas: list[ItemDiagnostico], topicos: list[TopicoDisponivel]
) -> list[SinalTopico]:
    """O estado de domínio de cada tópico do edital — o que a fatia 8 vai consumir.

    Args:
        respostas: todas as respostas do diagnóstico (qualquer tópico).
        topicos: todos os tópicos do edital do concurso principal.

    Returns:
        Um `SinalTopico` por tópico de `topicos`, na mesma ordem.
    """
    estados_por_topico = agrupar_por_topico(respostas)
    sinais: list[SinalTopico] = []
    for topico in topicos:
        if not topico.tem_questao:
            sinais.append(
                SinalTopico(
                    topico_id=topico.topico_id,
                    materia=topico.materia,
                    situacao="sem_questao",
                    estimativa_pct=None,
                    margem=None,
                    n_itens=0,
                )
            )
            continue
        estado = estados_por_topico.get(topico.topico_id)
        if estado is None or estado.n_itens == 0:
            sinais.append(
                SinalTopico(
                    topico_id=topico.topico_id,
                    materia=topico.materia,
                    situacao="sem_dado",
                    estimativa_pct=None,
                    margem=None,
                    n_itens=0,
                )
            )
            continue
        dominado = (
            estado.n_itens >= MINIMO_PARA_DOMINADO
            and estado.estimativa_pct is not None
            and estado.estimativa_pct >= LIMIAR_DOMINIO_TOPICO
        )
        situacao: Situacao = "dominado" if dominado else "a_estudar"
        sinais.append(
            SinalTopico(
                topico_id=topico.topico_id,
                materia=topico.materia,
                situacao=situacao,
                estimativa_pct=estado.estimativa_pct,
                margem=estado.margem,
                n_itens=estado.n_itens,
            )
        )
    return sinais


def motivo_geral(
    total_itens: int,
    estados_por_materia: dict[str, EstadoAgregado],
    materias_sem_questao: set[str],
) -> str:
    """Monta a explicação final ("por quê") mostrada na tela de resultado.

    Args:
        total_itens: quantos itens o diagnóstico usou ao todo.
        estados_por_materia: `agrupar_por_materia` do estado final.
        materias_sem_questao: matérias do edital sem nenhuma questão publicável (nunca testadas).

    Returns:
        Uma frase pt-BR começando por "Parei em N itens", citando a matéria que fechou com menos
        itens (quando há mais de uma fechada) e avisando as matérias sem questão, quando houver.
    """
    partes = [f"Parei em {total_itens} itens"]
    if total_itens >= MAXIMO_ITENS:
        partes[0] += f": atingi o máximo de {MAXIMO_ITENS}."
    else:
        fechadas = sorted(
            (
                (materia, estado)
                for materia, estado in estados_por_materia.items()
                if estado.fechado
            ),
            key=lambda par: par[1].n_itens,
        )
        if len(fechadas) >= 2:
            mais_rapida, estado_rapida = fechadas[0]
            mais_lenta, estado_lenta = fechadas[-1]
            partes[0] += (
                f": sua margem em {mais_rapida} fechou cedo ({estado_rapida.n_itens} itens) e "
                f"em {mais_lenta} levou mais ({estado_lenta.n_itens} itens)."
            )
        elif len(fechadas) == 1:
            materia, estado = fechadas[0]
            partes[0] += f": sua margem em {materia} fechou em {estado.n_itens} itens."
        else:
            partes[0] += ": não sobrou mais questão nova para as matérias em aberto."
    if materias_sem_questao:
        lista = ", ".join(sorted(materias_sem_questao))
        partes.append(f"Sem questão suficiente na base ainda para: {lista}.")
    return " ".join(partes)

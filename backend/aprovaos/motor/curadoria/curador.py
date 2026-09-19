"""O curador: junta segmentação + gabarito + classificação numa lista de `QuestaoCurada`.

O que é: `curar(...)`, que implementa o pipeline inteiro da skill `ingestao-de-provas` para um
caderno Cebraspe certo/errado — segmenta o texto da prova, lê o gabarito, classifica cada item
no vocabulário do edital e aplica o gate de publicação (`dominio.questao.decidir_publicacao`) —
e `verificar_curadoria(...)`, as 5 checagens de "Verificação antes de entregar" da skill. Função
de orquestração pura (sem I/O, sem banco): quem lê PDF e grava em disco/banco é o passo 5
(coletor) e o passo 12 (`motor/curar.py`), que chamam esta função com os textos já extraídos e
os 8 campos de origem já gravados no `Documento`. Quando ler: ao ligar o curador num comando
real, ao investigar por que um caderno virou `pendente_revisao`, ou ao mudar o gate de
publicação.
"""

from typing import Literal

from pydantic import BaseModel

from aprovaos.dominio.erros import GabaritoNaoReconhecido, SegmentacaoAmbigua
from aprovaos.dominio.gabarito import ler_gabarito_cebraspe
from aprovaos.dominio.prova import segmentar_cebraspe
from aprovaos.dominio.questao import (
    GabaritoStatus,
    Origem,
    QuestaoCurada,
    RegraProva,
    decidir_publicacao,
    hash_dedup,
    origem_completa,
)
from aprovaos.motor.curadoria.classificacao import (
    ClassificadorDeTopico,
    ItemParaClassificar,
    TopicoVocabulario,
    classificar,
)


class OrigemBase(BaseModel):
    """Os campos de `Origem` que são os mesmos para todo item do caderno (tudo, exceto o item).

    Attributes:
        banca: banca examinadora (ex.: `"cebraspe"`).
        orgao: órgão do concurso.
        cargo: cargo do caderno.
        ano: ano do concurso.
        tipo_caderno: identificador do caderno na banca, só quando a fonte o declara; `None`
            quando não declara (ver `dominio.questao.Origem.tipo_caderno`, Ruling 25 do passo 9
            — não inventar valor).
        url_prova: URL do PDF da prova, igual ao `Documento` gravado pelo coletor.
        documento_id: id do `Documento` da prova gravado pelo coletor.
    """

    banca: str
    orgao: str
    cargo: str
    ano: int
    tipo_caderno: str | None
    url_prova: str
    documento_id: str


class ResultadoCuradoria(BaseModel):
    """O que `curar` devolve para um caderno.

    Attributes:
        questoes: as `QuestaoCurada` produzidas; vazia quando `pendente_revisao` é `True`.
        pendente_revisao: `True` quando o caderno não pôde ser curado com segurança (segmentação
            ambígua, gabarito não reconhecido ou contagem de itens divergente do gabarito) — o
            documento inteiro fica para revisão manual, nenhuma questão é gravada.
        problemas: descrição de cada motivo de `pendente_revisao`; vazia quando `False`.
    """

    questoes: list[QuestaoCurada]
    pendente_revisao: bool
    problemas: list[str]


async def curar(
    texto_prova: str,
    texto_gabarito: str,
    vocabulario: list[TopicoVocabulario],
    origem_base: OrigemBase,
    regra_prova: RegraProva,
    classificador_ia: ClassificadorDeTopico | None,
    motivo_sem_ia: str | None,
    tamanho_lote: int,
) -> ResultadoCuradoria:
    """Cura um caderno Cebraspe certo/errado inteiro: segmenta, lê o gabarito e classifica.

    Implementa o pipeline da skill `ingestao-de-provas`: `SegmentacaoAmbigua` (segmentação com
    mais fronteiras de comando do que o padrão conhecido cobre) e `GabaritoNaoReconhecido`
    (nenhuma grade de gabarito Cebraspe C/E reconhecível) tornam o documento inteiro
    `pendente_revisao`, sem gravar nenhuma questão — assim como uma contagem de itens diferente
    da contagem de entradas do gabarito (documento pode estar mal segmentado). Fora desses três
    casos, cada item vira uma `QuestaoCurada` — anulado, alterado sem definitivo ou sem entrada
    no gabarito continuam na base (contam para incidência e DNA), só que com `publicavel=False`
    e o motivo.

    Args:
        texto_prova: texto do caderno de prova, já extraído do PDF.
        texto_gabarito: texto do gabarito, já extraído do PDF.
        vocabulario: os tópicos do conteúdo programático do edital da aluna.
        origem_base: os campos de `Origem` constantes para o caderno inteiro.
        regra_prova: a regra de correção vigente no caderno (ex.: anulação por erro).
        classificador_ia: implementação da porta de classificação com modelo, ou `None`.
        motivo_sem_ia: motivo registrado quando `classificador_ia` é `None`.
        tamanho_lote: quantos itens vão em cada chamada à IA (`config.lote_classificacao`).

    Returns:
        `ResultadoCuradoria` com uma `QuestaoCurada` por item do caderno, ou `pendente_revisao`
        com a lista de problemas encontrados.
    """
    try:
        itens = segmentar_cebraspe(texto_prova)
    except SegmentacaoAmbigua as erro:
        return ResultadoCuradoria(questoes=[], pendente_revisao=True, problemas=[str(erro)])

    try:
        gabarito = ler_gabarito_cebraspe(texto_gabarito)
    except GabaritoNaoReconhecido as erro:
        return ResultadoCuradoria(questoes=[], pendente_revisao=True, problemas=[str(erro)])

    if len(itens) != len(gabarito):
        problema = f"itens ({len(itens)}) ≠ gabarito ({len(gabarito)})"
        return ResultadoCuradoria(questoes=[], pendente_revisao=True, problemas=[problema])

    itens_para_classificar = [
        ItemParaClassificar(
            numero_item=item.numero_item, comando=item.comando, enunciado=item.enunciado
        )
        for item in itens
    ]
    resultado_classificacao = await classificar(
        itens_para_classificar, vocabulario, classificador_ia, motivo_sem_ia, tamanho_lote
    )
    classificacao_por_numero = {c.numero_item: c for c in resultado_classificacao.classificacoes}
    slugs_validos = {topico.slug for topico in vocabulario}

    questoes: list[QuestaoCurada] = []
    for item in itens:
        entrada = gabarito.get(item.numero_item)
        classificacao = classificacao_por_numero[item.numero_item]
        origem = Origem(
            banca=origem_base.banca,
            orgao=origem_base.orgao,
            cargo=origem_base.cargo,
            ano=origem_base.ano,
            numero_item=item.numero_item,
            tipo_caderno=origem_base.tipo_caderno,
            url_prova=origem_base.url_prova,
            documento_id=origem_base.documento_id,
        )

        gabarito_status: GabaritoStatus
        valor: Literal["C", "E"] | None
        valor_preliminar: Literal["C", "E"] | None
        if entrada is None:
            gabarito_status, valor, valor_preliminar = "sem_gabarito", None, None
        else:
            gabarito_status = entrada.status
            valor, valor_preliminar = entrada.valor, entrada.valor_preliminar

        publicavel, motivo = decidir_publicacao(
            gabarito_status=gabarito_status,
            topico_slug=classificacao.topico_slug,
            topico_confianca=classificacao.confianca,
            slugs_validos=slugs_validos,
            origem=origem,
        )

        questoes.append(
            QuestaoCurada(
                banca=origem_base.banca,
                numero_item=item.numero_item,
                comando=item.comando,
                texto_apoio=item.texto_apoio,
                texto_apoio_itens=item.texto_apoio_itens,
                enunciado=item.enunciado,
                gabarito_preliminar=valor_preliminar,
                gabarito=valor,
                gabarito_status=gabarito_status,
                publicavel=publicavel,
                motivo_nao_publicavel=motivo,
                regra_prova=regra_prova,
                topico_slug=classificacao.topico_slug,
                topico_confianca=classificacao.confianca,
                topico_evidencia=classificacao.evidencia,
                origem=origem,
                hash_dedup=hash_dedup(item.enunciado),
            )
        )

    return ResultadoCuradoria(questoes=questoes, pendente_revisao=False, problemas=[])


def verificar_curadoria(questoes: list[QuestaoCurada], total_itens: int) -> list[str]:
    """Roda as 5 checagens de "Verificação antes de entregar" da skill `ingestao-de-provas`.

    Args:
        questoes: a saída de `curar` para um caderno (lista vazia se `pendente_revisao`).
        total_itens: quantos itens o caderno tinha, para conferir a contagem 1:1.

    Returns:
        Uma mensagem por violação encontrada, na ordem das 5 checagens da skill; lista vazia
        quando nada está errado.
    """
    problemas: list[str] = []

    numeros = [questao.numero_item for questao in questoes]
    if len(questoes) != total_itens:
        problemas.append(
            f"total de questões ({len(questoes)}) diferente do total de itens do caderno "
            f"({total_itens})"
        )
    duplicados = sorted({numero for numero in numeros if numeros.count(numero) > 1})
    if duplicados:
        problemas.append(f"numero_item duplicado na saída: {duplicados}")

    por_numero = {questao.numero_item: questao for questao in questoes}
    numeros_em_bloco_de_apoio = {
        numero for questao in questoes for numero in questao.texto_apoio_itens
    }
    sem_apoio_no_bloco = sorted(
        numero
        for numero in numeros_em_bloco_de_apoio
        if (questao_do_bloco := por_numero.get(numero)) is not None
        and not questao_do_bloco.texto_apoio
    )
    if sem_apoio_no_bloco:
        problemas.append(f"itens num bloco de texto de apoio sem texto_apoio: {sem_apoio_no_bloco}")

    # A skill permite `comando is None` quando o caderno inteiro não tem comandos (raro na
    # Cebraspe); só é suspeita quando outro item do mesmo caderno tem comando preenchido.
    algum_comando_preenchido = any(questao.comando is not None for questao in questoes)
    if algum_comando_preenchido:
        sem_comando = sorted(questao.numero_item for questao in questoes if questao.comando is None)
        if sem_comando:
            problemas.append(f"itens sem comando: {sem_comando}")

    publicados = sorted(questao.numero_item for questao in questoes if questao.publicado)
    if publicados:
        problemas.append(f"itens com publicado=True na saída do curador: {publicados}")
    anulados_com_gabarito = sorted(
        questao.numero_item
        for questao in questoes
        if questao.gabarito_status == "anulado" and questao.gabarito is not None
    )
    if anulados_com_gabarito:
        problemas.append(f"itens anulados mas com gabarito preenchido: {anulados_com_gabarito}")

    origem_incompleta = sorted(
        questao.numero_item for questao in questoes if not origem_completa(questao.origem)
    )
    if origem_incompleta:
        problemas.append(f"itens com origem incompleta: {origem_incompleta}")

    return problemas

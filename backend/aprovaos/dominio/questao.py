"""Contrato da questão curada e o gate de publicação: `QuestaoCurada`, `Origem`, `RegraProva`.

O que é: os modelos Pydantic da saída do curador (`motor/curadoria/curador.py`), implementando
o contrato "A saída é uma lista de objetos com estes campos" da skill `ingestao-de-provas`, e
`decidir_publicacao` — o gate determinístico da premissa F do plano da V3 (vira ADR-0033 no
passo 15). `hash_dedup` normaliza o enunciado só para deduplicação; o texto servido ao aluno
nunca passa por essa normalização. Funções puras, sem I/O, sem banco. Quando ler: ao mudar um
campo do contrato de questão curada, ao ajustar o que torna uma questão publicável, ou ao
investigar por que uma questão real não está sendo servida.
"""

import hashlib
import re
from typing import Literal

from pydantic import BaseModel

#: Confiança da classificação de tópico (mesmos valores de
#: `motor.curadoria.classificacao.Confianca`; redeclarado aqui porque o domínio não depende do
#: motor — só o contrário).
Confianca = Literal["alta", "media", "baixa"]

#: `gabarito_status` de uma `QuestaoCurada`. Os quatro primeiros valores são os de
#: `dominio.gabarito.EntradaGabarito.status`; `"sem_gabarito"` é acréscimo deste contrato para o
#: item que não tem nenhuma entrada no gabarito (regra 4 de "Gabarito: a ordem de verdade" da
#: skill `ingestao-de-provas`, que fala do caso mas não nomeia um status para ele).
GabaritoStatus = Literal["definitivo", "preliminar", "anulado", "alterado", "sem_gabarito"]

_ESPACOS = re.compile(r"\s+")


class Origem(BaseModel):
    """Os 8 campos de procedência de uma questão original — nunca remontados de memória.

    `url_prova` e `documento_id` vêm sempre do `Documento` que o coletor gravou (passo 5 da V3);
    quem monta uma `Origem` não pode derivá-los de nome de arquivo nem inventá-los.

    Attributes:
        banca: banca examinadora (ex.: `"cebraspe"`).
        orgao: órgão do concurso (ex.: `"TJ-PA"`).
        cargo: cargo do caderno, como o edital nomeia (ex.: `"Analista Judiciário — Direito"`).
        ano: ano do concurso.
        numero_item: número do item impresso no caderno.
        tipo_caderno: identificador do caderno na banca (ex.: `"TIPO 1"`), só quando a fonte o
            declara; `None` quando não declara — a API da Cebraspe não expõe tipo de caderno de
            forma determinística no que já foi medido até este passo (Ruling 25 do passo 9).
            `None` aqui é um valor legítimo de procedência, não um campo faltando: nenhum campo
            é inventado só para preencher a lacuna (`origem_completa` não exige este campo).
        url_prova: URL do PDF da prova, igual ao `Documento` gravado pelo coletor.
        documento_id: id do `Documento` da prova gravado pelo coletor.
    """

    banca: str
    orgao: str
    cargo: str
    ano: int
    numero_item: int
    tipo_caderno: str | None
    url_prova: str
    documento_id: str


class RegraProva(BaseModel):
    """A regra de correção vigente no caderno de onde a questão veio, com a fonte.

    Attributes:
        anula_por_erro: `True` se uma resposta errada anula uma certa (Cebraspe C/E costuma
            anular; depende do edital/instrução do caderno).
        fonte: de onde a regra veio (ex.: `"instrução do caderno"`, `"edital §6.1"`).
    """

    anula_por_erro: bool
    fonte: str


class QuestaoCurada(BaseModel):
    """Uma questão original, no contrato de saída da skill `ingestao-de-provas`.

    `publicado` nasce sempre `False`: só o validador (fatia 5, para inéditas) ou o gate de
    publicação de originais ligam algo — o curador nunca marca uma questão como servida.
    `justificativa_certo`/`justificativa_errado` nascem sempre `None`: o curador nunca explica
    o gabarito (isso é papel do gerador de inéditas).

    Attributes:
        adapter: adapter de onde a questão veio (`"concursos"` nesta fatia).
        banca: banca examinadora (ex.: `"cebraspe"`).
        tipo_item: forma do item; só `"certo_errado"` é produzido nesta fatia (decisão J do
            plano da V3 — Cebraspe A–E e FGV ficam fora).
        numero_item: número do item impresso no caderno.
        comando: a instrução de julgamento vigente para o item, ou `None` se nenhuma foi
            encontrada antes dele.
        texto_apoio: o texto-base compartilhado com outros itens, ou `None`.
        texto_apoio_itens: todos os números do intervalo do texto de apoio (inclui o próprio
            item), ou lista vazia se não há texto de apoio.
        enunciado: a afirmação a ser julgada, como a banca imprimiu.
        alternativas: sempre `None` nesta fatia (Cebraspe C/E não tem alternativas; reservado
            para quando a segmentação A–E entrar).
        gabarito_preliminar: o valor anterior ao definitivo, só quando `gabarito_status ==
            "alterado"`.
        gabarito: `"C"`/`"E"` do gabarito definitivo, ou `None` quando anulado ou sem entrada.
        gabarito_status: ver `GabaritoStatus`.
        publicavel: resultado do gate de publicação (`decidir_publicacao`).
        publicado: sempre `False` na saída do curador.
        motivo_nao_publicavel: por que `publicavel` é `False`; `None` quando é `True`.
        regra_prova: a regra de correção vigente no caderno.
        topico_slug: slug do vocabulário canônico do edital, ou `None` sem correspondência.
        topico_confianca: confiança da classificação (ver `Confianca`).
        topico_evidencia: o que no texto decidiu o tópico (ou a falta de correspondência).
        origem: os 8 campos de procedência (ver `Origem`).
        hash_dedup: sha1 do enunciado normalizado (ver `hash_dedup`); o texto servido ao aluno
            continua o que a banca imprimiu.
        justificativa_certo: sempre `None` na saída do curador.
        justificativa_errado: sempre `None` na saída do curador.
    """

    adapter: Literal["concursos"] = "concursos"
    banca: str
    tipo_item: Literal["certo_errado"] = "certo_errado"
    numero_item: int
    comando: str | None
    texto_apoio: str | None
    texto_apoio_itens: list[int]
    enunciado: str
    alternativas: list[str] | None = None
    gabarito_preliminar: Literal["C", "E"] | None
    gabarito: Literal["C", "E"] | None
    gabarito_status: GabaritoStatus
    publicavel: bool
    publicado: Literal[False] = False
    motivo_nao_publicavel: str | None
    regra_prova: RegraProva
    topico_slug: str | None
    topico_confianca: Confianca
    topico_evidencia: str
    origem: Origem
    hash_dedup: str
    justificativa_certo: None = None
    justificativa_errado: None = None


def hash_dedup(enunciado: str) -> str:
    """Calcula o hash de deduplicação de um enunciado — sha1 do texto normalizado.

    A normalização (espaços e quebras de linha colapsados num único espaço, pontas removidas)
    existe só para decidir se dois enunciados são "o mesmo item"; caixa e acentuação são
    preservadas, e o texto servido ao aluno nunca passa por ela.

    Args:
        enunciado: o enunciado como a banca imprimiu.

    Returns:
        O hex digest sha1 do enunciado normalizado.
    """
    normalizado = _ESPACOS.sub(" ", enunciado).strip()
    return hashlib.sha1(normalizado.encode("utf-8")).hexdigest()  # noqa: S324 — dedup, não segurança


def origem_completa(origem: Origem) -> bool:
    """`True` se os 8 campos de `origem` existem como chave e os obrigatórios estão preenchidos.

    Usada pelo gate de publicação (`decidir_publicacao`) e pela verificação 5 da skill
    `ingestao-de-provas` (`motor.curadoria.curador.verificar_curadoria`). `tipo_caderno` fica de
    fora da checagem de "preenchido": `None` é um valor legítimo desse campo (Ruling 25 do
    passo 9 — a fonte não declara tipo de caderno na maioria dos casos), não uma ausência a
    barrar a publicação.

    Args:
        origem: os 8 campos de procedência a conferir.

    Returns:
        `True` se nenhum dos campos de texto obrigatórios (todos, exceto `tipo_caderno`) está
        vazio/só espaços e `ano`/`numero_item` são positivos.
    """
    campos_obrigatorios = (
        origem.banca,
        origem.orgao,
        origem.cargo,
        origem.url_prova,
        origem.documento_id,
    )
    return (
        all(campo.strip() for campo in campos_obrigatorios)
        and origem.ano > 0
        and origem.numero_item > 0
    )


def decidir_publicacao(
    gabarito_status: GabaritoStatus,
    topico_slug: str | None,
    topico_confianca: Confianca,
    slugs_validos: set[str],
    origem: Origem,
) -> tuple[bool, str | None]:
    """O gate de publicação de uma questão original (premissa F do plano da V3; ADR-0033).

    `publicavel = True` exige, cumulativamente: gabarito definitivo (`"definitivo"` ou
    `"alterado"`), `origem` com os 8 campos preenchidos, `topico_slug` presente no vocabulário
    do edital e `topico_confianca != "baixa"`. A primeira condição que falha decide o motivo —
    um item anulado nunca chega a ser avaliado pelas condições de tópico. O motivo distingue
    duas causas-raiz diferentes de barrar por tópico: `"tópico não identificado"` (slug ausente
    ou fora do vocabulário — problema de cobertura do vocabulário) e `"tópico identificado com
    confiança baixa"` (slug válido, mas a classificação não confia nele — problema de calibração
    do classificador). O classificador por regras nunca produz a segunda combinação sozinho
    (confiança baixa sempre vem sem slug, Ruling 21 do passo 8), mas o contrato da porta
    (`ClassificadorDeTopico`) não impede uma IA de devolver as duas coisas juntas.

    Args:
        gabarito_status: status do gabarito da questão (ver `GabaritoStatus`).
        topico_slug: slug decidido pela classificação, ou `None`.
        topico_confianca: confiança da classificação.
        slugs_validos: os slugs do vocabulário canônico do edital.
        origem: os 8 campos de procedência já montados.

    Returns:
        `(publicavel, motivo_nao_publicavel)`; o motivo é `None` quando `publicavel` é `True`.
    """
    if gabarito_status == "anulado":
        return False, "anulado — gabarito não é servido ao aluno"
    if gabarito_status == "sem_gabarito":
        return False, "sem gabarito"
    if gabarito_status == "preliminar":
        return False, "gabarito ainda preliminar — aguardando definitivo"
    # só sobra "definitivo" ou "alterado" daqui em diante.
    if not origem_completa(origem):
        return False, "origem incompleta"
    if topico_slug is None or topico_slug not in slugs_validos:
        return False, "tópico não identificado"
    if topico_confianca == "baixa":
        return False, "tópico identificado com confiança baixa"
    return True, None

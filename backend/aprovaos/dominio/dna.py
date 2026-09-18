"""Contrato do `DnaConcurso` (skill `dna-do-concurso`), DNA por regras e sua verificação.

O que é: os modelos Pydantic que espelham, campo a campo e na mesma ordem, o JSON da skill
`.claude/skills/dna-do-concurso/SKILL.md`; `montar_dna_por_regras`, que calcula o DNA reduzido só
com os fatos do edital (pct por pontos, peso uniforme por tópico, lacunas declaradas); e
`verificar_dna`, as quatro verificações da skill aplicadas a qualquer DNA (IA ou regras).
Quando ler: ao mudar o contrato da skill, ao revisar um número do DNA ou ao decidir por que um
DNA da IA foi reprovado.
"""

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel

from aprovaos.dominio.edital import (
    DESCONHECIDO,
    Desconhecido,
    MateriaExtraida,
    extrair_fatos,
    fonte_conteudo_programatico,
    sem_acento,
    slug_materia,
)

TipoItem = Literal["certo_errado", "multipla_escolha"]

LACUNAS_SEM_PROVAS = ["incidência por tópico", "estilo da banca", "corte histórico", "pegadinhas"]
FONTE_PESO_OMISSO = "edital omisso — assumido 1,0"
PREFIXOS_DE_FONTE = ("edital", "prova ", "sem provas", "nenhuma prova")
_PERCENTUAL = re.compile(r"(\d+)\s*%")


class ConcursoDna(BaseModel):
    """Identificação do concurso no DNA (bloco `concurso` da skill)."""

    orgao: str
    cargo: str
    banca: str
    edital: str
    data_prova: date | Desconhecido
    fonte: str


class RegraCorrecao(BaseModel):
    """Regra de correção da prova objetiva (bloco `regra_correcao`)."""

    tipo_item: TipoItem | Desconhecido
    alternativas: int | None
    anula_por_erro: bool | Desconhecido
    minimo_por_materia: str
    minimo_global: str
    fonte: str


class EtapaDna(BaseModel):
    """Uma etapa do concurso com pontos e quem a faz (item de `etapas`)."""

    nome: str
    pontos: float | Desconhecido
    quem_faz: str | None = None
    fonte: str


class PesoMateria(BaseModel):
    """Peso de uma matéria de prova por pontos (`pesos.materia[slug]`)."""

    questoes: int | Desconhecido
    peso_questao: float
    pontos: float | Desconhecido
    pct_pontos: float | Desconhecido
    fonte: str


class PesoTopico(BaseModel):
    """Peso de um tópico (`pesos.topico[slug]`): por prova quando há, senão uniforme."""

    pct_pontos: float | Desconhecido
    metodo: str
    pct_uniforme: float | Desconhecido


class Pesos(BaseModel):
    """Pesos por matéria de prova e por tópico (bloco `pesos`)."""

    materia: dict[str, PesoMateria]
    topico: dict[str, PesoTopico]


class TopicoEditalDna(BaseModel):
    """Um item do conteúdo programático no DNA (item de `topicos_edital`)."""

    slug: str
    materia: str
    texto_original: str
    fonte: str


class Incidencia(BaseModel):
    """Incidência por tópico medida em provas (bloco `incidencia`)."""

    por_topico: dict[str, float] | Desconhecido
    provas_analisadas: int
    fonte: str


class Estilo(BaseModel):
    """Estilo da banca: só o que o edital diz ou as provas mostram (bloco `estilo`)."""

    tipo_item: TipoItem | Desconhecido
    alternativas: int | None
    caracteristicas: str
    fonte: str


class Pegadinha(BaseModel):
    """Pegadinha observada numa prova real (item de `pegadinhas`)."""

    descricao: str
    banca: str
    ano: int
    item: str


class Corte(BaseModel):
    """Intervalo histórico da nota de corte (bloco `corte`)."""

    lo: float | Desconhecido
    hi: float | Desconhecido
    fonte: str


class DnaConcurso(BaseModel):
    """O DNA inteiro, na ordem do JSON da skill; todos os campos são obrigatórios.

    Attributes:
        concurso: órgão, cargo, banca, edital e data.
        regra_correcao: tipo de item, alternativas, anulação e mínimos.
        etapas: objetiva, discursiva…
        pesos: por matéria de prova e por tópico.
        topicos_edital: todos os itens do conteúdo programático, com slug.
        incidencia: por tópico, medida em provas (ou `desconhecido`).
        estilo: da banca, literal do edital ou medido em provas.
        pegadinhas: só de provas reais.
        corte: intervalo histórico (ou `desconhecido`).
        lacunas: tudo que está `desconhecido`, em linguagem clara.
        fontes: documentos usados.
        versao: versão do DNA deste concurso.
    """

    concurso: ConcursoDna
    regra_correcao: RegraCorrecao
    etapas: list[EtapaDna]
    pesos: Pesos
    topicos_edital: list[TopicoEditalDna]
    incidencia: Incidencia
    estilo: Estilo
    pegadinhas: list[Pegadinha]
    corte: Corte
    lacunas: list[str]
    fontes: list[str]
    versao: int


def _chave(nome: str) -> str:
    """Chave de comparação de nomes de matéria: sem acento, minúsculas, espaços únicos."""
    return " ".join(sem_acento(nome).casefold().split())


def _numero(valor: float) -> str:
    """`80.0` → `80`, `12.5` → `12.5` (para textos como `40 de 80`)."""
    return str(int(valor)) if float(valor).is_integer() else str(valor)


def montar_dna_por_regras(texto: str, materias: list[MateriaExtraida]) -> DnaConcurso:
    """Monta o DNA reduzido só com os fatos do edital, seguindo as regras de cálculo da skill.

    Matéria de prova é o nome que aparece na distribuição de questões; cada `MateriaExtraida`
    pertence à matéria de prova cujo nome bate (sem acento, sem caixa) com o seu `grupo` ou,
    sem grupo, com o seu `nome`. `pct_pontos = pontos / Σ pontos × 100` (pontos =
    questões × peso), e o `pct_uniforme` de cada tópico é o `pct_pontos` da matéria de prova
    dividido pelo número de tópicos que ela agrupa. Tudo que depende de prova (incidência,
    estilo, corte, pegadinhas) fica `desconhecido` e entra em `lacunas`, assim como banca, data
    e distribuição quando o edital não os traz.

    Args:
        texto: texto integral do edital.
        materias: saída de `extrair_conteudo_programatico(texto)`.

    Returns:
        Um `DnaConcurso` que passa em `verificar_dna`.
    """
    fatos = extrair_fatos(texto)
    cabecalho, regra = fatos.cabecalho, fatos.regra
    lacunas = list(LACUNAS_SEM_PROVAS)

    # Matérias de prova presentes no conteúdo programático, na ordem do edital.
    conteudo_por_chave: dict[str, list[MateriaExtraida]] = {}
    nome_por_chave: dict[str, str] = {}
    for materia in materias:
        nome_prova = materia.grupo or materia.nome
        conteudo_por_chave.setdefault(_chave(nome_prova), []).append(materia)
        nome_por_chave.setdefault(_chave(nome_prova), nome_prova)

    total_pontos = sum(d.questoes * d.peso_questao for d in fatos.distribuicao)
    pesos_materia: dict[str, PesoMateria] = {}
    pct_por_chave: dict[str, float] = {}
    for linha in fatos.distribuicao:
        chave = _chave(linha.nome)
        pontos = linha.questoes * linha.peso_questao
        pct = pontos / total_pontos * 100
        pesos_materia[slug_materia(linha.nome)] = PesoMateria(
            questoes=linha.questoes,
            peso_questao=linha.peso_questao,
            pontos=pontos,
            pct_pontos=pct,
            fonte=linha.fonte,
        )
        if chave in conteudo_por_chave:
            pct_por_chave[chave] = pct
        else:
            lacunas.append(f"matéria {linha.nome} da distribuição sem conteúdo programático")

    if not fatos.distribuicao:
        lacunas.append("distribuição de questões por matéria")
    for chave, nome_prova in nome_por_chave.items():
        if chave in pct_por_chave:
            continue
        pesos_materia.setdefault(
            slug_materia(nome_prova),
            PesoMateria(
                questoes=DESCONHECIDO,
                peso_questao=1.0,
                pontos=DESCONHECIDO,
                pct_pontos=DESCONHECIDO,
                fonte=FONTE_PESO_OMISSO,
            ),
        )
        if fatos.distribuicao:
            lacunas.append(f"peso de {nome_prova}: sem linha na distribuição")

    pesos_topico: dict[str, PesoTopico] = {}
    fonte_topicos = fonte_conteudo_programatico(texto)
    topicos_edital: list[TopicoEditalDna] = []
    for materia in materias:
        chave = _chave(materia.grupo or materia.nome)
        quantidade = sum(len(m.topicos) for m in conteudo_por_chave[chave])
        pct_uniforme: float | Desconhecido = (
            pct_por_chave[chave] / quantidade if chave in pct_por_chave else DESCONHECIDO
        )
        for topico in materia.topicos:
            pesos_topico[topico.slug] = PesoTopico(
                pct_pontos=DESCONHECIDO, metodo="uniforme_no_edital", pct_uniforme=pct_uniforme
            )
            topicos_edital.append(
                TopicoEditalDna(
                    slug=topico.slug,
                    materia=materia.slug,
                    texto_original=topico.texto_original,
                    fonte=fonte_topicos,
                )
            )

    minimo_global = regra.minimo_global
    percentual = _PERCENTUAL.match(minimo_global)
    if percentual is not None and total_pontos:
        minimo = total_pontos * int(percentual.group(1)) / 100
        minimo_global = f"{minimo_global} ({_numero(minimo)} de {_numero(total_pontos)})"

    if cabecalho.banca == DESCONHECIDO:
        lacunas.append("banca")
    if cabecalho.data_prova is None:
        lacunas.append("data da prova")
    if DESCONHECIDO in (
        regra.tipo_item,
        regra.anula_por_erro,
        regra.minimo_global,
        regra.minimo_por_materia,
    ):
        lacunas.append("regra de correção: parte não encontrada no edital")

    numero_edital = "" if cabecalho.edital == DESCONHECIDO else f" {cabecalho.edital}"
    return DnaConcurso(
        concurso=ConcursoDna(
            orgao=cabecalho.orgao,
            cargo=cabecalho.cargo,
            banca=cabecalho.banca,
            edital=cabecalho.edital,
            data_prova=cabecalho.data_prova or DESCONHECIDO,
            fonte=cabecalho.fonte,
        ),
        regra_correcao=RegraCorrecao(
            tipo_item=regra.tipo_item,
            alternativas=regra.alternativas,
            anula_por_erro=regra.anula_por_erro,
            minimo_por_materia=regra.minimo_por_materia,
            minimo_global=minimo_global,
            fonte=regra.fonte,
        ),
        etapas=[EtapaDna.model_validate(etapa.model_dump()) for etapa in fatos.etapas],
        pesos=Pesos(materia=pesos_materia, topico=pesos_topico),
        topicos_edital=topicos_edital,
        incidencia=Incidencia(
            por_topico=DESCONHECIDO, provas_analisadas=0, fonte="nenhuma prova da banca na base"
        ),
        estilo=Estilo(
            tipo_item=regra.tipo_item,
            alternativas=regra.alternativas,
            caracteristicas=DESCONHECIDO,
            fonte=f"{regra.fonte}; sem provas",
        ),
        pegadinhas=[],
        corte=Corte(lo=DESCONHECIDO, hi=DESCONHECIDO, fonte="sem provas/resultados anteriores"),
        lacunas=lacunas,
        fontes=[f"edital{numero_edital} (arquivo subido)"],
        versao=1,
    )


def _fontes_do_dna(dna: DnaConcurso) -> list[tuple[str, str]]:
    """Pares (rótulo, fonte) de todos os objetos que carregam `fonte` no contrato."""
    pares = [("concurso", dna.concurso.fonte), ("regra_correcao", dna.regra_correcao.fonte)]
    pares += [(f"etapas[{e.nome}]", e.fonte) for e in dna.etapas]
    pares += [(f"pesos.materia[{slug}]", p.fonte) for slug, p in dna.pesos.materia.items()]
    pares += [
        ("incidencia", dna.incidencia.fonte),
        ("estilo", dna.estilo.fonte),
        ("corte", dna.corte.fonte),
    ]
    pares += [(f"pegadinhas[{i}]", p.banca) for i, p in enumerate(dna.pegadinhas)]
    return pares


def _desconhecidos_do_dna(dna: DnaConcurso) -> list[tuple[str, str]]:
    """Pares (rótulo, palavra-chave da lacuna) para cada valor `desconhecido` que exige lacuna."""
    pares: list[tuple[str, str]] = []
    if dna.concurso.banca == DESCONHECIDO:
        pares.append(("concurso.banca", "banca"))
    if dna.concurso.data_prova == DESCONHECIDO:
        pares.append(("concurso.data_prova", "data"))
    regra = dna.regra_correcao
    for campo in ("tipo_item", "anula_por_erro", "minimo_por_materia", "minimo_global"):
        if getattr(regra, campo) == DESCONHECIDO:
            pares.append((f"regra_correcao.{campo}", "correcao"))
    if dna.corte.lo == DESCONHECIDO or dna.corte.hi == DESCONHECIDO:
        pares.append(("corte", "corte"))
    if dna.incidencia.por_topico == DESCONHECIDO:
        pares.append(("incidencia.por_topico", "incidencia"))
    if dna.estilo.caracteristicas == DESCONHECIDO:
        pares.append(("estilo.caracteristicas", "estilo"))
    for slug, peso in dna.pesos.materia.items():
        if peso.pct_pontos == DESCONHECIDO:
            pares.append((f"pesos.materia[{slug}].pct_pontos", "distribuicao"))
    return pares


def verificar_dna(dna: DnaConcurso, materias: list[MateriaExtraida]) -> list[str]:
    """Aplica as quatro verificações da skill; lista vazia = aprovado.

    1. Se todos os `pct_pontos` são conhecidos, somam 100 (± 0,01).
    2. Todo objeto com `fonte` a tem preenchida e começando por `edital`, `prova `,
       `sem provas` ou `nenhuma prova` (pegadinhas: `banca` preenchida).
    3. Todo valor `desconhecido` tem uma lacuna que cite a palavra-chave correspondente
       (banca, data, correcao, corte, incidencia, estilo, distribuicao).
    4. `topicos_edital` tem exatamente os slugs de todos os tópicos de `materias`.

    Args:
        dna: o DNA a verificar (da IA ou das regras).
        materias: o conteúdo programático extraído pelo parser.

    Returns:
        Uma mensagem por problema, em pt-BR; vazia quando o DNA passa.
    """
    problemas: list[str] = []

    percentuais = [p.pct_pontos for p in dna.pesos.materia.values()]
    conhecidos = [p for p in percentuais if not isinstance(p, str)]
    if percentuais and len(conhecidos) == len(percentuais):
        soma = sum(conhecidos)
        if abs(soma - 100) > 0.01:
            problemas.append(f"soma dos pct_pontos das matérias é {soma:.2f}, não 100")

    for rotulo, fonte in _fontes_do_dna(dna):
        if not fonte.strip():
            problemas.append(f"{rotulo}: sem fonte")
        elif not fonte.startswith(PREFIXOS_DE_FONTE):
            problemas.append(f"{rotulo}: fonte fora do padrão da skill ({fonte!r})")

    lacunas = [sem_acento(lacuna).casefold() for lacuna in dna.lacunas]
    for rotulo, palavra in _desconhecidos_do_dna(dna):
        if not any(palavra in lacuna for lacuna in lacunas):
            problemas.append(f"{rotulo} é 'desconhecido' sem lacuna que cite '{palavra}'")

    esperados = {t.slug for m in materias for t in m.topicos}
    total = sum(len(m.topicos) for m in materias)
    obtidos = {t.slug for t in dna.topicos_edital}
    if obtidos != esperados or len(dna.topicos_edital) != total:
        cobertos = len(obtidos & esperados)
        fora = len(obtidos - esperados)
        problemas.append(
            f"cobertura: {cobertos} de {total} tópicos do conteúdo programático "
            f"({len(dna.topicos_edital)} em topicos_edital, {fora} com slug fora do parser)"
        )
    return problemas

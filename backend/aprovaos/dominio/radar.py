"""Regras puras do radar de editais: ler o catálogo da Cebraspe e casar com o perfil da aluna.

O que é: `ler_catalogo`/`extrair_uf`/`ler_periodo_inscricao` (passo 1 do plano) e
`casar_com_perfil`/`PreferenciaRadar`/`Casamento` (passo 2). Nenhuma chamada de rede nem de banco
aqui — quem lê a API é `motor/fontes/cebraspe.py`; quem persiste é `dados/repositorio_radar.py`.
Quando ler: antes de mexer no que o radar entende da Cebraspe ou em como um concurso "combina"
com o perfil da aluna (`docs/fatias/1b-radar-e-conta.md`, Rulings 38-40).
"""

import re
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel

from aprovaos.motor.coletar import cargo_de_direito
from aprovaos.motor.fontes.cebraspe import CargoEvento

#: As 27 UFs — usado só para confirmar (nunca chutar) a UF de um concurso (Ruling 39).
UFS_VALIDAS = frozenset(
    {
        "AC",
        "AL",
        "AP",
        "AM",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MT",
        "MS",
        "MG",
        "PA",
        "PB",
        "PR",
        "PE",
        "PI",
        "RJ",
        "RN",
        "RS",
        "RO",
        "RR",
        "SC",
        "SP",
        "SE",
        "TO",
    }
)

Fase = Literal["novos", "inscricoes_abertas", "em_andamento", "encerrado"]

#: `faseEvento` (rótulo do grupo, medido em 19/09/2026 — §1 do plano) → `ConcursoDoRadar.fase`.
#: A fase nasce sempre daqui, nunca do caminho da URL (`/fase/<nome errado>` devolve HTTP 200 com
#: `[]`, não 404 — o achado que decidiu essa regra).
_FASES_POR_GRUPO: dict[str, Fase] = {
    "Novos": "novos",
    "Inscrições Abertas": "inscricoes_abertas",
    "Em Andamento": "em_andamento",
    "Encerrados": "encerrado",
}

#: Formato literal medido de `periodoInscricao` (evidência:
#: `knowledge/fixtures/fontes/cebraspe/evento-AGEPAR_PR_26-2026-09-19.json`). Qualquer outro
#: formato vira `(None, None)` mais uma lacuna — nunca uma data adivinhada.
_PADRAO_PERIODO = re.compile(
    r"^De (\d{2})/(\d{2})/(\d{4}) até (\d{2})/(\d{2})/(\d{4}) às \d{2}:\d{2}, "
    r"horário oficial de Bras[íi]lia/DF$"
)

LACUNA_DATA_PROVA = "data da prova não publicada na API"
LACUNA_VAGAS = "vagas não informadas"
LACUNA_SALARIO = "salário não informado"
LACUNA_PERIODO_FORMATO_DESCONHECIDO = "período de inscrição em formato não reconhecido"


class ConcursoDoRadar(BaseModel):
    """Um concurso do catálogo da Cebraspe, já normalizado (passo 1 do plano).

    Attributes:
        evento_url: identidade estável na fonte (`eventoURL` da API).
        nome: `eventoNomeAbreviado`, como a API escreve.
        ano: `eventoAno`, ou `None` quando ausente.
        fase: a fase do grupo em que o evento apareceu no catálogo (nunca do caminho da URL).
        uf: a UF confirmada (Ruling 39), ou `None` quando não confirmada nos dois lugares.
        vagas: `eventoTotalVagas` convertido para `int`; `None` quando ausente/vazio.
        salario_max_brl: `eventoSalarioMaximo`; `0` e ausente viram `None` (não é salário real).
        periodo_inscricao_texto: o texto literal de `periodoInscricao`, ou `None`.
        inscricao_inicio: início do período, só quando `periodo_inscricao_texto` casa o formato
            medido; senão `None`.
        inscricao_fim: fim do período, mesma regra de `inscricao_inicio`.
        lacunas: o que a API não informa para este item, em pt-BR — nunca escondido.
    """

    evento_url: str
    nome: str
    ano: int | None
    fase: Fase
    uf: str | None
    vagas: int | None
    salario_max_brl: Decimal | None
    periodo_inscricao_texto: str | None
    inscricao_inicio: date | None
    inscricao_fim: date | None
    lacunas: list[str]


class PreferenciaRadar(BaseModel):
    """O que a aluna declarou (ou não) sobre o que procura no radar (passo 2 do plano).

    Attributes:
        ufs: UFs de interesse; lista vazia = nenhuma preferência declarada.
        salario_minimo_brl: salário mínimo aceitável; `None` = sem preferência.
        area: `"direito"` ou `"qualquer"` (sem preferência de área).
    """

    ufs: list[str]
    salario_minimo_brl: Decimal | None
    area: Literal["direito", "qualquer"]


class Casamento(BaseModel):
    """O resultado de casar um `ConcursoDoRadar` com uma `PreferenciaRadar` (Ruling 40).

    Attributes:
        combina: `True` quando pelo menos um motivo bateu; nunca decide sozinho se o concurso
            aparece na lista (o catálogo mostra tudo — isto é só selo e ordenação).
        motivos: por que combina, em pt-BR, prontos para exibição (ex.: `"PR"`).
        contra: por que **não** combina mais — metade da honestidade (Ruling 40).
    """

    combina: bool
    motivos: list[str]
    contra: list[str]


def extrair_uf(nome: str, evento_url: str) -> str | None:
    """Confirma a UF de um concurso só quando ela aparece nos dois lugares (Ruling 39).

    A UF é um token solto no meio do nome (`"AGEPAR PR 26"`) e também precisa aparecer como
    token isolado no `eventoURL`, que separa por `_` (`"AGEPAR_PR_26"`). As duas confirmações
    evitam declarar UF errada para concursos federais cujo nome não tem token de duas letras que
    seja UF (ex.: `"AGU 26 ESTAGIARIO"`).

    Args:
        nome: `eventoNomeAbreviado`, como a API escreve.
        evento_url: `eventoURL`, como a API escreve.

    Returns:
        A UF (`"PR"`, `"MS"`...) quando confirmada nos dois lugares; `None` senão.
    """
    tokens_url = set(evento_url.split("_"))
    for token in nome.split():
        candidato = token.upper()
        if candidato in UFS_VALIDAS and candidato in tokens_url:
            return candidato
    return None


def ler_periodo_inscricao(texto: str | None) -> tuple[date | None, date | None]:
    """Lê `periodoInscricao` no formato literal medido; qualquer outro formato vira `(None, None)`.

    Args:
        texto: o campo `periodoInscricao` cru da API, ou `None`.

    Returns:
        `(inscricao_inicio, inscricao_fim)`; os dois `None` quando `texto` é `None` ou não casa
        o formato `"De DD/MM/AAAA até DD/MM/AAAA às HH:MM, horário oficial de Brasília/DF"` —
        nunca uma data adivinhada de um formato parecido.
    """
    if texto is None:
        return None, None
    casado = _PADRAO_PERIODO.match(texto.strip())
    if casado is None:
        return None, None
    d1, m1, a1, d2, m2, a2 = (int(grupo) for grupo in casado.groups())
    return date(a1, m1, d1), date(a2, m2, d2)


def _ler_vagas(bruto: Any) -> int | None:
    """`eventoTotalVagas` ("23", `None`, `""`) → `int` ou `None`."""
    if bruto in (None, ""):
        return None
    return int(bruto)


def _ler_salario(bruto: Any) -> Decimal | None:
    """`eventoSalarioMaximo` (número, `0` ou `None`) → `Decimal` ou `None` (0 não é salário)."""
    if not bruto:
        return None
    return Decimal(str(bruto))


def _ler_evento(evento: dict[str, Any], fase: Fase) -> ConcursoDoRadar:
    """Normaliza um item de `eventos[]` de um grupo do catálogo, já com a fase do grupo."""
    evento_url = evento["eventoURL"]
    nome = evento["eventoNomeAbreviado"]
    vagas = _ler_vagas(evento.get("eventoTotalVagas"))
    salario = _ler_salario(evento.get("eventoSalarioMaximo"))
    texto_periodo = evento.get("periodoInscricao")
    inicio, fim = ler_periodo_inscricao(texto_periodo)

    lacunas = [LACUNA_DATA_PROVA]
    if vagas is None:
        lacunas.append(LACUNA_VAGAS)
    if salario is None:
        lacunas.append(LACUNA_SALARIO)
    if texto_periodo is not None and inicio is None:
        lacunas.append(LACUNA_PERIODO_FORMATO_DESCONHECIDO)

    return ConcursoDoRadar(
        evento_url=evento_url,
        nome=nome,
        ano=evento.get("eventoAno"),
        fase=fase,
        uf=extrair_uf(nome, evento_url),
        vagas=vagas,
        salario_max_brl=salario,
        periodo_inscricao_texto=texto_periodo,
        inscricao_inicio=inicio,
        inscricao_fim=fim,
        lacunas=lacunas,
    )


def ler_catalogo(payload: object) -> list[ConcursoDoRadar]:
    """Lê o catálogo inteiro (`GET /cebraspe/eventos/tipo/concursos`, todas as fases numa chamada).

    A fase de cada item vem de `faseEvento` do **grupo**, nunca do caminho da URL (o achado do
    §1 do plano: `/fase/<nome errado>` devolve HTTP 200 com `[]`, não 404 — confiar no caminho
    esconderia esse erro).

    Args:
        payload: o corpo já decodificado da resposta (lista de grupos, cada um com `faseEvento`
            e `eventos[]`).

    Returns:
        Um `ConcursoDoRadar` por evento, na ordem em que os grupos e os eventos aparecem.

    Raises:
        ValueError: `payload` não é uma lista, ou algum grupo traz um `faseEvento` fora dos
            quatro conhecidos (`Novos`, `Inscrições Abertas`, `Em Andamento`, `Encerrados`) —
            falhar alto em vez de descartar o grupo em silêncio.
    """
    if not isinstance(payload, list):
        raise ValueError(f"catálogo esperava uma lista de grupos, recebeu {type(payload).__name__}")

    concursos: list[ConcursoDoRadar] = []
    for grupo in payload:
        nome_grupo = grupo.get("faseEvento")
        fase = _FASES_POR_GRUPO.get(nome_grupo)
        if fase is None:
            raise ValueError(f"faseEvento desconhecida no catálogo: {nome_grupo!r}")
        for evento in grupo.get("eventos") or []:
            concursos.append(_ler_evento(evento, fase))
    return concursos


def casar_com_perfil(
    concurso: ConcursoDoRadar, preferencia: PreferenciaRadar, cargos: list[str]
) -> Casamento:
    """Casa um concurso do radar com a preferência da aluna (Ruling 40: ordena e marca, não filtra).

    Sem nenhuma preferência preenchida, `combina=False` e `motivos=[]` — nunca "combina com
    tudo" por padrão. A área "direito" reusa `motor.coletar.cargo_de_direito` (o mesmo léxico da
    V3: "Direito", "Judiciária", "Jurídica", "Jurídico"), sem reimplementá-lo.

    Args:
        concurso: o concurso do radar já normalizado.
        preferencia: o que a aluna declarou.
        cargos: os textos de `eventoCargos[].area` do detalhe do evento; lista vazia quando o
            detalhe ainda não foi consultado (a varredura do catálogo não abre detalhe por
            evento — custo demais para uma rodada).

    Returns:
        O `Casamento`: se combina, por quê, e por que não combina mais.
    """
    sem_preferencia = not preferencia.ufs and preferencia.salario_minimo_brl is None
    sem_preferencia = sem_preferencia and preferencia.area == "qualquer"
    if sem_preferencia:
        return Casamento(combina=False, motivos=[], contra=[])

    motivos: list[str] = []
    contra: list[str] = []

    if preferencia.ufs:
        if concurso.uf is not None and concurso.uf in preferencia.ufs:
            motivos.append(concurso.uf)
        elif concurso.uf is not None:
            contra.append(f"UF fora do seu interesse ({concurso.uf})")

    if preferencia.salario_minimo_brl is not None and concurso.salario_max_brl is not None:
        if concurso.salario_max_brl >= preferencia.salario_minimo_brl:
            motivos.append("salário acima do seu mínimo")
        else:
            contra.append("salário abaixo do seu mínimo")

    if preferencia.area == "direito":
        cargos_evento = [
            CargoEvento(id_area=str(indice), area=area) for indice, area in enumerate(cargos)
        ]
        if cargo_de_direito(cargos_evento):
            motivos.append("cargo de Direito")
        elif cargos:
            contra.append("nenhum cargo de Direito identificado")

    return Casamento(combina=bool(motivos), motivos=motivos, contra=contra)

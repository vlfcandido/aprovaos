"""Classificador alimentado por arquivo — cura sem gastar a cota de LLM do projeto (ADR-0054).

O que é: `ClassificadorDeArquivo`, uma implementação da porta `ClassificadorDeTopico` que lê a
decisão de tópico de um JSON em vez de chamar o modelo, e `carregar_classificacoes` para ler esse
arquivo. Quando ler: ao curar um caderno com a classificação feita fora do pipeline, ou ao mudar
o formato do arquivo.

**Por que existe.** No piloto (n = 1) o gargalo é a cota do free tier — 20 requisições por dia
por modelo — e curar os cadernos coletados custaria 24 chamadas em dois dias. A decisão de qual
tópico um item cobra é classificação num vocabulário fechado: dá para tomá-la fora do pipeline e
trazer pronta. O que **não** muda de lugar: segmentação, leitura de gabarito, dedup, validação e
gravação continuam exatamente os mesmos, e o slug decidido continua sendo conferido contra o
vocabulário do edital — inventar slug é rejeitado aqui como seria numa resposta do modelo.

**Isto é bootstrap do piloto, não arquitetura.** Para dez pagantes o produto tem de classificar
sozinho; o gatilho para aposentar este caminho está na ADR-0054.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

from aprovaos.motor.curadoria.classificacao import (
    Classificacao,
    ItemParaClassificar,
    MotivosRejeicao,
    TopicoVocabulario,
)

#: Prefixo que toda `evidencia` vinda de arquivo carrega, para que a procedência apareça em
#: qualquer consulta ao banco — não só na documentação (decisão do dono, 24/09/2026). Sem isto,
#: daqui a um mês ninguém sabe que aquelas questões não foram classificadas pelo pipeline.
MARCA_DE_PROCEDENCIA = "classificado fora do pipeline"


def carregar_classificacoes(caminho: Path) -> dict[int, dict[str, Any]]:
    """Lê o arquivo de classificação e indexa por `numero_item`.

    Args:
        caminho: o JSON produzido a partir do `--exportar-itens`, com a chave `classificacoes`.

    Returns:
        `{numero_item: {"topico_slug": str | None, "evidencia": str}}`.

    Raises:
        ValueError: o arquivo não tem a chave `classificacoes`, ou uma entrada não tem
            `numero_item` — melhor falhar aqui do que curar meio caderno em silêncio.
    """
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    entradas = dados.get("classificacoes")
    if entradas is None:
        raise ValueError(f"{caminho}: arquivo sem a chave 'classificacoes'")
    indexado: dict[int, dict[str, Any]] = {}
    for entrada in entradas:
        numero = entrada.get("numero_item")
        if numero is None:
            raise ValueError(f"{caminho}: entrada sem 'numero_item': {entrada!r}")
        indexado[int(numero)] = entrada
    return indexado


class ClassificadorDeArquivo:
    """Porta de classificação servida por um arquivo já decidido.

    Cumpre o mesmo contrato de `ClassificadorDeTopico`: item que o arquivo não decidiu não vira
    `Classificacao` (o curador o manda para regras, como faria com um item ausente na resposta do
    modelo), e slug fora do vocabulário vira rejeição com motivo, nunca gravação.
    """

    def __init__(self, classificacoes: dict[int, dict[str, Any]], hoje: date | None = None) -> None:
        """Guarda as decisões já tomadas.

        Args:
            classificacoes: saída de `carregar_classificacoes`.
            hoje: data da marca de procedência; `None` usa a de hoje (parâmetro para o teste não
                depender do relógio).
        """
        self._classificacoes = classificacoes
        self._hoje = hoje or date.today()

    async def classificar_lote(
        self, itens: list[ItemParaClassificar], vocabulario: list[TopicoVocabulario]
    ) -> tuple[list[Classificacao], MotivosRejeicao]:
        """Devolve a decisão de cada item que o arquivo cobre.

        Args:
            itens: os itens do lote.
            vocabulario: os tópicos do edital — a lista contra a qual o slug é conferido.

        Returns:
            `(classificacoes, motivos_rejeicao)`, no mesmo contrato da porta.
        """
        slugs_validos = {topico.slug for topico in vocabulario}
        recebidas: list[Classificacao] = []
        rejeicoes: MotivosRejeicao = {}
        for item in itens:
            entrada = self._classificacoes.get(item.numero_item)
            if entrada is None:
                continue
            slug = entrada.get("topico_slug")
            if slug is not None and slug not in slugs_validos:
                rejeicoes[item.numero_item] = f"slug fora do vocabulário do edital: {slug!r}"
                continue
            recebidas.append(
                Classificacao(
                    numero_item=item.numero_item,
                    topico_slug=slug,
                    confianca="alta" if slug else "baixa",
                    evidencia=(
                        f"{MARCA_DE_PROCEDENCIA} em {self._hoje.strftime('%d/%m/%Y')}: "
                        f"{entrada.get('evidencia', 'sem evidência declarada')}"
                    ),
                    origem="ia",
                )
            )
        return recebidas, rejeicoes

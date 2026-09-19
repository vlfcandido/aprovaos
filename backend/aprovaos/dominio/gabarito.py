"""Leitura do gabarito definitivo de um caderno Cebraspe certo/errado: texto → mapa de entradas.

O que é: `EntradaGabarito` (Pydantic) e `ler_gabarito_cebraspe(texto: str) -> dict[int,
EntradaGabarito]`, que implementam a seção "Gabarito: a ordem de verdade" da skill
`ingestao-de-provas`. Função pura, sem IA, sem rede, sem disco — quem lê o PDF
(`dominio/pdf.extrair_texto`) é quem chama; a decisão do que fazer com um item sem entrada no
mapa (`dict.get` devolve `None`) é do curador. Quando ler: ao ajustar a leitura para um gabarito
Cebraspe real que ela não entendeu, ou ao ligar o resultado ao `ItemBruto` de `dominio/prova.py`.
"""

import re
from typing import Literal

from pydantic import BaseModel

from aprovaos.dominio.erros import GabaritoNaoReconhecido

_LINHA_DE_NUMEROS = re.compile(r"^[\d\s]+$")
"""Uma linha do quadro com só números de item e espaços (a extração pode juntar os `0` de
preenchimento em blocos como "000", mas nunca junta um número real de item com outro)."""

_LINHA_DE_VALORES = re.compile(r"^[CEX0\s]+$")
"""A linha logo abaixo de uma linha de números: um valor por item (`C`, `E` ou `X` de anulado) ou
`0` onde o quadro não tem item. A extração do PDF às vezes gruda colunas vizinhas sem espaço
entre elas (colunas de 1 caractere) — por isso o padrão não exige espaço entre os caracteres."""

_MARCADOR_DEFINITIVO = re.compile(r"(?i)definitivo")
"""Aparece em "GABARITOS OFICIAIS DEFINITIVOS" nos quatro gabaritos reais desta fatia."""

_MARCADOR_PRELIMINAR = re.compile(r"(?i)preliminar")
"""Aparece em "GABARITO PRELIMINAR" quando o documento só tem gabarito preliminar."""


class EntradaGabarito(BaseModel):
    """Uma linha do gabarito Cebraspe para um item do caderno.

    Attributes:
        valor: o gabarito do item ("C" ou "E"); `None` quando o item foi anulado.
        status: "definitivo" (valor final, sem preliminar diferente), "preliminar" (o documento
            só tem gabarito preliminar), "anulado" (a banca anulou o item) ou "alterado" (o
            documento trouxe um gabarito preliminar e um definitivo diferentes para o item).
        valor_preliminar: o valor anterior ao definitivo, só preenchido quando
            `status == "alterado"`.
    """

    valor: Literal["C", "E"] | None
    status: Literal["definitivo", "preliminar", "anulado", "alterado"]
    valor_preliminar: Literal["C", "E"] | None = None


def _pares_item_valor(linhas: list[str]) -> list[tuple[int, str]]:
    """Acha, em sequência, todo par (linha de números de item, linha de valores) do texto.

    Percorre as linhas aos pares candidatos: sempre que uma linha só tem números e ao menos um
    deles não é `0`, olha a linha seguinte; se ela só tem `C`/`E`/`X`/`0` e tem pelo menos uma
    letra, é a linha de valores do mesmo bloco. Qualquer outra linha (cabeçalho, rótulo de
    coluna, rodapé) não casa com nenhum dos dois padrões e é ignorada.

    Args:
        linhas: linhas do texto extraído, sem vazias, na ordem do documento.

    Returns:
        Os pares `(numero_item, valor)` na ordem em que apareceram no texto — um item pode
        aparecer mais de uma vez se o documento tiver mais de um quadro (preliminar e
        definitivo).

    Raises:
        GabaritoNaoReconhecido: uma linha de valores reconhecida tem uma quantidade de letras
            diferente da quantidade de itens não nulos da linha de números correspondente —
            estrutura de quadro que a leitura não cobre.
    """
    pares: list[tuple[int, str]] = []
    indice = 0
    while indice < len(linhas) - 1:
        linha_numeros = linhas[indice]
        if not _LINHA_DE_NUMEROS.fullmatch(linha_numeros):
            indice += 1
            continue
        itens = [n for n in (int(tok) for tok in re.findall(r"\d+", linha_numeros)) if n != 0]
        if not itens:
            indice += 1
            continue
        linha_valores = linhas[indice + 1]
        if not _LINHA_DE_VALORES.fullmatch(linha_valores):
            indice += 1
            continue
        valores = re.findall(r"[CEX]", linha_valores)
        if not valores:
            indice += 1
            continue
        if len(valores) != len(itens):
            raise GabaritoNaoReconhecido(
                f"Quadro do gabarito com {len(itens)} itens ({itens[0]}–{itens[-1]}) mas "
                f"{len(valores)} valores na linha seguinte — estrutura não reconhecida."
            )
        pares.extend(zip(itens, valores, strict=True))
        indice += 2
    return pares


def ler_gabarito_cebraspe(texto: str) -> dict[int, EntradaGabarito]:
    """Lê o gabarito de um caderno Cebraspe certo/errado, sem IA e sem rede.

    Implementa a seção "Gabarito: a ordem de verdade" da skill `ingestao-de-provas`: um item
    marcado "X" no quadro é anulado (`valor=None`); um item que aparece em dois quadros do mesmo
    documento (preliminar e definitivo) com valores diferentes é alterado (`valor` = o último
    valor do texto, `valor_preliminar` = o primeiro); um item com valor único é definitivo, salvo
    se o documento só tiver a palavra "preliminar" (nunca "definitivo") — aí é preliminar.

    Pré-condição: **o texto é de um único caderno/cargo**. A detecção de "alterado" decide pelo
    número do item aparecer duas vezes no texto com valores diferentes — ela não sabe distinguir
    "o mesmo item, dois quadros (preliminar e definitivo)" de "dois cargos diferentes, cada um
    com seu próprio item 1". Um PDF que consolidasse o gabarito de vários cargos na mesma matriz
    (a Cebraspe faz isso em alguns editais) produziria itens de cargos diferentes com o mesmo
    número, e a função os leria como um único item "alterado" por engano, em silêncio — por isso
    quem chama tem de garantir de antemão que o texto é de um cargo só (ex.: já separou o PDF por
    página/seção de cargo antes de extrair o texto). Não há checagem barata e honesta para essa
    pré-condição (faixa de itens não contígua também acontece legitimamente dentro de um cargo só,
    por causa dos "0" de preenchimento do quadro) — por isso ela é só documentada aqui, não
    imposta em código; ver `docs/PENDENCIAS.md`.

    Args:
        texto: texto do gabarito de **um único caderno/cargo**, já extraído do PDF
            (`dominio.pdf.extrair_texto`).

    Returns:
        Um mapa `numero_item -> EntradaGabarito`. Consultar um item que não está no mapa (fora do
        intervalo do caderno) é responsabilidade de quem chama (`dict.get` devolve `None`); o
        preenchimento "0" fora do intervalo do quadro nunca vira entrada.

    Raises:
        GabaritoNaoReconhecido: o texto não tem nenhuma grade de gabarito Cebraspe C/E
            reconhecível (nem um par válido de linha de números com linha de valores) — cobre
            tanto um PDF qualquer quanto um gabarito de banca em outro formato (ex.: múltipla
            escolha A–E).
    """
    linhas = [linha.strip() for linha in texto.split("\n") if linha.strip()]
    pares = _pares_item_valor(linhas)
    if not pares:
        raise GabaritoNaoReconhecido(
            "Não reconheci uma grade de gabarito Cebraspe C/E (itens numerados com valor "
            "C/E/X) neste texto."
        )

    ocorrencias: dict[int, list[str]] = {}
    for numero, valor in pares:
        ocorrencias.setdefault(numero, []).append(valor)

    tem_definitivo = bool(_MARCADOR_DEFINITIVO.search(texto))
    tem_preliminar = bool(_MARCADOR_PRELIMINAR.search(texto))

    gabarito: dict[int, EntradaGabarito] = {}
    for numero, valores in ocorrencias.items():
        valor_inicial, valor_final = valores[0], valores[-1]
        if valor_final == "X":
            gabarito[numero] = EntradaGabarito(valor=None, status="anulado")
            continue
        if len(valores) > 1 and valor_inicial != valor_final:
            preliminar = valor_inicial if valor_inicial in ("C", "E") else None
            gabarito[numero] = EntradaGabarito(
                valor=valor_final, status="alterado", valor_preliminar=preliminar
            )
            continue
        status: Literal["definitivo", "preliminar"] = (
            "definitivo" if tem_definitivo or not tem_preliminar else "preliminar"
        )
        gabarito[numero] = EntradaGabarito(valor=valor_final, status=status)
    return gabarito

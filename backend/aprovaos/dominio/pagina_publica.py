"""O corte que decide se uma página pública nasce, e os textos derivados do dado (fatia 13).

O que é: `PaginaPublica` (os metadados de toda página pública — `<title>`, `<meta description>`,
`<h1>`, canônica, data), `cabe_em_pagina` (o corte do playbook §3.4/plano §1: família A só existe
com ≥5 questões classificadas no tópico **ou** um dossiê publicado — "página fina em escala é o
caminho mais curto para penalização"), `montar_titulo_de_topico` (o `<title>` sem o nome da banca
quando ela é desconhecida — nunca a string "banca desconhecida") e `ajustar_descricao` (garante a
faixa de 120–160 caracteres da meta description; cortada pelo buscador é o defeito silencioso mais
comum de programática, plano §2). Funções puras, sem I/O, sem banco — quem soma questão/dossiê é
`dados.repositorio_publico`. Quando ler: antes de mudar o corte de qualquer família de página
pública, ou o texto de `<title>`/`<meta description>`.
"""

from datetime import date

from pydantic import BaseModel, field_validator

#: O corte da família A (plano §1, Ruling do playbook §3.4): abaixo disso a página não nasce.
CORTE_MINIMO_QUESTOES = 5

#: Faixa aceita de `<meta name="description">` — abaixo ou acima disso o buscador corta o texto
#: (playbook §4) e o defeito passa despercebido até alguém olhar o resultado de busca de verdade.
DESCRICAO_MINIMO = 120
DESCRICAO_MAXIMO = 160

#: Valores de `banca`/campo desconhecido que **nunca** aparecem no `<title>` como se fossem um
#: nome de banca de verdade — mesma convenção de `Concurso.banca` (nunca `NULL`, "desconhecido"
#: quando o edital não a declara).
_BANCA_DESCONHECIDA = {None, "desconhecido", ""}

_SUFIXO_DESCRICAO_CURTA = " Veja a origem completa e a explicação de cada questão no AprovaOS."


class PaginaPublica(BaseModel):
    """Os metadados de uma página pública, comuns às quatro famílias (playbook §2).

    Attributes:
        caminho: o endereço da página (ex.: `/o-que-cai/cebraspe/direito-administrativo/...`).
        titulo: `<title>`, derivado do dado, único por página.
        descricao: `<meta name="description">`; sempre entre `DESCRICAO_MINIMO` e
            `DESCRICAO_MAXIMO` caracteres (ver `ajustar_descricao`).
        h1: o único `<h1>` da página.
        canonica: caminho da página canônica (Ruling 49/ADR-0041), quando esta página é
            equivalente a outra de maior cobertura medida; `None` quando esta já é a canônica.
        atualizada_em: data do dado mais recente que sustenta a página — vira `Last-Modified` e
            entra no `sitemap.xml`.
    """

    caminho: str
    titulo: str
    descricao: str
    h1: str
    canonica: str | None = None
    atualizada_em: date

    @field_validator("descricao")
    @classmethod
    def _descricao_na_faixa(cls, valor: str) -> str:
        """Levanta `ValueError` fora de `[DESCRICAO_MINIMO, DESCRICAO_MAXIMO]` caracteres."""
        tamanho = len(valor)
        if not (DESCRICAO_MINIMO <= tamanho <= DESCRICAO_MAXIMO):
            raise ValueError(
                f"descrição com {tamanho} caracteres — precisa estar entre {DESCRICAO_MINIMO} "
                f"e {DESCRICAO_MAXIMO} (meta description cortada pelo buscador é o defeito "
                "silencioso mais comum de programática)"
            )
        return valor


def cabe_em_pagina(n_questoes: int, tem_dossie: bool) -> bool:
    """O corte da família A (plano §1): só nasce página com substância própria.

    Args:
        n_questoes: quantas questões publicáveis já classificadas neste tópico (para esta
            banca — quem conta é `dados.repositorio_publico`).
        tem_dossie: se este tópico já tem um dossiê publicado.

    Returns:
        `True` quando `n_questoes >= CORTE_MINIMO_QUESTOES` ou `tem_dossie` é `True`; `False`
        abaixo disso — a página **não** é gerada (playbook §3.4: página fina em escala é o
        caminho mais curto para penalização).
    """
    return n_questoes >= CORTE_MINIMO_QUESTOES or tem_dossie


def montar_titulo_de_topico(materia: str, topico: str, banca: str | None, n_questoes: int) -> str:
    """Monta o `<title>` da família A, derivado do dado — nunca "banca desconhecida".

    Args:
        materia: nome da matéria (ex.: `"Direito Administrativo"`).
        topico: nome do tópico (ex.: `"Improbidade administrativa"`).
        banca: banca examinadora, ou `None`/`"desconhecido"` quando a fonte não a declara (Ruling
            50: o nome da banca é texto factual, nunca um selo de produto).
        n_questoes: quantas questões publicáveis sustentam a página.

    Returns:
        `"{tópico} — {matéria} ({banca}): N questões classificadas | AprovaOS"`, sem o segmento
        `(banca)` quando `banca` é desconhecida.
    """
    plural = "questão classificada" if n_questoes == 1 else "questões classificadas"
    base = f"{topico} — {materia}"
    if banca not in _BANCA_DESCONHECIDA:
        base += f" ({banca})"
    return f"{base}: {n_questoes} {plural} | AprovaOS"


def ajustar_descricao(
    texto: str, *, minimo: int = DESCRICAO_MINIMO, maximo: int = DESCRICAO_MAXIMO
) -> str:
    """Normaliza espaços e garante que `texto` caiba em `[minimo, maximo]` caracteres.

    Completa com um sufixo padrão quando o texto é curto demais; corta na última palavra inteira
    que caiba quando é longo demais — nunca corta uma palavra ao meio. Existe para que quem monta
    `PaginaPublica.descricao` nunca precise contar caracteres na mão (o defeito silencioso que o
    playbook §4 descreve).

    Args:
        texto: o texto bruto (frase(s) já corretas semanticamente).
        minimo: tamanho mínimo aceito (padrão: `DESCRICAO_MINIMO`).
        maximo: tamanho máximo aceito (padrão: `DESCRICAO_MAXIMO`).

    Returns:
        `texto` ajustado para `minimo <= len(resultado) <= maximo`.
    """
    texto = " ".join(texto.split())
    while len(texto) < minimo:
        texto = texto + _SUFIXO_DESCRICAO_CURTA
    if len(texto) > maximo:
        cortado = texto[:maximo]
        ultimo_espaco = cortado.rfind(" ")
        if ultimo_espaco >= minimo:
            cortado = cortado[:ultimo_espaco]
        texto = cortado.rstrip(" ,;:-")
        while len(texto) < minimo:
            # Defensivo: só ocorre se o corte na última palavra tiver descido abaixo do mínimo
            # (frase com uma palavra muito longa perto do limite) — completa com pontuação, nunca
            # espaço, para não parecer texto truncado no resultado de busca.
            texto = texto + "."
    return texto

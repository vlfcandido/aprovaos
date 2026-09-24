"""Contraste de cor do sistema de design: lê `tokens.css` e mede par a par (WCAG 2.2 AA).

O que é: a conta de contraste da WCAG 2.x (luminância relativa sRGB) mais a **lista declarada**
dos pares texto/fundo que o produto realmente usa. Existe para que "contraste AA" seja um fato
medido a cada `pytest`, e não uma frase no documento: o tema escuro e o sépia são editados à mão,
e um token escurecido por engano some da revisão humana mas não some daqui. A mesma medida
alimenta a tabela de `GET /estilo`, para quem desenha ver o número sem sair do navegador.

Fonte da fórmula: WCAG 2.2, "Contrast (Minimum)" 1.4.3 e a definição de *relative luminance*
(https://www.w3.org/TR/WCAG22/#dfn-relative-luminance) — AA exige 4,5:1 em texto normal e 3:1 em
texto grande e em limite de componente de interface (1.4.11).

Quando ler: ao criar cor nova, ao criar tema novo, ou quando `tests/test_contraste.py` reprovar.
Nenhuma função aqui lê disco nem tem efeito em import: quem lê o arquivo é quem chama.
"""

import re

from pydantic import BaseModel, Field

_BLOCO = re.compile(r"(?P<seletor>[^{}]+)\{(?P<corpo>[^{}]*)\}")
_DECLARACAO = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")
_COMENTARIO = re.compile(r"/\*.*?\*/", re.DOTALL)

#: Mínimo da WCAG 2.2 AA para texto normal (1.4.3).
MINIMO_TEXTO = 4.5
#: Mínimo da WCAG 2.2 AA para texto grande e para limite de componente (1.4.3 e 1.4.11).
MINIMO_GRANDE = 3.0


class ParDeCor(BaseModel):
    """Um par texto/fundo que o produto usa de verdade, com o mínimo exigido dele.

    Attributes:
        texto: nome do token da cor de frente (ex.: `--cor-texto-2`).
        fundo: nome do token da cor de fundo (ex.: `--cor-superficie`).
        minimo: razão mínima aceitável — `MINIMO_TEXTO` ou `MINIMO_GRANDE`.
        onde: onde esse par aparece na interface, em português, para a mensagem de falha
            dizer o que conserta em vez de só qual token quebrou.
    """

    model_config = {"frozen": True}

    texto: str
    fundo: str
    minimo: float = MINIMO_TEXTO
    onde: str = Field(min_length=3)


class MedidaDeContraste(BaseModel):
    """O resultado de medir um `ParDeCor` num tema.

    Attributes:
        tema: `claro`, `escuro` ou `sepia`.
        par: o par medido.
        cor_texto: o valor hexadecimal resolvido da cor de frente naquele tema.
        cor_fundo: o valor hexadecimal resolvido do fundo naquele tema.
        razao: a razão de contraste, de 1,0 a 21,0.
        aprovado: `True` quando `razao >= par.minimo`.
    """

    model_config = {"frozen": True}

    tema: str
    par: ParDeCor
    cor_texto: str
    cor_fundo: str
    razao: float
    aprovado: bool


#: Os pares que a interface usa. Acrescentar cor ao sistema significa acrescentar o par aqui —
#: cor que ninguém mede é cor que ninguém garante.
PARES_OBRIGATORIOS: tuple[ParDeCor, ...] = (
    ParDeCor(texto="--cor-texto", fundo="--cor-fundo", onde="texto da página"),
    ParDeCor(texto="--cor-texto", fundo="--cor-superficie", onde="texto dentro do cartão"),
    ParDeCor(texto="--cor-texto", fundo="--cor-superficie-2", onde="texto sobre faixa/selo neutro"),
    ParDeCor(texto="--cor-texto-2", fundo="--cor-fundo", onde="texto de apoio (.muted)"),
    ParDeCor(texto="--cor-texto-2", fundo="--cor-superficie", onde="texto de apoio no cartão"),
    ParDeCor(texto="--cor-texto-2", fundo="--cor-superficie-2", onde="selo neutro (.chip)"),
    ParDeCor(texto="--cor-texto-3", fundo="--cor-fundo", onde="rótulo (.eyebrow) na página"),
    ParDeCor(texto="--cor-texto-3", fundo="--cor-superficie", onde="rótulo (.eyebrow) no cartão"),
    ParDeCor(texto="--cor-acao", fundo="--cor-fundo", onde="link na página"),
    ParDeCor(texto="--cor-acao", fundo="--cor-superficie", onde="link e citação legal no cartão"),
    ParDeCor(texto="--cor-acao-texto", fundo="--cor-acao", onde="rótulo do botão principal"),
    ParDeCor(texto="--cor-acao", fundo="--cor-acao-suave", onde="selo de destaque (.chip accent)"),
    ParDeCor(texto="--cor-ok", fundo="--cor-ok-suave", onde="selo de acerto (.chip good)"),
    ParDeCor(texto="--cor-erro", fundo="--cor-erro-suave", onde="selo de erro (.chip bad)"),
    ParDeCor(texto="--cor-alerta", fundo="--cor-alerta-suave", onde="selo de atenção (.chip warn)"),
    ParDeCor(texto="--cor-porque-texto", fundo="--cor-porque-suave", onde="selo novo (.chip novo)"),
    ParDeCor(texto="--cor-texto", fundo="--cor-porque-suave", onde="o porquê do agente (.why)"),
    ParDeCor(
        texto="--cor-porque",
        fundo="--cor-porque-suave",
        minimo=MINIMO_GRANDE,
        onde="a barra âmbar do .why (limite gráfico, WCAG 1.4.11)",
    ),
    ParDeCor(texto="--cor-ok", fundo="--cor-superficie", onde="texto de confirmação no cartão"),
    ParDeCor(texto="--cor-erro", fundo="--cor-superficie", onde="mensagem de erro no cartão"),
    ParDeCor(
        texto="--cor-lateral-texto", fundo="--cor-lateral-fundo", onde="navegação lateral, repouso"
    ),
    ParDeCor(
        texto="--cor-lateral-texto-forte",
        fundo="--cor-lateral-fundo",
        onde="marca e item ativo da navegação",
    ),
    ParDeCor(
        texto="--cor-lateral-texto-forte",
        fundo="--cor-lateral-ativo",
        onde="item atual da navegação",
    ),
    ParDeCor(
        texto="--cor-lateral-rotulo",
        fundo="--cor-lateral-fundo",
        onde="rótulo de grupo da navegação",
    ),
    ParDeCor(
        texto="--cor-lateral-acento",
        fundo="--cor-lateral-fundo",
        minimo=MINIMO_GRANDE,
        onde="a barra que marca a tela atual (limite gráfico, WCAG 1.4.11)",
    ),
    ParDeCor(
        texto="--cor-linha-forte",
        fundo="--cor-superficie",
        minimo=MINIMO_GRANDE,
        onde="borda de campo e de controle (WCAG 1.4.11)",
    ),
    *(
        ParDeCor(
            texto=f"--materia-{numero}",
            fundo="--cor-superficie",
            minimo=MINIMO_GRANDE,
            onde=f"marca da matéria {numero} (limite gráfico, WCAG 1.4.11)",
        )
        for numero in range(1, 10)
    ),
)


def _canal_linear(valor: int) -> float:
    """Converte um canal sRGB de 0–255 para luminância linear (WCAG 2.2)."""
    fracao = valor / 255
    return fracao / 12.92 if fracao <= 0.03928 else ((fracao + 0.055) / 1.055) ** 2.4


def converter_hexadecimal(cor: str) -> tuple[int, int, int]:
    """Converte `#rgb` ou `#rrggbb` (com ou sem `#`) na tripla RGB de 0 a 255.

    Args:
        cor: a cor em hexadecimal, como aparece no `tokens.css`.

    Returns:
        A tripla `(vermelho, verde, azul)`.

    Raises:
        ValueError: quando a cor não é um hexadecimal de 3 ou 6 dígitos — o medidor não adivinha
            `rgb()`, `color-mix()` nem nome de cor; token de tema é hexadecimal por contrato.
    """
    limpa = cor.strip().removeprefix("#")
    if len(limpa) == 3:
        limpa = "".join(digito * 2 for digito in limpa)
    if len(limpa) != 6 or not all(digito in "0123456789abcdefABCDEF" for digito in limpa):
        raise ValueError(f"cor fora do contrato (use #rgb ou #rrggbb): {cor!r}")
    return int(limpa[0:2], 16), int(limpa[2:4], 16), int(limpa[4:6], 16)


def luminancia_relativa(cor: str) -> float:
    """Calcula a luminância relativa de uma cor sRGB, de 0 (preto) a 1 (branco).

    Args:
        cor: a cor em hexadecimal.

    Returns:
        A luminância relativa definida pela WCAG 2.2.
    """
    vermelho, verde, azul = converter_hexadecimal(cor)
    return (
        0.2126 * _canal_linear(vermelho)
        + 0.7152 * _canal_linear(verde)
        + 0.0722 * _canal_linear(azul)
    )


def razao_de_contraste(cor_a: str, cor_b: str) -> float:
    """Mede a razão de contraste entre duas cores, de 1,0 (iguais) a 21,0 (preto e branco).

    Args:
        cor_a: uma das cores, em hexadecimal.
        cor_b: a outra cor, em hexadecimal. A ordem não importa.

    Returns:
        A razão `(L_maior + 0,05) / (L_menor + 0,05)`.
    """
    primeira, segunda = luminancia_relativa(cor_a), luminancia_relativa(cor_b)
    maior, menor = max(primeira, segunda), min(primeira, segunda)
    return (maior + 0.05) / (menor + 0.05)


def ler_temas(css: str) -> dict[str, dict[str, str]]:
    """Lê `tokens.css` e devolve o valor final de cada token em cada tema.

    O tema claro é o `:root`; escuro e sépia são os blocos `:root[data-theme="…"]`, **herdando**
    do claro tudo que não sobrescrevem (é assim que o navegador resolve, e é assim que espaço e
    tipografia continuam valendo nos três). O bloco dentro de `@media (prefers-color-scheme: dark)`
    é ignorado de propósito: ele é a cópia automática do escuro, e quem responde pelo tema é o
    bloco fixado — o teste `test_tema_escuro_automatico_espelha_o_fixado` cuida de os dois não
    divergirem.

    Args:
        css: o conteúdo de `web/static/css/tokens.css`.

    Returns:
        `{"claro": {...}, "escuro": {...}, "sepia": {...}}`, do nome do token (`--cor-fundo`) ao
        valor literal declarado.
    """
    blocos = {
        seletor.strip(): dict(_DECLARACAO.findall(corpo))
        for seletor, corpo in _BLOCO.findall(_sem_media(_COMENTARIO.sub("", css)))
    }
    claro = blocos.get(":root", {})
    temas = {"claro": {chave: valor.strip() for chave, valor in claro.items()}}
    for tema in ("escuro", "sepia"):
        sobrescritas = blocos.get(f':root[data-theme="{tema}"]')
        if sobrescritas is None:
            continue
        temas[tema] = temas["claro"] | {
            chave: valor.strip() for chave, valor in sobrescritas.items()
        }
    return temas


def ler_escuro_automatico(css: str) -> dict[str, str]:
    """Lê as declarações do bloco `@media (prefers-color-scheme: dark)`.

    Esse bloco é a cópia do tema escuro que vale para quem nunca tocou no alternador — e cópia
    é a coisa que diverge. Existe para o teste comparar as duas listas.

    Args:
        css: o conteúdo de `web/static/css/tokens.css`.

    Returns:
        Do nome do token ao valor declarado dentro da consulta de mídia; vazio se ela não existe.
    """
    sem_comentarios = _COMENTARIO.sub("", css)
    inicio = sem_comentarios.find("@media (prefers-color-scheme: dark)")
    if inicio == -1:
        return {}
    corpo = sem_comentarios[inicio:]
    fim = len(corpo)
    profundidade = 0
    for indice, caractere in enumerate(corpo):
        if caractere == "{":
            profundidade += 1
        elif caractere == "}":
            profundidade -= 1
            if profundidade == 0:
                fim = indice
                break
    return {chave: valor.strip() for chave, valor in _DECLARACAO.findall(corpo[:fim])}


def _sem_media(css: str) -> str:
    """Remove os blocos `@media` inteiros, que o leitor de temas não interpreta."""
    saida: list[str] = []
    resto = css
    while (inicio := resto.find("@media")) != -1:
        saida.append(resto[:inicio])
        profundidade = 0
        abertura = resto.find("{", inicio)
        if abertura == -1:
            return "".join(saida)
        fim = len(resto) - 1
        for posicao in range(abertura, len(resto)):
            if resto[posicao] == "{":
                profundidade += 1
            elif resto[posicao] == "}":
                profundidade -= 1
                if profundidade == 0:
                    fim = posicao
                    break
        resto = resto[fim + 1 :]
    saida.append(resto)
    return "".join(saida)


def medir_pares(
    temas: dict[str, dict[str, str]],
    pares: tuple[ParDeCor, ...] = PARES_OBRIGATORIOS,
) -> list[MedidaDeContraste]:
    """Mede todos os pares em todos os temas.

    Args:
        temas: a saída de `ler_temas`.
        pares: os pares a medir; o padrão é o contrato inteiro.

    Returns:
        Uma medida por combinação de tema e par, na ordem dos temas e dos pares.

    Raises:
        KeyError: quando um tema não define um dos tokens do par — o que, na prática, é a cor de
            outro tema vazando para dentro deste.
    """
    medidas: list[MedidaDeContraste] = []
    for tema, valores in temas.items():
        for par in pares:
            cor_texto, cor_fundo = valores[par.texto], valores[par.fundo]
            razao = razao_de_contraste(cor_texto, cor_fundo)
            medidas.append(
                MedidaDeContraste(
                    tema=tema,
                    par=par,
                    cor_texto=cor_texto,
                    cor_fundo=cor_fundo,
                    razao=round(razao, 2),
                    aprovado=razao >= par.minimo,
                )
            )
    return medidas

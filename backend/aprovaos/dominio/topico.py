"""Nome legível de um tópico a partir do texto literal do item do edital.

O que é: `nome_curto(literal)` — função pura, sem rede, banco ou LLM. Quando ler: ao mudar como
o nome de um tópico aparece na tela, ou ao investigar um rótulo cortado no lugar errado.

**Por que existe.** `topico.nome` guarda o item do edital **como o edital escreve**, e isso é
proposital: é a procedência do tópico, o que permite conferir contra o PDF. Só que o edital
escreve para um concurso, não para uma tela — numeração na frente (`"4 Atos administrativos"`),
subitens embutidos (`"Provas. 6.1. Teoria geral... 6.2. Meios..."`) e listas inteiras depois de
dois-pontos. O item de Informática do TJ-PR tem sessenta palavras e sete leis dentro do próprio
nome. Usar isso como rótulo produziu, no piloto de 23/09/2026, títulos de três linhas e listas
ilegíveis — o dono resumiu como "os nomes dos tópicos tão muito estranhos".

**A regra é conservadora de propósito:** corta onde o edital claramente abre enumeração e, na
dúvida, devolve o literal. Rótulo feio é irritante; rótulo cortado no meio de uma ideia é
errado, e errado com cara de certo é a mina nº 1 deste repositório. O texto completo nunca some
— continua em `topico.nome` e vai para o atributo `title` na tela.
"""

import re

#: Numeração do edital no começo do item: `"4 "`, `"4.1 "`, `"6.1. "`.
_NUMERACAO_INICIAL = re.compile(r"^\d+(?:\.\d+)*\.?\s+")

#: Onde o edital abre enumeração de subtemas. O ponto só corta quando vem seguido de espaço e de
#: **numeração de subitem** (`". 6.1"`) — um ponto seguido de palavra pode ser fim de frase
#: legítimo, e `"13.146/2015"` não tem espaço depois do ponto, então número de lei nunca corta.
_ABERTURA_DE_LISTA = re.compile(r"[:;]|\.\s+(?=\d+(?:\.\d+)*\.?\s)")


def nome_curto(literal: str) -> str:
    """Devolve o rótulo legível do item de edital `literal`.

    Args:
        literal: o texto do item como está em `topico.nome`.

    Returns:
        O rótulo sem a numeração inicial, cortado na primeira abertura de enumeração
        (dois-pontos, ponto e vírgula ou subitem numerado) e sem o ponto final. Devolve o
        literal (só aparado) quando o corte deixaria a string vazia — melhor feio do que vazio.
    """
    texto = literal.strip()
    if not texto:
        return ""

    sem_numeracao = _NUMERACAO_INICIAL.sub("", texto).strip()
    if not sem_numeracao:
        return texto

    corte = _ABERTURA_DE_LISTA.search(sem_numeracao)
    rotulo = (sem_numeracao[: corte.start()] if corte else sem_numeracao).strip()
    rotulo = rotulo.rstrip(".").strip()
    return rotulo or texto

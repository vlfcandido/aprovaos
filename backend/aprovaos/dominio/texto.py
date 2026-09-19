"""Similaridade léxica determinística entre textos — o proxy compartilhado da ADR-0045.

O que é: `tokens` e `similaridade_lexica` (cosseno médio de TF-IDF), puros e sem dependência
externa. Dois lugares medem "este texto fala do mesmo assunto que aquele": o validador de questão
inédita (aderência ao estilo da banca, Ruling 43) e o validador de justificativa (pertinência da
explicação ao item). Os dois usam **este** módulo — é o mesmo proxy, declarado como proxy, e não
duas implementações que podem divergir. Quando ler: antes de comparar dois textos em qualquer
lugar do domínio; se você está prestes a escrever um léxico novo para decidir se dois textos
falam da mesma coisa, é aqui que deve olhar primeiro.
"""

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-zà-úçã-õâ-ûêîô0-9]+", re.IGNORECASE)


def tokens(texto: str) -> list[str]:
    """Tokeniza `texto` em palavras minúsculas, sem pontuação.

    Args:
        texto: qualquer texto em português.

    Returns:
        Os tokens na ordem em que aparecem; lista vazia quando não há nenhum.
    """
    return [token.lower() for token in _TOKEN.findall(texto)]


def similaridade_lexica(texto: str, referencias: list[str]) -> float:
    """Cosseno médio de TF-IDF entre `texto` e cada uma das `referencias` (ADR-0045).

    O corpus para o IDF é `referencias + [texto]`; cada documento vira um vetor TF-IDF
    (frequência do termo no documento × log do inverso da frequência de documentos que o contêm),
    e a similaridade é o cosseno médio entre o vetor de `texto` e o de cada referência.

    É um **proxy declarado**, deliberadamente mais fraco que o embedding que a skill
    `gerador-questao-banca` pede: medir de verdade custaria cota de IA (ou a extensão `vector`,
    que nunca foi ligada) — ver ADR-0045 e P-66. Ele erra para os dois lados e não deve ser
    exibido como se fosse medida; serve para decidir corte, não para virar número na tela.

    Args:
        texto: o texto em julgamento.
        referencias: os textos de comparação (não vazio).

    Returns:
        A média das similaridades de cosseno, em `[0, 1]`; `0.0` quando `texto` ou toda
        referência é vazia de tokens (nunca divide por zero).

    Raises:
        ValueError: `referencias` vazio — não há com o que comparar, e devolver `0.0` aqui
            confundiria "nada parecido" com "nada para comparar".
    """
    if not referencias:
        raise ValueError("referencias não pode ser vazio")

    documentos = [*referencias, texto]
    tokens_por_documento = [tokens(doc) for doc in documentos]

    n_documentos = len(documentos)
    contagem_documentos: Counter[str] = Counter()
    for tokens_do_documento in tokens_por_documento:
        contagem_documentos.update(set(tokens_do_documento))

    def _vetor_tfidf(lista: list[str]) -> dict[str, float]:
        tf = Counter(lista)
        return {
            termo: (frequencia / len(lista))
            * math.log((n_documentos + 1) / (contagem_documentos[termo] + 1) + 1)
            for termo, frequencia in tf.items()
        }

    vetor_texto = _vetor_tfidf(tokens_por_documento[-1])
    if not vetor_texto:
        return 0.0

    similaridades: list[float] = []
    for tokens_referencia in tokens_por_documento[:-1]:
        vetor_referencia = _vetor_tfidf(tokens_referencia)
        if not vetor_referencia:
            similaridades.append(0.0)
            continue
        termos_comuns = set(vetor_texto) & set(vetor_referencia)
        produto_escalar = sum(vetor_texto[t] * vetor_referencia[t] for t in termos_comuns)
        norma_texto = math.sqrt(sum(v * v for v in vetor_texto.values()))
        norma_referencia = math.sqrt(sum(v * v for v in vetor_referencia.values()))
        if norma_texto == 0.0 or norma_referencia == 0.0:
            similaridades.append(0.0)
        else:
            similaridades.append(produto_escalar / (norma_texto * norma_referencia))

    return sum(similaridades) / len(similaridades)

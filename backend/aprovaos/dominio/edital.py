"""Leitura determinística do texto de um edital: conteúdo programático, slugs e fatos por regex.

O que é: funções puras (sem I/O, sem LLM) que transformam o texto extraído do PDF em
`MateriaExtraida`/`TopicoExtraido` (parser do conteúdo programático), nos slugs da premissa E
da V2 e em `FatosEdital` (distribuição, regra de correção, cabeçalho e etapas, cada fato com o
parágrafo de origem). Quando ler: ao ajustar o parser ou uma regex para um edital real que elas
não entenderam, ao mudar a regra de slug ou ao consumir matérias e fatos no DNA por regras.
"""

import re
import unicodedata
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from aprovaos.dominio.erros import ConteudoProgramaticoNaoEncontrado

_MARCADOR_INICIO = re.compile(
    r"^(?:ANEXO\s+[IVXLCD]+\s*[-–—:]?\s*)?"  # cabeçalho do anexo, quando o marcador está nele
    r"(?:DOS?\s+|DAS?\s+)?"  # "DO(S)"/"DA(S)" de "ANEXO II – DOS CONTEÚDOS PROGRAMÁTICOS"
    r"CONTE[ÚU]DOS?\s+PROGRAM[ÁA]TICOS?"
    r"\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_MARCADOR_FIM = re.compile(r"^ANEXO\s", re.MULTILINE)
_MAIUSCULAS = "A-ZÁÀÂÃÉÊÍÓÔÕÚÇ"
_CABECALHO_COM_DOIS_PONTOS = re.compile(rf"^([{_MAIUSCULAS}][{_MAIUSCULAS}\s]{{2,}}?)\s*:\s*(.*)$")
_CABECALHO_SEM_DOIS_PONTOS = re.compile(rf"^([{_MAIUSCULAS}][{_MAIUSCULAS}\s]{{2,}}?)\s+(1\.\s.*)$")
_NUMERO_DO_ITEM = re.compile(r"^\d+\.\s*")
_ANEXO = re.compile(r"ANEXO\s+([IVXLC]+|\d+)\b", re.IGNORECASE)

# Palavras que não entram no prefixo da matéria nem no nome curto do tópico (premissa E).
_PALAVRAS_VAZIAS = frozenset(
    {"de", "da", "do", "das", "dos", "e", "a", "o", "as", "os", "em", "no", "na", "nº", "n"}
)


class TopicoExtraido(BaseModel):
    """Um item numerado do conteúdo programático, como está no edital.

    Attributes:
        numero: número sequencial do item dentro da matéria (1, 2, 3…).
        texto_original: o item inteiro, com o número, sem quebras de linha nem espaços nas
            pontas — vai para `topico_edital.texto_original`.
        slug: identificador estável `materia-nn-nome-curto` (ver `slug_topico`).
    """

    numero: int
    texto_original: str
    slug: str


class MateriaExtraida(BaseModel):
    """Uma matéria do conteúdo programático com seus itens.

    Attributes:
        nome: nome como está no edital (caixa alta), sem o dois-pontos.
        slug: nome inteiro slugificado (`lingua-portuguesa`), chave de `pesos.materia` e de
            `topicos_edital[].materia` no DNA.
        grupo: cabeçalho agrupador acima da matéria (ex.: `CONHECIMENTOS ESPECÍFICOS`) ou
            `None` quando a matéria aparece solta.
        topicos: itens na ordem do edital.
    """

    nome: str
    slug: str
    grupo: str | None
    topicos: list[TopicoExtraido]


class _Bloco:
    """Cabeçalho em caixa alta e o texto acumulado até o próximo cabeçalho (uso interno)."""

    def __init__(self, nome: str, texto: str) -> None:
        self.nome = nome
        self.texto = texto.strip()

    def acrescentar(self, linha: str) -> None:
        """Junta uma linha de continuação ao texto do bloco.

        Linha anterior terminada em hífen seguida de linha iniciada em minúscula é uma palavra
        partida pela quebra de linha (`constitu-` + `inte`): junta sem espaço e sem o hífen.
        Qualquer outro caso junta com um espaço.
        """
        if not self.texto:
            self.texto = linha
        elif self.texto.endswith("-") and linha[:1].islower():
            self.texto = self.texto[:-1] + linha
        else:
            self.texto = f"{self.texto} {linha}"


def sem_acento(texto: str) -> str:
    """Remove os diacríticos (`LÍNGUA` → `LINGUA`) por decomposição NFKD.

    Args:
        texto: qualquer texto Unicode.

    Returns:
        O texto sem marcas combinantes; `º` vira `o` pela compatibilidade NFKD.
    """
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _palavras(texto: str) -> list[str]:
    """Quebra o texto em palavras `[a-z0-9]+` minúsculas e sem acento, na ordem."""
    return [p for p in re.split(r"[^a-z0-9]+", sem_acento(texto).lower()) if p]


def _palavras_significativas(texto: str) -> list[str]:
    """Como `_palavras`, descartando as palavras vazias da premissa E."""
    return [p for p in _palavras(texto) if p not in _PALAVRAS_VAZIAS]


def slug_materia(nome: str) -> str:
    """Slug do nome inteiro da matéria: `LÍNGUA PORTUGUESA` → `lingua-portuguesa`.

    Args:
        nome: nome da matéria (ou do grupo) como está no edital.

    Returns:
        As palavras do nome, sem acento e em minúsculas, unidas por hífen.
    """
    return "-".join(_palavras(nome))


def prefixo_materia(nome: str) -> str:
    """Prefixo do slug de tópico: 3 primeiras letras de cada palavra significativa do nome.

    `DIREITO ADMINISTRATIVO` → `dir-adm`; `LÍNGUA PORTUGUESA` → `lin-por`.

    Args:
        nome: nome da matéria como está no edital.

    Returns:
        O prefixo em minúsculas, sem acento, palavras unidas por hífen.
    """
    return "-".join(p[:3] for p in _palavras_significativas(nome))


def slug_topico(materia: str, numero: int, texto: str) -> str:
    """Slug `materia-nn-nome-curto` de um item do conteúdo programático (premissa E da V2).

    `nome-curto` são as duas primeiras palavras significativas do item, sem o número; se o
    item não tiver nenhuma, usa `item`.

    Args:
        materia: nome da matéria como está no edital.
        numero: número sequencial do item.
        texto: o item inteiro, com ou sem o número na frente.

    Returns:
        Por exemplo `dir-adm-04-licitacoes-contratos`.
    """
    sem_numero = _NUMERO_DO_ITEM.sub("", texto, count=1)
    palavras = _palavras_significativas(sem_numero)[:2] or ["item"]
    return f"{prefixo_materia(materia)}-{numero:02d}-{'-'.join(palavras)}"


def _recortar_conteudo(texto: str) -> str:
    """Devolve o trecho entre o marcador do conteúdo programático e o próximo `ANEXO`."""
    inicio = _MARCADOR_INICIO.search(texto)
    if inicio is None:
        raise ConteudoProgramaticoNaoEncontrado()
    recorte = texto[inicio.end() :]
    fim = _MARCADOR_FIM.search(recorte)
    return recorte if fim is None else recorte[: fim.start()]


def fonte_conteudo_programatico(texto: str) -> str:
    """`fonte` dos tópicos no DNA: o anexo em que o conteúdo programático está.

    Args:
        texto: texto integral do edital.

    Returns:
        `edital Anexo I` quando a linha do marcador cita `ANEXO I`; senão
        `edital (conteúdo programático)`.
    """
    inicio = _MARCADOR_INICIO.search(texto)
    if inicio is None:
        return "edital (conteúdo programático)"
    comeco_da_linha = texto.rfind("\n", 0, inicio.start()) + 1
    fim_da_linha = texto.find("\n", inicio.end())
    linha = texto[comeco_da_linha : fim_da_linha if fim_da_linha != -1 else len(texto)]
    anexo = _ANEXO.search(linha)
    if anexo is None:
        return "edital (conteúdo programático)"
    return f"edital Anexo {anexo.group(1).upper()}"


def _blocos(recorte: str) -> list[_Bloco]:
    """Agrupa as linhas do recorte em blocos: um por cabeçalho em caixa alta."""
    blocos: list[_Bloco] = []
    for indice, bruta in enumerate(recorte.splitlines()):
        linha = bruta.strip()
        if indice == 0:
            # Resto da linha do marcador (`CONTEÚDO PROGRAMÁTICO: LÍNGUA…`, quando houver).
            linha = linha.lstrip(" :—–-")
        if not linha:
            continue
        cabecalho = _CABECALHO_COM_DOIS_PONTOS.match(linha) or _CABECALHO_SEM_DOIS_PONTOS.match(
            linha
        )
        if cabecalho is not None:
            blocos.append(_Bloco(cabecalho.group(1).strip(), cabecalho.group(2)))
        elif blocos:
            blocos[-1].acrescentar(linha)
    return blocos


def _itens_numerados(texto: str) -> list[tuple[int, str]]:
    """Fatia o texto de uma matéria em itens pela numeração sequencial (`1.`, `2.`, `3.`…).

    Procura o número N seguido de ponto e espaço sempre a partir do fim do item anterior, com N
    crescente; por isso `14.133/2021` dentro do item 4 não vira item novo. Cada item vai até o
    começo do seguinte. O item `1.` tem de abrir o próprio bloco (posição 0): se o primeiro
    "1. " só aparece no meio do texto, não é uma lista numerada de topo — é numeração decimal
    hierárquica (`1.1.1.1.`) coincidindo por acaso com o padrão, e a função devolve lista vazia
    em vez de itens que começam no meio do bloco, com o conteúdo anterior descartado.
    """
    itens: list[tuple[int, str]] = []
    numero = 1
    posicao = 0
    inicio_anterior: int | None = None
    while True:
        encontrado = re.compile(rf"\b{numero}\.\s").search(texto, posicao)
        if encontrado is None:
            break
        if numero == 1 and encontrado.start() != 0:
            # O "1." não abre o bloco: não é lista numerada de topo, e sim numeração decimal
            # hierárquica (`1.1.1.1.`) coincidindo por acaso com o padrão dentro de texto sem
            # itens (visto na FCC — CONTABILIDADE TRIBUTÁRIA). Aceitar aqui devolveria itens
            # que começam no meio do bloco, com pedaços de conteúdo anterior perdidos — melhor
            # devolver bloco sem itens (vira `grupo`) do que uma lista fabricada.
            return []
        if inicio_anterior is not None:
            itens.append((numero - 1, texto[inicio_anterior : encontrado.start()].strip()))
        inicio_anterior = encontrado.start()
        posicao = encontrado.end()
        numero += 1
    if inicio_anterior is not None:
        itens.append((numero - 1, texto[inicio_anterior:].strip()))
    return itens


def extrair_conteudo_programatico(texto: str) -> list[MateriaExtraida]:
    """Extrai matérias e itens do conteúdo programático do texto de um edital, sem LLM.

    Algoritmo:
        1. Localiza o marcador — o cabeçalho `(ANEXO N –) (DOS/DAS) CONTEÚDO(S)
           PROGRAMÁTICO(S)` sozinho numa linha (singular ou plural, com ou sem acento, qualquer
           caixa; `ANEXO N` pode ficar em linha separada do resto, como na FCC) — e recorta
           dali até a próxima linha que começa com `ANEXO` ou até o fim do texto. Exigir a
           linha inteira evita casar uma referência cruzada em prosa antes do anexo de verdade
           (ex.: "Os conteúdos programáticos [...] encontram-se no Anexo II deste Edital.").
        2. Percorre as linhas do recorte. Linha que começa em caixa alta seguida de `:`
           (`DIREITO CIVIL: …`) ou seguida do item `1.` (`DIREITO TRIBUTÁRIO 1. …`) abre um
           bloco; qualquer outra linha é continuação do bloco aberto e é unida a ele com um
           espaço (ou sem espaço, quando a linha anterior termina em hífen e a nova começa em
           minúscula — palavra partida pela quebra de linha do PDF). Assim, um item cujo
           número ficou no fim de uma linha e o texto na seguinte volta a ser um só.
        3. Bloco sem item `1.` é um **grupo** (`CONHECIMENTOS ESPECÍFICOS:`) e passa a valer
           como `grupo` das matérias seguintes. Bloco com itens é uma matéria; os itens são
           fatiados pela numeração sequencial (`1.`, depois `2.` a partir do fim do `1.`, e
           assim por diante), o que impede que `14.133/2021` seja lido como item.
        4. Cada item vira `TopicoExtraido` com `slug_topico`; cada matéria, `MateriaExtraida`
           com `slug_materia`.

    Args:
        texto: texto integral do edital (saída de `extrair_texto` ou o `.md` da fixture).

    Returns:
        As matérias na ordem do edital, cada uma com seus itens.

    Raises:
        ConteudoProgramaticoNaoEncontrado: sem o marcador; ou com o marcador encontrado mas
            nenhum cabeçalho de matéria reconhecido (nomes fora de `NOME EM CAIXA ALTA:`); ou
            com matérias reconhecidas mas nenhuma com itens numerados — cada caso com uma
            mensagem própria, para a página de upload apontar o motivo certo.
    """
    blocos = _blocos(_recortar_conteudo(texto))
    materias: list[MateriaExtraida] = []
    grupo: str | None = None
    algum_bloco_tem_itens = False
    for bloco in blocos:
        itens = _itens_numerados(bloco.texto)
        if not itens:
            grupo = bloco.nome
            continue
        algum_bloco_tem_itens = True
        topicos = [
            TopicoExtraido(
                numero=numero, texto_original=item, slug=slug_topico(bloco.nome, numero, item)
            )
            for numero, item in itens
        ]
        materias.append(
            MateriaExtraida(
                nome=bloco.nome, slug=slug_materia(bloco.nome), grupo=grupo, topicos=topicos
            )
        )
    if not materias:
        if not blocos:
            raise ConteudoProgramaticoNaoEncontrado(
                "Encontrei o anexo do conteúdo programático, mas não reconheci nenhuma matéria "
                "nele — o parser espera o nome em CAIXA ALTA seguido de dois-pontos (ex.: "
                "'DIREITO CONSTITUCIONAL: 1. ...'). Peça para o suporte olhar este edital."
            )
        assert not algum_bloco_tem_itens  # "not materias" e blocos não vazios só coexistem aqui.
        raise ConteudoProgramaticoNaoEncontrado(
            "Encontrei o anexo do conteúdo programático e as matérias, mas os itens não estão "
            "numerados (1., 2., 3., ...) — este parser ainda não lê listas sem numeração. Peça "
            "para o suporte olhar este edital."
        )
    return materias


# ---- Parte 2: fatos do edital por regex --------------------------------------------------------

Desconhecido = Literal["desconhecido"]
DESCONHECIDO: Desconhecido = "desconhecido"

_INICIO_PARAGRAFO = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
_DISTRIBUICAO = re.compile(
    r"([A-Za-zÀ-ú ]+?)\s*[—–-]\s*(\d+)\s+quest(?:ões|oes)\s*,?\s*peso\s+(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_MULTIPLA_ESCOLHA = re.compile(r"m[úu]ltipla escolha", re.IGNORECASE)
_CERTO_ERRADO = re.compile(r"\bcerto\b.*\berrado\b", re.IGNORECASE)
# Dígito colado em "alternativas" ou com o número por extenso entre parênteses no meio (a forma
# da AOCP: "5 (cinco) alternativas") — o dígito é a fonte da verdade; o extenso é só validação
# textual, não é capturado.
_ALTERNATIVAS = re.compile(r"(\d+)\s*(?:\([^)]+\)\s*)?alternativas", re.IGNORECASE)
# Só quando não há dígito nenhum (a forma da FCC: "com cinco alternativas cada questão") —
# vocabulário fechado de um a dez; uma palavra fora dele ("algumas", "diversas") não casa, e o
# campo fica `None` — nunca se chuta um número a partir de "algumas".
_ALTERNATIVAS_POR_EXTENSO = re.compile(
    r"\b(um|uma|dois|duas|tr[êe]s|quatro|cinco|seis|sete|oito|nove|dez)\s+alternativas\b",
    re.IGNORECASE,
)
_NUMERO_POR_EXTENSO: dict[str, int] = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
}
# O mecanismo que faz uma prova ser de múltipla escolha, mesmo que o edital nunca diga a frase
# "múltipla escolha" (achado real na AOCP, §11.3: "terá 5 (cinco) alternativas, sendo que cada
# questão terá apenas 1 (uma) alternativa correta"). Exigido no mesmo parágrafo do número de
# alternativas — nunca em parágrafos diferentes, que poderia juntar fatos sem relação.
_MECANISMO_UMA_ALTERNATIVA_CORRETA = re.compile(
    r"apenas\s+1\s*\(?uma\)?\s+alternativa\s+correta", re.IGNORECASE
)
_NAO_ANULA = re.compile(r"sem desconto|não haverá desconto", re.IGNORECASE)
# "anula"/"desconto" sozinhos casam com qualquer cláusula administrativa (anulação de inscrição
# por fraude, de nomeação por declaração falsa — achado real na AOCP §5.10.1 e na FCC §6.5.1,
# nenhuma das duas sobre desconto por questão errada). Regra de correção de verdade liga o ERRO
# NA QUESTÃO ("errada"/"errado") ao desconto/anulação de ponto, a poucas palavras de distância,
# na mesma frase (`[^.]` não cruza ponto final).
_ANULA = re.compile(
    r"errad[ao]\b[^.]{0,40}\b(?:anula|desconta|desconto|subtrai)"
    r"|\b(?:anula|desconta|desconto|subtrai)\b[^.]{0,40}errad[ao]\b",
    re.IGNORECASE,
)
_MINIMO_GLOBAL = re.compile(r"(\d+)\s*%\s*do total(?: de pontos)?", re.IGNORECASE)
# "nota zero" sozinho casa com qualquer critério de correção que zere uma prova — inclusive o
# da Discursiva-Redação, sem relação nenhuma com eliminar por zerar uma disciplina da objetiva
# (achado real na FCC, §10.6: "Será atribuída nota ZERO à Prova Discursiva-Redação que: a)
# fugir à modalidade de texto [...]"). Mesma classe de bug do `_ANULA`: a cláusula tem de falar
# de disciplina/matéria/conhecimentos da prova, não só conter o termo "nota zero".
_NOTA_ZERO = re.compile(
    r"nota\s+zero\b[^.]{0,60}\b(?:disciplinas?|mat[ée]rias?|conhecimentos?)"
    r"|\b(?:disciplinas?|mat[ée]rias?|conhecimentos?)\b[^.]{0,60}nota\s+zero",
    re.IGNORECASE,
)
_CARGO = re.compile(r"Cargo:\s*([^.]+)\.")
# O nome capturado tem de começar em maiúscula — nome próprio de instituição, não qualquer
# substantivo comum antes da primeira vírgula (achado na re-revisão do merge: "executado pela
# empresa contratada, responsável por..." não é banca nenhuma). Por isso sem `re.IGNORECASE`.
_BANCA_EXECUTADO = re.compile(rf"executad[oa] pel[ao]\s+([{_MAIUSCULAS}].+?)(?:\s*\(banca|[.,])")
# Só com dois-pontos — igual à convenção de `Cargo:` — porque "banca organizadora" também
# aparece em cláusulas que não identificam ninguém (ex.: "recurso [...] pela banca organizadora
# resultar anulação..."); sem o rótulo explícito, casar por proximidade ainda seria chute.
_BANCA_ORGANIZADORA = re.compile(r"banca organizadora\s*:\s*(.+?)[.,]", re.IGNORECASE)
_NUMERO_DO_EDITAL = re.compile(r"EDITAL[^\n]*?N[ºo°.]?\s*(\d+/\d{4})")
_DATA_PROVA = re.compile(r"[Dd]ata (?:provável )?da prova[^\d]*(\d{2}/\d{2}/\d{4})")
_DISCURSIVA = re.compile(r"[Pp]rova discursiva[^.]*?peso\s+(\d+)\s+pontos")
_PRIMEIROS = re.compile(r"(\d+)\s+primeiros", re.IGNORECASE)

FONTE_SEM_NUMERACAO = "edital (trecho sem numeração)"
FONTE_NAO_LOCALIZADA = "edital (não localizado)"


class DistribuicaoMateria(BaseModel):
    """Uma linha da distribuição de questões por matéria (ex.: `Língua Portuguesa — 10, peso 1,0`).

    Attributes:
        nome: nome da matéria como está na distribuição (Title Case do edital).
        questoes: número de questões.
        peso_questao: peso de cada questão; vírgula decimal já convertida.
        fonte: parágrafo do edital (`edital §6.2`).
    """

    nome: str
    questoes: int
    peso_questao: float
    fonte: str


class RegraExtraida(BaseModel):
    """Regra de correção da prova objetiva, do que o edital diz literalmente ou do mecanismo.

    Attributes:
        tipo_item: `multipla_escolha` (frase literal, ou "N alternativas ... apenas 1 (uma)
            alternativa correta" no mesmo parágrafo), `certo_errado` ou `desconhecido`.
        alternativas: número de alternativas — em dígito, com ou sem o extenso entre parênteses
            ("5 (cinco) alternativas"), ou só o extenso ("cinco alternativas") — ou `None`.
        anula_por_erro: `True` só se uma cláusula liga o erro NA QUESTÃO ("errada"/"errado") a
            desconto/anulação de ponto na mesma frase; `False` se "sem desconto" (explícito);
            senão `desconhecido` — nunca `False` por suposição de mercado sem o edital dizer.
        minimo_por_materia: `nota zero elimina` só se "nota zero" aparecer perto de
            disciplina/matéria/conhecimentos da prova (nunca por zerar a Discursiva-Redação);
            senão `desconhecido`.
        minimo_global: `N % do total de pontos` ou `desconhecido`.
        fonte: parágrafos casados (`edital §6.1, §6.3`).
    """

    tipo_item: Literal["certo_errado", "multipla_escolha"] | Desconhecido
    alternativas: int | None
    anula_por_erro: bool | Desconhecido
    minimo_por_materia: str
    minimo_global: str
    fonte: str


class CabecalhoExtraido(BaseModel):
    """Identificação do concurso: órgão, cargo, banca, número do edital e data da prova.

    Attributes:
        orgao: primeira linha em caixa alta do texto (ou `desconhecido`).
        cargo: texto após `Cargo:` (ou `desconhecido`).
        banca: quem executa o concurso (ou `desconhecido`).
        edital: número no formato `NN/AAAA` (ou `desconhecido`).
        data_prova: data da prova objetiva ou `None` quando ausente/inválida.
        fonte: parágrafos casados (`edital §1.1, §1.2, §6.5`).
    """

    orgao: str
    cargo: str
    banca: str
    edital: str
    data_prova: date | None
    fonte: str


class Etapa(BaseModel):
    """Uma etapa do concurso (objetiva, discursiva…) com seus pontos e quem a faz.

    Attributes:
        nome: `objetiva` ou `discursiva`.
        pontos: total de pontos da etapa ou `desconhecido`.
        quem_faz: restrição de quem faz a etapa (`60 primeiros`) ou `None`.
        fonte: parágrafo do edital de onde os pontos vieram.
    """

    nome: str
    pontos: float | Desconhecido
    quem_faz: str | None = None
    fonte: str


class FatosEdital(BaseModel):
    """Tudo que o DNA por regras precisa do edital, cada fato com o parágrafo de origem.

    Attributes:
        distribuicao: questões e peso por matéria da prova objetiva (vazia se o edital omite).
        regra: regra de correção.
        cabecalho: órgão, cargo, banca, número do edital e data da prova.
        etapas: `objetiva` sempre (pontos = soma da distribuição) e `discursiva` se houver.
    """

    distribuicao: list[DistribuicaoMateria]
    regra: RegraExtraida
    cabecalho: CabecalhoExtraido
    etapas: list[Etapa]


class _Paragrafo:
    """Parágrafo numerado (`6.2`) ou não, com as linhas do PDF já reunidas (uso interno)."""

    def __init__(self, numero: str | None, texto: str) -> None:
        self.numero = numero
        self.bloco = _Bloco(numero or "", texto)

    @property
    def texto(self) -> str:
        """Texto do parágrafo com as linhas unidas."""
        return self.bloco.texto


def _paragrafos(texto: str) -> list[_Paragrafo]:
    """Reúne as linhas do texto em parágrafos.

    Linha que começa com numeração (`1.1 `, `6.2 `, `6. `) abre um parágrafo numerado; linha em
    branco fecha o parágrafo aberto; qualquer outra linha continua o parágrafo aberto (ou abre
    um sem número). É o que devolve o `6.2` inteiro quando o PDF o quebrou em três linhas.
    """
    paragrafos: list[_Paragrafo] = []
    aberto: _Paragrafo | None = None
    for bruta in texto.splitlines():
        linha = bruta.strip()
        if not linha:
            aberto = None
            continue
        numerada = _INICIO_PARAGRAFO.match(linha)
        if numerada is not None:
            aberto = _Paragrafo(numerada.group(1), numerada.group(2))
            paragrafos.append(aberto)
        elif aberto is not None:
            aberto.bloco.acrescentar(linha)
        else:
            aberto = _Paragrafo(None, linha)
            paragrafos.append(aberto)
    return paragrafos


def _fonte(paragrafos: list[_Paragrafo], casados: list[_Paragrafo]) -> str:
    """Monta `edital §a, §b` com os parágrafos casados, na ordem do documento, sem repetir."""
    if not casados:
        return FONTE_NAO_LOCALIZADA
    numeros: list[str] = []
    for paragrafo in paragrafos:
        if paragrafo in casados and paragrafo.numero and paragrafo.numero not in numeros:
            numeros.append(paragrafo.numero)
    if not numeros:
        return FONTE_SEM_NUMERACAO
    return "edital §" + ", §".join(numeros)


def _primeiro(
    paragrafos: list[_Paragrafo], regex: re.Pattern[str]
) -> tuple[re.Match[str], _Paragrafo] | None:
    """Primeiro parágrafo (na ordem do documento) em que a regex casa, com o `Match`."""
    for paragrafo in paragrafos:
        encontrado = regex.search(paragrafo.texto)
        if encontrado is not None:
            return encontrado, paragrafo
    return None


def _extrair_distribuicao(paragrafos: list[_Paragrafo]) -> list[DistribuicaoMateria]:
    """Linhas `Matéria — N questões, peso P` do parágrafo da distribuição."""
    candidatos = [p for p in paragrafos if _DISTRIBUICAO.search(p.texto)]
    if not candidatos:
        return []
    escolhido = next((p for p in candidatos if "distribui" in p.texto.lower()), candidatos[0])
    fonte = _fonte(paragrafos, [escolhido])
    return [
        DistribuicaoMateria(
            nome=m.group(1).strip(),
            questoes=int(m.group(2)),
            peso_questao=float(m.group(3).replace(",", ".")),
            fonte=fonte,
        )
        for m in _DISTRIBUICAO.finditer(escolhido.texto)
    ]


def _extrair_alternativas(
    paragrafos: list[_Paragrafo],
) -> tuple[int, _Paragrafo] | None:
    """Número de alternativas: dígito, com ou sem extenso, ou o extenso sozinho.

    Tenta primeiro o dígito (com o extenso opcional entre parênteses); na falta de dígito, o
    numeral por extenso sozinho (um a dez) — nessa ordem de preferência.

    Args:
        paragrafos: parágrafos do edital, na ordem do documento.

    Returns:
        `(número, parágrafo onde casou)` ou `None` se nenhum padrão casar com segurança.
    """
    if (digito := _primeiro(paragrafos, _ALTERNATIVAS)) is not None:
        return int(digito[0].group(1)), digito[1]
    if (extenso := _primeiro(paragrafos, _ALTERNATIVAS_POR_EXTENSO)) is not None:
        numero = _NUMERO_POR_EXTENSO[sem_acento(extenso[0].group(1)).casefold()]
        return numero, extenso[1]
    return None


def _extrair_regra(paragrafos: list[_Paragrafo]) -> RegraExtraida:
    """Tipo de item, alternativas, anulação e mínimos, cada um do primeiro parágrafo que casa."""
    casados: list[_Paragrafo] = []
    tipo_item: Literal["certo_errado", "multipla_escolha"] | Desconhecido = DESCONHECIDO
    if (multipla := _primeiro(paragrafos, _MULTIPLA_ESCOLHA)) is not None:
        tipo_item = "multipla_escolha"
        casados.append(multipla[1])
    elif (certo_errado := _primeiro(paragrafos, _CERTO_ERRADO)) is not None:
        tipo_item = "certo_errado"
        casados.append(certo_errado[1])

    alternativas: int | None = None
    alternativas_achadas = _extrair_alternativas(paragrafos)
    if alternativas_achadas is not None:
        alternativas, paragrafo_alternativas = alternativas_achadas
        casados.append(paragrafo_alternativas)
        # Sem a frase literal "múltipla escolha" nem "certo"..."errado", o mecanismo "N
        # alternativas ... apenas 1 (uma) alternativa correta" no MESMO parágrafo já é múltipla
        # escolha (achado real na AOCP, §11.3) — juntar parágrafos diferentes seria chute.
        if tipo_item == DESCONHECIDO and _MECANISMO_UMA_ALTERNATIVA_CORRETA.search(
            paragrafo_alternativas.texto
        ):
            tipo_item = "multipla_escolha"

    anula_por_erro: bool | Desconhecido = DESCONHECIDO
    for paragrafo in paragrafos:
        # "sem desconto" contém "desconto": a negação tem de ser testada antes, no mesmo parágrafo.
        if _NAO_ANULA.search(paragrafo.texto):
            anula_por_erro = False
        elif _ANULA.search(paragrafo.texto):
            anula_por_erro = True
        else:
            continue
        casados.append(paragrafo)
        break

    minimo_global: str = DESCONHECIDO
    if (minimo := _primeiro(paragrafos, _MINIMO_GLOBAL)) is not None:
        minimo_global = f"{minimo[0].group(1)} % do total de pontos"
        casados.append(minimo[1])

    minimo_por_materia: str = DESCONHECIDO
    if (zero := _primeiro(paragrafos, _NOTA_ZERO)) is not None:
        minimo_por_materia = "nota zero elimina"
        casados.append(zero[1])

    return RegraExtraida(
        tipo_item=tipo_item,
        alternativas=alternativas,
        anula_por_erro=anula_por_erro,
        minimo_por_materia=minimo_por_materia,
        minimo_global=minimo_global,
        fonte=_fonte(paragrafos, casados),
    )


def _orgao(texto: str) -> str:
    """Primeira linha não vazia em caixa alta que não começa por `EDITAL`, `#` nem `>`."""
    for bruta in texto.splitlines():
        linha = bruta.strip()
        if not linha or linha.startswith(("EDITAL", "#", ">")):
            continue
        if linha == linha.upper() and any(c.isalpha() for c in linha):
            return linha
    return DESCONHECIDO


def _extrair_cabecalho(texto: str, paragrafos: list[_Paragrafo]) -> CabecalhoExtraido:
    """Órgão (linha), número do edital (texto inteiro), cargo, banca e data (parágrafos)."""
    casados: list[_Paragrafo] = []

    banca: str = DESCONHECIDO
    achado = _primeiro(paragrafos, _BANCA_EXECUTADO) or _primeiro(paragrafos, _BANCA_ORGANIZADORA)
    if achado is not None:
        banca = achado[0].group(1).strip()
        casados.append(achado[1])

    cargo: str = DESCONHECIDO
    if (cargo_achado := _primeiro(paragrafos, _CARGO)) is not None:
        cargo = cargo_achado[0].group(1).strip()
        casados.append(cargo_achado[1])

    data_prova: date | None = None
    if (data_achada := _primeiro(paragrafos, _DATA_PROVA)) is not None:
        try:
            data_prova = datetime.strptime(data_achada[0].group(1), "%d/%m/%Y").date()
        except ValueError:
            data_prova = None
        else:
            casados.append(data_achada[1])

    numero_edital = _NUMERO_DO_EDITAL.search(texto)
    return CabecalhoExtraido(
        orgao=_orgao(texto),
        cargo=cargo,
        banca=banca,
        edital=numero_edital.group(1) if numero_edital else DESCONHECIDO,
        data_prova=data_prova,
        fonte=_fonte(paragrafos, casados),
    )


def _extrair_etapas(
    paragrafos: list[_Paragrafo], distribuicao: list[DistribuicaoMateria]
) -> list[Etapa]:
    """`objetiva` (soma de questões × peso) e `discursiva` (peso em pontos + quem faz)."""
    if distribuicao:
        objetiva = Etapa(
            nome="objetiva",
            pontos=sum(d.questoes * d.peso_questao for d in distribuicao),
            fonte=distribuicao[0].fonte,
        )
    else:
        objetiva = Etapa(
            nome="objetiva", pontos=DESCONHECIDO, fonte="edital omisso — sem distribuição"
        )
    etapas = [objetiva]
    if (discursiva := _primeiro(paragrafos, _DISCURSIVA)) is not None:
        primeiros = _PRIMEIROS.search(discursiva[1].texto)
        etapas.append(
            Etapa(
                nome="discursiva",
                pontos=float(discursiva[0].group(1)),
                quem_faz=f"{primeiros.group(1)} primeiros" if primeiros else None,
                fonte=_fonte(paragrafos, [discursiva[1]]),
            )
        )
    return etapas


def extrair_fatos(texto: str) -> FatosEdital:
    """Extrai por regex os fatos do edital que o DNA por regras usa, cada um com o parágrafo.

    O texto é reunido em parágrafos (`_paragrafos`) para que as linhas quebradas pelo PDF
    voltem a ser uma só; cada fato é procurado no primeiro parágrafo em que a regex casa e a
    `fonte` de cada grupo de fatos é `edital §a, §b` com os números desses parágrafos. O que
    nenhuma regex encontra fica `desconhecido` (ou `None`/lista vazia, conforme o campo) —
    nunca é estimado.

    Args:
        texto: texto integral do edital.

    Returns:
        `FatosEdital` com distribuição, regra de correção, cabeçalho e etapas.
    """
    paragrafos = _paragrafos(texto)
    distribuicao = _extrair_distribuicao(paragrafos)
    return FatosEdital(
        distribuicao=distribuicao,
        regra=_extrair_regra(paragrafos),
        cabecalho=_extrair_cabecalho(texto, paragrafos),
        etapas=_extrair_etapas(paragrafos, distribuicao),
    )

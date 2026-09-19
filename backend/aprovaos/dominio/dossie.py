"""Construção determinística do `DossieTopico` (fundação jurídica, passo 3).

O que é: `montar_dossie(topico_slug, pedidos, normas_html, normas_url, hoje)`, função pura que
monta o conteúdo de um dossiê (fontes com trecho literal e URL, log de buscas, lacunas
declaradas) para um conjunto de dispositivos **pedidos** de uma ou mais normas, usando só
`dominio.legislacao.extrair_artigo`/`localizar_trecho` sobre HTML já decodificado. **Nenhuma**
chamada de rede, banco ou LLM acontece aqui — é a mesma disciplina de `motor.ancorar`, aplicada
ao sentido inverso: em vez de "a questão cita este artigo, resolvo o trecho", aqui é "o tópico
precisa deste artigo, o extrator confirma (ou declara lacuna)".

Este módulo é a prova de conceito de que o dossiê da skill `deep-research-topico`
(`.claude/skills/deep-research-topico/SKILL.md`) pode ser alimentado por dispositivo real —
nunca por "o assunto costuma envolver X". Um pedido que `dominio.legislacao.extrair_artigo`/
`localizar_trecho` não resolve (`DispositivoNaoEncontrado`/`EstruturaNaoTratada`) vira
`LacunaDossie` com o **trecho literal da exceção**, nunca é preenchido de memória. O `conteudo`
gerado aqui é um esqueleto mecânico (concatenação de trechos citados, sem prosa de ligação
gerada por IA) — a rodada é 100 % determinística; a prosa de aula de verdade é outro passo,
fora do escopo desta fundação.

Quando ler: antes de montar o dossiê de um tópico novo; ao investigar por que um dispositivo
pedido virou lacuna em vez de fonte.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from aprovaos.dominio.citacao import citacao_canonica
from aprovaos.dominio.erros import DispositivoNaoEncontrado, EstruturaNaoTratada
from aprovaos.dominio.legislacao import extrair_artigo, localizar_trecho


class PedidoDispositivo(BaseModel):
    """Um dispositivo pedido para o dossiê: norma + artigo, com inciso/parágrafo opcionais.

    Attributes:
        norma: id estável da norma (o mesmo de `motor.fontes.planalto.CATALOGO`).
        artigo: número do artigo, sem ordinal (ex.: `"1"`, `"37"`).
        inciso: identificador do inciso (algarismo romano), quando o pedido desce a esse nível.
        paragrafo: número do parágrafo, sem ordinal, quando o pedido desce a esse nível.
    """

    norma: str
    artigo: str
    inciso: str | None = None
    paragrafo: str | None = None


class FonteDossie(BaseModel):
    """Uma fonte do dossiê (`## Fontes` da skill `deep-research-topico`).

    Já ligada ao dispositivo estrutural que a originou — é o que `dados.repositorio_dossie` usa
    para gravar `dispositivo_legal`/`citacao` sem reprocessar HTML.

    Attributes:
        id: identificador `F-n`, na ordem em que entrou no dossiê.
        norma / artigo / inciso / paragrafo: a referência estrutural do pedido que gerou esta
            fonte.
        citacao_canonica: a mesma string estável que `motor.ancorar` grava em
            `dispositivo_legal.citacao_canonica` — o elo entre o dossiê e o catálogo.
        url: URL de onde o texto foi coletado (Planalto).
        trecho: texto literal vigente do trecho (nunca parafraseado).
        tipo: sempre `"norma"` nesta rodada (súmula/julgado ficam para a próxima).
        vigente: sempre `True` — `extrair_artigo` já descarta o texto revogado.
        redacao_de: procedência da redação, quando o Planalto a informou.
    """

    id: str
    norma: str
    artigo: str
    inciso: str | None
    paragrafo: str | None
    citacao_canonica: str
    url: str
    trecho: str
    tipo: Literal["norma"] = "norma"
    vigente: bool = True
    redacao_de: str | None = None


class LacunaDossie(BaseModel):
    """Um dispositivo pedido que não virou fonte — declarado, nunca inventado.

    Attributes:
        dispositivo: rótulo do dispositivo pedido (`"<norma> art. <nº>"`, com `§`/inciso quando
            houver).
        motivo: a razão real, com o trecho literal do erro quando ele existe (nunca "não
            encontrado" genérico quando há mais informação disponível).
    """

    dispositivo: str
    motivo: str


class EntradaLogBusca(BaseModel):
    """Uma linha do `log_buscas`: o que foi tentado, com que ferramenta, e o resultado.

    Attributes:
        n: posição da tentativa, na ordem dos `pedidos` de `montar_dossie`.
        consulta: o que foi pedido (dispositivo).
        ferramenta: sempre `"extrair_artigo (offline)"` nesta rodada — não há busca de rede.
        resultado: `"aberta: ..."` quando resolveu, `"falhou: ..."` quando virou lacuna.
        data: a data em que o dossiê foi montado (parâmetro `hoje` de `montar_dossie`).
    """

    n: int
    consulta: str
    ferramenta: str
    resultado: str
    data: date


class ConteudoDossie(BaseModel):
    """O que `montar_dossie` produz — pronto para `dados.repositorio_dossie.salvar_dossie`.

    Attributes:
        conteudo: markdown mecanicamente montado a partir das fontes resolvidas (sem prosa de
            IA nesta rodada determinística).
        fontes: os dispositivos que o extrator conseguiu ler, na ordem em que foram pedidos.
        lacunas: os dispositivos pedidos que o extrator não conseguiu ler, com o motivo literal.
        log_buscas: uma entrada por pedido, resolvido ou não.
        bibliografia: doutrina consultada; vazia nesta rodada (nenhuma foi buscada).
    """

    conteudo: str
    fontes: list[FonteDossie]
    lacunas: list[LacunaDossie]
    log_buscas: list[EntradaLogBusca]
    bibliografia: list[str] = Field(default_factory=list)


def _rotulo_dispositivo(pedido: PedidoDispositivo) -> str:
    """Rótulo legível de um pedido, para `LacunaDossie.dispositivo`/`EntradaLogBusca.consulta`."""
    return citacao_canonica(
        pedido.norma, pedido.artigo, inciso=pedido.inciso, paragrafo=pedido.paragrafo
    )


def montar_dossie(
    *,
    topico_slug: str,
    pedidos: list[PedidoDispositivo],
    normas_html: dict[str, str],
    normas_url: dict[str, str],
    hoje: date,
) -> ConteudoDossie:
    """Monta o conteúdo de um dossiê para os dispositivos `pedidos`, offline e sem LLM.

    Args:
        topico_slug: o tópico a que este dossiê pertence (só para a frase de abertura do
            `conteudo`; a persistência de verdade do vínculo é `dossie_topico.topico_id`).
        pedidos: os dispositivos que o tópico precisa, na ordem em que devem entrar no dossiê.
        normas_html: HTML já decodificado (`motor.fontes.planalto.decodificar_html`) de cada
            norma citada em `pedidos`, por id de norma; norma ausente daqui vira lacuna para
            todo pedido dela.
        normas_url: URL de origem de cada norma (para `FonteDossie.url`), por id de norma.
        hoje: a data a gravar em cada `EntradaLogBusca.data` (injetada, não `date.today()` —
            determinismo do teste).

    Returns:
        O `ConteudoDossie` pronto para persistir — nunca levanta: todo pedido vira fonte ou
        lacuna.
    """
    fontes: list[FonteDossie] = []
    lacunas: list[LacunaDossie] = []
    log_buscas: list[EntradaLogBusca] = []

    for n, pedido in enumerate(pedidos, start=1):
        rotulo = _rotulo_dispositivo(pedido)
        html = normas_html.get(pedido.norma)
        if html is None:
            motivo = f"norma {pedido.norma!r} sem HTML carregado nesta rodada"
            lacunas.append(LacunaDossie(dispositivo=rotulo, motivo=motivo))
            log_buscas.append(
                EntradaLogBusca(
                    n=n,
                    consulta=rotulo,
                    ferramenta="extrair_artigo (offline)",
                    resultado=f"falhou: {motivo}",
                    data=hoje,
                )
            )
            continue

        try:
            artigo_extraido = extrair_artigo(html, pedido.artigo)
            trecho = localizar_trecho(
                artigo_extraido, inciso=pedido.inciso, paragrafo=pedido.paragrafo
            )
        except (DispositivoNaoEncontrado, EstruturaNaoTratada) as erro:
            motivo = f"{type(erro).__name__}: {erro}"
            lacunas.append(LacunaDossie(dispositivo=rotulo, motivo=motivo))
            log_buscas.append(
                EntradaLogBusca(
                    n=n,
                    consulta=rotulo,
                    ferramenta="extrair_artigo (offline)",
                    resultado=f"falhou: {motivo}",
                    data=hoje,
                )
            )
            continue

        fonte = FonteDossie(
            id=f"F{len(fontes) + 1}",
            norma=pedido.norma,
            artigo=pedido.artigo,
            inciso=pedido.inciso,
            paragrafo=pedido.paragrafo,
            citacao_canonica=rotulo,
            url=normas_url[pedido.norma],
            trecho=trecho.texto,
            vigente=True,
            redacao_de=trecho.redacao_de,
        )
        fontes.append(fonte)
        log_buscas.append(
            EntradaLogBusca(
                n=n,
                consulta=rotulo,
                ferramenta="extrair_artigo (offline)",
                resultado="aberta: trecho encontrado",
                data=hoje,
            )
        )

    conteudo = _montar_conteudo(topico_slug, fontes, lacunas)
    return ConteudoDossie(conteudo=conteudo, fontes=fontes, lacunas=lacunas, log_buscas=log_buscas)


def _montar_conteudo(
    topico_slug: str, fontes: list[FonteDossie], lacunas: list[LacunaDossie]
) -> str:
    r"""Monta o markdown do dossiê por concatenação mecânica das fontes — sem geração por IA.

    Cada fonte vira um parágrafo `"<citação>: \"<trecho>\" [F-n]."`; lacunas viram uma frase
    final que as nomeia (nunca preenche o texto que falta).
    """
    linhas = [
        f"Dossiê de {topico_slug} — dispositivos confirmados pelo extrator "
        f"(`dominio.legislacao.extrair_artigo`), sem geração por IA nesta rodada."
    ]
    for fonte in fontes:
        linhas.append(f'{fonte.citacao_canonica}: "{fonte.trecho}" [{fonte.id}]')
    if lacunas:
        nomes = "; ".join(f"{lacuna.dispositivo} ({lacuna.motivo})" for lacuna in lacunas)
        linhas.append(f"Lacunas declaradas (estrutura não tratada nesta rodada): {nomes}")
    return "\n\n".join(linhas)

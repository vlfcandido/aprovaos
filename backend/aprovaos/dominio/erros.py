"""Exceções de domínio (regras de negócio, independentes de HTTP e de banco).

O que é: `ErroDominio` e as subclasses de conta (`EmailJaCadastrado`, `CredenciaisInvalidas`), de
edital (`ArquivoInvalido`, `PdfSemTexto`, `ConteudoProgramaticoNaoEncontrado`), de prova
(`SegmentacaoAmbigua`) e de legislação (`DispositivoNaoEncontrado`, `EstruturaNaoTratada`).
Quando ler: ao tratar falhas esperadas numa rota ou ao criar regra de domínio nova; `str(erro)` é
o texto pt-BR mostrado ao aluno.
"""


class ErroDominio(Exception):
    """Raiz de todas as falhas esperadas do domínio; a rota decide como mostrar."""


class EmailJaCadastrado(ErroDominio):
    """Já existe conta ativa com este e-mail (cadastro)."""


class CredenciaisInvalidas(ErroDominio):
    """E-mail inexistente, senha errada ou conta excluída — sem distinguir qual (login)."""


class ConteudoProgramaticoNaoEncontrado(ErroDominio):
    """O texto do edital não tem o marcador "CONTEÚDO PROGRAMÁTICO" nem matéria com itens.

    A mensagem padrão é a que a página de upload mostra à aluna (premissa N da V2).
    """

    MENSAGEM_PADRAO = (
        "Não encontrei o conteúdo programático neste PDF. Confira se o edital traz o anexo "
        "com as matérias e os itens numerados (1., 2., ...) e envie o arquivo completo."
    )

    def __init__(self, mensagem: str | None = None) -> None:
        """Cria a exceção com a mensagem padrão em pt-BR, salvo se outra for dada."""
        super().__init__(mensagem or self.MENSAGEM_PADRAO)


class ArquivoInvalido(ErroDominio):
    """O upload não é um PDF aceitável (tipo, tamanho ou bytes corrompidos); mensagem em pt-BR."""


class PdfSemTexto(ErroDominio):
    """O PDF abriu, mas não tem texto extraível (provável imagem digitalizada; OCR é ADR-0023)."""


class SegmentacaoAmbigua(ErroDominio):
    """Um bloco do caderno tem mais fronteiras de comando candidatas do que o padrão conhecido.

    A segmentação (`dominio/prova.py`) reconhece até duas fronteiras num bloco de item (fim do
    enunciado; fim de uma narrativa de apoio implícita) e até uma num bloco de texto de apoio
    explícito. Uma fronteira a mais é estrutura que a regra não cobre — a função para em vez de
    adivinhar qual delas é a certa; o documento fica para revisão manual.
    """


class GabaritoNaoReconhecido(ErroDominio):
    """O texto não tem forma de gabarito Cebraspe C/E reconhecível (grade de itens numerados).

    Levantada por `dominio/gabarito.ler_gabarito_cebraspe` em vez de devolver um mapa vazio —
    mapa vazio esconderia falha de leitura pelo mesmo motivo que `FonteIndisponivel` existe para
    o coletor: "sem entradas" não pode significar "não consegui ler". Cobre tanto um PDF
    qualquer quanto um gabarito de banca em formato diferente (ex.: múltipla escolha A–E).
    """


class DispositivoNaoEncontrado(ErroDominio):
    """O artigo pedido não apareceu no HTML do Planalto (`dominio/legislacao.extrair_artigo`).

    Número inexistente na norma, HTML vazio ou de outra norma.
    """


class TopicoNaoEncontrado(ErroDominio):
    """O tópico pedido não existe no vocabulário canônico (`dados.modelos.Topico`).

    Levantada por comandos que montam conteúdo para um tópico específico (ex.:
    `motor.dossie.construir_dossie_improbidade`) — o comando nunca cria o tópico sozinho; isso é
    responsabilidade do parser de edital/classificador.
    """


class EstruturaNaoTratada(ErroDominio):
    """O HTML do Planalto tem uma forma que `dominio/legislacao.extrair_artigo` não sabe tratar.

    Levantada em vez de adivinhar — por exemplo, uma alínea (`a)`, `b)`...) aparecendo antes de
    qualquer inciso ou parágrafo a que ela possa pertencer. Melhor parar e mostrar o trecho cru
    do que gerar uma hierarquia inventada (o mesmo princípio de `SegmentacaoAmbigua`).
    """


class SemConcursoPrincipal(ErroDominio):
    """Não há rotina (`perfil_estudo`) ou concurso principal/edital para planejar (fatia 8).

    Levantada por `dados.repositorio_plano` quando o job noturno ou o check-in tentam montar um
    plano sem esses dois pré-requisitos — nunca inventa um plano vazio "de qualquer jeito"; a
    rota mostra a mensagem e o link para `/rotina`, o job noturno registra a falha no relatório e
    segue para o próximo usuário (CA explícito do PRD F3.1).
    """


class SumulaNaoEncontrada(ErroDominio):
    """A súmula pedida não resolveu (`dominio/sumula.py`).

    Número ausente do índice/PDF, página de tribunal errada, ou verbete marcado como
    cancelado/superado no índice do STF — nunca devolvida como se fosse vigente. Cobre STF
    (índice + página) e STJ (PDF único de verbetes).
    """

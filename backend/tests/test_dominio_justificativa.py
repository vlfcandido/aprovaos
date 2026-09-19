# O que é: testes do validador mecânico da justificativa (fundação jurídica, passo 5) — cada
# motivo de reprovação isolado (dispositivo fora da lista, trecho que não existe literalmente,
# afirmação sem citação) e o caminho aprovado, para certo/errado e para múltipla escolha.
# Quando ler: ao mudar `dominio.justificativa` ou ao investigar por que uma justificativa boa
# foi reprovada.
from aprovaos.dominio.justificativa import (
    Afirmacao,
    AfirmacaoExibicao,
    DispositivoParaJustificar,
    JustificativaCertoErrado,
    JustificativaMultiplaEscolha,
    JustificativaPorAlternativa,
    montar_texto,
    separar_afirmacoes,
    verificar_justificativa_certo_errado,
    verificar_justificativa_multipla_escolha,
)

DISPOSITIVO = DispositivoParaJustificar(
    citacao_canonica="Lei 8.429/1992 art. 1º",
    texto=(
        "Art. 1º Os atos de improbidade administrativa praticados por qualquer agente público, "
        "servidor ou não, contra a administração direta, indireta ou fundacional [...] serão "
        "punidos na forma desta lei."
    ),
)

OUTRO_DISPOSITIVO = DispositivoParaJustificar(
    citacao_canonica="Lei 8.429/1992 art. 2º",
    texto="Art. 2º Reputa-se agente público [...] todo aquele que exerce [...] mandato, cargo.",
)


def _afirmacao(
    *, dispositivo: str = DISPOSITIVO.citacao_canonica, trecho: str | None = None
) -> Afirmacao:
    return Afirmacao(
        texto="frase de exemplo apoiada na fonte",
        dispositivo=dispositivo,
        trecho_que_decide=trecho or "serão punidos na forma desta lei",
    )


def test_aprova_citacao_do_modelo_com_ordinal_que_o_gravado_nao_tem() -> None:
    """Caso real: o modelo citou "art. 1º"; o `dispositivo_legal` estava gravado como "art. 1" —
    mesmo dispositivo, grafia diferente; o validador não pode recusar por isso."""
    dispositivo_gravado = DispositivoParaJustificar(
        citacao_canonica="Lei 8.429/1992 art. 1", texto=DISPOSITIVO.texto
    )
    afirmacao_do_modelo = _afirmacao(dispositivo="Lei 8.429/1992 art. 1º")

    justificativa = JustificativaCertoErrado(
        afirmacoes_certo=[afirmacao_do_modelo], afirmacoes_errado=[_afirmacao()]
    )
    veredito = verificar_justificativa_certo_errado(justificativa, [dispositivo_gravado])
    assert veredito.aprovado is True
    assert veredito.motivos == []


def test_afirmacao_aprovada_quando_dispositivo_e_trecho_existem() -> None:
    justificativa = JustificativaCertoErrado(
        afirmacoes_certo=[_afirmacao()], afirmacoes_errado=[_afirmacao()]
    )
    veredito = verificar_justificativa_certo_errado(justificativa, [DISPOSITIVO])
    assert veredito.aprovado is True
    assert veredito.motivos == []


def test_reprova_dispositivo_fora_da_lista_ligada() -> None:
    justificativa = JustificativaCertoErrado(
        afirmacoes_certo=[_afirmacao(dispositivo="Lei 8.429/1992 art. 99")],
        afirmacoes_errado=[_afirmacao()],
    )
    veredito = verificar_justificativa_certo_errado(justificativa, [DISPOSITIVO])
    assert veredito.aprovado is False
    assert any("não está entre os ligados à questão" in motivo for motivo in veredito.motivos)


def test_reprova_trecho_que_nao_existe_literalmente_no_dispositivo() -> None:
    justificativa = JustificativaCertoErrado(
        afirmacoes_certo=[_afirmacao(trecho="frase que a lei nunca disse")],
        afirmacoes_errado=[_afirmacao()],
    )
    veredito = verificar_justificativa_certo_errado(justificativa, [DISPOSITIVO])
    assert veredito.aprovado is False
    assert any("não existe literalmente" in motivo for motivo in veredito.motivos)


def test_reprova_afirmacao_sem_citacao() -> None:
    afirmacao_sem_trecho = Afirmacao(
        texto="frase sem apoio", dispositivo=DISPOSITIVO.citacao_canonica, trecho_que_decide=""
    )
    justificativa = JustificativaCertoErrado(
        afirmacoes_certo=[afirmacao_sem_trecho], afirmacoes_errado=[_afirmacao()]
    )
    veredito = verificar_justificativa_certo_errado(justificativa, [DISPOSITIVO])
    assert veredito.aprovado is False
    assert any("trecho citado vazio" in motivo for motivo in veredito.motivos)


def test_reprova_quando_falta_justificativa_certo_ou_errado() -> None:
    so_errado = JustificativaCertoErrado(afirmacoes_certo=[], afirmacoes_errado=[_afirmacao()])
    veredito = verificar_justificativa_certo_errado(so_errado, [DISPOSITIVO])
    assert veredito.aprovado is False
    assert any("faltou justificativa_certo" in motivo for motivo in veredito.motivos)

    so_certo = JustificativaCertoErrado(afirmacoes_certo=[_afirmacao()], afirmacoes_errado=[])
    veredito_2 = verificar_justificativa_certo_errado(so_certo, [DISPOSITIVO])
    assert veredito_2.aprovado is False
    assert any("faltou justificativa_errado" in motivo for motivo in veredito_2.motivos)


def test_multipla_escolha_aprovada_com_as_cinco_letras() -> None:
    justificativa = JustificativaMultiplaEscolha(
        alternativas=[
            JustificativaPorAlternativa(letra=letra, afirmacoes=[_afirmacao()]) for letra in "ABCDE"
        ]
    )
    veredito = verificar_justificativa_multipla_escolha(
        justificativa, [DISPOSITIVO], letras_esperadas=list("ABCDE")
    )
    assert veredito.aprovado is True


def test_multipla_escolha_reprova_letra_faltando() -> None:
    justificativa = JustificativaMultiplaEscolha(
        alternativas=[
            JustificativaPorAlternativa(letra=letra, afirmacoes=[_afirmacao()]) for letra in "ABCD"
        ]
    )
    veredito = verificar_justificativa_multipla_escolha(
        justificativa, [DISPOSITIVO], letras_esperadas=list("ABCDE")
    )
    assert veredito.aprovado is False
    assert any("faltou justificativa da alternativa E" in motivo for motivo in veredito.motivos)


def test_multipla_escolha_reprova_dispositivo_nao_ligado_em_uma_alternativa() -> None:
    alternativas = [
        JustificativaPorAlternativa(letra=letra, afirmacoes=[_afirmacao()]) for letra in "ABCDE"
    ]
    alternativas[2] = JustificativaPorAlternativa(
        letra="C", afirmacoes=[_afirmacao(dispositivo=OUTRO_DISPOSITIVO.citacao_canonica)]
    )
    justificativa = JustificativaMultiplaEscolha(alternativas=alternativas)
    veredito = verificar_justificativa_multipla_escolha(
        justificativa, [DISPOSITIVO], letras_esperadas=list("ABCDE")
    )
    assert veredito.aprovado is False
    assert any("alt C" in motivo for motivo in veredito.motivos)


def test_separar_afirmacoes_de_texto_vazio_ou_none_e_lista_vazia() -> None:
    """Sem justificativa (a maioria das questões hoje), a tela não recebe nada para mostrar."""
    assert separar_afirmacoes(None) == []
    assert separar_afirmacoes("") == []


def test_separar_afirmacoes_desfaz_montar_texto() -> None:
    """`separar_afirmacoes` é o inverso de `montar_texto`: cada frase volta com seu dispositivo."""
    texto = montar_texto(
        [
            Afirmacao(
                texto="O TCU aprecia mediante parecer prévio",
                dispositivo="CF/88 art. 71 I",
                trecho_que_decide="apreciar as contas",
            ),
            Afirmacao(
                texto="Quem julga é o Congresso",
                dispositivo="CF/88 art. 49 IX",
                trecho_que_decide="julgar anualmente",
            ),
        ]
    )
    assert separar_afirmacoes(texto) == [
        AfirmacaoExibicao(
            texto="O TCU aprecia mediante parecer prévio", dispositivo="CF/88 art. 71 I"
        ),
        AfirmacaoExibicao(texto="Quem julga é o Congresso", dispositivo="CF/88 art. 49 IX"),
    ]


def test_separar_afirmacoes_texto_sem_colchete_reconhecivel_nao_quebra() -> None:
    """Texto fora do formato de `montar_texto` (não deveria acontecer) não derruba a tela."""
    assert separar_afirmacoes("um texto qualquer, sem citação nenhuma") == [
        AfirmacaoExibicao(texto="um texto qualquer, sem citação nenhuma", dispositivo=None)
    ]


def test_montar_texto_concatena_afirmacoes_com_a_citacao() -> None:
    texto = montar_texto(
        [
            Afirmacao(
                texto="O TCU aprecia mediante parecer prévio",
                dispositivo="CF/88 art. 71 I",
                trecho_que_decide="apreciar as contas",
            ),
            Afirmacao(
                texto="Quem julga é o Congresso",
                dispositivo="CF/88 art. 49 IX",
                trecho_que_decide="julgar anualmente",
            ),
        ]
    )
    assert texto == (
        "O TCU aprecia mediante parecer prévio [CF/88 art. 71 I] "
        "Quem julga é o Congresso [CF/88 art. 49 IX]"
    )

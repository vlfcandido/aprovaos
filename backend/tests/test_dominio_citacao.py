# O que é: testes do passo 2 da fundação jurídica — `dominio.citacao.extrair_citacoes`, a função
# que acha, no texto de uma questão, referências a dispositivo legal (art./inciso/parágrafo +
# norma) sem adivinhar. Casos vêm dos exemplos da skill `dna-do-concurso`/da tarefa e de trechos
# reais medidos em `dev.db` (ver `.superpowers/sdd/V3b-multipla-escolha/juridico-passo-2-report.md`,
# passo 2). Quando ler: ao mudar a gramática reconhecida, ou por que uma citação não foi achada.
from aprovaos.dominio.citacao import (
    ReferenciaLegal,
    extrair_citacoes,
    normalizar_citacao_para_comparacao,
)


def test_artigo_simples_da_cf_e_caput_implicito() -> None:
    """ "art. 37 da CF" vira uma referência ao caput (sem inciso/parágrafo explícito)."""
    referencias = extrair_citacoes("Nos termos do art. 37 da CF, a administração obedece a...")

    assert referencias == [
        ReferenciaLegal(
            norma="cf-1988",
            artigo="37",
            inciso=None,
            paragrafo=None,
            trecho="art. 37 da CF",
        )
    ]


def test_artigo_com_caput_explicito_e_igual_ao_implicito() -> None:
    """ "art. 37, caput, da Constituição Federal" resolve para o mesmo caput do artigo 37."""
    referencias = extrair_citacoes(
        "Segundo o art. 37, caput, da Constituição Federal, aplicam-se os princípios..."
    )

    assert referencias == [
        ReferenciaLegal(
            norma="cf-1988",
            artigo="37",
            inciso=None,
            paragrafo=None,
            trecho="art. 37, caput, da Constituição Federal",
        )
    ]


def test_lei_numerada_sozinha_sem_artigo_e_citacao_de_norma() -> None:
    """ "Lei nº 14.133/2021" sem artigo é citação válida — só não resolve para um dispositivo."""
    referencias = extrair_citacoes(
        "Os limites estabelecidos na Lei n.º 14.133/2021, concernentes às alterações..."
    )

    assert referencias == [
        ReferenciaLegal(
            norma="lei-14133-2021",
            artigo=None,
            inciso=None,
            paragrafo=None,
            trecho="Lei n.º 14.133/2021",
        )
    ]


def test_artigo_da_lei_numerada_com_ordinal() -> None:
    """ "art. 6º da Lei 14.133/2021" — número do artigo normalizado sem o ordinal."""
    referencias = extrair_citacoes("Conforme o art. 6º da Lei 14.133/2021, considera-se...")

    assert referencias == [
        ReferenciaLegal(
            norma="lei-14133-2021",
            artigo="6",
            inciso=None,
            paragrafo=None,
            trecho="art. 6º da Lei 14.133/2021",
        )
    ]


def test_paragrafo_sem_norma_e_ambiguo_nao_vira_citacao() -> None:
    """ "§ 1º do art. 37" sem indicar a norma é ambíguo — a regra de ouro proíbe adivinhar."""
    referencias = extrair_citacoes("Conforme o § 1º do art. 37, é vedado...")

    assert referencias == []


def test_paragrafo_do_artigo_com_norma_resolve_o_paragrafo() -> None:
    """ "§ 1º do art. 37 da CF" agora tem norma explícita — resolve para o parágrafo 1º."""
    referencias = extrair_citacoes("Conforme o § 1º do art. 37 da CF, é vedado...")

    assert referencias == [
        ReferenciaLegal(
            norma="cf-1988",
            artigo="37",
            inciso=None,
            paragrafo="1",
            trecho="§ 1º do art. 37 da CF",
        )
    ]


def test_inciso_do_artigo_da_cf_resolve_o_inciso() -> None:
    """ "inciso II do art. 37 da CF" resolve para o inciso II, não o caput."""
    referencias = extrair_citacoes("O inciso II do art. 37 da CF exige concurso público.")

    assert referencias == [
        ReferenciaLegal(
            norma="cf-1988",
            artigo="37",
            inciso="II",
            paragrafo=None,
            trecho="inciso II do art. 37 da CF",
        )
    ]


def test_texto_sem_nenhuma_referencia_nao_produz_citacao() -> None:
    """Texto sem "art."/norma reconhecível não vira citação nenhuma — é o caso comum na base."""
    referencias = extrair_citacoes(
        "O poder da administração pública de rever os próprios atos é absoluto."
    )

    assert referencias == []


def test_norma_nao_catalogada_ainda_e_reconhecida_como_lacuna() -> None:
    """CLT não está no catálogo do Planalto, mas é uma norma reconhecida — vira lacuna, não erro."""
    referencias = extrair_citacoes(
        "A multa prevista no art. 477 da CLT não é aplicável a pessoa jurídica de direito público."
    )

    assert referencias == [
        ReferenciaLegal(
            norma="clt",
            artigo="477",
            inciso=None,
            paragrafo=None,
            trecho="art. 477 da CLT",
        )
    ]


def test_lei_complementar_numerada_e_distinta_de_lei_ordinaria() -> None:
    """ "Lei Complementar nº 109/2001" vira norma própria — não confunde com "Lei nº 109/2001"."""
    referencias = extrair_citacoes(
        "De acordo com a Lei Complementar n.º 109/2001, o déficit será equacionado..."
    )

    assert referencias == [
        ReferenciaLegal(
            norma="lei-complementar-109-2001",
            artigo=None,
            inciso=None,
            paragrafo=None,
            trecho="Lei Complementar n.º 109/2001",
        )
    ]


def test_duas_referencias_distintas_no_mesmo_texto() -> None:
    """Um texto pode citar mais de um dispositivo — cada um vira uma referência, sem duplicar."""
    referencias = extrair_citacoes(
        "O art. 37 da CF traz os princípios; o art. 6º da Lei 14.133/2021 traz as definições."
    )

    assert referencias == [
        ReferenciaLegal(
            norma="cf-1988", artigo="37", inciso=None, paragrafo=None, trecho="art. 37 da CF"
        ),
        ReferenciaLegal(
            norma="lei-14133-2021",
            artigo="6",
            inciso=None,
            paragrafo=None,
            trecho="art. 6º da Lei 14.133/2021",
        ),
    ]


def test_referencia_repetida_no_mesmo_texto_nao_duplica() -> None:
    """A mesma referência citada duas vezes no mesmo texto vira uma só ocorrência na lista."""
    referencias = extrair_citacoes(
        "O art. 37 da CF... Mais adiante, o art. 37 da CF também dispõe sobre isso."
    )

    assert len(referencias) == 1
    assert referencias[0].norma == "cf-1988"
    assert referencias[0].artigo == "37"


def test_norma_sozinha_ja_consumida_pelo_artigo_nao_duplica() -> None:
    """ "art. 37 da CF" não gera uma segunda referência "só CF" — a norma já foi usada no artigo."""
    referencias = extrair_citacoes("O art. 37 da CF é claro.")

    assert len(referencias) == 1
    assert referencias[0].artigo == "37"


def test_abreviacao_academica_cf_ponto_nao_e_confundida_com_constituicao() -> None:
    """ "cf." minúsculo (abreviação de "confira") não é a Constituição Federal."""
    referencias = extrair_citacoes("Nesse sentido, cf. STF, RE 123.456, o entendimento é outro.")

    assert referencias == []


def test_normalizar_citacao_caso_real_que_falhou_ordinal_do_modelo_contra_gravado() -> None:
    """O caso real: o modelo citou "art. 1º"; o gravado era "art. 1" — mesmo dispositivo."""
    assert normalizar_citacao_para_comparacao(
        "Lei 8.429/1992 art. 1º"
    ) == normalizar_citacao_para_comparacao("Lei 8.429/1992 art. 1")


def test_normalizar_citacao_ordinal_letra_o_e_ponto_final_sao_o_mesmo_dispositivo() -> None:
    """ "art. 1º", "art. 1o", "art. 1" e "art. 1." normalizam para a mesma chave."""
    formas = [
        "Lei 8.429/1992 art. 1º",
        "Lei 8.429/1992 art. 1o",
        "Lei 8.429/1992 art. 1",
        "Lei 8.429/1992 art. 1.",
    ]
    normalizadas = {normalizar_citacao_para_comparacao(forma) for forma in formas}
    assert len(normalizadas) == 1


def test_normalizar_citacao_nao_confunde_artigo_1_com_artigo_1a() -> None:
    """ "art. 1" e "art. 1-A" são artigos distintos — a normalização não pode colidir os dois."""
    assert normalizar_citacao_para_comparacao(
        "Lei 8.429/1992 art. 1"
    ) != normalizar_citacao_para_comparacao("Lei 8.429/1992 art. 1-A")


def test_normalizar_citacao_nao_confunde_artigo_1_com_artigo_10() -> None:
    """ "art. 1" e "art. 10" são artigos distintos — a normalização não pode colidir os dois."""
    assert normalizar_citacao_para_comparacao(
        "Lei 8.429/1992 art. 1"
    ) != normalizar_citacao_para_comparacao("Lei 8.429/1992 art. 10")

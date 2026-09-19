# O que é: testes do validador mecânico da inédita (`dominio.validacao_questao`) — os cinco
# itens do validador da skill `gerador-questao-banca` §"Validador", aplicados por regra, sem
# embedding (Ruling 43). Quando ler: ao mudar `julgar`/`verificar_forma`/`verificar_fontes`, ou
# ao investigar por que um item bom (ou ruim) foi aprovado/reprovado.
from aprovaos.dominio.dossie import FonteDossie
from aprovaos.dominio.questao_inedita import AlternativaGerada, QuestaoGerada
from aprovaos.dominio.texto import similaridade_lexica
from aprovaos.dominio.validacao_questao import (
    julgar,
    verificar_fontes,
    verificar_forma,
)

FONTE = FonteDossie(
    id="F1",
    tipo="norma",
    norma="lei-8443-1992",
    artigo="71",
    inciso="I",
    citacao_canonica="CF/88 art. 71 I",
    url="https://planalto.gov.br/cf88",
    trecho=(
        "Art. 71. O controle externo, a cargo do Congresso Nacional, será exercido com o "
        "auxílio do Tribunal de Contas da União, ao qual compete: I - apreciar as contas "
        "prestadas anualmente pelo Presidente da República, mediante parecer prévio, que "
        "deverá ser elaborado em sessenta dias a contar de seu recebimento;"
    ),
)

ORIGINAIS = [
    "Compete ao TCU apreciar as contas do Presidente mediante parecer prévio.",
    "O parecer prévio do TCU sobre as contas do Presidente é elaborado em sessenta dias.",
    "O Congresso Nacional exerce o controle externo com o auxílio do TCU.",
    "As contas do Presidente da República são apreciadas anualmente pelo TCU.",
    "Ao TCU compete apreciar, mediante parecer prévio, as contas do Presidente.",
]


def _item_certo_errado(
    *,
    enunciado: str = "O TCU aprecia as contas do Presidente da República mediante parecer prévio.",
    trecho: str = "apreciar as contas prestadas anualmente pelo Presidente da República",
    gabarito: str = "C",
    comando: str | None = "Julgue o item a seguir.",
    fontes: list[str] | None = None,
) -> QuestaoGerada:
    return QuestaoGerada(
        tipo_item="certo_errado",
        banca_alvo="cebraspe",
        comando=comando,
        enunciado=enunciado,
        alternativas=None,
        gabarito=gabarito,
        fontes=fontes if fontes is not None else ["F1"],
        trecho_que_decide=trecho,
        justificativa_certo="Se o item dissesse 'aprecia', estaria certo.",
        justificativa_errado="O TCU aprecia, não julga.",
        mecanismo="literal",
        original_de_referencia="cebraspe 2024 tce-xx item 57",
        topico_slug="dir-const-06-fiscalizacao",
        aderencia_medida=True,
    )


class TestVerificarForma:
    def test_item_conforme_nao_reprova(self) -> None:
        assert verificar_forma(_item_certo_errado(), "cebraspe") == []

    def test_sem_comando_reprova(self) -> None:
        motivos = verificar_forma(_item_certo_errado(comando=None), "cebraspe")
        assert any("comando" in m for m in motivos)

    def test_mais_de_40_palavras_reprova(self) -> None:
        enunciado = " ".join(["palavra"] * 45)
        motivos = verificar_forma(_item_certo_errado(enunciado=enunciado), "cebraspe")
        assert any("40 palavras" in m for m in motivos)

    def test_sempre_ou_nunca_gratuito_reprova(self) -> None:
        enunciado = "O TCU sempre aprecia as contas do Presidente da República."
        motivos = verificar_forma(_item_certo_errado(enunciado=enunciado), "cebraspe")
        assert any("sempre" in m.lower() or "nunca" in m.lower() for m in motivos)

    def test_duas_afirmacoes_no_mesmo_item_reprova(self) -> None:
        enunciado = (
            "O TCU aprecia as contas do Presidente da República. O STF julga as ações diretas "
            "de inconstitucionalidade."
        )
        motivos = verificar_forma(_item_certo_errado(enunciado=enunciado), "cebraspe")
        assert any("uma afirmação" in m or "duas afirmações" in m for m in motivos)

    def test_multipla_escolha_com_cinco_alternativas_homogeneas_nao_reprova(self) -> None:
        item = _item_certo_errado()
        item = item.model_copy(
            update={
                "tipo_item": "multipla_escolha",
                "alternativas": [
                    AlternativaGerada(letra=letra, texto=f"Texto da alternativa {letra} completo.")
                    for letra in "ABCDE"
                ],
                "gabarito": "A",
            }
        )
        assert verificar_forma(item, "fgv") == []

    def test_multipla_escolha_com_tamanhos_dispares_reprova(self) -> None:
        item = _item_certo_errado()
        alternativas = [
            AlternativaGerada(letra=letra, texto=f"Texto da alternativa {letra} completo.")
            for letra in "ABCD"
        ]
        alternativas.append(
            AlternativaGerada(
                letra="E",
                texto=(
                    "Texto muito mais longo do que as demais alternativas, "
                    "com muito mais palavras e detalhes desnecessários para forçar a disparidade."
                ),
            )
        )
        item = item.model_copy(
            update={"tipo_item": "multipla_escolha", "alternativas": alternativas, "gabarito": "A"}
        )
        motivos = verificar_forma(item, "fgv")
        assert any("tamanho" in m for m in motivos)

    def test_multipla_escolha_sem_cinco_alternativas_reprova(self) -> None:
        item = _item_certo_errado()
        item = item.model_copy(
            update={
                "tipo_item": "multipla_escolha",
                "alternativas": [AlternativaGerada(letra="A", texto="Só uma alternativa.")],
                "gabarito": "A",
            }
        )
        motivos = verificar_forma(item, "fgv")
        assert any("cinco alternativas" in m for m in motivos)


class TestVerificarFontes:
    def test_fonte_existente_e_trecho_literal_nao_reprova(self) -> None:
        assert verificar_fontes(_item_certo_errado(), [FONTE]) == []

    def test_fonte_inexistente_no_dossie_reprova(self) -> None:
        motivos = verificar_fontes(_item_certo_errado(fontes=["F9"]), [FONTE])
        assert any("F9" in m for m in motivos)

    def test_trecho_que_nao_esta_na_fonte_reprova(self) -> None:
        item = _item_certo_errado(trecho="isto não existe em lugar nenhum do dossiê")
        motivos = verificar_fontes(item, [FONTE])
        assert any("literalmente" in m for m in motivos)

    def test_sem_nenhuma_fonte_reprova(self) -> None:
        # `QuestaoGerada.fontes` já exige `min_length=1`, então o caminho testado aqui é o
        # dossiê vazio: nenhuma fonte oferecida casa com a declarada no item.
        motivos = verificar_fontes(_item_certo_errado(), [])
        assert motivos != []


class TestSimilaridadeLexica:
    def test_texto_identico_a_um_original_tem_similaridade_alta(self) -> None:
        assert similaridade_lexica(ORIGINAIS[0], ORIGINAIS) > 0.5

    def test_texto_sem_nenhuma_palavra_em_comum_tem_similaridade_baixa(self) -> None:
        texto = "zzz yyy xxx www vvv uuu ttt sss"
        assert similaridade_lexica(texto, ORIGINAIS) < 0.05

    def test_similaridade_no_intervalo_0_1(self) -> None:
        valor = similaridade_lexica(_item_certo_errado().enunciado, ORIGINAIS)
        assert 0.0 <= valor <= 1.0


class TestJulgar:
    def test_item_conforme_aprova(self) -> None:
        veredito = julgar(_item_certo_errado(), [FONTE], ORIGINAIS, resolucao_independente="C")
        assert veredito.aprovado is True
        assert veredito.motivos == []
        assert veredito.aderencia_pct is not None

    def test_gabarito_divergente_da_resolucao_independente_reprova(self) -> None:
        veredito = julgar(_item_certo_errado(), [FONTE], ORIGINAIS, resolucao_independente="E")
        assert veredito.aprovado is False
        assert any("gabarito" in m for m in veredito.motivos)

    def test_consequencia_acrescentada_fora_do_trecho_reprova(self) -> None:
        item = _item_certo_errado(
            enunciado=(
                "O TCU aprecia as contas do Presidente da República, podendo executá-las "
                "diretamente sem necessidade de nova apreciação do Congresso Nacional."
            )
        )
        veredito = julgar(item, [FONTE], ORIGINAIS, resolucao_independente="C")
        assert veredito.aprovado is False
        assert any("consequência" in m or "acrescentada" in m for m in veredito.motivos)

    def test_aderencia_pct_none_com_menos_de_5_originais(self) -> None:
        veredito = julgar(_item_certo_errado(), [FONTE], ORIGINAIS[:3], resolucao_independente="C")
        assert veredito.aderencia_pct is None

    def test_fonte_inexistente_reprova_via_julgar(self) -> None:
        item = _item_certo_errado(fontes=["F9"])
        veredito = julgar(item, [FONTE], ORIGINAIS, resolucao_independente="C")
        assert veredito.aprovado is False

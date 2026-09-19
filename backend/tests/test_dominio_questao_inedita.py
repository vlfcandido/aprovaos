# O que é: testes do contrato `QuestaoGerada` e do Passo 0 (plano de mecanismos/gabaritos) da
# skill `gerador-questao-banca` — fatia 5. Quando ler: ao mudar `montar_plano_do_lote` ou
# `conferir_lote`, ou ao investigar por que um lote gerado foi apontado como fora do plano.
import pytest
from pydantic import ValidationError

from aprovaos.dominio.questao_inedita import (
    AlternativaGerada,
    ItemDoPlano,
    QuestaoGerada,
    conferir_lote,
    montar_plano_do_lote,
)


def _item(
    *,
    mecanismo: str = "literal",
    gabarito: str = "C",
    tipo_item: str = "certo_errado",
    topico_slug: str = "dir-adm-04-licitacoes",
) -> QuestaoGerada:
    return QuestaoGerada(
        tipo_item=tipo_item,
        banca_alvo="cebraspe",
        comando="Julgue o item a seguir.",
        enunciado="O TCU aprecia as contas do Presidente da República.",
        alternativas=None,
        gabarito=gabarito,
        fontes=["F1"],
        trecho_que_decide="apreciar as contas prestadas anualmente",
        justificativa_certo="Se o item dissesse 'aprecia', estaria certo.",
        justificativa_errado="O TCU aprecia, não julga.",
        mecanismo=mecanismo,
        original_de_referencia="cebraspe 2024 tce-xx item 57",
        topico_slug=topico_slug,
        aderencia_medida=True,
    )


class TestMontarPlanoDoLote:
    def test_n_5_reserva_um_literal(self) -> None:
        plano = montar_plano_do_lote(n_pedido=5, originais_recebidos=5, tipo_item="certo_errado")
        assert plano.mecanismos["literal"] == 1
        assert len(plano.itens) == 5

    def test_n_3_nao_reserva_literal(self) -> None:
        plano = montar_plano_do_lote(n_pedido=3, originais_recebidos=5, tipo_item="certo_errado")
        assert plano.mecanismos["literal"] == 0
        assert len(plano.itens) == 3

    def test_resto_distribuido_em_ordem_fixa_sem_random(self) -> None:
        # n=5 → literal=1, resto=4 distribuído nos primeiros 4 mecanismos da ordem fixa
        # (troca_de_verbo, troca_de_competencia, troca_de_quorum, excecao_omitida), sobrando
        # troca_de_prazo=0 — mesmo exemplo do cabeçalho da skill.
        plano = montar_plano_do_lote(n_pedido=5, originais_recebidos=5, tipo_item="certo_errado")
        assert plano.mecanismos == {
            "literal": 1,
            "troca_de_verbo": 1,
            "troca_de_competencia": 1,
            "troca_de_quorum": 1,
            "excecao_omitida": 1,
            "troca_de_prazo": 0,
        }

    def test_plano_e_deterministico(self) -> None:
        plano1 = montar_plano_do_lote(n_pedido=12, originais_recebidos=5, tipo_item="certo_errado")
        plano2 = montar_plano_do_lote(n_pedido=12, originais_recebidos=5, tipo_item="certo_errado")
        assert plano1 == plano2

    def test_gabaritos_quase_50_50_em_certo_errado(self) -> None:
        plano = montar_plano_do_lote(n_pedido=5, originais_recebidos=5, tipo_item="certo_errado")
        assert plano.gabaritos == {"C": 3, "E": 2}
        assert sum(plano.gabaritos.values()) == 5

    def test_gabaritos_distribuidos_em_a_e_para_multipla_escolha(self) -> None:
        plano = montar_plano_do_lote(
            n_pedido=5, originais_recebidos=5, tipo_item="multipla_escolha"
        )
        assert set(plano.gabaritos) == {"A", "B", "C", "D", "E"}
        assert sum(plano.gabaritos.values()) == 5

    def test_aderencia_medida_falsa_com_menos_de_5_originais(self) -> None:
        plano = montar_plano_do_lote(n_pedido=5, originais_recebidos=4, tipo_item="certo_errado")
        assert plano.aderencia_medida is False

    def test_aderencia_medida_verdadeira_com_5_originais(self) -> None:
        plano = montar_plano_do_lote(n_pedido=5, originais_recebidos=5, tipo_item="certo_errado")
        assert plano.aderencia_medida is True

    def test_n_pedido_zero_ou_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="n_pedido"):
            montar_plano_do_lote(n_pedido=0, originais_recebidos=5, tipo_item="certo_errado")
        with pytest.raises(ValueError, match="n_pedido"):
            montar_plano_do_lote(n_pedido=-1, originais_recebidos=5, tipo_item="certo_errado")

    def test_itens_do_plano_batem_com_os_dicionarios_de_contagem(self) -> None:
        plano = montar_plano_do_lote(n_pedido=12, originais_recebidos=5, tipo_item="certo_errado")
        contagem_mecanismo: dict[str, int] = {}
        contagem_gabarito: dict[str, int] = {}
        for item in plano.itens:
            contagem_mecanismo[item.mecanismo] = contagem_mecanismo.get(item.mecanismo, 0) + 1
            contagem_gabarito[item.gabarito] = contagem_gabarito.get(item.gabarito, 0) + 1
        assert contagem_mecanismo == plano.mecanismos
        assert contagem_gabarito == plano.gabaritos


class TestConferirLote:
    def test_lote_conforme_devolve_vazio(self) -> None:
        plano = montar_plano_do_lote(n_pedido=2, originais_recebidos=5, tipo_item="certo_errado")
        itens = [_item(mecanismo=i.mecanismo, gabarito=i.gabarito) for i in plano.itens]
        assert conferir_lote(itens, plano) == []

    def test_mecanismo_a_mais_e_apontado(self) -> None:
        plano = montar_plano_do_lote(n_pedido=2, originais_recebidos=5, tipo_item="certo_errado")
        # troca todos os itens para o mesmo mecanismo, quebrando a contagem esperada.
        itens = [_item(mecanismo="literal", gabarito=i.gabarito) for i in plano.itens]
        divergencias = conferir_lote(itens, plano)
        assert divergencias != []
        assert any("mecanismo" in d for d in divergencias)

    def test_gabarito_fora_do_plano_e_apontado(self) -> None:
        plano = montar_plano_do_lote(n_pedido=2, originais_recebidos=5, tipo_item="certo_errado")
        itens = [_item(mecanismo=i.mecanismo, gabarito="C") for i in plano.itens]
        divergencias = conferir_lote(itens, plano)
        assert any("gabarito" in d for d in divergencias)

    def test_quantidade_diferente_do_n_pedido_e_apontada(self) -> None:
        plano = montar_plano_do_lote(n_pedido=3, originais_recebidos=5, tipo_item="certo_errado")
        itens = [_item(mecanismo=i.mecanismo, gabarito=i.gabarito) for i in plano.itens[:2]]
        divergencias = conferir_lote(itens, plano)
        assert any("quantidade" in d for d in divergencias)


class TestQuestaoGerada:
    def test_nasce_sempre_nao_publicada(self) -> None:
        item = _item()
        assert item.publicado is False
        assert item.marcacao == "inédita validada — pendente"

    def test_alternativa_gerada_aceita_letras_a_e(self) -> None:
        alternativa = AlternativaGerada(letra="A", texto="Texto da alternativa A.")
        assert alternativa.letra == "A"

    def test_gabarito_fora_do_alfabeto_a_e_rejeitado(self) -> None:
        with pytest.raises(ValidationError):
            _item(gabarito="Z")

    def test_item_do_plano_exige_mecanismo_valido(self) -> None:
        with pytest.raises(ValidationError):
            ItemDoPlano(mecanismo="invencionice", gabarito="C")

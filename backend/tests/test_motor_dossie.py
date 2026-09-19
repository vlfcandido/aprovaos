# O que é: testes de `motor.dossie` — `construir_dossie` (genérico, dirigido por `RECEITAS`),
# `topicos_de_maior_peso` (o critério de peso medido desta fatia) e `construir_dossies` (o laço
# que `main()` usa, incluindo o caso "sem receita"). Sem rede, sem LLM. Quando ler: ao acrescentar
# uma receita nova, mudar o critério de peso, ou investigar por que um tópico não gerou dossiê.
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import (
    Concurso,
    DispositivoLegal,
    Edital,
    Questao,
    Topico,
    TopicoEdital,
)
from aprovaos.dominio.erros import TopicoNaoEncontrado
from aprovaos.motor.dossie import (
    RECEITAS,
    construir_dossie,
    construir_dossies,
    topicos_de_maior_peso,
)

HOJE = date(2026, 9, 19)


def _topico(db: Session, slug: str, materia: str = "direito-administrativo") -> Topico:
    topico = Topico(materia=materia, nome=slug, slug=slug)
    db.add(topico)
    db.flush()
    return topico


class TestConstruirDossieImprobidade:
    """A receita de improbidade (Lei 8.429/1992 + STJ 651/634) — cobre norma e súmula juntas."""

    def test_constroi_e_grava_o_dossie_com_fontes_de_norma_e_de_sumula(self, db: Session) -> None:
        topico = _topico(db, "dir-adm-06-improbidade-administrativa")

        dossie, conteudo = construir_dossie(db, topico.slug, hoje=HOJE)
        db.flush()

        assert dossie.topico_id == topico.id
        assert dossie.versao == 1

        citacoes = {fonte.citacao_canonica for fonte in conteudo.fontes}
        assert "Lei 8.429/1992 art. 1" in citacoes
        assert "Lei 8.429/1992 art. 1 § 2º" in citacoes  # definição de dolo
        assert "Lei 8.429/1992 art. 23" in citacoes  # prescrição
        assert "STJ Súmula 651" in citacoes
        assert "STJ Súmula 634" in citacoes

        tipos = {fonte.tipo for fonte in conteudo.fontes}
        assert tipos == {"norma", "sumula"}

        # só as fontes de norma viram dispositivo_legal — as duas súmulas, não:
        assert db.query(DispositivoLegal).filter_by(norma="lei-8429-1992").count() == len(
            {c for c in citacoes if c.startswith("Lei")}
        )

    def test_declara_lacuna_para_artigos_com_estrutura_nao_tratada(self, db: Session) -> None:
        """Arts. 9º, 10, 11 (Título Caso) e 17 (§ com sufixo de letra) viram lacuna."""
        _topico(db, "dir-adm-06-improbidade-administrativa")

        _dossie, conteudo = construir_dossie(db, "dir-adm-06-improbidade-administrativa", hoje=HOJE)

        dispositivos_das_lacunas = {lacuna.dispositivo for lacuna in conteudo.lacunas}
        assert "Lei 8.429/1992 art. 9" in dispositivos_das_lacunas
        assert "Lei 8.429/1992 art. 17" in dispositivos_das_lacunas


class TestConstruirDossieDireitosGarantias:
    """CF art. 5º (incisos/parágrafos) + SV 1 e SV 11 — as duas súmulas resolvem de verdade."""

    def test_constroi_com_fontes_de_cf_e_duas_sumulas_vinculantes(self, db: Session) -> None:
        topico = _topico(db, "dir-con-02-direitos-garantias", materia="direito-constitucional")

        dossie, conteudo = construir_dossie(db, topico.slug, hoje=HOJE)

        citacoes = {fonte.citacao_canonica for fonte in conteudo.fontes}
        assert "CF/88 art. 5" in citacoes
        assert "CF/88 art. 5 XXXVI" in citacoes
        assert "STF SV 1" in citacoes
        assert "STF SV 11" in citacoes
        assert conteudo.lacunas == []  # todos os pedidos desta receita resolvem de verdade

        fonte_sv11 = next(f for f in conteudo.fontes if f.citacao_canonica == "STF SV 11")
        assert fonte_sv11.trecho.startswith("Só é lícito o uso de algemas")
        assert fonte_sv11.tipo == "sumula"
        assert dossie.versao == 1


class TestConstruirDossieRecursosApelacao:
    """CPC (Lei 13.105/2015) — o achado do artigo de 4 dígitos (§2 do plano) provado aqui."""

    def test_constroi_com_artigos_de_quatro_digitos_do_cpc(self, db: Session) -> None:
        topico = _topico(db, "dir-pro-civ-05-recursos-apelacao", materia="direito-processual-civil")

        _dossie, conteudo = construir_dossie(db, topico.slug, hoje=HOJE)

        citacoes = {fonte.citacao_canonica for fonte in conteudo.fontes}
        assert "Lei 13.105/2015 art. 1009" in citacoes
        assert "Lei 13.105/2015 art. 1022" in citacoes
        assert "STJ Súmula 98" in citacoes
        assert "STJ Súmula 347" in citacoes

    def test_artigo_1026_fica_como_lacuna_declarada_de_proposito(self, db: Session) -> None:
        """Achado registrado, não remendado (§2 do plano): título de Seção em Title Case entre
        os arts. 1.025 e 1.026 do CPC."""
        _topico(db, "dir-pro-civ-05-recursos-apelacao", materia="direito-processual-civil")

        _dossie, conteudo = construir_dossie(db, "dir-pro-civ-05-recursos-apelacao", hoje=HOJE)

        dispositivos_das_lacunas = {lacuna.dispositivo for lacuna in conteudo.lacunas}
        assert "Lei 13.105/2015 art. 1026" in dispositivos_das_lacunas


class TestConstruirDossieAtosProcessuais:
    def test_constroi_com_artigos_de_prazo_e_a_sumula_216(self, db: Session) -> None:
        topico = _topico(db, "dir-pro-civ-03-atos-processuais", materia="direito-processual-civil")

        _dossie, conteudo = construir_dossie(db, topico.slug, hoje=HOJE)

        citacoes = {fonte.citacao_canonica for fonte in conteudo.fontes}
        assert "Lei 13.105/2015 art. 218" in citacoes
        assert "Lei 13.105/2015 art. 219" in citacoes
        assert "STJ Súmula 216" in citacoes
        assert conteudo.lacunas == []


def test_topico_inexistente_levanta_erro_de_dominio(db: Session) -> None:
    """Sem o tópico cadastrado, o comando para e avisa — nunca cria o tópico sozinho."""
    with pytest.raises(TopicoNaoEncontrado):
        construir_dossie(db, "dir-adm-06-improbidade-administrativa", hoje=HOJE)


def test_todas_as_receitas_tem_pelo_menos_um_pedido() -> None:
    """Trava de qualidade: nenhuma receita fica registrada vazia por engano."""
    assert len(RECEITAS) >= 4
    for slug, receita in RECEITAS.items():
        assert receita.pedidos, f"{slug} sem nenhum PedidoDispositivo"


class TestTopicosDeMaiorPeso:
    """`topicos_de_maior_peso`: nº de questões publicáveis por tópico do edital, descendente."""

    def _edital(self, db: Session) -> Edital:
        concurso = Concurso(
            orgao="CÂMARA MUNICIPAL DE CASCAVEL", cargo="ASSESSOR DE GABINETE", banca="FAU"
        )
        db.add(concurso)
        db.flush()
        edital = Edital(concurso_id=concurso.id, versao=1, documento_id=uuid4())
        db.add(edital)
        db.flush()
        return edital

    def _vincular(self, db: Session, edital: Edital, topico: Topico, ordem: int) -> None:
        db.add(
            TopicoEdital(
                edital_id=edital.id,
                topico_id=topico.id,
                ordem=ordem,
                texto_original=topico.nome,
            )
        )
        db.flush()

    def _questao_publicavel(self, db: Session, topico: Topico) -> None:
        db.add(
            Questao(
                adapter="concursos",
                banca="cebraspe",
                tipo_item="certo_errado",
                texto_apoio_itens=[],
                enunciado="enunciado de teste",
                gabarito_status="definitivo",
                publicavel=True,
                publicada=False,
                regra_prova={},
                topico_id=topico.id,
                topico_confianca="alta",
                topico_evidencia="teste",
                inedita=False,
                hash_dedup=str(uuid4()),
            )
        )
        db.flush()

    def test_ordena_por_numero_de_questoes_publicaveis_descendente(self, db: Session) -> None:
        edital = self._edital(db)
        muito = _topico(db, "materia-01-muito-cobrado")
        pouco = _topico(db, "materia-02-pouco-cobrado")
        nenhuma = _topico(db, "materia-03-sem-questao")
        self._vincular(db, edital, muito, 1)
        self._vincular(db, edital, pouco, 2)
        self._vincular(db, edital, nenhuma, 3)
        for _ in range(3):
            self._questao_publicavel(db, muito)
        self._questao_publicavel(db, pouco)

        ranking = topicos_de_maior_peso(db, edital.id, limite=10)

        assert [t.slug for t in ranking] == [
            "materia-01-muito-cobrado",
            "materia-02-pouco-cobrado",
            "materia-03-sem-questao",
        ]
        assert ranking[0].questoes_publicaveis == 3
        assert ranking[2].questoes_publicaveis == 0

    def test_respeita_o_limite(self, db: Session) -> None:
        edital = self._edital(db)
        for n in range(5):
            topico = _topico(db, f"materia-{n:02d}")
            self._vincular(db, edital, topico, n)

        ranking = topicos_de_maior_peso(db, edital.id, limite=2)

        assert len(ranking) == 2

    def test_nao_conta_questao_nao_publicavel(self, db: Session) -> None:
        edital = self._edital(db)
        topico = _topico(db, "materia-01")
        self._vincular(db, edital, topico, 1)
        db.add(
            Questao(
                adapter="concursos",
                banca="cebraspe",
                tipo_item="certo_errado",
                texto_apoio_itens=[],
                enunciado="anulada",
                gabarito_status="anulado",
                publicavel=False,
                publicada=False,
                motivo_nao_publicavel="anulado",
                regra_prova={},
                topico_id=topico.id,
                topico_confianca="alta",
                topico_evidencia="teste",
                inedita=False,
                hash_dedup=str(uuid4()),
            )
        )
        db.flush()

        ranking = topicos_de_maior_peso(db, edital.id, limite=10)

        assert ranking[0].questoes_publicaveis == 0


class TestConstruirDossies:
    """`construir_dossies`: o laço de `main()` — inclusive o tópico sem receita cadastrada."""

    def test_relata_sem_receita_para_topico_fora_de_receitas(self, db: Session) -> None:
        _topico(db, "dir-adm-03-poderes-administrativos")

        relatorios = construir_dossies(db, ["dir-adm-03-poderes-administrativos"], hoje=HOJE)

        assert relatorios[0].sem_receita is True
        assert relatorios[0].fontes is None

    def test_constroi_os_que_tem_receita_e_reporta_os_que_nao_tem(self, db: Session) -> None:
        _topico(db, "dir-adm-06-improbidade-administrativa")
        _topico(db, "dir-adm-03-poderes-administrativos")

        relatorios = construir_dossies(
            db,
            ["dir-adm-06-improbidade-administrativa", "dir-adm-03-poderes-administrativos"],
            hoje=HOJE,
        )

        assert relatorios[0].sem_receita is False
        assert relatorios[0].fontes is not None and relatorios[0].fontes > 0
        assert relatorios[1].sem_receita is True

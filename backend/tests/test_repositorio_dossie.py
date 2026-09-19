# O que é: testes do passo 3 da fundação jurídica — `dados.repositorio_dossie`: versionamento
# de `dossie_topico` e gravação dos `dispositivo_legal` que suas fontes referenciam. Quando ler:
# ao mexer em `dados/repositorio_dossie.py` ou no comando `motor/dossie.py`.
from datetime import date

from sqlalchemy.orm import Session

from aprovaos.dados.modelos import DispositivoLegal, DossieTopico, Topico
from aprovaos.dados.repositorio_dossie import (
    dossie_mais_recente_do_topico,
    proxima_versao,
    salvar_dossie,
)
from aprovaos.dados.repositorio_topico_relacao import (
    criar_relacao_equivalente,
    criar_relacao_subconjunto,
)
from aprovaos.dominio.dossie import ConteudoDossie, EntradaLogBusca, FonteDossie


def _topico(db: Session, slug: str = "dir-adm-06-improbidade-administrativa") -> Topico:
    topico = Topico(
        materia="direito-administrativo",
        nome="Improbidade administrativa",
        slug=slug,
    )
    db.add(topico)
    db.flush()
    return topico


def _conteudo(trecho: str = "condutas dolosas [...]") -> ConteudoDossie:
    return ConteudoDossie(
        conteudo=f'Lei 8.429/1992 art. 1 § 1º: "{trecho}" [F1]',
        fontes=[
            FonteDossie(
                id="F1",
                norma="lei-8429-1992",
                artigo="1",
                inciso=None,
                paragrafo="1",
                citacao_canonica="Lei 8.429/1992 art. 1 § 1º",
                url="https://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
                trecho=trecho,
                vigente=True,
                redacao_de=None,
            )
        ],
        lacunas=[],
        log_buscas=[
            EntradaLogBusca(
                n=1,
                consulta="Lei 8.429/1992 art. 1 § 1º",
                ferramenta="extrair_artigo (offline)",
                resultado="aberta: trecho encontrado",
                data=date(2026, 9, 19),
            )
        ],
    )


def test_salvar_dossie_grava_a_linha_e_o_dispositivo_da_fonte(db: Session) -> None:
    """`salvar_dossie` cria `dossie_topico` versão 1 e o `dispositivo_legal` da fonte F1."""
    topico = _topico(db)

    dossie = salvar_dossie(db, topico_id=topico.id, conteudo=_conteudo())
    db.flush()

    assert dossie.topico_id == topico.id
    assert dossie.versao == 1
    assert dossie.fontes[0]["citacao_canonica"] == "Lei 8.429/1992 art. 1 § 1º"
    assert dossie.log_buscas[0]["resultado"] == "aberta: trecho encontrado"
    assert dossie.validado_em is None
    assert dossie.substituido_por is None

    dispositivo = db.query(DispositivoLegal).one()
    assert dispositivo.citacao_canonica == "Lei 8.429/1992 art. 1 § 1º"
    assert dispositivo.norma == "lei-8429-1992"
    assert dispositivo.paragrafo == "1"


def test_salvar_dossie_de_novo_para_o_mesmo_topico_cria_versao_2(db: Session) -> None:
    """Uma segunda chamada para o mesmo tópico incrementa `versao` — não sobrescreve a 1."""
    topico = _topico(db)
    salvar_dossie(db, topico_id=topico.id, conteudo=_conteudo())
    db.flush()

    segunda = salvar_dossie(db, topico_id=topico.id, conteudo=_conteudo("nova redação [...]"))
    db.flush()

    assert segunda.versao == 2
    assert db.query(DossieTopico).filter_by(topico_id=topico.id).count() == 2


def test_salvar_dossie_nao_duplica_dispositivo_ja_existente(db: Session) -> None:
    """Se a fonte da nova versão cita o mesmo dispositivo, `dispositivo_legal` não duplica."""
    topico = _topico(db)
    salvar_dossie(db, topico_id=topico.id, conteudo=_conteudo())
    db.flush()

    salvar_dossie(db, topico_id=topico.id, conteudo=_conteudo())  # mesma citacao_canonica
    db.flush()

    assert db.query(DispositivoLegal).count() == 1


def test_proxima_versao_e_1_quando_nao_ha_dossie_do_topico(db: Session) -> None:
    topico = _topico(db)
    assert proxima_versao(db, topico.id) == 1


def test_dossie_mais_recente_do_topico_acha_a_maior_versao_direta(db: Session) -> None:
    topico = _topico(db)
    salvar_dossie(db, topico_id=topico.id, conteudo=_conteudo())
    segunda = salvar_dossie(db, topico_id=topico.id, conteudo=_conteudo("nova redação [...]"))
    db.flush()

    encontrada = dossie_mais_recente_do_topico(db, topico.id)
    assert encontrada is not None
    assert encontrada.id == segunda.id


def test_dossie_mais_recente_do_topico_sem_dossie_devolve_none(db: Session) -> None:
    topico = _topico(db)
    assert dossie_mais_recente_do_topico(db, topico.id) is None


def test_dossie_mais_recente_do_topico_segue_relacao_de_equivalencia(db: Session) -> None:
    """`dossie_mais_recente_do_topico` fecha a P-52 (ADR-0041): um tópico sem dossiê próprio,

    mas equivalente a outro que tem, encontra o dossiê do equivalente."""
    ficticio = _topico(db, "dir-adm-06-improbidade-administrativa")
    real = _topico(db, "noc-dir-adm-06-6-improbidade")
    dossie = salvar_dossie(db, topico_id=ficticio.id, conteudo=_conteudo())
    criar_relacao_equivalente(
        db, de_id=ficticio.id, para_id=real.id, evidencia="ambos citam a Lei nº 8.429/1992"
    )
    db.flush()

    encontrada = dossie_mais_recente_do_topico(db, real.id)
    assert encontrada is not None
    assert encontrada.id == dossie.id


def test_dossie_mais_recente_do_topico_prefere_o_direto_ao_equivalente(db: Session) -> None:
    ficticio = _topico(db, "dir-adm-06-improbidade-administrativa")
    real = _topico(db, "noc-dir-adm-06-6-improbidade")
    salvar_dossie(db, topico_id=ficticio.id, conteudo=_conteudo())
    dossie_proprio = salvar_dossie(db, topico_id=real.id, conteudo=_conteudo("versão própria"))
    criar_relacao_equivalente(db, de_id=ficticio.id, para_id=real.id, evidencia="mesma lei")
    db.flush()

    encontrada = dossie_mais_recente_do_topico(db, real.id)
    assert encontrada is not None
    assert encontrada.id == dossie_proprio.id


def test_dossie_mais_recente_do_topico_segue_relacao_de_subconjunto(db: Session) -> None:
    """I1: sem dossiê próprio nem equivalente pleno, um tópico ligado por cobertura parcial
    (`subconjunto_curado`) ainda encontra o dossiê — não "sumir" é melhor que a plena mesmo sem
    o rótulo de plena (quem precisa do aviso usa `repositorio_aula
    .aula_publicada_do_topico_com_origem`)."""
    cascavel = _topico(db, "dir-pro-civ-05-recursos-apelacao")
    tjpr = _topico(db, "noc-dir-pro-civ-07-recursos")
    dossie = salvar_dossie(db, topico_id=cascavel.id, conteudo=_conteudo())
    criar_relacao_subconjunto(
        db, de_id=cascavel.id, para_id=tjpr.id, evidencia="cobre só parte do item"
    )
    db.flush()

    encontrada = dossie_mais_recente_do_topico(db, tjpr.id)
    assert encontrada is not None
    assert encontrada.id == dossie.id


def test_dossie_mais_recente_do_topico_prefere_equivalente_pleno_a_subconjunto(
    db: Session,
) -> None:
    plena = _topico(db, "a-plena")
    parcial = _topico(db, "b-parcial")
    alvo = _topico(db, "c-alvo")
    dossie_plena = salvar_dossie(db, topico_id=plena.id, conteudo=_conteudo())
    salvar_dossie(db, topico_id=parcial.id, conteudo=_conteudo("outra versão"))
    criar_relacao_equivalente(db, de_id=alvo.id, para_id=plena.id, evidencia="mesma lei")
    criar_relacao_subconjunto(db, de_id=alvo.id, para_id=parcial.id, evidencia="parte do item")
    db.flush()

    encontrada = dossie_mais_recente_do_topico(db, alvo.id)
    assert encontrada is not None
    assert encontrada.id == dossie_plena.id


def _conteudo_com_sumula() -> ConteudoDossie:
    """Uma fonte `tipo="norma"` e uma `tipo="sumula"` — só a primeira deve virar
    `dispositivo_legal` (fatia 4, §1.3 do plano)."""
    conteudo = _conteudo()
    fonte_sumula = FonteDossie(
        id="F2",
        tipo="sumula",
        citacao_canonica="STJ Súmula 651",
        url=(
            "https://scon.stj.jus.br/docs_internet/jurisprudencia/tematica/download/SU/"
            "Verbetes/VerbetesSTJ.pdf"
        ),
        trecho=(
            "Compete à autoridade administrativa aplicar a servidor público a pena de demissão "
            "em razão da prática de improbidade administrativa, independentemente de prévia "
            "condenação, por autoridade judiciária, à perda da função pública."
        ),
        vigente=True,
    )
    return conteudo.model_copy(update={"fontes": [*conteudo.fontes, fonte_sumula]})


def test_salvar_dossie_nao_cria_dispositivo_legal_para_fonte_de_sumula(db: Session) -> None:
    """Uma fonte `tipo="sumula"` fica no JSON de `dossie_topico.fontes`, mas não vira
    `dispositivo_legal` — essa tabela é, por contrato, só de dispositivo de norma."""
    topico = _topico(db)

    dossie = salvar_dossie(db, topico_id=topico.id, conteudo=_conteudo_com_sumula())
    db.flush()

    assert len(dossie.fontes) == 2
    assert dossie.fontes[1]["tipo"] == "sumula"
    assert dossie.fontes[1]["citacao_canonica"] == "STJ Súmula 651"
    # só a fonte de norma (F1) virou dispositivo_legal — a súmula (F2), não:
    assert db.query(DispositivoLegal).count() == 1
    assert db.query(DispositivoLegal).one().citacao_canonica == "Lei 8.429/1992 art. 1 § 1º"

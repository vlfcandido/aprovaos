# O que é: testes do passo 3 da fundação jurídica — `dados.repositorio_dossie`: versionamento
# de `dossie_topico` e gravação dos `dispositivo_legal` que suas fontes referenciam. Quando ler:
# ao mexer em `dados/repositorio_dossie.py` ou no comando `motor/dossie.py`.
from datetime import date

from sqlalchemy.orm import Session

from aprovaos.dados.modelos import DispositivoLegal, DossieTopico, Topico
from aprovaos.dados.repositorio_dossie import proxima_versao, salvar_dossie
from aprovaos.dominio.dossie import ConteudoDossie, EntradaLogBusca, FonteDossie


def _topico(db: Session) -> Topico:
    topico = Topico(
        materia="direito-administrativo",
        nome="Improbidade administrativa",
        slug="dir-adm-06-improbidade-administrativa",
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

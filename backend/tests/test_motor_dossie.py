# O que é: testes do passo 3 da fundação jurídica — `motor.dossie.construir_dossie_improbidade`,
# a prova de conceito de ponta a ponta (tópico real → HTML real da Lei 8.429/1992 → dossiê
# gravado com fontes e lacunas). Sem rede, sem LLM. Quando ler: ao mudar a lista de dispositivos
# pedidos para o dossiê de improbidade, ou ao trocar de tópico-piloto.
from datetime import date

import pytest
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import DispositivoLegal, Topico
from aprovaos.dominio.erros import TopicoNaoEncontrado
from aprovaos.motor.dossie import SLUG_IMPROBIDADE, construir_dossie_improbidade


def _topico_improbidade(db: Session) -> Topico:
    topico = Topico(
        materia="direito-administrativo",
        nome="Improbidade administrativa",
        slug=SLUG_IMPROBIDADE,
    )
    db.add(topico)
    db.flush()
    return topico


def test_constroi_e_grava_o_dossie_com_fontes_reais(db: Session) -> None:
    """O dossiê de improbidade tem fontes com trecho real dos artigos que o extrator lê."""
    topico = _topico_improbidade(db)

    dossie, conteudo = construir_dossie_improbidade(db, hoje=date(2026, 9, 19))
    db.flush()

    assert dossie.topico_id == topico.id
    assert dossie.versao == 1

    citacoes_das_fontes = {fonte.citacao_canonica for fonte in conteudo.fontes}
    assert "Lei 8.429/1992 art. 1" in citacoes_das_fontes
    assert "Lei 8.429/1992 art. 1 § 2º" in citacoes_das_fontes  # definição de dolo
    assert "Lei 8.429/1992 art. 3" in citacoes_das_fontes
    assert "Lei 8.429/1992 art. 23" in citacoes_das_fontes  # prescrição
    assert len(conteudo.fontes) >= 6

    # o que ficou gravado em `dossie.fontes` (JSON) é o mesmo que `conteudo.fontes` produziu:
    assert {f["citacao_canonica"] for f in dossie.fontes} == citacoes_das_fontes
    assert db.query(DispositivoLegal).filter_by(norma="lei-8429-1992").count() == len(
        citacoes_das_fontes
    )


def test_dossie_declara_lacuna_para_artigos_com_estrutura_nao_tratada(db: Session) -> None:
    """Arts. 9º, 10 e 11 (títulos de Seção em Title Case) e 17 (§ com sufixo de letra) viram

    lacuna, com o trecho literal do erro — nunca conteúdo inventado no lugar deles.
    """
    _topico_improbidade(db)

    _dossie, conteudo = construir_dossie_improbidade(db, hoje=date(2026, 9, 19))

    dispositivos_das_lacunas = {lacuna.dispositivo for lacuna in conteudo.lacunas}
    assert "Lei 8.429/1992 art. 9" in dispositivos_das_lacunas
    assert "Lei 8.429/1992 art. 10" in dispositivos_das_lacunas
    assert "Lei 8.429/1992 art. 11" in dispositivos_das_lacunas
    assert "Lei 8.429/1992 art. 17" in dispositivos_das_lacunas
    lacuna_art9 = next(la for la in conteudo.lacunas if la.dispositivo == "Lei 8.429/1992 art. 9")
    assert "Seção II" in lacuna_art9.motivo


def test_topico_inexistente_levanta_erro_de_dominio(db: Session) -> None:
    """Sem o tópico `dir-adm-06-improbidade-administrativa` cadastrado, o comando para e avisa —

    nunca cria o tópico sozinho (isso é responsabilidade do parser de edital).
    """
    with pytest.raises(TopicoNaoEncontrado):
        construir_dossie_improbidade(db, hoje=date(2026, 9, 19))

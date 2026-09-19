# O que é: testes do passo 4 da fundação jurídica — `motor.ligar_por_topico.ligar_por_topico`:
# liga o dossiê mais recente de cada tópico às questões publicáveis desse tópico, via `Citacao`,
# mesmo quando a questão não cita nenhum artigo no enunciado. Sem rede, sem LLM. Quando ler: ao
# mudar a regra de quais questões ganham dispositivo por essa via, ou a numeração de `posicao`.
from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Citacao, DispositivoLegal, Questao, Topico
from aprovaos.dados.repositorio_citacao import registrar_citacao
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dados.repositorio_topico_relacao import criar_relacao_equivalente
from aprovaos.dominio.dossie import ConteudoDossie
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup
from aprovaos.motor.dossie import SLUG_IMPROBIDADE, construir_dossie_improbidade
from aprovaos.motor.ligar_por_topico import ligar_por_topico


def _topico_improbidade(db: Session) -> Topico:
    topico = Topico(
        materia="direito-administrativo",
        nome="Improbidade administrativa",
        slug=SLUG_IMPROBIDADE,
    )
    db.add(topico)
    db.flush()
    return topico


def _origem(numero_item: int) -> Origem:
    return Origem(
        banca="cebraspe",
        orgao="TJ-PA",
        cargo="Analista",
        ano=2025,
        numero_item=numero_item,
        tipo_caderno=None,
        url_prova="https://cdn.cebraspe.org.br/prova.pdf",
        documento_id=str(uuid4()),
    )


def _questao(numero_item: int, enunciado: str, topico_slug: str | None) -> QuestaoCurada:
    return QuestaoCurada(
        banca="cebraspe",
        numero_item=numero_item,
        comando=None,
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=enunciado,
        gabarito_preliminar=None,
        gabarito="C",
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=topico_slug,
        topico_confianca="alta" if topico_slug else "baixa",
        topico_evidencia="teste",
        origem=_origem(numero_item),
        hash_dedup=hash_dedup(enunciado),
    )


def _n_fontes_norma(conteudo: ConteudoDossie) -> int:
    """Só as fontes `tipo="norma"` viram `dispositivo_legal` — as de `tipo="sumula"` (fatia 4)

    não entram em `ligar_por_topico` ainda (plano §1.3).
    """
    return sum(1 for fonte in conteudo.fontes if fonte.tipo == "norma")


def test_questoes_do_topico_sem_nenhuma_citacao_ganham_os_dispositivos_do_dossie(
    db: Session,
) -> None:
    """As 2 questões do tópico (nenhuma citava artigo) ganham as fontes de norma do dossiê pelo
    tópico (as duas súmulas da receita de improbidade, fatia 4, não entram por essa via)."""
    _topico_improbidade(db)
    _dossie, conteudo = construir_dossie_improbidade(db, hoje=date(2026, 9, 19))
    db.flush()

    salvar_questoes(
        db,
        [
            _questao(
                1,
                "A legitimidade para a ação de improbidade é concorrente.",
                SLUG_IMPROBIDADE,
            ),
            _questao(
                2,
                "Particulares podem responder por ato de improbidade.",
                SLUG_IMPROBIDADE,
            ),
        ],
    )
    db.flush()

    relatorio = ligar_por_topico(db)

    n_norma = _n_fontes_norma(conteudo)
    assert relatorio.topicos_processados == 1
    assert relatorio.questoes_no_topico == 2
    assert relatorio.questoes_que_ganharam_dispositivo == 2
    assert relatorio.citacoes_novas == 2 * n_norma
    assert db.query(Citacao).count() == 2 * n_norma


def test_rodar_duas_vezes_e_idempotente(db: Session) -> None:
    """Rodar `ligar_por_topico` de novo sobre a mesma base não duplica citação nenhuma."""
    _topico_improbidade(db)
    construir_dossie_improbidade(db, hoje=date(2026, 9, 19))
    db.flush()
    salvar_questoes(db, [_questao(1, "Enunciado qualquer sobre improbidade.", SLUG_IMPROBIDADE)])
    db.flush()
    ligar_por_topico(db)
    db.flush()
    total_depois_da_primeira = db.query(Citacao).count()

    segunda = ligar_por_topico(db)
    db.flush()

    assert segunda.citacoes_novas == 0
    assert segunda.questoes_que_ganharam_dispositivo == 0
    assert db.query(Citacao).count() == total_depois_da_primeira


def test_questao_que_ja_tinha_citacao_por_texto_nao_conta_como_ganho_novo(db: Session) -> None:
    """Uma questão que já citava um artigo (via `motor.ancorar`) ganha as demais fontes do

    dossiê (posições continuam de onde a citação por texto parou), mas não conta como
    "ganhou dispositivo" — ela já tinha pelo menos um antes desta via.
    """
    _topico_improbidade(db)
    _dossie, conteudo = construir_dossie_improbidade(db, hoje=date(2026, 9, 19))
    db.flush()
    salvar_questoes(
        db, [_questao(1, "O art. 1º da Lei 8.429/1992 já foi citado por texto.", SLUG_IMPROBIDADE)]
    )
    db.flush()
    questao_gravada = db.query(Questao).one()
    dispositivo = (
        db.query(DispositivoLegal).filter_by(citacao_canonica="Lei 8.429/1992 art. 1").one()
    )
    registrar_citacao(
        db,
        conteudo_tipo="questao",
        conteudo_id=questao_gravada.id,
        dispositivo_id=dispositivo.id,
        posicao=1,
    )
    db.flush()

    relatorio = ligar_por_topico(db)

    assert relatorio.questoes_que_ganharam_dispositivo == 0
    # a fonte "art. 1" já existia (não duplica); as outras fontes de norma são novas:
    assert relatorio.citacoes_novas == _n_fontes_norma(conteudo) - 1


def test_questao_de_topico_equivalente_ganha_dispositivo_do_dossie(db: Session) -> None:
    """Fecha a P-52 (ADR-0041): uma questão de um tópico **sem** dossiê próprio, mas

    equivalente ao tópico do dossiê, ganha os dispositivos dele — o mesmo bug que deixava
    `ligar_por_topico` sem nenhuma ligação real entre o dossiê da fatia 4 e as questões da V3."""
    topico_ficticio = _topico_improbidade(db)
    _dossie, conteudo = construir_dossie_improbidade(db, hoje=date(2026, 9, 19))
    topico_real = Topico(
        materia="Noções de Direito Administrativo",
        nome="Improbidade administrativa",
        slug="noc-dir-adm-06-6-improbidade",
    )
    db.add(topico_real)
    db.flush()
    criar_relacao_equivalente(
        db,
        de_id=topico_ficticio.id,
        para_id=topico_real.id,
        evidencia="ambos citam a Lei nº 8.429/1992",
    )
    db.flush()

    salvar_questoes(
        db,
        [_questao(1, "Particulares podem responder por ato de improbidade.", topico_real.slug)],
    )
    db.flush()

    relatorio = ligar_por_topico(db)

    n_norma = _n_fontes_norma(conteudo)
    assert relatorio.questoes_no_topico == 1
    assert relatorio.questoes_que_ganharam_dispositivo == 1
    assert relatorio.citacoes_novas == n_norma
    questao_real = db.query(Questao).filter_by(topico_id=topico_real.id).one()
    assert db.query(Citacao).filter_by(conteudo_id=questao_real.id).count() == n_norma


def test_topico_sem_dossie_nao_gera_ligacao(db: Session) -> None:
    """Um tópico sem `dossie_topico` nenhum não é tocado — `ligar_por_topico` só usa dossiês

    já construídos (o comando de construção é sempre o passo anterior).
    """
    topico_sem_dossie = Topico(materia="x", nome="y", slug="materia-99-sem-dossie")
    db.add(topico_sem_dossie)
    db.flush()
    salvar_questoes(db, [_questao(1, "Enunciado qualquer.", "materia-99-sem-dossie")])
    db.flush()

    relatorio = ligar_por_topico(db)

    assert relatorio.topicos_processados == 0
    assert relatorio.citacoes_novas == 0

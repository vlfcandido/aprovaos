# O que é: testes do passo 2 da fundação jurídica — `motor.ancorar.ancorar_citacoes`, contra as
# fixtures reais de `knowledge/fixtures/juridico/` (sem rede, sem IA). Quando ler: ao mudar a
# classificação por questão ou a resolução offline do dispositivo.
from uuid import uuid4

from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Citacao, DispositivoLegal
from aprovaos.dados.repositorio_questao import salvar_questoes
from aprovaos.dominio.questao import Origem, QuestaoCurada, RegraProva, hash_dedup
from aprovaos.motor.ancorar import ancorar_citacoes


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


def _questao(numero_item: int, enunciado: str, comando: str | None = None) -> QuestaoCurada:
    return QuestaoCurada(
        banca="cebraspe",
        numero_item=numero_item,
        comando=comando,
        texto_apoio=None,
        texto_apoio_itens=[],
        enunciado=enunciado,
        gabarito_preliminar=None,
        gabarito="C",
        gabarito_status="definitivo",
        publicavel=True,
        motivo_nao_publicavel=None,
        regra_prova=RegraProva(anula_por_erro=True, fonte="instrução do caderno"),
        topico_slug=None,
        topico_confianca="baixa",
        topico_evidencia="sem correspondência no vocabulário",
        origem=_origem(numero_item),
        hash_dedup=hash_dedup(enunciado),
    )


def test_questao_com_artigo_da_cf_e_resolvida_e_grava_dispositivo_e_citacao(db: Session) -> None:
    """ "art. 37 da CF" resolve para o caput real do art. 37 — dispositivo e citação gravados."""
    salvar_questoes(
        db,
        [_questao(1, "O art. 37 da CF traz os princípios da administração pública.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.total == 1
    assert relatorio.resolvidas == 1
    assert relatorio.sem_citacao == 0
    assert relatorio.citacoes_novas == 1
    assert relatorio.dispositivos_novos == 1

    dispositivo = db.query(DispositivoLegal).one()
    assert dispositivo.norma == "cf-1988"
    assert dispositivo.artigo == "37"
    assert dispositivo.inciso is None
    assert dispositivo.texto.startswith("Art. 37. A administração pública")
    assert dispositivo.vigente is True
    citacao = db.query(Citacao).one()
    assert citacao.conteudo_tipo == "questao"
    assert citacao.dispositivo_id == dispositivo.id


def test_questao_com_inciso_da_lei_14133_resolve_o_inciso_exato(db: Session) -> None:
    """ "inciso IX do art. 6º da Lei 14.133/2021" resolve para o inciso, não para o caput."""
    salvar_questoes(
        db,
        [
            _questao(
                1,
                "O inciso IX do art. 6º da Lei 14.133/2021 define licitante.",
            )
        ],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 1
    dispositivo = db.query(DispositivoLegal).one()
    assert dispositivo.norma == "lei-14133-2021"
    assert dispositivo.artigo == "6"
    assert dispositivo.inciso == "IX"
    assert dispositivo.texto.startswith("IX - licitante:")


def test_norma_fora_do_catalogo_e_lacuna_e_entra_no_ranking(db: Session) -> None:
    """CLT não está no catálogo — a questão cai em `lacuna_norma`, sem gravar nada."""
    salvar_questoes(
        db,
        [_questao(1, "A multa prevista no art. 477 da CLT não é aplicável a ente público.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 0
    assert relatorio.lacuna_norma == 1
    assert relatorio.normas_fora_do_catalogo == {"clt": 1}
    assert db.query(DispositivoLegal).count() == 0


def test_norma_do_catalogo_sem_artigo_nao_resolve_e_nao_e_lacuna(db: Session) -> None:
    """ "Lei nº 14.133/2021" sozinha (sem artigo) não é lacuna — a norma já está no catálogo."""
    salvar_questoes(
        db,
        [_questao(1, "Os limites estabelecidos na Lei n.º 14.133/2021 podem ser ultrapassados.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 0
    assert relatorio.lacuna_norma == 0
    assert relatorio.catalogada_nao_resolvida == 1
    assert relatorio.normas_fora_do_catalogo == {}


def test_questao_sem_nenhuma_referencia_e_sem_citacao(db: Session) -> None:
    """O caso mais comum na base real: nenhuma referência reconhecível."""
    salvar_questoes(
        db,
        [_questao(1, "O poder da administração pública de rever os próprios atos é absoluto.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.sem_citacao == 1
    assert relatorio.resolvidas == 0
    assert relatorio.lacuna_norma == 0
    assert relatorio.catalogada_nao_resolvida == 0


def test_dez_questoes_com_o_mesmo_artigo_geram_um_dispositivo_e_dez_citacoes(db: Session) -> None:
    """O mesmo art. 37 da CF citado por dez questões diferentes não duplica `dispositivo_legal`."""
    questoes = [
        _questao(i, f"O art. 37 da CF é o princípio nº {i} desta questão.") for i in range(10)
    ]
    salvar_questoes(db, questoes)
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 10
    assert relatorio.citacoes_novas == 10
    assert relatorio.dispositivos_novos == 1
    assert db.query(DispositivoLegal).count() == 1
    assert db.query(Citacao).count() == 10


def test_rodar_duas_vezes_e_idempotente(db: Session) -> None:
    """Rodar `ancorar_citacoes` de novo sobre a mesma base não duplica nada e soma zero de novo."""
    salvar_questoes(db, [_questao(1, "O art. 37 da CF traz os princípios.")])
    db.flush()
    ancorar_citacoes(db)
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.citacoes_novas == 0
    assert relatorio.dispositivos_novos == 0
    assert db.query(DispositivoLegal).count() == 1
    assert db.query(Citacao).count() == 1


def test_comando_le_enunciado_comando_e_texto_apoio_juntos(db: Session) -> None:
    """A referência pode estar no `comando` da questão, não só no `enunciado`."""
    salvar_questoes(
        db,
        [_questao(1, "Julgue o item a seguir.", comando="Considerando o art. 37 da CF, julgue:")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 1

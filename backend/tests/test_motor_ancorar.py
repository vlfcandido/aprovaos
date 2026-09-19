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
    """Uma norma que nenhum catálogo cobre ainda (ex.: Lei 8.038/1990) cai em `lacuna_norma`."""
    salvar_questoes(
        db,
        [_questao(1, "O art. 12 da Lei n.º 8.038/1990 dispõe sobre o agravo regimental.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 0
    assert relatorio.lacuna_norma == 1
    assert relatorio.normas_fora_do_catalogo == {"lei-8038-1990": 1}
    assert db.query(DispositivoLegal).count() == 0


def test_clt_esta_no_catalogo_mas_art_477_nao_resolve_por_estrutura_nao_tratada(
    db: Session,
) -> None:
    """CLT entrou no catálogo (ampliação 19/09/2026), mas o art. 477 tem uma anotação

    ("Vigência\\nencerrada", sem parênteses) que `dominio.legislacao.extrair_artigo` não trata
    (ver `knowledge/fixtures/juridico/LEIA-ME.md`, achado 2) — a questão cai em
    `catalogada_nao_resolvida`, não em `lacuna_norma` (a norma já está no catálogo), e nenhum
    dispositivo é gravado (a falha é engolida por `_resolver_trecho`, nunca trava o comando).
    """
    salvar_questoes(
        db,
        [_questao(1, "A multa prevista no art. 477 da CLT não é aplicável a ente público.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 0
    assert relatorio.lacuna_norma == 0
    assert relatorio.catalogada_nao_resolvida == 1
    assert relatorio.normas_fora_do_catalogo == {}
    assert db.query(DispositivoLegal).count() == 0


def test_clt_resolve_um_artigo_sem_a_anotacao_problematica(db: Session) -> None:
    """O art. 3º da CLT (definição de empregado) não tem a anotação "Vigência\\nencerrada" do
    art. 477 — resolve normalmente, provando que a norma em si está bem catalogada.
    """
    salvar_questoes(
        db,
        [_questao(1, "O art. 3º da CLT define quem é empregado.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 1
    dispositivo = db.query(DispositivoLegal).one()
    assert dispositivo.norma == "clt"
    assert dispositivo.artigo == "3"
    assert dispositivo.texto.startswith("Art. 3º - Considera-se empregado")


def test_lei_8429_resolve_o_paragrafo_1_do_art_1_com_a_definicao_de_dolo(db: Session) -> None:
    """§ 1º do art. 1º da Lei 8.429/1992 (redação da Lei 14.230/2021) resolve — é o dispositivo

    que o dossiê de improbidade usa (passo 3 desta rodada).
    """
    salvar_questoes(
        db,
        [_questao(1, "O § 1º do art. 1º da Lei n.º 8.429/1992 exige dolo para configurar ato.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 1
    dispositivo = db.query(DispositivoLegal).one()
    assert dispositivo.norma == "lei-8429-1992"
    assert dispositivo.artigo == "1"
    assert dispositivo.paragrafo == "1"
    assert "condutas dolosas" in dispositivo.texto


def test_lei_6404_resolve_o_art_4_sem_rubrica_marginal_no_meio(db: Session) -> None:
    """A maioria dos artigos da Lei 6.404/1976 tem uma rubrica marginal em Title Case (ex.:

    "Objeto Social", "Denominação") entre o artigo anterior e o seu próprio caput — estrutura
    que o extrator não trata (`LEIA-ME.md`, achado 3). O art. 4º é um dos poucos sem essa
    rubrica logo antes, e resolve normalmente.
    """
    salvar_questoes(
        db,
        [_questao(1, "O art. 4º da Lei n.º 6.404/1976 distingue companhia aberta de fechada.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 1
    dispositivo = db.query(DispositivoLegal).one()
    assert dispositivo.norma == "lei-6404-1976"
    assert dispositivo.artigo == "4"
    assert "companhia é aberta ou fechada" in dispositivo.texto


def test_lei_11101_resolve_o_art_1(db: Session) -> None:
    """Art. 1º da Lei 11.101/2005 (objeto da lei) resolve sem nenhuma estrutura problemática."""
    salvar_questoes(
        db,
        [_questao(1, "O art. 1º da Lei n.º 11.101/2005 disciplina a recuperação judicial.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 1
    dispositivo = db.query(DispositivoLegal).one()
    assert dispositivo.norma == "lei-11101-2005"
    assert dispositivo.artigo == "1"


def test_lei_11340_resolve_o_inciso_i_do_art_5(db: Session) -> None:
    """Art. 5º, inciso I, da Lei 11.340/2006 (Maria da Penha) resolve — a fixture vinha em

    UTF-16 com BOM (achado 1 do `LEIA-ME.md`); sem a detecção de BOM em `decodificar_html`,
    nenhum artigo desta norma seria encontrado.
    """
    salvar_questoes(
        db,
        [_questao(1, "O inciso I do art. 5º da Lei n.º 11.340/2006 trata do âmbito doméstico.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 1
    dispositivo = db.query(DispositivoLegal).one()
    assert dispositivo.norma == "lei-11340-2006"
    assert dispositivo.artigo == "5"
    assert dispositivo.inciso == "I"


def test_lei_6830_resolve_o_art_1(db: Session) -> None:
    """Art. 1º da Lei 6.830/1980 (execução fiscal) resolve sem nenhuma estrutura problemática."""
    salvar_questoes(
        db,
        [_questao(1, "O art. 1º da Lei n.º 6.830/1980 rege a execução da Dívida Ativa.")],
    )
    db.flush()

    relatorio = ancorar_citacoes(db)

    assert relatorio.resolvidas == 1
    dispositivo = db.query(DispositivoLegal).one()
    assert dispositivo.norma == "lei-6830-1980"
    assert dispositivo.artigo == "1"


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

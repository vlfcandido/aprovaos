# O que é: testes de `dados/repositorio_perfil.py` (salvar rotina, versão incremental) e da
# atualização de `repositorio_edital.concurso_principal` para preferir `perfil_estudo` (P-23).
# Quando ler: ao mexer no salvamento da rotina ou em quem decide o concurso principal.
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from aprovaos.agentes.analista_de_edital import ResultadoDna
from aprovaos.dados.modelos import Usuario
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_edital import DadosDocumento, concurso_principal, registrar_edital
from aprovaos.dados.repositorio_perfil import (
    alternar_acompanhamento,
    marcar_principal,
    perfil_atual,
    salvar_perfil,
)
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.dna import montar_dna_por_regras
from aprovaos.dominio.edital import MateriaExtraida, extrair_conteudo_programatico
from aprovaos.dominio.erros import SemConcursoPrincipal
from aprovaos.dominio.rotina import DIAS_SEMANA, DadosRotina

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"


def _usuario(db: Session, email: str) -> Usuario:
    return criar_conta(db, DadosCadastro(email=email, senha="12345678"))


def _rotina(concurso_principal_id: UUID | None = None) -> DadosRotina:
    return DadosRotina(
        horas_por_dia_semana={dia: 2.0 for dia in DIAS_SEMANA},
        horario_preferido="manha",
        energia_tipica="media",
        data_alvo=None,
        concurso_principal_id=concurso_principal_id,
    )


def test_salvar_perfil_cria_a_primeira_versao(db: Session) -> None:
    usuario = _usuario(db, "a@exemplo.com")
    perfil = salvar_perfil(db, usuario, _rotina())
    db.commit()
    assert perfil.versao == 1
    atual = perfil_atual(db, usuario.id)
    assert atual is not None
    assert atual.id == perfil.id


def test_salvar_perfil_incrementa_versao_sem_apagar_a_anterior(db: Session) -> None:
    usuario = _usuario(db, "b@exemplo.com")
    primeiro = salvar_perfil(db, usuario, _rotina())
    db.commit()
    segundo = salvar_perfil(db, usuario, _rotina())
    db.commit()
    assert segundo.versao == 2
    assert primeiro.id != segundo.id
    atual = perfil_atual(db, usuario.id)
    assert atual is not None
    assert atual.id == segundo.id


def test_salvar_perfil_grava_consentimento_no_usuario(db: Session) -> None:
    usuario = _usuario(db, "c@exemplo.com")
    assert usuario.consentimento_dados_rotina is False
    salvar_perfil(db, usuario, _rotina())
    db.commit()
    assert usuario.consentimento_dados_rotina is True
    assert usuario.consentimento_dados_rotina_em is not None
    assert usuario.consentimento_dados_rotina_versao == "v1"


def test_perfil_atual_sem_nenhum_ainda_e_none(db: Session) -> None:
    usuario = _usuario(db, "d@exemplo.com")
    assert perfil_atual(db, usuario.id) is None


@pytest.fixture
def materias() -> tuple[str, list[MateriaExtraida]]:
    texto = FIXTURE_MD.read_text(encoding="utf-8")
    return texto, extrair_conteudo_programatico(texto)


def test_concurso_principal_prefere_o_perfil_ao_ultimo_subido(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    texto, lista_materias = materias
    usuario = _usuario(db, "e@exemplo.com")
    resultado = ResultadoDna(
        dna=montar_dna_por_regras(texto, lista_materias), origem="regras", motivo_fallback="x"
    )
    documento = DadosDocumento(
        hash="aa" * 32, caminho_relativo="a.pdf", nome_original="a.pdf", tamanho=1, paginas=1
    )
    primeiro = registrar_edital(db, usuario.tenant_id, resultado, lista_materias, documento)
    db.commit()
    documento2 = DadosDocumento(
        hash="bb" * 32, caminho_relativo="b.pdf", nome_original="b.pdf", tamanho=1, paginas=1
    )
    segundo = registrar_edital(db, usuario.tenant_id, resultado, lista_materias, documento2)
    db.commit()

    # Sem perfil ainda: heurística de "o último subido" (premissa A da V2).
    principal = concurso_principal(db, usuario.tenant_id)
    assert principal is not None
    assert principal.id == segundo.id

    # Com perfil escolhendo o primeiro: a escolha dela vence.
    salvar_perfil(db, usuario, _rotina(concurso_principal_id=primeiro.id))
    db.commit()
    principal = concurso_principal(db, usuario.tenant_id)
    assert principal is not None
    assert principal.id == primeiro.id


def test_concurso_principal_ignora_perfil_apontando_para_outro_tenant(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    texto, lista_materias = materias
    dono = _usuario(db, "f@exemplo.com")
    intruso = _usuario(db, "g@exemplo.com")
    resultado = ResultadoDna(
        dna=montar_dna_por_regras(texto, lista_materias), origem="regras", motivo_fallback="x"
    )
    documento = DadosDocumento(
        hash="cc" * 32, caminho_relativo="c.pdf", nome_original="c.pdf", tamanho=1, paginas=1
    )
    concurso_do_dono = registrar_edital(db, dono.tenant_id, resultado, lista_materias, documento)
    db.commit()
    # O perfil do intruso aponta para um concurso que não é do tenant dele (defensivo).
    salvar_perfil(db, intruso, _rotina(concurso_principal_id=concurso_do_dono.id))
    db.commit()
    assert concurso_principal(db, intruso.tenant_id) is None


def test_marcar_principal_sem_perfil_ainda_levanta_sem_concurso_principal(db: Session) -> None:
    usuario = _usuario(db, "h@exemplo.com")
    with pytest.raises(SemConcursoPrincipal):
        marcar_principal(db, usuario, UUID(int=0))


def test_marcar_principal_grava_nova_versao_preservando_a_rotina(db: Session) -> None:
    usuario = _usuario(db, "i@exemplo.com")
    salvar_perfil(db, usuario, _rotina())
    db.commit()

    novo_principal = UUID(int=42)
    perfil = marcar_principal(db, usuario, novo_principal)
    db.commit()

    assert perfil.versao == 2
    assert perfil.concurso_principal_id == novo_principal
    assert perfil.horario_preferido == "manha"
    assert perfil.energia_tipica == "media"


def test_alternar_acompanhamento_sem_perfil_ainda_levanta_sem_concurso_principal(
    db: Session,
) -> None:
    usuario = _usuario(db, "j@exemplo.com")
    with pytest.raises(SemConcursoPrincipal):
        alternar_acompanhamento(db, usuario, "AGEPAR_PR_26")


def test_alternar_acompanhamento_adiciona_e_depois_remove(db: Session) -> None:
    usuario = _usuario(db, "k@exemplo.com")
    salvar_perfil(db, usuario, _rotina())
    db.commit()

    adicionado = alternar_acompanhamento(db, usuario, "AGEPAR_PR_26")
    db.commit()
    assert adicionado.concursos_acompanhados == ["AGEPAR_PR_26"]
    assert adicionado.versao == 2

    removido = alternar_acompanhamento(db, usuario, "AGEPAR_PR_26")
    db.commit()
    assert removido.concursos_acompanhados == []
    assert removido.versao == 3


def test_alternar_acompanhamento_preserva_o_principal_ja_escolhido(db: Session) -> None:
    usuario = _usuario(db, "l@exemplo.com")
    salvar_perfil(db, usuario, _rotina())
    db.commit()
    principal = UUID(int=7)
    marcar_principal(db, usuario, principal)
    db.commit()

    perfil = alternar_acompanhamento(db, usuario, "AGEPAR_PR_26")
    db.commit()

    assert perfil.concurso_principal_id == principal
    assert perfil.concursos_acompanhados == ["AGEPAR_PR_26"]

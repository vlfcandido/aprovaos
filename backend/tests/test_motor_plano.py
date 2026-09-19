# O que é: testes de `motor/plano.py` — o job noturno gera plano por usuário ativo, idempotente,
# e a falha de um usuário (erro inesperado ou onboarding incompleto) não derruba o lote (CA
# explícito do PRD F3.1). Quando ler: ao mexer no comando ou no relatório do lote.
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

import aprovaos.motor.plano as motor_plano
from aprovaos.agentes.analista_de_edital import ResultadoDna
from aprovaos.dados.modelos import PlanoDia, Usuario
from aprovaos.dados.repositorio_conta import criar_conta
from aprovaos.dados.repositorio_edital import DadosDocumento, registrar_edital
from aprovaos.dados.repositorio_perfil import salvar_perfil
from aprovaos.dados.repositorio_plano import (
    gerar_ou_obter_plano_noturno as _gerar_ou_obter_plano_noturno_original,
)
from aprovaos.dominio.conta import DadosCadastro
from aprovaos.dominio.dna import montar_dna_por_regras
from aprovaos.dominio.edital import MateriaExtraida, extrair_conteudo_programatico
from aprovaos.dominio.rotina import DIAS_SEMANA, DadosRotina
from aprovaos.motor.plano import gerar_plano_da_noite

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MD = RAIZ / "docs/evidencias/2026-09-17-fase4-skills/fixtures/edital-assessor-gabinete.md"

UMA_TERCA = date(2026, 9, 22)


def _usuario(db: Session, email: str) -> Usuario:
    return criar_conta(db, DadosCadastro(email=email, senha="12345678"))


def _rotina(concurso_principal_id: UUID | None) -> DadosRotina:
    return DadosRotina(
        horas_por_dia_semana=dict.fromkeys(DIAS_SEMANA, 1.0),
        horario_preferido="manha",
        energia_tipica="media",
        data_alvo=None,
        concurso_principal_id=concurso_principal_id,
    )


@pytest.fixture
def materias() -> tuple[str, list[MateriaExtraida]]:
    texto = FIXTURE_MD.read_text(encoding="utf-8")
    return texto, extrair_conteudo_programatico(texto)


def _com_edital_e_rotina(
    db: Session, usuario: Usuario, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    texto, lista_materias = materias
    resultado = ResultadoDna(
        dna=montar_dna_por_regras(texto, lista_materias), origem="regras", motivo_fallback="x"
    )
    documento = DadosDocumento(
        hash=usuario.email.ljust(64, "0")[:64],
        caminho_relativo="a.pdf",
        nome_original="a.pdf",
        tamanho=1,
        paginas=1,
    )
    concurso = registrar_edital(db, usuario.tenant_id, resultado, lista_materias, documento)
    db.commit()
    salvar_perfil(db, usuario, _rotina(concurso.id))
    db.commit()


def test_gera_plano_para_usuario_com_rotina_e_edital(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "pronta@exemplo.com")
    _com_edital_e_rotina(db, usuario, materias)

    relatorio = gerar_plano_da_noite(db, UMA_TERCA)

    assert relatorio.gerados == 1
    assert relatorio.erros == 0
    assert relatorio.linhas[0].status == "gerado"


def test_rodar_duas_vezes_no_mesmo_dia_e_idempotente(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    usuario = _usuario(db, "duasvezes@exemplo.com")
    _com_edital_e_rotina(db, usuario, materias)

    primeiro = gerar_plano_da_noite(db, UMA_TERCA)
    segundo = gerar_plano_da_noite(db, UMA_TERCA)

    assert primeiro.linhas[0].status == "gerado"
    assert segundo.linhas[0].status == "ja_existia"


def test_usuario_sem_edital_nao_derruba_o_lote(
    db: Session, materias: tuple[str, list[MateriaExtraida]]
) -> None:
    sem_edital = _usuario(db, "so-rotina@exemplo.com")
    salvar_perfil(db, sem_edital, _rotina(None))
    db.commit()
    com_tudo = _usuario(db, "com-tudo@exemplo.com")
    _com_edital_e_rotina(db, com_tudo, materias)

    relatorio = gerar_plano_da_noite(db, UMA_TERCA)

    status_por_email = {linha.usuario_email: linha.status for linha in relatorio.linhas}
    assert status_por_email["so-rotina@exemplo.com"] == "sem_rotina_ou_concurso"
    assert status_por_email["com-tudo@exemplo.com"] == "gerado"


def test_erro_inesperado_de_um_usuario_nao_impede_os_outros(
    db: Session, materias: tuple[str, list[MateriaExtraida]], monkeypatch: pytest.MonkeyPatch
) -> None:
    quebrada = _usuario(db, "quebrada@exemplo.com")
    _com_edital_e_rotina(db, quebrada, materias)
    ok = _usuario(db, "ok@exemplo.com")
    _com_edital_e_rotina(db, ok, materias)

    def _explode_para_quebrada(
        db_: Session, usuario: Usuario, dia: date, agora: object = None
    ) -> PlanoDia:
        if usuario.email == "quebrada@exemplo.com":
            raise RuntimeError("falha simulada de infraestrutura")
        return _gerar_ou_obter_plano_noturno_original(db_, usuario, dia)

    monkeypatch.setattr(motor_plano, "gerar_ou_obter_plano_noturno", _explode_para_quebrada)

    relatorio = gerar_plano_da_noite(db, UMA_TERCA)

    status_por_email = {linha.usuario_email: linha.status for linha in relatorio.linhas}
    assert status_por_email["quebrada@exemplo.com"] == "erro"
    assert (
        "RuntimeError"
        in relatorio.linhas[
            [linha.usuario_email for linha in relatorio.linhas].index("quebrada@exemplo.com")
        ].motivo
    )
    assert status_por_email["ok@exemplo.com"] == "gerado"


def test_dry_run_nao_grava_nada(db: Session, materias: tuple[str, list[MateriaExtraida]]) -> None:
    usuario = _usuario(db, "dryrun@exemplo.com")
    _com_edital_e_rotina(db, usuario, materias)

    relatorio = gerar_plano_da_noite(db, UMA_TERCA, commit=False)
    assert relatorio.linhas[0].status == "gerado"

    # Sem commit nenhum: rodar de novo "gera" de novo (nada persistiu da primeira vez).
    relatorio_2 = gerar_plano_da_noite(db, UMA_TERCA, commit=False)
    assert relatorio_2.linhas[0].status == "gerado"

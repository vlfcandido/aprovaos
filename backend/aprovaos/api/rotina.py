"""Rota HTML de rotina (`GET/POST /rotina`, fatia 7, F2.2): horas, horário, energia, data-alvo.

O que é: `GET /rotina` mostra o formulário pré-preenchido com a última versão salva (ou valores
neutros na primeira vez); `POST /rotina` valida (`dominio.rotina.DadosRotina`), exige o
consentimento de dados de rotina/energia (R-01, LGPD — energia é dado sensível por cautela) antes
de gravar, confere que o `concurso_principal_id` escolhido pertence ao tenant do usuário (P-23) e
grava uma nova versão de `perfil_estudo`. Erros esperados voltam na mesma página com mensagem e
status 200 (mesmo padrão de `api/conta.py`/`api/editais.py`).

Corrigido em 19/09/2026 (I8): a caixa de consentimento **nunca nasce marcada**, nem para quem já
autorizou antes — caixa pré-marcada não é manifestação inequívoca (LGPD) e é exatamente o
"gruda silenciosamente" que o plano da fatia 7 já rejeitava. Quem já autorizou vê, em texto ao
lado da caixa desmarcada, a data e a versão do aceite anterior (`usuario
.consentimento_dados_rotina_em`/`_versao`, já gravados por `repositorio_perfil.salvar_perfil`).

Quando ler: ao mexer no formulário de rotina ou na regra de consentimento.
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.api.sessao import exigir_usuario
from aprovaos.api.templates import renderizar, responder_redirecionamento
from aprovaos.dados.modelos import Concurso, PerfilEstudo, Usuario
from aprovaos.dados.repositorio_edital import listar_concursos_do_tenant
from aprovaos.dados.repositorio_perfil import perfil_atual, salvar_perfil
from aprovaos.dominio.rotina import DIAS_SEMANA, ENERGIAS_VALIDAS, OPCOES_HORARIO, DadosRotina

router = APIRouter(include_in_schema=False)

MENSAGEM_CONSENTIMENTO_OBRIGATORIO = (
    "Marque o consentimento sobre dados de rotina (energia) para salvar — é dado sensível por "
    "cautela (LGPD); sem ele, o AprovaOS não grava sua energia típica."
)
MENSAGEM_CONCURSO_INVALIDO = "Concurso principal inválido — escolha um dos seus concursos."
MENSAGEM_DATA_INVALIDA = "Data-alvo inválida."

#: Rótulo de energia para o formulário. O valor do domínio (`ENERGIAS_VALIDAS`) é identificador,
#: não texto de tela: passado por `capitalize` no template ele saía "Media", sem acento (passada
#: visual de 23/09/2026).
ROTULO_ENERGIA: dict[str, str] = {"alta": "Alta", "media": "Média", "baixa": "Baixa"}

#: Rótulo do dia para o formulário — mesma ordem de `DIAS_SEMANA`.
ROTULO_DIA: dict[str, str] = {
    "seg": "Segunda",
    "ter": "Terça",
    "qua": "Quarta",
    "qui": "Quinta",
    "sex": "Sexta",
    "sab": "Sábado",
    "dom": "Domingo",
}


def _concursos_para_formulario(
    db: Session, usuario: Usuario, selecionado_id: UUID | None
) -> list[dict[str, object]]:
    """As opções do `<select>` de concurso principal, com a atual marcada."""
    return [
        {"id": str(c.id), "rotulo": f"{c.cargo} — {c.orgao}", "selecionado": c.id == selecionado_id}
        for c in listar_concursos_do_tenant(db, usuario.tenant_id)
    ]


def _dias_para_formulario(horas: dict[str, float]) -> list[dict[str, object]]:
    """As sete linhas do formulário de horas, na ordem de `DIAS_SEMANA`."""
    return [
        {"chave": dia, "rotulo": ROTULO_DIA[dia], "horas": horas.get(dia, 0.0)}
        for dia in DIAS_SEMANA
    ]


def _contexto_formulario(
    db: Session,
    usuario: Usuario,
    *,
    erros: list[str],
    horas: dict[str, float],
    horario_preferido: str,
    energia_tipica: str,
    data_alvo: str,
    concurso_principal_id: UUID | None,
) -> dict[str, object]:
    # Corrigido em 19/09/2026 (I8): a caixa de consentimento nunca nasce marcada — mesmo quando
    # já houve aceite antes, marcar a caixa de novo é o "gruda silenciosamente" que o próprio
    # plano da fatia 7 rejeitava, e caixa pré-marcada não é manifestação inequívoca (LGPD). Quem
    # já autorizou vê a data/versão do aceite anterior em texto, ao lado da caixa desmarcada.
    consentimento_anterior_em = (
        usuario.consentimento_dados_rotina_em.strftime("%d/%m/%Y")
        if usuario.consentimento_dados_rotina and usuario.consentimento_dados_rotina_em
        else ""
    )
    return {
        "erros": erros,
        "dias": _dias_para_formulario(horas),
        "opcoes_horario": OPCOES_HORARIO,
        "horario_preferido": horario_preferido,
        "opcoes_energia": [(valor, ROTULO_ENERGIA[valor]) for valor in ENERGIAS_VALIDAS],
        "energia_tipica": energia_tipica,
        "data_alvo": data_alvo,
        "concursos": _concursos_para_formulario(db, usuario, concurso_principal_id),
        "consentimento_anterior_em": consentimento_anterior_em,
        "consentimento_anterior_versao": usuario.consentimento_dados_rotina_versao,
    }


def _horas_do_perfil(perfil: PerfilEstudo | None) -> dict[str, float]:
    if perfil is None:
        return dict.fromkeys(DIAS_SEMANA, 0.0)
    return {dia: float(perfil.horas_por_dia_semana.get(dia, 0.0)) for dia in DIAS_SEMANA}


@router.get("/rotina")
def rotina(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
) -> Response:
    """Formulário de rotina, pré-preenchido com a última versão salva.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).

    Returns:
        O HTML de `rotina/formulario.html` sem erros.
    """
    perfil = perfil_atual(db, usuario.id)
    contexto = _contexto_formulario(
        db,
        usuario,
        erros=[],
        horas=_horas_do_perfil(perfil),
        horario_preferido=perfil.horario_preferido if perfil else "manha",
        energia_tipica=perfil.energia_tipica if perfil else "media",
        data_alvo=perfil.data_alvo.isoformat() if perfil and perfil.data_alvo else "",
        concurso_principal_id=perfil.concurso_principal_id if perfil else None,
    )
    return renderizar(request, "rotina/formulario.html", contexto, usuario)


@router.post("/rotina")
def salvar_rotina(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    hora_seg: Annotated[float, Form()],
    hora_ter: Annotated[float, Form()],
    hora_qua: Annotated[float, Form()],
    hora_qui: Annotated[float, Form()],
    hora_sex: Annotated[float, Form()],
    hora_sab: Annotated[float, Form()],
    hora_dom: Annotated[float, Form()],
    horario_preferido: Annotated[str, Form()],
    energia_tipica: Annotated[str, Form()],
    data_alvo: Annotated[str, Form()] = "",
    concurso_principal_id: Annotated[str, Form()] = "",
    consentimento: Annotated[str | None, Form()] = None,
) -> Response:
    """Valida e grava uma nova versão de `perfil_estudo`.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        hora_seg: horas de estudo na segunda-feira.
        hora_ter: horas de estudo na terça-feira.
        hora_qua: horas de estudo na quarta-feira.
        hora_qui: horas de estudo na quinta-feira.
        hora_sex: horas de estudo na sexta-feira.
        hora_sab: horas de estudo no sábado.
        hora_dom: horas de estudo no domingo.
        horario_preferido: um de `OPCOES_HORARIO`.
        energia_tipica: um de `ENERGIAS_VALIDAS`.
        data_alvo: `"AAAA-MM-DD"` do `<input type="date">`, ou `""`.
        concurso_principal_id: `id` de um concurso do próprio tenant, ou `""`.
        consentimento: `"on"` quando o checkbox de consentimento vem marcado; `None` sem marcar.

    Returns:
        Redirecionamento para `/rotina` no sucesso; a mesma página com a mensagem (200) em erro
        esperado (sem consentimento, concurso de outro tenant, data ou campos inválidos).
    """
    horas = {
        "seg": hora_seg,
        "ter": hora_ter,
        "qua": hora_qua,
        "qui": hora_qui,
        "sex": hora_sex,
        "sab": hora_sab,
        "dom": hora_dom,
    }
    erros: list[str] = []

    concurso_id: UUID | None = None
    if concurso_principal_id:
        try:
            concurso_id = UUID(concurso_principal_id)
        except ValueError:
            erros.append(MENSAGEM_CONCURSO_INVALIDO)
        else:
            concurso = db.get(Concurso, concurso_id)
            if concurso is None or concurso.tenant_id != usuario.tenant_id:
                erros.append(MENSAGEM_CONCURSO_INVALIDO)
                concurso_id = None

    data_alvo_valida: date | None = None
    if data_alvo:
        try:
            data_alvo_valida = date.fromisoformat(data_alvo)
        except ValueError:
            erros.append(MENSAGEM_DATA_INVALIDA)

    if consentimento != "on":
        erros.append(MENSAGEM_CONSENTIMENTO_OBRIGATORIO)

    if not erros:
        try:
            dados = DadosRotina(
                horas_por_dia_semana=horas,
                horario_preferido=horario_preferido,
                energia_tipica=energia_tipica,
                data_alvo=data_alvo_valida,
                concurso_principal_id=concurso_id,
            )
        except ValidationError as erro:
            erros = [str(e["msg"]) for e in erro.errors()]
        else:
            salvar_perfil(db, usuario, dados)
            db.commit()
            return responder_redirecionamento(request, "/rotina")

    contexto = _contexto_formulario(
        db,
        usuario,
        erros=erros,
        horas=horas,
        horario_preferido=horario_preferido,
        energia_tipica=energia_tipica,
        data_alvo=data_alvo,
        concurso_principal_id=concurso_id,
    )
    return renderizar(request, "rotina/formulario.html", contexto, usuario)

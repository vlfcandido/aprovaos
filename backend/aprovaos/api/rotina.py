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
from aprovaos.dominio.rotina import (
    DIAS_FIM_DE_SEMANA,
    DIAS_SEMANA,
    DIAS_UTEIS,
    ENERGIAS_VALIDAS,
    OPCOES_HORARIO,
    PRESET_MANUAL,
    PRESETS_HORAS,
    DadosRotina,
    horas_a_partir_das_escolhas,
    preset_das_horas,
    total_semanal,
)

router = APIRouter(include_in_schema=False)

MENSAGEM_CONSENTIMENTO_OBRIGATORIO = (
    "Marque o consentimento sobre dados de rotina (energia) para salvar — é dado sensível por "
    "cautela (LGPD); sem ele, o AprovaOS não grava sua energia típica."
)
MENSAGEM_CONCURSO_INVALIDO = "Concurso principal inválido — escolha um dos seus concursos."
MENSAGEM_DATA_INVALIDA = "Data-alvo inválida."
MENSAGEM_HORAS_INVALIDAS = (
    "Não entendi as horas do ajuste dia a dia — use números como 2 ou 2,5. Se preferir, feche o "
    "ajuste e escolha um dos atalhos de tempo."
)

#: Rótulo curto dos atalhos de tempo, na ordem de `PRESETS_HORAS`. "4 h+" grava 4 h por dia; quem
#: precisa de mais usa o ajuste dia a dia, e o texto da tela diz isso — rótulo que promete o que
#: não grava é mentira pequena, que é o tipo que ninguém revisa.
ROTULO_PRESET: dict[str, str] = {
    "0": "Não estudo",
    "1": "1 h",
    "2": "2 h",
    "3": "3 h",
    "4": "4 h+",
}

#: Rótulo curto do turno — o `<select>` virou controle segmentado, e "Manhã, antes do trabalho"
#: não cabe num botão de toque. A frase inteira continua na linha de apoio do grupo.
ROTULO_HORARIO_CURTO: dict[str, str] = {"manha": "Manhã", "noite": "Noite", "varia": "Varia"}

#: O atalho pré-selecionado na primeira visita. Não é a rotina dela: é uma sugestão visível, que
#: ela muda com um toque. O padrão antigo era 0 h em todo dia — e 0 h gera plano vazio, que é
#: pior que uma sugestão declarada.
PRESET_SUGERIDO = "2"

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
    """As sete linhas do ajuste dia a dia, na ordem de `DIAS_SEMANA`."""
    return [
        {"chave": dia, "rotulo": ROTULO_DIA[dia], "horas": _texto_de_horas(horas.get(dia, 0.0))}
        for dia in DIAS_SEMANA
    ]


def _texto_de_horas(horas: float) -> str:
    """Formata as horas para o campo em pt-BR: `2`, `2,5` — nunca `2.0`."""
    return f"{horas:g}".replace(".", ",")


def _horas_digitadas(brutas: dict[str, str]) -> tuple[dict[str, float], str]:
    """Lê os sete campos do ajuste dia a dia, aceitando vírgula decimal.

    O campo é `inputmode="decimal"` e **não** `type="number"` de propósito: no teclado do tablet
    da piloto o separador é a vírgula, e um `type="number"` que considera "2,5" inválido envia
    string vazia — o dado sumiria em silêncio, que é o pior defeito possível numa tela de
    configuração. Aqui, texto que não é número vira mensagem, não zero.

    Args:
        brutas: o valor de cada campo por chave de `DIAS_SEMANA`; `""` quando não veio nada.

    Returns:
        As horas reconhecidas (dias vazios ficam de fora) e a mensagem de erro — `""` quando
        tudo foi entendido.
    """
    horas: dict[str, float] = {}
    invalido = False
    for dia, bruto in brutas.items():
        texto = bruto.strip().replace(",", ".")
        if not texto:
            continue
        try:
            horas[dia] = float(texto)
        except ValueError:
            invalido = True
    return horas, MENSAGEM_HORAS_INVALIDAS if invalido else ""


def _atalhos_para_formulario(escolhido: str) -> list[dict[str, object]]:
    """Os botões de atalho de tempo de um grupo, mais a saída "dia a dia"."""
    opcoes: list[dict[str, object]] = [
        {
            "valor": f"{valor:g}",
            "rotulo": ROTULO_PRESET[f"{valor:g}"],
            "escolhido": f"{valor:g}" == escolhido,
        }
        for valor in PRESETS_HORAS
    ]
    opcoes.append(
        {
            "valor": PRESET_MANUAL,
            "rotulo": "Dia a dia",
            "escolhido": escolhido == PRESET_MANUAL,
        }
    )
    return opcoes


def _contexto_formulario(
    db: Session,
    usuario: Usuario,
    *,
    erros: list[str],
    horas: dict[str, float],
    preset_uteis: str,
    preset_fds: str,
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
    concursos = _concursos_para_formulario(db, usuario, concurso_principal_id)
    return {
        "erros": erros,
        "dias": _dias_para_formulario(horas),
        "atalhos_uteis": _atalhos_para_formulario(preset_uteis),
        "atalhos_fds": _atalhos_para_formulario(preset_fds),
        # O ajuste fino abre sozinho quando é ele que manda: quem salvou 2,5 h por dia precisa
        # ver de onde esse número vem, senão a tela parece ter esquecido a rotina dela.
        "ajuste_aberto": PRESET_MANUAL in (preset_uteis, preset_fds),
        "total_semanal": _texto_de_horas(total_semanal(horas)),
        "opcoes_horario": [
            (valor, ROTULO_HORARIO_CURTO[valor], rotulo) for valor, rotulo in OPCOES_HORARIO
        ],
        "horario_preferido": horario_preferido,
        "opcoes_energia": [(valor, ROTULO_ENERGIA[valor]) for valor in ENERGIAS_VALIDAS],
        "energia_tipica": energia_tipica,
        "data_alvo": data_alvo,
        "concursos": concursos,
        # Um concurso só não é uma escolha: é um fato. A tela mostra qual é e segue — perguntar o
        # que tem uma resposta só gasta o fôlego de quem já está cansada (pedido do dono,
        # 23/09/2026). O campo continua no formulário como `hidden`, vazio: vazio quer dizer
        # "mantenha a escolha automática", e não gravamos uma decisão que ela não tomou.
        "concurso_unico": concursos[0] if len(concursos) == 1 else None,
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

    Na primeira visita não há rotina salva: em vez de abrir sete campos zerados para digitar, a
    tela nasce com o atalho sugerido (`PRESET_SUGERIDO`) marcado nos dois grupos, e os campos
    dia a dia já refletem essa sugestão. É uma sugestão visível, a um toque de mudar — não uma
    rotina inventada às escondidas.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).

    Returns:
        O HTML de `rotina/formulario.html` sem erros.
    """
    perfil = perfil_atual(db, usuario.id)
    if perfil is None:
        preset_uteis = preset_fds = PRESET_SUGERIDO
        horas = horas_a_partir_das_escolhas(preset_uteis, preset_fds, {})
    else:
        horas = _horas_do_perfil(perfil)
        preset_uteis = preset_das_horas(horas, DIAS_UTEIS)
        preset_fds = preset_das_horas(horas, DIAS_FIM_DE_SEMANA)
    contexto = _contexto_formulario(
        db,
        usuario,
        erros=[],
        horas=horas,
        preset_uteis=preset_uteis,
        preset_fds=preset_fds,
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
    horario_preferido: Annotated[str, Form()] = "",
    energia_tipica: Annotated[str, Form()] = "",
    preset_uteis: Annotated[str, Form()] = "",
    preset_fds: Annotated[str, Form()] = "",
    hora_seg: Annotated[str, Form()] = "",
    hora_ter: Annotated[str, Form()] = "",
    hora_qua: Annotated[str, Form()] = "",
    hora_qui: Annotated[str, Form()] = "",
    hora_sex: Annotated[str, Form()] = "",
    hora_sab: Annotated[str, Form()] = "",
    hora_dom: Annotated[str, Form()] = "",
    data_alvo: Annotated[str, Form()] = "",
    concurso_principal_id: Annotated[str, Form()] = "",
    consentimento: Annotated[str | None, Form()] = None,
) -> Response:
    """Valida e grava uma nova versão de `perfil_estudo`.

    O tempo por dia chega de duas formas e a precedência é resolvida **aqui**, não no navegador
    (`dominio.rotina.horas_a_partir_das_escolhas`): o atalho do grupo é o caminho principal — um
    toque, sem teclado — e os sete campos dia a dia são a exceção, que vence quando o grupo está
    em `PRESET_MANUAL`. Quem posta só `hora_*`, sem atalho nenhum, continua funcionando: é o
    contrato antigo do formulário, e ele não quebrou.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        horario_preferido: um de `OPCOES_HORARIO`.
        energia_tipica: um de `ENERGIAS_VALIDAS`.
        preset_uteis: atalho de horas para `DIAS_UTEIS` — `"0"`…`"4"`, `PRESET_MANUAL` ou `""`.
        preset_fds: o mesmo para `DIAS_FIM_DE_SEMANA`.
        hora_seg: horas na segunda-feira, como texto (aceita `2` e `2,5`); `""` = não informado.
        hora_ter: idem, terça-feira.
        hora_qua: idem, quarta-feira.
        hora_qui: idem, quinta-feira.
        hora_sex: idem, sexta-feira.
        hora_sab: idem, sábado.
        hora_dom: idem, domingo.
        data_alvo: `"AAAA-MM-DD"` do `<input type="date">`, ou `""`.
        concurso_principal_id: `id` de um concurso do próprio tenant, ou `""`.
        consentimento: `"on"` quando o checkbox de consentimento vem marcado; `None` sem marcar.

    Returns:
        Redirecionamento para `/rotina` no sucesso; a mesma página com a mensagem (200) em erro
        esperado (sem consentimento, concurso de outro tenant, data ou campos inválidos).
    """
    erros: list[str] = []
    digitadas, erro_horas = _horas_digitadas(
        {
            "seg": hora_seg,
            "ter": hora_ter,
            "qua": hora_qua,
            "qui": hora_qui,
            "sex": hora_sex,
            "sab": hora_sab,
            "dom": hora_dom,
        }
    )
    if erro_horas:
        erros.append(erro_horas)
    horas = horas_a_partir_das_escolhas(preset_uteis, preset_fds, digitadas)

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
        preset_uteis=preset_uteis or preset_das_horas(horas, DIAS_UTEIS),
        preset_fds=preset_fds or preset_das_horas(horas, DIAS_FIM_DE_SEMANA),
        horario_preferido=horario_preferido,
        energia_tipica=energia_tipica,
        data_alvo=data_alvo,
        concurso_principal_id=concurso_id,
    )
    return renderizar(request, "rotina/formulario.html", contexto, usuario)

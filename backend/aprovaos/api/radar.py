"""Rotas HTML do radar de editais: catálogo, detalhe e "meus concursos" (fatia 1b, F1.1-F1.3).

O que é: `GET /radar` (catálogo com filtro por fase/UF e selo "combina com você", Ruling 40 —
mostra tudo, nunca esconde), `GET /radar/{evento_url}` (detalhe com cargos/arquivos ao vivo e o
botão "Analisar este edital"), `POST /radar/{evento_url}/acompanhar` e `POST /perfil/principal`
(F1.3, "meus concursos" — gravam em `perfil_estudo`) e `POST /radar/{evento_url}/analisar`
(reaproveita `api.editais.processar_conteudo_pdf` com o PDF baixado da própria Cebraspe). Quando
ler: ao mexer no radar ou em "meus concursos".
"""

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.api.editais import processar_conteudo_pdf
from aprovaos.api.sessao import exigir_usuario, usuario_atual
from aprovaos.api.templates import renderizar, responder_redirecionamento
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import ConcursoRadar, Usuario
from aprovaos.dados.repositorio_edital import listar_concursos_do_tenant
from aprovaos.dados.repositorio_perfil import (
    alternar_acompanhamento,
    marcar_principal,
    perfil_atual,
)
from aprovaos.dados.repositorio_radar import buscar_por_evento_url, listar
from aprovaos.dominio.erros import (
    ArquivoInvalido,
    ConteudoProgramaticoNaoEncontrado,
    PdfSemTexto,
    SemConcursoPrincipal,
)
from aprovaos.dominio.radar import Casamento, ConcursoDoRadar, PreferenciaRadar, casar_com_perfil
from aprovaos.motor.fontes.base import FonteIndisponivel, Novidade
from aprovaos.motor.fontes.cebraspe import URL_ARQUIVO, FonteCebraspe

router = APIRouter(include_in_schema=False)

#: Ruling 38: a FGV aparece no radar como fonte vetada, dita na tela — nunca ausência silenciosa.
NOTA_FGV_VETADA = (
    "FGV Conhecimento: fonte vetada por ora — os termos de uso vedam automação (P-13). O radar "
    "mostra só a Cebraspe até a autorização ser pedida ao titular do produto."
)

MENSAGEM_CONCURSO_NAO_ENCONTRADO = "Este concurso não está (mais) no radar."
MENSAGEM_ANALISE_SEM_PDF = "Este concurso ainda não tem edital em PDF publicado na fonte."
MENSAGEM_FONTE_INDISPONIVEL = (
    "Não deu para consultar a Cebraspe agora. Tente de novo em alguns instantes."
)
MENSAGEM_SEM_ROTINA = "Configure sua rotina antes de escolher ou acompanhar concursos."


def _preferencia_da_query(uf: str | None, salario_min: str | None, area: str) -> PreferenciaRadar:
    """Monta a preferência a partir dos filtros da URL — sem tabela nova nesta fatia.

    Ruling 40: o catálogo nunca esconde um concurso por causa da preferência, então não custa
    caro repetir o filtro a cada visita em vez de persistir. `area` fora de `("direito",
    "qualquer")` cai em `"qualquer"`, nunca 500; `salario_min` que não converte para `Decimal`
    vira `None` (sem preferência), nunca erro para a aluna.
    """
    ufs = [uf.upper()] if uf else []
    salario: Decimal | None = None
    if salario_min:
        try:
            salario = Decimal(salario_min)
        except InvalidOperation:
            salario = None
    area_valida = area if area == "direito" else "qualquer"
    return PreferenciaRadar(ufs=ufs, salario_minimo_brl=salario, area=area_valida)


def _linha_do_catalogo(
    concurso: ConcursoRadar, casamento: Casamento, agora: datetime
) -> dict[str, Any]:
    """Monta o dicionário de exibição de uma linha do catálogo."""
    novo_para_voce = casamento.combina and (agora - concurso.primeiro_visto_em) < timedelta(days=1)
    return {
        "evento_url": concurso.evento_url,
        "nome": concurso.nome,
        "ano": concurso.ano,
        "fase": concurso.fase,
        "uf": concurso.uf,
        "vagas": concurso.vagas,
        "salario_max_brl": concurso.salario_max_brl,
        "lacunas": concurso.lacunas,
        "combina": casamento.combina,
        "motivos": casamento.motivos,
        "novo_para_voce": novo_para_voce,
        "inscricao_fim": concurso.inscricao_fim,
    }


def _meus_concursos(db: Session, usuario: Usuario) -> dict[str, Any]:
    """Monta o painel "meus concursos": principal (entre os concursos do tenant) e acompanhados.

    Sem rotina ainda (`perfil_estudo` nunca salvo), devolve `tem_rotina=False` — a tela mostra o
    link para `/rotina` em vez do painel (marcar principal/acompanhar exige rotina, ver
    `dados.repositorio_perfil`).
    """
    perfil = perfil_atual(db, usuario.id)
    concursos_do_tenant = [
        {"id": str(c.id), "orgao": c.orgao, "cargo": c.cargo}
        for c in listar_concursos_do_tenant(db, usuario.tenant_id)
    ]
    if perfil is None:
        return {"tem_rotina": False, "concursos_do_tenant": concursos_do_tenant}

    acompanhados = []
    for url in perfil.concursos_acompanhados:
        radar_do_url = buscar_por_evento_url(db, url)
        nome = radar_do_url.nome if radar_do_url is not None else url
        acompanhados.append({"evento_url": url, "nome": nome})
    return {
        "tem_rotina": True,
        "concurso_principal_id": str(perfil.concurso_principal_id)
        if perfil.concurso_principal_id
        else None,
        "concursos_do_tenant": concursos_do_tenant,
        "acompanhados": acompanhados,
        "aviso_impacto": (
            f"Você acompanha {len(acompanhados)} concurso(s) do radar além do principal. O "
            "plano do dia segue só o concurso principal — os demais ficam aqui, para "
            "acompanhamento, mas não entram no plano."
        )
        if acompanhados
        else None,
    }


@router.get("/radar")
def radar(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario | None, Depends(usuario_atual)],
    fase: str | None = None,
    uf: str | None = None,
    salario_min: str | None = None,
    area: str = "qualquer",
) -> Response:
    """Catálogo do radar: todos os concursos vistos, com selo "combina com você" (Ruling 40).

    `fase` é um filtro de verdade (esconde: é navegação explícita, como abas "Encerrados"/"Em
    andamento"). `uf`/`salario_min`/`area` são a **preferência**, não um filtro — Ruling 40
    ("combina com o perfil" ordena e marca, nunca esconde): um concurso de outra UF continua na
    lista, só sem o selo e mais abaixo na ordenação.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado, ou `None` (o catálogo é público — informação de radar).
        fase: filtro que esconde (`novos`/`inscricoes_abertas`/`em_andamento`/`encerrado`).
        uf: preferência de UF para o selo "combina" — nunca esconde outra UF.
        salario_min: preferência de salário mínimo (texto — convertido com cautela).
        area: preferência de área (`"direito"`/`"qualquer"`).

    Returns:
        O HTML de `radar/index.html`.
    """
    preferencia = _preferencia_da_query(uf, salario_min, area)
    agora = agora_utc()
    concursos = listar(db, fase=fase)
    linhas = [
        _linha_do_catalogo(c, casar_com_perfil(_para_dominio(c), preferencia, cargos=[]), agora)
        for c in concursos
    ]
    linhas.sort(
        key=lambda linha: (
            not linha["combina"],
            linha["inscricao_fim"] or agora.date().replace(year=agora.year + 100),
        )
    )
    contexto: dict[str, Any] = {
        "linhas": linhas,
        "filtros": {"fase": fase, "uf": uf, "salario_min": salario_min, "area": area},
        "nota_fgv_vetada": NOTA_FGV_VETADA,
    }
    if usuario is not None:
        contexto["meus_concursos"] = _meus_concursos(db, usuario)
        contexto["mensagem_sem_rotina"] = MENSAGEM_SEM_ROTINA
    return renderizar(request, "radar/index.html", contexto, usuario)


def _para_dominio(concurso: ConcursoRadar) -> ConcursoDoRadar:
    """Reconstrói o `ConcursoDoRadar` puro a partir da linha persistida, para `casar_com_perfil`."""
    return ConcursoDoRadar(
        evento_url=concurso.evento_url,
        nome=concurso.nome,
        ano=concurso.ano,
        fase=concurso.fase,
        uf=concurso.uf,
        vagas=concurso.vagas,
        salario_max_brl=concurso.salario_max_brl,
        periodo_inscricao_texto=concurso.periodo_inscricao_texto,
        inscricao_inicio=concurso.inscricao_inicio,
        inscricao_fim=concurso.inscricao_fim,
        lacunas=concurso.lacunas,
    )


def _exigir_concurso(db: Session, evento_url: str) -> ConcursoRadar:
    """`buscar_por_evento_url` obrigatório: sem correspondência, levanta 404."""
    concurso = buscar_por_evento_url(db, evento_url)
    if concurso is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_CONCURSO_NAO_ENCONTRADO)
    return concurso


@router.get("/radar/{evento_url}")
def detalhe(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario | None, Depends(usuario_atual)],
    evento_url: str,
) -> Response:
    """Detalhe de um concurso do radar: cargos e arquivos de edital ao vivo (F1.1).

    O catálogo persistido não traz `eventoCargos`/`arquivosEdital` (só o detalhe da API tem) —
    esta rota consulta a fonte na hora; se a fonte estiver fora do ar, a página mostra o que já
    tem (catálogo) e avisa que o detalhe ao vivo falhou, em vez de quebrar.

    Args:
        request: a requisição atual.
        db: sessão de banco do request.
        usuario: o usuário logado, ou `None`.
        evento_url: identidade do concurso no radar.

    Returns:
        O HTML de `radar/detalhe.html`.

    Raises:
        HTTPException: 404 quando o concurso não está no radar.
    """
    concurso = _exigir_concurso(db, evento_url)
    fonte_cebraspe: FonteCebraspe = request.app.state.fonte_cebraspe
    cargos: list[str] = []
    arquivos_edital: list[dict[str, str]] = []
    erro_detalhe: str | None = None
    try:
        bruto = fonte_cebraspe.obter_detalhe(evento_url)
        cargos = [c["area"] for c in (bruto.get("eventoCargos") or [])]
        arquivos_edital = [
            {"nome": a["nomeArquivo"], "descricao": a["descricaoArquivo"]}
            for a in (bruto.get("arquivosEdital") or [])
            if a.get("tipoExtensaoArquivo", "").endswith(".pdf")
        ]
    except FonteIndisponivel:
        erro_detalhe = MENSAGEM_FONTE_INDISPONIVEL

    acompanhando = False
    if usuario is not None:
        perfil = perfil_atual(db, usuario.id)
        acompanhando = perfil is not None and evento_url in perfil.concursos_acompanhados

    contexto: dict[str, Any] = {
        "concurso": {
            "evento_url": concurso.evento_url,
            "nome": concurso.nome,
            "ano": concurso.ano,
            "fase": concurso.fase,
            "uf": concurso.uf,
            "vagas": concurso.vagas,
            "salario_max_brl": concurso.salario_max_brl,
            "periodo_inscricao_texto": concurso.periodo_inscricao_texto,
            "lacunas": concurso.lacunas,
            "url_evento": concurso.url_evento,
        },
        "cargos": cargos,
        "arquivos_edital": arquivos_edital,
        "erro_detalhe": erro_detalhe,
        "acompanhando": acompanhando,
    }
    return renderizar(request, "radar/detalhe.html", contexto, usuario)


@router.post("/radar/{evento_url}/acompanhar")
def acompanhar(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    evento_url: str,
) -> Response:
    """Alterna (liga/desliga) o acompanhamento de um concurso do radar (F1.3, toggle).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        evento_url: identidade do concurso no radar.

    Returns:
        Redirecionamento de volta para `/radar/{evento_url}`.

    Raises:
        HTTPException: 404 quando o concurso não está no radar.
    """
    _exigir_concurso(db, evento_url)
    try:
        alternar_acompanhamento(db, usuario, evento_url)
    except SemConcursoPrincipal:
        db.rollback()
        return responder_redirecionamento(request, "/rotina")
    db.commit()
    return responder_redirecionamento(request, f"/radar/{evento_url}")


@router.post("/perfil/principal")
def escolher_principal(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    concurso_id: Annotated[UUID, Form()],
) -> Response:
    """Escolhe qual `Concurso` (dos já analisados pela aluna) é o principal (F1.3).

    O plano do dia segue **só** o principal — o split de tempo entre concursos fica fora do
    escopo desta fatia (Ruling 41/§6 do plano); acompanhar outros concursos é só um selo e uma
    lista, nunca divide automaticamente o tempo de estudo.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        concurso_id: o `Concurso` escolhido — precisa ser do tenant do usuário.

    Returns:
        Redirecionamento para `/radar`.

    Raises:
        HTTPException: 403 se `concurso_id` não for de um concurso do tenant do usuário.
    """
    ids_do_tenant = {c.id for c in listar_concursos_do_tenant(db, usuario.tenant_id)}
    if concurso_id not in ids_do_tenant:
        raise HTTPException(status_code=403, detail="Este concurso pertence a outra conta.")
    try:
        marcar_principal(db, usuario, concurso_id)
    except SemConcursoPrincipal:
        db.rollback()
        return responder_redirecionamento(request, "/rotina")
    db.commit()
    return responder_redirecionamento(request, "/radar")


@router.post("/radar/{evento_url}/analisar")
async def analisar_edital_do_radar(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    evento_url: str,
) -> Response:
    """Analisa este edital: baixa o PDF direto da Cebraspe e roda o pipeline da V2.

    O mesmo pipeline de `POST /editais/subir`, só que o PDF chega pela URL do detalhe da
    Cebraspe (não por upload) — o primeiro arquivo de `arquivosEdital` cujo nome termina em
    `.pdf`. O `Concurso` nasce `origem="real"` (padrão de `registrar_edital`; nunca
    `"fixture"` — este concurso vem de dado de verdade da API, não de PDF de teste).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        evento_url: identidade do concurso no radar.

    Returns:
        Redirecionamento para `/concurso/{id}` no sucesso; volta para `/radar/{evento_url}` com
        mensagem quando não há PDF, o PDF não tem conteúdo programático reconhecível, ou a fonte
        está fora do ar.

    Raises:
        HTTPException: 404 quando o concurso não está no radar.
    """
    _exigir_concurso(db, evento_url)
    fonte_cebraspe: FonteCebraspe = request.app.state.fonte_cebraspe
    try:
        bruto = fonte_cebraspe.obter_detalhe(evento_url)
    except FonteIndisponivel:
        return renderizar(
            request, "radar/erro_analise.html", {"mensagem": MENSAGEM_FONTE_INDISPONIVEL}, usuario
        )
    arquivos = bruto.get("arquivosEdital") or []
    arquivo_pdf = next(
        (a for a in arquivos if a.get("tipoExtensaoArquivo", "").endswith(".pdf")), None
    )
    if arquivo_pdf is None:
        return renderizar(
            request, "radar/erro_analise.html", {"mensagem": MENSAGEM_ANALISE_SEM_PDF}, usuario
        )

    url_pdf = URL_ARQUIVO.format(eventoURL=evento_url, nomeArquivo=arquivo_pdf["nomeArquivo"])
    novidade = Novidade(
        id=f"{evento_url}/{arquivo_pdf['nomeArquivo']}",
        tipo="edital",
        titulo=arquivo_pdf["descricaoArquivo"],
        url=url_pdf,
        evento=evento_url,
        publicado_em=None,
    )
    try:
        baixado = fonte_cebraspe.baixar(novidade)
    except FonteIndisponivel:
        return renderizar(
            request, "radar/erro_analise.html", {"mensagem": MENSAGEM_FONTE_INDISPONIVEL}, usuario
        )

    try:
        concurso = await processar_conteudo_pdf(
            request, db, usuario, baixado.conteudo, arquivo_pdf["nomeArquivo"]
        )
    except (ArquivoInvalido, PdfSemTexto, ConteudoProgramaticoNaoEncontrado) as erro:
        return renderizar(request, "radar/erro_analise.html", {"mensagem": str(erro)}, usuario)
    db.commit()
    return responder_redirecionamento(request, f"/concurso/{concurso.id}")

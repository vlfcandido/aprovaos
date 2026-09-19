"""Rotas HTML do diagnóstico adaptativo (`GET/POST /diagnostico`, fatia 7, F2.1).

O que é: `GET /diagnostico` mostra o próximo item (escolhido por `dominio.diagnostico
.ordenar_candidatos`) com a caixa "por que este item", ou a tela de resultado quando o simulado
termina (teto de `MAXIMO_ITENS` ou nenhuma matéria elegível sobrando); `POST /diagnostico` registra
a resposta como um `evento_estudo` comum (`dados={"diagnostico": True}` — o mesmo marcador que
`respostas_diagnostico` filtra) e devolve o fragmento de resultado, reaproveitando
`contexto_questao`/`contexto_evento`/`questoes/_resultado.html` de `api/questoes.py` ("responder
no diagnóstico é, na prática, responder a questão de novo" — mesmo espírito de `/revisar`, V4).
Nenhuma tabela nova guarda "o estado do diagnóstico": cada `GET` recomputa tudo a partir dos
eventos já marcados (`dados/repositorio_diagnostico.py`) — reiniciar o navegador não perde
progresso, e trocar o concurso principal (rotina) começa um diagnóstico novo. "Insistir" (o
"discordar" desta fatia, plano §6) é o parâmetro `?insistir=<matéria>`: um item a mais numa
matéria já fechada, sempre respeitando o teto. Quando ler: ao mexer no fluxo do diagnóstico ou na
explicação exibida.
"""

from collections import Counter
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.api.questoes import (
    CONFIANCAS_VALIDAS,
    MENSAGEM_CONFIANCA_OBRIGATORIA,
    MENSAGEM_QUESTAO_INDISPONIVEL,
    MENSAGENS_RESPOSTA_INVALIDA_POR_TIPO,
    RESPOSTAS_VALIDAS_POR_TIPO,
    contexto_evento,
    contexto_questao,
    veredito_de_limite,
)
from aprovaos.api.sessao import exigir_usuario
from aprovaos.api.templates import renderizar
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Edital,
    EventoEstudo,
    Questao,
    ReporteErro,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dados.repositorio_cartao import registrar_erro
from aprovaos.dados.repositorio_diagnostico import respostas_diagnostico, topicos_do_diagnostico
from aprovaos.dados.repositorio_edital import concurso_principal, edital_atual
from aprovaos.dados.repositorio_questao import proxima_questao, registrar_resposta
from aprovaos.dominio.diagnostico import (
    MAXIMO_ITENS,
    EstadoAgregado,
    ItemDiagnostico,
    TopicoDisponivel,
    agrupar_por_materia,
    motivo_geral,
    ordenar_candidatos,
    sinais_por_topico,
)
from aprovaos.dominio.revisao import Confianca

router = APIRouter(include_in_schema=False)

MENSAGEM_TOPICO_FORA_DO_DIAGNOSTICO = "Tópico não encontrado neste diagnóstico."


def _edital_do_concurso_principal(db: Session, usuario: Usuario) -> Edital | None:
    """O `Edital` atual do concurso principal do tenant (P-23), ou `None` sem concurso/edital."""
    concurso = concurso_principal(db, usuario.tenant_id)
    if concurso is None:
        return None
    return edital_atual(db, concurso.id)


def _questao_pendente(
    db: Session, usuario_id: UUID, topico_id: UUID, questao_id: UUID
) -> Questao | None:
    """A `questao_id` só é aceita se ainda está pendente para este usuário neste tópico.

    Mesma checagem de `api.questoes._questao_pendente` (não importada daqui para não acoplar os
    dois módulos por um símbolo privado: a semântica é idêntica, a duplicação é de ~10 linhas).
    """
    respondidas = select(EventoEstudo.questao_id).where(
        EventoEstudo.usuario_id == usuario_id, EventoEstudo.tipo == "resposta"
    )
    reportadas = select(ReporteErro.conteudo_id).where(
        ReporteErro.usuario_id == usuario_id, ReporteErro.conteudo_tipo == "questao"
    )
    consulta = select(Questao).where(
        Questao.id == questao_id,
        Questao.topico_id == topico_id,
        Questao.publicavel.is_(True),
        Questao.despublicada_em.is_(None),  # P-34: calibrador despublica por aqui
        Questao.id.not_in(respondidas),
        Questao.id.not_in(reportadas),
    )
    return db.scalars(consulta).first()


def _topico_pertence_ao_edital(db: Session, topico_id: UUID, edital_id: UUID) -> bool:
    """`True` se `topico_id` está entre os tópicos deste edital."""
    consulta = select(TopicoEdital.id).where(
        TopicoEdital.edital_id == edital_id, TopicoEdital.topico_id == topico_id
    )
    return db.scalars(consulta).first() is not None


def _contexto_resultado(
    total_itens: int,
    topicos: list[TopicoDisponivel],
    respostas: list[ItemDiagnostico],
    estados_por_materia: dict[str, EstadoAgregado],
) -> dict[str, object]:
    """Monta o contexto de `diagnostico/resultado.html` — por matéria e por tópico.

    Args:
        total_itens: quantos itens o diagnóstico usou ao todo.
        topicos: todos os tópicos do edital do concurso principal.
        respostas: todas as respostas marcadas do diagnóstico.
        estados_por_materia: `agrupar_por_materia(respostas)`.

    Returns:
        O contexto para `renderizar`, com `finalizado=True`.
    """
    todas_materias = {t.materia for t in topicos}
    materias_com_questao = {t.materia for t in topicos if t.tem_questao}
    materias_sem_questao = todas_materias - materias_com_questao

    materias = []
    for materia in sorted(todas_materias):
        estado = estados_por_materia.get(materia)
        materias.append(
            {
                "materia": materia,
                "tem_questao": materia in materias_com_questao,
                "n_itens": estado.n_itens if estado else 0,
                "estimativa_pct": estado.estimativa_pct if estado else None,
                "margem": estado.margem if estado else None,
                "fechado": bool(estado and estado.fechado),
            }
        )

    nomes_por_topico = {t.topico_id: t.nome for t in topicos}
    sinais = [
        {
            "materia": sinal.materia,
            "nome": nomes_por_topico.get(sinal.topico_id, ""),
            "situacao": sinal.situacao,
            "estimativa_pct": sinal.estimativa_pct,
            "margem": sinal.margem,
            "n_itens": sinal.n_itens,
        }
        for sinal in sinais_por_topico(respostas, topicos)
    ]

    return {
        "finalizado": True,
        "total_itens": total_itens,
        "motivo": motivo_geral(total_itens, estados_por_materia, materias_sem_questao),
        "materias": materias,
        "topicos": sinais,
    }


@router.get("/diagnostico")
def diagnostico(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
) -> Response:
    """Mostra o próximo item do diagnóstico, ou o resultado quando ele termina.

    Args:
        request: a requisição atual (`?insistir=<matéria>` força mais um item numa matéria já
            fechada — §6 do plano).
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).

    Returns:
        `diagnostico/andamento.html` (`sem_concurso=True` sem concurso principal resolvível, ou
        com o próximo item), ou `diagnostico/resultado.html` quando termina. Sempre 200.
    """
    edital = _edital_do_concurso_principal(db, usuario)
    if edital is None:
        return renderizar(request, "diagnostico/andamento.html", {"sem_concurso": True}, usuario)

    topicos = topicos_do_diagnostico(db, edital.id)
    respostas = respostas_diagnostico(db, usuario.id, edital.id)
    estados = agrupar_por_materia(respostas)
    total_itens = len(respostas)

    insistir = request.query_params.get("insistir")
    materias_forcadas = frozenset({insistir}) if insistir else frozenset()

    if total_itens < MAXIMO_ITENS:
        veredito = veredito_de_limite(db, usuario)
        if not veredito.permitido:
            contexto_limite = {"limite": {"motivo": veredito.motivo, "convite": veredito.convite}}
            return renderizar(request, "diagnostico/andamento.html", contexto_limite, usuario)

        respondidos_por_topico = Counter(r.topico_id for r in respostas)
        candidatos = ordenar_candidatos(topicos, estados, respondidos_por_topico, materias_forcadas)
        for candidato in candidatos:
            questao = proxima_questao(db, usuario.id, candidato.topico_id)
            if questao is None:
                continue
            topico = db.get(Topico, candidato.topico_id)
            assert topico is not None  # veio de topicos_do_diagnostico, que lê do mesmo edital
            contexto = contexto_questao(
                db,
                topico,
                questao,
                acao_post="/diagnostico",
                campos_ocultos=[("topico_id", str(candidato.topico_id))],
            )
            contexto["progresso"] = {"atual": total_itens + 1, "maximo": MAXIMO_ITENS}
            contexto["motivo_item"] = candidato.motivo
            return renderizar(request, "diagnostico/andamento.html", contexto, usuario)

    contexto_final = _contexto_resultado(total_itens, topicos, respostas, estados)
    return renderizar(request, "diagnostico/resultado.html", contexto_final, usuario)


@router.post("/diagnostico")
def responder_diagnostico(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    resposta: Annotated[str, Form()],
    questao_id: Annotated[UUID, Form()],
    topico_id: Annotated[UUID, Form()],
    confianca: Annotated[str | None, Form()] = None,
    tempo_ms: Annotated[int, Form()] = 0,
) -> Response:
    """Registra a resposta ao item do diagnóstico e devolve o fragmento do resultado.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        resposta: o que o aluno marcou.
        questao_id: `id` da questão respondida, do campo oculto do formulário.
        topico_id: `id` do tópico do item mostrado, do campo oculto do formulário.
        confianca: `"certeza"`/`"duvida"`; `None` (campo ausente) é erro.
        tempo_ms: tempo gasto no item, em milissegundos; `0` quando o cliente não manda.

    Returns:
        `questoes/_resultado.html` com `proximo_url="/diagnostico"` (200).

    Raises:
        HTTPException: 404 sem concurso principal/edital, ou se `topico_id` não pertencer ao
            edital do concurso principal; 400 sem `confianca` válida, ou com `resposta` fora do
            que `RESPOSTAS_VALIDAS_POR_TIPO` aceita para o tipo da questão.
    """
    edital = _edital_do_concurso_principal(db, usuario)
    if edital is None:
        raise HTTPException(status_code=404, detail="Concurso principal não encontrado.")
    if not _topico_pertence_ao_edital(db, topico_id, edital.id):
        raise HTTPException(status_code=404, detail=MENSAGEM_TOPICO_FORA_DO_DIAGNOSTICO)
    if confianca not in CONFIANCAS_VALIDAS:
        raise HTTPException(status_code=400, detail=MENSAGEM_CONFIANCA_OBRIGATORIA)

    topico = db.get(Topico, topico_id)
    assert topico is not None  # confirmado por _topico_pertence_ao_edital

    questao = _questao_pendente(db, usuario.id, topico_id, questao_id)
    if questao is None:
        contexto = contexto_questao(db, topico, None)
        contexto["aviso"] = MENSAGEM_QUESTAO_INDISPONIVEL
        contexto["proximo_url"] = "/diagnostico"
        contexto["proximo_rotulo"] = "Continuar diagnóstico"
        return renderizar(request, "questoes/_resultado.html", contexto, usuario)

    respostas_validas = RESPOSTAS_VALIDAS_POR_TIPO[questao.tipo_item]
    if resposta not in respostas_validas:
        mensagem = MENSAGENS_RESPOSTA_INVALIDA_POR_TIPO[questao.tipo_item]
        raise HTTPException(status_code=400, detail=mensagem)

    agora = agora_utc()
    evento = registrar_resposta(
        db, usuario, questao, resposta, confianca, tempo_ms, dados={"diagnostico": True}
    )
    if not evento.acertou:
        registrar_erro(db, usuario, questao, cast(Confianca, confianca), agora)
    db.commit()

    contexto = contexto_questao(db, topico, questao)
    contexto["evento"] = contexto_evento(db, questao, resposta, evento.acertou)
    contexto["proximo_url"] = "/diagnostico"
    contexto["proximo_rotulo"] = "Continuar diagnóstico"
    return renderizar(request, "questoes/_resultado.html", contexto, usuario)

"""Rotas HTML do painel (`GET /painel`, `GET /painel/semana`, fatia 10, §8 do plano).

O que é: `GET /painel` monta a curva de domínio (RF-16, com o alerta de atraso — RF-10), os
padrões de erro com suporte estatístico (RF-17) e a previsão de nota v0 (RF-18), tudo
determinístico (Ruling 36) — nenhuma chamada de LLM aqui. `GET /painel/semana` monta o resumo
semanal cumulativo (F4.4c). As duas rotas mostram o caminho para `/rotina`/`/editais/subir` (nunca
uma exceção) quando o usuário ainda não tem concurso principal ou edital resolvível. O gráfico da
curva e a banda da previsão são `<svg>` montados aqui mesmo, em servidor, sem JS e sem
dependência nova (`_svg_curva`/`_svg_previsao`) — o número sempre aparece por escrito ao lado
(`docs/fatias/10-painel.md` §8), o desenho nunca é a única fonte da informação. Quando ler: ao
mudar o que a tela do painel mostra ou o texto de uma lacuna.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.api.sessao import exigir_usuario
from aprovaos.api.templates import renderizar
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Concurso, Edital, Usuario
from aprovaos.dados.repositorio_edital import concurso_principal, edital_atual
from aprovaos.dados.repositorio_painel import (
    FUSO_BRASILIA,
    curva_atual,
    nomes_por_topico,
    pesos_por_materia,
    respostas_classificadas,
    respostas_historicas,
    total_topicos,
)
from aprovaos.dados.repositorio_perfil import perfil_atual
from aprovaos.dados.repositorio_plano import dias_para_prova_do_dia
from aprovaos.dominio.curva import Curva, PontoCurva, alerta_da_curva
from aprovaos.dominio.estatistica import intervalo_wilson
from aprovaos.dominio.padroes import (
    MINIMO_RESPOSTAS_PADRAO,
    PadraoErro,
    RespostaClassificada,
    detectar_padroes,
)
from aprovaos.dominio.plano import DIAS_JANELA_SEMANA_PROVA
from aprovaos.dominio.previsao import DesempenhoMateria, Previsao, prever_nota
from aprovaos.dominio.resumo_semanal import montar_resumo

router = APIRouter(include_in_schema=False)

MENSAGEM_SEM_CONCURSO = (
    "Suba um edital e configure sua rotina em /rotina para ver o painel — sem isso não há "
    "curva, padrão nem previsão para calcular."
)
AVISO_FUSO = "Os horários desta página são os de Brasília (America/Sao_Paulo)."

#: Geometria do svg da curva (§8 do plano: "duas polilinhas + eixos", sem JS/biblioteca).
_SVG_LARGURA: Final = 640
_SVG_ALTURA: Final = 220
_SVG_MARGEM_ESQ: Final = 32
_SVG_MARGEM_DIR: Final = 12
_SVG_MARGEM_SUP: Final = 12
_SVG_MARGEM_INF: Final = 28


def _edital_do_concurso_principal(db: Session, usuario: Usuario) -> tuple[Concurso, Edital] | None:
    """`(concurso, edital)` do concurso principal do tenant, ou `None` sem um dos dois (P-23)."""
    concurso = concurso_principal(db, usuario.tenant_id)
    if concurso is None:
        return None
    edital = edital_atual(db, concurso.id)
    if edital is None:
        return None
    return concurso, edital


def _svg_curva(curva: Curva, total: int) -> str:
    """Monta o `<svg>` da curva: a polilinha real (cheia) e a necessária (tracejada), com eixos.

    Não desenha nada sem nenhum ponto real — a lacuna é dita em texto por quem chama
    (`curva.lacuna` ou "sem resposta ainda"), nunca um gráfico vazio fingindo dado.

    Args:
        curva: a curva já montada (`dados.repositorio_painel.curva_atual`).
        total: `total_topicos` do edital — o topo do eixo y (`curva.real` pode estar vazia).

    Returns:
        O markup do `<svg>` (cores por token, via `var(--cor-*)` — resolvidas pelo CSS da
        página), ou `""` sem nenhum ponto real.
    """
    if not curva.real:
        return ""

    eixo_total = total or curva.real[0].total_topicos or 1
    largura_util = _SVG_LARGURA - _SVG_MARGEM_ESQ - _SVG_MARGEM_DIR
    altura_util = _SVG_ALTURA - _SVG_MARGEM_SUP - _SVG_MARGEM_INF
    linha_base_y = _SVG_ALTURA - _SVG_MARGEM_INF

    todos_os_pontos = curva.real + curva.necessaria
    dia_min = min(p.dia for p in todos_os_pontos)
    dia_max = max(p.dia for p in todos_os_pontos)
    intervalo_dias = max((dia_max - dia_min).days, 1)

    def x(dia: date) -> float:
        return _SVG_MARGEM_ESQ + (dia - dia_min).days / intervalo_dias * largura_util

    def y(dominados: int) -> float:
        return _SVG_MARGEM_SUP + (1 - dominados / eixo_total) * altura_util

    def polilinha(pontos: list[PontoCurva]) -> str:
        return " ".join(f"{x(p.dia):.1f},{y(p.dominados):.1f}" for p in pontos)

    partes = [
        f'<svg viewBox="0 0 {_SVG_LARGURA} {_SVG_ALTURA}" role="img" '
        'aria-label="Curva de tópicos dominados: o que você já fez comparado ao que seria '
        'necessário até a prova">',
        f'<line x1="{_SVG_MARGEM_ESQ}" y1="{_SVG_MARGEM_SUP}" x2="{_SVG_MARGEM_ESQ}" '
        f'y2="{linha_base_y}" stroke="var(--cor-linha)" stroke-width="1"/>',
        f'<line x1="{_SVG_MARGEM_ESQ}" y1="{linha_base_y}" '
        f'x2="{_SVG_LARGURA - _SVG_MARGEM_DIR}" y2="{linha_base_y}" '
        'stroke="var(--cor-linha)" stroke-width="1"/>',
        f'<text x="4" y="{_SVG_MARGEM_SUP + 8}" font-size="10" '
        f'fill="var(--cor-texto-3)">{eixo_total}</text>',
        f'<text x="4" y="{linha_base_y}" font-size="10" fill="var(--cor-texto-3)">0</text>',
    ]
    if curva.necessaria:
        partes.append(
            f'<polyline points="{polilinha(curva.necessaria)}" fill="none" '
            'stroke="var(--cor-texto-3)" stroke-width="2" stroke-dasharray="4 4"/>'
        )
    partes.append(
        f'<polyline points="{polilinha(curva.real)}" fill="none" stroke="var(--cor-acao)" '
        'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    for ponto in curva.real:
        partes.append(
            f'<circle cx="{x(ponto.dia):.1f}" cy="{y(ponto.dominados):.1f}" r="3.5" '
            'fill="var(--cor-superficie)" stroke="var(--cor-acao)" stroke-width="2"/>'
        )
    partes.append("</svg>")
    return "".join(partes)


def _svg_previsao(previsao: Previsao) -> str:
    """Uma barra translúcida com a banda de Wilson da nota (§8 do plano: "banda… é um `<rect>`").

    O número por extenso ("62 % — entre 48 % e 74 %") é escrito pelo template, ao lado — este
    `<svg>` nunca é a única fonte da informação.
    """
    largura, altura = 200, 16
    escala = largura / 100
    inferior = max(0.0, min(100.0, previsao.nota_inferior_pct))
    superior = max(0.0, min(100.0, previsao.nota_superior_pct))
    ponto = max(0.0, min(100.0, previsao.nota_pct))
    return (
        f'<svg viewBox="0 0 {largura} {altura}" role="img" '
        f'aria-label="Banda da nota prevista, de {inferior:.0f} a {superior:.0f} por cento">'
        f'<rect x="0" y="6" width="{largura}" height="4" rx="2" '
        'fill="var(--cor-superficie-2)"/>'
        f'<rect x="{inferior * escala:.1f}" y="6" '
        f'width="{(superior - inferior) * escala:.1f}" height="4" rx="2" '
        'fill="var(--cor-acao-suave)"/>'
        f'<circle cx="{ponto * escala:.1f}" cy="8" r="4" fill="var(--cor-acao)"/>'
        "</svg>"
    )


def _contexto_curva(
    curva: Curva, total: int, alerta_ctx: dict[str, str] | None
) -> dict[str, object]:
    """O contexto de `painel/_curva.html` a partir da `Curva` e do alerta, já resolvidos."""
    dominados_hoje = curva.real[-1].dominados if curva.real else 0
    return {
        "lacuna": curva.lacuna,
        "atraso_topicos": curva.atraso_topicos,
        "data_alvo": curva.data_alvo,
        "dominados_hoje": dominados_hoje,
        "total_topicos": total,
        "svg": _svg_curva(curva, total),
        "alerta": alerta_ctx,
    }


def _desempenho_por_materia(
    respostas: list[RespostaClassificada], pesos: dict[str, int]
) -> list[DesempenhoMateria]:
    """Agrupa `respostas_classificadas` por matéria para `dominio.previsao.prever_nota` (RF-18).

    Matéria sem nenhuma resposta entra com `proporcao=None` (nunca zero) — é o que faz
    `prever_nota` colocá-la em `materias_sem_dado` em vez de puxar a média para baixo.

    Args:
        respostas: `dados.repositorio_painel.respostas_classificadas` (mesmas respostas usadas
            nos padrões — a proficiência por matéria usa `acertou`/`materia`, o resto não).
        pesos: `dados.repositorio_painel.pesos_por_materia(...).pesos`.

    Returns:
        Uma `DesempenhoMateria` por matéria (do edital e/ou já respondida), em ordem alfabética.
    """
    acertos_por_materia: dict[str, list[bool]] = defaultdict(list)
    for resposta in respostas:
        acertos_por_materia[resposta.materia].append(resposta.acertou)

    materias = sorted(set(pesos) | set(acertos_por_materia))
    desempenho: list[DesempenhoMateria] = []
    for materia in materias:
        acertos_da_materia = acertos_por_materia.get(materia)
        peso = pesos.get(materia, 1)
        if not acertos_da_materia:
            desempenho.append(
                DesempenhoMateria(materia=materia, proporcao=None, peso_questoes=peso)
            )
            continue
        total = len(acertos_da_materia)
        acertos = sum(acertos_da_materia)
        desempenho.append(
            DesempenhoMateria(
                materia=materia,
                proporcao=intervalo_wilson(acertos, total),
                peso_questoes=peso,
            )
        )
    return desempenho


def _contexto_previsao(
    desempenho: list[DesempenhoMateria],
) -> tuple[dict[str, object] | None, str | None]:
    """`(contexto de _previsao.html, motivo da lacuna)` — um dos dois é sempre `None`."""
    try:
        previsao = prever_nota(desempenho)
    except ValueError as erro:
        return None, str(erro)

    contexto: dict[str, object] = {
        "nota_pct": previsao.nota_pct,
        "nota_inferior_pct": previsao.nota_inferior_pct,
        "nota_superior_pct": previsao.nota_superior_pct,
        "confianca": previsao.confianca,
        "materias_sem_dado": previsao.materias_sem_dado,
        "probabilidade_lacuna": previsao.probabilidade_lacuna,
        "porque": previsao.porque,
        "svg": _svg_previsao(previsao),
    }
    return contexto, None


def _contexto_padroes(padroes: list[PadraoErro]) -> list[dict[str, object]]:
    """O contexto de `painel/_padroes.html`: só o que o template precisa de cada `PadraoErro`."""
    return [
        {
            "dimensao": padrao.dimensao,
            "valor": padrao.valor,
            "frase": padrao.frase,
            "n": padrao.proporcao.total,
        }
        for padrao in padroes
    ]


@router.get("/painel")
def painel(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
) -> Response:
    """Curva, alerta, padrões e previsão do concurso principal do usuário (RF-16/17/18, RF-10).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).

    Returns:
        `painel/pagina.html`, sempre 200: com `sem_concurso=True` e o caminho para `/rotina`/
        `/editais/subir` sem concurso principal ou edital resolvível; com os quatro blocos caso
        contrário.
    """
    resolvido = _edital_do_concurso_principal(db, usuario)
    if resolvido is None:
        return renderizar(
            request,
            "painel/pagina.html",
            {"sem_concurso": True, "motivo": MENSAGEM_SEM_CONCURSO},
            usuario,
        )
    _concurso, edital = resolvido

    hoje = agora_utc().date()
    total = total_topicos(db, edital.id)
    curva = curva_atual(db, usuario.id, edital.id, hoje)

    perfil = perfil_atual(db, usuario.id)
    horas_por_semana = (
        sum(float(v) for v in perfil.horas_por_dia_semana.values()) if perfil is not None else 0.0
    )
    alerta = alerta_da_curva(curva, horas_por_semana)
    alerta_ctx = (
        {"titulo": alerta.titulo, "porque": alerta.porque, "ajuste": alerta.ajuste}
        if alerta is not None
        else None
    )

    respostas_padroes = respostas_classificadas(db, usuario.id, edital.id)
    padroes = detectar_padroes(respostas_padroes)

    pesos = pesos_por_materia(db, edital.id)
    desempenho = _desempenho_por_materia(respostas_padroes, pesos.pesos)
    previsao_ctx, motivo_sem_previsao = _contexto_previsao(desempenho)

    dias_para_prova = dias_para_prova_do_dia(db, usuario.id, hoje)
    semana_prova = dias_para_prova is not None and 0 <= dias_para_prova <= DIAS_JANELA_SEMANA_PROVA

    contexto = {
        "sem_concurso": False,
        "aviso_fuso": AVISO_FUSO,
        "semana_prova": semana_prova,
        "dias_para_prova": dias_para_prova,
        "curva": _contexto_curva(curva, total, alerta_ctx),
        "padroes": _contexto_padroes(padroes),
        "minimo_respostas_padrao": MINIMO_RESPOSTAS_PADRAO,
        "previsao": previsao_ctx,
        "motivo_sem_previsao": motivo_sem_previsao,
        "pesos_lacuna": pesos.lacuna,
    }
    return renderizar(request, "painel/pagina.html", contexto, usuario)


@router.get("/painel/semana")
def painel_semana(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
) -> Response:
    """O resumo semanal cumulativo do concurso principal do usuário (F4.4c, sem LLM — Ruling 36).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado.

    Returns:
        `painel/semana.html`, sempre 200: com `sem_concurso=True` sem concurso principal/edital;
        com o `ResumoSemanal` da semana corrente (segunda a domingo, em Brasília) caso contrário.
    """
    resolvido = _edital_do_concurso_principal(db, usuario)
    if resolvido is None:
        return renderizar(
            request,
            "painel/semana.html",
            {"sem_concurso": True, "motivo": MENSAGEM_SEM_CONCURSO},
            usuario,
        )
    _concurso, edital = resolvido

    hoje_local = agora_utc().astimezone(FUSO_BRASILIA).date()
    inicio = hoje_local - timedelta(days=hoje_local.weekday())
    fim = inicio + timedelta(days=6)

    respostas = respostas_historicas(db, usuario.id, edital.id)
    nomes = nomes_por_topico(db, edital.id)
    resumo = montar_resumo(respostas, nomes, inicio, fim)

    contexto = {
        "sem_concurso": False,
        "aviso_fuso": AVISO_FUSO,
        "resumo": resumo,
    }
    return renderizar(request, "painel/semana.html", contexto, usuario)

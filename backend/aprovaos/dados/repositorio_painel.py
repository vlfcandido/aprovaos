"""Repositório do painel (fatia 10, §8 do plano): dados para curva, padrões, previsão e resumo.

O que é: `respostas_historicas`/`respostas_classificadas` (a mesma trava da P-34 de
`dados/repositorio_questao.py` — `Questao.publicavel is True` **e** `despublicada_em IS NULL`),
`pesos_por_materia` (do DNA quando o edital traz a distribuição real por matéria; peso uniforme
com lacuna declarada quando não traz — P-39), `nomes_por_topico`/`total_topicos` (auxiliares de
tela) e `curva_atual`/`alerta_atual` — que já chamam `dominio.curva.montar_curva`/
`alerta_da_curva` com os dados buscados, porque o alerta (RF-10) é reaproveitado por duas rotas
(`GET /painel` e `GET /hoje`) e não deve duplicar a consulta nem o critério em dois lugares.
Funções soltas recebendo `Session` como primeiro parâmetro, só leitura (o painel não grava nada).
Quando ler: ao mexer no que os números do painel realmente contam, ou ao investigar por que um
padrão/previsão/curva saiu diferente do esperado. Plano: `docs/fatias/10-painel.md` §8.
"""

from datetime import date
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import Edital, EventoEstudo, Questao, Topico, TopicoEdital, Usuario
from aprovaos.dados.repositorio_edital import concurso_principal, dna_atual, edital_atual
from aprovaos.dados.repositorio_perfil import perfil_atual
from aprovaos.dominio.curva import Alerta, Curva, RespostaHistorica, alerta_da_curva, montar_curva
from aprovaos.dominio.edital import normalizar_materia, slug_materia
from aprovaos.dominio.padroes import RespostaClassificada

#: Fuso da aluna (Ruling 37, `docs/fatias/10-painel.md` §1) — `evento_estudo.ocorrido_em` é
#: sempre UTC; toda hora do dia exibida no painel é convertida para cá e a tela diz isso.
FUSO_BRASILIA: Final = ZoneInfo("America/Sao_Paulo")

#: Mensagem exibida quando o DNA do edital não traz quantas questões cada matéria tem na prova —
#: a previsão usa peso `1` (uniforme) por matéria em vez de inventar uma distribuição. Em
#: linguagem da aluna, sem código interno de pendência.
LACUNA_PESO_UNIFORME: Final = (
    "o edital não informa quantas questões cada matéria tem, então o peso está uniforme entre "
    "as matérias"
)


class PesosMateria(BaseModel):
    """O peso (nº de questões na prova) de cada matéria do edital, para ponderar a previsão.

    Attributes:
        pesos: `{nome da matéria: peso_questoes}` — todas as matérias do edital, sempre `>= 1`.
        lacuna: o motivo de `pesos` ter caído no peso uniforme, quando o DNA não trouxe a
            distribuição real de nenhuma matéria com dado incompleto; `None` quando os pesos são
            os do DNA (`dna_concurso.conteudo.pesos.materia[slug].questoes`).
    """

    pesos: dict[str, int]
    lacuna: str | None


def respostas_historicas(db: Session, usuario_id: UUID, edital_id: UUID) -> list[RespostaHistorica]:
    """As respostas do usuário aos tópicos deste edital, para a curva de domínio (RF-16).

    Args:
        db: sessão do request.
        usuario_id: aluno.
        edital_id: chave do edital (decide quais tópicos valem — `topico` é vocabulário global,
            compartilhado por edital, mesma premissa D de `repositorio_questao.py`).

    Returns:
        Uma `RespostaHistorica` por `evento_estudo` de resposta, na ordem de `ocorrido_em`; só
        questões `publicavel=True` e `despublicada_em IS NULL` entram (P-34).
    """
    consulta = (
        select(EventoEstudo.acertou, EventoEstudo.ocorrido_em, Questao.topico_id)
        .join(Questao, EventoEstudo.questao_id == Questao.id)
        .join(TopicoEdital, TopicoEdital.topico_id == Questao.topico_id)
        .where(
            EventoEstudo.usuario_id == usuario_id,
            EventoEstudo.tipo == "resposta",
            TopicoEdital.edital_id == edital_id,
            Questao.publicavel.is_(True),
            Questao.despublicada_em.is_(None),  # P-34: calibrador despublica por aqui
        )
        .order_by(EventoEstudo.ocorrido_em)
    )
    return [
        RespostaHistorica(topico_id=topico_id, acertou=bool(acertou), ocorrido_em=ocorrido_em)
        for acertou, ocorrido_em, topico_id in db.execute(consulta).all()
    ]


def respostas_classificadas(
    db: Session, usuario_id: UUID, edital_id: UUID
) -> list[RespostaClassificada]:
    """As respostas do usuário já classificadas para `dominio.padroes.detectar_padroes` (RF-17).

    Args:
        db: sessão do request.
        usuario_id: aluno.
        edital_id: chave do edital.

    Returns:
        Uma `RespostaClassificada` por `evento_estudo` de resposta (`materia`/`topico_nome` de
        `topico`, `banca` de `questao`, `hora_local` convertida para `America/Sao_Paulo` —
        Ruling 37); mesma trava da P-34 de `respostas_historicas`. `materia` já passa por
        `normalizar_materia` — dado velho do bug de fusão pode ter a mesma matéria em duas
        caixas (`"LÍNGUA PORTUGUESA"` e `"Língua Portuguesa"`); sem normalizar aqui ela vira
        duas matérias na tela.
    """
    consulta = (
        select(
            EventoEstudo.acertou,
            EventoEstudo.ocorrido_em,
            EventoEstudo.energia,
            Topico.materia,
            Topico.nome,
            Questao.banca,
        )
        .join(Questao, EventoEstudo.questao_id == Questao.id)
        .join(Topico, Questao.topico_id == Topico.id)
        .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
        .where(
            EventoEstudo.usuario_id == usuario_id,
            EventoEstudo.tipo == "resposta",
            TopicoEdital.edital_id == edital_id,
            Questao.publicavel.is_(True),
            Questao.despublicada_em.is_(None),  # P-34: calibrador despublica por aqui
        )
    )
    return [
        RespostaClassificada(
            acertou=bool(acertou),
            materia=normalizar_materia(materia),
            topico_nome=topico_nome,
            banca=banca,
            hora_local=ocorrido_em.astimezone(FUSO_BRASILIA).hour,
            energia=energia,
        )
        for acertou, ocorrido_em, energia, materia, topico_nome, banca in db.execute(consulta).all()
    ]


def nomes_por_topico(db: Session, edital_id: UUID) -> dict[UUID, str]:
    """`{topico_id: nome}` de todos os tópicos deste edital — para o resumo semanal (F4.4c).

    Args:
        db: sessão do request.
        edital_id: chave do edital.

    Returns:
        O dicionário; vazio se o edital não tiver tópico nenhum.
    """
    consulta = (
        select(Topico.id, Topico.nome)
        .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
        .where(TopicoEdital.edital_id == edital_id)
    )
    return {topico_id: nome for topico_id, nome in db.execute(consulta).all()}


def total_topicos(db: Session, edital_id: UUID) -> int:
    """Quantos tópicos este edital tem ao todo — o denominador da curva (RF-16).

    Args:
        db: sessão do request.
        edital_id: chave do edital.

    Returns:
        A contagem; `0` se o edital não existir ou não tiver tópico nenhum.
    """
    consulta = (
        select(func.count()).select_from(TopicoEdital).where(TopicoEdital.edital_id == edital_id)
    )
    return db.scalar(consulta) or 0


def pesos_por_materia(db: Session, edital_id: UUID) -> PesosMateria:
    """O peso de cada matéria do edital na prova, do DNA quando completo, senão uniforme (P-39).

    Cai no peso uniforme (uma lacuna só, para todas as matérias) sempre que **qualquer** matéria
    do edital não tiver `questoes` (um número inteiro) no DNA — misturar peso real de uma matéria
    com peso uniforme de outra criaria uma previsão com precisão que os dados não sustentam.

    Args:
        db: sessão do request.
        edital_id: chave do edital.

    Returns:
        `PesosMateria` com uma entrada por matéria do edital; `pesos={}` sem matéria nenhuma.
        Os nomes já passam por `normalizar_materia` (mesmo motivo de `respostas_classificadas`).
    """
    materias = sorted(
        {
            normalizar_materia(materia)
            for (materia,) in db.execute(
                select(Topico.materia)
                .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
                .where(TopicoEdital.edital_id == edital_id)
                .distinct()
            ).all()
        }
    )
    if not materias:
        return PesosMateria(pesos={}, lacuna=None)

    edital = db.get(Edital, edital_id)
    dna = dna_atual(db, edital.concurso_id) if edital is not None else None
    if dna is not None:
        pesos_dna = dna.conteudo.get("pesos", {}).get("materia", {})
        pesos: dict[str, int] = {}
        completo = True
        for materia in materias:
            entrada = pesos_dna.get(slug_materia(materia))
            questoes = entrada.get("questoes") if entrada else None
            if isinstance(questoes, int):
                pesos[materia] = questoes
            else:
                completo = False
                break
        if completo:
            return PesosMateria(pesos=pesos, lacuna=None)

    return PesosMateria(pesos=dict.fromkeys(materias, 1), lacuna=LACUNA_PESO_UNIFORME)


def curva_atual(db: Session, usuario_id: UUID, edital_id: UUID, hoje: date) -> Curva:
    """Monta a `Curva` (RF-16) deste usuário/edital a partir do histórico e da rotina.

    Args:
        db: sessão do request.
        usuario_id: aluno.
        edital_id: chave do edital.
        hoje: data de referência (nunca lida internamente — quem chama decide "hoje").

    Returns:
        A `Curva` (`dominio.curva.montar_curva`); `data_alvo=None` quando o usuário não tem
        `perfil_estudo` ou não informou a data da prova.
    """
    respostas = respostas_historicas(db, usuario_id, edital_id)
    total = total_topicos(db, edital_id)
    perfil = perfil_atual(db, usuario_id)
    data_alvo = perfil.data_alvo if perfil is not None else None
    return montar_curva(respostas, total, hoje, data_alvo)


def alerta_atual(db: Session, usuario: Usuario, hoje: date) -> Alerta | None:
    """O alerta de atraso (RF-10) deste usuário, hoje — reaproveitado por `/painel` e `/hoje`.

    Args:
        db: sessão do request.
        usuario: usuário logado.
        hoje: data de referência.

    Returns:
        `None` sem concurso principal, sem edital, ou quando `alerta_da_curva` decide que não há
        atraso a avisar; o `Alerta` caso contrário.
    """
    concurso = concurso_principal(db, usuario.tenant_id)
    if concurso is None:
        return None
    edital = edital_atual(db, concurso.id)
    if edital is None:
        return None
    curva = curva_atual(db, usuario.id, edital.id, hoje)
    perfil = perfil_atual(db, usuario.id)
    horas_por_semana = (
        sum(float(v) for v in perfil.horas_por_dia_semana.values()) if perfil is not None else 0.0
    )
    return alerta_da_curva(curva, horas_por_semana)

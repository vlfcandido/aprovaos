"""Rotas HTML de questão (`/topico/{slug}/questoes`), reportar erro e revisão espaçada (`/revisar`).

O que é: `GET /topico/{slug}/questoes` mostra a próxima questão publicável do tópico que o
usuário ainda não respondeu nem reportou (`repositorio_questao.proxima_questao`); `POST` no
mesmo endereço registra a resposta e devolve só o fragmento HTMX com o resultado (decisão 1 do
passo 13); `POST /questoes/{id}/reportar` grava o reporte. O isolamento por tenant é feito aqui:
o `slug` é vocabulário global (compartilhado entre editais), então toda rota amarra o tópico ao
edital de algum concurso do tenant do usuário logado — tópico fora disso é 404 (decisão 2). A
tela decide pelo `Questao.tipo_item` (passo 3 da V3b): `"certo_errado"` julga C/E;
`"multipla_escolha"` escolhe entre as cinco `Alternativa` A–E gravadas pelo curador — as
respostas válidas e a mensagem de erro mudam conforme o tipo (`RESPOSTAS_VALIDAS_POR_TIPO`), mas
a gravação (`registrar_resposta`) e o critério de acerto (`resposta == questao.gabarito`) são os
mesmos para os dois, porque `Questao.gabarito` já guarda a letra certa nos dois casos. Quando há
justificativa gravada (fundação jurídica, passo 5), o resultado mostra as duas faces
(`afirmacoes_para_exibir`) marcadas como explicação do AprovaOS, cada frase com o dispositivo
legal que a sustenta — texto original da banca continua vindo só de `questao`/`Alternativa`, sem
mistura.

A V4 (F4.3) acrescenta: `responder_questao` grava um `cartao(origem="auto_erro")` sempre que
`acertou is False` (`repositorio_cartao.registrar_erro`) — acertar nunca cria cartão. `GET/POST
/revisar` mostram e respondem os cartões vencidos (`repositorio_cartao.cartoes_vencidos`, `due
<= agora`, ordem do FSRS); como "a revisão de um cartão de questão é, na prática, a questão de
novo" (plano V4 §5), as duas rotas reaproveitam `contexto_questao`/`contexto_evento` e o
parcial `questoes/_cartao_questao.html` — só o destino do formulário (`acao_post`) e os campos
ocultos extras (`cartao_id`) mudam.

A V5 (fio da memória) acrescenta a intercalação: `GET /topico/{slug}/questoes` decide, antes de
buscar a próxima questão nativa, se a posição do bloco (`repositorio_fio_memoria
.quantidade_no_bloco`) pede um item de outro tópico já visto (`dominio.fio_memoria
.decidir_proximo_intercalado`/`ordem_para_tentar`); quando pede, a tela mostra a questão desse
outro tópico com o selo "Fio da memória" e o motivo, reaproveitando o mesmo `_cartao_questao.html`
(`fio_da_memoria` no contexto). `POST` grava `bloco_topico_id` (e, quando intercalado,
`fio_motivo`/`fio_origem_topico_id`) em `evento_estudo.dados`, via campos ocultos do formulário —
é o que faz `quantidade_no_bloco` avançar independente de a resposta ser nativa ou intercalada
(`docs/fatias/V5-fio-da-memoria.md` §3/§4). A tela de revisão (`/revisar`) nunca intercala — só os
cartões vencidos (§5 do plano V5). Quando ler: ao mexer na tela de resolver questão, na tela de
revisão, no fluxo de reportar erro ou na intercalação do fio da memória.

A fatia 7 promove `contexto_questao`/`contexto_evento`/`alternativas_ordenadas`/
`mapa_dispositivos_por_chave`/`afirmacoes_para_exibir` de privadas (`_` na frente) a públicas: são
as mesmas funções, sem mudança de comportamento — só deixam de ter `_` porque `api/diagnostico.py`
também as usa ("responder no diagnóstico é, na prática, responder a questão de novo", mesmo
espírito de `/revisar`). Continuam sendo detalhe de implementação da camada `api/`, não parte da
superfície pública do produto.
"""

from collections.abc import Sequence
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.api.db import obter_db
from aprovaos.api.sessao import exigir_usuario
from aprovaos.api.templates import renderizar
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import (
    Alternativa,
    Aula,
    Cartao,
    Concurso,
    DispositivoLegal,
    Edital,
    EventoEstudo,
    Questao,
    ReporteErro,
    Topico,
    TopicoEdital,
    Usuario,
)
from aprovaos.dados.repositorio_assinatura import tier_do_usuario
from aprovaos.dados.repositorio_aula import aula_publicada_do_topico
from aprovaos.dados.repositorio_cartao import cartoes_vencidos, registrar_erro, revisar_cartao
from aprovaos.dados.repositorio_citacao import dispositivos_da_questao
from aprovaos.dados.repositorio_fio_memoria import (
    estatisticas_topicos_vistos,
    quantidade_no_bloco,
)
from aprovaos.dados.repositorio_questao import (
    proxima_questao,
    registrar_reporte,
    registrar_resposta,
)
from aprovaos.dados.repositorio_uso import uso_do_dia
from aprovaos.dominio.assinatura import Veredito, pode_responder
from aprovaos.dominio.aula import CitacaoAula, renderizar_com_notas
from aprovaos.dominio.citacao import normalizar_citacao_para_comparacao
from aprovaos.dominio.fio_memoria import (
    ItemIntercalado,
    escolher_para_intercalar,
    ordem_para_tentar,
)
from aprovaos.dominio.justificativa import separar_afirmacoes
from aprovaos.dominio.revisao import Confianca

router = APIRouter(include_in_schema=False)

#: Valores aceitos para `confianca` (decisão 3: obrigatório antes de responder).
CONFIANCAS_VALIDAS = ("certeza", "duvida")

MENSAGEM_RESPOSTA_INVALIDA_CERTO_ERRADO = "Resposta inválida — julgue o item como Certo ou Errado."
MENSAGEM_RESPOSTA_INVALIDA_MULTIPLA_ESCOLHA = (
    "Resposta inválida — escolha uma das alternativas de A a E."
)

#: Respostas aceitas e mensagem de erro por `Questao.tipo_item` (passo 3 da V3b). Só estes dois
#: valores existem em `dominio.questao.QuestaoCurada.tipo_item`; um `tipo_item` fora daqui é bug
#: de dado, não de formulário — a indexação em `responder_questao` levanta `KeyError` (500) se
#: acontecer, em vez de aceitar silenciosamente qualquer `resposta`.
RESPOSTAS_VALIDAS_POR_TIPO: dict[str, tuple[str, ...]] = {
    "certo_errado": ("C", "E"),
    "multipla_escolha": ("A", "B", "C", "D", "E"),
}
MENSAGENS_RESPOSTA_INVALIDA_POR_TIPO: dict[str, str] = {
    "certo_errado": MENSAGEM_RESPOSTA_INVALIDA_CERTO_ERRADO,
    "multipla_escolha": MENSAGEM_RESPOSTA_INVALIDA_MULTIPLA_ESCOLHA,
}

#: Acima de quantos caracteres o texto de apoio nasce recolhido atrás de "ver texto de apoio"
#: (passo 14 da V3, decisão 3). Regra de negócio: fica aqui, não como número solto no Jinja — o
#: template só lê a flag `apoio_recolhido` já calculada.
LIMITE_TEXTO_APOIO_RECOLHIDO = 600

MENSAGEM_TOPICO_NAO_ENCONTRADO = "Tópico não encontrado nesta conta."
MENSAGEM_CONFIANCA_OBRIGATORIA = "Diga se você tem certeza ou dúvida antes de responder."
MENSAGEM_QUESTAO_NAO_ENCONTRADA = "Questão não encontrada."
MENSAGEM_QUESTAO_INDISPONIVEL = (
    "Esta questão não está mais disponível para responder — atualize a página e tente de novo."
)

RESPOSTA_TEXTO = {"C": "Certo", "E": "Errado"}


def _eh_htmx(request: Request) -> bool:
    """`True` se o request veio de um `hx-post`/`hx-get` do htmx (cabeçalho `HX-Request`)."""
    return request.headers.get("HX-Request") == "true"


def _topico_do_tenant(db: Session, slug: str, tenant_id: UUID) -> Topico | None:
    """Localiza o tópico pelo `slug` só se ele pertencer a um edital de um concurso do tenant.

    O tópico é vocabulário global (`Topico.slug` é único e compartilhado entre editais); a
    junção com `topico_edital` → `edital` → `concurso` é o que restringe "pertence a este
    tenant" — sem ela, qualquer usuário logado poderia ler questões de qualquer edital só
    sabendo o slug.

    Args:
        db: sessão do request.
        slug: slug global do tópico, vindo da URL.
        tenant_id: tenant do usuário logado.

    Returns:
        O `Topico`, ou `None` se nenhum edital do tenant o contiver.
    """
    consulta = (
        select(Topico)
        .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
        .join(Edital, Edital.id == TopicoEdital.edital_id)
        .join(Concurso, Concurso.id == Edital.concurso_id)
        .where(Topico.slug == slug, Concurso.tenant_id == tenant_id)
    )
    return db.scalars(consulta).first()


def _exigir_topico_do_tenant(db: Session, slug: str, usuario: Usuario) -> Topico:
    """`_topico_do_tenant` obrigatório: sem correspondência, levanta 404 no formato da V1."""
    topico = _topico_do_tenant(db, slug, usuario.tenant_id)
    if topico is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_TOPICO_NAO_ENCONTRADO)
    return topico


def _edital_do_topico_para_tenant(db: Session, topico_id: UUID, tenant_id: UUID) -> UUID | None:
    """O `edital_id` de algum edital do tenant que contém este tópico (V5, fio da memória).

    Mesma junção de `_topico_do_tenant`, partindo do tópico em vez do slug. Um tópico pode, em
    tese, pertencer a mais de um edital do mesmo tenant (vocabulário global); esta função devolve
    o primeiro — suficiente para escopar `estatisticas_topicos_vistos` (mesma simplificação de
    "concurso principal" já aceita em outras telas, P-23) e não crítico: só decide quais tópicos
    entram no ranking de intercalação, nunca o que é publicável.

    Args:
        db: sessão do request.
        topico_id: o tópico já resolvido para o tenant.
        tenant_id: tenant do usuário logado.

    Returns:
        O `edital_id`, ou `None` (defensivo — não deveria acontecer para um tópico que já passou
        por `_exigir_topico_do_tenant`).
    """
    consulta = (
        select(Edital.id)
        .join(TopicoEdital, TopicoEdital.edital_id == Edital.id)
        .join(Concurso, Concurso.id == Edital.concurso_id)
        .where(TopicoEdital.topico_id == topico_id, Concurso.tenant_id == tenant_id)
    )
    return db.scalars(consulta).first()


def _questao_do_tenant(db: Session, questao_id: UUID, tenant_id: UUID) -> Questao | None:
    """Localiza a questão só se o tópico dela pertencer a um edital do tenant.

    Mesma checagem de `_topico_do_tenant` (junção `topico_edital` → `edital` → `concurso`),
    partindo da questão em vez do slug — `POST /questoes/{id}/reportar` não tem slug na URL, mas
    é a única rota da fatia que faltava essa amarração: sem ela, qualquer logado reportaria
    qualquer questão do pool global só sabendo o `id`. Uma questão sem tópico (`topico_id is
    None`, nunca publicável) não pertence a tenant nenhum por essa via.

    Args:
        db: sessão do request.
        questao_id: chave da questão, vinda da URL.
        tenant_id: tenant do usuário logado.

    Returns:
        A `Questao`, ou `None` se ela não existir ou o tópico dela não pertencer a nenhum
        edital do tenant.
    """
    questao = db.get(Questao, questao_id)
    if questao is None or questao.topico_id is None:
        return None
    consulta = (
        select(Topico.id)
        .join(TopicoEdital, TopicoEdital.topico_id == Topico.id)
        .join(Edital, Edital.id == TopicoEdital.edital_id)
        .join(Concurso, Concurso.id == Edital.concurso_id)
        .where(Topico.id == questao.topico_id, Concurso.tenant_id == tenant_id)
    )
    if db.scalars(consulta).first() is None:
        return None
    return questao


def _questao_pendente(
    db: Session, usuario_id: UUID, topico_id: UUID, questao_id: UUID
) -> Questao | None:
    """A `questao_id` só é aceita se ainda está pendente para este usuário neste tópico.

    Existe para a rota nunca gravar `registrar_resposta` contra uma questão que não é a que a
    tela mostrou — um `questao_id` de outro tópico, de uma questão já respondida (corrida entre
    abas, back/refresh) ou já reportada é rejeitado aqui, antes de qualquer gravação.
    `evento_estudo` é append-only e alimenta o FSRS: um evento gravado contra a questão errada
    não tem conserto depois. `responder_questao` (V5) chama esta função duas vezes conforme o
    caso: com `topico.id` da URL para a questão nativa, ou com `fio_origem_topico_id` (já
    validado como de um edital deste tenant) para um item intercalado — a garantia é a mesma nos
    dois casos, só o tópico de referência muda.

    Args:
        db: sessão do request.
        usuario_id: quem está respondendo.
        topico_id: o tópico ao qual a `questao_id` deve pertencer — o da URL para uma questão
            nativa, ou o tópico de origem já validado de um item intercalado (V5).
        questao_id: `questao_id` que veio do formulário.

    Returns:
        A `Questao`, ou `None` se ela não existir, não for deste tópico, não for publicável, ou
        já tiver resposta/reporte deste usuário.
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


def alternativas_ordenadas(db: Session, questao_id: UUID) -> list[Alternativa]:
    """As `Alternativa` (A–E) desta questão, na ordem impressa pela banca.

    Args:
        db: sessão do request.
        questao_id: chave da questão de múltipla escolha.

    Returns:
        As `Alternativa` ordenadas por `letra` (A, B, C, D, E); vazio se a questão não é de
        múltipla escolha ou (anomalia de dado) não tem nenhuma gravada.
    """
    consulta = (
        select(Alternativa).where(Alternativa.questao_id == questao_id).order_by(Alternativa.letra)
    )
    return list(db.scalars(consulta).all())


def contexto_questao(
    db: Session,
    topico: Topico,
    questao: Questao | None,
    *,
    acao_post: str = "",
    campos_ocultos: Sequence[tuple[str, str]] = (),
    fio_da_memoria: dict[str, object] | None = None,
) -> dict[str, object]:
    """Monta o contexto do parcial `questoes/_cartao_questao.html`.

    O gabarito nunca entra aqui (decisão 4): só o comando, o texto de apoio, o enunciado e a
    origem completa, todos vindos direto da `questao` — nada de reconstruir a partir de outro
    lugar. Em `"multipla_escolha"`, as cinco `alternativas` entram como `{letra, texto}` — sem
    `correta`, que só aparece depois de responder (`contexto_evento`): nada no HTML de antes da
    resposta pode distinguir qual das cinco é a certa. `acao_post`/`campos_ocultos` (V4) são o
    que faz o mesmo parcial servir `/topico/{slug}/questoes` e `/revisar` — só o destino do
    formulário e um campo oculto a mais (`cartao_id`, na revisão) mudam entre os dois.
    `fio_da_memoria` (V5) é o selo "de onde veio" quando `questao` é um item intercalado — `None`
    (o padrão) para uma questão nativa do tópico da URL. `questao_contexto["inedita"]` (fatia 5)
    é o que os parciais usam para trocar o bloco de origem de prova (`origem` vem `{}` para uma
    inédita, que não tem procedência) pelo selo "Questão inédita do AprovaOS".

    Args:
        db: sessão do request (só para buscar as alternativas de múltipla escolha).
        topico: o tópico já resolvido para o tenant (o tópico **da URL**, não necessariamente o
            de `questao` — um item intercalado tem `questao.topico_id` diferente deste).
        questao: a próxima questão publicável, ou `None` sem nenhuma sobrando.
        acao_post: URL para onde o formulário de resposta posta; `""` quando o contexto é usado
            só para montar o resultado (`_resultado.html` não inclui o formulário de novo).
        campos_ocultos: pares `(nome, valor)` de campos ocultos extras do formulário, além de
            `questao_id` (que já entra sempre).
        fio_da_memoria: `{"motivo": str}` quando `questao` é um item intercalado (V5); `None`
            para uma questão nativa.

    Returns:
        O contexto para `renderizar`.
    """
    contexto: dict[str, object] = {
        "topico": {"slug": topico.slug, "nome": topico.nome},
        "questao": None,
        "acao_post": acao_post,
        "campos_ocultos": list(campos_ocultos),
        "fio_da_memoria": fio_da_memoria,
    }
    if questao is not None:
        origem = questao.origem or {}
        questao_contexto: dict[str, object] = {
            "id": str(questao.id),
            "tipo_item": questao.tipo_item,
            "comando": questao.comando,
            "texto_apoio": questao.texto_apoio,
            "apoio_recolhido": bool(
                questao.texto_apoio and len(questao.texto_apoio) > LIMITE_TEXTO_APOIO_RECOLHIDO
            ),
            "enunciado": questao.enunciado,
            "inedita": questao.inedita,
        }
        if questao.tipo_item == "multipla_escolha":
            questao_contexto["alternativas"] = [
                {"letra": alternativa.letra, "texto": alternativa.texto}
                for alternativa in alternativas_ordenadas(db, questao.id)
            ]
        contexto["questao"] = questao_contexto
        contexto["origem"] = origem
    return contexto


def mapa_dispositivos_por_chave(db: Session, questao_id: UUID) -> dict[str, DispositivoLegal]:
    """Os `DispositivoLegal` já ligados a esta questão, por citação normalizada.

    São exatamente os dispositivos que o `gerador-de-justificativa` recebeu como única fonte
    permitida (`motor.justificar`) — por isso servem tanto para achar o dispositivo que uma
    afirmação cita quanto para exibir o trecho literal na tela, sem outra consulta. A chave é
    `dominio.citacao.normalizar_citacao_para_comparacao` do `citacao_canonica`: o mesmo ajuste que
    corrige o validador (ordinal/ponto final não mudam a identidade do dispositivo) evita que a
    tela deixe de casar uma citação por causa da grafia (`"art. 1º"` do gerador x `"art. 1"`
    gravado).

    Args:
        db: sessão do request.
        questao_id: chave da questão.

    Returns:
        `{chave_normalizada: DispositivoLegal}`; vazio se a questão não tem nenhum ligado ainda.
    """
    return {
        normalizar_citacao_para_comparacao(d.citacao_canonica): d
        for d in dispositivos_da_questao(db, questao_id)
    }


def afirmacoes_para_exibir(
    texto: str | None, dispositivos_por_chave: dict[str, DispositivoLegal]
) -> list[dict[str, object]]:
    """Separa `texto` (formato de `dominio.justificativa.montar_texto`) em frases exibíveis.

    Cada frase vem com o dispositivo que a sustenta — o trecho literal e a URL da fonte, quando o
    dispositivo citado está entre os já ligados à questão (`mapa_dispositivos_por_chave`); a
    citação aparece mesmo sem o trecho (defensivo: nunca deveria faltar, mas a tela não esconde a
    fonte citada só porque não achou o texto).

    Args:
        texto: `Questao.justificativa_certo`/`_errado` ou `Alternativa.justificativa`; `None`
            quando a questão/alternativa ainda não tem justificativa.
        dispositivos_por_chave: de `mapa_dispositivos_por_chave`, para achar o texto literal.

    Returns:
        Uma entrada por frase (`texto`, `dispositivo_rotulo`, `dispositivo_texto`,
        `dispositivo_url`); lista vazia quando `texto` é `None` — é o que faz a tela não mostrar
        nada, silenciosamente, na maioria das questões (ainda sem justificativa).
    """
    resultado: list[dict[str, object]] = []
    for afirmacao in separar_afirmacoes(texto):
        dispositivo = None
        if afirmacao.dispositivo:
            dispositivo = dispositivos_por_chave.get(
                normalizar_citacao_para_comparacao(afirmacao.dispositivo)
            )
        resultado.append(
            {
                "texto": afirmacao.texto,
                "dispositivo_rotulo": afirmacao.dispositivo,
                "dispositivo_texto": dispositivo.texto if dispositivo else None,
                "dispositivo_url": dispositivo.fonte_url if dispositivo else None,
            }
        )
    return resultado


def contexto_evento(
    db: Session, questao: Questao, resposta: str, acertou: bool | None
) -> dict[str, object]:
    """Monta o `evento` do template `questoes/_resultado.html` — só depois de já ter gravado.

    Em `"certo_errado"`, mostra os dois lados sempre (`Questao.justificativa_certo` **e**
    `justificativa_errado`, não só o que bate com `acertou`) — o aluno aprende com os dois,
    mesmo o que não escolheu (mesmo princípio de `dominio.justificativa.Afirmacao`). Em
    `"multipla_escolha"`, é a lista das cinco alternativas com `correta`/`marcada` e a própria
    justificativa de cada uma. As duas vias passam por `afirmacoes_para_exibir`, que nasce lista
    vazia sem justificativa gravada (a maioria das questões hoje) — ausente é mostrado como
    ausente, nunca com um texto inventado no lugar.

    Args:
        db: sessão do request (busca as alternativas de múltipla escolha e os dispositivos já
            ligados à questão).
        questao: a questão respondida.
        resposta: a letra que o aluno marcou.
        acertou: se `resposta == questao.gabarito`.

    Returns:
        O dicionário `evento` do contexto de `_resultado.html`.
    """
    dispositivos_por_chave = mapa_dispositivos_por_chave(db, questao.id)
    if questao.tipo_item == "multipla_escolha":
        alternativas = [
            {
                "letra": alternativa.letra,
                "texto": alternativa.texto,
                "correta": alternativa.correta,
                "marcada": alternativa.letra == resposta,
                "justificativa": afirmacoes_para_exibir(
                    alternativa.justificativa, dispositivos_por_chave
                ),
            }
            for alternativa in alternativas_ordenadas(db, questao.id)
        ]
        return {
            "acertou": acertou,
            "alternativas": alternativas,
            "tem_justificativa": any(a["justificativa"] for a in alternativas),
        }
    return {
        "acertou": acertou,
        "resposta_texto": RESPOSTA_TEXTO.get(resposta, resposta),
        "gabarito_texto": RESPOSTA_TEXTO.get(questao.gabarito or "", questao.gabarito),
        "justificativa_certo": afirmacoes_para_exibir(
            questao.justificativa_certo, dispositivos_por_chave
        ),
        "justificativa_errado": afirmacoes_para_exibir(
            questao.justificativa_errado, dispositivos_por_chave
        ),
    }


def veredito_de_limite(db: Session, usuario: Usuario) -> Veredito:
    """O `Veredito` de `dominio.assinatura.pode_responder` para este usuário, agora (Ruling 47).

    Conferido só ao **montar** a próxima questão (`GET /topico/{slug}/questoes` e
    `GET /diagnostico`) — nunca no meio de uma resposta (`POST`), e nunca em `/revisar` nem
    `/topico/{slug}/aula`: essas duas rotas não chamam esta função, então, por construção, não
    existe caminho para limitá-las.

    Args:
        db: sessão do request.
        usuario: o usuário logado.

    Returns:
        O `Veredito` (`permitido=True` para Pro ou Free abaixo do limite diário).
    """
    hoje = agora_utc().date()
    tier = tier_do_usuario(db, usuario.id, hoje)
    uso = uso_do_dia(db, usuario.id, hoje)
    return pode_responder(tier, uso)


def _proximo_item_intercalado(
    db: Session, usuario: Usuario, topico: Topico
) -> tuple[ItemIntercalado, Questao] | tuple[None, None]:
    """Decide se a posição atual do bloco pede um item intercalado e acha a questão dele (V5).

    O candidato indicado pela cadência (`dominio.fio_memoria.decidir_proximo_intercalado`) pode
    não ter mais questão disponível (todas já respondidas/reportadas) — por isso tenta, na ordem
    de `dominio.fio_memoria.ordem_para_tentar`, cada candidato do ranking até achar um com
    questão pendente (`repositorio_questao.proxima_questao`), antes de desistir e a rota cair de
    volta para a questão nativa do tópico (§3 do plano V5).

    Args:
        db: sessão do request.
        usuario: o usuário logado.
        topico: o tópico da URL — a âncora do bloco, não necessariamente o tópico do item
            devolvido (que é sempre de outro tópico já visto).

    Returns:
        `(item, questao)` do primeiro candidato com questão disponível; `(None, None)` quando não
        é a vez de intercalar, não há histórico, ou nenhum candidato tem questão sobrando.
    """
    edital_id = _edital_do_topico_para_tenant(db, topico.id, usuario.tenant_id)
    if edital_id is None:
        return None, None
    estatisticas = estatisticas_topicos_vistos(db, usuario.id, edital_id)
    itens = escolher_para_intercalar(topico.id, estatisticas, agora_utc())
    posicao = quantidade_no_bloco(db, usuario.id, topico.id)
    for candidato in ordem_para_tentar(posicao, itens):
        questao = proxima_questao(db, usuario.id, candidato.topico_id)
        if questao is not None:
            return candidato, questao
    return None, None


@router.get("/topico/{slug}/questoes")
def obter_questao(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    slug: str,
) -> Response:
    """Mostra a próxima questão do tópico, sem revelar o gabarito.

    Nativa ou, a cada 4ª posição do bloco, um item de outro tópico já visto (fio da memória, V5).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).
        slug: slug global do tópico.

    Returns:
        O HTML de `questoes/topico.html`; com `questao=None` no contexto quando não sobra
        nenhuma para este usuário (200, sem erro — decisão 7). Quando a questão é um item
        intercalado, o contexto ganha `fio_da_memoria={"motivo": ...}`.

    Raises:
        HTTPException: 404 se o tópico não pertencer a nenhum edital do tenant (decisão 2).
    """
    topico = _exigir_topico_do_tenant(db, slug, usuario)

    veredito = veredito_de_limite(db, usuario)
    if not veredito.permitido:
        contexto = contexto_questao(db, topico, None)
        contexto["limite"] = {"motivo": veredito.motivo, "convite": veredito.convite}
        return renderizar(request, "questoes/topico.html", contexto, usuario)

    item, questao_intercalada = _proximo_item_intercalado(db, usuario, topico)
    if item is not None and questao_intercalada is not None:
        contexto = contexto_questao(
            db,
            topico,
            questao_intercalada,
            acao_post=f"/topico/{topico.slug}/questoes",
            campos_ocultos=[
                ("fio_origem_topico_id", str(item.topico_id)),
                ("fio_motivo", item.motivo),
            ],
            fio_da_memoria={"motivo": item.motivo},
        )
        return renderizar(request, "questoes/topico.html", contexto, usuario)

    questao = proxima_questao(db, usuario.id, topico.id)
    contexto = contexto_questao(db, topico, questao, acao_post=f"/topico/{topico.slug}/questoes")
    return renderizar(request, "questoes/topico.html", contexto, usuario)


@router.post("/topico/{slug}/questoes")
def responder_questao(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    slug: str,
    resposta: Annotated[str, Form()],
    questao_id: Annotated[UUID, Form()],
    confianca: Annotated[str | None, Form()] = None,
    tempo_ms: Annotated[int, Form()] = 0,
    fio_origem_topico_id: Annotated[UUID | None, Form()] = None,
    fio_motivo: Annotated[str | None, Form()] = None,
) -> Response:
    """Registra a resposta à questão indicada e devolve o fragmento do resultado.

    O `questao_id` é obrigatório e vem de um campo oculto do formulário — a página só o
    preenche com o `id` da questão que ela de fato mostrou. A rota confere de novo que essa
    questão ainda está pendente para este usuário (`_questao_pendente`) antes de gravar
    qualquer coisa: sem essa checagem, duas abas abertas, um back/refresh ou qualquer corrida
    gravariam a resposta contra outra questão, e `evento_estudo` é append-only — não tem
    conserto depois. `fio_origem_topico_id`/`fio_motivo` (V5) só vêm preenchidos quando a
    questão mostrada era um item intercalado (`GET` os preenche via `campos_ocultos`) — nesse
    caso a checagem de pendência usa o tópico de origem do item, não o tópico da URL, e só
    aceita um `fio_origem_topico_id` que de fato pertença a um edital deste tenant
    (`_edital_do_topico_para_tenant`) — nunca um tópico de outro tenant.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        slug: slug global do tópico (a âncora do bloco, gravada em
            `evento_estudo.dados["bloco_topico_id"]`).
        resposta: `"C"`/`"E"` em `"certo_errado"`, `"A"`–`"E"` em `"multipla_escolha"` — o que
            o aluno marcou.
        questao_id: `id` da questão respondida, do campo oculto do formulário.
        confianca: `"certeza"`/`"duvida"`; `None` (campo ausente) é erro (decisão 3).
        tempo_ms: tempo gasto na questão, em milissegundos; `0` quando o cliente não manda.
        fio_origem_topico_id: tópico de origem do item intercalado, quando é o caso.
        fio_motivo: o motivo já formatado (`dominio.fio_memoria.ItemIntercalado.motivo`), para o
            resultado ecoar sem recalcular.

    Returns:
        O fragmento `questoes/_resultado.html` com o gabarito, o acerto e a origem (200).

    Raises:
        HTTPException: 404 se o tópico não pertencer a nenhum edital do tenant; 400 sem
            `confianca`/fora de `CONFIANCAS_VALIDAS`, ou com `resposta` fora do que
            `RESPOSTAS_VALIDAS_POR_TIPO` aceita para o `tipo_item` desta questão.
    """
    topico = _exigir_topico_do_tenant(db, slug, usuario)
    if confianca not in CONFIANCAS_VALIDAS:
        raise HTTPException(status_code=400, detail=MENSAGEM_CONFIANCA_OBRIGATORIA)

    intercalado = False
    if fio_origem_topico_id is not None:
        if _edital_do_topico_para_tenant(db, fio_origem_topico_id, usuario.tenant_id) is None:
            questao = None
        else:
            questao = _questao_pendente(db, usuario.id, fio_origem_topico_id, questao_id)
            intercalado = questao is not None
    else:
        questao = _questao_pendente(db, usuario.id, topico.id, questao_id)

    if questao is None:
        # A validação é idêntica a antes (404 lógico) — só a entrega muda: um 4xx aqui vira
        # JSON cru fora do htmx e não faz swap nenhum dentro dele (htmx 2 não troca em erro),
        # exatamente o cenário que o `questao_id` obrigatório existe para proteger (duas abas,
        # back/refresh). 200 com fragmento e um link de saída avisa a aluna de verdade.
        contexto = contexto_questao(db, topico, None)
        contexto["aviso"] = MENSAGEM_QUESTAO_INDISPONIVEL
        contexto["proximo_url"] = f"/topico/{topico.slug}/questoes"
        contexto["proximo_rotulo"] = "Próxima questão"
        return renderizar(request, "questoes/_resultado.html", contexto, usuario)

    # As respostas válidas dependem do tipo da questão de fato mostrada (não de um formato fixo
    # no formulário) — só se sabe depois de `_questao_pendente` confirmar qual questão é esta.
    respostas_validas = RESPOSTAS_VALIDAS_POR_TIPO[questao.tipo_item]
    if resposta not in respostas_validas:
        mensagem = MENSAGENS_RESPOSTA_INVALIDA_POR_TIPO[questao.tipo_item]
        raise HTTPException(status_code=400, detail=mensagem)

    agora = agora_utc()
    dados_evento: dict[str, object] = {"bloco_topico_id": str(topico.id)}
    fio_da_memoria: dict[str, object] | None = None
    if intercalado:
        dados_evento["fio_origem_topico_id"] = str(fio_origem_topico_id)
        if fio_motivo is not None:
            dados_evento["fio_motivo"] = fio_motivo
            fio_da_memoria = {"motivo": fio_motivo}
    evento = registrar_resposta(db, usuario, questao, resposta, confianca, tempo_ms, dados_evento)
    if not evento.acertou:
        # F4.3 (V4): o erro faz nascer (ou atualiza, idempotente) o cartão daquela questão.
        # Acertar nunca cria cartão nenhum. `cast`: `CONFIANCAS_VALIDAS` já garantiu, em tempo
        # de execução, que `confianca` só chega aqui como um dos dois valores do `Literal`.
        registrar_erro(db, usuario, questao, cast(Confianca, confianca), agora)
    db.commit()

    contexto = contexto_questao(db, topico, questao, fio_da_memoria=fio_da_memoria)
    contexto["evento"] = contexto_evento(db, questao, resposta, evento.acertou)
    contexto["proximo_url"] = f"/topico/{topico.slug}/questoes"
    contexto["proximo_rotulo"] = "Próxima questão"
    return renderizar(request, "questoes/_resultado.html", contexto, usuario)


@router.post("/questoes/{questao_id}/reportar")
def reportar_questao(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    questao_id: UUID,
    motivo: Annotated[str, Form()],
) -> Response:
    """Registra o reporte de erro de uma questão (some da fila só de quem reportou — premissa H).

    Mesmo isolamento por tenant das outras duas rotas (`_questao_do_tenant`): sem ele, qualquer
    logado reportaria qualquer questão do pool global só sabendo o `id` — o dano de reportar é
    nulo (só esconde para quem reportou), mas a fila do calibrador (fatia 8) vai ler
    `reporte_erro`, então o registro tem de ser de uma questão que este tenant de fato usa.

    Args:
        request: a requisição atual — decide se a resposta é o fragmento HTMX (`HX-Request:
            true`) ou a página inteira (POST direto do formulário, sem JS).
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        questao_id: chave da questão reportada.
        motivo: o texto livre do reporte.

    Returns:
        `questoes/_reportado.html` (fragmento, 200) sob htmx; `questoes/reportado.html` (página
        inteira, 200) fora dele — nunca um `<p>` solto sem navegação.

    Raises:
        HTTPException: 404 se a questão não existir ou não pertencer a um edital do tenant.
    """
    questao = _questao_do_tenant(db, questao_id, usuario.tenant_id)
    if questao is None:
        raise HTTPException(status_code=404, detail=MENSAGEM_QUESTAO_NAO_ENCONTRADA)
    registrar_reporte(db, usuario, questao, motivo)
    db.commit()
    nome_template = "questoes/_reportado.html" if _eh_htmx(request) else "questoes/reportado.html"
    return renderizar(request, nome_template, {}, usuario)


def _cartao_pendente(
    db: Session, usuario_id: UUID, cartao_id: UUID, questao_id: UUID
) -> Cartao | None:
    """O cartão só é aceito se pertence a este usuário e ainda aponta para a mesma questão.

    Mesmo espírito de `_questao_pendente`: um `cartao_id`/`questao_id` de outra conta, ou
    adulterado no formulário, não pode gravar `revisao_cartao` nenhum.

    Args:
        db: sessão do request.
        usuario_id: quem está revisando.
        cartao_id: `cartao_id` que veio do formulário.
        questao_id: `questao_id` que veio do formulário — tem de bater com o do cartão.

    Returns:
        O `Cartao`, ou `None` se não existir, não for deste usuário, ou apontar para outra
        questão.
    """
    cartao = db.get(Cartao, cartao_id)
    if cartao is None or cartao.usuario_id != usuario_id or cartao.questao_id != questao_id:
        return None
    return cartao


@router.get("/revisar")
def obter_revisao(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
) -> Response:
    """Mostra o cartão vencido mais antigo (ordem do FSRS), reaproveitando a tela de questão.

    "A revisão de um cartão de questão é, na prática, a questão de novo" (plano V4 §5): o
    parcial e os helpers são os mesmos de `/topico/{slug}/questoes`, só o `acao_post` e o campo
    oculto `cartao_id` mudam.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).

    Returns:
        `questoes/revisao.html`; com `questao=None` quando não há nenhum cartão vencido, ou
        (fora do escopo desta fatia — nenhum cartão manual existe ainda) o cartão vencido não
        tem `questao` ligada (200 nos dois casos, nunca erro).
    """
    vencidos = cartoes_vencidos(db, usuario.id, agora_utc())
    cartao = vencidos[0] if vencidos else None
    if cartao is None:
        return renderizar(request, "questoes/revisao.html", {"questao": None}, usuario)

    questao = cartao.questao
    topico = cartao.topico
    if questao is None:
        # Fora do escopo desta fatia — nenhum cartão manual (sem questão ligada) existe ainda —,
        # mas a tela não quebra se um aparecer: mesma resposta de "nada para revisar".
        return renderizar(request, "questoes/revisao.html", {"questao": None}, usuario)

    contexto = contexto_questao(
        db, topico, questao, acao_post="/revisar", campos_ocultos=[("cartao_id", str(cartao.id))]
    )
    return renderizar(request, "questoes/revisao.html", contexto, usuario)


@router.post("/revisar")
def responder_revisao(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    resposta: Annotated[str, Form()],
    questao_id: Annotated[UUID, Form()],
    cartao_id: Annotated[UUID, Form()],
    confianca: Annotated[str | None, Form()] = None,
    tempo_ms: Annotated[int, Form()] = 0,
) -> Response:
    """Registra a revisão de um cartão vencido: grava `revisao_cartao` e atualiza o FSRS.

    As duas gravações de `repositorio_cartao.revisar_cartao` acontecem sempre juntas (evento +
    estado) — esta rota nunca faz só uma.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (o commit é feito aqui).
        usuario: o usuário logado.
        resposta: o que a pessoa respondeu ao cartão.
        questao_id: `id` da questão do cartão, do campo oculto do formulário.
        cartao_id: `id` do cartão revisado, do campo oculto do formulário.
        confianca: `"certeza"`/`"duvida"`; `None` (campo ausente) é erro (decisão 3, igual à
            tela de questão).
        tempo_ms: tempo gasto na revisão, em milissegundos; `0` quando o cliente não manda.

    Returns:
        O fragmento `questoes/_resultado.html`, com o link "Próxima revisão".

    Raises:
        HTTPException: 400 sem `confianca` válida, ou com `resposta` fora do que
            `RESPOSTAS_VALIDAS_POR_TIPO` aceita para o `tipo_item` da questão do cartão.
    """
    if confianca not in CONFIANCAS_VALIDAS:
        raise HTTPException(status_code=400, detail=MENSAGEM_CONFIANCA_OBRIGATORIA)

    cartao = _cartao_pendente(db, usuario.id, cartao_id, questao_id)
    if cartao is None or cartao.questao is None:
        # Mesma postura de `_questao_pendente`: 200 com aviso, nunca um 4xx que não faz swap
        # dentro do htmx.
        contexto: dict[str, object] = {
            "aviso": MENSAGEM_QUESTAO_INDISPONIVEL,
            "proximo_url": "/revisar",
            "proximo_rotulo": "Próxima revisão",
        }
        return renderizar(request, "questoes/_resultado.html", contexto, usuario)

    questao = cartao.questao
    respostas_validas = RESPOSTAS_VALIDAS_POR_TIPO[questao.tipo_item]
    if resposta not in respostas_validas:
        mensagem = MENSAGENS_RESPOSTA_INVALIDA_POR_TIPO[questao.tipo_item]
        raise HTTPException(status_code=400, detail=mensagem)

    evento = revisar_cartao(
        db,
        usuario,
        cartao,
        acertou=resposta == questao.gabarito,
        resposta=resposta,
        confianca=cast(Confianca, confianca),
        tempo_ms=tempo_ms,
        agora=agora_utc(),
    )
    db.commit()

    contexto = contexto_questao(db, cartao.topico, questao)
    contexto["evento"] = contexto_evento(db, questao, resposta, evento.acertou)
    contexto["proximo_url"] = "/revisar"
    contexto["proximo_rotulo"] = "Próxima revisão"
    return renderizar(request, "questoes/_resultado.html", contexto, usuario)


def _contexto_aula(aula: Aula) -> dict[str, object]:
    """Monta o contexto de `aula/ver.html` a partir da `Aula` já publicada.

    `renderizar_com_notas` troca cada marcador `{{citação}}` do texto por uma nota numerada
    `[n]`, listada abaixo do texto com o mesmo popover `<details>`/`<summary>` do resultado de
    questão (`web/templates/_macros.html`) — a citação já traz o trecho literal embutido
    (`Aula.citacoes`), sem precisar juntar com `dispositivo_legal`.

    Args:
        aula: a `Aula` publicada a exibir.

    Returns:
        O dicionário de contexto do template, com `texto_denso`/`texto_leigo` já sem marcador
        cru e as respectivas listas de notas.
    """
    citacoes = [CitacaoAula.model_validate(c) for c in aula.citacoes]
    denso_html, notas_denso = renderizar_com_notas(aula.texto_denso, citacoes)
    leigo_html, notas_leigo = renderizar_com_notas(aula.texto_leigo, citacoes)
    return {
        "texto_denso": denso_html,
        "notas_denso": notas_denso,
        "texto_leigo": leigo_html,
        "notas_leigo": notas_leigo,
        "relacionados": aula.relacionados,
        "como_a_banca_cobra": aula.como_a_banca_cobra,
        "lacunas_declaradas": aula.lacunas_declaradas,
        "mnemonico": aula.mnemonico,
    }


@router.get("/topico/{slug}/aula")
def obter_aula(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    slug: str,
) -> Response:
    """Mostra a aula publicada do tópico (fatia 6), ou o aviso de que ainda não existe.

    A aula é gerada offline pelo comando `motor.aula` (com o validador mecânico já aprovando
    antes de publicar) — esta rota só lê e renderiza, nunca gera na hora.

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado.
        slug: slug global do tópico.

    Returns:
        O HTML de `aula/ver.html`; com `aula=None` no contexto quando o tópico ainda não tem
        aula publicada (200, sem erro — mesma decisão de "sem questão" da tela de questão).

    Raises:
        HTTPException: 404 se o tópico não pertencer a nenhum edital do tenant.
    """
    topico = _exigir_topico_do_tenant(db, slug, usuario)
    aula = aula_publicada_do_topico(db, topico.id)
    contexto: dict[str, object] = {"topico": topico, "aula": aula}
    if aula is not None:
        contexto.update(_contexto_aula(aula))
    return renderizar(request, "aula/ver.html", contexto, usuario)

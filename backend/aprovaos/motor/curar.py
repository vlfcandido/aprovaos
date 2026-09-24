"""O comando de curadoria: liga segmentação, gabarito, classificação e o gate de publicação.

O que é: `curar_documento(db, config, documento_prova_id, documento_gabarito_id, edital_id)` —
o pipeline completo de um caderno já coletado (passo 5): lê os dois PDFs do disco, monta a
`OrigemBase` a partir do `Documento` da prova, escolhe o classificador (IA quando há
`GOOGLE_API_KEY` e teto diário, senão `ClassificadorPorRegras` — mesmo desenho de
`agentes.classificador.escolher_classificador`, mas sem usuário autenticado: este é um comando,
não uma rota, e a linha de `traco` de cada chamada fica com `usuario_id=None`), roda `curar`
(passo 9; `--tipo-item` escolhe C/E ou múltipla escolha A–E — passo 2 da V3b) e grava com
`salvar_questoes` (passo 11). `RelatorioCuradoria` é o que volta para quem chama e para o diário
da fatia (`docs/fatias/V3-execucao.md`): total, publicáveis, anuladas, sem tópico e — quando a
segmentação ou o gabarito não bateram — os problemas, sem gravar nenhuma linha (decisão do dono,
passo 12: `pendente_revisao` não grava nada).

`main()` é o `argparse` que resolve o par prova+gabarito a partir de `--evento`/`--cargo` (mesma
filtragem do passo 5, `motor.coletar.arquivos_do_cargo`, sobre o que já está em `documento`) e
chama `curar_documento` com `asyncio.run` (`curar` é `async`). O pareamento de `--evento`/`--cargo`
para os dois `Documento` é resolvido aqui, em `main()` — nunca dentro de `curar_documento`, que
recebe os dois ids já resolvidos e nunca adivinha o par (decisão do dono, passo 12).
`--reclassificar` (passo 12b) troca `salvar_questoes` por `atualizar_classificacao`: útil para
rodar de novo com `GOOGLE_API_KEY` um caderno que já foi curado por regras, sem duplicar nada.

Nenhuma execução acontece em import: `main()` só roda sob `if __name__ == "__main__"`, e é quem
abre o engine do banco — o dono desse ciclo de vida é este módulo.

Quando ler: ao rodar a curadoria de um concurso já coletado, ou ao investigar por que um caderno
saiu `pendente_revisao` ou com poucos tópicos identificados.
"""

import argparse
import asyncio
import re
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.agentes.classificador import MOTIVO_SEM_CHAVE, MOTIVO_TETO, criar_classificador_adk
from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.modelos import Documento, Topico, TopicoEdital
from aprovaos.dados.repositorio_questao import atualizar_classificacao, salvar_questoes
from aprovaos.dados.repositorio_traco import registrar_traco
from aprovaos.dominio.pdf import extrair_texto
from aprovaos.dominio.questao import RegraProva
from aprovaos.motor.coletar import resolver_documentos_dir
from aprovaos.motor.curadoria.classificacao import ClassificadorDeTopico, TopicoVocabulario
from aprovaos.motor.curadoria.curador import OrigemBase, TipoItem, curar, verificar_curadoria
from aprovaos.roteador.custo import ChamadaLlm
from aprovaos.roteador.teto import TetoDiario

BANCA = "cebraspe"
"""Única banca que este comando cura (decisão J do plano da V3 — C/E e A–E, nunca FGV)."""

_PADRAO_CARGO_NA_DESCRICAO = re.compile(r"CARGO\s+(\d+)\s*$", re.IGNORECASE)
_PADRAO_TOKEN_DE_ANO = re.compile(r"^\d{2}$")

# A Cebraspe C/E costuma anular por erro (resposta errada zera uma certa), mas essa regra é do
# edital de cada concurso de origem — os cadernos desta fatia vêm de concursos cujo edital a V3
# não leu (só a prova e o gabarito, coletados no passo 5). `RegraProva` não decide `publicavel`
# (`dominio.questao.decidir_publicacao` não a consulta, só o gate de tópico/origem/gabarito faz
# isso) — por isso o valor entra com a fonte marcada como não verificada, em vez de fingir ter
# lido a instrução do caderno (que, medido no passo 12, nem está no texto extraído da prova).
_REGRA_PROVA_PADRAO = RegraProva(
    anula_por_erro=True,
    fonte="convenção Cebraspe C/E — edital do concurso de origem não lido nesta fatia",
)

# Múltipla escolha não tem o mecanismo "resposta errada anula uma certa" do C/E — cada questão
# vale sozinha; não é suposição, é a forma do item (uma única resposta por questão, sem par
# certo/errado para anular). Mesmo motivo de fonte "não verificada" da constante acima: o edital
# do concurso de origem não foi lido nesta fatia.
_REGRA_PROVA_PADRAO_MULTIPLA_ESCOLHA = RegraProva(
    anula_por_erro=False,
    fonte=(
        "convenção Cebraspe A–E — múltipla escolha não tem par certo/errado para anular; "
        "edital do concurso de origem não lido nesta fatia"
    ),
)


class DocumentoNaoEncontrado(RuntimeError):
    """`documento_prova_id`/`documento_gabarito_id` não existem, ou `main()` não achou o par.

    `curar_documento` nunca adivinha um documento substituto — a mesma decisão de
    `motor.coletar.ProvaSemGabarito` para o passo 5.
    """


class ParDivergente(RuntimeError):
    """A prova e o gabarito dados não são do mesmo evento/cargo (achado da revisão do passo 12).

    `curar_documento` recebe os dois ids já resolvidos e nunca adivinha o par — mas até este
    conserto também nunca *conferia* que os dois eram, de fato, o mesmo par: uma chamada fora de
    `main()` com um par trocado gerava uma `Origem` só com os dados da prova e lia o gabarito de
    outro caderno como se fosse dela, silenciosamente (nenhuma exceção, nenhum teste pegava
    isso). Esta é a asserção redundante que fecha esse buraco — barata de checar, porque os dois
    valores (`evento`, `cargo`) já são exatamente o que `_origem_base` deriva de qualquer forma.
    """


class RelatorioCuradoria(BaseModel):
    """O que `curar_documento` devolve — o que entra no diário da fatia (`V3-execucao.md`).

    Attributes:
        total: itens do caderno; `0` quando `pendente_revisao` (nada foi processado até o fim).
        publicaveis: quantos ficaram com `publicavel=True` (gate de `dominio.questao`).
        anuladas: quantos itens a banca anulou (`gabarito_status == "anulado"`).
        sem_topico: quantos ficaram sem `topico_slug` — o vocabulário do edital não cobre.
        pendente_revisao: `True` quando nada foi gravado em `questao` (segmentação ambígua,
            gabarito Cebraspe C/E não reconhecido, ou contagem de itens divergente do gabarito).
        problemas: o motivo de cada violação (de `curar`, quando `pendente_revisao`, ou de
            `verificar_curadoria`, quando não); lista vazia quando nada deu errado.
        novas: quantas linhas novas `salvar_questoes` gravou; `0` quando `pendente_revisao` ou
            `reclassificar=True` (reclassificar nunca cria linha).
        repetidas: quantas já existiam (dedup por `hash_dedup`); `0` quando `pendente_revisao`
            ou `reclassificar=True`.
        atualizadas: quantas linhas `atualizar_classificacao` (passo 12b) mudou de
            tópico/publicável; `0` fora do modo `reclassificar=True`.
        preservadas: quantas linhas mantiveram a classificação anterior porque a nova rodada
            veio **sem** tópico (P-76 — reclassificar nunca rebaixa); `0` fora do modo
            `reclassificar=True`.
        nao_encontradas: quantas `hash_dedup` do lote reclassificado não bateram com nenhuma
            linha existente (nada foi criado para elas); `0` fora do modo `reclassificar=True`.
    """

    total: int
    publicaveis: int
    anuladas: int
    sem_topico: int
    pendente_revisao: bool
    problemas: list[str]
    novas: int
    repetidas: int
    atualizadas: int = 0
    preservadas: int = 0
    nao_encontradas: int = 0


def _vocabulario_do_edital(db: Session, edital_id: UUID) -> list[TopicoVocabulario]:
    """Os tópicos do conteúdo programático do edital, no contrato do classificador.

    Args:
        db: sessão de banco.
        edital_id: chave do `Edital` cujo vocabulário classifica os itens do caderno.

    Returns:
        Um `TopicoVocabulario` por `TopicoEdital` do edital, na ordem do edital; lista vazia se
        o edital não tiver tópicos (nada será publicável — o gate de `dominio.questao` barra por
        "tópico não identificado").
    """
    consulta = (
        select(TopicoEdital, Topico)
        .join(Topico, TopicoEdital.topico_id == Topico.id)
        .where(TopicoEdital.edital_id == edital_id)
        .order_by(TopicoEdital.ordem)
    )
    return [
        TopicoVocabulario(
            slug=topico.slug, materia=topico.materia, texto_original=linha.texto_original
        )
        for linha, topico in db.execute(consulta).all()
    ]


def _orgao_e_ano_do_evento(evento: str) -> tuple[str, int]:
    """Extrai `(orgao, ano)` do `eventoURL` (ex.: `"TJ_PA_25_SERVIDOR"` → `("TJ-PA", 2025)`).

    O primeiro token puramente numérico de 2 dígitos é o ano (`20` + os 2 dígitos); os tokens
    antes dele, unidos por hífen, são o órgão. Sempre a partir do mesmo `eventoURL` que o
    coletor já gravou em `documento.metadados["evento"]` (passo 5) — nunca remontado de outra
    fonte nem de memória.

    Args:
        evento: `documento.metadados["evento"]` do `Documento` da prova.

    Returns:
        `(orgao, ano)`.

    Raises:
        ValueError: nenhum token de 2 dígitos encontrado (formato de `eventoURL` não conhecido).
    """
    partes = evento.split("_")
    indice_ano = next(
        (indice for indice, parte in enumerate(partes) if _PADRAO_TOKEN_DE_ANO.fullmatch(parte)),
        None,
    )
    if indice_ano is None:
        raise ValueError(f"evento sem token de ano reconhecível: {evento!r}")
    return "-".join(partes[:indice_ano]), 2000 + int(partes[indice_ano])


def _cargo_da_descricao(descricao: str) -> str:
    """`"PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS – CARGO 9"` → `"CARGO 9"`.

    Só o identificador do cargo tal como o coletor gravou em `documento.metadados["descricao"]`
    — sem inventar um nome de cargo que este passo não confirmou (ex.: "Analista Judiciário —
    Direito" exigiria reabrir a API/o edital do concurso de origem, fora do escopo do passo 12).

    Args:
        descricao: `documento.metadados["descricao"]` do `Documento` da prova.

    Returns:
        `"CARGO <número>"`.

    Raises:
        ValueError: a descrição não termina em `"CARGO <número>"`.
    """
    encontrado = _PADRAO_CARGO_NA_DESCRICAO.search(descricao)
    if encontrado is None:
        raise ValueError(f"descrição sem cargo reconhecível: {descricao!r}")
    return f"CARGO {encontrado.group(1)}"


def _origem_base(documento_prova: Documento) -> OrigemBase:
    """Monta `OrigemBase` a partir do `Documento` da prova gravado pelo coletor (passo 5).

    Args:
        documento_prova: o `Documento` de tipo `"prova"`.

    Returns:
        `OrigemBase` com `banca="cebraspe"`, `orgao`/`ano` extraídos do evento e `cargo`
        extraído da descrição do arquivo — nunca remontados de memória (mesma exigência da
        skill `ingestao-de-provas` para os campos de `origem`).
    """
    evento = documento_prova.metadados["evento"]
    orgao, ano = _orgao_e_ano_do_evento(evento)
    cargo = _cargo_da_descricao(documento_prova.metadados["descricao"])
    return OrigemBase(
        banca=BANCA,
        orgao=orgao,
        cargo=cargo,
        ano=ano,
        tipo_caderno=None,
        url_prova=documento_prova.metadados["url_origem"],
        documento_id=str(documento_prova.id),
    )


def _escolher_classificador(
    db: Session, config: Configuracoes
) -> tuple[ClassificadorDeTopico | None, str | None]:
    """Decide se a IA classifica: sem chave ou sem teto → `None` com o motivo; senão o ADK.

    Mesmo padrão de `agentes.classificador.escolher_classificador`, mas sem usuário autenticado
    — este é um comando, não uma rota; a linha de `traco` de cada chamada fica com
    `usuario_id=None`.

    Args:
        db: sessão de banco (lê o gasto do dia para o teto).
        config: configurações (`google_api_key`, `teto_diario_brl`).

    Returns:
        `(classificador, None)` quando a IA pode ser chamada; `(None, motivo)` quando não.
    """
    if config.google_api_key is None:
        return None, MOTIVO_SEM_CHAVE
    if not TetoDiario(config.teto_diario_brl).pode_chamar(db, agora_utc()):
        return None, MOTIVO_TETO

    def registrar(chamada: ChamadaLlm) -> None:
        registrar_traco(db, chamada, usuario_id=None)

    return criar_classificador_adk(config, registrar), None


def _conferir_par(documento_prova: Documento, documento_gabarito: Documento) -> None:
    """Confere que os dois documentos são do mesmo evento/cargo (achado da revisão do passo 12).

    Usa os mesmos dois campos que `_origem_base` já deriva de `documento_prova` — nenhum campo
    novo, nenhuma consulta nova; só compara o que a prova diz com o que o gabarito diz.

    Args:
        documento_prova: o `Documento` de tipo `"prova"`.
        documento_gabarito: o `Documento` de tipo `"gabarito"`.

    Raises:
        ParDivergente: `evento` ou `cargo` divergem entre os dois.
    """
    evento_prova = documento_prova.metadados.get("evento")
    evento_gabarito = documento_gabarito.metadados.get("evento")
    cargo_prova = _cargo_da_descricao(documento_prova.metadados.get("descricao", ""))
    cargo_gabarito = _cargo_da_descricao(documento_gabarito.metadados.get("descricao", ""))
    if evento_prova != evento_gabarito or cargo_prova != cargo_gabarito:
        raise ParDivergente(
            f"prova ({evento_prova}, {cargo_prova}) ≠ gabarito ({evento_gabarito}, "
            f"{cargo_gabarito})"
        )


async def curar_documento(
    db: Session,
    config: Configuracoes,
    documento_prova_id: UUID,
    documento_gabarito_id: UUID,
    edital_id: UUID,
    *,
    reclassificar: bool = False,
    tipo_item: TipoItem = "certo_errado",
) -> RelatorioCuradoria:
    """Cura um caderno já coletado e grava as questões publicáveis (passo 12 da V3; passo 2 da V3b).

    Lê os dois PDFs do disco (`resolver_documentos_dir(config) / documento.caminho`), monta a
    `OrigemBase` a partir do `Documento` da prova, classifica cada item no vocabulário de
    `edital_id` (IA quando há `GOOGLE_API_KEY` e teto, senão `ClassificadorPorRegras`) e grava
    com `salvar_questoes` (dedup por `hash_dedup`; grava também as alternativas quando
    `tipo_item="multipla_escolha"`) — ou, com `reclassificar=True`, atualiza as linhas já
    gravadas por `atualizar_classificacao` (passo 12b) em vez de gravar de novo: é o caminho para
    rodar `curar` outra vez sobre o mesmo par, agora com um classificador melhor (ex.: a chave
    chegou depois da primeira rodada por regras), sem duplicar nada.
    `pendente_revisao=True` não grava/atualiza nenhuma linha em `questao` — o motivo vai em
    `problemas`. Faz `add`/`flush`; o `commit` é de quem chama (`main()`, ou o teste).

    Args:
        db: sessão de banco.
        config: configurações do backend (`documentos_dir`, `google_api_key`,
            `teto_diario_brl`, `lote_classificacao`).
        documento_prova_id: chave do `Documento` (`tipo="prova"`) já gravado pelo coletor.
        documento_gabarito_id: chave do `Documento` (`tipo="gabarito"`) correspondente — o
            pareamento é decidido por quem chama (`main()`, a partir de `--evento`/`--cargo`);
            esta função nunca adivinha o par (decisão do dono, passo 12).
        edital_id: chave do `Edital` cujo vocabulário de tópicos classifica os itens.
        reclassificar: `False` (padrão) grava questão nova por `salvar_questoes`; `True`
            reclassifica as já gravadas (mesmo `hash_dedup`) por `atualizar_classificacao` — só
            `topico_id`/`topico_confianca`/`topico_evidencia`/`publicavel`/
            `motivo_nao_publicavel` mudam, o texto/gabarito/origem gravados na curadoria
            original continuam os mesmos.
        tipo_item: `"certo_errado"` (padrão, Cebraspe C/E) ou `"multipla_escolha"` (Cebraspe
            A–E, nível médio) — decide a segmentação, a leitura do gabarito e a regra de prova
            padrão (`_REGRA_PROVA_PADRAO`/`_REGRA_PROVA_PADRAO_MULTIPLA_ESCOLHA`).

    Returns:
        `RelatorioCuradoria` com as contagens e, quando algo deu errado, os problemas.

    Raises:
        DocumentoNaoEncontrado: `documento_prova_id` ou `documento_gabarito_id` não existem.
        ParDivergente: os dois documentos não são do mesmo evento/cargo.
    """
    documento_prova = db.get(Documento, documento_prova_id)
    if documento_prova is None:
        raise DocumentoNaoEncontrado(f"documento {documento_prova_id} não encontrado")
    documento_gabarito = db.get(Documento, documento_gabarito_id)
    if documento_gabarito is None:
        raise DocumentoNaoEncontrado(f"documento {documento_gabarito_id} não encontrado")
    _conferir_par(documento_prova, documento_gabarito)

    documentos_dir = resolver_documentos_dir(config)
    texto_prova = extrair_texto((documentos_dir / documento_prova.caminho).read_bytes())
    texto_gabarito = extrair_texto((documentos_dir / documento_gabarito.caminho).read_bytes())

    vocabulario = _vocabulario_do_edital(db, edital_id)
    origem_base = _origem_base(documento_prova)
    classificador_ia, motivo_sem_ia = _escolher_classificador(db, config)
    regra_prova = (
        _REGRA_PROVA_PADRAO if tipo_item == "certo_errado" else _REGRA_PROVA_PADRAO_MULTIPLA_ESCOLHA
    )

    resultado = await curar(
        texto_prova=texto_prova,
        texto_gabarito=texto_gabarito,
        vocabulario=vocabulario,
        origem_base=origem_base,
        regra_prova=regra_prova,
        classificador_ia=classificador_ia,
        motivo_sem_ia=motivo_sem_ia,
        tipo_item=tipo_item,
        tamanho_lote=config.lote_classificacao,
    )

    if resultado.pendente_revisao:
        return RelatorioCuradoria(
            total=0,
            publicaveis=0,
            anuladas=0,
            sem_topico=0,
            pendente_revisao=True,
            problemas=resultado.problemas,
            novas=0,
            repetidas=0,
        )

    problemas = verificar_curadoria(resultado.questoes, total_itens=len(resultado.questoes))
    if reclassificar:
        atualizadas, nao_encontradas, preservadas = atualizar_classificacao(db, resultado.questoes)
        novas, repetidas = 0, 0
    else:
        novas, repetidas = salvar_questoes(db, resultado.questoes)
        atualizadas, nao_encontradas, preservadas = 0, 0, 0
    return RelatorioCuradoria(
        total=len(resultado.questoes),
        publicaveis=sum(1 for questao in resultado.questoes if questao.publicavel),
        anuladas=sum(1 for questao in resultado.questoes if questao.gabarito_status == "anulado"),
        sem_topico=sum(1 for questao in resultado.questoes if questao.topico_slug is None),
        pendente_revisao=False,
        problemas=problemas,
        novas=novas,
        repetidas=repetidas,
        atualizadas=atualizadas,
        preservadas=preservadas,
        nao_encontradas=nao_encontradas,
    )


def _documento_do_par(db: Session, evento: str, cargo: int, tipo: str) -> Documento:
    """Acha, em `documento`, o `tipo` (`"prova"`/`"gabarito"`) do evento/cargo pedidos.

    Mesma filtragem do passo 5 (`motor.coletar.arquivos_do_cargo`), sobre o que já está
    persistido: casa `metadados["evento"] == evento` e `metadados["descricao"]` terminando em
    `"CARGO <cargo>"`.

    Args:
        db: sessão de banco.
        evento: `eventoURL` (o mesmo usado na coleta, passo 5).
        cargo: número do cargo (o mesmo usado na coleta).
        tipo: `"prova"` ou `"gabarito"`.

    Returns:
        O `Documento` encontrado.

    Raises:
        DocumentoNaoEncontrado: nenhum `Documento` desse tipo casa o evento/cargo pedidos.
    """
    terminacao = re.compile(rf"CARGO\s+{cargo}\s*$", re.IGNORECASE)
    candidatos = db.scalars(select(Documento).where(Documento.tipo == tipo)).all()
    for documento in candidatos:
        if documento.metadados.get("evento") != evento:
            continue
        if terminacao.search(documento.metadados.get("descricao", "")):
            return documento
    raise DocumentoNaoEncontrado(f"{evento} (cargo {cargo}): nenhum documento {tipo} encontrado")


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Cura um caderno Cebraspe já coletado (C/E ou múltipla escolha A–E): segmenta, lê "
            "o gabarito, classifica no vocabulário do edital dado e grava as questões "
            "publicáveis."
        )
    )
    parser.add_argument("--evento", required=True, help="eventoURL (ex.: TJ_PA_25_SERVIDOR)")
    parser.add_argument(
        "--cargo", required=True, type=int, help="número do cargo (o mesmo usado na coleta)"
    )
    parser.add_argument(
        "--edital", required=True, type=UUID, help="id do edital cujo vocabulário classifica"
    )
    parser.add_argument(
        "--tipo-item",
        choices=("certo_errado", "multipla_escolha"),
        default="certo_errado",
        help=(
            "certo_errado (padrão, Cebraspe C/E) ou multipla_escolha (Cebraspe A–E, nível "
            "médio) — passo 2 da fatia V3b"
        ),
    )
    parser.add_argument(
        "--reclassificar",
        action="store_true",
        help=(
            "reclassifica as questões já gravadas deste par (por hash_dedup) em vez de gravar "
            "de novo — use depois de rodar sem chave e a chave chegar (passo 12b)"
        ),
    )
    return parser.parse_args(argv)


def _relatar(evento: str, cargo: int, relatorio: RelatorioCuradoria) -> None:
    """Imprime o resumo de `relatorio` no formato usado pelo diário da fatia."""
    print(
        f"{evento} (cargo {cargo}): total={relatorio.total} publicaveis={relatorio.publicaveis} "
        f"anuladas={relatorio.anuladas} sem_topico={relatorio.sem_topico} "
        f"novas={relatorio.novas} repetidas={relatorio.repetidas} "
        f"atualizadas={relatorio.atualizadas} preservadas={relatorio.preservadas} "
        f"nao_encontradas={relatorio.nao_encontradas}"
    )
    if relatorio.pendente_revisao:
        print(f"{evento} (cargo {cargo}): PENDENTE_REVISAO — " + "; ".join(relatorio.problemas))
    elif relatorio.problemas:
        print(f"{evento} (cargo {cargo}): problemas — " + "; ".join(relatorio.problemas))


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando de curadoria.

    Resolve o par prova+gabarito a partir de `--evento`/`--cargo` (sobre o que o passo 5 já
    coletou), roda `curar_documento` com `asyncio.run` e faz o `commit` — o dono desse ciclo de
    vida é este módulo, nunca `curar_documento`.

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv` (padrão do `argparse`).
        config: configurações explícitas (testes); `None` lê do ambiente/.env.

    Returns:
        `0` sempre que o comando roda até o fim.

    Raises:
        DocumentoNaoEncontrado: `--evento`/`--cargo` não casam com nenhum par prova+gabarito já
            coletado.
    """
    argumentos = _analisar_argumentos(argv)
    config = config or obter_configuracoes()

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db:
        documento_prova = _documento_do_par(db, argumentos.evento, argumentos.cargo, "prova")
        documento_gabarito = _documento_do_par(db, argumentos.evento, argumentos.cargo, "gabarito")
        relatorio = asyncio.run(
            curar_documento(
                db,
                config,
                documento_prova.id,
                documento_gabarito.id,
                argumentos.edital,
                reclassificar=argumentos.reclassificar,
                tipo_item=argumentos.tipo_item,
            )
        )
        db.commit()
    _relatar(argumentos.evento, argumentos.cargo, relatorio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

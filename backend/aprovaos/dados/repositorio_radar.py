"""Repositório do radar: sincroniza o catálogo da Cebraspe em `concurso_radar` (fatia 1b, F1.1).

O que é: `obter_ou_criar_fonte` (get-or-create de `fonte`, espelho de `knowledge/fontes.yaml`),
`sincronizar` (insere o que é novo, atualiza o que mudou, carimba `ultimo_visto_em` em tudo que
veio, **nunca apaga**) e as consultas `listar`/`buscar_por_evento_url` que as rotas do radar
usam. Quando ler: ao mexer no comando `motor/radar.py::varrer` ou nas rotas `api/radar.py`. As
funções fazem `add`/`flush`; o `commit` é sempre do comando/rota (convenção transversal).
"""

from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.dados.modelos import ConcursoRadar, Fonte
from aprovaos.dominio.radar import ConcursoDoRadar

#: O mesmo literal de `motor.fontes.cebraspe.URL_DETALHE`, duplicado aqui de propósito: `dados/`
#: nunca importa de `motor/` (a direção inversa da arquitetura — motor depende de dados, não o
#: contrário). `test_repositorio_radar.py::test_url_detalhe_bate_com_a_fonte_cebraspe` garante
#: que os dois literais não divergem.
URL_DETALHE_CEBRASPE = "https://apis.cebraspe.org.br/cebraspe/eventos/{eventoURL}"


class RelatorioSincronizacao(BaseModel):
    """O relatório de uma rodada de `sincronizar` — o que o diário da fatia e o comando registram.

    Attributes:
        novos: quantos `evento_url` não existiam em `concurso_radar` e foram inseridos.
        atualizados: quantos já existiam e tiveram algum campo mudado.
        inalterados: quantos já existiam e vieram idênticos (só `ultimo_visto_em` avançou).
    """

    novos: int
    atualizados: int
    inalterados: int


def obter_ou_criar_fonte(db: Session, id_externo: str, nome: str, url_lista: str) -> Fonte:
    """Get-or-create da linha `fonte` (espelho de `knowledge/fontes.yaml`) pelo `id_externo`.

    Args:
        db: sessão do comando.
        id_externo: o `id` da ficha (ex.: `"cebraspe"`).
        nome: `Fonte.nome`, só usado ao criar.
        url_lista: `Fonte.url_lista`, só usado ao criar.

    Returns:
        A `Fonte` existente, ou uma nova com `status="ativa"`.
    """
    fonte = db.scalars(select(Fonte).where(Fonte.id_externo == id_externo)).first()
    if fonte is not None:
        return fonte
    fonte = Fonte(id_externo=id_externo, nome=nome, url_lista=url_lista, status="ativa")
    db.add(fonte)
    db.flush()
    return fonte


def _mudou(existente: ConcursoRadar, novo: ConcursoDoRadar) -> bool:
    """`True` quando algum campo visível do catálogo mudou desde a última varredura."""
    return (
        existente.nome != novo.nome
        or existente.fase != novo.fase
        or existente.uf != novo.uf
        or existente.vagas != novo.vagas
        or existente.salario_max_brl != novo.salario_max_brl
        or existente.periodo_inscricao_texto != novo.periodo_inscricao_texto
        or existente.inscricao_inicio != novo.inscricao_inicio
        or existente.inscricao_fim != novo.inscricao_fim
        or existente.lacunas != novo.lacunas
    )


def _aplicar(existente: ConcursoRadar, novo: ConcursoDoRadar) -> None:
    """Copia os campos de `novo` para a linha `existente` (usado só quando `_mudou` é `True`)."""
    existente.nome = novo.nome
    existente.fase = novo.fase
    existente.uf = novo.uf
    existente.vagas = novo.vagas
    existente.salario_max_brl = novo.salario_max_brl
    existente.periodo_inscricao_texto = novo.periodo_inscricao_texto
    existente.inscricao_inicio = novo.inscricao_inicio
    existente.inscricao_fim = novo.inscricao_fim
    existente.lacunas = list(novo.lacunas)
    existente.bruto = novo.model_dump(mode="json")


def sincronizar(
    db: Session, fonte: Fonte, concursos: Sequence[ConcursoDoRadar], agora: datetime
) -> RelatorioSincronizacao:
    """Insere o que é novo, atualiza o que mudou, carimba `ultimo_visto_em` em tudo — nunca apaga.

    Um concurso que sai do catálogo (a Cebraspe parou de listá-lo) continua na tabela com o
    último estado conhecido; só não tem `ultimo_visto_em` avançado na rodada em que sumiu.
    Rodar duas vezes com o mesmo catálogo não duplica nada nem altera `primeiro_visto_em`.

    Args:
        db: sessão do comando.
        fonte: a `Fonte` (get-or-create por `obter_ou_criar_fonte`).
        concursos: o catálogo já normalizado (`dominio.radar.ler_catalogo`).
        agora: instante da rodada — grava em `ultimo_visto_em` de tudo, e em `primeiro_visto_em`
            do que é novo.

    Returns:
        O `RelatorioSincronizacao` da rodada.
    """
    novos = atualizados = inalterados = 0
    for concurso in concursos:
        existente = db.scalars(
            select(ConcursoRadar).where(
                ConcursoRadar.fonte_id == fonte.id, ConcursoRadar.evento_url == concurso.evento_url
            )
        ).first()
        if existente is None:
            db.add(
                ConcursoRadar(
                    fonte_id=fonte.id,
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
                    lacunas=list(concurso.lacunas),
                    url_evento=URL_DETALHE_CEBRASPE.format(eventoURL=concurso.evento_url),
                    primeiro_visto_em=agora,
                    ultimo_visto_em=agora,
                    bruto=concurso.model_dump(mode="json"),
                )
            )
            novos += 1
            continue
        if _mudou(existente, concurso):
            _aplicar(existente, concurso)
            atualizados += 1
        else:
            inalterados += 1
        existente.ultimo_visto_em = agora
    db.flush()
    return RelatorioSincronizacao(novos=novos, atualizados=atualizados, inalterados=inalterados)


def listar(db: Session, *, fase: str | None = None, uf: str | None = None) -> list[ConcursoRadar]:
    """Lista o catálogo persistido, com filtro opcional por fase e/ou UF.

    Args:
        db: sessão da rota (só leitura).
        fase: quando informada, só concursos dessa fase.
        uf: quando informada, só concursos dessa UF confirmada.

    Returns:
        Os concursos, em ordem alfabética de nome (o desempate por "combina" e por inscrição
        fechando mais cedo é da rota — este repositório não sabe de perfil).
    """
    consulta = select(ConcursoRadar)
    if fase is not None:
        consulta = consulta.where(ConcursoRadar.fase == fase)
    if uf is not None:
        consulta = consulta.where(ConcursoRadar.uf == uf)
    return list(db.scalars(consulta.order_by(ConcursoRadar.nome)))


def buscar_por_evento_url(db: Session, evento_url: str) -> ConcursoRadar | None:
    """Busca um concurso do catálogo pelo `evento_url`.

    Args:
        db: sessão da rota.
        evento_url: identidade estável do evento na fonte.

    Returns:
        O `ConcursoRadar`, ou `None` se nunca foi visto.
    """
    consulta = select(ConcursoRadar).where(ConcursoRadar.evento_url == evento_url)
    return db.scalars(consulta).first()

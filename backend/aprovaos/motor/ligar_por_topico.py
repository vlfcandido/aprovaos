"""Liga o dossiê de um tópico às questões desse tópico (fundação jurídica, passo 4).

O que é: `ligar_por_topico(db)`. Para cada tópico que tem pelo menos um `DossieTopico`, pega a
versão mais recente, resolve cada `FonteDossie` para o `DispositivoLegal` que
`dados.repositorio_dossie.salvar_dossie` já criou (`buscar_dispositivo_por_citacao_canonica` —
nunca cria de novo aqui) e grava `Citacao` para toda `Questao` **publicável** desse tópico. É a
âncora grosseira (por tópico, não por frase) que complementa `motor.ancorar` (âncora fina, por
citação textual): uma questão que nunca menciona "art. 1º da Lei 8.429/1992" no enunciado passa
a ter pelo menos um dispositivo, porque o tópico dela tem dossiê.

Idempotente (como `motor.ancorar`): `dados.repositorio_citacao.registrar_citacao` já deduplica
por `(conteudo_tipo, conteudo_id, dispositivo_id)`; `posicao` continua de onde a maior citação
já gravada para aquela questão parou (`maior_posicao`), então rodar depois de `motor.ancorar`
(ou de novo) nunca colide nem duplica.

Desde a correção estrutural de 19/09/2026 (ADR-0041, fecha a P-52), as questões elegíveis de cada
dossiê não são só as do próprio `dossie.topico_id` — são as do `topico_id` **e** de cada tópico
equivalente a ele (`dados.repositorio_topico_relacao.topicos_equivalentes`, origem
`equivalencia_curada`). Sem isso, um dossiê gravado sob o vocabulário de um edital nunca alcança
as questões publicáveis de outro edital que cobre o mesmo assunto — o defeito que deixava
`ligar_por_topico` sem nenhuma ligação real no `dev.db` (0 tópicos com dossiê **e** questão sob o
mesmo `topico_id`).

Nenhuma execução acontece em import; `main()` é o `argparse` que abre o banco, roda o comando,
comita (salvo `--dry-run`) e imprime o relatório.

Quando ler: ao investigar por que uma questão sem citação textual não tem dispositivo nenhum
associado, ou para medir quantas questões uma nova via de ligação alcança.
"""

import argparse

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.modelos import DossieTopico, Questao
from aprovaos.dados.repositorio_citacao import (
    buscar_dispositivo_por_citacao_canonica,
    maior_posicao,
    registrar_citacao,
)
from aprovaos.dados.repositorio_topico_relacao import topicos_equivalentes


class RelatorioLigacaoPorTopico(BaseModel):
    """O que `ligar_por_topico` devolve — o alcance da âncora por tópico.

    Attributes:
        topicos_processados: tópicos com pelo menos um `DossieTopico` (a versão mais recente de
            cada um foi usada).
        questoes_no_topico: soma de questões publicáveis nesses tópicos (o universo elegível).
        questoes_que_ganharam_dispositivo: dessas, quantas tinham **zero** citações antes desta
            rodada e passaram a ter pelo menos uma — a métrica que a tarefa pede.
        citacoes_novas: linhas novas em `citacao` nesta rodada (idempotente — rodar de novo
            soma `0`).
    """

    topicos_processados: int
    questoes_no_topico: int
    questoes_que_ganharam_dispositivo: int
    citacoes_novas: int


def _dossies_mais_recentes(db: Session) -> list[DossieTopico]:
    """Um `DossieTopico` por `topico_id` — o de maior `versao`."""
    subquery = (
        select(DossieTopico.topico_id, func.max(DossieTopico.versao).label("versao_maxima"))
        .group_by(DossieTopico.topico_id)
        .subquery()
    )
    return list(
        db.scalars(
            select(DossieTopico).join(
                subquery,
                (DossieTopico.topico_id == subquery.c.topico_id)
                & (DossieTopico.versao == subquery.c.versao_maxima),
            )
        ).all()
    )


def ligar_por_topico(db: Session) -> RelatorioLigacaoPorTopico:
    """Liga a versão mais recente do dossiê de cada tópico às questões publicáveis desse tópico.

    Args:
        db: sessão de banco.

    Returns:
        `RelatorioLigacaoPorTopico` com o alcance da rodada. Faz `add`/`flush`; o `commit` é de
        quem chama (`main()`, ou o teste).
    """
    dossies = _dossies_mais_recentes(db)

    questoes_no_topico = 0
    questoes_que_ganharam_dispositivo = 0
    citacoes_novas = 0

    for dossie in dossies:
        dispositivos_do_dossie = [
            dispositivo
            for fonte in dossie.fontes
            if (
                dispositivo := buscar_dispositivo_por_citacao_canonica(
                    db, fonte["citacao_canonica"]
                )
            )
            is not None
        ]
        if not dispositivos_do_dossie:
            continue

        topicos_elegiveis = {dossie.topico_id, *topicos_equivalentes(db, dossie.topico_id)}
        questoes = db.scalars(
            select(Questao).where(
                Questao.topico_id.in_(topicos_elegiveis), Questao.publicavel.is_(True)
            )
        ).all()

        for questao in questoes:
            questoes_no_topico += 1
            posicao = maior_posicao(db, conteudo_tipo="questao", conteudo_id=questao.id)
            tinha_zero_antes = posicao == 0

            ganhou_alguma = False
            for dispositivo in dispositivos_do_dossie:
                posicao += 1
                criada = registrar_citacao(
                    db,
                    conteudo_tipo="questao",
                    conteudo_id=questao.id,
                    dispositivo_id=dispositivo.id,
                    posicao=posicao,
                )
                db.flush()
                if criada is not None:
                    citacoes_novas += 1
                    ganhou_alguma = True

            if tinha_zero_antes and ganhou_alguma:
                questoes_que_ganharam_dispositivo += 1

    return RelatorioLigacaoPorTopico(
        topicos_processados=len(dossies),
        questoes_no_topico=questoes_no_topico,
        questoes_que_ganharam_dispositivo=questoes_que_ganharam_dispositivo,
        citacoes_novas=citacoes_novas,
    )


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Liga o dossiê mais recente de cada tópico às questões publicáveis desse tópico "
            "(âncora por tópico, sem IA) — passo 4 da fundação jurídica."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="roda a ligação, mas não comita (só imprime o relatório)",
    )
    return parser.parse_args(argv)


def _relatar(relatorio: RelatorioLigacaoPorTopico) -> None:
    """Imprime o relatório no formato usado pelo diário da fatia."""
    print(
        f"topicos_processados={relatorio.topicos_processados} "
        f"questoes_no_topico={relatorio.questoes_no_topico} "
        f"questoes_que_ganharam_dispositivo={relatorio.questoes_que_ganharam_dispositivo} "
        f"citacoes_novas={relatorio.citacoes_novas}"
    )


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando de ligação por tópico.

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv` (padrão do `argparse`).
        config: configurações explícitas (testes); `None` lê do ambiente/.env.

    Returns:
        `0` sempre que o comando roda até o fim.
    """
    argumentos = _analisar_argumentos(argv)
    config = config or obter_configuracoes()

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db:
        relatorio = ligar_por_topico(db)
        if argumentos.dry_run:
            db.rollback()
        else:
            db.commit()
    _relatar(relatorio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

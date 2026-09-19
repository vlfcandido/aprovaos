"""O job noturno: gera o `PlanoDia` do dia seguinte para cada usuário ativo (fatia 8, F3.1).

O que é: `gerar_plano_da_noite(db, dia, commit=True)` — itera `dados.repositorio_plano.
usuarios_ativos` e chama `gerar_ou_obter_plano_noturno` por usuário, **cada um dentro do seu
próprio `try/except`**: uma falha (de dados, de rede, o que for) vira uma linha `"erro"` no
relatório e o loop **segue para o próximo usuário** — é o critério de aceite explícito do PRD
("falha de um usuário não derruba o lote"). `SemConcursoPrincipal` (sem rotina ou sem concurso
principal/edital ainda) é tratada à parte, com status próprio, porque não é uma falha do
sistema — é um estado esperado enquanto a aluna não terminou o onboarding.

`main()` é o `argparse` que resolve `--data` (padrão: amanhã, fuso do servidor — a V1 do plano
não resolve fuso por usuário, mesma pendência P-44 de `Cartao.due`), abre o engine, roda e
imprime o relatório. Idempotente: rodar duas vezes no mesmo dia não duplica a versão 1 de
ninguém (`gerar_ou_obter_plano_noturno` já garante isso). Nenhuma execução acontece em import.

Sem agendador de verdade nesta fatia — cron/systemd timer às 05h é infraestrutura de VPS
(ADR-0030, `docs/PENDENCIAS.md`); até lá o comando roda manualmente ou por agendador local:
`uv run python -m aprovaos.motor.plano`.

Quando ler: ao rodar o lote noturno, ou ao investigar por que um usuário não recebeu plano.
"""

import argparse
from datetime import date, timedelta

from pydantic import BaseModel
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.repositorio_plano import (
    gerar_ou_obter_plano_noturno,
    plano_mais_recente,
    usuarios_ativos,
)
from aprovaos.dominio.erros import SemConcursoPrincipal

StatusPlanoNoturno = str
"""`"gerado"` | `"ja_existia"` | `"sem_rotina_ou_concurso"` | `"erro"` — `str` simples (não
`Literal`) porque `RelatorioUsuario.status` só precisa comparar por igualdade no relatório."""


class RelatorioUsuario(BaseModel):
    """Uma linha do relatório — o que aconteceu ao tentar planejar o dia de um usuário.

    Attributes:
        usuario_email: quem foi processado.
        status: `"gerado"` (versão 1 nova nesta rodada), `"ja_existia"` (idempotente — já havia
            plano para este dia), `"sem_rotina_ou_concurso"` (`SemConcursoPrincipal` — estado
            esperado de onboarding incompleto), `"erro"` (qualquer outra exceção).
        motivo: detalhe pt-BR quando `status != "gerado"`; `""` para `"gerado"`.
    """

    usuario_email: str
    status: StatusPlanoNoturno
    motivo: str = ""


class RelatorioPlanoNoturno(BaseModel):
    """O relatório do lote inteiro — o que o diário da fatia e o log do cron registram.

    Attributes:
        dia: o dia planejado.
        linhas: uma por usuário ativo processado, na ordem de `usuarios_ativos`.
    """

    dia: date
    linhas: list[RelatorioUsuario]

    @property
    def gerados(self) -> int:
        """Quantos usuários receberam plano novo nesta rodada."""
        return sum(1 for linha in self.linhas if linha.status == "gerado")

    @property
    def erros(self) -> int:
        """Quantos usuários falharam por motivo inesperado (não onboarding incompleto)."""
        return sum(1 for linha in self.linhas if linha.status == "erro")


def gerar_plano_da_noite(db: Session, dia: date, *, commit: bool = True) -> RelatorioPlanoNoturno:
    """Gera (ou confirma que já existe) o plano de `dia` para cada usuário ativo.

    Cada usuário processado dentro do seu próprio `try/except` e do seu próprio commit/rollback —
    a falha de um nunca desfaz o sucesso dos que já foram processados nesta mesma rodada, nem
    impede os seguintes de rodar (CA do PRD F3.1).

    Args:
        db: sessão do comando.
        dia: o dia a planejar (amanhã, no uso normal do cron).
        commit: `True` grava de verdade (padrão); `False` (`--dry-run`) roda tudo e desfaz cada
            usuário depois de contabilizado — nada persiste.

    Returns:
        O `RelatorioPlanoNoturno` do lote.
    """
    linhas: list[RelatorioUsuario] = []
    for usuario in usuarios_ativos(db):
        try:
            ja_existia = plano_mais_recente(db, usuario.id, dia) is not None
            gerar_ou_obter_plano_noturno(db, usuario, dia)
            if commit:
                db.commit()
            else:
                db.rollback()
            linhas.append(
                RelatorioUsuario(
                    usuario_email=usuario.email, status="ja_existia" if ja_existia else "gerado"
                )
            )
        except SemConcursoPrincipal as erro:
            db.rollback()
            linhas.append(
                RelatorioUsuario(
                    usuario_email=usuario.email,
                    status="sem_rotina_ou_concurso",
                    motivo=str(erro),
                )
            )
        except Exception as erro:  # noqa: BLE001 — isolamento deliberado (CA: 1 usuário não derruba o lote)
            db.rollback()
            linhas.append(
                RelatorioUsuario(
                    usuario_email=usuario.email,
                    status="erro",
                    motivo=f"{type(erro).__name__}: {erro}",
                )
            )
    return RelatorioPlanoNoturno(dia=dia, linhas=linhas)


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Job noturno: gera o PlanoDia (versão 1) do dia seguinte para cada usuário ativo "
            "(fatia 8, F3.1) — falha de um usuário nunca derruba o lote."
        )
    )
    parser.add_argument(
        "--data", help="dia a planejar, AAAA-MM-DD; padrão: amanhã (fuso do servidor)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="roda e imprime o relatório, mas não grava nada",
    )
    return parser.parse_args(argv)


def _relatar(relatorio: RelatorioPlanoNoturno) -> None:
    """Imprime o relatório no formato usado pelo diário da fatia."""
    print(
        f"plano de {relatorio.dia.isoformat()}: {relatorio.gerados} gerado(s), "
        f"{relatorio.erros} erro(s), {len(relatorio.linhas)} usuário(s) processado(s)"
    )
    for linha in relatorio.linhas:
        if linha.status != "gerado":
            print(f"  {linha.usuario_email}: {linha.status} — {linha.motivo}")


def main(argv: list[str] | None = None, config: Configuracoes | None = None) -> int:
    """Ponto de entrada do comando do job noturno.

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv` (padrão do `argparse`).
        config: configurações explícitas (testes); `None` lê do ambiente/.env.

    Returns:
        `0` sempre — o CA é "falha de usuário não derruba o lote", e isso vale também para o
        processo do comando em si: o relatório é a forma de saber o que deu errado.
    """
    argumentos = _analisar_argumentos(argv)
    config = config or obter_configuracoes()
    dia = (
        date.fromisoformat(argumentos.data)
        if argumentos.data
        else agora_utc().date() + timedelta(days=1)
    )

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db:
        relatorio = gerar_plano_da_noite(db, dia, commit=not argumentos.dry_run)
    _relatar(relatorio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Rotina do aluno (fatia 7, F2.2): validação do formulário de `perfil_estudo`.

O que é: `DIAS_SEMANA`, `OPCOES_HORARIO`, `ENERGIAS_VALIDAS`, `VERSAO_CONSENTIMENTO_ROTINA` e
`DadosRotina` (Pydantic v2) — o que `POST /rotina` valida antes de gravar uma nova versão de
`perfil_estudo`. Puro: nenhuma leitura de banco (o `concurso_principal_id` só é conferido contra
os concursos do tenant na rota, que tem a sessão). Quando ler: ao mudar os campos do formulário de
rotina ou as faixas aceitas.
"""

from datetime import date
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, field_validator

#: Ordem canônica dos sete dias — a mesma chave que `perfil_estudo.horas_por_dia_semana` (JSON)
#: grava, e a ordem em que o formulário e a tela de rotina os mostram.
DIAS_SEMANA: Final[tuple[str, ...]] = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")

#: Horas por dia aceitas — 0 (não estuda naquele dia) a 16 (generoso, mas finito).
HORAS_MIN: Final = 0.0
HORAS_MAX: Final = 16.0

Horario = Literal["manha", "noite", "varia"]
Energia = Literal["alta", "media", "baixa"]

#: `(valor, rótulo)` do `<select>` de horário preferido (mockup: 2026-09-14-prototipo-clicavel).
OPCOES_HORARIO: Final[tuple[tuple[str, str], ...]] = (
    ("manha", "Manhã, antes do trabalho"),
    ("noite", "Noite"),
    ("varia", "Varia"),
)

ENERGIAS_VALIDAS: Final[tuple[str, ...]] = ("alta", "media", "baixa")

#: Versão do texto de consentimento de dados de rotina/energia (R-01, LGPD) — gravada em
#: `usuario.consentimento_dados_rotina_versao` a cada aceite; muda só quando o texto mudar.
VERSAO_CONSENTIMENTO_ROTINA: Final = "v1"


class DadosRotina(BaseModel):
    """O que o formulário de `/rotina` envia, já validado (F2.2, RF-05/06).

    Attributes:
        horas_por_dia_semana: uma entrada por dia de `DIAS_SEMANA`, cada uma entre `HORAS_MIN` e
            `HORAS_MAX`.
        horario_preferido: um de `OPCOES_HORARIO`.
        energia_tipica: um de `ENERGIAS_VALIDAS`.
        data_alvo: data da prova-alvo; `None` quando ainda não tem uma.
        concurso_principal_id: o concurso que os blocos do dia vão seguir (P-23); `None` mantém a
            heurística de "o último edital subido" (`repositorio_edital.concurso_principal`).
    """

    horas_por_dia_semana: dict[str, float]
    horario_preferido: Horario
    energia_tipica: Energia
    data_alvo: date | None
    concurso_principal_id: UUID | None

    @field_validator("horas_por_dia_semana")
    @classmethod
    def _valida_sete_dias(cls, valor: dict[str, float]) -> dict[str, float]:
        """Exige as sete chaves de `DIAS_SEMANA`, cada uma em `[HORAS_MIN, HORAS_MAX]`."""
        if set(valor) != set(DIAS_SEMANA):
            faltando = set(DIAS_SEMANA) - set(valor)
            sobrando = set(valor) - set(DIAS_SEMANA)
            raise ValueError(
                f"horas_por_dia_semana precisa dos sete dias {DIAS_SEMANA}"
                f"{f'; faltando: {sorted(faltando)}' if faltando else ''}"
                f"{f'; desconhecidos: {sorted(sobrando)}' if sobrando else ''}"
            )
        for dia, horas in valor.items():
            if not HORAS_MIN <= horas <= HORAS_MAX:
                raise ValueError(f"{dia}: {horas}h fora da faixa [{HORAS_MIN}, {HORAS_MAX}]")
        return valor

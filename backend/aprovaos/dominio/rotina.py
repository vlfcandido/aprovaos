"""Rotina do aluno (fatia 7, F2.2): validação do formulário de `perfil_estudo`.

O que é: `DIAS_SEMANA`, `OPCOES_HORARIO`, `ENERGIAS_VALIDAS`, `VERSAO_CONSENTIMENTO_ROTINA` e
`DadosRotina` (Pydantic v2) — o que `POST /rotina` valida antes de gravar uma nova versão de
`perfil_estudo`. Puro: nenhuma leitura de banco (o `concurso_principal_id` só é conferido contra
os concursos do tenant na rota, que tem a sessão). Quando ler: ao mudar os campos do formulário de
rotina ou as faixas aceitas.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, field_validator

#: Ordem canônica dos sete dias — a mesma chave que `perfil_estudo.horas_por_dia_semana` (JSON)
#: grava, e a ordem em que o formulário e a tela de rotina os mostram.
DIAS_SEMANA: Final[tuple[str, ...]] = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")

#: Os dois grupos em que a tela pergunta o tempo. A semana de quem trabalha não é sete decisões
#: diferentes: é "os dias de semana" e "o fim de semana" — e é assim que a pessoa pensa quando
#: está cansada.
DIAS_UTEIS: Final[tuple[str, ...]] = ("seg", "ter", "qua", "qui", "sex")
DIAS_FIM_DE_SEMANA: Final[tuple[str, ...]] = ("sab", "dom")

#: Os atalhos de tempo por dia, em horas. São valores, não texto de tela — o rótulo ("4 h+") vive
#: na camada de interface. `0.0` é uma resposta legítima: descansar é recomendação válida.
PRESETS_HORAS: Final[tuple[float, ...]] = (0.0, 1.0, 2.0, 3.0, 4.0)

#: A escolha que diz "não quero atalho, eu digito dia a dia". É o que faz o `<details>` mandar.
PRESET_MANUAL: Final = "manual"

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


def _preset_valido(escolha: str) -> float | None:
    """Converte a escolha de atalho em horas; `None` quando não é um atalho conhecido."""
    try:
        horas = float(escolha)
    except (TypeError, ValueError):
        return None
    return horas if horas in PRESETS_HORAS else None


def horas_a_partir_das_escolhas(
    preset_uteis: str,
    preset_fim_de_semana: str,
    horas_digitadas: Mapping[str, float],
) -> dict[str, float]:
    """Resolve, no servidor, o que a pessoa escolheu: o atalho do grupo ou o valor dia a dia.

    A tela oferece um atalho por grupo de dias (o caminho principal, um toque) e sete campos
    numéricos recolhidos num `<details>` (a exceção, para quem quer precisão). A precedência
    precisa ser decidida **aqui** e não no navegador, porque a página tem de funcionar sem JS:
    o atalho vence quando é um valor conhecido; `PRESET_MANUAL`, vazio ou qualquer coisa forjada
    caem no que foi digitado. Dia ausente vale zero — `DadosRotina` exige os sete.

    Args:
        preset_uteis: a escolha para `DIAS_UTEIS` — `"0"`…`"4"`, `PRESET_MANUAL` ou `""`.
        preset_fim_de_semana: a mesma coisa para `DIAS_FIM_DE_SEMANA`.
        horas_digitadas: o que veio dos campos dia a dia, por chave de `DIAS_SEMANA`.

    Returns:
        As horas dos sete dias, prontas para `DadosRotina`.
    """
    escolhas = {
        DIAS_UTEIS: _preset_valido(preset_uteis),
        DIAS_FIM_DE_SEMANA: _preset_valido(preset_fim_de_semana),
    }
    horas = {dia: float(horas_digitadas.get(dia, 0.0)) for dia in DIAS_SEMANA}
    for dias, do_atalho in escolhas.items():
        if do_atalho is None:
            continue
        for dia in dias:
            horas[dia] = do_atalho
    return horas


def preset_das_horas(horas: Mapping[str, float], dias: Sequence[str]) -> str:
    """Descobre qual atalho corresponde às horas já salvas de um grupo de dias.

    É o caminho de volta de `horas_a_partir_das_escolhas`: sem ele, quem salvou "2 h nos dias
    úteis" reabriria a tela com tudo em branco e teria de escolher de novo. Rotina que nenhum
    atalho descreve (dias desiguais, ou 2,5 h) volta como `PRESET_MANUAL`, que é a resposta
    honesta — inventar o atalho mais próximo mudaria a rotina dela sem avisar.

    Args:
        horas: as horas salvas, por chave de `DIAS_SEMANA`.
        dias: o grupo a examinar (`DIAS_UTEIS` ou `DIAS_FIM_DE_SEMANA`).

    Returns:
        `"0"`…`"4"` quando todos os dias do grupo têm o mesmo valor de `PRESETS_HORAS`;
        `PRESET_MANUAL` em qualquer outro caso.
    """
    valores = {float(horas.get(dia, 0.0)) for dia in dias}
    if len(valores) != 1:
        return PRESET_MANUAL
    (valor,) = valores
    if valor not in PRESETS_HORAS:
        return PRESET_MANUAL
    return f"{valor:g}"


def total_semanal(horas: Mapping[str, float]) -> float:
    """Soma as horas da semana — o número que a tela devolve ("isso dá N h por semana").

    Args:
        horas: as horas por chave de `DIAS_SEMANA`; dia ausente conta zero.

    Returns:
        O total em horas, arredondado a uma casa para não exibir ruído de ponto flutuante.
    """
    return round(sum(float(horas.get(dia, 0.0)) for dia in DIAS_SEMANA), 1)

"""Vocabulário de ESTADOS OPERACIONAIS de uma execução supervisionada.

Fonte única do lado host. O lado interno (IronPython 2.7, dentro do
MasterTool) tem a sua em `scripts/mastertool/automation/run_status.py:
VALID_STATES` — as duas precisam existir separadas porque os runtimes não se
importam, e `tests/unit/test_run_states.py` falha se divergirem.

**Estado operacional não é resultado científico.** Este módulo cobre apenas o
primeiro: *a execução foi íntegra e até onde chegou?* O veredito da
investigação (`P1`–`P4`, `E1`–`E4`, `S1`–`S3`, `resolved`,
`partially_resolved`, `ambiguous`, `unsupported`) pertence ao contrato de cada
módulo e **não entra aqui**. Uma run pode terminar `completed` com veredito
científico negativo — resultado inconclusivo não é falha operacional
(`docs/19-contratos-de-execucao.md`, seção 1).

Este módulo é vocabulário e evidência, não uma máquina de estados: não há
motor de transição, nem registro de handlers, nem imposição no caminho de
escrita. O runner interno continua sendo a única autoridade sobre o que
escreve em `status.json`.
"""

from __future__ import annotations

# --- estados ------------------------------------------------------------------

STATE_CREATED = "created"
STATE_MASTERTOOL_STARTED = "mastertool_started"
STATE_SCRIPT_STARTED = "script_started"
STATE_PROVENANCE_VALIDATED = "provenance_validated"
STATE_PROJECT_IDENTITY_VALIDATED = "project_identity_validated"
STATE_SCANNING = "scanning"
STATE_EXPORTING = "exporting"
STATE_PROBING_LADDER_DYNAMIC_SURFACE = "probing_ladder_dynamic_surface"
STATE_PROBING_LADDER_EXTENDER_SURFACE = "probing_ladder_extender_surface"
STATE_PROBING_PLCOPEN_EXPORT_SIGNATURE = "probing_plcopen_export_signature"
STATE_EXPORTING_PLCOPEN_XML = "exporting_plcopen_xml"
STATE_VALIDATING = "validating"
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"
STATE_NEEDS_INTERACTION = "needs_interaction"

# Ordem idêntica à de `run_status.VALID_STATES` — a paridade é verificada em
# teste, incluindo a ordem, porque ela é o próprio fluxo esperado.
VALID_STATES = (
    STATE_CREATED,
    STATE_MASTERTOOL_STARTED,
    STATE_SCRIPT_STARTED,
    STATE_PROVENANCE_VALIDATED,
    STATE_PROJECT_IDENTITY_VALIDATED,
    STATE_SCANNING,
    STATE_EXPORTING,
    STATE_PROBING_LADDER_DYNAMIC_SURFACE,
    STATE_PROBING_LADDER_EXTENDER_SURFACE,
    STATE_PROBING_PLCOPEN_EXPORT_SIGNATURE,
    STATE_EXPORTING_PLCOPEN_XML,
    STATE_VALIDATING,
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_NEEDS_INTERACTION,
)

TERMINAL_STATES = (STATE_COMPLETED, STATE_FAILED, STATE_NEEDS_INTERACTION)

# Escritos pelo HOST antes de o runner interno existir — por isso não aparecem
# no `status-history.jsonl`, que é escrito de dentro do MasterTool.
HOST_WRITTEN_STATES = (STATE_CREATED, STATE_MASTERTOOL_STARTED)

# O probe 16 NÃO tem estado dedicado: reusa `scanning`. Registrado aqui porque
# a ausência é decisão, não esquecimento — os probes 17, 18 e 19 ganharam
# estado próprio por terem gate de validade distinto, e o 16 não tem.
PROBE_16_STATE = STATE_SCANNING


# --- transições OBSERVADAS ----------------------------------------------------

# Derivadas de 10 execuções reais arquivadas em `C:\mastertool-ai-bridge-runs`,
# lendo `status-history.jsonl`. São EVIDÊNCIA, não desenho: o que está aqui
# aconteceu de fato. Transição legítima que ainda não ocorreu simplesmente não
# está nesta lista — ausência de observação não é prova de impossibilidade,
# a mesma disciplina que o resto do projeto aplica a APIs.
OBSERVED_TRANSITIONS = frozenset({
    (STATE_SCRIPT_STARTED, STATE_PROVENANCE_VALIDATED),
    (STATE_SCRIPT_STARTED, STATE_FAILED),
    (STATE_PROVENANCE_VALIDATED, STATE_PROJECT_IDENTITY_VALIDATED),
    (STATE_PROJECT_IDENTITY_VALIDATED, STATE_SCANNING),
    (STATE_PROJECT_IDENTITY_VALIDATED, STATE_FAILED),
    (STATE_SCANNING, STATE_EXPORTING),
    (STATE_SCANNING, STATE_VALIDATING),
    (STATE_EXPORTING, STATE_VALIDATING),
    (STATE_EXPORTING, STATE_SCANNING),
    (STATE_EXPORTING, STATE_PROBING_LADDER_DYNAMIC_SURFACE),
    (STATE_EXPORTING, STATE_PROBING_LADDER_EXTENDER_SURFACE),
    (STATE_EXPORTING, STATE_PROBING_PLCOPEN_EXPORT_SIGNATURE),
    (STATE_EXPORTING, STATE_EXPORTING_PLCOPEN_XML),
    (STATE_PROBING_LADDER_DYNAMIC_SURFACE, STATE_VALIDATING),
    (STATE_PROBING_LADDER_EXTENDER_SURFACE, STATE_VALIDATING),
    (STATE_PROBING_PLCOPEN_EXPORT_SIGNATURE, STATE_VALIDATING),
    (STATE_EXPORTING_PLCOPEN_XML, STATE_VALIDATING),
    (STATE_VALIDATING, STATE_COMPLETED),
})

# Estados que existem no vocabulário e nunca apareceram num histórico real.
# `created`/`mastertool_started` porque são do host; `needs_interaction`
# porque nenhuma das 10 runs precisou de intervenção humana.
NOT_YET_OBSERVED_STATES = (
    STATE_CREATED, STATE_MASTERTOOL_STARTED, STATE_NEEDS_INTERACTION)


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES


def is_valid_state(state: str) -> bool:
    return state in VALID_STATES


def unknown_states(states) -> list:
    """Estados fora do vocabulário, preservando a ordem de entrada. Serve para
    LER um histórico e denunciar o que não se reconhece — nunca para impedir o
    runner interno de escrever."""
    return [s for s in states if s not in VALID_STATES]


def unobserved_transitions(history) -> list:
    """Pares consecutivos de um histórico que nunca foram vistos numa run real.

    Não é veredito de invalidez: é sinalização. Uma transição nova pode ser
    legítima e simplesmente inédita — quem lê decide se investiga. Estados
    repetidos em sequência são ignorados (não são transição).
    """
    pairs = []
    previous = None
    for state in history:
        if previous is not None and previous != state:
            pair = (previous, state)
            if pair not in OBSERVED_TRANSITIONS:
                pairs.append(pair)
        previous = state
    return pairs

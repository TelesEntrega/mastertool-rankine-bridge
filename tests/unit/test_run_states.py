"""Vocabulário de estados operacionais: paridade entre os dois runtimes.

O host (CPython 3.11) e o runner interno (IronPython 2.7, dentro do
MasterTool) não podem importar um do outro. O vocabulário de estados existe
declarado nos dois lados, e a única defesa contra divergência silenciosa é
este teste: se alguém acrescentar um estado de um lado só, ele falha.

Divergir aqui é caro de descobrir em campo — o runner escreveria um estado
que o host recusa a interpretar, num ponto em que a execução já mexeu no
MasterTool.
"""

from __future__ import annotations

import ast
import io
from pathlib import Path

import pytest

from mastertool_bridge.automation import run_states

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERNAL_RUN_STATUS = (
    REPO_ROOT / "scripts" / "mastertool" / "automation" / "run_status.py")


def _internal_tuple(name: str) -> tuple:
    """Lê a constante do módulo IronPython por AST — importar não serve, o
    módulo é escrito para 2.7 e vive fora do pacote instalável."""
    tree = ast.parse(io.open(INTERNAL_RUN_STATUS, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return tuple(ast.literal_eval(node.value))
    raise AssertionError(f"{INTERNAL_RUN_STATUS.name} não declara {name}")


def test_valid_states_match_between_runtimes_including_order():
    """Ordem também é contrato: ela é o fluxo esperado da execução."""
    internal = _internal_tuple("VALID_STATES")
    assert run_states.VALID_STATES == internal, (
        "vocabulário divergiu entre host e runner interno\n"
        f"  só no host:    {sorted(set(run_states.VALID_STATES) - set(internal))}\n"
        f"  só no interno: {sorted(set(internal) - set(run_states.VALID_STATES))}")


def test_terminal_states_match_between_runtimes():
    assert run_states.TERMINAL_STATES == _internal_tuple("TERMINAL_STATES")


def test_result_models_reexports_the_single_source():
    """`result_models.TERMINAL_STATES` era uma terceira cópia."""
    from mastertool_bridge.automation import result_models

    assert result_models.TERMINAL_STATES is run_states.TERMINAL_STATES


def test_terminal_states_are_part_of_the_vocabulary():
    for state in run_states.TERMINAL_STATES:
        assert run_states.is_valid_state(state)
        assert run_states.is_terminal(state)


def test_probe_16_has_no_dedicated_state():
    """Decisão registrada, não esquecimento: o probe 16 reusa `scanning`
    porque não tem gate de validade próprio, ao contrário dos probes 17/18/19.
    Se alguém criar `probing_ladder_surface`, este teste falha e obriga a
    revisar a decisão em vez de acrescentar por simetria."""
    assert "probing_ladder_surface" not in run_states.VALID_STATES
    assert run_states.PROBE_16_STATE == run_states.STATE_SCANNING


# --- estado operacional NÃO é resultado científico ----------------------------

@pytest.mark.parametrize("scientific", [
    "P1", "P2", "P3", "P4", "E1", "E2", "E3", "E4", "S1", "S2", "S3",
    "resolved", "partially_resolved", "ambiguous", "unsupported",
    "P1_graphical_body_present", "P3_no_output",
])
def test_scientific_verdicts_never_enter_the_operational_vocabulary(scientific):
    """Os dois eixos são independentes: uma run pode ser `completed` com
    veredito científico negativo. Misturá-los destruiria a distinção que o
    projeto inteiro depende (docs/19, seção 1)."""
    assert scientific not in run_states.VALID_STATES


# --- transições ---------------------------------------------------------------

def test_observed_transitions_only_reference_known_states():
    for origin, destination in run_states.OBSERVED_TRANSITIONS:
        assert run_states.is_valid_state(origin), origin
        assert run_states.is_valid_state(destination), destination


def test_a_real_run_history_has_no_unobserved_transitions():
    history = [
        run_states.STATE_SCRIPT_STARTED,
        run_states.STATE_PROVENANCE_VALIDATED,
        run_states.STATE_PROJECT_IDENTITY_VALIDATED,
        run_states.STATE_SCANNING,
        run_states.STATE_EXPORTING,
        run_states.STATE_EXPORTING_PLCOPEN_XML,
        run_states.STATE_VALIDATING,
        run_states.STATE_COMPLETED,
    ]
    assert run_states.unobserved_transitions(history) == []


def test_repeated_states_are_not_treated_as_transitions():
    history = [run_states.STATE_SCANNING, run_states.STATE_SCANNING,
               run_states.STATE_EXPORTING]
    assert run_states.unobserved_transitions(history) == []


def test_an_unseen_transition_is_reported_not_rejected():
    """Sinalização, não veredito: transição inédita pode ser legítima."""
    history = [run_states.STATE_COMPLETED, run_states.STATE_SCANNING]
    assert run_states.unobserved_transitions(history) == [
        (run_states.STATE_COMPLETED, run_states.STATE_SCANNING)]


def test_unknown_states_are_detected_in_a_history():
    assert run_states.unknown_states(
        [run_states.STATE_SCANNING, "estado_inventado"]) == ["estado_inventado"]


def test_states_never_observed_are_declared_as_such():
    """`created`/`mastertool_started` são escritos pelo host e não aparecem no
    histórico interno; `needs_interaction` não ocorreu em nenhuma das 10 runs.
    Ausência de observação não é prova de impossibilidade — mesma disciplina
    que o projeto aplica a APIs do MasterTool."""
    for state in run_states.NOT_YET_OBSERVED_STATES:
        assert run_states.is_valid_state(state)
        assert all(state != destination
                   for _origin, destination in run_states.OBSERVED_TRANSITIONS)


def test_no_state_literals_left_in_host_modules():
    """Literal solto é o que faz um vocabulário divergir sem ninguém notar."""
    watched = [
        "automation/supervised_run.py",
        "automation/host_validation_revision.py",
        "automation/result_models.py",
    ]
    src = REPO_ROOT / "src" / "mastertool_bridge"
    offenders = []
    for rel in watched:
        tree = ast.parse(io.open(src / rel, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in run_states.VALID_STATES:
                offenders.append(f"{rel}:{node.lineno}:{node.value!r}")
    assert not offenders, f"estado como literal solto: {offenders}"

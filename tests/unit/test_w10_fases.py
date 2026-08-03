"""As fases de W10 — alteração de objeto preexistente (R2).

Verificação estática: o que se pode afirmar lendo os arquivos, sem abrir o
produto. O gate em si permanece fechado; estar no mapa não autoriza nada.
"""

import importlib.util
import io
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_COMMON = os.path.join(_REPO, "scripts", "mastertool")
if _COMMON not in sys.path:
    sys.path.insert(0, _COMMON)

from common import safety  # noqa: E402

_PROBE40 = os.path.join(_REPO, "scripts", "mastertool", "probes",
                        "40_build_w1_4.py")


def _probe40():
    spec = importlib.util.spec_from_file_location("probe40_w10", _PROBE40)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_a_allowlist_de_w10_e_a_MENOR_possivel():
    """`replace` e `save_as`, mais nada. Um `create_*` aqui deixaria a prova
    ambígua entre "alterou" e "criou por cima"."""
    assert safety.PHASE_ALLOWED_OPERATIONS["W10_EDIT_EXISTING"] == frozenset(
        ["replace", "save_as"])


def test_w10_nao_autoriza_criacao():
    allowlist = safety.PHASE_ALLOWED_OPERATIONS["W10_EDIT_EXISTING"]
    assert not any(op.startswith("create_") for op in allowlist)
    assert not any(op.startswith("set:") for op in allowlist)


def test_a_fase_de_build_de_w10_tem_um_verbo_so():
    assert safety.PHASE_ALLOWED_OPERATIONS["W10_VERIFY_BUILD"] == frozenset(
        ["build"])


def test_estar_no_mapa_NAO_autoriza():
    """Quem autoriza é `CONTROLLED_WRITE_PHASE`; o mapa é registro."""
    assert "W10_EDIT_EXISTING" in safety.PHASE_ALLOWED_OPERATIONS
    assert safety.CONTROLLED_WRITE_PHASE is None


def test_o_probe_de_build_aceita_a_fase_e_o_id_de_w10():
    probe40 = _probe40()
    assert "W10_VERIFY_BUILD" in probe40.ACCEPTED_BUILD_PHASES
    assert "w10-edit-existing" in probe40.ACCEPTED_OPERATION_IDS
    assert probe40.EXPECTED_PLAN_OPERATIONS_BY_PHASE["W10_VERIFY_BUILD"] == (
        "build",)


def test_toda_fase_aceita_pelo_build_tem_operacoes_esperadas():
    """Fase aceita sem entrada no mapa de operações cairia num `else` sem nome
    próprio."""
    probe40 = _probe40()
    for fase in probe40.ACCEPTED_BUILD_PHASES:
        assert fase in probe40.EXPECTED_PLAN_OPERATIONS_BY_PHASE, fase


def test_o_executor_tem_lista_PROPRIA_de_fases():
    """A dupla porta: estar no mapa de allowlists não basta, o executor
    mantém a sua. Foi ela que recusou a primeira tentativa de rodar W10."""
    fonte = io.open(
        os.path.join(_REPO, "scripts", "mastertool", "probes",
                     "46_execute_authoring_plan.py"), encoding="utf-8").read()
    assert "W10_EDIT_EXISTING" in fonte
    assert "ACCEPTED_PHASES" in fonte


def test_toda_fase_aceita_pelo_executor_existe_no_mapa_de_allowlists():
    """Fase aceita pelo executor e ausente do mapa seria autorização sem
    allowlist — o executor pediria permissão a uma tabela que não a tem."""
    import importlib.util

    caminho = os.path.join(_REPO, "scripts", "mastertool", "probes",
                           "46_execute_authoring_plan.py")
    spec = importlib.util.spec_from_file_location("probe46_fases", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    for fase in modulo.ACCEPTED_PHASES:
        assert fase in safety.PHASE_ALLOWED_OPERATIONS, fase

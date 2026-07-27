import json
from pathlib import Path

import pytest

from mastertool_bridge.changes.change_set import load_change_set
from mastertool_bridge.changes.validator import validate_change_set_policy
from mastertool_bridge.exceptions import ValidationError

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _base_data() -> dict:
    return {
        "schema_version": "1.0",
        "change_id": "CHG-2026-0001",
        "status": "draft",
        "source_export": "2026-07-23_09-45-10_ProjetoExemploNX3008",
        "source_export_hash": "a" * 64,
        "target_project": "copia-de-trabalho",
        "created_by": "agent",
        "objects": [{
            "qualified_name": "Application.POUs.ControleMotor",
            "operation": "replace_implementation",
            "original_hash": "b" * 64,
            "proposed_hash": "c" * 64,
            "risk_level": "medium",
            "reason": "Adicionar diagnostico de falha de partida",
        }],
        "safety_checks": {
            "changes_physical_outputs": False,
            "changes_hardware_configuration": False,
            "changes_communication_mapping": False,
            "changes_retain_data": False,
            "requires_compile": True,
            "requires_simulation": True,
            "requires_human_approval": True,
        },
    }


def _write(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "change-set.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_example_change_set_is_valid_and_passes_policy(tmp_path):
    cs = load_change_set(EXAMPLES / "sample-change-set.json")
    result = validate_change_set_policy(cs)
    assert result.ok, result.errors


def test_valid_change_set_loads(tmp_path):
    cs = load_change_set(_write(tmp_path, _base_data()))
    assert cs.change_id == "CHG-2026-0001"
    assert cs.highest_risk == "medium"


def test_bad_change_id_rejected_by_schema(tmp_path):
    data = _base_data()
    data["change_id"] = "MUDANCA-1"
    with pytest.raises(ValidationError):
        load_change_set(_write(tmp_path, data))


def test_human_approval_false_rejected_by_schema(tmp_path):
    data = _base_data()
    data["safety_checks"]["requires_human_approval"] = False
    with pytest.raises(ValidationError):
        load_change_set(_write(tmp_path, data))


def test_critical_risk_blocked_by_policy(tmp_path):
    data = _base_data()
    data["objects"][0]["risk_level"] = "critical"
    cs = load_change_set(_write(tmp_path, data))
    result = validate_change_set_policy(cs)
    assert not result.ok
    assert any("CRÍTICO" in e for e in result.errors)


def test_hardware_change_blocked_by_policy(tmp_path):
    data = _base_data()
    data["safety_checks"]["changes_hardware_configuration"] = True
    cs = load_change_set(_write(tmp_path, data))
    result = validate_change_set_policy(cs)
    assert not result.ok


def test_applied_status_blocked_in_this_phase(tmp_path):
    data = _base_data()
    data["status"] = "applied"
    cs = load_change_set(_write(tmp_path, data))
    result = validate_change_set_policy(cs)
    assert not result.ok


def test_no_compile_blocked_by_policy(tmp_path):
    data = _base_data()
    data["safety_checks"]["requires_compile"] = False
    cs = load_change_set(_write(tmp_path, data))
    result = validate_change_set_policy(cs)
    assert not result.ok

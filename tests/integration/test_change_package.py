import json
from pathlib import Path

from mastertool_bridge.cli import main

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_cli_validates_example_change_set():
    assert main(["validate-change-set",
                 str(EXAMPLES / "sample-change-set.json")]) == 0


def test_cli_rejects_critical_change_set(tmp_path):
    data = json.loads(
        (EXAMPLES / "sample-change-set.json").read_text(encoding="utf-8"))
    data["objects"][0]["risk_level"] = "critical"
    path = tmp_path / "critico.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["validate-change-set", str(path)]) == 1


def test_cli_rejects_malformed_change_set(tmp_path):
    path = tmp_path / "invalido.json"
    path.write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
    assert main(["validate-change-set", str(path)]) == 1

import json

from mastertool_bridge.cli import main
from mastertool_bridge.export.loader import load_export


def test_load_export_finds_all_objects(sample_project_dir):
    project = load_export(sample_project_dir)
    assert project.name == "ProjetoExemploNX3008"
    assert project.is_read_only
    assert len(project.objects) == 3
    fb = project.find("Application.POUs.ControleMotor")
    assert fb is not None
    assert fb.has_declaration and fb.has_implementation


def test_cli_validate_export_ok(sample_export):
    assert main(["validate-export", str(sample_export)]) == 0


def test_cli_validate_export_fails_on_tampering(sample_export):
    target = sample_export / "export-manifest.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    data["mode"] = "read_only"  # conteúdo igual, mas reescrita muda o hash
    target.write_text(json.dumps(data), encoding="utf-8")
    assert main(["validate-export", str(sample_export)]) == 1


def test_cli_inspect(sample_project_dir, capsys):
    assert main(["inspect", str(sample_project_dir)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["project"] == "ProjetoExemploNX3008"
    assert output["objects_loaded"] == 3


def test_cli_index(sample_export):
    assert main(["index", str(sample_export)]) == 0
    index_path = sample_export / "reports" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(index["objects"]) == 3
    var_names = {v["name"] for v in index["variables"]}
    assert {"xLigaMotor", "xMotor", "iEstado"} <= var_names

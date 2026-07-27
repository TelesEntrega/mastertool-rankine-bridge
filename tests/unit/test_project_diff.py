from pathlib import Path

from mastertool_bridge.diff.object_diff import diff_objects
from mastertool_bridge.diff.project_diff import compare_projects
from mastertool_bridge.models import ExportedProject, PlcObject


def _project(tag: str, objects: list[PlcObject]) -> ExportedProject:
    return ExportedProject(export_dir=Path(f"/fake/{tag}"),
                           manifest={"mode": "read_only",
                                     "project": {"name": "P"}},
                           objects=objects)


def _pou(name: str, impl: str) -> PlcObject:
    return PlcObject(name=name, object_type="program",
                     qualified_name=f"App.{name}",
                     declaration=f"PROGRAM {name}\nVAR\nEND_VAR\n",
                     implementation=impl)


def test_identical_projects_have_no_changes():
    a = _project("a", [_pou("Main", "x := 1;\n")])
    b = _project("b", [_pou("Main", "x := 1;\n")])
    result = compare_projects(a, b)
    assert result["added"] == []
    assert result["removed"] == []
    assert result["modified"] == []
    assert result["unchanged_count"] == 1


def test_modified_object_detected():
    a = _project("a", [_pou("Main", "x := 1;\n")])
    b = _project("b", [_pou("Main", "x := 2;\n")])
    result = compare_projects(a, b)
    assert [m["object"] for m in result["modified"]] == ["Main"]
    diff_lines = "".join(result["modified"][0]["implementation_diff"])
    assert "-x := 1;" in diff_lines
    assert "+x := 2;" in diff_lines


def test_added_and_removed():
    a = _project("a", [_pou("Main", ";"), _pou("Antigo", ";")])
    b = _project("b", [_pou("Main", ";"), _pou("Novo", ";")])
    result = compare_projects(a, b)
    assert result["added"] == ["App.Novo"]
    assert result["removed"] == ["App.Antigo"]


def test_trailing_whitespace_is_not_a_change():
    old = _pou("Main", "x := 1;   \n")
    new = _pou("Main", "x := 1;\n")
    assert diff_objects(old, new)["status"] == "unchanged"

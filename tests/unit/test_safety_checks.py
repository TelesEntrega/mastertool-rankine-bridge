from mastertool_bridge.analysis.safety_checks import (check_object_text,
                                                      check_project)
from mastertool_bridge.export.loader import load_export
from mastertool_bridge.models import PlcObject


def _checks(findings):
    return {f["check"] for f in findings}


def test_project_findings(sample_project_dir):
    project = load_export(sample_project_dir)
    findings = check_project(project)
    checks = _checks(findings)
    assert "direct_output_write" in checks          # %QX0.1 := ...
    assert "physical_output_variable" in checks     # xValvulaSaida AT %QX0.0
    assert "retain_persistent" in checks            # iContadorCiclos
    assert "for_bound_not_literal" in checks        # FOR ... TO aiPressoes[0]
    assert "computed_array_index" in checks         # aiPressoes[i]
    assert "read_never_written" in checks           # xLigaMotor
    # todos os alertas são heurísticos:
    assert all(f["heuristic"] is True for f in findings)


def test_clean_object_has_no_findings():
    obj = PlcObject(
        name="FB_Soma", object_type="function_block",
        declaration=("FUNCTION_BLOCK FB_Soma\nVAR_INPUT\n    a : INT;\n"
                     "    b : INT;\nEND_VAR\nVAR_OUTPUT\n    soma : INT;\n"
                     "END_VAR\n"),
        implementation="soma := a + b;\n")
    assert check_object_text(obj) == []


def test_pointer_usage_detected():
    obj = PlcObject(
        name="FB_Ptr", object_type="function_block",
        declaration="FUNCTION_BLOCK FB_Ptr\nVAR\n    p : POINTER TO INT;\nEND_VAR\n",
        implementation="p := ADR(x);\n")
    assert "pointer_usage" in _checks(check_object_text(obj))


def test_type_conversion_detected():
    obj = PlcObject(
        name="P1", object_type="program",
        declaration="PROGRAM P1\nVAR\n    x : INT;\nEND_VAR\n",
        implementation="x := DINT_TO_INT(valor);\n")
    assert "type_conversion" in _checks(check_object_text(obj))


def test_multiple_writers_detected():
    gvl = PlcObject(name="GVL", object_type="gvl",
                    qualified_name="App.GVL",
                    declaration="VAR_GLOBAL\n    xCmd : BOOL;\nEND_VAR\n")
    p1 = PlcObject(name="P1", object_type="program", qualified_name="App.P1",
                   declaration="PROGRAM P1\nVAR\nEND_VAR\n",
                   implementation="xCmd := TRUE;\ny := xCmd;\n")
    p2 = PlcObject(name="P2", object_type="program", qualified_name="App.P2",
                   declaration="PROGRAM P2\nVAR\nEND_VAR\n",
                   implementation="xCmd := FALSE;\n")
    from pathlib import Path

    from mastertool_bridge.models import ExportedProject
    project = ExportedProject(export_dir=Path("/fake"),
                              manifest={"mode": "read_only",
                                        "project": {"name": "P"}},
                              objects=[gvl, p1, p2])
    assert "multiple_writers" in _checks(check_project(project))

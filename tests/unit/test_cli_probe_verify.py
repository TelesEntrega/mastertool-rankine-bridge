"""Testa mastertool_bridge.automation.cli_probe_verify — o gate OFFLINE da
Etapa A do roadmap de automação (docs/15-automation-launcher-roadmap.md),
que lê os result.json produzidos por
scripts/mastertool/probes/15_validate_command_line_execution.py e emite o
veredito consolidado (gate_b_unblocked etc.).

Cobre, no mínimo (ver contrato do slice):
  - procedência aceita IronPython 2.7 e REJEITA o caso real CPython 3
    (platform="win32", runtime_family="CPython/desconhecido",
    version_info=[3, 11, ...]);
  - t1 passa com projects_available=False;
  - t2 reprova se a camada 1 não teve sucesso;
  - t3 sempre "manual";
  - t4 reprova se project.path diverge do esperado;
  - t4 reprova se qualquer flag de safety for True;
  - gate_b_unblocked False quando t3 não foi confirmado manualmente.
"""

from __future__ import annotations

import json
from pathlib import Path

from mastertool_bridge.automation.cli_probe_verify import (
    build_gate_report,
    check_provenance,
    discover_results,
    evaluate_test,
    run_verification,
)

# =============================================================================
# Fixtures / builders
# =============================================================================


def _base_runtime(inside_mastertool: bool = True) -> dict:
    if inside_mastertool:
        return {
            "platform": "cli",
            "runtime_family": "IronPython",
            "version_info": [2, 7, 12, "final", 0],
        }
    # Caso real de 2026-07-24 14:57: CPython 3 fora do MasterTool.
    return {
        "platform": "win32",
        "runtime_family": "CPython/desconhecido",
        "version_info": [3, 11, 8, "final", 0],
    }


def _make_result(
    *,
    inside_mastertool: bool = True,
    script_started: bool = True,
    argv: list | None = None,
    projects_available: bool = False,
    system_available: bool = False,
    primary_available: bool = False,
    project_path: str | None = None,
    output_dir_resolution: list | None = None,
    safety: dict | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "script_started": script_started,
        "argv": argv if argv is not None else [],
        "runtime": _base_runtime(inside_mastertool),
        "globals": {
            "projects_available": projects_available,
            "system_available": system_available,
        },
        "project": {
            "primary_available": primary_available,
            "path": project_path,
        },
        "safety": safety if safety is not None else {
            "project_modified": False,
            "save_called": False,
            "build_called": False,
            "online_operation": False,
        },
        "output_dir_resolution": output_dir_resolution if output_dir_resolution is not None else [],
    }


# =============================================================================
# check_provenance
# =============================================================================


def test_provenance_accepts_ironpython_2_7():
    result = _make_result(inside_mastertool=True)
    provenance = check_provenance(result)
    assert provenance["inside_mastertool"] is True
    assert provenance["reason"] is None
    assert all(c["ok"] for c in provenance["checks"].values())


def test_provenance_rejects_real_cpython3_case_outside_mastertool():
    """Caso real de 2026-07-24 14:57 confundido com execução no MasterTool."""
    result = _make_result(inside_mastertool=False)
    provenance = check_provenance(result)
    assert provenance["inside_mastertool"] is False
    assert provenance["reason"] is not None
    assert provenance["checks"]["platform"]["ok"] is False
    assert provenance["checks"]["runtime_family"]["ok"] is False
    assert provenance["checks"]["version_info"]["ok"] is False


def test_provenance_rejects_partial_match_platform_cli_but_wrong_family():
    result = _make_result(inside_mastertool=True)
    result["runtime"]["runtime_family"] = "CPython/desconhecido"
    provenance = check_provenance(result)
    assert provenance["inside_mastertool"] is False


def test_provenance_rejects_version_info_not_starting_with_2_7():
    result = _make_result(inside_mastertool=True)
    result["runtime"]["version_info"] = [2, 6, 1]
    provenance = check_provenance(result)
    assert provenance["checks"]["version_info"]["ok"] is False
    assert provenance["inside_mastertool"] is False


def test_provenance_handles_missing_runtime_key_without_raising():
    provenance = check_provenance({})
    assert provenance["inside_mastertool"] is False


# =============================================================================
# t1
# =============================================================================


def test_t1_passes_with_projects_available_false():
    result = _make_result(inside_mastertool=True, script_started=True,
                          projects_available=False)
    ev = evaluate_test("t1", result, {})
    assert ev["status"] == "pass"
    assert any("projects_available" in o for o in ev["observations"])


def test_t1_fails_when_script_started_false():
    result = _make_result(script_started=False)
    ev = evaluate_test("t1", result, {})
    assert ev["status"] == "fail"


def test_t1_fails_when_outside_mastertool():
    result = _make_result(inside_mastertool=False)
    ev = evaluate_test("t1", result, {})
    assert ev["status"] == "fail"


def test_t1_missing_when_result_is_none():
    ev = evaluate_test("t1", None, {})
    assert ev["status"] == "missing"


# =============================================================================
# t2
# =============================================================================


def test_t2_passes_when_output_dir_in_argv_and_layer1_success():
    result = _make_result(
        argv=["script.py", "--output", "C:\\saida\\dir"],
        output_dir_resolution=[{"layer": 1, "success": True}],
    )
    ev = evaluate_test("t2", result, {"output_dir": "C:\\saida\\dir"})
    assert ev["status"] == "pass"


def test_t2_passes_with_case_insensitive_normalized_path_match():
    result = _make_result(
        argv=["script.py", "--output", "c:\\saida\\DIR\\"],
        output_dir_resolution=[{"layer": 1, "success": True}],
    )
    ev = evaluate_test("t2", result, {"output_dir": "C:\\saida\\dir"})
    assert ev["status"] == "pass"


def test_t2_fails_when_layer1_not_successful():
    """Reprova quando a camada 1 (--output em argv) não teve sucesso — isso
    é o que provaria que aspas/espaços sobreviveram ao --scriptargs."""
    result = _make_result(
        argv=["script.py", "--output", "C:\\saida\\dir"],
        output_dir_resolution=[
            {"layer": 1, "success": False},
            {"layer": 2, "success": True},
        ],
    )
    ev = evaluate_test("t2", result, {"output_dir": "C:\\saida\\dir"})
    assert ev["status"] == "fail"


def test_t2_fails_when_output_dir_not_recognizable_in_argv():
    result = _make_result(
        argv=["script.py"],
        output_dir_resolution=[{"layer": 1, "success": True}],
    )
    ev = evaluate_test("t2", result, {"output_dir": "C:\\saida\\dir"})
    assert ev["status"] == "fail"


def test_t2_fails_closed_when_expected_output_dir_not_provided():
    result = _make_result(
        argv=["script.py", "--output", "C:\\saida\\dir"],
        output_dir_resolution=[{"layer": 1, "success": True}],
    )
    ev = evaluate_test("t2", result, {})
    assert ev["status"] == "fail"


def test_t2_missing_when_result_is_none():
    ev = evaluate_test("t2", None, {"output_dir": "C:\\x"})
    assert ev["status"] == "missing"


# =============================================================================
# t3
# =============================================================================


def test_t3_is_always_manual_never_pass_automatically():
    ev = evaluate_test("t3", None, {})
    assert ev["status"] == "manual"
    assert len(ev["manual_items"]) == 3


def test_t3_is_manual_even_when_expected_confirms_everything():
    ev = evaluate_test(
        "t3", None,
        {"t3_manual_confirmed": {
            "correct_project_opened": True,
            "no_conversion_or_license_dialog": True,
            "disposable_copy_hash_intact": True,
        }})
    assert ev["status"] == "manual"


def test_t3_never_reads_result_argument_even_if_provided():
    # Por construção, t3 nunca gera result.json -- mesmo que algo seja
    # passado, o status permanece "manual".
    ev = evaluate_test("t3", {"script_started": True}, {})
    assert ev["status"] == "manual"


# =============================================================================
# t4
# =============================================================================


def _t4_base_kwargs(**overrides):
    kwargs = dict(
        inside_mastertool=True,
        script_started=True,
        argv=["script.py", "--output", "C:\\saida\\dir"],
        projects_available=True,
        primary_available=True,
        project_path="C:\\Projetos\\Projeto.project",
        output_dir_resolution=[{"layer": 1, "success": True}],
        safety={
            "project_modified": False,
            "save_called": False,
            "build_called": False,
            "online_operation": False,
        },
    )
    kwargs.update(overrides)
    return kwargs


_T4_EXPECTED = {"output_dir": "C:\\saida\\dir", "project_path": "C:\\Projetos\\Projeto.project"}


def test_t4_passes_full_happy_path():
    result = _make_result(**_t4_base_kwargs())
    ev = evaluate_test("t4", result, _T4_EXPECTED)
    assert ev["status"] == "pass"


def test_t4_fails_when_project_path_diverges_from_expected():
    result = _make_result(**_t4_base_kwargs(project_path="C:\\Projetos\\Outro.project"))
    ev = evaluate_test("t4", result, _T4_EXPECTED)
    assert ev["status"] == "fail"


def test_t4_passes_when_project_path_matches_after_normalization():
    result = _make_result(**_t4_base_kwargs(project_path="c:\\projetos\\PROJETO.project\\"))
    ev = evaluate_test("t4", result, _T4_EXPECTED)
    assert ev["status"] == "pass"


def test_t4_fails_when_any_safety_flag_true():
    for key in ("project_modified", "save_called", "build_called", "online_operation"):
        safety = {
            "project_modified": False, "save_called": False,
            "build_called": False, "online_operation": False,
        }
        safety[key] = True
        result = _make_result(**_t4_base_kwargs(safety=safety))
        ev = evaluate_test("t4", result, _T4_EXPECTED)
        assert ev["status"] == "fail", "deveria reprovar com safety.%s=True" % key


def test_t4_fails_when_projects_available_false():
    result = _make_result(**_t4_base_kwargs(projects_available=False))
    ev = evaluate_test("t4", result, _T4_EXPECTED)
    assert ev["status"] == "fail"


def test_t4_fails_when_primary_available_false():
    result = _make_result(**_t4_base_kwargs(primary_available=False))
    ev = evaluate_test("t4", result, _T4_EXPECTED)
    assert ev["status"] == "fail"


def test_t4_missing_when_result_is_none():
    ev = evaluate_test("t4", None, _T4_EXPECTED)
    assert ev["status"] == "missing"


# =============================================================================
# t5
# =============================================================================


def test_t5_status_mirrors_t4_automatic_checks_and_carries_manual_items():
    result = _make_result(**_t4_base_kwargs())
    ev = evaluate_test("t5", result, _T4_EXPECTED)
    assert ev["status"] == "pass"
    assert len(ev["manual_items"]) == 3


def test_t5_fails_when_underlying_t4_checks_fail():
    result = _make_result(**_t4_base_kwargs(project_path="C:\\Projetos\\Outro.project"))
    ev = evaluate_test("t5", result, _T4_EXPECTED)
    assert ev["status"] == "fail"


def test_t5_missing_when_result_is_none():
    ev = evaluate_test("t5", None, _T4_EXPECTED)
    assert ev["status"] == "missing"


# =============================================================================
# build_gate_report
# =============================================================================


def _full_results_by_test(t5_result="same_as_t4"):
    t1 = _make_result(inside_mastertool=True, script_started=True, projects_available=False)
    t2 = _make_result(
        argv=["script.py", "--output", "C:\\saida\\dir"],
        output_dir_resolution=[{"layer": 1, "success": True}],
    )
    t4 = _make_result(**_t4_base_kwargs())
    results = {"t1": t1, "t2": t2, "t3": None, "t4": t4}
    if t5_result == "same_as_t4":
        results["t5"] = _make_result(**_t4_base_kwargs())
    else:
        results["t5"] = t5_result
    return results


def test_gate_b_unblocked_false_when_t3_not_manually_confirmed():
    results = _full_results_by_test()
    gate = build_gate_report(results, {"output_dir": "C:\\saida\\dir",
                                       "project_path": "C:\\Projetos\\Projeto.project"})
    assert gate["runscript_supported"] is True
    assert gate["scriptargs_supported"] is True
    assert gate["combined_execution_supported"] is True
    assert gate["project_supported"] == "pending_manual"
    assert gate["gate_b_unblocked"] is False


def test_gate_b_unblocked_true_when_all_confirmed_including_t3_manual():
    results = _full_results_by_test()
    expected = {
        "output_dir": "C:\\saida\\dir",
        "project_path": "C:\\Projetos\\Projeto.project",
        "t3_manual_confirmed": {
            "correct_project_opened": True,
            "no_conversion_or_license_dialog": True,
            "disposable_copy_hash_intact": True,
        },
    }
    gate = build_gate_report(results, expected)
    assert gate["project_supported"] == "confirmed"
    assert gate["gate_b_unblocked"] is True


def test_project_supported_failed_when_operator_explicitly_reproves_an_item():
    results = _full_results_by_test()
    expected = {
        "t3_manual_confirmed": {
            "correct_project_opened": False,
        },
    }
    gate = build_gate_report(results, expected)
    assert gate["project_supported"] == "failed"
    assert gate["gate_b_unblocked"] is False


def test_headless_status_not_tested_when_t5_absent():
    results = _full_results_by_test(t5_result=None)
    gate = build_gate_report(results, {})
    assert gate["headless_status"] == "not_tested"


def test_headless_status_unsupported_when_t5_fails():
    bad_t5 = _make_result(**_t4_base_kwargs(project_path="C:\\Projetos\\Outro.project"))
    results = _full_results_by_test(t5_result=bad_t5)
    gate = build_gate_report(
        results, {"output_dir": "C:\\saida\\dir", "project_path": "C:\\Projetos\\Projeto.project"})
    assert gate["headless_status"] == "unsupported"


def test_headless_status_unsafe_when_pass_but_manual_items_not_confirmed():
    results = _full_results_by_test()
    expected = {"output_dir": "C:\\saida\\dir", "project_path": "C:\\Projetos\\Projeto.project"}
    gate = build_gate_report(results, expected)
    assert gate["headless_status"] == "unsafe"


def test_headless_status_supported_when_pass_and_all_manual_items_confirmed():
    results = _full_results_by_test()
    expected = {
        "output_dir": "C:\\saida\\dir",
        "project_path": "C:\\Projetos\\Projeto.project",
        "t5_manual_confirmed": {
            "process_exit_code_ok": True,
            "no_orphan_process": True,
            "no_invisible_lock": True,
        },
    }
    gate = build_gate_report(results, expected)
    assert gate["headless_status"] == "supported"
    # headless NÃO bloqueia o gate mesmo quando "unsafe"/"unsupported"/
    # "not_tested" — só t1/t2/t3/t4 bloqueiam.
    expected["t3_manual_confirmed"] = {
        "correct_project_opened": True,
        "no_conversion_or_license_dialog": True,
        "disposable_copy_hash_intact": True,
    }
    gate2 = build_gate_report(results, expected)
    assert gate2["gate_b_unblocked"] is True


def test_gate_report_includes_summary_markdown_and_per_test():
    results = _full_results_by_test()
    gate = build_gate_report(results, {})
    assert isinstance(gate["summary_markdown"], str)
    assert "gate_b_unblocked" in gate["summary_markdown"]
    assert set(gate["per_test"].keys()) == {"t1", "t2", "t3", "t4", "t5"}


def test_build_gate_report_is_deterministic():
    results = _full_results_by_test()
    expected = {"output_dir": "C:\\saida\\dir", "project_path": "C:\\Projetos\\Projeto.project"}
    gate_a = build_gate_report(results, expected)
    gate_b = build_gate_report(results, expected)
    assert gate_a == gate_b


# =============================================================================
# discover_results / run_verification (I/O sobre disco, tmp_path)
# =============================================================================


def _write_result(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_discover_results_finds_files_by_test_id_in_path_case_insensitive(tmp_path):
    t1_result = _make_result(inside_mastertool=True, script_started=True)
    t4_result = _make_result(**_t4_base_kwargs())
    _write_result(tmp_path / "T1-runscript" / "result.json", t1_result)
    _write_result(tmp_path / "t4_combined" / "run-01" / "result.json", t4_result)

    found = discover_results(tmp_path)
    assert found["t1"]["script_started"] is True
    assert found["t4"]["project"]["path"] == "C:\\Projetos\\Projeto.project"
    assert found["t2"] is None
    assert found["t3"] is None
    assert found["t5"] is None


def test_discover_results_missing_dir_returns_all_none(tmp_path):
    found = discover_results(tmp_path / "does_not_exist")
    assert found == {"t1": None, "t2": None, "t3": None, "t4": None, "t5": None}


def test_run_verification_end_to_end_over_disk(tmp_path):
    _write_result(tmp_path / "t1" / "result.json",
                  _make_result(inside_mastertool=True, script_started=True))
    _write_result(tmp_path / "t2" / "result.json", _make_result(
        argv=["script.py", "--output", "C:\\saida\\dir"],
        output_dir_resolution=[{"layer": 1, "success": True}],
    ))
    _write_result(tmp_path / "t4" / "result.json", _make_result(**_t4_base_kwargs()))
    _write_result(tmp_path / "t5" / "result.json", _make_result(**_t4_base_kwargs()))

    expected = {
        "output_dir": "C:\\saida\\dir",
        "project_path": "C:\\Projetos\\Projeto.project",
        "t3_manual_confirmed": {
            "correct_project_opened": True,
            "no_conversion_or_license_dialog": True,
            "disposable_copy_hash_intact": True,
        },
    }
    gate = run_verification(tmp_path, expected)
    assert gate["gate_b_unblocked"] is True


# =============================================================================
# expected por teste (`per_test`) e coerência das observações
#
# Ambos cobrem defeitos encontrados na revisão da primeira versão do módulo:
# cada teste grava num diretório de saída PRÓPRIO, então um `output_dir`
# global sozinho fazia t4 reprovar sempre; e t4/t5 herdavam de t1 a
# observação "projects_available False é esperado", falsa quando há
# `--project`.
# =============================================================================


def _result_for_dir(out_dir: str, *, project_path: str | None = None, **kw) -> dict:
    return _make_result(
        argv=['--output "%s"' % out_dir],
        output_dir_resolution=[{"layer": 1, "source": "sys.argv --output",
                                "candidate": out_dir, "success": True}],
        project_path=project_path,
        **kw)


def test_per_test_expected_allows_distinct_output_dir_per_test():
    t2_dir = r"C:\repo\workspace\logs\cli-probe\t2"
    t4_dir = r"C:\repo\workspace\logs\cli-probe\t4"
    project = r"C:\Projetos\copia.project"

    expected = {
        "project_path": project,
        "per_test": {"t2": {"output_dir": t2_dir}, "t4": {"output_dir": t4_dir}},
    }

    t2 = evaluate_test("t2", _result_for_dir(t2_dir), expected)
    t4 = evaluate_test("t4", _result_for_dir(
        t4_dir, project_path=project, projects_available=True,
        primary_available=True), expected)

    assert t2["status"] == "pass"
    assert t4["status"] == "pass"


def test_global_output_dir_still_works_without_per_test():
    shared = r"C:\repo\workspace\logs\cli-probe"
    t2 = evaluate_test("t2", _result_for_dir(shared), {"output_dir": shared})
    assert t2["status"] == "pass"


def test_per_test_override_wins_over_global_key():
    global_dir = r"C:\repo\workspace\logs\global"
    t2_dir = r"C:\repo\workspace\logs\cli-probe\t2"
    expected = {"output_dir": global_dir, "per_test": {"t2": {"output_dir": t2_dir}}}

    # O artefato aponta para o diretório do override; o global não casaria.
    assert evaluate_test("t2", _result_for_dir(t2_dir), expected)["status"] == "pass"
    # E o inverso reprova, provando que o override realmente substituiu.
    assert evaluate_test("t2", _result_for_dir(global_dir), expected)["status"] == "fail"


def test_t4_does_not_inherit_the_no_project_observation_from_t1():
    out_dir = r"C:\repo\workspace\logs\cli-probe\t4"
    project = r"C:\Projetos\copia.project"
    expected = {"output_dir": out_dir, "project_path": project}

    t4 = evaluate_test("t4", _result_for_dir(
        out_dir, project_path=project, projects_available=True,
        primary_available=True), expected)

    assert not any("sem --project" in obs for obs in t4["observations"])
    # ...e a checagem de aprovação correspondente existe de verdade em t4.
    assert any(c["name"] == "globals.projects_available" and c["ok"]
               for c in t4["checks"])


def test_t1_and_t2_keep_the_no_project_observation():
    out_dir = r"C:\repo\workspace\logs\cli-probe\t2"
    t1 = evaluate_test("t1", _make_result(), {})
    t2 = evaluate_test("t2", _result_for_dir(out_dir), {"output_dir": out_dir})
    assert any("sem --project" in obs for obs in t1["observations"])
    assert any("sem --project" in obs for obs in t2["observations"])


def test_t5_does_not_inherit_the_no_project_observation_either():
    out_dir = r"C:\repo\workspace\logs\cli-probe\t5"
    project = r"C:\Projetos\copia.project"
    t5 = evaluate_test("t5", _result_for_dir(
        out_dir, project_path=project, projects_available=True,
        primary_available=True), {"output_dir": out_dir, "project_path": project})
    assert not any("sem --project" in obs for obs in t5["observations"])


# =============================================================================
# Desempate de discover_results (regressao do bug real de 2026-07-24: o gate
# reprovou t2 porque escolheu `collected-spaces-run/` em vez de `collected/`,
# por acidente de ordenacao alfabetica).
# =============================================================================


def test_discover_prefers_collected_dir_over_alphabetically_earlier_sibling(tmp_path):
    good = _make_result(argv=["marcador-bom"])
    bad = _make_result(argv=["marcador-ruim"])
    _write_result(tmp_path / "t2" / "collected" / "result.json", good)
    _write_result(tmp_path / "t2" / "collected-spaces-run" / "result.json", bad)

    # Ordem alfabetica pura escolheria 'collected-spaces-run': o '-' (0x2D)
    # precede tanto '\' (0x5C) quanto '/' (0x2F) como separador de caminho.
    sep = "\\"
    assert sorted(["collected-spaces-run" + sep, "collected" + sep])[0].startswith(
        "collected-spaces-run")

    found = discover_results(tmp_path)
    assert found["t2"]["argv"] == ["marcador-bom"]


def test_discover_falls_back_to_alphabetical_when_no_collected_dir(tmp_path):
    _write_result(tmp_path / "t4" / "aaa" / "result.json", _make_result(argv=["a"]))
    _write_result(tmp_path / "t4" / "bbb" / "result.json", _make_result(argv=["b"]))
    assert discover_results(tmp_path)["t4"]["argv"] == ["a"]


def test_discover_is_deterministic_across_calls(tmp_path):
    _write_result(tmp_path / "t1" / "collected" / "result.json", _make_result(argv=["x"]))
    _write_result(tmp_path / "t1" / "outro" / "result.json", _make_result(argv=["y"]))
    first = discover_results(tmp_path)
    for _ in range(3):
        assert discover_results(tmp_path) == first

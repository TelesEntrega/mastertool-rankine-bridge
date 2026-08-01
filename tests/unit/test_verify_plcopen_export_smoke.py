"""Verificador de smoke da exportação PLCopen (`tools/`).

A fixture é INTEIRAMENTE SINTÉTICA: nenhum nome de projeto, POU, GUID ou
caminho do cliente aparece aqui. Uma run real nunca é lida por estes testes.

Boa parte do que se protege abaixo veio de erros de uso cometidos durante o
primeiro smoke real, quando o verificador ainda era um script descartável:
`str` passado onde os helpers de hash exigem `Path`, veredito científico
procurado no arquivo errado, e `final_state` buscado num relatório que não o
contém. São exatamente os enganos que um verificador precisa não repetir — ele
existe para detectar problema, não para inventá-lo.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPO_ROOT / "tools" / "verify_plcopen_export_smoke.py"

_spec = importlib.util.spec_from_file_location("mtb_verify_smoke", str(TOOL_PATH))
verifier = importlib.util.module_from_spec(_spec)
sys.modules["mtb_verify_smoke"] = verifier
_spec.loader.exec_module(verifier)


# --- fixture sintética --------------------------------------------------------

IDENTITY = {
    "schema_version": 1,
    "target_node_id": "application/0/0",
    "name": "FB_SINTETICO",
    "guid": "00000000-0000-0000-0000-000000000001",
    "type_guid": "00000000-0000-0000-0000-000000000002",
    "is_folder": False,
    "identity_confirmed": True,
    "identity_check_reached": True,
    "mismatches": [],
}

ANALYSIS = {
    "schema_version": 1,
    "result_case": "P1_graphical_body_present",
    "element_counts": {"graphical_bodies": {"LD": 1}},
    "target_match": {"found": True, "has_graphical_body": True},
}

SAFETY = {
    "export_xml_called": True,
    "export_xml_call_count": 1,
    "filesystem_output_written": True,
    "filesystem_output_scope": "authorized_disposable_export_root",
    "project_save_called": False,
    "project_build_called": False,
    "text_document_write_called": False,
    "import_called": False,
    "online_operation": False,
    "download_called": False,
    "force_called": False,
}

DECLARATION = {
    "original_project_touched": False,
    "project_saved": False,
    "build_called": False,
    "online_operation": False,
    "download_called": False,
    "force_called": False,
    "runtime": {"provenance_confirmed": True},
}

RUN_CONFIG = {
    "schema_version": 1,
    "plcopen_export": {
        "expected_name": IDENTITY["name"],
        "expected_guid": IDENTITY["guid"],
        "expected_type_guid": IDENTITY["type_guid"],
        "target_node_id": IDENTITY["target_node_id"],
    },
}

HOST_REPORT = {
    "final_state": "completed",
    "project_hash_unchanged": True,
    "orphan_process_detected": False,
}

# Os artefatos que a validação host-side exige da exportação, além dos que a
# fixture já escreve com conteúdo próprio.
FILLER_ARTIFACTS = (
    "invocation.json", "filesystem-before.json", "filesystem-after.json",
    "created-artifacts.json", "diagnostics.json", "report.md",
    "export-root-preparation.json",
)


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_checksums(export_dir: Path, extra_lines=(), skip=()) -> None:
    lines = []
    for path in sorted(export_dir.iterdir()):
        if not path.is_file() or path.name == "checksums.sha256":
            continue
        if path.name in skip:
            continue
        lines.append("%s  %s" % (_sha256(path), path.name))
    lines.extend(extra_lines)
    (export_dir / "checksums.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def run_dir(tmp_path) -> Path:
    """Run sintética completa e aprovada."""
    run = tmp_path / "2000-01-01_00-00-00"
    export = run / "output" / verifier.EXPORT_DIRNAME
    export.mkdir(parents=True)
    (export / verifier.EXPORT_ROOT_DIRNAME).mkdir()
    (export / verifier.EXPORT_ROOT_DIRNAME / "pou-export").write_text(
        "<xml/>", encoding="utf-8")

    _write_json(export / "target-identity.json", IDENTITY)
    _write_json(export / "export-analysis.json", ANALYSIS)
    _write_json(export / "safety-declaration.json", SAFETY)
    for name in FILLER_ARTIFACTS:
        if name.endswith(".json"):
            _write_json(export / name, {})
        else:
            (export / name).write_text("# relatorio sintetico\n", encoding="utf-8")
    _write_checksums(export)

    _write_json(run / "status.json", {"state": "completed", "error": None})
    _write_json(run / "output" / "run-report.json", DECLARATION)
    _write_json(run / "run-config.json", RUN_CONFIG)

    # A validação host-side exige `run-report.json` e `checksums.sha256` no
    # próprio `output/`, além dos artefatos da exportação.
    _write_output_checksums(run / "output")
    return run


def _write_output_checksums(output_dir: Path) -> None:
    lines = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(output_dir).as_posix()
        if rel == "checksums.sha256":
            continue
        lines.append("%s  %s" % (_sha256(path), rel))
    (output_dir / "checksums.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def _by_name(checks, fragment):
    return [c for c in checks if fragment in c.name]


def _failed(checks):
    return [c.name for c in checks if not c.ok]


# --- caminho feliz ------------------------------------------------------------

def test_complete_synthetic_run_passes(run_dir):
    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert not _failed(checks), _failed(checks)


def test_cli_exit_code_zero(run_dir, capsys):
    assert verifier.main(["--run-dir", str(run_dir)]) == verifier.EXIT_OK


def test_output_is_deterministic(run_dir):
    first = verifier._render_text(verifier.verify_run(run_dir, host_report=HOST_REPORT))
    second = verifier._render_text(verifier.verify_run(run_dir, host_report=HOST_REPORT))
    assert first == second


def test_json_output_is_machine_readable(run_dir, capsys):
    code = verifier.main(["--run-dir", str(run_dir), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == verifier.EXIT_OK
    assert payload["ok"] is True and payload["failed"] == 0
    assert payload["total"] == len(payload["checks"])
    assert all({"name", "ok", "detail"} == set(c) for c in payload["checks"])


# --- 1. str vs Path nos helpers de hash ---------------------------------------

def test_string_run_dir_is_converted_before_hashing_helpers(run_dir):
    """`parse_checksums_file`/`sha256_file` exigem `Path`; um `str` vindo da
    linha de comando não pode chegar cru até eles."""
    checks = verifier.verify_run(str(run_dir), host_report=HOST_REPORT)
    assert not _failed(checks), _failed(checks)
    assert _by_name(checks, "todo hash confere")[0].ok


def test_cli_argument_is_a_plain_string(run_dir):
    assert verifier.main(["--run-dir", str(run_dir)]) == verifier.EXIT_OK


# --- 2 e 3. veredito científico ----------------------------------------------

def test_verdict_comes_from_the_analysis_not_the_report(run_dir):
    """`report.md` mencionando P1 não substitui a análise: apagar
    `export-analysis.json` tem de reprovar mesmo com o relatório citando P1."""
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    (export / "report.md").write_text(
        "resultado: P1_graphical_body_present\n", encoding="utf-8")
    (export / "export-analysis.json").unlink()
    _write_checksums(export)

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "export-analysis.json presente" in _failed(checks)


def test_probe_result_case_is_not_accepted_as_the_scientific_verdict(run_dir):
    """`P_created` é do probe: significa "invocou e criou entradas". Aceitá-lo
    como P1 confundiria estado operacional com resultado científico."""
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    _write_json(export / "export-analysis.json",
                dict(ANALYSIS, result_case="P_created"))
    _write_checksums(export)

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    offending = _by_name(checks, "não confundido com estado do probe")
    assert offending and not offending[0].ok
    assert "P_created" in offending[0].detail


# --- 4 e 5. declaração do runner × relatório do host --------------------------

def test_runner_declaration_and_host_report_are_distinct_sources(run_dir):
    """`output/run-report.json` não contém `final_state`; o verificador não
    pode tratá-lo como se contivesse."""
    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert _by_name(checks, "projeto original não foi tocado")[0].ok
    assert _by_name(checks, "final_state do host")[0].ok


def test_missing_host_report_does_not_invent_final_state(run_dir):
    checks = verifier.verify_run(run_dir, host_report=None)
    assert not _failed(checks)
    informed = _by_name(checks, "final_state do host informado")
    assert informed and "NÃO foi verificado" in informed[0].detail
    # e nenhuma checagem afirma que o final_state está correto
    assert not _by_name(checks, "final_state do host é completed")


def test_host_report_with_bad_final_state_fails(run_dir):
    checks = verifier.verify_run(
        run_dir, host_report=dict(HOST_REPORT, final_state="failed"))
    assert "final_state do host é completed" in _failed(checks)


def test_host_report_flags_touched_project(run_dir):
    checks = verifier.verify_run(
        run_dir, host_report=dict(HOST_REPORT, project_hash_unchanged=False))
    assert "hash do projeto inalterado" in _failed(checks)


# --- 6. hashes ----------------------------------------------------------------

def test_divergent_hash_fails(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    (export / "diagnostics.json").write_text('{"alterado": true}', encoding="utf-8")

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "todo hash confere" in _failed(checks)


def test_correct_hashes_pass(run_dir):
    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert _by_name(checks, "todo hash confere")[0].ok


# --- 7, 8, 9. identidade ------------------------------------------------------

def test_missing_identity_artifact_fails_a_fresh_run(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    (export / "target-identity.json").unlink()
    _write_checksums(export)

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "target-identity.json presente" in _failed(checks)


def test_identity_check_not_reached_fails(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    _write_json(export / "target-identity.json",
                dict(IDENTITY, identity_check_reached=False,
                     identity_confirmed=False))
    _write_checksums(export)

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "identity_check_reached é True" in _failed(checks)


def test_unconfirmed_identity_reports_the_mismatches(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    _write_json(export / "target-identity.json",
                dict(IDENTITY, identity_confirmed=False,
                     mismatches=["name", "object_guid"]))
    _write_checksums(export)

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    divergence = _by_name(checks, "sem divergências de identidade")[0]
    assert not divergence.ok
    assert "name" in divergence.detail and "object_guid" in divergence.detail


def test_string_schema_version_fails(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    _write_json(export / "target-identity.json", dict(IDENTITY, schema_version="1.0"))
    _write_checksums(export)

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "schema_version é o inteiro 1" in _failed(checks)


# --- 10, 11, 12. manifesto ----------------------------------------------------

def test_listed_but_missing_file_fails(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    ghost = export / "fantasma.json"
    _write_json(ghost, {})
    _write_checksums(export)
    ghost.unlink()

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "todo arquivo listado existe" in _failed(checks)


def test_orphan_temporary_file_fails(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    (export / "report.md.tmp").write_text("resto de falha", encoding="utf-8")

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "nenhum .tmp órfão no diretório" in _failed(checks)


def test_export_root_inside_the_manifest_fails(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    _write_checksums(export, extra_lines=[
        "%s  %s/pou-export" % ("0" * 64, verifier.EXPORT_ROOT_DIRNAME)])

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "export-root/ fora do manifesto" in _failed(checks)


# --- 13. safety declaration ---------------------------------------------------

def test_missing_export_call_fails(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    _write_json(export / "safety-declaration.json",
                dict(SAFETY, export_xml_called=False, export_xml_call_count=0))
    _write_checksums(export)

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "export_xml_called é True" in _failed(checks)
    assert "export_xml_call_count é 1" in _failed(checks)


def test_more_than_one_call_fails(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    _write_json(export / "safety-declaration.json",
                dict(SAFETY, export_xml_call_count=2))
    _write_checksums(export)

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "export_xml_call_count é 1" in _failed(checks)


def test_generic_write_called_key_is_rejected(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    _write_json(export / "safety-declaration.json",
                dict(SAFETY, write_called=False))
    _write_checksums(export)

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "sem a chave genérica write_called" in _failed(checks)


def test_forbidden_operation_fails(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    _write_json(export / "safety-declaration.json",
                dict(SAFETY, online_operation=True))
    _write_checksums(export)

    checks = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert "online_operation é False" in _failed(checks)


# --- uso inválido → código 2 --------------------------------------------------

def test_nonexistent_run_is_usage_error(tmp_path, capsys):
    assert verifier.main(["--run-dir", str(tmp_path / "nao-existe")]) == verifier.EXIT_USAGE


def test_directory_without_output_is_usage_error(tmp_path):
    (tmp_path / "run").mkdir()
    assert verifier.main(["--run-dir", str(tmp_path / "run")]) == verifier.EXIT_USAGE


def test_run_without_export_dir_is_usage_error(tmp_path):
    (tmp_path / "run" / "output").mkdir(parents=True)
    assert verifier.main(["--run-dir", str(tmp_path / "run")]) == verifier.EXIT_USAGE


def test_malformed_json_is_usage_error(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    (export / "target-identity.json").write_text("{ nao e json", encoding="utf-8")
    with pytest.raises(verifier.RunStructureError):
        verifier.verify_run(run_dir)


def test_failed_verification_exits_one(run_dir):
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    (export / "target-identity.json").unlink()
    _write_checksums(export)
    assert verifier.main(["--run-dir", str(run_dir)]) == verifier.EXIT_FAILED


def test_run_dir_argument_is_required(capsys):
    with pytest.raises(SystemExit):
        verifier.main([])


# --- modo histórico nunca é automático ---------------------------------------

def test_archived_mode_is_never_automatic(run_dir):
    """A validação roda estrita por padrão; o modo histórico existe só quando
    pedido explicitamente."""
    export = run_dir / "output" / verifier.EXPORT_DIRNAME
    (export / "target-identity.json").unlink()
    _write_checksums(export)
    # Sem regravar o manifesto de `output/`, a validação reprovaria por hash
    # divergente e o teste mediria outra coisa.
    _write_output_checksums(run_dir / "output")

    strict = verifier.verify_run(run_dir, host_report=HOST_REPORT)
    assert any("validação host-side" in c.name and not c.ok for c in strict)

    archived = verifier.verify_run(run_dir, host_report=HOST_REPORT,
                                   archived_revision=True)
    host_side = [c for c in archived if "validação host-side" in c.name]
    assert host_side and host_side[0].ok
    assert "revisão histórica" in host_side[0].name


# --- 15. a fixture não vaza nada real ----------------------------------------

def test_no_client_identifiers_in_this_module_or_the_tool():
    """Os tokens são montados por partes de propósito: escritos inteiros, este
    próprio teste os introduziria no arquivo que ele verifica."""
    forbidden = ("BLINK_" + "QUE_FUNCIONA", "TC_" + "Quimica",
                 "mastertool-ai-" + "bridge-runs", "beca" + "53e2",
                 "7bd3" + "0f35", "Rank" + "ine")
    for path in (Path(__file__), TOOL_PATH):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, "%s cita %r" % (path.name, token)

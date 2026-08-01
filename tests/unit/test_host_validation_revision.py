"""Revalidação host-side de runs arquivadas.

O ponto central destes testes: uma run arquivada NÃO pode ganhar procedência
confirmada por máquina retroativamente. O dado legível não está lá, e
declarar `confirmed` a partir da linha de log seria fabricar exatamente o
resultado que a correção existe para tornar verificável.
"""

from __future__ import annotations

import json

import pytest

from mastertool_bridge.automation.artifact_validation import (
    CHECKSUMS_FILENAME, FINAL_DECLARATION_KEYS)
from mastertool_bridge.automation.host_validation_revision import (
    HostRevisionError, revise_run, write_revision)


def _make_run(tmp_path, *, runtime=None, with_internal_evidence=True):
    run_dir = tmp_path / "run"
    output = run_dir / "output"
    output.mkdir(parents=True)

    report = {key: False for key in FINAL_DECLARATION_KEYS}
    if runtime is not None:
        report["runtime"] = runtime
    (output / "run-report.json").write_text(json.dumps(report), encoding="utf-8")

    import hashlib
    content = json.dumps(report)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    (output / CHECKSUMS_FILENAME).write_text(
        f"{digest}  run-report.json\n", encoding="utf-8")

    if with_internal_evidence:
        (run_dir / "status-history.jsonl").write_text(json.dumps({
            "state": "provenance_validated",
            "detail": "Procedencia IronPython/CLI 2.7 confirmada.",
            "updated_at": "2026-07-28T09:17:17",
        }) + "\n", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"state": "completed"}), encoding="utf-8")
    return run_dir


_VALID_RUNTIME = {"platform": "cli", "runtime_family": "IronPython",
                  "version_info": [2, 7, 12], "provenance_confirmed": True}


def test_run_with_valid_runtime_is_revised_to_completed(tmp_path):
    rev = revise_run(_make_run(tmp_path, runtime=_VALID_RUNTIME))

    assert rev.revised_final_state == "completed"
    assert rev.blocking_reasons == []
    assert rev.provenance_machine_check["inside_mastertool"] is True


def test_archived_run_without_runtime_stays_failed(tmp_path):
    """A evidência interna NÃO promove a run: é log, não o dado verificável."""
    rev = revise_run(_make_run(tmp_path, runtime=None))

    assert rev.revised_final_state == "failed"
    assert rev.provenance_machine_check["reason_code"] == "runtime_provenance_missing"
    # A evidência secundária É registrada -- mas separada, nunca fundida.
    assert rev.provenance_internal_evidence["found"] is True
    assert rev.provenance_internal_evidence["is_secondary_evidence"] is True
    assert rev.provenance_machine_check["inside_mastertool"] is False


def test_wrong_runtime_is_not_confused_with_missing(tmp_path):
    rev = revise_run(_make_run(tmp_path, runtime={
        "platform": "win32", "runtime_family": "CPython", "version_info": [3, 11, 8]}))

    assert rev.revised_final_state == "failed"
    assert rev.provenance_machine_check["reason_code"] == "runtime_provenance_mismatch"


def test_revision_never_touches_the_execution_record(tmp_path):
    run_dir = _make_run(tmp_path, runtime=_VALID_RUNTIME)
    before = {p.name: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}

    write_revision(revise_run(run_dir))

    for name, content in before.items():
        matches = [p for p in run_dir.rglob(name) if p.is_file()]
        assert matches and matches[0].read_bytes() == content, f"{name} alterado"


def test_markdown_states_machine_confirmation_is_not_retroactive(tmp_path):
    _json_path, md_path = write_revision(revise_run(_make_run(tmp_path, runtime=None)))
    md = md_path.read_text(encoding="utf-8")

    assert "ausência de prova" in md
    assert "Não promove esta run a procedência confirmada por máquina" in md


def test_nonexistent_run_is_refused(tmp_path):
    with pytest.raises(HostRevisionError, match="inexistente"):
        revise_run(tmp_path / "nao-existe")


# --- artefatos introduzidos depois de a run já existir ------------------------
#
# `target-identity.json` passou a ser exigido da exportação controlada durante
# a consolidação (docs/19-contratos-de-execucao.md, seção 4). Runs arquivadas
# antes disso não o têm e NÃO podem ser corrigidas retroativamente — refazer a
# aquisição é proibido. A ausência precisa virar aviso na revisão histórica e
# continuar sendo erro numa run nova; se as duas coincidirem, ou a revisão
# reprova runs legítimas, ou a validação de runs novas fica permissiva.

def _export_dir_with(tmp_path, filenames):
    from mastertool_bridge.automation.artifact_validation import PLCOPEN_EXPORT_DIRNAME

    output = tmp_path / "output"
    export_dir = output / PLCOPEN_EXPORT_DIRNAME
    export_dir.mkdir(parents=True)
    for name in filenames:
        (export_dir / name).write_text("{}", encoding="utf-8")
    return output


def test_artifact_introduced_later_is_error_for_a_fresh_run(tmp_path):
    from mastertool_bridge.automation.artifact_validation import (
        PLCOPEN_EXPORT_FILENAMES_INTRODUCED_LATER,
        PLCOPEN_EXPORT_REQUIRED_FILENAMES,
        validate_output_artifacts)

    keep = [f for f in PLCOPEN_EXPORT_REQUIRED_FILENAMES
            if f not in PLCOPEN_EXPORT_FILENAMES_INTRODUCED_LATER]
    output = _export_dir_with(tmp_path, keep)

    result = validate_output_artifacts(
        output, operations={"export_plcopen_xml": True})

    missing = [e for e in result.errors if "target-identity.json" in e]
    assert missing, f"run nova deveria reprovar: {result.errors}"
    assert not [w for w in result.warnings if "target-identity.json" in w]


def test_artifact_introduced_later_is_warning_for_an_archived_revision(tmp_path):
    from mastertool_bridge.automation.artifact_validation import (
        PLCOPEN_EXPORT_FILENAMES_INTRODUCED_LATER,
        PLCOPEN_EXPORT_REQUIRED_FILENAMES,
        validate_output_artifacts)

    keep = [f for f in PLCOPEN_EXPORT_REQUIRED_FILENAMES
            if f not in PLCOPEN_EXPORT_FILENAMES_INTRODUCED_LATER]
    output = _export_dir_with(tmp_path, keep)

    result = validate_output_artifacts(
        output, operations={"export_plcopen_xml": True}, archived_revision=True)

    assert not [e for e in result.errors if "target-identity.json" in e], result.errors
    warned = [w for w in result.warnings if "target-identity.json" in w]
    assert warned, f"ausência histórica deveria virar aviso: {result.warnings}"
    assert "introduzido depois" in warned[0]


def test_archived_revision_does_not_excuse_other_missing_artifacts(tmp_path):
    """O modo histórico perdoa SÓ os nomes declarados, nunca artefato antigo."""
    from mastertool_bridge.automation.artifact_validation import (
        PLCOPEN_EXPORT_FILENAMES_INTRODUCED_LATER,
        PLCOPEN_EXPORT_REQUIRED_FILENAMES,
        validate_output_artifacts)

    keep = [f for f in PLCOPEN_EXPORT_REQUIRED_FILENAMES
            if f not in PLCOPEN_EXPORT_FILENAMES_INTRODUCED_LATER
            and f != "checksums.sha256"]
    output = _export_dir_with(tmp_path, keep)

    result = validate_output_artifacts(
        output, operations={"export_plcopen_xml": True}, archived_revision=True)

    assert [e for e in result.errors if "checksums.sha256" in e], result.errors

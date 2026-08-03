"""Testes do lado HOST (Python 3.11, fora do MasterTool) da Etapa B —
`docs/16-supervised-runner-contract.md`.

NENHUM destes testes dispara `MT8500.exe` ou `tasklist` de verdade: todo
subprocesso é dublado (`process_launcher`/`process_lister` injetáveis).

Cobre, no mínimo (ver contrato do slice):
  - `bootstrap.py` gerado contém `globals()` na chamada de `main`;
  - `run-config.json` gerado tem exatamente as chaves da seção 2;
  - recusa quando a cópia == original;
  - recusa `operations` com `build:true`;
  - `read_status` cai para o histórico quando `status.json` some;
  - timeout produz `needs_interaction` sem matar processo;
  - hash final divergente reprova;
  - validação de artefato reprova quando `checksums.sha256` não fecha;
  - procedência CPython 3 (ou ausente) reprova.
"""

from __future__ import annotations


def _runscript_from_cmd(cmd):
    """Extrai o caminho do --runscript= de uma linha de comando em STRING.

    O comando deixou de ser lista quando se descobriu, na primeira execucao
    supervisionada real, que `subprocess.list2cmdline` cita o token inteiro
    e o MT8500 passa a ignorar a flag em silencio.
    """
    import re as _re
    match = _re.search(r'--runscript="([^"]+)"', cmd)
    assert match, "linha de comando sem --runscript=\"...\": %r" % (cmd,)
    return '--runscript=' + match.group(1)



import hashlib
import json

import pytest

from mastertool_bridge.automation.artifact_validation import (
    FINAL_DECLARATION_KEYS,
    LADDER_PROBE_DIRNAME,
    LADDER_PROBE_REQUIRED_FILENAMES,
    LADDER_PROBE_SAFETY_DECLARATION_KEYS,
    check_final_declaration,
    check_ladder_probe_safety_declaration,
    validate_output_artifacts,
    verify_checksums,
)
from mastertool_bridge.automation.config_models import (
    ConfigValidationError,
    LadderProbeConfig,
    RunConfig,
    RunOperations,
)
from mastertool_bridge.automation.run_workspace import (
    create_run_workspace,
    read_status,
    render_bootstrap,
)
from mastertool_bridge.automation.supervised_run import (
    _run_indexer,
    orchestrate_run,
    sha256_of_file,
)

_EXPORT_REQUIRED_FILES = ("manifest.json", "flat-objects.json",
                          "text-index.json", "checksums.sha256")


def _write_minimal_export_layout(export_dir) -> None:
    """Grava só a PRESENÇA dos arquivos exigidos por `_find_export_dir`
    (conteúdo irrelevante nestes testes: `build_static_index` é sempre
    dublado, nunca chamado de verdade sobre este conteúdo)."""
    export_dir.mkdir(parents=True, exist_ok=True)
    for name in _EXPORT_REQUIRED_FILES:
        (export_dir / name).write_text("{}", encoding="utf-8")


def _fake_static_index(*, symbols=5, types=2,
                       reference_states=("resolved", "resolved", "resolved", "unresolved"),
                       call_states=("resolved", "unresolved", "unresolved")) -> dict:
    return {
        "symbols": [{} for _ in range(symbols)],
        "type_symbols": [{} for _ in range(types)],
        "resolved_references": [{"resolution_state": s} for s in reference_states],
        "resolved_calls": [{"resolution_state": s} for s in call_states],
        "read_write_index": {
            "some_symbol": {"reads": [{}], "writes": [{}], "read_write": []},
            "_unresolved": [{}],
        },
    }

# =============================================================================
# Helpers
# =============================================================================


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_checksums_file(output_dir, files: dict[str, str]) -> None:
    lines = []
    for rel_path, content in files.items():
        target = output_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        lines.append(f"{_sha256_text(content)}  {rel_path}")
    (output_dir / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_ok_declaration(output_dir) -> None:
    declaration = {key: False for key in FINAL_DECLARATION_KEYS}
    (output_dir / "run-report.json").write_text(
        json.dumps(declaration), encoding="utf-8")


def _write_ok_ladder_probe_dir(output_dir, *, safety_overrides: dict | None = None,
                               omit_safety_keys: tuple[str, ...] = ()) -> None:
    """Grava `output_dir/ladder-surface-probe/` com os 12 artefatos exigidos
    pelo contrato (seção 3.1) e uma `safety-declaration.json` com as 10
    chaves em `False`, salvo o que `safety_overrides`/`omit_safety_keys`
    pedirem para o teste forçar uma reprovação."""
    ladder_dir = output_dir / LADDER_PROBE_DIRNAME
    ladder_dir.mkdir(parents=True, exist_ok=True)
    for name in LADDER_PROBE_REQUIRED_FILENAMES:
        if name == "safety-declaration.json":
            continue
        if name == "report.md":
            (ladder_dir / name).write_text("# report", encoding="utf-8")
        else:
            (ladder_dir / name).write_text("{}", encoding="utf-8")

    declaration = {key: False for key in LADDER_PROBE_SAFETY_DECLARATION_KEYS
                  if key not in omit_safety_keys}
    if safety_overrides:
        declaration.update(safety_overrides)
    (ladder_dir / "safety-declaration.json").write_text(
        json.dumps(declaration), encoding="utf-8")


def _make_valid_config(run_dir="C:\\runs\\r1", output_dir="C:\\runs\\r1\\output",
                       operations: RunOperations | None = None) -> RunConfig:
    return RunConfig(
        run_id="2026-07-24_17-30-00",
        mode="supervised_snapshot",
        repo_root="C:\\repo",
        mastertool_scripts_dir="C:\\repo\\scripts\\mastertool",
        expected_project_path="C:\\descartavel\\ExemploPlanta.project",
        expected_project_sha256="E278D1C2",
        expected_application_name="Application",
        expected_application_guid="00000000-0000-0000-0000-000000000001",
        expected_application_type_guid="639b491f-5557-464c-af91-1471bac9f549",
        run_dir=run_dir,
        output_dir=output_dir,
        allowed_output_root="C:\\runs",
        operations=operations or RunOperations(),
    )


class _FakePopen:
    """Dublê de `subprocess.Popen`. `exit_after_polls=None` nunca finaliza
    sozinho (simula timeout); um inteiro finaliza depois de N chamadas a
    `poll()`."""

    def __init__(self, exit_code=0, exit_after_polls=0):
        self.pid = 4242
        self._exit_code = exit_code
        self._exit_after_polls = exit_after_polls
        self._polls = 0

    def poll(self):
        if self._exit_after_polls is None:
            return None
        if self._polls >= self._exit_after_polls:
            return self._exit_code
        self._polls += 1
        return None


def _make_orchestrate_kwargs(tmp_path, **overrides):
    project_copy = tmp_path / "ExemploPlanta COPIA.project"
    project_copy.write_bytes(b"conteudo do projeto de teste")
    original_project = tmp_path / "ExemploPlanta.project"
    original_project.write_bytes(b"conteudo original, nunca tocado")
    runs_root = tmp_path / "runs"

    kwargs = dict(
        project_copy=str(project_copy),
        original_project=str(original_project),
        runs_root=str(runs_root),
        mastertool_exe="C:\\Program Files (x86)\\Altus\\MT8500 3.63\\MT8500\\Common\\MT8500.exe",
        repo_root="C:\\repo",
        mastertool_scripts_dir="C:\\repo\\scripts\\mastertool",
        expected_application_name="Application",
        expected_application_guid="00000000-0000-0000-0000-000000000001",
        expected_application_type_guid="639b491f-5557-464c-af91-1471bac9f549",
        process_lister=lambda: [],
        monotonic=_FakeClock(),
        sleep=lambda _seconds: None,
        run_index=False,
    )
    kwargs.update(overrides)
    return kwargs


class _FakeClock:
    """Relógio monotônico determinístico: avança 1.0s a cada leitura após a
    primeira (que fixa o instante inicial)."""

    def __init__(self, step=1.0):
        self._value = 0.0
        self._step = step
        self._first = True

    def __call__(self):
        if self._first:
            self._first = False
            return self._value
        self._value += self._step
        return self._value


# =============================================================================
# config_models.py
# =============================================================================


def test_run_config_to_dict_has_exact_keys_from_section_2():
    config = _make_valid_config()
    data = config.to_dict()
    expected_keys = {
        "schema_version", "run_id", "mode", "repo_root", "mastertool_scripts_dir",
        "expected_project_path", "expected_project_sha256",
        "expected_application_name", "expected_application_guid",
        "expected_application_type_guid", "run_dir", "output_dir",
        "allowed_output_root", "operations",
    }
    assert set(data.keys()) == expected_keys
    assert data["schema_version"] == 1
    assert set(data["operations"].keys()) == {
        "scan_project_tree", "export_text", "inventory_graphic_objects",
        "probe_ladder_surface", "probe_ladder_dynamic_surface",
        "probe_ladder_extender_surface", "probe_plcopen_export_signature",
        "export_plcopen_xml",
        "build", "save", "online",
    }


def test_run_operations_rejects_build_true():
    with pytest.raises(ConfigValidationError):
        RunOperations(build=True)


def test_run_operations_rejects_save_true():
    with pytest.raises(ConfigValidationError):
        RunOperations(save=True)


def test_run_operations_rejects_online_true():
    with pytest.raises(ConfigValidationError):
        RunOperations(online=True)


def test_run_operations_rejects_download_or_force_via_extra():
    with pytest.raises(ConfigValidationError):
        RunOperations(extra={"download": True})
    with pytest.raises(ConfigValidationError):
        RunOperations(extra={"force": True})


def test_run_operations_rejects_unknown_key():
    with pytest.raises(ConfigValidationError):
        RunOperations(extra={"reticulate_splines": True})


def test_run_operations_accepts_known_false_flags():
    ops = RunOperations(inventory_graphic_objects=True)
    assert ops.to_dict()["inventory_graphic_objects"] is True
    assert ops.to_dict()["build"] is False


def test_run_config_rejects_empty_required_field():
    with pytest.raises(ConfigValidationError):
        RunConfig(
            run_id="", mode="supervised_snapshot", repo_root="C:\\repo",
            mastertool_scripts_dir="C:\\repo\\scripts\\mastertool",
            expected_project_path="C:\\x.project", expected_project_sha256="abc",
            expected_application_name="Application",
            expected_application_guid="g", expected_application_type_guid="t",
            run_dir="C:\\runs\\r1", output_dir="C:\\runs\\r1\\output",
            allowed_output_root="C:\\runs", operations=RunOperations())


def _make_ladder_probe_config() -> LadderProbeConfig:
    return LadderProbeConfig(
        target_node_id="application/9/4",
        expected_name="BLINK_QUE_FUNCIONA",
        expected_guid="beca53e2-8466-404a-baf5-9fba1adc0fac",
        expected_type_guid="6f9dac99-8de1-4efc-8465-68ac443b7d08",
    )


# =============================================================================
# config_models.py — ladder_probe (Fase L1, contrato seção 3.1)
# =============================================================================


def test_run_config_rejects_probe_ladder_surface_true_without_ladder_probe():
    with pytest.raises(ConfigValidationError):
        _make_valid_config(operations=RunOperations(probe_ladder_surface=True))


def test_run_config_rejects_ladder_probe_present_when_operation_off():
    # Direção que normalmente se esquece: seção presente, operação desligada.
    with pytest.raises(ConfigValidationError):
        RunConfig(
            run_id="2026-07-24_17-30-00", mode="supervised_snapshot",
            repo_root="C:\\repo", mastertool_scripts_dir="C:\\repo\\scripts\\mastertool",
            expected_project_path="C:\\descartavel\\ExemploPlanta.project",
            expected_project_sha256="E278D1C2",
            expected_application_name="Application",
            expected_application_guid="00000000-0000-0000-0000-000000000001",
            expected_application_type_guid="639b491f-5557-464c-af91-1471bac9f549",
            run_dir="C:\\runs\\r1", output_dir="C:\\runs\\r1\\output",
            allowed_output_root="C:\\runs",
            operations=RunOperations(probe_ladder_surface=False),
            ladder_probe=_make_ladder_probe_config())


def test_ladder_probe_config_rejects_empty_field():
    with pytest.raises(ConfigValidationError):
        LadderProbeConfig(target_node_id="", expected_name="x",
                          expected_guid="y", expected_type_guid="z")


def test_run_config_to_dict_emits_ladder_probe_section_with_exact_four_fields():
    config = RunConfig(
        run_id="2026-07-24_17-30-00", mode="supervised_snapshot",
        repo_root="C:\\repo", mastertool_scripts_dir="C:\\repo\\scripts\\mastertool",
        expected_project_path="C:\\descartavel\\ExemploPlanta.project",
        expected_project_sha256="E278D1C2",
        expected_application_name="Application",
        expected_application_guid="00000000-0000-0000-0000-000000000001",
        expected_application_type_guid="639b491f-5557-464c-af91-1471bac9f549",
        run_dir="C:\\runs\\r1", output_dir="C:\\runs\\r1\\output",
        allowed_output_root="C:\\runs",
        operations=RunOperations(probe_ladder_surface=True),
        ladder_probe=_make_ladder_probe_config())
    data = config.to_dict()
    assert set(data["ladder_probe"].keys()) == {
        "target_node_id", "expected_name", "expected_guid", "expected_type_guid"}
    assert data["ladder_probe"]["target_node_id"] == "application/9/4"
    assert data["ladder_probe"]["expected_name"] == "BLINK_QUE_FUNCIONA"


def test_run_config_to_dict_omits_ladder_probe_when_absent():
    config = _make_valid_config()
    data = config.to_dict()
    assert "ladder_probe" not in data


# =============================================================================
# run_workspace.py
# =============================================================================


def test_bootstrap_skeleton_calls_main_with_globals():
    text = render_bootstrap()
    assert "supervised_snapshot_runner.main(run_dir, globals())" in text
    assert "from automation import supervised_snapshot_runner" in text


def test_create_run_workspace_writes_bootstrap_with_globals_call(tmp_path):
    config = _make_valid_config(
        run_dir=str(tmp_path / "runs" / "r1"),
        output_dir=str(tmp_path / "runs" / "r1" / "output"))
    run_dir = create_run_workspace(tmp_path / "runs", "r1", config)
    bootstrap_text = (run_dir / "bootstrap.py").read_text(encoding="utf-8")
    assert "globals()" in bootstrap_text
    # É a ÚLTIMA linha não vazia — o contrato exige que seja a chamada final.
    non_empty_lines = [ln for ln in bootstrap_text.splitlines() if ln.strip()]
    assert non_empty_lines[-1].strip().endswith("globals())")


def test_create_run_workspace_creates_logs_and_output_dirs(tmp_path):
    config = _make_valid_config(
        run_dir=str(tmp_path / "runs" / "r1"),
        output_dir=str(tmp_path / "runs" / "r1" / "output"))
    run_dir = create_run_workspace(tmp_path / "runs", "r1", config)
    assert (run_dir / "logs").is_dir()
    assert (run_dir / "output").is_dir()
    assert (run_dir / "run-config.json").is_file()


def test_create_run_workspace_writes_exact_run_config_keys(tmp_path):
    config = _make_valid_config(
        run_dir=str(tmp_path / "runs" / "r1"),
        output_dir=str(tmp_path / "runs" / "r1" / "output"))
    run_dir = create_run_workspace(tmp_path / "runs", "r1", config)
    written = json.loads((run_dir / "run-config.json").read_text(encoding="utf-8"))
    assert set(written.keys()) == set(config.to_dict().keys())


def test_create_run_workspace_refuses_nonempty_existing_dir(tmp_path):
    config = _make_valid_config(
        run_dir=str(tmp_path / "runs" / "r1"),
        output_dir=str(tmp_path / "runs" / "r1" / "output"))
    create_run_workspace(tmp_path / "runs", "r1", config)
    with pytest.raises(FileExistsError):
        create_run_workspace(tmp_path / "runs", "r1", config)


def test_read_status_reads_status_json(tmp_path):
    run_dir = tmp_path / "r1"
    run_dir.mkdir()
    (run_dir / "status.json").write_text(
        json.dumps({"state": "exporting"}), encoding="utf-8")
    status = read_status(run_dir)
    assert status["state"] == "exporting"


def test_read_status_falls_back_to_history_when_status_json_missing(tmp_path):
    run_dir = tmp_path / "r1"
    run_dir.mkdir()
    history = run_dir / "status-history.jsonl"
    history.write_text(
        json.dumps({"state": "scanning"}) + "\n"
        + json.dumps({"state": "exporting"}) + "\n",
        encoding="utf-8")
    # status.json NUNCA foi escrito (ou já foi removido na janela não-atômica).
    status = read_status(run_dir)
    assert status["state"] == "exporting"


def test_read_status_falls_back_to_history_when_status_json_corrupted(tmp_path):
    run_dir = tmp_path / "r1"
    run_dir.mkdir()
    (run_dir / "status.json").write_text("{ nao e json valido", encoding="utf-8")
    history = run_dir / "status-history.jsonl"
    history.write_text(json.dumps({"state": "validating"}) + "\n", encoding="utf-8")
    status = read_status(run_dir)
    assert status["state"] == "validating"


def test_read_status_returns_none_when_nothing_exists(tmp_path):
    run_dir = tmp_path / "r1"
    run_dir.mkdir()
    assert read_status(run_dir) is None


# =============================================================================
# artifact_validation.py
# =============================================================================


def test_verify_checksums_ok_when_hashes_match(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _write_checksums_file(output_dir, {"a.json": '{"x": 1}', "sub/b.txt": "hello"})
    ok, errors = verify_checksums(output_dir)
    assert ok is True
    assert errors == []


def test_verify_checksums_fails_when_file_modified_after_checksum(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _write_checksums_file(output_dir, {"a.json": '{"x": 1}'})
    (output_dir / "a.json").write_text('{"x": 2}', encoding="utf-8")
    ok, errors = verify_checksums(output_dir)
    assert ok is False
    assert any("não fecha" in e for e in errors)


def test_verify_checksums_fails_when_file_missing(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _write_checksums_file(output_dir, {"a.json": '{"x": 1}'})
    (output_dir / "a.json").unlink()
    ok, errors = verify_checksums(output_dir)
    assert ok is False


def test_verify_checksums_fails_when_file_absent():
    ok, errors = verify_checksums(__import__("pathlib").Path("C:\\does-not-exist"))
    assert ok is False
    assert errors


def test_check_final_declaration_ok_with_all_six_keys_false(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _write_ok_declaration(output_dir)
    declaration, errors = check_final_declaration(output_dir)
    assert errors == []
    assert set(declaration.keys()) == set(FINAL_DECLARATION_KEYS)


def test_check_final_declaration_fails_when_key_true(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    declaration = {key: False for key in FINAL_DECLARATION_KEYS}
    declaration["project_saved"] = True
    (output_dir / "run-report.json").write_text(json.dumps(declaration), encoding="utf-8")
    _declaration, errors = check_final_declaration(output_dir)
    assert errors


def test_check_final_declaration_fails_when_key_missing(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    declaration = {key: False for key in FINAL_DECLARATION_KEYS if key != "force_called"}
    (output_dir / "run-report.json").write_text(json.dumps(declaration), encoding="utf-8")
    _declaration, errors = check_final_declaration(output_dir)
    assert any("force_called" in e for e in errors)


def test_validate_output_artifacts_ok_when_everything_closes(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _write_ok_declaration(output_dir)
    _write_checksums_file(output_dir, {"scan.json": "{}"})
    result = validate_output_artifacts(output_dir, {})
    assert result.ok is True, result.errors


def test_validate_output_artifacts_fails_when_checksums_do_not_close(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _write_ok_declaration(output_dir)
    _write_checksums_file(output_dir, {"scan.json": "{}"})
    (output_dir / "scan.json").write_text("{corrompido}", encoding="utf-8")
    result = validate_output_artifacts(output_dir, {})
    assert result.ok is False
    assert any("não fecha" in e for e in result.errors)


def test_validate_output_artifacts_fails_when_errors_json_nonempty(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _write_ok_declaration(output_dir)
    _write_checksums_file(output_dir, {"scan.json": "{}"})
    (output_dir / "errors.json").write_text(json.dumps(["algo deu errado"]), encoding="utf-8")
    result = validate_output_artifacts(output_dir, {})
    assert result.ok is False


# =============================================================================
# artifact_validation.py — ladder-surface-probe (Fase L1, contrato seção 3.1)
# =============================================================================


def test_check_ladder_probe_safety_declaration_ok_with_all_ten_keys_false(tmp_path):
    output_dir = tmp_path / "output"
    _write_ok_ladder_probe_dir(output_dir)
    declaration, errors = check_ladder_probe_safety_declaration(output_dir / LADDER_PROBE_DIRNAME)
    assert errors == []
    assert set(declaration.keys()) == set(LADDER_PROBE_SAFETY_DECLARATION_KEYS)


def test_check_ladder_probe_safety_declaration_fails_when_any_key_true(tmp_path):
    output_dir = tmp_path / "output"
    _write_ok_ladder_probe_dir(output_dir, safety_overrides={"export_called": True})
    _declaration, errors = check_ladder_probe_safety_declaration(output_dir / LADDER_PROBE_DIRNAME)
    assert errors
    assert any("export_called" in e for e in errors)


def test_check_ladder_probe_safety_declaration_fails_when_key_missing(tmp_path):
    output_dir = tmp_path / "output"
    _write_ok_ladder_probe_dir(output_dir, omit_safety_keys=("project_modified",))
    _declaration, errors = check_ladder_probe_safety_declaration(output_dir / LADDER_PROBE_DIRNAME)
    assert errors
    assert any("project_modified" in e for e in errors)


def test_validate_output_artifacts_fails_when_ladder_probe_dir_missing(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _write_ok_declaration(output_dir)
    _write_checksums_file(output_dir, {"scan.json": "{}"})
    # ladder-surface-probe/ nunca foi gravado.
    result = validate_output_artifacts(output_dir, {"probe_ladder_surface": True})
    assert result.ok is False
    assert any("ladder-surface-probe" in e for e in result.errors)


def test_validate_output_artifacts_fails_when_one_ladder_artifact_missing(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _write_ok_declaration(output_dir)
    _write_checksums_file(output_dir, {"scan.json": "{}"})
    _write_ok_ladder_probe_dir(output_dir)
    (output_dir / LADDER_PROBE_DIRNAME / "methods.json").unlink()
    result = validate_output_artifacts(output_dir, {"probe_ladder_surface": True})
    assert result.ok is False
    assert any("methods.json" in e for e in result.errors)


def test_validate_output_artifacts_ok_with_ladder_probe_complete(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _write_ok_declaration(output_dir)
    _write_checksums_file(output_dir, {"scan.json": "{}"})
    _write_ok_ladder_probe_dir(output_dir)
    result = validate_output_artifacts(output_dir, {"probe_ladder_surface": True})
    assert result.ok is True, result.errors


def test_sha256_of_file_matches_hashlib(tmp_path):
    target = tmp_path / "x.bin"
    target.write_bytes(b"conteudo qualquer")
    assert sha256_of_file(target) == hashlib.sha256(b"conteudo qualquer").hexdigest()


# =============================================================================
# supervised_run.py — orchestrate_run
# =============================================================================


def test_orchestrate_run_refuses_when_copy_equals_original(tmp_path):
    project = tmp_path / "ExemploPlanta.project"
    project.write_bytes(b"original")
    kwargs = _make_orchestrate_kwargs(
        tmp_path, project_copy=str(project), original_project=str(project))
    result = orchestrate_run(**kwargs)
    assert result.final_state == "failed"
    assert any("ORIGINAL" in r for r in result.reasons)


def test_orchestrate_run_refuses_when_mastertool_already_running(tmp_path):
    kwargs = _make_orchestrate_kwargs(
        tmp_path, process_lister=lambda: [{"image_name": "MT8500.exe", "pid": 999}])
    result = orchestrate_run(**kwargs)
    assert result.final_state == "failed"
    assert any("999" in r for r in result.reasons)


def test_orchestrate_run_fails_when_run_index_true_and_export_text_false(tmp_path):
    kwargs = _make_orchestrate_kwargs(
        tmp_path, run_index=True, operations=RunOperations(export_text=False))
    result = orchestrate_run(**kwargs)
    assert result.final_state == "failed"
    assert any("incoerente" in r for r in result.reasons)


def test_orchestrate_run_ladder_only_completes(tmp_path, monkeypatch):
    from pathlib import Path as _Path

    monkeypatch.setattr(
        "mastertool_bridge.indexer.export_loader.build_static_index",
        lambda export_dir, output_dir: _fake_static_index())

    ladder_probe_dict = {
        "target_node_id": "application/9/4",
        "expected_name": "BLINK_QUE_FUNCIONA",
        "expected_guid": "beca53e2-8466-404a-baf5-9fba1adc0fac",
        "expected_type_guid": "6f9dac99-8de1-4efc-8465-68ac443b7d08",
    }

    def launcher(cmd):
        runscript_arg = _runscript_from_cmd(cmd)
        bootstrap_path = _Path(runscript_arg.split("=", 1)[1])
        run_dir = bootstrap_path.parent
        output_dir = run_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_ok_declaration(output_dir)
        _write_checksums_file(output_dir, {"scan.json": "{}"})
        _write_ok_ladder_probe_dir(output_dir)
        status = {
            "schema_version": 1, "state": "completed",
            "runtime": {"platform": "cli", "runtime_family": "IronPython",
                       "version_info": [2, 7, 12, "final", 0]},
        }
        (run_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")
        (run_dir / "status-history.jsonl").write_text(
            json.dumps(status) + "\n", encoding="utf-8")
        return _FakePopen(exit_code=0, exit_after_polls=0)

    kwargs = _make_orchestrate_kwargs(
        tmp_path, process_launcher=launcher, run_index=False,
        operations=RunOperations(scan_project_tree=False, export_text=False,
                                 probe_ladder_surface=True),
        ladder_probe=ladder_probe_dict)
    result = orchestrate_run(**kwargs)
    assert result.final_state == "completed", result.reasons
    assert result.artifact_validation.ok is True
    assert result.index_result.attempted is False


def test_orchestrate_run_timeout_produces_needs_interaction_without_killing(tmp_path):
    launched = {}

    def launcher(cmd):
        proc = _FakePopen(exit_after_polls=None)  # nunca termina sozinho
        launched["proc"] = proc
        launched["cmd"] = cmd
        return proc

    kwargs = _make_orchestrate_kwargs(
        tmp_path, process_launcher=launcher, timeout_seconds=3.0,
        monotonic=_FakeClock(step=1.0))
    result = orchestrate_run(**kwargs)
    assert result.final_state == "needs_interaction"
    # Nenhum método de finalização foi chamado no dublê — ele não tem
    # kill()/terminate() nem foram adicionados; se o orquestrador tentasse
    # chamar um deles, o teste levantaria AttributeError.
    assert launched["proc"].poll() is None


def test_orchestrate_run_never_uses_scriptargs_or_nouI(tmp_path):
    captured = {}

    def launcher(cmd):
        captured["cmd"] = cmd
        return _FakePopen(exit_code=0, exit_after_polls=0)

    kwargs = _make_orchestrate_kwargs(tmp_path, process_launcher=launcher)
    orchestrate_run(**kwargs)
    cmd_str = captured["cmd"]
    assert "--scriptargs" not in cmd_str
    assert "--noUI" not in cmd_str
    assert '--project="' in captured["cmd"]
    assert '--runscript="' in captured["cmd"]


def test_orchestrate_run_fails_when_final_hash_differs(tmp_path):
    project_copy_holder = {}

    def launcher(cmd):
        # Simula o MasterTool alterando a cópia (nunca deveria acontecer,
        # mas o host precisa detectar).
        path = project_copy_holder["path"]
        path.write_bytes(b"conteudo MODIFICADO pelo processo")
        return _FakePopen(exit_code=0, exit_after_polls=0)

    kwargs = _make_orchestrate_kwargs(tmp_path, process_launcher=launcher)
    project_copy_holder["path"] = __import__("pathlib").Path(kwargs["project_copy"])
    result = orchestrate_run(**kwargs)
    assert result.final_state == "failed"
    assert result.project_hash_unchanged is False
    assert any("MODIFICADA" in r for r in result.reasons)


def test_orchestrate_run_fails_when_artifacts_missing(tmp_path):
    kwargs = _make_orchestrate_kwargs(
        tmp_path, process_launcher=lambda cmd: _FakePopen(exit_code=0, exit_after_polls=0))
    result = orchestrate_run(**kwargs)
    # Nada foi gravado em output/ pelo dublê -> artefatos obrigatórios ausentes.
    assert result.final_state == "failed"
    assert result.artifact_validation is not None
    assert result.artifact_validation.ok is False


def test_orchestrate_run_fails_when_provenance_is_cpython3(tmp_path):
    def launcher(cmd):
        return _FakePopen(exit_code=0, exit_after_polls=0)

    kwargs = _make_orchestrate_kwargs(tmp_path, process_launcher=launcher)
    result = orchestrate_run(**kwargs)
    # Sem status.json/run-report.json com "runtime", check_provenance
    # reprova por ausência de prova (fail-closed) — cobre tanto o caso
    # "sem prova" quanto o caso explícito CPython 3 (mesma checagem).
    assert result.final_state == "failed"
    assert result.provenance is not None
    assert result.provenance.inside_mastertool is False


def test_orchestrate_run_completed_when_everything_closes(tmp_path):
    def launcher(cmd):
        return _FakePopen(exit_code=0, exit_after_polls=0)

    kwargs = _make_orchestrate_kwargs(tmp_path, process_launcher=launcher)
    result = orchestrate_run(**kwargs)
    # Grava os artefatos e o status "de dentro do MasterTool" ANTES de rodar
    # de novo não é possível (o launcher já rodou); então testamos via
    # segunda chamada que primeiro popula output/ manualmente através de um
    # launcher que grava os artefatos como o runner interno faria.
    assert result.final_state == "failed"  # nenhum artefato + sem provenance


def test_orchestrate_run_completed_when_internal_runner_produced_everything(tmp_path):
    from pathlib import Path as _Path

    run_dir_holder = {}

    def launcher(cmd):
        runscript_arg = _runscript_from_cmd(cmd)
        bootstrap_path = _Path(runscript_arg.split("=", 1)[1])
        run_dir = bootstrap_path.parent
        run_dir_holder["run_dir"] = run_dir
        output_dir = run_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_ok_declaration(output_dir)
        _write_checksums_file(output_dir, {"scan.json": "{}"})
        status = {
            "schema_version": 1, "state": "completed",
            "runtime": {"platform": "cli", "runtime_family": "IronPython",
                       "version_info": [2, 7, 12, "final", 0]},
        }
        (run_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")
        (run_dir / "status-history.jsonl").write_text(
            json.dumps(status) + "\n", encoding="utf-8")
        return _FakePopen(exit_code=0, exit_after_polls=0)

    kwargs = _make_orchestrate_kwargs(tmp_path, process_launcher=launcher)
    result = orchestrate_run(**kwargs)
    assert result.final_state == "completed", result.reasons
    assert result.provenance.inside_mastertool is True
    assert result.artifact_validation.ok is True
    assert result.exit_code == 0


# =============================================================================
# _run_indexer — StaticProjectIndexer (build_static_index), não o
# export/indexer.py antigo
# =============================================================================


def test_run_indexer_calls_build_static_index_entry_point(tmp_path, monkeypatch):
    calls = {}

    def fake_build_static_index(export_dir, output_dir):
        calls["export_dir"] = export_dir
        calls["output_dir"] = output_dir
        return _fake_static_index()

    monkeypatch.setattr(
        "mastertool_bridge.indexer.export_loader.build_static_index",
        fake_build_static_index)

    output_dir = tmp_path / "output"
    _write_minimal_export_layout(output_dir)

    result = _run_indexer(output_dir, expected_index_counts=None)

    assert calls["export_dir"] == output_dir
    assert result.attempted is True
    assert result.skipped is False
    assert result.ok is True


def test_run_indexer_extracts_counts_with_real_key_names(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "mastertool_bridge.indexer.export_loader.build_static_index",
        lambda export_dir, output_dir: _fake_static_index())

    output_dir = tmp_path / "output"
    _write_minimal_export_layout(output_dir)

    result = _run_indexer(output_dir, expected_index_counts=None)

    assert result.counts == {
        "symbols": 5,
        "type_symbols": 2,
        "resolved_references": {"resolved": 3, "unresolved": 1},
        "resolved_calls": {"resolved": 1, "unresolved": 2},
        "read_write_entries": 3,  # 1 read + 1 write + 0 read_write + 1 _unresolved
    }
    assert result.mismatches == []


def test_run_indexer_no_mismatch_when_expected_counts_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "mastertool_bridge.indexer.export_loader.build_static_index",
        lambda export_dir, output_dir: _fake_static_index())
    output_dir = tmp_path / "output"
    _write_minimal_export_layout(output_dir)

    result = _run_indexer(output_dir, expected_index_counts=None)
    assert result.mismatches == []
    assert result.ok is True


def test_run_indexer_reports_mismatch_against_expected_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "mastertool_bridge.indexer.export_loader.build_static_index",
        lambda export_dir, output_dir: _fake_static_index())
    output_dir = tmp_path / "output"
    _write_minimal_export_layout(output_dir)

    result = _run_indexer(output_dir, expected_index_counts={"symbols": 60, "type_symbols": 8})
    assert result.mismatches
    assert any("symbols" in m for m in result.mismatches)


def test_run_indexer_requested_but_export_incomplete_fails_ok_false(tmp_path):
    # Índice foi PEDIDO (esta função só é chamada quando run_index=True) e o
    # export está incompleto: skipped=True mas ok=False — um passo pedido
    # que não rodou nunca pode se apresentar como sucesso silencioso.
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    result = _run_indexer(output_dir, expected_index_counts=None)
    assert result.attempted is True
    assert result.skipped is True
    assert result.ok is False
    assert result.reason


def test_run_indexer_reason_names_the_actually_missing_files(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    # Só manifest.json presente — faltam flat-objects.json, text-index.json,
    # checksums.sha256. O motivo deve nomear ESSES, não a lista genérica.
    (output_dir / "manifest.json").write_text("{}", encoding="utf-8")

    result = _run_indexer(output_dir, expected_index_counts=None)
    assert result.ok is False
    assert "flat-objects.json" in result.reason
    assert "text-index.json" in result.reason
    assert "checksums.sha256" in result.reason
    assert "manifest.json" not in result.reason.split("faltam")[1].split(";")[0]


def test_find_export_dir_reports_missing_files_per_candidate(tmp_path):
    from mastertool_bridge.automation.supervised_run import _find_export_dir

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "manifest.json").write_text("{}", encoding="utf-8")
    subdir = output_dir / "export"
    subdir.mkdir()
    (subdir / "flat-objects.json").write_text("[]", encoding="utf-8")

    found, diagnostics = _find_export_dir(output_dir)
    assert found is None
    assert len(diagnostics) == 2  # output_dir e output_dir/export
    assert any("flat-objects.json" in d for d in diagnostics if str(output_dir) in d
               and "export" not in d.replace(str(output_dir), ""))
    assert any("manifest.json" in d for d in diagnostics if "export" in d)


def test_find_export_dir_finds_export_in_immediate_subdir(tmp_path):
    from mastertool_bridge.automation.supervised_run import _find_export_dir

    output_dir = tmp_path / "output"
    subdir = output_dir / "export"
    _write_minimal_export_layout(subdir)

    found, diagnostics = _find_export_dir(output_dir)
    assert found == subdir
    assert diagnostics == []


def test_orchestrate_run_completed_with_matching_expected_index_counts(tmp_path, monkeypatch):
    from pathlib import Path as _Path

    monkeypatch.setattr(
        "mastertool_bridge.indexer.export_loader.build_static_index",
        lambda export_dir, output_dir: _fake_static_index())

    def launcher(cmd):
        runscript_arg = _runscript_from_cmd(cmd)
        bootstrap_path = _Path(runscript_arg.split("=", 1)[1])
        run_dir = bootstrap_path.parent
        output_dir = run_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_ok_declaration(output_dir)
        _write_minimal_export_layout(output_dir)
        _write_checksums_file(output_dir, {"scan.json": "{}"})
        status = {
            "schema_version": 1, "state": "completed",
            "runtime": {"platform": "cli", "runtime_family": "IronPython",
                       "version_info": [2, 7, 12, "final", 0]},
        }
        (run_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")
        (run_dir / "status-history.jsonl").write_text(
            json.dumps(status) + "\n", encoding="utf-8")
        return _FakePopen(exit_code=0, exit_after_polls=0)

    kwargs = _make_orchestrate_kwargs(
        tmp_path, process_launcher=launcher, run_index=True,
        expected_index_counts={"symbols": 5, "type_symbols": 2})
    result = orchestrate_run(**kwargs)
    assert result.final_state == "completed", result.reasons
    assert result.index_result.mismatches == []


def test_orchestrate_run_fails_when_index_counts_diverge_from_expected(tmp_path, monkeypatch):
    from pathlib import Path as _Path

    monkeypatch.setattr(
        "mastertool_bridge.indexer.export_loader.build_static_index",
        lambda export_dir, output_dir: _fake_static_index())

    def launcher(cmd):
        runscript_arg = _runscript_from_cmd(cmd)
        bootstrap_path = _Path(runscript_arg.split("=", 1)[1])
        run_dir = bootstrap_path.parent
        output_dir = run_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_ok_declaration(output_dir)
        _write_minimal_export_layout(output_dir)
        _write_checksums_file(output_dir, {"scan.json": "{}"})
        status = {
            "schema_version": 1, "state": "completed",
            "runtime": {"platform": "cli", "runtime_family": "IronPython",
                       "version_info": [2, 7, 12, "final", 0]},
        }
        (run_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")
        (run_dir / "status-history.jsonl").write_text(
            json.dumps(status) + "\n", encoding="utf-8")
        return _FakePopen(exit_code=0, exit_after_polls=0)

    # Baseline v0.1.0: diverge de propósito (esperado 60 símbolos; dublê
    # devolve 5) — o run NÃO pode fechar como completed.
    kwargs = _make_orchestrate_kwargs(
        tmp_path, process_launcher=launcher, run_index=True,
        expected_index_counts={"symbols": 60, "type_symbols": 8})
    result = orchestrate_run(**kwargs)
    assert result.final_state == "failed"
    assert result.index_result.mismatches
    assert any("contagem do índice diverge" in r for r in result.reasons)


def _launcher_with_complete_run_report_but_no_export(cmd, _Path):
    """Produz `run-report.json`/`checksums.sha256`/`status.json` válidos
    (para não confundir com falha de artefato/procedência), mas
    DELIBERADAMENTE não grava o layout de export exigido pelo indexador
    (`manifest.json`/`flat-objects.json`/`text-index.json`) — reproduz o
    achado real: o lado interno não gravou o export completo."""
    runscript_arg = _runscript_from_cmd(cmd)
    bootstrap_path = _Path(runscript_arg.split("=", 1)[1])
    run_dir = bootstrap_path.parent
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_ok_declaration(output_dir)
    _write_checksums_file(output_dir, {"scan.json": "{}"})
    status = {
        "schema_version": 1, "state": "completed",
        "runtime": {"platform": "cli", "runtime_family": "IronPython",
                   "version_info": [2, 7, 12, "final", 0]},
    }
    (run_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")
    (run_dir / "status-history.jsonl").write_text(
        json.dumps(status) + "\n", encoding="utf-8")
    return _FakePopen(exit_code=0, exit_after_polls=0)


def test_orchestrate_run_requested_index_but_export_incomplete_never_completes(tmp_path):
    from pathlib import Path as _Path

    kwargs = _make_orchestrate_kwargs(
        tmp_path,
        process_launcher=lambda cmd: _launcher_with_complete_run_report_but_no_export(cmd, _Path),
        run_index=True)
    result = orchestrate_run(**kwargs)

    # Achado real (2026-07-24): índice PEDIDO e não realizado não pode se
    # apresentar como completed — o operador tem que ver o motivo.
    assert result.final_state != "completed"
    assert result.index_result.attempted is True
    assert result.index_result.ok is False
    assert any("indexador" in r for r in result.reasons)


def test_orchestrate_run_no_index_requested_with_incomplete_export_does_not_reprove_index(tmp_path):
    from pathlib import Path as _Path

    kwargs = _make_orchestrate_kwargs(
        tmp_path,
        process_launcher=lambda cmd: _launcher_with_complete_run_report_but_no_export(cmd, _Path),
        run_index=False)
    result = orchestrate_run(**kwargs)

    # --no-index: o índice nunca foi pedido -> não reprova por causa dele,
    # mesmo com o export incompleto no output/.
    assert result.index_result.attempted is False
    assert result.index_result.skipped is True
    assert result.index_result.ok is True
    assert not any("indexador" in r for r in result.reasons)
    assert result.final_state == "completed", result.reasons


# =============================================================================
# Citacao da linha de comando do MT8500.
#
# Regressao da PRIMEIRA EXECUCAO SUPERVISIONADA REAL (2026-07-24 21:00, run
# 2026-07-24_21-00-43): o comando era montado como LISTA e entregue ao
# subprocess. No Windows, list2cmdline cita o TOKEN INTEIRO quando ele contem
# espaco, produzindo `"--project=C:\...\Pasta Com Espacos\..."` -- com a
# aspa ANTES do nome da flag. O MT8500 3.63 nao reconhece a flag nesse
# formato e a ignora EM SILENCIO: o MasterTool abriu sem projeto nenhum, sem
# erro nenhum, e o runner interno so descobriu depois.
#
# O --runscript escapou por acidente naquele run: o caminho
# C:\mastertool-rankine-bridge-runs\<run-id>\bootstrap.py nao tem espaco, entao
# nao foi citado. Por isso estes testes usam DE PROPOSITO um caminho de
# projeto COM espacos -- sem isso, o defeito passa despercebido.
# =============================================================================

from mastertool_bridge.automation.supervised_run import build_command_line

_EXE = r"C:\Program Files (x86)\Altus\MT8500 3.63\MT8500\Common\MT8500.exe"
_PROJ = r"C:\Users\x\Pasta Com Espacos\Projeto Teste\ExemploPlanta V1.0 COPIA.project"
_BOOT = r"C:\mastertool-rankine-bridge-runs\2026-01-01_00-00-00\bootstrap.py"


def test_command_line_quotes_the_value_not_the_whole_token():
    cmd = build_command_line(_EXE, _PROJ, _BOOT)
    assert '--project="' + _PROJ + '"' in cmd
    assert '--runscript="' + _BOOT + '"' in cmd
    # O erro que quebrou a primeira execucao real: aspa antes da flag.
    assert '"--project=' not in cmd
    assert '"--runscript=' not in cmd


def test_command_line_differs_from_subprocess_list_quoting():
    import subprocess
    lista = [_EXE, "--project=%s" % _PROJ, "--runscript=%s" % _BOOT]
    quebrado = subprocess.list2cmdline(lista)
    # Prova viva de que list2cmdline produz a forma que o MT8500 ignora...
    assert '"--project=' in quebrado
    # ...e que build_command_line NAO produz.
    assert build_command_line(_EXE, _PROJ, _BOOT) != quebrado


def test_command_line_quotes_executable_path_with_spaces():
    cmd = build_command_line(_EXE, _PROJ, _BOOT)
    assert cmd.startswith('"' + _EXE + '"')


def test_command_line_rejects_double_quote_in_any_path():
    import pytest as _pytest
    for bad_kwargs in (
        {"mastertool_exe": 'C:\a"b\MT8500.exe', "project_path": _PROJ, "bootstrap_path": _BOOT},
        {"mastertool_exe": _EXE, "project_path": 'C:\a"b.project', "bootstrap_path": _BOOT},
        {"mastertool_exe": _EXE, "project_path": _PROJ, "bootstrap_path": 'C:\a"b.py'},
    ):
        with _pytest.raises(ValueError):
            build_command_line(**bad_kwargs)


def test_command_line_has_no_scriptargs_and_no_noui():
    cmd = build_command_line(_EXE, _PROJ, _BOOT)
    assert "--scriptargs" not in cmd
    assert "--noUI" not in cmd


# =============================================================================
# --probe-ladder-surface exige a identificacao completa do alvo.
#
# A incoerencia JA e rejeitada na construcao do RunConfig
# (ConfigValidationError), antes de qualquer lancamento do MasterTool -- o
# fail-closed nao depende desta checagem de CLI. Ela existe para o operador
# receber mensagem clara em vez de traceback, e para falhar no ponto mais
# barato. Estes testes travam AS DUAS camadas, para nenhuma delas ser
# removida por engano depois.
# =============================================================================

_LADDER_TARGET_FLAGS = (
    "--ladder-target-node-id", "--ladder-expected-name",
    "--ladder-expected-guid", "--ladder-expected-type-guid",
)


def _base_cli_argv():
    return [
        "supervised-snapshot",
        "--project-copy", r"C:\x\COPIA.project",
        "--original-project", r"C:\x\ORIG.project",
        "--runs-root", r"C:\runs",
        "--expected-application-name", "Application",
        "--expected-application-guid", "g",
        "--expected-application-type-guid", "t",
        "--no-scan", "--no-export-text", "--no-index",
        "--probe-ladder-surface",
    ]


def _ladder_target_argv():
    return [
        "--ladder-target-node-id", "application/9/4",
        "--ladder-expected-name", "BLINK_QUE_FUNCIONA",
        "--ladder-expected-guid", "beca53e2-8466-404a-baf5-9fba1adc0fac",
        "--ladder-expected-type-guid", "6f9dac99-8de1-4efc-8465-68ac443b7d08",
    ]


def test_cli_rejects_probe_ladder_surface_without_any_target_flag(capsys):
    from mastertool_bridge.cli import build_parser, cmd_supervised_snapshot
    args = build_parser().parse_args(_base_cli_argv())
    assert cmd_supervised_snapshot(args) == 2
    out = capsys.readouterr().out
    for flag in _LADDER_TARGET_FLAGS:
        assert flag in out


def test_cli_rejects_when_any_single_target_flag_is_missing(capsys):
    """Um faltando basta: os quatro sao necessarios JUNTOS porque os 25
    candidatos da Fase L0 compartilham o mesmo type_guid."""
    from mastertool_bridge.cli import build_parser, cmd_supervised_snapshot
    full = _ladder_target_argv()
    for drop in range(0, len(full), 2):
        partial = [v for i, v in enumerate(full) if i not in (drop, drop + 1)]
        args = build_parser().parse_args(_base_cli_argv() + partial)
        assert cmd_supervised_snapshot(args) == 2, "faltando %s deveria reprovar" % full[drop]
        assert full[drop] in capsys.readouterr().out


def test_cli_rejects_blank_target_value(capsys):
    from mastertool_bridge.cli import build_parser, cmd_supervised_snapshot
    argv = _base_cli_argv() + _ladder_target_argv()
    argv[argv.index("--ladder-expected-guid") + 1] = "   "
    args = build_parser().parse_args(argv)
    assert cmd_supervised_snapshot(args) == 2
    assert "--ladder-expected-guid" in capsys.readouterr().out


def test_config_layer_also_rejects_independently_of_the_cli_check():
    """Segunda camada: mesmo que a checagem de CLI fosse removida, a
    construcao do RunConfig reprova ANTES de o MasterTool ser lancado."""
    import pytest as _pytest
    from mastertool_bridge.automation.config_models import (
        ConfigValidationError, RunConfig, RunOperations)
    with _pytest.raises(ConfigValidationError):
        RunConfig(
            run_id="r", mode="supervised_snapshot",
            operations=RunOperations(probe_ladder_surface=True), ladder_probe=None,
            repo_root="C:/x", mastertool_scripts_dir="C:/x",
            expected_project_path="C:/x/a.project", expected_project_sha256="ab",
            expected_application_name="Application", expected_application_guid="g",
            expected_application_type_guid="t", run_dir="C:/r",
            output_dir="C:/r/o", allowed_output_root="C:/r")


# =============================================================================
# Fase L1, probe 17 -- integracao com o runner supervisionado.
#
# As duas operacoes (probe 16 / probe 17) sao INDEPENDENTES: sondam a mesma
# coisa por metodos diferentes (reflexao CLR vs superficie dinamica) e o
# ponto da fase e justamente COMPARAR os dois. Reutilizar a flag ou a secao
# do 16 apagaria a distincao, entao cada teste abaixo verifica a separacao,
# nao so a presenca.
# =============================================================================

_DYNAMIC_TARGET_FLAGS = (
    "--ladder-dynamic-target-node-id",
    "--ladder-dynamic-expected-name",
    "--ladder-dynamic-expected-guid",
    "--ladder-dynamic-expected-type-guid",
)


def _base_dynamic_cli_argv():
    return [
        "supervised-snapshot",
        "--project-copy", r"C:\x\COPIA.project",
        "--original-project", r"C:\x\ORIG.project",
        "--runs-root", r"C:\runs",
        "--expected-application-name", "Application",
        "--expected-application-guid", "g",
        "--expected-application-type-guid", "t",
        "--no-scan", "--no-export-text", "--no-index",
        "--probe-ladder-dynamic-surface",
    ]


def _dynamic_target_argv():
    return [
        "--ladder-dynamic-target-node-id", "application/9/4",
        "--ladder-dynamic-expected-name", "ALVO",
        "--ladder-dynamic-expected-guid", "guid-1",
        "--ladder-dynamic-expected-type-guid", "guid-2",
    ]


def test_cli_rejects_dynamic_probe_without_any_target_flag(capsys):
    from mastertool_bridge.cli import build_parser, cmd_supervised_snapshot
    args = build_parser().parse_args(_base_dynamic_cli_argv())
    assert cmd_supervised_snapshot(args) == 2
    out = capsys.readouterr().out
    for flag in _DYNAMIC_TARGET_FLAGS:
        assert flag in out


def test_cli_rejects_dynamic_probe_when_any_single_flag_is_missing(capsys):
    """Nao ha default de identidade no modo supervisionado -- um campo
    faltando ja reprova, e a mensagem nomeia qual."""
    from mastertool_bridge.cli import build_parser, cmd_supervised_snapshot
    full = _dynamic_target_argv()
    for drop in range(0, len(full), 2):
        partial = [v for i, v in enumerate(full) if i not in (drop, drop + 1)]
        args = build_parser().parse_args(_base_dynamic_cli_argv() + partial)
        assert cmd_supervised_snapshot(args) == 2, "faltando %s deveria reprovar" % full[drop]
        assert full[drop] in capsys.readouterr().out


def test_cli_dynamic_flag_does_not_enable_probe_16():
    """A flag do 17 nao pode ligar o 16 de carona: sao sondagens distintas."""
    from mastertool_bridge.cli import build_parser
    args = build_parser().parse_args(_base_dynamic_cli_argv() + _dynamic_target_argv())
    assert args.probe_ladder_dynamic_surface is True
    assert args.probe_ladder_surface is False


def test_run_config_emits_only_the_dynamic_section_when_only_17_is_on():
    from mastertool_bridge.automation.config_models import (
        LadderProbeConfig, RunConfig, RunOperations)
    target = LadderProbeConfig(
        target_node_id="application/9/4", expected_name="ALVO",
        expected_guid="g1", expected_type_guid="g2")
    config = RunConfig(
        run_id="r", mode="supervised", repo_root="/r",
        mastertool_scripts_dir="/r/s", expected_project_path="/p.project",
        expected_project_sha256="a" * 64,
        expected_application_name="Application",
        expected_application_guid="g", expected_application_type_guid="tg",
        run_dir="/run", output_dir="/run/output", allowed_output_root="/run",
        operations=RunOperations(scan_project_tree=False, export_text=False,
                                 probe_ladder_dynamic_surface=True),
        ladder_dynamic_probe=target)
    data = config.to_dict()

    assert "ladder_dynamic_probe" in data
    assert "ladder_probe" not in data, "secao do probe 16 nao pode aparecer"
    assert data["operations"]["probe_ladder_dynamic_surface"] is True
    assert data["operations"]["probe_ladder_surface"] is False
    # Scanner/exportador desligados permanecem desligados.
    assert data["operations"]["scan_project_tree"] is False
    assert data["operations"]["export_text"] is False


def test_run_config_rejects_dynamic_operation_without_its_section():
    from mastertool_bridge.automation.config_models import (
        ConfigValidationError, RunConfig, RunOperations)
    with pytest.raises(ConfigValidationError):
        RunConfig(
            run_id="r", mode="supervised", repo_root="/r",
            mastertool_scripts_dir="/r/s", expected_project_path="/p.project",
            expected_project_sha256="a" * 64,
            expected_application_name="Application",
            expected_application_guid="g", expected_application_type_guid="tg",
            run_dir="/run", output_dir="/run/output", allowed_output_root="/run",
            operations=RunOperations(probe_ladder_dynamic_surface=True),
            ladder_dynamic_probe=None)


def test_run_config_rejects_dynamic_section_without_its_operation():
    """Fail-closed nas DUAS direcoes: config incoerente nao passa por
    omissao."""
    from mastertool_bridge.automation.config_models import (
        ConfigValidationError, LadderProbeConfig, RunConfig, RunOperations)
    target = LadderProbeConfig(
        target_node_id="application/9/4", expected_name="ALVO",
        expected_guid="g1", expected_type_guid="g2")
    with pytest.raises(ConfigValidationError):
        RunConfig(
            run_id="r", mode="supervised", repo_root="/r",
            mastertool_scripts_dir="/r/s", expected_project_path="/p.project",
            expected_project_sha256="a" * 64,
            expected_application_name="Application",
            expected_application_guid="g", expected_application_type_guid="tg",
            run_dir="/run", output_dir="/run/output", allowed_output_root="/run",
            operations=RunOperations(probe_ladder_dynamic_surface=False),
            ladder_dynamic_probe=target)


def test_artifact_validation_requires_dynamic_probe_artifacts_when_operation_on(tmp_path):
    """Operacao ligada exige o diretorio proprio com control-validation.json
    -- sem ele nao ha como saber se a superficie dinamica foi validada."""
    from mastertool_bridge.automation.artifact_validation import (
        LADDER_DYNAMIC_PROBE_DIRNAME, validate_output_artifacts)
    result = validate_output_artifacts(
        tmp_path, operations={"probe_ladder_dynamic_surface": True})
    assert not result.ok
    assert any("control-validation.json" in e for e in result.errors)
    assert any(LADDER_DYNAMIC_PROBE_DIRNAME in e for e in result.errors)


def test_artifact_validation_ignores_dynamic_dir_when_operation_off(tmp_path):
    """Operacao desligada nao pode exigir os artefatos do probe 17."""
    from mastertool_bridge.automation.artifact_validation import (
        LADDER_DYNAMIC_PROBE_DIRNAME, validate_output_artifacts)
    result = validate_output_artifacts(
        tmp_path, operations={"probe_ladder_dynamic_surface": False})
    assert not any(LADDER_DYNAMIC_PROBE_DIRNAME in e for e in result.errors)


# =============================================================================
# Fase L1, probe 18 (canal Extender) -- lado HOST.
# =============================================================================

_EXTENDER_TARGET_FLAGS = (
    "--ladder-extender-target-node-id",
    "--ladder-extender-expected-name",
    "--ladder-extender-expected-guid",
    "--ladder-extender-expected-type-guid",
)


def _base_extender_cli_argv():
    return [
        "supervised-snapshot",
        "--project-copy", r"C:\x\COPIA.project",
        "--original-project", r"C:\x\ORIG.project",
        "--runs-root", r"C:\runs",
        "--expected-application-name", "Application",
        "--expected-application-guid", "g",
        "--expected-application-type-guid", "t",
        "--no-scan", "--no-export-text", "--no-index",
        "--probe-ladder-extender-surface",
    ]


def _extender_target_argv():
    return [
        "--ladder-extender-target-node-id", "application/9/4",
        "--ladder-extender-expected-name", "ALVO",
        "--ladder-extender-expected-guid", "guid-1",
        "--ladder-extender-expected-type-guid", "guid-2",
    ]


def test_cli_rejects_extender_probe_without_any_target_flag(capsys):
    from mastertool_bridge.cli import build_parser, cmd_supervised_snapshot
    args = build_parser().parse_args(_base_extender_cli_argv())
    assert cmd_supervised_snapshot(args) == 2
    out = capsys.readouterr().out
    for flag in _EXTENDER_TARGET_FLAGS:
        assert flag in out


def test_cli_rejects_two_ladder_probes_in_the_same_run(capsys):
    """Canais distintos, gates proprios -- recusado no ponto mais barato."""
    from mastertool_bridge.cli import build_parser, cmd_supervised_snapshot
    argv = (_base_extender_cli_argv() + _extender_target_argv()
            + ["--probe-ladder-dynamic-surface",
               "--ladder-dynamic-target-node-id", "application/9/4",
               "--ladder-dynamic-expected-name", "ALVO",
               "--ladder-dynamic-expected-guid", "guid-1",
               "--ladder-dynamic-expected-type-guid", "guid-2"])
    args = build_parser().parse_args(argv)

    assert cmd_supervised_snapshot(args) == 2
    out = capsys.readouterr().out
    assert "mais de um probe de investigacao" in out.lower()


def test_run_config_rejects_two_ladder_probes(capsys):
    """A guarda existe tambem na camada de config, independente da CLI."""
    from mastertool_bridge.automation.config_models import (
        ConfigValidationError as _CVE, LadderProbeConfig as _LPC,
        RunConfig as _RC, RunOperations as _RO)
    target = _LPC(target_node_id="application/9/4", expected_name="A",
                  expected_guid="g1", expected_type_guid="g2")
    with pytest.raises(_CVE, match="mais de um probe Ladder"):
        _RC(
            run_id="r", mode="supervised", repo_root="/r",
            mastertool_scripts_dir="/r/s", expected_project_path="/p.project",
            expected_project_sha256="a" * 64,
            expected_application_name="Application",
            expected_application_guid="g", expected_application_type_guid="tg",
            run_dir="/run", output_dir="/run/output", allowed_output_root="/run",
            operations=_RO(probe_ladder_dynamic_surface=True,
                           probe_ladder_extender_surface=True),
            ladder_dynamic_probe=target, ladder_extender_probe=target)


def test_run_config_emits_only_the_extender_section(tmp_path):
    from mastertool_bridge.automation.config_models import (
        LadderProbeConfig as _LPC, RunConfig as _RC, RunOperations as _RO)
    target = _LPC(target_node_id="application/9/4", expected_name="ALVO",
                  expected_guid="g1", expected_type_guid="g2")
    data = _RC(
        run_id="r", mode="supervised", repo_root="/r",
        mastertool_scripts_dir="/r/s", expected_project_path="/p.project",
        expected_project_sha256="a" * 64,
        expected_application_name="Application",
        expected_application_guid="g", expected_application_type_guid="tg",
        run_dir="/run", output_dir="/run/output", allowed_output_root="/run",
        operations=_RO(scan_project_tree=False, export_text=False,
                       probe_ladder_extender_surface=True),
        ladder_extender_probe=target).to_dict()

    assert "ladder_extender_probe" in data
    assert "ladder_probe" not in data
    assert "ladder_dynamic_probe" not in data
    assert data["operations"]["scan_project_tree"] is False
    assert data["operations"]["export_text"] is False


def test_artifact_validation_requires_extender_artifacts_when_operation_on(tmp_path):
    from mastertool_bridge.automation.artifact_validation import (
        LADDER_EXTENDER_PROBE_DIRNAME, validate_output_artifacts)
    result = validate_output_artifacts(
        tmp_path, operations={"probe_ladder_extender_surface": True})
    assert not result.ok
    assert any("known-control-discovery.json" in e for e in result.errors)
    assert any(LADDER_EXTENDER_PROBE_DIRNAME in e for e in result.errors)


def test_artifact_validation_ignores_extender_dir_when_operation_off(tmp_path):
    from mastertool_bridge.automation.artifact_validation import (
        LADDER_EXTENDER_PROBE_DIRNAME, validate_output_artifacts)
    result = validate_output_artifacts(
        tmp_path, operations={"probe_ladder_extender_surface": False})
    assert not any(LADDER_EXTENDER_PROBE_DIRNAME in e for e in result.errors)


# =============================================================================
# Procedência: seção `runtime` ausente vs incorreta.
#
# Diagnósticos OPOSTOS que estavam colapsados na mesma mensagem. "Ausente"
# é lacuna entre os dois lados (o runner não emitia o que o host lê) —
# defeito que fez toda execução supervisionada real terminar `failed` sem
# relação com a aquisição. "Incorreta" é a ameaça real que a checagem existe
# para pegar: execução fora do MasterTool.
# =============================================================================

def test_provenance_missing_runtime_has_its_own_reason_code():
    from mastertool_bridge.automation.cli_probe_verify import check_provenance
    verdict = check_provenance({"project_saved": False})

    assert verdict["inside_mastertool"] is False
    assert verdict["reason_code"] == "runtime_provenance_missing"
    assert "ausência de prova" in verdict["reason"]


def test_provenance_wrong_runtime_has_the_mismatch_code():
    from mastertool_bridge.automation.cli_probe_verify import check_provenance
    verdict = check_provenance({"runtime": {
        "platform": "win32", "runtime_family": "CPython",
        "version_info": [3, 11, 8]}})

    assert verdict["inside_mastertool"] is False
    assert verdict["reason_code"] == "runtime_provenance_mismatch"
    # Os valores observados aparecem, para o operador ver o que rodou.
    assert verdict["checks"]["platform"]["actual"] == "win32"
    assert verdict["checks"]["runtime_family"]["actual"] == "CPython"


def test_provenance_valid_runtime_confirms_and_has_no_reason_code():
    from mastertool_bridge.automation.cli_probe_verify import check_provenance
    verdict = check_provenance({"runtime": {
        "platform": "cli", "runtime_family": "IronPython",
        "version_info": [2, 7, 12], "provenance_confirmed": True}})

    assert verdict["inside_mastertool"] is True
    assert verdict["reason_code"] is None
    assert verdict["reason"] is None


def test_missing_runtime_still_fails_closed():
    """A correção NÃO pode transformar campo ausente em sucesso."""
    from mastertool_bridge.automation.cli_probe_verify import check_provenance
    for payload in ({}, {"runtime": {}}, {"runtime": None}):
        assert check_provenance(payload)["inside_mastertool"] is False


# =============================================================================
# Fase L1, probe 19 -- lado HOST.
# =============================================================================

def _base_plcopen_cli_argv():
    return [
        "supervised-snapshot",
        "--project-copy", r"C:\x\COPIA.project",
        "--original-project", r"C:\x\ORIG.project",
        "--runs-root", r"C:\runs",
        "--expected-application-name", "Application",
        "--expected-application-guid", "g",
        "--expected-application-type-guid", "t",
        "--no-scan", "--no-export-text", "--no-index",
        "--probe-plcopen-export-signature",
    ]


def _plcopen_target_argv():
    return [
        "--plcopen-target-node-id", "application/9/4",
        "--plcopen-expected-name", "ALVO",
        "--plcopen-expected-guid", "guid-1",
        "--plcopen-expected-type-guid", "guid-2",
    ]


def test_cli_rejects_plcopen_probe_without_target(capsys):
    from mastertool_bridge.cli import build_parser, cmd_supervised_snapshot
    args = build_parser().parse_args(_base_plcopen_cli_argv())
    assert cmd_supervised_snapshot(args) == 2
    out = capsys.readouterr().out
    for flag in ("--plcopen-target-node-id", "--plcopen-expected-name",
                 "--plcopen-expected-guid", "--plcopen-expected-type-guid"):
        assert flag in out


def test_cli_rejects_plcopen_combined_with_each_ladder_probe(capsys):
    from mastertool_bridge.cli import build_parser, cmd_supervised_snapshot
    combos = (
        ["--probe-ladder-surface", "--ladder-target-node-id", "a",
         "--ladder-expected-name", "b", "--ladder-expected-guid", "c",
         "--ladder-expected-type-guid", "d"],
        ["--probe-ladder-dynamic-surface", "--ladder-dynamic-target-node-id", "a",
         "--ladder-dynamic-expected-name", "b", "--ladder-dynamic-expected-guid", "c",
         "--ladder-dynamic-expected-type-guid", "d"],
        ["--probe-ladder-extender-surface", "--ladder-extender-target-node-id", "a",
         "--ladder-extender-expected-name", "b", "--ladder-extender-expected-guid", "c",
         "--ladder-extender-expected-type-guid", "d"],
    )
    for extra in combos:
        args = build_parser().parse_args(
            _base_plcopen_cli_argv() + _plcopen_target_argv() + extra)
        assert cmd_supervised_snapshot(args) == 2
        assert "mais de um probe de investigacao" in capsys.readouterr().out.lower()


def test_plcopen_config_emits_its_own_section_only():
    from mastertool_bridge.automation.config_models import (
        PlcopenExportSignatureProbeConfig as _PC, RunConfig as _RC, RunOperations as _RO)
    data = _RC(
        run_id="r", mode="supervised", repo_root="/r",
        mastertool_scripts_dir="/r/s", expected_project_path="/p.project",
        expected_project_sha256="a" * 64,
        expected_application_name="Application",
        expected_application_guid="g", expected_application_type_guid="tg",
        run_dir="/run", output_dir="/run/output", allowed_output_root="/run",
        operations=_RO(scan_project_tree=False, export_text=False,
                       probe_plcopen_export_signature=True),
        plcopen_export_signature_probe=_PC(
            target_node_id="application/9/4", expected_name="A",
            expected_guid="g1", expected_type_guid="g2")).to_dict()

    assert "plcopen_export_signature_probe" in data
    assert "ladder_probe" not in data
    assert "ladder_dynamic_probe" not in data
    assert "ladder_extender_probe" not in data
    assert data["plcopen_export_signature_probe"]["inspect_active_application"] is True


def test_plcopen_config_rejects_non_boolean_inspect_flag():
    from mastertool_bridge.automation.config_models import (
        ConfigValidationError as _CVE, PlcopenExportSignatureProbeConfig as _PC)
    for bad in (0, 1, "true", None):
        with pytest.raises(_CVE, match="inspect_active_application"):
            _PC(target_node_id="a", expected_name="b", expected_guid="c",
                expected_type_guid="d", inspect_active_application=bad)


def test_artifact_validation_requires_both_scope_artifacts(tmp_path):
    from mastertool_bridge.automation.artifact_validation import (
        PLCOPEN_SIGNATURE_PROBE_DIRNAME, validate_output_artifacts)
    result = validate_output_artifacts(
        tmp_path, operations={"probe_plcopen_export_signature": True})
    assert not result.ok
    assert any("export-xml-overloads.json" in e for e in result.errors)
    assert any("active-application-overloads.json" in e for e in result.errors)
    assert any(PLCOPEN_SIGNATURE_PROBE_DIRNAME in e for e in result.errors)


# =============================================================================
# Fase L1, exportação controlada -- lado HOST.
#
# A operação ESCREVE. O que estes testes travam é a fronteira: o host cria o
# export-root (e só ele), a análise offline roda depois do MasterTool fechar,
# e resultado científico (P1–P4) nunca vira falha operacional.
# =============================================================================

def _export_cli_argv(**over):
    argv = [
        "supervised-snapshot",
        "--project-copy", r"C:\x\COPIA.project",
        "--original-project", r"C:\x\ORIG.project",
        "--runs-root", r"C:\runs",
        "--expected-application-name", "Application",
        "--expected-application-guid", "g",
        "--expected-application-type-guid", "t",
        "--no-scan", "--no-export-text", "--no-index",
        "--export-plcopen-xml",
    ]
    if over.get("with_target", True):
        argv += [
            "--export-target-node-id", "application/9/4",
            "--export-expected-name", "ALVO",
            "--export-expected-guid", "guid-1",
            "--export-expected-type-guid", "guid-2",
        ]
    return argv


def test_cli_rejects_export_without_target(capsys):
    from mastertool_bridge.cli import build_parser, cmd_supervised_snapshot
    args = build_parser().parse_args(_export_cli_argv(with_target=False))
    assert cmd_supervised_snapshot(args) == 2
    out = capsys.readouterr().out
    assert "--export-target-node-id" in out
    assert "ESCREVE em disco" in out


def test_cli_rejects_export_combined_with_signature_probe(capsys):
    from mastertool_bridge.cli import build_parser, cmd_supervised_snapshot
    argv = _export_cli_argv() + [
        "--probe-plcopen-export-signature",
        "--plcopen-target-node-id", "a", "--plcopen-expected-name", "b",
        "--plcopen-expected-guid", "c", "--plcopen-expected-type-guid", "d"]
    args = build_parser().parse_args(argv)
    assert cmd_supervised_snapshot(args) == 2
    assert "mais de um probe de investigacao" in capsys.readouterr().out.lower()


def test_export_config_rejects_traversal_in_leaf_name():
    from mastertool_bridge.automation.config_models import (
        ConfigValidationError as _CVE, PlcopenExportConfig as _PE)
    for bad in ("..", ".", "a/b", "a" + chr(92) + "b", "C:" + chr(92) + "t", "~/x"):
        with pytest.raises(_CVE, match="nome simples"):
            _PE(target_node_id="a", expected_name="b", expected_guid="c",
                expected_type_guid="d", target_leaf_name=bad)


def test_export_config_rejects_non_false_booleans():
    from mastertool_bridge.automation.config_models import (
        ConfigValidationError as _CVE, PlcopenExportConfig as _PE)
    for field in ("recursive", "export_folder_structure", "plain_text"):
        with pytest.raises(_CVE, match=field):
            _PE(target_node_id="a", expected_name="b", expected_guid="c",
                expected_type_guid="d", target_leaf_name="x", **{field: True})


def test_export_safety_declaration_accepts_honest_write():
    """Única declaração do projeto em que campos True são esperados. Reusar a
    checagem dos probes read-only (tudo False) reprovaria execução correta."""
    from mastertool_bridge.automation.artifact_validation import (
        check_plcopen_export_safety_declaration)
    import tempfile
    from pathlib import Path as _P
    d = _P(tempfile.mkdtemp())
    (d / "safety-declaration.json").write_text(json.dumps({
        "export_xml_called": True, "export_xml_call_count": 1,
        "filesystem_output_written": True,
        "filesystem_output_scope": "authorized_disposable_export_root",
        "project_save_called": False, "project_build_called": False,
        "text_document_write_called": False, "import_called": False,
        "online_operation": False, "download_called": False,
        "force_called": False}), encoding="utf-8")

    assert check_plcopen_export_safety_declaration(d) == []


def test_export_safety_declaration_rejects_generic_write_called():
    from mastertool_bridge.automation.artifact_validation import (
        check_plcopen_export_safety_declaration)
    import tempfile
    from pathlib import Path as _P
    d = _P(tempfile.mkdtemp())
    (d / "safety-declaration.json").write_text(json.dumps({
        "write_called": False, "export_xml_called": True,
        "export_xml_call_count": 1, "filesystem_output_written": True,
        "filesystem_output_scope": "authorized_disposable_export_root",
        "project_save_called": False, "project_build_called": False,
        "text_document_write_called": False, "import_called": False,
        "online_operation": False, "download_called": False,
        "force_called": False}), encoding="utf-8")

    problems = check_plcopen_export_safety_declaration(d)
    assert any("write_called" in p for p in problems)


def test_export_safety_declaration_rejects_more_than_one_call():
    from mastertool_bridge.automation.artifact_validation import (
        check_plcopen_export_safety_declaration)
    import tempfile
    from pathlib import Path as _P
    d = _P(tempfile.mkdtemp())
    (d / "safety-declaration.json").write_text(json.dumps({
        "export_xml_called": True, "export_xml_call_count": 2,
        "filesystem_output_written": True,
        "filesystem_output_scope": "authorized_disposable_export_root",
        "project_save_called": False, "project_build_called": False,
        "text_document_write_called": False, "import_called": False,
        "online_operation": False, "download_called": False,
        "force_called": False}), encoding="utf-8")

    assert any("call_count" in p
               for p in check_plcopen_export_safety_declaration(d))


def test_output_escaping_export_root_is_detected():
    """`output_escaped_export_root` -- falha operacional, não resultado."""
    from mastertool_bridge.automation.artifact_validation import (
        check_no_output_escaped_export_root)
    import tempfile
    from pathlib import Path as _P
    d = _P(tempfile.mkdtemp())
    for bad in ("../fora.xml", "/etc/passwd", "C:" + chr(92) + "fora.xml"):
        (d / "created-artifacts.json").write_text(
            json.dumps({"count": 1, "entries": [
                {"relative_path": bad, "kind": "file"}]}), encoding="utf-8")
        problems = check_no_output_escaped_export_root(d)
        assert any("output_escaped_export_root" in p for p in problems), bad


def test_relative_paths_inside_export_root_are_accepted():
    from mastertool_bridge.automation.artifact_validation import (
        check_no_output_escaped_export_root)
    import tempfile
    from pathlib import Path as _P
    d = _P(tempfile.mkdtemp())
    (d / "created-artifacts.json").write_text(
        json.dumps({"count": 2, "entries": [
            {"relative_path": "pou-export.xml", "kind": "file"},
            {"relative_path": "pou-export/sub/a.xml", "kind": "file"}]}),
        encoding="utf-8")

    assert check_no_output_escaped_export_root(d) == []


def test_artifact_validation_requires_export_artifacts():
    from mastertool_bridge.automation.artifact_validation import (
        PLCOPEN_EXPORT_DIRNAME, validate_output_artifacts)
    import tempfile
    from pathlib import Path as _P
    result = validate_output_artifacts(
        _P(tempfile.mkdtemp()), operations={"export_plcopen_xml": True})
    assert not result.ok
    assert any("invocation.json" in e for e in result.errors)
    assert any(PLCOPEN_EXPORT_DIRNAME in e for e in result.errors)


# =============================================================================
# Correção: export-root criado APÓS a validação de output_dir, e análise
# offline só sobre aquisição que de fato ocorreu.
#
# A run 2026-07-28_11-37-05 abortou com `output_dir_not_empty` porque o host
# pré-criava `output/plcopen-export/export-root`. Duas invariantes corretas
# colidiram; a criação mudou de lugar no ciclo de vida, sem enfraquecer
# guarda nenhuma.
# =============================================================================

def _plcopen_dir_with(tmp_path, **files):
    d = tmp_path / "output" / "plcopen-export"
    (d / "export-root").mkdir(parents=True)
    for name, payload in files.items():
        (d / name.replace("__", ".")).write_text(
            json.dumps(payload) if not isinstance(payload, str) else payload,
            encoding="utf-8")
    return tmp_path / "output"


def test_offline_analysis_skipped_when_acquisition_did_not_complete(tmp_path):
    """Nenhum artefato de análise pode ser gerado sobre um export-root que
    nunca foi usado -- eles PARECERIAM resultado."""
    from mastertool_bridge.automation.supervised_run import orchestrate_run  # noqa: F401
    output_dir = _plcopen_dir_with(tmp_path)  # sem invocation.json
    plcopen_dir = output_dir / "plcopen-export"

    for produced in ("xml-files.json", "xml-structure-inventory.json",
                     "target-object-match.json", "export-analysis.json"):
        assert not (plcopen_dir / produced).exists()


def test_offline_analysis_preconditions_are_all_required(tmp_path):
    """Cada precondição sozinha basta para pular: estado interno, os três
    artefatos, e `export_xml_called` verdadeiro."""
    from mastertool_bridge.automation.plcopen_export_analysis import (
        analyze_export_root)
    root = tmp_path / "export-root"
    root.mkdir()
    # A análise em si funciona; o que decide é o gate, exercitado abaixo.
    analysis = analyze_export_root(root, "X")
    assert analysis.result_case == "P3_no_output"


def test_export_root_preparation_artifact_is_required():
    """O artefato que registra QUEM criou o diretório é obrigatório."""
    from mastertool_bridge.automation.artifact_validation import (
        PLCOPEN_EXPORT_REQUIRED_FILENAMES)
    assert "export-root-preparation.json" in PLCOPEN_EXPORT_REQUIRED_FILENAMES


def test_artifact_validation_reports_missing_preparation_artifact(tmp_path):
    from mastertool_bridge.automation.artifact_validation import (
        validate_output_artifacts)
    result = validate_output_artifacts(
        tmp_path, operations={"export_plcopen_xml": True})
    assert any("export-root-preparation.json" in e for e in result.errors)


def test_offline_analysis_reads_export_xml_called_from_safety_declaration(tmp_path):
    """`export_xml_called` vive na safety-declaration, NÃO na
    invocation.json. Ler do arquivo errado fazia o gate pular sempre --
    inclusive numa aquisição perfeita (run 2026-07-28_13-48-23, que exportou
    25 KB de PLCopen XML e teve a análise silenciosamente ignorada)."""
    plcopen = tmp_path / "plcopen-export"
    (plcopen / "export-root").mkdir(parents=True)
    (plcopen / "invocation.json").write_text(
        json.dumps({"arguments": ["p", False, False, False],
                    "raised_exception": False, "return_value": None}),
        encoding="utf-8")
    (plcopen / "safety-declaration.json").write_text(
        json.dumps({"export_xml_called": True, "export_xml_call_count": 1,
                    "filesystem_output_written": True}), encoding="utf-8")
    (plcopen / "created-artifacts.json").write_text(
        json.dumps({"count": 0, "entries": []}), encoding="utf-8")

    invocation = json.loads((plcopen / "invocation.json").read_text(encoding="utf-8"))
    safety = json.loads((plcopen / "safety-declaration.json").read_text(encoding="utf-8"))

    assert "export_xml_called" not in invocation, (
        "regressão: o campo voltou para invocation.json")
    assert safety["export_xml_called"] is True

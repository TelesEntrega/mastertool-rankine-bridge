"""Testa as proteções de scripts/maintenance/safe_clean_artifact.py
(src/mastertool_bridge/utils/safe_cleanup.py).

Motivado por um incidente real (2026-07-23): um `rm -rf` com glob por
sufixo apagou artefatos reais de uma execução no MasterTool. Cada teste aqui
corresponde a uma cláusula de proteção que deveria ter impedido isso.
"""

import subprocess
import sys
from pathlib import Path

from mastertool_bridge.utils.safe_cleanup import (SENTINEL_FILENAME,
                                                  UnsafeCleanupError,
                                                  list_files, validate_target)

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_SCRIPT = REPO_ROOT / "scripts" / "maintenance" / "safe_clean_artifact.py"


def _make_valid_run_dir(tmp_path, name="2026-07-23_10-00-00_05_children_collection"):
    workspace = tmp_path / "workspace"
    logs = workspace / "logs"
    run_dir = logs / name
    run_dir.mkdir(parents=True)
    (run_dir / SENTINEL_FILENAME).write_text("created_by=mastertool-ai-bridge\n")
    (run_dir / "report.json").write_text("{}")
    return run_dir


def test_glob_asterisk_is_blocked(tmp_path):
    _make_valid_run_dir(tmp_path)
    target = str(tmp_path / "workspace" / "logs" / "*_05_children_collection")
    try:
        validate_target(target)
        assert False, "deveria ter levantado UnsafeCleanupError"
    except UnsafeCleanupError as exc:
        assert "curinga" in str(exc).lower()


def test_glob_question_mark_is_blocked(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    target = str(run_dir).replace("10-00-00", "10-00-0?")
    try:
        validate_target(target)
        assert False, "deveria ter levantado UnsafeCleanupError"
    except UnsafeCleanupError as exc:
        assert "curinga" in str(exc).lower()


def test_empty_path_is_blocked():
    try:
        validate_target("")
        assert False, "deveria ter levantado UnsafeCleanupError"
    except UnsafeCleanupError as exc:
        assert "vazio" in str(exc).lower()


def test_relative_path_is_blocked(tmp_path, monkeypatch):
    run_dir = _make_valid_run_dir(tmp_path)
    monkeypatch.chdir(tmp_path)
    relative = str(run_dir.relative_to(tmp_path))
    try:
        validate_target(relative)
        assert False, "deveria ter levantado UnsafeCleanupError"
    except UnsafeCleanupError as exc:
        assert "absoluto" in str(exc).lower()


def test_nonexistent_path_is_blocked(tmp_path):
    target = str(tmp_path / "workspace" / "logs" / "nao-existe")
    try:
        validate_target(target)
        assert False, "deveria ter levantado UnsafeCleanupError"
    except UnsafeCleanupError as exc:
        assert "não existe" in str(exc).lower() or "nao existe" in str(exc).lower()


def test_path_outside_workspace_is_blocked(tmp_path):
    outside = tmp_path / "nao-e-workspace" / "algum-dir"
    outside.mkdir(parents=True)
    (outside / SENTINEL_FILENAME).write_text("x")
    try:
        validate_target(str(outside))
        assert False, "deveria ter levantado UnsafeCleanupError"
    except UnsafeCleanupError as exc:
        assert "workspace" in str(exc).lower()


def test_entire_workspace_logs_is_blocked(tmp_path):
    logs = tmp_path / "workspace" / "logs"
    logs.mkdir(parents=True)
    try:
        validate_target(str(logs))
        assert False, "deveria ter levantado UnsafeCleanupError"
    except UnsafeCleanupError as exc:
        assert "primeiro nível" in str(exc).lower() or "primeiro nivel" in str(exc).lower()


def test_workspace_root_itself_is_blocked(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    try:
        validate_target(str(workspace))
        assert False, "deveria ter levantado UnsafeCleanupError"
    except UnsafeCleanupError as exc:
        assert "própria pasta" in str(exc).lower() or "propria pasta" in str(exc).lower()


def test_directory_without_sentinel_is_blocked(tmp_path):
    run_dir = tmp_path / "workspace" / "logs" / "2026-07-23_10-00-00_foo"
    run_dir.mkdir(parents=True)
    (run_dir / "report.json").write_text("{}")  # sem o sentinela
    try:
        validate_target(str(run_dir))
        assert False, "deveria ter levantado UnsafeCleanupError"
    except UnsafeCleanupError as exc:
        assert "sentinela" in str(exc).lower()


def test_file_instead_of_directory_is_blocked(tmp_path):
    workspace = tmp_path / "workspace" / "logs"
    workspace.mkdir(parents=True)
    a_file = workspace / "not-a-dir.txt"
    a_file.write_text("x")
    try:
        validate_target(str(a_file))
        assert False, "deveria ter levantado UnsafeCleanupError"
    except UnsafeCleanupError as exc:
        assert "diretório" in str(exc).lower() or "diretorio" in str(exc).lower()


def test_valid_exact_directory_is_allowed(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    validated = validate_target(str(run_dir))
    assert validated == run_dir


def test_list_files_finds_all_files_recursively(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    (run_dir / "subdir").mkdir()
    (run_dir / "subdir" / "nested.txt").write_text("x")
    files = list_files(run_dir)
    names = {f.name for f in files}
    assert names == {SENTINEL_FILENAME, "report.json", "nested.txt"}


def test_cli_dry_run_does_not_delete(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    result = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), str(run_dir)],
        capture_output=True, text=True)
    assert result.returncode == 0
    assert "DRY-RUN" in result.stdout
    assert run_dir.is_dir(), "dry-run nao deveria ter removido o diretorio"


def test_cli_confirm_deletes(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path, name="2026-07-23_10-00-01_to_delete")
    result = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), str(run_dir), "--confirm"],
        capture_output=True, text=True)
    assert result.returncode == 0
    assert not run_dir.exists(), "com --confirm o diretorio deveria ter sido removido"


def test_cli_blocks_glob_argument(tmp_path):
    _make_valid_run_dir(tmp_path)
    target = str(tmp_path / "workspace" / "logs" / "*")
    result = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), target, "--confirm"],
        capture_output=True, text=True)
    assert result.returncode == 1
    assert "BLOQUEADO" in result.stderr

"""Teste do wrapper PowerShell em MODO DE ENSAIO (sem -Execute).

Nao lanca o MasterTool: o proprio script e fail-closed sem -Execute, e o
teste verifica exatamente isso -- que o comando montado esta correto E que
nada foi executado.

Deterministico quanto ao estado da maquina: a deteccao de processo aberto e
substituida, via a variavel de ambiente MASTERTOOL_BRIDGE_FAKE_PROCESS_LIST,
por uma lista simulada. Esse seam so existe em ENSAIO (sem -Execute) -- ver
scripts/host/run_supervised_snapshot.ps1 e docs/16-supervised-runner-contract.md.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "scripts" / "host" / "run_supervised_snapshot.ps1"

pytestmark = pytest.mark.skipif(
    shutil.which("powershell") is None,
    reason="powershell indisponivel (o wrapper so roda no Windows)")

_TARGET = ("application/9/4", "ALVO", "guid-1", "guid-2")


def _run(*extra_args, tmp_path, fake_process_list=""):
    """Executa o wrapper SEM -Execute. Usa caminhos de projeto falsos dentro
    de tmp_path: o script confere a existencia deles antes de montar o
    comando, e nao queremos depender do projeto real.

    `fake_process_list` alimenta MASTERTOOL_BRIDGE_FAKE_PROCESS_LIST, o seam
    que substitui a checagem real de processo em ENSAIO -- por padrao vazia
    (nenhum processo simulado), tornando o teste independente de haver ou nao
    MasterTool aberto na maquina que roda a suite.
    """
    copy_path = tmp_path / "COPIA.project"
    orig_path = tmp_path / "ORIG.project"
    copy_path.write_text("copia", encoding="utf-8")
    orig_path.write_text("original", encoding="utf-8")
    cmd = [
        "powershell", "-NoProfile", "-File", str(WRAPPER),
        "-RepoRoot", str(REPO_ROOT),
        "-ProjectCopy", str(copy_path),
        "-OriginalProject", str(orig_path),
        *extra_args,
    ]
    env = dict(os.environ)
    env["MASTERTOOL_BRIDGE_FAKE_PROCESS_LIST"] = fake_process_list
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
    return proc


def test_dry_run_builds_dynamic_probe_command_without_executing(tmp_path):
    proc = _run(
        "-ProbeLadderDynamicSurface",
        "-LadderDynamicTargetNodeId", _TARGET[0],
        "-LadderDynamicExpectedName", _TARGET[1],
        "-LadderDynamicExpectedGuid", _TARGET[2],
        "-LadderDynamicExpectedTypeGuid", _TARGET[3],
        tmp_path=tmp_path)
    out = proc.stdout
    assert proc.returncode == 0, out
    assert "--probe-ladder-dynamic-surface" in out
    for flag, value in zip(
            ("--ladder-dynamic-target-node-id", "--ladder-dynamic-expected-name",
             "--ladder-dynamic-expected-guid", "--ladder-dynamic-expected-type-guid"),
            _TARGET):
        assert flag in out
        assert value in out
    # Nada foi lancado.
    assert "ENSAIO (nada foi lancado)" in out
    # A flag do probe 16 NAO entra de carona.
    assert "--probe-ladder-surface" not in out


def test_dry_run_blocks_dynamic_probe_without_target(tmp_path):
    """Sem default de identidade: a flag sozinha reprova, nomeando o que
    falta, ANTES de montar qualquer comando."""
    proc = _run("-ProbeLadderDynamicSurface", tmp_path=tmp_path)
    out = proc.stdout
    assert proc.returncode == 2, out
    assert "-LadderDynamicTargetNodeId" in out
    assert "--probe-ladder-dynamic-surface" not in out


def test_dry_run_without_any_probe_flag_keeps_stage_b_behaviour(tmp_path):
    proc = _run(tmp_path=tmp_path)
    out = proc.stdout
    assert proc.returncode == 0, out
    assert "supervised-snapshot" in out
    assert "--probe-ladder-dynamic-surface" not in out
    assert "--probe-ladder-surface" not in out


def test_dry_run_blocks_when_fake_process_list_simulates_one_process(tmp_path):
    """Lista simulada com UM processo aberto: o wrapper bloqueia (exit 2)
    com a mesma mensagem que usaria para um processo real."""
    proc = _run(tmp_path=tmp_path, fake_process_list="MT8500.exe:4242")
    out = proc.stdout
    assert proc.returncode == 2, out
    assert "[BLOQUEADO] Ha instancia(s) do MasterTool aberta(s) (PID: 4242)" in out


def test_dry_run_fails_closed_on_malformed_fake_process_list(tmp_path):
    """Entrada malformada NUNCA vira 'nenhum processo aberto' -- o wrapper
    reprova fail-closed, nomeando o item invalido."""
    proc = _run(tmp_path=tmp_path, fake_process_list="isso-nao-e-valido")
    out = proc.stdout
    assert proc.returncode == 2, out
    assert "[BLOQUEADO]" in out
    assert "MASTERTOOL_BRIDGE_FAKE_PROCESS_LIST malformada" in out
    assert "Ha instancia(s) do MasterTool" not in out

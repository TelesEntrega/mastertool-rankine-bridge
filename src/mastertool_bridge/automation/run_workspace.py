"""Diretório de execução autossuficiente (Etapa B, contrato seções 1 e 5).

`create_run_workspace()` monta `<runs_root>/<run_id>/` com `logs/`,
`output/`, grava `run-config.json` e gera `bootstrap.py` — o alvo do
`--runscript` do MasterTool. `read_status()` lê o estado corrente escrito
pelo runner interno (IronPython, fora deste módulo), com a queda
obrigatória para `status-history.jsonl` descrita na seção 4 do contrato
(a troca de `status.json` não é atômica).
"""

from __future__ import annotations

import json
from pathlib import Path

from mastertool_bridge.automation.config_models import RunConfig
from mastertool_bridge.utils.json_io import write_json

STATUS_FILENAME = "status.json"
STATUS_HISTORY_FILENAME = "status-history.jsonl"
RUN_CONFIG_FILENAME = "run-config.json"
BOOTSTRAP_FILENAME = "bootstrap.py"

# Esqueleto EXATO da seção 5 do contrato. Não reformatar/"melhorar": o
# `globals()` na última linha não é opcional (ver contrato) e qualquer
# variação de nome de módulo/função quebra o acoplamento com o lado
# IronPython, que é gerado em paralelo.
_BOOTSTRAP_TEMPLATE = '''# -*- coding: utf-8 -*-
import json, os, sys

run_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(run_dir, "run-config.json")
f = open(config_path, "r")
try:
    config = json.load(f)
finally:
    f.close()

scripts_dir = config["mastertool_scripts_dir"]
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from automation import supervised_snapshot_runner
supervised_snapshot_runner.main(run_dir, globals())
'''


def render_bootstrap() -> str:
    """Devolve o conteúdo textual de `bootstrap.py` (seção 5 do contrato)."""
    return _BOOTSTRAP_TEMPLATE


def create_run_workspace(runs_root: Path, run_id: str, config: RunConfig) -> Path:
    """Cria `<runs_root>/<run_id>/` com `logs/`, `output/`, grava
    `run-config.json` (a partir de `config.to_dict()`) e `bootstrap.py`.

    Devolve o `Path` do `run_dir` criado. Não sobrescreve um `run_dir` que
    já exista com conteúdo — fail-closed: um `run_id` reaproveitado por
    acidente não deve silenciosamente misturar execuções."""
    runs_root = Path(runs_root)
    run_dir = runs_root / run_id

    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(
            f"run_dir já existe e não está vazio, fail-closed: {run_dir}")

    logs_dir = run_dir / "logs"
    output_dir = run_dir / "output"
    logs_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_json(run_dir / RUN_CONFIG_FILENAME, config.to_dict())

    bootstrap_path = run_dir / BOOTSTRAP_FILENAME
    bootstrap_path.write_text(render_bootstrap(), encoding="utf-8", newline="\n")

    return run_dir


def read_status(run_dir: Path) -> dict | None:
    """Lê `status.json`; se ausente ou corrompido (JSON inválido), cai para
    a última linha válida de `status-history.jsonl` (contrato seção 4: a
    troca de `status.json` não é atômica, o histórico é a fonte confiável
    na janela em que o arquivo pode estar ausente).

    Devolve `None` se nem `status.json` nem `status-history.jsonl`
    existirem ou tiverem conteúdo utilizável — nunca levanta exceção por
    isso (o runner interno pode ainda não ter escrito nada)."""
    run_dir = Path(run_dir)
    status_path = run_dir / STATUS_FILENAME

    if status_path.is_file():
        try:
            with open(status_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            pass

    history_path = run_dir / STATUS_HISTORY_FILENAME
    if not history_path.is_file():
        return None

    try:
        lines = history_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue

    return None

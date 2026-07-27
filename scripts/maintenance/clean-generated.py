#!/usr/bin/env python3
"""Remove artefatos gerados (temporários e normalized). NÃO apaga exports,
backups nem logs — esses são história do projeto e só se apagam manualmente."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SAFE_TO_CLEAN = [
    REPO_ROOT / "workspace" / "temporary",
    REPO_ROOT / "workspace" / "normalized",
]


def main() -> int:
    for target in SAFE_TO_CLEAN:
        if not target.is_dir():
            continue
        for item in target.iterdir():
            if item.name == ".gitkeep":
                continue
            print(f"removendo {item}")
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    print("Limpeza concluída (exports/backups/logs preservados por política).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

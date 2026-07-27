#!/usr/bin/env python3
"""Gera os artefatos classificados de workspace/analysis/static-api/ a partir
do catálogo bruto (tools/static-api-catalog.ps1).

Uso:
    python tools/build-static-api-catalog.py
    python tools/build-static-api-catalog.py --raw <caminho> --output <dir>
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mastertool_bridge.static_api.catalog import build_all_artifacts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw", default=str(REPO_ROOT / "workspace" / "analysis" / "static-api" / "raw-catalog.json"))
    parser.add_argument(
        "--output", default=str(REPO_ROOT / "workspace" / "analysis" / "static-api"))
    args = parser.parse_args()

    raw_path = Path(args.raw)
    if not raw_path.is_file():
        print(f"ERRO: catálogo bruto não encontrado: {raw_path}", file=sys.stderr)
        print("Execute primeiro: powershell -File tools/static-api-catalog.ps1", file=sys.stderr)
        return 1

    paths = build_all_artifacts(raw_path, Path(args.output))
    print(f"{len(paths)} artefato(s) gerado(s) em {args.output}:")
    for name in sorted(paths):
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

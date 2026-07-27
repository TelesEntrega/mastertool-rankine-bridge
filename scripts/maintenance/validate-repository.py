#!/usr/bin/env python3
"""Sanidade do repositório: estrutura esperada, scripts IronPython sem
sintaxe Python-3-only óbvia, schemas JSON válidos."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DIRS = [
    "config", "docs", "scripts/mastertool/common", "src/mastertool_bridge",
    "templates", "tests", "workspace/exports", "workspace/logs",
]
FORBIDDEN_IN_IRONPYTHON = [
    (re.compile(r"\bf['\"]"), "f-string"),
    (re.compile(r"\bimport\s+pathlib|\bfrom\s+pathlib\b"), "pathlib"),
    (re.compile(r"\bfrom\s+dataclasses\b"), "dataclasses"),
    (re.compile(r"def \w+\([^)]*:\s*\w+"), "type hint em parâmetro"),
]


def main() -> int:
    problems: list[str] = []

    for rel in REQUIRED_DIRS:
        if not (REPO_ROOT / rel).is_dir():
            problems.append(f"diretório ausente: {rel}")

    for script in sorted((REPO_ROOT / "scripts" / "mastertool").rglob("*.py")):
        text = script.read_text(encoding="utf-8")
        if "from __future__ import print_function" not in text:
            problems.append(f"{script.name}: falta 'from __future__ import print_function'")
        for pattern, label in FORBIDDEN_IN_IRONPYTHON:
            if pattern.search(text):
                problems.append(f"{script.name}: uso proibido de {label}")

    for schema in sorted((REPO_ROOT / "src" / "mastertool_bridge" / "schemas").glob("*.json")):
        try:
            json.loads(schema.read_text(encoding="utf-8"))
        except ValueError as exc:
            problems.append(f"schema inválido {schema.name}: {exc}")

    if problems:
        print(f"[FALHOU] {len(problems)} problema(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("[OK] Repositório consistente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

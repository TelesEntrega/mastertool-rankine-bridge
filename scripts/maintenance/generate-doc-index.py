#!/usr/bin/env python3
"""Gera docs/INDEX.md com o índice de toda a documentação."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"


def title_of(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def main() -> int:
    lines = ["# Índice da documentação", ""]
    for md in sorted(DOCS.rglob("*.md")):
        if md.name == "INDEX.md":
            continue
        rel = md.relative_to(DOCS).as_posix()
        indent = "  " * (len(md.relative_to(DOCS).parts) - 1)
        lines.append(f"{indent}- [{title_of(md)}]({rel})")
    lines += ["", "## Diagramas", ""]
    for mmd in sorted((DOCS / "diagrams").glob("*.mmd")):
        lines.append(f"- [{mmd.stem}](diagrams/{mmd.name})")
    (DOCS / "INDEX.md").write_text("\n".join(lines) + "\n",
                                   encoding="utf-8", newline="\n")
    print(f"Gerado {DOCS / 'INDEX.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

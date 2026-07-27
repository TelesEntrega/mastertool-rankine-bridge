"""Normalização de exports para comparação determinística.

Nunca altera o export original (imutável); grava a versão normalizada em
workspace/normalized/ quando solicitado.
"""

from __future__ import annotations

from pathlib import Path

from mastertool_bridge.models import ExportedProject
from mastertool_bridge.utils.json_io import write_json
from mastertool_bridge.utils.text import normalize_newlines


def normalize_st_text(text: str) -> str:
    """Normaliza para diff: EOL LF, sem espaços à direita, newline final."""
    lines = [line.rstrip() for line in normalize_newlines(text).split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def normalize_export(project: ExportedProject, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for obj in project.objects:
        obj_dir = output_dir / obj.object_type / obj.name
        obj_dir.mkdir(parents=True, exist_ok=True)
        if obj.declaration:
            (obj_dir / "declaration.st").write_text(
                normalize_st_text(obj.declaration), encoding="utf-8", newline="\n")
        if obj.implementation:
            (obj_dir / "implementation.st").write_text(
                normalize_st_text(obj.implementation), encoding="utf-8", newline="\n")
        index.append({
            "name": obj.name,
            "qualified_name": obj.qualified_name,
            "object_type": obj.object_type,
        })
    write_json(output_dir / "normalized-index.json", {
        "source_export": str(project.export_dir),
        "objects": index,
    })
    return output_dir

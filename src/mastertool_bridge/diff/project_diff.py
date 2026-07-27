"""Comparação entre dois exports completos."""

from __future__ import annotations

from mastertool_bridge.diff.object_diff import diff_objects
from mastertool_bridge.models import ExportedProject


def _key(obj) -> str:
    return obj.qualified_name or obj.name


def compare_projects(old: ExportedProject, new: ExportedProject) -> dict:
    old_map = {_key(o): o for o in old.objects}
    new_map = {_key(o): o for o in new.objects}

    added = sorted(set(new_map) - set(old_map))
    removed = sorted(set(old_map) - set(new_map))
    modified: list[dict] = []
    unchanged: list[str] = []

    for key in sorted(set(old_map) & set(new_map)):
        result = diff_objects(old_map[key], new_map[key])
        if result["status"] == "modified":
            modified.append(result)
        else:
            unchanged.append(key)

    return {
        "schema_version": "1.0",
        "export_a": str(old.export_dir),
        "export_b": str(new.export_dir),
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged_count": len(unchanged),
        "summary": (f"{len(added)} adicionado(s), {len(removed)} removido(s), "
                    f"{len(modified)} modificado(s), "
                    f"{len(unchanged)} inalterado(s)"),
    }

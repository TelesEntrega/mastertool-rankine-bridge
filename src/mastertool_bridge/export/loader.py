"""Carrega um diretório de export para os modelos da camada externa."""

from __future__ import annotations

from pathlib import Path

from mastertool_bridge.constants import MANIFEST_FILENAME, OBJECT_CATEGORIES
from mastertool_bridge.exceptions import ExportNotFoundError
from mastertool_bridge.models import ExportedProject, PlcObject
from mastertool_bridge.utils.json_io import read_json
from mastertool_bridge.utils.text import normalize_newlines

CATEGORY_TO_TYPE = {
    "programs": "program",
    "function-blocks": "function_block",
    "functions": "function",
    "methods": "method",
    "actions": "action",
    "properties": "property",
    "gvls": "gvl",
    "duts": "dut",
    "visualizations": "visualization",
    "other": "other",
}


def load_manifest(export_dir: Path) -> dict:
    manifest_path = export_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ExportNotFoundError(
            f"Manifesto não encontrado: {manifest_path}. "
            "O diretório é realmente um export do mastertool-rankine-bridge?")
    return read_json(manifest_path)


def _read_optional_text(path: Path) -> str | None:
    if path.is_file():
        return normalize_newlines(path.read_text(encoding="utf-8"))
    return None


def load_object(obj_dir: Path, category: str) -> PlcObject:
    metadata: dict = {}
    metadata_path = obj_dir / "metadata.json"
    if metadata_path.is_file():
        metadata = read_json(metadata_path)
    return PlcObject(
        name=metadata.get("name", obj_dir.name),
        object_type=metadata.get("object_type",
                                 CATEGORY_TO_TYPE.get(category, "other")),
        directory=obj_dir,
        qualified_name=metadata.get("qualified_name"),
        parent=metadata.get("parent"),
        language=metadata.get("language"),
        metadata=metadata,
        declaration=_read_optional_text(obj_dir / "declaration.st"),
        implementation=_read_optional_text(obj_dir / "implementation.st"),
    )


def load_export(export_dir: Path) -> ExportedProject:
    export_dir = Path(export_dir)
    if not export_dir.is_dir():
        raise ExportNotFoundError(f"Diretório de export inexistente: {export_dir}")
    manifest = load_manifest(export_dir)
    project = ExportedProject(export_dir=export_dir, manifest=manifest)

    objects_root = export_dir / "objects"
    if objects_root.is_dir():
        for category in OBJECT_CATEGORIES:
            category_dir = objects_root / category
            if not category_dir.is_dir():
                continue
            for obj_dir in sorted(p for p in category_dir.iterdir() if p.is_dir()):
                project.objects.append(load_object(obj_dir, category))
    return project

"""Índice de símbolos e objetos de um export, para buscas rápidas."""

from __future__ import annotations

from pathlib import Path

from mastertool_bridge.analysis.symbol_parser import parse_declaration
from mastertool_bridge.models import ExportedProject
from mastertool_bridge.utils.json_io import write_json


def build_index(project: ExportedProject) -> dict:
    index: dict = {
        "schema_version": "1.0",
        "source_export": str(project.export_dir),
        "project": project.name,
        "objects": [],
        "variables": [],
    }
    for obj in project.objects:
        entry = {
            "name": obj.name,
            "qualified_name": obj.qualified_name,
            "object_type": obj.object_type,
            "language": obj.language,
            "has_declaration": obj.has_declaration,
            "has_implementation": obj.has_implementation,
        }
        index["objects"].append(entry)
        if obj.declaration:
            symbol = parse_declaration(obj.declaration, obj.name)
            for var in symbol.variables:
                index["variables"].append({
                    "name": var.name,
                    "type": var.var_type,
                    "block": var.block,
                    "declared_in": obj.qualified_name or obj.name,
                    "address": var.address,
                    "retain": var.is_retain,
                    "persistent": var.is_persistent,
                })
    return index


def write_index(project: ExportedProject, output_path: Path) -> Path:
    return write_json(output_path, build_index(project))

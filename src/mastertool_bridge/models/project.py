"""Modelo do export de um projeto (visão externa, somente leitura)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mastertool_bridge.models.plc_object import PlcObject


@dataclass
class ExportedProject:
    export_dir: Path
    manifest: dict[str, Any]
    objects: list[PlcObject] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.manifest.get("project", {}).get("name", "<sem-nome>")

    @property
    def is_read_only(self) -> bool:
        return self.manifest.get("mode") == "read_only"

    def objects_by_type(self) -> dict[str, list[PlcObject]]:
        grouped: dict[str, list[PlcObject]] = {}
        for obj in self.objects:
            grouped.setdefault(obj.object_type, []).append(obj)
        return grouped

    def find(self, qualified_name: str) -> PlcObject | None:
        for obj in self.objects:
            if obj.qualified_name == qualified_name or obj.name == qualified_name:
                return obj
        return None

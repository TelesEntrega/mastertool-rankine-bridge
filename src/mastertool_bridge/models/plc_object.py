"""Objeto de CLP exportado (POU, GVL, DUT, ...)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PlcObject:
    name: str
    object_type: str
    directory: Path | None = None
    qualified_name: str | None = None
    parent: str | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    declaration: str | None = None
    implementation: str | None = None

    @property
    def has_declaration(self) -> bool:
        return bool(self.declaration)

    @property
    def has_implementation(self) -> bool:
        return bool(self.implementation)

    @property
    def full_text(self) -> str:
        return "\n".join(t for t in (self.declaration, self.implementation) if t)

"""Mapa de nós do export -> arquivos-fonte (declaration.st/implementation.st).

Construído a partir de `flat-objects.json` (+ `metadata.json` por objeto,
quando necessário para resolver o caminho exato do arquivo de texto). Não
lê conteúdo de arquivo nenhum — apenas caminhos e flags de disponibilidade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass(frozen=True)
class SourceFile:
    node_id: str
    name: str | None
    type_guid: str | None
    object_guid: str | None
    declaration_path: str | None
    implementation_path: str | None
    has_declaration: bool
    has_implementation: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type_guid": self.type_guid,
            "object_guid": self.object_guid,
            "declaration_file": self.declaration_path,
            "implementation_file": self.implementation_path,
            "has_declaration": self.has_declaration,
            "has_implementation": self.has_implementation,
        }


@dataclass
class SourceMap:
    """Coleção de `SourceFile` indexada por node_id."""

    files: dict[str, SourceFile] = field(default_factory=dict)

    def add(self, source_file: SourceFile) -> None:
        self.files[source_file.node_id] = source_file

    def get(self, node_id: str) -> SourceFile | None:
        return self.files.get(node_id)

    def __len__(self) -> int:
        return len(self.files)

    def __iter__(self) -> Iterator[SourceFile]:
        return iter(self.files.values())

    def nodes_with_declaration(self) -> list[SourceFile]:
        return [f for f in self.files.values() if f.has_declaration]

    def to_dict(self) -> dict[str, Any]:
        return {
            node_id: source_file.to_dict()
            for node_id, source_file in sorted(self.files.items())
        }

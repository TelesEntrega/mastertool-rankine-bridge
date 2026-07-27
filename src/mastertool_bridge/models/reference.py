"""Referência (uso) de um símbolo em código ST — resultado heurístico."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Reference:
    object_name: str
    line: int
    usage: str          # constants.USAGE_* (confirmed/probable read/write, unknown)
    snippet: str
    file: str | None = None

    def to_dict(self) -> dict:
        return {
            "object": self.object_name,
            "file": self.file,
            "line": self.line,
            "usage": self.usage,
            "snippet": self.snippet,
        }

"""Mensagem de compilação normalizada."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompilationMessage:
    severity: str               # error | warning | info | unknown
    text: str
    source: str | None = None
    object_name: str | None = None
    location: str | None = None
    timestamp: str | None = None

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "text": self.text,
            "source": self.source,
            "object": self.object_name,
            "location": self.location,
            "timestamp": self.timestamp,
        }

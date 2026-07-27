"""Diagnósticos não-fatais do StaticProjectIndexer.

Filosofia (mesma do scanner/exportador IronPython, replicada aqui em Python 3):
qualquer construção ambígua ou não suportada em lexing/parsing vira um
`Diagnostic` acumulado, NUNCA uma exceção que interrompe o processamento do
restante do export. Falha em um objeto nunca impede o processamento dos
demais.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mastertool_bridge.indexer.models import SourceLocation

Severity = str  # "error" | "warning" | "info"


@dataclass
class Diagnostic:
    severity: Severity
    code: str
    message: str
    location: SourceLocation | None = None
    node_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "location": self.location.to_dict() if self.location else None,
            "node_id": self.node_id,
        }


@dataclass
class DiagnosticsCollector:
    """Acumulador simples de diagnósticos, sem lançar exceção."""

    diagnostics: list[Diagnostic] = field(default_factory=list)

    def add(
        self,
        severity: Severity,
        code: str,
        message: str,
        location: SourceLocation | None = None,
        node_id: str | None = None,
    ) -> Diagnostic:
        diag = Diagnostic(
            severity=severity,
            code=code,
            message=message,
            location=location,
            node_id=node_id,
        )
        self.diagnostics.append(diag)
        return diag

    def error(
        self,
        code: str,
        message: str,
        location: SourceLocation | None = None,
        node_id: str | None = None,
    ) -> Diagnostic:
        return self.add("error", code, message, location, node_id)

    def warning(
        self,
        code: str,
        message: str,
        location: SourceLocation | None = None,
        node_id: str | None = None,
    ) -> Diagnostic:
        return self.add("warning", code, message, location, node_id)

    def info(
        self,
        code: str,
        message: str,
        location: SourceLocation | None = None,
        node_id: str | None = None,
    ) -> Diagnostic:
        return self.add("info", code, message, location, node_id)

    def extend(self, other: "DiagnosticsCollector | list[Diagnostic]") -> None:
        if isinstance(other, DiagnosticsCollector):
            self.diagnostics.extend(other.diagnostics)
        else:
            self.diagnostics.extend(other)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)

    def to_list(self) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self.diagnostics]

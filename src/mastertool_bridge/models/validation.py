"""Resultado padronizado de validações."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    subject: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def summary(self) -> str:
        status = "OK" if self.ok else "FALHOU"
        return (f"[{status}] {self.subject}: "
                f"{len(self.errors)} erro(s), {len(self.warnings)} aviso(s)")

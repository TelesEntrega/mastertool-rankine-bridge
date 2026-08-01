"""Dataclasses do resultado consolidado de uma execução supervisionada
(Etapa B, lado host). Ver `docs/16-supervised-runner-contract.md` seção 9
(divisão de responsabilidades) para o que cada campo representa.

Nenhuma lógica de decisão mora aqui — só estrutura de dados e serialização.
A decisão de estado final é de `supervised_run.orchestrate_run()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mastertool_bridge.automation.run_states import (  # noqa: F401
    TERMINAL_STATES,
)

# `TERMINAL_STATES` é reexportado de `run_states` — era declarado aqui e em
# `scripts/mastertool/automation/run_status.py`, duas cópias que podiam
# divergir em silêncio. Reexportado, e não movido de vez, porque chamadores
# existentes importam o nome deste módulo.


@dataclass
class ProvenanceCheckResult:
    """Resultado de `cli_probe_verify.check_provenance()` reaproveitado
    tal-e-qual (sem reinventar formato)."""

    inside_mastertool: bool
    checks: dict = field(default_factory=dict)
    reason: str | None = None

    @classmethod
    def from_raw(cls, raw: dict) -> "ProvenanceCheckResult":
        return cls(
            inside_mastertool=bool(raw.get("inside_mastertool")),
            checks=raw.get("checks") or {},
            reason=raw.get("reason"),
        )

    def to_dict(self) -> dict:
        return {
            "inside_mastertool": self.inside_mastertool,
            "checks": self.checks,
            "reason": self.reason,
        }


@dataclass
class ArtifactValidationResult:
    """Resultado de `artifact_validation.validate_output_artifacts()`."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)
    final_declaration: dict | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "checked_files": list(self.checked_files),
            "final_declaration": self.final_declaration,
        }


@dataclass
class IndexResult:
    """Resultado da chamada ao `StaticProjectIndexer` já existente
    (`mastertool_bridge.indexer.export_loader.build_static_index`) sobre o
    export textual produzido em `output/`. `skipped=True` quando
    `--no-index` foi pedido ou quando nenhum subdiretório de `output/`
    contém o layout de export esperado (ver docstring de
    `supervised_run.py` para a decisão de design).

    `counts` — quando `attempted and not skipped and ok` — carrega o resumo
    usado para comparar com a baseline (`v0.1.0`):
    `{"symbols": int, "type_symbols": int,
      "resolved_references": {"resolved": int, "partially_resolved": int,
                               "unresolved": int, ...},
      "resolved_calls": {"resolved": int, "unresolved": int, ...},
      "read_write_entries": int}`.

    `mismatches` — só populado quando o chamador passou
    `expected_index_counts` a `orchestrate_run()` e algum contador
    divergiu. Não vazio ⇒ o `final_state` do run NÃO pode ser
    `completed` (mesmo que `ok=True` — a comparação com a baseline é uma
    checagem à parte de "o indexador rodou sem erro")."""

    attempted: bool
    skipped: bool
    ok: bool
    reason: str | None = None
    index_dir: str | None = None
    export_dir: str | None = None
    counts: dict | None = None
    mismatches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "attempted": self.attempted,
            "skipped": self.skipped,
            "ok": self.ok,
            "reason": self.reason,
            "index_dir": self.index_dir,
            "export_dir": self.export_dir,
            "counts": self.counts,
            "mismatches": list(self.mismatches),
        }


@dataclass
class SupervisedRunResult:
    """Relatório consolidado de uma execução supervisionada completa (host)."""

    run_id: str
    final_state: str
    exit_code: int | None
    duration_seconds: float | None
    project_copy_path: str
    project_hash_before: str
    project_hash_after: str | None
    project_hash_unchanged: bool | None
    orphan_process_detected: bool
    orphan_process_ids: list[int] = field(default_factory=list)
    provenance: ProvenanceCheckResult | None = None
    artifact_validation: ArtifactValidationResult | None = None
    index_result: IndexResult | None = None
    internal_status: dict | None = None
    reasons: list[str] = field(default_factory=list)
    run_dir: str | None = None

    def __post_init__(self) -> None:
        if self.final_state not in TERMINAL_STATES:
            raise ValueError(
                "final_state deve ser um dos estados terminais do host: "
                + ", ".join(TERMINAL_STATES) + f" (recebido: {self.final_state!r})")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "final_state": self.final_state,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "project_copy_path": self.project_copy_path,
            "project_hash_before": self.project_hash_before,
            "project_hash_after": self.project_hash_after,
            "project_hash_unchanged": self.project_hash_unchanged,
            "orphan_process_detected": self.orphan_process_detected,
            "orphan_process_ids": list(self.orphan_process_ids),
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "artifact_validation": (
                self.artifact_validation.to_dict() if self.artifact_validation else None),
            "index_result": self.index_result.to_dict() if self.index_result else None,
            "internal_status": self.internal_status,
            "reasons": list(self.reasons),
        }

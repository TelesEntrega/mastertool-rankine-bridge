"""Mapa de uso de uma variável no projeto (heurístico)."""

from __future__ import annotations

from mastertool_bridge.analysis.reference_finder import (filter_reads,
                                                         filter_writes,
                                                         find_references)
from mastertool_bridge.models import ExportedProject


def usage_report(project: ExportedProject, variable: str) -> dict:
    references = find_references(project, variable)
    return {
        "schema_version": "1.0",
        "symbol": variable,
        "heuristic": True,
        "total_references": len(references),
        "writes": [r.to_dict() for r in filter_writes(references)],
        "reads": [r.to_dict() for r in filter_reads(references)],
        "references": [r.to_dict() for r in references],
    }

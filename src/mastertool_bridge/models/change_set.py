"""Modelo de change set (pacote de alteração proposta)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mastertool_bridge.constants import RISK_LEVELS

RISK_ORDER = {level: i for i, level in enumerate(RISK_LEVELS)}


@dataclass
class ChangeSetObject:
    qualified_name: str
    operation: str
    risk_level: str
    reason: str
    original_hash: str | None = None
    proposed_hash: str | None = None


@dataclass
class ChangeSet:
    change_id: str
    status: str
    source_export: str
    objects: list[ChangeSetObject] = field(default_factory=list)
    safety_checks: dict[str, Any] = field(default_factory=dict)
    source_export_hash: str | None = None
    target_project: str | None = None
    created_by: str | None = None
    requested_by: str | None = None

    @property
    def highest_risk(self) -> str:
        if not self.objects:
            return "low"
        return max((o.risk_level for o in self.objects),
                   key=lambda r: RISK_ORDER.get(r, len(RISK_LEVELS)))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChangeSet":
        objects = [
            ChangeSetObject(
                qualified_name=o["qualified_name"],
                operation=o["operation"],
                risk_level=o["risk_level"],
                reason=o["reason"],
                original_hash=o.get("original_hash"),
                proposed_hash=o.get("proposed_hash"),
            )
            for o in data.get("objects", [])
        ]
        return cls(
            change_id=data["change_id"],
            status=data["status"],
            source_export=data["source_export"],
            objects=objects,
            safety_checks=data.get("safety_checks", {}),
            source_export_hash=data.get("source_export_hash"),
            target_project=data.get("target_project"),
            created_by=data.get("created_by"),
            requested_by=data.get("requested_by"),
        )

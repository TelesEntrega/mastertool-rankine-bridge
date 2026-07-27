"""Carga e serialização de change sets."""

from __future__ import annotations

from pathlib import Path

from mastertool_bridge.export.validator import validate_against_schema
from mastertool_bridge.exceptions import ValidationError
from mastertool_bridge.models import ChangeSet
from mastertool_bridge.utils.json_io import read_json


def load_change_set(path: Path) -> ChangeSet:
    data = read_json(Path(path))
    issues = validate_against_schema(data, "change-set.schema.json")
    if issues:
        raise ValidationError(
            f"Change set inválido ({path}): {len(issues)} problema(s).",
            issues=issues)
    return ChangeSet.from_dict(data)

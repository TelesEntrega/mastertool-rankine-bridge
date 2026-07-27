"""Diff textual entre duas versões de um objeto."""

from __future__ import annotations

import difflib

from mastertool_bridge.export.normalizer import normalize_st_text
from mastertool_bridge.models import PlcObject


def diff_texts(old: str | None, new: str | None, label: str) -> list[str]:
    old_lines = normalize_st_text(old).splitlines(keepends=True) if old else []
    new_lines = normalize_st_text(new).splitlines(keepends=True) if new else []
    return list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{label}", tofile=f"b/{label}"))


def diff_objects(old: PlcObject | None, new: PlcObject | None) -> dict:
    name = (new or old).name if (new or old) else "<vazio>"
    result = {
        "object": name,
        "status": "unchanged",
        "declaration_diff": [],
        "implementation_diff": [],
    }
    if old is None and new is not None:
        result["status"] = "added"
    elif old is not None and new is None:
        result["status"] = "removed"
    result["declaration_diff"] = diff_texts(
        old.declaration if old else None,
        new.declaration if new else None,
        f"{name}/declaration.st")
    result["implementation_diff"] = diff_texts(
        old.implementation if old else None,
        new.implementation if new else None,
        f"{name}/implementation.st")
    if result["status"] == "unchanged" and (
            result["declaration_diff"] or result["implementation_diff"]):
        result["status"] = "modified"
    return result

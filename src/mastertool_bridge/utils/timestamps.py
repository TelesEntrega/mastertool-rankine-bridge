"""Timestamps padronizados (ISO-8601 com timezone local)."""

from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def stamp_for_dirname() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

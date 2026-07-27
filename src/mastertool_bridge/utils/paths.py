"""Normalização de caminhos Windows e nomes de arquivo seguros."""

from __future__ import annotations

import re
from pathlib import Path

WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def normalize_path(raw: str) -> str:
    """Normaliza separadores para '/' (formato interno dos manifestos)."""
    return raw.replace("\\", "/").rstrip("/")


def safe_filename(name: str, max_len: int = 100) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name or "").strip("._ ") or "sem-nome"
    if cleaned.split(".")[0].upper() in WINDOWS_RESERVED:
        cleaned = "_" + cleaned
    return cleaned[:max_len]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

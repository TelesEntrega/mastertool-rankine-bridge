"""SHA-256 de textos e arquivos, e verificação de checksums.sha256."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_checksums_file(path: Path) -> dict[str, str]:
    """Lê 'hash  caminho/relativo' -> {caminho: hash}. Linhas com ERRO são ignoradas."""
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("ERRO"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            digest, rel = parts
            entries[rel.strip()] = digest.strip()
    return entries


def verify_checksums(export_dir: Path, checksums_path: Path) -> list[str]:
    """Retorna lista de problemas (vazia = tudo confere)."""
    issues: list[str] = []
    entries = parse_checksums_file(checksums_path)
    for rel, expected in entries.items():
        target = export_dir / rel
        if not target.is_file():
            issues.append(f"checksum lista arquivo inexistente: {rel}")
            continue
        actual = sha256_file(target)
        if actual != expected:
            issues.append(f"hash divergente: {rel} (esperado {expected[:12]}…, "
                          f"obtido {actual[:12]}…)")
    return issues

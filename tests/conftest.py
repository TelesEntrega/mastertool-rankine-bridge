"""Fixtures compartilhadas dos testes da camada externa."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mastertool_bridge.utils.hashing import sha256_file

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def sample_project_dir() -> Path:
    return FIXTURES / "sample_project"


@pytest.fixture
def sample_export(tmp_path: Path, sample_project_dir: Path) -> Path:
    """Cópia do export sintético com checksums.sha256 gerado na hora."""
    dest = tmp_path / "export"
    shutil.copytree(sample_project_dir, dest)
    lines = []
    for file in sorted(dest.rglob("*")):
        if file.is_file() and file.name != "checksums.sha256":
            rel = file.relative_to(dest).as_posix()
            lines.append(f"{sha256_file(file)}  {rel}")
    (dest / "checksums.sha256").write_text("\n".join(lines) + "\n",
                                           encoding="utf-8")
    return dest

"""Carregamento de configuração (config/default.yaml + safety-policy.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mastertool_bridge.exceptions import SafetyPolicyViolation

DEFAULT_CONFIG_RELPATH = Path("config") / "default.yaml"
SAFETY_POLICY_RELPATH = Path("config") / "safety-policy.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or {}


def load_config(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or find_repo_root()
    path = root / DEFAULT_CONFIG_RELPATH
    if not path.is_file():
        return {}
    return load_yaml(path)


def load_safety_policy(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or find_repo_root()
    path = root / SAFETY_POLICY_RELPATH
    if not path.is_file():
        raise SafetyPolicyViolation(
            f"Política de segurança não encontrada em {path}. "
            "Operação bloqueada (fail closed).")
    return load_yaml(path)


def find_repo_root(start: Path | None = None) -> Path:
    """Sobe diretórios procurando a raiz do repositório (config/ + pyproject)."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "config").is_dir():
            return candidate
    return current


def assert_feature_enabled(config: dict[str, Any], feature: str) -> None:
    features = config.get("features", {})
    if not features.get(feature, False):
        raise SafetyPolicyViolation(
            f"Feature '{feature}' está desabilitada na configuração. "
            "Habilitação exige decisão humana registrada.")

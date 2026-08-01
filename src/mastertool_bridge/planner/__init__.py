"""Planner declarativo de autoria: `project_spec` -> plano de autoria literal.

Camada HOST (CPython 3), 100% offline. Ver `planner.py` para o contrato
completo, inclusive por que o conjunto de `operation` é fechado.
"""

from mastertool_bridge.planner.planner import (
    EXECUTOR_CONTRACT,
    PLAN_KIND,
    PLAN_OPERATIONS,
    PLAN_SCHEMA_VERSION,
    PlannerError,
    PlanResult,
    build_authoring_plan,
    canonical_json,
    normalize_authoring_text,
    plan_to_json,
    sha256_of_text,
)

__all__ = [
    "EXECUTOR_CONTRACT",
    "PLAN_KIND",
    "PLAN_OPERATIONS",
    "PLAN_SCHEMA_VERSION",
    "PlanResult",
    "PlannerError",
    "build_authoring_plan",
    "canonical_json",
    "normalize_authoring_text",
    "plan_to_json",
    "sha256_of_text",
]

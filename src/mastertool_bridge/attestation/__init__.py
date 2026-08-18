"""Capability Attestation — a maturidade de campo sai do código estático.

Ver `loader.py` para o contrato e o motivo.
"""

from mastertool_bridge.attestation.loader import (
    ATTESTATION_SCHEMA_VERSION,
    REASON_NOT_LOADED,
    AttestationLoad,
    load_attestation,
    load_default_attestation,
)
from mastertool_bridge.attestation.operational import load_for_execution

__all__ = [
    "ATTESTATION_SCHEMA_VERSION",
    "REASON_NOT_LOADED",
    "AttestationLoad",
    "load_attestation",
    "load_default_attestation",
    "load_for_execution",
]

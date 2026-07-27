"""Registro de aprovação humana — TERCEIRA ENTREGA (não implementado).

A aprovação será um arquivo approval.md assinado no diretório do change set;
este módulo fará a checagem de presença/validade. Ver templates/approval-template.md.
"""

from __future__ import annotations

from mastertool_bridge.exceptions import NotImplementedPhaseError


def record_approval(*_args, **_kwargs):
    raise NotImplementedPhaseError(
        "Registro de aprovação planejado para a terceira entrega.")


def check_approval(*_args, **_kwargs):
    raise NotImplementedPhaseError(
        "Checagem de aprovação planejada para a terceira entrega.")

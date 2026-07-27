"""Montagem do pacote físico de change set — TERCEIRA ENTREGA (não implementado).

Estrutura alvo: workspace/change-sets/<id>/{change-set.json, summary.md,
risk-assessment.md, approval.md, original/, proposed/, diffs/, validation/}.
"""

from __future__ import annotations

from mastertool_bridge.exceptions import NotImplementedPhaseError


def build_package(*_args, **_kwargs):
    raise NotImplementedPhaseError(
        "Montagem de pacotes de change set planejada para a terceira entrega.")

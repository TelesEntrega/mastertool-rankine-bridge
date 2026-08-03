"""Aprovação humana de um change set — fase R6.

Substitui o stub que levantava `NotImplementedPhaseError`. Módulo puro: não
aplica mudança nenhuma, não abre o MasterTool e não gera timestamp por conta
própria — a hora entra como dado, para que o registro seja reproduzível e para
que ninguém confunda "quando o objeto foi criado em memória" com "quando a
pessoa decidiu".

A DECISÃO É AMARRADA À EVIDÊNCIA QUE ELA APROVOU
================================================
Uma aprovação que diga apenas "aprovado por Fulano" não distingue o artefato
que a pessoa examinou daquele que está em disco agora. Por isso toda decisão
carrega o `bundle_sha256` do Evidence Bundle selado, e `check_approval`
compara: se o pacote mudou depois da decisão, a aprovação **não vale mais** —
não porque alguém agiu de má-fé, mas porque ninguém aprovou aquilo.

É a mesma razão de o executor exigir `expected_before_sha256` antes de
escrever: consentimento vale para um conteúdo, não para um nome.

O plano antigo previa um `approval.md` assinado no diretório do change set.
A forma mudou para dado estruturado — `approval/decision.json`, dentro do
Evidence Bundle — porque o pacote já carrega hash por arquivo, e um Markdown
solto ao lado dele ficaria fora dessa conferência.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from mastertool_bridge.changes.lifecycle import (
    APPROVED,
    AWAITING_APPROVAL,
    ChangeSetLifecycle,
    REJECTED,
    TransitionRecord,
)

SCHEMA_VERSION = 1

DECISION_APPROVED = "approved"
DECISION_REJECTED = "rejected"
DECISIONS = (DECISION_APPROVED, DECISION_REJECTED)

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
# ISO 8601 até o minuto, no mínimo. Não aceita "hoje", "agora" nem número solto.
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?")


@dataclass(frozen=True)
class ApprovalDecision:
    change_id: str
    decision: str
    approver: str
    reason: str
    decided_at: str
    bundle_sha256: str
    artifact_to_discard: str | None = None

    @property
    def approved(self) -> bool:
        return self.decision == DECISION_APPROVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "change_id": self.change_id,
            "decision": self.decision,
            "approved": self.approved,
            "approver": self.approver,
            "reason": self.reason,
            "decided_at": self.decided_at,
            "bundle_sha256": self.bundle_sha256,
            "artifact_to_discard": self.artifact_to_discard,
        }


@dataclass
class ApprovalResult:
    decision: ApprovalDecision | None = None
    problems: list[str] = field(default_factory=list)
    transition: TransitionRecord | None = None

    @property
    def recorded(self) -> bool:
        return (not self.problems and self.transition is not None
                and self.transition.accepted)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recorded": self.recorded,
            "problems": list(self.problems),
            "decision": self.decision.to_dict() if self.decision else None,
            "transition": (self.transition.to_dict()
                           if self.transition else None),
        }


def validate_decision(decision: Any) -> list[str]:
    """Problemas de uma decisão, sem levantar."""
    problems: list[str] = []
    if not isinstance(decision, ApprovalDecision):
        return ["decision: esperado ApprovalDecision, recebido %s"
                % type(decision).__name__]

    if decision.decision not in DECISIONS:
        problems.append("decision: esperado um de %s, recebido %r"
                        % (", ".join(DECISIONS), decision.decision))

    for campo in ("change_id", "approver", "reason"):
        valor = getattr(decision, campo)
        if not isinstance(valor, str) or not valor.strip():
            problems.append("%s: string não vazia obrigatória" % campo)

    if not isinstance(decision.decided_at, str) \
            or not _TIMESTAMP_RE.match(decision.decided_at):
        problems.append(
            "decided_at: esperado carimbo ISO 8601 (YYYY-MM-DDThh:mm) — uma "
            "decisão sem hora não pode ser situada em relação à evidência")

    if not isinstance(decision.bundle_sha256, str) \
            or not _SHA256_RE.match(decision.bundle_sha256):
        problems.append(
            "bundle_sha256: esperado hex de 64 caracteres. Consentimento vale "
            "para um conteúdo, não para um nome")

    if decision.decision == DECISION_REJECTED:
        if not isinstance(decision.artifact_to_discard, str) \
                or not decision.artifact_to_discard.strip():
            problems.append(
                "artifact_to_discard: obrigatório ao rejeitar depois da "
                "execução — sem nomear o artefato, o descarte não é "
                "verificável")

    return problems


def record_approval(lifecycle: Any, decision: Any) -> ApprovalResult:
    """Registra a decisão humana e move o change set.

    Exige que o change set esteja em `awaiting_approval`: aprovar antes disso
    seria aprovar o que ainda não foi verificado nem compilado, e a ordem do
    ciclo existe para tornar isso impossível.
    """
    resultado = ApprovalResult()

    if not isinstance(lifecycle, ChangeSetLifecycle):
        resultado.problems.append(
            "lifecycle: esperado ChangeSetLifecycle, recebido %s"
            % type(lifecycle).__name__)
        return resultado

    problemas = validate_decision(decision)
    if problemas:
        resultado.problems.extend(problemas)
        return resultado

    resultado.decision = decision

    if decision.change_id != lifecycle.change_id:
        resultado.problems.append(
            "decisão é do change set %r e o ciclo é do %r — aprovar um pelo "
            "outro é o erro que o identificador existe para impedir"
            % (decision.change_id, lifecycle.change_id))
        return resultado

    if lifecycle.state != AWAITING_APPROVAL:
        resultado.problems.append(
            "change set está em %r; a decisão humana só é registrável em %r"
            % (lifecycle.state, AWAITING_APPROVAL))
        return resultado

    destino = APPROVED if decision.approved else REJECTED
    resultado.transition = lifecycle.transition(
        destino, actor=decision.approver, reason=decision.reason,
        artifact_to_discard=decision.artifact_to_discard)
    if not resultado.transition.accepted:
        resultado.problems.extend(resultado.transition.problems)
    return resultado


def check_approval(decision: Any, current_bundle_sha256: Any) -> list[str]:
    """A aprovação ainda vale para o pacote que está em disco?

    Devolve lista vazia quando vale. Divergência de hash não é acusação de
    má-fé: é a constatação de que **ninguém aprovou o que está lá agora**.
    """
    problems = validate_decision(decision)
    if problems:
        return problems

    if not isinstance(current_bundle_sha256, str) \
            or not _SHA256_RE.match(current_bundle_sha256):
        return ["current_bundle_sha256: esperado hex de 64 caracteres"]

    if decision.bundle_sha256.lower() != current_bundle_sha256.lower():
        return [
            "o pacote mudou depois da decisão: aprovado %s, em disco %s. A "
            "aprovação não vale para este conteúdo — ninguém o examinou"
            % (decision.bundle_sha256, current_bundle_sha256)]

    if not decision.approved:
        return ["a decisão registrada foi de REJEIÇÃO, não de aprovação"]

    return []

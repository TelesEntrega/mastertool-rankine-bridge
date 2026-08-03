"""Ciclo de vida de um change set — a máquina de estados da fase R6.

Módulo puro, offline. Não executa mudança nenhuma: ele registra em que ponto
do processo um change set está, quem o moveu, quando e por quê. A regra que
governa tudo é a do roadmap R6 — **nenhuma operação manual oculta fora do
journal**: toda transição fica registrada, inclusive as recusadas.

A DIVERGÊNCIA DE VOCABULÁRIO, DECLARADA E NÃO SILENCIADA
========================================================
`docs/ROADMAP.md` R6 descreve dez estados; `schemas/change-set.schema.json`
declara seis, e dois deles (`applied`, `rolled_back`) não existem no roadmap.
Os dois vocabulários coexistem hoje no repositório, e a auditoria de
2026-08-01 registrou isso como contradição C2.

Este módulo implementa **os dez do roadmap**, porque é o roadmap que descreve
o processo que se quer ter, e oferece `SCHEMA_STATUS_MAP` para traduzir para o
vocabulário do schema — que continua sendo o que valida os arquivos já
existentes. Trocar o schema seria invalidar change sets gravados; traduzir sem
declarar seria esconder a divergência. A tradução é explícita e testada, e a
divergência continua sendo um achado a resolver, não um detalhe resolvido.

O QUE ROLLBACK SIGNIFICA AQUI
=============================
O projeto original nunca é alterado, então não existe "desfazer parcialmente".
Rollback é: invalidar e descartar o ARTEFATO NOVO, preservar a evidência, e
voltar a apontar para o último projeto aprovado. Por isso `rollback()` não é
uma transição própria — é uma rejeição depois da execução, com o artefato a
descartar nomeado no registro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

# --- os dez estados do roadmap R6 -------------------------------------------
DRAFT = "draft"
VALIDATED = "validated"
PLANNED = "planned"
AUTHORIZED = "authorized"
EXECUTED = "executed"
VERIFIED = "verified"
BUILD_PASSED = "build_passed"
AWAITING_APPROVAL = "awaiting_approval"
APPROVED = "approved"
REJECTED = "rejected"
ARCHIVED = "archived"

LIFECYCLE_STATES = (
    DRAFT, VALIDATED, PLANNED, AUTHORIZED, EXECUTED, VERIFIED, BUILD_PASSED,
    AWAITING_APPROVAL, APPROVED, REJECTED, ARCHIVED,
)

# Estados a partir dos quais o artefato novo já existe em disco. Rejeitar a
# partir daqui exige dizer qual artefato descartar — rejeitar antes disso não,
# porque não há artefato.
STATES_WITH_ARTIFACT = frozenset({EXECUTED, VERIFIED, BUILD_PASSED,
                                  AWAITING_APPROVAL, APPROVED})

TERMINAL_STATES = frozenset({ARCHIVED})

# Caminho feliz, em ordem. Cada estado só avança para o seguinte: pular etapa
# seria aprovar o que não foi verificado, ou verificar o que não foi executado.
_HAPPY_PATH = {
    DRAFT: VALIDATED,
    VALIDATED: PLANNED,
    PLANNED: AUTHORIZED,
    AUTHORIZED: EXECUTED,
    EXECUTED: VERIFIED,
    VERIFIED: BUILD_PASSED,
    BUILD_PASSED: AWAITING_APPROVAL,
    AWAITING_APPROVAL: APPROVED,
    APPROVED: ARCHIVED,
    REJECTED: ARCHIVED,
}

# Abortar é possível em qualquer estado não terminal, e é o único desvio.
# Modelado como lista explícita em vez de curinga: um curinga permitiria
# `archived -> rejected`, que reabriria o que já foi encerrado.
_ABORTABLE = frozenset(set(LIFECYCLE_STATES) - TERMINAL_STATES - {REJECTED})

# Tradução para o vocabulário do schema vigente. Ver o cabeçalho: os dois
# coexistem, e este mapa é a ponte declarada.
SCHEMA_STATUS_MAP = {
    DRAFT: "draft",
    VALIDATED: "validated",
    PLANNED: "validated",
    AUTHORIZED: "approved",
    EXECUTED: "applied",
    VERIFIED: "applied",
    BUILD_PASSED: "applied",
    AWAITING_APPROVAL: "validated",
    APPROVED: "approved",
    REJECTED: "rejected",
    ARCHIVED: "rolled_back",
}


class LifecycleError(ValueError):
    """Transição impossível pedida a `advance`/`reject`. As funções de
    validação devolvem problemas em lista; esta existe para o caminho que
    prefere falhar alto."""


@dataclass(frozen=True)
class TransitionRecord:
    """Uma transição, aceita ou recusada.

    As recusadas também entram no journal: "nenhuma operação manual oculta"
    inclui a tentativa que não passou — ela conta o que alguém tentou fazer.
    """

    from_state: str
    to_state: str
    actor: str
    reason: str
    accepted: bool
    problems: tuple[str, ...] = ()
    artifact_to_discard: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_state": self.from_state,
            "to_state": self.to_state,
            "actor": self.actor,
            "reason": self.reason,
            "accepted": self.accepted,
            "problems": list(self.problems),
            "artifact_to_discard": self.artifact_to_discard,
        }


def allowed_transitions(state: str) -> tuple[str, ...]:
    """Para onde `state` pode ir. Vazio em estado terminal ou desconhecido."""
    if state not in LIFECYCLE_STATES:
        return ()
    destinos: list[str] = []
    seguinte = _HAPPY_PATH.get(state)
    if seguinte:
        destinos.append(seguinte)
    if state in _ABORTABLE and REJECTED not in destinos:
        destinos.append(REJECTED)
    return tuple(destinos)


def validate_transition(from_state: Any, to_state: Any, *, actor: Any = "",
                        reason: Any = "",
                        artifact_to_discard: Any = None) -> list[str]:
    """Problemas de uma transição. Lista vazia = aceitável."""
    problems: list[str] = []

    if from_state not in LIFECYCLE_STATES:
        problems.append("estado de origem %r fora do vocabulário" % (from_state,))
    if to_state not in LIFECYCLE_STATES:
        problems.append("estado de destino %r fora do vocabulário" % (to_state,))
    if problems:
        return problems

    if from_state in TERMINAL_STATES:
        problems.append(
            "%r é terminal: reabrir o que já foi encerrado apagaria o registro "
            "de que foi encerrado" % (from_state,))
        return problems

    if to_state not in allowed_transitions(from_state):
        problems.append(
            "transição %r -> %r não é permitida; a partir de %r só: %s"
            % (from_state, to_state, from_state,
               ", ".join(allowed_transitions(from_state)) or "(nenhuma)"))

    if not isinstance(actor, str) or not actor.strip():
        problems.append(
            "actor: obrigatório em toda transição — um estado que mudou sem "
            "responsável é operação sem dono")

    if not isinstance(reason, str) or not reason.strip():
        problems.append(
            "reason: obrigatório em toda transição — sem motivo, o journal "
            "registra que algo mudou e não por quê")

    if to_state == REJECTED and from_state in STATES_WITH_ARTIFACT:
        if not isinstance(artifact_to_discard, str) or not artifact_to_discard.strip():
            problems.append(
                "artifact_to_discard: obrigatório ao rejeitar a partir de %r. "
                "Rollback aqui é descartar o artefato NOVO; sem nomeá-lo, o "
                "descarte não é verificável" % (from_state,))

    return problems


@dataclass
class ChangeSetLifecycle:
    """O estado corrente de um change set, com o journal de como chegou aqui."""

    change_id: str
    state: str = DRAFT
    journal: list[TransitionRecord] = field(default_factory=list)

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def has_artifact(self) -> bool:
        return self.state in STATES_WITH_ARTIFACT

    def can_advance_to(self, to_state: str) -> bool:
        return to_state in allowed_transitions(self.state)

    def transition(self, to_state: str, *, actor: str, reason: str,
                   artifact_to_discard: str | None = None) -> TransitionRecord:
        """Tenta mover. Registra no journal em qualquer caso, e só muda o
        estado se a transição for aceita."""
        problems = validate_transition(
            self.state, to_state, actor=actor, reason=reason,
            artifact_to_discard=artifact_to_discard)
        registro = TransitionRecord(
            from_state=self.state, to_state=to_state,
            actor=actor if isinstance(actor, str) else "",
            reason=reason if isinstance(reason, str) else "",
            accepted=not problems, problems=tuple(problems),
            artifact_to_discard=artifact_to_discard)
        self.journal.append(registro)
        if not problems:
            self.state = to_state
        return registro

    def advance(self, *, actor: str, reason: str) -> TransitionRecord:
        """Avança pelo caminho feliz, sem precisar nomear o destino.

        Existe para que o chamador não escreva o nome do próximo estado — é
        onde um erro de digitação viraria uma etapa pulada.
        """
        seguinte = _HAPPY_PATH.get(self.state)
        if seguinte is None:
            registro = TransitionRecord(
                from_state=self.state, to_state=self.state, actor=actor,
                reason=reason, accepted=False,
                problems=("não há próximo estado a partir de %r" % self.state,))
            self.journal.append(registro)
            return registro
        return self.transition(seguinte, actor=actor, reason=reason)

    def reject(self, *, actor: str, reason: str,
               artifact_to_discard: str | None = None) -> TransitionRecord:
        return self.transition(REJECTED, actor=actor, reason=reason,
                               artifact_to_discard=artifact_to_discard)

    def rollback(self, *, actor: str, reason: str,
                 artifact_to_discard: str) -> TransitionRecord:
        """Rollback = rejeitar depois da execução, nomeando o artefato a
        descartar.

        Não é transição própria de propósito: o original nunca foi tocado, e
        um estado `rolled_back` sugeriria que houve algo a desfazer no projeto
        de origem. O que há é um artefato novo a invalidar.
        """
        if self.state not in STATES_WITH_ARTIFACT:
            registro = TransitionRecord(
                from_state=self.state, to_state=REJECTED, actor=actor,
                reason=reason, accepted=False,
                problems=("rollback pedido em %r, onde ainda não existe "
                          "artefato novo a descartar" % self.state,),
                artifact_to_discard=artifact_to_discard)
            self.journal.append(registro)
            return registro
        return self.reject(actor=actor, reason=reason,
                           artifact_to_discard=artifact_to_discard)

    @property
    def schema_status(self) -> str:
        """O estado traduzido para o vocabulário de `change-set.schema.json`.
        Ver a divergência declarada no cabeçalho do módulo."""
        return SCHEMA_STATUS_MAP[self.state]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "change_id": self.change_id,
            "state": self.state,
            "schema_status": self.schema_status,
            "terminal": self.terminal,
            "has_artifact": self.has_artifact,
            "allowed_next": list(allowed_transitions(self.state)),
            "journal": [r.to_dict() for r in self.journal],
        }

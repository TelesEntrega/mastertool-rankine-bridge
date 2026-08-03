"""Vocabulário formal de estado de evidência — e a regra que impede ausência
de evidência de virar negação.

Módulo puro, offline, sem dependência externa. Existe por causa de um defeito
de comportamento observado na auditoria de 2026-08-01: um levantamento que não
acha implementação tende a ser relatado como "não existe", quando o que se
mediu foi "a busca não achou". As duas frases levam a decisões opostas — uma
manda construir, a outra manda procurar melhor — e só uma delas é sustentada
pelo que foi feito.

A REGRA FUNDAMENTAL
===================
    no_evidence_located != contradicted

`contradicted` é um resultado POSITIVO: houve teste, e a hipótese caiu.
`no_evidence_located` é uma declaração sobre a BUSCA, não sobre o mundo. Este
módulo torna a diferença estrutural de três formas:

1. o vocabulário é fechado, e não tem nenhum termo que sirva para as duas
   coisas (não existe `unsupported`, `false`, `missing` — cada um desses
   confundiria as duas leituras);
2. `no_evidence_located` EXIGE dizer o que foi procurado, onde, por que nada
   concluiu e qual é o próximo método. Uma ausência sem esses campos não é
   registrável — o que impede "não achei" de ser barato;
3. a transição de `no_evidence_located` para `contradicted` exige evidência
   nova e não vazia. Reclassificar sem medir nada é recusado por
   `validate_transition`, com nome próprio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

# --- vocabulário FECHADO -----------------------------------------------------
PROVEN = "proven"
CONTRADICTED = "contradicted"
NO_EVIDENCE_LOCATED = "no_evidence_located"
REQUIRES_FIELD = "requires_field"
NOT_APPLICABLE = "not_applicable"
BLOCKED = "blocked"

EVIDENCE_STATUSES = (
    PROVEN, CONTRADICTED, NO_EVIDENCE_LOCATED, REQUIRES_FIELD,
    NOT_APPLICABLE, BLOCKED,
)

STATUS_MEANING = {
    PROVEN: "existe evidência positiva suficiente",
    CONTRADICTED: "foi testado e a hipótese foi refutada",
    NO_EVIDENCE_LOCATED: "a busca não encontrou evidência suficiente",
    REQUIRES_FIELD: "só pode ser resolvido com o MasterTool aberto",
    NOT_APPLICABLE: "não se aplica ao escopo avaliado",
    BLOCKED: "há pré-condição ainda não satisfeita",
}

# Estados que afirmam algo sobre o MUNDO, e por isso exigem evidência citável.
_ASSERTIVE = frozenset({PROVEN, CONTRADICTED})

# Estados que afirmam algo sobre a BUSCA ou sobre o processo. Nenhum deles
# pode ser lido como negação do que se procurava.
_NON_ASSERTIVE = frozenset({NO_EVIDENCE_LOCATED, REQUIRES_FIELD, BLOCKED})

# Palavras que um relatório costuma usar como se fossem sinônimo de negação, e
# que na verdade descrevem a busca. Mapeadas EXPLICITAMENTE para
# `no_evidence_located` — nunca para `contradicted`.
_ABSENCE_PHRASES = (
    "sem evidência localizada",
    "sem evidencia localizada",
    "não localizado",
    "nao localizado",
    "não encontrado",
    "nao encontrado",
    "busca não retornou",
    "busca nao retornou",
)

# Termos proibidos como status: cada um serve para as duas leituras ao mesmo
# tempo, que é precisamente o defeito que este módulo existe para impedir.
_FORBIDDEN_STATUS_WORDS = {
    "false": "confunde 'não achei' com 'provei que não'",
    "unsupported": "confunde 'não suportado pelo produto' com 'não medido'",
    "rejected": "sugere veredito onde houve apenas ausência de busca positiva",
    "missing": "descreve o artefato, não o estado do conhecimento",
    "unknown": "não distingue 'não procurei' de 'procurei e não achei'",
    "n/a": "abreviação que esconde qual dos seis estados se aplica",
}


class EvidenceStatusError(ValueError):
    """Levantada só por `require_status`. As funções de validação devolvem
    problemas em lista; esta existe para o chamador que prefere falhar alto."""


@dataclass(frozen=True)
class EvidenceClaim:
    """Uma afirmação de auditoria, com o que a sustenta.

    Os quatro campos de busca são obrigatórios em `no_evidence_located` e
    opcionais nos demais. Não são decoração: sem eles, "não achei" seria uma
    conclusão sem método, impossível de refazer por outra pessoa — e o próximo
    a olhar repetiria a mesma busca sem saber que já foi feita.
    """

    item_id: str
    status: str
    summary: str
    evidence: tuple[str, ...] = ()
    queries_run: tuple[str, ...] = ()
    sources_examined: tuple[str, ...] = ()
    reason: str | None = None
    next_verification_method: str | None = None
    requires_field: bool = False
    origin: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "status": self.status,
            "summary": self.summary,
            "evidence": list(self.evidence),
            "queries_run": list(self.queries_run),
            "sources_examined": list(self.sources_examined),
            "reason": self.reason,
            "next_verification_method": self.next_verification_method,
            "requires_field": self.requires_field,
            "origin": self.origin,
        }


def normalize_status(raw: Any) -> tuple[str | None, list[str]]:
    """Traduz um texto de relatório para o vocabulário, ou recusa.

    Frase de ausência vira `no_evidence_located`, SEMPRE — nunca
    `contradicted`. Termo ambíguo (`false`, `unsupported`, `missing`…) é
    recusado com o motivo, em vez de mapeado para o palpite mais próximo:
    adivinhar aqui reintroduziria a confusão pela porta dos fundos.
    """
    problems: list[str] = []
    if not isinstance(raw, str) or not raw.strip():
        return None, ["status: esperado string não vazia"]

    texto = raw.strip().lower()

    if texto in EVIDENCE_STATUSES:
        return texto, []

    for palavra, motivo in _FORBIDDEN_STATUS_WORDS.items():
        if texto == palavra:
            return None, ["status %r é proibido: %s. Use um dos seis: %s"
                          % (raw, motivo, ", ".join(EVIDENCE_STATUSES))]

    for frase in _ABSENCE_PHRASES:
        if frase in texto:
            return NO_EVIDENCE_LOCATED, []

    problems.append(
        "status %r fora do vocabulário fechado: %s"
        % (raw, ", ".join(EVIDENCE_STATUSES)))
    return None, problems


def validate_claim(claim: Any) -> list[str]:
    """Problemas de uma afirmação. Lista vazia = registrável."""
    problems: list[str] = []
    if not isinstance(claim, EvidenceClaim):
        return ["claim: esperado EvidenceClaim, recebido %s"
                % type(claim).__name__]

    if claim.status not in EVIDENCE_STATUSES:
        problems.append("status %r fora do vocabulário fechado" % (claim.status,))
        return problems

    if not claim.item_id.strip():
        problems.append("item_id: string não vazia obrigatória")
    if not claim.summary.strip():
        problems.append("summary: string não vazia obrigatória")

    if claim.status in _ASSERTIVE and not claim.evidence:
        problems.append(
            "%s afirma algo sobre o mundo e precisa de evidência citável; sem "
            "ela, o estado correto é %r" % (claim.status, NO_EVIDENCE_LOCATED))

    if claim.status == NO_EVIDENCE_LOCATED:
        if not claim.queries_run:
            problems.append(
                "no_evidence_located exige `queries_run`: sem dizer o que foi "
                "procurado, 'não achei' não é refazível")
        if not claim.sources_examined:
            problems.append(
                "no_evidence_located exige `sources_examined`: sem dizer onde "
                "se procurou, a ausência não tem escopo")
        if not (claim.reason or "").strip():
            problems.append(
                "no_evidence_located exige `reason`: por que nenhuma conclusão "
                "foi possível")
        if not (claim.next_verification_method or "").strip():
            problems.append(
                "no_evidence_located exige `next_verification_method`: uma "
                "ausência sem próximo passo é uma pendência que ninguém sabe "
                "como fechar")

    if claim.status == REQUIRES_FIELD and not claim.requires_field:
        problems.append(
            "requires_field=True é obrigatório quando o status é "
            "'requires_field' — a contradição entre os dois campos esconderia "
            "o item da fila de campo")

    if claim.status == BLOCKED and not (claim.reason or "").strip():
        problems.append("blocked exige `reason`: qual pré-condição falta")

    return problems


def validate_transition(before: Any, after: Any,
                        new_evidence: Any = ()) -> list[str]:
    """A mudança de estado é legítima?

    A transição vigiada é `no_evidence_located -> contradicted`: reclassificar
    uma ausência como refutação sem medir nada é exatamente o defeito que este
    módulo existe para impedir. `proven` tem a mesma exigência, pela mesma
    razão — os dois afirmam sobre o mundo.
    """
    problems: list[str] = []
    if before not in EVIDENCE_STATUSES:
        problems.append("estado anterior %r fora do vocabulário" % (before,))
    if after not in EVIDENCE_STATUSES:
        problems.append("estado novo %r fora do vocabulário" % (after,))
    if problems:
        return problems

    if before == after:
        return []

    evidencias = list(new_evidence or ())
    if before in _NON_ASSERTIVE and after in _ASSERTIVE and not evidencias:
        problems.append(
            "transição %r -> %r sem evidência nova: ausência de evidência não "
            "vira afirmação por reclassificação. Meça, e cite o que mediu"
            % (before, after))

    if before == CONTRADICTED and after == PROVEN and not evidencias:
        problems.append(
            "transição contradicted -> proven sem evidência nova: a refutação "
            "anterior continua valendo até que algo a derrube")

    return problems


def require_status(raw: Any) -> str:
    """`normalize_status` para quem prefere exceção a lista de problemas."""
    status, problems = normalize_status(raw)
    if status is None:
        raise EvidenceStatusError("; ".join(problems))
    return status


@dataclass
class ClaimRegister:
    """Coleção de afirmações, com a contagem que o relatório publica.

    Existe para que um consolidador não precise recontar à mão — e para que a
    contagem de `no_evidence_located` seja visível em vez de diluída.
    """

    claims: list[EvidenceClaim] = field(default_factory=list)

    def add(self, claim: EvidenceClaim) -> list[str]:
        problems = validate_claim(claim)
        if not problems:
            self.claims.append(claim)
        return problems

    def count_by_status(self) -> dict[str, int]:
        return {status: sum(1 for c in self.claims if c.status == status)
                for status in EVIDENCE_STATUSES}

    def requiring_field(self) -> list[EvidenceClaim]:
        return [c for c in self.claims
                if c.requires_field or c.status == REQUIRES_FIELD]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "count_by_status": self.count_by_status(),
            "requiring_field": len(self.requiring_field()),
            "claims": [c.to_dict() for c in self.claims],
        }

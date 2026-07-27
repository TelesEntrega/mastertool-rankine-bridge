"""Camada de resposta em linguagem natural FUNDAMENTADA nas evidências já
produzidas por `query.py`/`query_intent.py`.

Este módulo NÃO é outro parser (reutiliza `parse_query_intent` tal como
está) nem introduz IA/inferência/embeddings/geração livre — a resposta é uma
representação PREVISÍVEL e determinística dos dados já retornados por
`find_symbol`/`find_reads`/`find_writes`/`find_calls`/`find_callers`,
montada por templates de string fixos.

Fluxo:

    pergunta controlada -> parse_query_intent() [query_intent.py] ->
    find_*() [query.py] -> QueryAnswer (ESTE módulo)

`answer_query` é uma função PURA (sem IO — `bundle` já vem carregado pelo
chamador via `load_query_bundle`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mastertool_bridge.indexer.query import (
    QueryIndexBundle,
    QueryResult,
    find_calls,
    find_callers,
    find_reads,
    find_symbol,
    find_writes,
)
from mastertool_bridge.indexer.query_intent import QueryIntent, parse_query_intent
from mastertool_bridge.indexer.symbol_resolver import owner_node_id_from_node_id

SCHEMA_VERSION = 1

_DISPATCH = {
    "find_symbol": find_symbol,
    "find_reads": find_reads,
    "find_writes": find_writes,
    "find_calls": find_calls,
    "find_callers": find_callers,
}

# Tabela FIXA QueryResult.status -> QueryAnswer.status (ver contrato).
_RESULT_STATUS_TO_ANSWER_STATUS: dict[str, str] = {
    "resolved": "answered",
    "found": "answered",
    "partially_resolved": "answered",
    "ambiguous": "ambiguous",
    "unresolved": "not_found",
    "not_found": "not_found",
}


@dataclass
class QueryAnswer:
    schema_version: int
    question: str
    status: str
    intent: dict[str, Any]
    summary: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "question": self.question,
            "status": self.status,
            "intent": self.intent,
            "summary": self.summary,
            "evidence": self.evidence,
            "limitations": self.limitations,
        }


# ---------------------------------------------------------------------------
# helpers de derivação de pou_name / localização
# ---------------------------------------------------------------------------


def _pou_name_for_entry(bundle: QueryIndexBundle, entry: dict[str, Any]) -> str | None:
    """Deriva `pou_name` a partir de `entry["node_id"]`, via
    `owner_node_id_from_node_id` + `bundle.symbol_index.pou_by_node_id`.
    Retorna None quando não é possível derivar (nunca lança)."""
    node_id = entry.get("node_id")
    if not node_id:
        return None
    owner_node_id = owner_node_id_from_node_id(node_id)
    pou = bundle.symbol_index.pou_by_node_id(owner_node_id)
    if pou is not None:
        return pou.name
    return None


def _location_str(entry: dict[str, Any]) -> str:
    file_ = entry.get("file")
    line = entry.get("line")
    column = entry.get("column")
    if file_ and line is not None and column is not None:
        return f"{file_}:{line}:{column}"
    return "(localização não disponível)"


def _build_evidence_entry(
    bundle: QueryIndexBundle,
    entry: dict[str, Any],
    *,
    name: str | None = None,
) -> dict[str, Any]:
    """Constrói UMA entrada de evidência do `QueryAnswer` a partir de uma
    entrada crua de evidência de `QueryResult` (nunca inventa valor para um
    campo ausente — usa None quando indisponível)."""
    pou_name = entry.get("pou_name")
    if pou_name is None:
        pou_name = _pou_name_for_entry(bundle, entry)

    out: dict[str, Any] = {
        "pou_name": pou_name,
        "file": entry.get("file"),
        "line": entry.get("line"),
        "column": entry.get("column"),
        "name": name if name is not None else entry.get("name") or entry.get("variable_name"),
        "resolved_symbol": entry.get("resolved_symbol"),
        "resolution_state": entry.get("resolution_state"),
        "confidence": entry.get("confidence"),
    }
    if entry.get("rule_applied") is not None:
        out["rule_applied"] = entry["rule_applied"]
    if entry.get("classification") is not None:
        out["classification"] = entry["classification"]
    if entry.get("callee") is not None:
        out["callee"] = entry["callee"]
    return out


# ---------------------------------------------------------------------------
# intent.status != "matched"
# ---------------------------------------------------------------------------


def _answer_for_unmatched_intent(question: str, intent: QueryIntent) -> QueryAnswer:
    target = intent.target

    if intent.status == "ambiguous":
        summary = (
            f"Não é possível determinar automaticamente se {target} deve ser tratado "
            "como leitura, escrita, ou ambos. Especifique 'leituras de "
            f"{target}' ou 'escritas de {target}'."
        )
        return QueryAnswer(
            schema_version=SCHEMA_VERSION,
            question=question,
            status="ambiguous",
            intent=intent.to_dict(),
            summary=summary,
            evidence=[],
            limitations=[],
        )

    if intent.status == "unsupported":
        if intent.reason == "explanation_or_reasoning_question_out_of_scope":
            summary = (
                "Esta pergunta pede uma explicação/raciocínio sobre a lógica do "
                "programa, o que está fora do escopo desta consulta determinística "
                "(apenas symbol/reads/writes/calls/callers são suportadas)."
            )
        elif intent.reason == "no_recognized_pattern":
            summary = (
                "Nenhum dos padrões de pergunta reconhecidos correspondeu ao texto "
                "informado. Reformule usando um dos formatos suportados (ex. "
                "'find symbol X', 'onde X é escrito?', 'o que X chama?', 'quem chama X?')."
            )
        else:
            summary = f"Pergunta fora do escopo suportado ({intent.reason})."
        return QueryAnswer(
            schema_version=SCHEMA_VERSION,
            question=question,
            status="unsupported",
            intent=intent.to_dict(),
            summary=summary,
            evidence=[],
            limitations=[],
        )

    # intent.status == "invalid"
    if intent.reason == "empty_input":
        summary = "A pergunta está vazia. Informe um texto com uma pergunta válida."
    elif intent.reason == "missing_target":
        summary = (
            "A pergunta não informa um alvo (nome de símbolo/POU) para consultar."
        )
    elif intent.reason == "multiple_questions_in_single_input":
        summary = (
            "Foram identificadas múltiplas perguntas coladas em uma única entrada. "
            "Informe apenas uma pergunta por vez."
        )
    else:
        summary = f"Entrada inválida ({intent.reason})."
    return QueryAnswer(
        schema_version=SCHEMA_VERSION,
        question=question,
        status="invalid",
        intent=intent.to_dict(),
        summary=summary,
        evidence=[],
        limitations=[],
    )


# ---------------------------------------------------------------------------
# SYMBOL
# ---------------------------------------------------------------------------


def _answer_symbol(
    bundle: QueryIndexBundle, question: str, intent: QueryIntent, result: QueryResult
) -> QueryAnswer:
    target = intent.target
    evidence: list[dict[str, Any]] = []
    limitations: list[str] = []

    if result.status == "resolved":
        entry = result.evidence[0]
        pou_name = entry.get("pou_name")
        if pou_name is None:
            pou_name = _pou_name_for_entry(bundle, entry)
        location = _location_str(entry)
        if entry.get("variable_name") is not None or entry.get("rule_applied") in (
            "declared_variable_scan",
            "local_variable",
            "pou_parameter",
            "gvl_implicit",
        ):
            summary = (
                f"{target} foi resolvido como variável da POU {pou_name}. "
                f"Declaração: {location}"
            )
        elif entry.get("pou_kind") is not None:
            summary = (
                f"{target} foi resolvido como {entry['pou_kind']} ({pou_name}). "
                f"Declaração: {location}"
            )
        else:
            summary = (
                f"{target} foi resolvido como variável da POU {pou_name}. "
                f"Declaração: {location}"
            )
        evidence = [_build_evidence_entry(bundle, entry, name=target)]

    elif result.status == "ambiguous":
        summary = (
            f"{target} corresponde a {result.count} símbolos e não pode ser "
            "escolhido automaticamente."
        )
        evidence = [_build_evidence_entry(bundle, e, name=target) for e in result.evidence]

    elif result.status == "partially_resolved":
        entry = result.evidence[0]
        resolved_prefix = entry.get("resolved_prefix")
        unresolved_suffix = entry.get("unresolved_suffix")
        reason = entry.get("reason")
        summary = f"{target} foi parcialmente resolvido até '{resolved_prefix}'."
        limitations = [
            f"A referência foi resolvida apenas até {resolved_prefix}. O membro "
            f"'{unresolved_suffix}' não pôde ser comprovado ({reason})."
        ]
        evidence = [_build_evidence_entry(bundle, entry, name=target)]

    else:  # unresolved
        summary = (
            f"Nenhum símbolo chamado '{target}' foi encontrado nos índices disponíveis."
        )
        evidence = []

    answer_status = _RESULT_STATUS_TO_ANSWER_STATUS.get(result.status, "not_found")
    return QueryAnswer(
        schema_version=SCHEMA_VERSION,
        question=question,
        status=answer_status,
        intent=intent.to_dict(),
        summary=summary,
        evidence=evidence,
        limitations=limitations,
    )


# ---------------------------------------------------------------------------
# READS / WRITES
# ---------------------------------------------------------------------------


def _answer_reads_writes(
    bundle: QueryIndexBundle,
    question: str,
    intent: QueryIntent,
    result: QueryResult,
    *,
    is_reads: bool,
) -> QueryAnswer:
    target = intent.target
    kind_word = "leitura" if is_reads else "escrita"
    evidence: list[dict[str, Any]] = []
    limitations: list[str] = []

    if result.status == "found":
        summary = f"{target} possui {result.count} ocorrências classificadas como {kind_word}."
        for idx, entry in enumerate(result.evidence, start=1):
            built = _build_evidence_entry(bundle, entry, name=target)
            built["ordinal"] = idx
            built["display"] = f"{idx}. {built['pou_name']} — {_location_str(entry)}"
            evidence.append(built)
        for entry in result.evidence:
            if entry.get("resolution_state") == "partially_resolved":
                resolved_prefix = entry.get("resolved_prefix")
                unresolved_suffix = entry.get("unresolved_suffix")
                reason = entry.get("reason")
                limitations.append(
                    f"A referência foi resolvida apenas até {resolved_prefix}. O membro "
                    f"'{unresolved_suffix}' não pôde ser comprovado ({reason})."
                )
    else:  # not_found
        summary = (
            f"Nenhuma ocorrência de {kind_word} de '{target}' foi encontrada no "
            "índice disponível."
        )

    answer_status = _RESULT_STATUS_TO_ANSWER_STATUS.get(result.status, "not_found")
    return QueryAnswer(
        schema_version=SCHEMA_VERSION,
        question=question,
        status=answer_status,
        intent=intent.to_dict(),
        summary=summary,
        evidence=evidence,
        limitations=limitations,
    )


# ---------------------------------------------------------------------------
# CALLS
# ---------------------------------------------------------------------------


def _answer_calls(
    bundle: QueryIndexBundle, question: str, intent: QueryIntent, result: QueryResult
) -> QueryAnswer:
    target = intent.target
    evidence: list[dict[str, Any]] = []
    limitations: list[str] = []

    if result.status == "resolved":
        pou_name = target
        if result.evidence:
            derived = _pou_name_for_entry(bundle, result.evidence[0])
            if derived is not None:
                pou_name = derived
        if result.count == 0:
            summary = f"{pou_name} não realiza nenhuma chamada registrada no índice."
            if result.note:
                limitations.append(result.note)
        else:
            summary = f"{pou_name} realiza {result.count} chamadas:"
            for entry in result.evidence:
                built = _build_evidence_entry(bundle, entry, name=entry.get("callee"))
                callee = entry.get("callee")
                if entry.get("resolution_state") == "resolved":
                    built["display"] = f"- {callee}"
                elif entry.get("resolution_state") == "ambiguous":
                    built["display"] = f"- {callee} — destino ambíguo no índice do projeto"
                else:
                    built["display"] = (
                        f"- {callee} — destino não resolvido no índice do projeto"
                    )
                evidence.append(built)

    elif result.status == "ambiguous":
        summary = (
            f"{target} corresponde a {len({e.get('candidate_node_id') for e in result.evidence})} "
            "símbolos e não pode ser escolhido automaticamente."
        )
        # Conta real de candidatos distintos (agrupamento por candidato).
        candidate_ids = []
        seen = set()
        for e in result.evidence:
            cid = e.get("candidate_node_id")
            if cid not in seen:
                seen.add(cid)
                candidate_ids.append(cid)
        summary = (
            f"{target} corresponde a {len(candidate_ids)} símbolos e não pode ser "
            "escolhido automaticamente."
        )
        for entry in result.evidence:
            evidence.append(_build_evidence_entry(bundle, entry, name=entry.get("callee")))

    else:  # unresolved
        summary = f"Nenhuma POU chamada '{target}' foi encontrada nos índices disponíveis."

    answer_status = _RESULT_STATUS_TO_ANSWER_STATUS.get(result.status, "not_found")
    return QueryAnswer(
        schema_version=SCHEMA_VERSION,
        question=question,
        status=answer_status,
        intent=intent.to_dict(),
        summary=summary,
        evidence=evidence,
        limitations=limitations,
    )


# ---------------------------------------------------------------------------
# CALLERS
# ---------------------------------------------------------------------------


def _answer_callers(
    bundle: QueryIndexBundle, question: str, intent: QueryIntent, result: QueryResult
) -> QueryAnswer:
    target = intent.target
    evidence: list[dict[str, Any]] = []
    limitations: list[str] = []

    if result.status == "resolved":
        if result.count == 0:
            summary = f"Nenhum chamador de {target} foi encontrado nos índices disponíveis."
            if result.note:
                limitations.append(result.note)
        elif result.count == 1:
            entry = result.evidence[0]
            caller_pou_name = _pou_name_for_entry(bundle, entry)
            summary = f"{target} é chamado por {caller_pou_name}."
            evidence = [_build_evidence_entry(bundle, entry, name=target)]
        else:
            summary = f"{target} é chamado por {result.count} POUs:"
            for entry in result.evidence:
                built = _build_evidence_entry(bundle, entry, name=target)
                caller_pou_name = built["pou_name"]
                built["display"] = f"- {caller_pou_name} — {_location_str(entry)}"
                evidence.append(built)

    elif result.status == "ambiguous":
        candidate_ids = []
        seen = set()
        for e in result.evidence:
            cid = e.get("candidate_node_id")
            if cid not in seen:
                seen.add(cid)
                candidate_ids.append(cid)
        summary = (
            f"{target} corresponde a {len(candidate_ids)} símbolos e não pode ser "
            "escolhido automaticamente."
        )
        for entry in result.evidence:
            evidence.append(_build_evidence_entry(bundle, entry, name=target))

    else:  # unresolved
        summary = f"Nenhuma POU chamada '{target}' foi encontrada nos índices disponíveis."

    answer_status = _RESULT_STATUS_TO_ANSWER_STATUS.get(result.status, "not_found")
    if result.status == "resolved" and result.count == 1:
        evidence = [_build_evidence_entry(bundle, result.evidence[0], name=target)]
    return QueryAnswer(
        schema_version=SCHEMA_VERSION,
        question=question,
        status=answer_status,
        intent=intent.to_dict(),
        summary=summary,
        evidence=evidence,
        limitations=limitations,
    )


# ---------------------------------------------------------------------------
# answer_query (entrypoint)
# ---------------------------------------------------------------------------


def answer_query(question: str, bundle: QueryIndexBundle) -> QueryAnswer:
    """Função PURA (sem IO): `question` -> `parse_query_intent` ->
    (se matched) despacha para `find_*` -> `QueryAnswer` fundamentado nas
    evidências. Se `intent.status != "matched"`, NENHUMA das 5 funções
    `find_*` é chamada."""
    intent = parse_query_intent(question)

    if intent.status != "matched":
        return _answer_for_unmatched_intent(question, intent)

    fn = _DISPATCH[intent.operation]
    result = fn(bundle, intent.target)

    if intent.operation == "find_symbol":
        return _answer_symbol(bundle, question, intent, result)
    if intent.operation == "find_reads":
        return _answer_reads_writes(bundle, question, intent, result, is_reads=True)
    if intent.operation == "find_writes":
        return _answer_reads_writes(bundle, question, intent, result, is_reads=False)
    if intent.operation == "find_calls":
        return _answer_calls(bundle, question, intent, result)
    if intent.operation == "find_callers":
        return _answer_callers(bundle, question, intent, result)

    # Defensivo: operação desconhecida (não deveria ocorrer -- query_intent.py
    # só produz as 5 operações conhecidas quando status=="matched").
    return QueryAnswer(
        schema_version=SCHEMA_VERSION,
        question=question,
        status="error",
        intent=intent.to_dict(),
        summary=f"Operação desconhecida: {intent.operation!r}.",
        evidence=[],
        limitations=[],
    )


# ---------------------------------------------------------------------------
# format_answer_human_readable
# ---------------------------------------------------------------------------


def format_answer_human_readable(answer: QueryAnswer) -> str:
    """Deriva a saída legível do MESMO objeto `QueryAnswer` usado para o
    JSON -- mesma fonte de fatos, formatos diferentes."""
    lines = [f"status={answer.status}", answer.summary, ""]

    if answer.evidence:
        for idx, entry in enumerate(answer.evidence, start=1):
            display = entry.get("display")
            if display:
                lines.append(display)
                continue
            pou_name = entry.get("pou_name")
            file_ = entry.get("file")
            line = entry.get("line")
            column = entry.get("column")
            location = f"{file_}:{line}:{column}" if file_ else "(sem localização)"
            state = entry.get("resolution_state")
            confidence = entry.get("confidence")
            lines.append(f"{idx}. {pou_name} — {location} | {state} ({confidence})")

    if answer.limitations:
        lines.append("")
        lines.append("Limitações:")
        for limitation in answer.limitations:
            lines.append(f"- {limitation}")

    return "\n".join(lines)

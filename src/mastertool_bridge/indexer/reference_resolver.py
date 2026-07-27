"""Resolução de símbolo + classificação read/write de `Reference`
(references.json -> resolved-references.json).

Para cada `Reference` já extraída sintaticamente (`context` gravado pelo
`statement_parser`), esta fatia:

  1. resolve o identificador (`name`) contra o `ProjectSymbolIndex`, usando
     a mesma prioridade de níveis de `symbol_resolver.py` (a POU "atual" é
     deduzida do node_id da própria Reference: "<owner_node_id>#stmtN");
  2. classifica a referência como read/write/read_write/not_applicable,
     seguindo regras fixas por `context`, cruzando com `CallArgument.operator`
     (via `resolved-calls.json` já calculado) quando `context ==
     "call_argument_value"`.

`build_read_write_index` consome o resultado de `resolve_references` e
produz um segundo artefato, agregado POR SÍMBOLO (não por ocorrência como
`resolved-references.json`) -> `read-write-index.json`.

Nunca lança exceção; toda ambiguidade/limitação vira diagnóstico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mastertool_bridge.indexer.call_resolver import ResolvedCall
from mastertool_bridge.indexer.diagnostics import DiagnosticsCollector
from mastertool_bridge.indexer.models import Reference
from mastertool_bridge.indexer.symbol_resolver import (
    ProjectSymbolIndex,
    owner_node_id_from_node_id,
    resolve_dotted_reference,
)

# Classificação fixa por contexto sintático (ver statement_parser.py para os
# valores possíveis de `context`). "call_argument_value" NÃO está aqui:
# depende do operador do CallArgument correspondente, resolvido à parte.
_CONTEXT_CLASSIFICATION: dict[str, str] = {
    "assignment_target": "write",
    "assignment_value": "read",
    "condition": "read",
    "for_loop_bound": "read",
    "call_callee": "not_applicable",
}

_OPERATOR_CLASSIFICATION: dict[str, str] = {
    ":=": "read",
    "=>": "write",
}


@dataclass
class ResolvedReference:
    reference: Reference
    resolution_state: str
    resolved_symbol: str | None
    classification: str
    candidates: list[str] = field(default_factory=list)
    rule_applied: str = "none"
    resolved_prefix: str | None = None
    """Preenchido quando `resolution_state == "partially_resolved"`: texto
    do prefixo da cadeia já confirmado (ex. "GVL_Processo.InstanciaFB")."""
    unresolved_suffix: str | None = None
    """Preenchido quando `resolution_state == "partially_resolved"`: texto
    do(s) segmento(s) restante(s) que não puderam ser confirmados."""
    reason: str | None = None
    """Preenchido quando `resolution_state == "partially_resolved"`: motivo
    textual pelo qual o sufixo não pôde ser confirmado."""

    def to_dict(self) -> dict[str, Any]:
        data = self.reference.to_dict()
        data["resolution_state"] = self.resolution_state
        data["resolved_symbol"] = self.resolved_symbol
        data["candidates"] = list(self.candidates)
        data["classification"] = self.classification
        data["rule_applied"] = self.rule_applied
        if self.resolution_state == "partially_resolved":
            data["resolved_prefix"] = self.resolved_prefix
            data["unresolved_suffix"] = self.unresolved_suffix
            data["reason"] = self.reason
        return data


def _call_argument_lookup(
    resolved_calls: list[ResolvedCall],
) -> dict[tuple[str, str, int, int], tuple[str | None, ResolvedCall]]:
    """Monta um índice (node_id, arg_name_or_empty, line, col) -> (operator,
    ResolvedCall) a partir dos argumentos de cada chamada resolvida, para
    permitir cruzar uma Reference de contexto "call_argument_value" com o
    CallArgument original (mesmo node_id + mesma location, único jeito de
    juntar os dois dados sem alterar os modelos existentes)."""
    lookup: dict[tuple[str, str, int, int], tuple[str | None, ResolvedCall]] = {}
    for rc in resolved_calls:
        for arg in rc.call.arguments:
            key = (
                rc.call.node_id,
                arg.name or "",
                arg.location.line,
                arg.location.column,
            )
            lookup[key] = (arg.operator, rc)
    return lookup


def _formal_param_is_var_in_out(
    rc: ResolvedCall, arg_name: str | None, index: ProjectSymbolIndex
) -> bool:
    """Verifica se o parâmetro formal (pelo NOME do argumento nomeado)
    corresponde a um VAR_IN_OUT do FB/FUNCTION chamado — só possível quando
    a chamada foi resolvida o suficiente para conhecer o PouSymbol alvo."""
    if rc.resolution_state != "resolved" or rc.resolved_symbol is None:
        return False
    if not arg_name:
        return False
    target = index.pou_by_node_id(rc.resolved_symbol)
    if target is None:
        return False
    for var in target.variables:
        if var.name == arg_name:
            return "VAR_IN_OUT" in var.scope.upper()
    return False


def resolve_references(
    references: list[Reference],
    index: ProjectSymbolIndex,
    resolved_calls: list[ResolvedCall],
) -> tuple[list[ResolvedReference], DiagnosticsCollector]:
    diags = DiagnosticsCollector()
    arg_lookup = _call_argument_lookup(resolved_calls)
    resolved: list[ResolvedReference] = []

    for ref in references:
        owner_node_id = owner_node_id_from_node_id(ref.node_id)
        owner_pou = index.pou_by_node_id(owner_node_id)

        symbol_ref = resolve_dotted_reference(ref.name, owner_pou, index)

        classification, class_rule = _classify(ref, symbol_ref.rule_applied, arg_lookup, index)

        rule_applied = (
            f"{symbol_ref.rule_applied}+{class_rule}"
            if class_rule
            else symbol_ref.rule_applied
        )

        rr = ResolvedReference(
            reference=ref,
            resolution_state=symbol_ref.state,
            resolved_symbol=symbol_ref.resolved_symbol,
            classification=classification,
            candidates=list(symbol_ref.candidates),
            rule_applied=rule_applied,
            resolved_prefix=symbol_ref.resolved_prefix,
            unresolved_suffix=symbol_ref.unresolved_suffix,
            reason=symbol_ref.reason,
        )
        resolved.append(rr)

        if symbol_ref.state == "ambiguous":
            diags.warning(
                "ambiguous_reference",
                symbol_ref.message
                or f"Referência a {ref.name!r} é ambígua.",
                ref.location,
                ref.node_id,
            )
        elif symbol_ref.state == "partially_resolved":
            diags.info(
                "partially_resolved_reference",
                symbol_ref.message
                or (
                    f"Referência a {ref.name!r}: prefixo "
                    f"{symbol_ref.resolved_prefix!r} confirmado, mas "
                    f"{symbol_ref.unresolved_suffix!r} não pôde ser "
                    "confirmado."
                ),
                ref.location,
                ref.node_id,
            )
        elif symbol_ref.state == "unresolved":
            diags.info(
                "unresolved_reference",
                symbol_ref.message
                or f"Referência a {ref.name!r} não pôde ser resolvida.",
                ref.location,
                ref.node_id,
            )

    resolved.sort(
        key=lambda rr: (
            rr.reference.node_id,
            rr.reference.location.line,
            rr.reference.location.column,
        )
    )
    return resolved, diags


def _classify(
    ref: Reference,
    resolution_rule: str,
    arg_lookup: dict[tuple[str, str, int, int], tuple[str | None, ResolvedCall]],
    index: ProjectSymbolIndex,
) -> tuple[str, str]:
    """Retorna (classification, rule_suffix)."""
    if ref.context in _CONTEXT_CLASSIFICATION:
        rule = "assignment_operator" if ref.context in (
            "assignment_target",
            "assignment_value",
        ) else ref.context
        return _CONTEXT_CLASSIFICATION[ref.context], rule

    if ref.context == "call_argument_value":
        # Tenta casar por (node_id, nome_ou_vazio, linha, coluna). Como
        # múltiplos argumentos posicionais têm name=None, casamos primeiro
        # por posição exata (linha/coluna), que é única por argumento.
        match = None
        for (node_id, _arg_name, line, col), value in arg_lookup.items():
            if (
                node_id == ref.node_id
                and line == ref.location.line
                and col == ref.location.column
            ):
                match = value
                break
        if match is None:
            # Referência dentro de um argumento composto (ex. expressão
            # "Foo(1) + 1" cujo argumento não bate exatamente na location) —
            # sem operador conhecido, aplica leitura como default seguro
            # (valor sendo passado é sempre ao menos lido para formar a
            # expressão), mas sinaliza a limitação via rule.
            return "read", "call_argument_value_operator_unknown"

        operator, rc = match
        base_classification = _OPERATOR_CLASSIFICATION.get(operator or ":=", "read")

        # VAR_IN_OUT sobrescreve a regra do operador, mas só quando o
        # parâmetro formal puder ser resolvido pelo NOME do argumento.
        arg_name = None
        for (node_id, name_key, line, col), value in arg_lookup.items():
            if (
                node_id == ref.node_id
                and line == ref.location.line
                and col == ref.location.column
                and value is match
            ):
                arg_name = name_key or None
                break
        if arg_name and _formal_param_is_var_in_out(rc, arg_name, index):
            return "read_write", "var_in_out_resolved"

        return base_classification, "call_argument_operator"

    # Contexto desconhecido (não deveria ocorrer com o modelo atual, mas
    # nunca lança): sem classificação.
    return "not_applicable", "unknown_context"


def build_symbol_index(symbols) -> ProjectSymbolIndex:
    return ProjectSymbolIndex(symbols)


_UNRESOLVED_KEY = "_unresolved"

# Chaves de classificação agregadas por símbolo em read-write-index.json.
# "not_applicable" (ex. call_callee) e "unknown_context" não representam
# leitura nem escrita de dado, então não geram uma lista própria aqui — a
# referência ainda aparece no resolved-references.json completo, apenas não
# é indexada por read/write/read_write neste artefato agregado.
_RW_BUCKETS = ("reads", "writes", "read_write")
_CLASSIFICATION_TO_BUCKET = {
    "read": "reads",
    "write": "writes",
    "read_write": "read_write",
}


def _rw_entry(rr: ResolvedReference) -> dict[str, Any]:
    ref = rr.reference
    return {
        "node_id": ref.node_id,
        "file": ref.file,
        "name": ref.name,
        "location": ref.location.to_dict(),
    }


def build_read_write_index(
    resolved_references: list[ResolvedReference],
) -> dict[str, Any]:
    """Agrega `resolved_references` (já calculado por `resolve_references`)
    POR SÍMBOLO resolvido, separando as ocorrências em `reads`/`writes`/
    `read_write` — artefato DISTINTO de `resolved-references.json` (que é
    uma lista plana por ocorrência): este índice responde diretamente a
    perguntas como "onde X é escrito" sem varrer a lista inteira.

    Referências sem `resolved_symbol` (resolution_state != "resolved", ou
    resolved mas sem node_id de símbolo concreto, ex. `type_reference` sem
    PouSymbol) são agrupadas à parte na chave `"_unresolved"`, para nunca
    serem perdidas silenciosamente. Referências com classificação que não é
    read/write/read_write (ex. `not_applicable` de `call_callee`) não geram
    entrada em nenhum bucket deste símbolo (o dado completo continua em
    resolved-references.json).

    Uma referência `resolution_state == "partially_resolved"` (cadeia
    pontuada de 3+ segmentos onde só um PREFIXO foi confirmado, ex.
    "GVL_Processo.InstanciaFB" de "GVL_Processo.InstanciaFB.Estado" com
    "Estado" não confirmado) É agregada normalmente sob o símbolo do
    prefixo confirmado (não cai em "_unresolved"), desde que
    `resolved_symbol` tenha sido preenchido pela resolução -- o critério
    aqui é puramente a presença de `resolved_symbol`, não o
    `resolution_state` em si.

    Saída determinística: chaves de símbolo em ordem alfabética, listas de
    cada bucket ordenadas por (node_id, line, column).
    """
    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    unresolved: list[dict[str, Any]] = []

    for rr in resolved_references:
        bucket = _CLASSIFICATION_TO_BUCKET.get(rr.classification)
        if rr.resolved_symbol is None:
            if bucket is not None:
                unresolved.append(_rw_entry(rr))
            continue
        if bucket is None:
            continue
        symbol_entry = index.setdefault(
            rr.resolved_symbol, {b: [] for b in _RW_BUCKETS}
        )
        symbol_entry[bucket].append(_rw_entry(rr))

    def _sort_key(entry: dict[str, Any]) -> tuple[str, int, int]:
        loc = entry["location"]
        return (entry["node_id"], loc["line"], loc["column"])

    result: dict[str, Any] = {}
    for symbol_node_id in sorted(index):
        buckets = index[symbol_node_id]
        result[symbol_node_id] = {
            b: sorted(buckets[b], key=_sort_key) for b in _RW_BUCKETS
        }

    unresolved.sort(key=_sort_key)
    result[_UNRESOLVED_KEY] = unresolved

    return result

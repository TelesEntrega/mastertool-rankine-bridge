"""Testes de mastertool_bridge.indexer.reference_resolver."""

from __future__ import annotations

from mastertool_bridge.indexer.call_resolver import resolve_calls
from mastertool_bridge.indexer.models import (
    Call,
    CallArgument,
    PouSymbol,
    Reference,
    SourceLocation,
    VariableDeclaration,
)
from mastertool_bridge.indexer.reference_resolver import (
    build_read_write_index,
    resolve_references,
)
from mastertool_bridge.indexer.symbol_resolver import ProjectSymbolIndex


def _loc(line: int = 1, col: int = 1) -> SourceLocation:
    return SourceLocation(file="f.st", line=line, column=col)


def _var(name: str, declared_type: str, scope: str) -> VariableDeclaration:
    return VariableDeclaration(name=name, declared_type=declared_type, scope=scope)


def _ref(node_id: str, name: str, context: str, line: int = 1, col: int = 1) -> Reference:
    return Reference(node_id=node_id, file="f.st", name=name, context=context, location=_loc(line, col))


def test_assignment_target_classified_as_write() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("x", "BOOL", "VAR")],
    )
    index = ProjectSymbolIndex([prg])
    ref = _ref("application/prg/0#stmt0", "x", "assignment_target")

    resolved, _diags = resolve_references([ref], index, [])

    assert resolved[0].classification == "write"
    assert resolved[0].resolution_state == "resolved"
    assert resolved[0].resolved_symbol == "application/prg/0"


def test_assignment_value_classified_as_read() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("y", "BOOL", "VAR")],
    )
    index = ProjectSymbolIndex([prg])
    ref = _ref("application/prg/0#stmt0", "y", "assignment_value")

    resolved, _diags = resolve_references([ref], index, [])

    assert resolved[0].classification == "read"


def test_condition_classified_as_read() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("z", "BOOL", "VAR")],
    )
    index = ProjectSymbolIndex([prg])
    ref = _ref("application/prg/0#stmt0", "z", "condition")

    resolved, _diags = resolve_references([ref], index, [])

    assert resolved[0].classification == "read"


def test_for_loop_bound_classified_as_read() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("i", "INT", "VAR")],
    )
    index = ProjectSymbolIndex([prg])
    ref = _ref("application/prg/0#stmt0", "i", "for_loop_bound")

    resolved, _diags = resolve_references([ref], index, [])

    assert resolved[0].classification == "read"


def test_call_callee_is_not_applicable_never_read_or_write() -> None:
    prg = PouSymbol(
        node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st", variables=[]
    )
    index = ProjectSymbolIndex([prg])
    ref = _ref("application/prg/0#stmt0", "SomeCallee", "call_callee")

    resolved, _diags = resolve_references([ref], index, [])

    assert resolved[0].classification == "not_applicable"


def test_call_argument_with_assign_operator_classified_as_read() -> None:
    func = PouSymbol(
        node_id="application/fun/0",
        pou_kind="FUNCTION",
        name="FunCalc",
        file="f.st",
        variables=[_var("IN_VALOR", "REAL", "VAR_INPUT")],
    )
    index = ProjectSymbolIndex([func])

    arg = CallArgument(name="IN_VALOR", operator=":=", value_raw="x", location=_loc(2, 5))
    call = Call(
        node_id="application/prg/0#stmt0",
        file="f.st",
        callee="FunCalc",
        arguments=[arg],
        location=_loc(2, 1),
    )
    resolved_calls, _cdiags = resolve_calls([call], index)

    ref = _ref("application/prg/0#stmt0", "x", "call_argument_value", line=2, col=5)
    resolved, _diags = resolve_references([ref], index, resolved_calls)

    assert resolved[0].classification == "read"
    assert "call_argument_operator" in resolved[0].rule_applied


def test_call_argument_with_output_operator_classified_as_write() -> None:
    func = PouSymbol(
        node_id="application/fun/0",
        pou_kind="FUNCTION",
        name="FunCalc",
        file="f.st",
        variables=[_var("OUT_VALOR", "REAL", "VAR_OUTPUT")],
    )
    index = ProjectSymbolIndex([func])

    arg = CallArgument(name="OUT_VALOR", operator="=>", value_raw="y", location=_loc(3, 5))
    call = Call(
        node_id="application/prg/0#stmt0",
        file="f.st",
        callee="FunCalc",
        arguments=[arg],
        location=_loc(3, 1),
    )
    resolved_calls, _cdiags = resolve_calls([call], index)

    ref = _ref("application/prg/0#stmt0", "y", "call_argument_value", line=3, col=5)
    resolved, _diags = resolve_references([ref], index, resolved_calls)

    assert resolved[0].classification == "write"


def test_var_in_out_argument_classified_as_read_write_overriding_operator() -> None:
    """VAR_IN_OUT deve virar read_write mesmo quando o operador usado foi
    ':=' (a regra do parâmetro formal SOBRESCREVE a regra do operador)."""
    fb = PouSymbol(
        node_id="application/fb/0",
        pou_kind="FUNCTION_BLOCK",
        name="FB_Timer",
        file="f.st",
        variables=[_var("tPreset", "TIME", "VAR_IN_OUT")],
    )
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("fbTimer", "FB_Timer", "VAR"), _var("tMyTime", "TIME", "VAR")],
    )
    index = ProjectSymbolIndex([fb, prg])

    arg = CallArgument(name="tPreset", operator=":=", value_raw="tMyTime", location=_loc(4, 10))
    call = Call(
        node_id="application/prg/0#stmt0",
        file="f.st",
        callee="fbTimer",
        arguments=[arg],
        location=_loc(4, 1),
    )
    resolved_calls, _cdiags = resolve_calls([call], index)
    assert resolved_calls[0].resolution_state == "resolved"

    ref = _ref("application/prg/0#stmt0", "tMyTime", "call_argument_value", line=4, col=10)
    resolved, _diags = resolve_references([ref], index, resolved_calls)

    assert resolved[0].classification == "read_write"
    assert "var_in_out_resolved" in resolved[0].rule_applied


def test_var_in_out_rule_not_forced_when_call_unresolved() -> None:
    """Se a chamada não foi resolvida o suficiente para saber o parâmetro
    formal, aplica só a regra do operador — nunca força read_write sem
    evidência."""
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("tMyTime", "TIME", "VAR")],
    )
    index = ProjectSymbolIndex([prg])

    arg = CallArgument(name="tPreset", operator=":=", value_raw="tMyTime", location=_loc(5, 10))
    call = Call(
        node_id="application/prg/0#stmt0",
        file="f.st",
        callee="Fantasma",
        arguments=[arg],
        location=_loc(5, 1),
    )
    resolved_calls, _cdiags = resolve_calls([call], index)
    assert resolved_calls[0].resolution_state == "unresolved"

    ref = _ref("application/prg/0#stmt0", "tMyTime", "call_argument_value", line=5, col=10)
    resolved, _diags = resolve_references([ref], index, resolved_calls)

    # Sem informação suficiente sobre o parâmetro formal -> regra do
    # operador (":=" -> read), NUNCA read_write forçado sem evidência.
    assert resolved[0].classification == "read"


def test_unresolved_identifier_never_silently_becomes_a_symbol() -> None:
    """Garantia central: um identificador que não bate com nada retorna
    resolution_state='unresolved' e resolved_symbol=None, nunca um
    palpite."""
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("x", "BOOL", "VAR")],
    )
    index = ProjectSymbolIndex([prg])
    ref = _ref("application/prg/0#stmt0", "NomeQueNaoExisteEmLugarNenhum", "assignment_value")

    resolved, diags = resolve_references([ref], index, [])

    assert resolved[0].resolution_state == "unresolved"
    assert resolved[0].resolved_symbol is None
    assert resolved[0].candidates == []
    assert any(d.code == "unresolved_reference" for d in diags.diagnostics)


def test_ambiguous_reference_never_picks_a_candidate() -> None:
    gvl1 = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="GvlA",
        file="f.st",
        variables=[_var("Shared", "INT", "VAR_GLOBAL")],
        is_qualified_only=False,
    )
    gvl2 = PouSymbol(
        node_id="application/gvl/1",
        pou_kind="GVL",
        name="GvlB",
        file="f.st",
        variables=[_var("Shared", "INT", "VAR_GLOBAL")],
        is_qualified_only=False,
    )
    index = ProjectSymbolIndex([gvl1, gvl2])
    ref = _ref("application/prg/0#stmt0", "Shared", "condition")

    resolved, diags = resolve_references([ref], index, [])

    assert resolved[0].resolution_state == "ambiguous"
    assert resolved[0].resolved_symbol is None
    assert set(resolved[0].candidates) == {"application/gvl/0", "application/gvl/1"}
    assert any(d.code == "ambiguous_reference" for d in diags.diagnostics)


def test_read_write_index_aggregates_mixed_reads_and_writes_by_symbol() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("x", "BOOL", "VAR")],
    )
    index = ProjectSymbolIndex([prg])
    refs = [
        _ref("application/prg/0#stmt0", "x", "assignment_target", line=1, col=1),
        _ref("application/prg/0#stmt1", "x", "assignment_value", line=2, col=5),
        _ref("application/prg/0#stmt2", "x", "condition", line=3, col=1),
    ]

    resolved, _diags = resolve_references(refs, index, [])
    rw_index = build_read_write_index(resolved)

    assert "application/prg/0" in rw_index
    entry = rw_index["application/prg/0"]
    assert [w["node_id"] for w in entry["writes"]] == ["application/prg/0#stmt0"]
    assert {r["node_id"] for r in entry["reads"]} == {
        "application/prg/0#stmt1",
        "application/prg/0#stmt2",
    }
    assert entry["read_write"] == []


def test_read_write_index_var_in_out_goes_to_read_write_bucket() -> None:
    fb = PouSymbol(
        node_id="application/fb/0",
        pou_kind="FUNCTION_BLOCK",
        name="FB_Timer",
        file="f.st",
        variables=[_var("tPreset", "TIME", "VAR_IN_OUT")],
    )
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("fbTimer", "FB_Timer", "VAR"), _var("tMyTime", "TIME", "VAR")],
    )
    index = ProjectSymbolIndex([fb, prg])

    arg = CallArgument(name="tPreset", operator=":=", value_raw="tMyTime", location=_loc(4, 10))
    call = Call(
        node_id="application/prg/0#stmt0",
        file="f.st",
        callee="fbTimer",
        arguments=[arg],
        location=_loc(4, 1),
    )
    resolved_calls, _cdiags = resolve_calls([call], index)

    ref = _ref("application/prg/0#stmt0", "tMyTime", "call_argument_value", line=4, col=10)
    resolved, _diags = resolve_references([ref], index, resolved_calls)
    rw_index = build_read_write_index(resolved)

    entry = rw_index["application/prg/0"]
    assert len(entry["read_write"]) == 1
    assert entry["read_write"][0]["name"] == "tMyTime"
    assert entry["reads"] == []
    assert entry["writes"] == []


def test_read_write_index_puts_unresolved_reference_in_separate_key() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("x", "BOOL", "VAR")],
    )
    index = ProjectSymbolIndex([prg])
    refs = [
        _ref("application/prg/0#stmt0", "x", "assignment_target", line=1, col=1),
        _ref(
            "application/prg/0#stmt1",
            "NomeQueNaoExisteEmLugarNenhum",
            "assignment_value",
            line=2,
            col=1,
        ),
    ]

    resolved, _diags = resolve_references(refs, index, [])
    rw_index = build_read_write_index(resolved)

    assert "_unresolved" in rw_index
    assert len(rw_index["_unresolved"]) == 1
    assert rw_index["_unresolved"][0]["name"] == "NomeQueNaoExisteEmLugarNenhum"
    # A referência resolvida NÃO aparece na chave de unresolved.
    assert all(e["name"] != "x" for e in rw_index["_unresolved"])


def test_read_write_index_deterministic_output() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("a", "BOOL", "VAR"), _var("b", "BOOL", "VAR")],
    )
    index = ProjectSymbolIndex([prg])
    refs = [
        _ref("application/prg/0#stmt1", "b", "assignment_target", line=5, col=1),
        _ref("application/prg/0#stmt0", "a", "assignment_target", line=1, col=1),
        _ref("application/prg/0#stmt0", "a", "assignment_value", line=1, col=10),
    ]

    resolved, _diags = resolve_references(refs, index, [])

    rw_index_1 = build_read_write_index(resolved)
    rw_index_2 = build_read_write_index(list(reversed(resolved)))

    assert rw_index_1 == rw_index_2
    assert list(rw_index_1.keys()) == ["application/prg/0", "_unresolved"]
    writes = rw_index_1["application/prg/0"]["writes"]
    assert [(w["node_id"], w["location"]["line"], w["location"]["column"]) for w in writes] == [
        ("application/prg/0#stmt0", 1, 1),
        ("application/prg/0#stmt1", 5, 1),
    ]


def test_output_sorted_deterministically_by_node_id_then_position() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("a", "BOOL", "VAR"), _var("b", "BOOL", "VAR")],
    )
    index = ProjectSymbolIndex([prg])
    refs = [
        _ref("application/prg/0#stmt1", "b", "assignment_target", line=5, col=1),
        _ref("application/prg/0#stmt0", "a", "assignment_target", line=1, col=1),
    ]

    resolved, _diags = resolve_references(refs, index, [])

    assert [rr.reference.node_id for rr in resolved] == [
        "application/prg/0#stmt0",
        "application/prg/0#stmt1",
    ]

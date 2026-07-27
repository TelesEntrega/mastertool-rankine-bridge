"""Testes de mastertool_bridge.indexer.call_resolver."""

from __future__ import annotations

from mastertool_bridge.indexer.call_resolver import build_callers_index, resolve_calls
from mastertool_bridge.indexer.models import Call, PouSymbol, SourceLocation, VariableDeclaration
from mastertool_bridge.indexer.symbol_resolver import ProjectSymbolIndex


def _loc(line: int = 1, col: int = 1) -> SourceLocation:
    return SourceLocation(file="f.st", line=line, column=col)


def _var(name: str, declared_type: str, scope: str) -> VariableDeclaration:
    return VariableDeclaration(name=name, declared_type=declared_type, scope=scope)


def test_resolves_call_to_fb_instance() -> None:
    fb_type = PouSymbol(
        node_id="application/fb/0", pou_kind="FUNCTION_BLOCK", name="FB_Timer", file="f.st"
    )
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("fbTimer", "FB_Timer", "VAR")],
    )
    index = ProjectSymbolIndex([fb_type, prg])

    call = Call(node_id="application/prg/0#stmt0", file="f.st", callee="fbTimer", location=_loc())
    resolved, diags = resolve_calls([call], index)

    assert len(resolved) == 1
    rc = resolved[0]
    assert rc.resolution_state == "resolved"
    assert rc.resolved_symbol == "application/fb/0"
    assert rc.rule_applied == "fb_instance"
    assert not diags.has_errors


def test_resolves_call_to_function_direct() -> None:
    func = PouSymbol(
        node_id="application/fun/0", pou_kind="FUNCTION", name="FunCalc", file="f.st"
    )
    index = ProjectSymbolIndex([func])

    call = Call(node_id="application/prg/0#stmt0", file="f.st", callee="FunCalc", location=_loc())
    resolved, _diags = resolve_calls([call], index)

    assert resolved[0].resolution_state == "resolved"
    assert resolved[0].resolved_symbol == "application/fun/0"
    assert resolved[0].rule_applied == "function_direct"


def test_resolves_call_to_program_direct() -> None:
    """PROGRAM-to-PROGRAM: no dialeto CODESYS uma PROGRAM chama outra
    PROGRAM diretamente pelo NOME, sem variável de instância local (padrão
    real confirmado no export do projeto: MainPrg chama StartPrg())."""
    called_prg = PouSymbol(
        node_id="application/prg/1", pou_kind="PROGRAM", name="StartPrg", file="f.st"
    )
    caller_prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[],
    )
    index = ProjectSymbolIndex([called_prg, caller_prg])

    call = Call(node_id="application/prg/0#stmt0", file="f.st", callee="StartPrg", location=_loc())
    resolved, diags = resolve_calls([call], index)

    assert len(resolved) == 1
    rc = resolved[0]
    assert rc.resolution_state == "resolved"
    assert rc.resolved_symbol == "application/prg/1"
    assert rc.rule_applied == "program_direct"
    assert not diags.has_errors


def test_ambiguous_when_multiple_programs_share_name() -> None:
    prg1 = PouSymbol(node_id="application/prg/1", pou_kind="PROGRAM", name="StartPrg", file="f.st")
    prg2 = PouSymbol(node_id="application/prg/2", pou_kind="PROGRAM", name="StartPrg", file="f.st")
    caller_prg = PouSymbol(
        node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st", variables=[]
    )
    index = ProjectSymbolIndex([prg1, prg2, caller_prg])

    call = Call(node_id="application/prg/0#stmt0", file="f.st", callee="StartPrg", location=_loc())
    resolved, diags = resolve_calls([call], index)

    assert resolved[0].resolution_state == "ambiguous"
    assert set(resolved[0].candidates) == {"application/prg/1", "application/prg/2"}
    assert resolved[0].rule_applied == "program_direct"
    assert any(d.code == "ambiguous_call_target" for d in diags.diagnostics)


def test_program_direct_call_appears_in_callers_index() -> None:
    called_prg = PouSymbol(
        node_id="application/prg/1", pou_kind="PROGRAM", name="StartPrg", file="f.st"
    )
    caller_prg = PouSymbol(
        node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st", variables=[]
    )
    index = ProjectSymbolIndex([called_prg, caller_prg])

    call = Call(node_id="application/prg/0#stmt0", file="f.st", callee="StartPrg", location=_loc(1, 1))
    resolved, _diags = resolve_calls([call], index)

    callers = build_callers_index(resolved)

    assert set(callers) == {"application/prg/1"}
    sites = callers["application/prg/1"]
    assert len(sites) == 1
    assert sites[0]["callee"] == "StartPrg"
    assert sites[0]["rule_applied"] == "program_direct"


def test_method_call_with_resolved_instance_is_never_resolved_but_ambiguous() -> None:
    """Instância resolvida, mas método não verificável neste modelo de
    dados -> resultado NUNCA "resolved" para o callee completo."""
    fb_type = PouSymbol(
        node_id="application/fb/0", pou_kind="FUNCTION_BLOCK", name="FB_Timer", file="f.st"
    )
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("fbTimer", "FB_Timer", "VAR")],
    )
    index = ProjectSymbolIndex([fb_type, prg])

    call = Call(
        node_id="application/prg/0#stmt1", file="f.st", callee="fbTimer.Reset", location=_loc()
    )
    resolved, diags = resolve_calls([call], index)

    rc = resolved[0]
    assert rc.resolution_state in ("ambiguous", "unresolved")
    assert rc.resolution_state != "resolved"
    assert rc.candidates == ["application/fb/0"]
    assert any(d.code == "unverifiable_method_call" for d in diags.diagnostics)


def test_method_call_with_unknown_instance_is_unresolved() -> None:
    prg = PouSymbol(
        node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st", variables=[]
    )
    index = ProjectSymbolIndex([prg])

    call = Call(
        node_id="application/prg/0#stmt0",
        file="f.st",
        callee="Desconhecido.Metodo",
        location=_loc(),
    )
    resolved, diags = resolve_calls([call], index)

    assert resolved[0].resolution_state == "unresolved"
    assert resolved[0].resolved_symbol is None
    assert any(d.code == "unresolved_call_target" for d in diags.diagnostics)


def test_unknown_callee_is_unresolved_never_a_guess() -> None:
    index = ProjectSymbolIndex([])
    call = Call(node_id="application/prg/0#stmt0", file="f.st", callee="Fantasma", location=_loc())

    resolved, _diags = resolve_calls([call], index)

    assert resolved[0].resolution_state == "unresolved"
    assert resolved[0].resolved_symbol is None
    assert resolved[0].candidates == []


def test_ambiguous_when_multiple_function_blocks_share_type_name() -> None:
    fb1 = PouSymbol(node_id="application/fb/0", pou_kind="FUNCTION_BLOCK", name="FB_X", file="f.st")
    fb2 = PouSymbol(node_id="application/fb/1", pou_kind="FUNCTION_BLOCK", name="FB_X", file="f.st")
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("inst", "FB_X", "VAR")],
    )
    index = ProjectSymbolIndex([fb1, fb2, prg])

    call = Call(node_id="application/prg/0#stmt0", file="f.st", callee="inst", location=_loc())
    resolved, diags = resolve_calls([call], index)

    assert resolved[0].resolution_state == "ambiguous"
    assert set(resolved[0].candidates) == {"application/fb/0", "application/fb/1"}
    assert any(d.code == "ambiguous_call_target" for d in diags.diagnostics)


def test_build_callers_index_only_includes_resolved_calls() -> None:
    fb_type = PouSymbol(
        node_id="application/fb/0", pou_kind="FUNCTION_BLOCK", name="FB_Timer", file="f.st"
    )
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("fbTimer", "FB_Timer", "VAR")],
    )
    index = ProjectSymbolIndex([fb_type, prg])

    resolved_call = Call(
        node_id="application/prg/0#stmt0", file="f.st", callee="fbTimer", location=_loc(1, 1)
    )
    unresolved_call = Call(
        node_id="application/prg/0#stmt1", file="f.st", callee="Fantasma", location=_loc(2, 1)
    )
    resolved, _diags = resolve_calls([resolved_call, unresolved_call], index)

    callers = build_callers_index(resolved)

    assert set(callers) == {"application/fb/0"}
    sites = callers["application/fb/0"]
    assert len(sites) == 1
    assert sites[0]["node_id"] == "application/prg/0#stmt0"
    assert sites[0]["callee"] == "fbTimer"

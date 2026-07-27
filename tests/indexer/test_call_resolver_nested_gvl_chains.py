"""Testes de extensão: `call_resolver._resolve_method_call` usando a
resolução generalizada de cadeia pontuada para o PREFIXO de uma chamada de
método (commit "feat: resolve nested GVL instance member references").

O ÚLTIMO segmento do callee é sempre o método/função chamado, tratado como
"unverifiable" (nunca "resolved" para a chamada completa) -- mesma
honestidade já aprovada antes para instâncias locais, agora também para
prefixos GVL-qualificados de 2+ segmentos."""

from __future__ import annotations

from mastertool_bridge.indexer.call_resolver import resolve_calls
from mastertool_bridge.indexer.models import Call, PouSymbol, SourceLocation, VariableDeclaration
from mastertool_bridge.indexer.symbol_resolver import ProjectSymbolIndex


def _loc(line: int = 1, col: int = 1) -> SourceLocation:
    return SourceLocation(file="f.st", line=line, column=col)


def _var(name: str, declared_type: str, scope: str = "VAR_GLOBAL") -> VariableDeclaration:
    return VariableDeclaration(name=name, declared_type=declared_type, scope=scope)


def test_gvl_qualified_method_call_prefix_resolved_but_call_never_resolved() -> None:
    fb_type = PouSymbol(
        node_id="app/fb/0", pou_kind="FUNCTION_BLOCK", name="FB_Equip", file="f.st"
    )
    gvl = PouSymbol(
        node_id="app/gvl/0",
        pou_kind="GVL",
        name="GVL_A",
        file="f.st",
        variables=[_var("Instancia", "FB_Equip")],
        is_qualified_only=True,
    )
    index = ProjectSymbolIndex([fb_type, gvl])

    call = Call(
        node_id="app/prg/0#stmt0",
        file="f.st",
        callee="GVL_A.Instancia.Metodo",
        location=_loc(),
    )
    resolved, diags = resolve_calls([call], index)

    rc = resolved[0]
    assert rc.resolution_state != "resolved"
    assert rc.resolution_state in ("ambiguous", "unresolved")
    assert rc.candidates == ["app/fb/0"]
    assert any(d.code == "unverifiable_method_call" for d in diags.diagnostics)


def test_gvl_qualified_method_call_with_three_segment_prefix() -> None:
    """Prefixo de 3 segmentos ("GVL_A.Instancia.Subestrutura"), onde
    "Subestrutura" é membro de outro FB conhecido -- o método chamado é
    sempre o ÚLTIMO segmento."""
    inner_fb = PouSymbol(
        node_id="app/fb/1", pou_kind="FUNCTION_BLOCK", name="FB_Sub", file="f.st"
    )
    outer_fb = PouSymbol(
        node_id="app/fb/0",
        pou_kind="FUNCTION_BLOCK",
        name="FB_Equip",
        file="f.st",
        variables=[_var("Subestrutura", "FB_Sub", scope="VAR")],
    )
    gvl = PouSymbol(
        node_id="app/gvl/0",
        pou_kind="GVL",
        name="GVL_A",
        file="f.st",
        variables=[_var("Instancia", "FB_Equip")],
        is_qualified_only=True,
    )
    index = ProjectSymbolIndex([inner_fb, outer_fb, gvl])

    call = Call(
        node_id="app/prg/0#stmt0",
        file="f.st",
        callee="GVL_A.Instancia.Subestrutura.Metodo",
        location=_loc(),
    )
    resolved, diags = resolve_calls([call], index)

    rc = resolved[0]
    assert rc.resolution_state != "resolved"
    assert rc.candidates == ["app/fb/1"]


def test_gvl_qualified_method_call_unknown_instance_is_unresolved() -> None:
    gvl = PouSymbol(
        node_id="app/gvl/0",
        pou_kind="GVL",
        name="GVL_A",
        file="f.st",
        variables=[_var("OutraVar", "DINT")],
        is_qualified_only=True,
    )
    index = ProjectSymbolIndex([gvl])

    call = Call(
        node_id="app/prg/0#stmt0",
        file="f.st",
        callee="GVL_A.InstanciaQueNaoExiste.Metodo",
        location=_loc(),
    )
    resolved, diags = resolve_calls([call], index)

    assert resolved[0].resolution_state == "unresolved"
    assert resolved[0].resolved_symbol is None


def test_gvl_qualified_method_call_unknown_gvl_is_unresolved() -> None:
    index = ProjectSymbolIndex([])

    call = Call(
        node_id="app/prg/0#stmt0",
        file="f.st",
        callee="GvlQueNaoExiste.Instancia.Metodo",
        location=_loc(),
    )
    resolved, _diags = resolve_calls([call], index)

    assert resolved[0].resolution_state == "unresolved"


def test_local_instance_method_call_still_never_resolved_non_regression() -> None:
    fb_type = PouSymbol(
        node_id="app/fb/0", pou_kind="FUNCTION_BLOCK", name="FB_Timer", file="f.st"
    )
    prg = PouSymbol(
        node_id="app/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("fbTimer", "FB_Timer", scope="VAR")],
    )
    index = ProjectSymbolIndex([fb_type, prg])

    call = Call(
        node_id="app/prg/0#stmt0", file="f.st", callee="fbTimer.Reset", location=_loc()
    )
    resolved, diags = resolve_calls([call], index)

    rc = resolved[0]
    assert rc.resolution_state != "resolved"
    assert rc.candidates == ["app/fb/0"]


def test_library_call_with_dotted_namespace_stays_unresolved_non_regression() -> None:
    index = ProjectSymbolIndex([])

    call = Call(
        node_id="app/prg/0#stmt0",
        file="f.st",
        callee="SysTimeCore.SysTimeGetUs",
        location=_loc(),
    )
    resolved, _diags = resolve_calls([call], index)

    assert resolved[0].resolution_state == "unresolved"
    assert resolved[0].resolved_symbol is None

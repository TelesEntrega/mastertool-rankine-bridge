"""Testes de extensão: propagação do estado "partially_resolved" (com
resolved_prefix/unresolved_suffix/reason) e da resolução generalizada de
cadeia em `reference_resolver.resolve_references` / `build_read_write_index`
(commit "feat: resolve nested GVL instance member references")."""

from __future__ import annotations

from mastertool_bridge.indexer.models import PouSymbol, Reference, SourceLocation, VariableDeclaration
from mastertool_bridge.indexer.reference_resolver import (
    build_read_write_index,
    resolve_references,
)
from mastertool_bridge.indexer.symbol_resolver import ProjectSymbolIndex


def _loc(line: int = 1, col: int = 1) -> SourceLocation:
    return SourceLocation(file="f.st", line=line, column=col)


def _var(name: str, declared_type: str, scope: str = "VAR_GLOBAL") -> VariableDeclaration:
    return VariableDeclaration(name=name, declared_type=declared_type, scope=scope)


def _ref(node_id: str, name: str, context: str, line: int = 1, col: int = 1) -> Reference:
    return Reference(node_id=node_id, file="f.st", name=name, context=context, location=_loc(line, col))


def test_three_segment_gvl_chain_resolved_and_classified() -> None:
    fb_type = PouSymbol(
        node_id="app/fb/0",
        pou_kind="FUNCTION_BLOCK",
        name="FB_Equip",
        file="f.st",
        variables=[_var("Estado", "BOOL", scope="VAR")],
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
    ref = _ref("app/prg/0#stmt0", "GVL_A.Instancia.Estado", "assignment_value")

    resolved, _diags = resolve_references([ref], index, [])

    assert resolved[0].resolution_state == "resolved"
    assert resolved[0].resolved_symbol == "app/fb/0"
    assert resolved[0].classification == "read"


def test_partially_resolved_reference_carries_prefix_suffix_reason() -> None:
    fb_type = PouSymbol(
        node_id="app/fb/0",
        pou_kind="FUNCTION_BLOCK",
        name="FB_Equip",
        file="f.st",
        variables=[_var("Estado", "BOOL", scope="VAR")],
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
    ref = _ref("app/prg/0#stmt0", "GVL_A.Instancia.MembroQueNaoExiste", "assignment_value")

    resolved, diags = resolve_references([ref], index, [])
    rr = resolved[0]

    assert rr.resolution_state == "partially_resolved"
    assert rr.resolved_prefix == "GVL_A.Instancia"
    assert rr.unresolved_suffix == "MembroQueNaoExiste"
    assert rr.reason == "member metadata unavailable"
    assert rr.resolved_symbol == "app/fb/0"
    assert any(d.code == "partially_resolved_reference" for d in diags.diagnostics)


def test_partially_resolved_reference_to_dict_includes_new_fields() -> None:
    gvl = PouSymbol(
        node_id="app/gvl/0",
        pou_kind="GVL",
        name="GVL_A",
        file="f.st",
        variables=[_var("Temporizador", "TON")],
        is_qualified_only=True,
    )
    index = ProjectSymbolIndex([gvl])
    ref = _ref("app/prg/0#stmt0", "GVL_A.Temporizador.Q", "assignment_value")

    resolved, _diags = resolve_references([ref], index, [])
    data = resolved[0].to_dict()

    assert data["resolution_state"] == "partially_resolved"
    assert data["resolved_prefix"] == "GVL_A.Temporizador"
    assert data["unresolved_suffix"] == "Q"
    assert "reason" in data


def test_resolved_reference_to_dict_omits_partial_fields_when_not_partial() -> None:
    prg = PouSymbol(
        node_id="app/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("x", "BOOL", scope="VAR")],
    )
    index = ProjectSymbolIndex([prg])
    ref = _ref("app/prg/0#stmt0", "x", "assignment_target")

    resolved, _diags = resolve_references([ref], index, [])
    data = resolved[0].to_dict()

    assert "resolved_prefix" not in data
    assert "unresolved_suffix" not in data
    assert "reason" not in data


def test_read_write_index_aggregates_partially_resolved_under_confirmed_prefix() -> None:
    """read-write-index.json não deve perder a referência parcialmente
    resolvida em "_unresolved" quando um prefixo confirmado existe -- deve
    aparecer sob o símbolo do prefixo (FB_Equip), permitindo agregação
    útil mesmo sem confirmar o membro final."""
    fb_type = PouSymbol(
        node_id="app/fb/0",
        pou_kind="FUNCTION_BLOCK",
        name="FB_Equip",
        file="f.st",
        variables=[_var("Estado", "BOOL", scope="VAR")],
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
    ref = _ref(
        "app/prg/0#stmt0",
        "GVL_A.Instancia.MembroQueNaoExiste",
        "assignment_value",
        line=1,
        col=1,
    )

    resolved, _diags = resolve_references([ref], index, [])
    rw_index = build_read_write_index(resolved)

    assert "app/fb/0" in rw_index
    assert [r["name"] for r in rw_index["app/fb/0"]["reads"]] == [
        "GVL_A.Instancia.MembroQueNaoExiste"
    ]
    assert all(e["name"] != "GVL_A.Instancia.MembroQueNaoExiste" for e in rw_index["_unresolved"])


def test_unverifiable_external_library_reference_stays_in_unresolved_bucket() -> None:
    index = ProjectSymbolIndex([])
    ref = _ref("app/prg/0#stmt0", "SysTimeCore.SysTimeGetUs", "call_callee")

    resolved, _diags = resolve_references([ref], index, [])

    assert resolved[0].resolution_state == "unresolved"
    assert resolved[0].resolved_symbol is None

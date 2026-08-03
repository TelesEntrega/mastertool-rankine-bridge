"""Testes de mastertool_bridge.indexer.gvl_parser."""

from __future__ import annotations

from mastertool_bridge.indexer.gvl_parser import parse_gvl_declaration


def test_gvl_with_qualified_only_pragma_sets_flag() -> None:
    text = """{attribute 'qualified_only'}
VAR_GLOBAL
END_VAR
VAR_GLOBAL RETAIN
    MT01: Motor;
    MT02: Motor;
END_VAR
VAR_GLOBAL
    MT03: Motor;
END_VAR
"""
    symbol, diags = parse_gvl_declaration(text, "f.st", "n1", "GvlMotores")

    assert symbol is not None
    assert symbol.pou_kind == "GVL"
    assert symbol.name == "GvlMotores"
    assert symbol.is_qualified_only is True
    assert not diags.has_errors


def test_gvl_without_qualified_only_pragma_flag_is_false() -> None:
    text = """VAR_GLOBAL
    DG_Contador : DINT;
END_VAR
"""
    symbol, diags = parse_gvl_declaration(text, "f.st", "n2", "GvlSemPragma")

    assert symbol is not None
    assert symbol.is_qualified_only is False
    assert not diags.has_errors


def test_gvl_concatenates_variables_from_multiple_var_global_blocks() -> None:
    text = """{attribute 'qualified_only'}
VAR_GLOBAL
END_VAR
VAR_GLOBAL RETAIN
    MT01: Motor;
    MT02: Motor;
END_VAR
VAR_GLOBAL
    MT03: Motor;
END_VAR
"""
    symbol, diags = parse_gvl_declaration(text, "f.st", "n3", "GvlMotores")

    assert symbol is not None
    names = [v.name for v in symbol.variables]
    assert names == ["MT01", "MT02", "MT03"]
    scopes = {v.name: v.scope for v in symbol.variables}
    assert scopes["MT01"] == "VAR_GLOBAL RETAIN"
    assert scopes["MT03"] == "VAR_GLOBAL"
    assert not diags.has_errors


def test_gvl_variable_with_hardware_address_captured() -> None:
    text = """VAR_GLOBAL
    DG_Sensor AT %IW12 : INT;
    DG_Contador : DINT;
END_VAR
"""
    symbol, diags = parse_gvl_declaration(text, "f.st", "n4", "GvlDiag")

    assert symbol is not None
    by_name = {v.name: v for v in symbol.variables}
    assert by_name["DG_Sensor"].hardware_address == "%IW12"
    assert by_name["DG_Contador"].hardware_address is None
    assert not diags.has_errors


def test_gvl_empty_var_global_block_generates_no_diagnostic() -> None:
    text = """{attribute 'qualified_only'}
VAR_GLOBAL
END_VAR
"""
    symbol, diags = parse_gvl_declaration(text, "f.st", "n5", "GvlVazia")

    assert symbol is not None
    assert symbol.variables == []
    assert diags.diagnostics == []


def test_gvl_pou_kind_is_always_gvl() -> None:
    text = "VAR_GLOBAL\n    x : BOOL;\nEND_VAR\n"
    symbol, _diags = parse_gvl_declaration(text, "f.st", "n6", "GvlQualquer")

    assert symbol is not None
    assert symbol.pou_kind == "GVL"


def test_file_without_any_var_global_is_not_treated_as_gvl() -> None:
    # Um DUT (TYPE ... STRUCT ... END_STRUCT ... END_TYPE) não é GVL nem
    # POU — não deve ser rotulado como GVL só por não ter cabeçalho de POU.
    text = "TYPE Motor :\nSTRUCT\n    Ligado : BOOL;\nEND_STRUCT\nEND_TYPE\n"
    symbol, diags = parse_gvl_declaration(text, "f.st", "n7", "Motor")

    assert symbol is None
    assert any(d.code == "gvl_header_not_found" for d in diags.diagnostics)

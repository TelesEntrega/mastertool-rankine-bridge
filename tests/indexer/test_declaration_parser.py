"""Testes de mastertool_bridge.indexer.declaration_parser."""

from __future__ import annotations

from mastertool_bridge.indexer.declaration_parser import parse_declaration


def test_program_simple() -> None:
    text = """PROGRAM MainPrg
VAR
    xStart : BOOL;
    xStop  : BOOL;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n1")

    assert symbol is not None
    assert symbol.pou_kind == "PROGRAM"
    assert symbol.name == "MainPrg"
    assert [v.name for v in symbol.variables] == ["xStart", "xStop"]
    assert not diags.has_errors


def test_function_block_with_input_output_var() -> None:
    text = """FUNCTION_BLOCK FbTeste
VAR_INPUT
    xIn : BOOL;
END_VAR
VAR_OUTPUT
    xOut : BOOL;
END_VAR
VAR
    tTimer : TON;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n2")

    assert symbol is not None
    assert symbol.pou_kind == "FUNCTION_BLOCK"
    scopes = {v.name: v.scope for v in symbol.variables}
    assert scopes["xIn"] == "VAR_INPUT"
    assert scopes["xOut"] == "VAR_OUTPUT"
    assert scopes["tTimer"] == "VAR"
    assert not diags.has_errors


def test_function_with_return_type() -> None:
    text = """FUNCTION FunSoma : INT
VAR_INPUT
    iA : INT;
    iB : INT;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n3")

    assert symbol is not None
    assert symbol.pou_kind == "FUNCTION"
    assert symbol.return_type == "INT"
    assert not diags.has_errors


def test_array_declaration() -> None:
    text = """PROGRAM PrgArray
VAR
    aiValores : ARRAY[0..9] OF INT;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n4")

    assert symbol is not None
    var = symbol.variables[0]
    assert var.name == "aiValores"
    assert var.is_array is True
    assert var.array_dimensions == [("0", "9")]
    assert "ARRAY" in var.declared_type
    assert "INT" in var.declared_type
    assert not diags.has_errors


def test_variable_with_initializer() -> None:
    text = """FUNCTION_BLOCK FbValvula
VAR_INPUT
    tTimeout : TIME := T#5S;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n5")

    assert symbol is not None
    var = symbol.variables[0]
    assert var.declared_type == "TIME"
    assert var.initializer_raw == "T#5S"
    assert not diags.has_errors


def test_var_input_constant() -> None:
    text = """FUNCTION_BLOCK FbConst
VAR_INPUT CONSTANT
    iMax : INT := 10;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n6")

    assert symbol is not None
    var = symbol.variables[0]
    assert var.is_constant is True
    assert var.scope == "VAR_INPUT CONSTANT"
    assert not diags.has_errors


def test_var_constant_block() -> None:
    text = """FUNCTION_BLOCK FbConst2
VAR CONSTANT
    iMax : INT := 5;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n7")

    assert symbol is not None
    var = symbol.variables[0]
    assert var.is_constant is True
    assert var.scope == "VAR CONSTANT"
    assert not diags.has_errors


def test_malformed_var_block_missing_end_var_generates_diagnostic_and_continues() -> None:
    text = """FUNCTION_BLOCK FbMalformado
VAR_INPUT
    xEntrada : BOOL;
VAR_OUTPUT
    xSaida : BOOL;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n8")

    # O parser não deve travar: a POU ainda é reconhecida.
    assert symbol is not None
    assert any(d.code == "unterminated_var_block" for d in diags.diagnostics)
    # O segundo bloco (VAR_OUTPUT ... END_VAR) ainda deve ser processado.
    names = [v.name for v in symbol.variables]
    assert "xSaida" in names


def test_comment_inside_var_block_not_a_false_declaration() -> None:
    text = """PROGRAM PrgComentario
VAR
    xVar : BOOL; // comentario apos ponto e virgula
    // comentario em linha propria, nao deve virar declaracao
    yVar : INT;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n9")

    assert symbol is not None
    names = [v.name for v in symbol.variables]
    assert names == ["xVar", "yVar"]
    assert not diags.has_errors


def test_missing_header_returns_none_with_diagnostic() -> None:
    text = "VAR\n    xVar : BOOL;\nEND_VAR\n"
    symbol, diags = parse_declaration(text, "f.st", node_id="n10")

    assert symbol is None
    assert any(d.code == "pou_header_not_found" for d in diags.diagnostics)


def test_extends_captured_as_raw_text() -> None:
    text = """FUNCTION_BLOCK FbFilho EXTENDS FbBase
VAR
    xVar : BOOL;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n11")

    assert symbol is not None
    assert symbol.extends == "FbBase"
    assert not diags.has_errors


def test_variable_with_hardware_address_binding() -> None:
    text = """PROGRAM PrgHw
VAR
    xSaida AT %QX54.0 : BOOL := TRUE;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n12")

    assert symbol is not None
    var = symbol.variables[0]
    assert var.name == "xSaida"
    assert var.hardware_address == "%QX54.0"
    assert var.declared_type == "BOOL"
    assert var.initializer_raw == "TRUE"
    assert not diags.has_errors


def test_variable_without_at_has_hardware_address_none() -> None:
    text = """PROGRAM PrgSemHw
VAR
    xVar : BOOL;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n13")

    assert symbol is not None
    var = symbol.variables[0]
    assert var.hardware_address is None
    assert not diags.has_errors


def test_multiple_names_with_hardware_address_is_invalid_but_tolerant() -> None:
    text = """PROGRAM PrgHwInvalido
VAR
    xA, xB AT %QX1.0 : BOOL;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n14")

    # Nunca lança exceção: best-effort, registra diagnóstico e continua.
    assert symbol is not None
    assert any(
        d.code == "invalid_multi_name_hardware_binding" for d in diags.diagnostics
    )


def test_hardware_address_with_word_size_and_no_dot() -> None:
    text = """PROGRAM PrgHwPalavra
VAR
    wValor AT %IW12 : WORD;
END_VAR
"""
    symbol, diags = parse_declaration(text, "f.st", node_id="n15")

    assert symbol is not None
    var = symbol.variables[0]
    assert var.hardware_address == "%IW12"
    assert not diags.has_errors

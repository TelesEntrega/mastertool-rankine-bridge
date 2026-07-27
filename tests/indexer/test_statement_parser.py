"""Testes de mastertool_bridge.indexer.statement_parser."""

from __future__ import annotations

import json

from mastertool_bridge.indexer.statement_parser import parse_implementation


def test_simple_assignment() -> None:
    text = "xValor := 10;"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n1")

    assert not diags.has_errors
    assert len(stmts) == 1
    assert stmts[0].kind == "assignment"
    assert calls == []
    target_refs = [r for r in refs if r.context == "assignment_target"]
    assert [r.name for r in target_refs] == ["xValor"]


def test_if_elsif_else_end_if() -> None:
    text = """IF xCond THEN
    y := 1;
ELSIF zCond THEN
    y := 2;
ELSE
    y := 3;
END_IF;
"""
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n2")

    assert not diags.has_errors
    kinds = [s.kind for s in stmts]
    assert "if" in kinds
    assert kinds.count("assignment") == 3
    condition_names = [r.name for r in refs if r.context == "condition"]
    assert "xCond" in condition_names
    assert "zCond" in condition_names


def test_case_multiple_labels_and_else() -> None:
    text = """CASE iSelector OF
    1: y := 10;
    2, 3: y := 20;
ELSE
    y := 0;
END_CASE;
"""
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n3")

    assert not diags.has_errors
    case_stmts = [s for s in stmts if s.kind == "case"]
    assert len(case_stmts) == 1
    assignment_stmts = [s for s in stmts if s.kind == "assignment"]
    assert len(assignment_stmts) == 3
    assert any(r.name == "iSelector" and r.context == "condition" for r in refs)


def test_for_to_by_do_end_for() -> None:
    text = """FOR i := 0 TO 10 BY 2 DO
    x := x + 1;
END_FOR;
"""
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n4")

    assert not diags.has_errors
    for_stmts = [s for s in stmts if s.kind == "for"]
    assert len(for_stmts) == 1
    bound_names = [r.name for r in refs if r.context == "for_loop_bound"]
    assert "i" in bound_names


def test_while_do_end_while() -> None:
    text = """WHILE xRunning DO
    x := x + 1;
END_WHILE;
"""
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n5")

    assert not diags.has_errors
    while_stmts = [s for s in stmts if s.kind == "while"]
    assert len(while_stmts) == 1
    assert any(r.name == "xRunning" and r.context == "condition" for r in refs)


def test_repeat_until_end_repeat() -> None:
    text = """REPEAT
    x := x + 1;
UNTIL x > 10
END_REPEAT;
"""
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n6")

    assert not diags.has_errors
    repeat_stmts = [s for s in stmts if s.kind == "repeat"]
    assert len(repeat_stmts) == 1
    assert any(r.name == "x" and r.context == "condition" for r in refs)


def test_return_statement() -> None:
    text = "RETURN;"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n7")

    assert not diags.has_errors
    assert len(stmts) == 1
    assert stmts[0].kind == "return"


def test_standalone_call_with_positional_args() -> None:
    text = "DoSomething(1, 2, 3);"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n8")

    assert not diags.has_errors
    assert len(calls) == 1
    call = calls[0]
    assert call.callee == "DoSomething"
    assert [a.name for a in call.arguments] == [None, None, None]
    assert [a.operator for a in call.arguments] == [None, None, None]
    assert [a.value_raw for a in call.arguments] == ["1", "2", "3"]


def test_standalone_call_with_named_args_meufb_example() -> None:
    text = """MeuFB(
    IN_VALOR := Estado_OP,
    OUT_VALOR => Estado_Aux
);
"""
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n9")

    assert not diags.has_errors
    assert len(calls) == 1
    call = calls[0]
    assert call.callee == "MeuFB"
    assert len(call.arguments) == 2
    assert call.arguments[0].name == "IN_VALOR"
    assert call.arguments[0].operator == ":="
    assert call.arguments[0].value_raw == "Estado_OP"
    assert call.arguments[1].name == "OUT_VALOR"
    assert call.arguments[1].operator == "=>"
    assert call.arguments[1].value_raw == "Estado_Aux"

    ref_names_contexts = {(r.name, r.context) for r in refs}
    assert ("MeuFB", "call_callee") in ref_names_contexts
    assert ("Estado_OP", "call_argument_value") in ref_names_contexts
    assert ("Estado_Aux", "call_argument_value") in ref_names_contexts

    # Nenhum indício de classificação de leitura/escrita ou resolução de
    # tipo/instância em NENHUM lugar da saída (statements, calls, refs).
    everything = json.dumps(
        [s.to_dict() for s in stmts]
        + [c.to_dict() for c in calls]
        + [r.to_dict() for r in refs]
    ).lower()
    for forbidden in (
        "is_read",
        "is_write",
        "read_write",
        '"read"',
        '"write"',
        "leitura",
        "escrita",
        "instance_of",
        "resolved_type",
    ):
        assert forbidden not in everything


def test_call_as_rhs_of_assignment() -> None:
    text = "resultado := Foo(a, b);"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n10")

    assert not diags.has_errors
    assert len(stmts) == 1
    assert stmts[0].kind == "assignment"
    assert len(calls) == 1
    call = calls[0]
    assert call.callee == "Foo"
    assert [a.value_raw for a in call.arguments] == ["a", "b"]

    target_refs = [r for r in refs if r.context == "assignment_target"]
    assert [r.name for r in target_refs] == ["resultado"]
    callee_refs = [r for r in refs if r.context == "call_callee"]
    assert [r.name for r in callee_refs] == ["Foo"]


def test_dotted_method_call() -> None:
    text = "Instancia.Metodo(x);"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n11")

    assert not diags.has_errors
    assert len(calls) == 1
    assert calls[0].callee == "Instancia.Metodo"
    callee_refs = [r for r in refs if r.context == "call_callee"]
    assert [r.name for r in callee_refs] == ["Instancia.Metodo"]


def test_unsupported_construct_produces_diagnostic_and_continues() -> None:
    text = "@@@ garbage ;;; xValor := 1;"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n12")

    assert any(
        d.code == "unsupported_statement_construct" for d in diags.diagnostics
    )
    # O restante do arquivo continua sendo processado.
    assignment_stmts = [s for s in stmts if s.kind == "assignment"]
    assert len(assignment_stmts) == 1


def test_unclosed_if_produces_diagnostic_and_continues() -> None:
    text = """IF xCond THEN
    y := 1;

zOutro := 2;
"""
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n13")

    assert any(d.code == "unterminated_block" for d in diags.diagnostics)
    # O corpo do IF (não fechado) ainda é capturado.
    assert any(s.kind == "assignment" for s in stmts)


def test_unclosed_case_produces_diagnostic_and_continues() -> None:
    text = """CASE x OF
1: y := 1;
"""
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n14")

    assert any(d.code == "unterminated_block" for d in diags.diagnostics)


def test_unclosed_for_produces_diagnostic_and_continues() -> None:
    text = "FOR i := 0 TO 10 DO\n x := 1;\n"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n15")

    assert any(d.code == "unterminated_block" for d in diags.diagnostics)


def test_unclosed_while_produces_diagnostic_and_continues() -> None:
    text = "WHILE xRunning DO\n y := 1;\n"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n16")

    assert any(d.code == "unterminated_block" for d in diags.diagnostics)


def test_unclosed_repeat_produces_diagnostic_and_continues() -> None:
    text = "REPEAT\n y := 1;\n"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n17")

    assert any(d.code == "unterminated_block" for d in diags.diagnostics)


def test_deterministic_output_same_fixture_twice() -> None:
    text = """MeuFB(
    IN_VALOR := Estado_OP,
    OUT_VALOR => Estado_Aux
);

resultado := Foo(a, b);

Instancia.Metodo(x);

IF xCond THEN
    y := 1;
ELSE
    y := 2;
END_IF;

CASE iSel OF
    1: y := 10;
ELSE
    y := 0;
END_CASE;

FOR i := 0 TO 10 BY 2 DO
    x := x + 1;
END_FOR;

WHILE xRunning DO
    x := x + 1;
END_WHILE;

REPEAT
    x := x + 1;
UNTIL x > 10
END_REPEAT;

RETURN;
"""
    stmts1, calls1, refs1, diags1 = parse_implementation(text, "f.st", "n18")
    stmts2, calls2, refs2, diags2 = parse_implementation(text, "f.st", "n18")

    assert [s.to_dict() for s in stmts1] == [s.to_dict() for s in stmts2]
    assert [c.to_dict() for c in calls1] == [c.to_dict() for c in calls2]
    assert [r.to_dict() for r in refs1] == [r.to_dict() for r in refs2]
    assert diags1.to_list() == diags2.to_list()


def test_nested_call_best_effort_does_not_raise() -> None:
    text = "x := Foo(Bar(1), 2);"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n19")

    # Nunca lança exceção; ao menos a chamada externa é registrada.
    assert len(calls) == 1
    assert calls[0].callee == "Foo"
    assert len(calls[0].arguments) == 2

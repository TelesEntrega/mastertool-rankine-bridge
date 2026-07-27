"""Testes de regressão: referências pontuadas (`GVL.Variavel`) capturadas
por `_scan_value_tokens_for_references` / `_scan_raw_text_for_identifiers`
em `statement_parser.py`.

Bug original: essas duas funções de varredura best-effort de referências
(usadas em condições de IF/WHILE/CASE/REPEAT, limites de FOR, RHS de
atribuição quando não é chamada pura, e valores de argumento de chamada)
reconheciam a cadeia pontuada mas descartavam os segmentos depois do
primeiro ponto, registrando a Reference só com o primeiro segmento (ex.
`VarGlobaisExemplo.NomeDaVariavel` virava `name="VarGlobaisExemplo"`). Este arquivo
cobre o fix: a cadeia pontuada completa agora vira UMA única Reference.
"""

from __future__ import annotations

from mastertool_bridge.indexer.statement_parser import parse_implementation


def test_if_condition_dotted_gvl_reference() -> None:
    text = "IF VarGlobaisExemplo.NomeDaVariavel THEN\n    y := 1;\nEND_IF;\n"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n1")

    assert not diags.has_errors
    condition_refs = [r for r in refs if r.context == "condition"]
    assert [r.name for r in condition_refs] == ["VarGlobaisExemplo.NomeDaVariavel"]


def test_assignment_rhs_dotted_gvl_reference_no_regression_on_target() -> None:
    text = "Destino := VarGlobaisExemplo.Origem;"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n2")

    assert not diags.has_errors
    target_refs = [r for r in refs if r.context == "assignment_target"]
    assert [r.name for r in target_refs] == ["Destino"]
    value_refs = [r for r in refs if r.context == "assignment_value"]
    assert [r.name for r in value_refs] == ["VarGlobaisExemplo.Origem"]


def test_for_loop_bounds_dotted_gvl_references() -> None:
    text = (
        "FOR i := VarGlobaisExemplo.Inicio TO VarGlobaisExemplo.Fim DO\n"
        "    x := x + 1;\n"
        "END_FOR;\n"
    )
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n3")

    assert not diags.has_errors
    bound_names = [
        r.name for r in refs if r.context == "for_loop_bound" and "." in r.name
    ]
    assert bound_names == ["VarGlobaisExemplo.Inicio", "VarGlobaisExemplo.Fim"]


def test_call_argument_value_dotted_gvl_reference() -> None:
    text = "MeuFB(IN_VALOR := VarGlobaisExemplo.Valor);"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n4")

    assert not diags.has_errors
    arg_refs = [r for r in refs if r.context == "call_argument_value"]
    assert [r.name for r in arg_refs] == ["VarGlobaisExemplo.Valor"]


def test_three_segment_dotted_chain_in_condition() -> None:
    text = "IF GVL_Processo.Sessao.Estado THEN\n    y := 1;\nEND_IF;\n"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n5")

    assert not diags.has_errors
    condition_refs = [r for r in refs if r.context == "condition"]
    assert [r.name for r in condition_refs] == ["GVL_Processo.Sessao.Estado"]


def test_dotted_call_no_regression_standalone() -> None:
    text = "SysTimeCore.SysTimeGetUs();"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n6")

    assert not diags.has_errors
    assert len(calls) == 1
    assert calls[0].callee == "SysTimeCore.SysTimeGetUs"
    callee_refs = [r for r in refs if r.context == "call_callee"]
    assert [r.name for r in callee_refs] == ["SysTimeCore.SysTimeGetUs"]


def test_dotted_call_no_regression_as_rhs() -> None:
    text = "resultado := Instancia.Metodo(x);"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n7")

    assert not diags.has_errors
    assert len(calls) == 1
    assert calls[0].callee == "Instancia.Metodo"
    callee_refs = [r for r in refs if r.context == "call_callee"]
    assert [r.name for r in callee_refs] == ["Instancia.Metodo"]


def test_indexed_access_produces_base_reference_and_index_reference() -> None:
    text = "Destino := GVL.ArrayValores[Indice];"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n8")

    assert not diags.has_errors
    value_refs = [r for r in refs if r.context == "assignment_value"]
    names = [r.name for r in value_refs]
    # A cadeia inteira (incluindo o índice) vira UMA Reference; o conteúdo
    # do índice ("Indice") também vira uma Reference própria e
    # independente (mesmo mecanismo de varredura recursiva).
    assert names == ["GVL.ArrayValores[Indice]", "Indice"]


def test_comment_and_string_with_dots_do_not_produce_spurious_references() -> None:
    text = (
        "// isto.tem.pontos\n"
        "Destino := 'texto.com.pontos';\n"
        "IF VarGlobaisExemplo.Real THEN // isto.tem.pontos\n"
        "    y := 1;\n"
        "END_IF;\n"
    )
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n9")

    assert not diags.has_errors
    all_names = [r.name for r in refs]
    assert not any("isto" in name for name in all_names)
    assert not any("tem" in name for name in all_names)
    condition_refs = [r for r in refs if r.context == "condition"]
    assert [r.name for r in condition_refs] == ["VarGlobaisExemplo.Real"]


def test_incomplete_dotted_name_does_not_raise() -> None:
    text = "IF GVL. THEN\n    y := 1;\nEND_IF;\n"
    # Comportamento best-effort: nunca lança exceção. Aceita tanto uma
    # Reference parcial "GVL" quanto nenhuma referência de condição —
    # o essencial é a ausência de exceção e o parser continuar.
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n10")

    assignment_stmts = [s for s in stmts if s.kind == "assignment"]
    assert len(assignment_stmts) == 1


def test_dotted_reference_location_and_end_location_positions() -> None:
    text = "IF VarGlobaisExemplo.NomeDaVariavel THEN\n    y := 1;\nEND_IF;\n"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n11")

    condition_refs = [r for r in refs if r.context == "condition"]
    assert len(condition_refs) == 1
    ref = condition_refs[0]
    assert ref.name == "VarGlobaisExemplo.NomeDaVariavel"

    # "IF VarGlobaisExemplo.NomeDaVariavel THEN" -> "VarGlobaisExemplo" começa na coluna 4
    # (1-based: I=1,F=2,' '=3,V=4...), linha 1.
    assert ref.location.line == 1
    assert ref.location.column == 4

    assert ref.end_location is not None
    # "NomeDaVariavel" comeca logo apos "VarGlobaisExemplo." -- ou seja, na coluna
    # inicial (4) mais o prefixo com o ponto. Derivado do proprio identificador em
    # vez de fixado: um numero magico aqui so diz "mudou", nunca "por que".
    assert ref.end_location.line == 1
    assert ref.end_location.column == 4 + len("VarGlobaisExemplo.")


def test_single_segment_reference_end_location_consistent() -> None:
    text = "IF xCond THEN\n    y := 1;\nEND_IF;\n"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n12")

    condition_refs = [r for r in refs if r.context == "condition"]
    assert len(condition_refs) == 1
    ref = condition_refs[0]
    assert ref.name == "xCond"
    # Referência de um único segmento: end_location, se preenchida, deve
    # ser consistente com location (mesmo token).
    if ref.end_location is not None:
        assert ref.end_location.line == ref.location.line
        assert ref.end_location.column == ref.location.column

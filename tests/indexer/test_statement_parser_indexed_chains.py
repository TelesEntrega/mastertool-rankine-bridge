"""Testes de extensão: cadeias pontuadas com índice de array NO MEIO da
cadeia (ex. `GVL_Processo.ArrayFB[i].Estado`) em `statement_parser.py`.

Antes desta extensão, a captura de nome em cadeia parava no primeiro `[`
encontrado, truncando a referência em "GVL_Processo.ArrayFB" e perdendo o
`.Estado` que vem DEPOIS do índice. Este arquivo cobre a extensão: a cadeia
pontuada agora reconhece `IDENTIFIER ('[' <índice> ']')? ('.' IDENTIFIER
('[' <índice> ']')?)*` como UMA única Reference/nome, preservando o texto
bruto do(s) índice(s) na string do nome (para exibição/depuração — a
resolução de símbolo, que decide como stripar `[i]`, é responsabilidade de
outra fase). O conteúdo de cada índice também é escaneado recursivamente
como Reference(s) própria(s) e independente(s).
"""

from __future__ import annotations

from mastertool_bridge.indexer.statement_parser import parse_implementation


def test_index_in_middle_of_chain_produces_single_reference_plus_index_reference() -> None:
    text = "Destino := GVL_A.ArrayInstancias[i].Estado;"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n1")

    assert not diags.has_errors
    value_refs = [r for r in refs if r.context == "assignment_value"]
    names = [r.name for r in value_refs]
    assert names == ["GVL_A.ArrayInstancias[i].Estado", "i"]


def test_four_segment_dotted_chain_without_index() -> None:
    text = "Destino := GVL_A.Instancia.Subestrutura.Valor;"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n2")

    assert not diags.has_errors
    value_refs = [r for r in refs if r.context == "assignment_value"]
    names = [r.name for r in value_refs]
    assert names == ["GVL_A.Instancia.Subestrutura.Valor"]


def test_index_with_arithmetic_expression_no_exception() -> None:
    text = "Destino := GVL_A.ArrayFB[i+1].Estado;"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n3")

    assert not diags.has_errors
    value_refs = [r for r in refs if r.context == "assignment_value"]
    names = [r.name for r in value_refs]
    # Nome bruto da cadeia preserva o índice sem interpretá-lo (o texto é
    # reconstruído via `_tokens_to_raw`, que normaliza espaçamento ao redor
    # de operadores — mesmo comportamento já usado em `value_raw` de
    # argumentos de chamada, não byte-a-byte do arquivo original); "i"
    # dentro do índice também aparece como Reference própria (varredura
    # recursiva do conteúdo do índice).
    assert names[0] == "GVL_A.ArrayFB[i + 1].Estado"
    assert "i" in names[1:]


def test_index_with_nested_bracket_expression_no_exception() -> None:
    text = "Destino := GVL_A.ArrayFB[Contador[j]].Estado;"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n4")

    assert not diags.has_errors
    value_refs = [r for r in refs if r.context == "assignment_value"]
    names = [r.name for r in value_refs]
    # Colchetes aninhados respeitados: o índice inteiro "Contador[j]" fica
    # preservado bruto dentro do nome da cadeia externa.
    assert names[0] == "GVL_A.ArrayFB[Contador[j]].Estado"
    # E o conteúdo do índice ("Contador[j]") é escaneado recursivamente,
    # produzindo sua própria Reference de cadeia com índice.
    assert "Contador[j]" in names[1:]


def test_unclosed_bracket_does_not_raise() -> None:
    text = "Destino := GVL_A.ArrayFB[i;"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n5")

    # Comportamento best-effort: nunca lança exceção. O parser deve
    # continuar processando (mesmo que a atribuição fique malformada).
    assert isinstance(refs, list)


def test_unclosed_bracket_at_eof_does_not_raise() -> None:
    text = "Destino := GVL_A.ArrayFB[i"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n6")

    # Sem ';' e sem ']': best-effort até EOF, sem exceção.
    assert isinstance(refs, list)


def test_index_in_middle_of_chain_locations() -> None:
    text = "Destino := GVL_A.ArrayFB[i].Estado;"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n7")

    assert not diags.has_errors
    value_refs = [r for r in refs if r.context == "assignment_value"]
    chain_refs = [r for r in value_refs if r.name.startswith("GVL_A")]
    assert len(chain_refs) == 1
    ref = chain_refs[0]

    # "Destino := GVL_A.ArrayFB[i].Estado;"
    #  1234567890123456789...
    # "GVL_A" começa na coluna 12 (1-based).
    assert ref.location.line == 1
    assert ref.location.column == 12

    # "Estado" é o último segmento; termina a referência ali.
    end_col = text.index("Estado") + 1
    assert ref.end_location is not None
    assert ref.end_location.line == 1
    assert ref.end_location.column == end_col


def test_library_call_without_index_no_regression() -> None:
    text = "SysTimeCore.SysTimeGetUs();"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n8")

    assert not diags.has_errors
    assert len(calls) == 1
    assert calls[0].callee == "SysTimeCore.SysTimeGetUs"
    callee_refs = [r for r in refs if r.context == "call_callee"]
    assert [r.name for r in callee_refs] == ["SysTimeCore.SysTimeGetUs"]


def test_index_at_end_of_chain_with_trailing_dot_after() -> None:
    text = "IF GVL_Processo.ArrayFB[i].Estado THEN\n    y := 1;\nEND_IF;\n"
    stmts, calls, refs, diags = parse_implementation(text, "f.st", "n9")

    assert not diags.has_errors
    condition_refs = [r for r in refs if r.context == "condition"]
    names = [r.name for r in condition_refs]
    assert names == ["GVL_Processo.ArrayFB[i].Estado", "i"]

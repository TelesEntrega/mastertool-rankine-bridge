"""Testes de mastertool_bridge.indexer.st_lexer."""

from __future__ import annotations

from mastertool_bridge.indexer.st_lexer import tokenize


def _kinds(tokens):
    return [t.kind for t in tokens if t.kind != "EOF"]


def _texts(tokens):
    return [t.text for t in tokens if t.kind != "EOF"]


def test_line_comment_does_not_become_symbol() -> None:
    tokens, diags = tokenize("xVar : BOOL; // isso nao e um token\n", "f.st")

    assert "isso" not in _texts(tokens)
    assert not diags.diagnostics


def test_block_comment_does_not_become_symbol() -> None:
    tokens, diags = tokenize(
        "xVar : BOOL; (* comentario\ncom quebra de linha *) yVar : INT;",
        "f.st",
    )

    texts = _texts(tokens)
    assert "comentario" not in texts
    assert "yVar" in texts
    assert not diags.diagnostics


def test_string_with_identifier_inside_not_a_false_symbol() -> None:
    tokens, diags = tokenize("sMsg := 'xVar nao e identificador';", "f.st")

    kinds_texts = list(zip(_kinds(tokens), _texts(tokens)))
    assert ("STRING", "'xVar nao e identificador'") in kinds_texts
    assert not any(k == "IDENTIFIER" and t == "xVar" for k, t in kinds_texts)
    assert not diags.diagnostics


def test_pragma_recognized_as_distinct_token() -> None:
    tokens, diags = tokenize("{attribute 'hide'} xVar : BOOL;", "f.st")

    pragma_tokens = [t for t in tokens if t.kind == "PRAGMA"]
    assert len(pragma_tokens) == 1
    assert pragma_tokens[0].text == "{attribute 'hide'}"
    assert not diags.diagnostics


def test_unterminated_string_generates_diagnostic_no_exception() -> None:
    tokens, diags = tokenize("sMsg := 'nunca fecha", "f.st")

    assert any(d.code == "unterminated_string" for d in diags.diagnostics)
    assert tokens[-1].kind == "EOF"  # tokenização concluiu normalmente


def test_unterminated_block_comment_generates_diagnostic() -> None:
    tokens, diags = tokenize("xVar : BOOL; (* nunca fecha", "f.st")

    assert any(d.code == "unterminated_block_comment" for d in diags.diagnostics)
    assert tokens[-1].kind == "EOF"


def test_numbers_and_typed_literals_recognized() -> None:
    tokens, diags = tokenize(
        "tValor := T#2S; iHex := 16#FF; iBin := 2#1010; rReal := 3.14;",
        "f.st",
    )
    kinds_texts = list(zip(_kinds(tokens), _texts(tokens)))

    assert ("TYPED_LITERAL", "T#2S") in kinds_texts
    assert ("NUMBER", "16#FF") in kinds_texts
    assert ("NUMBER", "2#1010") in kinds_texts
    assert ("NUMBER", "3.14") in kinds_texts
    assert not diags.diagnostics


def test_line_and_column_multiline() -> None:
    text = "PROGRAM Foo\nVAR\n    xVar : BOOL;\nEND_VAR\n"
    tokens, _ = tokenize(text, "f.st")

    xvar_tok = next(t for t in tokens if t.text == "xVar")
    assert xvar_tok.location.line == 3
    assert xvar_tok.location.column == 5  # 4 espaços de indentação + 1


def test_operators_assign_and_arrow_not_confused_with_singles() -> None:
    tokens, diags = tokenize("xVar := 1; fn(a => 2);", "f.st")
    kinds_texts = list(zip(_kinds(tokens), _texts(tokens)))

    assert ("OPERATOR", ":=") in kinds_texts
    assert ("OPERATOR", "=>") in kinds_texts
    # Não deve ter gerado um PUNCTUATION ':' isolado do ':=' nem um
    # OPERATOR '=' isolado do '=>'.
    assign_positions = [i for i, (k, t) in enumerate(kinds_texts) if t == ":="]
    assert len(assign_positions) == 1
    assert not diags.diagnostics


def test_comparison_operators_recognized() -> None:
    tokens, diags = tokenize("xA <= xB; xC >= xD; xE <> xF;", "f.st")
    kinds_texts = list(zip(_kinds(tokens), _texts(tokens)))

    assert ("OPERATOR", "<=") in kinds_texts
    assert ("OPERATOR", ">=") in kinds_texts
    assert ("OPERATOR", "<>") in kinds_texts
    assert not diags.diagnostics

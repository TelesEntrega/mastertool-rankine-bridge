"""Utilidades de texto para código IEC 61131-3 (ST)."""

from __future__ import annotations

import re

_BLOCK_COMMENT = re.compile(r"\(\*.*?\*\)", re.DOTALL)
_LINE_COMMENT = re.compile(r"//[^\n]*")
_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")


def strip_comments(source: str, placeholder: str = " ") -> str:
    """Remove comentários ST preservando posições de linha (troca por espaços)."""
    def _blank(match: re.Match) -> str:
        return "".join(ch if ch == "\n" else placeholder for ch in match.group(0))

    without_block = _BLOCK_COMMENT.sub(_blank, source)
    return _LINE_COMMENT.sub(_blank, without_block)


def strip_strings(source: str) -> str:
    return _STRING_LITERAL.sub(lambda m: " " * len(m.group(0)), source)


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def line_of_offset(text: str, offset: int) -> int:
    """Número da linha (1-based) de um offset."""
    return text.count("\n", 0, offset) + 1

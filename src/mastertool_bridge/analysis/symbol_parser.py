"""Parser TOLERANTE de declarações IEC 61131-3 (ST).

Não é um compilador: extrai cabeçalho do POU, blocos VAR* e variáveis
(nome, tipo, array, RETAIN/PERSISTENT, endereço AT, valor inicial).
Preserva o texto original e registra incertezas em Symbol.uncertainties.
"""

from __future__ import annotations

import re

from mastertool_bridge.models import Symbol, VariableDeclaration
from mastertool_bridge.utils.text import normalize_newlines, strip_comments

_HEADER_RE = re.compile(
    r"^\s*(PROGRAM|FUNCTION_BLOCK|FUNCTION|METHOD|INTERFACE|TYPE)\s+"
    r"(?:PUBLIC\s+|PRIVATE\s+|PROTECTED\s+|INTERNAL\s+|FINAL\s+|ABSTRACT\s+)*"
    r"([A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s*:\s*([A-Za-z_][A-Za-z0-9_.]*))?",
    re.IGNORECASE | re.MULTILINE)

_EXTENDS_RE = re.compile(r"\bEXTENDS\s+([A-Za-z_][A-Za-z0-9_.]*)", re.IGNORECASE)
_IMPLEMENTS_RE = re.compile(r"\bIMPLEMENTS\s+([A-Za-z0-9_., \t]+)", re.IGNORECASE)

_VAR_BLOCK_RE = re.compile(
    r"^\s*(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_GLOBAL|VAR_TEMP|VAR_STAT"
    r"|VAR_EXTERNAL|VAR_CONFIG|VAR)\b(?P<quals>[^\n]*)\n(?P<body>.*?)^\s*END_VAR\b",
    re.IGNORECASE | re.MULTILINE | re.DOTALL)

_STRUCT_RE = re.compile(r"\bSTRUCT\b(?P<body>.*?)\bEND_STRUCT\b",
                        re.IGNORECASE | re.DOTALL)

# nome1, nome2 AT %QX0.0 : ARRAY[0..9] OF INT := 0;
_VAR_DECL_RE = re.compile(
    r"^\s*(?P<names>[A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)"
    r"(?:\s+AT\s+(?P<address>%[IQM][XBWDL]?[0-9.]+))?"
    r"\s*:\s*(?P<type>[^:=;]+?)"
    r"(?:\s*:=\s*(?P<init>[^;]+?))?\s*$",
    re.IGNORECASE)

KIND_BY_HEADER = {
    "PROGRAM": "program",
    "FUNCTION_BLOCK": "function_block",
    "FUNCTION": "function",
    "METHOD": "method",
    "INTERFACE": "interface",
    "TYPE": "dut",
}


def _parse_block_body(body: str, block: str, quals: str, base_line: int,
                      symbol: Symbol) -> None:
    quals_upper = quals.upper()
    block_retain = "RETAIN" in quals_upper
    block_persistent = "PERSISTENT" in quals_upper
    offset = 0
    for statement in body.split(";"):
        stmt_line = base_line + body.count("\n", 0, offset)
        offset += len(statement) + 1
        text = statement.strip()
        if not text:
            continue
        match = _VAR_DECL_RE.match(text)
        if not match:
            symbol.uncertainties.append(
                f"linha ~{stmt_line}: declaração não reconhecida: "
                f"{text[:80]!r}")
            continue
        var_type = match.group("type").strip()
        for name in (n.strip() for n in match.group("names").split(",")):
            symbol.variables.append(VariableDeclaration(
                name=name,
                var_type=var_type,
                block=block.upper(),
                initial_value=(match.group("init") or "").strip() or None,
                is_array=var_type.upper().startswith("ARRAY"),
                is_retain=block_retain,
                is_persistent=block_persistent,
                address=match.group("address"),
                line=stmt_line,
            ))


def parse_declaration(source: str, default_name: str = "unknown") -> Symbol:
    original = normalize_newlines(source)
    clean = strip_comments(original)

    symbol = Symbol(name=default_name, kind="unknown")

    header = _HEADER_RE.search(clean)
    if header:
        keyword = header.group(1).upper()
        symbol.name = header.group(2)
        symbol.kind = KIND_BY_HEADER.get(keyword, "unknown")
        if header.group(3):
            symbol.return_type = header.group(3)
    elif _VAR_BLOCK_RE.search(clean):
        # Sem cabeçalho POU mas com bloco VAR — provavelmente uma GVL.
        symbol.kind = "gvl"
    else:
        symbol.uncertainties.append(
            "cabeçalho POU não identificado; tipo definido como 'unknown'.")

    extends = _EXTENDS_RE.search(clean)
    if extends:
        symbol.extends = extends.group(1)
    implements = _IMPLEMENTS_RE.search(clean)
    if implements:
        symbol.implements = [
            i.strip() for i in implements.group(1).split(",") if i.strip()]

    if symbol.kind == "dut":
        struct = _STRUCT_RE.search(clean)
        if struct:
            base_line = clean.count("\n", 0, struct.start("body")) + 1
            _parse_block_body(struct.group("body"), "STRUCT", "", base_line, symbol)

    for block_match in _VAR_BLOCK_RE.finditer(clean):
        base_line = clean.count("\n", 0, block_match.start("body")) + 1
        _parse_block_body(block_match.group("body"),
                          block_match.group(1),
                          block_match.group("quals") or "",
                          base_line, symbol)
    return symbol

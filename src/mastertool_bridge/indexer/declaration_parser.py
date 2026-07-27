"""Parser tolerante de `declaration.st` (cabeçalho de POU + blocos VAR*).

Escopo estrito desta fatia: só o CABEÇALHO da POU (PROGRAM/FUNCTION_BLOCK/
FUNCTION) e os blocos de declaração de variáveis. Corpo de implementação
(`implementation.st`) não é analisado aqui — apenas lexing básico é aceitável
em outros módulos, sem extração de símbolos.

Qualquer construção não reconhecida vira um `Diagnostic` com localização e o
parser CONTINUA tentando processar o resto do arquivo — nunca lança exceção
nem aborta o processamento do restante da POU.
"""

from __future__ import annotations

from mastertool_bridge.indexer.diagnostics import DiagnosticsCollector
from mastertool_bridge.indexer.models import (
    PouSymbol,
    SourceLocation,
    Token,
    VariableDeclaration,
)
from mastertool_bridge.indexer.st_lexer import tokenize

_POU_HEADER_KEYWORDS = {"PROGRAM", "FUNCTION_BLOCK", "FUNCTION"}

_VAR_BLOCK_STARTERS = {
    "VAR",
    "VAR_INPUT",
    "VAR_OUTPUT",
    "VAR_IN_OUT",
    "VAR_TEMP",
    "VAR_STAT",
    "VAR_GLOBAL",
}

_VAR_BLOCK_MODIFIERS = {"CONSTANT", "RETAIN", "PERSISTENT", "STAT"}


class _TokenStream:
    """Cursor simples sobre a lista de tokens não-triviais (sem PRAGMA)."""

    def __init__(self, tokens: list[Token]) -> None:
        # Pragmas são preservados no token stream original pelo lexer, mas
        # esta fatia do parser não interpreta pragmas — apenas os ignora ao
        # navegar pela estrutura de cabeçalho/blocos VAR.
        self.tokens = [t for t in tokens if t.kind != "PRAGMA"]
        self.pos = 0

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[idx]

    def advance(self) -> Token:
        tok = self.peek()
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def eof(self) -> bool:
        return self.peek().kind == "EOF"

    def is_keyword(self, tok: Token, word: str) -> bool:
        return tok.kind == "KEYWORD" and tok.text.upper() == word.upper()

    def match_keyword(self, word: str) -> bool:
        return self.is_keyword(self.peek(), word)


def parse_declaration(
    text: str, file: str, node_id: str | None = None
) -> tuple[PouSymbol | None, DiagnosticsCollector]:
    """Faz o parse de um `declaration.st`.

    Retorna (PouSymbol, diagnostics) — PouSymbol é None se o cabeçalho da POU
    não pôde ser reconhecido (diagnostics ainda assim é preenchido).
    """
    diags = DiagnosticsCollector()
    tokens, lex_diags = tokenize(text, file)
    diags.extend(lex_diags)

    stream = _TokenStream(tokens)
    symbol, header_diags = _parse_header(stream, file, node_id)
    diags.extend(header_diags)

    if symbol is None:
        return None, diags

    variables, body_diags = _parse_var_blocks(stream, file, node_id)
    diags.extend(body_diags)
    symbol.variables = variables

    return symbol, diags


def _parse_header(
    stream: _TokenStream, file: str, node_id: str | None
) -> tuple[PouSymbol | None, DiagnosticsCollector]:
    diags = DiagnosticsCollector()
    tok = stream.peek()

    if tok.kind != "KEYWORD" or tok.text.upper() not in _POU_HEADER_KEYWORDS:
        diags.error(
            "pou_header_not_found",
            f"Cabeçalho de POU esperado (PROGRAM/FUNCTION_BLOCK/FUNCTION), "
            f"encontrado {tok.kind} {tok.text!r}. Este arquivo pode ser uma "
            "GVL (ver parse_gvl_declaration) ou outra construção não "
            "suportada nesta fatia.",
            tok.location,
            node_id,
        )
        return None, diags

    header_location = tok.location
    pou_kind = tok.text.upper()
    stream.advance()

    name_tok = stream.peek()
    if name_tok.kind != "IDENTIFIER":
        diags.error(
            "malformed_declaration_line",
            f"Nome de POU esperado após {pou_kind}, encontrado "
            f"{name_tok.kind} {name_tok.text!r}.",
            name_tok.location,
            node_id,
        )
        return None, diags
    name = name_tok.text
    stream.advance()

    return_type: str | None = None
    extends: str | None = None
    implements: list[str] = []

    if pou_kind == "FUNCTION":
        colon_tok = stream.peek()
        if colon_tok.kind == "PUNCTUATION" and colon_tok.text == ":":
            stream.advance()
            type_tok = stream.peek()
            if type_tok.kind in {"IDENTIFIER", "KEYWORD"}:
                return_type = type_tok.text
                stream.advance()
                # Tipo pode ser ARRAY[..] OF TIPO — captura bruta simples.
                if return_type.upper() == "ARRAY":
                    return_type = _consume_raw_type_tail(stream, return_type)
            else:
                diags.error(
                    "malformed_declaration_line",
                    "Tipo de retorno esperado após ':' em cabeçalho de "
                    "FUNCTION.",
                    type_tok.location,
                    node_id,
                )
        else:
            diags.warning(
                "malformed_declaration_line",
                "Cabeçalho de FUNCTION sem tipo de retorno explícito "
                "(':' <tipo>).",
                colon_tok.location,
                node_id,
            )

    # EXTENDS <nome> / IMPLEMENTS <nome>,... — texto bruto, não é o foco
    # desta fatia.
    while True:
        cur = stream.peek()
        if stream.is_keyword(cur, "EXTENDS"):
            stream.advance()
            base_tok = stream.peek()
            if base_tok.kind in {"IDENTIFIER", "KEYWORD"}:
                extends = base_tok.text
                stream.advance()
            continue
        if stream.is_keyword(cur, "IMPLEMENTS"):
            stream.advance()
            while True:
                iface_tok = stream.peek()
                if iface_tok.kind in {"IDENTIFIER", "KEYWORD"}:
                    implements.append(iface_tok.text)
                    stream.advance()
                if (
                    stream.peek().kind == "PUNCTUATION"
                    and stream.peek().text == ","
                ):
                    stream.advance()
                    continue
                break
            continue
        break

    symbol = PouSymbol(
        node_id=node_id or name,
        pou_kind=pou_kind,
        name=name,
        file=file,
        return_type=return_type,
        extends=extends,
        implements=implements,
        variables=[],
        location=header_location,
    )
    return symbol, diags


def _consume_raw_type_tail(stream: _TokenStream, prefix: str) -> str:
    """Consome de forma bruta o restante de um tipo composto (ex.
    ARRAY[0..9] OF INT) para uso como `return_type`/`declared_type` textual,
    parando em ';', KEYWORD EXTENDS/IMPLEMENTS ou EOF."""
    parts = [prefix]
    while True:
        tok = stream.peek()
        if tok.kind == "EOF":
            break
        if tok.kind == "PUNCTUATION" and tok.text == ";":
            break
        if stream.is_keyword(tok, "EXTENDS") or stream.is_keyword(tok, "IMPLEMENTS"):
            break
        parts.append(tok.text)
        stream.advance()
    return "".join(
        p if p in "[](),." else f" {p}" for p in parts
    ).strip().replace("[ ", "[").replace(" ]", "]").replace(" ,", ",")


def _parse_var_blocks(
    stream: _TokenStream, file: str, node_id: str | None
) -> tuple[list[VariableDeclaration], DiagnosticsCollector]:
    diags = DiagnosticsCollector()
    variables: list[VariableDeclaration] = []

    while not stream.eof():
        tok = stream.peek()

        if tok.kind == "KEYWORD" and tok.text.upper() in _VAR_BLOCK_STARTERS:
            scope, is_constant = _consume_var_block_header(stream)
            block_vars, block_diags = _parse_var_block_body(
                stream, file, node_id, scope, is_constant
            )
            diags.extend(block_diags)
            variables.extend(block_vars)
            continue

        if tok.kind == "KEYWORD" and tok.text.upper() in {
            "END_PROGRAM",
            "END_FUNCTION_BLOCK",
            "END_FUNCTION",
        }:
            stream.advance()
            continue

        if tok.kind == "EOF":
            break

        # Token inesperado fora de qualquer bloco reconhecido: registra e
        # avança um token para não travar.
        diags.warning(
            "unexpected_token_outside_var_block",
            f"Token inesperado fora de bloco VAR/cabeçalho: {tok.kind} "
            f"{tok.text!r}.",
            tok.location,
            node_id,
        )
        stream.advance()

    return variables, diags


def _consume_var_block_header(stream: _TokenStream) -> tuple[str, bool]:
    start_tok = stream.advance()
    scope = start_tok.text.upper()
    is_constant = False

    # Aceita variações "VAR STAT" (espaço) e modificadores CONSTANT/RETAIN/
    # PERSISTENT logo após o iniciador do bloco.
    while True:
        cur = stream.peek()
        if cur.kind == "KEYWORD" and cur.text.upper() in _VAR_BLOCK_MODIFIERS:
            modifier = cur.text.upper()
            stream.advance()
            if modifier == "CONSTANT":
                is_constant = True
                scope = f"{scope} CONSTANT"
            elif modifier == "STAT" and scope == "VAR":
                scope = "VAR_STAT"
            else:
                scope = f"{scope} {modifier}"
            continue
        break

    return scope, is_constant


def _parse_var_block_body(
    stream: _TokenStream,
    file: str,
    node_id: str | None,
    scope: str,
    block_is_constant: bool,
) -> tuple[list[VariableDeclaration], DiagnosticsCollector]:
    diags = DiagnosticsCollector()
    variables: list[VariableDeclaration] = []

    while True:
        tok = stream.peek()

        if tok.kind == "KEYWORD" and tok.text.upper() == "END_VAR":
            stream.advance()
            return variables, diags

        if tok.kind == "EOF":
            diags.error(
                "unterminated_var_block",
                f"Bloco {scope} não foi terminado com END_VAR antes do fim "
                "do arquivo.",
                tok.location,
                node_id,
            )
            return variables, diags

        if tok.kind == "KEYWORD" and tok.text.upper() in _VAR_BLOCK_STARTERS:
            # Bloco anterior nunca fechou — registra e considera o bloco
            # atual encerrado ali, deixando o próximo loop tratar o novo
            # início de bloco.
            diags.error(
                "unterminated_var_block",
                f"Bloco {scope} não foi terminado com END_VAR antes de um "
                "novo bloco VAR começar.",
                tok.location,
                node_id,
            )
            return variables, diags

        decl_vars, consumed, decl_diags = _parse_one_declaration_line(
            stream, file, node_id, scope, block_is_constant
        )
        diags.extend(decl_diags)
        variables.extend(decl_vars)
        if not consumed:
            # Não conseguiu progredir: avança um token para evitar loop
            # infinito, mas já registrou diagnóstico dentro da função.
            stream.advance()


def _parse_one_declaration_line(
    stream: _TokenStream,
    file: str,
    node_id: str | None,
    scope: str,
    block_is_constant: bool,
) -> tuple[list[VariableDeclaration], bool, DiagnosticsCollector]:
    diags = DiagnosticsCollector()
    start_tok = stream.peek()

    if start_tok.kind != "IDENTIFIER":
        diags.warning(
            "malformed_declaration_line",
            f"Esperado nome de variável dentro de bloco {scope}, encontrado "
            f"{start_tok.kind} {start_tok.text!r}.",
            start_tok.location,
            node_id,
        )
        return [], False, diags

    names: list[str] = [start_tok.text]
    location = start_tok.location
    stream.advance()

    while (
        stream.peek().kind == "PUNCTUATION" and stream.peek().text == ","
    ):
        stream.advance()
        next_tok = stream.peek()
        if next_tok.kind != "IDENTIFIER":
            diags.warning(
                "malformed_declaration_line",
                "Esperado nome de variável após ',' na lista de "
                "declaração.",
                next_tok.location,
                node_id,
            )
            return [], True, diags
        names.append(next_tok.text)
        stream.advance()

    hardware_address: str | None = None
    at_tok = stream.peek()
    if at_tok.kind == "IDENTIFIER" and at_tok.text.upper() == "AT":
        stream.advance()
        addr_tok = stream.peek()
        if addr_tok.kind == "HW_ADDRESS":
            hardware_address = addr_tok.text
            stream.advance()
            if len(names) != 1:
                diags.error(
                    "invalid_multi_name_hardware_binding",
                    "Binding de hardware 'AT %endereco' só é válido para "
                    f"uma única variável por declaração, encontrado "
                    f"{names!r}.",
                    at_tok.location,
                    node_id,
                )
        else:
            diags.warning(
                "malformed_declaration_line",
                "Esperado endereço de hardware '%...' após 'AT', "
                f"encontrado {addr_tok.kind} {addr_tok.text!r}.",
                addr_tok.location,
                node_id,
            )

    colon_tok = stream.peek()
    if not (colon_tok.kind == "PUNCTUATION" and colon_tok.text == ":"):
        diags.warning(
            "malformed_declaration_line",
            f"Esperado ':' após nome(s) de variável {names!r}, encontrado "
            f"{colon_tok.kind} {colon_tok.text!r}.",
            colon_tok.location,
            node_id,
        )
        return [], True, diags
    stream.advance()

    declared_type, is_array, array_dims, type_diags = _parse_type(
        stream, file, node_id
    )
    diags.extend(type_diags)
    if declared_type is None:
        return [], True, diags

    initializer_raw: str | None = None
    if stream.peek().kind == "OPERATOR" and stream.peek().text == ":=":
        stream.advance()
        initializer_raw, init_diags = _consume_initializer_raw(stream)
        diags.extend(init_diags)

    semi_tok = stream.peek()
    if semi_tok.kind == "PUNCTUATION" and semi_tok.text == ";":
        stream.advance()
    else:
        diags.warning(
            "malformed_declaration_line",
            f"Esperado ';' ao final da declaração de {names!r}, encontrado "
            f"{semi_tok.kind} {semi_tok.text!r}.",
            semi_tok.location,
            node_id,
        )

    variables = [
        VariableDeclaration(
            name=name,
            declared_type=declared_type,
            scope=scope,
            is_array=is_array,
            array_dimensions=array_dims,
            initializer_raw=initializer_raw,
            is_constant=block_is_constant,
            location=location,
            hardware_address=hardware_address,
        )
        for name in names
    ]
    return variables, True, diags


def _parse_type(
    stream: _TokenStream, file: str, node_id: str | None
) -> tuple[str | None, bool, list[tuple[str, str]] | None, DiagnosticsCollector]:
    diags = DiagnosticsCollector()
    tok = stream.peek()

    if tok.kind == "KEYWORD" and tok.text.upper() == "ARRAY":
        stream.advance()
        dims: list[tuple[str, str]] = []
        if stream.peek().kind == "PUNCTUATION" and stream.peek().text == "[":
            stream.advance()
            dims, dim_diags = _parse_array_dimensions(stream, node_id)
            diags.extend(dim_diags)
            if (
                stream.peek().kind == "PUNCTUATION"
                and stream.peek().text == "]"
            ):
                stream.advance()
            else:
                diags.warning(
                    "malformed_declaration_line",
                    "Esperado ']' ao fechar dimensões de ARRAY.",
                    stream.peek().location,
                    node_id,
                )
        else:
            diags.warning(
                "malformed_declaration_line",
                "Esperado '[' após ARRAY.",
                stream.peek().location,
                node_id,
            )

        if stream.match_keyword("OF"):
            stream.advance()
        else:
            diags.warning(
                "malformed_declaration_line",
                "Esperado 'OF' após dimensões de ARRAY.",
                stream.peek().location,
                node_id,
            )

        base_type_tok = stream.peek()
        if base_type_tok.kind in {"IDENTIFIER", "KEYWORD"}:
            base_type = base_type_tok.text
            stream.advance()
        else:
            diags.warning(
                "malformed_declaration_line",
                "Esperado tipo base após ARRAY[..] OF.",
                base_type_tok.location,
                node_id,
            )
            base_type = "?"

        dims_text = ",".join(f"{lo}..{hi}" for lo, hi in dims)
        declared_type = f"ARRAY[{dims_text}] OF {base_type}"
        return declared_type, True, dims, diags

    if tok.kind in {"IDENTIFIER", "KEYWORD"}:
        declared_type = tok.text
        stream.advance()
        return declared_type, False, None, diags

    diags.error(
        "malformed_declaration_line",
        f"Tipo esperado, encontrado {tok.kind} {tok.text!r}.",
        tok.location,
        node_id,
    )
    return None, False, None, diags


def _parse_array_dimensions(
    stream: _TokenStream, node_id: str | None
) -> tuple[list[tuple[str, str]], DiagnosticsCollector]:
    diags = DiagnosticsCollector()
    dims: list[tuple[str, str]] = []

    while True:
        lo_tok = stream.peek()
        lo_parts = [lo_tok.text]
        stream.advance()
        # Aceita expressões simples de limite (ex. "0" ou "-1"); mantém
        # bruto sem avaliar.
        if lo_tok.kind == "OPERATOR" and lo_tok.text == "-":
            lo_parts = [lo_tok.text + stream.peek().text]
            stream.advance()

        dotdot_tok = stream.peek()
        if not (
            dotdot_tok.kind == "PUNCTUATION"
            and dotdot_tok.text == "."
            and stream.peek(1).kind == "PUNCTUATION"
            and stream.peek(1).text == "."
        ):
            diags.warning(
                "malformed_declaration_line",
                "Esperado '..' em dimensão de ARRAY.",
                dotdot_tok.location,
                node_id,
            )
            dims.append((lo_parts[0], "?"))
            break
        stream.advance()
        stream.advance()

        hi_tok = stream.peek()
        hi_text = hi_tok.text
        stream.advance()
        if hi_tok.kind == "OPERATOR" and hi_tok.text == "-":
            hi_text = hi_text + stream.peek().text
            stream.advance()

        dims.append((lo_parts[0], hi_text))

        if stream.peek().kind == "PUNCTUATION" and stream.peek().text == ",":
            stream.advance()
            continue
        break

    return dims, diags


def _consume_initializer_raw(
    stream: _TokenStream,
) -> tuple[str, DiagnosticsCollector]:
    """Consome o inicializador bruto até ';' (não avalia expressão),
    respeitando parênteses/colchetes aninhados para não parar num ';'
    dentro de um literal estruturado."""
    diags = DiagnosticsCollector()
    parts: list[str] = []
    depth = 0

    while True:
        tok = stream.peek()
        if tok.kind == "EOF":
            break
        if tok.kind == "PUNCTUATION" and tok.text in "([":
            depth += 1
        if tok.kind == "PUNCTUATION" and tok.text in ")]":
            depth = max(0, depth - 1)
        if tok.kind == "PUNCTUATION" and tok.text == ";" and depth == 0:
            break
        parts.append(tok.text)
        stream.advance()

    raw = " ".join(parts)
    # Normalizações leves para parecer com o texto original em casos comuns.
    raw = raw.replace(" (", "(").replace(" )", ")")
    raw = raw.replace(" [", "[").replace(" ]", "]")
    raw = raw.replace(" ,", ",").replace(" .", ".")
    return raw, diags

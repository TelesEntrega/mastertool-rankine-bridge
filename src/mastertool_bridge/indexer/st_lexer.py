"""Tokenizador de Structured Text (IEC 61131-3 / dialeto CODESYS).

Escopo estrito desta fatia: reconhece tokens preservando linha/coluna, sem
interpretar semântica nenhuma. Nunca lança exceção — qualquer condição de
erro (string/comentário não terminado, sequência de escape desconhecida,
comentário de bloco aninhado) vira um `Diagnostic` e a tokenização continua
até o fim do texto, sempre retornando (tokens, diagnostics).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mastertool_bridge.indexer.diagnostics import DiagnosticsCollector
from mastertool_bridge.indexer.models import SourceLocation, Token

# Palavras-chave-operador do IEC 61131-3 que, em contexto de expressão, atuam
# como operadores — mas nesta fatia não precisamos diferenciar de outras
# keywords: todas viram token KEYWORD (case-insensitive), o parser desta
# fatia não interpreta corpo de statements.
_KEYWORDS = {
    "AND", "OR", "NOT", "XOR", "MOD",
    "PROGRAM", "END_PROGRAM",
    "FUNCTION_BLOCK", "END_FUNCTION_BLOCK",
    "FUNCTION", "END_FUNCTION",
    "VAR", "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR_TEMP", "VAR_STAT",
    "VAR_GLOBAL", "END_VAR",
    "CONSTANT", "RETAIN", "PERSISTENT",
    "EXTENDS", "IMPLEMENTS",
    "ARRAY", "OF",
    "STRUCT", "END_STRUCT", "TYPE", "END_TYPE",
}

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# T#..., TIME#..., DT#..., DATE_AND_TIME#..., TOD#..., TIME_OF_DAY#..., DATE#...
# seguido de um valor sem espaços (aceita dígitos, letras, ':', '.', '_', '-').
_TYPED_LITERAL_PREFIX_RE = re.compile(
    r"(?i)(T|TIME|DT|DATE_AND_TIME|TOD|TIME_OF_DAY|DATE|LTIME)#"
)
_TYPED_LITERAL_VALUE_RE = re.compile(r"[0-9A-Za-z_:.\-]+")

# Endereço de hardware IEC 61131-3 (binding "AT"): %<I|Q|M><X|B|W|D|L opcional>
# <endereco com digitos/pontos>, ex. %QX54.0, %IW12, %MD3.1, %QB20480.
_HW_ADDRESS_RE = re.compile(r"%[IQM][XBWDL]?[0-9]+(\.[0-9]+)*")

# Literais com base explícita: 16#FF, 2#1010, 8#17
_BASED_NUMBER_RE = re.compile(r"[0-9]+#[0-9A-Fa-f_]+")

# Número real/inteiro simples (parte inteira, opcional fração/expoente).
_NUMBER_RE = re.compile(
    r"[0-9][0-9_]*(\.[0-9][0-9_]*)?([Ee][+\-]?[0-9]+)?"
)

_MULTI_CHAR_OPERATORS = [":=", "=>", "<=", ">=", "<>"]
_SINGLE_CHAR_OPERATORS = set("=+-*/<>")
_PUNCTUATION = set(":;,()[].")

_ESCAPE_RE = re.compile(r"\$.")
_KNOWN_ESCAPES = set("$'\"lLnNpPrRtT")


@dataclass
class _Cursor:
    text: str
    pos: int = 0
    line: int = 1
    column: int = 1

    def eof(self) -> bool:
        return self.pos >= len(self.text)

    def peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx >= len(self.text):
            return ""
        return self.text[idx]

    def location(self) -> tuple[int, int]:
        return self.line, self.column

    def advance(self, count: int = 1) -> str:
        chunk = self.text[self.pos : self.pos + count]
        for ch in chunk:
            if ch == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
        self.pos += count
        return chunk


def tokenize(
    text: str, file: str
) -> tuple[list[Token], DiagnosticsCollector]:
    """Tokeniza `text` (conteúdo de um .st) e retorna (tokens, diagnostics).

    Nunca lança exceção. Sempre inclui um token EOF explícito ao final,
    mesmo em caso de erro de tokenização.
    """
    diags = DiagnosticsCollector()
    tokens: list[Token] = []
    cur = _Cursor(text=text)

    while not cur.eof():
        ch = cur.peek()

        # Espaço em branco (não gera token).
        if ch in " \t\r\n":
            cur.advance()
            continue

        line, col = cur.location()

        # Comentário de linha.
        if ch == "/" and cur.peek(1) == "/":
            _consume_line_comment(cur)
            continue

        # Comentário de bloco (* ... *) — não aninhado.
        if ch == "(" and cur.peek(1) == "*":
            _consume_block_comment(cur, file, line, col, diags)
            continue

        # Pragma/atributo { ... }.
        if ch == "{":
            tok = _consume_pragma(cur, file, line, col, diags)
            tokens.append(tok)
            continue

        # String simples 'STRING'.
        if ch == "'":
            tok = _consume_quoted(cur, file, line, col, "'", "STRING", diags)
            tokens.append(tok)
            continue

        # WSTRING "..."
        if ch == '"':
            tok = _consume_quoted(cur, file, line, col, '"', "WSTRING", diags)
            tokens.append(tok)
            continue

        # Endereço de hardware %IX0.0 / %QB20480 / %MD3.1 (binding "AT").
        # Verificado antes de qualquer outra regra pois começa com '%', que
        # não colide com nenhum outro token.
        m_hw = _HW_ADDRESS_RE.match(cur.text, cur.pos)
        if ch == "%" and m_hw:
            value = cur.advance(len(m_hw.group(0)))
            tokens.append(
                Token("HW_ADDRESS", value, SourceLocation(file, line, col))
            )
            continue

        # Literal tipado T#..., TIME#..., DT#..., TOD#... (checar antes de
        # identificador genérico, pois começa com letras).
        m_typed = _TYPED_LITERAL_PREFIX_RE.match(cur.text, cur.pos)
        if m_typed:
            tok = _consume_typed_literal(cur, file, line, col, m_typed)
            tokens.append(tok)
            continue

        # Número com base explícita (16#FF) — checar antes de NUMBER simples.
        m_based = _BASED_NUMBER_RE.match(cur.text, cur.pos)
        if m_based:
            value = cur.advance(len(m_based.group(0)))
            tokens.append(
                Token("NUMBER", value, SourceLocation(file, line, col))
            )
            continue

        # Número simples.
        if ch.isdigit():
            m_num = _NUMBER_RE.match(cur.text, cur.pos)
            assert m_num is not None
            value = cur.advance(len(m_num.group(0)))
            tokens.append(
                Token("NUMBER", value, SourceLocation(file, line, col))
            )
            continue

        # Identificador / palavra-chave.
        if ch.isalpha() or ch == "_":
            m_ident = _IDENT_RE.match(cur.text, cur.pos)
            assert m_ident is not None
            value = cur.advance(len(m_ident.group(0)))
            kind = "KEYWORD" if value.upper() in _KEYWORDS else "IDENTIFIER"
            tokens.append(Token(kind, value, SourceLocation(file, line, col)))
            continue

        # Operadores multi-caractere.
        matched_op = None
        for op in _MULTI_CHAR_OPERATORS:
            if cur.text.startswith(op, cur.pos):
                matched_op = op
                break
        if matched_op:
            value = cur.advance(len(matched_op))
            tokens.append(
                Token("OPERATOR", value, SourceLocation(file, line, col))
            )
            continue

        # Operadores de um caractere.
        if ch in _SINGLE_CHAR_OPERATORS:
            value = cur.advance()
            tokens.append(
                Token("OPERATOR", value, SourceLocation(file, line, col))
            )
            continue

        # Pontuação.
        if ch in _PUNCTUATION:
            value = cur.advance()
            tokens.append(
                Token("PUNCTUATION", value, SourceLocation(file, line, col))
            )
            continue

        # Caractere não reconhecido: registra diagnóstico e avança 1 para
        # não travar a tokenização.
        diags.warning(
            "unrecognized_character",
            f"Caractere não reconhecido {ch!r} ignorado durante tokenização.",
            SourceLocation(file, line, col),
        )
        cur.advance()

    tokens.append(
        Token("EOF", "", SourceLocation(file, cur.line, cur.column))
    )
    return tokens, diags


def _consume_line_comment(cur: _Cursor) -> None:
    while not cur.eof() and cur.peek() != "\n":
        cur.advance()


def _consume_block_comment(
    cur: _Cursor, file: str, line: int, col: int, diags: DiagnosticsCollector
) -> None:
    cur.advance(2)  # "(*"
    nested_seen = False
    while not cur.eof():
        if cur.peek() == "*" and cur.peek(1) == ")":
            cur.advance(2)
            return
        if cur.peek() == "(" and cur.peek(1) == "*":
            nested_seen = True
        cur.advance()
    # Chegou ao EOF sem fechar.
    if nested_seen:
        diags.warning(
            "nested_block_comment",
            "Comentário de bloco aninhado detectado; fechado no primeiro "
            "'*)' encontrado (ou EOF).",
            SourceLocation(file, line, col),
        )
    diags.error(
        "unterminated_block_comment",
        "Comentário de bloco '(*' não foi terminado antes do fim do arquivo.",
        SourceLocation(file, line, col),
    )


def _consume_pragma(
    cur: _Cursor, file: str, line: int, col: int, diags: DiagnosticsCollector
) -> Token:
    start = cur.pos
    cur.advance(1)  # "{"
    while not cur.eof():
        if cur.peek() == "}":
            cur.advance(1)
            text = cur.text[start : cur.pos]
            return Token("PRAGMA", text, SourceLocation(file, line, col))
        cur.advance()
    # EOF sem fechar.
    diags.error(
        "unterminated_pragma",
        "Pragma/atributo '{' não foi terminado antes do fim do arquivo.",
        SourceLocation(file, line, col),
    )
    text = cur.text[start : cur.pos]
    return Token("PRAGMA", text, SourceLocation(file, line, col))


def _consume_quoted(
    cur: _Cursor,
    file: str,
    line: int,
    col: int,
    quote: str,
    kind: str,
    diags: DiagnosticsCollector,
) -> Token:
    start = cur.pos
    cur.advance(1)  # abre aspas
    while not cur.eof():
        ch = cur.peek()
        if ch == "$":
            esc = cur.peek(1)
            if esc == "" :
                break
            if esc.upper() not in {c.upper() for c in _KNOWN_ESCAPES} and esc != quote:
                diags.warning(
                    "unrecognized_escape_sequence",
                    f"Sequência de escape '$' + {esc!r} não reconhecida em string.",
                    SourceLocation(file, cur.line, cur.column),
                )
            cur.advance(2)
            continue
        if ch == quote:
            cur.advance(1)
            text = cur.text[start : cur.pos]
            return Token(kind, text, SourceLocation(file, line, col))
        if ch == "\n":
            break
        cur.advance()
    # Não terminada.
    diags.error(
        "unterminated_string",
        f"String iniciada com {quote!r} não foi terminada antes do fim da "
        "linha/arquivo.",
        SourceLocation(file, line, col),
    )
    text = cur.text[start : cur.pos]
    return Token(kind, text, SourceLocation(file, line, col))


def _consume_typed_literal(
    cur: _Cursor, file: str, line: int, col: int, prefix_match: re.Match[str]
) -> Token:
    start = cur.pos
    cur.advance(len(prefix_match.group(0)))
    m_val = _TYPED_LITERAL_VALUE_RE.match(cur.text, cur.pos)
    if m_val:
        cur.advance(len(m_val.group(0)))
    text = cur.text[start : cur.pos]
    return Token("TYPED_LITERAL", text, SourceLocation(file, line, col))

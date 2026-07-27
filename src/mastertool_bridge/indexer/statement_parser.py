"""Parser tolerante de statements e chamadas em `implementation.st`.

Escopo estrito desta fatia: reconhece CONSTRUÇÕES DE NÍVEL DE STATEMENT
(atribuição, IF/ELSIF/ELSE, CASE, FOR, WHILE, REPEAT, RETURN) e CHAMADAS
(standalone ou como lado direito de atribuição, incluindo chamadas de
método pontuadas como `Instancia.Metodo(...)`). Não é um parser de
expressões completo: dentro de condições/valores, o texto é preservado
bruto (`*_raw`), exceto pela extração best-effort de sites de chamada e
de ocorrências sintáticas de identificadores (para `references.json`).

Mesma filosofia dos demais módulos desta fatia (`declaration_parser.py`):
qualquer construção não reconhecida vira um `Diagnostic` com localização e
o parser CONTINUA processando o restante do arquivo — nunca lança exceção
nem aborta o processamento do restante da POU.

Fora de escopo (ver tarefa): resolução do alvo real de uma chamada,
associação de identificador a símbolo declarado, classificação semântica
de leitura/escrita, interpretação de VAR_INPUT/VAR_OUTPUT/VAR_IN_OUT a
partir do operador ':='/'=>' usado numa chamada, grafo de chamadas
agregado, busca em linguagem natural.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mastertool_bridge.indexer.diagnostics import DiagnosticsCollector
from mastertool_bridge.indexer.models import (
    Call,
    CallArgument,
    Reference,
    SourceLocation,
    Statement,
    Token,
)
from mastertool_bridge.indexer.st_lexer import tokenize

# Palavras-chave que iniciam/terminam blocos de statement reconhecidos por
# esta fatia.
_BLOCK_ENDERS = {
    "END_IF",
    "END_CASE",
    "END_FOR",
    "END_WHILE",
    "END_REPEAT",
    "ELSIF",
    "ELSE",
    "UNTIL",
}

_STATEMENT_STARTERS_HANDLED = {
    "IF",
    "CASE",
    "FOR",
    "WHILE",
    "REPEAT",
    "RETURN",
}


@dataclass
class _ParseResult:
    statements: list[Statement] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)

    def extend(self, other: "_ParseResult") -> None:
        self.statements.extend(other.statements)
        self.calls.extend(other.calls)
        self.references.extend(other.references)


class _TokenStream:
    """Cursor simples sobre a lista de tokens não-triviais (sem PRAGMA).

    NOTA IMPORTANTE: `st_lexer.tokenize()` classifica como KEYWORD apenas o
    conjunto fechado usado pela fatia de declaração (PROGRAM, VAR*, etc. —
    ver `_KEYWORDS` em `st_lexer.py`). Palavras reservadas de statement
    (IF/THEN/ELSIF/ELSE/END_IF/CASE/OF/END_CASE/FOR/TO/BY/DO/END_FOR/
    WHILE/END_WHILE/REPEAT/UNTIL/END_REPEAT/RETURN) NÃO estão nesse
    conjunto e chegam como token IDENTIFIER comum. Por isso
    `is_keyword`/`match_keyword` aqui reconhecem a palavra reservada pelo
    texto (case-insensitive), aceitando tanto KEYWORD quanto IDENTIFIER —
    sem modificar o lexer, apenas usando seu resultado como está."""

    def __init__(self, tokens: list[Token]) -> None:
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
        return tok.kind in ("KEYWORD", "IDENTIFIER") and tok.text.upper() == word.upper()

    def match_keyword(self, word: str) -> bool:
        return self.is_keyword(self.peek(), word)

    def is_punct(self, tok: Token, text: str) -> bool:
        return tok.kind == "PUNCTUATION" and tok.text == text

    def is_operator(self, tok: Token, text: str) -> bool:
        return tok.kind == "OPERATOR" and tok.text == text


class _NodeIdAllocator:
    """Gera node_ids determinísticos e únicos para statements/calls dentro
    de um mesmo arquivo `implementation.st`, com base no node_id do objeto
    dono mais um contador sequencial (ordem de aparição no arquivo)."""

    def __init__(self, owner_node_id: str) -> None:
        self._owner = owner_node_id
        self._counter = 0

    def next(self, prefix: str) -> str:
        node_id = f"{self._owner}#{prefix}{self._counter}"
        self._counter += 1
        return node_id


def parse_implementation(
    text: str, file: str, node_id: str
) -> tuple[list[Statement], list[Call], list[Reference], DiagnosticsCollector]:
    """Faz o parse de um `implementation.st`.

    Retorna (statements, calls, references, diagnostics), todos ordenados
    deterministicamente por posição de aparição. Nunca lança exceção:
    qualquer construção não reconhecida vira Diagnostic e o parser
    continua a partir do próximo token possível.
    """
    diags = DiagnosticsCollector()
    tokens, lex_diags = tokenize(text, file)
    diags.extend(lex_diags)

    stream = _TokenStream(tokens)
    allocator = _NodeIdAllocator(node_id)
    result = _parse_statement_list(
        stream, file, node_id, allocator, diags, terminators=set()
    )

    result.statements.sort(key=_sort_key_statement)
    result.calls.sort(key=_sort_key_call)
    result.references.sort(key=_sort_key_reference)

    return result.statements, result.calls, result.references, diags


def _sort_key_statement(stmt: Statement):
    return (stmt.node_id, stmt.location.line, stmt.location.column)


def _sort_key_call(call: Call):
    loc = call.location
    line = loc.line if loc else 0
    col = loc.column if loc else 0
    return (call.node_id, line, col)


def _sort_key_reference(ref: Reference):
    return (ref.node_id, ref.location.line, ref.location.column)


def _parse_statement_list(
    stream: _TokenStream,
    file: str,
    owner_node_id: str,
    allocator: _NodeIdAllocator,
    diags: DiagnosticsCollector,
    terminators: set[str],
) -> _ParseResult:
    """Processa uma sequência de statements até EOF ou até encontrar uma
    keyword em `terminators` (não consome o terminador)."""
    result = _ParseResult()

    while True:
        tok = stream.peek()

        if tok.kind == "EOF":
            return result

        if (
            tok.kind in ("KEYWORD", "IDENTIFIER")
            and tok.text.upper() in terminators
        ):
            return result

        # ';' solto (statement vazio) — ignora silenciosamente.
        if stream.is_punct(tok, ";"):
            stream.advance()
            continue

        stmt_result, consumed = _parse_one_statement(
            stream, file, owner_node_id, allocator, diags
        )
        if stmt_result is not None:
            result.extend(stmt_result)

        if not consumed:
            # Não conseguiu progredir de forma reconhecida: registra
            # diagnóstico e avança um token para não travar em loop
            # infinito.
            diags.warning(
                "unsupported_statement_construct",
                f"Construção de statement não reconhecida a partir de "
                f"{tok.kind} {tok.text!r}; token ignorado.",
                tok.location,
                owner_node_id,
            )
            stream.advance()


def _parse_one_statement(
    stream: _TokenStream,
    file: str,
    owner_node_id: str,
    allocator: _NodeIdAllocator,
    diags: DiagnosticsCollector,
) -> tuple[_ParseResult | None, bool]:
    """Tenta reconhecer um único statement a partir da posição atual.

    Retorna (resultado_parcial_ou_None, consumed) — `consumed` indica se
    ao menos um token foi consumido com sucesso como parte de um statement
    reconhecido (para o chamador decidir se precisa avançar manualmente)."""
    tok = stream.peek()

    if stream.is_keyword(tok, "IF"):
        return _parse_if(stream, file, owner_node_id, allocator, diags), True

    if stream.is_keyword(tok, "CASE"):
        return _parse_case(stream, file, owner_node_id, allocator, diags), True

    if stream.is_keyword(tok, "FOR"):
        return _parse_for(stream, file, owner_node_id, allocator, diags), True

    if stream.is_keyword(tok, "WHILE"):
        return _parse_while(stream, file, owner_node_id, allocator, diags), True

    if stream.is_keyword(tok, "REPEAT"):
        return _parse_repeat(stream, file, owner_node_id, allocator, diags), True

    if stream.is_keyword(tok, "RETURN"):
        return _parse_return(stream, file, owner_node_id, allocator, diags), True

    if tok.kind == "IDENTIFIER":
        return _parse_identifier_led_statement(
            stream, file, owner_node_id, allocator, diags
        )

    return None, False


# ---------------------------------------------------------------------------
# Atribuição / chamada standalone (ambos começam com IDENTIFIER, possivelmente
# com '.' no meio para chamadas de método).
# ---------------------------------------------------------------------------


def _parse_identifier_led_statement(
    stream: _TokenStream,
    file: str,
    owner_node_id: str,
    allocator: _NodeIdAllocator,
    diags: DiagnosticsCollector,
) -> tuple[_ParseResult | None, bool]:
    result = _ParseResult()
    start_tok = stream.peek()
    start_loc = start_tok.location

    name_text, name_end_loc, name_index_spans = _consume_dotted_name(stream)

    cur = stream.peek()

    # Atribuição: <nome> := <expressão> ;
    if stream.is_operator(cur, ":="):
        stream.advance()
        target_loc = start_loc
        result.references.append(
            Reference(
                node_id="",  # preenchido abaixo após alocar node_id
                file=file,
                name=name_text,
                context="assignment_target",
                location=target_loc,
                end_location=name_end_loc,
            )
        )
        for span in name_index_spans:
            for ref in _scan_value_tokens_for_references(
                span, file, "", context="assignment_target"
            ):
                result.references.append(ref)
        value_tokens, end_loc = _consume_expression_until_semicolon(stream)
        node_id = allocator.next("stmt")
        for ref in result.references:
            if ref.node_id == "":
                ref.node_id = node_id

        value_raw = _tokens_to_raw(value_tokens)
        stmt = Statement(
            node_id=node_id,
            file=file,
            kind="assignment",
            location=start_loc,
            end_location=end_loc,
        )
        result.statements.append(stmt)

        # Referências do lado direito: se for exatamente uma chamada,
        # decompõe e registra Call + referências dos argumentos/callee.
        # Caso contrário, registra uma referência agregada "assignment_value"
        # por identificador de nível superior encontrado no raw (best-effort).
        call = _try_parse_call_from_tokens(
            value_tokens, file, node_id, owner_node_id, allocator, diags, end_loc
        )
        if call is not None:
            result.calls.append(call)
            result.references.extend(
                _references_for_call(call, node_id, file)
            )
        else:
            result.references.extend(
                _scan_value_tokens_for_references(
                    value_tokens, file, node_id, context="assignment_value"
                )
            )

        _consume_semicolon(stream, file, node_id, diags, context="assignment")
        return result, True

    # Chamada standalone: <nome ou instancia.metodo> ( ... ) ;
    if stream.is_punct(cur, "("):
        node_id = allocator.next("stmt")
        call, end_loc, call_diags = _parse_call_arguments(
            stream, file, node_id, name_text, start_loc
        )
        diags.extend(call_diags)
        stmt = Statement(
            node_id=node_id,
            file=file,
            kind="call_statement",
            location=start_loc,
            end_location=end_loc,
        )
        result.statements.append(stmt)
        result.calls.append(call)
        result.references.extend(_references_for_call(call, node_id, file))

        _consume_semicolon(stream, file, node_id, diags, context="call_statement")
        return result, True

    # Não é nem atribuição nem chamada reconhecível: statement não suportado.
    # Consome até ';' (ou terminador de bloco/EOF) para não travar, e
    # registra diagnóstico.
    node_id = allocator.next("stmt")
    diags.warning(
        "unsupported_statement_construct",
        f"Statement iniciado por identificador {name_text!r} não reconhecido "
        "como atribuição ou chamada.",
        start_loc,
        owner_node_id,
    )
    _skip_to_semicolon_or_block_end(stream)
    return result, True


def _consume_dotted_name(
    stream: _TokenStream,
) -> tuple[str, SourceLocation, list[list[Token]]]:
    """Consome uma cadeia pontuada com índices opcionais a partir da posição
    atual do stream (o primeiro IDENTIFIER já é garantido pelo chamador) e
    avança o stream até o fim da cadeia reconhecida.

    Padrão reconhecido: `IDENTIFIER ('[' ... ']')? ('.' IDENTIFIER
    ('[' ... ']')?)*` — ver `_consume_dotted_chain_from_tokens` para os
    detalhes (mesma lógica, reutilizada aqui sobre `stream.tokens`).

    Retorna (texto_da_cadeia, localização_final, spans_de_índice) onde
    `spans_de_índice` é a lista de sublistas de tokens (uma por par de
    colchetes encontrado, na ordem em que aparecem) com o CONTEÚDO bruto de
    cada índice — para o chamador escanear recursivamente em busca de
    referências próprias (ex. `i` dentro de `Array[i]`), já que aqui não
    temos `file`/`node_id` disponíveis para construir `Reference`s."""
    name, end_loc, next_i, index_spans = _consume_dotted_chain_from_tokens(
        stream.tokens, stream.pos
    )
    stream.pos = min(next_i, len(stream.tokens) - 1)
    return name, end_loc, index_spans


def _consume_dotted_chain_from_tokens(
    tokens: list[Token], i: int
) -> tuple[str, SourceLocation, int, list[list[Token]]]:
    """Núcleo único (reutilizado por `_consume_dotted_name`,
    `_consume_dotted_name_from_list` e `_scan_raw_text_for_identifiers`) que
    reconhece uma cadeia pontuada com índices opcionais a partir de
    `tokens[i]` (deve ser IDENTIFIER — garantido pelo chamador).

    Gramática reconhecida (best-effort, nunca lança exceção):

        chain   := IDENTIFIER index? ( '.' IDENTIFIER index? )*
        index   := '[' <qualquer coisa até o ']' correspondente,
                        respeitando aninhamento de '[' '(' dentro do
                        índice, NUNCA interpretando o conteúdo> ']'

    Um índice sem ']' de fechamento (EOF antes de fechar) é best-effort:
    encerra a cadeia ali (todo o texto até o EOF fica preservado no nome),
    sem lançar exceção.

    Retorna (nome_completo_incluindo_índices, localização_do_último_token_
    consumido, próximo_índice_não_consumido, spans_de_índice) — `spans_de_
    índice` é a lista (uma entrada por par de colchetes reconhecido, na
    ordem de aparição) dos tokens do CONTEÚDO de cada índice (sem os
    colchetes), para o chamador escanear recursivamente em busca de
    referências próprias dentro do índice."""
    start_tok = tokens[i]
    name_parts: list[str] = [start_tok.text]
    last_loc = start_tok.location
    index_spans: list[list[Token]] = []
    j = i + 1

    def _consume_optional_index(j: int) -> int:
        """Se `tokens[j]` for '[', consome até o ']' correspondente
        (respeitando aninhamento de '[' e '(' dentro do índice), anexando o
        texto bruto a `name_parts` e o conteúdo a `index_spans`. Retorna o
        próximo índice não consumido. Se não houver ']' de fechamento antes
        do EOF, consome até o EOF (best-effort, sem exceção)."""
        nonlocal last_loc
        if not (
            j < len(tokens)
            and tokens[j].kind == "PUNCTUATION"
            and tokens[j].text == "["
        ):
            return j
        name_parts.append("[")
        last_loc = tokens[j].location
        depth = 1
        k = j + 1
        content_start = k
        while k < len(tokens) and tokens[k].kind != "EOF":
            tok = tokens[k]
            if tok.kind == "PUNCTUATION" and tok.text in "([":
                depth += 1
            elif tok.kind == "PUNCTUATION" and tok.text in ")]":
                depth -= 1
                if depth == 0 and tok.text == "]":
                    index_spans.append(tokens[content_start:k])
                    name_parts.append(_tokens_to_raw(tokens[content_start:k]))
                    name_parts.append("]")
                    last_loc = tok.location
                    return k + 1
            k += 1
        # ']' de fechamento nunca encontrado antes do EOF: best-effort,
        # preserva o que foi encontrado e encerra a cadeia ali (sem
        # consumir o EOF, sem lançar exceção).
        index_spans.append(tokens[content_start:k])
        name_parts.append(_tokens_to_raw(tokens[content_start:k]))
        if k > content_start:
            last_loc = tokens[k - 1].location
        return k

    j = _consume_optional_index(j)

    while (
        j + 1 < len(tokens)
        and tokens[j].kind == "PUNCTUATION"
        and tokens[j].text == "."
        and tokens[j + 1].kind == "IDENTIFIER"
    ):
        name_parts.append(".")
        name_parts.append(tokens[j + 1].text)
        last_loc = tokens[j + 1].location
        j = j + 2
        j = _consume_optional_index(j)

    return "".join(name_parts), last_loc, j, index_spans


def _consume_semicolon(
    stream: _TokenStream,
    file: str,
    node_id: str,
    diags: DiagnosticsCollector,
    context: str,
) -> None:
    tok = stream.peek()
    if stream.is_punct(tok, ";"):
        stream.advance()
        return
    diags.warning(
        "missing_statement_terminator",
        f"Esperado ';' ao final de {context}, encontrado {tok.kind} "
        f"{tok.text!r}.",
        tok.location,
        node_id,
    )


def _skip_to_semicolon_or_block_end(stream: _TokenStream) -> None:
    depth = 0
    while True:
        tok = stream.peek()
        if tok.kind == "EOF":
            return
        if tok.kind == "PUNCTUATION" and tok.text in "([":
            depth += 1
        if tok.kind == "PUNCTUATION" and tok.text in ")]":
            depth = max(0, depth - 1)
        if depth == 0 and tok.kind == "PUNCTUATION" and tok.text == ";":
            stream.advance()
            return
        if (
            depth == 0
            and tok.kind in ("KEYWORD", "IDENTIFIER")
            and tok.text.upper() in (_BLOCK_ENDERS | _STATEMENT_STARTERS_HANDLED)
        ):
            return
        stream.advance()


def _consume_expression_until_semicolon(
    stream: _TokenStream,
) -> tuple[list[Token], SourceLocation]:
    """Consome tokens até ';' de nível zero (respeitando parênteses), sem
    interpretar a expressão. Retorna (tokens_consumidos, localização do
    último token consumido antes do ';')."""
    tokens: list[Token] = []
    depth = 0
    last_loc: SourceLocation | None = None
    while True:
        tok = stream.peek()
        if tok.kind == "EOF":
            break
        if tok.kind == "PUNCTUATION" and tok.text in "([":
            depth += 1
        if tok.kind == "PUNCTUATION" and tok.text in ")]":
            depth = max(0, depth - 1)
        if depth == 0 and tok.kind == "PUNCTUATION" and tok.text == ";":
            break
        tokens.append(tok)
        last_loc = tok.location
        stream.advance()
    if last_loc is None:
        last_loc = stream.peek().location
    return tokens, last_loc


_NO_SPACE_BEFORE = {")", "]", ",", ".", ";", ":", "(", "["}
_NO_SPACE_AFTER = {"(", "[", "."}


def _tokens_to_raw(tokens: list[Token]) -> str:
    """Reconstrói um texto legível a partir de tokens brutos, sem tentar
    reproduzir espaçamento original byte-a-byte (apenas normaliza
    pontuação comum para não deixar espaços estranhos como "Foo( 1 )")."""
    parts: list[str] = []
    prev_text: str | None = None
    for tok in tokens:
        if tok.kind == "EOF" or tok.text == "":
            continue
        text = tok.text
        if not parts:
            parts.append(text)
        elif text in _NO_SPACE_BEFORE or prev_text in _NO_SPACE_AFTER:
            parts.append(text)
        else:
            parts.append(" ")
            parts.append(text)
        prev_text = text
    return "".join(parts)


# ---------------------------------------------------------------------------
# Reconhecimento best-effort de chamada como RHS de uma expressão de valor.
# ---------------------------------------------------------------------------


def _try_parse_call_from_tokens(
    value_tokens: list[Token],
    file: str,
    node_id: str,
    owner_node_id: str,
    allocator: _NodeIdAllocator,
    diags: DiagnosticsCollector,
    fallback_end_loc: SourceLocation,
) -> Call | None:
    """Se `value_tokens` representa exatamente `Nome[.Nome]* ( ... )` (sem
    sobra de tokens depois do ')' de fechamento), decompõe como Call.

    Caso a expressão seja mais complexa (ex. `Foo(Bar(1), 2) + 1` ou
    `Foo(x) + Bar(y)`), NÃO decompõe: retorna None e deixa o chamador tratar
    como valor bruto — best-effort, sem lançar exceção."""
    if not value_tokens:
        return None
    sub_stream = _TokenStream(value_tokens + [value_tokens[-1]])
    # Substitui o último token por um EOF sintético para não estourar índice.
    eof_tok = Token("EOF", "", fallback_end_loc)
    sub_stream.tokens = value_tokens + [eof_tok]
    sub_stream.pos = 0

    if sub_stream.peek().kind != "IDENTIFIER":
        return None

    start_loc = sub_stream.peek().location
    name_text, _, _index_spans = _consume_dotted_name(sub_stream)

    if not (
        sub_stream.peek().kind == "PUNCTUATION" and sub_stream.peek().text == "("
    ):
        return None

    call, end_loc, call_diags = _parse_call_arguments(
        sub_stream, file, node_id, name_text, start_loc
    )

    # Depois de consumir os argumentos, se sobrar QUALQUER token além do EOF
    # sintético, a expressão é mais complexa que uma chamada pura (ex. tem
    # operador depois) — registra a chamada externa mesmo assim (melhor
    # esforço), com diagnóstico informativo, capturando o argumento bruto
    # sem decompor aninhamento mais a fundo (já não decompomos aninhamento
    # de qualquer forma).
    if sub_stream.peek().kind != "EOF":
        diags.info(
            "call_expression_not_fully_decomposed",
            f"Expressão contendo chamada a {name_text!r} não foi totalmente "
            "decomposta (operador(es) além da chamada); apenas a chamada "
            "externa foi registrada.",
            start_loc,
            owner_node_id,
        )

    diags.extend(call_diags)
    return call


def _references_for_call(call: Call, node_id: str, file: str) -> list[Reference]:
    refs: list[Reference] = []
    if call.location is not None:
        refs.append(
            Reference(
                node_id=node_id,
                file=file,
                name=call.callee,
                context="call_callee",
                location=call.location,
            )
        )
    for arg in call.arguments:
        refs.extend(
            _scan_raw_text_for_identifiers(
                arg.value_raw, arg.location, node_id, file, context="call_argument_value"
            )
        )
    return refs


def _consume_dotted_name_from_list(
    tokens: list[Token], i: int
) -> tuple[str, "SourceLocation", int, list[list[Token]]]:
    """Junta `tokens[i]` (IDENTIFIER) com a cadeia pontuada com índices
    opcionais que o segue — ver `_consume_dotted_chain_from_tokens` (núcleo
    único reutilizado aqui). Retorna (nome_completo_incluindo_índices,
    localização_do_último_token, próximo_índice_não_consumido, spans_de_
    índice) — `spans_de_índice` é a lista de sublistas de tokens (conteúdo
    bruto de cada `[...]` reconhecido) para o chamador escanear
    recursivamente em busca de referências próprias dentro do índice.

    Nome incompleto tipo `GVL.` (ponto sem IDENTIFIER seguinte) é
    best-effort: o ponto NÃO é consumido (encerra a cadeia ali), então a
    Reference resultante fica só com o que foi reconhecido antes do ponto
    solto (ex. "GVL") — nunca lança exceção. Colchete não fechado também é
    best-effort (ver núcleo compartilhado): nunca lança exceção."""
    return _consume_dotted_chain_from_tokens(tokens, i)


def _scan_value_tokens_for_references(
    value_tokens: list[Token], file: str, node_id: str, context: str
) -> list[Reference]:
    """Registra como referência cada nome (possivelmente pontuado e com
    índices de array, `Identificador[indice].Identificador...`) de nível
    superior nos tokens de valor (best-effort, sem interpretar
    precedência/operadores). Uma cadeia pontuada inteira (incluindo
    índice(s)) vira UMA única Reference com `location` no primeiro token e
    `end_location` no último. O CONTEÚDO de cada índice é escaneado
    recursivamente pelo mesmo mecanismo, gerando Reference(s) PRÓPRIA(S) e
    independente(s) para identificadores encontrados ali dentro (mesmo
    `context` da cadeia externa)."""
    refs: list[Reference] = []
    i = 0
    while i < len(value_tokens):
        tok = value_tokens[i]
        if tok.kind == "IDENTIFIER":
            name, end_loc, next_i, index_spans = _consume_dotted_name_from_list(
                value_tokens, i
            )
            refs.append(
                Reference(
                    node_id=node_id,
                    file=file,
                    name=name,
                    context=context,
                    location=tok.location,
                    end_location=end_loc,
                )
            )
            for span in index_spans:
                refs.extend(
                    _scan_value_tokens_for_references(span, file, node_id, context)
                )
            i = next_i
            continue
        i += 1
    return refs


def _scan_raw_text_for_identifiers(
    value_raw: str,
    location: SourceLocation,
    node_id: str,
    file: str,
    context: str,
) -> list[Reference]:
    """Best-effort: tokeniza novamente o texto bruto de um argumento para
    localizar identificadores (possivelmente pontuados) dentro dele (usado
    quando só temos o `value_raw` já achatado, ex. dentro de argumentos de
    chamada).

    NOTA: como só temos o `value_raw` achatado (sem posições originais no
    arquivo-fonte), `location`/`end_location` de TODAS as referências aqui
    usam a `location` do argumento inteiro (mesmo comportamento pré-existente
    para `location`; `end_location` é preenchido com o mesmo valor por
    consistência, já que não há posição real do último token disponível
    neste caminho)."""
    tokens, _diags = tokenize(value_raw, file)
    refs: list[Reference] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.kind == "IDENTIFIER":
            name, _end_loc, next_i, index_spans = _consume_dotted_name_from_list(
                tokens, i
            )
            refs.append(
                Reference(
                    node_id=node_id,
                    file=file,
                    name=name,
                    context=context,
                    location=location,
                    end_location=location,
                )
            )
            # Escaneia recursivamente o CONTEÚDO de cada índice: sem
            # posições reais disponíveis neste caminho achatado (mesma
            # limitação pré-existente de `location`/`end_location` descrita
            # acima), reaproveitando o mesmo mecanismo de nome-pontuado.
            for span in index_spans:
                refs.extend(
                    _scan_raw_span_for_identifiers(
                        span, location, node_id, file, context
                    )
                )
            i = next_i
            continue
        i += 1
    return refs


def _scan_raw_span_for_identifiers(
    tokens: list[Token],
    location: SourceLocation,
    node_id: str,
    file: str,
    context: str,
) -> list[Reference]:
    """Igual a `_scan_raw_text_for_identifiers`, mas parte de uma lista de
    tokens já tokenizada (span de índice) em vez de retokenizar texto bruto
    — usada para escanear recursivamente o CONTEÚDO de um índice de array
    dentro de um argumento de chamada (`value_raw` achatado)."""
    refs: list[Reference] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.kind == "IDENTIFIER":
            name, _end_loc, next_i, index_spans = _consume_dotted_name_from_list(
                tokens, i
            )
            refs.append(
                Reference(
                    node_id=node_id,
                    file=file,
                    name=name,
                    context=context,
                    location=location,
                    end_location=location,
                )
            )
            for span in index_spans:
                refs.extend(
                    _scan_raw_span_for_identifiers(span, location, node_id, file, context)
                )
            i = next_i
            continue
        i += 1
    return refs


# ---------------------------------------------------------------------------
# Chamadas: argumentos posicionais/nomeados.
# ---------------------------------------------------------------------------


def _parse_call_arguments(
    stream: _TokenStream,
    file: str,
    node_id: str,
    callee: str,
    start_loc: SourceLocation,
) -> tuple[Call, SourceLocation, DiagnosticsCollector]:
    """Espera que o token atual seja '('. Consome até o ')' correspondente
    (ou EOF), retornando (Call, localização_final, diagnostics)."""
    diags = DiagnosticsCollector()
    open_tok = stream.advance()  # '('
    arguments: list[CallArgument] = []
    end_loc = open_tok.location

    if stream.peek().kind == "PUNCTUATION" and stream.peek().text == ")":
        end_loc = stream.peek().location
        stream.advance()
        return (
            Call(
                node_id=node_id,
                file=file,
                callee=callee,
                arguments=arguments,
                location=start_loc,
                end_location=end_loc,
            ),
            end_loc,
            diags,
        )

    while True:
        if stream.eof():
            diags.error(
                "unterminated_call_arguments",
                f"Lista de argumentos da chamada a {callee!r} não foi "
                "terminada com ')' antes do fim do arquivo.",
                start_loc,
                node_id,
            )
            end_loc = stream.peek().location
            break

        arg, arg_end_loc = _parse_one_call_argument(stream)
        arguments.append(arg)
        end_loc = arg_end_loc

        nxt = stream.peek()
        if nxt.kind == "PUNCTUATION" and nxt.text == ",":
            stream.advance()
            continue
        if nxt.kind == "PUNCTUATION" and nxt.text == ")":
            end_loc = nxt.location
            stream.advance()
            break
        if nxt.kind == "EOF":
            diags.error(
                "unterminated_call_arguments",
                f"Lista de argumentos da chamada a {callee!r} não foi "
                "terminada com ')' antes do fim do arquivo.",
                start_loc,
                node_id,
            )
            break
        # Token inesperado dentro da lista de argumentos: registra e avança
        # para tentar continuar.
        diags.warning(
            "malformed_call_argument",
            f"Token inesperado {nxt.kind} {nxt.text!r} na lista de "
            f"argumentos da chamada a {callee!r}.",
            nxt.location,
            node_id,
        )
        stream.advance()

    return (
        Call(
            node_id=node_id,
            file=file,
            callee=callee,
            arguments=arguments,
            location=start_loc,
            end_location=end_loc,
        ),
        end_loc,
        diags,
    )


def _parse_one_call_argument(stream: _TokenStream) -> tuple[CallArgument, SourceLocation]:
    """Consome um único argumento (até ',' ou ')' de nível zero).

    Formas suportadas:
      - posicional: <expressão>
      - nomeado entrada: NAME := <expressão>
      - nomeado saída:   NAME => <expressão>
    """
    start_tok = stream.peek()
    start_loc = start_tok.location

    name: str | None = None
    operator: str | None = None

    if start_tok.kind == "IDENTIFIER" and (
        (stream.peek(1).kind == "OPERATOR" and stream.peek(1).text == ":=")
        or (stream.peek(1).kind == "OPERATOR" and stream.peek(1).text == "=>")
    ):
        name = start_tok.text
        stream.advance()
        operator = stream.advance().text  # ':=' ou '=>'

    value_tokens: list[Token] = []
    depth = 0
    last_loc = start_loc
    while True:
        tok = stream.peek()
        if tok.kind == "EOF":
            break
        if tok.kind == "PUNCTUATION" and tok.text in "([":
            depth += 1
        if tok.kind == "PUNCTUATION" and tok.text in ")]":
            if depth == 0:
                break
            depth -= 1
        if depth == 0 and tok.kind == "PUNCTUATION" and tok.text == ",":
            break
        value_tokens.append(tok)
        last_loc = tok.location
        stream.advance()

    value_raw = _tokens_to_raw(value_tokens)
    arg_location = value_tokens[0].location if value_tokens else start_loc

    return (
        CallArgument(
            name=name,
            operator=operator,
            value_raw=value_raw,
            location=arg_location,
        ),
        last_loc,
    )


# ---------------------------------------------------------------------------
# IF / ELSIF / ELSE / END_IF
# ---------------------------------------------------------------------------


def _parse_if(
    stream: _TokenStream,
    file: str,
    owner_node_id: str,
    allocator: _NodeIdAllocator,
    diags: DiagnosticsCollector,
) -> _ParseResult:
    result = _ParseResult()
    start_tok = stream.advance()  # 'IF'
    node_id = allocator.next("stmt")

    cond_tokens, then_diags = _consume_condition_until_keyword(stream, "THEN")
    diags.extend(then_diags)
    result.references.extend(
        _scan_value_tokens_for_references(cond_tokens, file, node_id, "condition")
    )

    if stream.match_keyword("THEN"):
        stream.advance()
    else:
        diags.warning(
            "malformed_if_statement",
            "Esperado 'THEN' após condição de IF.",
            stream.peek().location,
            node_id,
        )

    body_result = _parse_statement_list(
        stream,
        file,
        owner_node_id,
        allocator,
        diags,
        terminators={"ELSIF", "ELSE", "END_IF"},
    )
    result.extend(body_result)

    while stream.match_keyword("ELSIF"):
        stream.advance()
        elsif_cond_tokens, elsif_diags = _consume_condition_until_keyword(
            stream, "THEN"
        )
        diags.extend(elsif_diags)
        result.references.extend(
            _scan_value_tokens_for_references(
                elsif_cond_tokens, file, node_id, "condition"
            )
        )
        if stream.match_keyword("THEN"):
            stream.advance()
        else:
            diags.warning(
                "malformed_if_statement",
                "Esperado 'THEN' após condição de ELSIF.",
                stream.peek().location,
                node_id,
            )
        elsif_body = _parse_statement_list(
            stream,
            file,
            owner_node_id,
            allocator,
            diags,
            terminators={"ELSIF", "ELSE", "END_IF"},
        )
        result.extend(elsif_body)

    if stream.match_keyword("ELSE"):
        stream.advance()
        else_body = _parse_statement_list(
            stream, file, owner_node_id, allocator, diags, terminators={"END_IF"}
        )
        result.extend(else_body)

    end_loc = start_tok.location
    if stream.match_keyword("END_IF"):
        end_tok = stream.advance()
        end_loc = end_tok.location
    else:
        diags.error(
            "unterminated_block",
            "Bloco IF não foi terminado com END_IF antes do fim do arquivo.",
            start_tok.location,
            owner_node_id,
        )

    _consume_optional_semicolon(stream)

    result.statements.append(
        Statement(
            node_id=node_id,
            file=file,
            kind="if",
            location=start_tok.location,
            end_location=end_loc,
        )
    )
    return result


def _consume_condition_until_keyword(
    stream: _TokenStream, keyword: str
) -> tuple[list[Token], DiagnosticsCollector]:
    """Consome tokens até encontrar a keyword de nível zero indicada (não a
    consome) ou EOF."""
    diags = DiagnosticsCollector()
    tokens: list[Token] = []
    depth = 0
    while True:
        tok = stream.peek()
        if tok.kind == "EOF":
            break
        if depth == 0 and stream.is_keyword(tok, keyword):
            break
        if tok.kind == "PUNCTUATION" and tok.text in "([":
            depth += 1
        if tok.kind == "PUNCTUATION" and tok.text in ")]":
            depth = max(0, depth - 1)
        tokens.append(tok)
        stream.advance()
    return tokens, diags


def _consume_optional_semicolon(stream: _TokenStream) -> None:
    if stream.peek().kind == "PUNCTUATION" and stream.peek().text == ";":
        stream.advance()


# ---------------------------------------------------------------------------
# CASE ... OF ... END_CASE
# ---------------------------------------------------------------------------


def _parse_case(
    stream: _TokenStream,
    file: str,
    owner_node_id: str,
    allocator: _NodeIdAllocator,
    diags: DiagnosticsCollector,
) -> _ParseResult:
    result = _ParseResult()
    start_tok = stream.advance()  # 'CASE'
    node_id = allocator.next("stmt")

    selector_tokens, _d = _consume_condition_until_keyword(stream, "OF")
    result.references.extend(
        _scan_value_tokens_for_references(selector_tokens, file, node_id, "condition")
    )

    if stream.match_keyword("OF"):
        stream.advance()
    else:
        diags.warning(
            "malformed_case_statement",
            "Esperado 'OF' após seletor de CASE.",
            stream.peek().location,
            node_id,
        )

    # Labels: <literal-ou-lista> ':' <statements...> até próximo label,
    # ELSE ou END_CASE.
    while not stream.eof():
        tok = stream.peek()
        if stream.is_keyword(tok, "ELSE") or stream.is_keyword(tok, "END_CASE"):
            break

        # Consome a lista de labels até ':' de nível zero.
        depth = 0
        found_colon = False
        while True:
            ltok = stream.peek()
            if ltok.kind == "EOF":
                break
            if ltok.kind == "PUNCTUATION" and ltok.text in "([":
                depth += 1
            if ltok.kind == "PUNCTUATION" and ltok.text in ")]":
                depth = max(0, depth - 1)
            if depth == 0 and ltok.kind == "PUNCTUATION" and ltok.text == ":":
                stream.advance()
                found_colon = True
                break
            stream.advance()

        if not found_colon:
            diags.error(
                "malformed_case_statement",
                "Label de CASE sem ':' antes do fim do arquivo.",
                tok.location,
                node_id,
            )
            break

        label_body = _parse_statement_list_until_case_boundary(
            stream, file, owner_node_id, allocator, diags
        )
        result.extend(label_body)

        # `_parse_statement_list_until_case_boundary` já para exatamente em
        # ELSE/END_CASE/EOF/início de próximo label (sem consumi-lo).
        if stream.eof():
            break
        if stream.match_keyword("ELSE") or stream.match_keyword("END_CASE"):
            break
        # Caso contrário, mais um label segue: volta ao topo do while.

    if stream.match_keyword("ELSE"):
        stream.advance()
        else_body = _parse_statement_list(
            stream, file, owner_node_id, allocator, diags, terminators={"END_CASE"}
        )
        result.extend(else_body)

    end_loc = start_tok.location
    if stream.match_keyword("END_CASE"):
        end_tok = stream.advance()
        end_loc = end_tok.location
    else:
        diags.error(
            "unterminated_block",
            "Bloco CASE não foi terminado com END_CASE antes do fim do "
            "arquivo.",
            start_tok.location,
            owner_node_id,
        )

    _consume_optional_semicolon(stream)

    result.statements.append(
        Statement(
            node_id=node_id,
            file=file,
            kind="case",
            location=start_tok.location,
            end_location=end_loc,
        )
    )
    return result


def _parse_statement_list_until_case_boundary(
    stream: _TokenStream,
    file: str,
    owner_node_id: str,
    allocator: _NodeIdAllocator,
    diags: DiagnosticsCollector,
) -> _ParseResult:
    """Como `_parse_statement_list`, mas também para (sem consumir) ao
    detectar o início de um novo label de CASE (`<literal-list> ':'` de
    nível zero) — necessário porque um label não tem palavra-chave própria
    que o distinga de um statement comum."""
    result = _ParseResult()

    while True:
        tok = stream.peek()

        if tok.kind == "EOF":
            return result

        if tok.kind in ("KEYWORD", "IDENTIFIER") and tok.text.upper() in (
            "ELSE",
            "END_CASE",
        ):
            return result

        if _looks_like_case_label_start(stream):
            return result

        if stream.is_punct(tok, ";"):
            stream.advance()
            continue

        stmt_result, consumed = _parse_one_statement(
            stream, file, owner_node_id, allocator, diags
        )
        if stmt_result is not None:
            result.extend(stmt_result)

        if not consumed:
            diags.warning(
                "unsupported_statement_construct",
                f"Construção de statement não reconhecida a partir de "
                f"{tok.kind} {tok.text!r}; token ignorado.",
                tok.location,
                owner_node_id,
            )
            stream.advance()


def _looks_like_case_label_start(stream: _TokenStream) -> bool:
    """Lookahead: retorna True se, a partir da posição atual, os próximos
    tokens formam `<literal-ou-lista> ':'` de nível zero SEM cruzar um ';'
    de nível zero antes — isto é, um novo label de CASE, e não uma
    atribuição/statement comum. Não consome tokens."""
    offset = 0
    depth = 0
    while True:
        tok = stream.peek(offset)
        if tok.kind == "EOF":
            return False
        if depth == 0 and tok.kind == "PUNCTUATION" and tok.text == ";":
            return False
        if depth == 0 and tok.kind == "PUNCTUATION" and tok.text == ":":
            # ':=' já é um token OPERATOR distinto do lexer, então um ':'
            # PUNCTUATION isolado aqui é sempre fim de label.
            return True
        if depth == 0 and tok.kind == "OPERATOR" and tok.text == ":=":
            return False
        if tok.kind == "PUNCTUATION" and tok.text in "([":
            depth += 1
        if tok.kind == "PUNCTUATION" and tok.text in ")]":
            depth = max(0, depth - 1)
        # Limite de segurança generoso para não escanear o arquivo inteiro
        # em busca de um ':' que nunca vem (statement comum sem label).
        offset += 1
        if offset > 200:
            return False


# ---------------------------------------------------------------------------
# FOR ... TO ... [BY ...] DO ... END_FOR
# ---------------------------------------------------------------------------


def _parse_for(
    stream: _TokenStream,
    file: str,
    owner_node_id: str,
    allocator: _NodeIdAllocator,
    diags: DiagnosticsCollector,
) -> _ParseResult:
    result = _ParseResult()
    start_tok = stream.advance()  # 'FOR'
    node_id = allocator.next("stmt")

    var_tok = stream.peek()
    if var_tok.kind == "IDENTIFIER":
        result.references.append(
            Reference(
                node_id=node_id,
                file=file,
                name=var_tok.text,
                context="for_loop_bound",
                location=var_tok.location,
            )
        )
        stream.advance()
    else:
        diags.warning(
            "malformed_for_statement",
            f"Esperado identificador de variável de controle após FOR, "
            f"encontrado {var_tok.kind} {var_tok.text!r}.",
            var_tok.location,
            node_id,
        )

    if stream.peek().kind == "OPERATOR" and stream.peek().text == ":=":
        stream.advance()
    else:
        diags.warning(
            "malformed_for_statement",
            "Esperado ':=' após variável de controle em FOR.",
            stream.peek().location,
            node_id,
        )

    start_expr_tokens, _d1 = _consume_condition_until_keyword(stream, "TO")
    result.references.extend(
        _scan_value_tokens_for_references(
            start_expr_tokens, file, node_id, "for_loop_bound"
        )
    )
    if stream.match_keyword("TO"):
        stream.advance()
    else:
        diags.warning(
            "malformed_for_statement",
            "Esperado 'TO' em FOR.",
            stream.peek().location,
            node_id,
        )

    # Limite superior vai até 'BY' ou 'DO', o que vier primeiro.
    end_expr_tokens, end_kw = _consume_condition_until_any_keyword(
        stream, ("BY", "DO")
    )
    result.references.extend(
        _scan_value_tokens_for_references(
            end_expr_tokens, file, node_id, "for_loop_bound"
        )
    )

    if end_kw == "BY":
        stream.advance()  # 'BY'
        step_tokens, _d2 = _consume_condition_until_keyword(stream, "DO")
        result.references.extend(
            _scan_value_tokens_for_references(
                step_tokens, file, node_id, "for_loop_bound"
            )
        )

    if stream.match_keyword("DO"):
        stream.advance()
    else:
        diags.warning(
            "malformed_for_statement",
            "Esperado 'DO' em FOR.",
            stream.peek().location,
            node_id,
        )

    body_result = _parse_statement_list(
        stream, file, owner_node_id, allocator, diags, terminators={"END_FOR"}
    )
    result.extend(body_result)

    end_loc = start_tok.location
    if stream.match_keyword("END_FOR"):
        end_tok = stream.advance()
        end_loc = end_tok.location
    else:
        diags.error(
            "unterminated_block",
            "Bloco FOR não foi terminado com END_FOR antes do fim do "
            "arquivo.",
            start_tok.location,
            owner_node_id,
        )

    _consume_optional_semicolon(stream)

    result.statements.append(
        Statement(
            node_id=node_id,
            file=file,
            kind="for",
            location=start_tok.location,
            end_location=end_loc,
        )
    )
    return result


def _consume_condition_until_any_keyword(
    stream: _TokenStream, keywords: tuple[str, ...]
) -> tuple[list[Token], str | None]:
    tokens: list[Token] = []
    depth = 0
    while True:
        tok = stream.peek()
        if tok.kind == "EOF":
            return tokens, None
        if (
            depth == 0
            and tok.kind in ("KEYWORD", "IDENTIFIER")
            and tok.text.upper() in keywords
        ):
            return tokens, tok.text.upper()
        if tok.kind == "PUNCTUATION" and tok.text in "([":
            depth += 1
        if tok.kind == "PUNCTUATION" and tok.text in ")]":
            depth = max(0, depth - 1)
        tokens.append(tok)
        stream.advance()


# ---------------------------------------------------------------------------
# WHILE ... DO ... END_WHILE
# ---------------------------------------------------------------------------


def _parse_while(
    stream: _TokenStream,
    file: str,
    owner_node_id: str,
    allocator: _NodeIdAllocator,
    diags: DiagnosticsCollector,
) -> _ParseResult:
    result = _ParseResult()
    start_tok = stream.advance()  # 'WHILE'
    node_id = allocator.next("stmt")

    cond_tokens, _d = _consume_condition_until_keyword(stream, "DO")
    result.references.extend(
        _scan_value_tokens_for_references(cond_tokens, file, node_id, "condition")
    )

    if stream.match_keyword("DO"):
        stream.advance()
    else:
        diags.warning(
            "malformed_while_statement",
            "Esperado 'DO' após condição de WHILE.",
            stream.peek().location,
            node_id,
        )

    body_result = _parse_statement_list(
        stream, file, owner_node_id, allocator, diags, terminators={"END_WHILE"}
    )
    result.extend(body_result)

    end_loc = start_tok.location
    if stream.match_keyword("END_WHILE"):
        end_tok = stream.advance()
        end_loc = end_tok.location
    else:
        diags.error(
            "unterminated_block",
            "Bloco WHILE não foi terminado com END_WHILE antes do fim do "
            "arquivo.",
            start_tok.location,
            owner_node_id,
        )

    _consume_optional_semicolon(stream)

    result.statements.append(
        Statement(
            node_id=node_id,
            file=file,
            kind="while",
            location=start_tok.location,
            end_location=end_loc,
        )
    )
    return result


# ---------------------------------------------------------------------------
# REPEAT ... UNTIL ... END_REPEAT
# ---------------------------------------------------------------------------


def _parse_repeat(
    stream: _TokenStream,
    file: str,
    owner_node_id: str,
    allocator: _NodeIdAllocator,
    diags: DiagnosticsCollector,
) -> _ParseResult:
    result = _ParseResult()
    start_tok = stream.advance()  # 'REPEAT'
    node_id = allocator.next("stmt")

    body_result = _parse_statement_list(
        stream, file, owner_node_id, allocator, diags, terminators={"UNTIL"}
    )
    result.extend(body_result)

    if stream.match_keyword("UNTIL"):
        stream.advance()
        cond_tokens, _d = _consume_condition_until_keyword(stream, "END_REPEAT")
        result.references.extend(
            _scan_value_tokens_for_references(
                cond_tokens, file, node_id, "condition"
            )
        )
    else:
        diags.error(
            "unterminated_block",
            "Bloco REPEAT não foi terminado com UNTIL antes do fim do "
            "arquivo.",
            start_tok.location,
            owner_node_id,
        )

    end_loc = start_tok.location
    if stream.match_keyword("END_REPEAT"):
        end_tok = stream.advance()
        end_loc = end_tok.location
    else:
        diags.error(
            "unterminated_block",
            "Bloco REPEAT não foi terminado com END_REPEAT antes do fim do "
            "arquivo.",
            start_tok.location,
            owner_node_id,
        )

    _consume_optional_semicolon(stream)

    result.statements.append(
        Statement(
            node_id=node_id,
            file=file,
            kind="repeat",
            location=start_tok.location,
            end_location=end_loc,
        )
    )
    return result


# ---------------------------------------------------------------------------
# RETURN
# ---------------------------------------------------------------------------


def _parse_return(
    stream: _TokenStream,
    file: str,
    owner_node_id: str,
    allocator: _NodeIdAllocator,
    diags: DiagnosticsCollector,
) -> _ParseResult:
    result = _ParseResult()
    start_tok = stream.advance()  # 'RETURN'
    node_id = allocator.next("stmt")

    end_loc = start_tok.location
    if stream.peek().kind == "PUNCTUATION" and stream.peek().text == ";":
        stream.advance()
    else:
        nxt = stream.peek()
        if nxt.kind not in ("EOF",):
            diags.warning(
                "missing_statement_terminator",
                f"Esperado ';' após RETURN, encontrado {nxt.kind} "
                f"{nxt.text!r}.",
                nxt.location,
                node_id,
            )

    result.statements.append(
        Statement(
            node_id=node_id,
            file=file,
            kind="return",
            location=start_tok.location,
            end_location=end_loc,
        )
    )
    return result

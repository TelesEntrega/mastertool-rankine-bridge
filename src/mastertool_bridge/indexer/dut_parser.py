"""Parser tolerante de `declaration.st` de DUT (Data Unit Type: `TYPE ... END_TYPE`).

Terceiro nível de fallback da cadeia `parse_declaration` -> `parse_gvl_declaration`
-> `parse_dut_declaration` (ver `export_loader.py`). Um DUT nunca tem cabeçalho
de POU (PROGRAM/FUNCTION_BLOCK/FUNCTION) nem bloco VAR_GLOBAL — começa
literalmente com o token `TYPE`, seguido de um nome, `:`, e então uma das três
formas reconhecidas nesta fase:

    a. `TYPE <nome> : STRUCT ... END_STRUCT END_TYPE` -> kind="struct".
    b. `TYPE <nome> : <OutroNome>; END_TYPE` (sem STRUCT/parênteses) -> kind="alias".
    c. `TYPE <nome> : ( ... ) ... END_TYPE` (ENUM) -> kind="unknown" (fora de
       escopo nesta fatia — apenas reconhecido como tipo existente).

Qualquer outra coisa (incluindo texto vazio, ou algo que nem começa com
`TYPE`) -> `(None, diags)` com diagnostic `dut_header_not_found`, mesma
convenção de `pou_header_not_found`/`gvl_header_not_found`, para que
`export_loader.py` desista graciosamente deste objeto.

Mesma filosofia de tolerância a erro do restante do indexador: construção não
reconhecida vira `Diagnostic` e o parser CONTINUA best-effort — nunca lança
exceção.
"""

from __future__ import annotations

from mastertool_bridge.indexer.declaration_parser import (
    _TokenStream,
    _parse_one_declaration_line,
)
from mastertool_bridge.indexer.diagnostics import DiagnosticsCollector
from mastertool_bridge.indexer.models import TypeSymbol, VariableDeclaration
from mastertool_bridge.indexer.st_lexer import tokenize

# Membros de STRUCT reaproveitam VariableDeclaration (ver models.py) com este
# valor constante de `scope`, nunca confundido com VAR/VAR_GLOBAL existentes.
STRUCT_MEMBER_SCOPE = "STRUCT_MEMBER"


def parse_dut_declaration(
    text: str, file: str, node_id: str, type_name: str
) -> tuple[TypeSymbol | None, DiagnosticsCollector]:
    """Faz o parse de um `declaration.st` de DUT.

    `type_name` é usado apenas como identificação de fallback caso o nome não
    possa ser lido do próprio arquivo (na prática o nome sempre vem do
    conteúdo, já que a construção `TYPE <nome> : ...` exige um identificador
    logo após `TYPE`). Retorna `(TypeSymbol, diagnostics)` — `TypeSymbol` é
    `None` se o cabeçalho `TYPE <nome> :` não pôde ser reconhecido.
    """
    diags = DiagnosticsCollector()
    tokens, lex_diags = tokenize(text, file)
    diags.extend(lex_diags)

    stream = _TokenStream(tokens)
    tok = stream.peek()

    if not (tok.kind == "KEYWORD" and tok.text.upper() == "TYPE"):
        diags.error(
            "dut_header_not_found",
            f"Cabeçalho de DUT esperado (TYPE <nome> : ...), encontrado "
            f"{tok.kind} {tok.text!r}. Este arquivo não é uma POU, GVL nem "
            "DUT reconhecível nesta fatia.",
            tok.location,
            node_id,
        )
        return None, diags

    header_location = tok.location
    stream.advance()

    name_tok = stream.peek()
    if name_tok.kind != "IDENTIFIER":
        diags.error(
            "dut_header_not_found",
            f"Nome de tipo esperado após TYPE, encontrado {name_tok.kind} "
            f"{name_tok.text!r}.",
            name_tok.location,
            node_id,
        )
        return None, diags
    name = name_tok.text
    stream.advance()

    colon_tok = stream.peek()
    if not (colon_tok.kind == "PUNCTUATION" and colon_tok.text == ":"):
        diags.error(
            "dut_header_not_found",
            f"Esperado ':' após nome de tipo {name!r} em cabeçalho de DUT, "
            f"encontrado {colon_tok.kind} {colon_tok.text!r}.",
            colon_tok.location,
            node_id,
        )
        return None, diags
    stream.advance()

    body_tok = stream.peek()

    if body_tok.kind == "KEYWORD" and body_tok.text.upper() == "STRUCT":
        return _parse_struct_body(
            stream, file, node_id, name, header_location, diags
        )

    if body_tok.kind == "PUNCTUATION" and body_tok.text == "(":
        return _parse_enum_body(
            stream, file, node_id, name, header_location, diags
        )

    if body_tok.kind in {"IDENTIFIER", "KEYWORD"}:
        return _parse_alias_body(
            stream, file, node_id, name, header_location, diags
        )

    diags.error(
        "dut_header_not_found",
        f"Corpo de DUT não reconhecido após 'TYPE {name} :': "
        f"{body_tok.kind} {body_tok.text!r} (esperado STRUCT, '(' de ENUM, "
        "ou nome de outro tipo para alias).",
        body_tok.location,
        node_id,
    )
    return None, diags


def _parse_alias_body(
    stream: _TokenStream,
    file: str,
    node_id: str,
    name: str,
    header_location,
    diags: DiagnosticsCollector,
) -> tuple[TypeSymbol | None, DiagnosticsCollector]:
    """`TYPE <nome> : <OutroNome>; END_TYPE` — alias simples, sem STRUCT nem
    parênteses. `alias_target` guarda o texto cru do outro nome, sem
    resolver nada (resolução fica para `resolve_alias_target`, FASE 2)."""
    target_tok = stream.peek()
    alias_target = target_tok.text
    stream.advance()

    semi_tok = stream.peek()
    if semi_tok.kind == "PUNCTUATION" and semi_tok.text == ";":
        stream.advance()
    else:
        diags.warning(
            "malformed_declaration_line",
            f"Esperado ';' após alvo de alias {alias_target!r} em "
            f"'TYPE {name} : {alias_target}'.",
            semi_tok.location,
            node_id,
        )

    _expect_end_type(stream, file, node_id, name, diags)

    symbol = TypeSymbol(
        node_id=node_id,
        name=name,
        kind="alias",
        file=file,
        alias_target=alias_target,
        members=[],
        location=header_location,
    )
    return symbol, diags


def _parse_enum_body(
    stream: _TokenStream,
    file: str,
    node_id: str,
    name: str,
    header_location,
    diags: DiagnosticsCollector,
) -> tuple[TypeSymbol | None, DiagnosticsCollector]:
    """`TYPE <nome> : ( ... ) [<tipo_base>]; END_TYPE` — ENUM. Fora de escopo
    nesta fatia: apenas reconhecido como tipo EXISTENTE (kind="unknown"),
    nunca parseado como STRUCT nem lança exceção. Consome de forma bruta até
    END_TYPE (ou EOF), respeitando aninhamento de parênteses."""
    diags.info(
        "enum_type_not_supported_yet",
        f"DUT {name!r} reconhecido como ENUM (lista parentizada de "
        "valores) — parsing de ENUM fica para uma fatia futura. Tipo "
        "existe, mas não é analisável nesta fase.",
        header_location,
        node_id,
    )

    depth = 0
    while True:
        tok = stream.peek()
        if tok.kind == "EOF":
            diags.warning(
                "unterminated_dut_declaration",
                f"DUT {name!r} (ENUM) não foi terminado com END_TYPE antes "
                "do fim do arquivo.",
                tok.location,
                node_id,
            )
            break
        if tok.kind == "PUNCTUATION" and tok.text == "(":
            depth += 1
            stream.advance()
            continue
        if tok.kind == "PUNCTUATION" and tok.text == ")":
            depth = max(0, depth - 1)
            stream.advance()
            continue
        if (
            depth == 0
            and tok.kind == "KEYWORD"
            and tok.text.upper() == "END_TYPE"
        ):
            stream.advance()
            break
        stream.advance()

    symbol = TypeSymbol(
        node_id=node_id,
        name=name,
        kind="unknown",
        file=file,
        alias_target=None,
        members=[],
        location=header_location,
    )
    return symbol, diags


def _parse_struct_body(
    stream: _TokenStream,
    file: str,
    node_id: str,
    name: str,
    header_location,
    diags: DiagnosticsCollector,
) -> tuple[TypeSymbol | None, DiagnosticsCollector]:
    """`TYPE <nome> : STRUCT ... END_STRUCT END_TYPE` -> kind="struct".

    Membros são parseados reaproveitando `_parse_one_declaration_line` de
    `declaration_parser.py` (a mesma função de parsing de UMA linha de
    variável que `gvl_parser.py` já reaproveita para blocos VAR_GLOBAL),
    garantindo suporte idêntico a tipos escalares, tipos definidos pelo
    usuário (texto cru, sem resolução), ARRAY[..] OF X, inicializadores
    `:= valor` crus, e ignorando comentários (já descartados pelo lexer).

    Nota de segurança (FASE 2, não deste parser): um membro cujo
    `declared_type` é o próprio nome do STRUCT (auto-referência) ou um ARRAY
    do próprio tipo é seguro de parsear aqui porque só guardamos o texto cru
    do tipo — nenhuma resolução/recursão acontece neste módulo. A
    responsabilidade de nunca entrar em recursão infinita ao CAMINHAR por
    esse tipo autorreferenciado é do resolver (symbol_resolver.py /
    caminhada de cadeia), não deste parser.
    """
    stream.advance()  # consome STRUCT

    members: list[VariableDeclaration] = []

    while True:
        tok = stream.peek()

        if tok.kind == "KEYWORD" and tok.text.upper() == "END_STRUCT":
            stream.advance()
            break

        if tok.kind == "EOF":
            diags.error(
                "unterminated_dut_declaration",
                f"STRUCT {name!r} não foi terminado com END_STRUCT antes "
                "do fim do arquivo.",
                tok.location,
                node_id,
            )
            symbol = TypeSymbol(
                node_id=node_id,
                name=name,
                kind="struct",
                file=file,
                alias_target=None,
                members=members,
                location=header_location,
            )
            return symbol, diags

        if tok.kind == "KEYWORD" and tok.text.upper() == "TYPE":
            # Novo TYPE começando sem END_STRUCT — desiste do STRUCT atual
            # com o que já foi reconhecido, mesma filosofia de
            # _parse_var_block_body para blocos VAR que nunca fecham.
            diags.error(
                "unterminated_dut_declaration",
                f"STRUCT {name!r} não foi terminado com END_STRUCT antes "
                "de um novo TYPE começar.",
                tok.location,
                node_id,
            )
            symbol = TypeSymbol(
                node_id=node_id,
                name=name,
                kind="struct",
                file=file,
                alias_target=None,
                members=members,
                location=header_location,
            )
            return symbol, diags

        decl_vars, consumed, decl_diags = _parse_one_declaration_line(
            stream, file, node_id, STRUCT_MEMBER_SCOPE, False
        )
        diags.extend(decl_diags)
        members.extend(decl_vars)
        if not consumed:
            stream.advance()

    _expect_end_type(stream, file, node_id, name, diags)

    symbol = TypeSymbol(
        node_id=node_id,
        name=name,
        kind="struct",
        file=file,
        alias_target=None,
        members=members,
        location=header_location,
    )
    return symbol, diags


def _expect_end_type(
    stream: _TokenStream,
    file: str,
    node_id: str,
    name: str,
    diags: DiagnosticsCollector,
) -> None:
    tok = stream.peek()
    if tok.kind == "KEYWORD" and tok.text.upper() == "END_TYPE":
        stream.advance()
        return
    if tok.kind == "EOF":
        diags.warning(
            "unterminated_dut_declaration",
            f"DUT {name!r} não foi terminado com END_TYPE antes do fim do "
            "arquivo.",
            tok.location,
            node_id,
        )
        return
    diags.warning(
        "unterminated_dut_declaration",
        f"Esperado END_TYPE ao final de {name!r}, encontrado {tok.kind} "
        f"{tok.text!r}.",
        tok.location,
        node_id,
    )

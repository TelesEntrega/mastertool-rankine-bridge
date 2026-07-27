"""Parser tolerante de `declaration.st` de GVL (Global Variable List).

Arquivos de GVL não têm cabeçalho PROGRAM/FUNCTION_BLOCK/FUNCTION — começam
direto com bloco(s) `VAR_GLOBAL`, tipicamente precedidos por um pragma
`{attribute 'qualified_only'}` seguido de um bloco `VAR_GLOBAL` vazio (isso é
artefato do exportador do CODESYS, tratado aqui como normal). O nome da GVL
não vem do arquivo — vem da identidade do objeto no export (`SourceFile.name`
via `SourceMap`/metadata.json), por isso é recebido como parâmetro explícito.

Mesma filosofia de tolerância a erro do restante do indexador: construção não
reconhecida vira `Diagnostic` e o parser CONTINUA — nunca lança exceção.
"""

from __future__ import annotations

import re

from mastertool_bridge.indexer.declaration_parser import (
    _TokenStream,
    _parse_var_blocks,
)
from mastertool_bridge.indexer.diagnostics import DiagnosticsCollector
from mastertool_bridge.indexer.models import PouSymbol
from mastertool_bridge.indexer.st_lexer import tokenize

# Aceita variações de aspas simples/duplas ao redor de 'qualified_only'.
_QUALIFIED_ONLY_RE = re.compile(
    r"(?i)\{\s*attribute\s*['\"]qualified_only['\"]\s*\}"
)


def parse_gvl_declaration(
    text: str, file: str, node_id: str | None, gvl_name: str
) -> tuple[PouSymbol | None, DiagnosticsCollector]:
    """Faz o parse de um `declaration.st` de GVL.

    `gvl_name` é o nome do objeto GVL vindo do export (não do conteúdo do
    arquivo). Retorna `PouSymbol` com `pou_kind="GVL"` quando o arquivo
    contém ao menos um bloco `VAR_GLOBAL` reconhecível (mesmo vazio de
    declarações — artefato normal do exportador). Se NENHUM `VAR_GLOBAL`
    for encontrado no arquivo inteiro (ex.: um DUT `TYPE ... END_TYPE`, que
    não é GVL nem POU), retorna `None` para que o chamador (`export_loader`)
    mantenha o diagnóstico genérico de "declaração não reconhecida" em vez
    de rotular incorretamente o objeto como GVL.
    """
    diags = DiagnosticsCollector()
    tokens, lex_diags = tokenize(text, file)
    diags.extend(lex_diags)

    has_var_global = any(
        tok.kind == "KEYWORD" and tok.text.upper() == "VAR_GLOBAL"
        for tok in tokens
    )
    if not has_var_global:
        diags.error(
            "gvl_header_not_found",
            "Nenhum bloco VAR_GLOBAL encontrado — arquivo não parece ser "
            "uma GVL.",
            None,
            node_id,
        )
        return None, diags

    is_qualified_only = any(
        tok.kind == "PRAGMA" and _QUALIFIED_ONLY_RE.match(tok.text)
        for tok in tokens
    )

    stream = _TokenStream(tokens)
    variables, body_diags = _parse_var_blocks(stream, file, node_id)
    diags.extend(body_diags)

    symbol = PouSymbol(
        node_id=node_id or gvl_name,
        pou_kind="GVL",
        name=gvl_name,
        file=file,
        return_type=None,
        extends=None,
        implements=[],
        variables=variables,
        location=None,
        is_qualified_only=is_qualified_only,
    )
    return symbol, diags

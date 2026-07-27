"""Localização HEURÍSTICA de leituras/escritas de um símbolo em código ST.

Classificações: confirmed_write, probable_write, confirmed_read,
probable_read, unknown_usage. Nunca apresente estes resultados como certeza
absoluta — são apoio à revisão humana.
"""

from __future__ import annotations

import re

from mastertool_bridge.constants import (USAGE_CONFIRMED_READ,
                                         USAGE_CONFIRMED_WRITE,
                                         USAGE_PROBABLE_READ,
                                         USAGE_PROBABLE_WRITE, USAGE_UNKNOWN)
from mastertool_bridge.models import ExportedProject, Reference
from mastertool_bridge.utils.text import (line_of_offset, normalize_newlines,
                                          strip_comments, strip_strings)

_CONDITION_KEYWORDS = re.compile(
    r"\b(IF|ELSIF|WHILE|UNTIL|CASE)\b", re.IGNORECASE)


def _line_bounds(text: str, offset: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    if end == -1:
        end = len(text)
    return start, end


def _classify_occurrence(text: str, match: re.Match, symbol: str) -> str:
    # análise por LINHA: em ST uma atribuição fica em uma linha na prática;
    # statements multi-linha viram probable_* (heurística assumida).
    start, end = _line_bounds(text, match.start())
    line = text[start:end]
    rel = match.start() - start
    before = line[:rel]
    after = line[rel + len(match.group(0)):]

    after_stripped = after.lstrip()
    prefix = before.strip()

    # saída de FB: "=> simbolo"
    if prefix.endswith("=>"):
        return USAGE_CONFIRMED_WRITE

    if after_stripped.startswith(":="):
        # dentro de chamada "F(par := x)": escrita no parâmetro do FB
        if before.count("(") > before.count(")"):
            return USAGE_PROBABLE_WRITE
        if prefix == "":
            return USAGE_CONFIRMED_WRITE
        # variável de laço: "FOR i := ..."
        if prefix.upper() == "FOR":
            return USAGE_CONFIRMED_WRITE

    # "simbolo[expr] :=" ou "simbolo.membro :=" no início da linha
    if prefix == "" and re.match(
            r"^\s*(\[[^\]]*\]|\.[A-Za-z_][A-Za-z0-9_.\[\]]*)\s*:=", after):
        return USAGE_PROBABLE_WRITE

    # chamada: "simbolo(" — sem índice de tipos não dá para saber se é
    # função (leitura) ou instância de FB (estado alterado)
    if after_stripped.startswith("("):
        return USAGE_UNKNOWN

    # lado direito de atribuição na mesma linha
    if ":=" in before:
        return USAGE_CONFIRMED_READ

    # dentro de condição IF/WHILE/CASE... na mesma linha
    if _CONDITION_KEYWORDS.search(before):
        return USAGE_CONFIRMED_READ

    return USAGE_PROBABLE_READ


def find_in_text(text: str, symbol: str, object_name: str,
                 file_label: str | None = None) -> list[Reference]:
    source = normalize_newlines(text)
    clean = strip_strings(strip_comments(source))
    # lookbehind exclui "algo.simbolo" (membro de outra variável)
    pattern = re.compile(r"(?<![A-Za-z0-9_.])%s(?![A-Za-z0-9_])" % re.escape(symbol),
                         re.IGNORECASE)
    references: list[Reference] = []
    lines = source.split("\n")
    for match in pattern.finditer(clean):
        usage = _classify_occurrence(clean, match, symbol)
        line_no = line_of_offset(clean, match.start())
        snippet = lines[line_no - 1].strip() if line_no <= len(lines) else ""
        references.append(Reference(
            object_name=object_name, line=line_no, usage=usage,
            snippet=snippet[:200], file=file_label))
    return references


def find_references(project: ExportedProject, symbol: str,
                    include_declarations: bool = False) -> list[Reference]:
    references: list[Reference] = []
    for obj in project.objects:
        label = obj.qualified_name or obj.name
        if obj.implementation:
            references.extend(
                find_in_text(obj.implementation, symbol, label, "implementation.st"))
        if include_declarations and obj.declaration:
            references.extend(
                find_in_text(obj.declaration, symbol, label, "declaration.st"))
    return references


def filter_writes(references: list[Reference]) -> list[Reference]:
    return [r for r in references
            if r.usage in (USAGE_CONFIRMED_WRITE, USAGE_PROBABLE_WRITE)]


def filter_reads(references: list[Reference]) -> list[Reference]:
    return [r for r in references
            if r.usage in (USAGE_CONFIRMED_READ, USAGE_PROBABLE_READ)]

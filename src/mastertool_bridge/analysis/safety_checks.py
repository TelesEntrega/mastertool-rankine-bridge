"""Verificações HEURÍSTICAS de segurança sobre código ST exportado.

Todo resultado é um ALERTA para revisão humana, nunca um diagnóstico
definitivo (finding["heuristic"] é sempre True).
"""

from __future__ import annotations

import re
from collections import defaultdict

from mastertool_bridge.analysis.reference_finder import (filter_reads,
                                                         filter_writes,
                                                         find_in_text)
from mastertool_bridge.analysis.symbol_parser import parse_declaration
from mastertool_bridge.models import ExportedProject, PlcObject
from mastertool_bridge.utils.text import normalize_newlines, strip_comments

_DIRECT_Q_WRITE = re.compile(r"(%Q[XBWDL]?[0-9.]+)\s*:=", re.IGNORECASE)
_FOR_HEADER = re.compile(r"\bFOR\b\s*(.+?)\bTO\b\s*(.+?)(?:\bBY\b|\bDO\b)",
                         re.IGNORECASE | re.DOTALL)
_COMPUTED_INDEX = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\s*\[\s*[^\]\s]*[A-Za-z_+\-*/]")
_POINTER_USE = re.compile(r"\bPOINTER\s+TO\b|\bADR\s*\(|\bREF=|\^", re.IGNORECASE)
_SUSPICIOUS_CONVERSION = re.compile(
    r"\b(?:DWORD|WORD|BYTE|INT|DINT|UINT|UDINT|REAL|LREAL|TIME)_TO_"
    r"(?:DWORD|WORD|BYTE|INT|DINT|UINT|UDINT|REAL|LREAL|TIME|BOOL)\s*\(",
    re.IGNORECASE)
_NUMERIC = re.compile(r"^\s*[0-9]+\s*$")


def _finding(check: str, obj: str, message: str, line: int | None = None) -> dict:
    return {
        "check": check,
        "object": obj,
        "line": line,
        "message": message,
        "heuristic": True,
        "note": "Alerta para revisão humana — não é diagnóstico definitivo.",
    }


def check_object_text(obj: PlcObject) -> list[dict]:
    """Verificações que dependem só do texto do próprio objeto."""
    findings: list[dict] = []
    label = obj.qualified_name or obj.name
    text = strip_comments(normalize_newlines(obj.full_text))
    if not text.strip():
        return findings

    for match in _DIRECT_Q_WRITE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        findings.append(_finding(
            "direct_output_write", label,
            f"Atribuição direta em endereço físico {match.group(1)} "
            "(risco crítico se em produção).", line))

    for match in _FOR_HEADER.finditer(text):
        bound = match.group(2).strip()
        if not _NUMERIC.match(bound):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(_finding(
                "for_bound_not_literal", label,
                f"Laço FOR com limite calculado ({bound[:40]!r}) — verificar "
                "possibilidade de estouro de faixa.", line))

    if _COMPUTED_INDEX.search(text):
        findings.append(_finding(
            "computed_array_index", label,
            "Índice de array calculado em tempo de execução — verificar limites."))

    if _POINTER_USE.search(text):
        findings.append(_finding(
            "pointer_usage", label,
            "Uso de ponteiro/ADR/dereferência — revisar validade e vida útil."))

    if _SUSPICIOUS_CONVERSION.search(text):
        findings.append(_finding(
            "type_conversion", label,
            "Conversão explícita de tipo — verificar perda de faixa/sinal."))

    if obj.declaration:
        symbol = parse_declaration(obj.declaration, obj.name)
        for var in symbol.variables:
            if var.is_retain or var.is_persistent:
                kind = "PERSISTENT" if var.is_persistent else "RETAIN"
                findings.append(_finding(
                    "retain_persistent", label,
                    f"Variável {var.name} declarada {kind} — alterações são de "
                    "risco alto (dados sobrevivem a reinício).", var.line))
            if var.address and var.address.upper().startswith("%Q"):
                findings.append(_finding(
                    "physical_output_variable", label,
                    f"Variável {var.name} mapeada em saída física "
                    f"{var.address} — risco crítico.", var.line))
    return findings


def check_project(project: ExportedProject) -> list[dict]:
    """Verificações do projeto inteiro: múltiplas escritas, escrita sem leitura etc."""
    findings: list[dict] = []
    for obj in project.objects:
        findings.extend(check_object_text(obj))

    # Coletar variáveis de saída/globais declaradas e analisar usos:
    declared: dict[str, str] = {}
    for obj in project.objects:
        if not obj.declaration:
            continue
        symbol = parse_declaration(obj.declaration, obj.name)
        for var in symbol.variables:
            if var.block in ("VAR_GLOBAL", "VAR_OUTPUT") or var.address:
                declared[var.name] = obj.qualified_name or obj.name

    for var_name, declared_in in sorted(declared.items()):
        refs = []
        for obj in project.objects:
            if obj.implementation:
                refs.extend(find_in_text(
                    obj.implementation, var_name,
                    obj.qualified_name or obj.name))
        writes = filter_writes(refs)
        reads = filter_reads(refs)
        writer_objects = {r.object_name for r in writes}
        if len(writer_objects) > 1:
            findings.append(_finding(
                "multiple_writers", declared_in,
                f"Variável {var_name} escrita em múltiplos objetos: "
                f"{', '.join(sorted(writer_objects))} — risco de sobreposição "
                "de comando."))
        if writes and not reads:
            findings.append(_finding(
                "written_never_read", declared_in,
                f"Variável {var_name} é escrita mas nenhuma leitura foi "
                "encontrada (heurística)."))
        if reads and not writes:
            findings.append(_finding(
                "read_never_written", declared_in,
                f"Variável {var_name} é lida mas nenhuma escrita foi "
                "encontrada (pode ser escrita por hardware/comunicação)."))
    return findings


def group_by_check(findings: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        grouped[f["check"]].append(f)
    return dict(grouped)

"""Grafo de chamadas HEURÍSTICO entre POUs do export.

Detecta 'Nome(' no corpo dos objetos quando Nome é outro objeto do projeto.
Não resolve métodos/ações qualificados nem instâncias — limitação registrada.
"""

from __future__ import annotations

import re

from mastertool_bridge.models import ExportedProject
from mastertool_bridge.utils.text import normalize_newlines, strip_comments, strip_strings


def build_call_graph(project: ExportedProject) -> dict:
    names = {obj.name: (obj.qualified_name or obj.name) for obj in project.objects}
    edges: list[dict] = []
    for obj in project.objects:
        if not obj.implementation:
            continue
        text = strip_strings(strip_comments(normalize_newlines(obj.implementation)))
        source = obj.qualified_name or obj.name
        for name, target in names.items():
            if target == source:
                continue
            if re.search(r"(?<![A-Za-z0-9_.])%s\s*\(" % re.escape(name), text,
                         re.IGNORECASE):
                edges.append({"from": source, "to": target})
    return {
        "schema_version": "1.0",
        "heuristic": True,
        "nodes": sorted(names.values()),
        "edges": edges,
        "limitations": [
            "Chamadas via instância de FB (inst()) não são atribuídas ao tipo.",
            "Métodos/ações qualificados (obj.Metodo()) não são resolvidos.",
        ],
    }


def to_mermaid(graph: dict) -> str:
    lines = ["graph TD"]
    for edge in graph["edges"]:
        a = edge["from"].replace(".", "_")
        b = edge["to"].replace(".", "_")
        lines.append(f"    {a}[{edge['from']}] --> {b}[{edge['to']}]")
    if len(lines) == 1:
        lines.append("    vazio[Nenhuma chamada detectada]")
    return "\n".join(lines) + "\n"

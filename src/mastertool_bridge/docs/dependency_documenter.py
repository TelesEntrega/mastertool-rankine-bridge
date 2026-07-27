"""Documentação de dependências entre objetos (usa o grafo de chamadas)."""

from __future__ import annotations

from mastertool_bridge.analysis.call_graph import build_call_graph, to_mermaid
from mastertool_bridge.models import ExportedProject


def document_dependencies(project: ExportedProject) -> str:
    graph = build_call_graph(project)
    lines = [
        f"# Dependências — {project.name}",
        "",
        "> Grafo HEURÍSTICO de chamadas; ver limitações abaixo.",
        "",
        "```mermaid",
        to_mermaid(graph).rstrip(),
        "```",
        "",
        "## Limitações",
    ]
    lines += [f"- {l}" for l in graph["limitations"]]
    return "\n".join(lines) + "\n"

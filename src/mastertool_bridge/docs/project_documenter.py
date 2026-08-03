"""Documentação Markdown de um export (inventário do projeto)."""

from __future__ import annotations

from mastertool_bridge.analysis.symbol_parser import parse_declaration
from mastertool_bridge.models import ExportedProject
from mastertool_bridge.utils.timestamps import now_iso


def document_project(project: ExportedProject) -> str:
    lines = [
        f"# Projeto {project.name}",
        "",
        f"Documentação gerada automaticamente em {now_iso()} a partir de "
        f"`{project.export_dir}`. Somente leitura.",
        "",
        "## Inventário",
        "",
        "| Tipo | Quantidade |",
        "|------|-----------:|",
    ]
    grouped = project.objects_by_type()
    for object_type in sorted(grouped):
        lines.append(f"| {object_type} | {len(grouped[object_type])} |")
    lines.append(f"| **total** | {len(project.objects)} |")

    for object_type in sorted(grouped):
        lines += ["", f"## {object_type}", ""]
        for obj in sorted(grouped[object_type], key=lambda o: o.name):
            lines.append(f"### {obj.qualified_name or obj.name}")
            lines.append("")
            if obj.declaration:
                symbol = parse_declaration(obj.declaration, obj.name)
                if symbol.extends:
                    lines.append(f"- Estende: `{symbol.extends}`")
                inputs = symbol.variables_in_block("VAR_INPUT")
                outputs = symbol.variables_in_block("VAR_OUTPUT")
                if inputs:
                    lines.append("- Entradas: " + ", ".join(
                        f"`{v.name}: {v.var_type}`" for v in inputs))
                if outputs:
                    lines.append("- Saídas: " + ", ".join(
                        f"`{v.name}: {v.var_type}`" for v in outputs))
                if symbol.uncertainties:
                    lines.append(f"- Incertezas do parser: {len(symbol.uncertainties)}")
            else:
                lines.append("- (sem declaração textual exportada)")
            lines.append("")
    return "\n".join(lines)

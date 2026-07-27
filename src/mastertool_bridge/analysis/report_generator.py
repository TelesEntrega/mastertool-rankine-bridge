"""Relatórios Markdown das análises (sempre marcados como heurísticos)."""

from __future__ import annotations

from mastertool_bridge.analysis.safety_checks import group_by_check
from mastertool_bridge.models import ExportedProject
from mastertool_bridge.utils.timestamps import now_iso


def safety_report_markdown(project: ExportedProject, findings: list[dict]) -> str:
    lines = [
        f"# Relatório de verificações de segurança — {project.name}",
        "",
        f"Gerado em {now_iso()} a partir de `{project.export_dir}`.",
        "",
        "> **Aviso:** todos os itens abaixo são resultados HEURÍSTICOS, "
        "para revisão humana. Nenhum deve ser tratado como erro confirmado.",
        "",
        f"Total de alertas: **{len(findings)}**",
    ]
    for check, items in sorted(group_by_check(findings).items()):
        lines += ["", f"## {check} ({len(items)})", ""]
        for item in items:
            location = f" (linha {item['line']})" if item.get("line") else ""
            lines.append(f"- `{item['object']}`{location}: {item['message']}")
    lines.append("")
    return "\n".join(lines)

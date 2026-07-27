"""Monta os artefatos de `workspace/analysis/static-api/` a partir do JSON
bruto gerado por `tools/static-api-catalog.ps1` (reflection estática, sem
execução de código .NET).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mastertool_bridge.static_api.classifier import classify_type_members

NAVIGATION_KEYWORDS = (
    "get_children", "find", "parent", "is_root", "handle", "project",
    "active_application", "all", "primary", "path", "is_folder", "type",
    "guid", "index", "get_name", "get_by_path",
)

TEXT_ACCESS_KEYWORDS = (
    "textual_declaration", "textual_implementation", "has_textual_declaration",
    "has_textual_implementation", "text", "length", "linecount", "get_line",
    "get_text", "replace_line", "append", "insert", "remove",
)

CREATION_KEYWORDS = (
    "create", "add", "insert", "open", "import", "convert", "document",
    "save", "close", "remove", "rename", "move", "replace", "append",
    "export",
)

COMPILATION_KEYWORDS = (
    "build", "rebuild", "clean", "generate_code", "create_boot_application",
    "create_task_configuration",
)


def load_raw_catalog(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def annotate_catalog(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return [classify_type_members(t) for t in raw.get("types", [])]


def _iter_members(catalog: list[dict[str, Any]]):
    for type_entry in catalog:
        for prop in type_entry.get("properties", []):
            yield type_entry["full_name"], "property", prop
        for method in type_entry.get("methods", []):
            yield type_entry["full_name"], "method", method


def _matches(name: str, keywords: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return any(kw in lowered for kw in keywords)


def _filter_by_keywords(catalog: list[dict[str, Any]], keywords: tuple[str, ...]):
    matches = []
    for type_name, kind, member in _iter_members(catalog):
        if _matches(member["name"], keywords):
            # "declaring_type" (nao "type"): membros de propriedade ja usam
            # a chave "type" para o TIPO .NET DA PROPRIEDADE — sobrescrever
            # com update() apagaria o nome do tipo declarante.
            entry = {"declaring_type": type_name, "member_kind": kind}
            entry.update(member)
            matches.append(entry)
    return matches


def build_navigation_candidates(catalog):
    return _filter_by_keywords(catalog, NAVIGATION_KEYWORDS)


def build_text_access_candidates(catalog):
    return _filter_by_keywords(catalog, TEXT_ACCESS_KEYWORDS)


def build_creation_candidates(catalog):
    return _filter_by_keywords(catalog, CREATION_KEYWORDS)


def build_compilation_candidates(catalog):
    return _filter_by_keywords(catalog, COMPILATION_KEYWORDS)


def render_reachable_types_markdown(catalog: list[dict[str, Any]]) -> str:
    lines = ["# Tipos alcançáveis — catálogo estático", "",
            "Fonte: reflection ESTÁTICA (`Assembly.ReflectionOnlyLoadFrom`), "
            "nenhum código .NET executado. Ver `tools/static-api-catalog.ps1`.",
            ""]
    for t in catalog:
        lines.append(f"## `{t['full_name']}`")
        lines.append(f"- Assembly: `{t.get('assembly')}` v{t.get('assembly_version')}")
        lines.append(f"- Interface: {t['is_interface']} | Enum: {t['is_enum']} | "
                     f"Público: {t['is_public']}")
        if t["is_enum"]:
            lines.append(f"- Valores: {', '.join(t['enum_values'])}")
            lines.append("")
            continue
        if t.get("interfaces"):
            iface_names = [i if i else "<generico sem FullName resolvido>" for i in t["interfaces"]]
            lines.append(f"- Interfaces: {', '.join(iface_names)}")
        if t["properties"]:
            lines.append("")
            lines.append("| Propriedade | Tipo | Leitura | Escrita | Classificação |")
            lines.append("|---|---|---|---|---|")
            for p in t["properties"]:
                lines.append(f"| `{p['name']}` | `{p['type']}` | {p.get('can_read')} "
                            f"| {p.get('can_write')} | **{p['classification']}** |")
        if t["methods"]:
            lines.append("")
            lines.append("| Método | Parâmetros | Retorno | Classificação |")
            lines.append("|---|---|---|---|")
            for m in t["methods"]:
                params = ", ".join(f"{p['type']} {p['name']}" for p in m.get("parameters", []))
                lines.append(f"| `{m['name']}` | {params or '—'} | `{m['return_type']}` "
                            f"| **{m['classification']}** |")
        lines.append("")
    return "\n".join(lines)


def render_safety_classification_markdown(catalog: list[dict[str, Any]]) -> str:
    lines = ["# Classificação de segurança — todos os membros catalogados", "",
            "> Categorias conservadoras: `read_candidate`, `write_candidate`, "
            "`online_candidate`, `unknown`. Nenhum membro é promovido a "
            "`read_candidate` sem evidência — ver `classifier.py`.", "",
            "| Tipo | Membro | Espécie | Classificação | Nota |",
            "|---|---|---|---|---|"]
    for type_name, kind, member in _iter_members(catalog):
        classification = member.get("classification", "unknown")
        note = member.get("note", "")
        lines.append(f"| `{type_name}` | `{member['name']}` | {kind} "
                     f"| **{classification}** | {note} |")
    lines.append("")
    return "\n".join(lines)


def build_all_artifacts(raw_catalog_path: Path, output_dir: Path) -> dict[str, Path]:
    """Gera todos os artefatos em output_dir a partir do catálogo bruto.
    Retorna dict nome -> caminho gerado."""
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = load_raw_catalog(raw_catalog_path)
    catalog = annotate_catalog(raw)

    paths = {}

    def _write_json(name, data):
        path = output_dir / name
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
                        encoding="utf-8", newline="\n")
        paths[name] = path

    def _write_text(name, text):
        path = output_dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        paths[name] = path

    _write_json("reachable-types.json", {"types": catalog, "not_found": raw.get("not_found", [])})
    _write_text("reachable-types.md", render_reachable_types_markdown(catalog))
    _write_json("project-navigation-candidates.json", build_navigation_candidates(catalog))
    _write_json("text-access-candidates.json", build_text_access_candidates(catalog))
    _write_json("creation-candidates.json", build_creation_candidates(catalog))
    _write_json("compilation-candidates.json", build_compilation_candidates(catalog))
    _write_text("safety-classification.md", render_safety_classification_markdown(catalog))
    return paths

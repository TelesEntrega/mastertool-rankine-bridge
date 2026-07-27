# -*- coding: utf-8 -*-
"""03_list_project_tree.py — Percorre a arvore do projeto aberto.

Para cada objeto registra: caminho completo, nome, tipo (GUID quando
disponivel), pai, profundidade, presenca de declaracao/implementacao textual.
Campos que dependem de API ainda nao confirmada ficam como null.

Saida:
    workspace/exports/<timestamp>_project-tree/project-tree.json
    workspace/exports/<timestamp>_project-tree/project-tree.csv
    workspace/exports/<timestamp>_project-tree/project-tree.md
"""
from __future__ import print_function

import os
import sys

try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _SCRIPT_DIR = os.getcwd()
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
LOG_DIR = os.path.join(REPO_ROOT, "workspace", "logs")
EXPORTS_ROOT = os.path.join(REPO_ROOT, "workspace", "exports")

CSV_COLUMNS = ["path", "name", "depth", "parent", "type_guid", "guid",
               "python_type", "is_folder", "has_declaration",
               "has_implementation", "errors"]


def _csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, list):
        value = "; ".join(str(v) for v in value)
    text = str(value)
    if '"' in text or "," in text or "\n" in text:
        return '"' + text.replace('"', '""') + '"'
    return text


def main():
    print("[INFO] Listagem da arvore do projeto iniciada (somente leitura).")
    try:
        from common import file_io, project_access, safety, tree_walker
        from common.logger import ScriptLogger
        log = ScriptLogger("03_list_project_tree", LOG_DIR)
        log.info(safety.read_only_banner())

        project, err = project_access.get_primary_project(globals())
        if project is None:
            log.error("Sem projeto primario: %s" % err)
            print("[ERROR] Abra um projeto no MasterTool e execute novamente.")
            return

        project_path = project_access.get_project_path(project)
        slug = None
        if project_path:
            slug = os.path.splitext(os.path.basename(project_path))[0]
        out_dir = file_io.new_export_dir(
            EXPORTS_ROOT, (slug or "projeto") + "_tree")

        nodes = []
        errors_total = 0
        for node, _obj in tree_walker.walk(project):
            nodes.append(node)
            if node["errors"]:
                errors_total += 1
            if len(nodes) % 100 == 0:
                log.info("%d objetos percorridos..." % len(nodes))

        report = {
            "schema_version": "1.0",
            "mode": "read_only",
            "generated_at": file_io.iso_now(),
            "project_path": project_path,
            "total_objects": len(nodes),
            "objects_with_errors": errors_total,
            "nodes": nodes,
        }
        file_io.write_json(os.path.join(out_dir, "project-tree.json"), report)

        # CSV
        csv_lines = [",".join(CSV_COLUMNS)]
        for node in nodes:
            csv_lines.append(",".join(_csv_cell(node.get(c)) for c in CSV_COLUMNS))
        file_io.write_text(os.path.join(out_dir, "project-tree.csv"),
                           "\n".join(csv_lines) + "\n")

        # Markdown (arvore indentada)
        md = ["# Arvore do projeto", "",
              "- Projeto: `%s`" % (project_path or "?"),
              "- Objetos: %d (com erros de leitura: %d)" % (len(nodes), errors_total),
              ""]
        for node in nodes:
            flags = []
            if node.get("has_declaration"):
                flags.append("decl")
            if node.get("has_implementation"):
                flags.append("impl")
            if node.get("is_folder"):
                flags.append("pasta")
            suffix = (" [%s]" % ", ".join(flags)) if flags else ""
            md.append("%s- %s%s" % ("  " * node["depth"], node["name"], suffix))
        file_io.write_text(os.path.join(out_dir, "project-tree.md"),
                           "\n".join(md) + "\n")

        log.ok("Arvore exportada: %d objetos em %s" % (len(nodes), out_dir))
        print("[OK] project-tree.json/.csv/.md gerados em:")
        print("     %s" % out_dir)
    except Exception as exc:
        print("[ERROR] Falha ao listar a arvore: %r" % (exc,))
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass


main()

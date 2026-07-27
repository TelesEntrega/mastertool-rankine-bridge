# -*- coding: utf-8 -*-
"""12_validate_recursive_scanner.py — primeira execução real do
`ReadOnlyProjectScanner` (common/read_only_project_scanner.py) contra o
projeto aberto no MasterTool.

Motivo (2026-07-23): depois dos probes 05-10 confirmarem, indice por
indice, que a cadeia `get_children(False)` -> `Count` -> indexador ->
`is_folder`/`type`/`guid`/`get_name(False)` funciona identicamente em
qualquer nivel da arvore, o proximo passo e substituir os probes de um
indice por execucao por UMA varredura completa, com limites rigidos.

Este script NAO reimplementa nenhuma logica de navegacao/seguranca: toda
ela vive em `common/read_only_project_scanner.py` (funcao pura em relacao
a I/O — recebe um `project` ja resolvido, devolve um dict serializavel),
coberta por `tests/unit/test_read_only_project_scanner.py` (31 testes com
fakes em memoria). Este script e so um wrapper fino: resolve
`projects.primary`, executa UMA varredura, e grava os artefatos.

Limites desta PRIMEIRA execucao (mais conservadores que o padrao generico
de config/scanner-defaults.yaml, especificos desta validacao):

    max_depth = 6
    max_total_nodes = 2000
    max_children_per_node = 128
    expected_root_count = 4   # especifico de ExemploPlanta V1.0.project

`expected_root_count=4` e validado SOMENTE na raiz; se divergir, o scanner
registra `root_count_mismatch` e CONTINUA usando o valor observado como
limite real da enumeracao (nunca usa o valor esperado como limite).

Nunca chama outro probe. Nunca executa compilacao ou escrita. `tree_walker.py`
NAO e reativado por este script.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

MAX_DEPTH = 6
MAX_TOTAL_NODES = 2000
MAX_CHILDREN_PER_NODE = 128
EXPECTED_ROOT_COUNT = 4

# Bootstrap (script vive em scripts/mastertool/probes/): sys.path recebe a
# pasta 'mastertool' (onde vive 'common/'), nao a propria pasta 'probes/'.
try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    _MASTERTOOL_DIR = os.path.dirname(_SCRIPT_DIR)
    _FILE_AVAILABLE = True
except NameError:
    _SCRIPT_DIR = None
    _MASTERTOOL_DIR = None
    _FILE_AVAILABLE = False
if _MASTERTOOL_DIR and _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)
REPO_ROOT = os.path.abspath(os.path.join(_MASTERTOOL_DIR, "..", "..")) if _MASTERTOOL_DIR else None
LOG_ROOT = os.path.join(REPO_ROOT, "workspace", "logs") if REPO_ROOT else None


def _summarize_tree_markdown(node, lines, max_lines=200):
    if len(lines) >= max_lines:
        return
    name_field = node["identity"].get("name") if node["identity"] else None
    name = name_field["value"] if name_field and name_field["state"] == "confirmed" else None
    label = name if name is not None else ("(raiz)" if node["node_id"] == "root" else "(sem nome)")
    indent = "  " * node["depth"]
    col = node["collection"]
    lines.append("%s- `%s` — %s (colecao: %s, count=%s)"
                 % (indent, node["node_id"], label, col["state"], col["count"]))
    for child in node["children"]:
        _summarize_tree_markdown(child, lines, max_lines)


def main():
    print("=" * 60)
    print("[INFO] probes/12_validate_recursive_scanner.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. ReadOnlyProjectScanner(max_depth=%s, "
         "max_total_nodes=%s, max_children_per_node=%s, expected_root_count=%s)"
         ".scan(project) — UMA varredura completa. Toda a logica de "
         "seguranca vive em common/read_only_project_scanner.py."
         % (MAX_DEPTH, MAX_TOTAL_NODES, MAX_CHILDREN_PER_NODE, EXPECTED_ROOT_COUNT))

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[BLOQUEADO] __file__ indisponivel: execucao recusada.")
        print("=" * 60)
        return

    try:
        from common import checksums, file_io, project_access, read_only_project_scanner
    except Exception as exc:
        print("[ERROR] Falha ao importar modulos comuns: %r" % (exc,))
        print("=" * 60)
        return

    report = {
        "schema_version": "1.0",
        "script": "probes/12_validate_recursive_scanner.py",
        "generated_at": file_io.iso_now(),
        "mode": "read_only",
        "scanner_config": {
            "max_depth": MAX_DEPTH,
            "max_total_nodes": MAX_TOTAL_NODES,
            "max_children_per_node": MAX_CHILDREN_PER_NODE,
            "expected_root_count": EXPECTED_ROOT_COUNT,
        },
        "baseline": {
            "projects.primary": {
                "previously_confirmed": False,
                "note": "Reutilizado sem re-resolver (ja confirmado em execucoes anteriores).",
            }
        },
        "statistics": None,
        "limits": None,
        "safety_declaration": None,
        "artifacts": {
            "project_tree": "project-tree.json",
            "flat_nodes": "flat-nodes.json",
            "node_indexes": "node-indexes.json",
            "errors": "errors.json",
        },
        "errors": [],
    }

    def _finish(scan_result=None, flat_nodes=None, node_indexes=None):
        run_dir = file_io.new_export_dir(LOG_ROOT, "12_validate_recursive_scanner")
        file_io.write_json(os.path.join(run_dir, "report.json"), report)

        if scan_result is not None:
            file_io.write_json(os.path.join(run_dir, "project-tree.json"), scan_result["tree"])
            file_io.write_json(os.path.join(run_dir, "flat-nodes.json"), flat_nodes)
            file_io.write_json(os.path.join(run_dir, "node-indexes.json"), node_indexes)
            file_io.write_json(os.path.join(run_dir, "errors.json"), scan_result["errors"])

        md = ["# Varredura recursiva somente leitura — ReadOnlyProjectScanner", "",
             "Modo: **somente leitura**. Uma unica varredura, limites: "
             "max_depth=%s, max_total_nodes=%s, max_children_per_node=%s, "
             "expected_root_count=%s." % (MAX_DEPTH, MAX_TOTAL_NODES,
                                         MAX_CHILDREN_PER_NODE, EXPECTED_ROOT_COUNT),
             ""]

        if scan_result is None:
            md.append("Projeto primário indisponível — scan não executado.")
        else:
            stats = scan_result["statistics"]
            limits = scan_result["limits"]
            md += ["## Estatísticas",
                  "- Total de nós: **%s**" % stats["total_nodes"],
                  "- Completos: %s | Parciais: %s | Falhos: %s"
                  % (stats["complete_nodes"], stats["partial_nodes"], stats["failed_nodes"]),
                  "- Coleções lidas: %s | Coleções vazias: %s"
                  % (stats["collections_read"], stats["empty_collections"]),
                  "- Profundidade máxima alcançada: %s" % stats["maximum_depth_reached"],
                  "- Erros de campo: %s | Erros de coleção: %s | Erros de índice: %s"
                  % (stats["field_errors"], stats["collection_errors"], stats["index_errors"]),
                  "- GUIDs de objeto duplicados: %s" % stats["duplicate_object_guids"],
                  "- **Scan completo**: %s" % stats["scan_complete"],
                  "", "## Limites atingidos",
                  "- Profundidade máxima: %s" % limits["max_depth_reached"],
                  "- Total de nós: %s" % limits["max_total_nodes_reached"],
                  "- Filhos por nó: %s" % limits["max_children_per_node_reached"],
                  "", "## Árvore resumida (até 200 linhas)"]
            tree_lines = []
            _summarize_tree_markdown(scan_result["tree"], tree_lines)
            md.extend(tree_lines)

            if scan_result["errors"]:
                md.append("")
                md.append("## Erros/advertências (completos em errors.json, %d no total)"
                          % len(scan_result["errors"]))
                for e in scan_result["errors"][:50]:
                    md.append("- em `%s`: %s" % (e["where"], e["message"]))
                if len(scan_result["errors"]) > 50:
                    md.append("- ... (%d adicionais em errors.json)" % (len(scan_result["errors"]) - 50))

            md.append("")
            md.append("## Declaração de segurança")
            for k, v in sorted(scan_result["safety_declaration"].items()):
                md.append("- %s: %s" % (k, v))

        file_io.write_text(os.path.join(run_dir, "report.md"), "\n".join(md) + "\n")
        checksums.write_checksums_file(run_dir, os.path.join(run_dir, "checksums.sha256"))
        print("[OK] Relatorio gravado em: %s" % run_dir)
        print("=" * 60)

    project, err = project_access.get_primary_project(globals())
    if project is None:
        report["errors"].append({"where": "projects.primary", "message": err})
        print("[WARN] Projeto primario indisponivel: %s" % err)
        _finish()
        return

    report["baseline"]["projects.primary"]["previously_confirmed"] = True
    print("[OK] projects.primary reutilizado.")

    scanner = read_only_project_scanner.ReadOnlyProjectScanner(
        max_depth=MAX_DEPTH, max_total_nodes=MAX_TOTAL_NODES,
        max_children_per_node=MAX_CHILDREN_PER_NODE, expected_root_count=EXPECTED_ROOT_COUNT)
    scan_result = scanner.scan(project)

    flat_nodes = read_only_project_scanner.flatten_tree(scan_result["tree"])
    node_indexes = read_only_project_scanner.build_node_indexes(flat_nodes)

    report["statistics"] = scan_result["statistics"]
    report["limits"] = scan_result["limits"]
    report["safety_declaration"] = scan_result["safety_declaration"]
    report["errors"] = scan_result["errors"]

    stats = scan_result["statistics"]
    print("[%s] scan concluido: total_nodes=%s completos=%s parciais=%s falhos=%s "
         "profundidade_max=%s scan_complete=%s"
         % ("OK" if stats["scan_complete"] else "INFO", stats["total_nodes"],
            stats["complete_nodes"], stats["partial_nodes"], stats["failed_nodes"],
            stats["maximum_depth_reached"], stats["scan_complete"]))

    _finish(scan_result, flat_nodes, node_indexes)


main()

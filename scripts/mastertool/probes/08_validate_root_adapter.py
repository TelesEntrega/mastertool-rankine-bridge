# -*- coding: utf-8 -*-
"""08_validate_root_adapter.py — valida o `ProjectTreeAdapter`
(`common/project_tree_adapter.py`) contra o projeto REAL aberto no
MasterTool, usando `expected_count=4` (valor conhecido de
`ExemploPlanta V1.0.project`, confirmado nos probes 05/06/07) e
`max_children=16` (reduz a superfície durante esta primeira validação —
suficiente para este projeto, nao e um limite permanente da API).

Escopo aprovado (2026-07-23):

    project = projects.primary                          # reutilizado, sem re-resolver
    adapter = ProjectTreeAdapter(project, expected_count=4, max_children=16)
    snapshot = adapter.get_root_children()               # depth=1 (default)

Este script NAO reimplementa nenhuma regra de navegacao: toda a logica de
chamada unica/indexador nativo/sem iteracao/degradacao por campo vive em
`common/project_tree_adapter.py` (ja coberto por
`tests/unit/test_project_tree_adapter.py`, 21 testes com fakes em memoria).
Este script apenas invoca o adaptador contra o projeto real e persiste o
resultado.

PROIBIDO nesta execucao: qualquer navegacao alem do que o proprio adaptador
executa (profundidade > 1, `find(...)`, documentos textuais,
`active_application`, criacao/alteracao, compilacao, salvamento,
exportacao, operacoes online). O adaptador em si ja impoe estas restricoes
por construcao — este script nao adiciona nenhum acesso extra.

`tree_walker.py` NAO e reativado por este script.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

EXPECTED_COUNT = 4
MAX_CHILDREN = 16

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


def main():
    print("=" * 60)
    print("[INFO] probes/08_validate_root_adapter.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. ProjectTreeAdapter(project, "
         "expected_count=%s, max_children=%s).get_root_children() — toda a "
         "logica de seguranca vive em common/project_tree_adapter.py."
         % (EXPECTED_COUNT, MAX_CHILDREN))

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[BLOQUEADO] __file__ indisponivel: execucao recusada.")
        print("=" * 60)
        return

    try:
        from common import (checksums, file_io, project_access,
                            project_tree_adapter)
    except Exception as exc:
        print("[ERROR] Falha ao importar modulos comuns: %r" % (exc,))
        print("=" * 60)
        return

    report = {
        "schema_version": "1.0",
        "script": "probes/08_validate_root_adapter.py",
        "generated_at": file_io.iso_now(),
        "mode": "read_only",
        "adapter_config": {
            "expected_count": EXPECTED_COUNT,
            "max_children": MAX_CHILDREN,
            "depth": 1,
        },
        "baseline": {
            "projects.primary": {
                "previously_confirmed": False,
                "note": "Reutilizado sem re-resolver (ja confirmado em execucoes anteriores).",
            }
        },
        "snapshot": None,
        "simplified": None,
        "errors": [],
        "safety_declaration": {
            "project_write": False,
            "project_save": False,
            "project_close": False,
            "object_creation": False,
            "object_modification": False,
            "collection_iteration": False,
            "recursive_navigation": False,
            "text_document_access": False,
            "compilation": False,
            "online_access": False,
            "device_repository_access": False,
            "download": False,
            "force": False,
            "collection_index_access": True,
            "note": ("Todas as garantias (chamada unica por membro, "
                     "acesso por indice nativo sem iteracao da colecao "
                     "CLR, profundidade fixa em 1, degradacao por campo "
                     "sem stringificacao de objeto CLR desconhecido) sao "
                     "impostas por common/project_tree_adapter.py, nao por "
                     "este script — ver tests/unit/test_project_tree_adapter.py."),
        },
    }

    def _finish():
        run_dir = file_io.new_export_dir(LOG_ROOT, "08_validate_root_adapter")
        file_io.write_json(os.path.join(run_dir, "report.json"), report)

        md = ["# Validação do ProjectTreeAdapter", "",
             "Modo: **somente leitura**. `ProjectTreeAdapter(project, "
             "expected_count=%s, max_children=%s).get_root_children()`."
             % (EXPECTED_COUNT, MAX_CHILDREN), ""]

        snap = report["snapshot"]
        if snap is None:
            md.append("Projeto primário indisponível — snapshot não executado.")
        else:
            col = snap["collection"]
            md += ["## Coleção",
                  "- Estado: **%s** | Count: %s | esperado: %s | bate: %s | max_children: %s"
                  % (col["state"], col["count"], col["expected_count"],
                     col["count_matches_expected"], col["max_children"]),
                  "- Snapshot completo (`complete`): **%s**" % snap["complete"],
                  "", "## Raiz",
                  "- path: estado=%s valor=%s" % (snap["root"]["path"]["state"], snap["root"]["path"]["value"]),
                  "- is_root: estado=%s valor=%s" % (snap["root"]["is_root"]["state"], snap["root"]["is_root"]["value"]),
                  "", "## Filhos (%d)" % len(snap["children"])]
            for child in snap["children"]:
                md.append("- [%d] nome=%s | is_folder=%s | type_guid=%s | object_guid=%s"
                         % (child["index"], child["name"].get("value"),
                            child["is_folder"].get("value"), child["type_guid"].get("value"),
                            child["object_guid"].get("value")))
                for field_name in ("name", "is_folder", "type_guid", "object_guid"):
                    field = child[field_name]
                    if field["state"] != "confirmed":
                        md.append("  - %s: estado=%s erro=%s" % (field_name, field["state"], field["error"]))
            if snap["errors"]:
                md.append("")
                md.append("## Erros do snapshot (completos em report.json)")
                for e in snap["errors"]:
                    md.append("- em `%s`: %s" % (e["where"], e["message"]))

        if report["errors"]:
            md.append("")
            md.append("## Erros do script (completos em report.json)")
            for e in report["errors"]:
                md.append("- em `%s`: %s" % (e["where"], e["message"]))

        md.append("")
        md.append("## Declaração de segurança")
        for k, v in sorted(report["safety_declaration"].items()):
            if k == "note":
                continue
            md.append("- %s: %s" % (k, v))
        file_io.write_text(os.path.join(run_dir, "report.md"), "\n".join(md) + "\n")

        checksums.write_checksums_file(run_dir, os.path.join(run_dir, "checksums.sha256"))
        print("[OK] Relatorio gravado em: %s" % run_dir)
        print("=" * 60)

    project, err = project_access.get_primary_project(globals())
    if project is None:
        report["baseline"]["projects.primary"]["error"] = err
        report["errors"].append({"where": "projects.primary", "message": err})
        print("[WARN] Projeto primario indisponivel: %s" % err)
        _finish()
        return

    report["baseline"]["projects.primary"]["previously_confirmed"] = True
    print("[OK] projects.primary reutilizado.")

    adapter = project_tree_adapter.ProjectTreeAdapter(
        project, expected_count=EXPECTED_COUNT, max_children=MAX_CHILDREN)
    snapshot = adapter.get_root_children()
    report["snapshot"] = snapshot
    report["simplified"] = project_tree_adapter.render_simplified_snapshot(snapshot)

    print("[%s] collection.state=%s count=%s complete=%s"
         % ("OK" if snapshot["collection"]["state"] == "confirmed" else "INFO",
            snapshot["collection"]["state"], snapshot["collection"]["count"], snapshot["complete"]))
    for child in snapshot["children"]:
        print("[INFO] children[%d]: name=%s is_folder=%s"
             % (child["index"], child["name"].get("value"), child["is_folder"].get("value")))

    _finish()


main()

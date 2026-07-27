# -*- coding: utf-8 -*-
"""14_inventory_graphic_pous.py — primeira execucao real do
`GraphicLanguageInventory` (common/graphic_language_inventory.py) contra a
Application do projeto aberto no MasterTool (Fase L0,
docs/14-ladder-roadmap.md: "Inventario e classificacao").

Motivo (2026-07-24): depois do exportador textual (`ReadOnlyTextExporter`,
probe 13) confirmar em runtime real (ExemploPlanta V1.0.project) a navegacao
completa da subarvore da Application COM leitura de conteudo textual
(declaracao/implementacao ST), esta fase reusa a MESMA navegacao e os MESMOS
2 indicadores tri-state ja confirmados (`has_textual_declaration`/
`has_textual_implementation`), mas SEM ler nenhum `.text` — so classifica
cada no em 4 estados (supported/partially_supported/unsupported/unknown),
segundo a regra documentada em `common/graphic_language_inventory.py`.

Este script NAO reimplementa nenhuma logica de navegacao/seguranca/
classificacao: toda ela vive em `common/graphic_language_inventory.py`
(classe `GraphicLanguageInventory`, pura em relacao a I/O), coberta por
`tests/unit/test_graphic_language_inventory.py`. Este script e so um wrapper
fino: resolve `projects.primary`, acessa `active_application`, valida a
identidade da Application ANTES de navegar (mesmos expected_* de
probe 13 — especificos de ExemploPlanta V1.0.project; se divergir, registra o
relatorio e ENCERRA sem prosseguir), executa UM inventario e grava os 4
artefatos exigidos pelo roadmap.

Limites (MESMOS valores ja usados/aprovados por probe 13, ver
docs/14-ladder-roadmap.md):

    max_depth = 8
    max_total_nodes = 1000
    max_children_per_node = 128
    expected_application_name = "Application"
    expected_application_type_guid = "639b491f-5557-464c-af91-1471bac9f549"
    expected_application_guid = "00000000-0000-0000-0000-000000000001"

IMPORTANTE: este script NAO deve ser executado dentro do MasterTool real
pelo agente que o criou — isso e responsabilidade do usuario, somente apos
aprovacao explicita. Nunca chama outro probe. Nunca compila, nunca salva,
nunca acessa online, nunca le conteudo textual (`.text`).

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

MAX_DEPTH = 8
MAX_TOTAL_NODES = 1000
MAX_CHILDREN_PER_NODE = 128
EXPECTED_APPLICATION_NAME = "Application"
EXPECTED_APPLICATION_TYPE_GUID = "639b491f-5557-464c-af91-1471bac9f549"
EXPECTED_APPLICATION_GUID = "00000000-0000-0000-0000-000000000001"

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
EXPORT_ROOT = os.path.join(REPO_ROOT, "workspace", "exports") if REPO_ROOT else None


def _summarize_tree_markdown(node, lines, max_lines=200):
    if len(lines) >= max_lines:
        return
    name_field = node["identity"].get("name") if node["identity"] else None
    name = name_field["value"] if name_field and name_field["state"] == "confirmed" else None
    label = name if name is not None else ("(Application)" if node["node_id"] == "application" else "(sem nome)")
    indent = "  " * node["depth"]
    col = node["collection"]
    state = node.get("state")
    lines.append("%s- `%s` — %s [**%s**] (colecao: %s, count=%s)"
                 % (indent, node["node_id"], label, state, col["state"], col["count"]))
    for child in node["children"]:
        _summarize_tree_markdown(child, lines, max_lines)


def main():
    print("=" * 60)
    print("[INFO] probes/14_inventory_graphic_pous.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. GraphicLanguageInventory(max_depth=%s, "
         "max_total_nodes=%s, max_children_per_node=%s).inventory(application) "
         "— UM inventario completo. Nenhum .text lido (so indicadores "
         "booleanos). Toda a logica vive em "
         "common/graphic_language_inventory.py."
         % (MAX_DEPTH, MAX_TOTAL_NODES, MAX_CHILDREN_PER_NODE))

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[BLOQUEADO] __file__ indisponivel: execucao recusada.")
        print("=" * 60)
        return

    try:
        from common import checksums, file_io, project_access, graphic_language_inventory
    except Exception as exc:
        print("[ERROR] Falha ao importar modulos comuns: %r" % (exc,))
        print("=" * 60)
        return

    report = {
        "schema_version": "1.0",
        "script": "probes/14_inventory_graphic_pous.py",
        "generated_at": file_io.iso_now(),
        "mode": "read_only",
        "inventory_config": {
            "max_depth": MAX_DEPTH,
            "max_total_nodes": MAX_TOTAL_NODES,
            "max_children_per_node": MAX_CHILDREN_PER_NODE,
            "expected_application_name": EXPECTED_APPLICATION_NAME,
            "expected_application_type_guid": EXPECTED_APPLICATION_TYPE_GUID,
            "expected_application_guid": EXPECTED_APPLICATION_GUID,
        },
        "baseline": {
            "projects.primary": {
                "previously_confirmed": False,
                "note": "Reutilizado sem re-resolver (ja confirmado em execucoes anteriores).",
            },
            "active_application": {
                "previously_confirmed": False,
                "note": "Membro de IScriptProject, ja confirmado em runtime (probe 04).",
            },
        },
        "application_identity": None,
        "application_identity_mismatch": [],
        "aborted_due_to_identity_mismatch": False,
        "statistics": None,
        "limits": None,
        "safety_declaration": None,
        "artifacts": {
            "graphic_language_inventory": "graphic-language-inventory.json",
            "ladder_objects": "ladder-objects.json",
            "unsupported_objects": "unsupported-objects.json",
            "discovery_report": "ladder-discovery-report.md",
            "errors": "errors.json",
        },
        "errors": [],
    }

    def _finish(inventory_result=None, flat_nodes=None, by_state=None):
        run_dir = file_io.new_export_dir(EXPORT_ROOT, "14_inventory_graphic_pous")

        manifest = {
            "schema_version": "1.0",
            "script": "probes/14_inventory_graphic_pous.py",
            "generated_at": file_io.iso_now(),
            "mode": "read_only",
            "inventory_config": report["inventory_config"],
        }
        file_io.write_json(os.path.join(run_dir, "manifest.json"), manifest)
        file_io.write_json(os.path.join(run_dir, "report.json"), report)

        if inventory_result is not None:
            file_io.write_json(os.path.join(run_dir, "graphic-language-inventory.json"), flat_nodes)
            file_io.write_json(os.path.join(run_dir, "ladder-objects.json"),
                               by_state[graphic_language_inventory.STATE_PARTIALLY_SUPPORTED])
            file_io.write_json(os.path.join(run_dir, "unsupported-objects.json"),
                               by_state[graphic_language_inventory.STATE_UNSUPPORTED])
            file_io.write_json(os.path.join(run_dir, "errors.json"), inventory_result["errors"])
        else:
            file_io.write_json(os.path.join(run_dir, "graphic-language-inventory.json"), [])
            file_io.write_json(os.path.join(run_dir, "ladder-objects.json"), [])
            file_io.write_json(os.path.join(run_dir, "unsupported-objects.json"), [])
            file_io.write_json(os.path.join(run_dir, "errors.json"), report["errors"])

        md = ["# Inventario de objetos de linguagem grafica — GraphicLanguageInventory",
             "", "Fase L0 (docs/14-ladder-roadmap.md). Modo: **somente leitura**. "
             "Nenhum conteudo textual (`.text`) foi lido — so os indicadores "
             "booleanos `has_textual_declaration`/`has_textual_implementation` "
             "ja confirmados em fases anteriores.", "",
             "Limites: max_depth=%s, max_total_nodes=%s, max_children_per_node=%s."
             % (MAX_DEPTH, MAX_TOTAL_NODES, MAX_CHILDREN_PER_NODE), ""]

        if report["aborted_due_to_identity_mismatch"]:
            md.append("## ABORTADO: application_identity_mismatch")
            md.append("")
            md.append("A identidade observada da Application divergiu dos valores "
                     "esperados. Execucao encerrada ANTES de navegar a arvore. Ver "
                     "`application_identity_mismatch` em report.json.")
        elif inventory_result is None:
            md.append("Projeto primario ou Application indisponivel — inventario nao executado.")
        else:
            stats = inventory_result["statistics"]
            limits = inventory_result["limits"]
            counts = stats["state_counts"]
            md += ["## Estatisticas",
                  "- Total de nos: **%s**" % stats["total_nodes"],
                  "- Completos: %s | Parciais: %s | Falhos: %s"
                  % (stats["complete_nodes"], stats["partial_nodes"], stats["failed_nodes"]),
                  "- Colecoes lidas: %s | Colecoes vazias: %s"
                  % (stats["collections_read"], stats["empty_collections"]),
                  "- Profundidade maxima alcancada: %s" % stats["maximum_depth_reached"],
                  "", "## Classificacao (Fase L0)",
                  "- supported: **%s**" % counts["supported"],
                  "- partially_supported: **%s**" % counts["partially_supported"],
                  "- unsupported: **%s**" % counts["unsupported"],
                  "- unknown: **%s**" % counts["unknown"],
                  "", "## Erros",
                  "- Erros de campo: %s | Erros de colecao: %s | Erros de indice: %s"
                  % (stats["field_errors"], stats["collection_errors"], stats["index_errors"]),
                  "- GUIDs de objeto duplicados: %s" % stats["duplicate_object_guids"],
                  "- **Scan completo**: %s" % stats["scan_complete"],
                  "", "## Limites atingidos",
                  "- Profundidade maxima: %s" % limits["max_depth_reached"],
                  "- Total de nos: %s" % limits["max_total_nodes_reached"],
                  "- Filhos por no: %s" % limits["max_children_per_node_reached"],
                  "", "## Candidatos partially_supported (ladder-objects.json)"]
            partial_list = by_state[graphic_language_inventory.STATE_PARTIALLY_SUPPORTED]
            if partial_list:
                for entry in partial_list[:100]:
                    md.append("- `%s` — %s (type_guid=%s)"
                             % (entry["node_id"], entry["name"], entry["type_guid"]))
                if len(partial_list) > 100:
                    md.append("- ... (%d adicionais em ladder-objects.json)" % (len(partial_list) - 100))
            else:
                md.append("- (nenhum candidato encontrado nesta execucao)")

            md.append("")
            md.append("## Arvore resumida (ate 200 linhas)")
            tree_lines = []
            _summarize_tree_markdown(inventory_result["tree"], tree_lines)
            md.extend(tree_lines)

            if inventory_result["errors"]:
                md.append("")
                md.append("## Erros/advertencias (completos em errors.json, %d no total)"
                          % len(inventory_result["errors"]))
                for e in inventory_result["errors"][:50]:
                    md.append("- em `%s`: %s" % (e["where"], e["message"]))
                if len(inventory_result["errors"]) > 50:
                    md.append("- ... (%d adicionais em errors.json)" % (len(inventory_result["errors"]) - 50))

            md.append("")
            md.append("## Declaracao de seguranca")
            for k, v in sorted(inventory_result["safety_declaration"].items()):
                md.append("- %s: %s" % (k, v))

        file_io.write_text(os.path.join(run_dir, "ladder-discovery-report.md"), "\n".join(md) + "\n")
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

    try:
        application = getattr(project, "active_application")
    except Exception as exc:
        report["errors"].append({"where": "project.active_application", "message": repr(exc)})
        print("[WARN] project.active_application indisponivel: %r" % (exc,))
        _finish()
        return

    if application is None:
        report["errors"].append({"where": "project.active_application",
                                 "message": "active_application retornou None."})
        print("[WARN] active_application e None.")
        _finish()
        return

    report["baseline"]["active_application"]["previously_confirmed"] = True
    print("[OK] active_application obtida.")

    inventory_engine = graphic_language_inventory.GraphicLanguageInventory(
        max_depth=MAX_DEPTH, max_total_nodes=MAX_TOTAL_NODES,
        max_children_per_node=MAX_CHILDREN_PER_NODE,
        expected_application_name=EXPECTED_APPLICATION_NAME,
        expected_application_type_guid=EXPECTED_APPLICATION_TYPE_GUID,
        expected_application_guid=EXPECTED_APPLICATION_GUID)

    # A classe generica so RELATA divergencia de identidade
    # (application_identity_mismatch); QUEM ABORTA e este script — e faz
    # isso ANTES de navegar a arvore. Para cumprir essa ordem, primeiro
    # sondamos SO a identidade (sem correr inventory() completo), decidimos,
    # e so entao chamamos inventory() de fato quando aprovado.
    identity_mismatches = []
    application_identity = inventory_engine.probe_application_identity(application, identity_mismatches)
    report["application_identity"] = application_identity
    report["application_identity_mismatch"] = [m.to_dict() for m in identity_mismatches]

    if identity_mismatches:
        report["aborted_due_to_identity_mismatch"] = True
        for m in identity_mismatches:
            report["errors"].append({
                "where": "application_identity",
                "message": ("application_identity_mismatch: campo=%s esperado=%r "
                           "observado_state=%s observado_valor=%r"
                           % (m.field, m.expected, m.observed_state, m.observed_value)),
            })
        print("[BLOQUEADO] application_identity_mismatch — encerrando ANTES de navegar a arvore.")
        _finish()
        return

    print("[OK] Identidade da Application confirmada — prosseguindo com o inventario.")

    inventory_result = inventory_engine.inventory(application)

    flat_nodes = graphic_language_inventory.flatten_tree(inventory_result["tree"])
    by_state = graphic_language_inventory.split_by_state(flat_nodes)

    report["statistics"] = inventory_result["statistics"]
    report["limits"] = inventory_result["limits"]
    report["safety_declaration"] = dict(inventory_result["safety_declaration"])
    report["errors"] = inventory_result["errors"]

    stats = inventory_result["statistics"]
    counts = stats["state_counts"]
    print("[%s] inventory concluido: total_nodes=%s completos=%s parciais=%s falhos=%s "
         "supported=%s partially_supported=%s unsupported=%s unknown=%s scan_complete=%s"
         % ("OK" if stats["scan_complete"] else "INFO", stats["total_nodes"],
            stats["complete_nodes"], stats["partial_nodes"], stats["failed_nodes"],
            counts["supported"], counts["partially_supported"], counts["unsupported"],
            counts["unknown"], stats["scan_complete"]))

    _finish(inventory_result, flat_nodes, by_state)


main()

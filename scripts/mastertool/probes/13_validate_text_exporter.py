# -*- coding: utf-8 -*-
"""13_validate_text_exporter.py — primeira execucao real do
`ReadOnlyTextExporter` (common/read_only_text_exporter.py) contra a
Application do projeto aberto no MasterTool.

Motivo (2026-07-23): depois do scanner recursivo (`ReadOnlyProjectScanner`,
probe 12) confirmar em runtime real a navegacao completa da arvore do
projeto (117 nos, 0 erros, ExemploPlanta V1.0.project), este script executa a
mesma filosofia de navegacao, mas entrando pela Application
(`project.active_application`) e adicionando leitura de TEXTO
(declaracao/implementacao ST) por objeto, sempre que os indicadores
booleanos correspondentes vierem CONFIRMADOS.

Este script NAO reimplementa nenhuma logica de navegacao/seguranca/leitura
de texto: toda ela vive em `common/read_only_text_exporter.py` (classe
`ReadOnlyTextExporter`, pura em relacao a I/O), coberta por
`tests/unit/test_read_only_text_exporter.py`. Este script e so um wrapper
fino: resolve `projects.primary`, acessa `active_application`, valida a
identidade da Application ANTES de ler qualquer documento textual (se
divergir dos expected_*, registra o relatorio e ENCERRA sem chamar
`.export()` de novo/sem ler documentos), executa UMA exportacao e grava os
artefatos.

Limites desta PRIMEIRA execucao (mais conservadores que o padrao generico
de config/text-export-defaults.yaml, especificos desta validacao — mesmos
valores da secao `first_validation_run` daquele arquivo):

    max_depth = 8
    max_total_nodes = 1000
    max_children_per_node = 128
    max_text_objects = 300
    max_document_characters = 1000000
    max_total_characters = 15000000
    expected_application_name = "Application"
    expected_application_type_guid = "639b491f-5557-464c-af91-1471bac9f549"
    expected_application_guid = "00000000-0000-0000-0000-000000000001"

Estes valores sao ESPECIFICOS de ExemploPlanta V1.0.project — nunca fixados na
classe generica (`ReadOnlyTextExporter`, cujos expected_* default para
None). Ver docs/api/mastertool-api-observations.md e
workspace/logs/2026-07-23_16-50-37_12_validate_recursive_scanner/project-tree.json
para a origem destes valores (Application em root/1/0/0 da arvore real).

IMPORTANTE: este script NAO deve ser executado dentro do MasterTool real
pelo agente que o criou — isso e responsabilidade do usuario, somente
apos aprovacao explicita. Nunca chama outro probe. Nunca compila, nunca
salva, nunca acessa online.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

MAX_DEPTH = 8
MAX_TOTAL_NODES = 1000
MAX_CHILDREN_PER_NODE = 128
MAX_TEXT_OBJECTS = 300
MAX_DOCUMENT_CHARACTERS = 1000000
MAX_TOTAL_CHARACTERS = 15000000
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
    text = node.get("text") or {}
    decl_state = (text.get("declaration") or {}).get("doc_state")
    impl_state = (text.get("implementation") or {}).get("doc_state")
    text_note = ""
    if decl_state == "saved" or impl_state == "saved":
        text_note = " [decl=%s impl=%s]" % (decl_state, impl_state)
    lines.append("%s- `%s` — %s (colecao: %s, count=%s)%s"
                 % (indent, node["node_id"], label, col["state"], col["count"], text_note))
    for child in node["children"]:
        _summarize_tree_markdown(child, lines, max_lines)


def main():
    print("=" * 60)
    print("[INFO] probes/13_validate_text_exporter.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. ReadOnlyTextExporter(max_depth=%s, "
         "max_total_nodes=%s, max_children_per_node=%s, max_text_objects=%s, "
         "max_document_characters=%s, max_total_characters=%s).export(application) "
         "— UMA exportacao completa. Toda a logica de seguranca vive em "
         "common/read_only_text_exporter.py."
         % (MAX_DEPTH, MAX_TOTAL_NODES, MAX_CHILDREN_PER_NODE, MAX_TEXT_OBJECTS,
            MAX_DOCUMENT_CHARACTERS, MAX_TOTAL_CHARACTERS))

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[BLOQUEADO] __file__ indisponivel: execucao recusada.")
        print("=" * 60)
        return

    try:
        from common import checksums, file_io, project_access, read_only_text_exporter
    except Exception as exc:
        print("[ERROR] Falha ao importar modulos comuns: %r" % (exc,))
        print("=" * 60)
        return

    report = {
        "schema_version": "1.0",
        "script": "probes/13_validate_text_exporter.py",
        "generated_at": file_io.iso_now(),
        "mode": "read_only",
        "exporter_config": {
            "max_depth": MAX_DEPTH,
            "max_total_nodes": MAX_TOTAL_NODES,
            "max_children_per_node": MAX_CHILDREN_PER_NODE,
            "max_text_objects": MAX_TEXT_OBJECTS,
            "max_document_characters": MAX_DOCUMENT_CHARACTERS,
            "max_total_characters": MAX_TOTAL_CHARACTERS,
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
            "application_tree": "application-tree.json",
            "flat_objects": "flat-objects.json",
            "text_index": "text-index.json",
            "errors": "errors.json",
            "objects_dir": "objects/",
        },
        "errors": [],
    }

    def _finish(export_result=None, flat_nodes=None, text_index=None):
        run_dir = file_io.new_export_dir(EXPORT_ROOT, "13_validate_text_exporter")

        manifest = {
            "schema_version": "1.0",
            "script": "probes/13_validate_text_exporter.py",
            "generated_at": file_io.iso_now(),
            "mode": "read_only",
            "exporter_config": report["exporter_config"],
        }
        file_io.write_json(os.path.join(run_dir, "manifest.json"), manifest)
        file_io.write_json(os.path.join(run_dir, "report.json"), report)

        if export_result is not None:
            file_io.write_json(os.path.join(run_dir, "application-tree.json"), export_result["tree"])
            file_io.write_json(os.path.join(run_dir, "flat-objects.json"), flat_nodes)
            file_io.write_json(os.path.join(run_dir, "text-index.json"), text_index)
            file_io.write_json(os.path.join(run_dir, "errors.json"), export_result["errors"])
            written_dirs = read_only_text_exporter.write_text_export_artifacts(export_result, run_dir)
        else:
            file_io.write_json(os.path.join(run_dir, "errors.json"), report["errors"])
            written_dirs = []

        md = ["# Exportacao textual somente leitura — ReadOnlyTextExporter", "",
             "Modo: **somente leitura**. Uma unica exportacao, limites: "
             "max_depth=%s, max_total_nodes=%s, max_children_per_node=%s, "
             "max_text_objects=%s, max_document_characters=%s, "
             "max_total_characters=%s."
             % (MAX_DEPTH, MAX_TOTAL_NODES, MAX_CHILDREN_PER_NODE, MAX_TEXT_OBJECTS,
                MAX_DOCUMENT_CHARACTERS, MAX_TOTAL_CHARACTERS),
             ""]

        if report["aborted_due_to_identity_mismatch"]:
            md.append("## ABORTADO: application_identity_mismatch")
            md.append("")
            md.append("A identidade observada da Application divergiu dos valores "
                     "esperados. Execucao encerrada ANTES de ler qualquer documento "
                     "textual. Ver `application_identity_mismatch` em report.json.")
        elif export_result is None:
            md.append("Projeto primario ou Application indisponivel — export nao executado.")
        else:
            stats = export_result["statistics"]
            limits = export_result["limits"]
            md += ["## Estatisticas",
                  "- Total de nos: **%s**" % stats["total_nodes"],
                  "- Completos: %s | Parciais: %s | Falhos: %s"
                  % (stats["complete_nodes"], stats["partial_nodes"], stats["failed_nodes"]),
                  "- Colecoes lidas: %s | Colecoes vazias: %s"
                  % (stats["collections_read"], stats["empty_collections"]),
                  "- Profundidade maxima alcancada: %s" % stats["maximum_depth_reached"],
                  "- Objetos com texto: %s | Declaracoes salvas: %s | Implementacoes salvas: %s"
                  % (stats["text_object_count"], stats["declarations_saved"], stats["implementations_saved"]),
                  "- Caracteres totais salvos: %s" % stats["total_characters_saved"],
                  "- Documentos descartados (tamanho/total/qtd objetos): %s / %s / %s"
                  % (stats["documents_skipped_size_limit"], stats["documents_skipped_total_limit"],
                     stats["documents_skipped_object_limit"]),
                  "- Erros de campo: %s | Erros de colecao: %s | Erros de indice: %s"
                  % (stats["field_errors"], stats["collection_errors"], stats["index_errors"]),
                  "- GUIDs de objeto duplicados: %s" % stats["duplicate_object_guids"],
                  "- **Scan completo**: %s" % stats["scan_complete"],
                  "", "## Limites atingidos",
                  "- Profundidade maxima: %s" % limits["max_depth_reached"],
                  "- Total de nos: %s" % limits["max_total_nodes_reached"],
                  "- Filhos por no: %s" % limits["max_children_per_node_reached"],
                  "- Objetos textuais: %s" % limits["max_text_objects_reached"],
                  "- Caracteres totais: %s" % limits["max_total_characters_reached"],
                  "", "## Diretorios de objeto gravados: %d" % len(written_dirs),
                  "", "## Arvore resumida (ate 200 linhas)"]
            tree_lines = []
            _summarize_tree_markdown(export_result["tree"], tree_lines)
            md.extend(tree_lines)

            if export_result["errors"]:
                md.append("")
                md.append("## Erros/advertencias (completos em errors.json, %d no total)"
                          % len(export_result["errors"]))
                for e in export_result["errors"][:50]:
                    md.append("- em `%s`: %s" % (e["where"], e["message"]))
                if len(export_result["errors"]) > 50:
                    md.append("- ... (%d adicionais em errors.json)" % (len(export_result["errors"]) - 50))

            md.append("")
            md.append("## Declaracao de seguranca")
            for k, v in sorted(export_result["safety_declaration"].items()):
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

    exporter = read_only_text_exporter.ReadOnlyTextExporter(
        max_depth=MAX_DEPTH, max_total_nodes=MAX_TOTAL_NODES,
        max_children_per_node=MAX_CHILDREN_PER_NODE, max_text_objects=MAX_TEXT_OBJECTS,
        max_document_characters=MAX_DOCUMENT_CHARACTERS, max_total_characters=MAX_TOTAL_CHARACTERS,
        expected_application_name=EXPECTED_APPLICATION_NAME,
        expected_application_type_guid=EXPECTED_APPLICATION_TYPE_GUID,
        expected_application_guid=EXPECTED_APPLICATION_GUID)

    # A classe generica so RELATA divergencia de identidade
    # (application_identity_mismatch); QUEM ABORTA e este script — e faz
    # isso ANTES de qualquer leitura de documento textual. Para cumprir
    # essa ordem, primeiro sondamos SO a identidade (sem correr export()
    # completo, que ja leria texto), decidimos, e so entao chamamos
    # export() de fato quando aprovado.
    identity_mismatches = []
    application_identity = exporter._probe_application_identity(application, identity_mismatches)
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
        print("[BLOQUEADO] application_identity_mismatch — encerrando ANTES de ler "
             "qualquer documento textual.")
        _finish()
        return

    print("[OK] Identidade da Application confirmada — prosseguindo com a exportacao.")

    export_result = exporter.export(application, output_directory=None)

    flat_nodes = read_only_text_exporter.flatten_tree(export_result["tree"])
    text_index = read_only_text_exporter.build_text_index(flat_nodes)

    report["statistics"] = export_result["statistics"]
    report["limits"] = export_result["limits"]
    report["safety_declaration"] = dict(export_result["safety_declaration"])
    report["safety_declaration"]["active_application_used"] = True
    report["errors"] = export_result["errors"]

    stats = export_result["statistics"]
    print("[%s] export concluido: total_nodes=%s completos=%s parciais=%s falhos=%s "
         "objetos_com_texto=%s scan_complete=%s"
         % ("OK" if stats["scan_complete"] else "INFO", stats["total_nodes"],
            stats["complete_nodes"], stats["partial_nodes"], stats["failed_nodes"],
            stats["text_object_count"], stats["scan_complete"]))

    _finish(export_result, flat_nodes, text_index)


main()

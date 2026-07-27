# -*- coding: utf-8 -*-
"""06_first_child_identity.py — acessa EXATAMENTE o primeiro elemento da
colecao de filhos ja confirmada e le somente sua identidade basica.

Escopo aprovado (2026-07-23):

    project = projects.primary
    children = project.get_children(False)   # 1 chamada
    first_child = children[0]                 # SO o indice 0, indexador nativo

Pre-condicoes obrigatorias (se qualquer uma falhar, registra e ENCERRA sem
tocar em first_child — nenhum probe de identidade e tentado):
  - get_children(False) confirmed;
  - Count confirmed E Count > 0;
  - children[0] confirmed.

4 probes ISOLADOS em first_child (uma falha NAO impede os demais):
    is_folder          getattr, valor so registrado se bool
    type               getattr, NAO presume tipo do retorno
    guid               getattr, serializa SO se GetType()==System.Guid;
                       persistence_status sempre 'unverified' aqui
    get_name(False)    chamada de metodo, UMA UNICA vez, SEM fallback p/ True

Classificacao: AttributeError -> unsupported; qualquer outra excecao ->
unknown; leitura/chamada concluida -> confirmed.

Acesso ao indice 0 e feito SOMENTE via `children[0]` (indexador nativo do
Python/IronPython) — NUNCA `children.Item[0]`/`children.get_Item(0)`/
`ElementAt(0)`. Nenhum outro indice e acessado. Nenhuma iteracao (`for`,
`iter()`, `list()`, `GetEnumerator()`, compreensao).

PROIBIDO nesta execucao: first_child.get_children(...)/find(...); acesso a
declaracao/implementacao (textual_declaration/textual_implementation/
has_textual_declaration); acesso ao pai; navegacao recursiva;
active_application; criacao/alteracao; compilacao; salvamento; exportacao;
operacoes online; repr()/str()/ToString() em objeto desconhecido
(representacao SEMPRE via `common/capabilities.py: build_representation()`).

`tree_walker.py` NAO e reativado por este script.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

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


def _empty_type_info():
    return {"module": None, "name": None}


def _empty_dotnet_info():
    return {"full_name": None, "available": False}


def _run_property_probe(capabilities, obj, obj_label, member):
    """getattr isolado + enriquecimento (tipo Python/.NET + representacao
    estrita), sem nenhuma segunda tentativa."""
    r = capabilities.probe_member(obj, obj_label, member,
                                  capabilities.EVIDENCE_STATIC_METADATA, capture_value=True)
    entry = {
        "state": r["state"],
        "duration_ms": r["duration_ms"],
        "exception_type": r.get("exception_type"),
        "exception_message": r.get("exception_message"),
        "python_type": _empty_type_info(),
        "dotnet_type": _empty_dotnet_info(),
        "representation": None,
    }
    if r["state"] == "confirmed" and "raw_value" in r:
        value = r["raw_value"]
        entry["is_null"] = value is None
        entry["python_type"] = capabilities.python_type_info(value)
        entry["dotnet_type"] = capabilities.dotnet_type_info(value)
        entry["representation"] = capabilities.build_representation(
            value, entry["python_type"], entry["dotnet_type"])
    return entry


def main():
    print("=" * 60)
    print("[INFO] probes/06_first_child_identity.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. get_children(False) 1x -> children[0] "
         "1x -> 4 probes isolados de identidade. Sem iteracao, sem outros "
         "indices, sem navegacao recursiva, sem tree_walker.")

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[BLOQUEADO] __file__ indisponivel: execucao recusada.")
        print("=" * 60)
        return

    try:
        from common import capabilities, compatibility, checksums, file_io, project_access
    except Exception as exc:
        print("[ERROR] Falha ao importar modulos comuns: %r" % (exc,))
        print("=" * 60)
        return

    report = {
        "schema_version": "1.0",
        "script": "probes/06_first_child_identity.py",
        "generated_at": file_io.iso_now(),
        "mode": "read_only",
        "collection": {
            "method": "get_children",
            "arguments": [False],
            "call_count": 0,
            "state": None,
            "count": None,
            "count_state": None,
            "iteration_performed": False,
        },
        "element_access": {
            "mode": "indexer",
            "index": 0,
            "access_count": 0,
            "state": None,
            "exception_type": None,
            "exception_message": None,
        },
        "first_child": {
            "python_type": _empty_type_info(),
            "dotnet_type": _empty_dotnet_info(),
            "representation": None,
            "stringification_performed": False,
            "probes": {},
        },
        "errors": [],
        "safety_declaration": {
            "project_write": False,
            "project_save": False,
            "project_close": False,
            "object_creation": False,
            "object_modification": False,
            "collection_iteration": False,
            "multiple_element_access": False,
            "recursive_navigation": False,
            "text_document_access": False,
            "compilation": False,
            "online_access": False,
            "device_repository_access": False,
            "download": False,
            "force": False,
            "collection_index_access": True,
            "accessed_indices": [0],
            "note": ("Garantido por construcao deste arquivo: nenhum call "
                     "site para as operacoes proibidas. Acesso por indice "
                     "(children[0]) e distinto de iteracao — ver "
                     "collection_index_access/accessed_indices."),
        },
    }

    def _finish():
        run_dir = file_io.new_export_dir(LOG_ROOT, "06_first_child_identity")
        file_io.write_json(os.path.join(run_dir, "report.json"), report)

        col = report["collection"]
        ea = report["element_access"]
        fc = report["first_child"]
        md = ["# Probe de identidade do primeiro filho", "",
             "Modo: **somente leitura**. `get_children(False)` 1x → "
             "`children[0]` 1x (indexador nativo) → 4 probes isolados. "
             "Sem iteração, sem outros índices, sem navegação recursiva.",
             "", "## Coleção",
             "- Estado: **%s** | Count: %s (%s) | chamadas: %s"
             % (col["state"], col["count"], col["count_state"], col["call_count"]),
             "", "## Acesso ao elemento",
             "- Modo: %s | índice: %s | tentativas: %s | Estado: **%s**"
             % (ea["mode"], ea["index"], ea["access_count"], ea["state"])]
        if ea.get("exception_type"):
            md.append("- Exceção: `%s`: %s" % (ea["exception_type"], ea["exception_message"]))
        md += ["", "## Primeiro filho",
              "- Tipo .NET: `%s`" % fc["dotnet_type"]["full_name"],
              "- Tipo Python: `%s`" % fc["python_type"]["name"],
              "- Stringificação da instância realizada: %s" % fc["stringification_performed"]]
        if fc.get("representation"):
            rep = fc["representation"]
            md.append("- Representação: modo=`%s`, valor=`%s`" % (rep["mode"], rep["value"]))
        md.append("")
        md.append("### Probes de identidade")
        for name, entry in sorted(fc["probes"].items()):
            md.append("- `%s`: estado=**%s**, duração=%sms"
                     % (name, entry["state"], entry["duration_ms"]))
            if entry.get("exception_type"):
                md.append("  - exceção: `%s`: %s" % (entry["exception_type"], entry["exception_message"]))
            if entry.get("representation"):
                rep = entry["representation"]
                md.append("  - representação: modo=`%s`, valor=`%s`" % (rep["mode"], rep["value"]))
            for extra_key in ("confirmed_as_system_guid", "persistence_status", "call_args"):
                if extra_key in entry:
                    md.append("  - %s: %s" % (extra_key, entry[extra_key]))
        if report["errors"]:
            md.append("")
            md.append("## Erros (completos em report.json)")
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
        report["errors"].append({"where": "projects.primary", "message": err, "traceback": None})
        print("[WARN] Projeto primario indisponivel: %s" % err)
        _finish()
        return

    # --- 1. get_children(False), UMA UNICA chamada -------------------------
    col = report["collection"]
    children = None
    try:
        col["call_count"] = 1
        children = project.get_children(False)
        col["state"] = "confirmed"
    except Exception as exc:
        col["state"] = "unsupported" if type(exc).__name__ == "AttributeError" else "unknown"
        report["errors"].append({"where": "get_children",
                                 "message": compatibility.safe_repr(exc), "traceback": None})
    print("[%s] get_children(False) -> %s"
         % ("OK" if col["state"] == "confirmed" else "INFO", col["state"]))

    if col["state"] != "confirmed" or children is None:
        _finish()
        return

    # --- 2. Count, UMA UNICA leitura, deve ser confirmado E > 0 -------------
    try:
        count_value = getattr(children, "Count")
        col["count"] = count_value if isinstance(count_value, (bool, int, float)) else None
        col["count_state"] = "confirmed"
    except Exception as exc:
        col["count_state"] = "unsupported" if type(exc).__name__ == "AttributeError" else "unknown"
        report["errors"].append({"where": "children.Count",
                                 "message": compatibility.safe_repr(exc), "traceback": None})
    print("[%s] Count -> %s (valor=%s)"
         % ("OK" if col["count_state"] == "confirmed" else "INFO", col["count_state"], col["count"]))

    if col["count_state"] != "confirmed" or not col["count"] or col["count"] <= 0:
        print("[INFO] Encerrando sem acessar elementos: Count nao confirmado ou <= 0.")
        _finish()
        return

    # --- 3. children[0], UM UNICO acesso por indice (indexador nativo) ------
    ea = report["element_access"]
    first_child = None
    ea["access_count"] = 1
    idx_record = capabilities.probe_indexer_access(
        children, "children", 0, capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
    ea["state"] = idx_record["state"]
    ea["exception_type"] = idx_record.get("exception_type")
    ea["exception_message"] = idx_record.get("exception_message")
    if idx_record["state"] == "confirmed" and "raw_value" in idx_record:
        first_child = idx_record["raw_value"]
    else:
        report["errors"].append({"where": "children[0]",
                                 "message": idx_record.get("exception_message"), "traceback": None})
    print("[%s] children[0] -> %s" % ("OK" if ea["state"] == "confirmed" else "INFO", ea["state"]))

    if ea["state"] != "confirmed" or first_child is None:
        print("[INFO] Encerrando: children[0] nao confirmado.")
        _finish()
        return

    # --- 4. Identidade do primeiro filho: 4 probes ISOLADOS -----------------
    fc = report["first_child"]
    fc["python_type"] = capabilities.python_type_info(first_child)
    fc["dotnet_type"] = capabilities.dotnet_type_info(first_child)
    fc["representation"] = capabilities.build_representation(
        first_child, fc["python_type"], fc["dotnet_type"])
    fc["stringification_performed"] = fc["representation"]["instance_stringification_performed"]
    print("[INFO] first_child: tipo .NET=%s" % fc["dotnet_type"]["full_name"])

    # is_folder
    entry = _run_property_probe(capabilities, first_child, "first_child", "is_folder")
    if entry["state"] == "confirmed" and entry.get("representation", {}).get("mode") == "value":
        val = entry["representation"]["value"]
        entry["value"] = val if isinstance(val, bool) else None
    fc["probes"]["is_folder"] = entry
    print("[%s] first_child.is_folder -> %s" % ("OK" if entry["state"] == "confirmed" else "INFO", entry["state"]))

    # type — NAO presume tipo do retorno
    entry = _run_property_probe(capabilities, first_child, "first_child", "type")
    fc["probes"]["type"] = entry
    print("[%s] first_child.type -> %s (dotnet=%s)"
         % ("OK" if entry["state"] == "confirmed" else "INFO", entry["state"], entry["dotnet_type"]["full_name"]))

    # guid — serializa SO se GetType()==System.Guid; persistence_status sempre unverified
    entry = _run_property_probe(capabilities, first_child, "first_child", "guid")
    if entry["state"] == "confirmed":
        entry["confirmed_as_system_guid"] = entry["dotnet_type"].get("full_name") == "System.Guid"
        entry["persistence_status"] = "unverified"
    fc["probes"]["guid"] = entry
    print("[%s] first_child.guid -> %s (dotnet=%s)"
         % ("OK" if entry["state"] == "confirmed" else "INFO", entry["state"], entry["dotnet_type"]["full_name"]))

    # get_name(False) — chamada de metodo, UMA UNICA vez, SEM fallback p/ True
    r = capabilities.probe_method_call(first_child, "first_child", "get_name", (False,),
                                       capabilities.EVIDENCE_STATIC_METADATA, capture_value=True)
    entry = {
        "state": r["state"], "duration_ms": r["duration_ms"],
        "exception_type": r.get("exception_type"), "exception_message": r.get("exception_message"),
        "call_args": [False],
        "python_type": _empty_type_info(), "dotnet_type": _empty_dotnet_info(),
        "representation": None,
    }
    if r["state"] == "confirmed" and "raw_value" in r:
        value = r["raw_value"]
        entry["python_type"] = capabilities.python_type_info(value)
        entry["dotnet_type"] = capabilities.dotnet_type_info(value)
        entry["representation"] = capabilities.build_representation(
            value, entry["python_type"], entry["dotnet_type"])
        # Registrar o valor textual SO se o tipo real confirmado for System.String.
        if entry["dotnet_type"].get("full_name") == "System.String" and entry["representation"]["mode"] == "value":
            entry["value"] = entry["representation"]["value"]
        else:
            entry["value"] = None
    fc["probes"]["get_name_false"] = entry
    print("[%s] first_child.get_name(False) -> %s (dotnet=%s)"
         % ("OK" if entry["state"] == "confirmed" else "INFO", entry["state"], entry["dotnet_type"]["full_name"]))

    _finish()


main()

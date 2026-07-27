# -*- coding: utf-8 -*-
"""07_remaining_top_level_children.py — le os 3 elementos de topo RESTANTES
da colecao de filhos ja confirmada (indice 0 = "Project Settings" ja lido em
probes/06_first_child_identity.py; NAO repetido aqui).

Escopo aprovado (2026-07-23):

    project = projects.primary
    children = project.get_children(False)   # 1 chamada
    children.Count                            # 1 leitura, DEVE ser == 4

Pre-condicao rigida (se qualquer uma falhar, registra e ENCERRA sem tocar em
nenhum elemento):
  - get_children(False) confirmed;
  - Count confirmed E Count == 4 EXATAMENTE (qualquer outro valor -> a
    estrutura do projeto mudou desde o probe 05/06; abortar, nao presumir
    nada sobre os indices 1/2/3 e registrar 'project_structure_changed').

Acesso aos elementos: SOMENTE os indices 1, 2 e 3, via a tupla local fixa
AUTHORIZED_INDICES = (1, 2, 3) — o loop percorre esta tupla PYTHON, NAO a
colecao do MasterTool (nao ha GetEnumerator()/iter()/list()/compreensao
sobre `children`). Cada indice usa o indexador nativo `children[i]`, nunca
`children.Item[i]`/`children.get_Item(i)`/`ElementAt(i)`.

Por elemento, os MESMOS 4 probes ISOLADOS de probes/06_first_child_identity.py
(uma falha em um probe NAO impede os demais, nem os de outro indice):
    is_folder          getattr, valor so registrado se bool
    type               getattr, NAO presume tipo do retorno
    guid               getattr, serializa SO se GetType()==System.Guid;
                       persistence_status sempre 'unverified' aqui
    get_name(False)    chamada de metodo, UMA UNICA vez, SEM fallback p/ True

O campo de conveniencia `value` de cada probe agora vem DIRETO de
`representation["value"]`/`representation["value_available"]` (corrigido em
common/capabilities.py — ver test_strict_representation.py), sem a checagem
redundante por `dotnet_type.full_name == "System.String"` que fazia o valor
de get_name(False) cair para null indevidamente no probe 06.

Classificacao: AttributeError -> unsupported; qualquer outra excecao ->
unknown; leitura/chamada concluida -> confirmed.

PROIBIDO nesta execucao: children[0] (ja lido, nao repetir); qualquer outro
indice fora de (1, 2, 3); iteracao da colecao; first_child.get_children(...)/
find(...); acesso a declaracao/implementacao (textual_declaration/
textual_implementation/has_textual_declaration); acesso ao pai; navegacao
recursiva; active_application; criacao/alteracao; compilacao; salvamento;
exportacao; operacoes online; repr()/str()/ToString() em objeto desconhecido
(representacao SEMPRE via common/capabilities.py: build_representation()).

`tree_walker.py` NAO e reativado por este script.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

# Acesso SOMENTE a estes 3 indices, via tupla Python local — NAO iteracao da
# colecao do MasterTool. Fixo por construcao: nao calculado a partir de
# Count nem de nenhum outro dado dinamico.
AUTHORIZED_INDICES = (1, 2, 3)

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


def _probe_element_identity(capabilities, element, obj_label):
    """Os mesmos 4 probes isolados de identidade usados em
    probes/06_first_child_identity.py, para UM elemento ja obtido."""
    probes = {}

    entry = _run_property_probe(capabilities, element, obj_label, "is_folder")
    if entry["state"] == "confirmed" and entry.get("representation", {}).get("mode") == "value":
        val = entry["representation"]["value"]
        entry["value"] = val if isinstance(val, bool) else None
    probes["is_folder"] = entry

    entry = _run_property_probe(capabilities, element, obj_label, "type")
    probes["type"] = entry

    entry = _run_property_probe(capabilities, element, obj_label, "guid")
    if entry["state"] == "confirmed":
        entry["confirmed_as_system_guid"] = entry["dotnet_type"].get("full_name") == "System.Guid"
        entry["persistence_status"] = "unverified"
    probes["guid"] = entry

    r = capabilities.probe_method_call(element, obj_label, "get_name", (False,),
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
        # Valor de conveniencia direto da representacao ja estrita — sem
        # checagem redundante por dotnet_type (correcao de 2026-07-23, ver
        # docstring do modulo).
        rep = entry["representation"]
        entry["value"] = rep["value"] if rep["value_available"] else None
    probes["get_name_false"] = entry

    return probes


def main():
    print("=" * 60)
    print("[INFO] probes/07_remaining_top_level_children.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. get_children(False) 1x -> Count deve "
         "ser == 4 -> children[1], children[2], children[3] (tupla fixa "
         "AUTHORIZED_INDICES, NAO iteracao) -> 4 probes isolados por indice. "
         "indice 0 NAO e repetido (ja lido em 06_first_child_identity.py).")

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
        "script": "probes/07_remaining_top_level_children.py",
        "generated_at": file_io.iso_now(),
        "mode": "read_only",
        "collection": {
            "method": "get_children",
            "arguments": [False],
            "call_count": 0,
            "state": None,
            "count": None,
            "count_state": None,
            "expected_count": 4,
            "count_matches_expected": None,
            "iteration_performed": False,
        },
        "element_access": {
            "mode": "indexer",
            "authorized_indices": list(AUTHORIZED_INDICES),
            "accessed_indices": [],
            "access_count": 0,
        },
        "children": [],
        "errors": [],
        "safety_declaration": {
            "project_write": False,
            "project_save": False,
            "project_close": False,
            "object_creation": False,
            "object_modification": False,
            "collection_iteration": False,
            "multiple_element_access": True,
            "recursive_navigation": False,
            "text_document_access": False,
            "compilation": False,
            "online_access": False,
            "device_repository_access": False,
            "download": False,
            "force": False,
            "collection_index_access": True,
            "bounded_index_access": True,
            "accessed_indices": list(AUTHORIZED_INDICES),
            "note": ("Garantido por construcao deste arquivo: nenhum call "
                     "site para as operacoes proibidas. Acesso por indice "
                     "(children[1], children[2], children[3]) via tupla "
                     "Python local fixa (AUTHORIZED_INDICES) — distinto de "
                     "iteracao da colecao do MasterTool. indice 0 NAO "
                     "repetido (ja confirmado em probes/06_first_child_"
                     "identity.py)."),
        },
    }

    def _finish():
        run_dir = file_io.new_export_dir(LOG_ROOT, "07_remaining_top_level_children")
        file_io.write_json(os.path.join(run_dir, "report.json"), report)

        col = report["collection"]
        ea = report["element_access"]
        md = ["# Probe dos elementos de topo restantes (indices 1, 2, 3)", "",
             "Modo: **somente leitura**. `get_children(False)` 1x → `Count` "
             "deve ser exatamente 4 → `children[1]`, `children[2]`, "
             "`children[3]` (tupla fixa, sem iteração da coleção) → 4 "
             "probes isolados por índice. Índice 0 não repetido (já lido em "
             "`06_first_child_identity.py`).",
             "", "## Coleção",
             "- Estado: **%s** | Count: %s (%s) | esperado: %s | bate: %s | chamadas: %s"
             % (col["state"], col["count"], col["count_state"], col["expected_count"],
                col["count_matches_expected"], col["call_count"]),
             "", "## Acesso aos elementos",
             "- Modo: %s | índices autorizados: %s | índices acessados: %s | tentativas: %s"
             % (ea["mode"], ea["authorized_indices"], ea["accessed_indices"], ea["access_count"])]

        for child in report["children"]:
            md.append("")
            md.append("## children[%s]" % child["index"])
            md.append("- Estado do acesso por índice: **%s**" % child["element_access_state"])
            if child.get("exception_type"):
                md.append("  - exceção: `%s`: %s" % (child["exception_type"], child["exception_message"]))
                continue
            md.append("- Tipo .NET: `%s`" % child["dotnet_type"]["full_name"])
            md.append("- Tipo Python: `%s`" % child["python_type"]["name"])
            md.append("- Stringificação da instância realizada: %s" % child["stringification_performed"])
            if child.get("representation"):
                rep = child["representation"]
                md.append("- Representação: modo=`%s`, valor=`%s`" % (rep["mode"], rep["value"]))
            md.append("### Probes de identidade")
            for name, entry in sorted(child["probes"].items()):
                md.append("- `%s`: estado=**%s**, duração=%sms"
                         % (name, entry["state"], entry["duration_ms"]))
                if entry.get("exception_type"):
                    md.append("  - exceção: `%s`: %s" % (entry["exception_type"], entry["exception_message"]))
                if entry.get("representation"):
                    rep = entry["representation"]
                    md.append("  - representação: modo=`%s`, valor=`%s`" % (rep["mode"], rep["value"]))
                if "value" in entry:
                    md.append("  - value: %s" % (entry["value"],))
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

    # --- 2. Count, UMA UNICA leitura, deve ser confirmado E == 4 EXATAMENTE -
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

    col["count_matches_expected"] = (col["count_state"] == "confirmed"
                                     and col["count"] == col["expected_count"])

    if not col["count_matches_expected"]:
        report["errors"].append({
            "where": "children.Count",
            "message": ("project_structure_changed: esperado Count == %s, "
                       "obtido state=%s count=%s. Abortando SEM acessar "
                       "nenhum elemento — a estrutura do projeto pode ter "
                       "mudado desde o probe 05/06."
                       % (col["expected_count"], col["count_state"], col["count"])),
            "traceback": None,
        })
        print("[BLOQUEADO] project_structure_changed: Count != %s. Encerrando "
             "sem acessar elementos." % col["expected_count"])
        _finish()
        return

    # --- 3. children[1], children[2], children[3] — tupla fixa, sem iteracao
    ea = report["element_access"]
    for index in AUTHORIZED_INDICES:
        ea["access_count"] += 1
        ea["accessed_indices"].append(index)

        idx_record = capabilities.probe_indexer_access(
            children, "children", index, capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)

        child_entry = {
            "index": index,
            "element_access_state": idx_record["state"],
            "exception_type": idx_record.get("exception_type"),
            "exception_message": idx_record.get("exception_message"),
            "python_type": _empty_type_info(),
            "dotnet_type": _empty_dotnet_info(),
            "representation": None,
            "stringification_performed": False,
            "probes": {},
        }
        print("[%s] children[%s] -> %s"
             % ("OK" if idx_record["state"] == "confirmed" else "INFO", index, idx_record["state"]))

        if idx_record["state"] != "confirmed" or "raw_value" not in idx_record:
            report["errors"].append({"where": "children[%s]" % index,
                                     "message": idx_record.get("exception_message"), "traceback": None})
            report["children"].append(child_entry)
            continue

        element = idx_record["raw_value"]
        obj_label = "children[%s]" % index
        child_entry["python_type"] = capabilities.python_type_info(element)
        child_entry["dotnet_type"] = capabilities.dotnet_type_info(element)
        child_entry["representation"] = capabilities.build_representation(
            element, child_entry["python_type"], child_entry["dotnet_type"])
        child_entry["stringification_performed"] = \
            child_entry["representation"]["instance_stringification_performed"]
        print("[INFO] children[%s]: tipo .NET=%s" % (index, child_entry["dotnet_type"]["full_name"]))

        child_entry["probes"] = _probe_element_identity(capabilities, element, obj_label)
        for probe_name in ("is_folder", "type", "guid", "get_name_false"):
            entry = child_entry["probes"][probe_name]
            print("[%s] %s.%s -> %s"
                 % ("OK" if entry["state"] == "confirmed" else "INFO", obj_label, probe_name, entry["state"]))

        report["children"].append(child_entry)

    _finish()


main()

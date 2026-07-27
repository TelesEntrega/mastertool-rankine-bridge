# -*- coding: utf-8 -*-
"""10_device_first_child_identity.py — identifica SOMENTE o primeiro filho
de `Device` (`device_children[0]`), sem acessar `active_application` nesta
mesma execucao.

Motivo (2026-07-23): apos o probe 09 confirmar que `Device.get_children(False)`
funciona identicamente a raiz (mesmo tipo concreto, mesmas interfaces,
`Count=2`), o proximo passo aprovado e identificar o PRIMEIRO filho de
Device, mantendo o teste causalmente simples:

    Project -> Device validado -> colecao de 2 filhos validada
    -> Device.children[0] -> identidade basica

A comparacao com `active_application` fica para outro probe — misturar
agora dificultaria isolar exatamente qual acesso causou uma eventual falha.

Toda a logica de seguranca (revalidacao de identidade de Device nesta
mesma execucao, gates de Count == 4 e Count == 2, indexador bounded,
probes isolados de identidade do primeiro filho, restricao de
serializacao de type/guid a valores CONFIRMADOS como System.Guid) vive em
`common/device_first_child_probe.py` (funcao pura, sem I/O — 16 testes com
fakes em memoria em `tests/unit/test_device_first_child_probe.py`,
cobrindo sucesso completo, Count da raiz != 4, identidade de Device
divergente, Count de Device != 2, colecao sem interface de contagem,
falha no indexador 0, falha isolada em cada campo de identidade, garantia
de que device_children[1] nunca e acessado, e garantia de que o primeiro
filho nunca recebe `get_children()`). Este script e so um wrapper fino:
resolve `projects.primary`, chama a funcao pura, e grava o relatorio.

PROIBIDO nesta execucao (garantido por construcao em
common/device_first_child_probe.py, nao repetido aqui): acessar
`device_children[1]`; iterar qualquer colecao; chamar `get_children()` no
primeiro filho; acessar `active_application`; usar `find()`; acessar
documentos textuais; acessar configuracao de hardware; compilar, salvar
ou modificar o projeto; qualquer operacao online.

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


def main():
    print("=" * 60)
    print("[INFO] probes/10_device_first_child_identity.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. Device revalidado (Count==4, "
         "nome/type/guid batem) -> device.get_children(False) 1x -> "
         "Count==2 confirmado -> device_children[0] 1x -> 4 probes "
         "isolados de identidade. Sem device_children[1], sem "
         "active_application, sem find(), sem get_children() no primeiro "
         "filho.")

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[BLOQUEADO] __file__ indisponivel: execucao recusada.")
        print("=" * 60)
        return

    try:
        from common import checksums, file_io, project_access, device_first_child_probe
    except Exception as exc:
        print("[ERROR] Falha ao importar modulos comuns: %r" % (exc,))
        print("=" * 60)
        return

    report = {
        "schema_version": "1.0",
        "script": "probes/10_device_first_child_identity.py",
        "generated_at": file_io.iso_now(),
        "mode": "read_only",
        "limits": {
            "expected_root_count": device_first_child_probe.DEFAULT_EXPECTED_ROOT_COUNT,
            "expected_device_name": device_first_child_probe.DEFAULT_EXPECTED_DEVICE_NAME,
            "expected_device_type_guid": device_first_child_probe.DEFAULT_EXPECTED_DEVICE_TYPE_GUID,
            "expected_device_object_guid": device_first_child_probe.DEFAULT_EXPECTED_DEVICE_OBJECT_GUID,
            "expected_device_children_count": device_first_child_probe.DEFAULT_EXPECTED_DEVICE_CHILDREN_COUNT,
        },
        "baseline": {
            "projects.primary": {
                "previously_confirmed": False,
                "note": "Reutilizado sem re-resolver (ja confirmado em execucoes anteriores).",
            }
        },
        "root_validation": None,
        "device_collection": None,
        "element_access": None,
        "first_child": None,
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
            "device_configuration_access": False,
            "device_repository_access": False,
            "compilation": False,
            "online_access": False,
            "download": False,
            "force": False,
            "active_application_access": False,
            "find_usage": False,
            "first_child_get_children_call": False,
            "root_bounded_index_access": True,
            "device_children_collection_access": True,
            "device_children_bounded_index_access": True,
            "note": ("Toda a garantia de escopo (revalidacao de identidade "
                     "de Device nesta execucao, gates de Count==4/Count==2, "
                     "indexadores limitados a root_children[1] e "
                     "device_children[0], probes isolados de identidade, "
                     "nenhuma chamada a get_children() no primeiro filho) "
                     "e imposta por construcao em "
                     "common/device_first_child_probe.py — ver "
                     "tests/unit/test_device_first_child_probe.py (16 "
                     "testes)."),
        },
    }

    def _finish():
        run_dir = file_io.new_export_dir(LOG_ROOT, "10_device_first_child_identity")
        file_io.write_json(os.path.join(run_dir, "report.json"), report)

        md = ["# Identidade do primeiro filho de Device", "",
             "Modo: **somente leitura**. Device revalidado (Count==4, "
             "nome/type/guid batem) → `device.get_children(False)` 1x → "
             "Count==2 confirmado → `device_children[0]` 1x → 4 probes "
             "isolados de identidade. Sem `device_children[1]`, sem "
             "`active_application`, sem `find()`, sem `get_children()` no "
             "primeiro filho.", ""]

        rv = report["root_validation"]
        dc = report["device_collection"]
        ea = report["element_access"]
        fc = report["first_child"]

        if rv is None:
            md.append("Projeto primário indisponível — probe não executado.")
        else:
            md += ["## Validação da raiz",
                  "- `get_children(False)`: estado=**%s** | Count=%s (esperado=%s, bate=%s)"
                  % (rv["get_children_state"], rv["count"], rv["expected_count"],
                     rv["count_matches_expected"]),
                  "- Acesso a `root_children[%s]`: estado=%s"
                  % (rv["device_index"], rv["element_access_state"]),
                  "", "### Identidade de Device revalidada"]
            for field_name, field in sorted(rv["device_identity"].items()):
                md.append("- `%s`: estado=%s valor=%s bate=%s"
                         % (field_name, field.get("state"), field.get("value"),
                            field.get("matches_expected")))
            md.append("- **Identidade confirmada**: %s" % rv["device_identity_confirmed"])

            md += ["", "## Coleção de filhos de Device",
                  "- Tentativa: %s | Estado: **%s** | is_null: %s"
                  % (dc["attempted"], dc["state"], dc["is_null"]),
                  "- Tipo .NET: `%s`" % dc["dotnet_type"]["full_name"],
                  "- Implementa ICollection/IList: %s" % dc["implements_count_bearing_interface"],
                  "- Count: %s (esperado=%s, bate=%s)"
                  % (dc["count"], dc["expected_count"], dc["count_matches_expected"])]

            md += ["", "## Acesso ao primeiro filho",
                  "- índice: %s | tentativas: %s | Estado: **%s**"
                  % (ea["index"], ea["access_count"], ea["state"])]

            if fc is not None:
                md.append("")
                md.append("### Identidade do primeiro filho")
                for field_name in ("name", "is_folder", "type", "guid"):
                    field = fc[field_name]
                    md.append("- `%s`: estado=**%s** valor=%s"
                             % (field_name, field["state"], field["value"]))
                    if field.get("error"):
                        md.append("  - nota: %s" % field["error"])

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
        report["errors"].append({"where": "projects.primary", "message": err})
        print("[WARN] Projeto primario indisponivel: %s" % err)
        _finish()
        return

    report["baseline"]["projects.primary"]["previously_confirmed"] = True
    print("[OK] projects.primary reutilizado.")

    result = device_first_child_probe.probe_device_first_child(project)
    report["root_validation"] = result["root_validation"]
    report["device_collection"] = result["device_collection"]
    report["element_access"] = result["element_access"]
    report["first_child"] = result["first_child"]
    report["errors"].extend(result["errors"])

    rv = result["root_validation"]
    print("[%s] root_children.Count -> %s (valor=%s)"
         % ("OK" if rv["count_matches_expected"] else "INFO", rv["count_state"], rv["count"]))
    print("[%s] identidade de Device confirmada: %s"
         % ("OK" if rv["device_identity_confirmed"] else "INFO", rv["device_identity_confirmed"]))

    dc = result["device_collection"]
    if dc["attempted"]:
        print("[%s] device.get_children(False) -> %s | Count=%s (bate=%s)"
             % ("OK" if dc["state"] == "confirmed" else "INFO", dc["state"],
                dc["count"], dc["count_matches_expected"]))

    ea = result["element_access"]
    if ea["attempted"]:
        print("[%s] device_children[0] -> %s" % ("OK" if ea["state"] == "confirmed" else "INFO", ea["state"]))

    if result["complete"]:
        fc = result["first_child"]
        print("[INFO] first_child: name=%s is_folder=%s type=%s guid=%s"
             % (fc["name"].get("value"), fc["is_folder"].get("value"),
                fc["type"].get("value"), fc["guid"].get("value")))

    _finish()


main()

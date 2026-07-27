# -*- coding: utf-8 -*-
"""02_dump_api_surface.py — verificador de SUPERFICIE CONHECIDA.

REFORMULADO em 2026-07-23 (nao e mais um "descobridor irrestrito"). Motivo:
o smoke test confirmou que `dir()` pode retornar vazio mesmo para objetos
cujos membros respondem normalmente via getattr (`projects.primary`, tipo
`ExtendedObject[IScriptProject]`). A versao anterior deste script usava
`dir(obj)` para ENUMERAR nomes a testar — nesse tipo de proxy isso produziria
uma lista vazia e o script concluiria (erradamente) que o objeto nao tem
membros.

Este script agora:
  - opera SOMENTE sobre os globais ja confirmados em runtime (`projects`,
    `system`) e o projeto primario, via `common/capabilities.py`;
  - sonda APENAS os membros da whitelist `capabilities.CAPABILITY_PROBES`
    (nenhuma tentativa de nome fora dela);
  - registra `dir()` apenas como campo DIAGNOSTICO (`diagnostic_dir`,
    `authoritative: false`), nunca como base para decidir o que existe;
  - NAO amostra a arvore do projeto (tree_walker.py esta suspenso — ver
    docs/api/mastertool-api-observations.md);
  - NAO invoca metodos, NAO toca "online"/"device_repository".

Para ampliar a whitelist, registre evidencia primeiro em
docs/api/mastertool-api-observations.md e so entao adicione o nome em
CAPABILITY_PROBES.

Saida:
    workspace/logs/<timestamp>_02_dump_api_surface/report.json
    workspace/logs/<timestamp>_02_dump_api_surface/report.md
"""
from __future__ import print_function

import os
import sys

try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    _FILE_AVAILABLE = True
except NameError:
    _SCRIPT_DIR = None
    _FILE_AVAILABLE = False
if _SCRIPT_DIR and _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..")) if _SCRIPT_DIR else None
LOG_ROOT = os.path.join(REPO_ROOT, "workspace", "logs") if REPO_ROOT else None

# Whitelist estrita: apenas globais ja confirmados em runtime (ver
# docs/api/mastertool-api-observations.md). NUNCA inclua "online" ou
# "device_repository" aqui.
GLOBALS_TO_CHECK = ["projects", "system"]


def main():
    print("=" * 60)
    print("[INFO] 02_dump_api_surface.py — verificador de superficie CONHECIDA (nao e mais um dumper irrestrito).")

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[BLOQUEADO] __file__ indisponivel: nao e possivel determinar "
             "com seguranca o diretorio de saida. Execucao recusada.")
        print("=" * 60)
        return

    try:
        from common import capabilities, compatibility, file_io, project_access, safety
        log_banner = safety.read_only_banner()
        print("[INFO] %s" % log_banner)

        report = {
            "schema_version": "2.0",
            "mode": "read_only",
            "generated_at": file_io.iso_now(),
            "role": "known_surface_checker",
            "note": ("Este relatorio so contem membros da whitelist "
                     "capabilities.CAPABILITY_PROBES, verificados por "
                     "sondagem explicita (nao por dir()). Campos "
                     "'diagnostic_dir' sao apenas informativos."),
            "globals_probed": list(GLOBALS_TO_CHECK),
            "objects": [],
            "warnings": [],
        }

        found = compatibility.probe_globals(GLOBALS_TO_CHECK, globals())
        for name in GLOBALS_TO_CHECK:
            obj = found.get(name)
            if obj is None:
                report["warnings"].append(
                    "Global '%s' nao encontrado nesta execucao." % name)
                continue
            result = capabilities.probe_object(
                obj, name, capabilities.EVIDENCE_RUNTIME_CONFIRMED)
            report["objects"].append(result)
            print("[OK] Sondado '%s' (tipo %s): %d membro(s) conhecido(s) "
                 "testado(s)." % (name, result["dotnet_type"],
                                  len(result["known_members"])))

        project, err = project_access.get_primary_project(globals())
        if project is not None:
            result = capabilities.probe_object(
                project, "project", capabilities.EVIDENCE_RUNTIME_CONFIRMED)
            report["objects"].append(result)
            print("[OK] Sondado 'project' (projeto primario, tipo %s): "
                 "%d membro(s) conhecido(s) testado(s)."
                 % (result["dotnet_type"], len(result["known_members"])))
        else:
            report["warnings"].append(
                "Projeto primario indisponivel: %s" % err)

        out_dir = file_io.new_export_dir(LOG_ROOT, "02_dump_api_surface")
        file_io.write_json(os.path.join(out_dir, "report.json"), report)

        md = ["# Superficie CONHECIDA verificada — MasterTool IEC XE", "",
             "Papel: verificador de superficie conhecida (nao e um "
             "descobridor irrestrito). Ver nota no topo do script.", "",
             "Gerado em %s." % report["generated_at"]]
        for entry in report["objects"]:
            md.append("")
            md.append("## %s" % entry["object_label"])
            md.append("- Tipo .NET: `%s`" % entry["dotnet_type"])
            md.append("- Membros conhecidos testados:")
            for member in entry["known_members"]:
                md.append("  - `%s`: %s (tipo do valor: %s)"
                          % (member["member"], member["state"],
                             member["value_type"]))
            dd = entry["diagnostic_dir"]
            md.append("- `dir()` diagnostico (NAO autoritativo): %d membro(s) — %s"
                      % (len(dd["members"]), dd["note"]))
        if report["warnings"]:
            md.append("")
            md.append("## Avisos")
            for w in report["warnings"]:
                md.append("- %s" % w)
        file_io.write_text(os.path.join(out_dir, "report.md"), "\n".join(md) + "\n")

        print("[OK] Relatorio gravado em: %s" % out_dir)
    except Exception as exc:
        print("[ERROR] Falha no verificador de superficie: %r" % (exc,))
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass
    print("=" * 60)


main()

# -*- coding: utf-8 -*-
"""01_discover_environment.py — Inventario do ambiente de scripting.

Investiga: versao do interpretador, objetos globais, 'projects', projeto
primario, propriedades do projeto, servicos de mensagens, mecanismos de
compilacao, APIs de export/import, gerenciador de bibliotecas, arvore de
dispositivos. Nada e modificado; nenhum metodo com efeito colateral e chamado.

Saida:
    workspace/exports/<timestamp>_discovery/environment.json
    workspace/exports/<timestamp>_discovery/environment.md
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

# Nomes plausiveis (ecossistema CODESYS) cuja PRESENCA sera testada.
# Nao presumimos que existem; apenas registramos o resultado.
EXPORT_IMPORT_CANDIDATES = [
    "export_native", "import_native", "export_xml", "import_xml",
    "export_plcopenxml", "import_plcopenxml", "save", "save_as",
]
LIBMGR_CANDIDATES = ["librarymanager", "libmanager"]


def _describe(obj, name, skip_values=False):
    """Descreve um objeto sem invocar metodos (dir + type)."""
    from common import compatibility, project_access
    info = {
        "name": name,
        "available": obj is not None,
        "python_type": None,
        "members": [],
        "notes": [],
    }
    if obj is None:
        return info
    info["python_type"] = compatibility.safe_type_name(obj)
    info["members"] = project_access.safe_dir(obj)
    if skip_values:
        info["notes"].append(
            "Leitura de valores suprimida (risco de efeito colateral).")
    else:
        info["repr"] = compatibility.safe_repr(obj)
    return info


def main():
    print("[INFO] Descoberta do ambiente iniciada (somente leitura).")
    try:
        from common import compatibility, file_io, message_reader, project_access, safety
        from common.logger import ScriptLogger
        log = ScriptLogger("01_discover_environment", LOG_DIR)
        log.info(safety.read_only_banner())

        out_dir = file_io.new_export_dir(EXPORTS_ROOT, "discovery")
        report = {
            "schema_version": "1.0",
            "mode": "read_only",
            "generated_at": file_io.iso_now(),
            "interpreter": {
                "version": compatibility.python_version(),
                "platform": sys.platform,
                "is_ironpython": compatibility.is_ironpython(),
                "executable": getattr(sys, "executable", None),
            },
            "globals_found": {},
            "project": None,
            "messages_and_compile": None,
            "export_import_apis": {},
            "library_manager": None,
            "device_tree_hint": None,
            "warnings": [],
        }

        # 1. Globais do ScriptEngine
        found = compatibility.find_available_globals(globals())
        for name, obj in found.items():
            skip = name in compatibility.SIDE_EFFECT_RISK
            report["globals_found"][name] = _describe(obj, name, skip_values=skip)
        missing = [n for n in compatibility.CANDIDATE_GLOBALS if n not in found]
        if missing:
            report["warnings"].append(
                "Globais candidatos ausentes: %s" % ", ".join(missing))
        log.info("Globais encontrados: %s" % ", ".join(sorted(found.keys())))

        # 2. Projeto primario e seus membros
        project, err = project_access.get_primary_project(globals())
        if project is not None:
            pinfo = _describe(project, "projects.primary")
            pinfo["path"] = project_access.get_project_path(project)
            pinfo["export_import_members_present"] = [
                m for m in EXPORT_IMPORT_CANDIDATES if m in pinfo["members"]]
            report["project"] = pinfo
            log.ok("Projeto primario inventariado: %s" % (pinfo.get("path") or "?"))
        else:
            report["warnings"].append("Projeto primario indisponivel: %s" % err)
            log.warn("Projeto primario indisponivel: %s" % err)

        # 3. Mensagens e compilacao (introspectivo)
        report["messages_and_compile"] = message_reader.describe_message_api(globals())

        # 4. Gerenciador de bibliotecas
        for name in LIBMGR_CANDIDATES:
            obj = found.get(name) or compatibility.get_scriptengine_global(name)
            if obj is not None:
                report["library_manager"] = _describe(obj, name)
                break

        # 5. Arvore de dispositivos: apenas registrar por onde comecar
        if project is not None:
            members = project_access.safe_dir(project)
            hints = [m for m in members
                     if "device" in m.lower() or "children" in m.lower()
                     or m in ("get_children", "active_application")]
            report["device_tree_hint"] = {
                "project_members_related": hints,
                "note": "Percurso real da arvore: usar 03_list_project_tree.py",
            }

        # Gravar saidas
        json_path = os.path.join(out_dir, "environment.json")
        file_io.write_json(json_path, report)

        md = ["# Descoberta do ambiente — MasterTool IEC XE", ""]
        md.append("- Gerado em: %s" % report["generated_at"])
        md.append("- Interpretador: `%s`" % report["interpreter"]["version"])
        md.append("- IronPython: %s" % report["interpreter"]["is_ironpython"])
        md.append("")
        md.append("## Globais do ScriptEngine")
        for name in sorted(report["globals_found"].keys()):
            g = report["globals_found"][name]
            md.append("- **%s** (`%s`): %d membros publicos"
                      % (name, g["python_type"], len(g["members"])))
        if report["project"]:
            md.append("")
            md.append("## Projeto primario")
            md.append("- Caminho: `%s`" % report["project"].get("path"))
            md.append("- Tipo: `%s`" % report["project"].get("python_type"))
            md.append("- APIs de export/import presentes: %s"
                      % (", ".join(report["project"]["export_import_members_present"]) or "nenhuma detectada"))
        if report["warnings"]:
            md.append("")
            md.append("## Avisos")
            for w in report["warnings"]:
                md.append("- %s" % w)
        md.append("")
        md.append("> Copie as observacoes relevantes para "
                  "`docs/api/mastertool-api-observations.md`.")
        file_io.write_text(os.path.join(out_dir, "environment.md"), "\n".join(md) + "\n")

        log.ok("Descoberta concluida. Saida: %s" % out_dir)
        print("[OK] environment.json e environment.md gerados em:")
        print("     %s" % out_dir)
    except Exception as exc:
        print("[ERROR] Falha na descoberta: %r" % (exc,))
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass


main()

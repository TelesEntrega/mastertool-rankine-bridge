# -*- coding: utf-8 -*-
"""00_smoke_test.py — Verifica que o scripting do MasterTool IEC XE funciona.

Execucao: menu de scripting do MasterTool, com um projeto aberto.

Garantias de escopo (validas por construcao deste arquivo — nao dependem do
ambiente real; ver secao "safety_declaration" no relatorio gerado):
  - NUNCA chama build()/rebuild()/clean()/generate_code() ou qualquer outro
    metodo de compilacao;
  - NUNCA acessa o global "online" nem "device_repository": a sondagem de
    globais usa uma whitelist estrita (compatibility.probe_globals) com
    APENAS "projects" e "system" — nomes fora dessa lista jamais sao tocados
    (nem hasattr/getattr), diferente de compatibility.find_available_globals;
  - NUNCA salva, fecha ou cria objetos no projeto;
  - so realiza leituras de propriedades/atributos, nunca escreve;
  - toda excecao e capturada por verificacao individual — uma falha isolada
    nao interrompe o restante do script nem o MasterTool;
  - a saida e gravada em workspace/logs/<timestamp>_00_smoke_test/, fora de
    qualquer pasta de projeto, em um diretorio novo por execucao (nunca
    sobrescreve uma execucao anterior).

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys
import traceback

# --- bootstrap: tornar 'common' importavel e localizar a raiz do repo -------
# Se __file__ nao estiver disponivel, NAO adivinhamos um diretorio de saida:
# escrever em disco fica desabilitado nesta execucao (console-only), para
# nunca arriscar gravar dentro da pasta do projeto por engano.
_FILE_AVAILABLE = True
try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _FILE_AVAILABLE = False
    _SCRIPT_DIR = None
if _SCRIPT_DIR and _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..")) if _SCRIPT_DIR else None
LOG_ROOT = os.path.join(REPO_ROOT, "workspace", "logs") if REPO_ROOT else None
# -----------------------------------------------------------------------------

# Whitelist estrita: NENHUM outro nome e sondado neste script.
GLOBALS_TO_CHECK = ["projects", "system"]


def _new_check():
    return {"name": None, "status": "not_run", "detail": None, "traceback": None}


def _run_check(report, name, func):
    """Executa uma verificacao isolada; falha nela nunca aborta o restante."""
    check = _new_check()
    check["name"] = name
    try:
        detail = func()
        check["status"] = "ok"
        check["detail"] = detail
    except Exception as exc:
        check["status"] = "error"
        check["detail"] = "excecao: %r" % (exc,)
        try:
            check["traceback"] = traceback.format_exc()
        except Exception:
            check["traceback"] = "<traceback indisponivel>"
        report["errors"].append({
            "where": name,
            "message": check["detail"],
            "traceback": check["traceback"],
        })
    report["checks"].append(check)
    return check


def build_report():
    from common import compatibility, project_access

    report = {
        "schema_version": "1.0",
        "script": "00_smoke_test.py",
        "generated_at": datetime.datetime.now().isoformat(),
        "mode": "read_only",
        "globals_probed": list(GLOBALS_TO_CHECK),
        # Campos separados por evidencia (2026-07-23): sys.version NAO da a
        # versao do Python/IronPython neste host — o MasterTool sobrescreve
        # essa string com um banner do produto. Ver docs/03-scripting-discovery.md.
        "interpreter": {
            "platform": None,               # sys.platform (evidencia direta e confiavel)
            "version_banner": None,          # sys.version cru — NAO e um numero de versao aqui
            "version_info": None,            # sys.version_info, se disponivel
            "subversion": None,              # sys.subversion, se disponivel (IronPython antigo)
            "host_executable": None,         # sys.executable, se disponivel
            "scriptengine_plugin_version": None,  # extraido do banner por regex, se possivel
            "ironpython_assembly_version": None,  # nao investigado nesta execucao (ver nota)
            "runtime_family": None,          # "IronPython" | "CPython/desconhecido"
            "runtime_version": "unknown",    # so promovido com evidencia forte (version_info)
            "runtime_version_evidence": None,
            "note": ("sys.version neste host retorna um banner do produto, "
                     "nao um numero de versao. 'runtime_version' so e "
                     "preenchido quando sys.version_info existir; caso "
                     "contrario permanece 'unknown'."),
        },
        "globals_found": {},
        "primary_project": {
            "present": False,
            "dotnet_type": None,
            "path": None,
            "name": None,
            "members": [],
            "error": None,
        },
        "checks": [],
        "errors": [],
        "safety_declaration": {
            # Garantias por CONSTRUCAO deste arquivo (nao ha nenhum call site
            # para essas operacoes em 00_smoke_test.py) — nao sao inferencias
            # de runtime, sao fatos sobre o codigo executado.
            "write_operations_requested": False,
            "compile_requested": False,
            "online_access_requested": False,
            "device_repository_access_requested": False,
            "project_saved": False,
            "project_closed": False,
            "objects_created": False,
            "note": ("Garantido pela whitelist GLOBALS_TO_CHECK = " +
                     repr(GLOBALS_TO_CHECK) + " e pela ausencia de qualquer "
                     "chamada de escrita/compilacao neste arquivo."),
        },
    }

    def _check_interpreter():
        info = report["interpreter"]
        info["platform"] = sys.platform
        try:
            info["version_banner"] = compatibility.python_version()
        except Exception:
            info["version_banner"] = None
        try:
            info["version_info"] = tuple(sys.version_info)
        except Exception:
            info["version_info"] = None
        try:
            info["subversion"] = tuple(sys.subversion)
        except Exception:
            info["subversion"] = None
        try:
            info["host_executable"] = getattr(sys, "executable", None)
        except Exception:
            info["host_executable"] = None

        # Extracao best-effort da versao do plugin ScriptEngine a partir do
        # banner ja capturado (nao sonda nenhum objeto novo).
        try:
            import re
            match = re.search(r"ScriptEngine\.plugin\s+([0-9.]+)",
                              info["version_banner"] or "")
            info["scriptengine_plugin_version"] = match.group(1) if match else None
        except Exception:
            info["scriptengine_plugin_version"] = None

        # Versao do assembly IronPython: nao investigada aqui de proposito
        # (exigiria reflection sobre assemblies carregados, uma ampliacao de
        # escopo fora deste ciclo — ver docs/10-roadmap.md).
        info["ironpython_assembly_version"] = None

        is_iron = compatibility.is_ironpython()
        info["runtime_family"] = "IronPython" if is_iron else "CPython/desconhecido"
        if info["version_info"]:
            info["runtime_version"] = "%s.%s.%s" % (
                info["version_info"][0], info["version_info"][1], info["version_info"][2])
            info["runtime_version_evidence"] = "sys.version_info"
        else:
            info["runtime_version"] = "unknown"
            info["runtime_version_evidence"] = (
                "sys.platform == 'cli'" if is_iron else "sys.platform == %r" % sys.platform)
        return info
    _run_check(report, "interpreter_info", _check_interpreter)

    def _check_globals():
        found = compatibility.probe_globals(GLOBALS_TO_CHECK, globals())
        for name in GLOBALS_TO_CHECK:
            obj = found.get(name)
            report["globals_found"][name] = {
                "present": obj is not None,
                "dotnet_type": compatibility.safe_type_name(obj) if obj is not None else None,
            }
        return report["globals_found"]
    _run_check(report, "globals_projects_system", _check_globals)

    def _check_primary_project():
        project, err = project_access.get_primary_project(globals())
        info = report["primary_project"]
        if project is None:
            info["error"] = err
            return info
        info["present"] = True
        info["dotnet_type"] = compatibility.safe_type_name(project)
        info["path"] = project_access.get_project_path(project)
        info["name"] = project_access.get_object_name(project)
        info["members"] = project_access.safe_dir(project)
        return info
    _run_check(report, "primary_project", _check_primary_project)

    return report


def report_to_markdown(report):
    lines = [
        "# Smoke test — MasterTool IEC XE",
        "",
        "Modo: **somente leitura**. Ver `safety_declaration` em `report.json` "
        "para as garantias de escopo desta execucao.",
        "",
        "- Gerado em: %s" % report["generated_at"],
        "- Globais sondados (whitelist estrita): %s" % ", ".join(report["globals_probed"]),
        "",
        "## Interpretador (campos separados por evidencia — ver nota)",
    ]
    interp = report["interpreter"]
    lines.append("- `sys.platform`: `%s`" % interp.get("platform"))
    lines.append("- `sys.version` (banner cru, NAO e numero de versao aqui): `%s`"
                 % interp.get("version_banner"))
    lines.append("- `sys.version_info`: `%s`" % (interp.get("version_info"),))
    lines.append("- `sys.subversion`: `%s`" % (interp.get("subversion"),))
    lines.append("- `sys.executable`: `%s`" % interp.get("host_executable"))
    lines.append("- Versao do plugin ScriptEngine (extraida do banner): `%s`"
                 % interp.get("scriptengine_plugin_version"))
    lines.append("- Versao do assembly IronPython: `%s` (nao investigado neste ciclo)"
                 % interp.get("ironpython_assembly_version"))
    lines.append("- runtime_family: `%s`" % interp.get("runtime_family"))
    lines.append("- runtime_version: `%s` (evidencia: %s)"
                 % (interp.get("runtime_version"), interp.get("runtime_version_evidence")))
    lines.append("")
    lines.append("## Verificacoes")
    for check in report["checks"]:
        lines.append("- **%s**: %s" % (check["name"], check["status"]))
        if check["detail"] is not None:
            lines.append("  - detalhe: `%r`" % (check["detail"],))
        if check["traceback"]:
            lines.append("  - traceback: ver `report.json`")
    lines.append("")
    lines.append("## Globais")
    for name, info in sorted(report["globals_found"].items()):
        lines.append("- `%s`: presente=%s, tipo=%s"
                     % (name, info["present"], info["dotnet_type"]))
    lines.append("")
    lines.append("## Projeto primario")
    pp = report["primary_project"]
    if pp["present"]:
        lines.append("- Nome: `%s`" % pp["name"])
        lines.append("- Caminho: `%s`" % pp["path"])
        lines.append("- Tipo .NET: `%s`" % pp["dotnet_type"])
        lines.append("- Membros conhecidos: %d" % len(pp["members"]))
    else:
        lines.append("- NAO encontrado. Erro: %s" % pp["error"])
    if report["errors"]:
        lines.append("")
        lines.append("## Erros")
        for e in report["errors"]:
            lines.append("- em `%s`: %s" % (e["where"], e["message"]))
    lines.append("")
    lines.append("## Declaracao de seguranca")
    for key, value in sorted(report["safety_declaration"].items()):
        if key == "note":
            continue
        lines.append("- %s: %s" % (key, value))
    lines.append("")
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("[OK] Script executado.")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] sys.version (banner cru, pode NAO ser um numero de versao "
         "de Python neste host): %s" % sys.version.replace("\n", " "))
    print("[INFO] Plataforma (sys.platform): %s" % sys.platform)
    print("[INFO] MODO SOMENTE LEITURA. Globais sondados (whitelist estrita): %s"
         % ", ".join(GLOBALS_TO_CHECK))

    if not _FILE_AVAILABLE:
        print("[WARN] __file__ indisponivel: escrita em disco DESABILITADA "
             "nesta execucao (evita gravar em local incerto, ex.: dentro da "
             "pasta do projeto). Somente saida em console.")

    try:
        report = build_report()
    except Exception as exc:
        # Falha catastrofica antes mesmo de montar o relatorio (ex.: 'common'
        # nao importavel). Tenta deixar um artefato minimo, sem depender de
        # 'common', usando so os modulos ja importados no topo do arquivo.
        print("[ERROR] Falha inesperada ao montar o relatorio: %r" % (exc,))
        tb = None
        try:
            tb = traceback.format_exc()
            print(tb)
        except Exception:
            pass
        if _FILE_AVAILABLE and LOG_ROOT:
            try:
                stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                fallback_dir = os.path.join(LOG_ROOT, stamp + "_00_smoke_test_FALHA")
                if not os.path.isdir(fallback_dir):
                    os.makedirs(fallback_dir)
                f = open(os.path.join(fallback_dir, "erro.txt"), "w")
                try:
                    f.write("Falha ao montar o relatorio do smoke test.\n")
                    f.write("Excecao: %r\n\n" % (exc,))
                    f.write(tb or "<traceback indisponivel>\n")
                finally:
                    f.close()
                print("[INFO] Artefato de falha salvo em: %s" % fallback_dir)
            except Exception as exc2:
                print("[ERROR] Nao foi possivel salvar artefato de falha: %r" % (exc2,))
        print("=" * 60)
        return

    # Resumo em console:
    for check in report["checks"]:
        marker = "[OK]" if check["status"] == "ok" else "[ERROR]"
        print("%s %s -> %s" % (marker, check["name"], check["status"]))
    if report["primary_project"]["present"]:
        print("[OK] Projeto primario encontrado: %s (%s)"
             % (report["primary_project"]["name"], report["primary_project"]["path"]))
    else:
        print("[WARN] Projeto primario NAO encontrado: %s"
             % report["primary_project"]["error"])

    if _FILE_AVAILABLE and LOG_ROOT:
        try:
            from common import file_io
            run_dir = file_io.new_export_dir(LOG_ROOT, "00_smoke_test")
            file_io.write_json(os.path.join(run_dir, "report.json"), report)
            file_io.write_text(os.path.join(run_dir, "report.md"),
                               report_to_markdown(report))
            print("[OK] Relatorio gravado em: %s" % run_dir)
        except Exception as exc:
            print("[ERROR] Falha ao gravar relatorio em disco: %r" % (exc,))
            try:
                traceback.print_exc()
            except Exception:
                pass
    else:
        print("[INFO] Escrita em disco desabilitada nesta execucao (ver aviso acima).")

    print("[OK] Smoke test concluido. Nenhuma escrita, compilacao ou operacao "
         "online foi solicitada (ver 'safety_declaration' no relatorio).")
    print("=" * 60)


main()

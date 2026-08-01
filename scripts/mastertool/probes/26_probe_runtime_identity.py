# -*- coding: utf-8 -*-
r"""26_probe_runtime_identity.py — Etapa 2 do marco W0 (ver
docs/27-reconhecimento-mastertool-x.md): mede a identidade REAL do runtime
que executa scripts, dentro do processo.

Existe porque W0 mediu tudo o que se pode medir de fora — versao do
executavel, versao dos assemblies em disco, superficie por reflexao estatica —
e quatro coisas continuam so observaveis de dentro:

    bitness EFETIVO do processo      (AnyCPU nao decide isso em disco)
    sys.version do host              (banner de produto, nao versao de Python)
    assemblies CARREGADOS            (disco mostra o que existe, nao o que carrega)
    caminho do processo em execucao  (qual instalacao, 4.0.0 ou 4.1.0)

`probe_cli.runtime_identity()` ja devolve executavel + file/product version +
sys.version, e este probe o REUSA em vez de reimplementar. O que ele acrescenta
e o bitness, a lista de assemblies carregados e o modulo real do processo.

SOMENTE LEITURA, e por construcao:
  - nao navega a arvore (nenhum get_children), nao le conteudo de objeto;
  - le do projeto APENAS `.path` de `projects.primary`, quando existir —
    mesmo escopo minimo ja aprovado em probes/15;
  - NUNCA toca `device_repository`: ele esta marcado em common/compatibility.py
    como capaz de iniciar comunicacao ao ter propriedades lidas. O diretorio do
    Device Repository e responsabilidade do HOST, que o le do disco;
  - nao cria, nao renomeia, nao remove, nao salva, nao compila, nao importa;
  - nao usa `dir()` em proxy CLR: a enumeracao de assemblies e do AppDomain
    do .NET, nao da superficie de scripting do MasterTool;
  - falha isolada por passo: um erro NUNCA impede os passos seguintes nem a
    gravacao do artefato.

Compatibilidade: IronPython 2.7 (sem f-string, sem pathlib, sem type hints).
"""
from __future__ import print_function

import os
import sys
import traceback

_FILE_AVAILABLE = True
try:
    _SCRIPT_PATH = os.path.abspath(__file__)
    _SCRIPT_DIR = os.path.dirname(_SCRIPT_PATH)
except NameError:
    _FILE_AVAILABLE = False
    _SCRIPT_PATH = None
    _SCRIPT_DIR = None

_MASTERTOOL_DIR = os.path.dirname(_SCRIPT_DIR) if _SCRIPT_DIR else None
if _MASTERTOOL_DIR and _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)
REPO_ROOT = os.path.abspath(os.path.join(_MASTERTOOL_DIR, "..", "..")) if _MASTERTOOL_DIR else None

SCRIPT_NAME = "26_probe_runtime_identity.py"

STATUS_COMPLETE = "complete"
STATUS_COMPLETE_WITH_STEP_ERRORS = "complete_with_step_errors"
STATUS_FATAL = "fatal"
EXIT_BY_STATUS = {STATUS_COMPLETE: 0, STATUS_COMPLETE_WITH_STEP_ERRORS: 0, STATUS_FATAL: 1}

# Lista LITERAL de prefixos de assembly de interesse. Nao e filtro de
# privacidade — o inventario completo tambem e gravado, so que sem os
# caminhos. Serve para o relatorio destacar o que importa sem obrigar quem le
# a varrer 200 linhas.
ASSEMBLY_PREFIXES_OF_INTEREST = (
    "ScriptEngine", "ScriptDriver", "IronPython", "Microsoft.Scripting",
    "MT9000", "MT8500", "ProjectArchive", "VersionCompatibilityManager",
)


def _new_step(name):
    return {"name": name, "status": "not_run", "detail": None, "error": None}


def _run_step(report, name, func):
    step = _new_step(name)
    try:
        step["detail"] = func()
        step["status"] = "ok"
    except Exception as exc:                                   # noqa: BLE001
        step["status"] = "error"
        try:
            step["error"] = repr(exc)
        except Exception:                                      # noqa: BLE001
            step["error"] = "<excecao sem repr>"
        try:
            step["traceback"] = traceback.format_exc()
        except Exception:                                      # noqa: BLE001
            pass
    report["steps"].append(step)
    return step


def collect_process_identity():
    """Bitness e caminho REAIS do processo. Medicao, nunca inferencia por
    diretorio de instalacao: um assembly AnyCPU vive em `Program Files` e pode
    rodar em 32 ou 64 bits."""
    info = {
        "pointer_size_bytes": None,
        "bitness": None,
        "bitness_evidence": None,
        "is_64bit_process": None,
        "is_64bit_operating_system": None,
        "main_module_file_name": None,
        "process_id": None,
        "error": None,
    }
    try:
        import clr                                             # noqa: F401
        from System import Environment, IntPtr

        info["pointer_size_bytes"] = IntPtr.Size
        info["bitness"] = 64 if IntPtr.Size == 8 else 32
        info["bitness_evidence"] = "System.IntPtr.Size"
        try:
            info["is_64bit_process"] = bool(Environment.Is64BitProcess)
        except Exception:                                      # noqa: BLE001
            info["is_64bit_process"] = None
        try:
            info["is_64bit_operating_system"] = bool(Environment.Is64BitOperatingSystem)
        except Exception:                                      # noqa: BLE001
            info["is_64bit_operating_system"] = None
        try:
            from System.Diagnostics import Process
            current = Process.GetCurrentProcess()
            info["process_id"] = current.Id
            info["main_module_file_name"] = current.MainModule.FileName
        except Exception as exc:                               # noqa: BLE001
            info["error"] = "MainModule indisponivel: %r" % (exc,)
    except Exception as exc:                                   # noqa: BLE001
        info["error"] = repr(exc)
    return info


def collect_loaded_assemblies():
    """Assemblies efetivamente CARREGADOS no AppDomain."""
    from common import probe_cli

    result = {"total": None, "of_interest": [], "all_names": [], "error": None}
    try:
        import clr                                             # noqa: F401
        from System import AppDomain

        assemblies = AppDomain.CurrentDomain.GetAssemblies()
        result["total"] = len(assemblies)
        for asm in assemblies:
            try:
                asm_name = asm.GetName()
                name = asm_name.Name
                version = str(asm_name.Version)
            except Exception:                                  # noqa: BLE001
                continue
            result["all_names"].append(name)
            if not probe_cli.assembly_name_matches(name, ASSEMBLY_PREFIXES_OF_INTEREST):
                continue
            entry = {"name": name, "version": version, "location": None,
                     "processor_architecture": None}
            try:
                entry["location"] = asm.Location
            except Exception:                                  # noqa: BLE001
                entry["location"] = "<indisponivel>"
            try:
                entry["processor_architecture"] = str(asm_name.ProcessorArchitecture)
            except Exception:                                  # noqa: BLE001
                pass
            result["of_interest"].append(entry)
        result["of_interest"].sort(key=lambda item: (item["name"], item["version"]))
        result["all_names"].sort()
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = repr(exc)
    return result


def build_report(argv, script_globals):
    from common import file_io, probe_cli

    report = {
        "schema_version": "1.0",
        "script": "probes/" + SCRIPT_NAME,
        "mode": "read_only",
        "script_started": True,
        "started_at": file_io.iso_now(),
        "completed_at": None,
        "argv": None,
        "cwd": None,
        "script_file": _SCRIPT_PATH,
        "runtime_identity": None,
        "process": None,
        "assemblies": None,
        "scriptengine": None,
        "python": {"version": None, "version_info": None, "platform": None,
                   "executable": None, "subversion": None},
        "project": {"primary_available": False, "path": None, "error": None},
        "steps": [],
        "status": STATUS_FATAL,
        "safety_declaration": {
            "read_only": True,
            "project_modified": False,
            "save_called": False,
            "build_called": False,
            "online_access": False,
            "project_navigation_attempted": False,
            "project_content_accessed": False,
            "device_repository_touched": False,
            "mutating_api_invoked": False,
            "note": ("Somente leitura por construcao: nenhuma chamada de "
                     "criacao, escrita, renome, remocao, importacao, save, "
                     "build ou online existe neste arquivo; do projeto le-se "
                     "apenas projects.primary.path."),
        },
    }

    def _step_argv():
        report["argv"] = list(argv or [])
        return {"count": len(report["argv"])}
    _run_step(report, "capture_argv", _step_argv)

    def _step_cwd():
        report["cwd"] = os.getcwd()
        return report["cwd"]
    _run_step(report, "capture_cwd", _step_cwd)

    def _step_python():
        info = report["python"]
        info["platform"] = sys.platform
        try:
            info["version"] = sys.version.replace("\n", " ").replace("\r", " ")
        except Exception:                                      # noqa: BLE001
            info["version"] = None
        try:
            info["version_info"] = list(sys.version_info)
        except Exception:                                      # noqa: BLE001
            info["version_info"] = None
        try:
            info["subversion"] = list(sys.subversion)
        except Exception:                                      # noqa: BLE001
            info["subversion"] = None
        try:
            info["executable"] = getattr(sys, "executable", None)
        except Exception:                                      # noqa: BLE001
            info["executable"] = None
        return info
    _run_step(report, "capture_python_runtime", _step_python)

    def _step_identity():
        report["runtime_identity"] = probe_cli.runtime_identity()
        return report["runtime_identity"]
    _run_step(report, "capture_runtime_identity", _step_identity)

    def _step_process():
        report["process"] = collect_process_identity()
        return report["process"]
    _run_step(report, "capture_process_identity", _step_process)

    def _step_assemblies():
        report["assemblies"] = collect_loaded_assemblies()
        report["scriptengine"] = probe_cli.scriptengine_version_from_assemblies(
            report["assemblies"].get("of_interest"))
        return {"total": report["assemblies"].get("total"),
                "of_interest": len(report["assemblies"].get("of_interest") or []),
                "scriptengine": report["scriptengine"]}
    _run_step(report, "capture_loaded_assemblies", _step_assemblies)

    def _step_project():
        from common import project_access

        project, err = project_access.get_primary_project(script_globals)
        if project is None:
            report["project"]["primary_available"] = False
            report["project"]["error"] = err
            return report["project"]
        report["project"]["primary_available"] = True
        report["project"]["path"] = project_access.get_project_path(project)
        return report["project"]
    _run_step(report, "capture_project_identity", _step_project)

    errors = [s for s in report["steps"] if s["status"] == "error"]
    report["status"] = STATUS_COMPLETE_WITH_STEP_ERRORS if errors else STATUS_COMPLETE
    report["completed_at"] = file_io.iso_now()
    return report


def report_to_markdown(report):
    lines = [
        "# Probe 26 — identidade real do runtime (W0, Etapa 2)",
        "",
        "Modo: **somente leitura**. Nenhuma API mutavel invocada; "
        "`device_repository` nao foi tocado.",
        "",
        "- status: **%s**" % report.get("status"),
        "- started_at: `%s`" % report.get("started_at"),
        "- completed_at: `%s`" % report.get("completed_at"),
        "",
        "## argv cru",
        "",
        "```",
        repr(report.get("argv")),
        "```",
        "",
        "## Processo",
    ]
    process = report.get("process") or {}
    lines.append("- bitness: **%s** (evidencia: %s)"
                 % (process.get("bitness"), process.get("bitness_evidence")))
    lines.append("- IntPtr.Size: `%s`" % process.get("pointer_size_bytes"))
    lines.append("- Environment.Is64BitProcess: `%s`" % process.get("is_64bit_process"))
    lines.append("- Environment.Is64BitOperatingSystem: `%s`"
                 % process.get("is_64bit_operating_system"))
    lines.append("- modulo principal: `%s`" % process.get("main_module_file_name"))
    lines.append("- pid: `%s`" % process.get("process_id"))
    if process.get("error"):
        lines.append("- erro: `%s`" % process.get("error"))
    lines.append("")
    lines.append("## Runtime de script")
    python = report.get("python") or {}
    lines.append("- `sys.version` (banner cru): `%s`" % python.get("version"))
    lines.append("- `sys.version_info`: `%s`" % (python.get("version_info"),))
    lines.append("- `sys.subversion`: `%s`" % (python.get("subversion"),))
    lines.append("- `sys.platform`: `%s`" % python.get("platform"))
    lines.append("- `sys.executable`: `%s`" % python.get("executable"))
    identity = report.get("runtime_identity") or {}
    lines.append("- executavel (entry assembly): `%s`" % identity.get("executable"))
    lines.append("- file_version: `%s`" % identity.get("file_version"))
    lines.append("- product_version: `%s`" % identity.get("product_version"))
    engine = report.get("scriptengine") or {}
    lines.append("- **ScriptEngine: `%s`** (fonte: %s)"
                 % (engine.get("version"), engine.get("source")))
    lines.append("")
    lines.append("## Assemblies carregados de interesse")
    assemblies = report.get("assemblies") or {}
    lines.append("- total no AppDomain: `%s`" % assemblies.get("total"))
    for entry in assemblies.get("of_interest") or []:
        lines.append("- `%s` **%s** — `%s`"
                     % (entry.get("name"), entry.get("version"), entry.get("location")))
    if assemblies.get("error"):
        lines.append("- erro: `%s`" % assemblies.get("error"))
    lines.append("")
    lines.append("## Projeto")
    project = report.get("project") or {}
    lines.append("- primary_available: **%s**" % project.get("primary_available"))
    lines.append("- path: `%s`" % project.get("path"))
    if project.get("error"):
        lines.append("- erro: `%s`" % project.get("error"))
    lines.append("")
    lines.append("## Passos")
    for step in report.get("steps") or []:
        marker = "OK" if step["status"] == "ok" else "ERROR"
        lines.append("- [%s] %s" % (marker, step["name"]))
        if step["status"] != "ok":
            lines.append("  - erro: `%s`" % step["error"])
    lines.append("")
    return "\n".join(lines)


def main():
    print("=" * 68)
    print("[INFO] probes/%s — SOMENTE LEITURA" % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel: sem ele nao da para localizar os "
              "modulos comuns nem provar que a saida esta fora do repo")
        sys.exit(EXIT_BY_STATUS[STATUS_FATAL])
        return

    try:
        from common import file_io, probe_cli
    except Exception as exc:                                   # noqa: BLE001
        print("[FATAL] falha ao importar modulos comuns: %r" % (exc,))
        sys.exit(EXIT_BY_STATUS[STATUS_FATAL])
        return

    problems = []
    argv = list(sys.argv or [])
    out_root = probe_cli.validate_output_path(
        probe_cli.find_arg(argv, "output"), REPO_ROOT, problems)
    if problems:
        print("[FATAL] argumentos recusados:")
        for item in problems:
            print("        - %s" % item)
        sys.exit(EXIT_BY_STATUS[STATUS_FATAL])
        return

    report = build_report(argv, globals())

    run_dir = file_io.new_export_dir(out_root, "runtime_identity")
    file_io.write_json(os.path.join(run_dir, "result.json"), report)
    file_io.write_text(os.path.join(run_dir, "report.md"), report_to_markdown(report))

    process = report.get("process") or {}
    engine = report.get("scriptengine") or {}
    print("[INFO] bitness: %s (%s)" % (process.get("bitness"), process.get("bitness_evidence")))
    print("[INFO] ScriptEngine: %s" % engine.get("version"))
    print("[INFO] sys.version: %s" % (report.get("python") or {}).get("version"))
    print("[INFO] projeto: %s" % (report.get("project") or {}).get("path"))
    print("[OK] artefato: %s" % run_dir)
    print("[OK] status=%s" % report.get("status"))
    print("=" * 68)
    sys.exit(EXIT_BY_STATUS.get(report.get("status"), 1))


main()

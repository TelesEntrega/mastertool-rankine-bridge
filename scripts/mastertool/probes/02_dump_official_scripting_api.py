# -*- coding: utf-8 -*-
"""02_dump_official_scripting_api.py — invoca o dumper OFICIAL do produto
(`ScriptEngine.DumpScriptingApi`), SEPARADO do verificador caseiro
`scripts/mastertool/02_dump_api_surface.py`.

Movido para `scripts/mastertool/probes/` em 2026-07-23 (organização: scripts
exploratórios ficam separados dos scripts funcionais numerados 00-11 —
`04_export_project.py`/`05_export_selected_object.py` etc. mantêm sua
numeração original na raiz de `scripts/mastertool/`).

BLOQUEADO por configuracao: exige `features.official_api_dump: true` em
config/default.yaml (padrao PERMANENTE do repositorio: `false`). Habilite
apenas localmente para uma execucao controlada e restaure `false` logo
depois — ver docs/api/mastertool-api-observations.md.

Assinatura confirmada por REFLECTION ESTATICA em 2026-07-23 (PowerShell,
`Assembly.ReflectionOnlyLoadFrom` — nao executa nada; ver
docs/api/mastertool-api-observations.md para o detalhe bruto):

    assembly:        ScriptEngine.plugin, Version=4.1.0.0
    tipo declarante: _3S.CoDeSys.ScriptEngine.ScriptEngine (classe publica)
    metodo:          DumpScriptingApi (instancia, publico, virtual)
    retorno:         System.Void
    parametros (so o [0] e obrigatorio; [1]-[6] sao OPTIONAL, default null):
        [0] System.IO.TextWriter                                    outputWriter
        [1] _3S.CoDeSys.ScriptEngine.LogCallback                    logCallback
        [2] _3S.CoDeSys.ScriptEngine.DriverFilter                   allowedDrivers
        [3] System.Predicate<object>                                allowedObjects
        [4] IEnumerable<KeyValuePair<string,object>>                additionalEntryPoints
        [5] IEnumerable<System.Reflection.Assembly>                 additionalAssemblies
        [6] _3S.CoDeSys.ScriptEngine.IScriptExecutor4                speciallyPreparedExecutor

FORMA DE INVOCACAO (primeira execucao controlada, 2026-07-23):
  - Chama-se APENAS com o parametro obrigatorio: `engine.DumpScriptingApi(writer)`.
  - Os outros 6 parametros sao OMITIDOS (nao passados), confiando no binding
    de parametros opcionais do IronPython/CLR — nunca preenchidos com
    objetos descobertos dinamicamente, filtros, delegates ou plugins.
  - UMA UNICA tentativa de chamada. Se falhar, a excecao completa e
    registrada e o script encerra: NENHUMA combinacao alternativa de
    argumentos e tentada automaticamente (sem retry com None explicito, sem
    testar overloads).

Garantias:
  - somente leitura; NENHUMA compilacao; NENHUM open/save/close de projeto;
  - NENHUMA operacao online; NENHUMA consulta a device_repository;
  - NENHUMA navegacao da arvore do projeto;
  - NENHUMA enumeracao ampla via dir() como fonte autoritativa (a unica
    introspeccao ampla aqui e a propria chamada ao metodo oficial, uma vez,
    e so ocorre se autorizada por configuracao);
  - NENHUMA chamada aos metodos que aparecerem no texto retornado pelo dump —
    o conteudo e apenas salvo para analise offline posterior;
  - caminho de saida calculado exclusivamente a partir de __file__; se
    indisponivel, o script recusa a execucao;
  - diretorio de saida com timestamp, nunca sobrescreve execucoes anteriores;
  - todas as excecoes sao capturadas;
  - a assinatura esperada e registrada no relatorio ANTES de qualquer chamada;
  - o tipo .NET real e o metodo de resolucao do objeto usado para invocar o
    metodo sao registrados;
  - checksums SHA-256 de todos os artefatos gerados.
"""
from __future__ import print_function

import datetime
import os
import sys
import time
import traceback

# Bootstrap (script vive em scripts/mastertool/probes/ — um nivel a mais que
# os scripts funcionais em scripts/mastertool/): sys.path recebe a pasta
# 'mastertool' (onde vive 'common/'), nao a propria pasta 'probes/'.
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
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "default.yaml") if REPO_ROOT else None

# Unico candidato plausivel para expor DumpScriptingApi a um script. NUNCA
# adicione "online"/"device_repository" a esta lista.
GLOBALS_TO_CHECK = ["scriptengine"]

EXPECTED_SIGNATURE = {
    "evidence": "static_metadata (Assembly.ReflectionOnlyLoadFrom, 2026-07-23)",
    "assembly": "ScriptEngine.plugin, Version=4.1.0.0, Culture=neutral, PublicKeyToken=null",
    "declaring_type": "_3S.CoDeSys.ScriptEngine.ScriptEngine",
    "namespace": "_3S.CoDeSys.ScriptEngine",
    "method_name": "DumpScriptingApi",
    "is_static": False,
    "is_public": True,
    "is_virtual": True,
    "return_type": "System.Void",
    "overload_count": 1,
    "parameters": [
        {"position": 0, "name": "outputWriter", "type": "System.IO.TextWriter", "optional": False},
        {"position": 1, "name": "logCallback", "type": "_3S.CoDeSys.ScriptEngine.LogCallback", "optional": True},
        {"position": 2, "name": "allowedDrivers", "type": "_3S.CoDeSys.ScriptEngine.DriverFilter", "optional": True},
        {"position": 3, "name": "allowedObjects", "type": "System.Predicate<System.Object>", "optional": True},
        {"position": 4, "name": "additionalEntryPoints",
         "type": "System.Collections.Generic.IEnumerable<System.Collections.Generic.KeyValuePair<System.String,System.Object>>",
         "optional": True},
        {"position": 5, "name": "additionalAssemblies",
         "type": "System.Collections.Generic.IEnumerable<System.Reflection.Assembly>", "optional": True},
        {"position": 6, "name": "speciallyPreparedExecutor",
         "type": "_3S.CoDeSys.ScriptEngine.IScriptExecutor4", "optional": True},
    ],
    "note": ("Delegates LogCallback/DriverFilter nao foram localizados no "
             "assembly ScriptEngine.plugin.dll (provavelmente definidos em "
             "outro assembly-nucleo, ainda nao pesquisado) — nao bloqueia a "
             "chamada, ja que sao parametros opcionais (default null)."),
}

CALL_MODE = ("Apenas outputWriter (System.IO.StringWriter); os outros 6 "
            "parametros sao OMITIDOS (nao passados nesta chamada). Uma "
            "unica tentativa; sem fallback para outra combinacao de "
            "argumentos se esta falhar.")


def _refuse(reason):
    print("=" * 60)
    print("[BLOQUEADO] %s" % reason)
    print("=" * 60)


def _new_report(run_dir):
    return {
        "schema_version": "1.0",
        "script": "probes/02_dump_official_scripting_api.py",
        "generated_at": datetime.datetime.now().isoformat(),
        "mode": "read_only",
        "call_mode": CALL_MODE,
        "expected_signature": EXPECTED_SIGNATURE,
        "globals_probed": list(GLOBALS_TO_CHECK),
        "scriptengine_object": {
            "found": False,
            "dotnet_type": None,
            "has_dump_method": None,
            "resolution_method": None,
            "error": None,
        },
        "invocation": {
            "attempted": False,
            "call_count": 0,
            "parameters_sent": "nao aplicavel: chamada nao tentada.",
            "started_at": None,
            "finished_at": None,
            "duration_ms": None,
            "success": False,
            "text_length": None,
            "text_sha256": None,
        },
        "output_files": {
            "dump_text": None,
            "report_json": os.path.join(run_dir, "report.json"),
            "report_md": os.path.join(run_dir, "report.md"),
            "checksums": os.path.join(run_dir, "checksums.sha256"),
        },
        "errors": [],
        "safety_declaration": {
            "write_operations_requested": False,
            "compile_requested": False,
            "online_access_requested": False,
            "device_repository_access_requested": False,
            "project_opened": False,
            "project_saved": False,
            "project_closed": False,
            "objects_created": False,
            "tree_navigation_attempted": False,
            "dir_used_as_authoritative": False,
            "alternative_overloads_or_argument_combos_attempted": False,
            "methods_from_dump_output_invoked": False,
            "note": ("Garantido por construcao deste arquivo: nao ha call "
                     "site para nenhuma dessas operacoes."),
        },
    }


def _report_to_markdown(report):
    lines = [
        "# Dump oficial da API de scripting (ScriptEngine.DumpScriptingApi)",
        "",
        "Modo: **somente leitura**. Assinatura esperada registrada em "
        "`expected_signature` (report.json) ANTES de qualquer chamada.",
        "",
        "- Gerado em: %s" % report["generated_at"],
        "- Forma de chamada: %s" % report["call_mode"],
        "",
        "## Objeto usado para invocar",
        "- Global 'scriptengine' encontrado: %s" % report["scriptengine_object"]["found"],
        "- Tipo .NET real: `%s`" % report["scriptengine_object"]["dotnet_type"],
        "- Metodo de resolucao: %s" % report["scriptengine_object"]["resolution_method"],
        "- Possui DumpScriptingApi: %s" % report["scriptengine_object"]["has_dump_method"],
        "- Erro (se houver): %s" % report["scriptengine_object"]["error"],
        "",
        "## Invocacao",
        "- Tentada: %s" % report["invocation"]["attempted"],
        "- Quantidade de chamadas realizadas: %s" % report["invocation"]["call_count"],
        "- Parametros efetivamente enviados: %s" % report["invocation"]["parameters_sent"],
        "- Inicio: %s" % report["invocation"]["started_at"],
        "- Fim: %s" % report["invocation"]["finished_at"],
        "- Duracao: %s ms" % report["invocation"]["duration_ms"],
        "- Sucesso: %s" % report["invocation"]["success"],
        "- Tamanho do texto retornado: %s caractere(s)" % report["invocation"]["text_length"],
        "- SHA-256 do texto retornado: `%s`" % report["invocation"]["text_sha256"],
        "",
        "## Arquivos gerados",
    ]
    for label, path in sorted(report["output_files"].items()):
        lines.append("- %s: `%s`" % (label, path))
    if report["errors"]:
        lines.append("")
        lines.append("## Excecoes (completas em report.json)")
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
    print("[INFO] probes/02_dump_official_scripting_api.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())

    if not _FILE_AVAILABLE or not REPO_ROOT:
        _refuse("__file__ indisponivel: nao e possivel determinar com "
               "seguranca o diretorio de saida. Execucao recusada.")
        return

    try:
        from common import config_reader
    except Exception as exc:
        _refuse("Falha ao importar common.config_reader: %r" % (exc,))
        return

    enabled = config_reader.read_feature_flag(
        CONFIG_PATH, "features", "official_api_dump", default=False)
    if not enabled:
        _refuse("features.official_api_dump esta 'false' (ou ausente) em "
               "config/default.yaml. Este script permanece desabilitado ate "
               "decisao humana explicita para esta execucao controlada.")
        return

    # --- A partir daqui, so executa porque features.official_api_dump: true ---
    try:
        from common import checksums, compatibility, file_io
    except Exception as exc:
        _refuse("Falha ao importar modulos comuns: %r" % (exc,))
        return

    run_dir = file_io.new_export_dir(LOG_ROOT, "02_dump_official_scripting_api")
    report = _new_report(run_dir)

    # Resolucao explicita do global 'scriptengine' (unico candidato desta
    # execucao) — registra COMO foi resolvido. Nunca toca "online"/
    # "device_repository".
    engine = None
    try:
        script_globals = globals()
        if "scriptengine" in script_globals:
            engine = script_globals["scriptengine"]
            report["scriptengine_object"]["resolution_method"] = (
                "presente diretamente no escopo do script (globals())")
        else:
            engine = compatibility.get_scriptengine_global("scriptengine")
            if engine is not None:
                report["scriptengine_object"]["resolution_method"] = (
                    "common.compatibility.get_scriptengine_global "
                    "(via 'import scriptengine' ou builtins)")
        if engine is None:
            report["scriptengine_object"]["error"] = (
                "Global 'scriptengine' nao encontrado nesta execucao.")
        else:
            report["scriptengine_object"]["found"] = True
            report["scriptengine_object"]["dotnet_type"] = compatibility.safe_type_name(engine)
            report["scriptengine_object"]["has_dump_method"] = hasattr(engine, "DumpScriptingApi")
    except Exception as exc:
        report["scriptengine_object"]["error"] = "excecao: %r" % (exc,)
        report["errors"].append({"where": "resolve_scriptengine_global",
                                 "message": repr(exc),
                                 "traceback": traceback.format_exc()})
        engine = None

    dump_text = None
    if engine is not None and report["scriptengine_object"]["has_dump_method"]:
        report["invocation"]["attempted"] = True
        report["invocation"]["parameters_sent"] = (
            "[outputWriter=System.IO.StringWriter()] somente; os outros 6 "
            "parametros foram OMITIDOS (nao passados) nesta chamada.")
        report["invocation"]["started_at"] = datetime.datetime.now().isoformat()
        t0 = time.time()
        try:
            # System.IO.StringWriter e um TextWriter .NET real (nao o
            # StringIO do Python) — e o tipo exigido por outputWriter.
            import System.IO
            writer = System.IO.StringWriter()
            report["invocation"]["call_count"] = 1
            # UNICA tentativa, somente com o parametro obrigatorio. Se
            # falhar, a excecao e registrada e o script encerra — nenhuma
            # combinacao alternativa de argumentos e tentada.
            engine.DumpScriptingApi(writer)
            dump_text = writer.ToString()
            report["invocation"]["success"] = True
            report["invocation"]["text_length"] = len(dump_text)
            report["invocation"]["text_sha256"] = checksums.sha256_text(dump_text)
        except Exception as exc:
            report["errors"].append({"where": "DumpScriptingApi",
                                     "message": repr(exc),
                                     "traceback": traceback.format_exc()})
        finally:
            report["invocation"]["finished_at"] = datetime.datetime.now().isoformat()
            report["invocation"]["duration_ms"] = int((time.time() - t0) * 1000)
    else:
        report["invocation"]["parameters_sent"] = (
            "nao aplicavel: chamada nao tentada (global 'scriptengine' "
            "ausente ou sem metodo DumpScriptingApi).")

    # --- Gravacao dos artefatos (ordem importa: checksums.sha256 e o ULTIMO
    # arquivo escrito, para que reflita o conteudo FINAL de report.json e
    # report.md — nenhum arquivo e reescrito depois de ser incluido no
    # checksums). ---
    if dump_text is not None:
        dump_path = os.path.join(run_dir, "official-scripting-api.txt")
        file_io.write_text(dump_path, dump_text)
        report["output_files"]["dump_text"] = dump_path

    file_io.write_json(report["output_files"]["report_json"], report)
    file_io.write_text(report["output_files"]["report_md"], _report_to_markdown(report))
    checksums.write_checksums_file(run_dir, report["output_files"]["checksums"])

    print("[OK] Invocacao tentada: %s | sucesso: %s | chamadas: %s"
         % (report["invocation"]["attempted"], report["invocation"]["success"],
            report["invocation"]["call_count"]))
    print("[OK] Artefatos gravados em: %s" % run_dir)
    print("=" * 60)


main()

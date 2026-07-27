# -*- coding: utf-8 -*-
r"""15_validate_command_line_execution.py — Etapa A do roadmap de automacao
(ver docs/15-automation-launcher-roadmap.md): prova MINIMA e inofensiva de
que um script IronPython invocado via `MT8500.exe --runscript=...` (com ou
sem `--project=...`/`--scriptargs:...`/`--noUI`, em qualquer combinacao) roda
de fato, e com que argumentos/contexto.

Renomeado e movido em 2026-07-24 (era
`scripts/mastertool/automation/probe_cli_invocation.py`): o usuario pediu
explicitamente o caminho `scripts/mastertool/probes/14_validate_command_line_
execution.py`, mas o numero 14 ja estava ocupado por
`probes/14_inventory_graphic_pous.py` (Fase L0 do roadmap Ladder, ja
commitada) — por isso o numero real usado e 15, na sequencia numerada de
probes (fora de `scripts/mastertool/automation/`, que deixou de existir).

NAO confirma nada sobre as flags de linha de comando alem do que este script
observa em runtime — `--project`/`--runscript`/`--scriptargs`/`--noUI` estao
documentadas para CODESYS em geral, NUNCA foram confirmadas no MT8500.exe
3.63 real da Altus. Este script existe exatamente para gerar essa evidencia,
sem tocar em nada do projeto.

Execucao pretendida (pelo USUARIO, nunca pelo agente, com a UI do MasterTool
VISIVEL no primeiro teste — ver docs/15-automation-launcher-roadmap.md):
    MT8500.exe --runscript="<repo>\scripts\mastertool\probes\15_validate_command_line_execution.py"
    MT8500.exe --runscript="..." --scriptargs:'--output "C:\algum\caminho"'
    MT8500.exe --project="C:\Projetos\Projeto.project" --runscript="..."
    MT8500.exe --project="..." --runscript="..." (combinado)
    MT8500.exe --project="..." --runscript="..." --noUI   (SO depois dos 4 acima)

Tambem roda pelo menu (Ferramentas -> Scripting -> Executar Arquivo de
Script), para comparar o contexto de execucao entre os dois modos de
invocacao.

Garantias de escopo (validas por construcao deste arquivo — ver
"safety"/"safety_declaration" no relatorio gerado):
  - NUNCA chama build()/rebuild()/clean()/generate_code() ou qualquer outro
    metodo de compilacao;
  - NUNCA acessa nenhum global alem de "projects"/"system" (via whitelist
    estrita common.compatibility.probe_globals);
  - sobre "projects": alem de confirmar presenca via
    common.capabilities.probe_member(..., "primary", capture_value=True)
    (mesmo padrao ja aprovado em 00_smoke_test.py), este script agora TAMBEM
    le `.path` de `projects.primary` — via
    common.capabilities.probe_member(primary_obj, "project", "path", ...,
    capture_value=True) + build_representation, o MESMO padrao ja usado e
    aprovado em probes/03_project_navigation.py. "path" ja esta na whitelist
    aprovada `common/capabilities.py: CAPABILITY_PROBES["project"]`. Nenhuma
    outra propriedade de `projects.primary` e lida (nao `is_root`, nao
    `handle`, nao `active_application`, mesmo estando na whitelist — escopo
    minimo desta prova);
  - NUNCA navega a arvore do projeto (nenhum get_children), NUNCA le
    conteudo de nenhum objeto;
  - NUNCA salva, fecha, cria ou modifica nada no projeto;
  - cada passo de coleta de evidencia e protegido por seu proprio
    try/except: uma falha isolada NUNCA impede os passos seguintes nem a
    gravacao do relatorio final (esse e o objetivo central desta prova:
    maximizar diagnostico mesmo em cenario de falha parcial);
  - a resolucao do diretorio de saida e defensiva e em camadas (ver
    `_resolve_output_dir`), documentando cada tentativa no proprio
    relatorio (`output_dir_resolution`); se todas falharem, o relatorio e
    pelo menos impresso via print() (aba de Mensagens do MasterTool).

Artefatos gravados por este script: SOMENTE `result.json` (dados objetivos)
+ `report.md` (o mesmo conteudo, em formato legivel). Este script NUNCA cria
`observation.md`/`summary.md` — esses arquivos sao para ANOTACAO MANUAL do
usuario, depois de observar a execucao real (ex.: "a UI abriu? apareceu
algum dialogo?"), preenchidos por fora deste script.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys
import traceback

# --- bootstrap: tornar 'common' importavel, sem presumir nada sobre cwd ----
# Mesmo padrao de 00_smoke_test.py: se __file__ nao estiver disponivel, nao
# adivinhamos nenhum caminho relativo ao script (camada 2 de
# _resolve_output_dir fica indisponivel, mas as demais camadas seguem
# tentando).
_FILE_AVAILABLE = True
try:
    _SCRIPT_PATH = os.path.abspath(__file__)
    _SCRIPT_DIR = os.path.dirname(_SCRIPT_PATH)
except NameError:
    _FILE_AVAILABLE = False
    _SCRIPT_PATH = None
    _SCRIPT_DIR = None

# _SCRIPT_DIR e .../scripts/mastertool/probes -> pasta 'mastertool' (onde
# vive 'common/') e 1 nivel acima; raiz do repo e 3 niveis acima dela.
_MASTERTOOL_DIR = os.path.dirname(_SCRIPT_DIR) if _SCRIPT_DIR else None
if _MASTERTOOL_DIR and _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)
REPO_ROOT = os.path.abspath(os.path.join(_MASTERTOOL_DIR, "..", "..")) if _MASTERTOOL_DIR else None
DEFAULT_LOG_ROOT = os.path.join(REPO_ROOT, "workspace", "logs") if REPO_ROOT else None
# -----------------------------------------------------------------------------

SCRIPT_NAME = "15_validate_command_line_execution.py"

# Whitelist estrita: NENHUM outro global e sondado neste script.
GLOBALS_TO_CHECK = ["projects", "system"]

# Variaveis de ambiente cujo VALOR e considerado seguro o suficiente para
# aparecer no relatorio (nunca dump de os.environ inteiro — pode conter
# segredos/caminhos de usuario sensiveis fora deste escopo minimo).
SAFE_ENV_VARS = ["COMPUTERNAME", "USERNAME", "OS", "PROCESSOR_ARCHITECTURE"]

# Strings nativas: no IronPython 2.7 um argumento de argv pode chegar como
# `str` OU `unicode`; `basestring` cobre ambos mas nao existe em Python 3
# (camada de testes externa) — mesmo padrao ja usado em
# common/capabilities.py (_STRING_TYPES), reaproveitado aqui.
try:
    _STRING_TYPES = (basestring,)  # noqa: F821  (Python 2 / IronPython 2.7)
except NameError:
    _STRING_TYPES = (str,)  # Python 3 (testes)


def _now_iso():
    return datetime.datetime.now().isoformat()


def _new_step(name):
    return {"name": name, "status": "not_run", "detail": None, "error": None, "traceback": None}


def _run_step(report, name, func):
    """Executa um passo de diagnostico isolado. Uma falha aqui NUNCA impede
    os passos seguintes nem a gravacao do relatorio final — e o requisito
    central desta prova."""
    step = _new_step(name)
    try:
        step["detail"] = func()
        step["status"] = "ok"
    except Exception as exc:
        step["status"] = "error"
        try:
            step["error"] = repr(exc)
        except Exception:
            step["error"] = "<excecao sem repr disponivel>"
        try:
            step["traceback"] = traceback.format_exc()
        except Exception:
            step["traceback"] = "<traceback indisponivel>"
    report["steps"].append(step)
    return step


# --- passo: parse tolerante de --output em sys.argv (sem argparse) --------
def _find_output_arg(argv):
    """Procura um argumento reconhecivel de saida em argv, de forma
    tolerante (nunca assume que argparse existe ou que o formato esta
    correto). Suporta as formas mais comuns:
        --output <caminho>
        --output=<caminho>
        --output:<caminho>
    Retorna o caminho cru (string) ou None. Nunca lanca excecao.
    """
    try:
        if not argv:
            return None
        for i, raw in enumerate(argv):
            try:
                token = raw
            except Exception:
                continue
            if not isinstance(token, _STRING_TYPES):
                continue
            if token == "--output":
                if i + 1 < len(argv):
                    candidate = argv[i + 1]
                    if isinstance(candidate, _STRING_TYPES) and candidate:
                        return candidate
                continue
            for sep in ("=", ":"):
                prefix = "--output" + sep
                if token.startswith(prefix) and len(token) > len(prefix):
                    return token[len(prefix):]
        return None
    except Exception:
        return None


def _try_write_to_dir(candidate_dir):
    """Tenta criar `candidate_dir` e escrever um arquivo de teste nele.
    Retorna (sucesso_bool, detalhe_str). Nunca lanca excecao."""
    try:
        if not candidate_dir:
            return False, "caminho vazio/None"
        if not os.path.isdir(candidate_dir):
            os.makedirs(candidate_dir)
        probe_path = os.path.join(candidate_dir, ".validate_command_line_execution_write_test")
        f = open(probe_path, "w")
        try:
            f.write("validate_command_line_execution write test\n")
        finally:
            f.close()
        try:
            os.remove(probe_path)
        except Exception:
            pass  # nao fatal: a escrita em si ja teve sucesso
        return True, "escrita de teste bem-sucedida em %s" % candidate_dir
    except Exception as exc:
        return False, "falha ao escrever em %r: %r" % (candidate_dir, exc)


def _resolve_output_dir(argv, report):
    """Resolucao DEFENSIVA e EM CAMADAS do diretorio de saida (local de
    gravacao GENUINAMENTE incerto quando invocado via --runscript/--project —
    ver docs/15-automation-launcher-roadmap.md). Cada tentativa e registrada
    em report["output_dir_resolution"], sucesso ou falha, nesta ordem:

        1. argumento --output em sys.argv (parse tolerante, sem argparse) —
           permite ao usuario escolher, por exemplo,
           "workspace/command-line-probe/test-01" como destino manualmente;
        2. caminho relativo ao proprio script (__file__), se disponivel:
           <repo>/workspace/logs/<timestamp>_validate_command_line_execution/;
        3. os.getcwd();
        4. (sem camada de escrita: fallback para print() em main()).

    Retorna o primeiro diretorio que aceitou escrita, ou None se todas as
    camadas falharem (caller cai para impressao via print()).
    """
    attempts = []
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Camada 1: --output em argv.
    try:
        arg_candidate = _find_output_arg(argv)
    except Exception as exc:
        arg_candidate = None
        attempts.append({
            "layer": 1, "source": "sys.argv --output", "candidate": None,
            "success": False, "detail": "falha ao parsear argv: %r" % (exc,),
        })
    else:
        if arg_candidate:
            ok, detail = _try_write_to_dir(arg_candidate)
            attempts.append({
                "layer": 1, "source": "sys.argv --output", "candidate": arg_candidate,
                "success": ok, "detail": detail,
            })
            if ok:
                report["output_dir_resolution"] = attempts
                return arg_candidate
        else:
            attempts.append({
                "layer": 1, "source": "sys.argv --output", "candidate": None,
                "success": False, "detail": "nenhum argumento --output reconhecido em argv",
            })

    # Camada 2: relativo ao proprio script (__file__).
    if _FILE_AVAILABLE and REPO_ROOT:
        script_relative = os.path.join(
            REPO_ROOT, "workspace", "logs",
            stamp + "_validate_command_line_execution")
        ok, detail = _try_write_to_dir(script_relative)
        attempts.append({
            "layer": 2, "source": "relativo a __file__ (REPO_ROOT/workspace/logs)",
            "candidate": script_relative, "success": ok, "detail": detail,
        })
        if ok:
            report["output_dir_resolution"] = attempts
            return script_relative
    else:
        attempts.append({
            "layer": 2, "source": "relativo a __file__ (REPO_ROOT/workspace/logs)",
            "candidate": None, "success": False,
            "detail": "__file__ indisponivel nesta execucao — camada pulada",
        })

    # Camada 3: diretorio de trabalho atual.
    try:
        cwd = os.getcwd()
    except Exception as exc:
        cwd = None
        attempts.append({
            "layer": 3, "source": "os.getcwd()", "candidate": None,
            "success": False, "detail": "os.getcwd() falhou: %r" % (exc,),
        })
    else:
        cwd_candidate = os.path.join(cwd, "validate_command_line_execution_" + stamp)
        ok, detail = _try_write_to_dir(cwd_candidate)
        attempts.append({
            "layer": 3, "source": "os.getcwd()", "candidate": cwd_candidate,
            "success": ok, "detail": detail,
        })
        if ok:
            report["output_dir_resolution"] = attempts
            return cwd_candidate

    # Camada 4: nenhuma escrita em disco possivel — caller cai para print().
    attempts.append({
        "layer": 4, "source": "print() (Mensagens de script do MasterTool)",
        "candidate": None, "success": None,
        "detail": "todas as camadas de escrita em disco falharam; "
                 "relatorio sera apenas impresso via print()",
    })
    report["output_dir_resolution"] = attempts
    return None


def build_report(started_at, raw_argv, script_globals):
    report = {
        # --- chaves de nivel superior EXIGIDAS (formato exato pedido) -------
        "schema_version": 1,
        "script_started": True,
        "argv": None,
        "runtime": {
            # Campos EXIGIDOS (nomes exatos): platform/version/version_info.
            "platform": None,
            "version": None,
            "version_info": None,
            # Extras (diagnostico adicional, mesma disciplina de
            # 00_smoke_test.py) — mantidos DENTRO de 'runtime'.
            "subversion": None,
            "host_executable": None,
            "scriptengine_plugin_version": None,
            "ironpython_assembly_version": None,
            "runtime_family": None,
            "runtime_version": "unknown",
            "runtime_version_evidence": None,
            "note": ("sys.version neste host pode retornar um banner do "
                     "produto, nao um numero de versao. 'runtime_version' "
                     "so e preenchido quando sys.version_info existir; caso "
                     "contrario permanece 'unknown'."),
        },
        "globals": {
            # Campos EXIGIDOS (booleanos simples: True somente quando
            # 'confirmed'; False em qualquer outro estado, inclusive
            # 'unsupported'/'unknown' — simplificacao deliberada pedida).
            "projects_available": False,
            "system_available": False,
        },
        "project": {
            # Objeto NOVO: primary_available (bool) + path (string ou None).
            "primary_available": False,
            "path": None,
        },
        "safety": {
            # Garantido por construcao: nenhuma chamada de escrita/save/
            # build/online existe neste arquivo.
            "project_modified": False,
            "save_called": False,
            "build_called": False,
            "online_operation": False,
        },
        # --- campos extras/diagnosticos (mantidos como no script anterior) -
        "script": SCRIPT_NAME,
        "purpose": ("Etapa A do roadmap de automacao: confirmar SE este "
                   "script roda via --runscript/--project/--scriptargs/"
                   "--noUI, com que argumentos, e em que contexto. Nao le "
                   "nem navega nada do projeto alem de projects.primary.path."),
        "started_at": started_at,
        "cwd": None,
        "script_file": None,
        "env": {},
        "globals_detail": {
            "projects": {"state": "unknown", "detail": None},
            "system": {"state": "unknown", "detail": None},
        },
        "project_detail": {
            "primary_state": "unknown",
            "primary_detail": None,
            "path_state": "unknown",
            "path_detail": None,
        },
        "steps": [],
        "output_dir_resolution": [],
        "completed_at": None,
        "safety_declaration": {
            "read_only": True,
            "write_operations_requested": False,
            "compilation": False,
            "online_access": False,
            "project_navigation_attempted": False,
            "project_content_accessed": False,
            "note": ("Garantido por construcao: GLOBALS_TO_CHECK = " +
                     repr(GLOBALS_TO_CHECK) + "; unico acesso ao global "
                     "'projects' alem da confirmacao de presenca de "
                     "'primary' e a leitura de 'primary.path' (via "
                     "probe_member + build_representation, mesmo padrao "
                     "aprovado em probes/03_project_navigation.py); nenhuma "
                     "outra propriedade de projects.primary e lida; nenhuma "
                     "chamada de escrita/compilacao/navegacao existe neste "
                     "arquivo."),
        },
    }

    # --- passo: sys.argv cru (dado mais importante desta prova) ------------
    def _step_argv():
        try:
            argv_list = list(raw_argv)
        except Exception:
            argv_list = None
        report["argv"] = argv_list
        return {"argv": argv_list, "count": len(argv_list) if argv_list is not None else None}
    _run_step(report, "capture_argv", _step_argv)

    # --- passo: contexto de execucao ----------------------------------------
    def _step_cwd():
        cwd = os.getcwd()
        report["cwd"] = cwd
        return cwd
    _run_step(report, "capture_cwd", _step_cwd)

    def _step_script_file():
        path = _SCRIPT_PATH if _FILE_AVAILABLE else None
        report["script_file"] = path
        return {"file_available": _FILE_AVAILABLE, "path": path}
    _run_step(report, "capture_script_file", _step_script_file)

    def _step_env():
        collected = {}
        for name in SAFE_ENV_VARS:
            try:
                collected[name] = os.environ.get(name)
            except Exception as exc:
                collected[name] = "<erro: %r>" % (exc,)
        report["env"] = collected
        return collected
    _run_step(report, "capture_safe_env_vars", _step_env)

    # --- passo: informacao do interpretador (mesma logica de
    # 00_smoke_test.py — replicada aqui porque nao existe hoje como funcao
    # extraivel em common/compatibility.py; ver docstring do modulo) -------
    def _step_interpreter():
        from common import compatibility

        info = report["runtime"]
        info["platform"] = sys.platform
        try:
            info["version"] = compatibility.python_version()
        except Exception:
            info["version"] = None
        try:
            info["version_info"] = list(sys.version_info)
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

        try:
            import re
            match = re.search(r"ScriptEngine\.plugin\s+([0-9.]+)",
                              info["version"] or "")
            info["scriptengine_plugin_version"] = match.group(1) if match else None
        except Exception:
            info["scriptengine_plugin_version"] = None

        # Nao investigado neste ciclo, mesma nota de 00_smoke_test.py.
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
    _run_step(report, "capture_interpreter_info", _step_interpreter)

    # --- passo: disponibilidade dos globais 'projects'/'system' (tri-state
    # completo em globals_detail; booleano simples em report["globals"]) ----
    def _step_globals():
        from common import compatibility

        # 'projects'/'system' podem nao existir em globals() DESTE modulo
        # (eles so existem no escopo INJETADO pelo ScriptEngine no arquivo
        # principal executado) — por isso script_globals (o globals() de
        # quem chamou main(), tipicamente o proprio modulo __main__) e
        # recebido explicitamente, nunca globals() local.
        found = compatibility.probe_globals(GLOBALS_TO_CHECK, script_globals)

        projects_obj = found.get("projects")
        if projects_obj is None:
            report["globals_detail"]["projects"] = {
                "state": "unsupported",
                "detail": {"reason": "global 'projects' nao encontrado nem no "
                                     "escopo do script nem via "
                                     "common.compatibility.get_scriptengine_global"},
            }
        else:
            report["globals_detail"]["projects"] = {
                "state": "confirmed",
                "detail": {"dotnet_type": compatibility.safe_type_name(projects_obj)},
            }
        report["globals"]["projects_available"] = (
            report["globals_detail"]["projects"]["state"] == "confirmed")

        system_obj = found.get("system")
        if system_obj is None:
            report["globals_detail"]["system"] = {
                "state": "unsupported",
                "detail": {"reason": "global 'system' nao encontrado nem no "
                                     "escopo do script nem via "
                                     "common.compatibility.get_scriptengine_global"},
            }
        else:
            report["globals_detail"]["system"] = {
                "state": "confirmed",
                "detail": {"dotnet_type": compatibility.safe_type_name(system_obj)},
            }
        report["globals"]["system_available"] = (
            report["globals_detail"]["system"]["state"] == "confirmed")

        return {"projects": report["globals_detail"]["projects"],
                "system": report["globals_detail"]["system"],
                "projects_obj": projects_obj}
    step_globals = _run_step(report, "check_globals_available", _step_globals)

    # --- passo: projects.primary (presenca) + primary.path (valor) ---------
    # Escopo minimo desta prova: SOMENTE 'primary' (presenca) e 'path'
    # (valor) sao lidos. Nenhuma outra propriedade de projects.primary
    # (is_root/handle/active_application) e tocada aqui, mesmo estando na
    # whitelist aprovada de common/capabilities.py.
    def _step_project_primary():
        from common import capabilities

        projects_obj = None
        if step_globals["status"] == "ok" and step_globals["detail"]:
            projects_obj = step_globals["detail"].get("projects_obj")

        if projects_obj is None:
            report["project_detail"]["primary_state"] = "unsupported"
            report["project_detail"]["primary_detail"] = {
                "reason": "global 'projects' indisponivel nesta execucao",
            }
            report["project"]["primary_available"] = False
            report["project"]["path"] = None
            return report["project_detail"]

        primary_record = capabilities.probe_member(
            projects_obj, "projects", "primary",
            capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
        report["project_detail"]["primary_state"] = primary_record.get("state")
        primary_obj = primary_record.pop("raw_value", None)
        report["project_detail"]["primary_detail"] = primary_record
        report["project"]["primary_available"] = (primary_record.get("state") == "confirmed")

        if not report["project"]["primary_available"] or primary_obj is None:
            report["project"]["path"] = None
            return report["project_detail"]

        # projects.primary confirmado -> le SOMENTE '.path' (ja aprovado em
        # CAPABILITY_PROBES["project"], confirmado em runtime desde
        # 00_smoke_test.py/probes/03_project_navigation.py). Mesmo padrao:
        # probe_member + build_representation, NUNCA str()/repr() direto no
        # proxy CLR.
        path_record = capabilities.probe_member(
            primary_obj, "project", "path",
            capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
        report["project_detail"]["path_state"] = path_record.get("state")

        if path_record.get("state") == "confirmed" and "raw_value" in path_record:
            value = path_record.pop("raw_value")
            python_type = capabilities.python_type_info(value)
            dotnet_type = capabilities.dotnet_type_info(value)
            representation = capabilities.build_representation(value, python_type, dotnet_type)
            path_record["python_type"] = python_type
            path_record["dotnet_type"] = dotnet_type
            path_record["representation"] = representation
            if representation.get("value_available") and isinstance(
                    representation.get("value"), _STRING_TYPES):
                report["project"]["path"] = representation["value"]
            else:
                # Valor obtido mas nao serializavel com seguranca como
                # string simples (ex.: tipo desconhecido) -> path permanece
                # None; o registro completo fica em project_detail.
                report["project"]["path"] = None
        else:
            # '.path' falhou ao ler (ou nao confirmado): falha isolada, NAO
            # impede o restante do relatorio. primary_available continua
            # True (primary em si foi confirmado); path fica None.
            report["project"]["path"] = None

        report["project_detail"]["path_detail"] = path_record
        return report["project_detail"]
    _run_step(report, "check_project_primary_and_path", _step_project_primary)

    report["completed_at"] = _now_iso()
    return report


def report_to_markdown(report):
    lines = [
        "# Probe 15 — validacao de execucao via linha de comando (Etapa A do roadmap de automacao)",
        "",
        "Modo: **somente leitura, diagnostico puro**. Ver `safety`/"
        "`safety_declaration` em `result.json` para as garantias de escopo "
        "desta execucao.",
        "",
        "- script_started: **%s**" % report["script_started"],
        "- schema_version: **%s**" % report["schema_version"],
        "- started_at: `%s`" % report["started_at"],
        "- completed_at: `%s`" % report["completed_at"],
        "- cwd: `%s`" % report["cwd"],
        "- script_file: `%s`" % report["script_file"],
        "",
        "## argv cru",
        "",
        "```",
        repr(report["argv"]),
        "```",
        "",
        "## Variaveis de ambiente (subset seguro)",
    ]
    for name, value in sorted((report.get("env") or {}).items()):
        lines.append("- `%s`: `%s`" % (name, value))
    lines.append("")
    lines.append("## Runtime / interpretador")
    interp = report["runtime"]
    lines.append("- `platform` (sys.platform): `%s`" % interp.get("platform"))
    lines.append("- `version` (sys.version, banner cru): `%s`" % interp.get("version"))
    lines.append("- `version_info`: `%s`" % (interp.get("version_info"),))
    lines.append("- `sys.subversion`: `%s`" % (interp.get("subversion"),))
    lines.append("- `sys.executable`: `%s`" % interp.get("host_executable"))
    lines.append("- Versao do plugin ScriptEngine: `%s`" % interp.get("scriptengine_plugin_version"))
    lines.append("- runtime_family: `%s`" % interp.get("runtime_family"))
    lines.append("- runtime_version: `%s` (evidencia: %s)"
                 % (interp.get("runtime_version"), interp.get("runtime_version_evidence")))
    lines.append("")
    lines.append("## Globais ('projects' / 'system')")
    lines.append("- globals.projects_available: **%s**" % report["globals"]["projects_available"])
    lines.append("- globals.system_available: **%s**" % report["globals"]["system_available"])
    lines.append("- detalhe (tri-state completo): `%r`" % (report["globals_detail"],))
    lines.append("")
    lines.append("## Projeto (`projects.primary` / `.path`)")
    lines.append("- project.primary_available: **%s**" % report["project"]["primary_available"])
    lines.append("- project.path: `%s`" % report["project"]["path"])
    lines.append("- detalhe: `%r`" % (report["project_detail"],))
    lines.append("")
    lines.append("## Passos executados")
    for step in report["steps"]:
        marker = "OK" if step["status"] == "ok" else "ERROR"
        lines.append("- [%s] **%s**" % (marker, step["name"]))
        if step["status"] != "ok":
            lines.append("  - erro: `%s`" % step["error"])
    lines.append("")
    lines.append("## Resolucao do diretorio de saida (camadas)")
    for attempt in report["output_dir_resolution"]:
        lines.append("- camada %s (%s): candidato=`%s`, sucesso=%s"
                     % (attempt["layer"], attempt["source"], attempt["candidate"],
                        attempt["success"]))
        lines.append("  - %s" % attempt["detail"])
    lines.append("")
    lines.append("## Declaracao de seguranca")
    lines.append("- safety.project_modified: %s" % report["safety"]["project_modified"])
    lines.append("- safety.save_called: %s" % report["safety"]["save_called"])
    lines.append("- safety.build_called: %s" % report["safety"]["build_called"])
    lines.append("- safety.online_operation: %s" % report["safety"]["online_operation"])
    for key, value in sorted(report["safety_declaration"].items()):
        if key == "note":
            continue
        lines.append("- %s: %s" % (key, value))
    lines.append("")
    return "\n".join(lines)


def main(script_globals=None):
    """script_globals: globals() de quem invocou (tipicamente __main__,
    injetado pelo ScriptEngine do MasterTool). Parametro explicito (em vez
    de globals() implicito deste modulo) para permitir testes automatizados
    injetarem um dict fake simulando 'projects'/'system' presentes/ausentes,
    sem depender de estado de modulo real."""
    # Passo 1: timestamp de inicio IMEDIATAMENTE, antes de qualquer outra
    # coisa — prova que o script pelo menos comecou a rodar, mesmo que
    # trave depois. Nada antes desta linha alem de imports/bootstrap.
    started_at = _now_iso()
    if script_globals is None:
        script_globals = globals()
    print("=" * 60)
    print("[OK] %s iniciado em %s" % (SCRIPT_NAME, started_at))

    try:
        raw_argv = sys.argv
    except Exception as exc:
        raw_argv = []
        print("[ERROR] sys.argv indisponivel: %r" % (exc,))

    try:
        print("[INFO] argv cru: %r" % (list(raw_argv) if raw_argv is not None else None,))
    except Exception:
        print("[INFO] argv cru: <falha ao formatar>")

    try:
        report = build_report(started_at, raw_argv, script_globals)
    except Exception as exc:
        # Falha catastrofica antes mesmo de montar o relatorio (ex.: 'common'
        # nao importavel). Registra o minimo possivel sem depender de nada
        # alem do que ja foi importado no topo do arquivo, e tenta gravar um
        # artefato de falha mesmo assim.
        print("[ERROR] Falha inesperada ao montar o relatorio: %r" % (exc,))
        tb = None
        try:
            tb = traceback.format_exc()
            print(tb)
        except Exception:
            pass
        report = {
            "schema_version": 1,
            "script_started": True,
            "argv": None,
            "runtime": {"platform": sys.platform, "version": None, "version_info": None},
            "globals": {"projects_available": False, "system_available": False},
            "project": {"primary_available": False, "path": None},
            "safety": {"project_modified": False, "save_called": False,
                      "build_called": False, "online_operation": False},
            "script": SCRIPT_NAME,
            "started_at": started_at,
            "completed_at": _now_iso(),
            "fatal_error": repr(exc),
            "fatal_traceback": tb,
        }
        try:
            report["argv"] = list(raw_argv)
        except Exception:
            pass

    # Resumo em console.
    for step in report.get("steps", []):
        marker = "[OK]" if step["status"] == "ok" else "[ERROR]"
        print("%s %s -> %s" % (marker, step["name"], step["status"]))
    print("[INFO] globals.projects_available: %s"
         % report.get("globals", {}).get("projects_available"))
    print("[INFO] globals.system_available: %s"
         % report.get("globals", {}).get("system_available"))
    print("[INFO] project.primary_available: %s"
         % report.get("project", {}).get("primary_available"))
    print("[INFO] project.path: %s" % report.get("project", {}).get("path"))

    # Gravar o relatorio, resolucao de diretorio em camadas.
    output_dir = None
    try:
        output_dir = _resolve_output_dir(raw_argv, report)
    except Exception as exc:
        print("[ERROR] Falha inesperada na resolucao do diretorio de saida: %r" % (exc,))
        report["output_dir_resolution"] = report.get("output_dir_resolution") or []
        report["output_dir_resolution"].append({
            "layer": None, "source": "_resolve_output_dir (excecao nao tratada)",
            "candidate": None, "success": False, "detail": repr(exc),
        })

    if output_dir:
        try:
            from common import file_io
            run_dir = file_io.new_export_dir(output_dir, "validate_command_line_execution")
            file_io.write_json(os.path.join(run_dir, "result.json"), report)
            file_io.write_text(os.path.join(run_dir, "report.md"), report_to_markdown(report))
            print("[OK] Relatorio gravado em: %s" % run_dir)
        except Exception as exc:
            print("[ERROR] Falha ao gravar relatorio via common.file_io: %r" % (exc,))
            try:
                traceback.print_exc()
            except Exception:
                pass
            # Fallback minimo dentro do proprio output_dir, sem depender de
            # common.file_io (pode ter sido o proprio import que falhou).
            try:
                import json
                fallback_path = os.path.join(
                    output_dir, "validate_command_line_execution_result_FALLBACK.json")
                f = open(fallback_path, "w")
                try:
                    f.write(json.dumps(report, indent=2, default=str))
                finally:
                    f.close()
                print("[OK] Relatorio de fallback (sem file_io) gravado em: %s" % fallback_path)
            except Exception as exc2:
                print("[ERROR] Fallback de gravacao tambem falhou: %r" % (exc2,))
                print("[INFO] Relatorio completo (JSON), somente em console:")
                print(repr(report))
    else:
        print("[WARN] Nenhuma camada de escrita em disco funcionou. "
             "Relatorio completo abaixo, somente em console (aba de "
             "Mensagens de script do MasterTool):")
        print(repr(report))

    print("[OK] %s concluido em %s. Nenhuma leitura/navegacao/escrita de "
         "projeto, compilacao ou operacao online foi realizada (ver "
         "'safety'/'safety_declaration' no relatorio)." % (SCRIPT_NAME, _now_iso()))
    print("=" * 60)
    return report


main()

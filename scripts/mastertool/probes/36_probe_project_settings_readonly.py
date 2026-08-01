# -*- coding: utf-8 -*-
r"""36_probe_project_settings_readonly.py - leitura SOMENTE LEITURA da
compiler version do projeto aberto, pela CADEIA LITERAL descoberta por
reflexao estatica sobre os assemblies instalados do MasterTool X.

MOTIVO DE EXISTIR
-----------------
Probe 35 emite `compiler_version` como LACUNA (`compiler_version_unresolved`)
e o registry recusa elegibilidade de autoria por causa disso. A lacuna nao era
da API: era do CATALOGO. `docs/27` catalogou apenas 15 tipos-semente, e o
acessor mora num tipo que nao estava entre eles.

A CADEIA LITERAL, COM FONTE
---------------------------
Medida em `C:\Program Files\Altus\MT9000 4.1.0\MT9000` (MT9000 4.1.0), por
`System.Reflection.Assembly.ReflectionOnlyLoadFrom` - leitura de metadados em
disco, nenhum codigo do produto executado, MasterTool NUNCA aberto:

  1. `projects.primary`
     -> objeto de projeto (o mesmo que probe 35 ja usa, via
        `common.project_access.get_primary_project`).

  2. `.project_settings`
     -> PROPRIEDADE somente-leitura (CanRead=True, CanWrite=False).
        Declarada em:
          Common\ScriptEngine3.dll
          _3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptProject11
          Property IScriptProjectSettings project_settings
          Method   IScriptProjectSettings get_project_settings()
        `IScriptProject11` esta na cadeia de heranca de `IScriptProject13`,
        que e o topo exposto no MT9000 4.1.0.
        Implementacao concreta (propriedade PUBLICA, nao explicita):
          PlugIns\9fcfbd1c-...\4.2.0.0\ScriptDriverProjects.plugin.dll
          _3S.CoDeSys.ScriptDriverProjects.ScriptProject.project_settings
        Confirmada tambem no stub oficial versionado pelo produto:
          MT9000\ScriptLib\Stubs\scriptengine\ScriptProject.pyi linhas 565-574
          ("Returns the management object for ScriptProjectSettings",
           version added 3.5.12.10).

  3. `.get_compilerversion()`
     -> METODO sem parametros, retorno `System.String`. Declarado em:
          Common\ScriptEngine3.dll
          _3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptProjectSettings2
          Method System.String get_compilerversion()
        `IScriptProjectSettings2 : IScriptProjectSettings` (heranca medida),
        e a classe concreta devolvida pelo passo 2 implementa AS DUAS:
          _3S.CoDeSys.ScriptDriverProjects.ScriptProjectSettings
            : IScriptProjectSettings2, IScriptProjectSettings
        com `System.String get_compilerversion()` PUBLICO e declarado nela.
        Por isso o metodo e visivel ao IronPython no objeto devolvido, ainda
        que a propriedade do passo 2 seja TIPADA como `IScriptProjectSettings`
        (o binding do IronPython e pelo tipo de RUNTIME, nao pelo estatico).
        Stub oficial: `ScriptProject.pyi` linhas 664-671.

O QUE ESTE PROBE NAO FAZ
------------------------
- Nao tenta acessor alternativo, nem cascata, nem busca por nome parcial:
  UMA cadeia, a medida. Se ela falhar, o resultado e LACUNA com a excecao
  registrada - nunca um segundo palpite.
- Nao usa `getattr`, `setattr`, `eval`, `dir`, nem enumeracao reflexiva:
  reflexao foi o INSTRUMENTO DE INVESTIGACAO sobre as DLLs, fora do produto;
  dentro do probe de producao ela seria exatamente a "invencao de API" que
  este arquivo existe para eliminar.
- Nao chama o mutador irmao de `get_compilerversion()` que existe no MESMO
  tipo `IScriptProjectSettings2` e que troca a versao de compilador do
  projeto - API PROIBIDA por contrato (docs/28 secao de APIs proibidas).
  Esse nome nao aparece em NENHUMA linha deste arquivo, nem em comentario:
  os dois metodos ficam a um caractere de distancia no autocompletar, e a
  unica defesa que nao depende de atencao humana e o nome nao existir aqui.
- Nao escreve, nao salva, nao compila, nao fecha o projeto.

LACUNA VIZINHA, MEDIDA E REGISTRADA, MAS NAO INSTRUMENTADA AQUI
---------------------------------------------------------------
`libraries_unresolved` (run-011: o no "Library Manager" devolve zero filhos)
tem causa medida na mesma sessao de reflexao: bibliotecas NAO sao filhos do
no. Elas saem de `IScriptLibManObject.get_libraries(bool)` -> `IList<String>`
(ScriptEngine3.dll), com o no reconhecivel por
`IScriptLibManObjectMarker.is_libman` (propriedade booleana), e a forma rica
por `IScriptLibManObject2.references` -> `IScriptLibraryReferences`, indexavel
por int/str, cujos itens expoem `name`, `namespace`, `is_placeholder`,
`is_managed`, `system_library`, `dependencies`. Fica FORA do escopo deste
probe de proposito: um probe que resolve dois bloqueadores ao mesmo tempo nao
permite atribuir a falha a um deles.

SOMENTE LEITURA. Compatibilidade: IronPython 2.7.12 (sem f-string, sem
anotacao de tipo, sem o modulo de caminhos orientado a objeto do Python 3).
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

SCRIPT_NAME = "36_probe_project_settings_readonly.py"
SCHEMA_VERSION = "1.0"

# --- a cadeia, LITERAL, como constante do modulo ----------------------------
#
# Ela e escrita UMA vez e vai para o artefato. Um artefato que mostra o valor
# sem mostrar por onde ele veio nao permite auditar a leitura depois - e a
# proxima pessoa teria de refazer a reflexao para saber se confia no numero.
ACCESSOR_CHAIN = "projects.primary.project_settings.get_compilerversion()"

ACCESSOR_CHAIN_STEPS = (
    "projects.primary",
    "project_settings (property, get-only, IScriptProject11)",
    "get_compilerversion() (method, returns System.String, "
    "IScriptProjectSettings2)",
)

ACCESSOR_CHAIN_SOURCE = (
    "reflexao estatica (ReflectionOnlyLoadFrom, metadados em disco, MasterTool "
    "nunca aberto) sobre "
    "'C:\\Program Files\\Altus\\MT9000 4.1.0\\MT9000\\Common\\ScriptEngine3.dll' "
    "-- _3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptProject11.project_settings "
    "e _3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptProjectSettings2."
    "get_compilerversion(); implementacao concreta "
    "_3S.CoDeSys.ScriptDriverProjects.ScriptProject / ScriptProjectSettings em "
    "'PlugIns\\9fcfbd1c-b152-4bd8-8bc2-9773bb566084\\4.2.0.0\\"
    "ScriptDriverProjects.plugin.dll'; stub oficial do produto "
    "'MT9000\\ScriptLib\\Stubs\\scriptengine\\ScriptProject.pyi' linhas 565-574 "
    "e 664-671"
)

# --- vocabulario fechado ----------------------------------------------------
STATUS_MEASURED = "measured"
STATUS_UNRESOLVED = "unresolved"
STATUS_FATAL = "fatal"

ALL_STATUSES = (STATUS_MEASURED, STATUS_UNRESOLVED, STATUS_FATAL)
SUCCESS_STATUSES = (STATUS_MEASURED,)

# `unresolved` NAO e sucesso e NAO e erro de execucao: a sessao rodou, a
# cadeia foi tentada, e o produto nao devolveu valor utilizavel. Codigo
# proprio (2) para nao se confundir com falha de infraestrutura (1).
EXIT_BY_STATUS = {
    STATUS_MEASURED: 0,
    STATUS_UNRESOLVED: 2,
    STATUS_FATAL: 1,
}

# Razoes fechadas de lacuna. Cada uma diz ONDE a cadeia parou -- "nao deu" sem
# o passo culpado obriga a repetir a sessao supervisionada so para descobrir.
REASON_NO_PROJECT = "sem projeto primario"
REASON_NO_SETTINGS_STEP = "passo project_settings falhou"
REASON_SETTINGS_IS_NONE = "project_settings devolveu None"
REASON_CALL_FAILED = "get_compilerversion() falhou"
REASON_EMPTY_VALUE = "get_compilerversion() devolveu valor vazio ou nao textual"

EVIDENCE_MEASURED = "measured"
EVIDENCE_UNRESOLVED = "unresolved"

# IronPython 2.7 dentro do MasterTool tem `basestring`; o CPython 3 dos testes
# nao. `py_compile` NAO pega essa diferenca -- o nome so quebraria em tempo de
# execucao, ou seja, dentro da sessao supervisionada, tarde demais.
try:
    _STRING_TYPES = (basestring,)  # noqa: F821  (Python 2 / IronPython 2.7)
except NameError:
    _STRING_TYPES = (str,)         # Python 3 (testes)


# =============================================================================
# nucleo puro -- nenhuma linha aqui toca o MasterTool
# =============================================================================

def build_evidence(value, reason):
    """Evidencia de compiler version: MEDIDA ou LACUNA, nunca ambigua.

    Duas formas fechadas e nenhuma terceira. `measured` exige valor textual
    nao vazio; `unresolved` exige valor None E razao escrita. Um valor vazio
    marcado como `measured` seria pior que a lacuna, porque a lacuna ao menos
    se anuncia. Espelha o contrato de campo que probe 35 ja consome.
    """
    if isinstance(value, _STRING_TYPES) and value.strip():
        return {
            "status": EVIDENCE_MEASURED,
            "value": value.strip(),
            "accessor_chain": ACCESSOR_CHAIN,
            "accessor_chain_steps": list(ACCESSOR_CHAIN_STEPS),
            "accessor_chain_source": ACCESSOR_CHAIN_SOURCE,
            "reason": None,
        }
    return {
        "status": EVIDENCE_UNRESOLVED,
        "value": None,
        "accessor_chain": ACCESSOR_CHAIN,
        "accessor_chain_steps": list(ACCESSOR_CHAIN_STEPS),
        "accessor_chain_source": ACCESSOR_CHAIN_SOURCE,
        "reason": reason or REASON_CALL_FAILED,
    }


def classify(evidence):
    """Status do probe DERIVADO da evidencia, nunca declarado a mao."""
    if (evidence or {}).get("status") == EVIDENCE_MEASURED:
        return STATUS_MEASURED
    return STATUS_UNRESOLVED


# =============================================================================
# orquestracao -- unica parte que toca o MasterTool
# =============================================================================

def read_compiler_version(project):
    """A CADEIA LITERAL, e SO ela. Devolve `(evidencia, passos)`.

    Cada passo e registrado com o que aconteceu, para que uma lacuna diga em
    qual elo parou. Nunca levanta: excecao vira lacuna com o `repr` da
    excecao. Nenhum acessor alternativo e tentado -- um fallback aqui seria
    adivinhacao de API disfarcada de robustez.
    """
    passos = []
    if project is None:
        passos.append({"step": "projects.primary", "ok": False,
                       "detail": REASON_NO_PROJECT})
        return build_evidence(None, REASON_NO_PROJECT), passos
    passos.append({"step": "projects.primary", "ok": True, "detail": None})

    try:
        settings = project.project_settings
    except Exception as exc:                                       # noqa: BLE001
        passos.append({"step": "project_settings", "ok": False,
                       "detail": "%s: %r" % (REASON_NO_SETTINGS_STEP, exc)})
        return build_evidence(None, "%s: %r" % (REASON_NO_SETTINGS_STEP, exc)), passos

    if settings is None:
        passos.append({"step": "project_settings", "ok": False,
                       "detail": REASON_SETTINGS_IS_NONE})
        return build_evidence(None, REASON_SETTINGS_IS_NONE), passos
    passos.append({"step": "project_settings", "ok": True, "detail": None})

    try:
        raw = settings.get_compilerversion()
    except Exception as exc:                                       # noqa: BLE001
        passos.append({"step": "get_compilerversion()", "ok": False,
                       "detail": "%s: %r" % (REASON_CALL_FAILED, exc)})
        return build_evidence(None, "%s: %r" % (REASON_CALL_FAILED, exc)), passos

    # `raw` vem do CLR como System.String; `str()` normaliza para o tipo
    # textual do interpretador antes de qualquer checagem de conteudo.
    valor = None
    try:
        if raw is not None:
            valor = str(raw)
    except Exception as exc:                                       # noqa: BLE001
        passos.append({"step": "get_compilerversion()", "ok": False,
                       "detail": "%s: %r" % (REASON_EMPTY_VALUE, exc)})
        return build_evidence(None, "%s: %r" % (REASON_EMPTY_VALUE, exc)), passos

    evidencia = build_evidence(valor, REASON_EMPTY_VALUE)
    passos.append({"step": "get_compilerversion()",
                   "ok": evidencia["status"] == EVIDENCE_MEASURED,
                   "detail": evidencia["reason"]})
    return evidencia, passos


def run_probe(script_globals, argv, project_access, file_io, probe_cli, now=None):
    """Orquestra. Nunca levanta: toda falha vira status + problema escrito."""
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": "read_only",
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "problems": [],
        "runtime": None,
        "project": {"path": None},
        "accessor_chain": ACCESSOR_CHAIN,
        "accessor_chain_source": ACCESSOR_CHAIN_SOURCE,
        "chain_steps": [],
        "compiler_version": build_evidence(None, REASON_NO_PROJECT),
        "artifacts_dir": None,
        "exit_code": EXIT_BY_STATUS[STATUS_FATAL],
        "mutating_calls": [],
    }

    def finish(status):
        result["status"] = status
        result["finished_at"] = now()
        result["exit_code"] = EXIT_BY_STATUS.get(status, EXIT_BY_STATUS[STATUS_FATAL])
        return result

    problems = []
    artifacts_dir = probe_cli.validate_output_path(
        probe_cli.find_arg(argv, "output"), REPO_ROOT, problems)
    if problems:
        for problema in problems:
            result["problems"].append(problema)
        return finish(STATUS_FATAL)
    result["artifacts_dir"] = artifacts_dir

    result["runtime"] = probe_cli.runtime_identity()

    project, access_error = project_access.get_primary_project(script_globals)
    if project is None:
        result["problems"].append("sem projeto primario: %s" % (access_error,))
        evidencia, passos = read_compiler_version(None)
        result["compiler_version"] = evidencia
        result["chain_steps"] = passos
        return finish(STATUS_FATAL)

    result["project"]["path"] = project_access.get_project_path(project)

    evidencia, passos = read_compiler_version(project)
    result["compiler_version"] = evidencia
    result["chain_steps"] = passos
    if evidencia["status"] != EVIDENCE_MEASURED:
        result["problems"].append(
            "compiler version nao lida pela cadeia %s: %s"
            % (ACCESSOR_CHAIN, evidencia["reason"]))
    return finish(classify(evidencia))


# =============================================================================
# artefatos
# =============================================================================

def build_completion(result):
    """Artefato de conclusao. E ELE que o wrapper le para dar veredito.

    Carrega a CADEIA junto do valor: quem le o veredito precisa poder conferir
    de onde veio o numero sem abrir outro arquivo.
    """
    evidencia = result.get("compiler_version") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "project": result.get("project"),
        "compiler_version": evidencia,
        "compiler_version_value": evidencia.get("value"),
        "accessor_chain": result.get("accessor_chain"),
        "accessor_chain_source": result.get("accessor_chain_source"),
        "chain_steps": result.get("chain_steps"),
        "runtime": result.get("runtime"),
        "errors": result.get("problems"),
        "mutating_calls": result.get("mutating_calls"),
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    evidencia = result.get("compiler_version") or {}
    lines = [
        "# Probe 36 - leitura read-only da compiler version do projeto",
        "",
        "Somente leitura. Nenhuma API mutavel existe neste probe.",
        "",
        "- status: **%s**" % result.get("status"),
        "- exit_code logico: **%s**" % result.get("exit_code"),
        "- projeto: `%s`" % (result.get("project") or {}).get("path"),
        "- cadeia: `%s`" % result.get("accessor_chain"),
        "- fonte da cadeia: %s" % result.get("accessor_chain_source"),
        "- compiler_version: `%s`" % evidencia.get("value"),
        "- evidencia: `%s` (razao: %s)" % (evidencia.get("status"),
                                           evidencia.get("reason")),
        "",
        "## Passos da cadeia",
        "",
    ]
    for passo in result.get("chain_steps") or []:
        lines.append("- `%s` ok=%s %s" % (passo.get("step"), passo.get("ok"),
                                          passo.get("detail") or ""))
    lines.append("")
    lines.append("## Problemas")
    lines.append("")
    for problema in result.get("problems") or []:
        lines.append("- %s" % problema)
    if not (result.get("problems") or []):
        lines.append("- nenhum")
    lines.append("")
    return "\n".join(lines)


def write_artifacts(result, file_io):
    artifacts_dir = result.get("artifacts_dir")
    if not artifacts_dir:
        return None
    file_io.ensure_dir(artifacts_dir)
    written = []
    file_io.write_json(os.path.join(artifacts_dir, "project-settings-analysis.json"),
                       result)
    written.append("project-settings-analysis.json")
    file_io.write_text(os.path.join(artifacts_dir, "project-settings-report.md"),
                       build_report_markdown(result))
    written.append("project-settings-report.md")
    file_io.write_json(os.path.join(artifacts_dir, "project-settings-completion.json"),
                       build_completion(result))
    written.append("project-settings-completion.json")
    return written


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s - SOMENTE LEITURA" % SCRIPT_NAME)
    print("[INFO] cadeia: %s" % ACCESSOR_CHAIN)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access

    try:
        result = run_probe(script_globals, list(sys.argv or []),
                           project_access, file_io, probe_cli)
    except Exception as exc:                                       # noqa: BLE001
        print("[FATAL] %r" % (exc,))
        try:
            traceback.print_exc()
        except Exception:                                          # noqa: BLE001
            pass
        return EXIT_BY_STATUS[STATUS_FATAL]

    try:
        write_artifacts(result, file_io)
    except Exception as exc:                                       # noqa: BLE001
        print("[ERROR] falha ao gravar artefatos: %r" % (exc,))

    print("[INFO] status=%s" % result.get("status"))
    print("[INFO] compiler_version=%s"
          % (result.get("compiler_version") or {}).get("value"))
    for problema in result.get("problems") or []:
        print("[PROBLEM] %s" % problema)
    print("=" * 68)
    return result.get("exit_code")


if "projects" in globals():
    sys.exit(main())

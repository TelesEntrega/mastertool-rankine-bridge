# -*- coding: utf-8 -*-
r"""48_probe_enums_readonly.py -- os enums `DutType` e `KindOfTask` sao
ALCANCAVEIS em runtime? SOMENTE LEITURA.

Contrato: `docs/35` secao 1, que declarou a lacuna e nomeou o instrumento --
"reflexao estatica sobre o enum DutType em ScriptEngine3". Este probe e esse
instrumento, com uma correcao: os DOIS enums estao CATALOGADOS nos stubs que o
produto versiona.

    ScriptIecLanguageObjectContainer.pyi L23  DutType
        Structure=1, Enumeration=2, Alias=3, Union=4
    ScriptTaskConfigObject.pyi L5             KindOfTask
        Cyclic=1, Freewheeling=2, Event=3, ExternalEvent=4, Status=5,
        ParentSynchron=6

`docs/35` afirmou que `DutType` NAO estava catalogado, e isso bloqueou `create_dut`
desde entao. A lacuna era do CATALOGO DESTE PROJETO, e nao da API -- pela QUARTA
vez. As tres anteriores estao registradas em docs/27 e docs/36.

MAS ESTAR NO STUB NAO E ESTAR ALCANCAVEL. O stub descreve a superficie .NET; o
que um script IronPython consegue NOMEAR depende do que o engine injeta no
escopo. Esta e a diferenca que este probe mede, e a razao de ele existir em vez
de eu simplesmente escrever `DutType.Structure` e torcer.

CAMINHOS TENTADOS, cada um LITERAL e escrito a mao. Nenhum nome e montado a
partir de dado, e a lista nao cresce sozinha:

    1. nome direto no escopo do script            `DutType`
    2. global injetado pelo engine                `script_globals["DutType"]`
    3. import do modulo do engine                 `from scriptengine import ...`
    4. import do assembly .NET por namespace      `from ScriptEngine3 import ...`

Cada tentativa e registrada com o que aconteceu -- achou, nao achou, ou
levantou. "Nao achei por este caminho" e evidencia; "nao existe" seria
conclusao, e este probe nao a tira.

NAO CRIA NADA. Nao ha `create_dut`, `create_task`, `create_*`, `save`, `save_as`
nem `build` neste arquivo. Ele le o escopo e relata.

Compatibilidade: IronPython 2.7.12.
"""
from __future__ import print_function

import json
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
REPO_ROOT = (os.path.abspath(os.path.join(_MASTERTOOL_DIR, "..", ".."))
             if _MASTERTOOL_DIR else None)

SCRIPT_NAME = "48_probe_enums_readonly.py"
SCHEMA_VERSION = "1.0"

# Os DOIS enums, e o que o STUB diz que eles tem. O probe compara o que achou
# em runtime contra isto -- se divergir, o stub e o runtime discordam, e isso e
# achado, nao detalhe.
ENUMS_ESPERADOS = {
    "DutType": {
        "stub": "ScriptIecLanguageObjectContainer.pyi L23",
        "members": ("Structure", "Enumeration", "Alias", "Union"),
    },
    "KindOfTask": {
        "stub": "ScriptTaskConfigObject.pyi L5",
        "members": ("Cyclic", "Freewheeling", "Event", "ExternalEvent",
                    "Status", "ParentSynchron"),
    },
}

STATUS_MEASURED = "measured"
STATUS_UNREACHABLE = "unreachable"
STATUS_FATAL = "fatal"

ALL_STATUSES = (STATUS_MEASURED, STATUS_UNREACHABLE, STATUS_FATAL)
SUCCESS_STATUSES = (STATUS_MEASURED,)

EXIT_BY_STATUS = {
    STATUS_MEASURED: 0,
    STATUS_UNREACHABLE: 4,
    STATUS_FATAL: 1,
}

ARTIFACT_NAMES = ("enum-probe-completion.json",)

try:
    _STRING_TYPES = (basestring,)                                  # noqa: F821
except NameError:
    _STRING_TYPES = (str,)


def is_text(value):
    return isinstance(value, _STRING_TYPES) and value != ""


def as_text(value):
    if value is None:
        return None
    if isinstance(value, _STRING_TYPES):
        return value
    try:
        return str(value)
    except Exception:                                              # noqa: BLE001
        return None


def describe_enum(objeto, esperados):
    """O que este objeto tem dos membros esperados.

    Le por nome LITERAL vindo da tupla do modulo -- nao enumera membros do
    objeto. Enumerar descobriria nomes que ninguem catalogou, e este probe
    existe para CONFERIR o catalogo, nao para expandi-lo em silencio.
    """
    achados = []
    faltando = []
    valores = {}
    for nome in esperados:
        try:
            membro = getattr(objeto, nome)
        except Exception:                                          # noqa: BLE001
            faltando.append(nome)
            continue
        achados.append(nome)
        valores[nome] = as_text(membro)
    return {
        "members_found": achados,
        "members_missing": faltando,
        "values": valores,
        "repr": as_text(objeto),
    }


def try_script_scope(nome, script_globals):
    """Caminho 1 e 2: o nome esta no escopo do script?"""
    if not isinstance(script_globals, dict):
        return None, "script_globals indisponivel"
    if nome not in script_globals:
        return None, "nome ausente do escopo do script"
    return script_globals[nome], None


def try_import_scriptengine(nome):
    """Caminho 3: `from scriptengine import <nome>`.

    O `import` e feito com `__import__` e o nome vem da tupla LITERAL de
    `ENUMS_ESPERADOS` -- nunca de dado externo.
    """
    try:
        modulo = __import__("scriptengine", globals(), locals(), [nome])
    except Exception as exc:                                       # noqa: BLE001
        return None, "import de scriptengine falhou: %r" % (exc,)
    try:
        return getattr(modulo, nome), None
    except Exception as exc:                                       # noqa: BLE001
        return None, "scriptengine nao expoe %s: %r" % (nome, exc)


def try_import_assembly(nome):
    """Caminho 4: o namespace .NET, se o CLR estiver acessivel."""
    try:
        modulo = __import__("ScriptEngine3", globals(), locals(), [nome])
    except Exception as exc:                                       # noqa: BLE001
        return None, "import de ScriptEngine3 falhou: %r" % (exc,)
    try:
        return getattr(modulo, nome), None
    except Exception as exc:                                       # noqa: BLE001
        return None, "ScriptEngine3 nao expoe %s: %r" % (nome, exc)


def probe_enum(nome, esperados, script_globals):
    """Tenta os quatro caminhos, na ordem, e para no primeiro que resolve.

    Registra TODOS os que tentou -- inclusive os que falharam depois de um ter
    dado certo nao seriam tentados, e por isso a lista de tentativas termina no
    sucesso. "Nao tentei" e diferente de "tentei e falhou", e o artefato
    distingue os dois.
    """
    tentativas = []

    objeto, erro = try_script_scope(nome, script_globals)
    tentativas.append({"path": "script_globals[%r]" % (nome,),
                       "found": objeto is not None, "error": erro})
    if objeto is None:
        objeto, erro = try_import_scriptengine(nome)
        tentativas.append({"path": "from scriptengine import %s" % (nome,),
                           "found": objeto is not None, "error": erro})
    if objeto is None:
        objeto, erro = try_import_assembly(nome)
        tentativas.append({"path": "from ScriptEngine3 import %s" % (nome,),
                           "found": objeto is not None, "error": erro})

    entrada = {"name": nome, "stub": esperados["stub"],
               "expected_members": list(esperados["members"]),
               "attempts": tentativas, "reachable": objeto is not None}
    if objeto is not None:
        entrada.update(describe_enum(objeto, esperados["members"]))
        entrada["matches_stub"] = (
            entrada["members_missing"] == []
            and sorted(entrada["members_found"])
            == sorted(esperados["members"]))
    return entrada


def run_probe(script_globals, argv, file_io, probe_cli, now=None):
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "artifacts_dir": None,
        "enums": [],
        "problems": [],
        "gap_notes": [],
    }

    def finish(status):
        result["status"] = status
        result["finished_at"] = now()
        result["exit_code"] = EXIT_BY_STATUS.get(status, 1)
        result["is_success"] = status in SUCCESS_STATUSES
        return result

    saida = probe_cli.find_arg(argv, "output")
    if is_text(saida):
        result["artifacts_dir"] = os.path.abspath(saida)

    for nome in sorted(ENUMS_ESPERADOS):
        result["enums"].append(
            probe_enum(nome, ENUMS_ESPERADOS[nome], script_globals))

    alcancaveis = [e for e in result["enums"] if e["reachable"]]
    if not alcancaveis:
        result["problems"].append(
            "nenhum dos enums foi alcancado por nenhum dos caminhos tentados. "
            "Isto NAO significa que eles nao existem -- significa que este "
            "probe nao os alcancou, e que a lista de caminhos precisa crescer "
            "por medicao.")
        return finish(STATUS_UNREACHABLE)

    for entrada in alcancaveis:
        if not entrada.get("matches_stub"):
            result["gap_notes"].append(
                "%s foi alcancado mas os membros divergem do stub: achados %s, "
                "faltando %s" % (entrada["name"], entrada.get("members_found"),
                                 entrada.get("members_missing")))
    return finish(STATUS_MEASURED)


def build_completion(result):
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "enums": result.get("enums"),
        "reachable": [e["name"] for e in (result.get("enums") or [])
                      if e.get("reachable")],
        "unreachable": [e["name"] for e in (result.get("enums") or [])
                        if not e.get("reachable")],
        "errors": result.get("problems"),
        "gap_notes": result.get("gap_notes"),
        "generated_at": result.get("finished_at"),
    }


def write_artifacts(result, file_io):
    destino = result.get("artifacts_dir")
    if not is_text(destino):
        return []
    escritos = []
    try:
        if not os.path.isdir(destino):
            os.makedirs(destino)
    except Exception:                                              # noqa: BLE001
        return escritos
    try:
        file_io.write_json(os.path.join(destino, "enum-probe-completion.json"),
                           build_completion(result))
        escritos.append("enum-probe-completion.json")
    except Exception:                                              # noqa: BLE001
        pass
    return escritos


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s -- enums, SOMENTE LEITURA" % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, safety

    if not safety.READ_ONLY_PHASE:
        print("[FATAL] READ_ONLY_PHASE desligado.")
        return EXIT_BY_STATUS[STATUS_FATAL]

    try:
        result = run_probe(script_globals, list(sys.argv or []), file_io,
                           probe_cli)
    except BaseException as exc:                                   # noqa: BLE001
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
    for entrada in result.get("enums") or []:
        print("[INFO] %-12s alcancavel=%-6s membros=%s"
              % (entrada["name"], entrada["reachable"],
                 entrada.get("members_found")))
    print("=" * 68)

    _encerrar_plataforma(script_globals)
    return result.get("exit_code")


def _encerrar_plataforma(script_globals):
    try:
        system = script_globals.get("system") if script_globals else None
    except Exception:                                              # noqa: BLE001
        system = None
    if system is None:
        print("[INFO] `system` indisponivel: feche a janela manualmente.")
        return
    try:
        print("[INFO] encerrando o MasterTool por system.exit(0)...")
        system.exit(0)
    except Exception as exc:                                       # noqa: BLE001
        print("[INFO] system.exit falhou (%r): feche a janela manualmente."
              % (exc,))


if "projects" in globals():
    sys.exit(main())

# -*- coding: utf-8 -*-
r"""29_preflight_program_w1_2_readonly.py — preflight SOMENTE LEITURA de W1.2.

Responde, sem criar nada, as perguntas que decidem se W1.2 pode ser aberto:

    o Application resolve pelo mesmo node_path?
    PRG_AI_TESTE ja existe?
    o container expoe o membro `create_program`, e ele e callable?
    qual e o GUID real da linguagem ST, medido em runtime?
    qual a identidade estrutural dos PROGRAMs que ja existem no projeto-base?

O que este probe NAO responde, e nao pode: **o texto padrao de um PROGRAM
recem-criado**. Ele so existe depois de `create_program`, e sera medido na
mutacao de W1.2, antes do `save_as` — do mesmo jeito que o texto canonico da
GVL foi medido em W1.1. Ler a declaracao de um PROGRAM PREEXISTENTE e evidencia
auxiliar, nunca "o canonico de um objeto novo".

NAO faz, por construcao — nenhuma destas chamadas existe neste arquivo:
`create_program`, `create_pou`, `create_gvl`, `create_folder`, `create_dut`,
`save`, `save_as`, `replace`, `remove`, `rename`, `build`, `import_xml`.

O acesso ao membro e LITERAL e nao invoca nada:

    create_program_member = iec_container.create_program   # referencia

Compatibilidade: IronPython 2.7.12.
"""
from __future__ import print_function

import hashlib
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
REPO_ROOT = os.path.abspath(os.path.join(_MASTERTOOL_DIR, "..", "..")) if _MASTERTOOL_DIR else None

SCRIPT_NAME = "29_preflight_program_w1_2_readonly.py"
SCHEMA_VERSION = "1.0"

EXPECTED_PROGRAM_NAME = "PRG_AI_TESTE"

# Candidatos LITERAIS para o global que expoe as linguagens de implementacao.
# Nenhum membro dos assemblies devolve IScriptImplementationLanguages (medido em
# docs/27), entao ele so pode vir de um global injetado pelo ScriptEngine — e o
# nome desse global nao esta catalogado. Lista fechada, escrita a mao, na mesma
# forma ja aprovada em probes/15 (GLOBALS_TO_CHECK).
#
# Globais de RISCO ficam de fora de proposito: `online` e `device_repository`
# podem iniciar comunicacao so de ter propriedade lida
# (common/compatibility.py: SIDE_EFFECT_RISK).
ST_LANGUAGE_GLOBAL_CANDIDATES = (
    "implementation_languages",
    "ImplementationLanguages",
    "languages",
)

GLOBALS_NEVER_TOUCHED = ("online", "device_repository")

# --- estados, vocabulario fechado -------------------------------------------
PREFLIGHT_PASSED = "preflight_passed"
CONTAINER_NOT_FOUND = "container_not_found"
CONTAINER_AMBIGUOUS = "container_ambiguous"
TARGET_NAME_EXISTS = "target_name_exists"
CREATE_PROGRAM_MEMBER_MISSING = "create_program_member_missing"
CREATE_PROGRAM_MEMBER_NOT_CALLABLE = "create_program_member_not_callable"
ST_LANGUAGE_GUID_MISSING = "st_language_guid_missing"
ST_LANGUAGE_GUID_AMBIGUOUS = "st_language_guid_ambiguous"
PROGRAM_IDENTITY_UNRESOLVED = "program_identity_unresolved"
RUNTIME_MISMATCH = "runtime_mismatch"
STATUS_FATAL = "fatal"

# Modo `postsave`: reabre o arquivo SALVO e prova a persistencia. Existe pela
# mesma razao de W1.1 -- `saved_as` prova que o MasterTool escreveu um arquivo,
# nao que o objeto esta dentro dele.
MODE_PREFLIGHT = "preflight"
MODE_POSTSAVE = "postsave"
VALID_MODES = (MODE_PREFLIGHT, MODE_POSTSAVE)

POSTSAVE_VERIFIED = "postsave_verified"
OUTPUT_HASH_MISMATCH = "output_hash_mismatch"
PROGRAM_MISSING = "program_missing"
PROGRAM_DUPLICATED = "program_duplicated"
UNEXPECTED_PERSISTENT_DIFF = "unexpected_persistent_diff"
TEXT_READ_GAP = "text_read_gap"

ALL_STATUSES = (
    PREFLIGHT_PASSED, CONTAINER_NOT_FOUND, CONTAINER_AMBIGUOUS,
    TARGET_NAME_EXISTS, CREATE_PROGRAM_MEMBER_MISSING,
    CREATE_PROGRAM_MEMBER_NOT_CALLABLE, ST_LANGUAGE_GUID_MISSING,
    ST_LANGUAGE_GUID_AMBIGUOUS, PROGRAM_IDENTITY_UNRESOLVED,
    RUNTIME_MISMATCH, STATUS_FATAL,
    POSTSAVE_VERIFIED, OUTPUT_HASH_MISMATCH, PROGRAM_MISSING,
    PROGRAM_DUPLICATED, UNEXPECTED_PERSISTENT_DIFF, TEXT_READ_GAP,
)

# `text_read_gap` NAO e sucesso: e limitacao registrada, e o veredito fica
# pendente de revisao humana.
SUCCESS_STATUSES = (PREFLIGHT_PASSED, POSTSAVE_VERIFIED)

EXIT_BY_STATUS = {
    PREFLIGHT_PASSED: 0,
    POSTSAVE_VERIFIED: 0,
    CONTAINER_NOT_FOUND: 2, CONTAINER_AMBIGUOUS: 2, TARGET_NAME_EXISTS: 2,
    CREATE_PROGRAM_MEMBER_MISSING: 2, CREATE_PROGRAM_MEMBER_NOT_CALLABLE: 2,
    ST_LANGUAGE_GUID_MISSING: 3, ST_LANGUAGE_GUID_AMBIGUOUS: 3,
    PROGRAM_IDENTITY_UNRESOLVED: 3,
    RUNTIME_MISMATCH: 2,
    OUTPUT_HASH_MISMATCH: 3, PROGRAM_MISSING: 3, PROGRAM_DUPLICATED: 3,
    UNEXPECTED_PERSISTENT_DIFF: 3, TEXT_READ_GAP: 4,
    STATUS_FATAL: 1,
}

ALLOWED_PERSISTENT_ADDITIONS = (EXPECTED_PROGRAM_NAME,)

VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp")

try:
    _STRING_TYPES = (basestring,)  # noqa: F821
except NameError:
    _STRING_TYPES = (str,)


def is_text(value):
    return isinstance(value, _STRING_TYPES) and value != ""


def sha256_of_text(text):
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except Exception:                                          # noqa: BLE001
        return None


def sha256_of_file(path):
    """(digest, erro). Nunca levanta. Usado pelo modo postsave para conferir o
    arquivo salvo contra o hash registrado logo apos o save_as."""
    try:
        digest = hashlib.sha256()
        handle = open(path, "rb")
        try:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
        finally:
            handle.close()
        return digest.hexdigest(), None
    except Exception as exc:                                   # noqa: BLE001
        return None, repr(exc)


def load_json_file(path):
    handle = open(path, "rb")
    try:
        raw = handle.read()
    finally:
        handle.close()
    return json.loads(raw.decode("utf-8"))


# --- identidade -------------------------------------------------------------

def object_identity(obj):
    """Membros lidos pelo nome LITERAL. `type` e o membro; `type_guid` e o nome
    do campo na saida — a troca dos dois reprovou um preflight real em W1.1."""
    identity = {"name": None, "type_guid": None, "is_folder": None,
                "is_transient": None, "has_textual_declaration": None,
                "has_textual_implementation": None, "errors": []}
    try:
        identity["name"] = str(obj.get_name(False))
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("get_name: %r" % (exc,))
    try:
        if hasattr(obj, "type"):
            identity["type_guid"] = str(obj.type)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("type: %r" % (exc,))
    try:
        if hasattr(obj, "is_folder"):
            identity["is_folder"] = bool(obj.is_folder)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("is_folder: %r" % (exc,))
    try:
        if hasattr(obj, "is_transient_object"):
            identity["is_transient"] = bool(obj.is_transient_object)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("is_transient_object: %r" % (exc,))
    try:
        if hasattr(obj, "has_textual_declaration"):
            identity["has_textual_declaration"] = bool(obj.has_textual_declaration)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("has_textual_declaration: %r" % (exc,))
    try:
        if hasattr(obj, "has_textual_implementation"):
            identity["has_textual_implementation"] = bool(obj.has_textual_implementation)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("has_textual_implementation: %r" % (exc,))
    return identity


def enumerate_children(container):
    snapshot = {"persistent": [], "transient": [], "count": None, "error": None}
    try:
        children = container.get_children(False)
        if children is None:
            snapshot["error"] = "get_children devolveu None"
            return snapshot
        snapshot["count"] = children.Count
        index = 0
        while index < children.Count:
            identity = object_identity(children[index])
            if identity.get("is_transient") is True:
                snapshot["transient"].append(identity)
            else:
                snapshot["persistent"].append(identity)
            index = index + 1
    except Exception as exc:                                   # noqa: BLE001
        snapshot["error"] = repr(exc)
    return snapshot


def count_matching_siblings(parent, expected_name, expected_type_guid):
    """Quantos irmaos casam com a identidade esperada do container."""
    matches = 0
    try:
        children = parent.get_children(False)
        if children is None:
            return None
        index = 0
        while index < children.Count:
            identity = object_identity(children[index])
            name_ok = (expected_name is None or identity.get("name") == expected_name)
            guid_ok = (expected_type_guid is None
                       or identity.get("type_guid") == expected_type_guid)
            if name_ok and guid_ok:
                matches = matches + 1
            index = index + 1
    except Exception:                                          # noqa: BLE001
        return None
    return matches


def probe_create_program_member(iec_container):
    """Referencia o membro, sem invocar. `create_program_member` morre aqui."""
    result = {"present": False, "callable": False, "type_name": None,
              "error": None}
    try:
        create_program_member = iec_container.create_program
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = repr(exc)
        return result
    result["present"] = create_program_member is not None
    try:
        result["callable"] = bool(callable(create_program_member))
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = repr(exc)
    try:
        result["type_name"] = type(create_program_member).__name__
    except Exception:                                          # noqa: BLE001
        pass
    return result


def probe_create_pou_fallback(iec_container):
    """Registra SE a sobrecarga antiga tambem esta disponivel — sem invocar e
    sem autorizar. Serve para o contrato decidir, com evidencia, se
    `create_pou` precisa entrar na allowlist de W1.2 ou pode ser proibida."""
    result = {"present": False, "callable": False, "error": None}
    try:
        create_pou_member = iec_container.create_pou
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = repr(exc)
        return result
    result["present"] = create_pou_member is not None
    try:
        result["callable"] = bool(callable(create_pou_member))
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = repr(exc)
    return result


# --- GUID da linguagem ST ---------------------------------------------------

def collect_injected_global_names(script_globals):
    """Somente os NOMES dos globais injetados. Nenhum membro e tocado.

    Enumerar nomes e inerte; tocar propriedade de global desconhecido nao e —
    `online` e `device_repository` podem iniciar comunicacao so de serem lidos.
    """
    names = []
    try:
        for key in script_globals:
            if key.startswith("_"):
                continue
            names.append(str(key))
        names.sort()
    except Exception:                                          # noqa: BLE001
        return []
    return names


def resolve_st_language_guid(script_globals):
    """GUID de ST, medido em runtime, a partir de uma lista fechada de nomes.

    Nunca aceita a string "ST" como substituto: o parametro de `create_program`
    e `Nullable<Guid>`, e passar texto seria inventar API. Se nenhum candidato
    resolver, o resultado e explicito e a fase nao pode ser aberta.
    """
    from common import compatibility

    result = {"guid": None, "value_type": None, "source": None,
              "candidates_tried": list(ST_LANGUAGE_GLOBAL_CANDIDATES),
              "resolved_by": [], "errors": []}

    for name in ST_LANGUAGE_GLOBAL_CANDIDATES:
        if name in GLOBALS_NEVER_TOUCHED:
            continue
        holder = None
        try:
            if name in script_globals:
                holder = script_globals[name]
            else:
                holder = compatibility.get_scriptengine_global(name)
        except Exception as exc:                               # noqa: BLE001
            result["errors"].append("%s: %r" % (name, exc))
            continue
        if holder is None:
            continue
        try:
            if not hasattr(holder, "st"):
                continue
            value = holder.st
        except Exception as exc:                               # noqa: BLE001
            result["errors"].append("%s.st: %r" % (name, exc))
            continue
        if value is None:
            continue
        try:
            texto = str(value)
        except Exception as exc:                               # noqa: BLE001
            result["errors"].append("%s.st str(): %r" % (name, exc))
            continue
        result["resolved_by"].append({"global": name, "value": texto})
        if result["guid"] is None:
            result["guid"] = texto
            result["source"] = name
            try:
                result["value_type"] = type(value).__name__
            except Exception:                                  # noqa: BLE001
                pass
    return result


def classify_existing_programs(container_snapshot):
    """Identidade estrutural dos objetos que ja existem, agrupada por
    `type_guid`. E o `type_guid` medido que vira criterio, nao a heuristica."""
    by_type = {}
    for item in (container_snapshot.get("persistent") or []):
        key = item.get("type_guid") or "<sem type>"
        if key not in by_type:
            by_type[key] = {"type_guid": key, "count": 0, "names": [],
                            "is_folder": [], "has_declaration": [],
                            "has_implementation": []}
        entry = by_type[key]
        entry["count"] = entry["count"] + 1
        entry["names"].append(item.get("name"))
        entry["is_folder"].append(item.get("is_folder"))
        entry["has_declaration"].append(item.get("has_textual_declaration"))
        entry["has_implementation"].append(item.get("has_textual_implementation"))
    groups = []
    for key in sorted(by_type.keys()):
        groups.append(by_type[key])
    return groups


def read_text_documents(obj):
    """Declaracao e implementacao de um objeto PREEXISTENTE. Evidencia
    auxiliar: NAO e o texto de um objeto recem-criado."""
    result = {"declaration": None, "declaration_sha256": None,
              "implementation": None, "implementation_sha256": None,
              "gap": None, "error": None}
    try:
        if hasattr(obj, "textual_declaration"):
            document = obj.textual_declaration
            if document is not None and hasattr(document, "text"):
                text = document.text
                if text is not None:
                    result["declaration"] = str(text)
                    result["declaration_sha256"] = sha256_of_text(result["declaration"])
        else:
            result["gap"] = "objeto nao expoe textual_declaration"
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = "declaration: %r" % (exc,)
    try:
        if hasattr(obj, "textual_implementation"):
            document = obj.textual_implementation
            if document is not None and hasattr(document, "text"):
                text = document.text
                if text is not None:
                    result["implementation"] = str(text)
                    result["implementation_sha256"] = sha256_of_text(
                        result["implementation"])
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = "implementation: %r" % (exc,)
    return result


def classify_program_emptiness(texts):
    """Classifica um PROGRAM preexistente. Vocabulario fechado.

    Nenhuma destas categorias autoriza chamar o texto de "canonico de um objeto
    novo" — isso so a mutacao de W1.2 pode medir.
    """
    declaration = texts.get("declaration")
    implementation = texts.get("implementation")
    if declaration is None and implementation is None:
        return "texto_ilegivel"
    corpo_declaracao = (declaration or "").strip()
    corpo_implementacao = (implementation or "").strip()
    if corpo_declaracao == "" and corpo_implementacao == "":
        return "vazio_total"
    if corpo_implementacao == "":
        return "somente_declaracao"
    if corpo_declaracao == "":
        return "somente_implementacao"
    return "declaracao_e_implementacao"


def multiset_difference(before_names, after_names):
    counts = {}
    for name in before_names:
        counts[name] = counts.get(name, 0) + 1
    added = []
    for name in after_names:
        pending = counts.get(name, 0)
        if pending > 0:
            counts[name] = pending - 1
        else:
            added.append(name)
    missing = []
    for name in before_names:
        if counts.get(name, 0) > 0:
            counts[name] = counts[name] - 1
            missing.append(name)
    return added, missing


def child_by_name(container, name):
    try:
        children = container.get_children(False)
        if children is None:
            return None
        index = 0
        while index < children.Count:
            child = children[index]
            try:
                if str(child.get_name(False)) == name:
                    return child
            except Exception:                                  # noqa: BLE001
                pass
            index = index + 1
    except Exception:                                          # noqa: BLE001
        return None
    return None


def run_postsave(container, plan, baseline, opened_path, expected_output_hash,
                 result):
    """Prova a persistencia do PROGRAM no arquivo REABERTO."""
    output_path = (plan.get("output_project") or {}).get("path")
    if not is_text(opened_path) or not is_text(output_path) or \
            os.path.normcase(os.path.abspath(opened_path)) != \
            os.path.normcase(os.path.abspath(output_path)):
        result["problems"].append(
            "projeto aberto (%r) nao e o output previsto (%r)"
            % (opened_path, output_path))
        return OUTPUT_HASH_MISMATCH

    observed, hash_error = sha256_of_file(opened_path)
    result["output_sha256_observed"] = observed
    if hash_error:
        result["problems"].append("sha256 do output ilegivel: %s" % hash_error)
        return OUTPUT_HASH_MISMATCH
    if is_text(expected_output_hash) and observed != expected_output_hash:
        result["problems"].append("sha256 do output diverge do registrado apos save_as")
        return OUTPUT_HASH_MISMATCH

    snapshot = enumerate_children(container)
    result["container_tree"] = snapshot
    if snapshot.get("error"):
        result["problems"].append("enumeracao falhou: %s" % snapshot["error"])
        return STATUS_FATAL

    encontrados = []
    for item in (snapshot.get("persistent") or []):
        if item.get("name") == EXPECTED_PROGRAM_NAME:
            encontrados.append(item)
    result["program_matches"] = len(encontrados)
    if not encontrados:
        result["problems"].append("%r nao esta no arquivo salvo"
                                  % (EXPECTED_PROGRAM_NAME,))
        return PROGRAM_MISSING
    if len(encontrados) > 1:
        result["problems"].append("%d objetos chamados %r"
                                  % (len(encontrados), EXPECTED_PROGRAM_NAME))
        return PROGRAM_DUPLICATED

    identidade = encontrados[0]
    result["program_identity"] = identidade
    if identidade.get("is_folder") is True:
        result["problems"].append("o objeto encontrado e uma pasta")
        return UNEXPECTED_PERSISTENT_DIFF
    esperado_guid = (plan.get("container") or {}).get("expected_program_type_guid")
    if is_text(esperado_guid) and identidade.get("type_guid") != esperado_guid:
        result["problems"].append(
            "type do PROGRAM salvo e %r, plano espera %r"
            % (identidade.get("type_guid"), esperado_guid))
        return UNEXPECTED_PERSISTENT_DIFF

    antes = [i.get("name") for i in ((baseline or {}).get("persistent") or [])]
    depois = [i.get("name") for i in (snapshot.get("persistent") or [])]
    added, missing = multiset_difference(antes, depois)
    result["structural_diff"] = {
        "persistent_added": added, "persistent_missing": missing,
        "allowed_additions": list(ALLOWED_PERSISTENT_ADDITIONS),
        "transient_before": [i.get("name")
                             for i in ((baseline or {}).get("transient") or [])],
        "transient_after": [i.get("name") for i in (snapshot.get("transient") or [])],
    }
    if missing:
        result["problems"].append("objetos persistentes sumiram: %r" % (missing,))
        return UNEXPECTED_PERSISTENT_DIFF
    if added != list(ALLOWED_PERSISTENT_ADDITIONS):
        result["problems"].append(
            "acrescimos persistentes = %r; permitido exatamente %r"
            % (added, list(ALLOWED_PERSISTENT_ADDITIONS)))
        return UNEXPECTED_PERSISTENT_DIFF

    textos = read_text_documents(child_by_name(container, EXPECTED_PROGRAM_NAME))
    result["program_texts"] = textos
    if textos.get("gap") or textos.get("declaration") is None:
        result["problems"].append(
            "texto do PROGRAM salvo nao pode ser lido: %s"
            % (textos.get("gap") or textos.get("error")))
        return TEXT_READ_GAP

    return POSTSAVE_VERIFIED


# --- orquestracao -----------------------------------------------------------

def run_preflight(script_globals, argv, project_access, file_io, probe_cli,
                  now=None):
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": "preflight_w1_2",
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "problems": [],
        "runtime": None,
        "opened_project": None,
        "container_node_path": None,
        "container_identity": None,
        "create_program_member": None,
        "create_pou_member": None,
        "st_language": None,
        "injected_globals": [],
        "container_tree": None,
        "program_identity_groups": [],
        "existing_programs": [],
        "artifacts_dir": None,
        "exit_code": EXIT_BY_STATUS[STATUS_FATAL],
        "canonical_text_note": (
            "O texto padrao de um PROGRAM RECEM-CRIADO nao e observavel aqui. "
            "Os textos abaixo sao de objetos PREEXISTENTES e valem como "
            "evidencia auxiliar. O padrao definitivo sera medido apos "
            "create_program, antes do save_as, na mutacao de W1.2."),
    }

    def finish(status):
        result["status"] = status
        result["finished_at"] = now()
        result["exit_code"] = EXIT_BY_STATUS.get(status, EXIT_BY_STATUS[STATUS_FATAL])
        return result

    problems = []
    plan_path = probe_cli.find_arg(argv, "plan")
    artifacts_dir = probe_cli.validate_output_path(
        probe_cli.find_arg(argv, "output"), REPO_ROOT, problems)
    result["artifacts_dir"] = artifacts_dir

    # Modo literal, de conjunto fechado. Ausente = preflight, que e o modo que
    # nao depende de nada ter sido criado antes.
    raw_mode = probe_cli.find_arg(argv, "mode")
    if raw_mode is None or raw_mode == "":
        mode = MODE_PREFLIGHT
    elif raw_mode == MODE_PREFLIGHT:
        mode = MODE_PREFLIGHT
    elif raw_mode == MODE_POSTSAVE:
        mode = MODE_POSTSAVE
    else:
        mode = None
        problems.append("--mode invalido: %r (esperado %r ou %r)"
                        % (raw_mode, MODE_PREFLIGHT, MODE_POSTSAVE))
    result["mode"] = mode
    baseline_path = probe_cli.find_arg(argv, "baseline")
    expected_output_hash = probe_cli.find_arg(argv, "output-sha256")
    result["output_sha256_expected"] = expected_output_hash

    if not is_text(plan_path) or not os.path.isfile(plan_path):
        problems.append("--plan obrigatorio e existente: %r" % (plan_path,))
    if problems:
        result["problems"].extend(problems)
        return finish(STATUS_FATAL)

    baseline = None
    if mode == MODE_POSTSAVE:
        if not is_text(baseline_path) or not os.path.isfile(baseline_path):
            result["problems"].append(
                "--baseline obrigatorio no modo postsave: sem a arvore do "
                "preflight nao existe diff estrutural")
            return finish(STATUS_FATAL)
        try:
            baseline = load_json_file(baseline_path)
        except Exception as exc:                               # noqa: BLE001
            result["problems"].append("baseline ilegivel: %r" % (exc,))
            return finish(STATUS_FATAL)

    try:
        plan = load_json_file(plan_path)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("plano ilegivel: %r" % (exc,))
        return finish(STATUS_FATAL)

    result["runtime"] = probe_cli.runtime_identity()
    expected_version = (plan.get("mastertool") or {}).get("version")
    observed_version = (result["runtime"] or {}).get("file_version")
    if observed_version != expected_version:
        result["problems"].append(
            "instalacao inesperada: observada %r, plano espera %r"
            % (observed_version, expected_version))
        return finish(RUNTIME_MISMATCH)

    project, access_error = project_access.get_primary_project(script_globals)
    if project is None:
        result["problems"].append("sem projeto primario: %s" % (access_error,))
        return finish(STATUS_FATAL)
    result["opened_project"] = project_access.get_project_path(project)

    container_spec = plan.get("container") or {}
    node_path = container_spec.get("node_path")
    result["container_node_path"] = node_path
    node_problems = []
    indexes = probe_cli.parse_node_id(node_path, node_problems,
                                      label="container.node_path")
    if indexes is None:
        result["problems"].extend(node_problems)
        return finish(CONTAINER_NOT_FOUND)

    trace = []
    container = probe_cli.descend(project, indexes, trace)
    if container is None:
        result["problems"].append("container nao alcancado pelo node_path")
        return finish(CONTAINER_NOT_FOUND)

    identity = object_identity(container)
    result["container_identity"] = identity
    expected_name = container_spec.get("expected_name")
    expected_type_guid = container_spec.get("expected_type_guid")
    if expected_name is not None and identity.get("name") != expected_name:
        result["problems"].append(
            "container resolvido e %r, plano espera %r"
            % (identity.get("name"), expected_name))
        return finish(CONTAINER_NOT_FOUND)
    if expected_type_guid is not None and identity.get("type_guid") != expected_type_guid:
        result["problems"].append(
            "type do container e %r, plano espera %r"
            % (identity.get("type_guid"), expected_type_guid))
        return finish(CONTAINER_NOT_FOUND)

    # Ambiguidade: mais de um irmao com a mesma identidade torna o caminho por
    # indice instavel entre sessoes. Achado real do projeto-base: `MainPrg`
    # aparece DUAS vezes na arvore -- como POU e como referencia de chamada sob
    # a task, com type_guid diferente. Busca por nome encontraria os dois.
    if len(indexes) > 1:
        parent_trace = []
        parent = probe_cli.descend(project, indexes[:-1], parent_trace)
        if parent is not None:
            matches = count_matching_siblings(parent, expected_name,
                                              expected_type_guid)
            result["sibling_matches"] = matches
            if matches is not None and matches > 1:
                result["problems"].append(
                    "%d irmaos casam com a identidade do container; o caminho "
                    "por indice nao e estavel" % matches)
                return finish(CONTAINER_AMBIGUOUS)

    if mode == MODE_POSTSAVE:
        return finish(run_postsave(container, plan, baseline,
                                   result["opened_project"],
                                   expected_output_hash, result))

    snapshot = enumerate_children(container)
    result["container_tree"] = snapshot
    if snapshot.get("error"):
        result["problems"].append("enumeracao falhou: %s" % snapshot["error"])
        return finish(STATUS_FATAL)

    for item in (snapshot.get("persistent") or []) + (snapshot.get("transient") or []):
        if item.get("name") == EXPECTED_PROGRAM_NAME:
            result["problems"].append(
                "%r ja existe no container" % (EXPECTED_PROGRAM_NAME,))
            return finish(TARGET_NAME_EXISTS)

    member = probe_create_program_member(container)
    result["create_program_member"] = member
    if not member.get("present"):
        result["problems"].append(
            "container nao expoe create_program: %r" % (member,))
        return finish(CREATE_PROGRAM_MEMBER_MISSING)
    if not member.get("callable"):
        result["problems"].append(
            "create_program existe mas nao e callable: %r" % (member,))
        return finish(CREATE_PROGRAM_MEMBER_NOT_CALLABLE)

    result["create_pou_member"] = probe_create_pou_fallback(container)

    result["injected_globals"] = collect_injected_global_names(script_globals)
    st_language = resolve_st_language_guid(script_globals)
    result["st_language"] = st_language
    if not is_text(st_language.get("guid")):
        result["problems"].append(
            "GUID da linguagem ST nao resolvido pelos candidatos %r; globais "
            "injetados observados: %r"
            % (list(ST_LANGUAGE_GLOBAL_CANDIDATES), result["injected_globals"]))
        return finish(ST_LANGUAGE_GUID_MISSING)
    distintos = []
    for entry in st_language.get("resolved_by") or []:
        if entry.get("value") not in distintos:
            distintos.append(entry.get("value"))
    if len(distintos) > 1:
        result["problems"].append(
            "candidatos devolveram GUIDs de ST diferentes: %r" % (distintos,))
        return finish(ST_LANGUAGE_GUID_AMBIGUOUS)

    result["program_identity_groups"] = classify_existing_programs(snapshot)

    program_paths = container_spec.get("existing_program_node_paths") or []
    for raw in program_paths:
        sub_problems = []
        sub_indexes = probe_cli.parse_node_id(raw, sub_problems,
                                              label="existing_program_node_path")
        if sub_indexes is None:
            result["problems"].extend(sub_problems)
            continue
        sub_trace = []
        node = probe_cli.descend(project, sub_indexes, sub_trace)
        if node is None:
            result["problems"].append("PROGRAM preexistente inalcancavel: %r" % (raw,))
            continue
        node_identity = object_identity(node)
        texts = read_text_documents(node)
        result["existing_programs"].append({
            "node_path": raw,
            "identity": node_identity,
            "texts": texts,
            "emptiness": classify_program_emptiness(texts),
        })

    if not result["existing_programs"]:
        result["problems"].append(
            "nenhum PROGRAM preexistente pode ser lido: sem eles nao ha "
            "identidade estrutural medida para comparar com o objeto futuro")
        return finish(PROGRAM_IDENTITY_UNRESOLVED)

    return finish(PREFLIGHT_PASSED)


# --- artefatos --------------------------------------------------------------

def build_completion(result):
    st_language = result.get("st_language") or {}
    member = result.get("create_program_member") or {}
    fallback = result.get("create_pou_member") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": result.get("mode"),
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        # Um estado de sucesso POR MODO. Comparar so com PREFLIGHT_PASSED fazia
        # o artefato de um postsave aprovado declarar is_success=False --
        # contradizendo o proprio campo `status` ao lado. Achado da run-006.
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "opened_project": result.get("opened_project"),
        "container_node_path": result.get("container_node_path"),
        "create_program_present": member.get("present"),
        "create_program_callable": member.get("callable"),
        "create_pou_present": fallback.get("present"),
        "st_language_guid": st_language.get("guid"),
        "st_language_source": st_language.get("source"),
        "program_identity_groups": result.get("program_identity_groups"),
        "existing_program_count": len(result.get("existing_programs") or []),
        "errors": result.get("problems"),
        "canonical_text_note": result.get("canonical_text_note"),
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    lines = [
        "# Probe 29 — preflight read-only de W1.2 (PROGRAM ST)",
        "",
        "Somente leitura. Nenhuma API mutavel existe neste probe.",
        "",
        "- status: **%s**" % result.get("status"),
        "- projeto aberto: `%s`" % result.get("opened_project"),
        "- container: `%s`" % result.get("container_node_path"),
        "",
        "## create_program (apenas referenciado)",
        "",
    ]
    member = result.get("create_program_member") or {}
    lines.append("- presente: **%s**" % member.get("present"))
    lines.append("- callable: **%s**" % member.get("callable"))
    lines.append("- tipo: `%s`" % member.get("type_name"))
    fallback = result.get("create_pou_member") or {}
    lines.append("- `create_pou` tambem disponivel: **%s** "
                 "(registro; nao autoriza uso)" % fallback.get("present"))
    lines.append("")
    lines.append("## Linguagem ST")
    st_language = result.get("st_language") or {}
    lines.append("- GUID: `%s`" % st_language.get("guid"))
    lines.append("- origem: `%s`" % st_language.get("source"))
    lines.append("- tipo do valor: `%s`" % st_language.get("value_type"))
    lines.append("- candidatos tentados: `%s`" % (st_language.get("candidates_tried"),))
    lines.append("")
    lines.append("## Identidade estrutural por type_guid")
    for group in result.get("program_identity_groups") or []:
        lines.append("- `%s` x%s -> %s" % (group.get("type_guid"),
                                           group.get("count"),
                                           group.get("names")))
    lines.append("")
    lines.append("## PROGRAMs preexistentes (evidencia AUXILIAR)")
    lines.append("")
    lines.append(result.get("canonical_text_note"))
    lines.append("")
    for entry in result.get("existing_programs") or []:
        lines.append("### `%s`" % entry.get("node_path"))
        lines.append("")
        lines.append("- nome: `%s`" % (entry.get("identity") or {}).get("name"))
        lines.append("- type_guid: `%s`" % (entry.get("identity") or {}).get("type_guid"))
        lines.append("- classificacao: **%s**" % entry.get("emptiness"))
        texts = entry.get("texts") or {}
        lines.append("- sha256 declaracao: `%s`" % texts.get("declaration_sha256"))
        lines.append("- sha256 implementacao: `%s`" % texts.get("implementation_sha256"))
        lines.append("")
        lines.append("```text")
        lines.append(texts.get("declaration") if texts.get("declaration") is not None
                     else "<declaracao ilegivel>")
        lines.append("```")
        lines.append("")
    lines.append("## Problemas")
    lines.append("")
    for problem in result.get("problems") or []:
        lines.append("- %s" % problem)
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
    if result.get("mode") == MODE_POSTSAVE:
        file_io.write_json(os.path.join(artifacts_dir, "w1-2-postsave-tree.json"),
                           result.get("container_tree") or {})
        written.append("w1-2-postsave-tree.json")
        file_io.write_json(os.path.join(artifacts_dir, "w1-2-postsave-program.json"),
                           {"identity": result.get("program_identity"),
                            "texts": result.get("program_texts")})
        written.append("w1-2-postsave-program.json")
        file_io.write_json(os.path.join(artifacts_dir, "w1-2-structural-diff.json"),
                           result.get("structural_diff") or {})
        written.append("w1-2-structural-diff.json")
        file_io.write_text(os.path.join(artifacts_dir, "w1-2-postsave-report.md"),
                           build_report_markdown(result))
        written.append("w1-2-postsave-report.md")
        file_io.write_json(os.path.join(artifacts_dir, "w1-2-postsave-completion.json"),
                           build_completion(result))
        written.append("w1-2-postsave-completion.json")
        return written
    file_io.write_json(os.path.join(artifacts_dir, "w1-2-preflight-tree.json"),
                       result.get("container_tree") or {})
    written.append("w1-2-preflight-tree.json")
    file_io.write_json(os.path.join(artifacts_dir, "w1-2-program-identity.json"),
                       {"groups": result.get("program_identity_groups"),
                        "existing_programs": result.get("existing_programs"),
                        "note": result.get("canonical_text_note")})
    written.append("w1-2-program-identity.json")
    file_io.write_json(os.path.join(artifacts_dir, "w1-2-st-language.json"),
                       result.get("st_language") or {})
    written.append("w1-2-st-language.json")
    file_io.write_text(os.path.join(artifacts_dir, "w1-2-preflight-report.md"),
                       build_report_markdown(result))
    written.append("w1-2-preflight-report.md")
    file_io.write_json(os.path.join(artifacts_dir, "w1-2-preflight-completion.json"),
                       build_completion(result))
    written.append("w1-2-preflight-completion.json")
    return written


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s — SOMENTE LEITURA" % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access

    try:
        result = run_preflight(script_globals, list(sys.argv or []),
                               project_access, file_io, probe_cli)
    except Exception as exc:                                   # noqa: BLE001
        print("[FATAL] %r" % (exc,))
        try:
            traceback.print_exc()
        except Exception:                                      # noqa: BLE001
            pass
        return EXIT_BY_STATUS[STATUS_FATAL]

    try:
        write_artifacts(result, file_io)
    except Exception as exc:                                   # noqa: BLE001
        print("[ERROR] falha ao gravar artefatos: %r" % (exc,))

    print("[INFO] status=%s" % result.get("status"))
    print("[INFO] create_program presente/callable: %s/%s"
          % ((result.get("create_program_member") or {}).get("present"),
             (result.get("create_program_member") or {}).get("callable")))
    print("[INFO] GUID ST: %s" % (result.get("st_language") or {}).get("guid"))
    for problem in result.get("problems") or []:
        print("[PROBLEM] %s" % problem)
    print("=" * 68)
    return result.get("exit_code")


if "projects" in globals():
    sys.exit(main())

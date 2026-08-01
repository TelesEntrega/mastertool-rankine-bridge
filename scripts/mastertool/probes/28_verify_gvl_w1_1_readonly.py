# -*- coding: utf-8 -*-
r"""28_verify_gvl_w1_1_readonly.py — verificacao SOMENTE LEITURA de W1.1.

Dois modos, ambos read-only:

    preflight   antes da mutacao: o container existe, e unico, expoe o membro
                `create_gvl` e o nome alvo ainda nao existe
    postsave    depois do save_as, sobre o ARQUIVO SALVO reaberto: a GVL
                persistiu, e so ela

O modo seleciona qual VERIFICACAO roda, nunca qual API e chamada — as duas
sao leitura, e nao existe mutador neste arquivo para ser escolhido.

Por que o modo `postsave` existe: `saved_as` prova que o MasterTool escreveu um
arquivo, nao que a GVL esta la dentro. Persistencia so se comprova reabrindo.

NAO faz, por construcao — nenhuma destas chamadas existe neste arquivo:
`create_gvl`, `create_pou`, `create_program`, `create_folder`, `create_dut`,
`save`, `save_as`, `replace`, `remove`, `rename`, `build`, `import_xml`.

O acesso ao membro `create_gvl` no preflight e LITERAL e nao invoca nada:

    create_gvl_member = iec_container.create_gvl     # referencia, nao chamada

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

SCRIPT_NAME = "28_verify_gvl_w1_1_readonly.py"
SCHEMA_VERSION = "1.0"

MODE_PREFLIGHT = "preflight"
MODE_POSTSAVE = "postsave"
VALID_MODES = (MODE_PREFLIGHT, MODE_POSTSAVE)

EXPECTED_GVL_NAME = "GVL_AI_TESTE"

# --- estados, vocabulario fechado -------------------------------------------
PREFLIGHT_PASSED = "preflight_passed"
CONTAINER_NOT_FOUND = "container_not_found"
CONTAINER_AMBIGUOUS = "container_ambiguous"
CREATE_GVL_MEMBER_MISSING = "create_gvl_member_missing"
TARGET_NAME_EXISTS = "target_name_exists"
RUNTIME_MISMATCH = "runtime_mismatch"

POSTSAVE_VERIFIED = "postsave_verified"
OUTPUT_HASH_MISMATCH = "output_hash_mismatch"
GVL_MISSING = "gvl_missing"
GVL_DUPLICATED = "gvl_duplicated"
UNEXPECTED_PERSISTENT_DIFF = "unexpected_persistent_diff"
TEXT_READ_GAP = "text_read_gap"

STATUS_FATAL = "fatal"

PREFLIGHT_STATUSES = (PREFLIGHT_PASSED, CONTAINER_NOT_FOUND, CONTAINER_AMBIGUOUS,
                      CREATE_GVL_MEMBER_MISSING, TARGET_NAME_EXISTS,
                      RUNTIME_MISMATCH, STATUS_FATAL)
POSTSAVE_STATUSES = (POSTSAVE_VERIFIED, OUTPUT_HASH_MISMATCH, GVL_MISSING,
                     GVL_DUPLICATED, UNEXPECTED_PERSISTENT_DIFF, TEXT_READ_GAP,
                     STATUS_FATAL)

# `text_read_gap` NAO e sucesso: e limitacao registrada, e o veredito da sessao
# fica pendente de revisao humana. Converte-lo em sucesso automatico
# transformaria "nao consegui ler" em "esta certo".
SUCCESS_STATUSES = (PREFLIGHT_PASSED, POSTSAVE_VERIFIED)

EXIT_BY_STATUS = {
    PREFLIGHT_PASSED: 0,
    POSTSAVE_VERIFIED: 0,
    CONTAINER_NOT_FOUND: 2,
    CONTAINER_AMBIGUOUS: 2,
    CREATE_GVL_MEMBER_MISSING: 2,
    TARGET_NAME_EXISTS: 2,
    RUNTIME_MISMATCH: 2,
    OUTPUT_HASH_MISMATCH: 3,
    GVL_MISSING: 3,
    GVL_DUPLICATED: 3,
    UNEXPECTED_PERSISTENT_DIFF: 3,
    TEXT_READ_GAP: 4,
    STATUS_FATAL: 1,
}

VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp")

# Diferenca estrutural PERMITIDA em W1.1: um objeto persistente, com forma de
# GVL, chamado GVL_AI_TESTE, no container selecionado. Mais nada.
ALLOWED_PERSISTENT_ADDITIONS = (EXPECTED_GVL_NAME,)

try:
    _STRING_TYPES = (basestring,)  # noqa: F821
except NameError:
    _STRING_TYPES = (str,)


def is_text(value):
    return isinstance(value, _STRING_TYPES) and value != ""


def sha256_of_file(path):
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


def sha256_of_text(text):
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except Exception:                                          # noqa: BLE001
        return None


def parse_mode(raw, problems):
    """Modo literal, de um conjunto fechado. Nao vem do plano e nao aceita
    prefixo nem caixa diferente."""
    if raw == MODE_PREFLIGHT:
        return MODE_PREFLIGHT
    if raw == MODE_POSTSAVE:
        return MODE_POSTSAVE
    problems.append("--mode invalido: %r (esperado %r ou %r)"
                    % (raw, MODE_PREFLIGHT, MODE_POSTSAVE))
    return None


def load_json_file(path):
    handle = open(path, "rb")
    try:
        raw = handle.read()
    finally:
        handle.close()
    return json.loads(raw.decode("utf-8"))


# --- leitura da arvore ------------------------------------------------------

def object_identity(obj):
    identity = {"name": None, "type_guid": None, "is_folder": None,
                "is_transient": None, "has_textual_declaration": None,
                "errors": []}
    try:
        identity["name"] = str(obj.get_name(False))
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("get_name: %r" % (exc,))
    # A propriedade do IScriptObject chama-se `type`; `type_guid` e apenas o
    # NOME DO CAMPO na saida do scanner aprovado (common/
    # read_only_project_scanner.py: _probe_node_identity). Ler `type_guid` do
    # proxy devolve None em silencio -- foi o que reprovou o primeiro preflight
    # real com `container_not_found`, quando o container estava certo.
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


def read_declaration_text(obj):
    result = {"text": None, "sha256": None, "linecount": None, "gap": None,
              "error": None}
    try:
        if not hasattr(obj, "textual_declaration"):
            result["gap"] = "objeto nao expoe textual_declaration"
            return result
        document = obj.textual_declaration
        if document is None:
            result["gap"] = "textual_declaration devolveu None"
            return result
        if hasattr(document, "text"):
            text = document.text
            result["text"] = None if text is None else str(text)
            if result["text"] is not None:
                result["sha256"] = sha256_of_text(result["text"])
        else:
            result["gap"] = "documento nao expoe 'text'"
        try:
            if hasattr(document, "linecount"):
                result["linecount"] = int(document.linecount)
        except Exception as exc:                               # noqa: BLE001
            result["error"] = "linecount: %r" % (exc,)
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = repr(exc)
    return result


def count_matching_siblings(parent, expected_name, expected_type_guid):
    """Quantos irmaos casam com a identidade esperada do container.

    Mais de um torna o caminho por indice instavel entre sessoes — e dai o
    estado `container_ambiguous`, que nao existe para o caso de "achei zero".
    """
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


def probe_create_gvl_member(iec_container):
    """Acesso LITERAL ao membro, sem invocar.

    `create_gvl_member` recebe a referencia e morre aqui: nada neste arquivo a
    chama. E o unico jeito honesto de responder "o container expoe o membro?"
    antes de W1.1 — perguntar sem executar.
    """
    result = {"present": False, "callable": False, "type_name": None,
              "error": None}
    try:
        create_gvl_member = iec_container.create_gvl
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = repr(exc)
        return result
    result["present"] = create_gvl_member is not None
    try:
        result["callable"] = bool(callable(create_gvl_member))
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = repr(exc)
    try:
        result["type_name"] = type(create_gvl_member).__name__
    except Exception:                                          # noqa: BLE001
        pass
    return result


def find_named(snapshot, name):
    found = []
    for item in (snapshot.get("persistent") or []):
        if item.get("name") == name:
            found.append(item)
    return found


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


# --- modo preflight ---------------------------------------------------------

def run_preflight(project, plan, container_node, parent_node, runtime, result):
    result["mode"] = MODE_PREFLIGHT

    expected_version = (plan.get("mastertool") or {}).get("version")
    observed_version = (runtime or {}).get("file_version")
    if observed_version != expected_version:
        result["problems"].append(
            "instalacao inesperada: observada %r, plano espera %r"
            % (observed_version, expected_version))
        return RUNTIME_MISMATCH

    if container_node is None:
        result["problems"].append("container nao alcancado pelo node_path")
        return CONTAINER_NOT_FOUND

    container = plan.get("container") or {}
    identity = object_identity(container_node)
    result["container_identity"] = identity
    expected_name = container.get("expected_name")
    expected_type_guid = container.get("expected_type_guid")
    if expected_name is not None and identity.get("name") != expected_name:
        result["problems"].append(
            "container resolvido e %r, plano espera %r"
            % (identity.get("name"), expected_name))
        return CONTAINER_NOT_FOUND
    if expected_type_guid is not None and identity.get("type_guid") != expected_type_guid:
        result["problems"].append(
            "type_guid do container e %r, plano espera %r"
            % (identity.get("type_guid"), expected_type_guid))
        return CONTAINER_NOT_FOUND

    if parent_node is not None:
        matches = count_matching_siblings(parent_node, expected_name, expected_type_guid)
        result["sibling_matches"] = matches
        if matches is not None and matches > 1:
            result["problems"].append(
                "%d irmaos casam com a identidade do container; o caminho por "
                "indice nao e estavel" % matches)
            return CONTAINER_AMBIGUOUS

    member = probe_create_gvl_member(container_node)
    result["create_gvl_member"] = member
    if not member.get("present") or not member.get("callable"):
        result["problems"].append(
            "container nao expoe membro create_gvl utilizavel: %r" % (member,))
        return CREATE_GVL_MEMBER_MISSING

    snapshot = enumerate_children(container_node)
    result["before_tree"] = snapshot
    if snapshot.get("error"):
        result["problems"].append("enumeracao falhou: %s" % snapshot["error"])
        return STATUS_FATAL

    existing = find_named(snapshot, EXPECTED_GVL_NAME)
    transient_named = [item for item in (snapshot.get("transient") or [])
                       if item.get("name") == EXPECTED_GVL_NAME]
    if existing or transient_named:
        result["problems"].append("%r ja existe no container" % (EXPECTED_GVL_NAME,))
        return TARGET_NAME_EXISTS

    return PREFLIGHT_PASSED


# --- modo postsave ----------------------------------------------------------

def run_postsave(project, plan, container_node, baseline, opened_path, result):
    result["mode"] = MODE_POSTSAVE

    output_path = (plan.get("output_project") or {}).get("path")
    if not is_text(opened_path) or not is_text(output_path) or \
            os.path.normcase(os.path.abspath(opened_path)) != \
            os.path.normcase(os.path.abspath(output_path)):
        result["problems"].append(
            "projeto aberto (%r) nao e o output previsto (%r)"
            % (opened_path, output_path))
        return OUTPUT_HASH_MISMATCH

    observed_hash, hash_error = sha256_of_file(opened_path)
    result["output_sha256_observed"] = observed_hash
    expected_hash = result.get("output_sha256_expected")
    if hash_error:
        result["problems"].append("sha256 do output ilegivel: %s" % hash_error)
        return OUTPUT_HASH_MISMATCH
    if is_text(expected_hash) and observed_hash != expected_hash:
        result["problems"].append(
            "sha256 do output diverge do registrado apos save_as")
        return OUTPUT_HASH_MISMATCH

    if container_node is None:
        result["problems"].append(
            "container nao resolve pelo mesmo node_path no arquivo salvo")
        return UNEXPECTED_PERSISTENT_DIFF

    snapshot = enumerate_children(container_node)
    result["postsave_tree"] = snapshot
    if snapshot.get("error"):
        result["problems"].append("enumeracao falhou: %s" % snapshot["error"])
        return STATUS_FATAL

    found = find_named(snapshot, EXPECTED_GVL_NAME)
    result["gvl_matches"] = len(found)
    if not found:
        result["problems"].append("%r nao esta no arquivo salvo" % (EXPECTED_GVL_NAME,))
        return GVL_MISSING
    if len(found) > 1:
        result["problems"].append("%d objetos chamados %r" % (len(found), EXPECTED_GVL_NAME))
        return GVL_DUPLICATED

    gvl_identity = found[0]
    result["gvl_identity"] = gvl_identity
    if gvl_identity.get("is_folder") is True:
        result["problems"].append("o objeto encontrado e uma pasta")
        return UNEXPECTED_PERSISTENT_DIFF

    before_names = [item.get("name")
                    for item in ((baseline or {}).get("persistent") or [])]
    after_names = [item.get("name") for item in (snapshot.get("persistent") or [])]
    added, missing = multiset_difference(before_names, after_names)
    result["structural_diff"] = {
        "persistent_added": added,
        "persistent_missing": missing,
        "transient_before": [item.get("name")
                             for item in ((baseline or {}).get("transient") or [])],
        "transient_after": [item.get("name") for item in (snapshot.get("transient") or [])],
        "allowed_additions": list(ALLOWED_PERSISTENT_ADDITIONS),
    }
    if missing:
        result["problems"].append("objetos persistentes sumiram: %r" % (missing,))
        return UNEXPECTED_PERSISTENT_DIFF
    if added != list(ALLOWED_PERSISTENT_ADDITIONS):
        result["problems"].append(
            "acrescimos persistentes = %r; permitido exatamente %r"
            % (added, list(ALLOWED_PERSISTENT_ADDITIONS)))
        return UNEXPECTED_PERSISTENT_DIFF

    declaration = read_declaration_text(_child_by_name(container_node, EXPECTED_GVL_NAME))
    result["gvl_declaration"] = declaration
    if declaration.get("gap") or declaration.get("text") is None:
        result["problems"].append(
            "texto canonico nao pode ser lido: %s"
            % (declaration.get("gap") or declaration.get("error")))
        return TEXT_READ_GAP

    return POSTSAVE_VERIFIED


def _child_by_name(container, name):
    """Devolve o filho de nome exato, ou None. Comparacao por igualdade."""
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


# --- orquestracao -----------------------------------------------------------

def run_verification(script_globals, argv, project_access, file_io, probe_cli,
                     now=None):
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": None,
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "problems": [],
        "runtime": None,
        "plan_path": None,
        "opened_project": None,
        "container_node_path": None,
        "container_identity": None,
        "create_gvl_member": None,
        "before_tree": None,
        "postsave_tree": None,
        "structural_diff": None,
        "gvl_identity": None,
        "gvl_declaration": None,
        "output_sha256_expected": None,
        "output_sha256_observed": None,
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
    mode = parse_mode(probe_cli.find_arg(argv, "mode"), problems)
    plan_path = probe_cli.find_arg(argv, "plan")
    artifacts_dir = probe_cli.validate_output_path(
        probe_cli.find_arg(argv, "output"), REPO_ROOT, problems)
    baseline_path = probe_cli.find_arg(argv, "baseline")
    expected_output_hash = probe_cli.find_arg(argv, "output-sha256")

    result["plan_path"] = plan_path
    result["artifacts_dir"] = artifacts_dir
    result["output_sha256_expected"] = expected_output_hash

    if not is_text(plan_path) or not os.path.isfile(plan_path):
        problems.append("--plan obrigatorio e existente: %r" % (plan_path,))
    if problems:
        result["problems"].extend(problems)
        return finish(STATUS_FATAL)

    try:
        plan = load_json_file(plan_path)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("plano ilegivel: %r" % (exc,))
        return finish(STATUS_FATAL)

    baseline = None
    if mode == MODE_POSTSAVE:
        if not is_text(baseline_path) or not os.path.isfile(baseline_path):
            result["problems"].append(
                "--baseline obrigatorio no modo postsave: sem a arvore de "
                "preflight nao existe diff estrutural")
            return finish(STATUS_FATAL)
        try:
            baseline = load_json_file(baseline_path)
        except Exception as exc:                               # noqa: BLE001
            result["problems"].append("baseline ilegivel: %r" % (exc,))
            return finish(STATUS_FATAL)

    result["runtime"] = probe_cli.runtime_identity()

    project, access_error = project_access.get_primary_project(script_globals)
    if project is None:
        result["problems"].append("sem projeto primario: %s" % (access_error,))
        return finish(STATUS_FATAL)
    opened_path = project_access.get_project_path(project)
    result["opened_project"] = opened_path

    node_path = (plan.get("container") or {}).get("node_path")
    result["container_node_path"] = node_path
    node_problems = []
    indexes = probe_cli.parse_node_id(node_path, node_problems,
                                      label="container.node_path")
    if indexes is None:
        result["problems"].extend(node_problems)
        return finish(CONTAINER_NOT_FOUND)

    trace = []
    container_node = probe_cli.descend(project, indexes, trace)
    result["container_trace"] = trace

    parent_node = None
    if len(indexes) > 1:
        parent_trace = []
        parent_node = probe_cli.descend(project, indexes[:-1], parent_trace)

    if mode == MODE_PREFLIGHT:
        return finish(run_preflight(project, plan, container_node, parent_node,
                                    result["runtime"], result))
    return finish(run_postsave(project, plan, container_node, baseline,
                               opened_path, result))


# --- artefatos --------------------------------------------------------------

def build_completion(result):
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": result.get("mode"),
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "opened_project": result.get("opened_project"),
        "container_node_path": result.get("container_node_path"),
        "create_gvl_member_present": (result.get("create_gvl_member") or {}).get("present"),
        "create_gvl_member_callable": (result.get("create_gvl_member") or {}).get("callable"),
        "gvl_matches": result.get("gvl_matches"),
        "structural_diff": result.get("structural_diff"),
        "errors": result.get("problems"),
        "mutating_calls": result.get("mutating_calls"),
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    lines = [
        "# Probe 28 — verificacao read-only de W1.1 (modo %s)" % result.get("mode"),
        "",
        "Somente leitura. Nenhuma API mutavel existe neste probe.",
        "",
        "- status: **%s**" % result.get("status"),
        "- exit_code logico: **%s**" % result.get("exit_code"),
        "- projeto aberto: `%s`" % result.get("opened_project"),
        "- container: `%s`" % result.get("container_node_path"),
        "",
    ]
    member = result.get("create_gvl_member") or {}
    if member:
        lines.append("## Membro create_gvl (apenas referenciado, nunca invocado)")
        lines.append("")
        lines.append("- presente: **%s**" % member.get("present"))
        lines.append("- callable: **%s**" % member.get("callable"))
        lines.append("- tipo: `%s`" % member.get("type_name"))
        lines.append("")
    diff = result.get("structural_diff")
    if diff:
        lines.append("## Diff estrutural")
        lines.append("")
        lines.append("- acrescentados: `%s`" % (diff.get("persistent_added"),))
        lines.append("- sumidos: `%s`" % (diff.get("persistent_missing"),))
        lines.append("- permitido: `%s`" % (diff.get("allowed_additions"),))
        lines.append("")
    declaration = result.get("gvl_declaration")
    if declaration:
        lines.append("## Texto canonico da GVL")
        lines.append("")
        lines.append("```text")
        lines.append(declaration.get("text") if declaration.get("text") is not None
                     else "<sem texto: %s>" % declaration.get("gap"))
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
    mode = result.get("mode")
    if mode == MODE_POSTSAVE:
        file_io.write_json(os.path.join(artifacts_dir, "postsave-tree.json"),
                           result.get("postsave_tree") or {})
        written.append("postsave-tree.json")
        file_io.write_json(os.path.join(artifacts_dir, "postsave-gvl.json"),
                           {"identity": result.get("gvl_identity"),
                            "declaration": result.get("gvl_declaration")})
        written.append("postsave-gvl.json")
        file_io.write_json(os.path.join(artifacts_dir, "structural-diff.json"),
                           result.get("structural_diff") or {})
        written.append("structural-diff.json")
        file_io.write_text(os.path.join(artifacts_dir, "postsave-report.md"),
                           build_report_markdown(result))
        written.append("postsave-report.md")
        file_io.write_json(os.path.join(artifacts_dir, "postsave-completion.json"),
                           build_completion(result))
        written.append("postsave-completion.json")
        return written

    file_io.write_json(os.path.join(artifacts_dir, "preflight-tree.json"),
                       result.get("before_tree") or {})
    written.append("preflight-tree.json")
    file_io.write_text(os.path.join(artifacts_dir, "preflight-report.md"),
                       build_report_markdown(result))
    written.append("preflight-report.md")
    file_io.write_json(os.path.join(artifacts_dir, "preflight-completion.json"),
                       build_completion(result))
    written.append("preflight-completion.json")
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
        result = run_verification(script_globals, list(sys.argv or []),
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

    print("[INFO] modo=%s status=%s" % (result.get("mode"), result.get("status")))
    for problem in result.get("problems") or []:
        print("[PROBLEM] %s" % problem)
    print("=" * 68)
    return result.get("exit_code")


if "projects" in globals():
    sys.exit(main())

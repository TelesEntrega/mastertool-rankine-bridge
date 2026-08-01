# -*- coding: utf-8 -*-
r"""32_edit_gvl_w1_3a.py - marco W1.3A: substituir o documento textual_declaration
de UMA GVL ja existente (GVL_AI_TESTE) e persistir por `save_as` em arquivo NOVO.

Contrato: docs/28. Plano: docs/31.

Duas invocacoes mutaveis, e so duas, cada uma com a guarda na linha
IMEDIATAMENTE anterior:

    assert_controlled_write_allowed("replace")
    text_document.replace(EXPECTED_FINAL_TEXT)

    assert_controlled_write_allowed("save_as")
    project.save_as(<caminho novo>)

O texto final e CONSTANTE LITERAL do modulo -- nunca vem do plano. O plano so
transporta dados: caminhos, hashes, node_path, run_id. Um plano que carregasse
o texto final autorizaria a si mesmo a escrever qualquer coisa.

NAO recria o objeto: GVL_AI_TESTE ja existe em W1-A1.project (saida de W1.1),
e e a UNICA entrada aceita. `create_gvl` nao existe neste arquivo.

NAO faz, por construcao: `create_gvl`, `create_program`, `create_pou`,
`create_folder`, `create_dut`, `save`, `insert`, `append`, `replace_line`,
`remove`, `rename`, `build`, `import_xml`. Depois de `replace`, uma
divergencia invalida a copia INTEIRA: registra e para, nunca tenta desfazer,
nunca `save`, nunca nova tentativa com conteudo diferente.

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

SCRIPT_NAME = "32_edit_gvl_w1_3a.py"
SCHEMA_VERSION = "1.0"

EXPECTED_PHASE = "W1_3A_EDIT_GVL"
EXPECTED_OPERATION_ID = "w1-3a-edit-gvl"
EXPECTED_TARGET_NAME = "GVL_AI_TESTE"
EXPECTED_OPERATIONS = ("replace", "save_as")

# --- textos canonicos, CONSTANTES do modulo -- NUNCA vindos do plano ---------
EXPECTED_INITIAL_TEXT = "{attribute 'qualified_only'}\nVAR_GLOBAL\nEND_VAR"
EXPECTED_FINAL_TEXT = ("{attribute 'qualified_only'}\nVAR_GLOBAL\n"
                       "    g_xTesteCriacao : BOOL;\nEND_VAR")

CALL_SITE_REPLACE = "probes/32_edit_gvl_w1_3a.py::replace_guarded"
CALL_SITE_SAVE_AS = "probes/32_edit_gvl_w1_3a.py::save_as_guarded"

STATUS_PRECONDITION_FAILED = "precondition_failed"
STATUS_REPLACE_FAILED = "replace_failed"
STATUS_REPLACED_IN_MEMORY = "replaced_in_memory"
STATUS_VERIFICATION_FAILED = "verification_failed"
STATUS_SAVE_AS_FAILED = "save_as_failed"
STATUS_SAVED_AS = "saved_as"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_PRECONDITION_FAILED, STATUS_REPLACE_FAILED,
    STATUS_REPLACED_IN_MEMORY, STATUS_VERIFICATION_FAILED,
    STATUS_SAVE_AS_FAILED, STATUS_SAVED_AS, STATUS_FATAL,
)

EXIT_BY_STATUS = {
    STATUS_SAVED_AS: 0,
    STATUS_PRECONDITION_FAILED: 2,
    STATUS_REPLACE_FAILED: 3,
    STATUS_REPLACED_IN_MEMORY: 3,
    STATUS_VERIFICATION_FAILED: 3,
    STATUS_SAVE_AS_FAILED: 4,
    STATUS_FATAL: 1,
}

STATUSES_REQUIRING_DISCARD = (
    STATUS_REPLACE_FAILED, STATUS_REPLACED_IN_MEMORY,
    STATUS_VERIFICATION_FAILED, STATUS_SAVE_AS_FAILED,
)

VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp")

ARTIFACT_NAMES = ("manifest.json", "journal.jsonl", "before-tree.json",
                  "after-replace-tree.json", "replaced-target.json",
                  "completion.json", "report.md")

PLAN_KEYS_REQUIRED = ("schema_version", "operation_id", "phase",
                      "input_project", "output_project", "container",
                      "operations", "target_name", "mastertool", "run_id",
                      "artifacts_dir")
PLAN_KEYS_OPTIONAL = ("notes",)

try:
    _STRING_TYPES = (basestring,)  # noqa: F821
except NameError:
    _STRING_TYPES = (str,)


class PlanError(Exception):
    """Plano recusado. Sempre antes de tocar o projeto."""


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


def normalize_text(text):
    """CRLF == LF, espaco no fim de cada linha ignorado, UMA quebra final
    ignorada. Qualquer outra diferenca e divergencia."""
    if text is None:
        return None
    # Unificacao de quebra de linha SEM `.replace(`: mantem exatamente UMA
    # ocorrencia de `.replace(` no modulo -- a da mutacao guardada.
    unified_chars = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\r":
            unified_chars.append("\n")
            if index + 1 < length and text[index + 1] == "\n":
                index = index + 1
        else:
            unified_chars.append(char)
        index = index + 1
    unified = "".join(unified_chars)
    lines = unified.split("\n")
    lines = [line.rstrip() for line in lines]
    if len(lines) > 1 and lines[-1] == "":
        lines = lines[:-1]
    return "\n".join(lines)


def path_is_inside(path, root):
    if not root:
        return False
    normalized = os.path.normcase(os.path.abspath(path))
    normalized_root = os.path.normcase(os.path.abspath(root))
    return (normalized == normalized_root
            or normalized.startswith(normalized_root + os.sep))


def looks_like_sha256(value):
    if not is_text(value) or len(value) != 64:
        return False
    for char in value.lower():
        if char not in "0123456789abcdef":
            return False
    return True


class Journal(object):
    """Append-only. Cada entrada e escrita ANTES do efeito que descreve."""

    def __init__(self, path, now):
        self.path = path
        self.now = now
        self.entries = []

    def record(self, entry):
        ordered = {}
        for key in entry:
            ordered[key] = entry[key]
        ordered["timestamp"] = self.now()
        ordered["sequence"] = len(self.entries)
        self.entries.append(ordered)
        if self.path:
            from common import file_io
            file_io.append_text(self.path, json.dumps(ordered, sort_keys=True) + "\n")
        return ordered


def load_plan(path):
    if not is_text(path):
        raise PlanError("--plan e obrigatorio")
    if not os.path.isabs(path):
        raise PlanError("--plan deve ser caminho absoluto: %r" % (path,))
    if " " in path:
        raise PlanError("--plan contem espaco: %r" % (path,))
    if not os.path.isfile(path):
        raise PlanError("plano inexistente: %r" % (path,))
    try:
        handle = open(path, "rb")
        try:
            raw = handle.read()
        finally:
            handle.close()
        text = raw.decode("utf-8")
    except Exception as exc:                                   # noqa: BLE001
        raise PlanError("plano ilegivel: %r" % (exc,))
    try:
        plan = json.loads(text)
    except Exception as exc:                                   # noqa: BLE001
        raise PlanError("plano nao e JSON valido: %r" % (exc,))
    if not isinstance(plan, dict):
        raise PlanError("plano deve ser um objeto JSON")
    return plan, sha256_of_text(text)


def validate_plan(plan, repo_root):
    """Tudo conferido contra CONSTANTE do modulo: um plano que declarasse a
    propria fase autorizaria a si mesmo."""
    problems = []

    unknown = []
    for key in plan:
        if key not in PLAN_KEYS_REQUIRED and key not in PLAN_KEYS_OPTIONAL:
            unknown.append(key)
    if unknown:
        unknown.sort()
        problems.append("plano tem campo(s) desconhecido(s): %s"
                        % ", ".join(unknown))
    for key in PLAN_KEYS_REQUIRED:
        if key not in plan:
            problems.append("plano sem campo obrigatorio: %s" % key)
    if problems:
        return problems

    if plan.get("schema_version") != SCHEMA_VERSION:
        problems.append("schema_version inesperado: %r" % (plan.get("schema_version"),))
    if plan.get("phase") != EXPECTED_PHASE:
        problems.append("phase inesperada: %r (esperado %r)"
                        % (plan.get("phase"), EXPECTED_PHASE))
    if plan.get("operation_id") != EXPECTED_OPERATION_ID:
        problems.append("operation_id inesperado: %r" % (plan.get("operation_id"),))
    if plan.get("target_name") != EXPECTED_TARGET_NAME:
        problems.append("target_name inesperado: %r (esperado %r)"
                        % (plan.get("target_name"), EXPECTED_TARGET_NAME))

    operations = plan.get("operations")
    if not isinstance(operations, list):
        problems.append("operations deve ser lista")
    else:
        kinds = []
        for item in operations:
            if not isinstance(item, dict):
                problems.append("cada operacao deve ser objeto: %r" % (item,))
                continue
            for key in item:
                if key not in ("kind", "name", "path"):
                    problems.append("operacao com campo desconhecido: %r" % (key,))
            kinds.append(item.get("kind"))
        if tuple(kinds) != EXPECTED_OPERATIONS:
            problems.append("operations deve ser exatamente %s, na ordem; "
                            "recebido %s" % (list(EXPECTED_OPERATIONS), kinds))

    input_project = plan.get("input_project")
    if not isinstance(input_project, dict):
        problems.append("input_project deve ser objeto")
        input_project = {}
    input_path = input_project.get("path")
    if not is_text(input_path):
        problems.append("input_project.path obrigatorio")
    elif not os.path.isabs(input_path):
        problems.append("input_project.path deve ser absoluto")
    elif " " in input_path:
        problems.append("input_project.path contem espaco")
    if not looks_like_sha256(input_project.get("sha256")):
        problems.append("input_project.sha256 ausente ou invalido")

    output_project = plan.get("output_project")
    if not isinstance(output_project, dict):
        problems.append("output_project deve ser objeto")
        output_project = {}
    output_path = output_project.get("path")
    if not is_text(output_path):
        problems.append("output_project.path obrigatorio")
    else:
        if not os.path.isabs(output_path):
            problems.append("output_project.path deve ser absoluto")
        if " " in output_path:
            problems.append("output_project.path contem espaco")
        if is_text(input_path):
            if os.path.normcase(os.path.abspath(output_path)) == \
                    os.path.normcase(os.path.abspath(input_path)):
                problems.append("output_project.path e igual a input_project.path")
        if os.path.exists(output_path):
            problems.append("output_project.path ja existe: save_as nunca sobrescreve")
        if repo_root and path_is_inside(output_path, repo_root):
            problems.append("output_project.path aponta para dentro do repositorio")

    artifacts_dir = plan.get("artifacts_dir")
    if not is_text(artifacts_dir):
        problems.append("artifacts_dir obrigatorio")
    else:
        if not os.path.isabs(artifacts_dir):
            problems.append("artifacts_dir deve ser absoluto")
        if " " in artifacts_dir:
            problems.append("artifacts_dir contem espaco")
        if repo_root and path_is_inside(artifacts_dir, repo_root):
            problems.append("artifacts_dir aponta para dentro do repositorio")

    container = plan.get("container")
    if not isinstance(container, dict):
        problems.append("container deve ser objeto")
    elif not is_text(container.get("node_path")):
        problems.append("container.node_path obrigatorio")

    mastertool = plan.get("mastertool")
    if not isinstance(mastertool, dict):
        problems.append("mastertool deve ser objeto")
    else:
        for key in ("version", "script_engine"):
            if not is_text(mastertool.get(key)):
                problems.append("mastertool.%s obrigatorio" % key)

    if not is_text(plan.get("run_id")):
        problems.append("run_id obrigatorio")

    return problems


def object_identity(obj):
    """`type` e o membro; `type_guid` e o nome do campo na saida."""
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


def find_named(snapshot, name):
    found = []
    for item in (snapshot.get("persistent") or []):
        if item.get("name") == name:
            found.append(item)
    return found


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


def read_declaration_text(obj):
    """Somente leitura -- usada ANTES do replace (precondicao) e DEPOIS
    (verificacao). `replace` nao esta nesta funcao."""
    result = {"text": None, "sha256": None, "gap": None, "error": None}
    if obj is None:
        result["gap"] = "objeto ausente"
        return result
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
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = "declaration: %r" % (exc,)
    return result


# --- as DUAS chamadas mutaveis ------------------------------------------------

def replace_guarded(text_document, safety):
    """A unica substituicao deste arquivo. O texto e a CONSTANTE do modulo
    `EXPECTED_FINAL_TEXT` -- referenciada diretamente aqui, nunca recebida
    como parametro calculado a partir do plano. Entre a guarda e a chamada
    nao ha ramo, laco, wrapper nem log."""
    safety.assert_controlled_write_allowed("replace")
    text_document.replace(EXPECTED_FINAL_TEXT)
    return True


def save_as_guarded(project, output_project_path, safety):
    """A unica persistencia deste arquivo. Sem senha, sem fallback, sem retry."""
    safety.assert_controlled_write_allowed("save_as")
    project.save_as(output_project_path)
    return True


def verify_replace(text_document, before_tree, after_tree, expected_final_text):
    """Confere o texto e o delta estrutural apos o replace. Nunca corrige nada."""
    report = {"text_matches": None, "persistent_added": [],
              "persistent_removed": [], "transient_added": [], "problems": []}

    observed_text = None
    try:
        observed_text = text_document.text
    except Exception as exc:                                   # noqa: BLE001
        report["problems"].append("nao foi possivel reler apos replace: %r" % (exc,))

    observed_normalized = normalize_text(
        str(observed_text) if observed_text is not None else None)
    expected_normalized = normalize_text(expected_final_text)
    report["text_matches"] = (observed_normalized == expected_normalized)
    if not report["text_matches"]:
        report["problems"].append("texto apos replace diverge do planejado (normalizado)")

    before_names = [item.get("name") for item in (before_tree.get("persistent") or [])]
    after_names = [item.get("name") for item in (after_tree.get("persistent") or [])]
    added, missing = multiset_difference(before_names, after_names)
    report["persistent_added"] = added
    report["persistent_removed"] = missing
    if added:
        report["problems"].append("objetos persistentes novos apos replace: %r" % (added,))
    if missing:
        report["problems"].append("objetos persistentes sumiram apos replace: %r" % (missing,))

    before_transient = [item.get("name") for item in (before_tree.get("transient") or [])]
    after_transient = [item.get("name") for item in (after_tree.get("transient") or [])]
    transient_added, _ignored = multiset_difference(before_transient, after_transient)
    report["transient_added"] = transient_added

    if before_tree.get("error") or after_tree.get("error"):
        report["problems"].append(
            "enumeracao com erro (antes=%r, depois=%r)"
            % (before_tree.get("error"), after_tree.get("error")))

    report["ok"] = not report["problems"]
    return report


def run_w1_3a(script_globals, argv, safety, project_access, file_io, probe_cli,
             now=None):
    """Executa W1.3A. Injecao explicita dos modulos para teste com dubles."""
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "phase_expected": EXPECTED_PHASE,
        "phase_observed": None,
        "plan_sha256": None,
        "plan_path": None,
        "input_project": {"path": None, "sha256_expected": None,
                          "sha256_observed": None, "matches": None},
        "output_project": {"path": None, "exists_before": None,
                           "exists_after": None},
        "operations_requested": [],
        "operations_authorized": [],
        "operations_executed": [],
        "problems": [],
        "gap_notes": [],
        "runtime": None,
        "before_tree": None,
        "after_replace_tree": None,
        "target_before": None,
        "target_after": None,
        "verification": None,
        "requires_copy_discard": False,
        "artifacts_dir": None,
        "exit_code": EXIT_BY_STATUS[STATUS_FATAL],
    }
    journal = Journal(None, now)

    def finish(status):
        result["status"] = status
        result["finished_at"] = now()
        result["exit_code"] = EXIT_BY_STATUS.get(status, EXIT_BY_STATUS[STATUS_FATAL])
        result["requires_copy_discard"] = status in STATUSES_REQUIRING_DISCARD
        result["journal"] = journal.entries
        return result

    plan_path = probe_cli.find_arg(argv, "plan")
    result["plan_path"] = plan_path
    try:
        plan, plan_hash = load_plan(plan_path)
    except PlanError as exc:
        result["problems"].append(str(exc))
        return finish(STATUS_PRECONDITION_FAILED)
    result["plan_sha256"] = plan_hash

    problems = validate_plan(plan, REPO_ROOT)
    if problems:
        result["problems"].extend(problems)
        return finish(STATUS_PRECONDITION_FAILED)

    input_path = plan["input_project"]["path"]
    output_path = plan["output_project"]["path"]
    artifacts_dir = plan["artifacts_dir"]
    result["input_project"]["path"] = input_path
    result["input_project"]["sha256_expected"] = plan["input_project"]["sha256"]
    result["output_project"]["path"] = output_path
    result["artifacts_dir"] = artifacts_dir

    journal.path = os.path.join(artifacts_dir, "journal.jsonl")
    journal.record({"event": "plan_accepted", "plan_sha256": plan_hash,
                    "phase_expected": EXPECTED_PHASE})

    result["runtime"] = probe_cli.runtime_identity()

    try:
        phase_observed = safety.CONTROLLED_WRITE_PHASE
    except Exception:                                          # noqa: BLE001
        phase_observed = None
    result["phase_observed"] = phase_observed
    if phase_observed != EXPECTED_PHASE:
        result["problems"].append(
            "fase controlada observada e %r, esperada %r"
            % (phase_observed, EXPECTED_PHASE))

    expected_version = plan["mastertool"].get("version")
    observed_version = (result["runtime"] or {}).get("file_version")
    if observed_version != expected_version:
        result["problems"].append(
            "instalacao inesperada: observada %r, plano espera %r"
            % (observed_version, expected_version))

    project, access_error = project_access.get_primary_project(script_globals)
    if project is None:
        result["problems"].append("sem projeto primario: %s" % (access_error,))
        return finish(STATUS_PRECONDITION_FAILED)

    opened_path = project_access.get_project_path(project)
    if not is_text(opened_path) or \
            os.path.normcase(os.path.abspath(opened_path)) != \
            os.path.normcase(os.path.abspath(input_path)):
        result["problems"].append(
            "projeto aberto (%r) nao e o input_project do plano (%r)"
            % (opened_path, input_path))
        return finish(STATUS_PRECONDITION_FAILED)

    observed_hash, hash_error = sha256_of_file(opened_path)
    result["input_project"]["sha256_observed"] = observed_hash
    result["input_project"]["matches"] = (observed_hash == plan["input_project"]["sha256"])
    if hash_error:
        result["problems"].append("sha256 do projeto aberto ilegivel: %s" % hash_error)
    elif not result["input_project"]["matches"]:
        result["problems"].append("sha256 do projeto aberto diverge do plano")

    exists_before = os.path.exists(output_path)
    result["output_project"]["exists_before"] = exists_before
    if exists_before:
        result["problems"].append("arquivo de saida ja existe: %r" % (output_path,))

    container_spec = plan["container"]
    node_indexes = probe_cli.parse_node_id(
        container_spec["node_path"], result["problems"], label="container.node_path")

    if result["problems"]:
        journal.record({"event": "precondition_failed",
                        "problem_count": len(result["problems"])})
        return finish(STATUS_PRECONDITION_FAILED)

    trace = []
    iec_container = probe_cli.descend(project, node_indexes, trace)
    result["container_trace"] = trace
    if iec_container is None:
        result["problems"].append("container IEC nao alcancado por node_path")
        journal.record({"event": "precondition_failed", "reason": "container_absent"})
        return finish(STATUS_PRECONDITION_FAILED)

    container_identity = object_identity(iec_container)
    result["container_identity"] = container_identity
    expected_name = container_spec.get("expected_name")
    expected_container_guid = container_spec.get("expected_type_guid")
    if expected_name is not None and container_identity.get("name") != expected_name:
        result["problems"].append(
            "container resolvido e %r, plano espera %r"
            % (container_identity.get("name"), expected_name))
        journal.record({"event": "precondition_failed", "reason": "container_mismatch"})
        return finish(STATUS_PRECONDITION_FAILED)
    if expected_container_guid is not None and \
            container_identity.get("type_guid") != expected_container_guid:
        result["problems"].append(
            "type do container e %r, plano espera %r"
            % (container_identity.get("type_guid"), expected_container_guid))
        journal.record({"event": "precondition_failed", "reason": "container_type_mismatch"})
        return finish(STATUS_PRECONDITION_FAILED)

    before = enumerate_children(iec_container)
    result["before_tree"] = before
    if before.get("error"):
        result["problems"].append("enumeracao inicial falhou: %s" % before["error"])
        journal.record({"event": "precondition_failed", "reason": "enumerate_failed"})
        return finish(STATUS_PRECONDITION_FAILED)

    found = find_named(before, EXPECTED_TARGET_NAME)
    if not found:
        result["problems"].append("%r nao encontrada no container" % (EXPECTED_TARGET_NAME,))
        journal.record({"event": "precondition_failed", "reason": "target_absent"})
        return finish(STATUS_PRECONDITION_FAILED)
    if len(found) > 1:
        result["problems"].append("%d objetos chamados %r" % (len(found), EXPECTED_TARGET_NAME))
        journal.record({"event": "precondition_failed", "reason": "target_duplicated"})
        return finish(STATUS_PRECONDITION_FAILED)

    target_identity = found[0]
    result["target_before"] = target_identity
    expected_target_guid = container_spec.get("expected_target_type_guid")
    if expected_target_guid is not None and \
            target_identity.get("type_guid") != expected_target_guid:
        result["problems"].append(
            "type do alvo e %r, plano espera %r"
            % (target_identity.get("type_guid"), expected_target_guid))
        journal.record({"event": "precondition_failed", "reason": "target_type_mismatch"})
        return finish(STATUS_PRECONDITION_FAILED)
    if target_identity.get("is_folder") is True:
        result["problems"].append("o objeto encontrado e uma pasta")
        journal.record({"event": "precondition_failed", "reason": "target_is_folder"})
        return finish(STATUS_PRECONDITION_FAILED)

    target_object = child_by_name(iec_container, EXPECTED_TARGET_NAME)
    current_text = read_declaration_text(target_object)
    result["target_before_text"] = current_text
    if current_text.get("gap") or current_text.get("text") is None:
        result["problems"].append(
            "texto atual nao pode ser lido: %s"
            % (current_text.get("gap") or current_text.get("error")))
        journal.record({"event": "precondition_failed", "reason": "text_read_gap"})
        return finish(STATUS_PRECONDITION_FAILED)

    observed_normalized = normalize_text(current_text.get("text"))
    expected_initial_normalized = normalize_text(EXPECTED_INITIAL_TEXT)
    if observed_normalized != expected_initial_normalized:
        result["problems"].append(
            "texto inicial diverge do esperado (normalizado): nao se adapta o "
            "conteudo automaticamente")
        journal.record({"event": "precondition_failed", "reason": "initial_text_mismatch"})
        return finish(STATUS_PRECONDITION_FAILED)

    try:
        text_document = target_object.textual_declaration
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("textual_declaration inacessivel: %r" % (exc,))
        journal.record({"event": "precondition_failed", "reason": "document_inaccessible"})
        return finish(STATUS_PRECONDITION_FAILED)
    if text_document is None:
        result["problems"].append("textual_declaration devolveu None")
        journal.record({"event": "precondition_failed", "reason": "document_none"})
        return finish(STATUS_PRECONDITION_FAILED)

    journal.record({"event": "preconditions_passed",
                    "children_before": before.get("count")})

    # --- mutacao 1: replace ---------------------------------------------------
    result["operations_requested"].append("replace")
    journal.record({"event": "mutation_attempt", "operation": "replace",
                    "document_operation": "replace_gvl_declaration",
                    "phase": phase_observed, "call_site": CALL_SITE_REPLACE,
                    "state_before": {"children": before.get("count")}})
    try:
        replace_guarded(text_document, safety)
    except safety.SafetyError as exc:
        result["problems"].append("autorizacao de replace recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied", "operation": "replace",
                        "document_operation": "replace_gvl_declaration",
                        "call_site": CALL_SITE_REPLACE, "error": repr(exc)})
        return finish(STATUS_PRECONDITION_FAILED)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("replace levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed", "operation": "replace",
                        "document_operation": "replace_gvl_declaration",
                        "call_site": CALL_SITE_REPLACE, "error": repr(exc)})
        return finish(STATUS_REPLACE_FAILED)

    result["operations_authorized"].append("replace")
    result["operations_executed"].append("replace")

    after = enumerate_children(iec_container)
    result["after_replace_tree"] = after
    journal.record({"event": "mutation_done", "operation": "replace",
                    "document_operation": "replace_gvl_declaration",
                    "call_site": CALL_SITE_REPLACE,
                    "state_after": {"children": after.get("count")}})

    verification = verify_replace(text_document, before, after, EXPECTED_FINAL_TEXT)
    result["verification"] = verification
    result["target_after"] = find_named(after, EXPECTED_TARGET_NAME)

    if not verification.get("ok"):
        result["problems"].extend(verification.get("problems") or [])
        journal.record({"event": "verification_failed",
                        "problem_count": len(verification.get("problems") or [])})
        return finish(STATUS_VERIFICATION_FAILED)

    journal.record({"event": "verification_passed",
                    "persistent_added": verification.get("persistent_added")})

    # --- mutacao 2: save_as ---------------------------------------------------
    result["operations_requested"].append("save_as")
    journal.record({"event": "mutation_attempt", "operation": "save_as",
                    "phase": phase_observed, "call_site": CALL_SITE_SAVE_AS,
                    "state_before": {"output_exists": os.path.exists(output_path)}})
    try:
        save_as_guarded(project, output_path, safety)
    except safety.SafetyError as exc:
        result["problems"].append("autorizacao de save_as recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied", "operation": "save_as",
                        "call_site": CALL_SITE_SAVE_AS, "error": repr(exc)})
        return finish(STATUS_REPLACED_IN_MEMORY)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("save_as levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed", "operation": "save_as",
                        "call_site": CALL_SITE_SAVE_AS, "error": repr(exc)})
        return finish(STATUS_SAVE_AS_FAILED)

    result["operations_authorized"].append("save_as")
    result["operations_executed"].append("save_as")

    exists_after = os.path.exists(output_path)
    result["output_project"]["exists_after"] = exists_after
    journal.record({"event": "mutation_done", "operation": "save_as",
                    "call_site": CALL_SITE_SAVE_AS,
                    "state_after": {"output_exists": exists_after}})
    if not exists_after:
        result["problems"].append(
            "save_as nao levantou, mas o arquivo de saida nao existe")
        return finish(STATUS_SAVE_AS_FAILED)

    return finish(STATUS_SAVED_AS)


def build_completion(result):
    """Escrito por ULTIMO: e o sinal de conclusao."""
    no_other_mutator = (tuple(result.get("operations_requested") or ())
                        in ((), ("replace",), EXPECTED_OPERATIONS))
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "phase": result.get("phase_observed"),
        "plan_sha256": result.get("plan_sha256"),
        "input_project_sha256_before": result.get("input_project", {}).get("sha256_observed"),
        "operations_requested": result.get("operations_requested"),
        "operations_authorized": result.get("operations_authorized"),
        "operations_executed": result.get("operations_executed"),
        "output_project_path": result.get("output_project", {}).get("path"),
        "output_project_exists": result.get("output_project", {}).get("exists_after"),
        "requires_copy_discard": result.get("requires_copy_discard"),
        "errors": result.get("problems"),
        "gap_notes": result.get("gap_notes"),
        "no_other_mutator_requested": no_other_mutator,
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    lines = [
        "# Probe 32 - W1.3A: editar GVL_AI_TESTE e salvar por save_as",
        "",
        "- status: **%s**" % result.get("status"),
        "- exit_code logico: **%s**" % result.get("exit_code"),
        "- fase observada: `%s`" % result.get("phase_observed"),
        "- copia precisa ser descartada: **%s**" % result.get("requires_copy_discard"),
        "",
        "## Operacoes",
        "",
        "- solicitadas: `%s`" % (result.get("operations_requested"),),
        "- executadas: `%s`" % (result.get("operations_executed"),),
        "",
        "## Problemas",
        "",
    ]
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
    written = []
    file_io.ensure_dir(artifacts_dir)

    manifest = {}
    for key in result:
        if key in ("journal",):
            continue
        manifest[key] = result[key]
    manifest["artifact_names"] = list(ARTIFACT_NAMES)
    manifest["volatile_fields"] = list(VOLATILE_FIELDS)
    manifest["exit_code_by_status"] = EXIT_BY_STATUS

    file_io.write_json(os.path.join(artifacts_dir, "manifest.json"), manifest)
    written.append("manifest.json")
    file_io.write_json(os.path.join(artifacts_dir, "before-tree.json"),
                       result.get("before_tree") or {})
    written.append("before-tree.json")
    file_io.write_json(os.path.join(artifacts_dir, "after-replace-tree.json"),
                       result.get("after_replace_tree") or {})
    written.append("after-replace-tree.json")
    file_io.write_json(os.path.join(artifacts_dir, "replaced-target.json"),
                       {"before": result.get("target_before"),
                        "after": result.get("target_after")})
    written.append("replaced-target.json")
    file_io.write_text(os.path.join(artifacts_dir, "report.md"),
                       build_report_markdown(result))
    written.append("report.md")
    file_io.write_json(os.path.join(artifacts_dir, "completion.json"),
                       build_completion(result))
    written.append("completion.json")
    return written


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s - W1.3A (escrita controlada)" % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access, safety

    try:
        result = run_w1_3a(script_globals, list(sys.argv or []), safety,
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
    print("[INFO] operacoes executadas: %s" % (result.get("operations_executed"),))
    print("[INFO] descartar a copia: %s" % result.get("requires_copy_discard"))
    for problem in result.get("problems") or []:
        print("[PROBLEM] %s" % problem)
    print("=" * 68)
    return result.get("exit_code")


if "projects" in globals():
    sys.exit(main())

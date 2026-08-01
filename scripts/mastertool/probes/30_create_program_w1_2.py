# -*- coding: utf-8 -*-
r"""30_create_program_w1_2.py — marco W1.2: criar UM `PROGRAM` ST vazio e
persistir por `save_as` em arquivo NOVO.

Contrato: `docs/28`. Plano: `docs/30`.

Duas invocacoes mutaveis, e so duas, cada uma com a guarda na linha
IMEDIATAMENTE anterior:

    assert_controlled_write_allowed("create_program")
    container.create_program("PRG_AI_TESTE", st_language_guid)

    assert_controlled_write_allowed("save_as")
    project.save_as(<caminho novo>)

O GUID da linguagem chega MEDIDO em runtime pelo preflight (probe 29) e vem no
plano. A string "ST" nunca o substitui: o parametro e `Nullable<Guid>`, e passar
texto seria inventar API.

NAO chama `replace`. A declaracao e a implementacao que o MasterTool gerar sao
apenas LIDAS e preservadas — e sao elas o resultado que W1.2 existe para medir:
o texto padrao de um PROGRAM recem-criado nao e observavel antes da criacao.

NAO faz, por construcao: `create_pou`, `create_gvl`, `create_folder`,
`create_dut`, `save`, `replace`, `remove`, `rename`, `build`, `import_xml`.
Depois de `create_program`, uma divergencia invalida a copia INTEIRA: registra e
para, nunca tenta desfazer.

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

SCRIPT_NAME = "30_create_program_w1_2.py"
SCHEMA_VERSION = "1.0"

EXPECTED_PHASE = "W1_2_CREATE_PROGRAM"
EXPECTED_OPERATION_ID = "w1-2-create-program"
EXPECTED_PROGRAM_NAME = "PRG_AI_TESTE"
EXPECTED_OPERATIONS = ("create_program", "save_as")

CALL_SITE_CREATE_PROGRAM = "probes/30_create_program_w1_2.py::create_program_guarded"
CALL_SITE_SAVE_AS = "probes/30_create_program_w1_2.py::save_as_guarded"

STATUS_PRECONDITION_FAILED = "precondition_failed"
STATUS_CREATE_PROGRAM_FAILED = "create_program_failed"
STATUS_CREATED_IN_MEMORY = "created_in_memory"
STATUS_VERIFICATION_FAILED = "verification_failed"
STATUS_SAVE_AS_FAILED = "save_as_failed"
STATUS_SAVED_AS = "saved_as"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_PRECONDITION_FAILED, STATUS_CREATE_PROGRAM_FAILED,
    STATUS_CREATED_IN_MEMORY, STATUS_VERIFICATION_FAILED,
    STATUS_SAVE_AS_FAILED, STATUS_SAVED_AS, STATUS_FATAL,
)

EXIT_BY_STATUS = {
    STATUS_SAVED_AS: 0,
    STATUS_PRECONDITION_FAILED: 2,
    STATUS_CREATE_PROGRAM_FAILED: 3,
    STATUS_CREATED_IN_MEMORY: 3,
    STATUS_VERIFICATION_FAILED: 3,
    STATUS_SAVE_AS_FAILED: 4,
    STATUS_FATAL: 1,
}

STATUSES_REQUIRING_DISCARD = (
    STATUS_CREATE_PROGRAM_FAILED, STATUS_CREATED_IN_MEMORY,
    STATUS_VERIFICATION_FAILED, STATUS_SAVE_AS_FAILED,
)

VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp")

ARTIFACT_NAMES = ("manifest.json", "journal.jsonl", "before-tree.json",
                  "after-create-tree.json", "created-program.json",
                  "completion.json", "report.md")

PLAN_KEYS_REQUIRED = ("schema_version", "operation_id", "phase",
                      "input_project", "output_project", "container",
                      "operations", "program_name", "mastertool", "run_id",
                      "artifacts_dir", "st_language_guid")
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


def looks_like_guid(value):
    """Forma de GUID, sem impor chaves. Nao valida semantica: o GUID vem MEDIDO
    do preflight, e aqui so se confere que nao e lixo nem a string 'ST'."""
    if not is_text(value):
        return False
    limpo = value.strip("{}")
    if len(limpo) != 36:
        return False
    for indice, char in enumerate(limpo):
        if indice in (8, 13, 18, 23):
            if char != "-":
                return False
        elif char.lower() not in "0123456789abcdef":
            return False
    return True


def to_clr_guid(text):
    """(System.Guid, erro). Nunca levanta.

    ACHADO da run-005: `create_program` recusa texto com
    `TypeError: expected Nullable[Guid], got str`. O IronPython nao converte
    string para Guid sozinho, e o plano so consegue transportar texto -- JSON
    nao tem tipo Guid. A conversao acontece AQUI, na fase de precondicao, e
    nunca entre a guarda e a chamada: `create_program_guarded` recebe o objeto
    ja tipado.

    `System.Guid` e tipo do .NET base, nao API do MasterTool: converter nao e
    inventar superficie.
    """
    try:
        from System import Guid
    except Exception as exc:                                   # noqa: BLE001
        return None, "System.Guid indisponivel: %r" % (exc,)
    try:
        return Guid(text), None
    except Exception as exc:                                   # noqa: BLE001
        return None, "texto nao converte para Guid: %r (%r)" % (text, exc)


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
    if plan.get("program_name") != EXPECTED_PROGRAM_NAME:
        problems.append("program_name inesperado: %r (esperado %r)"
                        % (plan.get("program_name"), EXPECTED_PROGRAM_NAME))

    guid = plan.get("st_language_guid")
    if not looks_like_guid(guid):
        problems.append(
            "st_language_guid ausente ou sem forma de GUID: %r. Ele vem MEDIDO "
            "pelo preflight; a string 'ST' nao o substitui." % (guid,))

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
                if key not in ("kind", "name", "path", "language"):
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


def read_canonical_texts(program_object):
    """Declaracao e implementacao que o PROPRIO MasterTool gerou.

    E o resultado central de W1.2: o texto padrao de um PROGRAM recem-criado nao
    existe antes desta chamada. Somente leitura — `replace` nao esta neste
    arquivo.
    """
    result = {"declaration": None, "declaration_sha256": None,
              "declaration_linecount": None,
              "implementation": None, "implementation_sha256": None,
              "implementation_linecount": None, "gap": None, "error": None}
    try:
        if not hasattr(program_object, "textual_declaration"):
            result["gap"] = "objeto nao expoe textual_declaration"
        else:
            document = program_object.textual_declaration
            if document is None:
                result["gap"] = "textual_declaration devolveu None"
            elif hasattr(document, "text"):
                text = document.text
                if text is not None:
                    result["declaration"] = str(text)
                    result["declaration_sha256"] = sha256_of_text(result["declaration"])
                    result["declaration_linecount"] = len(result["declaration"].split("\n"))
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = "declaration: %r" % (exc,)
    try:
        if hasattr(program_object, "textual_implementation"):
            document = program_object.textual_implementation
            if document is not None and hasattr(document, "text"):
                text = document.text
                if text is not None:
                    result["implementation"] = str(text)
                    result["implementation_sha256"] = sha256_of_text(result["implementation"])
                    result["implementation_linecount"] = len(
                        result["implementation"].split("\n"))
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = "implementation: %r" % (exc,)
    return result


# --- as DUAS chamadas mutaveis ----------------------------------------------

def create_program_guarded(iec_container, st_language_guid, safety):
    """A unica criacao deste arquivo.

    `st_language_guid` chega como System.Guid JA CONVERTIDO (ver to_clr_guid):
    nada e calculado depois da guarda. Entre a guarda e a chamada nao ha ramo,
    laco, wrapper nem log.
    """
    safety.assert_controlled_write_allowed("create_program")
    created_program = iec_container.create_program("PRG_AI_TESTE", st_language_guid)
    return created_program


def save_as_guarded(project, output_project_path, safety):
    """A unica persistencia deste arquivo. Sem senha, sem fallback, sem retry."""
    safety.assert_controlled_write_allowed("save_as")
    project.save_as(output_project_path)
    return True


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


def verify_created_object(created_program, before, after, expected_type_guid):
    """Confere o objeto criado e o delta. Nunca corrige nada."""
    report = {"return_not_null": created_program is not None,
              "name_matches": None, "type_matches": None,
              "looks_like_program": None,
              "persistent_added": [], "persistent_removed": [],
              "transient_added": [], "identity": None, "problems": []}

    if created_program is None:
        report["problems"].append("create_program devolveu None")
    else:
        identity = object_identity(created_program)
        report["identity"] = identity
        report["name_matches"] = (identity.get("name") == EXPECTED_PROGRAM_NAME)
        if not report["name_matches"]:
            report["problems"].append(
                "nome do objeto criado e %r, esperado %r"
                % (identity.get("name"), EXPECTED_PROGRAM_NAME))
        if is_text(expected_type_guid):
            report["type_matches"] = (identity.get("type_guid") == expected_type_guid)
            if not report["type_matches"]:
                report["problems"].append(
                    "type do objeto criado e %r, plano espera %r"
                    % (identity.get("type_guid"), expected_type_guid))
        # Fallback conservador: o type_guid de POU nao distingue PROGRAM de
        # FUNCTION_BLOCK (docs/30). A forma estrutural entra como evidencia
        # auxiliar, nunca como identidade definitiva.
        report["looks_like_program"] = (
            bool(identity.get("has_textual_declaration"))
            and identity.get("is_folder") is not True)
        if not report["looks_like_program"]:
            report["problems"].append(
                "objeto criado nao tem a forma esperada de POU "
                "(has_textual_declaration=%r, is_folder=%r)"
                % (identity.get("has_textual_declaration"),
                   identity.get("is_folder")))

    before_names = [item.get("name") for item in (before.get("persistent") or [])]
    after_names = [item.get("name") for item in (after.get("persistent") or [])]
    before_transient = [item.get("name") for item in (before.get("transient") or [])]
    after_transient = [item.get("name") for item in (after.get("transient") or [])]

    added, removed = multiset_difference(before_names, after_names)
    report["persistent_added"] = added
    report["persistent_removed"] = removed
    transient_added, _ignored = multiset_difference(before_transient, after_transient)
    report["transient_added"] = transient_added

    if added != [EXPECTED_PROGRAM_NAME]:
        report["problems"].append(
            "objetos persistentes novos = %r; esperado exatamente [%r]"
            % (added, EXPECTED_PROGRAM_NAME))
    if removed:
        report["problems"].append("objetos persistentes desapareceram: %r" % (removed,))
    if before.get("error") or after.get("error"):
        report["problems"].append(
            "enumeracao com erro (antes=%r, depois=%r)"
            % (before.get("error"), after.get("error")))

    report["ok"] = not report["problems"]
    return report


def run_w1_2(script_globals, argv, safety, project_access, file_io, probe_cli,
             now=None, guid_converter=None):
    """Executa W1.2. Injecao explicita dos modulos para teste com dubles.

    `guid_converter` existe porque `System.Guid` so existe sob CLR: em CPython
    o teste nao conseguiria exercitar o caminho da mutacao. O default e a
    conversao real, e o parametro nao escolhe operacao nenhuma -- so o tipo do
    argumento.
    """
    if now is None:
        now = file_io.iso_now
    if guid_converter is None:
        guid_converter = to_clr_guid

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
        "st_language_guid": None,
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
        "after_create_tree": None,
        "created_program": None,
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
    st_language_guid = plan["st_language_guid"]
    result["input_project"]["path"] = input_path
    result["input_project"]["sha256_expected"] = plan["input_project"]["sha256"]
    result["output_project"]["path"] = output_path
    result["artifacts_dir"] = artifacts_dir
    result["st_language_guid"] = st_language_guid

    journal.path = os.path.join(artifacts_dir, "journal.jsonl")
    journal.record({"event": "plan_accepted", "plan_sha256": plan_hash,
                    "phase_expected": EXPECTED_PHASE,
                    "st_language_guid": st_language_guid})

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

    result["gap_notes"].append(
        "estado offline nao verificado: nenhuma propriedade read-only "
        "comprovada expoe isso")

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

    existing_names = [item.get("name") for item in before.get("persistent") or []]
    existing_names.extend([item.get("name") for item in before.get("transient") or []])
    if EXPECTED_PROGRAM_NAME in existing_names:
        result["problems"].append("nome %r ja existe no container"
                                  % (EXPECTED_PROGRAM_NAME,))
        journal.record({"event": "precondition_failed", "reason": "name_exists"})
        return finish(STATUS_PRECONDITION_FAILED)

    # Conversao do GUID ANTES da guarda: o plano so transporta texto, e a API
    # exige Nullable[Guid]. Falhar aqui e precondicao, nao mutacao.
    clr_guid, guid_error = guid_converter(st_language_guid)
    result["st_language_guid_converted"] = (clr_guid is not None)
    if clr_guid is None:
        result["problems"].append(
            "GUID de ST nao pode ser convertido para System.Guid: %s" % guid_error)
        journal.record({"event": "precondition_failed", "reason": "guid_conversion"})
        return finish(STATUS_PRECONDITION_FAILED)

    journal.record({"event": "preconditions_passed",
                    "children_before": before.get("count"),
                    "st_guid_converted": True})

    # --- mutacao 1: create_program -------------------------------------------
    result["operations_requested"].append("create_program")
    journal.record({"event": "mutation_attempt", "operation": "create_program",
                    "phase": phase_observed, "call_site": CALL_SITE_CREATE_PROGRAM,
                    "state_before": {"children": before.get("count")}})
    try:
        created_program = create_program_guarded(iec_container, clr_guid, safety)
    except safety.SafetyError as exc:
        result["problems"].append("autorizacao de create_program recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied", "operation": "create_program",
                        "call_site": CALL_SITE_CREATE_PROGRAM, "error": repr(exc)})
        return finish(STATUS_PRECONDITION_FAILED)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("create_program levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed", "operation": "create_program",
                        "call_site": CALL_SITE_CREATE_PROGRAM, "error": repr(exc)})
        return finish(STATUS_CREATE_PROGRAM_FAILED)

    result["operations_authorized"].append("create_program")
    result["operations_executed"].append("create_program")

    after = enumerate_children(iec_container)
    result["after_create_tree"] = after
    journal.record({"event": "mutation_done", "operation": "create_program",
                    "call_site": CALL_SITE_CREATE_PROGRAM,
                    "state_after": {"children": after.get("count")}})

    verification = verify_created_object(
        created_program, before, after, container_spec.get("expected_program_type_guid"))
    result["verification"] = verification
    result["created_program"] = read_canonical_texts(created_program)
    if result["created_program"].get("gap"):
        result["gap_notes"].append(
            "texto canonico: %s" % result["created_program"]["gap"])

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
        return finish(STATUS_CREATED_IN_MEMORY)
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
                        in ((), ("create_program",), EXPECTED_OPERATIONS))
    created = result.get("created_program") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "phase": result.get("phase_observed"),
        "plan_sha256": result.get("plan_sha256"),
        "st_language_guid": result.get("st_language_guid"),
        "input_project_sha256_before": result.get("input_project", {}).get("sha256_observed"),
        "operations_requested": result.get("operations_requested"),
        "operations_authorized": result.get("operations_authorized"),
        "operations_executed": result.get("operations_executed"),
        "output_project_path": result.get("output_project", {}).get("path"),
        "output_project_exists": result.get("output_project", {}).get("exists_after"),
        "requires_copy_discard": result.get("requires_copy_discard"),
        "created_declaration_sha256": created.get("declaration_sha256"),
        "created_implementation_sha256": created.get("implementation_sha256"),
        "errors": result.get("problems"),
        "gap_notes": result.get("gap_notes"),
        "no_other_mutator_requested": no_other_mutator,
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    created = result.get("created_program") or {}
    lines = [
        "# Probe 30 — W1.2: criar PROGRAM ST e salvar por save_as",
        "",
        "- status: **%s**" % result.get("status"),
        "- exit_code logico: **%s**" % result.get("exit_code"),
        "- fase observada: `%s`" % result.get("phase_observed"),
        "- GUID ST usado: `%s`" % result.get("st_language_guid"),
        "- copia precisa ser descartada: **%s**" % result.get("requires_copy_discard"),
        "",
        "## Operacoes",
        "",
        "- solicitadas: `%s`" % (result.get("operations_requested"),),
        "- executadas: `%s`" % (result.get("operations_executed"),),
        "",
        "## Texto canonico do PROGRAM recem-criado",
        "",
        "- sha256 declaracao: `%s`" % created.get("declaration_sha256"),
        "- linhas: `%s`" % created.get("declaration_linecount"),
        "",
        "```text",
        created.get("declaration") if created.get("declaration") is not None
        else "<sem declaracao>",
        "```",
        "",
        "- sha256 implementacao: `%s`" % created.get("implementation_sha256"),
        "",
        "```text",
        created.get("implementation") if created.get("implementation") is not None
        else "<sem implementacao>",
        "```",
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
    file_io.write_json(os.path.join(artifacts_dir, "after-create-tree.json"),
                       result.get("after_create_tree") or {})
    written.append("after-create-tree.json")
    file_io.write_json(os.path.join(artifacts_dir, "created-program.json"),
                       result.get("created_program") or {})
    written.append("created-program.json")
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
    print("[INFO] probes/%s — W1.2 (escrita controlada)" % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access, safety

    try:
        result = run_w1_2(script_globals, list(sys.argv or []), safety,
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

# -*- coding: utf-8 -*-
r"""27_create_gvl_w1_1.py — marco W1.1: criar UMA GVL vazia e persistir por
`save_as` em arquivo NOVO.

Contrato: `docs/28-contrato-escrita-controlada-mastertool-x.md`.
Plano:    `docs/29-plano-w1-primeira-mutacao-controlada.md`.

Este e o PRIMEIRO probe deste repositorio que invoca API mutavel do
MasterTool. Duas invocacoes, e so duas:

    assert_controlled_write_allowed("create_gvl")
    container.create_gvl("GVL_AI_TESTE")

    assert_controlled_write_allowed("save_as")
    project.save_as(<caminho novo>)

Cada guarda fica na linha IMEDIATAMENTE anterior a sua chamada. Validar a
fase uma vez no inicio deixaria todo o corpo implicitamente autorizado; a
distancia entre a verificacao e a chamada e onde uma operacao a mais passa
despercebida numa revisao.

O nome do mutador esta escrito, literal, no codigo. Nao ha `getattr`, tabela
de despacho, lambda, alias, nem operacao escolhida a partir do plano. O plano
fornece DADOS (caminhos, hashes, nomes esperados); ele nunca escolhe o que
sera chamado.

NAO faz, por construcao — nenhuma destas chamadas existe neste arquivo:
`save`, `replace`, `remove`, `rename`, `move`, `build`, `import_xml`,
`create_pou`, `create_program`, `create_folder`, `create_dut`, nem qualquer
forma de rollback ou retry. Depois de `create_gvl`, uma divergencia invalida a
copia INTEIRA: este probe registra e para, nunca tenta desfazer.

Compatibilidade: IronPython 2.7.12 — sem f-string, sem pathlib, sem
dataclass, sem anotacao de tipo, sem biblioteca externa.
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

SCRIPT_NAME = "27_create_gvl_w1_1.py"
SCHEMA_VERSION = "1.0"

# --- constantes literais do marco -------------------------------------------
# Nao vem do plano: o plano DECLARA o que espera e e conferido contra estas
# constantes. Se o valor viesse de la, o plano escolheria a operacao.
EXPECTED_PHASE = "W1_1_CREATE_GVL"
EXPECTED_OPERATION_ID = "w1-1-create-gvl"
EXPECTED_GVL_NAME = "GVL_AI_TESTE"
EXPECTED_OPERATIONS = ("create_gvl", "save_as")

# Localizacao logica FIXA das duas chamadas mutaveis, para o journal. Constante
# escrita a mao, nunca derivada por inspecao de pilha: `inspect` seria
# introspeccao dinamica num arquivo cuja regra e nao ter nenhuma.
CALL_SITE_CREATE_GVL = "probes/27_create_gvl_w1_1.py::create_gvl_guarded"
CALL_SITE_SAVE_AS = "probes/27_create_gvl_w1_1.py::save_as_guarded"

# --- estados finais, vocabulario fechado ------------------------------------
STATUS_PRECONDITION_FAILED = "precondition_failed"
STATUS_CREATE_GVL_FAILED = "create_gvl_failed"
STATUS_CREATED_IN_MEMORY = "created_in_memory"
STATUS_VERIFICATION_FAILED = "verification_failed"
STATUS_SAVE_AS_FAILED = "save_as_failed"
STATUS_SAVED_AS = "saved_as"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_PRECONDITION_FAILED, STATUS_CREATE_GVL_FAILED,
    STATUS_CREATED_IN_MEMORY, STATUS_VERIFICATION_FAILED,
    STATUS_SAVE_AS_FAILED, STATUS_SAVED_AS, STATUS_FATAL,
)

# Somente saved_as e sucesso integral. created_in_memory NAO e sucesso: houve
# mutacao e ela nao foi persistida, entao a copia tem de ser descartada.
EXIT_BY_STATUS = {
    STATUS_SAVED_AS: 0,
    STATUS_PRECONDITION_FAILED: 2,
    STATUS_CREATE_GVL_FAILED: 3,
    STATUS_CREATED_IN_MEMORY: 3,
    STATUS_VERIFICATION_FAILED: 3,
    STATUS_SAVE_AS_FAILED: 4,
    STATUS_FATAL: 1,
}

# Estados em que a copia descartavel ficou invalida e precisa ser descartada
# integralmente — nao existe rollback transacional (docs/28 secao 10).
STATUSES_REQUIRING_DISCARD = (
    STATUS_CREATE_GVL_FAILED, STATUS_CREATED_IN_MEMORY,
    STATUS_VERIFICATION_FAILED, STATUS_SAVE_AS_FAILED,
)

# Campos voláteis, excluidos de qualquer comparacao de determinismo.
VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp",
                   "elapsed_seconds")

ARTIFACT_NAMES = ("manifest.json", "journal.jsonl", "before-tree.json",
                  "after-create-tree.json", "created-gvl.json",
                  "completion.json", "report.md")

# Chaves aceitas no plano. Chave desconhecida falha FECHADO: um campo que
# ninguem le e um campo que alguem achou que estava sendo respeitado.
PLAN_KEYS_REQUIRED = ("schema_version", "operation_id", "phase",
                      "input_project", "output_project", "container",
                      "operations", "gvl_name", "mastertool", "run_id",
                      "artifacts_dir")
PLAN_KEYS_OPTIONAL = ("notes",)

try:
    _STRING_TYPES = (basestring,)  # noqa: F821  (Python 2 / IronPython 2.7)
except NameError:
    _STRING_TYPES = (str,)


class PlanError(Exception):
    """Plano recusado. Sempre antes de tocar o projeto."""


# --- utilitarios sem efeito colateral ---------------------------------------

def is_text(value):
    return isinstance(value, _STRING_TYPES) and value != ""


def sha256_of_file(path):
    """(digest, erro). Nunca levanta."""
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


# --- journal append-only ----------------------------------------------------

class Journal(object):
    """Append-only. Cada entrada e escrita ANTES do efeito que descreve, para
    que a operacao que travar apareca no registro — um journal escrito depois
    nao registra justamente a que interessa."""

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


# --- validacao do plano -----------------------------------------------------

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
    """Devolve lista de problemas. Lista vazia = plano aceito.

    Tudo e conferido contra CONSTANTE do modulo, nunca contra o proprio plano:
    um plano que declarasse a sua propria fase autorizaria a si mesmo.
    """
    problems = []

    unknown = []
    for key in plan:
        if key not in PLAN_KEYS_REQUIRED and key not in PLAN_KEYS_OPTIONAL:
            unknown.append(key)
    if unknown:
        unknown.sort()
        problems.append("plano tem campo(s) desconhecido(s): %s. Campo que "
                        "ninguem le e campo que alguem achou que estava sendo "
                        "respeitado." % ", ".join(unknown))
    for key in PLAN_KEYS_REQUIRED:
        if key not in plan:
            problems.append("plano sem campo obrigatorio: %s" % key)
    if problems:
        return problems

    if plan.get("schema_version") != SCHEMA_VERSION:
        problems.append("schema_version inesperado: %r (esperado %r)"
                        % (plan.get("schema_version"), SCHEMA_VERSION))
    if plan.get("phase") != EXPECTED_PHASE:
        problems.append("phase inesperada: %r (esperado %r)"
                        % (plan.get("phase"), EXPECTED_PHASE))
    if plan.get("operation_id") != EXPECTED_OPERATION_ID:
        problems.append("operation_id inesperado: %r (esperado %r)"
                        % (plan.get("operation_id"), EXPECTED_OPERATION_ID))
    if plan.get("gvl_name") != EXPECTED_GVL_NAME:
        problems.append("gvl_name inesperado: %r (esperado %r)"
                        % (plan.get("gvl_name"), EXPECTED_GVL_NAME))

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
        problems.append("input_project.path deve ser absoluto: %r" % (input_path,))
    elif " " in input_path:
        problems.append("input_project.path contem espaco: %r" % (input_path,))
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
            problems.append("output_project.path deve ser absoluto: %r" % (output_path,))
        if " " in output_path:
            problems.append("output_project.path contem espaco: %r" % (output_path,))
        if is_text(input_path):
            if os.path.normcase(os.path.abspath(output_path)) == \
                    os.path.normcase(os.path.abspath(input_path)):
                problems.append("output_project.path e igual a input_project.path")
        if os.path.exists(output_path):
            problems.append("output_project.path ja existe: %r. save_as nunca "
                            "sobrescreve." % (output_path,))
        if repo_root and path_is_inside(output_path, repo_root):
            problems.append("output_project.path aponta para dentro do repositorio")

    artifacts_dir = plan.get("artifacts_dir")
    if not is_text(artifacts_dir):
        problems.append("artifacts_dir obrigatorio")
    else:
        if not os.path.isabs(artifacts_dir):
            problems.append("artifacts_dir deve ser absoluto: %r" % (artifacts_dir,))
        if " " in artifacts_dir:
            problems.append("artifacts_dir contem espaco: %r" % (artifacts_dir,))
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


# --- leitura read-only do projeto -------------------------------------------

def object_identity(obj):
    """Identidade de um objeto da arvore.

    Cada membro e acessado pelo nome LITERAL, num bloco proprio. Um laco sobre
    uma lista de nomes com acesso calculado seria mais curto e seria
    exatamente o acesso dinamico que este arquivo nao pode ter.
    """
    identity = {"name": None, "type_guid": None, "object_guid": None,
                "is_folder": None, "is_transient": None, "errors": []}
    try:
        identity["name"] = str(obj.get_name(False))
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("get_name: %r" % (exc,))
    # `type`, nao `type_guid`: o segundo e o nome do CAMPO na saida do scanner
    # aprovado, nao o nome do membro do IScriptObject. Aqui o valor e so
    # diagnostico, mas ler o membro errado gravaria None em todo artefato --
    # e no probe 28 o mesmo engano reprovou um preflight real.
    try:
        if hasattr(obj, "type"):
            identity["type_guid"] = str(obj.type)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("type: %r" % (exc,))
    try:
        if hasattr(obj, "guid"):
            identity["object_guid"] = str(obj.guid)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("guid: %r" % (exc,))
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
    return identity


def enumerate_children(container):
    """Snapshot dos filhos diretos, separando persistente de transiente."""
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


def read_canonical_declaration(gvl_object):
    """Le a declaracao que o PROPRIO MasterTool gerou para a GVL vazia.

    Evidencia para W1.3: o texto do IDE e a forma canonica, e e o que decide se
    o documento carrega `VAR_GLOBAL ... END_VAR` ou apenas o corpo interno.
    Somente leitura — `replace` nao e chamado neste arquivo.
    """
    result = {"has_textual_declaration": None, "text": None, "length": None,
              "linecount": None, "sha256": None, "gap": None, "error": None}
    try:
        if hasattr(gvl_object, "has_textual_declaration"):
            result["has_textual_declaration"] = bool(gvl_object.has_textual_declaration)
        if not hasattr(gvl_object, "textual_declaration"):
            result["gap"] = ("objeto nao expoe textual_declaration; API nao "
                             "catalogada nao e invocada")
            return result
        document = gvl_object.textual_declaration
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
            if hasattr(document, "length"):
                result["length"] = int(document.length)
        except Exception as exc:                               # noqa: BLE001
            result["error"] = "length: %r" % (exc,)
        try:
            if hasattr(document, "linecount"):
                result["linecount"] = int(document.linecount)
        except Exception as exc:                               # noqa: BLE001
            result["error"] = "linecount: %r" % (exc,)
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = repr(exc)
    return result


# --- as DUAS chamadas mutaveis ----------------------------------------------

def create_gvl_guarded(iec_container, safety):
    """A unica criacao deste arquivo.

    A guarda esta na linha imediatamente anterior a chamada. Entre as duas nao
    ha ramo, laco, wrapper, log ou acesso calculado — so o comentario acima.
    """
    safety.assert_controlled_write_allowed("create_gvl")
    created_gvl = iec_container.create_gvl("GVL_AI_TESTE")
    return created_gvl


def save_as_guarded(project, output_project_path, safety):
    """A unica persistencia deste arquivo.

    `output_project_path` chega inteiramente validado: nada e calculado depois
    da guarda. Sobrecarga com senha nao e usada, e nao ha fallback nem retry —
    se levantar, levantou.
    """
    safety.assert_controlled_write_allowed("save_as")
    project.save_as(output_project_path)
    return True


# --- verificacao em memoria -------------------------------------------------

def multiset_difference(before_names, after_names):
    """(acrescentados, sumidos), respeitando repeticao de nome."""
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
    removed = []
    for name in before_names:
        if counts.get(name, 0) > 0:
            counts[name] = counts[name] - 1
            removed.append(name)
    return added, removed


def verify_created_object(created_gvl, before, after):
    """Confere o objeto criado e o delta do container. Nunca corrige nada."""
    report = {"return_not_null": created_gvl is not None,
              "name_matches": None, "looks_like_gvl": None,
              "persistent_added": [], "persistent_removed": [],
              "transient_added": [], "identity": None, "problems": []}

    if created_gvl is None:
        report["problems"].append("create_gvl devolveu None")
    else:
        identity = object_identity(created_gvl)
        report["identity"] = identity
        report["name_matches"] = (identity.get("name") == EXPECTED_GVL_NAME)
        if not report["name_matches"]:
            report["problems"].append(
                "nome do objeto criado e %r, esperado %r"
                % (identity.get("name"), EXPECTED_GVL_NAME))
        has_declaration = False
        try:
            if hasattr(created_gvl, "has_textual_declaration"):
                has_declaration = bool(created_gvl.has_textual_declaration)
        except Exception as exc:                               # noqa: BLE001
            report["problems"].append("has_textual_declaration: %r" % (exc,))
        is_folder = identity.get("is_folder")
        report["looks_like_gvl"] = bool(has_declaration) and (is_folder is not True)
        if not report["looks_like_gvl"]:
            report["problems"].append(
                "objeto criado nao tem a forma esperada de GVL "
                "(has_textual_declaration=%r, is_folder=%r)"
                % (has_declaration, is_folder))

    before_names = [item.get("name") for item in (before.get("persistent") or [])]
    after_names = [item.get("name") for item in (after.get("persistent") or [])]
    before_transient = [item.get("name") for item in (before.get("transient") or [])]
    after_transient = [item.get("name") for item in (after.get("transient") or [])]

    # Diferenca de multiconjunto por contagem. O metodo de lista equivalente
    # faria o mesmo em menos linhas, mas uma inspecao de AST nao distingue a
    # chamada de lista da chamada homonima de IScriptObject — e a verificacao
    # estatica deste probe precisa poder afirmar, sem ressalva, que NENHUMA
    # chamada com esse nome existe aqui.
    added, removed = multiset_difference(before_names, after_names)
    report["persistent_added"] = added
    report["persistent_removed"] = removed

    transient_added, _ = multiset_difference(before_transient, after_transient)
    report["transient_added"] = transient_added

    if report["persistent_added"] != [EXPECTED_GVL_NAME]:
        report["problems"].append(
            "objetos persistentes novos = %r; esperado exatamente [%r]"
            % (report["persistent_added"], EXPECTED_GVL_NAME))
    if report["persistent_removed"]:
        report["problems"].append(
            "objetos persistentes desapareceram: %r" % (report["persistent_removed"],))
    if before.get("error") or after.get("error"):
        report["problems"].append(
            "enumeracao com erro (antes=%r, depois=%r)"
            % (before.get("error"), after.get("error")))

    report["ok"] = not report["problems"]
    return report


# --- orquestracao -----------------------------------------------------------

def run_w1_1(script_globals, argv, safety, project_access, file_io, probe_cli,
             now=None):
    """Executa W1.1 e devolve o resultado. Injecao explicita dos modulos para
    que o teste use dubles estritos sem tocar em nada real.

    Nenhuma operacao mutavel e escolhida aqui: as duas chamadas vivem em
    `create_gvl_guarded` e `save_as_guarded`, cada uma com o nome literal.
    """
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
        "after_create_tree": None,
        "created_gvl": None,
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

    # --- plano ---------------------------------------------------------------
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

    # --- precondicoes --------------------------------------------------------
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
            "instalacao inesperada: file_version observada %r, plano espera %r"
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
        result["problems"].append(
            "sha256 do projeto aberto diverge do plano (observado %r)"
            % (observed_hash,))

    exists_before = os.path.exists(output_path)
    result["output_project"]["exists_before"] = exists_before
    if exists_before:
        result["problems"].append("arquivo de saida ja existe: %r" % (output_path,))

    # Offline: nenhuma propriedade read-only comprovada expoe isso hoje
    # (docs/27 secao 9). Declarar a lacuna e mais honesto do que inventar
    # verificacao — e mais seguro do que presumir offline.
    result["gap_notes"].append(
        "estado offline nao verificado: nenhuma propriedade read-only "
        "comprovada expoe isso; o wrapper e o operador respondem por isso")

    node_indexes = probe_cli.parse_node_id(
        plan["container"]["node_path"], result["problems"], label="container.node_path")

    if result["problems"]:
        journal.record({"event": "precondition_failed",
                        "problem_count": len(result["problems"])})
        return finish(STATUS_PRECONDITION_FAILED)

    trace = []
    iec_container = probe_cli.descend(project, node_indexes, trace)
    result["container_trace"] = trace
    if iec_container is None:
        result["problems"].append(
            "container IEC nao alcancado por node_path (zero resultados)")
        journal.record({"event": "precondition_failed", "reason": "container_absent"})
        return finish(STATUS_PRECONDITION_FAILED)

    before = enumerate_children(iec_container)
    result["before_tree"] = before
    if before.get("error"):
        result["problems"].append("enumeracao inicial falhou: %s" % before["error"])
        journal.record({"event": "precondition_failed", "reason": "enumerate_failed"})
        return finish(STATUS_PRECONDITION_FAILED)

    existing_names = [item.get("name") for item in before.get("persistent") or []]
    existing_names.extend([item.get("name") for item in before.get("transient") or []])
    if EXPECTED_GVL_NAME in existing_names:
        result["problems"].append(
            "nome %r ja existe no container" % (EXPECTED_GVL_NAME,))
        journal.record({"event": "precondition_failed", "reason": "name_exists"})
        return finish(STATUS_PRECONDITION_FAILED)

    journal.record({"event": "preconditions_passed",
                    "children_before": before.get("count")})

    # --- mutacao 1: create_gvl ----------------------------------------------
    result["operations_requested"].append("create_gvl")
    journal.record({"event": "mutation_attempt", "operation": "create_gvl",
                    "phase": phase_observed, "call_site": CALL_SITE_CREATE_GVL,
                    "state_before": {"children": before.get("count")}})
    try:
        created_gvl = create_gvl_guarded(iec_container, safety)
    except safety.SafetyError as exc:
        result["problems"].append("autorizacao de create_gvl recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied", "operation": "create_gvl",
                        "call_site": CALL_SITE_CREATE_GVL, "error": repr(exc)})
        return finish(STATUS_PRECONDITION_FAILED)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("create_gvl levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed", "operation": "create_gvl",
                        "call_site": CALL_SITE_CREATE_GVL, "error": repr(exc)})
        return finish(STATUS_CREATE_GVL_FAILED)

    result["operations_authorized"].append("create_gvl")
    result["operations_executed"].append("create_gvl")

    after = enumerate_children(iec_container)
    result["after_create_tree"] = after
    journal.record({"event": "mutation_done", "operation": "create_gvl",
                    "call_site": CALL_SITE_CREATE_GVL,
                    "state_after": {"children": after.get("count")}})

    verification = verify_created_object(created_gvl, before, after)
    result["verification"] = verification
    result["created_gvl"] = read_canonical_declaration(created_gvl)
    if result["created_gvl"].get("gap"):
        result["gap_notes"].append(
            "declaracao canonica: %s" % result["created_gvl"]["gap"])

    if not verification.get("ok"):
        result["problems"].extend(verification.get("problems") or [])
        journal.record({"event": "verification_failed",
                        "problem_count": len(verification.get("problems") or [])})
        return finish(STATUS_VERIFICATION_FAILED)

    journal.record({"event": "verification_passed",
                    "persistent_added": verification.get("persistent_added")})

    # --- mutacao 2: save_as --------------------------------------------------
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
            "save_as nao levantou, mas o arquivo de saida nao existe: %r"
            % (output_path,))
        return finish(STATUS_SAVE_AS_FAILED)

    return finish(STATUS_SAVED_AS)


# --- artefatos --------------------------------------------------------------

def build_completion(result):
    """Escrito por ULTIMO. E ele que o wrapper le para saber que terminou: o
    fechamento espontaneo do MasterTool nao e sinal de conclusao, e a
    propagacao do exit code do script nunca foi observada (docs/27 secao 9)."""
    no_other_mutator = (tuple(result.get("operations_requested") or ())
                        in ((), ("create_gvl",), EXPECTED_OPERATIONS))
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
        "# Probe 27 — W1.1: criar GVL vazia e salvar por save_as",
        "",
        "- status: **%s**" % result.get("status"),
        "- exit_code logico: **%s**" % result.get("exit_code"),
        "- fase observada: `%s`" % result.get("phase_observed"),
        "- copia precisa ser descartada: **%s**" % result.get("requires_copy_discard"),
        "",
        "## Operacoes",
        "",
        "- solicitadas: `%s`" % (result.get("operations_requested"),),
        "- autorizadas: `%s`" % (result.get("operations_authorized"),),
        "- executadas: `%s`" % (result.get("operations_executed"),),
        "",
        "## Projeto",
        "",
        "- entrada: `%s`" % result.get("input_project", {}).get("path"),
        "- sha256 confere: **%s**" % result.get("input_project", {}).get("matches"),
        "- saida: `%s`" % result.get("output_project", {}).get("path"),
        "- saida existe depois: **%s**" % result.get("output_project", {}).get("exists_after"),
        "",
        "## Declaracao canonica da GVL vazia",
        "",
    ]
    created = result.get("created_gvl") or {}
    lines.append("- sha256 do texto: `%s`" % created.get("sha256"))
    lines.append("- linhas: `%s`" % created.get("linecount"))
    lines.append("- lacuna: `%s`" % created.get("gap"))
    lines.append("")
    lines.append("```text")
    lines.append(created.get("text") if created.get("text") is not None else "<sem texto>")
    lines.append("```")
    lines.append("")
    lines.append("## Problemas")
    lines.append("")
    for problem in result.get("problems") or []:
        lines.append("- %s" % problem)
    if not (result.get("problems") or []):
        lines.append("- nenhum")
    lines.append("")
    lines.append("## Lacunas declaradas")
    lines.append("")
    for note in result.get("gap_notes") or []:
        lines.append("- %s" % note)
    lines.append("")
    return "\n".join(lines)


def write_artifacts(result, file_io):
    """Grava os artefatos. `completion.json` por ultimo, sempre."""
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
    file_io.write_json(os.path.join(artifacts_dir, "created-gvl.json"),
                       result.get("created_gvl") or {})
    written.append("created-gvl.json")
    file_io.write_text(os.path.join(artifacts_dir, "report.md"),
                       build_report_markdown(result))
    written.append("report.md")
    # Por ultimo, sempre: e o sinal de conclusao.
    file_io.write_json(os.path.join(artifacts_dir, "completion.json"),
                       build_completion(result))
    written.append("completion.json")
    return written


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s — W1.1 (escrita controlada)" % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access, safety

    try:
        result = run_w1_1(script_globals, list(sys.argv or []), safety,
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


# Rodape guardado: `main()` so roda quando o ScriptEngine do MasterTool injeta
# o global 'projects' no escopo do arquivo executado por --runscript. Importar
# este modulo em CPython (testes) NAO executa nada — mesmo padrao ja aprovado
# em probes/16, e o que permite que este arquivo seja testavel.
if "projects" in globals():
    sys.exit(main())

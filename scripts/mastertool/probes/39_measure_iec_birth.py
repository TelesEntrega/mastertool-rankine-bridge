# -*- coding: utf-8 -*-
r"""39_measure_iec_birth.py -- marco W1.5: MEDIR o texto de nascimento de
`FUNCTION_BLOCK` e `FUNCTION`, numa copia descartavel, sem persistir nada.

Contrato: `docs/35`. Duas invocacoes mutaveis, e so duas, cada uma com a
guarda na linha IMEDIATAMENTE anterior:

    assert_controlled_write_allowed("create_function_block")
    iec_container.create_function_block("FB_AI_MEASURE_W1_5", language_guid)

    assert_controlled_write_allowed("create_function")
    iec_container.create_function("F_AI_MEASURE_W1_5", return_type, language_guid)

Este probe NAO CHAMA `save`/`save_as`/`save_archive`/`build`. A copia inteira
fica em memoria, nunca e persistida, e o descarte e feito fechando o
MasterTool SEM salvar (a responsabilidade e do host `.ps1` e de quem opera a
janela) -- e por isso que "medir" aqui nao exige `save_as`: o texto de
nascimento e lido do objeto recem-criado, ainda em memoria, e a copia inteira
e jogada fora depois. Diferente de W1.2 (`probes/30`), que precisava
persistir para provar reabertura, W1.5 so precisa LER uma vez.

Por que UMA sessao mede as DUAS familias (FUNCTION_BLOCK e FUNCTION), e nao
uma por sessao: as duas API vivem no MESMO container
(`IScriptIecLanguageObjectContainer4`, docs/27 secao 7, junto de
`create_program`), a mesma copia descartavel serve para as duas sem custo
extra de abrir o MasterTool duas vezes, e o contrato (`docs/35` secao 3) so
exige ordem entre familias -- nunca sessoes separadas -- e so torna FB/FUNCTION
adjacentes na ordem de dependencia (DUT -> FB -> FUNCTION). Cada `create_*`
continua tendo a SUA PROPRIA guarda adjacente, e uma falha em qualquer uma
invalida a copia inteira igual (docs/35 secao 7): nao ha diferenca de risco
entre "duas chamadas na mesma sessao" e "duas sessoes", porque a unidade de
descarte ja e sempre o projeto inteiro, nunca o objeto isolado.

`DUT` (`STRUCT` e `ENUM`) NAO ENTRA neste probe. `docs/35` secao 1 registra
que os valores do enum `DutType` nao estao catalogados em `docs/27` nem em
`api/mastertool-api-observations.md`. Descobri-los exigiria reflexao sobre o
assembly (`GetType().GetMethod("create_dut")` e `Enum.GetNames` sobre o
parametro), e reflexao esta PROIBIDA para este slice. Chamar `create_dut` sem
o tipo certo seria inventar o subtipo (STRUCT? ENUM? o primeiro da lista?) --
exatamente o que este probe existe para NAO fazer. `create_dut` fica de fora
por construcao; a lacuna fica registrada em `gap_notes` e a medicao de DUT
proposta como um probe FUTURO e dedicado, com reflexao autorizada em slice
proprio (ver rodape deste arquivo e o relatorio da execucao).

NAO faz, por construcao: `create_pou`, `create_gvl`, `create_program`,
`create_dut`, `create_folder`, `create_interface`, `save`, `save_as`,
`save_archive`, `replace`, `remove`, `rename`, `build`. Depois de qualquer
`create_*` bem sucedido, a copia INTEIRA fica invalidada para reuso: registra
e para, nunca tenta desfazer.

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

SCRIPT_NAME = "39_measure_iec_birth.py"
SCHEMA_VERSION = "1.0"

EXPECTED_PHASE = "W1_5_MEASURE_IEC_BIRTH"
EXPECTED_OPERATION_ID = "w1-5-measure-iec-birth"
EXPECTED_FUNCTION_BLOCK_NAME = "FB_AI_MEASURE_W1_5"
EXPECTED_FUNCTION_NAME = "F_AI_MEASURE_W1_5"
EXPECTED_OPERATIONS = ("create_function_block", "create_function")

CALL_SITE_CREATE_FUNCTION_BLOCK = \
    "probes/39_measure_iec_birth.py::create_function_block_guarded"
CALL_SITE_CREATE_FUNCTION = \
    "probes/39_measure_iec_birth.py::create_function_guarded"

# Textos JA MEDIDOS (docs/31, docs/35 secao 2) -- entram aqui apenas como
# CONTROLE: se a medicao de GVL/PROGRAM nesta sessao divergir dos hashes
# abaixo, o instrumento (ou o ambiente) esta errado, nunca o contrato. Este
# probe NAO le GVL nem PROGRAM -- os hashes servem so de referencia estatica
# comparavel por quem revisar o relatorio.
KNOWN_GVL_BIRTH_SHA256 = \
    "fd27fd816bdf9d2116403f691bcb84694119b3553b1067619bb9b96dd310affb"
KNOWN_PROGRAM_DECLARATION_BIRTH_SHA256 = \
    "6a2401fa5915a354eae0895d290e4bb6d3483c4d3ca4e05cb7e5b230f4435841"
KNOWN_PROGRAM_IMPLEMENTATION_BIRTH_SHA256 = \
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

STATUS_PRECONDITION_FAILED = "precondition_failed"
STATUS_GATE_CLOSED = "gate_closed"
STATUS_CREATE_FAILED = "create_failed"
STATUS_VERIFICATION_FAILED = "verification_failed"
STATUS_PARTIAL_MEASURED = "partial_measured"
STATUS_MEASURED = "measured"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_PRECONDITION_FAILED, STATUS_GATE_CLOSED, STATUS_CREATE_FAILED,
    STATUS_VERIFICATION_FAILED, STATUS_PARTIAL_MEASURED, STATUS_MEASURED,
    STATUS_FATAL,
)

EXIT_BY_STATUS = {
    STATUS_MEASURED: 0,
    STATUS_PRECONDITION_FAILED: 2,
    STATUS_CREATE_FAILED: 3,
    STATUS_VERIFICATION_FAILED: 4,
    STATUS_PARTIAL_MEASURED: 6,
    STATUS_GATE_CLOSED: 5,
    STATUS_FATAL: 1,
}

STATUSES_REQUIRING_DISCARD = (
    STATUS_CREATE_FAILED, STATUS_VERIFICATION_FAILED, STATUS_PARTIAL_MEASURED,
    STATUS_MEASURED,
)

VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp")

ARTIFACT_NAMES = ("manifest.json", "journal.jsonl", "before-tree.json",
                  "after-tree.json", "measured-function-block.json",
                  "measured-function.json", "completion.json", "report.md")

PLAN_KEYS_REQUIRED = ("schema_version", "operation_id", "phase",
                      "input_project", "container", "operations",
                      "function_block_name", "function_name",
                      "function_return_type", "language_guid",
                      "mastertool", "run_id", "artifacts_dir")
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
    """Forma de GUID, sem impor chaves. Nao valida semantica: o GUID vem
    MEDIDO (docs/30) e aqui so se confere que nao e lixo nem a string 'ST'."""
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


def looks_like_iec_type_name(value):
    """Nome de tipo elementar/derivado IEC: letras, digitos e underscore,
    comecando por letra ou underscore. Nao valida contra uma lista fechada de
    tipos elementares -- `return_type` aceita tipo derivado tambem -- so
    recusa lixo (espaco, aspas, vazio)."""
    if not is_text(value) or len(value) > 64:
        return False
    primeiro = value[0]
    if not (primeiro.isalpha() or primeiro == "_"):
        return False
    for char in value:
        if not (char.isalnum() or char == "_"):
            return False
    return True


def to_clr_guid(text):
    """(System.Guid, erro). Nunca levanta.

    Mesmo achado de W1.2 (`docs/30`): a API recusa texto com
    `TypeError: expected Nullable[Guid], got str`. A conversao acontece na
    fase de precondicao, nunca entre a guarda e a chamada.

    `System.Guid` e tipo do .NET base, nao API do MasterTool: converter nao e
    reflexao nem inventar superficie.
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
    if plan.get("function_block_name") != EXPECTED_FUNCTION_BLOCK_NAME:
        problems.append("function_block_name inesperado: %r (esperado %r)"
                        % (plan.get("function_block_name"), EXPECTED_FUNCTION_BLOCK_NAME))
    if plan.get("function_name") != EXPECTED_FUNCTION_NAME:
        problems.append("function_name inesperado: %r (esperado %r)"
                        % (plan.get("function_name"), EXPECTED_FUNCTION_NAME))

    guid = plan.get("language_guid")
    if not looks_like_guid(guid):
        problems.append(
            "language_guid ausente ou sem forma de GUID: %r. Ele vem MEDIDO "
            "pelo preflight de W1.2 (docs/30); a string 'ST' nao o substitui."
            % (guid,))

    return_type = plan.get("function_return_type")
    if not looks_like_iec_type_name(return_type):
        problems.append(
            "function_return_type ausente ou sem forma de nome de tipo IEC: %r"
            % (return_type,))

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
                if key not in ("kind", "name"):
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


def read_canonical_texts(created_object):
    """Declaracao e implementacao que o PROPRIO MasterTool gerou para o
    objeto recem-criado. E o resultado central deste probe: o texto padrao
    de um FUNCTION_BLOCK/FUNCTION recem-criado nao e observavel antes desta
    chamada. Somente leitura -- `replace` nao esta neste arquivo."""
    result = {"declaration": None, "declaration_sha256": None,
              "declaration_linecount": None,
              "implementation": None, "implementation_sha256": None,
              "implementation_linecount": None, "gap": None, "error": None}
    try:
        if not hasattr(created_object, "textual_declaration"):
            result["gap"] = "objeto nao expoe textual_declaration"
        else:
            document = created_object.textual_declaration
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
        if hasattr(created_object, "textual_implementation"):
            document = created_object.textual_implementation
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


def verify_created_object(created_object, before, after, expected_name):
    """Confere o objeto criado e o delta. Nunca corrige nada."""
    report = {"return_not_null": created_object is not None,
              "name_matches": None, "looks_like_pou": None,
              "persistent_added": [], "persistent_removed": [],
              "transient_added": [], "identity": None, "problems": []}

    if created_object is None:
        report["problems"].append("create_* devolveu None")
    else:
        identity = object_identity(created_object)
        report["identity"] = identity
        report["name_matches"] = (identity.get("name") == expected_name)
        if not report["name_matches"]:
            report["problems"].append(
                "nome do objeto criado e %r, esperado %r"
                % (identity.get("name"), expected_name))
        # O type_guid de POU nao distingue FUNCTION_BLOCK de FUNCTION de
        # PROGRAM entre si (docs/35 secao 4, ja medido para PROGRAM em
        # docs/30). A forma estrutural entra como evidencia auxiliar, nunca
        # como identidade definitiva.
        report["looks_like_pou"] = (
            bool(identity.get("has_textual_declaration"))
            and identity.get("is_folder") is not True)
        if not report["looks_like_pou"]:
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

    if added != [expected_name]:
        report["problems"].append(
            "objetos persistentes novos = %r; esperado exatamente [%r]"
            % (added, expected_name))
    if removed:
        report["problems"].append("objetos persistentes desapareceram: %r" % (removed,))
    if before.get("error") or after.get("error"):
        report["problems"].append(
            "enumeracao com erro (antes=%r, depois=%r)"
            % (before.get("error"), after.get("error")))

    report["ok"] = not report["problems"]
    return report


# --- as DUAS chamadas mutaveis -----------------------------------------------

def create_function_block_guarded(iec_container, name, language_guid, safety):
    """A UNICA chamada de create_function_block deste arquivo. Sem base_type
    nem interfaces: omitidos de proposito, para medir o nascimento MINIMO --
    ambos sao parametros opcionais catalogados (docs/27 secao 7), e passar
    valor para eles decidiria de antemao algo que este probe existe para
    medir, nao para presumir."""
    safety.assert_controlled_write_allowed("create_function_block")
    created = iec_container.create_function_block(name, language_guid)
    return created


def create_function_guarded(iec_container, name, return_type, language_guid, safety):
    """A UNICA chamada de create_function deste arquivo. `return_type` e
    obrigatorio na assinatura catalogada (docs/27 secao 7); vem do plano, e
    validado como nome de tipo, nunca escolhido pelo probe."""
    safety.assert_controlled_write_allowed("create_function")
    created = iec_container.create_function(name, return_type, language_guid)
    return created


def run_w1_5(script_globals, argv, safety, project_access, file_io, probe_cli,
             now=None, guid_converter=None):
    """Executa W1.5. Injecao explicita dos modulos para teste com dubles.

    `guid_converter` existe porque `System.Guid` so existe sob CLR: em
    CPython o teste nao conseguiria exercitar o caminho da mutacao. O default
    e a conversao real, e o parametro nao escolhe operacao nenhuma -- so o
    tipo do argumento.
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
        "language_guid": None,
        "function_return_type": None,
        "input_project": {"path": None, "sha256_expected": None,
                          "sha256_observed": None, "matches": None},
        "operations_requested": [],
        "operations_authorized": [],
        "operations_executed": [],
        "problems": [],
        "gap_notes": [
            "DUT (STRUCT, ENUM) nao medido nesta sessao: os valores do enum "
            "DutType nao estao catalogados (docs/35 secao 1) e este probe "
            "nao usa reflexao. create_dut NUNCA e chamado por este arquivo. "
            "Medicao futura proposta: probe read-only dedicado, com "
            "reflexao explicitamente autorizada em slice proprio, que liste "
            "os membros de DutType via System.Reflection sobre a assinatura "
            "de create_dut -- sem criar nenhum objeto -- antes de qualquer "
            "fase que chame create_dut com um tipo especifico.",
            "controle (nao medido por este probe, apenas citado): sha256 "
            "conhecido de nascimento de GVL=%s, declaracao de PROGRAM=%s, "
            "implementacao de PROGRAM=%s (docs/31, docs/35 secao 2)"
            % (KNOWN_GVL_BIRTH_SHA256, KNOWN_PROGRAM_DECLARATION_BIRTH_SHA256,
               KNOWN_PROGRAM_IMPLEMENTATION_BIRTH_SHA256),
        ],
        "runtime": None,
        "before_tree": None,
        "after_tree": None,
        "measured_function_block": None,
        "measured_function": None,
        "verification_function_block": None,
        "verification_function": None,
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
    artifacts_dir = plan["artifacts_dir"]
    language_guid = plan["language_guid"]
    return_type = plan["function_return_type"]
    fb_name = plan["function_block_name"]
    function_name = plan["function_name"]
    result["input_project"]["path"] = input_path
    result["input_project"]["sha256_expected"] = plan["input_project"]["sha256"]
    result["artifacts_dir"] = artifacts_dir
    result["language_guid"] = language_guid
    result["function_return_type"] = return_type

    journal.path = os.path.join(artifacts_dir, "journal.jsonl")
    journal.record({"event": "plan_accepted", "plan_sha256": plan_hash,
                    "phase_expected": EXPECTED_PHASE,
                    "language_guid": language_guid})

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
    if fb_name in existing_names:
        result["problems"].append("nome %r ja existe no container" % (fb_name,))
        journal.record({"event": "precondition_failed", "reason": "fb_name_exists"})
        return finish(STATUS_PRECONDITION_FAILED)
    if function_name in existing_names:
        result["problems"].append("nome %r ja existe no container" % (function_name,))
        journal.record({"event": "precondition_failed", "reason": "function_name_exists"})
        return finish(STATUS_PRECONDITION_FAILED)

    # Conversao do GUID ANTES de qualquer guarda: o plano so transporta
    # texto, e a API exige Nullable[Guid]. Falhar aqui e precondicao, nunca
    # mutacao. UMA conversao serve para as duas chamadas (mesma linguagem).
    clr_guid, guid_error = guid_converter(language_guid)
    result["language_guid_converted"] = (clr_guid is not None)
    if clr_guid is None:
        result["problems"].append(
            "GUID de linguagem nao pode ser convertido para System.Guid: %s"
            % guid_error)
        journal.record({"event": "precondition_failed", "reason": "guid_conversion"})
        return finish(STATUS_PRECONDITION_FAILED)

    journal.record({"event": "preconditions_passed",
                    "children_before": before.get("count"),
                    "language_guid_converted": True})

    # --- mutacao 1: create_function_block ------------------------------------
    result["operations_requested"].append("create_function_block")
    journal.record({"event": "mutation_attempt", "operation": "create_function_block",
                    "phase": phase_observed,
                    "call_site": CALL_SITE_CREATE_FUNCTION_BLOCK,
                    "state_before": {"children": before.get("count")}})
    try:
        created_fb = create_function_block_guarded(
            iec_container, fb_name, clr_guid, safety)
    except safety.SafetyError as exc:
        result["problems"].append(
            "autorizacao de create_function_block recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied", "operation": "create_function_block",
                        "call_site": CALL_SITE_CREATE_FUNCTION_BLOCK,
                        "error": repr(exc)})
        return finish(STATUS_GATE_CLOSED)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("create_function_block levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed", "operation": "create_function_block",
                        "call_site": CALL_SITE_CREATE_FUNCTION_BLOCK,
                        "error": repr(exc)})
        return finish(STATUS_CREATE_FAILED)

    result["operations_authorized"].append("create_function_block")
    result["operations_executed"].append("create_function_block")

    after_fb = enumerate_children(iec_container)
    journal.record({"event": "mutation_done", "operation": "create_function_block",
                    "call_site": CALL_SITE_CREATE_FUNCTION_BLOCK,
                    "state_after": {"children": after_fb.get("count")}})

    verification_fb = verify_created_object(created_fb, before, after_fb, fb_name)
    result["verification_function_block"] = verification_fb
    result["measured_function_block"] = read_canonical_texts(created_fb)
    if result["measured_function_block"].get("gap"):
        result["gap_notes"].append(
            "texto canonico de FUNCTION_BLOCK: %s"
            % result["measured_function_block"]["gap"])

    if not verification_fb.get("ok"):
        result["problems"].extend(verification_fb.get("problems") or [])
        journal.record({"event": "verification_failed", "operation": "create_function_block",
                        "problem_count": len(verification_fb.get("problems") or [])})
        return finish(STATUS_VERIFICATION_FAILED)

    journal.record({"event": "verification_passed", "operation": "create_function_block",
                    "persistent_added": verification_fb.get("persistent_added")})

    # --- mutacao 2: create_function -------------------------------------------
    result["operations_requested"].append("create_function")
    journal.record({"event": "mutation_attempt", "operation": "create_function",
                    "phase": phase_observed, "call_site": CALL_SITE_CREATE_FUNCTION,
                    "state_before": {"children": after_fb.get("count")}})
    try:
        created_function = create_function_guarded(
            iec_container, function_name, return_type, clr_guid, safety)
    except safety.SafetyError as exc:
        result["problems"].append("autorizacao de create_function recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied", "operation": "create_function",
                        "call_site": CALL_SITE_CREATE_FUNCTION, "error": repr(exc)})
        # FUNCTION_BLOCK ja foi criado em memoria: a copia ja esta invalidada,
        # mesmo com create_function negado. Medicao parcial, nao gate fechado
        # por completo -- a diferenca importa para quem revisa o relatorio.
        return finish(STATUS_PARTIAL_MEASURED)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("create_function levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed", "operation": "create_function",
                        "call_site": CALL_SITE_CREATE_FUNCTION, "error": repr(exc)})
        return finish(STATUS_CREATE_FAILED)

    result["operations_authorized"].append("create_function")
    result["operations_executed"].append("create_function")

    after_function = enumerate_children(iec_container)
    result["after_tree"] = after_function
    journal.record({"event": "mutation_done", "operation": "create_function",
                    "call_site": CALL_SITE_CREATE_FUNCTION,
                    "state_after": {"children": after_function.get("count")}})

    verification_function = verify_created_object(
        created_function, after_fb, after_function, function_name)
    result["verification_function"] = verification_function
    result["measured_function"] = read_canonical_texts(created_function)
    if result["measured_function"].get("gap"):
        result["gap_notes"].append(
            "texto canonico de FUNCTION: %s" % result["measured_function"]["gap"])

    if not verification_function.get("ok"):
        result["problems"].extend(verification_function.get("problems") or [])
        journal.record({"event": "verification_failed", "operation": "create_function",
                        "problem_count": len(verification_function.get("problems") or [])})
        return finish(STATUS_VERIFICATION_FAILED)

    journal.record({"event": "verification_passed", "operation": "create_function",
                    "persistent_added": verification_function.get("persistent_added")})

    return finish(STATUS_MEASURED)


def build_completion(result):
    """Escrito por ULTIMO: e o sinal de conclusao."""
    no_other_mutator = (tuple(result.get("operations_requested") or ())
                        in ((), ("create_function_block",), EXPECTED_OPERATIONS))
    fb = result.get("measured_function_block") or {}
    function = result.get("measured_function") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "phase": result.get("phase_observed"),
        "plan_sha256": result.get("plan_sha256"),
        "language_guid": result.get("language_guid"),
        "function_return_type": result.get("function_return_type"),
        "input_project_sha256_before": result.get("input_project", {}).get("sha256_observed"),
        "operations_requested": result.get("operations_requested"),
        "operations_authorized": result.get("operations_authorized"),
        "operations_executed": result.get("operations_executed"),
        "requires_copy_discard": result.get("requires_copy_discard"),
        "function_block_declaration_sha256": fb.get("declaration_sha256"),
        "function_block_implementation_sha256": fb.get("implementation_sha256"),
        "function_declaration_sha256": function.get("declaration_sha256"),
        "function_implementation_sha256": function.get("implementation_sha256"),
        "dut_measured": False,
        "errors": result.get("problems"),
        "gap_notes": result.get("gap_notes"),
        "no_other_mutator_requested": no_other_mutator,
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    fb = result.get("measured_function_block") or {}
    function = result.get("measured_function") or {}
    lines = [
        "# Probe 39 -- W1.5: medir texto de nascimento de FUNCTION_BLOCK e FUNCTION",
        "",
        "- status: **%s**" % result.get("status"),
        "- exit_code logico: **%s**" % result.get("exit_code"),
        "- fase observada: `%s`" % result.get("phase_observed"),
        "- GUID de linguagem usado: `%s`" % result.get("language_guid"),
        "- copia precisa ser descartada (fechar sem salvar): **%s**"
        % result.get("requires_copy_discard"),
        "",
        "## Operacoes",
        "",
        "- solicitadas: `%s`" % (result.get("operations_requested"),),
        "- executadas: `%s`" % (result.get("operations_executed"),),
        "",
        "## Texto canonico de FUNCTION_BLOCK recem-criado",
        "",
        "- sha256 declaracao: `%s`" % fb.get("declaration_sha256"),
        "- linhas: `%s`" % fb.get("declaration_linecount"),
        "",
        "```text",
        fb.get("declaration") if fb.get("declaration") is not None else "<sem declaracao>",
        "```",
        "",
        "- sha256 implementacao: `%s`" % fb.get("implementation_sha256"),
        "",
        "```text",
        fb.get("implementation") if fb.get("implementation") is not None
        else "<sem implementacao>",
        "```",
        "",
        "## Texto canonico de FUNCTION recem-criada",
        "",
        "- sha256 declaracao: `%s`" % function.get("declaration_sha256"),
        "- linhas: `%s`" % function.get("declaration_linecount"),
        "",
        "```text",
        function.get("declaration") if function.get("declaration") is not None
        else "<sem declaracao>",
        "```",
        "",
        "- sha256 implementacao: `%s`" % function.get("implementation_sha256"),
        "",
        "```text",
        function.get("implementation") if function.get("implementation") is not None
        else "<sem implementacao>",
        "```",
        "",
        "## DUT (STRUCT, ENUM)",
        "",
        "- **NAO MEDIDO nesta sessao.** create_dut nunca foi chamado.",
        "- motivo: DutType nao catalogado (docs/35 secao 1); descobrir os "
        "membros exigiria reflexao, proibida para este slice.",
        "",
        "## Problemas",
        "",
    ]
    for problem in result.get("problems") or []:
        lines.append("- %s" % problem)
    if not (result.get("problems") or []):
        lines.append("- nenhum")
    lines.append("")
    lines.append("## Lacunas registradas")
    lines.append("")
    for gap in result.get("gap_notes") or []:
        lines.append("- %s" % gap)
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
    file_io.write_json(os.path.join(artifacts_dir, "after-tree.json"),
                       result.get("after_tree") or {})
    written.append("after-tree.json")
    file_io.write_json(os.path.join(artifacts_dir, "measured-function-block.json"),
                       result.get("measured_function_block") or {})
    written.append("measured-function-block.json")
    file_io.write_json(os.path.join(artifacts_dir, "measured-function.json"),
                       result.get("measured_function") or {})
    written.append("measured-function.json")
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
    print("[INFO] probes/%s -- W1.5 (escrita controlada, medicao)" % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access, safety

    try:
        result = run_w1_5(script_globals, list(sys.argv or []), safety,
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
    print("[INFO] descartar a copia (fechar SEM salvar): %s"
          % result.get("requires_copy_discard"))
    for problem in result.get("problems") or []:
        print("[PROBLEM] %s" % problem)
    print("=" * 68)
    return result.get("exit_code")


if "projects" in globals():
    sys.exit(main())

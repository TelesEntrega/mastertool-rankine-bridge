# -*- coding: utf-8 -*-
r"""38_author_w1_4.py -- marco W1.4: autoria INTEGRADA sobre copia descartavel
do projeto-base, persistida por um unico `save_as` em arquivo NOVO.

Contrato: `docs/28`. Plano normativo: `docs/32`.

SEIS invocacoes mutaveis, e so seis, cada uma com a guarda na linha
IMEDIATAMENTE anterior:

    assert_controlled_write_allowed("create_gvl")
    iec_container.create_gvl("GVL_AI_TESTE")

    assert_controlled_write_allowed("create_program")
    iec_container.create_program("PRG_AI_TESTE", st_language_guid)

    assert_controlled_write_allowed("replace")
    gvl_declaration_document.replace(GVL_DECLARATION)

    assert_controlled_write_allowed("replace")
    program_declaration_document.replace(PROGRAM_DECLARATION)

    assert_controlled_write_allowed("replace")
    program_implementation_document.replace(PROGRAM_IMPLEMENTATION)

    assert_controlled_write_allowed("save_as")
    project.save_as(<caminho novo>)

`build` NAO esta aqui: ele roda em ABERTURA SEPARADA, sobre o arquivo salvo
(`probes/40`). Compilar na mesma sessao que escreveu provaria, no maximo, que
o texto em memoria compila.

DEPOIS DE CADA MUTACAO EM MEMORIA HA VERIFICACAO INTERMEDIARIA. Foi o que, em
W1.3B, tornou distinguiveis "a primeira falhou" e "a segunda falhou"
(`docs/34` secao 7): sem ela, um texto divergente no fim nao diria qual passo
o produziu.

Os TRES textos sao CONSTANTES DESTE MODULO -- nunca vem do plano. O plano so
transporta identidade (container, nomes, hashes, GUID de linguagem); um plano
que carregasse o texto final autorizaria a si mesmo a escrever qualquer coisa.

O GUID da linguagem NAO viaja como tipo: `create_program` recusa texto com
`TypeError: expected Nullable[Guid], got str` (achado da run-005). A conversao
para `System.Guid` acontece na fase de PRECONDICAO, nunca entre a guarda e a
chamada -- falha de conversao e `precondition_failed`, e nao
`create_program_failed`: uma nem chegou a pedir autorizacao, a outra sim.

SEM ROLLBACK. `create_*` devolve o objeto JA INSERIDO na arvore, sem passo de
confirmacao, e a API nao tem transacao. Por isso qualquer falha depois do
primeiro `create_gvl` invalida a COPIA INTEIRA -- a unidade descartada e a
copia, nunca uma operacao isolada dela. Este arquivo registra e para: nunca
chama `remove`, `rename` nem `save`.

NAO faz, por construcao: `create_pou`, `create_dut`, `create_folder`,
`create_function`, `create_function_block`, `save`, `build`, `rebuild`,
`clean`, `remove`, `rename`, `import_xml`, `insert`, `append` sobre documento
textual, `replace_line`.

Compatibilidade: IronPython 2.7.12.
"""
from __future__ import print_function

import hashlib
import json
import os
import re
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

SCRIPT_NAME = "38_author_w1_4.py"
SCHEMA_VERSION = "1.0"

EXPECTED_PHASE = "W1_4_INTEGRATED_BUILD"
EXPECTED_OPERATION_ID = "w1-4-integrated-build"
EXPECTED_GVL_NAME = "GVL_AI_TESTE"
EXPECTED_PROGRAM_NAME = "PRG_AI_TESTE"
EXPECTED_CONTAINER_NAME = "Application"

# A cadeia INTEIRA declarada no plano, na ordem da secao 3 de `docs/32`. O
# `build` e declarado aqui e executado por `probes/40`, em abertura separada:
# o plano descreve a cadeia, e cada probe executa a parte que lhe cabe.
EXPECTED_PLAN_OPERATIONS = ("create_gvl", "create_program", "replace",
                            "replace", "replace", "save_as", "build")
EXPECTED_REPLACE_TARGETS = ("gvl_textual_declaration",
                            "program_textual_declaration",
                            "program_textual_implementation")

# Medidos e congelados. Constantes de MODULO, conferidas contra o plano,
# nunca substituidas por ele.
EXPECTED_CONTAINER_TYPE_GUID = "639b491f-5557-464c-af91-1471bac9f549"
EXPECTED_GVL_TYPE_GUID = "ffbfa93a-b94d-45fc-a329-229860183b1d"
EXPECTED_PROGRAM_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
EXPECTED_ST_LANGUAGE_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"

# Textos canonicos de W1.4. O prefixo `GVL_AI_TESTE.` e OBRIGATORIO: a GVL
# nasce com `{attribute 'qualified_only'}` (medido em W1.1), que exige
# qualificacao em toda referencia externa. Sem ele o `build` falharia por
# simbolo nao resolvido -- achado sobre conteudo, nao sobre capacidade.
GVL_DECLARATION = (
    "{attribute 'qualified_only'}\n"
    "VAR_GLOBAL\n"
    "    g_xTesteCriacao : BOOL;\n"
    "END_VAR"
)
PROGRAM_DECLARATION = "PROGRAM PRG_AI_TESTE\nVAR\n    xLocal : BOOL;\nEND_VAR\n"
PROGRAM_IMPLEMENTATION = "xLocal := GVL_AI_TESTE.g_xTesteCriacao;\n"

CALL_SITE_CREATE_GVL = "probes/38_author_w1_4.py::create_gvl_guarded"
CALL_SITE_CREATE_PROGRAM = "probes/38_author_w1_4.py::create_program_guarded"
CALL_SITE_REPLACE_GVL_DECLARATION = \
    "probes/38_author_w1_4.py::replace_gvl_declaration_guarded"
CALL_SITE_REPLACE_PROGRAM_DECLARATION = \
    "probes/38_author_w1_4.py::replace_program_declaration_guarded"
CALL_SITE_REPLACE_PROGRAM_IMPLEMENTATION = \
    "probes/38_author_w1_4.py::replace_program_implementation_guarded"
CALL_SITE_SAVE_AS = "probes/38_author_w1_4.py::save_as_guarded"

# --- estados, vocabulario fechado (docs/32 secao 9) --------------------------
STATUS_PRECONDITION_FAILED = "precondition_failed"
STATUS_CREATE_GVL_FAILED = "create_gvl_failed"
STATUS_GVL_VERIFICATION_FAILED = "gvl_verification_failed"
STATUS_CREATE_PROGRAM_FAILED = "create_program_failed"
STATUS_PROGRAM_VERIFICATION_FAILED = "program_verification_failed"
STATUS_REPLACE_GVL_DECLARATION_FAILED = "replace_gvl_declaration_failed"
STATUS_GVL_TEXT_VERIFICATION_FAILED = "gvl_text_verification_failed"
STATUS_REPLACE_PROGRAM_DECLARATION_FAILED = "replace_program_declaration_failed"
STATUS_PROGRAM_DECLARATION_VERIFICATION_FAILED = \
    "program_declaration_verification_failed"
STATUS_REPLACE_PROGRAM_IMPLEMENTATION_FAILED = \
    "replace_program_implementation_failed"
STATUS_PROGRAM_IMPLEMENTATION_VERIFICATION_FAILED = \
    "program_implementation_verification_failed"
STATUS_AUTHORED_IN_MEMORY = "authored_in_memory"
STATUS_SAVE_AS_FAILED = "save_as_failed"
STATUS_SAVED_AS = "saved_as"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_PRECONDITION_FAILED, STATUS_CREATE_GVL_FAILED,
    STATUS_GVL_VERIFICATION_FAILED, STATUS_CREATE_PROGRAM_FAILED,
    STATUS_PROGRAM_VERIFICATION_FAILED, STATUS_REPLACE_GVL_DECLARATION_FAILED,
    STATUS_GVL_TEXT_VERIFICATION_FAILED,
    STATUS_REPLACE_PROGRAM_DECLARATION_FAILED,
    STATUS_PROGRAM_DECLARATION_VERIFICATION_FAILED,
    STATUS_REPLACE_PROGRAM_IMPLEMENTATION_FAILED,
    STATUS_PROGRAM_IMPLEMENTATION_VERIFICATION_FAILED,
    STATUS_AUTHORED_IN_MEMORY, STATUS_SAVE_AS_FAILED, STATUS_SAVED_AS,
    STATUS_FATAL,
)

EXIT_BY_STATUS = {
    STATUS_SAVED_AS: 0,
    STATUS_PRECONDITION_FAILED: 2,
    STATUS_CREATE_GVL_FAILED: 3,
    STATUS_GVL_VERIFICATION_FAILED: 3,
    STATUS_CREATE_PROGRAM_FAILED: 3,
    STATUS_PROGRAM_VERIFICATION_FAILED: 3,
    STATUS_REPLACE_GVL_DECLARATION_FAILED: 3,
    STATUS_GVL_TEXT_VERIFICATION_FAILED: 3,
    STATUS_REPLACE_PROGRAM_DECLARATION_FAILED: 3,
    STATUS_PROGRAM_DECLARATION_VERIFICATION_FAILED: 3,
    STATUS_REPLACE_PROGRAM_IMPLEMENTATION_FAILED: 3,
    STATUS_PROGRAM_IMPLEMENTATION_VERIFICATION_FAILED: 3,
    STATUS_AUTHORED_IN_MEMORY: 3,
    STATUS_SAVE_AS_FAILED: 4,
    STATUS_FATAL: 1,
}

# Qualquer status aqui: sem rollback, sem save, sem retry -- a COPIA INTEIRA e
# descartada. So `precondition_failed` nao exige descarte, porque nenhuma
# mutacao foi tentada.
STATUSES_REQUIRING_DISCARD = (
    STATUS_CREATE_GVL_FAILED, STATUS_GVL_VERIFICATION_FAILED,
    STATUS_CREATE_PROGRAM_FAILED, STATUS_PROGRAM_VERIFICATION_FAILED,
    STATUS_REPLACE_GVL_DECLARATION_FAILED, STATUS_GVL_TEXT_VERIFICATION_FAILED,
    STATUS_REPLACE_PROGRAM_DECLARATION_FAILED,
    STATUS_PROGRAM_DECLARATION_VERIFICATION_FAILED,
    STATUS_REPLACE_PROGRAM_IMPLEMENTATION_FAILED,
    STATUS_PROGRAM_IMPLEMENTATION_VERIFICATION_FAILED,
    STATUS_AUTHORED_IN_MEMORY, STATUS_SAVE_AS_FAILED,
)

# Ordem canonica das seis operacoes EXECUTADAS aqui. Serve ao artefato:
# qualquer prefixo dela e aceitavel (a cadeia parou), qualquer outra sequencia
# significa que algo fora do previsto foi pedido.
EXECUTED_OPERATION_SEQUENCE = (
    "create_gvl", "create_program", "replace_gvl_declaration",
    "replace_program_declaration", "replace_program_implementation", "save_as",
)

VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp")

ARTIFACT_NAMES = ("manifest.json", "journal.jsonl", "before-tree.json",
                  "after-create-tree.json", "authored-objects.json",
                  "completion.json", "report.md")

PLAN_KEYS_REQUIRED = ("schema_version", "operation_id", "phase",
                      "input_project", "output_project", "container",
                      "operations", "gvl_name", "program_name",
                      "st_language_guid", "mastertool", "run_id",
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
    """Mesma regra congelada de `docs/29` e `docs/31`. Via `re.sub`, nunca
    pelo metodo de string homonimo ao da API mutavel: a prova por AST de que
    ha EXATAMENTE tres chamadas com esse nome conta chamadas de atributo, e
    uma normalizacao textual nao pode inflar essa contagem."""
    if text is None:
        return None
    sem_cr = re.sub(r"\r\n|\r", "\n", text)
    linhas = [linha.rstrip() for linha in sem_cr.split("\n")]
    resultado = "\n".join(linhas)
    if resultado.endswith("\n"):
        resultado = resultado[:-1]
    return resultado


def texts_match(observed, expected):
    return normalize_text(observed) == normalize_text(expected)


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
    """Forma de GUID, sem impor chaves. Nao valida semantica: o valor e
    conferido contra a constante MEDIDA logo em seguida."""
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
    string para Guid sozinho e o plano so transporta texto -- JSON nao tem
    tipo Guid. A conversao acontece AQUI, na fase de precondicao, e nunca
    entre a guarda e a chamada: `create_program_guarded` recebe o objeto ja
    tipado.

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
    """Append-only. Cada `mutation_attempt` e escrito ANTES do efeito e cada
    `mutation_done` DEPOIS. Uma excecao entre os dois deixa um `attempt` sem
    `done` -- a assinatura de "a copia esta em estado desconhecido"."""

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
    """Tudo conferido contra CONSTANTE do modulo."""
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
    if plan.get("gvl_name") != EXPECTED_GVL_NAME:
        problems.append("gvl_name inesperado: %r (esperado %r)"
                        % (plan.get("gvl_name"), EXPECTED_GVL_NAME))
    if plan.get("program_name") != EXPECTED_PROGRAM_NAME:
        problems.append("program_name inesperado: %r (esperado %r)"
                        % (plan.get("program_name"), EXPECTED_PROGRAM_NAME))

    guid = plan.get("st_language_guid")
    if not looks_like_guid(guid):
        problems.append(
            "st_language_guid ausente ou sem forma de GUID: %r. A string 'ST' "
            "nao o substitui -- o parametro e Nullable[Guid]." % (guid,))
    elif guid != EXPECTED_ST_LANGUAGE_GUID:
        problems.append(
            "st_language_guid do plano (%r) diverge da constante medida (%r)"
            % (guid, EXPECTED_ST_LANGUAGE_GUID))

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
                if key not in ("kind", "name", "target", "path", "language"):
                    problems.append("operacao com campo desconhecido: %r" % (key,))
            kinds.append(item.get("kind"))
        if tuple(kinds) != EXPECTED_PLAN_OPERATIONS:
            problems.append("operations deve ser exatamente %s, na ordem; "
                            "recebido %s"
                            % (list(EXPECTED_PLAN_OPERATIONS), kinds))
        else:
            targets = tuple([item.get("target") for item in operations[2:5]])
            if targets != EXPECTED_REPLACE_TARGETS:
                problems.append(
                    "os tres replace devem visar, na ordem, %s; recebido %s"
                    % (list(EXPECTED_REPLACE_TARGETS), list(targets)))

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
    else:
        if not is_text(container.get("node_path")):
            problems.append("container.node_path obrigatorio")
        declarado = container.get("expected_type_guid")
        if declarado is not None and declarado != EXPECTED_CONTAINER_TYPE_GUID:
            problems.append(
                "container.expected_type_guid do plano (%r) diverge da "
                "constante medida (%r)" % (declarado, EXPECTED_CONTAINER_TYPE_GUID))
        declarado_gvl = container.get("expected_gvl_type_guid")
        if declarado_gvl is not None and declarado_gvl != EXPECTED_GVL_TYPE_GUID:
            problems.append(
                "container.expected_gvl_type_guid do plano (%r) diverge da "
                "constante medida (%r)" % (declarado_gvl, EXPECTED_GVL_TYPE_GUID))
        declarado_prg = container.get("expected_program_type_guid")
        if declarado_prg is not None and declarado_prg != EXPECTED_PROGRAM_TYPE_GUID:
            problems.append(
                "container.expected_program_type_guid do plano (%r) diverge da "
                "constante medida (%r)"
                % (declarado_prg, EXPECTED_PROGRAM_TYPE_GUID))

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


def delta_is_exactly(before, after, expected_added):
    """(ok, added, missing) sobre os NOMES do nivel do container."""
    before_names = [item.get("name") for item in (before.get("persistent") or [])]
    after_names = [item.get("name") for item in (after.get("persistent") or [])]
    added, missing = multiset_difference(before_names, after_names)
    return (added == list(expected_added) and not missing), added, missing


def trees_equal(before, after):
    ok, _added, _missing = delta_is_exactly(before, after, ())
    return ok


def read_declaration(obj):
    result = {"text": None, "sha256": None, "gap": None, "error": None}
    try:
        if not hasattr(obj, "textual_declaration"):
            result["gap"] = "objeto nao expoe textual_declaration"
            return result
        document = obj.textual_declaration
        if document is None or not hasattr(document, "text"):
            result["gap"] = "textual_declaration sem documento ou sem text"
            return result
        text = document.text
        if text is not None:
            result["text"] = str(text)
            result["sha256"] = sha256_of_text(result["text"])
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = "declaration: %r" % (exc,)
    return result


def read_implementation(obj):
    result = {"text": None, "sha256": None, "gap": None, "error": None}
    try:
        if not hasattr(obj, "textual_implementation"):
            result["gap"] = "objeto nao expoe textual_implementation"
            return result
        document = obj.textual_implementation
        if document is None or not hasattr(document, "text"):
            result["gap"] = "textual_implementation sem documento ou sem text"
            return result
        text = document.text
        if text is not None:
            result["text"] = str(text)
            result["sha256"] = sha256_of_text(result["text"])
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = "implementation: %r" % (exc,)
    return result


def verify_created_object(created, expected_name, expected_type_guid,
                          before, after):
    """Confere o objeto devolvido por `create_*` e o delta do container.
    Nunca corrige nada -- e nunca tenta desfazer."""
    report = {"return_not_null": created is not None, "identity": None,
              "name_matches": None, "type_matches": None,
              "persistent_added": [], "persistent_missing": [], "problems": []}
    if created is None:
        report["problems"].append("create devolveu None para %r" % (expected_name,))
    else:
        identity = object_identity(created)
        report["identity"] = identity
        report["name_matches"] = (identity.get("name") == expected_name)
        if not report["name_matches"]:
            report["problems"].append(
                "nome do objeto criado e %r, esperado %r"
                % (identity.get("name"), expected_name))
        report["type_matches"] = (identity.get("type_guid") == expected_type_guid)
        if not report["type_matches"]:
            report["problems"].append(
                "type do objeto criado e %r, esperado %r"
                % (identity.get("type_guid"), expected_type_guid))

    ok, added, missing = delta_is_exactly(before, after, (expected_name,))
    report["persistent_added"] = added
    report["persistent_missing"] = missing
    if not ok:
        report["problems"].append(
            "delta do container = acrescimos %r, sumicos %r; esperado "
            "exatamente [%r] e nenhum sumico" % (added, missing, expected_name))
    if before.get("error") or after.get("error"):
        report["problems"].append(
            "enumeracao com erro (antes=%r, depois=%r)"
            % (before.get("error"), after.get("error")))
    report["ok"] = not report["problems"]
    return report


# --- as SEIS chamadas mutaveis ------------------------------------------------

def create_gvl_guarded(iec_container, safety):
    """1a mutacao. O nome e a CONSTANTE do modulo; entre a guarda e a chamada
    nao ha ramo, laco, wrapper nem log."""
    safety.assert_controlled_write_allowed("create_gvl")
    created_gvl = iec_container.create_gvl(EXPECTED_GVL_NAME)
    return created_gvl


def create_program_guarded(iec_container, st_language_guid, safety):
    """2a mutacao. `st_language_guid` chega como System.Guid JA CONVERTIDO
    (ver `to_clr_guid`): nada e calculado depois da guarda."""
    safety.assert_controlled_write_allowed("create_program")
    created_program = iec_container.create_program(EXPECTED_PROGRAM_NAME,
                                                   st_language_guid)
    return created_program


def replace_gvl_declaration_guarded(gvl_declaration_document, safety):
    """3a mutacao."""
    safety.assert_controlled_write_allowed("replace")
    gvl_declaration_document.replace(GVL_DECLARATION)
    return True


def replace_program_declaration_guarded(program_declaration_document, safety):
    """4a mutacao."""
    safety.assert_controlled_write_allowed("replace")
    program_declaration_document.replace(PROGRAM_DECLARATION)
    return True


def replace_program_implementation_guarded(program_implementation_document, safety):
    """5a mutacao. E a unica que LE outro objeto (a GVL, por
    `GVL_AI_TESTE.`), e por isso vem depois da declaracao da GVL."""
    safety.assert_controlled_write_allowed("replace")
    program_implementation_document.replace(PROGRAM_IMPLEMENTATION)
    return True


def save_as_guarded(project, output_project_path, safety):
    """6a e ultima mutacao. Sem senha, sem fallback, sem retry."""
    safety.assert_controlled_write_allowed("save_as")
    project.save_as(output_project_path)
    return True


def run_w1_4(script_globals, argv, safety, project_access, file_io, probe_cli,
             now=None, guid_converter=None):
    """Executa a autoria de W1.4. Injecao explicita dos modulos para teste com
    dubles. `guid_converter` existe porque `System.Guid` so existe sob CLR: em
    CPython o teste nao conseguiria exercitar o caminho da mutacao. Ele nao
    escolhe operacao nenhuma -- so o tipo do argumento."""
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
        "st_language_guid_converted": None,
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
        "verifications": [],
        "authored_objects": None,
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
    result["input_project"]["matches"] = \
        (observed_hash == plan["input_project"]["sha256"])
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
        result["problems"].append(
            "container IEC nao alcancado por node_path: cartoes de I/O "
            "deslocam indices (docs/32 secao 2)")
        journal.record({"event": "precondition_failed", "reason": "container_absent"})
        return finish(STATUS_PRECONDITION_FAILED)

    container_identity = object_identity(iec_container)
    result["container_identity"] = container_identity
    if container_identity.get("name") != EXPECTED_CONTAINER_NAME:
        result["problems"].append(
            "container resolvido e %r, esperado %r"
            % (container_identity.get("name"), EXPECTED_CONTAINER_NAME))
        journal.record({"event": "precondition_failed", "reason": "container_mismatch"})
        return finish(STATUS_PRECONDITION_FAILED)
    if container_identity.get("type_guid") != EXPECTED_CONTAINER_TYPE_GUID:
        result["problems"].append(
            "type do container e %r, esperado %r"
            % (container_identity.get("type_guid"), EXPECTED_CONTAINER_TYPE_GUID))
        journal.record({"event": "precondition_failed",
                        "reason": "container_type_mismatch"})
        return finish(STATUS_PRECONDITION_FAILED)

    before = enumerate_children(iec_container)
    result["before_tree"] = before
    if before.get("error"):
        result["problems"].append("enumeracao inicial falhou: %s" % before["error"])
        journal.record({"event": "precondition_failed", "reason": "enumerate_failed"})
        return finish(STATUS_PRECONDITION_FAILED)

    existing_names = [item.get("name") for item in before.get("persistent") or []]
    existing_names.extend([item.get("name") for item in before.get("transient") or []])
    for nome_alvo in (EXPECTED_GVL_NAME, EXPECTED_PROGRAM_NAME):
        if nome_alvo in existing_names:
            result["problems"].append("nome %r ja existe no container" % (nome_alvo,))
    if result["problems"]:
        journal.record({"event": "precondition_failed", "reason": "name_exists"})
        return finish(STATUS_PRECONDITION_FAILED)

    # Conversao do GUID ANTES de qualquer guarda: o plano so transporta texto
    # e a API exige Nullable[Guid]. Falhar aqui e precondicao, nao mutacao.
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

    # --- mutacao 1: create_gvl ------------------------------------------------
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
    after_gvl = enumerate_children(iec_container)
    journal.record({"event": "mutation_done", "operation": "create_gvl",
                    "call_site": CALL_SITE_CREATE_GVL,
                    "state_after": {"children": after_gvl.get("count")}})

    verificacao_gvl = verify_created_object(
        created_gvl, EXPECTED_GVL_NAME, EXPECTED_GVL_TYPE_GUID, before, after_gvl)
    result["verifications"].append({"step": "create_gvl",
                                    "report": verificacao_gvl})
    if not verificacao_gvl.get("ok"):
        result["problems"].extend(verificacao_gvl.get("problems") or [])
        journal.record({"event": "verification_failed", "operation": "create_gvl"})
        return finish(STATUS_GVL_VERIFICATION_FAILED)
    journal.record({"event": "verification_passed", "operation": "create_gvl"})

    # --- mutacao 2: create_program --------------------------------------------
    result["operations_requested"].append("create_program")
    journal.record({"event": "mutation_attempt", "operation": "create_program",
                    "phase": phase_observed, "call_site": CALL_SITE_CREATE_PROGRAM,
                    "state_before": {"children": after_gvl.get("count")}})
    try:
        created_program = create_program_guarded(iec_container, clr_guid, safety)
    except safety.SafetyError as exc:
        result["problems"].append("autorizacao de create_program recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied", "operation": "create_program",
                        "call_site": CALL_SITE_CREATE_PROGRAM, "error": repr(exc)})
        return finish(STATUS_AUTHORED_IN_MEMORY)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("create_program levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed", "operation": "create_program",
                        "call_site": CALL_SITE_CREATE_PROGRAM, "error": repr(exc)})
        return finish(STATUS_CREATE_PROGRAM_FAILED)

    result["operations_authorized"].append("create_program")
    result["operations_executed"].append("create_program")
    after_program = enumerate_children(iec_container)
    result["after_create_tree"] = after_program
    journal.record({"event": "mutation_done", "operation": "create_program",
                    "call_site": CALL_SITE_CREATE_PROGRAM,
                    "state_after": {"children": after_program.get("count")}})

    verificacao_program = verify_created_object(
        created_program, EXPECTED_PROGRAM_NAME, EXPECTED_PROGRAM_TYPE_GUID,
        after_gvl, after_program)
    result["verifications"].append({"step": "create_program",
                                    "report": verificacao_program})
    if not verificacao_program.get("ok"):
        result["problems"].extend(verificacao_program.get("problems") or [])
        journal.record({"event": "verification_failed", "operation": "create_program"})
        return finish(STATUS_PROGRAM_VERIFICATION_FAILED)
    journal.record({"event": "verification_passed", "operation": "create_program"})

    # Texto de nascimento, LIDO -- nunca presumido. A comparacao "a
    # implementacao continua intacta", entre o 4o e o 5o passo, e feita contra
    # este valor observado, e nao contra uma constante que este arquivo teria
    # inventado para a base nova.
    nascimento_gvl = read_declaration(created_gvl)
    nascimento_program_declaracao = read_declaration(created_program)
    nascimento_program_implementacao = read_implementation(created_program)
    result["birth_texts"] = {
        "gvl_declaration": nascimento_gvl,
        "program_declaration": nascimento_program_declaracao,
        "program_implementation": nascimento_program_implementacao,
    }
    for rotulo, leitura in (("gvl_declaration", nascimento_gvl),
                            ("program_declaration", nascimento_program_declaracao),
                            ("program_implementation", nascimento_program_implementacao)):
        if leitura.get("gap") or leitura.get("error") or leitura.get("text") is None:
            result["problems"].append(
                "documento textual de nascimento ilegivel (%s): %s"
                % (rotulo, leitura.get("gap") or leitura.get("error")))
            journal.record({"event": "verification_failed",
                            "operation": "read_birth_texts"})
            return finish(STATUS_PROGRAM_VERIFICATION_FAILED)

    gvl_declaration_document = created_gvl.textual_declaration
    program_declaration_document = created_program.textual_declaration
    program_implementation_document = created_program.textual_implementation
    if gvl_declaration_document is None or program_declaration_document is None \
            or program_implementation_document is None:
        result["problems"].append("documento textual ausente apos as criacoes")
        journal.record({"event": "verification_failed", "operation": "resolve_documents"})
        return finish(STATUS_PROGRAM_VERIFICATION_FAILED)

    # --- mutacao 3: replace da declaracao da GVL ------------------------------
    result["operations_requested"].append("replace_gvl_declaration")
    journal.record({"event": "mutation_attempt",
                    "operation": "replace_gvl_declaration",
                    "phase": phase_observed,
                    "call_site": CALL_SITE_REPLACE_GVL_DECLARATION})
    try:
        replace_gvl_declaration_guarded(gvl_declaration_document, safety)
    except safety.SafetyError as exc:
        result["problems"].append(
            "autorizacao de replace (declaracao da GVL) recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied",
                        "operation": "replace_gvl_declaration",
                        "call_site": CALL_SITE_REPLACE_GVL_DECLARATION,
                        "error": repr(exc)})
        return finish(STATUS_AUTHORED_IN_MEMORY)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("replace (declaracao da GVL) levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed",
                        "operation": "replace_gvl_declaration",
                        "call_site": CALL_SITE_REPLACE_GVL_DECLARATION,
                        "error": repr(exc)})
        return finish(STATUS_REPLACE_GVL_DECLARATION_FAILED)

    result["operations_authorized"].append("replace_gvl_declaration")
    result["operations_executed"].append("replace_gvl_declaration")
    journal.record({"event": "mutation_done", "operation": "replace_gvl_declaration",
                    "call_site": CALL_SITE_REPLACE_GVL_DECLARATION})

    texto_gvl = read_declaration(created_gvl)
    arvore_apos_gvl = enumerate_children(iec_container)
    gvl_texto_ok = texts_match(texto_gvl.get("text"), GVL_DECLARATION)
    arvore_ok = trees_equal(after_program, arvore_apos_gvl)
    result["verifications"].append({"step": "replace_gvl_declaration",
                                    "text_ok": gvl_texto_ok,
                                    "tree_unchanged": arvore_ok})
    if not (gvl_texto_ok and arvore_ok):
        result["problems"].append(
            "verificacao pos-replace (declaracao da GVL) falhou: texto_ok=%r "
            "arvore_intacta=%r" % (gvl_texto_ok, arvore_ok))
        journal.record({"event": "verification_failed",
                        "operation": "replace_gvl_declaration"})
        return finish(STATUS_GVL_TEXT_VERIFICATION_FAILED)
    journal.record({"event": "verification_passed",
                    "operation": "replace_gvl_declaration"})

    # --- mutacao 4: replace da declaracao do PROGRAM --------------------------
    result["operations_requested"].append("replace_program_declaration")
    journal.record({"event": "mutation_attempt",
                    "operation": "replace_program_declaration",
                    "phase": phase_observed,
                    "call_site": CALL_SITE_REPLACE_PROGRAM_DECLARATION})
    try:
        replace_program_declaration_guarded(program_declaration_document, safety)
    except safety.SafetyError as exc:
        result["problems"].append(
            "autorizacao de replace (declaracao do PROGRAM) recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied",
                        "operation": "replace_program_declaration",
                        "call_site": CALL_SITE_REPLACE_PROGRAM_DECLARATION,
                        "error": repr(exc)})
        return finish(STATUS_AUTHORED_IN_MEMORY)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append(
            "replace (declaracao do PROGRAM) levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed",
                        "operation": "replace_program_declaration",
                        "call_site": CALL_SITE_REPLACE_PROGRAM_DECLARATION,
                        "error": repr(exc)})
        return finish(STATUS_REPLACE_PROGRAM_DECLARATION_FAILED)

    result["operations_authorized"].append("replace_program_declaration")
    result["operations_executed"].append("replace_program_declaration")
    journal.record({"event": "mutation_done",
                    "operation": "replace_program_declaration",
                    "call_site": CALL_SITE_REPLACE_PROGRAM_DECLARATION})

    declaracao_program = read_declaration(created_program)
    implementacao_intocada = read_implementation(created_program)
    gvl_ainda_ok = texts_match(read_declaration(created_gvl).get("text"),
                               GVL_DECLARATION)
    declaracao_ok = texts_match(declaracao_program.get("text"), PROGRAM_DECLARATION)
    implementacao_ok = texts_match(
        implementacao_intocada.get("text"),
        nascimento_program_implementacao.get("text"))
    result["verifications"].append({"step": "replace_program_declaration",
                                    "text_ok": declaracao_ok,
                                    "gvl_text_preserved": gvl_ainda_ok,
                                    "implementation_untouched": implementacao_ok})
    if not (declaracao_ok and gvl_ainda_ok and implementacao_ok):
        result["problems"].append(
            "verificacao pos-replace (declaracao do PROGRAM) falhou: "
            "declaracao_ok=%r gvl_preservada=%r implementacao_intocada=%r"
            % (declaracao_ok, gvl_ainda_ok, implementacao_ok))
        journal.record({"event": "verification_failed",
                        "operation": "replace_program_declaration"})
        return finish(STATUS_PROGRAM_DECLARATION_VERIFICATION_FAILED)
    journal.record({"event": "verification_passed",
                    "operation": "replace_program_declaration"})

    # --- mutacao 5: replace da implementacao do PROGRAM -----------------------
    result["operations_requested"].append("replace_program_implementation")
    journal.record({"event": "mutation_attempt",
                    "operation": "replace_program_implementation",
                    "phase": phase_observed,
                    "call_site": CALL_SITE_REPLACE_PROGRAM_IMPLEMENTATION})
    try:
        replace_program_implementation_guarded(program_implementation_document, safety)
    except safety.SafetyError as exc:
        result["problems"].append(
            "autorizacao de replace (implementacao do PROGRAM) recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied",
                        "operation": "replace_program_implementation",
                        "call_site": CALL_SITE_REPLACE_PROGRAM_IMPLEMENTATION,
                        "error": repr(exc)})
        return finish(STATUS_AUTHORED_IN_MEMORY)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append(
            "replace (implementacao do PROGRAM) levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed",
                        "operation": "replace_program_implementation",
                        "call_site": CALL_SITE_REPLACE_PROGRAM_IMPLEMENTATION,
                        "error": repr(exc)})
        return finish(STATUS_REPLACE_PROGRAM_IMPLEMENTATION_FAILED)

    result["operations_authorized"].append("replace_program_implementation")
    result["operations_executed"].append("replace_program_implementation")
    journal.record({"event": "mutation_done",
                    "operation": "replace_program_implementation",
                    "call_site": CALL_SITE_REPLACE_PROGRAM_IMPLEMENTATION})

    texto_final_gvl = read_declaration(created_gvl)
    texto_final_declaracao = read_declaration(created_program)
    texto_final_implementacao = read_implementation(created_program)
    arvore_final = enumerate_children(iec_container)
    result["authored_objects"] = {
        "gvl_declaration": texto_final_gvl,
        "program_declaration": texto_final_declaracao,
        "program_implementation": texto_final_implementacao,
    }
    final_gvl_ok = texts_match(texto_final_gvl.get("text"), GVL_DECLARATION)
    final_declaracao_ok = texts_match(texto_final_declaracao.get("text"),
                                      PROGRAM_DECLARATION)
    final_implementacao_ok = texts_match(texto_final_implementacao.get("text"),
                                         PROGRAM_IMPLEMENTATION)
    arvore_final_ok = trees_equal(after_program, arvore_final)
    result["verifications"].append({"step": "replace_program_implementation",
                                    "gvl_ok": final_gvl_ok,
                                    "declaration_ok": final_declaracao_ok,
                                    "implementation_ok": final_implementacao_ok,
                                    "tree_unchanged": arvore_final_ok})
    if not (final_gvl_ok and final_declaracao_ok and final_implementacao_ok
            and arvore_final_ok):
        result["problems"].append(
            "verificacao pos-replace (implementacao) falhou: gvl_ok=%r "
            "declaracao_ok=%r implementacao_ok=%r arvore_intacta=%r"
            % (final_gvl_ok, final_declaracao_ok, final_implementacao_ok,
               arvore_final_ok))
        journal.record({"event": "verification_failed",
                        "operation": "replace_program_implementation"})
        return finish(STATUS_PROGRAM_IMPLEMENTATION_VERIFICATION_FAILED)
    journal.record({"event": "verification_passed",
                    "operation": "replace_program_implementation"})

    # --- mutacao 6: save_as ---------------------------------------------------
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
        return finish(STATUS_AUTHORED_IN_MEMORY)
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


def no_other_mutator_requested(operations_requested):
    """True quando o que foi pedido e um PREFIXO da cadeia canonica -- nunca
    uma operacao a mais, nunca fora de ordem."""
    pedido = tuple(operations_requested or ())
    return pedido == EXECUTED_OPERATION_SEQUENCE[:len(pedido)]


def build_completion(result):
    """Escrito por ULTIMO: e o sinal de conclusao."""
    autorados = result.get("authored_objects") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "phase": result.get("phase_observed"),
        "plan_sha256": result.get("plan_sha256"),
        "st_language_guid": result.get("st_language_guid"),
        "st_language_guid_converted": result.get("st_language_guid_converted"),
        "input_project_sha256_before": result.get("input_project", {}).get("sha256_observed"),
        "operations_requested": result.get("operations_requested"),
        "operations_authorized": result.get("operations_authorized"),
        "operations_executed": result.get("operations_executed"),
        "output_project_path": result.get("output_project", {}).get("path"),
        "output_project_exists": result.get("output_project", {}).get("exists_after"),
        "requires_copy_discard": result.get("requires_copy_discard"),
        "authored_gvl_declaration_sha256":
            (autorados.get("gvl_declaration") or {}).get("sha256"),
        "authored_program_declaration_sha256":
            (autorados.get("program_declaration") or {}).get("sha256"),
        "authored_program_implementation_sha256":
            (autorados.get("program_implementation") or {}).get("sha256"),
        "errors": result.get("problems"),
        "gap_notes": result.get("gap_notes"),
        "no_other_mutator_requested":
            no_other_mutator_requested(result.get("operations_requested")),
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    autorados = result.get("authored_objects") or {}
    lines = [
        "# Probe 38 -- W1.4: autoria integrada (create x2, replace x3, save_as)",
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
        "## Verificacoes intermediarias",
        "",
    ]
    for verificacao in result.get("verifications") or []:
        lines.append("- `%s`" % (verificacao,))
    lines.extend([
        "",
        "## Textos autorados",
        "",
        "- sha256 declaracao GVL: `%s`"
        % (autorados.get("gvl_declaration") or {}).get("sha256"),
        "- sha256 declaracao PROGRAM: `%s`"
        % (autorados.get("program_declaration") or {}).get("sha256"),
        "- sha256 implementacao PROGRAM: `%s`"
        % (autorados.get("program_implementation") or {}).get("sha256"),
        "",
        "## Problemas",
        "",
    ])
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
    file_io.write_json(os.path.join(artifacts_dir, "authored-objects.json"),
                       result.get("authored_objects") or {})
    written.append("authored-objects.json")
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
    print("[INFO] probes/%s -- W1.4 (escrita controlada)" % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access, safety

    try:
        result = run_w1_4(script_globals, list(sys.argv or []), safety,
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

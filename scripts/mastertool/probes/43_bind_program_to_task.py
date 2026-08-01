# -*- coding: utf-8 -*-
r"""43_bind_program_to_task.py -- marco W2: acrescentar o PROGRAM CALL de um
PROGRAM ja existente a uma task JA EXISTENTE, e persistir por `save_as` em
arquivo NOVO.

Contrato: `docs/28`. Estado que este marco ataca: `docs/37` secao 6 -- "o
programa compila; NAO ha evidencia de que o CLP o executaria". Um PROGRAM fora
da lista de POUs de toda task nao roda.

Exatamente DUAS invocacoes mutaveis, e so duas, cada uma com a guarda na linha
IMEDIATAMENTE anterior. Elas estao descritas aqui SEM a sintaxe de chamada, de
proposito: o wrapper conta as chamadas no FONTE inteiro e exige exatamente uma
de cada, e uma explicacao escrita com parenteses se contaria a si mesma --

    assert_controlled_write_allowed("add")       e, na linha seguinte, o
                                                 metodo add da colecao de POUs
                                                 da task, com o nome do PROGRAM

    assert_controlled_write_allowed("save_as")   e, na linha seguinte, o
                                                 save_as do projeto, com o
                                                 caminho novo

As duas moram em funcoes proprias, de tres linhas cada (`add_program_call_
guarded` e `save_as_guarded`), e entre a guarda e a chamada nao ha ramo, laco,
wrapper nem log.

POR QUE ACRESCENTAR A UMA TASK EXISTENTE, E NAO CRIAR TASK
----------------------------------------------------------
O `TemplateExemplo v1.project` ja tem uma task (medida nas runs 011 e 018). Reutiliza-la
reduz a superficie mutavel deste marco de duas operacoes para UMA: so `add`.
`create_task` existe no stub (L57) e NAO aparece neste arquivo -- criar task e
decisao de outra fase, com allowlist propria. Uma allowlist nao antecipa
operacao que ninguem chama (docs/30).

A ARMADILHA CENTRAL DESTE ARQUIVO
---------------------------------
`ScriptPouObjectCollection` HERDA DE `list` (stub `ScriptTaskConfigObject.pyi`
L288) e os seus mutadores se chamam `add`, `insert`, `remove` e `replace`.
Quatro nomes que colidem com o vocabulario de qualquer lista Python. Por isso:

  1. A verificacao estatica dos testes e por RECEPTOR, com o mapa completo de
     "quem chama o que" congelado. Proibir o NOME `add` seria inutil nas duas
     direcoes -- reprovaria `lista.append`/`set.add` de Python legitimo e nao
     distinguiria a chamada que escreve no projeto.
  2. A unica chamada de `add` deste arquivo mora numa funcao propria, de tres
     linhas, cujo receptor se chama `pou_collection`. Entre a guarda e a
     chamada nao ha ramo, laco, wrapper nem log.
  3. `insert`, `remove` e `replace` nao sao chamados sobre proxy nenhum.

FAIL-CLOSED HOJE, POR CONSTRUCAO
--------------------------------
A fase `W2_BIND_PROGRAM_CALL` NAO esta autorizada em `common/safety.py`:
`CONTROLLED_WRITE_PHASE` e `None` e nao existe entrada dela em
`PHASE_ALLOWED_OPERATIONS`. Este probe, portanto, PARA na precondicao de fase,
antes de tocar o projeto -- e mesmo que a fase fosse forcada, a porta unica
recusaria por falta de allowlist. Abrir a fase e decisao humana em commit
ISOLADO (docs/28 secao 14), e nao acompanha este arquivo.

O CRITERIO DO MARCO NAO TERMINA AQUI
------------------------------------
Vincular nao basta. Depois do `save_as` o projeto tem de REABRIR, o vinculo tem
de PERSISTIR e o build tem de continuar verde. A persistencia e conferida por
`probes/42 --mode=postsave` sobre a SAIDA, em abertura separada; o build e
etapa propria e ja tem instrumento (`probes/40`). Este arquivo nao compila, nao
reabre e nao promove nada.

NAO faz, por construcao: `create_task`, `create_task_configuration`,
`create_gvl`, `create_program`, `save`, `insert`, `remove`, `replace`,
`rename`, `move`, `build`, `import_xml`. Depois do `add`, uma divergencia
invalida a copia INTEIRA: registra e para, nunca tenta desfazer -- nao existe
transacao, e `remove` nao e "desfazer", e outra mutacao.

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

SCRIPT_NAME = "43_bind_program_to_task.py"
SCHEMA_VERSION = "1.0"

EXPECTED_PHASE = "W2_BIND_PROGRAM_CALL"
EXPECTED_OPERATION_ID = "w2-bind-program-call"
EXPECTED_OPERATIONS = ("add", "save_as")
EXPECTED_ADD_TARGET = "task_pou_collection"

STUB_PATH = ("C:\\Program Files\\Altus\\MT9000 4.1.0\\MT9000\\ScriptLib\\"
             "Stubs\\scriptengine\\ScriptTaskConfigObject.pyi")

MARKER_CHAIN_TASK = "projects.primary -> get_children(False) -> node.is_task"

BIND_CHAIN = "task.pous -> add(pou_name)"

BIND_SOURCE = (
    "stub oficial versionado pelo produto '%s': L39-40 "
    "ScriptTaskObjectMarker.is_task (a task e achada por TIPO, nunca por nome "
    "de no); L218-225 ScriptTaskObject.pous -> ScriptPouObjectCollection; "
    "L295-305 o metodo add de ScriptPouObjectCollection, assinatura "
    "add(pou_name, comment=None), 'Add a POU to the list' -- E ESTA a operacao "
    "de Program Call; L346-353 __len__ e "
    "L355-365 __getitem__ devolvendo 'a python tuple' (name, comment), usados "
    "para medir antes e depois." % (STUB_PATH,)
)

# O `comment` opcional de `add` (stub L301-303) NAO e usado: a allowlist deste
# marco autoriza a operacao, e nao um texto livre gravado dentro do projeto do
# cliente. Menos superficie mutavel, e nada que precise ser conferido depois.

CALL_SITE_ADD = "probes/43_bind_program_to_task.py::add_program_call_guarded"
CALL_SITE_SAVE_AS = "probes/43_bind_program_to_task.py::save_as_guarded"

# --- estados, vocabulario fechado --------------------------------------------
STATUS_PRECONDITION_FAILED = "precondition_failed"
STATUS_ALREADY_BOUND = "already_bound"
STATUS_ADD_FAILED = "add_failed"
STATUS_BIND_VERIFICATION_FAILED = "bind_verification_failed"
STATUS_BOUND_IN_MEMORY = "bound_in_memory"
STATUS_SAVE_AS_FAILED = "save_as_failed"
STATUS_SAVED_AS = "saved_as"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_PRECONDITION_FAILED, STATUS_ALREADY_BOUND, STATUS_ADD_FAILED,
    STATUS_BIND_VERIFICATION_FAILED, STATUS_BOUND_IN_MEMORY,
    STATUS_SAVE_AS_FAILED, STATUS_SAVED_AS, STATUS_FATAL,
)

SUCCESS_STATUSES = (STATUS_SAVED_AS,)

EXIT_BY_STATUS = {
    STATUS_SAVED_AS: 0,
    STATUS_PRECONDITION_FAILED: 2,
    STATUS_ALREADY_BOUND: 2,
    STATUS_ADD_FAILED: 3,
    STATUS_BIND_VERIFICATION_FAILED: 3,
    STATUS_BOUND_IN_MEMORY: 3,
    STATUS_SAVE_AS_FAILED: 4,
    STATUS_FATAL: 1,
}

# Qualquer status aqui: sem rollback, sem save, sem retry -- a copia inteira e
# descartada. `precondition_failed` e `already_bound` ficam de fora porque
# nenhuma mutacao foi TENTADA neles.
STATUSES_REQUIRING_DISCARD = (
    STATUS_ADD_FAILED, STATUS_BIND_VERIFICATION_FAILED, STATUS_BOUND_IN_MEMORY,
    STATUS_SAVE_AS_FAILED,
)

VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp")

ARTIFACT_NAMES = ("bind-manifest.json", "bind-journal.jsonl",
                  "bind-tasks-before.json", "bind-tasks-after.json",
                  "bind-completion.json", "bind-report.md")

PLAN_KEYS_REQUIRED = ("schema_version", "operation_id", "phase",
                      "input_project", "output_project", "operations",
                      "task_name", "program_name", "mastertool", "run_id",
                      "artifacts_dir")
PLAN_KEYS_OPTIONAL = ("notes",)

# --- limites de varredura ----------------------------------------------------
MAX_DEPTH = 8
MAX_TOTAL_NODES = 5000
MAX_CHILDREN_PER_NODE = 256
MAX_POUS_PER_TASK = 256
MAX_TASKS = 256

try:
    _STRING_TYPES = (basestring,)  # noqa: F821
except NameError:
    _STRING_TYPES = (str,)


class PlanError(Exception):
    """Plano recusado. Sempre antes de tocar o projeto."""


def is_text(value):
    return isinstance(value, _STRING_TYPES) and value != ""


def as_text(value):
    if value is None:
        return None
    if isinstance(value, _STRING_TYPES):
        texto = value.strip()
        return texto or None
    try:
        texto = str(value).strip()
    except Exception:                                          # noqa: BLE001
        return None
    return texto or None


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


class Journal(object):
    """Append-only. `mutation_attempt` antes do efeito, `mutation_done`
    depois."""

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
        problems.append("schema_version inesperado: %r"
                        % (plan.get("schema_version"),))
    if plan.get("phase") != EXPECTED_PHASE:
        problems.append("phase inesperada: %r (esperado %r)"
                        % (plan.get("phase"), EXPECTED_PHASE))
    if plan.get("operation_id") != EXPECTED_OPERATION_ID:
        problems.append("operation_id inesperado: %r"
                        % (plan.get("operation_id"),))
    if not is_text(plan.get("task_name")):
        problems.append("task_name obrigatorio: a task e ACHADA por is_task e "
                        "so DESEMPATADA por nome")
    if not is_text(plan.get("program_name")):
        problems.append("program_name obrigatorio")

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
                if key not in ("kind", "target"):
                    problems.append("operacao com campo desconhecido: %r" % (key,))
            kinds.append(item.get("kind"))
        if tuple(kinds) != EXPECTED_OPERATIONS:
            problems.append("operations deve ser exatamente %s, na ordem; "
                            "recebido %s" % (list(EXPECTED_OPERATIONS), kinds))
        elif operations[0].get("target") != EXPECTED_ADD_TARGET:
            problems.append(
                "a operacao 'add' deve visar %r; recebido %r. `add` colide com "
                "o metodo homonimo de list, e o alvo declarado e o que impede "
                "que um plano autorize 'um add qualquer'"
                % (EXPECTED_ADD_TARGET, operations[0].get("target")))

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
    # `base_path` e o projeto do cliente, que MORA num caminho com espaco --
    # por isso ele nao herda a proibicao acima. Quem entra em `--scriptargs` e
    # a COPIA, e e ela que precisa ser livre de espaco (achado do probe 15).
    base_path = input_project.get("base_path")
    if not is_text(base_path):
        problems.append("input_project.base_path obrigatorio")
    elif not os.path.isabs(base_path):
        problems.append("input_project.base_path deve ser absoluto")
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


# =============================================================================
# leitura -- a MESMA cadeia read-only do probe 42, e nenhum membro alem dela
# =============================================================================

def read_is_task(node):
    try:
        marcado = node.is_task
    except Exception as exc:                                   # noqa: BLE001
        return False, "is_task falhou: %r" % (exc,)
    return bool(marcado), None


def read_node_name(node):
    try:
        return as_text(node.get_name(False))
    except Exception:                                          # noqa: BLE001
        return None


def read_children(node):
    try:
        colecao = node.get_children(False)
    except Exception as exc:                                   # noqa: BLE001
        return [], "get_children falhou: %r" % (exc,)
    if colecao is None:
        return [], "get_children devolveu None"
    try:
        total = colecao.Count
    except Exception as exc:                                   # noqa: BLE001
        return [], "Count falhou: %r" % (exc,)
    if total is None or total < 0 or total > MAX_CHILDREN_PER_NODE:
        return [], "Count fora de faixa: %r" % (total,)
    filhos = []
    for indice in range(total):
        try:
            filhos.append(colecao[indice])
        except Exception as exc:                               # noqa: BLE001
            return filhos, "indexador falhou em %d: %r" % (indice, exc)
    return filhos, None


def scan_project(project):
    """Uma unica varredura DFS que responde as DUAS perguntas da precondicao:
    quais nos sao task (por `is_task`) e quais nomes existem na arvore.

    Os nomes servem para confirmar que o PROGRAM alvo EXISTE antes de vincular.
    `add(pou_name)` recebe um nome; um nome inexistente produziria um vinculo
    para lugar nenhum, que so o build revelaria -- e o build e etapa seguinte.
    """
    varredura = {"visited": 0, "truncated": False, "errors": []}
    tasks = []
    nomes = []
    if project is None:
        varredura["errors"].append("sem projeto primario")
        return tasks, nomes, varredura

    pilha = [(project, "root", 0)]
    visitados = 0
    while pilha:
        if visitados >= MAX_TOTAL_NODES:
            varredura["truncated"] = True
            break
        no_atual, node_id, profundidade = pilha.pop()
        visitados += 1

        if node_id != "root":
            nome = read_node_name(no_atual)
            if nome is not None:
                nomes.append({"node_id": node_id, "name": nome})
            marcado, erro = read_is_task(no_atual)
            if erro:
                varredura["errors"].append("%s: %s" % (node_id, erro))
            elif marcado and len(tasks) < MAX_TASKS:
                tasks.append({"node_id": node_id, "name": nome, "node": no_atual})

        if profundidade >= MAX_DEPTH:
            continue
        filhos, erro_filhos = read_children(no_atual)
        if erro_filhos:
            varredura["errors"].append("%s: %s" % (node_id, erro_filhos))
        indice = len(filhos) - 1
        while indice >= 0:
            pilha.append((filhos[indice], "%s/%d" % (node_id, indice),
                          profundidade + 1))
            indice -= 1

    varredura["visited"] = visitados
    return tasks, nomes, varredura


def read_pou_entries(pou_collection):
    """`len(...)` e o indexador. NENHUMA chamada de metodo sobre a colecao.

    Devolve `(entradas, erro)`. Lista vazia e MEDIDA: task sem Program Call e
    exatamente o estado inicial que este marco existe para mudar.
    """
    if pou_collection is None:
        return None, "task.pous devolveu None"
    try:
        total = len(pou_collection)
    except Exception as exc:                                   # noqa: BLE001
        return None, "len(pous) falhou: %r" % (exc,)
    if total is None or total < 0 or total > MAX_POUS_PER_TASK:
        return None, "len(pous) fora de faixa: %r" % (total,)
    entradas = []
    for indice in range(total):
        try:
            item = pou_collection[indice]
        except Exception as exc:                               # noqa: BLE001
            return None, "pous[%d] falhou: %r" % (indice, exc)
        try:
            nome = as_text(item[0])
            comentario = as_text(item[1])
        except Exception as exc:                               # noqa: BLE001
            return None, ("pous[%d] nao e a tupla (name, comment) que o stub "
                          "documenta: %r" % (indice, exc))
        entradas.append({"index": indice, "name": nome, "comment": comentario})
    return entradas, None


def entry_names(entries):
    return [item.get("name") for item in (entries or [])]


def select_task(tasks, task_name):
    """`(task, problema)`. O MARCADOR decide o que E task; o nome so desempata
    entre nos que ele ja provou serem tasks.

    Duas tasks com o mesmo nome param o probe: vincular a "uma delas" seria
    escolher por acaso, e a escolha ficaria invisivel no artefato.
    """
    encontradas = [item for item in (tasks or []) if item.get("name") == task_name]
    if not encontradas:
        return None, ("nenhuma task marcada por is_task se chama %r (tasks "
                      "vistas: %s)" % (task_name,
                                       [item.get("name") for item in (tasks or [])]))
    if len(encontradas) > 1:
        return None, ("%d tasks marcadas por is_task se chamam %r; vincular a "
                      "'uma delas' seria escolher por acaso"
                      % (len(encontradas), task_name))
    return encontradas[0], None


def verify_binding(before_entries, after_entries, program_name):
    """A verificacao pos-`add`, feita sobre o que foi RELIDO do produto.

    Tres condicoes, e as tres importam:
      - a lista cresceu em exatamente UM;
      - as entradas anteriores continuam la, na mesma ordem (prefixo intacto);
      - o nome esperado esta presente exatamente uma vez a mais que antes.
    """
    resultado = {"ok": False, "count_before": None, "count_after": None,
                 "prefix_intact": None, "program_present": None, "reason": None,
                 "names_before": entry_names(before_entries),
                 "names_after": entry_names(after_entries)}
    if before_entries is None or after_entries is None:
        resultado["reason"] = "lista de POUs ilegivel antes ou depois do add"
        return resultado
    antes = entry_names(before_entries)
    depois = entry_names(after_entries)
    resultado["count_before"] = len(antes)
    resultado["count_after"] = len(depois)
    resultado["prefix_intact"] = depois[:len(antes)] == antes
    resultado["program_present"] = (depois.count(program_name)
                                    == antes.count(program_name) + 1)
    if len(depois) != len(antes) + 1:
        resultado["reason"] = ("a lista de POUs foi de %d para %d entradas; "
                               "esperado exatamente uma a mais"
                               % (len(antes), len(depois)))
        return resultado
    if not resultado["prefix_intact"]:
        resultado["reason"] = ("as entradas anteriores mudaram de conteudo ou "
                               "de ordem: %s -> %s" % (antes, depois))
        return resultado
    if not resultado["program_present"]:
        resultado["reason"] = ("%r nao aparece uma vez a mais na lista relida"
                               % (program_name,))
        return resultado
    resultado["ok"] = True
    return resultado


# =============================================================================
# as DUAS chamadas mutaveis
# =============================================================================

def add_program_call_guarded(pou_collection, program_name, safety):
    """A PRIMEIRA e principal mutacao deste arquivo: o Program Call.

    O receptor se chama `pou_collection` de proposito -- e por RECEPTOR que a
    verificacao estatica distingue esta chamada de um `.add` de colecao Python.
    Entre a guarda e a chamada nao ha ramo, laco, wrapper nem log.

    O `comment` opcional do stub nao e passado: menos superficie mutavel.
    """
    safety.assert_controlled_write_allowed("add")
    pou_collection.add(program_name)
    return True


def save_as_guarded(project, output_project_path, safety):
    """A unica persistencia deste arquivo. Sem senha, sem fallback, sem retry.

    `save_as` e nao `save`: escrever em arquivo NOVO preserva a copia de
    entrada como testemunha do estado inicial, e o wrapper confere o hash dela
    depois.
    """
    safety.assert_controlled_write_allowed("save_as")
    project.save_as(output_project_path)
    return True


def run_bind(script_globals, argv, safety, project_access, file_io, probe_cli,
             now=None):
    """Executa o vinculo. Injecao explicita dos modulos para teste com dubles."""
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
        "plan_path": None,
        "plan_sha256": None,
        "bind_chain": BIND_CHAIN,
        "bind_chain_source": BIND_SOURCE,
        "marker_chain_task": MARKER_CHAIN_TASK,
        "input_project": {"path": None, "sha256_expected": None,
                          "sha256_observed": None, "matches": None},
        "output_project": {"path": None, "exists_before": None,
                           "exists_after": None},
        "task": {"name": None, "node_id": None},
        "program_name": None,
        "pous_before": None,
        "pous_after": None,
        "verification": None,
        "walk": None,
        "operations_requested": [],
        "operations_authorized": [],
        "operations_executed": [],
        "problems": [],
        "gap_notes": [],
        "runtime": None,
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
    _marcar_inicio(list(argv or []), "plano_lido")
    result["plan_sha256"] = plan_hash

    # O DESTINO DOS ARTEFATOS E FIXADO ANTES DA VALIDACAO, e nao depois.
    #
    # Medido na run-021: com ele fixado so depois, uma reprovacao de plano
    # retornava sem que `result["artifacts_dir"]` existisse, e `write_artifacts`
    # nao tinha para onde escrever. O erro existia e nao tinha onde ser dito --
    # a sessao terminava sem NENHUM arquivo, e quem lia nao sabia se o probe
    # tinha rodado. Um relatorio de erro que depende de o plano estar certo nao
    # relata justamente o caso em que ele esta errado.
    #
    # A leitura e defensiva de proposito: o campo pode faltar ou nao ser texto,
    # e e exatamente isso que a validacao abaixo vai apontar.
    try:
        destino_declarado = plan.get("artifacts_dir")
    except Exception:                                          # noqa: BLE001
        destino_declarado = None
    if is_text(destino_declarado):
        result["artifacts_dir"] = destino_declarado

    problems = validate_plan(plan, REPO_ROOT)
    if problems:
        result["problems"].extend(problems)
        return finish(STATUS_PRECONDITION_FAILED)

    input_path = plan["input_project"]["path"]
    output_path = plan["output_project"]["path"]
    artifacts_dir = plan["artifacts_dir"]
    task_name = plan["task_name"]
    program_name = plan["program_name"]
    result["input_project"]["path"] = input_path
    result["input_project"]["sha256_expected"] = plan["input_project"]["sha256"]
    result["output_project"]["path"] = output_path
    result["artifacts_dir"] = artifacts_dir
    result["task"]["name"] = task_name
    result["program_name"] = program_name

    journal.path = os.path.join(artifacts_dir, "bind-journal.jsonl")
    journal.record({"event": "plan_accepted", "plan_sha256": plan_hash,
                    "phase_expected": EXPECTED_PHASE})

    _marcar_inicio(list(argv or []), "antes_de_runtime_identity")
    result["runtime"] = probe_cli.runtime_identity()
    _marcar_inicio(list(argv or []), "depois_de_runtime_identity")
    expected_version = plan["mastertool"].get("version")
    observed_version = (result["runtime"] or {}).get("file_version")
    if observed_version != expected_version:
        result["problems"].append(
            "instalacao inesperada: observada %r, plano espera %r"
            % (observed_version, expected_version))

    # A FASE. Hoje `W2_BIND_PROGRAM_CALL` NAO esta autorizada em safety.py, e e
    # AQUI que o probe para -- antes de tocar o projeto. Abrir a fase e commit
    # isolado (docs/28 secao 14).
    try:
        phase_observed = safety.CONTROLLED_WRITE_PHASE
    except Exception:                                          # noqa: BLE001
        phase_observed = None
    result["phase_observed"] = phase_observed
    if phase_observed != EXPECTED_PHASE:
        result["problems"].append(
            "fase controlada observada e %r, esperada %r. Nenhuma mutacao foi "
            "tentada." % (phase_observed, EXPECTED_PHASE))

    if result["problems"]:
        journal.record({"event": "precondition_failed",
                        "problem_count": len(result["problems"])})
        return finish(STATUS_PRECONDITION_FAILED)

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
    result["input_project"]["matches"] = (observed_hash ==
                                          plan["input_project"]["sha256"])
    if hash_error:
        result["problems"].append("sha256 do projeto aberto ilegivel: %s" % hash_error)
    elif not result["input_project"]["matches"]:
        result["problems"].append("sha256 do projeto aberto diverge do plano")

    exists_before = os.path.exists(output_path)
    result["output_project"]["exists_before"] = exists_before
    if exists_before:
        result["problems"].append("arquivo de saida ja existe: %r" % (output_path,))

    if result["problems"]:
        journal.record({"event": "precondition_failed",
                        "problem_count": len(result["problems"])})
        return finish(STATUS_PRECONDITION_FAILED)

    tasks, nomes, varredura = scan_project(project)
    result["walk"] = varredura
    if varredura.get("truncated"):
        result["problems"].append(
            "a varredura foi truncada em %d nos; a task alvo pode ter ficado "
            "fora e vincular sem ter visto a arvore inteira nao e medida"
            % (MAX_TOTAL_NODES,))
        journal.record({"event": "precondition_failed", "reason": "walk_truncated"})
        return finish(STATUS_PRECONDITION_FAILED)

    task_entry, problema_task = select_task(tasks, task_name)
    if task_entry is None:
        result["problems"].append(problema_task)
        journal.record({"event": "precondition_failed", "reason": "task_not_selected"})
        return finish(STATUS_PRECONDITION_FAILED)
    result["task"]["node_id"] = task_entry.get("node_id")

    programas = [item for item in nomes if item.get("name") == program_name]
    if not programas:
        result["problems"].append(
            "o PROGRAM %r nao existe na arvore varrida. `add` recebe um NOME: "
            "vincular um nome inexistente produziria um Program Call para "
            "lugar nenhum, e so o build revelaria." % (program_name,))
        journal.record({"event": "precondition_failed", "reason": "program_absent"})
        return finish(STATUS_PRECONDITION_FAILED)
    if len(programas) > 1:
        result["problems"].append(
            "%d objetos na arvore se chamam %r; o nome que `add` receberia e "
            "ambiguo" % (len(programas), program_name))
        journal.record({"event": "precondition_failed", "reason": "program_ambiguous"})
        return finish(STATUS_PRECONDITION_FAILED)

    try:
        pou_collection = task_entry["node"].pous
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("task.pous levantou: %r" % (exc,))
        journal.record({"event": "precondition_failed", "reason": "pous_unreadable"})
        return finish(STATUS_PRECONDITION_FAILED)

    before_entries, erro_before = read_pou_entries(pou_collection)
    result["pous_before"] = before_entries
    if before_entries is None:
        result["problems"].append(
            "lista de POUs ilegivel antes da mutacao: %s" % (erro_before,))
        journal.record({"event": "precondition_failed", "reason": "pous_unreadable"})
        return finish(STATUS_PRECONDITION_FAILED)

    if program_name in entry_names(before_entries):
        # IDEMPOTENCIA: o vinculo ja existe. Nao e sucesso (nada foi feito
        # nesta sessao) e nao e falha de mutacao -- e um estado proprio, com
        # nome proprio, e sem nenhuma chamada mutavel emitida.
        result["problems"].append(
            "%r JA esta na lista de POUs de %r (posicao %d). Nenhuma mutacao "
            "foi tentada: acrescentar de novo criaria Program Call duplicado."
            % (program_name, task_name,
               entry_names(before_entries).index(program_name)))
        journal.record({"event": "already_bound", "task": task_name,
                        "program": program_name})
        return finish(STATUS_ALREADY_BOUND)

    journal.record({"event": "preconditions_passed",
                    "task_node_id": task_entry.get("node_id"),
                    "pous_before": entry_names(before_entries)})

    # --- mutacao 1: o Program Call -------------------------------------------
    result["operations_requested"].append("add")
    journal.record({"event": "mutation_attempt", "operation": "add",
                    "phase": phase_observed, "call_site": CALL_SITE_ADD,
                    "state_before": {"pous": entry_names(before_entries)}})
    # Marcador ANTES da chamada, gravado em disco. A run-021 mostrou que o
    # processo pode terminar sem que `except BaseException` dispare -- ou seja,
    # sem excecao Python alguma --, e nesse caso o unico jeito de saber onde
    # ele parou e um arquivo ja fechado no disco antes de a chamada acontecer.
    _marcar_inicio(list(argv or []), "antes_do_add")
    try:
        add_program_call_guarded(pou_collection, program_name, safety)
        _marcar_inicio(list(argv or []), "depois_do_add")
    except safety.SafetyError as exc:
        result["problems"].append("autorizacao de add recusada: %s" % (exc,))
        journal.record({"event": "mutation_denied", "operation": "add",
                        "call_site": CALL_SITE_ADD, "error": repr(exc)})
        return finish(STATUS_PRECONDITION_FAILED)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("add levantou: %r" % (exc,))
        journal.record({"event": "mutation_failed", "operation": "add",
                        "call_site": CALL_SITE_ADD, "error": repr(exc)})
        return finish(STATUS_ADD_FAILED)

    result["operations_authorized"].append("add")
    result["operations_executed"].append("add")
    journal.record({"event": "mutation_done", "operation": "add",
                    "call_site": CALL_SITE_ADD})

    after_entries, erro_after = read_pou_entries(pou_collection)
    result["pous_after"] = after_entries
    if after_entries is None:
        result["gap_notes"].append(
            "lista de POUs ilegivel APOS o add: %s" % (erro_after,))
    verificacao = verify_binding(before_entries, after_entries, program_name)
    result["verification"] = verificacao
    if not verificacao["ok"]:
        result["problems"].append(
            "verificacao pos-add falhou: %s" % (verificacao.get("reason"),))
        journal.record({"event": "verification_failed", "operation": "add"})
        return finish(STATUS_BIND_VERIFICATION_FAILED)
    journal.record({"event": "verification_passed", "operation": "add",
                    "pous_after": entry_names(after_entries)})

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
        return finish(STATUS_BOUND_IN_MEMORY)
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

    # `saved_as` diz que o vinculo foi feito e PERSISTIDO em arquivo novo. Ele
    # NAO diz que o vinculo sobrevive a uma reabertura, nem que o projeto ainda
    # compila: essas duas provas sao de outras aberturas (probes/42 em
    # --mode=postsave e probes/40), e o wrapper as executa em etapa propria.
    return finish(STATUS_SAVED_AS)


# =============================================================================
# artefatos
# =============================================================================

def build_completion(result):
    """Escrito por ULTIMO: e o sinal de conclusao."""
    verificacao = result.get("verification") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "phase": result.get("phase_observed"),
        "plan_sha256": result.get("plan_sha256"),
        "bind_chain": result.get("bind_chain"),
        "bind_chain_source": result.get("bind_chain_source"),
        "task_name": (result.get("task") or {}).get("name"),
        "task_node_id": (result.get("task") or {}).get("node_id"),
        "program_name": result.get("program_name"),
        "pous_before": [item.get("name") for item in (result.get("pous_before") or [])],
        "pous_after": [item.get("name") for item in (result.get("pous_after") or [])],
        "binding_verified_in_memory": bool(verificacao.get("ok")),
        "input_project_sha256_before":
            result.get("input_project", {}).get("sha256_observed"),
        "output_project_path": result.get("output_project", {}).get("path"),
        "output_project_exists": result.get("output_project", {}).get("exists_after"),
        "operations_requested": result.get("operations_requested"),
        "operations_authorized": result.get("operations_authorized"),
        "operations_executed": result.get("operations_executed"),
        "no_other_mutator_requested":
            tuple(result.get("operations_requested") or ()) in
            ((), ("add",), ("add", "save_as")),
        "requires_copy_discard": result.get("requires_copy_discard"),
        "errors": result.get("problems"),
        "gap_notes": result.get("gap_notes"),
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    verificacao = result.get("verification") or {}
    lines = [
        "# Probe 43 -- W2: Program Call (add + save_as)",
        "",
        "- status: **%s**" % result.get("status"),
        "- exit_code logico: **%s**" % result.get("exit_code"),
        "- fase observada: `%s`" % result.get("phase_observed"),
        "- cadeia: `%s`" % result.get("bind_chain"),
        "- task: `%s` (`%s`)" % ((result.get("task") or {}).get("name"),
                                 (result.get("task") or {}).get("node_id")),
        "- PROGRAM: `%s`" % result.get("program_name"),
        "- copia precisa ser descartada: **%s**" % result.get("requires_copy_discard"),
        "",
        "## Program Calls da task",
        "",
        "- antes: `%s`" % (verificacao.get("names_before"),),
        "- depois: `%s`" % (verificacao.get("names_after"),),
        "- prefixo intacto: `%s`" % verificacao.get("prefix_intact"),
        "- verificacao em memoria: **%s** (%s)"
        % (verificacao.get("ok"), verificacao.get("reason")),
        "",
        "## Operacoes",
        "",
        "- solicitadas: `%s`" % (result.get("operations_requested"),),
        "- executadas: `%s`" % (result.get("operations_executed"),),
        "",
        "## O que este probe NAO prova",
        "",
        "- que o vinculo PERSISTE apos reabrir: probe 42 em `--mode=postsave`",
        "- que o projeto ainda compila: probe 40, em etapa propria",
        "",
        "## Problemas",
        "",
    ]
    for problem in result.get("problems") or []:
        lines.append("- %s" % problem)
    if not (result.get("problems") or []):
        lines.append("- nenhum")
    lines.append("")
    lines.append("## Lacunas")
    lines.append("")
    for nota in result.get("gap_notes") or []:
        lines.append("- %s" % nota)
    if not (result.get("gap_notes") or []):
        lines.append("- nenhuma")
    lines.append("")
    return "\n".join(lines)


def write_artifacts(result, file_io):
    artifacts_dir = result.get("artifacts_dir")
    if not artifacts_dir:
        return None
    file_io.ensure_dir(artifacts_dir)
    written = []

    manifest = {}
    for key in result:
        if key in ("journal",):
            continue
        manifest[key] = result[key]
    manifest["artifact_names"] = list(ARTIFACT_NAMES)
    manifest["volatile_fields"] = list(VOLATILE_FIELDS)
    manifest["exit_code_by_status"] = EXIT_BY_STATUS

    file_io.write_json(os.path.join(artifacts_dir, "bind-manifest.json"), manifest)
    written.append("bind-manifest.json")
    file_io.write_json(os.path.join(artifacts_dir, "bind-tasks-before.json"),
                       {"pous": result.get("pous_before") or [],
                        "task": result.get("task")})
    written.append("bind-tasks-before.json")
    file_io.write_json(os.path.join(artifacts_dir, "bind-tasks-after.json"),
                       {"pous": result.get("pous_after") or [],
                        "verification": result.get("verification")})
    written.append("bind-tasks-after.json")
    file_io.write_text(os.path.join(artifacts_dir, "bind-report.md"),
                       build_report_markdown(result))
    written.append("bind-report.md")
    file_io.write_json(os.path.join(artifacts_dir, "bind-completion.json"),
                       build_completion(result))
    written.append("bind-completion.json")
    return written


def _marcar_inicio(argv, estagio="main"):
    """Grava `bind-started.json` como PRIMEIRA acao, antes de qualquer import
    de `common` e antes de qualquer logica.

    Existe porque `print` num probe do MasterTool NAO vai para stdout -- vai
    para o message store do produto, e some com a janela. Sem este marcador,
    "nenhum artefato" tem duas leituras incompativeis: o probe nao rodou, ou
    rodou e morreu antes de gravar. As duas pedem investigacoes opostas.

    Medido na run-020 e na run-021: o probe terminava sem NENHUM arquivo, nem
    mesmo o de erro, e nao havia como distinguir os dois casos.

    Usa apenas `open` e `os` -- nada de `common`, porque um erro de import ali
    e justamente uma das hipoteses que este marcador precisa distinguir.
    Nunca levanta.
    """
    try:
        caminho_plano = None
        for bruto in (argv or []):
            if bruto.startswith("--plan="):
                caminho_plano = bruto.split("=", 1)[1]
        if not caminho_plano:
            return
        conteudo = open(caminho_plano, "rb").read().decode("utf-8")
        plano = json.loads(conteudo)
        destino = plano.get("artifacts_dir")
        if not destino:
            return
        if not os.path.isdir(destino):
            os.makedirs(destino)
        marcador = open(os.path.join(destino, "bind-started.json"), "wb")
        try:
            marcador.write(json.dumps({
                "script": "probes/" + SCRIPT_NAME,
                "phase": EXPECTED_PHASE,
                "stage": estagio,
                "note": ("o probe carregou e chegou ao estagio declarado. A "
                         "ausencia deste arquivo significa que ele nem "
                         "carregou -- e nao que ele falhou no meio."),
            }, indent=2).encode("utf-8"))
        finally:
            marcador.close()
    except Exception:                                          # noqa: BLE001
        pass


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    _marcar_inicio(list(sys.argv or []))
    print("=" * 68)
    print("[INFO] probes/%s -- W2 Program Call (escrita controlada)" % SCRIPT_NAME)
    print("[INFO] cadeia: %s" % BIND_CHAIN)
    print("[INFO] marcador da task: %s" % MARKER_CHAIN_TASK)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    # O IMPORT ENTRA NO `try`, e a rede pega BaseException.
    #
    # Medido nas runs 020 e 021: com o import fora, uma falha ali escapava do
    # unico bloco que grava artefato de erro, e a sessao terminava com
    # `bind-started.json` e mais nada -- o marcador provava que o probe rodou,
    # e nenhum arquivo dizia POR QUE ele parou. Depois de mover o import para
    # dentro, o sintoma PERSISTIU: logo o que escapa nao e `Exception`.
    #
    # `BaseException` cobre `SystemExit` e `KeyboardInterrupt`, e no IronPython
    # cobre tambem excecao .NET que nao entre na hierarquia Python. Capturar
    # tao largo seria ruim num programa comum; aqui e o contrario: o artefato
    # e o UNICO canal de evidencia, e um erro que escapa sem deixar arquivo
    # obriga quem le a adivinhar entre "nao rodou" e "morreu no meio".
    try:
        _marcar_inicio(list(sys.argv or []), "antes_do_import")
        from common import file_io, probe_cli, project_access, safety
        _marcar_inicio(list(sys.argv or []), "antes_do_run_bind")
        result = run_bind(script_globals, list(sys.argv or []), safety,
                          project_access, file_io, probe_cli)
    except BaseException as exc:                               # noqa: BLE001
        # O ARTEFATO E O UNICO CANAL DE EVIDENCIA, e por isso ele tem de ser
        # gravado em TODO caminho -- inclusive neste.
        #
        # Medido na run-020: uma excecao aqui devolvia o exit code e nao
        # gravava nada. O wrapper via "artefato ausente" e, corretamente, teve
        # de declarar a copia em estado DESCONHECIDO -- quando na verdade nada
        # tinha sido mutado. Ausencia de artefato nao distingue "morreu antes
        # de tocar em qualquer coisa" de "morreu no meio da mutacao", e as
        # duas pedem acoes opostas: uma manda reusar a copia, a outra manda
        # descarta-la.
        detalhe = repr(exc)
        rastro = None
        try:
            rastro = traceback.format_exc()
        except Exception:                                      # noqa: BLE001
            rastro = None
        print("[FATAL] %s" % detalhe)
        if rastro:
            print(rastro)
        _gravar_artefato_fatal(list(sys.argv or []), detalhe, rastro)
        _encerrar_plataforma(script_globals)
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

    # ENCERRA O MASTERTOOL, e so DEPOIS de os artefatos estarem no disco.
    #
    # `CloseMainWindow()` nao fecha nesta fase: escrever deixa o projeto
    # alterado em memoria, o pedido de fechar cai num dialogo modal de salvar e
    # a janela fica aberta -- medido tres vezes seguidas na run-019, com o
    # operador tendo de clicar "Nao" em cada uma. Pior aqui do que la: responder
    # "Sim" gravaria por cima da COPIA DE ENTRADA, destruindo a testemunha do
    # estado inicial.
    #
    # `system.exit()` "shuts down the engine and exits the process"
    # (ScriptSystem.pyi L143-157) -- encerra sem passar pelo dialogo. NAO e
    # `Stop-Process` disfarcado: aquilo mata o processo de fora e pode
    # interromper gravacao de artefato; isto e o proprio produto se encerrando,
    # por API documentada, com os artefatos JA gravados acima.
    _encerrar_plataforma(script_globals)
    return result.get("exit_code")


def _gravar_artefato_fatal(argv, detalhe, rastro):
    """Grava `bind-completion.json` minimo quando o caminho normal levanta.

    NAO DEPENDE DE `common`. Usa so `open`, `os` e `json` -- porque uma falha
    ao importar `common` e justamente um dos casos que este artefato precisa
    registrar, e um gravador que dependesse do modulo quebrado morreria junto.

    Declara `operations_executed: []` e `requires_copy_discard: False`, e as
    duas afirmacoes tem a MESMA base: a excecao escapou do bloco protegido, e
    toda mutacao la dentro e guardada e registrada no journal ANTES do efeito.
    Uma excecao que tivesse passado por uma delas teria deixado rastro; sem
    rastro, nada foi mutado.

    Nunca levanta -- levantar aqui apagaria tambem a mensagem de erro.
    """
    artifacts_dir = None
    try:
        for bruto in (argv or []):
            if bruto.startswith("--plan="):
                caminho = bruto.split("=", 1)[1]
                dados = open(caminho, "rb").read().decode("utf-8")
                artifacts_dir = json.loads(dados).get("artifacts_dir")
    except Exception:                                          # noqa: BLE001
        artifacts_dir = None
    if not artifacts_dir:
        print("[ERROR] sem artifacts_dir: o artefato fatal nao pode ser gravado")
        return
    conteudo = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": STATUS_FATAL,
        "exit_code": EXIT_BY_STATUS[STATUS_FATAL],
        "is_success": False,
        "phase": EXPECTED_PHASE,
        "operations_requested": list(EXPECTED_OPERATIONS),
        "operations_executed": [],
        "requires_copy_discard": False,
        "errors": [detalhe],
        "traceback": rastro,
        "gap_notes": [
            "a excecao escapou de run_bind. Toda mutacao de la e guardada e "
            "registrada no journal ANTES do efeito, entao a ausencia de "
            "registro de mutacao e evidencia de que nada foi mutado -- e nao "
            "apenas ausencia de evidencia."
        ],
    }
    try:
        if not os.path.isdir(artifacts_dir):
            os.makedirs(artifacts_dir)
        alvo = open(os.path.join(artifacts_dir, "bind-completion.json"), "wb")
        try:
            alvo.write(json.dumps(conteudo, indent=2).encode("utf-8"))
        finally:
            alvo.close()
        print("[INFO] artefato fatal gravado em %s" % artifacts_dir)
    except Exception as exc:                                   # noqa: BLE001
        print("[ERROR] falha ao gravar o artefato fatal: %r" % (exc,))


def _encerrar_plataforma(script_globals):
    """Chama `system.exit(0)` se o global existir. Nunca levanta.

    O codigo de saida do probe ja foi decidido e gravado no artefato; este
    encerramento e sobre a JANELA, e nao sobre o veredito.
    """
    try:
        system = script_globals.get("system") if script_globals else None
    except Exception:                                          # noqa: BLE001
        system = None
    if system is None:
        print("[INFO] `system` indisponivel: feche a janela manualmente.")
        return
    try:
        print("[INFO] encerrando o MasterTool por system.exit(0)...")
        system.exit(0)
    except Exception as exc:                                   # noqa: BLE001
        print("[INFO] system.exit falhou (%r): feche a janela manualmente." % (exc,))


if "projects" in globals():
    sys.exit(main())

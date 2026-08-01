# -*- coding: utf-8 -*-
r"""42_recon_tasks_readonly.py - reconhecimento SOMENTE LEITURA da Task
Configuration, das tasks e do Program Call que cada task ja executa.

MOTIVO DE EXISTIR
-----------------
`docs/37` fecha W1 com uma frase que este probe existe para instrumentar: "o
programa compila; NAO ha evidencia de que o CLP o executaria". Um PROGRAM que
nao esta na lista de POUs de nenhuma task nao roda -- o projeto compila e o CLP
nao executa nada. Antes de vincular, e preciso MEDIR o que ja existe: quantas
tasks ha, como cada uma esta configurada, e o que cada uma ja chama.

Este probe le. Ele nao cria task, nao vincula programa, nao salva e nao
compila. A mutacao e do `probes/43`, em fase propria.

FONTE DE PRIMEIRA CLASSE: O STUB QUE O PRODUTO VERSIONA
-------------------------------------------------------
Todas as assinaturas abaixo vem de

    C:\Program Files\Altus\MT9000 4.1.0\MT9000\ScriptLib\Stubs\scriptengine\
    ScriptTaskConfigObject.pyi

que e o stub oficial instalado com o MT9000 4.1.0 -- a mesma classe de fonte
que resolveu a compiler version e o inventario de bibliotecas. Nenhuma linha
deste arquivo chama membro que nao esteja catalogado la.

  L21-22    `ScriptTaskConfigObjectMarker.is_task_configuration` -> bool
            "Every ScriptObject instance will be extended with this method",
            ":version added: 3.5.10.0". E por AQUI que o no da Task
            Configuration e reconhecido: por TIPO, nunca pelo nome. Nome de no
            e rotulo de interface e depende do idioma do projeto -- foi assim
            que a run-011 procurou biblioteca no lugar errado (docs/36).

  L39-40    `ScriptTaskObjectMarker.is_task` -> bool. Mesmo argumento: a task
            e reconhecida por tipo.

  L75-82    `ScriptTaskObject.name` -> str
  L84-91    `ScriptTaskObject.kind_of_task` -> KindOfTask (enum, L5-11:
            Cyclic=1, Freewheeling=2, Event=3, ExternalEvent=4, Status=5,
            ParentSynchron=6)
  L106-113  `ScriptTaskObject.priority` -> str
  L119-129  `ScriptTaskObject.interval` -> str; o proprio stub avisa que exige
            `kind_of_task` em Cyclic ou ExternalEvent
  L135-144  `ScriptTaskObject.interval_unit` -> str
  L150-157  `ScriptTaskObject.watchdog` -> ScriptWatchdog
  L228-285  `ScriptWatchdog.enabled` (bool), `.time` (str), `.time_unit` (str),
            `.sensitivity` (str)
  L218-225  `ScriptTaskObject.pous` -> ScriptPouObjectCollection
  L288-293  `ScriptPouObjectCollection(list)` -- a colecao HERDA de `list`
  L346-353  `__len__` -> int
  L355-365  `__getitem__(index)` -> "the name and the comment of the entry at
            the specifed index as a python tuple", `tuple[str, str]`

O PERIGO DESTE PROBE, E COMO ELE E CONTIDO
------------------------------------------
`ScriptPouObjectCollection` HERDA DE `list` (L288) e os seus mutadores se
chamam `add`, `insert`, `remove` e `replace` -- quatro nomes que colidem com o
vocabulario cotidiano de qualquer lista Python. Uma verificacao por NOME de
metodo aqui seria inutil nas duas direcoes: reprovaria o metodo `append` de uma
lista Python, que e inofensivo, e nao teria como distinguir o mutador da
colecao de POUs -- que escreve no projeto -- de um homonimo qualquer. Por isso
a verificacao estatica dos testes e por RECEPTOR, com o mapa de "quem chama o
que"
CONGELADO. Os unicos receptores que sao proxies do MasterTool neste arquivo
sao `node` e `system`, e o que eles podem receber esta escrito no teste.

Neste probe a colecao de POUs so e LIDA, e por duas operacoes que nao sao
chamadas de metodo: `len(...)` e o indexador. Nao ha uma unica chamada de
metodo sobre ela.

ZERO E MEDIDA AQUI, AO CONTRARIO DO PROBE 41
--------------------------------------------
No inventario de bibliotecas, lista vazia era LACUNA: zero biblioteca num
projeto industrial e implausivel, e o vazio repetia o sintoma da run-011. Aqui
e o oposto, e a diferenca precisa estar escrita para ninguem "corrigir" o que
esta certo: uma task SEM Program Call e exatamente o estado inicial esperado, e
distinguir 0 de 1 e a GRANDEZA QUE ESTE PROBE MEDE. Tratar `pous` vazio como
lacuna apagaria a medida.

NAO USADO, DE PROPOSITO
-----------------------
- A API de CRIACAO de task (stub L57) NAO aparece neste arquivo -- nem em
  codigo, nem em comentario, nem em docstring, de onde alguem poderia copia-la
  por engano. O wrapper le o fonte e recusa a sessao se ela aparecer. A
  estrategia do marco tambem nao pede criacao: ver `probes/43`.
- Os setters de `kind_of_task`, `priority`, `interval`, `interval_unit`,
  `event`, `external_event`, `core_binding` e `parent_synchron_task` existem no
  stub. Nenhuma ATRIBUICAO de atributo ocorre neste arquivo, e ha teste que
  verifica isso na arvore inteira: atribuicao escreveria no projeto sem chamar
  metodo nenhum e passaria por baixo de qualquer guarda que so olhe chamadas.
- Nao ha `getattr`, `dir`, `eval`, enumeracao de membros nem busca por nome
  parcial. Reflexao foi instrumento de investigacao fora do produto; dentro do
  probe seria invencao de API.

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

SCRIPT_NAME = "42_recon_tasks_readonly.py"
SCHEMA_VERSION = "1.0"

# --- as cadeias, LITERAIS, como constantes do modulo -------------------------
#
# Escritas UMA vez e levadas ao artefato. Um artefato que mostra o valor sem
# mostrar por onde ele veio nao permite auditar a leitura depois.
STUB_PATH = ("C:\\Program Files\\Altus\\MT9000 4.1.0\\MT9000\\ScriptLib\\"
             "Stubs\\scriptengine\\ScriptTaskConfigObject.pyi")

MARKER_CHAIN_TASK_CONFIG = (
    "projects.primary -> get_children(False) -> node.is_task_configuration")

MARKER_CHAIN_TASK = "projects.primary -> get_children(False) -> node.is_task"

MARKER_CHAIN_SOURCE = (
    "stub oficial versionado pelo produto '%s': linhas 21-22 "
    "(ScriptTaskConfigObjectMarker.is_task_configuration -> bool) e 39-40 "
    "(ScriptTaskObjectMarker.is_task -> bool), ambas descritas como 'Every "
    "ScriptObject instance will be extended with this method', version added "
    "3.5.10.0. Os nos sao reconhecidos por TIPO: nome de no e rotulo de "
    "interface, depende do idioma do projeto e nao serve de identificador -- "
    "foi por nome que a run-011 procurou biblioteca no lugar errado "
    "(docs/36)." % (STUB_PATH,)
)

TASK_FIELDS_CHAIN = ("task.name / kind_of_task / priority / interval / "
                     "interval_unit / watchdog")

TASK_FIELDS_SOURCE = (
    "stub oficial '%s': L75-82 name (str), L84-91 kind_of_task (enum "
    "KindOfTask, L5-11: Cyclic=1, Freewheeling=2, Event=3, ExternalEvent=4, "
    "Status=5, ParentSynchron=6), L106-113 priority (str), L119-129 interval "
    "(str, exige kind_of_task Cyclic ou ExternalEvent), L135-144 "
    "interval_unit (str), L150-157 watchdog (ScriptWatchdog)." % (STUB_PATH,)
)

WATCHDOG_FIELDS_CHAIN = ("task.watchdog -> enabled / time / time_unit / "
                         "sensitivity")

WATCHDOG_FIELDS_SOURCE = (
    "stub oficial '%s' L228-285: ScriptWatchdog.enabled (bool), .time (str), "
    ".time_unit (str), .sensitivity (str)." % (STUB_PATH,)
)

POUS_CHAIN = "task.pous -> len(pous) -> pous[i] -> (name, comment)"

POUS_SOURCE = (
    "stub oficial '%s': L218-225 ScriptTaskObject.pous -> "
    "ScriptPouObjectCollection ('Collection of POUs which are executed by the "
    "task'); L288-293 a colecao HERDA de list; L346-353 __len__ -> int; "
    "L355-365 __getitem__(index) devolve 'the name and the comment of the "
    "entry at the specifed index as a python tuple', tuple[str, str]. E ESTA "
    "lista que materializa o Program Call: um PROGRAM que nao esta nela nao e "
    "executado pelo CLP." % (STUB_PATH,)
)

# A relacao "esta task esta dentro daquela Task Configuration" e DERIVADA do
# caminho de indices, e nao lida de acessor nenhum: o stub nao cataloga
# `ScriptTaskConfigObject.tasks`. Dizer isso em cada artefato evita que a
# proxima pessoa leia derivacao como leitura direta -- foi a mesma precaucao
# tomada com a versao derivada do nome de biblioteca (probe 41).
CONTAINMENT_SOURCE = (
    "DERIVADA do caminho de indices da varredura (prefixo de node_id), nunca "
    "lida de acessor: o stub nao cataloga colecao de tasks a partir de "
    "ScriptTaskConfigObject. Derivacao NAO e leitura direta."
)

# --- modos -------------------------------------------------------------------
#
# `recon` mede o estado; `postsave` confere um vinculo especifico DEPOIS de o
# projeto ter sido salvo e REABERTO. A segunda existe porque vincular em
# memoria nao prova nada: o criterio do marco e que o vinculo PERSISTA.
MODE_RECON = "recon"
MODE_POSTSAVE = "postsave"
VALID_MODES = (MODE_RECON, MODE_POSTSAVE)

# --- limites de varredura ----------------------------------------------------
#
# Limite infinito nao e oferecido: uma arvore ciclica ou um defeito de
# navegacao viraria varredura infinita dentro de uma sessao supervisionada.
MAX_DEPTH = 8
MAX_TOTAL_NODES = 5000
MAX_CHILDREN_PER_NODE = 256
MAX_POUS_PER_TASK = 256
MAX_TASKS = 256

# --- vocabulario fechado -----------------------------------------------------
STATUS_MEASURED = "measured"
STATUS_PARTIAL = "partial"
STATUS_UNRESOLVED = "unresolved"
STATUS_BINDING_VERIFIED = "binding_verified"
STATUS_BINDING_MISSING = "binding_missing"
STATUS_FATAL = "fatal"

ALL_STATUSES = (STATUS_MEASURED, STATUS_PARTIAL, STATUS_UNRESOLVED,
                STATUS_BINDING_VERIFIED, STATUS_BINDING_MISSING, STATUS_FATAL)
SUCCESS_STATUSES = (STATUS_MEASURED, STATUS_BINDING_VERIFIED)

# `partial` = as tasks foram alcancadas, mas algum campo OBRIGATORIO (nome ou
# lista de POUs) nao pode ser lido em pelo menos uma delas. Ha medida, e ela
# esta incompleta -- e incompleta nao sai com 0.
EXIT_BY_STATUS = {
    STATUS_MEASURED: 0,
    STATUS_BINDING_VERIFIED: 0,
    STATUS_UNRESOLVED: 2,
    STATUS_BINDING_MISSING: 3,
    STATUS_PARTIAL: 4,
    STATUS_FATAL: 1,
}

# Razoes fechadas de lacuna. Cada uma diz ONDE a leitura parou -- "nao deu" sem
# o passo culpado obriga a repetir a sessao supervisionada so para descobrir.
REASON_NO_PROJECT = "sem projeto primario"
REASON_NO_TASK_NODE = (
    "nenhum no com is_task == True foi encontrado na arvore varrida. Sem task "
    "nao ha o que executar o PROGRAM: o projeto compila e o CLP nao roda nada")
REASON_WALK_TRUNCATED = (
    "a varredura atingiu o limite de nos antes de terminar; nos de task podem "
    "ter ficado fora")
REASON_FIELD_RAISED = "a leitura do campo levantou"
REASON_FIELD_NONE = (
    "a leitura respondeu e devolveu None -- o produto nao definiu valor para "
    "este campo nesta task (o stub condiciona interval e interval_unit a "
    "kind_of_task Cyclic ou ExternalEvent)")
REASON_TASK_NAME_UNREADABLE = (
    "ha task cujo nome nao pode ser lido; sem nome nao se sabe A QUAL task um "
    "Program Call seria acrescentado")
REASON_POUS_UNREADABLE = (
    "ha task cuja lista de POUs nao pode ser lida; e justamente essa lista que "
    "diz se o PROGRAM e executado")
REASON_TASK_NOT_FOUND = "nenhuma task marcada por is_task tem o nome esperado"
REASON_TASK_AMBIGUOUS = (
    "mais de uma task marcada por is_task tem o nome esperado; vincular a "
    "'uma delas' seria escolher por acaso")
REASON_POU_NOT_BOUND = (
    "a task existe e a lista de POUs foi lida, e o PROGRAM esperado NAO esta "
    "nela: o vinculo nao persistiu")

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

def build_evidence(value, source, reason):
    """Evidencia no MESMO formato fechado ja usado para a compiler version e
    para o inventario de bibliotecas.

    Duas formas e nenhuma terceira. `measured` exige valor; `unresolved` exige
    valor None E razao escrita. Um valor ausente marcado como `measured` seria
    pior que a lacuna, porque a lacuna ao menos se anuncia.

    Lista VAZIA e valor, e nao ausencia: uma task sem Program Call e o estado
    inicial esperado, e essa e a grandeza que este probe mede.
    """
    if value is None:
        return {
            "status": EVIDENCE_UNRESOLVED,
            "value": None,
            "source": source,
            "reason": reason or REASON_FIELD_RAISED,
        }
    return {
        "status": EVIDENCE_MEASURED,
        "value": value,
        "source": source,
        "reason": None,
    }


def field_evidence(value, error_repr, source):
    """Evidencia de UM campo, distinguindo as duas ausencias.

    "A leitura levantou" e "a leitura respondeu None" nao sao a mesma coisa: a
    primeira e defeito ou API indisponivel, a segunda e o produto dizendo que
    aquele campo nao se aplica aqui (o stub condiciona `interval` ao
    `kind_of_task`). Colapsar as duas num `None` mudo obrigaria a proxima
    pessoa a reabrir o MasterTool para descobrir qual das duas aconteceu.
    """
    if error_repr:
        return build_evidence(None, source,
                              "%s: %s" % (REASON_FIELD_RAISED, error_repr))
    if value is None:
        return build_evidence(None, source, REASON_FIELD_NONE)
    return build_evidence(value, source, None)


def as_text(value):
    """Texto do CLR normalizado para o tipo textual do interpretador.

    Devolve None para vazio: string em branco vinda do produto nao e nome nem
    unidade, e deixa-la passar produziria uma linha que parece medida e nao
    identifica nada.
    """
    if value is None:
        return None
    if isinstance(value, _STRING_TYPES):
        texto = value.strip()
        return texto or None
    try:
        texto = str(value).strip()
    except Exception:                                              # noqa: BLE001
        return None
    return texto or None


def is_inside(node_id, container_node_id):
    """Contencao DERIVADA do caminho de indices: `root/1/0` contem
    `root/1/0/2`. Prefixo com barra, nunca prefixo textual solto -- senao
    `root/1` "conteria" `root/10`.
    """
    if not node_id or not container_node_id:
        return False
    return node_id.startswith(container_node_id + "/")


def summarize_task(task_entry):
    """Uma linha de resumo por task, com o que decide o marco: o nome e o que
    ela ja executa."""
    nome = (task_entry.get("name") or {}).get("value")
    pous = (task_entry.get("pous") or {}).get("value")
    return {
        "node_id": task_entry.get("node_id"),
        "name": nome,
        "pous_count": len(pous) if pous is not None else None,
        "pous_names": [item.get("name") for item in (pous or [])],
        "within_task_configuration": task_entry.get("within_task_configuration"),
    }


def find_task_by_name(tasks, expected_name):
    """`(task, razao)`. A task e escolhida entre nos que o MARCADOR ja provou
    serem tasks; o nome so desempata dentro desse conjunto.

    Isso nao contradiz "nunca por nome": o TIPO decide o que E task, e o nome
    decide QUAL delas -- e para essa segunda pergunta nao existe outro
    discriminador catalogado. Ambiguidade nao e resolvida por ordem de
    varredura: duas tasks com o mesmo nome param o probe.
    """
    if not expected_name:
        return None, REASON_TASK_NOT_FOUND
    encontradas = []
    for task_entry in tasks or []:
        if (task_entry.get("name") or {}).get("value") == expected_name:
            encontradas.append(task_entry)
    if not encontradas:
        return None, REASON_TASK_NOT_FOUND
    if len(encontradas) > 1:
        return None, REASON_TASK_AMBIGUOUS
    return encontradas[0], None


def check_binding(tasks, expected_task, expected_pou):
    """O vinculo esperado esta na lista de POUs da task esperada?

    Devolve um bloco serializavel. `bound` so e True quando a task foi achada
    sem ambiguidade, a lista foi LIDA e o nome esta nela -- lista ilegivel nao
    vira "nao vinculado", vira lacuna com razao propria.
    """
    resultado = {
        "expected_task": expected_task,
        "expected_pou": expected_pou,
        "task_found": False,
        "task_node_id": None,
        "pous_readable": False,
        "pous_names": [],
        "position": None,
        "bound": False,
        "reason": None,
    }
    task_entry, razao = find_task_by_name(tasks, expected_task)
    if task_entry is None:
        resultado["reason"] = razao
        return resultado
    resultado["task_found"] = True
    resultado["task_node_id"] = task_entry.get("node_id")

    evidencia_pous = task_entry.get("pous") or {}
    if evidencia_pous.get("status") != EVIDENCE_MEASURED:
        resultado["reason"] = evidencia_pous.get("reason") or REASON_POUS_UNREADABLE
        return resultado
    resultado["pous_readable"] = True
    nomes = [item.get("name") for item in (evidencia_pous.get("value") or [])]
    resultado["pous_names"] = nomes
    indice = 0
    for nome in nomes:
        if nome == expected_pou:
            resultado["position"] = indice
            resultado["bound"] = True
            return resultado
        indice = indice + 1
    resultado["reason"] = REASON_POU_NOT_BOUND
    return resultado


def classify(mode, evidence, tasks, binding):
    """Status DERIVADO da evidencia, nunca declarado a mao."""
    if (evidence or {}).get("status") != EVIDENCE_MEASURED:
        return STATUS_UNRESOLVED
    incompleta = False
    for task_entry in tasks or []:
        if (task_entry.get("name") or {}).get("status") != EVIDENCE_MEASURED:
            incompleta = True
        if (task_entry.get("pous") or {}).get("status") != EVIDENCE_MEASURED:
            incompleta = True
    if mode == MODE_POSTSAVE:
        if (binding or {}).get("bound"):
            return STATUS_BINDING_VERIFIED
        return STATUS_BINDING_MISSING
    if incompleta:
        return STATUS_PARTIAL
    return STATUS_MEASURED


# =============================================================================
# orquestracao -- unica parte que toca o MasterTool
# =============================================================================

def read_is_task_configuration(node):
    """`node.is_task_configuration` -- marcador de TIPO. `(bool, erro)`."""
    try:
        marcado = node.is_task_configuration
    except Exception as exc:                                       # noqa: BLE001
        return False, "is_task_configuration falhou: %r" % (exc,)
    return bool(marcado), None


def read_is_task(node):
    """`node.is_task` -- marcador de TIPO. `(bool, erro)`."""
    try:
        marcado = node.is_task
    except Exception as exc:                                       # noqa: BLE001
        return False, "is_task falhou: %r" % (exc,)
    return bool(marcado), None


def read_node_name(node):
    """Nome do no, so para o registro. Nunca usado para ACHAR o no."""
    try:
        return as_text(node.get_name(False))
    except Exception:                                              # noqa: BLE001
        return None


def read_children(node):
    """`get_children(False)` -> `Count` -> indexador. A MESMA cadeia ja
    confirmada pelos probes 05-10 e usada pelo scanner read-only. Devolve
    `(lista_de_filhos, erro)` e nunca levanta.
    """
    try:
        colecao = node.get_children(False)
    except Exception as exc:                                       # noqa: BLE001
        return [], "get_children falhou: %r" % (exc,)
    if colecao is None:
        return [], "get_children devolveu None"
    try:
        total = colecao.Count
    except Exception as exc:                                       # noqa: BLE001
        return [], "Count falhou: %r" % (exc,)
    if total is None or total < 0 or total > MAX_CHILDREN_PER_NODE:
        return [], "Count fora de faixa: %r" % (total,)
    filhos = []
    for indice in range(total):
        try:
            filhos.append(colecao[indice])
        except Exception as exc:                                   # noqa: BLE001
            return filhos, "indexador falhou em %d: %r" % (indice, exc)
    return filhos, None


def collect_marked_nodes(project):
    """Varredura DFS iterativa com pilha explicita, procurando os DOIS
    marcadores de tipo na mesma passada.

    Nunca por nome. Os achados carregam o proxy do no; tudo o mais e
    serializavel.
    """
    varredura = {"visited": 0, "truncated": False, "errors": []}
    configuracoes = []
    tasks = []
    if project is None:
        varredura["errors"].append(REASON_NO_PROJECT)
        return configuracoes, tasks, varredura

    pilha = [(project, "root", 0)]
    visitados = 0
    while pilha:
        if visitados >= MAX_TOTAL_NODES:
            varredura["truncated"] = True
            break
        no_atual, node_id, profundidade = pilha.pop()
        visitados += 1

        if node_id != "root":
            marcado_config, erro_config = read_is_task_configuration(no_atual)
            if erro_config:
                varredura["errors"].append("%s: %s" % (node_id, erro_config))
            elif marcado_config:
                configuracoes.append({"node_id": node_id,
                                      "name": read_node_name(no_atual)})
            marcado_task, erro_task = read_is_task(no_atual)
            if erro_task:
                varredura["errors"].append("%s: %s" % (node_id, erro_task))
            elif marcado_task and len(tasks) < MAX_TASKS:
                tasks.append({"node_id": node_id, "node": no_atual})

        if profundidade >= MAX_DEPTH:
            continue
        filhos, erro_filhos = read_children(no_atual)
        if erro_filhos:
            varredura["errors"].append("%s: %s" % (node_id, erro_filhos))
        # Empilhados em ordem reversa para que o `pop()` os processe na ordem
        # crescente de indice, igual ao scanner read-only.
        indice = len(filhos) - 1
        while indice >= 0:
            pilha.append((filhos[indice], "%s/%d" % (node_id, indice),
                          profundidade + 1))
            indice -= 1

    varredura["visited"] = visitados
    return configuracoes, tasks, varredura


def read_watchdog(task):
    """Os QUATRO campos do watchdog, cada um no seu proprio `try`.

    Devolve um dicionario `campo -> (valor, erro)`. Um campo que falha nao pode
    levar junto os outros tres.
    """
    try:
        watchdog = task.watchdog
        erro_watchdog = None
    except Exception as exc:                                       # noqa: BLE001
        watchdog = None
        erro_watchdog = repr(exc)
    if watchdog is None:
        motivo = erro_watchdog or "task.watchdog devolveu None"
        return {"enabled": (None, motivo), "time": (None, motivo),
                "time_unit": (None, motivo), "sensitivity": (None, motivo)}

    campos = {}
    try:
        campos["enabled"] = (bool(watchdog.enabled), None)
    except Exception as exc:                                       # noqa: BLE001
        campos["enabled"] = (None, repr(exc))
    try:
        campos["time"] = (as_text(watchdog.time), None)
    except Exception as exc:                                       # noqa: BLE001
        campos["time"] = (None, repr(exc))
    try:
        campos["time_unit"] = (as_text(watchdog.time_unit), None)
    except Exception as exc:                                       # noqa: BLE001
        campos["time_unit"] = (None, repr(exc))
    try:
        campos["sensitivity"] = (as_text(watchdog.sensitivity), None)
    except Exception as exc:                                       # noqa: BLE001
        campos["sensitivity"] = (None, repr(exc))
    return campos


def read_pous(task):
    """A LISTA DE PROGRAM CALLS. Somente leitura: `len(...)` e o indexador.

    Nao ha uma unica chamada de metodo sobre esta colecao, e a razao esta na
    docstring do modulo: `ScriptPouObjectCollection` herda de `list`, e os seus
    mutadores se chamam `add`, `insert`, `remove` e `replace`.

    Devolve `(entradas, erro)`. Lista vazia e MEDIDA, nao lacuna.
    """
    try:
        colecao = task.pous
    except Exception as exc:                                       # noqa: BLE001
        return None, "task.pous falhou: %r" % (exc,)
    if colecao is None:
        return None, "task.pous devolveu None"
    try:
        total = len(colecao)
    except Exception as exc:                                       # noqa: BLE001
        return None, "len(pous) falhou: %r" % (exc,)
    if total is None or total < 0:
        return None, "len(pous) fora de faixa: %r" % (total,)
    if total > MAX_POUS_PER_TASK:
        # Lacuna, e nao lista parcial: uma lista cortada pela metade que saisse
        # como MEDIDA poderia "provar" que o PROGRAM nao esta vinculado quando
        # ele esta na posicao seguinte a do corte.
        return None, ("len(pous) = %d excede o limite de %d deste probe; a "
                      "lista NAO e devolvida pela metade"
                      % (total, MAX_POUS_PER_TASK))
    entradas = []
    for indice in range(total):
        try:
            item = colecao[indice]
        except Exception as exc:                                   # noqa: BLE001
            return None, "pous[%d] falhou: %r" % (indice, exc)
        # O stub (L355-365) diz que o item e uma tupla Python `(name,
        # comment)`. Nao ha segunda forma catalogada, e por isso nao ha
        # tentativa alternativa: se a desestruturacao falhar, isso e ACHADO --
        # a forma real do item passa a ser grandeza a medir, e nao algo a
        # adivinhar dentro de um `except`.
        try:
            nome = as_text(item[0])
            comentario = as_text(item[1])
        except Exception as exc:                                   # noqa: BLE001
            return None, ("pous[%d] nao e a tupla (name, comment) que o stub "
                          "documenta: %r" % (indice, exc))
        entradas.append({"index": indice, "name": nome, "comment": comentario})
    return entradas, None


def read_task_entry(task_node, node_id, configuracoes):
    """Todos os campos pedidos pelo contrato de saida, um por `try`.

    Campo ilegivel vira LACUNA EXPLICITA com o `repr` da excecao, nunca `None`
    mudo: um `None` sem razao obriga a reabrir o MasterTool so para descobrir
    se o campo nao existe, nao se aplica ou quebrou.
    """
    try:
        nome = as_text(task_node.name)
        erro_nome = None
    except Exception as exc:                                       # noqa: BLE001
        nome = None
        erro_nome = repr(exc)
    try:
        especie = as_text(task_node.kind_of_task)
        erro_especie = None
    except Exception as exc:                                       # noqa: BLE001
        especie = None
        erro_especie = repr(exc)
    try:
        prioridade = as_text(task_node.priority)
        erro_prioridade = None
    except Exception as exc:                                       # noqa: BLE001
        prioridade = None
        erro_prioridade = repr(exc)
    try:
        intervalo = as_text(task_node.interval)
        erro_intervalo = None
    except Exception as exc:                                       # noqa: BLE001
        intervalo = None
        erro_intervalo = repr(exc)
    try:
        unidade = as_text(task_node.interval_unit)
        erro_unidade = None
    except Exception as exc:                                       # noqa: BLE001
        unidade = None
        erro_unidade = repr(exc)

    watchdog = read_watchdog(task_node)
    entradas, erro_pous = read_pous(task_node)

    dentro_de = None
    for configuracao in configuracoes or []:
        if is_inside(node_id, configuracao.get("node_id")):
            dentro_de = configuracao.get("node_id")
            break

    return {
        "node_id": node_id,
        "name": field_evidence(nome, erro_nome, TASK_FIELDS_SOURCE),
        "kind_of_task": field_evidence(especie, erro_especie, TASK_FIELDS_SOURCE),
        "priority": field_evidence(prioridade, erro_prioridade, TASK_FIELDS_SOURCE),
        "interval": field_evidence(intervalo, erro_intervalo, TASK_FIELDS_SOURCE),
        "interval_unit": field_evidence(unidade, erro_unidade, TASK_FIELDS_SOURCE),
        "watchdog": {
            "enabled": field_evidence(watchdog["enabled"][0],
                                      watchdog["enabled"][1],
                                      WATCHDOG_FIELDS_SOURCE),
            "time": field_evidence(watchdog["time"][0], watchdog["time"][1],
                                   WATCHDOG_FIELDS_SOURCE),
            "time_unit": field_evidence(watchdog["time_unit"][0],
                                        watchdog["time_unit"][1],
                                        WATCHDOG_FIELDS_SOURCE),
            "sensitivity": field_evidence(watchdog["sensitivity"][0],
                                          watchdog["sensitivity"][1],
                                          WATCHDOG_FIELDS_SOURCE),
        },
        "pous": field_evidence(entradas, erro_pous, POUS_SOURCE),
        "pous_count": len(entradas) if entradas is not None else None,
        "within_task_configuration": dentro_de,
        "containment_source": CONTAINMENT_SOURCE,
    }


def read_recon(project):
    """Orquestra a varredura e a leitura de todas as tasks. Nunca levanta.

    Devolve `(evidencia, detalhe)`.
    """
    configuracoes, tasks_brutas, varredura = collect_marked_nodes(project)
    detalhe = {
        "walk": varredura,
        "task_configuration_nodes": configuracoes,
        "tasks": [],
        "chain_steps": [],
    }
    passos = detalhe["chain_steps"]

    if project is None:
        passos.append({"step": "projects.primary", "ok": False,
                       "detail": REASON_NO_PROJECT})
        return (build_evidence(None, MARKER_CHAIN_SOURCE, REASON_NO_PROJECT),
                detalhe)
    passos.append({"step": "projects.primary", "ok": True, "detail": None})

    passos.append({"step": MARKER_CHAIN_TASK_CONFIG,
                   "ok": bool(configuracoes),
                   "detail": "%d no(s) marcado(s)" % (len(configuracoes),)})

    if not tasks_brutas:
        razao = REASON_WALK_TRUNCATED if varredura["truncated"] else REASON_NO_TASK_NODE
        passos.append({"step": MARKER_CHAIN_TASK, "ok": False, "detail": razao})
        return (build_evidence(None, MARKER_CHAIN_SOURCE, razao), detalhe)
    passos.append({"step": MARKER_CHAIN_TASK, "ok": True,
                   "detail": "%d task(s) marcada(s)" % (len(tasks_brutas),)})

    tasks = []
    for bruta in tasks_brutas:
        entrada = read_task_entry(bruta["node"], bruta["node_id"], configuracoes)
        tasks.append(entrada)
        passos.append({"step": "%s @ %s" % (POUS_CHAIN, bruta["node_id"]),
                       "ok": (entrada["pous"] or {}).get("status") == EVIDENCE_MEASURED,
                       "detail": (entrada["pous"] or {}).get("reason")})
    detalhe["tasks"] = tasks

    # ZERO POUS NAO E LACUNA -- ver a docstring do modulo. A evidencia da
    # varredura e a LISTA DE TASKS; o que cada task executa e evidencia propria
    # dentro dela.
    return (build_evidence(tasks, MARKER_CHAIN_SOURCE, None), detalhe)


def resolve_mode(argv, probe_cli, problems):
    """Modo explicito, com default `recon`. Nome desconhecido falha fechado."""
    bruto = probe_cli.find_arg(argv, "mode")
    if bruto is None or bruto == "":
        return MODE_RECON
    if bruto == MODE_RECON:
        return MODE_RECON
    if bruto == MODE_POSTSAVE:
        return MODE_POSTSAVE
    problems.append("--mode invalido: %r (validos: %s)"
                    % (bruto, ", ".join(VALID_MODES)))
    return None


def run_probe(script_globals, argv, project_access, file_io, probe_cli, now=None):
    """Orquestra. Nunca levanta: toda falha vira status + problema escrito."""
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
        "project": {"path": None},
        "marker_chain_task_configuration": MARKER_CHAIN_TASK_CONFIG,
        "marker_chain_task": MARKER_CHAIN_TASK,
        "marker_chain_source": MARKER_CHAIN_SOURCE,
        "task_fields_chain": TASK_FIELDS_CHAIN,
        "watchdog_fields_chain": WATCHDOG_FIELDS_CHAIN,
        "pous_chain": POUS_CHAIN,
        "tasks": build_evidence(None, MARKER_CHAIN_SOURCE, REASON_NO_PROJECT),
        "task_summaries": [],
        "task_configuration_nodes": [],
        "binding": None,
        "walk": {},
        "chain_steps": [],
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
    mode = resolve_mode(argv, probe_cli, problems)
    result["mode"] = mode

    expected_task = probe_cli.find_arg(argv, "expect-task")
    expected_pou = probe_cli.find_arg(argv, "expect-pou")
    if mode == MODE_POSTSAVE:
        if not expected_task:
            problems.append("--expect-task e obrigatorio em --mode=postsave: "
                            "conferir vinculo exige saber QUAL task")
        if not expected_pou:
            problems.append("--expect-pou e obrigatorio em --mode=postsave: "
                            "conferir vinculo exige saber QUAL PROGRAM")
    if problems:
        for problema in problems:
            result["problems"].append(problema)
        return finish(STATUS_FATAL)
    result["artifacts_dir"] = artifacts_dir

    result["runtime"] = probe_cli.runtime_identity()

    project, access_error = project_access.get_primary_project(script_globals)
    if project is None:
        result["problems"].append("sem projeto primario: %s" % (access_error,))
        evidencia, detalhe = read_recon(None)
        result["tasks"] = evidencia
        result["walk"] = detalhe["walk"]
        result["chain_steps"] = detalhe["chain_steps"]
        return finish(STATUS_FATAL)

    result["project"]["path"] = project_access.get_project_path(project)

    evidencia, detalhe = read_recon(project)
    result["tasks"] = evidencia
    result["task_configuration_nodes"] = detalhe["task_configuration_nodes"]
    result["walk"] = detalhe["walk"]
    result["chain_steps"] = detalhe["chain_steps"]
    tasks = evidencia.get("value") or []
    result["task_summaries"] = [summarize_task(item) for item in tasks]

    binding = None
    if mode == MODE_POSTSAVE:
        binding = check_binding(tasks, expected_task, expected_pou)
        result["binding"] = binding

    if evidencia["status"] != EVIDENCE_MEASURED:
        result["problems"].append(
            "tasks nao medidas pela cadeia %s: %s"
            % (MARKER_CHAIN_TASK, evidencia["reason"]))
    else:
        for item in tasks:
            if (item.get("name") or {}).get("status") != EVIDENCE_MEASURED:
                result["problems"].append(
                    "%s: %s" % (item.get("node_id"), REASON_TASK_NAME_UNREADABLE))
            if (item.get("pous") or {}).get("status") != EVIDENCE_MEASURED:
                result["problems"].append(
                    "%s: %s (%s)" % (item.get("node_id"), REASON_POUS_UNREADABLE,
                                     (item.get("pous") or {}).get("reason")))
    if binding is not None and not binding.get("bound"):
        result["problems"].append(
            "vinculo NAO confirmado apos a reabertura: task %r, PROGRAM %r -- %s"
            % (binding.get("expected_task"), binding.get("expected_pou"),
               binding.get("reason")))

    return finish(classify(mode, evidencia, tasks, binding))


# =============================================================================
# artefatos
# =============================================================================

def build_completion(result):
    """Artefato de conclusao. E ELE que o wrapper le para dar veredito."""
    evidencia = result.get("tasks") or {}
    tasks = evidencia.get("value") or []
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": result.get("mode"),
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "project": result.get("project"),
        "tasks": evidencia,
        "tasks_count": len(tasks),
        "task_summaries": result.get("task_summaries"),
        "task_configuration_nodes": result.get("task_configuration_nodes"),
        "binding": result.get("binding"),
        "binding_verified": bool((result.get("binding") or {}).get("bound")),
        "marker_chain_task_configuration": result.get("marker_chain_task_configuration"),
        "marker_chain_task": result.get("marker_chain_task"),
        "marker_chain_source": result.get("marker_chain_source"),
        "pous_chain": result.get("pous_chain"),
        "chain_steps": result.get("chain_steps"),
        "runtime": result.get("runtime"),
        "errors": result.get("problems"),
        "mutating_calls": result.get("mutating_calls"),
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    evidencia = result.get("tasks") or {}
    tasks = evidencia.get("value") or []
    lines = [
        "# Probe 42 - reconhecimento read-only de Task Configuration",
        "",
        "Somente leitura. Nenhuma API mutavel existe neste probe.",
        "",
        "- modo: **%s**" % result.get("mode"),
        "- status: **%s**" % result.get("status"),
        "- exit_code logico: **%s**" % result.get("exit_code"),
        "- projeto: `%s`" % (result.get("project") or {}).get("path"),
        "- marcador da task config: `%s`"
        % result.get("marker_chain_task_configuration"),
        "- marcador da task: `%s`" % result.get("marker_chain_task"),
        "- cadeia do Program Call: `%s`" % result.get("pous_chain"),
        "- evidencia: `%s` (razao: %s)" % (evidencia.get("status"),
                                           evidencia.get("reason")),
        "- tasks medidas: **%d**" % len(tasks),
        "",
        "## Nos de Task Configuration (por is_task_configuration)",
        "",
    ]
    for no_marcado in result.get("task_configuration_nodes") or []:
        lines.append("- `%s` (%s)"
                     % (no_marcado.get("node_id"), no_marcado.get("name")))
    if not (result.get("task_configuration_nodes") or []):
        lines.append("- nenhum")
    lines.append("")
    lines.append("## Tasks (por is_task)")
    lines.append("")
    for task_entry in tasks:
        watchdog = task_entry.get("watchdog") or {}
        lines.append(
            "- `%s` nome=`%s` (%s) | kind=`%s` | prioridade=`%s` | "
            "intervalo=`%s` `%s` | watchdog: enabled=`%s` time=`%s` `%s` "
            "sensitivity=`%s` | dentro de `%s`"
            % (task_entry.get("node_id"),
               (task_entry.get("name") or {}).get("value"),
               (task_entry.get("name") or {}).get("status"),
               (task_entry.get("kind_of_task") or {}).get("value"),
               (task_entry.get("priority") or {}).get("value"),
               (task_entry.get("interval") or {}).get("value"),
               (task_entry.get("interval_unit") or {}).get("value"),
               (watchdog.get("enabled") or {}).get("value"),
               (watchdog.get("time") or {}).get("value"),
               (watchdog.get("time_unit") or {}).get("value"),
               (watchdog.get("sensitivity") or {}).get("value"),
               task_entry.get("within_task_configuration")))
        evidencia_pous = task_entry.get("pous") or {}
        entradas = evidencia_pous.get("value")
        if entradas is None:
            lines.append("  - Program Call: LACUNA -- %s"
                         % evidencia_pous.get("reason"))
        elif not entradas:
            lines.append("  - Program Call: NENHUM (medido: a task nao executa "
                         "POU algum)")
        else:
            for entrada in entradas:
                lines.append("  - Program Call [%s]: `%s` (comentario: %s)"
                             % (entrada.get("index"), entrada.get("name"),
                                entrada.get("comment")))
    if not tasks:
        lines.append("- nenhuma")
    lines.append("")
    binding = result.get("binding")
    if binding is not None:
        lines.append("## Conferencia do vinculo (modo postsave)")
        lines.append("")
        lines.append("- task esperada: `%s`" % binding.get("expected_task"))
        lines.append("- PROGRAM esperado: `%s`" % binding.get("expected_pou"))
        lines.append("- vinculado: **%s** (posicao: %s)"
                     % (binding.get("bound"), binding.get("position")))
        lines.append("- razao: %s" % binding.get("reason"))
        lines.append("")
    lines.append("## Passos")
    lines.append("")
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
    file_io.write_json(os.path.join(artifacts_dir, "tasks-analysis.json"), result)
    written.append("tasks-analysis.json")
    file_io.write_text(os.path.join(artifacts_dir, "tasks-report.md"),
                       build_report_markdown(result))
    written.append("tasks-report.md")
    file_io.write_json(os.path.join(artifacts_dir, "tasks-completion.json"),
                       build_completion(result))
    written.append("tasks-completion.json")
    return written


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s - SOMENTE LEITURA" % SCRIPT_NAME)
    print("[INFO] marcadores: %s | %s" % (MARKER_CHAIN_TASK_CONFIG,
                                          MARKER_CHAIN_TASK))
    print("[INFO] campos    : %s | %s" % (TASK_FIELDS_CHAIN,
                                          WATCHDOG_FIELDS_CHAIN))
    print("[INFO] Program Call: %s" % POUS_CHAIN)
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
    print("[INFO] tasks=%d" % len((result.get("tasks") or {}).get("value") or []))
    for problema in result.get("problems") or []:
        print("[PROBLEM] %s" % problema)
    print("=" * 68)

    # ENCERRA O MASTERTOOL, e so DEPOIS de os artefatos estarem no disco.
    #
    # `CloseMainWindow()` nao basta: o MasterTool marca o projeto como alterado
    # so de abrir (medido em W1.5), entao o pedido de fechar cai num dialogo
    # modal de salvar e a janela NAO fecha sozinha -- na run-019 o operador teve
    # de clicar "Nao" tres vezes seguidas.
    #
    # `system.exit()` "shuts down the engine and exits the process"
    # (ScriptSystem.pyi L143-157) -- encerra sem passar pelo dialogo, porque nao
    # ha pedido de fechamento de janela a ser respondido. NAO e `Stop-Process`
    # disfarcado: aquilo mata o processo de fora e pode interromper gravacao de
    # artefato; isto e o proprio produto se encerrando, por API documentada,
    # com os artefatos JA gravados acima.
    _encerrar_plataforma(script_globals)
    return result.get("exit_code")


def _encerrar_plataforma(script_globals):
    """Chama `system.exit(0)` se o global existir. Nunca levanta.

    O codigo de saida do probe ja foi decidido e gravado no artefato; este
    encerramento e sobre a JANELA, e nao sobre o veredito. Passar o exit_code
    aqui confundiria as duas coisas -- e o launcher, por contrato, nunca decide
    nada pelo exit code.
    """
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
        print("[INFO] system.exit falhou (%r): feche a janela manualmente." % (exc,))


if "projects" in globals():
    sys.exit(main())

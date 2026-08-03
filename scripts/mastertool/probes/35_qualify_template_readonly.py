# -*- coding: utf-8 -*-
r"""35_qualify_template_readonly.py - qualificacao SOMENTE LEITURA de um
projeto-base candidato a template (`TemplateExemplo v1.project`), precondicao de W1.4.

Contrato: docs/28. Plano: docs/32 (Sprint 5.2/5.4 do plano "MasterTool X
Project Factory").

VEREDITO SOBRE `probes/21_scan_project_tree_full.py` (registrado aqui porque
decide a existencia deste arquivo): probe 21 ja congela SHA-256 do projeto
(linhas 100-109 e 216-218 de probe 21), tamanho e limites (docs/22), a arvore
completa por navegacao DFS iterativa com isolamento de erro por no (usa
`common.read_only_project_scanner.ReadOnlyProjectScanner`, linhas 228-233),
`node_path`/`type_guid`/`name`/`object_guid` por no (`flatten_tree`,
`read_only_project_scanner.py` linhas 565-591) e indices auxiliares por nome e
por type_guid (`build_node_indexes`, linhas 594-611). Isso ja cobre
estruturalmente `Application`, `Plc Logic`, containers IEC, tasks, Program
Calls, GVLs, PROGRAMs, FUNCTION_BLOCKs, FUNCTIONs, DUTs, dispositivos e
cartoes de I/O -- todos aparecem como nos genericos com nome e type_guid.

O que falta, e por isso este arquivo existe como CLASSIFICADOR DE SEGUNDA
PASSAGEM sobre a MESMA saida do scanner (nunca um segundo caminhador de
arvore):

  1. resolver o `Application` POR BUSCA (nome + type_guid) e reportar o
     `node_path` encontrado -- probe 21 nao faz isso, so enumera;
  2. classificar type_guids conhecidos (Application/GVL/POU/Device) contra o
     catalogo medido, e declarar como `unclassified` qualquer outro -- probe
     21 devolve o type_guid cru, sem classificacao;
  3. detectar conflito de nome com `GVL_AI_TESTE`/`PRG_AI_TESTE` -- ausente
     em probe 21;
  4. derivar `libraries` e `tasks` a partir dos filhos dos nos "Library
     Manager"/"Task Configuration" -- usando SOMENTE os dados que o scanner ja
     produziu (parent_node_id/name em flat-nodes.json), sem nenhuma chamada
     adicional ao MasterTool;
  5. calcular um hash deterministico da arvore persistente
     (`persistent_tree_sha256`) -- inexistente em qualquer script do
     repositorio (so citado em docs/18 como `structure_sha256`, nunca
     implementado);
  6. emitir o candidato de registry de template do Sprint 5.4.

O que este arquivo NAO determina, por falta de API catalogada (reportado
como lacuna, nunca inventado):

  - `compiler_version`: `IScriptProjectSettings2.get_compilerversion()`
    existe (docs/27 linha 191/267), mas NENHUM membro catalogado devolve uma
    instancia de `IScriptProjectSettings2` a partir de `IScriptProject` ou
    `IScriptApplication`. Sem o acessor, chamar getattr especulativo seria
    inventar API -- o campo fica `None` com `compiler_version_gap` explicito;
  - `is_transient_object` por no, EM TODA a arvore: o scanner reaproveitado
    (`ReadOnlyProjectScanner`) le name/is_folder/type_guid/object_guid, nunca
    is_transient_object. Repetir a navegacao so para ler esse campo
    duplicaria o caminhador de arvore -- fora de escopo deste probe. Por isso
    `persistent_tree_sha256` e calculado sobre a arvore INTEIRA (nao apenas
    objetos persistentes) e o proprio nome do campo carrega essa ressalva
    (`persistent_tree_sha256_caveat`), nunca escondida.

SOMENTE LEITURA. Nenhuma API mutavel existe neste arquivo. Nenhuma chamada
adicional ao MasterTool alem da MESMA varredura que `probes/21` ja faz.

Compatibilidade: IronPython 2.7.12 (sem f-string, sem a construcao de
delegacao de gerador do Python 3, sem anotacao de tipo, sem o modulo de
caminhos orientado a objeto do Python 3).
"""
from __future__ import print_function

import hashlib
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

SCRIPT_NAME = "35_qualify_template_readonly.py"
SCHEMA_VERSION = "1.0"

DEFAULT_MAX_DEPTH = 32
DEFAULT_MAX_TOTAL_NODES = 20000
DEFAULT_MAX_CHILDREN_PER_NODE = 1024

# --- identidade, CONSTANTES DO MODULO, medidas (nunca vindas de argumento) ---
APPLICATION_NAME = "Application"
APPLICATION_TYPE_GUID = "639b491f-5557-464c-af91-1471bac9f549"
GVL_TYPE_GUID = "ffbfa93a-b94d-45fc-a329-229860183b1d"
POU_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
DEVICE_TYPE_GUID = "225bfe47-7336-4dbc-9419-4105a7c831fa"

# Catalogo LITERAL de type_guid conhecido -> rotulo. Qualquer type_guid fora
# daqui vira "unclassified" -- nunca um rotulo inventado.
KNOWN_TYPE_GUID_CATALOG = {
    APPLICATION_TYPE_GUID: "application",
    GVL_TYPE_GUID: "gvl",
    # docs/30: type_guid de POU NAO distingue PROGRAM de FUNCTION_BLOCK/
    # FUNCTION/DUT -- lacuna ja declarada, herdada sem re-derivacao.
    POU_TYPE_GUID: "pou_or_dut_leaf_undistinguished",
    DEVICE_TYPE_GUID: "device_or_hardware_node",
}

# Nomes-alvo cujo conflito bloqueia W1.4 (docs/32 secao 3, sequencia de
# criacao). Constante do modulo -- nunca vinda de argumento.
CONFLICT_TARGET_NAMES = ("GVL_AI_TESTE", "PRG_AI_TESTE")

# Nomes de nos-container cujos FILHOS (ja presentes em flat-nodes, via
# parent_node_id) sao reportados como bibliotecas/tasks. Derivado do dado que
# o scanner ja produziu -- nenhuma chamada adicional ao MasterTool.
LIBRARY_MANAGER_NODE_NAME = "Library Manager"
TASK_CONFIGURATION_NODE_NAME = "Task Configuration"

# --- estados, vocabulario fechado --------------------------------------------
STATUS_QUALIFIED = "qualified"
STATUS_QUALIFIED_WITH_NODE_ERRORS = "qualified_with_node_errors"
STATUS_NAME_CONFLICT_DETECTED = "name_conflict_detected"
STATUS_APPLICATION_NOT_FOUND = "application_not_found"
STATUS_APPLICATION_AMBIGUOUS = "application_ambiguous"
STATUS_TREE_TRUNCATED = "tree_truncated"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_QUALIFIED, STATUS_QUALIFIED_WITH_NODE_ERRORS,
    STATUS_NAME_CONFLICT_DETECTED, STATUS_APPLICATION_NOT_FOUND,
    STATUS_APPLICATION_AMBIGUOUS, STATUS_TREE_TRUNCATED, STATUS_FATAL,
)

# `name_conflict_detected` tem exit_code != 0 de proposito (secao abaixo): um
# conflito de nome BLOQUEIA W1.4, e a convencao deste repositorio e
# `is_success == (exit_code == 0)` (ver probes/31). Por isso ele NAO entra em
# SUCCESS_STATUSES, mesmo a qualificacao em si tendo funcionado -- o campo
# `registry_candidate` continua presente no resultado para quem quiser
# inspecionar apesar do bloqueio.
SUCCESS_STATUSES = (STATUS_QUALIFIED, STATUS_QUALIFIED_WITH_NODE_ERRORS)

EXIT_BY_STATUS = {
    STATUS_QUALIFIED: 0,
    STATUS_QUALIFIED_WITH_NODE_ERRORS: 0,
    STATUS_NAME_CONFLICT_DETECTED: 3,
    STATUS_APPLICATION_NOT_FOUND: 2,
    STATUS_APPLICATION_AMBIGUOUS: 2,
    STATUS_TREE_TRUNCATED: 2,
    STATUS_FATAL: 1,
}

_SCAN_STATUS_TRUNCATED = "truncated"
_SCAN_STATUS_COMPLETE = "complete"
_SCAN_STATUS_COMPLETE_WITH_NODE_ERRORS = "complete_with_node_errors"
_SCAN_STATUS_FATAL = "fatal"


# =============================================================================
# nucleo puro -- SOMENTE dados serializaveis, sem tocar o MasterTool. Testavel
# sem nenhum duble de CLR: opera sobre `flat_nodes`/`node_indexes`, que ja sao
# a saida de `read_only_project_scanner.flatten_tree`/`build_node_indexes`.
# =============================================================================

def classify_type_guid(type_guid):
    """Rotulo do catalogo LITERAL, ou 'unclassified'. Nunca inventa rotulo
    para um type_guid nao medido."""
    return KNOWN_TYPE_GUID_CATALOG.get(type_guid, "unclassified")


def classify_scan_status(scan_status, has_flat_nodes):
    """Espelha `_classify` de probes/21 -- mesma precedencia (truncado tem
    prioridade sobre erro de no), duplicada aqui de proposito: os dois probes
    sao runners finos independentes, e um import cruzado entre eles acoplaria
    scripts que precisam continuar executaveis isoladamente via
    `--runscript`."""
    if scan_status == _SCAN_STATUS_TRUNCATED:
        return STATUS_TREE_TRUNCATED
    if not has_flat_nodes:
        return STATUS_FATAL
    if scan_status == _SCAN_STATUS_COMPLETE_WITH_NODE_ERRORS:
        return STATUS_QUALIFIED_WITH_NODE_ERRORS
    if scan_status == _SCAN_STATUS_COMPLETE:
        return STATUS_QUALIFIED
    return STATUS_FATAL


def resolve_application(flat_nodes):
    """Resolve o `Application` POR BUSCA -- nome E type_guid, nunca por
    `node_path` presumido (docs/18: `root/1/0/0` era da base ANTIGA e nao
    vale aqui). Devolve dict com status/node_path/matches."""
    matches = [entry for entry in (flat_nodes or [])
              if entry.get("name") == APPLICATION_NAME
              and entry.get("type_guid") == APPLICATION_TYPE_GUID]
    if not matches:
        return {"status": "not_found", "node_path": None,
               "matches": []}
    if len(matches) > 1:
        return {"status": "ambiguous", "node_path": None,
               "matches": [m.get("node_id") for m in matches]}
    return {"status": "resolved", "node_path": matches[0].get("node_id"),
           "matches": [matches[0].get("node_id")]}


def detect_name_conflicts(flat_nodes, names=CONFLICT_TARGET_NAMES):
    """Para cada nome-alvo de W1.4, lista os `node_id` onde ja existe um
    objeto com esse nome. Dict vazio em cada entrada == sem conflito."""
    conflicts = {}
    for name in names:
        found = [entry.get("node_id") for entry in (flat_nodes or [])
                if entry.get("name") == name]
        conflicts[name] = found
    return conflicts


def has_any_conflict(conflicts):
    return any(bool(v) for v in (conflicts or {}).values())


def children_names_of_named_node(flat_nodes, node_name):
    """Filhos (por `parent_node_id`) do UNICO no chamado `node_name`, usando
    SOMENTE o que o scanner ja produziu -- nenhuma chamada adicional ao
    MasterTool. Devolve dict {status, node_id, names}."""
    matches = [entry for entry in (flat_nodes or []) if entry.get("name") == node_name]
    if not matches:
        return {"status": "not_found", "node_id": None, "names": []}
    if len(matches) > 1:
        return {"status": "ambiguous", "node_id": None,
               "names": [m.get("node_id") for m in matches]}
    node_id = matches[0].get("node_id")
    children = [entry.get("name") for entry in (flat_nodes or [])
               if entry.get("parent_node_id") == node_id]
    return {"status": "resolved", "node_id": node_id, "names": children}


def compute_persistent_tree_sha256(flat_nodes):
    """Hash deterministico sobre (node_id, name, type_guid) ordenados. NAO
    exclui objeto transiente (`is_transient_object` nao e lido pelo scanner
    reaproveitado) -- ver caveat no docstring do modulo e no campo
    `persistent_tree_sha256_caveat` do resultado."""
    rows = []
    for entry in (flat_nodes or []):
        rows.append("%s|%s|%s" % (entry.get("node_id"), entry.get("name"),
                                  entry.get("type_guid")))
    rows.sort()
    text = "\n".join(rows)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


PERSISTENT_TREE_SHA256_CAVEAT = (
    "calculado sobre TODOS os nos da arvore (node_id, name, type_guid); "
    "NAO exclui objeto transiente porque o scanner reaproveitado "
    "(ReadOnlyProjectScanner) nao le is_transient_object por no -- ver "
    "docstring do modulo, secao do que nao foi determinado."
)

COMPILER_VERSION_GAP = (
    "IScriptProjectSettings2.get_compilerversion() esta catalogado (docs/27 "
    "secao 6/7), mas nenhum membro catalogado devolve uma instancia de "
    "IScriptProjectSettings2 a partir de IScriptProject/IScriptApplication. "
    "Sem o acessor catalogado, o valor fica None em vez de inventado."
)

# --- evidencia, e nao valor -------------------------------------------------
#
# `compiler_version` deixou de ser um campo escalar e passou a ser EVIDENCIA
# explicita, por determinacao do usuario ao revisar a integracao. A razao: o
# probe se recusa a inventar API e o registry se recusa a aceitar template
# incompleto, e as duas recusas estao certas -- mas juntas nao compunham.
#
# A saida nao e escolher entre inventar valor e rejeitar o registro inteiro. E
# separar duas perguntas que estavam coladas numa so:
#
#     template qualificado ESTRUTURALMENTE  !=  template ELEGIVEL PARA AUTORIA
#
# Um template com lacuna pode ser medido, registrado e inspecionado. O que ele
# nao pode e ser selecionado por um executor mutavel.
EVIDENCE_MEASURED = "measured"
EVIDENCE_UNRESOLVED = "unresolved"

# Limites da varredura atras do no de bibliotecas. Existem para que "nao achei"
# seja sempre distinguivel de "desisti": estourar o limite devolve razao
# propria, e nao a mesma mensagem de ausencia.
_LIBMAN_MAX_DEPTH = 8
_LIBMAN_MAX_NODES = 512

# IronPython 2.7 dentro do MasterTool tem `basestring`; CPython 3 dos testes
# nao. `py_compile` NAO pega a diferenca -- o nome so falharia em tempo de
# execucao, ou seja, dentro da sessao supervisionada, tarde demais.
try:
    _STRING_TYPES = (basestring,)  # noqa: F821  (Python 2 / IronPython 2.7)
except NameError:
    _STRING_TYPES = (str,)         # Python 3 (testes)

# `unresolved` NUNCA vira string vazia, e `None` NUNCA significa "nao
# aplicavel": string vazia e None sao os dois jeitos classicos de uma lacuna
# atravessar uma fronteira se passando por dado. Aqui a lacuna tem nome,
# origem e razao.
COMPILER_VERSION_SOURCE_PROBE = "probe_35"
BLOCKER_COMPILER_VERSION = "compiler_version_unresolved"
BLOCKER_LIBRARIES = "libraries_unresolved"

# ACHADO NA RUN-010: o no "Library Manager" foi ALCANCADO (status `resolved`,
# node_id root/1/0/0/0) e devolveu ZERO filhos, num projeto industrial real com
# cartoes de I/O. Zero biblioteca ali e implausivel -- o que houve foi que as
# bibliotecas nao aparecem como filhos deste no na varredura.
#
# Lista vazia le como "medido: nenhuma", e o que se tem e "nao mensuravel por
# este caminho". Sao coisas opostas para quem decide, e a diferenca so aparece
# se alguem escrever. Enquanto nao houver caminho medido, isso bloqueia
# elegibilidade pelo mesmo motivo que a compiler version: autoria controlada
# sobre template cujo conjunto de bibliotecas e desconhecido nao e controlada.
LIBRARIES_EMPTY_GAP = (
    "o no Library Manager foi alcancado mas devolveu zero filhos. Em projeto "
    "real isso e implausivel: bibliotecas provavelmente nao sao expostas como "
    "filhos deste no via get_children. Tratado como LACUNA, e nao como "
    "'nenhuma biblioteca' -- medir exige caminho de API ainda nao catalogado."
)

QUALIFICATION_QUALIFIED = "qualified"
QUALIFICATION_WITH_BLOCKERS = "qualified_with_blockers"
QUALIFICATION_NOT_QUALIFIED = "not_qualified"


def build_type_guid_histogram(flat_nodes):
    """Contagem por type_guid observado, com a CLASSIFICACAO do catalogo
    literal (`classify_type_guid`) anexada a cada entrada -- nunca so a
    contagem cru: uma funcao de classificacao escrita e nunca chamada seria
    exatamente o defeito de 'constante que aparenta verificar e nao
    verifica'. Serve tambem para inspecao humana de dispositivos/cartoes de
    I/O que nao tem type_guid catalogado individualmente (`unclassified`)."""
    counts = {}
    for entry in (flat_nodes or []):
        key = entry.get("type_guid")
        if key is None:
            continue
        counts[key] = counts.get(key, 0) + 1
    classified = {}
    for type_guid, count in counts.items():
        classified[type_guid] = {"count": count,
                                 "classification": classify_type_guid(type_guid)}
    return classified


def read_compiler_version(project):
    """Le a compiler version pela cadeia LITERAL medida na run-012.

        projects.primary.project_settings.get_compilerversion()

    Fonte: stub oficial versionado pelo produto,
    `MT9000\\ScriptLib\\Stubs\\scriptengine\\ScriptProject.pyi` linhas 565-574
    (`project_settings`) e 664-671 (`get_compilerversion`). Confirmada em
    runtime na run-012, que devolveu "3.5.18.50".

    Uma cadeia so, literal, sem `getattr`, sem enumeracao de propriedades e
    sem tentar outro acessor se este falhar. Falha vira LACUNA com o `repr` da
    excecao e o passo culpado -- nunca valor inventado.
    """
    if project is None:
        return None, "sem projeto primario"
    try:
        settings = project.project_settings
    except Exception as exc:                                       # noqa: BLE001
        return None, "passo `project_settings` falhou: %r" % (exc,)
    if settings is None:
        return None, "passo `project_settings` devolveu None"
    try:
        valor = settings.get_compilerversion()
    except Exception as exc:                                       # noqa: BLE001
        return None, "passo `get_compilerversion()` falhou: %r" % (exc,)
    if not isinstance(valor, _STRING_TYPES) or not valor:
        return None, "get_compilerversion() devolveu %r" % (valor,)
    return valor, None


def build_compiler_version_evidence(value, reason):
    """Evidencia de compiler version: medida ou lacuna, nunca ambigua.

    Duas formas fechadas, e nenhuma terceira. `measured` exige valor textual
    nao vazio; `unresolved` exige valor None e razao escrita. Um valor vazio
    com status `measured` seria pior que a lacuna, porque a lacuna pelo menos
    se anuncia.
    """
    if isinstance(value, _STRING_TYPES) and value:
        return {
            "status": EVIDENCE_MEASURED,
            "value": value,
            "source": "literal read-only MasterTool API",
            "reason": None,
        }
    return {
        "status": EVIDENCE_UNRESOLVED,
        "value": None,
        "source": COMPILER_VERSION_SOURCE_PROBE,
        "reason": reason or COMPILER_VERSION_GAP,
    }


def classify_libraries(libraries):
    """Distingue "medido: nenhuma" de "nao mensuravel por este caminho".

    Devolve `(libraries_com_lacuna, ha_lacuna)`. Um no resolvido com zero
    filhos NAO e resultado -- e ausencia de resultado, e o artefato passa a
    dize-lo em vez de exibir uma lista vazia que le como medicao.
    """
    if not isinstance(libraries, dict):
        return libraries, True
    if libraries.get("status") != "resolved":
        return libraries, True
    nomes = libraries.get("names")
    if nomes:
        return libraries, False
    enriquecido = {}
    for chave in libraries:
        enriquecido[chave] = libraries[chave]
    enriquecido["status"] = "resolved_but_empty"
    enriquecido["gap"] = LIBRARIES_EMPTY_GAP
    return enriquecido, True


def derive_qualification(compiler_version_evidence, scan_ok, conflicts_found,
                         libraries_gap=False):
    """Qualificacao e elegibilidade DERIVADAS, nunca declaradas.

    Devolve `(qualification_status, authoring_eligible, blocking_issues)`.
    Ninguem escreve `authoring_eligible = True` a mao: ele e consequencia de
    nao haver bloqueio. Um artefato que pudesse se declarar elegivel seria
    exatamente o modo de falha que este desenho existe para impedir -- a mesma
    razao pela qual um plano nao pode declarar a propria fase.

    Lacuna medida NAO vira `fatal`: se todo o resto foi medido, a sessao
    read-only e valida e o template e registravel. O que ela impede e a
    ELEGIBILIDADE, e so ela.
    """
    blockers = []
    if (compiler_version_evidence or {}).get("status") != EVIDENCE_MEASURED:
        blockers.append(BLOCKER_COMPILER_VERSION)
    if libraries_gap:
        blockers.append(BLOCKER_LIBRARIES)
    if conflicts_found:
        blockers.append("object_name_conflict")

    if not scan_ok:
        return QUALIFICATION_NOT_QUALIFIED, False, blockers
    if blockers:
        return QUALIFICATION_WITH_BLOCKERS, False, blockers
    return QUALIFICATION_QUALIFIED, True, []


def build_registry_candidate(project_slug, project_sha256, mastertool_version,
                             application, compiler_version,
                             persistent_tree_sha256, libraries, tasks,
                             qualification_status, authoring_eligible,
                             blocking_issues):
    """Candidato de registry de template, no formato do Sprint 5.4. So e
    montado quando o Application foi resolvido -- sem container resolvido nao
    ha `application_node_path` valido para gravar."""
    template_id = None
    if project_slug and project_sha256:
        template_id = project_slug + "-" + project_sha256[:12]
    return {
        "template_id": template_id,
        "mastertool_version": mastertool_version,
        "sha256": project_sha256,
        "application_node_path": application.get("node_path"),
        "application_type_guid": APPLICATION_TYPE_GUID,
        "compiler_version": compiler_version,
        "qualification_status": qualification_status,
        "authoring_eligible": authoring_eligible,
        "blocking_issues": blocking_issues,
        "persistent_tree_sha256": persistent_tree_sha256,
        "libraries": libraries,
        "tasks": tasks,
        "volatile_fields": [
            "object_guid (docs/22: nao e identidade estavel entre sessoes)",
            "generated_at / timestamp de manifesto",
            "arquivos .opt irmaos (criados ao abrir o projeto, docs/27 secao 9)",
        ],
    }


def read_libraries_inventory(project):
    """Le o inventario de bibliotecas pelas cadeias medidas na run-016.

        no marcado por `is_libman`  (nunca pelo NOME "Library Manager",
                                     que e rotulo de interface e depende de
                                     idioma)
        libman.get_libraries(False)          -> nomes  (conferencia)
        libman.references[<nome>]            -> os cinco campos  (primaria)

    A indexacao e POR NOME, e nao por posicao: medido na run-015, o indexador
    posicional levanta NullReference no TemplateExemplo v1 mesmo com `len()` respondendo
    17. As duas formas estao no stub (`ScriptLibManObject.pyi` L476-506).

    NUNCA usa `get_library_manager()`: o stub diz (L819-826) que ele CRIA o
    gerenciador se nao existir, e criar esta fora de um probe read-only.

    Devolve `(lista_ou_None, razao_ou_None)`.
    """
    if project is None:
        return None, "sem projeto primario"

    # VARREDURA RECURSIVA, e nao filhos diretos. Medido na run-017, que falhou
    # por este exato motivo: o no marcado por `is_libman` esta em
    # `root/1/0/0/0` -- filho do Application, e nao do projeto. Olhar so um
    # nivel devolvia "nenhum filho do projeto tem is_libman" e reintroduzia,
    # por outro caminho, a mesma lacuna que a run-016 tinha fechado.
    libman = None
    pilha = [(project, 0)]
    visitados = 0
    while pilha and libman is None:
        if visitados >= _LIBMAN_MAX_NODES:
            return None, "varredura truncada em %d nos sem achar is_libman" % (
                _LIBMAN_MAX_NODES,)
        no_atual, profundidade = pilha.pop()
        visitados = visitados + 1
        if profundidade > 0:
            try:
                if no_atual.is_libman:
                    libman = no_atual
                    break
            except Exception:                                      # noqa: BLE001
                pass
        if profundidade >= _LIBMAN_MAX_DEPTH:
            continue
        try:
            filhos = no_atual.get_children(False)
            total_filhos = filhos.Count if filhos is not None else 0
        except Exception:                                          # noqa: BLE001
            continue
        indice = total_filhos - 1
        while indice >= 0:
            try:
                pilha.append((filhos[indice], profundidade + 1))
            except Exception:                                      # noqa: BLE001
                pass
            indice = indice - 1
    if libman is None:
        return None, ("nenhum no marcado por is_libman em %d nos varridos"
                      % (visitados,))

    try:
        nomes = list(libman.get_libraries(False))
    except Exception as exc:                                       # noqa: BLE001
        return None, "get_libraries(False) falhou: %r" % (exc,)
    if not nomes:
        return None, LIBRARIES_EMPTY_GAP

    try:
        referencias = libman.references
    except Exception as exc:                                       # noqa: BLE001
        return None, "`references` falhou: %r" % (exc,)
    if referencias is None:
        return None, "`references` devolveu None"

    bibliotecas = []
    for nome in nomes:
        try:
            referencia = referencias[nome]
        except Exception as exc:                                   # noqa: BLE001
            return None, "indexador por nome falhou em %r: %r" % (nome, exc)
        if referencia is None:
            return None, "indexador por nome devolveu None em %r" % (nome,)
        try:
            bibliotecas.append({
                "name": referencia.name,
                "namespace": referencia.namespace,
                "is_placeholder": referencia.is_placeholder,
                "is_managed": referencia.is_managed,
                "system_library": referencia.system_library,
            })
        except Exception as exc:                                   # noqa: BLE001
            return None, "leitura de campos falhou em %r: %r" % (nome, exc)
    return bibliotecas, None


def analyze(flat_nodes, scan_status, project_meta, runtime_identity,
            compiler_version_value=None, compiler_version_reason=None,
            libraries_measured=None, libraries_reason=None):
    """Nucleo puro: classifica o resultado do scanner reaproveitado. Nunca
    toca o MasterTool -- so le as listas ja serializadas."""
    result = {
        "application": None,
        "name_conflicts": None,
        "libraries": None,
        "tasks": None,
        "persistent_tree_sha256": None,
        "persistent_tree_sha256_caveat": PERSISTENT_TREE_SHA256_CAVEAT,
        # Nao ha acessor catalogado; a evidencia nasce `unresolved` e so muda
        # se um dia houver leitura literal. O probe nunca preenche por
        # analogia nem por default.
        "compiler_version": build_compiler_version_evidence(
            compiler_version_value,
            compiler_version_reason or COMPILER_VERSION_GAP),
        "compiler_version_gap": COMPILER_VERSION_GAP,
        "qualification_status": QUALIFICATION_NOT_QUALIFIED,
        "authoring_eligible": False,
        "blocking_issues": [BLOCKER_COMPILER_VERSION],
        "type_guid_histogram": None,
        "registry_candidate": None,
        "status": STATUS_FATAL,
    }

    base_status = classify_scan_status(scan_status, bool(flat_nodes))
    if base_status in (STATUS_TREE_TRUNCATED, STATUS_FATAL):
        result["status"] = base_status
        return result

    application = resolve_application(flat_nodes)
    result["application"] = application
    if application["status"] == "not_found":
        result["status"] = STATUS_APPLICATION_NOT_FOUND
        return result
    if application["status"] == "ambiguous":
        result["status"] = STATUS_APPLICATION_AMBIGUOUS
        return result

    conflicts = detect_name_conflicts(flat_nodes)
    result["name_conflicts"] = conflicts

    # MEDICAO REAL primeiro; a varredura da arvore so entra se ela nao veio.
    # A ordem importa porque as duas discordam de propria natureza: bibliotecas
    # NAO sao filhas do no, entao a arvore sempre devolveria vazio, e vazio le
    # como "nenhuma" (run-011, docs/36).
    if libraries_measured:
        result["libraries"] = {
            "status": "measured",
            "source": ("libman.get_libraries(False) para os nomes + "
                       "libman.references[<nome>] para os campos "
                       "(medido na run-016)"),
            "names": [b.get("name") for b in libraries_measured],
            "entries": libraries_measured,
            "count": len(libraries_measured),
        }
        libraries_gap = False
    else:
        libraries_raw = children_names_of_named_node(
            flat_nodes, LIBRARY_MANAGER_NODE_NAME)
        libraries_classificadas, libraries_gap = classify_libraries(libraries_raw)
        if libraries_reason:
            libraries_classificadas = dict(libraries_classificadas)
            libraries_classificadas["gap"] = libraries_reason
        result["libraries"] = libraries_classificadas
    result["tasks"] = children_names_of_named_node(flat_nodes, TASK_CONFIGURATION_NODE_NAME)
    result["persistent_tree_sha256"] = compute_persistent_tree_sha256(flat_nodes)
    result["type_guid_histogram"] = build_type_guid_histogram(flat_nodes)

    conflitou = has_any_conflict(conflicts)
    qualification, eligible, blockers = derive_qualification(
        result["compiler_version"], scan_ok=True, conflicts_found=conflitou,
        libraries_gap=libraries_gap)
    result["qualification_status"] = qualification
    result["authoring_eligible"] = eligible
    result["blocking_issues"] = blockers

    result["registry_candidate"] = build_registry_candidate(
        project_slug=(project_meta or {}).get("slug"),
        project_sha256=(project_meta or {}).get("sha256"),
        mastertool_version=(runtime_identity or {}).get("file_version"),
        application=application,
        compiler_version=result["compiler_version"],
        persistent_tree_sha256=result["persistent_tree_sha256"],
        libraries=(result["libraries"] or {}).get("names"),
        tasks=(result["tasks"] or {}).get("names"),
        qualification_status=qualification,
        authoring_eligible=eligible,
        blocking_issues=blockers)

    if conflitou:
        result["status"] = STATUS_NAME_CONFLICT_DETECTED
        return result

    result["status"] = base_status
    return result


# =============================================================================
# orquestracao -- unica parte que toca o MasterTool/disco.
# =============================================================================

def _project_sha256_and_size(project_path):
    if not project_path:
        return None, None, "caminho do projeto indisponivel"
    try:
        from common import checksums
        if not os.path.isfile(project_path):
            return None, None, "arquivo do projeto nao encontrado: %s" % project_path
        digest = checksums.sha256_file(project_path)
        size = os.path.getsize(project_path)
        return digest, size, None
    except Exception as exc:                                      # noqa: BLE001
        return None, None, repr(exc)


def _sibling_opt_files(project_path):
    """Lista .opt irmaos do projeto (docs/27 secao 9: abrir um projeto cria
    arquivos irmaos). Leitura pura de sistema de arquivos -- nao toca o
    MasterTool."""
    if not project_path:
        return []
    try:
        directory = os.path.dirname(os.path.abspath(project_path))
        stem = os.path.splitext(os.path.basename(project_path))[0]
        found = []
        for name in os.listdir(directory):
            if name.lower().endswith(".opt") and name.startswith(stem):
                found.append(name)
        return sorted(found)
    except Exception:                                              # noqa: BLE001
        return []


def run_qualification(script_globals, argv, project_access, file_io, probe_cli,
                      scanner_factory=None, now=None):
    """Orquestra: le o projeto primario, roda o scanner ja aprovado
    (ReadOnlyProjectScanner, via `scanner_factory` para permitir duble em
    teste), e classifica com o nucleo puro `analyze`. Nunca lanca."""
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": "read_only",
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "problems": [],
        "runtime": None,
        "project": {"path": None, "sha256": None, "size_bytes": None,
                   "sha256_error": None, "sibling_opt_files": None},
        "scan_status": None,
        "observed": {"root_count": None, "total_nodes": None},
        "analysis": None,
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
    if problems:
        result["problems"].extend(problems)
        return finish(STATUS_FATAL)
    result["artifacts_dir"] = artifacts_dir

    result["runtime"] = probe_cli.runtime_identity()

    project, access_error = project_access.get_primary_project(script_globals)
    if project is None:
        result["problems"].append("sem projeto primario: %s" % (access_error,))
        return finish(STATUS_FATAL)

    project_path = project_access.get_project_path(project)
    digest, size, digest_error = _project_sha256_and_size(project_path)
    slug = "projeto"
    if project_path:
        slug = os.path.splitext(os.path.basename(project_path))[0]
    result["project"]["path"] = project_path
    result["project"]["sha256"] = digest
    result["project"]["size_bytes"] = size
    result["project"]["sha256_error"] = digest_error
    result["project"]["sibling_opt_files"] = _sibling_opt_files(project_path)

    try:
        from common import read_only_project_scanner as default_scanner_module
        factory = scanner_factory
        if factory is None:
            factory = lambda: default_scanner_module.ReadOnlyProjectScanner(  # noqa: E731
                max_depth=DEFAULT_MAX_DEPTH, max_total_nodes=DEFAULT_MAX_TOTAL_NODES,
                max_children_per_node=DEFAULT_MAX_CHILDREN_PER_NODE,
                expected_root_count=None)
        scanner = factory()
        scan_result = scanner.scan(project)
        flat_nodes = default_scanner_module.flatten_tree(scan_result["tree"])
    except Exception as exc:                                       # noqa: BLE001
        result["problems"].append("falha ao varrer a arvore: %r" % (exc,))
        return finish(STATUS_FATAL)

    scan_status = None
    try:
        limits = scan_result.get("limits") or {}
        if any(limits.values()):
            scan_status = _SCAN_STATUS_TRUNCATED
        elif scan_result.get("errors"):
            scan_status = _SCAN_STATUS_COMPLETE_WITH_NODE_ERRORS
        elif flat_nodes:
            scan_status = _SCAN_STATUS_COMPLETE
        else:
            scan_status = _SCAN_STATUS_FATAL
    except Exception:                                               # noqa: BLE001
        scan_status = _SCAN_STATUS_FATAL

    result["scan_status"] = scan_status
    try:
        result["observed"]["total_nodes"] = len(flat_nodes)
        result["observed"]["root_count"] = len(scan_result["tree"]["children"])
    except Exception:                                                # noqa: BLE001
        pass

    # As duas medicoes que destravam a elegibilidade. Cada uma e uma cadeia
    # literal, e cada falha vira LACUNA com razao escrita -- nunca valor
    # inventado, nunca outro acessor tentado no lugar.
    compiler_valor, compiler_razao = read_compiler_version(project)
    bibliotecas_medidas, bibliotecas_razao = read_libraries_inventory(project)

    analysis = analyze(flat_nodes, scan_status,
                       {"slug": slug, "sha256": digest}, result["runtime"],
                       compiler_version_value=compiler_valor,
                       compiler_version_reason=compiler_razao,
                       libraries_measured=bibliotecas_medidas,
                       libraries_reason=bibliotecas_razao)
    result["analysis"] = analysis
    if analysis["status"] in (STATUS_APPLICATION_NOT_FOUND, STATUS_APPLICATION_AMBIGUOUS,
                              STATUS_TREE_TRUNCATED, STATUS_FATAL):
        result["problems"].append("qualificacao nao concluida: %s" % analysis["status"])
    if analysis["status"] == STATUS_NAME_CONFLICT_DETECTED:
        result["problems"].append(
            "conflito de nome detectado: %s -- W1.4 NAO pode rodar sem "
            "renomear ou trocar de base." % (analysis["name_conflicts"],))

    return finish(analysis["status"])


# =============================================================================
# artefatos ---------------------------------------------------------------
# =============================================================================

def build_completion(result):
    """Artefato de conclusao. E ELE que o wrapper le para dar veredito.

    ACHADO NA RUN-010, e corrigido aqui: a versao anterior omitia
    `qualification_status`, `authoring_eligible` e `blocking_issues`. Eles
    existiam no analysis e no registry_candidate, mas nao aqui -- e o wrapper,
    lendo so `status: "qualified"`, imprimiu "VEREDITO: APROVADO" para um
    template que NAO e elegivel para autoria.

    Um artefato de conclusao que precisa de outro arquivo ao lado para nao ser
    lido errado nao esta concluindo nada. `status` responde "a varredura deu
    certo?"; `authoring_eligible` responde "da para escrever neste template?".
    Sao perguntas diferentes e agora aparecem juntas.
    """
    analysis = result.get("analysis") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        # Veredito de AUTORIA, separado do veredito de VARREDURA.
        "qualification_status": analysis.get("qualification_status"),
        "authoring_eligible": analysis.get("authoring_eligible"),
        "blocking_issues": analysis.get("blocking_issues"),
        "project": result.get("project"),
        "scan_status": result.get("scan_status"),
        "observed": result.get("observed"),
        "application": analysis.get("application"),
        "name_conflicts": analysis.get("name_conflicts"),
        "persistent_tree_sha256": analysis.get("persistent_tree_sha256"),
        "compiler_version": analysis.get("compiler_version"),
        "compiler_version_gap": analysis.get("compiler_version_gap"),
        "libraries": analysis.get("libraries"),
        "tasks": analysis.get("tasks"),
        "registry_candidate": analysis.get("registry_candidate"),
        "errors": result.get("problems"),
        "mutating_calls": result.get("mutating_calls"),
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    analysis = result.get("analysis") or {}
    lines = [
        "# Probe 35 - qualificacao read-only do projeto-base candidato a template",
        "",
        "Somente leitura. Nenhuma API mutavel existe neste probe.",
        "",
        "- status: **%s**" % result.get("status"),
        "- exit_code logico: **%s**" % result.get("exit_code"),
        "- projeto: `%s`" % (result.get("project") or {}).get("path"),
        "- sha256: `%s`" % (result.get("project") or {}).get("sha256"),
        "- tamanho (bytes): `%s`" % (result.get("project") or {}).get("size_bytes"),
        "- .opt irmaos: `%s`" % (result.get("project") or {}).get("sibling_opt_files"),
        "- Application: `%s`" % (analysis.get("application") or {}),
        "- conflitos de nome: `%s`" % (analysis.get("name_conflicts") or {}),
        "- persistent_tree_sha256: `%s`" % analysis.get("persistent_tree_sha256"),
        "- compiler_version: `%s` (gap: %s)" % (analysis.get("compiler_version"),
                                                analysis.get("compiler_version_gap")),
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
    file_io.ensure_dir(artifacts_dir)
    written = []
    # A ANALISE CARREGA A IDENTIDADE DO ARQUIVO QUE ELA QUALIFICA.
    #
    # `qualify-analysis.json` e o artefato que a fabrica consulta para decidir
    # se um template e elegivel para autoria, e ate 2026-08-02 ele nao dizia de
    # QUAL arquivo falava -- o sha256 do projeto so existia no
    # `qualify-completion.json`, que a fabrica nao le. Duas execucoes, uma
    # qualificacao: dava para autorizar escrita num projeto apresentando a
    # qualificacao de outro, e nada detectaria.
    #
    # Isto nao acrescenta medicao nenhuma. So leva a medicao que ja existia
    # para o arquivo onde a decisao e tomada.
    analise = dict(result.get("analysis") or {})
    analise["project"] = result.get("project")
    file_io.write_json(os.path.join(artifacts_dir, "qualify-analysis.json"),
                       analise)
    written.append("qualify-analysis.json")
    if (result.get("analysis") or {}).get("registry_candidate"):
        file_io.write_json(os.path.join(artifacts_dir, "template-registry-candidate.json"),
                           result["analysis"]["registry_candidate"])
        written.append("template-registry-candidate.json")
    file_io.write_text(os.path.join(artifacts_dir, "qualify-report.md"),
                       build_report_markdown(result))
    written.append("qualify-report.md")
    file_io.write_json(os.path.join(artifacts_dir, "qualify-completion.json"),
                       build_completion(result))
    written.append("qualify-completion.json")
    return written


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s - SOMENTE LEITURA" % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access

    try:
        result = run_qualification(script_globals, list(sys.argv or []),
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
    for problem in result.get("problems") or []:
        print("[PROBLEM] %s" % problem)
    print("=" * 68)
    return result.get("exit_code")


if "projects" in globals():
    sys.exit(main())

# -*- coding: utf-8 -*-
"""GraphicLanguageInventory — inventario e classificacao tri-state (Fase L0,
docs/14-ladder-roadmap.md) de TODOS os nos da subarvore da Application de um
projeto MasterTool ja resolvido, usando SOMENTE capacidades JA CONFIRMADAS:

    node.get_children(False)             (ja confirmado — read_only_project_scanner.py)
    collection.Count                     (idem)
    collection[index]                    (idem, indexador nativo)
    node.get_name(False)                 (idem)
    node.is_folder / node.type / node.guid   (idem, identidade)
    node.has_textual_declaration         (ja confirmado — read_only_text_exporter.py)
    node.has_textual_implementation      (idem)

Motivo de existir (2026-07-24): a Fase L0 do roadmap Ladder
(docs/14-ladder-roadmap.md) pede um inventario que classifique cada no da
Application em 4 estados (supported/partially_supported/unsupported/unknown)
SEM sondar nenhuma propriedade nova alem das ja confirmadas acima — a
descoberta da representacao real de uma implementacao grafica fica para a
Fase L1 (probes/15+, ainda nao escrita). Este modulo NUNCA acessa
`.textual_declaration.text` / `.textual_implementation.text` (leitura de
CONTEUDO fica fora de escopo aqui — so os indicadores booleanos tri-state).

Este modulo e uma COPIA LOCAL deliberada da navegacao ja aprovada em
`common/read_only_project_scanner.py` e `common/read_only_text_exporter.py`
(mesma filosofia adotada entre aqueles dois modulos: nao importar
cruzado, cada modulo permanece independente e auditavel isoladamente) —
SOMENTE a parte de navegacao/identidade/indicadores tri-state e reaproveitada
textualmente; a logica de CLASSIFICACAO (4 estados) e nova, especifica desta
fase.

Regra de classificacao (identica a de
`src/mastertool_bridge/discovery/graphic_language_scan.py`, a contraparte
offline em Python 3.11 que analisa exports ja capturados — os dois modulos
NAO compartilham codigo, mas devem produzir a MESMA regra documentada):

    supported             has_textual_declaration CONFIRMADO True e
                           has_textual_implementation CONFIRMADO True.

    partially_supported   has_textual_declaration CONFIRMADO True,
                           has_textual_implementation NAO confirmado True
                           (False/ausente/erro), MAS o mesmo `type_guid`
                           aparece em outro no da MESMA arvore que TEM
                           has_textual_implementation CONFIRMADO True
                           (evidencia de "mesma familia de objeto, uma tem
                           texto, outra nao" — candidato a implementacao
                           nao-textual).

    unsupported           has_textual_declaration NAO confirmado True
                           (pastas, GVLs, Tasks, etc. — objeto fora do
                           escopo de POU com corpo de logica).

    unknown                has_textual_declaration CONFIRMADO True,
                           has_textual_implementation NAO confirmado True, e
                           o `type_guid` NAO aparece em nenhum outro no com
                           has_textual_implementation CONFIRMADO True (sem
                           referencia de comparacao).

A classificacao e feita em DUAS passadas sobre a arvore ja construida (dados
serializaveis em memoria, nao proxies): (1) navegacao + sondagem tri-state
por no, coletando type_guid -> lista de node_ids com implementacao textual
confirmada; (2) classificacao de cada no usando esse indice ja fechado (um
no PRECEDENTE na ordem de visita pode depender de um type_guid encontrado
so DEPOIS dele na arvore — por isso a classificacao so roda apos a arvore
inteira estar montada, nunca durante a navegacao/primeira passada).

Percurso: DFS ITERATIVO com pilha explicita (identico ao scanner/exportador
ja aprovados) — nunca recursao Python nem GetEnumerator()/iter()/list()
sobre a colecao CLR.

Identificacao de no: `node_id` construido EXCLUSIVAMENTE a partir do caminho
de indices, prefixo `application` (`application`, `application/0`, ...) —
mesma convencao de `read_only_text_exporter.py`.

Isolamento de falhas: falha de colecao/indexador isola so aquele ramo; falha
de campo de identidade isola so aquele campo; falha ao sondar um indicador
tri-state isola so aquele indicador (nunca aborta a varredura inteira). So o
limite global de nos (`max_total_nodes`) aborta o scan inteiro, preservando
o que ja foi coletado.

NAO FAZ: nao le `.textual_declaration.text` / `.textual_implementation.text`
(so os indicadores booleanos); nao sonda nenhum membro fora da whitelist ja
confirmada; nao modifica o projeto; nao usa `dir()` como fonte de verdade;
nao usa `find()`/`active_application` alem do parametro ja recebido
resolvido pelo chamador.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

from common import capabilities, compatibility

DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_TOTAL_NODES = 1000
DEFAULT_MAX_CHILDREN_PER_NODE = 128

_COUNT_BEARING_INTERFACE_PREFIXES = ("ICollection", "IList")

# Estados possiveis de node["collection"]["state"] (mesmo vocabulario do
# scanner/exportador ja aprovados, reaproveitado identico).
COLLECTION_STATE_CONFIRMED = "confirmed"
COLLECTION_STATE_UNSUPPORTED = "unsupported"
COLLECTION_STATE_UNKNOWN = "unknown"
COLLECTION_STATE_NULL = "null"
COLLECTION_STATE_INTERFACE_UNCONFIRMED = "interface_unconfirmed"
COLLECTION_STATE_INVALID_NEGATIVE_COUNT = "invalid_negative_count"
COLLECTION_STATE_COUNT_READ_FAILED = "count_read_failed"
COLLECTION_STATE_CHILDREN_LIMIT_EXCEEDED = "children_limit_exceeded"
COLLECTION_STATE_DEPTH_LIMIT = "not_attempted_depth_limit"
COLLECTION_STATE_TOTAL_NODES_LIMIT = "max_total_nodes_would_be_exceeded"
COLLECTION_STATE_PARTIAL_INDEXING = "partial_indexing"

_COLLECTION_ERROR_STATES = frozenset([
    COLLECTION_STATE_UNSUPPORTED, COLLECTION_STATE_UNKNOWN, COLLECTION_STATE_NULL,
    COLLECTION_STATE_INTERFACE_UNCONFIRMED, COLLECTION_STATE_INVALID_NEGATIVE_COUNT,
    COLLECTION_STATE_COUNT_READ_FAILED,
])

# Estados possiveis de um indicador tri-state (has_textual_declaration/
# has_textual_implementation) por no — mesmo vocabulario de
# read_only_text_exporter.py (DOC_STATE_*), reaproveitado identico para o
# indicador em si (aqui nao ha leitura de documento/.text).
INDICATOR_STATE_CONFIRMED_TRUE = "confirmed_true"
INDICATOR_STATE_CONFIRMED_FALSE = "confirmed_false"
INDICATOR_STATE_UNSUPPORTED = "unsupported"
INDICATOR_STATE_UNKNOWN = "unknown"
INDICATOR_STATE_NOT_BOOLEAN = "not_boolean"

# --- os 4 estados de classificacao exigidos pelo roadmap (nomenclatura EXATA) ---
STATE_SUPPORTED = "supported"
STATE_PARTIALLY_SUPPORTED = "partially_supported"
STATE_UNSUPPORTED = "unsupported"
STATE_UNKNOWN = "unknown"


def _field_result(state, value=None, error=None):
    return {"state": state, "value": value, "error": error}


def _empty_dotnet_info():
    return {"full_name": None, "available": False}


def _implements_count_bearing_interface(value):
    """Reflection sobre o TIPO do valor (GetType().GetInterfaces()) — NUNCA
    toca os DADOS/elementos da colecao. Copia local do mesmo helper usado em
    common/read_only_project_scanner.py e common/read_only_text_exporter.py."""
    try:
        clr_type = value.GetType()
        interfaces = clr_type.GetInterfaces()
        names = []
        for iface in interfaces:
            try:
                names.append(iface.Name)
            except Exception:
                continue
        implements = any(
            any(name.startswith(prefix) for prefix in _COUNT_BEARING_INTERFACE_PREFIXES)
            for name in names)
        return implements, names, None
    except Exception as exc:
        return False, [], repr(exc)


def _probe_property_via_representation(obj, obj_label, member_name):
    """1 getattr isolado + representacao estrita (build_representation) —
    identico ao helper do scanner/exportador ja aprovados."""
    record = capabilities.probe_member(
        obj, obj_label, member_name, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return _field_result(record["state"], error=record.get("exception_message"))
    value = record["raw_value"]
    python_type = capabilities.python_type_info(value)
    dotnet_type = capabilities.dotnet_type_info(value)
    rep = capabilities.build_representation(value, python_type, dotnet_type)
    if not rep["value_available"]:
        return _field_result(
            "unrepresentable",
            error="valor obtido, mas sem representacao segura (tipo .NET nao confirmado).")
    return _field_result("confirmed", value=rep["value"])


def _probe_name_via_method_call(obj, obj_label):
    """`get_name(False)`, 1 chamada, SEM fallback para `get_name(True)`."""
    record = capabilities.probe_method_call(
        obj, obj_label, "get_name", (False,), capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return _field_result(record["state"], error=record.get("exception_message"))
    value = record["raw_value"]
    python_type = capabilities.python_type_info(value)
    dotnet_type = capabilities.dotnet_type_info(value)
    rep = capabilities.build_representation(value, python_type, dotnet_type)
    if not rep["value_available"]:
        return _field_result("unrepresentable", error="nome obtido, mas sem representacao segura.")
    return _field_result("confirmed", value=rep["value"])


def _bool_field(field_result):
    """`is_folder` deve ser bool; qualquer outro valor vira 'unrepresentable'."""
    if field_result["state"] != "confirmed":
        return field_result
    if isinstance(field_result["value"], bool):
        return field_result
    return _field_result(
        "unrepresentable",
        error="valor obtido nao e bool (tipo: %s)." % compatibility.safe_type_name(field_result["value"]))


def _probe_node_identity(proxy, obj_label):
    """Os 4 campos de identidade de um no da subarvore (mesmo shape do
    scanner/exportador ja aprovados): name/is_folder/type_guid/object_guid."""
    return {
        "name": _probe_name_via_method_call(proxy, obj_label),
        "is_folder": _bool_field(_probe_property_via_representation(proxy, obj_label, "is_folder")),
        "type_guid": _probe_property_via_representation(proxy, obj_label, "type"),
        "object_guid": _probe_property_via_representation(proxy, obj_label, "guid"),
    }


def _node_runtime_info(proxy):
    python_type = capabilities.python_type_info(proxy)
    dotnet_type = capabilities.dotnet_type_info(proxy)
    rep = capabilities.build_representation(proxy, python_type, dotnet_type)
    return {
        "python_type": python_type,
        "dotnet_type": dotnet_type,
        "stringification_performed": rep["instance_stringification_performed"],
    }


def _call_get_children(proxy, obj_label):
    record = capabilities.probe_method_call(
        proxy, obj_label, "get_children", (False,), capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return record["state"], None, record.get("exception_message")
    return "confirmed", record["raw_value"], None


def _read_count(collection, obj_label):
    record = capabilities.probe_member(
        collection, obj_label, "Count", capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return record["state"], None, record.get("exception_message")
    raw = record["raw_value"]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return "unknown", None, "Count nao e um inteiro valido (tipo: %s)." % compatibility.safe_type_name(raw)
    return "confirmed", raw, None


def _access_index(collection, obj_label, index):
    record = capabilities.probe_indexer_access(
        collection, obj_label, index, capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return record["state"], None, record.get("exception_message")
    return "confirmed", record["raw_value"], None


def _probe_boolean_indicator(proxy, obj_label, member_name):
    """Sonda um indicador booleano tri-state (has_textual_declaration/
    has_textual_implementation) SEM ler nenhum documento/.text — este modulo
    e estritamente inventario (Fase L0), nunca extracao de conteudo.

    Retorna dict: {"state": INDICATOR_STATE_*, "error": str|None} — nunca
    "value" bruto do getattr (ja resolvido em confirmed_true/confirmed_false
    pelo proprio state)."""
    record = capabilities.probe_member(
        proxy, obj_label, member_name, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if record["state"] == "unsupported":
        return {"state": INDICATOR_STATE_UNSUPPORTED, "error": record.get("exception_message")}
    if record["state"] == "unknown":
        return {"state": INDICATOR_STATE_UNKNOWN, "error": record.get("exception_message")}
    # state == "confirmed"
    value = record.get("raw_value")
    if not isinstance(value, bool):
        return {"state": INDICATOR_STATE_NOT_BOOLEAN, "error": None}
    if value is True:
        return {"state": INDICATOR_STATE_CONFIRMED_TRUE, "error": None}
    return {"state": INDICATOR_STATE_CONFIRMED_FALSE, "error": None}


class GraphicLanguageInventory(object):
    """Varredura recursiva (DFS iterativo), somente leitura, com limites
    rigidos, da subarvore de uma Application ja resolvida — classifica cada
    no em supported/partially_supported/unsupported/unknown (Fase L0). Ver
    docstring do modulo para as regras completas."""

    def __init__(self, max_depth=DEFAULT_MAX_DEPTH, max_total_nodes=DEFAULT_MAX_TOTAL_NODES,
                max_children_per_node=DEFAULT_MAX_CHILDREN_PER_NODE,
                expected_application_name=None, expected_application_type_guid=None,
                expected_application_guid=None):
        self.max_depth = max_depth
        self.max_total_nodes = max_total_nodes
        self.max_children_per_node = max_children_per_node
        self.expected_application_name = expected_application_name
        self.expected_application_type_guid = expected_application_type_guid
        self.expected_application_guid = expected_application_guid

    # ------------------------------------------------------------------
    # Identidade da Application (name/type/guid) + comparacao com expected_*.
    # A CLASSE GENERICA so RELATA divergencia; quem decide abortar por causa
    # disso e o script chamador (mesmo padrao de ReadOnlyTextExporter).
    # ------------------------------------------------------------------
    def probe_application_identity(self, application, mismatches_out):
        name_field = _probe_name_via_method_call(application, "application")
        type_field = _probe_property_via_representation(application, "application", "type")
        guid_field = _probe_property_via_representation(application, "application", "guid")

        if self.expected_application_name is not None:
            if not (name_field["state"] == "confirmed"
                   and name_field["value"] == self.expected_application_name):
                mismatches_out.append(_IdentityMismatch(
                    "name", self.expected_application_name, name_field["state"], name_field["value"]))

        if self.expected_application_type_guid is not None:
            if not (type_field["state"] == "confirmed"
                   and type_field["value"] == self.expected_application_type_guid):
                mismatches_out.append(_IdentityMismatch(
                    "type_guid", self.expected_application_type_guid, type_field["state"], type_field["value"]))

        if self.expected_application_guid is not None:
            if not (guid_field["state"] == "confirmed"
                   and guid_field["value"] == self.expected_application_guid):
                mismatches_out.append(_IdentityMismatch(
                    "object_guid", self.expected_application_guid, guid_field["state"], guid_field["value"]))

        return {
            "name": name_field,
            "type_guid": type_field,
            "object_guid": guid_field,
        }

    # ------------------------------------------------------------------
    # Camada PURA: navegacao + sondagem tri-state + classificacao. Nao toca
    # disco, nunca le `.text`. Retorna dict 100% serializavel.
    # ------------------------------------------------------------------
    def inventory(self, application):
        """Executa UM inventario completo contra uma `application` JA
        RESOLVIDA. Nunca lanca excecao; retorna sempre um dict 100%
        serializavel, com a arvore + classificacao EM MEMORIA (nenhum proxy
        CLR)."""
        errors = []
        stats = {
            "total_nodes": 0,
            "complete_nodes": 0,
            "partial_nodes": 0,
            "failed_nodes": 0,
            "collections_read": 0,
            "empty_collections": 0,
            "maximum_depth_reached": 0,
            "field_errors": 0,
            "collection_errors": 0,
            "index_errors": 0,
            "duplicate_object_guids": 0,
            "scan_complete": False,
            "state_counts": {
                STATE_SUPPORTED: 0,
                STATE_PARTIALLY_SUPPORTED: 0,
                STATE_UNSUPPORTED: 0,
                STATE_UNKNOWN: 0,
            },
        }
        limits_hit = {
            "max_depth_reached": False,
            "max_total_nodes_reached": False,
            "max_children_per_node_reached": False,
        }
        seen_object_guids = {}

        identity_mismatches = []
        application_identity = self.probe_application_identity(application, identity_mismatches)

        root_runtime = _node_runtime_info(application)

        tree_root = {
            "node_id": "application",
            "parent_node_id": None,
            "depth": 0,
            "index": None,
            "path_indices": [],
            "identity": {},
            "runtime": root_runtime,
            "collection": {
                "state": None, "count": None, "accessed_indices": [],
                "dotnet_type": _empty_dotnet_info(),
                "implements_count_bearing_interface": None,
            },
            "indicators": {
                "has_textual_declaration": {"state": INDICATOR_STATE_UNSUPPORTED, "error": None},
                "has_textual_implementation": {"state": INDICATOR_STATE_UNSUPPORTED, "error": None},
            },
            "children": [],
            "cycle_detected": False,
        }
        # A raiz (Application) nunca e sondada quanto a indicadores tri-state
        # aqui: `_probe_boolean_indicator` roda para TODOS os nos visitados
        # via `_process_node`, incluindo a raiz — o valor acima e so o
        # default ANTES da sondagem real (sobrescrito logo abaixo).

        total_nodes = [1]
        aborted = [False]

        stack = [{
            "proxy": application, "record": tree_root, "obj_label": "application",
            "depth": 0, "ancestor_guids": frozenset([]), "is_root": True,
        }]

        while stack and not aborted[0]:
            frame = stack.pop()
            self._process_node(frame, stack, errors, stats, limits_hit,
                               seen_object_guids, total_nodes, aborted)

        stats["total_nodes"] = total_nodes[0]
        stats["scan_complete"] = not aborted[0]

        # --- Segunda passada: indice type_guid -> node_ids com
        # has_textual_implementation CONFIRMADO True (fechado sobre a arvore
        # inteira ANTES de classificar qualquer no — um no pode depender de
        # um irmao/primo visitado DEPOIS dele na ordem de navegacao).
        implementation_type_guids = _collect_implementation_type_guids(tree_root)

        self._classify_nodes(tree_root, stats, implementation_type_guids, is_root=True)

        return {
            "schema_version": "1.0",
            "inventory": {
                "mode": "read_only",
                "max_depth": self.max_depth,
                "max_total_nodes": self.max_total_nodes,
                "max_children_per_node": self.max_children_per_node,
            },
            "application_identity": application_identity,
            "application_identity_mismatch": [m.to_dict() for m in identity_mismatches],
            "statistics": stats,
            "tree": tree_root,
            "errors": errors,
            "limits": limits_hit,
            "safety_declaration": _SAFETY_DECLARATION,
        }

    # ------------------------------------------------------------------
    # Navegacao (identica ao scanner/exportador ja aprovados) + sondagem dos
    # 2 indicadores tri-state (sem leitura de documento/.text).
    # ------------------------------------------------------------------
    def _process_node(self, frame, stack, errors, stats, limits_hit,
                      seen_object_guids, total_nodes, aborted):
        record = frame["record"]
        proxy = frame["proxy"]
        depth = frame["depth"]
        obj_label = frame["obj_label"]
        col = record["collection"]

        # --- indicadores tri-state NESTE no (independe do resultado da
        # colecao; roda mesmo em folhas sem filhos e mesmo na raiz).
        record["indicators"] = {
            "has_textual_declaration": _probe_boolean_indicator(
                proxy, obj_label, "has_textual_declaration"),
            "has_textual_implementation": _probe_boolean_indicator(
                proxy, obj_label, "has_textual_implementation"),
        }
        for indicator_name, indicator_result in record["indicators"].items():
            if indicator_result["state"] in (INDICATOR_STATE_UNSUPPORTED, INDICATOR_STATE_UNKNOWN):
                # 'unsupported' e o caso ESPERADO para pastas/GVLs/Tasks/etc
                # (indicador simplesmente nao existe no objeto) — nao e um
                # erro de execucao do inventario, entao nao polui `errors`.
                if indicator_result["state"] == INDICATOR_STATE_UNKNOWN:
                    stats["field_errors"] += 1
                    errors.append({
                        "where": record["node_id"],
                        "message": "%s: %s (%s)" % (indicator_result["state"], indicator_name,
                                                    indicator_result.get("error")),
                    })

        if depth > self.max_depth:
            limits_hit["max_depth_reached"] = True
            col["state"] = COLLECTION_STATE_DEPTH_LIMIT
            return

        if depth > stats["maximum_depth_reached"]:
            stats["maximum_depth_reached"] = depth

        gc_state, children_collection, gc_error = _call_get_children(proxy, obj_label)
        if gc_state != "confirmed":
            col["state"] = gc_state
            stats["collection_errors"] += 1
            errors.append({"where": record["node_id"], "message": gc_error})
            return

        if children_collection is None:
            col["state"] = COLLECTION_STATE_NULL
            stats["collection_errors"] += 1
            errors.append({"where": record["node_id"], "message": "colecao de filhos retornou nula."})
            return

        col["dotnet_type"] = capabilities.dotnet_type_info(children_collection)
        implements, iface_names, iface_err = _implements_count_bearing_interface(children_collection)
        col["implements_count_bearing_interface"] = implements
        col["type_interfaces_observed"] = iface_names
        if not implements:
            col["state"] = COLLECTION_STATE_INTERFACE_UNCONFIRMED
            stats["collection_errors"] += 1
            errors.append({"where": record["node_id"],
                          "message": "colecao nao confirmou ICollection/IList (%s)." % iface_err})
            return

        count_state, count_value, count_err = _read_count(children_collection, obj_label + "_children")
        if count_state != "confirmed":
            col["state"] = COLLECTION_STATE_COUNT_READ_FAILED
            stats["collection_errors"] += 1
            errors.append({"where": record["node_id"], "message": count_err})
            return

        if count_value < 0:
            col["state"] = COLLECTION_STATE_INVALID_NEGATIVE_COUNT
            stats["collection_errors"] += 1
            errors.append({"where": record["node_id"], "message": "Count negativo (%s)." % count_value})
            return

        col["count"] = count_value
        stats["collections_read"] += 1
        if count_value == 0:
            stats["empty_collections"] += 1

        if count_value > self.max_children_per_node:
            col["state"] = COLLECTION_STATE_CHILDREN_LIMIT_EXCEEDED
            limits_hit["max_children_per_node_reached"] = True
            errors.append({
                "where": record["node_id"],
                "message": ("children_limit_exceeded: Count (%s) excede max_children_per_node "
                           "(%s). Nenhum filho desta colecao foi indexado."
                           % (count_value, self.max_children_per_node)),
            })
            return

        if total_nodes[0] + count_value > self.max_total_nodes:
            limits_hit["max_total_nodes_reached"] = True
            col["state"] = COLLECTION_STATE_TOTAL_NODES_LIMIT
            errors.append({
                "where": record["node_id"],
                "message": ("max_total_nodes_reached: indexar esta colecao (%s filhos) "
                           "levaria o total a %s, acima de max_total_nodes (%s). Scan "
                           "interrompido, dados ja coletados preservados."
                           % (count_value, total_nodes[0] + count_value, self.max_total_nodes)),
            })
            aborted[0] = True
            return

        col["state"] = COLLECTION_STATE_CONFIRMED

        pending_push = []
        accessed_indices = []
        for index in range(count_value):
            idx_state, child_proxy, idx_err = _access_index(children_collection, obj_label + "_children", index)
            accessed_indices.append(index)
            if idx_state != "confirmed":
                stats["index_errors"] += 1
                col["state"] = COLLECTION_STATE_PARTIAL_INDEXING
                errors.append({
                    "where": "%s/%s" % (record["node_id"], index),
                    "message": ("falha no indexador: %s. Interrompendo esta colecao "
                               "(nenhum indice seguinte tentado); apenas ESTA "
                               "colecao, o resto do scan continua." % idx_err),
                })
                break  # interrompe SO esta colecao — colecao pode estar instavel

            child_node_id = record["node_id"] + "/" + str(index)
            identity = _probe_node_identity(child_proxy, "node_" + child_node_id.replace("/", "_"))
            for field in identity.values():
                if field["state"] != "confirmed":
                    stats["field_errors"] += 1
            runtime_info = _node_runtime_info(child_proxy)

            child_record = {
                "node_id": child_node_id,
                "parent_node_id": record["node_id"],
                "depth": depth + 1,
                "index": index,
                "path_indices": record["path_indices"] + [index],
                "identity": identity,
                "runtime": runtime_info,
                "collection": {
                    "state": None, "count": None, "accessed_indices": [],
                    "dotnet_type": _empty_dotnet_info(),
                    "implements_count_bearing_interface": None,
                },
                "indicators": {
                    "has_textual_declaration": {"state": INDICATOR_STATE_UNSUPPORTED, "error": None},
                    "has_textual_implementation": {"state": INDICATOR_STATE_UNSUPPORTED, "error": None},
                },
                "children": [],
                "cycle_detected": False,
            }

            object_guid_field = identity["object_guid"]
            object_guid_value = object_guid_field["value"] if object_guid_field["state"] == "confirmed" else None
            if object_guid_value is not None:
                seen_object_guids.setdefault(object_guid_value, [])
                if seen_object_guids[object_guid_value]:
                    stats["duplicate_object_guids"] += 1
                    errors.append({
                        "where": child_node_id,
                        "message": ("duplicate_object_guid: guid %s ja visto em %s."
                                   % (object_guid_value, seen_object_guids[object_guid_value])),
                    })
                seen_object_guids[object_guid_value].append(child_node_id)

            ancestor_guids = frame["ancestor_guids"]
            is_cycle = object_guid_value is not None and object_guid_value in ancestor_guids
            child_record["cycle_detected"] = is_cycle
            if is_cycle:
                errors.append({
                    "where": child_node_id,
                    "message": ("cycle_detected: object_guid %s ja presente na cadeia de "
                               "ancestrais deste no. Descida interrompida (get_children "
                               "NAO chamado neste no)." % object_guid_value),
                })

            record["children"].append(child_record)
            total_nodes[0] += 1

            if not is_cycle:
                new_ancestors = ancestor_guids
                if object_guid_value is not None:
                    new_ancestors = ancestor_guids | frozenset([object_guid_value])
                pending_push.append({
                    "proxy": child_proxy, "record": child_record,
                    "obj_label": "node_" + child_node_id.replace("/", "_"),
                    "depth": depth + 1, "ancestor_guids": new_ancestors, "is_root": False,
                })

        col["accessed_indices"] = accessed_indices

        for item in reversed(pending_push):
            stack.append(item)

    def _classify_nodes(self, node, stats, implementation_type_guids, is_root=False):
        """Classifica cada no (supported/partially_supported/unsupported/
        unknown) segundo a regra do modulo, usando o indice `type_guid ->
        node_ids com implementacao textual confirmada` JA FECHADO sobre a
        arvore inteira. Tambem acumula complete/partial/failed (mesmo
        criterio estrutural do scanner/exportador ja aprovados, para
        paridade de relatorio). Percurso recursivo sobre a ARVORE JA
        CONSTRUIDA (dados serializaveis, nao proxies) — profundidade
        limitada por max_depth, sem risco de recursao excessiva."""
        col = node["collection"]
        col_state = col["state"]

        fields_states = [f["state"] for f in node["identity"].values()] if node["identity"] else []
        all_fields_failed = bool(fields_states) and all(s != "confirmed" for s in fields_states)
        any_field_failed = any(s != "confirmed" for s in fields_states)

        collection_ok_or_boundary = col_state in (
            COLLECTION_STATE_CONFIRMED, COLLECTION_STATE_DEPTH_LIMIT,
            COLLECTION_STATE_CHILDREN_LIMIT_EXCEEDED, COLLECTION_STATE_TOTAL_NODES_LIMIT,
        )

        if all_fields_failed and not is_root:
            stats["failed_nodes"] += 1
        elif (not any_field_failed) and collection_ok_or_boundary:
            stats["complete_nodes"] += 1
        else:
            stats["partial_nodes"] += 1

        declaration_indicator = node["indicators"]["has_textual_declaration"]
        implementation_indicator = node["indicators"]["has_textual_implementation"]
        declaration_confirmed_true = declaration_indicator["state"] == INDICATOR_STATE_CONFIRMED_TRUE
        implementation_confirmed_true = implementation_indicator["state"] == INDICATOR_STATE_CONFIRMED_TRUE

        type_guid_field = node["identity"].get("type_guid") if node["identity"] else None
        type_guid_value = (type_guid_field["value"]
                          if type_guid_field and type_guid_field["state"] == "confirmed" else None)

        evidence_node_ids = None
        if not declaration_confirmed_true:
            state = STATE_UNSUPPORTED
            evidence = ("has_textual_declaration nao confirmado True (state=%s) — objeto fora "
                       "do escopo de POU com corpo de logica." % declaration_indicator["state"])
        elif implementation_confirmed_true:
            state = STATE_SUPPORTED
            evidence = "has_textual_declaration e has_textual_implementation ambos confirmados True."
        else:
            # declaracao confirmada True, implementacao NAO confirmada True.
            evidence_node_ids = ([nid for nid in implementation_type_guids.get(type_guid_value, [])
                                  if nid != node["node_id"]]
                                 if type_guid_value is not None else [])
            if evidence_node_ids:
                state = STATE_PARTIALLY_SUPPORTED
                evidence = ("has_textual_declaration confirmado True; has_textual_implementation "
                           "nao confirmado (state=%s); type_guid %r compartilhado com no(s) que TEM "
                           "has_textual_implementation confirmado True: %s — candidato a "
                           "implementacao nao-textual." % (implementation_indicator["state"],
                                                           type_guid_value, evidence_node_ids))
            else:
                state = STATE_UNKNOWN
                evidence = ("has_textual_declaration confirmado True; has_textual_implementation "
                           "nao confirmado (state=%s); type_guid %r sem nenhuma referencia de "
                           "comparacao (nenhum outro no com has_textual_implementation confirmado "
                           "True compartilha este type_guid)." % (implementation_indicator["state"],
                                                                  type_guid_value))

        node["state"] = state
        node["evidence"] = evidence
        stats["state_counts"][state] += 1

        for child in node["children"]:
            self._classify_nodes(child, stats, implementation_type_guids, is_root=False)


class _IdentityMismatch(object):
    """Estrutura simples (nao excecao) representando uma divergencia de
    identidade entre o valor observado e o expected_* configurado. Copia
    local de ApplicationIdentityMismatch (read_only_text_exporter.py)."""

    def __init__(self, field, expected, observed_state, observed_value):
        self.field = field
        self.expected = expected
        self.observed_state = observed_state
        self.observed_value = observed_value

    def to_dict(self):
        return {
            "field": self.field,
            "expected": self.expected,
            "observed_state": self.observed_state,
            "observed_value": self.observed_value,
        }


def _collect_implementation_type_guids(tree):
    """Indice type_guid -> lista ordenada de node_ids, restrito a nos com
    has_textual_implementation CONFIRMADO True e type_guid confirmado.
    Percurso iterativo (pilha explicita), nao recursivo."""
    index = {}
    stack = [tree]
    while stack:
        node = stack.pop()
        implementation_indicator = node["indicators"]["has_textual_implementation"]
        if implementation_indicator["state"] == INDICATOR_STATE_CONFIRMED_TRUE:
            type_guid_field = node["identity"].get("type_guid") if node["identity"] else None
            if type_guid_field and type_guid_field["state"] == "confirmed":
                index.setdefault(type_guid_field["value"], []).append(node["node_id"])
        for child in node["children"]:
            stack.append(child)
    for node_ids in index.values():
        node_ids.sort()
    return index


_SAFETY_DECLARATION = {
    "read_only": True,
    "project_write": False,
    "project_save": False,
    "project_close": False,
    "object_creation": False,
    "object_modification": False,
    "text_content_read": False,
    "textual_declaration_text_accessed": False,
    "textual_implementation_text_accessed": False,
    "find_used": False,
    "compilation": False,
    "online_access": False,
    "device_repository_access": False,
    "device_configuration_access": False,
    "download": False,
    "force": False,
    "collection_direct_iteration": False,
    "bounded_index_navigation": True,
    "recursive_navigation": True,
    "new_member_probing": False,
}


def flatten_tree(tree):
    """Lista achatada de todos os nos da arvore (mesmo padrao do scanner/
    exportador ja aprovados). Percurso iterativo (pilha explicita), nao
    recursivo."""
    flat = []
    stack = [tree]
    while stack:
        node = stack.pop()
        name_field = node["identity"].get("name") if node["identity"] else None
        type_guid_field = node["identity"].get("type_guid") if node["identity"] else None
        object_guid_field = node["identity"].get("object_guid") if node["identity"] else None
        is_folder_field = node["identity"].get("is_folder") if node["identity"] else None
        declaration_indicator = node["indicators"]["has_textual_declaration"]
        implementation_indicator = node["indicators"]["has_textual_implementation"]
        flat.append({
            "node_id": node["node_id"],
            "parent_node_id": node["parent_node_id"],
            "depth": node["depth"],
            "index": node["index"],
            "name": name_field["value"] if name_field and name_field["state"] == "confirmed" else None,
            "object_guid": object_guid_field["value"] if object_guid_field and object_guid_field["state"] == "confirmed" else None,
            "type_guid": type_guid_field["value"] if type_guid_field and type_guid_field["state"] == "confirmed" else None,
            "path": node["node_id"],
            "is_folder": is_folder_field["value"] if is_folder_field and is_folder_field["state"] == "confirmed" else None,
            "has_textual_declaration": declaration_indicator["state"],
            "has_textual_implementation": implementation_indicator["state"],
            "state": node.get("state"),
            "evidence": node.get("evidence"),
            "child_count": len(node["children"]),
        })
        for child in reversed(node["children"]):
            stack.append(child)
    flat.sort(key=lambda entry: entry["node_id"])
    return flat


def split_by_state(flat_nodes):
    """Particiona `flat_nodes` (ja achatado por flatten_tree) nos 4
    subconjuntos exigidos pelo roadmap. Cada subconjunto e um SUBCONJUNTO
    EXATO e consistente da lista completa (mesmos dicts, sem copia parcial
    de campos)."""
    by_state = {
        STATE_SUPPORTED: [],
        STATE_PARTIALLY_SUPPORTED: [],
        STATE_UNSUPPORTED: [],
        STATE_UNKNOWN: [],
    }
    for entry in flat_nodes:
        state = entry.get("state")
        if state in by_state:
            by_state[state].append(entry)
    return by_state

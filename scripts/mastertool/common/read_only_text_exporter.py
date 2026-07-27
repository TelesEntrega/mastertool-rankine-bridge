# -*- coding: utf-8 -*-
"""ReadOnlyTextExporter — exportador textual SOMENTE LEITURA da subarvore da
Application de um projeto MasterTool IEC XE 3.63 (CODESYS ScriptEngine).

Motivo de existir (2026-07-23): depois de `common/read_only_project_scanner.py`
confirmar em runtime real (117 nos, 0 erros, ExemploPlanta V1.0.project) que a
cadeia `get_children(False)` -> `Count` -> indexador -> `is_folder`/`type`/
`guid`/`get_name(False)` funciona identicamente em qualquer nivel da arvore,
esta fase estende a MESMA filosofia para: (1) entrar pela Application (nao
pela raiz do projeto) e (2) alem dos metadados estruturais, ler o CONTEUDO
TEXTUAL (declaracao/implementacao ST) de cada objeto que o confirmar de
forma explicita, tri-state, via `common/capabilities.py`.

API usada, EXCLUSIVAMENTE, em qualquer no da subarvore:

    node.get_children(False)
    collection.Count
    collection[index]
    node.get_name(False)
    node.is_folder
    node.type
    node.guid
    node.has_textual_declaration       (getattr isolado, tri-state)
    node.textual_declaration           (getattr isolado, SO SE has_* confirmed True)
    node.textual_declaration.text      (getattr isolado, SO SE textual_declaration confirmed)
    node.has_textual_implementation    (mesma regra, para implementacao)
    node.textual_implementation
    node.textual_implementation.text

NUNCA usa: `dir()` como fonte de verdade; `find()`; `replace()`/`append()`/
`get_line()`/`create_pou()`/`create_gvl()`/`create_dut()`/`build()`/
`rebuild()`/`clean()`/`generate_code()`/`save()`/`save_as()`/`close()`;
nenhum setter; `device_repository`/`online`; PLCopen XML; nenhuma
normalizacao/strip do texto lido (preservacao EXATA por padrao).

Percurso: DFS ITERATIVO com pilha explicita (nunca recursao Python nem
GetEnumerator()/iter()/list() sobre a colecao CLR) — identico ao scanner ja
aprovado. Filhos lidos em ordem crescente (0..Count-1), empilhados em ordem
reversa para o pop() processar na ordem crescente correta.

Identificacao de no: `node_id` construido EXCLUSIVAMENTE a partir do caminho
de indices, com prefixo `application` no lugar de `root`
(`application`, `application/0`, `application/0/3`, `application/0/3/2`, ...).

Isolamento de falhas: falha de colecao/indexador isola so aquele ramo; falha
de campo de identidade isola so aquele campo; falha ao sondar/ler um
documento textual isola so aquele documento (declaracao OU implementacao,
nunca os dois de uma vez pelo mesmo motivo). Only o limite global de nos
(`max_total_nodes`) aborta o scan inteiro, preservando o que ja foi
coletado.

Separacao pura/impura: `export()` e 100% puro em relacao a disco (navega,
decide, monta a arvore + textos EM MEMORIA, retorna um dict serializavel).
A escrita de artefatos em disco (metadata.json/declaration.st/
implementation.st por objeto) e uma camada fina e SEPARADA
(`write_text_export_artifacts()`), que so serializa o que `export()` ja
decidiu gravar — nunca toca em proxies/objetos do ScriptEngine.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import os

from common import capabilities, compatibility, file_io

DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_TOTAL_NODES = 2000
DEFAULT_MAX_CHILDREN_PER_NODE = 256
DEFAULT_MAX_TEXT_OBJECTS = 500
DEFAULT_MAX_DOCUMENT_CHARACTERS = 2000000
DEFAULT_MAX_TOTAL_CHARACTERS = 25000000

_COUNT_BEARING_INTERFACE_PREFIXES = ("ICollection", "IList")

# Estados possiveis de node["collection"]["state"] (mesmo vocabulario do
# scanner ja aprovado, reaproveitado identico).
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

# Estados possiveis de um documento textual (declaration/implementation) por no.
DOC_STATE_NOT_APPLICABLE = "not_applicable"          # indicador ausente/False/unsupported/unknown/nao-booleano
DOC_STATE_INDICATOR_CONFIRMED_FALSE = "indicator_confirmed_false"
DOC_STATE_INDICATOR_UNSUPPORTED = "indicator_unsupported"
DOC_STATE_INDICATOR_UNKNOWN = "indicator_unknown"
DOC_STATE_INDICATOR_NOT_BOOLEAN = "indicator_not_boolean"
DOC_STATE_DOCUMENT_UNSUPPORTED = "document_unsupported"
DOC_STATE_DOCUMENT_UNKNOWN = "document_unknown"
DOC_STATE_DOCUMENT_NULL = "document_null"
DOC_STATE_TEXT_UNSUPPORTED = "text_unsupported"
DOC_STATE_TEXT_UNKNOWN = "text_unknown"
DOC_STATE_TEXT_NOT_STRING = "text_not_string"
DOC_STATE_SAVED = "saved"
DOC_STATE_SIZE_LIMIT_EXCEEDED = "document_size_limit_exceeded"
DOC_STATE_TOTAL_CHARACTERS_LIMIT_REACHED = "max_total_characters_reached"
DOC_STATE_TEXT_OBJECT_LIMIT_REACHED = "max_text_objects_reached"


def _field_result(state, value=None, error=None):
    return {"state": state, "value": value, "error": error}


def _empty_dotnet_info():
    return {"full_name": None, "available": False}


def _implements_count_bearing_interface(value):
    """Reflection sobre o TIPO do valor (GetType().GetInterfaces()) — NUNCA
    toca os DADOS/elementos da colecao. Copia local do mesmo helper usado em
    common/read_only_project_scanner.py."""
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
    identico ao helper do scanner ja aprovado."""
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
    scanner ja aprovado): name/is_folder/type_guid/object_guid."""
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
    has_textual_implementation). Retorna (confirmed_true: bool,
    doc_state: str|None, error: str|None). doc_state so e preenchido quando
    o indicador NAO habilita leitura adicional (None quando confirmed_true)."""
    record = capabilities.probe_member(
        proxy, obj_label, member_name, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if record["state"] == "unsupported":
        return False, DOC_STATE_INDICATOR_UNSUPPORTED, record.get("exception_message")
    if record["state"] == "unknown":
        return False, DOC_STATE_INDICATOR_UNKNOWN, record.get("exception_message")
    # state == "confirmed"
    value = record.get("raw_value")
    if not isinstance(value, bool):
        return False, DOC_STATE_INDICATOR_NOT_BOOLEAN, None
    if value is False:
        return False, DOC_STATE_INDICATOR_CONFIRMED_FALSE, None
    return True, None, None


def _probe_text_document(proxy, obj_label, document_member_name):
    """SO chamado quando o indicador booleano correspondente ja veio
    CONFIRMADO True. 1 getattr isolado para o objeto documento, depois 1
    getattr isolado para `.text` — NUNCA repr()/str()/ToString() no proprio
    objeto documento (so no texto, DEPOIS de confirmado como string nativa).

    Retorna dict:
        {"doc_state": ..., "text": str|None, "error": str|None}
    """
    doc_record = capabilities.probe_member(
        proxy, obj_label, document_member_name, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if doc_record["state"] == "unsupported":
        return {"doc_state": DOC_STATE_DOCUMENT_UNSUPPORTED, "text": None,
                "error": doc_record.get("exception_message")}
    if doc_record["state"] == "unknown":
        return {"doc_state": DOC_STATE_DOCUMENT_UNKNOWN, "text": None,
                "error": doc_record.get("exception_message")}

    document = doc_record.get("raw_value")
    if document is None:
        return {"doc_state": DOC_STATE_DOCUMENT_NULL, "text": None, "error": None}

    text_record = capabilities.probe_member(
        document, obj_label + "_document", "text", capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if text_record["state"] == "unsupported":
        return {"doc_state": DOC_STATE_TEXT_UNSUPPORTED, "text": None,
                "error": text_record.get("exception_message")}
    if text_record["state"] == "unknown":
        return {"doc_state": DOC_STATE_TEXT_UNKNOWN, "text": None,
                "error": text_record.get("exception_message")}

    text_value = text_record.get("raw_value")
    if not isinstance(text_value, capabilities._STRING_TYPES):
        return {"doc_state": DOC_STATE_TEXT_NOT_STRING, "text": None,
                "error": "text nao e uma string nativa (tipo: %s)."
                        % compatibility.safe_type_name(text_value)}

    # text_value JA E uma string nativa confirmada: seguro por construcao,
    # nenhuma normalizacao/strip/alteracao aplicada.
    return {"doc_state": DOC_STATE_SAVED, "text": text_value, "error": None}


class ApplicationIdentityMismatch(object):
    """Estrutura simples (nao excecao) representando uma divergencia de
    identidade entre o valor observado e o expected_* configurado."""

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


class ReadOnlyTextExporter(object):
    """Exportador textual recursivo (DFS iterativo), somente leitura, da
    subarvore de uma Application ja resolvida. Ver docstring do modulo para
    as regras completas de limites/isolamento de falha/seguranca."""

    def __init__(self, max_depth=DEFAULT_MAX_DEPTH, max_total_nodes=DEFAULT_MAX_TOTAL_NODES,
                max_children_per_node=DEFAULT_MAX_CHILDREN_PER_NODE,
                max_text_objects=DEFAULT_MAX_TEXT_OBJECTS,
                max_document_characters=DEFAULT_MAX_DOCUMENT_CHARACTERS,
                max_total_characters=DEFAULT_MAX_TOTAL_CHARACTERS,
                expected_application_name=None, expected_application_type_guid=None,
                expected_application_guid=None):
        self.max_depth = max_depth
        self.max_total_nodes = max_total_nodes
        self.max_children_per_node = max_children_per_node
        self.max_text_objects = max_text_objects
        self.max_document_characters = max_document_characters
        self.max_total_characters = max_total_characters
        self.expected_application_name = expected_application_name
        self.expected_application_type_guid = expected_application_type_guid
        self.expected_application_guid = expected_application_guid

    # ------------------------------------------------------------------
    # Camada PURA: navegacao + decisao. Nao toca disco. `output_directory`
    # e aceito apenas para reportar no resultado onde a camada de escrita
    # (write_text_export_artifacts, mais abaixo) DEVERIA gravar — este
    # metodo em si nunca abre um arquivo.
    # ------------------------------------------------------------------
    def export(self, application, output_directory=None):
        """Executa UMA varredura textual completa contra uma `application`
        JA RESOLVIDA. Nunca lanca excecao; retorna sempre um dict 100%
        serializavel, com a arvore + textos EM MEMORIA (nenhum proxy CLR)."""
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
            "text_object_count": 0,
            "declarations_saved": 0,
            "implementations_saved": 0,
            "total_characters_saved": 0,
            "documents_skipped_size_limit": 0,
            "documents_skipped_total_limit": 0,
            "documents_skipped_object_limit": 0,
            "scan_complete": False,
        }
        limits_hit = {
            "max_depth_reached": False,
            "max_total_nodes_reached": False,
            "max_children_per_node_reached": False,
            "max_text_objects_reached": False,
            "max_total_characters_reached": False,
        }
        seen_object_guids = {}

        identity_mismatches = []
        application_identity = self._probe_application_identity(application, identity_mismatches)

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
                "iteration_performed": False, "dotnet_type": _empty_dotnet_info(),
                "implements_count_bearing_interface": None,
            },
            "text": {
                "declaration": None,
                "implementation": None,
            },
            "children": [],
            "cycle_detected": False,
        }

        total_nodes = [1]
        aborted = [False]
        text_object_count = [0]
        total_characters = [0]
        total_characters_limit_reached = [False]
        text_objects_limit_reached = [False]

        stack = [{
            "proxy": application, "record": tree_root, "obj_label": "application",
            "depth": 0, "ancestor_guids": frozenset([]), "is_root": True,
        }]

        while stack and not aborted[0]:
            frame = stack.pop()
            self._process_node(frame, stack, errors, stats, limits_hit,
                               seen_object_guids, total_nodes, aborted,
                               text_object_count, total_characters,
                               total_characters_limit_reached,
                               text_objects_limit_reached)

        stats["total_nodes"] = total_nodes[0]
        stats["text_object_count"] = text_object_count[0]
        stats["total_characters_saved"] = total_characters[0]
        stats["scan_complete"] = not aborted[0]
        limits_hit["max_total_characters_reached"] = total_characters_limit_reached[0]
        limits_hit["max_text_objects_reached"] = text_objects_limit_reached[0]
        self._classify_nodes(tree_root, stats, is_root=True)

        return {
            "schema_version": "1.0",
            "exporter": {
                "mode": "read_only",
                "max_depth": self.max_depth,
                "max_total_nodes": self.max_total_nodes,
                "max_children_per_node": self.max_children_per_node,
                "max_text_objects": self.max_text_objects,
                "max_document_characters": self.max_document_characters,
                "max_total_characters": self.max_total_characters,
            },
            "application_identity": application_identity,
            "application_identity_mismatch": [m.to_dict() for m in identity_mismatches],
            "output_directory": output_directory,
            "statistics": stats,
            "tree": tree_root,
            "errors": errors,
            "limits": limits_hit,
            "safety_declaration": _SAFETY_DECLARATION,
        }

    # ------------------------------------------------------------------
    # Identidade da Application (name/type/guid) + comparacao com expected_*.
    # A CLASSE GENERICA so RELATA divergencia (application_identity_mismatch);
    # quem decide abortar por causa disso e o script de validacao chamador.
    # ------------------------------------------------------------------
    def _probe_application_identity(self, application, mismatches_out):
        name_field = _probe_name_via_method_call(application, "application")
        type_field = _probe_property_via_representation(application, "application", "type")
        guid_field = _probe_property_via_representation(application, "application", "guid")

        if self.expected_application_name is not None:
            if not (name_field["state"] == "confirmed"
                   and name_field["value"] == self.expected_application_name):
                mismatches_out.append(ApplicationIdentityMismatch(
                    "name", self.expected_application_name, name_field["state"], name_field["value"]))

        if self.expected_application_type_guid is not None:
            if not (type_field["state"] == "confirmed"
                   and type_field["value"] == self.expected_application_type_guid):
                mismatches_out.append(ApplicationIdentityMismatch(
                    "type_guid", self.expected_application_type_guid, type_field["state"], type_field["value"]))

        if self.expected_application_guid is not None:
            if not (guid_field["state"] == "confirmed"
                   and guid_field["value"] == self.expected_application_guid):
                mismatches_out.append(ApplicationIdentityMismatch(
                    "object_guid", self.expected_application_guid, guid_field["state"], guid_field["value"]))

        return {
            "name": name_field,
            "type_guid": type_field,
            "object_guid": guid_field,
        }

    # ------------------------------------------------------------------
    # Navegacao (identica ao scanner ja aprovado) + descoberta de texto.
    # ------------------------------------------------------------------
    def _process_node(self, frame, stack, errors, stats, limits_hit,
                      seen_object_guids, total_nodes, aborted,
                      text_object_count, total_characters,
                      total_characters_limit_reached, text_objects_limit_reached):
        record = frame["record"]
        proxy = frame["proxy"]
        depth = frame["depth"]
        obj_label = frame["obj_label"]
        col = record["collection"]

        # --- descoberta de texto NESTE no (independe do resultado da colecao;
        # roda mesmo em folhas sem filhos). So conta como "novo objeto textual"
        # na primeira vez que ESTE no salva pelo menos 1 documento.
        self._discover_node_text(proxy, obj_label, record, stats, errors,
                                 text_object_count, total_characters,
                                 total_characters_limit_reached,
                                 text_objects_limit_reached)

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
                    "iteration_performed": False, "dotnet_type": _empty_dotnet_info(),
                    "implements_count_bearing_interface": None,
                },
                "text": {
                    "declaration": None,
                    "implementation": None,
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

    def _discover_node_text(self, proxy, obj_label, record, stats, errors,
                            text_object_count, total_characters,
                            total_characters_limit_reached, text_objects_limit_reached):
        """Sonda declaracao e implementacao textual deste no, uma de cada
        vez, isoladamente. So tenta NOVAS leituras de texto se os limites de
        quantidade de objetos textuais e de caracteres totais ainda
        permitirem — mas SEMPRE continua coletando metadados estruturais
        (esta funcao nunca impede a navegacao do no)."""
        node_saved_any = [False]

        for kind, indicator_name, document_name in (
            ("declaration", "has_textual_declaration", "textual_declaration"),
            ("implementation", "has_textual_implementation", "textual_implementation"),
        ):
            entry = self._discover_one_document(
                proxy, obj_label, kind, indicator_name, document_name, record["node_id"],
                stats, errors, text_object_count, total_characters,
                total_characters_limit_reached, text_objects_limit_reached, node_saved_any)
            record["text"][kind] = entry

    def _discover_one_document(self, proxy, obj_label, kind, indicator_name, document_name,
                               node_id, stats, errors, text_object_count, total_characters,
                               total_characters_limit_reached, text_objects_limit_reached,
                               node_saved_any):
        # Limite de quantidade de objetos textuais: se ja atingido, NAO
        # tenta nenhuma NOVA leitura textual (mas nao afeta metadados).
        if text_object_count[0] >= self.max_text_objects:
            text_objects_limit_reached[0] = True
            return {"doc_state": DOC_STATE_TEXT_OBJECT_LIMIT_REACHED, "character_length": None,
                   "byte_length": None, "sha256": None, "error": None}

        confirmed_true, indicator_doc_state, indicator_error = _probe_boolean_indicator(
            proxy, obj_label, indicator_name)
        if not confirmed_true:
            doc_state = indicator_doc_state or DOC_STATE_NOT_APPLICABLE
            if doc_state in (DOC_STATE_INDICATOR_UNSUPPORTED, DOC_STATE_INDICATOR_UNKNOWN):
                errors.append({"where": node_id, "message": "%s (%s): %s" % (doc_state, indicator_name, indicator_error)})
            return {"doc_state": doc_state, "character_length": None, "byte_length": None,
                   "sha256": None, "error": indicator_error}

        # Indicador CONFIRMADO True: agora, e so agora, sonda o documento.
        doc_result = _probe_text_document(proxy, obj_label, document_name)
        doc_state = doc_result["doc_state"]
        if doc_state != DOC_STATE_SAVED:
            if doc_state in (DOC_STATE_DOCUMENT_UNSUPPORTED, DOC_STATE_DOCUMENT_UNKNOWN,
                             DOC_STATE_TEXT_UNSUPPORTED, DOC_STATE_TEXT_UNKNOWN, DOC_STATE_TEXT_NOT_STRING):
                errors.append({"where": node_id, "message": "%s (%s): %s" % (doc_state, document_name, doc_result.get("error"))})
            return {"doc_state": doc_state, "character_length": None, "byte_length": None,
                   "sha256": None, "error": doc_result.get("error"), "text": None}

        text_value = doc_result["text"]
        char_length = len(text_value)

        if char_length > self.max_document_characters:
            stats["documents_skipped_size_limit"] += 1
            errors.append({
                "where": node_id,
                "message": ("document_size_limit_exceeded: %s tem %s caracteres, acima de "
                           "max_document_characters (%s). Documento NAO salvo."
                           % (kind, char_length, self.max_document_characters)),
            })
            return {"doc_state": DOC_STATE_SIZE_LIMIT_EXCEEDED, "character_length": char_length,
                   "byte_length": None, "sha256": None, "error": None, "text": None}

        if total_characters[0] + char_length > self.max_total_characters:
            total_characters_limit_reached[0] = True
            stats["documents_skipped_total_limit"] += 1
            errors.append({
                "where": node_id,
                "message": ("max_total_characters_reached: salvar %s (%s caracteres) levaria o "
                           "total a %s, acima de max_total_characters (%s). Documento NAO salvo; "
                           "impedindo novas leituras textuais dali em diante."
                           % (kind, char_length, total_characters[0] + char_length, self.max_total_characters)),
            })
            return {"doc_state": DOC_STATE_TOTAL_CHARACTERS_LIMIT_REACHED, "character_length": char_length,
                   "byte_length": None, "sha256": None, "error": None, "text": None}

        # Preservacao EXATA: sem strip/replace/normalizacao de finais de linha.
        try:
            byte_length = len(text_value.encode("utf-8"))
        except Exception:
            byte_length = None
        from common import checksums as _checksums
        sha256_hex = _checksums.sha256_text(text_value)

        total_characters[0] += char_length
        if not node_saved_any[0]:
            node_saved_any[0] = True
            text_object_count[0] += 1

        if kind == "declaration":
            stats["declarations_saved"] += 1
        else:
            stats["implementations_saved"] += 1

        return {
            "doc_state": DOC_STATE_SAVED,
            "character_length": char_length,
            "byte_length": byte_length,
            "sha256": sha256_hex,
            "error": None,
            "text": text_value,
        }

    def _classify_nodes(self, node, stats, is_root=False):
        """Classifica cada no (complete/partial/failed) e acumula nas
        estatisticas. Percurso recursivo sobre a ARVORE JA CONSTRUIDA
        (dados serializaveis, nao proxies) — profundidade limitada por
        max_depth, sem risco de recursao excessiva."""
        col = node["collection"]
        col_state = col["state"]

        fields_states = [f["state"] for f in node["identity"].values()] if node["identity"] else []

        all_fields_failed = bool(fields_states) and all(s != "confirmed" for s in fields_states)
        any_field_failed = any(s != "confirmed" for s in fields_states)

        collection_ok_or_boundary = col_state in (
            COLLECTION_STATE_CONFIRMED, COLLECTION_STATE_DEPTH_LIMIT,
            COLLECTION_STATE_CHILDREN_LIMIT_EXCEEDED, COLLECTION_STATE_TOTAL_NODES_LIMIT,
        )
        collection_failed = col_state in _COLLECTION_ERROR_STATES or col_state == COLLECTION_STATE_PARTIAL_INDEXING

        if all_fields_failed and not is_root:
            stats["failed_nodes"] += 1
        elif (not any_field_failed) and collection_ok_or_boundary:
            stats["complete_nodes"] += 1
        else:
            stats["partial_nodes"] += 1

        for child in node["children"]:
            self._classify_nodes(child, stats, is_root=False)


_SAFETY_DECLARATION = {
    "read_only": True,
    "project_write": False,
    "project_save": False,
    "project_close": False,
    "object_creation": False,
    "object_modification": False,
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
    "text_read_only": True,
    "text_normalization_applied": False,
    "text_written_verbatim": True,
    "text_document_access": True,
    "text_document_write": False,
    "replace_called": False,
    "append_called": False,
    "get_line_called": False,
}


def flatten_tree(tree):
    """Lista achatada de todos os nos da arvore (mesmo padrao do scanner ja
    aprovado). Percurso iterativo (pilha explicita), nao recursivo."""
    flat = []
    stack = [tree]
    while stack:
        node = stack.pop()
        name_field = node["identity"].get("name") if node["identity"] else None
        type_guid_field = node["identity"].get("type_guid") if node["identity"] else None
        object_guid_field = node["identity"].get("object_guid") if node["identity"] else None
        text = node.get("text") or {}
        declaration = text.get("declaration") or {}
        implementation = text.get("implementation") or {}
        declaration_state = declaration.get("doc_state")
        implementation_state = implementation.get("doc_state")
        has_declaration = declaration_state == DOC_STATE_SAVED
        has_implementation = implementation_state == DOC_STATE_SAVED
        flat.append({
            "node_id": node["node_id"],
            "parent_node_id": node["parent_node_id"],
            "depth": node["depth"],
            "index": node["index"],
            "name": name_field["value"] if name_field and name_field["state"] == "confirmed" else None,
            "type_guid": type_guid_field["value"] if type_guid_field and type_guid_field["state"] == "confirmed" else None,
            "object_guid": object_guid_field["value"] if object_guid_field and object_guid_field["state"] == "confirmed" else None,
            "child_count": len(node["children"]),
            "has_declaration": has_declaration,
            "has_implementation": has_implementation,
            "declaration_state": declaration_state,
            "implementation_state": implementation_state,
            "declaration_file": "declaration.st" if has_declaration else None,
            "implementation_file": "implementation.st" if has_implementation else None,
            "declaration_character_length": declaration.get("character_length") if has_declaration else None,
            "implementation_character_length": implementation.get("character_length") if has_implementation else None,
        })
        for child in reversed(node["children"]):
            stack.append(child)
    flat.sort(key=lambda entry: entry["node_id"])
    return flat


# doc_state que representa uma FALHA real de sondagem/leitura (nem
# "confirmado False", nem "salvo com sucesso") — para declaracao OU
# implementacao. Estados de limite (tamanho/quantidade/total de
# caracteres) NAO sao erro: sao recusa deliberada de salvar por politica,
# nao falha ao sondar/ler.
_DOC_ERROR_STATES = frozenset([
    DOC_STATE_INDICATOR_UNSUPPORTED,
    DOC_STATE_INDICATOR_UNKNOWN,
    DOC_STATE_INDICATOR_NOT_BOOLEAN,
    DOC_STATE_DOCUMENT_UNSUPPORTED,
    DOC_STATE_DOCUMENT_UNKNOWN,
    DOC_STATE_DOCUMENT_NULL,
    DOC_STATE_TEXT_UNSUPPORTED,
    DOC_STATE_TEXT_UNKNOWN,
    DOC_STATE_TEXT_NOT_STRING,
])


def _text_index_object_entry(entry):
    return {
        "node_id": entry["node_id"],
        "name": entry["name"],
        "type_guid": entry["type_guid"],
        "object_guid": entry["object_guid"],
        "declaration_file": entry.get("declaration_file"),
        "implementation_file": entry.get("implementation_file"),
    }


def build_text_index(flat_nodes):
    """Constroi o indice textual no schema exigido (ver docs/12-read-only-
    text-export.md): 5 listas de objetos (declaracao/implementacao/ambos/
    sem texto/com erro de sondagem-leitura) + 4 totais agregados.

    `objects_with_text_errors` NAO e mutuamente exclusiva com as outras
    listas de "sucesso" (um no pode ter declaracao salva E erro na
    implementacao); e exclusiva apenas com `objects_without_text`, que so
    recebe nos onde AMBOS os indicadores vieram confirmados False (nenhum
    problema — apenas ausencia real de texto)."""
    objects_with_declaration = []
    objects_with_implementation = []
    objects_with_both = []
    objects_without_text = []
    objects_with_text_errors = []

    total_text_objects = 0
    total_declaration_characters = 0
    total_implementation_characters = 0

    for entry in flat_nodes:
        has_declaration = entry["has_declaration"]
        has_implementation = entry["has_implementation"]
        declaration_state = entry.get("declaration_state")
        implementation_state = entry.get("implementation_state")

        object_entry = _text_index_object_entry(entry)

        if has_declaration:
            objects_with_declaration.append(object_entry)
        if has_implementation:
            objects_with_implementation.append(object_entry)
        if has_declaration and has_implementation:
            objects_with_both.append(object_entry)

        declaration_confirmed_false = declaration_state == DOC_STATE_INDICATOR_CONFIRMED_FALSE
        implementation_confirmed_false = implementation_state == DOC_STATE_INDICATOR_CONFIRMED_FALSE
        if declaration_confirmed_false and implementation_confirmed_false:
            objects_without_text.append(object_entry)

        declaration_errored = declaration_state in _DOC_ERROR_STATES
        implementation_errored = implementation_state in _DOC_ERROR_STATES
        if declaration_errored or implementation_errored:
            objects_with_text_errors.append(object_entry)

        if has_declaration:
            total_declaration_characters += entry.get("declaration_character_length") or 0
        if has_implementation:
            total_implementation_characters += entry.get("implementation_character_length") or 0

        if has_declaration or has_implementation:
            total_text_objects += 1

    return {
        "objects_with_declaration": objects_with_declaration,
        "objects_with_implementation": objects_with_implementation,
        "objects_with_both": objects_with_both,
        "objects_without_text": objects_without_text,
        "objects_with_text_errors": objects_with_text_errors,
        "total_text_objects": total_text_objects,
        "total_declaration_characters": total_declaration_characters,
        "total_implementation_characters": total_implementation_characters,
        "total_characters": total_declaration_characters + total_implementation_characters,
    }


# ----------------------------------------------------------------------
# Camada de escrita em disco — FINA, separada da navegacao/decisao acima.
# So serializa o que export() ja decidiu (dict puro), nunca toca em
# proxies/objetos do ScriptEngine. Aceita output_directory explicito.
# ----------------------------------------------------------------------

def write_text_export_artifacts(export_result, output_directory):
    """Grava, para cada no com documento(s) textual(is) salvos:
    objects/<node_id_seguro>__<nome_sanitizado>/metadata.json +
    declaration.st (se houver) + implementation.st (se houver).

    `export_result` deve ser o dict retornado por
    ReadOnlyTextExporter.export(). Retorna a lista de diretorios de objeto
    criados (relativos a output_directory)."""
    objects_root = os.path.join(output_directory, "objects")
    written = []

    stack = [export_result["tree"]]
    while stack:
        node = stack.pop()
        text = node.get("text") or {}
        declaration = text.get("declaration") or {}
        implementation = text.get("implementation") or {}
        has_declaration = declaration.get("doc_state") == DOC_STATE_SAVED
        has_implementation = implementation.get("doc_state") == DOC_STATE_SAVED

        if has_declaration or has_implementation:
            name_field = node["identity"].get("name") if node["identity"] else None
            name_value = name_field["value"] if name_field and name_field["state"] == "confirmed" else None
            node_id_safe = file_io.safe_filename(node["node_id"].replace("/", "_"), 60)
            name_safe = file_io.safe_filename(name_value, 60)
            dir_name = "%s__%s" % (node_id_safe, name_safe)
            object_dir = os.path.join(objects_root, dir_name)
            file_io.ensure_dir(object_dir)

            node_errors = [
                e for e in export_result.get("errors", [])
                if isinstance(e.get("where"), str) and (
                    e["where"] == node["node_id"]
                    or e["where"].startswith(node["node_id"] + "/")
                )
            ]

            metadata = {
                "schema_version": "1.0",
                "node_id": node["node_id"],
                "parent_node_id": node["parent_node_id"],
                "depth": node["depth"],
                "index": node["index"],
                "identity": _identity_metadata(node["identity"]),
                "declaration": _doc_metadata(declaration, "declaration.st"),
                "implementation": _doc_metadata(implementation, "implementation.st"),
                "runtime": node["runtime"],
                "errors": node_errors,
            }
            file_io.write_json(os.path.join(object_dir, "metadata.json"), metadata)

            if has_declaration and declaration.get("text") is not None:
                _write_verbatim(os.path.join(object_dir, "declaration.st"), declaration["text"])
            if has_implementation and implementation.get("text") is not None:
                _write_verbatim(os.path.join(object_dir, "implementation.st"), implementation["text"])

            written.append(dir_name)

        for child in node["children"]:
            stack.append(child)

    return written


def _identity_metadata(identity):
    """Extrai so o "value" (quando state=="confirmed", senao None) de cada
    campo de identidade — valores diretos, nao os dicts {"state":...,
    "value":...} inteiros, para bater com o shape de metadata.json."""
    identity = identity or {}

    def _value_of(field_name):
        field = identity.get(field_name)
        if field and field.get("state") == "confirmed":
            return field.get("value")
        return None

    return {
        "name": _value_of("name"),
        "is_folder": _value_of("is_folder"),
        "type_guid": _value_of("type_guid"),
        "object_guid": _value_of("object_guid"),
    }


def _doc_metadata(doc_entry, file_name):
    doc_state = doc_entry.get("doc_state")
    available = doc_state == DOC_STATE_SAVED
    return {
        "available": available,
        "state": doc_state,
        "file": file_name if available else None,
        "character_length": doc_entry.get("character_length"),
        "byte_length": doc_entry.get("byte_length"),
        "sha256": doc_entry.get("sha256"),
    }


def _write_verbatim(path, text):
    """Grava o texto EXATAMENTE como recebido — sem strip/normalizacao de
    finais de linha. codecs.open com newline nativo do Python 2/IronPython
    (sem tradução automática de '\\n', ao contrário do modo texto do C)."""
    file_io.ensure_dir(os.path.dirname(path))
    import codecs
    f = codecs.open(path, "wb", "utf-8")
    try:
        f.write(text)
    finally:
        f.close()
    return path

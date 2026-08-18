# -*- coding: utf-8 -*-
"""ReadOnlyProjectScanner — scanner recursivo, somente leitura, com limites
rigidos, da arvore completa de um projeto MasterTool ja resolvido.

Motivo de existir (2026-07-23): os probes 05-10 confirmaram, um indice por
vez, que a cadeia `get_children(False)` -> `Count` -> indexador nativo ->
`is_folder`/`type`/`guid`/`get_name(False)` funciona identicamente em
qualquer nivel da arvore (raiz e nos filhos). Em vez de continuar criando
um probe por indice, este modulo generaliza a MESMA cadeia ja confirmada
para uma varredura completa, com limites obrigatorios (profundidade, total
de nos, filhos por no), isolamento de falhas por ramo, deteccao
conservadora de ciclos, e saida 100% serializavel.

Nao reativa `tree_walker.py` (que segue suspenso). Este e um modulo NOVO e
independente — ver docs/11-read-only-project-scanner.md.

API usada, EXCLUSIVAMENTE, em qualquer nivel da arvore (nunca outra):

    node.get_children(False)
    collection.Count
    collection[index]
    node.get_name(False)
    node.is_folder
    node.type
    node.guid

NUNCA usa: `dir()`; `find()`; `active_application`; documentos textuais
(`textual_declaration`/`textual_implementation`); configuracao de
hardware; qualquer API online; criacao/alteracao/compilacao/salvamento.

Regra estrutural (confirmada em runtime real, probes 06/09/10): um no com
`is_folder == False` PODE ter filhos — `is_folder` e so um metadado
semantico, `get_children(False)` e a fonte real da estrutura. Por isso o
scanner tenta `get_children(False)` em TODO no alcancado, ate os limites
configurados, independente do valor de `is_folder`.

Percurso: DFS ITERATIVO com pilha explicita (nunca recursao Python nem
GetEnumerator()/iter()/list() sobre a colecao CLR) — ver секao 21/22 do
pedido original. Filhos sao lidos em ordem crescente (0..Count-1) e
empilhados em ordem reversa, para que o pop() da pilha os processe na
ordem crescente correta.

Identificacao de no: `node_id` e construido EXCLUSIVAMENTE a partir do
caminho de indices (`root`, `root/0`, `root/1/0`, ...) — nunca a partir do
GUID (alguns nos podem nao expor GUID; o GUID pode falhar isoladamente; o
caminho de indices representa exatamente a navegacao realizada).

Deteccao de ciclos: conservadora. Um `object_guid` repetido em dois
caminhos DIFERENTES e so registrado como `duplicate_object_guid`
(informativo, ambos os nos preservados) — a descida so e bloqueada
(`cycle_detected`) quando o MESMO `object_guid` ja aparece entre os
ANCESTRAIS do proprio no atual (evidencia suficiente de ciclo real).
`handle` nunca e usado como identificador.

Falha na coleção de um no (get_children/Count/interface/indexador) marca
aquele ramo como parcial/incompleto e INTERROMPE apenas aquela coleção —
nunca aborta o scan inteiro. Falha em um campo de identidade (nome/
is_folder/type/guid) nunca impede a leitura dos demais campos do mesmo no,
nem de qualquer outro no. Só dois eventos abortam o scan INTEIRO:
excecao inesperada ja tratada como estado 'unknown' na propria raiz (sem
sequer identidade minima) e o limite global `max_total_nodes` sendo
alcancado — ambos preservam tudo ja coletado.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import json

from common import capabilities, compatibility

DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_TOTAL_NODES = 5000
DEFAULT_MAX_CHILDREN_PER_NODE = 256

_COUNT_BEARING_INTERFACE_PREFIXES = ("ICollection", "IList")

# Estados possiveis de node["collection"]["state"].
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


def _field_result(state, value=None, error=None):
    return {"state": state, "value": value, "error": error}


def _empty_type_info():
    return {"module": None, "name": None}


def _empty_dotnet_info():
    return {"full_name": None, "available": False}


def _implements_count_bearing_interface(value):
    """Reflection sobre o TIPO do valor (GetType().GetInterfaces()) — NUNCA
    toca os DADOS/elementos da colecao. Mesmo helper usado em
    probes/05_children_collection.py, probes/09_device_children_collection.py
    e common/device_first_child_probe.py."""
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
    """1 getattr isolado + representacao estrita (aceita qualquer tipo
    confirmado seguro por build_representation() — string nativa, Guid
    confirmado, etc). Usado para os campos de identidade (name/is_folder/
    type/guid) e para o path/is_root da raiz."""
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
    """`is_folder` deve ser bool; qualquer outro valor vira 'unrepresentable'
    (nao presumimos truthiness de um valor nao-bool)."""
    if field_result["state"] != "confirmed":
        return field_result
    if isinstance(field_result["value"], bool):
        return field_result
    return _field_result(
        "unrepresentable",
        error="valor obtido nao e bool (tipo: %s)." % compatibility.safe_type_name(field_result["value"]))


def _probe_node_identity(proxy, obj_label):
    """Os 4 campos de identidade de um no NAO-RAIZ (IScriptObject):
    name/is_folder/type_guid/object_guid. Cada um isolado; falha em um
    NUNCA impede os demais."""
    return {
        "name": _probe_name_via_method_call(proxy, obj_label),
        "is_folder": _bool_field(_probe_property_via_representation(proxy, obj_label, "is_folder")),
        "type_guid": _probe_property_via_representation(proxy, obj_label, "type"),
        "object_guid": _probe_property_via_representation(proxy, obj_label, "guid"),
    }


def _probe_root_identity(project):
    """path/is_root — os unicos membros confirmados em IScriptProject
    (que NAO implementa IScriptObject: 'type'/'guid'/'get_name' nao se
    aplicam a raiz — ver probes/04_project_identity.py)."""
    return {
        "path": _probe_property_via_representation(project, "project", "path"),
        "is_root": _bool_field(_probe_property_via_representation(project, "project", "is_root")),
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


# Contadores cuja presenca torna a varredura NAO confiavel. Lista FECHADA e
# explicita: um contador novo tem de entrar aqui por decisao, e nao ser
# esquecido de fora -- esquecer de fora e o modo de falha que produz de novo um
# `scan_complete` permissivo.
_COUNTERS_THAT_BREAK_COMPLETENESS = (
    "collection_errors",
    "partial_nodes",
    "failed_nodes",
    "field_errors",
    "index_errors",
)


def _derive_scan_complete(stats, tree_root, limits_hit):
    """`scan_complete` e CONJUNCAO, nunca sinonimo de `traversal_finished`.

    `traversal_finished` responde "o algoritmo terminou?"; `scan_complete`
    responde "o que saiu daqui pode ser lido como a arvore?". Ate o
    R3.1A-3-FIX-2 existia so o primeiro, com o nome do segundo: a run-065 saiu
    `scan_complete: True` com `partial_nodes: 14`, e a diferenca entre
    "nao ha filhos" e "nao sei se ha filhos" desaparecia no campo booleano.

    A raiz entra por `state == confirmed` e nao por contador: uma raiz cuja
    colecao nao confirmou produz arvore de um no so, que passaria por todos os
    contadores zerados -- foi o desfecho da run-049.

    Limite atingido tambem reprova: uma varredura truncada por profundidade ou
    por teto de nos terminou normalmente e nao percorreu a arvore. O limite fica
    registrado em `limits`, e quem quiser aceitar a truncagem le de la; o que
    nao pode e a truncagem sair com o mesmo booleano de uma varredura inteira.
    """
    if not stats.get("traversal_finished"):
        return False
    for contador in _COUNTERS_THAT_BREAK_COMPLETENESS:
        if stats.get(contador):
            return False
    if any(limits_hit.values()):
        return False
    raiz = (tree_root or {}).get("collection") or {}
    return raiz.get("state") == COLLECTION_STATE_CONFIRMED


class ReadOnlyProjectScanner(object):
    """Scanner recursivo (DFS iterativo), somente leitura, com limites
    rigidos. Ver docstring do modulo para as regras completas."""

    def __init__(self, max_depth=DEFAULT_MAX_DEPTH, max_total_nodes=DEFAULT_MAX_TOTAL_NODES,
                max_children_per_node=DEFAULT_MAX_CHILDREN_PER_NODE, expected_root_count=None):
        self.max_depth = max_depth
        self.max_total_nodes = max_total_nodes
        self.max_children_per_node = max_children_per_node
        self.expected_root_count = expected_root_count

    def scan(self, project, visitor=None):
        """Executa UMA varredura completa contra um `project` JA RESOLVIDO.
        Nunca lanca excecao; retorna sempre um dict 100% serializavel (ver
        docstring do modulo, secao 6 da especificacao original, para o
        schema completo).

        `visitor` (opcional, contrato docs/59) e chamado UMA vez por no
        alcancado, com `(node_proxy, record)`, e o que ele devolver entra no
        registro sob "visitor". Ele existe porque a saida deste scanner e 100%
        serializavel de proposito: o proxy vivo e usado e descartado, e ha
        perguntas -- `hasattr(obj, ...)`, `GetType().GetInterfaces()` -- que so
        o objeto vivo responde.

        QUATRO RESTRICOES, cada uma contra uma falha nomeada:

          * ele NAO altera o percurso: nao escolhe filhos, nao poda, nao
            ordena. Um visitante capaz de podar tornaria a varredura dependente
            do chamador, e "arvore inteira ou recusa explicita" deixaria de ser
            verificavel aqui dentro;
          * excecao dele e isolada como falha de RAMO e nao interrompe o scan.
            Derrubar a varredura transformaria erro de classificacao em arvore
            ilegivel -- dois diagnosticos distintos virando um;
          * o valor devolvido tem de ser serializavel, senao a propriedade que
            motiva este parametro se perderia por dentro;
          * `visitor=None` e o comportamento anterior, byte a byte.

        A GARANTIA DESTE MODULO NAO COBRE O VISITANTE. Este scanner promete o
        que ELE chama (nunca `dir()`, `find()`, documento textual, API online,
        criacao/alteracao/compilacao). Um visitante e codigo do CHAMADOR, e a
        garantia sobre a inspecao e dele -- no probe 49, a guarda de AST que
        recusa verbo mutante. Duas garantias, duas portas.
        """
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
            # DOIS campos, e nao um. `traversal_finished` e estado MECANICO: o
            # laco chegou ao fim sem abortar. `scan_complete` e estado
            # EPISTEMICO: a arvore foi percorrida inteira e o que saiu daqui
            # pode ser lido como a arvore. Ate o R3.1A-3-FIX-2 os dois eram o
            # mesmo campo com o nome do segundo e a semantica do primeiro, e a
            # run-065 saiu `scan_complete: True` com 14 nos parciais.
            "traversal_finished": False,
            "scan_complete": False,
        }
        limits_hit = {
            "max_depth_reached": False,
            "max_total_nodes_reached": False,
            "max_children_per_node_reached": False,
        }
        seen_object_guids = {}

        root_identity = _probe_root_identity(project)
        root_runtime = _node_runtime_info(project)

        tree_root = {
            "node_id": "root",
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
            "children": [],
            "cycle_detected": False,
        }

        total_nodes = [1]
        aborted = [False]

        stack = [{
            "proxy": project, "record": tree_root, "obj_label": "project",
            "depth": 0, "ancestor_guids": frozenset([]), "is_root": True,
        }]

        while stack and not aborted[0]:
            frame = stack.pop()
            self._process_node(frame, stack, errors, stats, limits_hit,
                               seen_object_guids, total_nodes, aborted,
                               visitor)

        stats["total_nodes"] = total_nodes[0]
        stats["traversal_finished"] = not aborted[0]
        # `_classify_nodes` e quem preenche partial_nodes/failed_nodes, entao a
        # conjuncao so pode ser derivada DEPOIS dela. Derivar antes daria
        # exatamente o campo permissivo que este slice esta removendo.
        self._classify_nodes(tree_root, stats, is_root=True)
        stats["scan_complete"] = _derive_scan_complete(stats, tree_root,
                                                       limits_hit)

        return {
            "schema_version": "1.0",
            "scanner": {
                "mode": "read_only",
                "max_depth": self.max_depth,
                "max_total_nodes": self.max_total_nodes,
                "max_children_per_node": self.max_children_per_node,
            },
            "root": root_identity,
            "statistics": stats,
            "tree": tree_root,
            "errors": errors,
            "limits": limits_hit,
            "safety_declaration": _SAFETY_DECLARATION,
        }

    def _process_node(self, frame, stack, errors, stats, limits_hit,
                      seen_object_guids, total_nodes, aborted, visitor=None):
        record = frame["record"]
        proxy = frame["proxy"]
        depth = frame["depth"]
        obj_label = frame["obj_label"]
        col = record["collection"]

        # O visitante roda para TODO no alcancado, inclusive o que sera
        # barrado pelo limite de profundidade logo abaixo: ele FOI alcancado e
        # a identidade dele ja esta lida. Chamar so nos nos que descem faria a
        # cobertura do visitante depender de um limite de navegacao.
        if visitor is not None:
            self._run_visitor(visitor, proxy, record, errors, stats)

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

        if frame.get("is_root") and self.expected_root_count is not None:
            matches = (count_value == self.expected_root_count)
            col["expected_count"] = self.expected_root_count
            col["count_matches_expected"] = matches
            if not matches:
                errors.append({
                    "where": record["node_id"],
                    "message": ("root_count_mismatch: esperado Count == %s, obtido %s. "
                               "Nao usado como limite da enumeracao — continuando com "
                               "o valor observado." % (self.expected_root_count, count_value)),
                })

        if count_value > self.max_children_per_node:
            col["state"] = COLLECTION_STATE_CHILDREN_LIMIT_EXCEEDED
            limits_hit["max_children_per_node_reached"] = True
            stats["collection_errors"] += 0  # limite, nao erro de acesso
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
                               "(nenhum indice seguinte tentado); nao — apenas ESTA "
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

    def _run_visitor(self, visitor, proxy, record, errors, stats):
        """Chama o visitante e ISOLA a falha dele.

        Uma excecao aqui e falha de ramo, com a mesma severidade das outras --
        nunca o fim do scan. E o resultado passa por serializacao ANTES de
        entrar no registro: um visitante que devolvesse o proxy vivo destruiria
        em silencio a propriedade que este scanner promete.
        """
        try:
            resultado = visitor(proxy, record)
        except BaseException as exc:                                # noqa: BLE001
            stats["visitor_errors"] = stats.get("visitor_errors", 0) + 1
            errors.append({
                "where": record["node_id"],
                "message": ("falha no visitante: %r. Isolada: o no continua "
                            "registrado e a varredura segue." % (exc,)),
            })
            record["visitor"] = {"state": "visitor_failed"}
            return
        if resultado is None:
            return
        try:
            json.dumps(resultado)
        except (TypeError, ValueError) as exc:
            stats["visitor_errors"] = stats.get("visitor_errors", 0) + 1
            errors.append({
                "where": record["node_id"],
                "message": ("visitante devolveu valor nao serializavel (%s); "
                            "descartado para preservar a saida do scanner."
                            % (exc,)),
            })
            record["visitor"] = {"state": "visitor_unserializable"}
            return
        record["visitor"] = resultado

    def _classify_nodes(self, node, stats, is_root=False):
        """Classifica cada no (complete/partial/failed) e acumula nas
        estatisticas. Percurso recursivo sobre a ARVORE JA CONSTRUIDA
        (dados serializaveis, nao proxies) — profundidade limitada por
        max_depth, sem risco de recursao excessiva."""
        col = node["collection"]
        col_state = col["state"]

        if is_root:
            fields_states = [f["state"] for f in node["identity"].values()] if node["identity"] else []
        else:
            fields_states = [f["state"] for f in node["identity"].values()]

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
    "text_document_access": False,
    "find_used": False,
    "active_application_used": False,
    "compilation": False,
    "online_access": False,
    "device_repository_access": False,
    "device_configuration_access": False,
    "download": False,
    "force": False,
    "collection_direct_iteration": False,
    "bounded_index_navigation": True,
    "recursive_navigation": True,
}


def flatten_tree(tree):
    """Lista achatada de todos os nos da arvore (secao 15). Percurso
    iterativo (pilha explicita), nao recursivo."""
    flat = []
    stack = [tree]
    while stack:
        node = stack.pop()
        name_field = node["identity"].get("name") if node["identity"] else None
        type_guid_field = node["identity"].get("type_guid") if node["identity"] else None
        object_guid_field = node["identity"].get("object_guid") if node["identity"] else None
        flat.append({
            "node_id": node["node_id"],
            "parent_node_id": node["parent_node_id"],
            "depth": node["depth"],
            "index": node["index"],
            "name": name_field["value"] if name_field and name_field["state"] == "confirmed" else None,
            "type_guid": type_guid_field["value"] if type_guid_field and type_guid_field["state"] == "confirmed" else None,
            "object_guid": object_guid_field["value"] if object_guid_field and object_guid_field["state"] == "confirmed" else None,
            "child_count": len(node["children"]),
        })
        for child in reversed(node["children"]):
            stack.append(child)
    # Ordem estavel: node_id crescente por profundidade/indice (a pilha DFS
    # acima ja produz uma ordem de pre-ordem razoavel; ordenar por node_id
    # deixa o arquivo determinista e facil de revisar).
    flat.sort(key=lambda entry: entry["node_id"])
    return flat


def build_node_indexes(flat_nodes):
    """Indices por nome/type_guid/object_guid (secao 15) — somente
    strings/listas serializaveis."""
    nodes_by_name = {}
    nodes_by_type_guid = {}
    nodes_by_object_guid = {}
    for entry in flat_nodes:
        if entry["name"] is not None:
            nodes_by_name.setdefault(entry["name"], []).append(entry["node_id"])
        if entry["type_guid"] is not None:
            nodes_by_type_guid.setdefault(entry["type_guid"], []).append(entry["node_id"])
        if entry["object_guid"] is not None:
            nodes_by_object_guid.setdefault(entry["object_guid"], []).append(entry["node_id"])
    return {
        "nodes_by_name": nodes_by_name,
        "nodes_by_type_guid": nodes_by_type_guid,
        "nodes_by_object_guid": nodes_by_object_guid,
    }

"""Topologia lógica dirigida (`plcopen/logical_topology.py`).

Os 18 casos do contrato (`docs/20-contrato-topologia-logica.md`, §13) mais as
travas que impedem a camada de crescer para além do que ela deve fazer: nada de
releitura do XML, nada de aresta "provável", nada de semântica booleana.

Fixtures sintéticas, construídas diretamente sobre o modelo canônico — a
entrada desta camada é o `GraphicPOU`, não o arquivo.
"""

from __future__ import annotations

import ast
import io
import json
from pathlib import Path

import pytest

from mastertool_bridge.plcopen.canonical_model import (
    ConnectedComponent, ConnectionEvidence, DerivedEdge, Element, GraphicPOU,
    Network, Pin, VendorExtension)
from mastertool_bridge.plcopen.logical_topology import (
    LOGICAL_TOPOLOGY_SCHEMA_VERSION, LogicalTopology, LogicalTopologyError,
    derive_logical_topology)

MODULE_PATH = (Path(__file__).resolve().parents[2] / "src" / "mastertool_bridge"
               / "plcopen" / "logical_topology.py")


# --- construtores de fixture --------------------------------------------------

def _element(local_id, kind, **kw):
    return Element(element_id="el:%s" % local_id, local_id=str(local_id),
                   kind=kind, **kw)


def _pin(local_id, name, direction):
    return Pin(pin_id="pin:%s:%s:%s" % (local_id, direction, name),
               owner_element_id="el:%s" % local_id, formal_parameter=name,
               direction=direction, declaration_source="%sVariables" % direction)


def _evidence(index, source, target, kind="plcopen_connection",
              source_pin=None, target_pin=None):
    return ConnectionEvidence(
        evidence_id="ev:%04d" % index, evidence_kind=kind,
        source_element_ref="el:%s" % source, target_element_ref="el:%s" % target,
        source_pin_raw=source_pin, target_pin_raw=target_pin)


def _derived(source, target, evidence_ids, source_pin=None, target_pin=None,
             status="not_applicable"):
    return DerivedEdge(
        edge_id="edge:el:%s->el:%s#%s" % (source, target, target_pin or "-"),
        source_element_id="el:%s" % source, target_element_id="el:%s" % target,
        supporting_evidence_ids=list(evidence_ids),
        resolved_source_pin=source_pin, resolved_target_pin=target_pin,
        source_pin_resolution_status=status)


def _pou(elements, pins=(), evidence=(), edges=(), networks=(), extensions=()):
    return GraphicPOU(
        name="FB_SINTETICO", pou_type="functionBlock", language="LD",
        source_file="sintetico", elements=list(elements), pins=list(pins),
        connection_evidence=list(evidence), derived_edges=list(edges),
        networks=list(networks), vendor_extensions=list(extensions))


def _network(network_id, element_ids, order=0):
    return Network(network_id=network_id, order=order,
                   element_ids=list(element_ids),
                   reconstruction_status="confirmed_by_marker_and_connectivity")


def _only_network(topology):
    assert len(topology.networks) == 1
    return topology.networks[0]


def _codes(network):
    return {d.code for d in network.diagnostics}


# --- 1. sequência linear ------------------------------------------------------

def _linear_pou():
    """inVariable(1) → contact(2) → coil(3)"""
    return _pou(
        elements=[_element(1, "in_variable"), _element(2, "contact"),
                  _element(3, "coil")],
        evidence=[_evidence(0, 1, 2), _evidence(1, 2, 3)],
        edges=[_derived(1, 2, ["ev:0000"]), _derived(2, 3, ["ev:0001"])],
        networks=[_network("net:0000", ["el:1", "el:2", "el:3"])])


def test_linear_sequence_produces_directed_chain():
    network = _only_network(derive_logical_topology(_linear_pou()))
    assert len(network.edges) == 2
    assert all(e.direction_status == "resolved" for e in network.edges)
    # nós são TERMINAIS: contato e bobina produzem dois cada, inVariable um
    assert len(network.nodes) == 5
    # Sem aresta interna ligando entrada a saida do MESMO elemento, todo
    # terminal de saida e root: nada "entra" nele. Ver o teste dedicado abaixo.
    assert "net:0000|1|output" in network.roots
    assert network.sinks == ["net:0000|3|input"] or "net:0000|3|input" in network.sinks
    chain = {(e.source_node_id, e.target_node_id) for e in network.edges}
    assert ("net:0000|1|output", "net:0000|2|input") in chain
    assert ("net:0000|2|output", "net:0000|3|input") in chain


# --- 2. fan-out e 3. fan-in ---------------------------------------------------

def test_fan_out_is_preserved_as_branch():
    pou = _pou(
        elements=[_element(1, "in_variable"), _element(2, "coil"),
                  _element(3, "coil")],
        evidence=[_evidence(0, 1, 2), _evidence(1, 1, 3)],
        edges=[_derived(1, 2, ["ev:0000"]), _derived(1, 3, ["ev:0001"])],
        networks=[_network("net:0000", ["el:1", "el:2", "el:3"])])
    network = _only_network(derive_logical_topology(pou))
    assert network.branches == ["net:0000|1|output"]
    assert len(network.edges) == 2


def test_fan_in_is_preserved_as_join():
    pou = _pou(
        elements=[_element(1, "in_variable"), _element(2, "in_variable"),
                  _element(3, "coil")],
        evidence=[_evidence(0, 1, 3), _evidence(1, 2, 3)],
        edges=[_derived(1, 3, ["ev:0000"]), _derived(2, 3, ["ev:0001"])],
        networks=[_network("net:0000", ["el:1", "el:2", "el:3"])])
    network = _only_network(derive_logical_topology(pou))
    assert network.joins == ["net:0000|3|input"]


# --- 4. ramificação do fornecedor e 5. duas evidências ------------------------

def test_vendor_parallel_branch_becomes_topology():
    pou = _pou(
        elements=[_element(1, "in_variable"), _element(3, "vendor_element")],
        evidence=[_evidence(0, 1, 3, kind="vendor_parallel_branch")],
        edges=[_derived(1, 3, ["ev:0000"])],
        networks=[_network("net:0000", ["el:1", "el:3"])],
        extensions=[VendorExtension(extension_id="ext:3", owner_id="el:3", namespace=None,
                                    tag="vendorElement",
                                    normalized_classification="ldparallelbranch")])
    network = _only_network(derive_logical_topology(pou))
    assert len(network.edges) == 1
    kinds = {e["evidence_kind"] for e in network.edges[0].evidence}
    assert kinds == {"vendor_parallel_branch"}


def test_two_evidences_one_edge_none_discarded():
    """Uma aresta lógica, duas evidências — nunca duas arestas paralelas nem
    um tipo genérico de evidência."""
    pou = _pou(
        elements=[_element(1, "in_variable"), _element(3, "vendor_element")],
        evidence=[_evidence(0, 1, 3),
                  _evidence(1, 1, 3, kind="vendor_parallel_branch")],
        edges=[_derived(1, 3, ["ev:0000"]),
               DerivedEdge(edge_id="edge:extra", source_element_id="el:1",
                           target_element_id="el:3",
                           supporting_evidence_ids=["ev:0001"])],
        networks=[_network("net:0000", ["el:1", "el:3"])],
        extensions=[VendorExtension(extension_id="ext:3", owner_id="el:3", namespace=None,
                                    tag="vendorElement",
                                    normalized_classification="ldparallelbranch")])
    network = _only_network(derive_logical_topology(pou))
    assert len(network.edges) == 1, "não pode haver arestas paralelas acidentais"
    kinds = sorted(e["evidence_kind"] for e in network.edges[0].evidence)
    assert kinds == ["plcopen_connection", "vendor_parallel_branch"]


# --- 6. pino resolvido e 7. pino ausente --------------------------------------

def test_block_pin_comes_from_the_declared_pin():
    pou = _pou(
        elements=[_element(1, "in_variable"), _element(5, "block", type_name="EQ")],
        pins=[_pin(5, "In1", "input"), _pin(5, "Out1", "output")],
        evidence=[_evidence(0, 1, 5, target_pin="In1")],
        edges=[_derived(1, 5, ["ev:0000"], target_pin="In1")],
        networks=[_network("net:0000", ["el:1", "el:5"])])
    network = _only_network(derive_logical_topology(pou))
    by_id = {n.node_id: n for n in network.nodes}
    assert by_id["net:0000|5|In1"].terminal_role == "declared_pin"
    assert by_id["net:0000|5|In1"].terminal_direction == "input"
    assert network.edges[0].target_node_id == "net:0000|5|In1"


def test_block_without_declared_pins_reports_missing_terminal():
    pou = _pou(elements=[_element(5, "block", type_name="EQ")],
               networks=[_network("net:0000", ["el:5"])])
    network = _only_network(derive_logical_topology(pou))
    assert "missing_terminal" in _codes(network)


# --- 8. direção ambígua e 9. conexão não resolvida ----------------------------

def test_ambiguous_direction_does_not_become_an_edge():
    """Bloco com dois pinos de entrada e nenhum indicado: não há critério
    estrutural para escolher, então não há aresta."""
    pou = _pou(
        elements=[_element(1, "in_variable"), _element(5, "block", type_name="EQ")],
        pins=[_pin(5, "In1", "input"), _pin(5, "In2", "input")],
        evidence=[_evidence(0, 1, 5)],
        edges=[_derived(1, 5, ["ev:0000"])],
        networks=[_network("net:0000", ["el:1", "el:5"])])
    network = _only_network(derive_logical_topology(pou))
    assert network.edges == []
    assert len(network.unresolved_connections) == 1
    assert network.unresolved_connections[0].reason == "ambiguous_direction"


def test_unresolved_connection_keeps_its_evidence():
    pou = _pou(
        elements=[_element(1, "in_variable"), _element(5, "block", type_name="EQ")],
        pins=[_pin(5, "In1", "input"), _pin(5, "In2", "input")],
        evidence=[_evidence(0, 1, 5)],
        edges=[_derived(1, 5, ["ev:0000"])],
        networks=[_network("net:0000", ["el:1", "el:5"])])
    network = _only_network(derive_logical_topology(pou))
    assert network.unresolved_connections[0].evidence_ids == ["ev:0000"]


def test_no_probable_direction_status_exists():
    """`probable` não existe no vocabulário, e o tipo recusa construção de
    aresta com direção não resolvida."""
    from mastertool_bridge.plcopen import logical_topology as module

    assert "probable" not in module.DIRECTION_STATUSES
    with pytest.raises(LogicalTopologyError, match="unresolved_connections"):
        module.LogicalEdge(edge_id="e", network_id="n", source_node_id="a",
                           target_node_id="b", direction_status="unresolved",
                           evidence=[{"evidence_id": "x"}])


# --- 10, 11, 12. ciclo, sem root, sem sink ------------------------------------

def _cyclic_pou():
    """coil(1) → coil(2) → coil(1) no nivel dos ELEMENTOS."""
    return _pou(
        elements=[_element(1, "coil"), _element(2, "coil")],
        evidence=[_evidence(0, 1, 2), _evidence(1, 2, 1)],
        edges=[_derived(1, 2, ["ev:0000"]), _derived(2, 1, ["ev:0001"])],
        networks=[_network("net:0000", ["el:1", "el:2"])])


def test_element_level_loop_is_not_a_terminal_level_cycle():
    """ACHADO da implementacao: com nos-TERMINAIS e sem aresta interna ligando
    entrada a saida do mesmo elemento, um laco entre ELEMENTOS nao produz ciclo
    no grafo de terminais.

    E a aresta interna nao deve existir nesta camada: afirmar que o sinal
    atravessa um contato e afirmar que ele CONDUZ, o que depende do valor da
    variavel -- semantica booleana, fora deste slice.
    """
    network = _only_network(derive_logical_topology(_cyclic_pou()))
    assert len(network.edges) == 2
    assert network.cycles == []


def test_cycle_detection_works_on_a_real_directed_cycle():
    """O detector existe e funciona; o que a camada nao produz hoje e a aresta
    interna que fecharia um ciclo."""
    from mastertool_bridge.plcopen import logical_topology as module

    node_a = module.LogicalNode(
        node_id="n|a", network_id="n", owner_element_id="el:1",
        owner_local_id="1", owner_kind="coil", terminal_name="a",
        terminal_direction="output", terminal_role="element_contract")
    node_b = module.LogicalNode(
        node_id="n|b", network_id="n", owner_element_id="el:2",
        owner_local_id="2", owner_kind="coil", terminal_name="b",
        terminal_direction="input", terminal_role="element_contract")
    edge_ab = module.LogicalEdge(
        edge_id="n|a->b", network_id="n", source_node_id="n|a",
        target_node_id="n|b", direction_status="resolved",
        evidence=[{"evidence_id": "ev:0000"}])
    edge_ba = module.LogicalEdge(
        edge_id="n|b->a", network_id="n", source_node_id="n|b",
        target_node_id="n|a", direction_status="resolved",
        evidence=[{"evidence_id": "ev:0001"}])

    cycles = module._find_cycles("n", [node_a, node_b], [edge_ab, edge_ba])
    assert len(cycles) == 1
    assert sorted(cycles[0].node_ids) == ["n|a", "n|b"]
    assert cycles[0].detection_method == "dfs_back_edge"


def test_cycle_is_informative_never_fatal():
    """Realimentacao e construcao legitima; validade e juizo semantico."""
    from mastertool_bridge.plcopen import logical_topology as module

    for code in ("cycle_detected", "network_without_root", "network_without_sink"):
        assert module.DIAGNOSTIC_SEVERITIES[code] == "info"


# --- 13. redes isoladas e 14. conexão entre redes -----------------------------

def test_isolated_networks_do_not_contaminate_each_other():
    pou = _pou(
        elements=[_element(1, "in_variable"), _element(2, "coil"),
                  _element(3, "in_variable"), _element(4, "coil")],
        evidence=[_evidence(0, 1, 2), _evidence(1, 3, 4)],
        edges=[_derived(1, 2, ["ev:0000"]), _derived(3, 4, ["ev:0001"])],
        networks=[_network("net:0000", ["el:1", "el:2"], order=0),
                  _network("net:0001", ["el:3", "el:4"], order=1)])
    topology = derive_logical_topology(pou)
    assert len(topology.networks) == 2
    for network in topology.networks:
        assert len(network.edges) == 1
        assert {n.network_id for n in network.nodes} == {network.network_id}


def test_cross_network_connection_is_an_error():
    pou = _pou(
        elements=[_element(1, "in_variable"), _element(2, "coil"),
                  _element(3, "in_variable"), _element(4, "coil")],
        evidence=[_evidence(0, 1, 4)],
        edges=[_derived(1, 4, ["ev:0000"])],
        networks=[_network("net:0000", ["el:1", "el:2"], order=0),
                  _network("net:0001", ["el:3", "el:4"], order=1)])
    topology = derive_logical_topology(pou)
    codes = set()
    for network in topology.networks:
        codes |= _codes(network)
        assert not network.edges or all(
            e.source_node_id.startswith(network.network_id) for e in network.edges)
    assert "cross_network_connection" in codes

    from mastertool_bridge.plcopen import logical_topology as module
    assert module.DIAGNOSTIC_SEVERITIES["cross_network_connection"] == "error"


def test_connection_from_unassigned_element_is_not_an_error():
    """O trilho esquerdo fica fora das redes por decisão do canônico. A conexão
    trilho → rede tem uma ponta sem rede, e isso é esperado — não o mesmo que
    atravessar duas redes."""
    from mastertool_bridge.plcopen import logical_topology as module

    pou = _pou(
        elements=[_element(0, "left_power_rail"), _element(2, "coil")],
        evidence=[_evidence(0, 0, 2)],
        edges=[_derived(0, 2, ["ev:0000"])],
        networks=[_network("net:0000", ["el:2"])])
    pou.unassigned_elements = ["el:0"]
    network = _only_network(derive_logical_topology(pou))

    reasons = {u.reason for u in network.unresolved_connections}
    assert reasons == {"unassigned_element_connection"}
    assert module.DIAGNOSTIC_SEVERITIES["unassigned_element_connection"] == "info"
    assert not [d for d in network.diagnostics if d.severity == "error"]


# --- 15, 16, 17. posição, determinismo, rastreabilidade -----------------------

def test_zero_positions_do_not_influence_the_output():
    """Todas as posições são (0,0) no export real; a topologia tem de sair
    igual com ou sem elas."""
    from mastertool_bridge.plcopen.canonical_model import Position

    plain = derive_logical_topology(_linear_pou()).to_dict()

    with_positions = _linear_pou()
    for element in with_positions.elements:
        element.position = Position(x=0, y=0, usable_for_topology=False)
    assert derive_logical_topology(with_positions).to_dict() == plain


def test_input_order_does_not_change_the_output():
    forward = derive_logical_topology(_linear_pou()).to_dict()

    reversed_pou = _linear_pou()
    reversed_pou.elements.reverse()
    reversed_pou.derived_edges.reverse()
    reversed_pou.connection_evidence.reverse()
    assert derive_logical_topology(reversed_pou).to_dict() == forward


def test_serialization_is_deterministic():
    first = json.dumps(derive_logical_topology(_linear_pou()).to_dict(),
                       ensure_ascii=False)
    second = json.dumps(derive_logical_topology(_linear_pou()).to_dict(),
                        ensure_ascii=False)
    assert first == second


def test_round_trip_preserves_the_topology():
    original = derive_logical_topology(_linear_pou()).to_dict()
    assert LogicalTopology.from_dict(original).to_dict() == original


def test_every_node_and_edge_is_traceable():
    network = _only_network(derive_logical_topology(_linear_pou()))
    for node in network.nodes:
        assert node.owner_local_id and node.owner_element_id
        assert node.terminal_name
    for edge in network.edges:
        assert edge.evidence and all(e["evidence_id"] for e in edge.evidence)
        assert edge.source.get("canonical_edge_id")


# --- travas explícitas --------------------------------------------------------

def test_module_never_reads_xml():
    """A entrada é o modelo canônico. Reler o XML criaria uma segunda
    interpretação do mesmo documento."""
    source = io.open(MODULE_PATH, encoding="utf-8").read()
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    for forbidden in ("xml", "lxml"):
        assert forbidden not in imported
    for token in ("ElementTree", "parse_ladder", "map_structure", "open("):
        assert token not in source, "camada não deve alcançar o XML: %r" % token


def test_no_boolean_semantics_in_this_layer():
    """`negated`, `edge`, `storage` continuam nos elementos canônicos e
    acessíveis — a topologia apenas não os interpreta."""
    source = io.open(MODULE_PATH, encoding="utf-8").read()
    tree = ast.parse(source)
    identifiers = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    identifiers |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for forbidden in ("negated", "storage", "normally_open", "normally_closed",
                      "rising_edge", "falling_edge", "evaluate", "truth_value"):
        assert forbidden not in identifiers, (
            "semântica booleana não pertence a esta camada: %r" % forbidden)


def test_declared_pin_and_element_contract_stay_distinguishable():
    pou = _pou(
        elements=[_element(2, "contact"), _element(5, "block", type_name="EQ")],
        pins=[_pin(5, "In1", "input")],
        networks=[_network("net:0000", ["el:2", "el:5"])])
    network = _only_network(derive_logical_topology(pou))
    roles = {n.node_id: n.terminal_role for n in network.nodes}
    assert roles["net:0000|2|input"] == "element_contract"
    assert roles["net:0000|5|In1"] == "declared_pin"


def test_not_observed_kinds_get_no_presumed_terminals():
    """Ausência de observação não é prova de ausência de suporte: o nó existe
    com `unknown`, sem terminal inventado e sem virar `unsupported`."""
    pou = _pou(elements=[_element(9, "jump")],
               networks=[_network("net:0000", ["el:9"])])
    network = _only_network(derive_logical_topology(pou))
    assert len(network.nodes) == 1
    node = network.nodes[0]
    assert node.terminal_direction == "unknown"
    assert node.terminal_role == "inferred_absent"
    assert "unknown_terminal_direction" in _codes(network)


def test_schema_version_is_its_own_family():
    from mastertool_bridge.plcopen import canonical_model, structure_map

    assert LOGICAL_TOPOLOGY_SCHEMA_VERSION == 1
    assert isinstance(LOGICAL_TOPOLOGY_SCHEMA_VERSION, int)
    # constante própria: coincidir no valor não pode virar acoplamento
    from mastertool_bridge.plcopen import logical_topology
    assert "LOGICAL_TOPOLOGY_SCHEMA_VERSION" in dir(logical_topology)
    assert canonical_model.SCHEMA_VERSION == 1
    assert structure_map.STRUCTURE_MAP_SCHEMA_VERSION == 1


def test_from_dict_rejects_a_foreign_schema_version():
    payload = derive_logical_topology(_linear_pou()).to_dict()
    payload["schema_version"] = "1.0"
    with pytest.raises(LogicalTopologyError, match="schema_version"):
        LogicalTopology.from_dict(payload)


def test_unresolved_connections_never_appear_in_edges():
    pou = _pou(
        elements=[_element(1, "in_variable"), _element(5, "block", type_name="EQ")],
        pins=[_pin(5, "In1", "input"), _pin(5, "In2", "input")],
        evidence=[_evidence(0, 1, 5)],
        edges=[_derived(1, 5, ["ev:0000"])],
        networks=[_network("net:0000", ["el:1", "el:5"])])
    network = _only_network(derive_logical_topology(pou))
    unresolved_ids = {u.connection_id for u in network.unresolved_connections}
    edge_sources = {e.source.get("canonical_edge_id") for e in network.edges}
    assert not (unresolved_ids & edge_sources)


# --- 18. POU real -------------------------------------------------------------

REAL_EXPORT = Path(
    "C:/mastertool-rankine-bridge-runs/2026-07-29_10-14-54/output/plcopen-export"
    "/export-root/pou-export")


def test_real_pou_reproduces_the_documented_numbers():
    """Oráculo de regressão (`docs/20`, §14). Divergência é achado, não alvo a
    ser forçado."""
    if not REAL_EXPORT.is_file():
        pytest.skip("export real nao disponivel neste ambiente")

    from mastertool_bridge.plcopen.ladder_parser import parse_ladder

    pou = parse_ladder(REAL_EXPORT)
    topology = derive_logical_topology(pou)

    assert len(topology.networks) == 4
    assert len(topology.all_nodes()) == 66
    assert len(topology.all_edges()) == 26

    unresolved = [u for n in topology.networks for u in n.unresolved_connections]
    assert len(unresolved) == 6
    assert {u.reason for u in unresolved} == {"unassigned_element_connection"}

    errors = [d for n in topology.networks for d in n.diagnostics
              if d.severity == "error"]
    assert not errors

    referenced = set()
    for network in topology.networks:
        for edge in network.edges:
            referenced.update(e["evidence_id"] for e in edge.evidence)
        for item in network.unresolved_connections:
            referenced.update(item.evidence_ids)
    assert referenced == {e.evidence_id for e in pou.connection_evidence}

    twice = derive_logical_topology(parse_ladder(REAL_EXPORT)).to_dict()
    assert twice == topology.to_dict()

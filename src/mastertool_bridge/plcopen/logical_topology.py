"""Topologia lógica dirigida de uma POU Ladder.

Camada intermediária entre a estrutura canônica e qualquer interpretação de
comportamento (`docs/20-contrato-topologia-logica.md`):

    evidência PLCopen → estrutura canônica → topologia lógica dirigida
                                            → semântica booleana

Este módulo termina na topologia dirigida. Ele responde quais terminais estão
ligados, em que direção, onde há ramificação e convergência — e **nada** sobre
o que a lógica faz. `negated`, `edge`, `storage`, `type_name` continuam nos
elementos canônicos, acessíveis por `owner_element_id`; aqui não são
interpretados.

**A entrada é exclusivamente o `GraphicPOU`.** Este módulo não abre o XML e não
importa nada que o faça: reler criaria uma segunda interpretação do mesmo
documento, e as duas divergiriam com o tempo. Se um dado necessário não está no
modelo canônico, a lacuna se resolve no parser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Versão do contrato DESTA família de artefato, inteiro. Constante própria: a
# topologia evolui num ritmo que não é o do modelo canônico nem o do mapa
# estrutural (`docs/19-contratos-de-execucao.md`, seção 7).
LOGICAL_TOPOLOGY_SCHEMA_VERSION = 1

MODEL_KIND = "logical_topology"

TERMINAL_DIRECTIONS = ("input", "output", "inout", "unknown")

# Como a direção do terminal foi determinada. Distinguir as duas primeiras
# importa: um pino declarado está escrito no arquivo; um terminal de contrato
# decorre do tipo do elemento e nunca aparece no XML.
TERMINAL_ROLES = ("declared_pin", "element_contract", "inferred_absent")

RESOLUTION_STATUSES = ("resolved", "partially_resolved", "ambiguous", "unresolved")

# `probable` NÃO existe de propósito: uma topologia com arestas prováveis é
# indistinguível de uma topologia errada.
DIRECTION_STATUSES = RESOLUTION_STATUSES

# Terminais que decorrem do TIPO do elemento — não são declarados em lugar
# nenhum do XML. Só os tipos com evidência real entram aqui; os demais ficam
# `unknown` com diagnóstico, nunca com terminal presumido.
ELEMENT_TERMINAL_CONTRACT = {
    "contact": (("input", "input"), ("output", "output")),
    "coil": (("input", "input"), ("output", "output")),
    "in_variable": (("output", "output"),),
    "out_variable": (("input", "input"),),
    "left_power_rail": (("output", "output"),),
    "right_power_rail": (("input", "input"),),
}

# `vendorElement` depende da extensão que carrega. O marcador de rede não
# participa de conexão nenhuma; o paralelo do fornecedor é ponto de
# convergência e tem os dois terminais.
VENDOR_TERMINAL_CONTRACT = {
    "ldparallelbranch": (("input", "input"), ("output", "output")),
    "networktitle": (),
}

# Tipos modelados no canônico que ainda NÃO foram observados num export real.
# Não recebem contrato por antecipação — ausência de observação não é prova de
# ausência de suporte.
NOT_OBSERVED_KINDS = frozenset({
    "inout_variable", "connector", "continuation", "jump", "label", "return",
})

DIAGNOSTIC_SEVERITIES = {
    "missing_terminal": "warning",
    "unknown_terminal_direction": "warning",
    "unresolved_source_reference": "warning",
    "unresolved_target_reference": "warning",
    "ambiguous_direction": "warning",
    "orphan_terminal": "info",
    "duplicate_edge_evidence": "warning",
    "cross_network_connection": "error",
    # Conexão em que uma das pontas é elemento que o canônico deixou em
    # `unassigned_elements` — tipicamente o trilho esquerdo alimentando a rede.
    # NÃO é o mesmo que atravessar duas redes: aqui não há segmentação
    # inconsistente, há um elemento deliberadamente fora das redes lógicas.
    # Informativo, portanto, e não erro.
    "unassigned_element_connection": "info",
    "cycle_detected": "info",
    "network_without_root": "info",
    "network_without_sink": "info",
}


class LogicalTopologyError(Exception):
    """Invariante da topologia violada."""


def _sorted_unique(values) -> list:
    return sorted(set(values))


# --- tipos --------------------------------------------------------------------

@dataclass
class TopologyDiagnostic:
    code: str
    message: str
    severity: str = "info"
    refs: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.code in DIAGNOSTIC_SEVERITIES:
            self.severity = DIAGNOSTIC_SEVERITIES[self.code]

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message,
                "severity": self.severity, "refs": _sorted_unique(self.refs)}

    @classmethod
    def from_dict(cls, data: dict) -> TopologyDiagnostic:
        item = cls(code=data["code"], message=data["message"],
                   refs=list(data.get("refs") or []))
        item.severity = data.get("severity", item.severity)
        return item


@dataclass
class LogicalNode:
    """Um TERMINAL, não um elemento. Um contato produz dois nós."""

    node_id: str
    network_id: str
    owner_element_id: str
    owner_local_id: str | None
    owner_kind: str
    terminal_name: str
    terminal_direction: str
    terminal_role: str
    resolution_status: str = "resolved"
    source: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.terminal_direction not in TERMINAL_DIRECTIONS:
            raise LogicalTopologyError(
                f"terminal_direction inválida: {self.terminal_direction!r}")
        if self.terminal_role not in TERMINAL_ROLES:
            raise LogicalTopologyError(
                f"terminal_role inválido: {self.terminal_role!r}")
        if self.resolution_status not in RESOLUTION_STATUSES:
            raise LogicalTopologyError(
                f"resolution_status inválido: {self.resolution_status!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id, "network_id": self.network_id,
            "owner_element_id": self.owner_element_id,
            "owner_local_id": self.owner_local_id,
            "owner_kind": self.owner_kind,
            "terminal_name": self.terminal_name,
            "terminal_direction": self.terminal_direction,
            "terminal_role": self.terminal_role,
            "resolution_status": self.resolution_status,
            "source": dict(sorted(self.source.items())),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }

    @classmethod
    def from_dict(cls, data: dict) -> LogicalNode:
        return cls(
            node_id=data["node_id"], network_id=data["network_id"],
            owner_element_id=data["owner_element_id"],
            owner_local_id=data.get("owner_local_id"),
            owner_kind=data["owner_kind"],
            terminal_name=data["terminal_name"],
            terminal_direction=data["terminal_direction"],
            terminal_role=data["terminal_role"],
            resolution_status=data.get("resolution_status", "resolved"),
            source=dict(data.get("source") or {}),
            diagnostics=[TopologyDiagnostic.from_dict(d)
                         for d in data.get("diagnostics") or []])


@dataclass
class LogicalEdge:
    """Liga TERMINAL a TERMINAL. Nunca elemento a elemento."""

    edge_id: str
    network_id: str
    source_node_id: str
    target_node_id: str
    direction_status: str
    evidence: list = field(default_factory=list)
    resolution_status: str = "resolved"
    source: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.direction_status not in DIRECTION_STATUSES:
            raise LogicalTopologyError(
                f"direction_status inválido: {self.direction_status!r}")
        if self.direction_status in ("ambiguous", "unresolved"):
            raise LogicalTopologyError(
                f"aresta {self.edge_id!r} com direção {self.direction_status!r} "
                "— conexão não resolvida pertence a unresolved_connections, "
                "nunca a edges")
        if not self.evidence:
            raise LogicalTopologyError(
                f"aresta {self.edge_id!r} sem evidência — toda aresta aponta "
                "para o que a justifica")

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id, "network_id": self.network_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "direction_status": self.direction_status,
            "evidence": [dict(sorted(e.items())) for e in
                         sorted(self.evidence, key=lambda e: e.get("evidence_id", ""))],
            "resolution_status": self.resolution_status,
            "source": dict(sorted(self.source.items())),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }

    @classmethod
    def from_dict(cls, data: dict) -> LogicalEdge:
        return cls(
            edge_id=data["edge_id"], network_id=data["network_id"],
            source_node_id=data["source_node_id"],
            target_node_id=data["target_node_id"],
            direction_status=data["direction_status"],
            evidence=[dict(e) for e in data.get("evidence") or []],
            resolution_status=data.get("resolution_status", "resolved"),
            source=dict(data.get("source") or {}),
            diagnostics=[TopologyDiagnostic.from_dict(d)
                         for d in data.get("diagnostics") or []])


@dataclass
class UnresolvedConnection:
    connection_id: str
    network_id: str | None
    evidence_ids: list = field(default_factory=list)
    reason: str = "unresolved"
    candidate_nodes: list = field(default_factory=list)
    source: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id, "network_id": self.network_id,
            "evidence_ids": _sorted_unique(self.evidence_ids),
            "reason": self.reason,
            "candidate_nodes": _sorted_unique(self.candidate_nodes),
            "source": dict(sorted(self.source.items())),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }

    @classmethod
    def from_dict(cls, data: dict) -> UnresolvedConnection:
        return cls(
            connection_id=data["connection_id"],
            network_id=data.get("network_id"),
            evidence_ids=list(data.get("evidence_ids") or []),
            reason=data.get("reason", "unresolved"),
            candidate_nodes=list(data.get("candidate_nodes") or []),
            source=dict(data.get("source") or {}),
            diagnostics=[TopologyDiagnostic.from_dict(d)
                         for d in data.get("diagnostics") or []])


@dataclass
class LogicalCycle:
    cycle_id: str
    node_ids: list = field(default_factory=list)
    edge_ids: list = field(default_factory=list)
    detection_method: str = "dfs_back_edge"
    source: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"cycle_id": self.cycle_id,
                "node_ids": _sorted_unique(self.node_ids),
                "edge_ids": _sorted_unique(self.edge_ids),
                "detection_method": self.detection_method,
                "source": dict(sorted(self.source.items()))}

    @classmethod
    def from_dict(cls, data: dict) -> LogicalCycle:
        return cls(cycle_id=data["cycle_id"],
                   node_ids=list(data.get("node_ids") or []),
                   edge_ids=list(data.get("edge_ids") or []),
                   detection_method=data.get("detection_method", "dfs_back_edge"),
                   source=dict(data.get("source") or {}))


@dataclass
class LogicalNetwork:
    network_id: str
    source_network_id: str | None = None
    order: int = 0
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    roots: list = field(default_factory=list)
    sinks: list = field(default_factory=list)
    branches: list = field(default_factory=list)
    joins: list = field(default_factory=list)
    cycles: list = field(default_factory=list)
    unresolved_connections: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)
    source: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "network_id": self.network_id,
            "source_network_id": self.source_network_id,
            "order": self.order,
            "nodes": [n.to_dict() for n in sorted(self.nodes, key=lambda n: n.node_id)],
            "edges": [e.to_dict() for e in sorted(self.edges, key=lambda e: e.edge_id)],
            "roots": _sorted_unique(self.roots),
            "sinks": _sorted_unique(self.sinks),
            "branches": _sorted_unique(self.branches),
            "joins": _sorted_unique(self.joins),
            "cycles": [c.to_dict() for c in sorted(self.cycles, key=lambda c: c.cycle_id)],
            "unresolved_connections": [
                u.to_dict() for u in sorted(self.unresolved_connections,
                                            key=lambda u: u.connection_id)],
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "source": dict(sorted(self.source.items())),
        }

    @classmethod
    def from_dict(cls, data: dict) -> LogicalNetwork:
        return cls(
            network_id=data["network_id"],
            source_network_id=data.get("source_network_id"),
            order=int(data.get("order", 0)),
            nodes=[LogicalNode.from_dict(n) for n in data.get("nodes") or []],
            edges=[LogicalEdge.from_dict(e) for e in data.get("edges") or []],
            roots=list(data.get("roots") or []),
            sinks=list(data.get("sinks") or []),
            branches=list(data.get("branches") or []),
            joins=list(data.get("joins") or []),
            cycles=[LogicalCycle.from_dict(c) for c in data.get("cycles") or []],
            unresolved_connections=[
                UnresolvedConnection.from_dict(u)
                for u in data.get("unresolved_connections") or []],
            diagnostics=[TopologyDiagnostic.from_dict(d)
                         for d in data.get("diagnostics") or []],
            source=dict(data.get("source") or {}))


@dataclass
class LogicalTopology:
    pou_identity: dict = field(default_factory=dict)
    networks: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)
    source: dict = field(default_factory=dict)
    schema_version: int = LOGICAL_TOPOLOGY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_kind": MODEL_KIND,
            "pou_identity": dict(sorted(self.pou_identity.items())),
            "networks": [n.to_dict() for n in
                         sorted(self.networks, key=lambda n: (n.order, n.network_id))],
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "source": dict(sorted(self.source.items())),
        }

    @classmethod
    def from_dict(cls, data: dict) -> LogicalTopology:
        if data.get("model_kind") != MODEL_KIND:
            raise LogicalTopologyError(
                f"model_kind inesperado: {data.get('model_kind')!r}")
        if data.get("schema_version") != LOGICAL_TOPOLOGY_SCHEMA_VERSION:
            raise LogicalTopologyError(
                f"schema_version não suportada: {data.get('schema_version')!r} "
                f"(este módulo lê {LOGICAL_TOPOLOGY_SCHEMA_VERSION})")
        return cls(
            pou_identity=dict(data.get("pou_identity") or {}),
            networks=[LogicalNetwork.from_dict(n) for n in data.get("networks") or []],
            diagnostics=[TopologyDiagnostic.from_dict(d)
                         for d in data.get("diagnostics") or []],
            source=dict(data.get("source") or {}),
            schema_version=data.get("schema_version",
                                    LOGICAL_TOPOLOGY_SCHEMA_VERSION))

    # --- consultas ------------------------------------------------------------

    def network_by_id(self, network_id: str):
        for network in self.networks:
            if network.network_id == network_id:
                return network
        return None

    def all_nodes(self) -> list:
        return [n for network in self.networks for n in network.nodes]

    def all_edges(self) -> list:
        return [e for network in self.networks for e in network.edges]


# --- derivação ----------------------------------------------------------------

def _node_id(network_id: str, local_id, terminal_name: str) -> str:
    return "%s|%s|%s" % (network_id, local_id, terminal_name)


def _terminal_contract_for(element, vendor_classification):
    """Terminais que decorrem do TIPO. Devolve `(terminais, observado)`."""
    if element.kind == "vendor_element":
        if vendor_classification in VENDOR_TERMINAL_CONTRACT:
            return VENDOR_TERMINAL_CONTRACT[vendor_classification], True
        return (), False
    if element.kind in ELEMENT_TERMINAL_CONTRACT:
        return ELEMENT_TERMINAL_CONTRACT[element.kind], True
    if element.kind in ("block", "comment"):
        return (), True
    return (), False


def _build_nodes(pou, network, network_id, vendor_class_by_owner):
    """Registro determinístico `(owner_local_id, terminal_name) -> LogicalNode`."""
    elements = {e.element_id: e for e in pou.elements}
    pins_by_owner: dict = {}
    for pin in pou.pins:
        pins_by_owner.setdefault(pin.owner_element_id, []).append(pin)

    nodes: list = []
    diagnostics: list = []
    for element_id in sorted(network.element_ids):
        element = elements.get(element_id)
        if element is None:
            continue

        if element.kind == "block":
            pins = sorted(pins_by_owner.get(element_id, []),
                          key=lambda p: (p.direction, p.formal_parameter or ""))
            if not pins:
                diagnostics.append(TopologyDiagnostic(
                    code="missing_terminal",
                    message="bloco %s não declara nenhum pino" % element.local_id,
                    refs=[element_id]))
            for pin in pins:
                name = pin.formal_parameter or "?"
                nodes.append(LogicalNode(
                    node_id=_node_id(network_id, element.local_id, name),
                    network_id=network_id, owner_element_id=element_id,
                    owner_local_id=element.local_id, owner_kind=element.kind,
                    terminal_name=name, terminal_direction=pin.direction,
                    terminal_role="declared_pin",
                    source={"pin_id": pin.pin_id,
                            "declaration_source": pin.declaration_source or ""}))
            continue

        contract, observed = _terminal_contract_for(
            element, vendor_class_by_owner.get(element_id))
        if not observed:
            # Tipo modelado mas nunca observado, ou extensão desconhecida: o nó
            # existe com direção `unknown` e diagnóstico. Omiti-lo faria a
            # topologia afirmar uma conectividade que o arquivo não tem;
            # inventar terminais seria pior ainda.
            nodes.append(LogicalNode(
                node_id=_node_id(network_id, element.local_id, "unknown"),
                network_id=network_id, owner_element_id=element_id,
                owner_local_id=element.local_id, owner_kind=element.kind,
                terminal_name="unknown", terminal_direction="unknown",
                terminal_role="inferred_absent", resolution_status="unresolved",
                diagnostics=[TopologyDiagnostic(
                    code="unknown_terminal_direction",
                    message="tipo %r sem contrato de terminais observado — "
                            "nenhum terminal presumido" % element.kind,
                    refs=[element_id])]))
            diagnostics.append(TopologyDiagnostic(
                code="unknown_terminal_direction",
                message="elemento %s (%s) sem contrato de terminais"
                        % (element.local_id, element.kind),
                refs=[element_id]))
            continue

        for terminal_name, direction in contract:
            nodes.append(LogicalNode(
                node_id=_node_id(network_id, element.local_id, terminal_name),
                network_id=network_id, owner_element_id=element_id,
                owner_local_id=element.local_id, owner_kind=element.kind,
                terminal_name=terminal_name, terminal_direction=direction,
                terminal_role="element_contract"))
    return nodes, diagnostics


def _pick_terminal(nodes_by_element, element_id, wanted_direction, preferred_name):
    """Terminal de um elemento na direção pedida.

    `preferred_name` vem do pino JÁ RESOLVIDO pelo canônico. Quando não há
    preferência e o elemento tem exatamente um terminal naquela direção, ele é
    identificado sem ambiguidade — é o caso de contato, bobina e trilho, cujo
    contrato define um único terminal de cada lado.

    Devolve `(node, status)` com status em resolved/ambiguous/unresolved.
    """
    candidates = [n for n in nodes_by_element.get(element_id, [])
                  if n.terminal_direction in (wanted_direction, "inout")]
    if not candidates:
        return None, "unresolved"
    if preferred_name:
        exact = [n for n in candidates if n.terminal_name == preferred_name]
        if len(exact) == 1:
            return exact[0], "resolved"
        if len(exact) > 1:
            return None, "ambiguous"
        return None, "unresolved"
    if len(candidates) == 1:
        return candidates[0], "resolved"
    return None, "ambiguous"


def _network_of_element(element_to_network, element_id):
    return element_to_network.get(element_id)


def _find_cycles(network_id, nodes, edges):
    """Ciclos por DFS iterativa sobre o grafo dirigido.

    Detecta e registra; NUNCA rejeita a rede. Realimentação é construção
    legítima em Ladder, e julgar validade exige informação que esta camada não
    tem.
    """
    adjacency: dict = {n.node_id: [] for n in nodes}
    for edge in sorted(edges, key=lambda e: e.edge_id):
        adjacency.setdefault(edge.source_node_id, []).append(edge)

    WHITE, GREY, BLACK = 0, 1, 2
    color = {node_id: WHITE for node_id in adjacency}
    cycles: list = []
    seen_signatures: set = set()

    for start in sorted(adjacency):
        if color[start] != WHITE:
            continue
        stack = [(start, iter(adjacency.get(start, ())))]
        path_nodes = [start]
        path_edges: list = []
        color[start] = GREY
        while stack:
            current, iterator = stack[-1]
            advanced = False
            for edge in iterator:
                target = edge.target_node_id
                if target not in color:
                    continue
                if color[target] == GREY:
                    # aresta de retorno: fecha um ciclo
                    if target in path_nodes:
                        index = path_nodes.index(target)
                        cycle_nodes = path_nodes[index:]
                        cycle_edges = [e.edge_id for e in path_edges[index:]] + [edge.edge_id]
                    else:
                        cycle_nodes, cycle_edges = [target], [edge.edge_id]
                    signature = tuple(sorted(set(cycle_nodes)))
                    if signature not in seen_signatures:
                        seen_signatures.add(signature)
                        cycles.append(LogicalCycle(
                            cycle_id="%s|cycle|%s" % (network_id, min(signature)),
                            node_ids=list(cycle_nodes), edge_ids=cycle_edges))
                    continue
                if color[target] == WHITE:
                    color[target] = GREY
                    stack.append((target, iter(adjacency.get(target, ()))))
                    path_nodes.append(target)
                    path_edges.append(edge)
                    advanced = True
                    break
            if not advanced:
                color[current] = BLACK
                stack.pop()
                if path_nodes:
                    path_nodes.pop()
                if path_edges:
                    path_edges.pop()
    return sorted(cycles, key=lambda c: c.cycle_id)


def derive_logical_topology(pou) -> LogicalTopology:
    """`GraphicPOU` → `LogicalTopology`. Não lê o XML."""
    vendor_class_by_owner = {
        extension.owner_id: extension.normalized_classification
        for extension in pou.vendor_extensions if extension.owner_id}

    element_to_network: dict = {}
    for network in pou.networks:
        for element_id in network.element_ids:
            element_to_network[element_id] = network.network_id

    evidence_by_id = {e.evidence_id: e for e in pou.connection_evidence}

    topology_diagnostics: list = []
    logical_networks: list = []

    for order, network in enumerate(
            sorted(pou.networks, key=lambda n: (n.order, n.network_id))):
        network_id = network.network_id
        nodes, node_diagnostics = _build_nodes(
            pou, network, network_id, vendor_class_by_owner)
        nodes_by_element: dict = {}
        for node in nodes:
            nodes_by_element.setdefault(node.owner_element_id, []).append(node)

        edges: list = []
        unresolved: list = []
        network_diagnostics = list(node_diagnostics)

        # Uma DerivedEdge canônica pode virar uma aresta lógica, ou não virar
        # nenhuma. Nunca vira "provável".
        edges_by_key: dict = {}
        for derived in sorted(pou.derived_edges, key=lambda e: e.edge_id):
            source_network = _network_of_element(
                element_to_network, derived.source_element_id)
            target_network = _network_of_element(
                element_to_network, derived.target_element_id)
            if network_id not in (source_network, target_network):
                continue

            evidence_records = []
            for evidence_id in sorted(derived.supporting_evidence_ids):
                evidence = evidence_by_id.get(evidence_id)
                if evidence is None:
                    continue
                evidence_records.append({
                    "evidence_id": evidence.evidence_id,
                    "evidence_kind": evidence.evidence_kind,
                    "source_pin_raw": evidence.source_pin_raw,
                    "target_pin_raw": evidence.target_pin_raw,
                })

            if source_network != target_network:
                # Duas situações que NÃO são a mesma coisa:
                #
                # - uma das pontas está fora de qualquer rede (o canônico a
                #   deixou em `unassigned_elements`): é o trilho alimentando a
                #   rede, esperado e informativo. O elemento não tem nó em rede
                #   nenhuma, então não há aresta a criar — mas nada está errado;
                # - as duas pontas estão em redes DIFERENTES: aí sim a
                #   segmentação ou a resolução de referências está inconsistente,
                #   e seguir produziria topologia falsa.
                #
                # Tratar as duas como erro faria o trilho — presente em toda
                # rede real — parecer defeito estrutural.
                unassigned = source_network is None or target_network is None
                code = ("unassigned_element_connection" if unassigned
                        else "cross_network_connection")
                message = (
                    "conexão com elemento fora das redes lógicas (%s -> %s)"
                    if unassigned else
                    "conexão entre redes distintas (%s -> %s)") % (
                        source_network, target_network)
                diagnostic = TopologyDiagnostic(
                    code=code, message=message, refs=[derived.edge_id])
                network_diagnostics.append(diagnostic)
                unresolved.append(UnresolvedConnection(
                    connection_id=derived.edge_id, network_id=network_id,
                    evidence_ids=list(derived.supporting_evidence_ids),
                    reason=code, diagnostics=[diagnostic]))
                continue

            source_node, source_status = _pick_terminal(
                nodes_by_element, derived.source_element_id, "output",
                derived.resolved_source_pin)
            target_node, target_status = _pick_terminal(
                nodes_by_element, derived.target_element_id, "input",
                derived.resolved_target_pin)

            if source_node is None or target_node is None:
                reason = "unresolved"
                if "ambiguous" in (source_status, target_status):
                    reason = "ambiguous_direction"
                elif source_node is None:
                    reason = "unresolved_source_reference"
                else:
                    reason = "unresolved_target_reference"
                candidates = [n.node_id for n in
                              nodes_by_element.get(derived.source_element_id, [])
                              + nodes_by_element.get(derived.target_element_id, [])]
                diagnostic = TopologyDiagnostic(
                    code=reason if reason in DIAGNOSTIC_SEVERITIES else "ambiguous_direction",
                    message="conexão %s não produziu aresta dirigida (%s)"
                            % (derived.edge_id, reason),
                    refs=[derived.edge_id])
                network_diagnostics.append(diagnostic)
                unresolved.append(UnresolvedConnection(
                    connection_id=derived.edge_id, network_id=network_id,
                    evidence_ids=list(derived.supporting_evidence_ids),
                    reason=reason, candidate_nodes=candidates,
                    diagnostics=[diagnostic]))
                continue

            direction_status = ("resolved"
                                if source_status == "resolved" == target_status
                                else "partially_resolved")
            key = (source_node.node_id, target_node.node_id)
            if key in edges_by_key:
                # Mesma ligação sustentada por mais de uma DerivedEdge: uma
                # aresta lógica, evidências somadas — nunca duas arestas
                # paralelas acidentais.
                existing = edges_by_key[key]
                known = {e["evidence_id"] for e in existing.evidence}
                for record in evidence_records:
                    if record["evidence_id"] in known:
                        existing.diagnostics.append(TopologyDiagnostic(
                            code="duplicate_edge_evidence",
                            message="evidência %s contada duas vezes"
                                    % record["evidence_id"],
                            refs=[existing.edge_id]))
                    else:
                        existing.evidence.append(record)
                continue

            edge = LogicalEdge(
                edge_id="%s|%s|%s" % (network_id, source_node.node_id,
                                      target_node.node_id),
                network_id=network_id,
                source_node_id=source_node.node_id,
                target_node_id=target_node.node_id,
                direction_status=direction_status,
                evidence=evidence_records,
                resolution_status=direction_status,
                source={"canonical_edge_id": derived.edge_id})
            edges.append(edge)
            edges_by_key[key] = edge

        # --- análise do grafo, só depois das arestas finais -------------------
        in_degree = {n.node_id: 0 for n in nodes}
        out_degree = {n.node_id: 0 for n in nodes}
        for edge in edges:
            if edge.source_node_id in out_degree:
                out_degree[edge.source_node_id] += 1
            if edge.target_node_id in in_degree:
                in_degree[edge.target_node_id] += 1

        roots = [nid for nid in sorted(in_degree) if in_degree[nid] == 0]
        sinks = [nid for nid in sorted(out_degree) if out_degree[nid] == 0]
        branches = [nid for nid in sorted(out_degree) if out_degree[nid] > 1]
        joins = [nid for nid in sorted(in_degree) if in_degree[nid] > 1]
        cycles = _find_cycles(network_id, nodes, edges)

        for node_id in sorted(in_degree):
            if in_degree[node_id] == 0 and out_degree[node_id] == 0:
                network_diagnostics.append(TopologyDiagnostic(
                    code="orphan_terminal",
                    message="terminal sem nenhuma aresta", refs=[node_id]))
        if not roots:
            network_diagnostics.append(TopologyDiagnostic(
                code="network_without_root",
                message="nenhum nó sem aresta de entrada", refs=[network_id]))
        if not sinks:
            network_diagnostics.append(TopologyDiagnostic(
                code="network_without_sink",
                message="nenhum nó sem aresta de saída", refs=[network_id]))
        for cycle in cycles:
            network_diagnostics.append(TopologyDiagnostic(
                code="cycle_detected",
                message="ciclo observado — não é veredito de invalidez",
                refs=[cycle.cycle_id]))

        logical_networks.append(LogicalNetwork(
            network_id=network_id, source_network_id=network.network_id,
            order=order, nodes=nodes, edges=edges, roots=roots, sinks=sinks,
            branches=branches, joins=joins, cycles=cycles,
            unresolved_connections=unresolved,
            diagnostics=network_diagnostics,
            source={"reconstruction_status": network.reconstruction_status,
                    "canonical_network_id": network.network_id}))

    # Diagnósticos do canônico são TRANSPORTADOS, não substituídos.
    for diagnostic in pou.diagnostics:
        topology_diagnostics.append(TopologyDiagnostic(
            code="canonical:%s" % diagnostic.step, message=diagnostic.message,
            refs=list(diagnostic.refs)))
        topology_diagnostics[-1].severity = diagnostic.severity

    return LogicalTopology(
        pou_identity={"name": pou.name, "pou_type": pou.pou_type,
                      "language": pou.language, "namespace": pou.namespace},
        networks=logical_networks,
        diagnostics=topology_diagnostics,
        source={"source_file": pou.source_file or "",
                "canonical_schema_version": pou.schema_version})

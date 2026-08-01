"""Parser Ladder: liga `structure_map.py` (schema real) a `canonical_model.py`
(tipos e invariantes).

Este módulo é uma CAMADA sobre `map_structure()`. Ele não reabre o XML nem
reimplementa nada que o `StructureMap` já resolve — pinos declarados, conexões,
`ParallelBranch`, segmentação por marcador `networktitle`, componentes conexos.
A única exceção documentada é o hash de `VendorExtension.raw_fragment_hash`
(`docs/17-plcopen-ladder-schema.md`, `canonical_model.py`): para isso, e só
para isso, o XML é reaberto.

Decisões que este módulo não redecide (contratuais, fixadas pelo slice):

* IDs determinísticos e estáveis (`element_id`, `pin_id`, `evidence_id`,
  `edge_id`, `component_id`, `network_id`, `marker_id`, `extension_id`).
* `formalParameter` de uma `<connection>` NUNCA vira `resolved_source_pin`
  sem confirmação contra os pinos de saída realmente declarados pelo bloco de
  origem — a anomalia real do export (bobina referenciando bloco `EQ` com o
  nome da própria variável) é preservada como `raw_connection_formal_parameter`
  e denunciada, nunca corrigida.
* Evidência de conexão PLCopen e evidência de `ParallelBranch` do fornecedor
  nunca se fundem — cada `DerivedEdge` aponta para todas as evidências que a
  sustentam, mas a origem de cada evidência continua rastreável.
* Rede é reconstruída por dois sinais independentes (marcador + topologia sem
  trilhos, incluindo arestas de `ParallelBranch`); marcador vazio é registrado
  como `NetworkBoundary`, nunca vira `Network`.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .canonical_model import (
    ConnectedComponent,
    ConnectionEvidence,
    Diagnostic,
    Element,
    GraphicPOU,
    InterfaceVariable,
    NetworkBoundary,
    Network,
    Pin,
    Position,
    DerivedEdge,
    SourceRef,
    VendorExtension,
)
from .structure_map import (
    LadderElement,
    StructureMap,
    StructureMapError,
    map_structure,
)

# Item 3 do contrato: mapa de tipos XML -> `kind` canônico. Qualquer tag fora
# deste mapa vira "unknown", com o tag original preservado em `raw_xml_tag`.
KIND_MAP: dict[str, str] = {
    "leftPowerRail": "left_power_rail",
    "rightPowerRail": "right_power_rail",
    "contact": "contact",
    "coil": "coil",
    "block": "block",
    "inVariable": "in_variable",
    "outVariable": "out_variable",
    "inOutVariable": "inout_variable",
    "connector": "connector",
    "continuation": "continuation",
    "jump": "jump",
    "label": "label",
    "return": "return",
    "vendorElement": "vendor_element",
    "comment": "comment",
}

# `step` do diagnóstico de `structure_map` -> severidade transportada (item 11).
_WARNING_STEPS = {"formal_parameter", "local_id", "connection"}

_PIN_GROUP_DIRECTION = {
    "inputVariables": "input",
    "outputVariables": "output",
    "inOutVariables": "inout",
}

_RAIL_KINDS = {"left_power_rail", "right_power_rail"}


class LadderParseError(Exception):
    """Envolve `StructureMapError` — XML sem POU Ladder analisável."""


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _element_id_for(local_id: str | None, document_order: int | None = None) -> str | None:
    if local_id is not None:
        return f"el:{local_id}"
    if document_order is not None:
        return f"el:#{document_order}"
    return None


def _vendor_fragment_hashes(xml_path: Path) -> dict[str, str]:
    """Hash sha256 do fragmento normalizado de cada `<vendorElement>`, na
    ordem de documento. Único ponto autorizado a reabrir o XML
    (`canonical_model.py`, item 9 do contrato) — o fragmento cru NUNCA entra
    no modelo, só o hash."""
    try:
        tree = ET.parse(str(xml_path))
    except (ET.ParseError, OSError) as exc:
        raise LadderParseError(f"XML ilegível ao calcular hash de extensão: {exc}") from exc
    root = tree.getroot()
    ld_bodies = [e for e in root.iter() if _local_name(e.tag) == "LD"]
    if not ld_bodies:
        return {}
    ld = ld_bodies[0]
    hashes: dict[str, str] = {}
    for order, child in enumerate(ld):
        if _local_name(child.tag) != "vendorElement":
            continue
        local_id = child.get("localId")
        key = local_id if local_id is not None else f"#{order}"
        fragment = ET.tostring(child)
        hashes[key] = hashlib.sha256(fragment).hexdigest()
    return hashes


def parse_ladder(xml_path: Path | str) -> GraphicPOU:
    """Lê um PLCopen XML de POU Ladder e devolve um `GraphicPOU` validado."""
    xml_path = Path(xml_path)
    try:
        structure = map_structure(xml_path)
    except StructureMapError as exc:
        raise LadderParseError(str(exc)) from exc

    namespaces = structure.document.get("namespaces") or []
    namespace = namespaces[0] if len(namespaces) == 1 else None
    source_file = str(xml_path)

    diagnostics: list[Diagnostic] = []
    for entry in structure.diagnostics:
        step = entry.get("step", "")
        severity = "warning" if step in _WARNING_STEPS else "info"
        diagnostics.append(Diagnostic(step=step, message=entry["message"], severity=severity))

    # --- elementos -----------------------------------------------------------
    elements: list[Element] = []
    element_id_by_local_id: dict[str, str] = {}
    for le in structure.elements:
        element_id = _element_id_for(le.local_id, le.document_order)
        assert element_id is not None
        kind = KIND_MAP.get(le.kind, "unknown")
        raw_xml_tag = le.kind if kind == "unknown" else None

        value_text: str | None = None
        value_source_kind: str | None = None
        if le.variable is not None:
            value_text, value_source_kind = le.variable, "variable"
        elif le.expression is not None:
            value_text, value_source_kind = le.expression, "expression"

        vendor_metadata: dict[str, Any] = {}
        if le.vendor_element_type is not None:
            vendor_metadata["vendor_element_type"] = le.vendor_element_type

        element = Element(
            element_id=element_id,
            local_id=le.local_id,
            kind=kind,
            raw_xml_tag=raw_xml_tag,
            attributes=dict(le.attributes),
            position=Position(),
            source=SourceRef(
                source_file=source_file, local_id=le.local_id,
                namespace=namespace, raw_tag=le.kind),
            vendor_metadata=vendor_metadata,
            negated=le.negated, edge=le.edge, storage=le.storage,
            value_text=value_text, value_source_kind=value_source_kind,
            type_name=le.type_name, call_type=le.call_type,
            instance_name=le.instance_name,
        )
        elements.append(element)
        if le.local_id is not None:
            element_id_by_local_id[le.local_id] = element_id

    element_by_id = {e.element_id: e for e in elements}

    def element_id_for_local_id(local_id: str | None) -> str | None:
        if local_id is None:
            return None
        return element_id_by_local_id.get(local_id, f"el:{local_id}")

    # --- pinos -----------------------------------------------------------------
    pins: list[Pin] = []
    block_output_pins: dict[str, set[str]] = {}
    pin_ids_by_element: dict[str, list[str]] = {}
    for le in structure.elements:
        if le.kind != "block":
            continue
        owner_element_id = element_id_by_local_id.get(le.local_id) or _element_id_for(
            le.local_id, le.document_order)
        declared: list[str] = []
        outputs: set[str] = set()
        for pin_data in le.input_pins + le.output_pins:
            group = pin_data["group"]
            direction = _PIN_GROUP_DIRECTION[group]
            formal_parameter = pin_data["formal_parameter"]
            pin_id = f"pin:{le.local_id}:{direction}:{formal_parameter}"
            pin = Pin(
                pin_id=pin_id, owner_element_id=owner_element_id,
                formal_parameter=formal_parameter, direction=direction,
                declaration_source=group,
                source=SourceRef(
                    source_file=source_file, local_id=le.local_id, namespace=namespace))
            pins.append(pin)
            declared.append(pin_id)
            if direction == "output" and formal_parameter is not None:
                outputs.add(formal_parameter)
        pin_ids_by_element[owner_element_id] = declared
        block_output_pins[owner_element_id] = outputs

    for element in elements:
        element.pin_ids = pin_ids_by_element.get(element.element_id, [])

    # --- evidência de conexão: as duas fontes, nunca fundidas -----------------
    connection_evidence: list[ConnectionEvidence] = []
    for index, conn in enumerate(structure.connections):
        connection_evidence.append(ConnectionEvidence(
            evidence_id=f"ev:conn:{index:04d}",
            evidence_kind="plcopen_connection",
            source_element_ref=element_id_for_local_id(conn.source_local_id),
            target_element_ref=element_id_for_local_id(conn.target_local_id),
            source_pin_raw=conn.source_formal_parameter,
            target_pin_raw=conn.target_pin,
            source_location=SourceRef(
                source_file=source_file, local_id=conn.target_local_id, namespace=namespace),
        ))

    pb_index = 0
    for branch in structure.parallel_branches:
        owner_ref = element_id_for_local_id(branch.owner_local_id)
        for ref in branch.input_refs:
            connection_evidence.append(ConnectionEvidence(
                evidence_id=f"ev:pb:{pb_index:04d}",
                evidence_kind="vendor_parallel_branch",
                source_element_ref=element_id_for_local_id(ref.get("ref_local_id")),
                target_element_ref=owner_ref,
                source_pin_raw=ref.get("formal_parameter"),
                target_pin_raw=None,
                vendor_attributes={"mode": branch.mode, "role": "branch_input"},
                source_location=SourceRef(
                    source_file=source_file, local_id=branch.owner_local_id, namespace=namespace),
            ))
            pb_index += 1
        for ref in branch.tree_refs:
            connection_evidence.append(ConnectionEvidence(
                evidence_id=f"ev:pb:{pb_index:04d}",
                evidence_kind="vendor_parallel_branch",
                source_element_ref=element_id_for_local_id(ref.get("ref_local_id")),
                target_element_ref=owner_ref,
                source_pin_raw=ref.get("formal_parameter"),
                target_pin_raw=None,
                vendor_attributes={"mode": branch.mode, "role": "branch_tree"},
                source_location=SourceRef(
                    source_file=source_file, local_id=branch.owner_local_id, namespace=namespace),
            ))
            pb_index += 1

    # --- arestas derivadas -----------------------------------------------------
    edge_groups: dict[tuple[str | None, str | None, str | None], list[ConnectionEvidence]] = {}
    edge_order: list[tuple[str | None, str | None, str | None]] = []
    for evidence in connection_evidence:
        key = (evidence.source_element_ref, evidence.target_element_ref, evidence.target_pin_raw)
        if key not in edge_groups:
            edge_groups[key] = []
            edge_order.append(key)
        edge_groups[key].append(evidence)

    edges: list[DerivedEdge] = []
    for (source_id, target_id, target_pin) in edge_order:
        evidences = edge_groups[(source_id, target_id, target_pin)]
        pin_part = target_pin if target_pin is not None else "-"
        edge_id = f"edge:{source_id}->{target_id}#{pin_part}"

        # O valor cru precisa vir de TODAS as evidências que sustentam a
        # aresta, não só das `plcopen_connection` — senão o `formalParameter`
        # que o `ParallelBranch` do fornecedor declara (ex.: "ENO") some
        # silenciosamente quando a aresta só tem evidência vendor_parallel_branch.
        # Precedência: `plcopen_connection` (na ordem em que aparecem) antes de
        # `vendor_parallel_branch`. Valores crus DIFERENTES e não-nulos nunca
        # são escolhidos por preferência — viram conflito explícito.
        conn_raws = [e.source_pin_raw for e in evidences
                     if e.evidence_kind == "plcopen_connection" and e.source_pin_raw is not None]
        pb_raws = [e.source_pin_raw for e in evidences
                   if e.evidence_kind == "vendor_parallel_branch" and e.source_pin_raw is not None]
        distinct_raws = list(dict.fromkeys(conn_raws + pb_raws))
        has_conflict = len(distinct_raws) > 1
        raw_param = None if has_conflict else (distinct_raws[0] if distinct_raws else None)
        raw_param_from_vendor_only = bool(raw_param) and not conn_raws

        source_element = element_by_id.get(source_id) if source_id is not None else None
        is_block_source = source_element is not None and source_element.kind == "block"

        resolved_source_pin: str | None = None
        method: str | None = None
        status = "not_applicable"

        if is_block_source:
            declared_outputs = block_output_pins.get(source_id, set())
            if has_conflict:
                method = "conflicting_raw_formal_parameters"
                status = "ambiguous"
                diagnostics.append(Diagnostic(
                    step="source_pin_resolution", severity="warning",
                    message=(
                        f"aresta {edge_id!r}: evidências trazem valores crus de "
                        f"formalParameter DIFERENTES para a mesma aresta: "
                        f"{sorted(distinct_raws)}. Nenhum foi escolhido por preferência."),
                    refs=[edge_id]))
            elif raw_param is not None:
                if raw_param in declared_outputs:
                    resolved_source_pin = raw_param
                    method = (
                        "declared_output_pin_match_from_vendor_parallel_branch"
                        if raw_param_from_vendor_only else "declared_output_pin_match")
                    status = "resolved_from_declared_block_pins"
                else:
                    method = "formal_parameter_not_a_declared_output"
                    status = "unresolved"
                    diagnostics.append(Diagnostic(
                        step="source_pin_resolution", severity="warning",
                        message=(
                            f"aresta {edge_id!r}: formalParameter cru {raw_param!r} não é "
                            f"pino de saída declarado pelo bloco de origem {source_id!r} "
                            f"(saídas declaradas: {sorted(declared_outputs)}). Preservado "
                            "como evidência bruta, não usado como pino resolvido."),
                        refs=[edge_id]))
            else:
                if len(declared_outputs) == 1:
                    method = "single_declared_output_not_confirmed"
                    status = "ambiguous"
                else:
                    status = "unresolved"

        edges.append(DerivedEdge(
            edge_id=edge_id,
            source_element_id=source_id,
            target_element_id=target_id,
            supporting_evidence_ids=[e.evidence_id for e in evidences],
            resolved_source_pin=resolved_source_pin,
            source_pin_resolution_method=method,
            source_pin_resolution_status=status,
            resolved_target_pin=target_pin,
            raw_connection_formal_parameter=raw_param,
        ))

    # --- componentes conexos (sem trilhos, com arestas de ParallelBranch) -----
    rail_element_ids = {e.element_id for e in elements if e.kind in _RAIL_KINDS}
    adjacency: dict[str, set[str]] = {e.element_id: set() for e in elements}
    edges_by_pair: dict[frozenset[str], list[str]] = {}
    for edge in edges:
        s, t = edge.source_element_id, edge.target_element_id
        if s is None or t is None:
            continue
        if s in rail_element_ids or t in rail_element_ids:
            continue
        if s not in adjacency or t not in adjacency:
            continue
        adjacency[s].add(t)
        adjacency[t].add(s)
        pair = frozenset((s, t))
        edges_by_pair.setdefault(pair, []).append(edge.edge_id)

    components: list[ConnectedComponent] = []
    seen: set[str] = set()
    comp_index = 0
    for e in elements:
        eid = e.element_id
        if eid in rail_element_ids or eid in seen:
            continue
        stack, group = [eid], []
        seen.add(eid)
        while stack:
            current = stack.pop()
            group.append(current)
            for neighbour in adjacency.get(current, ()):
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        edge_ids: set[str] = set()
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                pair = frozenset((group[i], group[j]))
                if pair in edges_by_pair:
                    edge_ids.update(edges_by_pair[pair])
        components.append(ConnectedComponent(
            component_id=f"cmp:{comp_index:04d}",
            element_ids=list(group),
            edge_ids=list(edge_ids),
            discovery_method="connectivity_without_rails_including_parallel_branch",
        ))
        comp_index += 1

    nontrivial_components = [c for c in components if len(c.element_ids) > 1]

    # --- fronteiras e redes ------------------------------------------------------
    connected_ids: set[str | None] = set()
    for conn in structure.connections:
        connected_ids.add(conn.target_local_id)
        connected_ids.add(conn.source_local_id)

    rail_local_ids = {le.local_id for le in structure.elements
                      if le.kind in ("leftPowerRail", "rightPowerRail")}

    marker_segments = [seg for seg in structure.networks if seg.get("title_marker_local_id")]

    network_boundaries: list[NetworkBoundary] = []
    networks: list[Network] = []
    assigned_element_ids: set[str] = set()
    handled_component_ids: set[str] = set()
    order_counter = 0

    for seg in marker_segments:
        marker_local_id = seg["title_marker_local_id"]
        is_empty = not any(lid in connected_ids for lid in seg["member_local_ids"])
        boundary = NetworkBoundary(
            marker_id=f"mk:{marker_local_id}", title=None, is_empty=is_empty,
            order=order_counter,
            source=SourceRef(
                source_file=source_file, local_id=marker_local_id, namespace=namespace))
        network_boundaries.append(boundary)

        if is_empty:
            order_counter += 1
            continue

        member_local_ids = [lid for lid in seg["member_local_ids"] if lid not in rail_local_ids]
        member_element_ids = {element_id_for_local_id(lid) for lid in member_local_ids}

        intersecting = [c for c in nontrivial_components
                        if set(c.element_ids) & member_element_ids]
        net_diagnostics: list[Diagnostic] = []
        if not intersecting:
            status = "marker_only"
        else:
            fully_contained = all(
                set(c.element_ids) <= member_element_ids for c in intersecting)
            if fully_contained:
                status = "confirmed_by_marker_and_connectivity"
            else:
                status = "ambiguous"
                message = (
                    f"componente não-trivial atravessa a fronteira do marcador "
                    f"mk:{marker_local_id} — segmentação por marcador e topologia "
                    "divergem para este trecho.")
                diag = Diagnostic(step="network_reconstruction", severity="warning",
                                   message=message)
                net_diagnostics.append(diag)
                diagnostics.append(diag)

        connection_ids = [
            e.edge_id for e in edges
            if e.source_element_id in member_element_ids
            and e.target_element_id in member_element_ids]

        network = Network(
            network_id=f"net:{order_counter:04d}", order=order_counter, title=None,
            element_ids=sorted(member_element_ids),
            connection_ids=connection_ids,
            boundary_evidence_ids=[f"ext:{marker_local_id}:networktitle"],
            component_ids=[c.component_id for c in intersecting],
            reconstruction_status=status,
            diagnostics=net_diagnostics,
        )
        networks.append(network)
        assigned_element_ids.update(member_element_ids)
        for c in intersecting:
            handled_component_ids.add(c.component_id)
        order_counter += 1

    for component in nontrivial_components:
        if component.component_id in handled_component_ids:
            continue
        network = Network(
            network_id=f"net:{order_counter:04d}", order=order_counter, title=None,
            element_ids=sorted(component.element_ids),
            connection_ids=list(component.edge_ids),
            boundary_evidence_ids=[],
            component_ids=[component.component_id],
            reconstruction_status="connectivity_only",
        )
        networks.append(network)
        assigned_element_ids.update(component.element_ids)
        order_counter += 1

    unassigned_elements = sorted(
        e.element_id for e in elements if e.element_id not in assigned_element_ids)

    # --- extensões do fornecedor -------------------------------------------------
    parallel_owner_ids = {b.owner_local_id for b in structure.parallel_branches}
    vendor_hashes = _vendor_fragment_hashes(xml_path)
    vendor_extensions: list[VendorExtension] = []
    for le in structure.elements:
        if le.kind != "vendorElement":
            continue
        if le.vendor_element_type == "networktitle":
            classification = "networktitle"
        elif le.local_id in parallel_owner_ids:
            classification = "ldparallelbranch"
        else:
            classification = "unclassified"
        hash_key = le.local_id if le.local_id is not None else f"#{le.document_order}"
        vendor_extensions.append(VendorExtension(
            extension_id=f"ext:{le.local_id}:{classification}",
            owner_id=element_id_for_local_id(le.local_id),
            namespace=namespace, tag="vendorElement",
            attributes=dict(le.attributes),
            normalized_classification=classification,
            raw_fragment_hash=vendor_hashes.get(hash_key),
            source=SourceRef(
                source_file=source_file, local_id=le.local_id, namespace=namespace,
                raw_tag="vendorElement"),
        ))

    # --- interface -----------------------------------------------------------
    interface = [
        InterfaceVariable(name=v.get("name"), group=v.get("group"), type_name=v.get("type"))
        for v in structure.pou.get("interface_variables") or []]

    return GraphicPOU(
        name=structure.pou.get("name"),
        pou_type=structure.pou.get("pou_type"),
        language="LD",
        namespace=namespace,
        source_file=source_file,
        interface=interface,
        elements=elements,
        pins=pins,
        connection_evidence=connection_evidence,
        derived_edges=edges,
        network_boundaries=network_boundaries,
        components=components,
        networks=networks,
        vendor_extensions=vendor_extensions,
        unassigned_elements=unassigned_elements,
        diagnostics=diagnostics,
    )


def write_canonical_pou(pou: GraphicPOU, output_dir: Path | str) -> list[Path]:
    """Grava `canonical-pou.json`, determinístico (JSON `indent=2`,
    `ensure_ascii=False`, newline final)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "canonical-pou.json"
    path.write_text(
        json.dumps(pou.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return [path]

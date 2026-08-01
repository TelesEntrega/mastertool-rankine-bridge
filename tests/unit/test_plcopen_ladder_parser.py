"""Parser Ladder: `structure_map` -> `canonical_model`.

Roda sobre a fixture SINTETICA e SANITIZADA (`ladder_sample.xml`). O XML real
nao entra no repositorio: contem nomes de equipamento, variaveis e logica do
cliente. Se disponivel localmente (fora do versionamento), o teste contra o
export real e pulado quando o arquivo nao existir.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastertool_bridge.plcopen.canonical_model import GraphicPOU
from mastertool_bridge.plcopen.ladder_parser import (
    LadderParseError,
    parse_ladder,
    write_canonical_pou,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "plcopen" / "ladder_sample.xml"

REAL_EXPORT_FILE = (
    Path(__file__).resolve().parents[2]
    / "workspace" / "exports"
    / "2026-07-28_13-48-49_20_validate_controlled_plcopen_export"
    / "plcopen-export" / "export-root" / "pou-export")


@pytest.fixture(scope="module")
def pou() -> GraphicPOU:
    return parse_ladder(FIXTURE)


# --- contagem e taxonomia de elementos ---------------------------------------

def test_element_count_and_no_unknown_kind(pou):
    assert len(pou.elements) == 20
    assert all(e.kind != "unknown" for e in pou.elements)


def test_element_kind_taxonomy(pou):
    by_local_id = {e.local_id: e for e in pou.elements}
    assert by_local_id["0"].kind == "left_power_rail"
    assert by_local_id["2147483646"].kind == "right_power_rail"
    assert by_local_id["8"].kind == "contact"
    assert by_local_id["18"].kind == "coil"
    assert by_local_id["5"].kind == "block"
    assert by_local_id["6"].kind == "in_variable"
    assert by_local_id["2"].kind == "vendor_element"


def test_element_ids_are_stable_format(pou):
    ids = {e.element_id for e in pou.elements}
    assert "el:0" in ids
    assert "el:24" in ids
    assert all(eid.startswith("el:") for eid in ids)


# --- as duas fontes de evidencia, nunca fundidas -----------------------------

def test_plcopen_connection_evidence_count(pou):
    plcopen_evidence = pou.evidence_by_kind("plcopen_connection")
    assert len(plcopen_evidence) == 14
    assert all(e.evidence_id.startswith("ev:conn:") for e in plcopen_evidence)


def test_vendor_parallel_branch_evidence_is_separate(pou):
    pb_evidence = pou.evidence_by_kind("vendor_parallel_branch")
    assert len(pb_evidence) == 3
    assert all(e.evidence_id.startswith("ev:pb:") for e in pb_evidence)
    roles = {e.vendor_attributes.get("role") for e in pb_evidence}
    assert roles == {"branch_input", "branch_tree"}
    assert all(e.vendor_attributes.get("mode") == "sce" for e in pb_evidence)


def test_evidence_kinds_never_mix_ids(pou):
    conn_ids = {e.evidence_id for e in pou.evidence_by_kind("plcopen_connection")}
    pb_ids = {e.evidence_id for e in pou.evidence_by_kind("vendor_parallel_branch")}
    assert conn_ids.isdisjoint(pb_ids)


def test_every_evidence_supports_exactly_one_edge(pou):
    supported: dict[str, str] = {}
    for edge in pou.derived_edges:
        for evidence_id in edge.supporting_evidence_ids:
            assert evidence_id not in supported, (
                f"evidência {evidence_id!r} sustenta mais de uma aresta")
            supported[evidence_id] = edge.edge_id
    all_evidence_ids = {e.evidence_id for e in pou.connection_evidence}
    assert set(supported) == all_evidence_ids


# --- a anomalia do formalParameter --------------------------------------------

def test_formal_parameter_anomaly_stays_unresolved_with_raw_value(pou):
    edge = next(
        e for e in pou.derived_edges
        if e.source_element_id == "el:21" and e.target_element_id == "el:24")
    assert edge.raw_connection_formal_parameter == "SAIDA_B"
    assert edge.resolved_source_pin is None
    assert edge.source_pin_resolution_status == "unresolved"
    assert edge.source_pin_resolution_method == "formal_parameter_not_a_declared_output"


def test_formal_parameter_resolved_case_for_contrast(pou):
    edge = next(
        e for e in pou.derived_edges
        if e.source_element_id == "el:5" and e.target_element_id == "el:8")
    assert edge.raw_connection_formal_parameter == "Out1"
    assert edge.resolved_source_pin == "Out1"
    assert edge.source_pin_resolution_status == "resolved_from_declared_block_pins"
    assert edge.source_pin_resolution_method == "declared_output_pin_match"


def test_anomaly_produces_warning_diagnostic(pou):
    assert any(
        d.step == "source_pin_resolution" and d.severity == "warning"
        and "SAIDA_B" in d.message
        for d in pou.diagnostics)


# --- TON com instanceName vs operadores sem instanceName ---------------------

def test_function_block_call_type_and_instance_name(pou):
    by_local_id = {e.local_id: e for e in pou.elements}
    ton = by_local_id["26"]
    assert ton.type_name == "TON"
    assert ton.call_type == "functionblock"
    assert ton.instance_name == "TEMPORIZADOR_0"

    operator_block = by_local_id["5"]
    assert operator_block.type_name == "EQ"
    assert operator_block.call_type == "operator"
    assert operator_block.instance_name is None


def test_ton_pins_declared_with_output_direction(pou):
    ton_pins = pou.pins_of("el:26")
    formal_parameters_by_direction = {
        (p.direction, p.formal_parameter) for p in ton_pins}
    assert ("output", "Q") in formal_parameters_by_direction
    assert ("output", "ET") in formal_parameters_by_direction
    assert ("input", "IN") in formal_parameters_by_direction
    assert ("input", "PT") in formal_parameters_by_direction


# --- value_source_kind variable vs expression --------------------------------

def test_value_source_kind_variable_for_contact_and_coil(pou):
    by_local_id = {e.local_id: e for e in pou.elements}
    contact = by_local_id["8"]
    assert contact.value_source_kind == "variable"
    assert contact.value_text == "ENTRADA"

    coil = by_local_id["18"]
    assert coil.value_source_kind == "variable"
    assert coil.value_text == "SAIDA_A"


def test_value_source_kind_expression_for_invariable(pou):
    by_local_id = {e.local_id: e for e in pou.elements}
    in_variable = by_local_id["6"]
    assert in_variable.value_source_kind == "expression"
    assert in_variable.value_text == "ESTADO"

    literal = by_local_id["7"]
    assert literal.value_source_kind == "expression"
    assert literal.value_text == "0"


# --- marcadores de rede e status de reconstrucao -----------------------------

def test_network_boundaries_registered_in_document_order(pou):
    marker_ids = [b.marker_id for b in sorted(pou.network_boundaries, key=lambda b: b.order)]
    assert marker_ids == ["mk:2", "mk:14", "mk:20"]
    assert all(not b.is_empty for b in pou.network_boundaries)


def test_networks_confirmed_by_marker_and_connectivity(pou):
    assert len(pou.networks) == 3
    assert all(
        n.reconstruction_status == "confirmed_by_marker_and_connectivity"
        for n in pou.networks)


def test_network_membership_excludes_rails_and_markers(pou):
    all_network_members: set[str] = set()
    for network in pou.networks:
        all_network_members.update(network.element_ids)
    assert "el:0" not in all_network_members
    assert "el:2147483646" not in all_network_members
    assert "el:2" not in all_network_members
    assert "el:0" in pou.unassigned_elements
    assert "el:2147483646" in pou.unassigned_elements


def test_no_element_appears_in_two_networks(pou):
    seen: set[str] = set()
    for network in pou.networks:
        for element_id in network.element_ids:
            assert element_id not in seen, f"{element_id!r} em duas redes"
            seen.add(element_id)


# --- determinismo e round-trip ------------------------------------------------

def test_two_parses_produce_identical_json():
    first = parse_ladder(FIXTURE).to_dict()
    second = parse_ladder(FIXTURE).to_dict()
    assert json.dumps(first, indent=2, ensure_ascii=False) == json.dumps(
        second, indent=2, ensure_ascii=False)


def test_write_canonical_pou_is_byte_stable(tmp_path):
    first_pou = parse_ladder(FIXTURE)
    second_pou = parse_ladder(FIXTURE)
    first_paths = write_canonical_pou(first_pou, tmp_path / "run1")
    second_paths = write_canonical_pou(second_pou, tmp_path / "run2")
    assert first_paths[0].read_bytes() == second_paths[0].read_bytes()


def test_roundtrip_to_dict_from_dict(pou):
    restored = GraphicPOU.from_dict(pou.to_dict())
    assert restored.to_dict() == pou.to_dict()


# --- API pública e erro envolto -----------------------------------------------

def test_parse_ladder_raises_ladder_parse_error_on_bad_xml(tmp_path):
    bad_xml = tmp_path / "not-ladder.xml"
    bad_xml.write_text("<project/>", encoding="utf-8")
    with pytest.raises(LadderParseError):
        parse_ladder(bad_xml)


# --- contra o export real, se disponivel (nunca versionado) -------------------

def test_against_real_export_if_available():
    if not REAL_EXPORT_FILE.is_file():
        pytest.skip("export real nao disponivel neste ambiente")

    real_pou = parse_ladder(REAL_EXPORT_FILE)

    # Nenhuma asserção abaixo revela nome de POU, variavel, instancia ou
    # contagem especifica do arquivo do cliente -- apenas invariantes
    # estruturais e relativas, para o teste continuar publicavel.
    assert len(real_pou.elements) > 0
    assert all(e.kind != "unknown" for e in real_pou.elements)

    # toda evidencia sustenta exatamente uma aresta, nenhuma orfa.
    supported: dict[str, str] = {}
    for edge in real_pou.derived_edges:
        for evidence_id in edge.supporting_evidence_ids:
            assert evidence_id not in supported, (
                f"evidência {evidence_id!r} sustenta mais de uma aresta")
            supported[evidence_id] = edge.edge_id
    all_evidence_ids = {e.evidence_id for e in real_pou.connection_evidence}
    assert set(supported) == all_evidence_ids

    # nenhum resolved_source_pin fora dos pinos de saida declarados pelo
    # bloco de origem.
    output_pins_by_element: dict[str, set[str]] = {}
    for pin in real_pou.pins:
        if pin.direction == "output" and pin.formal_parameter is not None:
            output_pins_by_element.setdefault(pin.owner_element_id, set()).add(
                pin.formal_parameter)
    for edge in real_pou.derived_edges:
        if edge.resolved_source_pin is not None:
            declared = output_pins_by_element.get(edge.source_element_id, set())
            assert edge.resolved_source_pin in declared

    # nenhum elemento em duas redes.
    seen: set[str] = set()
    for network in real_pou.networks:
        for element_id in network.element_ids:
            assert element_id not in seen, f"{element_id!r} em duas redes"
            seen.add(element_id)

    # dois parses do mesmo arquivo produzem o mesmo JSON.
    first = parse_ladder(REAL_EXPORT_FILE).to_dict()
    second = parse_ladder(REAL_EXPORT_FILE).to_dict()
    assert json.dumps(first, indent=2, ensure_ascii=False) == json.dumps(
        second, indent=2, ensure_ascii=False)

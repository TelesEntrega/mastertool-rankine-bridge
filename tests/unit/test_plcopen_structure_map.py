"""Mapa estrutural de PLCopen XML Ladder.

Roda sobre uma fixture SINTETICA e SANITIZADA que espelha o schema observado
num export real. O XML real nao entra no repositorio: contem nomes de
equipamento, variaveis e logica do cliente.

Varias assercoes aqui existem porque a fixture EXPOS defeitos no mapeador
durante a construcao -- limiar de componente errado, arestas de
ParallelBranch ausentes, e comparacao injusta contra marcadores vazios.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mastertool_bridge.plcopen.structure_map import (
    StructureMapError,
    map_structure,
    write_structure_map,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "plcopen" / "ladder_sample.xml"


@pytest.fixture(scope="module")
def structure():
    return map_structure(FIXTURE)


# --- documento e POU ---------------------------------------------------------

def test_namespace_and_absence_of_explicit_network(structure):
    """Nao existe <network>: redes PRECISAM ser reconstruidas."""
    assert any("plcopen.org/xml/tc6" in ns for ns in structure.document["namespaces"])
    assert structure.document["has_explicit_network_element"] is False
    assert structure.document["ld_body_count"] == 1


def test_pou_identity_and_interface(structure):
    assert structure.pou["name"] == "FB_EXEMPLO"
    assert structure.pou["pou_type"] == "functionBlock"
    by_name = {v["name"]: v for v in structure.pou["interface_variables"]}
    assert by_name["ENTRADA"]["type"] == "BOOL"
    assert by_name["ENTRADA"]["group"] == "inputVars"
    assert by_name["ESTADO"]["group"] == "localVars"


# --- onde cada elemento guarda o nome ----------------------------------------

def test_contact_stores_name_in_variable_child(structure):
    contacts = {e.local_id: e for e in structure.elements if e.kind == "contact"}
    assert contacts["8"].variable == "ENTRADA"
    assert contacts["8"].expression is None
    assert contacts["8"].negated is False
    assert contacts["11"].negated is True


def test_invariable_stores_name_in_expression_child(structure):
    invars = {e.local_id: e for e in structure.elements if e.kind == "inVariable"}
    assert invars["6"].expression == "ESTADO"
    assert invars["6"].variable is None
    assert invars["7"].expression == "0"


def test_coil_attributes_carry_storage_and_negation(structure):
    coils = {e.local_id: e for e in structure.elements if e.kind == "coil"}
    assert coils["18"].variable == "SAIDA_A"
    assert coils["18"].storage == "reset"
    assert coils["24"].storage == "none"
    assert coils["34"].negated is True


# --- blocos: operador vs bloco de funcao -------------------------------------

def test_call_type_distinguishes_operator_from_function_block(structure):
    blocks = {e.local_id: e for e in structure.elements if e.kind == "block"}
    assert blocks["5"].call_type == "operator"
    assert blocks["5"].instance_name is None
    assert blocks["26"].call_type == "functionblock"
    assert blocks["26"].instance_name == "TEMPORIZADOR_0"
    assert blocks["26"].type_name == "TON"


def test_block_pins_are_formal_parameters(structure):
    blocks = {e.local_id: e for e in structure.elements if e.kind == "block"}
    ton = blocks["26"]
    assert {p["formal_parameter"] for p in ton.input_pins} == {"IN", "PT"}
    assert {p["formal_parameter"] for p in ton.output_pins} == {"Q", "ET"}
    assert all("connected" in p for p in ton.output_pins)


def test_vendor_detection_matches_by_suffix_not_domain(structure):
    """A fixture usa example.com; o arquivo real usa 3s-software.com. Se a
    deteccao dependesse do dominio, quebraria numa troca de versao."""
    blocks = [e for e in structure.elements if e.kind == "block"]
    assert all(b.call_type for b in blocks)


# --- conexoes ----------------------------------------------------------------

def test_connections_point_from_target_to_source(structure):
    ton_inputs = [c for c in structure.connections if c.target_local_id == "26"]
    by_pin = {c.target_pin: c for c in ton_inputs}
    assert by_pin["IN"].source_local_id == "21"
    assert by_pin["PT"].source_local_id == "27"


def test_target_pin_is_recorded_for_block_inputs(structure):
    pins = {c.target_pin for c in structure.connections if c.target_local_id == "5"}
    assert pins == {"EN", "In2", "In3"}


def test_coil_connection_has_no_target_pin(structure):
    coil = [c for c in structure.connections if c.target_local_id == "18"][0]
    assert coil.target_pin is None
    assert coil.source_local_id == "15"


def test_formal_parameter_anomaly_is_reported_not_normalized(structure):
    """No arquivo real uma bobina referencia um bloco EQ com formalParameter
    igual ao nome da PROPRIA variavel da bobina, nao ao pino de saida. Um
    parser que confiar nesse atributo quebra -- o mapa denuncia em vez de
    normalizar em silencio, e preserva o valor bruto."""
    anomalies = [d for d in structure.diagnostics if d["step"] == "formal_parameter"]
    assert anomalies
    assert any("SAIDA_B" in d["message"] for d in anomalies)

    conn = [c for c in structure.connections if c.target_local_id == "24"][0]
    assert conn.source_formal_parameter == "SAIDA_B"


def test_parallel_branch_is_a_vendor_extension(structure):
    assert len(structure.parallel_branches) == 1
    branch = structure.parallel_branches[0]
    assert branch.mode == "sce"
    assert [r["ref_local_id"] for r in branch.input_refs] == ["0"]
    assert sorted(r["ref_local_id"] for r in branch.tree_refs) == ["10", "4"]
    assert all(r["formal_parameter"] == "ENO" for r in branch.tree_refs)


def test_parallel_branch_edges_are_kept_out_of_the_main_connection_map(structure):
    """Misturar as duas fontes esconderia que uma delas e nao-padrao."""
    assert not any(c.via == "ParallelBranch" for c in structure.connections)


# --- redes -------------------------------------------------------------------

def test_networks_are_segmented_by_vendor_title_markers(structure):
    titled = [n for n in structure.networks if n["title_marker_local_id"]]
    assert len(titled) == 3
    assert [n["index"] for n in titled] == [0, 1, 2]


def test_elements_before_the_first_marker_go_to_an_explicit_prologue(structure):
    prologue = [n for n in structure.networks if n.get("prologue")]
    assert len(prologue) == 1
    assert "0" in prologue[0]["member_local_ids"]


def test_two_independent_signals_agree_on_network_count(structure):
    """Marcador do fornecedor E topologia dao o mesmo numero. Concordancia de
    fontes independentes e mais forte que confiar so na extensao."""
    message = [d["message"] for d in structure.diagnostics
               if d["step"] == "network_segmentation"][0]
    assert "concordam" in message


def test_power_rail_joins_everything_so_raw_components_do_not_segment(structure):
    """Com o trilho no grafo o corpo vira quase um unico componente -- por
    isso a segmentacao usa o grafo SEM trilhos."""
    assert max(len(c) for c in structure.components) > max(
        len(c) for c in structure.components_without_rails)


# --- diagnosticos ------------------------------------------------------------

def test_graphical_position_is_reported_as_useless(structure):
    """Todas as posicoes do export real sao (0,0)."""
    assert any(d["step"] == "position" for d in structure.diagnostics)


def test_no_unknown_elements_in_the_fixture(structure):
    assert structure.unknown_elements == []


def test_unknown_elements_are_reported_never_silently_dropped(tmp_path):
    xml = tmp_path / "estranho.xml"
    xml.write_text(
        '<?xml version="1.0"?>\n'
        '<project xmlns="http://www.plcopen.org/xml/tc6_0200">'
        '<types><pous><pou name="P" pouType="program"><body><LD>'
        '<elementoInventado localId="99" />'
        '</LD></body></pou></pous></types></project>', encoding="utf-8")

    assert [u["kind"] for u in map_structure(xml).unknown_elements] == ["elementoInventado"]


def test_duplicated_local_id_is_reported(tmp_path):
    xml = tmp_path / "duplicado.xml"
    xml.write_text(
        '<?xml version="1.0"?>\n'
        '<project xmlns="http://www.plcopen.org/xml/tc6_0200">'
        '<types><pous><pou name="P" pouType="program"><body><LD>'
        '<contact localId="7"><variable>A</variable></contact>'
        '<contact localId="7"><variable>B</variable></contact>'
        '</LD></body></pou></pous></types></project>', encoding="utf-8")

    assert any(d["step"] == "local_id" for d in map_structure(xml).diagnostics)


def test_dangling_ref_local_id_is_reported(tmp_path):
    xml = tmp_path / "pendente.xml"
    xml.write_text(
        '<?xml version="1.0"?>\n'
        '<project xmlns="http://www.plcopen.org/xml/tc6_0200">'
        '<types><pous><pou name="P" pouType="program"><body><LD>'
        '<coil localId="1"><connectionPointIn>'
        '<connection refLocalId="999" /></connectionPointIn>'
        '<variable>X</variable></coil>'
        '</LD></body></pou></pous></types></project>', encoding="utf-8")

    assert any(d["step"] == "connection" and "999" in d["message"]
               for d in map_structure(xml).diagnostics)


def test_missing_ld_body_is_refused(tmp_path):
    xml = tmp_path / "sem_ld.xml"
    xml.write_text(
        '<?xml version="1.0"?>\n'
        '<project xmlns="http://www.plcopen.org/xml/tc6_0200">'
        '<types><pous /></types></project>', encoding="utf-8")

    with pytest.raises(StructureMapError, match="LD"):
        map_structure(xml)


# --- artefatos ---------------------------------------------------------------

def test_write_structure_map_emits_the_expected_artifacts(structure, tmp_path):
    written = {p.name for p in write_structure_map(structure, tmp_path)}
    for expected in ("document-summary.json", "pou-structure.json",
                     "ladder-elements.json", "block-instances.json",
                     "connection-map.json", "connected-components.json",
                     "observed-element-schema.json", "unknown-elements.json",
                     "diagnostics.json"):
        assert expected in written

"""Modelo canonico de POU grafica: tipos, invariantes e serializacao.

Nenhum parser aqui -- os modelos sao construidos a mao, de proposito, para
os testes exercitarem as invariantes sem depender de XML.

As assercoes mais importantes deste arquivo nao sao sobre o que o modelo
guarda, e sim sobre o que ele SE RECUSA a fazer: fundir as duas fontes de
topologia, tratar `formalParameter` cru como verdade sobre o pino, usar
coordenada (0,0) como desempate, e transformar "nunca observado" em "nao
suportado".
"""

from __future__ import annotations

import json

import pytest

from mastertool_bridge.plcopen.canonical_model import (
    CanonicalModelError,
    ConnectedComponent,
    ConnectionEvidence,
    DerivedEdge,
    Diagnostic,
    Element,
    GraphicPOU,
    InterfaceVariable,
    Network,
    NetworkBoundary,
    Pin,
    Position,
    SourceRef,
    VendorExtension,
)


def _element(element_id="e1", local_id="1", kind="contact", **kw):
    return Element(element_id=element_id, local_id=local_id, kind=kind, **kw)


def _pou(**kw):
    defaults = dict(name="FB_EXEMPLO", pou_type="functionBlock", language="LD")
    defaults.update(kw)
    return GraphicPOU(**defaults)


# --- tipos basicos -----------------------------------------------------------

def test_element_rejects_unknown_kind_and_suggests_unknown():
    with pytest.raises(CanonicalModelError, match="unknown"):
        Element(element_id="x", local_id="1", kind="inventado")


def test_unknown_kind_is_representable_and_keeps_the_raw_tag():
    """Elemento nao pode DESAPARECER por nao ser reconhecido."""
    element = _element(kind="unknown", raw_xml_tag="elementoInventado",
                       attributes={"foo": "bar"})
    pou = _pou(elements=[element])

    dumped = pou.to_dict()["elements"][0]
    assert dumped["kind"] == "unknown"
    assert dumped["raw_xml_tag"] == "elementoInventado"
    assert dumped["attributes"] == {"foo": "bar"}


def test_value_source_kind_preserves_where_the_name_came_from():
    """contact/coil usam <variable>; inVariable usa <expression>. Fundir os
    dois apagaria uma distincao que o proprio schema faz."""
    contact = _element(element_id="c", local_id="8", kind="contact",
                       value_text="ENTRADA", value_source_kind="variable")
    invar = _element(element_id="v", local_id="6", kind="in_variable",
                     value_text="ESTADO", value_source_kind="expression")
    pou = _pou(elements=[contact, invar])

    by_id = {e["element_id"]: e for e in pou.to_dict()["elements"]}
    assert by_id["c"]["value_source_kind"] == "variable"
    assert by_id["v"]["value_source_kind"] == "expression"


def test_invalid_value_source_kind_is_refused():
    with pytest.raises(CanonicalModelError, match="value_source_kind"):
        _element(value_text="X", value_source_kind="atributo")


def test_pin_direction_is_validated():
    with pytest.raises(CanonicalModelError, match="direção de pino"):
        Pin(pin_id="p", owner_element_id="e", formal_parameter="EN",
            direction="entrada")


# --- observado vs nao suportado ----------------------------------------------

def test_not_observed_never_becomes_unsupported():
    """Ausencia de observacao nao e prova de ausencia de suporte."""
    jump = _element(element_id="j", local_id="99", kind="jump")
    assert jump.observation_status == "not_observed"

    contact = _element()
    assert contact.observation_status == "observed"

    summary = _pou(elements=[jump, contact]).observation_summary()
    assert "jump" in summary["modelled_but_not_observed"]
    assert "contact" in summary["observed"]
    assert "unsupported" not in json.dumps(summary)


# --- posicao (0,0) -----------------------------------------------------------

def test_position_is_preserved_but_marked_unusable():
    element = _element(position=Position(x=0, y=0))
    dumped = _pou(elements=[element]).to_dict()["elements"][0]["position"]
    assert dumped == {"x": 0, "y": 0, "usable_for_topology": False}


def test_position_cannot_be_declared_usable_for_topology():
    """Nenhum export observado sustenta desempate por coordenada."""
    element = _element(position=Position(x=10, y=20, usable_for_topology=True))
    with pytest.raises(CanonicalModelError, match="posição utilizável"):
        _pou(elements=[element])


# --- as duas fontes de topologia ---------------------------------------------

def test_evidence_kinds_stay_separate():
    plc = ConnectionEvidence(evidence_id="ev1", evidence_kind="plcopen_connection",
                             source_element_ref="e1", target_element_ref="e2")
    vendor = ConnectionEvidence(evidence_id="ev2",
                                evidence_kind="vendor_parallel_branch",
                                source_element_ref="e1", target_element_ref="e2",
                                vendor_attributes={"mode": "sce"})
    pou = _pou(elements=[_element("e1", "1"), _element("e2", "2")],
               connection_evidence=[plc, vendor])

    assert len(pou.evidence_by_kind("plcopen_connection")) == 1
    assert len(pou.evidence_by_kind("vendor_parallel_branch")) == 1
    assert pou.evidence_by_kind("vendor_parallel_branch")[0].vendor_attributes == {
        "mode": "sce"}


def test_unknown_evidence_kind_is_refused():
    with pytest.raises(CanonicalModelError, match="evidence_kind"):
        ConnectionEvidence(evidence_id="x", evidence_kind="inventado",
                           source_element_ref=None, target_element_ref=None)


def test_derived_edge_must_cite_supporting_evidence():
    """Aresta sem evidencia seria topologia afirmada sem fonte."""
    with pytest.raises(CanonicalModelError, match="sem evidência"):
        DerivedEdge(edge_id="d1", source_element_id="e1", target_element_id="e2")


def test_derived_edge_referencing_missing_evidence_is_refused():
    edge = DerivedEdge(edge_id="d1", source_element_id="e1",
                       target_element_id="e2",
                       supporting_evidence_ids=["nao-existe"])
    with pytest.raises(CanonicalModelError, match="evidência"):
        _pou(elements=[_element("e1", "1"), _element("e2", "2")],
             derived_edges=[edge])


def test_raw_formal_parameter_is_preserved_apart_from_the_resolved_pin():
    """O atributo cru fica como EVIDENCIA; o pino resolvido e campo separado,
    com metodo e status. No arquivo real esse atributo as vezes traz o nome
    da variavel do destino, e um parser que confiasse nele quebraria."""
    evidence = ConnectionEvidence(
        evidence_id="ev1", evidence_kind="plcopen_connection",
        source_element_ref="bloco", target_element_ref="bobina",
        source_pin_raw="SAIDA_B")
    edge = DerivedEdge(
        edge_id="d1", source_element_id="bloco", target_element_id="bobina",
        supporting_evidence_ids=["ev1"],
        raw_connection_formal_parameter="SAIDA_B",
        resolved_source_pin="Out1",
        source_pin_resolution_method="declared_block_output_pins",
        source_pin_resolution_status="resolved_from_declared_block_pins")

    pou = _pou(elements=[_element("bloco", "21", kind="block"),
                         _element("bobina", "24", kind="coil")],
               connection_evidence=[evidence], derived_edges=[edge])
    dumped = pou.to_dict()["derived_edges"][0]

    assert dumped["raw_connection_formal_parameter"] == "SAIDA_B"
    assert dumped["resolved_source_pin"] == "Out1"
    assert dumped["source_pin_resolution_status"] == "resolved_from_declared_block_pins"


def test_invalid_resolution_status_is_refused():
    with pytest.raises(CanonicalModelError, match="source_pin_resolution_status"):
        DerivedEdge(edge_id="d", source_element_id="a", target_element_id="b",
                    supporting_evidence_ids=["ev"],
                    source_pin_resolution_status="chutado")


# --- invariantes da POU ------------------------------------------------------

def test_duplicated_local_id_is_refused():
    with pytest.raises(CanonicalModelError, match="localId duplicado"):
        _pou(elements=[_element("a", "7"), _element("b", "7")])


def test_duplicated_element_id_is_refused():
    with pytest.raises(CanonicalModelError, match="element_id duplicado"):
        _pou(elements=[_element("a", "1"), _element("a", "2")])


def test_pin_of_missing_element_is_refused():
    pin = Pin(pin_id="p1", owner_element_id="fantasma",
              formal_parameter="EN", direction="input")
    with pytest.raises(CanonicalModelError, match="elemento inexistente"):
        _pou(elements=[_element("e1", "1")], pins=[pin])


def test_element_referencing_missing_pin_is_refused():
    element = _element("e1", "1", kind="block", pin_ids=["nao-existe"])
    with pytest.raises(CanonicalModelError, match="pino"):
        _pou(elements=[element])


def test_dangling_element_reference_becomes_diagnostic_not_exception():
    """Um XML com referencia pendente ainda e analisavel -- recusa-lo inteiro
    esconderia tudo o que ele tem de bom."""
    evidence = ConnectionEvidence(
        evidence_id="ev1", evidence_kind="plcopen_connection",
        source_element_ref="999", target_element_ref="e1")
    pou = _pou(elements=[_element("e1", "1")], connection_evidence=[evidence])

    dangling = [d for d in pou.diagnostics if d.step == "dangling_reference"]
    assert dangling
    assert dangling[0].severity == "warning"
    assert "999" in dangling[0].message


def test_unknown_language_is_refused():
    with pytest.raises(CanonicalModelError, match="linguagem"):
        _pou(language="ST")


def test_fbd_and_sfc_are_accepted_for_the_future():
    for language in ("FBD", "SFC"):
        assert _pou(language=language).language == language


# --- redes -------------------------------------------------------------------

def test_empty_boundary_marker_is_recorded_not_discarded():
    """Marcador vazio produziu divergencia FALSA na primeira analise do
    arquivo real -- registrar e a correcao."""
    boundary = NetworkBoundary(marker_id="m5", is_empty=True, order=4)
    pou = _pou(network_boundaries=[boundary])
    assert pou.to_dict()["network_boundaries"][0]["is_empty"] is True


def test_two_element_network_is_valid():
    """Rede legitima pode ter so bloco + bobina."""
    network = Network(network_id="n1", element_ids=["e1", "e2"],
                      reconstruction_status="confirmed_by_marker_and_connectivity")
    pou = _pou(elements=[_element("e1", "1", kind="block"),
                         _element("e2", "2", kind="coil")],
               networks=[network])
    assert pou.to_dict()["networks"][0]["element_ids"] == ["e1", "e2"]


def test_network_reconstruction_status_is_validated():
    with pytest.raises(CanonicalModelError, match="reconstruction_status"):
        Network(network_id="n", reconstruction_status="mais_ou_menos")


def test_network_records_which_evidence_supports_it():
    network = Network(
        network_id="n1", boundary_evidence_ids=["m1"], component_ids=["c1"],
        reconstruction_status="confirmed_by_marker_and_connectivity")
    dumped = _pou(networks=[network]).to_dict()["networks"][0]
    assert dumped["boundary_evidence_ids"] == ["m1"]
    assert dumped["component_ids"] == ["c1"]
    assert dumped["reconstruction_status"] == "confirmed_by_marker_and_connectivity"


# --- extensoes do fornecedor -------------------------------------------------

def test_vendor_extension_is_traceable_without_embedding_raw_xml():
    extension = VendorExtension(
        extension_id="x1", owner_id="e3", namespace="http://vendor/ldparallelbranch",
        tag="ParallelBranch", attributes={"mode": "sce"},
        normalized_classification="parallel_branch",
        raw_fragment_hash="abc123",
        source=SourceRef(source_file="pou-export", local_id="3"))
    dumped = _pou(vendor_extensions=[extension]).to_dict()["vendor_extensions"][0]

    assert dumped["attributes"] == {"mode": "sce"}
    assert dumped["raw_fragment_hash"] == "abc123"
    assert dumped["source"]["local_id"] == "3"
    assert "<ParallelBranch" not in json.dumps(dumped), (
        "o XML cru nao entra no JSON publico -- pode conter conteudo do cliente")


# --- serializacao ------------------------------------------------------------

def _rich_pou():
    block = _element("blk", "21", kind="block", type_name="EQ",
                     call_type="operator", pin_ids=["p_out"])
    coil = _element("coil", "24", kind="coil", value_text="SAIDA_B",
                    value_source_kind="variable", storage="none", negated=False)
    pin = Pin(pin_id="p_out", owner_element_id="blk", formal_parameter="Out1",
              direction="output", declaration_source="outputVariables")
    evidence = ConnectionEvidence(
        evidence_id="ev1", evidence_kind="plcopen_connection",
        source_element_ref="blk", target_element_ref="coil",
        source_pin_raw="SAIDA_B")
    edge = DerivedEdge(
        edge_id="d1", source_element_id="blk", target_element_id="coil",
        supporting_evidence_ids=["ev1"], resolved_source_pin="Out1",
        source_pin_resolution_method="declared_block_output_pins",
        source_pin_resolution_status="resolved_from_declared_block_pins",
        raw_connection_formal_parameter="SAIDA_B")
    return _pou(
        namespace="http://www.plcopen.org/xml/tc6_0200",
        interface=[InterfaceVariable(name="ENTRADA", group="inputVars",
                                     type_name="BOOL")],
        elements=[block, coil], pins=[pin], connection_evidence=[evidence],
        derived_edges=[edge],
        network_boundaries=[NetworkBoundary(marker_id="m1", order=0)],
        components=[ConnectedComponent(component_id="c1",
                                       element_ids=["blk", "coil"],
                                       discovery_method="without_rails")],
        networks=[Network(network_id="n1", element_ids=["blk", "coil"],
                          reconstruction_status="confirmed_by_marker_and_connectivity")],
        vendor_extensions=[VendorExtension(extension_id="x1", owner_id="blk",
                                           namespace="http://vendor/x", tag="T")],
        diagnostics=[Diagnostic(step="teste", message="msg")])


def test_serialization_is_deterministic():
    """Dois dumps do mesmo modelo precisam ser byte-a-byte identicos."""
    first = json.dumps(_rich_pou().to_dict(), sort_keys=False)
    second = json.dumps(_rich_pou().to_dict(), sort_keys=False)
    assert first == second


def test_serialization_order_does_not_depend_on_insertion_order():
    pou = _rich_pou()
    reversed_pou = _rich_pou()
    reversed_pou.elements = list(reversed(reversed_pou.elements))
    assert pou.to_dict()["elements"] == reversed_pou.to_dict()["elements"]


def test_round_trip_preserves_the_model():
    original = _rich_pou()
    restored = GraphicPOU.from_dict(original.to_dict())
    assert restored.to_dict() == original.to_dict()


def test_round_trip_does_not_duplicate_diagnostics():
    """A validacao roda de novo no from_dict; se ela reemitisse avisos, cada
    ida e volta inflaria a lista."""
    evidence = ConnectionEvidence(
        evidence_id="ev1", evidence_kind="plcopen_connection",
        source_element_ref="999", target_element_ref="e1")
    pou = _pou(elements=[_element("e1", "1")], connection_evidence=[evidence])

    once = len(pou.diagnostics)
    twice = GraphicPOU.from_dict(pou.to_dict())
    thrice = GraphicPOU.from_dict(twice.to_dict())

    assert once == len(twice.diagnostics) == len(thrice.diagnostics)


def test_output_declares_schema_version_and_model_kind():
    dumped = _rich_pou().to_dict()
    assert dumped["schema_version"] == 1
    assert dumped["model_kind"] == "graphic_pou"
    assert dumped["language"] == "LD"


def test_from_dict_refuses_a_foreign_model_kind():
    data = _rich_pou().to_dict()
    data["model_kind"] = "outra_coisa"
    with pytest.raises(CanonicalModelError, match="model_kind"):
        GraphicPOU.from_dict(data)


def test_from_dict_refuses_an_unsupported_schema_version():
    data = _rich_pou().to_dict()
    data["schema_version"] = 99
    with pytest.raises(CanonicalModelError, match="schema_version"):
        GraphicPOU.from_dict(data)


def test_serialized_model_holds_no_live_xml_objects():
    dumped = json.dumps(_rich_pou().to_dict())
    assert "Element object at" not in dumped
    assert "xml.etree" not in dumped

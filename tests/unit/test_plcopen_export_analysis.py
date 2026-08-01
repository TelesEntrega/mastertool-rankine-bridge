"""Análise offline do que `export_xml` produziu.

O ponto: descobrir o formato REAL sem presumi-lo. A semântica de `stPath`
era desconhecida, então nem a extensão do arquivo nem o prefixo de namespace
podem ser usados como critério — só os bytes e as URIs.
"""

from __future__ import annotations

import json

import pytest

from mastertool_bridge.automation.plcopen_export_analysis import (
    ExportAnalysisError,
    analyze_export_root,
    classify_export_analysis,
    write_analysis,
)

_PLCOPEN_NS = "http://www.plcopen.org/xml/tc6_0201"


def _ladder_xml(pou_name="FB_PISCA_EXEMPLO"):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<project xmlns="{_PLCOPEN_NS}">
  <contentHeader name="x" version="2.01"/>
  <types><pous>
    <pou name="{pou_name}" pouType="functionBlock">
      <body><LD>
        <contact localId="1"/><coil localId="2"/>
        <connectionPointIn/><connectionPointOut/>
      </LD></body>
    </pou>
  </pous></types>
</project>
"""


def _declaration_only_xml(pou_name="FB_PISCA_EXEMPLO"):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<project xmlns="{_PLCOPEN_NS}">
  <types><pous>
    <pou name="{pou_name}" pouType="functionBlock">
      <interface/>
    </pou>
  </pous></types>
</project>
"""


def test_graphical_body_is_P1(tmp_path):
    (tmp_path / "pou-export.xml").write_text(_ladder_xml(), encoding="utf-8")

    analysis = analyze_export_root(tmp_path, "FB_PISCA_EXEMPLO")

    assert analysis.result_case == "P1_graphical_body_present"
    assert analysis.element_counts["graphical_bodies"]["LD"] == 1
    assert analysis.element_counts["graphical_details"]["contact"] == 1
    assert analysis.target_match["found"] is True
    assert analysis.target_match["has_graphical_body"] is True
    assert "NÃO foi interpretada" in analysis.verdict


def test_declaration_only_is_P2(tmp_path):
    (tmp_path / "pou-export.xml").write_text(
        _declaration_only_xml(), encoding="utf-8")

    analysis = analyze_export_root(tmp_path, "FB_PISCA_EXEMPLO")

    assert analysis.result_case == "P2_declaration_only"
    assert analysis.target_match["found"] is True
    assert analysis.target_match["has_graphical_body"] is False


def test_no_output_is_P3(tmp_path):
    analysis = analyze_export_root(tmp_path, "X")
    assert analysis.result_case == "P3_no_output"


def test_non_xml_output_is_P4(tmp_path):
    (tmp_path / "pou-export").write_bytes(b"\x00\x01binario nao-xml")

    analysis = analyze_export_root(tmp_path, "X")

    assert analysis.result_case == "P4_unrecognized_format"
    assert analysis.xml_files[0].is_xml is False


def test_malformed_xml_is_P4_with_the_parse_error(tmp_path):
    (tmp_path / "pou-export.xml").write_text(
        "<project><unclosed>", encoding="utf-8")

    analysis = analyze_export_root(tmp_path, "X")

    assert analysis.result_case == "P4_unrecognized_format"
    assert analysis.xml_files[0].well_formed is False
    assert analysis.xml_files[0].parse_error


def test_xml_without_extension_is_still_analyzed(tmp_path):
    """A semântica de stPath era desconhecida -- o exportador pode produzir
    um nome sem `.xml`. Julgar por extensao perderia justamente o caso que
    motivou a guarda de diretorio."""
    (tmp_path / "pou-export").write_text(_ladder_xml(), encoding="utf-8")

    analysis = analyze_export_root(tmp_path, "FB_PISCA_EXEMPLO")

    assert analysis.xml_files[0].is_xml is True
    assert analysis.result_case == "P1_graphical_body_present"


def test_arbitrary_namespace_prefix_is_still_detected(tmp_path):
    """Prefixo e escolha do documento, nao do schema -- a deteccao e por URI."""
    (tmp_path / "e.xml").write_text(
        f'<?xml version="1.0"?>\n<zz:project xmlns:zz="{_PLCOPEN_NS}">'
        '<zz:types><zz:pous><zz:pou name="P" pouType="functionBlock">'
        '<zz:body><zz:LD><zz:coil/></zz:LD></zz:body>'
        "</zz:pou></zz:pous></zz:types></zz:project>", encoding="utf-8")

    analysis = analyze_export_root(tmp_path, "P")

    assert analysis.xml_files[0].plcopen_detected is True
    assert analysis.result_case == "P1_graphical_body_present"
    assert analysis.target_match["found"] is True


def test_directory_output_with_multiple_files(tmp_path):
    """Caso 'stPath e diretorio': varios arquivos dentro de uma arvore."""
    sub = tmp_path / "pou-export"
    sub.mkdir()
    (sub / "a.xml").write_text(_ladder_xml("A"), encoding="utf-8")
    (sub / "b.xml").write_text(_declaration_only_xml("B"), encoding="utf-8")

    analysis = analyze_export_root(tmp_path, "A")

    assert len(analysis.xml_files) == 2
    assert analysis.result_case == "P1_graphical_body_present"
    assert analysis.target_match["found"] is True


def test_target_not_found_is_reported_without_failing(tmp_path):
    (tmp_path / "e.xml").write_text(_ladder_xml("OUTRA"), encoding="utf-8")

    analysis = analyze_export_root(tmp_path, "FB_PISCA_EXEMPLO")

    assert analysis.target_match["searched"] is True
    assert analysis.target_match["found"] is False
    # Corpo grafico existe no arquivo, mesmo sem o alvo -- os dois fatos sao
    # independentes e nao podem ser fundidos.
    assert analysis.result_case == "P1_graphical_body_present"


def test_oversized_file_is_skipped_not_parsed(tmp_path, monkeypatch):
    import mastertool_bridge.automation.plcopen_export_analysis as mod
    monkeypatch.setattr(mod, "MAX_XML_PARSE_BYTES", 10)
    (tmp_path / "big.xml").write_text(_ladder_xml(), encoding="utf-8")

    analysis = analyze_export_root(tmp_path, "X")

    assert analysis.xml_files[0].parse_error == "parse_skipped_too_large"
    assert analysis.result_case == "P4_unrecognized_format"


def test_write_analysis_emits_the_three_artifacts(tmp_path):
    root = tmp_path / "export-root"
    root.mkdir()
    (root / "e.xml").write_text(_ladder_xml(), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()

    written = write_analysis(analyze_export_root(root, "FB_PISCA_EXEMPLO"), out)
    names = {p.name for p in written}

    assert {"xml-files.json", "xml-structure-inventory.json",
            "target-object-match.json"} <= names
    data = json.loads((out / "xml-files.json").read_text(encoding="utf-8"))
    assert data[0]["sha256"]


def test_missing_export_root_is_refused(tmp_path):
    with pytest.raises(ExportAnalysisError, match="inexistente"):
        analyze_export_root(tmp_path / "nao-existe")


def test_classification_is_pure_and_reusable():
    """Mesma disciplina dos probes: funcao pura, reaplicavel a coletas
    arquivadas sem reimplementacao."""
    case, verdict = classify_export_analysis([], {}, {})
    assert case == "P3_no_output"
    assert verdict

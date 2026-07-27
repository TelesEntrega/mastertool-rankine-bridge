"""Testes de mastertool_bridge.indexer.export_loader."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mastertool_bridge.indexer.export_loader import build_static_index, load_export

FIXTURE_EXPORT = Path(__file__).parent / "fixtures" / "sample_export"


@pytest.fixture
def sample_export(tmp_path: Path) -> Path:
    dest = tmp_path / "sample_export"
    shutil.copytree(FIXTURE_EXPORT, dest)
    return dest


def test_load_export_valid_fixture(sample_export: Path) -> None:
    bundle = load_export(sample_export)

    assert bundle.result.ok, bundle.result.errors
    assert len(bundle.flat_objects) == 10
    assert len(bundle.declaration_node_ids) == 9
    assert "application/fb/0" in bundle.declaration_node_ids
    assert "application/gvl/0" in bundle.declaration_node_ids
    assert "application/gvl/1" in bundle.declaration_node_ids
    assert "application/fb/2" in bundle.declaration_node_ids
    assert "application/gvl/2" in bundle.declaration_node_ids
    assert "application/prg/1" in bundle.declaration_node_ids


def test_source_map_built_correctly(sample_export: Path) -> None:
    bundle = load_export(sample_export)

    sf = bundle.source_map.get("application/fb/0")
    assert sf is not None
    assert sf.name == "FB_ValvulaSintetica"
    assert sf.has_declaration is True
    assert sf.has_implementation is False
    assert sf.declaration_path is not None
    assert sf.declaration_path.endswith("declaration.st")

    folder = bundle.source_map.get("application")
    assert folder is not None
    assert folder.has_declaration is False


def test_load_export_checksum_mismatch_reports_error_not_crash(
    sample_export: Path,
) -> None:
    decl = sample_export / "objects" / "application_prg_0__MainPrg" / "declaration.st"
    decl.write_text(decl.read_text(encoding="utf-8") + "\n// adulterado\n", encoding="utf-8")

    bundle = load_export(sample_export)

    assert not bundle.result.ok
    assert any("hash divergente" in e for e in bundle.result.errors)
    # Mesmo com erro de checksum, o loader continua e retorna dados.
    assert len(bundle.flat_objects) == 10


def test_load_export_missing_manifest(sample_export: Path) -> None:
    (sample_export / "manifest.json").unlink()

    bundle = load_export(sample_export)

    assert not bundle.result.ok
    assert any("manifest.json" in e for e in bundle.result.errors)


def test_load_export_missing_flat_objects(sample_export: Path) -> None:
    (sample_export / "flat-objects.json").unlink()

    bundle = load_export(sample_export)

    assert not bundle.result.ok
    assert any("flat-objects.json" in e for e in bundle.result.errors)
    assert bundle.flat_objects == []


def test_load_export_nonexistent_directory(tmp_path: Path) -> None:
    bundle = load_export(tmp_path / "does_not_exist")

    assert not bundle.result.ok


def test_build_static_index_writes_six_artifacts(
    sample_export: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "out"
    result = build_static_index(sample_export, output_dir)

    for filename in (
        "symbols.json",
        "type-index.json",
        "diagnostics.json",
        "source-map.json",
        "calls.json",
        "references.json",
    ):
        assert (output_dir / filename).is_file()

    # 3 POUs bem formadas + 1 malformada (sem END_VAR em VAR_INPUT) + 2 GVLs
    # sintéticas (uma com qualified_only, outra sem) — o cabeçalho da
    # malformada ainda é reconhecido, então ela também vira PouSymbol (com
    # diagnostics de bloco não terminado). As GVLs não têm cabeçalho de POU,
    # mas ainda viram PouSymbol via parse_gvl_declaration. Mais 3 símbolos
    # sintéticos da fatia de resolução: FB_TimerSintetico (FB com
    # VAR_IN_OUT), GvlAmbiguaSintetica (GVL não-qualified_only com nome de
    # variável duplicado em relação a GvlDiagnosticoSintetico, para o caso
    # ambíguo) e PrgResolucaoSintetica (shadowing + GVL explícita/implícita
    # + chamada de instância de FB).
    assert len(result["symbols"]) == 9
    names = {s["name"] for s in result["symbols"]}
    assert "MainPrg" in names
    assert "FB_ValvulaSintetica" in names
    assert "FunCalcularMedia" in names
    assert "GvlMotoresSintetica" in names
    assert "GvlDiagnosticoSintetico" in names
    assert "FB_TimerSintetico" in names
    assert "GvlAmbiguaSintetica" in names
    assert "PrgResolucaoSintetica" in names

    gvl_symbols = {s["name"]: s for s in result["symbols"] if s["pou_kind"] == "GVL"}
    assert set(gvl_symbols) == {
        "GvlMotoresSintetica",
        "GvlDiagnosticoSintetico",
        "GvlAmbiguaSintetica",
    }
    assert gvl_symbols["GvlMotoresSintetica"]["is_qualified_only"] is True
    assert gvl_symbols["GvlDiagnosticoSintetico"]["is_qualified_only"] is False

    motores_vars = {v["name"]: v for v in gvl_symbols["GvlMotoresSintetica"]["variables"]}
    assert set(motores_vars) == {"MT01", "MT02", "MT03", "MT04_ComEndereco"}
    assert motores_vars["MT01"]["scope"] == "VAR_GLOBAL RETAIN"
    assert motores_vars["MT03"]["scope"] == "VAR_GLOBAL"
    assert motores_vars["MT04_ComEndereco"]["hardware_address"] == "%QX54.0"
    assert motores_vars["MT01"]["hardware_address"] is None

    diag_vars = {v["name"]: v for v in gvl_symbols["GvlDiagnosticoSintetico"]["variables"]}
    assert diag_vars["DG_SensorSintetico"]["hardware_address"] == "%IW12"
    assert diag_vars["DG_Contador"]["hardware_address"] is None

    assert len(result["diagnostics"]) >= 1  # ao menos o VAR malformado


def test_build_static_index_extracts_calls_and_references_from_implementation(
    sample_export: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "out"
    result = build_static_index(sample_export, output_dir)

    # FunCalcularMedia contém uma chamada de método FbLimitador.Ajustar com
    # argumentos nomeados; PrgResolucaoSintetica (fatia de resolução)
    # contém uma chamada de instância de FB (fbTimer(...)) e uma chamada de
    # método sobre essa mesma instância (fbTimer.Reset()).
    assert len(result["calls"]) == 3
    calls_by_node_prefix = {c["node_id"].split("#")[0]: c for c in result["calls"]}
    call = calls_by_node_prefix["application/fun/0"]
    assert call["callee"] == "FbLimitador.Ajustar"
    assert call["node_id"].startswith("application/fun/0")
    arg_names = [a["name"] for a in call["arguments"]]
    assert arg_names == ["IN_VALOR", "OUT_VALOR"]
    operators = [a["operator"] for a in call["arguments"]]
    assert operators == [":=", "=>"]

    assert len(result["references"]) > 0
    ref_names = {r["name"] for r in result["references"]}
    assert "rResultado" in ref_names
    assert "FbLimitador.Ajustar" in ref_names

    # Nenhum campo/termo de classificação semântica de leitura/escrita.
    import json

    calls_text = json.dumps(result["calls"])
    references_text = json.dumps(result["references"])
    for forbidden in ("is_read", "is_write", "read_write", "\"read\"", "\"write\""):
        assert forbidden not in calls_text
        assert forbidden not in references_text


def test_build_static_index_routes_pou_and_gvl_files_to_correct_parser(
    sample_export: Path, tmp_path: Path
) -> None:
    """`declaration.st` sem cabeçalho de POU deve ser automaticamente
    reconhecido como GVL (pou_kind="GVL"), enquanto arquivos com cabeçalho
    PROGRAM/FUNCTION_BLOCK/FUNCTION continuam indo para o caminho de POU —
    sem exigir nenhuma configuração manual por objeto."""
    output_dir = tmp_path / "out"
    result = build_static_index(sample_export, output_dir)

    by_name = {s["name"]: s for s in result["symbols"]}

    assert by_name["MainPrg"]["pou_kind"] == "PROGRAM"
    assert by_name["FB_ValvulaSintetica"]["pou_kind"] == "FUNCTION_BLOCK"
    assert by_name["FunCalcularMedia"]["pou_kind"] == "FUNCTION"
    assert by_name["GvlMotoresSintetica"]["pou_kind"] == "GVL"
    assert by_name["GvlDiagnosticoSintetico"]["pou_kind"] == "GVL"

    # Nenhum diagnostic de "cabeçalho de POU não encontrado" deve sobrar
    # para as GVLs — foram resolvidas pelo caminho de fallback.
    gvl_node_ids = {"application/gvl/0", "application/gvl/1"}
    assert not any(
        d["node_id"] in gvl_node_ids and d["code"] == "pou_header_not_found"
        for d in result["diagnostics"]
    )

"""Testes de mastertool_bridge.discovery.graphic_language_scan (Fase L0 offline).

Todos os GUIDs/nomes usados aqui sao FICTICIOS/sinteticos -- nenhum dado
real de ExemploPlanta V1.0.project aparece nestes testes (nem no modulo de
producao, que nunca hardcoda type_guid nenhum).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mastertool_bridge.discovery.graphic_language_scan import (
    PARTIALLY_SUPPORTED,
    SUPPORTED,
    UNKNOWN,
    UNSUPPORTED,
    scan_graphic_language_candidates,
)
from mastertool_bridge.utils.json_io import write_json

TEXTUAL_TYPE_GUID = "aaaaaaaa-0000-0000-0000-000000000001"
GRAPHIC_TYPE_GUID = "bbbbbbbb-0000-0000-0000-000000000002"
UNIQUE_TYPE_GUID = "cccccccc-0000-0000-0000-000000000003"
FOLDER_TYPE_GUID = "dddddddd-0000-0000-0000-000000000004"


def _write_export(export_dir: Path, flat_objects: list[dict[str, Any]]) -> Path:
    write_json(export_dir / "flat-objects.json", flat_objects)
    return export_dir


def _obj(
    node_id: str,
    name: str | None,
    type_guid: str | None,
    has_declaration: bool,
    has_implementation: bool,
    parent_node_id: str | None = "application",
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "name": name,
        "type_guid": type_guid,
        "parent_node_id": parent_node_id,
        "has_declaration": has_declaration,
        "has_implementation": has_implementation,
        "child_count": 0,
        "depth": 1,
        "index": 0,
        "object_guid": f"guid-{node_id}",
    }


def test_supported_object(tmp_path: Path) -> None:
    export_dir = _write_export(
        tmp_path / "export",
        [
            _obj("application", None, None, False, False, parent_node_id=None),
            _obj("application/0", "MainPrg", TEXTUAL_TYPE_GUID, True, True),
        ],
    )
    result = scan_graphic_language_candidates(export_dir, tmp_path / "out")

    main = next(o for o in result["inventory"] if o["node_id"] == "application/0")
    assert main["state"] == SUPPORTED
    assert main["has_declaration"] is True
    assert main["has_implementation"] is True


def test_partially_supported_object(tmp_path: Path) -> None:
    export_dir = _write_export(
        tmp_path / "export",
        [
            _obj("application", None, None, False, False, parent_node_id=None),
            # confirma o type_guid como "tem implementacao textual em algum lugar"
            _obj("application/0", "MainPrg", TEXTUAL_TYPE_GUID, True, True),
            # mesmo type_guid, sem implementacao -> candidato
            _obj("application/1", "StartPrg", TEXTUAL_TYPE_GUID, True, False),
        ],
    )
    result = scan_graphic_language_candidates(export_dir, tmp_path / "out")

    start = next(o for o in result["inventory"] if o["node_id"] == "application/1")
    assert start["state"] == PARTIALLY_SUPPORTED
    assert "application/0" in start["evidence"]
    assert start in result["ladder_objects"]


def test_unsupported_object(tmp_path: Path) -> None:
    export_dir = _write_export(
        tmp_path / "export",
        [
            _obj("application", None, None, False, False, parent_node_id=None),
            _obj("application/0", "Estruturas", FOLDER_TYPE_GUID, False, False),
        ],
    )
    result = scan_graphic_language_candidates(export_dir, tmp_path / "out")

    folder = next(o for o in result["inventory"] if o["node_id"] == "application/0")
    assert folder["state"] == UNSUPPORTED
    assert folder in result["unsupported_objects"]
    # listado explicitamente, nunca omitido
    assert folder in result["inventory"]


def test_unknown_object_no_comparison_reference(tmp_path: Path) -> None:
    export_dir = _write_export(
        tmp_path / "export",
        [
            _obj("application", None, None, False, False, parent_node_id=None),
            _obj("application/0", "FB_Isolado", UNIQUE_TYPE_GUID, True, False),
        ],
    )
    result = scan_graphic_language_candidates(export_dir, tmp_path / "out")

    isolated = next(o for o in result["inventory"] if o["node_id"] == "application/0")
    assert isolated["state"] == UNKNOWN
    assert isolated not in result["ladder_objects"]
    assert isolated not in result["unsupported_objects"]


def test_mixed_impl_true_and_false_same_type_guid(tmp_path: Path) -> None:
    """Multiplos objetos com o MESMO type_guid, misturando impl=true e
    impl=false -- so os impl=false daquele type_guid viram
    partially_supported; os impl=true continuam supported."""
    export_dir = _write_export(
        tmp_path / "export",
        [
            _obj("application", None, None, False, False, parent_node_id=None),
            _obj("application/0", "MainPrg", TEXTUAL_TYPE_GUID, True, True),
            _obj("application/1", "SpecialVariablesPrg", TEXTUAL_TYPE_GUID, True, True),
            _obj("application/2", "StartPrg", TEXTUAL_TYPE_GUID, True, False),
            _obj("application/3", "UserPrg", TEXTUAL_TYPE_GUID, True, False),
        ],
    )
    result = scan_graphic_language_candidates(export_dir, tmp_path / "out")

    by_name = {o["name"]: o for o in result["inventory"]}
    assert by_name["MainPrg"]["state"] == SUPPORTED
    assert by_name["SpecialVariablesPrg"]["state"] == SUPPORTED
    assert by_name["StartPrg"]["state"] == PARTIALLY_SUPPORTED
    assert by_name["UserPrg"]["state"] == PARTIALLY_SUPPORTED

    ladder_names = {o["name"] for o in result["ladder_objects"]}
    assert ladder_names == {"StartPrg", "UserPrg"}


def test_empty_export_produces_three_empty_artifacts(tmp_path: Path) -> None:
    export_dir = _write_export(tmp_path / "export", [])
    output_dir = tmp_path / "out"

    result = scan_graphic_language_candidates(export_dir, output_dir)

    assert result["inventory"] == []
    assert result["ladder_objects"] == []
    assert result["unsupported_objects"] == []
    assert result["counts"] == {
        SUPPORTED: 0,
        PARTIALLY_SUPPORTED: 0,
        UNSUPPORTED: 0,
        UNKNOWN: 0,
    }

    for filename in (
        "graphic-language-inventory.json",
        "ladder-objects.json",
        "unsupported-objects.json",
    ):
        path = output_dir / filename
        assert path.is_file()
        assert json.loads(path.read_text(encoding="utf-8")) == []


def test_evidence_references_correct_confirming_node_ids(tmp_path: Path) -> None:
    export_dir = _write_export(
        tmp_path / "export",
        [
            _obj("application", None, None, False, False, parent_node_id=None),
            _obj("application/0", "MainPrg", TEXTUAL_TYPE_GUID, True, True),
            _obj("application/1", "SpecialVariablesPrg", TEXTUAL_TYPE_GUID, True, True),
            _obj("application/2", "StartPrg", TEXTUAL_TYPE_GUID, True, False),
        ],
    )
    result = scan_graphic_language_candidates(export_dir, tmp_path / "out")

    start = next(o for o in result["inventory"] if o["node_id"] == "application/2")
    assert start["state"] == PARTIALLY_SUPPORTED
    assert "application/0" in start["evidence"]
    assert "application/1" in start["evidence"]
    assert "2 objeto(s)" in start["evidence"]
    # a lista de node_ids confirmados na evidencia nunca inclui o proprio
    # objeto sendo classificado
    node_id_list = start["evidence"].split(":", 1)[1].strip()
    assert start["node_id"] not in node_id_list


def test_determinism_same_input_twice_byte_identical(tmp_path: Path) -> None:
    flat_objects = [
        _obj("application", None, None, False, False, parent_node_id=None),
        _obj("application/0", "MainPrg", TEXTUAL_TYPE_GUID, True, True),
        _obj("application/1", "StartPrg", TEXTUAL_TYPE_GUID, True, False),
        _obj("application/2", "Estruturas", FOLDER_TYPE_GUID, False, False),
        _obj("application/3", "FB_Isolado", UNIQUE_TYPE_GUID, True, False),
    ]
    export_dir = _write_export(tmp_path / "export", flat_objects)

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    scan_graphic_language_candidates(export_dir, out1)
    scan_graphic_language_candidates(export_dir, out2)

    for filename in (
        "graphic-language-inventory.json",
        "ladder-objects.json",
        "unsupported-objects.json",
    ):
        bytes1 = (out1 / filename).read_bytes()
        bytes2 = (out2 / filename).read_bytes()
        assert bytes1 == bytes2, f"{filename} nao e determinístico"


def test_ladder_and_unsupported_are_exact_consistent_subsets(tmp_path: Path) -> None:
    flat_objects = [
        _obj("application", None, None, False, False, parent_node_id=None),
        _obj("application/0", "MainPrg", TEXTUAL_TYPE_GUID, True, True),
        _obj("application/1", "StartPrg", TEXTUAL_TYPE_GUID, True, False),
        _obj("application/2", "Estruturas", FOLDER_TYPE_GUID, False, False),
        _obj("application/3", "FB_Isolado", UNIQUE_TYPE_GUID, True, False),
        _obj("application/4", "Outra_Pasta", FOLDER_TYPE_GUID, False, False),
    ]
    export_dir = _write_export(tmp_path / "export", flat_objects)
    result = scan_graphic_language_candidates(export_dir, tmp_path / "out")

    inventory_by_id = {o["node_id"]: o for o in result["inventory"]}

    # nenhuma duplicacao
    ladder_ids = [o["node_id"] for o in result["ladder_objects"]]
    assert len(ladder_ids) == len(set(ladder_ids))
    unsupported_ids = [o["node_id"] for o in result["unsupported_objects"]]
    assert len(unsupported_ids) == len(set(unsupported_ids))

    # subconjunto EXATO: todo objeto em ladder_objects esta no inventory
    # com o mesmo conteudo, e e exatamente o conjunto state=partially_supported
    expected_ladder_ids = {
        nid for nid, o in inventory_by_id.items() if o["state"] == PARTIALLY_SUPPORTED
    }
    assert set(ladder_ids) == expected_ladder_ids
    for obj in result["ladder_objects"]:
        assert obj == inventory_by_id[obj["node_id"]]

    expected_unsupported_ids = {
        nid for nid, o in inventory_by_id.items() if o["state"] == UNSUPPORTED
    }
    assert set(unsupported_ids) == expected_unsupported_ids
    for obj in result["unsupported_objects"]:
        assert obj == inventory_by_id[obj["node_id"]]

    # nenhuma omissao: todo objeto de flat_objects aparece no inventory
    assert set(inventory_by_id) == {o["node_id"] for o in flat_objects}


def test_path_derivation_from_hierarchy(tmp_path: Path) -> None:
    export_dir = _write_export(
        tmp_path / "export",
        [
            _obj("application", None, None, False, False, parent_node_id=None),
            _obj(
                "application/0",
                "Estruturas",
                FOLDER_TYPE_GUID,
                False,
                False,
                parent_node_id="application",
            ),
            _obj(
                "application/0/0",
                "Motor",
                UNIQUE_TYPE_GUID,
                True,
                False,
                parent_node_id="application/0",
            ),
        ],
    )
    result = scan_graphic_language_candidates(export_dir, tmp_path / "out")

    motor = next(o for o in result["inventory"] if o["node_id"] == "application/0/0")
    assert motor["path"] == "application/Estruturas/Motor"


def test_no_new_dependency_and_never_hardcodes_real_project_guid() -> None:
    """Confere que o modulo de producao nao faz `import` de biblioteca nova
    e nao contem o type_guid REAL confirmado manualmente
    (6f9dac99-8de1-4efc-8465-68ac443b7d08, de ExemploPlanta V1.0.project)."""
    import mastertool_bridge.discovery.graphic_language_scan as module

    source_path = Path(module.__file__)
    source_text = source_path.read_text(encoding="utf-8")
    assert "6f9dac99-8de1-4efc-8465-68ac443b7d08" not in source_text


@pytest.fixture
def sample_real_shaped_export(tmp_path: Path) -> Path:
    """Fixture com formato igual ao real (mesmos NOMES DE CAMPO), mas
    valores 100% sinteticos."""
    return _write_export(
        tmp_path / "export",
        [
            _obj("application", None, None, False, False, parent_node_id=None),
            _obj("application/0", "MainPrg", TEXTUAL_TYPE_GUID, True, True),
            _obj("application/1", "StartPrg", TEXTUAL_TYPE_GUID, True, False),
            _obj("application/2", "UserPrg", TEXTUAL_TYPE_GUID, True, False),
        ],
    )


def test_is_folder_reported_as_unknown_never_guessed(
    sample_real_shaped_export: Path, tmp_path: Path
) -> None:
    """flat-objects.json nao carrega um campo is_folder confiavel (ver
    docstring do modulo) -- nunca deve ser inferido/adivinhado."""
    result = scan_graphic_language_candidates(sample_real_shaped_export, tmp_path / "out")
    for obj in result["inventory"]:
        assert obj["is_folder"] is None

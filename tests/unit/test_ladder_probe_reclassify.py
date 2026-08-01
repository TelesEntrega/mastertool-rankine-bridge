"""Reclassificacao offline de execucoes arquivadas do probe 17.

O ponto destes testes nao e so "o caso muda de B para D": e que a coleta
BRUTA sobrevive intacta. Um artefato arquivado que muda em silencio deixa de
ser evidencia -- e a revisao de interpretacao nao pode custar isso.
"""

from __future__ import annotations

import json

import pytest

from mastertool_bridge.discovery.ladder_probe_reclassify import (
    REVISION_JSON_FILENAME,
    REVISION_MD_FILENAME,
    ReclassifyError,
    reclassify_probe_dir,
    write_revision,
)


def _make_probe_dir(tmp_path, *, dir_members, candidates, control_seen=True,
                    clr_seen=False, safe_getters=24,
                    manifest_case="B", manifest_status="ok"):
    d = tmp_path / "probe"
    d.mkdir()
    (d / "control-validation.json").write_text(json.dumps({
        "control_member": "textual_declaration",
        "seen_by_dynamic_surface": control_seen,
        "seen_by_clr_reflection": clr_seen,
        "dynamic_probe_validated": control_seen and not clr_seen,
    }), encoding="utf-8")
    (d / "dynamic-dir-members.json").write_text(
        json.dumps([{"name": n} for n in dir_members]), encoding="utf-8")
    (d / "ladder-candidate-members.json").write_text(
        json.dumps([{"name": n} for n in candidates]), encoding="utf-8")
    (d / "safe-getter-results.json").write_text(
        json.dumps([{"member": "m%d" % i} for i in range(safe_getters)]),
        encoding="utf-8")
    if manifest_case is not None:
        (d / "manifest.json").write_text(json.dumps({
            "result_case": manifest_case, "status": manifest_status}),
            encoding="utf-8")
    return d


def test_empty_enumeration_is_reclassified_from_B_to_D(tmp_path):
    """O cenario real de 2026-07-27."""
    d = _make_probe_dir(tmp_path, dir_members=[], candidates=[])

    revision = reclassify_probe_dir(d)

    assert revision.original_result_case == "B"
    assert revision.revised_result_case == "D"
    assert revision.revised_status == "dynamic_discovery_channel_unavailable"
    assert revision.dynamic_named_access_validated is True
    assert revision.dynamic_enumeration_available is False
    assert revision.candidate_search_exhaustive is False
    assert revision.changed is True


def test_real_enumeration_without_candidates_stays_B(tmp_path):
    d = _make_probe_dir(tmp_path, dir_members=["banana", "abacaxi"], candidates=[])

    revision = reclassify_probe_dir(d)

    assert revision.revised_result_case == "B"
    assert revision.dynamic_enumeration_available is True
    assert revision.changed is False


def test_control_absent_is_C(tmp_path):
    d = _make_probe_dir(tmp_path, dir_members=["x"], candidates=[],
                        control_seen=False)

    revision = reclassify_probe_dir(d)

    assert revision.revised_result_case == "C"
    assert revision.revised_status == "inconclusive"


def test_control_seen_by_clr_reflection_invalidates_named_access(tmp_path):
    """Se a reflexao CLR ja via o controle, ele nao prova nada sobre a
    superficie dinamica."""
    d = _make_probe_dir(tmp_path, dir_members=["x"], candidates=[],
                        control_seen=True, clr_seen=True)

    revision = reclassify_probe_dir(d)

    assert revision.dynamic_named_access_validated is False
    assert revision.revised_result_case == "C"


def test_write_revision_preserves_the_raw_collection(tmp_path):
    """A garantia central: nenhum arquivo da coleta e tocado."""
    d = _make_probe_dir(tmp_path, dir_members=[], candidates=[])
    before = {p.name: p.read_bytes() for p in d.iterdir()}

    json_path, md_path = write_revision(reclassify_probe_dir(d))

    for name, content in before.items():
        assert (d / name).read_bytes() == content, f"{name} foi alterado"
    assert json_path.name == REVISION_JSON_FILENAME
    assert md_path.name == REVISION_MD_FILENAME


def test_original_manifest_keeps_its_wrong_verdict(tmp_path):
    """A revisao NAO reescreve o manifest coberto por checksum -- ele segue
    dizendo 'B', e a correcao vive no arquivo novo."""
    d = _make_probe_dir(tmp_path, dir_members=[], candidates=[])
    write_revision(reclassify_probe_dir(d))

    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["result_case"] == "B"

    revision = json.loads((d / REVISION_JSON_FILENAME).read_text(encoding="utf-8"))
    assert revision["revised"]["result_case"] == "D"
    assert revision["original"]["result_case"] == "B"
    assert revision["raw_collection_preserved"] is True


def test_revision_markdown_states_the_conclusion_is_barred(tmp_path):
    d = _make_probe_dir(tmp_path, dir_members=[], candidates=[])
    _json_path, md_path = write_revision(reclassify_probe_dir(d))

    md = md_path.read_text(encoding="utf-8")
    assert "Nenhuma conclusao pode ser feita" in md
    assert "coleta não foi refeita" in md


def test_missing_artifact_is_reported_by_name(tmp_path):
    d = _make_probe_dir(tmp_path, dir_members=[], candidates=[])
    (d / "control-validation.json").unlink()

    with pytest.raises(ReclassifyError, match="control-validation.json"):
        reclassify_probe_dir(d)


def test_nonexistent_directory_is_refused(tmp_path):
    with pytest.raises(ReclassifyError, match="inexistente"):
        reclassify_probe_dir(tmp_path / "nao-existe")

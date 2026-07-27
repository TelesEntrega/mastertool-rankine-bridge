import json

from mastertool_bridge.export.validator import validate_export


def test_valid_export_passes(sample_export):
    result = validate_export(sample_export)
    assert result.ok, result.errors


def test_fixture_without_checksums_passes_with_warning(sample_project_dir):
    result = validate_export(sample_project_dir)
    assert result.ok, result.errors
    assert any("checksums" in w for w in result.warnings)


def test_missing_manifest_fails(tmp_path):
    result = validate_export(tmp_path)
    assert not result.ok
    assert any("export-manifest.json" in e for e in result.errors)


def test_tampered_file_fails_checksum(sample_export):
    target = sample_export / "objects" / "programs" / "MainPrg" / "implementation.st"
    target.write_text(target.read_text(encoding="utf-8") + "\n// adulterado\n",
                      encoding="utf-8")
    result = validate_export(sample_export)
    assert not result.ok
    assert any("hash divergente" in e for e in result.errors)


def test_manifest_not_read_only_fails(sample_export):
    manifest_path = sample_export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["safety"]["project_modified"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = validate_export(sample_export, check_checksums=False)
    assert not result.ok


def test_invalid_manifest_schema_fails(sample_export):
    manifest_path = sample_export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["statistics"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = validate_export(sample_export, check_checksums=False)
    assert not result.ok

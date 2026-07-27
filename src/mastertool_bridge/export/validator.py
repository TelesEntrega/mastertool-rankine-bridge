"""Validação de um diretório de export: manifesto, schemas, checksums."""

from __future__ import annotations

from pathlib import Path

import jsonschema

from mastertool_bridge.constants import (CHECKSUMS_FILENAME, MANIFEST_FILENAME,
                                         SCHEMA_DIR)
from mastertool_bridge.models import ValidationResult
from mastertool_bridge.utils.hashing import verify_checksums
from mastertool_bridge.utils.json_io import read_json


def _load_schema(name: str) -> dict:
    return read_json(SCHEMA_DIR / name)


def validate_against_schema(data: dict, schema_name: str) -> list[str]:
    schema = _load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in err.absolute_path) or '<raiz>'}: {err.message}"
        for err in sorted(validator.iter_errors(data), key=str)
    ]


def validate_export(export_dir: Path, check_checksums: bool = True) -> ValidationResult:
    export_dir = Path(export_dir)
    result = ValidationResult(subject=str(export_dir))

    if not export_dir.is_dir():
        result.add_error("Diretório de export não existe.")
        return result

    # 1. Manifesto presente e válido
    manifest_path = export_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        result.add_error(f"{MANIFEST_FILENAME} ausente.")
        return result
    try:
        manifest = read_json(manifest_path)
    except ValueError as exc:
        result.add_error(f"{MANIFEST_FILENAME} não é JSON válido: {exc}")
        return result
    for issue in validate_against_schema(manifest, "project-manifest.schema.json"):
        result.add_error(f"manifesto: {issue}")

    # 2. Modo somente leitura declarado
    if manifest.get("mode") != "read_only":
        result.add_error("Manifesto não declara mode=read_only.")
    safety = manifest.get("safety", {})
    if safety.get("project_modified") is not False:
        result.add_error("safety.project_modified deveria ser false.")

    # 3. Metadados de objetos válidos
    objects_root = export_dir / "objects"
    if objects_root.is_dir():
        for metadata_path in sorted(objects_root.glob("*/*/metadata.json")):
            try:
                metadata = read_json(metadata_path)
            except ValueError as exc:
                result.add_error(f"{metadata_path.relative_to(export_dir)}: "
                                 f"JSON inválido: {exc}")
                continue
            for issue in validate_against_schema(metadata, "object.schema.json"):
                result.add_error(
                    f"{metadata_path.relative_to(export_dir)}: {issue}")
    else:
        result.add_warning("Diretório objects/ ausente (export só de descoberta?).")

    # 4. Checksums
    checksums_path = export_dir / CHECKSUMS_FILENAME
    if checksums_path.is_file():
        if check_checksums:
            for issue in verify_checksums(export_dir, checksums_path):
                result.add_error(f"checksums: {issue}")
    else:
        result.add_warning(f"{CHECKSUMS_FILENAME} ausente.")

    return result

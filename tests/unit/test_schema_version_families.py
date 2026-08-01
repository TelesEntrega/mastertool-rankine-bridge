"""Versões de schema são POR FAMÍLIA de artefato, nunca globais.

`schema_version` não é um campo único do projeto: são contratos independentes
que hoje coincidem no valor, e que precisam poder divergir amanhã sem que um
arraste o outro. Duas famílias convivem por motivo real
(`docs/19-contratos-de-execucao.md`, seção 7):

* artefatos internos do host → **inteiro**, constante própria por contrato;
* artefatos de probe/export do IronPython → **string** `"1.0"`, formalizada
  pelos cinco JSON Schemas em `src/mastertool_bridge/schemas/`.

O que estes testes protegem: que ninguém "uniformize" as duas famílias, que
nenhuma constante vire global, e que um leitor não passe a aceitar a versão de
uma família que não é a dele — o que ligaria silenciosamente artefatos
incompatíveis.
"""

from __future__ import annotations

import ast
import io
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "mastertool_bridge"
SCHEMAS_DIR = SRC / "schemas"

# Família INTEIRA: módulo → nome da constante que declara a versão daquele
# contrato. Cada uma é própria de propósito — ver docstring.
INTEGER_FAMILY = {
    "automation/config_models.py": "SCHEMA_VERSION",
    "indexer/query_response.py": "SCHEMA_VERSION",
    "plcopen/canonical_model.py": "SCHEMA_VERSION",
    "plcopen/structure_map.py": "STRUCTURE_MAP_SCHEMA_VERSION",
    "automation/plcopen_export_analysis.py": "ANALYSIS_SCHEMA_VERSION",
    "automation/host_validation_revision.py": "REVISION_SCHEMA_VERSION",
    "discovery/ladder_probe_reclassify.py": "RECLASSIFY_SCHEMA_VERSION",
}


def _module_constant(rel_path: str, name: str):
    tree = ast.parse(io.open(SRC / rel_path, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{rel_path} não declara a constante {name}")


@pytest.mark.parametrize("rel_path,const_name", sorted(INTEGER_FAMILY.items()))
def test_integer_family_declares_its_own_constant(rel_path, const_name):
    value = _module_constant(rel_path, const_name)
    assert isinstance(value, int) and not isinstance(value, bool), (
        f"{rel_path}:{const_name} deveria ser inteiro, é {type(value).__name__}")
    assert value == 1


def test_integer_family_has_no_stray_literals():
    """Nenhum `"schema_version": 1` solto nos módulos da família inteira.

    Literal solto é o que torna impossível evoluir um contrato sem caçar
    ocorrências pelo repositório inteiro.
    """
    offenders = []
    for rel_path in INTEGER_FAMILY:
        tree = ast.parse(io.open(SRC / rel_path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant) and key.value == "schema_version"
                        and isinstance(value, ast.Constant)):
                    offenders.append(f"{rel_path}:{value.lineno}")
    assert not offenders, f"literal solto de schema_version: {offenders}"


def test_no_global_schema_version_constant_exists():
    """Uma constante única para o projeto inteiro acoplaria contratos que
    precisam evoluir separados — foi decisão explícita não ter uma."""
    forbidden = ("ARTIFACT_SCHEMA_VERSION", "GLOBAL_SCHEMA_VERSION",
                 "PROJECT_SCHEMA_VERSION")
    hits = []
    for path in SRC.rglob("*.py"):
        text = io.open(path, encoding="utf-8").read()
        for name in forbidden:
            if name in text:
                hits.append(f"{path.relative_to(SRC)}:{name}")
    assert not hits, f"constante global de schema encontrada: {hits}"


def test_constants_are_independent_objects():
    """Coincidir no valor 1 hoje não pode significar compartilhar a mesma
    fonte: cada contrato tem que poder ir para 2 sozinho."""
    from mastertool_bridge.automation import config_models
    from mastertool_bridge.plcopen import canonical_model, structure_map

    assert config_models.SCHEMA_VERSION == canonical_model.SCHEMA_VERSION == 1
    assert structure_map.STRUCTURE_MAP_SCHEMA_VERSION == 1
    # Nomes distintos em módulos distintos — nenhum reexporta o do outro.
    assert "SCHEMA_VERSION" not in dir(structure_map)


# --- a fronteira entre as famílias -------------------------------------------

def test_canonical_model_rejects_the_string_family_version():
    """O modelo canônico é da família inteira. Receber `"1.0"` significa que
    alguém entregou artefato de outra família — tem que falhar, não adaptar."""
    from mastertool_bridge.plcopen.canonical_model import (
        MODEL_KIND, CanonicalModelError, GraphicPOU)

    payload = {"model_kind": MODEL_KIND, "schema_version": "1.0",
               "identity": {"name": "X", "pou_type": "functionBlock"}}
    with pytest.raises(CanonicalModelError, match="schema_version"):
        GraphicPOU.from_dict(payload)


def test_index_api_accepts_only_integer_versions():
    from mastertool_bridge.api import SUPPORTED_INDEX_SCHEMA_VERSIONS

    assert SUPPORTED_INDEX_SCHEMA_VERSIONS == {1}
    assert all(isinstance(v, int) for v in SUPPORTED_INDEX_SCHEMA_VERSIONS)
    assert "1.0" not in SUPPORTED_INDEX_SCHEMA_VERSIONS


def test_json_schemas_still_declare_the_string_family():
    """Os cinco JSON Schemas formalizam `string` para os artefatos de
    export/probe. Trocar para `integer` invalidaria artefatos arquivados
    cobertos por checksum, que não podem ser reescritos."""
    checked = 0
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        schema = json.loads(io.open(path, encoding="utf-8").read())
        prop = (schema.get("properties") or {}).get("schema_version")
        if prop is None:
            continue
        assert prop.get("type") == "string", (
            f"{path.name} mudou o tipo de schema_version — isso quebra "
            "artefatos arquivados da família de export/probe")
        checked += 1
    assert checked == 5, f"esperados 5 schemas com schema_version, vistos {checked}"


def test_ironpython_probe_family_keeps_its_own_versions():
    """A família de probe/export permanece string, e o `"2.0"` de
    `02_dump_api_surface.py` permanece `"2.0"` — rebaixá-lo para `1` apagaria
    uma versão real de contrato."""
    probes_root = REPO_ROOT / "scripts" / "mastertool"
    api_surface = probes_root / "02_dump_api_surface.py"
    text = io.open(api_surface, encoding="utf-8").read()
    assert '"schema_version": "2.0"' in text, (
        "a versão 2.0 do dump de API foi alterada — é contrato próprio")

    scanner = probes_root / "common" / "read_only_project_scanner.py"
    assert '"schema_version": "1.0"' in io.open(scanner, encoding="utf-8").read()

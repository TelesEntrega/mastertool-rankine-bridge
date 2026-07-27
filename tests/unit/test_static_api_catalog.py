import json

from mastertool_bridge.static_api.catalog import (annotate_catalog,
                                                   build_all_artifacts,
                                                   build_compilation_candidates,
                                                   build_creation_candidates,
                                                   build_navigation_candidates,
                                                   build_text_access_candidates,
                                                   load_raw_catalog,
                                                   render_reachable_types_markdown)

SYNTHETIC_RAW = {
    "generated_by": "test-fixture",
    "types": [
        {
            "full_name": "Fake.IScriptTreeObject",
            "assembly": "Fake", "assembly_version": "1.0.0.0",
            "is_public": True, "is_interface": True, "is_enum": False,
            "is_generic": False, "base_type": None, "interfaces": [],
            "properties": [
                {"name": "is_root", "type": "System.Boolean", "can_read": True, "can_write": False},
                {"name": "parent", "type": "System.Object", "can_read": True, "can_write": False},
            ],
            "methods": [
                {"name": "get_children", "return_type": "System.Collections.IList",
                 "is_static": False, "is_public": True,
                 "parameters": [{"name": "recursive", "type": "System.Boolean", "optional": False}]},
                {"name": "find", "return_type": "System.Collections.IList",
                 "is_static": False, "is_public": True, "parameters": []},
            ],
            "fields": [],
        },
        {
            "full_name": "Fake.IScriptTextDocument",
            "assembly": "Fake", "assembly_version": "1.0.0.0",
            "is_public": True, "is_interface": True, "is_enum": False,
            "is_generic": False, "base_type": None, "interfaces": [],
            "properties": [
                {"name": "text", "type": "System.String", "can_read": True, "can_write": False},
            ],
            "methods": [
                {"name": "append", "return_type": "System.Void", "is_static": False,
                 "is_public": True, "parameters": [{"name": "text", "type": "System.String", "optional": False}]},
            ],
            "fields": [],
        },
        {
            "full_name": "Fake.ScriptApplication",
            "assembly": "Fake", "assembly_version": "1.0.0.0",
            "is_public": True, "is_interface": False, "is_enum": False,
            "is_generic": False, "base_type": "System.Object", "interfaces": [],
            "properties": [],
            "methods": [
                {"name": "build", "return_type": "System.Void", "is_static": False,
                 "is_public": True, "parameters": []},
                {"name": "generate_code", "return_type": "System.Void", "is_static": False,
                 "is_public": True, "parameters": []},
            ],
            "fields": [],
        },
    ],
    "not_found": [],
}


def test_annotate_catalog_classifies_every_member():
    catalog = annotate_catalog(SYNTHETIC_RAW)
    tree = next(t for t in catalog if t["full_name"] == "Fake.IScriptTreeObject")
    props = {p["name"]: p for p in tree["properties"]}
    methods = {m["name"]: m for m in tree["methods"]}
    assert props["is_root"]["classification"] == "read_candidate"
    assert props["parent"]["classification"] == "unknown"
    assert methods["get_children"]["classification"] == "read_candidate"
    assert methods["find"]["classification"] == "read_candidate"


def test_navigation_candidates_include_expected_members():
    catalog = annotate_catalog(SYNTHETIC_RAW)
    nav = build_navigation_candidates(catalog)
    names = {(n["declaring_type"], n["name"]) for n in nav}
    assert ("Fake.IScriptTreeObject", "get_children") in names
    assert ("Fake.IScriptTreeObject", "find") in names
    assert ("Fake.IScriptTreeObject", "parent") in names
    assert ("Fake.IScriptTreeObject", "is_root") in names
    # membros de outro tipo, sem relacao com navegacao, nao devem aparecer
    assert not any(n["declaring_type"] == "Fake.IScriptTextDocument" for n in nav
                  if n["name"] not in ("text",))


def test_text_access_candidates_include_text_members():
    catalog = annotate_catalog(SYNTHETIC_RAW)
    text_candidates = build_text_access_candidates(catalog)
    names = {(n["declaring_type"], n["name"]) for n in text_candidates}
    assert ("Fake.IScriptTextDocument", "text") in names
    assert ("Fake.IScriptTextDocument", "append") in names


def test_compilation_candidates_include_build_members():
    catalog = annotate_catalog(SYNTHETIC_RAW)
    compile_candidates = build_compilation_candidates(catalog)
    names = {(n["declaring_type"], n["name"]) for n in compile_candidates}
    assert ("Fake.ScriptApplication", "build") in names
    assert ("Fake.ScriptApplication", "generate_code") in names


def test_creation_candidates_include_append():
    catalog = annotate_catalog(SYNTHETIC_RAW)
    creation = build_creation_candidates(catalog)
    names = {(n["declaring_type"], n["name"]) for n in creation}
    assert ("Fake.IScriptTextDocument", "append") in names


def test_build_all_artifacts_writes_expected_files(tmp_path):
    raw_path = tmp_path / "raw-catalog.json"
    raw_path.write_text(json.dumps(SYNTHETIC_RAW), encoding="utf-8")
    output_dir = tmp_path / "out"

    paths = build_all_artifacts(raw_path, output_dir)

    expected = {
        "reachable-types.json", "reachable-types.md",
        "project-navigation-candidates.json", "text-access-candidates.json",
        "creation-candidates.json", "compilation-candidates.json",
        "safety-classification.md",
    }
    assert set(paths.keys()) == expected
    for path in paths.values():
        assert path.is_file()

    reachable = json.loads((output_dir / "reachable-types.json").read_text(encoding="utf-8"))
    assert len(reachable["types"]) == 3


def test_render_reachable_types_handles_null_interface_name():
    # GetInterfaces() do PowerShell as vezes retorna FullName None (tipo
    # generico sem argumentos resolvidos) — o renderer nao pode quebrar.
    raw = {
        "types": [{
            "full_name": "Fake.Weird",
            "assembly": "Fake", "assembly_version": "1.0.0.0",
            "is_public": True, "is_interface": False, "is_enum": False,
            "is_generic": True, "base_type": "System.Object",
            "interfaces": [None, "System.IDisposable"],
            "properties": [], "methods": [], "fields": [],
        }],
        "not_found": [],
    }
    catalog = annotate_catalog(raw)
    md = render_reachable_types_markdown(catalog)
    assert "System.IDisposable" in md
    assert "generico sem FullName" in md


def test_load_raw_catalog_handles_bom(tmp_path):
    # o PowerShell (Out-File -Encoding utf8) grava BOM — o loader precisa
    # aceitar isso sem lancar excecao.
    raw_path = tmp_path / "raw-catalog.json"
    raw_path.write_bytes(b"\xef\xbb\xbf" + json.dumps(SYNTHETIC_RAW).encode("utf-8"))
    data = load_raw_catalog(raw_path)
    assert len(data["types"]) == 3

"""Testes de integracao de mastertool_bridge.indexer.query.run_ask.

Usa fixtures reais (arquivos JSON em tmp_path via write_json), reproduzindo
o padrao de test_load_query_bundle_valid_files_builds_symbol_index em
tests/indexer/test_query.py.
"""

from __future__ import annotations

import json

import pytest

from mastertool_bridge.exceptions import ValidationError
from mastertool_bridge.indexer import query as query_mod
from mastertool_bridge.indexer.models import PouSymbol, SourceLocation, VariableDeclaration
from mastertool_bridge.indexer.query import find_writes, load_query_bundle, run_ask
from mastertool_bridge.utils.json_io import write_json


def _loc(file: str = "f.st", line: int = 1, col: int = 1) -> SourceLocation:
    return SourceLocation(file=file, line=line, column=col)


def _var(name: str, declared_type: str, scope: str, location=None) -> VariableDeclaration:
    return VariableDeclaration(name=name, declared_type=declared_type, scope=scope, location=location)


def _ref_entry(node_id, name, classification, resolution_state="resolved", resolved_symbol=None, line=1, col=1, file="f.st", **extra):
    entry = {
        "node_id": node_id,
        "file": file,
        "name": name,
        "context": "assignment_target" if classification == "write" else "assignment_value",
        "location": {"file": file, "line": line, "column": col},
        "resolution_state": resolution_state,
        "resolved_symbol": resolved_symbol,
        "candidates": [],
        "classification": classification,
        "rule_applied": "test_rule",
    }
    entry.update(extra)
    return entry


def _write_real_index(tmp_path, prg: PouSymbol, references: list[dict]) -> None:
    write_json(tmp_path / "symbols.json", [prg.to_dict()])
    write_json(tmp_path / "resolved-calls.json", [])
    write_json(tmp_path / "callers.json", {})
    write_json(tmp_path / "resolved-references.json", references)
    write_json(tmp_path / "read-write-index.json", {})


def test_run_ask_matched_writes_identical_to_direct_find_writes(tmp_path) -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(line=5))],
    )
    refs = [
        _ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=10),
        _ref_entry("application/prg/0#stmt1", "Estado_OP", "read", line=11),
    ]
    _write_real_index(tmp_path, prg, refs)

    envelope = run_ask(tmp_path, "onde Estado_OP é escrito?")

    assert "result" in envelope
    assert envelope["intent"]["status"] == "matched"
    assert envelope["intent"]["operation"] == "find_writes"

    bundle = load_query_bundle(tmp_path)
    direct = find_writes(bundle, "Estado_OP")

    assert envelope["result"] == direct.to_dict()


def test_run_ask_ambiguous_has_no_result_key_and_does_not_call_find(tmp_path, monkeypatch) -> None:
    calls = []
    for key, fn in list(query_mod._DISPATCH.items()):
        def spy(bundle, q, _fn=fn, _key=key):
            calls.append(_key)
            return _fn(bundle, q)
        monkeypatch.setitem(query_mod._DISPATCH, key, spy)

    # index_dir nao existe -- se load_query_bundle fosse chamado, levantaria
    # ValidationError. Confirmamos que NAO levanta (prova de que
    # load_query_bundle nunca e chamado quando status != "matched").
    nonexistent = tmp_path / "does_not_exist"

    envelope = run_ask(nonexistent, "onde Estado_OP é usado?")

    assert envelope["intent"]["status"] == "ambiguous"
    assert "result" not in envelope
    assert calls == []


def test_run_ask_unsupported_has_no_result_key_and_does_not_raise(tmp_path) -> None:
    nonexistent = tmp_path / "does_not_exist"

    envelope = run_ask(nonexistent, "explique Estado_OP")

    assert envelope["intent"]["status"] == "unsupported"
    assert "result" not in envelope


def test_run_ask_invalid_has_no_result_key_and_does_not_raise(tmp_path) -> None:
    nonexistent = tmp_path / "does_not_exist"

    envelope = run_ask(nonexistent, "")

    assert envelope["intent"]["status"] == "invalid"
    assert "result" not in envelope


def test_run_ask_matched_but_bad_index_dir_raises_validation_error(tmp_path) -> None:
    nonexistent = tmp_path / "does_not_exist"

    with pytest.raises(ValidationError):
        run_ask(nonexistent, "find symbol Estado_OP")


def test_run_ask_stable_json_output_across_runs(tmp_path) -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(line=5))],
    )
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=10)]
    _write_real_index(tmp_path, prg, refs)

    e1 = run_ask(tmp_path, "onde Estado_OP é escrito?")
    e2 = run_ask(tmp_path, "onde Estado_OP é escrito?")

    json1 = json.dumps(e1, indent=2, ensure_ascii=False, sort_keys=True)
    json2 = json.dumps(e2, indent=2, ensure_ascii=False, sort_keys=True)
    assert json1 == json2


def test_run_ask_find_symbol_matched(tmp_path) -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(line=5))],
    )
    _write_real_index(tmp_path, prg, [])

    envelope = run_ask(tmp_path, "find symbol Estado_OP")

    assert envelope["intent"]["operation"] == "find_symbol"
    assert envelope["result"]["status"] == "resolved"
    assert envelope["result"]["count"] == 1

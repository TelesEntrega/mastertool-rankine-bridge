"""Testes da API pública `mastertool_bridge.api` / `mastertool_bridge.__init__`.

Fixtures sintéticas via `write_json`, mesmo padrão de
`tests/indexer/test_query_ask_integration.py`. O FLUXO de uso da API pública
(abrir índice, rodar as 5 consultas + ask, ler evidências/status/summary)
nunca precisa importar `mastertool_bridge.indexer.*` -- esse import só
acontece aqui para MONTAR fixtures e para comparar lado a lado com a
implementação interna (equivalência estrutural).
"""

from __future__ import annotations

import json

import pytest

from mastertool_bridge import (
    InvalidIndexError,
    ProjectIndex,
    ProjectIndexError,
    QueryAnswer,
    QueryEvidence,
    QueryIntent,
    QueryResult,
    UnsupportedSchemaError,
)
from mastertool_bridge.indexer.models import PouSymbol, SourceLocation, VariableDeclaration
from mastertool_bridge.indexer.query import QueryIndexBundle
from mastertool_bridge.indexer.query import find_calls as _internal_find_calls
from mastertool_bridge.indexer.query import find_callers as _internal_find_callers
from mastertool_bridge.indexer.query import find_reads as _internal_find_reads
from mastertool_bridge.indexer.query import find_symbol as _internal_find_symbol
from mastertool_bridge.indexer.query import find_writes as _internal_find_writes
from mastertool_bridge.indexer.query_response import answer_query as _internal_answer_query
from mastertool_bridge.indexer.symbol_resolver import ProjectSymbolIndex
from mastertool_bridge.utils.json_io import write_json


# ---------------------------------------------------------------------------
# helpers de fixture (mesmo padrão de tests/indexer/*)
# ---------------------------------------------------------------------------


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


def _call_entry(node_id, callee, resolution_state="resolved", resolved_symbol=None, line=1, col=1, file="f.st"):
    return {
        "node_id": node_id,
        "file": file,
        "callee": callee,
        "arguments": [],
        "location": {"file": file, "line": line, "column": col},
        "resolution_state": resolution_state,
        "resolved_symbol": resolved_symbol,
        "candidates": [],
        "rule_applied": "test_rule",
    }


def _caller_site(node_id, callee, line=1, col=1, file="f.st"):
    return {
        "node_id": node_id,
        "file": file,
        "callee": callee,
        "location": {"file": file, "line": line, "column": col},
        "rule_applied": "fb_instance",
    }


def _write_index(index_dir, symbols=None, resolved_calls=None, callers=None, resolved_references=None, read_write_index=None):
    write_json(index_dir / "symbols.json", [s.to_dict() for s in (symbols or [])])
    write_json(index_dir / "resolved-calls.json", resolved_calls or [])
    write_json(index_dir / "callers.json", callers or {})
    write_json(index_dir / "resolved-references.json", resolved_references or [])
    write_json(index_dir / "read-write-index.json", read_write_index or {})


def _internal_bundle(symbols, resolved_calls=None, callers=None, resolved_references=None, read_write_index=None):
    from pathlib import Path

    return QueryIndexBundle(
        index_dir=Path("unused"),
        symbols=[s.to_dict() for s in symbols],
        resolved_calls=resolved_calls or [],
        callers=callers or {},
        resolved_references=resolved_references or [],
        read_write_index=read_write_index or {},
        symbol_index=ProjectSymbolIndex(symbols),
        pou_symbols=symbols,
    )


def _main_prg():
    return PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(line=5))],
    )


# ---------------------------------------------------------------------------
# abertura de índice
# ---------------------------------------------------------------------------


def test_open_valid_index(tmp_path) -> None:
    _write_index(tmp_path, symbols=[_main_prg()])

    index = ProjectIndex.open(tmp_path)

    assert index.metadata["symbol_count"] == 1


def test_open_nonexistent_dir_raises_invalid_index_error(tmp_path) -> None:
    with pytest.raises(InvalidIndexError):
        ProjectIndex.open(tmp_path / "does_not_exist")


def test_open_nonexistent_dir_does_not_raise_raw_validation_error(tmp_path) -> None:
    from mastertool_bridge.exceptions import ValidationError

    try:
        ProjectIndex.open(tmp_path / "does_not_exist")
    except ValidationError:
        pytest.fail("ProjectIndex.open deve envolver ValidationError em InvalidIndexError")
    except InvalidIndexError:
        pass


def test_open_missing_required_file_raises_invalid_index_error(tmp_path) -> None:
    write_json(tmp_path / "symbols.json", [])
    # Demais 4 arquivos obrigatórios ausentes.

    with pytest.raises(InvalidIndexError):
        ProjectIndex.open(tmp_path)


def test_open_corrupted_json_raises_invalid_index_error(tmp_path) -> None:
    write_json(tmp_path / "symbols.json", [])
    write_json(tmp_path / "resolved-calls.json", [])
    write_json(tmp_path / "callers.json", {})
    write_json(tmp_path / "resolved-references.json", [])
    (tmp_path / "read-write-index.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(InvalidIndexError):
        ProjectIndex.open(tmp_path)


def test_invalid_index_error_is_project_index_error() -> None:
    assert issubclass(InvalidIndexError, ProjectIndexError)


def test_unsupported_schema_error_is_project_index_error() -> None:
    assert issubclass(UnsupportedSchemaError, ProjectIndexError)


# ---------------------------------------------------------------------------
# bundle carregado uma única vez
# ---------------------------------------------------------------------------


def test_open_calls_load_query_bundle_exactly_once_and_queries_reuse_it(tmp_path, monkeypatch) -> None:
    _write_index(
        tmp_path,
        symbols=[_main_prg()],
        resolved_references=[_ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=10)],
    )

    import mastertool_bridge.api as api_mod

    calls = []
    original = api_mod.load_query_bundle

    def spy(index_dir):
        calls.append(index_dir)
        return original(index_dir)

    monkeypatch.setattr(api_mod, "load_query_bundle", spy)

    index = ProjectIndex.open(tmp_path)
    assert len(calls) == 1

    index.find_symbol("Estado_OP")
    index.find_reads("Estado_OP")
    index.find_writes("Estado_OP")
    index.find_calls("MainPrg")
    index.find_callers("MainPrg")
    index.ask("find symbol Estado_OP")

    assert len(calls) == 1  # nenhuma releitura adicional


# ---------------------------------------------------------------------------
# equivalência com as funções internas
# ---------------------------------------------------------------------------


def test_find_symbol_equivalent_to_internal(tmp_path) -> None:
    prg = _main_prg()
    _write_index(tmp_path, symbols=[prg])
    internal_bundle = _internal_bundle([prg])

    index = ProjectIndex.open(tmp_path)

    assert index.find_symbol("Estado_OP").to_dict() == _internal_find_symbol(internal_bundle, "Estado_OP").to_dict()


def test_find_reads_equivalent_to_internal(tmp_path) -> None:
    prg = _main_prg()
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "read", line=11)]
    _write_index(tmp_path, symbols=[prg], resolved_references=refs)
    internal_bundle = _internal_bundle([prg], resolved_references=refs)

    index = ProjectIndex.open(tmp_path)

    assert index.find_reads("Estado_OP").to_dict() == _internal_find_reads(internal_bundle, "Estado_OP").to_dict()


def test_find_writes_equivalent_to_internal(tmp_path) -> None:
    prg = _main_prg()
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=10)]
    _write_index(tmp_path, symbols=[prg], resolved_references=refs)
    internal_bundle = _internal_bundle([prg], resolved_references=refs)

    index = ProjectIndex.open(tmp_path)

    assert index.find_writes("Estado_OP").to_dict() == _internal_find_writes(internal_bundle, "Estado_OP").to_dict()


def test_find_calls_equivalent_to_internal(tmp_path) -> None:
    prg = PouSymbol(node_id="application/6/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    calls = [
        _call_entry("application/6/0#stmt0", "SpecialVariablesPrg", resolved_symbol="application/prg/1", line=1),
        _call_entry("application/6/0#stmt1", "StartPrg", resolved_symbol="application/prg/2", line=2),
    ]
    _write_index(tmp_path, symbols=[prg], resolved_calls=calls)
    internal_bundle = _internal_bundle([prg], resolved_calls=calls)

    index = ProjectIndex.open(tmp_path)

    assert index.find_calls("MainPrg").to_dict() == _internal_find_calls(internal_bundle, "MainPrg").to_dict()


def test_find_callers_equivalent_to_internal(tmp_path) -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="SpecialVariablesPrg", file="f.st")
    callers = {
        "application/prg/0": [_caller_site("application/prg/1#stmt0", "SpecialVariablesPrg", line=1)],
    }
    _write_index(tmp_path, symbols=[prg], callers=callers)
    internal_bundle = _internal_bundle([prg], callers=callers)

    index = ProjectIndex.open(tmp_path)

    assert index.find_callers("SpecialVariablesPrg").to_dict() == _internal_find_callers(internal_bundle, "SpecialVariablesPrg").to_dict()


def test_ask_equivalent_to_internal_answer_query(tmp_path) -> None:
    prg = _main_prg()
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=10)]
    _write_index(tmp_path, symbols=[prg], resolved_references=refs)
    internal_bundle = _internal_bundle([prg], resolved_references=refs)

    index = ProjectIndex.open(tmp_path)
    question = "onde Estado_OP é escrito?"

    public_dict = index.ask(question).to_dict()
    internal_dict = _internal_answer_query(question, internal_bundle).to_dict()

    assert public_dict == internal_dict


def test_ask_intent_is_typed_query_intent_object(tmp_path) -> None:
    _write_index(tmp_path, symbols=[_main_prg()])
    index = ProjectIndex.open(tmp_path)

    answer = index.ask("find symbol Estado_OP")

    assert isinstance(answer.intent, QueryIntent)
    assert answer.intent.status == "matched"
    assert answer.intent.operation == "find_symbol"


# ---------------------------------------------------------------------------
# round-trip QueryEvidence.from_dict(d).to_dict() == d, para os 5 comandos
# ---------------------------------------------------------------------------


def test_evidence_round_trip_find_symbol(tmp_path) -> None:
    prg = _main_prg()
    _write_index(tmp_path, symbols=[prg])
    index = ProjectIndex.open(tmp_path)
    internal = _internal_find_symbol(_internal_bundle([prg]), "Estado_OP")

    for d in internal.evidence:
        assert QueryEvidence.from_dict(d).to_dict() == d


def test_evidence_round_trip_find_reads(tmp_path) -> None:
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "read", line=11)]
    internal = _internal_find_reads(_internal_bundle([], resolved_references=refs), "Estado_OP")

    for d in internal.evidence:
        assert QueryEvidence.from_dict(d).to_dict() == d


def test_evidence_round_trip_find_writes(tmp_path) -> None:
    refs = [
        _ref_entry(
            "application/prg/0#stmt0",
            "VarMotores.MT01.RetornoDisjuntor",
            "write",
            resolution_state="partially_resolved",
            resolved_symbol="application/gvl/0",
            resolved_prefix="VarMotores.MT01",
            unresolved_suffix="RetornoDisjuntor",
            reason="member metadata unavailable",
        )
    ]
    internal = _internal_find_writes(_internal_bundle([], resolved_references=refs), "VarMotores.MT01.RetornoDisjuntor")

    for d in internal.evidence:
        assert QueryEvidence.from_dict(d).to_dict() == d


def test_evidence_round_trip_find_calls(tmp_path) -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    calls = [_call_entry("application/prg/0#stmt0", "SysTimeCore.SysTimeGetUs", resolution_state="unresolved")]
    internal = _internal_find_calls(_internal_bundle([prg], resolved_calls=calls), "MainPrg")

    for d in internal.evidence:
        assert QueryEvidence.from_dict(d).to_dict() == d


def test_evidence_round_trip_find_callers(tmp_path) -> None:
    prg1 = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="DupPrg", file="f.st")
    prg2 = PouSymbol(node_id="application/prg/1", pou_kind="PROGRAM", name="DupPrg", file="g.st")
    callers = {
        "application/prg/0": [_caller_site("application/prg/9#stmt0", "DupPrg", line=1)],
        "application/prg/1": [_caller_site("application/prg/8#stmt0", "DupPrg", line=2)],
    }
    internal = _internal_find_callers(_internal_bundle([prg1, prg2], callers=callers), "DupPrg")

    for d in internal.evidence:
        assert QueryEvidence.from_dict(d).to_dict() == d


def test_evidence_round_trip_ask(tmp_path) -> None:
    prg = _main_prg()
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=10)]
    internal_bundle = _internal_bundle([prg], resolved_references=refs)
    internal_answer = _internal_answer_query("onde Estado_OP é escrito?", internal_bundle)

    for d in internal_answer.evidence:
        assert QueryEvidence.from_dict(d).to_dict() == d


# ---------------------------------------------------------------------------
# serialização JSON / determinismo
# ---------------------------------------------------------------------------


def test_query_result_to_dict_is_json_serializable_and_deterministic(tmp_path) -> None:
    _write_index(tmp_path, symbols=[_main_prg()])
    index = ProjectIndex.open(tmp_path)

    r1 = index.find_symbol("Estado_OP").to_dict()
    r2 = index.find_symbol("Estado_OP").to_dict()

    j1 = json.dumps(r1, indent=2, ensure_ascii=False, sort_keys=True)
    j2 = json.dumps(r2, indent=2, ensure_ascii=False, sort_keys=True)
    assert j1 == j2


def test_query_answer_to_dict_is_json_serializable_and_deterministic(tmp_path) -> None:
    prg = _main_prg()
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=10)]
    _write_index(tmp_path, symbols=[prg], resolved_references=refs)
    index = ProjectIndex.open(tmp_path)

    a1 = index.ask("onde Estado_OP é escrito?").to_dict()
    a2 = index.ask("onde Estado_OP é escrito?").to_dict()

    j1 = json.dumps(a1, indent=2, ensure_ascii=False, sort_keys=True)
    j2 = json.dumps(a2, indent=2, ensure_ascii=False, sort_keys=True)
    assert j1 == j2


# ---------------------------------------------------------------------------
# ausência de vazamento de tipos internos / uso completo da API pública
# ---------------------------------------------------------------------------


def test_full_public_flow_without_importing_indexer_internals(tmp_path) -> None:
    """Fluxo completo (abrir, 5 consultas + ask, ler evidencias/status/
    summary) usando SOMENTE simbolos publicos de `mastertool_bridge`."""
    prg = _main_prg()
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=10)]
    _write_index(tmp_path, symbols=[prg], resolved_references=refs)

    index = ProjectIndex.open(tmp_path)

    r_symbol = index.find_symbol("Estado_OP")
    r_reads = index.find_reads("Estado_OP")
    r_writes = index.find_writes("Estado_OP")
    r_calls = index.find_calls("MainPrg")
    r_callers = index.find_callers("MainPrg")
    answer = index.ask("onde Estado_OP é escrito?")

    for result in (r_symbol, r_reads, r_writes, r_calls, r_callers):
        assert isinstance(result, QueryResult)
        assert result.status
        for ev in result.evidence:
            assert isinstance(ev, QueryEvidence)

    assert isinstance(answer, QueryAnswer)
    assert answer.summary
    assert isinstance(answer.intent, QueryIntent)

    metadata = index.metadata
    assert metadata["symbol_count"] == 1


# ---------------------------------------------------------------------------
# isolamento entre instâncias
# ---------------------------------------------------------------------------


def test_two_instances_do_not_leak_state(tmp_path) -> None:
    dir_a = tmp_path / "index_a"
    dir_b = tmp_path / "index_b"
    dir_a.mkdir()
    dir_b.mkdir()

    prg_a = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="OnlyInA", file="a.st")
    prg_b = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="OnlyInB", file="b.st")

    _write_index(dir_a, symbols=[prg_a])
    _write_index(dir_b, symbols=[prg_b])

    index_a = ProjectIndex.open(dir_a)
    index_b = ProjectIndex.open(dir_b)

    assert index_a.find_symbol("OnlyInA").status == "resolved"
    assert index_a.find_symbol("OnlyInB").status == "unresolved"

    assert index_b.find_symbol("OnlyInB").status == "resolved"
    assert index_b.find_symbol("OnlyInA").status == "unresolved"

    assert index_a.metadata["index_dir"] != index_b.metadata["index_dir"]


# ---------------------------------------------------------------------------
# estabilidade de contrato (shape) -- regressao
# ---------------------------------------------------------------------------


def test_query_result_minimal_shape() -> None:
    result = QueryResult(command="symbol", query="X", status="unresolved", evidence=[])
    d = result.to_dict()

    assert set(d.keys()) == {"command", "query", "status", "count", "evidence"}
    assert d["count"] == 0
    assert d["evidence"] == []


def test_query_result_with_note_shape() -> None:
    result = QueryResult(command="calls", query="X", status="resolved", evidence=[], note="nota")
    d = result.to_dict()

    assert set(d.keys()) == {"command", "query", "status", "count", "evidence", "note"}


def test_query_answer_minimal_shape() -> None:
    intent = QueryIntent(status="invalid", reason="empty_input")
    answer = QueryAnswer(
        schema_version=1,
        question="",
        status="invalid",
        intent=intent,
        summary="vazio",
        evidence=[],
        limitations=[],
    )
    d = answer.to_dict()

    assert set(d.keys()) == {
        "schema_version",
        "question",
        "status",
        "intent",
        "summary",
        "evidence",
        "limitations",
    }
    assert d["intent"] == intent.to_dict()


def test_query_evidence_minimal_shape() -> None:
    ev = QueryEvidence(
        node_id=None,
        file=None,
        line=None,
        column=None,
        resolution_state=None,
        resolved_symbol=None,
        confidence=None,
    )
    d = ev.to_dict()

    assert set(d.keys()) == {
        "node_id",
        "file",
        "line",
        "column",
        "resolution_state",
        "resolved_symbol",
        "confidence",
    }


def test_query_intent_reexported_directly_is_stable() -> None:
    intent = QueryIntent(status="matched", operation="find_symbol", target="X", matched_pattern="p", confidence="exact")
    d = intent.to_dict()

    assert d["status"] == "matched"
    assert d["operation"] == "find_symbol"
    assert d["target"] == "X"


def test_public_imports_resolve() -> None:
    # Já exercitado pelos imports no topo do arquivo -- este teste documenta
    # explicitamente o contrato de importação exigido.
    import mastertool_bridge as mb

    for name in (
        "ProjectIndex",
        "QueryResult",
        "QueryAnswer",
        "QueryIntent",
        "QueryEvidence",
        "ProjectIndexError",
        "InvalidIndexError",
        "UnsupportedSchemaError",
    ):
        assert hasattr(mb, name)

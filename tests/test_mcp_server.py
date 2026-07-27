"""Testes do servidor MCP (`mastertool_bridge.mcp_server`).

Chamam as funções `_*_impl` (e as `*_impl` publicas equivalentes)
DIRETAMENTE -- nunca sobem o transporte MCP de verdade. Mesmo padrão de
fixture sintetica de `tests/test_api.py` (via `write_json`).
"""

from __future__ import annotations

import pytest

from mastertool_bridge import ProjectIndex
from mastertool_bridge.indexer.models import PouSymbol, SourceLocation, VariableDeclaration
from mastertool_bridge.utils.json_io import write_json

from mastertool_bridge.mcp_server import (
    _INDEX_CACHE,
    ask_project_impl,
    find_calls_impl,
    find_callers_impl,
    find_reads_impl,
    find_symbol_impl,
    find_writes_impl,
    get_index_metadata_impl,
    open_project_index_impl,
)


@pytest.fixture(autouse=True)
def _clear_index_cache():
    """Cada teste comeca com o cache de indices vazio, e nao vaza para o
    proximo (o cache do modulo e global por design)."""
    _INDEX_CACHE.clear()
    yield
    _INDEX_CACHE.clear()


# ---------------------------------------------------------------------------
# helpers de fixture (mesmo padrao de tests/test_api.py)
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


def _main_prg():
    return PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(line=5))],
    )


# ---------------------------------------------------------------------------
# open_project_index / get_index_metadata
# ---------------------------------------------------------------------------


def test_open_project_index_valid_returns_metadata(tmp_path) -> None:
    _write_index(tmp_path, symbols=[_main_prg()])

    result = open_project_index_impl(str(tmp_path))

    assert result["symbol_count"] == 1
    assert "error" not in result


def test_get_index_metadata_valid_returns_metadata(tmp_path) -> None:
    _write_index(tmp_path, symbols=[_main_prg()])

    result = get_index_metadata_impl(str(tmp_path))

    assert result["symbol_count"] == 1
    assert "error" not in result


def test_open_project_index_and_get_index_metadata_share_implementation(tmp_path) -> None:
    _write_index(tmp_path, symbols=[_main_prg()])

    a = open_project_index_impl(str(tmp_path))
    b = get_index_metadata_impl(str(tmp_path))

    assert a == b


def test_open_project_index_nonexistent_dir_returns_structured_error(tmp_path) -> None:
    result = open_project_index_impl(str(tmp_path / "does_not_exist"))

    assert result["error"] == "invalid_index"
    assert "message" in result


# ---------------------------------------------------------------------------
# equivalencia com ProjectIndex direto, para cada find_* + ask_project
# ---------------------------------------------------------------------------


def test_find_symbol_impl_equivalent_to_project_index(tmp_path) -> None:
    prg = _main_prg()
    _write_index(tmp_path, symbols=[prg])
    index = ProjectIndex.open(tmp_path)

    result = find_symbol_impl(str(tmp_path), "Estado_OP")

    assert result == index.find_symbol("Estado_OP").to_dict()


def test_find_reads_impl_equivalent_to_project_index(tmp_path) -> None:
    prg = _main_prg()
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "read", line=11)]
    _write_index(tmp_path, symbols=[prg], resolved_references=refs)
    index = ProjectIndex.open(tmp_path)

    result = find_reads_impl(str(tmp_path), "Estado_OP")

    assert result == index.find_reads("Estado_OP").to_dict()


def test_find_writes_impl_equivalent_to_project_index(tmp_path) -> None:
    prg = _main_prg()
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=10)]
    _write_index(tmp_path, symbols=[prg], resolved_references=refs)
    index = ProjectIndex.open(tmp_path)

    result = find_writes_impl(str(tmp_path), "Estado_OP")

    assert result == index.find_writes("Estado_OP").to_dict()


def test_find_calls_impl_equivalent_to_project_index(tmp_path) -> None:
    prg = PouSymbol(node_id="application/6/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    calls = [
        _call_entry("application/6/0#stmt0", "SpecialVariablesPrg", resolved_symbol="application/prg/1", line=1),
        _call_entry("application/6/0#stmt1", "StartPrg", resolved_symbol="application/prg/2", line=2),
    ]
    _write_index(tmp_path, symbols=[prg], resolved_calls=calls)
    index = ProjectIndex.open(tmp_path)

    result = find_calls_impl(str(tmp_path), "MainPrg")

    assert result == index.find_calls("MainPrg").to_dict()


def test_find_callers_impl_equivalent_to_project_index(tmp_path) -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="SpecialVariablesPrg", file="f.st")
    callers = {
        "application/prg/0": [_caller_site("application/prg/1#stmt0", "SpecialVariablesPrg", line=1)],
    }
    _write_index(tmp_path, symbols=[prg], callers=callers)
    index = ProjectIndex.open(tmp_path)

    result = find_callers_impl(str(tmp_path), "SpecialVariablesPrg")

    assert result == index.find_callers("SpecialVariablesPrg").to_dict()


def test_ask_project_impl_equivalent_to_project_index(tmp_path) -> None:
    prg = _main_prg()
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=10)]
    _write_index(tmp_path, symbols=[prg], resolved_references=refs)
    index = ProjectIndex.open(tmp_path)
    question = "onde Estado_OP é escrito?"

    result = ask_project_impl(str(tmp_path), question)

    assert result == index.ask(question).to_dict()


# ---------------------------------------------------------------------------
# erro estruturado -- index_dir invalido
# ---------------------------------------------------------------------------


def test_find_symbol_impl_invalid_index_dir_returns_structured_error(tmp_path) -> None:
    result = find_symbol_impl(str(tmp_path / "does_not_exist"), "Estado_OP")

    assert result["error"] == "invalid_index"
    assert "message" in result


def test_find_symbol_impl_corrupted_index_returns_structured_error(tmp_path) -> None:
    write_json(tmp_path / "symbols.json", [])
    write_json(tmp_path / "resolved-calls.json", [])
    write_json(tmp_path / "callers.json", {})
    write_json(tmp_path / "resolved-references.json", [])
    (tmp_path / "read-write-index.json").write_text("{not valid json", encoding="utf-8")

    result = find_symbol_impl(str(tmp_path), "Estado_OP")

    assert result["error"] == "invalid_index"


# ---------------------------------------------------------------------------
# validacao de argumentos -- name/question vazios/ausentes, sem excecao crua
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_index_dir", ["", "   ", None, 123])
def test_find_symbol_impl_invalid_index_dir_argument(bad_index_dir) -> None:
    result = find_symbol_impl(bad_index_dir, "Estado_OP")

    assert result["error"] == "invalid_argument"


@pytest.mark.parametrize("bad_name", ["", "   ", None, 42])
def test_find_symbol_impl_invalid_name_argument(tmp_path, bad_name) -> None:
    _write_index(tmp_path, symbols=[_main_prg()])

    result = find_symbol_impl(str(tmp_path), bad_name)

    assert result["error"] == "invalid_argument"


@pytest.mark.parametrize("bad_question", ["", "   ", None, 7])
def test_ask_project_impl_invalid_question_argument(tmp_path, bad_question) -> None:
    _write_index(tmp_path, symbols=[_main_prg()])

    result = ask_project_impl(str(tmp_path), bad_question)

    assert result["error"] == "invalid_argument"


def test_open_project_index_invalid_index_dir_argument() -> None:
    result = open_project_index_impl("")

    assert result["error"] == "invalid_argument"


def test_find_reads_writes_calls_callers_reject_empty_name(tmp_path) -> None:
    _write_index(tmp_path, symbols=[_main_prg()])

    for fn in (find_reads_impl, find_writes_impl, find_calls_impl, find_callers_impl):
        result = fn(str(tmp_path), "")
        assert result["error"] == "invalid_argument"


# ---------------------------------------------------------------------------
# cache: mesmo index_dir reutiliza; index_dir diferente nao vaza estado
# ---------------------------------------------------------------------------


def test_repeated_calls_same_index_dir_open_project_index_once(tmp_path, monkeypatch) -> None:
    _write_index(tmp_path, symbols=[_main_prg()])

    import mastertool_bridge.api as api_mod

    calls = []
    original = api_mod.load_query_bundle

    def spy(index_dir):
        calls.append(index_dir)
        return original(index_dir)

    monkeypatch.setattr(api_mod, "load_query_bundle", spy)

    find_symbol_impl(str(tmp_path), "Estado_OP")
    find_symbol_impl(str(tmp_path), "Estado_OP")

    assert len(calls) == 1


def test_two_different_index_dirs_open_and_cache_independently(tmp_path, monkeypatch) -> None:
    dir_a = tmp_path / "index_a"
    dir_b = tmp_path / "index_b"
    dir_a.mkdir()
    dir_b.mkdir()

    prg_a = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="OnlyInA", file="a.st")
    prg_b = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="OnlyInB", file="b.st")
    _write_index(dir_a, symbols=[prg_a])
    _write_index(dir_b, symbols=[prg_b])

    import mastertool_bridge.api as api_mod

    calls = []
    original = api_mod.load_query_bundle

    def spy(index_dir):
        calls.append(index_dir)
        return original(index_dir)

    monkeypatch.setattr(api_mod, "load_query_bundle", spy)

    result_a = find_symbol_impl(str(dir_a), "OnlyInA")
    result_b = find_symbol_impl(str(dir_b), "OnlyInB")

    assert result_a["status"] == "resolved"
    assert result_b["status"] == "resolved"
    assert len(calls) == 2  # cada index_dir abriu/cacheou o seu proprio, independente

    # nenhum vazamento: OnlyInA nao existe no indice B e vice-versa
    assert find_symbol_impl(str(dir_a), "OnlyInB")["status"] == "unresolved"
    assert find_symbol_impl(str(dir_b), "OnlyInA")["status"] == "unresolved"

    # reconsultar os mesmos 2 index_dir nao reabre
    find_symbol_impl(str(dir_a), "OnlyInA")
    find_symbol_impl(str(dir_b), "OnlyInB")
    assert len(calls) == 2

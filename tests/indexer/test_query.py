"""Testes de mastertool_bridge.indexer.query.

Fixtures SINTETICAS construidas em memoria (sem tocar disco), exceto para os
testes de `load_query_bundle` (que precisam de arquivos reais/tmp_path).
"""

from __future__ import annotations

import json

from mastertool_bridge.exceptions import ValidationError
from mastertool_bridge.indexer.models import (
    PouSymbol,
    SourceLocation,
    TypeSymbol,
    VariableDeclaration,
)
from mastertool_bridge.indexer.query import (
    QueryIndexBundle,
    find_calls,
    find_callers,
    find_reads,
    find_symbol,
    find_writes,
    load_query_bundle,
)
from mastertool_bridge.indexer.symbol_resolver import ProjectSymbolIndex
from mastertool_bridge.utils.json_io import write_json

import pytest


def _loc(file: str = "f.st", line: int = 1, col: int = 1) -> SourceLocation:
    return SourceLocation(file=file, line=line, column=col)


def _var(
    name: str,
    declared_type: str,
    scope: str,
    location: SourceLocation | None = None,
) -> VariableDeclaration:
    return VariableDeclaration(
        name=name, declared_type=declared_type, scope=scope, location=location
    )


def _bundle(
    symbols: list[PouSymbol],
    resolved_calls: list[dict] | None = None,
    callers: dict | None = None,
    resolved_references: list[dict] | None = None,
    read_write_index: dict | None = None,
) -> QueryIndexBundle:
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


def _ref_entry(
    node_id: str,
    name: str,
    classification: str,
    resolution_state: str = "resolved",
    resolved_symbol: str | None = None,
    line: int = 1,
    col: int = 1,
    file: str = "f.st",
    **extra,
) -> dict:
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


def _call_entry(
    node_id: str,
    callee: str,
    resolution_state: str = "resolved",
    resolved_symbol: str | None = None,
    line: int = 1,
    col: int = 1,
    file: str = "f.st",
) -> dict:
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


def _caller_site(
    node_id: str, callee: str, line: int = 1, col: int = 1, file: str = "f.st"
) -> dict:
    return {
        "node_id": node_id,
        "file": file,
        "callee": callee,
        "location": {"file": file, "line": line, "column": col},
        "rule_applied": "fb_instance",
    }


# ---------------------------------------------------------------------------
# find_symbol
# ---------------------------------------------------------------------------


def test_find_symbol_unique_bare_name_resolved() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(line=5))],
    )
    bundle = _bundle([prg])

    result = find_symbol(bundle, "Estado_OP")

    assert result.status == "resolved"
    assert result.count == 1
    assert result.evidence[0]["node_id"] == "application/prg/0"


def test_find_symbol_duplicate_variable_in_different_pous_is_ambiguous() -> None:
    prg1 = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(line=5))],
    )
    prg2 = PouSymbol(
        node_id="application/prg/1",
        pou_kind="PROGRAM",
        name="SecondaryPrg",
        file="g.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(file="g.st", line=9))],
    )
    bundle = _bundle([prg1, prg2])

    result = find_symbol(bundle, "Estado_OP")

    assert result.status == "ambiguous"
    assert result.count == 2
    node_ids = {e["node_id"] for e in result.evidence}
    assert node_ids == {"application/prg/0", "application/prg/1"}


def test_find_symbol_nonexistent_name_is_unresolved() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    bundle = _bundle([prg])

    result = find_symbol(bundle, "NomeQueNaoExiste")

    assert result.status == "unresolved"
    assert result.count == 0
    assert result.evidence == []


def test_find_symbol_dotted_partially_resolved_chain() -> None:
    gvl = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="GvlDiag",
        file="f.st",
        variables=[_var("DG_Contador", "DINT", "VAR_GLOBAL")],
    )
    bundle = _bundle([gvl])

    result = find_symbol(bundle, "GvlDiag.NaoExiste")

    assert result.status == "partially_resolved"
    assert result.count == 1
    entry = result.evidence[0]
    assert entry["resolved_prefix"] == "GvlDiag"
    assert entry["unresolved_suffix"] == "NaoExiste"
    assert entry["reason"]


def test_find_symbol_dotted_ambiguous_two_gvls_same_name() -> None:
    gvl1 = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="GvlDup",
        file="f.st",
        variables=[_var("X", "INT", "VAR_GLOBAL")],
    )
    gvl2 = PouSymbol(
        node_id="application/gvl/1",
        pou_kind="GVL",
        name="GvlDup",
        file="g.st",
        variables=[_var("X", "INT", "VAR_GLOBAL")],
    )
    bundle = _bundle([gvl1, gvl2])

    result = find_symbol(bundle, "GvlDup.X")

    assert result.status == "ambiguous"
    assert result.count == 2
    node_ids = {e["node_id"] for e in result.evidence}
    assert node_ids == {"application/gvl/0", "application/gvl/1"}


def test_find_symbol_qualified_name_resolved() -> None:
    gvl = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="GvlDiag",
        file="f.st",
        variables=[_var("DG_Contador", "DINT", "VAR_GLOBAL")],
        is_qualified_only=True,
    )
    bundle = _bundle([gvl])

    result = find_symbol(bundle, "GvlDiag.DG_Contador")

    assert result.status == "resolved"
    assert result.count == 1
    assert result.evidence[0]["resolved_symbol"] == "application/gvl/0"


def test_find_symbol_no_duplicates() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Unique_Var", "BOOL", "VAR", _loc(line=1))],
    )
    bundle = _bundle([prg])

    result = find_symbol(bundle, "Unique_Var")

    assert result.count == 1


# ---------------------------------------------------------------------------
# find_reads / find_writes
# ---------------------------------------------------------------------------


def test_find_reads_multiple_occurrences_found_no_dedup_lost() -> None:
    refs = [
        _ref_entry("application/prg/0#stmt0", "IN_PERM_DESCARGA", "read", line=1),
        _ref_entry("application/prg/0#stmt1", "IN_PERM_DESCARGA", "read", line=2),
        _ref_entry("application/prg/1#stmt0", "IN_PERM_DESCARGA", "read", resolution_state="unresolved", line=3),
    ]
    bundle = _bundle([], resolved_references=refs)

    result = find_reads(bundle, "IN_PERM_DESCARGA")

    assert result.status == "found"
    assert result.count == 3
    states = {e["resolution_state"] for e in result.evidence}
    assert states == {"resolved", "unresolved"}


def test_find_reads_no_occurrences_not_found() -> None:
    bundle = _bundle([], resolved_references=[])

    result = find_reads(bundle, "NomeSemOcorrencia")

    assert result.status == "not_found"
    assert result.count == 0
    assert result.evidence == []


def test_find_writes_filters_by_classification() -> None:
    refs = [
        _ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=1),
        _ref_entry("application/prg/0#stmt1", "Estado_OP", "read", line=2),
        _ref_entry("application/prg/0#stmt2", "Estado_OP", "read_write", line=3),
    ]
    bundle = _bundle([], resolved_references=refs)

    result = find_writes(bundle, "Estado_OP")

    assert result.status == "found"
    assert result.count == 2


def test_find_reads_dotted_partially_resolved_reference() -> None:
    refs = [
        _ref_entry(
            "application/prg/0#stmt0",
            "VarMotores.MT01.RetornoDisjuntor",
            "read",
            resolution_state="partially_resolved",
            resolved_symbol="application/gvl/0",
            resolved_prefix="VarMotores.MT01",
            unresolved_suffix="RetornoDisjuntor",
            reason="member metadata unavailable",
        )
    ]
    bundle = _bundle([], resolved_references=refs)

    result = find_reads(bundle, "VarMotores.MT01.RetornoDisjuntor")

    assert result.status == "found"
    assert result.count == 1
    entry = result.evidence[0]
    assert entry["resolution_state"] == "partially_resolved"
    assert entry["resolved_prefix"] == "VarMotores.MT01"
    assert entry["unresolved_suffix"] == "RetornoDisjuntor"


# ---------------------------------------------------------------------------
# find_calls -- direção de SAÍDA: "o que a POU <query> chama?"
# ---------------------------------------------------------------------------


def test_find_calls_unique_pou_with_outgoing_calls() -> None:
    """POU única resolvida com chamadas de saída (caso principal), refletindo
    o smoke test real: MainPrg chama SpecialVariablesPrg/StartPrg/UserPrg."""
    main = PouSymbol(node_id="application/6/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    calls = [
        _call_entry("application/6/0#stmt0", "SpecialVariablesPrg", resolved_symbol="application/prg/1", line=1),
        _call_entry("application/6/0#stmt1", "StartPrg", resolved_symbol="application/prg/2", line=2),
        _call_entry("application/6/0#stmt2", "UserPrg", resolved_symbol="application/prg/3", line=3),
    ]
    bundle = _bundle([main], resolved_calls=calls)

    result = find_calls(bundle, "MainPrg")

    assert result.status == "resolved"
    assert result.count == 3
    callees = {e["callee"] for e in result.evidence}
    assert callees == {"SpecialVariablesPrg", "StartPrg", "UserPrg"}
    for entry in result.evidence:
        assert entry["resolution_state"] == "resolved"


def test_find_calls_ambiguous_name_grouped_by_candidate() -> None:
    prg1 = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="DupPrg", file="f.st")
    prg2 = PouSymbol(node_id="application/prg/1", pou_kind="PROGRAM", name="DupPrg", file="g.st")
    calls = [
        _call_entry("application/prg/0#stmt0", "Foo", resolved_symbol="application/prg/9", line=1),
        _call_entry("application/prg/1#stmt0", "Bar", resolved_symbol="application/prg/8", line=2),
    ]
    bundle = _bundle([prg1, prg2], resolved_calls=calls)

    result = find_calls(bundle, "DupPrg")

    assert result.status == "ambiguous"
    assert result.count == 2
    candidate_ids = {e["candidate_node_id"] for e in result.evidence}
    assert candidate_ids == {"application/prg/0", "application/prg/1"}


def test_find_calls_nonexistent_symbol_unresolved() -> None:
    bundle = _bundle([], resolved_calls=[])

    result = find_calls(bundle, "NaoExiste")

    assert result.status == "unresolved"
    assert result.count == 0
    assert result.evidence == []


def test_find_calls_name_matches_non_pou_kind_is_unresolved() -> None:
    """Nome bate com GVL (não é PROGRAM/FUNCTION_BLOCK/FUNCTION) -- mesmo
    tratamento que find_callers já dá a este caso (via
    _call_target_candidates, que filtra por _CALL_TARGET_KINDS)."""
    gvl = PouSymbol(node_id="application/gvl/0", pou_kind="GVL", name="GvlDiag", file="f.st")
    bundle = _bundle([gvl], resolved_calls=[])

    result = find_calls(bundle, "GvlDiag")

    assert result.status == "unresolved"
    assert result.count == 0


def test_find_calls_pou_with_zero_outgoing_calls_has_note() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="LeafPrg", file="f.st")
    bundle = _bundle([prg], resolved_calls=[])

    result = find_calls(bundle, "LeafPrg")

    assert result.status == "resolved"
    assert result.count == 0
    assert result.note is not None


def test_find_calls_includes_resolved_ambiguous_and_unresolved_calls() -> None:
    """Nenhuma chamada escondida por causa do próprio resolution_state --
    resolved, ambiguous e unresolved todas aparecem como evidência."""
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    calls = [
        _call_entry("application/prg/0#stmt0", "StartPrg", resolution_state="resolved", resolved_symbol="application/prg/1", line=1),
        _call_entry("application/prg/0#stmt1", "DupTarget", resolution_state="ambiguous", resolved_symbol=None, line=2),
        _call_entry("application/prg/0#stmt2", "SysTimeCore.SysTimeGetUs", resolution_state="unresolved", resolved_symbol=None, line=3),
    ]
    bundle = _bundle([prg], resolved_calls=calls)

    result = find_calls(bundle, "MainPrg")

    assert result.status == "resolved"
    assert result.count == 3
    states = {e["resolution_state"] for e in result.evidence}
    assert states == {"resolved", "ambiguous", "unresolved"}


def test_find_calls_dotted_library_callee_shown_as_evidence() -> None:
    """Chamada de método/biblioteca (callee pontuado, unresolved) originada
    dentro da POU aparece normalmente como evidência de find_calls."""
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    calls = [
        _call_entry(
            "application/prg/0#stmt0",
            "SysTimeCore.SysTimeGetUs",
            resolution_state="unresolved",
            resolved_symbol=None,
        )
    ]
    bundle = _bundle([prg], resolved_calls=calls)

    result = find_calls(bundle, "MainPrg")

    assert result.status == "resolved"
    assert result.count == 1
    assert result.evidence[0]["callee"] == "SysTimeCore.SysTimeGetUs"
    assert result.evidence[0]["resolution_state"] == "unresolved"
    assert result.evidence[0]["confidence"] == "none"


def test_find_calls_multiple_calls_to_same_target_not_deduped() -> None:
    """Múltiplas chamadas ao MESMO alvo em linhas diferentes -- 2+
    evidências distintas, nenhuma deduplicada indevidamente."""
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    calls = [
        _call_entry("application/prg/0#stmt0", "HelperPrg", resolved_symbol="application/prg/1", line=1),
        _call_entry("application/prg/0#stmt1", "HelperPrg", resolved_symbol="application/prg/1", line=2),
    ]
    bundle = _bundle([prg], resolved_calls=calls)

    result = find_calls(bundle, "MainPrg")

    assert result.status == "resolved"
    assert result.count == 2
    lines = sorted(e["line"] for e in result.evidence)
    assert lines == [1, 2]


# ---------------------------------------------------------------------------
# find_callers
# ---------------------------------------------------------------------------


def test_find_callers_unique_symbol_with_callers() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="SpecialVariablesPrg", file="f.st")
    callers = {
        "application/prg/0": [
            _caller_site("application/prg/1#stmt0", "SpecialVariablesPrg", line=1),
            _caller_site("application/prg/2#stmt0", "SpecialVariablesPrg", line=2),
        ]
    }
    bundle = _bundle([prg], callers=callers)

    result = find_callers(bundle, "SpecialVariablesPrg")

    assert result.status == "resolved"
    assert result.count == 2
    assert result.note is None


def test_find_callers_unique_symbol_zero_callers_has_note() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="NeverCalledPrg", file="f.st")
    bundle = _bundle([prg], callers={})

    result = find_callers(bundle, "NeverCalledPrg")

    assert result.status == "resolved"
    assert result.count == 0
    assert result.note is not None
    assert "callers.json" in result.note


def test_find_callers_ambiguous_grouped_by_candidate() -> None:
    prg1 = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="DupPrg", file="f.st")
    prg2 = PouSymbol(node_id="application/prg/1", pou_kind="PROGRAM", name="DupPrg", file="g.st")
    callers = {
        "application/prg/0": [_caller_site("application/prg/9#stmt0", "DupPrg", line=1)],
        "application/prg/1": [_caller_site("application/prg/8#stmt0", "DupPrg", line=2)],
    }
    bundle = _bundle([prg1, prg2], callers=callers)

    result = find_callers(bundle, "DupPrg")

    assert result.status == "ambiguous"
    assert result.count == 2
    candidate_ids = {e["candidate_node_id"] for e in result.evidence}
    assert candidate_ids == {"application/prg/0", "application/prg/1"}
    # Nunca funde: cada entrada carrega seu proprio candidate_node_id.
    for entry in result.evidence:
        assert entry["target_node_id"] == entry["candidate_node_id"]


def test_find_callers_nonexistent_symbol_unresolved() -> None:
    bundle = _bundle([])

    result = find_callers(bundle, "NaoExiste")

    assert result.status == "unresolved"
    assert result.count == 0


# ---------------------------------------------------------------------------
# Determinismo / no-duplicates
# ---------------------------------------------------------------------------


def test_json_output_is_deterministic_across_runs() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(line=5))],
    )
    bundle = _bundle([prg])

    result1 = find_symbol(bundle, "Estado_OP")
    result2 = find_symbol(bundle, "Estado_OP")

    json1 = json.dumps(result1.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
    json2 = json.dumps(result2.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
    assert json1 == json2


def test_no_duplicate_evidence_in_any_command() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("X", "INT", "VAR", _loc(line=1))],
    )
    refs = [_ref_entry("application/prg/0#stmt0", "X", "read", line=1)]
    calls = [_call_entry("application/prg/0#stmt0", "MainPrg", resolved_symbol="application/prg/0")]
    callers = {"application/prg/0": [_caller_site("application/prg/1#stmt0", "MainPrg", line=1)]}
    bundle = _bundle([prg], resolved_calls=calls, callers=callers, resolved_references=refs)

    for result in (
        find_symbol(bundle, "X"),
        find_reads(bundle, "X"),
        find_calls(bundle, "MainPrg"),
        find_callers(bundle, "MainPrg"),
    ):
        keys = [(e.get("node_id"), e.get("line"), e.get("column")) for e in result.evidence]
        assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# Contrato de direção: find_calls (SAIDA) vs find_callers (ENTRADA)
# ---------------------------------------------------------------------------


def test_find_calls_and_find_callers_are_opposite_directions() -> None:
    """POU A chama POU B: find_calls(A) -> B como evidencia, find_callers(B)
    -> A como evidencia (mesma chamada, duas direcoes). find_calls(B) e
    find_callers(A) devem retornar vazio para o MESMO par (a chamada so
    existe numa direcao) -- trava a distincao de direcao para sempre."""
    pou_a = PouSymbol(node_id="application/prg/a", pou_kind="PROGRAM", name="A", file="a.st")
    pou_b = PouSymbol(node_id="application/prg/b", pou_kind="PROGRAM", name="B", file="b.st")
    calls = [
        _call_entry("application/prg/a#stmt0", "B", resolution_state="resolved", resolved_symbol="application/prg/b", line=1)
    ]
    callers = {
        "application/prg/b": [_caller_site("application/prg/a#stmt0", "B", line=1)]
    }
    bundle = _bundle([pou_a, pou_b], resolved_calls=calls, callers=callers)

    calls_from_a = find_calls(bundle, "A")
    callers_of_b = find_callers(bundle, "B")
    calls_from_b = find_calls(bundle, "B")
    callers_of_a = find_callers(bundle, "A")

    assert calls_from_a.status == "resolved"
    assert calls_from_a.count == 1
    assert calls_from_a.evidence[0]["callee"] == "B"

    assert callers_of_b.status == "resolved"
    assert callers_of_b.count == 1

    assert calls_from_b.status == "resolved"
    assert calls_from_b.count == 0

    assert callers_of_a.status == "resolved"
    assert callers_of_a.count == 0


# ---------------------------------------------------------------------------
# load_query_bundle (arquivo real / tmp_path)
# ---------------------------------------------------------------------------


def test_load_query_bundle_missing_dir_raises_validation_error(tmp_path) -> None:
    with pytest.raises(ValidationError):
        load_query_bundle(tmp_path / "does_not_exist")


def test_load_query_bundle_missing_file_raises_validation_error(tmp_path) -> None:
    write_json(tmp_path / "symbols.json", [])
    # Demais 4 arquivos obrigatorios ausentes.

    with pytest.raises(ValidationError) as exc_info:
        load_query_bundle(tmp_path)

    assert "resolved-calls.json" in str(exc_info.value)


def test_load_query_bundle_corrupted_file_raises_validation_error(tmp_path) -> None:
    write_json(tmp_path / "symbols.json", [])
    write_json(tmp_path / "resolved-calls.json", [])
    write_json(tmp_path / "callers.json", {})
    write_json(tmp_path / "resolved-references.json", [])
    (tmp_path / "read-write-index.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_query_bundle(tmp_path)


def test_load_query_bundle_valid_files_builds_symbol_index(tmp_path) -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("X", "INT", "VAR")],
    )
    write_json(tmp_path / "symbols.json", [prg.to_dict()])
    write_json(tmp_path / "resolved-calls.json", [])
    write_json(tmp_path / "callers.json", {})
    write_json(tmp_path / "resolved-references.json", [])
    write_json(tmp_path / "read-write-index.json", {})

    bundle = load_query_bundle(tmp_path)

    assert len(bundle.pou_symbols) == 1
    assert bundle.symbol_index.pou_by_node_id("application/prg/0") is not None


# ---------------------------------------------------------------------------
# load_query_bundle + type-index.json (regressao do bug de STRUCT/DUT)
# ---------------------------------------------------------------------------


def _struct_type_dict(
    node_id: str = "types/0",
    name: str = "ST_Motor",
    members: list[dict] | None = None,
) -> dict:
    return TypeSymbol(
        node_id=node_id,
        name=name,
        kind="struct",
        file="dut.st",
        members=[
            VariableDeclaration(**m) if not isinstance(m, VariableDeclaration) else m
            for m in (members or [])
        ]
        if members
        else [
            VariableDeclaration(
                name="RetornoDisjuntor", declared_type="BOOL", scope="STRUCT_MEMBER"
            )
        ],
    ).to_dict()


def _minimal_required_files(tmp_path) -> None:
    write_json(tmp_path / "symbols.json", [])
    write_json(tmp_path / "resolved-calls.json", [])
    write_json(tmp_path / "callers.json", {})
    write_json(tmp_path / "resolved-references.json", [])
    write_json(tmp_path / "read-write-index.json", {})


def test_load_query_bundle_reads_type_index_and_populates_type_symbols(tmp_path) -> None:
    _minimal_required_files(tmp_path)
    write_json(
        tmp_path / "type-index.json",
        {
            "declared_type_usage": {},
            "types": [_struct_type_dict()],
        },
    )

    bundle = load_query_bundle(tmp_path)

    assert len(bundle.symbol_index.type_symbols) == 1
    type_symbol = bundle.symbol_index.type_symbols[0]
    assert type_symbol.name == "ST_Motor"
    assert type_symbol.kind == "struct"
    assert [m.name for m in type_symbol.members] == ["RetornoDisjuntor"]
    assert "ST_Motor" in bundle.symbol_index.types_by_name


def test_load_query_bundle_missing_type_index_file_gives_empty_type_symbols(tmp_path) -> None:
    _minimal_required_files(tmp_path)
    # type-index.json NAO escrito -- deliberadamente ausente.

    bundle = load_query_bundle(tmp_path)

    assert bundle.symbol_index.type_symbols == []


def test_load_query_bundle_type_index_without_types_key_gives_empty_type_symbols(tmp_path) -> None:
    _minimal_required_files(tmp_path)
    # Formato antigo: so declared_type_usage, sem a chave "types".
    write_json(tmp_path / "type-index.json", {"declared_type_usage": {}})

    bundle = load_query_bundle(tmp_path)

    assert bundle.symbol_index.type_symbols == []


def test_load_query_bundle_type_index_present_but_empty_types_gives_empty_list(tmp_path) -> None:
    _minimal_required_files(tmp_path)
    write_json(tmp_path / "type-index.json", {"declared_type_usage": {}, "types": []})

    bundle = load_query_bundle(tmp_path)

    assert bundle.symbol_index.type_symbols == []


def test_load_query_bundle_corrupted_type_index_gives_empty_list_no_exception(tmp_path) -> None:
    _minimal_required_files(tmp_path)
    (tmp_path / "type-index.json").write_text("{not valid json", encoding="utf-8")

    bundle = load_query_bundle(tmp_path)

    assert bundle.symbol_index.type_symbols == []


def test_load_query_bundle_type_index_alias_and_unknown_kinds_reconstructed(tmp_path) -> None:
    _minimal_required_files(tmp_path)
    alias_dict = TypeSymbol(
        node_id="types/1",
        name="T_Alias",
        kind="alias",
        file="dut.st",
        alias_target="INT",
    ).to_dict()
    unknown_dict = TypeSymbol(
        node_id="types/2",
        name="E_Estado",
        kind="unknown",
        file="dut.st",
    ).to_dict()
    write_json(
        tmp_path / "type-index.json",
        {"declared_type_usage": {}, "types": [alias_dict, unknown_dict]},
    )

    bundle = load_query_bundle(tmp_path)

    by_name = {t.name: t for t in bundle.symbol_index.type_symbols}
    assert by_name["T_Alias"].kind == "alias"
    assert by_name["T_Alias"].alias_target == "INT"
    assert by_name["T_Alias"].members == []
    assert by_name["E_Estado"].kind == "unknown"
    assert by_name["E_Estado"].members == []


def test_load_query_bundle_struct_member_chain_resolves_via_find_symbol(tmp_path) -> None:
    """Regressao explicita do bug: uma GVL cuja variavel e do tipo de um
    STRUCT indexado em type-index.json deve resolver "GVL.Var.Membro" como
    "resolved" via find_symbol (que usa resolve_dotted_reference AO VIVO),
    tal qual resolved-references.json ja resolvia apos build_static_index."""
    gvl = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="VarMotores",
        file="gvl.st",
        variables=[_var("MT01", "ST_Motor", "VAR_GLOBAL")],
    )
    write_json(tmp_path / "symbols.json", [gvl.to_dict()])
    write_json(tmp_path / "resolved-calls.json", [])
    write_json(tmp_path / "callers.json", {})
    write_json(tmp_path / "resolved-references.json", [])
    write_json(tmp_path / "read-write-index.json", {})
    write_json(
        tmp_path / "type-index.json",
        {
            "declared_type_usage": {},
            "types": [_struct_type_dict(name="ST_Motor")],
        },
    )

    bundle = load_query_bundle(tmp_path)
    result = find_symbol(bundle, "VarMotores.MT01.RetornoDisjuntor")

    assert result.status == "resolved"
    assert result.count == 1
    assert result.evidence[0]["resolution_state"] == "resolved"

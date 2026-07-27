"""Testes de mastertool_bridge.indexer.query_response (answer_query /
format_answer_human_readable) e de run_answer (integração, query.py).

Reproduz o padrão de fixtures de tests/indexer/test_query.py (bundles
sintéticos em memória) e de test_query_ask_integration.py (fixtures reais em
disco via write_json, para run_answer).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastertool_bridge.indexer.models import PouSymbol, SourceLocation, VariableDeclaration
from mastertool_bridge.indexer.query import QueryIndexBundle, load_query_bundle, run_answer
from mastertool_bridge.indexer.query_response import answer_query, format_answer_human_readable
from mastertool_bridge.indexer.symbol_resolver import ProjectSymbolIndex
from mastertool_bridge.utils.json_io import write_json


def _loc(file: str = "f.st", line: int = 1, col: int = 1) -> SourceLocation:
    return SourceLocation(file=file, line=line, column=col)


def _var(name: str, declared_type: str, scope: str, location=None) -> VariableDeclaration:
    return VariableDeclaration(name=name, declared_type=declared_type, scope=scope, location=location)


def _bundle(
    symbols: list[PouSymbol],
    resolved_calls: list[dict] | None = None,
    callers: dict | None = None,
    resolved_references: list[dict] | None = None,
    read_write_index: dict | None = None,
) -> QueryIndexBundle:
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


def _caller_site(node_id: str, callee: str, line: int = 1, col: int = 1, file: str = "f.st") -> dict:
    return {
        "node_id": node_id,
        "file": file,
        "callee": callee,
        "location": {"file": file, "line": line, "column": col},
        "rule_applied": "fb_instance",
    }


# ---------------------------------------------------------------------------
# answered para cada uma das 5 intencoes
# ---------------------------------------------------------------------------


def test_answer_symbol_resolved_variable() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(line=5, col=3))],
    )
    bundle = _bundle([prg])

    answer = answer_query("find symbol Estado_OP", bundle)

    assert answer.status == "answered"
    assert answer.schema_version == 1
    assert answer.summary == (
        "Estado_OP foi resolvido como variável da POU MainPrg. Declaração: f.st:5:3"
    )
    assert len(answer.evidence) == 1
    assert answer.evidence[0]["pou_name"] == "MainPrg"
    assert answer.limitations == []


def test_answer_reads_found() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "read", line=11)]
    bundle = _bundle([prg], resolved_references=refs)

    answer = answer_query("quem lê Estado_OP", bundle)

    assert answer.status == "answered"
    assert answer.summary == "Estado_OP possui 1 ocorrências classificadas como leitura."
    assert len(answer.evidence) == 1


def test_answer_writes_found() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    refs = [_ref_entry("application/prg/0#stmt0", "Estado_OP", "write", line=10)]
    bundle = _bundle([prg], resolved_references=refs)

    answer = answer_query("quem escreve Estado_OP", bundle)

    assert answer.status == "answered"
    assert answer.summary == "Estado_OP possui 1 ocorrências classificadas como escrita."


def test_answer_calls_resolved_three_calls() -> None:
    main = PouSymbol(node_id="application/main/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    calls = [
        _call_entry("application/main/0#stmt0", "SpecialVariablesPrg", line=1),
        _call_entry("application/main/0#stmt1", "StartPrg", line=2),
        _call_entry("application/main/0#stmt2", "UserPrg", line=3),
    ]
    bundle = _bundle([main], resolved_calls=calls)

    answer = answer_query("o que MainPrg chama?", bundle)

    assert answer.status == "answered"
    assert answer.summary == "MainPrg realiza 3 chamadas:"
    assert len(answer.evidence) == 3
    displays = {e["display"] for e in answer.evidence}
    assert displays == {"- SpecialVariablesPrg", "- StartPrg", "- UserPrg"}


def test_answer_callers_resolved_single_caller() -> None:
    main = PouSymbol(node_id="application/main/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    special = PouSymbol(
        node_id="application/special/0", pou_kind="PROGRAM", name="SpecialVariablesPrg", file="f.st"
    )
    callers = {"application/special/0": [_caller_site("application/main/0#stmt0", "SpecialVariablesPrg")]}
    bundle = _bundle([main, special], callers=callers)

    answer = answer_query("quem chama SpecialVariablesPrg?", bundle)

    assert answer.status == "answered"
    assert answer.summary == "SpecialVariablesPrg é chamado por MainPrg."
    assert len(answer.evidence) == 1


# ---------------------------------------------------------------------------
# simbolo unico / ambiguo / inexistente
# ---------------------------------------------------------------------------


def test_answer_symbol_ambiguous_two_candidates() -> None:
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

    answer = answer_query("find symbol Estado_OP", bundle)

    assert answer.status == "ambiguous"
    assert answer.summary == (
        "Estado_OP corresponde a 2 símbolos e não pode ser escolhido automaticamente."
    )
    assert len(answer.evidence) == 2


def test_answer_symbol_not_found() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    bundle = _bundle([prg])

    answer = answer_query("find symbol NomeQueNaoExiste", bundle)

    assert answer.status == "not_found"
    assert answer.summary == (
        "Nenhum símbolo chamado 'NomeQueNaoExiste' foi encontrado nos índices disponíveis."
    )
    assert answer.evidence == []


# ---------------------------------------------------------------------------
# resultado vazio: reads/writes sem ocorrencia; calls sem chamadas com nota;
# callers com zero chamadores reproduzindo a frase exata
# ---------------------------------------------------------------------------


def test_answer_reads_not_found() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    bundle = _bundle([prg])

    answer = answer_query("quem lê Estado_OP", bundle)

    assert answer.status == "not_found"
    assert answer.summary == (
        "Nenhuma ocorrência de leitura de 'Estado_OP' foi encontrada no índice disponível."
    )


def test_answer_writes_not_found() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    bundle = _bundle([prg])

    answer = answer_query("quem escreve Estado_OP", bundle)

    assert answer.status == "not_found"
    assert answer.summary == (
        "Nenhuma ocorrência de escrita de 'Estado_OP' foi encontrada no índice disponível."
    )


def test_answer_calls_resolved_zero_calls_has_note() -> None:
    main = PouSymbol(node_id="application/main/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    bundle = _bundle([main])

    answer = answer_query("o que MainPrg chama?", bundle)

    assert answer.status == "answered"
    assert answer.summary == "MainPrg não realiza nenhuma chamada registrada no índice."
    assert answer.evidence == []
    assert answer.limitations  # nota reaproveitada


def test_answer_callers_resolved_zero_callers_exact_phrase() -> None:
    main = PouSymbol(node_id="application/main/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    bundle = _bundle([main])

    answer = answer_query("quem chama MainPrg?", bundle)

    assert answer.status == "answered"
    assert answer.summary == "Nenhum chamador de MainPrg foi encontrado nos índices disponíveis."


# ---------------------------------------------------------------------------
# referencia parcialmente resolvida (find_symbol dotted)
# ---------------------------------------------------------------------------


def test_answer_symbol_partially_resolved_var_motores() -> None:
    fb_motor = PouSymbol(
        node_id="application/fb_motor/0",
        pou_kind="FUNCTION_BLOCK",
        name="FB_Motor",
        file="f.st",
        variables=[_var("RetornoDisjuntor", "BOOL", "VAR")],
    )
    gvl = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="VarEquipamentosExemplo",
        file="f.st",
        variables=[_var("MT01", "FB_Motor", "VAR_GLOBAL")],
    )
    bundle = _bundle([fb_motor, gvl])

    answer = answer_query("find symbol VarEquipamentosExemplo.MT01.RetornoDisjuntorX", bundle)

    assert answer.status == "answered"
    assert "parcialmente resolvido" in answer.summary
    assert len(answer.limitations) == 1
    assert "não pôde ser comprovado" in answer.limitations[0]


# ---------------------------------------------------------------------------
# chamada de biblioteca nao resolvida em find_calls
# ---------------------------------------------------------------------------


def test_answer_calls_unresolved_library_call_suffix() -> None:
    main = PouSymbol(node_id="application/main/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    calls = [
        _call_entry(
            "application/main/0#stmt0",
            "SysTimeCore.SysTimeGetUs",
            resolution_state="unresolved",
            line=1,
        )
    ]
    bundle = _bundle([main], resolved_calls=calls)

    answer = answer_query("o que MainPrg chama?", bundle)

    assert answer.status == "answered"
    assert len(answer.evidence) == 1
    assert answer.evidence[0]["display"] == (
        "- SysTimeCore.SysTimeGetUs — destino não resolvido no índice do projeto"
    )


# ---------------------------------------------------------------------------
# multiplas evidencias
# ---------------------------------------------------------------------------


def test_answer_reads_multiple_occurrences() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    refs = [
        _ref_entry("application/prg/0#stmt0", "Estado_OP", "read", line=1),
        _ref_entry("application/prg/0#stmt1", "Estado_OP", "read", line=2),
        _ref_entry("application/prg/0#stmt2", "Estado_OP", "read", line=3),
    ]
    bundle = _bundle([prg], resolved_references=refs)

    answer = answer_query("quem lê Estado_OP", bundle)

    assert answer.summary == "Estado_OP possui 3 ocorrências classificadas como leitura."
    assert len(answer.evidence) == 3
    assert [e["ordinal"] for e in answer.evidence] == [1, 2, 3]


def test_answer_callers_multiple_callers() -> None:
    special = PouSymbol(
        node_id="application/special/0", pou_kind="PROGRAM", name="SpecialVariablesPrg", file="f.st"
    )
    main = PouSymbol(node_id="application/main/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    other = PouSymbol(node_id="application/other/0", pou_kind="PROGRAM", name="OtherPrg", file="f.st")
    callers = {
        "application/special/0": [
            _caller_site("application/main/0#stmt0", "SpecialVariablesPrg", line=1),
            _caller_site("application/other/0#stmt0", "SpecialVariablesPrg", line=2),
        ]
    }
    bundle = _bundle([special, main, other], callers=callers)

    answer = answer_query("quem chama SpecialVariablesPrg?", bundle)

    assert answer.status == "answered"
    assert answer.summary == "SpecialVariablesPrg é chamado por 2 POUs:"
    assert len(answer.evidence) == 2


# ---------------------------------------------------------------------------
# estabilidade da ordenacao
# ---------------------------------------------------------------------------


def test_answer_stable_ordering_across_runs() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    refs = [
        _ref_entry("application/prg/0#stmt0", "Estado_OP", "read", line=1),
        _ref_entry("application/prg/0#stmt1", "Estado_OP", "read", line=2),
    ]
    bundle = _bundle([prg], resolved_references=refs)

    a1 = answer_query("quem lê Estado_OP", bundle)
    a2 = answer_query("quem lê Estado_OP", bundle)

    j1 = json.dumps(a1.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
    j2 = json.dumps(a2.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
    assert j1 == j2


# ---------------------------------------------------------------------------
# equivalencia JSON <-> texto
# ---------------------------------------------------------------------------


def test_json_and_text_output_reflect_same_facts() -> None:
    prg = PouSymbol(node_id="application/prg/0", pou_kind="PROGRAM", name="MainPrg", file="f.st")
    refs = [
        _ref_entry("application/prg/0#stmt0", "Estado_OP", "read", line=1),
        _ref_entry("application/prg/0#stmt1", "Estado_OP", "read", line=2),
    ]
    bundle = _bundle([prg], resolved_references=refs)

    answer = answer_query("quem lê Estado_OP", bundle)
    text = format_answer_human_readable(answer)
    data = answer.to_dict()

    assert data["summary"] in text
    assert str(data["status"]) in text
    assert len(data["evidence"]) == 2
    # ambos os formatos citam o mesmo pou_name para cada evidencia.
    for entry in data["evidence"]:
        assert entry["pou_name"] in text


# ---------------------------------------------------------------------------
# nenhuma execucao de find_* para intent ambiguo/nao suportado
# ---------------------------------------------------------------------------


def test_answer_ambiguous_usage_does_not_call_find(monkeypatch) -> None:
    import mastertool_bridge.indexer.query_response as qr_mod

    calls = []
    for key, fn in list(qr_mod._DISPATCH.items()):
        def spy(bundle, q, _fn=fn, _key=key):
            calls.append(_key)
            return _fn(bundle, q)

        monkeypatch.setitem(qr_mod._DISPATCH, key, spy)

    bundle = _bundle([])
    answer = answer_query("onde Estado_OP é usado?", bundle)

    assert answer.status == "ambiguous"
    assert calls == []
    assert answer.evidence == []
    assert "leitura" in answer.summary and "escrita" in answer.summary


def test_answer_unsupported_does_not_call_find(monkeypatch) -> None:
    import mastertool_bridge.indexer.query_response as qr_mod

    calls = []
    for key, fn in list(qr_mod._DISPATCH.items()):
        def spy(bundle, q, _fn=fn, _key=key):
            calls.append(_key)
            return _fn(bundle, q)

        monkeypatch.setitem(qr_mod._DISPATCH, key, spy)

    bundle = _bundle([])
    answer = answer_query("explique Estado_OP", bundle)

    assert answer.status == "unsupported"
    assert calls == []


def test_answer_invalid_does_not_call_find(monkeypatch) -> None:
    import mastertool_bridge.indexer.query_response as qr_mod

    calls = []
    for key, fn in list(qr_mod._DISPATCH.items()):
        def spy(bundle, q, _fn=fn, _key=key):
            calls.append(_key)
            return _fn(bundle, q)

        monkeypatch.setitem(qr_mod._DISPATCH, key, spy)

    bundle = _bundle([])
    answer = answer_query("", bundle)

    assert answer.status == "invalid"
    assert calls == []


# ---------------------------------------------------------------------------
# run_answer: mensagem honesta para diretorio de indice invalido/ausente
# ---------------------------------------------------------------------------


def test_run_answer_missing_index_dir_returns_error_without_raising(tmp_path) -> None:
    nonexistent = tmp_path / "does_not_exist"

    result = run_answer(nonexistent, "find symbol Estado_OP")

    assert result["status"] == "error"
    assert result["schema_version"] == 1
    assert result["evidence"] == []
    assert result["limitations"] == []
    assert "intent" in result and result["intent"] is not None


def test_run_answer_matched_real_files(tmp_path) -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(line=5))],
    )
    write_json(tmp_path / "symbols.json", [prg.to_dict()])
    write_json(tmp_path / "resolved-calls.json", [])
    write_json(tmp_path / "callers.json", {})
    write_json(tmp_path / "resolved-references.json", [])
    write_json(tmp_path / "read-write-index.json", {})

    result = run_answer(tmp_path, "find symbol Estado_OP")

    assert result["status"] == "answered"
    assert result["schema_version"] == 1
    bundle = load_query_bundle(tmp_path)
    direct = answer_query("find symbol Estado_OP", bundle)
    assert result == direct.to_dict()


def test_run_answer_stable_json_output_across_runs(tmp_path) -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("Estado_OP", "INT", "VAR", _loc(line=5))],
    )
    write_json(tmp_path / "symbols.json", [prg.to_dict()])
    write_json(tmp_path / "resolved-calls.json", [])
    write_json(tmp_path / "callers.json", {})
    write_json(tmp_path / "resolved-references.json", [])
    write_json(tmp_path / "read-write-index.json", {})

    r1 = run_answer(tmp_path, "find symbol Estado_OP")
    r2 = run_answer(tmp_path, "find symbol Estado_OP")

    j1 = json.dumps(r1, indent=2, ensure_ascii=False, sort_keys=True)
    j2 = json.dumps(r2, indent=2, ensure_ascii=False, sort_keys=True)
    assert j1 == j2

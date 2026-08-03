"""Testes de TypeSymbol (models.py) e da extensão de ProjectSymbolIndex /
resolve_alias_target (symbol_resolver.py) para conhecer tipos de DUT.

Escopo estrito desta fatia: apenas os DADOS (TypeSymbol, types_by_name,
resolve_alias_target) — a caminhada de cadeia (resolve_identifier/
resolve_dotted_reference) ainda NÃO usa TypeSymbol (isso é FASE 2).
"""

from __future__ import annotations

from mastertool_bridge.indexer.models import TypeSymbol
from mastertool_bridge.indexer.symbol_resolver import (
    ProjectSymbolIndex,
    resolve_alias_target,
)


def _type(name: str, kind: str, alias_target: str | None = None) -> TypeSymbol:
    return TypeSymbol(
        node_id=f"node/{name}",
        name=name,
        kind=kind,
        file="f.st",
        alias_target=alias_target,
    )


def test_project_symbol_index_backward_compatible_without_type_symbols() -> None:
    # Todo ProjectSymbolIndex(symbols) já existente continua funcionando sem
    # passar type_symbols.
    index = ProjectSymbolIndex([])
    assert index.types_by_name == {}
    assert index.type_symbols == []


def test_project_symbol_index_indexes_types_by_name() -> None:
    struct_a = _type("Motor", "struct")
    alias_x = _type("X", "alias", alias_target="Y")

    index = ProjectSymbolIndex([], type_symbols=[struct_a, alias_x])

    assert index.types_by_name["Motor"] == [struct_a]
    assert index.types_by_name["X"] == [alias_x]


def test_resolve_alias_target_non_alias_returns_self() -> None:
    struct_a = _type("Motor", "struct")
    index = ProjectSymbolIndex([], type_symbols=[struct_a])

    result = resolve_alias_target(struct_a, index)

    assert result is struct_a


def test_resolve_alias_target_chained_alias_reaches_final_struct() -> None:
    type_a = _type("A", "alias", alias_target="B")
    type_b = _type("B", "alias", alias_target="C")
    type_c = _type("C", "struct")

    index = ProjectSymbolIndex([], type_symbols=[type_a, type_b, type_c])

    result = resolve_alias_target(type_a, index)

    assert result is type_c


def test_resolve_alias_target_cyclic_returns_none_without_hanging() -> None:
    type_a = _type("A", "alias", alias_target="B")
    type_b = _type("B", "alias", alias_target="A")

    index = ProjectSymbolIndex([], type_symbols=[type_a, type_b])

    result = resolve_alias_target(type_a, index)

    assert result is None


def test_resolve_alias_target_missing_target_returns_none() -> None:
    type_a = _type("A", "alias", alias_target="Inexistente")
    index = ProjectSymbolIndex([], type_symbols=[type_a])

    result = resolve_alias_target(type_a, index)

    assert result is None


def test_resolve_alias_target_ambiguous_target_returns_none() -> None:
    type_a = _type("A", "alias", alias_target="Dup")
    dup1 = _type("Dup", "struct")
    dup2 = _type("Dup", "struct")

    index = ProjectSymbolIndex([], type_symbols=[type_a, dup1, dup2])

    result = resolve_alias_target(type_a, index)

    assert result is None


def test_types_by_name_has_both_entries_for_duplicate_names() -> None:
    dup1 = _type("Duplicado", "struct")
    dup2 = _type("Duplicado", "struct")

    index = ProjectSymbolIndex([], type_symbols=[dup1, dup2])

    assert len(index.types_by_name["Duplicado"]) == 2

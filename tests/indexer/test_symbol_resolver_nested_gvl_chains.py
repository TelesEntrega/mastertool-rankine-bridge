"""Testes de extensão: resolução generalizada de cadeias pontuadas de N>=2
segmentos em `symbol_resolver.resolve_dotted_reference` (commit "feat:
resolve nested GVL instance member references").

Cobre o caminho GVL -> instância de FUNCTION_BLOCK -> membro do FB
(recursivamente, se o membro em si for outro FB conhecido), com suporte a
índice de array no meio da cadeia (ex. "GVL_A.ArrayInstancias[i].Estado"),
e o novo estado de resolução "partially_resolved" para prefixos
parcialmente confirmados. Nomes de fixtures são SINTÉTICOS, diferentes dos
nomes reais do cliente."""

from __future__ import annotations

from mastertool_bridge.indexer.models import PouSymbol, VariableDeclaration
from mastertool_bridge.indexer.symbol_resolver import (
    ProjectSymbolIndex,
    resolve_dotted_reference,
)


def _var(
    name: str,
    declared_type: str,
    scope: str = "VAR_GLOBAL",
    is_array: bool = False,
    array_dimensions: list[tuple[str, str]] | None = None,
) -> VariableDeclaration:
    return VariableDeclaration(
        name=name,
        declared_type=declared_type,
        scope=scope,
        is_array=is_array,
        array_dimensions=array_dimensions,
    )


def _fb(node_id: str, name: str, variables: list[VariableDeclaration] | None = None) -> PouSymbol:
    return PouSymbol(
        node_id=node_id,
        pou_kind="FUNCTION_BLOCK",
        name=name,
        file="f.st",
        variables=variables or [],
    )


def _gvl(
    node_id: str,
    name: str,
    variables: list[VariableDeclaration],
    is_qualified_only: bool = True,
) -> PouSymbol:
    return PouSymbol(
        node_id=node_id,
        pou_kind="GVL",
        name=name,
        file="f.st",
        variables=variables,
        is_qualified_only=is_qualified_only,
    )


# ---------------------------------------------------------------------------
# 2 níveis: GVL -> instância de FB -> membro do FB.
# ---------------------------------------------------------------------------


def test_gvl_instance_member_two_levels_resolved() -> None:
    fb_type = _fb("app/fb/0", "FB_Equip", variables=[_var("Estado", "BOOL", scope="VAR")])
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "FB_Equip")])
    index = ProjectSymbolIndex([fb_type, gvl])

    result = resolve_dotted_reference("GVL_A.Instancia.Estado", None, index)

    assert result.state == "resolved"
    assert result.rule_applied == "dotted_chain"
    assert result.resolved_symbol == "app/fb/0"
    assert result.variable is not None
    assert result.variable.name == "Estado"


# ---------------------------------------------------------------------------
# 3 níveis: GVL -> instância FB -> membro que é OUTRO FB conhecido -> membro
# do segundo FB (recursão de container).
# ---------------------------------------------------------------------------


def test_gvl_instance_nested_fb_member_three_levels_resolved() -> None:
    inner_fb = _fb("app/fb/1", "FB_Sub", variables=[_var("Valor", "INT", scope="VAR")])
    outer_fb = _fb(
        "app/fb/0",
        "FB_Equip",
        variables=[_var("Subestrutura", "FB_Sub", scope="VAR")],
    )
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "FB_Equip")])
    index = ProjectSymbolIndex([inner_fb, outer_fb, gvl])

    result = resolve_dotted_reference("GVL_A.Instancia.Subestrutura.Valor", None, index)

    assert result.state == "resolved"
    assert result.resolved_symbol == "app/fb/1"
    assert result.variable is not None
    assert result.variable.name == "Valor"


# ---------------------------------------------------------------------------
# Índice de array no meio da cadeia, ignorado na busca mas preservado.
# ---------------------------------------------------------------------------


def test_gvl_array_of_instances_with_index_resolved_ignoring_index_in_lookup() -> None:
    fb_type = _fb("app/fb/0", "FB_Equip", variables=[_var("Estado", "BOOL", scope="VAR")])
    gvl = _gvl(
        "app/gvl/0",
        "GVL_A",
        variables=[
            _var(
                "ArrayInstancias",
                "ARRAY[0..3] OF FB_Equip",
                is_array=True,
                array_dimensions=[("0", "3")],
            )
        ],
    )
    index = ProjectSymbolIndex([fb_type, gvl])

    result = resolve_dotted_reference("GVL_A.ArrayInstancias[i].Estado", None, index)

    assert result.state == "resolved"
    assert result.resolved_symbol == "app/fb/0"
    assert result.variable is not None
    assert result.variable.name == "Estado"


# ---------------------------------------------------------------------------
# Não-regressão: cadeia simples de 2 segmentos, sem instância de FB.
# ---------------------------------------------------------------------------


def test_gvl_simple_variable_two_segments_still_resolved_as_gvl_explicit() -> None:
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("VariavelSimples", "DINT")])
    index = ProjectSymbolIndex([gvl])

    result = resolve_dotted_reference("GVL_A.VariavelSimples", None, index)

    assert result.state == "resolved"
    assert result.rule_applied == "gvl_explicit"
    assert result.resolved_symbol == "app/gvl/0"


# ---------------------------------------------------------------------------
# Não-regressão: instância LOCAL da POU atual (não GVL).
# ---------------------------------------------------------------------------


def test_local_instance_member_resolved_non_regression() -> None:
    fb_type = _fb("app/fb/0", "FB_Equip", variables=[_var("Estado", "BOOL", scope="VAR")])
    prg = PouSymbol(
        node_id="app/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("InstanciaLocal", "FB_Equip", scope="VAR")],
    )
    index = ProjectSymbolIndex([fb_type, prg])

    result = resolve_dotted_reference("InstanciaLocal.Estado", prg, index)

    assert result.state == "resolved"
    # resolved_symbol aponta para o DONO do último segmento confirmado
    # ("Estado", declarado dentro de FB_Equip) -- mesma convenção usada
    # para cadeias GVL-qualificadas mais longas (ver
    # test_gvl_instance_member_two_levels_resolved).
    assert result.resolved_symbol == "app/fb/0"
    assert result.variable is not None
    assert result.variable.name == "Estado"


# ---------------------------------------------------------------------------
# Biblioteca externa: primeiro segmento não bate com nada -> unresolved,
# NUNCA partially_resolved sem nenhum prefixo confirmado.
# ---------------------------------------------------------------------------


def test_external_library_call_prefix_unresolved_never_partial() -> None:
    index = ProjectSymbolIndex([])

    result = resolve_dotted_reference("Namespace.Funcao", None, index)

    assert result.state == "unresolved"
    assert result.resolved_prefix is None
    assert result.unresolved_suffix is None


# ---------------------------------------------------------------------------
# GVL inexistente.
# ---------------------------------------------------------------------------


def test_nonexistent_gvl_is_unresolved() -> None:
    index = ProjectSymbolIndex([])

    result = resolve_dotted_reference("GvlQueNaoExiste.Var", None, index)

    assert result.state == "unresolved"


# ---------------------------------------------------------------------------
# Instância inexistente dentro de uma GVL real -> partially_resolved
# (decisão documentada: ver test_symbol_resolver.py
# test_level_4_gvl_explicit_variable_not_found_is_partially_resolved).
# ---------------------------------------------------------------------------


def test_nonexistent_instance_inside_real_gvl_is_partially_resolved() -> None:
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("OutraVar", "DINT")])
    index = ProjectSymbolIndex([gvl])

    result = resolve_dotted_reference("GVL_A.InstanciaQueNaoExiste", None, index)

    assert result.state == "partially_resolved"
    assert result.resolved_prefix == "GVL_A"
    assert result.unresolved_suffix == "InstanciaQueNaoExiste"
    assert result.resolved_symbol == "app/gvl/0"


# ---------------------------------------------------------------------------
# Tipo da instância desconhecido (ex. tipo de biblioteca como TON).
# ---------------------------------------------------------------------------


def test_unknown_instance_type_is_partially_resolved() -> None:
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Temporizador", "TON")])
    index = ProjectSymbolIndex([gvl])

    result = resolve_dotted_reference("GVL_A.Temporizador.Q", None, index)

    assert result.state == "partially_resolved"
    assert result.resolved_prefix == "GVL_A.Temporizador"
    assert result.unresolved_suffix == "Q"
    assert result.resolved_symbol == "app/gvl/0"
    assert result.reason is not None


# ---------------------------------------------------------------------------
# Membro inexistente num FB conhecido.
# ---------------------------------------------------------------------------


def test_nonexistent_member_in_known_fb_is_partially_resolved() -> None:
    fb_type = _fb("app/fb/0", "FB_Equip", variables=[_var("Estado", "BOOL", scope="VAR")])
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "FB_Equip")])
    index = ProjectSymbolIndex([fb_type, gvl])

    result = resolve_dotted_reference("GVL_A.Instancia.MembroQueNaoExiste", None, index)

    assert result.state == "partially_resolved"
    assert result.resolved_prefix == "GVL_A.Instancia"
    assert result.unresolved_suffix == "MembroQueNaoExiste"
    assert result.resolved_symbol == "app/fb/0"
    assert result.reason == "member metadata unavailable"


# ---------------------------------------------------------------------------
# Ambiguidade: dois símbolos com mesmo nome no mesmo container.
# ---------------------------------------------------------------------------


def test_two_symbols_with_same_name_in_same_container_is_ambiguous() -> None:
    fb_type = _fb(
        "app/fb/0",
        "FB_Equip",
        variables=[
            VariableDeclaration(name="Dup", declared_type="BOOL", scope="VAR"),
            VariableDeclaration(name="Dup", declared_type="BOOL", scope="VAR_INPUT"),
        ],
    )
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "FB_Equip")])
    index = ProjectSymbolIndex([fb_type, gvl])

    result = resolve_dotted_reference("GVL_A.Instancia.Dup", None, index)

    assert result.state == "ambiguous"
    assert result.resolved_symbol is None


# ---------------------------------------------------------------------------
# Cadeia incompleta (termina em '.' sem identificador seguinte) -- captura
# já lida com isso sem exceção; aqui confirmamos que a RESOLUÇÃO também não
# lança, tratando o "nome" resultante (sem trailing dot, pois a captura de
# statement_parser nunca inclui um '.' final sem identificador -- este teste
# simula defensivamente uma chamada direta com texto malformado).
# ---------------------------------------------------------------------------


def test_malformed_trailing_dot_does_not_raise() -> None:
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "DINT")])
    index = ProjectSymbolIndex([gvl])

    result = resolve_dotted_reference("GVL_A.Instancia.", None, index)

    assert result.state in ("resolved", "partially_resolved", "unresolved", "ambiguous")


# ---------------------------------------------------------------------------
# Ambiguidade de GVL propaga corretamente através da cadeia generalizada.
# ---------------------------------------------------------------------------


def test_ambiguous_gvl_name_propagates() -> None:
    gvl1 = _gvl("app/gvl/0", "GVL_Dup", variables=[_var("X", "DINT")])
    gvl2 = _gvl("app/gvl/1", "GVL_Dup", variables=[_var("X", "DINT")])
    index = ProjectSymbolIndex([gvl1, gvl2])

    result = resolve_dotted_reference("GVL_Dup.X", None, index)

    assert result.state == "ambiguous"
    assert result.resolved_symbol is None

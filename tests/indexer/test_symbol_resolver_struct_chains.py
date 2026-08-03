"""Testes da FASE 2: generalização da caminhada de cadeia pontuada
(`symbol_resolver._container_from_declared_type`/`_walk_remaining_segments`)
para reconhecer STRUCT/alias (`TypeSymbol`, ver `models.py`/`dut_parser.py`)
como "container" navegável, além de FUNCTION_BLOCK (já suportado).

Nomes de fixtures são SINTÉTICOS, diferentes dos nomes reais do cliente
(estes aparecem apenas na validação real contra o export, não em testes)."""

from __future__ import annotations

from mastertool_bridge.indexer.models import (
    PouSymbol,
    TypeSymbol,
    VariableDeclaration,
)
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


def _struct_member(name: str, declared_type: str) -> VariableDeclaration:
    return VariableDeclaration(name=name, declared_type=declared_type, scope="STRUCT_MEMBER")


def _struct(node_id: str, name: str, members: list[VariableDeclaration]) -> TypeSymbol:
    return TypeSymbol(node_id=node_id, name=name, kind="struct", file="f.st", members=members)


def _alias(node_id: str, name: str, target: str) -> TypeSymbol:
    return TypeSymbol(node_id=node_id, name=name, kind="alias", file="f.st", alias_target=target)


def _unknown_type(node_id: str, name: str) -> TypeSymbol:
    return TypeSymbol(node_id=node_id, name=name, kind="unknown", file="f.st")


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


def _fb(node_id: str, name: str, variables: list[VariableDeclaration] | None = None) -> PouSymbol:
    return PouSymbol(
        node_id=node_id,
        pou_kind="FUNCTION_BLOCK",
        name=name,
        file="f.st",
        variables=variables or [],
    )


# ---------------------------------------------------------------------------
# GVL.Instancia.Membro onde Instancia é STRUCT conhecido -> resolved.
# ---------------------------------------------------------------------------


def test_gvl_struct_instance_member_resolved() -> None:
    motor = _struct(
        "app/type/Motor", "Motor", members=[_struct_member("RetornoDisjuntor", "BOOL")]
    )
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "Motor")])
    index = ProjectSymbolIndex([gvl], type_symbols=[motor])

    result = resolve_dotted_reference("GVL_A.Instancia.RetornoDisjuntor", None, index)

    assert result.state == "resolved"
    assert result.resolved_symbol == "app/type/Motor"
    assert result.variable is not None
    assert result.variable.name == "RetornoDisjuntor"


# ---------------------------------------------------------------------------
# STRUCT aninhado: GVL.Instancia.Sub.Valor onde Sub é membro STRUCT de outro
# STRUCT (2+ níveis de STRUCT, recursivo).
# ---------------------------------------------------------------------------


def test_gvl_nested_struct_member_two_levels_resolved() -> None:
    inner = _struct("app/type/Inner", "Inner", members=[_struct_member("Valor", "INT")])
    outer = _struct("app/type/Outer", "Outer", members=[_struct_member("Sub", "Inner")])
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "Outer")])
    index = ProjectSymbolIndex([gvl], type_symbols=[inner, outer])

    result = resolve_dotted_reference("GVL_A.Instancia.Sub.Valor", None, index)

    assert result.state == "resolved"
    assert result.resolved_symbol == "app/type/Inner"
    assert result.variable is not None
    assert result.variable.name == "Valor"


# ---------------------------------------------------------------------------
# Array de STRUCTs com índice -> resolved, índice ignorado na busca mas
# preservado no texto (não-regressão do padrão já existente para FB).
# ---------------------------------------------------------------------------


def test_gvl_array_of_structs_with_index_resolved() -> None:
    motor = _struct(
        "app/type/Motor", "Motor", members=[_struct_member("RetornoDisjuntor", "BOOL")]
    )
    gvl = _gvl(
        "app/gvl/0",
        "GVL_A",
        variables=[
            _var(
                "ArrayDeStructs",
                "ARRAY[0..3] OF Motor",
                is_array=True,
                array_dimensions=[("0", "3")],
            )
        ],
    )
    index = ProjectSymbolIndex([gvl], type_symbols=[motor])

    result = resolve_dotted_reference("GVL_A.ArrayDeStructs[2].RetornoDisjuntor", None, index)

    assert result.state == "resolved"
    assert result.resolved_symbol == "app/type/Motor"
    assert result.variable is not None
    assert result.variable.name == "RetornoDisjuntor"


# ---------------------------------------------------------------------------
# STRUCT alcançado via ALIAS simples -> resolved.
# ---------------------------------------------------------------------------


def test_gvl_struct_via_simple_alias_resolved() -> None:
    motor = _struct(
        "app/type/Motor", "Motor", members=[_struct_member("RetornoDisjuntor", "BOOL")]
    )
    alias_type = _alias("app/type/MotorAlias", "MotorAlias", target="Motor")
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "MotorAlias")])
    index = ProjectSymbolIndex([gvl], type_symbols=[motor, alias_type])

    result = resolve_dotted_reference("GVL_A.Instancia.RetornoDisjuntor", None, index)

    assert result.state == "resolved"
    assert result.resolved_symbol == "app/type/Motor"
    assert result.variable is not None
    assert result.variable.name == "RetornoDisjuntor"


# ---------------------------------------------------------------------------
# STRUCT alcançado via ALIAS encadeado (2+ níveis) -> resolved.
# ---------------------------------------------------------------------------


def test_gvl_struct_via_chained_alias_resolved() -> None:
    motor = _struct(
        "app/type/Motor", "Motor", members=[_struct_member("RetornoDisjuntor", "BOOL")]
    )
    alias_b = _alias("app/type/B", "B", target="Motor")
    alias_a = _alias("app/type/A", "A", target="B")
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "A")])
    index = ProjectSymbolIndex([gvl], type_symbols=[motor, alias_b, alias_a])

    result = resolve_dotted_reference("GVL_A.Instancia.RetornoDisjuntor", None, index)

    assert result.state == "resolved"
    assert result.resolved_symbol == "app/type/Motor"
    assert result.variable is not None
    assert result.variable.name == "RetornoDisjuntor"


# ---------------------------------------------------------------------------
# ALIAS cíclico como declared_type de uma variável -> partially_resolved
# (nunca trava).
# ---------------------------------------------------------------------------


def test_cyclic_alias_declared_type_is_partially_resolved_never_hangs() -> None:
    alias_a = _alias("app/type/A", "A", target="B")
    alias_b = _alias("app/type/B", "B", target="A")
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "A")])
    index = ProjectSymbolIndex([gvl], type_symbols=[alias_a, alias_b])

    result = resolve_dotted_reference("GVL_A.Instancia.QualquerMembro", None, index)

    assert result.state == "partially_resolved"
    assert result.resolved_prefix == "GVL_A.Instancia"
    assert result.unresolved_suffix == "QualquerMembro"


# ---------------------------------------------------------------------------
# Tipo STRUCT inexistente (nome não bate com nada em types_by_name) ->
# partially_resolved (mesma regra já existente de "tipo desconhecido").
# ---------------------------------------------------------------------------


def test_unknown_struct_type_name_is_partially_resolved() -> None:
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "TipoQueNaoExiste")])
    index = ProjectSymbolIndex([gvl])

    result = resolve_dotted_reference("GVL_A.Instancia.Membro", None, index)

    assert result.state == "partially_resolved"
    assert result.resolved_prefix == "GVL_A.Instancia"
    assert result.unresolved_suffix == "Membro"


# ---------------------------------------------------------------------------
# Membro inexistente DENTRO de um STRUCT conhecido -> partially_resolved,
# reason="member_not_found_in_indexed_type" (EXATO).
# ---------------------------------------------------------------------------


def test_nonexistent_member_in_known_struct_has_exact_reason() -> None:
    motor = _struct(
        "app/type/Motor", "Motor", members=[_struct_member("RetornoDisjuntor", "BOOL")]
    )
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "Motor")])
    index = ProjectSymbolIndex([gvl], type_symbols=[motor])

    result = resolve_dotted_reference("GVL_A.Instancia.MembroInexistente", None, index)

    assert result.state == "partially_resolved"
    assert result.resolved_prefix == "GVL_A.Instancia"
    assert result.unresolved_suffix == "MembroInexistente"
    assert result.reason == "member_not_found_in_indexed_type"
    assert result.resolved_symbol == "app/type/Motor"


# ---------------------------------------------------------------------------
# Dois TypeSymbol com mesmo nome usados como declared_type -> ambiguous
# (nunca escolhe arbitrariamente).
# ---------------------------------------------------------------------------


def test_two_type_symbols_with_same_name_is_ambiguous_not_resolved() -> None:
    dup1 = _struct("app/type/Dup1", "Dup", members=[_struct_member("X", "BOOL")])
    dup2 = _struct("app/type/Dup2", "Dup", members=[_struct_member("X", "BOOL")])
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "Dup")])
    index = ProjectSymbolIndex([gvl], type_symbols=[dup1, dup2])

    result = resolve_dotted_reference("GVL_A.Instancia.X", None, index)

    # Container ambíguo -> None -> segmento seguinte não pode ser
    # confirmado -> partially_resolved (nunca escolhe um dos dois Dup
    # arbitrariamente, e nunca vira "ambiguous" propriamente pois a
    # ambiguidade está no TIPO do container, não no NOME do membro
    # encontrado dentro de um container único).
    assert result.state == "partially_resolved"
    assert result.resolved_prefix == "GVL_A.Instancia"
    assert result.unresolved_suffix == "X"


# ---------------------------------------------------------------------------
# Tipo "unknown" (enum) como declared_type, cadeia tentando acessar membro
# dele -> partially_resolved (nunca unresolved).
# ---------------------------------------------------------------------------


def test_unknown_kind_type_enum_member_access_is_partially_resolved() -> None:
    enum_type = _unknown_type("app/type/Estado", "E_Estado")
    gvl = _gvl("app/gvl/0", "GVL_A", variables=[_var("Instancia", "E_Estado")])
    index = ProjectSymbolIndex([gvl], type_symbols=[enum_type])

    result = resolve_dotted_reference("GVL_A.Instancia.Membro", None, index)

    assert result.state == "partially_resolved"
    assert result.resolved_prefix == "GVL_A.Instancia"
    assert result.unresolved_suffix == "Membro"
    assert result.reason is not None
    assert "enum" in result.reason.lower()


# ---------------------------------------------------------------------------
# Amostragem obrigatória, replicando os dados reais do projeto (nomes
# sintéticos aqui, os reais são validados contra o export em separado):
# GVL.Instancia.Membro onde Instancia é STRUCT com um único membro BOOL.
# ---------------------------------------------------------------------------


def test_sampled_pattern_var_motores_style_resolved() -> None:
    motor = _struct(
        "app/type/Motor", "Motor", members=[_struct_member("RetornoDisjuntor", "BOOL")]
    )
    gvl = _gvl("app/gvl/0", "VarMotores", variables=[_var("MT01", "Motor")])
    index = ProjectSymbolIndex([gvl], type_symbols=[motor])

    result = resolve_dotted_reference("VarMotores.MT01.RetornoDisjuntor", None, index)

    assert result.state == "resolved"


def test_sampled_pattern_var_tpv_style_resolved() -> None:
    valvulas = _struct(
        "app/type/Valvulas", "Valvulas", members=[_struct_member("Sensor_Aberta", "BOOL")]
    )
    gvl = _gvl("app/gvl/0", "VarTPV", variables=[_var("V6", "Valvulas")])
    index = ProjectSymbolIndex([gvl], type_symbols=[valvulas])

    result = resolve_dotted_reference("VarTPV.V6.Sensor_Aberta", None, index)

    assert result.state == "resolved"


# ---------------------------------------------------------------------------
# Não-regressão: FUNCTION_BLOCK como container continua funcionando
# EXATAMENTE como antes -- reexecuta uma amostra de
# test_symbol_resolver_nested_gvl_chains.py neste arquivo para reforço, mas
# a suíte completa daquele arquivo já é rodada sem alteração (ver PROOF).
# ---------------------------------------------------------------------------


def test_fb_container_non_regression_still_works_alongside_struct_types() -> None:
    fb_type = _fb("app/fb/0", "FB_Equip", variables=[_var("Estado", "BOOL", scope="VAR")])
    motor = _struct(
        "app/type/Motor", "Motor", members=[_struct_member("RetornoDisjuntor", "BOOL")]
    )
    gvl = _gvl(
        "app/gvl/0",
        "GVL_A",
        variables=[_var("Instancia", "FB_Equip"), _var("Motor1", "Motor")],
    )
    index = ProjectSymbolIndex([fb_type, gvl], type_symbols=[motor])

    fb_result = resolve_dotted_reference("GVL_A.Instancia.Estado", None, index)
    struct_result = resolve_dotted_reference("GVL_A.Motor1.RetornoDisjuntor", None, index)

    assert fb_result.state == "resolved"
    assert fb_result.resolved_symbol == "app/fb/0"
    assert struct_result.state == "resolved"
    assert struct_result.resolved_symbol == "app/type/Motor"

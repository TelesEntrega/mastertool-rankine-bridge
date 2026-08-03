"""Testes de mastertool_bridge.indexer.symbol_resolver."""

from __future__ import annotations

from mastertool_bridge.indexer.models import PouSymbol, VariableDeclaration
from mastertool_bridge.indexer.symbol_resolver import (
    ProjectSymbolIndex,
    owner_node_id_from_node_id,
    resolve_dotted_reference,
    resolve_identifier,
)


def _var(name: str, declared_type: str, scope: str) -> VariableDeclaration:
    return VariableDeclaration(name=name, declared_type=declared_type, scope=scope)


def test_owner_node_id_from_node_id_strips_stmt_suffix() -> None:
    assert owner_node_id_from_node_id("application/prg/0#stmt3") == "application/prg/0"


def test_owner_node_id_from_node_id_without_hash_returns_itself() -> None:
    assert owner_node_id_from_node_id("application/prg/0") == "application/prg/0"


# ---------------------------------------------------------------------------
# Nível 1/2: variável/parâmetro local da POU atual.
# ---------------------------------------------------------------------------


def test_level_1_2_resolves_local_variable() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("xStart", "BOOL", "VAR")],
    )
    index = ProjectSymbolIndex([prg])

    result = resolve_identifier("xStart", prg, index)

    assert result.state == "resolved"
    assert result.rule_applied == "local_variable"
    assert result.resolved_symbol == "application/prg/0"
    assert result.variable is not None
    assert result.variable.name == "xStart"


def test_level_1_2_resolves_pou_parameter() -> None:
    fb = PouSymbol(
        node_id="application/fb/0",
        pou_kind="FUNCTION_BLOCK",
        name="FB_Foo",
        file="f.st",
        variables=[_var("xIn", "BOOL", "VAR_INPUT")],
    )
    index = ProjectSymbolIndex([fb])

    result = resolve_identifier("xIn", fb, index)

    assert result.state == "resolved"
    assert result.rule_applied == "pou_parameter"


def test_level_1_2_shadowing_between_scopes_is_ambiguous_not_error() -> None:
    # Mesmo nome declarado em VAR_INPUT e também em VAR dentro da MESMA POU
    # (shadowing intra-POU) -> ambiguous, nunca erro de parsing nem palpite.
    fb = PouSymbol(
        node_id="application/fb/0",
        pou_kind="FUNCTION_BLOCK",
        name="FB_Foo",
        file="f.st",
        variables=[
            _var("dup", "BOOL", "VAR_INPUT"),
            _var("dup", "BOOL", "VAR"),
        ],
    )
    index = ProjectSymbolIndex([fb])

    result = resolve_identifier("dup", fb, index)

    assert result.state == "ambiguous"
    assert result.rule_applied == "pou_local_shadowing"
    assert result.resolved_symbol is None or result.resolved_symbol == "application/fb/0"


def test_shadowing_local_variable_wins_over_gvl_same_name() -> None:
    """Variável local com mesmo nome de uma variável de GVL deve resolver
    como local, NUNCA a GVL, sem ambiguidade espúria."""
    gvl = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="GvlMotores",
        file="f.st",
        variables=[_var("MT01", "Motor", "VAR_GLOBAL")],
        is_qualified_only=False,
    )
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("MT01", "BOOL", "VAR")],
    )
    index = ProjectSymbolIndex([gvl, prg])

    result = resolve_identifier("MT01", prg, index)

    assert result.state == "resolved"
    assert result.rule_applied == "local_variable"
    assert result.resolved_symbol == "application/prg/0"
    assert result.variable.declared_type == "BOOL"


# ---------------------------------------------------------------------------
# Nível 3: instância de FUNCTION_BLOCK.
# ---------------------------------------------------------------------------


def test_level_3_resolves_fb_instance() -> None:
    fb_type = PouSymbol(
        node_id="application/fb/0", pou_kind="FUNCTION_BLOCK", name="FB_Timer", file="f.st"
    )
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("fbTimer", "FB_Timer", "VAR")],
    )
    index = ProjectSymbolIndex([fb_type, prg])

    result = resolve_identifier("fbTimer", prg, index)

    assert result.state == "resolved"
    assert result.rule_applied == "fb_instance"
    assert result.fb_type_symbol is not None
    assert result.fb_type_symbol.node_id == "application/fb/0"


# ---------------------------------------------------------------------------
# Nível 4: GVL explícita.
# ---------------------------------------------------------------------------


def test_level_4_resolves_gvl_explicit_reference() -> None:
    gvl = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="GvlDiag",
        file="f.st",
        variables=[_var("DG_Contador", "DINT", "VAR_GLOBAL")],
        is_qualified_only=True,
    )
    index = ProjectSymbolIndex([gvl])

    result = resolve_dotted_reference("GvlDiag.DG_Contador", None, index)

    assert result.state == "resolved"
    assert result.rule_applied == "gvl_explicit"
    assert result.resolved_symbol == "application/gvl/0"


def test_level_4_gvl_explicit_variable_not_found_is_partially_resolved() -> None:
    """Decisão deliberada (contrato do commit "nested GVL instance member
    references"): GVL conhecida mas variável pedida ausente dela é tratado
    de forma UNIFORME com qualquer outro "membro não encontrado no
    container atual" da cadeia generalizada -- vira partially_resolved com
    resolved_prefix="GvlDiag" (a GVL, prefixo confirmado) e
    unresolved_suffix="NaoExiste", em vez de um "unresolved" totalmente
    silencioso. Isso é mais granular/honesto (a GVL EXISTE, só o membro
    específico não) e mantém consistência com o caso de membro ausente em
    FUNCTION_BLOCK (ex. GVL_A.Instancia.MembroQueNaoExiste)."""
    gvl = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="GvlDiag",
        file="f.st",
        variables=[_var("DG_Contador", "DINT", "VAR_GLOBAL")],
    )
    index = ProjectSymbolIndex([gvl])

    result = resolve_dotted_reference("GvlDiag.NaoExiste", None, index)

    assert result.state == "partially_resolved"
    assert result.resolved_prefix == "GvlDiag"
    assert result.unresolved_suffix == "NaoExiste"
    assert result.resolved_symbol == "application/gvl/0"


# ---------------------------------------------------------------------------
# Nível 5: GVL implícita.
# ---------------------------------------------------------------------------


def test_level_5_resolves_gvl_implicit_unique_match() -> None:
    gvl = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="GvlDiag",
        file="f.st",
        variables=[_var("DG_Contador", "DINT", "VAR_GLOBAL")],
        is_qualified_only=False,
    )
    index = ProjectSymbolIndex([gvl])

    result = resolve_identifier("DG_Contador", None, index)

    assert result.state == "resolved"
    assert result.rule_applied == "gvl_implicit"
    assert result.resolved_symbol == "application/gvl/0"


def test_level_5_qualified_only_gvl_does_not_participate_in_implicit_lookup() -> None:
    gvl = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="GvlMotores",
        file="f.st",
        variables=[_var("MT01", "Motor", "VAR_GLOBAL")],
        is_qualified_only=True,
    )
    index = ProjectSymbolIndex([gvl])

    result = resolve_identifier("MT01", None, index)

    assert result.state == "unresolved"
    assert result.resolved_symbol is None


def test_level_5_ambiguous_when_two_non_qualified_gvls_share_variable_name() -> None:
    gvl1 = PouSymbol(
        node_id="application/gvl/0",
        pou_kind="GVL",
        name="GvlA",
        file="f.st",
        variables=[_var("DG_Contador", "DINT", "VAR_GLOBAL")],
        is_qualified_only=False,
    )
    gvl2 = PouSymbol(
        node_id="application/gvl/1",
        pou_kind="GVL",
        name="GvlB",
        file="f.st",
        variables=[_var("DG_Contador", "DINT", "VAR_GLOBAL")],
        is_qualified_only=False,
    )
    index = ProjectSymbolIndex([gvl1, gvl2])

    result = resolve_identifier("DG_Contador", None, index)

    assert result.state == "ambiguous"
    assert result.rule_applied == "gvl_implicit"
    assert set(result.candidates) == {"application/gvl/0", "application/gvl/1"}
    assert result.resolved_symbol is None


# ---------------------------------------------------------------------------
# Nível 6: tipo.
# ---------------------------------------------------------------------------


def test_level_6_resolves_type_reference_by_pou_name() -> None:
    fb_type = PouSymbol(
        node_id="application/fb/0", pou_kind="FUNCTION_BLOCK", name="FB_Timer", file="f.st"
    )
    index = ProjectSymbolIndex([fb_type])

    result = resolve_identifier("FB_Timer", None, index)

    assert result.state == "resolved"
    assert result.rule_applied == "type_reference"
    assert result.resolved_symbol == "application/fb/0"


def test_level_6_resolves_type_reference_by_declared_type_usage() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("someMotor", "Motor", "VAR")],
    )
    index = ProjectSymbolIndex([prg])

    result = resolve_identifier("Motor", None, index)

    assert result.state == "resolved"
    assert result.rule_applied == "type_reference"
    # "Motor" não é o nome de nenhuma POU/GVL conhecida — apenas um tipo
    # usado; não há PouSymbol concreto para apontar.
    assert result.resolved_symbol is None


def test_level_6_resolves_type_reference_by_array_base_type() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[
            VariableDeclaration(
                name="aiSetpoints",
                declared_type="ARRAY[0..3] OF INT",
                scope="VAR",
                is_array=True,
                array_dimensions=[("0", "3")],
            )
        ],
    )
    index = ProjectSymbolIndex([prg])

    result = resolve_identifier("INT", None, index)

    assert result.state == "resolved"
    assert result.rule_applied == "type_reference"


# ---------------------------------------------------------------------------
# Nível 7: unresolved — NUNCA um palpite.
# ---------------------------------------------------------------------------


def test_level_7_unknown_identifier_is_unresolved_never_a_guess() -> None:
    prg = PouSymbol(
        node_id="application/prg/0",
        pou_kind="PROGRAM",
        name="MainPrg",
        file="f.st",
        variables=[_var("xStart", "BOOL", "VAR")],
    )
    index = ProjectSymbolIndex([prg])

    result = resolve_identifier("NomeCompletamenteDesconhecido", prg, index)

    assert result.state == "unresolved"
    assert result.resolved_symbol is None
    assert result.candidates == []


def test_dotted_reference_to_unknown_namespaced_type_is_unresolved() -> None:
    """ex.: 'LibDataTypes.QUALITY' — tipo namespaced desconhecido para o
    projeto não deve ser inventado como resolvido."""
    index = ProjectSymbolIndex([])

    result = resolve_dotted_reference("LibDataTypes.QUALITY", None, index)

    assert result.state == "unresolved"
    assert result.resolved_symbol is None

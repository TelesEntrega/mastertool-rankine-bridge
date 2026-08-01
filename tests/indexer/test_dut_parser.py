"""Testes de mastertool_bridge.indexer.dut_parser."""

from __future__ import annotations

from mastertool_bridge.indexer.dut_parser import parse_dut_declaration


def test_struct_simples_membro_escalar_unico() -> None:
    text = "TYPE ST_Simples :\nSTRUCT\n\tHabilitado : BOOL;\nEND_STRUCT\nEND_TYPE\n"
    symbol, diags = parse_dut_declaration(text, "f.st", "n1", "ST_Simples")

    assert symbol is not None
    assert symbol.kind == "struct"
    assert symbol.name == "ST_Simples"
    assert not diags.has_errors
    assert len(symbol.members) == 1
    assert symbol.members[0].name == "Habilitado"
    assert symbol.members[0].declared_type == "BOOL"
    assert symbol.members[0].scope == "STRUCT_MEMBER"


def test_struct_com_membro_tipo_definido_pelo_usuario_texto_cru() -> None:
    text = (
        "TYPE PrgValvulasExemplo :\n"
        "STRUCT\n"
        "\tAbre : BOOL;\n"
        "\tPrgParametrosExemplo : PrgPrgPrgParametrosExemploExemploAuxExemplo;\n"
        "END_STRUCT\n"
        "END_TYPE\n"
    )
    symbol, diags = parse_dut_declaration(text, "f.st", "n2", "PrgValvulasExemplo")

    assert symbol is not None
    assert not diags.has_errors
    param_member = next(m for m in symbol.members if m.name == "PrgParametrosExemplo")
    assert param_member.declared_type == "PrgPrgPrgParametrosExemploExemploAuxExemplo"
    assert param_member.is_array is False


def test_struct_com_array_de_outro_struct() -> None:
    text = (
        "TYPE ContainerMotores :\n"
        "STRUCT\n"
        "\tMotores : ARRAY[1..8] OF ST_Equipamento;\n"
        "END_STRUCT\n"
        "END_TYPE\n"
    )
    symbol, diags = parse_dut_declaration(text, "f.st", "n3", "ContainerMotores")

    assert symbol is not None
    assert not diags.has_errors
    member = symbol.members[0]
    assert member.is_array is True
    assert member.array_dimensions == [("1", "8")]
    assert member.declared_type == "ARRAY[1..8] OF ST_Equipamento"


def test_alias_simples() -> None:
    text = "TYPE X : Y;\nEND_TYPE\n"
    symbol, diags = parse_dut_declaration(text, "f.st", "n4", "X")

    assert symbol is not None
    assert symbol.kind == "alias"
    assert symbol.alias_target == "Y"
    assert symbol.members == []
    assert not diags.has_errors


def test_enum_real_kind_unknown_com_diagnostic_informativo() -> None:
    text = (
        "TYPE E_EstadoExemplo :\n"
        "(\n"
        "    AGUARDANDO_INICIO           := 0,\n"
        "    LIGA_BOMBA_VACUO            := 1\n"
        ") INT;\n"
        "END_TYPE\n"
    )
    symbol, diags = parse_dut_declaration(text, "f.st", "n5", "E_EstadoExemplo")

    assert symbol is not None
    assert symbol.kind == "unknown"
    assert symbol.members == []
    assert not diags.has_errors
    codes = {d.code for d in diags.diagnostics}
    assert "enum_type_not_supported_yet" in codes


def test_comentarios_fim_de_linha_e_linha_inteira_nunca_viram_membro() -> None:
    text = (
        "TYPE Equipamento :\n"
        "STRUCT\n"
        "\tLiga_Auto\t:\tBOOL; // comentario\n"
        "//\tSelecao_Modo\t:\tINT;\n"
        "\t//Rampa_Acel : INT;\n"
        "\tRetornoDisjuntor\t:\tBOOL;\t// comentario\n"
        "END_STRUCT\n"
        "END_TYPE\n"
    )
    symbol, diags = parse_dut_declaration(text, "f.st", "n6", "Equipamento")

    assert symbol is not None
    assert not diags.has_errors
    names = [m.name for m in symbol.members]
    assert names == ["Liga_Auto", "RetornoDisjuntor"]


def test_declaracao_incompleta_falta_end_struct_sem_excecao() -> None:
    text = "TYPE Incompleto :\nSTRUCT\n\tA : BOOL;\nEND_TYPE\n"
    symbol, diags = parse_dut_declaration(text, "f.st", "n7", "Incompleto")

    # Best-effort: não lança, reporta o que conseguiu.
    assert diags.has_errors or symbol is not None


def test_declaracao_incompleta_falta_end_type_sem_excecao() -> None:
    text = "TYPE SemFim :\nSTRUCT\n\tA : BOOL;\nEND_STRUCT\n"
    symbol, diags = parse_dut_declaration(text, "f.st", "n8", "SemFim")

    assert symbol is not None
    assert symbol.kind == "struct"
    assert len(symbol.members) == 1


def test_membro_sem_ponto_e_virgula_nao_lanca_excecao() -> None:
    text = "TYPE Quebrado :\nSTRUCT\n\tA : BOOL\n\tB : INT;\nEND_STRUCT\nEND_TYPE\n"
    symbol, diags = parse_dut_declaration(text, "f.st", "n9", "Quebrado")

    assert symbol is not None
    assert symbol.kind == "struct"
    # Não lança exceção -- resultado best-effort, com diagnostics.
    assert isinstance(diags.diagnostics, list)


def test_texto_vazio_retorna_none_com_dut_header_not_found() -> None:
    symbol, diags = parse_dut_declaration("", "f.st", "n10", "Vazio")

    assert symbol is None
    codes = {d.code for d in diags.diagnostics}
    assert "dut_header_not_found" in codes


def test_texto_nao_comeca_com_type_retorna_none() -> None:
    text = "PROGRAM MainPrg\nEND_PROGRAM\n"
    symbol, diags = parse_dut_declaration(text, "f.st", "n11", "Algo")

    assert symbol is None
    codes = {d.code for d in diags.diagnostics}
    assert "dut_header_not_found" in codes


def test_dois_type_symbol_mesmo_nome_ambos_validos() -> None:
    text_a = "TYPE Duplicado :\nSTRUCT\n\tA : BOOL;\nEND_STRUCT\nEND_TYPE\n"
    text_b = "TYPE Duplicado :\nSTRUCT\n\tB : INT;\nEND_STRUCT\nEND_TYPE\n"

    symbol_a, diags_a = parse_dut_declaration(text_a, "a.st", "na", "Duplicado")
    symbol_b, diags_b = parse_dut_declaration(text_b, "b.st", "nb", "Duplicado")

    assert symbol_a is not None and symbol_b is not None
    assert symbol_a.name == symbol_b.name == "Duplicado"
    assert not diags_a.has_errors
    assert not diags_b.has_errors


def test_tipo_autorreferenciado_struct_com_membro_do_proprio_tipo() -> None:
    text = (
        "TYPE No :\n"
        "STRUCT\n"
        "\tProximo : No;\n"
        "\tValor : INT;\n"
        "END_STRUCT\n"
        "END_TYPE\n"
    )
    symbol, diags = parse_dut_declaration(text, "f.st", "n12", "No")

    assert symbol is not None
    assert not diags.has_errors
    proximo = next(m for m in symbol.members if m.name == "Proximo")
    assert proximo.declared_type == "No"


def test_localizacao_linha_coluna_type_symbol_e_membros() -> None:
    text = "TYPE ST_Loc :\nSTRUCT\n\tCampo : BOOL;\nEND_STRUCT\nEND_TYPE\n"
    symbol, _diags = parse_dut_declaration(text, "f.st", "n13", "ST_Loc")

    assert symbol is not None
    assert symbol.location is not None
    assert symbol.location.line == 1
    member = symbol.members[0]
    assert member.location is not None
    assert member.location.line == 3


def test_saida_deterministica_mesma_entrada_duas_vezes() -> None:
    text = (
        "TYPE Equipamento :\n"
        "STRUCT\n"
        "\tLiga_Auto : BOOL;\n"
        "\tRetornoDisjuntor : BOOL;\n"
        "END_STRUCT\n"
        "END_TYPE\n"
    )
    symbol1, diags1 = parse_dut_declaration(text, "f.st", "n14", "Equipamento")
    symbol2, diags2 = parse_dut_declaration(text, "f.st", "n14", "Equipamento")

    assert symbol1 is not None and symbol2 is not None
    assert symbol1.to_dict() == symbol2.to_dict()
    assert diags1.to_list() == diags2.to_list()


def test_inicializador_preservado_cru() -> None:
    text = "TYPE ST_Init :\nSTRUCT\n\tContador : INT := 10;\nEND_STRUCT\nEND_TYPE\n"
    symbol, diags = parse_dut_declaration(text, "f.st", "n15", "ST_Init")

    assert symbol is not None
    assert not diags.has_errors
    assert symbol.members[0].initializer_raw == "10"

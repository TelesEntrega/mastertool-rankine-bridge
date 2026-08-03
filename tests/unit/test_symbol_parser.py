from mastertool_bridge.analysis.symbol_parser import parse_declaration


def _read(path):
    return path.read_text(encoding="utf-8")


def test_function_block_header(sample_project_dir):
    decl = _read(sample_project_dir / "objects" / "function-blocks"
                 / "ControleMotor" / "declaration.st")
    symbol = parse_declaration(decl)
    assert symbol.name == "ControleMotor"
    assert symbol.kind == "function_block"
    assert not symbol.uncertainties


def test_var_blocks_and_types(sample_project_dir):
    decl = _read(sample_project_dir / "objects" / "function-blocks"
                 / "ControleMotor" / "declaration.st")
    symbol = parse_declaration(decl)
    inputs = symbol.variables_in_block("VAR_INPUT")
    outputs = symbol.variables_in_block("VAR_OUTPUT")
    assert [v.name for v in inputs] == ["xLiga", "xDesliga", "rSetpoint"]
    assert [v.name for v in outputs] == ["xMotor", "xFalha"]
    setpoint = next(v for v in inputs if v.name == "rSetpoint")
    assert setpoint.var_type == "REAL"
    assert setpoint.initial_value == "10.0"


def test_gvl_retain_array_and_address(sample_project_dir):
    decl = _read(sample_project_dir / "objects" / "gvls"
                 / "GVL_Maquina" / "declaration.st")
    symbol = parse_declaration(decl, "GVL_Maquina")
    assert symbol.kind == "gvl"
    by_name = {v.name: v for v in symbol.variables}
    assert by_name["aiPressoes"].is_array
    assert by_name["xValvulaSaida"].address == "%QX0.0"
    assert by_name["iContadorCiclos"].is_retain
    assert not by_name["xLigaMotor"].is_retain


def test_extends_in_out_and_persistent(fixtures_dir):
    decl = _read(fixtures_dir / "sample_pous" / "FB_Valvula.declaration.st")
    symbol = parse_declaration(decl)
    assert symbol.kind == "function_block"
    assert symbol.extends == "FB_EquipamentoBase"
    inout = symbol.variables_in_block("VAR_IN_OUT")
    assert [v.name for v in inout] == ["stComando"]
    persistent = [v for v in symbol.variables if v.is_persistent]
    assert [v.name for v in persistent] == ["iAcionamentos"]


def test_unparseable_line_registers_uncertainty():
    decl = "FUNCTION_BLOCK FB_X\nVAR\n    123 tipo estranho !!;\nEND_VAR\n"
    symbol = parse_declaration(decl)
    assert symbol.uncertainties
    assert symbol.kind == "function_block"


def test_program_header(sample_project_dir):
    decl = _read(sample_project_dir / "objects" / "programs"
                 / "MainPrg" / "declaration.st")
    symbol = parse_declaration(decl)
    assert symbol.kind == "program"
    assert {v.name for v in symbol.variables} == {"fbMotor", "i"}

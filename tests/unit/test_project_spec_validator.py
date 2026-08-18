"""Testa `mastertool_bridge.spec.validator` (Frente E, primeiro draft do
modelo declarativo `project_spec`). Suíte 100% offline: nenhum teste aqui
abre o MasterTool nem depende de IronPython — `validate_project_spec` é
CPython 3 puro, sem `jsonschema`.

Cobertura mínima exigida pelo contrato da frente: spec mínima válida; campo
desconhecido recusado em cada nível; nome IEC inválido; nome duplicado na
mesma família e entre famílias; referência inexistente; ciclo entre FBs;
linguagem como string "ST" recusada; GUID malformado recusado; ordem de
criação correta com dependências cruzadas; expected_diff correto; hashes de
texto corretos; entrada degenerada (None, lista, string) devolve problemas em
vez de levantar."""

import copy
import hashlib
import json

import pytest

from mastertool_bridge.spec.validator import (
    ST_LANGUAGE_GUID,
    ValidationResult,
    validate_project_spec,
)

from tests.support_spec import minimal_valid_spec


def _minimal_valid_spec():
    """Delegado a `tests/support_spec.py`.

    O corpo morava aqui e era importado por `test_spec_method_r3_1b`. Import
    de teste para teste amarra a publicação de um à do outro — ver o cabeçalho
    do módulo de apoio. Aqui fica só o nome que os testes deste arquivo usam.
    """
    return minimal_valid_spec()


# =============================================================================
# Spec mínima válida
# =============================================================================

def test_minimal_valid_spec_has_no_problems():
    result = validate_project_spec(_minimal_valid_spec())
    assert result.problems == []
    assert isinstance(result, ValidationResult)
    assert result.ok is True


def test_json_schema_file_is_parseable_json():
    """O deliverable 1 (project_spec.schema.json) precisa ser JSON válido
    mesmo não sendo usado por este validador em tempo de execução."""
    from pathlib import Path
    schema_path = (Path(__file__).resolve().parents[2] / "src" / "mastertool_bridge"
                   / "spec" / "project_spec.schema.json")
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    assert data["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "template" in data["properties"]


# =============================================================================
# Campo desconhecido, fail-closed, em cada nível
# =============================================================================

def test_unknown_field_rejected_at_root():
    spec = _minimal_valid_spec()
    spec["telepatia"] = True
    result = validate_project_spec(spec)
    assert any("telepatia" in p for p in result.problems)


@pytest.mark.parametrize("family", [
    "duts", "gvls", "functions", "function_blocks", "programs", "tasks", "libraries",
])
def test_unknown_field_rejected_in_each_family(family):
    spec = _minimal_valid_spec()
    spec[family][0]["campo_alienigena"] = 42
    result = validate_project_spec(spec)
    assert any("campo_alienigena" in p for p in result.problems), result.problems


def test_unknown_field_rejected_in_template():
    spec = _minimal_valid_spec()
    spec["template"]["extra"] = "nope"
    result = validate_project_spec(spec)
    assert any("template" in p and "extra" in p for p in result.problems)


def test_unknown_field_rejected_in_language_object():
    spec = _minimal_valid_spec()
    spec["programs"][0]["language"]["extra_key"] = "x"
    result = validate_project_spec(spec)
    assert any("language" in p and "extra_key" in p for p in result.problems)


# =============================================================================
# Nome IEC inválido
# =============================================================================

@pytest.mark.parametrize("bad_name", [
    "1StartsWithDigit", "has space", "has-dash", "", "PROGRAM", "var_global",
    "A" * 65,
])
def test_invalid_iec_name_rejected(bad_name):
    spec = _minimal_valid_spec()
    spec["programs"][0]["name"] = bad_name
    result = validate_project_spec(spec)
    assert any("programs" in p and ".name" in p for p in result.problems), result.problems


def test_valid_iec_name_with_underscore_prefix_accepted():
    spec = _minimal_valid_spec()
    spec["programs"][0]["name"] = "_PRG_VALID"
    spec["tasks"][0]["program_calls"] = ["_PRG_VALID"]
    result = validate_project_spec(spec)
    assert result.problems == []


# =============================================================================
# Nome duplicado — mesma família e entre famílias
# =============================================================================

def test_duplicate_name_within_same_family_rejected():
    spec = _minimal_valid_spec()
    second_dut = copy.deepcopy(spec["duts"][0])
    spec["duts"].append(second_dut)  # mesmo nome "ST_Point" duas vezes
    result = validate_project_spec(spec)
    assert any("ST_Point" in p and "duplicado" in p for p in result.problems)


def test_duplicate_name_across_families_rejected():
    spec = _minimal_valid_spec()
    # GVL com o mesmo nome de um DUT já existente -- mesmo container (Application).
    spec["gvls"].append({
        "name": "ST_Point",
        "declaration": "VAR_GLOBAL\nEND_VAR",
    })
    result = validate_project_spec(spec)
    assert any("ST_Point" in p and "conflita" in p for p in result.problems)


def test_tasks_and_libraries_do_not_conflict_with_application_namespace():
    """tasks/libraries vivem em containers próprios -- reusar um nome já
    usado por um DUT/GVL/PROGRAM não é conflito nestas duas famílias."""
    spec = _minimal_valid_spec()
    spec["tasks"][0]["name"] = "ST_Point"
    result = validate_project_spec(spec)
    assert result.problems == []


# =============================================================================
# Referência inexistente
# =============================================================================

def test_reference_to_nonexistent_object_in_uses_rejected():
    spec = _minimal_valid_spec()
    spec["programs"][0]["uses"] = ["FB_Counter", "GVL_AI_TESTE", "FB_NAO_EXISTE"]
    result = validate_project_spec(spec)
    assert any("FB_NAO_EXISTE" in p and "não existe" in p for p in result.problems)


def test_reference_to_object_created_later_rejected():
    """Um DUT não pode depender de uma GVL: GVL é criada DEPOIS na ordem de
    criação, então referenciá-la a partir de um DUT aponta para algo que
    ainda não existe no momento em que o DUT seria criado."""
    spec = _minimal_valid_spec()
    spec["duts"][0]["uses"] = ["GVL_AI_TESTE"]
    result = validate_project_spec(spec)
    assert any("GVL_AI_TESTE" in p for p in result.problems)


def test_task_program_call_to_nonexistent_program_rejected():
    spec = _minimal_valid_spec()
    spec["tasks"][0]["program_calls"] = ["PRG_FANTASMA"]
    result = validate_project_spec(spec)
    assert any("PRG_FANTASMA" in p and "não existe" in p for p in result.problems)


# =============================================================================
# Ciclo entre FBs/FUNCTIONs
# =============================================================================

def test_cycle_between_function_blocks_rejected():
    spec = _minimal_valid_spec()
    spec["function_blocks"] = [
        {
            "name": "FB_A",
            "language": {"guid": ST_LANGUAGE_GUID},
            "declaration": "FUNCTION_BLOCK FB_A\nEND_FUNCTION_BLOCK\n",
            "implementation": "",
            "uses": ["FB_B"],
        },
        {
            "name": "FB_B",
            "language": {"guid": ST_LANGUAGE_GUID},
            "declaration": "FUNCTION_BLOCK FB_B\nEND_FUNCTION_BLOCK\n",
            "implementation": "",
            "uses": ["FB_A"],
        },
    ]
    spec["programs"][0]["uses"] = ["FB_A", "GVL_AI_TESTE"]
    result = validate_project_spec(spec)
    assert any("ciclo inválido" in p and "FB_A" in p and "FB_B" in p
               for p in result.problems), result.problems


def test_no_false_positive_cycle_on_simple_dependency_chain():
    result = validate_project_spec(_minimal_valid_spec())
    assert not any("ciclo" in p for p in result.problems)


# =============================================================================
# Linguagem como string "ST" recusada / GUID malformado
# =============================================================================

def test_language_as_string_st_rejected():
    spec = _minimal_valid_spec()
    spec["programs"][0]["language"] = "ST"
    result = validate_project_spec(spec)
    assert any('"ST"' in p or "'ST'" in p for p in result.problems), result.problems
    assert any("Nullable<Guid>" in p for p in result.problems)


def test_language_guid_malformed_rejected():
    spec = _minimal_valid_spec()
    spec["programs"][0]["language"] = {"guid": "not-a-real-guid"}
    result = validate_project_spec(spec)
    assert any("guid" in p and "not-a-real-guid" in p for p in result.problems)


def test_language_guid_valid_format_accepted():
    spec = _minimal_valid_spec()
    result = validate_project_spec(spec)
    assert not any("language" in p for p in result.problems)


# =============================================================================
# Ordem de criação, com dependências cruzadas
# =============================================================================

def test_creation_order_follows_dut_gvl_function_fb_program_task_sequence():
    result = validate_project_spec(_minimal_valid_spec())
    assert result.problems == []

    families_in_order = [entry.split(":", 1)[0] for entry in result.creation_order
                          if not entry.startswith("program_call:")]
    # A primeira ocorrência de cada família preserva a sequência do contrato.
    first_seen = []
    for family in families_in_order:
        if family not in first_seen:
            first_seen.append(family)
    assert first_seen == ["duts", "gvls", "functions", "function_blocks",
                          "programs", "tasks"]

    assert "duts:ST_Point" in result.creation_order
    assert "gvls:GVL_AI_TESTE" in result.creation_order
    assert "functions:FUNC_Add" in result.creation_order
    assert "function_blocks:FB_Counter" in result.creation_order
    assert "programs:PRG_AI_TESTE" in result.creation_order
    assert "tasks:MainTask" in result.creation_order
    # Program call é o último passo, depois de a task existir.
    assert result.creation_order[-1] == "program_call:MainTask->PRG_AI_TESTE"


def test_creation_order_is_deterministic_across_runs():
    spec = _minimal_valid_spec()
    order_1 = validate_project_spec(spec).creation_order
    order_2 = validate_project_spec(copy.deepcopy(spec)).creation_order
    assert order_1 == order_2


# =============================================================================
# expected_diff
# =============================================================================

def test_expected_diff_counts_match_spec():
    result = validate_project_spec(_minimal_valid_spec())
    assert result.expected_diff == {
        "duts": 1,
        "gvls": 1,
        "functions": 1,
        "function_blocks": 1,
        "programs": 1,
        "tasks": 1,
        "libraries": 1,
        "program_calls": 1,
    }


def test_expected_diff_counts_multiple_program_calls():
    spec = _minimal_valid_spec()
    spec["tasks"][0]["program_calls"] = ["PRG_AI_TESTE", "PRG_AI_TESTE"]
    # Chamar o mesmo PROGRAM duas vezes na mesma task é uma decisão de
    # contagem (cada entrada em program_calls é uma ligação persistente
    # própria), não uma duplicata de NOME de objeto -- então não reprova.
    result = validate_project_spec(spec)
    assert result.problems == []
    assert result.expected_diff["program_calls"] == 2


# =============================================================================
# text_hashes
# =============================================================================

def test_text_hashes_match_sha256_of_declared_text():
    spec = _minimal_valid_spec()
    result = validate_project_spec(spec)
    assert result.problems == []

    expected_gvl_hash = hashlib.sha256(
        spec["gvls"][0]["declaration"].encode("utf-8")).hexdigest()
    assert result.text_hashes["gvls:GVL_AI_TESTE:declaration"] == expected_gvl_hash

    expected_prg_decl_hash = hashlib.sha256(
        spec["programs"][0]["declaration"].encode("utf-8")).hexdigest()
    expected_prg_impl_hash = hashlib.sha256(
        spec["programs"][0]["implementation"].encode("utf-8")).hexdigest()
    assert result.text_hashes["programs:PRG_AI_TESTE:declaration"] == expected_prg_decl_hash
    assert result.text_hashes["programs:PRG_AI_TESTE:implementation"] == expected_prg_impl_hash

    # DUT/GVL não têm implementation -- não deve haver chave para ela.
    assert "duts:ST_Point:implementation" not in result.text_hashes
    assert "gvls:GVL_AI_TESTE:implementation" not in result.text_hashes


def test_text_hash_of_empty_implementation_is_sha256_of_empty_string():
    """O SHA-256 da string vazia é um fato medido em docs/31 -- vale
    registrar aqui porque é fácil confundir 'vazio medido' com 'não lido'."""
    spec = _minimal_valid_spec()
    spec["function_blocks"][0]["implementation"] = ""
    result = validate_project_spec(spec)
    assert result.problems == []
    assert result.text_hashes["function_blocks:FB_Counter:implementation"] == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")


# =============================================================================
# Entrada degenerada nunca levanta
# =============================================================================

@pytest.mark.parametrize("degenerate", [None, [], ["a", "b"], "not-a-dict", 42, 3.14, True])
def test_degenerate_input_returns_problems_instead_of_raising(degenerate):
    result = validate_project_spec(degenerate)
    assert isinstance(result, ValidationResult)
    assert result.problems != []
    assert result.creation_order == []
    assert result.expected_diff == {}
    assert result.text_hashes == {}


def test_missing_template_reports_problem_not_crash():
    spec = _minimal_valid_spec()
    del spec["template"]
    result = validate_project_spec(spec)
    assert any("template" in p for p in result.problems)


def test_wrong_schema_version_rejected():
    spec = _minimal_valid_spec()
    spec["schema_version"] = 999
    result = validate_project_spec(spec)
    assert any("schema_version" in p for p in result.problems)


def test_family_entry_that_is_not_a_dict_reports_problem_not_crash():
    spec = _minimal_valid_spec()
    spec["gvls"].append("not-an-object")
    result = validate_project_spec(spec)
    assert any("gvls" in p and "dict" in p for p in result.problems)


def test_family_that_is_not_a_list_reports_problem_not_crash():
    spec = _minimal_valid_spec()
    spec["programs"] = {"name": "oops"}
    result = validate_project_spec(spec)
    assert any("programs" in p and "lista" in p for p in result.problems)

"""Testa `mastertool_bridge.planner` — o planner declarativo que transforma
`project_spec` num plano de autoria literal.

Suíte 100% offline: nenhum teste aqui abre o MasterTool, importa IronPython ou
executa processo. O que está sob teste é a parte difícil da frente —
**ordenação, ciclos e determinismo** — e a restrição de desenho que decide o
formato do plano: o executor tem chamadas LITERAIS, logo o conjunto de
`operation` precisa ser fechado e não pode crescer sozinho.

Grupos de teste, na ordem em que aparecem:

  1. conjunto fechado de `operation` (a prova, em quatro ângulos)
  2. normalização textual (equivalência com a primitiva já congelada)
  3. plano feliz e conformidade com o JSON Schema
  4. ordenação topológica, empates e ordem canônica de família
  5. ciclos — com o CAMINHO, não só "há ciclo"
  6. determinismo byte a byte e invariância a permutação
  7. allowlist DERIVADA e lacunas de medição
  8. validações offline e entrada degenerada
  9. spec grande sintética (20 DUTs, 20 GVLs, 50 FBs, 10 PROGRAMs)
"""

from __future__ import annotations

import ast
import io
import json
import os
import sys
from pathlib import Path

import pytest

from mastertool_bridge.planner import planner as planner_module
from mastertool_bridge.planner.planner import (
    EXECUTOR_CONTRACT,
    FAMILY_RANK,
    OBJECT_FAMILIES,
    PLAN_KIND,
    PLAN_OPERATIONS,
    PLAN_SCHEMA_VERSION,
    PROJECT_TARGET,
    TARGET_KINDS,
    build_authoring_plan,
    canonical_json,
    normalize_authoring_text,
    plan_to_json,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANNER_PY = REPO_ROOT / "src" / "mastertool_bridge" / "planner" / "planner.py"
PLAN_SCHEMA_PATH = (REPO_ROOT / "src" / "mastertool_bridge" / "planner"
                    / "authoring_plan.schema.json")

_MASTERTOOL_DIR = str(REPO_ROOT / "scripts" / "mastertool")
if _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)

from common import authoring_text as frozen_authoring_text  # noqa: E402
from common import safety  # noqa: E402

ST_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"
TEMPLATE = {"id": "TemplateExemplo-v1", "sha256": "a" * 64}


# --- material de teste --------------------------------------------------------

def minimal_spec() -> dict:
    """Spec pequena, mas com dependência em toda direção permitida."""
    return {
        "schema_version": 1,
        "template": dict(TEMPLATE),
        "duts": [
            {"name": "ST_Motor", "kind": "STRUCT",
             "declaration": "TYPE ST_Motor :\nSTRUCT\n x : INT;\nEND_STRUCT\nEND_TYPE\n"},
        ],
        "gvls": [
            {"name": "GVL_AI_TESTE",
             "declaration": "{attribute 'qualified_only'}\nVAR_GLOBAL\n"
                            "    g_xTesteCriacao : BOOL;\nEND_VAR",
             "uses": ["ST_Motor"]},
        ],
        "functions": [
            {"name": "FUN_Soma", "language": {"guid": ST_GUID},
             "declaration": "FUNCTION FUN_Soma : INT\nVAR_INPUT\n a : INT;\nEND_VAR",
             "implementation": "FUN_Soma := a;",
             "return_type": "INT", "uses": ["ST_Motor"]},
        ],
        "function_blocks": [
            {"name": "FB_AI_CONTADOR", "language": {"guid": ST_GUID},
             "declaration": "FUNCTION_BLOCK FB_AI_CONTADOR\nVAR\n n : INT;\nEND_VAR",
             "implementation": "n := n + 1;",
             "uses": ["FUN_Soma", "GVL_AI_TESTE"]},
        ],
        "programs": [
            {"name": "PRG_AI_TESTE", "language": {"guid": ST_GUID},
             "declaration": "PROGRAM PRG_AI_TESTE\nVAR\n xLocal : BOOL;\nEND_VAR",
             "implementation": "xLocal := GVL_AI_TESTE.g_xTesteCriacao;",
             "uses": ["FB_AI_CONTADOR"]},
        ],
    }


def field_proven_spec() -> dict:
    """Spec restrita as operacoes PROVADAS contra o produto real: GVL,
    PROGRAM, texto, `save_as`, `build` e a chamada idiomatica dentro da POU
    de perfil (docs/41).

    Existe porque `minimal_spec` tem DUT, FUNCTION e FUNCTION_BLOCK, cujas
    APIs estao catalogadas mas NUNCA foram exercidas numa cadeia que
    persistiu e compilou. Usar `minimal_spec` para afirmar "executavel" era
    o proprio fail-open escrito como teste.

    `MainTask` vem com `existing: True`: ela JA existe no template, e todas
    as execucoes reais a reusaram.
    """
    return {
        "schema_version": 1,
        "template": dict(TEMPLATE),
        "gvls": [
            {"name": "GVL_AI_TESTE",
             "declaration": "{attribute 'qualified_only'}\nVAR_GLOBAL\n"
                            "    g_xTesteCriacao : BOOL;\nEND_VAR"},
        ],
        "programs": [
            {"name": "PRG_AI_TESTE", "language": {"guid": ST_GUID},
             "declaration": "PROGRAM PRG_AI_TESTE\nVAR\n xLocal : BOOL;\nEND_VAR",
             "implementation": "xLocal := GVL_AI_TESTE.g_xTesteCriacao;"},
        ],
        "tasks": [{"name": "MainTask", "existing": True,
                   "program_calls": ["PRG_AI_TESTE"]}],
    }


def spec_with_tasks() -> dict:
    """As DUAS formas de vincular, porque elas não são intercambiáveis.

    `MainTask` recebe a chamada dentro de `UserPrg` — o caminho que o fabricante
    pede. `TaskDiagnostico`, criada aqui, recebe o programa na própria lista de
    POUs: `UserPrg` roda pela cadeia da `MainTask`, e chegar por ali a uma task
    nova ligaria o programa ao ciclo errado.
    """
    spec = minimal_spec()
    spec["tasks"] = [
        {"name": "MainTask", "program_calls": ["PRG_AI_TESTE"]},
        # Com tempo declarado: sem isso a task nasceria a `t#20ms` com
        # prioridade 1, mais rapida e mais prioritaria que a MainTask
        # (docs/48 secao 4).
        {"name": "TaskDiagnostico", "program_calls": ["PRG_AI_TESTE"],
         "kind_of_task": "Cyclic", "interval": "t#500ms", "priority": 20},
    ]
    spec["libraries"] = [{"name": "Standard"}]
    return spec


def big_spec() -> dict:
    """20 DUTs, 20 GVLs, 50 FUNCTION_BLOCKs, 10 PROGRAMs, com dependências
    cruzadas em todas as direções permitidas.

    Existe para pegar dois defeitos que uma spec pequena esconde: ordem que
    depende de iteração de `dict`/`set` (só aparece com muitos empates
    simultâneos) e ordenação de família que "funciona por acaso" porque só há
    um objeto por família.
    """
    # DUTs em QUATRO cadeias de cinco: quatro raízes ficam prontas ao mesmo
    # tempo já na primeira rodada da topológica. Uma cadeia única esconderia o
    # empate inicial — e é exatamente ali que iteração de `set` decide a ordem.
    duts = [{"name": f"ST_D{index:02d}", "kind": "STRUCT",
             "declaration": f"TYPE ST_D{index:02d} :\nSTRUCT\n v : INT;\nEND_STRUCT\nEND_TYPE",
             "uses": [] if index % 5 == 0 else [f"ST_D{index - 1:02d}"]}
            for index in range(20)]
    # Um quarto das GVLs e um terço dos FBs sem dependência nenhuma: entram no
    # conjunto de prontos da PRIMEIRA rodada, junto com as raízes de DUT, o que
    # também põe a ordem canônica de família sob pressão.
    gvls = [{"name": f"GVL_G{index:02d}",
             "declaration": f"VAR_GLOBAL\n g_n{index:02d} : INT;\nEND_VAR",
             "uses": [] if index % 4 == 0 else [f"ST_D{index % 20:02d}"]}
            for index in range(20)]
    function_blocks = [
        {"name": f"FB_F{index:02d}", "language": {"guid": ST_GUID},
         "declaration": f"FUNCTION_BLOCK FB_F{index:02d}\nVAR\n n : INT;\nEND_VAR",
         "implementation": f"n := n + {index};",
         "uses": ([] if index % 3 == 0
                  else [f"ST_D{index % 20:02d}"]
                  + ([f"FB_F{index - 25:02d}"] if index >= 25 else []))}
        for index in range(50)]
    programs = [
        {"name": f"PRG_P{index:02d}", "language": {"guid": ST_GUID},
         "declaration": f"PROGRAM PRG_P{index:02d}\nVAR\n b : BOOL;\nEND_VAR",
         "implementation": f"b := GVL_G{index:02d}.g_n{index:02d} > 0;",
         "uses": [f"GVL_G{index:02d}", f"FB_F{index:02d}"]}
        for index in range(10)]
    return {"schema_version": 1, "template": dict(TEMPLATE), "duts": duts,
            "gvls": gvls, "function_blocks": function_blocks,
            "programs": programs}


def _plan_of(spec: dict) -> dict:
    result = build_authoring_plan(spec)
    assert result.problems == [], result.problems
    assert result.ok
    assert result.plan is not None
    return result.plan


def _planner_ast() -> ast.Module:
    return ast.parse(io.open(PLANNER_PY, encoding="utf-8").read())


# =============================================================================
# 1. O conjunto FECHADO de `operation`
# =============================================================================
#
# Quatro ângulos, porque um só não prova nada: o literal congelado impede que o
# conjunto cresça sem revisão humana; o contrato do executor impede que um
# valor exista sem alguém declarar o que ele consome; o enum do schema impede
# que o artefato aceite algo que o módulo não emite; e a varredura de AST
# impede que um nome de operação seja FABRICADO a partir de dados em tempo de
# execução, que é o buraco por onde o dispatch dinâmico voltaria.

# Literal congelado. Mexer no planner sem mexer AQUI reprova — que é
# exatamente o ponto: o conjunto não pode crescer sozinho.
FROZEN_PLAN_OPERATIONS = (
    "create_dut",
    "create_gvl",
    "create_function",
    "create_function_block",
    "create_program",
    "create_task",
    "create_program_call",
    "bind_program_to_task",
    "configure_task",
    "replace",
    "save_as",
    "reopen",
    "build",
    "verify",
)


def test_operation_set_is_frozen_literal_and_ordered():
    assert PLAN_OPERATIONS == FROZEN_PLAN_OPERATIONS
    assert len(set(PLAN_OPERATIONS)) == len(PLAN_OPERATIONS)


def test_operation_constants_are_string_literals_at_module_level():
    """Cada `OPERATION_*` é uma constante de string literal — nunca uma
    expressão. Um nome montado por concatenação poderia mudar com o ambiente."""
    tree = _planner_ast()
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.startswith("OPERATION_"):
                assert isinstance(node.value, ast.Constant), (
                    f"{target.id} não é literal de string")
                assert isinstance(node.value.value, str)
                found[target.id] = node.value.value
    assert sorted(found.values()) == sorted(FROZEN_PLAN_OPERATIONS)


def test_executor_contract_covers_exactly_the_operation_set():
    """Se um valor de `operation` pudesse existir sem entrada no contrato do
    executor, ele chegaria ao executor sem ninguém ter escrito o ramo dele."""
    assert set(EXECUTOR_CONTRACT) == set(PLAN_OPERATIONS)
    for operation, contract in EXECUTOR_CONTRACT.items():
        assert set(contract) == {"mastertool_operation", "mutating",
                                 "cataloged", "field_proven", "evidence"}
        assert isinstance(contract["mutating"], bool)
        assert isinstance(contract["cataloged"], bool)
        assert isinstance(contract["field_proven"], bool)
        # Ter nome de API mutável <=> mutar E estar catalogado.
        #
        # UMA exceção, e ela é a classe de mutação nova: `configure_task` muta
        # e é catalogada, e mesmo assim não tem `mastertool_operation`. O que
        # ela consome não é MÉTODO — são escritas de propriedade, com prefixo
        # `set:`, e elas vêm do PASSO (`task_properties`), porque uma spec que
        # configura só o intervalo não deve autorizar as outras três. Um nome
        # único aqui seria a abertura ampla com outro nome.
        if operation == "configure_task":
            assert contract["mastertool_operation"] is None
            assert contract["mutating"] is True
            assert contract["cataloged"] is True
            continue
        has_api = contract["mastertool_operation"] is not None
        assert has_api == (contract["mutating"] and contract["cataloged"]), operation
        # Provado em campo EXIGE catalogado: exercer o que nao esta no
        # registro literal seria ter inventado a API no caminho.
        if contract["field_proven"]:
            assert contract["cataloged"], operation


def test_cataloged_apis_are_subset_of_the_literal_mutating_registry():
    """Toda API que o plano pode consumir está no registro LITERAL de
    `scripts/mastertool/common/safety.py` (docs/27 §7). Nome fora do registro
    é API inventada."""
    used = {contract["mastertool_operation"]
            for contract in EXECUTOR_CONTRACT.values()
            if contract["mastertool_operation"] is not None}
    assert used <= set(safety.MASTERTOOL_MUTATING_OPERATIONS)


def test_plan_schema_enum_matches_the_operation_set_exactly():
    schema = json.loads(io.open(PLAN_SCHEMA_PATH, encoding="utf-8").read())
    enum = schema["$defs"]["step"]["properties"]["operation"]["enum"]
    assert tuple(enum) == PLAN_OPERATIONS
    target_enum = schema["$defs"]["step"]["properties"]["target_kind"]["enum"]
    assert tuple(target_enum) == TARGET_KINDS


def test_operation_values_never_come_from_data():
    """Varredura de AST: todo argumento `operation=` de chamada é uma
    REFERÊNCIA a uma constante `OPERATION_*`.

    Nunca um literal solto (que escaparia ao conjunto fechado), nunca uma
    f-string, concatenação, índice ou chamada (que fabricaria o nome a partir
    de dados em tempo de execução).
    """
    tree = _planner_ast()
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "operation":
                continue
            value = keyword.value
            if not (isinstance(value, ast.Name)
                    and value.id.startswith("OPERATION_")):
                offenders.append(f"linha {keyword.value.lineno}")
    assert not offenders, f"`operation=` fabricado a partir de dados: {offenders}"


def test_only_one_place_builds_a_step_record():
    """Existe exatamente UM dicionário literal com a chave "operation" — o de
    `_step`. Dois construtores de passo divergiriam em silêncio."""
    tree = _planner_ast()
    builders = [node for node in ast.walk(tree)
                if isinstance(node, ast.Dict)
                and any(isinstance(key, ast.Constant) and key.value == "operation"
                        for key in node.keys if key is not None)]
    assert len(builders) == 1


def test_planner_has_no_dynamic_dispatch_primitives():
    """Sem `getattr`, `eval`, `exec`, `__import__`, `globals()`, `locals()`.

    O planner não precisa de nenhum deles, e a presença de qualquer um abriria
    a porta para escolher comportamento por string — o oposto exato do que
    este desenho promete ao executor.
    """
    tree = _planner_ast()
    forbidden = {"getattr", "setattr", "eval", "exec", "__import__",
                 "globals", "locals", "vars"}
    hits = [f"{node.func.id}@{node.lineno}" for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in forbidden]
    assert not hits, f"primitiva de dispatch dinâmico no planner: {hits}"


def test_every_operation_in_the_closed_set_is_actually_reachable():
    """Nenhum membro do conjunto é decorativo: uma spec que exercita todas as
    famílias emite todos os doze. Um valor que nunca é emitido seria permissão
    aberta sem uso — o inverso do defeito, e igualmente indesejável."""
    plan = _plan_of(spec_with_tasks())
    emitted = {step["operation"] for step in plan["steps"]}
    assert emitted == set(PLAN_OPERATIONS)


def test_plan_never_carries_the_final_text():
    """Herdado de `probes/32`: um plano que carregasse o texto final
    autorizaria a si mesmo a escrever qualquer coisa. O plano leva hash e
    `source_location`; o texto vem da spec, presa por `spec_sha256`."""
    spec = spec_with_tasks()
    plan = _plan_of(spec)
    serialized = canonical_json(plan)
    for family in OBJECT_FAMILIES:
        for obj in spec.get(family, []):
            for field_name in ("declaration", "implementation"):
                text = obj.get(field_name)
                if isinstance(text, str) and len(text) > 8:
                    assert text not in serialized, (
                        f"o plano transporta o texto de {obj['name']}.{field_name}")


# =============================================================================
# 2. Normalização textual
# =============================================================================

NORMALIZATION_CORPUS = [
    "", "\n", "\r\n", "\r", "a", "a\n", "a\n\n", "a\r\nb\r\n",
    "a  \nb\t\n", "  a  ", "a\n\n\n", "linha\v\f \nfim   \n",
    "VAR_GLOBAL\r\n    g : BOOL;\r\nEND_VAR\r\n",
    "{attribute 'qualified_only'}\nVAR_GLOBAL\nEND_VAR",
    "áéí\r\nçã \n", "\n\n", "x\n \n", None, 3, True, [], {},
]


@pytest.mark.parametrize("value", NORMALIZATION_CORPUS)
def test_normalization_matches_the_frozen_primitive(value):
    """A regra é a MESMA de `scripts/mastertool/common/authoring_text`.

    Ela é reescrita no planner porque `scripts/mastertool/` é árvore
    IronPython não empacotada, e importá-la de `src/` acoplaria a camada host
    a um caminho inexistente numa instalação. Este teste é a proteção contra
    deriva: as duas implementações são comparadas caractere a caractere.
    """
    assert normalize_authoring_text(value) == \
        frozen_authoring_text.normalize_text(value)


def test_normalization_ignores_exactly_one_trailing_newline():
    assert normalize_authoring_text("a\n") == "a"
    assert normalize_authoring_text("a\n\n") == "a\n"
    assert normalize_authoring_text("a\r\n") == "a"


# =============================================================================
# 3. Plano feliz e conformidade com o JSON Schema
# =============================================================================

def test_minimal_spec_produces_a_plan():
    plan = _plan_of(minimal_spec())
    assert plan["kind"] == PLAN_KIND
    assert plan["schema_version"] == PLAN_SCHEMA_VERSION


def test_schema_version_is_an_integer_not_the_probe_string():
    """Convenção da camada `src/` (docs/19 §7): inteiro. A string "1.0" é da
    família de artefatos de probe/export e ligá-las casaria contratos que
    precisam evoluir separados."""
    plan = _plan_of(minimal_spec())
    assert isinstance(plan["schema_version"], int)
    assert not isinstance(plan["schema_version"], bool)
    assert plan["schema_version"] != "1.0"
    assert isinstance(PLAN_SCHEMA_VERSION, int)


@pytest.mark.parametrize("factory", [minimal_spec, spec_with_tasks, big_spec])
def test_plan_conforms_to_its_own_json_schema(factory):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(io.open(PLAN_SCHEMA_PATH, encoding="utf-8").read())
    jsonschema.validate(instance=_plan_of(factory()), schema=schema)


def test_sequences_are_one_based_and_contiguous():
    plan = _plan_of(spec_with_tasks())
    assert [step["sequence"] for step in plan["steps"]] == \
        list(range(1, len(plan["steps"]) + 1))


def test_pipeline_ends_with_save_as_reopen_build_verify_in_that_order():
    plan = _plan_of(spec_with_tasks())
    tail = [step["operation"] for step in plan["steps"][-4:]]
    assert tail == ["save_as", "reopen", "build", "verify"]
    for step in plan["steps"][-4:]:
        assert step["target_name"] == PROJECT_TARGET
        assert step["target_kind"] == "project"


def test_replace_steps_follow_the_create_steps_and_point_back_to_them():
    """Todo `replace` sabe QUAL passo criou o objeto que ele sobrescreve.

    É o que permite o executor provar que está escrevendo num objeto que ele
    mesmo acabou de criar, e não num preexistente do template — o texto de
    esqueleto pós-`create_*` não está medido, então `expected_before_sha256` é
    honestamente nulo e a garantia tem de vir daqui.
    """
    plan = _plan_of(minimal_spec())
    by_sequence = {step["sequence"]: step for step in plan["steps"]}
    for step in plan["steps"]:
        if step["operation"] != "replace":
            continue
        assert step["expected_before_kind"] == "created_in_this_plan"
        assert step["expected_before_sha256"] is None
        origin = by_sequence[step["created_by_sequence"]]
        assert origin["sequence"] < step["sequence"]
        assert origin["target_name"] == step["target_name"]
        assert origin["operation"].startswith("create_")


def test_declaration_is_replaced_before_implementation():
    plan = _plan_of(minimal_spec())
    order = [step["target_kind"] for step in plan["steps"]
             if step["operation"] == "replace"
             and step["target_name"] == "FB_AI_CONTADOR"]
    assert order == ["function_block_declaration",
                     "function_block_implementation"]


def test_text_hashes_carry_raw_and_normalized():
    """O veredito de igualdade é o normalizado; o bruto prova que uma
    divergência, quando existe, é só de fim de linha."""
    spec = minimal_spec()
    plan = _plan_of(spec)
    entry = plan["text_hashes"]["gvls:GVL_AI_TESTE:declaration"]
    text = spec["gvls"][0]["declaration"]
    assert entry["raw_sha256"] == planner_module.sha256_of_text(text)
    assert entry["normalized_sha256"] == planner_module.sha256_of_text(
        normalize_authoring_text(text))


def test_expected_tree_and_expected_diff_agree_with_the_steps():
    plan = _plan_of(spec_with_tasks())
    tree = plan["expected_tree"]
    diff = plan["expected_diff"]
    creates = [step["target_name"] for step in plan["steps"]
               if step["operation"].startswith("create_")
               and step["target_kind"] in OBJECT_FAMILIES_SINGULAR]
    assert tree["persistent_additions"] == creates
    assert diff["total_steps"] == len(plan["steps"])
    assert diff["text_replacements"] == len(tree["text_replacements"])
    assert diff["program_calls"] == len(tree["program_call_additions"])
    assert diff["tasks"] == len(tree["task_additions"])
    assert diff["mutating_steps"] == sum(
        1 for step in plan["steps"]
        if EXECUTOR_CONTRACT[step["operation"]]["mutating"])
    assert tree["library_preconditions"] == ["Standard"]


OBJECT_FAMILIES_SINGULAR = ("dut", "gvl", "function", "function_block", "program")


def test_libraries_are_precondition_not_mutation():
    """DECISÃO deste slice: nenhum passo chama `add_library`. A ordem canônica
    do contrato não tem passo de biblioteca, e ampliar a superfície mutável por
    conveniência é o que docs/30 recusou ao deixar `create_pou` de fora."""
    plan = _plan_of(spec_with_tasks())
    assert "add_library" not in plan["required_allowlist"]
    assert plan["expected_tree"]["library_preconditions"] == ["Standard"]


# =============================================================================
# 4. Ordenação topológica, empates e ordem canônica de família
# =============================================================================

def test_family_order_is_canonical_even_without_dependencies():
    """DUTs -> GVLs -> FUNCTIONs -> FBs -> PROGRAMs, mesmo quando NADA depende
    de nada: a ordem canônica não é consequência das dependências."""
    spec = {
        "schema_version": 1, "template": dict(TEMPLATE),
        "duts": [{"name": "ST_Z", "kind": "STRUCT", "declaration": "d"}],
        "gvls": [{"name": "GVL_A", "declaration": "d"}],
        "functions": [{"name": "FUN_A", "language": {"guid": ST_GUID},
                       "declaration": "d", "implementation": "i",
                       "return_type": "INT"}],
        "function_blocks": [{"name": "FB_A", "language": {"guid": ST_GUID},
                             "declaration": "d", "implementation": "i"}],
        "programs": [{"name": "PRG_A", "language": {"guid": ST_GUID},
                      "declaration": "d", "implementation": "i"}],
    }
    plan = _plan_of(spec)
    assert plan["creation_order"] == [
        "duts:ST_Z", "gvls:GVL_A", "functions:FUN_A",
        "function_blocks:FB_A", "programs:PRG_A"]


def test_ties_are_broken_by_family_rank_then_name_never_by_dict_order():
    """O CRITÉRIO explícito de desempate, exercitado onde ele é o único fator.

    Nove FBs sem dependência nenhuma entre si: todos ficam prontos ao mesmo
    tempo. A ordem tem de ser exatamente a de `(rank da família, nome)` — e os
    nomes são inseridos na spec em ordem embaralhada de propósito, para que
    "sair na ordem de inserção" reprove.
    """
    names = ["FB_M", "FB_a", "FB_C", "FB_Z", "FB_b", "FB_A", "FB_x", "FB_D",
             "FB_Y"]
    spec = {
        "schema_version": 1, "template": dict(TEMPLATE),
        "function_blocks": [{"name": name, "language": {"guid": ST_GUID},
                             "declaration": "d", "implementation": "i"}
                            for name in names],
    }
    plan = _plan_of(spec)
    # `sorted` de str compara por ponto de código: maiúsculas antes de
    # minúsculas. O critério é esse, e é declarado — não "ordem alfabética
    # humana", que seria ambígua.
    assert plan["creation_order"] == [f"function_blocks:{name}"
                                      for name in sorted(names)]
    assert sorted(names) != names, "o corpus precisa estar fora de ordem"


def test_sort_key_is_family_rank_then_name():
    assert planner_module._sort_key("duts", "B") < planner_module._sort_key("duts", "a")
    assert planner_module._sort_key("duts", "z") < planner_module._sort_key("gvls", "A")
    assert FAMILY_RANK == {"duts": 0, "gvls": 1, "functions": 2,
                           "function_blocks": 3, "programs": 4}


def test_dependencies_always_precede_dependents():
    plan = _plan_of(big_spec())
    position = {key: index for index, key in enumerate(plan["creation_order"])}
    spec = big_spec()
    for family in OBJECT_FAMILIES:
        for obj in spec.get(family, []):
            for used in obj.get("uses", []):
                for candidate_family in OBJECT_FAMILIES:
                    key = f"{candidate_family}:{used}"
                    if key in position:
                        assert position[key] < position[f"{family}:{obj['name']}"]
                        break


def test_long_dependency_chain_is_ordered_by_dependency_not_by_name():
    """Cadeia `ST_D19 -> ST_D18 -> ... -> ST_D00`: a dependência manda, e o
    nome só desempata quem já está pronto."""
    plan = _plan_of(big_spec())
    duts = [key for key in plan["creation_order"] if key.startswith("duts:")]
    assert duts == [f"duts:ST_D{index:02d}" for index in range(20)]


# =============================================================================
# 5. Ciclos — com o CAMINHO
# =============================================================================

def _cycle_problems(spec: dict) -> list[str]:
    result = build_authoring_plan(spec)
    assert result.plan is None, "spec com ciclo não pode produzir plano"
    return [problem for problem in result.problems
            if "ciclo de dependência no grafo de criação" in problem]


def test_cycle_between_function_blocks_is_reported_with_the_full_path():
    spec = minimal_spec()
    spec["function_blocks"] = [
        {"name": "FB_A", "language": {"guid": ST_GUID}, "declaration": "d",
         "implementation": "i", "uses": ["FB_B"]},
        {"name": "FB_B", "language": {"guid": ST_GUID}, "declaration": "d",
         "implementation": "i", "uses": ["FB_C"]},
        {"name": "FB_C", "language": {"guid": ST_GUID}, "declaration": "d",
         "implementation": "i", "uses": ["FB_A"]},
    ]
    spec["programs"][0]["uses"] = []
    problems = _cycle_problems(spec)
    assert len(problems) == 1
    assert ("function_blocks:FB_A -> function_blocks:FB_B -> "
            "function_blocks:FB_C -> function_blocks:FB_A") in problems[0]


def test_cycle_among_duts_is_detected_too():
    """O grafo do planner cobre TODAS as famílias. O validador da spec só olha
    FUNCTIONs/FBs; um `STRUCT` que se aninha em si mesmo passaria por lá."""
    spec = {
        "schema_version": 1, "template": dict(TEMPLATE),
        "duts": [
            {"name": "ST_A", "kind": "STRUCT", "declaration": "d",
             "uses": ["ST_B"]},
            {"name": "ST_B", "kind": "STRUCT", "declaration": "d",
             "uses": ["ST_A"]},
        ],
    }
    problems = _cycle_problems(spec)
    assert len(problems) == 1
    assert "duts:ST_A -> duts:ST_B -> duts:ST_A" in problems[0]


def test_self_dependency_is_a_cycle_of_length_one():
    spec = {
        "schema_version": 1, "template": dict(TEMPLATE),
        "function_blocks": [{"name": "FB_S", "language": {"guid": ST_GUID},
                             "declaration": "d", "implementation": "i",
                             "uses": ["FB_S"]}],
    }
    problems = _cycle_problems(spec)
    assert len(problems) == 1
    assert "function_blocks:FB_S -> function_blocks:FB_S" in problems[0]


def test_two_disjoint_cycles_are_both_reported_each_with_its_path():
    spec = {
        "schema_version": 1, "template": dict(TEMPLATE),
        "function_blocks": [
            {"name": "FB_A", "language": {"guid": ST_GUID}, "declaration": "d",
             "implementation": "i", "uses": ["FB_B"]},
            {"name": "FB_B", "language": {"guid": ST_GUID}, "declaration": "d",
             "implementation": "i", "uses": ["FB_A"]},
            {"name": "FB_Y", "language": {"guid": ST_GUID}, "declaration": "d",
             "implementation": "i", "uses": ["FB_Z"]},
            {"name": "FB_Z", "language": {"guid": ST_GUID}, "declaration": "d",
             "implementation": "i", "uses": ["FB_Y"]},
        ],
    }
    problems = _cycle_problems(spec)
    assert len(problems) == 2
    assert "function_blocks:FB_A -> function_blocks:FB_B -> function_blocks:FB_A" \
        in problems[0]
    assert "function_blocks:FB_Y -> function_blocks:FB_Z -> function_blocks:FB_Y" \
        in problems[1]


def test_same_cycle_is_not_reported_twice_by_different_entry_points():
    """Percorrer o mesmo ciclo por duas portas de entrada não são dois
    achados. A representação canônica (rotacionada para o menor nó) deduplica
    sem perder o caminho."""
    spec = {
        "schema_version": 1, "template": dict(TEMPLATE),
        "function_blocks": [
            {"name": "FB_A", "language": {"guid": ST_GUID}, "declaration": "d",
             "implementation": "i", "uses": ["FB_B"]},
            {"name": "FB_B", "language": {"guid": ST_GUID}, "declaration": "d",
             "implementation": "i", "uses": ["FB_A"]},
            # entra no ciclo por fora, por um nó que vem depois na ordem
            {"name": "FB_C", "language": {"guid": ST_GUID}, "declaration": "d",
             "implementation": "i", "uses": ["FB_B"]},
        ],
    }
    assert len(_cycle_problems(spec)) == 1


def test_cycle_report_is_deterministic_across_permutations():
    base = [
        {"name": "FB_A", "language": {"guid": ST_GUID}, "declaration": "d",
         "implementation": "i", "uses": ["FB_B"]},
        {"name": "FB_B", "language": {"guid": ST_GUID}, "declaration": "d",
         "implementation": "i", "uses": ["FB_C"]},
        {"name": "FB_C", "language": {"guid": ST_GUID}, "declaration": "d",
         "implementation": "i", "uses": ["FB_A"]},
    ]
    reports = []
    for rotation in range(3):
        spec = {"schema_version": 1, "template": dict(TEMPLATE),
                "function_blocks": base[rotation:] + base[:rotation]}
        reports.append(_cycle_problems(spec))
    assert reports[0] == reports[1] == reports[2]


def test_cycle_never_yields_a_partial_plan():
    spec = minimal_spec()
    spec["function_blocks"].append(
        {"name": "FB_B", "language": {"guid": ST_GUID}, "declaration": "d",
         "implementation": "i", "uses": ["FB_AI_CONTADOR"]})
    spec["function_blocks"][0]["uses"] = ["FB_B"]
    result = build_authoring_plan(spec)
    assert result.plan is None
    assert not result.ok
    assert result.problems


# =============================================================================
# 6. Determinismo
# =============================================================================

def test_same_spec_produces_the_same_plan_byte_for_byte():
    for factory in (minimal_spec, spec_with_tasks, big_spec):
        first = plan_to_json(_plan_of(factory()))
        second = plan_to_json(_plan_of(factory()))
        assert first == second


def test_plan_sha256_is_stable_and_covers_the_plan_minus_itself():
    plan = _plan_of(big_spec())
    body = {key: value for key, value in plan.items() if key != "plan_sha256"}
    import hashlib
    assert plan["plan_sha256"] == hashlib.sha256(
        canonical_json(body).encode("utf-8")).hexdigest()
    assert plan["plan_sha256"] == _plan_of(big_spec())["plan_sha256"]


def test_plan_is_invariant_under_permutation_of_the_spec_arrays():
    """Reordenar as listas da spec não muda o plano — só `spec_sha256`, que é
    justamente o campo que amarra o plano ao arquivo literal da spec.

    Essa invariância é o que prova que a ordem NÃO veio da ordem de inserção
    do autor, e sim do critério declarado de desempate.
    """
    spec = big_spec()
    shuffled = big_spec()
    for family in OBJECT_FAMILIES:
        if family in shuffled:
            shuffled[family] = list(reversed(shuffled[family]))

    plan = _plan_of(spec)
    other = _plan_of(shuffled)
    assert plan["spec_sha256"] != other["spec_sha256"]
    del plan["spec_sha256"], plan["plan_sha256"]
    del other["spec_sha256"], other["plan_sha256"]
    assert plan_to_json(plan) == plan_to_json(other)


def test_plan_has_no_clock_or_environment_derived_field():
    """Nenhum campo volátil. O plano não tem `generated_at`, `timestamp`,
    caminho absoluto nem nome de máquina — se tivesse, "o mesmo plano" deixaria
    de significar "os mesmos bytes" e o determinismo viraria promessa vaga."""
    serialized = plan_to_json(_plan_of(spec_with_tasks()))
    for forbidden in ("generated_at", "started_at", "finished_at", "timestamp",
                      "hostname", "cwd", os.sep + os.sep):
        assert forbidden not in serialized


def test_repeated_builds_do_not_share_mutable_state():
    """Duas construções seguidas não podem se contaminar (lista/dict de módulo
    acumulando entre chamadas)."""
    first = _plan_of(spec_with_tasks())
    _plan_of(big_spec())
    third = _plan_of(spec_with_tasks())
    assert plan_to_json(first) == plan_to_json(third)


# =============================================================================
# 7. Allowlist DERIVADA e lacunas de medição
# =============================================================================

def test_required_allowlist_is_derived_from_the_steps():
    plan = _plan_of(minimal_spec())
    expected = sorted({
        EXECUTOR_CONTRACT[step["operation"]]["mastertool_operation"]
        for step in plan["steps"]
        if EXECUTOR_CONTRACT[step["operation"]]["mastertool_operation"]})
    assert plan["required_allowlist"] == expected
    assert plan["required_allowlist"] == [
        "build", "create_dut", "create_function", "create_function_block",
        "create_gvl", "create_program", "replace", "save_as"]


def test_required_allowlist_is_a_subset_of_the_literal_mutating_registry():
    """A allowlist só pode pedir nome que o gate reconheça, e o gate tem DOIS
    registros: métodos e escritas de propriedade.

    A união aqui não afrouxa nada — os dois registros são disjuntos (há teste
    no gate), e o segundo laço exige que cada nome caia em exatamente um deles.
    Um nome fora dos dois seria uma fase pedindo autorização para algo que a
    porta não sabe nomear."""
    conhecidos = (set(safety.MASTERTOOL_MUTATING_OPERATIONS)
                  | set(safety.MASTERTOOL_PROPERTY_WRITES))
    for factory in (minimal_spec, spec_with_tasks, big_spec):
        plan = _plan_of(factory())
        assert set(plan["required_allowlist"]) <= conhecidos
        for nome in plan["required_allowlist"]:
            metodo = nome in safety.MASTERTOOL_MUTATING_OPERATIONS
            propriedade = nome in safety.MASTERTOOL_PROPERTY_WRITES
            assert metodo != propriedade, nome


def test_allowlist_shrinks_when_the_plan_needs_less():
    """A allowlist é função dos passos: uma spec sem FUNCTION não pede
    `create_function`. Uma allowlist maior que o uso é permissão que ninguém
    exerce — foi o que docs/30 recusou ao deixar `create_pou` de fora."""
    spec = {
        "schema_version": 1, "template": dict(TEMPLATE),
        "gvls": [{"name": "GVL_X", "declaration": "VAR_GLOBAL\nEND_VAR"}],
    }
    plan = _plan_of(spec)
    assert plan["required_allowlist"] == [
        "build", "create_gvl", "replace", "save_as"]


def test_author_cannot_declare_the_allowlist_in_the_spec():
    """A allowlist não é declarável: o campo sequer existe na spec, e
    inventá-lo reprova por chave desconhecida (fail-closed do validador)."""
    spec = minimal_spec()
    spec["required_allowlist"] = ["create_gvl"]
    result = build_authoring_plan(spec)
    assert result.plan is None
    assert any("required_allowlist" in problem for problem in result.problems)


def test_non_mutating_steps_never_enter_the_allowlist():
    plan = _plan_of(minimal_spec())
    assert "reopen" not in plan["required_allowlist"]
    assert "verify" not in plan["required_allowlist"]


def test_program_call_compila_para_a_forma_IDIOMATICA():
    """Duas formas foram medidas, e elas NAO empatam:

        W2 (docs/39)  `MainTask.pous.add(nome)` -> compila, e o FABRICANTE
                      avisa que o padrao e outro (1 aviso).
        W3 (docs/41)  a chamada dentro de `UserPrg` -> 0 avisos.

    O planner emite a forma idiomatica, e por isso a API consumida e
    `replace`, nunca `add`. Uma fabrica que gerasse o caminho de W2
    produziria em escala o que o fabricante desaconselha.
    """
    contrato = EXECUTOR_CONTRACT["create_program_call"]
    assert contrato["mastertool_operation"] == "replace"
    assert contrato["cataloged"] is True
    assert contrato["field_proven"] is True
    plan = _plan_of(field_proven_spec())
    assert "add" not in plan["required_allowlist"]
    assert "replace" in plan["required_allowlist"]
    assert plan["executable"] is True


def test_add_so_existe_para_a_task_QUE_O_PLANO_CRIA():
    """A recusa de W2 era sobre a `MainTask`, e continua de pe: o aviso do
    fabricante nomeia ELA. Uma task criada pela spec nao e a `MainTask`, o
    perfil nao diz nada sobre ela, e a lista de POUs dela e o unico caminho.

    Este teste ja afirmou que NENHUMA operacao consome `add`. Afirmar isso
    hoje proibiria a unica forma que existe de encher uma task nova -- e a
    proibicao ampla escondia a distincao que importa, que e o RECEPTOR."""
    consomem_add = sorted(operacao for operacao, contrato
                          in EXECUTOR_CONTRACT.items()
                          if contrato["mastertool_operation"] == "add")
    assert consomem_add == ["bind_program_to_task"]
    # A operacao que serve a task do PERFIL nunca chega perto de `add`.
    assert (EXECUTOR_CONTRACT["create_program_call"]["mastertool_operation"]
            == "replace")


def test_a_task_do_perfil_recebe_a_forma_IDIOMATICA_e_a_nova_recebe_add():
    """O roteamento e por TASK, e nao por spec: quem escreve a spec pede
    `program_calls`, e quem decide o caminho e o planner."""
    plan = _plan_of(spec_with_tasks())
    por_task = {step["task_name"]: step["operation"] for step in plan["steps"]
                if step["operation"] in ("create_program_call",
                                         "bind_program_to_task")}
    assert por_task == {"MainTask": "create_program_call",
                        "TaskDiagnostico": "bind_program_to_task"}


def test_vincular_a_task_PREEXISTENTE_que_nao_e_a_do_perfil_e_LACUNA():
    """Nem `UserPrg` (que roda pela cadeia da MainTask) nem a lista de POUs
    (cujo estado inicial so e conhecido quando o plano cria a task)."""
    spec = minimal_spec()
    spec["tasks"] = [{"name": "TaskDoCliente", "existing": True,
                      "program_calls": ["PRG_AI_TESTE"]}]
    plan = _plan_of(spec)
    assert plan["executable"] is False
    lacunas = [g for g in plan["measurement_gaps"]
               if g["kind"] == "unmeasured_task_binding"]
    assert len(lacunas) == 1
    assert "TaskDoCliente" in lacunas[0]["detail"]
    # O passo CONTINUA no plano: ele e a evidencia do que a spec pediu.
    assert any(step["operation"] == "bind_program_to_task"
               for step in plan["steps"])


def test_task_criada_pelo_plano_NAO_gera_lacuna_de_vinculo():
    """A lacuna e sobre task PREEXISTENTE. A criada aqui tem estado inicial
    conhecido -- vazia --, e desde a run-036 (docs/48) ela nao tem lacuna
    nenhuma: a cadeia inteira foi medida, e o plano sai executavel."""
    spec = minimal_spec()
    spec["tasks"] = [{"name": "TaskNova", "program_calls": ["PRG_AI_TESTE"]}]
    plan = _plan_of(spec)
    assert plan["measurement_gaps"] == []
    assert plan["executable"] is True
    assert "add" in plan["required_allowlist"]
    assert "create_task" in plan["required_allowlist"]


def test_task_EXISTENTE_nao_e_criada():
    """`MainTask` vem no template. Todas as execucoes reais a reusaram --
    reusar reduz a superficie mutavel de duas operacoes estruturais para
    uma (docs/38 §1)."""
    plan = _plan_of(field_proven_spec())
    assert all(step["operation"] != "create_task" for step in plan["steps"])
    assert "create_task" not in plan["required_allowlist"]


def test_task_NAO_declarada_como_existente_pede_CRIACAO():
    """Default `False` de proposito: quem nao diz nada esta pedindo para CRIAR.

    Este teste ja terminava em BLOQUEIA, porque `create_task` nao tinha prova.
    Tem desde a run-036 (docs/48), e o que sobra e a parte que sempre foi o
    ponto: o default nao inventa que a task ja existe.

    A `MainTask` do template continua fora, e agora por um motivo diferente --
    ela E declarada `existing`. Pedir para criar uma task que ja existe e outro
    erro, e nao este."""
    spec = field_proven_spec()
    del spec["tasks"][0]["existing"]
    plan = _plan_of(spec)
    assert any(step["operation"] == "create_task" for step in plan["steps"])
    assert "create_task" in plan["required_allowlist"]


def test_plan_without_gaps_is_executable():
    plan = _plan_of(field_proven_spec())
    assert plan["measurement_gaps"] == []
    assert plan["executable"] is True


def test_API_CATALOGADA_NAO_E_OPERACAO_PROVADA(monkeypatch):
    """A distincao que fechou um fail-open real, e que continua valendo.

    Quando ela nasceu, `minimal_spec` saia `executable: True` com DUT, FUNCTION
    e FUNCTION_BLOCK -- as tres com API catalogada e NENHUMA exercida numa
    cadeia que persistiu e compilou. A lista de nao provadas ENCOLHEU a cada
    marco (docs/43, docs/46) ate ficar VAZIA na run-036 (docs/48).

    E por isso este teste virou monkeypatch. Ele ja se apoiou numa operacao
    real que por acaso estava sem prova, e essa era a fragilidade: quando a
    ultima foi provada, o teste do MECANISMO morreria junto com o exemplo. O
    que ele guarda nao e "existe algo sem prova" -- e "se houver, o plano
    bloqueia". Marcar `field_proven` sem medir tem de continuar reprovando
    mesmo num dia em que tudo esta medido.

    A allowlist CONTINUA listando a operacao -- ela descreve o que seria
    exigido --, e a lacuna diz que ninguem provou que exigir basta. Os dois ao
    mesmo tempo, de proposito.
    """
    fingido = dict(EXECUTOR_CONTRACT["create_gvl"])
    fingido["field_proven"] = False
    fingido["evidence"] = None
    monkeypatch.setitem(planner_module.EXECUTOR_CONTRACT, "create_gvl",
                        fingido)
    plan = _plan_of(minimal_spec())
    assert plan["executable"] is False
    nao_provadas = {gap["detail"].split("'")[1]
                    for gap in plan["measurement_gaps"]
                    if gap["kind"] == "operation_not_field_proven"}
    assert nao_provadas == {"create_gvl"}
    # E continua na allowlist: a fase precisaria dela.
    assert "create_gvl" in plan["required_allowlist"]


def test_NENHUMA_operacao_do_vocabulario_esta_sem_prova():
    """O outro lado do teste acima, e o unico lugar onde este fato mora.

    Se um dia uma operacao voltar a `field_proven: False` -- porque foi
    acrescentada, ou porque uma medicao foi retirada --, este teste reprova e
    obriga a dizer qual e, em vez de deixar a lacuna passar despercebida no
    meio de um plano."""
    sem_prova = sorted(operacao for operacao, contrato
                       in EXECUTOR_CONTRACT.items()
                       if not contrato["field_proven"])
    # `configure_task` esteve aqui entre a implementacao e a run-037: a classe
    # de mutacao nova (atribuicao em vez de chamada, docs/48 secao 5) nasceu sem
    # prova, como toda operacao nasce, e saiu no commit que citou a run.
    assert sem_prova == []


def test_toda_operacao_provada_cita_a_evidencia():
    """`field_proven: True` sem artefato citado seria declaracao, e nao
    medicao -- exatamente o que o campo existe para impedir."""
    for operation, contrato in EXECUTOR_CONTRACT.items():
        if contrato["field_proven"]:
            assert contrato["evidence"], operation
            assert "docs/" in contrato["evidence"], operation
        else:
            assert contrato["evidence"] is None, operation


def test_unmeasured_language_guid_becomes_a_gap_not_an_error():
    spec = minimal_spec()
    spec["programs"][0]["language"] = {"guid": "11111111-2222-3333-4444-555555555555"}
    plan = _plan_of(spec)
    assert plan["executable"] is False
    assert "unmeasured_language_guid" in [
        gap["kind"] for gap in plan["measurement_gaps"]]


def test_st_guid_is_measured_and_produces_no_gap():
    plan = _plan_of(minimal_spec())
    assert all(gap["kind"] != "unmeasured_language_guid"
               for gap in plan["measurement_gaps"])


def test_language_never_travels_as_the_string_st():
    spec = minimal_spec()
    spec["programs"][0]["language"] = "ST"
    result = build_authoring_plan(spec)
    assert result.plan is None
    assert any("Nullable" in problem or "GUID" in problem
               for problem in result.problems)


# =============================================================================
# 8. Validações offline e entrada degenerada
# =============================================================================

@pytest.mark.parametrize("value", [None, [], "spec", 3, True, 0.5, (), set()])
def test_degenerate_input_returns_problems_and_never_raises(value):
    result = build_authoring_plan(value)
    assert isinstance(result.problems, list) and result.problems
    assert result.plan is None
    assert not result.ok


@pytest.mark.parametrize("value", [None, [], "x", 3, True, {"id": 1}])
def test_degenerate_expected_template_never_raises(value):
    result = build_authoring_plan(minimal_spec(), expected_template=value)
    assert isinstance(result.problems, list)
    assert result.plan is None or result.problems == []


def test_expected_template_mismatch_is_refused():
    result = build_authoring_plan(
        minimal_spec(), expected_template={"id": "OUTRO", "sha256": "b" * 64})
    assert result.plan is None
    assert any("template.id" in problem for problem in result.problems)
    assert any("template.sha256" in problem for problem in result.problems)


def test_expected_template_match_is_accepted():
    result = build_authoring_plan(minimal_spec(), expected_template=dict(TEMPLATE))
    assert result.problems == []
    assert result.plan is not None


def test_expected_template_sha_is_compared_case_insensitively():
    spec = minimal_spec()
    spec["template"]["sha256"] = "A" * 64
    result = build_authoring_plan(spec, expected_template={"id": "TemplateExemplo-v1",
                                                           "sha256": "a" * 64})
    assert result.problems == []


def test_duplicate_name_across_families_is_refused():
    """Dois objetos com o mesmo nome no container da Application não podem
    coexistir — e resolver `uses` viraria ambíguo, o que produziria um plano
    silenciosamente errado."""
    spec = minimal_spec()
    spec["gvls"].append({"name": "ST_Motor", "declaration": "VAR_GLOBAL\nEND_VAR"})
    result = build_authoring_plan(spec)
    assert result.plan is None
    assert any("conflita entre" in problem for problem in result.problems)


def test_duplicate_name_within_family_is_refused():
    spec = minimal_spec()
    spec["duts"].append({"name": "ST_Motor", "kind": "ENUM", "declaration": "d"})
    result = build_authoring_plan(spec)
    assert result.plan is None
    assert any("duplicado" in problem for problem in result.problems)


def test_missing_reference_is_refused():
    spec = minimal_spec()
    spec["programs"][0]["uses"] = ["FB_QUE_NAO_EXISTE"]
    result = build_authoring_plan(spec)
    assert result.plan is None
    assert any("não existe na" in problem for problem in result.problems)


def test_invalid_iec_name_is_refused():
    spec = minimal_spec()
    spec["duts"][0]["name"] = "1_invalido"
    result = build_authoring_plan(spec)
    assert result.plan is None


def test_reserved_word_as_name_is_refused():
    spec = minimal_spec()
    spec["duts"][0]["name"] = "STRUCT"
    result = build_authoring_plan(spec)
    assert result.plan is None


def test_wrong_schema_version_is_refused():
    spec = minimal_spec()
    spec["schema_version"] = "1.0"
    result = build_authoring_plan(spec)
    assert result.plan is None
    assert any("schema_version" in problem for problem in result.problems)


def test_unknown_field_anywhere_is_refused():
    spec = minimal_spec()
    spec["duts"][0]["cor_favorita"] = "azul"
    result = build_authoring_plan(spec)
    assert result.plan is None


def test_program_call_to_unknown_program_is_refused():
    spec = spec_with_tasks()
    spec["tasks"][0]["program_calls"] = ["PRG_FANTASMA"]
    result = build_authoring_plan(spec)
    assert result.plan is None


def test_repeated_program_call_in_the_same_task_is_refused():
    spec = spec_with_tasks()
    spec["tasks"][0]["program_calls"] = ["PRG_AI_TESTE", "PRG_AI_TESTE"]
    result = build_authoring_plan(spec)
    assert result.plan is None
    assert any("mais de uma vez na mesma task" in problem
               for problem in result.problems)


def test_duplicate_library_is_refused():
    spec = spec_with_tasks()
    spec["libraries"] = [{"name": "Standard"}, {"name": "Standard"}]
    result = build_authoring_plan(spec)
    assert result.plan is None
    assert any("mais de uma vez" in problem for problem in result.problems)


def test_forward_reference_to_a_later_family_is_refused():
    """Um DUT não pode usar uma GVL: a GVL é criada depois, e nenhuma ordem
    topológica conserta isso."""
    spec = minimal_spec()
    spec["duts"][0]["uses"] = ["GVL_AI_TESTE"]
    result = build_authoring_plan(spec)
    assert result.plan is None


def test_empty_spec_produces_only_the_project_level_steps():
    spec = {"schema_version": 1, "template": dict(TEMPLATE)}
    plan = _plan_of(spec)
    assert [step["operation"] for step in plan["steps"]] == \
        ["save_as", "reopen", "build", "verify"]
    assert plan["creation_order"] == []
    assert plan["required_allowlist"] == ["build", "save_as"]


def test_result_dataclass_never_reports_ok_with_problems():
    result = build_authoring_plan(None)
    assert not result.ok
    assert result.plan is None


# =============================================================================
# 9. Spec grande sintética
# =============================================================================

def test_big_spec_counts():
    plan = _plan_of(big_spec())
    diff = plan["expected_diff"]
    assert diff["duts"] == 20
    assert diff["gvls"] == 20
    assert diff["functions"] == 0
    assert diff["function_blocks"] == 50
    assert diff["programs"] == 10
    # 100 objetos criados; texto: 20 + 20 + 50*2 + 10*2 = 160 replaces
    assert diff["text_replacements"] == 160
    assert diff["total_steps"] == 100 + 160 + 4
    assert len(plan["creation_order"]) == 100


def test_big_spec_keeps_families_contiguous_and_in_canonical_order():
    """Nenhuma GVL sai antes do último DUT. Se a topológica escolhesse "o
    primeiro pronto" em vez de "o menor por chave", famílias se
    interleaveriam — defeito que uma spec de um objeto por família esconde."""
    plan = _plan_of(big_spec())
    ranks = [FAMILY_RANK[key.split(":", 1)[0]] for key in plan["creation_order"]]
    assert ranks == sorted(ranks)


def test_big_spec_order_is_stable_across_many_builds():
    """Muitos empates simultâneos são exatamente onde iteração de `set`/`dict`
    apareceria. Repetir a construção tem de dar sempre o mesmo plano."""
    reference = plan_to_json(_plan_of(big_spec()))
    for _ in range(5):
        assert plan_to_json(_plan_of(big_spec())) == reference


def test_big_spec_every_step_uses_the_closed_operation_set():
    plan = _plan_of(big_spec())
    for step in plan["steps"]:
        assert step["operation"] in PLAN_OPERATIONS
        assert step["target_kind"] in TARGET_KINDS
        assert set(step) == {
            "sequence", "operation", "target_kind", "target_name",
            "source_location", "expected_before_kind", "expected_before_sha256",
            "planned_after_sha256", "planned_after_normalized_sha256",
            "language_guid", "dut_kind", "return_type", "created_by_sequence",
            "task_name", "program_name", "task_properties"}


BIG_SPEC_PROBE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
from test_planner import big_spec
from mastertool_bridge.planner.planner import build_authoring_plan, plan_to_json
result = build_authoring_plan(big_spec())
assert result.problems == [], result.problems
# Escreve BYTES, nao texto. `sys.stdout.write` deixaria a codificacao a cargo
# do default do interpretador filho, que no Windows depende de code page, de
# modo UTF-8 e de variavel de ambiente -- o mesmo tipo de suposicao que ja
# produziu BOM em `session-verdict.json`. Com `buffer.write` o produtor e o
# consumidor concordam por construcao, e nao por coincidencia de ambiente.
sys.stdout.buffer.write(plan_to_json(result.plan).encode("utf-8"))
"""


def test_big_spec_plan_is_identical_across_separate_processes(tmp_path):
    """Determinismo REAL: processos separados, `PYTHONHASHSEED` diferente.

    Repetir a construção dentro do mesmo processo não prova nada sobre ordem
    de `set`/`dict`: dentro de um processo o hash de string é fixo. O
    não-determinismo por iteração de `set` só aparece quando a semente muda —
    e é justamente com 100 objetos e dezenas de empates simultâneos que ele
    apareceria.
    """
    import subprocess

    script = tmp_path / "build_big_plan.py"
    script.write_text(BIG_SPEC_PROBE, encoding="utf-8")
    src_dir = str(REPO_ROOT / "src")
    tests_dir = str(Path(__file__).resolve().parent)

    outputs = []
    for seed in ("0", "1", "12345", "424242", "random"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        env.pop("PYTHONPATH", None)
        # `encoding="utf-8"` e obrigatorio, e nao cosmetico. Com `text=True`
        # sozinho, o Python decodifica a saida do subprocesso usando o code
        # page do console -- cp1252 nesta maquina --, e o plano volta com
        # `nAo` no lugar de `nao` acentuado. O teste entao acusaria
        # NAO-DETERMINISMO onde ha apenas decodificacao errada: os cinco
        # subprocessos concordavam entre si, e so a comparacao com o plano
        # gerado em processo e que quebrava. Mesma classe do BOM em
        # `session-verdict.json` -- suposicao de codificacao no Windows.
        completed = subprocess.run(
            [sys.executable, str(script), src_dir, tests_dir],
            capture_output=True, text=True, encoding="utf-8",
            env=env, cwd=str(tmp_path), timeout=120, check=False)
        assert completed.returncode == 0, completed.stderr
        outputs.append(completed.stdout)

    assert len(set(outputs)) == 1, (
        "o plano da spec grande mudou entre processos com PYTHONHASHSEED "
        "diferente — há ordem vindo de iteração de set/dict")
    # E o processo separado concorda com o processo do teste, byte a byte.
    assert outputs[0].replace("\r\n", "\n") == plan_to_json(_plan_of(big_spec()))


# =============================================================================
# 10. Limites de VERIFICAÇÃO (o que a API NÃO permite medir hoje)
# =============================================================================

def test_no_validation_compares_declared_language_with_observed_language():
    """Medido: não há API catalogada para LER a linguagem de um objeto
    existente. Uma comparação declarado-vs-observado seria inverificável — não
    existe, e o plano DECLARA o limite em vez de fingir que verifica."""
    plan = _plan_of(minimal_spec())
    kinds = [limit["kind"] for limit in plan["verification_limits"]]
    assert "language_not_readable" in kinds
    source = io.open(PLANNER_PY, encoding="utf-8").read()
    for forbidden in ("observed_language", "language_observed",
                      "read_language", "get_language"):
        assert forbidden not in source


def test_expected_tree_is_comparable_with_a_direct_children_scan():
    """A varredura dos probes é `get_children(False)` — só filhos diretos.

    Consequências que este teste congela: `persistent_additions` é de um único
    nível; nenhum passo cria pasta ou aninha objeto; e tasks/Program Calls
    ficam em listas SEPARADAS, porque vivem em outro container e nunca
    apareceriam naquela varredura.
    """
    plan = _plan_of(spec_with_tasks())
    kinds = [limit["kind"] for limit in plan["verification_limits"]]
    assert "direct_children_only" in kinds
    assert "task_container_not_in_application_scan" in kinds

    assert "create_folder" not in plan["required_allowlist"]
    assert all(step["operation"] != "create_folder" for step in plan["steps"])

    tree = plan["expected_tree"]
    assert set(tree["persistent_additions"]).isdisjoint(tree["task_additions"])
    assert set(tree["persistent_additions"]).isdisjoint(
        tree["program_call_additions"])
    # Um único nível: nenhum nome de adição carrega separador de caminho.
    for name in tree["persistent_additions"]:
        assert "/" not in name and "\\" not in name


def test_verification_limits_do_not_block_execution():
    """Limite de verificação delimita o que `verify` pode afirmar; lacuna de
    medição impede executar. São coisas distintas e não podem se confundir."""
    plan = _plan_of(field_proven_spec())
    assert plan["verification_limits"]
    assert plan["measurement_gaps"] == []
    assert plan["executable"] is True


def test_verification_limits_are_a_closed_set():
    schema = json.loads(io.open(PLAN_SCHEMA_PATH, encoding="utf-8").read())
    enum = schema["properties"]["verification_limits"]["items"][
        "properties"]["kind"]["enum"]
    assert tuple(enum) == planner_module.VERIFICATION_LIMIT_KINDS
    for factory in (minimal_spec, spec_with_tasks, big_spec):
        for limit in _plan_of(factory())["verification_limits"]:
            assert limit["kind"] in planner_module.VERIFICATION_LIMIT_KINDS


def test_empty_spec_declares_no_irrelevant_limit():
    """O limite só é declarado quando é relevante: uma spec sem objeto nenhum
    não tem árvore a comparar nem linguagem a informar."""
    plan = _plan_of({"schema_version": 1, "template": dict(TEMPLATE)})
    assert plan["verification_limits"] == []


def test_big_spec_source_locations_are_unique_and_name_qualified():
    plan = _plan_of(big_spec())
    replaces = [step["source_location"] for step in plan["steps"]
                if step["operation"] == "replace"]
    assert len(replaces) == len(set(replaces))
    assert all(location.count(":") == 2 for location in replaces)


# =============================================================================
# ordem de chamada dentro de uma task -- a ordem de execucao no ciclo IEC
# =============================================================================

def _spec_com_duas_chamadas_fora_de_ordem_alfabetica():
    """`PRG_Bomba` antes de `PRG_Alarme`: alfabetizar inverte os dois."""
    return {
        "schema_version": 1,
        "template": {"id": "TemplateExemplo_v1", "sha256": "5966257" + "0" * 57},
        "programs": [
            {"name": "PRG_Bomba", "language": {"guid": ST_GUID},
             "declaration": "PROGRAM PRG_Bomba\nVAR\n x : BOOL;\nEND_VAR",
             "implementation": "x := TRUE;"},
            {"name": "PRG_Alarme", "language": {"guid": ST_GUID},
             "declaration": "PROGRAM PRG_Alarme\nVAR\n y : BOOL;\nEND_VAR",
             "implementation": "y := TRUE;"},
        ],
        "tasks": [{"name": "MainTask", "existing": True,
                   "program_calls": ["PRG_Bomba", "PRG_Alarme"]}],
    }


def test_ordem_declarada_de_program_calls_e_preservada_no_plano():
    """Em IEC, a ordem das chamadas dentro de uma task É a ordem de execução
    no ciclo. O planner alfabetizava, e a spec acima executaria o alarme antes
    da bomba — comportamento diferente do pedido, sem diagnóstico nenhum."""
    resultado = build_authoring_plan(_spec_com_duas_chamadas_fora_de_ordem_alfabetica())
    assert resultado.problems == [], resultado.problems

    chamadas = [passo["target_name"] for passo in resultado.plan["steps"]
                if passo["operation"] in ("create_program_call",
                                          "bind_program_to_task")]
    assert chamadas == ["MainTask->PRG_Bomba", "MainTask->PRG_Alarme"]
    assert chamadas != sorted(chamadas)


def test_creation_order_do_validador_tambem_segue_a_ordem_declarada():
    """São duas estruturas com o mesmo nome, e só uma lista chamadas: o
    `creation_order` do PLANO é a ordem topológica dos objetos criados; o do
    VALIDADOR é o que a verificação compara contra o projeto gerado, e é lá
    que as chamadas aparecem. As duas precisavam ser corrigidas juntas —
    validador alfabetizando e planner respeitando a spec seria discordância
    silenciosa entre quem verifica e quem executa."""
    from mastertool_bridge.spec.validator import validate_project_spec

    resultado = validate_project_spec(
        _spec_com_duas_chamadas_fora_de_ordem_alfabetica())
    chamadas = [chave for chave in resultado.creation_order
                if chave.startswith("program_call:")]
    assert chamadas == ["program_call:MainTask->PRG_Bomba",
                        "program_call:MainTask->PRG_Alarme"]
    assert chamadas != sorted(chamadas)


def test_a_ordem_declarada_continua_deterministica():
    """Trocar ordem alfabética por ordem da spec não introduz variação: o
    mesmo texto de spec produz o mesmo plano."""
    spec = _spec_com_duas_chamadas_fora_de_ordem_alfabetica()
    primeiro = build_authoring_plan(spec).plan
    segundo = build_authoring_plan(spec).plan
    assert primeiro["steps"] == segundo["steps"]
    assert primeiro["creation_order"] == segundo["creation_order"]
    assert primeiro["plan_sha256"] == segundo["plan_sha256"]


def test_chamada_repetida_na_mesma_task_continua_reprovando():
    """A ordem passou a ser respeitada; a recusa de duplicata não afrouxou."""
    spec = _spec_com_duas_chamadas_fora_de_ordem_alfabetica()
    spec["tasks"][0]["program_calls"] = ["PRG_Bomba", "PRG_Bomba"]
    resultado = build_authoring_plan(spec)
    assert any("aparece mais de uma vez" in p for p in resultado.problems)


# =============================================================================
# R2 -- alteração de objeto preexistente, com hash anterior medido
# =============================================================================

def _spec_modificacao(**mudancas):
    entrada = {"family": "programs", "name": "UserPrg",
               "field": "implementation",
               "expected_before_sha256": "a" * 64, "text": "x := 1;"}
    entrada.update(mudancas)
    return {"schema_version": 1,
            "template": {"id": "TemplateExemplo_v1", "sha256": "5966257" + "0" * 57},
            "modifications": [entrada]}


def test_modificacao_emite_replace_com_procedencia_medida():
    from mastertool_bridge.planner.planner import EXPECTED_BEFORE_MEASURED

    resultado = build_authoring_plan(_spec_modificacao())
    assert resultado.problems == [], resultado.problems
    passos = [p for p in resultado.plan["steps"] if p["operation"] == "replace"]
    assert len(passos) == 1
    assert passos[0]["expected_before_kind"] == EXPECTED_BEFORE_MEASURED
    assert passos[0]["expected_before_sha256"] == "a" * 64
    assert passos[0]["planned_after_sha256"]


def test_alterar_objeto_que_a_propria_spec_cria_reprova():
    """As duas procedências existem para casos diferentes. Conferir o hash de
    um esqueleto que o plano acabou de gerar é verificação que passa sempre."""
    spec = _spec_modificacao(name="PRG_NOVO")
    spec["programs"] = [{"name": "PRG_NOVO", "language": {"guid": ST_GUID},
                         "declaration": "PROGRAM PRG_NOVO\nVAR\nEND_VAR",
                         "implementation": ";"}]
    resultado = build_authoring_plan(spec)
    assert any("procedências diferentes" in p or "procedencias diferentes" in p
               for p in resultado.problems)


@pytest.mark.parametrize("mudanca,esperado", [
    ({"expected_before_sha256": "curto"}, "expected_before_sha256"),
    ({"expected_before_sha256": None}, "expected_before_sha256"),
    ({"family": "tasks"}, "family"),
    ({"field": "corpo"}, "field"),
    ({"name": "1_invalido"}, "name"),
    ({"text": 42}, "text"),
])
def test_modificacao_malformada_reprova(mudanca, esperado):
    resultado = build_authoring_plan(_spec_modificacao(**mudanca))
    assert any(esperado in p for p in resultado.problems), resultado.problems


def test_duas_alteracoes_do_mesmo_documento_reprovam():
    """Qual conteúdo ficaria? A pergunta não tem resposta, então o plano não
    é emitido."""
    spec = _spec_modificacao()
    spec["modifications"].append(dict(spec["modifications"][0], text="y := 2;"))
    resultado = build_authoring_plan(spec)
    assert any("mais de uma vez" in p for p in resultado.problems)


def test_campo_desconhecido_na_modificacao_reprova():
    spec = _spec_modificacao()
    spec["modifications"][0]["node_path"] = "root/1/0/0"
    resultado = build_authoring_plan(spec)
    assert any("desconhecido" in p for p in resultado.problems)


def test_spec_sem_modifications_continua_igual():
    """A família nova é opcional: nenhuma spec existente muda de comportamento."""
    plano = build_authoring_plan(
        _spec_com_duas_chamadas_fora_de_ordem_alfabetica()).plan
    assert all(p.get("expected_before_kind") != "measured"
               for p in plano["steps"])
    assert any(p["operation"] == "replace" for p in plano["steps"])

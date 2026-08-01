"""Testa `mastertool_bridge.templates.registry` (Frente B, modelo
declarativo `template_registry`). Suíte 100% offline: nenhum teste aqui abre
o MasterTool nem depende de IronPython — `validate_template_registry` é
CPython 3 puro, sem `jsonschema`.

Cobertura mínima exigida pelo contrato da frente: registry mínimo válido;
campo desconhecido recusado em cada nível; `allow_download: true` sempre
recusado; `node_path` só resolvido quando o sha256 do arquivo bate com a
entrada exata (nunca por template_id); `reserved_object_names` detecta
conflito com nomes propostos; entrada degenerada (None, lista, string, int,
bool) devolve problemas em vez de levantar."""

import copy
import json
from pathlib import Path

import pytest

from mastertool_bridge.templates import registry as registry_mod
from mastertool_bridge.templates.registry import (
    BLOCKER_COMPILER_VERSION,
    EVIDENCE_UNRESOLVED,
    QUALIFICATION_QUALIFIED,
    QUALIFICATION_WITH_BLOCKERS,
    RegistryValidationResult,
    authoring_refusal_reason,
    check_reserved_object_names,
    resolve_node_path_for_file,
    select_template_for_authoring,
    validate_template_registry,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
GUID_APPLICATION = "639b491f-5557-464c-af91-1471bac9f549"


def _minimal_valid_registry():
    return {
        "schema_version": 1,
        "templates": [
            {
                "template_id": "TemplateExemplo-v1",
                "mastertool_version": "1.2.3.4",
                "sha256": SHA_A,
                "size_bytes": 503040,
                "application_node_path": "root/1/0/0",
                "application_type_guid": GUID_APPLICATION,
                "compiler_version": {
            "status": "measured",
            "value": "4.11.0.0",
            "source": "literal read-only MasterTool API",
            "reason": None,
        },
                "persistent_tree_sha256": SHA_B,
                "libraries": [
                    {"name": "Standard", "allow_download": False},
                ],
                "tasks": [
                    {"name": "MainTask", "cycle_time_ms": 10, "priority": 1},
                ],
                "volatile_fields": ["timestamp_catalogado", "session_guid"],
                "reserved_object_names": ["GVL_AI_TESTE", "PRG_AI_TESTE"],
                "authoring_rules": {
                    "allowed_object_families": ["gvls", "programs"],
                    "forbidden_apis": [
                        "download_missing_libraries",
                        "set_compilerversion_to_newest",
                    ],
                },
            },
        ],
    }


# =============================================================================
# Registry mínimo válido
# =============================================================================

def _com_lacuna_de_compiler():
    """Registry cujo template foi medido em tudo, MENOS compiler version --
    exatamente o que o probe 35 produz hoje, porque nenhum acessor de
    IScriptProjectSettings2 esta catalogado."""
    registry = _minimal_valid_registry()
    registry["templates"][0]["compiler_version"] = {
        "status": "unresolved",
        "value": None,
        "source": "probe_35",
        "reason": "IScriptProjectSettings2 accessor not catalogued",
    }
    return registry


def test_template_com_lacuna_e_REGISTRAVEL():
    """A metade que quase se perde: template incompleto PODE ser inspecionado
    e registrado. Rejeitar o registro inteiro por causa de um campo seria
    jogar fora todas as outras medicoes da sessao."""
    result = validate_template_registry(_com_lacuna_de_compiler())
    assert result.ok, result.problems
    entry = result.entries_by_sha256[SHA_A]
    assert entry.compiler_version.status == EVIDENCE_UNRESOLVED
    assert entry.compiler_version.value is None
    assert entry.compiler_version.reason


def test_template_com_lacuna_NAO_e_elegivel_para_autoria():
    """E a outra metade: registravel nao e executavel."""
    result = validate_template_registry(_com_lacuna_de_compiler())
    entry = result.entries_by_sha256[SHA_A]
    assert entry.qualification_status == QUALIFICATION_WITH_BLOCKERS
    assert entry.authoring_eligible is False
    assert BLOCKER_COMPILER_VERSION in entry.blocking_issues


def test_o_executor_nao_consegue_selecionar_template_inelegivel():
    """O gate que importa: `select_template_for_authoring` recusa, mesmo com
    o sha256 correto e o registry valido."""
    result = validate_template_registry(_com_lacuna_de_compiler())
    assert select_template_for_authoring(result, SHA_A) is None
    motivo = authoring_refusal_reason(result, SHA_A)
    assert motivo is not None and "NÃO é elegível" in motivo
    assert BLOCKER_COMPILER_VERSION in motivo


def test_inspecao_continua_permitida_no_template_inelegivel():
    """Recusar autoria nao pode ter fechado a inspecao junto -- o node_path
    continua disponivel para quem so quer LER o template."""
    result = validate_template_registry(_com_lacuna_de_compiler())
    assert resolve_node_path_for_file(result, SHA_A) == "root/1/0/0"


def test_template_medido_volta_a_ser_elegivel():
    """Prova que o bloqueio e condicional e nao permanente: com a evidencia
    `measured`, o mesmo template passa. Sem isto, o gate poderia estar
    simplesmente quebrado e ninguem notaria."""
    result = validate_template_registry(_minimal_valid_registry())
    entry = result.entries_by_sha256[SHA_A]
    assert entry.authoring_eligible is True
    assert entry.qualification_status == QUALIFICATION_QUALIFIED
    assert entry.blocking_issues == ()
    assert select_template_for_authoring(result, SHA_A) is entry
    assert authoring_refusal_reason(result, SHA_A) is None


def test_declarar_authoring_eligible_no_arquivo_e_CONTRADICAO():
    """O modo de falha central: alguem edita o registry para se declarar
    elegivel e libera execucao mutavel sobre template incompleto. O campo e
    derivado, e declara-lo divergente reprova."""
    registry = _com_lacuna_de_compiler()
    registry["templates"][0]["authoring_eligible"] = True
    result = validate_template_registry(registry)
    assert not result.ok
    assert any("DERIVADO" in p for p in result.problems)


def test_declarar_blocking_issues_vazio_tambem_e_CONTRADICAO():
    """Nao basta guardar `authoring_eligible`: zerar a lista de bloqueios
    seria o mesmo ataque por outra porta."""
    registry = _com_lacuna_de_compiler()
    registry["templates"][0]["blocking_issues"] = []
    result = validate_template_registry(registry)
    assert not result.ok
    assert any("DERIVADO" in p for p in result.problems)


@pytest.mark.parametrize("evidencia,fragmento", [
    ({"status": "measured", "value": None, "source": "x", "reason": None},
     "exige value string não vazia"),
    ({"status": "measured", "value": "", "source": "x", "reason": None},
     "exige value string não vazia"),
    ({"status": "unresolved", "value": "3.5", "source": "x", "reason": "r"},
     "exige value null"),
    ({"status": "unresolved", "value": None, "source": "x", "reason": ""},
     "exige reason"),
    ({"status": "inventado", "value": None, "source": "x", "reason": "r"},
     "deve ser um de"),
    ("4.11.0.0", "objeto de evidência"),
    (None, "objeto de evidência"),
])
def test_evidencia_incoerente_e_recusada(evidencia, fragmento):
    """As duas direcoes. A terceira linha e a mais importante: `unresolved`
    carregando valor e uma lacuna que se anuncia como lacuna enquanto entrega
    dado que ninguem mediu."""
    registry = _minimal_valid_registry()
    registry["templates"][0]["compiler_version"] = evidencia
    result = validate_template_registry(registry)
    assert not result.ok
    assert any(fragmento in p for p in result.problems), result.problems


def test_registry_nao_conhece_set_compilerversion_to_newest():
    """Fallback para compiler mais novo e proibido por contrato. Verificado no
    fonte, e nao apenas prometido no docstring."""
    fonte = Path(registry_mod.__file__).read_text(encoding="utf-8")
    assert "set_compilerversion_to_newest" not in fonte.replace(
        "'set_compilerversion_to_newest'", "").replace(
        '"set_compilerversion_to_newest"', "")


def test_minimal_valid_registry_has_no_problems():
    result = validate_template_registry(_minimal_valid_registry())
    assert isinstance(result, RegistryValidationResult)
    assert result.problems == []
    assert result.ok is True
    assert SHA_A in result.entries_by_sha256
    assert "TemplateExemplo-v1" in result.entries_by_template_id


def test_json_schema_file_is_parseable_json():
    schema_path = (Path(__file__).resolve().parents[2] / "src" / "mastertool_bridge"
                   / "templates" / "template_registry.schema.json")
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    assert data["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "templates" in data["properties"]


# =============================================================================
# Entrada degenerada nunca levanta
# =============================================================================

@pytest.mark.parametrize("degenerate", [None, [], "not-a-dict", 42, True, False])
def test_degenerate_input_never_raises(degenerate):
    result = validate_template_registry(degenerate)
    assert isinstance(result, RegistryValidationResult)
    assert result.problems != []
    assert result.ok is False


def test_degenerate_templates_list_never_raises():
    registry = _minimal_valid_registry()
    registry["templates"] = "not-a-list"
    result = validate_template_registry(registry)
    assert result.ok is False


def test_degenerate_template_entry_never_raises():
    registry = _minimal_valid_registry()
    registry["templates"].append(None)
    registry["templates"].append("also not a dict")
    registry["templates"].append(42)
    result = validate_template_registry(registry)
    assert result.ok is False
    assert any("templates[1]" in p for p in result.problems)
    assert any("templates[2]" in p for p in result.problems)
    assert any("templates[3]" in p for p in result.problems)


# =============================================================================
# Campo desconhecido, fail-closed, em cada nível
# =============================================================================

def test_unknown_field_rejected_at_root():
    registry = _minimal_valid_registry()
    registry["telepatia"] = True
    result = validate_template_registry(registry)
    assert any("telepatia" in p for p in result.problems)


def test_unknown_field_rejected_at_template_entry():
    registry = _minimal_valid_registry()
    registry["templates"][0]["campo_fantasma"] = 1
    result = validate_template_registry(registry)
    assert any("campo_fantasma" in p for p in result.problems)


def test_unknown_field_rejected_at_library():
    registry = _minimal_valid_registry()
    registry["templates"][0]["libraries"][0]["magico"] = True
    result = validate_template_registry(registry)
    assert any("magico" in p for p in result.problems)


def test_unknown_field_rejected_at_task():
    registry = _minimal_valid_registry()
    registry["templates"][0]["tasks"][0]["extra"] = "x"
    result = validate_template_registry(registry)
    assert any("extra" in p for p in result.problems)


def test_unknown_field_rejected_at_authoring_rules():
    registry = _minimal_valid_registry()
    registry["templates"][0]["authoring_rules"]["outro"] = 1
    result = validate_template_registry(registry)
    assert any("outro" in p for p in result.problems)


def test_missing_required_field_at_template_entry():
    registry = _minimal_valid_registry()
    del registry["templates"][0]["compiler_version"]
    result = validate_template_registry(registry)
    assert any("compiler_version" in p for p in result.problems)


# =============================================================================
# allow_download deve ser sempre false — download_missing_libraries proibido
# =============================================================================

def test_allow_download_true_is_rejected():
    registry = _minimal_valid_registry()
    registry["templates"][0]["libraries"][0]["allow_download"] = True
    result = validate_template_registry(registry)
    assert result.ok is False
    assert any("allow_download" in p and "download_missing_libraries" in p
               for p in result.problems)


def test_allow_download_false_is_accepted():
    result = validate_template_registry(_minimal_valid_registry())
    entry = result.entries_by_sha256[SHA_A]
    assert entry.libraries[0].allow_download is False


# =============================================================================
# node_path é caminho de índices, amarrado ao sha256 do arquivo exato
# =============================================================================

def test_node_path_pattern_is_index_path_not_names():
    registry = _minimal_valid_registry()
    registry["templates"][0]["application_node_path"] = "Application/GVL_AI_TESTE"
    result = validate_template_registry(registry)
    assert result.ok is False
    assert any("application_node_path" in p for p in result.problems)


def test_resolve_node_path_for_file_matches_by_sha256_of_the_exact_file():
    result = validate_template_registry(_minimal_valid_registry())
    assert resolve_node_path_for_file(result, SHA_A) == "root/1/0/0"


def test_resolve_node_path_for_file_refuses_unknown_sha256():
    """Um sha256 de um arquivo DIFERENTE (ex.: mesma base de template, mas
    com um cartão de I/O a mais, que desloca os índices) nunca deve receber
    de volta o node_path de outra entrada — a única resposta correta é
    'não sei', nunca um valor emprestado de outro arquivo."""
    result = validate_template_registry(_minimal_valid_registry())
    outro_arquivo_sha256 = "c" * 64
    assert resolve_node_path_for_file(result, outro_arquivo_sha256) is None


def test_resolve_node_path_for_file_has_no_lookup_by_template_id():
    """Não existe, deliberadamente, uma função `resolve_node_path_by_template_id`
    — pedir node_path por template_id devolveria o node_path errado quando o
    template tem mais de uma versão de arquivo com sha256 diferentes."""
    import mastertool_bridge.templates.registry as registry_module
    assert not hasattr(registry_module, "resolve_node_path_by_template_id")


def test_resolve_node_path_for_file_returns_none_when_registry_has_problems():
    registry = _minimal_valid_registry()
    registry["templates"][0]["libraries"][0]["allow_download"] = True
    result = validate_template_registry(registry)
    assert resolve_node_path_for_file(result, SHA_A) is None


def test_two_entries_with_same_sha256_but_divergent_data_is_rejected():
    """Duas entradas descrevendo o 'mesmo' arquivo (mesmo sha256) mas com
    node_path divergente é uma contradição: node_path só é válido para o
    arquivo exato, e um arquivo não pode ter dois node_paths diferentes."""
    registry = _minimal_valid_registry()
    second = copy.deepcopy(registry["templates"][0])
    second["application_node_path"] = "root/2/0/0"
    registry["templates"].append(second)
    result = validate_template_registry(registry)
    assert result.ok is False
    assert any("sha256" in p and "divergentes" in p for p in result.problems)


def test_two_entries_with_same_sha256_and_identical_data_is_redundant_not_error():
    registry = _minimal_valid_registry()
    registry["templates"].append(copy.deepcopy(registry["templates"][0]))
    result = validate_template_registry(registry)
    assert result.ok is True


def test_same_template_id_different_sha256_are_independent_versions():
    """Duas versões do mesmo template_id (cartões de I/O diferentes) têm
    sha256 e node_path próprios, e ambos ficam disponíveis por sha256."""
    registry = _minimal_valid_registry()
    second = copy.deepcopy(registry["templates"][0])
    second["sha256"] = SHA_B
    second["persistent_tree_sha256"] = SHA_A
    second["application_node_path"] = "root/1/0/1"
    registry["templates"].append(second)
    result = validate_template_registry(registry)
    assert result.ok is True
    assert len(result.entries_by_template_id["TemplateExemplo-v1"]) == 2
    assert resolve_node_path_for_file(result, SHA_A) == "root/1/0/0"
    assert resolve_node_path_for_file(result, SHA_B) == "root/1/0/1"


# =============================================================================
# reserved_object_names detecta conflito com nomes propostos
# =============================================================================

def test_check_reserved_object_names_detects_conflict():
    result = validate_template_registry(_minimal_valid_registry())
    entry = result.entries_by_sha256[SHA_A]
    conflicts = check_reserved_object_names(entry, ["GVL_AI_TESTE", "GVL_NOVO"])
    assert conflicts == ["GVL_AI_TESTE"]


def test_check_reserved_object_names_no_conflict():
    result = validate_template_registry(_minimal_valid_registry())
    entry = result.entries_by_sha256[SHA_A]
    conflicts = check_reserved_object_names(entry, ["GVL_NOVO", "PRG_NOVO"])
    assert conflicts == []


def test_check_reserved_object_names_degenerate_input_returns_empty():
    result = validate_template_registry(_minimal_valid_registry())
    entry = result.entries_by_sha256[SHA_A]
    assert check_reserved_object_names(entry, None) == []
    assert check_reserved_object_names(entry, "GVL_AI_TESTE") == []
    assert check_reserved_object_names(entry, 42) == []


# =============================================================================
# GUID, sha256, size_bytes, tipos numéricos
# =============================================================================

def test_invalid_guid_rejected():
    registry = _minimal_valid_registry()
    registry["templates"][0]["application_type_guid"] = "nao-e-guid"
    result = validate_template_registry(registry)
    assert result.ok is False


def test_invalid_sha256_rejected():
    registry = _minimal_valid_registry()
    registry["templates"][0]["sha256"] = "curto-demais"
    result = validate_template_registry(registry)
    assert result.ok is False


def test_size_bytes_bool_rejected():
    """bool é subclasse de int em Python — este validador precisa recusar
    explicitamente, senão True/False passariam como 1/0 válidos."""
    registry = _minimal_valid_registry()
    registry["templates"][0]["size_bytes"] = True
    result = validate_template_registry(registry)
    assert result.ok is False


def test_size_bytes_negative_rejected():
    registry = _minimal_valid_registry()
    registry["templates"][0]["size_bytes"] = -1
    result = validate_template_registry(registry)
    assert result.ok is False


def test_authoring_rules_unknown_family_rejected():
    registry = _minimal_valid_registry()
    registry["templates"][0]["authoring_rules"]["allowed_object_families"] = ["ladder"]
    result = validate_template_registry(registry)
    assert result.ok is False


def test_authoring_rules_missing_forbidden_apis_rejected():
    registry = _minimal_valid_registry()
    del registry["templates"][0]["authoring_rules"]["forbidden_apis"]
    result = validate_template_registry(registry)
    assert result.ok is False

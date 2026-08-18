"""O plano de reversão de MEMBRO é EMITIDO, e desfaz exatamente o que a ida fez.

Contrato `docs/87` §7.

`changes/rollback.py` reverte **texto de objeto preexistente** — a inversa de um
`replace` é outro `replace`. Aqui a operação é outra: o que se desfaz é a
**existência** do objeto. Reusar aquele módulo produziria um `replace` com texto
vazio, que **deixa o membro na árvore** — e é exatamente isso que o gate da R2
recusa, porque desfazer tem de ser pelo MESMO mecanismo e com o MESMO rigor.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from mastertool_bridge.changes.member_rollback import build_member_rollback_plan
from mastertool_bridge.planner.planner import build_authoring_plan

from tests.support_spec import spec_with_methods

ESQUEMA = (Path(__file__).resolve().parent.parent.parent / "src"
           / "mastertool_bridge" / "contract" / "authoring-plan.schema.json")


@pytest.fixture(scope="module")
def plano_ida():
    resultado = build_authoring_plan(spec_with_methods())
    assert resultado.plan is not None, resultado.problems
    return resultado.plan


def test_a_reversao_remove_os_membros_que_a_ida_criou(plano_ida) -> None:
    criados = [p["target_name"] for p in plano_ida["steps"]
               if p["operation"] == "create_method"]
    assert criados, "a ida precisa criar membro, senão o teste mede nada"

    reversao = build_member_rollback_plan(plano_ida)
    assert reversao.ok, reversao.problems
    removidos = [p["target_name"] for p in reversao.plan["steps"]
                 if p["operation"] == "remove_method"]
    assert sorted(removidos) == sorted(criados)


def test_a_ordem_e_INVERSA_a_da_criacao(plano_ida) -> None:
    """Não porque a remoção de irmãos dependa da ordem — não depende —, mas
    porque a ordem inversa é a única que continua correta se um dia a superfície
    ganhar membro que dependa de membro. Depender de os irmãos serem
    independentes seria uma premissa que nada verifica."""
    criados = [p["target_name"] for p in plano_ida["steps"]
               if p["operation"] == "create_method"]
    reversao = build_member_rollback_plan(plano_ida)
    removidos = [p["target_name"] for p in reversao.plan["steps"]
                 if p["operation"] == "remove_method"]
    assert removidos == list(reversed(criados))


def test_a_reversao_esta_AMARRADA_a_ida(plano_ida) -> None:
    """Sem isto, um plano de reversão poderia ser executado contra uma saída que
    ele não desfez — e o registro diria que desfez."""
    reversao = build_member_rollback_plan(plano_ida)
    assert reversao.plan["spec_sha256"] == plano_ida["plan_sha256"]


def test_a_reversao_pede_object_remove_e_NUNCA_remove_cru(plano_ida) -> None:
    reversao = build_member_rollback_plan(plano_ida)
    allowlist = reversao.plan["required_allowlist"]
    assert "object:remove" in allowlist
    assert "remove" not in allowlist, (
        "`remove` cru autorizaria também apagar CARACTERES de um documento "
        "textual — outra operação com o mesmo nome (docs/87 §4)")


def test_a_reversao_NAO_usa_replace(plano_ida) -> None:
    """`replace` com texto vazio deixaria o membro na árvore, vazio. O gate da
    R2 pede que a coisa criada deixe de existir."""
    reversao = build_member_rollback_plan(plano_ida)
    operacoes = {p["operation"] for p in reversao.plan["steps"]}
    assert "replace" not in operacoes


def test_o_plano_de_reversao_valida_contra_o_schema(plano_ida) -> None:
    esquema = json.loads(ESQUEMA.read_text(encoding="utf-8"))
    reversao = build_member_rollback_plan(plano_ida,
                                          output_path="C:/saida/REV.project")
    erros = list(jsonschema.Draft202012Validator(esquema).iter_errors(
        reversao.plan))
    assert erros == [], [e.message[:200] for e in erros[:3]]


def test_sem_save_as_a_allowlist_NAO_pede_persistencia(plano_ida) -> None:
    """Reversão em memória é legítima para medição, e forçar `save_as` aqui
    esconderia a diferença entre "removi" e "removi e gravei"."""
    reversao = build_member_rollback_plan(plano_ida)
    assert reversao.plan["required_allowlist"] == ["object:remove"]
    assert all(p["operation"] != "save_as" for p in reversao.plan["steps"])


def test_a_reversao_declara_que_MUTA(plano_ida) -> None:
    """Publicar `mutating_steps: 0` faria uma execução que remove objetos
    parecer inócua no manifesto."""
    reversao = build_member_rollback_plan(plano_ida)
    assert reversao.plan["expected_diff"]["mutating_steps"] > 0


# =============================================================================
# recusas
# =============================================================================

def test_plano_SEM_membro_criado_e_recusado() -> None:
    """Emitir um plano de reversão vazio faria uma execução sem efeito parecer
    uma reversão bem-sucedida."""
    resultado = build_member_rollback_plan(
        {"steps": [{"operation": "create_gvl", "target_name": "GVL_X"}]})
    assert not resultado.ok
    assert "não há o que reverter" in resultado.problems[0]


def test_create_method_sem_owner_e_recusado() -> None:
    """Sem o dono não há como remover o membro certo — há homônimo possível em
    outro owner, e removê-lo seria o pior desfecho de uma reversão."""
    resultado = build_member_rollback_plan({"steps": [
        {"operation": "create_method", "target_name": "M", "sequence": 1,
         "owner_name": None, "owner_kind": "function_block"}]})
    assert not resultado.ok
    assert "owner_name" in resultado.problems[0]


def test_owner_fora_do_escopo_e_recusado() -> None:
    """A reversão não amplia escopo: se a ida saiu do escopo qualificado, a
    volta não o legitima."""
    resultado = build_member_rollback_plan({"steps": [
        {"operation": "create_method", "target_name": "M", "sequence": 1,
         "owner_name": "PRG_X", "owner_kind": "program"}]})
    assert not resultado.ok
    assert "FUNCTION_BLOCK" in resultado.problems[0]


def test_membro_duplicado_na_ida_torna_a_reversao_AMBIGUA() -> None:
    resultado = build_member_rollback_plan({"steps": [
        {"operation": "create_method", "target_name": "M", "sequence": 1,
         "owner_name": "FB_X", "owner_kind": "function_block"},
        {"operation": "create_method", "target_name": "M", "sequence": 2,
         "owner_name": "FB_X", "owner_kind": "function_block"}]})
    assert not resultado.ok
    assert "ambígua" in resultado.problems[0]


@pytest.mark.parametrize("entrada", [None, [], "plano", 42])
def test_entrada_malformada_NUNCA_levanta(entrada) -> None:
    """Mesma disciplina do planner: plano ausente com `problems` preenchido é o
    desfecho, e não uma exceção que o chamador teria de adivinhar."""
    resultado = build_member_rollback_plan(entrada)
    assert not resultado.ok
    assert resultado.problems

"""Testes do "antes medido" de propriedade de task (fase R2)."""

import pytest

from mastertool_bridge.spec.task_property_source import (
    TASK_PROPERTIES,
    load_task_property_inventory,
    verify_task_modifications,
)


def _inventario(**mudancas):
    task = {"name": "MainTask", "kind_of_task": "Cyclic",
            "interval": "t#100ms", "interval_unit": "ms", "priority": "13"}
    task.update(mudancas)
    return load_task_property_inventory({"tasks": [task]})


def _spec(**mudancas):
    entrada = {"name": "MainTask",
               "expected_before": {"interval": "t#100ms", "priority": "13"},
               "set": {"interval": "t#200ms"}}
    entrada.update(mudancas)
    return {"task_modifications": [entrada]}


def test_propriedade_conferida_contra_o_inventario():
    resultado = verify_task_modifications(_spec(), _inventario())
    assert resultado.ok, resultado.problems
    assert sorted(resultado.verified) == ["MainTask.interval",
                                          "MainTask.priority"]


def test_propriedade_que_mudou_desde_a_medicao_recusa():
    resultado = verify_task_modifications(_spec(),
                                          _inventario(interval="t#500ms"))
    assert not resultado.ok
    assert any("inventário mediu" in p for p in resultado.problems)


def test_task_ausente_do_inventario_recusa():
    resultado = verify_task_modifications(_spec(name="Fantasma"), _inventario())
    assert not resultado.ok
    assert any("não foi lido" in p for p in resultado.problems)


def test_propriedade_nao_medida_NAO_e_igualdade():
    """`None` é "não medido". Tratá-lo como igual autorizaria escrita cega —
    e é a diferença de forma entre comparar hash e comparar valor."""
    inventario = load_task_property_inventory(
        {"tasks": [{"name": "MainTask", "priority": "13"}]})
    resultado = verify_task_modifications(_spec(), inventario)
    assert not resultado.ok
    assert any("não foi medido" in p for p in resultado.problems)


def test_expected_before_vazio_recusa():
    resultado = verify_task_modifications(_spec(expected_before={}),
                                          _inventario())
    assert not resultado.ok
    assert any("obrigatório e não vazio" in p for p in resultado.problems)


def test_propriedade_fora_do_vocabulario_recusa():
    """`watchdog` é legível mas nunca foi escrito. Aceitá-lo aqui daria a
    impressão de que a comparação o cobre."""
    resultado = verify_task_modifications(
        _spec(expected_before={"watchdog": "x"}), _inventario())
    assert not resultado.ok
    assert any("fora do vocabulário medido" in p for p in resultado.problems)
    assert "watchdog" not in TASK_PROPERTIES


def test_inventario_vazio_e_leitura_falha():
    vazio = load_task_property_inventory({"tasks": []})
    assert not vazio.ok
    assert any("leitura falha" in p for p in vazio.problems)
    assert not verify_task_modifications(_spec(), vazio).ok


@pytest.mark.parametrize("entrada", [None, [], "x", 7, {}, {"tasks": "x"},
                                     {"tasks": [{"sem_nome": 1}]}])
def test_inventario_degenerado_nao_levanta(entrada):
    assert not load_task_property_inventory(entrada).ok


def test_spec_sem_alteracao_de_task_passa_sem_verificar_nada():
    resultado = verify_task_modifications({}, _inventario())
    assert resultado.ok
    assert resultado.verified == []


def test_as_quatro_propriedades_sao_as_medidas_e_escreviveis():
    """Interseção do que `probes/42` lê com o que o executor escreve — não a
    união: propriedade legível e não escrevível não pertence a um vocabulário
    de alteração."""
    assert set(TASK_PROPERTIES) == {"kind_of_task", "interval",
                                    "interval_unit", "priority"}


def test_valores_numericos_e_texto_comparam_igual():
    """O produto devolve `priority` como str; uma spec pode declarar int. A
    comparação normaliza, porque recusar por tipo seria recusar por
    formatação."""
    resultado = verify_task_modifications(
        _spec(expected_before={"priority": 13}), _inventario())
    assert resultado.ok, resultado.problems


def test_serializacao():
    d = verify_task_modifications(_spec(), _inventario()).to_dict()
    assert d["ok"] is True
    assert d["schema_version"] == 1

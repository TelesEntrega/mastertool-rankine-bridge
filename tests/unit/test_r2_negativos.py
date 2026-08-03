"""Os testes NEGATIVOS da fase R2 — o gate que o roadmap lista.

Cada um exercita uma forma de a alteração transacional dar errado. Um
mecanismo de alteração que só sabe acertar não protege projeto nenhum: o que
protege é ele recusar, com nome próprio, nos nove casos abaixo.

Referência: `docs/ROADMAP.md` §R2, "Testes negativos".
"""

import hashlib
import importlib.util
import io
import json
import os
import sys

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.join(_REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_REPO, "src"))
if os.path.join(_REPO, "scripts", "mastertool") not in sys.path:
    sys.path.insert(0, os.path.join(_REPO, "scripts", "mastertool"))

from mastertool_bridge.planner.planner import build_authoring_plan  # noqa: E402
from mastertool_bridge.spec.modification_source import (  # noqa: E402
    TextInventory,
    load_text_inventory,
    verify_modifications,
)

_PROBE46 = os.path.join(_REPO, "scripts", "mastertool", "probes",
                        "46_execute_authoring_plan.py")


def _carregar_probe():
    spec = importlib.util.spec_from_file_location("probe46_r2", _PROBE46)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


probe46 = _carregar_probe()

TEMPLATE_SHA = "5966257" + "0" * 57


def _sha(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _spec(**mudancas):
    entrada = {"family": "programs", "name": "UserPrg",
               "field": "implementation",
               "expected_before_sha256": _sha("// atual\n"),
               "text": "xNovo := TRUE;"}
    entrada.update(mudancas)
    return {"schema_version": 1,
            "template": {"id": "TemplateExemplo_v1", "sha256": TEMPLATE_SHA},
            "modifications": [entrada]}


def _inventario(texto_atual="// atual\n", nome="UserPrg",
                projeto=TEMPLATE_SHA):
    return load_text_inventory({
        "objects": [{
            "family": "programs", "name": nome,
            "texts": [{"field": "implementation",
                       "sha256_observed": _sha(texto_atual)}],
        }]
    }, project_sha256=projeto)


# =============================================================================
# 1-3: o alvo
# =============================================================================

def test_1_seletor_encontra_zero_objetos():
    """Alterar o que não foi lido é escrever às cegas — e o objeto pode nem
    existir."""
    verificacao = verify_modifications(_spec(name="NaoExiste"), _inventario())
    assert not verificacao.ok
    assert any("não está no inventário" in p for p in verificacao.problems)


def test_2_objeto_alterado_entre_a_medicao_e_o_planejamento():
    """A spec foi escrita contra um estado, e o inventário mediu outro."""
    verificacao = verify_modifications(
        _spec(), _inventario(texto_atual="// alguem editou\n"))
    assert not verificacao.ok
    assert any("ou o objeto mudou depois da medição" in p
               for p in verificacao.problems)


def test_3_inventario_de_outro_projeto():
    """Um hash anterior só vale para o arquivo onde foi medido."""
    verificacao = verify_modifications(
        _spec(), _inventario(projeto="f" * 64),
        expected_project_sha256=TEMPLATE_SHA)
    assert not verificacao.ok
    assert any("é do projeto" in p for p in verificacao.problems)


# =============================================================================
# 4-6: a spec
# =============================================================================

def test_4_hash_anterior_ausente_ou_malformado():
    verificacao = verify_modifications(
        _spec(expected_before_sha256="curto"), _inventario())
    assert not verificacao.ok
    assert any("malformado" in p for p in verificacao.problems)


def test_5_duas_alteracoes_do_mesmo_documento():
    spec = _spec()
    spec["modifications"].append(dict(spec["modifications"][0], text="y := 2;"))
    resultado = build_authoring_plan(spec)
    assert resultado.plan is None
    assert any("mais de uma vez" in p for p in resultado.problems)


def test_6_alterar_objeto_que_a_spec_cria():
    spec = _spec(name="PRG_NOVO")
    spec["programs"] = [{
        "name": "PRG_NOVO",
        "language": {"guid": "cc393387-a21c-4f68-a3e3-84c36951965d"},
        "declaration": "PROGRAM PRG_NOVO\nVAR\nEND_VAR",
        "implementation": ";"}]
    resultado = build_authoring_plan(spec)
    assert resultado.plan is None


# =============================================================================
# 7-9: a execução
# =============================================================================

def test_7_conteudo_anterior_divergente_para_a_execucao():
    """O executor recusa com status PRÓPRIO, distinto do de texto novo."""
    assert probe46.STATUS_BEFORE_HASH_MISMATCH in probe46.ALL_STATUSES
    assert (probe46.STATUS_BEFORE_HASH_MISMATCH
            != probe46.STATUS_TEXT_HASH_MISMATCH)


def test_8_procedencia_medida_sem_hash_no_passo():
    """Declarar `measured` sem hash promete uma conferência que não acontece,
    e o executor trata isso como divergência, não como ausência benigna."""
    fonte = io.open(_PROBE46, encoding="utf-8").read()
    assert "EXPECTED_BEFORE_MEASURED" in fonte
    posicao_checagem = fonte.index("expected_before_kind\") == EXPECTED_BEFORE_MEASURED")
    posicao_escrita = fonte.index("replace_guarded(documento, textos.get(sequencia), safety)",
                                  posicao_checagem)
    assert posicao_checagem < posicao_escrita, (
        "a conferência do hash anterior tem de vir ANTES da escrita")


def test_9_inventario_vazio_nao_faz_tudo_passar():
    """O modo de falha mais traiçoeiro: sem dado, toda conferência "passa"."""
    vazio = load_text_inventory({"objects": []})
    assert not vazio.ok
    verificacao = verify_modifications(_spec(), vazio)
    assert not verificacao.ok
    assert any("inutilizável" in p for p in verificacao.problems)


# =============================================================================
# o caminho aprovado, para que as recusas signifiquem algo
# =============================================================================

def test_o_caminho_aprovado_confere_e_planeja():
    spec = _spec()
    verificacao = verify_modifications(spec, _inventario(),
                                       expected_project_sha256=TEMPLATE_SHA)
    assert verificacao.ok, verificacao.problems
    assert verificacao.verified == ["programs:UserPrg:implementation"]

    resultado = build_authoring_plan(spec)
    assert resultado.problems == [], resultado.problems
    passos = [p for p in resultado.plan["steps"] if p["operation"] == "replace"]
    assert passos[0]["expected_before_kind"] == "measured"


def test_spec_sem_modificacoes_passa_mas_nao_verifica_nada():
    """"Não há o que conferir" é diferente de "conferi e está tudo bem"."""
    verificacao = verify_modifications({"modifications": []}, _inventario())
    assert verificacao.ok
    assert verificacao.verified == []


def test_preencher_nao_substitui_conferir():
    """Quem preenche e quem aprova não devem ser a mesma etapa."""
    from mastertool_bridge.spec.modification_source import fill_expected_before

    spec = _spec(expected_before_sha256="0" * 64)
    preenchida, problemas = fill_expected_before(spec, _inventario())
    assert problemas == []
    assert preenchida["modifications"][0]["expected_before_sha256"] == \
        _sha("// atual\n")
    # A spec ORIGINAL não foi tocada.
    assert spec["modifications"][0]["expected_before_sha256"] == "0" * 64


@pytest.mark.parametrize("payload", [None, [], "inventário", 7, {}, {"objects": "x"}])
def test_inventario_degenerado_nao_levanta(payload):
    inventario = load_text_inventory(payload)
    assert not inventario.ok


def test_inventario_com_hash_invalido_reprova():
    inventario = load_text_inventory({"objects": [{
        "family": "programs", "name": "UserPrg",
        "texts": [{"field": "implementation", "sha256_observed": "nao-e-sha"}]}]})
    assert not inventario.ok
    assert any("não é medição" in p for p in inventario.problems)


# =============================================================================
# o comando que o operador roda antes da sessão
# =============================================================================

def _escrever(tmp_path, nome, conteudo):
    caminho = os.path.join(str(tmp_path), nome)
    io.open(caminho, "w", encoding="utf-8", newline="\n").write(
        json.dumps(conteudo, ensure_ascii=False))
    return caminho


def _inventario_bruto(texto="// atual\n", nome="UserPrg"):
    return {"objects": [{"family": "programs", "name": nome,
                         "texts": [{"field": "implementation",
                                    "sha256_observed": _sha(texto)}]}]}


def test_cli_aprova_spec_conferida(tmp_path, capsys):
    from mastertool_bridge.cli import main

    caminho_spec = _escrever(tmp_path, "spec.json", _spec())
    caminho_inv = _escrever(tmp_path, "inv.json", _inventario_bruto())
    codigo = main(["verify-modifications", "--spec", caminho_spec,
                   "--inventory", caminho_inv,
                   "--output", os.path.join(str(tmp_path), "r.json")])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert "[OK]" in saida
    assert "programs:UserPrg:implementation" in saida


def test_cli_recusa_e_impede_a_sessao(tmp_path, capsys):
    from mastertool_bridge.cli import main

    caminho_spec = _escrever(tmp_path, "spec.json", _spec())
    caminho_inv = _escrever(tmp_path, "inv.json",
                            _inventario_bruto(texto="// outro\n"))
    codigo = main(["verify-modifications", "--spec", caminho_spec,
                   "--inventory", caminho_inv])
    saida = capsys.readouterr().out
    assert codigo == 2
    assert "não deve começar" in saida


def test_cli_recusa_inventario_de_outro_projeto(tmp_path, capsys):
    from mastertool_bridge.cli import main

    caminho_spec = _escrever(tmp_path, "spec.json", _spec())
    caminho_inv = _escrever(tmp_path, "inv.json", _inventario_bruto())
    codigo = main(["verify-modifications", "--spec", caminho_spec,
                   "--inventory", caminho_inv,
                   "--inventory-project-sha256", "a" * 64,
                   "--expected-project-sha256", "b" * 64])
    assert codigo == 2
    assert "é do projeto" in capsys.readouterr().out

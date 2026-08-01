"""Testes de `scripts/mastertool/emit_authoring_plan.py`.

O emissor e a unica ponte entre o planner (CPython 3) e o host PowerShell. O
que estes testes protegem e a distincao entre os dois modos de recusa:

    spec invalida          -> corrigir a SPEC, e nenhum plano e gravado
    plano nao executavel   -> MEDIR uma operacao contra o produto, e o plano
                              E gravado, porque ele e a evidencia do que falta

Um codigo de saida so faria as duas parecerem a mesma coisa.
"""

import io
import json
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
_MASTERTOOL_DIR = os.path.join(_REPO_ROOT, "scripts", "mastertool")
if _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)

import emit_authoring_plan as emissor  # noqa: E402

ST_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"
TEMPLATE_SHA = "5966257" + "0" * 57


def _spec_executavel():
    return {
        "schema_version": 1,
        "template": {"id": "TemplateExemplo_v1", "sha256": TEMPLATE_SHA},
        "gvls": [{"name": "GVL_X", "declaration": "VAR_GLOBAL\nEND_VAR"}],
        "programs": [{"name": "PRG_X", "language": {"guid": ST_GUID},
                      "declaration": "PROGRAM PRG_X\nVAR\nEND_VAR",
                      "implementation": "xA := TRUE;"}],
        "tasks": [{"name": "MainTask", "existing": True,
                   "program_calls": ["PRG_X"]}],
    }


def _escrever(tmp_path, nome, conteudo):
    caminho = os.path.join(str(tmp_path), nome)
    io.open(caminho, "w", encoding="utf-8", newline="\n").write(
        json.dumps(conteudo, ensure_ascii=False))
    return caminho


def _rodar(tmp_path, spec):
    entrada = _escrever(tmp_path, "spec.json", spec)
    saida = os.path.join(str(tmp_path), "plano.json")
    codigo = emissor.main(["--spec", entrada, "--out", saida])
    return codigo, saida


def test_spec_executavel_emite_plano_e_sai_zero(tmp_path):
    codigo, saida = _rodar(tmp_path, _spec_executavel())
    assert codigo == emissor.EXIT_OK
    plano = json.loads(io.open(saida, encoding="utf-8").read())
    assert plano["executable"] is True
    assert plano["kind"] == "authoring_plan"
    assert plano["required_allowlist"] == ["build", "create_gvl",
                                           "create_program", "replace",
                                           "save_as"]


def test_spec_invalida_NAO_grava_plano(tmp_path):
    """Plano de spec invalida seria um artefato que descreve uma intencao que
    o validador ja recusou."""
    spec = _spec_executavel()
    spec["programs"][0]["language"] = "ST"          # texto, e nao GUID
    codigo, saida = _rodar(tmp_path, spec)
    assert codigo == emissor.EXIT_SPEC_INVALID
    assert not os.path.exists(saida)


def test_plano_com_lacuna_E_gravado_e_sai_TRES(tmp_path):
    """O plano com lacuna e a evidencia do que falta medir; apaga-lo apagaria a
    explicacao. E o codigo e OUTRO: 3 pede medir, 2 pede corrigir a spec."""
    # O exemplo ja foi FUNCTION_BLOCK (provado na run-028, docs/43), DUT
    # (run-033, docs/46) e `create_task` (run-036, docs/48) -- a lista de
    # operacoes sem prova encolheu ate ficar vazia, e o exemplo acompanhou.
    #
    # A lacuna de hoje nao e sobre operacao: e sobre ALVO. Vincular um programa
    # a uma task que ja estava no projeto e que nao e a do perfil nao tem
    # caminho medido -- ninguem leu o que ja esta na lista dela.
    spec = _spec_executavel()
    spec["tasks"] = [{"name": "TaskDoCliente", "existing": True,
                      "program_calls": ["PRG_X"]}]
    codigo, saida = _rodar(tmp_path, spec)
    assert codigo == emissor.EXIT_PLAN_NOT_EXECUTABLE
    assert os.path.exists(saida)
    plano = json.loads(io.open(saida, encoding="utf-8").read())
    assert plano["executable"] is False
    assert any(g["kind"] == "unmeasured_task_binding"
               for g in plano["measurement_gaps"])


def test_os_tres_codigos_de_saida_sao_distintos():
    assert len({emissor.EXIT_OK, emissor.EXIT_SPEC_INVALID,
                emissor.EXIT_PLAN_NOT_EXECUTABLE}) == 3
    assert emissor.EXIT_OK == 0


def test_spec_ilegivel_nao_levanta(tmp_path):
    caminho = os.path.join(str(tmp_path), "quebrada.json")
    io.open(caminho, "w", encoding="utf-8").write("{ isto nao e json")
    codigo = emissor.main(["--spec", caminho,
                           "--out", os.path.join(str(tmp_path), "p.json")])
    assert codigo == emissor.EXIT_SPEC_INVALID


def test_o_plano_gravado_NAO_tem_BOM(tmp_path):
    """`Out-File -Encoding utf8` do PS 5.1 grava BOM e o artefato fica ilegivel
    para leitor JSON estrito -- achado da run-008. Do lado do Python o cuidado
    e o mesmo."""
    _codigo, saida = _rodar(tmp_path, _spec_executavel())
    bruto = io.open(saida, "rb").read()
    assert not bruto.startswith(b"\xef\xbb\xbf")
    assert bruto.endswith(b"\n")


def test_o_plano_gravado_e_deterministico(tmp_path):
    """Duas emissoes da mesma spec produzem o MESMO arquivo. Sem isso, um diff
    entre dois planos nao distinguiria mudanca de intencao de ruido de
    serializacao."""
    spec = _spec_executavel()
    _c1, s1 = _rodar(tmp_path, spec)
    primeiro = io.open(s1, "rb").read()
    os.remove(s1)
    _c2, s2 = _rodar(tmp_path, spec)
    assert io.open(s2, "rb").read() == primeiro


def test_o_emissor_nao_abre_o_mastertool():
    """Camada HOST: nenhuma referencia a produto, processo ou IronPython."""
    texto = io.open(emissor.__file__, encoding="utf-8").read()
    for proibido in ("MT9000", "subprocess", "System.Guid", "runscript",
                     "os.system", "Popen"):
        assert proibido not in texto, proibido

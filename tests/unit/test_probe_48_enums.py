"""Testes de `probes/48_probe_enums_readonly.py`.

O que ele protege: a diferenca entre "esta no stub" e "da para nomear em
runtime". As duas sao perguntas distintas, e responder a primeira achando que
respondeu a segunda foi o erro que bloqueou `create_dut` desde `docs/35`.

Ele NAO cria nada -- le o escopo e relata.
"""

import ast
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

from common import file_io, probe_cli  # noqa: E402

PROBE48_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "48_probe_enums_readonly.py")


def _load(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe48 = _load(PROBE48_PATH, "probe48_enums")


class FakeEnum(object):
    """Enum sintetico: so precisa expor os membros por nome."""

    def __init__(self, membros):
        for nome in membros:
            setattr(self, nome, nome)

    def __str__(self):
        return "<FakeEnum>"


def _escopo(completo=True, dut_membros=None, kind_membros=None):
    dut = dut_membros
    if dut is None:
        dut = probe48.ENUMS_ESPERADOS["DutType"]["members"]
    kind = kind_membros
    if kind is None:
        kind = probe48.ENUMS_ESPERADOS["KindOfTask"]["members"]
    escopo = {"projects": object()}
    if completo:
        escopo["DutType"] = FakeEnum(dut)
        escopo["KindOfTask"] = FakeEnum(kind)
    return escopo


def _run(tmp_path, escopo=None):
    if escopo is None:
        escopo = _escopo()
    argv = ["probe", "--output=" + os.path.join(str(tmp_path), "art")]
    return probe48.run_probe(escopo, argv, file_io, probe_cli)


def test_os_dois_enums_alcancaveis_pelo_escopo_do_script(tmp_path):
    resultado = _run(tmp_path)
    assert resultado["status"] == probe48.STATUS_MEASURED
    assert resultado["exit_code"] == 0
    completion = probe48.build_completion(resultado)
    assert sorted(completion["reachable"]) == ["DutType", "KindOfTask"]
    assert completion["unreachable"] == []


def test_para_no_PRIMEIRO_caminho_que_resolve(tmp_path):
    """"Nao tentei" e diferente de "tentei e falhou", e o artefato distingue os
    dois: os caminhos seguintes nem aparecem quando o primeiro resolve."""
    resultado = _run(tmp_path)
    for entrada in resultado["enums"]:
        assert len(entrada["attempts"]) == 1
        assert entrada["attempts"][0]["found"] is True


def test_registra_TODOS_os_caminhos_tentados_quando_falha(tmp_path):
    resultado = _run(tmp_path, escopo=_escopo(completo=False))
    assert resultado["status"] == probe48.STATUS_UNREACHABLE
    assert resultado["exit_code"] != 0
    for entrada in resultado["enums"]:
        caminhos = [t["path"] for t in entrada["attempts"]]
        assert len(caminhos) == 3
        assert any("script_globals" in c for c in caminhos)
        assert any("scriptengine" in c for c in caminhos)
        assert any("ScriptEngine3" in c for c in caminhos)


def test_inalcancavel_NAO_vira_inexistente(tmp_path):
    """"Nao alcancei" e evidencia; "nao existe" seria conclusao, e este probe
    nao a tira."""
    resultado = _run(tmp_path, escopo=_escopo(completo=False))
    texto = " ".join(resultado["problems"])
    assert "NAO significa que eles nao existem" in texto


def test_membro_faltando_vira_LACUNA_e_nao_reprova(tmp_path):
    """Alcancar o enum e ver membro a menos e achado sobre o CATALOGO -- o
    stub e o runtime discordam --, e nao falha de execucao."""
    resultado = _run(tmp_path, escopo=_escopo(dut_membros=("Structure",)))
    assert resultado["status"] == probe48.STATUS_MEASURED
    dut = [e for e in resultado["enums"] if e["name"] == "DutType"][0]
    assert dut["members_found"] == ["Structure"]
    assert sorted(dut["members_missing"]) == ["Alias", "Enumeration", "Union"]
    assert dut["matches_stub"] is False
    assert any("divergem do stub" in n for n in resultado["gap_notes"])


def test_os_membros_esperados_sao_os_do_STUB():
    """Congelados num literal: se o stub mudar, o teste obriga a olhar."""
    assert (probe48.ENUMS_ESPERADOS["DutType"]["members"]
            == ("Structure", "Enumeration", "Alias", "Union"))
    assert (probe48.ENUMS_ESPERADOS["KindOfTask"]["members"]
            == ("Cyclic", "Freewheeling", "Event", "ExternalEvent", "Status",
                "ParentSynchron"))
    for nome, dados in probe48.ENUMS_ESPERADOS.items():
        assert dados["stub"].endswith((".pyi L23", ".pyi L5")), nome


def test_a_leitura_de_membro_e_por_nome_LITERAL_da_tupla(tmp_path):
    """Enumerar membros do objeto descobriria nomes que ninguem catalogou, e
    este probe existe para CONFERIR o catalogo, nao para expandi-lo em
    silencio."""
    escopo = _escopo()
    escopo["DutType"].MembroSurpresa = "surpresa"
    resultado = _run(tmp_path, escopo=escopo)
    dut = [e for e in resultado["enums"] if e["name"] == "DutType"][0]
    assert "MembroSurpresa" not in dut["members_found"]
    assert "MembroSurpresa" not in dut["values"]


def test_a_completion_e_gravada(tmp_path):
    resultado = _run(tmp_path)
    escritos = probe48.write_artifacts(resultado, file_io)
    assert escritos == list(probe48.ARTIFACT_NAMES)


# =============================================================================
# verificacao estatica -- ele NAO cria nada
# =============================================================================

@pytest.fixture(scope="module")
def tree48():
    return ast.parse(io.open(PROBE48_PATH, encoding="utf-8").read())


def test_nenhuma_criacao_nem_persistencia_no_fonte():
    texto = io.open(PROBE48_PATH, encoding="utf-8").read()
    for proibido in (".create_dut(", ".create_task(", ".create_gvl(",
                     ".create_program(", ".create_function(", ".save(",
                     ".save_as(", ".build(", ".replace("):
        assert proibido not in texto, proibido


def test_o_import_dinamico_recebe_nome_da_tupla_LITERAL(tree48):
    """`__import__` existe aqui, e o nome do modulo e literal em todas as
    chamadas. O que varia e o membro pedido, e ele vem de `ENUMS_ESPERADOS`."""
    for no in ast.walk(tree48):
        if not isinstance(no, ast.Call):
            continue
        if not isinstance(no.func, ast.Name) or no.func.id != "__import__":
            continue
        assert isinstance(no.args[0], ast.Constant), ast.dump(no)
        assert no.args[0].value in ("scriptengine", "ScriptEngine3")


def test_vocabulario_de_status_fechado():
    assert set(probe48.EXIT_BY_STATUS) == set(probe48.ALL_STATUSES)
    assert probe48.EXIT_BY_STATUS[probe48.STATUS_MEASURED] == 0
    for status in probe48.ALL_STATUSES:
        if status not in probe48.SUCCESS_STATUSES:
            assert probe48.EXIT_BY_STATUS[status] != 0, status


def test_identificadores_ascii(tree48):
    for no in ast.walk(tree48):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(no, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor

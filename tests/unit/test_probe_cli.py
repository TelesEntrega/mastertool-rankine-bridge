"""Testes de `scripts/mastertool/common/probe_cli.py`.

Fixtures inteiramente sinteticas: nenhum nome de equipamento, projeto ou
caminho de cliente aparece aqui. O fake de navegacao LEVANTA se qualquer
membro fora da cadeia autorizada for tocado — e o que transforma "o probe
nao deveria fazer isso" em teste, e nao em promessa.
"""

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
_MASTERTOOL_DIR = os.path.join(_REPO_ROOT, "scripts", "mastertool")
if _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)

from common import probe_cli  # noqa: E402


# --- fakes ------------------------------------------------------------------

class ForbiddenMemberTouched(AssertionError):
    """Levantada quando o codigo sob teste toca algo que nao deveria."""


ALLOWED_NODE_MEMBERS = ("get_children", "get_name", "children_result", "name")


class FakeCollection(object):
    def __init__(self, items, count=None):
        self._items = list(items)
        self.Count = len(self._items) if count is None else count

    def __getitem__(self, index):
        return self._items[index]


class FakeNode(object):
    """So expoe a cadeia autorizada. Qualquer outro atributo levanta."""

    def __init__(self, name, children=None, count=None, children_result="ok"):
        self.name = name
        self._children = list(children or [])
        self._count = count
        self._children_result = children_result

    def get_children(self, recursive):
        assert recursive is False, "get_children deve ser chamado com False"
        if self._children_result == "none":
            return None
        return FakeCollection(self._children, self._count)

    def get_name(self, recursive):
        assert recursive is False
        return self.name

    def __getattr__(self, item):
        if item.startswith("_") or item in ALLOWED_NODE_MEMBERS:
            raise AttributeError(item)
        raise ForbiddenMemberTouched(
            "o codigo tocou o membro proibido %r" % item)


# --- find_arg ---------------------------------------------------------------

@pytest.mark.parametrize("argv,expected", [
    (["--output", "C:\\saida"], "C:\\saida"),
    (["--output=C:\\saida"], "C:\\saida"),
    (["--output:C:\\saida"], "C:\\saida"),
    (["--outro=x"], None),
    ([], None),
    (["--output"], ""),
])
def test_find_arg_aceita_as_tres_formas(argv, expected):
    assert probe_cli.find_arg(argv, "output") == expected


def test_find_arg_nao_confunde_prefixo_parecido():
    assert probe_cli.find_arg(["--output-dir=x"], "output") is None


# --- validate_output_path ---------------------------------------------------

def test_output_obrigatorio():
    problems = []
    assert probe_cli.validate_output_path(None, "C:\\repo", problems) is None
    assert problems


def test_output_com_espaco_e_recusado():
    problems = []
    assert probe_cli.validate_output_path(
        "C:\\um caminho", "C:\\repo", problems) is None
    assert any("espaco" in p for p in problems)


def test_output_dentro_do_repo_e_recusado(tmp_path):
    repo = str(tmp_path / "repo")
    dentro = os.path.join(repo, "saida")
    problems = []
    assert probe_cli.validate_output_path(dentro, repo, problems) is None
    assert any("repositorio" in p for p in problems)


def test_output_igual_a_raiz_do_repo_e_recusado(tmp_path):
    repo = str(tmp_path / "repo")
    problems = []
    assert probe_cli.validate_output_path(repo, repo, problems) is None
    assert problems


def test_output_irmao_do_repo_nao_e_confundido_com_dentro(tmp_path):
    """`.../repo-saida` comeca com `.../repo` como texto, mas nao esta dentro
    dele. Sem o separador na comparacao isto passaria batido."""
    repo = str(tmp_path / "repo")
    irmao = str(tmp_path / "repo-saida")
    problems = []
    resolved = probe_cli.validate_output_path(irmao, repo, problems)
    assert problems == []
    assert resolved == os.path.abspath(irmao)


def test_output_fora_do_repo_e_aceito(tmp_path):
    repo = str(tmp_path / "repo")
    fora = str(tmp_path / "saida")
    problems = []
    assert probe_cli.validate_output_path(fora, repo, problems) == \
        os.path.abspath(fora)
    assert problems == []


# --- inteiros e booleanos ---------------------------------------------------

def test_positive_int_usa_default_quando_ausente():
    problems = []
    assert probe_cli.positive_int(None, 32, "--max-depth", problems) == 32
    assert problems == []


@pytest.mark.parametrize("raw", ["0", "-1", "abc", "1.5"])
def test_positive_int_recusa_invalido(raw):
    problems = []
    assert probe_cli.positive_int(raw, 32, "--max-depth", problems) is None
    assert problems


def test_positive_int_nao_oferece_ilimitado():
    """Zero seria a forma natural de pedir 'sem limite'. E recusado."""
    problems = []
    assert probe_cli.positive_int("0", 32, "--max-depth", problems) is None


@pytest.mark.parametrize("raw,expected", [
    ("1", True), ("true", True), ("sim", True),
    ("0", False), ("false", False), ("nao", False),
])
def test_parse_bool(raw, expected):
    problems = []
    assert probe_cli.parse_bool(raw, None, "--recursive", problems) is expected
    assert problems == []


def test_parse_bool_recusa_lixo():
    problems = []
    assert probe_cli.parse_bool("talvez", False, "--recursive", problems) is None
    assert problems


# --- node ids ---------------------------------------------------------------

def test_parse_node_id_valido():
    problems = []
    assert probe_cli.parse_node_id("root/1/0/2", problems) == [1, 0, 2]
    assert problems == []


@pytest.mark.parametrize("raw", [
    "", "1/0/2", "raiz/1", "root/x", "root/-1", "root", "root/",
])
def test_parse_node_id_recusa_invalido(raw):
    problems = []
    assert probe_cli.parse_node_id(raw, problems) is None
    assert problems


def test_parse_node_id_recusa_profundidade_absurda():
    problems = []
    fundo = "root/" + "/".join(["0"] * (probe_cli.MAX_PATH_STEPS + 1))
    assert probe_cli.parse_node_id(fundo, problems) is None
    assert problems


def test_parse_node_id_list_e_obrigatorio():
    """Nao ha default: uma lista embutida seria a estrutura de UM projeto
    especifico dentro do repositorio."""
    problems = []
    assert probe_cli.parse_node_id_list("", problems, 10) is None
    assert any("obrigatorio" in p for p in problems)


def test_parse_node_id_list_valido():
    problems = []
    parsed = probe_cli.parse_node_id_list("root/0, root/1/2", problems, 10)
    assert parsed == [("root/0", [0]), ("root/1/2", [1, 2])]
    assert problems == []


def test_parse_node_id_list_respeita_maximo():
    problems = []
    assert probe_cli.parse_node_id_list("root/0,root/1", problems, 1) is None
    assert problems


def test_parse_node_id_list_propaga_erro_de_item():
    problems = []
    assert probe_cli.parse_node_id_list("root/0,lixo", problems, 10) is None
    assert problems


# --- descend ----------------------------------------------------------------

def _arvore():
    folha = FakeNode("folha")
    meio = FakeNode("meio", [folha])
    return FakeNode("raiz", [FakeNode("outro"), meio])


def test_descend_alcanca_o_no_e_registra_o_caminho():
    trace = []
    node = probe_cli.descend(_arvore(), [1, 0], trace)
    assert node.get_name(False) == "folha"
    assert [t["index"] for t in trace] == [1, 0]
    assert [t["name"] for t in trace] == ["meio", "folha"]


def test_descend_recusa_indice_fora_da_faixa():
    trace = []
    assert probe_cli.descend(_arvore(), [9], trace) is None
    assert "fora da faixa" in trace[-1]["error"]


def test_descend_recusa_colecao_nula():
    trace = []
    raiz = FakeNode("raiz", children_result="none")
    assert probe_cli.descend(raiz, [0], trace) is None
    assert "None" in trace[-1]["error"]


@pytest.mark.parametrize("count", [-1, probe_cli.MAX_CHILDREN_PER_STEP + 1])
def test_descend_recusa_count_fora_da_faixa(count):
    trace = []
    raiz = FakeNode("raiz", [FakeNode("a")], count=count)
    assert probe_cli.descend(raiz, [0], trace) is None
    assert "Count fora de faixa" in trace[-1]["error"]


def test_runtime_identity_degrada_sem_levantar_fora_do_mastertool():
    """Em CPython nao ha `clr`. O campo fica nulo com o erro registrado —
    nunca uma versao inventada, e nunca uma excecao que derrube o probe."""
    info = probe_cli.runtime_identity()
    assert info["file_version"] is None
    assert info["error"] is not None
    assert info["script_runtime"]


# --- identidade de assembly (W0 / MasterTool X) -----------------------------

def test_assembly_name_matches_e_por_prefixo_nao_por_substring():
    prefixos = ("ScriptEngine", "IronPython")
    assert probe_cli.assembly_name_matches("ScriptEngine3", prefixos)
    assert probe_cli.assembly_name_matches("IronPython.Modules", prefixos)
    # substring no meio do nome NAO casa: um assembly de terceiro chamado
    # "MeuScriptEngineFalso" nao e nosso.
    assert not probe_cli.assembly_name_matches("MeuScriptEngineFalso", prefixos)
    assert not probe_cli.assembly_name_matches("mscorlib", prefixos)


def test_assembly_name_matches_nunca_levanta_com_entrada_degenerada():
    assert not probe_cli.assembly_name_matches(None, ("ScriptEngine",))
    assert not probe_cli.assembly_name_matches("", ("ScriptEngine",))
    assert not probe_cli.assembly_name_matches("ScriptEngine3", None)
    assert not probe_cli.assembly_name_matches("ScriptEngine3", ())


def test_scriptengine_version_prefere_scriptengine3():
    """ScriptEngine3 e onde vivem as interfaces reais (docs/24). Se ele
    estiver carregado, e ele que responde — mesmo vindo depois na lista."""
    entradas = [
        {"name": "ScriptEngine.plugin", "version": "9.9.9.9"},
        {"name": "ScriptEngine3", "version": "4.2.0.0"},
    ]
    resultado = probe_cli.scriptengine_version_from_assemblies(entradas)
    assert resultado["version"] == "4.2.0.0"
    assert "ScriptEngine3" in resultado["source"]


def test_scriptengine_version_cai_para_outro_e_diz_qual_usou():
    entradas = [{"name": "ScriptEngine.plugin", "version": "4.2.0.0"}]
    resultado = probe_cli.scriptengine_version_from_assemblies(entradas)
    assert resultado["version"] == "4.2.0.0"
    assert "ScriptEngine.plugin" in resultado["source"]


def test_scriptengine_version_ausente_nao_inventa():
    """Sem assembly ScriptEngine carregado, a resposta e None COM motivo —
    nunca um palpite a partir do banner de sys.version."""
    for entradas in ([], None, [{"name": "mscorlib", "version": "4.0.0.0"}]):
        resultado = probe_cli.scriptengine_version_from_assemblies(entradas)
        assert resultado["version"] is None
        assert "nenhum assembly" in resultado["source"]


def test_descend_nao_toca_membro_proibido():
    """Se algum dia alguem acrescentar `.export_xml`, `.save` ou
    `device_parameters` a esta funcao, este teste levanta."""
    trace = []
    probe_cli.descend(_arvore(), [1, 0], trace)  # nao levanta

    raiz = _arvore()
    with pytest.raises(ForbiddenMemberTouched):
        raiz.save()

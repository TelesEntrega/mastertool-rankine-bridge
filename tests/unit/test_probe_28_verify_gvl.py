"""Testes de `probes/28_verify_gvl_w1_1_readonly.py` com dubles ESTRITOS,
mais a verificacao estatica (AST) de que o probe nao contem mutador.

Nenhuma API real do MasterTool e importada ou chamada. Fixtures sinteticas.
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

PROBE_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                          "28_verify_gvl_w1_1_readonly.py")


def _load_probe():
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("probe28_w1_1", PROBE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except ImportError:                                        # IronPython 2.7
        import imp
        return imp.load_source("probe28_w1_1", PROBE_PATH)


probe = _load_probe()


# --- dubles -----------------------------------------------------------------

class ForbiddenMemberTouched(AssertionError):
    pass


class FakeChildren(object):
    def __init__(self, items):
        self._items = list(items)

    @property
    def Count(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]


class FakeDoc(object):
    def __init__(self, text):
        self.text = text
        self.linecount = len(text.split("\n"))

    def replace(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 28 chamou replace()")


class FakeNode(object):
    """Duble de no. Expoe `type`, e NAO `type_guid`.

    O nome importa: `IScriptObject` tem a propriedade `type`; `type_guid` e o
    nome do campo na saida do scanner. A primeira versao destes dubles expunha
    `type_guid` e por isso os 53 testes passaram enquanto o probe lia um membro
    inexistente -- o dublê reproduzia a suposicao errada em vez de contradize-la.
    Quem apanhou o defeito foi o primeiro preflight real.

    `__getattr__` levanta para membro nao declarado, entao ler `type_guid` aqui
    e um erro visivel, nao um None silencioso.
    """

    def __init__(self, name, children=None, type_guid="guid-container",
                 transient=False, is_folder=False, has_declaration=True,
                 declaration="VAR_GLOBAL\nEND_VAR", expose_create_gvl=True):
        self._name = name
        self._children = list(children or [])
        self.type = type_guid
        self.is_transient_object = transient
        self.is_folder = is_folder
        self.has_textual_declaration = has_declaration
        self._declaration = declaration
        if expose_create_gvl:
            self.create_gvl = self._create_gvl_nunca_invocado

    def _create_gvl_nunca_invocado(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 28 INVOCOU create_gvl()")

    def get_name(self, _recursive):
        return self._name

    def get_children(self, _recursive):
        return FakeChildren(self._children)

    def __getattr__(self, name):
        raise ForbiddenMemberTouched(
            "probe 28 leu membro inexistente no proxy: %r" % (name,))

    @property
    def textual_declaration(self):
        if self._declaration is None:
            return None
        return FakeDoc(self._declaration)

    def save(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 28 chamou save()")

    def save_as(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 28 chamou save_as()")

    def build(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 28 chamou build()")


class FakeProject(FakeNode):
    def __init__(self, path, children):
        FakeNode.__init__(self, "projeto", children=children,
                          expose_create_gvl=False)
        self.path = path


class FakeProjectAccess(object):
    def __init__(self, project):
        self._project = project

    def get_primary_project(self, _globals):
        return self._project, None

    def get_project_path(self, project):
        return project.path


class FakeProbeCli(object):
    def __init__(self, container=None, parent=None, version="4.1.0.11"):
        self._container = container
        self._parent = parent
        self._version = version

    def find_arg(self, argv, name):
        return probe_cli.find_arg(argv, name)

    def parse_node_id(self, raw, problems, label="--node-id"):
        return probe_cli.parse_node_id(raw, problems, label=label)

    def validate_output_path(self, raw, repo_root, problems):
        return probe_cli.validate_output_path(raw, repo_root, problems)

    def runtime_identity(self):
        return {"executable": "MT9000.exe", "file_version": self._version,
                "product_version": self._version, "error": None}

    def descend(self, project, indexes, trace):
        if len(indexes) == 1:
            return self._parent if self._parent is not None else self._container
        return self._container


# --- helpers ----------------------------------------------------------------

def _plan(tmp_path, output_path=None, **overrides):
    plano = {
        "schema_version": "1.0",
        "phase": "W1_1_CREATE_GVL",
        "gvl_name": "GVL_AI_TESTE",
        "container": {"node_path": "root/1/0", "expected_name": "Application",
                      "expected_type_guid": "guid-container"},
        "mastertool": {"version": "4.1.0.11", "script_engine": "4.2.0.0"},
        "output_project": {"path": output_path or os.path.join(str(tmp_path), "saida.project")},
    }
    plano.update(overrides)
    caminho = os.path.join(str(tmp_path), "plano.json")
    handle = open(caminho, "w")
    try:
        handle.write(json.dumps(plano))
    finally:
        handle.close()
    return caminho, plano


def _run(tmp_path, mode, container, project=None, plan_path=None,
         baseline=None, output_sha=None, probe_cli_double=None, parent=None):
    if plan_path is None:
        plan_path, _p = _plan(tmp_path)
    if project is None:
        project = FakeProject(os.path.join(str(tmp_path), "aberto.project"),
                              [container])
    argv = ["probe", "--mode=" + mode, "--plan=" + plan_path,
            "--output=" + os.path.join(str(tmp_path), "art")]
    if baseline:
        argv.append("--baseline=" + baseline)
    if output_sha:
        argv.append("--output-sha256=" + output_sha)
    duplo = probe_cli_double or FakeProbeCli(container=container, parent=parent)
    return probe.run_verification({"projects": object()}, argv,
                                  FakeProjectAccess(project), file_io, duplo)


def _write_baseline(tmp_path, persistent_names, transient_names=()):
    dados = {
        "persistent": [{"name": n, "is_transient": False} for n in persistent_names],
        "transient": [{"name": n, "is_transient": True} for n in transient_names],
        "count": len(persistent_names) + len(transient_names),
        "error": None,
    }
    caminho = os.path.join(str(tmp_path), "baseline.json")
    handle = open(caminho, "w")
    try:
        handle.write(json.dumps(dados))
    finally:
        handle.close()
    return caminho


# --- preflight --------------------------------------------------------------

def test_preflight_passa_quando_tudo_confere(tmp_path):
    container = FakeNode("Application", children=[FakeNode("Outra")])
    resultado = _run(tmp_path, "preflight", container)
    assert resultado["status"] == probe.PREFLIGHT_PASSED
    assert resultado["exit_code"] == 0
    assert resultado["create_gvl_member"]["present"] is True
    assert resultado["create_gvl_member"]["callable"] is True


def test_preflight_nao_invoca_create_gvl(tmp_path):
    """O duble levanta se create_gvl for CHAMADO. Passar prova que o probe so
    referenciou o membro."""
    container = FakeNode("Application")
    resultado = _run(tmp_path, "preflight", container)
    assert resultado["status"] == probe.PREFLIGHT_PASSED


def test_preflight_membro_ausente(tmp_path):
    container = FakeNode("Application", expose_create_gvl=False)
    resultado = _run(tmp_path, "preflight", container)
    assert resultado["status"] == probe.CREATE_GVL_MEMBER_MISSING
    assert resultado["exit_code"] == 2


def test_preflight_container_nao_encontrado(tmp_path):
    resultado = _run(tmp_path, "preflight", None)
    assert resultado["status"] == probe.CONTAINER_NOT_FOUND


def test_preflight_container_com_nome_diferente(tmp_path):
    container = FakeNode("OutroNome")
    resultado = _run(tmp_path, "preflight", container)
    assert resultado["status"] == probe.CONTAINER_NOT_FOUND


def test_preflight_container_com_type_guid_diferente(tmp_path):
    container = FakeNode("Application", type_guid="guid-errado")
    resultado = _run(tmp_path, "preflight", container)
    assert resultado["status"] == probe.CONTAINER_NOT_FOUND


def test_preflight_container_ambiguo(tmp_path):
    """Dois irmaos com a mesma identidade tornam o caminho por indice
    instavel entre sessoes."""
    container = FakeNode("Application")
    gemeo = FakeNode("Application")
    parent = FakeNode("Plc Logic", children=[container, gemeo])
    resultado = _run(tmp_path, "preflight", container, parent=parent)
    assert resultado["status"] == probe.CONTAINER_AMBIGUOUS


def test_preflight_nome_alvo_ja_existe(tmp_path):
    container = FakeNode("Application", children=[FakeNode("GVL_AI_TESTE")])
    resultado = _run(tmp_path, "preflight", container)
    assert resultado["status"] == probe.TARGET_NAME_EXISTS


def test_preflight_instalacao_divergente(tmp_path):
    container = FakeNode("Application")
    duplo = FakeProbeCli(container=container, version="4.0.0.1")
    resultado = _run(tmp_path, "preflight", container, probe_cli_double=duplo)
    assert resultado["status"] == probe.RUNTIME_MISMATCH


def test_modo_invalido_falha(tmp_path):
    container = FakeNode("Application")
    resultado = _run(tmp_path, "PREFLIGHT", container)
    assert resultado["status"] == probe.STATUS_FATAL


# --- postsave ---------------------------------------------------------------

def _postsave_setup(tmp_path, children, baseline_names=("Outra",)):
    saida = os.path.join(str(tmp_path), "saida.project")
    handle = open(saida, "w")
    try:
        handle.write("projeto salvo")
    finally:
        handle.close()
    plan_path, _p = _plan(tmp_path, output_path=saida)
    container = FakeNode("Application", children=children)
    project = FakeProject(saida, [container])
    baseline = _write_baseline(tmp_path, list(baseline_names))
    digest, _erro = probe.sha256_of_file(saida)
    return plan_path, container, project, baseline, digest


def test_postsave_verificado(tmp_path):
    plan_path, container, project, baseline, digest = _postsave_setup(
        tmp_path, [FakeNode("Outra"), FakeNode("GVL_AI_TESTE")])
    resultado = _run(tmp_path, "postsave", container, project=project,
                     plan_path=plan_path, baseline=baseline, output_sha=digest)
    assert resultado["status"] == probe.POSTSAVE_VERIFIED
    assert resultado["exit_code"] == 0
    assert resultado["structural_diff"]["persistent_added"] == ["GVL_AI_TESTE"]
    assert resultado["gvl_declaration"]["text"] == "VAR_GLOBAL\nEND_VAR"


def test_postsave_gvl_ausente(tmp_path):
    plan_path, container, project, baseline, digest = _postsave_setup(
        tmp_path, [FakeNode("Outra")])
    resultado = _run(tmp_path, "postsave", container, project=project,
                     plan_path=plan_path, baseline=baseline, output_sha=digest)
    assert resultado["status"] == probe.GVL_MISSING


def test_postsave_gvl_duplicada(tmp_path):
    plan_path, container, project, baseline, digest = _postsave_setup(
        tmp_path, [FakeNode("Outra"), FakeNode("GVL_AI_TESTE"),
                   FakeNode("GVL_AI_TESTE")])
    resultado = _run(tmp_path, "postsave", container, project=project,
                     plan_path=plan_path, baseline=baseline, output_sha=digest)
    assert resultado["status"] == probe.GVL_DUPLICATED


def test_postsave_objeto_extra_reprova(tmp_path):
    plan_path, container, project, baseline, digest = _postsave_setup(
        tmp_path, [FakeNode("Outra"), FakeNode("GVL_AI_TESTE"),
                   FakeNode("PRG_INESPERADO")])
    resultado = _run(tmp_path, "postsave", container, project=project,
                     plan_path=plan_path, baseline=baseline, output_sha=digest)
    assert resultado["status"] == probe.UNEXPECTED_PERSISTENT_DIFF
    assert "PRG_INESPERADO" in str(resultado["problems"])


def test_postsave_objeto_sumido_reprova(tmp_path):
    plan_path, container, project, baseline, digest = _postsave_setup(
        tmp_path, [FakeNode("GVL_AI_TESTE")], baseline_names=("Outra",))
    resultado = _run(tmp_path, "postsave", container, project=project,
                     plan_path=plan_path, baseline=baseline, output_sha=digest)
    assert resultado["status"] == probe.UNEXPECTED_PERSISTENT_DIFF


def test_postsave_transiente_nao_conta_como_diff(tmp_path):
    plan_path, container, project, baseline, digest = _postsave_setup(
        tmp_path, [FakeNode("Outra"), FakeNode("GVL_AI_TESTE"),
                   FakeNode("TRANSIENTE", transient=True)])
    resultado = _run(tmp_path, "postsave", container, project=project,
                     plan_path=plan_path, baseline=baseline, output_sha=digest)
    assert resultado["status"] == probe.POSTSAVE_VERIFIED
    assert "TRANSIENTE" in resultado["structural_diff"]["transient_after"]


def test_postsave_hash_divergente(tmp_path):
    plan_path, container, project, baseline, _digest = _postsave_setup(
        tmp_path, [FakeNode("Outra"), FakeNode("GVL_AI_TESTE")])
    resultado = _run(tmp_path, "postsave", container, project=project,
                     plan_path=plan_path, baseline=baseline, output_sha="0" * 64)
    assert resultado["status"] == probe.OUTPUT_HASH_MISMATCH


def test_postsave_arquivo_aberto_nao_e_o_output(tmp_path):
    plan_path, container, _project, baseline, digest = _postsave_setup(
        tmp_path, [FakeNode("GVL_AI_TESTE")])
    outro = FakeProject(os.path.join(str(tmp_path), "outro.project"), [container])
    resultado = _run(tmp_path, "postsave", container, project=outro,
                     plan_path=plan_path, baseline=baseline, output_sha=digest)
    assert resultado["status"] == probe.OUTPUT_HASH_MISMATCH


def test_postsave_sem_baseline_e_fatal(tmp_path):
    plan_path, container, project, _baseline, digest = _postsave_setup(
        tmp_path, [FakeNode("GVL_AI_TESTE")])
    resultado = _run(tmp_path, "postsave", container, project=project,
                     plan_path=plan_path, output_sha=digest)
    assert resultado["status"] == probe.STATUS_FATAL
    assert "baseline" in str(resultado["problems"])


def test_postsave_sem_texto_e_lacuna_nao_sucesso(tmp_path):
    plan_path, container, project, baseline, digest = _postsave_setup(
        tmp_path, [FakeNode("Outra"),
                   FakeNode("GVL_AI_TESTE", declaration=None)])
    resultado = _run(tmp_path, "postsave", container, project=project,
                     plan_path=plan_path, baseline=baseline, output_sha=digest)
    assert resultado["status"] == probe.TEXT_READ_GAP
    assert resultado["exit_code"] != 0
    completion = probe.build_completion(resultado)
    assert completion["is_success"] is False


def test_apenas_dois_estados_sao_sucesso():
    for status in probe.PREFLIGHT_STATUSES + probe.POSTSAVE_STATUSES:
        esperado = status in (probe.PREFLIGHT_PASSED, probe.POSTSAVE_VERIFIED)
        assert (probe.EXIT_BY_STATUS[status] == 0) is esperado, status


def test_artefatos_do_postsave(tmp_path):
    plan_path, container, project, baseline, digest = _postsave_setup(
        tmp_path, [FakeNode("Outra"), FakeNode("GVL_AI_TESTE")])
    resultado = _run(tmp_path, "postsave", container, project=project,
                     plan_path=plan_path, baseline=baseline, output_sha=digest)
    escritos = probe.write_artifacts(resultado, file_io)
    assert escritos[-1] == "postsave-completion.json"
    for nome in ("postsave-tree.json", "postsave-gvl.json",
                 "structural-diff.json", "postsave-report.md"):
        assert nome in escritos


def test_relatorio_deterministico_fora_dos_volateis(tmp_path):
    plan_path, container, project, baseline, digest = _postsave_setup(
        tmp_path, [FakeNode("Outra"), FakeNode("GVL_AI_TESTE")])
    resultado = _run(tmp_path, "postsave", container, project=project,
                     plan_path=plan_path, baseline=baseline, output_sha=digest)
    a = probe.build_report_markdown(resultado)
    b = probe.build_report_markdown(resultado)
    assert a == b
    for campo in probe.VOLATILE_FIELDS:
        assert campo not in a


# --- regressao: o nome do membro de identidade ------------------------------

class _NoSoComTypeGuid(object):
    """Expoe o nome ERRADO, `type_guid`, e nada mais."""
    type_guid = "guid-container"

    def get_name(self, _recursive):
        return "Application"


class _NoComType(object):
    """Expoe o nome REAL do IScriptObject: `type`."""
    type = "guid-container"

    def get_name(self, _recursive):
        return "Application"


def test_identidade_le_o_membro_type_e_nao_type_guid():
    """Regressao do primeiro preflight real (2026-07-31).

    O probe lia `obj.type_guid`, que nao existe em IScriptObject -- `type_guid`
    e o nome do CAMPO na saida do scanner, nao do membro. O resultado era None
    em silencio, e o preflight reprovou com `container_not_found` enquanto o
    container estava correto.

    Um teste negativo com duble estrito nao pegaria isto: o probe e defensivo
    por construcao e engole a excecao. Por isso o teste e POSITIVO -- compara os
    dois nomes e exige que so o certo produza valor.
    """
    assert probe.object_identity(_NoSoComTypeGuid())["type_guid"] is None
    assert probe.object_identity(_NoComType())["type_guid"] == "guid-container"


def test_preflight_reprova_container_que_nao_expoe_type(tmp_path):
    """O sintoma exato observado em campo, agora coberto."""
    class ContainerSemType(FakeNode):
        def __init__(self):
            FakeNode.__init__(self, "Application")
            del self.type

    resultado = _run(tmp_path, "preflight", ContainerSemType())
    assert resultado["status"] == probe.CONTAINER_NOT_FOUND
    assert "type_guid do container" in str(resultado["problems"])


# --- verificacao estatica ---------------------------------------------------

@pytest.fixture(scope="module")
def tree():
    return ast.parse(io.open(PROBE_PATH, encoding="utf-8").read())


def _method_calls(tree, nome):
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == nome]


@pytest.mark.parametrize("metodo", [
    "create_gvl", "create_pou", "create_program", "create_folder", "create_dut",
    "create_interface", "create_persistentvars", "save", "save_as", "replace",
    "replace_line", "remove", "rename", "move", "build", "rebuild", "clean",
    "import_xml", "import_native", "Invoke",
])
def test_probe_28_nao_contem_mutador(tree, metodo):
    assert _method_calls(tree, metodo) == [], (
        "probe 28 e read-only e nao pode chamar .%s()" % metodo)


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_probe_28_sem_acesso_dinamico(tree, nome):
    encontrados = [n for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == nome]
    assert encontrados == []


def test_probe_28_referencia_create_gvl_sem_invocar(tree):
    """`iec_container.create_gvl` aparece como ATRIBUTO lido, nunca como
    chamada. E a diferenca entre perguntar e executar."""
    atributos = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Attribute) and n.attr == "create_gvl"]
    assert len(atributos) >= 1
    assert _method_calls(tree, "create_gvl") == []


def test_probe_28_sem_fstring(tree):
    assert [n for n in ast.walk(tree)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []

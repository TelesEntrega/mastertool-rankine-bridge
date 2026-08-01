"""Testes de `probes/33_verify_program_edit_w1_3b_readonly.py` e
`probes/34_edit_program_w1_3b.py` com dubles ESTRITOS, mais a verificacao
estatica (AST) das guardas adjacentes e dos mutadores proibidos.

Nenhuma API real do MasterTool e importada ou chamada. Os dubles LEVANTAM se
um probe tocar qualquer mutador fora do que lhe e proprio. Fixtures
sinteticas.
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

PROBE33_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                           "33_verify_program_edit_w1_3b_readonly.py")
PROBE34_PATH = os.path.join(_MASTERTOOL_DIR, "probes", "34_edit_program_w1_3b.py")

CONTAINER_GUID = "639b491f-5557-464c-af91-1471bac9f549"
POU_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
ST_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"

INITIAL_DECLARATION = "PROGRAM PRG_AI_TESTE\nVAR\nEND_VAR\n"
INITIAL_IMPLEMENTATION = ""
FINAL_DECLARATION = "PROGRAM PRG_AI_TESTE\nVAR\n    xLocal : BOOL;\nEND_VAR\n"
FINAL_IMPLEMENTATION = "xLocal := FALSE;\n"


def _load_module(path, name):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except ImportError:                                        # IronPython 2.7
        import imp
        return imp.load_source(name, path)


probe33 = _load_module(PROBE33_PATH, "probe33_w1_3b")
probe34 = _load_module(PROBE34_PATH, "probe34_w1_3b")


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
    """`replace()` funciona de verdade quando permitido, e persiste o estado
    no `owner` -- necessario para provar a leitura pos-mutacao no probe 34.
    Quando `forbid_replace` e True (usado pelos dubles do probe 33),
    `replace()` levanta: o probe read-only nunca pode chama-lo."""

    def __init__(self, owner, attr, forbid_replace=False):
        self.owner = owner
        self.attr = attr
        self.forbid_replace = forbid_replace
        self.replace_calls = []

    @property
    def text(self):
        if self.attr == "declaration":
            return self.owner._declaration
        return self.owner._implementation

    def replace(self, new_text):
        if self.forbid_replace:
            raise ForbiddenMemberTouched("probe read-only chamou replace()")
        self.replace_calls.append(new_text)
        if self.attr == "declaration":
            self.owner._declaration = new_text
        else:
            self.owner._implementation = new_text


class FakeNode(object):
    def __init__(self, name, children=None, node_type=POU_GUID,
                 declaration=INITIAL_DECLARATION,
                 implementation=INITIAL_IMPLEMENTATION,
                 transient=False, is_folder=False, forbid_replace=False):
        self._name = name
        self._children = list(children or [])
        self.type = node_type
        self.is_transient_object = transient
        self.is_folder = is_folder
        self._declaration = declaration
        self._implementation = implementation
        self._forbid_replace = forbid_replace

    @property
    def has_textual_declaration(self):
        return self._declaration is not None

    @property
    def has_textual_implementation(self):
        return self._implementation is not None

    def get_name(self, _recursive):
        return self._name

    def get_children(self, _recursive):
        return FakeChildren(self._children)

    @property
    def textual_declaration(self):
        if self._declaration is None:
            return None
        return FakeDoc(self, "declaration", forbid_replace=self._forbid_replace)

    @property
    def textual_implementation(self):
        if self._implementation is None:
            return None
        return FakeDoc(self, "implementation", forbid_replace=self._forbid_replace)


class FakeContainer(FakeNode):
    def __init__(self, children=None, node_type=CONTAINER_GUID):
        FakeNode.__init__(self, "Application", children=children, node_type=node_type)

    def create_program(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou create_program()")

    def create_pou(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou create_pou()")

    def create_gvl(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou create_gvl()")

    def remove(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe tentou rollback via remove()")

    def rename(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou rename()")


class FakeProject(FakeNode):
    def __init__(self, path, children, raise_on_save_as=None, create_output=True):
        FakeNode.__init__(self, "projeto", children=children)
        self.path = path
        self._raise = raise_on_save_as
        self._create_output = create_output
        self.save_as_calls = []

    def save_as(self, path):
        self.save_as_calls.append(path)
        if self._raise is not None:
            raise self._raise
        if self._create_output:
            handle = open(path, "w")
            try:
                handle.write("projeto salvo sintetico")
            finally:
                handle.close()

    def save(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou save()")

    def build(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou build()")


class FakeSafety(object):
    class SafetyError(Exception):
        pass

    def __init__(self, phase="W1_3B_EDIT_PROGRAM",
                 allowed=("replace", "save_as"), deny=()):
        self.CONTROLLED_WRITE_PHASE = phase
        self._allowed = set(allowed)
        self._deny = set(deny)
        self.requested = []

    def assert_controlled_write_allowed(self, operation):
        self.requested.append(operation)
        if operation in self._deny or operation not in self._allowed:
            raise self.SafetyError("operacao %r nao autorizada" % (operation,))
        return True


class FakeProjectAccess(object):
    def __init__(self, project):
        self._project = project

    def get_primary_project(self, _globals):
        return self._project, None

    def get_project_path(self, project):
        return project.path


class FakeProbeCli(object):
    def __init__(self, container=None, version="4.1.0.11"):
        self._container = container
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
        return self._container


def _hash_of(path):
    digest, _erro = probe34.sha256_of_file(path)
    return digest


def _make_input(tmp_path):
    caminho = os.path.join(str(tmp_path), "entrada.project")
    handle = open(caminho, "w")
    try:
        handle.write("conteudo sintetico")
    finally:
        handle.close()
    return caminho


def _plan(tmp_path, **overrides):
    entrada = overrides.pop("input_path", None) or _make_input(tmp_path)
    saida = overrides.pop("output_path", None) or os.path.join(str(tmp_path), "saida.project")
    plano = {
        "schema_version": "1.0",
        "operation_id": "w1-3b-edit-program",
        "phase": "W1_3B_EDIT_PROGRAM",
        "program_name": "PRG_AI_TESTE",
        "run_id": "run-sintetica",
        "input_project": {"path": entrada, "sha256": _hash_of(entrada)},
        "output_project": {"path": saida},
        "artifacts_dir": os.path.join(str(tmp_path), "art"),
        "container": {"node_path": "root/1/0/0", "expected_name": "Application",
                      "expected_type_guid": CONTAINER_GUID,
                      "expected_program_type_guid": POU_GUID},
        "mastertool": {"version": "4.1.0.11", "script_engine": "4.2.0.0"},
        "operations": [{"kind": "replace", "target": "textual_declaration"},
                       {"kind": "replace", "target": "textual_implementation"},
                       {"kind": "save_as"}],
    }
    plano.update(overrides)
    caminho = os.path.join(str(tmp_path), "plano.json")
    handle = open(caminho, "w")
    try:
        handle.write(json.dumps(plano))
    finally:
        handle.close()
    return caminho, plano


def _run34(tmp_path, plano_path=None, container=None, project=None, safety=None):
    if plano_path is None:
        plano_path, plano = _plan(tmp_path)
    else:
        plano = json.loads(io.open(plano_path, encoding="utf-8").read())
    container = container if container is not None else FakeContainer(
        children=[FakeNode("PRG_AI_TESTE")])
    project = project if project is not None else FakeProject(
        plano["input_project"]["path"], [container])
    safety = safety if safety is not None else FakeSafety()
    duplo = FakeProbeCli(container=container)
    resultado = probe34.run_w1_3b({"projects": object()},
                                  ["probe", "--plan=" + plano_path], safety,
                                  FakeProjectAccess(project), file_io, duplo)
    return resultado, container, project, safety


# =============================================================================
# probe 34 -- mutacao
# =============================================================================

def test_saved_as(tmp_path):
    resultado, container, project, safety = _run34(tmp_path)
    assert resultado["status"] == probe34.STATUS_SAVED_AS
    assert resultado["exit_code"] == 0
    programa = container._children[0]
    assert programa._declaration == FINAL_DECLARATION
    assert programa._implementation == FINAL_IMPLEMENTATION
    assert len(project.save_as_calls) == 1
    assert safety.requested == ["replace", "replace", "save_as"]
    assert resultado["requires_copy_discard"] is False
    assert resultado["operations_executed"] == [
        "replace_program_declaration", "replace_program_implementation", "save_as"]


def test_somente_saved_as_tem_codigo_zero():
    for status in probe34.ALL_STATUSES:
        esperado = (status == probe34.STATUS_SAVED_AS)
        assert (probe34.EXIT_BY_STATUS[status] == 0) is esperado, status


def _recusa34(tmp_path, **overrides):
    plano_path, _p = _plan(tmp_path, **overrides)
    resultado, container, project, safety = _run34(tmp_path, plano_path=plano_path)
    assert resultado["status"] == probe34.STATUS_PRECONDITION_FAILED
    assert project.save_as_calls == []
    assert safety.requested == []
    return resultado


def test_fase_errada_no_plano(tmp_path):
    _recusa34(tmp_path, phase="W1_3A_EDIT_GVL")


def test_nome_errado(tmp_path):
    _recusa34(tmp_path, program_name="PRG_OUTRO")


def test_operacao_extra(tmp_path):
    _recusa34(tmp_path, operations=[
        {"kind": "replace", "target": "textual_declaration"},
        {"kind": "replace", "target": "textual_implementation"},
        {"kind": "save_as"}, {"kind": "build"}])


def test_operacao_de_create_no_plano(tmp_path):
    _recusa34(tmp_path, operations=[
        {"kind": "create_program", "name": "PRG_AI_TESTE"},
        {"kind": "save_as"}])


def test_targets_fora_de_ordem(tmp_path):
    _recusa34(tmp_path, operations=[
        {"kind": "replace", "target": "textual_implementation"},
        {"kind": "replace", "target": "textual_declaration"},
        {"kind": "save_as"}])


def test_campo_desconhecido(tmp_path):
    _recusa34(tmp_path, campo_inesperado="x")


def test_st_language_guid_divergente_da_constante(tmp_path):
    _recusa34(tmp_path, st_language_guid="00000000-0000-0000-0000-000000000000")


def test_output_ja_existe(tmp_path):
    saida = os.path.join(str(tmp_path), "existe.project")
    handle = open(saida, "w")
    try:
        handle.write("ocupado")
    finally:
        handle.close()
    _recusa34(tmp_path, output_path=saida)


def test_fase_controlada_divergente(tmp_path):
    resultado, container, _p, safety = _run34(tmp_path, safety=FakeSafety(phase=None))
    assert resultado["status"] == probe34.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


def test_container_type_divergente(tmp_path):
    container = FakeContainer(node_type="guid-errado",
                              children=[FakeNode("PRG_AI_TESTE")])
    resultado, container, _p, safety = _run34(tmp_path, container=container)
    assert resultado["status"] == probe34.STATUS_PRECONDITION_FAILED


def test_programa_ausente(tmp_path):
    container = FakeContainer(children=[])
    resultado, container, _p, safety = _run34(tmp_path, container=container)
    assert resultado["status"] == probe34.STATUS_PRECONDITION_FAILED


def test_programa_duplicado(tmp_path):
    container = FakeContainer(children=[FakeNode("PRG_AI_TESTE"), FakeNode("PRG_AI_TESTE")])
    resultado, container, _p, safety = _run34(tmp_path, container=container)
    assert resultado["status"] == probe34.STATUS_PRECONDITION_FAILED


def test_type_do_programa_divergente(tmp_path):
    container = FakeContainer(children=[FakeNode("PRG_AI_TESTE", node_type="guid-outro")])
    resultado, container, _p, safety = _run34(tmp_path, container=container)
    assert resultado["status"] == probe34.STATUS_PRECONDITION_FAILED


def test_declaracao_inicial_divergente_nao_muta(tmp_path):
    container = FakeContainer(children=[
        FakeNode("PRG_AI_TESTE", declaration="PROGRAM PRG_AI_TESTE\nVAR\nEND_VAR\n\n")])
    resultado, container, project, safety = _run34(tmp_path, container=container)
    assert resultado["status"] == probe34.STATUS_PRECONDITION_FAILED
    assert safety.requested == []
    assert project.save_as_calls == []


def test_implementacao_inicial_divergente_nao_muta(tmp_path):
    container = FakeContainer(children=[
        FakeNode("PRG_AI_TESTE", implementation="ja_tem_algo();")])
    resultado, container, project, safety = _run34(tmp_path, container=container)
    assert resultado["status"] == probe34.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


def test_autorizacao_do_primeiro_replace_recusada(tmp_path):
    safety = FakeSafety(deny=("replace",))
    resultado, container, project, safety = _run34(tmp_path, safety=safety)
    assert resultado["status"] == probe34.STATUS_PRECONDITION_FAILED
    assert safety.requested == ["replace"]
    programa = container._children[0]
    assert programa._declaration == INITIAL_DECLARATION
    assert project.save_as_calls == []


class DenySecondReplace(FakeSafety):
    def assert_controlled_write_allowed(self, operation):
        self.requested.append(operation)
        if operation == "replace" and self.requested.count("replace") == 2:
            raise self.SafetyError("segundo replace recusado")
        if operation not in self._allowed:
            raise self.SafetyError("nao autorizado")
        return True


def test_autorizacao_do_segundo_replace_recusada_deixa_editado_em_memoria(tmp_path):
    safety = DenySecondReplace()
    resultado, container, project, safety = _run34(tmp_path, safety=safety)
    assert resultado["status"] == probe34.STATUS_EDITED_IN_MEMORY
    assert resultado["requires_copy_discard"] is True
    programa = container._children[0]
    assert programa._declaration == FINAL_DECLARATION
    assert programa._implementation == INITIAL_IMPLEMENTATION
    assert project.save_as_calls == []


def test_autorizacao_de_save_as_recusada_deixa_editado_em_memoria(tmp_path):
    safety = FakeSafety(deny=("save_as",))
    resultado, container, project, safety = _run34(tmp_path, safety=safety)
    assert resultado["status"] == probe34.STATUS_EDITED_IN_MEMORY
    assert resultado["requires_copy_discard"] is True
    programa = container._children[0]
    assert programa._declaration == FINAL_DECLARATION
    assert programa._implementation == FINAL_IMPLEMENTATION
    assert project.save_as_calls == []


def test_excecao_no_primeiro_replace(tmp_path):
    class Explosivo(FakeNode):
        @property
        def textual_declaration(self):
            class Bomba(object):
                text = INITIAL_DECLARATION

                def replace(self, _t):
                    raise RuntimeError("falha sintetica")
            return Bomba()

    container = FakeContainer(children=[Explosivo("PRG_AI_TESTE")])
    resultado, container, project, safety = _run34(tmp_path, container=container)
    assert resultado["status"] == probe34.STATUS_REPLACE_DECLARATION_FAILED
    assert resultado["requires_copy_discard"] is True
    assert project.save_as_calls == []


def test_excecao_no_segundo_replace(tmp_path):
    class Explosivo(FakeNode):
        @property
        def textual_implementation(self):
            class Bomba(object):
                text = INITIAL_IMPLEMENTATION

                def replace(self, _t):
                    raise RuntimeError("falha sintetica")
            return Bomba()

    container = FakeContainer(children=[Explosivo("PRG_AI_TESTE")])
    resultado, container, project, safety = _run34(tmp_path, container=container)
    assert resultado["status"] == probe34.STATUS_REPLACE_IMPLEMENTATION_FAILED
    assert resultado["requires_copy_discard"] is True
    assert project.save_as_calls == []


def test_replace_que_nao_muda_nada_reprova_verificacao(tmp_path):
    class Inerte(FakeNode):
        @property
        def textual_declaration(self):
            class Nulo(object):
                text = INITIAL_DECLARATION

                def replace(self, _t):
                    pass  # nao muda o texto -- verificacao deve reprovar
            return Nulo()

    container = FakeContainer(children=[Inerte("PRG_AI_TESTE")])
    resultado, container, project, safety = _run34(tmp_path, container=container)
    assert resultado["status"] == probe34.STATUS_DECLARATION_VERIFICATION_FAILED
    assert resultado["requires_copy_discard"] is True
    assert project.save_as_calls == []


def test_objeto_extra_reprova_verificacao_da_declaracao(tmp_path):
    class Ruidoso(FakeContainer):
        def __init__(self):
            FakeContainer.__init__(self, children=[FakeNode("PRG_AI_TESTE")])

        def get_children(self, _recursive):
            self._children_snapshot_calls = getattr(self, "_children_snapshot_calls", 0) + 1
            if self._children_snapshot_calls > 1:
                return FakeChildren(self._children + [FakeNode("GVL_INESPERADA")])
            return FakeChildren(self._children)

    resultado, container, project, safety = _run34(tmp_path, container=Ruidoso())
    assert resultado["status"] == probe34.STATUS_DECLARATION_VERIFICATION_FAILED
    assert project.save_as_calls == []


def test_excecao_em_save_as_sem_retry(tmp_path):
    plano_path, plano = _plan(tmp_path)
    container = FakeContainer(children=[FakeNode("PRG_AI_TESTE")])
    project = FakeProject(plano["input_project"]["path"], [container],
                          raise_on_save_as=RuntimeError("falha"))
    resultado, _c, project, _s = _run34(tmp_path, plano_path=plano_path,
                                        container=container, project=project)
    assert resultado["status"] == probe34.STATUS_SAVE_AS_FAILED
    assert len(project.save_as_calls) == 1


def test_journal_ordenado_com_call_sites(tmp_path):
    resultado, _c, _p, _s = _run34(tmp_path)
    entradas = resultado["journal"]
    assert [e["sequence"] for e in entradas] == list(range(len(entradas)))
    sites = [e.get("call_site") for e in entradas if e.get("call_site")]
    assert probe34.CALL_SITE_REPLACE_DECLARATION in sites
    assert probe34.CALL_SITE_REPLACE_IMPLEMENTATION in sites
    assert probe34.CALL_SITE_SAVE_AS in sites
    eventos = [e.get("operation") for e in entradas if e.get("operation")]
    assert "replace_program_declaration" in eventos
    assert "replace_program_implementation" in eventos


def test_completion_por_ultimo_e_declara_nada_alem(tmp_path):
    resultado, _c, _p, _s = _run34(tmp_path)
    escritos = probe34.write_artifacts(resultado, file_io)
    assert escritos[-1] == "completion.json"
    completion = probe34.build_completion(resultado)
    assert completion["no_other_mutator_requested"] is True
    assert completion["operations_executed"] == [
        "replace_program_declaration", "replace_program_implementation", "save_as"]
    assert completion["edited_declaration_sha256"]
    assert completion["edited_implementation_sha256"]


def test_todos_os_artefatos(tmp_path):
    resultado, _c, _p, _s = _run34(tmp_path)
    probe34.write_artifacts(resultado, file_io)
    presentes = os.listdir(resultado["artifacts_dir"])
    for nome in probe34.ARTIFACT_NAMES:
        assert nome in presentes, nome


def test_normalizacao_de_texto():
    assert probe34.texts_match("a\r\nb\r\n", "a\nb\n")
    assert probe34.texts_match("a \nb\n", "a\nb")
    assert probe34.texts_match("a\nb\n\n", "a\nb\n") is False
    assert probe34.texts_match("a\nb", "a\nc") is False


# =============================================================================
# probe 33 -- verificacao read-only
# =============================================================================

def _run33(tmp_path, mode="preflight", plano_path=None, container=None,
          project=None, baseline_path=None, output_sha=None):
    if plano_path is None:
        plano_path, plano = _plan(tmp_path)
    else:
        plano = json.loads(io.open(plano_path, encoding="utf-8").read())
    container = container if container is not None else FakeContainer(
        children=[FakeNode("PRG_AI_TESTE", forbid_replace=True)])
    caminho_projeto = plano["output_project"]["path"] if mode == "postsave" \
        else plano["input_project"]["path"]
    if mode == "postsave" and not os.path.exists(caminho_projeto):
        handle = open(caminho_projeto, "w")
        try:
            handle.write("saida sintetica")
        finally:
            handle.close()
    project = project if project is not None else FakeProject(caminho_projeto, [container])
    duplo = FakeProbeCli(container=container)
    argv = ["probe", "--plan=" + plano_path, "--mode=" + mode,
           "--output=" + os.path.join(str(tmp_path), "saida-probe33-" + mode)]
    if mode == "postsave":
        if baseline_path is None:
            baseline_path = os.path.join(str(tmp_path), "baseline.json")
            file_io.write_json(baseline_path, {"persistent": [
                {"name": "PRG_AI_TESTE", "type_guid": POU_GUID, "is_folder": False,
                 "is_transient": False}], "transient": [], "count": 1, "error": None})
        argv.append("--baseline=" + baseline_path)
        if output_sha is None:
            output_sha = _hash_of(caminho_projeto)
        argv.append("--output-sha256=" + output_sha)
    resultado = probe33.run_verify({"projects": object()}, argv,
                                   FakeProjectAccess(project), file_io, duplo)
    return resultado, container, project


def test_preflight_verificado(tmp_path):
    resultado, container, _p = _run33(tmp_path, mode="preflight")
    assert resultado["status"] == probe33.PREFLIGHT_VERIFIED
    assert resultado["exit_code"] == 0


def test_preflight_declaracao_divergente(tmp_path):
    container = FakeContainer(children=[
        FakeNode("PRG_AI_TESTE", declaration="PROGRAM PRG_AI_TESTE\nVAR\nEND_VAR\n\n",
                forbid_replace=True)])
    resultado, _c, _p = _run33(tmp_path, mode="preflight", container=container)
    assert resultado["status"] == probe33.INITIAL_TEXT_MISMATCH


def test_preflight_implementacao_divergente(tmp_path):
    container = FakeContainer(children=[
        FakeNode("PRG_AI_TESTE", implementation="ja_tem_algo();", forbid_replace=True)])
    resultado, _c, _p = _run33(tmp_path, mode="preflight", container=container)
    assert resultado["status"] == probe33.INITIAL_TEXT_MISMATCH


def test_preflight_programa_ausente(tmp_path):
    container = FakeContainer(children=[])
    resultado, _c, _p = _run33(tmp_path, mode="preflight", container=container)
    assert resultado["status"] == probe33.PROGRAM_MISSING


def test_preflight_programa_duplicado(tmp_path):
    container = FakeContainer(children=[
        FakeNode("PRG_AI_TESTE", forbid_replace=True),
        FakeNode("PRG_AI_TESTE", forbid_replace=True)])
    resultado, _c, _p = _run33(tmp_path, mode="preflight", container=container)
    assert resultado["status"] == probe33.PROGRAM_DUPLICATED


def test_preflight_tipo_divergente(tmp_path):
    container = FakeContainer(children=[
        FakeNode("PRG_AI_TESTE", node_type="guid-outro", forbid_replace=True)])
    resultado, _c, _p = _run33(tmp_path, mode="preflight", container=container)
    assert resultado["status"] == probe33.PROGRAM_TYPE_MISMATCH


def test_preflight_container_type_divergente(tmp_path):
    container = FakeContainer(node_type="guid-errado",
                              children=[FakeNode("PRG_AI_TESTE", forbid_replace=True)])
    resultado, _c, _p = _run33(tmp_path, mode="preflight", container=container)
    assert resultado["status"] == probe33.CONTAINER_NOT_FOUND


def test_postsave_verificado(tmp_path):
    container = FakeContainer(children=[
        FakeNode("PRG_AI_TESTE", declaration=FINAL_DECLARATION,
                implementation=FINAL_IMPLEMENTATION, forbid_replace=True)])
    resultado, _c, _p = _run33(tmp_path, mode="postsave", container=container)
    assert resultado["status"] == probe33.POSTSAVE_VERIFIED
    assert resultado["exit_code"] == 0


def test_postsave_hash_divergente(tmp_path):
    container = FakeContainer(children=[
        FakeNode("PRG_AI_TESTE", declaration=FINAL_DECLARATION,
                implementation=FINAL_IMPLEMENTATION, forbid_replace=True)])
    resultado, _c, _p = _run33(tmp_path, mode="postsave", container=container,
                               output_sha="0" * 64)
    assert resultado["status"] == probe33.OUTPUT_HASH_MISMATCH


def test_postsave_texto_final_divergente(tmp_path):
    container = FakeContainer(children=[
        FakeNode("PRG_AI_TESTE", declaration=INITIAL_DECLARATION,
                implementation=INITIAL_IMPLEMENTATION, forbid_replace=True)])
    resultado, _c, _p = _run33(tmp_path, mode="postsave", container=container)
    assert resultado["status"] == probe33.FINAL_TEXT_MISMATCH


def test_postsave_diff_estrutural_inesperado(tmp_path):
    container = FakeContainer(children=[
        FakeNode("PRG_AI_TESTE", declaration=FINAL_DECLARATION,
                implementation=FINAL_IMPLEMENTATION, forbid_replace=True),
        FakeNode("GVL_INESPERADA", forbid_replace=True)])
    resultado, _c, _p = _run33(tmp_path, mode="postsave", container=container)
    assert resultado["status"] == probe33.STRUCTURAL_DIFF_UNEXPECTED


def test_replace_nunca_e_chamado_pelo_probe33(tmp_path):
    """Os dubles do modo preflight/postsave levantam ForbiddenMemberTouched se
    replace() for chamado -- este teste prova, por execucao, que nao e."""
    resultado, _c, _p = _run33(tmp_path, mode="preflight")
    assert resultado["status"] == probe33.PREFLIGHT_VERIFIED


def test_modo_invalido_recusado(tmp_path):
    plano_path, _p = _plan(tmp_path)
    container = FakeContainer(children=[FakeNode("PRG_AI_TESTE", forbid_replace=True)])
    project = FakeProject(_p["input_project"]["path"], [container])
    duplo = FakeProbeCli(container=container)
    argv = ["probe", "--plan=" + plano_path, "--mode=algo_invalido",
           "--output=" + os.path.join(str(tmp_path), "saida")]
    resultado = probe33.run_verify({"projects": object()}, argv,
                                   FakeProjectAccess(project), file_io, duplo)
    assert resultado["status"] == probe33.STATUS_FATAL


def test_todos_os_status_tem_um_por_sucesso():
    for status in probe33.ALL_STATUSES:
        esperado = status in probe33.SUCCESS_STATUSES
        assert (probe33.EXIT_BY_STATUS[status] == 0) is esperado, status


# =============================================================================
# verificacao estatica -- probe 34 (mutacao)
# =============================================================================

@pytest.fixture(scope="module")
def tree34():
    return ast.parse(io.open(PROBE34_PATH, encoding="utf-8").read())


@pytest.fixture(scope="module")
def tree33():
    return ast.parse(io.open(PROBE33_PATH, encoding="utf-8").read())


def _calls(tree):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)]


def _method_calls(tree, nome):
    return [n for n in _calls(tree)
            if isinstance(n.func, ast.Attribute) and n.func.attr == nome]


def _guard_calls(tree, operacao):
    encontrados = []
    for node in _calls(tree):
        if isinstance(node.func, ast.Attribute) and \
                node.func.attr == "assert_controlled_write_allowed":
            if node.args and isinstance(node.args[0], ast.Str) \
                    and node.args[0].s == operacao:
                encontrados.append(node)
    return encontrados


def _adjacent_pairs(tree, operacao, mutador):
    """Todos os pares (guarda, mutacao) em que a guarda de `operacao` e a
    instrucao IMEDIATAMENTE anterior a uma chamada de `mutador`, no mesmo
    bloco. Restrito a instrucoes-expressao simples (`ast.Expr`): sem essa
    restricao, dois `def` adjacentes no mesmo modulo -- um contendo a guarda,
    o outro contendo a mutacao, cada um na SUA PROPRIA funcao -- casariam
    como se fossem adjacentes, o que nao e o que a regra exige."""
    pares = []
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        index = 0
        while index < len(body) - 1:
            atual, seguinte = body[index], body[index + 1]
            if isinstance(atual, ast.Expr) and isinstance(seguinte, ast.Expr) \
                    and _guard_calls(atual, operacao) and _method_calls(seguinte, mutador):
                pares.append((atual, seguinte))
            index = index + 1
    return pares


def test_exatamente_duas_chamadas_de_replace(tree34):
    chamadas = _method_calls(tree34, "replace")
    assert len(chamadas) == 2


def test_exatamente_uma_chamada_de_save_as(tree34):
    chamadas = _method_calls(tree34, "save_as")
    assert len(chamadas) == 1


def test_tres_guardas_no_total(tree34):
    guardas = [n for n in _calls(tree34)
              if isinstance(n.func, ast.Attribute)
              and n.func.attr == "assert_controlled_write_allowed"]
    assert len(guardas) == 3


def test_cada_replace_tem_guarda_adjacente(tree34):
    pares = _adjacent_pairs(tree34, "replace", "replace")
    assert len(pares) == 2
    for guarda, mutacao in pares:
        assert mutacao.lineno == guarda.lineno + 1


def test_save_as_tem_guarda_adjacente(tree34):
    pares = _adjacent_pairs(tree34, "save_as", "save_as")
    assert len(pares) == 1
    guarda, mutacao = pares[0]
    assert mutacao.lineno == guarda.lineno + 1


def test_replace_chamado_apenas_com_constantes_do_modulo(tree34):
    """Os argumentos das duas chamadas de replace() sao NOMES (referencia a
    constante do modulo), nunca literal derivado de variavel do plano."""
    chamadas = _method_calls(tree34, "replace")
    nomes_esperados = {"FINAL_DECLARATION", "FINAL_IMPLEMENTATION"}
    encontrados = set()
    for chamada in chamadas:
        assert len(chamada.args) == 1
        assert isinstance(chamada.args[0], ast.Name)
        encontrados.add(chamada.args[0].id)
    assert encontrados == nomes_esperados


@pytest.mark.parametrize("metodo", [
    "create_pou", "create_program", "create_gvl", "create_folder", "create_dut",
    "create_function", "create_function_block", "save", "replace_line", "remove",
    "rename", "move", "build", "rebuild", "clean", "import_xml", "Invoke",
])
# `insert`/`append` ficam FORA desta lista de proposito: `list.append(...)` e
# uso legitimo e onipresente no proprio probe (registro de problemas), e
# incluir o nome aqui reprovaria o arquivo pelo metodo homonimo de lista, nao
# pela API do MasterTool.
def test_mutador_proibido_ausente_no_probe34(tree34, metodo):
    assert _method_calls(tree34, metodo) == []


def test_documento_textual_so_recebe_replace_probe34(tree34):
    """`insert`, `append` e `remove` existem em IScriptTextDocument E em
    `list`. Proibi-los por NOME quebra em `lista.append(...)`; tira-los da
    lista sem mais nada perderia a garantia que docs/31 pede.

    A garantia correta e por RECEPTOR: o documento textual so recebe `replace`.
    `replace` do documento inteiro e a unica forma cujo estado final nao
    depende de offset, e portanto a unica verificavel por hash."""
    chamadas = []
    for no in ast.walk(tree34):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            receptor = no.func.value
            if isinstance(receptor, ast.Name) and receptor.id in (
                    "text_document", "document", "text_doc",
                    "declaration_document", "implementation_document"):
                chamadas.append((receptor.id, no.func.attr))
    assert chamadas, "nenhuma chamada no documento textual foi encontrada"
    for receptor, metodo in chamadas:
        assert metodo == "replace", (
            "%s.%s() nao e permitido: o documento so recebe replace()"
            % (receptor, metodo))


def test_probe33_readonly_nunca_escreve_no_documento(tree33):
    for no in ast.walk(tree33):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            receptor = no.func.value
            if isinstance(receptor, ast.Name) and receptor.id in (
                    "text_document", "document", "text_doc",
                    "declaration_document", "implementation_document"):
                assert no.func.attr not in (
                    "replace", "insert", "append", "remove", "replace_line"), (
                    "probe read-only chamou %s.%s()" % (receptor.id, no.func.attr))


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_sem_acesso_dinamico_probe34(tree34, nome):
    assert [n for n in _calls(tree34)
            if isinstance(n.func, ast.Name) and n.func.id == nome] == []


def test_sem_lambda_nem_fstring_probe34(tree34):
    assert [n for n in ast.walk(tree34) if isinstance(n, ast.Lambda)] == []
    assert [n for n in ast.walk(tree34)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []


def test_identificadores_ascii_probe34():
    arvore = ast.parse(io.open(PROBE34_PATH, encoding="utf-8").read())
    for node in ast.walk(arvore):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


# =============================================================================
# verificacao estatica -- probe 33 (somente leitura)
# =============================================================================

@pytest.mark.parametrize("metodo", [
    "create_pou", "create_program", "create_gvl", "create_folder", "create_dut",
    "create_function", "create_function_block", "save", "save_as", "replace",
    "replace_line", "remove", "rename", "move", "build", "rebuild", "clean",
    "import_xml", "Invoke",
])
def test_mutador_proibido_ausente_no_probe33(tree33, metodo):
    assert _method_calls(tree33, metodo) == []


def test_probe33_nao_chama_a_guarda(tree33):
    guardas = [n for n in _calls(tree33)
              if isinstance(n.func, ast.Attribute)
              and n.func.attr == "assert_controlled_write_allowed"]
    assert guardas == []


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_sem_acesso_dinamico_probe33(tree33, nome):
    assert [n for n in _calls(tree33)
            if isinstance(n.func, ast.Name) and n.func.id == nome] == []


def test_sem_lambda_nem_fstring_probe33(tree33):
    assert [n for n in ast.walk(tree33) if isinstance(n, ast.Lambda)] == []
    assert [n for n in ast.walk(tree33)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []


def test_identificadores_ascii_probe33():
    arvore = ast.parse(io.open(PROBE33_PATH, encoding="utf-8").read())
    for node in ast.walk(arvore):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


def test_busca_literal_zero_mutadores_no_probe33():
    """Busca literal, sem AST: prova adicional pedida pelo contrato de que
    `.replace(`, `.save_as(`, `.save(` e `getattr(` nao aparecem em lugar
    nenhum do arquivo -- nem em codigo, nem em comentario, nem em docstring."""
    texto = io.open(PROBE33_PATH, encoding="utf-8").read()
    for proibido in (".replace(", ".save_as(", ".save(", "getattr("):
        assert proibido not in texto, proibido

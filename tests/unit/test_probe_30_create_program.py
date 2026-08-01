"""Testes de `probes/30_create_program_w1_2.py` com dubles ESTRITOS, mais a
verificacao estatica (AST) das guardas adjacentes.

Nenhuma API real do MasterTool e importada ou chamada. Os dubles LEVANTAM se o
probe tocar qualquer mutador fora dos dois autorizados. Fixtures sinteticas.
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

PROBE_PATH = os.path.join(_MASTERTOOL_DIR, "probes", "30_create_program_w1_2.py")

CONTAINER_GUID = "639b491f-5557-464c-af91-1471bac9f549"
POU_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
ST_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"


def _load_probe():
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("probe30_w1_2", PROBE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except ImportError:                                        # IronPython 2.7
        import imp
        return imp.load_source("probe30_w1_2", PROBE_PATH)


probe = _load_probe()


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

    def replace(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 30 chamou replace()")


class FakeNode(object):
    def __init__(self, name, children=None, node_type=POU_GUID,
                 declaration="PROGRAM PRG_AI_TESTE\nVAR\nEND_VAR",
                 implementation="", transient=False, is_folder=False):
        self._name = name
        self._children = list(children or [])
        self.type = node_type
        self.is_transient_object = transient
        self.is_folder = is_folder
        self.has_textual_declaration = declaration is not None
        self.has_textual_implementation = implementation is not None
        self._declaration = declaration
        self._implementation = implementation

    def get_name(self, _recursive):
        return self._name

    def get_children(self, _recursive):
        return FakeChildren(self._children)

    @property
    def textual_declaration(self):
        return None if self._declaration is None else FakeDoc(self._declaration)

    @property
    def textual_implementation(self):
        return None if self._implementation is None else FakeDoc(self._implementation)


class FakeContainer(FakeNode):
    def __init__(self, children=None, created_name="PRG_AI_TESTE",
                 raise_on_create=None, created_object=None,
                 node_type=CONTAINER_GUID):
        FakeNode.__init__(self, "Application", children=children,
                          node_type=node_type)
        self._created_name = created_name
        self._raise_on_create = raise_on_create
        self._forced = created_object
        self.create_program_calls = []

    def create_program(self, name, language):
        self.create_program_calls.append((name, language))
        if self._raise_on_create is not None:
            raise self._raise_on_create
        novo = self._forced if self._forced is not None else FakeNode(self._created_name)
        self._children.append(novo)
        return novo

    def create_pou(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 30 chamou create_pou()")

    def create_gvl(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 30 chamou create_gvl()")

    def remove(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 30 tentou rollback via remove()")

    def rename(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 30 chamou rename()")


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
        raise ForbiddenMemberTouched("probe 30 chamou save()")

    def build(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 30 chamou build()")


class FakeSafety(object):
    class SafetyError(Exception):
        pass

    def __init__(self, phase="W1_2_CREATE_PROGRAM",
                 allowed=("create_program", "save_as"), deny=()):
        self.CONTROLLED_WRITE_PHASE = phase
        self._allowed = set(allowed)
        self._deny = set(deny)
        self.requested = []

    def assert_controlled_write_allowed(self, operation):
        self.requested.append(operation)
        if operation in self._deny or operation not in self._allowed:
            raise self.SafetyError("operacao %r nao autorizada" % (operation,))
        return True

    def assert_operation_allowed(self, operation):
        raise ForbiddenMemberTouched("probe 30 usou a porta legada")


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

    def runtime_identity(self):
        return {"executable": "MT9000.exe", "file_version": self._version,
                "product_version": self._version, "error": None}

    def descend(self, project, indexes, trace):
        return self._container


def _hash_of(path):
    digest, _erro = probe.sha256_of_file(path)
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
        "operation_id": "w1-2-create-program",
        "phase": "W1_2_CREATE_PROGRAM",
        "program_name": "PRG_AI_TESTE",
        "run_id": "run-sintetica",
        "st_language_guid": ST_GUID,
        "input_project": {"path": entrada, "sha256": _hash_of(entrada)},
        "output_project": {"path": saida},
        "artifacts_dir": os.path.join(str(tmp_path), "art"),
        "container": {"node_path": "root/0", "expected_name": "Application",
                      "expected_type_guid": CONTAINER_GUID,
                      "expected_program_type_guid": POU_GUID},
        "mastertool": {"version": "4.1.0.11", "script_engine": "4.2.0.0"},
        "operations": [{"kind": "create_program", "name": "PRG_AI_TESTE"},
                       {"kind": "save_as", "path": saida}],
    }
    plano.update(overrides)
    caminho = os.path.join(str(tmp_path), "plano.json")
    handle = open(caminho, "w")
    try:
        handle.write(json.dumps(plano))
    finally:
        handle.close()
    return caminho, plano


class FakeGuid(object):
    """Duble de System.Guid: existe para provar que o argumento NAO chega como
    str. Em CPython nao ha CLR, entao a conversao real e insubstituivel aqui."""

    def __init__(self, texto):
        self.texto = texto

    def __eq__(self, other):
        return isinstance(other, FakeGuid) and other.texto == self.texto

    def __repr__(self):
        return "FakeGuid(%r)" % (self.texto,)


def _conversor_ok(texto):
    return FakeGuid(texto), None


def _run(tmp_path, plano_path=None, container=None, project=None, safety=None,
         duplo=None, guid_converter=_conversor_ok):
    if plano_path is None:
        plano_path, plano = _plan(tmp_path)
    else:
        plano = json.loads(io.open(plano_path, encoding="utf-8").read())
    container = container if container is not None else FakeContainer()
    project = project if project is not None else FakeProject(
        plano["input_project"]["path"], [container])
    safety = safety if safety is not None else FakeSafety()
    duplo = duplo or FakeProbeCli(container=container)
    resultado = probe.run_w1_2({"projects": object()},
                               ["probe", "--plan=" + plano_path], safety,
                               FakeProjectAccess(project), file_io, duplo,
                               guid_converter=guid_converter)
    return resultado, container, project, safety


# --- caminho feliz ----------------------------------------------------------

def test_saved_as(tmp_path):
    resultado, container, project, safety = _run(tmp_path)
    assert resultado["status"] == probe.STATUS_SAVED_AS
    assert resultado["exit_code"] == 0
    assert container.create_program_calls == [("PRG_AI_TESTE", FakeGuid(ST_GUID))]
    assert len(project.save_as_calls) == 1
    assert safety.requested == ["create_program", "save_as"]
    assert resultado["requires_copy_discard"] is False


def test_guid_st_chega_convertido_e_nao_como_texto(tmp_path):
    """Regressao da run-005 (2026-07-31).

    O plano so transporta TEXTO -- JSON nao tem tipo Guid -- e a API recusou com
    `TypeError: expected Nullable[Guid], got str`. A conversao passou a ocorrer
    na fase de precondicao, ANTES da guarda, e o que chega em create_program e
    um System.Guid.

    Em CPython nao existe System.Guid, entao `to_clr_guid` devolve erro e o
    probe para em precondition_failed -- o que este teste comprova: o valor
    NUNCA e repassado como str.
    """
    resultado, container, _p, _s = _run(tmp_path)
    passado = container.create_program_calls[0][1]
    assert not isinstance(passado, str)
    assert passado == FakeGuid(ST_GUID)


def test_sem_clr_a_conversao_falha_em_precondicao(tmp_path):
    """Com a conversao real (sem CLR no ambiente de teste), o probe para ANTES
    de qualquer mutacao -- nunca tentando a chamada com texto."""
    resultado, container, project, safety = _run(tmp_path,
                                                 guid_converter=probe.to_clr_guid)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert resultado["st_language_guid_converted"] is False
    assert container.create_program_calls == []
    assert project.save_as_calls == []
    assert safety.requested == []
    assert "System.Guid" in str(resultado["problems"])


def test_to_clr_guid_sem_dotnet_devolve_erro_sem_levantar():
    guid, erro = probe.to_clr_guid("cc393387-a21c-4f68-a3e3-84c36951965d")
    assert guid is None
    assert erro
    assert "System.Guid" in erro


def test_texto_canonico_do_objeto_novo_e_registrado(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    criado = resultado["created_program"]
    assert criado["declaration"] == "PROGRAM PRG_AI_TESTE\nVAR\nEND_VAR"
    assert criado["declaration_sha256"]
    assert criado["implementation"] == ""


def test_somente_saved_as_tem_codigo_zero():
    for status in probe.ALL_STATUSES:
        esperado = (status == probe.STATUS_SAVED_AS)
        assert (probe.EXIT_BY_STATUS[status] == 0) is esperado, status


# --- plano recusado ---------------------------------------------------------

def _recusa(tmp_path, **overrides):
    plano_path, _p = _plan(tmp_path, **overrides)
    resultado, container, project, safety = _run(tmp_path, plano_path=plano_path)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_program_calls == []
    assert project.save_as_calls == []
    assert safety.requested == []
    return resultado


def test_fase_errada_no_plano(tmp_path):
    _recusa(tmp_path, phase="W1_1_CREATE_GVL")


def test_nome_errado(tmp_path):
    _recusa(tmp_path, program_name="PRG_OUTRO")


def test_operacao_extra(tmp_path):
    saida = os.path.join(str(tmp_path), "saida.project")
    _recusa(tmp_path, operations=[{"kind": "create_program", "name": "PRG_AI_TESTE"},
                                  {"kind": "save_as", "path": saida},
                                  {"kind": "build"}])


def test_operacao_de_w1_1_no_plano(tmp_path):
    saida = os.path.join(str(tmp_path), "saida.project")
    _recusa(tmp_path, operations=[{"kind": "create_gvl", "name": "X"},
                                  {"kind": "save_as", "path": saida}])


@pytest.mark.parametrize("guid", [None, "", "ST", "nao-e-guid",
                                  "cc393387a21c4f68a3e384c36951965d"])
def test_guid_st_invalido_recusa(tmp_path, guid):
    """A string 'ST' nunca substitui o GUID: o parametro e Nullable<Guid>."""
    _recusa(tmp_path, st_language_guid=guid)


def test_campo_desconhecido(tmp_path):
    _recusa(tmp_path, campo_inesperado="x")


def test_output_ja_existe(tmp_path):
    saida = os.path.join(str(tmp_path), "existe.project")
    handle = open(saida, "w")
    try:
        handle.write("ocupado")
    finally:
        handle.close()
    _recusa(tmp_path, output_path=saida)


# --- precondicoes de runtime ------------------------------------------------

def test_fase_controlada_divergente(tmp_path):
    resultado, container, _p, safety = _run(tmp_path, safety=FakeSafety(phase=None))
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_program_calls == []
    assert safety.requested == []


def test_container_type_divergente(tmp_path):
    container = FakeContainer(node_type="guid-errado")
    resultado, container, _p, safety = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_program_calls == []


def test_nome_ja_existe_no_container(tmp_path):
    container = FakeContainer(children=[FakeNode("PRG_AI_TESTE")])
    resultado, container, _p, safety = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_program_calls == []


def test_autorizacao_de_create_program_recusada(tmp_path):
    safety = FakeSafety(deny=("create_program",))
    resultado, container, project, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_program_calls == []
    assert project.save_as_calls == []
    assert safety.requested == ["create_program"]


# --- verificacao pos-criacao ------------------------------------------------

def test_tipo_do_objeto_criado_divergente(tmp_path):
    errado = FakeNode("PRG_AI_TESTE", node_type="guid-outro")
    container = FakeContainer(created_object=errado)
    resultado, _c, project, _s = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED
    assert resultado["requires_copy_discard"] is True
    assert project.save_as_calls == []


def test_objeto_extra_reprova(tmp_path):
    class Ruidoso(FakeContainer):
        def create_program(self, name, language):
            self.create_program_calls.append((name, language))
            novo = FakeNode("PRG_AI_TESTE")
            self._children.append(novo)
            self._children.append(FakeNode("GVL_INESPERADA"))
            return novo

    resultado, _c, project, _s = _run(tmp_path, container=Ruidoso())
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED
    assert project.save_as_calls == []


def test_retorno_nulo(tmp_path):
    class Nulo(FakeContainer):
        def create_program(self, name, language):
            self.create_program_calls.append((name, language))
            return None

    resultado, _c, project, _s = _run(tmp_path, container=Nulo())
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED
    assert project.save_as_calls == []


def test_excecao_em_create_program(tmp_path):
    container = FakeContainer(raise_on_create=RuntimeError("falha sintetica"))
    resultado, container, project, safety = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_CREATE_PROGRAM_FAILED
    assert resultado["requires_copy_discard"] is True
    assert project.save_as_calls == []


def test_save_as_recusado_deixa_created_in_memory(tmp_path):
    safety = FakeSafety(deny=("save_as",))
    resultado, container, project, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe.STATUS_CREATED_IN_MEMORY
    assert resultado["requires_copy_discard"] is True
    assert container.create_program_calls == [("PRG_AI_TESTE", FakeGuid(ST_GUID))]
    assert project.save_as_calls == []


def test_excecao_em_save_as_sem_retry(tmp_path):
    plano_path, plano = _plan(tmp_path)
    container = FakeContainer()
    project = FakeProject(plano["input_project"]["path"], [container],
                          raise_on_save_as=RuntimeError("falha"))
    resultado, _c, project, _s = _run(tmp_path, plano_path=plano_path,
                                      container=container, project=project)
    assert resultado["status"] == probe.STATUS_SAVE_AS_FAILED
    assert len(project.save_as_calls) == 1


def test_nenhum_rollback_apos_falha(tmp_path):
    """Os dubles levantam em remove/rename."""
    errado = FakeNode("PRG_ERRADO")
    resultado, _c, _p, _s = _run(tmp_path, container=FakeContainer(created_object=errado))
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED


# --- journal e artefatos ----------------------------------------------------

def test_journal_ordenado_com_call_sites(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    entradas = resultado["journal"]
    assert [e["sequence"] for e in entradas] == list(range(len(entradas)))
    sites = [e.get("call_site") for e in entradas if e.get("call_site")]
    assert probe.CALL_SITE_CREATE_PROGRAM in sites
    assert probe.CALL_SITE_SAVE_AS in sites


def test_completion_por_ultimo_e_declara_nada_alem(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    escritos = probe.write_artifacts(resultado, file_io)
    assert escritos[-1] == "completion.json"
    completion = probe.build_completion(resultado)
    assert completion["no_other_mutator_requested"] is True
    assert completion["operations_executed"] == ["create_program", "save_as"]
    assert completion["st_language_guid"] == ST_GUID


def test_todos_os_artefatos(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    probe.write_artifacts(resultado, file_io)
    presentes = os.listdir(resultado["artifacts_dir"])
    for nome in probe.ARTIFACT_NAMES:
        assert nome in presentes, nome


# --- verificacao estatica ---------------------------------------------------

@pytest.fixture(scope="module")
def tree():
    return ast.parse(io.open(PROBE_PATH, encoding="utf-8").read())


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


def _adjacentes(tree, operacao, mutador):
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        index = 0
        while index < len(body) - 1:
            atual, seguinte = body[index], body[index + 1]
            if _guard_calls(atual, operacao) and _method_calls(seguinte, mutador):
                return atual, seguinte
            index = index + 1
    return None, None


def test_guarda_de_create_program_adjacente(tree):
    guarda, mutacao = _adjacentes(tree, "create_program", "create_program")
    assert guarda is not None
    assert mutacao.lineno == guarda.lineno + 1


def test_guarda_de_save_as_adjacente(tree):
    guarda, mutacao = _adjacentes(tree, "save_as", "save_as")
    assert guarda is not None
    assert mutacao.lineno == guarda.lineno + 1


def test_create_program_chamado_com_literais(tree):
    chamadas = _method_calls(tree, "create_program")
    assert len(chamadas) == 1
    assert isinstance(chamadas[0].args[0], ast.Str)
    assert chamadas[0].args[0].s == "PRG_AI_TESTE"
    assert len(chamadas[0].args) == 2


@pytest.mark.parametrize("metodo", [
    "create_pou", "create_gvl", "create_folder", "create_dut", "create_function",
    "create_function_block", "save", "replace", "replace_line", "remove",
    "rename", "move", "build", "rebuild", "clean", "import_xml", "Invoke",
])
def test_mutador_proibido_ausente(tree, metodo):
    assert _method_calls(tree, metodo) == []


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_sem_acesso_dinamico(tree, nome):
    assert [n for n in _calls(tree)
            if isinstance(n.func, ast.Name) and n.func.id == nome] == []


def test_sem_lambda_nem_fstring(tree):
    assert [n for n in ast.walk(tree) if isinstance(n, ast.Lambda)] == []
    assert [n for n in ast.walk(tree)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []


def test_identificadores_ascii():
    arvore = ast.parse(io.open(PROBE_PATH, encoding="utf-8").read())
    for node in ast.walk(arvore):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor

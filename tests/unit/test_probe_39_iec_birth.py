"""Testes de `probes/39_measure_iec_birth.py` com dubles ESTRITOS, mais a
verificacao estatica (AST) das guardas adjacentes.

Nenhuma API real do MasterTool e importada ou chamada. Os dubles LEVANTAM se o
probe tocar qualquer mutador fora dos dois autorizados (create_function_block,
create_function). `create_dut` esta na mesma lista de mutadores proibidos:
este probe nao mede DUT (docs/35 secao 1 -- DutType nao catalogado).
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

PROBE_PATH = os.path.join(_MASTERTOOL_DIR, "probes", "39_measure_iec_birth.py")

CONTAINER_GUID = "639b491f-5557-464c-af91-1471bac9f549"
POU_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
LANGUAGE_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"


def _load_probe():
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("probe39_w1_5", PROBE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except ImportError:                                        # IronPython 2.7
        import imp
        return imp.load_source("probe39_w1_5", PROBE_PATH)


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
        raise ForbiddenMemberTouched("probe 39 chamou replace()")


class FakeNode(object):
    def __init__(self, name, children=None, node_type=POU_GUID,
                 declaration="FUNCTION_BLOCK FB_AI_MEASURE_W1_5\nVAR\nEND_VAR",
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
    def __init__(self, children=None,
                 fb_name="FB_AI_MEASURE_W1_5", function_name="F_AI_MEASURE_W1_5",
                 raise_on_create_fb=None, raise_on_create_function=None,
                 created_fb=None, created_function=None,
                 node_type=CONTAINER_GUID):
        FakeNode.__init__(self, "Application", children=children,
                          node_type=node_type)
        self._fb_name = fb_name
        self._function_name = function_name
        self._raise_fb = raise_on_create_fb
        self._raise_function = raise_on_create_function
        self._forced_fb = created_fb
        self._forced_function = created_function
        self.create_function_block_calls = []
        self.create_function_calls = []

    def create_function_block(self, name, language):
        self.create_function_block_calls.append((name, language))
        if self._raise_fb is not None:
            raise self._raise_fb
        novo = self._forced_fb if self._forced_fb is not None else FakeNode(self._fb_name)
        self._children.append(novo)
        return novo

    def create_function(self, name, return_type, language):
        self.create_function_calls.append((name, return_type, language))
        if self._raise_function is not None:
            raise self._raise_function
        novo = self._forced_function if self._forced_function is not None \
            else FakeNode(self._function_name,
                         declaration="FUNCTION F_AI_MEASURE_W1_5 : DINT\nVAR_INPUT\nEND_VAR",
                         implementation="")
        self._children.append(novo)
        return novo

    def create_dut(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 39 chamou create_dut()")

    def create_program(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 39 chamou create_program()")

    def create_pou(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 39 chamou create_pou()")

    def create_gvl(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 39 chamou create_gvl()")

    def remove(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 39 tentou rollback via remove()")

    def rename(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 39 chamou rename()")


class FakeProject(FakeNode):
    def __init__(self, path, children):
        FakeNode.__init__(self, "projeto", children=children)
        self.path = path

    def save(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 39 chamou save()")

    def save_as(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 39 chamou save_as()")

    def build(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 39 chamou build()")


class FakeSafety(object):
    class SafetyError(Exception):
        pass

    def __init__(self, phase="W1_5_MEASURE_IEC_BIRTH",
                 allowed=("create_function_block", "create_function"), deny=()):
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
        raise ForbiddenMemberTouched("probe 39 usou a porta legada")


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
    plano = {
        "schema_version": "1.0",
        "operation_id": "w1-5-measure-iec-birth",
        "phase": "W1_5_MEASURE_IEC_BIRTH",
        "function_block_name": "FB_AI_MEASURE_W1_5",
        "function_name": "F_AI_MEASURE_W1_5",
        "function_return_type": "DINT",
        "run_id": "run-sintetica",
        "language_guid": LANGUAGE_GUID,
        "input_project": {"path": entrada, "sha256": _hash_of(entrada)},
        "artifacts_dir": os.path.join(str(tmp_path), "art"),
        "container": {"node_path": "root/0", "expected_name": "Application",
                      "expected_type_guid": CONTAINER_GUID},
        "mastertool": {"version": "4.1.0.11", "script_engine": "4.2.0.0"},
        "operations": [{"kind": "create_function_block", "name": "FB_AI_MEASURE_W1_5"},
                       {"kind": "create_function", "name": "F_AI_MEASURE_W1_5"}],
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
    resultado = probe.run_w1_5({"projects": object()},
                               ["probe", "--plan=" + plano_path], safety,
                               FakeProjectAccess(project), file_io, duplo,
                               guid_converter=guid_converter)
    return resultado, container, project, safety


# --- caminho feliz (fase hipoteticamente aberta) -----------------------------

def test_measured(tmp_path):
    resultado, container, project, safety = _run(tmp_path)
    assert resultado["status"] == probe.STATUS_MEASURED
    assert resultado["exit_code"] == 0
    assert container.create_function_block_calls == \
        [("FB_AI_MEASURE_W1_5", FakeGuid(LANGUAGE_GUID))]
    assert container.create_function_calls == \
        [("F_AI_MEASURE_W1_5", "DINT", FakeGuid(LANGUAGE_GUID))]
    assert safety.requested == ["create_function_block", "create_function"]
    assert resultado["requires_copy_discard"] is True   # objeto em memoria, nunca salvo


def test_nenhum_save_ou_save_as_chamado(tmp_path):
    """FakeProject levanta se save/save_as/build forem chamados -- a ausencia
    de excecao aqui e a prova de que o probe nunca tenta persistir."""
    resultado, _c, _p, _s = _run(tmp_path)
    assert resultado["status"] == probe.STATUS_MEASURED


def test_guid_chega_convertido_e_nao_como_texto(tmp_path):
    resultado, container, _p, _s = _run(tmp_path)
    passado_fb = container.create_function_block_calls[0][1]
    passado_function = container.create_function_calls[0][2]
    assert not isinstance(passado_fb, str)
    assert not isinstance(passado_function, str)
    assert passado_fb == FakeGuid(LANGUAGE_GUID)
    assert passado_function == FakeGuid(LANGUAGE_GUID)


def test_sem_clr_a_conversao_falha_em_precondicao(tmp_path):
    resultado, container, project, safety = _run(tmp_path,
                                                  guid_converter=probe.to_clr_guid)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert resultado["language_guid_converted"] is False
    assert container.create_function_block_calls == []
    assert container.create_function_calls == []
    assert safety.requested == []
    assert "System.Guid" in str(resultado["problems"])


def test_to_clr_guid_sem_dotnet_devolve_erro_sem_levantar():
    guid, erro = probe.to_clr_guid("cc393387-a21c-4f68-a3e3-84c36951965d")
    assert guid is None
    assert erro
    assert "System.Guid" in erro


def test_texto_canonico_dos_dois_objetos_e_registrado(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    fb = resultado["measured_function_block"]
    function = resultado["measured_function"]
    assert fb["declaration"] == "FUNCTION_BLOCK FB_AI_MEASURE_W1_5\nVAR\nEND_VAR"
    assert fb["declaration_sha256"]
    assert fb["implementation"] == ""
    assert function["declaration"] == \
        "FUNCTION F_AI_MEASURE_W1_5 : DINT\nVAR_INPUT\nEND_VAR"
    assert function["declaration_sha256"]
    assert function["implementation"] == ""


def test_dut_nunca_e_medido(tmp_path):
    resultado, container, _p, _s = _run(tmp_path)
    completion = probe.build_completion(resultado)
    assert completion["dut_measured"] is False
    assert any("DutType" in nota for nota in resultado["gap_notes"])


def test_somente_measured_tem_codigo_zero():
    for status in probe.ALL_STATUSES:
        esperado = (status == probe.STATUS_MEASURED)
        assert (probe.EXIT_BY_STATUS[status] == 0) is esperado, status


# --- plano recusado ---------------------------------------------------------

def _recusa(tmp_path, **overrides):
    plano_path, _p = _plan(tmp_path, **overrides)
    resultado, container, project, safety = _run(tmp_path, plano_path=plano_path)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_function_block_calls == []
    assert container.create_function_calls == []
    assert safety.requested == []
    return resultado


def test_fase_errada_no_plano(tmp_path):
    _recusa(tmp_path, phase="W1_2_CREATE_PROGRAM")


def test_nome_de_fb_errado(tmp_path):
    _recusa(tmp_path, function_block_name="FB_OUTRO")


def test_nome_de_function_errado(tmp_path):
    _recusa(tmp_path, function_name="F_OUTRO")


def test_operacao_extra(tmp_path):
    _recusa(tmp_path, operations=[
        {"kind": "create_function_block", "name": "FB_AI_MEASURE_W1_5"},
        {"kind": "create_function", "name": "F_AI_MEASURE_W1_5"},
        {"kind": "create_dut", "name": "ST_X"}])


def test_operacao_de_create_dut_no_plano_e_recusada(tmp_path):
    _recusa(tmp_path, operations=[
        {"kind": "create_dut", "name": "ST_X"},
        {"kind": "create_function", "name": "F_AI_MEASURE_W1_5"}])


def test_operacao_de_save_as_no_plano_e_recusada(tmp_path):
    """Este probe nunca declara save_as como operacao -- nem no plano."""
    _recusa(tmp_path, operations=[
        {"kind": "create_function_block", "name": "FB_AI_MEASURE_W1_5"},
        {"kind": "save_as", "path": "x"}])


@pytest.mark.parametrize("guid", [None, "", "ST", "nao-e-guid",
                                  "cc393387a21c4f68a3e384c36951965d"])
def test_guid_invalido_recusa(tmp_path, guid):
    _recusa(tmp_path, language_guid=guid)


@pytest.mark.parametrize("tipo", [None, "", "123DINT", "DINT INVALIDO",
                                  "tipo'malicioso"])
def test_return_type_invalido_recusa(tmp_path, tipo):
    _recusa(tmp_path, function_return_type=tipo)


def test_campo_desconhecido(tmp_path):
    _recusa(tmp_path, campo_inesperado="x")


def test_campo_output_project_nao_existe_no_schema(tmp_path):
    """Este probe nunca persiste: o plano nao tem (nem aceita) output_project."""
    _recusa(tmp_path, output_project={"path": "x"})


# --- precondicoes de runtime ------------------------------------------------

def test_fase_controlada_divergente(tmp_path):
    resultado, container, _p, safety = _run(tmp_path, safety=FakeSafety(phase=None))
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_function_block_calls == []
    assert safety.requested == []


def test_container_type_divergente(tmp_path):
    container = FakeContainer(node_type="guid-errado")
    resultado, container, _p, safety = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_function_block_calls == []


def test_nome_de_fb_ja_existe_no_container(tmp_path):
    container = FakeContainer(children=[FakeNode("FB_AI_MEASURE_W1_5")])
    resultado, container, _p, safety = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_function_block_calls == []


def test_nome_de_function_ja_existe_no_container(tmp_path):
    container = FakeContainer(children=[FakeNode("F_AI_MEASURE_W1_5")])
    resultado, container, _p, safety = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_function_block_calls == []


# --- fase fechada (hoje) -----------------------------------------------------

def test_gate_closed_quando_fase_desconhecida_para_a_allowlist(tmp_path):
    """Hoje CONTROLLED_WRITE_PHASE = None em safety.py: uma FakeSafety que
    reproduz esse estado nega create_function_block e o probe termina
    gate_closed, sem tentar create_function."""
    safety = FakeSafety(phase="W1_5_MEASURE_IEC_BIRTH", allowed=())
    resultado, container, project, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe.STATUS_GATE_CLOSED
    assert resultado["exit_code"] != 0
    assert container.create_function_block_calls == []
    assert container.create_function_calls == []
    assert safety.requested == ["create_function_block"]
    assert resultado["requires_copy_discard"] is False


def test_create_function_negado_apos_fb_criado_e_medicao_parcial(tmp_path):
    safety = FakeSafety(deny=("create_function",))
    resultado, container, project, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe.STATUS_PARTIAL_MEASURED
    assert container.create_function_block_calls == \
        [("FB_AI_MEASURE_W1_5", FakeGuid(LANGUAGE_GUID))]
    assert container.create_function_calls == []
    assert resultado["requires_copy_discard"] is True
    assert resultado["measured_function_block"]["declaration_sha256"]
    assert resultado["measured_function"] is None


# --- verificacao pos-criacao ------------------------------------------------

def test_forma_do_fb_criado_divergente(tmp_path):
    """type_guid de POU nao distingue familia (docs/35 secao 4): a
    verificacao usa a FORMA estrutural, nao o type_guid. Um objeto sem
    declaracao textual reprova."""
    errado = FakeNode("FB_AI_MEASURE_W1_5", declaration=None)
    container = FakeContainer(created_fb=errado)
    resultado, _c, project, _s = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED
    assert resultado["requires_copy_discard"] is True


def test_excecao_em_create_function_block(tmp_path):
    container = FakeContainer(raise_on_create_fb=RuntimeError("falha sintetica"))
    resultado, container, project, safety = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_CREATE_FAILED
    assert resultado["requires_copy_discard"] is True
    assert container.create_function_calls == []


def test_excecao_em_create_function(tmp_path):
    container = FakeContainer(raise_on_create_function=RuntimeError("falha sintetica"))
    resultado, container, project, safety = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_CREATE_FAILED
    assert resultado["requires_copy_discard"] is True
    assert container.create_function_block_calls == \
        [("FB_AI_MEASURE_W1_5", FakeGuid(LANGUAGE_GUID))]


def test_retorno_nulo_de_create_function_block(tmp_path):
    class Nulo(FakeContainer):
        def create_function_block(self, name, language):
            self.create_function_block_calls.append((name, language))
            return None

    resultado, _c, project, _s = _run(tmp_path, container=Nulo())
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED


def test_nenhum_rollback_apos_falha(tmp_path):
    """Os dubles levantam em remove/rename."""
    errado = FakeNode("FB_ERRADO")
    resultado, _c, _p, _s = _run(tmp_path, container=FakeContainer(created_fb=errado))
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED


# --- journal e artefatos ----------------------------------------------------

def test_journal_ordenado_com_call_sites(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    entradas = resultado["journal"]
    assert [e["sequence"] for e in entradas] == list(range(len(entradas)))
    sites = [e.get("call_site") for e in entradas if e.get("call_site")]
    assert probe.CALL_SITE_CREATE_FUNCTION_BLOCK in sites
    assert probe.CALL_SITE_CREATE_FUNCTION in sites


def test_completion_por_ultimo_e_declara_nada_alem(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    escritos = probe.write_artifacts(resultado, file_io)
    assert escritos[-1] == "completion.json"
    completion = probe.build_completion(resultado)
    assert completion["no_other_mutator_requested"] is True
    assert completion["operations_executed"] == ["create_function_block", "create_function"]
    assert completion["language_guid"] == LANGUAGE_GUID
    assert completion["dut_measured"] is False


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


def test_guarda_de_create_function_block_adjacente(tree):
    guarda, mutacao = _adjacentes(tree, "create_function_block", "create_function_block")
    assert guarda is not None
    assert mutacao.lineno == guarda.lineno + 1


def test_guarda_de_create_function_adjacente(tree):
    guarda, mutacao = _adjacentes(tree, "create_function", "create_function")
    assert guarda is not None
    assert mutacao.lineno == guarda.lineno + 1


def test_create_function_block_chamado_com_literal_de_nome(tree):
    chamadas = _method_calls(tree, "create_function_block")
    assert len(chamadas) == 1
    assert isinstance(chamadas[0].args[0], ast.Name)   # parametro `name`, injetado pelo plano
    assert len(chamadas[0].args) == 2


def test_create_function_chamado_uma_vez(tree):
    chamadas = _method_calls(tree, "create_function")
    assert len(chamadas) == 1
    assert len(chamadas[0].args) == 3


@pytest.mark.parametrize("metodo", [
    "create_pou", "create_gvl", "create_program", "create_dut", "create_folder",
    "create_interface", "save", "save_as", "save_archive", "replace",
    "replace_line", "remove", "rename", "move", "build",
    "rebuild", "clean", "import_xml", "Invoke",
])
def test_mutador_proibido_ausente(tree, metodo):
    assert _method_calls(tree, metodo) == []


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_sem_acesso_dinamico(tree, nome):
    assert [n for n in _calls(tree)
            if isinstance(n.func, ast.Name) and n.func.id == nome] == []


def test_sem_reflexao_dotnet(tree):
    """Nem `GetType`, nem `GetMethod`, nem `Enum.GetNames`/`Enum.Parse` -- a
    descoberta de DutType foi deliberadamente adiada, nao contornada."""
    proibidos = ("GetType", "GetMethod", "GetMethods", "GetParameters",
                 "GetNames", "GetUnderlyingType")
    for nome in proibidos:
        assert _method_calls(tree, nome) == [], nome
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "System":
            for alias in node.names:
                assert alias.name not in ("Enum", "Reflection"), alias.name


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

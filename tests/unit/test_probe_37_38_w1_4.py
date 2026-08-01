"""Testes de `probes/37_preflight_w1_4_readonly.py` e `probes/38_author_w1_4.py`
com dubles ESTRITOS, mais a verificacao estatica (AST) das guardas adjacentes e
dos mutadores proibidos POR RECEPTOR.

Nenhuma API real do MasterTool e importada ou chamada. Os dubles LEVANTAM se um
probe tocar qualquer mutador fora do que lhe e proprio -- inclusive `build`, que
em W1.4 pertence a `probes/40` e a mais ninguem. Fixtures sinteticas.

A verificacao de mutadores e por RECEPTOR, e nao por nome: `.append` e `.insert`
existem em `list`/`sys.path` E em `IScriptTextDocument`. O nome nao decide; o
receptor decide.
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

PROBE37_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "37_preflight_w1_4_readonly.py")
PROBE38_PATH = os.path.join(_MASTERTOOL_DIR, "probes", "38_author_w1_4.py")

CONTAINER_GUID = "639b491f-5557-464c-af91-1471bac9f549"
GVL_GUID = "ffbfa93a-b94d-45fc-a329-229860183b1d"
POU_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
ST_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"

GVL_DECLARATION = ("{attribute 'qualified_only'}\nVAR_GLOBAL\n"
                   "    g_xTesteCriacao : BOOL;\nEND_VAR")
PROGRAM_DECLARATION = "PROGRAM PRG_AI_TESTE\nVAR\n    xLocal : BOOL;\nEND_VAR\n"
PROGRAM_IMPLEMENTATION = "xLocal := GVL_AI_TESTE.g_xTesteCriacao;\n"

# Texto de NASCIMENTO da GVL (medido em W1.1: nasce com o pragma). Nos dubles
# ele so precisa ser diferente do texto final, para que a verificacao
# intermediaria tenha o que distinguir.
BORN_GVL_DECLARATION = "{attribute 'qualified_only'}\nVAR_GLOBAL\nEND_VAR"
BORN_PROGRAM_DECLARATION = "PROGRAM PRG_AI_TESTE\nVAR\nEND_VAR\n"
BORN_PROGRAM_IMPLEMENTATION = ""


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


probe37 = _load_module(PROBE37_PATH, "probe37_w1_4")
probe38 = _load_module(PROBE38_PATH, "probe38_w1_4")


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
    """`replace()` funciona de verdade quando permitido e persiste o estado no
    `owner`. Com `forbid_replace`, levanta: o probe read-only nunca o chama."""

    def __init__(self, owner, attr, forbid_replace=False):
        self.owner = owner
        self.attr = attr
        self.forbid_replace = forbid_replace

    @property
    def text(self):
        if self.attr == "declaration":
            return self.owner._declaration
        return self.owner._implementation

    def replace(self, new_text):
        if self.forbid_replace:
            raise ForbiddenMemberTouched("probe read-only chamou replace()")
        if self.attr == "declaration":
            self.owner._declaration = new_text
        else:
            self.owner._implementation = new_text

    def insert(self, *_a, **_k):
        raise ForbiddenMemberTouched("documento textual recebeu insert()")

    def append(self, *_a, **_k):
        raise ForbiddenMemberTouched("documento textual recebeu append()")

    def replace_line(self, *_a, **_k):
        raise ForbiddenMemberTouched("documento textual recebeu replace_line()")

    def remove(self, *_a, **_k):
        raise ForbiddenMemberTouched("documento textual recebeu remove()")


class FakeNode(object):
    def __init__(self, name, children=None, node_type=POU_GUID,
                 declaration=None, implementation=None, transient=False,
                 is_folder=False, forbid_replace=False):
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

    def build(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe de autoria chamou build()")

    def rename(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou rename()")

    def remove(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe tentou rollback via remove()")


class FakeContainer(FakeNode):
    """`Application`. As criacoes funcionam de verdade e INSEREM na arvore --
    e o ponto do achado: `create_*` devolve o objeto ja inserido, sem passo de
    confirmacao e sem rollback."""

    def __init__(self, children=None, node_type=CONTAINER_GUID,
                 gvl_type=GVL_GUID, program_type=POU_GUID,
                 create_gvl_error=None, create_program_error=None,
                 created_gvl_name="GVL_AI_TESTE",
                 created_program_name="PRG_AI_TESTE",
                 forbid_replace=False):
        FakeNode.__init__(self, "Application", children=children,
                          node_type=node_type, forbid_replace=forbid_replace)
        self._gvl_type = gvl_type
        self._program_type = program_type
        self._create_gvl_error = create_gvl_error
        self._create_program_error = create_program_error
        self._created_gvl_name = created_gvl_name
        self._created_program_name = created_program_name
        self.create_gvl_calls = []
        self.create_program_calls = []

    def create_gvl(self, name):
        self.create_gvl_calls.append(name)
        if self._create_gvl_error is not None:
            raise self._create_gvl_error
        node = FakeNode(self._created_gvl_name, node_type=self._gvl_type,
                        declaration=BORN_GVL_DECLARATION)
        self._children.append(node)
        return node

    def create_program(self, name, language):
        self.create_program_calls.append((name, language))
        if self._create_program_error is not None:
            raise self._create_program_error
        if isinstance(language, str):
            raise TypeError("expected Nullable[Guid], got str")
        node = FakeNode(self._created_program_name, node_type=self._program_type,
                        declaration=BORN_PROGRAM_DECLARATION,
                        implementation=BORN_PROGRAM_IMPLEMENTATION)
        self._children.append(node)
        return node

    def create_pou(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou create_pou()")

    def create_dut(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou create_dut()")

    def create_folder(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou create_folder()")


class ReadOnlyContainer(FakeContainer):
    """Container dos testes do probe 37: QUALQUER criacao levanta."""

    def create_gvl(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe read-only chamou create_gvl()")

    def create_program(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe read-only chamou create_program()")


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


class FakeSafety(object):
    class SafetyError(Exception):
        pass

    def __init__(self, phase="W1_4_INTEGRATED_BUILD",
                 allowed=("create_gvl", "create_program", "replace", "save_as",
                          "build"),
                 deny=()):
        self.CONTROLLED_WRITE_PHASE = phase
        self._allowed = set(allowed)
        self._deny = set(deny)
        self.requested = []

    def assert_controlled_write_allowed(self, operation):
        self.requested.append(operation)
        if operation in self._deny or operation not in self._allowed:
            raise self.SafetyError("operacao %r nao autorizada" % (operation,))
        return True


class DenyNthReplace(FakeSafety):
    def __init__(self, nth, **kwargs):
        FakeSafety.__init__(self, **kwargs)
        self._nth = nth

    def assert_controlled_write_allowed(self, operation):
        self.requested.append(operation)
        if operation == "replace" and self.requested.count("replace") == self._nth:
            raise self.SafetyError("replace #%d recusado" % self._nth)
        if operation not in self._allowed:
            raise self.SafetyError("nao autorizado")
        return True


class FakeProjectAccess(object):
    def __init__(self, project):
        self._project = project

    def get_primary_project(self, _globals):
        return self._project, None

    def get_project_path(self, project):
        return project.path


class FakeProbeCli(object):
    def __init__(self, container=None, version="4.1.0.11", by_path=None):
        self._container = container
        self._version = version
        self._by_path = dict(by_path or {})

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
        chave = tuple(indexes)
        if chave in self._by_path:
            return self._by_path[chave]
        return self._container


class FakeScanner(object):
    def __init__(self, flat_nodes, statistics=None, limits=None):
        self._flat = flat_nodes
        self._stats = statistics
        self._limits = limits

    def scan(self, _project):
        estatisticas = self._stats or {"scan_complete": True, "failed_nodes": 0,
                                       "total_nodes": len(self._flat)}
        limites = self._limits or {"max_depth_reached": False,
                                   "max_total_nodes_reached": False,
                                   "max_children_per_node_reached": False}
        return {"tree": {"flat": self._flat}, "statistics": estatisticas,
                "limits": limites, "errors": []}


class FakeScanModule(object):
    def __init__(self, flat_nodes, statistics=None, limits=None):
        self._flat = flat_nodes
        self._stats = statistics
        self._limits = limits

    def ReadOnlyProjectScanner(self, max_depth=None, max_total_nodes=None,
                               max_children_per_node=None):
        return FakeScanner(self._flat, self._stats, self._limits)

    def flatten_tree(self, tree):
        return list(tree["flat"])


def _hash_of(path):
    digest, _erro = probe38.sha256_of_file(path)
    return digest


def _make_input(tmp_path, nome="entrada.project"):
    caminho = os.path.join(str(tmp_path), nome)
    handle = open(caminho, "w")
    try:
        handle.write("conteudo sintetico")
    finally:
        handle.close()
    return caminho


def _operations():
    return [
        {"kind": "create_gvl", "name": "GVL_AI_TESTE"},
        {"kind": "create_program", "name": "PRG_AI_TESTE", "language": "st"},
        {"kind": "replace", "target": "gvl_textual_declaration"},
        {"kind": "replace", "target": "program_textual_declaration"},
        {"kind": "replace", "target": "program_textual_implementation"},
        {"kind": "save_as"},
        {"kind": "build"},
    ]


def _plan(tmp_path, **overrides):
    entrada = overrides.pop("input_path", None) or _make_input(tmp_path)
    saida = overrides.pop("output_path", None) or \
        os.path.join(str(tmp_path), "saida.project")
    plano = {
        "schema_version": "1.0",
        "operation_id": "w1-4-integrated-build",
        "phase": "W1_4_INTEGRATED_BUILD",
        "gvl_name": "GVL_AI_TESTE",
        "program_name": "PRG_AI_TESTE",
        "st_language_guid": ST_GUID,
        "run_id": "run-sintetica",
        "input_project": {"path": entrada, "sha256": _hash_of(entrada)},
        "output_project": {"path": saida},
        "artifacts_dir": os.path.join(str(tmp_path), "art"),
        "container": {"node_path": "root/1/0/0", "expected_name": "Application",
                      "expected_type_guid": CONTAINER_GUID,
                      "expected_gvl_type_guid": GVL_GUID,
                      "expected_program_type_guid": POU_GUID},
        "mastertool": {"version": "4.1.0.11", "script_engine": "4.2.0.0"},
        "operations": _operations(),
    }
    plano.update(overrides)
    caminho = os.path.join(str(tmp_path), "plano.json")
    handle = open(caminho, "w")
    try:
        handle.write(json.dumps(plano))
    finally:
        handle.close()
    return caminho, plano


def _fake_guid(_text):
    class GuidSintetico(object):
        pass
    return GuidSintetico(), None


# =============================================================================
# probe 38 -- autoria (as seis mutacoes)
# =============================================================================

def _run38(tmp_path, plano_path=None, container=None, project=None, safety=None,
           guid_converter=None):
    if plano_path is None:
        plano_path, plano = _plan(tmp_path)
    else:
        plano = json.loads(io.open(plano_path, encoding="utf-8").read())
    container = container if container is not None else FakeContainer(children=[])
    project = project if project is not None else FakeProject(
        plano["input_project"]["path"], [container])
    safety = safety if safety is not None else FakeSafety()
    duplo = FakeProbeCli(container=container)
    resultado = probe38.run_w1_4({"projects": object()},
                                 ["probe", "--plan=" + plano_path], safety,
                                 FakeProjectAccess(project), file_io, duplo,
                                 guid_converter=guid_converter or _fake_guid)
    return resultado, container, project, safety


def test_cadeia_completa_termina_em_saved_as(tmp_path):
    resultado, container, project, safety = _run38(tmp_path)
    assert resultado["status"] == probe38.STATUS_SAVED_AS
    assert resultado["exit_code"] == 0
    assert safety.requested == ["create_gvl", "create_program", "replace",
                                "replace", "replace", "save_as"]
    assert resultado["operations_executed"] == list(
        probe38.EXECUTED_OPERATION_SEQUENCE)
    assert len(project.save_as_calls) == 1
    gvl = container._children[0]
    programa = container._children[1]
    assert gvl._declaration == GVL_DECLARATION
    assert programa._declaration == PROGRAM_DECLARATION
    assert programa._implementation == PROGRAM_IMPLEMENTATION
    assert resultado["requires_copy_discard"] is False


def test_a_implementacao_carrega_o_prefixo_obrigatorio(tmp_path):
    """`qualified_only` na GVL torna `GVL_AI_TESTE.` obrigatorio. Sem ele o
    build falharia por conteudo, e o achado seria confundido com capacidade."""
    resultado, container, _p, _s = _run38(tmp_path)
    assert resultado["status"] == probe38.STATUS_SAVED_AS
    assert "GVL_AI_TESTE.g_xTesteCriacao" in container._children[1]._implementation
    assert "qualified_only" in container._children[0]._declaration


def test_somente_saved_as_tem_codigo_zero():
    for status in probe38.ALL_STATUSES:
        esperado = (status == probe38.STATUS_SAVED_AS)
        assert (probe38.EXIT_BY_STATUS[status] == 0) is esperado, status


def test_todo_status_de_falha_pos_mutacao_exige_descarte():
    """Nao existe rollback transacional: a unidade descartada e a COPIA
    INTEIRA. Apenas `precondition_failed` (nada foi tentado) e `saved_as`
    escapam."""
    for status in probe38.ALL_STATUSES:
        if status in (probe38.STATUS_PRECONDITION_FAILED,
                      probe38.STATUS_SAVED_AS, probe38.STATUS_FATAL):
            continue
        assert status in probe38.STATUSES_REQUIRING_DISCARD, status


def _recusa38(tmp_path, **overrides):
    plano_path, _p = _plan(tmp_path, **overrides)
    resultado, container, project, safety = _run38(tmp_path, plano_path=plano_path)
    assert resultado["status"] == probe38.STATUS_PRECONDITION_FAILED
    assert project.save_as_calls == []
    assert safety.requested == []
    assert container.create_gvl_calls == []
    assert container.create_program_calls == []
    return resultado


def test_fase_errada_no_plano(tmp_path):
    _recusa38(tmp_path, phase="W1_3B_EDIT_PROGRAM")


def test_operacao_extra_no_plano(tmp_path):
    extra = _operations() + [{"kind": "save"}]
    _recusa38(tmp_path, operations=extra)


def test_falta_o_build_no_plano(tmp_path):
    _recusa38(tmp_path, operations=_operations()[:6])


def test_targets_dos_replace_fora_de_ordem(tmp_path):
    ops = _operations()
    ops[2]["target"] = "program_textual_declaration"
    ops[3]["target"] = "gvl_textual_declaration"
    _recusa38(tmp_path, operations=ops)


def test_campo_desconhecido_no_plano(tmp_path):
    _recusa38(tmp_path, campo_inesperado="x")


def test_st_guid_divergente_da_constante(tmp_path):
    _recusa38(tmp_path, st_language_guid="00000000-0000-0000-0000-000000000000")


def test_st_guid_como_texto_ST_e_recusado(tmp_path):
    """`create_program` recusa `str` com TypeError: expected Nullable[Guid].
    O plano so transporta texto, e a string 'ST' nao substitui o GUID."""
    _recusa38(tmp_path, st_language_guid="ST")


def test_conversao_de_guid_falha_e_precondicao_nao_mutacao(tmp_path):
    def conversor_quebrado(_texto):
        return None, "System.Guid indisponivel"
    resultado, container, project, safety = _run38(
        tmp_path, guid_converter=conversor_quebrado)
    assert resultado["status"] == probe38.STATUS_PRECONDITION_FAILED
    assert safety.requested == []
    assert container.create_gvl_calls == []
    assert resultado["requires_copy_discard"] is False


def test_guid_convertido_chega_tipado_a_api(tmp_path):
    """A conversao acontece na PRECONDICAO: o duble de container levanta
    TypeError se receber `str`, exatamente como a run-005."""
    resultado, container, _p, _s = _run38(tmp_path)
    assert resultado["status"] == probe38.STATUS_SAVED_AS
    assert resultado["st_language_guid_converted"] is True
    _nome, idioma = container.create_program_calls[0]
    assert not isinstance(idioma, str)


def test_output_ja_existe(tmp_path):
    saida = os.path.join(str(tmp_path), "existe.project")
    handle = open(saida, "w")
    try:
        handle.write("ocupado")
    finally:
        handle.close()
    _recusa38(tmp_path, output_path=saida)


def test_fase_controlada_ausente_bloqueia_tudo(tmp_path):
    resultado, container, project, safety = _run38(
        tmp_path, safety=FakeSafety(phase=None))
    assert resultado["status"] == probe38.STATUS_PRECONDITION_FAILED
    assert safety.requested == []
    assert container.create_gvl_calls == []


def test_nome_alvo_ja_existente_bloqueia(tmp_path):
    container = FakeContainer(children=[FakeNode("GVL_AI_TESTE",
                                                 node_type=GVL_GUID)])
    resultado, container, project, safety = _run38(tmp_path, container=container)
    assert resultado["status"] == probe38.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


def test_container_type_divergente(tmp_path):
    container = FakeContainer(children=[], node_type="guid-errado")
    resultado, _c, _p, safety = _run38(tmp_path, container=container)
    assert resultado["status"] == probe38.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


# --- fault injection: um ponto de falha por mutacao --------------------------

def test_falha_em_create_gvl(tmp_path):
    container = FakeContainer(children=[],
                              create_gvl_error=RuntimeError("falha sintetica"))
    resultado, _c, project, _s = _run38(tmp_path, container=container)
    assert resultado["status"] == probe38.STATUS_CREATE_GVL_FAILED
    assert resultado["requires_copy_discard"] is True
    assert project.save_as_calls == []


def test_create_gvl_com_nome_errado_reprova_verificacao(tmp_path):
    container = FakeContainer(children=[], created_gvl_name="GVL_OUTRA")
    resultado, _c, project, _s = _run38(tmp_path, container=container)
    assert resultado["status"] == probe38.STATUS_GVL_VERIFICATION_FAILED
    assert resultado["requires_copy_discard"] is True
    assert project.save_as_calls == []


def test_create_gvl_com_type_guid_errado_reprova_verificacao(tmp_path):
    container = FakeContainer(children=[], gvl_type="guid-inesperado")
    resultado, _c, _p, _s = _run38(tmp_path, container=container)
    assert resultado["status"] == probe38.STATUS_GVL_VERIFICATION_FAILED


def test_falha_em_create_program_deixa_gvl_em_memoria(tmp_path):
    container = FakeContainer(children=[],
                              create_program_error=RuntimeError("falha"))
    resultado, container, project, _s = _run38(tmp_path, container=container)
    assert resultado["status"] == probe38.STATUS_CREATE_PROGRAM_FAILED
    assert resultado["requires_copy_discard"] is True
    # A GVL JA esta inserida na arvore: `create_*` nao tem rollback, e por
    # isso a unidade descartada e a copia inteira.
    assert [n._name for n in container._children] == ["GVL_AI_TESTE"]
    assert project.save_as_calls == []


def test_create_program_com_type_guid_errado_reprova_verificacao(tmp_path):
    container = FakeContainer(children=[], program_type="guid-inesperado")
    resultado, _c, project, _s = _run38(tmp_path, container=container)
    assert resultado["status"] == probe38.STATUS_PROGRAM_VERIFICATION_FAILED
    assert project.save_as_calls == []


class ContainerComReplaceInerte(FakeContainer):
    """A criacao funciona, mas o `replace` do documento indicado nao muda
    nada -- a verificacao intermediaria tem de pegar."""

    def __init__(self, alvo, **kwargs):
        FakeContainer.__init__(self, **kwargs)
        self._alvo = alvo

    def create_gvl(self, name):
        node = FakeContainer.create_gvl(self, name)
        if self._alvo == "gvl_declaration":
            self._children[-1] = _NoInerte(node, "declaration")
            return self._children[-1]
        return node

    def create_program(self, name, language):
        node = FakeContainer.create_program(self, name, language)
        if self._alvo in ("program_declaration", "program_implementation"):
            atributo = ("declaration" if self._alvo == "program_declaration"
                        else "implementation")
            self._children[-1] = _NoInerte(node, atributo)
            return self._children[-1]
        return node


class _DocInerte(object):
    def __init__(self, owner, attr):
        self.owner = owner
        self.attr = attr

    @property
    def text(self):
        if self.attr == "declaration":
            return self.owner._declaration
        return self.owner._implementation

    def replace(self, _new_text):
        return None                      # nao muda nada, de proposito


class _NoInerte(FakeNode):
    def __init__(self, origem, atributo_inerte):
        FakeNode.__init__(self, origem._name, node_type=origem.type,
                          declaration=origem._declaration,
                          implementation=origem._implementation)
        self._atributo_inerte = atributo_inerte

    @property
    def textual_declaration(self):
        if self._declaration is None:
            return None
        if self._atributo_inerte == "declaration":
            return _DocInerte(self, "declaration")
        return FakeDoc(self, "declaration")

    @property
    def textual_implementation(self):
        if self._implementation is None:
            return None
        if self._atributo_inerte == "implementation":
            return _DocInerte(self, "implementation")
        return FakeDoc(self, "implementation")


def test_replace_inerte_na_gvl_reprova_a_verificacao_intermediaria(tmp_path):
    container = ContainerComReplaceInerte("gvl_declaration", children=[])
    resultado, _c, project, safety = _run38(tmp_path, container=container)
    assert resultado["status"] == probe38.STATUS_GVL_TEXT_VERIFICATION_FAILED
    assert safety.requested == ["create_gvl", "create_program", "replace"]
    assert project.save_as_calls == []


def test_replace_inerte_na_declaracao_do_program(tmp_path):
    container = ContainerComReplaceInerte("program_declaration", children=[])
    resultado, _c, project, safety = _run38(tmp_path, container=container)
    assert resultado["status"] == \
        probe38.STATUS_PROGRAM_DECLARATION_VERIFICATION_FAILED
    assert safety.requested.count("replace") == 2
    assert project.save_as_calls == []


def test_replace_inerte_na_implementacao_do_program(tmp_path):
    container = ContainerComReplaceInerte("program_implementation", children=[])
    resultado, _c, project, safety = _run38(tmp_path, container=container)
    assert resultado["status"] == \
        probe38.STATUS_PROGRAM_IMPLEMENTATION_VERIFICATION_FAILED
    assert safety.requested.count("replace") == 3
    assert project.save_as_calls == []


def test_excecao_em_save_as_sem_retry(tmp_path):
    plano_path, plano = _plan(tmp_path)
    container = FakeContainer(children=[])
    project = FakeProject(plano["input_project"]["path"], [container],
                          raise_on_save_as=RuntimeError("falha"))
    resultado, _c, project, _s = _run38(tmp_path, plano_path=plano_path,
                                        container=container, project=project)
    assert resultado["status"] == probe38.STATUS_SAVE_AS_FAILED
    assert len(project.save_as_calls) == 1
    assert resultado["requires_copy_discard"] is True


def test_save_as_silencioso_sem_arquivo_reprova(tmp_path):
    plano_path, plano = _plan(tmp_path)
    container = FakeContainer(children=[])
    project = FakeProject(plano["input_project"]["path"], [container],
                          create_output=False)
    resultado, _c, _p, _s = _run38(tmp_path, plano_path=plano_path,
                                   container=container, project=project)
    assert resultado["status"] == probe38.STATUS_SAVE_AS_FAILED


# --- falsificacao das guardas -------------------------------------------------

def test_falsificacao_guarda_create_gvl(tmp_path):
    safety = FakeSafety(deny=("create_gvl",))
    resultado, container, project, safety = _run38(tmp_path, safety=safety)
    assert resultado["status"] == probe38.STATUS_PRECONDITION_FAILED
    assert safety.requested == ["create_gvl"]
    assert container._children == []
    assert project.save_as_calls == []


def test_falsificacao_guarda_create_program(tmp_path):
    safety = FakeSafety(deny=("create_program",))
    resultado, container, project, safety = _run38(tmp_path, safety=safety)
    assert resultado["status"] == probe38.STATUS_AUTHORED_IN_MEMORY
    assert resultado["requires_copy_discard"] is True
    assert [n._name for n in container._children] == ["GVL_AI_TESTE"]
    assert project.save_as_calls == []


def test_falsificacao_guarda_do_terceiro_replace(tmp_path):
    safety = DenyNthReplace(3)
    resultado, container, project, safety = _run38(tmp_path, safety=safety)
    assert resultado["status"] == probe38.STATUS_AUTHORED_IN_MEMORY
    assert resultado["requires_copy_discard"] is True
    assert container._children[1]._implementation == BORN_PROGRAM_IMPLEMENTATION
    assert project.save_as_calls == []


def test_falsificacao_guarda_save_as(tmp_path):
    safety = FakeSafety(deny=("save_as",))
    resultado, container, project, safety = _run38(tmp_path, safety=safety)
    assert resultado["status"] == probe38.STATUS_AUTHORED_IN_MEMORY
    assert resultado["requires_copy_discard"] is True
    assert project.save_as_calls == []


def test_fase_de_w1_3_nao_autoriza_w1_4(tmp_path):
    """Falsificacao de fase: com a allowlist de W1.3B (`replace`/`save_as`), a
    primeira mutacao de W1.4 e recusada na porta."""
    safety = FakeSafety(phase="W1_4_INTEGRATED_BUILD",
                        allowed=("replace", "save_as"))
    resultado, container, project, safety = _run38(tmp_path, safety=safety)
    assert resultado["status"] == probe38.STATUS_PRECONDITION_FAILED
    assert container.create_gvl_calls == []


# --- journal e artefatos ------------------------------------------------------

def test_journal_tem_attempt_e_done_para_cada_mutacao(tmp_path):
    resultado, _c, _p, _s = _run38(tmp_path)
    entradas = resultado["journal"]
    assert [e["sequence"] for e in entradas] == list(range(len(entradas)))
    tentativas = [e["operation"] for e in entradas
                  if e.get("event") == "mutation_attempt"]
    concluidas = [e["operation"] for e in entradas
                  if e.get("event") == "mutation_done"]
    assert tentativas == list(probe38.EXECUTED_OPERATION_SEQUENCE)
    assert concluidas == list(probe38.EXECUTED_OPERATION_SEQUENCE)


def test_journal_deixa_attempt_sem_done_quando_a_mutacao_levanta(tmp_path):
    """A assinatura de 'a copia esta em estado desconhecido'."""
    container = FakeContainer(children=[],
                              create_program_error=RuntimeError("falha"))
    resultado, _c, _p, _s = _run38(tmp_path, container=container)
    entradas = resultado["journal"]
    tentativas = [e["operation"] for e in entradas
                  if e.get("event") == "mutation_attempt"]
    concluidas = [e["operation"] for e in entradas
                  if e.get("event") == "mutation_done"]
    assert "create_program" in tentativas
    assert "create_program" not in concluidas


def test_call_sites_no_journal(tmp_path):
    resultado, _c, _p, _s = _run38(tmp_path)
    sites = [e.get("call_site") for e in resultado["journal"] if e.get("call_site")]
    for site in (probe38.CALL_SITE_CREATE_GVL, probe38.CALL_SITE_CREATE_PROGRAM,
                 probe38.CALL_SITE_REPLACE_GVL_DECLARATION,
                 probe38.CALL_SITE_REPLACE_PROGRAM_DECLARATION,
                 probe38.CALL_SITE_REPLACE_PROGRAM_IMPLEMENTATION,
                 probe38.CALL_SITE_SAVE_AS):
        assert site in sites


def test_completion_por_ultimo_e_declara_nada_alem(tmp_path):
    resultado, _c, _p, _s = _run38(tmp_path)
    escritos = probe38.write_artifacts(resultado, file_io)
    assert escritos[-1] == "completion.json"
    completion = probe38.build_completion(resultado)
    assert completion["no_other_mutator_requested"] is True
    assert completion["operations_executed"] == list(
        probe38.EXECUTED_OPERATION_SEQUENCE)
    assert completion["authored_gvl_declaration_sha256"]
    assert completion["authored_program_implementation_sha256"]


def test_operacao_fora_da_cadeia_reprova_no_other_mutator():
    assert probe38.no_other_mutator_requested(["create_gvl"]) is True
    assert probe38.no_other_mutator_requested(
        ["create_gvl", "create_program"]) is True
    assert probe38.no_other_mutator_requested(["save_as", "create_gvl"]) is False
    assert probe38.no_other_mutator_requested(
        list(probe38.EXECUTED_OPERATION_SEQUENCE) + ["build"]) is False


def test_todos_os_artefatos(tmp_path):
    resultado, _c, _p, _s = _run38(tmp_path)
    probe38.write_artifacts(resultado, file_io)
    presentes = os.listdir(resultado["artifacts_dir"])
    for nome in probe38.ARTIFACT_NAMES:
        if nome == "journal.jsonl":
            continue                     # gravado incrementalmente pelo Journal
        assert nome in presentes, nome


def test_normalizacao_de_texto_do_probe38():
    assert probe38.texts_match("a\r\nb\r\n", "a\nb\n")
    assert probe38.texts_match("a \nb\n", "a\nb")
    assert probe38.texts_match("a\nb\n\n", "a\nb\n") is False


# =============================================================================
# probe 37 -- verificacao somente leitura
# =============================================================================

def _flat(nodes):
    saida = []
    for node_id, name, type_guid in nodes:
        saida.append({"node_id": node_id, "parent_node_id": None, "depth": 3,
                      "index": 0, "name": name, "type_guid": type_guid,
                      "object_guid": None, "child_count": 0})
    return saida


BASE_FLAT = _flat([
    ("root", None, None),
    ("root/1", "Device", "225bfe47-7336-4dbc-9419-4105a7c831fa"),
    ("root/1/0/0", "Application", CONTAINER_GUID),
    ("root/1/0/0/0", "PLC_PRG", POU_GUID),
    ("root/1/0/0/1", "GVL_EXISTENTE", GVL_GUID),
])

DEPOIS_FLAT = BASE_FLAT + _flat([
    ("root/1/0/0/2", "GVL_AI_TESTE", GVL_GUID),
    ("root/1/0/0/3", "PRG_AI_TESTE", POU_GUID),
])


def _run37(tmp_path, mode="preflight", plano_path=None, container=None,
           project=None, flat_nodes=None, baseline_flat=None, output_sha=None,
           by_path=None, statistics=None, limits=None):
    if plano_path is None:
        plano_path, plano = _plan(tmp_path)
    else:
        plano = json.loads(io.open(plano_path, encoding="utf-8").read())
    container = container if container is not None else ReadOnlyContainer(
        children=[], forbid_replace=True)
    caminho_projeto = plano["output_project"]["path"] if mode == "postsave" \
        else plano["input_project"]["path"]
    if mode == "postsave" and not os.path.exists(caminho_projeto):
        handle = open(caminho_projeto, "w")
        try:
            handle.write("saida sintetica")
        finally:
            handle.close()
    project = project if project is not None else FakeProject(caminho_projeto,
                                                              [container])
    duplo = FakeProbeCli(container=container, by_path=by_path)
    argv = ["probe", "--plan=" + plano_path, "--mode=" + mode,
            "--output=" + os.path.join(str(tmp_path), "saida-probe37-" + mode)]
    if mode == "postsave":
        caminho_baseline = os.path.join(str(tmp_path), "baseline.json")
        file_io.write_json(caminho_baseline,
                           baseline_flat if baseline_flat is not None else BASE_FLAT)
        argv.append("--baseline=" + caminho_baseline)
        if output_sha is None:
            output_sha = _hash_of(caminho_projeto)
        argv.append("--output-sha256=" + output_sha)
    modulo = FakeScanModule(
        flat_nodes if flat_nodes is not None
        else (DEPOIS_FLAT if mode == "postsave" else BASE_FLAT),
        statistics=statistics, limits=limits)
    resultado = probe37.run_verify({"projects": object()}, argv,
                                   FakeProjectAccess(project), file_io, duplo,
                                   modulo)
    return resultado, container, project


def test_preflight_verificado(tmp_path):
    resultado, _c, _p = _run37(tmp_path, mode="preflight")
    assert resultado["status"] == probe37.PREFLIGHT_VERIFIED
    assert resultado["exit_code"] == 0
    assert resultado["name_conflicts"] == {"GVL_AI_TESTE": [], "PRG_AI_TESTE": []}


def test_preflight_recusa_nome_ja_existente(tmp_path):
    flat = BASE_FLAT + _flat([("root/1/0/0/2", "PRG_AI_TESTE", POU_GUID)])
    resultado, _c, _p = _run37(tmp_path, mode="preflight", flat_nodes=flat)
    assert resultado["status"] == probe37.NAME_CONFLICT


def test_preflight_recusa_container_com_type_divergente(tmp_path):
    container = ReadOnlyContainer(children=[], node_type="guid-errado",
                                  forbid_replace=True)
    resultado, _c, _p = _run37(tmp_path, mode="preflight", container=container)
    assert resultado["status"] == probe37.CONTAINER_NOT_FOUND


def test_preflight_recusa_varredura_truncada(tmp_path):
    """Arvore incompleta como linha de base acusaria remocao onde houve so
    limite."""
    resultado, _c, _p = _run37(
        tmp_path, mode="preflight",
        limits={"max_depth_reached": True, "max_total_nodes_reached": False,
                "max_children_per_node_reached": False})
    assert resultado["status"] == probe37.SCAN_INCOMPLETE


def test_preflight_recusa_varredura_com_no_falho(tmp_path):
    resultado, _c, _p = _run37(
        tmp_path, mode="preflight",
        statistics={"scan_complete": True, "failed_nodes": 2})
    assert resultado["status"] == probe37.SCAN_INCOMPLETE


def test_preflight_recusa_plano_com_st_guid_divergente(tmp_path):
    plano_path, _p = _plan(tmp_path, st_language_guid="00000000-0000-0000-0000-000000000000")
    resultado, _c, _pr = _run37(tmp_path, mode="preflight", plano_path=plano_path)
    assert resultado["status"] == probe37.PLAN_REJECTED


def _postsave_objetos(container):
    gvl = FakeNode("GVL_AI_TESTE", node_type=GVL_GUID,
                   declaration=GVL_DECLARATION, forbid_replace=True)
    programa = FakeNode("PRG_AI_TESTE", node_type=POU_GUID,
                        declaration=PROGRAM_DECLARATION,
                        implementation=PROGRAM_IMPLEMENTATION,
                        forbid_replace=True)
    return {(1, 0, 0): container, (1, 0, 0, 2): gvl, (1, 0, 0, 3): programa}, \
        gvl, programa


def test_postsave_verificado(tmp_path):
    container = ReadOnlyContainer(children=[], forbid_replace=True)
    by_path, _g, _pr = _postsave_objetos(container)
    resultado, _c, _p = _run37(tmp_path, mode="postsave", container=container,
                               by_path=by_path)
    assert resultado["status"] == probe37.POSTSAVE_VERIFIED
    assert resultado["exit_code"] == 0
    diff = resultado["structural_diff"]
    assert diff["missing"] == []
    assert diff["unexpected_additions"] == []


def test_postsave_diff_com_objeto_a_mais_reprova(tmp_path):
    container = ReadOnlyContainer(children=[], forbid_replace=True)
    by_path, _g, _pr = _postsave_objetos(container)
    flat = DEPOIS_FLAT + _flat([("root/1/0/0/4", "DUT_INESPERADO", "outro-guid")])
    resultado, _c, _p = _run37(tmp_path, mode="postsave", container=container,
                               by_path=by_path, flat_nodes=flat)
    assert resultado["status"] == probe37.STRUCTURAL_DIFF_UNEXPECTED


def test_postsave_diff_com_objeto_removido_reprova(tmp_path):
    container = ReadOnlyContainer(children=[], forbid_replace=True)
    by_path, _g, _pr = _postsave_objetos(container)
    flat = [n for n in DEPOIS_FLAT if n["name"] != "GVL_EXISTENTE"]
    resultado, _c, _p = _run37(tmp_path, mode="postsave", container=container,
                               by_path=by_path, flat_nodes=flat)
    assert resultado["status"] == probe37.STRUCTURAL_DIFF_UNEXPECTED


def test_postsave_hash_divergente_reprova(tmp_path):
    container = ReadOnlyContainer(children=[], forbid_replace=True)
    by_path, _g, _pr = _postsave_objetos(container)
    resultado, _c, _p = _run37(tmp_path, mode="postsave", container=container,
                               by_path=by_path, output_sha="0" * 64)
    assert resultado["status"] == probe37.OUTPUT_HASH_MISMATCH


def test_postsave_texto_divergente_reprova(tmp_path):
    container = ReadOnlyContainer(children=[], forbid_replace=True)
    by_path, gvl, _pr = _postsave_objetos(container)
    gvl._declaration = "{attribute 'qualified_only'}\nVAR_GLOBAL\nEND_VAR"
    resultado, _c, _p = _run37(tmp_path, mode="postsave", container=container,
                               by_path=by_path)
    assert resultado["status"] == probe37.FINAL_TEXT_MISMATCH


def test_postsave_sem_o_prefixo_qualificado_reprova(tmp_path):
    """Implementacao sem `GVL_AI_TESTE.` diverge do texto canonico -- e o
    proprio motivo pelo qual o prefixo entra desde o plano."""
    container = ReadOnlyContainer(children=[], forbid_replace=True)
    by_path, _g, programa = _postsave_objetos(container)
    programa._implementation = "xLocal := g_xTesteCriacao;\n"
    resultado, _c, _p = _run37(tmp_path, mode="postsave", container=container,
                               by_path=by_path)
    assert resultado["status"] == probe37.FINAL_TEXT_MISMATCH


def test_postsave_exige_baseline(tmp_path):
    plano_path, plano = _plan(tmp_path)
    container = ReadOnlyContainer(children=[], forbid_replace=True)
    caminho = plano["output_project"]["path"]
    handle = open(caminho, "w")
    try:
        handle.write("saida")
    finally:
        handle.close()
    project = FakeProject(caminho, [container])
    duplo = FakeProbeCli(container=container)
    argv = ["probe", "--plan=" + plano_path, "--mode=postsave",
            "--output=" + os.path.join(str(tmp_path), "saida-sem-baseline")]
    resultado = probe37.run_verify({"projects": object()}, argv,
                                   FakeProjectAccess(project), file_io, duplo,
                                   FakeScanModule(DEPOIS_FLAT))
    assert resultado["status"] == probe37.STATUS_FATAL


def test_modo_invalido_recusado(tmp_path):
    plano_path, plano = _plan(tmp_path)
    container = ReadOnlyContainer(children=[], forbid_replace=True)
    project = FakeProject(plano["input_project"]["path"], [container])
    duplo = FakeProbeCli(container=container)
    argv = ["probe", "--plan=" + plano_path, "--mode=algo_invalido",
            "--output=" + os.path.join(str(tmp_path), "saida")]
    resultado = probe37.run_verify({"projects": object()}, argv,
                                   FakeProjectAccess(project), file_io, duplo,
                                   FakeScanModule(BASE_FLAT))
    assert resultado["status"] == probe37.STATUS_FATAL


def test_presencas_da_secao_7_sao_conferidas():
    faltando = probe37.contains_all_tokens("xLocal := g_xTesteCriacao;",
                                           probe37.REQUIRED_IMPLEMENTATION_TOKENS)
    assert "GVL_AI_TESTE.g_xTesteCriacao" in faltando
    assert probe37.contains_all_tokens(PROGRAM_IMPLEMENTATION,
                                       probe37.REQUIRED_IMPLEMENTATION_TOKENS) == []


def test_diff_exato_e_o_da_secao_6():
    diff = probe37.structural_diff(BASE_FLAT, DEPOIS_FLAT)
    assert probe37.diff_is_exact(diff) is True
    assert sorted(diff["added"]) == sorted(
        [list(item) for item in probe37.ALLOWED_ADDITIONS])


def test_um_unico_objeto_novo_nao_basta():
    parcial = BASE_FLAT + _flat([("root/1/0/0/2", "GVL_AI_TESTE", GVL_GUID)])
    diff = probe37.structural_diff(BASE_FLAT, parcial)
    assert probe37.diff_is_exact(diff) is False


def test_todos_os_status_tem_um_por_sucesso_probe37():
    for status in probe37.ALL_STATUSES:
        esperado = status in probe37.SUCCESS_STATUSES
        assert (probe37.EXIT_BY_STATUS[status] == 0) is esperado, status


def test_artefatos_do_probe37_terminam_na_completion(tmp_path):
    container = ReadOnlyContainer(children=[], forbid_replace=True)
    by_path, _g, _pr = _postsave_objetos(container)
    resultado, _c, _p = _run37(tmp_path, mode="postsave", container=container,
                               by_path=by_path)
    escritos = probe37.write_artifacts(resultado, file_io)
    assert escritos[-1] == "w1-4-postsave-completion.json"


# =============================================================================
# verificacao estatica -- probe 38 (autoria)
# =============================================================================

@pytest.fixture(scope="module")
def tree38():
    return ast.parse(io.open(PROBE38_PATH, encoding="utf-8").read())


@pytest.fixture(scope="module")
def tree37():
    return ast.parse(io.open(PROBE37_PATH, encoding="utf-8").read())


def _calls(tree):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)]


def _method_calls(tree, nome):
    return [n for n in _calls(tree)
            if isinstance(n.func, ast.Attribute) and n.func.attr == nome]


def _calls_by_receiver(tree, receptores):
    encontrados = []
    for no in ast.walk(tree):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            receptor = no.func.value
            if isinstance(receptor, ast.Name) and receptor.id in receptores:
                encontrados.append((receptor.id, no.func.attr))
    return encontrados


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
    """Pares (guarda, mutacao) em que a guarda de `operacao` e a instrucao
    IMEDIATAMENTE anterior a uma chamada de `mutador`, no mesmo bloco.

    Restrito a instrucao-expressao e a atribuicao simples: sem essa restricao,
    dois `def` adjacentes -- um com a guarda, outro com a mutacao, cada um na
    SUA funcao -- casariam como se fossem adjacentes.
    """
    pares = []
    aceitos = (ast.Expr, ast.Assign)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        index = 0
        while index < len(body) - 1:
            atual, seguinte = body[index], body[index + 1]
            if isinstance(atual, aceitos) and isinstance(seguinte, aceitos) \
                    and _guard_calls(atual, operacao) \
                    and _method_calls(seguinte, mutador):
                pares.append((atual, seguinte))
            index = index + 1
    return pares


def test_probe38_tem_exatamente_um_create_gvl(tree38):
    assert len(_method_calls(tree38, "create_gvl")) == 1


def test_probe38_tem_exatamente_um_create_program(tree38):
    assert len(_method_calls(tree38, "create_program")) == 1


def test_probe38_tem_exatamente_tres_replace(tree38):
    assert len(_method_calls(tree38, "replace")) == 3


def test_probe38_tem_exatamente_um_save_as(tree38):
    assert len(_method_calls(tree38, "save_as")) == 1


def test_probe38_tem_seis_guardas(tree38):
    guardas = [n for n in _calls(tree38)
               if isinstance(n.func, ast.Attribute)
               and n.func.attr == "assert_controlled_write_allowed"]
    assert len(guardas) == 6


@pytest.mark.parametrize("operacao,mutador,quantidade", [
    ("create_gvl", "create_gvl", 1),
    ("create_program", "create_program", 1),
    ("replace", "replace", 3),
    ("save_as", "save_as", 1),
])
def test_cada_mutacao_tem_guarda_adjacente(tree38, operacao, mutador, quantidade):
    pares = _adjacent_pairs(tree38, operacao, mutador)
    assert len(pares) == quantidade
    for guarda, mutacao in pares:
        assert mutacao.lineno == guarda.lineno + 1


def test_replace_chamado_apenas_com_constantes_do_modulo(tree38):
    chamadas = _method_calls(tree38, "replace")
    esperados = {"GVL_DECLARATION", "PROGRAM_DECLARATION",
                 "PROGRAM_IMPLEMENTATION"}
    encontrados = set()
    for chamada in chamadas:
        assert len(chamada.args) == 1
        assert isinstance(chamada.args[0], ast.Name)
        encontrados.add(chamada.args[0].id)
    assert encontrados == esperados


def test_create_recebe_nome_de_constante_do_modulo(tree38):
    for nome, constante in (("create_gvl", "EXPECTED_GVL_NAME"),
                            ("create_program", "EXPECTED_PROGRAM_NAME")):
        chamada = _method_calls(tree38, nome)[0]
        assert isinstance(chamada.args[0], ast.Name)
        assert chamada.args[0].id == constante


def test_documento_textual_so_recebe_replace_no_probe38(tree38):
    """Garantia por RECEPTOR: `insert`/`append`/`remove` existem em
    `IScriptTextDocument` E em `list`. Proibi-los por NOME quebraria em
    `lista.append(...)`; o que decide e o receptor."""
    receptores = ("gvl_declaration_document", "program_declaration_document",
                  "program_implementation_document", "document", "text_document")
    chamadas = _calls_by_receiver(tree38, receptores)
    assert chamadas, "nenhuma chamada no documento textual foi encontrada"
    for receptor, metodo in chamadas:
        assert metodo == "replace", (
            "%s.%s() nao e permitido: o documento so recebe replace()"
            % (receptor, metodo))


def test_container_e_projeto_so_recebem_o_que_lhes_cabe(tree38):
    permitido = {
        "iec_container": set(["create_gvl", "create_program", "get_children"]),
        "project": set(["save_as", "get_children", "get_name"]),
    }
    for receptor, metodo in _calls_by_receiver(tree38, tuple(permitido)):
        assert metodo in permitido[receptor], "%s.%s()" % (receptor, metodo)


@pytest.mark.parametrize("metodo", [
    "create_pou", "create_dut", "create_folder", "create_function",
    "create_function_block", "create_persistentvars", "create_interface",
    "save", "save_archive", "build", "rebuild", "clean", "replace_line",
    "rename", "move", "import_xml", "import_native", "add_library",
    "remove_library", "download_missing_libraries",
    "set_compilerversion_to_newest", "Invoke",
])
# `insert`/`append`/`remove` ficam FORA desta lista de proposito: sao nomes de
# `list`/`sys.path` tambem, e a proibicao correta e por receptor (teste acima).
def test_mutador_proibido_ausente_no_probe38(tree38, metodo):
    assert _method_calls(tree38, metodo) == []


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_sem_acesso_dinamico_probe38(tree38, nome):
    assert [n for n in _calls(tree38)
            if isinstance(n.func, ast.Name) and n.func.id == nome] == []


def test_sem_lambda_nem_fstring_probe38(tree38):
    assert [n for n in ast.walk(tree38) if isinstance(n, ast.Lambda)] == []
    assert [n for n in ast.walk(tree38)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []


def test_identificadores_ascii_probe38(tree38):
    for node in ast.walk(tree38):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


def test_textos_canonicos_sao_constantes_de_modulo():
    """Os tres textos vem do MODULO, e o modulo os declara exatamente como
    `docs/32` os fixa -- inclusive o pragma e o prefixo qualificado."""
    assert probe38.GVL_DECLARATION == GVL_DECLARATION
    assert probe38.PROGRAM_DECLARATION == PROGRAM_DECLARATION
    assert probe38.PROGRAM_IMPLEMENTATION == PROGRAM_IMPLEMENTATION
    assert probe37.GVL_DECLARATION == probe38.GVL_DECLARATION
    assert probe37.PROGRAM_DECLARATION == probe38.PROGRAM_DECLARATION
    assert probe37.PROGRAM_IMPLEMENTATION == probe38.PROGRAM_IMPLEMENTATION


def test_a_fase_esperada_e_a_de_w1_4():
    assert probe37.EXPECTED_PHASE == "W1_4_INTEGRATED_BUILD"
    assert probe38.EXPECTED_PHASE == "W1_4_INTEGRATED_BUILD"


# =============================================================================
# verificacao estatica -- probe 37 (somente leitura)
# =============================================================================

@pytest.mark.parametrize("metodo", [
    "create_gvl", "create_program", "create_pou", "create_dut", "create_folder",
    "create_function", "create_function_block", "save", "save_as",
    "save_archive", "replace", "replace_line", "rename", "move", "build",
    "rebuild", "clean", "import_xml", "Invoke",
])
def test_mutador_proibido_ausente_no_probe37(tree37, metodo):
    assert _method_calls(tree37, metodo) == []


def test_probe37_nao_chama_a_guarda(tree37):
    guardas = [n for n in _calls(tree37)
               if isinstance(n.func, ast.Attribute)
               and n.func.attr == "assert_controlled_write_allowed"]
    assert guardas == []


def test_probe37_nunca_escreve_em_documento_textual(tree37):
    receptores = ("document", "text_document", "declaration_document",
                  "implementation_document")
    for receptor, metodo in _calls_by_receiver(tree37, receptores):
        assert metodo not in ("replace", "insert", "append", "remove",
                              "replace_line"), "%s.%s()" % (receptor, metodo)


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_sem_acesso_dinamico_probe37(tree37, nome):
    assert [n for n in _calls(tree37)
            if isinstance(n.func, ast.Name) and n.func.id == nome] == []


def test_sem_lambda_nem_fstring_probe37(tree37):
    assert [n for n in ast.walk(tree37) if isinstance(n, ast.Lambda)] == []
    assert [n for n in ast.walk(tree37)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []


def test_identificadores_ascii_probe37(tree37):
    for node in ast.walk(tree37):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


def test_busca_literal_zero_mutadores_no_probe37():
    """Busca literal, sem AST: `.replace(`, `.save_as(`, `.save(`, `.build(` e
    `getattr(` nao aparecem em lugar nenhum do arquivo -- nem em codigo, nem em
    comentario, nem em docstring."""
    texto = io.open(PROBE37_PATH, encoding="utf-8").read()
    for proibido in (".replace(", ".save_as(", ".save(", ".build(",
                     ".create_gvl(", ".create_program(", "getattr("):
        assert proibido not in texto, proibido

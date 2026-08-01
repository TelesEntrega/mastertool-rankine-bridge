"""Testes de `probes/27_create_gvl_w1_1.py` com dubles ESTRITOS.

Nenhuma API real do MasterTool e importada ou chamada. Nenhum projeto e
aberto. Os fakes LEVANTAM se o probe tocar qualquer membro que nao esteja
expressamente autorizado -- e o que transforma "o probe nao deveria fazer isso"
em teste, e nao em promessa.

Fixtures inteiramente sinteticas: nenhum nome de equipamento, projeto ou
caminho de cliente aparece aqui.
"""

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


def _load_probe():
    """Carrega o probe pelo CAMINHO: o nome do arquivo comeca com digito, entao
    `import probes.27_...` seria SyntaxError. O rodape e guardado por
    `if "projects" in globals()`, entao carregar aqui nao executa main()."""
    path = os.path.join(_MASTERTOOL_DIR, "probes", "27_create_gvl_w1_1.py")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("probe27_w1_1", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except ImportError:                                        # IronPython 2.7
        import imp
        return imp.load_source("probe27_w1_1", path)


probe = _load_probe()


# --- dubles estritos --------------------------------------------------------

class ForbiddenMemberTouched(AssertionError):
    """O probe tocou algo que nao deveria."""


class StrictObject(object):
    """Base: qualquer membro fora de `_allowed` levanta."""

    _allowed = ()

    def __getattr__(self, name):
        raise ForbiddenMemberTouched(
            "%s tocou membro nao autorizado: %r" % (type(self).__name__, name))


class FakeChildren(object):
    def __init__(self, items):
        self._items = list(items)

    @property
    def Count(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]


class FakeNode(StrictObject):
    """No da arvore. Expoe apenas o que o probe pode ler."""

    def __init__(self, name, children=None, transient=False, is_folder=False,
                 has_declaration=True, declaration_text="VAR_GLOBAL\nEND_VAR"):
        self._name = name
        self._children = list(children or [])
        self.is_transient_object = transient
        self.is_folder = is_folder
        self.has_textual_declaration = has_declaration
        self.type_guid = "type-guid-sintetico"
        self.guid = "object-guid-sintetico"
        self._declaration_text = declaration_text
        self.create_gvl_calls = []

    def get_name(self, _recursive):
        return self._name

    def get_children(self, _recursive):
        return FakeChildren(self._children)

    @property
    def textual_declaration(self):
        if self._declaration_text is None:
            return None
        return FakeTextDocument(self._declaration_text)


class FakeTextDocument(StrictObject):
    """So leitura. `replace` levanta: o probe 27 nunca pode chama-lo."""

    def __init__(self, text):
        self.text = text
        self.length = len(text)
        self.linecount = len(text.split("\n"))

    def replace(self, *_args, **_kwargs):
        raise ForbiddenMemberTouched("probe 27 chamou replace()")

    def insert(self, *_args, **_kwargs):
        raise ForbiddenMemberTouched("probe 27 chamou insert()")


class FakeContainer(FakeNode):
    """Container IEC. `create_gvl` e a unica criacao permitida."""

    def __init__(self, children=None, created_name="GVL_AI_TESTE",
                 raise_on_create=None, created_object=None):
        FakeNode.__init__(self, "Application", children=children)
        self._created_name = created_name
        self._raise_on_create = raise_on_create
        self._forced_object = created_object

    def create_gvl(self, name):
        self.create_gvl_calls.append(name)
        if self._raise_on_create is not None:
            raise self._raise_on_create
        if self._forced_object is not None:
            novo = self._forced_object
        else:
            novo = FakeNode(self._created_name)
        self._children.append(novo)
        return novo

    def create_pou(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 27 chamou create_pou()")

    def create_program(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 27 chamou create_program()")

    def create_folder(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 27 chamou create_folder()")

    def remove(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 27 tentou rollback via remove()")

    def rename(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 27 chamou rename()")


class FakeProject(StrictObject):
    def __init__(self, path, children, raise_on_save_as=None,
                 create_output=True):
        self.path = path
        self._root_children = list(children)
        self._raise_on_save_as = raise_on_save_as
        self._create_output = create_output
        self.save_as_calls = []

    def get_children(self, _recursive):
        return FakeChildren(self._root_children)

    def get_name(self, _recursive):
        return "projeto-sintetico"

    def save_as(self, path):
        self.save_as_calls.append(path)
        if self._raise_on_save_as is not None:
            raise self._raise_on_save_as
        if self._create_output:
            handle = open(path, "w")
            try:
                handle.write("projeto salvo sintetico")
            finally:
                handle.close()

    def save(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 27 chamou save()")

    def build(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 27 chamou build()")

    def import_xml(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 27 chamou import_xml()")


class FakeSafety(object):
    """Espelha a porta unica. Registra o que foi pedido, na ordem."""

    class SafetyError(Exception):
        pass

    def __init__(self, phase="W1_1_CREATE_GVL", allowed=("create_gvl", "save_as"),
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

    def assert_operation_allowed(self, operation):
        raise ForbiddenMemberTouched(
            "probe 27 usou a porta legada para %r" % (operation,))


class FakeProjectAccess(object):
    def __init__(self, project, error=None):
        self._project = project
        self._error = error

    def get_primary_project(self, _globals):
        return self._project, self._error

    def get_project_path(self, project):
        return project.path


# --- helpers de plano -------------------------------------------------------

def _hash_of(path):
    digest, _erro = probe.sha256_of_file(path)
    return digest


def _make_input_project(tmp_path, nome="entrada.project"):
    caminho = os.path.join(str(tmp_path), nome)
    handle = open(caminho, "w")
    try:
        handle.write("conteudo sintetico do projeto")
    finally:
        handle.close()
    return caminho


def _plan(tmp_path, **overrides):
    entrada = overrides.pop("input_path", None) or _make_input_project(tmp_path)
    saida = overrides.pop("output_path", None) or os.path.join(str(tmp_path), "saida.project")
    artefatos = overrides.pop("artifacts_dir", None) or os.path.join(str(tmp_path), "art")
    plano = {
        "schema_version": "1.0",
        "operation_id": "w1-1-create-gvl",
        "phase": "W1_1_CREATE_GVL",
        "gvl_name": "GVL_AI_TESTE",
        "run_id": "run-sintetica-001",
        "input_project": {"path": entrada, "sha256": _hash_of(entrada)},
        "output_project": {"path": saida},
        "artifacts_dir": artefatos,
        "container": {"node_path": "root/0"},
        "mastertool": {"version": "4.1.0.11", "script_engine": "4.2.0.0"},
        "operations": [{"kind": "create_gvl", "name": "GVL_AI_TESTE"},
                       {"kind": "save_as", "path": saida}],
    }
    plano.update(overrides)
    return plano


def _write_plan(tmp_path, plano, nome="plano.json"):
    caminho = os.path.join(str(tmp_path), nome)
    handle = open(caminho, "w")
    try:
        handle.write(json.dumps(plano))
    finally:
        handle.close()
    return caminho


class FakeProbeCli(object):
    """Reusa a logica real de argumentos e navegacao -- ela ja tem testes
    proprios -- e nada mais."""

    def __init__(self, container=None, descend_result=None):
        self._container = container
        self._descend_override = descend_result

    def find_arg(self, argv, name):
        return probe_cli.find_arg(argv, name)

    def parse_node_id(self, raw, problems, label="--node-id"):
        return probe_cli.parse_node_id(raw, problems, label=label)

    def runtime_identity(self):
        return {"executable": "MT9000.exe", "file_version": "4.1.0.11",
                "product_version": "4.1.0.11",
                "script_runtime": "MT9000.exe Mastertool X 4.1.0.11", "error": None}

    def descend(self, project, indexes, trace):
        if self._descend_override is not None:
            return self._descend_override
        return self._container


def _run(tmp_path, plano=None, container=None, project=None, safety=None,
         probe_cli_double=None, argv=None):
    plano = plano if plano is not None else _plan(tmp_path)
    caminho_plano = _write_plan(tmp_path, plano)
    container = container if container is not None else FakeContainer()
    project = project if project is not None else FakeProject(
        plano["input_project"]["path"], [container])
    safety = safety if safety is not None else FakeSafety()
    probe_cli_double = probe_cli_double or FakeProbeCli(container=container)
    argv = argv or ["probe", "--plan=" + caminho_plano]
    resultado = probe.run_w1_1(
        {"projects": object()}, argv, safety,
        FakeProjectAccess(project), file_io, probe_cli_double)
    return resultado, container, project, safety


# --- 0. regressao: o nome do membro de identidade ---------------------------

class _NoSoComTypeGuid(object):
    type_guid = "guid-sintetico"

    def get_name(self, _recursive):
        return "Objeto"


class _NoComType(object):
    type = "guid-sintetico"

    def get_name(self, _recursive):
        return "Objeto"


def test_identidade_le_o_membro_type_e_nao_type_guid():
    """`type_guid` e o nome do CAMPO na saida do scanner; o membro de
    IScriptObject chama-se `type`. Ler o nome errado gravava None em todo
    artefato -- e no probe 28 o mesmo engano reprovou um preflight real."""
    assert probe.object_identity(_NoSoComTypeGuid())["type_guid"] is None
    assert probe.object_identity(_NoComType())["type_guid"] == "guid-sintetico"


# --- 1. caminho feliz -------------------------------------------------------

def test_plano_valido_termina_em_saved_as(tmp_path):
    resultado, container, project, safety = _run(tmp_path)
    assert resultado["status"] == probe.STATUS_SAVED_AS
    assert resultado["exit_code"] == 0
    assert resultado["requires_copy_discard"] is False
    assert container.create_gvl_calls == ["GVL_AI_TESTE"]
    assert len(project.save_as_calls) == 1
    assert safety.requested == ["create_gvl", "save_as"]


def test_somente_saved_as_produz_codigo_zero():
    for status in probe.ALL_STATUSES:
        codigo = probe.EXIT_BY_STATUS[status]
        if status == probe.STATUS_SAVED_AS:
            assert codigo == 0
        else:
            assert codigo != 0


# --- 2-11. recusa do plano, sem tocar o projeto -----------------------------

def _recusa(tmp_path, **overrides):
    plano = _plan(tmp_path, **overrides)
    resultado, container, project, safety = _run(tmp_path, plano=plano)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert resultado["exit_code"] == 2
    assert container.create_gvl_calls == []
    assert project.save_as_calls == []
    assert safety.requested == []
    return resultado


def test_schema_desconhecido(tmp_path):
    _recusa(tmp_path, schema_version="9.9")


def test_fase_incorreta_no_plano(tmp_path):
    _recusa(tmp_path, phase="W1_2_CREATE_PROGRAM")


def test_operacao_adicional(tmp_path):
    saida = os.path.join(str(tmp_path), "saida.project")
    _recusa(tmp_path, operations=[{"kind": "create_gvl", "name": "GVL_AI_TESTE"},
                                  {"kind": "save_as", "path": saida},
                                  {"kind": "build"}])


def test_operacao_ausente(tmp_path):
    _recusa(tmp_path, operations=[{"kind": "create_gvl", "name": "GVL_AI_TESTE"}])


def test_operacoes_fora_de_ordem(tmp_path):
    saida = os.path.join(str(tmp_path), "saida.project")
    _recusa(tmp_path, operations=[{"kind": "save_as", "path": saida},
                                  {"kind": "create_gvl", "name": "GVL_AI_TESTE"}])


def test_nome_de_gvl_diferente(tmp_path):
    _recusa(tmp_path, gvl_name="GVL_OUTRA")


def test_hash_invalido_no_plano(tmp_path):
    entrada = _make_input_project(tmp_path)
    _recusa(tmp_path, input_path=entrada,
            input_project={"path": entrada, "sha256": "nao-e-um-hash"})


def test_output_ja_existente(tmp_path):
    saida = os.path.join(str(tmp_path), "ja-existe.project")
    handle = open(saida, "w")
    try:
        handle.write("ocupado")
    finally:
        handle.close()
    _recusa(tmp_path, output_path=saida)


def test_output_igual_a_entrada(tmp_path):
    entrada = _make_input_project(tmp_path)
    _recusa(tmp_path, input_path=entrada, output_path=entrada,
            input_project={"path": entrada, "sha256": _hash_of(entrada)})


def test_caminho_relativo(tmp_path):
    _recusa(tmp_path, output_path="saida-relativa.project")


def test_caminho_com_espaco(tmp_path):
    _recusa(tmp_path, output_path=os.path.join(str(tmp_path), "com espaco.project"))


def test_campo_desconhecido_falha_fechado(tmp_path):
    _recusa(tmp_path, campo_inesperado="valor")


def test_artifacts_dir_dentro_do_repositorio(tmp_path):
    _recusa(tmp_path, artifacts_dir=os.path.join(_REPO_ROOT, "workspace", "x"))


# --- 12-16. precondicoes de runtime -----------------------------------------

def test_container_ausente(tmp_path):
    plano = _plan(tmp_path)
    container = FakeContainer()
    project = FakeProject(plano["input_project"]["path"], [container])
    duplo = FakeProbeCli(container=None)
    resultado, _c, _p, safety = _run(tmp_path, plano=plano, container=container,
                                     project=project, probe_cli_double=duplo)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_gvl_calls == []
    assert safety.requested == []


def test_container_node_path_invalido(tmp_path):
    _recusa(tmp_path, container={"node_path": "sem-root/1"})


def test_gvl_ja_existente_no_container(tmp_path):
    container = FakeContainer(children=[FakeNode("GVL_AI_TESTE")])
    resultado, container, project, safety = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_gvl_calls == []
    assert safety.requested == []


def test_hash_da_entrada_divergente(tmp_path):
    entrada = _make_input_project(tmp_path)
    plano = _plan(tmp_path, input_path=entrada,
                  input_project={"path": entrada, "sha256": "0" * 64})
    resultado, container, _p, safety = _run(tmp_path, plano=plano)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_gvl_calls == []
    assert safety.requested == []


def test_fase_controlada_divergente_em_runtime(tmp_path):
    safety = FakeSafety(phase="W1_2_CREATE_PROGRAM")
    resultado, container, _p, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_gvl_calls == []
    assert safety.requested == []


def test_instalacao_inesperada(tmp_path):
    class OutraInstalacao(FakeProbeCli):
        def runtime_identity(self):
            info = FakeProbeCli.runtime_identity(self)
            info["file_version"] = "4.0.0.1"
            return info

    container = FakeContainer()
    duplo = OutraInstalacao(container=container)
    resultado, container, _p, safety = _run(tmp_path, container=container,
                                            probe_cli_double=duplo)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_gvl_calls == []


def test_projeto_aberto_diferente_do_plano(tmp_path):
    plano = _plan(tmp_path)
    container = FakeContainer()
    outro = FakeProject(os.path.join(str(tmp_path), "outro.project"), [container])
    resultado, container, _p, safety = _run(tmp_path, plano=plano,
                                            container=container, project=outro)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_gvl_calls == []


# --- 17-24. autorizacao e verificacao pos-criacao ---------------------------

def test_autorizacao_de_create_gvl_recusada(tmp_path):
    safety = FakeSafety(deny=("create_gvl",))
    resultado, container, project, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe.STATUS_PRECONDITION_FAILED
    assert container.create_gvl_calls == []
    assert project.save_as_calls == []
    assert safety.requested == ["create_gvl"]


def test_create_gvl_chamado_exatamente_uma_vez_com_literal(tmp_path):
    _resultado, container, _p, _s = _run(tmp_path)
    assert container.create_gvl_calls == ["GVL_AI_TESTE"]


def test_objeto_retornado_nulo(tmp_path):
    class ContainerNulo(FakeContainer):
        def create_gvl(self, name):
            self.create_gvl_calls.append(name)
            return None

    container = ContainerNulo()
    resultado, container, project, _s = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED
    assert resultado["requires_copy_discard"] is True
    assert project.save_as_calls == []


def test_objeto_com_nome_incorreto(tmp_path):
    container = FakeContainer(created_name="GVL_ERRADA")
    resultado, container, project, _s = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED
    assert project.save_as_calls == []


def test_objeto_com_tipo_incorreto(tmp_path):
    errado = FakeNode("GVL_AI_TESTE", has_declaration=False, is_folder=True)
    container = FakeContainer(created_object=errado)
    resultado, container, project, _s = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED
    assert project.save_as_calls == []


def test_objeto_persistente_extra(tmp_path):
    class ContainerRuidoso(FakeContainer):
        def create_gvl(self, name):
            self.create_gvl_calls.append(name)
            novo = FakeNode("GVL_AI_TESTE")
            self._children.append(novo)
            self._children.append(FakeNode("PRG_INESPERADO"))
            return novo

    container = ContainerRuidoso()
    resultado, container, project, _s = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED
    assert "PRG_INESPERADO" in str(resultado["problems"])
    assert project.save_as_calls == []


def test_objeto_transiente_registrado_separadamente(tmp_path):
    class ContainerTransiente(FakeContainer):
        def create_gvl(self, name):
            self.create_gvl_calls.append(name)
            novo = FakeNode("GVL_AI_TESTE")
            self._children.append(novo)
            self._children.append(FakeNode("TRANSIENTE", transient=True))
            return novo

    container = ContainerTransiente()
    resultado, container, project, _s = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_SAVED_AS
    assert resultado["verification"]["transient_added"] == ["TRANSIENTE"]
    assert resultado["verification"]["persistent_added"] == ["GVL_AI_TESTE"]


def test_leitura_da_declaracao_vazia(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    criado = resultado["created_gvl"]
    assert criado["text"] == "VAR_GLOBAL\nEND_VAR"
    assert criado["linecount"] == 2
    assert criado["sha256"]


def test_lacuna_registrada_quando_nao_ha_declaracao(tmp_path):
    sem_texto = FakeNode("GVL_AI_TESTE", declaration_text=None)
    container = FakeContainer(created_object=sem_texto)
    resultado, _c, _p, _s = _run(tmp_path, container=container)
    assert resultado["created_gvl"]["gap"]
    assert any("declaracao canonica" in nota for nota in resultado["gap_notes"])


# --- 26-34. o que nunca pode ser chamado ------------------------------------

def test_replace_nunca_chamado(tmp_path):
    """O duble levanta ForbiddenMemberTouched se replace for tocado; chegar em
    saved_as prova que nao foi."""
    resultado, _c, _p, _s = _run(tmp_path)
    assert resultado["status"] == probe.STATUS_SAVED_AS


def test_autorizacao_de_save_as_recusada(tmp_path):
    safety = FakeSafety(deny=("save_as",))
    resultado, container, project, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe.STATUS_CREATED_IN_MEMORY
    assert resultado["exit_code"] == 3
    assert resultado["requires_copy_discard"] is True
    assert container.create_gvl_calls == ["GVL_AI_TESTE"]
    assert project.save_as_calls == []
    assert safety.requested == ["create_gvl", "save_as"]


def test_save_as_chamado_exatamente_uma_vez(tmp_path):
    _resultado, _c, project, _s = _run(tmp_path)
    assert len(project.save_as_calls) == 1


def test_save_nunca_chamado(tmp_path):
    resultado, _c, project, _s = _run(tmp_path)
    assert resultado["status"] == probe.STATUS_SAVED_AS
    assert len(project.save_as_calls) == 1


def test_excecao_em_create_gvl(tmp_path):
    container = FakeContainer(raise_on_create=RuntimeError("falha sintetica"))
    resultado, container, project, safety = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_CREATE_GVL_FAILED
    assert resultado["exit_code"] == 3
    assert resultado["requires_copy_discard"] is True
    assert project.save_as_calls == []
    assert safety.requested == ["create_gvl"]


def test_excecao_em_save_as_nao_gera_retry(tmp_path):
    plano = _plan(tmp_path)
    container = FakeContainer()
    project = FakeProject(plano["input_project"]["path"], [container],
                          raise_on_save_as=RuntimeError("falha sintetica"))
    resultado, container, project, safety = _run(tmp_path, plano=plano,
                                                 container=container,
                                                 project=project)
    assert resultado["status"] == probe.STATUS_SAVE_AS_FAILED
    assert resultado["exit_code"] == 4
    assert resultado["requires_copy_discard"] is True
    assert len(project.save_as_calls) == 1
    assert safety.requested == ["create_gvl", "save_as"]


def test_save_as_silencioso_sem_arquivo_e_falha(tmp_path):
    plano = _plan(tmp_path)
    container = FakeContainer()
    project = FakeProject(plano["input_project"]["path"], [container],
                          create_output=False)
    resultado, _c, project, _s = _run(tmp_path, plano=plano, container=container,
                                      project=project)
    assert resultado["status"] == probe.STATUS_SAVE_AS_FAILED


def test_nenhuma_tentativa_de_rollback_apos_falha(tmp_path):
    """Os dubles levantam em remove/rename. Qualquer rollback interno faria o
    teste explodir com ForbiddenMemberTouched em vez de terminar no estado."""
    container = FakeContainer(created_name="GVL_ERRADA")
    resultado, _c, _p, _s = _run(tmp_path, container=container)
    assert resultado["status"] == probe.STATUS_VERIFICATION_FAILED


# --- 35-40. artefatos, journal e determinismo -------------------------------

def test_journal_ordenado_e_append_only(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    entradas = resultado["journal"]
    assert [e["sequence"] for e in entradas] == list(range(len(entradas)))
    eventos = [e["event"] for e in entradas]
    assert eventos[0] == "plan_accepted"
    assert "mutation_attempt" in eventos
    assert eventos.index("mutation_attempt") < eventos.index("mutation_done")


def test_journal_registra_tentativa_antes_do_efeito(tmp_path):
    """A tentativa e escrita ANTES da chamada: numa falha, ela e a unica prova
    de que houve mutacao."""
    container = FakeContainer(raise_on_create=RuntimeError("falha sintetica"))
    resultado, _c, _p, _s = _run(tmp_path, container=container)
    eventos = [e["event"] for e in resultado["journal"]]
    assert "mutation_attempt" in eventos
    assert "mutation_failed" in eventos
    assert "mutation_done" not in eventos


def test_journal_registra_call_site_fixo(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    sites = [e.get("call_site") for e in resultado["journal"] if e.get("call_site")]
    assert probe.CALL_SITE_CREATE_GVL in sites
    assert probe.CALL_SITE_SAVE_AS in sites


def test_completion_escrito_por_ultimo(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    escritos = probe.write_artifacts(resultado, file_io)
    assert escritos[-1] == "completion.json"
    caminho = os.path.join(resultado["artifacts_dir"], "completion.json")
    assert os.path.isfile(caminho)


def test_completion_declara_que_nenhum_outro_mutador_foi_pedido(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    completion = probe.build_completion(resultado)
    assert completion["no_other_mutator_requested"] is True
    assert completion["operations_executed"] == ["create_gvl", "save_as"]
    assert completion["status"] == probe.STATUS_SAVED_AS


def test_completion_marca_descarte_quando_falha_apos_criacao(tmp_path):
    safety = FakeSafety(deny=("save_as",))
    resultado, _c, _p, _s = _run(tmp_path, safety=safety)
    completion = probe.build_completion(resultado)
    assert completion["requires_copy_discard"] is True
    assert completion["status"] == probe.STATUS_CREATED_IN_MEMORY
    assert completion["exit_code"] != 0


def test_artefatos_deterministicos_fora_dos_campos_volateis(tmp_path):
    resultado_a, _c, _p, _s = _run(tmp_path)

    outro = tmp_path / "segunda"
    outro.mkdir()
    resultado_b, _c2, _p2, _s2 = _run(outro)

    def normalizar(resultado):
        completion = probe.build_completion(resultado)
        for campo in probe.VOLATILE_FIELDS:
            if campo in completion:
                completion[campo] = "<volatil>"
        completion["plan_sha256"] = "<depende do tmp>"
        completion["input_project_sha256_before"] = "<depende do tmp>"
        completion["output_project_path"] = "<depende do tmp>"
        return json.dumps(completion, sort_keys=True)

    assert normalizar(resultado_a) == normalizar(resultado_b)


def test_todos_os_artefatos_declarados_sao_gravados(tmp_path):
    resultado, _c, _p, _s = _run(tmp_path)
    probe.write_artifacts(resultado, file_io)
    presentes = os.listdir(resultado["artifacts_dir"])
    for nome in probe.ARTIFACT_NAMES:
        assert nome in presentes, nome


def test_precondicao_falha_sem_chamar_nenhum_mutador(tmp_path):
    """Consolidado: o duble de safety registra TODA solicitacao, e uma recusa
    de plano nao pode produzir nenhuma."""
    resultado = _recusa(tmp_path, gvl_name="GVL_OUTRA")
    assert resultado["operations_requested"] == []
    assert resultado["operations_executed"] == []


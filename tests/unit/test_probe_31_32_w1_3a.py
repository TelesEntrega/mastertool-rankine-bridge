"""Testes de `probes/31_verify_gvl_edit_w1_3a_readonly.py` e
`probes/32_edit_gvl_w1_3a.py`, com dubles ESTRITOS e verificacao estatica (AST).

Nenhuma API real do MasterTool e importada ou chamada. Os dubles LEVANTAM se o
probe tocar qualquer mutador fora do autorizado para cada um. Fixtures
sinteticas.

Os dubles expoem `type` (o membro real), NUNCA `type_guid` -- a licao de W1.1,
onde o fake reproduzia a suposicao errada do autor e os testes passavam sobre
um defeito.
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

PROBE31_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "31_verify_gvl_edit_w1_3a_readonly.py")
PROBE32_PATH = os.path.join(_MASTERTOOL_DIR, "probes", "32_edit_gvl_w1_3a.py")

CONTAINER_GUID = "639b491f-5557-464c-af91-1471bac9f549"
GVL_GUID = "ffbfa93a-b94d-45fc-a329-229860183b1d"

INITIAL_TEXT = "{attribute 'qualified_only'}\nVAR_GLOBAL\nEND_VAR"
FINAL_TEXT = ("{attribute 'qualified_only'}\nVAR_GLOBAL\n"
              "    g_xTesteCriacao : BOOL;\nEND_VAR")


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


probe31 = _load_module(PROBE31_PATH, "probe31_w1_3a")
probe32 = _load_module(PROBE32_PATH, "probe32_w1_3a")


class ForbiddenMemberTouched(AssertionError):
    pass


# =============================================================================
# Constantes do modulo conferem com os dados medidos (docs/31)
# =============================================================================

def test_constantes_do_probe_31_conferem_com_os_dados_medidos():
    assert probe31.EXPECTED_GVL_NAME == "GVL_AI_TESTE"
    assert probe31.EXPECTED_GVL_TYPE_GUID == GVL_GUID
    assert probe31.EXPECTED_CONTAINER_TYPE_GUID == CONTAINER_GUID
    assert probe31.EXPECTED_INITIAL_TEXT == INITIAL_TEXT
    assert probe31.EXPECTED_FINAL_TEXT == FINAL_TEXT
    assert probe31.sha256_of_text(probe31.EXPECTED_INITIAL_TEXT) == \
        probe31.EXPECTED_INITIAL_TEXT_SHA256
    assert probe31.sha256_of_text(probe31.EXPECTED_FINAL_TEXT) == \
        probe31.EXPECTED_FINAL_TEXT_SHA256


def test_constantes_do_probe_32_conferem_com_o_probe_31():
    assert probe32.EXPECTED_TARGET_NAME == probe31.EXPECTED_GVL_NAME
    assert probe32.EXPECTED_INITIAL_TEXT == probe31.EXPECTED_INITIAL_TEXT
    assert probe32.EXPECTED_FINAL_TEXT == probe31.EXPECTED_FINAL_TEXT


# =============================================================================
# normalize_text
# =============================================================================

@pytest.mark.parametrize("bruto,esperado", [
    ("a\nb", "a\nb"),
    ("a\r\nb", "a\nb"),
    ("a\rb", "a\nb"),
    ("a\nb\n", "a\nb"),
    ("a  \nb\t\n", "a\nb"),
    ("a\n\n", "a\n"),
    (None, None),
    ("", ""),
])
def test_normalize_text(bruto, esperado):
    assert probe31.normalize_text(bruto) == esperado
    assert probe32.normalize_text(bruto) == esperado


def test_normalize_text_uma_quebra_final_ignorada_mas_nao_duas():
    """Doc/31: 'UMA quebra de linha final ignorada'. Duas quebras finais nao
    colapsam para a mesma forma que zero quebras -- so uma e absorvida."""
    sem_quebra = probe31.normalize_text("x\ny")
    uma_quebra = probe31.normalize_text("x\ny\n")
    duas_quebras = probe31.normalize_text("x\ny\n\n")
    assert sem_quebra == uma_quebra == "x\ny"
    assert duas_quebras != sem_quebra


# =============================================================================
# Probe 31 -- dubles
# =============================================================================

class FakeChildren(object):
    def __init__(self, items):
        self._items = list(items)

    @property
    def Count(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]


class FakeDoc31(object):
    def __init__(self, text):
        self.text = text

    def replace(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 31 chamou replace()")


class FakeNode31(object):
    def __init__(self, name, children=None, node_type=GVL_GUID,
                 declaration=INITIAL_TEXT, transient=False, is_folder=False):
        self._name = name
        self._children = list(children or [])
        self.type = node_type
        self.is_transient_object = transient
        self.is_folder = is_folder
        self.has_textual_declaration = declaration is not None
        self._declaration = declaration

    def get_name(self, _recursive):
        return self._name

    def get_children(self, _recursive):
        return FakeChildren(self._children)

    @property
    def textual_declaration(self):
        return None if self._declaration is None else FakeDoc31(self._declaration)

    def create_gvl(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 31 chamou create_gvl()")

    def create_program(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 31 chamou create_program()")

    def save(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 31 chamou save()")

    def save_as(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 31 chamou save_as()")

    def remove(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 31 chamou remove()")

    def rename(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 31 chamou rename()")


class FakeProject31(FakeNode31):
    def __init__(self, path, children):
        FakeNode31.__init__(self, "projeto", children=children)
        self.path = path


class FakeProjectAccess31(object):
    def __init__(self, project):
        self._project = project

    def get_primary_project(self, _globals):
        return self._project, None

    def get_project_path(self, project):
        return project.path


class FakeProbeCli31(object):
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
        """O probe desce DUAS vezes: `indexes` para o container e `indexes[:-1]`
        para o pai, quando precisa contar irmaos ambiguos.

        A versao anterior deste duble devolvia o PAI nas duas chamadas -- com
        node_path `root/1/0`, `len(indexes)` e 2 na primeira e 1 na segunda, e a
        condicao `len(indexes) > 1` casava com a do container. O container
        resolvia para "Plc Logic", o nome nao conferia, e o teste de ambiguidade
        media `container_not_found`.

        Agora a distincao e pelo caminho exato, nao pelo comprimento."""
        caminho = tuple(indexes)
        if self._parent is not None and caminho == (1,):
            return self._parent
        return self._container


def _plan31(tmp_path, **overrides):
    plano = {
        "mastertool": {"version": "4.1.0.11", "script_engine": "4.2.0.0"},
        "container": {"node_path": "root/1/0"},
        "output_project": {"path": os.path.join(str(tmp_path), "saida.project")},
    }
    plano.update(overrides)
    caminho = os.path.join(str(tmp_path), "plano.json")
    handle = open(caminho, "w")
    try:
        handle.write(json.dumps(plano))
    finally:
        handle.close()
    return caminho


def _run31(tmp_path, container, mode="preflight", plan_path=None, parent=None,
          probe_cli_double=None, extra_args=None):
    if plan_path is None:
        plan_path = _plan31(tmp_path)
    project = FakeProject31(os.path.join(str(tmp_path), "aberto.project"),
                            [container] if container is not None else [])
    duplo = probe_cli_double or FakeProbeCli31(container=container, parent=parent)
    argv = ["probe", "--mode=" + mode, "--plan=" + plan_path,
            "--output=" + os.path.join(str(tmp_path), "art")]
    argv.extend(extra_args or [])
    return probe31.run_verification({"projects": object()}, argv,
                                    FakeProjectAccess31(project), file_io, duplo)


# --- caminho feliz, preflight -------------------------------------------------

def test_preflight_passa(tmp_path):
    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE")])
    resultado = _run31(tmp_path, container)
    assert resultado["status"] == probe31.PREFLIGHT_PASSED
    assert resultado["exit_code"] == 0
    assert resultado["initial_text_matches"] is True


def test_replace_nunca_e_chamado(tmp_path):
    """O duble levanta se replace() for CHAMADO -- prova que probe 31 e
    genuinamente read-only."""
    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE")])
    resultado = _run31(tmp_path, container)
    assert resultado["status"] == probe31.PREFLIGHT_PASSED


def test_apenas_dois_estados_de_sucesso():
    assert probe31.SUCCESS_STATUSES == (probe31.PREFLIGHT_PASSED,
                                        probe31.POSTSAVE_VERIFIED)
    for status in probe31.PREFLIGHT_STATUSES + probe31.POSTSAVE_STATUSES:
        esperado = status in probe31.SUCCESS_STATUSES
        assert (probe31.EXIT_BY_STATUS[status] == 0) is esperado, status


# --- container ----------------------------------------------------------------

def test_container_nao_encontrado(tmp_path):
    resultado = _run31(tmp_path, None)
    assert resultado["status"] == probe31.CONTAINER_NOT_FOUND


def test_container_nome_divergente(tmp_path):
    container = FakeNode31("Outro", node_type=CONTAINER_GUID)
    resultado = _run31(tmp_path, container)
    assert resultado["status"] == probe31.CONTAINER_NOT_FOUND


def test_container_type_divergente(tmp_path):
    container = FakeNode31("Application", node_type="guid-errado")
    resultado = _run31(tmp_path, container)
    assert resultado["status"] == probe31.CONTAINER_NOT_FOUND


def test_container_ambiguo(tmp_path):
    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE")])
    gemeo = FakeNode31("Application", node_type=CONTAINER_GUID)
    parent = FakeNode31("Plc Logic", children=[container, gemeo])
    resultado = _run31(tmp_path, container, parent=parent)
    assert resultado["status"] == probe31.CONTAINER_AMBIGUOUS


def test_instalacao_divergente(tmp_path):
    container = FakeNode31("Application", node_type=CONTAINER_GUID)
    duplo = FakeProbeCli31(container=container, version="4.0.0.1")
    resultado = _run31(tmp_path, container, probe_cli_double=duplo)
    assert resultado["status"] == probe31.RUNTIME_MISMATCH


# --- alvo -----------------------------------------------------------------

def test_alvo_ausente(tmp_path):
    container = FakeNode31("Application", node_type=CONTAINER_GUID, children=[])
    resultado = _run31(tmp_path, container)
    assert resultado["status"] == probe31.TARGET_NOT_FOUND


def test_alvo_duplicado(tmp_path):
    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE"),
                                    FakeNode31("GVL_AI_TESTE")])
    resultado = _run31(tmp_path, container)
    assert resultado["status"] == probe31.TARGET_DUPLICATED


def test_alvo_type_guid_divergente(tmp_path):
    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE", node_type="guid-outro")])
    resultado = _run31(tmp_path, container)
    assert resultado["status"] == probe31.TARGET_TYPE_MISMATCH


def test_alvo_e_pasta(tmp_path):
    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE", is_folder=True)])
    resultado = _run31(tmp_path, container)
    assert resultado["status"] == probe31.TARGET_TYPE_MISMATCH


def test_texto_ilegivel(tmp_path):
    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE", declaration=None)])
    resultado = _run31(tmp_path, container)
    assert resultado["status"] == probe31.TEXT_READ_GAP
    assert resultado["exit_code"] != 0


def test_texto_inicial_divergente(tmp_path):
    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE",
                                               declaration="VAR_GLOBAL\nEND_VAR")])
    resultado = _run31(tmp_path, container)
    assert resultado["status"] == probe31.INITIAL_TEXT_MISMATCH


def test_texto_inicial_com_crlf_ainda_passa(tmp_path):
    """CRLF equivale a LF -- a normalizacao nao pode reprovar isso."""
    texto_crlf = INITIAL_TEXT.replace("\n", "\r\n")
    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE", declaration=texto_crlf)])
    resultado = _run31(tmp_path, container)
    assert resultado["status"] == probe31.PREFLIGHT_PASSED


# --- modo -----------------------------------------------------------------

def test_modo_ausente_e_RECUSADO(tmp_path):
    """O probe exige `--mode` explicito, como o probe 28 de W1.1 -- e nao
    assume preflight por omissao.

    A garantia e sobre a EVIDENCIA: o artefato tem de dizer qual verificacao
    rodou. Um default silencioso faria um postsave esquecido ser gravado como
    preflight, e o arquivo pareceria legitimo."""
    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE")])
    plan_path = _plan31(tmp_path)
    argv = ["probe", "--plan=" + plan_path,
            "--output=" + os.path.join(str(tmp_path), "art")]
    project = FakeProject31(os.path.join(str(tmp_path), "aberto.project"), [container])
    resultado = probe31.run_verification(
        {"projects": object()}, argv, FakeProjectAccess31(project), file_io,
        FakeProbeCli31(container=container))
    assert resultado["mode"] is None
    assert resultado["status"] == probe31.STATUS_FATAL
    assert any("--mode" in p for p in resultado["problems"])


def test_modo_invalido_recusado(tmp_path):
    container = FakeNode31("Application", node_type=CONTAINER_GUID)
    resultado = _run31(tmp_path, container, mode="PREFLIGHT")
    assert resultado["status"] == probe31.STATUS_FATAL


def test_postsave_sem_baseline_e_fatal(tmp_path):
    saida = os.path.join(str(tmp_path), "saida.project")
    handle = open(saida, "w")
    try:
        handle.write("x")
    finally:
        handle.close()
    container = FakeNode31("Application", node_type=CONTAINER_GUID)
    plan_path = _plan31(tmp_path, output_project={"path": saida})
    project = FakeProject31(saida, [container])
    argv = ["probe", "--mode=postsave", "--plan=" + plan_path,
            "--output=" + os.path.join(str(tmp_path), "art")]
    resultado = probe31.run_verification(
        {"projects": object()}, argv, FakeProjectAccess31(project), file_io,
        FakeProbeCli31(container=container))
    assert resultado["status"] == probe31.STATUS_FATAL
    assert "baseline" in str(resultado["problems"])


# --- postsave ------------------------------------------------------------

def _postsave31(tmp_path, filhos, baseline_nomes=("UserGVLs", "GVL_AI_TESTE"),
                sha_esperado=None,
                plano_extra=None):
    saida = os.path.join(str(tmp_path), "saida.project")
    handle = open(saida, "w")
    try:
        handle.write("projeto salvo")
    finally:
        handle.close()
    plano = {"output_project": {"path": saida}}
    if plano_extra:
        plano.update(plano_extra)
    plan_path = _plan31(tmp_path, **plano)

    baseline_path = os.path.join(str(tmp_path), "baseline.json")
    handle = open(baseline_path, "w")
    try:
        handle.write(json.dumps({"persistent": [{"name": n} for n in baseline_nomes],
                                 "transient": []}))
    finally:
        handle.close()

    container = FakeNode31("Application", node_type=CONTAINER_GUID, children=filhos)
    project = FakeProject31(saida, [container])
    digest, _e = probe31.sha256_of_file(saida)
    argv = ["probe", "--mode=postsave", "--plan=" + plan_path,
            "--output=" + os.path.join(str(tmp_path), "art"),
            "--baseline=" + baseline_path,
            "--output-sha256=" + (sha_esperado if sha_esperado else digest)]
    duplo = FakeProbeCli31(container=container)
    return probe31.run_verification({"projects": object()}, argv,
                                    FakeProjectAccess31(project), file_io, duplo)


def test_postsave_verificado(tmp_path):
    filhos = [FakeNode31("UserGVLs", node_type="guid-pasta", is_folder=True),
              FakeNode31("GVL_AI_TESTE", declaration=FINAL_TEXT)]
    resultado = _postsave31(tmp_path, filhos)
    assert resultado["status"] == probe31.POSTSAVE_VERIFIED
    assert resultado["exit_code"] == 0
    assert resultado["structural_diff"]["persistent_added"] == []
    assert resultado["structural_diff"]["persistent_missing"] == []


def test_postsave_alvo_ausente(tmp_path):
    resultado = _postsave31(tmp_path, [FakeNode31("UserGVLs", is_folder=True)])
    assert resultado["status"] == probe31.TARGET_NOT_FOUND


def test_postsave_alvo_duplicado(tmp_path):
    filhos = [FakeNode31("UserGVLs", is_folder=True),
              FakeNode31("GVL_AI_TESTE", declaration=FINAL_TEXT),
              FakeNode31("GVL_AI_TESTE", declaration=FINAL_TEXT)]
    resultado = _postsave31(tmp_path, filhos)
    assert resultado["status"] == probe31.TARGET_DUPLICATED


def test_postsave_objeto_extra_reprova(tmp_path):
    """W1.3A EDITA -- ZERO objetos podem ser adicionados, diferente de W1.1/
    W1.2 que criavam exatamente um."""
    filhos = [FakeNode31("UserGVLs", is_folder=True),
              FakeNode31("GVL_AI_TESTE", declaration=FINAL_TEXT),
              FakeNode31("GVL_INESPERADA")]
    resultado = _postsave31(tmp_path, filhos)
    assert resultado["status"] == probe31.UNEXPECTED_PERSISTENT_DIFF


def test_postsave_objeto_sumiu_reprova(tmp_path):
    filhos = [FakeNode31("GVL_AI_TESTE", declaration=FINAL_TEXT)]
    resultado = _postsave31(tmp_path, filhos, baseline_nomes=("UserGVLs", "GVL_AI_TESTE"))
    assert resultado["status"] == probe31.UNEXPECTED_PERSISTENT_DIFF


def test_postsave_hash_divergente(tmp_path):
    filhos = [FakeNode31("UserGVLs", is_folder=True),
              FakeNode31("GVL_AI_TESTE", declaration=FINAL_TEXT)]
    resultado = _postsave31(tmp_path, filhos, sha_esperado="0" * 64)
    assert resultado["status"] == probe31.OUTPUT_HASH_MISMATCH


def test_postsave_texto_final_divergente(tmp_path):
    filhos = [FakeNode31("UserGVLs", is_folder=True),
              FakeNode31("GVL_AI_TESTE", declaration=INITIAL_TEXT)]
    resultado = _postsave31(tmp_path, filhos)
    assert resultado["status"] == probe31.FINAL_TEXT_MISMATCH


def test_postsave_texto_ilegivel_nao_e_sucesso(tmp_path):
    filhos = [FakeNode31("UserGVLs", is_folder=True),
              FakeNode31("GVL_AI_TESTE", declaration=None)]
    resultado = _postsave31(tmp_path, filhos)
    assert resultado["status"] == probe31.TEXT_READ_GAP
    assert probe31.build_completion(resultado)["is_success"] is False


def test_is_success_acompanha_o_status_em_cada_modo(tmp_path):
    filhos = [FakeNode31("UserGVLs", is_folder=True),
              FakeNode31("GVL_AI_TESTE", declaration=FINAL_TEXT)]
    postsave = _postsave31(tmp_path, filhos)
    assert postsave["status"] == probe31.POSTSAVE_VERIFIED
    assert probe31.build_completion(postsave)["is_success"] is True

    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE")])
    preflight = _run31(tmp_path, container)
    assert preflight["status"] == probe31.PREFLIGHT_PASSED
    assert probe31.build_completion(preflight)["is_success"] is True


def test_artefatos_gravados_preflight(tmp_path):
    container = FakeNode31("Application", node_type=CONTAINER_GUID,
                           children=[FakeNode31("GVL_AI_TESTE")])
    resultado = _run31(tmp_path, container)
    escritos = probe31.write_artifacts(resultado, file_io)
    assert escritos[-1] == "w1-3a-preflight-completion.json"


def test_artefatos_gravados_postsave(tmp_path):
    filhos = [FakeNode31("UserGVLs", is_folder=True),
              FakeNode31("GVL_AI_TESTE", declaration=FINAL_TEXT)]
    resultado = _postsave31(tmp_path, filhos)
    escritos = probe31.write_artifacts(resultado, file_io)
    assert escritos[-1] == "w1-3a-postsave-completion.json"


# =============================================================================
# Probe 32 -- dubles
# =============================================================================

class FakeDoc32(object):
    def __init__(self, text):
        self.text = text
        self.replace_calls = []

    def replace(self, new_text):
        self.replace_calls.append(new_text)
        self.text = new_text


class FakeNode32(object):
    def __init__(self, name, children=None, node_type=GVL_GUID,
                 declaration=INITIAL_TEXT, transient=False, is_folder=False):
        self._name = name
        self._children = list(children or [])
        self.type = node_type
        self.is_transient_object = transient
        self.is_folder = is_folder
        self.has_textual_declaration = declaration is not None
        self._doc = None if declaration is None else FakeDoc32(declaration)

    def get_name(self, _recursive):
        return self._name

    def get_children(self, _recursive):
        return FakeChildren(self._children)

    @property
    def textual_declaration(self):
        return self._doc

    def create_gvl(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 32 chamou create_gvl()")

    def create_program(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 32 chamou create_program()")

    def create_pou(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 32 chamou create_pou()")

    def remove(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 32 tentou rollback via remove()")

    def rename(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 32 chamou rename()")


class FakeContainer32(FakeNode32):
    def __init__(self, children=None, node_type=CONTAINER_GUID):
        FakeNode32.__init__(self, "Application", children=children,
                            node_type=node_type)


class FakeProject32(FakeNode32):
    def __init__(self, path, children, raise_on_save_as=None, create_output=True):
        FakeNode32.__init__(self, "projeto", children=children)
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
        raise ForbiddenMemberTouched("probe 32 chamou save()")

    def build(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 32 chamou build()")


class FakeSafety32(object):
    class SafetyError(Exception):
        pass

    def __init__(self, phase="W1_3A_EDIT_GVL", allowed=("replace", "save_as"),
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
        raise ForbiddenMemberTouched("probe 32 usou a porta legada")


class FakeProjectAccess32(object):
    def __init__(self, project):
        self._project = project

    def get_primary_project(self, _globals):
        return self._project, None

    def get_project_path(self, project):
        return project.path


class FakeProbeCli32(object):
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


def _hash_of32(path):
    digest, _erro = probe32.sha256_of_file(path)
    return digest


def _make_input32(tmp_path):
    caminho = os.path.join(str(tmp_path), "entrada.project")
    handle = open(caminho, "w")
    try:
        handle.write("conteudo sintetico")
    finally:
        handle.close()
    return caminho


def _plan32(tmp_path, **overrides):
    entrada = overrides.pop("input_path", None) or _make_input32(tmp_path)
    saida = overrides.pop("output_path", None) or os.path.join(str(tmp_path), "saida.project")
    plano = {
        "schema_version": "1.0",
        "operation_id": "w1-3a-edit-gvl",
        "phase": "W1_3A_EDIT_GVL",
        "target_name": "GVL_AI_TESTE",
        "run_id": "run-sintetica",
        "input_project": {"path": entrada, "sha256": _hash_of32(entrada)},
        "output_project": {"path": saida},
        "artifacts_dir": os.path.join(str(tmp_path), "art"),
        "container": {"node_path": "root/1/0", "expected_name": "Application",
                      "expected_type_guid": CONTAINER_GUID,
                      "expected_target_type_guid": GVL_GUID},
        "mastertool": {"version": "4.1.0.11", "script_engine": "4.2.0.0"},
        "operations": [{"kind": "replace", "name": "GVL_AI_TESTE"},
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


def _run32(tmp_path, plano_path=None, container=None, project=None, safety=None,
          duplo=None):
    if plano_path is None:
        plano_path, plano = _plan32(tmp_path)
    else:
        plano = json.loads(io.open(plano_path, encoding="utf-8").read())
    container = container if container is not None else FakeContainer32(
        children=[FakeNode32("GVL_AI_TESTE")])
    project = project if project is not None else FakeProject32(
        plano["input_project"]["path"], [container])
    safety = safety if safety is not None else FakeSafety32()
    duplo = duplo or FakeProbeCli32(container=container)
    resultado = probe32.run_w1_3a({"projects": object()},
                                  ["probe", "--plan=" + plano_path], safety,
                                  FakeProjectAccess32(project), file_io, duplo)
    return resultado, container, project, safety


# --- caminho feliz --------------------------------------------------------

def test_saved_as(tmp_path):
    resultado, container, project, safety = _run32(tmp_path)
    assert resultado["status"] == probe32.STATUS_SAVED_AS
    assert resultado["exit_code"] == 0
    alvo = container._children[0]
    assert alvo._doc.replace_calls == [FINAL_TEXT]
    assert alvo._doc.text == FINAL_TEXT
    assert len(project.save_as_calls) == 1
    assert safety.requested == ["replace", "save_as"]
    assert resultado["requires_copy_discard"] is False


def test_somente_saved_as_tem_codigo_zero():
    for status in probe32.ALL_STATUSES:
        esperado = (status == probe32.STATUS_SAVED_AS)
        assert (probe32.EXIT_BY_STATUS[status] == 0) is esperado, status


# --- plano recusado --------------------------------------------------------

def _recusa32(tmp_path, **overrides):
    plano_path, _p = _plan32(tmp_path, **overrides)
    resultado, container, project, safety = _run32(tmp_path, plano_path=plano_path)
    assert resultado["status"] == probe32.STATUS_PRECONDITION_FAILED
    assert container._children[0]._doc.replace_calls == []
    assert project.save_as_calls == []
    assert safety.requested == []
    return resultado


def test_fase_errada_no_plano(tmp_path):
    _recusa32(tmp_path, phase="W1_1_CREATE_GVL")


def test_target_name_errado(tmp_path):
    _recusa32(tmp_path, target_name="OUTRA")


def test_operacao_extra(tmp_path):
    saida = os.path.join(str(tmp_path), "saida.project")
    _recusa32(tmp_path, operations=[{"kind": "replace", "name": "GVL_AI_TESTE"},
                                    {"kind": "save_as", "path": saida},
                                    {"kind": "build"}])


def test_operacao_fora_de_ordem(tmp_path):
    saida = os.path.join(str(tmp_path), "saida.project")
    _recusa32(tmp_path, operations=[{"kind": "save_as", "path": saida},
                                    {"kind": "replace", "name": "GVL_AI_TESTE"}])


def test_campo_desconhecido(tmp_path):
    _recusa32(tmp_path, campo_inesperado="x")


def test_output_ja_existe(tmp_path):
    saida = os.path.join(str(tmp_path), "existe.project")
    handle = open(saida, "w")
    try:
        handle.write("ocupado")
    finally:
        handle.close()
    _recusa32(tmp_path, output_path=saida)


# --- precondicoes de runtime ------------------------------------------------

def test_fase_controlada_divergente(tmp_path):
    resultado, container, _p, safety = _run32(tmp_path, safety=FakeSafety32(phase=None))
    assert resultado["status"] == probe32.STATUS_PRECONDITION_FAILED
    assert container._children[0]._doc.replace_calls == []
    assert safety.requested == []


def test_container_type_divergente(tmp_path):
    container = FakeContainer32(node_type="guid-errado",
                                children=[FakeNode32("GVL_AI_TESTE")])
    resultado, container, _p, safety = _run32(tmp_path, container=container)
    assert resultado["status"] == probe32.STATUS_PRECONDITION_FAILED


def test_alvo_ausente(tmp_path):
    container = FakeContainer32(children=[])
    resultado, container, _p, safety = _run32(tmp_path, container=container)
    assert resultado["status"] == probe32.STATUS_PRECONDITION_FAILED


def test_alvo_duplicado(tmp_path):
    container = FakeContainer32(children=[FakeNode32("GVL_AI_TESTE"),
                                          FakeNode32("GVL_AI_TESTE")])
    resultado, container, _p, safety = _run32(tmp_path, container=container)
    assert resultado["status"] == probe32.STATUS_PRECONDITION_FAILED


def test_alvo_type_guid_divergente(tmp_path):
    container = FakeContainer32(children=[FakeNode32("GVL_AI_TESTE", node_type="guid-outro")])
    resultado, container, _p, safety = _run32(tmp_path, container=container)
    assert resultado["status"] == probe32.STATUS_PRECONDITION_FAILED


def test_alvo_e_pasta(tmp_path):
    container = FakeContainer32(children=[FakeNode32("GVL_AI_TESTE", is_folder=True)])
    resultado, container, _p, safety = _run32(tmp_path, container=container)
    assert resultado["status"] == probe32.STATUS_PRECONDITION_FAILED


def test_texto_atual_ilegivel(tmp_path):
    container = FakeContainer32(children=[FakeNode32("GVL_AI_TESTE", declaration=None)])
    resultado, container, _p, safety = _run32(tmp_path, container=container)
    assert resultado["status"] == probe32.STATUS_PRECONDITION_FAILED


def test_texto_inicial_divergente_recusa(tmp_path):
    """Nao adaptar o conteudo automaticamente: se o texto inicial nao e o
    esperado, aborta ANTES do replace."""
    container = FakeContainer32(children=[
        FakeNode32("GVL_AI_TESTE", declaration="VAR_GLOBAL\nEND_VAR")])
    resultado, container, project, safety = _run32(tmp_path, container=container)
    assert resultado["status"] == probe32.STATUS_PRECONDITION_FAILED
    assert container._children[0]._doc.replace_calls == []
    assert safety.requested == []


def test_texto_inicial_com_crlf_ainda_passa(tmp_path):
    texto_crlf = INITIAL_TEXT.replace("\n", "\r\n")
    container = FakeContainer32(children=[
        FakeNode32("GVL_AI_TESTE", declaration=texto_crlf)])
    resultado, container, project, safety = _run32(tmp_path, container=container)
    assert resultado["status"] == probe32.STATUS_SAVED_AS


def test_autorizacao_de_replace_recusada(tmp_path):
    safety = FakeSafety32(deny=("replace",))
    resultado, container, project, safety = _run32(tmp_path, safety=safety)
    assert resultado["status"] == probe32.STATUS_PRECONDITION_FAILED
    assert container._children[0]._doc.replace_calls == []
    assert project.save_as_calls == []
    assert safety.requested == ["replace"]


# --- verificacao pos-replace -------------------------------------------------

def test_objeto_extra_apos_replace_reprova(tmp_path):
    class Ruidoso(FakeContainer32):
        pass

    alvo = FakeNode32("GVL_AI_TESTE")
    container = Ruidoso(children=[alvo])

    original_replace = alvo._doc.replace

    def replace_ruidoso(novo_texto):
        original_replace(novo_texto)
        container._children.append(FakeNode32("GVL_INESPERADA"))

    alvo._doc.replace = replace_ruidoso

    resultado, _c, project, _s = _run32(tmp_path, container=container)
    assert resultado["status"] == probe32.STATUS_VERIFICATION_FAILED
    assert resultado["requires_copy_discard"] is True
    assert project.save_as_calls == []


def test_texto_apos_replace_divergente_reprova(tmp_path):
    """Se o duble simulasse um replace que nao aplica o texto esperado, a
    verificacao pos-replace tem de reprovar -- nunca confiar cegamente."""
    alvo = FakeNode32("GVL_AI_TESTE")
    container = FakeContainer32(children=[alvo])

    def replace_incompleto(_novo_texto):
        alvo._doc.text = "texto errado"
        alvo._doc.replace_calls.append(_novo_texto)

    alvo._doc.replace = replace_incompleto

    resultado, _c, project, _s = _run32(tmp_path, container=container)
    assert resultado["status"] == probe32.STATUS_VERIFICATION_FAILED
    assert project.save_as_calls == []


def test_save_as_recusado_deixa_replaced_in_memory(tmp_path):
    safety = FakeSafety32(deny=("save_as",))
    resultado, container, project, safety = _run32(tmp_path, safety=safety)
    assert resultado["status"] == probe32.STATUS_REPLACED_IN_MEMORY
    assert resultado["requires_copy_discard"] is True
    assert container._children[0]._doc.replace_calls == [FINAL_TEXT]
    assert project.save_as_calls == []


def test_excecao_em_save_as_sem_retry(tmp_path):
    plano_path, plano = _plan32(tmp_path)
    container = FakeContainer32(children=[FakeNode32("GVL_AI_TESTE")])
    project = FakeProject32(plano["input_project"]["path"], [container],
                            raise_on_save_as=RuntimeError("falha"))
    resultado, _c, project, _s = _run32(tmp_path, plano_path=plano_path,
                                       container=container, project=project)
    assert resultado["status"] == probe32.STATUS_SAVE_AS_FAILED
    assert len(project.save_as_calls) == 1


def test_nenhum_rollback_apos_falha(tmp_path):
    """Os dubles levantam em remove/rename."""
    alvo = FakeNode32("GVL_AI_TESTE")
    container = FakeContainer32(children=[alvo])

    def replace_ruidoso(novo_texto):
        alvo._doc.text = novo_texto
        alvo._doc.replace_calls.append(novo_texto)
        container._children.append(FakeNode32("GVL_INESPERADA"))

    alvo._doc.replace = replace_ruidoso
    resultado, _c, _p, _s = _run32(tmp_path, container=container)
    assert resultado["status"] == probe32.STATUS_VERIFICATION_FAILED


# --- journal e artefatos -----------------------------------------------------

def test_journal_ordenado_com_call_sites_e_documento(tmp_path):
    resultado, _c, _p, _s = _run32(tmp_path)
    entradas = resultado["journal"]
    assert [e["sequence"] for e in entradas] == list(range(len(entradas)))
    sites = [e.get("call_site") for e in entradas if e.get("call_site")]
    assert probe32.CALL_SITE_REPLACE in sites
    assert probe32.CALL_SITE_SAVE_AS in sites
    documentos = [e.get("document_operation") for e in entradas
                 if e.get("document_operation")]
    assert "replace_gvl_declaration" in documentos


def test_completion_por_ultimo_e_declara_nada_alem(tmp_path):
    resultado, _c, _p, _s = _run32(tmp_path)
    escritos = probe32.write_artifacts(resultado, file_io)
    assert escritos[-1] == "completion.json"
    completion = probe32.build_completion(resultado)
    assert completion["no_other_mutator_requested"] is True
    assert completion["operations_executed"] == ["replace", "save_as"]


def test_todos_os_artefatos(tmp_path):
    resultado, _c, _p, _s = _run32(tmp_path)
    probe32.write_artifacts(resultado, file_io)
    presentes = os.listdir(resultado["artifacts_dir"])
    for nome in probe32.ARTIFACT_NAMES:
        assert nome in presentes, nome


# =============================================================================
# Verificacao estatica (AST) -- probe 31 (SOMENTE LEITURA)
# =============================================================================

@pytest.fixture(scope="module")
def tree31():
    return ast.parse(io.open(PROBE31_PATH, encoding="utf-8").read())


def _method_calls(tree, nome):
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == nome]


@pytest.mark.parametrize("metodo", [
    "create_gvl", "create_program", "create_pou", "create_folder", "create_dut",
    "create_function", "create_function_block", "save", "save_as", "replace",
    "replace_line", "rename", "move", "build",
    "rebuild", "clean", "import_xml", "Invoke",
])
def test_probe_31_nao_contem_mutador(tree31, metodo):
    assert _method_calls(tree31, metodo) == [], (
        "probe 31 e read-only e nao pode chamar .%s()" % metodo)


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_probe_31_sem_acesso_dinamico(tree31, nome):
    encontrados = [n for n in ast.walk(tree31)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == nome]
    assert encontrados == []


def test_probe_31_sem_lambda_nem_fstring(tree31):
    assert [n for n in ast.walk(tree31) if isinstance(n, ast.Lambda)] == []
    assert [n for n in ast.walk(tree31)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []


def test_probe_31_identificadores_ascii():
    fonte = io.open(PROBE31_PATH, encoding="utf-8").read()
    arvore = ast.parse(fonte)
    for node in ast.walk(arvore):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


# =============================================================================
# Verificacao estatica (AST) -- probe 32 (mutacao)
# =============================================================================

@pytest.fixture(scope="module")
def tree32():
    return ast.parse(io.open(PROBE32_PATH, encoding="utf-8").read())


def _calls(tree):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)]


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


def test_guarda_de_replace_adjacente(tree32):
    guarda, mutacao = _adjacentes(tree32, "replace", "replace")
    assert guarda is not None
    assert mutacao.lineno == guarda.lineno + 1


def test_guarda_de_save_as_adjacente(tree32):
    guarda, mutacao = _adjacentes(tree32, "save_as", "save_as")
    assert guarda is not None
    assert mutacao.lineno == guarda.lineno + 1


def test_replace_chamado_exatamente_uma_vez_com_argumento_literal(tree32):
    """O argumento e o Name que referencia a CONSTANTE do modulo
    (EXPECTED_FINAL_TEXT), nunca texto calculado ou vindo do plano."""
    chamadas = _method_calls(tree32, "replace")
    assert len(chamadas) == 1
    assert len(chamadas[0].args) == 1
    arg = chamadas[0].args[0]
    assert isinstance(arg, ast.Name)
    assert arg.id == "EXPECTED_FINAL_TEXT"


def test_save_as_chamado_exatamente_uma_vez(tree32):
    chamadas = _method_calls(tree32, "save_as")
    assert len(chamadas) == 1


def test_expected_final_text_e_literal_no_modulo(tree32):
    """A CONSTANTE referenciada pelo replace e, ela propria, um literal --
    nao um valor derivado em runtime nem lido do plano."""
    atribuicoes_de_string = []
    for node in ast.walk(tree32):
        if isinstance(node, ast.Assign):
            for alvo in node.targets:
                if isinstance(alvo, ast.Name) and alvo.id == "EXPECTED_FINAL_TEXT":
                    atribuicoes_de_string.append(node.value)
    assert len(atribuicoes_de_string) == 1
    valor = atribuicoes_de_string[0]
    # Concatenacao de literais (parenteses/linhas) tambem e literal: o AST
    # representa `("a" "b")` como um unico ast.Str/Constant.
    assert isinstance(valor, ast.Str)


@pytest.mark.parametrize("metodo", [
    "create_gvl", "create_program", "create_pou", "create_folder", "create_dut",
    "create_function", "create_function_block", "save",
    "replace_line", "remove", "rename", "move", "build", "rebuild", "clean",
    "import_xml", "Invoke",
])
def test_probe_32_nao_contem_mutador_proibido(tree32, metodo):
    assert _method_calls(tree32, metodo) == [], (
        "probe 32 nao pode chamar .%s()" % metodo)


# --- o documento textual so recebe `replace` --------------------------------
#
# `insert`, `append` e `remove` existem em IScriptTextDocument E em `list`.
# Proibi-los por NOME quebra em `identity["errors"].append(...)`, que e lista
# Python -- foi onde a Frente A parou. Tira-los da lista sem mais nada, porem,
# perderia a garantia: docs/31 proibe explicitamente insert/append/replace_line
# em W1.3.
#
# A garantia correta e por RECEPTOR: o documento textual so pode receber
# `replace`. `replace` do documento inteiro e a unica forma cujo estado final
# nao depende de offset, e portanto a unica verificavel por hash.

DOCUMENT_VARIABLE_NAMES = ("text_document", "document", "text_doc")

METODOS_POSICIONAIS_PROIBIDOS = ("insert", "append", "remove", "replace_line",
                                 "delete", "clear")


def _chamadas_no_documento(arvore):
    encontradas = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        if not isinstance(no.func, ast.Attribute):
            continue
        receptor = no.func.value
        if isinstance(receptor, ast.Name) and receptor.id in DOCUMENT_VARIABLE_NAMES:
            encontradas.append((receptor.id, no.func.attr))
    return encontradas


def test_documento_textual_so_recebe_replace(tree32):
    chamadas = _chamadas_no_documento(tree32)
    assert chamadas, "nenhuma chamada no documento textual foi encontrada"
    for receptor, metodo in chamadas:
        assert metodo == "replace", (
            "%s.%s() nao e permitido: o documento so pode receber replace()"
            % (receptor, metodo))


def test_documento_textual_nao_recebe_metodo_posicional(tree32):
    for receptor, metodo in _chamadas_no_documento(tree32):
        assert metodo not in METODOS_POSICIONAIS_PROIBIDOS, (
            "%s.%s() edita por posicao e docs/31 proibe" % (receptor, metodo))


def test_probe_31_readonly_nunca_toca_documento(tree31):
    """O probe read-only pode LER o documento, nunca escrever nele."""
    for receptor, metodo in _chamadas_no_documento(tree31):
        assert metodo not in METODOS_POSICIONAIS_PROIBIDOS + ("replace",), (
            "probe read-only chamou %s.%s()" % (receptor, metodo))


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_probe_32_sem_acesso_dinamico(tree32, nome):
    assert [n for n in _calls(tree32)
            if isinstance(n.func, ast.Name) and n.func.id == nome] == []


def test_probe_32_sem_lambda_nem_fstring(tree32):
    assert [n for n in ast.walk(tree32) if isinstance(n, ast.Lambda)] == []
    assert [n for n in ast.walk(tree32)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []


def test_probe_32_identificadores_ascii():
    fonte = io.open(PROBE32_PATH, encoding="utf-8").read()
    arvore = ast.parse(fonte)
    for node in ast.walk(arvore):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor

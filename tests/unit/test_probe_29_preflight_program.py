"""Testes de `probes/29_preflight_program_w1_2_readonly.py`.

Dubles ESTRITOS e verificacao estatica (AST). Nenhuma API real do MasterTool e
importada ou chamada; nenhum projeto e aberto. Fixtures sinteticas.

Os dubles expoem `type` (o membro real), nunca `type_guid` -- a licao de W1.1,
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

PROBE_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                          "29_preflight_program_w1_2_readonly.py")

CONTAINER_GUID = "639b491f-5557-464c-af91-1471bac9f549"
POU_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
ST_GUID = "guid-st-sintetico"


def _load_probe():
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("probe29_w1_2", PROBE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except ImportError:                                        # IronPython 2.7
        import imp
        return imp.load_source("probe29_w1_2", PROBE_PATH)


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

    def replace(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 29 chamou replace()")


class FakeNode(object):
    def __init__(self, name, children=None, node_type=POU_GUID,
                 declaration="PROGRAM X\nVAR\nEND_VAR", implementation="",
                 transient=False, is_folder=False, expose_create_program=True,
                 expose_create_pou=True, create_program_callable=True):
        self._name = name
        self._children = list(children or [])
        self.type = node_type
        self.is_transient_object = transient
        self.is_folder = is_folder
        self.has_textual_declaration = declaration is not None
        self.has_textual_implementation = implementation is not None
        self._declaration = declaration
        self._implementation = implementation
        if expose_create_program:
            if create_program_callable:
                self.create_program = self._create_program_nunca_invocado
            else:
                self.create_program = "nao-callable"
        if expose_create_pou:
            self.create_pou = self._create_pou_nunca_invocado

    def _create_program_nunca_invocado(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 29 INVOCOU create_program()")

    def _create_pou_nunca_invocado(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 29 INVOCOU create_pou()")

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

    def create_gvl(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 29 chamou create_gvl()")

    def save(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 29 chamou save()")

    def save_as(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe 29 chamou save_as()")


class FakeProject(FakeNode):
    def __init__(self, path, children):
        FakeNode.__init__(self, "projeto", children=children,
                          expose_create_program=False, expose_create_pou=False)
        self.path = path


class FakeLanguages(object):
    def __init__(self, st=ST_GUID):
        self.st = st


class FakeProjectAccess(object):
    def __init__(self, project):
        self._project = project

    def get_primary_project(self, _globals):
        return self._project, None

    def get_project_path(self, project):
        return project.path


class FakeProbeCli(object):
    def __init__(self, container=None, parent=None, nodes=None,
                 version="4.1.0.11"):
        self._container = container
        self._parent = parent
        self._nodes = nodes or {}
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
        chave = "root/" + "/".join([str(i) for i in indexes])
        if chave in self._nodes:
            return self._nodes[chave]
        if len(indexes) == 2 and self._parent is not None:
            return self._parent
        return self._container


# --- helpers ----------------------------------------------------------------

def _plan(tmp_path, **overrides):
    container = {"node_path": "root/1/0", "expected_name": "Application",
                 "expected_type_guid": CONTAINER_GUID,
                 "existing_program_node_paths": ["root/1/0/0"]}
    container.update(overrides.pop("container", {}))
    plano = {
        "schema_version": "1.0",
        "phase": "W1_2_CREATE_PROGRAM",
        "program_name": "PRG_AI_TESTE",
        "container": container,
        "mastertool": {"version": "4.1.0.11", "script_engine": "4.2.0.0"},
    }
    plano.update(overrides)
    caminho = os.path.join(str(tmp_path), "plano.json")
    handle = open(caminho, "w")
    try:
        handle.write(json.dumps(plano))
    finally:
        handle.close()
    return caminho


def _run(tmp_path, container, plan_path=None, globais=None, nodes=None,
         parent=None, probe_cli_double=None, programa=None):
    if plan_path is None:
        plan_path = _plan(tmp_path)
    programa = programa if programa is not None else FakeNode("UserPrg")
    nodes = nodes if nodes is not None else {"root/1/0": container,
                                             "root/1/0/0": programa}
    project = FakeProject(os.path.join(str(tmp_path), "aberto.project"),
                          [container])
    duplo = probe_cli_double or FakeProbeCli(container=container, parent=parent,
                                             nodes=nodes)
    globais = globais if globais is not None else {
        "projects": object(), "implementation_languages": FakeLanguages()}
    argv = ["probe", "--plan=" + plan_path,
            "--output=" + os.path.join(str(tmp_path), "art")]
    return probe.run_preflight(globais, argv, FakeProjectAccess(project),
                               file_io, duplo)


# --- caminho feliz ----------------------------------------------------------

def test_preflight_passa(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID,
                         children=[FakeNode("UserPrg")])
    resultado = _run(tmp_path, container)
    assert resultado["status"] == probe.PREFLIGHT_PASSED
    assert resultado["exit_code"] == 0
    assert resultado["create_program_member"]["present"] is True
    assert resultado["create_program_member"]["callable"] is True
    assert resultado["st_language"]["guid"] == ST_GUID


def test_create_program_nunca_e_invocado(tmp_path):
    """O duble levanta se create_program for CHAMADO."""
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    resultado = _run(tmp_path, container)
    assert resultado["status"] == probe.PREFLIGHT_PASSED


def test_create_pou_registrado_mas_nao_invocado(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    resultado = _run(tmp_path, container)
    assert resultado["create_pou_member"]["present"] is True


def test_apenas_os_dois_estados_de_sucesso_tem_codigo_zero():
    """Um por modo: preflight_passed e postsave_verified. Todo o resto falha,
    inclusive text_read_gap -- 'nao consegui ler' nao vira 'esta certo'."""
    assert probe.SUCCESS_STATUSES == (probe.PREFLIGHT_PASSED,
                                      probe.POSTSAVE_VERIFIED)
    for status in probe.ALL_STATUSES:
        esperado = status in probe.SUCCESS_STATUSES
        assert (probe.EXIT_BY_STATUS[status] == 0) is esperado, status


# --- container --------------------------------------------------------------

def test_container_nao_encontrado(tmp_path):
    resultado = _run(tmp_path, None, nodes={})
    assert resultado["status"] == probe.CONTAINER_NOT_FOUND


def test_container_nome_divergente(tmp_path):
    container = FakeNode("Outro", node_type=CONTAINER_GUID)
    resultado = _run(tmp_path, container)
    assert resultado["status"] == probe.CONTAINER_NOT_FOUND


def test_container_type_divergente(tmp_path):
    container = FakeNode("Application", node_type="guid-errado")
    resultado = _run(tmp_path, container)
    assert resultado["status"] == probe.CONTAINER_NOT_FOUND


def test_container_ambiguo(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    gemeo = FakeNode("Application", node_type=CONTAINER_GUID)
    parent = FakeNode("Plc Logic", children=[container, gemeo])
    resultado = _run(tmp_path, container, parent=parent,
                     nodes={"root/1/0": container, "root/1": parent,
                            "root/1/0/0": FakeNode("UserPrg")})
    assert resultado["status"] == probe.CONTAINER_AMBIGUOUS


def test_nome_alvo_ja_existe(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID,
                         children=[FakeNode("PRG_AI_TESTE")])
    resultado = _run(tmp_path, container)
    assert resultado["status"] == probe.TARGET_NAME_EXISTS


def test_instalacao_divergente(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    duplo = FakeProbeCli(container=container, version="4.0.0.1",
                         nodes={"root/1/0": container})
    resultado = _run(tmp_path, container, probe_cli_double=duplo)
    assert resultado["status"] == probe.RUNTIME_MISMATCH


# --- membro create_program --------------------------------------------------

def test_membro_ausente(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID,
                         expose_create_program=False)
    resultado = _run(tmp_path, container)
    assert resultado["status"] == probe.CREATE_PROGRAM_MEMBER_MISSING


def test_membro_nao_callable(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID,
                         create_program_callable=False)
    resultado = _run(tmp_path, container)
    assert resultado["status"] == probe.CREATE_PROGRAM_MEMBER_NOT_CALLABLE


# --- GUID ST ----------------------------------------------------------------

def test_guid_st_ausente(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    resultado = _run(tmp_path, container, globais={"projects": object()})
    assert resultado["status"] == probe.ST_LANGUAGE_GUID_MISSING
    assert "projects" in resultado["injected_globals"]


def test_guid_st_ambiguo(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    resultado = _run(tmp_path, container, globais={
        "projects": object(),
        "implementation_languages": FakeLanguages("guid-a"),
        "ImplementationLanguages": FakeLanguages("guid-b")})
    assert resultado["status"] == probe.ST_LANGUAGE_GUID_AMBIGUOUS


def test_guid_st_registra_origem(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    resultado = _run(tmp_path, container)
    assert resultado["st_language"]["source"] == "implementation_languages"
    assert resultado["st_language"]["candidates_tried"] == list(
        probe.ST_LANGUAGE_GLOBAL_CANDIDATES)


def test_globais_de_risco_nunca_sao_candidatos():
    """`online` e `device_repository` podem iniciar comunicacao so de ter
    propriedade lida (common/compatibility.py: SIDE_EFFECT_RISK)."""
    for perigoso in probe.GLOBALS_NEVER_TOUCHED:
        assert perigoso not in probe.ST_LANGUAGE_GLOBAL_CANDIDATES


def test_globais_injetados_sao_so_nomes(tmp_path):
    """Enumerar nomes e inerte; tocar membro de global desconhecido nao e."""
    class GlobalPerigoso(object):
        def __getattr__(self, name):
            raise ForbiddenMemberTouched("probe 29 tocou global de risco")

    container = FakeNode("Application", node_type=CONTAINER_GUID)
    resultado = _run(tmp_path, container, globais={
        "projects": object(), "device_repository": GlobalPerigoso(),
        "implementation_languages": FakeLanguages()})
    assert resultado["status"] == probe.PREFLIGHT_PASSED
    assert "device_repository" in resultado["injected_globals"]


# --- identidade de PROGRAM --------------------------------------------------

def test_identidade_agrupada_por_type_guid(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID, children=[
        FakeNode("UserPrg", node_type=POU_GUID),
        FakeNode("StartPrg", node_type=POU_GUID),
        FakeNode("UserGVLs", node_type="guid-pasta", is_folder=True)])
    resultado = _run(tmp_path, container)
    grupos = {g["type_guid"]: g for g in resultado["program_identity_groups"]}
    assert grupos[POU_GUID]["count"] == 2
    assert sorted(grupos[POU_GUID]["names"]) == ["StartPrg", "UserPrg"]


def test_programa_preexistente_lido_e_classificado(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    programa = FakeNode("UserPrg", declaration="PROGRAM UserPrg\nVAR\nEND_VAR",
                        implementation="")
    resultado = _run(tmp_path, container, programa=programa)
    entrada = resultado["existing_programs"][0]
    assert entrada["emptiness"] == "somente_declaracao"
    assert entrada["texts"]["declaration_sha256"]


def test_sem_programa_preexistente_reprova(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    plan_path = _plan(tmp_path, container={"existing_program_node_paths": []})
    resultado = _run(tmp_path, container, plan_path=plan_path)
    assert resultado["status"] == probe.PROGRAM_IDENTITY_UNRESOLVED


@pytest.mark.parametrize("declaracao,implementacao,esperado", [
    ("", "", "vazio_total"),
    ("PROGRAM X\nVAR\nEND_VAR", "", "somente_declaracao"),
    ("", "x := 1;", "somente_implementacao"),
    ("PROGRAM X", "x := 1;", "declaracao_e_implementacao"),
    (None, None, "texto_ilegivel"),
])
def test_classificacao_de_vazio(declaracao, implementacao, esperado):
    textos = {"declaration": declaracao, "implementation": implementacao}
    assert probe.classify_program_emptiness(textos) == esperado


def test_nota_sobre_texto_canonico_esta_no_artefato(tmp_path):
    """O texto de um PROGRAM PREEXISTENTE nao pode ser chamado de canonico de
    um objeto novo -- e o artefato tem de dizer isso, nao so o autor."""
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    resultado = _run(tmp_path, container)
    completion = probe.build_completion(resultado)
    assert "RECEM-CRIADO" in completion["canonical_text_note"]
    assert "create_program" in completion["canonical_text_note"]


def test_artefatos_gravados(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    resultado = _run(tmp_path, container)
    escritos = probe.write_artifacts(resultado, file_io)
    assert escritos[-1] == "w1-2-preflight-completion.json"
    for nome in ("w1-2-preflight-tree.json", "w1-2-program-identity.json",
                 "w1-2-st-language.json", "w1-2-preflight-report.md"):
        assert nome in escritos


# --- modo postsave ----------------------------------------------------------

def _postsave(tmp_path, filhos, baseline_nomes=("UserPOUs",), sha_esperado=None,
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
    plan_path = _plan(tmp_path, **plano)

    baseline_path = os.path.join(str(tmp_path), "baseline.json")
    handle = open(baseline_path, "w")
    try:
        handle.write(json.dumps({
            "persistent": [{"name": n} for n in baseline_nomes],
            "transient": []}))
    finally:
        handle.close()

    container = FakeNode("Application", node_type=CONTAINER_GUID, children=filhos)
    project = FakeProject(saida, [container])
    digest, _e = probe.sha256_of_file(saida)
    argv = ["probe", "--mode=postsave", "--plan=" + plan_path,
            "--output=" + os.path.join(str(tmp_path), "art"),
            "--baseline=" + baseline_path,
            "--output-sha256=" + (sha_esperado if sha_esperado else digest)]
    duplo = FakeProbeCli(container=container,
                         nodes={"root/1/0": container})
    return probe.run_preflight({"projects": object(), "implementation_languages":
                                FakeLanguages()}, argv,
                               FakeProjectAccess(project), file_io, duplo)


def test_is_success_acompanha_o_status_em_cada_modo(tmp_path):
    """Regressao da run-006: o completion de um postsave APROVADO declarava
    is_success=False, contradizendo o campo `status` ao lado. Um artefato que
    se contradiz e pior do que um artefato omisso -- quem le acredita no campo
    errado."""
    filhos = [FakeNode("UserPOUs", node_type="guid-pasta", is_folder=True),
              FakeNode("PRG_AI_TESTE", node_type=POU_GUID)]
    postsave = _postsave(tmp_path, filhos)
    assert postsave["status"] == probe.POSTSAVE_VERIFIED
    assert probe.build_completion(postsave)["is_success"] is True

    container = FakeNode("Application", node_type=CONTAINER_GUID)
    preflight = _run(tmp_path, container)
    assert preflight["status"] == probe.PREFLIGHT_PASSED
    assert probe.build_completion(preflight)["is_success"] is True


def test_postsave_verificado(tmp_path):
    filhos = [FakeNode("UserPOUs", node_type="guid-pasta", is_folder=True),
              FakeNode("PRG_AI_TESTE", node_type=POU_GUID)]
    resultado = _postsave(tmp_path, filhos,
                          plano_extra={"container": {
                              "node_path": "root/1/0",
                              "expected_name": "Application",
                              "expected_type_guid": CONTAINER_GUID,
                              "expected_program_type_guid": POU_GUID,
                              "existing_program_node_paths": []}})
    assert resultado["status"] == probe.POSTSAVE_VERIFIED
    assert resultado["exit_code"] == 0
    assert resultado["structural_diff"]["persistent_added"] == ["PRG_AI_TESTE"]


def test_postsave_program_ausente(tmp_path):
    resultado = _postsave(tmp_path, [FakeNode("UserPOUs", is_folder=True)])
    assert resultado["status"] == probe.PROGRAM_MISSING


def test_postsave_program_duplicado(tmp_path):
    filhos = [FakeNode("UserPOUs", is_folder=True),
              FakeNode("PRG_AI_TESTE"), FakeNode("PRG_AI_TESTE")]
    resultado = _postsave(tmp_path, filhos)
    assert resultado["status"] == probe.PROGRAM_DUPLICATED


def test_postsave_objeto_extra(tmp_path):
    filhos = [FakeNode("UserPOUs", is_folder=True), FakeNode("PRG_AI_TESTE"),
              FakeNode("GVL_INESPERADA")]
    resultado = _postsave(tmp_path, filhos)
    assert resultado["status"] == probe.UNEXPECTED_PERSISTENT_DIFF


def test_postsave_hash_divergente(tmp_path):
    filhos = [FakeNode("UserPOUs", is_folder=True), FakeNode("PRG_AI_TESTE")]
    resultado = _postsave(tmp_path, filhos, sha_esperado="0" * 64)
    assert resultado["status"] == probe.OUTPUT_HASH_MISMATCH


def test_postsave_sem_baseline_e_fatal(tmp_path):
    saida = os.path.join(str(tmp_path), "saida.project")
    handle = open(saida, "w")
    try:
        handle.write("x")
    finally:
        handle.close()
    plan_path = _plan(tmp_path, output_project={"path": saida})
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    project = FakeProject(saida, [container])
    argv = ["probe", "--mode=postsave", "--plan=" + plan_path,
            "--output=" + os.path.join(str(tmp_path), "art")]
    resultado = probe.run_preflight({"projects": object()}, argv,
                                    FakeProjectAccess(project), file_io,
                                    FakeProbeCli(container=container))
    assert resultado["status"] == probe.STATUS_FATAL
    assert "baseline" in str(resultado["problems"])


def test_postsave_texto_ilegivel_nao_e_sucesso(tmp_path):
    filhos = [FakeNode("UserPOUs", is_folder=True),
              FakeNode("PRG_AI_TESTE", declaration=None)]
    resultado = _postsave(tmp_path, filhos)
    assert resultado["status"] == probe.TEXT_READ_GAP
    assert resultado["exit_code"] != 0
    assert probe.build_completion(resultado)["is_success"] is False


def test_modo_invalido_recusado(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    plan_path = _plan(tmp_path)
    argv = ["probe", "--mode=POSTSAVE", "--plan=" + plan_path,
            "--output=" + os.path.join(str(tmp_path), "art")]
    resultado = probe.run_preflight({"projects": object()}, argv,
                                    FakeProjectAccess(
                                        FakeProject("x", [container])),
                                    file_io, FakeProbeCli(container=container))
    assert resultado["status"] == probe.STATUS_FATAL


def test_modo_ausente_e_preflight(tmp_path):
    container = FakeNode("Application", node_type=CONTAINER_GUID)
    resultado = _run(tmp_path, container)
    assert resultado["mode"] == probe.MODE_PREFLIGHT


def test_artefatos_do_postsave(tmp_path):
    filhos = [FakeNode("UserPOUs", is_folder=True), FakeNode("PRG_AI_TESTE")]
    resultado = _postsave(tmp_path, filhos)
    escritos = probe.write_artifacts(resultado, file_io)
    assert escritos[-1] == "w1-2-postsave-completion.json"


# --- verificacao estatica ---------------------------------------------------

@pytest.fixture(scope="module")
def tree():
    return ast.parse(io.open(PROBE_PATH, encoding="utf-8").read())


def _method_calls(tree, nome):
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == nome]


@pytest.mark.parametrize("metodo", [
    "create_program", "create_pou", "create_gvl", "create_folder", "create_dut",
    "create_function", "create_function_block", "create_interface",
    "create_persistentvars", "create_task", "save", "save_as", "replace",
    "replace_line", "remove", "rename", "move", "build", "rebuild", "clean",
    "import_xml", "import_native", "Invoke",
])
def test_probe_29_nao_contem_mutador(tree, metodo):
    assert _method_calls(tree, metodo) == [], (
        "probe 29 e read-only e nao pode chamar .%s()" % metodo)


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_probe_29_sem_acesso_dinamico(tree, nome):
    encontrados = [n for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == nome]
    assert encontrados == []


def test_probe_29_referencia_create_program_sem_invocar(tree):
    atributos = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Attribute) and n.attr == "create_program"]
    assert len(atributos) >= 1
    assert _method_calls(tree, "create_program") == []


def test_probe_29_sem_fstring_nem_anotacao(tree):
    assert [n for n in ast.walk(tree)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            assert node.returns is None


def test_probe_29_identificadores_sao_ascii():
    """Python 2 recusa identificador nao-ASCII: seria SyntaxError no
    IronPython, e o py_compile do CPython 3 NAO acusaria."""
    fonte = io.open(PROBE_PATH, encoding="utf-8").read()
    arvore = ast.parse(fonte)
    for node in ast.walk(arvore):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor

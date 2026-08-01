"""Testes de `probes/40_build_w1_4.py` -- o `build` de W1.4, em abertura
separada, com dubles ESTRITOS e verificacao estatica (AST).

Nenhuma API real do MasterTool e importada ou chamada. Os dubles LEVANTAM se o
probe tocar `save`, `save_as`, `rebuild`, `clean` ou qualquer criacao: o build
NAO salva, e o arquivo em disco e conferido por hash antes e depois.

A regra central que estes testes ancoram: **AVISO NAO E ERRO**, e severidade
que o probe nao consegue classificar tambem NAO e aviso -- ela reprova.
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

PROBE40_PATH = os.path.join(_MASTERTOOL_DIR, "probes", "40_build_w1_4.py")

CONTAINER_GUID = "639b491f-5557-464c-af91-1471bac9f549"
ST_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"


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


probe40 = _load_module(PROBE40_PATH, "probe40_w1_4")


class ForbiddenMemberTouched(AssertionError):
    pass


# As CINCO linhas que o compilador emitiu, identicas, nas tres geracoes medidas
# (run-019, run-022, run-023). O caminho feliz sintetico usa estas, e nao uma
# lista vazia: build que nao diz nada nao e o caso comum, e um duple que fingia
# silencio fazia o teste de sucesso exercitar justamente o cenario que hoje
# reprova.
def _mensagens_de_compilacao():
    return [
        FakeMessage("Severity.Text", "------ Build started: Application: "
                                     "Device.Application -------"),
        FakeMessage("Severity.Text", "Typify code..."),
        FakeMessage("Severity.Text", "Compile complete -- 0 errors, 0 warnings"),
        FakeMessage("Severity.Text", "Additional code checks ..."),
        FakeMessage("Severity.Text", "Additional code checks complete -- 0 errors"),
    ]


class FakeMessage(object):
    """`ScriptMessage` sintetico, na grafia minuscula catalogada em
    `docs/api/mastertool-api-observations.md`."""

    def __init__(self, severity, text, position="linha 1", obj="guid-obj"):
        self.severity = severity
        self.text = text
        self.position = position
        self.object = obj


class FakeMessagePascal(object):
    """A outra grafia catalogada (`docs/27` secao 6): Text/Severity/
    Position/ObjectGuid."""

    def __init__(self, severity, text, position="linha 1", obj="guid-obj"):
        self.Severity = severity
        self.Text = text
        self.Position = position
        self.ObjectGuid = obj


class FakeChildren(object):
    def __init__(self, items):
        self._items = list(items)

    @property
    def Count(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]


class FakeSystem(object):
    """O `system` do MasterTool, com UM armazem de mensagens.

    Um armazem so, de proposito: e essa a realidade que causou o defeito -- o
    `print` do probe e a saida do compilador caem na MESMA colecao, porque
    `print` num script do MasterTool nao vai para stdout, vai para o message
    store do produto.
    """

    def __init__(self, mensagens=None):
        self.mensagens = list(mensagens or [])

    def get_message_categories(self, _ativas):
        return ["categoria-unica"]

    def get_message_objects(self, categoria, *args, **kwargs):
        if args or kwargs:
            raise TypeError("expected Severity, got long")
        assert isinstance(categoria, str), "categoria tem de chegar como str"
        return list(self.mensagens)

    def escrever(self, *mensagens):
        self.mensagens.extend(mensagens)


class FakeApplication(object):
    """O `Application`: e nele que `IScriptApplication.build()` vive."""

    def __init__(self, name="Application", node_type=CONTAINER_GUID,
                 build_result=None, build_error=None, on_build=None):
        self._name = name
        self.type = node_type
        self.is_folder = False
        self._build_result = build_result
        self._build_error = build_error
        self._on_build = on_build
        self.build_calls = 0

    def get_name(self, _recursive):
        return self._name

    def get_children(self, _recursive):
        return FakeChildren([])

    def build(self):
        self.build_calls = self.build_calls + 1
        if self._on_build is not None:
            self._on_build()
        if self._build_error is not None:
            raise self._build_error
        return self._build_result

    def rebuild(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou rebuild()")

    def clean(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou clean()")

    def create_boot_application(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe chamou create_boot_application()")

    def create_gvl(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe de build chamou create_gvl()")

    def create_program(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe de build chamou create_program()")


class FakeProject(object):
    def __init__(self, path, children):
        self.path = path
        self._children = list(children)

    def get_name(self, _recursive):
        return "projeto"

    def get_children(self, _recursive):
        return FakeChildren(self._children)

    def save(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe de build chamou save()")

    def save_as(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe de build chamou save_as()")

    def save_archive(self, *_a, **_k):
        raise ForbiddenMemberTouched("probe de build chamou save_archive()")


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


class FakeProjectAccess(object):
    def __init__(self, project, error=None):
        self._project = project
        self._error = error

    def get_primary_project(self, _globals):
        if self._project is None:
            return None, self._error or "projeto indisponivel"
        return self._project, None

    def get_project_path(self, project):
        return project.path


class FakeProbeCli(object):
    def __init__(self, application=None, version="4.1.0.11"):
        self._application = application
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
        return self._application


def _hash_of(path):
    digest, _erro = probe40.sha256_of_file(path)
    return digest


def _make_output(tmp_path, conteudo="saida sintetica"):
    caminho = os.path.join(str(tmp_path), "saida.project")
    handle = open(caminho, "w")
    try:
        handle.write(conteudo)
    finally:
        handle.close()
    return caminho


def _operations():
    return [
        {"kind": "create_gvl"}, {"kind": "create_program"},
        {"kind": "replace", "target": "gvl_textual_declaration"},
        {"kind": "replace", "target": "program_textual_declaration"},
        {"kind": "replace", "target": "program_textual_implementation"},
        {"kind": "save_as"}, {"kind": "build"},
    ]


def _plan(tmp_path, output_path, **overrides):
    plano = {
        "schema_version": "1.0",
        "operation_id": "w1-4-integrated-build",
        "phase": "W1_4_INTEGRATED_BUILD",
        "gvl_name": "GVL_AI_TESTE",
        "program_name": "PRG_AI_TESTE",
        "st_language_guid": ST_GUID,
        "run_id": "run-sintetica",
        "input_project": {"path": os.path.join(str(tmp_path), "copia.project"),
                          "sha256": "0" * 64},
        "output_project": {"path": output_path},
        "artifacts_dir": os.path.join(str(tmp_path), "art"),
        "container": {"node_path": "root/1/0/0", "expected_name": "Application",
                      "expected_type_guid": CONTAINER_GUID},
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


def _run40(tmp_path, application=None, project=None, safety=None,
           plano_path=None, output_path=None, output_sha=None,
           project_access=None, system=None):
    output_path = output_path or _make_output(tmp_path)
    if plano_path is None:
        plano_path, _plano = _plan(tmp_path, output_path)
    application = application if application is not None else FakeApplication(
        build_result=_mensagens_de_compilacao())
    project = project if project is not None else FakeProject(output_path,
                                                              [application])
    safety = safety if safety is not None else FakeSafety()
    acesso = project_access if project_access is not None else \
        FakeProjectAccess(project)
    if output_sha is None:
        output_sha = _hash_of(output_path)
    argv = ["probe", "--plan=" + plano_path,
            "--output=" + os.path.join(str(tmp_path), "art-build"),
            "--output-sha256=" + output_sha]
    globais = {"projects": object()}
    if system is not None:
        globais["system"] = system
    resultado = probe40.run_build(globais, argv, safety, acesso,
                                  file_io, FakeProbeCli(application=application))
    return resultado, application, project, safety


# =============================================================================
# caminho aprovado e classificacao de severidade
# =============================================================================

def test_build_com_as_mensagens_do_compilador_e_aprovado(tmp_path):
    """Caminho feliz: as cinco linhas medidas em campo, nenhuma de erro."""
    resultado, application, _p, safety = _run40(tmp_path)
    assert resultado["status"] == probe40.STATUS_BUILD_VERIFIED
    assert resultado["exit_code"] == 0
    assert application.build_calls == 1
    assert safety.requested == ["build"]
    assert resultado["message_count_from_build"] == 5


def test_build_sem_mensagem_alguma_nao_e_aprovado(tmp_path):
    """ZERO MENSAGEM NAO E APROVACAO.

    O nome deste teste sempre disse isso; o corpo afirmava o contrario --
    colecao vazia devolvia `build_verified`. Este compilador SEMPRE fala: as
    tres geracoes medidas emitiram as mesmas cinco linhas. Silencio significa
    que a leitura falhou ou que o build nao rodou, e nenhum dos dois e
    evidencia de que compilou limpo.

    O risco ficou concreto quando o probe passou a descontar a linha de base:
    um desconto largo demais esvaziaria a lista, e a lista vazia leria como
    sucesso.
    """
    resultado, application, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_result=[]))
    assert resultado["status"] == probe40.STATUS_NO_BUILD_MESSAGES
    assert resultado["exit_code"] != 0
    assert probe40.STATUS_NO_BUILD_MESSAGES in probe40.STATUSES_BLOCKING_PROMOTION
    assert application.build_calls == 1


def test_aviso_nao_e_erro(tmp_path):
    mensagens = [FakeMessage("Severity.Warning", "variavel nunca lida"),
                 FakeMessage("Severity.Information", "compilacao concluida")]
    resultado, _a, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_result=mensagens))
    assert resultado["status"] == probe40.STATUS_BUILD_VERIFIED
    resumo = resultado["message_summary"]
    assert resumo[probe40.SEVERITY_WARNING] == 1
    assert resumo[probe40.SEVERITY_INFORMATION] == 1
    assert resumo[probe40.SEVERITY_ERROR] == 0


def test_avisos_ficam_registrados_na_integra(tmp_path):
    mensagens = [FakeMessage("Warning", "aviso %d" % i) for i in range(7)]
    resultado, _a, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_result=mensagens))
    assert resultado["status"] == probe40.STATUS_BUILD_VERIFIED
    assert len(resultado["messages"]) == 7
    textos = [m["text"] for m in resultado["messages"]]
    assert textos == ["aviso %d" % i for i in range(7)]


def test_um_unico_erro_reprova(tmp_path):
    mensagens = [FakeMessage("Warning", "aviso"),
                 FakeMessage("Severity.Error", "simbolo nao resolvido")]
    resultado, _a, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_result=mensagens))
    assert resultado["status"] == probe40.STATUS_BUILD_FAILED
    assert resultado["message_summary"][probe40.SEVERITY_ERROR] == 1
    # o aviso continua registrado: e a evidencia de que a sessao o viu
    assert resultado["message_summary"][probe40.SEVERITY_WARNING] == 1
    assert len(resultado["messages"]) == 2


def test_severidade_desconhecida_nao_vira_aviso(tmp_path):
    mensagens = [FakeMessage("Severity.Nivel7", "mensagem de tipo novo")]
    resultado, _a, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_result=mensagens))
    assert resultado["status"] == probe40.STATUS_SEVERITY_UNCLASSIFIED
    assert resultado["exit_code"] != 0


def test_as_duas_grafias_catalogadas_de_ScriptMessage(tmp_path):
    mensagens = [FakeMessagePascal("Severity.Warning", "aviso em PascalCase")]
    resultado, _a, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_result=mensagens))
    assert resultado["status"] == probe40.STATUS_BUILD_VERIFIED
    registro = resultado["messages"][0]
    assert registro["text"] == "aviso em PascalCase"
    assert registro["fields_read"]["severity"] == "Severity"
    assert registro["fields_read"]["object"] == "ObjectGuid"


def test_os_quatro_campos_pedidos_pelo_contrato(tmp_path):
    mensagens = [FakeMessage("Warning", "texto", position="l3,c7", obj="guid-x")]
    resultado, _a, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_result=mensagens))
    registro = resultado["messages"][0]
    for campo in ("severity", "text", "position", "object"):
        assert registro[campo] is not None, campo


def test_classificacao_de_severidade_e_fechada():
    assert probe40.classify_severity("Severity.Error") == probe40.SEVERITY_ERROR
    assert probe40.classify_severity("FatalError") == probe40.SEVERITY_ERROR
    assert probe40.classify_severity("Warning") == probe40.SEVERITY_WARNING
    assert probe40.classify_severity("Information") == probe40.SEVERITY_INFORMATION
    assert probe40.classify_severity("Info") == probe40.SEVERITY_INFORMATION
    assert probe40.classify_severity(None) == probe40.SEVERITY_UNCLASSIFIED
    assert probe40.classify_severity("Verbose") == probe40.SEVERITY_UNCLASSIFIED


def test_erro_tem_precedencia_sobre_aviso_no_mesmo_texto():
    assert probe40.classify_severity("ErrorOrWarning") == probe40.SEVERITY_ERROR


# =============================================================================
# a lacuna declarada: fonte de mensagens
# =============================================================================

def test_build_sem_fonte_de_mensagem_nao_aprova(tmp_path):
    """`build()` que devolve None nao da fonte de mensagem alguma, e 'sem
    erro' nao pode ser afirmado sem ter lido mensagem nenhuma."""
    resultado, _a, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_result=None))
    assert resultado["status"] == probe40.STATUS_MESSAGES_UNAVAILABLE
    assert resultado["exit_code"] != 0
    assert resultado["messages_available"] is False
    assert any("catalogado" in nota for nota in resultado["gap_notes"])


def test_retorno_nao_iteravel_tambem_e_lacuna(tmp_path):
    resultado, _a, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_result=17))
    assert resultado["status"] == probe40.STATUS_MESSAGES_UNAVAILABLE


def test_retorno_de_texto_nao_e_lido_como_colecao(tmp_path):
    """Uma string e iteravel em Python e produziria uma 'mensagem' por
    caractere -- fonte falsa, o pior resultado possivel."""
    resultado, _a, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_result="build ok"))
    assert resultado["status"] == probe40.STATUS_MESSAGES_UNAVAILABLE
    assert resultado["messages"] == []


# =============================================================================
# fault injection e falsificacao
# =============================================================================

def test_build_que_levanta_reprova(tmp_path):
    resultado, _a, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_error=RuntimeError("falha")))
    assert resultado["status"] == probe40.STATUS_BUILD_FAILED
    assert resultado["blocks_promotion"] is True


def test_falsificacao_da_guarda_de_build(tmp_path):
    safety = FakeSafety(deny=("build",))
    resultado, application, _p, safety = _run40(tmp_path, safety=safety)
    assert resultado["status"] == probe40.STATUS_PRECONDITION_FAILED
    assert safety.requested == ["build"]
    assert application.build_calls == 0


def test_fase_de_w1_3_nao_autoriza_build(tmp_path):
    """Falsificacao de fase: com a allowlist de W1.3B o `build` e recusado na
    porta, e a chamada nunca acontece."""
    safety = FakeSafety(allowed=("replace", "save_as"))
    resultado, application, _p, safety = _run40(tmp_path, safety=safety)
    assert resultado["status"] == probe40.STATUS_PRECONDITION_FAILED
    assert application.build_calls == 0


def test_fase_controlada_ausente_bloqueia(tmp_path):
    safety = FakeSafety(phase=None)
    resultado, application, _p, safety = _run40(tmp_path, safety=safety)
    assert resultado["status"] == probe40.STATUS_PRECONDITION_FAILED
    assert safety.requested == []
    assert application.build_calls == 0


def test_reabertura_falha_nao_e_forcada(tmp_path):
    resultado, application, _p, _s = _run40(
        tmp_path, project_access=FakeProjectAccess(None, "arquivo ilegivel"))
    assert resultado["status"] == probe40.STATUS_REOPEN_FAILED
    assert application.build_calls == 0
    assert resultado["blocks_promotion"] is True


def test_projeto_aberto_diferente_do_output(tmp_path):
    saida = _make_output(tmp_path)
    outro = os.path.join(str(tmp_path), "outro.project")
    handle = open(outro, "w")
    try:
        handle.write("outro")
    finally:
        handle.close()
    application = FakeApplication(build_result=[])
    project = FakeProject(outro, [application])
    resultado, application, _p, _s = _run40(tmp_path, application=application,
                                            project=project, output_path=saida)
    assert resultado["status"] == probe40.STATUS_REOPEN_FAILED
    assert application.build_calls == 0


def test_hash_da_saida_divergente_do_registrado(tmp_path):
    resultado, application, _p, _s = _run40(tmp_path, output_sha="0" * 64)
    assert resultado["status"] == probe40.STATUS_REOPEN_FAILED
    assert application.build_calls == 0


def test_output_sha256_e_obrigatorio(tmp_path):
    saida = _make_output(tmp_path)
    plano_path, _plano = _plan(tmp_path, saida)
    application = FakeApplication(build_result=[])
    project = FakeProject(saida, [application])
    argv = ["probe", "--plan=" + plano_path,
            "--output=" + os.path.join(str(tmp_path), "art-build")]
    resultado = probe40.run_build({"projects": object()}, argv, FakeSafety(),
                                  FakeProjectAccess(project), file_io,
                                  FakeProbeCli(application=application))
    assert resultado["status"] == probe40.STATUS_PRECONDITION_FAILED
    assert application.build_calls == 0


def test_arquivo_alterado_pelo_build_reprova(tmp_path):
    saida = _make_output(tmp_path)

    def mexer_no_arquivo():
        handle = open(saida, "w")
        try:
            handle.write("conteudo alterado pelo build")
        finally:
            handle.close()

    application = FakeApplication(build_result=[], on_build=mexer_no_arquivo)
    project = FakeProject(saida, [application])
    resultado, application, _p, _s = _run40(tmp_path, application=application,
                                            project=project, output_path=saida)
    assert resultado["status"] == probe40.STATUS_OUTPUT_MODIFIED_BY_BUILD
    assert resultado["output_project"]["unchanged"] is False


def test_plano_de_outra_fase_recusado(tmp_path):
    saida = _make_output(tmp_path)
    plano_path, _plano = _plan(tmp_path, saida, phase="W1_3B_EDIT_PROGRAM")
    resultado, application, _p, _s = _run40(tmp_path, plano_path=plano_path,
                                            output_path=saida)
    assert resultado["status"] == probe40.STATUS_PRECONDITION_FAILED
    assert application.build_calls == 0


def test_plano_sem_build_na_cadeia_recusado(tmp_path):
    saida = _make_output(tmp_path)
    plano_path, _plano = _plan(tmp_path, saida, operations=_operations()[:6])
    resultado, application, _p, _s = _run40(tmp_path, plano_path=plano_path,
                                            output_path=saida)
    assert resultado["status"] == probe40.STATUS_PRECONDITION_FAILED
    assert application.build_calls == 0


def test_objeto_alvo_com_type_guid_divergente(tmp_path):
    application = FakeApplication(node_type="guid-errado", build_result=[])
    resultado, application, _p, _s = _run40(tmp_path, application=application)
    assert resultado["status"] == probe40.STATUS_PRECONDITION_FAILED
    assert application.build_calls == 0


def test_versao_de_instalacao_divergente(tmp_path):
    saida = _make_output(tmp_path)
    plano_path, _plano = _plan(tmp_path, saida)
    application = FakeApplication(build_result=[])
    project = FakeProject(saida, [application])
    argv = ["probe", "--plan=" + plano_path,
            "--output=" + os.path.join(str(tmp_path), "art-build"),
            "--output-sha256=" + _hash_of(saida)]
    resultado = probe40.run_build({"projects": object()}, argv, FakeSafety(),
                                  FakeProjectAccess(project), file_io,
                                  FakeProbeCli(application=application,
                                               version="4.0.0.0"))
    assert resultado["status"] == probe40.STATUS_PRECONDITION_FAILED
    assert application.build_calls == 0


# =============================================================================
# artefatos e estados
# =============================================================================

def test_somente_build_verified_tem_codigo_zero():
    for status in probe40.ALL_STATUSES:
        esperado = (status == probe40.STATUS_BUILD_VERIFIED)
        assert (probe40.EXIT_BY_STATUS[status] == 0) is esperado, status


def test_todo_status_que_nao_e_sucesso_bloqueia_promocao():
    for status in probe40.ALL_STATUSES:
        if status == probe40.STATUS_BUILD_VERIFIED:
            assert status not in probe40.STATUSES_BLOCKING_PROMOTION
        else:
            assert status in probe40.STATUSES_BLOCKING_PROMOTION, status


def test_completion_por_ultimo(tmp_path):
    resultado, _a, _p, _s = _run40(tmp_path)
    escritos = probe40.write_artifacts(resultado, file_io)
    assert escritos[-1] == "build-completion.json"
    completion = probe40.build_completion(resultado)
    assert completion["is_success"] is True
    assert completion["no_other_mutator_requested"] is True
    assert completion["operations_executed"] == ["build"]
    assert completion["output_unchanged_by_build"] is True


def test_todos_os_artefatos_do_build(tmp_path):
    resultado, _a, _p, _s = _run40(tmp_path)
    probe40.write_artifacts(resultado, file_io)
    presentes = os.listdir(resultado["artifacts_dir"])
    for nome in probe40.ARTIFACT_NAMES:
        if nome == "build-journal.jsonl":
            continue                     # gravado incrementalmente pelo Journal
        assert nome in presentes, nome


def test_journal_tem_attempt_e_done_do_build(tmp_path):
    resultado, _a, _p, _s = _run40(tmp_path)
    eventos = [(e.get("event"), e.get("operation")) for e in resultado["journal"]]
    assert ("mutation_attempt", "build") in eventos
    assert ("mutation_done", "build") in eventos


def test_relatorio_diz_que_aviso_nao_e_erro(tmp_path):
    mensagens = [FakeMessage("Warning", "aviso")]
    resultado, _a, _p, _s = _run40(
        tmp_path, application=FakeApplication(build_result=mensagens))
    texto = probe40.build_report_markdown(resultado)
    assert "AVISO NAO E ERRO" in texto
    assert "aviso" in texto


# =============================================================================
# verificacao estatica
# =============================================================================

@pytest.fixture(scope="module")
def tree40():
    return ast.parse(io.open(PROBE40_PATH, encoding="utf-8").read())


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


def test_exatamente_uma_chamada_de_build_por_receptor(tree40):
    """A contagem e por RECEPTOR: `build_completion(...)` e
    `build_report_markdown(...)` sao funcoes do modulo, nao a API. So
    `application.build()` conta."""
    chamadas = _method_calls(tree40, "build")
    assert len(chamadas) == 1
    receptor = chamadas[0].func.value
    assert isinstance(receptor, ast.Name)
    assert receptor.id == "application"
    assert chamadas[0].args == []


def test_uma_unica_guarda_e_ela_e_de_build(tree40):
    guardas = [n for n in _calls(tree40)
               if isinstance(n.func, ast.Attribute)
               and n.func.attr == "assert_controlled_write_allowed"]
    assert len(guardas) == 1
    assert isinstance(guardas[0].args[0], ast.Str)
    assert guardas[0].args[0].s == "build"


def test_a_guarda_e_a_linha_imediatamente_anterior(tree40):
    pares = []
    for node in ast.walk(tree40):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        index = 0
        while index < len(body) - 1:
            atual, seguinte = body[index], body[index + 1]
            if isinstance(atual, (ast.Expr, ast.Assign)) and \
                    isinstance(seguinte, (ast.Expr, ast.Assign)):
                guarda = [n for n in _calls(atual)
                          if isinstance(n.func, ast.Attribute)
                          and n.func.attr == "assert_controlled_write_allowed"]
                if guarda and _method_calls(seguinte, "build"):
                    pares.append((atual, seguinte))
            index = index + 1
    assert len(pares) == 1
    guarda, mutacao = pares[0]
    assert mutacao.lineno == guarda.lineno + 1


def test_o_application_so_recebe_build(tree40):
    chamadas = _calls_by_receiver(tree40, ("application",))
    assert chamadas
    for receptor, metodo in chamadas:
        assert metodo == "build", "%s.%s()" % (receptor, metodo)


def test_o_projeto_nunca_recebe_persistencia(tree40):
    for receptor, metodo in _calls_by_receiver(tree40, ("project",)):
        assert metodo not in ("save", "save_as", "save_archive", "close"), \
            "%s.%s()" % (receptor, metodo)


@pytest.mark.parametrize("metodo", [
    "save", "save_as", "save_archive", "rebuild", "clean",
    "create_boot_application", "create_gvl", "create_program", "create_pou",
    "replace", "replace_line", "rename", "move", "import_xml",
    "download_missing_libraries", "set_compilerversion_to_newest",
    "add_library", "remove_library", "Invoke",
])
def test_mutador_proibido_ausente_no_probe40(tree40, metodo):
    assert _method_calls(tree40, metodo) == []


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_sem_acesso_dinamico_probe40(tree40, nome):
    assert [n for n in _calls(tree40)
            if isinstance(n.func, ast.Name) and n.func.id == nome] == []


def test_sem_lambda_nem_fstring_probe40(tree40):
    assert [n for n in ast.walk(tree40) if isinstance(n, ast.Lambda)] == []
    assert [n for n in ast.walk(tree40)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []


def test_identificadores_ascii_probe40(tree40):
    for node in ast.walk(tree40):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


def test_busca_literal_sem_persistencia_no_probe40():
    texto = io.open(PROBE40_PATH, encoding="utf-8").read()
    for proibido in (".save(", ".save_as(", ".save_archive(", ".rebuild(",
                     ".clean(", "getattr("):
        assert proibido not in texto, proibido


def test_a_fase_esperada_e_a_de_w1_4():
    assert probe40.EXPECTED_PHASE == "W1_4_INTEGRATED_BUILD"


# =============================================================================
# linha de base do message store -- o probe le o armazem onde ele mesmo escreve
# =============================================================================

def _banner_do_probe():
    """O que o `print` deste probe deixa no store antes do build."""
    return [
        FakeMessage("Severity.Text", "=" * 68),
        FakeMessage("Severity.Text",
                    "[INFO] probes/40_build_w1_4.py -- W1.4 build"),
        FakeMessage("Severity.Text", "=" * 68),
    ]


def _com_system(tmp_path, antes, depois):
    """Roda o probe com um `system` cujo store ganha `depois` durante o build.

    `build_result=None` de proposito: e assim que o produto se comporta -- a
    run-019 mediu que `build()` nao devolve colecao --, e e o que faz o probe
    cair na leitura pelo `system`, que e o caminho onde a contaminacao existe.
    """
    system = FakeSystem(antes)
    aplicacao = FakeApplication(build_result=None,
                               on_build=lambda: system.escrever(*depois))
    return _run40(tmp_path, application=aplicacao, system=system)


def test_o_banner_do_proprio_probe_nao_conta_como_mensagem_do_build(tmp_path):
    """O defeito medido na run-023: 8 mensagens, das quais 3 eram o probe se
    lendo. `message_summary` decide o status e por isso conta so o build; o
    total fica ao lado para que o desconto seja auditavel."""
    resultado, _a, _p, _s = _com_system(
        tmp_path, _banner_do_probe(), _mensagens_de_compilacao())
    assert resultado["status"] == probe40.STATUS_BUILD_VERIFIED
    assert resultado["message_count_total"] == 8
    assert resultado["message_count_from_build"] == 5
    assert resultado["messages_baseline_count"] == 3
    assert resultado["message_summary"][probe40.SEVERITY_INFORMATION] == 5
    assert (resultado["message_summary_including_pre_existing"]
            [probe40.SEVERITY_INFORMATION]) == 8


def test_as_mensagens_pre_existentes_ficam_no_artefato_marcadas(tmp_path):
    """Descontar nao e apagar. As oito continuam gravadas na integra -- o que
    muda e a atribuicao. Apagar destruiria a evidencia de que o desconto
    aconteceu, e um desconto invisivel nao pode ser auditado."""
    resultado, _a, _p, _s = _com_system(
        tmp_path, _banner_do_probe(), _mensagens_de_compilacao())
    assert len(resultado["messages"]) == 8
    marcadas = [m for m in resultado["messages"] if m["pre_existing"]]
    assert len(marcadas) == 3
    assert all("pre_existing" in m for m in resultado["messages"])


def test_erro_do_compilador_nao_e_descontado(tmp_path):
    """A direcao que importa: o desconto nunca pode silenciar o build."""
    resultado, _a, _p, _s = _com_system(
        tmp_path, _banner_do_probe(),
        [FakeMessage("Severity.Error", "simbolo nao resolvido")])
    assert resultado["status"] == probe40.STATUS_BUILD_FAILED
    assert resultado["message_summary"][probe40.SEVERITY_ERROR] == 1


def test_desconto_e_por_multiconjunto_e_nao_por_conjunto(tmp_path):
    """Se o texto aparece DUAS vezes depois e UMA antes, so uma e
    pre-existente. Com semantica de conjunto, um erro de compilacao que
    repetisse o texto de uma mensagem anterior sumiria do resumo -- e sumir do
    resumo e sumir do veredito."""
    repetido = "simbolo nao resolvido"
    resultado, _a, _p, _s = _com_system(
        tmp_path,
        [FakeMessage("Severity.Error", repetido)],
        [FakeMessage("Severity.Error", repetido),
         FakeMessage("Severity.Error", repetido)])
    assert resultado["message_count_total"] == 3
    assert resultado["message_count_from_build"] == 2
    assert resultado["message_summary"][probe40.SEVERITY_ERROR] == 2
    assert resultado["status"] == probe40.STATUS_BUILD_FAILED


def test_build_mudo_apos_o_desconto_nao_vira_sucesso(tmp_path):
    """O buraco que o proprio desconto abriu: se tudo for descontado, a lista
    fica vazia -- e vazia leria como 'compilou limpo' sem a regra de zero
    mensagem."""
    resultado, _a, _p, _s = _com_system(
        tmp_path, _banner_do_probe(), [])
    assert resultado["status"] == probe40.STATUS_NO_BUILD_MESSAGES
    assert resultado["exit_code"] != 0
    assert resultado["message_count_from_build"] == 0
    assert resultado["message_count_total"] == 3


def test_identidade_de_mensagem_usa_campos_lidos_e_nao_o_objeto():
    """Comparar identidade de OBJETO marcaria tudo como novo: o produto
    devolve um objeto diferente a cada leitura para o mesmo texto."""
    a = probe40.describe_message(FakeMessage("Severity.Text", "igual"))
    b = probe40.describe_message(FakeMessage("Severity.Text", "igual"))
    assert a is not b
    assert probe40.message_identity(a) == probe40.message_identity(b)


def test_no_build_messages_esta_no_vocabulario_fechado():
    assert probe40.STATUS_NO_BUILD_MESSAGES in probe40.ALL_STATUSES
    assert probe40.STATUS_NO_BUILD_MESSAGES not in probe40.SUCCESS_STATUSES
    assert probe40.STATUS_NO_BUILD_MESSAGES in probe40.STATUSES_BLOCKING_PROMOTION
    assert probe40.EXIT_BY_STATUS[probe40.STATUS_NO_BUILD_MESSAGES] != 0


def test_o_completion_carrega_os_numeros_do_desconto(tmp_path):
    """Desconto que nao aparece no artefato e desconto que ninguem confere.

    O `completion.json` e o que o host le para decidir; se ele trouxesse
    apenas o resumo ja descontado, nada no artefato diria que houve desconto,
    nem de quanto.
    """
    resultado, _a, _p, _s = _com_system(
        tmp_path, _banner_do_probe(), _mensagens_de_compilacao())
    completion = probe40.build_completion(resultado)
    assert completion["message_count_from_build"] == 5
    assert completion["message_count_total"] == 8
    assert completion["messages_baseline_count"] == 3
    assert completion["messages_baseline_available"] is True
    assert completion["message_summary"][probe40.SEVERITY_INFORMATION] == 5
    assert (completion["message_summary_including_pre_existing"]
            [probe40.SEVERITY_INFORMATION]) == 8


# =============================================================================
# a cadeia esperada e POR FASE
# =============================================================================

def test_cada_fase_aceita_para_build_declara_a_propria_cadeia():
    """Antes havia uma tupla so, a de W1.4, exigida de todo plano de build --
    e por isso o plano de build de W2 teve de declarar operacoes que NAO
    produziram aquele artefato. Passava na validacao e mentia no registro."""
    for fase in probe40.ACCEPTED_BUILD_PHASES:
        assert fase in probe40.EXPECTED_PLAN_OPERATIONS_BY_PHASE, fase
    for cadeia in probe40.EXPECTED_PLAN_OPERATIONS_BY_PHASE.values():
        assert cadeia[-1] == "build", cadeia


def test_a_cadeia_de_w2_continua_sendo_a_de_w1_4_por_registro():
    """Reescrever aqui invalidaria um plano ja executado e documentado em
    docs/39. Corrigir para frente, sem reescrever historia."""
    assert (probe40.EXPECTED_PLAN_OPERATIONS_BY_PHASE["W2_VERIFY_BUILD"]
            == probe40.EXPECTED_PLAN_OPERATIONS)


def test_fase_sem_cadeia_declarada_e_RECUSADA_e_nao_cai_no_padrao(tmp_path):
    """Fallback silencioso para a cadeia de W1.4 deixaria uma fase nova passar
    declarando a cadeia errada."""
    output_path = _make_output(tmp_path)
    plano_path, _p = _plan(tmp_path, output_path, phase="W2_VERIFY_BUILD",
                           operation_id="w2-verify-build")
    # A fase existe no mapa; remove-la prova que a ausencia REPROVA.
    guardado = dict(probe40.EXPECTED_PLAN_OPERATIONS_BY_PHASE)
    try:
        del probe40.EXPECTED_PLAN_OPERATIONS_BY_PHASE["W2_VERIFY_BUILD"]
        resultado, _a, _p2, _s = _run40(tmp_path, plano_path=plano_path,
                                        output_path=output_path)
    finally:
        probe40.EXPECTED_PLAN_OPERATIONS_BY_PHASE.clear()
        probe40.EXPECTED_PLAN_OPERATIONS_BY_PHASE.update(guardado)
    assert resultado["status"] == probe40.STATUS_PRECONDITION_FAILED
    assert any("cadeia esperada" in p for p in resultado["problems"])

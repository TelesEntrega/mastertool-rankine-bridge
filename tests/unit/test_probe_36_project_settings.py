"""Testes de `probes/36_probe_project_settings_readonly.py`, com dubles
ESTRITOS e verificacao estatica (AST).

Nenhuma API real do MasterTool e importada ou chamada. O duble de projeto
LEVANTA se o probe tocar qualquer coisa alem de `.project_settings`, e o duble
de settings LEVANTA se o probe chamar qualquer coisa alem de
`get_compilerversion()` -- e assim que "so a cadeia descoberta" deixa de ser
promessa de docstring e vira verificacao.

O wrapper `run_probe_project_settings.ps1` tambem e verificado por texto: ASCII
puro, sem `--noUI`, sem `Stop-Process`, e gravando JSON sem BOM.
"""

import ast
import io
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
_MASTERTOOL_DIR = os.path.join(_REPO_ROOT, "scripts", "mastertool")
if _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)

PROBE36_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "36_probe_project_settings_readonly.py")
WRAPPER_PATH = os.path.join(_MASTERTOOL_DIR, "run_probe_project_settings.ps1")


def _load_module(path, name):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except ImportError:                                            # IronPython 2.7
        import imp
        return imp.load_source(name, path)


probe36 = _load_module(PROBE36_PATH, "probe36_project_settings")


# =============================================================================
# Dubles ESTRITOS -- qualquer acesso fora da cadeia medida LEVANTA
# =============================================================================

class SettingsEstrito(object):
    """So responde `get_compilerversion()`. Qualquer outro atributo levanta --
    inclusive o mutador irmao, que assim nao pode passar despercebido."""

    def __init__(self, value=None, raise_on_call=None):
        self._value = value
        self._raise_on_call = raise_on_call
        self.calls = []

    def get_compilerversion(self):
        self.calls.append("get_compilerversion")
        if self._raise_on_call is not None:
            raise self._raise_on_call
        return self._value

    def __getattr__(self, name):
        raise AssertionError(
            "probe 36 acessou %r no objeto de settings -- fora da cadeia "
            "medida" % name)


class ProjetoEstrito(object):
    """So responde `project_settings` e `path`. Qualquer outro atributo
    levanta: se o probe tentasse um acessor alternativo, o teste quebra."""

    def __init__(self, settings, path="C:/w/proj.project"):
        self._settings = settings
        self.path = path
        self.settings_reads = 0

    @property
    def project_settings(self):
        self.settings_reads += 1
        if isinstance(self._settings, Exception):
            raise self._settings
        return self._settings

    def __getattr__(self, name):
        raise AssertionError(
            "probe 36 acessou %r no projeto -- fora da cadeia medida" % name)


# =============================================================================
# Cadeia literal -- a constante e a fonte precisam continuar dizendo a verdade
# =============================================================================

def test_cadeia_literal_e_a_medida():
    assert probe36.ACCESSOR_CHAIN == (
        "projects.primary.project_settings.get_compilerversion()")
    assert len(probe36.ACCESSOR_CHAIN_STEPS) == 3
    assert probe36.ACCESSOR_CHAIN_STEPS[0] == "projects.primary"


def test_fonte_da_cadeia_cita_tipo_e_membro_verificaveis():
    """A fonte nao pode ser 'a documentacao diz': tem de nomear o assembly, o
    tipo e o membro, para que outra pessoa refaca a reflexao e confira."""
    fonte = probe36.ACCESSOR_CHAIN_SOURCE
    assert "ScriptEngine3.dll" in fonte
    assert "IScriptProject11" in fonte
    assert "IScriptProjectSettings2" in fonte
    assert "get_compilerversion" in fonte


# =============================================================================
# build_evidence -- lacuna nunca se disfarca de medida
# =============================================================================

def test_evidencia_medida_quando_valor_textual_nao_vazio():
    ev = probe36.build_evidence("3.5.19.20", None)
    assert ev["status"] == probe36.EVIDENCE_MEASURED
    assert ev["value"] == "3.5.19.20"
    assert ev["reason"] is None
    assert ev["accessor_chain"] == probe36.ACCESSOR_CHAIN


@pytest.mark.parametrize("valor", [None, "", "   ", 42, object()])
def test_evidencia_lacuna_para_valor_nao_textual_ou_vazio(valor):
    ev = probe36.build_evidence(valor, "razao escrita")
    assert ev["status"] == probe36.EVIDENCE_UNRESOLVED
    assert ev["value"] is None
    assert ev["reason"] == "razao escrita"


def test_lacuna_sem_razao_ainda_tem_razao():
    """`None` nunca atravessa a fronteira como razao: uma lacuna sem motivo
    escrito e indistinguivel de um campo esquecido."""
    ev = probe36.build_evidence(None, None)
    assert ev["reason"]


def test_classify_deriva_status_da_evidencia():
    assert probe36.classify(probe36.build_evidence("4.1", None)) == probe36.STATUS_MEASURED
    assert probe36.classify(probe36.build_evidence(None, "x")) == probe36.STATUS_UNRESOLVED
    assert probe36.classify(None) == probe36.STATUS_UNRESOLVED


# =============================================================================
# read_compiler_version -- a cadeia, e so ela
# =============================================================================

def test_le_pela_cadeia_e_so_por_ela():
    settings = SettingsEstrito(value="3.5.19.20")
    projeto = ProjetoEstrito(settings)
    ev, passos = probe36.read_compiler_version(projeto)
    assert ev["status"] == probe36.EVIDENCE_MEASURED
    assert ev["value"] == "3.5.19.20"
    assert settings.calls == ["get_compilerversion"]
    # UMA leitura da propriedade: sem retentativa, sem segunda rota.
    assert projeto.settings_reads == 1
    assert [p["step"] for p in passos] == [
        "projects.primary", "project_settings", "get_compilerversion()"]
    assert all(p["ok"] for p in passos)


def test_sem_projeto_vira_lacuna_e_nao_excecao():
    ev, passos = probe36.read_compiler_version(None)
    assert ev["status"] == probe36.EVIDENCE_UNRESOLVED
    assert probe36.REASON_NO_PROJECT in ev["reason"]
    assert passos[0]["ok"] is False


def test_settings_none_vira_lacuna_nomeando_o_elo():
    ev, passos = probe36.read_compiler_version(ProjetoEstrito(None))
    assert ev["status"] == probe36.EVIDENCE_UNRESOLVED
    assert ev["reason"] == probe36.REASON_SETTINGS_IS_NONE
    assert passos[-1]["step"] == "project_settings"


def test_excecao_no_passo_settings_vira_lacuna_com_o_repr():
    projeto = ProjetoEstrito(RuntimeError("sem membro"))
    ev, passos = probe36.read_compiler_version(projeto)
    assert ev["status"] == probe36.EVIDENCE_UNRESOLVED
    assert probe36.REASON_NO_SETTINGS_STEP in ev["reason"]
    assert "sem membro" in ev["reason"]
    assert passos[-1]["ok"] is False


def test_excecao_na_chamada_vira_lacuna_e_nao_tenta_outro_acessor():
    settings = SettingsEstrito(raise_on_call=RuntimeError("boom"))
    projeto = ProjetoEstrito(settings)
    ev, _ = probe36.read_compiler_version(projeto)
    assert ev["status"] == probe36.EVIDENCE_UNRESOLVED
    assert probe36.REASON_CALL_FAILED in ev["reason"]
    # UMA tentativa. Um fallback apareceria aqui como segunda chamada.
    assert settings.calls == ["get_compilerversion"]


def test_valor_vazio_do_produto_nao_vira_medida():
    projeto = ProjetoEstrito(SettingsEstrito(value="   "))
    ev, _ = probe36.read_compiler_version(projeto)
    assert ev["status"] == probe36.EVIDENCE_UNRESOLVED
    assert ev["value"] is None


# =============================================================================
# run_probe -- orquestracao, com dubles de io/cli
# =============================================================================

class ProbeCliFalso(object):
    def __init__(self, output="C:/fora/artefatos"):
        self._output = output

    def find_arg(self, argv, name):
        return self._output if name == "output" else None

    def validate_output_path(self, raw, repo_root, problems):
        if not raw:
            problems.append("--output e obrigatorio")
            return None
        return raw

    def runtime_identity(self):
        return {"file_version": "4.1.0.11"}


class ProjectAccessFalso(object):
    def __init__(self, project, error=None):
        self._project = project
        self._error = error

    def get_primary_project(self, script_globals):
        return self._project, self._error

    def get_project_path(self, project):
        return project.path


class FileIoFalso(object):
    def __init__(self):
        self.json_writes = {}
        self.text_writes = {}

    def iso_now(self):
        return "2026-07-31T00:00:00"

    def ensure_dir(self, path):
        return path

    def write_json(self, path, data):
        self.json_writes[os.path.basename(path)] = data
        return path

    def write_text(self, path, text):
        self.text_writes[os.path.basename(path)] = text
        return path


def test_run_probe_sucesso():
    projeto = ProjetoEstrito(SettingsEstrito(value="3.5.19.20"))
    file_io = FileIoFalso()
    resultado = probe36.run_probe({}, [], ProjectAccessFalso(projeto), file_io,
                                  ProbeCliFalso())
    assert resultado["status"] == probe36.STATUS_MEASURED
    assert resultado["exit_code"] == 0
    assert resultado["compiler_version"]["value"] == "3.5.19.20"
    assert resultado["mutating_calls"] == []
    assert resultado["problems"] == []

    completion = probe36.build_completion(resultado)
    assert completion["is_success"] is True
    assert completion["compiler_version_value"] == "3.5.19.20"
    assert completion["accessor_chain"] == probe36.ACCESSOR_CHAIN

    probe36.write_artifacts(resultado, file_io)
    assert "project-settings-completion.json" in file_io.json_writes
    assert "project-settings-analysis.json" in file_io.json_writes
    assert "project-settings-report.md" in file_io.text_writes


def test_run_probe_lacuna_nao_e_sucesso_e_nao_sai_zero():
    projeto = ProjetoEstrito(SettingsEstrito(value=None))
    resultado = probe36.run_probe({}, [], ProjectAccessFalso(projeto),
                                  FileIoFalso(), ProbeCliFalso())
    assert resultado["status"] == probe36.STATUS_UNRESOLVED
    assert resultado["exit_code"] == 2
    assert probe36.build_completion(resultado)["is_success"] is False
    assert resultado["problems"]


def test_run_probe_sem_output_e_fatal_antes_de_tocar_o_projeto():
    """Se o argumento for recusado, o projeto nem chega a ser acessado -- o
    duble de projeto levantaria se fosse tocado."""
    resultado = probe36.run_probe({}, [], ProjectAccessFalso(None, "n/a"),
                                  FileIoFalso(), ProbeCliFalso(output=None))
    assert resultado["status"] == probe36.STATUS_FATAL
    assert resultado["exit_code"] == 1


def test_run_probe_sem_projeto_primario_e_fatal():
    resultado = probe36.run_probe({}, [], ProjectAccessFalso(None, "nada aberto"),
                                  FileIoFalso(), ProbeCliFalso())
    assert resultado["status"] == probe36.STATUS_FATAL
    assert resultado["compiler_version"]["status"] == probe36.EVIDENCE_UNRESOLVED


def test_relatorio_markdown_mostra_a_cadeia_junto_do_valor():
    projeto = ProjetoEstrito(SettingsEstrito(value="3.5.19.20"))
    resultado = probe36.run_probe({}, [], ProjectAccessFalso(projeto),
                                  FileIoFalso(), ProbeCliFalso())
    texto = probe36.build_report_markdown(resultado)
    assert "3.5.19.20" in texto
    assert probe36.ACCESSOR_CHAIN in texto


def test_exit_codes_cobrem_todos_os_status():
    for status in probe36.ALL_STATUSES:
        assert status in probe36.EXIT_BY_STATUS
    assert probe36.EXIT_BY_STATUS[probe36.STATUS_MEASURED] == 0
    for status in probe36.ALL_STATUSES:
        zero = probe36.EXIT_BY_STATUS[status] == 0
        assert zero == (status in probe36.SUCCESS_STATUSES)


# =============================================================================
# Verificacao estatica (AST) -- probe 36 e SOMENTE LEITURA
# =============================================================================

@pytest.fixture(scope="module")
def tree36():
    return ast.parse(io.open(PROBE36_PATH, encoding="utf-8").read())


def _method_calls(tree, nome):
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == nome]


# O RECEPTOR decide, nunca o nome do metodo: `.insert(...)` existe em `list`
# (`sys.path.insert(0, ...)`, presente neste probe) E em
# `IScriptTextDocument`. Proibir o NOME inteiro reprovaria codigo legitimo.
_RECEPTORES_SEGUROS_CONHECIDOS = {
    "insert": (("sys", "path"),),
}


def _method_calls_sobre_proxy(tree, nome):
    seguros = _RECEPTORES_SEGUROS_CONHECIDOS.get(nome, ())
    encontrados = []
    for chamada in _method_calls(tree, nome):
        receptor = chamada.func.value
        if isinstance(receptor, ast.Attribute) and isinstance(receptor.value, ast.Name):
            if (receptor.value.id, receptor.attr) in seguros:
                continue
        encontrados.append(chamada)
    return encontrados


MUTADORES_PROIBIDOS = (
    "create_gvl", "create_pou", "create_program", "create_folder", "create_dut",
    "create_function", "create_function_block", "create_interface",
    "create_persistentvars", "create_task", "create_task_configuration",
    "create_boot_application", "replace", "replace_line", "insert", "remove",
    "save", "save_as", "save_archive", "build", "rebuild", "clean", "close",
    "import_xml", "import_native", "import_device", "rename", "move", "add",
    "unplug", "update", "set_gateway_and_ip_address", "remove_device",
    "set_compilerversion_to_newest", "set_project_defines", "set_sourcedownload",
    "download_missing_libraries", "remove_library", "add_library",
    "add_placeholder",
)


@pytest.mark.parametrize("metodo", MUTADORES_PROIBIDOS)
def test_probe_36_nao_contem_mutador(tree36, metodo):
    assert _method_calls_sobre_proxy(tree36, metodo) == [], (
        "probe 36 e read-only e nao pode chamar .%s() sobre proxy do "
        "MasterTool" % metodo)


def test_probe_36_nao_menciona_o_mutador_de_compiler_version():
    """O mutador irmao vive no MESMO tipo e difere por um sufixo. A guarda de
    AST pega a CHAMADA; esta pega a MENCAO -- inclusive em comentario, string
    ou docstring, de onde alguem poderia copiar por engano."""
    fonte = io.open(PROBE36_PATH, encoding="utf-8").read()
    assert "set_compilerversion" not in fonte


@pytest.mark.parametrize("nome", ["getattr", "setattr", "delattr", "hasattr",
                                  "eval", "exec", "compile", "__import__",
                                  "vars", "locals", "dir"])
def test_probe_36_sem_acesso_dinamico(tree36, nome):
    """Reflexao foi o instrumento de INVESTIGACAO das DLLs, fora do produto.
    Dentro do probe ela seria a invencao de API que este arquivo elimina."""
    encontrados = [n for n in ast.walk(tree36)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == nome]
    assert encontrados == []


def test_probe_36_acessa_project_settings_por_atributo_literal(tree36):
    """`project_settings` tem de aparecer como acesso de atributo LITERAL --
    se um dia virar nome calculado, esta guarda quebra."""
    acessos = [n for n in ast.walk(tree36)
               if isinstance(n, ast.Attribute) and n.attr == "project_settings"
               and isinstance(n.value, ast.Name) and n.value.id == "project"]
    assert len(acessos) == 1


def test_probe_36_chama_get_compilerversion_uma_unica_vez(tree36):
    """Uma chamada no fonte inteiro. Duas seriam retentativa ou fallback."""
    assert len(_method_calls(tree36, "get_compilerversion")) == 1


def test_probe_36_sem_fstring_e_identificadores_ascii(tree36):
    assert [n for n in ast.walk(tree36)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []
    for node in ast.walk(tree36):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


def test_probe_36_compativel_com_ironpython_27(tree36):
    fonte = io.open(PROBE36_PATH, encoding="utf-8").read()
    assert "from __future__ import print_function" in fonte
    assert "yield from" not in fonte
    assert "pathlib" not in fonte
    for node in ast.walk(tree36):
        assert not isinstance(node, ast.AnnAssign)
        if isinstance(node, ast.FunctionDef):
            assert node.returns is None
            for arg in node.args.args:
                assert getattr(arg, "annotation", None) is None


# =============================================================================
# Wrapper .ps1 -- fail-closed, ASCII puro, sem --noUI, sem Stop-Process
# =============================================================================

@pytest.fixture(scope="module")
def wrapper_fonte():
    return io.open(WRAPPER_PATH, encoding="utf-8").read()


@pytest.fixture(scope="module")
def wrapper_codigo(wrapper_fonte):
    """So as linhas EXECUTAVEIS: bloco `<# ... #>` e linhas de comentario
    removidos. As proibicoes valem para o que o PowerShell executa -- proibir
    a MENCAO tambem apagaria a explicacao de por que a proibicao existe, que e
    justamente o que impede alguem de reintroduzir o defeito."""
    linhas = []
    dentro_do_bloco = False
    for linha in wrapper_fonte.splitlines():
        texto = linha.strip()
        if texto.startswith("<#"):
            dentro_do_bloco = True
        if dentro_do_bloco:
            if texto.endswith("#>"):
                dentro_do_bloco = False
            continue
        if texto.startswith("#"):
            continue
        linhas.append(linha)
    return "\n".join(linhas)


def test_wrapper_existe_e_e_ascii_puro():
    dados = io.open(WRAPPER_PATH, "rb").read()
    fora = [b for b in bytearray(dados) if b > 127]
    assert fora == [], "wrapper tem %d byte(s) > 127" % len(fora)


def test_wrapper_nunca_usa_noui_nem_mata_processo(wrapper_fonte, wrapper_codigo):
    assert "--noUI" not in wrapper_codigo
    assert "Stop-Process" not in wrapper_codigo
    assert "CloseMainWindow" in wrapper_fonte


def test_wrapper_default_nao_abre_nada(wrapper_fonte):
    assert "assumindo -ValidateOnly (default)" in wrapper_fonte
    assert "[switch]$Execute" in wrapper_fonte
    assert "Modos mutuamente exclusivos" in wrapper_fonte


def test_wrapper_grava_json_sem_bom(wrapper_fonte, wrapper_codigo):
    """`Out-File -Encoding utf8` grava BOM no PS 5.1 e um leitor JSON estrito
    recusaria o proprio relatorio da sessao."""
    assert "System.Text.UTF8Encoding($false)" in wrapper_fonte
    assert "[System.IO.File]::WriteAllText" in wrapper_fonte
    assert "Out-File" not in wrapper_codigo


def test_wrapper_verifica_hash_antes_e_depois(wrapper_fonte):
    assert "Get-FileHash" in wrapper_fonte
    assert "A copia MUDOU durante a leitura read-only." in wrapper_fonte
    assert "O PROJETO-BASE ORIGINAL foi tocado." in wrapper_fonte


def test_wrapper_recusa_probe_com_mutador(wrapper_fonte):
    assert "Sessao recusada" in wrapper_fonte
    assert "READ_ONLY_PHASE" in wrapper_fonte


def test_wrapper_separa_sessao_de_medida(wrapper_fonte):
    """Sessao que roda inteira e nao mede nada nao pode sair com 0."""
    assert "exit 4" in wrapper_fonte
    assert "compiler_version_measured" in wrapper_fonte

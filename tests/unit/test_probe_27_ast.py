"""Verificacao ESTATICA (AST) de `probes/27_create_gvl_w1_1.py`.

Nao importa o probe, nao executa nada, nao toca o MasterTool: le o arquivo e
inspeciona a arvore sintatica.

Estes testes existem porque as garantias do contrato sao sobre a FORMA do
codigo, e forma se verifica lendo o codigo. "A guarda fica colada na chamada" e
uma afirmacao sobre linhas adjacentes -- ou um teste olha para elas, ou a
afirmacao e so um comentario que envelhece.
"""

import ast
import io
import os

import pytest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
PROBE_PATH = os.path.join(_REPO_ROOT, "scripts", "mastertool", "probes",
                          "27_create_gvl_w1_1.py")

GUARD_NAME = "assert_controlled_write_allowed"


@pytest.fixture(scope="module")
def source():
    return io.open(PROBE_PATH, encoding="utf-8").read()


@pytest.fixture(scope="module")
def tree(source):
    return ast.parse(source)


def _calls(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]


def _method_calls(tree, method_name):
    return [node for node in _calls(tree)
            if isinstance(node.func, ast.Attribute) and node.func.attr == method_name]


def _guard_calls(tree, operation):
    found = []
    for node in _calls(tree):
        if isinstance(node.func, ast.Attribute) and node.func.attr == GUARD_NAME:
            if node.args and isinstance(node.args[0], ast.Str) \
                    and node.args[0].s == operation:
                found.append(node)
    return found


def test_probe_existe():
    assert os.path.isfile(PROBE_PATH)


# --- as duas chamadas mutaveis, literais ------------------------------------

def test_guarda_literal_de_create_gvl(tree):
    assert len(_guard_calls(tree, "create_gvl")) == 1


def test_chamada_literal_de_create_gvl_com_nome_esperado(tree):
    chamadas = _method_calls(tree, "create_gvl")
    assert len(chamadas) == 1
    argumentos = chamadas[0].args
    assert len(argumentos) == 1
    assert isinstance(argumentos[0], ast.Str)
    assert argumentos[0].s == "GVL_AI_TESTE"


def test_guarda_literal_de_save_as(tree):
    assert len(_guard_calls(tree, "save_as")) == 1


def test_chamada_literal_de_save_as(tree):
    chamadas = _method_calls(tree, "save_as")
    assert len(chamadas) == 1
    # Sem sobrecarga com senha: um argumento so.
    assert len(chamadas[0].args) == 1
    assert not chamadas[0].keywords


# --- adjacencia -------------------------------------------------------------

def _adjacent_statements(tree, guard_operation, mutator_name):
    """Encontra o par (guarda, mutacao) e devolve as duas instrucoes na ordem
    em que aparecem no corpo da funcao que as contem."""
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        index = 0
        while index < len(body) - 1:
            atual, seguinte = body[index], body[index + 1]
            guardas = _guard_calls(atual, guard_operation)
            mutacoes = _method_calls(seguinte, mutator_name)
            if guardas and mutacoes:
                return atual, seguinte
            index = index + 1
    return None, None


def test_guarda_de_create_gvl_e_a_instrucao_imediatamente_anterior(tree):
    guarda, mutacao = _adjacent_statements(tree, "create_gvl", "create_gvl")
    assert guarda is not None, "guarda e create_gvl nao sao instrucoes adjacentes"
    assert mutacao.lineno == guarda.lineno + 1, (
        "ha linha de codigo entre a guarda e a chamada de create_gvl")


def test_guarda_de_save_as_e_a_instrucao_imediatamente_anterior(tree):
    guarda, mutacao = _adjacent_statements(tree, "save_as", "save_as")
    assert guarda is not None, "guarda e save_as nao sao instrucoes adjacentes"
    assert mutacao.lineno == guarda.lineno + 1, (
        "ha linha de codigo entre a guarda e a chamada de save_as")


def test_entre_guarda_e_mutacao_nao_ha_ramo_nem_laco(tree):
    """Redundante com a adjacencia, e de proposito: se alguem inserir um `if`
    de uma linha so, a checagem de lineno sozinha poderia passar."""
    for operacao in ("create_gvl", "save_as"):
        guarda, mutacao = _adjacent_statements(tree, operacao, operacao)
        for node in (guarda, mutacao):
            for filho in ast.walk(node):
                assert not isinstance(filho, (ast.If, ast.For, ast.While,
                                              ast.Try, ast.Lambda)), operacao


# --- o que nao pode existir -------------------------------------------------

@pytest.mark.parametrize("metodo", [
    "save", "replace", "replace_line", "remove", "rename", "move", "build",
    "rebuild", "clean", "import_xml", "import_native", "create_pou",
    "create_program", "create_function", "create_function_block", "create_dut",
    "create_interface", "create_persistentvars", "create_folder", "create_task",
    "set_compilerversion_to_newest", "download_missing_libraries", "Invoke",
])
def test_metodo_mutavel_ausente(tree, metodo):
    assert _method_calls(tree, metodo) == [], (
        "probe 27 nao pode chamar .%s()" % metodo)


@pytest.mark.parametrize("nome", ["getattr", "setattr", "delattr", "eval",
                                  "exec", "compile", "__import__", "vars",
                                  "locals"])
def test_funcao_dinamica_ausente(tree, nome):
    encontrados = [n for n in _calls(tree)
                   if isinstance(n.func, ast.Name) and n.func.id == nome]
    assert encontrados == [], "probe 27 nao pode chamar %s()" % nome


def test_globals_so_para_ler_o_escopo_injetado(tree):
    """`globals()` NAO entra na lista proibida, e a razao e concreta: e por ele
    que se le o global `projects`, injetado pelo ScriptEngine no arquivo
    executado por --runscript. Nao ha outro caminho, e ele nao seleciona
    mutador nenhum.

    O que este teste garante e que o resultado de globals() nunca vira alvo de
    acesso calculado: nada de globals()[nome_variavel]."""
    for node in _calls(tree):
        if isinstance(node.func, ast.Name) and node.func.id == "globals":
            pai_indexado = [
                n for n in ast.walk(tree)
                if isinstance(n, ast.Subscript)
                and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Name)
                and n.value.func.id == "globals"
            ]
            assert pai_indexado == [], "globals()[...] e acesso calculado"


def test_sem_lambda(tree):
    assert [n for n in ast.walk(tree) if isinstance(n, ast.Lambda)] == []


def test_sem_correspondencia_parcial_de_nome(tree):
    """Curinga e prefixo nao se detectam procurando '*' no texto -- '**' e
    negrito de markdown no relatorio. O que importa e que nenhum NOME DE
    OPERACAO seja resolvido por correspondencia parcial.

    `startswith` e permitido em UM lugar so, `path_is_inside`, onde compara
    CAMINHO e nao nome de operacao: conter um diretorio e literalmente uma
    pergunta de prefixo. Fora dali, e proibido.
    """
    parciais = ("startswith", "endswith", "fnmatch", "match", "search",
                "findall", "glob")
    permitido_em = {"startswith": "path_is_inside"}

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for chamada in _calls(node):
            if isinstance(chamada.func, ast.Attribute) \
                    and chamada.func.attr in parciais:
                assert permitido_em.get(chamada.func.attr) == node.name, (
                    "%s() usado em %s()" % (chamada.func.attr, node.name))


def test_sem_tabela_de_despacho_de_mutador(source):
    """Um dict que mapeie nome -> mutador recriaria a selecao dinamica que a
    allowlist existe para impedir."""
    for suspeito in ("DISPATCH", "OPERATION_MAP", "MUTATORS", "HANDLERS"):
        assert suspeito not in source


def test_reflexao_dotnet_ausente(source):
    for suspeito in ("MethodInfo", "GetMethod", "InvokeMember", "clr.Convert"):
        assert suspeito not in source


# --- invariantes de forma ---------------------------------------------------

def test_nome_da_gvl_aparece_como_literal_uma_unica_vez_na_chamada(tree):
    chamadas = _method_calls(tree, "create_gvl")
    assert chamadas[0].args[0].s == "GVL_AI_TESTE"


def test_guarda_nunca_recebe_nome_calculado(tree):
    for node in _calls(tree):
        if isinstance(node.func, ast.Attribute) and node.func.attr == GUARD_NAME:
            assert node.args, "guarda sem argumento"
            assert isinstance(node.args[0], ast.Str), (
                "o nome da operacao tem de ser literal, nunca variavel")


def test_compatibilidade_ironpython_sem_fstring_nem_anotacao(source, tree):
    # f-string se detecta por AST (JoinedStr), nunca por substring: procurar
    # 'f"' no texto casa com o final de '...abcdef":' e acusa falso positivo.
    assert [n for n in ast.walk(tree)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []
    for node in ast.walk(tree):
        assert not isinstance(node, getattr(ast, "AnnAssign", ()))
        if isinstance(node, (ast.FunctionDef,)):
            assert node.returns is None
            for arg in node.args.args:
                assert getattr(arg, "annotation", None) is None


def test_sem_import_de_biblioteca_externa(tree):
    permitidos = set(["hashlib", "json", "os", "sys", "traceback",
                      "__future__", "common", "common.file_io"])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in permitidos, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert node.module.split(".")[0] in permitidos, node.module

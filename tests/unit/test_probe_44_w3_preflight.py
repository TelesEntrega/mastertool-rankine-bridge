"""Testes de `probes/44_preflight_w3_readonly.py` -- leitura das POUs de perfil
para o marco W3 (chamada idiomatica).

Dubles ESTRITOS: qualquer tentativa de escrever levanta. Este probe le, e so.

A regra central que estes testes ancoram: **escrever sem ter lido apagaria o
codigo do fabricante**. `replace` substitui o documento INTEIRO, entao o
preflight que nao consegue ler o texto de destino nao pode aprovar -- e o
postsave que nao encontra o texto original de volta tem de reprovar.
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

PROBE44_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "44_preflight_w3_readonly.py")


def _load(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe44 = _load(PROBE44_PATH, "probe44_w3")

POU_GUID = probe44.POU_TYPE_GUID
TEXTO_USERPRG = "(* codigo do usuario *)\nblSaida := blEntrada;\n"


class EscritaProibida(AssertionError):
    pass


class FakeDocument(object):
    def __init__(self, texto):
        self.text = texto

    def replace(self, *_a, **_k):
        raise EscritaProibida("probe de leitura chamou replace()")


class FakeChildren(object):
    def __init__(self, itens):
        self._itens = list(itens)

    @property
    def Count(self):
        return len(self._itens)

    def __getitem__(self, indice):
        return self._itens[indice]


class FakeNode(object):
    def __init__(self, nome, tipo=POU_GUID, filhos=None, declaracao=None,
                 implementacao=None, tem_decl=None, tem_impl=None):
        self._nome = nome
        self.type = tipo
        self._filhos = list(filhos or [])
        if declaracao is not None:
            self.has_textual_declaration = (True if tem_decl is None
                                            else tem_decl)
            self.textual_declaration = FakeDocument(declaracao)
        elif tem_decl is not None:
            self.has_textual_declaration = tem_decl
        if implementacao is not None:
            self.has_textual_implementation = (True if tem_impl is None
                                               else tem_impl)
            self.textual_implementation = FakeDocument(implementacao)
        elif tem_impl is not None:
            self.has_textual_implementation = tem_impl

    def get_name(self, _recursivo):
        return self._nome

    def get_children(self, _recursivo):
        return FakeChildren(self._filhos)

    def save(self, *_a, **_k):
        raise EscritaProibida("probe de leitura chamou save()")

    def save_as(self, *_a, **_k):
        raise EscritaProibida("probe de leitura chamou save_as()")

    def build(self, *_a, **_k):
        raise EscritaProibida("probe de leitura chamou build()")


def _arvore(userprg_impl=TEXTO_USERPRG, extras=None, userprg_tipo=POU_GUID):
    """A forma medida do `TemplateExemplo v1.project`: SystemPOUs com MainPrg, UserPOUs com
    StartPrg e UserPrg. `ActivePrg` e `NonSkippedPrg` NAO existem."""
    userprg = FakeNode("UserPrg", tipo=userprg_tipo,
                       declaracao="PROGRAM UserPrg\nVAR\nEND_VAR",
                       implementacao=userprg_impl)
    filhos_user = [FakeNode("StartPrg", declaracao="PROGRAM StartPrg",
                            implementacao=";"), userprg]
    filhos_user.extend(extras or [])
    return FakeNode("Application", tipo=probe44.CONTAINER_TYPE_GUID, filhos=[
        FakeNode("SystemPOUs", tipo="pasta", filhos=[
            FakeNode("MainPrg", declaracao="PROGRAM MainPrg",
                     implementacao="StartPrg();\n"),
        ]),
        FakeNode("UserPOUs", tipo="pasta", filhos=filhos_user),
    ])


class FakeProjectAccess(object):
    def __init__(self, projeto):
        self._projeto = projeto

    def get_primary_project(self, _globals):
        if self._projeto is None:
            return None, "projeto indisponivel"
        return self._projeto, None

    def get_project_path(self, _projeto):
        return "C:\\saida\\W3.project"


def _plano(tmp_path, **overrides):
    plano = {
        "schema_version": "1.0",
        "operation_id": "w3-idiomatic-call",
        "phase": "W3_IDIOMATIC_CALL",
        "call_host": "UserPrg",
        "program_name": "PRG_AI_TESTE",
    }
    plano.update(overrides)
    caminho = os.path.join(str(tmp_path), "plano-w3.json")
    io.open(caminho, "w", encoding="utf-8").write(
        json.dumps(plano, ensure_ascii=False))
    return caminho


def _run(tmp_path, modo="preflight", projeto=None, plano_path=None,
         extra_argv=()):
    if projeto is None:
        projeto = _arvore()
    if plano_path is None:
        plano_path = _plano(tmp_path)
    argv = ["probe", "--mode=" + modo, "--plan=" + plano_path,
            "--output=" + os.path.join(str(tmp_path), "art")]
    argv.extend(extra_argv)
    return probe44.run_probe({"projects": object()}, argv,
                             FakeProjectAccess(projeto), file_io, probe_cli)


# =============================================================================
# preflight
# =============================================================================

def test_preflight_acha_userprg_e_le_a_implementacao(tmp_path):
    resultado = _run(tmp_path)
    assert resultado["status"] == probe44.STATUS_PREFLIGHT_VERIFIED
    assert resultado["exit_code"] == 0
    completion = probe44.build_completion(resultado)
    assert completion["call_host_name"] == "UserPrg"
    assert completion["implementation_state"] == "read"
    assert completion["implementation_sha256"] == probe44.sha256_of_text(
        TEXTO_USERPRG)


def test_as_pous_do_perfil_AUSENTES_sao_registradas_e_nao_omitidas(tmp_path):
    """`ActivePrg` e `NonSkippedPrg` nao existem no template. Omiti-las faria a
    lista parecer completa; o aviso do fabricante cita o perfil INTEIRO."""
    resultado = _run(tmp_path)
    completion = probe44.build_completion(resultado)
    assert completion["profile_pous_present"] == ["StartPrg", "UserPrg"]
    assert completion["profile_pous_absent"] == ["ActivePrg", "NonSkippedPrg"]
    nomes = [e["name"] for e in resultado["profile_pous"]]
    assert nomes == list(probe44.PROFILE_POU_NAMES)


def test_nome_certo_com_TIPO_errado_nao_e_a_pou(tmp_path):
    """Nome sozinho nao distingue objeto algum: uma PASTA chamada `UserPrg`
    casaria."""
    projeto = _arvore(userprg_tipo="tipo-de-pasta")
    resultado = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe44.STATUS_HOST_NOT_FOUND
    assert any("type" in nota for nota in resultado["gap_notes"])


def test_pou_de_perfil_duplicada_nao_e_escolhida_por_sorte(tmp_path):
    """Dois objetos com o nome do perfil e o tipo certo: registrar e recusar e
    melhor que escolher e acertar por acaso."""
    duplicada = FakeNode("UserPrg", declaracao="PROGRAM UserPrg",
                         implementacao="(* outra *)")
    projeto = _arvore(extras=[duplicada])
    resultado = _run(tmp_path, projeto=projeto)
    assert any("duplicado" in nota for nota in resultado["gap_notes"])


def test_sem_texto_legivel_o_preflight_NAO_aprova(tmp_path):
    """Escrever sem ter lido apagaria o codigo do fabricante."""
    userprg = FakeNode("UserPrg", declaracao="PROGRAM UserPrg", tem_impl=False)
    projeto = FakeNode("Application", tipo=probe44.CONTAINER_TYPE_GUID,
                       filhos=[FakeNode("UserPOUs", tipo="pasta",
                                        filhos=[userprg])])
    resultado = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe44.STATUS_TEXT_READ_GAP
    assert resultado["exit_code"] != 0


def test_call_host_fora_do_perfil_e_recusado(tmp_path):
    """Pendurar a chamada em qualquer POU derrotaria o proposito do marco."""
    plano = _plano(tmp_path, call_host="MainPrg")
    resultado = _run(tmp_path, plano_path=plano)
    assert resultado["status"] == probe44.STATUS_PRECONDITION_FAILED
    assert any("nao e POU de perfil" in p for p in resultado["problems"])


def test_plano_de_outra_fase_recusado(tmp_path):
    plano = _plano(tmp_path, phase="W1_4_INTEGRATED_BUILD")
    resultado = _run(tmp_path, plano_path=plano)
    assert resultado["status"] == probe44.STATUS_PRECONDITION_FAILED


def test_modo_e_conjunto_fechado(tmp_path):
    resultado = _run(tmp_path, modo="qualquer")
    assert resultado["status"] == probe44.STATUS_PRECONDITION_FAILED
    assert probe44.ALL_MODES == ("preflight", "postsave")


def test_o_destino_dos_artefatos_e_fixado_antes_da_validacao(tmp_path):
    """Achado de W2: um relatorio de erro que so funciona quando o plano esta
    certo nao relata justamente o caso em que ele esta errado."""
    resultado = _run(tmp_path, modo="invalido")
    assert resultado["artifacts_dir"] is not None
    escritos = probe44.write_artifacts(resultado, file_io)
    assert "w3-preflight-completion.json" in escritos


# =============================================================================
# postsave
# =============================================================================

def _postsave(tmp_path, texto_final, original=TEXTO_USERPRG, com_sha=True):
    caminho = os.path.join(str(tmp_path), "original.st")
    io.open(caminho, "w", encoding="utf-8", newline="").write(original)
    extra = ["--original-implementation=" + caminho]
    if com_sha:
        extra.append("--original-implementation-sha256="
                     + probe44.sha256_of_text(original))
    return _run(tmp_path, modo="postsave",
                projeto=_arvore(userprg_impl=texto_final), extra_argv=extra)


def test_postsave_aprova_quando_a_chamada_esta_la_e_o_original_ficou(tmp_path):
    final = TEXTO_USERPRG + "PRG_AI_TESTE();\n"
    resultado = _postsave(tmp_path, final)
    assert resultado["status"] == probe44.STATUS_POSTSAVE_VERIFIED
    assert resultado["exit_code"] == 0


def test_postsave_reprova_se_a_chamada_nao_estiver_la(tmp_path):
    resultado = _postsave(tmp_path, TEXTO_USERPRG)
    assert resultado["status"] == probe44.STATUS_CALL_ABSENT


def test_postsave_reprova_se_o_texto_original_SUMIU(tmp_path):
    """O modo de falha que mais importa: `replace` substitui o documento
    inteiro, e um final que so tem a chamada apagou o codigo do fabricante."""
    resultado = _postsave(tmp_path, "PRG_AI_TESTE();\n")
    assert resultado["status"] == probe44.STATUS_ORIGINAL_TEXT_LOST


def test_postsave_exige_o_texto_original(tmp_path):
    """Sem o texto inicial nao da para provar que ele foi preservado."""
    resultado = _run(tmp_path, modo="postsave",
                     projeto=_arvore(userprg_impl="PRG_AI_TESTE();"))
    assert resultado["status"] == probe44.STATUS_PRECONDITION_FAILED


def test_postsave_recusa_original_que_nao_confere_com_o_sha_do_preflight(
        tmp_path):
    """Um 'original' trocado entre o preflight e o postsave provaria
    preservacao de um texto que nunca esteve la."""
    caminho = os.path.join(str(tmp_path), "original.st")
    io.open(caminho, "w", encoding="utf-8", newline="").write("outra coisa\n")
    resultado = _run(
        tmp_path, modo="postsave",
        projeto=_arvore(userprg_impl=TEXTO_USERPRG + "PRG_AI_TESTE();"),
        extra_argv=["--original-implementation=" + caminho,
                    "--original-implementation-sha256="
                    + probe44.sha256_of_text(TEXTO_USERPRG)])
    assert resultado["status"] == probe44.STATUS_PRECONDITION_FAILED


# =============================================================================
# as regras de texto
# =============================================================================

def test_a_chamada_exige_parenteses_e_ponto_e_virgula():
    """Procurar so pelo nome casaria com um comentario que o citasse -- e
    comentario nao chama nada."""
    assert probe44.contains_call("PRG_AI_TESTE();", "PRG_AI_TESTE")
    assert not probe44.contains_call("(* chama PRG_AI_TESTE *)", "PRG_AI_TESTE")
    assert not probe44.contains_call("PRG_AI_TESTE", "PRG_AI_TESTE")


def test_a_chamada_e_achada_apesar_de_CRLF_e_espaco_ao_fim():
    assert probe44.contains_call("a := 1;\r\nPRG_AI_TESTE();   \r\n",
                                 "PRG_AI_TESTE")


def test_preservacao_ignora_reordenacao_mas_nao_perda():
    original = "linha A\nlinha B\n"
    assert probe44.preserves(original, "linha B\nlinha A\nnova\n")
    assert not probe44.preserves(original, "linha A\n")


def test_preservacao_de_texto_vazio_nao_e_vacua():
    """Original vazio nao pode virar 'preservou tudo' sem sentido -- mas
    tambem nao pode reprovar: um `UserPrg` vazio e um caso real."""
    assert probe44.preserves("", "PRG_AI_TESTE();")
    assert probe44.preserves("\n\n", "qualquer coisa")


def test_o_hash_do_texto_NAO_e_normalizado():
    """Normalizar no hash impediria responder 'o arquivo mudou byte a byte?'.
    A normalizacao e regra de comparacao, e vive em quem compara."""
    assert (probe44.sha256_of_text("a := 1;\n")
            != probe44.sha256_of_text("a := 1;\r\n"))
    assert probe44.normalize("a := 1;\n") == probe44.normalize("a := 1;\r\n")


# =============================================================================
# verificacao estatica -- este arquivo nao escreve
# =============================================================================

@pytest.fixture(scope="module")
def tree44():
    return ast.parse(io.open(PROBE44_PATH, encoding="utf-8").read())


# Nomes que colidem com metodos de `str`/`list` do Python e por isso NAO podem
# ser verificados por busca textual. `text.replace("\r\n", "\n")` e
# `linhas.pop()` sao Python puro; `documento.replace(...)` seria mutacao do
# MasterTool. So o RECEPTOR distingue -- foi essa a licao de W2, onde
# `ScriptPouObjectCollection` HERDA de `list`.
METODOS_QUE_COLIDEM_COM_PYTHON = ("replace", "remove", "add", "insert",
                                  "append", "pop", "update")

# Estes nao colidem com nada do Python: busca textual basta.
METODOS_EXCLUSIVOS_DO_PRODUTO = (".save(", ".save_as(", ".build(",
                                 ".create_program(", ".create_gvl(",
                                 ".create_pou(", ".create_folder(",
                                 ".rename(", ".import_xml(", ".save_archive(")


def test_nenhuma_chamada_exclusiva_do_produto_no_fonte():
    texto = io.open(PROBE44_PATH, encoding="utf-8").read()
    for proibido in METODOS_EXCLUSIVOS_DO_PRODUTO:
        assert proibido not in texto, proibido


def test_os_metodos_que_COLIDEM_com_python_so_aparecem_em_receptor_python(
        tree44):
    """Busca textual daria falso positivo aqui, e deu: `text.replace()` e
    `str.replace`, nao o documento do MasterTool.

    A verificacao e por RECEPTOR. Todo receptor tem de ser uma variavel local
    de texto ou lista deste arquivo -- nunca um proxy do produto.
    """
    RECEPTORES_PYTHON = {"text", "unificado", "texto", "linhas", "achadas",
                         "varredura", "filhos", "pilha", "escritos",
                         "resultado", "problems", "relatorio", "sys.path",
                         "digest",  # hashlib: `digest.update(bloco)`
                         'result["journal"]', 'result["gap_notes"]',
                         'varredura["errors"]'}

    def nome_pontuado(no):
        """`sys.path` vira "sys.path"; `d["k"]` vira 'd["k"]'; `x` vira "x".

        Qualquer outra forma devolve None, e None REPROVA: receptor que nao da
        para nomear nao da para auditar, e um guarda que ignorasse o que nao
        entende seria um guarda que passa justamente no caso estranho.
        """
        if isinstance(no, ast.Name):
            return no.id
        if isinstance(no, ast.Attribute):
            base = nome_pontuado(no.value)
            return None if base is None else "%s.%s" % (base, no.attr)
        if isinstance(no, ast.Subscript):
            base = nome_pontuado(no.value)
            chave = no.slice
            if base is None or not isinstance(chave, ast.Constant):
                return None
            return '%s["%s"]' % (base, chave.value)
        return None

    achados = []
    for no in ast.walk(tree44):
        if not isinstance(no, ast.Call) or not isinstance(no.func,
                                                          ast.Attribute):
            continue
        if no.func.attr not in METODOS_QUE_COLIDEM_COM_PYTHON:
            continue
        receptor = no.func.value
        # Cadeia como `text.replace(...).replace(...)`: o receptor do segundo
        # e a propria chamada anterior, e ja foi conferido nesta varredura.
        if isinstance(receptor, ast.Call):
            continue
        rotulo = nome_pontuado(receptor)
        assert rotulo is not None, ast.dump(no.func)
        achados.append((rotulo, no.func.attr))
        assert rotulo in RECEPTORES_PYTHON, (
            "%s.%s() -- receptor nao e variavel Python conhecida deste arquivo"
            % (rotulo, no.func.attr))
    # Ancora: se a varredura nao encontrasse nada, ela passaria por vacuidade.
    assert achados, "nenhuma chamada colidente encontrada -- guarda vacuo"


def test_nenhum_getattr_dinamico_para_achar_membro(tree44):
    """`getattr` com nome montado esconderia qual membro foi tocado. Os dois
    usos aqui sao com nome vindo de constante LITERAL do modulo."""
    literais = set()
    for node in ast.walk(tree44):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) in (
                "getattr", "hasattr"):
            alvo = node.args[1] if len(node.args) > 1 else None
            # Nome vindo de parametro nomeado da funcao de leitura: aceito,
            # porque quem o chama passa constante literal (verificado abaixo).
            assert isinstance(alvo, (ast.Name, ast.Constant)), ast.dump(alvo)
            if isinstance(alvo, ast.Constant):
                literais.add(alvo.value)
    assert literais == set() or all(isinstance(v, str) for v in literais)


def test_os_membros_de_documento_sao_os_catalogados():
    texto = io.open(PROBE44_PATH, encoding="utf-8").read()
    for membro in ("has_textual_declaration", "textual_declaration",
                   "has_textual_implementation", "textual_implementation"):
        assert membro in texto, membro


def test_identificadores_ascii(tree44):
    for node in ast.walk(tree44):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


def test_vocabulario_de_status_e_fechado():
    assert set(probe44.EXIT_BY_STATUS) == set(probe44.ALL_STATUSES)
    for status in probe44.SUCCESS_STATUSES:
        assert probe44.EXIT_BY_STATUS[status] == 0
    for status in probe44.ALL_STATUSES:
        if status not in probe44.SUCCESS_STATUSES:
            assert probe44.EXIT_BY_STATUS[status] != 0, status


def test_a_lista_de_pous_de_perfil_e_a_do_aviso_do_fabricante():
    """O aviso cita as quatro textualmente. A lista e fechada: um probe que
    aceitasse 'a POU que o plano disser' nao verificaria perfil algum."""
    assert probe44.PROFILE_POU_NAMES == ("StartPrg", "UserPrg", "ActivePrg",
                                         "NonSkippedPrg")
    assert probe44.DEFAULT_CALL_HOST == "UserPrg"


def test_a_completion_e_o_ULTIMO_artefato(tmp_path):
    resultado = _run(tmp_path)
    escritos = probe44.write_artifacts(resultado, file_io)
    assert escritos[-1] == "w3-preflight-completion.json"
    assert set(escritos) == set(probe44.ARTIFACT_NAMES)

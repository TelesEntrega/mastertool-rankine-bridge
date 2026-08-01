"""Testes de `probes/45_author_w3_idiomatic_call.py` -- as DUAS mutacoes de W3.

Dubles ESTRITOS: `create_*`, `add`, `insert`, `remove`, `build` e `save`
levantam. Verificacao estatica por RECEPTOR, e nao por nome de metodo:
`replace` colide com `str.replace` e `add`/`insert`/`remove` colidem com
`list` -- foi assim que W2 quase deixou passar uma chamada em colecao que
HERDA de `list`.

A regra central: **`replace` substitui o documento INTEIRO**. Nao existe
acrescentar. Todo teste aqui gira em torno de que o texto do fabricante
sobrevive.
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

PROBE45_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "45_author_w3_idiomatic_call.py")
PROBE44_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "44_preflight_w3_readonly.py")


def _load(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe45 = _load(PROBE45_PATH, "probe45_w3")
probe44 = _load(PROBE44_PATH, "probe44_w3_para_45")

POU_GUID = probe45.POU_TYPE_GUID
TEXTO_USERPRG = "(* codigo do usuario *)\nblSaida := blEntrada;\n"


class MembroProibido(AssertionError):
    pass


class FakeDocument(object):
    def __init__(self, texto):
        self.text = texto
        self.replaced = []

    def replace(self, novo):
        self.replaced.append(novo)
        self.text = novo
        return True


class FakeChildren(object):
    def __init__(self, itens):
        self._itens = list(itens)

    @property
    def Count(self):
        return len(self._itens)

    def __getitem__(self, indice):
        return self._itens[indice]


class FakeNode(object):
    def __init__(self, nome, tipo=POU_GUID, filhos=None, implementacao=None):
        self._nome = nome
        self.type = tipo
        self._filhos = list(filhos or [])
        if implementacao is not None:
            self.has_textual_implementation = True
            self.textual_implementation = FakeDocument(implementacao)

    def get_name(self, _r):
        return self._nome

    def get_children(self, _r):
        return FakeChildren(self._filhos)

    def create_program(self, *_a, **_k):
        raise MembroProibido("probe de W3 chamou create_program()")

    def create_gvl(self, *_a, **_k):
        raise MembroProibido("probe de W3 chamou create_gvl()")

    def add(self, *_a, **_k):
        raise MembroProibido("probe de W3 chamou add()")

    def insert(self, *_a, **_k):
        raise MembroProibido("probe de W3 chamou insert()")

    def remove(self, *_a, **_k):
        raise MembroProibido("probe de W3 chamou remove()")

    def build(self, *_a, **_k):
        raise MembroProibido("probe de W3 chamou build()")


class FakeProject(FakeNode):
    def __init__(self, filhos, caminho_aberto="C:\\trabalho\\W3-work.project"):
        FakeNode.__init__(self, "projeto", tipo="projeto", filhos=filhos)
        self.path = caminho_aberto
        self.saved_as = []

    def save(self, *_a, **_k):
        raise MembroProibido("probe de W3 chamou save()")

    def save_as(self, caminho):
        self.saved_as.append(caminho)
        handle = io.open(caminho, "w", encoding="utf-8")
        try:
            handle.write("projeto sintetico")
        finally:
            handle.close()
        return True

    def save_archive(self, *_a, **_k):
        raise MembroProibido("probe de W3 chamou save_archive()")


class FakeSafety(object):
    class SafetyError(Exception):
        pass

    def __init__(self, phase="W3_IDIOMATIC_CALL",
                 allowed=("replace", "save_as"), deny=()):
        self.CONTROLLED_WRITE_PHASE = phase
        self.PHASE_ALLOWED_OPERATIONS = {phase: frozenset(allowed)}
        self._allowed = set(allowed)
        self._deny = set(deny)
        self.requested = []

    def assert_controlled_write_allowed(self, operacao):
        self.requested.append(operacao)
        if operacao in self._deny or operacao not in self._allowed:
            raise self.SafetyError("operacao %r nao autorizada" % (operacao,))
        return True


class FakeProjectAccess(object):
    def __init__(self, projeto):
        self._projeto = projeto

    def get_primary_project(self, _g):
        if self._projeto is None:
            return None, "projeto indisponivel"
        return self._projeto, None

    def get_project_path(self, projeto):
        return projeto.path


def _projeto(userprg_impl=TEXTO_USERPRG, extras=None):
    userprg = FakeNode("UserPrg", implementacao=userprg_impl)
    filhos = [FakeNode("StartPrg", implementacao=";"), userprg]
    filhos.extend(extras or [])
    return FakeProject([FakeNode("UserPOUs", tipo="pasta", filhos=filhos)])


def _plano(tmp_path, saida, **overrides):
    plano = {
        "schema_version": "1.0",
        "operation_id": "w3-idiomatic-call",
        "phase": "W3_IDIOMATIC_CALL",
        "call_host": "UserPrg",
        "program_name": "PRG_AI_TESTE",
        "output_project": {"path": saida},
        "operations": [{"kind": "replace"}, {"kind": "save_as"}],
    }
    plano.update(overrides)
    caminho = os.path.join(str(tmp_path), "plano-w3.json")
    io.open(caminho, "w", encoding="utf-8").write(
        json.dumps(plano, ensure_ascii=False))
    return caminho


def _run(tmp_path, projeto=None, safety=None, plano_path=None,
         original=TEXTO_USERPRG, sha_original=None, saida=None):
    if projeto is None:
        projeto = _projeto()
    if saida is None:
        saida = os.path.join(str(tmp_path), "W3-saida.project")
    if plano_path is None:
        plano_path = _plano(tmp_path, saida)
    if safety is None:
        safety = FakeSafety()
    caminho_original = os.path.join(str(tmp_path), "original.st")
    io.open(caminho_original, "w", encoding="utf-8", newline="").write(original)
    if sha_original is None:
        sha_original = probe45.sha256_of_text(original)
    argv = ["probe", "--plan=" + plano_path,
            "--output=" + os.path.join(str(tmp_path), "art"),
            "--original-implementation=" + caminho_original,
            "--original-implementation-sha256=" + sha_original]
    resultado = probe45.run_author({"projects": object()}, argv, safety,
                                   FakeProjectAccess(projeto), file_io,
                                   probe_cli)
    return resultado, projeto, safety


# =============================================================================
# a montagem do texto -- funcao pura
# =============================================================================

def test_a_montagem_preserva_o_original_integralmente():
    final = probe45.compose_implementation(TEXTO_USERPRG, "PRG_AI_TESTE")
    for linha in ("(* codigo do usuario *)", "blSaida := blEntrada;"):
        assert linha in final
    assert "PRG_AI_TESTE();" in final


def test_a_montagem_e_deterministica():
    """Condicao para que W3 possa ser medido como determinista do mesmo jeito
    que W1.4 foi."""
    a = probe45.compose_implementation(TEXTO_USERPRG, "PRG_AI_TESTE")
    b = probe45.compose_implementation(TEXTO_USERPRG, "PRG_AI_TESTE")
    assert a == b


def test_a_montagem_marca_a_origem():
    """Um projeto gerado que nao diz que foi gerado obriga o proximo
    engenheiro a adivinhar."""
    final = probe45.compose_implementation(TEXTO_USERPRG, "PRG_AI_TESTE")
    assert probe45.ORIGIN_COMMENT in final
    assert final.index(probe45.ORIGIN_COMMENT) < final.index("PRG_AI_TESTE();")


def test_a_montagem_sobre_texto_vazio_nao_deixa_linha_solta():
    final = probe45.compose_implementation("", "PRG_AI_TESTE")
    assert not final.startswith("\n")
    assert final.endswith("\n")
    assert final.count("\n\n") == 0


def test_a_montagem_termina_com_UMA_quebra():
    final = probe45.compose_implementation(TEXTO_USERPRG, "PRG_AI_TESTE")
    assert final.endswith("\n")
    assert not final.endswith("\n\n")


def test_a_montagem_recusa_nome_vazio():
    with pytest.raises(ValueError):
        probe45.compose_implementation(TEXTO_USERPRG, "")


def test_o_texto_montado_passa_no_criterio_do_probe_44():
    """Os dois probes rodam em processos separados; se a montagem de um nao
    satisfizesse o criterio do outro, a cadeia so falharia em campo."""
    final = probe45.compose_implementation(TEXTO_USERPRG, "PRG_AI_TESTE")
    assert probe44.contains_call(final, "PRG_AI_TESTE")
    assert probe44.preserves(TEXTO_USERPRG, final)


# =============================================================================
# caminho aprovado
# =============================================================================

def test_duas_mutacoes_exatamente_nesta_ordem(tmp_path):
    resultado, projeto, safety = _run(tmp_path)
    assert resultado["status"] == probe45.STATUS_SAVED_AS
    assert resultado["exit_code"] == 0
    assert safety.requested == ["replace", "save_as"]
    assert resultado["operations_executed"] == ["replace", "save_as"]
    assert len(projeto.saved_as) == 1


def test_o_documento_recebeu_o_texto_montado(tmp_path):
    resultado, projeto, _s = _run(tmp_path)
    userprg = projeto._filhos[0]._filhos[1]
    assert len(userprg.textual_implementation.replaced) == 1
    escrito = userprg.textual_implementation.replaced[0]
    assert escrito == resultado["text"]["final"]
    assert probe44.preserves(TEXTO_USERPRG, escrito)


def test_o_completion_registra_os_dois_hashes(tmp_path):
    resultado, _p, _s = _run(tmp_path)
    completion = probe45.build_completion(resultado)
    assert completion["original_sha256"] == probe45.sha256_of_text(TEXTO_USERPRG)
    assert completion["final_sha256"] != completion["original_sha256"]
    assert completion["no_other_mutator_requested"] is True


# =============================================================================
# recusas
# =============================================================================

def test_texto_que_MUDOU_desde_o_preflight_reprova(tmp_path):
    """Escrever a partir de uma leitura velha apagaria o que mudou no meio."""
    projeto = _projeto(userprg_impl="outro texto, escrito por alguem\n")
    resultado, projeto, safety = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe45.STATUS_TEXT_DRIFTED
    assert safety.requested == []


def test_chamada_ja_presente_nao_e_duplicada(tmp_path):
    texto = TEXTO_USERPRG + "PRG_AI_TESTE();\n"
    resultado, _p, safety = _run(tmp_path, projeto=_projeto(userprg_impl=texto),
                                 original=texto)
    assert resultado["status"] == probe45.STATUS_CALL_ALREADY_PRESENT
    assert safety.requested == []


def test_saida_existente_nunca_e_sobrescrita(tmp_path):
    saida = os.path.join(str(tmp_path), "ja-existe.project")
    io.open(saida, "w", encoding="utf-8").write("conteudo anterior")
    resultado, _p, safety = _run(tmp_path, saida=saida)
    assert resultado["status"] == probe45.STATUS_PRECONDITION_FAILED
    assert safety.requested == []
    assert io.open(saida, encoding="utf-8").read() == "conteudo anterior"


def test_fase_errada_bloqueia_antes_de_qualquer_mutacao(tmp_path):
    safety = FakeSafety(phase="W1_4_INTEGRATED_BUILD")
    resultado, _p, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe45.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


def test_guarda_falsificada_de_replace_reprova(tmp_path):
    safety = FakeSafety(deny=("replace",))
    resultado, projeto, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe45.STATUS_PRECONDITION_FAILED
    assert safety.requested == ["replace"]
    assert projeto.saved_as == []


def test_guarda_falsificada_de_save_as_reprova_depois_do_replace(tmp_path):
    safety = FakeSafety(deny=("save_as",))
    resultado, projeto, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe45.STATUS_PRECONDITION_FAILED
    assert safety.requested == ["replace", "save_as"]
    assert projeto.saved_as == []


def test_call_host_fora_do_perfil_recusado(tmp_path):
    saida = os.path.join(str(tmp_path), "W3-saida.project")
    plano = _plano(tmp_path, saida, call_host="MainPrg")
    resultado, _p, safety = _run(tmp_path, plano_path=plano)
    assert resultado["status"] == probe45.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


def test_pou_duplicada_nao_e_desempatada(tmp_path):
    """Escolher um por ordem de varredura seria acertar por sorte, e a mutacao
    iria para o objeto errado sem ninguem perceber."""
    extra = FakeNode("UserPrg", implementacao="(* outra *)")
    resultado, _p, safety = _run(tmp_path, projeto=_projeto(extras=[extra]))
    assert resultado["status"] == probe45.STATUS_HOST_NOT_FOUND
    assert safety.requested == []


def test_cadeia_do_plano_diferente_recusada(tmp_path):
    saida = os.path.join(str(tmp_path), "W3-saida.project")
    plano = _plano(tmp_path, saida,
                   operations=[{"kind": "replace"}, {"kind": "add"},
                               {"kind": "save_as"}])
    resultado, _p, safety = _run(tmp_path, plano_path=plano)
    assert resultado["status"] == probe45.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


def test_sem_o_texto_do_preflight_nao_roda(tmp_path):
    saida = os.path.join(str(tmp_path), "W3-saida.project")
    plano = _plano(tmp_path, saida)
    argv = ["probe", "--plan=" + plano,
            "--output=" + os.path.join(str(tmp_path), "art")]
    resultado = probe45.run_author({"projects": object()}, argv, FakeSafety(),
                                   FakeProjectAccess(_projeto()), file_io,
                                   probe_cli)
    assert resultado["status"] == probe45.STATUS_PRECONDITION_FAILED


def test_sha_do_texto_entregue_confere(tmp_path):
    resultado, _p, safety = _run(tmp_path, sha_original="0" * 64)
    assert resultado["status"] == probe45.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


# =============================================================================
# verificacao estatica -- por RECEPTOR
# =============================================================================

@pytest.fixture(scope="module")
def tree45():
    return ast.parse(io.open(PROBE45_PATH, encoding="utf-8").read())


def _chamadas_por_receptor(tree, receptores):
    achadas = []
    for no in ast.walk(tree):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            receptor = no.func.value
            if isinstance(receptor, ast.Name) and receptor.id in receptores:
                achadas.append((receptor.id, no.func.attr))
    return achadas


def test_exatamente_uma_chamada_de_replace_no_documento(tree45):
    """Por RECEPTOR: `text.replace()` e `str.replace`, e casaria numa busca
    textual. So `document.replace()` e mutacao."""
    chamadas = [c for c in _chamadas_por_receptor(tree45, ("document",))]
    assert chamadas == [("document", "replace")], chamadas


def test_exatamente_uma_chamada_de_save_as_no_projeto(tree45):
    chamadas = _chamadas_por_receptor(tree45, ("project",))
    assert chamadas == [("project", "save_as")], chamadas


def test_o_projeto_nunca_recebe_save_nem_outro_mutador(tree45):
    for receptor, metodo in _chamadas_por_receptor(tree45, ("project",)):
        assert metodo == "save_as", "%s.%s()" % (receptor, metodo)


def test_a_guarda_e_a_linha_IMEDIATAMENTE_anterior(tree45):
    """Um log, um `if` ou um wrapper entre a guarda e a chamada abririam espaco
    para a chamada acontecer sem a guarda."""
    tree = ast.parse(io.open(PROBE45_PATH, encoding="utf-8").read())
    for nome, receptor_esperado, metodo_esperado in (
            ("replace_guarded", "document", "replace"),
            ("save_as_guarded", "project", "save_as")):
        funcao = [n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == nome]
        assert len(funcao) == 1, nome
        # A docstring sai; o resto TEM de ser exatamente tres nos.
        corpo = [n for n in funcao[0].body
                 if not (isinstance(n, ast.Expr)
                         and isinstance(getattr(n, "value", None),
                                        ast.Constant))]
        assert len(corpo) == 3, [ast.dump(n) for n in corpo]
        guarda, chamada, retorno = corpo

        assert isinstance(guarda, ast.Expr)
        assert isinstance(guarda.value, ast.Call)
        assert guarda.value.func.attr == "assert_controlled_write_allowed"
        # A guarda pede EXATAMENTE a operacao que a linha seguinte executa.
        # Guardar `replace` e chamar `save_as` passaria por qualquer teste que
        # so contasse linhas.
        assert guarda.value.args[0].value == metodo_esperado

        assert isinstance(chamada, ast.Expr)
        assert isinstance(chamada.value, ast.Call)
        assert isinstance(chamada.value.func, ast.Attribute)
        assert chamada.value.func.value.id == receptor_esperado
        assert chamada.value.func.attr == metodo_esperado

        assert isinstance(retorno, ast.Return)


def test_nenhum_criador_nem_outro_mutavel_no_fonte():
    texto = io.open(PROBE45_PATH, encoding="utf-8").read()
    for proibido in (".create_program(", ".create_gvl(", ".create_pou(",
                     ".create_dut(", ".create_folder(", ".build(",
                     ".save_archive(", ".rename(", ".import_xml(",
                     ".download_missing_libraries("):
        assert proibido not in texto, proibido
    # `.save(` exige cuidado: `.save_as(` o contem como prefixo.
    assert ".save(" not in texto


def test_os_metodos_de_lista_nao_aparecem_em_receptor_do_produto(tree45):
    """`add`, `insert`, `remove` e `append` colidem com `list`. Foi essa
    colisao que quase deixou passar uma chamada em W2, numa colecao que HERDA
    de `list`."""
    RECEPTORES_PYTHON = {"partes", "linhas", "filhos", "pilha", "erros",
                         "escritos", "problems", "achadas"}
    for no in ast.walk(tree45):
        if not isinstance(no, ast.Call) or not isinstance(no.func,
                                                          ast.Attribute):
            continue
        if no.func.attr not in ("add", "insert", "remove", "append", "pop"):
            continue
        receptor = no.func.value
        if isinstance(receptor, ast.Subscript):
            base = receptor.value
            assert isinstance(base, ast.Name) and base.id in ("result",), \
                ast.dump(no.func)
            continue
        if isinstance(receptor, ast.Attribute):
            # `sys.path.insert(...)`: Python puro, e o unico receptor pontuado
            # aceito. Qualquer outro reprova.
            assert (isinstance(receptor.value, ast.Name)
                    and receptor.value.id == "sys"
                    and receptor.attr == "path"), ast.dump(no.func)
            continue
        assert isinstance(receptor, ast.Name), ast.dump(no.func)
        assert receptor.id in RECEPTORES_PYTHON, "%s.%s()" % (receptor.id,
                                                              no.func.attr)


def test_as_constantes_duplicadas_conferem_com_o_probe_44():
    """Os dois arquivos rodam em processos separados e por isso repetem as
    constantes. A duplicacao e legitima; divergir em silencio nao e."""
    assert probe45.PROFILE_POU_NAMES == probe44.PROFILE_POU_NAMES
    assert probe45.POU_TYPE_GUID == probe44.POU_TYPE_GUID
    assert probe45.EXPECTED_PHASE == probe44.EXPECTED_PHASE
    assert probe45.EXPECTED_OPERATION_ID == probe44.EXPECTED_OPERATION_ID
    assert probe45.normalize("a\r\n") == probe44.normalize("a\n")


def test_vocabulario_de_status_fechado():
    assert set(probe45.EXIT_BY_STATUS) == set(probe45.ALL_STATUSES)
    assert probe45.EXIT_BY_STATUS[probe45.STATUS_SAVED_AS] == 0
    for status in probe45.ALL_STATUSES:
        if status not in probe45.SUCCESS_STATUSES:
            assert probe45.EXIT_BY_STATUS[status] != 0, status


def test_identificadores_ascii(tree45):
    for no in ast.walk(tree45):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(no, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


def test_completion_e_o_ultimo_artefato(tmp_path):
    resultado, _p, _s = _run(tmp_path)
    escritos = probe45.write_artifacts(resultado, file_io)
    assert escritos[-1] == "w3-completion.json"
    assert set(escritos) == set(probe45.ARTIFACT_NAMES)

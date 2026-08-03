"""Testes de `probes/47_verify_factory_output_readonly.py`.

Ele responde o que o EXECUTOR nao pode responder: o executor sabe o que
escreveu, e nao o que ficou no arquivo. Este probe reabre a saida e le do
disco.

Duble ESTRITO: qualquer escrita levanta.
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
if os.path.join(_REPO_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from common import file_io, probe_cli  # noqa: E402
from mastertool_bridge.planner.planner import build_authoring_plan  # noqa: E402

PROBE47_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "47_verify_factory_output_readonly.py")


def _load(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe47 = _load(PROBE47_PATH, "probe47_verify")

ST_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"
POU_GUID = probe47.POU_TYPE_GUID
GVL_GUID = probe47.GVL_TYPE_GUID


class EscritaProibida(AssertionError):
    pass


class FakeDocument(object):
    def __init__(self, texto):
        self.text = texto

    def replace(self, *_a, **_k):
        raise EscritaProibida("verificador chamou replace()")


class FakeChildren(object):
    def __init__(self, itens):
        self._itens = list(itens)

    @property
    def Count(self):
        return len(self._itens)

    def __getitem__(self, indice):
        return self._itens[indice]


class FakeNode(object):
    def __init__(self, nome, tipo, filhos=None, declaracao=None,
                 implementacao=None, guid="guid-fixo"):
        self._nome = nome
        self.type = tipo
        self.guid = guid
        self._filhos = list(filhos or [])
        if declaracao is not None:
            self.has_textual_declaration = True
            self.textual_declaration = FakeDocument(declaracao)
        if implementacao is not None:
            self.has_textual_implementation = True
            self.textual_implementation = FakeDocument(implementacao)

    def get_name(self, _r):
        return self._nome

    def get_children(self, _r):
        return FakeChildren(self._filhos)

    def save(self, *_a, **_k):
        raise EscritaProibida("verificador chamou save()")

    def save_as(self, *_a, **_k):
        raise EscritaProibida("verificador chamou save_as()")

    def build(self, *_a, **_k):
        raise EscritaProibida("verificador chamou build()")

    def create_gvl(self, *_a, **_k):
        raise EscritaProibida("verificador chamou create_gvl()")


class FakeProjectAccess(object):
    def __init__(self, projeto, caminho=None):
        self._projeto = projeto
        self._caminho = caminho

    def get_primary_project(self, _g):
        if self._projeto is None:
            return None, "projeto indisponivel"
        return self._projeto, None

    def get_project_path(self, _p):
        return self._caminho


def _spec():
    return {
        "schema_version": 1,
        "template": {"id": "TemplateExemplo_v1", "sha256": "5966257" + "0" * 57},
        "gvls": [{"name": "GVL_V", "declaration": "VAR_GLOBAL\nEND_VAR"}],
        "programs": [{"name": "PRG_V", "language": {"guid": ST_GUID},
                      "declaration": "PROGRAM PRG_V\nVAR\nEND_VAR",
                      "implementation": "xA := TRUE;"}],
        "tasks": [{"name": "MainTask", "existing": True,
                   "program_calls": ["PRG_V"]}],
    }


def _arvore(gvl_decl=None, prg_decl=None, prg_impl=None, gvl_tipo=GVL_GUID):
    spec = _spec()
    gvl = FakeNode("GVL_V", gvl_tipo, guid="g-gvl",
                   declaracao=(spec["gvls"][0]["declaration"]
                               if gvl_decl is None else gvl_decl))
    prg = FakeNode("PRG_V", POU_GUID, guid="g-prg",
                   declaracao=(spec["programs"][0]["declaration"]
                               if prg_decl is None else prg_decl),
                   implementacao=(spec["programs"][0]["implementation"]
                                  if prg_impl is None else prg_impl))
    app = FakeNode("Application", "app", guid="g-app", filhos=[gvl, prg])
    plc = FakeNode("Plc Logic", "plc", guid="g-plc", filhos=[app])
    dev = FakeNode("Device", "dev", guid="g-dev", filhos=[plc])
    return FakeNode("projeto", "projeto", guid="g-raiz", filhos=[dev])


@pytest.fixture()
def sem_catalogo_de_dut():
    """Remove `duts` do mapa de tipos, para exercitar o caminho de familia NAO
    catalogada.

    Hoje TODAS as familias tem `type_guid` -- o de DUT foi medido na run-032. O
    mecanismo continua testado porque a proxima familia nova cai nele, e
    descobrir isso quebrado so na hora seria tarde."""
    original = dict(probe47.FAMILY_TYPE_GUID)
    probe47.FAMILY_TYPE_GUID.pop("duts", None)
    yield
    probe47.FAMILY_TYPE_GUID.clear()
    probe47.FAMILY_TYPE_GUID.update(original)


def _run(tmp_path, projeto=None, spec=None, sha_declarado=None,
         caminho_projeto=None, plano_pronto=None):
    if spec is None:
        spec = _spec()
    if projeto is None:
        projeto = _arvore()
    plano = plano_pronto if plano_pronto is not None         else build_authoring_plan(spec).plan
    caminho_plano = os.path.join(str(tmp_path), "plano.json")
    io.open(caminho_plano, "w", encoding="utf-8").write(
        json.dumps(plano, ensure_ascii=False))
    argv = ["probe", "--plan=" + caminho_plano,
            "--output=" + os.path.join(str(tmp_path), "art")]
    if sha_declarado:
        argv.append("--output-sha256=" + sha_declarado)
    return probe47.run_verify({"projects": object()}, argv,
                              FakeProjectAccess(projeto, caminho_projeto),
                              file_io, probe_cli)


# =============================================================================
# caminho aprovado
# =============================================================================

def test_verifica_objetos_e_textos_relidos(tmp_path):
    resultado = _run(tmp_path)
    assert resultado["status"] == probe47.STATUS_VERIFIED, resultado["problems"]
    assert resultado["exit_code"] == 0
    completion = probe47.build_completion(resultado)
    assert completion["objects_total"] == 2
    assert completion["objects_verified"] == 2
    assert completion["objects_by_outcome"] == ["verified"]


def test_a_arvore_inteira_e_achatada_com_os_campos_da_comparacao(tmp_path):
    """Os campos sao os MESMOS que `generation_equivalence` compara -- se
    divergirem, a comparacao entre duas execucoes vira uma lista de `None`s
    que casa com qualquer coisa."""
    from mastertool_bridge.automation.generation_equivalence import (
        NODE_SIGNATURE_FIELDS, missing_node_fields)
    resultado = _run(tmp_path)
    nos = resultado["nodes"]
    assert len(nos) == 6
    assert missing_node_fields(nos) == []
    for campo in NODE_SIGNATURE_FIELDS:
        assert campo in nos[0], campo
    assert "object_guid" in nos[0]


def test_o_texto_e_conferido_contra_o_hash_do_PLANO(tmp_path):
    """A fonte e o plano, e nao a spec: o plano passou pela validacao e tem
    hash proprio. Conferir contra a spec mediria a spec contra ela mesma."""
    resultado = _run(tmp_path, projeto=_arvore(prg_impl="xA := FALSE;"))
    assert resultado["status"] == probe47.STATUS_TEXT_MISMATCH
    prg = [o for o in resultado["objects"] if o["name"] == "PRG_V"][0]
    impl = [t for t in prg["texts"] if t["field"] == "implementation"][0]
    assert impl["outcome"] == "mismatch"
    assert impl["sha256_expected"] != impl["sha256_observed"]


def test_objeto_ausente_reprova(tmp_path):
    projeto = _arvore()
    app = projeto._filhos[0]._filhos[0]._filhos[0]
    app._filhos = [n for n in app._filhos if n._nome != "GVL_V"]
    resultado = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe47.STATUS_OBJECT_MISSING


def test_tipo_errado_conta_como_ausente_e_nao_como_encontrado(tmp_path):
    """Nome sozinho nao distingue objeto algum -- uma pasta chamada `GVL_V`
    casaria."""
    resultado = _run(tmp_path, projeto=_arvore(gvl_tipo="tipo-de-pasta"))
    assert resultado["status"] == probe47.STATUS_OBJECT_MISSING


def test_texto_ilegivel_e_LACUNA_e_nao_divergencia(tmp_path):
    """Nao conseguir ler nao e o mesmo que ler e achar diferente: uma pede
    investigar o instrumento, a outra pede investigar o projeto."""
    projeto = _arvore()
    app = projeto._filhos[0]._filhos[0]._filhos[0]
    prg = [n for n in app._filhos if n._nome == "PRG_V"][0]
    prg.has_textual_implementation = False
    resultado = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe47.STATUS_TEXT_UNREADABLE
    assert resultado["exit_code"] == 4


def test_o_hash_da_saida_e_conferido_contra_o_que_o_host_declarou(tmp_path):
    """Sem isso o probe poderia estar lendo outro arquivo e afirmando sobre
    ele."""
    alvo = os.path.join(str(tmp_path), "saida.project")
    io.open(alvo, "w", encoding="utf-8").write("conteudo")
    resultado = _run(tmp_path, sha_declarado="0" * 64, caminho_projeto=alvo)
    assert resultado["status"] == probe47.STATUS_PRECONDITION_FAILED
    assert "nao e o que o host declarou" in " ".join(resultado["problems"])


def test_plano_sem_text_hashes_nao_tem_o_que_verificar(tmp_path):
    spec = _spec()
    plano = build_authoring_plan(spec).plan
    plano["text_hashes"] = {}
    caminho = os.path.join(str(tmp_path), "p.json")
    io.open(caminho, "w", encoding="utf-8").write(json.dumps(plano))
    resultado = probe47.run_verify(
        {"projects": object()},
        ["probe", "--plan=" + caminho,
         "--output=" + os.path.join(str(tmp_path), "a")],
        FakeProjectAccess(_arvore()), file_io, probe_cli)
    assert resultado["status"] == probe47.STATUS_PRECONDITION_FAILED


def test_a_completion_e_o_ultimo_artefato(tmp_path):
    resultado = _run(tmp_path)
    escritos = probe47.write_artifacts(resultado, file_io)
    assert escritos[-1] == "factory-verify-completion.json"
    assert set(escritos) == set(probe47.ARTIFACT_NAMES)


# =============================================================================
# verificacao estatica -- ele NAO escreve
# =============================================================================

@pytest.fixture(scope="module")
def tree47():
    return ast.parse(io.open(PROBE47_PATH, encoding="utf-8").read())


def test_nenhuma_chamada_exclusiva_do_produto_no_fonte():
    texto = io.open(PROBE47_PATH, encoding="utf-8").read()
    for proibido in (".save(", ".save_as(", ".build(", ".create_gvl(",
                     ".create_program(", ".create_function(", ".rename(",
                     ".import_xml(", ".save_archive("):
        assert proibido not in texto, proibido


def test_os_metodos_que_colidem_com_python_tem_receptor_python(tree47):
    """`replace`, `add`, `remove`, `insert`, `append` e `pop` colidem com
    `str`/`list`. So o RECEPTOR distingue."""
    receptores_python = {"texto", "unificado", "linhas", "filhos", "pilha",
                         "nos", "escritos", "problems", "saida", "sys.path",
                         "entrada", "digest", "esperado", "ilegiveis"}
    for no in ast.walk(tree47):
        if not isinstance(no, ast.Call) or not isinstance(no.func,
                                                          ast.Attribute):
            continue
        if no.func.attr not in ("replace", "add", "remove", "insert",
                                "append", "pop", "update"):
            continue
        receptor = no.func.value
        if isinstance(receptor, ast.Call):
            continue
        if isinstance(receptor, ast.Attribute):
            assert (isinstance(receptor.value, ast.Name)
                    and receptor.value.id == "sys"), ast.dump(no.func)
            continue
        if isinstance(receptor, ast.Subscript):
            continue
        assert isinstance(receptor, ast.Name), ast.dump(no.func)
        assert receptor.id in receptores_python, "%s.%s()" % (receptor.id,
                                                              no.func.attr)


def test_vocabulario_de_status_fechado():
    assert set(probe47.EXIT_BY_STATUS) == set(probe47.ALL_STATUSES)
    assert probe47.EXIT_BY_STATUS[probe47.STATUS_VERIFIED] == 0
    for status in probe47.ALL_STATUSES:
        if status not in probe47.SUCCESS_STATUSES:
            assert probe47.EXIT_BY_STATUS[status] != 0, status


def test_identificadores_ascii(tree47):
    for no in ast.walk(tree47):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(no, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


def test_o_type_guid_NAO_distingue_program_de_fb_de_function():
    """Limite declarado, e nao afirmacao: docs/35 secao 4 mediu que as tres
    familias compartilham o mesmo `type_guid`. O verificador consegue dizer "e
    uma POU", nunca "e um FUNCTION_BLOCK"."""
    tipos = {familia: probe47.FAMILY_TYPE_GUID[familia]
             for familia in ("programs", "function_blocks", "functions")}
    assert len(set(tipos.values())) == 1
    assert probe47.FAMILY_TYPE_GUID["gvls"] != probe47.POU_TYPE_GUID


# =============================================================================
# familia sem type_guid catalogado -- o fail-open da run-032
# =============================================================================

def _spec_com_dut():
    spec = _spec()
    spec["duts"] = [{
        "name": "ST_EIXO", "kind": "STRUCT",
        "declaration": "TYPE ST_EIXO :\nSTRUCT\n rP : REAL;\nEND_STRUCT\nEND_TYPE"}]
    return spec


def _arvore_com_dut(dut_tipo=None):
    spec = _spec_com_dut()
    gvl = FakeNode("GVL_V", GVL_GUID, guid="g-gvl",
                   declaracao=spec["gvls"][0]["declaration"])
    prg = FakeNode("PRG_V", POU_GUID, guid="g-prg",
                   declaracao=spec["programs"][0]["declaration"],
                   implementacao=spec["programs"][0]["implementation"])
    dut = FakeNode("ST_EIXO", dut_tipo or probe47.DUT_TYPE_GUID, guid="g-dut",
                   declaracao=spec["duts"][0]["declaration"])
    app = FakeNode("Application", "app", guid="g-app", filhos=[gvl, prg, dut])
    plc = FakeNode("Plc Logic", "plc", guid="g-plc", filhos=[app])
    dev = FakeNode("Device", "dev", guid="g-dev", filhos=[plc])
    return FakeNode("projeto", "projeto", guid="g-raiz", filhos=[dev])


def test_familia_sem_type_guid_BLOQUEIA_o_veredito(tmp_path,
                                                   sem_catalogo_de_dut):
    """O fail-open medido na run-032: a saida dizia `factory_output_verified`
    com "1 de 3 verificados". Um objeto que ninguem conseguiu verificar nao pode
    sair como verificado."""
    resultado = _run(tmp_path, projeto=_arvore_com_dut(), spec=_spec_com_dut())
    assert resultado["status"] == probe47.STATUS_FAMILY_NOT_VERIFIABLE
    assert resultado["exit_code"] != 0
    completion = probe47.build_completion(resultado)
    assert "unknown_family" in completion["objects_by_outcome"]
    assert completion["objects_verified"] < completion["objects_total"]


def test_o_type_guid_observado_e_MEDIDO_para_a_lacuna_ser_fechavel(
        tmp_path, sem_catalogo_de_dut):
    """Medir nao e verificar: o `outcome` continua bloqueando, e o tipo
    observado vira dado para fechar o catalogo depois."""
    resultado = _run(tmp_path, projeto=_arvore_com_dut(dut_tipo="tipo-medido"),
                     spec=_spec_com_dut())
    dut = [o for o in resultado["objects"] if o["name"] == "ST_EIXO"][0]
    assert dut["outcome"] == "unknown_family"
    assert dut["type_guid_observed"] == "tipo-medido"
    # E foi exatamente assim que o `type_guid` de DUT entrou no catalogo: a
    # run-032 mediu `2db5746d-...` por este caminho.
    assert any("type_guid observado" in n for n in resultado["gap_notes"])


def test_a_busca_SO_POR_NOME_nao_e_usada_para_verificar(tmp_path,
                                                        sem_catalogo_de_dut):
    """Achar por nome nao distingue objeto algum. Ela alimenta uma nota de
    medicao, e nunca um veredito -- por isso o objeto continua nao verificado
    mesmo tendo sido achado."""
    resultado = _run(tmp_path, projeto=_arvore_com_dut(), spec=_spec_com_dut())
    dut = [o for o in resultado["objects"] if o["name"] == "ST_EIXO"][0]
    assert dut["type_guid_observed"] is not None
    assert dut["outcome"] != "verified"


def test_unknown_family_tem_precedencia_sobre_as_outras_falhas(
        tmp_path, sem_catalogo_de_dut):
    """"Nao consegui verificar" e mais grave que "verifiquei e diverge": a
    segunda ao menos foi medida."""
    projeto = _arvore_com_dut()
    app = projeto._filhos[0]._filhos[0]._filhos[0]
    prg = [n for n in app._filhos if n._nome == "PRG_V"][0]
    prg.textual_implementation.text = "outro texto"
    resultado = _run(tmp_path, projeto=projeto, spec=_spec_com_dut())
    assert resultado["status"] == probe47.STATUS_FAMILY_NOT_VERIFIABLE


def test_family_not_verifiable_esta_no_vocabulario_e_nao_e_sucesso():
    assert (probe47.STATUS_FAMILY_NOT_VERIFIABLE in probe47.ALL_STATUSES)
    assert (probe47.STATUS_FAMILY_NOT_VERIFIABLE
            not in probe47.SUCCESS_STATUSES)
    assert probe47.EXIT_BY_STATUS[probe47.STATUS_FAMILY_NOT_VERIFIABLE] != 0


def test_o_type_guid_de_dut_esta_catalogado_e_e_o_mesmo_para_os_subtipos():
    """Medido na run-032 (docs/46): `ST_EIXO` (STRUCT) e `EN_ESTADO` (ENUM)
    nasceram com o MESMO `type_guid`. O tipo nao distingue subtipo, igual ao
    que docs/35 secao 4 ja registrava para as familias de POU -- entao o
    verificador consegue dizer "e um DUT", nunca "e um STRUCT"."""
    assert probe47.FAMILY_TYPE_GUID["duts"] == probe47.DUT_TYPE_GUID
    assert probe47.DUT_TYPE_GUID not in (probe47.POU_TYPE_GUID,
                                         probe47.GVL_TYPE_GUID)


# =============================================================================
# chaves de `text_hashes`: criação e ALTERAÇÃO (fase R2)
# =============================================================================

def _hashes(**por_chave):
    return {"text_hashes": {c: {"raw_sha256": v}
                            for c, v in por_chave.items()}}


def test_chave_de_criacao_continua_lida():
    esperado, ilegiveis = probe47.expected_texts(
        _hashes(**{"gvls:GVL_A:declaration": "a" * 64}))
    assert esperado == {("gvls", "GVL_A", "declaration"): "a" * 64}
    assert ilegiveis == []


def test_chave_de_ALTERACAO_e_lida_como_o_mesmo_alvo():
    """`modify:` diz de onde o objeto veio, não o que conferir. A procedência
    já foi verificada antes, no `expected_before` do passo (probe 46)."""
    esperado, ilegiveis = probe47.expected_texts(
        _hashes(**{"modify:programs:UserPrg:implementation": "b" * 64}))
    assert esperado == {("programs", "UserPrg", "implementation"): "b" * 64}
    assert ilegiveis == []


def test_criacao_e_alteracao_no_MESMO_plano_convivem():
    esperado, ilegiveis = probe47.expected_texts(_hashes(**{
        "gvls:GVL_A:declaration": "a" * 64,
        "modify:programs:UserPrg:implementation": "b" * 64}))
    assert len(esperado) == 2
    assert ilegiveis == []


@pytest.mark.parametrize("chave", ["so_um_pedaco", "a:b", "a:b:c:d",
                                   "rename:a:b:c", "modify:a:b",
                                   "modify:a:b:c:d", ":b:c", "a::c",
                                   "modify::b:c"])
def test_chave_que_o_verificador_NAO_sabe_ler_sai_na_lista_de_ilegiveis(chave):
    """O `continue` mudo que estava aqui era o defeito: um plano com uma
    criação e uma alteração conferiria só a criação e sairia VERDE, com
    metade medida. Chave ilegível não é chave ausente."""
    esperado, ilegiveis = probe47.expected_texts(_hashes(**{chave: "c" * 64}))
    assert esperado == {}
    assert ilegiveis == [chave]


def test_hash_ausente_tambem_e_ilegivel():
    """Entrada sem `raw_sha256` não tem contra o que conferir. Aceitá-la
    faria o objeto entrar no conjunto verificado comparando contra `None`."""
    esperado, ilegiveis = probe47.expected_texts(
        {"text_hashes": {"gvls:G:declaration": {"normalized_sha256": "x"}}})
    assert esperado == {}
    assert ilegiveis == ["gvls:G:declaration"]


def test_ilegivel_bloqueia_a_verificacao_inteira(tmp_path):
    """E bloqueia com mensagem PRÓPRIA: "não sei ler estas chaves" manda o
    operador a um lugar diferente de "o plano não pediu texto nenhum"."""
    dados = dict(build_authoring_plan(_spec()).plan)
    dados["text_hashes"] = {"nao:sei:ler:isto": {"raw_sha256": "d" * 64}}
    resultado = _run(tmp_path, plano_pronto=dados)
    assert resultado["status"] == probe47.STATUS_PRECONDITION_FAILED
    assert any("nao sabe ler" in p for p in resultado["problems"])

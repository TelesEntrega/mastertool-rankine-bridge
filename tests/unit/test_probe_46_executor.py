"""Testes de `probes/46_execute_authoring_plan.py` -- o EXECUTOR.

Este arquivo protege a propriedade que separa um executor de um interpretador
solto: **o plano decide O QUE, e nunca COMO**. O executor tem um ramo literal
por operacao; texto so entra se o hash do plano o autorizar; operacao fora do
vocabulario reprova antes da primeira mutacao.

Dubles ESTRITOS: `add`, `insert`, `remove`, `save`, `rebuild` e `create_dut`
levantam se tocados.
"""

import ast
import hashlib
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
from mastertool_bridge.planner.planner import (  # noqa: E402
    EXECUTOR_CONTRACT,
    PLAN_OPERATIONS,
    build_authoring_plan,
)

PROBE46_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "46_execute_authoring_plan.py")


def _load(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe46 = _load(PROBE46_PATH, "probe46_executor")

ST_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"
POU_GUID = probe46.POU_TYPE_GUID
GVL_GUID = probe46.GVL_TYPE_GUID
CONTAINER_GUID = probe46.EXPECTED_CONTAINER_TYPE_GUID


class MembroProibido(AssertionError):
    pass


class FakeDocument(object):
    def __init__(self, texto=""):
        self.text = texto
        self.replaced = []

    def replace(self, novo):
        self.replaced.append(novo)
        self.text = novo
        return True

    def insert(self, *_a, **_k):
        raise MembroProibido("executor chamou insert() em documento")

    def append(self, *_a, **_k):
        raise MembroProibido("executor chamou append() em documento")


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
                 implementacao=None):
        self._nome = nome
        self.type = tipo
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

    def add(self, *_a, **_k):
        raise MembroProibido("executor chamou add() -- o caminho de W2")

    def insert(self, *_a, **_k):
        raise MembroProibido("executor chamou insert()")

    def remove(self, *_a, **_k):
        raise MembroProibido("executor chamou remove()")

    def rename(self, *_a, **_k):
        raise MembroProibido("executor chamou rename()")


class FakeContainer(FakeNode):
    """A `Application`. Registra o que foi criado, na ordem."""

    def __init__(self, filhos=None):
        FakeNode.__init__(self, "Application", CONTAINER_GUID, filhos=filhos)
        self.created = []

    def create_gvl(self, nome):
        self.created.append(("create_gvl", nome))
        novo = FakeNode(nome, GVL_GUID, declaracao="")
        self._filhos.append(novo)
        return novo

    def create_program(self, nome, language_guid):
        # O binding real exige `System.Guid`; o duble exige que NAO seja `str`,
        # que e o erro medido na run-005.
        if isinstance(language_guid, str):
            raise TypeError("expected Nullable[Guid], got str")
        self.created.append(("create_program", nome, str(language_guid)))
        novo = FakeNode(nome, POU_GUID, declaracao="", implementacao="")
        self._filhos.append(novo)
        return novo

    def create_function_block(self, nome, language_guid):
        # Assinatura medida em W1.5: `create_function_block(name, language?)`,
        # SEM `base_type` nem `interfaces`. Um argumento a mais aqui denunciaria
        # o executor tendo escolhido valor para parametro que ninguem mediu.
        if isinstance(language_guid, str):
            raise TypeError("expected Nullable[Guid], got str")
        self.created.append(("create_function_block", nome, str(language_guid)))
        novo = FakeNode(nome, POU_GUID, declaracao="", implementacao="")
        self._filhos.append(novo)
        return novo

    def create_dut(self, nome, dut_type):
        # Assinatura catalogada: `create_dut(name, type, baseType=None)`.
        # `baseType` OMITIDO -- obrigatorio so para `Alias`, que este executor
        # nao emite. Um terceiro argumento aqui denunciaria o executor tendo
        # escolhido valor para parametro que ninguem mediu.
        if not isinstance(dut_type, str) or not dut_type.startswith("DutType."):
            raise TypeError("expected DutType, got %r" % (dut_type,))
        self.created.append(("create_dut", nome, dut_type))
        novo = FakeNode(nome, "dut", declaracao="")
        self._filhos.append(novo)
        return novo

    def create_function(self, nome, return_type, language_guid):
        # `return_type` e POSICIONAL e vem antes da linguagem -- assinatura
        # catalogada em docs/27 secao 7 e exercida em W1.5.
        if isinstance(language_guid, str):
            raise TypeError("expected Nullable[Guid], got str")
        if not isinstance(return_type, str) or not return_type:
            raise TypeError("return_type obrigatorio, recebido %r" % (return_type,))
        self.created.append(("create_function", nome, return_type,
                             str(language_guid)))
        novo = FakeNode(nome, POU_GUID, declaracao="", implementacao="")
        self._filhos.append(novo)
        return novo


class FakeGuid(object):
    """`System.Guid` sintetico -- so precisa NAO ser `str`."""

    def __init__(self, texto):
        self._texto = texto

    def __str__(self):
        return self._texto


class FakeProject(FakeNode):
    def __init__(self, filhos, caminho="C:\\trabalho\\W4-work.project"):
        FakeNode.__init__(self, "projeto", "projeto", filhos=filhos)
        self.path = caminho
        self.saved_as = []

    def save(self, *_a, **_k):
        raise MembroProibido("executor chamou save()")

    def save_as(self, caminho):
        self.saved_as.append(caminho)
        io.open(caminho, "w", encoding="utf-8").write("projeto sintetico")
        return True

    def save_archive(self, *_a, **_k):
        raise MembroProibido("executor chamou save_archive()")


class FakeSafety(object):
    class SafetyError(Exception):
        pass

    def __init__(self, phase="W4_EXECUTE_PLAN",
                 allowed=("create_gvl", "create_program", "replace", "save_as",
                          "build"),
                 deny=()):
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

    def assert_controlled_property_write_allowed(self, escrita):
        """A porta separada do gate real. Ela e OUTRA funcao aqui tambem, e nao
        um apelido: um teste que chamasse a de metodos por engano passaria sem
        exercer a verificacao que existe para a atribuicao."""
        self.requested.append(escrita)
        if not escrita.startswith("set:"):
            raise self.SafetyError(
                "escrita de propriedade sem prefixo: %r" % (escrita,))
        if escrita in self._deny or escrita not in self._allowed:
            raise self.SafetyError(
                "escrita de propriedade %r nao autorizada" % (escrita,))
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


# --------------------------------------------------------------------------
# a arvore medida do TemplateExemplo v1, reduzida ao que o executor navega
# --------------------------------------------------------------------------

def _arvore(userprg_impl=""):
    container = FakeContainer(filhos=[
        FakeNode("SystemPOUs", "pasta", filhos=[
            FakeNode("MainPrg", POU_GUID, declaracao="PROGRAM MainPrg",
                     implementacao="StartPrg();\n")]),
        FakeNode("UserPOUs", "pasta", filhos=[
            FakeNode("StartPrg", POU_GUID, declaracao="PROGRAM StartPrg",
                     implementacao=";"),
            FakeNode("UserPrg", POU_GUID, declaracao="PROGRAM UserPrg",
                     implementacao=userprg_impl)]),
    ])
    # `root/1/0/0`: Device -> Plc Logic -> Application
    plc = FakeNode("Plc Logic", "plc", filhos=[container])
    device = FakeNode("Device", "device", filhos=[plc])
    projeto = FakeProject([FakeNode("Project Settings", "cfg"), device])
    return projeto, container


def _spec():
    return {
        "schema_version": 1,
        "template": {"id": "TemplateExemplo_v1", "sha256": "5966257" + "0" * 57},
        "gvls": [{"name": "GVL_FAB",
                  "declaration": "{attribute 'qualified_only'}\nVAR_GLOBAL\n"
                                 "    g_xLigado : BOOL;\nEND_VAR"}],
        "programs": [{"name": "PRG_FAB", "language": {"guid": ST_GUID},
                      "declaration": "PROGRAM PRG_FAB\nVAR\n xL : BOOL;\nEND_VAR",
                      "implementation": "xL := GVL_FAB.g_xLigado;"}],
        "tasks": [{"name": "MainTask", "existing": True,
                   "program_calls": ["PRG_FAB"]}],
    }


def _escrever(tmp_path, nome, conteudo):
    caminho = os.path.join(str(tmp_path), nome)
    io.open(caminho, "w", encoding="utf-8", newline="").write(
        json.dumps(conteudo, ensure_ascii=False))
    return caminho


def _run(tmp_path, spec=None, plano=None, projeto=None, safety=None,
         saida=None, argv_extra=(), monkeypatch=None, escopo_extra=None):
    if spec is None:
        spec = _spec()
    if plano is None:
        resultado = build_authoring_plan(spec)
        assert resultado.problems == [], resultado.problems
        plano = resultado.plan
    if projeto is None:
        projeto, _c = _arvore()
    if safety is None:
        safety = FakeSafety()
    if saida is None:
        saida = os.path.join(str(tmp_path), "saida.project")
    caminho_spec = _escrever(tmp_path, "spec.json", spec)
    caminho_plano = _escrever(tmp_path, "plano.json", plano)
    argv = ["probe", "--plan=" + caminho_plano, "--spec=" + caminho_spec,
            "--output=" + os.path.join(str(tmp_path), "art"),
            "--output-project=" + saida]
    argv.extend(argv_extra)
    escopo = {"projects": object()}
    if escopo_extra:
        escopo.update(escopo_extra)
    resultado = probe46.run_executor(escopo, argv, safety,
                                     FakeProjectAccess(projeto), file_io,
                                     probe_cli)
    return resultado, projeto, safety


@pytest.fixture(autouse=True)
def _guid_sintetico(monkeypatch):
    """`System.Guid` nao existe no CPython. A conversao continua acontecendo na
    PRECONDICAO -- o que o duble troca e so o tipo de destino."""
    monkeypatch.setattr(probe46, "to_clr_guid",
                        lambda texto: (FakeGuid(texto), None))


# =============================================================================
# caminho aprovado
# =============================================================================

def test_executa_o_plano_inteiro_na_ordem(tmp_path):
    resultado, projeto, safety = _run(tmp_path)
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    assert resultado["exit_code"] == 0
    # 10 no plano: 7 executados aqui (create_gvl, create_program, tres
    # `replace`, a chamada idiomatica e `save_as`) e 3 delegados.
    assert resultado["steps_total"] == 10
    assert resultado["steps_executed"] == 7
    assert resultado["steps_delegated"] == 3
    assert safety.requested == ["create_gvl", "create_program", "replace",
                                "replace", "replace", "replace", "save_as"]
    assert projeto.saved_as == [os.path.join(str(tmp_path), "saida.project")]


def test_os_objetos_criados_vem_do_PLANO_e_nao_do_fonte(tmp_path):
    """O que separa este executor do probe 38: os nomes vem da spec. Trocar a
    spec troca o projeto gerado, sem tocar em codigo."""
    spec = _spec()
    spec["gvls"][0]["name"] = "GVL_OUTRA"
    spec["programs"][0]["name"] = "PRG_OUTRO"
    spec["programs"][0]["implementation"] = "xL := GVL_OUTRA.g_xLigado;"
    spec["tasks"][0]["program_calls"] = ["PRG_OUTRO"]
    resultado, _p, _s = _run(tmp_path, spec=spec)
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    criados = [(o["kind"], o["name"]) for o in resultado["created_objects"]]
    assert criados == [("gvl", "GVL_OUTRA"), ("program", "PRG_OUTRO")]


def test_dois_programas_e_duas_gvls(tmp_path):
    """A fabrica nao e de um objeto por familia."""
    spec = _spec()
    spec["gvls"].append({"name": "GVL_B", "declaration": "VAR_GLOBAL\nEND_VAR"})
    spec["programs"].append({"name": "PRG_B", "language": {"guid": ST_GUID},
                             "declaration": "PROGRAM PRG_B\nVAR\nEND_VAR",
                             "implementation": ";"})
    spec["tasks"][0]["program_calls"] = ["PRG_FAB", "PRG_B"]
    resultado, _p, _s = _run(tmp_path, spec=spec)
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    criados = sorted(o["name"] for o in resultado["created_objects"])
    assert criados == ["GVL_B", "GVL_FAB", "PRG_B", "PRG_FAB"]


def test_o_texto_escrito_e_o_da_spec(tmp_path):
    resultado, projeto, _s = _run(tmp_path)
    assert resultado["status"] == probe46.STATUS_EXECUTED
    container = projeto._filhos[1]._filhos[0]._filhos[0]
    por_nome = {n._nome: n for n in container._filhos}
    assert (por_nome["GVL_FAB"].textual_declaration.replaced[0]
            == _spec()["gvls"][0]["declaration"])
    assert (por_nome["PRG_FAB"].textual_implementation.replaced[0]
            == _spec()["programs"][0]["implementation"])


def test_a_chamada_vai_para_UserPrg_e_preserva_o_que_havia(tmp_path):
    projeto, _c = _arvore(userprg_impl="(* do fabricante *)\nxA := TRUE;\n")
    resultado, projeto, _s = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    userprg = projeto._filhos[1]._filhos[0]._filhos[0]._filhos[1]._filhos[1]
    escrito = userprg.textual_implementation.replaced[0]
    assert "(* do fabricante *)" in escrito
    assert "xA := TRUE;" in escrito
    assert "PRG_FAB();" in escrito


def test_a_chamada_ja_presente_nao_e_duplicada(tmp_path):
    projeto, _c = _arvore(userprg_impl="PRG_FAB();\n")
    resultado, projeto, _s = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe46.STATUS_EXECUTED
    userprg = projeto._filhos[1]._filhos[0]._filhos[0]._filhos[1]._filhos[1]
    assert userprg.textual_implementation.replaced == []
    passos = [s for s in resultado["step_log"]
              if s["operation"] == "create_program_call"]
    assert passos[0]["outcome"] == "already_present"


def test_o_texto_da_chamada_nao_e_lacrado_pelo_plano_e_isso_e_REGISTRADO(
        tmp_path):
    """Limite estrutural: o planner e offline e nao pode saber o que ha dentro
    de `UserPrg`, entao nao existe hash a conferir para este unico texto. Os
    dois hashes ficam no log para que a diferenca seja auditavel."""
    resultado, _p, _s = _run(tmp_path)
    passo = [s for s in resultado["step_log"]
             if s["operation"] == "create_program_call"][0]
    assert passo["not_hash_sealed_by_plan"] is True
    assert passo["host_sha256_before"]
    assert passo["host_sha256_after_planned"]
    assert passo["host_sha256_before"] != passo["host_sha256_after_planned"]


# =============================================================================
# o plano decide O QUE; o hash autoriza o texto
# =============================================================================

def test_texto_da_spec_que_nao_bate_com_o_hash_do_plano_REPROVA(tmp_path):
    """Plano e spec que discordam nao descrevem a mesma intencao. Reprova ANTES
    de qualquer mutacao -- e nao trata a spec como 'mais atual'."""
    spec = _spec()
    resultado_plano = build_authoring_plan(spec)
    plano = resultado_plano.plan
    spec["programs"][0]["implementation"] = "xL := FALSE;  (* trocado *)"
    resultado, projeto, safety = _run(tmp_path, spec=spec, plano=plano)
    assert resultado["status"] == probe46.STATUS_TEXT_HASH_MISMATCH
    assert safety.requested == []
    assert projeto.saved_as == []


def test_texto_ausente_na_spec_reprova_antes_de_mutar(tmp_path):
    spec = _spec()
    plano = build_authoring_plan(spec).plan
    del spec["programs"][0]["implementation"]
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano)
    assert resultado["status"] == probe46.STATUS_TEXT_MISSING
    assert safety.requested == []


def test_plano_nao_executavel_e_recusado(tmp_path):
    """Fail-closed do planner honrado aqui tambem: duas portas, nao uma."""
    spec = _spec()
    plano = build_authoring_plan(spec).plan
    plano["executable"] = False
    plano["measurement_gaps"] = [{"kind": "operation_not_field_proven",
                                  "detail": "sintetico"}]
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano)
    assert resultado["status"] == probe46.STATUS_PLAN_NOT_EXECUTABLE
    assert safety.requested == []


def test_operacao_fora_do_vocabulario_reprova_ANTES_da_primeira_mutacao(
        tmp_path):
    """Descobrir no passo 7 que ele e desconhecido deixaria a copia com seis
    mutacoes e nenhuma forma de desfaze-las."""
    spec = _spec()
    plano = build_authoring_plan(spec).plan
    plano["steps"][-1]["operation"] = "delete_everything"
    resultado, projeto, safety = _run(tmp_path, spec=spec, plano=plano)
    assert resultado["status"] == probe46.STATUS_UNKNOWN_OPERATION
    assert safety.requested == []
    assert projeto.saved_as == []


def test_operacao_do_vocabulario_mas_NAO_implementada_reprova_com_nome(
        tmp_path):
    """Uma operacao do vocabulario sem ramo escrito reprova com NOME
    PROPRIO, em vez de cair no `else` junto com lixo."""
    spec = _spec()
    plano = build_authoring_plan(spec).plan
    # `NOT_IMPLEMENTED_OPERATIONS` esta vazia hoje. O mecanismo continua
    # testado: sem ele, um vocabulario novo cairia no `else` generico.
    original = probe46.NOT_IMPLEMENTED_OPERATIONS
    try:
        probe46.NOT_IMPLEMENTED_OPERATIONS = ("create_dut",)
        plano["steps"][0]["operation"] = "create_dut"
        resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano)
    finally:
        probe46.NOT_IMPLEMENTED_OPERATIONS = original
    assert resultado["status"] == probe46.STATUS_OPERATION_NOT_IMPLEMENTED
    assert safety.requested == []
    assert "create_dut" in " ".join(resultado["problems"])


# =============================================================================
# a fase e a allowlist
# =============================================================================

def test_fase_errada_bloqueia(tmp_path):
    resultado, _p, safety = _run(tmp_path,
                                 safety=FakeSafety(phase="W1_4_INTEGRATED_BUILD"))
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


def test_allowlist_da_fase_menor_que_a_exigida_pelo_plano_bloqueia(tmp_path):
    """O plano declara o que precisa; a fase declara o que autoriza. Executar
    com a fase mais estreita descobriria a recusa no meio da cadeia."""
    safety = FakeSafety(allowed=("replace", "save_as"))
    resultado, projeto, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert safety.requested == []
    assert projeto.saved_as == []
    assert "create_gvl" in " ".join(resultado["problems"])


def test_guarda_falsificada_no_meio_da_cadeia_para_a_execucao(tmp_path):
    safety = FakeSafety(deny=("save_as",))
    resultado, projeto, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert "save_as" in safety.requested
    assert projeto.saved_as == []


def test_saida_existente_nunca_e_sobrescrita(tmp_path):
    saida = os.path.join(str(tmp_path), "ja-existe.project")
    io.open(saida, "w", encoding="utf-8").write("anterior")
    resultado, _p, safety = _run(tmp_path, saida=saida)
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert safety.requested == []
    assert io.open(saida, encoding="utf-8").read() == "anterior"


def test_reopen_build_e_verify_sao_DELEGADOS_e_registrados(tmp_path):
    """"O plano tinha 10 passos e eu executei 6" precisa aparecer no
    artefato."""
    resultado, _p, _s = _run(tmp_path)
    delegados = [s for s in resultado["step_log"] if s["outcome"] == "delegated"]
    assert sorted(s["operation"] for s in delegados) == ["build", "reopen",
                                                         "verify"]
    completion = probe46.build_completion(resultado)
    assert completion["steps_total"] == 10
    assert completion["steps_executed"] + completion["steps_delegated"] == 10


def test_o_guid_de_linguagem_chega_convertido_e_nao_como_texto(tmp_path):
    """Achado da run-005: `create_program` recusa `str`. O duble levanta
    `TypeError` se receber texto -- o mesmo erro do produto."""
    resultado, projeto, _s = _run(tmp_path)
    assert resultado["status"] == probe46.STATUS_EXECUTED
    container = projeto._filhos[1]._filhos[0]._filhos[0]
    criados = [c for c in container.created if c[0] == "create_program"]
    assert criados[0][2] == ST_GUID


# =============================================================================
# verificacao estatica
# =============================================================================

@pytest.fixture(scope="module")
def tree46():
    return ast.parse(io.open(PROBE46_PATH, encoding="utf-8").read())


def test_o_vocabulario_nao_divergiu_do_planner():
    """Os dois arquivos rodam em runtimes diferentes -- CPython 3 no host,
    IronPython 2.7 no probe -- e um import entre eles nao existe. A duplicacao
    e legitima; divergir em silencio nao e."""
    assert probe46.ALL_PLAN_OPERATIONS == PLAN_OPERATIONS


def test_toda_operacao_executada_e_provada_OU_esta_na_lista_de_prova():
    """A invariante, com a excecao NOMEADA.

    Executar o que o contrato marca como nao provado seria contradizer o que o
    planner recusa emitir -- exceto quando a operacao esta em
    `PROVING_OPERATIONS`, que e a lista explicita de "implementada aqui e ainda
    nao provada em campo". Essa lista existe porque ha um ovo-e-galinha real: o
    planner nao emite plano executavel com operacao nao provada, e sem executar
    nao ha prova.

    A lista ENCOLHE, e desde a run-028 ela esta VAZIA: `create_function_block`
    e `create_function` foram provadas (docs/43) e sairam dela. Um item que
    ficasse la para sempre seria uma operacao que o executor faz sem prova,
    indefinidamente."""
    for operacao in probe46.EXECUTED_OPERATIONS:
        provada = EXECUTOR_CONTRACT[operacao]["field_proven"]
        em_prova = operacao in probe46.PROVING_OPERATIONS
        assert provada or em_prova, operacao
        # Nunca as duas: uma operacao ja provada nao tem o que provar.
        assert not (provada and em_prova), operacao


def test_a_lista_de_prova_tem_o_que_o_contrato_diz_nao_provado():
    """Invariante que vale com a lista vazia ou cheia: nada entra nela sem o
    contrato concordar que ainda nao ha prova."""
    for operacao in probe46.PROVING_OPERATIONS:
        assert EXECUTOR_CONTRACT[operacao]["field_proven"] is False, operacao
        assert operacao in probe46.EXECUTED_OPERATIONS, operacao


def test_o_vocabulario_INTEIRO_tem_ramo_escrito():
    """`NOT_IMPLEMENTED_OPERATIONS` esta vazia: toda operacao que o planner
    pode emitir tem ramo aqui. A tupla continua existindo para que uma
    operacao NOVA reprove com nome proprio, em vez de cair no `else` junto
    com lixo."""
    assert probe46.NOT_IMPLEMENTED_OPERATIONS == ()
    executadas = set(probe46.EXECUTED_OPERATIONS)
    delegadas = set(probe46.DELEGATED_OPERATIONS)
    assert executadas | delegadas == set(probe46.ALL_PLAN_OPERATIONS)


def test_as_operacoes_em_prova_sao_as_que_o_contrato_diz_nao_provadas():
    # VAZIA desde a run-036 (docs/48): `create_task` e `bind_program_to_task`
    # sairam juntas, como tinham de sair -- uma task cheia e uma cadeia so.
    #
    # A tupla vazia nao desliga nada. A igualdade abaixo continua sendo o
    # invariante: uma operacao esta na tupla SE E SOMENTE SE o contrato a
    # declara sem prova. Marcar `field_proven: True` sem tirar daqui, ou tirar
    # daqui sem medir, reprova de qualquer lado.
    # VAZIA de novo desde a run-037 (docs/49). A igualdade abaixo continua
    # sendo o invariante, e e ela que este teste guarda: uma operacao esta na
    # tupla SE E SOMENTE SE o contrato a declara sem prova.
    assert probe46.PROVING_OPERATIONS == ()
    for operacao in probe46.EXECUTED_OPERATIONS:
        provada = EXECUTOR_CONTRACT[operacao]["field_proven"]
        em_prova = operacao in probe46.PROVING_OPERATIONS
        assert provada != em_prova, operacao
        if provada:
            assert EXECUTOR_CONTRACT[operacao]["evidence"], operacao


def test_o_nome_do_gap_nao_divergiu_do_planner():
    from mastertool_bridge.planner.planner import GAP_OPERATION_NOT_FIELD_PROVEN
    assert (probe46.GAP_OPERATION_NOT_FIELD_PROVEN
            == GAP_OPERATION_NOT_FIELD_PROVEN)


def test_toda_operacao_NAO_implementada_e_nao_provada_no_contrato():
    for operacao in probe46.NOT_IMPLEMENTED_OPERATIONS:
        assert EXECUTOR_CONTRACT[operacao]["field_proven"] is False, operacao


def test_a_particao_do_vocabulario_e_total_e_disjunta():
    """Uma operacao que nao caisse em nenhum dos tres grupos chegaria ao laco
    sem ninguem ter decidido o que fazer com ela."""
    executadas = set(probe46.EXECUTED_OPERATIONS)
    delegadas = set(probe46.DELEGATED_OPERATIONS)
    ausentes = set(probe46.NOT_IMPLEMENTED_OPERATIONS)
    assert executadas | delegadas | ausentes == set(probe46.ALL_PLAN_OPERATIONS)
    assert executadas & delegadas == set()
    assert executadas & ausentes == set()
    assert delegadas & ausentes == set()


def test_o_despacho_e_por_IGUALDADE_com_constante_do_modulo(tree46):
    """Um despacho por dicionario de funcoes ou por `getattr` aceitaria uma
    operacao que ninguem escreveu."""
    constantes = {no.targets[0].id for no in ast.walk(tree46)
                  if isinstance(no, ast.Assign)
                  and isinstance(no.targets[0], ast.Name)
                  and no.targets[0].id.startswith("OP_")}
    assert len(constantes) == len(probe46.ALL_PLAN_OPERATIONS)
    comparados = set()
    for no in ast.walk(tree46):
        if not isinstance(no, ast.Compare) or len(no.ops) != 1:
            continue
        if not isinstance(no.ops[0], ast.Eq):
            continue
        alvo = no.left
        direita = no.comparators[0]
        if (isinstance(alvo, ast.Name) and alvo.id == "operacao"
                and isinstance(direita, ast.Name)):
            comparados.add(direita.id)
    # Todo ramo compara com uma constante `OP_*` do modulo, nunca com literal
    # solto nem com valor vindo de dado.
    assert comparados
    assert comparados <= constantes


def test_nenhum_getattr_recebe_dado_do_plano(tree46):
    """`getattr` existe quatro vezes e nenhuma escolhe operacao: duas leem
    documento com nome vindo de constante literal, duas leem o modulo
    `safety`."""
    achados = []
    for no in ast.walk(tree46):
        if not isinstance(no, ast.Call):
            continue
        if not isinstance(no.func, ast.Name) or no.func.id != "getattr":
            continue
        argumento = no.args[1]
        if isinstance(argumento, ast.Constant):
            achados.append(("literal", argumento.value))
        elif isinstance(argumento, ast.Name):
            # Parametro de funcao: aceito apenas nos leitores de documento, que
            # sao chamados com constante literal (conferido abaixo).
            achados.append(("parametro", argumento.id))
        else:
            raise AssertionError("getattr com argumento inesperado: "
                                 + ast.dump(no))
    assert achados
    for forma, valor in achados:
        if forma == "parametro":
            # `nome_membro` vem de `DUT_KIND_TO_MEMBER`, mapa LITERAL do
            # modulo: a spec escolhe a CHAVE, nunca o nome do atributo.
            assert valor in ("indicator_name", "document_name",
                             "nome_membro"), valor
        else:
            assert valor in ("CONTROLLED_WRITE_PHASE",
                             "PHASE_ALLOWED_OPERATIONS", "DutType"), valor


def test_os_leitores_de_documento_sao_chamados_com_literal(tree46):
    for no in ast.walk(tree46):
        if not isinstance(no, ast.Call):
            continue
        if not isinstance(no.func, ast.Name) or no.func.id != "read_document":
            continue
        for argumento in no.args[1:]:
            assert isinstance(argumento, ast.Constant), ast.dump(no)
            assert argumento.value in ("has_textual_declaration",
                                       "textual_declaration",
                                       "has_textual_implementation",
                                       "textual_implementation")


def test_sem_eval_exec_ou_import_dinamico():
    texto = io.open(PROBE46_PATH, encoding="utf-8").read()
    for proibido in ("eval(", "exec(", "__import__", "globals()["):
        assert proibido not in texto, proibido


def test_sem_setattr__que_e_o_dispatch_dinamico_da_ATRIBUICAO(tree46):
    """`getattr` seria escolher o metodo por string; `setattr` e escolher o
    CAMPO por string, e o dado viria do plano.

    Com ele, `configure_task` poderia escrever qualquer propriedade do objeto
    do produto -- inclusive as que ninguem catalogou -- e a allowlist por
    propriedade viraria enfeite: o gate autorizaria `set:interval` e a linha
    escreveria outra coisa.

    `getattr` NAO entra nesta proibicao, e a assimetria e o ponto. Ler por nome
    ja e restrito por testes proprios -- `read_document` so aceita os quatro
    literais catalogados, e `resolve_dut_type` alcanca o membro por um mapa
    LITERAL deste arquivo. Leitura errada devolve dado errado; escrita errada
    muda o produto."""
    for no in ast.walk(tree46):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
            assert no.func.id not in ("setattr", "delattr"), ast.dump(no.func)


def test_toda_atribuicao_de_propriedade_do_produto_esta_GUARDADA(tree46):
    """A verificacao estatica que a porta de metodos nao faz.

    Uma guarda de chamada procura `Call`; isto procura `Assign` cujo alvo e
    `Attribute`. Foi exatamente por essa fresta que a classe inteira passou
    despercebida ate a run-036."""
    guardadas = {"set_kind_of_task_guarded", "set_interval_guarded",
                 "set_interval_unit_guarded", "set_priority_guarded"}
    dentro_de_guardada = set()
    for no in ast.walk(tree46):
        if isinstance(no, ast.FunctionDef) and no.name in guardadas:
            for interno in ast.walk(no):
                dentro_de_guardada.add(id(interno))
    for no in ast.walk(tree46):
        if not isinstance(no, ast.Assign):
            continue
        for alvo in no.targets:
            if not isinstance(alvo, ast.Attribute):
                continue
            if alvo.attr not in probe46.CONFIGURABLE_TASK_PROPERTIES:
                continue
            assert id(no) in dentro_de_guardada,                 "atribuicao de %r fora de funcao guardada (linha %d)" % (
                    alvo.attr, no.lineno)


def test_a_guarda_da_ATRIBUICAO_e_a_linha_imediatamente_anterior(tree46):
    """Mesmo rigor da adjacencia das chamadas, e com a OUTRA funcao de guarda:
    escrita de propriedade tem porta propria no gate."""
    esperado = {
        "set_kind_of_task_guarded": ("kind_of_task", "set:kind_of_task"),
        "set_interval_guarded": ("interval", "set:interval"),
        "set_interval_unit_guarded": ("interval_unit", "set:interval_unit"),
        "set_priority_guarded": ("priority", "set:priority"),
    }
    vistos = set()
    for no in ast.walk(tree46):
        if not isinstance(no, ast.FunctionDef) or no.name not in esperado:
            continue
        vistos.add(no.name)
        campo, nome_no_gate = esperado[no.name]
        corpo = [n for n in no.body
                 if not (isinstance(n, ast.Expr)
                         and isinstance(getattr(n, "value", None), ast.Constant))]
        assert len(corpo) == 3, [ast.dump(n) for n in corpo]
        guarda, atribuicao, retorno = corpo
        assert (guarda.value.func.attr
                == "assert_controlled_property_write_allowed")
        assert guarda.value.args[0].value == nome_no_gate
        assert isinstance(atribuicao, ast.Assign)
        alvo = atribuicao.targets[0]
        assert isinstance(alvo, ast.Attribute)
        assert alvo.value.id == "task"
        assert alvo.attr == campo
        assert isinstance(retorno, ast.Return)
    assert vistos == set(esperado)


def test_o_membro_do_enum_de_task_NAO_vem_do_dado(tree46):
    """`resolve_kind_of_task` alcanca o membro por nome que ESTE arquivo
    escreve. Um `getattr(enum, valor_da_spec)` deixaria a spec escolher qual
    membro tocar -- mesmo cuidado de `resolve_dut_type` (docs/45)."""
    fonte = io.open(PROBE46_PATH, encoding="utf-8").read()
    assert "enum.Cyclic" in fonte
    assert "enum.Freewheeling" in fonte


def test_nenhum_mutador_fora_dos_cinco_guardados(tree46):
    """`add` e o mais importante da lista, e a razao mudou de forma.

    Ele ja foi proibido em qualquer receptor, pelo aviso que W2 mediu. So que
    o aviso nomeia a `MainTask` -- ele fala da task DO PERFIL. Numa task criada
    pela spec, `pou_collection.add` e o unico caminho que existe, e a protecao
    nao e proibir o verbo: e o RECEPTOR, mais a guarda imediatamente antes."""
    proibidos = ("add", "insert", "remove", "rename", "save", "save_archive",
                 "rebuild", "clean", "create_dut", "create_folder",
                 "create_function", "create_function_block", "create_task",
                 "import_xml", "download_missing_libraries")
    receptores_python = {"partes", "linhas", "filhos", "pilha", "escritos",
                         "problems", "entries", "required", "achados",
                         "comparados", "sys.path", "nos"}
    # `container` recebe as QUATRO criacoes, cada uma numa funcao guardada
    # propria -- conferidas por `test_a_guarda_e_a_linha_IMEDIATAMENTE_anterior`.
    criacoes_guardadas = {"create_function_block", "create_function",
                          "create_gvl", "create_program", "create_dut"}
    for no in ast.walk(tree46):
        if not isinstance(no, ast.Call) or not isinstance(no.func,
                                                          ast.Attribute):
            continue
        if no.func.attr not in proibidos:
            continue
        if (no.func.attr in criacoes_guardadas
                and isinstance(no.func.value, ast.Name)
                and no.func.value.id == "container"):
            continue
        # `create_task` vive em outro receptor: `ScriptTaskConfigObject`.
        if (no.func.attr == "create_task"
                and isinstance(no.func.value, ast.Name)
                and no.func.value.id == "task_configuration"):
            continue
        # `add` na lista de POUs da task que este plano criou. O receptor se
        # chama `pou_collection` porque e por ele que esta chamada se distingue
        # de um `.add` de `set` do Python -- mesmo nome que o probe 43 usou.
        if (no.func.attr == "add"
                and isinstance(no.func.value, ast.Name)
                and no.func.value.id == "pou_collection"):
            continue
        receptor = no.func.value
        if isinstance(receptor, ast.Attribute):
            assert (isinstance(receptor.value, ast.Name)
                    and receptor.value.id == "sys"), ast.dump(no.func)
            continue
        if isinstance(receptor, ast.Subscript):
            continue
        assert isinstance(receptor, ast.Name), ast.dump(no.func)
        assert receptor.id in receptores_python, "%s.%s()" % (receptor.id,
                                                              no.func.attr)


def test_a_guarda_e_a_linha_IMEDIATAMENTE_anterior(tree46):
    esperado = {
        "create_gvl_guarded": ("container", "create_gvl", "create_gvl"),
        "create_program_guarded": ("container", "create_program",
                                   "create_program"),
        "create_function_block_guarded": ("container", "create_function_block",
                                          "create_function_block"),
        "create_function_guarded": ("container", "create_function",
                                    "create_function"),
        "replace_guarded": ("document", "replace", "replace"),
        "replace_call_host_guarded": ("document", "replace", "replace"),
        "create_dut_guarded": ("container", "create_dut", "create_dut"),
        "create_task_guarded": ("task_configuration", "create_task",
                                "create_task"),
        "add_program_call_guarded": ("pou_collection", "add", "add"),
        "save_as_guarded": ("project", "save_as", "save_as"),
    }
    vistos = set()
    for no in ast.walk(tree46):
        if not isinstance(no, ast.FunctionDef) or no.name not in esperado:
            continue
        vistos.add(no.name)
        receptor_esperado, metodo, operacao = esperado[no.name]
        corpo = [n for n in no.body
                 if not (isinstance(n, ast.Expr)
                         and isinstance(getattr(n, "value", None), ast.Constant))]
        assert len(corpo) == 3, [ast.dump(n) for n in corpo]
        guarda, chamada, retorno = corpo
        assert guarda.value.func.attr == "assert_controlled_write_allowed"
        assert guarda.value.args[0].value == operacao
        alvo = chamada.value if isinstance(chamada, ast.Expr) else chamada.value
        assert isinstance(alvo, ast.Call)
        assert alvo.func.value.id == receptor_esperado
        assert alvo.func.attr == metodo
        assert isinstance(retorno, (ast.Return, ast.Expr))
    assert vistos == set(esperado)


def test_vocabulario_de_status_fechado():
    assert set(probe46.EXIT_BY_STATUS) == set(probe46.ALL_STATUSES)
    assert probe46.EXIT_BY_STATUS[probe46.STATUS_EXECUTED] == 0
    for status in probe46.ALL_STATUSES:
        if status not in probe46.SUCCESS_STATUSES:
            assert probe46.EXIT_BY_STATUS[status] != 0, status


def test_identificadores_ascii(tree46):
    for no in ast.walk(tree46):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(no, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


def test_a_completion_e_o_ultimo_artefato(tmp_path):
    resultado, _p, _s = _run(tmp_path)
    escritos = probe46.write_artifacts(resultado, file_io)
    assert escritos[-1] == "execution-completion.json"
    assert set(escritos) == set(probe46.ARTIFACT_NAMES)


def test_a_hospedeira_da_chamada_e_do_perfil_e_a_lista_e_fechada():
    assert probe46.PROGRAM_CALL_HOST in probe46.PROFILE_POU_NAMES
    assert probe46.PROFILE_POU_NAMES == ("StartPrg", "UserPrg", "ActivePrg",
                                         "NonSkippedPrg")


def test_hospedeira_ausente_reprova_e_nao_cai_para_outra_pou(tmp_path):
    """Cair para outra POU mudaria a semantica do projeto sem ninguem pedir --
    `StartPrg` roda na partida, e nao ciclicamente."""
    projeto, _c = _arvore()
    # Remove `UserPrg` da arvore.
    userpous = projeto._filhos[1]._filhos[0]._filhos[0]._filhos[1]
    userpous._filhos = [n for n in userpous._filhos if n._nome != "UserPrg"]
    resultado, _p, _s = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe46.STATUS_TARGET_NOT_FOUND
    assert "UserPrg" in " ".join(resultado["problems"])


def test_a_autorizacao_e_pedida_para_o_que_o_executor_FAZ(tmp_path):
    """A run-027 reprovou com "faltam: ['build']": a primeira versao comparava
    o `required_allowlist` do PLANO INTEIRO com a allowlist da fase. A recusa
    estava certa e a pergunta estava errada -- o plano descreve a cadeia
    inteira, inclusive o build, e o build tem fase PROPRIA.

    A fase de autoria NAO autoriza `build`, e a execucao tem de passar."""
    safety = FakeSafety(allowed=("create_gvl", "create_program", "replace",
                                 "save_as"))
    resultado, _p, safety = _run(tmp_path, safety=safety)
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    assert "build" in _plan_allowlist(tmp_path)
    assert resultado["operations_required"] == ["create_gvl", "create_program",
                                                "replace", "save_as"]
    assert "build" not in resultado["operations_required"]


def _plan_allowlist(tmp_path):
    plano = build_authoring_plan(_spec()).plan
    return plano["required_allowlist"]


def test_a_exigencia_e_DERIVADA_dos_passos_e_nao_lida_do_plano(tmp_path):
    """Derivar o REQUISITO dos passos e legitimo; derivar a PERMISSAO seria a
    fase deixando de autorizar coisa alguma. Um plano que mentisse no
    `required_allowlist` nao muda o que o executor pede."""
    spec = _spec()
    plano = build_authoring_plan(spec).plan
    plano["required_allowlist"] = ["save_as"]      # mentira deliberada
    safety = FakeSafety(allowed=("save_as",))
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano,
                                 safety=safety)
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert "create_gvl" in " ".join(resultado["problems"])
    assert safety.requested == []


def test_a_chamada_idiomatica_consome_replace_e_nao_um_verbo_proprio():
    """Ela e uma escrita de texto na POU de perfil (docs/41), e nao uma
    operacao estrutural. Um verbo proprio pediria autorizacao que nunca foi
    provada."""
    assert (probe46.OPERATION_TO_MASTERTOOL_VERB["create_program_call"]
            == "replace")


def test_o_mapa_de_verbos_cobre_exatamente_as_operacoes_executadas():
    """UMA operacao executada fica de fora do mapa, e a ausencia e o desenho:
    `configure_task` nao consome METODO nenhum -- ela ATRIBUI. O que ela precisa
    autorizado sai do passo, uma escrita por propriedade declarada."""
    assert (set(probe46.OPERATION_TO_MASTERTOOL_VERB)
            == set(probe46.EXECUTED_OPERATIONS) - {"configure_task"})
    assert probe46.PROPERTY_WRITE_PREFIX == "set:"
    assert probe46.CONFIGURABLE_TASK_PROPERTIES == (
        "kind_of_task", "interval", "interval_unit", "priority")
    for operacao, verbo in probe46.OPERATION_TO_MASTERTOOL_VERB.items():
        assert (EXECUTOR_CONTRACT[operacao]["mastertool_operation"] == verbo), \
            operacao


# =============================================================================
# a execucao de PROVA -- a excecao nomeada e estreita
# =============================================================================

def _spec_com_fb():
    spec = _spec()
    spec["function_blocks"] = [
        {"name": "FB_MOTOR", "language": {"guid": ST_GUID},
         "declaration": "FUNCTION_BLOCK FB_MOTOR\nVAR_INPUT\n xLiga : BOOL;\nEND_VAR",
         "implementation": "xSaida := xLiga;"}]
    spec["functions"] = [
        {"name": "F_ESCALA", "language": {"guid": ST_GUID}, "return_type": "REAL",
         "declaration": "FUNCTION F_ESCALA : REAL\nVAR_INPUT\n rEntrada : REAL;\nEND_VAR",
         "implementation": "F_ESCALA := rEntrada * 2.0;"}]
    return spec


def _fase_de_prova():
    return FakeSafety(phase="W5_PROVE_IEC_PACKAGE",
                      allowed=("create_gvl", "create_program",
                               "create_function_block", "create_function",
                               "replace", "save_as"))


def test_spec_com_FB_e_FUNCTION_agora_e_executavel_normalmente(tmp_path):
    """Depois da run-028 (docs/43) as duas estao provadas, e a spec com FB nao
    depende mais de fase de prova nenhuma: ela e plano executavel comum."""
    spec = _spec_com_fb()
    plano = build_authoring_plan(spec).plan
    assert plano["executable"] is True, plano["measurement_gaps"]
    resultado, projeto, safety = _run(tmp_path, spec=spec, plano=plano,
                                      safety=_fase_de_prova())
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    assert resultado["proving_operations"] == []
    criados = {o["name"]: o["kind"] for o in resultado["created_objects"]}
    assert criados["FB_MOTOR"] == "function_block"
    assert criados["F_ESCALA"] == "function"


def test_o_caminho_de_prova_continua_existindo_para_o_proximo_marco(tmp_path):
    """A lista esta vazia hoje; o mecanismo nao. Este teste simula uma operacao
    ainda nao provada e confere que a fase continua sendo quem desempata --
    senao o proximo marco descobriria o caminho quebrado so ao precisar
    dele."""
    spec = _spec_com_fb()
    plano = build_authoring_plan(spec).plan
    plano["executable"] = False
    plano["measurement_gaps"] = [{
        "kind": "operation_not_field_proven",
        "detail": "a operacao de plano 'create_function_block' tem API "
                  "catalogada, mas nunca foi exercida."}]
    original = probe46.PROVING_OPERATIONS
    try:
        probe46.PROVING_OPERATIONS = ("create_function_block",)
        resultado, _p, _s = _run(tmp_path, spec=spec, plano=plano,
                                 safety=_fase_de_prova())
    finally:
        probe46.PROVING_OPERATIONS = original
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    assert resultado["proving_operations"] == ["create_function_block"]
    assert any("EXECUCAO DE PROVA" in n for n in resultado["gap_notes"])


def test_a_fase_que_NAO_autoriza_o_verbo_nao_redime_o_plano(tmp_path):
    """A excecao e da FASE, e nao do plano. Sem o verbo na allowlist literal,
    ninguem decidiu provar coisa alguma."""
    spec = _spec_com_fb()
    plano = build_authoring_plan(spec).plan
    safety = FakeSafety(phase="W5_PROVE_IEC_PACKAGE",
                        allowed=("create_gvl", "create_program", "replace",
                                 "save_as"))
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano,
                                 safety=safety)
    # Com as duas ja provadas, o plano e executavel e a fase estreita reprova
    # pelo verbo que FALTA, e nao pela falta de prova.
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


def test_lacuna_de_OUTRO_TIPO_reprova_mesmo_na_fase_de_prova(tmp_path):
    """A excecao cobre EXATAMENTE `operation_not_field_proven`. GUID de
    linguagem nao medido continua reprovando -- a fase nao redime lacuna que
    ela nao nomeia."""
    spec = _spec_com_fb()
    spec["programs"][0]["language"] = {
        "guid": "11111111-2222-3333-4444-555555555555"}
    plano = build_authoring_plan(spec).plan
    tipos = {g["kind"] for g in plano["measurement_gaps"]}
    assert "unmeasured_language_guid" in tipos
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano,
                                 safety=_fase_de_prova())
    assert resultado["status"] == probe46.STATUS_PLAN_NOT_EXECUTABLE
    assert safety.requested == []


def test_operacao_nao_provada_FORA_da_lista_de_prova_reprova(tmp_path):
    """`create_task` nao esta implementada nem em `PROVING_OPERATIONS`. Nem a
    fase mais generosa a torna executavel."""
    spec = _spec()
    plano = build_authoring_plan(spec).plan
    plano["executable"] = False
    plano["measurement_gaps"] = [{
        "kind": "operation_not_field_proven",
        "detail": "a operacao de plano 'create_interface' nao foi "
                  "exercida."}]
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano,
                                 safety=_fase_de_prova())
    assert resultado["status"] == probe46.STATUS_PLAN_NOT_EXECUTABLE
    assert safety.requested == []


def test_a_FUNCTION_recebe_o_return_type_do_plano(tmp_path):
    """Obrigatorio na assinatura catalogada, e vem do PLANO -- o executor nao
    escolhe um."""
    spec = _spec_com_fb()
    plano = build_authoring_plan(spec).plan
    resultado, projeto, _s = _run(tmp_path, spec=spec, plano=plano,
                                  safety=_fase_de_prova())
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    funcao = [o for o in resultado["created_objects"]
              if o["kind"] == "function"][0]
    assert funcao["return_type"] == "REAL"


def test_FUNCTION_sem_return_type_reprova_antes_de_mutar(tmp_path):
    spec = _spec_com_fb()
    plano = build_authoring_plan(spec).plan
    for passo in plano["steps"]:
        if passo["operation"] == "create_function":
            passo["return_type"] = None
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano,
                                 safety=_fase_de_prova())
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


def test_a_fase_da_fabrica_NAO_autoriza_os_verbos_de_fb_e_function(tmp_path):
    """Provar e um marco; produzir e outro. A fabrica nao autoriza os verbos de
    prova, entao um plano com FB nao roda sob ela nem por engano."""
    spec = _spec_com_fb()
    plano = build_authoring_plan(spec).plan
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano,
                                 safety=FakeSafety())
    # A fabrica nao autoriza os verbos de FB/FUNCTION: reprova por allowlist.
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


def test_as_fases_aceitas_sao_conjunto_fechado():
    """Literal e fechado, pelo mesmo motivo de `ACCEPTED_BUILD_PHASES` no probe
    40: acrescentar fase aqui e decisao humana no mesmo commit que a abre, e
    nao consequencia de um plano trazer nome novo."""
    assert probe46.ACCEPTED_PHASES == ("W9_PROVE_TASK_TIMING",
                                       "W8_PROVE_TASK_WITH_POU",
                                       "W4_EXECUTE_PLAN",
                                       "W5_PROVE_IEC_PACKAGE",
                                       "W6_PROVE_DUT_AND_TASK",
                                       "W7_FACTORY_FULL",
                                       "W10_EDIT_EXISTING",
                                       "W10_REVERT")


def test_fase_fora_do_conjunto_reprova(tmp_path):
    resultado, _p, safety = _run(
        tmp_path, safety=FakeSafety(phase="W1_4_INTEGRATED_BUILD"))
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


# =============================================================================
# create_dut e create_task
# =============================================================================

class FakeDutType(object):
    """O enum injetado no escopo do script (medido na run-031, docs/45)."""
    Structure = "DutType.Structure"
    Enumeration = "DutType.Enumeration"
    Alias = "DutType.Alias"
    Union = "DutType.Union"


class FakeKindOfTask(object):
    """O enum injetado no escopo do script, como `DutType` (docs/45)."""
    Cyclic = "KindOfTask.Cyclic"
    Freewheeling = "KindOfTask.Freewheeling"
    Event = "KindOfTask.Event"
    ExternalEvent = "KindOfTask.ExternalEvent"
    Status = "KindOfTask.Status"
    ParentSynchron = "KindOfTask.ParentSynchron"


class FakeTaskConfig(FakeNode):
    def __init__(self):
        FakeNode.__init__(self, "Task Configuration", "taskcfg")
        self.is_task_configuration = True
        self.created_tasks = []

    def __init__(self, surda=False):
        FakeNode.__init__(self, "Task Configuration", "taskcfg")
        self.is_task_configuration = True
        self.created_tasks = []
        # `surda`: a task ACEITA a atribuicao e continua com o valor antigo --
        # o modo de falha proprio da escrita de propriedade, e o unico que um
        # metodo nao tem.
        self.surda = surda

    def create_task(self, nome):
        self.created_tasks.append(nome)
        novo = FakeTask(nome, surda=self.surda)
        self._filhos.append(novo)
        return novo


class FakeTask(FakeNode):
    """Nasce com os defaults que a run-036 MEDIU no produto (docs/48 secao 4):
    ciclica de 20 ms e prioridade 1 -- mais rapida e mais prioritaria que a
    propria MainTask. E esse nascimento que `configure_task` existe para
    corrigir."""

    def __init__(self, nome, surda=False):
        FakeNode.__init__(self, nome, "task")
        self.is_task = True
        self.pous = FakePouCollection()
        self._surda = surda
        self._valores = {"kind_of_task": "Cyclic", "interval": "t#20ms",
                         "interval_unit": "ms", "priority": "1"}

    def _le(self, campo):
        return self._valores[campo]

    def _escreve(self, campo, valor):
        if self._surda:
            return
        # O produto devolve o NOME do membro do enum, e nao o membro.
        if campo == "kind_of_task" and isinstance(valor, str)                 and valor.startswith("KindOfTask."):
            valor = valor.split(".", 1)[1]
        self._valores[campo] = valor

    kind_of_task = property(lambda self: self._le("kind_of_task"),
                            lambda self, v: self._escreve("kind_of_task", v))
    interval = property(lambda self: self._le("interval"),
                        lambda self, v: self._escreve("interval", v))
    interval_unit = property(lambda self: self._le("interval_unit"),
                             lambda self, v: self._escreve("interval_unit", v))
    priority = property(lambda self: self._le("priority"),
                        lambda self, v: self._escreve("priority", v))


class FakePouCollection(list):
    """`ScriptPouObjectCollection` herda de `list`, e cada entrada e a tupla
    `(name, comment)` -- medido em W2 (docs/39). A task nasce VAZIA, e esse
    estado inicial e o que torna o `add` verificavel."""

    def add(self, pou_name, comment=None):
        list.append(self, (pou_name, comment))


def _spec_com_dut_e_task(task_name="MainTask", existing=True):
    spec = _spec()
    spec["duts"] = [
        {"name": "ST_MOTOR", "kind": "STRUCT",
         "declaration": "TYPE ST_MOTOR :\nSTRUCT\n rV : REAL;\nEND_STRUCT\nEND_TYPE"},
        {"name": "EN_MODO", "kind": "ENUM",
         "declaration": "TYPE EN_MODO :\n(\n Parado := 0\n);\nEND_TYPE"}]
    tarefa = {"name": task_name, "program_calls": ["PRG_FAB"]}
    if existing:
        tarefa["existing"] = True
    spec["tasks"] = [tarefa]
    return spec


def _arvore_com_taskconfig(userprg_impl="", surda=False):
    projeto, container = _arvore(userprg_impl=userprg_impl)
    container._filhos.append(FakeTaskConfig(surda=surda))
    return projeto, container


def _fase_com_configuracao():
    """A fase de vinculo mais as QUATRO escritas de propriedade. Os nomes
    levam o prefixo `set:` porque o registro do gate exige -- e sem ele um
    campo se confundiria com um metodo dentro da mesma allowlist."""
    return FakeSafety(phase="W9_PROVE_TASK_TIMING",
                      allowed=("create_gvl", "create_program", "create_task",
                               "add", "replace", "save_as",
                               "set:kind_of_task", "set:interval",
                               "set:interval_unit", "set:priority"))


def _spec_com_task_configurada(**parametros):
    spec = _spec()
    tarefa = {"name": "TaskNova", "program_calls": ["PRG_FAB"]}
    tarefa.update(parametros)
    spec["tasks"] = [tarefa]
    return spec


def _run_configuracao(tmp_path, spec, surda=False, safety=None):
    projeto, _c = _arvore_com_taskconfig(surda=surda)
    plano = build_authoring_plan(spec).plan
    assert plano is not None
    return _run(tmp_path, spec=spec, plano=plano, projeto=projeto,
                safety=safety or _fase_com_configuracao(),
                escopo_extra={"DutType": FakeDutType,
                              "KindOfTask": FakeKindOfTask})


def _fase_com_dut_e_task():
    return FakeSafety(phase="W5_PROVE_IEC_PACKAGE",
                      allowed=("create_gvl", "create_program", "create_dut",
                               "create_task", "replace", "save_as"))


def _fase_com_vinculo_de_task():
    """A de cima mais `add` -- a fase que exerce a cadeia inteira da task."""
    return FakeSafety(phase="W8_PROVE_TASK_WITH_POU",
                      allowed=("create_gvl", "create_program", "create_dut",
                               "create_task", "add", "replace", "save_as"))


def _run_prova(tmp_path, spec, projeto=None, safety=None):
    if projeto is None:
        projeto, _c = _arvore_com_taskconfig()
    plano = build_authoring_plan(spec).plan
    return _run(tmp_path, spec=spec, plano=plano, projeto=projeto,
                safety=safety or _fase_com_dut_e_task(),
                escopo_extra={"DutType": FakeDutType})


def test_cria_dut_de_cada_subtipo_com_o_membro_do_enum(tmp_path):
    spec = _spec_com_dut_e_task()
    resultado, projeto, _s = _run_prova(tmp_path, spec)
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    container = projeto._filhos[1]._filhos[0]._filhos[0]
    criados = [c for c in container.created if c[0] == "create_dut"]
    por_nome = {c[1]: c[2] for c in criados}
    assert por_nome["ST_MOTOR"] == "DutType.Structure"
    assert por_nome["EN_MODO"] == "DutType.Enumeration"


def test_dut_kind_fora_do_mapa_reprova_e_nao_vira_Structure(tmp_path):
    """Cair para `Structure` por conveniencia criaria o objeto errado calado."""
    spec = _spec_com_dut_e_task()
    plano = build_authoring_plan(spec).plan
    for passo in plano["steps"]:
        if passo["operation"] == "create_dut":
            passo["dut_kind"] = "UNIAO_QUALQUER"
    projeto, _c = _arvore_com_taskconfig()
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano,
                                 projeto=projeto,
                                 safety=_fase_com_dut_e_task(),
                                 escopo_extra={"DutType": FakeDutType})
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert safety.requested == []


def test_enum_ausente_do_escopo_e_ACHADO_e_nao_motivo_para_adivinhar(tmp_path):
    spec = _spec_com_dut_e_task()
    plano = build_authoring_plan(spec).plan
    projeto, _c = _arvore_com_taskconfig()
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano,
                                 projeto=projeto,
                                 safety=_fase_com_dut_e_task())
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert "DutType" in " ".join(resultado["problems"])
    assert safety.requested == []


def test_cria_task_no_no_de_configuracao_achado_pelo_MARCADOR(tmp_path):
    spec = _spec_com_dut_e_task(task_name="MainTask", existing=False)
    projeto, container = _arvore_com_taskconfig()
    resultado, projeto, _s = _run_prova(tmp_path, spec, projeto=projeto)
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    cfg = [n for n in container._filhos
           if getattr(n, "is_task_configuration", False)][0]
    assert cfg.created_tasks == ["MainTask"]
    criados = {o["name"]: o["kind"] for o in resultado["created_objects"]}
    assert criados["MainTask"] == "task"


def test_sem_no_de_configuracao_de_tasks_reprova_antes_de_mutar(tmp_path):
    spec = _spec_com_dut_e_task(task_name="MainTask", existing=False)
    plano = build_authoring_plan(spec).plan
    projeto, _c = _arvore()          # sem Task Configuration
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano,
                                 projeto=projeto,
                                 safety=_fase_com_dut_e_task(),
                                 escopo_extra={"DutType": FakeDutType})
    assert resultado["status"] == probe46.STATUS_TARGET_NOT_FOUND
    assert safety.requested == []


def test_chamada_IDIOMATICA_para_task_QUE_NAO_E_A_DO_PERFIL_reprova(tmp_path):
    """A recusa que impede o pior defeito silencioso desta fabrica.

    O caminho idiomatico escreve em `UserPrg`, que roda pela cadeia da
    `MainTask`. Se um plano pedisse "TaskNova chama PRG_X" POR ALI, o projeto
    executaria PRG_X no ciclo ERRADO -- e compilaria limpo.

    O planner de hoje nao emite isso: ele roteia por task. O plano aqui e
    fabricado A MAO justamente porque o executor nao pode depender disso -- ele
    recebe um artefato, e artefato se confere."""
    spec = _spec_com_dut_e_task(task_name="TaskNova", existing=False)
    plano = build_authoring_plan(spec).plan
    trocados = 0
    for passo in plano["steps"]:
        if passo["operation"] == "bind_program_to_task":
            passo["operation"] = "create_program_call"
            trocados += 1
    assert trocados == 1
    projeto, _c = _arvore_com_taskconfig()
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano,
                                 projeto=projeto,
                                 safety=_fase_com_vinculo_de_task(),
                                 escopo_extra={"DutType": FakeDutType})
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    texto = " ".join(resultado["problems"])
    assert "TaskNova" in texto and "UserPrg" in texto
    assert safety.requested == []


def test_vincular_a_task_QUE_O_PLANO_NAO_CRIA_reprova(tmp_path):
    """O espelho da recusa acima. Numa task preexistente ninguem leu a lista, e
    acrescentar no fim dela mudaria a ordem de execucao de um projeto que nao
    foi gerado aqui."""
    spec = _spec_com_dut_e_task(task_name="TaskNova", existing=False)
    plano = build_authoring_plan(spec).plan
    plano["steps"] = [p for p in plano["steps"]
                      if p["operation"] != "create_task"]
    projeto, _c = _arvore_com_taskconfig()
    resultado, _p, safety = _run(tmp_path, spec=spec, plano=plano,
                                 projeto=projeto,
                                 safety=_fase_com_vinculo_de_task(),
                                 escopo_extra={"DutType": FakeDutType})
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    texto = " ".join(resultado["problems"])
    assert "TaskNova" in texto and "preexistente" in texto
    assert safety.requested == []


def test_a_task_criada_recebe_o_programa_na_PROPRIA_lista(tmp_path):
    """A cadeia que W6 nao tinha: criar a task E encher a task. `UserPrg` fica
    intacta -- o programa nao entra na cadeia da MainTask por engano."""
    spec = _spec_com_dut_e_task(task_name="TaskNova", existing=False)
    projeto, container = _arvore_com_taskconfig()
    resultado, projeto, safety = _run_prova(
        tmp_path, spec, projeto=projeto, safety=_fase_com_vinculo_de_task())
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    cfg = [n for n in projeto._filhos[1]._filhos[0]._filhos[0]._filhos
           if getattr(n, "is_task_configuration", False)][0]
    task = [n for n in cfg._filhos if n.get_name(None) == "TaskNova"][0]
    assert list(task.pous) == [("PRG_FAB", None)]
    assert "add" in safety.requested
    # A POU do perfil nao foi tocada: o vinculo foi pela lista da task.
    registro = [e for e in resultado["step_log"]
                if e["operation"] == "bind_program_to_task"][0]
    assert registro["pous_before"] == []
    assert registro["pous_after"] == ["PRG_FAB"]


def test_a_task_do_perfil_e_uma_constante_LITERAL():
    assert probe46.PROFILE_TASK_NAME == "MainTask"
    assert probe46.DUT_KIND_TO_MEMBER == {"STRUCT": "Structure",
                                          "ENUM": "Enumeration"}


# =============================================================================
# configure_task -- a classe de mutacao NOVA
# =============================================================================

def test_configura_a_task_e_RELE_cada_propriedade(tmp_path):
    """A task nasce a `t#20ms` com prioridade 1 (docs/48 secao 4). A spec pede
    outra coisa, e o executor confere que o produto obedeceu."""
    spec = _spec_com_task_configurada(kind_of_task="Cyclic",
                                      interval="t#500ms", priority=20)
    resultado, projeto, safety = _run_configuracao(tmp_path, spec)
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    cfg = [n for n in projeto._filhos[1]._filhos[0]._filhos[0]._filhos
           if getattr(n, "is_task_configuration", False)][0]
    task = [n for n in cfg._filhos if n.get_name(None) == "TaskNova"][0]
    assert task.interval == "t#500ms"
    assert task.priority == "20"
    assert task.kind_of_task == "Cyclic"
    registro = [e for e in resultado["step_log"]
                if e["operation"] == "configure_task"][0]
    escritas = {e["property"]: e for e in registro["property_writes"]}
    # ANTES e DEPOIS medidos, propriedade por propriedade.
    assert escritas["interval"]["before"] == "t#20ms"
    assert escritas["interval"]["after"] == "t#500ms"
    assert escritas["priority"]["before"] == "1"
    assert escritas["priority"]["after"] == "20"


def test_a_ORDEM_de_escrita_e_a_do_stub_e_nao_a_da_spec(tmp_path):
    """O stub condiciona `interval` a `kind_of_task` ja ser Cyclic (L119-129).
    Escrever na ordem em que o autor digitou entregaria `interval` num momento
    em que o produto pode recusa-lo."""
    spec = _spec_com_task_configurada(priority=7, interval="t#250ms",
                                      interval_unit="ms",
                                      kind_of_task="Cyclic")
    resultado, _p, _s = _run_configuracao(tmp_path, spec)
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    registro = [e for e in resultado["step_log"]
                if e["operation"] == "configure_task"][0]
    assert [e["property"] for e in registro["property_writes"]] == [
        "kind_of_task", "interval", "interval_unit", "priority"]


def test_so_o_DECLARADO_e_escrito(tmp_path):
    """Ausente nao vira default nosso: quem nao declara fica com o que o
    produto der, e docs/48 secao 4 diz o que isso significa."""
    spec = _spec_com_task_configurada(priority=15)
    resultado, projeto, safety = _run_configuracao(tmp_path, spec)
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    registro = [e for e in resultado["step_log"]
                if e["operation"] == "configure_task"][0]
    assert [e["property"] for e in registro["property_writes"]] == ["priority"]
    assert safety.requested.count("set:priority") == 1
    for nao_pedido in ("set:interval", "set:kind_of_task", "set:interval_unit"):
        assert nao_pedido not in safety.requested


def test_task_SEM_parametro_declarado_nao_gera_o_passo(tmp_path):
    spec = _spec_com_task_configurada()
    plano = build_authoring_plan(spec).plan
    assert all(p["operation"] != "configure_task" for p in plano["steps"])
    assert not [n for n in plano["required_allowlist"] if n.startswith("set:")]


def test_ATRIBUICAO_QUE_NAO_PEGA_reprova(tmp_path):
    """O modo de falha proprio desta classe, e o unico que um metodo nao tem.

    Um metodo que nao funciona levanta; um campo simplesmente continua com o
    valor antigo, e o projeto sai com o tempo errado -- compilando limpo. Sem a
    releitura, isto passaria como sucesso."""
    spec = _spec_com_task_configurada(interval="t#500ms")
    resultado, _p, safety = _run_configuracao(tmp_path, spec, surda=True)
    assert resultado["status"] == probe46.STATUS_MUTATION_FAILED
    texto = " ".join(resultado["problems"])
    assert "nao pegou" in texto and "t#500ms" in texto
    # A guarda FOI pedida: a recusa e da verificacao, e nao da autorizacao.
    assert "set:interval" in safety.requested


def test_sem_a_propriedade_na_allowlist_a_escrita_e_RECUSADA(tmp_path):
    """A allowlist e por PROPRIEDADE. Uma fase que autorize o intervalo nao
    autoriza a prioridade -- um nome unico para a operacao inteira seria a
    abertura ampla com outro nome."""
    spec = _spec_com_task_configurada(interval="t#500ms", priority=20)
    fase = FakeSafety(phase="W9_PROVE_TASK_TIMING",
                      allowed=("create_gvl", "create_program", "create_task",
                               "add", "replace", "save_as", "set:interval"))
    resultado, _p, _s = _run_configuracao(tmp_path, spec, safety=fase)
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert "set:priority" in " ".join(resultado["problems"])


def test_configurar_task_PREEXISTENTE_reprova(tmp_path):
    """Mesmo espelho do vinculo: reescrever o tempo de uma task que ja estava
    no projeto mudaria o comportamento de algo que nao foi gerado aqui."""
    spec = _spec_com_task_configurada(interval="t#500ms")
    plano = build_authoring_plan(spec).plan
    plano["steps"] = [p for p in plano["steps"]
                      if p["operation"] != "create_task"]
    projeto, _c = _arvore_com_taskconfig()
    resultado, _p, safety = _run(
        tmp_path, spec=spec, plano=plano, projeto=projeto,
        safety=_fase_com_configuracao(),
        escopo_extra={"DutType": FakeDutType, "KindOfTask": FakeKindOfTask})
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert "TaskNova" in " ".join(resultado["problems"])
    assert safety.requested == []


def test_sem_o_enum_no_escopo_reprova_ANTES_de_escrever(tmp_path):
    """`KindOfTask` ausente e precondicao, e nao excecao no meio da cadeia."""
    spec = _spec_com_task_configurada(kind_of_task="Cyclic")
    projeto, _c = _arvore_com_taskconfig()
    plano = build_authoring_plan(spec).plan
    resultado, _p, _s = _run(tmp_path, spec=spec, plano=plano, projeto=projeto,
                             safety=_fase_com_configuracao(),
                             escopo_extra={"DutType": FakeDutType})
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert "KindOfTask" in " ".join(resultado["problems"])


# =============================================================================
# selecao semantica do container -- fase R0b
# =============================================================================

def _arvore_com_cartoes(cartoes):
    """A mesma arvore, com `cartoes` cartoes de I/O inseridos ANTES do
    `Plc Logic` -- que e o que a troca de projeto-base de 2026-07-31 fez, e o
    que desloca todos os indices abaixo do `Device`."""
    container = FakeContainer(filhos=[
        FakeNode("UserPOUs", "pasta", filhos=[
            FakeNode("UserPrg", POU_GUID, declaracao="PROGRAM UserPrg",
                     implementacao="")]),
    ])
    plc = FakeNode("Plc Logic", "plc", filhos=[container])
    filhos_device = [FakeNode("Cartao_%d" % i, "io") for i in range(cartoes)]
    filhos_device.append(plc)
    device = FakeNode("Device", "device", filhos=filhos_device)
    projeto = FakeProject([FakeNode("Project Settings", "cfg"), device])
    return projeto, container


class NoIlegivel(FakeNode):
    """Um no cujo nome nao pode ser lido -- o que o binding CLR faz quando o
    objeto e transiente ou o proxy expirou."""

    def get_name(self, _r):
        raise RuntimeError("COMException: objeto indisponivel")


def test_a_identidade_posicional_saiu_do_executor():
    """Gate da R0b: nenhum caminho de escrita depende de `node_path`.

    A constante em si nao existe mais. O teste e por ausencia porque foi a
    presenca dela que a `CURRENT_STATUS` listava como divida -- reintroduzi-la
    reprova aqui, com nome."""
    assert not hasattr(probe46, "CONTAINER_NODE_PATH")


def test_o_vocabulario_de_selecao_nao_divergiu_do_host():
    """Mesma regra do teste de vocabulario do planner: dois runtimes, uma
    linguagem. CPython 3 no host, IronPython 2.7 no probe, sem import entre
    eles -- a duplicacao e legitima, divergir em silencio nao e."""
    from mastertool_bridge.templates.selector import SELECTOR_DIAGNOSTICS
    assert probe46.SELECTOR_DIAGNOSTICS == SELECTOR_DIAGNOSTICS


@pytest.mark.parametrize("cartoes", [1, 3, 7])
def test_cartao_de_io_desloca_indices_e_a_execucao_continua(tmp_path, cartoes):
    """A prova da fase, no executor e nao so no modulo puro: com cartoes sob o
    `Device`, `root/1/0/0` deixaria de apontar para o `Application`, e o plano
    executa do mesmo jeito."""
    projeto, _c = _arvore_com_cartoes(cartoes)
    resultado, _p, _s = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe46.STATUS_EXECUTED
    selecao = resultado["container_selection"]
    assert selecao["diagnostic"] == probe46.SELECTOR_DIAG_RESOLVED
    # O node_path do container MUDOU com os cartoes, e a execucao nao mudou:
    # e a demonstracao de que ele virou diagnostico, nao identidade.
    assert selecao["candidates"] == ["root/1/%d/0" % cartoes]


def test_dois_containers_recusam_antes_de_qualquer_escrita(tmp_path):
    projeto, _c = _arvore_com_cartoes(0)
    device = projeto._filhos[1]
    device._filhos.append(FakeNode("Plc Logic", "plc", filhos=[FakeContainer()]))

    resultado, _p, safety = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert resultado["container_selection"]["diagnostic"] == \
        probe46.SELECTOR_DIAG_AMBIGUOUS
    assert len(resultado["container_selection"]["candidates"]) == 2
    # O ponto do gate: a recusa acontece ANTES de o gate de escrita ser tocado.
    assert safety.requested == []


def test_container_ausente_recusa_com_nome_proprio(tmp_path):
    projeto = FakeProject([FakeNode("Project Settings", "cfg")])
    resultado, _p, safety = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    assert resultado["container_selection"]["diagnostic"] == \
        probe46.SELECTOR_DIAG_NO_MATCH
    assert safety.requested == []


def test_no_ilegivel_recusa_mesmo_com_o_container_encontrado(tmp_path):
    """A recusa sutil: o `Application` foi achado, e mesmo assim a execucao
    para. Com um no que nao pode ser lido, ninguem pode afirmar que nao existe
    um segundo container -- e escrever no primeiro seria apostar."""
    projeto, _c = _arvore_com_cartoes(0)
    projeto._filhos.append(NoIlegivel("?", "?"))

    resultado, _p, safety = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED
    selecao = resultado["container_selection"]
    assert selecao["diagnostic"] == probe46.SELECTOR_DIAG_UNREADABLE
    assert selecao["unreadable"] == 1
    # O candidato continua reportado -- recusar nao e esconder o que se viu.
    assert selecao["candidates"] == ["root/1/0/0"]
    assert safety.requested == []


def test_a_selecao_entra_no_artefato_tambem_quando_recusa(tmp_path):
    """Sem isto, uma recusa nao diz onde o probe procurou -- e essa e a
    informacao que decide se o template mudou ou se o seletor ficou fraco."""
    projeto = FakeProject([FakeNode("Project Settings", "cfg")])
    resultado, _p, _s = _run(tmp_path, projeto=projeto)
    selecao = resultado["container_selection"]
    assert selecao["visited"] > 0
    assert selecao["selector"]["name"] == "Application"
    assert selecao["selector"]["expected_cardinality"] == 1
    assert selecao["diagnostic"] in probe46.SELECTOR_DIAGNOSTICS


def test_a_selecao_do_container_vai_para_o_ARQUIVO_e_nao_so_a_memoria(tmp_path):
    """ACHADO do piloto de 2026-08-02.

    As tres runs recusaram com "1 no ilegivel" e o artefato em disco nao dizia
    QUAL no. O diagnostico existia no dicionario `result` -- e os testes
    conferiam justamente esse dicionario, nao o arquivo. `execution-manifest`
    tem lista FIXA de campos, e `container_selection` nao estava nela.
    """
    import io as _io
    import json as _json

    projeto = FakeProject([FakeNode("Project Settings", "cfg")])   # sem container
    resultado, _p, _s = _run(tmp_path, projeto=projeto)
    assert resultado["status"] == probe46.STATUS_PRECONDITION_FAILED

    # `write_artifacts` é o gravador real — quem o chama é o `main`, e o teste
    # exercita `run_executor`. Chamá-lo aqui é o que faz este teste conferir o
    # ARQUIVO, que é justamente o que faltava.
    escritos = probe46.write_artifacts(resultado, file_io)
    assert "execution-manifest.json" in escritos

    manifesto = _json.loads(_io.open(
        os.path.join(resultado["artifacts_dir"], "execution-manifest.json"),
        encoding="utf-8").read())
    assert "container_selection" in manifesto
    selecao = manifesto["container_selection"]
    assert selecao["diagnostic"] == probe46.SELECTOR_DIAG_NO_MATCH
    assert selecao["visited"] > 0
    assert selecao["selector"]["name"] == "Application"


# =============================================================================
# R2 -- alteracao de objeto PREEXISTENTE, com hash anterior medido
# =============================================================================

def _spec_com_modificacao(sha_anterior, texto_novo="xNovo := TRUE;"):
    return {
        "schema_version": 1,
        "template": {"id": "TemplateExemplo_v1", "sha256": "5966257" + "0" * 57},
        "modifications": [{
            "family": "programs", "name": "UserPrg", "field": "implementation",
            "expected_before_sha256": sha_anterior, "text": texto_novo,
        }],
    }


def _sha_do_texto(texto):
    import hashlib
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def test_alteracao_de_preexistente_confere_o_texto_ANTERIOR(tmp_path):
    """O invariante da fase R2. Sem esta leitura, `expected_before_sha256`
    seria decorativo e a alteração seria escrita cega."""
    atual = "// implementacao antiga\n"
    projeto, _c = _arvore(userprg_impl=atual)
    spec = _spec_com_modificacao(_sha_do_texto(atual))

    resultado, projeto_final, safety = _run(
        tmp_path, spec=spec, projeto=projeto,
        safety=FakeSafety(allowed=("replace", "save_as")))
    assert resultado["status"] == probe46.STATUS_EXECUTED, resultado["problems"]
    conferidos = [p for p in resultado["step_log"]
                  if p.get("outcome") == "before_hash_verified"]
    assert len(conferidos) == 1
    assert conferidos[0]["before_sha256_observed"] == _sha_do_texto(atual)


def test_objeto_alterado_desde_a_medicao_RECUSA(tmp_path):
    """O caso que a fase existe para pegar: alguém editou o objeto entre a
    leitura e a execução. Sobrescrever descartaria conteúdo que ninguém
    examinou."""
    projeto, _c = _arvore(userprg_impl="// alguem editou depois da medicao\n")
    spec = _spec_com_modificacao(_sha_do_texto("// o que foi medido\n"))

    resultado, _p, safety = _run(
        tmp_path, spec=spec, projeto=projeto,
        safety=FakeSafety(allowed=("replace", "save_as")))
    assert resultado["status"] == probe46.STATUS_BEFORE_HASH_MISMATCH
    assert any("mudou desde a medicao" in p for p in resultado["problems"])
    # E nada foi escrito.
    assert "replace" not in safety.requested


def test_o_status_de_hash_anterior_e_DIFERENTE_do_de_texto_novo():
    """As duas divergências pedem ações opostas: uma manda remedir o projeto,
    a outra manda refazer o plano."""
    assert (probe46.STATUS_BEFORE_HASH_MISMATCH
            != probe46.STATUS_TEXT_HASH_MISMATCH)
    assert probe46.STATUS_BEFORE_HASH_MISMATCH in probe46.ALL_STATUSES
    assert probe46.EXIT_BY_STATUS[probe46.STATUS_BEFORE_HASH_MISMATCH] == 2


def test_procedencia_medida_sem_hash_recusa(tmp_path):
    """Declarar `measured` sem o hash seria pior que não declarar: promete uma
    conferência que não acontece."""
    atual = "// antiga\n"
    projeto, _c = _arvore(userprg_impl=atual)
    spec = _spec_com_modificacao(_sha_do_texto(atual))
    plano = build_authoring_plan(spec).plan
    for passo in plano["steps"]:
        if passo.get("expected_before_kind") == "measured":
            passo["expected_before_sha256"] = None

    resultado, _p, _s = _run(tmp_path, spec=spec, plano=plano, projeto=projeto,
                             safety=FakeSafety(allowed=("replace", "save_as")))
    assert resultado["status"] == probe46.STATUS_BEFORE_HASH_MISMATCH

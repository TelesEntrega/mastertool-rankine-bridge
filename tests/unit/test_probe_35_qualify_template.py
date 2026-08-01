"""Testes de `probes/35_qualify_template_readonly.py`, com dubles ESTRITOS e
verificacao estatica (AST).

Nenhuma API real do MasterTool e importada ou chamada. O duble de scanner
LEVANTA se `run_qualification` tentar qualquer coisa alem de `.scan(project)`
sobre ele -- o nucleo de classificacao (`analyze`) e testado direto, sem
nenhum duble de CLR, porque opera sobre `flat_nodes` ja serializado (a mesma
saida de `read_only_project_scanner.flatten_tree`).
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

PROBE35_PATH = os.path.join(_MASTERTOOL_DIR, "probes",
                            "35_qualify_template_readonly.py")

APPLICATION_GUID = "639b491f-5557-464c-af91-1471bac9f549"
GVL_GUID = "ffbfa93a-b94d-45fc-a329-229860183b1d"
POU_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"


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


probe35 = _load_module(PROBE35_PATH, "probe35_qualify")


# =============================================================================
# Constantes conferem com os dados medidos (docs/18, docs/32)
# =============================================================================

def test_constantes_conferem_com_dados_medidos():
    assert probe35.APPLICATION_TYPE_GUID == APPLICATION_GUID
    assert probe35.GVL_TYPE_GUID == GVL_GUID
    assert probe35.POU_TYPE_GUID == POU_GUID
    assert probe35.CONFLICT_TARGET_NAMES == ("GVL_AI_TESTE", "PRG_AI_TESTE")


# =============================================================================
# classify_type_guid
# =============================================================================

def test_classify_type_guid_conhecido():
    assert probe35.classify_type_guid(APPLICATION_GUID) == "application"
    assert probe35.classify_type_guid(GVL_GUID) == "gvl"
    assert probe35.classify_type_guid(POU_GUID) == "pou_or_dut_leaf_undistinguished"


def test_classify_type_guid_desconhecido_nunca_inventa_rotulo():
    assert probe35.classify_type_guid("guid-nunca-visto") == "unclassified"
    assert probe35.classify_type_guid(None) == "unclassified"


# =============================================================================
# resolve_application
# =============================================================================

def test_resolve_application_unico():
    flat = [
        {"node_id": "root", "parent_node_id": None, "name": None, "type_guid": None},
        {"node_id": "root/1/0/0", "parent_node_id": "root/1/0",
         "name": "Application", "type_guid": APPLICATION_GUID},
    ]
    resultado = probe35.resolve_application(flat)
    assert resultado["status"] == "resolved"
    assert resultado["node_path"] == "root/1/0/0"


def test_resolve_application_ausente():
    flat = [{"node_id": "root", "parent_node_id": None, "name": None, "type_guid": None}]
    resultado = probe35.resolve_application(flat)
    assert resultado["status"] == "not_found"
    assert resultado["node_path"] is None


def test_resolve_application_ambiguo():
    flat = [
        {"node_id": "root/1/0/0", "parent_node_id": "root/1/0",
         "name": "Application", "type_guid": APPLICATION_GUID},
        {"node_id": "root/2/0/0", "parent_node_id": "root/2/0",
         "name": "Application", "type_guid": APPLICATION_GUID},
    ]
    resultado = probe35.resolve_application(flat)
    assert resultado["status"] == "ambiguous"
    assert resultado["node_path"] is None
    assert len(resultado["matches"]) == 2


def test_resolve_application_nome_bate_mas_type_guid_nao():
    """Nome 'Application' sozinho nao basta -- outro objeto poderia ter esse
    nome sem ser o container real."""
    flat = [{"node_id": "root/9", "parent_node_id": "root",
            "name": "Application", "type_guid": "guid-qualquer"}]
    resultado = probe35.resolve_application(flat)
    assert resultado["status"] == "not_found"


# =============================================================================
# detect_name_conflicts / has_any_conflict
# =============================================================================

def test_detect_name_conflicts_sem_conflito():
    flat = [{"node_id": "root/1", "parent_node_id": "root",
            "name": "GVL_OUTRA", "type_guid": GVL_GUID}]
    conflitos = probe35.detect_name_conflicts(flat)
    assert conflitos == {"GVL_AI_TESTE": [], "PRG_AI_TESTE": []}
    assert probe35.has_any_conflict(conflitos) is False


def test_detect_name_conflicts_com_conflito():
    flat = [{"node_id": "root/1", "parent_node_id": "root",
            "name": "GVL_AI_TESTE", "type_guid": GVL_GUID}]
    conflitos = probe35.detect_name_conflicts(flat)
    assert conflitos["GVL_AI_TESTE"] == ["root/1"]
    assert conflitos["PRG_AI_TESTE"] == []
    assert probe35.has_any_conflict(conflitos) is True


# =============================================================================
# children_names_of_named_node
# =============================================================================

def test_children_names_resolvido():
    flat = [
        {"node_id": "root/1", "parent_node_id": "root",
         "name": "Library Manager", "type_guid": "x"},
        {"node_id": "root/1/0", "parent_node_id": "root/1",
         "name": "Standard", "type_guid": "y"},
        {"node_id": "root/1/1", "parent_node_id": "root/1",
         "name": "IoStandard", "type_guid": "y"},
    ]
    resultado = probe35.children_names_of_named_node(flat, "Library Manager")
    assert resultado["status"] == "resolved"
    assert sorted(resultado["names"]) == ["IoStandard", "Standard"]


def test_children_names_no_ausente():
    resultado = probe35.children_names_of_named_node([], "Library Manager")
    assert resultado["status"] == "not_found"
    assert resultado["names"] == []


def test_children_names_no_ambiguo():
    flat = [
        {"node_id": "root/1", "parent_node_id": "root",
         "name": "Task Configuration", "type_guid": "x"},
        {"node_id": "root/2", "parent_node_id": "root",
         "name": "Task Configuration", "type_guid": "x"},
    ]
    resultado = probe35.children_names_of_named_node(flat, "Task Configuration")
    assert resultado["status"] == "ambiguous"


# =============================================================================
# compute_persistent_tree_sha256 -- deterministico
# =============================================================================

def test_persistent_tree_sha256_deterministico_e_sensivel_a_ordem_de_entrada():
    flat_a = [
        {"node_id": "root/1", "name": "A", "type_guid": "g1"},
        {"node_id": "root/0", "name": "B", "type_guid": "g2"},
    ]
    flat_b = list(reversed(flat_a))
    assert probe35.compute_persistent_tree_sha256(flat_a) == \
        probe35.compute_persistent_tree_sha256(flat_b)


def test_persistent_tree_sha256_muda_com_o_conteudo():
    flat_a = [{"node_id": "root/1", "name": "A", "type_guid": "g1"}]
    flat_b = [{"node_id": "root/1", "name": "A", "type_guid": "g2"}]
    assert probe35.compute_persistent_tree_sha256(flat_a) != \
        probe35.compute_persistent_tree_sha256(flat_b)


# =============================================================================
# analyze -- nucleo puro
# =============================================================================

def _flat_com_application(extra=None):
    flat = [
        {"node_id": "root/1/0/0", "parent_node_id": "root/1/0",
         "name": "Application", "type_guid": APPLICATION_GUID},
    ]
    flat.extend(extra or [])
    return flat


def test_analyze_qualified_sem_conflito():
    resultado = probe35.analyze(_flat_com_application(), "complete",
                                {"slug": "TemplateExemplo_v1", "sha256": "a" * 64},
                                {"file_version": "4.1.0.11"})
    assert resultado["status"] == probe35.STATUS_QUALIFIED
    assert resultado["application"]["status"] == "resolved"
    assert resultado["name_conflicts"]["GVL_AI_TESTE"] == []
    assert resultado["registry_candidate"]["application_node_path"] == "root/1/0/0"
    assert resultado["registry_candidate"]["template_id"] == "TemplateExemplo_v1-" + "a" * 12


def test_analyze_com_conflito_detectado():
    extra = [{"node_id": "root/1/0/0/5", "parent_node_id": "root/1/0/0",
             "name": "GVL_AI_TESTE", "type_guid": GVL_GUID}]
    resultado = probe35.analyze(_flat_com_application(extra), "complete",
                                {"slug": "TemplateExemplo_v1", "sha256": "b" * 64},
                                {"file_version": "4.1.0.11"})
    assert resultado["status"] == probe35.STATUS_NAME_CONFLICT_DETECTED
    assert resultado["name_conflicts"]["GVL_AI_TESTE"] == ["root/1/0/0/5"]
    # o registry candidate ainda e montado -- a informacao de conflito nao
    # impede a qualificacao estrutural, so bloqueia W1.4.
    assert resultado["registry_candidate"] is not None


def test_analyze_application_nao_encontrado():
    resultado = probe35.analyze([{"node_id": "root", "name": None, "type_guid": None}],
                                "complete", {}, {})
    assert resultado["status"] == probe35.STATUS_APPLICATION_NOT_FOUND
    assert resultado["registry_candidate"] is None


def test_analyze_application_ambiguo():
    flat = [
        {"node_id": "root/1", "name": "Application", "type_guid": APPLICATION_GUID},
        {"node_id": "root/2", "name": "Application", "type_guid": APPLICATION_GUID},
    ]
    resultado = probe35.analyze(flat, "complete", {}, {})
    assert resultado["status"] == probe35.STATUS_APPLICATION_AMBIGUOUS


def test_analyze_arvore_truncada_nao_avanca_para_resolucao():
    resultado = probe35.analyze(_flat_com_application(), "truncated", {}, {})
    assert resultado["status"] == probe35.STATUS_TREE_TRUNCATED
    assert resultado["application"] is None


def test_analyze_sem_flat_nodes_e_fatal():
    resultado = probe35.analyze([], "complete", {}, {})
    assert resultado["status"] == probe35.STATUS_FATAL


def test_analyze_compiler_version_e_EVIDENCIA_e_nao_valor():
    """`compiler_version` deixou de ser escalar. A lacuna tem status, origem e
    razao -- em vez de um `None` que o proximo leitor teria de interpretar."""
    resultado = probe35.analyze(_flat_com_application(), "complete",
                                {"slug": "x", "sha256": "c" * 64}, {})
    evidencia = resultado["compiler_version"]
    assert evidencia["status"] == probe35.EVIDENCE_UNRESOLVED
    assert evidencia["value"] is None
    assert evidencia["source"] == probe35.COMPILER_VERSION_SOURCE_PROBE
    assert "IScriptProjectSettings2" in evidencia["reason"]
    assert "IScriptProjectSettings2" in resultado["compiler_version_gap"]


def test_unresolved_nunca_vira_string_vazia():
    """String vazia e `None` sao os dois jeitos classicos de uma lacuna
    atravessar fronteira se passando por dado. Nenhum dos dois pode produzir
    `measured`."""
    for valor in (None, "", u""):
        evidencia = probe35.build_compiler_version_evidence(valor, "razao")
        assert evidencia["status"] == probe35.EVIDENCE_UNRESOLVED
        assert evidencia["value"] is None
        assert evidencia["reason"]


def test_valor_medido_produz_evidencia_measured():
    """A outra direcao: se um dia houver leitura literal, a mesma funcao
    produz `measured` -- o mecanismo nao foi desenhado so para falhar."""
    evidencia = probe35.build_compiler_version_evidence("3.5.18.60", None)
    assert evidencia["status"] == probe35.EVIDENCE_MEASURED
    assert evidencia["value"] == "3.5.18.60"
    assert evidencia["reason"] is None


def test_lacuna_bloqueia_elegibilidade_mas_NAO_invalida_a_sessao():
    """A distincao que o usuario determinou: template qualificado
    estruturalmente NAO e o mesmo que template elegivel para autoria. Com
    tudo o mais medido, a sessao read-only vale -- o que a lacuna impede e a
    ELEGIBILIDADE."""
    resultado = probe35.analyze(_flat_com_application(), "complete",
                                {"slug": "x", "sha256": "e" * 64}, {})
    assert resultado["qualification_status"] == probe35.QUALIFICATION_WITH_BLOCKERS
    assert resultado["authoring_eligible"] is False
    assert probe35.BLOCKER_COMPILER_VERSION in resultado["blocking_issues"]
    # E, crucialmente, NAO virou fatal: a arvore foi medida.
    assert resultado["status"] != probe35.STATUS_FATAL
    assert resultado["application"] is not None
    assert resultado["persistent_tree_sha256"]


def test_elegibilidade_e_DERIVADA_e_nunca_declarada():
    """Ninguem escreve `authoring_eligible = True` a mao. Ele e consequencia
    de nao haver bloqueio -- e o unico caminho para True e a evidencia estar
    `measured` e nao haver conflito de nome."""
    medida = probe35.build_compiler_version_evidence("3.5.18.60", None)
    status, elegivel, bloqueios = probe35.derive_qualification(
        medida, scan_ok=True, conflicts_found=False)
    assert (status, elegivel, bloqueios) == (probe35.QUALIFICATION_QUALIFIED, True, [])

    status, elegivel, bloqueios = probe35.derive_qualification(
        medida, scan_ok=True, conflicts_found=True)
    assert elegivel is False and "object_name_conflict" in bloqueios

    lacuna = probe35.build_compiler_version_evidence(None, "sem acessor")
    status, elegivel, bloqueios = probe35.derive_qualification(
        lacuna, scan_ok=True, conflicts_found=False)
    assert elegivel is False
    assert bloqueios == [probe35.BLOCKER_COMPILER_VERSION]

    # Varredura ruim nao pode virar "qualificado com bloqueio": e outra coisa.
    status, elegivel, _ = probe35.derive_qualification(
        medida, scan_ok=False, conflicts_found=False)
    assert status == probe35.QUALIFICATION_NOT_QUALIFIED and elegivel is False


def test_registry_candidate_carrega_a_elegibilidade():
    """O candidato que vai para o registry precisa levar o veredito junto; um
    candidato que so levasse a medicao deixaria a decisao para quem o le."""
    resultado = probe35.analyze(_flat_com_application(), "complete",
                                {"slug": "x", "sha256": "f" * 64}, {})
    candidato = resultado["registry_candidate"]
    assert candidato["authoring_eligible"] is False
    assert candidato["qualification_status"] == probe35.QUALIFICATION_WITH_BLOCKERS
    assert probe35.BLOCKER_COMPILER_VERSION in candidato["blocking_issues"]
    assert candidato["compiler_version"]["status"] == probe35.EVIDENCE_UNRESOLVED


def test_library_manager_resolvido_e_VAZIO_e_lacuna_e_nao_medicao():
    """ACHADO NA RUN-010: o no Library Manager foi ALCANCADO (status
    `resolved`, node_id root/1/0/0/0) e devolveu ZERO filhos, num projeto
    industrial real com cartoes de I/O. Lista vazia le como "medido: nenhuma
    biblioteca"; o que se tem e "nao mensuravel por este caminho". Sao coisas
    opostas para quem decide, e a diferenca so existe se alguem escrever."""
    libs, houve_lacuna = probe35.classify_libraries(
        {"status": "resolved", "node_id": "root/1/0/0/0", "names": []})
    assert houve_lacuna is True
    assert libs["status"] == "resolved_but_empty"
    assert "implausivel" in libs["gap"]


def test_library_manager_COM_filhos_nao_e_lacuna():
    """A outra direcao: com bibliotecas de verdade nao ha lacuna. Sem isto, a
    guarda poderia estar simplesmente bloqueando sempre e ninguem notaria."""
    libs, houve_lacuna = probe35.classify_libraries(
        {"status": "resolved", "node_id": "root/1/0/0/0",
         "names": ["Standard", "Util"]})
    assert houve_lacuna is False
    assert "gap" not in libs
    assert libs["names"] == ["Standard", "Util"]


def test_library_manager_ausente_tambem_e_lacuna():
    """No nao encontrado tambem nao e medicao -- e o terceiro caso, e ele nao
    pode virar 'nenhuma biblioteca' por omissao."""
    libs, houve_lacuna = probe35.classify_libraries(
        {"status": "not_found", "node_id": None, "names": []})
    assert houve_lacuna is True


def test_lacuna_de_biblioteca_BLOQUEIA_elegibilidade():
    """Integrado: qualquer lacuna de biblioteca impede autoria, pelo mesmo
    motivo que a compiler version -- autoria controlada sobre template cujo
    conjunto de bibliotecas e desconhecido nao e controlada."""
    resultado = probe35.analyze(_flat_com_application(), "complete",
                                {"slug": "x", "sha256": "a" * 64}, {})
    assert probe35.BLOCKER_LIBRARIES in resultado["blocking_issues"]
    assert resultado["authoring_eligible"] is False


def test_completion_carrega_a_ELEGIBILIDADE_junto_do_status():
    """ACHADO NA RUN-010, e a razao deste teste existir: o completion trazia
    `status: "qualified"` sem `authoring_eligible`, e o wrapper imprimiu
    "APROVADO" para um template inelegivel. Um artefato de conclusao que
    precisa de outro arquivo ao lado para nao ser lido errado nao esta
    concluindo nada."""
    resultado = probe35.analyze(_flat_com_application(), "complete",
                                {"slug": "x", "sha256": "b" * 64}, {})
    completion = probe35.build_completion({
        "status": resultado["status"], "exit_code": 0, "analysis": resultado,
        "project": {}, "scan_status": "complete", "observed": {},
        "problems": [], "mutating_calls": [], "finished_at": None})
    for campo in ("qualification_status", "authoring_eligible", "blocking_issues"):
        assert campo in completion, campo
    assert completion["authoring_eligible"] is False
    assert completion["libraries"] is not None
    assert completion["tasks"] is not None


def test_o_probe_nao_conhece_set_compilerversion_to_newest():
    """Fallback para compiler mais novo e proibido por contrato. A ausencia e
    verificada no fonte, e nao apenas prometida."""
    fonte = io.open(probe35.__file__.replace(".pyc", ".py"), encoding="utf-8").read() \
        if hasattr(probe35, "__file__") else ""
    assert "set_compilerversion_to_newest" not in fonte


def test_analyze_persistent_tree_sha256_caveat_declarado():
    resultado = probe35.analyze(_flat_com_application(), "complete",
                                {"slug": "x", "sha256": "d" * 64}, {})
    assert "is_transient_object" in resultado["persistent_tree_sha256_caveat"]


def test_apenas_status_de_sucesso_tem_exit_zero():
    for status in probe35.ALL_STATUSES:
        esperado = status in probe35.SUCCESS_STATUSES
        assert (probe35.EXIT_BY_STATUS[status] == 0) is esperado, status


# =============================================================================
# run_qualification -- orquestracao, com duble ESTRITO de scanner
# =============================================================================

class ForbiddenCallTouched(AssertionError):
    pass


class FakeScanner(object):
    """So expoe `.scan(project)`. Qualquer outro metodo levanta -- prova de
    que `run_qualification` nao chama mais nada do scanner alem do contrato
    ja usado por probes/21."""
    def __init__(self, scan_result):
        self._scan_result = scan_result

    def scan(self, project):
        return self._scan_result

    def __getattr__(self, nome):
        raise ForbiddenCallTouched("run_qualification acessou %r no scanner" % nome)


def _scan_result_ok(extra_children=None):
    application = {
        "node_id": "root/1/0/0", "parent_node_id": "root/1/0", "depth": 3, "index": 0,
        "identity": {
            "name": {"state": "confirmed", "value": "Application"},
            "type_guid": {"state": "confirmed", "value": APPLICATION_GUID},
            "object_guid": {"state": "confirmed", "value": "og-1"},
        },
        "children": list(extra_children or []),
    }
    root = {
        "node_id": "root", "parent_node_id": None, "depth": 0, "index": None,
        "identity": {}, "children": [application],
    }
    return {
        "tree": root,
        "errors": [],
        "limits": {"max_depth_reached": False, "max_total_nodes_reached": False,
                  "max_children_per_node_reached": False},
        "statistics": {"total_nodes": 2},
        "safety_declaration": {"read_only": True},
    }


class FakeProject(object):
    pass


class FakeProjectAccess(object):
    def __init__(self, path):
        self._path = path

    def get_primary_project(self, _globals):
        return FakeProject(), None

    def get_project_path(self, _project):
        return self._path


class FakeProbeCli(object):
    def find_arg(self, argv, name):
        return probe_cli.find_arg(argv, name)

    def validate_output_path(self, raw, repo_root, problems):
        return probe_cli.validate_output_path(raw, repo_root, problems)

    def runtime_identity(self):
        return {"executable": "MT9000.exe", "file_version": "4.1.0.11",
                "product_version": "4.1.0.11", "error": None}


def _make_project_file(tmp_path, name="TemplateExemplo v1.project", content=b"conteudo sintetico"):
    caminho = os.path.join(str(tmp_path), name)
    handle = open(caminho, "wb")
    try:
        handle.write(content)
    finally:
        handle.close()
    return caminho


def test_run_qualification_feliz(tmp_path):
    caminho = _make_project_file(tmp_path)
    argv = ["probe", "--output=" + os.path.join(str(tmp_path), "art")]
    resultado = probe35.run_qualification(
        {"projects": object()}, argv, FakeProjectAccess(caminho), file_io,
        FakeProbeCli(), scanner_factory=lambda: FakeScanner(_scan_result_ok()))
    assert resultado["status"] == probe35.STATUS_QUALIFIED
    assert resultado["exit_code"] == 0
    assert resultado["project"]["sha256"] is not None
    assert resultado["project"]["size_bytes"] == len(b"conteudo sintetico")
    assert resultado["analysis"]["application"]["node_path"] == "root/1/0/0"


def test_run_qualification_detecta_conflito(tmp_path):
    caminho = _make_project_file(tmp_path)
    conflito = {
        "node_id": "root/1/0/0/9", "parent_node_id": "root/1/0/0", "depth": 4, "index": 9,
        "identity": {
            "name": {"state": "confirmed", "value": "GVL_AI_TESTE"},
            "type_guid": {"state": "confirmed", "value": GVL_GUID},
            "object_guid": {"state": "confirmed", "value": "og-2"},
        },
        "children": [],
    }
    argv = ["probe", "--output=" + os.path.join(str(tmp_path), "art")]
    resultado = probe35.run_qualification(
        {"projects": object()}, argv, FakeProjectAccess(caminho), file_io,
        FakeProbeCli(),
        scanner_factory=lambda: FakeScanner(_scan_result_ok(extra_children=[conflito])))
    assert resultado["status"] == probe35.STATUS_NAME_CONFLICT_DETECTED
    assert resultado["exit_code"] == 3
    assert any("GVL_AI_TESTE" in p for p in resultado["problems"])


def test_run_qualification_sem_projeto_primario_e_fatal(tmp_path):
    class SemProjeto(object):
        def get_primary_project(self, _globals):
            return None, "sem projeto"

    argv = ["probe", "--output=" + os.path.join(str(tmp_path), "art")]
    resultado = probe35.run_qualification(
        {"projects": object()}, argv, SemProjeto(), file_io, FakeProbeCli(),
        scanner_factory=lambda: FakeScanner(_scan_result_ok()))
    assert resultado["status"] == probe35.STATUS_FATAL


def test_run_qualification_output_obrigatorio(tmp_path):
    caminho = _make_project_file(tmp_path)
    resultado = probe35.run_qualification(
        {"projects": object()}, ["probe"], FakeProjectAccess(caminho), file_io,
        FakeProbeCli(), scanner_factory=lambda: FakeScanner(_scan_result_ok()))
    assert resultado["status"] == probe35.STATUS_FATAL
    assert any("--output" in p for p in resultado["problems"])


def test_run_qualification_scanner_so_e_chamado_via_scan(tmp_path):
    """O duble levanta se qualquer atributo alem de `.scan` for tocado."""
    caminho = _make_project_file(tmp_path)
    argv = ["probe", "--output=" + os.path.join(str(tmp_path), "art")]
    resultado = probe35.run_qualification(
        {"projects": object()}, argv, FakeProjectAccess(caminho), file_io,
        FakeProbeCli(), scanner_factory=lambda: FakeScanner(_scan_result_ok()))
    assert resultado["status"] == probe35.STATUS_QUALIFIED


def test_run_qualification_arvore_truncada(tmp_path):
    caminho = _make_project_file(tmp_path)
    scan = _scan_result_ok()
    scan["limits"]["max_depth_reached"] = True
    argv = ["probe", "--output=" + os.path.join(str(tmp_path), "art")]
    resultado = probe35.run_qualification(
        {"projects": object()}, argv, FakeProjectAccess(caminho), file_io,
        FakeProbeCli(), scanner_factory=lambda: FakeScanner(scan))
    assert resultado["status"] == probe35.STATUS_TREE_TRUNCATED
    assert resultado["exit_code"] == 2


def test_artefatos_gravados(tmp_path):
    caminho = _make_project_file(tmp_path)
    saida = os.path.join(str(tmp_path), "art")
    argv = ["probe", "--output=" + saida]
    resultado = probe35.run_qualification(
        {"projects": object()}, argv, FakeProjectAccess(caminho), file_io,
        FakeProbeCli(), scanner_factory=lambda: FakeScanner(_scan_result_ok()))
    escritos = probe35.write_artifacts(resultado, file_io)
    assert "qualify-completion.json" in escritos
    assert "template-registry-candidate.json" in escritos
    presentes = os.listdir(saida)
    for nome in escritos:
        assert nome in presentes


def test_completion_is_success_acompanha_status(tmp_path):
    caminho = _make_project_file(tmp_path)
    argv = ["probe", "--output=" + os.path.join(str(tmp_path), "art")]
    resultado = probe35.run_qualification(
        {"projects": object()}, argv, FakeProjectAccess(caminho), file_io,
        FakeProbeCli(), scanner_factory=lambda: FakeScanner(_scan_result_ok()))
    completion = probe35.build_completion(resultado)
    assert completion["is_success"] is True
    assert completion["registry_candidate"]["application_node_path"] == "root/1/0/0"


# =============================================================================
# Verificacao estatica (AST) -- probe 35 e SOMENTE LEITURA
# =============================================================================

@pytest.fixture(scope="module")
def tree35():
    return ast.parse(io.open(PROBE35_PATH, encoding="utf-8").read())


def _method_calls(tree, nome):
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == nome]


# O RECEPTOR decide, nunca o nome do metodo: `.insert(...)` existe em `list`
# (ex.: `sys.path.insert(0, ...)`, presente neste proprio probe para montar
# o `sys.path`) E em `IScriptTextDocument`. Excluir receptores conhecidos e
# comprovadamente nao-proxy (aqui, `sys.path`) e a unica forma correta de
# aplicar esta guarda -- proibir o NOME inteiro reprovaria codigo legitimo.
_RECEPTORES_SEGUROS_CONHECIDOS = {
    "insert": (("sys", "path"),),
}


def _method_calls_sobre_proxy(tree, nome):
    seguros = _RECEPTORES_SEGUROS_CONHECIDOS.get(nome, ())
    encontrados = []
    for chamada in _method_calls(tree, nome):
        receptor = chamada.func.value
        if isinstance(receptor, ast.Attribute) and isinstance(receptor.value, ast.Name):
            caminho = (receptor.value.id, receptor.attr)
            if caminho in seguros:
                continue
        encontrados.append(chamada)
    return encontrados


MUTADORES_PROIBIDOS = (
    "create_gvl", "create_pou", "create_program", "create_folder", "create_dut",
    "create_function", "create_function_block", "create_interface",
    "create_persistentvars", "create_task", "create_task_configuration",
    "create_boot_application", "replace", "replace_line", "insert", "remove",
    "save", "save_as", "save_archive", "build", "rebuild", "clean",
    "import_xml", "import_native", "import_device", "rename", "move", "add",
    "unplug", "update", "set_gateway_and_ip_address", "remove_device",
    "set_compilerversion_to_newest", "download_missing_libraries",
    "remove_library", "add_library",
)


@pytest.mark.parametrize("metodo", MUTADORES_PROIBIDOS)
def test_probe_35_nao_contem_mutador(tree35, metodo):
    assert _method_calls_sobre_proxy(tree35, metodo) == [], (
        "probe 35 e read-only e nao pode chamar .%s() sobre proxy do "
        "MasterTool" % metodo)


def test_probe_35_receptor_de_lista_nao_e_confundido_com_mutador():
    """`.append(...)` existe em `list` E em `IScriptTextDocument` -- o
    RECEPTOR decide, nunca o nome. Este probe usa `.append` apenas sobre
    variaveis locais de lista (ex.: `found`, `matches`), nunca sobre um
    proxy do MasterTool. Prova textual: toda ocorrencia de `.append(` no
    arquivo tem, como receptor, um Name cujo identificador NAO e proxy
    conhecido de objeto do MasterTool (`project`, `container`, `document`,
    `text_document`, `obj`, `node`, `child_proxy`)."""
    fonte = io.open(PROBE35_PATH, encoding="utf-8").read()
    arvore = ast.parse(fonte)
    proxies_conhecidos = ("project", "container", "document", "text_document",
                          "obj", "node", "child_proxy", "proxy")
    for chamada in _method_calls(arvore, "append"):
        receptor = chamada.func.value
        if isinstance(receptor, ast.Name):
            assert receptor.id not in proxies_conhecidos, (
                "append() chamado sobre %r -- pode ser proxy do MasterTool, "
                "nao lista local" % receptor.id)


@pytest.mark.parametrize("nome", ["getattr", "setattr", "eval", "exec",
                                  "compile", "__import__", "vars", "locals"])
def test_probe_35_sem_acesso_dinamico(tree35, nome):
    encontrados = [n for n in ast.walk(tree35)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == nome]
    assert encontrados == []


def test_probe_35_sem_lambda_nem_fstring(tree35):
    lambdas = [n for n in ast.walk(tree35) if isinstance(n, ast.Lambda)]
    # `lambda: default_scanner_module.ReadOnlyProjectScanner(...)` e permitido
    # -- e uma factory de configuracao, nunca dispatch dinamico por nome
    # calculado. A garantia real e a ausencia de getattr/eval acima.
    assert [n for n in ast.walk(tree35)
            if isinstance(n, getattr(ast, "JoinedStr", ()))] == []


def test_probe_35_identificadores_ascii():
    fonte = io.open(PROBE35_PATH, encoding="utf-8").read()
    arvore = ast.parse(fonte)
    for node in ast.walk(arvore):
        for atributo in ("name", "id", "arg", "attr"):
            valor = getattr(node, atributo, None)
            if isinstance(valor, str):
                assert all(ord(c) < 128 for c in valor), valor


def test_probe_35_from_future_print_function():
    fonte = io.open(PROBE35_PATH, encoding="utf-8").read()
    assert "from __future__ import print_function" in fonte
    assert "yield from" not in fonte
    assert "pathlib" not in fonte
    # sem type hints (anotacao `: Tipo` em assinatura de funcao / variavel)
    arvore = ast.parse(fonte)
    for node in ast.walk(arvore):
        assert not isinstance(node, ast.AnnAssign)
    for node in ast.walk(arvore):
        if isinstance(node, ast.FunctionDef):
            assert node.returns is None
            for arg in node.args.args:
                assert getattr(arg, "annotation", None) is None

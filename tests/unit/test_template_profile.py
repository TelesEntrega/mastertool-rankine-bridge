"""Testes de `mastertool_bridge.templates.profile` — o Template Profile da
fase R0b, e o perfil congelado do `TemplateExemplo v1.project`.

O teste que mais importa aqui não é o do caminho feliz: é o que prova que um
perfil **não consegue se autopromover**. Elegibilidade e maturidade são
derivadas da evidência; declará-las no arquivo tem de reprovar, não valer.
"""

import copy
import io
import json
import os

import pytest

from mastertool_bridge.templates import profile as prof

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PERFIL_TemplateExemplo = os.path.join(
    _REPO_ROOT, "config", "template-profiles",
    "mastertool-x-4.1.0.11-tmf-v1-io.json")

SHA_TemplateExemplo = "596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5"
APPLICATION_GUID = "639b491f-5557-464c-af91-1471bac9f549"


def _perfil_congelado():
    return json.loads(io.open(PERFIL_TemplateExemplo, encoding="utf-8").read())


def _valido(**mudancas):
    """Perfil mínimo válido, montado do zero — independente do congelado, para
    que um teste de regra não quebre quando o perfil real mudar."""
    base = {
        "schema_version": 1,
        "profile_id": "perfil-de-teste-v1",
        "product": "MasterTool X",
        "product_version": "4.1.0.11",
        "project": {
            "file_name": "sintetico.project",
            "sha256": "a" * 64,
            "size_bytes": 1024,
            "classification": "projeto sintético de teste",
        },
        "structure": {
            "root_count": 3,
            "node_count": 42,
            "tree_sha256": "b" * 64,
            "tree_sha256_scope": "árvore inteira, sem distinguir transiente",
        },
        "application_selector": {
            "name": "Application",
            "type_guid": APPLICATION_GUID,
            "expected_cardinality": 1,
        },
        "compiler_version": {
            "status": "measured", "value": "3.5.18.50", "source": "run-012",
        },
        "libraries": {
            "status": "measured", "value": {"count": 17}, "source": "run-016",
        },
        "device_inventory": {
            "status": "unresolved", "value": None, "source": "R0b",
            "reason": "nenhuma run mediu",
        },
        "library_lock": {
            "status": "unresolved", "value": None, "source": "R0b",
            "reason": "bibliotecas placeholder, sem versão resolvida",
        },
        "capability_qualification": {
            "status": "not_measured", "runs": [],
            "reason": "R1 não executada",
        },
        "provenance": [
            {"field": "project.sha256", "run": "run-010", "document": "docs/36"},
            {"field": "structure", "run": "run-011", "document": "docs/36"},
            {"field": "application_selector", "run": "run-011",
             "document": "docs/36"},
            {"field": "compiler_version", "run": "run-012", "document": "docs/18"},
            {"field": "libraries", "run": "run-016", "document": "docs/18"},
        ],
    }
    base.update(copy.deepcopy(mudancas))
    return base


# =============================================================================
# o perfil congelado do TemplateExemplo v1
# =============================================================================

def test_o_perfil_congelado_carrega_sem_problema():
    resultado = prof.validate_template_profile(_perfil_congelado())
    assert resultado.problems == [], resultado.problems
    assert resultado.ok


def test_o_perfil_congelado_descreve_o_arquivo_medido():
    resultado = prof.validate_template_profile(_perfil_congelado())
    perfil = prof.select_profile_for_file(resultado, SHA_TemplateExemplo)
    assert perfil is not None
    assert perfil.project.size_bytes == 503040
    assert perfil.structure.node_count == 42
    assert perfil.structure.unclassified_node_count == 13
    assert perfil.application_selector.name == "Application"
    assert perfil.application_selector.type_guid == APPLICATION_GUID


def test_o_perfil_congelado_e_autoravel_e_nao_qualificado():
    """As duas coisas ao mesmo tempo, que é o estado real.

    Atualizado em 2026-08-02 pela qualificação R1 N=10: a lacuna de
    `capability_qualification` fechou e onze operações estão `repeatable` —
    e o perfil CONTINUA não qualificado, porque `template_qualified` depende
    das duas lacunas que seguem abertas. É a distinção que o refinamento por
    nível existe para preservar."""
    resultado = prof.validate_template_profile(_perfil_congelado())
    perfil = prof.select_profile_for_file(resultado, SHA_TemplateExemplo)
    assert perfil.authoring_eligible is True
    assert perfil.blocking_issues == ()
    assert perfil.qualified is False
    assert set(perfil.qualification_gaps) == {
        prof.GAP_DEVICE_INVENTORY, prof.GAP_LIBRARY_LOCK,
    }
    assert len(perfil.qualified_capabilities) == 14
    assert {c.maturity for c in perfil.qualified_capabilities} == {"repeatable"}
    promovidas = {c.operation for c in perfil.qualified_capabilities}
    # As três de task entraram no segundo lote (docs/51), com spec que CRIA
    # task. O primeiro lote (docs/50) não podia promovê-las, e não promoveu.
    assert {"create_task", "bind_program_to_task", "configure_task"} <= promovidas

    from mastertool_bridge.planner.planner import EXECUTOR_CONTRACT
    assert promovidas == set(EXECUTOR_CONTRACT)


def test_o_perfil_congelado_nao_usa_node_path():
    """Gate da R0b, do lado do dado: a identidade do container é semântica, e
    nenhum caminho de índices sobrou no arquivo."""
    texto = io.open(PERFIL_TemplateExemplo, encoding="utf-8").read()
    assert "node_path" not in texto
    assert "root/1/0/0" not in texto


def test_o_escopo_do_hash_de_arvore_e_declarado():
    """O mesmo nome de campo já designou escopos diferentes nesta base. Sem o
    escopo escrito, um consumidor compararia o hash de árvore inteira com o de
    um nível de filhos e concluiria que a árvore mudou."""
    resultado = prof.validate_template_profile(_perfil_congelado())
    perfil = prof.select_profile_for_file(resultado, SHA_TemplateExemplo)
    assert "transiente" in perfil.structure.tree_sha256_scope
    assert "template_registry" in perfil.structure.tree_sha256_scope


def test_a_proveniencia_do_congelado_cobre_o_que_foi_medido():
    resultado = prof.validate_template_profile(_perfil_congelado())
    perfil = prof.select_profile_for_file(resultado, SHA_TemplateExemplo)
    campos = {p.field_path for p in perfil.provenance}
    assert {"project.sha256", "structure", "application_selector",
            "compiler_version", "libraries"} <= campos
    # A resolução que nenhum documento numerado registrava tem entrada própria.
    por_run = {p.run for p in perfil.provenance}
    assert {"run-012", "run-016", "run-018"} <= por_run


# =============================================================================
# um perfil não promove a si mesmo
# =============================================================================

def test_capacidade_declarada_com_qualificacao_nao_medida_reprova():
    """A regra central do módulo."""
    resultado = prof.validate_template_profile(_valido(
        capability_qualification={
            "status": "not_measured", "runs": [], "reason": "R1 não executada",
            "capabilities": [{"operation": "create_gvl",
                              "maturity": "template_qualified",
                              "runs": ["run-999"], "document": "docs/inventado"}],
        }))
    assert not resultado.ok
    assert any("não promove maturidade" in p for p in resultado.problems)


def test_runs_declaradas_com_status_nao_medido_reprovam():
    resultado = prof.validate_template_profile(_valido(
        capability_qualification={
            "status": "not_measured", "runs": ["run-001"],
            "reason": "R1 não executada"}))
    assert not resultado.ok
    assert any("contradição" in p for p in resultado.problems)


def test_repeatable_NAO_e_bloqueado_por_lacuna_de_template():
    """A refinação forçada pela qualificação N=10 de 2026-08-02.

    Dez execuções independentes, equivalentes e com build verde respondem
    "isto se repete?". O inventário de dispositivos do template responde
    "isto vale neste template?" — outra pergunta. A regra grossa fazia a
    régua de uma cobrar a evidência da outra.
    """
    runs = ["run-%03d" % (100 + i) for i in range(10)]
    resultado = prof.validate_template_profile(_valido(
        capability_qualification={
            "status": "measured", "runs": runs, "reason": None,
            "capabilities": [{"operation": "create_gvl",
                              "maturity": "repeatable",
                              "runs": runs, "document": "docs/50"}]}))
    assert resultado.ok, resultado.problems
    perfil = prof.select_profile_for_file(resultado, "a" * 64)
    assert perfil.qualified_capabilities[0].maturity == "repeatable"
    # E o perfil CONTINUA não qualificado: as lacunas seguem abertas.
    assert perfil.qualified is False
    assert prof.GAP_DEVICE_INVENTORY in perfil.qualification_gaps


def test_template_qualified_CONTINUA_bloqueado_pelas_mesmas_lacunas():
    """A contraprova: a refinação não afrouxou o nível que de fato depende do
    template estar caracterizado."""
    runs = ["run-%03d" % (100 + i) for i in range(10)]
    resultado = prof.validate_template_profile(_valido(
        capability_qualification={
            "status": "measured", "runs": runs, "reason": None,
            "capabilities": [{"operation": "create_gvl",
                              "maturity": "template_qualified",
                              "runs": runs, "document": "docs/50"}]}))
    assert not resultado.ok
    assert any("device_inventory_unresolved" in p for p in resultado.problems)


def test_o_mapa_de_bloqueio_cobre_todo_nivel_acima_do_teto():
    """Nível novo acima do teto sem entrada no mapa passaria sem bloqueio
    nenhum — silêncio virando permissão."""
    teto = prof.MATURITY_SCALE.index(prof.MATURITY_CEILING_WITH_GAPS)
    acima = prof.MATURITY_SCALE[teto + 1:]
    assert set(acima) == set(prof.GAPS_BLOCKING_BY_MATURITY)


def test_maturidade_acima_do_teto_com_lacuna_aberta_reprova():
    """`template_qualified` exige que o próprio perfil esteja sem lacuna. Com
    library lock e inventário de dispositivos por medir, o teto é
    `field_proven`."""
    resultado = prof.validate_template_profile(_valido(
        capability_qualification={
            "status": "measured", "runs": ["run-100"], "reason": None,
            "capabilities": [{"operation": "create_gvl",
                              "maturity": "template_qualified",
                              "runs": ["run-100", "run-101"],
                              "document": "docs/50"}]}))
    assert not resultado.ok
    assert any("lacunas do perfil" in p for p in resultado.problems)


def _com_qualificacao_medida(maturidade, runs):
    """Perfil sem lacuna de dispositivo/trava, para que o teto de maturidade
    não seja o que reprova — assim o teste isola a regra de contagem de runs."""
    return _valido(
        device_inventory={"status": "measured", "value": {"cards": 2},
                          "source": "run-100"},
        library_lock={"status": "measured", "value": {"hash": "c" * 64},
                      "source": "run-100"},
        provenance=[
            {"field": "project.sha256", "run": "run-010", "document": "docs/36"},
            {"field": "structure", "run": "run-011", "document": "docs/36"},
            {"field": "application_selector", "run": "run-011", "document": "docs/36"},
            {"field": "compiler_version", "run": "run-012", "document": "docs/18"},
            {"field": "libraries", "run": "run-016", "document": "docs/18"},
            {"field": "device_inventory", "run": "run-100", "document": "docs/50"},
            {"field": "library_lock", "run": "run-100", "document": "docs/50"},
        ],
        capability_qualification={
            "status": "measured", "runs": list(runs), "reason": None,
            "capabilities": [{"operation": "create_gvl", "maturity": maturidade,
                              "runs": list(runs), "document": "docs/50"}]})


@pytest.mark.parametrize("quantidade", [1, 2, 9])
def test_repeatable_abaixo_do_piso_normativo_reprova(quantidade):
    """O piso é o da norma, não o do bom senso.

    A primeira versão desta guarda exigia 2 — reprovava a run única e aprovava
    duas, quando `docs/ROADMAP.md` §R1 manda dez. Nove reprova junto com uma:
    o que decide é o número da fase, e ele está em MIN_INDEPENDENT_RUNS."""
    runs = ["run-%03d" % (100 + i) for i in range(quantidade)]
    resultado = prof.validate_template_profile(
        _com_qualificacao_medida("repeatable", runs))
    assert not resultado.ok
    assert any("execuções independentes" in p for p in resultado.problems)


def test_repeatable_com_dez_runs_distintas_passa():
    runs = ["run-%03d" % (100 + i) for i in range(10)]
    resultado = prof.validate_template_profile(
        _com_qualificacao_medida("repeatable", runs))
    assert resultado.ok, resultado.problems
    perfil = prof.select_profile_for_file(resultado, "a" * 64)
    assert perfil.qualified_capabilities[0].maturity == "repeatable"
    assert perfil.qualified is True


def test_dez_runs_repetidas_nao_sao_dez_execucoes():
    """Contagem é por run DISTINTA: repetir o mesmo identificador dez vezes
    mede uma execução, não dez."""
    resultado = prof.validate_template_profile(
        _com_qualificacao_medida("repeatable", ["run-100"] * 10))
    assert not resultado.ok


def test_o_piso_nunca_diminui_ao_subir_de_nivel():
    """Monotonicidade: um nível superior não pode exigir menos evidência que o
    nível abaixo. Sem isto, `production_qualified` poderia ser mais barato que
    `repeatable`."""
    escala = [m for m in prof.MATURITY_SCALE if m in prof.MIN_INDEPENDENT_RUNS]
    pisos = [prof.MIN_INDEPENDENT_RUNS[m] for m in escala]
    assert pisos == sorted(pisos)
    assert min(pisos) >= 10


def test_capacidade_field_proven_com_lacuna_e_aceita():
    """O teto não proíbe declarar — proíbe declarar ACIMA dele."""
    resultado = prof.validate_template_profile(_valido(
        capability_qualification={
            "status": "measured", "runs": ["run-100"], "reason": None,
            "capabilities": [{"operation": "create_gvl",
                              "maturity": "field_proven",
                              "runs": ["run-100"], "document": "docs/33"}]}))
    assert resultado.ok, resultado.problems
    perfil = prof.select_profile_for_file(resultado, "a" * 64)
    assert perfil.qualified_capabilities[0].operation == "create_gvl"
    # Continua não qualificado: sobraram as lacunas de dispositivo e trava.
    assert perfil.qualified is False


def test_maturidade_fora_da_escala_reprova():
    resultado = prof.validate_template_profile(_valido(
        capability_qualification={
            "status": "measured", "runs": ["run-100"], "reason": None,
            "capabilities": [{"operation": "create_gvl", "maturity": "otima",
                              "runs": ["run-100"], "document": "docs/33"}]}))
    assert not resultado.ok
    assert any("fora da escala" in p for p in resultado.problems)


# =============================================================================
# evidência: as duas formas, e nenhuma terceira
# =============================================================================

def test_compilador_nao_resolvido_bloqueia_autoria():
    resultado = prof.validate_template_profile(_valido(
        compiler_version={"status": "unresolved", "value": None,
                          "source": "probes/35",
                          "reason": "acessor não catalogado"}))
    assert resultado.ok, resultado.problems
    perfil = prof.select_profile_for_file(resultado, "a" * 64)
    assert perfil.authoring_eligible is False
    assert prof.BLOCK_COMPILER_VERSION in perfil.blocking_issues


def test_bibliotecas_nao_resolvidas_bloqueiam_autoria():
    resultado = prof.validate_template_profile(_valido(
        libraries={"status": "unresolved", "value": None, "source": "probes/41",
                   "reason": "Library Manager inalcançável"}))
    perfil = prof.select_profile_for_file(resultado, "a" * 64)
    assert prof.BLOCK_LIBRARIES in perfil.blocking_issues


def test_medido_com_valor_nulo_reprova():
    resultado = prof.validate_template_profile(_valido(
        compiler_version={"status": "measured", "value": None,
                          "source": "run-012"}))
    assert not resultado.ok
    assert any("medir produz valor" in p for p in resultado.problems)


def test_medido_com_string_vazia_reprova():
    resultado = prof.validate_template_profile(_valido(
        compiler_version={"status": "measured", "value": "  ",
                          "source": "run-012"}))
    assert not resultado.ok


def test_nao_resolvido_com_valor_reprova():
    """"Valor de consolação" é o modo de falha: um número plausível preenchido
    para o campo não ficar vazio."""
    resultado = prof.validate_template_profile(_valido(
        library_lock={"status": "unresolved", "value": "d" * 64,
                      "source": "R0b", "reason": "sem versão"}))
    assert not resultado.ok
    assert any("consolação" in p for p in resultado.problems)


def test_nao_resolvido_sem_motivo_reprova():
    resultado = prof.validate_template_profile(_valido(
        library_lock={"status": "unresolved", "value": None, "source": "R0b"}))
    assert not resultado.ok
    assert any("lacuna escondida" in p for p in resultado.problems)


def test_medido_com_motivo_reprova():
    resultado = prof.validate_template_profile(_valido(
        compiler_version={"status": "measured", "value": "3.5.18.50",
                          "source": "run-012", "reason": "por via das dúvidas"}))
    assert not resultado.ok


def test_evidencia_sem_source_reprova_nos_dois_status():
    for evidencia in ({"status": "measured", "value": "x", "source": ""},
                      {"status": "unresolved", "value": None, "source": "",
                       "reason": "sem acesso"}):
        resultado = prof.validate_template_profile(
            _valido(compiler_version=evidencia))
        assert not resultado.ok


def test_status_de_evidencia_fora_do_vocabulario_reprova():
    resultado = prof.validate_template_profile(_valido(
        compiler_version={"status": "provavel", "value": "3.5",
                          "source": "achismo"}))
    assert not resultado.ok


# =============================================================================
# proveniência
# =============================================================================

def test_proveniencia_vazia_reprova():
    resultado = prof.validate_template_profile(_valido(provenance=[]))
    assert not resultado.ok
    assert any("sem origem" in p for p in resultado.problems)


def test_campo_medido_sem_proveniencia_reprova():
    resultado = prof.validate_template_profile(_valido(provenance=[
        {"field": "project.sha256", "run": "run-010", "document": "docs/36"}]))
    assert not resultado.ok
    assert any("structure" in p for p in resultado.problems)


def test_evidencia_medida_sem_proveniencia_reprova():
    """A exigência é DINÂMICA: o campo entra na lista por estar medido, não
    por estar numa lista fixa. Medir sem dizer quem mediu é o formato exato da
    lacuna que `docs/36` deixou aberta."""
    resultado = prof.validate_template_profile(_valido(
        device_inventory={"status": "measured", "value": {"cards": 2},
                          "source": "run-100"}))
    assert not resultado.ok
    assert any("device_inventory" in p for p in resultado.problems)


def test_evidencia_nao_resolvida_dispensa_proveniencia():
    """`reason` é a própria origem de uma lacuna — exigir run para o que não
    foi medido seria pedir a origem de uma medição que não houve."""
    resultado = prof.validate_template_profile(_valido())
    assert resultado.ok, resultado.problems
    perfil = prof.select_profile_for_file(resultado, "a" * 64)
    assert perfil.device_inventory.is_measured is False
    assert perfil.device_inventory.reason


def test_proveniencia_cobre_por_prefixo():
    """Uma entrada para `structure` cobre `structure.node_count`. Exigir
    entrada por folha transformaria proveniência em burocracia."""
    resultado = prof.validate_template_profile(_valido())
    assert resultado.ok, resultado.problems


def test_entrada_de_proveniencia_sem_run_reprova():
    resultado = prof.validate_template_profile(_valido(provenance=[
        {"field": "project.sha256", "run": "  ", "document": "docs/36"},
        {"field": "structure", "run": "run-011", "document": "docs/36"},
        {"field": "application_selector", "run": "run-011", "document": "docs/36"}]))
    assert not resultado.ok


# =============================================================================
# identidade do arquivo — sem atalho por nome
# =============================================================================

def test_perfil_so_sai_pelo_sha256_do_arquivo():
    resultado = prof.validate_template_profile(_perfil_congelado())
    assert prof.select_profile_for_file(resultado, "f" * 64) is None
    assert prof.select_profile_for_file(resultado, "nao-e-sha") is None
    assert prof.select_profile_for_file(resultado, None) is None
    assert prof.select_profile_for_file(resultado, SHA_TemplateExemplo) is not None


def test_perfil_invalido_nao_devolve_nada():
    resultado = prof.validate_template_profile({"schema_version": 1})
    assert not resultado.ok
    assert prof.select_profile_for_file(resultado, SHA_TemplateExemplo) is None


def test_motivo_da_recusa_distingue_ausente_de_inelegivel():
    """Recusa silenciosa é indistinguível de perfil ausente, e as duas pedem
    ações opostas: uma manda medir, a outra manda registrar."""
    congelado = prof.validate_template_profile(_perfil_congelado())
    assert prof.authoring_refusal_reason(congelado, SHA_TemplateExemplo) is None
    ausente = prof.authoring_refusal_reason(congelado, "f" * 64)
    assert "nenhum perfil descreve" in ausente

    bloqueado = prof.validate_template_profile(_valido(
        compiler_version={"status": "unresolved", "value": None,
                          "source": "probes/35", "reason": "sem acessor"}))
    motivo = prof.authoring_refusal_reason(bloqueado, "a" * 64)
    assert prof.BLOCK_COMPILER_VERSION in motivo


# =============================================================================
# forma: campo desconhecido, aritmética impossível, entrada degenerada
# =============================================================================

def test_campo_desconhecido_no_topo_reprova():
    resultado = prof.validate_template_profile(_valido(qualified=True))
    assert not resultado.ok
    assert any("desconhecido" in p for p in resultado.problems)


def test_campo_desconhecido_em_project_reprova():
    perfil = _valido()
    perfil["project"]["node_path"] = "root/1/0/0"
    resultado = prof.validate_template_profile(perfil)
    assert not resultado.ok


def test_escopo_do_hash_de_arvore_e_obrigatorio():
    perfil = _valido()
    del perfil["structure"]["tree_sha256_scope"]
    resultado = prof.validate_template_profile(perfil)
    assert not resultado.ok
    assert any("escopo" in p or "tree_sha256_scope" in p
               for p in resultado.problems)


def test_mais_nao_classificados_que_nos_reprova():
    perfil = _valido()
    perfil["structure"]["unclassified_node_count"] = 43
    resultado = prof.validate_template_profile(perfil)
    assert not resultado.ok
    assert any("impossível" in p for p in resultado.problems)


def test_seletor_invalido_bloqueia_autoria_e_reprova_o_perfil():
    perfil = _valido()
    perfil["application_selector"] = {"name": "Application", "typeguid": "x"}
    resultado = prof.validate_template_profile(perfil)
    assert not resultado.ok
    assert any("application_selector" in p for p in resultado.problems)


@pytest.mark.parametrize("entrada", [None, [], "perfil", 7, True, 3.5])
def test_entrada_degenerada_nao_levanta(entrada):
    resultado = prof.validate_template_profile(entrada)
    assert not resultado.ok


def test_json_malformado_vira_problema_e_nao_excecao():
    resultado = prof.load_template_profile("{ isto não é json")
    assert not resultado.ok
    assert any("JSON inválido" in p for p in resultado.problems)


def test_load_template_profile_le_o_congelado():
    resultado = prof.load_template_profile(
        io.open(PERFIL_TemplateExemplo, encoding="utf-8").read())
    assert resultado.ok, resultado.problems


def test_schema_version_diferente_reprova():
    resultado = prof.validate_template_profile(_valido(schema_version=2))
    assert not resultado.ok


def test_escala_de_maturidade_e_ordenada_e_sem_repeticao():
    assert len(set(prof.MATURITY_SCALE)) == len(prof.MATURITY_SCALE)
    assert prof.MATURITY_SCALE[0] == "discovered"
    assert prof.MATURITY_SCALE[-1] == "production_qualified"
    assert prof.MATURITY_CEILING_WITH_GAPS in prof.MATURITY_SCALE

"""Testes do preflight do lote (fase R1).

Cada condição de recusa do contrato do piloto tem teste próprio, e cada uma
tem também a sua contraprova — um preflight que só sabe liberar não protege
sessão nenhuma.
"""

import pytest

from mastertool_bridge.automation import batch_preflight as bp

SPEC_SHA = "2e382c763ce4796a99f44cdf58ae5f18003c8a4f44d3fdc174e1f37a08db1481"
TEMPLATE_SHA = "596625796e4efd54d3cc2d6286e858b683f0f58de66ab9a36eed532dd1d815f5"
SPEC = r"C:\mastertool-x-r1\specs\w7-factory-full-v1.json"
TEMPLATE = r"C:\mastertool-x-w2\template\TemplateExemplo_v1.project"
EXE = "C:\\" + "Program Files" + "\\Altus\\MT9000 4.1.0\\MT9000\\Common\\MT9000.exe"
LOTE = r"C:\mastertool-x-r1\lote-piloto"


class _Instalacao:
    def __init__(self, exe_path, version):
        self.exe_path = exe_path
        self.version = version


class _Deteccao:
    def __init__(self, candidatos, instalacao):
        self.candidates = candidatos
        self.install = instalacao


def _pedido(**kwargs):
    base = dict(
        spec_path=SPEC, expected_spec_sha256=SPEC_SHA,
        template_path=TEMPLATE, expected_template_sha256=TEMPLATE_SHA,
        template_profile_id="mastertool-x-4.1.0.11-tmf-v1-io-v1",
        output_root=LOTE, requested_runs=3, requested_stage=bp.STAGE_PLAN,
        mastertool_wrapper_path=EXE,
        expected_mastertool_version="4.1.0.11",
        timestamp="2026-08-02T09:00")
    base.update(kwargs)
    return bp.PreflightRequest(**base)


def _ambiente(*, limpa=True, head="abc1234", hashes=None, gate=None,
              deteccao="ok", saida_existe=False, runs=(), planos_ok=True):
    hashes = hashes if hashes is not None else {SPEC: SPEC_SHA,
                                                TEMPLATE: TEMPLATE_SHA}
    if deteccao == "ok":
        deteccao = _Deteccao([EXE], _Instalacao(EXE, "4.1.0.11"))
    return bp.PreflightEnvironment(
        git_head=lambda: head,
        git_tree_clean=lambda: limpa,
        sha256_of=lambda p: hashes.get(p),
        path_exists=lambda p: saida_existe,
        list_run_dirs=lambda p: list(runs),
        plan_output_exists=lambda p: planos_ok,
        read_controlled_write_phase=lambda: gate,
        detect_mastertool=lambda: deteccao)


# =============================================================================
# o caminho liberado
# =============================================================================

def test_preflight_limpo_libera_a_sessao():
    resultado = bp.run_preflight(_pedido(), _ambiente())
    assert resultado.cleared is True, resultado.details
    assert resultado.refusals == []
    assert bp.refusal_report(resultado) == ""


def test_o_registro_tem_todos_os_campos_do_contrato():
    registro = bp.run_preflight(_pedido(), _ambiente()).record
    for campo in ("preflight_schema_version", "head", "git_tree_clean",
                  "spec_path", "spec_sha256", "expected_spec_sha256",
                  "template_path", "template_sha256", "template_profile_id",
                  "mastertool_detected_count", "mastertool_detected_path",
                  "mastertool_wrapper_path", "mastertool_paths_match",
                  "mastertool_version", "controlled_write_phase",
                  "output_root", "output_root_exists", "prior_batch_reused",
                  "requested_runs", "requested_stage", "timestamp"):
        assert campo in registro, campo
    assert registro["preflight_schema_version"] == 1


def test_o_registro_declara_o_que_e_so_host_side():
    """Afirmar "inspecionei o template" tendo comparado um JSON descreveria
    mal o que foi feito."""
    registro = bp.run_preflight(_pedido(), _ambiente()).record
    assert any("sha256" in item for item in registro["host_side_only"])
    assert any("árvore" in item
               for item in registro["reevaluated_in_mastertool"])
    assert any("bibliotecas" in item
               for item in registro["reevaluated_in_mastertool"])


# =============================================================================
# as onze recusas do contrato
# =============================================================================

def test_arvore_suja_recusa():
    resultado = bp.run_preflight(_pedido(), _ambiente(limpa=False))
    assert bp.REFUSAL_DIRTY_TREE in resultado.refusals
    assert resultado.cleared is False


def test_gate_aberto_antes_da_sessao_recusa():
    """Encontrar o gate aberto significa fase não encerrada da vez anterior."""
    resultado = bp.run_preflight(_pedido(),
                                 _ambiente(gate="W7_FACTORY_FULL"))
    assert bp.REFUSAL_GATE_OPEN in resultado.refusals
    assert any("não encerrada" in d for d in resultado.details)


def test_spec_com_sha_diferente_recusa():
    resultado = bp.run_preflight(
        _pedido(), _ambiente(hashes={SPEC: "f" * 64, TEMPLATE: TEMPLATE_SHA}))
    assert bp.REFUSAL_SPEC_MISMATCH in resultado.refusals
    assert any("equivalência semântica não basta" in d
               for d in resultado.details)


def test_spec_ausente_recusa():
    resultado = bp.run_preflight(_pedido(),
                                 _ambiente(hashes={TEMPLATE: TEMPLATE_SHA}))
    assert bp.REFUSAL_SPEC_MISMATCH in resultado.refusals


def test_template_com_sha_diferente_recusa():
    """O hash do arquivo é a identidade primária da entrada — nenhuma
    propriedade do perfil o substitui."""
    resultado = bp.run_preflight(
        _pedido(), _ambiente(hashes={SPEC: SPEC_SHA, TEMPLATE: "e" * 64}))
    assert bp.REFUSAL_TEMPLATE_MISMATCH in resultado.refusals
    assert any("identidade primária" in d for d in resultado.details)


def test_nenhuma_instalacao_recusa():
    resultado = bp.run_preflight(_pedido(),
                                 _ambiente(deteccao=_Deteccao([], None)))
    assert bp.REFUSAL_MASTERTOOL_NOT_FOUND in resultado.refusals


def test_duas_instalacoes_recusam():
    outra = EXE.replace("4.1.0", "4.2.0")
    resultado = bp.run_preflight(
        _pedido(),
        _ambiente(deteccao=_Deteccao([EXE, outra], _Instalacao(EXE, "4.1.0.11"))))
    assert bp.REFUSAL_MASTERTOOL_AMBIGUOUS in resultado.refusals


def test_instalacao_detectada_diferente_da_do_wrapper_recusa():
    """O lote mediria um produto e o wrapper abriria outro."""
    outra = EXE.replace("4.1.0", "4.3.0")
    resultado = bp.run_preflight(
        _pedido(),
        _ambiente(deteccao=_Deteccao([outra], _Instalacao(outra, "4.1.0.11"))))
    assert bp.REFUSAL_MASTERTOOL_PATH_DIVERGENT in resultado.refusals
    assert any("wrapper abriria outro" in d for d in resultado.details)


def test_caminho_compara_sem_tropecar_em_caixa_e_barra():
    variante = EXE.replace("\\", "/").upper()
    resultado = bp.run_preflight(
        _pedido(mastertool_wrapper_path=variante), _ambiente())
    assert bp.REFUSAL_MASTERTOOL_PATH_DIVERGENT not in resultado.refusals


def test_versao_diferente_da_qualificada_recusa():
    resultado = bp.run_preflight(
        _pedido(),
        _ambiente(deteccao=_Deteccao([EXE], _Instalacao(EXE, "4.2.0.0"))))
    assert bp.REFUSAL_MASTERTOOL_VERSION in resultado.refusals


def test_versao_ilegivel_recusa():
    """Versão não medida não é a versão certa por omissão."""
    resultado = bp.run_preflight(
        _pedido(), _ambiente(deteccao=_Deteccao([EXE], _Instalacao(EXE, None))))
    assert bp.REFUSAL_MASTERTOOL_VERSION in resultado.refusals


def test_output_root_existente_recusa_no_estagio_plan():
    resultado = bp.run_preflight(_pedido(), _ambiente(saida_existe=True))
    assert bp.REFUSAL_OUTPUT_EXISTS in resultado.refusals


def test_lote_anterior_reaproveitado_recusa():
    resultado = bp.run_preflight(
        _pedido(), _ambiente(saida_existe=True, runs=["run-001", "run-002"]))
    assert bp.REFUSAL_PRIOR_BATCH_REUSED in resultado.refusals
    assert any("N-1 leituras" in d for d in resultado.details)


def test_estagio_build_sem_saida_do_plan_recusa():
    resultado = bp.run_preflight(
        _pedido(requested_stage=bp.STAGE_BUILD),
        _ambiente(saida_existe=True, runs=["run-001"], planos_ok=False))
    assert bp.REFUSAL_PLAN_OUTPUTS_MISSING in resultado.refusals
    assert any("run-003" in d for d in resultado.details)


def test_estagio_build_com_as_saidas_do_plan_libera():
    """A contraprova: no estágio build, saída existente é precondição, não
    violação — exigir ausência ali seria a regra do estágio errado."""
    resultado = bp.run_preflight(
        _pedido(requested_stage=bp.STAGE_BUILD),
        _ambiente(saida_existe=True, runs=["run-001", "run-002", "run-003"],
                  planos_ok=True))
    assert resultado.cleared is True, resultado.details


# =============================================================================
# forma do pedido
# =============================================================================

@pytest.mark.parametrize("mudanca", [
    {"requested_runs": 1},
    {"requested_runs": 0},
    {"requested_runs": True},
    {"requested_stage": "verify"},
    {"expected_spec_sha256": "curto"},
    {"expected_template_sha256": ""},
    {"spec_path": "   "},
    {"timestamp": ""},
])
def test_pedido_malformado_recusa_sem_abrir_nada(mudanca):
    resultado = bp.run_preflight(_pedido(**mudanca), _ambiente())
    assert bp.REFUSAL_INVALID_REQUEST in resultado.refusals
    assert resultado.cleared is False


@pytest.mark.parametrize("entrada", [None, {}, "preflight", 7])
def test_entrada_degenerada_nao_levanta(entrada):
    resultado = bp.run_preflight(entrada, _ambiente())
    assert resultado.cleared is False
    assert bp.REFUSAL_INVALID_REQUEST in resultado.refusals


def test_ambiente_padrao_e_fail_closed():
    """Sem ambiente injetado, tudo é desconhecido — e desconhecido recusa."""
    resultado = bp.run_preflight(_pedido())
    assert resultado.cleared is False
    assert bp.REFUSAL_DIRTY_TREE in resultado.refusals
    assert bp.REFUSAL_SPEC_MISMATCH in resultado.refusals


def test_varias_recusas_aparecem_juntas():
    """O operador vê tudo de uma vez, e não uma por rodada."""
    resultado = bp.run_preflight(
        _pedido(), _ambiente(limpa=False, gate="W7_FACTORY_FULL",
                             hashes={}, saida_existe=True))
    assert len(resultado.refusals) >= 4
    relatorio = bp.refusal_report(resultado)
    assert bp.REFUSAL_DIRTY_TREE in relatorio
    assert bp.REFUSAL_GATE_OPEN in relatorio


def test_o_vocabulario_de_recusa_e_fechado():
    assert len(set(bp.REFUSALS)) == len(bp.REFUSALS)
    resultado = bp.run_preflight(_pedido(), _ambiente(limpa=False))
    for recusa in resultado.refusals:
        assert recusa in bp.REFUSALS


def test_serializacao_carrega_veredito_e_motivos():
    d = bp.run_preflight(_pedido(), _ambiente(limpa=False)).to_dict()
    assert d["cleared"] is False
    assert d["refusals"]
    assert d["details"]
    assert d["timestamp"] == "2026-08-02T09:00"

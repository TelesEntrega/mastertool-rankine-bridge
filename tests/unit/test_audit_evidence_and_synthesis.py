"""Testes das duas guardas de auditoria da fase P0.

`evidence_status` impede que ausência de evidência vire negação.
`synthesis_integrity` impede que uma síntese incompleta seja publicada como
completa — a regressão do corte de 120.000 caracteres, congelada.
"""

import pytest

from mastertool_bridge.audit import evidence_status as ev
from mastertool_bridge.audit import synthesis_integrity as si


# =============================================================================
# vocabulário de evidência
# =============================================================================

def test_o_vocabulario_e_fechado_e_sem_sinonimo_ambiguo():
    assert len(set(ev.EVIDENCE_STATUSES)) == 6
    assert set(ev.STATUS_MEANING) == set(ev.EVIDENCE_STATUSES)
    for proibido in ("false", "unsupported", "rejected", "missing", "unknown"):
        assert proibido not in ev.EVIDENCE_STATUSES


@pytest.mark.parametrize("frase", [
    "sem evidência localizada",
    "sem evidencia localizada",
    "Busca não retornou nada em src/",
    "não encontrado no repositório",
])
def test_frase_de_ausencia_vira_no_evidence_located_e_nunca_contradicted(frase):
    """A regra fundamental do módulo, como teste."""
    status, problemas = ev.normalize_status(frase)
    assert problemas == []
    assert status == ev.NO_EVIDENCE_LOCATED
    assert status != ev.CONTRADICTED


@pytest.mark.parametrize("palavra", ["false", "unsupported", "rejected",
                                     "missing", "unknown", "n/a"])
def test_termo_ambiguo_e_recusado_em_vez_de_adivinhado(palavra):
    """Mapear `unsupported` para o palpite mais próximo reintroduziria a
    confusão pela porta dos fundos."""
    status, problemas = ev.normalize_status(palavra)
    assert status is None
    assert any("proibido" in p for p in problemas)


def test_status_do_vocabulario_passa_direto():
    for status in ev.EVIDENCE_STATUSES:
        assert ev.normalize_status(status) == (status, [])


@pytest.mark.parametrize("entrada", [None, "", "   ", 7, [], {}])
def test_status_degenerado_nao_levanta(entrada):
    status, problemas = ev.normalize_status(entrada)
    assert status is None and problemas


def test_require_status_levanta_para_quem_prefere_falhar_alto():
    assert ev.require_status("proven") == ev.PROVEN
    with pytest.raises(ev.EvidenceStatusError):
        ev.require_status("unsupported")


def _ausencia(**kwargs):
    base = dict(
        item_id="r11-atualizacao-controlada",
        status=ev.NO_EVIDENCE_LOCATED,
        summary="não há mecanismo de atualização controlada",
        queries_run=("grep -r 'update' src/ tools/ scripts/",),
        sources_examined=("src/", "tools/", "scripts/", "docs/"),
        reason="nenhum componente de atualização foi encontrado nas três "
               "árvores varridas",
        next_verification_method="perguntar ao operador se a atualização é "
                                 "feita fora do repositório",
    )
    base.update(kwargs)
    return ev.EvidenceClaim(**base)


def test_ausencia_bem_formada_e_registravel():
    assert ev.validate_claim(_ausencia()) == []


@pytest.mark.parametrize("campo", ["queries_run", "sources_examined"])
def test_ausencia_sem_busca_declarada_reprova(campo):
    """"Não achei" sem dizer o que se procurou não é refazível — e o próximo a
    olhar repetiria a mesma busca sem saber."""
    problemas = ev.validate_claim(_ausencia(**{campo: ()}))
    assert any(campo in p for p in problemas)


@pytest.mark.parametrize("campo", ["reason", "next_verification_method"])
def test_ausencia_sem_motivo_ou_proximo_passo_reprova(campo):
    problemas = ev.validate_claim(_ausencia(**{campo: None}))
    assert any(campo in p for p in problemas)


@pytest.mark.parametrize("status", [ev.PROVEN, ev.CONTRADICTED])
def test_afirmacao_sobre_o_mundo_exige_evidencia(status):
    problemas = ev.validate_claim(ev.EvidenceClaim(
        item_id="x", status=status, summary="afirmação sem lastro"))
    assert any("evidência citável" in p for p in problemas)
    assert any(ev.NO_EVIDENCE_LOCATED in p for p in problemas)


def test_afirmacao_com_evidencia_passa():
    assert ev.validate_claim(ev.EvidenceClaim(
        item_id="x", status=ev.PROVEN, summary="existe",
        evidence=("src/mastertool_bridge/templates/selector.py:1",))) == []


def test_requires_field_incoerente_com_a_flag_reprova():
    """A contradição esconderia o item da fila de campo."""
    problemas = ev.validate_claim(ev.EvidenceClaim(
        item_id="x", status=ev.REQUIRES_FIELD, summary="precisa do produto",
        requires_field=False))
    assert any("requires_field" in p for p in problemas)


def test_blocked_sem_motivo_reprova():
    problemas = ev.validate_claim(ev.EvidenceClaim(
        item_id="x", status=ev.BLOCKED, summary="travado"))
    assert any("pré-condição" in p for p in problemas)


def test_reclassificar_ausencia_como_refutacao_sem_medir_e_recusado():
    """A transição vigiada. Sem evidência nova, `no_evidence_located` não vira
    `contradicted` por decreto."""
    problemas = ev.validate_transition(ev.NO_EVIDENCE_LOCATED, ev.CONTRADICTED)
    assert any("sem evidência nova" in p for p in problemas)


def test_reclassificar_com_evidencia_nova_e_permitido():
    assert ev.validate_transition(
        ev.NO_EVIDENCE_LOCATED, ev.CONTRADICTED,
        new_evidence=("run-050: o produto recusou a operação",)) == []


def test_refutacao_nao_vira_prova_sem_evidencia():
    problemas = ev.validate_transition(ev.CONTRADICTED, ev.PROVEN)
    assert any("continua valendo" in p for p in problemas)


def test_transicao_para_estado_nao_assertivo_nao_exige_evidencia():
    """Reconhecer que algo depende de campo não é afirmar sobre o mundo."""
    assert ev.validate_transition(ev.NO_EVIDENCE_LOCATED, ev.REQUIRES_FIELD) == []
    assert ev.validate_transition(ev.BLOCKED, ev.NO_EVIDENCE_LOCATED) == []


def test_transicao_fora_do_vocabulario_reprova():
    assert ev.validate_transition("achismo", ev.PROVEN)


def test_registro_conta_por_status_e_separa_a_fila_de_campo():
    registro = ev.ClaimRegister()
    assert registro.add(_ausencia()) == []
    assert registro.add(ev.EvidenceClaim(
        item_id="r3-alias", status=ev.REQUIRES_FIELD,
        summary="Alias nunca foi exercido contra o produto",
        requires_field=True)) == []
    contagem = registro.count_by_status()
    assert contagem[ev.NO_EVIDENCE_LOCATED] == 1
    assert contagem[ev.REQUIRES_FIELD] == 1
    assert contagem[ev.CONTRADICTED] == 0
    assert len(registro.requiring_field()) == 1


def test_afirmacao_invalida_nao_entra_no_registro():
    registro = ev.ClaimRegister()
    problemas = registro.add(_ausencia(queries_run=()))
    assert problemas
    assert registro.claims == []


# =============================================================================
# integridade de síntese — a regressão do corte de 120k
# =============================================================================

FASES = ("R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10",
         "R11", "R12")


def _manifesto(**kwargs):
    base = dict(
        expected_agent_results=13,
        loaded_agent_results=13,
        expected_phase_ids=FASES,
        observed_phase_ids=FASES,
        input_character_count=90_000,
        input_truncated=False,
        truncation_limit=120_000,
        journal_result_ids=tuple("a%d" % i for i in range(13)),
        cache_result_ids=tuple("a%d" % i for i in range(13)),
    )
    base.update(kwargs)
    return si.SynthesisManifest(**base)


def test_1_entrada_abaixo_do_limite_e_publicavel():
    resultado = si.validate_synthesis(_manifesto())
    assert resultado.publishable is True
    assert resultado.problems == []


def test_2_entrada_acima_de_120k_sem_declarar_truncamento_reprova():
    resultado = si.validate_synthesis(_manifesto(input_character_count=184_321))
    assert resultado.publishable is False
    assert any("NÃO declarado" in p for p in resultado.problems)


def test_3_ultimas_tres_fases_ausentes_reprovam():
    """O defeito original, exatamente: R9, R10 e R12 ficaram depois do corte e
    o documento se apresentou como cobrindo o roadmap inteiro."""
    resultado = si.validate_synthesis(_manifesto(
        observed_phase_ids=tuple(f for f in FASES if f not in ("R9", "R10", "R12")),
        input_character_count=184_321, input_truncated=True))
    assert resultado.publishable is False
    assert any("R9" in p and "R10" in p and "R12" in p
               for p in resultado.problems)
    assert any("truncada" in p for p in resultado.problems)


def test_4_resultado_de_agente_ausente_reprova():
    resultado = si.validate_synthesis(_manifesto(
        loaded_agent_results=12,
        journal_result_ids=tuple("a%d" % i for i in range(13)),
        cache_result_ids=tuple("a%d" % i for i in range(12))))
    assert resultado.publishable is False
    assert any("faltam 1" in p for p in resultado.problems)


def test_5_journal_completo_cache_incompleto_reprova():
    resultado = si.validate_synthesis(_manifesto(
        cache_result_ids=tuple("a%d" % i for i in range(11)),
        loaded_agent_results=11))
    assert any("ausente(s) no cache" in p for p in resultado.problems)


def test_6_cache_completo_journal_incompleto_reprova():
    resultado = si.validate_synthesis(_manifesto(
        journal_result_ids=tuple("a%d" % i for i in range(11))))
    assert any("ausente(s) no journal" in p for p in resultado.problems)


def test_7_reexecucao_so_do_consolidador_continua_publicavel():
    """Reaproveitar os 13 resultados do journal é legítimo: o que precisa
    fechar é a cardinalidade, não a novidade."""
    resultado = si.validate_synthesis(_manifesto())
    assert resultado.publishable is True


def test_8_ordem_diferente_dos_resultados_nao_e_problema():
    """Ordem não é integridade — recusar por ordem seria rigor teatral."""
    invertido = tuple(reversed(FASES))
    resultado = si.validate_synthesis(_manifesto(observed_phase_ids=invertido))
    assert resultado.publishable is True


def test_9_fase_duplicada_reprova():
    resultado = si.validate_synthesis(_manifesto(
        observed_phase_ids=FASES + ("R3",)))
    assert any("mais de uma vez" in p for p in resultado.problems)


def test_10_fase_desconhecida_reprova():
    resultado = si.validate_synthesis(_manifesto(
        observed_phase_ids=FASES + ("R99",)))
    assert any("R99" in p for p in resultado.problems)


def test_veredito_sem_origem_rastreavel_reprova():
    resultado = si.validate_synthesis(_manifesto(
        verdict_origins=(("v1", "a0"), ("v2", "agente-fantasma"))))
    assert any("agente-fantasma" in p for p in resultado.problems)


def test_veredito_com_origem_conhecida_passa():
    resultado = si.validate_synthesis(_manifesto(
        verdict_origins=(("v1", "a0"), ("v2", "a12"))))
    assert resultado.publishable is True


def test_truncamento_declarado_reprova_mesmo_dentro_do_limite():
    """Declarar o corte é honestidade, não permissão."""
    resultado = si.validate_synthesis(_manifesto(input_truncated=True))
    assert resultado.publishable is False


def test_assert_publishable_levanta_com_o_motivo():
    with pytest.raises(ValueError) as erro:
        si.assert_publishable(_manifesto(loaded_agent_results=1))
    assert "não publicável" in str(erro.value)
    si.assert_publishable(_manifesto())


@pytest.mark.parametrize("entrada", [None, {}, "manifesto", 7])
def test_manifesto_degenerado_nao_levanta(entrada):
    resultado = si.validate_synthesis(entrada)
    assert resultado.publishable is False


def test_o_resultado_diz_quais_checagens_rodaram():
    """Sem isto, "nenhum problema" não distingue "conferi tudo" de "não
    confiei nada"."""
    resultado = si.validate_synthesis(_manifesto())
    assert set(resultado.checks_run) == {
        "agent_cardinality", "phase_coverage", "truncation",
        "journal_cache_agreement", "verdict_traceability"}

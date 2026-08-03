"""Testes da máquina de estados do change set (fase R6).

A invariante que mais importa: **nenhuma operação manual oculta fora do
journal** — inclusive a tentativa recusada, que conta o que alguém tentou
fazer.
"""

import pytest

from mastertool_bridge.changes import lifecycle as lc


def _ate(estado, change_id="CS-001"):
    """Leva um change set até `estado` pelo caminho feliz."""
    ciclo = lc.ChangeSetLifecycle(change_id=change_id)
    while ciclo.state != estado:
        registro = ciclo.advance(actor="operador", reason="avanço de teste")
        assert registro.accepted, (ciclo.state, registro.problems)
    return ciclo


# =============================================================================
# vocabulário e forma
# =============================================================================

def test_os_dez_estados_do_roadmap_estao_presentes():
    for estado in ("draft", "validated", "planned", "authorized", "executed",
                   "verified", "build_passed", "awaiting_approval", "approved",
                   "rejected", "archived"):
        assert estado in lc.LIFECYCLE_STATES
    assert len(set(lc.LIFECYCLE_STATES)) == len(lc.LIFECYCLE_STATES)


def test_a_traducao_para_o_schema_cobre_todo_estado():
    """A divergência entre os dez do roadmap e os seis do schema é declarada,
    e a ponte é total: nenhum estado fica sem tradução."""
    assert set(lc.SCHEMA_STATUS_MAP) == set(lc.LIFECYCLE_STATES)
    destinos = set(lc.SCHEMA_STATUS_MAP.values())
    assert destinos <= {"draft", "validated", "approved", "rejected",
                        "applied", "rolled_back"}


def test_o_caminho_feliz_e_uma_corrente_unica():
    ciclo = lc.ChangeSetLifecycle(change_id="CS-002")
    visitados = [ciclo.state]
    while not ciclo.terminal:
        registro = ciclo.advance(actor="operador", reason="passo")
        assert registro.accepted, registro.problems
        visitados.append(ciclo.state)
    assert visitados == ["draft", "validated", "planned", "authorized",
                         "executed", "verified", "build_passed",
                         "awaiting_approval", "approved", "archived"]


# =============================================================================
# o que a máquina se recusa a permitir
# =============================================================================

def test_pular_etapa_e_recusado():
    """Aprovar o que não foi verificado é o erro que a ordem existe para
    impedir."""
    ciclo = lc.ChangeSetLifecycle(change_id="CS-003")
    registro = ciclo.transition(lc.APPROVED, actor="op", reason="pressa")
    assert registro.accepted is False
    assert ciclo.state == lc.DRAFT
    assert any("não é permitida" in p for p in registro.problems)


def test_voltar_atras_e_recusado():
    ciclo = _ate(lc.VERIFIED)
    registro = ciclo.transition(lc.EXECUTED, actor="op", reason="refazer")
    assert registro.accepted is False
    assert ciclo.state == lc.VERIFIED


def test_estado_terminal_nao_reabre():
    """Reabrir o que já foi encerrado apagaria o registro de que foi
    encerrado."""
    ciclo = _ate(lc.ARCHIVED)
    for destino in lc.LIFECYCLE_STATES:
        registro = ciclo.transition(destino, actor="op", reason="reabrir")
        assert registro.accepted is False
    assert ciclo.state == lc.ARCHIVED
    assert lc.allowed_transitions(lc.ARCHIVED) == ()


def test_transicao_sem_ator_e_recusada():
    """Um estado que mudou sem responsável é operação sem dono."""
    ciclo = lc.ChangeSetLifecycle(change_id="CS-004")
    registro = ciclo.transition(lc.VALIDATED, actor="  ", reason="ok")
    assert registro.accepted is False
    assert any("actor" in p for p in registro.problems)


def test_transicao_sem_motivo_e_recusada():
    ciclo = lc.ChangeSetLifecycle(change_id="CS-005")
    registro = ciclo.transition(lc.VALIDATED, actor="op", reason="")
    assert registro.accepted is False
    assert any("reason" in p for p in registro.problems)


def test_estado_fora_do_vocabulario_e_recusado():
    ciclo = lc.ChangeSetLifecycle(change_id="CS-006")
    registro = ciclo.transition("quase_pronto", actor="op", reason="x")
    assert registro.accepted is False
    assert any("fora do vocabulário" in p for p in registro.problems)


# =============================================================================
# abortar e rollback
# =============================================================================

@pytest.mark.parametrize("estado", ["draft", "validated", "planned",
                                    "authorized"])
def test_abortar_antes_do_artefato_nao_exige_nomear_descarte(estado):
    ciclo = _ate(estado)
    registro = ciclo.reject(actor="op", reason="spec errada")
    assert registro.accepted is True
    assert ciclo.state == lc.REJECTED


@pytest.mark.parametrize("estado", ["executed", "verified", "build_passed",
                                    "awaiting_approval"])
def test_rejeitar_depois_do_artefato_exige_nomear_o_descarte(estado):
    """Sem nomear o artefato, o descarte não é verificável."""
    ciclo = _ate(estado)
    registro = ciclo.reject(actor="op", reason="build com erro")
    assert registro.accepted is False
    assert any("artifact_to_discard" in p for p in registro.problems)
    assert ciclo.state == estado


def test_rollback_nomeia_o_artefato_e_nao_toca_no_original():
    ciclo = _ate(lc.BUILD_PASSED)
    registro = ciclo.rollback(actor="engenheiro", reason="regressão em campo",
                              artifact_to_discard="C:/runs/run-007/saida.project")
    assert registro.accepted is True
    assert ciclo.state == lc.REJECTED
    assert registro.artifact_to_discard.endswith("saida.project")


def test_rollback_antes_de_existir_artefato_e_recusado():
    """Não há o que descartar, e fingir que há esconderia a diferença entre
    abortar um plano e invalidar um artefato."""
    ciclo = _ate(lc.PLANNED)
    registro = ciclo.rollback(actor="op", reason="desistiu",
                              artifact_to_discard="qualquer.project")
    assert registro.accepted is False
    assert any("ainda não existe artefato" in p for p in registro.problems)
    assert ciclo.state == lc.PLANNED


def test_rejeitado_ainda_pode_ser_arquivado():
    ciclo = _ate(lc.PLANNED)
    ciclo.reject(actor="op", reason="cancelado")
    registro = ciclo.advance(actor="op", reason="encerrar")
    assert registro.accepted is True
    assert ciclo.state == lc.ARCHIVED


def test_rejeitado_nao_volta_para_o_caminho_feliz():
    ciclo = _ate(lc.PLANNED)
    ciclo.reject(actor="op", reason="cancelado")
    registro = ciclo.transition(lc.AUTHORIZED, actor="op", reason="mudei de ideia")
    assert registro.accepted is False


# =============================================================================
# journal
# =============================================================================

def test_toda_transicao_entra_no_journal_inclusive_a_recusada():
    """"Nenhuma operação manual oculta" inclui a tentativa que não passou."""
    ciclo = lc.ChangeSetLifecycle(change_id="CS-007")
    ciclo.transition(lc.APPROVED, actor="op", reason="pular")   # recusada
    ciclo.advance(actor="op", reason="validar")                 # aceita
    assert len(ciclo.journal) == 2
    assert ciclo.journal[0].accepted is False
    assert ciclo.journal[1].accepted is True
    assert ciclo.journal[0].to_dict()["problems"]


def test_o_journal_preserva_quem_e_por_que():
    ciclo = lc.ChangeSetLifecycle(change_id="CS-008")
    ciclo.advance(actor="gabriel", reason="spec revisada em reunião")
    registro = ciclo.journal[-1]
    assert registro.actor == "gabriel"
    assert "reunião" in registro.reason


def test_advance_no_fim_da_corrente_registra_a_tentativa():
    ciclo = _ate(lc.ARCHIVED)
    antes = len(ciclo.journal)
    registro = ciclo.advance(actor="op", reason="e agora?")
    assert registro.accepted is False
    assert len(ciclo.journal) == antes + 1


def test_serializacao_completa():
    ciclo = _ate(lc.VERIFIED)
    d = ciclo.to_dict()
    assert d["state"] == "verified"
    assert d["schema_status"] == "applied"
    assert d["has_artifact"] is True
    assert d["allowed_next"] == ["build_passed", "rejected"]
    assert len(d["journal"]) == 5


def test_allowed_transitions_de_estado_desconhecido_e_vazio():
    assert lc.allowed_transitions("inventado") == ()


def test_validate_transition_e_pura_e_nao_muda_nada():
    problemas = lc.validate_transition(lc.DRAFT, lc.APPROVED, actor="op",
                                       reason="x")
    assert problemas
    # chamada de novo, mesmo resultado: sem estado escondido
    assert problemas == lc.validate_transition(lc.DRAFT, lc.APPROVED,
                                               actor="op", reason="x")


# =============================================================================
# aprovação humana -- amarrada à evidência que ela aprovou
# =============================================================================

from mastertool_bridge.changes import approval as ap  # noqa: E402

SHA_PACOTE = "a" * 64


def _decisao(**kwargs):
    base = dict(
        change_id="CS-001",
        decision=ap.DECISION_APPROVED,
        approver="gabriel",
        reason="revisado com o engenheiro responsável",
        decided_at="2026-08-02T09:30",
        bundle_sha256=SHA_PACOTE,
    )
    base.update(kwargs)
    return ap.ApprovalDecision(**base)


def test_aprovacao_move_o_change_set_e_entra_no_journal():
    ciclo = _ate(lc.AWAITING_APPROVAL)
    resultado = ap.record_approval(ciclo, _decisao())
    assert resultado.recorded is True
    assert ciclo.state == lc.APPROVED
    assert ciclo.journal[-1].actor == "gabriel"


def test_aprovar_antes_da_hora_e_recusado():
    """Aprovar em `executed` seria aprovar o que ainda não foi verificado nem
    compilado."""
    ciclo = _ate(lc.EXECUTED)
    resultado = ap.record_approval(ciclo, _decisao())
    assert resultado.recorded is False
    assert any("awaiting_approval" in p for p in resultado.problems)
    assert ciclo.state == lc.EXECUTED


def test_decisao_de_outro_change_set_e_recusada():
    ciclo = _ate(lc.AWAITING_APPROVAL, change_id="CS-999")
    resultado = ap.record_approval(ciclo, _decisao(change_id="CS-001"))
    assert resultado.recorded is False
    assert any("CS-999" in p for p in resultado.problems)


def test_rejeicao_exige_nomear_o_artefato():
    ciclo = _ate(lc.AWAITING_APPROVAL)
    resultado = ap.record_approval(
        ciclo, _decisao(decision=ap.DECISION_REJECTED))
    assert resultado.recorded is False
    assert any("artifact_to_discard" in p for p in resultado.problems)


def test_rejeicao_com_artefato_nomeado_move_para_rejected():
    ciclo = _ate(lc.AWAITING_APPROVAL)
    resultado = ap.record_approval(ciclo, _decisao(
        decision=ap.DECISION_REJECTED,
        artifact_to_discard="C:/runs/run-007/saida.project"))
    assert resultado.recorded is True
    assert ciclo.state == lc.REJECTED


@pytest.mark.parametrize("campo,valor", [
    ("approver", "   "),
    ("reason", ""),
    ("decided_at", "ontem"),
    ("decided_at", "2026-08-02"),
    ("bundle_sha256", "nao-e-sha"),
    ("decision", "talvez"),
])
def test_decisao_malformada_e_recusada(campo, valor):
    problemas = ap.validate_decision(_decisao(**{campo: valor}))
    assert any(campo in p or "esperado" in p for p in problemas)


def test_aprovacao_nao_vale_para_pacote_alterado():
    """O ponto do módulo: divergência de hash não acusa má-fé — constata que
    ninguém aprovou o que está em disco agora."""
    decisao = _decisao()
    assert ap.check_approval(decisao, SHA_PACOTE) == []
    problemas = ap.check_approval(decisao, "b" * 64)
    assert any("ninguém o examinou" in p for p in problemas)


def test_check_approval_nao_confunde_rejeicao_com_aprovacao():
    decisao = _decisao(decision=ap.DECISION_REJECTED,
                       artifact_to_discard="saida.project")
    problemas = ap.check_approval(decisao, SHA_PACOTE)
    assert any("REJEIÇÃO" in p for p in problemas)


def test_check_approval_com_hash_degenerado_reprova():
    assert ap.check_approval(_decisao(), None)
    assert ap.check_approval(_decisao(), "curto")


def test_entrada_degenerada_no_registro_nao_levanta():
    assert ap.record_approval(None, _decisao()).problems
    assert ap.record_approval(lc.ChangeSetLifecycle("CS-1"), None).problems


def test_a_decisao_serializa_com_o_hash_do_pacote():
    d = _decisao().to_dict()
    assert d["bundle_sha256"] == SHA_PACOTE
    assert d["approved"] is True
    assert d["decided_at"] == "2026-08-02T09:30"

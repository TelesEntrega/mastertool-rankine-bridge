"""Gate do slice A0-RV2-FIX — os dois achados, cada um com o seu guarda.

RV2-1  a completude vinha de `manifest.status` e `manifest.missing_required`,
       que ficam FORA do `bundle_sha256` (o selo exclui o manifesto ao
       hashear). Quem tivesse escrita no `bundle_root` removia um arquivo
       obrigatório, recomputava `files` e `bundle_sha256` pelo mesmo
       algoritmo, escrevia `sealed_complete`, e promovia qualquer capacidade
       a `repeatable`.

RV2-2  `independent_runs: 10` era um inteiro digitado. Sem id de execução,
       sem pacote por execução, sem comparação — e a ausência de prova não
       caía nem em `problems` nem em `unresolved`.

Todas as fixtures são SINTÉTICAS: nenhum caminho de campo, nenhum id de run
interna, nenhum hash real. Este arquivo é publicado.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from mastertool_bridge.attestation.loader import (
    ATTESTATION_SCHEMA_VERSION,
    MATURITY_FLOOR,
    load_attestation,
)
from mastertool_bridge.evidence.bundle import (
    MANIFEST_NAME,
    STATUS_SEALED_COMPLETE,
    STATUS_SEALED_INCOMPLETE,
    EvidenceBundle,
    missing_required_in,
    verify_bundle,
)
from mastertool_bridge.evidence.qualification import (
    QUALIFICATION_DIRNAME,
    find_report,
    verify_qualification,
)

from tests.support_attestation import (
    ISSUED_FROM_COMMIT as COMMIT,
    PERFIL,
    PRODUTO,
    VERSAO,
    bundle_sintetico_completo,
    conjunto_sintetico,
    qualificacao_sintetica,
)

_BUNDLE_ROOT, SHA = bundle_sintetico_completo()
_, _SHAS, RUN_IDS, _RELATORIOS = conjunto_sintetico()

CAPACIDADE = "create_program"
OBRIGATORIO = "execution/journal.jsonl"


# =============================================================================
# apoio
# =============================================================================

@pytest.fixture()
def raiz(tmp_path):
    """Uma cópia gravável do conjunto sintético completo."""
    for origem in Path(_BUNDLE_ROOT).iterdir():
        shutil.copytree(origem, tmp_path / origem.name)
    return tmp_path


def _reescrever_manifesto(pacote: Path, **mudancas) -> str:
    """Recomputa `files` e `bundle_sha256` pelo MESMO algoritmo do selo.

    É isto que torna o achado sério: a forja não precisa quebrar hash nenhum,
    porque o hash nunca cobriu o campo forjado.
    """
    manifesto = json.loads((pacote / MANIFEST_NAME).read_text(encoding="utf-8"))
    arquivos = {}
    for caminho in sorted(pacote.rglob("*")):
        if caminho.is_file() and caminho.name != MANIFEST_NAME:
            arquivos[caminho.relative_to(pacote).as_posix()] = hashlib.sha256(
                caminho.read_bytes()).hexdigest()
    resumo = "\n".join("%s %s" % (n, arquivos[n]) for n in sorted(arquivos))
    manifesto["files"] = arquivos
    manifesto["bundle_sha256"] = hashlib.sha256(
        resumo.encode("utf-8")).hexdigest()
    manifesto.update(mudancas)
    (pacote / MANIFEST_NAME).write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n", encoding="utf-8", newline="\n")
    return manifesto["bundle_sha256"]


def _att(raiz, capacidade=CAPACIDADE, **mudancas):
    from mastertool_bridge.contract.fingerprint import core_contract_sha256

    entrada = {
        "maturity": "repeatable",
        "independent_runs": len(RUN_IDS),
        "bundle_sha256": _SHAS[0],
        "evidence_id": "EVID-SINTETICA",
        "qualification_evidence": qualificacao_sintetica(capacidade),
    }
    entrada.update(mudancas)
    return {"schema_version": ATTESTATION_SCHEMA_VERSION,
            "core_contract_sha256": core_contract_sha256(),
            "issued_from_commit": COMMIT, "product": PRODUTO,
            "product_version": VERSAO, "template_profile": PERFIL,
            "capabilities": {capacidade: entrada}}


def _carregar(raiz, doc):
    return load_attestation(doc, expected_product=PRODUTO,
                            expected_product_version=VERSAO,
                            expected_template_profile=PERFIL,
                            bundle_root=str(raiz))


def _qual(raiz, **mudancas):
    bloco = qualificacao_sintetica(CAPACIDADE)
    bloco.update(mudancas)
    return bloco


# =============================================================================
# RV2-1 — a completude é recomputada, nunca lida
# =============================================================================

def test_rv2_1_manifesto_adulterado_para_sealed_complete_NAO_confirma(raiz):
    """A forja exata do achado, ponta a ponta."""
    pacote = raiz / RUN_IDS[0]
    (pacote / OBRIGATORIO).unlink()
    sha = _reescrever_manifesto(pacote, status=STATUS_SEALED_COMPLETE,
                                complete=True, missing_required=[])

    verificacao = verify_bundle(pacote)
    # ÍNTEGRO: nenhum hash foi quebrado, porque nenhum hash cobria o campo.
    assert verificacao.intact, verificacao.problems
    # E MESMO ASSIM incompleto.
    assert not verificacao.complete
    assert OBRIGATORIO in verificacao.effective_missing_required

    carga = _carregar(raiz, _att(raiz, bundle_sha256=sha))
    assert carga.effective_maturity_of(CAPACIDADE) == MATURITY_FLOOR


def test_rv2_1_missing_required_vazio_e_FALSO_nao_torna_o_pacote_completo(raiz):
    pacote = raiz / RUN_IDS[0]
    (pacote / OBRIGATORIO).unlink()
    _reescrever_manifesto(pacote, missing_required=[])

    verificacao = verify_bundle(pacote)
    assert verificacao.manifest_missing_required == []
    assert verificacao.recomputed_missing_required == [OBRIGATORIO]
    assert not verificacao.complete
    assert any("não registra falta" in i for i in verificacao.inconsistencies)


def test_rv2_1_arquivo_removido_com_hashes_RECALCULADOS_e_detectado(raiz):
    pacote = raiz / RUN_IDS[0]
    (pacote / OBRIGATORIO).unlink()
    _reescrever_manifesto(pacote, status=STATUS_SEALED_COMPLETE)

    assert missing_required_in(pacote) == [OBRIGATORIO]
    assert not verify_bundle(pacote).complete


def test_rv2_1_o_manifesto_ACRESCENTA_falta_e_isso_e_respeitado(raiz):
    """A direção oposta, e ela precisa continuar valendo.

    `rollback/` é opcional no layout estático: execução que não altera objeto
    preexistente não tem o que reverter. Quando o plano ALTERA, quem sabe é
    quem montou o pacote, e a falta chega ao selo por `extra_missing`.

    Se a completude passasse a ser SÓ o layout, esta guarda — que custou dez
    pacotes de reversão selados errado — seria desfeita pela correção do
    RV2-1. Por isso o manifesto acrescenta faltas e nunca as remove.
    """
    pacote = raiz / RUN_IDS[0]
    assert missing_required_in(pacote) == []          # layout: nada falta
    _reescrever_manifesto(pacote, status=STATUS_SEALED_INCOMPLETE,
                          missing_required=["rollback/rollback-spec.json"])

    verificacao = verify_bundle(pacote)
    assert verificacao.recomputed_missing_required == []
    assert not verificacao.complete
    assert verificacao.effective_missing_required == [
        "rollback/rollback-spec.json"]


def test_rv2_1_manifesto_INCORRETO_mas_recomputado_completo_e_ACEITO(raiz):
    """Aceito, com a divergência registrada.

    O manifesto diz `sealed_incomplete` e não nomeia falta nenhuma; o disco
    tem tudo. Recusar aqui trataria erro de rótulo como ausência de
    evidência.
    """
    pacote = raiz / RUN_IDS[0]
    _reescrever_manifesto(pacote, status=STATUS_SEALED_INCOMPLETE,
                          missing_required=[])

    verificacao = verify_bundle(pacote)
    assert verificacao.complete
    assert verificacao.inconsistencies

    carga = _carregar(raiz, _att(
        raiz, bundle_sha256=json.loads(
            (pacote / MANIFEST_NAME).read_text(encoding="utf-8"))["bundle_sha256"]))
    assert carga.structurally_valid, carga.problems
    assert carga.effective_maturity_of(CAPACIDADE) == "repeatable"
    assert any("divergência de manifesto" in u for u in carga.unresolved)


def test_rv2_1_pacote_completo_com_manifesto_COERENTE_confirma(raiz):
    verificacao = verify_bundle(raiz / RUN_IDS[0])
    assert verificacao.intact and verificacao.complete
    assert verificacao.inconsistencies == []
    assert verificacao.status == STATUS_SEALED_COMPLETE

    carga = _carregar(raiz, _att(raiz))
    assert carga.structurally_valid, carga.problems
    assert carga.effective_maturity_of(CAPACIDADE) == "repeatable"
    assert carga.unresolved == []


def test_rv2_1_bundle_sem_manifesto_nao_sai_daqui_como_completo(tmp_path):
    """Lista vazia por falta de execução não é lista vazia por conferência."""
    vazio = tmp_path / "pkg"
    vazio.mkdir()
    verificacao = verify_bundle(vazio)
    assert not verificacao.intact
    assert not verificacao.complete


# =============================================================================
# RV2-2 — a independência é comprovada, nunca declarada
# =============================================================================

def test_rv2_2_independent_runs_sem_run_ids_e_RECUSADO(raiz):
    entrada = {"maturity": "repeatable", "independent_runs": 10,
               "bundle_sha256": _SHAS[0], "evidence_id": "EVID-SINTETICA"}
    doc = _att(raiz)
    doc["capabilities"][CAPACIDADE] = entrada

    carga = _carregar(raiz, doc)
    assert not carga.structurally_valid
    assert any("qualification_evidence" in p for p in carga.problems)
    assert carga.effective_maturity_of(CAPACIDADE) == MATURITY_FLOOR


def test_rv2_2_dez_run_ids_DUPLICADOS_sao_recusados(raiz):
    ids = [RUN_IDS[0]] * 10
    doc = _att(raiz, qualification_evidence=_qual(raiz, run_ids=ids))
    doc["capabilities"][CAPACIDADE].pop("independent_runs")

    carga = _carregar(raiz, doc)
    assert not carga.structurally_valid
    assert any("repetição" in p for p in carga.problems), carga.problems


def test_rv2_2_ids_distintos_SEM_relatorio_sao_recusados(raiz):
    bloco = {"run_ids": list(RUN_IDS)}
    carga = _carregar(raiz, _att(raiz, qualification_evidence=bloco))
    assert not carga.structurally_valid
    assert any("comparison_report_sha256" in p for p in carga.problems)


def test_rv2_2_relatorio_AUSENTE_do_disco_e_recusado(raiz):
    shutil.rmtree(raiz / QUALIFICATION_DIRNAME)
    carga = _carregar(raiz, _att(raiz))
    assert not carga.structurally_valid
    assert any("nenhum relatório de comparação" in p for p in carga.problems)


def test_rv2_2_relatorio_ALTERADO_deixa_de_ser_encontrado(raiz):
    """Endereçado por conteúdo: alterar é o mesmo que apagar."""
    sha = qualificacao_sintetica(CAPACIDADE)["comparison_report_sha256"]
    caminho = raiz / QUALIFICATION_DIRNAME / ("%s.json" % sha)
    relatorio = json.loads(caminho.read_text(encoding="utf-8"))
    relatorio["pairwise_independent"] = True          # já era; o byte é outro
    relatorio["metadata"] = {"mexido": True}
    caminho.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2,
                                  sort_keys=True) + "\n",
                       encoding="utf-8", newline="\n")

    assert find_report(raiz, sha) is None
    carga = _carregar(raiz, _att(raiz))
    assert not carga.structurally_valid


def test_rv2_2_relatorio_com_pairwise_independent_FALSO_e_recusado(raiz):
    """A medição existe e diz que não. O grau cai — e o documento também,
    porque declarar `repeatable` contra a própria evidência é contradição."""
    sha = qualificacao_sintetica(CAPACIDADE)["comparison_report_sha256"]
    caminho = raiz / QUALIFICATION_DIRNAME / ("%s.json" % sha)
    relatorio = json.loads(caminho.read_text(encoding="utf-8"))
    relatorio["pairwise_independent"] = False
    relatorio["independence_violations"] = ["gerações 1 e 2 com os mesmos GUIDs"]
    dados = (json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True)
             + "\n").encode("utf-8")
    novo = hashlib.sha256(dados).hexdigest()
    (raiz / QUALIFICATION_DIRNAME / ("%s.json" % novo)).write_bytes(dados)

    carga = _carregar(raiz, _att(raiz, qualification_evidence=_qual(
        raiz, comparison_report_sha256=novo, pairwise_independent=False)))
    assert not carga.structurally_valid
    assert any("pairwise_independent" in p for p in carga.problems)
    assert carga.effective_maturity_of(CAPACIDADE) == MATURITY_FLOOR


def test_rv2_2_documento_que_CONTRADIZ_o_relatorio_e_recusado(raiz):
    """`equivalent: false` no documento, `true` no relatório."""
    carga = _carregar(raiz, _att(raiz, qualification_evidence=_qual(
        raiz, equivalent=False)))
    assert not carga.structurally_valid
    assert any("contradiz a própria evidência" in p for p in carga.problems)


def test_rv2_2_um_dos_dez_bundles_INCOMPLETO_derruba_o_conjunto(raiz):
    (raiz / RUN_IDS[4] / OBRIGATORIO).unlink()
    _reescrever_manifesto(raiz / RUN_IDS[4], status=STATUS_SEALED_COMPLETE,
                          missing_required=[])

    carga = _carregar(raiz, _att(raiz))
    assert carga.effective_maturity_of(CAPACIDADE) == MATURITY_FLOOR
    assert any(RUN_IDS[4] in u for u in carga.unresolved), carga.unresolved


def test_rv2_2_um_dos_dez_runs_INEXISTENTE_e_recusado(raiz):
    shutil.rmtree(raiz / RUN_IDS[7])
    carga = _carregar(raiz, _att(raiz))
    assert not carga.structurally_valid
    assert any("não tem pacote" in p for p in carga.problems)
    assert carga.effective_maturity_of(CAPACIDADE) == MATURITY_FLOOR


def test_rv2_2_relatorio_de_OUTRA_capacidade_nao_respalda_esta(raiz):
    """Um relatório genérico deixaria uma capacidade se apoiar na medição de
    outra — promoção por associação, uma camada abaixo."""
    outro = qualificacao_sintetica("create_gvl")["comparison_report_sha256"]
    carga = _carregar(raiz, _att(raiz, qualification_evidence=_qual(
        raiz, comparison_report_sha256=outro)))
    assert not carga.structurally_valid
    assert any("o relatório fala da capacidade 'create_gvl'" in p
               for p in carga.problems), carga.problems


def test_rv2_2_N10_completo_e_conferido_PROMOVE(raiz):
    carga = _carregar(raiz, _att(raiz))
    assert carga.structurally_valid, carga.problems
    assert carga.evidence_confirmed[CAPACIDADE] is True
    assert carga.effective_maturity_of(CAPACIDADE) == "repeatable"

    check = verify_qualification(CAPACIDADE, qualificacao_sintetica(CAPACIDADE),
                                 str(raiz), 10)
    assert check.confirmed, (check.problems, check.unresolved)
    assert len(check.confirmed_runs) == 10


def test_rv2_2_field_proven_NAO_exige_evidencia_de_conjunto(raiz):
    """Ele pede UMA execução completa e verificável, e o pacote citado já
    prova isso sozinho. Exigir dez ali seria mover o piso do grau."""
    doc = _att(raiz)
    doc["capabilities"][CAPACIDADE] = {
        "maturity": "field_proven", "independent_runs": 1,
        "bundle_sha256": _SHAS[0], "evidence_id": "EVID-SINTETICA"}

    carga = _carregar(raiz, doc)
    assert carga.structurally_valid, carga.problems
    assert carga.effective_maturity_of(CAPACIDADE) == "field_proven"


def test_rv2_2_independent_traduz_a_lista_e_nao_a_substitui(raiz):
    """`independent_runs` é redundância conferida. Discordar da lista é erro
    dele, não da lista."""
    carga = _carregar(raiz, _att(raiz, independent_runs=7))
    assert not carga.structurally_valid
    assert any("mesma coisa" in p for p in carga.problems)


# =============================================================================
# o vínculo contratual acompanha a mudança de semântica
# =============================================================================

def test_a_politica_de_confirmacao_de_bundle_SUBIU(raiz):
    """Sem a subida, uma attestation medida sob a regra antiga — em que a
    completude era forjável — seguiria valendo sob a nova."""
    from mastertool_bridge.contract.fingerprint import (
        BUNDLE_CONFIRMATION_POLICY,
        INDEPENDENCE_EVIDENCE_POLICY,
        core_contract,
    )

    assert BUNDLE_CONFIRMATION_POLICY == 2
    politicas = core_contract()["policies"]
    assert politicas["bundle_confirmation"] == BUNDLE_CONFIRMATION_POLICY
    assert politicas["independence_evidence"] == INDEPENDENCE_EVIDENCE_POLICY


def test_o_carregador_nao_le_status_do_manifesto_para_decidir_completude():
    """Guarda de FORMA, e não de comportamento.

    Voltar a ler `manifest.status` faria os testes acima falharem — mas só
    enquanto alguém lembrar de mantê-los. Esta procura o caminho de volta no
    código, que é como o RV1-1 foi reintroduzido em revisão anterior.
    """
    fonte = Path(
        __file__).resolve().parents[2] / "src" / "mastertool_bridge" / \
        "attestation" / "loader.py"
    texto = fonte.read_text(encoding="utf-8")
    codigo = "\n".join(
        linha for linha in texto.splitlines()
        if not linha.lstrip().startswith("#"))
    assert "STATUS_SEALED_COMPLETE" not in codigo, (
        "o carregador voltou a comparar o status DECLARADO no manifesto; "
        "completude vem de `verificacao.complete`, que percorre o disco")

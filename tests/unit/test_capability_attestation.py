"""Testes do carregador de Capability Attestation.

Os testes centrais aqui são as **recusas**. Uma attestation que promove
capacidade sem respaldo é pior que attestation nenhuma: ela dá ao plano a
aparência de ter sido medido.

Todas as fixtures são SINTÉTICAS. Nenhum commit real, nenhum bundle real,
nenhum id de run interna — este arquivo é publicado.
"""

import hashlib
import io
import json
from pathlib import Path

import pytest

from mastertool_bridge.attestation.loader import (
    ATTESTATION_SCHEMA_VERSION,
    MATURITY_FLOOR,
    REASON_EVIDENCE_NOT_CONFIRMED,
    REASON_NOT_LOADED,
    REASON_REFUSED,
    canonical_bytes,
    canonical_sha256,
    load_attestation,
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

# Bundle SINTÉTICO real: desde RV1-1 a evidência decide, e um `bundle_sha256`
# inventado deixa a capacidade em `discovered` — corretamente. Os testes que
# exercitam PROMOÇÃO precisam de um pacote selado e completo de verdade.
_BUNDLE_ROOT, SHA = bundle_sintetico_completo()

# Desde RV2-2, `repeatable` também exige evidência de CONJUNTO: dez execuções
# com id, cada uma com pacote próprio, e o relatório que as compara.
_, _SHAS, RUN_IDS, _RELATORIOS = conjunto_sintetico()


def _cap(capacidade="create_program", **mudancas):
    entrada = {"maturity": "repeatable", "independent_runs": len(RUN_IDS),
               "bundle_sha256": SHA, "evidence_id": "EVID-SINTETICA-001",
               "qualification_evidence": qualificacao_sintetica(capacidade)}
    entrada.update(mudancas)
    if entrada.get("maturity") in ("discovered", "field_proven"):
        entrada.pop("qualification_evidence", None)
    return entrada


def _qual(**mudancas):
    """`qualification_evidence` com um campo trocado."""
    bloco = qualificacao_sintetica()
    bloco.update(mudancas)
    return bloco


def _preparar(tmp_path):
    """Copia o conjunto sintético inteiro para `tmp_path`.

    Os testes abaixo variam UM fator — o pacote representativo citado — e
    precisam que todo o resto esteja confirmado. Sem isto, um teste sobre
    bundle incompleto passaria a falhar por ausência de relatório de
    comparação, e o nome dele deixaria de descrever o que ele mede.
    """
    import shutil

    for origem in Path(_BUNDLE_ROOT).iterdir():
        shutil.copytree(origem, tmp_path / origem.name)
    return str(tmp_path)


def _att(capabilities=None, **mudancas):
    from mastertool_bridge.contract.fingerprint import core_contract_sha256

    doc = {"schema_version": ATTESTATION_SCHEMA_VERSION,
           "core_contract_sha256": core_contract_sha256(),
           "issued_from_commit": COMMIT, "product": PRODUTO,
           "product_version": VERSAO, "template_profile": PERFIL,
           "capabilities": capabilities or {"create_program": _cap()}}
    doc.update(mudancas)
    return doc


def _carregar(doc=None, **kwargs):
    kwargs.setdefault("bundle_root", _BUNDLE_ROOT)
    kwargs.setdefault("expected_product", PRODUTO)
    kwargs.setdefault("expected_product_version", VERSAO)
    kwargs.setdefault("expected_template_profile", PERFIL)
    return load_attestation(_att() if doc is None else doc, **kwargs)


# =============================================================================
# o caminho aprovado
# =============================================================================

def test_attestation_valida_promove_ate_o_grau_declarado():
    r = _carregar()
    assert r.structurally_valid, r.problems
    assert r.effective_maturity_of("create_program") == "repeatable"


def test_capacidade_AUSENTE_fica_no_piso_e_isso_nao_e_erro():
    """Ausência não é erro: é ausência. O planner a trata como `discovered`."""
    r = _carregar()
    assert r.structurally_valid, r.problems
    assert r.effective_maturity_of("create_dut") == MATURITY_FLOOR
    assert r.reason_for("create_dut") == REASON_NOT_LOADED


def test_attestation_PARCIAL_nao_promove_o_conjunto_por_associacao():
    """O modo de falha que isto impede: uma capacidade comprovada arrastando
    as vizinhas para o mesmo grau."""
    r = _carregar(_att({"create_program": _cap(),
                        "create_gvl": _cap(maturity="field_proven",
                                           independent_runs=1)}))
    assert r.structurally_valid, r.problems
    assert r.effective_maturity_of("create_program") == "repeatable"
    assert r.effective_maturity_of("create_gvl") == "field_proven"
    assert r.effective_maturity_of("create_function") == MATURITY_FLOOR


# =============================================================================
# as 20 recusas
# =============================================================================

def test_recusa_01_attestation_ausente():
    r = load_attestation(None)
    assert not r.structurally_valid
    assert r.effective_maturity_of("create_program") == MATURITY_FLOOR
    assert any("ausente" in p for p in r.problems)


@pytest.mark.parametrize("entrada", ["texto", 7, [], True])
def test_recusa_02_payload_que_nao_e_objeto(entrada):
    assert not load_attestation(entrada).structurally_valid


def test_recusa_03_schema_version_desconhecido():
    r = _carregar(_att(schema_version=99))
    assert not r.structurally_valid
    assert any("desconhecido" in p for p in r.problems)


def test_recusa_04_campo_adicional_no_topo():
    r = _carregar(_att(campo_que_ninguem_conhece=1))
    assert not r.structurally_valid
    assert any("desconhecido" in p for p in r.problems)


def test_recusa_04b_campo_adicional_na_capacidade():
    r = _carregar(_att({"create_program": _cap(inventado=1)}))
    assert not r.structurally_valid


def test_recusa_05_contrato_divergente():
    """O vínculo NORMATIVO. Contrato diferente significa que capacidades,
    mapeamento, pisos ou política de evidência mudaram — a medição de campo
    continua existindo, e não descreve mais este sistema."""
    r = _carregar(_att(core_contract_sha256="c" * 64))
    assert not r.structurally_valid
    assert any("core_contract" in p for p in r.problems)


def test_issued_from_commit_divergente_do_HEAD_NAO_invalida():
    """Proveniência não decide validade.

    Uma attestation versionada dentro da árvore NUNCA aponta para o commit que
    a contém — o commit que a adiciona muda o HEAD. Comparar com o HEAD a faria
    nascer inválida, e reemitir só deslocaria a divergência em um commit."""
    r = _carregar(_att(issued_from_commit="c" * 40))
    assert r.structurally_valid, r.problems
    assert r.effective_maturity_of("create_program") == "repeatable"


def test_issued_from_commit_malformado_recusa():
    r = _carregar(_att(issued_from_commit="nao-e-commit"))
    assert not r.structurally_valid


def test_attestation_do_contrato_ANTIGO_e_recusada_com_erro_categorizado():
    """Documento emitido sob `core_commit`, sem o vínculo novo."""
    doc = _att()
    doc.pop("core_contract_sha256")
    doc["core_commit"] = COMMIT
    r = _carregar(doc)
    assert not r.structurally_valid
    assert any("core_contract_sha256" in p for p in r.problems)


def test_recusa_06_template_profile_divergente():
    r = _carregar(_att(template_profile="outro-perfil"))
    assert not r.structurally_valid
    assert any("template_profile" in p for p in r.problems)


def test_recusa_07_produto_divergente():
    r = _carregar(_att(product="OutroProduto"))
    assert not r.structurally_valid
    assert any("product" in p for p in r.problems)


def test_recusa_08_versao_do_produto_divergente():
    r = _carregar(_att(product_version="9.9.9.9"))
    assert not r.structurally_valid
    assert any("product_version" in p for p in r.problems)


def test_recusa_09_maturidade_fora_da_escala():
    r = _carregar(_att({"create_program": _cap(maturity="quase_provado")}))
    assert not r.structurally_valid
    assert any("fora da escala" in p for p in r.problems)


def test_recusa_10_maturidade_sem_o_minimo_de_runs():
    """`repeatable` com 3 execuções. O número é a medição."""
    r = _carregar(_att({"create_program": _cap(
        independent_runs=3,
        qualification_evidence=_qual(run_ids=RUN_IDS[:3]))}))
    assert not r.structurally_valid
    assert any("o grau exige 10" in p for p in r.problems), r.problems


def test_recusa_11_run_ids_duplicadas():
    """Duas entradas com o mesmo id são UMA execução contada duas vezes, e
    independência é exatamente o que a contagem deveria provar."""
    ids = list(RUN_IDS[:9]) + [RUN_IDS[0]]
    # Sem `independent_runs`: ele é derivado, e informá-lo aqui faria a
    # divergência de contagem disparar ANTES da repetição — mascarando o que
    # este teste mede.
    entrada = _cap(qualification_evidence=_qual(run_ids=ids))
    entrada.pop("independent_runs")
    r = _carregar(_att({"create_program": entrada}))
    assert not r.structurally_valid
    assert any("repetição" in p for p in r.problems), r.problems


def test_recusa_11b_run_ids_em_numero_diferente_do_declarado():
    r = _carregar(_att({"create_program": _cap(
        qualification_evidence=_qual(run_ids=list(RUN_IDS[:2])))}))
    assert not r.structurally_valid
    assert any("mesma coisa" in p for p in r.problems), r.problems


@pytest.mark.parametrize("ruim", ["", "xyz", "B" * 64, "b" * 63, 7, None])
def test_recusa_12_bundle_sha256_malformado(ruim):
    r = _carregar(_att({"create_program": _cap(bundle_sha256=ruim)}))
    assert not r.structurally_valid


def test_recusa_13_bundle_inexistente(tmp_path):
    r = _carregar(bundle_root=str(tmp_path))
    assert not r.structurally_valid
    assert any("nenhum bundle" in p for p in r.problems)


def test_recusa_14_bundle_alterado_depois_do_selo(tmp_path):
    """Pacote adulterado não respalda nada."""
    from mastertool_bridge.evidence.bundle import EvidenceBundle

    pacote = EvidenceBundle(tmp_path / "pkg", "run-sintetica-001").create()
    pacote.add("source", "project.sha256", "d" * 64)
    manifesto = pacote.seal()

    alvo = tmp_path / "pkg" / "source" / "project.sha256"
    alvo.write_text("ADULTERADO", encoding="utf-8")

    r = _carregar(_att({"create_program": _cap(
        bundle_sha256=manifesto.bundle_sha256, independent_runs=10)}),
        bundle_root=str(tmp_path))
    assert not r.structurally_valid
    assert any("NÃO está íntegro" in p for p in r.problems)


def test_recusa_15_hash_do_bundle_divergente(tmp_path):
    """O bundle existe e está íntegro, mas não é o que a attestation cita."""
    from mastertool_bridge.evidence.bundle import EvidenceBundle

    pacote = EvidenceBundle(tmp_path / "pkg", "run-sintetica-001").create()
    pacote.add("source", "project.sha256", "d" * 64)
    pacote.seal()

    r = _carregar(bundle_root=str(tmp_path))
    assert not r.structurally_valid
    assert any("nenhum bundle" in p for p in r.problems)


def test_recusa_16_capacidade_que_nao_existe_no_contrato():
    r = _carregar(_att({"voar": _cap()}),
                  known_capabilities={"create_program", "create_gvl"})
    assert not r.structurally_valid
    assert any("não existe no contrato" in p for p in r.problems)


def test_recusa_17_operacao_sem_attestation_NAO_e_erro_e_fica_no_piso():
    """A contraparte da 16: o contrato pode ter operação que a attestation não
    cobre. Isso é ausência, e ausência não recusa o documento."""
    r = _carregar(known_capabilities={"create_program", "create_dut"})
    assert r.structurally_valid, r.problems
    assert r.effective_maturity_of("create_dut") == MATURITY_FLOOR


def test_recusa_18_maturidade_acima_do_que_os_runs_sustentam():
    r = _carregar(_att({"create_program": _cap(
        maturity="production_qualified", independent_runs=2)}))
    assert not r.structurally_valid


def test_recusa_19_duas_attestations_conflitantes_para_a_mesma_capacidade():
    """JSON não permite chave repetida, então o conflito aparece ao carregar
    DOIS documentos. Carregar o segundo não pode sobrescrever o primeiro em
    silêncio: qual dos dois vale é decisão de quem os emitiu, não do
    carregador."""
    a = _carregar()
    b = _carregar(_att({"create_program": _cap(maturity="field_proven",
                                               independent_runs=1)}))
    assert a.effective_maturity_of("create_program") == "repeatable"
    assert b.effective_maturity_of("create_program") == "field_proven"
    assert a.effective_maturity_of("create_program") != b.effective_maturity_of("create_program")


def test_recusa_20_referencia_documental_no_lugar_do_bundle():
    """Foi assim que a maturidade estática passou a citar evidência ausente do
    pacote: `"evidence": "docs/46 (W6, run-033)"`. Um caminho de documento não
    prova integridade de nada."""
    r = _carregar(_att({"create_program": _cap(
        bundle_sha256="docs/46 (W6, run-033)")}))
    assert not r.structurally_valid
    assert any("Referência documental" in p for p in r.problems)


# =============================================================================
# o caso que decide o slice
# =============================================================================

def test_attestation_INVALIDA_recusa_e_NAO_volta_ao_comportamento_anterior():
    """O teste que falharia se alguém introduzisse fallback silencioso.

    Documento inválido não pode fazer o carregador ignorá-lo e usar a
    maturidade de antes — voltar ao anterior seria promover por código
    estático outra vez, que é o que este módulo existe para remover."""
    r = _carregar(_att(core_commit="c" * 40))
    assert not r.structurally_valid
    assert r.capabilities == {}
    assert r.evidence_confirmed == {}
    assert r.effective_maturity_of("create_program") == MATURITY_FLOOR
    assert r.reason_for("create_program") == REASON_REFUSED


# =============================================================================
# validade estrutural ≠ confiança na evidência
# =============================================================================

def test_sem_bundle_root_o_documento_vale_e_a_evidencia_fica_NAO_confirmada():
    """A distinção que o módulo existe para preservar. Um documento bem
    formado não é um documento respaldado."""
    r = _carregar(bundle_root=None)
    assert r.structurally_valid
    assert r.evidence_confirmed["create_program"] is False
    assert any("não conferida" in u for u in r.unresolved)


def test_conferencia_que_nao_pode_ser_feita_NUNCA_conta_como_bem_sucedida():
    """Contexto que o chamador não informou entra em `unresolved`, não em
    confirmado. Tratar "não sei" como "confere" faria a attestation de um
    contexto valer para outro.

    O `core_contract_sha256` NÃO está entre esses: ele é calculado pelo
    próprio código e sempre pode ser conferido — foi por isso que ele
    substituiu o `core_commit`, que dependia de git."""
    r = load_attestation(_att(), expected_product=None,
                         expected_product_version=None,
                         expected_template_profile=None,
                         bundle_root=_BUNDLE_ROOT)
    assert r.structurally_valid, r.problems
    assert any("product" in u for u in r.unresolved)
    assert not any("core_contract" in u for u in r.unresolved)


def _bundle_completo(raiz, run_id="run-sintetica-001"):
    """Um bundle com TODOS os arquivos obrigatórios do layout.

    Escrito depois de um achado: a versão anterior deste helper adicionava só
    `source/project.sha256`, selava `sealed_incomplete`, e o teste de
    evidência confirmada passava mesmo assim — porque `verify_bundle` só
    confere integridade. O teste estava assertando o defeito."""
    from mastertool_bridge.evidence.bundle import BUNDLE_LAYOUT, EvidenceBundle

    pacote = EvidenceBundle(raiz, run_id).create()
    for secao, layout in BUNDLE_LAYOUT.items():
        for nome in layout["required"]:
            pacote.add(secao, nome, "conteudo-sintetico-%s-%s" % (secao, nome))
    return pacote.seal()


def test_evidencia_CONFIRMADA_quando_o_bundle_existe_esta_integro_e_COMPLETO(
        tmp_path):
    raiz = _preparar(tmp_path)
    manifesto = _bundle_completo(tmp_path / "pkg")
    assert manifesto.status == "sealed_complete"

    r = _carregar(_att({"create_program": _cap(
        bundle_sha256=manifesto.bundle_sha256)}), bundle_root=raiz)
    assert r.structurally_valid, r.problems
    assert r.evidence_confirmed["create_program"] is True
    assert r.unresolved == []


# =============================================================================
# serialização determinística
# =============================================================================

def test_mesmo_conteudo_logico_produz_o_MESMO_digest():
    """Ordem de chave não pode mudar o hash: senão ele deixa de identificar o
    conteúdo e passa a identificar a digitação."""
    a = {"schema_version": 1, "core_commit": COMMIT, "product": PRODUTO}
    b = {"product": PRODUTO, "core_commit": COMMIT, "schema_version": 1}
    assert canonical_sha256(a) == canonical_sha256(b)
    assert canonical_bytes(a) == canonical_bytes(b)


def test_conteudo_diferente_produz_digest_diferente():
    assert canonical_sha256(_att()) != canonical_sha256(
        _att(core_commit="c" * 40))


def test_a_forma_canonica_e_estavel_entre_processos():
    """Sem espaço supérfluo e com chave ordenada: o mesmo documento relido de
    disco tem de dar o mesmo digest."""
    doc = _att()
    bruto = canonical_bytes(doc)
    assert hashlib.sha256(bruto).hexdigest() == canonical_sha256(doc)
    assert canonical_sha256(json.loads(bruto.decode("utf-8"))) == \
        canonical_sha256(doc)


# =============================================================================
# forma
# =============================================================================

def test_a_escala_NAO_e_redefinida_aqui():
    """Duas definições da mesma escala divergem no dia em que alguém
    acrescenta um grau."""
    import mastertool_bridge.attestation.loader as loader
    from mastertool_bridge.templates.profile import MATURITY_SCALE

    assert loader.MATURITY_SCALE is MATURITY_SCALE
    assert loader.MATURITY_FLOOR == MATURITY_SCALE[0] == "discovered"


def test_serializacao_separa_DECLARADA_de_EFETIVA():
    """As duas viajam no artefato, e separadas. Um relatório que só mostrasse
    a declarada esconderia exatamente o que RV1-1 encontrou: capacidade
    escrita como `repeatable` e efetivamente em `discovered` por falta de
    evidência."""
    d = _carregar().to_dict()
    assert d["structurally_valid"] is True
    assert d["declared_capabilities"]["create_program"] == "repeatable"
    assert d["effective_capabilities"]["create_program"] == "repeatable"
    assert "unresolved" in d

    sem_evidencia = _carregar(bundle_root=None).to_dict()
    assert sem_evidencia["declared_capabilities"]["create_program"] == "repeatable"
    assert sem_evidencia["effective_capabilities"]["create_program"] == "discovered"


def test_o_schema_publicado_bate_com_o_carregador():
    """Schema e carregador precisam concordar sobre o que é obrigatório —
    senão um documento aceito por um é recusado pelo outro."""
    from mastertool_bridge.contract import load_schema

    schema = load_schema("capability-attestation")
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version", "core_contract_sha256", "issued_from_commit",
        "product", "product_version", "template_profile", "capabilities"}
    cap = schema["properties"]["capabilities"]["additionalProperties"]
    assert cap["additionalProperties"] is False
    assert set(cap["required"]) == {
        "maturity", "bundle_sha256", "evidence_id"}
    # `independent_runs` saiu dos obrigatorios (RV2-2): ele e derivado de
    # `qualification_evidence.run_ids`, e nunca a fonte.
    assert "independent_runs" not in cap["required"]
    qual = cap["properties"]["qualification_evidence"]
    assert set(qual["required"]) == {"run_ids", "comparison_report_sha256"}


# =============================================================================
# achados da revisão adversarial — cada um com o seu guarda
# =============================================================================

def test_grau_acima_do_piso_com_ZERO_execucoes_e_recusado():
    """ACHADO. `MIN_INDEPENDENT_RUNS` só tem entrada de `repeatable` para
    cima, então `field_proven` com `independent_runs: 0` passava — e
    `field_proven` é exatamente o limiar que o planner exige para considerar
    um plano executável. O buraco ficava no único ponto que decide.

    `field_proven` significa "exercida contra o produto real numa cadeia que
    persistiu e compilou". Zero execuções contradiz a definição."""
    r = _carregar(_att({"create_program": _cap(maturity="field_proven",
                                               independent_runs=0)}))
    assert not r.structurally_valid
    assert any("zero" in p or "0 execucoes" in p for p in r.problems)
    assert r.effective_maturity_of("create_program") == MATURITY_FLOOR


def test_discovered_com_zero_execucoes_continua_valendo():
    """A contraparte: `discovered` é justamente "catalogada, nunca exercida".
    Exigir execução dele tornaria impossível attestar o piso."""
    r = _carregar(_att({"create_program": _cap(maturity="discovered",
                                               independent_runs=0)}))
    assert r.structurally_valid, r.problems
    assert r.effective_maturity_of("create_program") == "discovered"


def test_bundle_INCOMPLETO_e_integro_mas_NAO_confirma_a_evidencia(tmp_path):
    """ACHADO. `verify_bundle` recomputa hashes e diz se alguém mexeu no
    pacote depois do selo; ela não diz se o pacote tem tudo. Um
    `sealed_incomplete` passa por íntegro — e passava por CONFIRMADO.

    Não recusa o documento: um bundle incompleto ainda registra uma execução
    que aconteceu, e recusar apagaria o registro do que deu errado. O que ele
    não pode é contar como evidência confirmada."""
    from mastertool_bridge.evidence.bundle import EvidenceBundle

    raiz = _preparar(tmp_path)
    pacote = EvidenceBundle(tmp_path / "pkg", "run-ruim-001").create()
    pacote.add("source", "project.sha256", "d" * 64)
    manifesto = pacote.seal()
    assert manifesto.status == "sealed_incomplete"

    r = _carregar(_att({"create_program": _cap(
        bundle_sha256=manifesto.bundle_sha256)}), bundle_root=raiz)
    assert r.structurally_valid, r.problems
    assert r.evidence_confirmed["create_program"] is False
    assert any("Íntegro não" in u for u in r.unresolved)


def test_attestation_de_TIPO_ERRADO_e_recusa_nomeada_no_planner():
    """ACHADO. Passar um `dict` cru levantava `AttributeError`, que a rede de
    segurança convertia em "planner falhou de forma não categorizada" —
    fail-closed, mas com o diagnóstico errado: quem chamasse com o objeto
    errado procuraria defeito do planner em vez do próprio erro."""
    from mastertool_bridge.planner.planner import (
        GAP_OPERATION_NOT_FIELD_PROVEN,
        build_authoring_plan,
    )

    spec = {"schema_version": 1, "template": {"id": "x", "sha256": "a" * 64},
            "programs": [{"name": "P1",
                          "declaration": "PROGRAM P1\nEND_PROGRAM",
                          "implementation": ";",
                          "language": {"guid": "cc393387-a21c-4f68-a3e3-84c36951965d"}}]}
    resultado = build_authoring_plan(spec, None, {"create_program": "repeatable"})
    assert resultado.plan is not None, resultado.problems
    assert resultado.plan["executable"] is False
    lacunas = [g for g in resultado.plan["measurement_gaps"]
               if g["kind"] == GAP_OPERATION_NOT_FIELD_PROVEN]
    assert lacunas
    assert all(g["reason"] == REASON_REFUSED for g in lacunas)


# =============================================================================
# RV1-1 — a evidência DECIDE a maturidade efetiva
# =============================================================================
#
# O achado: o carregador CALCULAVA `evidence_confirmed` e o planner não
# consumia o resultado. Uma attestation apontando para um bundle que ninguém
# abriu promovia igual a uma conferida, e a separação entre validade
# estrutural e confiança na evidência era decorativa.

@pytest.mark.parametrize("grau", ["field_proven", "repeatable"])
def test_grau_declarado_SEM_evidencia_confirmada_fica_no_piso(grau):
    runs = 1 if grau == "field_proven" else 10
    r = _carregar(_att({"create_program": _cap(maturity=grau,
                                               independent_runs=runs)}),
                  bundle_root=None)
    assert r.structurally_valid, r.problems
    assert r.declared_maturity_of("create_program") == grau
    assert r.effective_maturity_of("create_program") == MATURITY_FLOOR
    assert r.reason_for("create_program") == REASON_EVIDENCE_NOT_CONFIRMED


def test_bundle_AUSENTE_deixa_a_capacidade_no_piso(tmp_path):
    r = _carregar(bundle_root=str(tmp_path))
    assert not r.structurally_valid
    assert r.effective_maturity_of("create_program") == MATURITY_FLOOR


def test_bundle_INCOMPLETO_deixa_a_capacidade_no_piso(tmp_path):
    """Íntegro não é completo. O documento continua válido — um bundle
    incompleto registra uma execução que aconteceu — mas não promove."""
    from mastertool_bridge.evidence.bundle import EvidenceBundle

    raiz = _preparar(tmp_path)
    pacote = EvidenceBundle(tmp_path / "pkg", "run-ruim-001").create()
    pacote.add("source", "project.sha256", "d" * 64)
    manifesto = pacote.seal()
    assert manifesto.status == "sealed_incomplete"

    r = _carregar(_att({"create_program": _cap(
        bundle_sha256=manifesto.bundle_sha256)}), bundle_root=raiz)
    assert r.structurally_valid, r.problems
    assert r.declared_maturity_of("create_program") == "repeatable"
    assert r.effective_maturity_of("create_program") == MATURITY_FLOOR


def test_bundle_COMPLETO_promove():
    r = _carregar()
    assert r.effective_maturity_of("create_program") == "repeatable"
    assert r.evidence_confirmed["create_program"] is True


def test_attestation_MISTA_promove_so_o_que_tem_lastro(tmp_path):
    """Lacuna individual de evidência NÃO invalida as capacidades
    confirmadas — e também não promove o documento como bloco."""
    from mastertool_bridge.evidence.bundle import EvidenceBundle

    raiz = _preparar(tmp_path)
    ruim = EvidenceBundle(tmp_path / "ruim", "run-ruim-002").create()
    ruim.add("source", "project.sha256", "e" * 64)
    manifesto_ruim = ruim.seal()

    r = _carregar(_att({
        "create_program": _cap(),
        "create_gvl": _cap("create_gvl",
                           bundle_sha256=manifesto_ruim.bundle_sha256)}),
        bundle_root=raiz)
    assert r.structurally_valid, r.problems
    assert r.effective_maturity_of("create_program") == "repeatable"
    assert r.effective_maturity_of("create_gvl") == MATURITY_FLOOR


def test_o_planner_NAO_le_maturidade_declarada_em_lugar_nenhum():
    """Busca explícita no caminho do planner. `declared_maturity_of` existe
    para diagnóstico e relatório; consumi-la para decidir seria desfazer
    RV1-1 sem que nenhum teste de comportamento acusasse."""
    import io as _io
    import os as _os

    raiz = _os.path.dirname(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__))))
    fonte = _io.open(_os.path.join(raiz, "src", "mastertool_bridge",
                                   "planner", "planner.py"),
                     encoding="utf-8").read()
    assert "declared_maturity_of" not in fonte
    assert "effective_maturity_of" in fonte


# =============================================================================
# o vínculo contratual — o que invalida e o que NÃO invalida
# =============================================================================

def _com_contrato_alterado(monkeypatch, **mudanca):
    """Recarrega a mesma attestation depois de mexer numa decisão do contrato.

    O documento não muda: quem muda é o núcleo. É exatamente esse o caso que
    o vínculo existe para pegar — medição feita sob outras regras."""
    import mastertool_bridge.contract.fingerprint as fp

    doc = _att()
    for atributo, valor in mudanca.items():
        monkeypatch.setattr(fp, atributo, valor)
    return _carregar(doc)


def test_mudanca_de_POLITICA_de_maturidade_efetiva_invalida(monkeypatch):
    r = _com_contrato_alterado(monkeypatch, EFFECTIVE_MATURITY_POLICY=2)
    assert not r.structurally_valid
    assert any("core_contract" in p for p in r.problems)


def test_mudanca_de_POLITICA_de_confirmacao_de_bundle_invalida(monkeypatch):
    r = _com_contrato_alterado(monkeypatch, BUNDLE_CONFIRMATION_POLICY=99)
    assert not r.structurally_valid


def test_mudanca_no_REGISTRO_de_capacidades_invalida(monkeypatch):
    """Capacidade a mais ou a menos muda o que o sistema sabe fazer."""
    import mastertool_bridge.planner.capabilities as cap

    doc = _att()
    monkeypatch.setattr(
        cap, "KNOWN_CAPABILITIES", frozenset(cap.KNOWN_CAPABILITIES | {"voar"}))
    assert not _carregar(doc).structurally_valid


def test_remover_configure_task_do_MAPEAMENTO_invalida(monkeypatch):
    import mastertool_bridge.planner.capabilities as cap

    doc = _att()
    reduzido = {k: v for k, v in cap.OPERATION_TO_CAPABILITY.items()
                if k != "configure_task"}
    monkeypatch.setattr(cap, "OPERATION_TO_CAPABILITY", reduzido)
    assert not _carregar(doc).structurally_valid


def test_mudanca_no_MINIMO_de_execucoes_invalida(monkeypatch):
    import mastertool_bridge.templates.profile as perfil

    doc = _att()
    monkeypatch.setattr(perfil, "MIN_INDEPENDENT_RUNS",
                        dict(perfil.MIN_INDEPENDENT_RUNS, repeatable=3))
    assert not _carregar(doc).structurally_valid


def test_mudanca_no_LIMIAR_executavel_invalida(monkeypatch):
    import mastertool_bridge.planner.planner as planner

    doc = _att()
    monkeypatch.setattr(planner, "REQUIRED_MATURITY", "repeatable")
    assert not _carregar(doc).structurally_valid


def test_o_fingerprint_NAO_depende_de_comentario_nem_de_documentacao():
    """A razão de o vínculo não ser o hash de `planner.py`: comentário,
    docstring e documentação não decidem nada, e fazê-los expirar uma medição
    de campo seria ruído com cara de rigor."""
    from mastertool_bridge.contract.fingerprint import core_contract_bytes

    bruto = core_contract_bytes().decode("utf-8")
    assert "#" not in bruto
    assert "docs/" not in bruto
    assert "\"\"\"" not in bruto

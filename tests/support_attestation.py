"""Attestation sintética com evidência REAL, para os testes que precisam de um
plano executável.

POR QUE ELA PRECISA DE UM BUNDLE DE VERDADE
===========================================
Desde o achado RV1-1, maturidade declarada não promove nada sozinha: só o grau
**efetivo** conta, e ele exige que a evidência tenha sido confirmada — bundle
localizado pelo `bundle_sha256`, íntegro e completo.

Antes disso os helpers montavam um documento e pronto. Eles passavam porque o
carregador calculava `evidence_confirmed` e ninguém consumia o resultado; o
plano saía executável com uma attestation apontando para um bundle que não
existia. Sessenta e oito testes quebraram quando a evidência passou a decidir,
e isso é a correção funcionando, não regressão.

O bundle é construído UMA vez por processo, num diretório temporário, com
todos os arquivos obrigatórios do layout. Sintético de ponta a ponta: nenhum
hash real, nenhum id de run interna.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

ISSUED_FROM_COMMIT = "a" * 40
CORE_COMMIT = ISSUED_FROM_COMMIT          # compat: nome antigo
PRODUTO = "MasterTool X"
VERSAO = "4.1.0.11"
PERFIL = "perfil-sintetico-v1"

RUNS_SINTETICAS = 10

_CACHE: dict[str, object] = {}


def _selar(raiz: Path, run_id: str) -> str:
    """Um pacote completo, com conteúdo VARIADO por execução.

    Conteúdo idêntico em todos daria o mesmo `bundle_sha256` nos dez — o
    manifesto fica fora do hash do conjunto, então o `run_id` sozinho não
    diferencia. Dez pacotes indistinguíveis por hash é exatamente o cenário
    que a evidência de conjunto existe para reprovar, e uma fixture que o
    reproduz por descuido testa o oposto do que diz testar.
    """
    from mastertool_bridge.evidence.bundle import BUNDLE_LAYOUT, EvidenceBundle

    pacote = EvidenceBundle(raiz / run_id, run_id).create()
    for secao, layout in BUNDLE_LAYOUT.items():
        for nome in layout["required"]:
            pacote.add(secao, nome, "sintetico-%s-%s-%s" % (secao, nome, run_id))
    manifesto = pacote.seal()
    assert manifesto.status == "sealed_complete", manifesto.status
    return manifesto.bundle_sha256


def _relatorio_sintetico(capacidade: str, run_ids: list[str]):
    """Um `RepeatabilityResult` REAL com veredito sintético.

    A classe é a de produção, e por isso o relatório tem a forma de produção.
    O que é sintético é o VEREDITO — offline não há MasterTool para comparar
    gerações, e fabricar equivalência é o único jeito de exercitar o
    carregador sem o produto.

    Isso não afrouxa nada em campo: a conferência exige o relatório em disco,
    endereçado por conteúdo, com os mesmos ids, e cada pacote aberto. A
    fixture constrói tudo isso de verdade.
    """
    from mastertool_bridge.automation.generation_equivalence import (
        RepeatabilityResult,
    )

    return RepeatabilityResult(
        layout="sintetico",
        generations=list(run_ids),
        reference=run_ids[0],
        minimum_required=RUNS_SINTETICAS,
        per_generation=[{"generation": r, "equivalent": True} for r in run_ids],
        independence_violations=[],
        problems=[],
    )


def bundle_sintetico_completo() -> tuple[str, str]:
    """`(bundle_root, bundle_sha256)` de um pacote SELADO e COMPLETO.

    Cacheado por processo: selar é barato, mas repetir por teste tornaria a
    suíte mais lenta sem provar nada — o que cada teste exercita é o
    carregador, não o empacotador.
    """
    raiz, shas, _, _ = _conjunto_sintetico()
    return raiz, shas[0]


def conjunto_sintetico() -> tuple[str, list[str], list[str], dict]:
    """API pública do conjunto — ver `_conjunto_sintetico`."""
    return _conjunto_sintetico()


def qualificacao_sintetica(capacidade: str = "create_program") -> dict:
    """O bloco `qualification_evidence` que promove a `repeatable`."""
    _, _, run_ids, relatorios = _conjunto_sintetico()
    return {
        "run_ids": list(run_ids),
        "comparison_report_sha256": relatorios.get(capacidade, "0" * 64),
        "equivalent": True,
        "pairwise_independent": True,
    }


def _conjunto_sintetico() -> tuple[str, list[str], list[str], dict]:
    """`(bundle_root, shas, run_ids, comparison_report_sha256)`.

    As dez execuções que o grau `repeatable` passou a exigir (achado RV2-2).
    """
    if "conjunto" not in _CACHE:
        from mastertool_bridge.evidence.qualification import (
            build_report,
            write_report,
        )

        raiz = Path(tempfile.mkdtemp(prefix="attestation-sintetica-"))
        run_ids = ["run-sintetica-%03d" % (i + 1)
                   for i in range(RUNS_SINTETICAS)]
        shas = [_selar(raiz, r) for r in run_ids]
        assert len(set(shas)) == len(shas), "pacotes sintéticos colidiram"

        # UM relatório por capacidade: `verify_qualification` confere que o
        # relatório fala da capacidade citada, e um relatório genérico faria a
        # fixture passar por um caminho que produção não tem.
        from mastertool_bridge.planner.capabilities import KNOWN_CAPABILITIES

        por_capacidade = {}
        for capacidade in sorted(KNOWN_CAPABILITIES):
            _, sha = write_report(raiz, build_report(
                capacidade, run_ids, _relatorio_sintetico(capacidade, run_ids)))
            por_capacidade[capacidade] = sha
        _CACHE["conjunto"] = (str(raiz), shas, run_ids, por_capacidade)
    return _CACHE["conjunto"]                                  # type: ignore


def documento(capacidades, *, issued_from_commit: str = ISSUED_FROM_COMMIT,
              core_contract_sha256: str | None = None) -> dict:
    """A attestation em si, cobrindo `capacidades` com evidência confirmável.

    O `core_contract_sha256` é calculado do contrato CORRENTE — é o vínculo
    normativo, e uma fixture com hash fixo passaria a recusar no dia em que
    qualquer decisão do contrato mudasse, que é exatamente o comportamento
    desejado em produção e ruído numa fixture.
    """
    from mastertool_bridge.contract.fingerprint import (
        core_contract_sha256 as fingerprint,
    )

    _, shas, run_ids, relatorios = _conjunto_sintetico()
    return {
        "schema_version": 1,
        "core_contract_sha256": core_contract_sha256 or fingerprint(),
        "issued_from_commit": issued_from_commit,
        "product": PRODUTO,
        "product_version": VERSAO,
        "template_profile": PERFIL,
        "capabilities": {
            nome: {
                "maturity": "repeatable",
                "independent_runs": len(run_ids),
                "bundle_sha256": shas[0],
                "evidence_id": "EVID-SINTETICA",
                "qualification_evidence": {
                    "run_ids": list(run_ids),
                    # Capacidade fora do registro canônico não tem relatório —
                    # e o documento é recusado pelo nome antes de chegar à
                    # evidência. O hash nulo mantém a forma válida para que o
                    # teste falhe pelo motivo que ele testa.
                    "comparison_report_sha256": relatorios.get(nome, "0" * 64),
                    "equivalent": True,
                    "pairwise_independent": True,
                },
            }
            for nome in capacidades},
    }


def attestation_completa():
    """Cobre TODO o `EXECUTOR_CONTRACT`, com evidência confirmada.

    É o cenário normal da maioria dos testes de planner e executor: eles são
    sobre outra coisa (ordem topológica, hashes, allowlist derivada), e exigir
    plano executável faz parte do enunciado deles. Os testes que são SOBRE a
    ausência de attestation ou sobre evidência não confirmada montam o próprio
    documento, de propósito.
    """
    from mastertool_bridge.attestation import load_attestation
    from mastertool_bridge.planner.capabilities import KNOWN_CAPABILITIES

    raiz, _ = bundle_sintetico_completo()
    return load_attestation(documento(sorted(KNOWN_CAPABILITIES)),
                            expected_product=PRODUTO,
                            expected_product_version=VERSAO,
                            expected_template_profile=PERFIL,
                            bundle_root=raiz)

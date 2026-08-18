"""A impressão digital do CONTRATO — o vínculo normativo da attestation.

POR QUE ELA SUBSTITUI `core_commit`
===================================
Amarrar a attestation a um commit não tem ponto fixo. O documento mora dentro
da árvore, e o commit que o carrega muda o `HEAD` — então ele nasce obsoleto
por exatamente um commit, o dele mesmo. Reemitir só desloca a divergência.

Pior: um commit que mexe em documentação, teste ou relatório invalidaria uma
medição de campo que nada tem a ver com isso.

O vínculo passa a ser o que DECIDE:

    quais capacidades existem
    como operação mapeia para capacidade
    qual maturidade é efetiva
    que evidência é exigida
    quando um plano pode ser executável

    core_contract_sha256    vínculo NORMATIVO — divergiu, a attestation cai
    issued_from_commit      proveniência — auditoria, nunca validade

NÃO É O HASH DE `planner.py`
============================
Hashear o arquivo inteiro faria comentário, formatação e função sem relação
expirarem attestations. O que entra aqui é um objeto MONTADO pelo código, com
as decisões e nada mais — e por isso ele é reproduzível na wheel instalada e
no checkout, nas duas árvores, sem git.

Que ele não precise de git é consequência, e é boa: um pacote instalado não
tem repositório, e antes disso o contexto operacional era impossível de montar
fora de um checkout.

VERSÕES DE POLÍTICA
===================
`effective_maturity` e `bundle_confirmation` são números que sobem quando a
SEMÂNTICA muda sem que nenhuma estrutura mude junto. Sem eles, trocar "bundle
incompleto não confirma" por "confirma" deixaria o fingerprint intacto — e uma
attestation medida sob a regra antiga seguiria valendo sob a nova.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

CONTRACT_VERSION = 1

# Sobe quando a regra de derivação da maturidade EFETIVA muda. Hoje:
# evidência não confirmada derruba a capacidade para o piso, sem invalidar o
# documento nem as outras capacidades.
EFFECTIVE_MATURITY_POLICY = 1

# Sobe quando muda o que confirma uma evidência.
#
#   1  bundle localizado pelo `bundle_sha256`, íntegro E com `status`
#      `sealed_complete` LIDO do manifesto.
#   2  completude RECOMPUTADA do layout percorrendo o disco (achado RV2-1). O
#      manifesto só acrescenta faltas, nunca as remove.
#
# A subida é o que impede uma attestation medida sob a regra 1 de seguir
# valendo sob a 2 — e ela precisa cair, porque sob a regra 1 a completude era
# forjável por quem tivesse escrita no `bundle_root`.
BUNDLE_CONFIRMATION_POLICY = 2

# Sobe quando muda o que prova que N execuções são N execuções.
#
#   1  `run_ids` distintos obrigatórios de `repeatable` para cima, cada
#      execução com pacote localizado, íntegro e completo, mais relatório de
#      comparação endereçado por conteúdo com `equivalent` e
#      `pairwise_independent` CONFERIDOS no relatório (achado RV2-2).
#
# Antes disso não havia política: `independent_runs` era um inteiro digitado.
INDEPENDENCE_EVIDENCE_POLICY = 1


def _minimos_efetivos() -> dict[str, int]:
    """O piso de execuções por grau, como ele REALMENTE é aplicado.

    `MIN_INDEPENDENT_RUNS` só tem entrada de `repeatable` para cima. O piso de
    `field_proven` é derivado — qualquer grau acima de `discovered` exige ao
    menos uma execução —, e foi justamente a ausência dele que deixou
    `field_proven` com zero runs passar (achado RV1-1 da revisão).

    O fingerprint registra a política aplicada, não a tabela crua: se
    registrasse a tabela, mudar o piso derivado não invalidaria nada.
    """
    from mastertool_bridge.templates.profile import (
        MATURITY_SCALE,
        MIN_INDEPENDENT_RUNS,
    )

    minimos = {}
    for grau in MATURITY_SCALE[1:]:
        minimos[grau] = int(MIN_INDEPENDENT_RUNS.get(grau, 1))
    return minimos


def _hashes_dos_schemas() -> dict[str, str]:
    """sha256 de cada schema do contrato operacional.

    Um schema que mude a forma do que atravessa a fronteira muda o contrato,
    e uma attestation medida sob a forma anterior não descreve mais o mesmo
    sistema.
    """
    from mastertool_bridge.contract import SCHEMAS, schema_path

    return {nome: hashlib.sha256(
        schema_path(nome).read_bytes()).hexdigest()
        for nome in sorted(SCHEMAS)}


def core_contract() -> dict[str, Any]:
    """O objeto canônico. MONTADO pelo código, nunca escrito à mão."""
    from mastertool_bridge.planner.capabilities import (
        KNOWN_CAPABILITIES,
        OPERATION_TO_CAPABILITY,
    )
    from mastertool_bridge.planner.planner import REQUIRED_MATURITY
    from mastertool_bridge.templates.profile import MATURITY_SCALE

    # Escritas de propriedade: `configure_task` não é chamada de método, e é a
    # única capacidade cujo alcance é um conjunto de NOMES em vez de uma API.
    #
    # A fonte é `spec/task_property_source.py`, do lado `src/`, e não o
    # registro de `scripts/mastertool/common/safety.py`. Os dois descrevem a
    # mesma coisa por ângulos diferentes — a allowlist do gate e o vocabulário
    # que o planner sabe autorar —, e fazer a biblioteca importar dos scripts
    # criaria a dependência que o publicador existe para detectar.
    from mastertool_bridge.spec.task_property_source import TASK_PROPERTIES

    return {
        "contract_version": CONTRACT_VERSION,
        "maturity_scale": list(MATURITY_SCALE),
        "minimum_runs": _minimos_efetivos(),
        "known_capabilities": sorted(KNOWN_CAPABILITIES),
        "operation_capabilities": dict(sorted(OPERATION_TO_CAPABILITY.items())),
        "property_write_capabilities": sorted(TASK_PROPERTIES),
        "policies": {
            "effective_maturity": EFFECTIVE_MATURITY_POLICY,
            "bundle_confirmation": BUNDLE_CONFIRMATION_POLICY,
            "independence_evidence": INDEPENDENCE_EVIDENCE_POLICY,
            "planner_threshold": REQUIRED_MATURITY,
        },
        "schema_hashes": _hashes_dos_schemas(),
    }


def core_contract_bytes() -> bytes:
    """Serialização canônica: chaves ordenadas, sem espaço supérfluo, UTF-8.

    Mesma disciplina da attestation — se a ordem das chaves mudasse o hash, ele
    identificaria a digitação em vez do conteúdo.
    """
    return json.dumps(core_contract(), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def core_contract_sha256() -> str:
    return hashlib.sha256(core_contract_bytes()).hexdigest()

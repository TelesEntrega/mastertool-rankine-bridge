"""A ÚNICA entrada operacional que carrega uma attestation.

POR QUE ELA EXISTE (achado RV1-2)
=================================
As conferências de identidade, de capacidade conhecida e de integridade do
bundle existiam no carregador — e o caminho de produção não passava nenhuma
delas. `emit_authoring_plan.py` chamava `load_default_attestation(repo_root)`
sem nada, e as três viravam `unresolved` ou eram puladas.

Verificação que só roda quando alguém lembra de ligá-la é verificação que não
roda. E não bastava acrescentar argumento opcional: enquanto `None` continuasse
aceito, o esquecimento seguiria sendo silencioso.

Esta função MONTA o contexto inteiro — registro canônico de capacidades,
diretório de bundles, caminho da attestation — e só então chama o carregador.
Peça faltando é RECUSA nomeada, não omissão:

    capability_attestation_validation_context_missing

DE ONDE VEM CADA PEÇA
=====================
`contrato`      calculado pelo próprio código
                (`contract/fingerprint.py`). NÃO vem de git: uma wheel
                instalada não tem repositório, e o vínculo normativo da
                attestation deixou de ser o commit justamente porque commit
                não descreve comportamento.

`bundle_root`   de `MASTERTOOL_BUNDLE_ROOT` ou do argumento. NÃO vem da
                attestation, e nem do contrato: caminho local não entra em
                schema compartilhado. Apontar para o diretório errado não é
                falha de segurança — os bundles não são encontrados, a
                evidência não confirma, e a capacidade fica `discovered`.

`capacidades`   do registro canônico derivado do `EXECUTOR_CONTRACT`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from mastertool_bridge.attestation.loader import (
    REASON_CONTEXT_MISSING,
    AttestationLoad,
    load_default_attestation,
)

ENV_BUNDLE_ROOT = "MASTERTOOL_BUNDLE_ROOT"

# Peças do contexto. Lista LITERAL: uma peça nova entra aqui e passa a ser
# exigida, em vez de ser esquecida por quem escreveu a chamada.
CONTEXT_FIELDS = ("known_capabilities", "bundle_root")


def current_core_commit(repo_root: Path | str) -> str | None:
    """`HEAD` da árvore, ou `None` fora de um repositório git.

    Serve para EMITIR uma attestation (o campo `issued_from_commit`, que é
    proveniência). NÃO participa da validação: desde o binding contratual,
    quem decide se a attestation vale é `core_contract_sha256`, e um pacote
    instalado — que não tem git — precisa conseguir validar.
    """
    try:
        saida = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo_root),
            capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    commit = (saida.stdout or "").strip()
    return commit if saida.returncode == 0 and commit else None


def load_for_execution(repo_root: Path | str, *,
                       bundle_root: Path | str | None = None,
                       expected_product: str | None = None,
                       expected_product_version: str | None = None,
                       expected_template_profile: str | None = None
                       ) -> AttestationLoad:
    """Carrega a attestation com o contexto COMPLETO, ou recusa dizendo o que
    faltou.

    Nunca devolve `None`: ausência de attestation e contexto incompleto são
    estados diferentes, e os dois precisam de um resultado que o chamador possa
    inspecionar. `None` obrigaria quem chama a distinguir os dois casos por
    outro meio, e é assim que um deles acaba tratado como o outro.
    """
    from mastertool_bridge.planner.capabilities import KNOWN_CAPABILITIES

    raiz = Path(repo_root)
    bundles = bundle_root or os.environ.get(ENV_BUNDLE_ROOT) or None

    faltando = []
    if not KNOWN_CAPABILITIES:
        faltando.append("known_capabilities")
    if not bundles:
        faltando.append("bundle_root")
    elif not Path(bundles).is_dir():
        faltando.append("bundle_root")

    if faltando:
        recusa = AttestationLoad()
        recusa.problems.append(
            "%s: %s. O contexto de validação é montado por inteiro ou não é "
            "montado — argumento opcional que aceita ausência faz a "
            "conferência depender de alguém lembrar de ligá-la"
            % (REASON_CONTEXT_MISSING, ", ".join(faltando)))
        return recusa

    carga = load_default_attestation(
        raiz,
        expected_product=expected_product,
        expected_product_version=expected_product_version,
        expected_template_profile=expected_template_profile,
        bundle_root=bundles,
        known_capabilities=KNOWN_CAPABILITIES)

    if carga is None:
        vazio = AttestationLoad()
        vazio.problems.append(
            "nenhuma attestation versionada nesta árvore. Sem ela nenhuma "
            "capacidade passa de `discovered` — que é o estado correto de uma "
            "árvore sem evidência, e não uma degradação")
        return vazio
    return carga

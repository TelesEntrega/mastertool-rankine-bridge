"""Reaplica a validação HOST-SIDE a uma run supervisionada já arquivada.

Existe porque o `final_state=failed` das runs anteriores a 2026-07-28 não
vem da aquisição: vem da seção `runtime` que o runner interno nunca emitia
(ver `fix: include runtime provenance in supervised run report`). A coleta
era válida; o veredito derivado dela é que estava errado.

**Não refaz a execução** e **não reescreve nada coberto pelos checksums da
coleta.** A revisão sai em arquivos novos (`host-validation-revision.json`/
`.md`), como já se faz para a reclassificação do probe 17.

LIMITE HONESTO, e é o ponto principal deste módulo: uma run arquivada
**não pode** ter a procedência confirmada por máquina retroativamente. O
dado legível não está lá — o `run-report.json` foi gerado antes do fix.
O que existe é evidência SECUNDÁRIA: o estado `provenance_validated` no
`status-history.jsonl`, escrito pelo runner interno depois de a checagem
passar de verdade dentro do MasterTool.

Este módulo reporta as duas coisas separadamente e nunca as funde. Declarar
`confirmed` a partir da evidência secundária seria fabricar o resultado que
a correção existe justamente para tornar verificável.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mastertool_bridge.automation.artifact_validation import validate_output_artifacts
from mastertool_bridge.automation.cli_probe_verify import check_provenance
from mastertool_bridge.automation.run_states import (
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_PROVENANCE_VALIDATED,
)

# Versão do contrato DESTE artefato (revisão host-side de run arquivada),
# inteiro. Constante própria: a revisão pode ganhar campos sem que os
# artefatos da run mudem — são contratos separados, cada um com seu ritmo.
# Ver `docs/19-contratos-de-execucao.md`, seção 7.
REVISION_SCHEMA_VERSION = 1

REVISION_JSON_FILENAME = "host-validation-revision.json"
REVISION_MD_FILENAME = "host-validation-revision.md"

INTERNAL_PROVENANCE_STATE = STATE_PROVENANCE_VALIDATED


class HostRevisionError(Exception):
    """Diretório de run inválido ou incompleto."""


@dataclass(frozen=True)
class HostValidationRevision:
    run_dir: Path
    original_final_state: str | None
    revised_final_state: str
    provenance_machine_check: dict
    provenance_internal_evidence: dict
    artifact_validation_ok: bool
    artifact_errors: list[str] = field(default_factory=list)
    semantic_results: dict = field(default_factory=dict)
    project_hash_unchanged: bool | None = None
    blocking_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REVISION_SCHEMA_VERSION,
            "revision_of": str(self.run_dir),
            "operational": {
                "original_final_state": self.original_final_state,
                "revised_final_state": self.revised_final_state,
                "blocking_reasons": self.blocking_reasons,
            },
            "provenance": {
                "machine_check": self.provenance_machine_check,
                "internal_runner_evidence": self.provenance_internal_evidence,
                "note": (
                    "Confirmação por máquina NÃO é possível retroativamente: a "
                    "seção `runtime` do run-report.json não existia quando esta "
                    "run foi produzida. A evidência interna é secundária e não "
                    "substitui a checagem."
                ),
            },
            "artifacts": {
                "ok": self.artifact_validation_ok,
                "errors": self.artifact_errors,
            },
            "semantic_results": self.semantic_results,
            "project_hash_unchanged": self.project_hash_unchanged,
            "raw_collection_preserved": True,
        }


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HostRevisionError(f"arquivo ausente: {path.name}") from exc
    except ValueError as exc:
        raise HostRevisionError(f"arquivo inválido (JSON): {path.name}") from exc


def _internal_provenance_evidence(run_dir: Path) -> dict:
    """Procura o estado `provenance_validated` no histórico. É evidência de
    que a checagem passou DENTRO do MasterTool — secundária, porque é uma
    string de log, não o dado estruturado que o host verifica."""
    history = run_dir / "status-history.jsonl"
    if not history.is_file():
        return {"found": False, "reason": "status-history.jsonl ausente"}
    for line in history.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("state") == INTERNAL_PROVENANCE_STATE:
            return {
                "found": True,
                "state": INTERNAL_PROVENANCE_STATE,
                "detail": entry.get("detail"),
                "updated_at": entry.get("updated_at"),
                "is_secondary_evidence": True,
            }
    return {"found": False, "reason": f"estado {INTERNAL_PROVENANCE_STATE} ausente do histórico"}


def _collect_semantic_results(output_dir: Path) -> dict:
    """Lê o veredito de cada probe presente, SEM reinterpretá-lo. Resultado
    semântico inconclusivo (E3/E4, caso D) não é falha operacional e não
    entra em `blocking_reasons`."""
    results: dict[str, Any] = {}
    for dirname, keys in (
            ("ladder-surface-probe", ("candidate_count",)),
            ("ladder-dynamic-surface", ("result_case", "status", "ladder_candidate_count")),
            ("ladder-extender-probe", ("result_case", "status", "extender_channel_validated",
                                       "ladder_candidate_count")),
    ):
        manifest = output_dir / dirname / "manifest.json"
        if manifest.is_file():
            data = _read_json(manifest)
            results[dirname] = {k: data.get(k) for k in keys if k in data}
    return results


def revise_run(run_dir: Path | str, *, operations: dict | None = None) -> HostValidationRevision:
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise HostRevisionError(f"diretório de run inexistente: {run_dir}")
    output_dir = run_dir / "output"
    if not output_dir.is_dir():
        raise HostRevisionError(f"output/ ausente em {run_dir}")

    run_report = _read_json(output_dir / "run-report.json")
    machine_check = check_provenance(run_report)
    internal_evidence = _internal_provenance_evidence(run_dir)

    # `archived_revision=True`: esta função SEMPRE revisa uma run já
    # arquivada, nunca uma execução nova. Artefatos que passaram a ser
    # exigidos depois da run existir viram aviso, não erro — a run não pode
    # ser corrigida retroativamente e refazer a aquisição é proibido.
    artifact_result = validate_output_artifacts(
        output_dir, operations=operations, archived_revision=True)

    # Só falha OPERACIONAL bloqueia. Procedência ausente continua bloqueando
    # (fail-closed), mas agora com a razão nomeada — o operador vê que é
    # lacuna de registro, não execução externa.
    blocking: list[str] = []
    if not artifact_result.ok:
        blocking.extend(f"artefato: {e}" for e in artifact_result.errors)
    if not machine_check["inside_mastertool"]:
        blocking.append(
            f"procedência: {machine_check.get('reason_code')} — {machine_check.get('reason')}")

    config_path = run_dir / "run-config.json"
    operations_from_config = None
    if operations is None and config_path.is_file():
        operations_from_config = (_read_json(config_path) or {}).get("operations")
        if operations_from_config:
            artifact_result = validate_output_artifacts(
                output_dir, operations=operations_from_config,
                archived_revision=True)
            blocking = [b for b in blocking if not b.startswith("artefato: ")]
            if not artifact_result.ok:
                blocking.extend(f"artefato: {e}" for e in artifact_result.errors)

    original_state = None
    status_path = run_dir / "status.json"
    if status_path.is_file():
        original_state = (_read_json(status_path) or {}).get("state")

    return HostValidationRevision(
        run_dir=run_dir,
        original_final_state=STATE_FAILED,
        revised_final_state=STATE_COMPLETED if not blocking else STATE_FAILED,
        provenance_machine_check=machine_check,
        provenance_internal_evidence=internal_evidence,
        artifact_validation_ok=artifact_result.ok,
        artifact_errors=list(artifact_result.errors),
        semantic_results=_collect_semantic_results(output_dir),
        project_hash_unchanged=None if original_state is None else True,
        blocking_reasons=blocking,
    )


def _render_markdown(rev: HostValidationRevision) -> str:
    lines = [
        "# Revisão de validação host-side",
        "",
        f"Run: `{rev.run_dir.name}`",
        "",
        "A **execução não foi refeita**. Nenhum arquivo coberto pelos "
        "checksums da coleta foi alterado. Apenas a validação host-side foi "
        "reaplicada aos artefatos existentes.",
        "",
        "## Estado operacional",
        "",
        f"- original: `{rev.original_final_state}`",
        f"- revisado: **`{rev.revised_final_state}`**",
        "",
    ]
    if rev.blocking_reasons:
        lines += ["Motivos que ainda bloqueiam:", ""]
        lines += [f"- {r}" for r in rev.blocking_reasons]
        lines += [""]

    mc = rev.provenance_machine_check
    ev = rev.provenance_internal_evidence
    lines += [
        "## Procedência — duas coisas distintas",
        "",
        f"**Checagem por máquina**: `{mc.get('reason_code') or 'confirmed'}`.",
        "",
    ]
    if not mc.get("inside_mastertool"):
        lines += [
            "A seção `runtime` não existe no `run-report.json` desta run — ela "
            "foi produzida antes do fix que passou a emiti-la. Isso é "
            "**ausência de prova**, não prova de execução fora do MasterTool.",
            "",
        ]
    if ev.get("found"):
        lines += [
            "**Evidência interna (secundária)**: o runner registrou o estado "
            f"`{ev['state']}` em `{ev.get('updated_at')}` — "
            f"*{ev.get('detail')}*",
            "",
            "Isso indica que a checagem passou dentro do MasterTool, mas é uma "
            "linha de log, não o dado estruturado que o host verifica. **Não "
            "promove esta run a procedência confirmada por máquina** — só uma "
            "execução nova, já com o fix, produz isso.",
            "",
        ]
    if rev.semantic_results:
        lines += ["## Resultados semânticos (não são falha operacional)", ""]
        for name, data in rev.semantic_results.items():
            pairs = ", ".join(f"`{k}`={v}" for k, v in data.items())
            lines += [f"- **{name}**: {pairs}"]
        lines += [
            "",
            "Um probe inconclusivo (E3/E4, caso D) é uma investigação que "
            "executou corretamente sem confirmar seu canal. Não é falha de "
            "infraestrutura e não bloqueia o estado operacional.",
            "",
        ]
    lines += [
        "## Artefatos",
        "",
        f"- validação: **{'ok' if rev.artifact_validation_ok else 'reprovada'}**",
        "",
    ]
    return "\n".join(lines)


def write_revision(rev: HostValidationRevision) -> tuple[Path, Path]:
    json_path = rev.run_dir / REVISION_JSON_FILENAME
    md_path = rev.run_dir / REVISION_MD_FILENAME
    for path in (json_path, md_path):
        if path.name in ("run-report.json", "checksums.sha256", "status.json",
                         "status-history.jsonl", "run-config.json"):
            raise HostRevisionError(
                f"recusado: {path.name} pertence ao registro da execução.")
    json_path.write_text(
        json.dumps(rev.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(rev), encoding="utf-8")
    return json_path, md_path

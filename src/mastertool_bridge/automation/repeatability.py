"""Orquestração de N execuções independentes — o mecanismo da fase R1.

Roda no lado HOST (CPython 3) e **não lança o MasterTool**. Quem executa é um
callable injetado (`executor`), e a razão é a regra de segurança do projeto:
escrita dentro do produto acontece em sessão supervisionada, com o operador
presente. Este módulo faz o que dá para fazer sem o produto aberto — preparar,
isolar, conferir invariante, agregar e julgar — e é inteiramente exercitável
offline com um executor sintético.

O QUE ESTE MÓDULO DECIDE, E O QUE ELE SE RECUSA A DECIDIR
========================================================
Ele decide se um LOTE qualifica. Não decide se uma execução isolada "deu
certo": isso quem diz é o executor, e este módulo confere o que foi entregue
contra a lista literal de artefatos exigidos.

Três invariantes que valem antes de qualquer execução começar:

* **cada run parte de uma cópia nova, em diretório próprio.** Diretório de
  saída que já existe faz o lote inteiro recusar ANTES da primeira execução —
  reaproveitar saída transformaria "dez execuções" em "uma execução e nove
  leituras do mesmo resultado";
* **a entrada permanece idêntica byte a byte.** O sha256 do projeto de origem
  é conferido antes e depois de cada run; divergir reprova a run e o lote;
* **run incompleta nunca entra como sucesso.** Faltando qualquer artefato da
  lista exigida, a run é `incomplete` — e `incomplete` não é `completed` nem é
  descartável: entra no relatório, e reprova o lote.

POR QUE CONTINUAR DEPOIS DE UMA FALHA
=====================================
Parar na primeira run que falha economiza tempo e destrói a evidência que
justifica o lote existir. Continuar mostra a diferença entre falha isolada,
falha sistemática, falha dependente da ordem e falha intermitente — quatro
diagnósticos com quatro tratamentos diferentes, indistinguíveis a partir de
uma única execução interrompida. O lote inteiro reprova de qualquer forma: uma
run inconsistente reprova a qualificação mesmo que as outras nove passem.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mastertool_bridge.automation.generation_equivalence import (
    LAYOUT_FACTORY,
    RepeatabilityResult,
    compare_many,
)

SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# Vocabulário FECHADO de status de execução. `incomplete` existe separado de
# `failed` porque as duas pedem investigações diferentes: `failed` é o produto
# dizendo que não deu; `incomplete` é o produto tendo dito qualquer coisa e o
# artefato não estar lá para conferir.
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_INCOMPLETE = "incomplete"
STATUS_NOT_RUN = "not_run"

RUN_STATUSES = (STATUS_COMPLETED, STATUS_FAILED, STATUS_INCOMPLETE,
                STATUS_NOT_RUN)

# Artefatos que uma run PRECISA entregar para ser considerada completa. Lista
# literal e auditável: o que não está aqui não é exigido, e o que está aqui não
# é opcional. Nomes conferidos contra o que a fábrica já grava hoje.
REQUIRED_RUN_ARTIFACTS = (
    "execution-manifest.json",
    "execution-steps.json",
    "execution-completion.json",
)


@dataclass(frozen=True)
class QualificationRequest:
    qualification_id: str
    template_profile: str
    source_project_sha256: str
    specification: str
    runs: int
    output_root: str
    continue_after_failure: bool = True


@dataclass(frozen=True)
class RunSlot:
    """Uma vaga de execução, já com identidade e destino — decidida ANTES de
    qualquer execução, para que a numeração não dependa de o que deu certo."""

    index: int
    run_id: str
    output_dir: Path


@dataclass
class RunOutcome:
    run_id: str
    status: str
    output_dir: str
    problems: list[str] = field(default_factory=list)
    input_sha256_before: str | None = None
    input_sha256_after: str | None = None
    missing_artifacts: list[str] = field(default_factory=list)

    @property
    def completed(self) -> bool:
        return self.status == STATUS_COMPLETED

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "output_dir": self.output_dir,
            "problems": list(self.problems),
            "input_sha256_before": self.input_sha256_before,
            "input_sha256_after": self.input_sha256_after,
            "missing_artifacts": list(self.missing_artifacts),
        }


@dataclass
class QualificationResult:
    qualification_id: str
    requested_runs: int
    outcomes: list[RunOutcome] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    equivalence: RepeatabilityResult | None = None

    @property
    def completed_runs(self) -> int:
        return sum(1 for o in self.outcomes if o.completed)

    @property
    def all_runs_completed(self) -> bool:
        return (len(self.outcomes) == self.requested_runs
                and self.completed_runs == self.requested_runs)

    @property
    def qualified(self) -> bool:
        """DERIVADO. Todas as condições, e não a maioria delas: o critério da
        fase é `N solicitadas = N concluídas = N equivalentes`, e uma execução
        inconsistente reprova mesmo com todas as outras aprovadas."""
        return (
            not self.problems
            and self.all_runs_completed
            and self.equivalence is not None
            and self.equivalence.repeatable
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "qualification_id": self.qualification_id,
            "qualified": self.qualified,
            "requested_runs": self.requested_runs,
            "completed_runs": self.completed_runs,
            "all_runs_completed": self.all_runs_completed,
            "runs": [o.to_dict() for o in self.outcomes],
            "problems": list(self.problems),
            "equivalence": (self.equivalence.to_dict()
                            if self.equivalence is not None else None),
        }


def validate_request(request: Any) -> list[str]:
    """Problemas da solicitação, sem levantar. Lista vazia = solicitação
    aceitável."""
    problems: list[str] = []
    if not isinstance(request, QualificationRequest):
        return ["request: esperado QualificationRequest, recebido %s"
                % type(request).__name__]

    for campo in ("qualification_id", "template_profile", "specification",
                  "output_root"):
        valor = getattr(request, campo)
        if not isinstance(valor, str) or not valor.strip():
            problems.append("%s: string não vazia obrigatória" % campo)

    if not isinstance(request.source_project_sha256, str) \
            or not _SHA256_RE.match(request.source_project_sha256):
        problems.append("source_project_sha256: esperado hex de 64 caracteres")

    if isinstance(request.runs, bool) or not isinstance(request.runs, int) \
            or request.runs < 1:
        problems.append("runs: esperado inteiro >= 1")

    return problems


def plan_iterations(request: QualificationRequest) -> list[RunSlot]:
    """As N vagas, numeradas com largura fixa.

    `run-001` e não `run-1`: a ordenação lexicográfica dos diretórios passa a
    coincidir com a ordem de execução, e o relatório fica legível sem depender
    de quem o lê saber ordenar números como texto.
    """
    raiz = Path(request.output_root)
    return [
        RunSlot(index=i, run_id="run-%03d" % i, output_dir=raiz / ("run-%03d" % i))
        for i in range(1, request.runs + 1)
    ]


def _artifacts_missing(output_dir: Path) -> list[str]:
    return [nome for nome in REQUIRED_RUN_ARTIFACTS
            if not (output_dir / nome).is_file()]


def execute_qualification(
    request: QualificationRequest,
    executor: Callable[[RunSlot], dict],
    layout: dict | None = None,
    minimum_required: int | None = None,
) -> QualificationResult:
    """Roda as N vagas pelo `executor` e julga o lote.

    `executor` recebe uma `RunSlot` e devolve um dicionário com, no mínimo,
    `status`; opcionalmente `input_sha256_before`, `input_sha256_after` e
    `problems`. Ele é injetado porque o que executa de verdade abre o
    MasterTool, e este módulo nunca abre.
    """
    resultado = QualificationResult(
        qualification_id=getattr(request, "qualification_id", ""),
        requested_runs=getattr(request, "runs", 0) or 0,
    )

    problemas_de_forma = validate_request(request)
    if problemas_de_forma:
        resultado.problems.extend(problemas_de_forma)
        return resultado

    vagas = plan_iterations(request)

    # Recusa ANTES da primeira execução: saída que já existe faria o lote medir
    # artefato de outro lote sem que nada avisasse.
    ocupados = [str(v.output_dir) for v in vagas if v.output_dir.exists()]
    if ocupados:
        resultado.problems.append(
            "diretório de saída já existe, e reaproveitar saída não é repetir "
            "execução: " + ", ".join(sorted(ocupados)))
        return resultado

    for vaga in vagas:
        vaga.output_dir.mkdir(parents=True, exist_ok=True)
        desfecho = RunOutcome(run_id=vaga.run_id, status=STATUS_NOT_RUN,
                              output_dir=str(vaga.output_dir))
        try:
            bruto = executor(vaga)
        except Exception as exc:  # noqa: BLE001 — falha do executor é dado
            desfecho.status = STATUS_FAILED
            desfecho.problems.append("executor levantou: %r" % (exc,))
            resultado.outcomes.append(desfecho)
            if not request.continue_after_failure:
                break
            continue

        if not isinstance(bruto, dict):
            desfecho.status = STATUS_INCOMPLETE
            desfecho.problems.append(
                "executor devolveu %s, esperado dict" % type(bruto).__name__)
            resultado.outcomes.append(desfecho)
            if not request.continue_after_failure:
                break
            continue

        desfecho.input_sha256_before = bruto.get("input_sha256_before")
        desfecho.input_sha256_after = bruto.get("input_sha256_after")
        problemas = bruto.get("problems")
        if isinstance(problemas, list):
            desfecho.problems.extend(str(p) for p in problemas)

        status_bruto = bruto.get("status")
        if status_bruto not in RUN_STATUSES:
            desfecho.status = STATUS_INCOMPLETE
            desfecho.problems.append(
                "status %r fora do vocabulário fechado" % (status_bruto,))
        else:
            desfecho.status = status_bruto

        # A entrada tem de sair intacta. Conferido mesmo quando a run se
        # declara bem-sucedida: uma run que altera o projeto de origem é o
        # pior sucesso possível.
        antes, depois = desfecho.input_sha256_before, desfecho.input_sha256_after
        if antes is not None and depois is not None and antes != depois:
            desfecho.status = STATUS_FAILED
            desfecho.problems.append(
                "projeto de origem mudou durante a run: %s != %s"
                % (antes, depois))
        elif antes is not None and antes != request.source_project_sha256:
            desfecho.status = STATUS_FAILED
            desfecho.problems.append(
                "projeto de origem não é o declarado na solicitação: %s != %s"
                % (antes, request.source_project_sha256))

        if desfecho.status == STATUS_COMPLETED:
            faltando = _artifacts_missing(vaga.output_dir)
            if faltando:
                # Declarou sucesso e não entregou: `incomplete`, nunca
                # `completed`. O status vem do que está em disco, não do que a
                # run diz de si mesma.
                desfecho.status = STATUS_INCOMPLETE
                desfecho.missing_artifacts = faltando
                desfecho.problems.append(
                    "run declarada completa sem entregar: " + ", ".join(faltando))

        resultado.outcomes.append(desfecho)
        if desfecho.status != STATUS_COMPLETED and not request.continue_after_failure:
            break

    faltantes = request.runs - len(resultado.outcomes)
    if faltantes > 0:
        resultado.problems.append(
            "%d run(s) não executada(s) — o lote parou antes do fim"
            % faltantes)

    concluidas = [Path(o.output_dir) for o in resultado.outcomes if o.completed]
    if len(concluidas) >= 2:
        resultado.equivalence = compare_many(
            concluidas, layout=layout or LAYOUT_FACTORY,
            minimum_required=minimum_required)
    else:
        resultado.problems.append(
            "menos de duas runs concluídas: não há o que comparar, e um lote "
            "sem comparação não qualifica")

    return resultado

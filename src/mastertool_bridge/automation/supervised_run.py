"""Orquestrador de HOST (Python 3.11, roda FORA do MasterTool) da Etapa B —
`docs/16-supervised-runner-contract.md`, seção 9 ("Host").

Sequência (ver `orchestrate_run()`): valida a cópia descartável, bloqueia se
houver instância do MasterTool aberta, cria o workspace de execução,
inicia o MT8500 com UI visível e `--runscript=<bootstrap.py>`, aguarda com
timeout configurável SEM matar o processo se estourar, confere hash final,
valida artefatos, confere procedência, roda o indexador Python 3 existente
e produz o relatório consolidado.

Determinístico e testável sem MasterTool: `process_launcher` e
`process_lister` são seams injetáveis — os testes NUNCA disparam
`MT8500.exe` nem `tasklist` de verdade.
"""

from __future__ import annotations

import csv
import hashlib
import io
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from mastertool_bridge.automation.artifact_validation import validate_output_artifacts
from mastertool_bridge.automation.cli_probe_verify import check_provenance
from mastertool_bridge.automation.config_models import (
    LadderProbeConfig,
    RunConfig,
    RunOperations,
)
from mastertool_bridge.automation.result_models import (
    IndexResult,
    ProvenanceCheckResult,
    SupervisedRunResult,
)
from mastertool_bridge.automation.run_workspace import create_run_workspace, read_status

MASTERTOOL_PROCESS_PREFIX = "MT8500"


# =============================================================================
# Detecção de processo MT8500 (tasklist — sem dependência nova; psutil NÃO
# está nas dependências do projeto)
# =============================================================================

def _parse_tasklist_csv(output: str) -> list[dict]:
    """Parseia a saída de `tasklist /FO CSV /NH` em uma lista de
    `{"image_name": str, "pid": int}`. Tolerante a linhas malformadas
    (nunca levanta exceção por causa delas — fail-closed pertence à camada
    de decisão, não ao parser)."""
    rows: list[dict] = []
    if not output:
        return rows
    for row in csv.reader(io.StringIO(output)):
        if len(row) < 2:
            continue
        image_name = row[0].strip()
        try:
            pid = int(row[1].strip())
        except ValueError:
            continue
        if image_name:
            rows.append({"image_name": image_name, "pid": pid})
    return rows


def default_process_lister(image_prefix: str = MASTERTOOL_PROCESS_PREFIX) -> list[dict]:
    """Lista processos correntes com nome iniciando por `image_prefix`
    (case-insensitive) usando `tasklist` (sem dependência nova). Devolve
    lista vazia se `tasklist` falhar — a camada que decide bloquear/reportar
    deve tratar isso como "não foi possível confirmar", nunca como "não há
    processo" silenciosamente (ver `check_no_mastertool_running`)."""
    try:
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError(
            "não foi possível executar 'tasklist' para checar instâncias do "
            "MasterTool em execução — fail-closed, abortando.") from None

    rows = _parse_tasklist_csv(proc.stdout)
    prefix_upper = image_prefix.upper()
    return [r for r in rows if r["image_name"].upper().startswith(prefix_upper)]


# =============================================================================
# Hash SHA256 (host — nunca reaproveita common/checksums.py, que é do lado
# interno IronPython 2.7; a lógica é trivial e roda em runtimes diferentes)
# =============================================================================

def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_path(value: str | Path) -> str:
    import os
    return os.path.normcase(os.path.normpath(str(value)))


# =============================================================================
# Erros do orquestrador
# =============================================================================

class SupervisedRunAbortedError(Exception):
    """Levantada por validações de pré-condição fatais (fail-closed), antes
    mesmo de o MasterTool ser iniciado. Sempre resulta em `final_state`
    `failed` — nunca é deixada escapar de `orchestrate_run()`."""


def build_command_line(
    mastertool_exe: str | Path,
    project_path: str | Path,
    bootstrap_path: str | Path,
) -> str:
    """Monta a linha de comando do MT8500 como STRING, com as aspas em volta
    do VALOR de cada flag — a única forma comprovada em runtime real.

    Não use lista com `subprocess`: no Windows o `list2cmdline` cita o token
    inteiro quando ele contém espaço, produzindo `"--project=C:\\..."` (aspa
    ANTES do nome da flag). O MT8500 3.63 não reconhece a flag nesse formato
    e a ignora **em silêncio** — foi assim que a primeira execução
    supervisionada abriu o MasterTool sem projeto nenhum, sem erro nenhum.

    O formato produzido aqui é idêntico ao que os testes t3 e t4 da Etapa A
    validaram via PowerShell:

        "<exe>" --project="<projeto>" --runscript="<bootstrap>"

    Nenhum valor pode conter aspa dupla: caminho do Windows não aceita `"`,
    então isso indicaria entrada corrompida e é rejeitado em vez de escapado.
    """
    parts = {
        "mastertool_exe": str(mastertool_exe),
        "project_path": str(project_path),
        "bootstrap_path": str(bootstrap_path),
    }
    for name, value in parts.items():
        if '"' in value:
            raise ValueError(
                "%s contém aspa dupla, o que é impossível num caminho Windows "
                "válido e indicaria entrada corrompida: %r" % (name, value))

    return '"%s" --project="%s" --runscript="%s"' % (
        parts["mastertool_exe"], parts["project_path"], parts["bootstrap_path"])


def _result(
    *,
    run_id: str,
    final_state: str,
    reasons: list[str],
    project_copy_path: str,
    project_hash_before: str,
    run_dir: str | None = None,
    exit_code: int | None = None,
    duration_seconds: float | None = None,
    project_hash_after: str | None = None,
    project_hash_unchanged: bool | None = None,
    orphan_process_detected: bool = False,
    orphan_process_ids: list[int] | None = None,
    provenance: ProvenanceCheckResult | None = None,
    artifact_validation=None,
    index_result: IndexResult | None = None,
    internal_status: dict | None = None,
) -> SupervisedRunResult:
    return SupervisedRunResult(
        run_id=run_id,
        run_dir=run_dir,
        final_state=final_state,
        exit_code=exit_code,
        duration_seconds=duration_seconds,
        project_copy_path=project_copy_path,
        project_hash_before=project_hash_before,
        project_hash_after=project_hash_after,
        project_hash_unchanged=project_hash_unchanged,
        orphan_process_detected=orphan_process_detected,
        orphan_process_ids=orphan_process_ids or [],
        provenance=provenance,
        artifact_validation=artifact_validation,
        index_result=index_result,
        internal_status=internal_status,
        reasons=reasons,
    )


# =============================================================================
# Orquestração principal
# =============================================================================

def orchestrate_run(
    *,
    project_copy: str | Path,
    original_project: str | Path,
    runs_root: str | Path,
    mastertool_exe: str | Path,
    repo_root: str | Path,
    mastertool_scripts_dir: str | Path,
    expected_application_name: str,
    expected_application_guid: str,
    expected_application_type_guid: str,
    timeout_seconds: float = 900.0,
    run_index: bool = True,
    expected_index_counts: dict | None = None,
    operations: RunOperations | None = None,
    probe_ladder_surface: bool = False,
    ladder_probe: dict | None = None,
    run_id: str | None = None,
    process_launcher: Callable[[str], "subprocess.Popen"] | None = None,
    process_lister: Callable[[], list[dict]] | None = None,
    poll_interval_seconds: float = 1.0,
    monotonic: Callable[[], float] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> SupervisedRunResult:
    """Executa a sequência completa da Etapa B do lado host. NUNCA levanta
    exceção por uma falha de negócio esperada (cópia==original, timeout,
    hash divergente, etc.) — todas viram `SupervisedRunResult` com
    `final_state` apropriado. Só propaga exceções verdadeiramente
    inesperadas (ex.: `runs_root` sem permissão de escrita)."""
    # `cmd` é uma STRING (ver a montagem do comando, passo 4): no Windows ela
    # chega verbatim ao CreateProcess, preservando `--project="<valor>"`.
    # shell=False permanece — não há shell na cadeia.
    process_launcher = process_launcher or (lambda cmd: subprocess.Popen(cmd, shell=False))
    process_lister = process_lister or default_process_lister
    monotonic = monotonic or time.monotonic
    sleep = sleep or time.sleep
    # `probe_ladder_surface` só é usado para montar o `RunOperations`
    # default quando o chamador NÃO passou `operations` explicitamente —
    # se `operations` já veio pronto (ex.: CLI ligando --no-scan/
    # --no-export-text junto com a sondagem Ladder), ele é a autoridade e o
    # parâmetro solto é ignorado (documentação da decisão: evita dois
    # lugares "donos" do mesmo booleano).
    operations = operations or RunOperations(probe_ladder_surface=probe_ladder_surface)

    ladder_probe_config: LadderProbeConfig | None = None
    if ladder_probe is not None:
        ladder_probe_config = LadderProbeConfig(**ladder_probe)

    project_copy_path = Path(project_copy)
    original_project_path = Path(original_project)
    run_id = run_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # --- 0. coerência run_index / export_text -------------------------------
    # Achado real (2026-07-24, ver contrato seção 3.1): quando a operação
    # Ladder está ligada e scan_project_tree/export_text estão desligados,
    # não há export textual nenhum para indexar. Em vez de o índice ser
    # pedido e pular em silêncio (o defeito já corrigido da Etapa B), uma
    # config que pede índice sem export textual é reprovada explicitamente
    # ANTES de o MasterTool ser iniciado.
    if run_index and not operations.export_text:
        return _result(
            run_id=run_id, final_state="failed",
            reasons=["run_index=True pedido mas operations.export_text=False "
                     "— configuração incoerente: sem export textual não há "
                     "o que indexar. Passe run_index=False (--no-index na "
                     "CLI) quando export_text estiver desligado."],
            project_copy_path=str(project_copy_path), project_hash_before="")

    # --- 1. valida a cópia descartável -------------------------------------
    if not project_copy_path.is_file():
        return _result(
            run_id=run_id, final_state="failed",
            reasons=[f"project_copy não encontrado: {project_copy_path}"],
            project_copy_path=str(project_copy_path), project_hash_before="")

    if _normalize_path(project_copy_path) == _normalize_path(original_project_path):
        return _result(
            run_id=run_id, final_state="failed",
            reasons=["project_copy aponta para o PROJETO ORIGINAL — recusado, "
                     "fail-closed. Use sempre uma cópia descartável."],
            project_copy_path=str(project_copy_path), project_hash_before="")

    project_hash_before = sha256_of_file(project_copy_path)

    # --- 2. bloqueia se houver instância do MasterTool em execução --------
    try:
        running = process_lister()
    except RuntimeError as exc:
        return _result(
            run_id=run_id, final_state="failed",
            reasons=[str(exc)],
            project_copy_path=str(project_copy_path),
            project_hash_before=project_hash_before)

    if running:
        pids = ", ".join(str(r["pid"]) for r in running)
        return _result(
            run_id=run_id, final_state="failed",
            reasons=[f"instância(s) do MasterTool já em execução (PID {pids}) — "
                     "recusado, fail-closed. Feche antes de rodar."],
            project_copy_path=str(project_copy_path),
            project_hash_before=project_hash_before)

    # --- 3. cria o workspace de execução ------------------------------------
    runs_root_path = Path(runs_root)
    run_dir = runs_root_path / run_id
    output_dir = run_dir / "output"

    config = RunConfig(
        run_id=run_id,
        mode="supervised_snapshot",
        repo_root=str(repo_root),
        mastertool_scripts_dir=str(mastertool_scripts_dir),
        expected_project_path=str(project_copy_path),
        expected_project_sha256=project_hash_before,
        expected_application_name=expected_application_name,
        expected_application_guid=expected_application_guid,
        expected_application_type_guid=expected_application_type_guid,
        run_dir=str(run_dir),
        output_dir=str(output_dir),
        allowed_output_root=str(runs_root_path),
        operations=operations,
        ladder_probe=ladder_probe_config,
    )
    run_dir = create_run_workspace(runs_root_path, run_id, config)
    bootstrap_path = run_dir / "bootstrap.py"

    # --- 4. monta o comando --------------------------------------------------
    # NUNCA --scriptargs (quebra em espaços, Etapa A) nem --noUI (fora de
    # escopo).
    #
    # ACHADO REAL da primeira execução supervisionada (2026-07-24 21:00): a
    # versão anterior passava uma LISTA ao subprocess, e isso não funciona
    # aqui. No Windows, `subprocess.list2cmdline` cita o TOKEN INTEIRO quando
    # ele contém espaço:
    #
    #     "--project=C:\\...\\Pasta Com Espacos\\...\\COPIA.project"
    #      ^ a aspa vem ANTES de --project
    #
    # O MT8500 não reconhece a flag nesse formato e a ignora em silêncio — o
    # MasterTool abriu SEM projeto. O `--runscript` escapou por acidente: o
    # caminho do run (`C:\mastertool-ai-bridge-runs\<run-id>\bootstrap.py`)
    # não tem espaço, então não foi citado e funcionou.
    #
    # A forma comprovada em runtime (testes t3 e t4 da Etapa A, via
    # PowerShell) põe as aspas em volta do VALOR:
    #
    #     --project="C:\\...\\COPIA.project"
    #
    # Para reproduzir isso exatamente, o comando é montado como STRING: no
    # Windows, quando `args` é uma string, ela é repassada verbatim ao
    # CreateProcess, sem a citação automática do list2cmdline. `shell` segue
    # False — não há shell envolvido, e nenhum dos valores vem de entrada não
    # confiável (são caminhos já validados acima).
    cmd = build_command_line(mastertool_exe, project_copy_path, bootstrap_path)

    # --- 5. inicia com UI visível e aguarda, com timeout --------------------
    proc = process_launcher(cmd)
    start = monotonic()
    timed_out = False
    while True:
        exit_code = proc.poll()
        if exit_code is not None:
            break
        elapsed = monotonic() - start
        if elapsed >= timeout_seconds:
            timed_out = True
            break
        sleep(poll_interval_seconds)
    duration_seconds = monotonic() - start

    if timed_out:
        # --- 6. timeout: NUNCA mata o processo ------------------------------
        return _result(
            run_id=run_id, final_state="needs_interaction",
            reasons=[f"timeout de {timeout_seconds}s excedido sem o processo "
                     "encerrar — provável diálogo aguardando decisão humana. "
                     "Processo NÃO foi finalizado por este orquestrador."],
            project_copy_path=str(project_copy_path),
            project_hash_before=project_hash_before,
            run_dir=str(run_dir), duration_seconds=duration_seconds,
            internal_status=read_status(run_dir))

    # --- 7. verifica processo órfão (reporta, nunca mata) --------------------
    try:
        orphans = process_lister()
    except RuntimeError:
        orphans = []
    orphan_ids = [r["pid"] for r in orphans]

    # --- 8. confere o SHA256 final -------------------------------------------
    project_hash_after = sha256_of_file(project_copy_path)
    project_hash_unchanged = (project_hash_after == project_hash_before)

    reasons: list[str] = []
    if not project_hash_unchanged:
        reasons.append(
            "cópia descartável foi MODIFICADA durante a execução "
            f"(hash antes={project_hash_before} depois={project_hash_after})")

    # --- 9. valida os artefatos ------------------------------------------------
    artifact_result = validate_output_artifacts(output_dir, operations.to_dict())
    if not artifact_result.ok:
        reasons.extend(f"validação de artefato: {e}" for e in artifact_result.errors)

    # --- 10. verifica a procedência ---------------------------------------------
    internal_status = read_status(run_dir)
    provenance_source = internal_status if isinstance(internal_status, dict) else {}
    if isinstance(artifact_result.final_declaration, dict) and "runtime" in artifact_result.final_declaration:
        provenance_source = artifact_result.final_declaration
    provenance_raw = check_provenance(provenance_source)
    provenance = ProvenanceCheckResult.from_raw(provenance_raw)
    if not provenance.inside_mastertool:
        reasons.append(
            "procedência não confirmada (IronPython 2.7 dentro do MasterTool): "
            f"{provenance.reason}")

    # --- 11. indexador Python 3 (opcional) --------------------------------------
    if run_index:
        index_result = _run_indexer(output_dir, expected_index_counts)
        # `attempted=True` significa "foi PEDIDO" (run_index=True). Um índice
        # pedido que não rodou (`ok=False`, seja por export incompleto ou por
        # exceção do indexador) IMPEDE completed — mesmo que `skipped=True`.
        # `ok=True` com `skipped=True` não deveria mais ocorrer, mas o check
        # abaixo continua correto se algum dia ocorrer (nada a reportar).
        if index_result.attempted and not index_result.ok:
            reasons.append(f"indexador: {index_result.reason}")
        if index_result.mismatches:
            reasons.extend(f"contagem do índice diverge da baseline: {m}"
                           for m in index_result.mismatches)
    else:
        index_result = IndexResult(attempted=False, skipped=True, ok=True,
                                    reason="--no-index solicitado")

    final_state = "completed" if not reasons else "failed"

    # --- 12. relatório consolidado -----------------------------------------------
    return _result(
        run_id=run_id, final_state=final_state, reasons=reasons,
        project_copy_path=str(project_copy_path),
        project_hash_before=project_hash_before,
        project_hash_after=project_hash_after,
        project_hash_unchanged=project_hash_unchanged,
        run_dir=str(run_dir), exit_code=exit_code,
        duration_seconds=duration_seconds,
        orphan_process_detected=bool(orphans),
        orphan_process_ids=orphan_ids,
        provenance=provenance,
        artifact_validation=artifact_result,
        index_result=index_result,
        internal_status=internal_status,
    )


# Arquivos obrigatórios do export textual consumido por
# `indexer.export_loader.load_export` (mesma constante de lá — duplicada
# aqui só para a busca do subdiretório certo dentro de `output/`; a
# validação de verdade continua sendo feita por `load_export`/
# `build_static_index`, nunca reimplementada aqui).
_EXPORT_REQUIRED_FILES = ("manifest.json", "flat-objects.json",
                          "text-index.json", "checksums.sha256")


def _find_export_dir(output_dir: Path) -> tuple[Path | None, list[str]]:
    """Localiza, dentro de `output_dir`, o diretório que contém o layout de
    export textual esperado por `build_static_index` (`manifest.json`,
    `flat-objects.json`, `text-index.json`, `checksums.sha256`, `objects/`).

    Devolve `(candidato_encontrado_ou_None, diagnóstico)`. `diagnóstico` é
    uma lista com UMA entrada por candidato inspecionado, nomeando
    EXATAMENTE quais arquivos de `_EXPORT_REQUIRED_FILES` faltaram naquele
    candidato — nunca a lista genérica de exigências, que não ajuda o
    operador a descobrir o que aconteceu de verdade. Lista vazia quando um
    candidato bateu (`candidato_encontrado is not None`).

    DECISÃO DE DESIGN (reportada, não improvisada silenciosamente): o
    contrato (seção 1) define `output/` como "todos os artefatos de
    aquisição" mas NÃO fixa se o export textual fica solto em `output/`
    ou num subdiretório próprio (`output/export/`, por exemplo) — isso é
    detalhe do lado IronPython, desenvolvido em paralelo. Por isso a busca
    tenta primeiro `output_dir` diretamente e, se não bater, cada
    subdiretório IMEDIATO (não recursivo — evita casar acidentalmente com
    um `objects/` aninhado de outro artefato)."""
    if not output_dir.is_dir():
        return None, [f"{output_dir}: diretório de saída inexistente"]

    candidates = [output_dir] + sorted(p for p in output_dir.iterdir() if p.is_dir())
    diagnostics: list[str] = []
    for candidate in candidates:
        missing = [f for f in _EXPORT_REQUIRED_FILES if not (candidate / f).is_file()]
        if not missing:
            return candidate, []
        diagnostics.append(f"{candidate}: faltam {', '.join(missing)}")
    return None, diagnostics


def _summarize_index_counts(index: dict) -> dict:
    """Extrai do dict devolvido por `build_static_index()` os contadores
    comparáveis com a baseline `v0.1.0` (`RELATORIO-VALIDACAO-OPERACIONAL-
    2026-07-24.md`, seção 4): `symbols.json`=60, `type-index.json`
    (`type_symbols`)=8, `resolved-references.json`=409 resolved/64
    partially_resolved/61 unresolved, `resolved-calls.json`=3 resolved/9
    unresolved, `read-write-index.json`=522 entradas totais.

    Nomes de chave usados abaixo são os REAIS devolvidos por
    `build_static_index()` (`symbols`, `type_symbols`, `resolved_calls`,
    `resolved_references`, `read_write_index`), cada item de
    `resolved_calls`/`resolved_references` trazendo `resolution_state`
    (`ResolvedCall.to_dict`/`ResolvedReference.to_dict`) — não inventados."""
    symbols = index.get("symbols") or []
    type_symbols = index.get("type_symbols") or []

    resolved_references = index.get("resolved_references") or []
    reference_states: dict[str, int] = {}
    for ref in resolved_references:
        state = ref.get("resolution_state", "unknown")
        reference_states[state] = reference_states.get(state, 0) + 1

    resolved_calls = index.get("resolved_calls") or []
    call_states: dict[str, int] = {}
    for call in resolved_calls:
        state = call.get("resolution_state", "unknown")
        call_states[state] = call_states.get(state, 0) + 1

    read_write_index = index.get("read_write_index") or {}
    read_write_entries = 0
    for key, buckets in read_write_index.items():
        if key == "_unresolved":
            read_write_entries += len(buckets)
        else:
            read_write_entries += sum(len(v) for v in buckets.values())

    return {
        "symbols": len(symbols),
        "type_symbols": len(type_symbols),
        "resolved_references": reference_states,
        "resolved_calls": call_states,
        "read_write_entries": read_write_entries,
    }


def _compare_index_counts(actual: dict, expected: dict, prefix: str = "") -> list[str]:
    """Compara `actual` (o que `_summarize_index_counts` extraiu) contra
    `expected` (o que o chamador declarou esperar). Só as chaves presentes
    em `expected` são checadas — permite comparação parcial (ex.: só
    `symbols`, sem exigir os demais contadores)."""
    mismatches: list[str] = []
    for key, expected_value in expected.items():
        path = f"{prefix}{key}"
        actual_value = actual.get(key) if isinstance(actual, dict) else None
        if isinstance(expected_value, dict):
            mismatches.extend(
                _compare_index_counts(actual_value or {}, expected_value, prefix=f"{path}."))
        elif actual_value != expected_value:
            mismatches.append(f"{path}: esperado={expected_value!r} obtido={actual_value!r}")
    return mismatches


def _run_indexer(output_dir: Path, expected_index_counts: dict | None) -> IndexResult:
    """Chama o `StaticProjectIndexer` já existente
    (`mastertool_bridge.indexer.export_loader.build_static_index`) sobre o
    export textual produzido em `output/`, grava os artefatos em
    `output/index/` e devolve os contadores para comparação opcional com
    `expected_index_counts` (nunca hardcoda os números da baseline —
    específicos de `ExemploPlanta V1.0`; o runner é genérico, mesmo motivo
    pelo qual os GUIDs da Application vêm do config).

    O índice foi PEDIDO por quem chama (`run_index=True`) — esta função só
    é chamada nesse caso; `orchestrate_run` trata `run_index=False`
    separadamente, sem chamar `_run_indexer` (`attempted=False`). Por isso,
    se nenhum subdiretório de `output/` tiver o layout de export esperado
    (`_find_export_dir` devolve `None`), este passo é `skipped=True,
    **ok=False**` — um índice pedido que não rodou IMPEDE `completed`
    (ver `orchestrate_run`, passo 11). `reason` nomeia os arquivos que
    faltaram em cada candidato inspecionado (ver `_find_export_dir`)."""
    from mastertool_bridge.indexer.export_loader import build_static_index

    export_dir, diagnostics = _find_export_dir(output_dir)
    if export_dir is None:
        reason = ("índice foi pedido (run_index=True) mas nenhum diretório sob "
                  "output/ tem o layout de export completo esperado por "
                  "build_static_index. Candidatos inspecionados: "
                  + ("; ".join(diagnostics) if diagnostics else "nenhum"))
        return IndexResult(attempted=True, skipped=True, ok=False, reason=reason)

    index_dir = output_dir / "index"
    try:
        index = build_static_index(export_dir, index_dir)
    except Exception as exc:  # noqa: BLE001 - defesa: indexador não deve derrubar o host
        return IndexResult(attempted=True, skipped=False, ok=False,
                            export_dir=str(export_dir),
                            reason=f"indexador levantou exceção: {exc}")

    counts = _summarize_index_counts(index)
    mismatches: list[str] = []
    if expected_index_counts:
        mismatches = _compare_index_counts(counts, expected_index_counts)

    return IndexResult(
        attempted=True, skipped=False, ok=True,
        index_dir=str(index_dir), export_dir=str(export_dir),
        counts=counts, mismatches=mismatches)

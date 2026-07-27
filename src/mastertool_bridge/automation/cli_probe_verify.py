"""Verificador OFFLINE e DETERMINÍSTICO do gate da Etapa A do roadmap de
automação (`docs/15-automation-launcher-roadmap.md`).

Lê os `result.json` produzidos por
`scripts/mastertool/probes/15_validate_command_line_execution.py` nos 5
testes de linha de comando do MasterTool (`--runscript`, `--runscript` +
`--scriptargs`, `--project` sozinho, combinado, e `--noUI` combinado) e
emite o veredito consolidado do gate. Este módulo NUNCA executa o
MasterTool, NUNCA abre `MT8500.exe`, e NUNCA presume nada sobre o schema do
`result.json` além do que `build_report()` do probe 15 efetivamente produz.

Motivação da checagem de procedência (`check_provenance`): uma execução de
2026-07-24 14:57 foi confundida com execução dentro do MasterTool, mas na
verdade rodou em CPython 3 fora dele (o `--runscript` "silenciosamente" não
chegou a executar dentro do ScriptEngine do MasterTool). Sem esta checagem,
um artefato assim passaria por sucesso porque `script_started` já é `True`
por construção do probe 15, mesmo fora do MasterTool. Por isso todo
resultado de teste (exceto t3, que nunca gera artefato) exige procedência
`inside_mastertool=True` antes de qualquer outra checagem.

Filosofia (herdada de `discovery/graphic_language_scan.py`): funções puras,
deterministas (mesma entrada -> mesma saída), sem qualquer `datetime.now()`
dentro da lógica de avaliação — timestamp só apareceria na borda da CLI, se
necessário (não é necessário aqui: o veredito não depende de "agora").

Fail-closed, deliberado em cada ambiguidade: na dúvida entre aprovar e
reprovar, este módulo reprova. Em particular:
  - t3 (`--project` sozinho) NUNCA recebe aprovação automática — não existe
    `result.json` para esse teste por construção (não há `--runscript`), e
    a confirmação depende inteiramente do operador (projeto correto aberto
    visualmente, ausência de diálogo de conversão/licença/biblioteca,
    integridade de hash da cópia descartável antes/depois);
  - `project_supported` só vira `"confirmed"` se o operador explicitamente
    confirmar via `expected["t3_manual_confirmed"] = True`; ausência dessa
    chave (ou `False` explícito) NUNCA vira `"confirmed"`;
  - `headless_status` só vira `"supported"` se TODOS os itens manuais de t5
    estiverem explicitamente confirmados (`True`) em
    `expected["t5_manual_confirmed"]`; qualquer item ausente ou `False`
    resulta em `"unsafe"` (nunca em aprovação silenciosa por omissão).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from mastertool_bridge.utils.json_io import read_json, write_json

TEST_IDS = ("t1", "t2", "t3", "t4", "t5")

# IDs curtos e estáveis para os itens de confirmação manual (usados como
# chaves em `expected["t3_manual_confirmed"]`/`expected["t5_manual_confirmed"]`).
T3_MANUAL_ITEMS = (
    {"id": "correct_project_opened",
     "description": "Confirmar visualmente que o projeto correto (esperado) foi aberto."},
    {"id": "no_conversion_or_license_dialog",
     "description": "Confirmar ausência de diálogo de conversão/licença/biblioteca ao abrir o projeto."},
    {"id": "disposable_copy_hash_intact",
     "description": "Confirmar integridade da cópia descartável do projeto (hash idêntico antes/depois)."},
)

T5_MANUAL_ITEMS = (
    {"id": "process_exit_code_ok",
     "description": "Confirmar código de saída do processo MT8500.exe (--noUI) após a execução."},
    {"id": "no_orphan_process",
     "description": "Confirmar ausência de processo órfão do MasterTool após --noUI."},
    {"id": "no_invisible_lock",
     "description": "Confirmar ausência de bloqueio invisível (arquivo de lock/licença) após --noUI."},
)


# =============================================================================
# Prova de procedência
# =============================================================================

def check_provenance(result: dict) -> dict:
    """Confirma que `result` foi genuinamente produzido DENTRO do MasterTool
    (IronPython 2.7 via `sys.platform == "cli"`), não em CPython 3 fora dele.

    Todas as 3 checagens abaixo devem ser verdadeiras:
        - runtime.platform == "cli"
        - runtime.runtime_family == "IronPython"
        - runtime.version_info é lista/tupla começando com [2, 7]
    """
    runtime = (result or {}).get("runtime") or {}

    platform_actual = runtime.get("platform")
    platform_ok = platform_actual == "cli"

    family_actual = runtime.get("runtime_family")
    family_ok = family_actual == "IronPython"

    version_info_actual = runtime.get("version_info")
    version_ok = (
        isinstance(version_info_actual, (list, tuple))
        and len(version_info_actual) >= 2
        and list(version_info_actual[:2]) == [2, 7]
    )

    checks = {
        "platform": {"expected": "cli", "actual": platform_actual, "ok": platform_ok},
        "runtime_family": {"expected": "IronPython", "actual": family_actual, "ok": family_ok},
        "version_info": {"expected": "[2, 7, ...]", "actual": version_info_actual, "ok": version_ok},
    }

    inside_mastertool = platform_ok and family_ok and version_ok
    reason = None
    if not inside_mastertool:
        failed = [name for name, c in checks.items() if not c["ok"]]
        reason = ("procedência não confirmada — checagem(ns) reprovada(s): "
                  + ", ".join(sorted(failed)))

    return {"inside_mastertool": inside_mastertool, "checks": checks, "reason": reason}


# =============================================================================
# Helpers de comparação de caminho (Windows: normalização + case-insensitive)
# =============================================================================

def _normalize_path(value: str) -> str:
    return os.path.normcase(os.path.normpath(value))


def _argv_contains_path(argv: Any, expected_path: str) -> bool:
    """Procura `expected_path` (normalizado, case-insensitive) como
    substring de algum token de `argv`. Substring (não igualdade exata)
    porque `--scriptargs` pode entregar um token único contendo a flag
    inteira, ex. `'--output "C:\\algum\\caminho"'` — a normalização de
    `os.path.normpath` só é aplicada ao lado esperado; o token bruto é
    comparado via `os.path.normcase` (sem `normpath`, já que o token pode
    não ser um caminho "puro")."""
    if not argv or not expected_path:
        return False
    target = os.path.normcase(os.path.normpath(expected_path))
    for token in argv:
        if not isinstance(token, str) or not token:
            continue
        if target in os.path.normcase(token):
            return True
    return False


# =============================================================================
# Avaliação por teste
# =============================================================================

def _check(name: str, expected: Any, actual: Any, ok: bool) -> dict:
    return {"name": name, "expected": expected, "actual": actual, "ok": ok}


def _expected_for(expected: dict | None, test_id: str) -> dict:
    """Resolve o `expected` efetivo de um teste, aplicando os overrides de
    `expected["per_test"][test_id]` por cima das chaves globais.

    Necessário porque cada teste grava num diretório de saída PRÓPRIO
    (`workspace/logs/cli-probe/t2`, `.../t4`, …) — disciplina anti-sobrescrita
    já usada em todos os probes. Um único `output_dir` global não conseguiria
    casar com t2 e t4 ao mesmo tempo, e t4 reprovaria sempre. Chaves globais
    seguem valendo como padrão para quem usa um diretório único."""
    expected = expected or {}
    per_test = expected.get("per_test") or {}
    override = per_test.get(test_id) or {}
    merged = dict(expected)
    merged.pop("per_test", None)
    merged.update(override)
    return merged


def _evaluate_provenance_and_script_started(result: dict) -> tuple[list[dict], dict]:
    checks = []
    script_started_actual = result.get("script_started")
    checks.append(_check("script_started", True, script_started_actual,
                         script_started_actual is True))

    provenance = check_provenance(result)
    checks.append(_check("inside_mastertool", True, provenance["inside_mastertool"],
                         provenance["inside_mastertool"]))
    for name, c in provenance["checks"].items():
        checks.append(_check("provenance." + name, c["expected"], c["actual"], c["ok"]))
    return checks, provenance


def _no_project_observation(result: dict) -> str:
    """Observação usada SOMENTE em t1/t2 (testes sem `--project`). Em t4/t5
    `projects_available` é uma CHECAGEM de aprovação, não uma observação -
    reaproveitar este texto lá produziria um relatório que se contradiz.

    ACHADO REAL do t1 (2026-07-24 16:21, MT8500 3.63): mesmo SEM `--project`,
    o ScriptEngine expôs `projects_available=True` E `primary_available=True`;
    só `project.path` ficou `None`. Ou seja, a presença de `projects.primary`
    NÃO prova que existe projeto aberto - quem prova é `project.path`. Por
    isso nenhum destes dois campos reprova t1/t2, e em t4 o peso da prova
    fica em `project.path`."""
    globals_ = result.get("globals") or {}
    project = result.get("project") or {}
    return ("globals.projects_available=%r, project.primary_available=%r, "
            "project.path=%r - sem --project, o MT8500 3.63 ainda expõe "
            "'projects'/'primary'; só 'path' distingue projeto aberto de "
            "não aberto. OBSERVAÇÃO, nunca reprovação."
            % (globals_.get("projects_available"),
               project.get("primary_available"),
               project.get("path")))


def _evaluate_t1(result: dict) -> dict:
    checks, _provenance = _evaluate_provenance_and_script_started(result)
    observations = [_no_project_observation(result)]

    status = "pass" if all(c["ok"] for c in checks) else "fail"
    return {"test_id": "t1", "status": status, "checks": checks,
            "observations": observations, "manual_items": []}


def _evaluate_t2(result: dict, expected: dict) -> dict:
    t1_eval = _evaluate_t1(result)
    checks = list(t1_eval["checks"])
    observations = list(t1_eval["observations"])

    argv = result.get("argv") or []
    expected_output_dir = expected.get("output_dir")
    if expected_output_dir:
        argv_has_output_dir = _argv_contains_path(argv, expected_output_dir)
    else:
        argv_has_output_dir = False
    checks.append(_check(
        "output_dir_in_argv", expected_output_dir, argv,
        bool(expected_output_dir) and argv_has_output_dir))

    resolution = result.get("output_dir_resolution") or []
    layer1_success = any(
        isinstance(a, dict) and a.get("layer") == 1 and a.get("success") is True
        for a in resolution)
    checks.append(_check(
        "output_dir_resolution_layer1_success", True, resolution, layer1_success))

    status = "pass" if all(c["ok"] for c in checks) else "fail"
    return {"test_id": "t2", "status": status, "checks": checks,
            "observations": observations, "manual_items": []}


def _evaluate_t3(expected: dict) -> dict:
    confirmed_map = (expected or {}).get("t3_manual_confirmed") or {}
    observations = [
        "t3 (--project sozinho, SEM --runscript) NUNCA gera result.json por "
        "construção — confirmação é 100% manual, nunca automática.",
    ]
    manual_items = [dict(item) for item in T3_MANUAL_ITEMS]
    for item in manual_items:
        item["confirmed"] = confirmed_map.get(item["id"])
    return {"test_id": "t3", "status": "manual", "checks": [],
            "observations": observations, "manual_items": manual_items}


def _evaluate_t4(result: dict, expected: dict) -> dict:
    t2_eval = _evaluate_t2(result, expected)
    checks = list(t2_eval["checks"])
    # A observação de t1/t2 ("projects_available False é esperado") é FALSA
    # aqui: t4 passa --project, então projects_available vira checagem de
    # aprovação logo abaixo. Herdá-la produziria um relatório contraditório.
    no_project_obs = _no_project_observation(result)
    observations = [o for o in t2_eval["observations"] if o != no_project_obs]

    globals_ = result.get("globals") or {}
    projects_available_actual = globals_.get("projects_available")
    checks.append(_check("globals.projects_available", True, projects_available_actual,
                         projects_available_actual is True))

    project = result.get("project") or {}
    primary_available_actual = project.get("primary_available")
    checks.append(_check("project.primary_available", True, primary_available_actual,
                         primary_available_actual is True))

    expected_project_path = expected.get("project_path")
    actual_project_path = project.get("path")
    if expected_project_path and isinstance(actual_project_path, str):
        path_ok = _normalize_path(actual_project_path) == _normalize_path(expected_project_path)
    else:
        path_ok = False
    checks.append(_check("project.path", expected_project_path, actual_project_path, path_ok))

    safety = result.get("safety") or {}
    for key in ("project_modified", "save_called", "build_called", "online_operation"):
        actual = safety.get(key)
        checks.append(_check("safety.%s" % key, False, actual, actual is False))

    status = "pass" if all(c["ok"] for c in checks) else "fail"
    return {"test_id": "t4", "status": status, "checks": checks,
            "observations": observations, "manual_items": []}


def _evaluate_t5(result: dict, expected: dict) -> dict:
    t4_eval = _evaluate_t4(result, expected)
    confirmed_map = (expected or {}).get("t5_manual_confirmed") or {}
    manual_items = [dict(item) for item in T5_MANUAL_ITEMS]
    for item in manual_items:
        item["confirmed"] = confirmed_map.get(item["id"])
    return {"test_id": "t5", "status": t4_eval["status"], "checks": t4_eval["checks"],
            "observations": t4_eval["observations"], "manual_items": manual_items}


def evaluate_test(test_id: str, result: dict | None, expected: dict) -> dict:
    """Avalia um único teste (`test_id` em `{"t1","t2","t3","t4","t5"}`)
    contra o `result` (dict do `result.json`, ou `None` se o artefato não
    existir) e o `expected` (o que o operador pediu — ver docstring do
    módulo para as chaves reconhecidas).

    Retorna sempre `{"test_id", "status", "checks", "observations",
    "manual_items"}`. `status="missing"` só ocorre para result=None em
    testes diferentes de t3 (t3 nunca produz artefato por construção, então
    result=None é o caso NORMAL para ele, não uma falha)."""
    if test_id not in TEST_IDS:
        raise ValueError("test_id desconhecido: %r" % (test_id,))

    expected = _expected_for(expected, test_id)

    if test_id == "t3":
        return _evaluate_t3(expected)

    if result is None:
        return {"test_id": test_id, "status": "missing", "checks": [],
                "observations": [], "manual_items": []}

    if test_id == "t1":
        return _evaluate_t1(result)
    if test_id == "t2":
        return _evaluate_t2(result, expected)
    if test_id == "t4":
        return _evaluate_t4(result, expected)
    return _evaluate_t5(result, expected)


# =============================================================================
# Resumo do gate
# =============================================================================

def _project_supported_status(t3_eval: dict, expected: dict) -> str:
    confirmed = (expected or {}).get("t3_manual_confirmed", {}) or {}
    # "confirmed" exige TODOS os itens manuais explicitamente True.
    if all(confirmed.get(item["id"]) is True for item in T3_MANUAL_ITEMS):
        return "confirmed"
    # "failed" só quando o operador reprovou explicitamente algum item
    # (False explícito) — ausência de resposta é "pending_manual", nunca
    # "failed" silenciosamente.
    if any(confirmed.get(item["id"]) is False for item in T3_MANUAL_ITEMS):
        return "failed"
    return "pending_manual"


def _headless_status(t5_eval: dict, expected: dict) -> str:
    if t5_eval["status"] == "missing":
        return "not_tested"
    if t5_eval["status"] != "pass":
        # "fail" (checagens automáticas reprovadas) — artefato existe mas
        # não passou.
        return "unsupported"

    confirmed = (expected or {}).get("t5_manual_confirmed", {}) or {}
    all_confirmed = all(confirmed.get(item["id"]) is True for item in T5_MANUAL_ITEMS)
    if all_confirmed:
        return "supported"
    # Artefato produzido e checagens automáticas ok, mas pelo menos um item
    # manual não foi confirmado (ausente ou explicitamente reprovado) ->
    # fail-closed: nunca "supported" por omissão.
    return "unsafe"


def _summary_markdown(gate: dict) -> str:
    lines = [
        "# Gate da Etapa A — verificação do probe 15 (linha de comando do MasterTool)",
        "",
        "## Decisão",
        "- runscript_supported: **%s**" % gate["runscript_supported"],
        "- scriptargs_supported: **%s**" % gate["scriptargs_supported"],
        "- project_supported: **%s**" % gate["project_supported"],
        "- combined_execution_supported: **%s**" % gate["combined_execution_supported"],
        "- headless_status: **%s**" % gate["headless_status"],
        "- gate_b_unblocked: **%s**" % gate["gate_b_unblocked"],
        "",
        "## Por teste",
    ]
    for test_id in TEST_IDS:
        per = gate["per_test"].get(test_id) or {}
        lines.append("### %s — status: %s" % (test_id, per.get("status")))
        for c in per.get("checks", []):
            marker = "OK" if c["ok"] else "FALHOU"
            lines.append("- [%s] %s (esperado=%r, obtido=%r)"
                         % (marker, c["name"], c["expected"], c["actual"]))
        for obs in per.get("observations", []):
            lines.append("- observação: %s" % obs)
        for item in per.get("manual_items", []):
            lines.append("- manual [%s]: %s (confirmado=%r)"
                         % (item["id"], item["description"], item.get("confirmed")))
        lines.append("")
    return "\n".join(lines)


def build_gate_report(results_by_test: dict, expected: dict) -> dict:
    """Consolida os 5 `evaluate_test(...)` no veredito do gate da Etapa A.

    `results_by_test`: dict `test_id -> result dict|None` (o `result.json`
    cru de cada teste; `None` quando ausente — sempre `None` para t3).
    `expected`: o que o operador pediu, ver docstring do módulo."""
    expected = expected or {}

    per_test = {
        test_id: evaluate_test(test_id, results_by_test.get(test_id), expected)
        for test_id in TEST_IDS
    }

    runscript_supported = per_test["t1"]["status"] == "pass"
    scriptargs_supported = per_test["t2"]["status"] == "pass"
    project_supported = _project_supported_status(per_test["t3"], expected)
    combined_execution_supported = per_test["t4"]["status"] == "pass"
    headless_status = _headless_status(per_test["t5"], expected)

    gate_b_unblocked = bool(
        runscript_supported and scriptargs_supported
        and combined_execution_supported and project_supported == "confirmed")

    gate = {
        "runscript_supported": runscript_supported,
        "scriptargs_supported": scriptargs_supported,
        "project_supported": project_supported,
        "combined_execution_supported": combined_execution_supported,
        "headless_status": headless_status,
        "gate_b_unblocked": gate_b_unblocked,
        "per_test": per_test,
    }
    gate["summary_markdown"] = _summary_markdown(gate)
    return gate


# =============================================================================
# Descoberta tolerante de result.json em --results-dir
# =============================================================================

def discover_results(results_dir: Path) -> dict:
    """Procura `result.json` sob `results_dir` (recursivamente), atribuindo
    cada arquivo encontrado ao teste (`t1`/`t2`/`t4`/`t5`) cujo identificador
    aparece (case-insensitive, substring simples) no caminho completo do
    arquivo. t3 nunca produz artefato - sempre `None`.

    Desempate INTENCIONAL quando o mesmo teste tem mais de um candidato:
    vence o que estiver num diretório chamado exatamente `collected` (o
    destino canônico que o runner de host preenche), e só depois a ordem
    alfabética do caminho.

    Isto não é detalhe de estilo. Na verificação real de 2026-07-24, o
    diretório de t2 tinha DOIS artefatos: `collected/` (a execução boa) e
    `collected-spaces-run/` (a execução anterior, guardada como evidência do
    achado de espaços). Por ordem alfabética pura, `collected-spaces-run`
    vence `collected` (o '-' precede o separador de caminho), e o gate
    reprovou t2 usando o artefato errado. Empate resolvido por acidente de
    ordenação é defeito, não determinismo."""
    results_dir = Path(results_dir)
    found: dict[str, dict | None] = {"t1": None, "t2": None, "t3": None, "t4": None, "t5": None}

    if not results_dir.is_dir():
        return found

    candidates: dict[str, list[Path]] = {"t1": [], "t2": [], "t4": [], "t5": []}
    for path in results_dir.rglob("result.json"):
        path_lower = str(path).lower()
        for test_id in ("t1", "t2", "t4", "t5"):
            if test_id in path_lower:
                candidates[test_id].append(path)
                break

    def _rank(path: Path) -> tuple:
        return (0 if path.parent.name.lower() == "collected" else 1, str(path).lower())

    for test_id, paths in candidates.items():
        if paths:
            found[test_id] = read_json(sorted(paths, key=_rank)[0])

    return found


def run_verification(results_dir: Path, expected: dict | None = None) -> dict:
    """Ponto de entrada puro (sem I/O de saída): descobre os `result.json`
    sob `results_dir` e devolve o relatório de gate consolidado."""
    results_by_test = discover_results(Path(results_dir))
    return build_gate_report(results_by_test, expected or {})


# =============================================================================
# CLI (`mastertool-bridge verify-cli-probe`)
# =============================================================================

def cmd_verify_cli_probe(args: argparse.Namespace) -> int:
    # O console do Windows costuma usar cp850/cp1252, o que transforma os
    # acentos do relatório em lixo ("verifica��o"). Reconfigurar para
    # UTF-8 com errors="replace" nunca derruba o comando: se o terminal não
    # suportar, degrada em vez de levantar UnicodeEncodeError.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

    expected: dict = {}
    if getattr(args, "expected", None):
        expected = read_json(Path(args.expected)) or {}

    gate = run_verification(Path(args.results_dir), expected)

    if getattr(args, "output", None):
        write_json(Path(args.output), gate)

    print(gate["summary_markdown"])
    return 0 if gate["gate_b_unblocked"] else 1

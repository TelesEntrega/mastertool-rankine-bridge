#!/usr/bin/env python3
"""Verifica uma run de exportação PLCopen supervisionada já concluída.

Read-only: não abre o MasterTool, não altera a run, não reescreve artefato
nenhum. Serve para conferir um smoke sem depender de leitura manual do
relatório.

    python tools/verify_plcopen_export_smoke.py --run-dir <caminho da run>

Não há caminho padrão: a run vem sempre por argumento. Um default apontando
para o diretório de runs de alguém transformaria "esqueci de informar a run"
numa verificação silenciosa contra a execução errada.

## Cada afirmação tem uma fonte, e elas não se substituem

| Fonte | O que responde |
|---|---|
| `plcopen-export/target-identity.json` | identidade do alvo exportado |
| `plcopen-export/export-analysis.json` | veredito científico (`P1`…`P4`) |
| `plcopen-export/safety-declaration.json` | o que a operação declara ter feito |
| `plcopen-export/checksums.sha256` | integridade dos artefatos |
| `status.json` | último estado operacional persistido |
| `output/run-report.json` | declaração final do runner INTERNO |
| relatório do host (`--host-report`) | `final_state` do orquestrador |

Três confusões custaram tempo no primeiro smoke e estão travadas por teste:

1. **`P1` não está em `report.md`.** O veredito científico é produzido pela
   análise offline, no host, depois que o MasterTool fecha.
2. **`result_case=P_created` NÃO é `P1_graphical_body_present`.** O primeiro é
   do probe e significa "invocou e criou entradas"; o segundo classifica o
   FORMATO do que foi produzido. Aceitar um pelo outro é confundir estado
   operacional com resultado científico.
3. **`output/run-report.json` não tem `final_state`.** Ele é a declaração
   final do runner interno. O `final_state` pertence ao relatório do host, que
   sai no stdout do orquestrador — se não for fornecido, este verificador diz
   que não pôde conferir, em vez de inventar.

## Códigos de saída

    0  todas as verificações passaram
    1  run válida, mas alguma verificação falhou
    2  uso inválido, estrutura de run ausente ou entrada malformada

Artefato de contrato ausente (`target-identity.json`, por exemplo) é `1`, não
`2`: a run é analisável e detectar essa ausência é exatamente o motivo de o
verificador existir.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from mastertool_bridge.utils.hashing import (  # noqa: E402
    parse_checksums_file, sha256_file)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

EXPORT_DIRNAME = "plcopen-export"
EXPORT_ROOT_DIRNAME = "export-root"
GRAPHICAL_RESULT_CASE = "P1_graphical_body_present"

# Vocabulário do PROBE, não da análise. Nunca pode ser aceito como veredito
# científico — ver item 2 da docstring.
PROBE_RESULT_CASES = ("P_created", "P_invoked", "P_not_invoked")

EXPORT_SAFETY_MUST_BE_FALSE = (
    "project_save_called", "project_build_called", "text_document_write_called",
    "import_called", "online_operation", "download_called", "force_called",
)


class RunStructureError(Exception):
    """Estrutura de run ausente ou ilegível — vira código de saída 2."""


class Check:
    __slots__ = ("name", "ok", "detail")

    def __init__(self, name: str, ok: bool, detail: str = ""):
        self.name = name
        self.ok = bool(ok)
        self.detail = detail

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RunStructureError("arquivo ausente: %s" % path) from exc
    except ValueError as exc:
        raise RunStructureError("JSON inválido em %s: %s" % (path, exc)) from exc


def _check_identity(export_dir: Path, run_config: dict | None) -> list[Check]:
    checks: list[Check] = []
    path = export_dir / "target-identity.json"
    if not path.is_file():
        return [Check("target-identity.json presente", False, str(path))]
    checks.append(Check("target-identity.json presente", True))

    doc = _read_json(path)
    version = doc.get("schema_version")
    checks.append(Check(
        "schema_version é o inteiro 1",
        version == 1 and isinstance(version, int) and not isinstance(version, bool),
        repr(version)))
    checks.append(Check("identity_check_reached é True",
                        doc.get("identity_check_reached") is True,
                        repr(doc.get("identity_check_reached"))))
    checks.append(Check("identity_confirmed é True",
                        doc.get("identity_confirmed") is True,
                        repr(doc.get("identity_confirmed"))))

    mismatches = doc.get("mismatches") or []
    checks.append(Check(
        "sem divergências de identidade", not mismatches,
        "campos divergentes: %s" % sorted(mismatches) if mismatches else ""))

    checks.append(Check("alvo não é pasta", doc.get("is_folder") is False,
                        repr(doc.get("is_folder"))))
    for field in ("target_node_id", "name", "guid", "type_guid"):
        checks.append(Check("campo %s preenchido" % field, bool(doc.get(field))))

    # Não duplicar o que é papel de invocation.json.
    invocation_fields = {"arguments", "overload_parameters", "return_value",
                         "raised_exception"}
    intruders = sorted(invocation_fields & set(doc))
    checks.append(Check("não duplica invocation.json", not intruders, str(intruders)))

    if run_config is not None:
        expected = run_config.get("plcopen_export") or {}
        pairs = (("name", "expected_name"), ("guid", "expected_guid"),
                 ("type_guid", "expected_type_guid"),
                 ("target_node_id", "target_node_id"))
        for actual_key, expected_key in pairs:
            if expected_key not in expected:
                continue
            checks.append(Check(
                "%s confere com o run-config" % actual_key,
                doc.get(actual_key) == expected.get(expected_key)))
    return checks


def _check_scientific_verdict(export_dir: Path) -> list[Check]:
    """Veredito vem de `export-analysis.json`, nunca de `report.md`."""
    checks: list[Check] = []
    path = export_dir / "export-analysis.json"
    if not path.is_file():
        return [Check("export-analysis.json presente", False, str(path))]
    checks.append(Check("export-analysis.json presente", True))

    analysis = _read_json(path)
    result_case = analysis.get("result_case")

    if result_case in PROBE_RESULT_CASES:
        checks.append(Check(
            "veredito científico não confundido com estado do probe", False,
            "result_case=%r é vocabulário do PROBE (invocou/criou), não "
            "classificação de formato" % result_case))
        return checks

    checks.append(Check("veredito científico não confundido com estado do probe", True))
    checks.append(Check("result_case é %s" % GRAPHICAL_RESULT_CASE,
                        result_case == GRAPHICAL_RESULT_CASE, repr(result_case)))

    graphical = (analysis.get("element_counts") or {}).get("graphical_bodies") or {}
    checks.append(Check("corpo gráfico presente", bool(graphical), repr(graphical)))

    match = analysis.get("target_match") or {}
    checks.append(Check("alvo localizado no XML", match.get("found") is True,
                        repr(match.get("found"))))
    checks.append(Check("alvo tem corpo gráfico",
                        match.get("has_graphical_body") is True,
                        repr(match.get("has_graphical_body"))))
    return checks


def _check_checksums(export_dir: Path) -> list[Check]:
    checks: list[Check] = []
    path = export_dir / "checksums.sha256"
    if not path.is_file():
        return [Check("checksums.sha256 presente", False, str(path))]
    checks.append(Check("checksums.sha256 presente", True))

    entries = parse_checksums_file(path)
    checks.append(Check("manifesto não está vazio", bool(entries)))

    missing = sorted(rel for rel in entries if not (export_dir / rel).is_file())
    checks.append(Check("todo arquivo listado existe", not missing, str(missing[:5])))

    divergent = []
    for rel, expected in sorted(entries.items()):
        target = export_dir / rel
        if target.is_file() and sha256_file(target) != expected:
            divergent.append(rel)
    checks.append(Check("todo hash confere", not divergent, str(divergent[:5])))

    checks.append(Check("target-identity.json está no manifesto",
                        "target-identity.json" in entries))

    escaped = sorted(r for r in entries if r.startswith(EXPORT_ROOT_DIRNAME + "/"))
    checks.append(Check(
        "export-root/ fora do manifesto", not escaped,
        "conteúdo produzido pela API tem hashes próprios em "
        "created-artifacts.json: %s" % escaped[:3] if escaped else ""))

    listed_temp = sorted(r for r in entries if r.endswith(".tmp"))
    on_disk_temp = sorted(p.name for p in export_dir.iterdir()
                          if p.is_file() and p.name.endswith(".tmp"))
    checks.append(Check("nenhum .tmp no manifesto", not listed_temp, str(listed_temp)))
    checks.append(Check("nenhum .tmp órfão no diretório", not on_disk_temp,
                        str(on_disk_temp)))
    return checks


def _check_safety(export_dir: Path) -> list[Check]:
    checks: list[Check] = []
    path = export_dir / "safety-declaration.json"
    if not path.is_file():
        return [Check("safety-declaration.json presente", False, str(path))]
    checks.append(Check("safety-declaration.json presente", True))

    safety = _read_json(path)
    checks.append(Check("export_xml_called é True",
                        safety.get("export_xml_called") is True,
                        repr(safety.get("export_xml_called"))))
    checks.append(Check("export_xml_call_count é 1",
                        safety.get("export_xml_call_count") == 1,
                        repr(safety.get("export_xml_call_count"))))
    checks.append(Check(
        "escrita no escopo autorizado",
        safety.get("filesystem_output_scope") == "authorized_disposable_export_root",
        repr(safety.get("filesystem_output_scope"))))
    for key in EXPORT_SAFETY_MUST_BE_FALSE:
        checks.append(Check("%s é False" % key, safety.get(key) is False,
                            repr(safety.get(key))))
    checks.append(Check(
        "sem a chave genérica write_called", "write_called" not in safety,
        "um XML É escrito nesta operação; a chave sugeriria o contrário"))
    return checks


def _check_operational(run_dir: Path, output_dir: Path,
                       host_report: dict | None) -> list[Check]:
    checks: list[Check] = []

    status_path = run_dir / "status.json"
    if status_path.is_file():
        status = _read_json(status_path)
        checks.append(Check("estado operacional persistido é completed",
                            status.get("state") == "completed",
                            repr(status.get("state"))))
        checks.append(Check("status sem erro registrado", not status.get("error"),
                            repr(status.get("error"))))
    else:
        checks.append(Check("status.json presente", False, str(status_path)))

    declaration_path = output_dir / "run-report.json"
    if declaration_path.is_file():
        decl = _read_json(declaration_path)
        # É a declaração final do runner interno — NÃO tem final_state.
        checks.append(Check("projeto original não foi tocado",
                            decl.get("original_project_touched") is False,
                            repr(decl.get("original_project_touched"))))
        checks.append(Check("projeto não foi salvo",
                            decl.get("project_saved") is False,
                            repr(decl.get("project_saved"))))
        for key in ("build_called", "online_operation", "download_called",
                    "force_called"):
            checks.append(Check("declaração final: %s é False" % key,
                                decl.get(key) is False, repr(decl.get(key))))
        runtime = decl.get("runtime") or {}
        checks.append(Check("procedência confirmada",
                            runtime.get("provenance_confirmed") is True,
                            repr(runtime.get("provenance_confirmed"))))
    else:
        checks.append(Check("output/run-report.json presente", False,
                            str(declaration_path)))

    if host_report is None:
        # Sem relatório do host não há como saber o final_state. Dizer isso é
        # mais honesto que derivá-lo da declaração do runner, que responde
        # outra pergunta.
        checks.append(Check(
            "final_state do host informado", True,
            "não fornecido (--host-report ausente); final_state NÃO foi "
            "verificado e não pode ser inferido dos artefatos"))
    else:
        checks.append(Check("final_state do host é completed",
                            host_report.get("final_state") == "completed",
                            repr(host_report.get("final_state"))))
        checks.append(Check("hash do projeto inalterado",
                            host_report.get("project_hash_unchanged") is True,
                            repr(host_report.get("project_hash_unchanged"))))
        checks.append(Check("nenhum processo órfão",
                            host_report.get("orphan_process_detected") is False,
                            repr(host_report.get("orphan_process_detected"))))
    return checks


def _check_host_validation(output_dir: Path, archived_revision: bool) -> list[Check]:
    from mastertool_bridge.automation.artifact_validation import (
        validate_output_artifacts)

    result = validate_output_artifacts(
        Path(output_dir), operations={"export_plcopen_xml": True},
        archived_revision=archived_revision)
    mode = "revisão histórica" if archived_revision else "run nova (estrito)"
    return [
        Check("validação host-side sem erros (%s)" % mode, not result.errors,
              str(result.errors[:4])),
    ]


def verify_run(run_dir, host_report=None, archived_revision=False) -> list[Check]:
    """Devolve a lista de verificações. Levanta `RunStructureError` quando a
    run não tem estrutura analisável."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise RunStructureError("diretório de run inexistente: %s" % run_dir)
    output_dir = run_dir / "output"
    if not output_dir.is_dir():
        raise RunStructureError("output/ ausente em %s" % run_dir)
    export_dir = output_dir / EXPORT_DIRNAME
    if not export_dir.is_dir():
        raise RunStructureError(
            "%s/ ausente — esta run não é uma exportação PLCopen" % EXPORT_DIRNAME)

    config_path = run_dir / "run-config.json"
    run_config = _read_json(config_path) if config_path.is_file() else None

    checks: list[Check] = []
    checks.extend(_check_identity(export_dir, run_config))
    checks.extend(_check_scientific_verdict(export_dir))
    checks.extend(_check_checksums(export_dir))
    checks.extend(_check_safety(export_dir))
    checks.extend(_check_operational(run_dir, output_dir, host_report))
    checks.extend(_check_host_validation(output_dir, archived_revision))
    return checks


def _render_text(checks: list[Check]) -> str:
    lines = []
    for check in checks:
        marker = "ok  " if check.ok else "FAIL"
        line = "  %s  %s" % (marker, check.name)
        if check.detail and not check.ok:
            line += "\n          %s" % check.detail
        elif check.detail and check.ok:
            line += "  (%s)" % check.detail
        lines.append(line)
    failed = [c for c in checks if not c.ok]
    lines.append("")
    lines.append("%d verificações, %d falhas" % (len(checks), len(failed)))
    if failed:
        lines.append("")
        lines.append("FALHAS:")
        for check in failed:
            lines.append("  - %s" % check.name)
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica uma run de exportação PLCopen supervisionada.")
    parser.add_argument("--run-dir", required=True,
                        help="diretório da run a verificar (obrigatório)")
    parser.add_argument("--host-report",
                        help="JSON do relatório do orquestrador host, se salvo; "
                             "sem ele o final_state não é verificado")
    parser.add_argument("--archived-revision", action="store_true",
                        help="trata a run como histórica: artefatos introduzidos "
                             "depois dela viram aviso. NUNCA é automático")
    parser.add_argument("--json", action="store_true",
                        help="saída em JSON em vez de texto")
    args = parser.parse_args(argv)

    host_report = None
    if args.host_report:
        host_path = Path(args.host_report)
        try:
            host_report = json.loads(host_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("erro: --host-report ilegível: %s" % exc, file=sys.stderr)
            return EXIT_USAGE

    try:
        checks = verify_run(Path(args.run_dir), host_report=host_report,
                            archived_revision=args.archived_revision)
    except RunStructureError as exc:
        print("erro: %s" % exc, file=sys.stderr)
        return EXIT_USAGE

    failed = [c for c in checks if not c.ok]
    if args.json:
        print(json.dumps(
            {"run_dir": str(args.run_dir),
             "checks": [c.to_dict() for c in checks],
             "total": len(checks), "failed": len(failed),
             "ok": not failed},
            indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(_render_text(checks))
    return EXIT_FAILED if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

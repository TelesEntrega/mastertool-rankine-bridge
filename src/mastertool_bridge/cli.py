"""CLI externa `mastertool-bridge` (argparse — sem dependências extras).

Todos os comandos operam sobre exports em disco; nenhum toca o MasterTool
ou o CLP.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mastertool_bridge import __version__
from mastertool_bridge.exceptions import BridgeError, ValidationError
from mastertool_bridge.logging_config import setup_logging
from mastertool_bridge.utils.json_io import write_json


def _print_json(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def cmd_validate_export(args) -> int:
    from mastertool_bridge.export.validator import validate_export
    result = validate_export(Path(args.export_dir),
                             check_checksums=not args.skip_checksums)
    print(result.summary())
    for error in result.errors:
        print(f"  ERRO: {error}")
    for warning in result.warnings:
        print(f"  AVISO: {warning}")
    return 0 if result.ok else 1


def cmd_inspect(args) -> int:
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    stats = {t: len(objs) for t, objs in sorted(project.objects_by_type().items())}
    _print_json({
        "project": project.name,
        "export_dir": str(project.export_dir),
        "read_only": project.is_read_only,
        "manifest_statistics": project.manifest.get("statistics", {}),
        "objects_loaded": len(project.objects),
        "objects_by_type": stats,
    })
    return 0


def cmd_index(args) -> int:
    from mastertool_bridge.export.indexer import build_index
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    index = build_index(project)
    output = Path(args.output) if args.output else (
        Path(args.export_dir) / "reports" / "index.json")
    write_json(output, index)
    print(f"Índice gravado em {output} "
          f"({len(index['objects'])} objetos, {len(index['variables'])} variáveis).")
    return 0


def cmd_analyze(args) -> int:
    from mastertool_bridge.analysis.report_generator import safety_report_markdown
    from mastertool_bridge.analysis.safety_checks import check_project
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    findings = check_project(project)
    report = safety_report_markdown(project, findings)
    output = Path(args.output) if args.output else (
        Path(args.export_dir) / "reports" / "safety-report.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8", newline="\n")
    print(f"{len(findings)} alerta(s) heurístico(s). Relatório: {output}")
    return 0


def cmd_document(args) -> int:
    from mastertool_bridge.docs.dependency_documenter import document_dependencies
    from mastertool_bridge.docs.project_documenter import document_project
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    out_dir = Path(args.output) if args.output else (
        Path(args.export_dir) / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "project-documentation.md").write_text(
        document_project(project), encoding="utf-8", newline="\n")
    (out_dir / "dependencies.md").write_text(
        document_dependencies(project), encoding="utf-8", newline="\n")
    print(f"Documentação gerada em {out_dir}")
    return 0


def cmd_compare(args) -> int:
    from mastertool_bridge.diff.project_diff import compare_projects
    from mastertool_bridge.export.loader import load_export
    old = load_export(Path(args.export_a))
    new = load_export(Path(args.export_b))
    result = compare_projects(old, new)
    if args.output:
        write_json(Path(args.output), result)
    print(result["summary"])
    for item in result["modified"]:
        print(f"  modificado: {item['object']}")
    for name in result["added"]:
        print(f"  adicionado: {name}")
    for name in result["removed"]:
        print(f"  removido:   {name}")
    return 0


def _find_symbol_refs(args, mode: str) -> int:
    from mastertool_bridge.analysis.reference_finder import (
        filter_reads, filter_writes, find_references)
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    references = find_references(project, args.symbol,
                                 include_declarations=(mode == "all"))
    if mode == "writes":
        references = filter_writes(references)
    elif mode == "reads":
        references = filter_reads(references)
    _print_json({
        "schema_version": "1.0",
        "symbol": args.symbol,
        "heuristic": True,
        "note": "Classificação heurística — revisar manualmente.",
        "references": [r.to_dict() for r in references],
    })
    return 0


def cmd_find_symbol(args) -> int:
    return _find_symbol_refs(args, "all")


def cmd_find_writes(args) -> int:
    return _find_symbol_refs(args, "writes")


def cmd_find_reads(args) -> int:
    return _find_symbol_refs(args, "reads")


def cmd_build_agent_context(args) -> int:
    from mastertool_bridge.docs.project_documenter import document_project
    from mastertool_bridge.export.indexer import build_index
    from mastertool_bridge.export.loader import load_export
    project = load_export(Path(args.export_dir))
    out_dir = Path(args.output) if args.output else (
        Path(args.export_dir) / "reports" / "agent-context")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "index.json", build_index(project))
    (out_dir / "project-overview.md").write_text(
        document_project(project), encoding="utf-8", newline="\n")
    (out_dir / "SAFETY.md").write_text(
        "# Contexto para agentes de IA\n\n"
        "Este material é SOMENTE LEITURA. Regras completas em AGENTS.md do "
        "repositório. Não invente APIs do MasterTool; não proponha operações "
        "online; toda alteração vira change set com aprovação humana.\n",
        encoding="utf-8", newline="\n")
    print(f"Contexto para agentes gerado em {out_dir}")
    return 0


def cmd_validate_change_set(args) -> int:
    from mastertool_bridge.changes.change_set import load_change_set
    from mastertool_bridge.changes.validator import validate_change_set_policy
    try:
        change_set = load_change_set(Path(args.change_set_file))
    except ValidationError as exc:
        print(f"[FALHOU] {exc}")
        for issue in exc.issues:
            print(f"  ERRO (schema): {issue}")
        return 1
    result = validate_change_set_policy(change_set)
    print(result.summary())
    print(f"  risco mais alto: {change_set.highest_risk}")
    for error in result.errors:
        print(f"  ERRO (política): {error}")
    for warning in result.warnings:
        print(f"  AVISO: {warning}")
    return 0 if result.ok else 1


def cmd_verify_cli_probe(args) -> int:
    from mastertool_bridge.automation.cli_probe_verify import cmd_verify_cli_probe as _run
    return _run(args)


def cmd_supervised_snapshot(args) -> int:
    from pathlib import Path as _Path

    from mastertool_bridge.automation.config_models import RunOperations
    from mastertool_bridge.automation.supervised_run import orchestrate_run
    from mastertool_bridge.utils.json_io import write_json

    # --probe-ladder-surface exige os 4 valores do alvo. A incoerência JÁ é
    # rejeitada mais adiante, na construção do RunConfig (ConfigValidationError),
    # e isso acontece antes de qualquer lançamento do MasterTool — a propriedade
    # fail-closed não depende desta checagem. Ela existe para o operador receber
    # uma mensagem de CLI clara em vez de um traceback, e para falhar no ponto
    # mais barato possível.
    if args.probe_ladder_surface:
        faltando = [
            flag for flag, valor in (
                ("--ladder-target-node-id", args.ladder_target_node_id),
                ("--ladder-expected-name", args.ladder_expected_name),
                ("--ladder-expected-guid", args.ladder_expected_guid),
                ("--ladder-expected-type-guid", args.ladder_expected_type_guid),
            ) if not (valor or "").strip()
        ]
        if faltando:
            print("erro: --probe-ladder-surface exige a identificação completa do "
                  "alvo. Faltando: " + ", ".join(faltando))
            print("Os 25 candidatos da Fase L0 compartilham o mesmo type_guid, "
                  "então os quatro campos são necessários juntos "
                  "(ver docs/16-supervised-runner-contract.md, seção 3.1).")
            return 2

    repo_root = _Path(args.repo_root) if args.repo_root else _Path(__file__).resolve().parents[2]
    mastertool_scripts_dir = (
        _Path(args.mastertool_scripts_dir) if args.mastertool_scripts_dir
        else repo_root / "scripts" / "mastertool")

    operations = RunOperations(
        scan_project_tree=not args.no_scan,
        export_text=not args.no_export_text,
        probe_ladder_surface=args.probe_ladder_surface,
    )

    ladder_probe = None
    if args.probe_ladder_surface:
        ladder_probe = {
            "target_node_id": args.ladder_target_node_id,
            "expected_name": args.ladder_expected_name,
            "expected_guid": args.ladder_expected_guid,
            "expected_type_guid": args.ladder_expected_type_guid,
        }

    result = orchestrate_run(
        project_copy=args.project_copy,
        original_project=args.original_project,
        runs_root=args.runs_root,
        mastertool_exe=args.mastertool_exe,
        repo_root=repo_root,
        mastertool_scripts_dir=mastertool_scripts_dir,
        expected_application_name=args.expected_application_name,
        expected_application_guid=args.expected_application_guid,
        expected_application_type_guid=args.expected_application_type_guid,
        timeout_seconds=args.timeout,
        run_index=not args.no_index,
        operations=operations,
        ladder_probe=ladder_probe,
    )

    report = result.to_dict()
    if args.output:
        write_json(Path(args.output), report)
    _print_json(report)
    return 0 if result.final_state == "completed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mastertool-bridge",
        description=("Camada externa do mastertool-ai-bridge (somente leitura: "
                     "lê exports; nunca toca o MasterTool nem o CLP)."))
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-export", help="Valida manifesto, schemas e checksums")
    p.add_argument("export_dir")
    p.add_argument("--skip-checksums", action="store_true")
    p.set_defaults(func=cmd_validate_export)

    p = sub.add_parser("inspect", help="Resumo de um export")
    p.add_argument("export_dir")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("index", help="Gera índice de objetos e variáveis")
    p.add_argument("export_dir")
    p.add_argument("--output")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("analyze", help="Verificações de segurança (heurísticas)")
    p.add_argument("export_dir")
    p.add_argument("--output")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("document", help="Gera documentação Markdown do export")
    p.add_argument("export_dir")
    p.add_argument("--output")
    p.set_defaults(func=cmd_document)

    p = sub.add_parser("compare", help="Compara dois exports")
    p.add_argument("export_a")
    p.add_argument("export_b")
    p.add_argument("--output")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("find-symbol", help="Todas as referências a um símbolo")
    p.add_argument("export_dir")
    p.add_argument("symbol")
    p.set_defaults(func=cmd_find_symbol)

    p = sub.add_parser("find-writes", help="Escritas (heurísticas) de uma variável")
    p.add_argument("export_dir")
    p.add_argument("symbol")
    p.set_defaults(func=cmd_find_writes)

    p = sub.add_parser("find-reads", help="Leituras (heurísticas) de uma variável")
    p.add_argument("export_dir")
    p.add_argument("symbol")
    p.set_defaults(func=cmd_find_reads)

    p = sub.add_parser("build-agent-context",
                       help="Pacote de contexto (índice + docs) para agentes de IA")
    p.add_argument("export_dir")
    p.add_argument("--output")
    p.set_defaults(func=cmd_build_agent_context)

    p = sub.add_parser("validate-change-set",
                       help="Valida change set contra schema e política de segurança")
    p.add_argument("change_set_file")
    p.set_defaults(func=cmd_validate_change_set)

    p = sub.add_parser("verify-cli-probe",
                       help=("Verifica o gate da Etapa A (roadmap de automação) a partir dos "
                             "result.json do probe 15 (--runscript/--scriptargs/--project/"
                             "--noUI), 100% offline"))
    p.add_argument("--results-dir", required=True,
                   help="Diretório contendo os result.json (ou subdiretórios) dos testes t1/t2/t4/t5")
    p.add_argument("--output", help="Grava o relatório de gate completo neste arquivo JSON")
    p.add_argument("--expected", help="Arquivo JSON com o que o operador pediu/confirmou "
                                      "(output_dir, project_path, t3_manual_confirmed, "
                                      "t5_manual_confirmed)")
    p.set_defaults(func=cmd_verify_cli_probe)

    p = sub.add_parser(
        "supervised-snapshot",
        help=("Etapa B: orquestra, do lado HOST, uma execução supervisionada do "
             "MT8500 sobre uma cópia descartável do projeto (--project + "
             "--runscript=bootstrap.py, UI visível, sem --scriptargs/--noUI). "
             "Ver docs/16-supervised-runner-contract.md"))
    p.add_argument("--project-copy", required=True,
                   help="Cópia DESCARTÁVEL do .project. NUNCA o projeto original.")
    p.add_argument("--original-project", required=True,
                   help="Projeto original, só para a checagem de 'você não apontou para o original'.")
    p.add_argument("--runs-root", required=True,
                   help="Diretório raiz onde o workspace de execução (<runs-root>/<run-id>/) é criado.")
    p.add_argument("--timeout", type=float, default=900.0,
                   help="Timeout em segundos aguardando o MasterTool encerrar (padrão: 900).")
    p.add_argument("--no-index", action="store_true",
                   help="Não roda o indexador Python 3 sobre o export produzido.")
    p.add_argument("--mastertool-exe",
                   default=r"C:\Program Files (x86)\Altus\MT8500 3.63\MT8500\Common\MT8500.exe",
                   help="Caminho do MT8500.exe.")
    p.add_argument("--repo-root",
                   help="Raiz do repositório (padrão: derivada deste arquivo).")
    p.add_argument("--mastertool-scripts-dir",
                   help="Diretório scripts/mastertool (padrão: <repo-root>/scripts/mastertool).")
    p.add_argument("--expected-application-name", required=True,
                   help="Nome esperado da Application ativa (identidade, contrato seção 2).")
    p.add_argument("--expected-application-guid", required=True,
                   help="GUID esperado da Application ativa (identidade, contrato seção 2).")
    p.add_argument("--expected-application-type-guid", required=True,
                   help="GUID de tipo esperado da Application ativa (identidade, contrato seção 2).")
    p.add_argument("--no-scan", action="store_true",
                   help="Desliga operations.scan_project_tree (padrão: ligado).")
    p.add_argument("--no-export-text", action="store_true",
                   help="Desliga operations.export_text (padrão: ligado). Se ligado junto com "
                        "--run-index (padrão), a execução é reprovada por configuração "
                        "incoerente — passe também --no-index.")
    p.add_argument("--probe-ladder-surface", action="store_true",
                   help=("Liga operations.probe_ladder_surface (Fase L1 — sondagem de "
                         "superfície de API sobre um único objeto POU). Exige os quatro "
                         "--ladder-* abaixo. Ver docs/16-supervised-runner-contract.md seção 3.1."))
    p.add_argument("--ladder-target-node-id",
                   help="ladder_probe.target_node_id — obrigatório com --probe-ladder-surface.")
    p.add_argument("--ladder-expected-name",
                   help="ladder_probe.expected_name — obrigatório com --probe-ladder-surface.")
    p.add_argument("--ladder-expected-guid",
                   help="ladder_probe.expected_guid — obrigatório com --probe-ladder-surface.")
    p.add_argument("--ladder-expected-type-guid",
                   help="ladder_probe.expected_type_guid — obrigatório com --probe-ladder-surface.")
    p.add_argument("--output", help="Grava o relatório consolidado neste arquivo JSON.")
    p.set_defaults(func=cmd_supervised_snapshot, _parser=p)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "command", None) == "supervised-snapshot" and args.probe_ladder_surface:
        missing = [flag for flag, value in (
            ("--ladder-target-node-id", args.ladder_target_node_id),
            ("--ladder-expected-name", args.ladder_expected_name),
            ("--ladder-expected-guid", args.ladder_expected_guid),
            ("--ladder-expected-type-guid", args.ladder_expected_type_guid),
        ) if not value]
        if missing:
            error_parser = getattr(args, "_parser", parser)
            error_parser.error(
                "--probe-ladder-surface exige também: " + ", ".join(missing))

    setup_logging(args.log_level)
    try:
        return args.func(args)
    except BridgeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

import json

from mastertool_bridge.cli import main


def test_cli_analyze_generates_report(sample_export):
    assert main(["analyze", str(sample_export)]) == 0
    report = (sample_export / "reports" / "safety-report.md").read_text(
        encoding="utf-8")
    assert "HEURÍSTICOS" in report
    assert "direct_output_write" in report


def test_cli_find_writes(sample_project_dir, capsys):
    assert main(["find-writes", str(sample_project_dir), "xMotorLigado"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["heuristic"] is True
    usages = {r["usage"] for r in output["references"]}
    assert "confirmed_write" in usages


def test_cli_find_reads(sample_project_dir, capsys):
    assert main(["find-reads", str(sample_project_dir), "xLigaMotor"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["references"], "xLigaMotor deveria ter leitura em MainPrg"


def test_cli_document(sample_export):
    assert main(["document", str(sample_export)]) == 0
    doc = (sample_export / "reports" / "project-documentation.md").read_text(
        encoding="utf-8")
    assert "ControleMotor" in doc
    deps = (sample_export / "reports" / "dependencies.md").read_text(
        encoding="utf-8")
    assert "mermaid" in deps


def test_cli_compare_detects_change(sample_export, tmp_path, capsys):
    import shutil
    export_b = tmp_path / "export-b"
    shutil.copytree(sample_export, export_b)
    impl = export_b / "objects" / "programs" / "MainPrg" / "implementation.st"
    impl.write_text(impl.read_text(encoding="utf-8")
                    .replace("rVelocidade + 1.0", "rVelocidade + 2.0"),
                    encoding="utf-8")
    assert main(["compare", str(sample_export), str(export_b)]) == 0
    out = capsys.readouterr().out
    assert "1 modificado(s)" in out
    assert "MainPrg" in out


def test_cli_build_agent_context(sample_export):
    assert main(["build-agent-context", str(sample_export)]) == 0
    context_dir = sample_export / "reports" / "agent-context"
    assert (context_dir / "index.json").is_file()
    assert (context_dir / "SAFETY.md").is_file()

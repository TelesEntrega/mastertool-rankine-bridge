"""Testes do empacotamento de uma execução real em Evidence Bundle (R2)."""

import json

import pytest

from mastertool_bridge.evidence import bundle as eb
from mastertool_bridge.evidence.from_run import RUN_ARTIFACT_MAP, package_run


def _run_completa(tmp_path, nome="run-001", com_build=True):
    artefatos = tmp_path / nome / "artefatos"
    (artefatos / "execucao").mkdir(parents=True)
    (artefatos / "verificacao").mkdir(parents=True)
    if com_build:
        (artefatos / "build").mkdir(parents=True)

    (artefatos / "authoring-plan.json").write_text(
        json.dumps({"steps": []}), encoding="utf-8")
    (artefatos / "execucao" / "execution-completion.json").write_text(
        json.dumps({"status": "plan_executed", "plan_sha256": "p" * 64,
                    "output_sha256": "o" * 64}), encoding="utf-8")
    (artefatos / "execucao" / "execution-manifest.json").write_text(
        json.dumps({"journal": [{"passo": 1}, {"passo": 2}]}), encoding="utf-8")
    (artefatos / "verificacao" / "factory-verify-flat-nodes.json").write_text(
        json.dumps({"nodes": [{"name": "GVL_A"}]}), encoding="utf-8")
    if com_build:
        (artefatos / "build" / "build-completion.json").write_text(
            json.dumps({"status": "build_verified"}), encoding="utf-8")
        (artefatos / "build" / "build-messages.json").write_text(
            json.dumps({"messages": []}), encoding="utf-8")
    return tmp_path / nome


def test_run_completa_gera_pacote_completo(tmp_path):
    run = _run_completa(tmp_path)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    resultado = package_run(run, tmp_path / "bundle", "run-001",
                            spec_path=spec, source_project_sha256="s" * 64,
                            unexpected_changes={"verdict": "only_authorized_changed"})
    assert resultado.ok, resultado.problems
    assert resultado.status == eb.STATUS_SEALED_COMPLETE
    assert resultado.missing == []

    verificacao = eb.verify_bundle(resultado.bundle_root)
    assert verificacao.intact is True


def test_journal_vira_JSONL_uma_entrada_por_linha(tmp_path):
    run = _run_completa(tmp_path)
    package_run(run, tmp_path / "b", "run-001", source_project_sha256="s" * 64)
    linhas = (tmp_path / "b" / "execution" / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(linhas) == 2
    assert json.loads(linhas[0])["passo"] == 1


def test_run_sem_build_sela_INCOMPLETA_e_nomeia_o_que_falta(tmp_path):
    """A execução que deu errado é a que mais precisa ficar registrada."""
    run = _run_completa(tmp_path, com_build=False)
    resultado = package_run(run, tmp_path / "b", "run-001",
                            source_project_sha256="s" * 64)
    assert resultado.status == eb.STATUS_SEALED_INCOMPLETE
    assert "verification/build_report.json" in resultado.missing
    # E o pacote existe e é verificável mesmo assim.
    assert eb.verify_bundle(resultado.bundle_root).intact is True


def test_run_sem_artefatos_recusa(tmp_path):
    (tmp_path / "vazia").mkdir()
    resultado = package_run(tmp_path / "vazia", tmp_path / "b", "run-001")
    assert not resultado.ok
    assert any("sem diretório" in p for p in resultado.problems)


def test_conclusao_ilegivel_e_problema_e_nao_pacote_silencioso(tmp_path):
    run = _run_completa(tmp_path)
    (run / "artefatos" / "execucao" / "execution-completion.json").write_text(
        "{ nao e json", encoding="utf-8")
    resultado = package_run(run, tmp_path / "b", "run-001",
                            source_project_sha256="s" * 64)
    assert not resultado.ok
    assert any("sem ele não há hash" in p for p in resultado.problems)


def test_o_mapa_de_artefatos_e_literal():
    """Empacotar tudo que sobrou faria o hash do conjunto mudar por causa de
    arquivo temporário."""
    secoes = {secao for secao, _nome, _rel in RUN_ARTIFACT_MAP}
    assert secoes <= set(eb.SECTIONS)
    for secao, nome, _rel in RUN_ARTIFACT_MAP:
        assert nome in eb.allowed_names(secao), (secao, nome)


def test_arquivo_extra_no_diretorio_da_run_nao_entra(tmp_path):
    run = _run_completa(tmp_path)
    (run / "artefatos" / "temporario.tmp").write_text("lixo", encoding="utf-8")
    resultado = package_run(run, tmp_path / "b", "run-001",
                            source_project_sha256="s" * 64)
    assert not any("temporario" in nome for nome in resultado.packaged)

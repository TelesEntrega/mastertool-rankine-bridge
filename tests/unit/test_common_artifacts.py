"""Mecanismo comum de escrita de artefatos (`common/artifacts.py`).

O módulo unifica COMO os quatro artefatos comuns são produzidos, nunca o que
eles significam. Estes testes protegem as duas metades disso: que o mecanismo
funciona (escrita via temporário, checksums por último, ordenação estável) e
que a semântica NÃO foi unificada — cada operação continua dona da sua safety
declaration e dos seus artefatos específicos.

O código sob teste roda em IronPython 2.7 dentro do MasterTool; aqui ele é
carregado pelo caminho, como os testes dos probes já fazem.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_MASTERTOOL = REPO_ROOT / "scripts" / "mastertool"

if str(SCRIPTS_MASTERTOOL) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_MASTERTOOL))


def _load(module_name, relative):
    spec = importlib.util.spec_from_file_location(
        module_name, str(SCRIPTS_MASTERTOOL / relative))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


artifacts = _load("mtb_common_artifacts", "common/artifacts.py")

READ_ONLY_SAFETY = {
    "text_document_read": False, "text_document_write": False,
    "export_called": False, "import_called": False, "save_called": False,
    "build_called": False, "online_operation": False, "download_called": False,
    "force_called": False, "project_modified": False,
}

EXPORT_SAFETY = {
    "export_xml_called": True, "export_xml_call_count": 1,
    "filesystem_output_written": True,
    "filesystem_output_scope": "authorized_disposable_export_root",
    "project_save_called": False, "project_build_called": False,
    "text_document_write_called": False, "import_called": False,
    "online_operation": False, "download_called": False, "force_called": False,
}

DIAGNOSTICS = [{"step": "guard", "message": "mensagem"}]


# --- os quatro artefatos ------------------------------------------------------

def test_writes_exactly_the_four_common_artifacts(tmp_path):
    written = artifacts.write_common_artifacts(
        str(tmp_path), DIAGNOSTICS, READ_ONLY_SAFETY, "# relatorio\n")

    assert [Path(p).name for p in written] == list(
        artifacts.COMMON_ARTIFACT_FILENAMES)
    produced = sorted(p.name for p in tmp_path.iterdir())
    assert produced == sorted(artifacts.COMMON_ARTIFACT_FILENAMES)


def test_checksums_is_written_last_and_covers_the_others(tmp_path):
    artifacts.write_common_artifacts(
        str(tmp_path), DIAGNOSTICS, READ_ONLY_SAFETY, "# r\n")

    listed = {}
    for line in (tmp_path / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, rel = line.split(None, 1)
        listed[rel.strip()] = digest
    # cobre os três anteriores e nunca a si mesmo
    assert sorted(listed) == ["diagnostics.json", "report.md",
                              "safety-declaration.json"]
    assert "checksums.sha256" not in listed


def test_specific_artifacts_stay_out_of_the_helper(tmp_path):
    """O helper não produz `manifest.json`, `invocation.json`,
    `target-identity.json` nem nenhum artefato de domínio — eles continuam
    sob responsabilidade de cada operação."""
    artifacts.write_common_artifacts(
        str(tmp_path), DIAGNOSTICS, READ_ONLY_SAFETY, "# r\n")
    produced = {p.name for p in tmp_path.iterdir()}
    for specific in ("manifest.json", "invocation.json", "target-identity.json",
                     "control-validation.json", "created-artifacts.json",
                     "extension-items.json"):
        assert specific not in produced


def test_preexisting_specific_artifacts_are_covered_by_checksums(tmp_path):
    """Escritos pela operação ANTES do helper, entram no checksums — é assim
    que `target-identity.json` continua coberto na exportação."""
    (tmp_path / "target-identity.json").write_text('{"schema_version": 1}',
                                                   encoding="utf-8")
    (tmp_path / "invocation.json").write_text("{}", encoding="utf-8")

    artifacts.write_common_artifacts(
        str(tmp_path), DIAGNOSTICS, EXPORT_SAFETY, "# r\n")

    content = (tmp_path / "checksums.sha256").read_text(encoding="utf-8")
    assert "target-identity.json" in content
    assert "invocation.json" in content


# --- escrita via temporário ---------------------------------------------------

def test_no_temporary_file_remains_after_success(tmp_path):
    artifacts.write_common_artifacts(
        str(tmp_path), DIAGNOSTICS, READ_ONLY_SAFETY, "# r\n")
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_failure_does_not_replace_the_destination(tmp_path, monkeypatch):
    """O destino mantém o conteúdo anterior quando a escrita falha — nunca
    fica truncado nem com conteúdo parcial."""
    target = tmp_path / "diagnostics.json"
    target.write_text('{"anterior": true}', encoding="utf-8")

    def explode(path, data):
        raise IOError("disco cheio")

    monkeypatch.setattr(artifacts.file_io, "write_json", explode)

    with pytest.raises(artifacts.ArtifactWriteError):
        artifacts.write_json_via_temp(str(target), {"novo": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"anterior": True}


def test_failure_leaves_no_temporary_behind(tmp_path, monkeypatch):
    target = tmp_path / "report.md"

    def explode(path, text):
        Path(path).write_text("lixo parcial", encoding="utf-8")
        raise IOError("falhou no meio")

    monkeypatch.setattr(artifacts.file_io, "write_text", explode)

    with pytest.raises(artifacts.ArtifactWriteError):
        artifacts.write_text_via_temp(str(target), "conteudo")

    assert [p.name for p in tmp_path.iterdir()] == []


def test_write_error_is_structured(tmp_path, monkeypatch):
    """Erro estruturado: quem chama precisa saber QUAL arquivo falhou e por
    quê, para registrar diagnóstico em vez de propagar exceção crua."""
    def explode(path, data):
        raise IOError("permissao negada")

    monkeypatch.setattr(artifacts.file_io, "write_json", explode)
    target = tmp_path / "diagnostics.json"

    with pytest.raises(artifacts.ArtifactWriteError) as excinfo:
        artifacts.write_json_via_temp(str(target), {})

    error = excinfo.value
    assert error.path == str(target)
    assert isinstance(error.cause, IOError)
    assert "diagnostics.json" in str(error)
    assert "permissao negada" in str(error)


def test_orphan_temporary_is_not_counted_as_artifact(tmp_path):
    """Um `.tmp` sobrevivente de falha anterior não pode virar artefato
    fantasma no checksums da próxima escrita."""
    (tmp_path / "report.md.tmp").write_text("resto", encoding="utf-8")

    artifacts.write_common_artifacts(
        str(tmp_path), DIAGNOSTICS, READ_ONLY_SAFETY, "# r\n")

    content = (tmp_path / "checksums.sha256").read_text(encoding="utf-8")
    assert ".tmp" not in content


# --- determinismo -------------------------------------------------------------

def test_two_runs_produce_identical_bytes(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    for out in (first, second):
        out.mkdir()
        artifacts.write_common_artifacts(
            str(out), DIAGNOSTICS, READ_ONLY_SAFETY, "# relatorio\n")

    for name in artifacts.COMMON_ARTIFACT_FILENAMES:
        assert (first / name).read_bytes() == (second / name).read_bytes(), name


def test_empty_diagnostics_is_valid(tmp_path):
    """Diagnóstico vazio significa "nada a registrar" — diferente de "não
    verificamos". O artefato é escrito do mesmo jeito."""
    artifacts.write_common_artifacts(
        str(tmp_path), [], READ_ONLY_SAFETY, "# r\n")
    assert json.loads((tmp_path / "diagnostics.json").read_text(encoding="utf-8")) == []


def test_checksum_lines_are_sorted(tmp_path):
    for name in ("z.json", "a.json", "m.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    artifacts.write_common_artifacts(
        str(tmp_path), DIAGNOSTICS, READ_ONLY_SAFETY, "# r\n")

    rels = [line.split(None, 1)[1].strip() for line in
            (tmp_path / "checksums.sha256").read_text(encoding="utf-8").splitlines()]
    assert rels == sorted(rels)


# --- exclusão de diretório (a divergência legítima do probe 20) ---------------

def test_excluded_directory_is_not_walked(tmp_path):
    export_root = tmp_path / "export-root"
    export_root.mkdir()
    (export_root / "pou-export").write_text("conteudo da API", encoding="utf-8")
    (tmp_path / "invocation.json").write_text("{}", encoding="utf-8")

    artifacts.write_common_artifacts(
        str(tmp_path), DIAGNOSTICS, EXPORT_SAFETY, "# r\n",
        checksums_exclude_dirs=[str(export_root)])

    content = (tmp_path / "checksums.sha256").read_text(encoding="utf-8")
    assert "pou-export" not in content, (
        "conteúdo produzido pela API do MasterTool não pode entrar no "
        "checksums do probe — tem hashes próprios em created-artifacts.json")
    assert "invocation.json" in content


def test_without_exclusion_everything_is_covered(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "dentro.json").write_text("{}", encoding="utf-8")

    artifacts.write_common_artifacts(
        str(tmp_path), DIAGNOSTICS, READ_ONLY_SAFETY, "# r\n")

    content = (tmp_path / "checksums.sha256").read_text(encoding="utf-8")
    assert "sub/dentro.json" in content


# --- a semântica NÃO foi unificada -------------------------------------------

def test_helper_does_not_validate_or_rewrite_the_safety_declaration(tmp_path):
    """O helper grava a declaração como recebeu. As duas classes continuam
    separadas e validadas pelo host (`artifact_validation.py`), cada uma com
    as suas chaves — um schema permissivo aqui aceitaria uma exportação
    silenciosa e um probe que escreveu."""
    artifacts.write_common_artifacts(
        str(tmp_path), DIAGNOSTICS, EXPORT_SAFETY, "# r\n")
    written = json.loads(
        (tmp_path / "safety-declaration.json").read_text(encoding="utf-8"))
    assert written == EXPORT_SAFETY

    other = tmp_path / "outro"
    other.mkdir()
    artifacts.write_common_artifacts(
        str(other), DIAGNOSTICS, READ_ONLY_SAFETY, "# r\n")
    assert json.loads(
        (other / "safety-declaration.json").read_text(encoding="utf-8")) == READ_ONLY_SAFETY


def test_the_two_safety_classes_remain_incompatible():
    """Nenhuma chave `True` da exportação pode ser aceitável num probe
    read-only, e vice-versa: as formas são opostas por construção."""
    from mastertool_bridge.automation.artifact_validation import (
        LADDER_PROBE_SAFETY_DECLARATION_KEYS,
        PLCOPEN_EXPORT_SAFETY_TRUE_KEYS)

    for key in PLCOPEN_EXPORT_SAFETY_TRUE_KEYS:
        assert EXPORT_SAFETY[key] is True
    for key in LADDER_PROBE_SAFETY_DECLARATION_KEYS:
        assert READ_ONLY_SAFETY[key] is False
    # os dois vocabulários não se confundem
    assert not (set(PLCOPEN_EXPORT_SAFETY_TRUE_KEYS)
                & set(LADDER_PROBE_SAFETY_DECLARATION_KEYS))

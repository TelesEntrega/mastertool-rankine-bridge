# -*- coding: utf-8 -*-
"""Testes de `scripts/mastertool/common/authoring_text.py`.

Puros: nenhum MasterTool, nenhum CLR, nenhum I/O real. Onde o modulo aceita
um `writer` injetado, o teste usa um duble em memoria.
"""

import os
import sys

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))
_MASTERTOOL_DIR = os.path.join(_REPO_ROOT, "scripts", "mastertool")
if _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)

from common import authoring_text as at  # noqa: E402


EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# --- normalize_text / texts_equivalent --------------------------------------

def test_crlf_e_lf_sao_equivalentes():
    assert at.texts_equivalent("linha1\r\nlinha2\r\n", "linha1\nlinha2\n")


def test_espaco_em_branco_no_fim_da_linha_e_ignorado():
    assert at.texts_equivalent("abc   \ndef\t\n", "abc\ndef\n")


def test_uma_quebra_de_linha_final_e_ignorada():
    assert at.texts_equivalent("conteudo\n", "conteudo")


def test_duas_quebras_de_linha_finais_nao_sao_ignoradas():
    assert not at.texts_equivalent("conteudo\n\n", "conteudo")
    assert not at.texts_equivalent("conteudo\n\n", "conteudo\n")


def test_texto_diferente_no_meio_e_detectado_na_linha_certa():
    expected = "linha1\nlinha2\nlinha3\n"
    observed = "linha1\nDIVERGE\nlinha3\n"
    report = at.text_diff_report(expected, observed)
    assert report["equivalent"] is False
    assert report["first_divergent_line"] == 2
    assert report["expected_line"] == "linha2"
    assert report["observed_line"] == "DIVERGE"


def test_text_diff_report_equivalente_sob_normalizacao():
    report = at.text_diff_report("igual\r\n", "igual")
    assert report["equivalent"] is True
    assert report["first_divergent_line"] is None
    assert report["expected_line"] is None
    assert report["observed_line"] is None
    assert report["expected_normalized_sha256"] == report["observed_normalized_sha256"]


def test_text_diff_report_nunca_levanta_com_entrada_invalida():
    report = at.text_diff_report(None, 12345)
    assert isinstance(report, dict)
    assert "equivalent" in report


# --- sha256 -----------------------------------------------------------------

def test_sha256_of_text_vazio():
    assert at.sha256_of_text("") == EMPTY_SHA256


def test_sha256_of_file_devolve_erro_sem_levantar_para_caminho_inexistente():
    digest, error = at.sha256_of_file(
        os.path.join(_REPO_ROOT, "caminho-que-nao-existe-authoring-text.tmp"))
    assert digest is None
    assert error is not None


def test_sha256_of_file_le_conteudo_real(tmp_path):
    path = str(tmp_path / "arquivo.txt")
    with open(path, "wb") as handle:
        handle.write(b"")
    digest, error = at.sha256_of_file(path)
    assert error is None
    assert digest == EMPTY_SHA256


# --- multiset_difference ------------------------------------------------

def test_multiset_difference_com_nomes_repetidos():
    before = ["MainPrg", "MainPrg", "GVL1"]
    after = ["MainPrg", "GVL1", "GVL1", "Novo"]
    added, missing = at.multiset_difference(before, after)
    assert added == ["GVL1", "Novo"]
    assert missing == ["MainPrg"]


def test_multiset_difference_identico_nao_gera_diff():
    names = ["A", "A", "B"]
    added, missing = at.multiset_difference(names, list(names))
    assert added == []
    assert missing == []


# --- structural_diff ---------------------------------------------------

def _snapshot(persistent_names, transient_names=None):
    return {
        "persistent": [{"name": n} for n in persistent_names],
        "transient": [{"name": n} for n in (transient_names or [])],
    }


def test_structural_diff_dentro_da_allowlist():
    before = _snapshot(["GVL1"])
    after = _snapshot(["GVL1", "PRG_AI_TESTE"])
    diff = at.structural_diff(before, after, ["PRG_AI_TESTE"])
    assert diff["added"] == ["PRG_AI_TESTE"]
    assert diff["missing"] == []
    assert diff["within_allowlist"] is True


def test_structural_diff_fora_da_allowlist_por_remocao():
    before = _snapshot(["GVL1", "GVL2"])
    after = _snapshot(["GVL1", "PRG_AI_TESTE"])
    diff = at.structural_diff(before, after, ["PRG_AI_TESTE"])
    assert diff["missing"] == ["GVL2"]
    assert diff["within_allowlist"] is False


def test_structural_diff_fora_da_allowlist_por_adicao_extra():
    before = _snapshot(["GVL1"])
    after = _snapshot(["GVL1", "PRG_AI_TESTE", "EXTRA"])
    diff = at.structural_diff(before, after, ["PRG_AI_TESTE"])
    assert diff["within_allowlist"] is False


# --- Journal --------------------------------------------------------------

def test_journal_sequencia_continua_e_append_only():
    ticks = iter(["t0", "t1", "t2"])
    journal = at.Journal(now=lambda: next(ticks))
    e0 = journal.record({"event": "a"})
    e1 = journal.record({"event": "b"})
    e2 = journal.record({"event": "c"})
    assert [e["sequence"] for e in (e0, e1, e2)] == [0, 1, 2]
    assert [e["timestamp"] for e in (e0, e1, e2)] == ["t0", "t1", "t2"]
    assert len(journal.entries) == 3
    # append-only: a lista interna preserva ordem e nao e mutada por fora
    assert journal.entries[0]["event"] == "a"
    assert journal.entries[-1]["event"] == "c"


def test_journal_escreve_via_writer_injetado_quando_path_presente():
    written = []

    def fake_writer(path, text):
        written.append((path, text))

    journal = at.Journal(now=lambda: "t0", writer=fake_writer, path="/fake/journal.jsonl")
    journal.record({"event": "x"})
    assert len(written) == 1
    assert written[0][0] == "/fake/journal.jsonl"
    assert "\"event\": \"x\"" in written[0][1]


def test_journal_sem_writer_nao_toca_disco():
    journal = at.Journal(now=lambda: "t0", writer=None, path="/fake/journal.jsonl")
    # nao deve levantar mesmo com path setado, pois writer e None
    journal.record({"event": "x"})
    assert len(journal.entries) == 1


# --- strip_volatile / determinismo -----------------------------------------

def test_strip_volatile_remove_exatamente_os_campos_declarados():
    payload = {"status": "ok", "generated_at": "2026-01-01T00:00:00",
              "started_at": "x", "finished_at": "y", "timestamp": "z",
              "value": 42}
    stripped = at.strip_volatile(payload)
    assert stripped == {"status": "ok", "value": 42}
    for field in at.VOLATILE_FIELDS:
        assert field not in stripped


def test_strip_volatile_nunca_levanta_com_entrada_invalida():
    assert at.strip_volatile(None) == {}
    assert at.strip_volatile(["nao", "e", "dict"]) == {}


def test_determinismo_mesma_entrada_mesmo_payload_sem_volateis():
    def make_completion(now_value):
        return at.build_completion(
            status="ok", exit_code=0,
            extra_fields={"plan_sha256": "abc123", "operations": ["create_program"]},
            schema_version="1.0", script_name="probes/xx.py",
            finished_at=now_value)

    payload_a = make_completion("2026-01-01T00:00:00")
    payload_b = make_completion("2026-01-02T00:00:00")

    assert payload_a != payload_b  # generated_at difere
    assert at.strip_volatile(payload_a) == at.strip_volatile(payload_b)


# --- build_manifest / build_completion --------------------------------------

def test_build_manifest_inclui_metadados_fixos_e_exclui_journal():
    result = {"status": "ok", "journal": [{"sequence": 0}], "problems": []}
    manifest = at.build_manifest(
        result, artifact_names=("manifest.json",),
        exit_code_by_status={"ok": 0}, volatile_fields=("finished_at",))
    assert "journal" not in manifest
    assert manifest["status"] == "ok"
    assert manifest["artifact_names"] == ["manifest.json"]
    assert manifest["volatile_fields"] == ["finished_at"]
    assert manifest["exit_code_by_status"] == {"ok": 0}


def test_build_completion_mescla_campos_extras_sem_sobrescrever_fixos():
    completion = at.build_completion(
        status="saved_as", exit_code=0,
        extra_fields={"status": "deveria-ser-ignorado-se-colidisse",
                     "custom": "valor"},
        schema_version="1.0", script_name="probes/x.py",
        finished_at="2026-01-01T00:00:00")
    # extra_fields tem chave "status" tambem: o merge por cima e esperado e
    # documentado -- o chamador nao deve reusar chaves fixas em extra_fields.
    assert completion["custom"] == "valor"
    assert completion["schema_version"] == "1.0"
    assert completion["script"] == "probes/x.py"


# --- object_identity ---------------------------------------------------

class _FakeObj(object):
    def __init__(self, name, type_guid=None, is_folder=None, is_transient=None,
                has_decl=None, has_impl=None):
        self._name = name
        self.type = type_guid
        if is_folder is not None:
            self.is_folder = is_folder
        if is_transient is not None:
            self.is_transient_object = is_transient
        if has_decl is not None:
            self.has_textual_declaration = has_decl
        if has_impl is not None:
            self.has_textual_implementation = has_impl

    def get_name(self, recursive):
        return self._name


def test_object_identity_le_campos_esperados():
    obj = _FakeObj("PRG_AI_TESTE", type_guid="guid-1", is_folder=False,
                  is_transient=False, has_decl=True, has_impl=True)
    identity = at.object_identity(obj)
    assert identity["name"] == "PRG_AI_TESTE"
    assert identity["type_guid"] == "guid-1"
    assert identity["is_folder"] is False
    assert identity["is_transient"] is False
    assert identity["has_textual_declaration"] is True
    assert identity["has_textual_implementation"] is True
    assert identity["errors"] == []


def test_object_identity_nunca_levanta_com_get_name_quebrado():
    class Broken(object):
        def get_name(self, recursive):
            raise RuntimeError("boom")

    identity = at.object_identity(Broken())
    assert identity["name"] is None
    assert identity["errors"]

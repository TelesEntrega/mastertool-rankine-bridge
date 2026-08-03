"""Testes do Evidence Bundle (fase R2).

O que este pacote promete é **verificabilidade**, não impossibilidade de
alteração — e é isso que os testes exercitam: alterar um arquivo selado é
possível, e tem de ser detectado.
"""

import json

import pytest

from mastertool_bridge.evidence import bundle as eb


def _bundle_completo(tmp_path, run_id="run-001"):
    pacote = eb.EvidenceBundle(tmp_path / run_id, run_id).create()
    pacote.add("source", "project.sha256", "a" * 64)
    pacote.add("plan", "specification.json", {"schema_version": 1})
    pacote.add("plan", "normalized_plan.json", {"steps": []})
    pacote.add("plan", "plan.sha256", "b" * 64)
    pacote.add("execution", "journal.jsonl", '{"step": 1}\n')
    pacote.add("verification", "reopened_inventory.json", {"nodes": 42})
    pacote.add("verification", "build_report.json", {"errors": 0, "warnings": 0})
    pacote.add("output", "project.sha256", "c" * 64)
    return pacote


# =============================================================================
# montagem
# =============================================================================

def test_pacote_completo_sela_como_completo(tmp_path):
    manifesto = _bundle_completo(tmp_path).seal()
    assert manifesto.status == eb.STATUS_SEALED_COMPLETE
    assert manifesto.complete is True
    assert manifesto.missing_required == []
    assert len(manifesto.files) == 8
    assert manifesto.bundle_sha256


def test_pacote_incompleto_SELA_e_nomeia_o_que_falta(tmp_path):
    """Recusar-se a selar deixaria a evidência do fracasso solta em disco, sem
    hash e sem manifesto — e é a execução que deu errado que mais precisa
    ficar registrada."""
    pacote = eb.EvidenceBundle(tmp_path / "run-002", "run-002").create()
    pacote.add("source", "project.sha256", "a" * 64)
    manifesto = pacote.seal()
    assert manifesto.status == eb.STATUS_SEALED_INCOMPLETE
    assert manifesto.complete is False
    assert "plan/specification.json" in manifesto.missing_required
    assert "execution/journal.jsonl" in manifesto.missing_required


def test_secao_desconhecida_e_recusada_na_gravacao(tmp_path):
    pacote = eb.EvidenceBundle(tmp_path / "r", "r").create()
    with pytest.raises(eb.BundleError) as erro:
        pacote.add("anexos", "qualquer.json", {})
    assert "não existe no layout" in str(erro.value)


def test_arquivo_fora_do_layout_e_recusado(tmp_path):
    """Descoberto na gravação, e não na hora de ler."""
    pacote = eb.EvidenceBundle(tmp_path / "r", "r").create()
    with pytest.raises(eb.BundleError) as erro:
        pacote.add("plan", "plano_v2_final.json", {})
    assert "não é declarado" in str(erro.value)


def test_nada_entra_depois_do_selo(tmp_path):
    pacote = _bundle_completo(tmp_path)
    pacote.seal()
    with pytest.raises(eb.BundleError) as erro:
        pacote.add("approval", "decision.json", {"approved": True})
    assert "já está selado" in str(erro.value)


def test_selar_duas_vezes_e_recusado(tmp_path):
    pacote = _bundle_completo(tmp_path)
    pacote.seal()
    with pytest.raises(eb.BundleError):
        pacote.seal()


def test_conteudo_bytes_str_e_json_sao_gravados_sem_adivinhacao(tmp_path):
    pacote = eb.EvidenceBundle(tmp_path / "r", "r").create()
    caminho_texto = pacote.add("execution", "stdout.log", "linha\n")
    caminho_bytes = pacote.add("execution", "journal.jsonl", b'{"a":1}\n')
    caminho_json = pacote.add("plan", "specification.json", {"b": 2})
    assert caminho_texto.read_text(encoding="utf-8") == "linha\n"
    assert caminho_bytes.read_bytes() == b'{"a":1}\n'
    assert json.loads(caminho_json.read_text(encoding="utf-8")) == {"b": 2}


def test_metadata_entra_no_manifesto(tmp_path):
    manifesto = _bundle_completo(tmp_path).seal(
        metadata={"qualification_id": "R1-W7-W9", "run": 1})
    assert manifesto.to_dict()["metadata"]["qualification_id"] == "R1-W7-W9"


# =============================================================================
# verificação — a promessa real do pacote
# =============================================================================

def test_pacote_intacto_verifica(tmp_path):
    _bundle_completo(tmp_path).seal()
    resultado = eb.verify_bundle(tmp_path / "run-001")
    assert resultado.intact is True
    assert resultado.checked_files == 8
    assert resultado.status == eb.STATUS_SEALED_COMPLETE


def test_conteudo_alterado_depois_do_selo_e_detectado(tmp_path):
    _bundle_completo(tmp_path).seal()
    alvo = tmp_path / "run-001" / "verification" / "build_report.json"
    alvo.write_text('{"errors": 0, "warnings": 0, "mentira": true}',
                    encoding="utf-8")
    resultado = eb.verify_bundle(tmp_path / "run-001")
    assert resultado.intact is False
    assert any("conteúdo alterado" in p for p in resultado.problems)


def test_arquivo_removido_depois_do_selo_e_detectado(tmp_path):
    _bundle_completo(tmp_path).seal()
    (tmp_path / "run-001" / "execution" / "journal.jsonl").unlink()
    resultado = eb.verify_bundle(tmp_path / "run-001")
    assert any("sumiu" in p for p in resultado.problems)


def test_arquivo_acrescentado_depois_do_selo_e_detectado(tmp_path):
    """O caso que um manifesto só de hashes não pegaria: nada foi alterado,
    algo foi ACRESCENTADO."""
    _bundle_completo(tmp_path).seal()
    (tmp_path / "run-001" / "approval" / "decision.json").write_text(
        '{"approved": true}', encoding="utf-8")
    resultado = eb.verify_bundle(tmp_path / "run-001")
    assert any("acrescentado depois do selo" in p for p in resultado.problems)


def test_manifesto_editado_para_esconder_alteracao_e_detectado(tmp_path):
    """Alterar o arquivo E o hash declarado ainda derruba o hash do CONJUNTO."""
    _bundle_completo(tmp_path).seal()
    raiz = tmp_path / "run-001"
    alvo = raiz / "output" / "project.sha256"
    alvo.write_text("d" * 64, encoding="utf-8")

    import hashlib
    novo_sha = hashlib.sha256(alvo.read_bytes()).hexdigest()
    manifesto = json.loads((raiz / eb.MANIFEST_NAME).read_text(encoding="utf-8"))
    manifesto["files"]["output/project.sha256"] = novo_sha
    (raiz / eb.MANIFEST_NAME).write_text(
        json.dumps(manifesto, ensure_ascii=False), encoding="utf-8")

    resultado = eb.verify_bundle(raiz)
    assert resultado.intact is False
    assert any("o próprio manifesto foi editado" in p
               for p in resultado.problems)


def test_pacote_sem_manifesto_nao_e_verificavel(tmp_path):
    pacote = _bundle_completo(tmp_path)
    resultado = eb.verify_bundle(pacote.root)
    assert resultado.intact is False
    assert any("nunca foi selado" in p for p in resultado.problems)


def test_manifesto_ilegivel_vira_problema_e_nao_excecao(tmp_path):
    _bundle_completo(tmp_path).seal()
    (tmp_path / "run-001" / eb.MANIFEST_NAME).write_text(
        "{ isto não é json", encoding="utf-8")
    resultado = eb.verify_bundle(tmp_path / "run-001")
    assert any("ilegível" in p for p in resultado.problems)


def test_verificar_diretorio_inexistente_nao_levanta(tmp_path):
    resultado = eb.verify_bundle(tmp_path / "nao-existe")
    assert resultado.intact is False


# =============================================================================
# layout
# =============================================================================

def test_o_layout_cobre_as_secoes_do_roadmap():
    """Seis vieram de `ROADMAP` §2.7. A sétima, `rollback`, foi acrescentada
    em 2026-08-02 porque o gate da R2 pede *reversível* e o layout original
    não dava onde guardar o que uma reversão exige: o TEXTO anterior. O pacote
    guardava o hash dele, e hash não reconstrói texto — um pacote que registra
    uma mudança sem registrar como desfazê-la não fecha o gate."""
    assert set(eb.SECTIONS) == {"source", "plan", "execution", "verification",
                                "output", "approval", "rollback"}


def test_rollback_nao_tem_arquivo_OBRIGATORIO():
    """Execução que só cria não tem o que reverter. Exigir o artefato dela
    faria toda run de criação selar incompleta — a condição é do PLANO, e
    quem a conhece é `evidence/from_run.py`."""
    assert eb.BUNDLE_LAYOUT["rollback"]["required"] == ()
    assert "before-texts.json" in eb.BUNDLE_LAYOUT["rollback"]["optional"]


def test_toda_secao_declara_required_e_optional():
    for secao, layout in eb.BUNDLE_LAYOUT.items():
        assert set(layout) == {"required", "optional"}, secao
        assert isinstance(layout["required"], tuple)
        assert isinstance(layout["optional"], tuple)


def test_aprovacao_nao_tem_arquivo_obrigatorio():
    """Um pacote é selável antes de existir decisão humana — a decisão é o
    passo seguinte, não uma precondição da evidência."""
    assert eb.BUNDLE_LAYOUT["approval"]["required"] == ()


def test_nomes_permitidos_de_secao_inexistente_e_vazio():
    assert eb.allowed_names("inexistente") == ()

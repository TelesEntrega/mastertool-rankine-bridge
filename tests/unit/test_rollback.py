"""A spec inversa — testes da quarta palavra do gate da fase R2.

O que estes testes fixam não é "sabe gerar uma spec": é **quando ele se
recusa**. Uma reversão que emite spec com o texto errado, ou que confere
contra o hash errado, é pior que reversão nenhuma — ela escreve, e escreve com
a aparência de ter sido verificada.
"""

import hashlib

import pytest

from mastertool_bridge.changes.rollback import build_rollback_spec

ANTES = "// texto anterior\n;\n"
DEPOIS = "// texto novo\n;\n"
SHA_ANTES = hashlib.sha256(ANTES.encode("utf-8")).hexdigest()
SHA_DEPOIS = hashlib.sha256(DEPOIS.encode("utf-8")).hexdigest()
ORIGEM = "modify:programs:UserPrg:implementation"
SAIDA = "f" * 64


def _plano(**mudancas):
    passo = {"sequence": 1, "operation": "replace",
             "source_location": ORIGEM,
             "target_name": "UserPrg",
             "target_kind": "program_implementation",
             "expected_before_kind": "measured",
             "expected_before_sha256": SHA_ANTES,
             "planned_after_sha256": SHA_DEPOIS}
    passo.update(mudancas)
    return {"steps": [passo, {"sequence": 2, "operation": "save_as",
                              "source_location": "$project"}],
            "template": {"id": "TemplateExemplo_v1", "sha256": "a" * 64}}


def _antes(**mudancas):
    entrada = {"source_location": ORIGEM, "name": "UserPrg",
               "target_kind": "program_implementation",
               "sha256": SHA_ANTES, "text": ANTES}
    entrada.update(mudancas)
    return {"objects": [entrada]}


# =============================================================================
# a inversão
# =============================================================================

def test_a_spec_inversa_troca_os_dois_hashes_de_lado():
    """O invariante do módulo. O `antes` da reversão é o `depois` da
    alteração, e o texto da reversão é o texto anterior."""
    r = build_rollback_spec(_plano(), _antes(), output_project_sha256=SAIDA)
    assert r.ok, r.problems
    (m,) = r.spec["modifications"]
    assert m["expected_before_sha256"] == SHA_DEPOIS
    assert m["text"] == ANTES
    assert m["family"] == "programs"
    assert m["name"] == "UserPrg"
    assert m["field"] == "implementation"


def test_o_alvo_da_reversao_e_a_SAIDA_e_nao_o_template():
    """Um hash anterior só vale para o arquivo onde foi medido. O template não
    tem o texto novo — reverter contra ele conferiria a coisa errada."""
    r = build_rollback_spec(_plano(), _antes(), output_project_sha256=SAIDA)
    assert r.spec["template"]["sha256"] == SAIDA


def test_reverter_a_reversao_devolve_o_original():
    """Aplicar o módulo sobre o próprio resultado tem que fechar o ciclo."""
    ida = build_rollback_spec(_plano(), _antes(), output_project_sha256=SAIDA)
    volta = build_rollback_spec(
        _plano(expected_before_sha256=SHA_DEPOIS,
               planned_after_sha256=SHA_ANTES),
        {"objects": [{"source_location": ORIGEM, "sha256": SHA_DEPOIS,
                      "text": DEPOIS}]},
        output_project_sha256="e" * 64)
    assert ida.spec["modifications"][0]["text"] == ANTES
    assert volta.spec["modifications"][0]["text"] == DEPOIS


def test_varias_alteracoes_viram_varias_reversoes():
    plano = _plano()
    outra = "modify:gvls:GVL_A:declaration"
    plano["steps"].append({"sequence": 3, "operation": "replace",
                           "source_location": outra,
                           "planned_after_sha256": "b" * 64})
    antes = _antes()
    antes["objects"].append({"source_location": outra, "sha256": SHA_ANTES,
                             "text": ANTES})
    r = build_rollback_spec(plano, antes, output_project_sha256=SAIDA)
    assert r.ok, r.problems
    assert len(r.spec["modifications"]) == 2
    assert sorted(r.reverted) == ["gvls:GVL_A:declaration",
                                  "programs:UserPrg:implementation"]


def test_texto_anterior_VAZIO_e_reversivel():
    """O caso do W10: a `UserPrg` do template tem implementação vazia. Tratar
    string vazia como "sem texto" tornaria justamente esse alvo irreversível."""
    vazio = hashlib.sha256(b"").hexdigest()
    r = build_rollback_spec(_plano(),
                            _antes(text="", sha256=vazio),
                            output_project_sha256=SAIDA)
    assert r.ok, r.problems
    assert r.spec["modifications"][0]["text"] == ""


# =============================================================================
# as recusas — o que o módulo existe para não fazer
# =============================================================================

def test_sem_o_texto_anterior_RECUSA_em_vez_de_apagar():
    """O modo de falha que destrói dado: sem texto anterior, uma spec com
    `text: ""` apagaria o objeto e teria a aparência de reversão."""
    r = build_rollback_spec(_plano(), {"objects": []},
                            output_project_sha256=SAIDA)
    assert not r.ok
    assert r.spec is None
    assert any("adivinhar o conteúdo" in p for p in r.problems)


def test_hash_que_nao_confere_com_o_proprio_texto_RECUSA():
    """Artefato corrompido que passasse daqui viraria spec que escreve
    conteúdo errado com hash certo — o pior desfecho possível."""
    r = build_rollback_spec(_plano(), _antes(text="OUTRO TEXTO"),
                            output_project_sha256=SAIDA)
    assert not r.ok
    assert any("ninguém conferiu" in p for p in r.problems)


def test_passo_sem_planned_after_sha256_RECUSA():
    r = build_rollback_spec(_plano(planned_after_sha256=None), _antes(),
                            output_project_sha256=SAIDA)
    assert not r.ok
    assert any("contra o que conferir" in p for p in r.problems)


def test_plano_sem_alteracao_e_RECUSA_e_nao_spec_vazia():
    """"Não há o que reverter" e "a reversão está pronta" são estados
    diferentes. Devolver spec vazia faria o chamador executar um nada."""
    r = build_rollback_spec({"steps": [{"operation": "create_gvl",
                                        "source_location": "gvls:G:declaration"}],
                             "template": {"sha256": "a" * 64}},
                            _antes(), output_project_sha256=SAIDA)
    assert not r.ok
    assert any("não há o que reverter" in p for p in r.problems)


def test_sem_sha_do_alvo_RECUSA_quando_o_plano_tambem_nao_tem():
    plano = _plano()
    plano.pop("template")
    r = build_rollback_spec(plano, _antes())
    assert not r.ok
    assert any("projeto ALVO" in p for p in r.problems)


def test_source_location_fora_da_forma_RECUSA():
    r = build_rollback_spec(_plano(source_location="modify:so:duas"),
                            _antes(), output_project_sha256=SAIDA)
    assert not r.ok
    assert any("fora da forma" in p for p in r.problems)


@pytest.mark.parametrize("plano", [None, [], "x", 7, {}, {"steps": "x"}])
def test_plano_degenerado_nao_levanta(plano):
    assert not build_rollback_spec(plano, _antes()).ok


@pytest.mark.parametrize("antes", [None, [], "x", 7, {}, {"objects": "x"},
                                   {"objects": [{"sem_origem": 1}]}])
def test_artefato_de_antes_degenerado_nao_levanta(antes):
    assert not build_rollback_spec(_plano(), antes).ok


def test_serializacao():
    d = build_rollback_spec(_plano(), _antes(),
                            output_project_sha256=SAIDA).to_dict()
    assert d["ok"] is True
    assert d["schema_version"] == 1
    assert d["reverted"] == ["programs:UserPrg:implementation"]

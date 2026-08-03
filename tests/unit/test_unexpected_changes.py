"""Testes do detector de mudança não autorizada (fase R2).

O que este módulo promete não é "sei dizer que mudou": é **saber dizer que
NADA além do autorizado mudou**, e recusar-se a dizer isso quando não pôde
comparar.
"""

import pytest

from mastertool_bridge.diff import unexpected_changes as uc

GVL = "ffbfa93a-b94d-45fc-a329-229860183b1d"
POU = "6f9dac99-8de1-4efc-8465-68ac443b7d08"


def _nos(*nomes_e_tipos):
    return {"nodes": [{"name": n, "type_guid": t, "object_guid": "g-%s" % n}
                      for n, t in nomes_e_tipos]}


def _textos(**por_chave):
    objetos = {}
    for chave, sha in por_chave.items():
        familia, nome, campo = chave.split("__")
        objetos.setdefault((familia, nome), []).append(
            {"field": campo, "sha256_observed": sha})
    return {"objects": [{"family": f, "name": n, "texts": t}
                        for (f, n), t in objetos.items()]}


ANTES_NOS = _nos(("GVL_A", GVL), ("PRG_B", POU))
ANTES_TXT = _textos(gvls__GVL_A__declaration="a" * 64,
                    programs__PRG_B__implementation="b" * 64)


# =============================================================================
# o caminho limpo
# =============================================================================

def test_so_o_autorizado_mudou():
    depois = _textos(gvls__GVL_A__declaration="a" * 64,
                     programs__PRG_B__implementation="NOVO" + "b" * 60)
    r = uc.compare(ANTES_NOS, ANTES_NOS, ANTES_TXT, depois,
                   authorized=["programs:PRG_B:implementation"])
    assert r.verdict == uc.VERDICT_UNCHANGED
    assert r.clean is True
    assert r.authorized_and_changed == ["programs:PRG_B:implementation"]
    assert r.unauthorized_text_changes == []


def test_nada_mudou_tambem_e_limpo():
    r = uc.compare(ANTES_NOS, ANTES_NOS, ANTES_TXT, ANTES_TXT)
    assert r.clean is True
    assert r.added_objects == []


# =============================================================================
# o que sobra é o achado
# =============================================================================

def test_texto_nao_autorizado_que_mudou_e_achado():
    """O caso que a fase R2 existe para pegar."""
    depois = _textos(gvls__GVL_A__declaration="MUDOU" + "a" * 59,
                     programs__PRG_B__implementation="b" * 64)
    r = uc.compare(ANTES_NOS, ANTES_NOS, ANTES_TXT, depois,
                   authorized=["programs:PRG_B:implementation"])
    assert r.verdict == uc.VERDICT_UNEXPECTED
    assert r.clean is False
    assert r.unauthorized_text_changes == ["gvls:GVL_A:declaration"]


def test_objeto_a_mais_na_arvore_e_achado_mesmo_com_texto_perfeito():
    """Um `replace` de texto não deve mexer na árvore — medido em W1.3A, nove
    filhos antes e nove depois. Se mexeu, é achado ainda que todo texto
    autorizado esteja certo."""
    depois_nos = _nos(("GVL_A", GVL), ("PRG_B", POU), ("PRG_INTRUSO", POU))
    r = uc.compare(ANTES_NOS, depois_nos, ANTES_TXT, ANTES_TXT)
    assert r.verdict == uc.VERDICT_UNEXPECTED
    assert r.added_objects == ["PRG_INTRUSO:%s" % POU]


def test_objeto_removido_e_achado():
    depois_nos = _nos(("GVL_A", GVL))
    r = uc.compare(ANTES_NOS, depois_nos, ANTES_TXT, ANTES_TXT)
    assert r.verdict == uc.VERDICT_UNEXPECTED
    assert r.removed_objects == ["PRG_B:%s" % POU]


def test_as_duas_camadas_sao_relatadas_separadas():
    """Fundi-las mandaria o operador investigar a árvore quando o problema é
    texto."""
    depois_nos = _nos(("GVL_A", GVL), ("PRG_B", POU), ("EXTRA", POU))
    depois_txt = _textos(gvls__GVL_A__declaration="z" * 64,
                         programs__PRG_B__implementation="b" * 64)
    r = uc.compare(ANTES_NOS, depois_nos, ANTES_TXT, depois_txt)
    assert r.added_objects
    assert r.unauthorized_text_changes
    assert r.added_objects != r.unauthorized_text_changes


# =============================================================================
# autorizado que não mudou — informação, não reprovação
# =============================================================================

def test_autorizado_que_nao_mudou_e_relatado_sem_reprovar():
    """O plano pediu uma alteração que não teve efeito. Costuma ser texto
    idêntico ao que já estava lá — vale saber, não vale reprovar."""
    r = uc.compare(ANTES_NOS, ANTES_NOS, ANTES_TXT, ANTES_TXT,
                   authorized=["programs:PRG_B:implementation"])
    assert r.clean is True
    assert r.authorized_but_unchanged == ["programs:PRG_B:implementation"]
    assert r.authorized_and_changed == []


# =============================================================================
# incomparável NUNCA é "nada mudou"
# =============================================================================

@pytest.mark.parametrize("faltante", ["before_nodes", "after_nodes",
                                      "before_texts", "after_texts"])
def test_artefato_ausente_e_INCOMPARAVEL(faltante):
    argumentos = {"before_nodes": ANTES_NOS, "after_nodes": ANTES_NOS,
                  "before_texts": ANTES_TXT, "after_texts": ANTES_TXT}
    argumentos[faltante] = None
    r = uc.compare(**argumentos)
    assert r.verdict == uc.VERDICT_INCOMPARABLE
    assert r.clean is False
    assert any("INCOMPARÁVEL" in p for p in r.problems)


def test_incomparavel_nao_e_limpo_mesmo_sem_achado():
    """A distinção que o módulo existe para preservar: um lote sem artefato e
    um lote comprovadamente idêntico são estados opostos."""
    r = uc.compare(None, None, None, None)
    assert r.added_objects == []
    assert r.unauthorized_text_changes == []
    assert r.clean is False


@pytest.mark.parametrize("entrada", ["texto", 7, [], {"sem_nodes": 1},
                                    {"nodes": []}])
def test_artefato_degenerado_nao_levanta(entrada):
    r = uc.compare(entrada, ANTES_NOS, ANTES_TXT, ANTES_TXT)
    assert r.verdict == uc.VERDICT_INCOMPARABLE


def test_zero_nos_e_leitura_FALHA_nao_arvore_vazia():
    """Um projeto do MasterTool sempre tem nós. Aceitar o vazio como medição
    faria todo o estado seguinte parecer acrescentado — veredito enganoso no
    lugar de recusa."""
    r = uc.compare({"nodes": []}, ANTES_NOS, ANTES_TXT, ANTES_TXT)
    assert r.verdict == uc.VERDICT_INCOMPARABLE
    assert r.added_objects == []


def test_zero_textos_tambem_e_leitura_falha():
    r = uc.compare(ANTES_NOS, ANTES_NOS, {"objects": []}, ANTES_TXT)
    assert r.verdict == uc.VERDICT_INCOMPARABLE


# =============================================================================
# forma
# =============================================================================

def test_object_guid_nao_entra_na_identidade():
    """Ele é sorteado a cada criação. Entrasse, toda comparação entre gerações
    independentes acusaria mudança em tudo."""
    assert "object_guid" not in uc.NODE_IDENTITY_FIELDS
    outros_guids = {"nodes": [dict(n, object_guid="OUTRO")
                              for n in ANTES_NOS["nodes"]]}
    r = uc.compare(ANTES_NOS, outros_guids, ANTES_TXT, ANTES_TXT)
    assert r.clean is True


def test_vocabulario_de_veredito_e_fechado():
    assert len(set(uc.VERDICTS)) == 3
    r = uc.compare(ANTES_NOS, ANTES_NOS, ANTES_TXT, ANTES_TXT)
    assert r.verdict in uc.VERDICTS


def test_serializacao():
    d = uc.compare(ANTES_NOS, ANTES_NOS, ANTES_TXT, ANTES_TXT).to_dict()
    assert d["clean"] is True
    assert d["verdict"] == uc.VERDICT_UNCHANGED
    assert d["schema_version"] == 1


# =============================================================================
# o comando que produz `verification/unexpected_changes.json`
# =============================================================================

def _escrever(tmp_path, nome, conteudo):
    import io
    import json
    import os

    caminho = os.path.join(str(tmp_path), nome)
    io.open(caminho, "w", encoding="utf-8", newline="\n").write(
        json.dumps(conteudo, ensure_ascii=False))
    return caminho


def _quatro(tmp_path, depois_txt=None, depois_nos=None):
    return [
        "--before-nodes", _escrever(tmp_path, "bn.json", ANTES_NOS),
        "--after-nodes", _escrever(tmp_path, "an.json", depois_nos or ANTES_NOS),
        "--before-texts", _escrever(tmp_path, "bt.json", ANTES_TXT),
        "--after-texts", _escrever(tmp_path, "at.json", depois_txt or ANTES_TXT),
    ]


def test_cli_aprova_quando_so_o_autorizado_mudou(tmp_path, capsys):
    import io
    import json

    from mastertool_bridge.cli import main

    depois = _textos(gvls__GVL_A__declaration="a" * 64,
                     programs__PRG_B__implementation="NOVO" + "b" * 60)
    saida_json = str(tmp_path / "uc.json")
    codigo = main(["check-unexpected-changes"] + _quatro(tmp_path, depois)
                  + ["--authorized", "programs:PRG_B:implementation",
                     "--output", saida_json])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert "[OK]" in saida
    assert json.loads(io.open(saida_json, encoding="utf-8").read())["clean"] is True


def test_cli_acusa_mudanca_nao_autorizada(tmp_path, capsys):
    from mastertool_bridge.cli import main

    depois = _textos(gvls__GVL_A__declaration="MUDOU" + "a" * 59,
                     programs__PRG_B__implementation="b" * 64)
    codigo = main(["check-unexpected-changes"] + _quatro(tmp_path, depois))
    saida = capsys.readouterr().out
    assert codigo == 2
    assert "[ACHADO]" in saida
    assert "gvls:GVL_A:declaration" in saida


def test_cli_diz_INCOMPARAVEL_quando_falta_artefato(tmp_path, capsys):
    from mastertool_bridge.cli import main

    argumentos = _quatro(tmp_path)
    argumentos[1] = str(tmp_path / "nao-existe.json")
    codigo = main(["check-unexpected-changes"] + argumentos)
    saida = capsys.readouterr().out
    assert codigo == 2
    assert "INCOMPARÁVEL" in saida
    assert "não é" in saida

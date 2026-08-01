"""Testes de `automation.generation_equivalence`.

O que estes testes protegem não é "o comparador roda": é que ele **reprova
quando deve**. Um comparador de determinismo que só sabe dizer "igual" é o pior
resultado possível, porque produz um selo de reprodutibilidade sem tê-la
verificado — e ninguém descobre até um cliente receber dois projetos diferentes
gerados da mesma especificação.

Por isso cada camada tem um par: uma prova de que o igual passa, e uma prova de
que a divergência daquela camada específica é PEGA.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastertool_bridge.automation.generation_equivalence import (
    NODE_SIGNATURE_FIELDS,
    VOLATILE_COMPLETION_FIELDS,
    compare_generations,
    missing_node_fields,
    tree_signature,
)

# --------------------------------------------------------------------------
# Fixtures: artefatos mínimos com a MESMA forma que os probes 37/38 gravam.
# --------------------------------------------------------------------------

TEXTOS = {
    "gvl_declaration": {"sha256": "aaa", "text": "VAR_GLOBAL\nEND_VAR", "error": None},
    "program_declaration": {"sha256": "bbb", "text": "PROGRAM P\nEND_VAR", "error": None},
    "program_implementation": {"sha256": "ccc", "text": "x := 1;", "error": None},
}

DIFF_ESTRUTURAL = {
    "added": [["GVL_AI_TESTE", "ffbfa93a"], ["PRG_AI_TESTE", "6f9dde40"]],
    "missing": [],
    "unexpected_additions": [],
    "baseline_node_count": 42,
    "observed_node_count": 44,
}


def _no(node_id: str, guid: str, nome: str = "Objeto") -> dict:
    return {
        "node_id": node_id,
        "parent_node_id": "root",
        "depth": 1,
        "index": 0,
        "name": nome,
        "type_guid": "639b491f",
        "child_count": 0,
        "object_guid": guid,
    }


def _escrever(raiz: Path, *, guids: list[str], textos=None, diff=None,
              completion=None, nos=None) -> Path:
    postsave = raiz / "postsave"
    postsave.mkdir(parents=True, exist_ok=True)
    if nos is None:
        nos = [_no(f"root/{i}", g, f"Obj{i}") for i, g in enumerate(guids)]

    def grava(caminho: Path, conteudo) -> None:
        caminho.write_text(
            json.dumps(conteudo, ensure_ascii=False), encoding="utf-8"
        )

    grava(postsave / "w1-4-persisted-texts.json",
          TEXTOS if textos is None else textos)
    grava(postsave / "w1-4-postsave-flat-nodes.json", {"nodes": nos})
    grava(postsave / "w1-4-structural-diff.json",
          DIFF_ESTRUTURAL if diff is None else diff)
    grava(raiz / "completion.json", completion or {
        "status": "saved_as",
        "generated_at": "2026-07-31T22:03:45",
        "plan_sha256": "b126e13",
        "output_project_path": r"C:\x\run-019\saida\W1-A5.project",
    })
    return raiz


@pytest.fixture()
def par(tmp_path: Path):
    """Duas gerações equivalentes e INDEPENDENTES (GUIDs distintos)."""
    a = _escrever(tmp_path / "a", guids=["g1", "g2"])
    b = _escrever(
        tmp_path / "b",
        guids=["g3", "g4"],
        completion={
            "status": "saved_as",
            "generated_at": "2026-07-31T23:44:55",
            "plan_sha256": "16fd54c",
            "output_project_path": r"C:\x\run-022\saida\W1-A5b.project",
        },
    )
    return a, b


# --------------------------------------------------------------------------
# O caso que a run-022 mediu de verdade
# --------------------------------------------------------------------------


def test_duas_geracoes_equivalentes_e_independentes_aprovam(par):
    r = compare_generations(*par)
    assert r.equivalent, r.divergences
    assert r.divergences == []
    assert sorted(r.layers_compared) == ["persisted_texts", "structural_diff", "tree"]


def test_o_volatil_difere_e_NAO_conta_para_o_veredito(par):
    """`generated_at`, `plan_sha256` e o caminho diferem entre quaisquer duas
    execuções. Contassem, nenhuma geração seria jamais determinista."""
    r = compare_generations(*par)
    assert r.equivalent
    assert sorted(r.volatile_differences) == sorted(VOLATILE_COMPLETION_FIELDS)


# --------------------------------------------------------------------------
# Camada 1 -- texto
# --------------------------------------------------------------------------


def test_texto_diferente_reprova(tmp_path: Path):
    a = _escrever(tmp_path / "a", guids=["g1"])
    outros = json.loads(json.dumps(TEXTOS))
    outros["program_implementation"]["sha256"] = "OUTRO"
    b = _escrever(tmp_path / "b", guids=["g2"], textos=outros)
    r = compare_generations(a, b)
    assert not r.equivalent
    assert any("program_implementation" in d for d in r.divergences)


def test_texto_A_MAIS_numa_das_geracoes_reprova(tmp_path: Path):
    """Um objeto extra numa geração é divergência mesmo que todos os textos
    comuns batam."""
    a = _escrever(tmp_path / "a", guids=["g1"])
    extra = json.loads(json.dumps(TEXTOS))
    extra["fb_declaration"] = {"sha256": "ddd", "text": "FUNCTION_BLOCK FB"}
    b = _escrever(tmp_path / "b", guids=["g2"], textos=extra)
    r = compare_generations(a, b)
    assert not r.equivalent
    assert any("conjunto de textos" in d for d in r.divergences)


# --------------------------------------------------------------------------
# Camada 2 -- árvore, e as duas armadilhas
# --------------------------------------------------------------------------


def test_arvore_com_no_a_mais_reprova(tmp_path: Path):
    a = _escrever(tmp_path / "a", guids=["g1", "g2"])
    b = _escrever(tmp_path / "b", guids=["g3", "g4", "g5"])
    r = compare_generations(a, b)
    assert not r.equivalent
    assert any("assinatura da árvore" in d for d in r.divergences)
    assert r.node_count == {"a": 2, "b": 3}


def test_no_renomeado_reprova_mesmo_com_a_mesma_contagem(tmp_path: Path):
    a = _escrever(tmp_path / "a", guids=["g1"])
    b = _escrever(tmp_path / "b", guids=["g2"],
                  nos=[_no("root/0", "g2", "NomeDiferente")])
    r = compare_generations(a, b)
    assert not r.equivalent
    assert r.node_count == {"a": 1, "b": 1}


def test_assinatura_montada_com_campos_ausentes_REPROVA(tmp_path: Path):
    """A armadilha central. Sem os campos, a assinatura vira uma lista de
    `None`s idênticos, que casa com qualquer coisa — e o comparador diria
    "determinista" sobre dois projetos diferentes."""
    pobre = [{"object_guid": "g1"}, {"object_guid": "g2"}]
    a = _escrever(tmp_path / "a", guids=[], nos=pobre)
    b = _escrever(tmp_path / "b", guids=[],
                  nos=[{"object_guid": "g3"}, {"object_guid": "g4"}])
    r = compare_generations(a, b)
    assert not r.equivalent
    assert any("campos de nó ausentes" in d for d in r.divergences)


def test_a_assinatura_pobre_de_fato_casaria__prova_da_armadilha():
    """Prova direta de que o guarda acima não é decorativo: sem ele, dois
    conjuntos de nós SEM os campos produzem assinaturas iguais."""
    pobres_a = [{"object_guid": "g1"}, {"object_guid": "g2"}]
    pobres_b = [{"object_guid": "g9"}, {"object_guid": "g8"}]
    assert tree_signature(pobres_a) == tree_signature(pobres_b)
    assert missing_node_fields(pobres_a) == list(NODE_SIGNATURE_FIELDS)


def test_guids_identicos_reprovam_por_nao_serem_geracoes_independentes(
    tmp_path: Path,
):
    """Comparar um diretório com ele mesmo dá "igual" em tudo — e não prova
    determinismo nenhum, prova que arquivo é igual a si próprio."""
    a = _escrever(tmp_path / "a", guids=["g1", "g2"])
    b = _escrever(tmp_path / "b", guids=["g1", "g2"])
    r = compare_generations(a, b)
    assert not r.equivalent
    assert any("não são independentes" in d for d in r.divergences)
    assert r.distinct_object_guids == 0


def test_geracoes_independentes_contam_os_guids_distintos(par):
    r = compare_generations(*par)
    assert r.distinct_object_guids == 2


# --------------------------------------------------------------------------
# Camada 3 -- diff estrutural
# --------------------------------------------------------------------------


def test_diff_estrutural_divergente_reprova(tmp_path: Path):
    a = _escrever(tmp_path / "a", guids=["g1"])
    outro = dict(DIFF_ESTRUTURAL, unexpected_additions=[["Intruso", "xxx"]])
    b = _escrever(tmp_path / "b", guids=["g2"], diff=outro)
    r = compare_generations(a, b)
    assert not r.equivalent
    assert any("unexpected_additions" in d for d in r.divergences)


# --------------------------------------------------------------------------
# Artefato ausente nunca vira aprovação
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "arquivo",
    [
        "postsave/w1-4-persisted-texts.json",
        "postsave/w1-4-postsave-flat-nodes.json",
        "postsave/w1-4-structural-diff.json",
    ],
)
def test_artefato_ausente_reprova_em_vez_de_ser_ignorado(tmp_path: Path, arquivo):
    """Camada que não pôde ser lida é camada que não foi verificada. Pular em
    silêncio transformaria "não medi" em "está igual"."""
    a = _escrever(tmp_path / "a", guids=["g1"])
    b = _escrever(tmp_path / "b", guids=["g2"])
    (Path(b) / arquivo).unlink()
    r = compare_generations(a, b)
    assert not r.equivalent
    assert len(r.layers_compared) == 2


def test_diretorio_inexistente_reprova(tmp_path: Path):
    a = _escrever(tmp_path / "a", guids=["g1"])
    r = compare_generations(a, tmp_path / "nao-existe")
    assert not r.equivalent
    assert r.layers_compared == []


def test_equivalent_e_derivado_de_divergences(par):
    """`equivalent` nunca é declarado: é propriedade de `divergences` estar
    vazio, pelo mesmo motivo que `authoring_eligible` é derivado em docs/36."""
    r = compare_generations(*par)
    assert r.equivalent is True
    r.divergences.append("qualquer coisa")
    assert r.equivalent is False
    assert r.to_dict()["equivalent"] is False


# =============================================================================
# o layout da FABRICA -- artefatos do probe 47
# =============================================================================

from mastertool_bridge.automation.generation_equivalence import (  # noqa: E402
    ALL_LAYOUTS,
    LAYOUT_FACTORY,
    LAYOUT_W1_4,
)

OBJETOS = [
    {"family": "gvls", "name": "GVL_F", "outcome": "verified",
     "texts": [{"field": "declaration", "outcome": "match",
                "sha256_observed": "aaa"}]},
    {"family": "programs", "name": "PRG_F", "outcome": "verified",
     "texts": [{"field": "declaration", "outcome": "match",
                "sha256_observed": "bbb"},
               {"field": "implementation", "outcome": "match",
                "sha256_observed": "ccc"}]},
]


def _escrever_fabrica(raiz: Path, *, guids: list[str], objetos=None) -> Path:
    sub = raiz / LAYOUT_FACTORY["subdir"]
    sub.mkdir(parents=True, exist_ok=True)
    nos = [_no(f"root/{i}", g, f"Obj{i}") for i, g in enumerate(guids)]
    (sub / LAYOUT_FACTORY["nodes"]).write_text(
        json.dumps({"nodes": nos}, ensure_ascii=False), encoding="utf-8")
    (sub / LAYOUT_FACTORY["texts"]).write_text(
        json.dumps({"objects": OBJETOS if objetos is None else objetos},
                   ensure_ascii=False), encoding="utf-8")
    return raiz


def test_layout_da_fabrica_compara_duas_geracoes(tmp_path: Path):
    a = _escrever_fabrica(tmp_path / "a", guids=["g1", "g2"])
    b = _escrever_fabrica(tmp_path / "b", guids=["g3", "g4"])
    r = compare_generations(a, b, layout=LAYOUT_FACTORY)
    assert r.equivalent, r.divergences
    assert r.layout == "factory"
    assert r.layers_compared == ["persisted_texts", "tree"]


def test_a_camada_ausente_e_DECLARADA_e_nao_some(tmp_path: Path):
    """A fabrica nao parte de arvore-base conhecida, entao `structural_diff`
    nao existe para ela. Soma-la a `layers_compared` faria o resultado alegar
    tres camadas tendo medido duas."""
    a = _escrever_fabrica(tmp_path / "a", guids=["g1"])
    b = _escrever_fabrica(tmp_path / "b", guids=["g2"])
    r = compare_generations(a, b, layout=LAYOUT_FACTORY)
    assert r.layers_absent == ["structural_diff"]
    assert "structural_diff" not in r.layers_compared
    assert r.to_dict()["layers_absent"] == ["structural_diff"]


def test_texto_divergente_no_layout_da_fabrica_reprova(tmp_path: Path):
    outros = json.loads(json.dumps(OBJETOS))
    outros[1]["texts"][1]["sha256_observed"] = "OUTRO"
    a = _escrever_fabrica(tmp_path / "a", guids=["g1"])
    b = _escrever_fabrica(tmp_path / "b", guids=["g2"], objetos=outros)
    r = compare_generations(a, b, layout=LAYOUT_FACTORY)
    assert not r.equivalent
    assert any("programs:PRG_F:implementation" in d for d in r.divergences)


def test_a_chave_do_texto_carrega_familia_nome_e_campo(tmp_path: Path):
    """Duas familias podem ter objeto de mesmo nome. Comparar so por campo
    misturaria os dois e um `mismatch` apareceria no lugar errado."""
    outros = json.loads(json.dumps(OBJETOS))
    outros[0]["name"] = "PRG_F"          # mesmo nome, familia diferente
    a = _escrever_fabrica(tmp_path / "a", guids=["g1"])
    b = _escrever_fabrica(tmp_path / "b", guids=["g2"], objetos=outros)
    r = compare_generations(a, b, layout=LAYOUT_FACTORY)
    assert not r.equivalent
    assert any("conjunto de textos difere" in d for d in r.divergences)


def test_o_layout_e_EXPLICITO_e_o_default_e_o_de_w1_4(tmp_path: Path):
    """Adivinhar o layout por qual arquivo existe escolheria em silencio, e
    escolher errado compararia camadas que nao sao as mesmas."""
    a = _escrever_fabrica(tmp_path / "a", guids=["g1"])
    b = _escrever_fabrica(tmp_path / "b", guids=["g2"])
    # Sem `layout`, ele procura os artefatos de W1.4 -- que nao existem aqui.
    r = compare_generations(a, b)
    assert not r.equivalent
    assert r.layout == "w1-4"


def test_todo_layout_declara_as_mesmas_chaves():
    """Um layout com chave a menos quebraria no meio da comparacao, depois de
    ja ter escrito parte do resultado."""
    esperadas = {"name", "subdir", "texts", "nodes", "structural_diff",
                 "texts_shape"}
    for layout in ALL_LAYOUTS:
        assert set(layout) == esperadas, layout["name"]
        assert layout["texts_shape"] in ("mapping", "objects"), layout["name"]
    assert len({l["name"] for l in ALL_LAYOUTS}) == len(ALL_LAYOUTS)
    assert LAYOUT_W1_4["structural_diff"] is not None
    assert LAYOUT_FACTORY["structural_diff"] is None

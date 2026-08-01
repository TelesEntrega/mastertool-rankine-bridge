"""Equivalência entre duas gerações da MESMA especificação de autoria.

Responde à pergunta que ficou aberta na seção Limites de `docs/33`, `docs/37`
e `docs/39`: *a mesma especificação, executada duas vezes sobre cópias novas do
mesmo template, produz o mesmo projeto?* Sem essa resposta a fábrica não promete
resultado reprodutível, e um diff entre duas gerações não distingue "mudou
porque a spec mudou" de "mudou porque a ferramenta varia".

Funções puras sobre caminhos de disco — nenhuma delas toca o MasterTool. Toda a
entrada são artefatos já gravados pelos probes 37/38.

## Por que o `.project` inteiro NÃO é o critério

O arquivo carrega GUID de objeto e timestamp, sorteados a cada geração. Comparar
bytes reprovaria **sempre**, e um critério que reprova sempre não distingue
projeto igual de projeto diferente — não mede nada, só parece rigoroso.

O critério é o **conteúdo**, em três camadas independentes:

1. **Texto relido do disco** (`postsave`), não o texto que a autoria tinha em
   memória. Comparar a memória de quem escreveu com a memória de quem escreveu
   provaria apenas que a variável não mudou entre duas linhas.
2. **Árvore de objetos** persistida — posição, nome e tipo de cada nó.
3. **Diff estrutural** de cada geração contra o **próprio** preflight.

Divergência em qualquer camada reprova.

## Duas armadilhas que o módulo fecha explicitamente

**Assinatura vazia.** Montada com nomes de campo errados, a assinatura da
árvore vira uma lista de `None`s idênticos, que casa com qualquer coisa. Os
campos são por isso verificados como presentes (`MISSING_NODE_FIELDS`), e a
ausência **reprova** em vez de passar em silêncio. Um comparador que passa à toa
é pior que comparador nenhum, porque parece evidência.

**Gerações não independentes.** Se os `object_guid` das duas árvores forem
idênticos, os artefatos vieram da mesma execução (diretório repetido, cópia),
e a igualdade é tautologia. O módulo exige a contraprova de que ao menos um
GUID difere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Nome dos artefatos, fixados pelos probes 37 (modo `postsave`) e 38.
PERSISTED_TEXTS_FILENAME = "w1-4-persisted-texts.json"
POSTSAVE_FLAT_NODES_FILENAME = "w1-4-postsave-flat-nodes.json"
STRUCTURAL_DIFF_FILENAME = "w1-4-structural-diff.json"
POSTSAVE_DIRNAME = "postsave"

# --- layouts de artefato ----------------------------------------------------
#
# Duas cadeias produzem evidência comparável, com nomes de arquivo diferentes:
# a de W1.4 (probes 37/38) e a da FÁBRICA (probe 47). O layout é PASSADO pelo
# chamador, e nunca adivinhado a partir de qual arquivo existe — adivinhar
# escolheria em silêncio, e escolher errado compararia camadas que não são as
# mesmas.
#
# A fábrica não tem `structural_diff`: ela não parte de uma árvore-base
# conhecida, e sim de um template que a spec nomeia. A ausência é DECLARADA
# aqui (`structural_diff: None`) em vez de a camada sumir sem explicação.
LAYOUT_W1_4 = {
    "name": "w1-4",
    "subdir": POSTSAVE_DIRNAME,
    "texts": PERSISTED_TEXTS_FILENAME,
    "nodes": POSTSAVE_FLAT_NODES_FILENAME,
    "structural_diff": STRUCTURAL_DIFF_FILENAME,
    "texts_shape": "mapping",
}

LAYOUT_FACTORY = {
    "name": "factory",
    "subdir": "verificacao",
    "texts": "factory-verify-texts.json",
    "nodes": "factory-verify-flat-nodes.json",
    "structural_diff": None,
    "texts_shape": "objects",
}

ALL_LAYOUTS = (LAYOUT_W1_4, LAYOUT_FACTORY)

# Campos de um nó que carregam significado de engenharia. `object_guid` fica
# FORA de propósito: é sorteado a cada criação. Ficasse dentro, a comparação
# reprovaria sempre.
NODE_SIGNATURE_FIELDS = (
    "node_id",
    "parent_node_id",
    "depth",
    "index",
    "name",
    "type_guid",
    "child_count",
)

# Campos do artefato de conclusão que PODEM diferir sem significar nada:
# instante da geração, hash do plano (que difere só pelos caminhos de saída) e
# o próprio caminho.
VOLATILE_COMPLETION_FIELDS = (
    "generated_at",
    "plan_sha256",
    "output_project_path",
)


@dataclass
class GenerationEquivalenceResult:
    """Veredito da comparação. `equivalent` é DERIVADO de `divergences` estar
    vazio — nunca declarado por quem monta o resultado."""

    divergences: list[str] = field(default_factory=list)
    layers_compared: list[str] = field(default_factory=list)
    layers_absent: list[str] = field(default_factory=list)
    layout: str = "w1-4"
    node_count: dict[str, int] = field(default_factory=dict)
    distinct_object_guids: int = 0
    volatile_differences: list[str] = field(default_factory=list)

    @property
    def equivalent(self) -> bool:
        return not self.divergences

    def to_dict(self) -> dict[str, Any]:
        return {
            "equivalent": self.equivalent,
            "divergences": list(self.divergences),
            "layers_compared": list(self.layers_compared),
            "layers_absent": list(self.layers_absent),
            "layout": self.layout,
            "node_count": dict(self.node_count),
            "distinct_object_guids": self.distinct_object_guids,
            "volatile_differences": list(self.volatile_differences),
        }


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _nodes_of(flat: Any) -> list[dict] | None:
    """Os probes gravam ora `{"nodes": [...]}`, ora a lista pelada. Aceitar as
    duas formas é leitura de artefato, não permissividade: o formato é do probe,
    e adivinhar aqui seria pior que aceitar os dois explicitamente."""
    if isinstance(flat, dict):
        flat = flat.get("nodes")
    if not isinstance(flat, list):
        return None
    return [n for n in flat if isinstance(n, dict)]


def missing_node_fields(nodes: list[dict]) -> list[str]:
    """Campos de `NODE_SIGNATURE_FIELDS` ausentes no artefato.

    Existe para que uma assinatura montada com nomes errados REPROVE, em vez de
    virar uma lista de `None`s que casa com qualquer coisa.
    """
    if not nodes:
        return list(NODE_SIGNATURE_FIELDS)
    presentes = set(nodes[0].keys())
    return [c for c in NODE_SIGNATURE_FIELDS if c not in presentes]


def tree_signature(nodes: list[dict]) -> list[tuple]:
    """Posição, nome e tipo de cada nó, em ordem estável."""
    return sorted(
        (tuple(n.get(campo) for campo in NODE_SIGNATURE_FIELDS) for n in nodes),
        key=str,
    )


def object_guids(nodes: list[dict]) -> list[str]:
    return sorted(str(n.get("object_guid")) for n in nodes)


def _texts_by_key(payload: Any, shape: str) -> dict[str, str | None] | None:
    """Normaliza os dois formatos de artefato de texto para `chave -> sha256`.

    `mapping`  (probes 37): `{"gvl_declaration": {"sha256": ...}, ...}`
    `objects`  (probe 47):  `{"objects": [{"family", "name", "texts": [...]}]}`

    A normalização acontece AQUI, e não no comparador, para que a comparação
    tenha uma forma só. Duas formas no ponto da comparação seriam dois
    caminhos de código com uma asserção cada — e o segundo envelheceria.
    """
    if shape == "mapping":
        if not isinstance(payload, dict):
            return None
        saida: dict[str, str | None] = {}
        for chave, valor in payload.items():
            if isinstance(valor, dict) and ("sha256" in valor or "text" in valor):
                saida[chave] = valor.get("sha256")
        return saida
    if shape == "objects":
        if not isinstance(payload, dict):
            return None
        objetos = payload.get("objects")
        if not isinstance(objetos, list):
            return None
        saida = {}
        for objeto in objetos:
            if not isinstance(objeto, dict):
                continue
            for texto in objeto.get("texts") or []:
                if not isinstance(texto, dict):
                    continue
                chave = "%s:%s:%s" % (objeto.get("family"), objeto.get("name"),
                                      texto.get("field"))
                saida[chave] = texto.get("sha256_observed")
        return saida
    return None


def compare_generations(
    artifacts_a: Path | str, artifacts_b: Path | str, layout: dict | None = None
) -> GenerationEquivalenceResult:
    """Compara dois diretórios de artefatos nas camadas que o layout declara.

    `layout` é EXPLÍCITO e nunca adivinhado a partir de qual arquivo existe:
    adivinhar escolheria em silêncio, e escolher errado compararia camadas que
    não são as mesmas. O default é `LAYOUT_W1_4`, que era o único quando esta
    função nasceu.
    """
    layout = layout or LAYOUT_W1_4
    a, b = Path(artifacts_a), Path(artifacts_b)
    resultado = GenerationEquivalenceResult()
    resultado.layout = layout["name"]
    sub = layout["subdir"]

    # --- camada 1: os textos RELIDOS do projeto salvo ------------------------
    ta = _texts_by_key(_read_json(a / sub / layout["texts"]),
                       layout["texts_shape"])
    tb = _texts_by_key(_read_json(b / sub / layout["texts"]),
                       layout["texts_shape"])
    if ta is None or tb is None or not ta or not tb:
        resultado.divergences.append("textos persistidos ausentes ou ilegíveis")
    else:
        resultado.layers_compared.append("persisted_texts")
        if sorted(ta) != sorted(tb):
            resultado.divergences.append(
                f"conjunto de textos difere: {sorted(ta)} != {sorted(tb)}"
            )
        for chave in sorted(set(ta) | set(tb)):
            # O SHA é o critério, e não o texto: o texto entra no diagnóstico,
            # o hash entra no veredito.
            if ta.get(chave) != tb.get(chave):
                resultado.divergences.append(
                    f"{chave}: sha256 {ta.get(chave)} != {tb.get(chave)}"
                )

    # --- camada 2: a árvore persistida --------------------------------------
    fa = _nodes_of(_read_json(a / sub / layout["nodes"]))
    fb = _nodes_of(_read_json(b / sub / layout["nodes"]))
    if fa is None or fb is None:
        resultado.divergences.append("árvore persistida ausente ou ilegível")
    else:
        resultado.layers_compared.append("tree")
        resultado.node_count = {"a": len(fa), "b": len(fb)}
        ausentes = sorted(set(missing_node_fields(fa)) | set(missing_node_fields(fb)))
        if ausentes:
            # Reprovar, e não seguir: sem esses campos a assinatura não
            # distingue nada, e um "igual" aqui seria falso conforto.
            resultado.divergences.append(
                f"campos de nó ausentes no artefato: {ausentes}"
            )
        elif tree_signature(fa) != tree_signature(fb):
            resultado.divergences.append("assinatura da árvore difere")

        ga, gb = object_guids(fa), object_guids(fb)
        resultado.distinct_object_guids = len(set(ga) ^ set(gb)) // 2
        if ga and ga == gb:
            resultado.divergences.append(
                "GUIDs de objeto idênticos: as duas gerações não são "
                "independentes, e a comparação não prova nada"
            )

    # --- camada 3: o diff estrutural contra o PRÓPRIO preflight -------------
    nome_diff = layout["structural_diff"]
    if nome_diff is None:
        # A fábrica não parte de árvore-base conhecida: a camada NÃO EXISTE
        # para este layout. Registrada como ausente, e não como comparada —
        # somá-la a `layers_compared` faria o resultado alegar três camadas
        # tendo medido duas.
        resultado.layers_absent.append("structural_diff")
    else:
        da = _read_json(a / sub / nome_diff)
        db = _read_json(b / sub / nome_diff)
        if not isinstance(da, dict) or not isinstance(db, dict):
            resultado.divergences.append("diff estrutural ausente ou ilegível")
        else:
            resultado.layers_compared.append("structural_diff")
            for chave in sorted(set(da) | set(db)):
                if da.get(chave) != db.get(chave):
                    resultado.divergences.append(
                        f"diff estrutural: {chave} difere")

    # --- volátil: registrado, nunca somado ao veredito ----------------------
    ca = _read_json(a / "completion.json")
    cb = _read_json(b / "completion.json")
    if isinstance(ca, dict) and isinstance(cb, dict):
        for chave in VOLATILE_COMPLETION_FIELDS:
            if ca.get(chave) != cb.get(chave):
                resultado.volatile_differences.append(chave)

    return resultado

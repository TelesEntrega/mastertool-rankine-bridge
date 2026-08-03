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
from collections.abc import Sequence
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
#
# `completion` é DECLARADO por layout, e não fixado como "completion.json".
# ACHADO que motivou isto: a cadeia da fábrica grava
# `execution-completion.json` (probe 46, `ARTIFACT_NAMES`), e o nome fixo
# encontrava esse arquivo em NENHUM lote real — a distribuição de campos
# voláteis saía vazia e ninguém era avisado, porque campo volátil ausente não
# reprova. Um relatório diria "0 campos voláteis observados" sobre um lote que
# tem três.
LAYOUT_W1_4 = {
    "name": "w1-4",
    "subdir": POSTSAVE_DIRNAME,
    "texts": PERSISTED_TEXTS_FILENAME,
    "nodes": POSTSAVE_FLAT_NODES_FILENAME,
    "structural_diff": STRUCTURAL_DIFF_FILENAME,
    "texts_shape": "mapping",
    "completion": "completion.json",
}

LAYOUT_FACTORY = {
    "name": "factory",
    "subdir": "verificacao",
    "texts": "factory-verify-texts.json",
    "nodes": "factory-verify-flat-nodes.json",
    "structural_diff": None,
    "texts_shape": "objects",
    # Caminho RELATIVO ao diretório de artefatos, e com subdiretório: a árvore
    # real de `run-034` (medida, não suposta) é
    # `artefatos/{authoring-plan.json, build/, execucao/, verificacao/}`, e a
    # conclusão do executor fica em `execucao/`. A primeira correção deste
    # nome acertou o arquivo e errou a pasta — e o sintoma seria o mesmo:
    # distribuição de voláteis vazia, sem reprovar nada.
    "completion": "execucao/execution-completion.json",
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


@dataclass
class RepeatabilityResult:
    """Veredito de N gerações — o que a fase R1 pede, e que a comparação
    pareada não conseguia expressar.

    POR QUE NÃO BASTA COMPARAR TODAS CONTRA UMA REFERÊNCIA
    ======================================================
    `compare_generations` mistura DUAS relações de natureza oposta:

    * as camadas de equivalência (textos, assinatura da árvore, diff
      estrutural) são igualdade de valor canônico. Igualdade é transitiva:
      se A≡R e B≡R, então A≡B. Comparar cada geração contra uma referência
      basta, e comparar todos contra todos só gastaria tempo;
    * a exigência de **independência** — GUIDs de objeto distintos — é o
      contrário disso. Ela é ANTI-reflexiva (uma geração comparada consigo
      mesma tem de reprovar) e **não é transitiva**: A≠B e B≠C não implicam
      A≠C. Verificá-la só contra a referência deixaria passar duas gerações
      não-referência que nasceram com os mesmos GUIDs — que é exatamente a
      forma como "dez execuções" poderiam ser, na verdade, uma execução
      copiada nove vezes.

    Por isso este resultado usa referência para equivalência e **todos os
    pares** para independência. Com n=10 são 45 pares, custo irrelevante
    perto de errar o veredito da fase.
    """

    layout: str = "w1-4"
    generations: list[str] = field(default_factory=list)
    reference: str | None = None
    minimum_required: int = 0
    per_generation: list[dict] = field(default_factory=list)
    independence_violations: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    # Distribuição dos campos classificados como voláteis PERMITIDOS, com os
    # valores observados em cada geração. Estar na allowlist dispensa o campo
    # de reprovar — não dispensa de aparecer. Um campo volátil que assume dez
    # valores distintos em dez execuções é o esperado; o mesmo campo assumindo
    # dois valores que se alternam é um achado que o veredito binário
    # esconderia.
    volatile_distribution: list[dict] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.generations)

    @property
    def equivalent_count(self) -> int:
        return sum(1 for g in self.per_generation if g["equivalent"])

    @property
    def all_equivalent(self) -> bool:
        return bool(self.per_generation) and self.equivalent_count == len(
            self.per_generation)

    @property
    def meets_minimum(self) -> bool:
        return self.count >= self.minimum_required

    @property
    def repeatable(self) -> bool:
        """DERIVADO, e nunca declarado. As três condições são independentes:
        dez execuções equivalentes mas não independentes não provam nada; dez
        independentes e divergentes provam o contrário; e duas de cada não
        chegam ao piso da norma."""
        return (
            not self.problems
            and self.meets_minimum
            and self.all_equivalent
            and not self.independence_violations
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "repeatable": self.repeatable,
            "layout": self.layout,
            "count": self.count,
            "minimum_required": self.minimum_required,
            "meets_minimum": self.meets_minimum,
            "reference": self.reference,
            "generations": list(self.generations),
            "equivalent_count": self.equivalent_count,
            "all_equivalent": self.all_equivalent,
            "per_generation": [dict(g) for g in self.per_generation],
            "independence_violations": list(self.independence_violations),
            "volatile_distribution": [dict(v) for v in self.volatile_distribution],
            "problems": list(self.problems),
        }


def _guids_of(artifacts: Path, layout: dict) -> list[str] | None:
    nodes = _nodes_of(_read_json(artifacts / layout["subdir"] / layout["nodes"]))
    if nodes is None:
        return None
    return object_guids(nodes)


def compare_many(
    artifact_dirs: Sequence[Path | str],
    layout: dict | None = None,
    minimum_required: int | None = None,
) -> RepeatabilityResult:
    """Veredito de repetibilidade sobre N diretórios de artefatos.

    `minimum_required` vem, por padrão, do mesmo lugar que o gate do Template
    Profile lê: `MIN_INDEPENDENT_RUNS["repeatable"]`. Uma segunda constante
    aqui poderia divergir daquela, e duas versões do mesmo número são uma a
    mais do que a norma tem.
    """
    layout = layout or LAYOUT_W1_4
    if minimum_required is None:
        # Import local para não criar dependência de importação em tempo de
        # módulo entre `automation` e `templates` — o número é normativo, o
        # acoplamento não precisa ser estrutural.
        from mastertool_bridge.templates.profile import MIN_INDEPENDENT_RUNS

        minimum_required = MIN_INDEPENDENT_RUNS["repeatable"]

    caminhos = [Path(d) for d in artifact_dirs]
    resultado = RepeatabilityResult(
        layout=layout["name"],
        generations=[str(c) for c in caminhos],
        minimum_required=minimum_required,
    )

    if len(caminhos) < 2:
        resultado.problems.append(
            "repetibilidade exige ao menos duas gerações para comparar; "
            f"recebidas {len(caminhos)}")
        return resultado

    duplicados = sorted({str(c) for c in caminhos
                         if [str(x) for x in caminhos].count(str(c)) > 1})
    if duplicados:
        # Mesmo diretório duas vezes não é geração repetida: é o mesmo
        # artefato contado duas vezes, e passaria em toda camada de igualdade.
        resultado.problems.append(
            "diretório repetido na lista de gerações: "
            + ", ".join(duplicados))
        return resultado

    referencia = caminhos[0]
    resultado.reference = str(referencia)

    for caminho in caminhos[1:]:
        comparacao = compare_generations(referencia, caminho, layout)
        resultado.per_generation.append({
            "generation": str(caminho),
            "equivalent": comparacao.equivalent,
            "divergences": list(comparacao.divergences),
            "layers_compared": list(comparacao.layers_compared),
            "layers_absent": list(comparacao.layers_absent),
            "volatile_differences": list(comparacao.volatile_differences),
        })

    # A referência entra no relatório como equivalente a si mesma POR
    # DEFINIÇÃO, e não por medição — comparar A com A dispararia a regra de
    # independência e produziria uma divergência que não significa nada.
    resultado.per_generation.insert(0, {
        "generation": str(referencia),
        "equivalent": True,
        "divergences": [],
        "layers_compared": [],
        "layers_absent": [],
        "volatile_differences": [],
        "note": "referência: equivalente a si mesma por definição, não por medição",
    })

    # --- independência: TODOS os pares --------------------------------------
    guids: dict[str, list[str] | None] = {
        str(c): _guids_of(c, layout) for c in caminhos}
    ilegiveis = sorted(k for k, v in guids.items() if v is None)
    if ilegiveis:
        resultado.problems.append(
            "árvore ausente ou ilegível, independência não verificável em: "
            + ", ".join(ilegiveis))
    for i in range(len(caminhos)):
        for j in range(i + 1, len(caminhos)):
            a, b = str(caminhos[i]), str(caminhos[j])
            ga, gb = guids.get(a), guids.get(b)
            if not ga or not gb:
                continue
            if ga == gb:
                resultado.independence_violations.append(
                    f"{a} e {b} têm os mesmos GUIDs de objeto: não são "
                    "execuções independentes")

    # --- distribuição do que é volátil PERMITIDO ----------------------------
    #
    # A lista de campos é LITERAL (`VOLATILE_COMPLETION_FIELDS`), nunca um
    # padrão que remova recursivamente qualquer chave chamada `id`, `guid` ou
    # `time`: uma allowlist por forma do nome esconderia campo que ninguém
    # decidiu excluir.
    nome_conclusao = layout.get("completion", "completion.json")
    conclusoes = {str(c): _read_json(c / nome_conclusao) for c in caminhos}
    for campo in VOLATILE_COMPLETION_FIELDS:
        valores: dict[str, Any] = {}
        for caminho, conclusao in conclusoes.items():
            if isinstance(conclusao, dict) and campo in conclusao:
                valores[caminho] = conclusao[campo]
        if not valores:
            continue
        distintos = {json.dumps(v, sort_keys=True, ensure_ascii=False)
                     for v in valores.values()}
        resultado.volatile_distribution.append({
            "field": campo,
            "classification": "allowed_volatile",
            "distinct_values": len(distintos),
            "observed_in": len(valores),
            "runs": valores,
        })

    return resultado


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
    nome_conclusao = layout.get("completion", "completion.json")
    ca = _read_json(a / nome_conclusao)
    cb = _read_json(b / nome_conclusao)
    if isinstance(ca, dict) and isinstance(cb, dict):
        for chave in VOLATILE_COMPLETION_FIELDS:
            if ca.get(chave) != cb.get(chave):
                resultado.volatile_differences.append(chave)

    return resultado

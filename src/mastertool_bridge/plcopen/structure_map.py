"""Mapa ESTRUTURAL de um PLCopen XML de POU Ladder — o schema real, observado.

Este módulo não interpreta lógica. Ele não decide o que é leitura, escrita ou
condição booleana, e não converte redes em expressões. Ele responde às
perguntas que precisam estar respondidas **antes** de existir um modelo
canônico: como identificar elementos, como identificar pinos, como
reconstruir conexões, como separar redes, e como distinguir variáveis,
contatos, bobinas e blocos de função.

Escrito depois de inspecionar um export real (MasterTool IEC XE 3.63,
namespace `tc6_0200`) — e deliberadamente descritivo, não normativo: onde o
arquivo real diverge do que o padrão PLCopen sugeriria, o mapa registra **o
que está lá**, com diagnóstico, em vez de normalizar para o esperado.

Achados que moldaram o desenho, todos verificáveis nos artefatos:

1. **Não existe `<network>`.** Todos os elementos são irmãos diretos de
   `<LD>`. Redes precisam ser reconstruídas.
2. **Posição gráfica é inútil**: todas as 42 `<position>` do arquivo real são
   `x=0 y=0`. Qualquer estratégia que dependa de coordenadas falha aqui.
3. **Fronteira de rede é extensão do fornecedor**: `<vendorElement>` com
   `addData/data[@name=".../fbdelementtype"]` contendo `networktitle`.
4. **Paralelo também é extensão**: `<vendorElement>` com
   `data[@name=".../ldparallelbranch"]` → `<ParallelBranch>` com
   `<BranchInput>` (entrada comum) e `<BranchTrees><Tree>` (as pernas).
5. **`CallType` separa operador de bloco de função** — e `instanceName` só
   aparece no segundo.
6. **`formalParameter` em `<connection>` NÃO é confiável como nome do pino de
   origem**: no arquivo real, uma bobina referencia um bloco `EQ` com
   `formalParameter` igual ao NOME DA PRÓPRIA VARIÁVEL da bobina, onde
   outra bobina usa `formalParameter="Out1"` (o pino real). Registrado como
   anomalia, nunca "corrigido" em silêncio.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Versão do contrato DESTE artefato (mapa estrutural), inteiro. Constante
# própria de propósito: o mapa estrutural evolui junto com o schema real
# observado do PLCopen, num ritmo que não é o do modelo canônico nem o dos
# artefatos de run. Ver `docs/19-contratos-de-execucao.md`, seção 7 — não
# existe versão global de schema neste projeto.
STRUCTURE_MAP_SCHEMA_VERSION = 1

VENDOR_ELEMENT_TYPE_DATA = "fbdelementtype"
VENDOR_PARALLEL_BRANCH_DATA = "ldparallelbranch"
VENDOR_CALL_TYPE_DATA = "fbdcalltype"

NETWORK_TITLE_MARKER = "networktitle"

# Elementos Ladder do padrão que o mapa reconhece. O que não estiver aqui vai
# para `unknown-elements.json` — silêncio sobre elemento desconhecido é como
# um parser começa a mentir.
KNOWN_LD_ELEMENTS = (
    "contact", "coil", "block", "inVariable", "outVariable", "inOutVariable",
    "leftPowerRail", "rightPowerRail", "connector", "continuation",
    "jump", "label", "return", "comment", "vendorElement",
)


def _ln(element: ET.Element) -> str:
    """Nome local, sem namespace."""
    tag = element.tag
    return tag.split("}", 1)[1] if "}" in tag else tag


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _ln(child) == name:
            return child.text
    return None


def _vendor_data(element: ET.Element, suffix: str) -> ET.Element | None:
    """Localiza `addData/data` cujo `@name` termina no sufixo dado. A
    comparação é por sufixo porque o prefixo é uma URL do fornecedor que pode
    mudar de versão sem mudar o significado."""
    for data in element.iter():
        if _ln(data) != "data":
            continue
        name = data.get("name") or ""
        if name.rstrip("/").endswith(suffix):
            return data
    return None


@dataclass
class LadderElement:
    local_id: str | None
    kind: str
    attributes: dict
    variable: str | None = None
    expression: str | None = None
    negated: bool | None = None
    edge: str | None = None
    storage: str | None = None
    type_name: str | None = None
    instance_name: str | None = None
    call_type: str | None = None
    vendor_element_type: str | None = None
    input_pins: list = field(default_factory=list)
    output_pins: list = field(default_factory=list)
    document_order: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "local_id": self.local_id,
            "kind": self.kind,
            "document_order": self.document_order,
            "attributes": self.attributes,
            "variable": self.variable,
            "expression": self.expression,
            "negated": self.negated,
            "edge": self.edge,
            "storage": self.storage,
            "type_name": self.type_name,
            "instance_name": self.instance_name,
            "call_type": self.call_type,
            "vendor_element_type": self.vendor_element_type,
            "input_pins": self.input_pins,
            "output_pins": self.output_pins,
        }


@dataclass
class Connection:
    """Uma aresta. A referência no XML aponta do DESTINO para a ORIGEM
    (`connectionPointIn/connection/@refLocalId`), então `source_*` é o que o
    destino declara consumir."""

    target_local_id: str | None
    target_kind: str
    target_pin: str | None
    source_local_id: str | None
    source_formal_parameter: str | None
    via: str = "connectionPointIn"

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_local_id": self.target_local_id,
            "target_kind": self.target_kind,
            "target_pin": self.target_pin,
            "source_local_id": self.source_local_id,
            "source_formal_parameter": self.source_formal_parameter,
            "via": self.via,
        }


@dataclass
class ParallelBranch:
    owner_local_id: str | None
    mode: str | None
    input_refs: list
    tree_refs: list

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_local_id": self.owner_local_id,
            "mode": self.mode,
            "input_refs": self.input_refs,
            "tree_refs": self.tree_refs,
        }


class StructureMapError(Exception):
    """XML sem POU Ladder analisável."""


def _collect_pins(block: ET.Element) -> tuple[list, list]:
    """Pinos de um `<block>`: `inputVariables`/`outputVariables`/
    `inOutVariables`, cada `<variable formalParameter="...">`. O pino É o
    `formalParameter` — é assim que blocos identificam entradas e saídas."""
    inputs, outputs = [], []
    for group in block:
        group_name = _ln(group)
        if group_name not in ("inputVariables", "outputVariables", "inOutVariables"):
            continue
        for variable in group:
            if _ln(variable) != "variable":
                continue
            pin = {
                "formal_parameter": variable.get("formalParameter"),
                "group": group_name,
                "connected": any(_ln(c) == "connectionPointIn" for c in variable),
            }
            if group_name == "outputVariables":
                outputs.append(pin)
            else:
                inputs.append(pin)
    return inputs, outputs


def _parse_element(element: ET.Element, order: int) -> LadderElement:
    kind = _ln(element)
    attributes = dict(element.attrib)
    mapped = LadderElement(
        local_id=element.get("localId"),
        kind=kind,
        attributes={k: v for k, v in attributes.items() if k != "localId"},
        document_order=order,
    )

    negated = element.get("negated")
    if negated is not None:
        mapped.negated = (negated == "true")
    mapped.edge = element.get("edge")
    mapped.storage = element.get("storage")
    mapped.type_name = element.get("typeName")
    mapped.instance_name = element.get("instanceName")

    # Onde o NOME da variável vive muda conforme o elemento: contato e bobina
    # usam <variable>, inVariable usa <expression>. Tratar os dois como o
    # mesmo campo apagaria a distinção que o próprio schema faz.
    mapped.variable = _child_text(element, "variable")
    mapped.expression = _child_text(element, "expression")

    if kind == "block":
        call_type_data = _vendor_data(element, VENDOR_CALL_TYPE_DATA)
        if call_type_data is not None:
            for child in call_type_data.iter():
                if _ln(child) == "CallType":
                    mapped.call_type = child.text
        mapped.input_pins, mapped.output_pins = _collect_pins(element)

    if kind == "vendorElement":
        element_type_data = _vendor_data(element, VENDOR_ELEMENT_TYPE_DATA)
        if element_type_data is not None:
            for child in element_type_data.iter():
                if _ln(child) == "ElementType":
                    mapped.vendor_element_type = child.text

    return mapped


def _collect_connections(element: ET.Element) -> list[Connection]:
    """Percorre os `connectionPointIn` DESTE elemento, atribuindo o pino
    correto quando o ponto pertence a um `<variable formalParameter>`."""
    kind = _ln(element)
    local_id = element.get("localId")
    connections: list[Connection] = []

    def _walk(node: ET.Element, pin: str | None) -> None:
        for child in node:
            child_kind = _ln(child)
            if child_kind == "variable":
                _walk(child, child.get("formalParameter"))
            elif child_kind == "connectionPointIn":
                for conn in child:
                    if _ln(conn) != "connection":
                        continue
                    connections.append(Connection(
                        target_local_id=local_id,
                        target_kind=kind,
                        target_pin=pin,
                        source_local_id=conn.get("refLocalId"),
                        source_formal_parameter=conn.get("formalParameter"),
                    ))
            elif child_kind in ("inputVariables", "outputVariables",
                                "inOutVariables"):
                _walk(child, pin)

    _walk(element, None)
    return connections


def _collect_parallel_branches(element: ET.Element) -> list[ParallelBranch]:
    data = _vendor_data(element, VENDOR_PARALLEL_BRANCH_DATA)
    if data is None:
        return []
    branches = []
    for branch in data.iter():
        if _ln(branch) != "ParallelBranch":
            continue
        input_refs, tree_refs = [], []
        for part in branch:
            part_kind = _ln(part)
            refs = [
                {"ref_local_id": c.get("refLocalId"),
                 "formal_parameter": c.get("formalParameter")}
                for c in part.iter() if _ln(c) == "connection"
            ]
            if part_kind == "BranchInput":
                input_refs.extend(refs)
            elif part_kind == "BranchTrees":
                tree_refs.extend(refs)
        branches.append(ParallelBranch(
            owner_local_id=element.get("localId"),
            mode=branch.get("mode"),
            input_refs=input_refs,
            tree_refs=tree_refs))
    return branches


def _segment_networks(elements: list[LadderElement]) -> list[dict]:
    """Redes reconstruídas pelos marcadores `networktitle`, na ordem do
    documento. Não há `<network>` no XML e a posição gráfica é inútil (todas
    as coordenadas do export real são zero), então o marcador do fornecedor é
    o único sinal explícito de fronteira disponível.

    Devolve segmentos com os `local_id` que caem em cada um. NÃO afirma que
    cada segmento é um circuito conexo — isso é conclusão sobre topologia, e
    fica para quem for construir o modelo canônico."""
    networks: list[dict] = []
    current: dict | None = None
    for element in elements:
        is_title = (element.kind == "vendorElement"
                    and element.vendor_element_type == NETWORK_TITLE_MARKER)
        if is_title:
            current = {
                "index": sum(1 for n in networks if n["title_marker_local_id"]),
                "title_marker_local_id": element.local_id,
                "member_local_ids": [],
            }
            networks.append(current)
            continue
        if current is None:
            # Elementos antes do primeiro marcador (tipicamente o trilho
            # esquerdo) ficam num segmento de prólogo explícito, nunca
            # silenciosamente colados na primeira rede.
            current = {"index": None, "title_marker_local_id": None,
                       "member_local_ids": [], "prologue": True}
            networks.append(current)
        if element.local_id is not None:
            current["member_local_ids"].append(element.local_id)
    return networks


def _connected_components(elements: list[LadderElement],
                          connections: list[Connection]) -> list[list[str]]:
    """Componentes conexos por `localId`, ignorando direção. É topologia
    pura — não diz nada sobre lógica booleana."""
    adjacency: dict[str, set] = {
        e.local_id: set() for e in elements if e.local_id is not None}
    for conn in connections:
        a, b = conn.target_local_id, conn.source_local_id
        if a in adjacency and b in adjacency:
            adjacency[a].add(b)
            adjacency[b].add(a)

    seen: set = set()
    components: list[list[str]] = []
    for node in adjacency:
        if node in seen:
            continue
        stack, group = [node], []
        seen.add(node)
        while stack:
            current = stack.pop()
            group.append(current)
            for neighbour in adjacency[current]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        components.append(sorted(group, key=lambda v: (len(v), v)))
    return components


@dataclass
class StructureMap:
    document: dict
    pou: dict
    elements: list[LadderElement]
    connections: list[Connection]
    parallel_branches: list[ParallelBranch]
    networks: list[dict]
    components: list[list[str]]
    components_without_rails: list[list[str]]
    observed_schema: dict
    unknown_elements: list[dict]
    diagnostics: list[dict]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STRUCTURE_MAP_SCHEMA_VERSION,
            "document": self.document,
            "pou": self.pou,
            "element_count": len(self.elements),
            "connection_count": len(self.connections),
            "network_count": len(self.networks),
            "component_count": len(self.components),
            "component_count_without_rails": len(self.components_without_rails),
            "nontrivial_component_count_without_rails": sum(
                1 for c in self.components_without_rails if len(c) > 1),
            "unknown_element_count": len(self.unknown_elements),
        }


def map_structure(xml_path: Path | str) -> StructureMap:
    xml_path = Path(xml_path)
    try:
        tree = ET.parse(str(xml_path))
    except (ET.ParseError, OSError) as exc:
        raise StructureMapError(f"XML ilegível: {exc}") from exc
    root = tree.getroot()

    diagnostics: list[dict] = []

    ld_bodies = [e for e in root.iter() if _ln(e) == "LD"]
    if not ld_bodies:
        raise StructureMapError("nenhum corpo <LD> encontrado no documento")
    if len(ld_bodies) > 1:
        diagnostics.append({
            "step": "body", "message":
            "múltiplos corpos <LD> (%d) — apenas o primeiro foi mapeado; "
            "vários corpos não estavam previstos e precisam de decisão "
            "explícita antes do parser." % len(ld_bodies)})
    ld = ld_bodies[0]

    pou_elements = [e for e in root.iter() if _ln(e) == "pou"]
    pou = pou_elements[0] if pou_elements else None

    namespaces = sorted({
        e.tag[1:].split("}", 1)[0] for e in root.iter() if e.tag.startswith("{")})

    file_header = next((e for e in root.iter() if _ln(e) == "fileHeader"), None)
    content_header = next((e for e in root.iter() if _ln(e) == "contentHeader"), None)

    document = {
        "root_tag": _ln(root),
        "namespaces": namespaces,
        "file_header": dict(file_header.attrib) if file_header is not None else {},
        "content_header": dict(content_header.attrib) if content_header is not None else {},
        "ld_body_count": len(ld_bodies),
        "has_explicit_network_element": any(_ln(e) == "network" for e in root.iter()),
    }

    interface_variables: list[dict] = []
    if pou is not None:
        for group in pou.iter():
            group_kind = _ln(group)
            if group_kind not in ("inputVars", "outputVars", "localVars",
                                  "inOutVars", "tempVars", "externalVars"):
                continue
            for variable in group:
                if _ln(variable) != "variable":
                    continue
                type_names = [
                    _ln(t) for holder in variable if _ln(holder) == "type"
                    for t in holder]
                interface_variables.append({
                    "name": variable.get("name"),
                    "group": group_kind,
                    "type": type_names[0] if type_names else None,
                })

    pou_info = {
        "name": pou.get("name") if pou is not None else None,
        "pou_type": pou.get("pouType") if pou is not None else None,
        "interface_variables": interface_variables,
    }

    elements: list[LadderElement] = []
    connections: list[Connection] = []
    parallel_branches: list[ParallelBranch] = []
    unknown_elements: list[dict] = []

    for order, child in enumerate(ld):
        kind = _ln(child)
        mapped = _parse_element(child, order)
        elements.append(mapped)
        connections.extend(_collect_connections(child))
        parallel_branches.extend(_collect_parallel_branches(child))
        if kind not in KNOWN_LD_ELEMENTS:
            unknown_elements.append({
                "kind": kind, "local_id": child.get("localId"),
                "attributes": dict(child.attrib),
                "children": sorted({_ln(c) for c in child}),
            })

    # localId duplicado quebraria toda referência — verificado, não assumido.
    seen_ids: dict[str, int] = {}
    for element in elements:
        if element.local_id is None:
            continue
        seen_ids[element.local_id] = seen_ids.get(element.local_id, 0) + 1
    duplicated = sorted(k for k, v in seen_ids.items() if v > 1)
    if duplicated:
        diagnostics.append({
            "step": "local_id", "message":
            "localId DUPLICADO: %s — referências por refLocalId ficam "
            "ambíguas." % ", ".join(duplicated)})

    known_ids = set(seen_ids)
    for conn in connections:
        if conn.source_local_id is not None and conn.source_local_id not in known_ids:
            diagnostics.append({
                "step": "connection", "message":
                "refLocalId=%s não corresponde a nenhum elemento do corpo "
                "(destino=%s)." % (conn.source_local_id, conn.target_local_id)})

    # `formalParameter` como nome do pino de ORIGEM não é confiável: verifica
    # contra os pinos de saída realmente declarados pelo bloco de origem.
    outputs_by_id = {
        e.local_id: {p["formal_parameter"] for p in e.output_pins}
        for e in elements if e.kind == "block"}
    for conn in connections:
        param = conn.source_formal_parameter
        declared = outputs_by_id.get(conn.source_local_id)
        if param and declared and param not in declared and param != "ENO":
            diagnostics.append({
                "step": "formal_parameter", "message":
                "connection para localId=%s declara formalParameter=%r, que "
                "NÃO é pino de saída do bloco de origem (localId=%s, saídas: "
                "%s). O atributo não pode ser tratado como nome do pino de "
                "origem sem verificação." % (
                    conn.target_local_id, param, conn.source_local_id,
                    sorted(declared))})

    positions = [
        (e.get("x"), e.get("y")) for e in ld.iter() if _ln(e) == "position"]
    distinct_positions = sorted(set(positions))
    if len(distinct_positions) <= 1:
        diagnostics.append({
            "step": "position", "message":
            "todas as %d posições gráficas são idênticas (%s) — coordenadas "
            "NÃO servem para desempatar topologia neste export."
            % (len(positions), distinct_positions)})

    # O trilho esquerdo conecta TODAS as redes entre si: com ele no grafo, o
    # corpo inteiro vira um único componente e a análise de conectividade não
    # separa nada. Removendo os trilhos, os componentes não-triviais
    # coincidiram com os marcadores `networktitle` no export real — dois
    # sinais independentes concordando, o que é bem mais forte que confiar
    # só na extensão do fornecedor.
    rail_ids = {e.local_id for e in elements
                if e.kind in ("leftPowerRail", "rightPowerRail")}

    # As arestas do ParallelBranch vivem SO na extensao do fornecedor e nao
    # aparecem em `connections`. Sem elas, as pernas de um paralelo viram
    # componentes separados e a contagem de redes fica inflada -- defeito que
    # a fixture sintetica expos. O `BranchInput` e o ponto comum; cada `Tree`
    # e o terminal de uma perna.
    branch_edges: list = []
    for branch in parallel_branches:
        endpoints = [r["ref_local_id"] for r in branch.tree_refs
                     if r.get("ref_local_id")]
        anchors = [r["ref_local_id"] for r in branch.input_refs
                   if r.get("ref_local_id")]
        for endpoint in endpoints:
            for other in endpoints:
                if endpoint != other:
                    branch_edges.append(Connection(
                        endpoint, "parallelBranchTree", None, other, None,
                        via="ParallelBranch"))
            for anchor in anchors:
                branch_edges.append(Connection(
                    endpoint, "parallelBranchTree", None, anchor, None,
                    via="ParallelBranch"))

    components_without_rails = _connected_components(
        [e for e in elements if e.local_id not in rail_ids],
        [c for c in list(connections) + branch_edges
         if c.source_local_id not in rail_ids and c.target_local_id not in rail_ids])
    # Limiar > 1, nao > 2: uma rede legitima pode ter apenas dois elementos
    # conectados (um bloco alimentando uma bobina). O limiar mais alto
    # descartava redes reais -- defeito que a fixture sintetica expos.
    # Limiar > 1, nao > 2: uma rede legitima pode ter apenas dois elementos
    # conectados (um bloco alimentando uma bobina). O limiar mais alto
    # descartava redes reais -- defeito que a fixture sintetica expos.
    nontrivial = [c for c in components_without_rails if len(c) > 1]

    # Comparar contra TODOS os marcadores seria injusto: no export real o
    # ultimo `networktitle` nao tem elemento nenhum depois dele, e um marcador
    # sem conteudo nao pode gerar componente. A comparacao honesta e contra os
    # marcadores que delimitam pelo menos um elemento conectavel.
    connected_ids = set()
    for conn in connections:
        connected_ids.add(conn.target_local_id)
        connected_ids.add(conn.source_local_id)
    networks_all = _segment_networks(elements)
    populated_networks = [
        n for n in networks_all
        if n.get("title_marker_local_id")
        and any(m in connected_ids for m in n["member_local_ids"])]
    empty_networks = [
        n for n in networks_all
        if n.get("title_marker_local_id")
        and not any(m in connected_ids for m in n["member_local_ids"])]

    agrees = len(populated_networks) == len(nontrivial)
    diagnostics.append({
        "step": "network_segmentation", "message":
        "marcadores networktitle com conteudo conectado=%d (marcadores vazios "
        "ignorados: %d); componentes nao-triviais apos remover trilhos e "
        "incluir arestas de ParallelBranch=%d. %s" % (
            len(populated_networks), len(empty_networks), len(nontrivial),
            "Os dois sinais INDEPENDENTES concordam -- a segmentacao por "
            "networktitle e confirmada pela topologia."
            if agrees else
            "DIVERGEM -- a segmentacao de redes precisa de decisao explicita "
            "antes do modelo canonico.")})

    observed_schema: dict = OrderedDict()
    for element in ld.iter():
        kind = _ln(element)
        entry = observed_schema.setdefault(
            kind, {"count": 0, "attributes": set(), "children": set()})
        entry["count"] += 1
        entry["attributes"].update(element.attrib)
        entry["children"].update(_ln(c) for c in element)
    observed_schema = {
        k: {"count": v["count"],
            "attributes": sorted(v["attributes"]),
            "children": sorted(v["children"])}
        for k, v in observed_schema.items()}

    return StructureMap(
        document=document,
        pou=pou_info,
        elements=elements,
        connections=connections,
        parallel_branches=parallel_branches,
        networks=_segment_networks(elements),
        components=_connected_components(elements, connections),
        components_without_rails=components_without_rails,
        observed_schema=observed_schema,
        unknown_elements=unknown_elements,
        diagnostics=diagnostics,
    )


def write_structure_map(structure: StructureMap, output_dir: Path | str) -> list[Path]:
    import json

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    payloads = {
        "document-summary.json": {**structure.document,
                                  **structure.to_dict()},
        "pou-structure.json": structure.pou,
        "ladder-elements.json": [e.to_dict() for e in structure.elements],
        "block-instances.json": [
            e.to_dict() for e in structure.elements if e.kind == "block"],
        "connection-map.json": [c.to_dict() for c in structure.connections],
        "connected-components-without-rails.json": structure.components_without_rails,
        "parallel-branches.json": [p.to_dict() for p in structure.parallel_branches],
        "networks.json": structure.networks,
        "connected-components.json": structure.components,
        "observed-element-schema.json": structure.observed_schema,
        "unknown-elements.json": structure.unknown_elements,
        "diagnostics.json": structure.diagnostics,
    }
    for name, payload in payloads.items():
        path = output_dir / name
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        written.append(path)
    return written

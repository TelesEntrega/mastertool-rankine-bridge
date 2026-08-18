"""Modelo canônico de uma POU gráfica — independente do XML e do fornecedor.

"Canônico" aqui **não** quer dizer simplificado. Quer dizer normalizado
preservando tudo que ainda não compreendemos: extensões do fornecedor,
atributos não interpretados, evidência bruta que contradiz o que seria
esperado. Um modelo que descarta o que não entende produz um parser que
mente com confiança.

O desenho vem de `docs/17-plcopen-ladder-schema.md`, que por sua vez veio de
um export real — não do que o padrão PLCopen sugeriria. Cinco exigências do
arquivo observado moldaram estes tipos:

1. **Rede não vem pronta.** Não existe `<network>`; ela é reconstruída a
   partir de duas fontes independentes (marcador do fornecedor e topologia),
   e o modelo guarda as duas separadas junto com o veredito.
2. **Aresta tem duas fontes distintas** — conexão PLCopen e extensão de
   paralelismo do fornecedor — que **não podem ser fundidas**. Fundi-las
   apagaria que uma delas é não-padrão, e um dia alguém precisaria saber.
3. **`formalParameter` da `<connection>` não é verdade sobre o pino de
   origem.** No arquivo real ele às vezes traz o nome da variável do
   destino. Fica preservado como evidência bruta; o pino resolvido é campo
   separado, com método e status de resolução.
4. **Nome de variável vem de campos diferentes** conforme o elemento, e a
   origem é preservada (`variable` vs `expression`).
5. **Coordenadas são todas (0,0)** e ficam marcadas como inúteis para
   topologia — presentes como dado observado, nunca como desempate.

Este módulo é só o modelo: tipos, invariantes e serialização. O parser que
constrói tudo isso a partir do XML é uma fatia separada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
MODEL_KIND = "graphic_pou"

# --- vocabulários ------------------------------------------------------------

# Linguagens gráficas. Só `LD` foi observada; as outras existem para o modelo
# não precisar mudar de forma quando aparecerem.
LANGUAGES = ("LD", "FBD", "SFC")

# Tipos de elemento. Os que ainda não apareceram permanecem aqui de
# propósito: o modelo precisa poder REPRESENTÁ-LOS sem que ninguém escreva
# implementação por suposição. Ver `ELEMENT_KIND_OBSERVATION`.
ELEMENT_KINDS = (
    "left_power_rail", "right_power_rail", "contact", "coil", "block",
    "in_variable", "out_variable", "inout_variable", "connector",
    "continuation", "jump", "label", "return", "vendor_element", "comment",
    "unknown",
)

# Distinção deliberada entre "nunca vimos" e "não suportamos". Ausência de
# observação NÃO é prova de ausência de suporte — confundir os dois faria o
# projeto declarar limitações que talvez não existam.
#
# "comment" observado no export real (5 elementos `<comment>` no arquivo de
# 2026-07-28) — mapeá-lo para "unknown" afirmaria não-reconhecimento onde há
# reconhecimento (`comment` já consta em `KNOWN_LD_ELEMENTS` do structure_map).
OBSERVED_ELEMENT_KINDS = frozenset({
    "left_power_rail", "right_power_rail", "contact", "coil", "block",
    "in_variable", "vendor_element", "comment",
})

PIN_DIRECTIONS = ("input", "output", "inout", "unknown")

# Como o pino de origem de uma aresta foi determinado.
SOURCE_PIN_RESOLUTION_STATUSES = (
    "resolved_from_declared_block_pins",
    "ambiguous",
    "unresolved",
    "not_applicable",
)

# As duas fontes de topologia. Nunca fundidas.
EVIDENCE_KINDS = ("plcopen_connection", "vendor_parallel_branch")

NETWORK_RECONSTRUCTION_STATUSES = (
    "confirmed_by_marker_and_connectivity",
    "marker_only",
    "connectivity_only",
    "ambiguous",
    "unassigned",
)


class CanonicalModelError(Exception):
    """Invariante do modelo violada."""


def _sorted_dict(value: dict | None) -> dict:
    """Ordem determinística — a serialização precisa ser byte-a-byte estável
    para dois runs do mesmo XML produzirem o mesmo JSON."""
    return {k: value[k] for k in sorted(value or {})}


# --- rastreabilidade ---------------------------------------------------------

@dataclass(frozen=True)
class SourceRef:
    """De onde no XML este objeto veio. Sem isto, um achado no modelo não
    pode ser conferido contra o arquivo."""

    source_file: str | None = None
    xml_path: str | None = None
    local_id: str | None = None
    line: int | None = None
    namespace: str | None = None
    raw_tag: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "xml_path": self.xml_path,
            "local_id": self.local_id,
            "line": self.line,
            "namespace": self.namespace,
            "raw_tag": self.raw_tag,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> SourceRef:
        data = data or {}
        return cls(
            source_file=data.get("source_file"), xml_path=data.get("xml_path"),
            local_id=data.get("local_id"), line=data.get("line"),
            namespace=data.get("namespace"), raw_tag=data.get("raw_tag"))


@dataclass(frozen=True)
class Position:
    """Coordenada observada. `usable_for_topology` é sempre False nesta
    versão: no export real as 42 posições são (0,0). O campo existe para o
    dado não sumir, nunca para desempatar conexão."""

    x: int | None = None
    y: int | None = None
    usable_for_topology: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y,
                "usable_for_topology": self.usable_for_topology}

    @classmethod
    def from_dict(cls, data: dict | None) -> Position:
        data = data or {}
        return cls(x=data.get("x"), y=data.get("y"),
                   usable_for_topology=bool(data.get("usable_for_topology")))


@dataclass
class Diagnostic:
    step: str
    message: str
    severity: str = "info"
    refs: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"step": self.step, "message": self.message,
                "severity": self.severity, "refs": sorted(self.refs)}

    @classmethod
    def from_dict(cls, data: dict) -> Diagnostic:
        return cls(step=data["step"], message=data["message"],
                   severity=data.get("severity", "info"),
                   refs=list(data.get("refs") or []))


# --- pinos -------------------------------------------------------------------

@dataclass
class Pin:
    """Entidade própria, não um campo do bloco. O pino de origem de uma
    aresta é resolvido contra estes — nunca contra o `formalParameter` da
    conexão."""

    pin_id: str
    owner_element_id: str
    formal_parameter: str | None
    direction: str
    declaration_source: str | None = None
    source: SourceRef = field(default_factory=SourceRef)

    def __post_init__(self) -> None:
        if self.direction not in PIN_DIRECTIONS:
            raise CanonicalModelError(
                f"direção de pino desconhecida: {self.direction!r} "
                f"(esperado um de {list(PIN_DIRECTIONS)})")

    def to_dict(self) -> dict[str, Any]:
        return {
            "pin_id": self.pin_id,
            "owner_element_id": self.owner_element_id,
            "formal_parameter": self.formal_parameter,
            "direction": self.direction,
            "declaration_source": self.declaration_source,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Pin:
        return cls(
            pin_id=data["pin_id"], owner_element_id=data["owner_element_id"],
            formal_parameter=data.get("formal_parameter"),
            direction=data["direction"],
            declaration_source=data.get("declaration_source"),
            source=SourceRef.from_dict(data.get("source")))


# --- elementos ---------------------------------------------------------------

@dataclass
class Element:
    """Elemento gráfico. Campos específicos convivem com `attributes` cru:
    um atributo que ainda não sabemos nomear continua acessível."""

    element_id: str
    local_id: str | None
    kind: str
    raw_xml_tag: str | None = None
    execution_order_id: str | None = None
    attributes: dict = field(default_factory=dict)
    position: Position = field(default_factory=Position)
    source: SourceRef = field(default_factory=SourceRef)
    vendor_metadata: dict = field(default_factory=dict)

    # contato / bobina
    negated: bool | None = None
    edge: str | None = None
    storage: str | None = None

    # variável — a ORIGEM do texto é preservada, não fundida
    value_text: str | None = None
    value_source_kind: str | None = None   # "variable" | "expression"

    # bloco
    type_name: str | None = None
    call_type: str | None = None
    instance_name: str | None = None
    pin_ids: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in ELEMENT_KINDS:
            raise CanonicalModelError(
                f"tipo de elemento desconhecido: {self.kind!r}. Use 'unknown' "
                "e preserve o tag original em raw_xml_tag — elemento não pode "
                "desaparecer por não ser reconhecido.")
        if self.value_source_kind not in (None, "variable", "expression"):
            raise CanonicalModelError(
                f"value_source_kind inválido: {self.value_source_kind!r} "
                "(esperado 'variable', 'expression' ou None)")

    @property
    def observation_status(self) -> str:
        """`observed` quando o tipo já apareceu num export real;
        `not_observed` caso contrário. NUNCA `unsupported` — ausência de
        observação não é prova de ausência de suporte."""
        return "observed" if self.kind in OBSERVED_ELEMENT_KINDS else "not_observed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "local_id": self.local_id,
            "kind": self.kind,
            "observation_status": self.observation_status,
            "raw_xml_tag": self.raw_xml_tag,
            "execution_order_id": self.execution_order_id,
            "attributes": _sorted_dict(self.attributes),
            "position": self.position.to_dict(),
            "source": self.source.to_dict(),
            "vendor_metadata": _sorted_dict(self.vendor_metadata),
            "negated": self.negated,
            "edge": self.edge,
            "storage": self.storage,
            "value_text": self.value_text,
            "value_source_kind": self.value_source_kind,
            "type_name": self.type_name,
            "call_type": self.call_type,
            "instance_name": self.instance_name,
            "pin_ids": sorted(self.pin_ids),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Element:
        return cls(
            element_id=data["element_id"], local_id=data.get("local_id"),
            kind=data["kind"], raw_xml_tag=data.get("raw_xml_tag"),
            execution_order_id=data.get("execution_order_id"),
            attributes=dict(data.get("attributes") or {}),
            position=Position.from_dict(data.get("position")),
            source=SourceRef.from_dict(data.get("source")),
            vendor_metadata=dict(data.get("vendor_metadata") or {}),
            negated=data.get("negated"), edge=data.get("edge"),
            storage=data.get("storage"), value_text=data.get("value_text"),
            value_source_kind=data.get("value_source_kind"),
            type_name=data.get("type_name"), call_type=data.get("call_type"),
            instance_name=data.get("instance_name"),
            pin_ids=list(data.get("pin_ids") or []))


# --- topologia: evidência e aresta derivada ----------------------------------

@dataclass
class ConnectionEvidence:
    """UMA observação de ligação, com a fonte preservada. Nunca convertida em
    outra espécie de evidência."""

    evidence_id: str
    evidence_kind: str
    source_element_ref: str | None
    target_element_ref: str | None
    source_pin_raw: str | None = None
    target_pin_raw: str | None = None
    vendor_attributes: dict = field(default_factory=dict)
    source_location: SourceRef = field(default_factory=SourceRef)

    def __post_init__(self) -> None:
        if self.evidence_kind not in EVIDENCE_KINDS:
            raise CanonicalModelError(
                f"evidence_kind desconhecido: {self.evidence_kind!r} "
                f"(esperado um de {list(EVIDENCE_KINDS)})")

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_kind": self.evidence_kind,
            "source_element_ref": self.source_element_ref,
            "target_element_ref": self.target_element_ref,
            "source_pin_raw": self.source_pin_raw,
            "target_pin_raw": self.target_pin_raw,
            "vendor_attributes": _sorted_dict(self.vendor_attributes),
            "source_location": self.source_location.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ConnectionEvidence:
        return cls(
            evidence_id=data["evidence_id"],
            evidence_kind=data["evidence_kind"],
            source_element_ref=data.get("source_element_ref"),
            target_element_ref=data.get("target_element_ref"),
            source_pin_raw=data.get("source_pin_raw"),
            target_pin_raw=data.get("target_pin_raw"),
            vendor_attributes=dict(data.get("vendor_attributes") or {}),
            source_location=SourceRef.from_dict(data.get("source_location")))


@dataclass
class DerivedEdge:
    """Adjacência unificada, construída A PARTIR das evidências e sempre
    apontando de volta para elas. O pino de origem resolvido NUNCA vem do
    `formalParameter` cru."""

    edge_id: str
    source_element_id: str | None
    target_element_id: str | None
    supporting_evidence_ids: list = field(default_factory=list)
    resolved_source_pin: str | None = None
    source_pin_resolution_method: str | None = None
    source_pin_resolution_status: str = "not_applicable"
    resolved_target_pin: str | None = None
    raw_connection_formal_parameter: str | None = None

    def __post_init__(self) -> None:
        if self.source_pin_resolution_status not in SOURCE_PIN_RESOLUTION_STATUSES:
            raise CanonicalModelError(
                "source_pin_resolution_status inválido: "
                f"{self.source_pin_resolution_status!r}")
        if not self.supporting_evidence_ids:
            raise CanonicalModelError(
                f"aresta {self.edge_id!r} sem evidência de suporte — toda "
                "aresta derivada precisa apontar para o que a justifica.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_element_id": self.source_element_id,
            "target_element_id": self.target_element_id,
            "supporting_evidence_ids": sorted(self.supporting_evidence_ids),
            "resolved_source_pin": self.resolved_source_pin,
            "source_pin_resolution_method": self.source_pin_resolution_method,
            "source_pin_resolution_status": self.source_pin_resolution_status,
            "resolved_target_pin": self.resolved_target_pin,
            "raw_connection_formal_parameter": self.raw_connection_formal_parameter,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DerivedEdge:
        return cls(
            edge_id=data["edge_id"],
            source_element_id=data.get("source_element_id"),
            target_element_id=data.get("target_element_id"),
            supporting_evidence_ids=list(data.get("supporting_evidence_ids") or []),
            resolved_source_pin=data.get("resolved_source_pin"),
            source_pin_resolution_method=data.get("source_pin_resolution_method"),
            source_pin_resolution_status=data.get(
                "source_pin_resolution_status", "not_applicable"),
            resolved_target_pin=data.get("resolved_target_pin"),
            raw_connection_formal_parameter=data.get(
                "raw_connection_formal_parameter"))


# --- redes -------------------------------------------------------------------

@dataclass
class NetworkBoundary:
    """Marcador de fronteira do fornecedor. Marcador VAZIO é registrado, não
    descartado — foi justamente ele que produziu divergência falsa na
    primeira análise do arquivo real."""

    marker_id: str
    title: str | None = None
    is_empty: bool = False
    order: int = 0
    source: SourceRef = field(default_factory=SourceRef)

    def to_dict(self) -> dict[str, Any]:
        return {"marker_id": self.marker_id, "title": self.title,
                "is_empty": self.is_empty, "order": self.order,
                "source": self.source.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> NetworkBoundary:
        return cls(marker_id=data["marker_id"], title=data.get("title"),
                   is_empty=bool(data.get("is_empty")),
                   order=int(data.get("order", 0)),
                   source=SourceRef.from_dict(data.get("source")))


@dataclass
class ConnectedComponent:
    component_id: str
    element_ids: list = field(default_factory=list)
    edge_ids: list = field(default_factory=list)
    discovery_method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"component_id": self.component_id,
                "element_ids": sorted(self.element_ids),
                "edge_ids": sorted(self.edge_ids),
                "discovery_method": self.discovery_method}

    @classmethod
    def from_dict(cls, data: dict) -> ConnectedComponent:
        return cls(component_id=data["component_id"],
                   element_ids=list(data.get("element_ids") or []),
                   edge_ids=list(data.get("edge_ids") or []),
                   discovery_method=data.get("discovery_method"))


@dataclass
class Network:
    """Rede canônica. Guarda de qual evidência veio e com que confiança —
    duas fontes concordando é resultado diferente de uma só."""

    network_id: str
    order: int = 0
    title: str | None = None
    element_ids: list = field(default_factory=list)
    connection_ids: list = field(default_factory=list)
    boundary_evidence_ids: list = field(default_factory=list)
    component_ids: list = field(default_factory=list)
    reconstruction_status: str = "unassigned"
    diagnostics: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.reconstruction_status not in NETWORK_RECONSTRUCTION_STATUSES:
            raise CanonicalModelError(
                f"reconstruction_status inválido: {self.reconstruction_status!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "network_id": self.network_id, "order": self.order,
            "title": self.title,
            "element_ids": sorted(self.element_ids),
            "connection_ids": sorted(self.connection_ids),
            "boundary_evidence_ids": sorted(self.boundary_evidence_ids),
            "component_ids": sorted(self.component_ids),
            "reconstruction_status": self.reconstruction_status,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Network:
        return cls(
            network_id=data["network_id"], order=int(data.get("order", 0)),
            title=data.get("title"),
            element_ids=list(data.get("element_ids") or []),
            connection_ids=list(data.get("connection_ids") or []),
            boundary_evidence_ids=list(data.get("boundary_evidence_ids") or []),
            component_ids=list(data.get("component_ids") or []),
            reconstruction_status=data.get("reconstruction_status", "unassigned"),
            diagnostics=[Diagnostic.from_dict(d) for d in data.get("diagnostics") or []])


# --- extensões do fornecedor -------------------------------------------------

@dataclass
class VendorExtension:
    """Preservada integralmente em forma normalizada. O fragmento XML cru não
    entra no JSON público (pode conter conteúdo do cliente), mas o hash
    permite rastrear até a origem."""

    extension_id: str
    owner_id: str | None
    namespace: str | None
    tag: str | None
    attributes: dict = field(default_factory=dict)
    normalized_classification: str | None = None
    raw_fragment_hash: str | None = None
    source: SourceRef = field(default_factory=SourceRef)

    def to_dict(self) -> dict[str, Any]:
        return {
            "extension_id": self.extension_id, "owner_id": self.owner_id,
            "namespace": self.namespace, "tag": self.tag,
            "attributes": _sorted_dict(self.attributes),
            "normalized_classification": self.normalized_classification,
            "raw_fragment_hash": self.raw_fragment_hash,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> VendorExtension:
        return cls(
            extension_id=data["extension_id"], owner_id=data.get("owner_id"),
            namespace=data.get("namespace"), tag=data.get("tag"),
            attributes=dict(data.get("attributes") or {}),
            normalized_classification=data.get("normalized_classification"),
            raw_fragment_hash=data.get("raw_fragment_hash"),
            source=SourceRef.from_dict(data.get("source")))


# --- POU ---------------------------------------------------------------------

@dataclass
class InterfaceVariable:
    name: str | None
    group: str | None
    type_name: str | None = None
    """Nome RESOLVÍVEL do tipo contra o índice do projeto: `BOOL` para
    elementar, `TON` para `<derived name="TON"/>`, `None` quando o documento
    não o carrega."""
    type_kind: str | None = None
    """FORMA declarada do tipo — a tag dentro de `<type>`: `BOOL`, `derived`,
    `array`. Separada do nome porque distinguir primitivo de derivado é uma
    pergunta diferente de "que tipo é este"."""

    @property
    def declared_type(self) -> str:
        """O que vai para `VariableDeclaration.declared_type`.

        O nome quando existe; a forma quando não existe. Nunca vazio por
        omissão: um tipo sem nome derivável continua sendo um fato declarado, e
        apagá-lo esconderia a declaração inteira em vez de só o nome.
        """
        return self.type_name or self.type_kind or ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "group": self.group,
                "type_name": self.type_name, "type_kind": self.type_kind}

    @classmethod
    def from_dict(cls, data: dict) -> InterfaceVariable:
        return cls(name=data.get("name"), group=data.get("group"),
                   type_name=data.get("type_name"),
                   type_kind=data.get("type_kind"))


@dataclass
class GraphicPOU:
    """Raiz do modelo. As invariantes são checadas na construção, não na
    serialização — um modelo inconsistente não deve nem existir."""

    name: str | None
    pou_type: str | None
    language: str = "LD"
    namespace: str | None = None
    source_file: str | None = None
    interface: list = field(default_factory=list)
    elements: list = field(default_factory=list)
    pins: list = field(default_factory=list)
    connection_evidence: list = field(default_factory=list)
    derived_edges: list = field(default_factory=list)
    network_boundaries: list = field(default_factory=list)
    components: list = field(default_factory=list)
    networks: list = field(default_factory=list)
    vendor_extensions: list = field(default_factory=list)
    unassigned_elements: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate()

    # --- invariantes ---------------------------------------------------------

    def validate(self) -> None:
        if self.language not in LANGUAGES:
            raise CanonicalModelError(
                f"linguagem desconhecida: {self.language!r} "
                f"(esperado um de {list(LANGUAGES)})")

        element_ids = [e.element_id for e in self.elements]
        if len(set(element_ids)) != len(element_ids):
            raise CanonicalModelError("element_id duplicado dentro da POU")

        # `localId` único dentro da POU — referência ambígua torna toda a
        # topologia não confiável, então é erro, não diagnóstico.
        local_ids = [e.local_id for e in self.elements if e.local_id is not None]
        if len(set(local_ids)) != len(local_ids):
            duplicated = sorted({i for i in local_ids if local_ids.count(i) > 1})
            raise CanonicalModelError(
                f"localId duplicado dentro da POU: {duplicated}")

        known_elements = set(element_ids)
        for pin in self.pins:
            if pin.owner_element_id not in known_elements:
                raise CanonicalModelError(
                    f"pino {pin.pin_id!r} pertence a elemento inexistente "
                    f"{pin.owner_element_id!r}")

        pin_ids = [p.pin_id for p in self.pins]
        if len(set(pin_ids)) != len(pin_ids):
            raise CanonicalModelError("pin_id duplicado dentro da POU")

        known_pins = set(pin_ids)
        for element in self.elements:
            for referenced in element.pin_ids:
                if referenced not in known_pins:
                    raise CanonicalModelError(
                        f"elemento {element.element_id!r} referencia pino "
                        f"inexistente {referenced!r}")

        evidence_ids = [e.evidence_id for e in self.connection_evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise CanonicalModelError("evidence_id duplicado")

        known_evidence = set(evidence_ids)
        for edge in self.derived_edges:
            missing = [e for e in edge.supporting_evidence_ids
                       if e not in known_evidence]
            if missing:
                raise CanonicalModelError(
                    f"aresta {edge.edge_id!r} aponta para evidência "
                    f"inexistente: {missing}")

        # Referência a elemento que não existe NÃO derruba o modelo: vira
        # diagnóstico. Um XML com referência pendente ainda é analisável, e
        # recusá-lo inteiro esconderia tudo o que ele tem de bom.
        for evidence in self.connection_evidence:
            for ref, role in ((evidence.source_element_ref, "origem"),
                              (evidence.target_element_ref, "destino")):
                if ref is not None and ref not in known_elements:
                    self.diagnostics.append(Diagnostic(
                        step="dangling_reference",
                        severity="warning",
                        message=(f"evidência {evidence.evidence_id!r} referencia "
                                 f"elemento de {role} inexistente: {ref!r}"),
                        refs=[evidence.evidence_id]))

        # Nenhuma posição pode ser marcada como utilizável para topologia
        # enquanto o único export observado tem tudo em (0,0).
        for element in self.elements:
            if element.position.usable_for_topology:
                raise CanonicalModelError(
                    f"elemento {element.element_id!r} declara posição utilizável "
                    "para topologia — nenhum export observado sustenta isso.")

    # --- consultas úteis, sem interpretar lógica -----------------------------

    def pins_of(self, element_id: str) -> list:
        return [p for p in self.pins if p.owner_element_id == element_id]

    def evidence_by_kind(self, kind: str) -> list:
        return [e for e in self.connection_evidence if e.evidence_kind == kind]

    def observation_summary(self) -> dict:
        """Quais tipos apareceram e quais não. `not_observed` nunca vira
        `unsupported`."""
        present = {e.kind for e in self.elements}
        return {
            "observed": sorted(present & OBSERVED_ELEMENT_KINDS),
            "modelled_but_not_observed": sorted(
                set(ELEMENT_KINDS) - OBSERVED_ELEMENT_KINDS - {"unknown"}),
            "present_in_this_pou": sorted(present),
        }

    # --- serialização --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_kind": MODEL_KIND,
            "language": self.language,
            "identity": {
                "name": self.name,
                "pou_type": self.pou_type,
                "namespace": self.namespace,
                "source_file": self.source_file,
            },
            "interface": [v.to_dict() for v in self.interface],
            "elements": [e.to_dict() for e in
                         sorted(self.elements, key=lambda e: e.element_id)],
            "pins": [p.to_dict() for p in
                     sorted(self.pins, key=lambda p: p.pin_id)],
            "connection_evidence": [e.to_dict() for e in
                                    sorted(self.connection_evidence,
                                           key=lambda e: e.evidence_id)],
            "derived_edges": [e.to_dict() for e in
                              sorted(self.derived_edges, key=lambda e: e.edge_id)],
            "network_boundaries": [b.to_dict() for b in
                                   sorted(self.network_boundaries,
                                          key=lambda b: (b.order, b.marker_id))],
            "components": [c.to_dict() for c in
                           sorted(self.components, key=lambda c: c.component_id)],
            "networks": [n.to_dict() for n in
                         sorted(self.networks, key=lambda n: (n.order, n.network_id))],
            "vendor_extensions": [v.to_dict() for v in
                                  sorted(self.vendor_extensions,
                                         key=lambda v: v.extension_id)],
            "unassigned_elements": sorted(self.unassigned_elements),
            "observation_summary": self.observation_summary(),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }

    @classmethod
    def from_dict(cls, data: dict) -> GraphicPOU:
        if data.get("model_kind") != MODEL_KIND:
            raise CanonicalModelError(
                f"model_kind inesperado: {data.get('model_kind')!r}")
        if data.get("schema_version") != SCHEMA_VERSION:
            raise CanonicalModelError(
                f"schema_version não suportada: {data.get('schema_version')!r} "
                f"(este módulo lê {SCHEMA_VERSION})")
        identity = data.get("identity") or {}
        pou = cls(
            name=identity.get("name"), pou_type=identity.get("pou_type"),
            language=data.get("language", "LD"),
            namespace=identity.get("namespace"),
            source_file=identity.get("source_file"),
            interface=[InterfaceVariable.from_dict(v) for v in data.get("interface") or []],
            elements=[Element.from_dict(e) for e in data.get("elements") or []],
            pins=[Pin.from_dict(p) for p in data.get("pins") or []],
            connection_evidence=[ConnectionEvidence.from_dict(e)
                                 for e in data.get("connection_evidence") or []],
            derived_edges=[DerivedEdge.from_dict(e)
                           for e in data.get("derived_edges") or []],
            network_boundaries=[NetworkBoundary.from_dict(b)
                                for b in data.get("network_boundaries") or []],
            components=[ConnectedComponent.from_dict(c)
                        for c in data.get("components") or []],
            networks=[Network.from_dict(n) for n in data.get("networks") or []],
            vendor_extensions=[VendorExtension.from_dict(v)
                               for v in data.get("vendor_extensions") or []],
            unassigned_elements=list(data.get("unassigned_elements") or []),
            diagnostics=[],
            schema_version=data.get("schema_version", SCHEMA_VERSION))
        # Diagnósticos vindos do dict são restaurados DEPOIS da validação,
        # senão os avisos gerados por ela seriam duplicados a cada round-trip.
        pou.diagnostics = [Diagnostic.from_dict(d) for d in data.get("diagnostics") or []]
        return pou

"""R9.1 — o modelo canônico de engenharia de planta.

O QUE ELE É
===========
Uma representação da planta **independente do MasterTool**. Ela existe para
que a documentação de engenharia possa ser normalizada, revisada e aprovada
ANTES de virar projeto — e para que cada decisão possa ser rastreada até o
documento que a sustenta.

O modelo não gera código. Ele carrega fatos com origem e estado.

DESENHADO CONTRA O CORPUS REAL, NÃO CONTRA UMA IDEIA DE CORPUS
==============================================================
As formas abaixo saíram de um levantamento somente-leitura de documentação de
projeto real — uma tabela de pontos de controle e um descritivo lógico. Três
coisas medidas que decidiram o desenho:

* **agrupamento por linha-cabeçalho.** O equipamento dono de um ponto não vem
  numa coluna: vem numa linha que só tem o nome da seção. Quem lê precisa
  carregar estado; quem modela precisa saber que essa relação é posicional e
  frágil, e por isso ela vira `origin` explícita;

* **colunas que existem e estão vazias.** As colunas de I/O de segurança
  estavam presentes em todas as versões do arquivo e sem uma única linha
  preenchida. "Coluna existe" não é "dado existe", e o modelo precisa
  distinguir os dois — senão a ausência vira zero e o zero vira fato;

* **classificação divergente.** Dispositivos de segurança apareciam tipados
  como entrada digital comum. O modelo registra a divergência em vez de
  escolher um dos lados: escolher seria decidir engenharia de segurança por
  heurística de planilha.

ESTADO É DE PRIMEIRA CLASSE
===========================
Cada requisito carrega `state`. Um modelo que só guardasse valores obrigaria
o consumidor a tratar ausência como zero, e é assim que uma planta ganha um
intertravamento que ninguém especificou.

    confirmed   o documento diz, sem ambiguidade
    ambiguous   o documento diz coisas que não fecham entre si
    absent      o documento deveria dizer e não diz
    derived     obtido por regra declarada a partir de confirmados

`derived` NÃO é inferência estatística nem preenchimento por semelhança. É
aplicação de uma regra nomeada, e a regra vai junto no fato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
MODEL_KIND = "plant_engineering_model"

# Vocabulário FECHADO. Um estado novo é decisão de contrato.
STATES = ("confirmed", "ambiguous", "absent", "derived")

# Classes de ponto de I/O, com o vocabulário da própria documentação. Os
# quatro últimos existem no cabeçalho do corpus real e podem estar vazios —
# ver `Fact.state`.
IO_CLASSES = (
    "digital_input",            # ED
    "digital_output",           # SD
    "safety_digital_input",     # EDS
    "safety_digital_output",    # SDS
    "analog_input",             # EA
    "analog_output",            # SA
    "safety_controller_input",  # ED-CPS
    "safety_controller_output",  # SD-CPS
)

# As classes que NÃO entram em geração automática de lógica. Não é precaução
# genérica: é a linha acordada com o operador, e ela precisa ser executável
# pelo código, não só escrita em prosa.
SAFETY_CLASSES = frozenset({
    "safety_digital_input", "safety_digital_output",
    "safety_controller_input", "safety_controller_output",
})


@dataclass(frozen=True)
class Origin:
    """De onde o fato veio. Nunca opcional em fato `confirmed`.

    `document` + `locator` juntos precisam permitir que um humano abra o
    arquivo e olhe para a mesma célula. Sem isso, "rastreável" é adjetivo.
    """

    document: str
    locator: str
    sheet: str | None = None
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"document": self.document, "locator": self.locator,
                "sheet": self.sheet, "version": self.version}


@dataclass(frozen=True)
class Fact:
    """Um valor normalizado com estado e procedência."""

    value: Any
    state: str
    origin: Origin | None = None
    rule: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError("estado %r fora de %s" % (self.state, list(STATES)))
        if self.state == "confirmed" and self.origin is None:
            raise ValueError(
                "fato `confirmed` sem origem: confirmado por quem? Um valor "
                "sem procedência não é confirmação, é digitação")
        if self.state == "derived" and not self.rule:
            raise ValueError(
                "fato `derived` sem regra nomeada. Derivação sem regra é "
                "inferência, e inferência não entra neste modelo")
        if self.state == "absent" and self.value is not None:
            raise ValueError(
                "fato `absent` com valor %r: ausência com valor preenchido é "
                "exatamente o preenchimento silencioso que este estado existe "
                "para impedir" % (self.value,))

    @property
    def usable(self) -> bool:
        """Pode ser consumido por quem gera arquitetura?

        `ambiguous` e `absent` não podem. Deixá-los passar transformaria uma
        pendência de engenharia em decisão do gerador.
        """
        return self.state in ("confirmed", "derived")

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "state": self.state,
            "usable": self.usable,
            "origin": self.origin.to_dict() if self.origin else None,
            "rule": self.rule,
            "note": self.note,
        }


@dataclass(frozen=True)
class IOPoint:
    """Um ponto de controle: a menor unidade rastreável da planta."""

    tag: str
    description: Fact
    equipment: Fact
    location: Fact
    io_counts: dict = field(default_factory=dict)   # classe -> Fact
    protocol: Fact | None = None
    diagnostics: tuple = ()

    @property
    def is_safety(self) -> bool:
        """Verdadeiro se QUALQUER contagem de classe de segurança for usável.

        Um ponto de segurança nunca entra em geração de lógica.
        """
        return any(f.usable and f.value
                   for c, f in self.io_counts.items() if c in SAFETY_CLASSES)

    @property
    def total_points(self) -> int:
        return sum(int(f.value or 0) for f in self.io_counts.values()
                   if f.usable and isinstance(f.value, (int, float)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "description": self.description.to_dict(),
            "equipment": self.equipment.to_dict(),
            "location": self.location.to_dict(),
            "io_counts": {c: f.to_dict() for c, f in sorted(self.io_counts.items())},
            "protocol": self.protocol.to_dict() if self.protocol else None,
            "is_safety": self.is_safety,
            "total_points": self.total_points,
            "diagnostics": list(self.diagnostics),
        }


@dataclass(frozen=True)
class Equipment:
    """Um equipamento, derivado do agrupamento da fonte."""

    name: str
    origin: Origin
    point_tags: tuple = ()

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "origin": self.origin.to_dict(),
                "point_tags": list(self.point_tags)}


@dataclass(frozen=True)
class Gap:
    """Uma lacuna NOMEADA. O produto mais importante do modelo.

    Uma arquitetura que diz "falta o intertravamento X, origem: documento Y,
    linha 42" vale mais que uma que o preencheu — porque a primeira pode ser
    resolvida e a segunda precisa primeiro ser descoberta.
    """

    kind: str
    subject: str
    detail: str
    origin: Origin | None = None
    blocks_generation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "subject": self.subject,
            "detail": self.detail,
            "origin": self.origin.to_dict() if self.origin else None,
            "blocks_generation": self.blocks_generation,
        }


@dataclass
class PlantModel:
    """O modelo. Determinístico na serialização."""

    project: str
    source_version: str | None = None
    equipment: list = field(default_factory=list)
    points: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)

    # --- consultas ----------------------------------------------------------

    def points_of(self, equipment_name: str) -> list:
        return [p for p in self.points
                if p.equipment.usable and p.equipment.value == equipment_name]

    def safety_points(self) -> list:
        return [p for p in self.points if p.is_safety]

    def generable_points(self) -> list:
        """Os pontos que podem entrar em geração de lógica.

        Exclui segurança e exclui o que não tem equipamento utilizável: um
        ponto sem dono não pertence a nenhum FB, e escolher um dono seria
        inventar a arquitetura.
        """
        return [p for p in self.points
                if not p.is_safety and p.equipment.usable]

    def blocking_gaps(self) -> list:
        return [g for g in self.gaps if g.blocks_generation]

    @property
    def ready_for_architecture(self) -> bool:
        """Derivado, e nunca declarado. Uma lacuna bloqueante em aberto
        significa que a arquitetura seria escrita sobre suposição."""
        return not self.blocking_gaps()

    def summary(self) -> dict[str, Any]:
        classes: dict = {}
        for p in self.points:
            for c, f in p.io_counts.items():
                if f.usable and f.value:
                    classes[c] = classes.get(c, 0) + int(f.value)
        return {
            "equipment": len(self.equipment),
            "points": len(self.points),
            "io_by_class": dict(sorted(classes.items())),
            "safety_points": len(self.safety_points()),
            "generable_points": len(self.generable_points()),
            "gaps": len(self.gaps),
            "blocking_gaps": len(self.blocking_gaps()),
            "ready_for_architecture": self.ready_for_architecture,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "model_kind": MODEL_KIND,
            "project": self.project,
            "source_version": self.source_version,
            "equipment": [e.to_dict() for e in
                          sorted(self.equipment, key=lambda e: e.name)],
            "points": [p.to_dict() for p in
                       sorted(self.points, key=lambda p: p.tag)],
            "gaps": [g.to_dict() for g in
                     sorted(self.gaps, key=lambda g: (g.kind, g.subject))],
            "diagnostics": sorted(self.diagnostics,
                                  key=lambda d: (d.get("code", ""),
                                                 d.get("subject", ""))),
            "summary": self.summary(),
        }

"""R9.4 — arquitetura preliminar, com bloqueadores explícitos.

O QUE ELA É
===========
Um rascunho estrutural que mostra **quais decisões cada lacuna impede**. Não é
arquitetura aprovada e não gera ST.

Ela existe porque pedir "resolva as pendências" sem mostrar o que elas
bloqueiam produz respostas genéricas que depois não alteram artefato nenhum.

DUAS DECISÕES QUE NÃO SE MISTURAM
=================================
    como o software deve ser estruturado
    ≠
    em qual CLP cada parte fica

A primeira é derivável do corpus. A segunda **nunca** é: a topologia de
controladores é DECLARADA por quem conhece a planta, e a alocação é derivada
dela. Que o corpus descreva um controlador não prova que a planta tenha um.

    topologia não declarada   ->  human_decision_required (alocar seria decidir
                                  por omissão)
    um controlador declarado  ->  derived: existe um só candidato, e perguntar
                                  produziria decisões cuja resposta já é sabida
    vários declarados         ->  human_decision_required: saber QUANTOS são
                                  não diz QUAL recebe o quê

Nunca por proximidade textual, ordem do documento ou primeiro equipamento da
sequência.

O INVARIANTE DO MULTICANAL
==========================
Um dispositivo não é um ponto de I/O. Sete dispositivos do corpus têm mais de
um canal, e reduzi-los a um ponto perderia dezesseis endereços — silenciosamente,
porque a contagem de dispositivos continuaria certa.

    identidade de dispositivo   ≠   canal físico/lógico

`device_channel_map` carrega os dois, sempre.

CINCO ESTADOS, E `proposed` É O QUE FALTAVA
===========================================
    measured                  o corpus diz
    derived                   regra nomeada sobre o que o corpus diz
    proposed                  decisão de arquitetura do sistema, sem fato documental
    human_decision_required   o corpus não sustenta e alguém precisa decidir
    blocked                   depende de um bloqueador aberto

`proposed` é honesto: uma decisão arquitetural válida pode ser proposta do
sistema sem ser fato documental. Chamá-la de `derived` a faria parecer medida.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
MODEL_KIND = "plant_architecture_draft"

MEASURED = "measured"
DERIVED = "derived"
PROPOSED = "proposed"
HUMAN_DECISION = "human_decision_required"
BLOCKED = "blocked"

STATUSES = (MEASURED, DERIVED, PROPOSED, HUMAN_DECISION, BLOCKED)

# Domínios de GVL. Segurança fica SEPARADA e, nesta fase, guarda referências e
# estados documentais — nunca lógica gerada.
GVL_DOMAINS = (
    "GVL_IO", "GVL_Equipment", "GVL_Process", "GVL_Commands",
    "GVL_Status", "GVL_Communication", "GVL_Parameters",
    "GVL_Safety_Requirements",
)

SAFETY_GVL = "GVL_Safety_Requirements"


@dataclass(frozen=True)
class Element:
    """Um elemento de arquitetura proposto, com por que existe e o que o
    bloqueia."""

    kind: str                     # dut | gvl | fb | program | task | interface
    name: str
    status: str
    rationale: str
    satisfies: tuple = ()         # requirement ids / tags
    blocked_by: tuple = ()
    sources: tuple = ()

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError("status %r fora de %s" % (self.status,
                                                       list(STATUSES)))
        if not self.rationale:
            raise ValueError(
                "elemento %r sem justificativa: 'por que existe' é exigência "
                "do gate, não decoração" % self.name)

    @property
    def approval_state(self) -> str:
        if self.blocked_by:
            return BLOCKED
        return self.status

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "name": self.name, "status": self.status,
            "approval_state": self.approval_state,
            "rationale": self.rationale,
            "satisfies": list(self.satisfies),
            "blocked_by": list(self.blocked_by),
            "sources": list(self.sources),
        }


@dataclass(frozen=True)
class Blocker:
    blocker_id: str
    subject: str
    detail: str
    affected_requirements: tuple = ()
    affected_elements: tuple = ()
    blocks_approval: bool = True
    blocks_materialization: bool = True
    origin: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocker_id": self.blocker_id, "subject": self.subject,
            "detail": self.detail,
            "affected_requirements": list(self.affected_requirements),
            "affected_elements": list(self.affected_elements),
            "blocks_approval": self.blocks_approval,
            "blocks_materialization": self.blocks_materialization,
            "origin": self.origin,
        }


@dataclass
class ArchitectureDraft:
    project: str
    elements: list = field(default_factory=list)
    blockers: list = field(default_factory=list)
    device_channel_map: list = field(default_factory=list)
    sequence_architecture: list = field(default_factory=list)
    boundary_contracts: list = field(default_factory=list)
    unplaced_in_behavior: list = field(default_factory=list)
    allocation: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)
    controller_topology: dict = field(
        default_factory=lambda: _topologia(None, ()))

    # --- prontidão, por dimensão -------------------------------------------

    def readiness(self) -> dict[str, Any]:
        """Um `ready_for_architecture` único já não descreve o estado.

        Estruturar pode ser permitido enquanto aprovar e materializar não são —
        e colapsar as três esconderia exatamente o que este slice mostra.
        """
        aprova = [b for b in self.blockers if b.blocks_approval]
        materializa = [b for b in self.blockers if b.blocks_materialization]
        seguranca = [b for b in self.blockers if "safety" in b.subject.lower()
                     or "NR-12" in b.detail or "seguran" in b.detail.lower()]
        # Pendente é o que ainda espera alguém: `derived` já tem dono, e
        # exigir `measured` aqui manteria a alocação eternamente incompleta
        # mesmo com a topologia declarada e o dono determinado.
        alocacao = [a for a in self.allocation
                    if a["allocation_status"] in (HUMAN_DECISION, BLOCKED)]
        return {
            "inventory_complete": bool(self.device_channel_map),
            "sequence_inventory_complete": bool(self.sequence_architecture),
            "structural_draft_allowed": True,
            "plc_allocation_complete": not alocacao,
            "behavior_complete": all(
                s["status"] != HUMAN_DECISION
                for s in self.sequence_architecture),
            "safety_requirements_complete": not seguranca,
            "inter_plc_contracts_complete": not self.boundary_contracts,
            "architecture_approval_allowed": not aprova,
            "materialization_allowed": not materializa,
        }

    def summary(self) -> dict[str, Any]:
        por_tipo: dict = {}
        por_estado: dict = {}
        for e in self.elements:
            por_tipo[e.kind] = por_tipo.get(e.kind, 0) + 1
            por_estado[e.approval_state] = por_estado.get(e.approval_state, 0) + 1
        return {
            "elements": len(self.elements),
            "by_kind": dict(sorted(por_tipo.items())),
            "by_approval_state": dict(sorted(por_estado.items())),
            "blockers": len(self.blockers),
            "devices": len(self.device_channel_map),
            "channels": sum(d["channels"] for d in self.device_channel_map),
            "multichannel_devices": sum(1 for d in self.device_channel_map
                                        if d["channels"] > 1),
            "sequences": len(self.sequence_architecture),
            "boundary_contracts": len(self.boundary_contracts),
            "unplaced_in_behavior": len(self.unplaced_in_behavior),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "model_kind": MODEL_KIND,
            "project": self.project,
            "readiness": self.readiness(),
            "elements": [e.to_dict() for e in
                         sorted(self.elements, key=lambda e: (e.kind, e.name))],
            "blockers": [b.to_dict() for b in
                         sorted(self.blockers, key=lambda b: b.blocker_id)],
            "device_channel_map": sorted(self.device_channel_map,
                                         key=lambda d: d["tag"]),
            "sequence_architecture": sorted(self.sequence_architecture,
                                            key=lambda s: s["sequence_id"]),
            "boundary_contracts": self.boundary_contracts,
            "unplaced_in_behavior": sorted(self.unplaced_in_behavior),
            "controller_topology": self.controller_topology,
            "plc_allocation": sorted(self.allocation,
                                     key=lambda a: a["subject"]),
            "diagnostics": sorted(self.diagnostics,
                                  key=lambda d: (d.get("code", ""),
                                                 d.get("subject", ""))),
            "summary": self.summary(),
        }


# =============================================================================
# construção
# =============================================================================

def _mapa_dispositivo_canal(plant) -> list:
    """Dispositivo e canal, lado a lado. O invariante permanente do modelo.

    Reduzir um multicanal a um ponto perderia endereços em silêncio — a
    contagem de dispositivos continuaria certa, e é isso que torna o erro
    difícil de ver.
    """
    saida = []
    for ponto in plant.points:
        classes = {c: f.value for c, f in ponto.io_counts.items()
                   if f.usable and f.value}
        saida.append({
            "tag": ponto.tag,
            "equipment": ponto.equipment.value,
            "channels": ponto.total_points,
            "by_class": dict(sorted(classes.items())),
            "is_multichannel": ponto.total_points > 1,
            "is_safety": ponto.is_safety,
            "status": MEASURED,
        })
    return saida


def _bloqueadores(plant, requirements) -> list:
    """Cada lacuna vira bloqueador com IMPACTO rastreado.

    O que ele afeta vem do que foi medido, e não da interpretação da sigla:
    o alcance de `1800FZ` e de `FAT` sai das referências reais do corpus.
    """
    saida = []
    for numero, lacuna in enumerate(plant.blocking_gaps(), start=1):
        classe = {"EDS": "safety_digital_input", "SDS": "safety_digital_output",
                  "ED-CPS": "safety_controller_input",
                  "SD-CPS": "safety_controller_output"}.get(lacuna.subject)
        afetados = ["GVL_IO", "device_channel_map", "io_addressing"]
        if classe:
            afetados.append(SAFETY_GVL)
        saida.append(Blocker(
            blocker_id="BLK-INV-%02d" % numero,
            subject=lacuna.subject, detail=lacuna.detail,
            affected_elements=tuple(afetados),
            blocks_approval=True, blocks_materialization=True,
            origin=lacuna.origin.to_dict() if lacuna.origin else None))

    if requirements is None:
        return saida

    for lacuna in requirements.gaps:
        if lacuna.kind != "documented_pendency":
            continue
        # ALCANCE MEDIDO: as sequências que citam o assunto, não a leitura da
        # sigla. `1800FZ` e `FAT` recebem consequência derivada do corpus.
        baixo = lacuna.detail.lower()
        afetadas = tuple(
            s.sequence_id for s in requirements.sequences
            if any(p in s.name.lower() for p in ("recuper", "falha", "parada"))
            and ("emerg" in baixo or "falta total" in baixo or "fat" in baixo))
        saida.append(Blocker(
            blocker_id="BLK-%s" % lacuna.subject,
            subject=lacuna.subject, detail=lacuna.detail,
            affected_requirements=afetadas,
            affected_elements=(SAFETY_GVL,) if "seguran" in baixo else (),
            blocks_approval=lacuna.blocks_generation,
            blocks_materialization=lacuna.blocks_generation,
            origin=lacuna.origin.to_dict() if lacuna.origin else None))
    return saida


def _elementos(plant, requirements, blockers) -> list:
    """DUTs, GVLs e FBs propostos — cada um com por que existe.

    Nada é criado para "completar um padrão". Uma família de FB só aparece se
    houver equipamento observado que a justifique.
    """
    elementos = []
    ids_seguranca = tuple(b.blocker_id for b in blockers
                          if SAFETY_GVL in b.affected_elements)

    # GVLs por domínio.
    for dominio in GVL_DOMAINS:
        seguranca = dominio == SAFETY_GVL
        elementos.append(Element(
            kind="gvl", name=dominio,
            status=BLOCKED if (seguranca and ids_seguranca) else PROPOSED,
            rationale=("referências e estados documentais de segurança; NÃO "
                       "contém lógica gerada" if seguranca else
                       "separação por domínio funcional; uma GVL única "
                       "acompanharia ownership nenhum"),
            blocked_by=ids_seguranca if seguranca else (),
            sources=("R9.2 inventário",)))

    # DUTs derivados do que foi observado.
    elementos.append(Element(
        kind="dut", name="ST_DeviceChannels", status=DERIVED,
        rationale=("sete dispositivos têm mais de um canal; um DUT por "
                   "dispositivo com um único ponto perderia dezesseis "
                   "endereços"),
        satisfies=tuple(d["tag"] for d in _mapa_dispositivo_canal(plant)
                        if d["is_multichannel"]),
        sources=("R9.2 inventário",)))
    elementos.append(Element(
        kind="dut", name="ST_EquipmentState", status=PROPOSED,
        rationale="estado por equipamento; nove equipamentos observados",
        satisfies=tuple(sorted(e.name for e in plant.equipment)),
        sources=("R9.2 equipamentos",)))

    # FB por FAMÍLIA OBSERVADA, e não por prefixo de TAG.
    familias: dict = {}
    for ponto in plant.generable_points():
        classes = {c for c, f in ponto.io_counts.items() if f.usable and f.value}
        if "digital_output" in classes and "digital_input" in classes:
            chave = "comandado_com_retorno"
        elif "digital_output" in classes:
            chave = "comandado"
        elif "digital_input" in classes:
            chave = "monitorado"
        else:
            continue
        familias.setdefault(chave, []).append(ponto.tag)
    for chave, tags in sorted(familias.items()):
        elementos.append(Element(
            kind="fb", name="FB_%s" % chave.title().replace("_", ""),
            status=PROPOSED,
            rationale=("família derivada das CLASSES de I/O observadas, e não "
                       "de prefixo de TAG nem de descrição aproximada; %d "
                       "dispositivo(s)" % len(tags)),
            satisfies=tuple(sorted(tags)),
            sources=("R9.2 inventário",)))

    if requirements is not None:
        elementos.append(Element(
            kind="fb", name="FB_SequenceState", status=PROPOSED,
            rationale=("%d sequência(s) com tabela de estado exigem máquina de "
                       "estados comum" % sum(1 for s in requirements.sequences
                                             if s.structured)),
            satisfies=tuple(s.sequence_id for s in requirements.sequences
                            if s.structured),
            sources=("R9.3 sequências",)))
    return elementos


def _arquitetura_de_sequencia(requirements, blockers) -> list:
    saida = []
    ids_bloqueio = tuple(b.blocker_id for b in blockers if b.blocks_approval)
    for seq in requirements.sequences:
        estruturada = seq.structured
        saida.append({
            "sequence_id": seq.sequence_id,
            "name": seq.name,
            "status": DERIVED if estruturada else HUMAN_DECISION,
            "sequence_status": ("structured" if estruturada
                                else "requires_human_structuring"),
            "implementation_status": BLOCKED,
            "states": [r.left for r in seq.state_rows] if estruturada else [],
            "referenced_devices": sorted({r.tag for r in seq.point_refs}),
            "boundary_interactions": len(seq.cross_owner),
            "safety_references": len(seq.safety_refs),
            # NUNCA inferidos deste documento.
            "missing": ["transitions", "completion_conditions", "timeouts"],
            "blocked_by": list(ids_bloqueio),
        })
    return saida


def _contratos_de_fronteira(requirements) -> list:
    """As interações viram REQUISITOS de interface, nunca sinais.

    `signals` fica vazia até aprovação humana. Gerar `Req/Ack/Done` por padrão
    inventaria o contrato mais crítico do projeto.
    """
    saida = []
    for seq in requirements.sequences:
        for numero, interacao in enumerate(seq.cross_owner, start=1):
            saida.append({
                "contract_id": "IFC-%s-%02d" % (seq.sequence_id, numero),
                "source_sequence": seq.sequence_id,
                "description": interacao["excerpt"],
                "producer": None,
                "consumer": None,
                "contract_required": True,
                "signals": [],
                "status": HUMAN_DECISION,
                "locator": interacao["locator"],
            })
    return saida


def _topologia(controller_count, controller_ids) -> dict:
    """A topologia de controladores, como FATO com três estados.

    `undeclared` não é `single` nem `multiple`: ausência de declaração é
    afirmação sobre o que ninguém disse, e tratá-la como "um" atribuiria dono a
    65 equipamentos por omissão.

    Com mais de um controlador declarado, a alocação volta a ser humana — saber
    QUANTOS são não diz QUAL recebe o quê.
    """
    ids = tuple(controller_ids or ())
    if controller_count is None:
        return {"state": "undeclared", "count": None, "controller_ids": [],
                "owner_when_single": None,
                "reason": ("topologia de controladores não declarada; alocar "
                           "sem ela seria decidir por omissão")}
    if controller_count == 1:
        # Sem id declarado o dono é o PAPEL, não um nome inventado: um
        # identificador fabricado apareceria no pacote despachado como se
        # tivesse origem no projeto.
        return {"state": "single", "count": 1, "controller_ids": list(ids),
                "owner_when_single": ids[0] if ids else "single_controller",
                "reason": "topologia declarada com um único controlador"}
    return {"state": "multiple", "count": controller_count,
            "controller_ids": list(ids), "owner_when_single": None,
            "reason": ("topologia declarada com %d controladores; saber quantos "
                       "são não diz qual recebe o quê" % controller_count)}


def build_draft(*, plant, requirements=None,
                project: str = "planta",
                controller_count: int | None = None,
                controller_ids: tuple = ()) -> ArchitectureDraft:
    """Monta o rascunho a partir do inventário (R9.2) e das sequências (R9.3).

    `controller_count` é a topologia DECLARADA, e o padrão `None` significa
    *não declarada* — não "zero" e não "um". Sem ela, a alocação continua
    exigindo decisão humana, exatamente como antes.

    Ela é entrada e não leitura: o corpus descreve um controlador, e isso não
    prova que a planta tem um. Derivar a topologia do corpus foi o erro que
    este parâmetro existe para não repetir.
    """
    rascunho = ArchitectureDraft(project=project)
    rascunho.controller_topology = _topologia(controller_count, controller_ids)
    rascunho.device_channel_map = _mapa_dispositivo_canal(plant)
    rascunho.blockers = _bloqueadores(plant, requirements)
    rascunho.elements = _elementos(plant, requirements, rascunho.blockers)

    if requirements is not None:
        rascunho.sequence_architecture = _arquitetura_de_sequencia(
            requirements, rascunho.blockers)
        rascunho.boundary_contracts = _contratos_de_fronteira(requirements)
        # A afirmação medida é "não localizados nas sequências ingeridas".
        # Dizer "sem uso" seria mais forte do que o corpus sustenta.
        rascunho.unplaced_in_behavior = list(requirements.uncited_points)

    # ALOCAÇÃO. Derivada da topologia DECLARADA, nunca do corpus.
    #
    # A versão anterior marcava todo equipamento como `human_decision_required`
    # justificando que "dividir entre CLPs não é sustentado" — e concluía
    # pedindo que um humano dividisse. Com um controlador declarado não há o
    # que dividir: existe exatamente um candidato, e o dono é DERIVADO.
    # Perguntar mesmo assim produziria 65 decisões cuja resposta já é conhecida.
    unico = rascunho.controller_topology["owner_when_single"]
    for equipamento in plant.equipment:
        if unico is not None:
            rascunho.allocation.append({
                "subject": equipamento.name,
                "kind": "equipment",
                "allocation_status": DERIVED,
                "owner": unico,
                "reason": ("topologia declarada com um único controlador; "
                           "o dono é o único candidato existente"),
            })
        else:
            rascunho.allocation.append({
                "subject": equipamento.name,
                "kind": "equipment",
                "allocation_status": HUMAN_DECISION,
                "owner": None,
                "reason": rascunho.controller_topology["reason"],
            })
    return rascunho

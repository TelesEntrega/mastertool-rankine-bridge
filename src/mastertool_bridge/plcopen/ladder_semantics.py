"""Semântica local de uma network Ladder — leituras, escritas e chamadas.

O QUE ESTE MÓDULO FAZ, E O QUE ELE DELIBERADAMENTE NÃO FAZ
=========================================================
Ele transforma elementos gráficos em ACESSOS (`read`, `write`, `read_write`) e
CHAMADAS. Ele **não** resolve símbolo nenhum contra o índice ST: saber se
`ESTADO` é uma variável local, uma GVL ou coisa nenhuma é pergunta de R4.2, e
respondê-la aqui misturaria duas fontes de erro num resultado só.

A REGRA CENTRAL
===============
    ausência de evidência  ≠  ligação provável

Nenhum acesso nasce de proximidade gráfica. Um acesso nasce de:

  * um elemento que CARREGA o nome (contato, bobina), ou
  * uma aresta de topologia com `direction_status: resolved`, que liga um
    terminal a outro.

Pino de bloco sem aresta incidente fica `unbound`. Ele não vira ligação por
estar desenhado ao lado de uma variável — no Ladder, "ao lado" não é uma
relação, é um pixel.

O PROBLEMA QUE DEFINE O SLICE
=============================
`in_variable` chega do parser com `value_source_kind="expression"` SEMPRE,
inclusive quando o texto é um nome. Na mesma network do export real convivem
`ESTADO` e `0`.

Tratar os dois como símbolo inventaria uma leitura da constante `0`. Tratar os
dois como opaco perderia metade das leituras reais. A saída é classificar
LEXICALMENTE, e dizer em que base:

    literal      numérico, TIME, STRING, TRUE/FALSE  → não é acesso
    identifier   identificador IEC, possivelmente pontuado → acesso
    outro        `A + B`, chamada, indexação          → unresolved

`identifier` afirma que o TEXTO é sintaticamente uma referência. Não afirma
que o símbolo existe — isso é R4.2, e a distinção é o que impede este módulo
de promover suposição a fato.

NEGAÇÃO NÃO MUDA O MODO
=======================
Contato NF lê a mesma variável que o NA; bobina negada escreve na mesma. O que
muda é o sentido lógico do valor, não a natureza do acesso. Registrar NF como
"não-leitura" quebraria a pergunta que o modelo existe para responder — "quem
lê isto?" — em troca de nada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
MODEL_KIND = "ladder_network_semantics"

MODES = ("read", "write", "read_write")

# Como o texto de um elemento foi classificado. `literal` e `expression` NÃO
# produzem acesso — e são registrados assim mesmo, porque "não gerou acesso"
# e "não foi olhado" precisam ser distinguíveis por quem lê o resultado.
TEXT_CLASSES = ("identifier", "literal", "expression", "empty")

# De onde veio a conclusão. Fechado de propósito: uma base nova é uma decisão
# de contrato, e decisão de contrato não entra por string solta.
EVIDENCE_BASES = (
    # o elemento carrega o nome no próprio corpo (contato, bobina)
    "element_value_text",
    # o texto foi reconhecido como identificador IEC, sem consultar índice
    "lexical_identifier",
    # uma aresta de topologia resolvida ligou dois terminais
    "resolved_topology_edge",
    # o bloco declara a instância de FB
    "declared_instance",
)

UNRESOLVED_REASONS = (
    "expression_not_a_plain_symbol",
    "element_kind_not_interpreted",
    "unresolved_topology_edge",
    "pin_unbound",
    "block_without_type_name",
)

# Elementos cuja semântica está DEFINIDA neste slice. Um tipo fora daqui não
# recebe interpretação por antecipação — ele vira `unresolved` com o motivo
# nomeado. É a mesma disciplina de `OBSERVED_ELEMENT_KINDS` no canônico:
# ausência de observação não autoriza implementação por suposição.
INTERPRETED_KINDS = frozenset({
    "contact", "coil", "in_variable", "out_variable", "inout_variable",
    "block",
})

# Elementos que existem no modelo e que, por construção, não produzem acesso
# nem chamada. Listá-los é o que impede que virem ruído em `unresolved`.
STRUCTURAL_KINDS = frozenset({
    "left_power_rail", "right_power_rail", "comment", "label",
})

_IDENTIFICADOR = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")

# Literais IEC 61131-3 que aparecem como texto de `in_variable`. A lista é
# de FORMA, não de valor: `T#5s` é literal por ser tempo, não por ser 5.
_LITERAL_NUMERICO = re.compile(
    r"^[+-]?(\d+\.?\d*([eE][+-]?\d+)?|16#[0-9A-Fa-f_]+|2#[01_]+|8#[0-7_]+)$")
_LITERAL_TIPADO = re.compile(
    r"^(T|TIME|D|DATE|TOD|DT|LTIME)#", re.IGNORECASE)
_PALAVRAS_LITERAIS = frozenset({"TRUE", "FALSE"})


def classify_text(texto: str | None) -> str:
    """Classifica o texto de um elemento SEM consultar índice nenhum.

    A ordem importa: `TRUE` casa com a gramática de identificador, e precisa
    ser reconhecido como literal antes disso. Um `read` de `TRUE` seria uma
    variável inventada que nunca existiu no projeto.
    """
    if texto is None or not texto.strip():
        return "empty"
    limpo = texto.strip()
    if limpo.upper() in _PALAVRAS_LITERAIS:
        return "literal"
    if _LITERAL_NUMERICO.match(limpo) or _LITERAL_TIPADO.match(limpo):
        return "literal"
    if limpo.startswith(("'", '"')):
        return "literal"
    if _IDENTIFICADOR.match(limpo):
        return "identifier"
    return "expression"


# =============================================================================
# estruturas
# =============================================================================

@dataclass(frozen=True)
class Evidence:
    """De onde a conclusão veio. Nunca opcional.

    `pou`, `network` e `element` juntos localizam a afirmação no projeto — é o
    que o gate de R4.1 exige de toda conclusão. `basis` diz COMO, e
    `supporting` guarda os ids das arestas ou evidências de conexão.
    """

    pou: str
    network_id: str
    element_id: str
    basis: str
    supporting: tuple = ()
    detail: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.basis not in EVIDENCE_BASES:
            raise ValueError(
                "base de evidência %r fora do vocabulário fechado: %s"
                % (self.basis, ", ".join(EVIDENCE_BASES)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pou": self.pou,
            "network_id": self.network_id,
            "element_id": self.element_id,
            "basis": self.basis,
            "supporting": list(self.supporting),
            "detail": dict(sorted(self.detail.items())),
        }


@dataclass(frozen=True)
class Access:
    symbol: str
    mode: str
    element_id: str
    element_kind: str
    evidence: Evidence

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError("modo %r fora de %s" % (self.mode, list(MODES)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "mode": self.mode,
            "element_id": self.element_id,
            "element_kind": self.element_kind,
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True)
class PinBinding:
    """Um pino do bloco e o que está ligado nele — ou o registro de que nada
    está, que é informação e não ausência de informação."""

    formal_parameter: str
    direction: str
    bound_symbol: str | None = None
    bound_literal: str | None = None
    # `power_flow` é o quarto estado, e o mais importante: a aresta existe e
    # NÃO é ligação de dado. Sem ele, contato e bobina ligados a um bloco
    # viravam operandos, e o bloco passava a "escrever" a variável que o
    # contato apenas lê.
    status: str = "unbound"   # bound_symbol | bound_literal | power_flow | unbound
    evidence: Evidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "formal_parameter": self.formal_parameter,
            "direction": self.direction,
            "status": self.status,
            "bound_symbol": self.bound_symbol,
            "bound_literal": self.bound_literal,
            "evidence": self.evidence.to_dict() if self.evidence else None,
        }


@dataclass(frozen=True)
class Call:
    target: str
    call_type: str
    element_id: str
    instance: str | None = None
    pins: tuple = ()
    evidence: Evidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "call_type": self.call_type,
            "instance": self.instance,
            "element_id": self.element_id,
            "pins": [p.to_dict() for p in self.pins],
            "evidence": self.evidence.to_dict() if self.evidence else None,
        }


@dataclass(frozen=True)
class Unresolved:
    reason: str
    element_id: str | None
    network_id: str
    detail: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.reason not in UNRESOLVED_REASONS:
            raise ValueError(
                "motivo %r fora do vocabulário fechado: %s"
                % (self.reason, ", ".join(UNRESOLVED_REASONS)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "element_id": self.element_id,
            "network_id": self.network_id,
            "detail": dict(sorted(self.detail.items())),
        }


@dataclass
class LadderNetworkSemantics:
    pou: str
    network_id: str
    order: int = 0
    accesses: list = field(default_factory=list)
    calls: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        # Ordenação TOTAL, e por chaves estáveis. O golden file compara bytes,
        # e ordem de dicionário do parser não é contrato de nada.
        return {
            "schema_version": SCHEMA_VERSION,
            "model_kind": MODEL_KIND,
            "pou": self.pou,
            "network_id": self.network_id,
            "order": self.order,
            "accesses": [a.to_dict() for a in sorted(
                self.accesses,
                key=lambda a: (a.symbol, a.mode, a.element_id))],
            "calls": [c.to_dict() for c in sorted(
                self.calls,
                key=lambda c: (c.target, c.instance or "", c.element_id))],
            "diagnostics": sorted(self.diagnostics,
                                  key=lambda d: (d.get("code", ""),
                                                 d.get("element_id") or "")),
            "unresolved": [u.to_dict() for u in sorted(
                self.unresolved,
                key=lambda u: (u.reason, u.element_id or ""))],
        }


@dataclass
class LadderSemantics:
    pou: str
    networks: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "model_kind": MODEL_KIND,
            "pou": self.pou,
            "networks": [n.to_dict() for n in sorted(
                self.networks, key=lambda n: (n.order, n.network_id))],
        }


# =============================================================================
# derivação
# =============================================================================

def _terminais_ligados(topologia_net: dict) -> dict:
    """`(element_id, terminal)` → lista de arestas RESOLVIDAS que chegam/saem.

    Só `direction_status == "resolved"` entra. Uma aresta ambígua descreve uma
    ligação que ninguém conseguiu determinar, e usá-la para criar acesso
    transformaria dúvida em fato — que é precisamente o que a regra central
    proíbe.
    """
    por_no: dict = {}
    for aresta in topologia_net.get("edges", []):
        if aresta.get("direction_status") != "resolved":
            continue
        por_no.setdefault(aresta["source_node_id"], []).append(("out", aresta))
        por_no.setdefault(aresta["target_node_id"], []).append(("in", aresta))
    return por_no


def _no_de(topologia_net: dict) -> dict:
    return {n["node_id"]: n for n in topologia_net.get("nodes", [])}


def _simbolo_do_elemento(elemento) -> tuple:
    """`(classe, texto)` do texto que o elemento carrega."""
    texto = getattr(elemento, "value_text", None)
    return classify_text(texto), (texto or "").strip()


def derive_network_semantics(pou, network, topologia_net: dict
                             ) -> LadderNetworkSemantics:
    """A semântica de UMA network. Determinística e sem estado externo."""
    resultado = LadderNetworkSemantics(
        pou=pou.name, network_id=network.network_id,
        order=getattr(network, "order", 0))

    elementos = {e.element_id: e for e in pou.elements}
    pinos = {p.pin_id: p for p in pou.pins}
    nos = _no_de(topologia_net)
    incidencias = _terminais_ligados(topologia_net)

    def evidencia(element_id, basis, supporting=(), **detalhe):
        return Evidence(pou=pou.name, network_id=network.network_id,
                        element_id=element_id, basis=basis,
                        supporting=tuple(supporting), detail=detalhe)

    for element_id in sorted(network.element_ids):
        elemento = elementos.get(element_id)
        if elemento is None:
            continue
        kind = elemento.kind

        if kind in STRUCTURAL_KINDS:
            continue

        if kind not in INTERPRETED_KINDS:
            resultado.unresolved.append(Unresolved(
                reason="element_kind_not_interpreted",
                element_id=element_id, network_id=network.network_id,
                detail={"element_kind": kind}))
            continue

        if kind in ("contact", "coil"):
            classe, texto = _simbolo_do_elemento(elemento)
            if classe != "identifier":
                resultado.unresolved.append(Unresolved(
                    reason="expression_not_a_plain_symbol",
                    element_id=element_id, network_id=network.network_id,
                    detail={"element_kind": kind, "text_class": classe,
                            "text": texto}))
                continue
            # NEGAÇÃO NÃO MUDA O MODO. Ela é registrada na evidência porque
            # descreve o sentido lógico, e alguém vai querer saber.
            modo = "read" if kind == "contact" else "write"
            resultado.accesses.append(Access(
                symbol=texto, mode=modo, element_id=element_id,
                element_kind=kind,
                evidence=evidencia(
                    element_id, "element_value_text",
                    negated=bool(getattr(elemento, "negated", False)),
                    storage=getattr(elemento, "storage", None) or "none",
                    edge=getattr(elemento, "edge", None) or "none")))
            continue

        if kind in ("in_variable", "out_variable", "inout_variable"):
            classe, texto = _simbolo_do_elemento(elemento)
            if classe == "literal":
                # Literal NÃO é acesso, e também não é problema. Registrar em
                # `unresolved` faria `0` parecer uma falha de análise.
                resultado.diagnostics.append({
                    "code": "literal_operand",
                    "element_id": element_id,
                    "severity": "info",
                    "message": "operando literal %r: não gera acesso" % texto,
                })
                continue
            if classe != "identifier":
                resultado.unresolved.append(Unresolved(
                    reason="expression_not_a_plain_symbol",
                    element_id=element_id, network_id=network.network_id,
                    detail={"element_kind": kind, "text_class": classe,
                            "text": texto}))
                continue
            modo = {"in_variable": "read", "out_variable": "write",
                    "inout_variable": "read_write"}[kind]
            resultado.accesses.append(Access(
                symbol=texto, mode=modo, element_id=element_id,
                element_kind=kind,
                evidence=evidencia(element_id, "lexical_identifier",
                                   text_class=classe)))
            continue

        # --- bloco -----------------------------------------------------------
        alvo = getattr(elemento, "type_name", None)
        if not alvo:
            resultado.unresolved.append(Unresolved(
                reason="block_without_type_name",
                element_id=element_id, network_id=network.network_id))
            continue

        instancia = getattr(elemento, "instance_name", None)
        call_type = getattr(elemento, "call_type", None) or "unknown"

        ligacoes = []
        for pin_id in elemento.pin_ids:
            pino = pinos.get(pin_id)
            if pino is None:
                continue
            node_id = "%s|%s|%s" % (network.network_id,
                                    getattr(elemento, "local_id", None),
                                    pino.formal_parameter)
            incidentes = incidencias.get(node_id, [])
            ligacao = _ligar_pino(
                pino, incidentes, nos, elementos, evidencia, element_id)
            ligacoes.append(ligacao)

            # A LIGAÇÃO NÃO GERA ACESSO. Quem gera é o elemento que CARREGA o
            # nome — o `in_variable`, o contato, a bobina. O pino registra a
            # ligação, e ela vive em `calls[].pins`.
            #
            # A primeira versão criava acesso nos dois lugares, e `ESTADO`
            # aparecia duas vezes na mesma network: uma pelo `in_variable`,
            # outra pelo pino `In2` ligado a ele. Duas linhas para um fato só
            # fazem qualquer contagem de leitores mentir.
            if ligacao.status == "unbound":
                resultado.unresolved.append(Unresolved(
                    reason="pin_unbound", element_id=element_id,
                    network_id=network.network_id,
                    detail={"formal_parameter": pino.formal_parameter,
                            "direction": pino.direction}))

        if instancia:
            # A instância de FB É uma variável do projeto, e chamar o bloco a
            # lê e a escreve: o estado interno persiste entre ciclos.
            resultado.accesses.append(Access(
                symbol=instancia, mode="read_write", element_id=element_id,
                element_kind="block",
                evidence=evidencia(element_id, "declared_instance",
                                   type_name=alvo, call_type=call_type)))

        resultado.calls.append(Call(
            target=alvo, call_type=call_type, element_id=element_id,
            instance=instancia, pins=tuple(ligacoes),
            evidence=evidencia(element_id, "declared_instance"
                               if instancia else "element_value_text",
                               type_name=alvo, call_type=call_type)))

    for aresta in topologia_net.get("edges", []):
        if aresta.get("direction_status") != "resolved":
            resultado.unresolved.append(Unresolved(
                reason="unresolved_topology_edge", element_id=None,
                network_id=network.network_id,
                detail={"edge_id": aresta.get("edge_id"),
                        "direction_status": aresta.get("direction_status")}))

    return resultado


def _ligar_pino(pino, incidentes, nos, elementos, evidencia, dono_id
                ) -> PinBinding:
    """O que está ligado neste pino — ou o registro de que nada está.

    A DISTINÇÃO QUE DEFINE LADDER
    =============================
    Uma aresta que chega num pino pode significar duas coisas completamente
    diferentes, e confundi-las inventa acessos:

    * **operando de dado** — `in_variable` / `out_variable` / `inout_variable`.
      O valor do símbolo entra no pino, ou sai dele. Isto é ligação.
    * **fluxo de energia** — contato ou bobina. A aresta carrega a condição
      booleana do rung, não um valor. O contato já LÊ a própria variável por
      conta própria; a bobina já ESCREVE na dela.

    A primeira versão deste módulo tratou as duas do mesmo jeito e produziu
    `ENTRADA write` a partir de um `EQ.Out1` ligado a um contato `ENTRADA` —
    afirmando que o bloco escrevia na variável que o contato apenas lê. A
    aresta existia; o significado que eu atribuí a ela, não.

    Bloco ligado a bloco propaga um valor intermediário que não tem nome no
    projeto. Inventar um seria criar símbolo do nada.
    """
    esperado = "in" if pino.direction in ("input", "inout") else "out"
    for sentido, aresta in incidentes:
        if sentido != esperado:
            continue
        outro_id = (aresta["source_node_id"] if sentido == "in"
                    else aresta["target_node_id"])
        no = nos.get(outro_id)
        if no is None:
            continue
        elemento = elementos.get(no.get("owner_element_id"))
        if elemento is None:
            continue

        if elemento.kind in ("contact", "coil"):
            return PinBinding(
                formal_parameter=pino.formal_parameter,
                direction=pino.direction, status="power_flow",
                evidence=evidencia(dono_id, "resolved_topology_edge",
                                   supporting=(aresta["edge_id"],),
                                   source_element_id=elemento.element_id,
                                   source_element_kind=elemento.kind))

        if elemento.kind not in ("in_variable", "out_variable",
                                 "inout_variable"):
            continue

        classe, texto = _simbolo_do_elemento(elemento)
        if classe == "identifier":
            return PinBinding(
                formal_parameter=pino.formal_parameter,
                direction=pino.direction, bound_symbol=texto,
                status="bound_symbol",
                evidence=evidencia(dono_id, "resolved_topology_edge",
                                   supporting=(aresta["edge_id"],),
                                   source_element_id=elemento.element_id,
                                   formal_parameter=pino.formal_parameter))
        if classe == "literal":
            return PinBinding(
                formal_parameter=pino.formal_parameter,
                direction=pino.direction, bound_literal=texto,
                status="bound_literal",
                evidence=evidencia(dono_id, "resolved_topology_edge",
                                   supporting=(aresta["edge_id"],),
                                   source_element_id=elemento.element_id))
    return PinBinding(formal_parameter=pino.formal_parameter,
                      direction=pino.direction)


def derive_ladder_semantics(pou, topology) -> LadderSemantics:
    """A semântica de todas as networks de uma POU gráfica."""
    dados = topology.to_dict() if hasattr(topology, "to_dict") else topology
    por_id = {n["network_id"]: n for n in dados.get("networks", [])}
    return LadderSemantics(
        pou=pou.name,
        networks=[derive_network_semantics(pou, net,
                                           por_id.get(net.network_id, {}))
                  for net in pou.networks])

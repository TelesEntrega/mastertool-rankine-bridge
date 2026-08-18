"""R4.2 — resolução dos símbolos Ladder contra o índice estático do projeto.

O QUE ESTE MÓDULO NÃO FAZ, E ISSO É O PRINCIPAL
==============================================
Ele **não implementa precedência de escopo**. A precedência já existe em
`indexer/symbol_resolver.py` — níveis 1/2 (local da POU) → 3 (instância de FB)
→ 4 (GVL explícita, para nomes pontuados) → 5 → 6 → 7 — e é a mesma que o ST
usa há muito tempo.

Uma segunda resolução específica para Ladder divergiria da primeira no dia em
que alguém corrigisse só uma delas, e a divergência apareceria como "o mesmo
símbolo resolve diferente dependendo da linguagem" — a pior forma de defeito
neste projeto, porque cada lado parece certo isoladamente.

Aqui há um ADAPTADOR e nada mais: ele monta o contexto (`PouSymbol` da POU
gráfica), chama o resolvedor de sempre e registra o que voltou.

TRÊS COISAS QUE NUNCA ENTRAM NA RESOLUÇÃO
=========================================
* **`power_flow`** — a aresta entre um bloco e um contato carrega condição de
  rung, não valor. Ela sobrevive como evidência da lógica em `calls[].pins`, e
  tentar resolvê-la criaria um símbolo a partir de um fio.
* **literais** — `0`, `TRUE`, `T#5s` são argumentos. Eles aparecem nos pinos e
  jamais em leitores, escritores ou não-resolvidos.
* **expressões** — R4.1 já as separou; elas chegam aqui como categoria própria
  e não voltam a ser tentadas.

INSTÂNCIA E CHAMADA SÃO FATOS DIFERENTES
========================================
Para `TEMPORIZADOR_0 : TON` existem dois fatos, e colapsá-los perderia um:

    acesso à instância TEMPORIZADOR_0  →  read_write
    chamada para o tipo TON            →  call

A instância pode resolver com o tipo não resolvido, e vice-versa. Os dois
estados são independentes e ambos são registrados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
MODEL_KIND = "resolved_ladder_semantics"

SOURCE_LANGUAGE = "LD"

# Reusados do indexador, e não redefinidos: `resolved`, `partially_resolved`,
# `ambiguous`, `unresolved`. Uma cópia local divergiria no primeiro estado
# novo que o ST ganhasse.
RESOLUTION_STATES = ("resolved", "partially_resolved", "ambiguous",
                     "unresolved")

# As quatro razões pelas quais um identificador não vira símbolo. Elas são
# separadas porque a AÇÃO de correção é diferente em cada uma: um símbolo
# inexistente é erro de projeto; um ambíguo é erro de escopo; uma expressão é
# limitação declarada do analisador; contexto insuficiente é falha de setup.
UNRESOLVED_CATEGORIES = (
    "symbol_not_found",
    "symbol_ambiguous",
    "expression_not_supported",
    "insufficient_context",
)

# `group` do PLCopen → `scope` do indexador. Mapa LITERAL: um grupo que não
# esteja aqui não recebe escopo por semelhança de nome, porque errar o escopo
# muda a precedência de resolução inteira.
#
# `_POU_LOCAL_SCOPE_PREFIXES` do resolvedor aceita qualquer coisa que comece
# com "VAR" e não seja "VAR_GLOBAL" — então os nomes abaixo precisam ser os
# do vocabulário IEC, não invenções.
GROUP_TO_SCOPE = {
    "inputVars": "VAR_INPUT",
    "outputVars": "VAR_OUTPUT",
    "inOutVars": "VAR_IN_OUT",
    "localVars": "VAR",
    "tempVars": "VAR_TEMP",
    "externalVars": "VAR_EXTERNAL",
    "globalVars": "VAR_GLOBAL",
}


# =============================================================================
# adaptação: POU gráfica → símbolo que o resolvedor entende
# =============================================================================

def pou_symbol_from_graphic(pou, *, file: str | None = None):
    """Monta um `PouSymbol` a partir da interface declarada no export gráfico.

    O export PLCopen de uma POU Ladder **carrega as declarações** — foi isso
    que tornou R4.2 possível sem depender do export textual da mesma POU.

    Devolve `(PouSymbol, diagnostics)`. Um grupo fora de `GROUP_TO_SCOPE` NÃO
    vira escopo por aproximação: a variável entra com o grupo cru como escopo
    — que não começa com `VAR` e portanto não conta como local — e o
    diagnóstico nomeia o grupo. O símbolo aparece como não resolvido, que é a
    verdade, em vez de resolver pelo escopo errado.
    """
    from mastertool_bridge.indexer.models import PouSymbol, VariableDeclaration

    diagnosticos = []
    variaveis = []
    for entrada in pou.interface:
        grupo = getattr(entrada, "group", None)
        escopo = GROUP_TO_SCOPE.get(grupo)
        if escopo is None:
            escopo = grupo or "UNKNOWN_GROUP"
            diagnosticos.append({
                "code": "interface_group_not_mapped",
                "severity": "warning",
                "message": ("grupo %r da interface não está em GROUP_TO_SCOPE; "
                            "a variável %r não contará como local da POU"
                            % (grupo, getattr(entrada, "name", None))),
            })
        declarado = getattr(entrada, "declared_type", None)
        if declarado is None:  # entrada de outro produtor, sem a propriedade
            declarado = getattr(entrada, "type_name", None) or ""
        if getattr(entrada, "type_kind", None) == "derived" and not (
                getattr(entrada, "type_name", None)):
            diagnosticos.append({
                "code": "derived_type_without_name",
                "severity": "warning",
                "message": ("a variável %r declara tipo derivado sem nome no "
                            "documento; ela não poderá casar com um tipo do "
                            "índice" % getattr(entrada, "name", None)),
            })
        variaveis.append(VariableDeclaration(
            name=entrada.name, declared_type=declarado, scope=escopo))

    simbolo = PouSymbol(
        node_id="ld:%s" % pou.name,
        pou_kind=_POU_KIND.get(pou.pou_type, pou.pou_type or "unknown"),
        name=pou.name,
        file=file or (pou.source_file or ""),
        variables=variaveis)
    return simbolo, diagnosticos


_POU_KIND = {
    "functionBlock": "FUNCTION_BLOCK",
    "program": "PROGRAM",
    "function": "FUNCTION",
}


# =============================================================================
# estruturas
# =============================================================================

@dataclass(frozen=True)
class ResolvedAccess:
    access_id: str
    symbol_text: str
    mode: str
    resolution_status: str
    source_language: str = SOURCE_LANGUAGE
    resolved_symbol_id: str | None = None
    declaration_scope: str | None = None
    declared_type: str | None = None
    address: str | None = None
    candidates: tuple = ()
    unresolved_category: str | None = None
    rule_applied: str | None = None
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_id": self.access_id,
            "symbol_text": self.symbol_text,
            "mode": self.mode,
            "resolution_status": self.resolution_status,
            "source_language": self.source_language,
            "resolved_symbol_id": self.resolved_symbol_id,
            "declaration_scope": self.declaration_scope,
            "declared_type": self.declared_type,
            "address": self.address,
            "candidates": list(self.candidates),
            "unresolved_category": self.unresolved_category,
            "rule_applied": self.rule_applied,
            "evidence": dict(sorted(self.evidence.items())),
        }


@dataclass(frozen=True)
class ResolvedCall:
    call_id: str
    target_text: str
    call_kind: str
    resolution_status: str
    source_language: str = SOURCE_LANGUAGE
    resolved_target_id: str | None = None
    instance_symbol_text: str | None = None
    instance_resolution_status: str | None = None
    instance_symbol_id: str | None = None
    pins: tuple = ()
    unresolved_category: str | None = None
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "target_text": self.target_text,
            "call_kind": self.call_kind,
            "resolution_status": self.resolution_status,
            "source_language": self.source_language,
            "resolved_target_id": self.resolved_target_id,
            "instance_symbol_text": self.instance_symbol_text,
            "instance_resolution_status": self.instance_resolution_status,
            "instance_symbol_id": self.instance_symbol_id,
            "pins": [dict(sorted(p.items())) for p in self.pins],
            "unresolved_category": self.unresolved_category,
            "evidence": dict(sorted(self.evidence.items())),
        }


@dataclass
class ResolvedLadderSemantics:
    pou: str
    accesses: list = field(default_factory=list)
    calls: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "model_kind": MODEL_KIND,
            "pou": self.pou,
            "accesses": [a.to_dict() for a in sorted(
                self.accesses, key=lambda a: a.access_id)],
            "calls": [c.to_dict() for c in sorted(
                self.calls, key=lambda c: c.call_id)],
            "diagnostics": sorted(
                self.diagnostics,
                key=lambda d: (d.get("code", ""), d.get("message", ""))),
            "unresolved": sorted(
                self.unresolved,
                key=lambda u: (u.get("category", ""), u.get("symbol_text") or "",
                               u.get("access_id") or "")),
        }


# =============================================================================
# resolução
# =============================================================================

def _access_id(pou: str, network_id: str, element_id: str, symbol: str,
               mode: str) -> str:
    """Identidade SEMÂNTICA do acesso.

    Inclui o elemento porque dois contatos da MESMA variável na MESMA network
    são dois usos reais — o operador desenhou dois, e uma consulta de leitores
    tem de mostrar dois. Não inclui pino nem aresta: essas são representações
    do mesmo fato, e contá-las multiplicaria um uso por quantas evidências ele
    tem.
    """
    return "%s|%s|%s|%s|%s" % (pou, network_id, element_id, symbol, mode)


def _classificar_estado(ref) -> tuple:
    """`(status, categoria)` a partir do que o resolvedor devolveu."""
    estado = ref.state
    if estado == "resolved":
        return "resolved", None
    if estado == "ambiguous":
        return "ambiguous", "symbol_ambiguous"
    if estado == "partially_resolved":
        return "partially_resolved", "symbol_not_found"
    return "unresolved", "symbol_not_found"


def resolve_ladder_semantics(semantics, index, owner_pou,
                             extra_diagnostics=()) -> ResolvedLadderSemantics:
    """Resolve os acessos e chamadas de uma POU Ladder contra `index`.

    `owner_pou` pode ser `None` — e isso não é erro, é contexto insuficiente:
    sem a POU dona, os níveis 1/2 e 3 da precedência não têm onde procurar, e
    todo símbolo local vira `insufficient_context` em vez de `not_found`. As
    duas coisas exigem ações diferentes de quem lê o diagnóstico.
    """
    from mastertool_bridge.indexer.symbol_resolver import (
        resolve_callable_target,
        resolve_dotted_reference,
        resolve_identifier,
    )

    dados = semantics.to_dict() if hasattr(semantics, "to_dict") else semantics
    resultado = ResolvedLadderSemantics(pou=dados["pou"])
    resultado.diagnostics.extend(extra_diagnostics)

    def resolver(texto: str):
        if owner_pou is None:
            return None
        if "." in texto:
            return resolve_dotted_reference(texto, owner_pou, index)
        return resolve_identifier(texto, owner_pou, index)

    def registrar_aberto(categoria, **campos):
        resultado.unresolved.append(dict(sorted(
            {"category": categoria, **campos}.items())))

    for net in dados["networks"]:
        network_id = net["network_id"]

        # EXPRESSÕES não voltam a ser tentadas: R4.1 já as classificou, e
        # tentar resolvê-las aqui seria refazer a decisão dele com menos
        # informação.
        for aberto in net["unresolved"]:
            if aberto["reason"] == "expression_not_a_plain_symbol":
                registrar_aberto(
                    "expression_not_supported",
                    symbol_text=aberto["detail"].get("text"),
                    network_id=network_id,
                    element_id=aberto["element_id"],
                    detail=aberto["detail"].get("text_class"))

        for acesso in net["accesses"]:
            texto = acesso["symbol"]
            aid = _access_id(dados["pou"], network_id, acesso["element_id"],
                             texto, acesso["mode"])
            evidencia = dict(acesso["evidence"])
            evidencia["element_kind"] = acesso["element_kind"]

            ref = resolver(texto)
            if ref is None:
                resultado.accesses.append(ResolvedAccess(
                    access_id=aid, symbol_text=texto, mode=acesso["mode"],
                    resolution_status="unresolved",
                    unresolved_category="insufficient_context",
                    evidence=evidencia))
                registrar_aberto("insufficient_context", symbol_text=texto,
                                 network_id=network_id, access_id=aid)
                continue

            status, categoria = _classificar_estado(ref)
            variavel = getattr(ref, "variable", None)
            resultado.accesses.append(ResolvedAccess(
                access_id=aid, symbol_text=texto, mode=acesso["mode"],
                resolution_status=status,
                resolved_symbol_id=ref.resolved_symbol,
                declaration_scope=getattr(variavel, "scope", None),
                declared_type=getattr(variavel, "declared_type", None),
                candidates=tuple(ref.candidates),
                unresolved_category=categoria,
                rule_applied=ref.rule_applied,
                evidence=evidencia))
            if categoria:
                registrar_aberto(categoria, symbol_text=texto,
                                 network_id=network_id, access_id=aid,
                                 candidates=list(ref.candidates))

        for chamada in net["calls"]:
            cid = "%s|%s|%s" % (dados["pou"], network_id,
                                chamada["element_id"])
            alvo = chamada["target"]
            instancia = chamada["instance"]

            # O TIPO. Um operador (`EQ`, `MOVE`) não é POU do projeto: ele é
            # do padrão IEC, e procurá-lo no índice devolveria "inexistente"
            # sobre algo que existe — só não aqui.
            if chamada["call_type"] == "operator":
                status_alvo, alvo_id, categoria_alvo = (
                    "not_applicable", None, None)
                candidatos_alvo = []
            else:
                # O MESMO serviço que o ST usa. Procurar aqui só entre
                # FUNCTION_BLOCKs — o que este ramo fazia — deixava toda
                # chamada a PROGRAM como símbolo inexistente, com a POU
                # presente no índice: 21 casos no projeto real medido.
                ref_alvo = resolve_callable_target(alvo, index)
                status_alvo = ref_alvo.state
                alvo_id = ref_alvo.resolved_symbol
                candidatos_alvo = list(ref_alvo.candidates)
                categoria_alvo = {
                    "ambiguous": "symbol_ambiguous",
                    "unresolved": "symbol_not_found",
                }.get(ref_alvo.state)
                if categoria_alvo:
                    registrar_aberto(categoria_alvo, symbol_text=alvo,
                                     network_id=network_id, call_id=cid,
                                     candidates=candidatos_alvo,
                                     detail="call_target")

            # A INSTÂNCIA, resolvida em separado. Ela pode existir com o tipo
            # ausente, e o tipo pode existir com a instância não declarada.
            status_inst, inst_id = None, None
            if instancia:
                ref_inst = resolver(instancia)
                if ref_inst is None:
                    status_inst = "unresolved"
                else:
                    status_inst = _classificar_estado(ref_inst)[0]
                    inst_id = ref_inst.resolved_symbol

            resultado.calls.append(ResolvedCall(
                call_id=cid, target_text=alvo,
                call_kind=chamada["call_type"],
                resolution_status=status_alvo,
                resolved_target_id=alvo_id,
                instance_symbol_text=instancia,
                instance_resolution_status=status_inst,
                instance_symbol_id=inst_id,
                # PINOS preservados como vieram. `power_flow` sobrevive aqui
                # como evidência da lógica — e nunca é oferecido à resolução.
                pins=tuple(chamada["pins"]),
                unresolved_category=categoria_alvo,
                evidence={"network_id": network_id,
                          "element_id": chamada["element_id"]}))

    return resultado


# =============================================================================
# consultas — a camada unificada ST + Ladder
# =============================================================================

def _fato_ladder(acesso: ResolvedAccess) -> dict:
    return {
        "source_language": SOURCE_LANGUAGE,
        "symbol_text": acesso.symbol_text,
        "mode": acesso.mode,
        "access_id": acesso.access_id,
        "resolution_status": acesso.resolution_status,
        "resolved_symbol_id": acesso.resolved_symbol_id,
        "network_id": acesso.evidence.get("network_id"),
        "element_id": acesso.evidence.get("element_id"),
        "pou": acesso.evidence.get("pou"),
    }


class UnifiedSymbolView:
    """Consulta sobre ST e Ladder ao mesmo tempo, sem fundir as origens.

    Cada fato carrega `source_language` e a origem exata. Perder isso tornaria
    impossível responder "esta variável é escrita nas duas linguagens?", que é
    justamente a pergunta que a camada existe para responder.

    Ela NÃO reescreve os artefatos do ST: consome `resolved_references` já
    calculado por `indexer/reference_resolver.resolve_references`.
    """

    def __init__(self, ladder=None, st_resolved_references=()) -> None:
        self._ladder = list(ladder.accesses) if ladder is not None else []
        self._st = list(st_resolved_references)

    # --- ST -----------------------------------------------------------------

    def _fatos_st(self, modos) -> list:
        saida = []
        for rr in self._st:
            if rr.classification not in modos:
                continue
            referencia = rr.reference
            saida.append({
                "source_language": "ST",
                "symbol_text": referencia.name,
                "mode": rr.classification,
                "resolution_status": rr.resolution_state,
                "resolved_symbol_id": rr.resolved_symbol,
                "node_id": referencia.node_id,
                "file": referencia.file,
                "location": referencia.location.to_dict()
                if referencia.location else None,
            })
        return saida

    # --- consultas ----------------------------------------------------------

    def writers(self, symbol: str) -> list:
        """Quem ESCREVE o símbolo, nas duas linguagens.

        Conta fatos únicos — não arestas, não evidências. Um contato e um pino
        que apontam para o mesmo uso são um escritor, não dois.
        """
        modos = ("write", "read_write")
        ladder = [_fato_ladder(a) for a in self._ladder
                  if a.symbol_text == symbol and a.mode in modos]
        st = [f for f in self._fatos_st(modos) if f["symbol_text"] == symbol]
        return sorted(ladder + st, key=_ordem_do_fato)

    def readers(self, symbol: str) -> list:
        modos = ("read", "read_write")
        ladder = [_fato_ladder(a) for a in self._ladder
                  if a.symbol_text == symbol and a.mode in modos]
        st = [f for f in self._fatos_st(modos) if f["symbol_text"] == symbol]
        return sorted(ladder + st, key=_ordem_do_fato)

    def multi_writers(self) -> dict:
        """Símbolos com mais de um escritor. O caso que mais importa em campo:
        duas lógicas comandando a mesma saída."""
        por_simbolo: dict = {}
        for simbolo in self.symbols():
            escritores = self.writers(simbolo)
            if len(escritores) > 1:
                por_simbolo[simbolo] = escritores
        return dict(sorted(por_simbolo.items()))

    def cross_language(self) -> dict:
        """Símbolos que aparecem em ST **e** em Ladder, com as origens
        separadas."""
        saida: dict = {}
        for simbolo in self.symbols():
            fatos = self.readers(simbolo) + self.writers(simbolo)
            linguagens = {f["source_language"] for f in fatos}
            if len(linguagens) > 1:
                saida[simbolo] = {
                    "languages": sorted(linguagens),
                    "facts": sorted(fatos, key=_ordem_do_fato),
                }
        return dict(sorted(saida.items()))

    def ladder_calls(self, target: str | None = None) -> list:
        chamadas = getattr(self, "_calls", [])
        return sorted(
            [c.to_dict() for c in chamadas
             if target is None or c.target_text == target],
            key=lambda c: c["call_id"])

    def symbols(self) -> list:
        nomes = {a.symbol_text for a in self._ladder}
        nomes |= {rr.reference.name for rr in self._st}
        return sorted(nomes)

    def with_calls(self, ladder) -> UnifiedSymbolView:
        self._calls = list(ladder.calls)
        return self


def _ordem_do_fato(fato: dict) -> tuple:
    return (fato["source_language"], fato["symbol_text"], fato["mode"],
            fato.get("access_id") or fato.get("node_id") or "")

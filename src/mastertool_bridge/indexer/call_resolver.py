"""Resolução de `Call` (calls.json) contra símbolos conhecidos do projeto.

Produz duas visões:

  - `resolve_calls`: para cada `Call` já extraída, decide se o `callee`
    resolve para um `PouSymbol` conhecido (instância de FUNCTION_BLOCK,
    FUNCTION direta, PROGRAM direto, ou fica ambiguous/unresolved),
    preservando node_id, localização e a regra aplicada -> vira
    `resolved-calls.json`. PROGRAM é um alvo de chamada válido e comum no
    dialeto CODESYS: uma PROGRAM pode chamar outra PROGRAM diretamente pelo
    NOME (sem instância local), diferente de FUNCTION_BLOCK que sempre
    precisa de uma variável de instância declarada na POU chamadora.
  - `build_callers_index`: a partir do resultado de `resolve_calls`, monta
    o índice invertido alvo -> lista de sites de chamada, incluindo
    SOMENTE chamadas com resolution_state="resolved" -> `callers.json`.

Chamadas de método (`callee` com ".") são tratadas com uma limitação
explícita e documentada: o modelo de dados desta fase não tem acesso à
árvore de métodos de um FUNCTION_BLOCK, então nunca afirmamos que um
método existe — o resultado fica "ambiguous"/"unresolved" com um
Diagnostic explicando o motivo. O PREFIXO da chamada (tudo antes do
ÚLTIMO segmento, ex. "GVL_Processo.InstanciaFB" em
"GVL_Processo.InstanciaFB.AlgumMetodo") é resolvido pela cadeia
generalizada de `symbol_resolver.resolve_dotted_reference`, que suporta
2+ segmentos (GVL-qualificado ou instância local simples) — mas o método
em si nunca é confirmado, então a chamada completa nunca fica "resolved".

Nunca lança exceção; toda ambiguidade/limitação vira diagnóstico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mastertool_bridge.indexer.diagnostics import DiagnosticsCollector
from mastertool_bridge.indexer.models import Call
from mastertool_bridge.indexer.symbol_resolver import (
    ProjectSymbolIndex,
    ResolvedSymbolRef,
    fb_candidates_for_declared_type,
    find_pou_local_variable,
    owner_node_id_from_node_id,
    resolve_dotted_reference,
)


@dataclass
class ResolvedCall:
    call: Call
    resolution_state: str
    resolved_symbol: str | None
    candidates: list[str] = field(default_factory=list)
    rule_applied: str = "none"

    def to_dict(self) -> dict[str, Any]:
        data = self.call.to_dict()
        data["resolution_state"] = self.resolution_state
        data["resolved_symbol"] = self.resolved_symbol
        data["candidates"] = list(self.candidates)
        data["rule_applied"] = self.rule_applied
        return data


def resolve_calls(
    calls: list[Call], index: ProjectSymbolIndex
) -> tuple[list[ResolvedCall], DiagnosticsCollector]:
    diags = DiagnosticsCollector()
    resolved: list[ResolvedCall] = []

    for call in calls:
        owner_node_id = owner_node_id_from_node_id(call.node_id)
        owner_pou = index.pou_by_node_id(owner_node_id)
        rc = _resolve_one_call(call, owner_pou, index, diags)
        resolved.append(rc)

    resolved.sort(
        key=lambda rc: (
            rc.call.node_id,
            rc.call.location.line if rc.call.location else 0,
            rc.call.location.column if rc.call.location else 0,
        )
    )
    return resolved, diags


def _resolve_one_call(
    call: Call,
    owner_pou,
    index: ProjectSymbolIndex,
    diags: DiagnosticsCollector,
) -> ResolvedCall:
    callee = call.callee

    if "." in callee:
        return _resolve_method_call(call, owner_pou, index, diags)

    # callee sem ponto: FB instance (nível 3) ou FUNCTION direta.
    if owner_pou is not None:
        state, matches = find_pou_local_variable(owner_pou, callee)
        if state == "ambiguous":
            diags.warning(
                "ambiguous_call_target",
                f"Chamada a {callee!r}: identificador ambíguo (shadowing "
                f"intra-POU em {owner_pou.name!r}).",
                call.location,
                call.node_id,
            )
            return ResolvedCall(
                call=call,
                resolution_state="ambiguous",
                resolved_symbol=None,
                candidates=[owner_pou.node_id],
                rule_applied="pou_local_shadowing",
            )
        if state == "resolved":
            var = matches[0]
            fb_candidates = index.function_blocks_by_name.get(var.declared_type, [])
            if len(fb_candidates) == 1:
                return ResolvedCall(
                    call=call,
                    resolution_state="resolved",
                    resolved_symbol=fb_candidates[0].node_id,
                    rule_applied="fb_instance",
                )
            if len(fb_candidates) > 1:
                diags.warning(
                    "ambiguous_call_target",
                    f"Chamada a {callee!r}: tipo {var.declared_type!r} bate "
                    "com mais de um FUNCTION_BLOCK conhecido.",
                    call.location,
                    call.node_id,
                )
                return ResolvedCall(
                    call=call,
                    resolution_state="ambiguous",
                    resolved_symbol=None,
                    candidates=[s.node_id for s in fb_candidates],
                    rule_applied="fb_instance",
                )
            # Variável local existe mas não é instância de FB conhecido —
            # não é uma chamada válida contra este modelo; segue para
            # FUNCTION direta/unresolved abaixo (variável comum não pode
            # ser "chamada").

    function_candidates = index.functions_by_name.get(callee, [])
    if len(function_candidates) == 1:
        return ResolvedCall(
            call=call,
            resolution_state="resolved",
            resolved_symbol=function_candidates[0].node_id,
            rule_applied="function_direct",
        )
    if len(function_candidates) > 1:
        diags.warning(
            "ambiguous_call_target",
            f"Chamada a {callee!r}: mais de uma FUNCTION conhecida com "
            "este nome.",
            call.location,
            call.node_id,
        )
        return ResolvedCall(
            call=call,
            resolution_state="ambiguous",
            resolved_symbol=None,
            candidates=[s.node_id for s in function_candidates],
            rule_applied="function_direct",
        )

    # PROGRAM direto: no dialeto CODESYS uma PROGRAM chama outra PROGRAM
    # diretamente pelo NOME, sem precisar de uma variável de instância local
    # (diferente de FUNCTION_BLOCK, tratado acima via find_pou_local_variable
    # + declared_type). Mesma lógica defensiva de resolved/ambiguous da
    # FUNCTION direta acima — nunca escolhe arbitrariamente entre 2+ PROGRAMs
    # com o mesmo nome (não deveria ocorrer num projeto real, mas não
    # adivinhamos).
    program_candidates = index.programs_by_name.get(callee, [])
    if len(program_candidates) == 1:
        return ResolvedCall(
            call=call,
            resolution_state="resolved",
            resolved_symbol=program_candidates[0].node_id,
            rule_applied="program_direct",
        )
    if len(program_candidates) > 1:
        diags.warning(
            "ambiguous_call_target",
            f"Chamada a {callee!r}: mais de uma PROGRAM conhecida com "
            "este nome.",
            call.location,
            call.node_id,
        )
        return ResolvedCall(
            call=call,
            resolution_state="ambiguous",
            resolved_symbol=None,
            candidates=[s.node_id for s in program_candidates],
            rule_applied="program_direct",
        )

    diags.info(
        "unresolved_call_target",
        f"Chamada a {callee!r}: nenhum símbolo correspondente (instância "
        "de FUNCTION_BLOCK, FUNCTION ou PROGRAM) foi encontrado.",
        call.location,
        call.node_id,
    )
    return ResolvedCall(
        call=call,
        resolution_state="unresolved",
        resolved_symbol=None,
        rule_applied="none",
    )


def _resolve_method_call(
    call: Call,
    owner_pou,
    index: ProjectSymbolIndex,
    diags: DiagnosticsCollector,
) -> ResolvedCall:
    """Chamada de método `Prefixo.Metodo(...)`, onde `Prefixo` pode ser uma
    cadeia GVL-qualificada de 2+ segmentos (ex.
    "GVL_Processo.InstanciaFB.AlgumMetodo" -> prefixo
    "GVL_Processo.InstanciaFB", método "AlgumMetodo") ou uma instância LOCAL
    simples (ex. "fbTimer.Reset" -> prefixo "fbTimer"). O ÚLTIMO segmento do
    callee é sempre o nome do método/função sendo chamado, tratado como
    "unverifiable" quando o prefixo resolve para uma instância de FB
    conhecida (este modelo de dados não tem acesso à árvore de métodos) —
    resultado final é sempre "ambiguous" ou "unresolved" para o callee
    completo, jamais "resolved", mesmo quando o PREFIXO resolve com
    confiança total (`resolved`) via a resolução generalizada de cadeia."""
    prefix, _, method_name = call.callee.rpartition(".")

    if not prefix:
        # Callee sem ponto não deveria cair aqui (`_resolve_one_call` só
        # despacha para `_resolve_method_call` quando há "." no callee),
        # mas mantém o comportamento defensivo de sempre, sem lançar.
        diags.info(
            "unresolved_call_target",
            f"Chamada de método {call.callee!r}: prefixo de instância vazio.",
            call.location,
            call.node_id,
        )
        return ResolvedCall(
            call=call,
            resolution_state="unresolved",
            resolved_symbol=None,
            rule_applied="none",
        )

    prefix_result = resolve_dotted_reference(prefix, owner_pou, index)

    if prefix_result.state == "unresolved":
        diags.info(
            "unresolved_call_target",
            f"Chamada de método {call.callee!r}: prefixo {prefix!r} não "
            "encontrado (nem variável/instância local, nem GVL/cadeia "
            "conhecida).",
            call.location,
            call.node_id,
        )
        return ResolvedCall(
            call=call,
            resolution_state="unresolved",
            resolved_symbol=None,
            rule_applied="none",
        )
    if prefix_result.state == "ambiguous":
        diags.warning(
            "ambiguous_call_target",
            f"Chamada de método {call.callee!r}: prefixo {prefix!r} "
            "ambíguo.",
            call.location,
            call.node_id,
        )
        return ResolvedCall(
            call=call,
            resolution_state="ambiguous",
            resolved_symbol=None,
            candidates=list(prefix_result.candidates)
            or ([prefix_result.resolved_symbol] if prefix_result.resolved_symbol else []),
            rule_applied=prefix_result.rule_applied or "pou_local_shadowing",
        )
    if prefix_result.state == "partially_resolved":
        # Prefixo só parcialmente confirmado (ex. instância de tipo
        # desconhecido, ou membro intermediário não encontrado) -- não há
        # instância de FB confirmada para tratar o método como
        # "unverifiable contra um tipo conhecido"; a chamada inteira fica
        # unresolved (nunca inventamos uma instância a partir de um prefixo
        # incompleto).
        diags.info(
            "unresolved_call_target",
            f"Chamada de método {call.callee!r}: prefixo {prefix!r} "
            f"apenas parcialmente resolvido ({prefix_result.reason}).",
            call.location,
            call.node_id,
        )
        return ResolvedCall(
            call=call,
            resolution_state="unresolved",
            resolved_symbol=None,
            rule_applied="none",
        )

    # prefix_result.state == "resolved": determina se o prefixo é uma
    # instância de FUNCTION_BLOCK conhecida (única forma de tratar o método
    # como "unverifiable" em vez de simplesmente unresolved).
    fb_candidates: list = []
    if prefix_result.fb_type_symbol is not None:
        fb_candidates = [prefix_result.fb_type_symbol]
    elif prefix_result.variable is not None:
        fb_candidates = fb_candidates_for_declared_type(
            prefix_result.variable.declared_type, index
        )

    if not fb_candidates:
        diags.info(
            "unresolved_call_target",
            f"Chamada de método {call.callee!r}: {prefix!r} não é uma "
            "instância de FUNCTION_BLOCK conhecida.",
            call.location,
            call.node_id,
        )
        return ResolvedCall(
            call=call,
            resolution_state="unresolved",
            resolved_symbol=None,
            rule_applied="none",
        )

    # Instância resolvida, mas o método em si não é verificável neste
    # modelo de dados (metodos são objetos-filhos separados na árvore, sem
    # acesso direto aqui) — nunca afirmamos "resolved" para o callee.
    diags.warning(
        "unverifiable_method_call",
        f"Chamada de método {call.callee!r}: prefixo {prefix!r} resolvido "
        f"para {fb_candidates[0].node_id!r}, mas não é possível confirmar "
        f"que o método {method_name!r} existe naquele tipo neste modelo de "
        "dados (métodos não são acessíveis nesta fase).",
        call.location,
        call.node_id,
    )
    return ResolvedCall(
        call=call,
        resolution_state="ambiguous",
        resolved_symbol=None,
        candidates=[s.node_id for s in fb_candidates],
        rule_applied="fb_instance_method_unverifiable",
    )


def build_callers_index(resolved_calls: list[ResolvedCall]) -> dict[str, list[dict[str, Any]]]:
    """Índice invertido: node_id de PouSymbol alvo -> lista de sites de
    chamada (apenas chamadas resolution_state="resolved")."""
    index: dict[str, list[dict[str, Any]]] = {}
    for rc in resolved_calls:
        if rc.resolution_state != "resolved" or rc.resolved_symbol is None:
            continue
        call = rc.call
        entry = {
            "node_id": call.node_id,
            "file": call.file,
            "callee": call.callee,
            "location": call.location.to_dict() if call.location else None,
            "rule_applied": rc.rule_applied,
        }
        index.setdefault(rc.resolved_symbol, []).append(entry)

    for entries in index.values():
        entries.sort(
            key=lambda e: (
                e["node_id"],
                e["location"]["line"] if e["location"] else 0,
                e["location"]["column"] if e["location"] else 0,
            )
        )
    return dict(sorted(index.items()))

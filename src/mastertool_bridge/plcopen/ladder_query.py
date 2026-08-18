"""R4.3 — a API pública de consulta sobre a semântica Ladder.

O QUE ELA CONSOME, E O QUE ELA NÃO PODE FAZER
=============================================
Ela consome **exclusivamente** os resultados de R4.1 (semântica local) e R4.2
(resolução). Ela não abre XML, não chama o parser e não deriva topologia.

Isso não é organização de arquivos — é a garantia de que as quatro superfícies
(API, CLI, MCP, relatório) respondem a mesma coisa. Se esta camada pudesse
inferir algo por conta própria, cada superfície poderia inferir diferente, e
"o CLI disse outra coisa" viraria um bug impossível de localizar.

Há um teste que varre este módulo procurando importação do parser.

FATO, DIAGNÓSTICO, LIMITAÇÃO E CONTEXTO SÃO COISAS DIFERENTES
=============================================================
    fato          `SAIDA_A` tem dois escritores
    diagnóstico   `TEMPORIZADOR_0` não foi localizado
    limitação     tal expressão ainda não é suportada
    contexto      o índice necessário não foi fornecido

Agrupar os quatro como "erro" faria alguém procurar defeito de projeto onde há
falta de setup — e ignorar o primeiro, que não é problema nenhum.
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1

# Como cada categoria deve ser APRESENTADA. O vocabulário de diagnóstico é o
# de R4.2; o que este mapa acrescenta é a natureza — e ela decide em que
# seção do relatório a linha aparece.
CATEGORY_NATURE = {
    "symbol_not_found": "diagnostic",
    "symbol_ambiguous": "diagnostic",
    "expression_not_supported": "limitation",
    "insufficient_context": "context",
}


class LadderQuery:
    """Consulta estável sobre uma POU Ladder já analisada e resolvida."""

    def __init__(self, semantics, resolved, st_resolved_references=()) -> None:
        from mastertool_bridge.plcopen.ladder_resolution import (
            UnifiedSymbolView,
        )

        self._semantics = (semantics.to_dict()
                           if hasattr(semantics, "to_dict") else semantics)
        self._resolved = resolved
        self._view = UnifiedSymbolView(
            ladder=resolved,
            st_resolved_references=st_resolved_references).with_calls(resolved)

    # --- identidade ---------------------------------------------------------

    @property
    def pou(self) -> str:
        return self._semantics["pou"]

    def networks(self) -> list:
        return [n["network_id"] for n in self._semantics["networks"]]

    # --- consultas por símbolo ---------------------------------------------

    def writers(self, symbol: str) -> list:
        return self._view.writers(symbol)

    def readers(self, symbol: str) -> list:
        return self._view.readers(symbol)

    def calls(self, target: str | None = None) -> list:
        return self._view.ladder_calls(target)

    def multi_writers(self) -> dict:
        return self._view.multi_writers()

    def cross_language(self) -> dict:
        return self._view.cross_language()

    def symbols(self) -> list:
        return self._view.symbols()

    def unresolved(self) -> dict:
        """Por categoria, com a NATUREZA de cada uma.

        Devolver uma lista plana faria "não existe" e "não foi fornecido"
        pedirem a mesma ação de quem lê, e elas são diferentes.
        """
        por_categoria: dict = {}
        for aberto in self._resolved.to_dict()["unresolved"]:
            por_categoria.setdefault(aberto["category"], []).append(aberto)
        return {
            "count": sum(len(v) for v in por_categoria.values()),
            "by_category": {
                categoria: {
                    "nature": CATEGORY_NATURE.get(categoria, "diagnostic"),
                    "items": por_categoria[categoria],
                }
                for categoria in sorted(por_categoria)},
        }

    # --- consultas por lugar ------------------------------------------------

    def network_semantics(self, network_id: str) -> dict:
        """Tudo que acontece numa network, já resolvido."""
        local = next((n for n in self._semantics["networks"]
                      if n["network_id"] == network_id), None)
        if local is None:
            return {"error": "network_not_found", "network_id": network_id,
                    "known_networks": self.networks()}

        acessos = [a.to_dict() for a in self._resolved.accesses
                   if a.evidence.get("network_id") == network_id]
        chamadas = [c.to_dict() for c in self._resolved.calls
                    if c.evidence.get("network_id") == network_id]
        abertos = [u for u in self._resolved.to_dict()["unresolved"]
                   if u.get("network_id") == network_id]

        def por_modo(modo):
            return sorted(a for a in {x["symbol_text"] for x in acessos
                                      if x["mode"] == modo})

        return {
            "schema_version": SCHEMA_VERSION,
            "pou": self.pou,
            "network_id": network_id,
            "order": local["order"],
            "reads": por_modo("read"),
            "writes": por_modo("write"),
            "read_write": por_modo("read_write"),
            "accesses": sorted(acessos, key=lambda a: a["access_id"]),
            "calls": sorted(chamadas, key=lambda c: c["call_id"]),
            "diagnostics": local["diagnostics"],
            "unresolved": sorted(
                abertos, key=lambda u: (u["category"],
                                        u.get("symbol_text") or "")),
        }

    def pou_semantics(self) -> dict:
        """O resumo da POU inteira, network a network."""
        redes = [self.network_semantics(n) for n in self.networks()]
        return {
            "schema_version": SCHEMA_VERSION,
            "pou": self.pou,
            "networks": redes,
            "summary": self.summary(),
        }

    # --- números ------------------------------------------------------------

    def summary(self) -> dict:
        """Contagens. Elas descrevem a ANÁLISE, não a qualidade do projeto:
        `multi_writer_symbols: 1` é um fato, não uma reprovação."""
        acessos = [a.to_dict() for a in self._resolved.accesses]
        estados: dict = {}
        for acesso in acessos:
            estados[acesso["resolution_status"]] = estados.get(
                acesso["resolution_status"], 0) + 1
        abertos = self.unresolved()["by_category"]
        return {
            "networks": len(self.networks()),
            "accesses": len(acessos),
            "reads": sum(1 for a in acessos if a["mode"] == "read"),
            "writes": sum(1 for a in acessos if a["mode"] == "write"),
            "read_write": sum(1 for a in acessos if a["mode"] == "read_write"),
            "calls": len(self._resolved.calls),
            "resolution": dict(sorted(estados.items())),
            "unresolved_by_category": {
                categoria: len(dados["items"])
                for categoria, dados in sorted(abertos.items())},
            "multi_writer_symbols": len(self.multi_writers()),
        }

"""A montagem do pipeline Ladder — o ÚNICO lugar que parte do XML.

POR QUE ELE É SEPARADO DA CONSULTA
==================================
`ladder_query.LadderQuery` consome apenas resultados já derivados, e há um
teste que varre aquele módulo procurando importação do parser. A separação faz
a garantia valer: as quatro superfícies (API, CLI, MCP, relatório) recebem o
MESMO objeto, montado uma vez, em vez de cada uma refazer o caminho e poder
refazê-lo diferente.

    parse_ladder → derive_logical_topology → derive_ladder_semantics (R4.1)
                 → resolve_ladder_semantics (R4.2) → LadderQuery (R4.3)
"""

from __future__ import annotations

from pathlib import Path


def query_from_export(xml_path: Path | str, *, extra_symbols=(),
                      st_resolved_references=()):
    """`LadderQuery` a partir de um export PLCopen de POU gráfica."""
    from mastertool_bridge.indexer.reference_resolver import build_symbol_index
    from mastertool_bridge.plcopen.ladder_parser import parse_ladder
    from mastertool_bridge.plcopen.ladder_query import LadderQuery
    from mastertool_bridge.plcopen.ladder_resolution import (
        pou_symbol_from_graphic,
        resolve_ladder_semantics,
    )
    from mastertool_bridge.plcopen.ladder_semantics import (
        derive_ladder_semantics,
    )
    from mastertool_bridge.plcopen.logical_topology import (
        derive_logical_topology,
    )

    pou = parse_ladder(xml_path)
    semantica = derive_ladder_semantics(pou, derive_logical_topology(pou))
    simbolo, diagnosticos = pou_symbol_from_graphic(pou)
    index = build_symbol_index([simbolo, *extra_symbols])
    resolvido = resolve_ladder_semantics(semantica, index, simbolo,
                                         extra_diagnostics=diagnosticos)
    return LadderQuery(semantica, resolvido,
                       st_resolved_references=st_resolved_references)

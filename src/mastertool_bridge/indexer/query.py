"""Consultas determinísticas sobre o índice estático já gerado.

Esta camada opera EXCLUSIVAMENTE sobre os artefatos JSON já produzidos por
`export_loader.build_static_index` (symbols.json, resolved-calls.json,
callers.json, resolved-references.json, read-write-index.json). NUNCA
reprocessa Structured Text — nenhuma chamada a st_lexer/declaration_parser/
gvl_parser/statement_parser/export_loader.build_static_index a partir daqui.
Apenas leitura dos JSONs já escritos em disco e lógica pura em memória.

Separado deliberadamente do pipeline heurístico e antigo
(`mastertool_bridge.analysis.reference_finder` + `mastertool_bridge.export.loader`,
exposto por `cli.py` via `find-symbol`/`find-reads`/`find-writes`) — este
módulo NÃO reaproveita nada daquele código e não deve ser confundido com ele.

Cinco consultas são expostas, todas PURAS (sem IO) uma vez que o
`QueryIndexBundle` já foi carregado via `load_query_bundle`:

    find_symbol(bundle, query)   -- "que declaração(ões) esse nome designa?"
    find_reads(bundle, query)    -- ocorrências de leitura do texto exato
    find_writes(bundle, query)   -- ocorrências de escrita do texto exato
    find_calls(bundle, query)    -- o que a POU <query> CHAMA (chamadas de SAÍDA)
    find_callers(bundle, query)  -- quem chama o símbolo <query>? (chamadas de ENTRADA)

Mapeamento FIXO e determinístico de `resolution_state` -> `confidence`
(rótulo textual direto, não é heurística nem IA):

    resolved            -> "high"
    partially_resolved  -> "medium"
    ambiguous           -> "low"
    unresolved          -> "none"

Ordenação determinística da lista `evidence`: por `(node_id, line, column)`
quando a evidência tem um `node_id` significativo (referências, chamadas,
callers, candidatos de find_symbol pontuado); por `(file, line, column)`
quando não há node_id útil para ordenar (ex. uma variável local encontrada
por varredura de `find_symbol` bare, cujo "node_id" natural é o da POU que a
declara, mas pode haver 2+ PouSymbol com o mesmo node_id-like em arquivos
diferentes -- na prática usamos sempre (node_id, line, column) para todas as
5 consultas, já que toda evidência aqui carrega um node_id de PouSymbol ou
de Reference/Call, e isso já desempata igual a (file, line, column) por
construção do projeto (node_id é único por arquivo/objeto)).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from mastertool_bridge.exceptions import ValidationError
from mastertool_bridge.indexer.models import (
    PouSymbol,
    SourceLocation,
    TypeSymbol,
    VariableDeclaration,
)
from mastertool_bridge.indexer.symbol_resolver import (
    ProjectSymbolIndex,
    ResolvedSymbolRef,
    resolve_dotted_reference,
    resolve_identifier,
)
from mastertool_bridge.utils.json_io import read_json

QueryCommand = Literal["symbol", "reads", "writes", "calls", "callers"]

_REQUIRED_FILES = (
    "symbols.json",
    "resolved-calls.json",
    "callers.json",
    "resolved-references.json",
    "read-write-index.json",
)

_CONFIDENCE_BY_STATE: dict[str, str] = {
    "resolved": "high",
    "partially_resolved": "medium",
    "ambiguous": "low",
    "unresolved": "none",
}

_CALL_TARGET_KINDS = ("PROGRAM", "FUNCTION_BLOCK", "FUNCTION")


def confidence_for_state(resolution_state: str | None) -> str:
    """Mapeamento FIXO resolution_state -> confidence (ver docstring do
    módulo). Estado desconhecido/None mapeia defensivamente para "none"."""
    if resolution_state is None:
        return "none"
    return _CONFIDENCE_BY_STATE.get(resolution_state, "none")


@dataclass
class QueryIndexBundle:
    """Os 5 JSONs de `output_dir` já carregados em memória, mais um
    `ProjectSymbolIndex` reconstruído a partir de `symbols.json` (reutilizado
    por `find_symbol`/`find_callers`, que precisam de
    `resolve_identifier`/`resolve_dotted_reference`)."""

    index_dir: Path
    symbols: list[dict[str, Any]]
    resolved_calls: list[dict[str, Any]]
    callers: dict[str, list[dict[str, Any]]]
    resolved_references: list[dict[str, Any]]
    read_write_index: dict[str, Any]
    symbol_index: ProjectSymbolIndex
    pou_symbols: list[PouSymbol]


def _location_from_dict(data: dict[str, Any] | None) -> SourceLocation | None:
    if not data:
        return None
    return SourceLocation(file=data["file"], line=data["line"], column=data["column"])


def _variable_from_dict(data: dict[str, Any]) -> VariableDeclaration:
    array_dims = data.get("array_dimensions")
    return VariableDeclaration(
        name=data["name"],
        declared_type=data["declared_type"],
        scope=data["scope"],
        is_array=bool(data.get("is_array", False)),
        array_dimensions=(
            [(lo, hi) for lo, hi in array_dims] if array_dims else None
        ),
        initializer_raw=data.get("initializer_raw"),
        is_constant=bool(data.get("is_constant", False)),
        location=_location_from_dict(data.get("location")),
        hardware_address=data.get("hardware_address"),
    )


def _pou_symbol_from_dict(data: dict[str, Any]) -> PouSymbol:
    return PouSymbol(
        node_id=data["node_id"],
        pou_kind=data["pou_kind"],
        name=data["name"],
        file=data["file"],
        return_type=data.get("return_type"),
        extends=data.get("extends"),
        implements=list(data.get("implements") or []),
        variables=[_variable_from_dict(v) for v in data.get("variables") or []],
        location=_location_from_dict(data.get("location")),
        is_qualified_only=bool(data.get("is_qualified_only", False)),
    )


def _type_symbol_from_dict(data: dict[str, Any]) -> TypeSymbol:
    return TypeSymbol(
        node_id=data["node_id"],
        name=data["name"],
        kind=data["kind"],
        file=data["file"],
        alias_target=data.get("alias_target"),
        members=[_variable_from_dict(m) for m in data.get("members") or []],
        location=_location_from_dict(data.get("location")),
    )


def _load_type_symbols(index_dir: Path) -> list[TypeSymbol]:
    """Leitura DEFENSIVA e OPCIONAL de `type-index.json` (ver docstring de
    `load_query_bundle`): ausência do arquivo, ausência da chave `"types"`,
    JSON corrompido, ou formato inesperado dentro de `"types"` nunca viram
    exceção aqui -- sempre resulta em `[]`, preservando compatibilidade com
    índices antigos (gerados antes do commit de DUT/STRUCT) e com fixtures
    de teste que não escrevem este arquivo."""
    path = index_dir / "type-index.json"
    if not path.is_file():
        return []
    try:
        data = read_json(path)
    except (ValueError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    raw_types = data.get("types")
    if not raw_types:
        return []
    type_symbols: list[TypeSymbol] = []
    for entry in raw_types:
        try:
            type_symbols.append(_type_symbol_from_dict(entry))
        except (KeyError, TypeError):
            continue
    return type_symbols


def _read_required_json(index_dir: Path, filename: str) -> Any:
    path = index_dir / filename
    if not path.is_file():
        raise ValidationError(
            f"arquivo obrigatório ausente no índice: {filename} "
            f"(esperado em {path})"
        )
    try:
        return read_json(path)
    except (ValueError, OSError) as exc:
        raise ValidationError(
            f"falha ao ler/parsear {filename} em {index_dir}: {exc}"
        ) from exc


def load_query_bundle(index_dir: Path) -> QueryIndexBundle:
    """Carrega os 5 JSONs necessários de `index_dir` (saída de
    `export_loader.build_static_index`) e reconstrói um `ProjectSymbolIndex`
    a partir de `symbols.json`. Levanta `ValidationError` com mensagem clara
    (nunca traceback cru) se `index_dir` não existir ou algum arquivo
    obrigatório estiver ausente/corrompido.

    Também lê `type-index.json` (chave `"types"`) para reconstruir os
    `TypeSymbol` (STRUCT/alias/DUT) e passá-los para `ProjectSymbolIndex`,
    de forma que `resolve_identifier`/`resolve_dotted_reference` (usados AO
    VIVO por `find_symbol`/`find_callers`/`find_calls`) enxerguem os mesmos
    tipos que já foram usados para pré-computar `resolved-references.json`/
    `read-write-index.json` durante `build_static_index`. Esta leitura é
    DELIBERADAMENTE opcional/defensiva (ver `_load_type_symbols`):
    `type-index.json` NÃO é um arquivo obrigatório (não está em
    `_REQUIRED_FILES`) -- ausência do arquivo, ausência da chave `"types"`,
    ou qualquer formato inesperado nunca impedem o carregamento do bundle,
    apenas resultam em `type_symbols=[]` (compatibilidade com índices
    antigos, gerados antes do commit de DUT/STRUCT, e com fixtures de teste
    que não escrevem este arquivo)."""
    index_dir = Path(index_dir)
    if not index_dir.exists() or not index_dir.is_dir():
        raise ValidationError(
            f"diretório de índice não existe: {index_dir}"
        )

    for filename in _REQUIRED_FILES:
        if not (index_dir / filename).is_file():
            raise ValidationError(
                f"arquivo obrigatório ausente no índice: {filename} "
                f"(esperado em {index_dir / filename})"
            )

    symbols_json = _read_required_json(index_dir, "symbols.json")
    resolved_calls_json = _read_required_json(index_dir, "resolved-calls.json")
    callers_json = _read_required_json(index_dir, "callers.json")
    resolved_references_json = _read_required_json(index_dir, "resolved-references.json")
    read_write_index_json = _read_required_json(index_dir, "read-write-index.json")

    try:
        pou_symbols = [_pou_symbol_from_dict(s) for s in symbols_json]
    except (KeyError, TypeError) as exc:
        raise ValidationError(
            f"symbols.json em {index_dir} tem formato inesperado: {exc}"
        ) from exc

    type_symbols = _load_type_symbols(index_dir)

    symbol_index = ProjectSymbolIndex(pou_symbols, type_symbols=type_symbols)

    return QueryIndexBundle(
        index_dir=index_dir,
        symbols=symbols_json,
        resolved_calls=resolved_calls_json,
        callers=callers_json,
        resolved_references=resolved_references_json,
        read_write_index=read_write_index_json,
        symbol_index=symbol_index,
        pou_symbols=pou_symbols,
    )


@dataclass
class QueryResult:
    """Envelope de resultado padrão retornado por todas as 5 consultas."""

    command: QueryCommand
    query: str
    status: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    note: str | None = None

    @property
    def count(self) -> int:
        return len(self.evidence)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "command": self.command,
            "query": self.query,
            "status": self.status,
            "count": self.count,
            "evidence": self.evidence,
        }
        if self.note is not None:
            data["note"] = self.note
        return data


def _evidence_sort_key(entry: dict[str, Any]) -> tuple[str, int, int]:
    node_id = entry.get("node_id") or ""
    line = entry.get("line")
    column = entry.get("column")
    return (node_id, line if isinstance(line, int) else 0, column if isinstance(column, int) else 0)


def _sort_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(evidence, key=_evidence_sort_key)


def _dedupe_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplica por (node_id, location) preservando a primeira ocorrência,
    na ordem em que foi construída (a ordenação final acontece depois)."""
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for entry in evidence:
        key = (entry.get("node_id"), entry.get("line"), entry.get("column"), entry.get("_dedupe_extra"))
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# find symbol
# ---------------------------------------------------------------------------


def _resolved_ref_to_evidence(
    ref: ResolvedSymbolRef, *, node_id: str | None = None
) -> dict[str, Any]:
    """Converte um `ResolvedSymbolRef` (de resolve_identifier/
    resolve_dotted_reference) em UMA entrada de evidência de `find_symbol`.
    `node_id` explícito é usado quando o ref não carrega um resolved_symbol
    "de exibição" próprio (ex. entrada de candidato ambíguo)."""
    display_node_id = node_id if node_id is not None else ref.resolved_symbol
    entry: dict[str, Any] = {
        "node_id": display_node_id,
        "resolution_state": ref.state,
        "resolved_symbol": ref.resolved_symbol,
        "confidence": confidence_for_state(ref.state),
        "rule_applied": ref.rule_applied,
    }
    if ref.variable is not None and ref.variable.location is not None:
        entry["file"] = ref.variable.location.file
        entry["line"] = ref.variable.location.line
        entry["column"] = ref.variable.location.column
    else:
        entry["file"] = None
        entry["line"] = None
        entry["column"] = None
    if ref.state == "partially_resolved":
        entry["resolved_prefix"] = ref.resolved_prefix
        entry["unresolved_suffix"] = ref.unresolved_suffix
        entry["reason"] = ref.reason
    if ref.message:
        entry["message"] = ref.message
    return entry


def _pou_location_evidence(pou: PouSymbol) -> dict[str, Any]:
    loc = pou.location
    return {
        "node_id": pou.node_id,
        "file": loc.file if loc else pou.file,
        "line": loc.line if loc else None,
        "column": loc.column if loc else None,
        "resolution_state": "resolved",
        "resolved_symbol": pou.node_id,
        "confidence": "high",
        "rule_applied": "declared_pou_or_gvl_name",
        "pou_kind": pou.pou_kind,
        "pou_name": pou.name,
    }


def _bare_variable_scan_evidence(
    name: str, index: ProjectSymbolIndex
) -> list[dict[str, Any]]:
    """Varredura própria de `find_symbol` (não existe em symbol_resolver.py):
    percorre TODOS os PouSymbol e procura em `.variables` por `v.name ==
    name`. Cada match vira UMA entrada de evidência própria (owner PouSymbol
    + VariableDeclaration), mesmo que existam 2+ em POUs DIFERENTES."""
    evidence: list[dict[str, Any]] = []
    for pou in index.symbols:
        for var in pou.variables:
            if var.name != name:
                continue
            loc = var.location
            evidence.append(
                {
                    "node_id": pou.node_id,
                    "file": loc.file if loc else pou.file,
                    "line": loc.line if loc else None,
                    "column": loc.column if loc else None,
                    "resolution_state": "resolved",
                    "resolved_symbol": pou.node_id,
                    "confidence": "high",
                    "rule_applied": "declared_variable_scan",
                    "pou_kind": pou.pou_kind,
                    "pou_name": pou.name,
                    "variable_name": var.name,
                    "declared_type": var.declared_type,
                    "scope": var.scope,
                }
            )
    return evidence


def _status_from_count(count: int) -> str:
    if count == 0:
        return "unresolved"
    if count == 1:
        return "resolved"
    return "ambiguous"


def find_symbol(bundle: QueryIndexBundle, query: str) -> QueryResult:
    """"Que declaração(ões) esse nome designa?"

    Nome pontuado (contém '.'): delega inteiramente para
    `resolve_dotted_reference(query, owner_pou=None, index)`. O estado do
    envelope é o MESMO estado retornado (resolved/partially_resolved/
    ambiguous/unresolved) -- para "ambiguous", uma entrada de evidência por
    candidato em `candidates`; para os demais, uma única entrada.

    Nome bare: combina (a) `resolve_identifier(query, owner_pou=None,
    index)` (GVL implícita / tipo) com (b) varredura própria por todas as
    variáveis de todos os PouSymbol com aquele nome. status = "resolved" se
    count==1, "ambiguous" se count>=2, "unresolved" se count==0.
    """
    index = bundle.symbol_index

    if "." in query:
        ref = resolve_dotted_reference(query, None, index)
        if ref.state == "ambiguous" and ref.candidates:
            evidence = [
                _resolved_ref_to_evidence(ref, node_id=candidate)
                for candidate in ref.candidates
            ]
        else:
            evidence = [_resolved_ref_to_evidence(ref)]
        evidence = _sort_evidence(_dedupe_evidence(evidence))
        return QueryResult(
            command="symbol", query=query, status=ref.state, evidence=evidence
        )

    evidence: list[dict[str, Any]] = []

    # (a) resolve_identifier: GVL implícita e tipo (owner_pou=None -> níveis
    # 1/2/3 nunca disparam, o que é correto sem um "owner").
    identifier_ref = resolve_identifier(query, None, index)
    if identifier_ref.state == "ambiguous" and identifier_ref.candidates:
        for candidate in identifier_ref.candidates:
            evidence.append(_resolved_ref_to_evidence(identifier_ref, node_id=candidate))
    elif identifier_ref.state == "resolved":
        if identifier_ref.resolved_symbol is not None:
            pou = index.pou_by_node_id(identifier_ref.resolved_symbol)
            if pou is not None:
                evidence.append(_pou_location_evidence(pou))
            else:
                evidence.append(_resolved_ref_to_evidence(identifier_ref))
        # rule_applied == "type_reference" com resolved_symbol None: tipo
        # conhecido apenas via uso (declared_type), sem PouSymbol concreto
        # -- não há uma "declaração" própria para listar como evidência de
        # find_symbol (nada com node_id/localização definida a mostrar).
    # identifier_ref.state == "unresolved": nenhuma evidência de (a).

    # (b) varredura própria: todas as variáveis, de todos os POUs, com esse
    # nome (bare). Responde "em que POU(s) existe uma variável chamada X".
    evidence.extend(_bare_variable_scan_evidence(query, index))

    evidence = _sort_evidence(_dedupe_evidence(evidence))
    status = _status_from_count(len(evidence))
    return QueryResult(command="symbol", query=query, status=status, evidence=evidence)


# ---------------------------------------------------------------------------
# find reads / find writes
# ---------------------------------------------------------------------------


def _reference_evidence(entry: dict[str, Any]) -> dict[str, Any]:
    location = entry.get("location") or {}
    out: dict[str, Any] = {
        "node_id": entry.get("node_id"),
        "file": location.get("file", entry.get("file")),
        "line": location.get("line"),
        "column": location.get("column"),
        "resolution_state": entry.get("resolution_state"),
        "resolved_symbol": entry.get("resolved_symbol"),
        "confidence": confidence_for_state(entry.get("resolution_state")),
        "classification": entry.get("classification"),
        "rule_applied": entry.get("rule_applied"),
        "candidates": list(entry.get("candidates") or []),
        "context": entry.get("context"),
    }
    if entry.get("resolution_state") == "partially_resolved":
        out["resolved_prefix"] = entry.get("resolved_prefix")
        out["unresolved_suffix"] = entry.get("unresolved_suffix")
        out["reason"] = entry.get("reason")
    return out


def _find_references_by_name(
    bundle: QueryIndexBundle, query: str, command: Literal["reads", "writes"]
) -> QueryResult:
    allowed = ("read", "read_write") if command == "reads" else ("write", "read_write")
    evidence = [
        _reference_evidence(entry)
        for entry in bundle.resolved_references
        if entry.get("name") == query and entry.get("classification") in allowed
    ]
    evidence = _sort_evidence(_dedupe_evidence(evidence))
    status = "found" if evidence else "not_found"
    return QueryResult(command=command, query=query, status=status, evidence=evidence)


def find_reads(bundle: QueryIndexBundle, query: str) -> QueryResult:
    """Filtra `resolved-references.json` por `name == query` (texto exato,
    bare ou dotted) e `classification in ("read", "read_write")`. status do
    envelope = "found"/"not_found"; cada evidência carrega seu próprio
    `resolution_state` individual (sem alteração)."""
    return _find_references_by_name(bundle, query, "reads")


def find_writes(bundle: QueryIndexBundle, query: str) -> QueryResult:
    """Filtra `resolved-references.json` por `name == query` (texto exato,
    bare ou dotted) e `classification in ("write", "read_write")`. status do
    envelope = "found"/"not_found"; cada evidência carrega seu próprio
    `resolution_state` individual (sem alteração)."""
    return _find_references_by_name(bundle, query, "writes")


# ---------------------------------------------------------------------------
# resolução compartilhada de alvo de chamada (find_calls / find_callers)
# ---------------------------------------------------------------------------


def _call_target_candidates(bundle: QueryIndexBundle, query: str) -> list[PouSymbol]:
    """Resolve `query` para 0, 1 ou 2+ PouSymbol restritos a
    PROGRAM/FUNCTION_BLOCK/FUNCTION (GVL não é alvo de chamada), usando a
    MESMA lógica de `find_symbol`."""
    symbol_result = find_symbol(bundle, query)
    node_ids: list[str] = []
    for entry in symbol_result.evidence:
        node_id = entry.get("resolved_symbol") or entry.get("node_id")
        if node_id:
            node_ids.append(node_id)
    # Dedup preservando ordem.
    seen: set[str] = set()
    unique_ids: list[str] = []
    for node_id in node_ids:
        if node_id in seen:
            continue
        seen.add(node_id)
        unique_ids.append(node_id)

    candidates: list[PouSymbol] = []
    for node_id in unique_ids:
        pou = bundle.symbol_index.pou_by_node_id(node_id)
        if pou is not None and pou.pou_kind in _CALL_TARGET_KINDS:
            candidates.append(pou)
    return candidates


# ---------------------------------------------------------------------------
# find calls
# ---------------------------------------------------------------------------


def _call_evidence(entry: dict[str, Any]) -> dict[str, Any]:
    location = entry.get("location") or {}
    return {
        "node_id": entry.get("node_id"),
        "file": location.get("file", entry.get("file")),
        "line": location.get("line"),
        "column": location.get("column"),
        "resolution_state": entry.get("resolution_state"),
        "resolved_symbol": entry.get("resolved_symbol"),
        "confidence": confidence_for_state(entry.get("resolution_state")),
        "callee": entry.get("callee"),
        "rule_applied": entry.get("rule_applied"),
        "candidates": list(entry.get("candidates") or []),
    }


def _is_call_site_of_pou(node_id: str | None, pou_node_id: str) -> bool:
    """Um entry de `resolved-calls.json` foi ORIGINADO dentro da POU
    `pou_node_id` quando seu `node_id` (do SITE da chamada) tem como
    PREFIXO, antes do primeiro '#', o node_id da própria POU. Ex.: site
    "application/6/0#stmt3" pertence à POU "application/6/0"."""
    if not node_id:
        return False
    prefix = node_id.split("#", 1)[0]
    return prefix == pou_node_id


def find_calls(bundle: QueryIndexBundle, query: str) -> QueryResult:
    """"O que a POU <query> CHAMA?" (chamadas de SAÍDA).

    Resolve `query` para PouSymbol(s) restritos a PROGRAM/FUNCTION_BLOCK/
    FUNCTION usando a MESMA lógica de `find_symbol`/`find_callers`
    (`_call_target_candidates`). Exatamente 1 match -> status="resolved",
    evidência = TODAS as entradas de `resolved-calls.json` cujo `node_id`
    (site da chamada) tem como prefixo o node_id da POU resolvida --
    independente do `resolution_state` PRÓPRIO de cada chamada (inclui
    resolved/ambiguous/unresolved, cobrindo chamadas de método e de
    biblioteca externa como "SysTimeCore.SysTimeGetUs", nunca escondidas).
    count==0 -> nota explicativa (POU existe, nenhuma chamada de saída). 2+
    matches -> status="ambiguous", evidência agrupada POR candidato (nunca
    fundida). 0 matches -> status="unresolved"."""
    candidates = _call_target_candidates(bundle, query)

    if not candidates:
        return QueryResult(command="calls", query=query, status="unresolved", evidence=[])

    if len(candidates) == 1:
        pou = candidates[0]
        raw_calls = [
            entry
            for entry in bundle.resolved_calls
            if _is_call_site_of_pou(entry.get("node_id"), pou.node_id)
        ]
        evidence = _sort_evidence(
            _dedupe_evidence([_call_evidence(entry) for entry in raw_calls])
        )
        note = None
        if not evidence:
            note = "POU encontrada, nenhuma chamada de saida registrada."
        return QueryResult(
            command="calls", query=query, status="resolved", evidence=evidence, note=note
        )

    # 2+ candidatos: evidencia agrupada POR candidato, nunca fundida.
    evidence: list[dict[str, Any]] = []
    for pou in candidates:
        raw_calls = [
            entry
            for entry in bundle.resolved_calls
            if _is_call_site_of_pou(entry.get("node_id"), pou.node_id)
        ]
        for entry in raw_calls:
            call_entry = _call_evidence(entry)
            call_entry["candidate_node_id"] = pou.node_id
            evidence.append(call_entry)
    evidence = _sort_evidence(evidence)
    return QueryResult(command="calls", query=query, status="ambiguous", evidence=evidence)


# ---------------------------------------------------------------------------
# find callers
# ---------------------------------------------------------------------------


def _caller_entry_evidence(entry: dict[str, Any], *, candidate_node_id: str | None = None) -> dict[str, Any]:
    location = entry.get("location") or {}
    out: dict[str, Any] = {
        "node_id": entry.get("node_id"),
        "file": location.get("file", entry.get("file")),
        "line": location.get("line"),
        "column": location.get("column"),
        "resolution_state": "resolved",  # callers.json só contém resolved por construção
        "resolved_symbol": candidate_node_id,
        "confidence": confidence_for_state("resolved"),
        "callee": entry.get("callee"),
        "rule_applied": entry.get("rule_applied"),
    }
    if candidate_node_id is not None:
        out["target_node_id"] = candidate_node_id
    return out


def find_callers(bundle: QueryIndexBundle, query: str) -> QueryResult:
    """"Quem chama o símbolo <query>?"

    Resolve `query` para PouSymbol(s) restritos a PROGRAM/FUNCTION_BLOCK/
    FUNCTION usando a mesma lógica de `find_symbol`. Exatamente 1 match ->
    status="resolved", evidência = callers.json.get(node_id, []) (pode ser
    vazia -- nota explicativa quando count==0). 2+ matches ->
    status="ambiguous", evidência agrupada POR candidato (nunca fundida). 0
    matches -> status="unresolved"."""
    candidates = _call_target_candidates(bundle, query)

    if not candidates:
        return QueryResult(command="callers", query=query, status="unresolved", evidence=[])

    if len(candidates) == 1:
        pou = candidates[0]
        raw_callers = bundle.callers.get(pou.node_id, [])
        evidence = _sort_evidence(
            _dedupe_evidence(
                [_caller_entry_evidence(c, candidate_node_id=pou.node_id) for c in raw_callers]
            )
        )
        note = None
        if not evidence:
            note = (
                "simbolo encontrado, nenhum chamador resolvido registrado "
                "(callers.json so inclui chamadas com resolution_state="
                "resolved, por construcao)."
            )
        return QueryResult(
            command="callers", query=query, status="resolved", evidence=evidence, note=note
        )

    # 2+ candidatos: evidencia agrupada POR candidato, nunca fundida.
    evidence: list[dict[str, Any]] = []
    for pou in candidates:
        raw_callers = bundle.callers.get(pou.node_id, [])
        for c in raw_callers:
            entry = _caller_entry_evidence(c, candidate_node_id=pou.node_id)
            entry["candidate_node_id"] = pou.node_id
            evidence.append(entry)
    evidence = _sort_evidence(evidence)
    return QueryResult(command="callers", query=query, status="ambiguous", evidence=evidence)


# ---------------------------------------------------------------------------
# CLI standalone (NAO em cli.py -- ver restricao do commit).
# ---------------------------------------------------------------------------

_DISPATCH = {
    "symbol": find_symbol,
    "reads": find_reads,
    "writes": find_writes,
    "calls": find_calls,
    "callers": find_callers,
}


def run_query(index_dir: Path, command: QueryCommand, query: str) -> QueryResult:
    bundle = load_query_bundle(index_dir)
    fn = _DISPATCH[command]
    return fn(bundle, query)


def run_ask(index_dir: Path, text: str) -> dict[str, Any]:
    """Camada de linguagem natural sobre as 5 consultas: `text` ->
    `parse_query_intent(text)` -> `QueryIntent` -> se `status=="matched"`,
    despacha para o `find_*` correspondente. Retorna o envelope
    `{"intent": ..., "result": ...}` -- a chave "result" fica AUSENTE
    quando `status != "matched"` (nenhuma das 5 consultas e executada
    nesse caso, e `load_query_bundle` NAO e chamado)."""
    from mastertool_bridge.indexer.query_intent import parse_query_intent

    intent = parse_query_intent(text)
    envelope: dict[str, Any] = {"intent": intent.to_dict()}
    if intent.status == "matched":
        bundle = load_query_bundle(index_dir)
        fn = _DISPATCH[intent.operation.removeprefix("find_")]
        envelope["result"] = fn(bundle, intent.target).to_dict()
    return envelope


def run_answer(index_dir: Path, question: str) -> dict[str, Any]:
    """Camada de resposta em linguagem natural FUNDAMENTADA: `question` ->
    `parse_query_intent` -> (se matched) despacha para `find_*` -> resposta
    textual determinística montada a partir das evidências (ver
    `query_response.answer_query`). `status="error"` no envelope retornado
    representa SOMENTE falha operacional controlada (índice ausente/
    corrompido) OU qualquer exceção inesperada durante `answer_query` --
    NUNCA deixa um traceback cru escapar para o chamador (CLI)."""
    from mastertool_bridge.indexer.query_intent import parse_query_intent
    from mastertool_bridge.indexer.query_response import (
        SCHEMA_VERSION, QueryAnswer, answer_query)

    try:
        bundle = load_query_bundle(index_dir)
    except ValidationError as exc:
        intent = parse_query_intent(question)
        return QueryAnswer(
            schema_version=SCHEMA_VERSION,
            question=question,
            status="error",
            intent=intent.to_dict(),
            summary=f"Falha ao carregar o indice: {exc}",
            evidence=[],
            limitations=[],
        ).to_dict()

    try:
        return answer_query(question, bundle).to_dict()
    except Exception as exc:  # noqa: BLE001 - rede de seguranca deliberada
        intent = parse_query_intent(question)
        return QueryAnswer(
            schema_version=SCHEMA_VERSION,
            question=question,
            status="error",
            intent=intent.to_dict(),
            summary=f"Falha inesperada ao processar a pergunta: {exc}",
            evidence=[],
            limitations=[],
        ).to_dict()


def format_human_readable(result: QueryResult) -> str:
    lines = [
        f"command={result.command} query={result.query!r} "
        f"status={result.status} count={result.count}"
    ]
    if result.note:
        lines.append(f"note: {result.note}")
    for entry in result.evidence:
        file_ = entry.get("file")
        line = entry.get("line")
        column = entry.get("column")
        location = f"{file_}:{line}:{column}" if file_ else "(sem localizacao)"
        state = entry.get("resolution_state")
        confidence = entry.get("confidence")
        extras = []
        for key in (
            "classification",
            "callee",
            "rule_applied",
            "resolved_prefix",
            "unresolved_suffix",
            "reason",
            "candidate_node_id",
            "variable_name",
        ):
            if entry.get(key) is not None:
                extras.append(f"{key}={entry[key]}")
        extras_str = f" | {' '.join(extras)}" if extras else ""
        lines.append(
            f"  {result.status} | {location} | {state} ({confidence}){extras_str}"
        )
    return "\n".join(lines)


def _build_arg_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m mastertool_bridge.indexer",
        description=(
            "Consultas deterministicas sobre o StaticProjectIndexer "
            "(symbols.json/resolved-calls.json/callers.json/"
            "resolved-references.json/read-write-index.json)."
        ),
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    query_parser = subparsers.add_parser("query", help="Executa uma das 5 consultas.")
    query_parser.add_argument(
        "command", choices=["symbol", "reads", "writes", "calls", "callers"]
    )
    query_parser.add_argument("name", help="Nome exato a consultar (bare ou dotted).")
    query_parser.add_argument(
        "--index-dir", required=True, type=Path, help="Diretorio com os JSONs do indice."
    )
    query_parser.add_argument(
        "--json", action="store_true", help="Saida JSON estruturada (default: legivel)."
    )

    ask_parser = subparsers.add_parser(
        "ask", help="Interpreta uma pergunta em linguagem natural e despacha a consulta."
    )
    ask_parser.add_argument("text", help="Pergunta em linguagem natural (PT ou EN canonico).")
    ask_parser.add_argument(
        "--index-dir", required=True, type=Path, help="Diretorio com os JSONs do indice."
    )
    ask_parser.add_argument(
        "--json", action="store_true", help="Saida JSON estruturada (default: legivel)."
    )
    return parser


def _format_intent_readable(intent: Any) -> str:
    data = intent.to_dict()
    lines = [
        f"status={data['status']} operation={data.get('operation')} "
        f"target={data.get('target')!r} confidence={data.get('confidence')} "
        f"matched_pattern={data.get('matched_pattern')}"
    ]
    if data.get("reason") is not None:
        lines.append(f"reason: {data['reason']}")
    if data.get("candidates"):
        lines.append(f"candidates: {data['candidates']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.mode == "query":
        try:
            result = run_query(args.index_dir, args.command, args.name)
        except ValidationError as exc:
            print(f"ERRO: {exc}")
            return 1

        if args.json:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(format_human_readable(result))
        return 0

    if args.mode == "ask":
        from mastertool_bridge.indexer.query_response import format_answer_human_readable

        answer = run_answer(args.index_dir, args.text)

        if args.json:
            print(json.dumps(answer, indent=2, ensure_ascii=False, sort_keys=True))
            return 0

        if answer["status"] == "error":
            print(f"ERRO: {answer['summary']}")
            return 1

        from mastertool_bridge.indexer.query_response import QueryAnswer

        answer_obj = QueryAnswer(
            schema_version=answer["schema_version"],
            question=answer["question"],
            status=answer["status"],
            intent=answer["intent"],
            summary=answer["summary"],
            evidence=answer["evidence"],
            limitations=answer["limitations"],
        )
        print(format_answer_human_readable(answer_obj))
        return 0

    parser.error(f"modo desconhecido: {args.mode}")
    return 2


if __name__ == "__main__":
    import sys

    sys.exit(main())

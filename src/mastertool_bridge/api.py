"""Superfície pública, tipada e estável, sobre o StaticProjectIndexer.

Este módulo NUNCA reimplementa lógica de resolução/consulta/formatação --
toda a lógica de domínio continua 100% em `mastertool_bridge.indexer.query`/
`query_intent`/`query_response` (intocados). `api.py` é uma camada de
EMPACOTAMENTO: carrega o índice uma única vez (`ProjectIndex.open`) e expõe
wrappers estruturais/tipados em cima das funções internas já existentes, para
que um consumidor externo nunca precise importar `mastertool_bridge.indexer.*`
diretamente.

Zero IO além do já feito por `load_query_bundle` em `ProjectIndex.open()` --
nenhuma consulta subsequente relê os JSONs do disco.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mastertool_bridge.exceptions import InvalidIndexError
from mastertool_bridge.indexer.query import QueryIndexBundle, load_query_bundle
from mastertool_bridge.indexer.query import QueryResult as _InternalQueryResult
from mastertool_bridge.indexer.query_intent import QueryIntent
from mastertool_bridge.indexer.query_response import QueryAnswer as _InternalQueryAnswer
from mastertool_bridge.indexer.query_response import answer_query
from mastertool_bridge.exceptions import ValidationError

# ---------------------------------------------------------------------------
# Versionamento
# ---------------------------------------------------------------------------

API_VERSION = "1"

# Placeholder honesto: nenhum artefato JSON gerado hoje por
# `export_loader.build_static_index` carrega um campo de versão de schema
# explícito para checar de verdade -- este conjunto existe como ponto de
# extensão futuro (ver `UnsupportedSchemaError`).
SUPPORTED_INDEX_SCHEMA_VERSIONS = {1}

# 7 campos nomeados de QueryEvidence (todo o resto vai para `extra`).
_NAMED_EVIDENCE_FIELDS = (
    "node_id",
    "file",
    "line",
    "column",
    "resolution_state",
    "resolved_symbol",
    "confidence",
)


# ---------------------------------------------------------------------------
# QueryEvidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QueryEvidence:
    """Uma entrada de evidência, de QUALQUER um dos 5 comandos (ou de `ask`).

    Os dicts de evidência produzidos por `query.py`/`query_response.py` têm
    formatos DIFERENTES entre si (reads/writes têm "classification"; calls
    têm "callee"; callers pode ter "candidate_node_id"/"target_node_id";
    find_symbol pode ter "pou_name"/"variable_name"/"pou_kind";
    query_response.py adiciona ainda "pou_name"/"ordinal"/"display" -- não
    forçamos um único esquema rígido). Apenas os 7 campos presentes em TODOS
    os formatos são nomeados; todo o resto vive em `extra`, preservando
    perda ZERO de informação via `to_dict()`.
    """

    node_id: str | None
    file: str | None
    line: int | None
    column: int | None
    resolution_state: str | None
    resolved_symbol: str | None
    confidence: str | None
    extra: dict[str, Any] = field(default_factory=dict)
    # Quais dos 7 campos nomeados estavam PRESENTES como chave no dict de
    # origem (não apenas com valor não-None) -- necessário para round-trip
    # sem perda, já que `query_response.py` produz evidências que às vezes
    # OMITEM "node_id"/"file"/etc. por completo (em vez de setá-los como
    # None). Campo privado, não faz parte do contrato público de construção
    # manual (default: todos os 7, o caso comum de quem instancia à mão).
    _present: frozenset[str] = field(
        default_factory=lambda: frozenset(_NAMED_EVIDENCE_FIELDS), repr=False, compare=False
    )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "QueryEvidence":
        extra = {k: v for k, v in d.items() if k not in _NAMED_EVIDENCE_FIELDS}
        present = frozenset(k for k in _NAMED_EVIDENCE_FIELDS if k in d)
        return cls(
            node_id=d.get("node_id"),
            file=d.get("file"),
            line=d.get("line"),
            column=d.get("column"),
            resolution_state=d.get("resolution_state"),
            resolved_symbol=d.get("resolved_symbol"),
            confidence=d.get("confidence"),
            extra=extra,
            _present=present,
        )

    def to_dict(self) -> dict[str, Any]:
        values = {
            "node_id": self.node_id,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "resolution_state": self.resolution_state,
            "resolved_symbol": self.resolved_symbol,
            "confidence": self.confidence,
        }
        data: dict[str, Any] = {k: v for k, v in values.items() if k in self._present}
        data.update(self.extra)
        return data


def _evidence_list_from_dicts(evidence: list[dict[str, Any]]) -> list[QueryEvidence]:
    return [QueryEvidence.from_dict(e) for e in evidence]


def _evidence_list_to_dicts(evidence: list[QueryEvidence]) -> list[dict[str, Any]]:
    return [e.to_dict() for e in evidence]


# ---------------------------------------------------------------------------
# QueryResult (público)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QueryResult:
    """Mirror público 1:1 de `mastertool_bridge.indexer.query.QueryResult`,
    com `evidence` tipado como `list[QueryEvidence]` em vez de `list[dict]`."""

    command: str
    query: str
    status: str
    evidence: list[QueryEvidence] = field(default_factory=list)
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
            "evidence": _evidence_list_to_dicts(self.evidence),
        }
        if self.note is not None:
            data["note"] = self.note
        return data


def _public_result_from_internal(internal: _InternalQueryResult) -> QueryResult:
    return QueryResult(
        command=internal.command,
        query=internal.query,
        status=internal.status,
        evidence=_evidence_list_from_dicts(internal.evidence),
        note=internal.note,
    )


# ---------------------------------------------------------------------------
# QueryAnswer (público)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QueryAnswer:
    """Mirror público 1:1 de
    `mastertool_bridge.indexer.query_response.QueryAnswer`, com `intent`
    tipado como `QueryIntent` (em vez de dict) e `evidence` tipado como
    `list[QueryEvidence]` (em vez de `list[dict]`)."""

    schema_version: int
    question: str
    status: str
    intent: QueryIntent
    summary: str
    evidence: list[QueryEvidence] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "question": self.question,
            "status": self.status,
            "intent": self.intent.to_dict(),
            "summary": self.summary,
            "evidence": _evidence_list_to_dicts(self.evidence),
            "limitations": list(self.limitations),
        }


def _intent_from_dict(d: dict[str, Any]) -> QueryIntent:
    return QueryIntent(
        status=d["status"],
        operation=d.get("operation"),
        target=d.get("target"),
        matched_pattern=d.get("matched_pattern"),
        confidence=d.get("confidence", "none"),
        reason=d.get("reason"),
        candidates=d.get("candidates") or [],
    )


def _public_answer_from_internal(internal: _InternalQueryAnswer) -> QueryAnswer:
    return QueryAnswer(
        schema_version=internal.schema_version,
        question=internal.question,
        status=internal.status,
        intent=_intent_from_dict(internal.intent),
        summary=internal.summary,
        evidence=_evidence_list_from_dicts(internal.evidence),
        limitations=list(internal.limitations),
    )


# ---------------------------------------------------------------------------
# ProjectIndex
# ---------------------------------------------------------------------------


class ProjectIndex:
    """Superfície pública, somente leitura, sobre um índice já gerado por
    `export_loader.build_static_index`. Carrega o índice UMA VEZ em
    `open()`; todas as consultas subsequentes reutilizam o bundle em
    memória (nunca relê os JSONs do disco)."""

    def __init__(self, bundle: QueryIndexBundle) -> None:
        self._bundle = bundle

    @classmethod
    def open(cls, index_dir: str | Path) -> "ProjectIndex":
        """Carrega o índice de `index_dir`. Levanta `InvalidIndexError`
        (NUNCA a `ValidationError` interna crua) se o diretório não existir
        ou algum arquivo obrigatório estiver ausente/corrompido."""
        try:
            bundle = load_query_bundle(Path(index_dir))
        except ValidationError as exc:
            raise InvalidIndexError(str(exc)) from exc
        return cls(bundle)

    def find_symbol(self, name: str) -> QueryResult:
        from mastertool_bridge.indexer.query import find_symbol

        return _public_result_from_internal(find_symbol(self._bundle, name))

    def find_reads(self, name: str) -> QueryResult:
        from mastertool_bridge.indexer.query import find_reads

        return _public_result_from_internal(find_reads(self._bundle, name))

    def find_writes(self, name: str) -> QueryResult:
        from mastertool_bridge.indexer.query import find_writes

        return _public_result_from_internal(find_writes(self._bundle, name))

    def find_calls(self, name: str) -> QueryResult:
        from mastertool_bridge.indexer.query import find_calls

        return _public_result_from_internal(find_calls(self._bundle, name))

    def find_callers(self, name: str) -> QueryResult:
        from mastertool_bridge.indexer.query import find_callers

        return _public_result_from_internal(find_callers(self._bundle, name))

    def ask(self, question: str) -> QueryAnswer:
        """Camada de resposta em linguagem natural fundamentada nas
        evidências (ver `query_response.answer_query`). Mesma disciplina
        defensiva de `run_answer`: NUNCA deixa uma exceção inesperada
        escapar -- em caso raro de falha, retorna um `QueryAnswer` público
        com `status="error"`."""
        try:
            internal_answer = answer_query(question, self._bundle)
        except Exception as exc:  # noqa: BLE001 - rede de seguranca deliberada
            from mastertool_bridge.indexer.query_intent import parse_query_intent
            from mastertool_bridge.indexer.query_response import SCHEMA_VERSION

            intent = parse_query_intent(question)
            internal_answer = _InternalQueryAnswer(
                schema_version=SCHEMA_VERSION,
                question=question,
                status="error",
                intent=intent.to_dict(),
                summary=f"Falha inesperada ao processar a pergunta: {exc}",
                evidence=[],
                limitations=[],
            )
        return _public_answer_from_internal(internal_answer)

    @property
    def metadata(self) -> dict[str, Any]:
        """index_dir (str), symbol_count, type_count, reference_count,
        call_count -- todos derivados diretamente do bundle já carregado.
        Inclui também um identificador de run/timestamp best-effort SE E
        SOMENTE SE puder ser derivado honestamente do nome do diretório
        (padrão de timestamp `YYYY-MM-DD_HH-MM-SS` no início do nome) --
        senão, None. Nunca inventa um valor."""
        index_dir = self._bundle.index_dir
        return {
            "index_dir": str(index_dir),
            "symbol_count": len(self._bundle.pou_symbols),
            "type_count": len(self._bundle.symbol_index.type_symbols),
            "reference_count": len(self._bundle.resolved_references),
            "call_count": len(self._bundle.resolved_calls),
            "run_id": _run_id_from_dirname(index_dir.name),
        }


_TIMESTAMP_RE = None


def _run_id_from_dirname(dirname: str) -> str | None:
    """Extrai um identificador de run best-effort a partir de um padrão de
    timestamp `YYYY-MM-DD_HH-MM-SS` no INÍCIO do nome do diretório (ex.:
    "2026-07-23_17-29-54_13_validate_text_exporter" -> o próprio
    dirname, já que ele já É o identificador honesto de run). Retorna None
    quando o nome não começa com esse padrão -- nunca inventa um valor."""
    global _TIMESTAMP_RE
    if _TIMESTAMP_RE is None:
        import re

        _TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}")
    if _TIMESTAMP_RE.match(dirname):
        return dirname
    return None

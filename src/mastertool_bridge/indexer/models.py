"""Modelos de dados do StaticProjectIndexer (fatia 1).

Todos os dataclasses aqui são deliberadamente "burros": não validam semântica
de ST, apenas guardam o que o lexer/parser conseguiu reconhecer. Construções
não suportadas viram `Diagnostic` (ver `diagnostics.py`), nunca exceção.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceLocation:
    """Posição de um token/declaração dentro de um arquivo-fonte exportado."""

    file: str
    line: int
    column: int

    def to_dict(self) -> dict[str, Any]:
        return {"file": self.file, "line": self.line, "column": self.column}


@dataclass(frozen=True)
class Token:
    """Um token bruto do lexer de Structured Text."""

    kind: str
    text: str
    location: SourceLocation
    end_location: SourceLocation | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "kind": self.kind,
            "text": self.text,
            "location": self.location.to_dict(),
        }
        if self.end_location is not None:
            data["end_location"] = self.end_location.to_dict()
        return data


@dataclass
class VariableDeclaration:
    """Uma variável declarada dentro de um bloco VAR* de uma POU."""

    name: str
    declared_type: str
    scope: str
    is_array: bool = False
    array_dimensions: list[tuple[str, str]] | None = None
    initializer_raw: str | None = None
    is_constant: bool = False
    location: SourceLocation | None = None
    hardware_address: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "declared_type": self.declared_type,
            "scope": self.scope,
            "is_array": self.is_array,
            "array_dimensions": (
                [[lo, hi] for lo, hi in self.array_dimensions]
                if self.array_dimensions
                else None
            ),
            "initializer_raw": self.initializer_raw,
            "is_constant": self.is_constant,
            "location": self.location.to_dict() if self.location else None,
            "hardware_address": self.hardware_address,
        }


@dataclass
class PouSymbol:
    """Símbolo de nível de POU (PROGRAM/FUNCTION_BLOCK/FUNCTION) extraído de declaration.st."""

    node_id: str
    pou_kind: str
    name: str
    file: str
    return_type: str | None = None
    extends: str | None = None
    implements: list[str] = field(default_factory=list)
    variables: list[VariableDeclaration] = field(default_factory=list)
    location: SourceLocation | None = None
    is_qualified_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "pou_kind": self.pou_kind,
            "name": self.name,
            "file": self.file,
            "return_type": self.return_type,
            "extends": self.extends,
            "implements": list(self.implements),
            "variables": [v.to_dict() for v in self.variables],
            "location": self.location.to_dict() if self.location else None,
            "is_qualified_only": self.is_qualified_only,
        }

    def variables_in_scope(self, scope: str) -> list[VariableDeclaration]:
        return [v for v in self.variables if v.scope == scope]


@dataclass
class TypeSymbol:
    """Símbolo de nível de tipo (`TYPE <nome> : ...  END_TYPE`) extraído de
    um `declaration.st` de DUT — STRUCT, alias simples, ou algo reconhecido
    como tipo mas ainda não analisável nesta fase (ex. ENUM, kind="unknown").

    Decisão de arquitetura DELIBERADA: `members` reutiliza `VariableDeclaration`
    (em vez de uma classe `TypeMember` paralela quase idêntica) para que a
    FASE 2 possa generalizar a caminhada de cadeia (hoje restrita a
    `PouSymbol.variables`) para também tratar `TypeSymbol.members` sem
    duplicar lógica de busca por nome. Para diferenciar de VAR/VAR_GLOBAL
    existentes, membros de STRUCT usam `scope="STRUCT_MEMBER"` (ver
    `dut_parser.py`)."""

    node_id: str
    name: str
    kind: str  # "struct" | "alias" | "unknown"
    file: str
    alias_target: str | None = None  # só quando kind=="alias"
    members: list[VariableDeclaration] = field(default_factory=list)  # só quando kind=="struct"
    location: SourceLocation | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "kind": self.kind,
            "file": self.file,
            "alias_target": self.alias_target,
            "members": [m.to_dict() for m in self.members],
            "location": self.location.to_dict() if self.location else None,
        }


@dataclass
class CallArgument:
    """Um argumento (posicional ou nomeado) de uma chamada em `implementation.st`.

    `operator` preserva apenas o texto literal do operador usado na
    passagem do argumento (":=", "=>" ou None para posicional) — nenhuma
    semântica de VAR_INPUT/VAR_OUTPUT/VAR_IN_OUT é atribuída aqui."""

    name: str | None
    operator: str | None
    value_raw: str
    location: SourceLocation

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "operator": self.operator,
            "value_raw": self.value_raw,
            "location": self.location.to_dict(),
        }


@dataclass
class Call:
    """Um site de chamada reconhecido em `implementation.st` (standalone ou
    como lado direito de uma atribuição). Nunca resolve o alvo real da
    chamada — `callee` é apenas o texto bruto usado (incluindo '.' para
    chamadas de método, ex. "Instancia.Metodo")."""

    node_id: str
    file: str
    callee: str
    arguments: list[CallArgument] = field(default_factory=list)
    location: SourceLocation | None = None
    end_location: SourceLocation | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "file": self.file,
            "callee": self.callee,
            "arguments": [a.to_dict() for a in self.arguments],
            "location": self.location.to_dict() if self.location else None,
            "end_location": (
                self.end_location.to_dict() if self.end_location else None
            ),
        }


@dataclass
class Reference:
    """Ocorrência SINTÁTICA de um identificador dentro de um statement de
    `implementation.st`. `context` descreve apenas ONDE o identificador
    apareceu textualmente — nenhuma classificação semântica (nem de
    leitura/escrita, nem de resolução para símbolo declarado) é feita aqui.

    `end_location` guarda a localização do ÚLTIMO token de um nome pontuado
    (`Identificador.Identificador...`) quando a referência abrange mais de um
    token — para uma referência de um único segmento, pode ficar None ou
    igual a `location` (best-effort, sem garantia de preenchimento em todos
    os caminhos legados)."""

    node_id: str
    file: str
    name: str
    context: str
    location: SourceLocation
    end_location: SourceLocation | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "node_id": self.node_id,
            "file": self.file,
            "name": self.name,
            "context": self.context,
            "location": self.location.to_dict(),
        }
        if self.end_location is not None:
            data["end_location"] = self.end_location.to_dict()
        return data


@dataclass
class Statement:
    """Um statement de nível superior reconhecido em `implementation.st`
    (atribuição, IF, CASE, FOR, WHILE, REPEAT, RETURN, ou chamada
    standalone). Guarda apenas o que foi reconhecido sintaticamente."""

    node_id: str
    file: str
    kind: str
    location: SourceLocation
    end_location: SourceLocation | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "file": self.file,
            "kind": self.kind,
            "location": self.location.to_dict(),
            "end_location": (
                self.end_location.to_dict() if self.end_location else None
            ),
        }


@dataclass
class ExportBundle:
    """Resultado de `load_export()`: dados brutos carregados de um export do
    ReadOnlyTextExporter, prontos para o parser processar."""

    export_dir: Path
    result: Any  # ValidationResult (import tardio evita ciclo; ver export_loader.py)
    source_map: Any  # SourceMap (idem)
    flat_objects: list[dict[str, Any]] = field(default_factory=list)
    text_index: dict[str, Any] = field(default_factory=dict)
    declaration_node_ids: list[str] = field(default_factory=list)

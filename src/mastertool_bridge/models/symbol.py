"""Símbolos extraídos por parsing tolerante de declarações ST."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VariableDeclaration:
    name: str
    var_type: str
    block: str                      # VAR, VAR_INPUT, VAR_OUTPUT, VAR_IN_OUT, VAR_GLOBAL...
    initial_value: str | None = None
    is_array: bool = False
    is_retain: bool = False
    is_persistent: bool = False
    address: str | None = None      # ex.: %QX0.0 quando declarado com AT
    line: int | None = None
    comment: str | None = None


@dataclass
class Symbol:
    """POU/GVL/DUT parseado (resultado heurístico)."""
    name: str
    kind: str                       # program | function_block | function | gvl | dut | unknown
    return_type: str | None = None
    variables: list[VariableDeclaration] = field(default_factory=list)
    extends: str | None = None
    implements: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)

    def variables_in_block(self, block: str) -> list[VariableDeclaration]:
        return [v for v in self.variables if v.block == block]

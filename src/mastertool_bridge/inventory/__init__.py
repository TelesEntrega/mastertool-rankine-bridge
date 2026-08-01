"""Inventário determinístico de configuração de dispositivo, a partir de
exports PLCopen por dispositivo.

Duas camadas independentes e deliberadamente separadas:

- **bruta**: uma ocorrência por `<Parameter>`, nada descartado, nada
  reinterpretado;
- **interpretada**: só onde há evidência estrutural, com regra, evidência e
  confiança em cada afirmação.

Nenhum dado de projeto real entra neste pacote nem nos seus testes.
"""

from mastertool_bridge.inventory.device_inventory import (  # noqa: F401
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    INVENTORY_SCHEMA_VERSION,
    RunSource,
    build_inventory,
    interpret_parameter,
    parse_device_export,
    protocol_context,
    value_shape,
)

__all__ = [
    "CONFIDENCE_HIGH",
    "CONFIDENCE_MEDIUM",
    "INVENTORY_SCHEMA_VERSION",
    "RunSource",
    "build_inventory",
    "interpret_parameter",
    "parse_device_export",
    "protocol_context",
    "value_shape",
]

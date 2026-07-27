"""Pacote `automation` — verificação OFFLINE do roadmap de automação via
linha de comando do MasterTool (Etapa A, `docs/15-automation-launcher-
roadmap.md`).

Nunca toca o MasterTool nem o CLP: opera somente sobre os artefatos
`result.json` já gravados por
`scripts/mastertool/probes/15_validate_command_line_execution.py`.
"""

from __future__ import annotations

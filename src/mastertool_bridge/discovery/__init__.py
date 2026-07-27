"""Pacote de descoberta (`discovery`) — fatias que investigam o que existe
num export ANTES de qualquer parser semântico saber interpretar o conteúdo
(ex. Fase L0 do roadmap Ladder/FBD/SFC: `docs/14-ladder-roadmap.md`).

Diferente de `indexer/` (que interpreta `.st`), este pacote opera apenas
sobre metadados já capturados em `flat-objects.json` — nunca lê/parseia
texto de declaration/implementation, nunca assume formato ainda não
confirmado dentro do MasterTool real.
"""

from __future__ import annotations

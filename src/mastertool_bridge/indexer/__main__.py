"""Entry point `python -m mastertool_bridge.indexer` (consultas deterministicas).

Uso:
    python -m mastertool_bridge.indexer query symbol Estado_OP --index-dir OUT_DIR
    python -m mastertool_bridge.indexer query reads IN_PERM_DESCARGA --index-dir OUT_DIR --json
"""

from __future__ import annotations

import sys

from mastertool_bridge.indexer.query import main

if __name__ == "__main__":
    sys.exit(main())

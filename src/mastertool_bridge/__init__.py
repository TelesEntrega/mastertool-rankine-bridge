"""mastertool_bridge — camada externa (Python 3.11+) do mastertool-rankine-bridge.

Lê e analisa exports gerados pelos scripts IronPython do MasterTool.
Nunca acessa o MasterTool nem o CLP diretamente.
"""

from mastertool_bridge.api import ProjectIndex, QueryAnswer, QueryEvidence, QueryResult
from mastertool_bridge.exceptions import (
    InvalidIndexError,
    ProjectIndexError,
    UnsupportedSchemaError,
)
from mastertool_bridge.indexer.query_intent import QueryIntent

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "ProjectIndex",
    "QueryResult",
    "QueryAnswer",
    "QueryIntent",
    "QueryEvidence",
    "ProjectIndexError",
    "InvalidIndexError",
    "UnsupportedSchemaError",
]

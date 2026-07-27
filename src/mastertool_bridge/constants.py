"""Constantes compartilhadas da camada externa."""

from pathlib import Path

SCHEMA_DIR = Path(__file__).parent / "schemas"

MANIFEST_FILENAME = "export-manifest.json"
CHECKSUMS_FILENAME = "checksums.sha256"

RISK_LEVELS = ("low", "medium", "high", "critical")

# Classificação de uso de variáveis (heurística — nunca certeza absoluta):
USAGE_CONFIRMED_WRITE = "confirmed_write"
USAGE_PROBABLE_WRITE = "probable_write"
USAGE_CONFIRMED_READ = "confirmed_read"
USAGE_PROBABLE_READ = "probable_read"
USAGE_UNKNOWN = "unknown_usage"

OBJECT_CATEGORIES = (
    "programs", "function-blocks", "functions", "methods", "actions",
    "properties", "gvls", "duts", "visualizations", "other",
)

VAR_BLOCK_KEYWORDS = (
    "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR_GLOBAL",
    "VAR_TEMP", "VAR_STAT", "VAR_EXTERNAL", "VAR_CONFIG", "VAR",
)

POU_HEADER_KEYWORDS = ("PROGRAM", "FUNCTION_BLOCK", "FUNCTION", "METHOD",
                       "ACTION", "TYPE", "INTERFACE", "PROPERTY")

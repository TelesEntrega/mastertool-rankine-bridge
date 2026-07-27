"""StaticProjectIndexer — analisador estático 100% Python 3.

Roda SOMENTE sobre arquivos já exportados por
`common/read_only_text_exporter.py: ReadOnlyTextExporter`. Nunca abre o
MasterTool, nunca faz IO de rede.

Pipeline desta fatia:

    export_loader -> source_model -> st_lexer -> declaration_parser ->
    models -> diagnostics
"""

from __future__ import annotations

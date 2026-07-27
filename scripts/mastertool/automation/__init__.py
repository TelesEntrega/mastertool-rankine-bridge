# -*- coding: utf-8 -*-
"""Runner supervisionado interno (roda DENTRO do MasterTool, IronPython 2.7).

Contrato desta pasta: `docs/16-supervised-runner-contract.md`. Nenhum modulo
aqui importa nada de `src/` (lado host, Python 3.11) nem o contrario -- o
unico acoplamento entre os dois lados sao os arquivos `run-config.json` e
`status.json`/`status-history.jsonl` descritos no contrato.

Compatibilidade obrigatoria: IronPython 2.7 (sem f-strings, pathlib, type
hints ou dependencias pip). Ver AGENTS.md.
"""
from __future__ import print_function

__version__ = "0.1.0"

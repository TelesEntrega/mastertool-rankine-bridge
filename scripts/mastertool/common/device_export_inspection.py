# -*- coding: utf-8 -*-
"""Inspecao do arquivo produzido por uma exportacao PLCopen, e classificacao
do resultado de uma exportacao por dispositivo.

Existe separado do probe porque e a parte que decide se um export esta
COMPLETO ou TRUNCADO, e essa decisao precisa de teste. Um export truncado que
passe por completo e o defeito que este projeto ja pagou caro: duas
exportacoes monoliticas terminaram sem fechar `</project>` e nada avisou.

IronPython 2.7: sem f-string, sem pathlib, sem type hints.
"""
from __future__ import print_function

import os

CLOSING_TAG = "</project>"
TAIL_BYTES = 512

STATUS_COMPLETE = "complete"
STATUS_WITH_ERRORS = "complete_with_export_errors"
STATUS_TRUNCATED = "truncated_outputs"
STATUS_FATAL = "fatal"

EXIT_BY_STATUS = {
    STATUS_COMPLETE: 0,
    STATUS_WITH_ERRORS: 0,
    STATUS_TRUNCATED: 2,
    STATUS_FATAL: 1,
}


def ascii_slug(text, fallback, max_len=60):
    """Nome de diretorio seguro. ASCII estrito de proposito: nome de
    dispositivo pode vir acentuado ou em outro alfabeto, e caminho nao-ASCII
    ja custou tempo neste projeto."""
    out = []
    for ch in (text or ""):
        code = ord(ch)
        if code < 128 and (ch.isalnum() or ch in ("_", "-")):
            out.append(ch)
        else:
            out.append("_")
    slug = "".join(out).strip("_")
    return slug[:max_len] if slug else fallback


def inspect_export_file(path, sha256_fn=None):
    """Tamanho, hash e — o que decide tudo — se o arquivo FECHA `</project>`.

    `sha256_fn` e injetavel para o teste nao depender de I/O real de hashing.
    """
    info = {"exists": False, "size": None, "sha256": None,
            "closes_root_element": None, "tail": None, "error": None}
    try:
        if not os.path.isfile(path):
            return info
        info["exists"] = True
        info["size"] = os.path.getsize(path)
        if sha256_fn is not None:
            info["sha256"] = sha256_fn(path)
        handle = open(path, "rb")
        try:
            handle.seek(max(0, info["size"] - TAIL_BYTES))
            tail = handle.read()
        finally:
            handle.close()
        try:
            text = tail.decode("utf-8", "replace")
        except Exception:                                      # noqa: BLE001
            text = str(tail)
        stripped = text.rstrip()
        info["closes_root_element"] = stripped.endswith(CLOSING_TAG)
        info["tail"] = stripped[-90:]
    except Exception as exc:                                   # noqa: BLE001
        info["error"] = repr(exc)
    return info


def classify_export_run(totals):
    """Truncado tem PRECEDENCIA sobre erro isolado: um conjunto com arquivo
    incompleto nunca pode ser reportado como completo so porque os outros
    dispositivos foram bem.

    Erro isolado de um dispositivo NAO invalida os XML completos ja
    exportados — ele reduz a cobertura, e a cobertura e declarada.
    """
    if totals.get("truncated"):
        return STATUS_TRUNCATED
    if totals.get("errors"):
        return STATUS_WITH_ERRORS
    return STATUS_COMPLETE


def exit_code_for(status):
    return EXIT_BY_STATUS.get(status, EXIT_BY_STATUS[STATUS_FATAL])

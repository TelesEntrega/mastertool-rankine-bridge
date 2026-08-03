# -*- coding: utf-8 -*-
"""Escrita segura de arquivos (UTF-8) para os scripts internos. IronPython 2.7."""
from __future__ import print_function

import codecs
import datetime
import json
import os
import re

WINDOWS_RESERVED = set([
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
])

# Arquivo sentinela gravado em TODO diretorio criado por new_export_dir().
# Prova de que o diretorio foi criado por esta ferramenta (nao um diretorio
# arbitrario) — usado por scripts/maintenance/safe_clean_artifact.py como
# pre-requisito obrigatorio antes de qualquer remocao automatizada.
# Motivo (2026-07-23): um 'rm -rf' com glob por sufixo apagou artefatos
# reais de execucao por engano — ver docs/api/mastertool-api-observations.md.
SENTINEL_FILENAME = ".mastertool-bridge-run"


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def timestamp():
    """Timestamp para nomes de diretorio: 2026-07-23_09-45-10."""
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def iso_now():
    return datetime.datetime.now().isoformat()


def safe_filename(name, max_len=100):
    """Converte nome de objeto em nome de arquivo seguro no Windows."""
    if name is None:
        name = "sem-nome"
    try:
        name = str(name)
    except Exception:
        name = "sem-nome"
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._ ") or "sem-nome"
    if cleaned.upper().split(".")[0] in WINDOWS_RESERVED:
        cleaned = "_" + cleaned
    return cleaned[:max_len]


def write_text(path, text):
    ensure_dir(os.path.dirname(path))
    f = codecs.open(path, "w", "utf-8")
    try:
        f.write(text)
    finally:
        f.close()
    return path


def append_text(path, text):
    ensure_dir(os.path.dirname(path))
    f = codecs.open(path, "a", "utf-8")
    try:
        f.write(text)
    finally:
        f.close()
    return path


def write_json(path, data):
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True, default=str)
    return write_text(path, text + "\n")


def new_export_dir(exports_root, project_slug):
    """Cria diretorio imutavel de export: <timestamp>_<slug>. Nunca sobrescreve.

    Grava tambem um arquivo sentinela (SENTINEL_FILENAME) dentro do
    diretorio, provando que ele foi criado por esta ferramenta — pre-
    requisito para remocao automatizada segura (ver
    scripts/maintenance/safe_clean_artifact.py).
    """
    base = timestamp()
    if project_slug:
        base = base + "_" + safe_filename(project_slug, 60)
    path = os.path.join(exports_root, base)
    if os.path.exists(path):
        suffix = 1
        while os.path.exists(path + "-" + str(suffix)):
            suffix += 1
        path = path + "-" + str(suffix)
    ensure_dir(path)
    try:
        write_text(os.path.join(path, SENTINEL_FILENAME),
                  "created_by=mastertool-ai-bridge\ncreated_at=%s\nslug=%s\n"
                  % (iso_now(), project_slug or ""))
    except Exception:
        pass  # sentinela e defesa extra; falha ao grava-la nao deve travar o export
    return path

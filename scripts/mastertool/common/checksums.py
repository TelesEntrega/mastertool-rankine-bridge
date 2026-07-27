# -*- coding: utf-8 -*-
"""Checksums SHA-256 para exports. IronPython 2.7 compativel."""
from __future__ import print_function

import hashlib
import os


def sha256_text(text):
    if text is None:
        return None
    if not isinstance(text, bytes):
        text = text.encode("utf-8")
    return hashlib.sha256(text).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    f = open(path, "rb")
    try:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    finally:
        f.close()
    return h.hexdigest()


def write_checksums_file(root_dir, output_path):
    """Gera arquivo no formato 'hash  caminho/relativo' para todos os arquivos."""
    lines = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.abspath(full) == os.path.abspath(output_path):
                continue
            rel = os.path.relpath(full, root_dir).replace("\\", "/")
            try:
                digest = sha256_file(full)
                lines.append("%s  %s" % (digest, rel))
            except Exception as exc:
                lines.append("ERRO  %s  (%s)" % (rel, exc))
    from common import file_io
    file_io.write_text(output_path, "\n".join(lines) + "\n")
    return output_path

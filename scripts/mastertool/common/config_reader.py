# -*- coding: utf-8 -*-
"""Leitor MINIMO de config/default.yaml, sem dependencias externas.

NAO e um parser YAML completo (scripts IronPython nao podem depender de
pyyaml — ver AGENTS.md). Le apenas pares "chave: valor" simples dentro de uma
secao top-level indicada (ex.: "features:"), no formato usado por
config/default.yaml: mapeamentos aninhados por indentacao de 2 espacos,
valores escalares bool/string/null. Suficiente para os flags de feature deste
projeto; nao tenta suportar listas, ancoras ou strings multilinha.

Fail closed: qualquer arquivo ausente, secao ausente ou chave ausente
retorna o `default` explicito do chamador — nunca lanca excecao, nunca
presume True.
"""
from __future__ import print_function

import re

_BOOL_TRUE = ("true", "yes", "on")
_BOOL_FALSE = ("false", "no", "off")


def _parse_scalar(text):
    text = text.strip()
    lowered = text.lower()
    if lowered in _BOOL_TRUE:
        return True
    if lowered in _BOOL_FALSE:
        return False
    if lowered in ("null", "~", ""):
        return None
    if len(text) >= 2 and ((text[0] == '"' and text[-1] == '"') or
                           (text[0] == "'" and text[-1] == "'")):
        return text[1:-1]
    return text


def read_feature_flag(config_path, section, key, default=False):
    """Le <section>.<key> de um YAML simples. Retorna `default` se qualquer
    parte do caminho nao existir (arquivo, secao ou chave) — fail closed.
    """
    try:
        f = open(config_path, "r")
        try:
            lines = f.readlines()
        finally:
            f.close()
    except Exception:
        return default

    in_section = False
    section_indent = None
    for raw_line in lines:
        line = raw_line.rstrip("\n").rstrip("\r")
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if not in_section:
            if stripped == (section + ":"):
                in_section = True
                section_indent = indent
            continue

        # indentacao <= a da secao encerra o bloco da secao
        if indent <= section_indent:
            break

        match = re.match(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*)$", stripped)
        if not match:
            continue
        found_key, value_text = match.group(1), match.group(2)
        if found_key == key:
            value_text = re.split(r"\s+#", value_text, 1)[0].strip()
            return _parse_scalar(value_text)
    return default

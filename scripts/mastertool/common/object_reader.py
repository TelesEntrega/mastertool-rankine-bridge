# -*- coding: utf-8 -*-
"""Leitura defensiva de declaracao/implementacao textual de objetos.

Convencao CODESYS a confirmar: obj.textual_declaration.text e
obj.textual_implementation.text quando has_textual_* for True.
"""
from __future__ import print_function


def _read_textual(obj, flag_attr, holder_attr):
    """Retorna (texto, erro). Ambos None = objeto nao possui esse conteudo."""
    try:
        if hasattr(obj, flag_attr) and not getattr(obj, flag_attr):
            return None, None
    except Exception as exc:
        return None, "falha ao ler %s: %s" % (flag_attr, exc)
    try:
        if not hasattr(obj, holder_attr):
            return None, "objeto nao expoe %s" % holder_attr
        holder = getattr(obj, holder_attr)
        if holder is None:
            return None, None
        if hasattr(holder, "text"):
            text = holder.text
            return (str(text) if text is not None else None), None
        return None, "%s nao expoe .text" % holder_attr
    except Exception as exc:
        return None, "falha ao ler %s.text: %s" % (holder_attr, exc)


def read_declaration(obj):
    return _read_textual(obj, "has_textual_declaration", "textual_declaration")


def read_implementation(obj):
    return _read_textual(obj, "has_textual_implementation", "textual_implementation")

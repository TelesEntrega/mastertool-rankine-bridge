# -*- coding: utf-8 -*-
"""Conversao defensiva de objetos .NET/ScriptEngine para estruturas JSON-aveis."""
from __future__ import print_function

from common import compatibility

BASIC_TYPES = (str, int, float, bool)
try:
    BASIC_TYPES = BASIC_TYPES + (unicode, long)  # noqa: F821 (IronPython 2.7)
except NameError:
    pass


def to_jsonable(value, max_depth=3, _depth=0):
    """Converte valor arbitrario em algo serializavel por json.dumps.

    Nunca lanca excecao; em caso de falha retorna string descritiva.
    Nao invoca metodos do objeto — apenas repr/str.
    """
    try:
        if value is None or isinstance(value, BASIC_TYPES):
            return value
        if isinstance(value, dict):
            if _depth >= max_depth:
                return compatibility.safe_repr(value)
            out = {}
            for k, v in value.items():
                out[str(k)] = to_jsonable(v, max_depth, _depth + 1)
            return out
        if isinstance(value, (list, tuple, set)):
            if _depth >= max_depth:
                return compatibility.safe_repr(value)
            return [to_jsonable(v, max_depth, _depth + 1) for v in value]
        return compatibility.safe_repr(value)
    except Exception as exc:
        return "<erro de serializacao: %s>" % exc


def describe_value(value):
    """Par (tipo, repr) seguro para relatorios de introspeccao."""
    return {
        "type": compatibility.safe_type_name(value),
        "repr": compatibility.safe_repr(value),
    }

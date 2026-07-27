# -*- coding: utf-8 -*-
"""Camada de compatibilidade entre IronPython 2.7 e o ScriptEngine do MasterTool.

Nenhum nome de API e presumido: todo acesso e defensivo e retorna None quando
o objeto nao existe. O que for observado de fato deve ser registrado em
docs/api/mastertool-api-observations.md.
"""
from __future__ import print_function

import sys

# Nomes de globais tipicamente injetados pelo CODESYS ScriptEngine (base do
# MasterTool). A EXISTENCIA de cada um precisa ser confirmada na Fase 0.
CANDIDATE_GLOBALS = [
    "projects",
    "system",
    "librarymanager",
    "device_repository",
    "online",
    "scriptengine",
]

# Objetos cuja leitura de propriedades de instancia pode ter efeito colateral
# (ex.: iniciar comunicacao). Para eles, apenas dir() e type() sao permitidos.
SIDE_EFFECT_RISK = ["online", "device_repository"]


def python_version():
    return sys.version.replace("\n", " ").replace("\r", " ")


def is_ironpython():
    return sys.platform == "cli" or "IronPython" in sys.version


def get_builtins_module():
    try:
        import __builtin__
        return __builtin__
    except ImportError:
        import builtins
        return builtins


def get_scriptengine_global(name):
    """Retorna um objeto global do ScriptEngine ou None, sem lancar excecao.

    Ordem de busca:
      1. modulo 'scriptengine' (convencao CODESYS: import scriptengine);
      2. builtins (alguns hosts injetam os nomes la);
    O escopo do proprio script (globals()) deve ser testado pelo chamador,
    pois este modulo nao enxerga o escopo do script principal.
    """
    try:
        import scriptengine
        if hasattr(scriptengine, name):
            return getattr(scriptengine, name)
    except Exception:
        pass
    try:
        mod = get_builtins_module()
        if hasattr(mod, name):
            return getattr(mod, name)
    except Exception:
        pass
    return None


def find_available_globals(script_globals=None):
    """Mapeia quais globais candidatos existem. Retorna dict nome -> objeto.

    ATENCAO: isto sonda TODOS os CANDIDATE_GLOBALS, inclusive "online" e
    "device_repository". hasattr()/getattr() executam o getter de verdade,
    entao isto conta como ACESSO a esses objetos, nao so uma checagem inerte.
    Use apenas quando o acesso a "online"/"device_repository" for aceitavel
    para o script em questao. Para uma sondagem restrita a uma lista
    explicita (ex.: smoke test, que nao deve tocar "online"), use
    probe_globals() abaixo.
    """
    found = {}
    for name in CANDIDATE_GLOBALS:
        obj = None
        if script_globals is not None and name in script_globals:
            obj = script_globals[name]
        if obj is None:
            obj = get_scriptengine_global(name)
        if obj is not None:
            found[name] = obj
    return found


def probe_globals(names, script_globals=None):
    """Sonda APENAS os nomes explicitamente passados (whitelist estrita).

    Ao contrario de find_available_globals(), nao itera sobre
    CANDIDATE_GLOBALS: e impossivel esta funcao tocar em um nome que nao
    esteja em `names`. Use para scripts que precisam de uma garantia forte de
    escopo minimo (ex.: nunca acessar "online"/"device_repository").
    Retorna dict nome -> objeto (somente os presentes).
    """
    found = {}
    for name in names:
        obj = None
        if script_globals is not None and name in script_globals:
            obj = script_globals[name]
        if obj is None:
            obj = get_scriptengine_global(name)
        if obj is not None:
            found[name] = obj
    return found


def safe_type_name(obj):
    try:
        return type(obj).__name__
    except Exception:
        return "<tipo indisponivel>"


def safe_repr(obj, max_len=200):
    try:
        text = repr(obj)
    except Exception:
        try:
            text = str(obj)
        except Exception:
            return "<repr indisponivel>"
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text

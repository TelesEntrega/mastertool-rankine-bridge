# -*- coding: utf-8 -*-
"""Acesso defensivo ao projeto aberto no MasterTool.

Convencoes do CODESYS ScriptEngine (a CONFIRMAR na Fase 0):
  - global 'projects' com propriedade 'primary' (projeto aberto);
  - projeto com propriedade 'path'.
Todo acesso e guardado; ausencia vira None + registro de erro, nunca excecao.
"""
from __future__ import print_function

from common import compatibility


def get_projects_object(script_globals=None):
    if script_globals is not None and "projects" in script_globals:
        return script_globals["projects"]
    return compatibility.get_scriptengine_global("projects")


def get_primary_project(script_globals=None):
    """Retorna (projeto, erro). erro=None em caso de sucesso."""
    projects = get_projects_object(script_globals)
    if projects is None:
        return None, "Objeto global 'projects' nao encontrado no ScriptEngine."
    try:
        if hasattr(projects, "primary"):
            primary = projects.primary
            if primary is None:
                return None, "'projects.primary' existe mas e None (nenhum projeto aberto?)."
            return primary, None
        return None, ("Objeto 'projects' existe mas nao possui atributo "
                      "'primary'. Membros: %s" % ", ".join(safe_dir(projects)[:40]))
    except Exception as exc:
        return None, "Falha ao acessar 'projects.primary': %s" % exc


def get_project_path(project):
    for attr in ("path", "project_path", "full_name"):
        try:
            if hasattr(project, attr):
                value = getattr(project, attr)
                if value:
                    return str(value)
        except Exception:
            continue
    return None


def get_object_name(obj):
    """Nome de um objeto da arvore, tentando as convencoes conhecidas."""
    try:
        if hasattr(obj, "get_name"):
            name = obj.get_name()
            if name:
                return str(name)
    except Exception:
        pass
    for attr in ("name", "path"):
        try:
            if hasattr(obj, attr):
                value = getattr(obj, attr)
                if value:
                    return str(value)
        except Exception:
            continue
    return None


def safe_dir(obj):
    try:
        return sorted([m for m in dir(obj) if not m.startswith("_")])
    except Exception:
        return []

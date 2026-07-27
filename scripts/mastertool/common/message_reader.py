# -*- coding: utf-8 -*-
"""Descoberta (introspectiva) dos servicos de mensagens/compilacao.

Nesta fase NAO coletamos mensagens de fato: apenas registramos quais APIs
parecem existir, para preencher docs/api/mastertool-api-observations.md.
Nenhum metodo e invocado; apenas dir()/hasattr.
"""
from __future__ import print_function

from common import compatibility, project_access

# Nomes plausiveis no ecossistema CODESYS — EXISTENCIA a confirmar na Fase 0.
#
# 2026-07-23: evidencia ESTATICA (reflection .NET read-only sobre os plugins
# instalados nesta maquina, sem executar nada — ver
# docs/api/mastertool-api-observations.md) encontrou um tipo ScriptApplication
# com metodos build()/rebuild()/clean()/generate_code() (sem "compile" nem
# "check_all_pool_objects") e um tipo ScriptMessage com campos
# project/object/position/text/severity. Isso e forte indicio, NAO confirmacao
# em runtime — os nomes abaixo foram ajustados para refletir essa evidencia,
# mas a lista permanece so de candidatos a testar.
MESSAGE_RELATED_MEMBERS = [
    "get_message_categories",
    "get_message_objects",
    "get_messages",
    "messages",
]
COMPILE_RELATED_MEMBERS = [
    "build",           # evidencia estatica: ScriptApplication.build()
    "rebuild",         # evidencia estatica: ScriptApplication.rebuild()
    "clean",           # evidencia estatica: ScriptApplication.clean()
    "generate_code",   # evidencia estatica: ScriptApplication.generate_code()
    "compile",         # sem evidencia estatica; mantido como candidato extra
    "check_all_pool_objects",  # idem
]


def describe_message_api(script_globals=None):
    """Relata quais membros relacionados a mensagens/compilacao existem."""
    report = {
        "system_object_found": False,
        "system_members": [],
        "message_candidates_present": [],
        "project_compile_candidates_present": [],
        "notes": [
            "Somente introspeccao: nenhum metodo foi invocado.",
            "Confirmar assinaturas reais na Fase 0 antes de usar.",
        ],
    }
    system = None
    if script_globals is not None and "system" in script_globals:
        system = script_globals["system"]
    if system is None:
        system = compatibility.get_scriptengine_global("system")
    if system is not None:
        report["system_object_found"] = True
        members = project_access.safe_dir(system)
        report["system_members"] = members
        report["message_candidates_present"] = [
            m for m in MESSAGE_RELATED_MEMBERS if m in members]

    project, err = project_access.get_primary_project(script_globals)
    if project is not None:
        members = project_access.safe_dir(project)
        report["project_compile_candidates_present"] = [
            m for m in COMPILE_RELATED_MEMBERS if m in members]
    elif err:
        report["notes"].append("Projeto primario indisponivel: %s" % err)
    return report

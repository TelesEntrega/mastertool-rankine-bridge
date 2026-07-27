# -*- coding: utf-8 -*-
"""Guarda de seguranca dos scripts internos. Espelha config/safety-policy.yaml.

Fase atual: SOMENTE LEITURA. Qualquer operacao de escrita/online e bloqueada
aqui, independentemente de configuracao (fail closed).
"""
from __future__ import print_function

READ_ONLY_PHASE = True

FORBIDDEN_OPERATIONS = [
    "modify_original_project",
    "download_to_plc",
    "go_online",
    "login_to_controller",
    "start_controller",
    "stop_controller",
    "reset_controller",
    "force_variables",
    "write_physical_outputs",
    "change_hardware_configuration",
    "install_libraries_without_authorization",
    "import_without_backup",
    "apply_ai_changes_to_official_project",
]

WRITE_OPERATIONS = [
    "save_project",
    "import_object",
    "create_object",
    "delete_object",
    "modify_object",
    "set_declaration",
    "set_implementation",
]


class SafetyError(Exception):
    """Operacao bloqueada pela politica de seguranca."""
    pass


def assert_operation_allowed(operation):
    """Lanca SafetyError se a operacao for proibida na fase atual."""
    if operation in FORBIDDEN_OPERATIONS:
        raise SafetyError(
            "Operacao '%s' e permanentemente proibida pela politica de "
            "seguranca (config/safety-policy.yaml)." % operation)
    if READ_ONLY_PHASE and operation in WRITE_OPERATIONS:
        raise SafetyError(
            "Operacao de escrita '%s' bloqueada: fase atual e somente "
            "leitura. Conclua e aprove as fases 0-3 antes." % operation)
    return True


def read_only_banner():
    return ("MODO SOMENTE LEITURA: este script nao modifica o projeto, nao "
            "compila, nao realiza download nem qualquer operacao online.")

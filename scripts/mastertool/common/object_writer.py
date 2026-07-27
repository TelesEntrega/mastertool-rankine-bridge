# -*- coding: utf-8 -*-
"""Escrita de objetos — DESABILITADA nesta fase (somente leitura).

Este modulo existe apenas para reservar a interface. Toda funcao lanca
SafetyError ate que as fases 0-3 estejam concluidas, testadas e aprovadas.
"""
from __future__ import print_function

from common import safety

DISABLED_MESSAGE = (
    "Importacao desabilitada. Conclua e aprove as fases de leitura, backup, "
    "validacao e compilacao antes de habilitar esta funcionalidade.")


def set_declaration(obj, text):
    safety.assert_operation_allowed("set_declaration")
    raise safety.SafetyError(DISABLED_MESSAGE)


def set_implementation(obj, text):
    safety.assert_operation_allowed("set_implementation")
    raise safety.SafetyError(DISABLED_MESSAGE)


def import_object(project, package):
    safety.assert_operation_allowed("import_object")
    raise safety.SafetyError(DISABLED_MESSAGE)

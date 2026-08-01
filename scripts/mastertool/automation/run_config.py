# -*- coding: utf-8 -*-
"""Leitura e validacao de `run-config.json` (lado interno do runner
supervisionado). Contrato: `docs/16-supervised-runner-contract.md`, secoes
2 e 3.

O host (Python 3.11, `src/mastertool_bridge/automation/`) e quem GERA
`run-config.json`; este modulo so LE e valida -- fail-closed em qualquer
divergencia. Nunca escreve nada em disco.

Compatibilidade: IronPython 2.7 (sem f-strings, pathlib, type hints).
"""
from __future__ import print_function

import json
import os

from common import safety

# Strings nativas: basestring cobre str/unicode no IronPython 2.7; so 'str'
# em Python 3 (testes). Mesmo padrao de common/capabilities.py.
try:
    _STRING_TYPES = (basestring,)  # noqa: F821
except NameError:
    _STRING_TYPES = (str,)

# Campos obrigatorios de run-config.json (contrato, secao 2). A ausencia de
# QUALQUER um deles reprova o config inteiro -- nenhum default e assumido
# para campos de identidade/seguranca (fail-closed).
REQUIRED_FIELDS = (
    "schema_version",
    "run_id",
    "mode",
    "repo_root",
    "mastertool_scripts_dir",
    "expected_project_path",
    "expected_project_sha256",
    "expected_application_name",
    "expected_application_guid",
    "expected_application_type_guid",
    "run_dir",
    "output_dir",
    "allowed_output_root",
    "operations",
)

# Unicas chaves conhecidas dentro de 'operations' (contrato, secao 2 e 3).
# Qualquer chave fora desta lista reprova o config -- uma operacao que o
# runner nao conhece nao pode ser silenciosamente ignorada.
KNOWN_OPERATION_KEYS = (
    "scan_project_tree",
    "export_text",
    "inventory_graphic_objects",
    "probe_ladder_surface",
    "probe_ladder_dynamic_surface",
    "probe_ladder_extender_surface",
    "probe_plcopen_export_signature",
    "export_plcopen_xml",
    "build",
    "save",
    "online",
    "download",
    "force",
)

# Campos obrigatorios da secao 'ladder_probe' (contrato, secao 3.1) --
# EXATAMENTE estes 4, cada um uma string nao vazia. Nenhum destes valores
# pode ser hardcoded no runner nem no probe (mesma regra dos
# expected_application_*, contrato secao 6.3) -- por isso sao validados
# aqui e repassados tal como vieram do config.
LADDER_PROBE_REQUIRED_FIELDS = (
    "target_node_id",
    "expected_name",
    "expected_guid",
    "expected_type_guid",
)

# Mapeamento operations.<chave> -> nome de operacao em common/safety.py
# (contrato, secao 3: "reutiliza common/safety.py -- assert_operation_allowed()
# ... Nao criar uma segunda guarda de seguranca paralela"). 'build' NAO tem
# equivalente em safety.py (nao e save/online/download/force) -- por isso e
# rejeitado explicitamente logo abaixo, fora deste mapa.
OPERATION_SAFETY_MAP = {
    "save": "save_project",
    "online": "go_online",
    "download": "download_to_plc",
    "force": "force_variables",
}

# Limites de travessia por motor (scanner/exportador/inventario). Uma secao
# 'limits' em run-config.json e OPCIONAL; quando ausente (ou quando um bloco/
# chave individual estiver ausente), vale o default abaixo -- que sao os
# valores JA VALIDADOS em runtime real pelos probes 12/13/14 contra
# ExemploPlanta V1.0.project (baseline v0.1.0), NAO os defaults (mais frouxos)
# das proprias classes em common/. Usar os defaults das classes silenciosamente
# trocaria uma configuracao validada por outra nunca testada, quebrando a
# reprodutibilidade contra a baseline -- por isso o runner NUNCA instancia um
# motor sem passar estes limites explicitamente (ver
# supervised_snapshot_runner.py).
#
# 'expected_root_count' (bloco 'scanner') e o UNICO valor cujo default e
# None (sem validacao de contagem de raizes): o valor 4 usado pelo probe 12 e
# especifico de ExemploPlanta V1.0.project -- hardcoda-lo aqui repetiria o
# mesmo erro que o contrato explicitamente proibe para os GUIDs de
# Application (secao 6.3). Quando o config informar um valor, ele e
# repassado ao scanner tal como veio.
DEFAULT_LIMITS = {
    "scanner": {
        "max_depth": 8,
        "max_total_nodes": 2000,
        "max_children_per_node": 128,
        "expected_root_count": None,
    },
    "exporter": {
        "max_depth": 8,
        "max_total_nodes": 1000,
        "max_children_per_node": 128,
        "max_text_objects": 300,
        "max_document_characters": 1000000,
        "max_total_characters": 15000000,
    },
    "inventory": {
        "max_depth": 8,
        "max_total_nodes": 1000,
        "max_children_per_node": 128,
    },
}

LIMIT_BLOCK_NAMES = ("scanner", "exporter", "inventory")


class RunConfigError(Exception):
    """run-config.json reprovado. A mensagem sempre identifica QUAL campo
    (ou operacao) causou a reprovacao -- nunca uma falha generica."""
    pass


def load_run_config(run_dir):
    """Le e valida `<run_dir>/run-config.json`. Retorna o dict do config em
    caso de sucesso; levanta RunConfigError em qualquer reprovacao (arquivo
    ausente/corrompido, schema_version errado, campo obrigatorio ausente,
    chave desconhecida em 'operations', ou operacao proibida marcada como
    true). Nunca retorna um config parcialmente valido -- ou o config inteiro
    e aceito, ou a excecao e levantada e o chamador aborta (fail-closed)."""
    config_path = os.path.join(run_dir, "run-config.json")

    try:
        f = open(config_path, "r")
    except Exception as exc:
        raise RunConfigError(
            "Nao foi possivel abrir run-config.json em '%s': %s" % (config_path, exc))
    try:
        try:
            config = json.load(f)
        except Exception as exc:
            raise RunConfigError(
                "run-config.json invalido (JSON malformado) em '%s': %s" % (config_path, exc))
    finally:
        f.close()

    if not isinstance(config, dict):
        raise RunConfigError(
            "run-config.json deve conter um objeto JSON no nivel raiz (recebido: %s)."
            % type(config).__name__)

    for field in REQUIRED_FIELDS:
        if field not in config:
            raise RunConfigError(
                "Campo obrigatorio ausente em run-config.json: '%s'." % field)

    if config["schema_version"] != 1:
        raise RunConfigError(
            "schema_version invalido em run-config.json: esperado 1, recebido %r."
            % (config["schema_version"],))

    operations = config["operations"]
    if not isinstance(operations, dict):
        raise RunConfigError(
            "Campo 'operations' de run-config.json deve ser um objeto JSON "
            "(recebido: %s)." % type(operations).__name__)

    for key in operations:
        if key not in KNOWN_OPERATION_KEYS:
            raise RunConfigError(
                "Chave desconhecida em 'operations': '%s'. Fail-closed: uma "
                "operacao que o runner nao conhece nao pode ser "
                "silenciosamente ignorada." % key)

    # 'build' nao tem equivalente em common/safety.py (nao e save/online/
    # download/force) -- rejeitado explicitamente aqui, como pede o contrato
    # (secao 3): "build" so aparece na lista de operacoes proibidas, nunca
    # mapeado para uma operacao de common/safety.py.
    if bool(operations.get("build", False)):
        raise RunConfigError(
            "Operacao 'operations.build' nao e permitida nesta fase (sem "
            "equivalente em common/safety.py; rejeitada explicitamente pelo "
            "runner, nao pela guarda de seguranca generica).")

    for op_key, safety_operation in OPERATION_SAFETY_MAP.items():
        if bool(operations.get(op_key, False)):
            try:
                safety.assert_operation_allowed(safety_operation)
            except safety.SafetyError as exc:
                raise RunConfigError(
                    "Operacao 'operations.%s' proibida (mapeada para '%s' em "
                    "common/safety.py): %s" % (op_key, safety_operation, exc))
            # assert_operation_allowed() sempre levanta SafetyError para os 4
            # nomes deste mapa (save_project esta em WRITE_OPERATIONS e a
            # fase atual e somente-leitura; go_online/download_to_plc/
            # force_variables estao em FORBIDDEN_OPERATIONS, permanentes) --
            # entao este ponto e inalcancavel na pratica. Mesmo assim, se
            # algum dia a politica de common/safety.py mudar e parar de
            # bloquear uma dessas operacoes, o runner NAO deve herdar essa
            # permissao silenciosamente: fail-closed aqui tambem.
            raise RunConfigError(
                "Operacao 'operations.%s' esta marcada como true em "
                "run-config.json, mas nao e permitida nesta fase do runner "
                "supervisionado." % op_key)

    # Duas secoes independentes, mesma regra. O probe 17 NAO reutiliza a
    # flag nem a secao do 16: sao sondagens distintas (reflexao CLR vs
    # superficie dinamica) e precisam poder ser ligadas separadamente, com
    # alvos que podem ate diferir.
    _validate_ladder_probe_section(config, operations,
                                   "ladder_probe", "probe_ladder_surface")
    _validate_ladder_probe_section(config, operations,
                                   "ladder_dynamic_probe",
                                   "probe_ladder_dynamic_surface")
    _validate_ladder_probe_section(config, operations,
                                   "ladder_extender_probe",
                                   "probe_ladder_extender_surface")
    _validate_plcopen_signature_section(config, operations)
    _validate_plcopen_export_section(config, operations)
    _validate_ladder_probes_mutually_exclusive(operations)

    config["limits"] = _resolve_limits(config.get("limits"))

    return config


def _validate_ladder_probe_section(config, operations, section_name=None,
                                   operation_key=None):
    """Valida uma secao de identidade de alvo de probe Ladder. Regra
    fail-closed EM AMBAS AS DIRECOES -- nao so a ausencia quando a operacao
    esta ligada, mas TAMBEM a presenca quando a operacao esta desligada
    (config incoerente nao e aceito por omissao, mesmo criterio ja aplicado
    a 'operations'/'limits'):

        <operacao>=true  e <secao> ausente        -> reprova
        <operacao>=false e <secao> presente       -> reprova
        <operacao>=true  e <secao> com campo vazio -> reprova

    Parametrizada porque os probes 16 e 17 usam a MESMA regra sobre secoes
    diferentes ('ladder_probe' e 'ladder_dynamic_probe'). Duplicar o corpo
    criaria duas copias que podem divergir em silencio -- e divergencia
    numa guarda fail-closed e exatamente o tipo de erro que so aparece
    quando ja e tarde. Os defaults preservam a assinatura antiga, usada
    pelos testes e chamadas existentes.
    """
    if section_name is None:
        section_name = "ladder_probe"
    if operation_key is None:
        operation_key = "probe_ladder_surface"

    ladder_probe = config.get(section_name)
    operation_enabled = bool(operations.get(operation_key, False))

    if operation_enabled and ladder_probe is None:
        raise RunConfigError(
            "Operacao 'operations.%s' esta ligada, mas a secao "
            "'%s' esta ausente em run-config.json (obrigatoria quando a "
            "operacao esta ligada, contrato secao 3.1)."
            % (operation_key, section_name))

    if not operation_enabled and ladder_probe is not None:
        raise RunConfigError(
            "Secao '%s' presente em run-config.json, mas "
            "'operations.%s' esta desligada -- config incoerente "
            "nao e aceito por omissao (fail-closed, contrato secao 3.1)."
            % (section_name, operation_key))

    if not operation_enabled:
        return

    if not isinstance(ladder_probe, dict):
        raise RunConfigError(
            "Secao '%s' de run-config.json deve ser um objeto JSON "
            "(recebido: %s)." % (section_name, type(ladder_probe).__name__))

    for field in LADDER_PROBE_REQUIRED_FIELDS:
        if field not in ladder_probe:
            raise RunConfigError(
                "Campo obrigatorio ausente em '%s': '%s'."
                % (section_name, field))
        value = ladder_probe[field]
        if not isinstance(value, _STRING_TYPES) or not value:
            raise RunConfigError(
                "Campo '%s.%s' deve ser uma string nao vazia (recebido: %r)."
                % (section_name, field, value))


# Os tres probes Ladder investigam CANAIS diferentes (reflexao CLR /
# superficie dinamica / Extender) sobre o MESMO objeto. Rodar mais de um na
# mesma run e recusado enquanto nao houver suporte explicito: cada um tem seu
# proprio gate de validade e seu proprio diretorio de saida, e uma run com
# dois deles produziria dois vereditos concorrentes sob um unico status --
# ambiguidade justamente no registro que serve de auditoria. Separar as runs
# custa uma execucao a mais e mantem cada artefato autoexplicativo.
LADDER_PROBE_OPERATION_KEYS = (
    "probe_ladder_surface",
    "probe_ladder_dynamic_surface",
    "probe_ladder_extender_surface",
    "probe_plcopen_export_signature",
    "export_plcopen_xml",
)


def _validate_ladder_probes_mutually_exclusive(operations):
    enabled = [key for key in LADDER_PROBE_OPERATION_KEYS
              if bool(operations.get(key, False))]
    if len(enabled) > 1:
        raise RunConfigError(
            "Mais de um probe Ladder ligado na mesma run: %s. Cada probe "
            "investiga um canal distinto e tem gate de validade proprio -- "
            "combina-los produziria vereditos concorrentes sob um unico "
            "status. Rode um por vez." % ", ".join(sorted(enabled)))


# A secao do probe 19 tem os MESMOS 4 campos de identidade dos probes
# Ladder MAIS um booleano proprio, entao nao reusa
# _validate_ladder_probe_section (que exige exatamente 4 strings). Um campo
# aceito e silenciosamente ignorado seria o mesmo defeito que
# KNOWN_OPERATION_KEYS existe para impedir.
PLCOPEN_SIGNATURE_SECTION = "plcopen_export_signature_probe"
PLCOPEN_SIGNATURE_OPERATION = "probe_plcopen_export_signature"


def _validate_plcopen_signature_section(config, operations):
    section = config.get(PLCOPEN_SIGNATURE_SECTION)
    enabled = bool(operations.get(PLCOPEN_SIGNATURE_OPERATION, False))

    if enabled and section is None:
        raise RunConfigError(
            "Operacao 'operations.%s' esta ligada, mas a secao '%s' esta ausente "
            "em run-config.json." % (PLCOPEN_SIGNATURE_OPERATION, PLCOPEN_SIGNATURE_SECTION))
    if not enabled and section is not None:
        raise RunConfigError(
            "Secao '%s' presente mas 'operations.%s' desligada -- config incoerente "
            "nao e aceito por omissao (fail-closed)."
            % (PLCOPEN_SIGNATURE_SECTION, PLCOPEN_SIGNATURE_OPERATION))
    if not enabled:
        return

    if not isinstance(section, dict):
        raise RunConfigError(
            "Secao '%s' deve ser um objeto JSON (recebido: %s)."
            % (PLCOPEN_SIGNATURE_SECTION, type(section).__name__))

    for field in LADDER_PROBE_REQUIRED_FIELDS:
        if field not in section:
            raise RunConfigError(
                "Campo obrigatorio ausente em '%s': '%s'."
                % (PLCOPEN_SIGNATURE_SECTION, field))
        value = section[field]
        if not isinstance(value, _STRING_TYPES) or not value:
            raise RunConfigError(
                "Campo '%s.%s' deve ser uma string nao vazia (recebido: %r)."
                % (PLCOPEN_SIGNATURE_SECTION, field, value))

    # Booleano ESTRITO: aceitar 0/1/"true" faria a config parecer valida com
    # um valor que nao expressa a intencao. Ausente vale True (inspecionar),
    # que e o comportamento util por padrao.
    if "inspect_active_application" in section:
        flag = section["inspect_active_application"]
        if not isinstance(flag, bool):
            raise RunConfigError(
                "Campo '%s.inspect_active_application' deve ser booleano true/false "
                "(recebido: %r)." % (PLCOPEN_SIGNATURE_SECTION, flag))


PLCOPEN_EXPORT_SECTION = "plcopen_export"
PLCOPEN_EXPORT_OPERATION = "export_plcopen_xml"

# Os tres booleanos existem para AUDITORIA -- para um run-config.json
# arquivado dizer com que argumentos a exportacao correu -- e nao para abrir
# uma matriz livre de execucao. Nesta versao qualquer valor diferente de
# False reprova: uma combinacao nao testada nao pode entrar em producao por
# alguem editar o JSON.
PLCOPEN_EXPORT_FALSE_ONLY_FIELDS = ("recursive", "export_folder_structure", "plain_text")


def _validate_plcopen_export_section(config, operations):
    section = config.get(PLCOPEN_EXPORT_SECTION)
    enabled = bool(operations.get(PLCOPEN_EXPORT_OPERATION, False))

    if enabled and section is None:
        raise RunConfigError(
            "Operacao 'operations.%s' esta ligada, mas a secao '%s' esta ausente."
            % (PLCOPEN_EXPORT_OPERATION, PLCOPEN_EXPORT_SECTION))
    if not enabled and section is not None:
        raise RunConfigError(
            "Secao '%s' presente mas 'operations.%s' desligada -- config incoerente "
            "nao e aceito por omissao (fail-closed)."
            % (PLCOPEN_EXPORT_SECTION, PLCOPEN_EXPORT_OPERATION))
    if not enabled:
        return

    if not isinstance(section, dict):
        raise RunConfigError(
            "Secao '%s' deve ser um objeto JSON (recebido: %s)."
            % (PLCOPEN_EXPORT_SECTION, type(section).__name__))

    for field in LADDER_PROBE_REQUIRED_FIELDS + ("target_leaf_name",):
        if field not in section:
            raise RunConfigError(
                "Campo obrigatorio ausente em '%s': '%s'."
                % (PLCOPEN_EXPORT_SECTION, field))
        value = section[field]
        if not isinstance(value, _STRING_TYPES) or not value:
            raise RunConfigError(
                "Campo '%s.%s' deve ser uma string nao vazia (recebido: %r)."
                % (PLCOPEN_EXPORT_SECTION, field, value))

    for field in PLCOPEN_EXPORT_FALSE_ONLY_FIELDS:
        if field not in section:
            raise RunConfigError(
                "Campo obrigatorio ausente em '%s': '%s' (exigido explicitamente "
                "para o run-config arquivado registrar com que argumentos a "
                "exportacao correu)." % (PLCOPEN_EXPORT_SECTION, field))
        value = section[field]
        if value is not False:
            raise RunConfigError(
                "Campo '%s.%s' deve ser exatamente false nesta versao (recebido: "
                "%r). Os tres booleanos existem para auditoria, nao para abrir "
                "matriz de execucao." % (PLCOPEN_EXPORT_SECTION, field, value))


def _is_positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _resolve_limits(raw_limits):
    """Valida a secao opcional 'limits' e devolve um dict TOTALMENTE
    preenchido (defaults aplicados onde faltar), para o chamador
    (supervised_snapshot_runner.py) nunca ter que decidir um default por
    conta propria. Fail-closed: chave desconhecida em qualquer um dos 3
    blocos, ou valor que nao seja inteiro positivo (exceto
    'expected_root_count', que aceita None), reprova o config inteiro --
    mesmo criterio ja aplicado a 'operations'."""
    if raw_limits is None:
        raw_limits = {}
    if not isinstance(raw_limits, dict):
        raise RunConfigError(
            "Campo 'limits' de run-config.json deve ser um objeto JSON "
            "(recebido: %s)." % type(raw_limits).__name__)

    for block_name in raw_limits:
        if block_name not in LIMIT_BLOCK_NAMES:
            raise RunConfigError(
                "Chave desconhecida em 'limits': '%s'. FuncoesExemplo validos: %s."
                % (block_name, ", ".join(LIMIT_BLOCK_NAMES)))

    resolved = {}
    for block_name in LIMIT_BLOCK_NAMES:
        block_defaults = DEFAULT_LIMITS[block_name]
        raw_block = raw_limits.get(block_name, {})
        if raw_block is None:
            raw_block = {}
        if not isinstance(raw_block, dict):
            raise RunConfigError(
                "Campo 'limits.%s' de run-config.json deve ser um objeto "
                "JSON (recebido: %s)." % (block_name, type(raw_block).__name__))

        for key in raw_block:
            if key not in block_defaults:
                raise RunConfigError(
                    "Chave desconhecida em 'limits.%s': '%s'. Fail-closed: "
                    "um limite que o runner nao conhece nao pode ser "
                    "silenciosamente ignorado." % (block_name, key))

        resolved_block = {}
        for key, default_value in block_defaults.items():
            value = raw_block.get(key, default_value)
            if key == "expected_root_count":
                if value is not None and not _is_positive_int(value):
                    raise RunConfigError(
                        "Valor invalido em 'limits.%s.%s': deve ser um "
                        "inteiro positivo ou null (recebido: %r)."
                        % (block_name, key, value))
            else:
                if not _is_positive_int(value):
                    raise RunConfigError(
                        "Valor invalido em 'limits.%s.%s': deve ser um "
                        "inteiro positivo (recebido: %r)."
                        % (block_name, key, value))
            resolved_block[key] = value
        resolved[block_name] = resolved_block

    return resolved

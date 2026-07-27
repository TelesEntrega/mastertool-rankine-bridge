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

    _validate_ladder_probe_section(config, operations)

    config["limits"] = _resolve_limits(config.get("limits"))

    return config


def _validate_ladder_probe_section(config, operations):
    """Valida a secao opcional 'ladder_probe' (contrato, secao 3.1). Regra
    fail-closed EM AMBAS AS DIRECOES -- nao so a ausencia quando a operacao
    esta ligada, mas TAMBEM a presenca quando a operacao esta desligada
    (config incoerente nao e aceito por omissao, mesmo criterio ja aplicado
    a 'operations'/'limits'):

        probe_ladder_surface=true  e ladder_probe ausente        -> reprova
        probe_ladder_surface=false e ladder_probe presente        -> reprova
        probe_ladder_surface=true  e ladder_probe com campo vazio -> reprova
    """
    ladder_probe = config.get("ladder_probe")
    operation_enabled = bool(operations.get("probe_ladder_surface", False))

    if operation_enabled and ladder_probe is None:
        raise RunConfigError(
            "Operacao 'operations.probe_ladder_surface' esta ligada, mas a secao "
            "'ladder_probe' esta ausente em run-config.json (obrigatoria quando a "
            "operacao esta ligada, contrato secao 3.1).")

    if not operation_enabled and ladder_probe is not None:
        raise RunConfigError(
            "Secao 'ladder_probe' presente em run-config.json, mas "
            "'operations.probe_ladder_surface' esta desligada -- config incoerente "
            "nao e aceito por omissao (fail-closed, contrato secao 3.1).")

    if not operation_enabled:
        return

    if not isinstance(ladder_probe, dict):
        raise RunConfigError(
            "Secao 'ladder_probe' de run-config.json deve ser um objeto JSON "
            "(recebido: %s)." % type(ladder_probe).__name__)

    for field in LADDER_PROBE_REQUIRED_FIELDS:
        if field not in ladder_probe:
            raise RunConfigError(
                "Campo obrigatorio ausente em 'ladder_probe': '%s'." % field)
        value = ladder_probe[field]
        if not isinstance(value, _STRING_TYPES) or not value:
            raise RunConfigError(
                "Campo 'ladder_probe.%s' deve ser uma string nao vazia (recebido: %r)."
                % (field, value))


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

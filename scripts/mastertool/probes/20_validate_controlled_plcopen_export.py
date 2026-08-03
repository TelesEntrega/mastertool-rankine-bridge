# -*- coding: utf-8 -*-
"""20_validate_controlled_plcopen_export.py -- Fase L1 (docs/14-ladder-roadmap.md),
IRMAO de probes/19_probe_plcopen_xml_export_signature.py -- mesma identidade de
alvo, mesma navegacao bounded/indexada, mesma verificacao de identidade (4
campos, ordem fixa). A MUDANCA desta fatia: pela primeira vez nesta trilha,
uma chamada real ao ScriptObject e feita, e ela ESCREVE EM DISCO.

Motivacao (o "porque"): o probe 19 (reflexao pura, nunca invoca) confirmou
por evidencia de runtime que `export_xml` tem 4 sobrecargas no proxy-alvo, e
que a sobrecarga de 4 argumentos SEM `IExportReporter` e:

    stPath (System.String, pos=0), bRecursive (System.Boolean, pos=1),
    bExportFolderStructure (System.Boolean, pos=2), bPlainText (System.Boolean, pos=3)

Nenhum parametro e opcional, nenhum e out/ref -- confirmado por reflexao real
(nao suposto). A semantica de `stPath` (se recebe um caminho de ARQUIVO ou de
DIRETORIO) permanece DESCONHECIDA -- e exatamente o que esta execucao
descobre, por observacao pos-chamada, nunca por suposicao previa.

Perfil de seguranca desta fatia (diferente do probe 19): a escrita em disco e
AUTORIZADA, mas estritamente contida --

    - a UNICA invocacao permitida e `target.export_xml(st_path, False, False, False)`,
      EXATAMENTE UMA VEZ, com os 4 argumentos explicitos acima -- NUNCA
      `MethodInfo.Invoke()`, NUNCA as sobrecargas com `IExportReporter` ou
      `ConflictResolve` (import_xml continua fora de escopo, permanentemente);
    - o destino (`stPath`) e sempre um filho AINDA INEXISTENTE de um
      diretorio descartavel (`export-root`) que o CHAMADOR ja criou, vazio,
      dentro da propria run -- este probe NUNCA cria `export-root`, so
      confirma suas propriedades antes de escrever;
    - toda guarda (identidade, caminho, sobrecarga) e verificada ANTES da
      invocacao; qualquer reprovacao aborta SEM chamar `export_xml`;
    - nenhuma outra API e tocada: sem save/build/import/online/download/force,
      sem leitura de `.text`, sem `str()`/`repr()`/`ToString()` sobre proxies
      ou tipos refletidos.

Este probe NAO interpreta o XML produzido (isso e trabalho do HOST, offline,
fora de escopo aqui) -- so registra o que foi criado (caminho relativo,
tipo, tamanho, SHA-256), nunca o conteudo.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

# --- bootstrap: tornar 'common' importavel quando executado standalone
# (--runscript). Copia identica do bloco equivalente em probes/19_....py.
try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    _MASTERTOOL_DIR = os.path.dirname(_SCRIPT_DIR)
    _FILE_AVAILABLE = True
except NameError:
    _SCRIPT_DIR = None
    _MASTERTOOL_DIR = None
    _FILE_AVAILABLE = False
if _MASTERTOOL_DIR and _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)
REPO_ROOT = os.path.abspath(os.path.join(_MASTERTOOL_DIR, "..", "..")) if _MASTERTOOL_DIR else None
EXPORT_ROOT = os.path.join(REPO_ROOT, "workspace", "exports") if REPO_ROOT else None

from common import artifacts, capabilities, checksums, compatibility, file_io  # noqa: E402

# Strings nativas: basestring cobre str/unicode no IronPython 2.7; so 'str'
# em Python 3 (testes). Mesma logica de common/capabilities.py.
try:
    _STRING_TYPES = (basestring,)  # noqa: F821
except NameError:
    _STRING_TYPES = (str,)

EXPORT_XML_METHOD_NAME = "export_xml"

# A assinatura EXATA (nome/tipo, na ordem) da UNICA sobrecarga autorizada
# nesta fatia -- evidencia real do probe 19, nunca suposicao.
EXPECTED_PARAM_TYPES = ("System.String", "System.Boolean", "System.Boolean", "System.Boolean")

# Campos exigidos em plcopen_export_config, alem dos 3 booleanos (que tem
# tratamento proprio, fail-closed).
REQUIRED_CONFIG_STRING_FIELDS = (
    "target_node_id", "expected_name", "expected_guid", "expected_type_guid", "target_leaf_name",
)
CONFIG_BOOLEAN_FIELDS = ("recursive", "export_folder_structure", "plain_text")

# Limites de inventario -- defesa contra uma exportacao inesperadamente
# gigante travar o probe. Nunca abortam a invocacao (que ja aconteceu quando
# o inventario roda) -- so limitam QUANTO e registrado, com diagnostico
# explicito, nunca silenciosamente.
DEFAULT_MAX_INVENTORY_ENTRIES = 5000
DEFAULT_MAX_INVENTORY_DEPTH = 32
DEFAULT_MAX_HASHED_FILE_BYTES = 200 * 1024 * 1024  # 200 MiB

# Alvo padrao para execucao STANDALONE (--runscript) -- MESMO alvo do probe
# 19 (mesma POU ja usada para reflexao da assinatura, agora exportada de
# fato).
DEFAULT_TARGET_NODE_ID = "application/9/4"
DEFAULT_EXPECTED_NAME = "BLINK_QUE_FUNCIONA"
DEFAULT_EXPECTED_GUID = "beca53e2-8466-404a-baf5-9fba1adc0fac"
DEFAULT_EXPECTED_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
DEFAULT_TARGET_LEAF_NAME = "pou-export"


# =============================================================================
# Procedencia do runtime -- copia adaptada de
# automation/supervised_snapshot_runner.py:_check_provenance (mesmo
# racional: platform=='cli' E IronPython E version_info[:3]==(2,7,12) --
# isolada em funcao propria, injetavel via parametro `provenance_check`, para
# que os testes de unidade (CPython 3.11) possam substituir SO este ponto de
# decisao e exercitar as guardas SEGUINTES sem um interprete IronPython real.
# =============================================================================

def _check_provenance():
    try:
        version_info = tuple(sys.version_info[:3])
    except Exception:
        version_info = None
    ironpython = bool(compatibility.is_ironpython())
    platform_cli = (sys.platform == "cli")
    ok = bool(ironpython and platform_cli and version_info == (2, 7, 12))
    detail = ("platform=%r, compatibility.is_ironpython()=%r, version_info[:3]=%r"
              % (sys.platform, ironpython, version_info))
    runtime = {
        "platform": sys.platform,
        "runtime_family": "IronPython" if ironpython else "CPython",
        "version_info": list(version_info) if version_info is not None else None,
        "provenance_confirmed": ok,
    }
    return ok, detail, runtime


# =============================================================================
# Navegacao bounded/indexada -- copia local deliberada do mesmo padrao
# aprovado nos probes 16/17/18/19 (mesma filosofia de independencia por
# modulo). get_children(False) + Count + indexador nativo -- NUNCA
# iteracao direta da colecao CLR.
# =============================================================================

def _call_get_children(proxy, obj_label):
    record = capabilities.probe_method_call(
        proxy, obj_label, "get_children", (False,), capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return record["state"], None, record.get("exception_message")
    return "confirmed", record["raw_value"], None


def _read_count(collection, obj_label):
    record = capabilities.probe_member(
        collection, obj_label, "Count", capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return record["state"], None, record.get("exception_message")
    raw = record["raw_value"]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return "unknown", None, "Count nao e um inteiro valido (tipo: %s)." % compatibility.safe_type_name(raw)
    return "confirmed", raw, None


def _access_index(collection, obj_label, index):
    record = capabilities.probe_indexer_access(
        collection, obj_label, index, capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return record["state"], None, record.get("exception_message")
    return "confirmed", record["raw_value"], None


def _parse_node_path(target_node_id):
    """'application/9/4' -> [9, 4]. 'application' -> []. Qualquer outro
    formato -> None (invalido). Copia identica dos probes 16/17/18/19."""
    if not isinstance(target_node_id, _STRING_TYPES) or not target_node_id:
        return None
    parts = target_node_id.split("/")
    if not parts or parts[0] != "application":
        return None
    indices = []
    for part in parts[1:]:
        try:
            idx = int(part)
        except Exception:
            return None
        if idx < 0:
            return None
        indices.append(idx)
    return indices


def _navigate_to_target(application, indices, diagnostics):
    """Navega da Application ate o no alvo, indice a indice, usando SOMENTE
    get_children(False) + Count + indexador nativo. Copia identica dos
    probes 16/17/18/19."""
    proxy = application
    node_id = "application"
    label = "application"

    for idx in indices:
        gc_state, children, gc_err = _call_get_children(proxy, label)
        if gc_state != "confirmed":
            diagnostics.append({
                "step": "navigation", "node_id": node_id,
                "message": "get_children(False) falhou: state=%s erro=%s" % (gc_state, gc_err),
            })
            return None, node_id, "get_children_failed"

        if children is None:
            diagnostics.append({
                "step": "navigation", "node_id": node_id,
                "message": "get_children(False) retornou colecao nula.",
            })
            return None, node_id, "children_collection_null"

        count_state, count_value, count_err = _read_count(children, label + "_children")
        if count_state != "confirmed":
            diagnostics.append({
                "step": "navigation", "node_id": node_id,
                "message": "leitura de Count falhou: state=%s erro=%s" % (count_state, count_err),
            })
            return None, node_id, "count_read_failed"

        if idx >= count_value:
            diagnostics.append({
                "step": "navigation", "node_id": node_id,
                "message": "indice %s fora do intervalo (Count=%s)." % (idx, count_value),
            })
            return None, node_id, "index_out_of_range"

        idx_state, child_proxy, idx_err = _access_index(children, label + "_children", idx)
        if idx_state != "confirmed":
            diagnostics.append({
                "step": "navigation", "node_id": node_id,
                "message": "acesso ao indice %s falhou: state=%s erro=%s" % (idx, idx_state, idx_err),
            })
            return None, node_id, "indexer_failed"

        proxy = child_proxy
        node_id = node_id + "/" + str(idx)
        label = "node_" + node_id.replace("/", "_")

    diagnostics.append({
        "step": "navigation", "node_id": node_id,
        "message": "navegacao concluida com sucesso.",
    })
    return proxy, node_id, None


# =============================================================================
# Identidade -- copia local deliberada, identica aos probes 16/17/18/19
# (mesmo contrato, secao 3.1).
# =============================================================================

def _field_result(state, value=None, error=None):
    return {"state": state, "value": value, "error": error}


def _probe_property_via_representation(obj, obj_label, member_name):
    record = capabilities.probe_member(
        obj, obj_label, member_name, capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return _field_result(record["state"], error=record.get("exception_message"))
    value = record["raw_value"]
    python_type = capabilities.python_type_info(value)
    dotnet_type = capabilities.dotnet_type_info(value)
    rep = capabilities.build_representation(value, python_type, dotnet_type)
    if not rep["value_available"]:
        return _field_result(
            "unrepresentable",
            error="valor obtido, mas sem representacao segura (tipo .NET nao confirmado).")
    return _field_result("confirmed", value=rep["value"])


def _probe_name_via_method_call(obj, obj_label):
    record = capabilities.probe_method_call(
        obj, obj_label, "get_name", (False,), capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return _field_result(record["state"], error=record.get("exception_message"))
    value = record["raw_value"]
    python_type = capabilities.python_type_info(value)
    dotnet_type = capabilities.dotnet_type_info(value)
    rep = capabilities.build_representation(value, python_type, dotnet_type)
    if not rep["value_available"]:
        return _field_result("unrepresentable", error="nome obtido, mas sem representacao segura.")
    return _field_result("confirmed", value=rep["value"])


def _bool_field(field_result):
    if field_result["state"] != "confirmed":
        return field_result
    if isinstance(field_result["value"], bool):
        return field_result
    return _field_result(
        "unrepresentable",
        error="valor obtido nao e bool (tipo: %s)." % compatibility.safe_type_name(field_result["value"]))


def _probe_target_identity(proxy, obj_label):
    """Os 4 campos de identidade exigidos pela sequencia obrigatoria (nome,
    object_guid, type_guid, is_folder), na MESMA ordem do contrato."""
    return {
        "name": _probe_name_via_method_call(proxy, obj_label),
        "object_guid": _probe_property_via_representation(proxy, obj_label, "guid"),
        "type_guid": _probe_property_via_representation(proxy, obj_label, "type"),
        "is_folder": _bool_field(_probe_property_via_representation(proxy, obj_label, "is_folder")),
    }


def _check_identity(identity, plcopen_export_config):
    """Compara os 4 campos observados contra os 4 'expected_*' do config, NA
    ORDEM do contrato: name -> object_guid -> type_guid -> is_folder==False.
    Retorna lista de mismatches (vazia se tudo confere) -- TODOS os campos
    sao checados (nao para no primeiro)."""
    mismatches = []

    def _check_field(field_name, identity_key, expected_value):
        field = identity.get(identity_key)
        observed_state = field.get("state") if field else "unknown"
        observed_value = field.get("value") if field else None
        if observed_state != "confirmed" or observed_value != expected_value:
            mismatches.append({
                "field": field_name,
                "expected": expected_value,
                "observed_state": observed_state,
                "observed_value": observed_value,
            })

    _check_field("name", "name", plcopen_export_config["expected_name"])
    _check_field("object_guid", "object_guid", plcopen_export_config["expected_guid"])
    _check_field("type_guid", "type_guid", plcopen_export_config["expected_type_guid"])
    _check_field("is_folder", "is_folder", False)

    return mismatches


# =============================================================================
# Configuracao -- validacao FAIL-CLOSED, defesa em profundidade (mesma regra
# dos probes 16/17/18/19: nenhum caminho de codigo confia cegamente no
# formato de plcopen_export_config).
# =============================================================================

def _validate_config(config, diagnostics):
    """Retorna None se valido, ou um abort_reason nomeado."""
    if not isinstance(config, dict):
        diagnostics.append({"step": "config_validation", "message": "plcopen_export_config nao e um dict."})
        return "plcopen_export_config_invalid"

    for field in REQUIRED_CONFIG_STRING_FIELDS:
        value = config.get(field)
        if not isinstance(value, _STRING_TYPES) or not value:
            diagnostics.append({
                "step": "config_validation",
                "message": "campo obrigatorio ausente/vazio em plcopen_export_config: %s" % field,
            })
            return "plcopen_export_config_invalid"

    # Os 3 booleanos: FAIL-CLOSED. Ausentes -> tratados como False (seguro).
    # Presentes -> tem que ser EXATAMENTE `False` (bool estrito -- 0/1/"false"
    # reprovam). Estes campos existem para AUDITORIA nesta versao, nao para
    # abrir uma matriz de execucao.
    for field in CONFIG_BOOLEAN_FIELDS:
        if field not in config:
            continue
        value = config[field]
        if not isinstance(value, bool) or value is not False:
            diagnostics.append({
                "step": "config_validation",
                "message": "campo booleano '%s' deve ser exatamente False nesta versao (obtido: %r)."
                          % (field, value),
            })
            return "plcopen_export_boolean_not_false"

    return None


def _validate_target_leaf_name(name):
    """`target_leaf_name` precisa ser um nome de arquivo SIMPLES: sem
    separador de caminho, sem '..'/'.', sem caminho absoluto, sem letra de
    unidade. Retorna (True, None) ou (False, abort_reason)."""
    if not isinstance(name, _STRING_TYPES) or not name.strip():
        return False, "target_leaf_name_empty"
    if "/" in name or "\\" in name:
        return False, "target_leaf_name_contains_separator"
    if name in (".", ".."):
        return False, "target_leaf_name_dot_segment"
    if ":" in name:
        return False, "target_leaf_name_drive_letter"
    try:
        if os.path.isabs(name):
            return False, "target_leaf_name_absolute"
    except Exception:
        return False, "target_leaf_name_absolute"
    return True, None


# =============================================================================
# export-root -- deteccao de reparse point (junction/symlink) compativel com
# IronPython (via System.IO) e CPython (via os.stat().st_file_attributes,
# usado pelos testes). Isolada em funcao propria e injetavel pelo chamador
# (mesmo racional do provenance_check): testes de unidade podem substituir
# este UNICO ponto de decisao para simular um reparse point sem precisar
# criar uma junction real (privilegio elevado no Windows).
# =============================================================================

def _is_reparse_point(path):
    try:
        from System.IO import File, FileAttributes  # IronPython/.NET
        attrs = File.GetAttributes(path)
        return bool(int(attrs) & int(FileAttributes.ReparsePoint))
    except Exception:
        pass
    try:
        st = os.lstat(path)
        attrs = getattr(st, "st_file_attributes", None)
        if attrs is not None:
            return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except Exception:
        pass
    try:
        return os.path.islink(path)
    except Exception:
        return False


def _normalize_path(path):
    try:
        return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))
    except Exception:
        return None


def _is_within(path, root):
    norm_path = _normalize_path(path)
    norm_root = _normalize_path(root)
    if norm_path is None or norm_root is None:
        return False
    if norm_path == norm_root:
        return True
    return norm_path.startswith(norm_root + os.sep)


def _check_export_root(export_root, run_dir, diagnostics, is_reparse_point_fn):
    """Guardas sobre `export-root`: dentro da run, existe, vazio, e nunca um
    link/junction/reparse point. Retorna None (ok) ou um abort_reason
    nomeado."""
    if not _is_within(export_root, run_dir):
        diagnostics.append({"step": "export_root_check",
                            "message": "export-root fora da run: %s" % export_root})
        return "export_root_outside_run"
    if is_reparse_point_fn(export_root):
        diagnostics.append({"step": "export_root_check",
                            "message": "export-root e um link/junction/reparse point: %s" % export_root})
        return "export_root_is_reparse_point"
    if not os.path.isdir(export_root):
        diagnostics.append({"step": "export_root_check",
                            "message": "export-root nao existe (deveria ter sido criado pelo chamador): %s"
                                      % export_root})
        return "export_root_missing"
    try:
        contents = os.listdir(export_root)
    except Exception as exc:
        diagnostics.append({"step": "export_root_check",
                            "message": "listdir(export-root) falhou: %s" % compatibility.safe_repr(exc)})
        return "export_root_listdir_failed"
    if contents:
        diagnostics.append({"step": "export_root_check",
                            "message": "export-root nao esta vazio: %r" % (contents,)})
        return "export_root_not_empty"
    return None


# =============================================================================
# Reflexao da sobrecarga de 4 argumentos -- SOMENTE metadados ate a
# invocacao autorizada. Copia LOCAL (nao reusa probes/19) porque este probe
# so precisa confirmar UMA sobrecarga especifica, nao a superficie inteira.
# =============================================================================

def _reflect_overload_summary(method, params):
    entry = {"declaring_type": None, "return_type": None, "parameters": []}
    try:
        entry["declaring_type"] = method.DeclaringType.FullName
    except Exception:
        pass
    try:
        entry["return_type"] = method.ReturnType.FullName
    except Exception:
        pass
    for param in params:
        p = {"name": None, "type": None, "position": None, "is_out": None, "is_by_ref": None}
        try:
            p["name"] = param.Name
        except Exception:
            pass
        try:
            p["type"] = param.ParameterType.FullName
        except Exception:
            pass
        try:
            p["position"] = param.Position
        except Exception:
            pass
        try:
            p["is_out"] = bool(param.IsOut)
        except Exception:
            pass
        try:
            p["is_by_ref"] = bool(param.ParameterType.IsByRef)
        except Exception:
            pass
        entry["parameters"].append(p)
    return entry


def _overload_matches_four_arg_signature(entry):
    params = entry["parameters"]
    if len(params) != len(EXPECTED_PARAM_TYPES):
        return False
    for position, expected_type in enumerate(EXPECTED_PARAM_TYPES):
        param = params[position]
        if param.get("type") != expected_type:
            return False
        if param.get("is_out") or param.get("is_by_ref"):
            return False
    return True


def _find_unique_four_arg_overload(clr_type, diagnostics):
    """Re-percorre GetMethods()/GetParameters() (SO metadados) e devolve
    (overload_summary, abort_reason, all_export_xml_overloads). Exige que
    EXATAMENTE UMA sobrecarga de 'export_xml' bata com
    (String, Boolean, Boolean, Boolean), nenhum out/ref -- nunca escolhe por
    contagem de parametros isolada, nunca por nome de parametro (so
    tipo+posicao+out/by_ref, evidencia ja confirmada pelo probe 19)."""
    all_overloads = []
    if clr_type is None:
        diagnostics.append({"step": "overload_reflection", "message": "clr_type indisponivel (None)."})
        return None, "get_type_unavailable", all_overloads

    try:
        raw_methods = clr_type.GetMethods()
    except Exception as exc:
        diagnostics.append({"step": "overload_reflection",
                            "message": "GetMethods() falhou: %s" % compatibility.safe_repr(exc)})
        return None, "get_methods_failed", all_overloads

    matches = []
    for method in raw_methods:
        try:
            name = method.Name
        except Exception:
            continue
        if name != EXPORT_XML_METHOD_NAME:
            continue
        try:
            params = method.GetParameters()
        except Exception as exc:
            diagnostics.append({"step": "overload_reflection",
                                "message": "GetParameters() falhou para uma sobrecarga de '%s': %s"
                                          % (EXPORT_XML_METHOD_NAME, compatibility.safe_repr(exc))})
            continue
        entry = _reflect_overload_summary(method, params)
        all_overloads.append(entry)
        if _overload_matches_four_arg_signature(entry):
            matches.append(entry)

    diagnostics.append({
        "step": "overload_reflection",
        "message": "%d sobrecarga(s) de '%s' refletida(s), %d compativel(is) com "
                  "(String, Boolean, Boolean, Boolean) sem out/ref."
                  % (len(all_overloads), EXPORT_XML_METHOD_NAME, len(matches)),
    })

    if len(matches) != 1:
        return None, "overload_not_uniquely_confirmed", all_overloads
    return matches[0], None, all_overloads


# =============================================================================
# Inventario do filesystem -- percurso ITERATIVO (pilha explicita) sobre
# `export-root`, com limites obrigatorios (entradas/profundidade/tamanho de
# arquivo para hash). Reparse points sao registrados e NUNCA seguidos, mesmo
# quando aparentam ser diretorio.
# =============================================================================

def _inventory_export_root(export_root, diagnostics, is_reparse_point_fn,
                           max_entries=DEFAULT_MAX_INVENTORY_ENTRIES,
                           max_depth=DEFAULT_MAX_INVENTORY_DEPTH,
                           max_hashed_file_bytes=DEFAULT_MAX_HASHED_FILE_BYTES):
    entries = []
    limits_hit = {"max_entries_reached": False, "max_depth_reached": False}
    stack = [(export_root, 0)]

    while stack:
        current_dir, depth = stack.pop()
        if depth > max_depth:
            limits_hit["max_depth_reached"] = True
            diagnostics.append({"step": "inventory",
                                "message": "max_depth (%s) atingido em '%s' -- ramo interrompido."
                                          % (max_depth, current_dir)})
            continue
        try:
            names = sorted(os.listdir(current_dir))
        except Exception as exc:
            diagnostics.append({"step": "inventory",
                                "message": "listdir falhou em '%s': %s"
                                          % (current_dir, compatibility.safe_repr(exc))})
            continue

        for name in names:
            if len(entries) >= max_entries:
                limits_hit["max_entries_reached"] = True
                diagnostics.append({"step": "inventory",
                                    "message": "max_entries (%s) atingido -- inventario interrompido."
                                              % max_entries})
                entries.sort(key=lambda e: e["relative_path"])
                return entries, limits_hit

            full_path = os.path.join(current_dir, name)
            rel_path = os.path.relpath(full_path, export_root).replace("\\", "/")

            if is_reparse_point_fn(full_path):
                # NUNCA segue um reparse point, mesmo que aparente ser um
                # diretorio -- so registra o ramo e para ali.
                entries.append({
                    "relative_path": rel_path, "kind": "reparse_point",
                    "size_bytes": None, "sha256": None, "is_reparse_point": True,
                })
                continue

            if os.path.isdir(full_path):
                entries.append({
                    "relative_path": rel_path, "kind": "directory",
                    "size_bytes": None, "sha256": None, "is_reparse_point": False,
                })
                stack.append((full_path, depth + 1))
            elif os.path.isfile(full_path):
                try:
                    size = os.path.getsize(full_path)
                except Exception:
                    size = None
                digest = None
                if size is not None and size <= max_hashed_file_bytes:
                    try:
                        digest = checksums.sha256_file(full_path)
                    except Exception as exc:
                        diagnostics.append({"step": "inventory",
                                            "message": "sha256 falhou para '%s': %s"
                                                      % (rel_path, compatibility.safe_repr(exc))})
                elif size is not None:
                    diagnostics.append({"step": "inventory",
                                        "message": "arquivo '%s' (%s bytes) excede max_hashed_file_bytes "
                                                  "(%s) -- hash omitido, entrada preservada."
                                                  % (rel_path, size, max_hashed_file_bytes)})
                entries.append({
                    "relative_path": rel_path, "kind": "file",
                    "size_bytes": size, "sha256": digest, "is_reparse_point": False,
                })
            else:
                entries.append({
                    "relative_path": rel_path, "kind": "other",
                    "size_bytes": None, "sha256": None, "is_reparse_point": False,
                })

    entries.sort(key=lambda e: e["relative_path"])
    return entries, limits_hit


# =============================================================================
# Classificacao PURA do resultado -- fonte unica de verdade, reaplicavel a
# artefatos ja arquivados sem reimplementacao. NUNCA interpreta o conteudo do
# XML produzido (isso e trabalho do host, offline).
# =============================================================================

def classify_export_result(invoked, raised_exception, created_entries_count):
    """Devolve (result_case, status, verdict_message).

    - invoked=False: a invocacao foi rejeitada por uma guarda ANTES de
      acontecer -- este caso normalmente nao chega aqui (o chamador aborta e
      grava abort_reason sem classificar), mas a funcao permanece total para
      ser testavel em isolamento.
    - invoked=True e raised_exception=True: `export_invocation_failed`.
    - invoked=True, sem excecao, created_entries_count==0: `P3_no_output`
      (nada foi criado -- inconclusivo, nao um erro).
    - invoked=True, sem excecao, created_entries_count>0: `P_created` (a
      distincao fina P1/P2/P4 -- arquivo unico vs pasta vs multiplos
      arquivos -- e do HOST, offline; este probe NAO interpreta XML)."""
    if not invoked:
        return ("not_invoked", "blocked",
                "invocacao nunca aconteceu: uma guarda reprovou antes da chamada.")
    if raised_exception:
        return ("export_invocation_failed", "failed",
                "export_xml() foi chamado e lancou excecao -- ver invocation.json para a mensagem.")
    if created_entries_count == 0:
        return ("P3_no_output", "inconclusive",
                "export_xml() foi chamado, retornou sem excecao, mas nenhum arquivo/diretorio foi "
                "criado em export-root. Inconclusivo -- nenhuma conclusao sobre a semantica de "
                "stPath e permitida a partir daqui.")
    return ("P_created", "ok",
            "export_xml() foi chamado, retornou sem excecao, e %d entrada(s) foram criadas em "
            "export-root. A distincao fina (arquivo unico / pasta / multiplos arquivos) cabe ao "
            "HOST, offline, a partir de filesystem-after.json -- este probe nao interpreta XML."
            % created_entries_count)


# =============================================================================
# Escrita de artefatos.
# =============================================================================

_EMPTY_INVOCATION_DOC = {
    "overload_declaring_type": None, "overload_parameters": None, "arguments": None,
    "return_value": None, "raised_exception": None, "exception_message": None,
    "invoked_at": None,
    "note": "export_xml() NUNCA foi chamado -- uma guarda reprovou antes da invocacao.",
}


def _build_report_markdown(result, diagnostics, invocation, before_entries, after_entries,
                           created_entries):
    lines = [
        "# Exportacao PLCopen XML controlada -- probe_validate_controlled_plcopen_export",
        "",
        "Fase L1 (docs/14-ladder-roadmap.md), IRMAO do probe 19. PRIMEIRA fatia desta trilha "
        "que escreve em disco -- escrita restrita a um diretorio descartavel autorizado "
        "(`export-root`), via UMA UNICA chamada a `export_xml(stPath, False, False, False)`.",
        "",
        "- target_node_id: `%s`" % result.get("target_node_id"),
        "- abortado: **%s**" % result.get("aborted"),
        "- motivo do aborto: %s" % result.get("abort_reason"),
        "- identidade da Application confirmada: **%s**" % result.get("application_identity_confirmed"),
        "- identidade do alvo (POU) confirmada: **%s**" % result.get("target_identity_confirmed"),
        "- export_xml chamado: **%s** (contagem: %s)"
        % (result.get("export_xml_called"), result.get("export_xml_call_count")),
        "- resultado: **%s**" % result.get("result_case"),
        "- status: **%s**" % result.get("status"),
        "",
    ]

    if invocation and invocation is not _EMPTY_INVOCATION_DOC:
        lines.append("## Invocacao")
        lines.append("- sobrecarga: declaring_type=`%s`" % invocation.get("overload_declaring_type"))
        lines.append("- argumentos: %r" % (invocation.get("arguments"),))
        lines.append("- retorno: %r" % invocation.get("return_value"))
        lines.append("- lancou excecao: **%s** (%s)"
                     % (invocation.get("raised_exception"), invocation.get("exception_message")))
        lines.append("")

    lines.append("## Inventario de export-root")
    lines.append("- entradas ANTES da chamada: %d (esperado: 0)" % len(before_entries))
    lines.append("- entradas DEPOIS da chamada: %d" % len(after_entries))
    lines.append("- entradas CRIADAS por esta chamada: %d" % len(created_entries))
    for entry in created_entries:
        lines.append("  - `%s` (%s, %s bytes, sha256=%s, reparse_point=%s)"
                     % (entry["relative_path"], entry["kind"], entry["size_bytes"],
                        entry["sha256"], entry["is_reparse_point"]))
    lines.append("")

    lines.append("## Diagnosticos (%d)" % len(diagnostics))
    for diag in diagnostics:
        lines.append("- [%s] %s" % (diag.get("step"), diag.get("message")))
    lines.append("")

    lines.append("## Nota sobre checksums.sha256")
    lines.append(
        "`checksums.sha256` cobre SOMENTE os artefatos deste probe (invocation.json, "
        "filesystem-before.json, filesystem-after.json, created-artifacts.json, "
        "diagnostics.json, safety-declaration.json, report.md) -- NUNCA o conteudo de "
        "`export-root/`, que ja tem seu proprio SHA-256 por arquivo em created-artifacts.json.")
    lines.append("")

    return "\n".join(lines) + "\n"


def _identity_field_value(identity, key):
    """Extrai o valor observado de um campo de identidade, ou None se o
    campo nunca foi confirmado (estado != 'confirmed'). Usado so para
    popular `result`, nunca para decidir mismatch (isso e `_check_identity`,
    que ja rodou antes)."""
    field = identity.get(key) if identity else None
    if not field or field.get("state") != "confirmed":
        return None
    return field.get("value")


def _build_target_identity_doc(result):
    """Conteudo de `target-identity.json`, derivado EXCLUSIVAMENTE de
    `result` (mais nada) -- ver docstring de `_write_target_identity`. Duas
    chamadas com o mesmo `result` produzem o mesmo documento (idempotencia
    por construcao, sem cache nem flag de 'ja escrevi')."""
    return {
        "schema_version": 1,
        "target_node_id": result.get("target_node_id"),
        "name": result.get("target_identity_name"),
        "guid": result.get("target_identity_object_guid"),
        "type_guid": result.get("target_identity_type_guid"),
        "is_folder": result.get("target_identity_is_folder"),
        "identity_confirmed": bool(result.get("target_identity_confirmed")),
        "identity_check_reached": bool(result.get("target_identity_check_reached")),
        "mismatches": result.get("target_identity_mismatches") or [],
    }


def _write_target_identity(output_dir, result):
    """Grava `target-identity.json` -- artefato proprio e checksummado da
    identidade do alvo (docs/19-contratos-de-execucao.md secao 4). Chamada
    em TRES pontos (logo apos a Guarda 4, nos dois caminhos -- confere e
    diverge --, e de novo dentro de `_write_artifacts`, para o caso de
    aborto ANTES da Guarda 4). Como o conteudo vem so de `result`, as
    chamadas repetidas produzem os mesmos bytes quando o estado nao mudou:
    escrita idempotente por construcao, sem necessidade de cache."""
    file_io.ensure_dir(output_dir)
    doc = _build_target_identity_doc(result)
    file_io.write_json(os.path.join(output_dir, "target-identity.json"), doc)
    return doc


def _write_artifacts(output_dir, export_root, result, diagnostics, invocation=None,
                     before_entries=None, after_entries=None, before_limits=None,
                     after_limits=None):
    file_io.ensure_dir(output_dir)

    before_entries = before_entries or []
    after_entries = after_entries or []
    before_keys = set(e["relative_path"] for e in before_entries)
    created_entries = [e for e in after_entries if e["relative_path"] not in before_keys]

    invocation_doc = invocation if invocation is not None else dict(_EMPTY_INVOCATION_DOC)

    file_io.write_json(os.path.join(output_dir, "invocation.json"), invocation_doc)
    file_io.write_json(os.path.join(output_dir, "filesystem-before.json"), {
        "export_root": export_root, "entries": before_entries,
        "count": len(before_entries), "limits": before_limits or {},
    })
    file_io.write_json(os.path.join(output_dir, "filesystem-after.json"), {
        "export_root": export_root, "entries": after_entries,
        "count": len(after_entries), "limits": after_limits or {},
    })
    file_io.write_json(os.path.join(output_dir, "created-artifacts.json"), {
        "entries": created_entries, "count": len(created_entries),
    })

    # target-identity.json (docs/19-contratos-de-execucao.md secao 4) --
    # SEMPRE gravado aqui tambem, para cobrir o caso de aborto ANTES da
    # Guarda 4 (onde a chamada dedicada, mais proxima da checagem, nunca
    # aconteceu). Mesmo conteudo, mesma funcao -- ver docstring.
    _write_target_identity(output_dir, result)

    safety_declaration = {
        "export_xml_called": bool(result.get("export_xml_called")),
        "export_xml_call_count": int(result.get("export_xml_call_count") or 0),
        "filesystem_output_written": len(created_entries) > 0,
        "filesystem_output_scope": "authorized_disposable_export_root",
        "project_save_called": False,
        "project_build_called": False,
        "text_document_write_called": False,
        "import_called": False,
        "online_operation": False,
        "download_called": False,
        "force_called": False,
    }

    md = _build_report_markdown(result, diagnostics, invocation_doc, before_entries, after_entries,
                                created_entries)
    # Os quatro artefatos comuns saem por `common.artifacts`, com checksums
    # por ultimo. `export-root/` fica FORA: aquele conteudo veio da API do
    # MasterTool e tem hashes proprios em created-artifacts.json -- cobrir os
    # dois no mesmo arquivo confundiria "o que o probe gravou" com "o que a
    # API produziu".
    artifacts.write_common_artifacts(
        output_dir, diagnostics, safety_declaration, md,
        checksums_exclude_dirs=[export_root])

    result["artifacts_dir"] = output_dir
    result["created_entries_count"] = len(created_entries)
    return result


# =============================================================================
# Orquestracao.
# =============================================================================

def probe_controlled_plcopen_export(application, plcopen_export_config, output_dir,
                                    provenance_check=None, is_reparse_point_fn=None,
                                    max_inventory_entries=DEFAULT_MAX_INVENTORY_ENTRIES,
                                    max_inventory_depth=DEFAULT_MAX_INVENTORY_DEPTH,
                                    max_hashed_file_bytes=DEFAULT_MAX_HASHED_FILE_BYTES):
    """Ponto de entrada publico. `output_dir` e o diretorio 'plcopen-export/'
    -- `export-root` (subpasta) deve ja existir, vazia, criada pelo
    CHAMADOR (o runner supervisionado, fora de escopo aqui) ANTES desta
    chamada. Este probe NUNCA cria `export-root`, so confirma suas
    propriedades.

    `provenance_check` e `is_reparse_point_fn` sao pontos de decisao
    injetaveis (mesmo racional de `inspect_active_application` no probe 19):
    permitem que os testes de unidade (CPython 3.11) substituam SO esses
    dois pontos e exercitem todo o resto da sequencia sem um interprete
    IronPython real nem uma junction/symlink real no disco.

    Nunca lanca excecao: qualquer falha de guarda e capturada e reportada
    via diagnostics.json + result['abort_reason']. Sempre grava os
    artefatos obrigatorios (mesmo em caso de aborto)."""
    diagnostics = []
    result = {
        "schema_version": "1.0",
        "generated_at": file_io.iso_now(),
        "aborted": False,
        "abort_reason": None,
        "target_node_id": None,
        "application_identity_confirmed": False,
        "target_identity_confirmed": False,
        "target_identity_check_reached": False,
        "target_identity_name": None,
        "target_identity_object_guid": None,
        "target_identity_type_guid": None,
        "target_identity_is_folder": None,
        "target_identity_mismatches": [],
        "export_xml_called": False,
        "export_xml_call_count": 0,
        "export_xml_overload_candidates": 0,
        "result_case": None,
        "status": "blocked",
        "runtime": None,
    }

    export_root = os.path.join(output_dir, "export-root")
    reparse_fn = is_reparse_point_fn or _is_reparse_point

    def _abort(reason, message):
        result["aborted"] = True
        result["abort_reason"] = reason
        result["status"] = "failed"
        diagnostics.append({"step": "guard", "message": message})
        return _write_artifacts(output_dir, export_root, result, diagnostics)

    # Guarda 0: procedencia do runtime (cli / IronPython / 2.7.12). Ponto
    # unico, injetavel -- ver docstring de _check_provenance.
    check_fn = provenance_check or _check_provenance
    prov_ok, prov_detail, prov_runtime = check_fn()
    result["runtime"] = prov_runtime
    if not prov_ok:
        return _abort("runtime_provenance_not_confirmed",
                      "procedencia do runtime nao confirmada: %s" % prov_detail)

    # Guarda 1: formato do config.
    config_error = _validate_config(plcopen_export_config, diagnostics)
    if config_error:
        return _abort(config_error, "plcopen_export_config invalido/reprovado.")

    target_node_id = plcopen_export_config["target_node_id"]
    result["target_node_id"] = target_node_id
    target_leaf_name = plcopen_export_config["target_leaf_name"]

    leaf_ok, leaf_reason = _validate_target_leaf_name(target_leaf_name)
    if not leaf_ok:
        return _abort(leaf_reason, "target_leaf_name reprovado: %r" % (target_leaf_name,))

    # Guarda 2: identidade da Application.
    if application is None:
        return _abort("application_unavailable", "application e None.")
    app_name_field = _probe_name_via_method_call(application, "application")
    if app_name_field["state"] != "confirmed":
        return _abort(
            "application_identity_not_confirmed",
            "nao foi possivel confirmar a identidade da Application: %s" % app_name_field.get("error"))
    result["application_identity_confirmed"] = True
    diagnostics.append({"step": "identity_check",
                        "message": "identidade da Application confirmada (get_name(False))."})

    # Guarda 3: navegacao ate o alvo (POU).
    indices = _parse_node_path(target_node_id)
    if indices is None:
        return _abort("invalid_target_node_id", "target_node_id malformado: %r" % (target_node_id,))

    proxy, reached_node_id, nav_error = _navigate_to_target(application, indices, diagnostics)
    if proxy is None:
        return _abort("navigation_failed",
                      "falha ao navegar ate '%s': %s" % (target_node_id, nav_error))

    # Guarda 4: identidade do alvo (4 campos, ordem fixa -- inclui
    # is_folder==False, "POU nao e pasta").
    identity = _probe_target_identity(proxy, "plcopen_export_target")
    mismatches = _check_identity(identity, plcopen_export_config)
    result["target_identity_check_reached"] = True
    result["target_identity_name"] = _identity_field_value(identity, "name")
    result["target_identity_object_guid"] = _identity_field_value(identity, "object_guid")
    result["target_identity_type_guid"] = _identity_field_value(identity, "type_guid")
    result["target_identity_is_folder"] = _identity_field_value(identity, "is_folder")
    result["target_identity_mismatches"] = mismatches
    if mismatches:
        diagnostics.append({
            "step": "identity_check",
            "message": "divergencia(s) de identidade do alvo: %s" % mismatches,
        })
        # Grava target-identity.json AQUI -- antes do abort -- para que o
        # artefato exista em disco mesmo se o processo morrer logo depois
        # (mesmo racional do caminho de sucesso, abaixo).
        _write_target_identity(output_dir, result)
        return _abort("target_identity_mismatch", "identidade do alvo (POU) nao confere.")
    result["target_identity_confirmed"] = True
    diagnostics.append({"step": "identity_check",
                        "message": "identidade do alvo confirmada (name/object_guid/type_guid/"
                                  "is_folder) -- prosseguindo."})
    # Grava target-identity.json logo apos a confirmacao -- ANTES de
    # prosseguir para export_xml -- pelo mesmo motivo: o artefato deve
    # existir mesmo se o processo morrer durante a invocacao.
    _write_target_identity(output_dir, result)

    # Guarda 5: export-root (dentro da run, existe, vazio, nao e reparse point).
    export_root_error = _check_export_root(export_root, output_dir, diagnostics, reparse_fn)
    if export_root_error:
        return _abort(export_root_error, "export-root reprovado: %s" % export_root_error)

    # Guarda 6: alvo final ainda nao existe.
    final_target_path = os.path.join(export_root, target_leaf_name)
    if os.path.exists(final_target_path) or reparse_fn(final_target_path):
        return _abort("target_leaf_already_exists",
                      "alvo final ja existe: %s" % final_target_path)

    # Guarda 7: a sobrecarga de 4 argumentos, confirmada por reflexao, de
    # forma UNICA (nunca a sobrecarga com IExportReporter, nunca invocada via
    # MethodInfo.Invoke()).
    try:
        pou_clr_type = proxy.GetType()
    except Exception as exc:
        return _abort("get_type_failed",
                      "GetType() do proxy-alvo falhou: %s" % compatibility.safe_repr(exc))

    overload, overload_error, all_overloads = _find_unique_four_arg_overload(pou_clr_type, diagnostics)
    result["export_xml_overload_candidates"] = len(all_overloads)
    if overload is None:
        return _abort(overload_error,
                      "sobrecarga de 4 argumentos (String, Boolean, Boolean, Boolean) nao "
                      "confirmada de forma unica.")

    # Todas as guardas passaram. Inventario "antes" (deve ser vazio -- ja
    # confirmado pela Guarda 5, mas registrado aqui como evidencia formal).
    before_entries, before_limits = _inventory_export_root(
        export_root, diagnostics, reparse_fn, max_entries=max_inventory_entries,
        max_depth=max_inventory_depth, max_hashed_file_bytes=max_hashed_file_bytes)

    # =========================================================================
    # A UNICA invocacao autorizada nesta fatia. EXATAMENTE UMA VEZ.
    # =========================================================================
    invoked_at = file_io.iso_now()
    result["export_xml_called"] = True
    result["export_xml_call_count"] = 1
    raised_exception = False
    exception_message = None
    return_value_repr = None
    try:
        raw_return = proxy.export_xml(final_target_path, False, False, False)
    except Exception as exc:
        raised_exception = True
        exception_message = compatibility.safe_repr(exc)
    else:
        # O retorno conhecido e System.String (nao um proxy do ScriptEngine)
        # -- registrar como string e seguro aqui, diferente de
        # str()/repr() sobre um proxy desconhecido (regra 10 do AGENTS.md).
        if isinstance(raw_return, _STRING_TYPES):
            return_value_repr = raw_return
        elif raw_return is None:
            return_value_repr = None
        else:
            return_value_repr = compatibility.safe_repr(raw_return)

    after_entries, after_limits = _inventory_export_root(
        export_root, diagnostics, reparse_fn, max_entries=max_inventory_entries,
        max_depth=max_inventory_depth, max_hashed_file_bytes=max_hashed_file_bytes)

    before_keys = set(e["relative_path"] for e in before_entries)
    created_count = len([e for e in after_entries if e["relative_path"] not in before_keys])

    result_case, status, verdict = classify_export_result(True, raised_exception, created_count)
    result["result_case"] = result_case
    result["status"] = status
    diagnostics.append({"step": "verdict", "message": verdict})

    invocation_doc = {
        "overload_declaring_type": overload.get("declaring_type"),
        "overload_parameters": overload.get("parameters"),
        "arguments": [final_target_path, False, False, False],
        "return_value": return_value_repr,
        "raised_exception": raised_exception,
        "exception_message": exception_message,
        "invoked_at": invoked_at,
    }

    return _write_artifacts(output_dir, export_root, result, diagnostics, invocation_doc,
                            before_entries, after_entries, before_limits, after_limits)


# =============================================================================
# Execucao standalone (--runscript), mesmo padrao dos probes 16/17/18/19.
# =============================================================================

def main():
    print("=" * 60)
    print("[INFO] probes/20_validate_controlled_plcopen_export.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] PRIMEIRA fatia desta trilha que escreve em disco -- escrita restrita a um")
    print("[INFO] diretorio descartavel autorizado (export-root), via UMA UNICA chamada a")
    print("[INFO] export_xml(stPath, False, False, False).")

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[BLOQUEADO] __file__ indisponivel: execucao recusada.")
        print("=" * 60)
        return

    try:
        from common import project_access
    except Exception as exc:
        print("[ERROR] Falha ao importar modulos comuns: %r" % (exc,))
        print("=" * 60)
        return

    project, err = project_access.get_primary_project(globals())
    if project is None:
        print("[WARN] Projeto primario indisponivel: %s" % err)
        print("=" * 60)
        return

    try:
        application = getattr(project, "active_application")
    except Exception as exc:
        print("[WARN] project.active_application indisponivel: %r" % (exc,))
        print("=" * 60)
        return

    if application is None:
        print("[WARN] active_application e None.")
        print("=" * 60)
        return

    plcopen_export_config = {
        "target_node_id": DEFAULT_TARGET_NODE_ID,
        "expected_name": DEFAULT_EXPECTED_NAME,
        "expected_guid": DEFAULT_EXPECTED_GUID,
        "expected_type_guid": DEFAULT_EXPECTED_TYPE_GUID,
        "recursive": False,
        "export_folder_structure": False,
        "plain_text": False,
        "target_leaf_name": DEFAULT_TARGET_LEAF_NAME,
    }

    run_dir = file_io.new_export_dir(EXPORT_ROOT, "20_validate_controlled_plcopen_export")
    plcopen_export_dir = os.path.join(run_dir, "plcopen-export")
    export_root = os.path.join(plcopen_export_dir, "export-root")
    # Este script tambem faz o papel do "runner" nesta execucao STANDALONE
    # (--runscript): cria export-root vazio ANTES de chamar o probe, exatamente
    # o pre-requisito que a orquestracao supervisionada (fora de escopo aqui)
    # deve garantir em producao.
    file_io.ensure_dir(export_root)

    result = probe_controlled_plcopen_export(application, plcopen_export_config, plcopen_export_dir)

    if result["aborted"]:
        print("[BLOQUEADO] abort_reason=%s" % result["abort_reason"])
    else:
        print("[OK] result_case=%s status=%s export_xml_call_count=%s created_entries_count=%s"
             % (result["result_case"], result["status"], result["export_xml_call_count"],
                result.get("created_entries_count")))
    print("[OK] Artefatos gravados em: %s" % plcopen_export_dir)
    print("=" * 60)


main()

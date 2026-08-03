# -*- coding: utf-8 -*-
"""16_probe_ladder_object_surface.py -- Fase L1 (docs/14-ladder-roadmap.md:
"Descoberta da representacao Ladder"), operacao 'probe_ladder_surface' do
contrato do runner supervisionado (docs/16-supervised-runner-contract.md,
secao 3.1).

Objetivo desta fatia: descobrir COMO acessar a representacao Ladder de UM
objeto POU ja identificado com certeza (nao "qual objeto" -- isso e a Fase
L0, ja concluida). NAO interpreta a representacao. Nenhum parser Ladder
nesta fatia.

Sequencia obrigatoria (contrato, secao 3.1), sem excecao:

    localizar target_node_id -> conferir expected_name -> conferir
    expected_guid -> conferir expected_type_guid -> confirmar
    is_folder == false -> so entao inspecionar

Qualquer divergencia entre o observado e os 4 campos 'expected_*' do
ladder_probe (mais is_folder) aborta com 'target_identity_mismatch', SEM
sondar reflection/getters/candidatos. Os 25 candidatos da Fase L0
compartilham o MESMO type_guid (POU) -- por isso a identificacao forte exige
object_guid + node_id + name juntos (ver contrato, secao 3.1, "Identificacao
do alvo").

O que este probe PODE fazer, uma vez a identidade confirmada:
  1. Identidade e runtime (target-identity.json, runtime-types.json) --
     campos ja sondados durante a propria checagem de identidade acima, mais
     tipo Python/tipo CLR do proxy.
  2. Reflection-only (interfaces.json, properties.json, methods.json):
     GetType().GetInterfaces()/GetProperties()/GetMethods() -- SOMENTE
     leitura de metadados, NENHUMA invocacao nesta etapa.
  3. Getters seguros (safe-getter-results.json): so invoca um membro
     encontrado LITERALMENTE por reflection (nunca um nome adivinhado), sem
     parametros, propriedade/getter, nome fora de termos associados a
     escrita/alteracao/importacao/execucao, E presente na whitelist
     explicita SAFE_GETTER_WHITELIST (comentada abaixo). Cada getter isolado
     em seu proprio try/except (via common/capabilities.probe_member) -- uma
     falha nunca impede os demais.
  4. Candidatos (candidate-representation-members.json): um registro por
     membro (propriedade OU metodo) cujo nome/tipo de retorno bateu com pelo
     menos um EVIDENCE_TERM -- separa "encontrado" de "considerado
     relevante" de "realmente acessado" de "bloqueado por seguranca".

PROIBIDO nesta fase (contrato, secao "PROIBIDO"): ler '.text' de
implementacao; chamar export(); salvar arquivo via API do objeto; serializar
proxy com str()/repr()/ToString() (sempre via
common/capabilities.build_representation); chamar metodo so porque o nome
parece util; testar setter; importar/substituir objeto; criar rede ou
elemento; salvar projeto; compilar; operar online; modificar a POU; iniciar
parser Ladder.

Integracao com o runner supervisionado: a funcao publica
`probe_ladder_surface(application, ladder_probe_config, output_dir)` e o
ponto de entrada usado por automation/supervised_snapshot_runner.py -- que
carrega este modulo por CAMINHO (via `imp.load_source`, nao
`import probes.16_...`, que e SyntaxError porque o nome do arquivo comeca
com digito). Ver o comentario correspondente em
supervised_snapshot_runner.py. Este arquivo tambem roda standalone via
--runscript (mesmo padrao de probes/14_inventory_graphic_pous.py), com um
alvo padrao hardcoded SO para essa execucao avulsa (nunca usado pelo
runner, que sempre recebe ladder_probe_config vindo de run-config.json).

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

# --- bootstrap: tornar 'common' importavel quando executado standalone
# (--runscript). Quando este modulo e carregado pelo runner via
# imp.load_source, o sys.path ja foi preparado pelo bootstrap.py do host
# (contrato, secao 5) -- este bloco e redundante nesse caso, mas inofensivo.
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

# --- termos de classificacao (contrato, secao 3.1, item 2) -- usados SO
# para CLASSIFICAR um membro ja encontrado por reflection, nunca para
# inventar um nome a sondar.
EVIDENCE_TERMS = (
    "network", "ladder", "implementation", "graphical", "element",
    "connector", "connection", "pin", "export", "xml", "plcopen", "serialize",
)

# Termos associados a escrita/alteracao/importacao/execucao -- qualquer
# membro cujo NOME contenha um destes NUNCA e invocado, mesmo que esteja na
# whitelist abaixo por engano futuro (defesa em profundidade).
FORBIDDEN_GETTER_NAME_TERMS = (
    "write", "modify", "alter", "import", "execute", "invoke", "run",
    "save", "export", "delete", "remove", "create", "build", "compile",
    "download", "force", "close", "clear", "reset", "apply", "replace",
    "generate", "destroy", "dispose", "set_",
)

# Whitelist EXPLICITA de getters candidatos a invocacao (contrato, secao
# 3.1, item 3: "consta de uma whitelist explicita no codigo, comentada").
# Cada nome aqui e uma HIPOTESE de superficie de API tipica de frameworks
# CODESYS/MasterTool para objetos de implementacao grafica -- SO e
# efetivamente chamado se (a) aparecer por reflection REAL no objeto (nunca
# adivinhado como presente), (b) for propriedade/getter sem parametros, e
# (c) nao contiver nenhum termo de FORBIDDEN_GETTER_NAME_TERMS. Nomes
# deliberadamente EXCLUIDOS mesmo sendo provaveis candidatos: qualquer
# variante de "Export"/"Save"/"Import" (contrato: "chamar export() e
# proibido nesta fase -- assinatura e risco nao comprovados").
SAFE_GETTER_WHITELIST = (
    "Name", "FullName", "Guid", "Id",
    "Language", "ImplementationLanguage", "LanguageType",
    "Networks", "NetworkCount", "NetworkList",
    "Elements", "ElementCount",
    "Connections", "ConnectionCount",
    "Pins", "PinCount",
    "IsEmpty", "Count", "Length",
    "HasNetworks", "HasElements", "HasConnections",
    "XmlRepresentation", "PlcOpenXml",
)

# safety-declaration.json -- EXATAMENTE estas 10 chaves, todas False
# (contrato, secao 3.1). Nenhuma delas pode se tornar True nesta fase: nao
# ha caminho de codigo que chame export()/import/save/build/download/force,
# nem que leia '.text' de implementacao.
SAFETY_DECLARATION = {
    "text_document_read": False,
    "text_document_write": False,
    "export_called": False,
    "import_called": False,
    "save_called": False,
    "build_called": False,
    "online_operation": False,
    "download_called": False,
    "force_called": False,
    "project_modified": False,
}

# Alvo padrao para execucao STANDALONE deste probe (--runscript), escolhido
# por evidencia (contrato, secao 3.1, "Alvo da primeira execucao"). NUNCA
# usado pelo runner supervisionado -- este sempre recebe ladder_probe_config
# vindo de run-config.json (contrato, secao 3.1: "Nenhum destes valores pode
# ser hardcoded no probe ou no runner"; aqui a excecao e SOMENTE o modo
# standalone, mesmo padrao ja usado pelos EXPECTED_APPLICATION_* de
# probes/14_inventory_graphic_pous.py).
DEFAULT_TARGET_NODE_ID = "application/9/4"
DEFAULT_EXPECTED_NAME = "BLINK_QUE_FUNCIONA"
DEFAULT_EXPECTED_GUID = "beca53e2-8466-404a-baf5-9fba1adc0fac"
DEFAULT_EXPECTED_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"


# =============================================================================
# Navegacao bounded/indexada -- copia local deliberada do mesmo padrao ja
# aprovado em common/read_only_project_scanner.py e
# common/graphic_language_inventory.py (mesma filosofia de independencia por
# modulo ja documentada la: nao importar cruzado entre modulos de
# navegacao). get_children(False) + Count + indexador nativo -- NUNCA
# iteracao direta da colecao CLR (GetEnumerator()/iter()/list()).
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
    formato (prefixo diferente de 'application', indice nao inteiro, indice
    negativo) -> None (invalido)."""
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
    get_children(False) + Count + indexador nativo -- cada passo bounded
    (confere Count e limites de indice ANTES de indexar). Retorna
    (proxy, node_id_alcancado, motivo_de_falha_ou_None)."""
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
# Identidade (mesma tecnica de _probe_node_identity em
# common/graphic_language_inventory.py -- copia local deliberada).
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


def _node_runtime_info(proxy):
    python_type = capabilities.python_type_info(proxy)
    dotnet_type = capabilities.dotnet_type_info(proxy)
    rep = capabilities.build_representation(proxy, python_type, dotnet_type)
    return {
        "python_type": python_type,
        "dotnet_type": dotnet_type,
        "stringification_performed": rep["instance_stringification_performed"],
    }


def _check_identity(identity, ladder_probe_config):
    """Compara os 4 campos observados contra os 4 'expected_*' do config, NA
    ORDEM do contrato: name -> object_guid -> type_guid -> is_folder==False.
    Retorna lista de mismatches (vazia se tudo confere) -- TODOS os campos
    sao checados (nao para no primeiro), para o relatorio de aborto conter o
    diagnostico completo."""
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

    _check_field("name", "name", ladder_probe_config["expected_name"])
    _check_field("object_guid", "object_guid", ladder_probe_config["expected_guid"])
    _check_field("type_guid", "type_guid", ladder_probe_config["expected_type_guid"])
    _check_field("is_folder", "is_folder", False)

    return mismatches


# =============================================================================
# Reflection-only (contrato, secao 3.1, item 2). SOMENTE leitura de
# metadados via GetType()/GetInterfaces()/GetProperties()/GetMethods() --
# NENHUMA invocacao acontece aqui.
# =============================================================================

def _classify_evidence(name, return_type):
    """Classifica um membro pelos EVIDENCE_TERMS encontrados no nome OU no
    tipo de retorno (case-insensitive). Retorna os termos batidos, ordenados
    e unidos por virgula, ou 'unclassified' se nenhum bateu."""
    haystack = ((name or "") + " " + (return_type or "")).lower()
    matched = sorted(term for term in EVIDENCE_TERMS if term in haystack)
    if not matched:
        return "unclassified"
    return ",".join(matched)


def _safe_assembly_full_name(clr_type):
    try:
        return clr_type.Assembly.FullName
    except Exception:
        return None


def _reflect_attributes(member_info):
    """GetCustomAttributes(False) -- so os NOMES dos tipos de atributo (nao
    os valores das instancias). Best-effort: qualquer falha vira lista
    vazia, nunca aborta a reflection do membro."""
    try:
        raw_attributes = member_info.GetCustomAttributes(False)
    except Exception:
        return []
    names = []
    for attr in raw_attributes:
        try:
            names.append(type(attr).__name__)
        except Exception:
            continue
    return names


def _reflect_interfaces(proxy, diagnostics):
    try:
        clr_type = proxy.GetType()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_interfaces",
            "message": "GetType() falhou: %s" % compatibility.safe_repr(exc),
        })
        return []
    try:
        raw_interfaces = clr_type.GetInterfaces()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_interfaces",
            "message": "GetInterfaces() falhou: %s" % compatibility.safe_repr(exc),
        })
        return []

    result = []
    for iface in raw_interfaces:
        try:
            full_name = iface.FullName
        except Exception:
            full_name = None
        result.append({
            "interface": full_name,
            "assembly": _safe_assembly_full_name(iface),
        })
    return result


def _reflect_properties(clr_type, diagnostics):
    try:
        raw_properties = clr_type.GetProperties()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_properties",
            "message": "GetProperties() falhou: %s" % compatibility.safe_repr(exc),
        })
        return []

    result = []
    for prop in raw_properties:
        try:
            name = prop.Name
        except Exception:
            continue
        try:
            declaring_type = prop.DeclaringType.FullName
        except Exception:
            declaring_type = None
        try:
            return_type = prop.PropertyType.FullName
        except Exception:
            return_type = None
        try:
            has_index_parameters = len(prop.GetIndexParameters()) > 0
        except Exception:
            has_index_parameters = None
        try:
            can_read = bool(prop.CanRead)
        except Exception:
            can_read = None

        result.append({
            "member": name,
            "declaring_type": declaring_type,
            "member_kind": "property",
            "return_type": return_type,
            "parameters": [] if not has_index_parameters else [{"name": None, "type": "indexer"}],
            "can_read": can_read,
            "assembly": _safe_assembly_full_name(prop.PropertyType) if return_type else None,
            "attributes": _reflect_attributes(prop),
            "evidence_category": _classify_evidence(name, return_type),
        })
    return result


def _reflect_methods(clr_type, diagnostics):
    try:
        raw_methods = clr_type.GetMethods()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_methods",
            "message": "GetMethods() falhou: %s" % compatibility.safe_repr(exc),
        })
        return []

    result = []
    for method in raw_methods:
        try:
            # IsSpecialName == True cobre os accessors compilados
            # (get_Xxx/set_Xxx) ja representados em properties.json -- nao
            # duplicamos aqui.
            if getattr(method, "IsSpecialName", False):
                continue
            if not getattr(method, "IsPublic", True):
                continue
            name = method.Name
        except Exception:
            continue
        try:
            declaring_type = method.DeclaringType.FullName
        except Exception:
            declaring_type = None
        try:
            return_type = method.ReturnType.FullName
        except Exception:
            return_type = None

        parameters = []
        try:
            for param in method.GetParameters():
                try:
                    param_name = param.Name
                except Exception:
                    param_name = None
                try:
                    param_type = param.ParameterType.FullName
                except Exception:
                    param_type = None
                parameters.append({"name": param_name, "type": param_type})
        except Exception:
            pass

        result.append({
            "member": name,
            "declaring_type": declaring_type,
            "member_kind": "method",
            "return_type": return_type,
            "parameters": parameters,
            "assembly": _safe_assembly_full_name(method.ReturnType) if return_type else None,
            "attributes": _reflect_attributes(method),
            "evidence_category": _classify_evidence(name, return_type),
        })
    return result


def _build_candidates(properties, methods):
    """Um registro por membro (propriedade OU metodo) cujo evidence_category
    nao e 'unclassified' -- separa 'encontrado por reflection' (todo mundo
    em properties.json/methods.json) de 'considerado relevante' (aqui).
    EXATAMENTE as 8 chaves exigidas pelo contrato."""
    candidates = []
    for entry in list(properties) + list(methods):
        if entry["evidence_category"] == "unclassified":
            continue
        candidates.append({
            "member": entry["member"],
            "declaring_type": entry["declaring_type"],
            "member_kind": entry["member_kind"],
            "return_type": entry["return_type"],
            "parameters": entry["parameters"],
            "evidence_category": entry["evidence_category"],
            "invoked": False,
            "reason_not_invoked": "not yet evaluated",
        })
    return candidates


# =============================================================================
# Getters seguros (contrato, secao 3.1, item 3).
# =============================================================================

def _is_forbidden_getter_name(name):
    lowered = (name or "").lower()
    return any(term in lowered for term in FORBIDDEN_GETTER_NAME_TERMS)


def _run_safe_getters(proxy, candidates, diagnostics):
    """Para cada candidato, decide se pode ser invocado (todos os criterios
    do contrato SIMULTANEAMENTE) e, se sim, invoca via
    capabilities.probe_member (1 getattr, isolado em try/except proprio --
    uma falha aqui NUNCA impede os getters seguintes). Atualiza
    candidate['invoked']/['reason_not_invoked'] IN PLACE. Retorna a lista de
    resultados (safe-getter-results.json)."""
    results = []
    for candidate in candidates:
        name = candidate["member"]

        if candidate["member_kind"] != "property":
            candidate["reason_not_invoked"] = "member is a method, not a property/getter"
            continue
        if candidate.get("parameters"):
            candidate["reason_not_invoked"] = "member has parameters (not a plain getter)"
            continue
        if name not in SAFE_GETTER_WHITELIST:
            candidate["reason_not_invoked"] = "member not in SAFE_GETTER_WHITELIST"
            continue
        if _is_forbidden_getter_name(name):
            candidate["reason_not_invoked"] = (
                "member name associated with write/alter/import/execute -- never invoked")
            continue

        # Todos os criterios satisfeitos. Invocacao real, 1 getattr,
        # isolado (probe_member ja embrulha em try/except proprio).
        record = capabilities.probe_member(
            proxy, "ladder_target", name, capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)

        candidate["invoked"] = True
        candidate["reason_not_invoked"] = None

        representation = None
        if record["state"] == "confirmed" and "raw_value" in record:
            value = record["raw_value"]
            python_type = capabilities.python_type_info(value)
            dotnet_type = capabilities.dotnet_type_info(value)
            representation = capabilities.build_representation(value, python_type, dotnet_type)

        results.append({
            "member": name,
            "state": record["state"],
            "exception_type": record.get("exception_type"),
            "exception_message": record.get("exception_message"),
            "representation": representation,
        })
        diagnostics.append({
            "step": "safe_getter", "member": name, "message": "state=%s" % record["state"],
        })
    return results


# =============================================================================
# Orquestracao + escrita de artefatos.
# =============================================================================

def _build_report_markdown(result, target_identity, candidates, safe_getter_results):
    lines = [
        "# Sondagem de superficie do objeto Ladder -- probe_ladder_surface",
        "",
        "Fase L1 (docs/14-ladder-roadmap.md). Modo: **somente leitura**. "
        "Nenhum parser Ladder; nenhuma leitura de `.text` de implementacao.",
        "",
        "- target_node_id: `%s`" % result.get("target_node_id"),
        "- abortado: **%s**" % result.get("aborted"),
        "- motivo do aborto: %s" % result.get("abort_reason"),
        "- identidade do alvo confirmada: **%s**" % result.get("target_identity_confirmed"),
        "",
    ]
    if target_identity:
        lines.append("## Identidade observada")
        lines.append("- no alcancado: `%s`" % target_identity.get("reached_node_id"))
        for mismatch in target_identity.get("mismatches", []):
            lines.append(
                "- DIVERGENCIA em `%s`: esperado=%r observado_state=%s observado_valor=%r"
                % (mismatch["field"], mismatch["expected"], mismatch["observed_state"],
                   mismatch["observed_value"]))
        lines.append("")
    lines.append("## Candidatos a representacao (%d)" % len(candidates))
    for candidate in candidates[:200]:
        lines.append(
            "- `%s` (%s, %s) evidence=%s invoked=%s"
            % (candidate["member"], candidate["member_kind"], candidate["return_type"],
               candidate["evidence_category"], candidate["invoked"]))
    lines.append("")
    lines.append("## Getters seguros invocados (%d)" % len(safe_getter_results))
    for getter_result in safe_getter_results:
        lines.append("- `%s`: state=%s" % (getter_result["member"], getter_result["state"]))
    lines.append("")
    return "\n".join(lines) + "\n"


def _write_artifacts(output_dir, result, diagnostics, target_identity, runtime_types,
                     interfaces, properties, methods, candidates, safe_getter_results):
    file_io.ensure_dir(output_dir)

    manifest = {
        "schema_version": "1.0",
        "script": "probes/16_probe_ladder_object_surface.py",
        "generated_at": result["generated_at"],
        "mode": "read_only",
        "target_node_id": result["target_node_id"],
        "aborted": result["aborted"],
        "abort_reason": result["abort_reason"],
        "target_identity_confirmed": result["target_identity_confirmed"],
        "candidate_count": result["candidate_count"],
        "safe_getter_invocations": result["safe_getter_invocations"],
    }
    file_io.write_json(os.path.join(output_dir, "manifest.json"), manifest)
    file_io.write_json(os.path.join(output_dir, "target-identity.json"),
                       target_identity if target_identity is not None else {})
    file_io.write_json(os.path.join(output_dir, "runtime-types.json"),
                       runtime_types if runtime_types is not None else {})
    file_io.write_json(os.path.join(output_dir, "interfaces.json"), interfaces)
    file_io.write_json(os.path.join(output_dir, "properties.json"), properties)
    file_io.write_json(os.path.join(output_dir, "methods.json"), methods)
    file_io.write_json(os.path.join(output_dir, "safe-getter-results.json"), safe_getter_results)
    file_io.write_json(os.path.join(output_dir, "candidate-representation-members.json"), candidates)

    md = _build_report_markdown(result, target_identity, candidates, safe_getter_results)
    # Os quatro artefatos comuns (diagnostics, safety-declaration, report,
    # checksums) saem por `common.artifacts`, na ordem contratual e com
    # checksums por ultimo. O que e especifico deste probe continua acima.
    artifacts.write_common_artifacts(
        output_dir, diagnostics, dict(SAFETY_DECLARATION), md)

    result["artifacts_dir"] = output_dir
    return result


def probe_ladder_surface(application, ladder_probe_config, output_dir):
    """Ponto de entrada publico, usado pelo runner supervisionado (via
    imp.load_source) e pelos testes de unidade. `application` ja deve estar
    resolvida pelo chamador (mesmo padrao de scanner/exportador/inventario
    em common/). `ladder_probe_config` e o dict cru da secao 'ladder_probe'
    de run-config.json (4 chaves obrigatorias). `output_dir` e o diretorio
    ONDE os artefatos desta sondagem sao gravados diretamente -- o chamador
    decide o nome da subpasta (o runner usa 'output/ladder-surface-probe/',
    contrato secao 3.1).

    Nunca lanca excecao: qualquer falha de navegacao/identidade/reflection
    e capturada e reportada via diagnostics.json + result['abort_reason'].
    Sempre grava os artefatos obrigatorios (mesmo em caso de aborto, para
    auditoria completa de toda execucao)."""
    diagnostics = []
    result = {
        "schema_version": "1.0",
        "generated_at": file_io.iso_now(),
        "aborted": False,
        "abort_reason": None,
        "target_node_id": None,
        "target_identity_confirmed": False,
        "candidate_count": 0,
        "safe_getter_invocations": 0,
    }

    # Passo 0: defesa em profundidade -- este probe NAO confia cegamente no
    # chamador quanto ao formato de ladder_probe_config. A validacao "de
    # verdade" (fail-closed, reprova o run-config inteiro) e
    # responsabilidade de automation/run_config.py quando chamado pelo
    # runner; aqui e so uma guarda extra contra um chamador de teste/futuro
    # que nao passou por aquela validacao.
    required_fields = ("target_node_id", "expected_name", "expected_guid", "expected_type_guid")
    if not isinstance(ladder_probe_config, dict):
        result["aborted"] = True
        result["abort_reason"] = "ladder_probe_config_invalid"
        diagnostics.append({"step": "config_validation",
                            "message": "ladder_probe_config nao e um dict."})
        return _write_artifacts(output_dir, result, diagnostics, None, None, [], [], [], [], [])
    for field in required_fields:
        value = ladder_probe_config.get(field)
        if not isinstance(value, _STRING_TYPES) or not value:
            result["aborted"] = True
            result["abort_reason"] = "ladder_probe_config_invalid"
            diagnostics.append({"step": "config_validation",
                                "message": "campo ausente/vazio em ladder_probe_config: %s" % field})
            return _write_artifacts(output_dir, result, diagnostics, None, None, [], [], [], [], [])

    target_node_id = ladder_probe_config["target_node_id"]
    result["target_node_id"] = target_node_id

    # Passo 1: localizar target_node_id.
    indices = _parse_node_path(target_node_id)
    if indices is None:
        result["aborted"] = True
        result["abort_reason"] = "invalid_target_node_id"
        diagnostics.append({"step": "parse_node_path",
                            "message": "target_node_id malformado: %r" % (target_node_id,)})
        return _write_artifacts(output_dir, result, diagnostics, None, None, [], [], [], [], [])

    proxy, reached_node_id, nav_error = _navigate_to_target(application, indices, diagnostics)
    if proxy is None:
        result["aborted"] = True
        result["abort_reason"] = "navigation_failed"
        diagnostics.append({"step": "navigation",
                            "message": "falha ao navegar ate '%s': %s" % (target_node_id, nav_error)})
        return _write_artifacts(output_dir, result, diagnostics, None, None, [], [], [], [], [])

    # Passos 2-5: conferir expected_name -> expected_guid -> expected_type_guid
    # -> is_folder == false. SO ENTAO inspecionar.
    identity = _probe_target_identity(proxy, "ladder_target")
    runtime_types = _node_runtime_info(proxy)
    mismatches = _check_identity(identity, ladder_probe_config)

    target_identity_doc = {
        "target_node_id": target_node_id,
        "reached_node_id": reached_node_id,
        "identity": identity,
        "mismatches": mismatches,
    }

    if mismatches:
        result["aborted"] = True
        result["abort_reason"] = "target_identity_mismatch"
        diagnostics.append({
            "step": "identity_check",
            "message": "divergencia(s) de identidade -- abortando SEM sondar reflection/getters: %s"
                      % mismatches,
        })
        return _write_artifacts(
            output_dir, result, diagnostics, target_identity_doc, runtime_types, [], [], [], [], [])

    result["target_identity_confirmed"] = True
    diagnostics.append({
        "step": "identity_check",
        "message": "identidade confirmada (name/object_guid/type_guid/is_folder) -- prosseguindo.",
    })

    # A partir daqui: reflection-only + getters seguros (contrato, itens 2 e 3).
    interfaces = _reflect_interfaces(proxy, diagnostics)

    try:
        clr_type = proxy.GetType()
    except Exception as exc:
        clr_type = None
        diagnostics.append({
            "step": "reflect", "message": "GetType() falhou apos identidade confirmada: %s"
                                          % compatibility.safe_repr(exc),
        })

    properties = _reflect_properties(clr_type, diagnostics) if clr_type is not None else []
    methods = _reflect_methods(clr_type, diagnostics) if clr_type is not None else []

    candidates = _build_candidates(properties, methods)
    safe_getter_results = _run_safe_getters(proxy, candidates, diagnostics)

    result["candidate_count"] = len(candidates)
    result["safe_getter_invocations"] = len(safe_getter_results)

    return _write_artifacts(
        output_dir, result, diagnostics, target_identity_doc, runtime_types,
        interfaces, properties, methods, candidates, safe_getter_results)


# =============================================================================
# Execucao standalone (--runscript), mesmo padrao de
# probes/14_inventory_graphic_pous.py.
# =============================================================================

def main():
    print("=" * 60)
    print("[INFO] probes/16_probe_ladder_object_surface.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. Fase L1 -- descobre a superficie de API")
    print("[INFO] do objeto POU-alvo (reflection-only + getters seguros da whitelist).")
    print("[INFO] Nenhum parser Ladder. Nenhuma leitura de .text de implementacao.")

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

    ladder_probe_config = {
        "target_node_id": DEFAULT_TARGET_NODE_ID,
        "expected_name": DEFAULT_EXPECTED_NAME,
        "expected_guid": DEFAULT_EXPECTED_GUID,
        "expected_type_guid": DEFAULT_EXPECTED_TYPE_GUID,
    }

    run_dir = file_io.new_export_dir(EXPORT_ROOT, "16_probe_ladder_object_surface")
    result = probe_ladder_surface(application, ladder_probe_config, run_dir)

    if result["aborted"]:
        print("[BLOQUEADO] abort_reason=%s" % result["abort_reason"])
    else:
        print("[OK] identidade confirmada; candidate_count=%s safe_getter_invocations=%s"
             % (result["candidate_count"], result["safe_getter_invocations"]))
    print("[OK] Artefatos gravados em: %s" % run_dir)
    print("=" * 60)


main()

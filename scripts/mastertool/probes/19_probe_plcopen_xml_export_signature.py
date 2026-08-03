# -*- coding: utf-8 -*-
"""19_probe_plcopen_xml_export_signature.py -- Fase L1 (docs/14-ladder-roadmap.md:
"Descoberta da representacao Ladder"), IRMAO de probes/16_probe_ladder_object_surface.py,
probes/17_probe_ladder_dynamic_surface.py e probes/18_probe_ladder_extender_surface.py --
mesma identidade de alvo, mesmo modo somente leitura.

Motivacao (o "porque"): tres canais de introspeccao foram eliminados por
evidencia. Probe 16 (reflexao CLR pura sobre o proxy-alvo) NAO expoe os
membros dinamicos do ScriptEngine -- 'textual_declaration' (membro
comprovadamente funcional) nao aparece na lista, provando que a reflexao
estatica tem um falso-negativo estrutural. Probe 17 (dir() + hasattr()
controlado) confirmou que dir() do proxy volta VAZIO -- nenhuma conclusao
sobre existencia/ausencia de uma API Ladder por esse canal. Probe 18
(reflexao do membro 'Extender') confirmou que o Extender devolve o MESMO
`ScriptObject` (nao um `ICustomTypeDescriptor`/provider distinto) -- o canal
de extensao dinamica nao e uma rota nova, e sim o mesmo objeto ja refletido
pelo probe 16.

A rota que sobra e a exportacao oficial: `export_xml` existe no proxy-alvo
(confirmado por reflexao no probe 16, 4 sobrecargas), e uma sobrecarga de
`import_xml` recebe um parametro do tipo
`_3S.CoDeSys.PLCopenXML.ConflictResolve` -- evidencia forte de que a familia
e PLCopen XML, o formato de intercambio IEC 61131-3 que representa LD/FBD/SFC
graficamente (docs/14-ladder-roadmap.md, secao "Achado positivo").

Mas a assinatura de `export_xml` NAO esta completamente conhecida. O probe 16
capturou apenas `name`/`type` por parametro (metodos.json). Antes de invocar
um metodo que ESCREVE EM DISCO, e preciso conhecer optionality, defaults, o
significado do retorno e o ESCOPO do metodo (isolado no objeto POU, ou
tambem presente na Application/no projeto -- pergunta que separa os casos P2
e P3 do roadmap). Invocar sobre assinatura suposta e exatamente o que
AGENTS.md proibe (regra 1: "Nao invente APIs").

ESTE PROBE NAO INVOCA NADA. E read-only estrito, como os probes 16/17/18 --
so refletimos METADADOS (GetType()/GetMethods()/GetParameters()/
GetCustomAttributes()/GetInterfaces()/GetMembers()/GetEnumNames()/
GetFields()), nunca uma CHAMADA de export_xml/import_xml/export_native/
import_native ou qualquer outro metodo do proxy-alvo.

Sequencia obrigatoria de execucao desta fatia (ordem fixa, sem excecao):

    confirmar identidade do alvo (4 campos, contrato secao 3.1)
    -> refletir TODAS as sobrecargas de 'export_xml' no tipo CLR do
       proxy-alvo (POU): por parametro, name/type/IsOptional/DefaultValue/
       RawDefaultValue/IsOut/IsIn/IsByRef/Position/HasDefaultValue -- cada
       leitura em try/except proprio; por metodo, attributes/IsStatic/
       IsPublic/DeclaringType/ReturnType/assembly
    -> refletir TODAS as sobrecargas de 'import_xml' pelo mesmo processo
       (so reflexao -- import continua PROIBIDO)
    -> verificar o ESCOPO de 'export_xml': presente no POU (ja refletido
       acima) e, SE alcancavel sem invocar nada novo, na Application
       (o proprio parametro 'application' recebido por esta funcao, ja
       resolvido pelo chamador -- nenhuma navegacao adicional necessaria
       para alcanca-la) e no objeto de projeto (registrado como nao
       tentado, honestamente, porque esta assinatura de entrada nao recebe
       o objeto de projeto)
    -> localizar o tipo do parametro 'IExportReporter' entre os parametros
       ja refletidos de 'export_xml' (busca por substring no FullName, sem
       adivinhar um nome), e caracteriza-lo por reflexao: interface?
       membros? assembly? NUNCA instanciado
    -> localizar o tipo do parametro '_3S.CoDeSys.PLCopenXML.ConflictResolve'
       entre os parametros ja refletidos de 'import_xml', e enumerar seus
       membros via GetEnumNames()/GetFields() (cada um em try/except
       proprio) -- NUNCA usado para nada alem de registro
    -> classificar o resultado (S1/S2/S3) via classify_signature_probe_result

PROIBIDO nesta fase (defesa em profundidade -- guarda ANTES de qualquer
chamada, nao so ausencia de invocacao no codigo): invocar export_xml,
import_xml, export_native, import_native ou QUALQUER metodo do proxy-alvo;
instanciar qualquer tipo refletido (IExportReporter, ConflictResolve, ou
qualquer outro); str()/repr()/ToString() sobre proxies ou sobre os tipos
refletidos (toda representacao de VALOR passa por
common/capabilities.build_representation, nunca por formatacao implicita da
instancia); ler '.text'; setters; escrever em disco pela API do objeto;
salvar/compilar/online/download/force; criar/remover objetos.

Mesma identidade de alvo dos probes 16/17/18 (contrato, secao 3.1): os 4
campos 'expected_*' (nome, object_guid, type_guid) mais is_folder==False,
checados NA MESMA ORDEM, ANTES de qualquer sondagem de assinatura. Qualquer
divergencia aborta com 'target_identity_mismatch'.

Esta fatia AINDA NAO escreve XML -- a mudanca de perfil de seguranca (S1
abrindo espaco para uma exportacao controlada, com destino descartavel e
autorizacao humana explicita) vem na fatia seguinte, fora de escopo aqui.

Integracao com o runner supervisionado: esta fatia NAO altera
automation/supervised_snapshot_runner.py nem run_config.py (fora de escopo).
Este arquivo roda standalone via --runscript, mesmo padrao dos probes
16/17/18, com um alvo padrao hardcoded SO para essa execucao avulsa.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

# --- bootstrap: tornar 'common' importavel quando executado standalone
# (--runscript). Copia identica do bloco equivalente em
# probes/18_probe_ladder_extender_surface.py -- mesmo racional la documentado.
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

# Copia LITERAL de probes/16/17/18. Qualquer membro cujo NOME contenha um
# destes termos NUNCA e invocado, mesmo que apareca em alguma whitelist por
# engano futuro (defesa em profundidade). 'export_xml'/'import_xml' SEMPRE
# batem aqui ('export'/'import') -- o campo 'forbidden_term' resultante e
# preservado nos registros como prova de que a guarda foi aplicada, nao so
# ausencia de chamada no codigo.
FORBIDDEN_GETTER_NAME_TERMS = (
    "write", "modify", "alter", "import", "execute", "invoke", "run",
    "save", "export", "delete", "remove", "create", "build", "compile",
    "download", "force", "close", "clear", "reset", "apply", "replace",
    "generate", "destroy", "dispose", "set_",
)

# Nomes literais dos metodos refletidos (nunca invocados).
EXPORT_XML_METHOD_NAME = "export_xml"
IMPORT_XML_METHOD_NAME = "import_xml"

# Tipos primitivos aceitos para uma sobrecarga ser considerada "invocavel com
# seguranca" pela classificacao S1 (contrato: "todos os parametros da
# sobrecarga escolhida tem tipo conhecido e primitivo (String/Boolean)").
PRIMITIVE_PARAMETER_TYPES = ("System.String", "System.Boolean")

# Substrings usadas para localizar, entre os parametros JA refletidos, o
# tipo do reporter de exportacao e o enum de resolucao de conflito -- nunca
# usadas para adivinhar um nome a sondar, so para IDENTIFICAR um tipo dentro
# de uma assinatura ja obtida por reflexao real.
EXPORT_REPORTER_TYPE_SUBSTRING = "iexportreporter"
CONFLICT_RESOLVE_TYPE_SUBSTRING = "conflictresolve"

# safety-declaration.json -- EXATAMENTE estas 10 chaves, todas False. Copia
# literal do mesmo dicionario dos probes 16/17/18: nenhum caminho de codigo
# desta fatia chama export()/import/save/build/download/force, nem le
# '.text', nem escreve em disco -- so metadados de reflexao.
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

# Alvo padrao para execucao STANDALONE deste probe (--runscript) -- IDENTICO
# ao default dos probes 16/17/18 (mesmo alvo, mesma evidencia de escolha).
DEFAULT_TARGET_NODE_ID = "application/9/4"
DEFAULT_EXPECTED_NAME = "BLINK_QUE_FUNCIONA"
DEFAULT_EXPECTED_GUID = "beca53e2-8466-404a-baf5-9fba1adc0fac"
DEFAULT_EXPECTED_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"


# =============================================================================
# Navegacao bounded/indexada -- copia local deliberada do mesmo padrao
# aprovado nos probes 16/17/18 (mesma filosofia de independencia por
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
    formato -> None (invalido). Copia identica dos probes 16/17/18."""
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
    probes 16/17/18."""
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
# Identidade -- copia local deliberada, identica aos probes 16/17/18 (mesmo
# contrato, secao 3.1).
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


def _check_identity(identity, ladder_probe_config):
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

    _check_field("name", "name", ladder_probe_config["expected_name"])
    _check_field("object_guid", "object_guid", ladder_probe_config["expected_guid"])
    _check_field("type_guid", "type_guid", ladder_probe_config["expected_type_guid"])
    _check_field("is_folder", "is_folder", False)

    return mismatches


# =============================================================================
# Helpers de reflexao puros -- SOMENTE metadados, NUNCA invocacao.
# =============================================================================

def _forbidden_term_in(name):
    """Devolve o termo proibido que o nome contem, ou None -- usado para
    ANOTAR o registro do metodo (defesa em profundidade). export_xml/
    import_xml SEMPRE batem aqui ('export'/'import')."""
    lowered = (name or "").lower()
    for term in FORBIDDEN_GETTER_NAME_TERMS:
        if term in lowered:
            return term
    return None


def _safe_assembly_full_name(clr_type):
    try:
        return clr_type.Assembly.FullName
    except Exception:
        return None


def _safe_clr_full_name(obj):
    """GetType().FullName isolado -- NUNCA repr()/str()/ToString() sobre a
    instancia (so o NOME DO TIPO, obtido via reflexao)."""
    try:
        return obj.GetType().FullName
    except Exception:
        return None


def _reflect_attributes(member_info):
    """GetCustomAttributes(False) -- so os NOMES dos tipos de atributo (nao
    os valores das instancias). Best-effort: qualquer falha vira lista
    vazia, nunca aborta a reflexao do membro. Copia do mesmo padrao usado em
    probes/16_probe_ladder_object_surface.py."""
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


def _represent_reflected_value(value):
    """Representa com seguranca um valor obtido por reflexao (DefaultValue/
    RawDefaultValue de um parametro) -- NUNCA str()/repr() direto. Reusa o
    mesmo pipeline de common/capabilities.build_representation ja aplicado a
    valores de proxy nos probes 16/17/18."""
    try:
        python_type = capabilities.python_type_info(value)
        dotnet_type = capabilities.dotnet_type_info(value)
        rep = capabilities.build_representation(value, python_type, dotnet_type)
        return rep["value"] if rep["value_available"] else None
    except Exception:
        return None


def _reflect_parameter(param):
    """Le os campos de UM ParameterInfo exigidos pelo contrato -- cada
    leitura em try/except proprio (nem toda propriedade existe em todo
    runtime)."""
    entry = {
        "name": None, "type": None, "position": None, "is_optional": None,
        "has_default_value": None, "default_value": None, "raw_default_value": None,
        "is_out": None, "is_in": None, "is_by_ref": None,
    }
    try:
        entry["name"] = param.Name
    except Exception:
        pass
    try:
        entry["type"] = param.ParameterType.FullName
    except Exception:
        pass
    try:
        entry["position"] = param.Position
    except Exception:
        pass
    try:
        entry["is_optional"] = bool(param.IsOptional)
    except Exception:
        pass
    try:
        entry["has_default_value"] = bool(param.HasDefaultValue)
    except Exception:
        pass
    try:
        entry["default_value"] = _represent_reflected_value(param.DefaultValue)
    except Exception:
        pass
    try:
        entry["raw_default_value"] = _represent_reflected_value(param.RawDefaultValue)
    except Exception:
        pass
    try:
        entry["is_out"] = bool(param.IsOut)
    except Exception:
        pass
    try:
        entry["is_in"] = bool(param.IsIn)
    except Exception:
        pass
    try:
        entry["is_by_ref"] = bool(param.ParameterType.IsByRef)
    except Exception:
        pass
    return entry


def _reflect_method_overloads(clr_type, method_name, diagnostics):
    """Todas as sobrecargas de `method_name` no tipo CLR dado -- SOMENTE
    metadados (attributes/IsStatic/IsPublic/DeclaringType/ReturnType/
    assembly por metodo, mais a lista de parametros via _reflect_parameter).
    NENHUMA invocacao acontece aqui. Retorna lista de dicts (uma entrada por
    sobrecarga)."""
    overloads = []
    if clr_type is None:
        return overloads

    try:
        raw_methods = clr_type.GetMethods()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_method_overloads",
            "message": "GetMethods() falhou para '%s': %s" % (method_name, compatibility.safe_repr(exc)),
        })
        return overloads

    for method in raw_methods:
        try:
            name = method.Name
        except Exception:
            continue
        if name != method_name:
            continue

        entry = {
            "declaring_type": None, "return_type": None, "is_static": None,
            "is_public": None, "assembly": None, "attributes": [], "parameters": [],
        }
        try:
            entry["declaring_type"] = method.DeclaringType.FullName
        except Exception:
            pass
        try:
            entry["return_type"] = method.ReturnType.FullName
        except Exception:
            pass
        try:
            entry["is_static"] = bool(method.IsStatic)
        except Exception:
            pass
        try:
            entry["is_public"] = bool(method.IsPublic)
        except Exception:
            pass
        try:
            entry["assembly"] = _safe_assembly_full_name(method.DeclaringType)
        except Exception:
            pass
        entry["attributes"] = _reflect_attributes(method)
        try:
            for param in method.GetParameters():
                entry["parameters"].append(_reflect_parameter(param))
        except Exception as exc:
            diagnostics.append({
                "step": "reflect_method_overloads",
                "message": "GetParameters() falhou para uma sobrecarga de '%s': %s"
                          % (method_name, compatibility.safe_repr(exc)),
            })
        overloads.append(entry)

    diagnostics.append({
        "step": "reflect_method_overloads",
        "message": "%d sobrecarga(s) refletida(s) para '%s'." % (len(overloads), method_name),
    })
    return overloads


def _find_parameter_type_by_substring(clr_type, method_name, name_substring, diagnostics):
    """Re-percorre GetMethods()/GetParameters() (SO metadados) procurando um
    ParameterType cujo FullName contenha `name_substring` (case-insensitive)
    entre os parametros de `method_name`. Devolve o objeto System.Type
    (nunca uma instancia) ou None -- usado para IDENTIFICAR um tipo dentro de
    uma assinatura ja obtida por reflexao real, nunca para adivinhar um nome
    novo a sondar."""
    if clr_type is None:
        return None
    try:
        raw_methods = clr_type.GetMethods()
    except Exception as exc:
        diagnostics.append({
            "step": "find_parameter_type",
            "message": "GetMethods() falhou: %s" % compatibility.safe_repr(exc),
        })
        return None

    lowered_target = name_substring.lower()
    for method in raw_methods:
        try:
            if method.Name != method_name:
                continue
        except Exception:
            continue
        try:
            params = method.GetParameters()
        except Exception:
            continue
        for param in params:
            try:
                param_type = param.ParameterType
                full_name = param_type.FullName or ""
            except Exception:
                continue
            if lowered_target in full_name.lower():
                return param_type
    return None


def _reflect_interface_type(clr_type, diagnostics):
    """Caracteriza um tipo candidato a interface (IExportReporter) -- SOMENTE
    metadados (FullName/IsInterface/assembly/GetMembers()). NUNCA
    instanciado. `member_type_value` e o inteiro subjacente de
    System.Reflection.MemberTypes (nunca ToString() sobre o enum)."""
    result = {
        "found": clr_type is not None, "full_name": None, "is_interface": None,
        "assembly": None, "members": [],
    }
    if clr_type is None:
        return result

    try:
        result["full_name"] = clr_type.FullName
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_interface_type",
            "message": "FullName falhou: %s" % compatibility.safe_repr(exc),
        })
    try:
        result["is_interface"] = bool(clr_type.IsInterface)
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_interface_type",
            "message": "IsInterface falhou: %s" % compatibility.safe_repr(exc),
        })
    try:
        result["assembly"] = _safe_assembly_full_name(clr_type)
    except Exception:
        pass
    try:
        raw_members = clr_type.GetMembers()
        members = []
        for member in raw_members:
            entry = {"name": None, "member_type_value": None}
            try:
                entry["name"] = member.Name
            except Exception:
                pass
            try:
                entry["member_type_value"] = int(member.MemberType)
            except Exception:
                pass
            members.append(entry)
        result["members"] = members
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_interface_type",
            "message": "GetMembers() falhou: %s" % compatibility.safe_repr(exc),
        })
    return result


def _reflect_enum_type(clr_type, diagnostics):
    """Caracteriza o enum ConflictResolve -- SOMENTE metadados
    (FullName/IsEnum/assembly/GetEnumNames() com fallback para GetFields()).
    Cada leitura isolada em try/except proprio (contrato: "cada um em
    try/except proprio"). NUNCA instanciado, NUNCA usado para nada alem de
    registro."""
    result = {
        "found": clr_type is not None, "full_name": None, "is_enum": None,
        "assembly": None, "members": [],
    }
    if clr_type is None:
        return result

    try:
        result["full_name"] = clr_type.FullName
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_enum_type",
            "message": "FullName falhou: %s" % compatibility.safe_repr(exc),
        })
    try:
        result["is_enum"] = bool(clr_type.IsEnum)
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_enum_type",
            "message": "IsEnum falhou: %s" % compatibility.safe_repr(exc),
        })
    try:
        result["assembly"] = _safe_assembly_full_name(clr_type)
    except Exception:
        pass

    try:
        names = clr_type.GetEnumNames()
        result["members"] = list(names)
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_enum_type",
            "message": "GetEnumNames() falhou (tentando GetFields()): %s" % compatibility.safe_repr(exc),
        })
        try:
            raw_fields = clr_type.GetFields()
            names = []
            for field in raw_fields:
                try:
                    names.append(field.Name)
                except Exception:
                    continue
            result["members"] = names
        except Exception as exc2:
            diagnostics.append({
                "step": "reflect_enum_type",
                "message": "GetFields() tambem falhou: %s" % compatibility.safe_repr(exc2),
            })
    return result


def _is_primitive_parameter_type(type_name):
    return type_name in PRIMITIVE_PARAMETER_TYPES


def _has_overload_without_type(overloads, type_full_name):
    """True se PELO MENOS UMA sobrecarga NAO tem nenhum parametro cujo tipo
    seja `type_full_name` -- usado para registrar (contrato: "registre se ha
    sobrecarga SEM reporter"), NUNCA para decidir invocacao."""
    if not overloads or not type_full_name:
        return False
    for overload in overloads:
        if all(p.get("type") != type_full_name for p in overload.get("parameters", [])):
            return True
    return False


def _overload_is_safely_invocable(overload):
    """Uma sobrecarga e considerada 'invocavel com seguranca' (contrato S1)
    quando TODOS os seus parametros tem tipo conhecido e primitivo
    (String/Boolean) e NENHUM e out/ref. Um parametro IExportReporter (tipo
    nao-primitivo) automaticamente desqualifica a sobrecarga -- sem precisar
    checar o nome do tipo explicitamente."""
    for param in overload.get("parameters", []):
        if param.get("is_out") or param.get("is_by_ref"):
            return False
        if not _is_primitive_parameter_type(param.get("type")):
            return False
    return True


# =============================================================================
# Classificacao PURA do resultado do probe -- fonte unica de verdade,
# reaplicavel a artefatos ja arquivados sem reimplementacao.
# =============================================================================

def classify_signature_probe_result(export_xml_found, export_xml_overloads):
    """Casos S1/S2/S3 (contrato desta fatia). Devolve
    (result_case, status, verdict_message).

    REGRA CONTRA FALSO SUCESSO: encontrar 'export_xml' e refletir N
    sobrecargas NAO basta para S1 -- e preciso que PELO MENOS UMA sobrecarga
    seja invocavel com seguranca (todos os parametros primitivos, nenhum
    out/ref). Sobrecargas cujo unico parametro nao-primitivo e o
    IExportReporter (ou qualquer outro tipo complexo) NUNCA contam para S1 --
    caem automaticamente em S2 (nenhuma sobrecarga invocavel), sem precisar
    checar o nome do tipo do reporter explicitamente."""
    if not export_xml_found or not export_xml_overloads:
        return ("S3", "inconclusive",
                "caso S3: 'export_xml' NAO encontrado no alvo (reflexao nao localizou nenhuma "
                "sobrecarga). Nenhuma conclusao sobre a assinatura de exportacao e permitida; "
                "invocacao permanece nao autorizada.")

    invocable_overloads = [ov for ov in export_xml_overloads if _overload_is_safely_invocable(ov)]

    if not invocable_overloads:
        return ("S2", "inconclusive",
                "caso S2: 'export_xml' encontrado com %d sobrecarga(s) refletida(s), mas NENHUMA "
                "e invocavel com seguranca -- toda sobrecarga exige um parametro nao-primitivo "
                "(tipicamente IExportReporter) ou contem parametro out/ref. Invocacao ainda NAO "
                "autorizada." % len(export_xml_overloads))

    return ("S1", "ok",
            "caso S1: 'export_xml' encontrado com %d sobrecarga(s) refletida(s), das quais %d "
            "sao invocaveis com seguranca (todos os parametros primitivos String/Boolean, "
            "nenhum out/ref, sem exigir IExportReporter). Abre espaco para a proxima fatia "
            "(exportacao controlada, com autorizacao humana e destino descartavel)."
            % (len(export_xml_overloads), len(invocable_overloads)))


# =============================================================================
# Orquestracao + escrita de artefatos.
# =============================================================================

def _build_export_scope(pou_overloads, application, diagnostics,
                        inspect_active_application=True):
    """Registra em que niveis 'export_xml' foi encontrado por reflexao e
    devolve (levels, application_overloads).

    As sobrecargas da Application sao devolvidas SEPARADAS das do POU e
    nunca fundidas: a pergunta que decide a primeira exportacao e se cada
    escopo tem, por si, uma sobrecarga invocavel. Uma lista unica esconderia
    de qual escopo veio a sobrecarga segura.

    `inspect_active_application=False` PULA o escopo e registra
    `attempted=False` com razao explicita -- nunca `found=False`, que
    significaria "procurei e nao achei". Confundir "nao procurei" com "nao
    existe" e o mesmo erro que ja custou duas reclassificacoes nesta trilha.
    """
    pou_declaring_types = sorted(set(
        ov["declaring_type"] for ov in pou_overloads if ov.get("declaring_type")))
    levels = [{
        "level": "pou",
        "found": len(pou_overloads) > 0,
        "overload_count": len(pou_overloads),
        "declaring_types": pou_declaring_types,
        "attempted": True,
        "reason": None,
    }]

    app_overloads = []
    if not inspect_active_application:
        diagnostics.append({
            "step": "export_scope_application",
            "message": "escopo Application NAO inspecionado por configuracao "
                      "(inspect_active_application=False).",
        })
        levels.append({
            "level": "application", "found": None, "overload_count": None,
            "declaring_types": [], "attempted": False,
            "reason": "inspect_active_application=False -- escopo nao inspecionado; "
                     "isto NAO significa ausencia de export_xml na Application.",
        })
    else:
        try:
            app_clr_type = application.GetType()
        except Exception as exc:
            diagnostics.append({
                "step": "export_scope_application",
                "message": "GetType() da Application falhou: %s" % compatibility.safe_repr(exc),
            })
            levels.append({
                "level": "application", "found": False, "overload_count": 0,
                "declaring_types": [], "attempted": True,
                "reason": "GetType() da Application falhou: %s" % compatibility.safe_repr(exc),
            })
        else:
            app_overloads = _reflect_method_overloads(
                app_clr_type, EXPORT_XML_METHOD_NAME, diagnostics)
            app_declaring_types = sorted(set(
                ov["declaring_type"] for ov in app_overloads if ov.get("declaring_type")))
            levels.append({
                "level": "application",
                "found": len(app_overloads) > 0,
                "overload_count": len(app_overloads),
                "declaring_types": app_declaring_types,
                "attempted": True,
                "reason": None,
            })

    levels.append({
        "level": "project",
        "found": None,
        "overload_count": 0,
        "declaring_types": [],
        "attempted": False,
        "reason": "objeto de projeto nao alcancavel nesta assinatura de entrada (esta funcao "
                 "recebe apenas 'application' e o proxy-alvo POU, nao o objeto de projeto) -- "
                 "registrado honestamente como nao tentado, nao como ausente.",
    })

    return levels, app_overloads



def _build_report_markdown(result, target_identity, export_overloads, import_overloads,
                           export_scope, export_reporter_type, conflict_resolve_enum):
    lines = [
        "# Sondagem da assinatura completa de export_xml -- probe_plcopen_xml_export_signature",
        "",
        "Fase L1 (docs/14-ladder-roadmap.md), IRMAO dos probes 16/17/18. Modo: "
        "**somente leitura estrita**. Nenhuma invocacao de export_xml/import_xml/"
        "export_native/import_native ou qualquer outro metodo; nenhuma instanciacao de tipo; "
        "nenhuma leitura de `.text`.",
        "",
        "- target_node_id: `%s`" % result.get("target_node_id"),
        "- abortado: **%s**" % result.get("aborted"),
        "- motivo do aborto: %s" % result.get("abort_reason"),
        "- identidade do alvo confirmada: **%s**" % result.get("target_identity_confirmed"),
        "- resultado (S1-S3): **%s**" % result.get("result_case"),
        "- status: **%s**" % result.get("status"),
        "- export_xml_found: **%s**" % result.get("export_xml_found"),
        "- export_xml_overload_count: **%s**" % result.get("export_xml_overload_count"),
        "- import_xml_overload_count: **%s**" % result.get("import_xml_overload_count"),
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

    result_case = result.get("result_case")
    if result_case == "S3":
        lines.append("## ATENCAO -- 'export_xml' NAO encontrado (caso S3)")
        lines.append("")
        lines.append(
            "Nenhuma sobrecarga de 'export_xml' foi localizada por reflexao no proxy-alvo. "
            "Nenhuma conclusao sobre a assinatura de exportacao e permitida.")
        lines.append("")
    elif result_case == "S2":
        lines.append("## ATENCAO -- nenhuma sobrecarga invocavel com seguranca (caso S2)")
        lines.append("")
        lines.append(
            "'export_xml' foi encontrado, mas TODA sobrecarga refletida exige um parametro "
            "nao-primitivo (tipicamente IExportReporter) ou contem parametro out/ref. A "
            "invocacao permanece NAO AUTORIZADA -- refletir 4 sobrecargas NAO basta para "
            "concluir seguranca de invocacao.")
        lines.append("")
    elif result_case == "S1":
        lines.append("## Conclusao (caso S1) -- sobrecarga invocavel identificada")
        lines.append("")
        lines.append(
            "Pelo menos uma sobrecarga de 'export_xml' tem todos os parametros primitivos "
            "(String/Boolean), sem parametro out/ref e sem exigir IExportReporter. Abre "
            "espaco para a proxima fatia (exportacao controlada), sujeita a autorizacao "
            "humana explicita e destino descartavel.")
        lines.append("")

    lines.append("## Sobrecargas de export_xml (%d)" % len(export_overloads))
    for overload in export_overloads:
        param_summary = ", ".join(
            "%s: %s" % (p.get("name"), p.get("type")) for p in overload.get("parameters", []))
        lines.append("- declaring_type=`%s` params=(%s)" % (overload.get("declaring_type"), param_summary))
    lines.append("")

    lines.append("## Sobrecargas de import_xml (%d)" % len(import_overloads))
    for overload in import_overloads:
        param_summary = ", ".join(
            "%s: %s" % (p.get("name"), p.get("type")) for p in overload.get("parameters", []))
        lines.append("- declaring_type=`%s` params=(%s)" % (overload.get("declaring_type"), param_summary))
    lines.append("")

    lines.append("## Escopo de export_xml")
    for level in export_scope:
        lines.append(
            "- nivel=`%s` found=%s overload_count=%s tentado=%s motivo=%s"
            % (level.get("level"), level.get("found"), level.get("overload_count"),
               level.get("attempted"), level.get("reason")))
    lines.append("")

    lines.append("## IExportReporter")
    lines.append("- encontrado: **%s**" % export_reporter_type.get("found"))
    lines.append("- full_name: `%s`" % export_reporter_type.get("full_name"))
    lines.append("- is_interface: **%s**" % export_reporter_type.get("is_interface"))
    lines.append("- membros refletidos: %d" % len(export_reporter_type.get("members", [])))
    lines.append("")

    lines.append("## Enum ConflictResolve (_3S.CoDeSys.PLCopenXML.ConflictResolve)")
    lines.append("- encontrado: **%s**" % conflict_resolve_enum.get("found"))
    lines.append("- full_name: `%s`" % conflict_resolve_enum.get("full_name"))
    lines.append("- membros: %s" % conflict_resolve_enum.get("members"))
    lines.append("")

    return "\n".join(lines) + "\n"


def _write_artifacts(output_dir, result, diagnostics, target_identity, export_overloads,
                     import_overloads, export_scope, export_reporter_type, conflict_resolve_enum,
                     application_overloads=None):
    file_io.ensure_dir(output_dir)

    manifest = {
        "schema_version": "1.0",
        "script": "probes/19_probe_plcopen_xml_export_signature.py",
        "target_object_result_case": result.get("target_object_result_case"),
        "active_application_result_case": result.get("active_application_result_case"),
        "active_application_overload_count": result.get("active_application_overload_count"),
        "generated_at": result["generated_at"],
        "mode": "read_only",
        "target_node_id": result["target_node_id"],
        "aborted": result["aborted"],
        "abort_reason": result["abort_reason"],
        "target_identity_confirmed": result["target_identity_confirmed"],
        "export_xml_found": result["export_xml_found"],
        "export_xml_overload_count": result["export_xml_overload_count"],
        "import_xml_overload_count": result["import_xml_overload_count"],
        "result_case": result["result_case"],
        "status": result["status"],
    }
    file_io.write_json(os.path.join(output_dir, "manifest.json"), manifest)
    file_io.write_json(os.path.join(output_dir, "target-identity.json"),
                       target_identity if target_identity is not None else {})
    file_io.write_json(os.path.join(output_dir, "export-xml-overloads.json"), {
        "method_name": EXPORT_XML_METHOD_NAME,
        "forbidden_term": _forbidden_term_in(EXPORT_XML_METHOD_NAME),
        "invoked": False,
        "overload_count": len(export_overloads),
        "overloads": export_overloads,
    })
    # Escopo Application em arquivo PROPRIO -- nunca fundido com o do POU.
    # Quem decidir a primeira exportacao precisa ver, por escopo, se existe
    # sobrecarga invocavel; uma lista unica esconderia a origem.
    file_io.write_json(os.path.join(output_dir, "active-application-overloads.json"), {
        "method_name": EXPORT_XML_METHOD_NAME,
        "scope": "active_application",
        "forbidden_term": _forbidden_term_in(EXPORT_XML_METHOD_NAME),
        "invoked": False,
        "inspected": bool(result.get("active_application_inspected")),
        "overload_count": len(application_overloads or []),
        "overloads": list(application_overloads or []),
        "result_case": result.get("active_application_result_case"),
    })
    file_io.write_json(os.path.join(output_dir, "import-xml-overloads.json"), {
        "method_name": IMPORT_XML_METHOD_NAME,
        "forbidden_term": _forbidden_term_in(IMPORT_XML_METHOD_NAME),
        "invoked": False,
        "overload_count": len(import_overloads),
        "overloads": import_overloads,
    })
    file_io.write_json(os.path.join(output_dir, "export-scope.json"), export_scope)
    file_io.write_json(os.path.join(output_dir, "export-reporter-type.json"), export_reporter_type)
    file_io.write_json(os.path.join(output_dir, "conflict-resolve-enum.json"), conflict_resolve_enum)

    md = _build_report_markdown(
        result, target_identity, export_overloads, import_overloads, export_scope,
        export_reporter_type, conflict_resolve_enum)
    # Os quatro artefatos comuns (diagnostics, safety-declaration, report,
    # checksums) saem por `common.artifacts`, na ordem contratual e com
    # checksums por ultimo. O que e especifico deste probe continua acima.
    artifacts.write_common_artifacts(
        output_dir, diagnostics, dict(SAFETY_DECLARATION), md)

    result["artifacts_dir"] = output_dir
    return result


def _empty_write(output_dir, result, diagnostics):
    empty_reporter = {"found": False, "full_name": None, "is_interface": None,
                      "assembly": None, "members": []}
    empty_enum = {"found": False, "full_name": None, "is_enum": None,
                 "assembly": None, "members": []}
    return _write_artifacts(
        output_dir, result, diagnostics, None, [], [], [], empty_reporter, empty_enum)


def probe_plcopen_export_signature(application, ladder_probe_config, output_dir,
                                   inspect_active_application=True):
    """Ponto de entrada publico. `application` ja deve estar resolvida pelo
    chamador (mesmo padrao de common/), e e reutilizada DIRETAMENTE (sem
    navegacao adicional) para checar o escopo 'application' de export_xml.
    `ladder_probe_config` e o mesmo formato de dict usado pelos probes
    16/17/18 (4 chaves obrigatorias). `output_dir` e o diretorio onde os
    artefatos desta sondagem sao gravados diretamente.

    ESTE PROBE NAO INVOCA export_xml/import_xml/export_native/import_native
    nem qualquer outro metodo do proxy-alvo -- so reflexao de metadados.

    Nunca lanca excecao: qualquer falha de navegacao/identidade/reflexao e
    capturada e reportada via diagnostics.json + result['abort_reason'].
    Sempre grava os artefatos obrigatorios (mesmo em caso de aborto)."""
    diagnostics = []
    result = {
        "schema_version": "1.0",
        "generated_at": file_io.iso_now(),
        "aborted": False,
        "abort_reason": None,
        "target_node_id": None,
        "target_identity_confirmed": False,
        "export_xml_found": False,
        "export_xml_overload_count": 0,
        "import_xml_overload_count": 0,
        "result_case": "S3",
        "status": "inconclusive",
    }

    # Passo 0: mesma defesa em profundidade dos probes 16/17/18 -- este
    # probe NAO confia cegamente no formato de ladder_probe_config.
    required_fields = ("target_node_id", "expected_name", "expected_guid", "expected_type_guid")
    if not isinstance(ladder_probe_config, dict):
        result["aborted"] = True
        result["abort_reason"] = "ladder_probe_config_invalid"
        result["status"] = "failed"
        diagnostics.append({"step": "config_validation",
                            "message": "ladder_probe_config nao e um dict."})
        return _empty_write(output_dir, result, diagnostics)
    for field in required_fields:
        value = ladder_probe_config.get(field)
        if not isinstance(value, _STRING_TYPES) or not value:
            result["aborted"] = True
            result["abort_reason"] = "ladder_probe_config_invalid"
            result["status"] = "failed"
            diagnostics.append({"step": "config_validation",
                                "message": "campo ausente/vazio em ladder_probe_config: %s" % field})
            return _empty_write(output_dir, result, diagnostics)

    target_node_id = ladder_probe_config["target_node_id"]
    result["target_node_id"] = target_node_id

    # Passo 1: localizar target_node_id.
    indices = _parse_node_path(target_node_id)
    if indices is None:
        result["aborted"] = True
        result["abort_reason"] = "invalid_target_node_id"
        result["status"] = "failed"
        diagnostics.append({"step": "parse_node_path",
                            "message": "target_node_id malformado: %r" % (target_node_id,)})
        return _empty_write(output_dir, result, diagnostics)

    proxy, reached_node_id, nav_error = _navigate_to_target(application, indices, diagnostics)
    if proxy is None:
        result["aborted"] = True
        result["abort_reason"] = "navigation_failed"
        result["status"] = "failed"
        diagnostics.append({"step": "navigation",
                            "message": "falha ao navegar ate '%s': %s" % (target_node_id, nav_error)})
        return _empty_write(output_dir, result, diagnostics)

    # Passos 2-5: conferir expected_name -> expected_guid -> expected_type_guid
    # -> is_folder == false. SO ENTAO refletir a assinatura.
    identity = _probe_target_identity(proxy, "plcopen_signature_target")
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
        result["status"] = "failed"
        diagnostics.append({
            "step": "identity_check",
            "message": "divergencia(s) de identidade -- abortando SEM refletir assinatura: %s"
                      % mismatches,
        })
        empty_reporter = {"found": False, "full_name": None, "is_interface": None,
                          "assembly": None, "members": []}
        empty_enum = {"found": False, "full_name": None, "is_enum": None,
                     "assembly": None, "members": []}
        return _write_artifacts(
            output_dir, result, diagnostics, target_identity_doc, [], [], [],
            empty_reporter, empty_enum)

    result["target_identity_confirmed"] = True
    diagnostics.append({
        "step": "identity_check",
        "message": "identidade confirmada (name/object_guid/type_guid/is_folder) -- prosseguindo.",
    })

    # A partir daqui: reflexao pura da assinatura -- export_xml -> import_xml
    # -> escopo -> IExportReporter -> ConflictResolve -> classificacao
    # (ordem fixa do contrato desta fatia). NENHUMA invocacao de metodo do
    # proxy-alvo acontece a partir deste ponto.
    try:
        pou_clr_type = proxy.GetType()
    except Exception as exc:
        pou_clr_type = None
        diagnostics.append({
            "step": "reflect", "message": "GetType() do proxy-alvo falhou apos identidade "
                                          "confirmada: %s" % compatibility.safe_repr(exc),
        })

    export_overloads = _reflect_method_overloads(pou_clr_type, EXPORT_XML_METHOD_NAME, diagnostics)
    import_overloads = _reflect_method_overloads(pou_clr_type, IMPORT_XML_METHOD_NAME, diagnostics)

    export_scope, application_overloads = _build_export_scope(
        export_overloads, application, diagnostics, inspect_active_application)

    reporter_type_ref = _find_parameter_type_by_substring(
        pou_clr_type, EXPORT_XML_METHOD_NAME, EXPORT_REPORTER_TYPE_SUBSTRING, diagnostics)
    export_reporter_type = _reflect_interface_type(reporter_type_ref, diagnostics)
    export_reporter_type["has_overload_without_reporter"] = _has_overload_without_type(
        export_overloads, export_reporter_type.get("full_name"))

    conflict_resolve_type_ref = _find_parameter_type_by_substring(
        pou_clr_type, IMPORT_XML_METHOD_NAME, CONFLICT_RESOLVE_TYPE_SUBSTRING, diagnostics)
    conflict_resolve_enum = _reflect_enum_type(conflict_resolve_type_ref, diagnostics)

    result["export_xml_found"] = len(export_overloads) > 0
    result["export_xml_overload_count"] = len(export_overloads)
    result["import_xml_overload_count"] = len(import_overloads)

    result_case, status, verdict_message = classify_signature_probe_result(
        result["export_xml_found"], export_overloads)
    result["result_case"] = result_case
    result["status"] = status
    diagnostics.append({"step": "verdict", "message": verdict_message})

    # Classificacao SEPARADA por escopo. Um S1 no POU nao promove a
    # Application, e vice-versa: a matriz de decisao da primeira exportacao
    # depende de saber, para CADA escopo, se ele tem por si uma sobrecarga
    # invocavel. Fundir os dois esconderia de onde veio a sobrecarga segura.
    result["target_object_result_case"] = result_case
    # Guardado EXPLICITAMENTE: derivar de `application_overloads is not None`
    # daria True para a lista vazia devolvida quando o escopo e pulado -- o
    # mesmo "nao procurei virou procurei" que este probe existe para evitar.
    result["active_application_inspected"] = bool(inspect_active_application)
    if inspect_active_application:
        app_case, app_status, app_verdict = classify_signature_probe_result(
            len(application_overloads) > 0, application_overloads)
        result["active_application_result_case"] = app_case
        result["active_application_overload_count"] = len(application_overloads)
        diagnostics.append({
            "step": "verdict_application",
            "message": "escopo Application -- %s" % app_verdict,
        })
    else:
        result["active_application_result_case"] = None
        result["active_application_overload_count"] = None

    return _write_artifacts(
        output_dir, result, diagnostics, target_identity_doc, export_overloads, import_overloads,
        export_scope, export_reporter_type, conflict_resolve_enum, application_overloads)


# =============================================================================
# Execucao standalone (--runscript), mesmo padrao dos probes 16/17/18.
# =============================================================================

def main():
    print("=" * 60)
    print("[INFO] probes/19_probe_plcopen_xml_export_signature.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA ESTRITA. Fase L1 -- reflexao da assinatura")
    print("[INFO] completa de export_xml/import_xml no objeto POU-alvo. NENHUMA")
    print("[INFO] invocacao de export_xml/import_xml/export_native/import_native.")

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

    run_dir = file_io.new_export_dir(EXPORT_ROOT, "19_probe_plcopen_xml_export_signature")
    result = probe_plcopen_export_signature(application, ladder_probe_config, run_dir)

    if result["aborted"]:
        print("[BLOQUEADO] abort_reason=%s" % result["abort_reason"])
    else:
        print("[OK] identidade confirmada; result_case=%s status=%s "
             "export_xml_overload_count=%s"
             % (result["result_case"], result["status"], result["export_xml_overload_count"]))
    print("[OK] Artefatos gravados em: %s" % run_dir)
    print("=" * 60)


main()

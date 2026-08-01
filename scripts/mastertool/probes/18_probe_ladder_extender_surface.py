# -*- coding: utf-8 -*-
"""18_probe_ladder_extender_surface.py -- Fase L1 (docs/14-ladder-roadmap.md:
"Descoberta da representacao Ladder"), IRMAO de
probes/17_probe_ladder_dynamic_surface.py -- mesma identidade de alvo, mesmo
modo somente leitura, mesma filosofia de whitelist explicita.

Motivacao (o "porque"): probe 16 (reflexao CLR pura sobre o proxy-alvo) NUNCA
viu 'textual_declaration'. Probe 17 (dir() + hasattr() controlado)
confirmou que o ACESSO POR NOME funciona (hasattr() achou o controle), mas a
ENUMERACAO via dir() voltou VAZIA -- caso D: nenhuma conclusao sobre
existencia/ausencia de uma API Ladder foi possivel, porque zero candidatos
vindos de zero nomes enumerados nao mede ausencia, mede ausencia de
enumeracao. Este probe (18) persegue uma pista concreta, ja visivel na
propria reflexao do probe 16: entre os 29 membros refletidos pelo tipo CLR
do proxy-alvo esta 'Extender' -- consistente com o objeto ser um
`ExtendedObject[IScriptObject]` que implementa `IExtendedObject` (achado
registrado em docs/api/mastertool-api-observations.md). Se 'Extender' expoe
um canal ESTRUTURAL de enumeracao (tipicamente `ICustomTypeDescriptor`,
usado pelo DLR/WinForms para descrever propriedades adicionadas em runtime),
esse canal pode ser a explicacao concreta de COMO 'textual_declaration'
chega ao proxy sem aparecer na reflexao CLR estatica nem no dir() do proxy.

CRITERIO DE VALIDADE (o coracao deste probe, nao negociavel): validar o
canal Extender exige REENCONTRAR 'textual_declaration' por um caminho
ESTRUTURAL que passe pelo Extender -- proxy -> Extender -> provider ->
PropertyDescriptor de nome 'textual_declaration'. NAO basta acessar
'Extender', nem refletir dezenas de membros nele, nem repetir
hasattr(proxy, "textual_declaration") (isso o probe 17 ja fez -- nao prova
nada sobre o Extender). Sem essa cadeia estrutural comprovada, o probe e
INCONCLUSIVO, mesmo que 'Extender' seja acessivel e rico em membros --
"Extender acessivel + 40 membros refletidos + controle NAO localizado" e
SEMPRE caso E3 (canal nao validado), NUNCA sucesso.

Sequencia obrigatoria de execucao desta fatia (ordem fixa, sem excecao):

    confirmar identidade do alvo (4 campos, contrato secao 3.1)
    -> refletir literalmente o membro 'Extender' no tipo CLR do proxy-alvo
       (declaring type, member kind, return type, getter, parametros,
       assembly) -- NUNCA invocado por hipotese
    -> invocar 'Extender' SOMENTE se a reflexao autorizar (getter
       confirmado, sem parametros, sem termo proibido no nome)
    -> inspecionar o OBJETO retornado com GetType()/AssemblyQualifiedName/
       GetInterfaces()/GetProperties()/GetMethods()/GetFields()/GetEvents()
       -- cada operacao isolada em try/except proprio, SOMENTE metadados
    -> classificar os tipos encontrados por termos (nunca invocar por causa
       da classificacao)
    -> SE E SOMENTE SE `ICustomTypeDescriptor` for confirmado literalmente
       nas interfaces do Extender, chamar extender.GetProperties() (unico
       metodo do Extender chamado nesta fase, alem do proprio getter
       'Extender') e enumerar a colecao resultante de forma bounded (Count +
       indexador nativo, limite maximo, falha isolada por item, deteccao de
       duplicidade -- so DEPOIS de confirmar que a colecao implementa uma
       interface de colecao CONHECIDA: IList/IReadOnlyList/ICollection/
       Array)
    -> para cada item (um PropertyDescriptor), ler SOMENTE Name/
       PropertyType/ComponentType/IsReadOnly -- NUNCA GetValue()/
       SetValue()/ResetValue()/AddValueChanged()/RemoveValueChanged()
    -> classificar cada nome encontrado (controle conhecido / candidato
       Ladder / nao classificado), preservando o padrao 'forbidden_term' do
       probe 17
    -> montar a cadeia de descoberta (known-control-discovery.json) SE o
       controle foi reencontrado; caso contrario, registrar o motivo

PROIBIDO nesta fase (defesa em profundidade -- guarda ANTES de qualquer
invocacao, nao so ausencia de chamada no codigo): export_xml e qualquer
exportacao; leitura de '.text'; setters; PropertyDescriptor.GetValue()/
SetValue()/ResetValue()/AddValueChanged()/RemoveValueChanged();
GetMetaObject() (so registramos presenca/assinatura, NUNCA chamamos --
exige um argumento `Expression` que este probe nao tem motivo de construir);
CanExtend() (so registramos presenca/assinatura, NUNCA chamamos -- exige um
argumento de extensao); qualquer metodo dinamico descoberto durante esta
propria execucao; escrita no projeto; build; save; online; download; force;
criacao/remocao de objetos; serializacao de proxies via
str()/repr()/ToString() (toda representacao passa por
common/capabilities.build_representation ou por nomes de tipo ja obtidos via
GetType().FullName, nunca por formatacao implicita da instancia).

Mesma identidade de alvo do probe 16/17 (contrato, secao 3.1): os 4 campos
'expected_*' (nome, object_guid, type_guid) mais is_folder==False, checados
NA MESMA ORDEM, ANTES de qualquer sondagem de Extender. Qualquer divergencia
aborta com 'target_identity_mismatch'.

Integracao com o runner supervisionado: esta fatia NAO altera
automation/supervised_snapshot_runner.py nem run_config.py -- nenhuma nova
operacao foi registrada no contrato nesta fatia (fora de escopo). Este
arquivo roda standalone via --runscript, mesmo padrao dos probes 16/17, com
um alvo padrao hardcoded SO para essa execucao avulsa (NUNCA usado por um
eventual runner futuro, que sempre receberia ladder_probe_config vindo de
run-config.json).

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

# --- bootstrap: tornar 'common' importavel quando executado standalone
# (--runscript). Copia identica do bloco equivalente em
# probes/17_probe_ladder_dynamic_surface.py -- mesmo racional la documentado.
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

# --- termos de classificacao de CANDIDATOS LADDER (copia LITERAL de
# probes/17_probe_ladder_dynamic_surface.py, que copiou do probe 16) -- usados
# SO para classificar um nome de PropertyDescriptor ja enumerado pelo canal
# Extender, nunca para inventar um nome a sondar.
EVIDENCE_TERMS = (
    "network", "ladder", "implementation", "graphical", "element",
    "connector", "connection", "pin", "export", "xml", "plcopen", "serialize",
)

# Copia LITERAL de probes/17_probe_ladder_dynamic_surface.py. Qualquer membro
# cujo NOME contenha um destes termos NUNCA e invocado, mesmo que apareca em
# alguma whitelist por engano futuro (defesa em profundidade).
FORBIDDEN_GETTER_NAME_TERMS = (
    "write", "modify", "alter", "import", "execute", "invoke", "run",
    "save", "export", "delete", "remove", "create", "build", "compile",
    "download", "force", "close", "clear", "reset", "apply", "replace",
    "generate", "destroy", "dispose", "set_",
)

# Termos de classificacao ESTRUTURAL (contrato desta fatia, secao "Escopo
# autorizado", item 3) -- usados para anotar interfaces/propriedades/metodos
# do Extender com uma categoria legivel, NUNCA para decidir invocacao (a
# decisao de invocar segue apenas os portoes explicitos: reflexao +
# whitelist de interface conhecida + ausencia de termo proibido).
CLASSIFICATION_TERMS = (
    "iextender", "extension", "extended", "provider", "dynamic", "member",
    "property", "descriptor", "script", "object", "ladder", "network",
    "graphical", "implementation", "editor", "plcopen",
)

# Interfaces de colecao CONHECIDAS (contrato, item 4) -- so se uma delas
# aparecer literalmente em GetInterfaces() da colecao retornada por
# ICustomTypeDescriptor.GetProperties() e que a enumeracao bounded (Count +
# indexador) e autorizada. Comparacao por substring, minusculas.
KNOWN_COLLECTION_INTERFACE_TERMS = ("ilist", "ireadonlylist", "icollection", "array")

# Termos de interface usados para decidir os TRES canais de extensao
# descritos no contrato (itens 5/6/7) -- comparacao por substring, minusculas,
# sobre o FullName da interface.
CUSTOM_TYPE_DESCRIPTOR_TERM = "icustomtypedescriptor"
DYNAMIC_META_OBJECT_PROVIDER_TERM = "idynamicmetaobjectprovider"
EXTENDER_PROVIDER_TERM = "iextenderprovider"

# Nome literal do membro refletido no proxy-alvo (contrato: "o membro CLR
# 'Extender'").
EXTENDER_MEMBER_NAME = "Extender"

# Limite maximo de itens enumerados da colecao de PropertyDescriptor
# (contrato, item 4: "usar limite maximo de itens"). Nao ha guia numerico no
# contrato -- 200 e o mesmo limite de exibicao ja usado nos relatorios dos
# probes 16/17, reaproveitado aqui como teto de ENUMERACAO (nao so exibicao),
# suficiente para qualquer conjunto razoavel de propriedades de um objeto de
# script e uma defesa contra uma colecao anomalamente grande.
MAX_EXTENSION_ITEMS = 200

# O membro de controle usado como criterio de validade do probe inteiro
# (mesmo controle usado pelos probes 16/17 -- contrato desta fatia: "o
# coracao do probe").
CONTROL_MEMBER = "textual_declaration"

# safety-declaration.json -- EXATAMENTE estas 10 chaves, todas False. Copia
# literal do mesmo dicionario dos probes 16/17: nenhum caminho de codigo
# desta fatia chama export()/import/save/build/download/force, nem le
# '.text' de implementacao/declaracao, nem GetValue()/SetValue()/
# GetMetaObject()/CanExtend().
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
# ao default dos probes 16/17 (mesmo alvo, mesma evidencia de escolha).
# NUNCA usado por um eventual runner supervisionado -- este e so o modo
# standalone avulso.
DEFAULT_TARGET_NODE_ID = "application/9/4"
DEFAULT_EXPECTED_NAME = "FB_PISCA_EXEMPLO"
DEFAULT_EXPECTED_GUID = "00000000-0000-0000-0000-000000000002"
DEFAULT_EXPECTED_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"


# =============================================================================
# Navegacao bounded/indexada -- copia local deliberada do mesmo padrao
# aprovado em probes/16_probe_ladder_object_surface.py e
# probes/17_probe_ladder_dynamic_surface.py (mesma filosofia de independencia
# por modulo). get_children(False) + Count + indexador nativo -- NUNCA
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
    formato -> None (invalido). Copia identica dos probes 16/17."""
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
    probes 16/17."""
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
# Identidade -- copia local deliberada, identica aos probes 16/17 (mesmo
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
# Classificacao por termos -- puro, sem I/O. Usado tanto para candidatos
# Ladder (EVIDENCE_TERMS, mesma semantica dos probes 16/17) quanto para
# anotar interfaces/propriedades/metodos do Extender (CLASSIFICATION_TERMS,
# contrato item 3) -- NUNCA decide invocacao sozinho.
# =============================================================================

def _has_evidence_term(name):
    lowered = (name or "").lower()
    return any(term in lowered for term in EVIDENCE_TERMS)


def _forbidden_term_in(name):
    """Devolve o termo proibido que o nome contem, ou None. Usado para
    ANOTAR o registro do membro -- a guarda de invocacao propriamente dita e
    aplicada separadamente, antes de qualquer chamada."""
    lowered = (name or "").lower()
    for term in FORBIDDEN_GETTER_NAME_TERMS:
        if term in lowered:
            return term
    return None


def _classify_by_terms(name):
    """Classificacao ESTRUTURAL (contrato item 3): termos batidos no nome,
    em ordem alfabetica. Lista vazia se nenhum termo bateu. NUNCA usada para
    decidir invocacao."""
    lowered = (name or "").lower()
    return sorted(term for term in CLASSIFICATION_TERMS if term in lowered)


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


# =============================================================================
# Passo 1 do escopo autorizado: reflexao literal do membro 'Extender' no tipo
# CLR do proxy-alvo -- NENHUMA invocacao acontece aqui, so metadados.
# =============================================================================

def _reflect_extender_member(proxy, diagnostics):
    """Reflete literalmente o membro 'Extender' no tipo CLR do proxy-alvo.
    Retorna um dict com os metadados exigidos pelo escopo (declaring type,
    member kind, return type, getter, parametros, assembly) mais o veredito
    'invocation_authorized', que so e True se TODOS os criterios de
    seguranca baterem: encontrado, e propriedade, tem getter (CanRead),
    sem parametros (nao e indexador), sem termo proibido no nome."""
    result = {
        "found": False,
        "member_kind": None,
        "declaring_type": None,
        "return_type": None,
        "can_read": None,
        "has_index_parameters": None,
        "assembly": None,
        "forbidden_term": _forbidden_term_in(EXTENDER_MEMBER_NAME),
        "invocation_authorized": False,
    }

    try:
        clr_type = proxy.GetType()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_extender_member",
            "message": "GetType() do proxy-alvo falhou: %s" % compatibility.safe_repr(exc),
        })
        return result

    try:
        raw_properties = clr_type.GetProperties()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_extender_member",
            "message": "GetProperties() do proxy-alvo falhou: %s" % compatibility.safe_repr(exc),
        })
        return result

    for prop in raw_properties:
        try:
            name = prop.Name
        except Exception:
            continue
        if name != EXTENDER_MEMBER_NAME:
            continue

        result["found"] = True
        result["member_kind"] = "property"
        try:
            result["declaring_type"] = prop.DeclaringType.FullName
        except Exception:
            result["declaring_type"] = None
        try:
            result["return_type"] = prop.PropertyType.FullName
        except Exception:
            result["return_type"] = None
        try:
            result["can_read"] = bool(prop.CanRead)
        except Exception:
            result["can_read"] = None
        try:
            result["has_index_parameters"] = len(prop.GetIndexParameters()) > 0
        except Exception:
            result["has_index_parameters"] = None
        try:
            result["assembly"] = _safe_assembly_full_name(prop.PropertyType)
        except Exception:
            result["assembly"] = None
        break

    result["invocation_authorized"] = bool(
        result["found"]
        and result["member_kind"] == "property"
        and result["can_read"] is True
        and result["has_index_parameters"] is False
        and result["forbidden_term"] is None)

    diagnostics.append({
        "step": "reflect_extender_member",
        "message": "found=%s can_read=%s has_index_parameters=%s invocation_authorized=%s"
                  % (result["found"], result["can_read"], result["has_index_parameters"],
                     result["invocation_authorized"]),
    })
    return result


def _invoke_extender(proxy, extender_member, diagnostics):
    """Invoca o getter 'Extender' SOMENTE se a reflexao autorizou. Nunca
    invoca por hipotese -- a guarda e checada ANTES desta chamada, nao so
    pela ausencia de outra chamada no codigo. Retorna (state, extender_obj)."""
    if not extender_member["invocation_authorized"]:
        diagnostics.append({
            "step": "invoke_extender",
            "message": "invocacao NAO autorizada pela reflexao -- 'Extender' nao invocado.",
        })
        return "not_authorized", None

    record = capabilities.probe_member(
        proxy, "ladder_target", EXTENDER_MEMBER_NAME, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    diagnostics.append({
        "step": "invoke_extender", "message": "state=%s" % record["state"],
    })
    if record["state"] != "confirmed" or "raw_value" not in record:
        return record["state"], None
    return "confirmed", record["raw_value"]


# =============================================================================
# Passo 2 do escopo autorizado: inspecionar o OBJETO Extender retornado --
# SOMENTE metadados (GetType/AssemblyQualifiedName/GetInterfaces/
# GetProperties/GetMethods/GetFields/GetEvents), cada operacao isolada em
# try/except proprio.
# =============================================================================

def _reflect_extender_runtime_type(extender_obj, diagnostics):
    """GetType()/AssemblyQualifiedName/Assembly/GetFields()/GetEvents() do
    objeto Extender -- cada leitura isolada, falha de uma nao impede as
    demais. Retorna (runtime_type_dict, clr_type_ou_None) -- o segundo e
    reaproveitado pelo chamador para refletir interfaces/properties/methods
    sem repetir GetType()."""
    result = {
        "full_name": None,
        "assembly_qualified_name": None,
        "assembly": None,
        "interfaces_count": None,
        "properties_count": None,
        "methods_count": None,
        "fields_count": None,
        "field_names": [],
        "events_count": None,
        "event_names": [],
        "implements_icustomtypedescriptor": False,
        "implements_idynamicmetaobjectprovider": False,
        "implements_iextenderprovider": False,
        "has_get_meta_object_method": False,
        "has_can_extend_method": False,
    }

    try:
        clr_type = extender_obj.GetType()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_extender_runtime_type",
            "message": "GetType() do Extender falhou: %s" % compatibility.safe_repr(exc),
        })
        return result, None

    try:
        result["full_name"] = clr_type.FullName
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_extender_runtime_type",
            "message": "FullName falhou: %s" % compatibility.safe_repr(exc),
        })

    try:
        result["assembly_qualified_name"] = clr_type.AssemblyQualifiedName
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_extender_runtime_type",
            "message": "AssemblyQualifiedName falhou: %s" % compatibility.safe_repr(exc),
        })

    try:
        result["assembly"] = _safe_assembly_full_name(clr_type)
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_extender_runtime_type",
            "message": "Assembly.FullName falhou: %s" % compatibility.safe_repr(exc),
        })

    try:
        raw_fields = clr_type.GetFields()
        names = []
        for f in raw_fields:
            try:
                names.append(f.Name)
            except Exception:
                continue
        result["fields_count"] = len(names)
        result["field_names"] = names[:MAX_EXTENSION_ITEMS]
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_extender_runtime_type",
            "message": "GetFields() falhou: %s" % compatibility.safe_repr(exc),
        })

    try:
        raw_events = clr_type.GetEvents()
        names = []
        for e in raw_events:
            try:
                names.append(e.Name)
            except Exception:
                continue
        result["events_count"] = len(names)
        result["event_names"] = names[:MAX_EXTENSION_ITEMS]
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_extender_runtime_type",
            "message": "GetEvents() falhou: %s" % compatibility.safe_repr(exc),
        })

    return result, clr_type


def _reflect_extender_interfaces(clr_type, diagnostics):
    """GetInterfaces() do tipo CLR do Extender -- SOMENTE metadados,
    classificados por termos estruturais (contrato item 3), NUNCA
    invocacao."""
    if clr_type is None:
        return []
    try:
        raw_interfaces = clr_type.GetInterfaces()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_extender_interfaces",
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
            "classification": _classify_by_terms(full_name),
        })
    return result


def _compute_channel_flags(interfaces):
    """Determina, a partir das interfaces JA refletidas literalmente, se o
    Extender implementa cada um dos tres canais de extensao descritos no
    contrato (itens 5/6/7). Comparacao por substring, minusculas, sobre o
    FullName -- NUNCA invoca nada."""
    lowered_names = [(i.get("interface") or "").lower() for i in interfaces]
    implements_ctd = any(CUSTOM_TYPE_DESCRIPTOR_TERM in n for n in lowered_names)
    implements_dmop = any(DYNAMIC_META_OBJECT_PROVIDER_TERM in n for n in lowered_names)
    implements_iep = any(EXTENDER_PROVIDER_TERM in n for n in lowered_names)
    return implements_ctd, implements_dmop, implements_iep


def _reflect_extender_members(clr_type, diagnostics):
    """GetProperties()/GetMethods() do tipo CLR do Extender -- SOMENTE
    metadados (mesmo padrao dos probes 16/17: DeclaringType/PropertyType ou
    ReturnType/parametros/assembly), classificados por termos estruturais.
    NENHUMA invocacao acontece aqui. Retorna (properties, methods)."""
    properties = []
    methods = []
    if clr_type is None:
        return properties, methods

    try:
        raw_properties = clr_type.GetProperties()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_extender_members",
            "message": "GetProperties() do Extender falhou: %s" % compatibility.safe_repr(exc),
        })
        raw_properties = []
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
            can_read = bool(prop.CanRead)
        except Exception:
            can_read = None
        try:
            has_index_parameters = len(prop.GetIndexParameters()) > 0
        except Exception:
            has_index_parameters = None
        properties.append({
            "member": name, "member_kind": "property", "declaring_type": declaring_type,
            "return_type": return_type, "can_read": can_read,
            "has_index_parameters": has_index_parameters,
            "assembly": _safe_assembly_full_name(prop.PropertyType) if return_type else None,
            "classification": _classify_by_terms((name or "") + " " + (return_type or "")),
        })

    try:
        raw_methods = clr_type.GetMethods()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_extender_members",
            "message": "GetMethods() do Extender falhou: %s" % compatibility.safe_repr(exc),
        })
        raw_methods = []
    for method in raw_methods:
        try:
            # IsSpecialName cobre os accessors compilados (get_Xxx/set_Xxx),
            # ja representados pelas properties acima -- nao duplicamos.
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
        methods.append({
            "member": name, "member_kind": "method", "declaring_type": declaring_type,
            "return_type": return_type, "parameters": parameters,
            "assembly": _safe_assembly_full_name(method.ReturnType) if return_type else None,
            "classification": _classify_by_terms((name or "") + " " + (return_type or "")),
        })

    return properties, methods


def _compute_method_presence_flags(methods):
    """Registra SOMENTE presenca/assinatura de GetMetaObject/CanExtend
    (contrato itens 6/7) -- NUNCA invoca nenhum dos dois."""
    has_get_meta_object = False
    has_can_extend = False
    for m in methods:
        name_lower = (m.get("member") or "").lower()
        if name_lower == "getmetaobject":
            has_get_meta_object = True
        if name_lower == "canextend":
            has_can_extend = True
    return has_get_meta_object, has_can_extend


# =============================================================================
# Passo 3 do escopo autorizado: canal ICustomTypeDescriptor -- SO chamado se
# a interface ja foi confirmada literalmente. Unico metodo do Extender
# chamado nesta fase, alem do proprio getter 'Extender' no proxy.
# =============================================================================

def _call_get_properties_ctd(extender_obj, diagnostics):
    record = capabilities.probe_method_call(
        extender_obj, "extender", "GetProperties", (), capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    diagnostics.append({"step": "ctd_get_properties", "message": "state=%s" % record["state"]})
    if record["state"] != "confirmed" or "raw_value" not in record:
        return record["state"], None
    return "confirmed", record["raw_value"]


def _confirm_known_collection_interface(collection, diagnostics):
    """Contrato item 4: so enumerar apos confirmar interface CONHECIDA
    (IList/IReadOnlyList/ICollection/Array). Retorna (confirmado, nome da
    interface batida ou None)."""
    try:
        clr_type = collection.GetType()
    except Exception as exc:
        diagnostics.append({
            "step": "confirm_collection_interface",
            "message": "GetType() da colecao falhou: %s" % compatibility.safe_repr(exc),
        })
        return False, None

    try:
        if getattr(clr_type, "IsArray", False):
            diagnostics.append({
                "step": "confirm_collection_interface", "message": "colecao e Array (IsArray=True).",
            })
            return True, "Array"
    except Exception:
        pass

    try:
        raw_interfaces = clr_type.GetInterfaces()
    except Exception as exc:
        diagnostics.append({
            "step": "confirm_collection_interface",
            "message": "GetInterfaces() da colecao falhou: %s" % compatibility.safe_repr(exc),
        })
        return False, None

    for iface in raw_interfaces:
        try:
            full_name = iface.FullName or ""
        except Exception:
            continue
        lowered = full_name.lower()
        for term in KNOWN_COLLECTION_INTERFACE_TERMS:
            if term in lowered:
                diagnostics.append({
                    "step": "confirm_collection_interface",
                    "message": "interface conhecida confirmada: %s" % full_name,
                })
                return True, full_name

    diagnostics.append({
        "step": "confirm_collection_interface",
        "message": "nenhuma interface de colecao conhecida encontrada -- enumeracao NAO autorizada.",
    })
    return False, None


def _read_property_descriptor_fields(item, idx):
    """Le SOMENTE Name/PropertyType/ComponentType/IsReadOnly de UM
    PropertyDescriptor (contrato item 5) -- NUNCA GetValue()/SetValue()/
    ResetValue()/AddValueChanged()/RemoveValueChanged(). Cada leitura isolada
    via capabilities.probe_member (proprio try/except)."""
    entry = {
        "index": idx, "state": "confirmed", "name": None, "property_type": None,
        "component_type": None, "is_read_only": None, "error": None,
    }

    name_record = capabilities.probe_member(
        item, "property_descriptor_%d" % idx, "Name", capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if name_record["state"] == "confirmed" and "raw_value" in name_record:
        value = name_record["raw_value"]
        if isinstance(value, _STRING_TYPES):
            entry["name"] = value
    else:
        entry["state"] = name_record["state"]
        entry["error"] = name_record.get("exception_message")

    type_record = capabilities.probe_member(
        item, "property_descriptor_%d" % idx, "PropertyType", capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if type_record["state"] == "confirmed" and "raw_value" in type_record:
        try:
            entry["property_type"] = type_record["raw_value"].FullName
        except Exception:
            entry["property_type"] = None

    component_record = capabilities.probe_member(
        item, "property_descriptor_%d" % idx, "ComponentType", capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if component_record["state"] == "confirmed" and "raw_value" in component_record:
        try:
            entry["component_type"] = component_record["raw_value"].FullName
        except Exception:
            entry["component_type"] = None

    readonly_record = capabilities.probe_member(
        item, "property_descriptor_%d" % idx, "IsReadOnly", capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if readonly_record["state"] == "confirmed" and "raw_value" in readonly_record:
        ro_value = readonly_record["raw_value"]
        if isinstance(ro_value, bool):
            entry["is_read_only"] = ro_value

    return entry


def _enumerate_extension_items(collection, diagnostics):
    """Enumeracao BOUNDED da colecao de PropertyDescriptor: Count +
    indexador nativo, limite MAX_EXTENSION_ITEMS, falha isolada por item,
    deteccao de duplicidade -- NUNCA iteracao livre (contrato item 4).
    Retorna (items, item_types, enumeration_ok)."""
    items = []
    item_types = []

    count_state, count_value, count_err = _read_count(collection, "extension_items")
    if count_state != "confirmed":
        diagnostics.append({
            "step": "enumerate_extension_items",
            "message": "Count falhou: state=%s erro=%s" % (count_state, count_err),
        })
        return items, item_types, False

    seen_names = set()
    limit = min(count_value, MAX_EXTENSION_ITEMS)
    for idx in range(limit):
        idx_state, item, idx_err = _access_index(collection, "extension_items", idx)
        if idx_state != "confirmed":
            items.append({
                "index": idx, "state": idx_state, "name": None, "property_type": None,
                "component_type": None, "is_read_only": None, "error": idx_err, "duplicate": False,
            })
            item_types.append({"index": idx, "full_name": None, "assembly": None, "error": idx_err})
            continue

        entry = _read_property_descriptor_fields(item, idx)
        name = entry.get("name")
        entry["duplicate"] = bool(name is not None and name in seen_names)
        if name is not None:
            seen_names.add(name)
        items.append(entry)

        try:
            item_clr_type = item.GetType()
            item_types.append({
                "index": idx,
                "full_name": getattr(item_clr_type, "FullName", None),
                "assembly": _safe_assembly_full_name(item_clr_type),
                "error": None,
            })
        except Exception as exc:
            item_types.append({
                "index": idx, "full_name": None, "assembly": None,
                "error": compatibility.safe_repr(exc),
            })

    diagnostics.append({
        "step": "enumerate_extension_items",
        "message": "enumerados %d/%d item(ns) (limite=%d)." % (len(items), count_value, MAX_EXTENSION_ITEMS),
    })
    return items, item_types, True


def _classify_extension_items(items):
    """Classifica cada item enumerado -- controle conhecido / candidato
    Ladder / nao classificado -- mesma logica de precedencia e o mesmo
    padrao 'forbidden_term'/'reason_not_invoked' dos probes 16/17. NUNCA
    invoca nada (so anota o registro ja lido)."""
    records = []
    for entry in items:
        name = entry.get("name")
        record = dict(entry)
        record["invoked"] = False

        if name == CONTROL_MEMBER:
            record["classification"] = "known_dynamic_control"
            record["reason_not_invoked"] = "control only"
            record["forbidden_term"] = None
        elif name and _has_evidence_term(name):
            forbidden = _forbidden_term_in(name)
            record["forbidden_term"] = forbidden
            if forbidden:
                record["classification"] = "candidate_ladder_representation"
                record["reason_not_invoked"] = (
                    "forbidden in this phase: name matches '%s' (side-effecting surface -- "
                    "may write to disk or mutate the project); requires explicit human "
                    "authorization and a disposable destination before any invocation"
                    % forbidden)
            else:
                record["classification"] = "candidate_ladder_representation"
                record["reason_not_invoked"] = "not previously approved"
        else:
            record["classification"] = "unclassified"
            record["reason_not_invoked"] = "no evidence term matched; not a known control"
            record["forbidden_term"] = _forbidden_term_in(name) if name else None

        records.append(record)
    return records


# =============================================================================
# Classificacao PURA do resultado do probe -- fonte unica de verdade (mesmo
# racional de classify_dynamic_probe_result do probe 17), reaplicavel a
# artefatos ja arquivados sem reimplementacao.
# =============================================================================

def classify_extender_probe_result(extender_accessible, extension_channel_enumerable,
                                   control_provider_found, candidate_count, item_count):
    """Casos E1-E4 (contrato desta fatia). Devolve
    (result_case, status, verdict_message).

    REGRA CONTRA FALSO SUCESSO: 'Extender' acessivel + N membros refletidos +
    controle NAO localizado (control_provider_found=False) NUNCA produz
    sucesso -- extender_channel_validated exige as tres condicoes
    (extender_accessible, extension_channel_enumerable,
    control_provider_found) simultaneamente verdadeiras; a ausencia de
    qualquer uma delas cai em E3 (se 'Extender' era acessivel) ou E4 (se nao
    era)."""
    if not extender_accessible:
        return ("E4", "inconclusive",
                "caso E4: 'Extender' inacessivel (reflexao nao confirmou um getter valido, "
                "invocacao nao autorizada, ou a invocacao falhou/retornou nulo). Nenhuma "
                "conclusao sobre o canal de extensao Extender e permitida.")

    extender_channel_validated = bool(extension_channel_enumerable and control_provider_found)

    if not extender_channel_validated:
        return ("E3", "inconclusive",
                "caso E3: 'Extender' acessivel, mas o canal de extensao NAO foi validado -- "
                "o controle '%s' nao foi reencontrado por um caminho estrutural que passe "
                "pelo Extender (reflexao sem mecanismo de extensao reconhecido, provider nao "
                "enumeravel, ou controle ausente entre os itens efetivamente enumerados). "
                "Nenhuma conclusao sobre a existencia ou ausencia de candidatos Ladder no "
                "canal Extender e permitida." % CONTROL_MEMBER)

    if candidate_count > 0:
        return ("E2", "ok",
                "caso E2: canal Extender validado (controle '%s' reencontrado), %d "
                "candidato(s) Ladder no canal -- abre espaco para o proximo probe."
                % (CONTROL_MEMBER, candidate_count))

    return ("E1", "ok",
            "caso E1: canal Extender validado (controle '%s' reencontrado), 0 candidatos "
            "Ladder entre %d item(ns) enumerados. Conclusao LIMITADA: nenhum candidato foi "
            "encontrado no canal examinado. NAO afirma ausencia global de API Ladder."
            % (CONTROL_MEMBER, item_count))


# =============================================================================
# Orquestracao + escrita de artefatos.
# =============================================================================

def _build_known_control_discovery(control_provider_found, proxy_type_name,
                                   extender_runtime_type, control_entry):
    if not control_provider_found:
        return {
            "control_provider_found": False,
            "extender_channel_validated": False,
            "reason": "known dynamic member was not rediscovered through the Extender channel",
        }
    extender_type_name = extender_runtime_type.get("full_name") if extender_runtime_type else None
    return {
        "control_member": CONTROL_MEMBER,
        "discovery_path": [
            {"stage": "proxy", "type": proxy_type_name},
            {"stage": "extender", "type": extender_type_name},
            {"stage": "provider", "type": extender_type_name},
            {"stage": "property_descriptor", "name": CONTROL_MEMBER,
             "property_type": control_entry.get("property_type") if control_entry else None},
        ],
    }


def _build_report_markdown(result, target_identity, extender_member, extender_runtime_type,
                           candidates, known_control_discovery, extension_items):
    lines = [
        "# Sondagem do canal Extender/IExtendedObject -- probe_ladder_extender_surface",
        "",
        "Fase L1 (docs/14-ladder-roadmap.md), IRMAO dos probes 16 e 17. Modo: "
        "**somente leitura**. Nenhum parser Ladder; nenhuma leitura de `.text` de "
        "declaracao/implementacao; nenhuma chamada a GetValue()/SetValue()/GetMetaObject()/"
        "CanExtend().",
        "",
        "- target_node_id: `%s`" % result.get("target_node_id"),
        "- abortado: **%s**" % result.get("aborted"),
        "- motivo do aborto: %s" % result.get("abort_reason"),
        "- identidade do alvo confirmada: **%s**" % result.get("target_identity_confirmed"),
        "- resultado (E1-E4): **%s**" % result.get("result_case"),
        "- extender_accessible: **%s**" % result.get("extender_accessible"),
        "- extension_channel_enumerable: **%s**" % result.get("extension_channel_enumerable"),
        "- control_provider_found: **%s**" % result.get("control_provider_found"),
        "- extender_channel_validated: **%s**" % result.get("extender_channel_validated"),
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

    if extender_member is not None:
        lines.append("## Reflexao do membro 'Extender' no proxy-alvo")
        lines.append("- encontrado: **%s**" % extender_member.get("found"))
        lines.append("- invocacao autorizada: **%s**" % extender_member.get("invocation_authorized"))
        lines.append("- declaring_type: `%s`" % extender_member.get("declaring_type"))
        lines.append("- return_type: `%s`" % extender_member.get("return_type"))
        lines.append("")

    if extender_runtime_type is not None:
        lines.append("## Tipo do objeto Extender")
        lines.append("- full_name: `%s`" % extender_runtime_type.get("full_name"))
        lines.append("- implements_icustomtypedescriptor: **%s**"
                     % extender_runtime_type.get("implements_icustomtypedescriptor"))
        lines.append("- implements_idynamicmetaobjectprovider: **%s**"
                     % extender_runtime_type.get("implements_idynamicmetaobjectprovider"))
        lines.append("- implements_iextenderprovider: **%s**"
                     % extender_runtime_type.get("implements_iextenderprovider"))
        lines.append("")

    result_case = result.get("result_case")
    if result_case == "E4":
        lines.append("## ATENCAO -- 'Extender' inacessivel (caso E4)")
        lines.append("")
        lines.append(
            "Nenhuma conclusao pode ser feita sobre o canal de extensao Extender: o membro "
            "nao pode ser invocado com seguranca ou a invocacao falhou/retornou nulo.")
        lines.append("")
    elif result_case == "E3":
        lines.append("## ATENCAO -- canal Extender NAO validado (caso E3)")
        lines.append("")
        lines.append(
            "'Extender' e acessivel, mas o controle '%s' NAO foi reencontrado por um "
            "caminho estrutural que passe pelo Extender. Isto e INCONCLUSIVO -- NENHUMA "
            "conclusao sobre a existencia ou ausencia de uma API Ladder por este canal e "
            "permitida, mesmo que o Extender exponha muitos membros refletidos."
            % CONTROL_MEMBER)
        lines.append("")
    elif result_case == "E1":
        lines.append("## Conclusao (caso E1) -- limitada ao canal examinado")
        lines.append("")
        lines.append(
            "O canal Extender foi validado (controle '%s' reencontrado), mas nenhum "
            "candidato no canal examinado bateu os termos de evidencia Ladder. Isto NAO "
            "afirma ausencia global de API Ladder -- apenas que o canal Extender examinado "
            "nao apresentou candidatos." % CONTROL_MEMBER)
        lines.append("")

    if known_control_discovery.get("control_provider_found") is False:
        lines.append("## Cadeia de descoberta do controle")
        lines.append("- %s" % known_control_discovery.get("reason"))
        lines.append("")
    elif "discovery_path" in known_control_discovery:
        lines.append("## Cadeia de descoberta do controle '%s'" % CONTROL_MEMBER)
        for stage in known_control_discovery["discovery_path"]:
            lines.append("- `%s`: %r" % (stage.get("stage"), stage))
        lines.append("")

    lines.append("## Itens enumerados do canal Extender (%d)" % len(extension_items))
    for item in extension_items[:200]:
        lines.append(
            "- `%s` classification=%s duplicate=%s"
            % (item.get("name"), item.get("classification"), item.get("duplicate")))
    lines.append("")
    lines.append("## Candidatos a representacao Ladder (%d)" % len(candidates))
    for candidate in candidates[:200]:
        lines.append("- `%s` (nao invocado: %s)" % (candidate.get("name"), candidate.get("reason_not_invoked")))
    lines.append("")
    return "\n".join(lines) + "\n"


def _write_artifacts(output_dir, result, diagnostics, target_identity, extender_member,
                     extender_runtime_type, extender_interfaces, extender_properties,
                     extender_methods, extension_items, extension_item_types,
                     known_control_discovery, candidates):
    file_io.ensure_dir(output_dir)

    manifest = {
        "schema_version": "1.0",
        "script": "probes/18_probe_ladder_extender_surface.py",
        "generated_at": result["generated_at"],
        "mode": "read_only",
        "target_node_id": result["target_node_id"],
        "aborted": result["aborted"],
        "abort_reason": result["abort_reason"],
        "target_identity_confirmed": result["target_identity_confirmed"],
        "control_member": CONTROL_MEMBER,
        "extender_accessible": result["extender_accessible"],
        "extension_channel_enumerable": result["extension_channel_enumerable"],
        "control_provider_found": result["control_provider_found"],
        "extender_channel_validated": result["extender_channel_validated"],
        "ladder_candidate_count": result["ladder_candidate_count"],
        "extension_item_count": result["extension_item_count"],
        "result_case": result["result_case"],
        "status": result["status"],
    }
    file_io.write_json(os.path.join(output_dir, "manifest.json"), manifest)
    file_io.write_json(os.path.join(output_dir, "target-identity.json"),
                       target_identity if target_identity is not None else {})
    file_io.write_json(os.path.join(output_dir, "extender-member.json"),
                       extender_member if extender_member is not None else {})
    file_io.write_json(os.path.join(output_dir, "extender-runtime-type.json"),
                       extender_runtime_type if extender_runtime_type is not None else {})
    file_io.write_json(os.path.join(output_dir, "extender-interfaces.json"), extender_interfaces)
    file_io.write_json(os.path.join(output_dir, "extender-properties.json"), extender_properties)
    file_io.write_json(os.path.join(output_dir, "extender-methods.json"), extender_methods)
    file_io.write_json(os.path.join(output_dir, "extension-items.json"), extension_items)
    file_io.write_json(os.path.join(output_dir, "extension-item-types.json"), extension_item_types)
    file_io.write_json(os.path.join(output_dir, "known-control-discovery.json"), known_control_discovery)
    file_io.write_json(os.path.join(output_dir, "ladder-candidate-members.json"), candidates)

    md = _build_report_markdown(
        result, target_identity, extender_member, extender_runtime_type, candidates,
        known_control_discovery, extension_items)
    # Os quatro artefatos comuns (diagnostics, safety-declaration, report,
    # checksums) saem por `common.artifacts`, na ordem contratual e com
    # checksums por ultimo. O que e especifico deste probe continua acima.
    artifacts.write_common_artifacts(
        output_dir, diagnostics, dict(SAFETY_DECLARATION), md)

    result["artifacts_dir"] = output_dir
    return result


def _empty_write(output_dir, result, diagnostics):
    empty_discovery = {
        "control_provider_found": False,
        "extender_channel_validated": False,
        "reason": "known dynamic member was not rediscovered through the Extender channel",
    }
    return _write_artifacts(
        output_dir, result, diagnostics, None, None, None, [], [], [], [], [],
        empty_discovery, [])


def probe_ladder_extender_surface(application, ladder_probe_config, output_dir):
    """Ponto de entrada publico. `application` ja deve estar resolvida pelo
    chamador (mesmo padrao de common/). `ladder_probe_config` e o mesmo
    formato de dict usado pelos probes 16/17 (4 chaves obrigatorias).
    `output_dir` e o diretorio onde os artefatos desta sondagem sao gravados
    diretamente.

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
        "extender_accessible": False,
        "extension_channel_enumerable": False,
        "control_provider_found": False,
        "extender_channel_validated": False,
        "ladder_candidate_count": 0,
        "extension_item_count": 0,
        "result_case": "E4",
        "status": "inconclusive",
    }

    # Passo 0: mesma defesa em profundidade dos probes 16/17 -- este probe
    # NAO confia cegamente no formato de ladder_probe_config.
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
    # -> is_folder == false. SO ENTAO sondar o Extender.
    identity = _probe_target_identity(proxy, "ladder_target")
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
            "message": "divergencia(s) de identidade -- abortando SEM sondar Extender: %s"
                      % mismatches,
        })
        empty_discovery = {
            "control_provider_found": False,
            "extender_channel_validated": False,
            "reason": "known dynamic member was not rediscovered through the Extender channel",
        }
        return _write_artifacts(
            output_dir, result, diagnostics, target_identity_doc, None, None, [], [], [], [], [],
            empty_discovery, [])

    result["target_identity_confirmed"] = True
    diagnostics.append({
        "step": "identity_check",
        "message": "identidade confirmada (name/object_guid/type_guid/is_folder) -- prosseguindo.",
    })

    # A partir daqui: reflexao do membro 'Extender' -> invocacao guardada ->
    # inspecao do objeto retornado -> canal ICustomTypeDescriptor (ordem
    # fixa do contrato desta fatia).
    extender_member = _reflect_extender_member(proxy, diagnostics)
    extender_state, extender_obj = _invoke_extender(proxy, extender_member, diagnostics)
    extender_accessible = extender_state == "confirmed" and extender_obj is not None

    extender_runtime_type = None
    extender_interfaces = []
    extender_properties = []
    extender_methods = []
    extension_items = []
    extension_item_types = []
    extension_channel_enumerable = False

    if extender_accessible:
        extender_runtime_type, extender_clr_type = _reflect_extender_runtime_type(
            extender_obj, diagnostics)
        extender_interfaces = _reflect_extender_interfaces(extender_clr_type, diagnostics)
        implements_ctd, implements_dmop, implements_iep = _compute_channel_flags(extender_interfaces)
        extender_runtime_type["implements_icustomtypedescriptor"] = implements_ctd
        extender_runtime_type["implements_idynamicmetaobjectprovider"] = implements_dmop
        extender_runtime_type["implements_iextenderprovider"] = implements_iep

        extender_properties, extender_methods = _reflect_extender_members(
            extender_clr_type, diagnostics)
        extender_runtime_type["interfaces_count"] = len(extender_interfaces)
        extender_runtime_type["properties_count"] = len(extender_properties)
        extender_runtime_type["methods_count"] = len(extender_methods)
        has_gmo, has_ce = _compute_method_presence_flags(extender_methods)
        extender_runtime_type["has_get_meta_object_method"] = has_gmo
        extender_runtime_type["has_can_extend_method"] = has_ce

        if implements_ctd:
            ctd_state, collection = _call_get_properties_ctd(extender_obj, diagnostics)
            if ctd_state == "confirmed" and collection is not None:
                known_ok, known_iface = _confirm_known_collection_interface(collection, diagnostics)
                if known_ok:
                    extension_items, extension_item_types, extension_channel_enumerable = (
                        _enumerate_extension_items(collection, diagnostics))
                else:
                    diagnostics.append({
                        "step": "extension_channel",
                        "message": "colecao retornada por GetProperties() nao implementa "
                                  "interface de colecao conhecida -- enumeracao NAO autorizada.",
                    })
            else:
                diagnostics.append({
                    "step": "extension_channel",
                    "message": "extender.GetProperties() (ICustomTypeDescriptor) falhou: "
                              "state=%s." % ctd_state,
                })
        else:
            diagnostics.append({
                "step": "extension_channel",
                "message": "Extender nao implementa ICustomTypeDescriptor -- nenhum canal de "
                          "enumeracao de propriedades reconhecido nesta fase.",
            })

    extension_item_records = _classify_extension_items(extension_items)
    candidates = [r for r in extension_item_records
                 if r["classification"] == "candidate_ladder_representation"]
    control_entry = next(
        (r for r in extension_item_records if r.get("name") == CONTROL_MEMBER), None)
    control_provider_found = control_entry is not None

    proxy_type_name = _safe_clr_full_name(proxy)
    known_control_discovery = _build_known_control_discovery(
        control_provider_found, proxy_type_name, extender_runtime_type, control_entry)

    extender_channel_validated = bool(
        extender_accessible and extension_channel_enumerable and control_provider_found)

    result["extender_accessible"] = extender_accessible
    result["extension_channel_enumerable"] = extension_channel_enumerable
    result["control_provider_found"] = control_provider_found
    result["extender_channel_validated"] = extender_channel_validated
    result["ladder_candidate_count"] = len(candidates)
    result["extension_item_count"] = len(extension_item_records)

    result_case, status, verdict_message = classify_extender_probe_result(
        extender_accessible, extension_channel_enumerable, control_provider_found,
        len(candidates), len(extension_item_records))
    result["result_case"] = result_case
    result["status"] = status
    diagnostics.append({"step": "verdict", "message": verdict_message})

    return _write_artifacts(
        output_dir, result, diagnostics, target_identity_doc, extender_member,
        extender_runtime_type, extender_interfaces, extender_properties, extender_methods,
        extension_item_records, extension_item_types, known_control_discovery, candidates)


# =============================================================================
# Execucao standalone (--runscript), mesmo padrao dos probes 16/17.
# =============================================================================

def main():
    print("=" * 60)
    print("[INFO] probes/18_probe_ladder_extender_surface.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. Fase L1 -- sondagem do canal Extender/")
    print("[INFO] IExtendedObject do objeto POU-alvo, complementar aos probes 16/17.")
    print("[INFO] Nenhum parser Ladder. Nenhuma leitura de .text de declaracao/implementacao.")

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

    run_dir = file_io.new_export_dir(EXPORT_ROOT, "18_probe_ladder_extender_surface")
    result = probe_ladder_extender_surface(application, ladder_probe_config, run_dir)

    if result["aborted"]:
        print("[BLOQUEADO] abort_reason=%s" % result["abort_reason"])
    else:
        print("[OK] identidade confirmada; result_case=%s extender_channel_validated=%s "
             "ladder_candidate_count=%s"
             % (result["result_case"], result["extender_channel_validated"],
                result["ladder_candidate_count"]))
    print("[OK] Artefatos gravados em: %s" % run_dir)
    print("=" * 60)


main()

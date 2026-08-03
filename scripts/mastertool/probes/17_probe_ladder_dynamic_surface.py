# -*- coding: utf-8 -*-
"""17_probe_ladder_dynamic_surface.py -- Fase L1 (docs/14-ladder-roadmap.md:
"Descoberta da representacao Ladder"), IRMAO de
probes/16_probe_ladder_object_surface.py -- mesma identidade de alvo, mesmo
modo somente leitura, mesma filosofia de whitelist explicita. Este arquivo
NAO substitui o probe 16: ele responde a uma pergunta que o probe 16 nao
podia responder.

Motivacao (o "porque"): o probe 16 enumerou a superficie do objeto POU-alvo
SOMENTE via reflexao CLR pura (GetType().GetProperties()/GetMethods()). Essa
reflexao NUNCA viu 'textual_declaration', apesar deste membro ser
comprovadamente funcional -- e o que common/read_only_text_exporter.py usa,
com sucesso, para ler os 68 objetos de texto do projeto real (ver
docs/api/mastertool-api-observations.md, achado 'ExtendedObject[T] e o
protocolo dinamico do DLR'). A causa e conhecida: o objeto retornado por
active_application/get_children() e um ExtendedObject[IScriptObject] que
implementa IExtendedObject e tambem, por extensao anexada em RUNTIME pelo
ScriptEngine, IScriptObjectWithTextualDeclaration -- a reflexao sobre o TIPO
CLR estatico nao alcanca extensoes anexadas dinamicamente. Consequencia
pratica: o resultado negativo do probe 16 ("nenhuma property de reflexao da
acesso a Ladder") e INCONCLUSIVO quanto a superficie DINAMICA -- ele so
prova algo sobre a superficie ESTATICA. Este probe existe para separar "a
API Ladder nao existe nesta superficie" de "existe, e so a reflexao pura nao
a enxerga" (AGENTS.md, regra 9: "dir() nunca e fonte de verdade", mas
tambem nunca e ausencia de verdade -- so um diagnostico, testado aqui contra
uma whitelist explicita, nunca por enumeracao livre).

Sequencia obrigatoria de execucao desta fatia (ordem fixa, sem excecao):

    enumerar com dir() (diagnostico, NUNCA fonte de verdade sozinho)
    -> comparar com reflexao CLR (probe 16, copia local)
    -> classificar membros (controle conhecido / getter seguro / candidato /
       nao classificado)
    -> testar hasattr() APENAS contra whitelist literal (nunca hasattr()
       generico sobre tudo que apareceu no dir() -- hasattr() invoca o
       getter, entao 'testar tudo' seria 'invocar tudo')
    -> invocar SOMENTE getters ja aprovados no probe 16
       (SAFE_GETTER_WHITELIST, copiada literalmente)

NENHUM membro novo descoberto durante esta propria execucao e invocado --
nomes encontrados no dir() que nao estejam nesta whitelist viram, no maximo,
CANDIDATOS registrados para a Fase 18 (nunca sondados aqui).

Mesma identidade de alvo do probe 16 (contrato, secao 3.1): os 4 campos
'expected_*' (nome, object_guid, type_guid) mais is_folder==False, checados
NA MESMA ORDEM, ANTES de qualquer sondagem de superficie. Qualquer
divergencia aborta com 'target_identity_mismatch'.

PROIBIDO nesta fase (defesa em profundidade -- guarda ANTES de qualquer
invocacao, nao so ausencia de chamada no codigo):
  - export_xml e QUALQUER metodo de exportacao;
  - setters;
  - metodos com parametros;
  - metodos/membros associados a save/import/create/delete/replace (ver
    FORBIDDEN_GETTER_NAME_TERMS, copiada do probe 16);
  - leitura de '.text' de implementacao grafica (nunca acessado -- nem
    mesmo o membro documento 'textual_implementation' e lido quando o
    indicador 'has_textual_implementation' correspondente nao vier
    confirmado True: mesmo portao obrigatorio de AGENTS.md regra 13);
  - serializacao de proxies via str()/repr()/ToString() -- toda
    representacao passa por common/capabilities.build_representation();
  - qualquer operacao que escreva em disco pela API do objeto;
  - qualquer alteracao no projeto.

ATENCAO ESPECIAL sobre o controle dinamico ('textual_declaration'/
'textual_implementation'): AGENTS.md regra 13 exige que esses dois membros
(e seus '.text') SO sejam acessados depois que o indicador booleano
correspondente ('has_textual_declaration'/'has_textual_implementation')
vier CONFIRMADO e estritamente True -- nunca acesso especulativo. Este
probe respeita essa regra tambem para a MERA deteccao de presenca: o
criterio de validade preve duas fontes, nesta ordem de preferencia -- (1) o
nome aparecer em dir() (enumeracao, NUNCA invoca o getter) ou, so quando
ausente do dir(), (2) hasattr() controlado sobre 'textual_declaration'/
'textual_implementation' -- e ESSA segunda fonte so e tentada depois que o
indicador booleano 'has_*' correspondente ja veio confirmado True (o
'has_*' em si e seguro: e so um booleano, e a propria razao de ser do
portao). O valor de 'textual_declaration'/'textual_implementation' (o
documento em si) NUNCA e capturado/representado aqui -- so o ESTADO da
sondagem (presente/ausente) interessa a este probe; ler '.text' continua
proibido nesta fase (seria a Fase L2/parser).

Integracao com o runner supervisionado: esta fatia NAO altera
automation/supervised_snapshot_runner.py nem run_config.py -- nenhuma nova
operacao foi registrada no contrato nesta fatia (fora de escopo). Este
arquivo roda standalone via --runscript, mesmo padrao do probe 16, com um
alvo padrao hardcoded SO para essa execucao avulsa (NUNCA usado por um
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
# probes/16_probe_ladder_object_surface.py -- mesmo racional la documentado.
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

# --- termos de classificacao (copia LITERAL de probes/16_..., mesma
# filosofia de nao-import-cruzado entre modulos independentes ja documentada
# la) -- usados SO para CLASSIFICAR um nome ja encontrado por dir(), nunca
# para inventar um nome a sondar.
EVIDENCE_TERMS = (
    "network", "ladder", "implementation", "graphical", "element",
    "connector", "connection", "pin", "export", "xml", "plcopen", "serialize",
)

# Copia LITERAL de probes/16_probe_ladder_object_surface.py. Qualquer membro
# cujo NOME contenha um destes termos NUNCA e invocado, mesmo que apareca em
# alguma whitelist por engano futuro (defesa em profundidade).
FORBIDDEN_GETTER_NAME_TERMS = (
    "write", "modify", "alter", "import", "execute", "invoke", "run",
    "save", "export", "delete", "remove", "create", "build", "compile",
    "download", "force", "close", "clear", "reset", "apply", "replace",
    "generate", "destroy", "dispose", "set_",
)

# Copia LITERAL da whitelist explicita de getters aprovados no probe 16 --
# ver comentario completo la (secao "Whitelist EXPLICITA de getters
# candidatos a invocacao"). Neste probe, cada nome so e efetivamente
# invocado se (a) hasattr() controlado confirmar presenca E (b) nao conter
# nenhum termo de FORBIDDEN_GETTER_NAME_TERMS -- os mesmos dois criterios do
# probe 16, adaptados a uma superficie sem metadados de reflexao (sem
# 'CanRead'/'GetIndexParameters()' aqui -- soh a whitelist decide o que e
# "getter").
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

# Controles conhecidos da superficie DINAMICA (contrato desta fatia). Os
# dois primeiros ('has_textual_declaration'/'has_textual_implementation')
# sao booleanos puros, sempre seguros de sondar (sao o proprio portao). Os
# dois ultimos ('textual_declaration'/'textual_implementation') so sao
# sondados via hasattr() SE o 'has_*' correspondente ja veio confirmado
# True (AGENTS.md regra 13) -- e mesmo assim NUNCA tem seu valor capturado/
# representado aqui (o valor e um documento, nao um primitivo; ler '.text'
# continua fora de escopo desta fase).
CONTROL_GATE_PAIRS = (
    ("has_textual_declaration", "textual_declaration"),
    ("has_textual_implementation", "textual_implementation"),
)
KNOWN_DYNAMIC_CONTROLS = ("textual_declaration", "has_textual_declaration",
                          "textual_implementation", "has_textual_implementation")

# O membro de controle usado como criterio de validade do probe inteiro
# (contrato desta fatia: "o coracao do probe"). Escolhido porque e o membro
# comprovadamente funcional (common/read_only_text_exporter.py) que a
# reflexao pura do probe 16 nunca viu.
CONTROL_MEMBER = "textual_declaration"

# safety-declaration.json -- EXATAMENTE estas 10 chaves, todas False. Copia
# literal do mesmo dicionario do probe 16: nenhum caminho de codigo desta
# fatia chama export()/import/save/build/download/force, nem le '.text' de
# implementacao/declaracao.
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
# ao default do probe 16 (mesmo alvo, mesma evidencia de escolha: ver o
# comentario completo la). NUNCA usado por um eventual runner supervisionado
# -- este e so o modo standalone avulso.
DEFAULT_TARGET_NODE_ID = "application/9/4"
DEFAULT_EXPECTED_NAME = "BLINK_QUE_FUNCIONA"
DEFAULT_EXPECTED_GUID = "beca53e2-8466-404a-baf5-9fba1adc0fac"
DEFAULT_EXPECTED_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"


# =============================================================================
# Navegacao bounded/indexada -- copia local deliberada do mesmo padrao
# aprovado em probes/16_probe_ladder_object_surface.py (mesma filosofia de
# independencia por modulo). get_children(False) + Count + indexador nativo
# -- NUNCA iteracao direta da colecao CLR.
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
    formato -> None (invalido). Copia identica do probe 16."""
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
    get_children(False) + Count + indexador nativo. Copia identica do
    probe 16."""
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
# Identidade -- copia local deliberada, identica ao probe 16 (mesmo
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
# Reflexao CLR -- SOMENTE para construir o CONJUNTO de nomes comparado
# contra o dir() dinamico (contrato: "comparar com reflexao CLR"). Nenhuma
# invocacao acontece aqui -- so leitura de metadados via
# GetType()/GetProperties()/GetMethods(), mesma tecnica do probe 16.
# =============================================================================

def _reflect_clr_members(proxy, diagnostics):
    """Retorna a lista de membros vistos por reflexao CLR pura (propriedades
    + metodos publicos nao-especiais), no mesmo formato usado pelo probe 16
    (properties.json/methods.json combinados). Usado SO para comparacao de
    nomes -- nenhum destes membros e invocado neste probe."""
    try:
        clr_type = proxy.GetType()
    except Exception as exc:
        diagnostics.append({
            "step": "reflect_clr_members",
            "message": "GetType() falhou: %s" % compatibility.safe_repr(exc),
        })
        return []

    result = []

    try:
        raw_properties = clr_type.GetProperties()
    except Exception as exc:
        raw_properties = []
        diagnostics.append({
            "step": "reflect_clr_members",
            "message": "GetProperties() falhou: %s" % compatibility.safe_repr(exc),
        })
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
        result.append({
            "member": name, "member_kind": "property",
            "declaring_type": declaring_type, "return_type": return_type, "parameters": [],
        })

    try:
        raw_methods = clr_type.GetMethods()
    except Exception as exc:
        raw_methods = []
        diagnostics.append({
            "step": "reflect_clr_members",
            "message": "GetMethods() falhou: %s" % compatibility.safe_repr(exc),
        })
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
        result.append({
            "member": name, "member_kind": "method",
            "declaring_type": declaring_type, "return_type": return_type, "parameters": parameters,
        })

    return result


# =============================================================================
# Superficie dinamica (dir()) -- SOMENTE diagnostico (contrato,
# common/capabilities.diagnostic_dir): lista vazia NUNCA significa "sem
# membros", so "introspeccao generica indisponivel". Nenhuma invocacao
# acontece aqui -- dir() em si nao invoca getters.
# =============================================================================

def _has_evidence_term(name):
    lowered = (name or "").lower()
    return any(term in lowered for term in EVIDENCE_TERMS)


def _forbidden_term_in(name):
    """Devolve o termo proibido que o nome contem, ou None. Usado para
    ANOTAR o registro do membro -- a guarda de invocacao propriamente dita
    e aplicada separadamente, antes de qualquer chamada."""
    lowered = (name or "").lower()
    for term in FORBIDDEN_GETTER_NAME_TERMS:
        if term in lowered:
            return term
    return None


def classify_dynamic_probe_result(named_access_validated, enumeration_available,
                                  candidate_count, dir_member_count,
                                  safe_getter_count):
    """Classificacao PURA (sem I/O, sem proxy) do resultado do probe.

    Extraida do corpo da sondagem para ter UMA fonte de verdade: o mesmo
    criterio que classifica uma execucao ao vivo precisa poder ser
    reaplicado a artefatos ja arquivados, sem reimplementacao. Duas copias
    da regra divergiriam, e a divergencia so apareceria como duas conclusoes
    diferentes sobre a MESMA coleta.

    ACESSO POR NOME e ENUMERACAO DE NOMES sao capacidades distintas e nao
    compartilham gate. A execucao real de 2026-07-27 provou por que: o
    controle foi confirmado por hasattr() (acesso funciona) enquanto dir()
    devolveu lista vazia (enumeracao nao funciona). Com gate unico isso
    virou "evidencia forte de que a superficie dinamica nao expoe Ladder" --
    conclusao que os dados nao sustentam, porque candidate_count e derivado
    da lista do dir(): zero candidatos vindos de zero nomes enumerados nao
    mede ausencia, mede ausencia de enumeracao.

    Devolve (result_case, status, verdict_message).
    """
    if not named_access_validated:
        return ("C", "inconclusive",
                "caso C: controle '%s' nao confirmado pela superficie dinamica -- "
                "probe INCONCLUSIVO. Nenhuma conclusao sobre existencia ou ausencia "
                "de API Ladder e permitida." % CONTROL_MEMBER)

    if not enumeration_available:
        return ("D", "dynamic_discovery_channel_unavailable",
                "caso D: acesso dinamico por nome CONHECIDO comprovado (controle "
                "'%s' confirmado e ausente da reflexao CLR), mas o proxy nao "
                "forneceu canal de enumeracao de membros (dir() sem nomes). Nenhuma "
                "conclusao pode ser feita sobre existencia ou ausencia de acessores "
                "Ladder nao conhecidos previamente -- os %d nome(s) da whitelist "
                "testados sao hipoteses, e a ausencia deles nada diz sobre nomes nao "
                "adivinhados." % (CONTROL_MEMBER, safe_getter_count))

    if candidate_count > 0:
        return ("A", "ok",
                "caso A: acesso por nome validado, enumeracao disponivel, %d "
                "candidato(s) Ladder -- abre espaco para acesso controlado."
                % candidate_count)

    return ("B", "ok",
            "caso B: acesso por nome validado, enumeracao disponivel sobre %d "
            "nome(s), 0 candidatos. Conclusao LIMITADA: nenhum candidato Ladder foi "
            "encontrado no canal dinamico enumerado. NAO afirma ausencia global de "
            "API Ladder." % dir_member_count)


def _classify_dynamic_member(name, clr_member_names):
    """Classifica um nome ja encontrado por dir() -- NUNCA usado para
    inventar nomes a sondar. Ordem de precedencia: controle conhecido >
    getter seguro conhecido > candidato (bateu EVIDENCE_TERMS) >
    nao classificado."""
    if name in KNOWN_DYNAMIC_CONTROLS:
        return "known_dynamic_control", "control only"
    if name in SAFE_GETTER_WHITELIST:
        return "known_safe_getter", "pending_whitelist_hasattr_check"
    if _has_evidence_term(name):
        # Candidato que TAMBEM bate um termo proibido (export_xml,
        # import_xml, export_native...) nao pode sair do artefato com a
        # mesma cara de 'networks'. Os dois sao candidatos legitimos para a
        # fase 18, mas um deles ESCREVE EM DISCO, e quem desenhar a fase 18
        # le este arquivo -- nao a whitelist do codigo. "not previously
        # approved" descreveria mal esse caso: nao e falta de aprovacao, e
        # proibicao ativa nesta fase.
        forbidden = _forbidden_term_in(name)
        if forbidden:
            return ("candidate_ladder_representation",
                    "forbidden in this phase: name matches '%s' (side-effecting "
                    "surface -- may write to disk or mutate the project); "
                    "requires explicit human authorization and a disposable "
                    "destination before any invocation" % forbidden)
        return "candidate_ladder_representation", "not previously approved"
    return "unclassified", "no evidence term matched; not a known control or safe getter"


def _build_dynamic_member_records(dynamic_dir_names, clr_member_names):
    """Um registro por nome visto em dir(), com as 8 chaves do contrato
    (secao 'Classificacao'). 'hasattr_checked'/'hasattr_result'/'invoked'
    comecam neutros aqui -- so as fases seguintes (whitelist hasattr /
    safe getters) os preenchem, IN PLACE, para os nomes que passam pela
    whitelist."""
    records = []
    for name in dynamic_dir_names:
        classification, reason = _classify_dynamic_member(name, clr_member_names)
        records.append({
            "name": name,
            "seen_by_dir": True,
            "seen_by_clr_reflection": name in clr_member_names,
            "hasattr_checked": False,
            "hasattr_result": None,
            "invoked": False,
            "classification": classification,
            "reason_not_invoked": reason,
            # Campo ADITIVO (alem das 8 chaves do contrato): torna a
            # proibicao legivel por maquina, nao so pela prosa do
            # 'reason_not_invoked'. A fase 18 pode filtrar por ele em vez de
            # casar substring.
            "forbidden_term": _forbidden_term_in(name),
        })
    return records


# =============================================================================
# Whitelist hasattr() (contrato: "testar hasattr() apenas contra
# whitelist") -- controles conhecidos, com o portao obrigatorio de AGENTS.md
# regra 13 para 'textual_declaration'/'textual_implementation'.
# =============================================================================

def _check_control_gate_pair(proxy, gate_name, control_name, dynamic_dir_names,
                             records_by_name, whitelist_results, diagnostics):
    """Sonda UM par (has_X, X): has_X e sempre sondado (booleano puro,
    seguro); X so e sondado por hasattr() controlado se NAO ja apareceu no
    dir() (enumeracao pura, sem invocacao) E se has_X veio CONFIRMADO True
    (portao AGENTS.md regra 13). O VALOR de X nunca e capturado -- so o
    ESTADO da sondagem interessa aqui. Retorna seen_by_dynamic_surface (bool)
    para o membro de controle X."""

    # has_X -- booleano puro, sempre seguro de sondar. O valor booleano E
    # capturado e representado (primitivo nativo, sem risco).
    gate_record = capabilities.probe_member(
        proxy, "ladder_target", gate_name, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    gate_seen_by_dir = gate_name in dynamic_dir_names
    gate_value = gate_record.get("raw_value") if gate_record["state"] == "confirmed" else None
    gate_confirmed_true = gate_record["state"] == "confirmed" and gate_value is True

    whitelist_results.append({
        "name": gate_name,
        "hasattr_checked": True,
        "hasattr_result": gate_record["state"] == "confirmed",
        "state": gate_record["state"],
        "gate": None,
    })
    if gate_name in records_by_name:
        record = records_by_name[gate_name]
        record["hasattr_checked"] = True
        record["hasattr_result"] = gate_record["state"] == "confirmed"
        record["invoked"] = True
        record["reason_not_invoked"] = None
    diagnostics.append({
        "step": "control_gate", "member": gate_name,
        "message": "state=%s seen_by_dir=%s confirmed_true=%s"
                  % (gate_record["state"], gate_seen_by_dir, gate_confirmed_true),
    })

    # X -- so sondado por hasattr() se AINDA nao visto por dir() (enumeracao
    # ja e prova suficiente, sem necessidade de invocar nada) e se o portao
    # 'has_X' veio confirmado True.
    control_seen_by_dir = control_name in dynamic_dir_names
    if control_seen_by_dir:
        whitelist_results.append({
            "name": control_name, "hasattr_checked": False, "hasattr_result": None,
            "state": None, "gate": "not_needed_seen_by_dir",
        })
        seen_by_dynamic_surface = True
        diagnostics.append({
            "step": "control_member", "member": control_name,
            "message": "presente em dir() -- hasattr() controlado dispensado.",
        })
    elif gate_confirmed_true:
        ctrl_record = capabilities.probe_member(
            proxy, "ladder_target", control_name, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
            capture_value=False)  # NUNCA captura o valor (documento, fora de escopo)
        whitelist_results.append({
            "name": control_name, "hasattr_checked": True,
            "hasattr_result": ctrl_record["state"] == "confirmed",
            "state": ctrl_record["state"], "gate": "has_%s_confirmed_true" % control_name,
        })
        seen_by_dynamic_surface = ctrl_record["state"] == "confirmed"
        diagnostics.append({
            "step": "control_member", "member": control_name,
            "message": "hasattr() controlado (portao aberto): state=%s" % ctrl_record["state"],
        })
    else:
        whitelist_results.append({
            "name": control_name, "hasattr_checked": False, "hasattr_result": None,
            "state": None, "gate": "blocked_gate_not_confirmed_true",
        })
        seen_by_dynamic_surface = False
        diagnostics.append({
            "step": "control_member", "member": control_name,
            "message": "ausente do dir() e portao 'has_%s' nao confirmado True -- "
                      "hasattr() controlado NAO tentado (AGENTS.md regra 13)." % gate_name,
        })

    if control_name in records_by_name:
        record = records_by_name[control_name]
        record["hasattr_checked"] = (not control_seen_by_dir) and gate_confirmed_true
        record["hasattr_result"] = seen_by_dynamic_surface if not control_seen_by_dir else None
        record["invoked"] = False  # so PRESENCA e sondada -- nunca o valor/documento
        record["reason_not_invoked"] = "control only"

    # seen_by_clr_reflection NAO e calculado aqui -- este helper nao tem o
    # conjunto de nomes da reflexao CLR; o chamador computa isso a partir de
    # clr_member_names.
    return seen_by_dynamic_surface


def _run_control_gates(proxy, dynamic_dir_names, records_by_name, diagnostics):
    """Executa os 2 pares de portao (declaracao/implementacao). Retorna
    (whitelist_results, seen_by_dynamic_surface_by_name) -- o segundo so
    tem entradas para 'textual_declaration'/'textual_implementation'."""
    whitelist_results = []
    seen_by_dynamic_surface_by_name = {}
    for gate_name, control_name in CONTROL_GATE_PAIRS:
        seen = _check_control_gate_pair(
            proxy, gate_name, control_name, dynamic_dir_names, records_by_name,
            whitelist_results, diagnostics)
        seen_by_dynamic_surface_by_name[control_name] = seen
    return whitelist_results, seen_by_dynamic_surface_by_name


def _run_safe_getter_whitelist(proxy, dynamic_dir_names, records_by_name,
                               whitelist_results, diagnostics):
    """Sonda cada nome de SAFE_GETTER_WHITELIST via hasattr() controlado
    (capabilities.probe_member com capture_value=True -- um unico getattr
    ja serve como o hasattr() controlado E como a invocacao do getter,
    exatamente o padrao 'testar hasattr() apenas contra whitelist' seguido
    de 'invocar somente getters ja aprovados no probe 16'). Guarda
    FORBIDDEN_GETTER_NAME_TERMS aplicada ANTES de qualquer invocacao, mesmo
    que nenhum nome desta whitelist contenha atualmente um termo proibido
    (defesa em profundidade, mesma filosofia do probe 16). Retorna a lista
    de safe-getter-results.json."""
    safe_getter_results = []
    for name in SAFE_GETTER_WHITELIST:
        if _is_forbidden_getter_name(name):
            diagnostics.append({
                "step": "safe_getter_whitelist", "member": name,
                "message": "nome contem termo proibido -- NUNCA invocado.",
            })
            continue

        record = capabilities.probe_member(
            proxy, "ladder_target", name, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
            capture_value=True)
        whitelist_results.append({
            "name": name,
            "hasattr_checked": True,
            "hasattr_result": record["state"] == "confirmed",
            "state": record["state"],
            "gate": None,
        })

        representation = None
        if record["state"] == "confirmed" and "raw_value" in record:
            value = record["raw_value"]
            python_type = capabilities.python_type_info(value)
            dotnet_type = capabilities.dotnet_type_info(value)
            representation = capabilities.build_representation(value, python_type, dotnet_type)

        safe_getter_results.append({
            "member": name,
            "state": record["state"],
            "exception_type": record.get("exception_type"),
            "exception_message": record.get("exception_message"),
            "representation": representation,
        })

        if name in records_by_name:
            entry = records_by_name[name]
            entry["hasattr_checked"] = True
            entry["hasattr_result"] = record["state"] == "confirmed"
            entry["invoked"] = record["state"] == "confirmed"
            entry["reason_not_invoked"] = None if record["state"] == "confirmed" else (
                "hasattr controlado nao confirmou presenca (state=%s)" % record["state"])

        diagnostics.append({
            "step": "safe_getter_whitelist", "member": name, "message": "state=%s" % record["state"],
        })
    return safe_getter_results


def _is_forbidden_getter_name(name):
    lowered = (name or "").lower()
    return any(term in lowered for term in FORBIDDEN_GETTER_NAME_TERMS)


# =============================================================================
# Orquestracao + escrita de artefatos.
# =============================================================================

def _build_report_markdown(result, target_identity, control_validation, candidates,
                           safe_getter_results, dynamic_only_members, shared_members):
    lines = [
        "# Sondagem de superficie DINAMICA do objeto Ladder -- probe_ladder_dynamic_surface",
        "",
        "Fase L1 (docs/14-ladder-roadmap.md), IRMAO do probe 16. Modo: **somente "
        "leitura**. Nenhum parser Ladder; nenhuma leitura de `.text` de "
        "declaracao/implementacao.",
        "",
        "- target_node_id: `%s`" % result.get("target_node_id"),
        "- abortado: **%s**" % result.get("aborted"),
        "- motivo do aborto: %s" % result.get("abort_reason"),
        "- identidade do alvo confirmada: **%s**" % result.get("target_identity_confirmed"),
        "- resultado (A/B/C/D): **%s**" % result.get("result_case"),
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

    if control_validation is not None:
        lines.append("## Validacao do controle dinamico (`%s`)" % control_validation["control_member"])
        lines.append("- visto pela superficie dinamica: **%s**"
                     % control_validation["seen_by_dynamic_surface"])
        lines.append("- visto pela reflexao CLR: **%s**" % control_validation["seen_by_clr_reflection"])
        lines.append("- probe dinamico validado: **%s**" % control_validation["dynamic_probe_validated"])
        lines.append("")
        if not control_validation["dynamic_probe_validated"]:
            lines.append(
                "**ATENCAO**: o controle `%s` NAO foi confirmado pela superficie "
                "dinamica nesta execucao. Este resultado e **INCONCLUSIVO** -- "
                "NENHUMA conclusao sobre a existencia ou ausencia de uma API "
                "Ladder e permitida a partir deste probe. Isso NAO reabilita a "
                "leitura de conclusoes do probe 16 (que ja era, por si so, "
                "inconclusivo quanto a superficie dinamica)."
                % control_validation["control_member"])
            lines.append("")

    lines.append("## Membros so na superficie dinamica (dynamic_only, %d)" % len(dynamic_only_members))
    for member in dynamic_only_members[:200]:
        lines.append("- `%s` classification=%s" % (member["name"], member["classification"]))
    lines.append("")
    lines.append("## Membros compartilhados (dir() e reflexao CLR, %d)" % len(shared_members))
    for member in shared_members[:200]:
        lines.append("- `%s` classification=%s" % (member["name"], member["classification"]))
    lines.append("")
    if result.get("result_case") == "D":
        lines.append("## ATENCAO -- canal de descoberta indisponivel (caso D)")
        lines.append("")
        lines.append(
            "O acesso dinamico por nome CONHECIDO foi comprovado: o controle "
            "`%s` respondeu positivamente e esta ausente da reflexao CLR. "
            "Porem o proxy NAO forneceu canal de enumeracao de membros "
            "(`dir()` sem nomes)." % CONTROL_MEMBER)
        lines.append("")
        lines.append(
            "**Nenhuma conclusao pode ser feita sobre a existencia ou ausencia "
            "de acessores Ladder nao conhecidos previamente.** O "
            "`ladder_candidate_count` abaixo e derivado da enumeracao, que "
            "esta vazia -- ele NAO mede ausencia. Os nomes da whitelist "
            "testados sao hipoteses; a ausencia deles nada diz sobre nomes "
            "que nao foram adivinhados.")
        lines.append("")
    elif result.get("result_case") == "B":
        lines.append("## Conclusao (caso B) -- limitada ao canal enumerado")
        lines.append("")
        lines.append(
            "Nenhum candidato Ladder foi encontrado no canal dinamico "
            "enumerado (%d nome(s)). Isto NAO afirma ausencia global de API "
            "Ladder -- apenas que a superficie enumeravel nao apresentou "
            "membros candidatos." % result.get("dynamic_dir_member_count", 0))
        lines.append("")

    lines.append("## Candidatos a representacao Ladder (%d)" % len(candidates))
    for candidate in candidates[:200]:
        lines.append("- `%s` (nao invocado: %s)" % (candidate["name"], candidate["reason_not_invoked"]))
    lines.append("")
    lines.append("## Getters seguros invocados (%d)" % len(safe_getter_results))
    for getter_result in safe_getter_results:
        lines.append("- `%s`: state=%s" % (getter_result["member"], getter_result["state"]))
    lines.append("")
    return "\n".join(lines) + "\n"


def _write_artifacts(output_dir, result, diagnostics, target_identity, clr_members,
                     dynamic_dir_members, dynamic_only_members, shared_members,
                     whitelist_hasattr_results, safe_getter_results, candidates,
                     control_validation):
    file_io.ensure_dir(output_dir)

    manifest = {
        "schema_version": "1.0",
        "script": "probes/17_probe_ladder_dynamic_surface.py",
        "generated_at": result["generated_at"],
        "mode": "read_only",
        "target_node_id": result["target_node_id"],
        "aborted": result["aborted"],
        "abort_reason": result["abort_reason"],
        "target_identity_confirmed": result["target_identity_confirmed"],
        "dynamic_probe_validated": result["dynamic_probe_validated"],
        # Acesso por nome e enumeracao de nomes sao capacidades distintas --
        # ver o bloco de classificacao. Sem esta separacao um
        # ladder_candidate_count=0 vindo de uma enumeracao vazia se parece
        # com evidencia de ausencia.
        "dynamic_named_access_validated": result["dynamic_named_access_validated"],
        "dynamic_enumeration_available": result["dynamic_enumeration_available"],
        "candidate_search_exhaustive": result["candidate_search_exhaustive"],
        "ladder_candidate_count": result["ladder_candidate_count"],
        "result_case": result["result_case"],
        "status": result["status"],
        "dynamic_dir_member_count": result["dynamic_dir_member_count"],
        "clr_member_count": result["clr_member_count"],
        "dynamic_only_member_count": result["dynamic_only_member_count"],
        "shared_member_count": result["shared_member_count"],
        "safe_getter_invocations": result["safe_getter_invocations"],
    }
    file_io.write_json(os.path.join(output_dir, "manifest.json"), manifest)
    file_io.write_json(os.path.join(output_dir, "target-identity.json"),
                       target_identity if target_identity is not None else {})
    file_io.write_json(os.path.join(output_dir, "clr-members.json"), clr_members)
    file_io.write_json(os.path.join(output_dir, "dynamic-dir-members.json"), dynamic_dir_members)
    file_io.write_json(os.path.join(output_dir, "dynamic-only-members.json"), dynamic_only_members)
    file_io.write_json(os.path.join(output_dir, "shared-members.json"), shared_members)
    file_io.write_json(os.path.join(output_dir, "whitelist-hasattr-results.json"),
                       whitelist_hasattr_results)
    file_io.write_json(os.path.join(output_dir, "safe-getter-results.json"), safe_getter_results)
    file_io.write_json(os.path.join(output_dir, "ladder-candidate-members.json"), candidates)
    file_io.write_json(os.path.join(output_dir, "control-validation.json"),
                       control_validation if control_validation is not None else {
                           "control_member": CONTROL_MEMBER,
                           "seen_by_dynamic_surface": False,
                           "seen_by_clr_reflection": False,
                           "dynamic_probe_validated": False,
                       })

    md = _build_report_markdown(
        result, target_identity, control_validation, candidates, safe_getter_results,
        dynamic_only_members, shared_members)
    # Os quatro artefatos comuns (diagnostics, safety-declaration, report,
    # checksums) saem por `common.artifacts`, na ordem contratual e com
    # checksums por ultimo. O que e especifico deste probe continua acima.
    artifacts.write_common_artifacts(
        output_dir, diagnostics, dict(SAFETY_DECLARATION), md)

    result["artifacts_dir"] = output_dir
    return result


def _empty_write(output_dir, result, diagnostics):
    return _write_artifacts(
        output_dir, result, diagnostics, None, [], [], [], [], [], [], [], None)


def probe_ladder_dynamic_surface(application, ladder_probe_config, output_dir):
    """Ponto de entrada publico. `application` ja deve estar resolvida pelo
    chamador (mesmo padrao de common/). `ladder_probe_config` e o mesmo
    formato de dict usado pelo probe 16 (4 chaves obrigatorias). `output_dir`
    e o diretorio onde os artefatos desta sondagem sao gravados diretamente.

    Nunca lanca excecao: qualquer falha de navegacao/identidade/reflection
    e capturada e reportada via diagnostics.json + result['abort_reason'].
    Sempre grava os artefatos obrigatorios (mesmo em caso de aborto)."""
    diagnostics = []
    result = {
        "schema_version": "1.0",
        "generated_at": file_io.iso_now(),
        "aborted": False,
        "abort_reason": None,
        "target_node_id": None,
        "target_identity_confirmed": False,
        "dynamic_probe_validated": False,
        # Estado inicial/abortado: NADA foi comprovado. Os tres precisam
        # existir aqui porque o manifest e escrito tambem no caminho de
        # abort -- um KeyError ali transformaria uma recusa limpa (identidade
        # divergente, config invalida) numa excecao dentro do MasterTool.
        "dynamic_named_access_validated": False,
        "dynamic_enumeration_available": False,
        "candidate_search_exhaustive": False,
        "ladder_candidate_count": 0,
        "result_case": "C",
        "status": "inconclusive",
        "dynamic_dir_member_count": 0,
        "clr_member_count": 0,
        "dynamic_only_member_count": 0,
        "shared_member_count": 0,
        "safe_getter_invocations": 0,
    }

    # Passo 0: mesma defesa em profundidade do probe 16 -- este probe NAO
    # confia cegamente no formato de ladder_probe_config.
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
    # -> is_folder == false. SO ENTAO sondar a superficie dinamica.
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
            "message": "divergencia(s) de identidade -- abortando SEM sondar dir()/reflexao/"
                      "getters/controles: %s" % mismatches,
        })
        return _write_artifacts(
            output_dir, result, diagnostics, target_identity_doc, [], [], [], [], [], [], [], None)

    result["target_identity_confirmed"] = True
    diagnostics.append({
        "step": "identity_check",
        "message": "identidade confirmada (name/object_guid/type_guid/is_folder) -- prosseguindo.",
    })

    # A partir daqui: enumeracao com dir() -> reflexao CLR -> classificacao
    # -> whitelist hasattr() -> getters seguros ja aprovados (ordem fixa do
    # contrato desta fatia).
    dynamic_dir_names, dir_note = capabilities.diagnostic_dir(proxy)
    diagnostics.append({"step": "diagnostic_dir", "message": dir_note})

    clr_members = _reflect_clr_members(proxy, diagnostics)
    clr_member_names = set(m["member"] for m in clr_members)

    dynamic_dir_member_records = _build_dynamic_member_records(dynamic_dir_names, clr_member_names)
    records_by_name = dict((r["name"], r) for r in dynamic_dir_member_records)

    whitelist_hasattr_results, gate_seen_by_dynamic_surface = _run_control_gates(
        proxy, dynamic_dir_names, records_by_name, diagnostics)

    safe_getter_results = _run_safe_getter_whitelist(
        proxy, dynamic_dir_names, records_by_name, whitelist_hasattr_results, diagnostics)

    # Reconstroi a lista final (dict -> list) preservando a ordem original de
    # dir() -- os records ja foram atualizados IN PLACE pelas duas fases
    # acima, para os nomes que passaram pela whitelist.
    dynamic_dir_member_records = [records_by_name[name] for name in dynamic_dir_names]

    dynamic_only_members = [r for r in dynamic_dir_member_records if not r["seen_by_clr_reflection"]]
    shared_members = [r for r in dynamic_dir_member_records if r["seen_by_clr_reflection"]]

    candidates = [r for r in dynamic_dir_member_records
                 if r["classification"] == "candidate_ladder_representation"]

    # Criterio de validade (contrato: "o coracao do probe"). O controle
    # 'textual_declaration' e visto pela superficie dinamica se (a) apareceu
    # em dir() OU (b) respondeu positivamente ao hasattr() controlado
    # (gated); e NAO deve estar no conjunto da reflexao CLR.
    control_seen_by_dynamic_surface = gate_seen_by_dynamic_surface.get(CONTROL_MEMBER, False)
    control_seen_by_clr_reflection = CONTROL_MEMBER in clr_member_names
    dynamic_probe_validated = (
        control_seen_by_dynamic_surface and not control_seen_by_clr_reflection)

    control_validation = {
        "control_member": CONTROL_MEMBER,
        "seen_by_dynamic_surface": control_seen_by_dynamic_surface,
        "seen_by_clr_reflection": control_seen_by_clr_reflection,
        "dynamic_probe_validated": dynamic_probe_validated,
    }

    # ACESSO POR NOME e ENUMERACAO DE NOMES sao capacidades distintas e NAO
    # podem compartilhar o mesmo gate. A primeira execucao real provou por
    # que: o controle 'textual_declaration' foi confirmado por hasattr()
    # (acesso funciona) enquanto dir() devolveu lista VAZIA (enumeracao nao
    # funciona). Com um gate unico isso virou "caso B: evidencia forte de que
    # a superficie dinamica nao expoe Ladder" -- conclusao que os dados nao
    # sustentam, porque `ladder_candidate_count` e derivado da lista do dir().
    # Zero candidatos vindos de zero nomes enumerados nao e evidencia de
    # ausencia; e ausencia de enumeracao. Era o mesmo erro do probe 16 (usar
    # um metodo cego para afirmar inexistencia), reproduzido um nivel acima.
    dynamic_named_access_validated = dynamic_probe_validated

    # `diagnostic_dir` devolve [] nos tres casos que impedem enumeracao
    # (lista vazia, excecao, retorno nao-enumeravel) e distingue qual foi
    # na nota -- ja registrada em diagnostics. Para a classificacao os tres
    # sao equivalentes: nao houve universo de candidatos.
    dynamic_enumeration_available = len(dynamic_dir_names) > 0

    # So faz sentido chamar a busca de exaustiva se houve o que buscar.
    candidate_search_exhaustive = dynamic_enumeration_available

    result["dynamic_probe_validated"] = dynamic_probe_validated
    result["dynamic_named_access_validated"] = dynamic_named_access_validated
    result["dynamic_enumeration_available"] = dynamic_enumeration_available
    result["candidate_search_exhaustive"] = candidate_search_exhaustive
    result["ladder_candidate_count"] = len(candidates)
    result["dynamic_dir_member_count"] = len(dynamic_dir_names)
    result["clr_member_count"] = len(clr_member_names)
    result["dynamic_only_member_count"] = len(dynamic_only_members)
    result["shared_member_count"] = len(shared_members)
    result["safe_getter_invocations"] = len(safe_getter_results)

    result_case, status, verdict_message = classify_dynamic_probe_result(
        dynamic_named_access_validated, dynamic_enumeration_available,
        len(candidates), len(dynamic_dir_names), len(safe_getter_results))
    result["result_case"] = result_case
    result["status"] = status
    diagnostics.append({"step": "verdict", "message": verdict_message})
    return _write_artifacts(
        output_dir, result, diagnostics, target_identity_doc, clr_members,
        dynamic_dir_member_records, dynamic_only_members, shared_members,
        whitelist_hasattr_results, safe_getter_results, candidates, control_validation)


# =============================================================================
# Execucao standalone (--runscript), mesmo padrao de
# probes/16_probe_ladder_object_surface.py.
# =============================================================================

def main():
    print("=" * 60)
    print("[INFO] probes/17_probe_ladder_dynamic_surface.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. Fase L1 -- sondagem de superficie")
    print("[INFO] DINAMICA (dir() + hasattr() controlado) do objeto POU-alvo,")
    print("[INFO] complementar a reflexao pura do probe 16.")
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

    run_dir = file_io.new_export_dir(EXPORT_ROOT, "17_probe_ladder_dynamic_surface")
    result = probe_ladder_dynamic_surface(application, ladder_probe_config, run_dir)

    if result["aborted"]:
        print("[BLOQUEADO] abort_reason=%s" % result["abort_reason"])
    else:
        print("[OK] identidade confirmada; result_case=%s dynamic_probe_validated=%s "
             "ladder_candidate_count=%s"
             % (result["result_case"], result["dynamic_probe_validated"],
                result["ladder_candidate_count"]))
    print("[OK] Artefatos gravados em: %s" % run_dir)
    print("=" * 60)


main()

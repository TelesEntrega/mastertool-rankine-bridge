# -*- coding: utf-8 -*-
"""Registro de capacidades confirmadas do ScriptEngine.

Motivo de existir (2026-07-23): o smoke test confirmou que `projects.primary`
e um proxy dinamico (tipo .NET real: `ExtendedObject[IScriptProject]`) cujo
`dir()` retorna lista VAZIA, mesmo com `getattr(obj, "path")` funcionando
normalmente. Ou seja, `dir()` NAO e uma fonte de verdade confiavel neste
ambiente para decidir se um membro existe.

Este modulo formaliza tres estados por sondagem explicita (nunca por
enumeracao):

    confirmed    getattr(obj, nome) teve sucesso
    unsupported  getattr falhou de forma compativel com "membro inexistente"
                 (ex.: AttributeError)
    unknown      dir() vazio, ou falha ambigua que nao prova ausencia

Um `dir()` vazio NUNCA vira "unsupported": vira apenas uma nota diagnostica,
nunca decide nada. A fonte de verdade e a whitelist explicita
CAPABILITY_PROBES, testada nome a nome.

Ver docs/api/mastertool-api-observations.md ("Achado importante") e
docs/03-scripting-discovery.md para o registro do achado que motivou isto.
"""
from __future__ import print_function

import time

from common import compatibility

# --- estados de uma sondagem -------------------------------------------------
STATE_CONFIRMED = "confirmed"
STATE_UNSUPPORTED = "unsupported"
STATE_UNKNOWN = "unknown"

# --- origem da evidencia (por que confiamos ou nao num dado) ----------------
EVIDENCE_RUNTIME_CONFIRMED = "runtime_confirmed"
EVIDENCE_STATIC_METADATA = "static_metadata"
EVIDENCE_OFFICIAL_API_DUMP = "official_api_dump"
EVIDENCE_DOCUMENTATION = "documentation"
EVIDENCE_UNVERIFIED = "unverified"

# Whitelist estrita de membros AUTORIZADOS a sondar, por objeto conhecido.
# Cada entrada e um CANDIDATO a testar, nao uma afirmacao de que existe.
# So adicione aqui apos registrar a evidencia correspondente em
# docs/api/mastertool-api-observations.md.
CAPABILITY_PROBES = {
    "projects": ["primary"],
    # "is_root"/"handle" promovidos em 2026-07-23 apos confirmacao em runtime
    # via scripts/mastertool/probes/03_project_navigation.py.
    # "active_application" promovido em 2026-07-23 apos confirmacao em
    # runtime via scripts/mastertool/probes/04_project_identity.py — "type" e
    # "guid" NAO foram promovidos (deram unsupported: pertencem a
    # IScriptObject, nao a IScriptProject). Ver
    # docs/api/mastertool-api-observations.md.
    "project": ["path", "is_root", "handle", "active_application"],
    "system": [],
}

# Nomes de excecao compativeis com "membro inexistente". Mantido como lista
# explicita e curta: nao presumimos alem do que foi observado (o smoke test
# so confirmou este caso via AttributeError padrao do Python/IronPython).
_UNSUPPORTED_EXCEPTION_NAMES = ("AttributeError",)


def _exception_type_name(exc):
    try:
        return type(exc).__name__
    except Exception:
        return "<tipo de excecao indisponivel>"


def probe_member(obj, obj_label, member_name, evidence_source, capture_value=False):
    """Sondagem explicita e guardada de UM membro, por nome, via getattr.

    Nunca lanca excecao. Retorna um dict com: objeto de origem, nome
    solicitado, tipo .NET do objeto, metodo de acesso usado, sucesso/falha,
    tipo do valor retornado, excecao completa (tipo/mensagem/traceback),
    origem da evidencia e duracao em ms. Se `capture_value=True` (default
    False, para nao mudar comportamento de chamadores existentes), o valor
    bruto retornado fica em `record["raw_value"]` — util para o chamador
    inspecionar mais (ex.: GetType().FullName) SEM um segundo getattr.
    """
    record = {
        "source_object": obj_label,
        "member": member_name,
        "dotnet_type": compatibility.safe_type_name(obj),
        "access_method": "getattr",
        "success": False,
        "state": STATE_UNKNOWN,
        "value_type": None,
        "exception_type": None,
        "exception_message": None,
        "traceback": None,
        "evidence_source": evidence_source,
        "duration_ms": None,
    }
    t0 = time.time()
    try:
        value = getattr(obj, member_name)
        record["success"] = True
        record["state"] = STATE_CONFIRMED
        record["value_type"] = compatibility.safe_type_name(value)
        if capture_value:
            record["raw_value"] = value
    except Exception as exc:
        record["exception_type"] = _exception_type_name(exc)
        record["exception_message"] = compatibility.safe_repr(exc)
        try:
            import traceback as _tb
            record["traceback"] = _tb.format_exc()
        except Exception:
            record["traceback"] = "<traceback indisponivel>"
        if record["exception_type"] in _UNSUPPORTED_EXCEPTION_NAMES:
            record["state"] = STATE_UNSUPPORTED
        else:
            # Excecao ambigua (ex.: erro interno do proxy, nao "atributo
            # inexistente"): NAO concluimos ausencia. Fica 'unknown'.
            record["state"] = STATE_UNKNOWN
    record["duration_ms"] = int((time.time() - t0) * 1000)
    return record


def probe_method_call(obj, obj_label, member_name, call_args, evidence_source,
                      capture_value=False):
    """Sondagem explicita de UMA chamada de metodo com argumentos FIXOS, uma
    unica vez. Mesma classificacao tri-state de probe_member (confirmed/
    unsupported/unknown), mas para chamadas com argumentos (nao so leitura
    de propriedade via getattr). Nunca lanca excecao; nunca tenta uma
    segunda combinacao de argumentos.
    """
    record = {
        "source_object": obj_label,
        "member": member_name,
        "call_args": list(call_args),
        "dotnet_type": compatibility.safe_type_name(obj),
        "access_method": "method_call",
        "success": False,
        "state": STATE_UNKNOWN,
        "value_type": None,
        "exception_type": None,
        "exception_message": None,
        "traceback": None,
        "evidence_source": evidence_source,
        "duration_ms": None,
    }
    t0 = time.time()
    try:
        method = getattr(obj, member_name)
        value = method(*call_args)
        record["success"] = True
        record["state"] = STATE_CONFIRMED
        record["value_type"] = compatibility.safe_type_name(value)
        if capture_value:
            record["raw_value"] = value
    except Exception as exc:
        record["exception_type"] = _exception_type_name(exc)
        record["exception_message"] = compatibility.safe_repr(exc)
        try:
            import traceback as _tb
            record["traceback"] = _tb.format_exc()
        except Exception:
            record["traceback"] = "<traceback indisponivel>"
        if record["exception_type"] in _UNSUPPORTED_EXCEPTION_NAMES:
            record["state"] = STATE_UNSUPPORTED
        else:
            record["state"] = STATE_UNKNOWN
    record["duration_ms"] = int((time.time() - t0) * 1000)
    return record


def probe_indexer_access(obj, obj_label, index, evidence_source, capture_value=False):
    """Sondagem explicita de UM acesso por indice (obj[index]), uma unica
    vez, via o indexador NATIVO do Python/IronPython — nunca `.Item[index]`/
    `.get_Item(index)`/`ElementAt(index)`. Mesma classificacao tri-state.
    """
    record = {
        "source_object": obj_label,
        "index": index,
        "dotnet_type": compatibility.safe_type_name(obj),
        "access_method": "indexer",
        "success": False,
        "state": STATE_UNKNOWN,
        "value_type": None,
        "exception_type": None,
        "exception_message": None,
        "traceback": None,
        "evidence_source": evidence_source,
        "duration_ms": None,
    }
    t0 = time.time()
    try:
        value = obj[index]
        record["success"] = True
        record["state"] = STATE_CONFIRMED
        record["value_type"] = compatibility.safe_type_name(value)
        if capture_value:
            record["raw_value"] = value
    except Exception as exc:
        record["exception_type"] = _exception_type_name(exc)
        record["exception_message"] = compatibility.safe_repr(exc)
        try:
            import traceback as _tb
            record["traceback"] = _tb.format_exc()
        except Exception:
            record["traceback"] = "<traceback indisponivel>"
        if record["exception_type"] in _UNSUPPORTED_EXCEPTION_NAMES:
            record["state"] = STATE_UNSUPPORTED
        else:
            record["state"] = STATE_UNKNOWN
    record["duration_ms"] = int((time.time() - t0) * 1000)
    return record


def probe_known_members(obj, obj_label, evidence_source):
    """Sonda todos os membros da whitelist CAPABILITY_PROBES[obj_label].

    Se obj_label nao estiver registrado, retorna lista vazia (nunca tenta
    adivinhar nomes fora da whitelist).
    """
    names = CAPABILITY_PROBES.get(obj_label, [])
    return [probe_member(obj, obj_label, name, evidence_source) for name in names]


def diagnostic_dir(obj):
    """dir() como DIAGNOSTICO apenas — NUNCA como fonte de verdade.

    Retorna (lista_de_nomes, nota). Lista vazia significa "introspeccao
    generica indisponivel para este objeto neste host", NAO "objeto sem
    membros" — ver motivo no topo deste modulo.
    """
    try:
        names = sorted([m for m in dir(obj) if not m.startswith("_")])
    except Exception as exc:
        return [], "dir() falhou: %s" % compatibility.safe_repr(exc)
    if not names:
        return [], ("dir() vazio - NAO significa ausencia de membros; pode "
                    "ser um proxy dinamico do DLR (ver "
                    "docs/api/mastertool-api-observations.md).")
    return names, "dir() retornou %d membro(s) publico(s)." % len(names)


def probe_object(obj, obj_label, evidence_source):
    """Sondagem completa de um objeto conhecido: membros da whitelist (fonte
    de verdade) + dir() somente como diagnostico (nao autoritativo).
    """
    members, dir_note = diagnostic_dir(obj)
    return {
        "object_label": obj_label,
        "dotnet_type": compatibility.safe_type_name(obj),
        "known_members": probe_known_members(obj, obj_label, evidence_source),
        "diagnostic_dir": {
            "members": members,
            "note": dir_note,
            "authoritative": False,
        },
    }


# --- Politica de serializacao ESTRITA (2026-07-23) --------------------------
# Motivo: uma execucao real usou repr()/str() para "representacao segura" de
# um objeto retornado; em IronPython isso tipicamente invoca ToString() no
# objeto .NET — uma CHAMADA DE METODO na instancia, fora do escopo aprovado
# quando a regra e "nao chamar metodos no objeto retornado". ToString() e so
# convencao (nao garantia tecnica): uma classe pode sobrescreve-lo com
# qualquer efeito. Corrigido: nunca mais repr()/str()/ToString()/formatacao
# implicita em objetos CLR desconhecidos. So serializamos o VALOR quando e
# primitivo Python nativo, ou um tipo .NET CONFIRMADO como seguro (value
# types selados da BCL, ToString() documentado e nao sobrescrevivel).
# Ver docs/api/mastertool-api-observations.md e
# workspace/logs/2026-07-23_11-34-20_04_probe_project_identity/POLICY-DEVIATION-NOTE.md

KNOWN_SAFE_DOTNET_TYPES = frozenset([
    "System.String", "System.Guid", "System.Boolean",
    "System.Int16", "System.Int32", "System.Int64",
    "System.Single", "System.Double",
])

# Strings nativas do interpretador: no IronPython 2.7, um System.String pode
# chegar como `str` OU `unicode` dependendo do binder — `basestring` cobre
# ambos. Em CPython 3 (camada externa/testes) so existe `str`. NUNCA depende
# de GetType() para reconhecer isso — sao tipos Python nativos, ja seguros
# por construcao (2026-07-23, correcao: a versao anterior so checava `str`,
# perdendo `unicode`, o que fazia `get_name(False)` cair em 'type_only'
# mesmo com o valor real disponivel — ver mastertool-api-observations.md).
try:
    _STRING_TYPES = (basestring,)  # noqa: F821  (Python 2 / IronPython 2.7)
except NameError:
    _STRING_TYPES = (str,)  # Python 3


def python_type_info(value):
    try:
        t = type(value)
        return {"module": getattr(t, "__module__", None), "name": getattr(t, "__name__", None)}
    except Exception:
        return {"module": None, "name": None}


def dotnet_type_info(value):
    """Tenta GetType() diretamente (try/except puro) — NUNCA via dir()/
    hasattr para decidir se o metodo existe. Chamador deve so invocar apos o
    getattr do MEMBRO ja ter tido sucesso (state == confirmed)."""
    try:
        clr_type = value.GetType()
        return {"full_name": clr_type.FullName, "available": True}
    except Exception:
        return {"full_name": None, "available": False}


def strict_object_repr(type_name):
    """Representacao SEM tocar a instancia: monta a string so a partir do
    NOME DO TIPO ja capturado via GetType() (nao via repr/str/ToString)."""
    if not type_name:
        return "<unknown-object>"
    return "<%s>" % type_name


def _safe_value_result(mode, value, stringification_performed, value_available,
                       serialization_mode):
    """Monta o dict de retorno de build_representation com TODOS os campos:
    'mode'/'value'/'instance_stringification_performed' (campos originais,
    mantidos por compatibilidade) e 'value_available'/'serialization_mode'
    (campo principal 'value' + proveniencia, 2026-07-23)."""
    return {
        "mode": mode,
        "value": value,
        "instance_stringification_performed": stringification_performed,
        "value_available": value_available,
        "serialization_mode": serialization_mode,
    }


def build_representation(value, python_type, dotnet_type):
    """Serializacao ESTRITA: NUNCA chama repr(value)/str(value)/
    value.ToString()/formatacao implicita em objetos CLR desconhecidos. So
    serializa o VALOR em si quando e primitivo Python nativo (None/bool/int/
    long/float/string — string cobre `str` E `unicode` no IronPython 2.7,
    via `_STRING_TYPES`, SEM depender de GetType()) ou tipo .NET CONFIRMADO
    seguro (KNOWN_SAFE_DOTNET_TYPES). Qualquer outra coisa vira representacao
    'type_only', montada so do nome do tipo.

    `python_type`/`dotnet_type`: dicts ja produzidos por python_type_info()/
    dotnet_type_info() para este mesmo `value` (nao recalculados aqui).

    Retorno inclui tanto os campos originais ('mode'/'value'/
    'instance_stringification_performed') quanto os de conveniencia
    ('value_available'/'serialization_mode') — mesma informacao, duas formas
    de consulta, para nao quebrar chamadores existentes.
    """
    dotnet_full_name = dotnet_type.get("full_name")

    if value is None:
        return _safe_value_result("value", None, False, True, "none")

    if isinstance(value, bool):
        # bool e subclasse de int em Python — checar ANTES de int/long.
        return _safe_value_result("value", value, False, True, "native_bool")

    try:
        # 'long' so existe em Python 2 (IronPython 2.7); em Python 3 (testes
        # externos) isinstance(value, int) ja cobre tudo.
        is_int_like = isinstance(value, (int, long))  # noqa: F821
    except NameError:
        is_int_like = isinstance(value, int)
    if is_int_like:
        return _safe_value_result("value", value, False, True, "native_int")
    if isinstance(value, float):
        return _safe_value_result("value", value, False, True, "native_float")

    if isinstance(value, _STRING_TYPES):
        # ja e uma string nativa (str OU unicode) — o proprio valor JA E a
        # representacao, sem chamar nada na instancia. NUNCA depende de
        # GetType(): primitivos nativos do IronPython nem sempre respondem
        # a GetType() de forma confiavel neste host (ver nota no topo).
        return _safe_value_result("value", value, False, True, "native_string")

    if dotnet_full_name in KNOWN_SAFE_DOTNET_TYPES:
        # Guid/String/numericos: ToString() e formato padronizado da BCL,
        # nao sobrescrevivel com efeito colateral (value types selados). So
        # chega aqui DEPOIS de confirmar o tipo real via GetType() — E so
        # para valores que nao passaram pelos ramos nativos acima (na
        # pratica, um System.String real de dentro do IronPython quase
        # sempre ja e pego pelo ramo native_string; este ramo e uma defesa
        # extra para o caso hipotetico de um wrapper que reporte
        # dotnet_type=System.String sem ser um str/unicode nativo).
        try:
            text = str(value)
            return _safe_value_result("value", text, True, True, "confirmed_dotnet_type")
        except Exception:
            pass  # cai para type_only abaixo

    type_name = dotnet_full_name or python_type.get("name")
    return _safe_value_result(
        "type_only", strict_object_repr(type_name), False, False, "type_only")

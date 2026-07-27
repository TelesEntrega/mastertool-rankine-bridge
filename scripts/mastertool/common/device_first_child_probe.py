# -*- coding: utf-8 -*-
"""Sondagem PURA (sem I/O) do primeiro filho de `Device`, segundo nível da
árvore de `ExemploPlanta V1.0.project`.

Motivo de existir (2026-07-23): depois do probe 09 confirmar em runtime que
`Device.get_children(False)` funciona identicamente à raiz (mesmo tipo
concreto, mesmas interfaces, `Count=2`), o próximo passo aprovado é
identificar SOMENTE o primeiro filho de `Device` (índice 0), sem misturar
com a comparação a `active_application` (fica para outro probe, para nao
dificultar isolar a causa de uma eventual falha).

Esta funcao e PURA: recebe um `project` JA RESOLVIDO e devolve um dict
100% serializavel, sem tocar disco nem gerar relatorio — isso permite
testar toda a logica de seguranca com fakes em memoria
(tests/unit/test_device_first_child_probe.py), assim como
common/project_tree_adapter.py. O script `probes/10_device_first_child_identity.py`
e so um wrapper fino que resolve `projects.primary`, chama esta funcao e
grava o relatorio.

Fluxo obrigatorio (cada passo so ocorre se o anterior foi confirmado):
  1. `project.get_children(False)`, 1 chamada;
  2. `root_children.Count`, 1 leitura, DEVE bater com `expected_root_count`
     (4) — senao aborta (`root_count_mismatch`), sem acessar indice 1;
  3. `root_children[1]` (indexador nativo), 1 acesso;
  4. revalidacao de identidade de Device NESTA execucao (`get_name(False)`,
     `type`, `guid`), cada um 1 vez — qualquer divergencia com os valores
     esperados aborta (`device_identity_mismatch`), SEM chamar
     `device.get_children(False)`;
  5. `device.get_children(False)`, 1 chamada;
  6. colecao nao pode ser nula; deve implementar `ICollection`/`IList`
     (via `GetType().GetInterfaces()`, metadados, nunca dados); `Count`
     deve bater com `expected_device_children_count` (2) — qualquer uma
     destas falhar aborta (`device_children_collection_null`/
     `device_children_count_interface_unconfirmed`/
     `device_children_count_mismatch`), SEM acessar indice 0;
  7. `device_children[0]` (indexador nativo), 1 acesso;
  8. no primeiro filho, 4 probes ISOLADOS de identidade
     (`is_folder`/`type`/`guid`/`get_name(False)`) — falha em UM nao aborta
     os demais.

PROIBIDO por construcao (nenhum call site existe para isto neste modulo):
`device_children[1]`; iteracao de qualquer colecao; `get_children()` no
primeiro filho; `active_application`; `find()`; documentos textuais;
configuracao de hardware; escrita/compilacao/salvamento/modificacao;
qualquer operacao online. `repr()`/`str()`/`.ToString()` NUNCA em objeto
CLR desconhecido — toda serializacao via
`common.capabilities.build_representation()`.

Para os campos `type`/`guid` do PRIMEIRO FILHO (nao para a revalidacao de
Device, que segue o mesmo padrao ja usado no probe 09), o valor so e
serializado quando o tipo .NET foi CONFIRMADO como `System.Guid` via
`GetType()` — restricao explicitamente pedida pelo usuario, mais estrita
que `build_representation()` isolado (que tambem aceitaria outros tipos
confirmados seguros, como String/Boolean/numericos).

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

from common import capabilities, compatibility

DEVICE_INDEX = 1
FIRST_CHILD_INDEX = 0

DEFAULT_EXPECTED_ROOT_COUNT = 4
DEFAULT_EXPECTED_DEVICE_NAME = "Device"
DEFAULT_EXPECTED_DEVICE_TYPE_GUID = "225bfe47-7336-4dbc-9419-4105a7c831fa"
DEFAULT_EXPECTED_DEVICE_OBJECT_GUID = "00000000-0000-0000-0000-000000000208"
DEFAULT_EXPECTED_DEVICE_CHILDREN_COUNT = 2

_COUNT_BEARING_INTERFACE_PREFIXES = ("ICollection", "IList")


def _field_result(state, value=None, error=None):
    return {"state": state, "value": value, "error": error}


def _implements_count_bearing_interface(value):
    """Reflection sobre o TIPO do valor (GetType().GetInterfaces()) — NUNCA
    toca os DADOS/elementos da colecao. Copia local do mesmo helper usado em
    probes/05_children_collection.py e probes/09_device_children_collection.py.
    Retorna (implementa: bool, nomes_interfaces: list, erro: str|None)."""
    try:
        clr_type = value.GetType()
        interfaces = clr_type.GetInterfaces()
        names = []
        for iface in interfaces:
            try:
                names.append(iface.Name)
            except Exception:
                continue
        implements = any(
            any(name.startswith(prefix) for prefix in _COUNT_BEARING_INTERFACE_PREFIXES)
            for name in names)
        return implements, names, None
    except Exception as exc:
        return False, [], repr(exc)


def _probe_property_via_representation(obj, obj_label, member_name):
    """1 getattr isolado + representacao estrita generica (aceita qualquer
    tipo confirmado seguro por build_representation(), incluindo strings
    nativas). Usado para a revalidacao de identidade de Device (mesmo
    padrao ja usado/confirmado em runtime no probe 09)."""
    record = capabilities.probe_member(
        obj, obj_label, member_name, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
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
    """`get_name(False)`, 1 chamada, SEM fallback para `get_name(True)`."""
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
        return _field_result(
            "unrepresentable",
            error="nome obtido, mas sem representacao segura.")
    return _field_result("confirmed", value=rep["value"])


def _probe_guid_confirmed_only(obj, obj_label, member_name):
    """1 getattr isolado — SO aceita o valor quando `dotnet_type.full_name`
    foi CONFIRMADO (via GetType(), nunca por suposicao) como exatamente
    'System.Guid'. Mais estrito que build_representation() isolado (que
    tambem aceitaria String/Boolean/numericos confirmados) — restricao
    explicita pedida pelo usuario para os campos type/guid do PRIMEIRO
    FILHO de Device."""
    record = capabilities.probe_member(
        obj, obj_label, member_name, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if record["state"] != "confirmed" or "raw_value" not in record:
        return _field_result(record["state"], error=record.get("exception_message"))
    value = record["raw_value"]
    dotnet_type = capabilities.dotnet_type_info(value)
    if dotnet_type.get("full_name") != "System.Guid":
        return _field_result(
            "confirmed_not_guid",
            error=("valor obtido com sucesso, mas o tipo .NET nao foi "
                  "confirmado como System.Guid (full_name=%r); valor NAO "
                  "serializado por restricao explicita deste probe."
                  % dotnet_type.get("full_name")))
    python_type = capabilities.python_type_info(value)
    rep = capabilities.build_representation(value, python_type, dotnet_type)
    if not rep["value_available"]:
        return _field_result(
            "unrepresentable",
            error="System.Guid confirmado, mas representacao indisponivel.")
    return _field_result("confirmed", value=rep["value"])


def _bool_field(field_result):
    """`is_folder` deve ser bool; qualquer outro valor vira 'unrepresentable'
    (nao presumimos truthiness de um valor nao-bool)."""
    if field_result["state"] != "confirmed":
        return field_result
    if isinstance(field_result["value"], bool):
        return field_result
    return _field_result(
        "unrepresentable",
        error="valor obtido nao e bool (tipo: %s)." % compatibility.safe_type_name(field_result["value"]))


def probe_device_first_child(
        project,
        expected_root_count=DEFAULT_EXPECTED_ROOT_COUNT,
        expected_device_name=DEFAULT_EXPECTED_DEVICE_NAME,
        expected_device_type_guid=DEFAULT_EXPECTED_DEVICE_TYPE_GUID,
        expected_device_object_guid=DEFAULT_EXPECTED_DEVICE_OBJECT_GUID,
        expected_device_children_count=DEFAULT_EXPECTED_DEVICE_CHILDREN_COUNT):
    """Executa o fluxo completo descrito na docstring do modulo contra um
    `project` JA RESOLVIDO. Nunca lanca excecao; retorna sempre um dict
    100% serializavel. Ver docstring do modulo para a granularidade exata
    de aborto por etapa."""

    result = {
        "root_validation": {
            "get_children_call_count": 0,
            "get_children_state": None,
            "count_state": None,
            "count": None,
            "expected_count": expected_root_count,
            "count_matches_expected": None,
            "device_index": DEVICE_INDEX,
            "element_access_state": None,
            "device_identity": {
                "name": _field_result(None, error=None),
                "type_guid": _field_result(None, error=None),
                "object_guid": _field_result(None, error=None),
            },
            "device_identity_confirmed": False,
        },
        "device_collection": {
            "attempted": False,
            "get_children_call_count": 0,
            "state": None,
            "is_null": None,
            "python_type": {"module": None, "name": None},
            "dotnet_type": {"full_name": None, "available": False},
            "implements_count_bearing_interface": None,
            "type_interfaces_observed": [],
            "count_state": None,
            "count": None,
            "expected_count": expected_device_children_count,
            "count_matches_expected": None,
            "iteration_performed": False,
        },
        "element_access": {
            "attempted": False,
            "index": FIRST_CHILD_INDEX,
            "access_count": 0,
            "state": None,
        },
        "first_child": {
            "is_folder": _field_result(None),
            "type": _field_result(None),
            "guid": _field_result(None),
            "name": _field_result(None),
        },
        "errors": [],
        "complete": False,
    }

    rv = result["root_validation"]

    # --- 1. get_children(False) na RAIZ, EXATAMENTE 1 chamada -------------------
    gc_record = capabilities.probe_method_call(
        project, "project", "get_children", (False,),
        capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
    rv["get_children_call_count"] = 1
    rv["get_children_state"] = gc_record["state"]
    if rv["get_children_state"] != "confirmed" or "raw_value" not in gc_record:
        result["errors"].append({"where": "get_children",
                                 "message": gc_record.get("exception_message")})
        return result
    root_children = gc_record["raw_value"]

    # --- 2. root_children.Count, EXATAMENTE 1 leitura, DEVE bater com
    # expected_root_count ---------------------------------------------------------
    count_record = capabilities.probe_member(
        root_children, "root_children", "Count", capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    rv["count_state"] = count_record["state"]
    if rv["count_state"] == "confirmed" and "raw_value" in count_record:
        raw_count = count_record["raw_value"]
        rv["count"] = (raw_count if isinstance(raw_count, (int, float))
                       and not isinstance(raw_count, bool) else None)

    rv["count_matches_expected"] = (rv["count_state"] == "confirmed"
                                    and rv["count"] == expected_root_count)
    if not rv["count_matches_expected"]:
        result["errors"].append({
            "where": "root_children.Count",
            "message": ("root_count_mismatch: esperado Count == %s, obtido "
                       "state=%s count=%s. Abortando SEM acessar "
                       "root_children[%s]." % (expected_root_count, rv["count_state"],
                                              rv["count"], DEVICE_INDEX)),
        })
        return result

    # --- 3. root_children[1], EXATAMENTE 1 acesso por indice --------------------
    idx_record = capabilities.probe_indexer_access(
        root_children, "root_children", DEVICE_INDEX, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    rv["element_access_state"] = idx_record["state"]
    if rv["element_access_state"] != "confirmed" or "raw_value" not in idx_record:
        result["errors"].append({"where": "root_children[%s]" % DEVICE_INDEX,
                                 "message": idx_record.get("exception_message")})
        return result
    device = idx_record["raw_value"]

    # --- 4. Revalidacao de identidade de Device, 1 leitura/chamada cada ---------
    identity = rv["device_identity"]
    identity["name"] = _probe_name_via_method_call(device, "device")
    identity["name"]["matches_expected"] = (identity["name"]["value"] == expected_device_name)
    identity["type_guid"] = _probe_property_via_representation(device, "device", "type")
    identity["type_guid"]["matches_expected"] = (identity["type_guid"]["value"] == expected_device_type_guid)
    identity["object_guid"] = _probe_property_via_representation(device, "device", "guid")
    identity["object_guid"]["matches_expected"] = (identity["object_guid"]["value"] == expected_device_object_guid)

    rv["device_identity_confirmed"] = (identity["name"]["matches_expected"]
                                       and identity["type_guid"]["matches_expected"]
                                       and identity["object_guid"]["matches_expected"])

    if not rv["device_identity_confirmed"]:
        result["errors"].append({
            "where": "root_children[%s]" % DEVICE_INDEX,
            "message": ("device_identity_mismatch: name/type/guid de "
                       "root_children[%s] nao batem com os valores "
                       "esperados nesta execucao. Abortando SEM chamar "
                       "device.get_children(False)." % DEVICE_INDEX),
        })
        return result

    # --- 5. device.get_children(False), EXATAMENTE 1 chamada — SO com
    # identidade confirmada acima -------------------------------------------------
    dc = result["device_collection"]
    dc["attempted"] = True
    dgc_record = capabilities.probe_method_call(
        device, "device", "get_children", (False,), capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    dc["get_children_call_count"] = 1
    dc["state"] = dgc_record["state"]
    if dc["state"] != "confirmed" or "raw_value" not in dgc_record:
        result["errors"].append({"where": "device.get_children",
                                 "message": dgc_record.get("exception_message")})
        return result
    device_children = dgc_record["raw_value"]

    # --- 6. colecao nao pode ser nula; deve implementar ICollection/IList;
    # Count deve bater com expected_device_children_count -------------------------
    dc["is_null"] = device_children is None
    if dc["is_null"]:
        result["errors"].append({"where": "device.get_children",
                                 "message": "device_children_collection_null: retorno nulo."})
        return result

    dc["python_type"] = capabilities.python_type_info(device_children)
    dc["dotnet_type"] = capabilities.dotnet_type_info(device_children)

    implements, iface_names, iface_err = _implements_count_bearing_interface(device_children)
    dc["implements_count_bearing_interface"] = implements
    dc["type_interfaces_observed"] = iface_names
    if not implements:
        result["errors"].append({
            "where": "device_children",
            "message": ("device_children_count_interface_unconfirmed: tipo "
                       "nao confirmou ICollection/IList via "
                       "GetType().GetInterfaces() (%s). Abortando SEM "
                       "acessar device_children[%s]."
                       % (iface_err, FIRST_CHILD_INDEX)),
        })
        return result

    count_record2 = capabilities.probe_member(
        device_children, "device_children", "Count", capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    dc["count_state"] = count_record2["state"]
    if dc["count_state"] == "confirmed" and "raw_value" in count_record2:
        raw = count_record2["raw_value"]
        dc["count"] = raw if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None

    dc["count_matches_expected"] = (dc["count_state"] == "confirmed"
                                    and dc["count"] == expected_device_children_count)
    if not dc["count_matches_expected"]:
        result["errors"].append({
            "where": "device_children.Count",
            "message": ("device_children_count_mismatch: esperado Count == "
                       "%s, obtido state=%s count=%s. Abortando SEM "
                       "acessar device_children[%s]."
                       % (expected_device_children_count, dc["count_state"],
                          dc["count"], FIRST_CHILD_INDEX)),
        })
        return result

    # --- 7. device_children[0], EXATAMENTE 1 acesso por indice. NUNCA
    # device_children[1] nem qualquer outro indice; NENHUMA iteracao -------------
    ea = result["element_access"]
    ea["attempted"] = True
    ea["access_count"] = 1
    child_idx_record = capabilities.probe_indexer_access(
        device_children, "device_children", FIRST_CHILD_INDEX,
        capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
    ea["state"] = child_idx_record["state"]
    if ea["state"] != "confirmed" or "raw_value" not in child_idx_record:
        result["errors"].append({"where": "device_children[%s]" % FIRST_CHILD_INDEX,
                                 "message": child_idx_record.get("exception_message")})
        return result
    first_child = child_idx_record["raw_value"]

    # --- 8. 4 probes ISOLADOS de identidade no primeiro filho. Falha em UM
    # nao aborta os demais. NUNCA chama get_children() no primeiro filho. --------
    fc = result["first_child"]
    fc["is_folder"] = _bool_field(_probe_property_via_representation(first_child, "first_child", "is_folder"))
    fc["type"] = _probe_guid_confirmed_only(first_child, "first_child", "type")
    fc["guid"] = _probe_guid_confirmed_only(first_child, "first_child", "guid")
    fc["name"] = _probe_name_via_method_call(first_child, "first_child")

    result["complete"] = True
    return result

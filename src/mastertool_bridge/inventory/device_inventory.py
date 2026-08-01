"""Inventário de configuração de dispositivo a partir de exports PLCopen.

Entrada: um ou mais **exports por dispositivo** (`probes/25`), mais a
topologia (`probes/21`). Saída: duas camadas independentes.

Por que duas camadas
--------------------
A camada bruta é o registro; a interpretada é a leitura. Misturá-las faria a
leitura apagar o registro, e um dia alguém precisaria do parâmetro que a
regra da época achou irrelevante. A bruta nunca descarta nada.

Por que o inventário pode ser **composto**
------------------------------------------
Exports de runs diferentes podem vir de estados diferentes do projeto — por
exemplo, quando uma device description é instalada entre uma coleta e outra e
dispositivos que antes falhavam passam a exportar. O resultado então NÃO é um
snapshot único, e chamá-lo assim seria falso. Cada registro carrega o hash do
projeto da sua run, e o manifesto declara `inventory_snapshot_kind`.

Hierarquia de evidência da interpretação
----------------------------------------
1. token semântico explícito no `type` .................... `high`
2. `ParameterId` conhecido **corroborado pelo nome esperado**,
   dentro do contexto de protocolo ......................... `high`
3. nome exato + forma do valor + contexto estrutural ....... `medium`
4. nome isolado ............ **não interpreta**; vira `unresolved`

O contexto de protocolo vem de `DeviceIdentification/Type` e de
`Connector/@interface` — estrutura. **O nome do dispositivo nunca é
evidência.**

Por que o `ParameterId` sozinho não basta
-----------------------------------------
Ids como `0`, `1` e `2` existem em praticamente toda device description. Sem
corroboração pelo nome, um parâmetro de flags chamado `Supported Functions`
(id 0) foi classificado como `ip_address`, e um `Dummy Parameter` (id 1) como
`subnet_mask`. Falso positivo real, observado e corrigido — daí a exigência
do nome esperado.
"""

from __future__ import annotations

import collections
import hashlib
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

INVENTORY_SCHEMA_VERSION = 1

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"

VALUE_PRESENT = "presente"
VALUE_STRUCTURED = "estruturado"
VALUE_EMPTY = "vazio"
VALUE_ABSENT = "ausente"

CTX_ETHERNET_IP = "ethernet_ip"
CTX_MODBUS = "modbus"
CTX_ETHERNET = "ethernet_interface"
CTX_LOCAL = "local_io"

SNAPSHOT_SINGLE = "single"
SNAPSHOT_COMPOSITE = "composite"


# --- vocabulário de regras ---------------------------------------------------

#: Tokens semânticos no atributo `type`. Evidência forte: vêm da device
#: description, não de rótulo de tela, e independem de contexto.
TYPE_TOKENS: tuple[tuple[str, str], ...] = (
    ("unit_id", r"SLAVE_?ADDRESS|UNIT_?ID|STATION_?ADDR"),
    ("tcp_port", r"TCP_PORT|UDP_PORT|IP_PORT"),
    ("timeout", r"TIMEOUT"),
    ("polling_interval", r"TASK_CYCLE"),
    ("connection_mode", r"CLOSE_MODE|MODBUS_PROTOCOL"),
    ("retries", r"SIMULTANEOUS_REQUESTS"),
    ("modbus_request", r"REQUEST_SETTINGS"),
    ("iec_mapping", r"MAPPING_SETTINGS|DATA_LOCATION"),
    ("serial_config", r"TYPE_BAUDRATE|TYPE_PARITY|TYPE_DATABITS|"
                      r"TYPE_STOPBITS|TYPE_SERIAL|TYPE_COM"),
    ("ip_config_mode", r"IPCONFIGMODE"),
    ("signal_type", r"TRANSFERRATE"),
    ("protocol_hint", r"PROTOCOLENUM"),
    ("failsafe", r"FAILSAFE"),
    ("filter", r"INPUTFILTER"),
)

#: `ParameterId` -> (conceito, nome esperado), por contexto de protocolo.
#: O nome esperado é obrigatório: ver docstring do módulo.
PARAMETER_IDS: dict[str, dict[str, tuple[str, str]]] = {
    CTX_ETHERNET_IP: {
        "2000": ("vendor_code", "Vendor Code"),
        "2001": ("device_type_cip", "Product Type"),
        "2002": ("product_code", "Product Code"),
        "2003": ("major_revision", "Major Revision"),
        "2004": ("minor_revision", "Minor Revision"),
        "2005": ("serial_number", "Serial Number"),
        "256": ("ip_address", "IPAddress"),
        "257": ("subnet_mask", "SubnetMask"),
        "258": ("gateway", "GatewayAddress"),
    },
    CTX_ETHERNET: {
        "0": ("ip_address", "IPAddress"),
        "1": ("subnet_mask", "SubnetMask"),
        "2": ("gateway", "GatewayAddress"),
        "100": ("ip_address", "IPAddress"),
        "101": ("subnet_mask", "SubnetMask"),
        "102": ("gateway", "GatewayAddress"),
        "201": ("ip_address", "IPAddress"),
        "202": ("subnet_mask", "SubnetMask"),
        "203": ("gateway", "GatewayAddress"),
    },
}

#: (conceito, regex de nome exato, forma exigida do valor, contextos válidos)
STRUCTURAL_NAMES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("ip_address", r"^IPAddress$|^IP address of Target$", "ip4",
     (CTX_ETHERNET_IP, CTX_ETHERNET)),
    ("subnet_mask", r"^SubnetMask$", "ip4", (CTX_ETHERNET_IP, CTX_ETHERNET)),
    ("gateway", r"^GatewayAddress$", "ip4", (CTX_ETHERNET_IP, CTX_ETHERNET)),
    ("mac_address", r"^MACAddress$", "any", (CTX_ETHERNET_IP, CTX_ETHERNET)),
    ("network_interface", r"^NetworkInterfaceName$", "scalar",
     (CTX_ETHERNET_IP, CTX_ETHERNET)),
    ("tcp_port", r"^Porta TCP$", "scalar", (CTX_MODBUS,)),
    ("polling_interval", r"^Ciclo da Tarefa$|^Task Cycle$", "scalar",
     (CTX_MODBUS,)),
    ("vendor_code", r"^Vendor Code$", "scalar", (CTX_ETHERNET_IP,)),
    ("product_code", r"^Product Code$", "scalar", (CTX_ETHERNET_IP,)),
    ("device_type_cip", r"^Product Type$", "scalar", (CTX_ETHERNET_IP,)),
    ("major_revision", r"^Major Revision$", "scalar", (CTX_ETHERNET_IP,)),
    ("minor_revision", r"^Minor Revision$", "scalar", (CTX_ETHERNET_IP,)),
    ("vendor_name", r"^Vendor Name$|^Vendor$", "scalar", (CTX_ETHERNET_IP,)),
    ("electronic_keying", r"^Keying$", "any", (CTX_ETHERNET_IP,)),
    ("connection_path", r"^Connection Path$", "any", (CTX_ETHERNET_IP,)),
    ("connection_settings", r"^Connection Settings$", "any", (CTX_ETHERNET_IP,)),
    ("heartbeat_multiplier", r"^Heartbeat Multiplier$", "scalar",
     (CTX_ETHERNET_IP,)),
    ("connection_count", r"^Number of Connections$", "scalar", (CTX_ETHERNET_IP,)),
)

_TYPE_TOKENS_C = [(c, re.compile(r, re.I)) for c, r in TYPE_TOKENS]
_STRUCTURAL_C = [(c, re.compile(r), shape, ctxs)
                 for c, r, shape, ctxs in STRUCTURAL_NAMES]

_RX_IP4 = re.compile(
    r"^\[\s*(?:16#)?[0-9A-Fa-f]{1,3}\s*(?:,\s*(?:16#)?[0-9A-Fa-f]{1,3}\s*){3}\]$")
_RX_SCALAR = re.compile(
    r"^(?:16#[0-9A-Fa-f]+|-?\d+|'[^']*'|\"[^\"]*\"|TRUE|FALSE|true|false)$")


@dataclass(frozen=True)
class RunSource:
    """Uma run de export, com o estado do projeto que a originou.

    `project_sha256` é o que permite dizer, depois, que o inventário é
    composto — e de qual estado veio cada dispositivo.
    """

    run_dir: str
    state: str
    project_sha256: str
    only_devices: tuple[str, ...] | None = None
    exclude_devices: tuple[str, ...] = field(default_factory=tuple)


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def value_shape(value: str | None, state: str) -> str:
    """Forma do valor: `ip4`, `scalar`, `other` ou `non_scalar`.

    Existe porque nome sozinho não distingue um `SubnetMask` de verdade de um
    parâmetro homônimo com valor vazio ou estruturado.
    """
    if state != VALUE_PRESENT or value is None:
        return "non_scalar"
    text = value.strip()
    if _RX_IP4.match(text):
        return "ip4"
    if _RX_SCALAR.match(text):
        return "scalar"
    return "other"


def protocol_context(device_type: str | None, interfaces, parameter_types) -> list[str]:
    """Contexto de protocolo a partir da ESTRUTURA do export.

    Nunca do nome do dispositivo: nome é convenção da planta e muda entre
    projetos.
    """
    context: set[str] = set()
    if device_type in ("100", "101", "120"):
        context.add(CTX_ETHERNET_IP)
    for interface in interfaces or ():
        lowered = (interface or "").lower()
        if "ethernetip" in lowered:
            context.add(CTX_ETHERNET_IP)
        if "modbus" in lowered:
            context.add(CTX_MODBUS)
        if lowered in ("common.ethernet", "common.ethernetip"):
            context.add(CTX_ETHERNET)
    for parameter_type in parameter_types or ():
        upper = (parameter_type or "").upper()
        if "MODBUS" in upper or "TYPE_ETH_" in upper:
            context.add(CTX_MODBUS)
        if "IPCONFIGMODE" in upper or "TRANSFERRATE" in upper:
            context.add(CTX_ETHERNET)
    if not context:
        context.add(CTX_LOCAL)
    return sorted(context)


def interpret_parameter(record: dict[str, Any], context) -> tuple[list[dict], str | None]:
    """Devolve `(acertos, motivo_unresolved)`.

    Só um dos dois é significativo: com acertos, o motivo é `None`.
    """
    parameter_type = record.get("type") or ""
    name = record.get("name") or ""
    hits: list[dict] = []

    for concept, regex in _TYPE_TOKENS_C:
        if regex.search(parameter_type):
            hits.append({
                "concept": concept,
                "confidence": CONFIDENCE_HIGH,
                "rule": f"type_token:{regex.pattern[:34]}",
                "evidence": f"token semantico no type={parameter_type}",
            })
    if hits:
        return hits, None

    rejected_by_name: str | None = None
    parameter_id = record.get("parameter_id")
    for ctx in context:
        mapping = PARAMETER_IDS.get(ctx) or {}
        if parameter_id not in mapping:
            continue
        concept, expected_name = mapping[parameter_id]
        if name != expected_name:
            rejected_by_name = (
                f"ParameterId {parameter_id} casaria com {concept} no contexto "
                f"{ctx}, mas o nome e {name!r} e nao {expected_name!r} — "
                "ParameterId isolado nao e evidencia")
            continue
        hits.append({
            "concept": concept,
            "confidence": CONFIDENCE_HIGH,
            "rule": f"parameter_id+nome:{parameter_id}@{ctx}",
            "evidence": (f"ParameterId {parameter_id} corroborado pelo nome "
                         f"{name!r} no contexto {ctx}"),
        })
    if hits:
        return hits, None

    shape = value_shape(record.get("value"), record.get("value_state"))
    for concept, regex, required_shape, contexts in _STRUCTURAL_C:
        if not regex.match(name):
            continue
        if not set(contexts) & set(context):
            return [], (f"nome {name!r} casa com {concept}, mas o contexto "
                        f"estrutural do dispositivo e {context}")
        if required_shape != "any" and shape != required_shape:
            return [], (f"nome {name!r} casa com {concept}, mas a forma do "
                        f"valor e {shape!r} (esperado {required_shape!r})")
        hits.append({
            "concept": concept,
            "confidence": CONFIDENCE_MEDIUM,
            "rule": f"nome_estrutural:{regex.pattern[:34]}",
            "evidence": f"nome exato + forma {shape!r} + contexto {context}",
        })
    if hits:
        return hits, None
    if rejected_by_name:
        return [], rejected_by_name
    return [], "sem token de tipo, sem ParameterId conhecido, sem nome estrutural"


def parse_device_export(path: str) -> dict[str, Any]:
    """Lê um export de dispositivo e devolve identidade, interfaces e
    parâmetros. Não interpreta nada."""
    tree = ET.parse(path)
    root = tree.getroot()
    parents = {child: parent for parent in root.iter() for child in parent}

    device_type = device_id = device_version = None
    for element in root.iter():
        if _local(element.tag) == "DeviceIdentification":
            for child in element:
                tag = _local(child.tag)
                text = (child.text or "").strip()
                if tag == "Type":
                    device_type = text
                elif tag == "Id":
                    device_id = text
                elif tag == "Version":
                    device_version = text
            break

    interfaces = [element.get("interface") for element in root.iter()
                  if _local(element.tag) == "Connector" and element.get("interface")]

    parameters = []
    for element in root.iter():
        if _local(element.tag) != "Parameter":
            continue
        chain = []
        current: Any = element
        while current is not None:
            label = _local(current.tag)
            name_attr = current.get("name") or current.get("Name")
            if name_attr:
                label += f"[{name_attr}]"
            chain.append(label)
            current = parents.get(current)

        children: dict[str, Any] = {}
        attributes: dict[str, Any] = {}
        value_element = None
        for child in element:
            tag = _local(child.tag)
            children[tag] = child.text
            if tag == "Value":
                value_element = child
            for key in child.keys():
                attributes[f"{tag}@{key}"] = child.get(key)

        text = children.get("Value")
        child_count = 0 if value_element is None else len(list(value_element))
        if "Value" not in children:
            state = VALUE_ABSENT
        elif child_count > 0:
            state = VALUE_STRUCTURED
        elif text is None or text.strip() == "":
            state = VALUE_EMPTY
        else:
            state = VALUE_PRESENT

        parameters.append({
            "xml_path": "/".join(reversed(chain)),
            "parameter_id": element.get("ParameterId"),
            "index_in_devdesc": element.get("IndexInDevDesc"),
            "fixed_address": element.get("FixedAddress"),
            "type": element.get("type"),
            "name": children.get("Name"),
            "visible_name": attributes.get("Value@visiblename"),
            "description": children.get("Description"),
            "unit": children.get("Unit"),
            "value": text,
            "value_state": state,
            "value_children": child_count,
            "online_access": attributes.get("Attributes@onlineaccess"),
            "offline_access": attributes.get("Attributes@offlineaccess"),
        })

    return {
        "device_identification": {"type": device_type, "id": device_id,
                                  "version": device_version},
        "connector_interfaces": sorted(set(interfaces)),
        "parameters": parameters,
    }


def build_inventory(sources, device_files, topology_nodes=None) -> dict[str, Any]:
    """Monta as duas camadas a partir de `device_files`.

    `device_files`: lista de dicts com `device_name`, `node_id`, `path` e
    `source` (o `RunSource` de origem). Quem descobre os arquivos é o
    chamador — assim esta função não depende de layout de disco e é testável
    com fixtures sintéticas.
    """
    topology = {node["node_id"]: node for node in (topology_nodes or [])}
    raw: list[dict[str, Any]] = []
    devices: list[dict[str, Any]] = []
    sequence = 0

    for entry in sorted(device_files, key=lambda e: e["node_id"]):
        source: RunSource = entry["source"]
        digest = sha256_file(entry["path"])
        parsed = parse_device_export(entry["path"])
        node = topology.get(entry["node_id"], {})
        device_records = []
        for parameter in parsed["parameters"]:
            sequence += 1
            record = dict(parameter)
            record.update({
                "seq": sequence,
                "device_name": entry["device_name"],
                "device_node_id": entry["node_id"],
                "run_dir": source.run_dir,
                "project_state": source.state,
                "project_sha256": source.project_sha256,
                "source_file": entry["path"],
                "source_sha256": digest,
                "device_ident_type": parsed["device_identification"]["type"],
                "device_ident_id": parsed["device_identification"]["id"],
                "device_ident_version": parsed["device_identification"]["version"],
                "parse_status": "ok",
            })
            device_records.append(record)
        raw.extend(device_records)
        devices.append({
            "device_name": entry["device_name"],
            "node_id": entry["node_id"],
            "depth": node.get("depth"),
            "project_state": source.state,
            "project_sha256": source.project_sha256,
            "source_file": entry["path"],
            "source_sha256": digest,
            "parameters": len(device_records),
            "device_identification": parsed["device_identification"],
            "connector_interfaces": parsed["connector_interfaces"],
            "protocol_context": protocol_context(
                parsed["device_identification"]["type"],
                parsed["connector_interfaces"],
                [r["type"] for r in device_records]),
        })

    context_by_device = {d["device_name"]: d["protocol_context"] for d in devices}

    interpreted: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for record in raw:
        context = context_by_device.get(record["device_name"], [CTX_LOCAL])
        hits, reason = interpret_parameter(record, context)
        if not hits:
            unresolved.append({
                "seq": record["seq"], "device_name": record["device_name"],
                "parameter_id": record["parameter_id"], "type": record["type"],
                "name": record["name"], "value": record["value"],
                "value_state": record["value_state"],
                "protocol_context": context, "motivo": reason,
            })
            continue
        concepts = sorted({hit["concept"] for hit in hits})
        ambiguity = (f"casou com {len(concepts)} conceitos: {', '.join(concepts)}"
                     if len(concepts) > 1 else None)
        for hit in hits:
            interpreted.append({
                "seq": record["seq"], "device_name": record["device_name"],
                "device_node_id": record["device_node_id"],
                "project_state": record["project_state"],
                "project_sha256": record["project_sha256"],
                "concept": hit["concept"], "raw_value": record["value"],
                "value_state": record["value_state"], "unit": record["unit"],
                "source_parameter_id": record["parameter_id"],
                "source_type": record["type"], "source_name": record["name"],
                "source_file": record["source_file"],
                "source_sha256": record["source_sha256"],
                "xml_path": record["xml_path"], "protocol_context": context,
                "rule": hit["rule"], "confidence": hit["confidence"],
                "evidence": hit["evidence"], "ambiguity": ambiguity,
            })

    states = {source.project_sha256 for source in sources}
    snapshot_kind = SNAPSHOT_SINGLE if len(states) <= 1 else SNAPSHOT_COMPOSITE

    raw.sort(key=lambda r: (r["device_node_id"], int(r["parameter_id"] or 0),
                            r["xml_path"], r["seq"]))
    interpreted.sort(key=lambda i: (i["device_node_id"], i["concept"],
                                    int(i["source_parameter_id"] or 0), i["seq"]))
    unresolved.sort(key=lambda u: (u["device_name"] or "", u["seq"]))
    devices.sort(key=lambda d: d["node_id"])

    by_id = collections.Counter(
        (r["device_node_id"], r["parameter_id"]) for r in raw)
    exact = collections.Counter(
        (r["device_node_id"], r["xml_path"], r["parameter_id"], r["value"])
        for r in raw)
    keys: dict[tuple, set] = {}
    for record in raw:
        keys.setdefault((record["device_node_id"], record["name"]), set()).add(
            record["value"])

    return {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "inventory_snapshot_kind": snapshot_kind,
        "raw": raw,
        "interpreted": interpreted,
        "unresolved": unresolved,
        "devices": devices,
        "coverage": {
            "devices_observed": len(devices),
            "devices_with_parameters": len([d for d in devices
                                            if d["parameters"] > 0]),
            "devices_by_state": {
                state: sorted(d["device_name"] for d in devices
                              if d["project_state"] == state)
                for state in sorted({d["project_state"] for d in devices})
            },
        },
        "validations": {
            "parameters_total": len(raw),
            "value_states": dict(collections.Counter(
                r["value_state"] for r in raw)),
            "value_text_zero": len([r for r in raw if r["value"] == "0"]),
            "duplicate_parameter_ids": sorted(
                [list(k) + [v] for k, v in by_id.items() if v > 1]),
            "exact_duplicates": len([1 for v in exact.values() if v > 1]),
            "conflicting_values": sorted(
                [list(k) for k, v in keys.items() if len(v) > 1]),
            "interpretations_missing_provenance": len(
                [i for i in interpreted
                 if not i["rule"] or not i["confidence"] or not i["source_file"]]),
        },
    }

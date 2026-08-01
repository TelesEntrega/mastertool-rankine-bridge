# -*- coding: utf-8 -*-
r"""23_inventory_device_parameters_readonly.py — FASE 1: inventario dos
parametros de dispositivo lendo EXCLUSIVAMENTE membros getter-only.

Pre-requisito comprovado (FASE 0, probe 22, execucao real de 2026-07-30):
`node.device_parameters` existe e devolve
`ScriptMappableDeviceParameterSet`, que implementa `IScriptDeviceParameterSet`
e `IScriptMappableDeviceParameterSet`.

O QUE E LIDO — lista fechada, cada membro com acesso LITERAL escrito no
codigo, um por funcao. Todos sao getter-only na evidencia estatica:

    id                    name                  identifier
    visible_name          description           iec_type
    param_type            section               type_string
    unit                  bit_size              base_type
    default_value         min_value             max_value
    offline_access_rights online_access_rights  can_access_online
    has_sub_elements      is_enumeration        is_mappable_io
    allowed_values        (so identifier/visible_name de cada item)

O QUE NAO E LIDO, e nao aparece como acesso neste arquivo:

    value          enum_value      value_index     user_comment
    Item           read_online_value               read_online_enum_value
    write_online_value              Add/Clear/Insert/Remove/RemoveAt/CopyTo
    qualquer membro que possua setter
    qualquer metodo de mutacao ou de rede

`value` e FASE 2 e vive em probe separado. `has_sub_elements` e apenas
REGISTRADO: descer em sub-elementos exige `Item`, que esta proibido aqui.

De `allowed_values` sao lidos somente `identifier` e `visible_name` de cada
item. O membro `IScriptEnumerationValue.value` e getter-only, mas e valor —
fica para a Fase 2 por conservadorismo, nao por impedimento tecnico.

PROIBIDO, e ausente do arquivo: dir(), getattr com nome em variavel,
setattr, PropertyInfo.SetValue, GetExtensions(), qualquer API online.

LIMITES: finitos e configuraveis. Um dispositivo com um numero absurdo de
parametros interrompe aquele dispositivo, registra o limite, e a varredura
continua nos demais — isolamento por dispositivo, como o probe 21 faz por no.

EXECUCAO (pelo USUARIO, UI VISIVEL, COPIA DESCARTAVEL, offline, sem salvar):

    --scriptargs:"--output=C:\saida-fase1 --node-ids=root/1/1/0,root/1/1/0/2"
"""
from __future__ import print_function

import os
import sys

try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    _FILE_AVAILABLE = True
except NameError:
    _SCRIPT_DIR = os.getcwd()
    _FILE_AVAILABLE = False

_MASTERTOOL_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
if _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)
REPO_ROOT = os.path.abspath(os.path.join(_MASTERTOOL_DIR, "..", ".."))

# NAO existe lista default de dispositivos: uma lista embutida seria a
# estrutura de UM projeto especifico dentro do repositorio. --node-ids e
# obrigatorio e vem da varredura do probe 21.

EXPECTED_INTERFACE = ("_3S.CoDeSys.ScriptEngine.BasicFunctionality."
                      "IScriptDeviceParameterSet")
DEFAULT_MAX_DEVICES = 64
DEFAULT_MAX_PARAMS_PER_DEVICE = 2048
DEFAULT_MAX_ALLOWED_VALUES = 256
MAX_PATH_STEPS = 12
MAX_CHILDREN_PER_STEP = 1024

STATUS_COMPLETE = "complete"
STATUS_COMPLETE_WITH_DEVICE_ERRORS = "complete_with_device_errors"
STATUS_TRUNCATED = "truncated"
STATUS_FATAL = "fatal"
EXIT_BY_STATUS = {STATUS_COMPLETE: 0, STATUS_COMPLETE_WITH_DEVICE_ERRORS: 0,
                  STATUS_TRUNCATED: 2, STATUS_FATAL: 1}

SAFETY_DECLARATION = {
    "read_only": True,
    "reads_configured_value": False,
    "reads_enum_value": False,
    "reads_value_index": False,
    "reads_user_comment": False,
    "reads_item_indexer": False,
    "descends_sub_elements": False,
    "uses_dir": False,
    "uses_dynamic_getattr": False,
    "uses_setattr": False,
    "uses_property_setvalue": False,
    "uses_get_extensions": False,
    "calls_online_api": False,
    "calls_ilist_mutators": False,
    "project_write": False,
    "project_save": False,
}


# --- getters: um por membro, acesso LITERAL --------------------------------
def _g_id(p):                    return p.id
def _g_name(p):                  return p.name
def _g_identifier(p):            return p.identifier
def _g_visible_name(p):          return p.visible_name
def _g_description(p):           return p.description
def _g_iec_type(p):              return p.iec_type
def _g_param_type(p):            return p.param_type
def _g_section(p):               return p.section
def _g_type_string(p):           return p.type_string
def _g_unit(p):                  return p.unit
def _g_bit_size(p):              return p.bit_size
def _g_base_type(p):             return p.base_type
def _g_default_value(p):         return p.default_value
def _g_min_value(p):             return p.min_value
def _g_max_value(p):             return p.max_value
def _g_offline_access_rights(p): return p.offline_access_rights
def _g_online_access_rights(p):  return p.online_access_rights
def _g_can_access_online(p):     return p.can_access_online
def _g_has_sub_elements(p):      return p.has_sub_elements
def _g_is_enumeration(p):        return p.is_enumeration
def _g_is_mappable_io(p):        return p.is_mappable_io

PARAMETER_GETTERS = (
    ("id", _g_id), ("name", _g_name), ("identifier", _g_identifier),
    ("visible_name", _g_visible_name), ("description", _g_description),
    ("iec_type", _g_iec_type), ("param_type", _g_param_type),
    ("section", _g_section), ("type_string", _g_type_string),
    ("unit", _g_unit), ("bit_size", _g_bit_size), ("base_type", _g_base_type),
    ("default_value", _g_default_value), ("min_value", _g_min_value),
    ("max_value", _g_max_value),
    ("offline_access_rights", _g_offline_access_rights),
    ("online_access_rights", _g_online_access_rights),
    ("can_access_online", _g_can_access_online),
    ("has_sub_elements", _g_has_sub_elements),
    ("is_enumeration", _g_is_enumeration),
    ("is_mappable_io", _g_is_mappable_io),
)


def _g_allowed_values(p):        return p.allowed_values
def _g_ev_identifier(v):         return v.identifier
def _g_ev_visible_name(v):       return v.visible_name


def _g_device_parameters(node):
    """Elo comprovado na Fase 0. Acesso literal."""
    return node.device_parameters


# --- infraestrutura --------------------------------------------------------
def _find_arg(argv, name):
    prefix = "--" + name
    for i, raw in enumerate(argv):
        if raw == prefix:
            return argv[i + 1] if i + 1 < len(argv) else ""
        for sep in ("=", ":"):
            if raw.startswith(prefix + sep):
                return raw[len(prefix) + 1:]
    return None


def _validate_output(raw, problems):
    if raw is None or raw.strip() == "":
        problems.append("--output e obrigatorio")
        return None
    path = raw.strip().strip('"')
    if " " in path:
        problems.append("--output contem espaco: %r" % path)
        return None
    absolute = os.path.abspath(path)
    norm = os.path.normcase(absolute)
    if norm == os.path.normcase(REPO_ROOT) or \
            norm.startswith(os.path.normcase(REPO_ROOT) + os.sep):
        problems.append("--output aponta para dentro do repositorio")
        return None
    return absolute


def _positive_int(raw, default, label, problems):
    if raw is None or raw == "":
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        problems.append("%s invalido: %r" % (label, raw))
        return None
    if value <= 0:
        problems.append("%s deve ser > 0" % label)
        return None
    return value


def _parse_node_ids(raw, problems):
    text = (raw or "").strip()
    if text == "":
        problems.append("--node-ids e obrigatorio: a lista vem da varredura do "
                        "projeto, nunca embutida no repositorio")
        return None
    items = [p.strip() for p in text.split(",") if p.strip()]
    parsed = []
    for item in items:
        parts = [p for p in item.split("/") if p != ""]
        if not parts or parts[0] != "root":
            problems.append("node-id invalido (deve comecar por 'root'): %r" % item)
            return None
        idx = []
        for part in parts[1:]:
            try:
                value = int(part)
            except (TypeError, ValueError):
                problems.append("node-id com segmento nao numerico: %r" % item)
                return None
            if value < 0:
                problems.append("node-id com indice negativo: %r" % item)
                return None
            idx.append(value)
        if not idx or len(idx) > MAX_PATH_STEPS:
            problems.append("node-id com profundidade invalida: %r" % item)
            return None
        parsed.append((item, idx))
    return parsed


def _descend(project, indexes, trace):
    current = project
    for step, index in enumerate(indexes):
        children = current.get_children(False)
        if children is None:
            trace.append({"step": step, "error": "get_children devolveu None"})
            return None
        count = children.Count
        if count < 0 or count > MAX_CHILDREN_PER_STEP:
            trace.append({"step": step, "error": "Count fora de faixa: %r" % count})
            return None
        if index >= count:
            trace.append({"step": step, "error":
                          "indice %d fora da faixa (Count=%d)" % (index, count)})
            return None
        current = children[index]
        trace.append({"step": step, "index": index, "sibling_count": count,
                      "name": current.get_name(False)})
    return current


def _implements_expected(obj):
    try:
        import clr
        clr_type = clr.GetClrType(type(obj))
        for iface in clr_type.GetInterfaces():
            if iface.FullName == EXPECTED_INTERFACE:
                return True, clr_type.FullName, None
        return False, clr_type.FullName, None
    except Exception as exc:                                   # noqa: BLE001
        return False, None, repr(exc)


def _read_allowed_values(parameter, max_items):
    """So identifier e visible_name. `value` de enum e Fase 2."""
    out = {"count": 0, "items": [], "error": None, "truncated": False}
    try:
        collection = _g_allowed_values(parameter)
    except Exception as exc:                                   # noqa: BLE001
        out["error"] = repr(exc)
        return out
    if collection is None:
        return out
    try:
        for item in collection:
            if out["count"] >= max_items:
                out["truncated"] = True
                break
            entry = {"identifier": None, "visible_name": None, "error": None}
            try:
                entry["identifier"] = _g_ev_identifier(item)
            except Exception as exc:                           # noqa: BLE001
                entry["error"] = repr(exc)
            try:
                entry["visible_name"] = _g_ev_visible_name(item)
            except Exception as exc:                           # noqa: BLE001
                entry["error"] = repr(exc)
            out["items"].append(entry)
            out["count"] += 1
    except Exception as exc:                                   # noqa: BLE001
        out["error"] = repr(exc)
    return out


def _read_parameter(parameter, index, max_allowed):
    record = {"index": index, "fields": {}, "field_errors": {},
              "allowed_values": None}
    for name, getter in PARAMETER_GETTERS:
        try:
            value = getter(parameter)
        except Exception as exc:                               # noqa: BLE001
            record["field_errors"][name] = repr(exc)
            continue
        if value is None or isinstance(value, (bool, int, float)):
            record["fields"][name] = value
        else:
            try:
                record["fields"][name] = str(value)
            except Exception as exc:                           # noqa: BLE001
                record["field_errors"][name] = repr(exc)
    if record["fields"].get("is_enumeration") is True:
        record["allowed_values"] = _read_allowed_values(parameter, max_allowed)
    return record


def main():
    print("=" * 68)
    print("[INFO] probes/23_inventory_device_parameters_readonly.py — FASE 1")
    print("[INFO] Somente membros getter-only. `value` NAO e lido aqui.")
    print("=" * 68)

    problems = []
    argv = list(sys.argv or [])
    out_root = _validate_output(_find_arg(argv, "output"), problems)
    node_ids = _parse_node_ids(_find_arg(argv, "node-ids"), problems)
    max_devices = _positive_int(_find_arg(argv, "max-devices"),
                                DEFAULT_MAX_DEVICES, "--max-devices", problems)
    max_params = _positive_int(_find_arg(argv, "max-params-per-device"),
                               DEFAULT_MAX_PARAMS_PER_DEVICE,
                               "--max-params-per-device", problems)
    max_allowed = _positive_int(_find_arg(argv, "max-allowed-values"),
                                DEFAULT_MAX_ALLOWED_VALUES,
                                "--max-allowed-values", problems)
    if not _FILE_AVAILABLE:
        problems.append("__file__ indisponivel")
    if node_ids and len(node_ids) > (max_devices or 0):
        problems.append("mais dispositivos (%d) que --max-devices (%s)"
                        % (len(node_ids), max_devices))

    if problems:
        print("[FATAL] argumentos recusados:")
        for item in problems:
            print("        - %s" % item)
        sys.exit(EXIT_BY_STATUS[STATUS_FATAL])
        return

    try:
        from common import file_io, project_access
    except Exception as exc:                                   # noqa: BLE001
        print("[FATAL] falha ao importar modulos comuns: %r" % (exc,))
        sys.exit(EXIT_BY_STATUS[STATUS_FATAL])
        return

    manifest = {
        "schema_version": "1.0",
        "script": "probes/23_inventory_device_parameters_readonly.py",
        "phase": "1",
        "mode": "read_only",
        "generated_at": file_io.iso_now(),
        "expected_interface": EXPECTED_INTERFACE,
        "getters_declared": [n for n, _f in PARAMETER_GETTERS] + ["allowed_values"],
        "limits_configured": {"max_devices": max_devices,
                              "max_params_per_device": max_params,
                              "max_allowed_values": max_allowed},
        "devices": [],
        "totals": {"devices": 0, "devices_with_set": 0, "devices_with_errors": 0,
                   "parameters": 0, "truncated_devices": 0},
        "status": STATUS_FATAL,
        "fatal_error": None,
        "safety_declaration": SAFETY_DECLARATION,
    }

    run_dir = None
    try:
        project, err = project_access.get_primary_project(globals())
        if project is None:
            manifest["fatal_error"] = "sem projeto primario: %s" % (err,)
            raise RuntimeError(manifest["fatal_error"])
        project_path = project_access.get_project_path(project)
        manifest["project_path"] = project_path
        slug = "projeto"
        if project_path:
            slug = os.path.splitext(os.path.basename(project_path))[0]
        run_dir = file_io.new_export_dir(out_root,
                                         file_io.safe_filename(slug) + "_fase1")
        print("[INFO] saida: %s" % run_dir)
        print("[INFO] dispositivos na lista: %d" % len(node_ids))

        for node_text, indexes in node_ids:
            entry = {"node_id": node_text, "device_name": None,
                     "descent_trace": [], "set_type": None,
                     "implements_expected_interface": None,
                     "count": None, "error": None, "truncated": False,
                     "parameters": []}
            manifest["devices"].append(entry)
            manifest["totals"]["devices"] += 1
            try:
                node = _descend(project, indexes, entry["descent_trace"])
                if node is None:
                    entry["error"] = "no inalcancavel"
                    manifest["totals"]["devices_with_errors"] += 1
                    continue
                entry["device_name"] = entry["descent_trace"][-1].get("name")

                try:
                    parameter_set = _g_device_parameters(node)
                except Exception as exc:                       # noqa: BLE001
                    entry["error"] = "device_parameters indisponivel: %r" % (exc,)
                    manifest["totals"]["devices_with_errors"] += 1
                    continue
                if parameter_set is None:
                    entry["error"] = "device_parameters devolveu None"
                    manifest["totals"]["devices_with_errors"] += 1
                    continue

                ok, type_name, type_error = _implements_expected(parameter_set)
                entry["set_type"] = type_name
                entry["implements_expected_interface"] = ok
                if type_error:
                    entry["error"] = "reflection do tipo falhou: %s" % type_error
                if not ok:
                    manifest["totals"]["devices_with_errors"] += 1
                    continue
                manifest["totals"]["devices_with_set"] += 1

                try:
                    entry["count"] = parameter_set.Count
                except Exception as exc:                       # noqa: BLE001
                    entry["error"] = "Count indisponivel: %r" % (exc,)
                    manifest["totals"]["devices_with_errors"] += 1
                    continue

                read = 0
                for parameter in parameter_set:
                    if read >= max_params:
                        entry["truncated"] = True
                        manifest["totals"]["truncated_devices"] += 1
                        break
                    entry["parameters"].append(
                        _read_parameter(parameter, read, max_allowed))
                    read += 1
                manifest["totals"]["parameters"] += read
                print("[INFO] %-24s Count=%-5s lidos=%d"
                      % (entry["device_name"], entry["count"], read))
            except Exception as exc:                           # noqa: BLE001
                entry["error"] = repr(exc)
                manifest["totals"]["devices_with_errors"] += 1

        if manifest["totals"]["truncated_devices"]:
            manifest["status"] = STATUS_TRUNCATED
        elif manifest["totals"]["devices_with_errors"]:
            manifest["status"] = STATUS_COMPLETE_WITH_DEVICE_ERRORS
        else:
            manifest["status"] = STATUS_COMPLETE
    except Exception as exc:                                   # noqa: BLE001
        manifest["status"] = STATUS_FATAL
        if not manifest["fatal_error"]:
            manifest["fatal_error"] = repr(exc)
        print("[FATAL] %s" % manifest["fatal_error"])
        try:
            import traceback
            traceback.print_exc()
        except Exception:                                      # noqa: BLE001
            pass

    try:
        if run_dir is None:
            run_dir = file_io.new_export_dir(out_root, "fase1_fatal")
        file_io.write_json(os.path.join(run_dir, "manifest.json"), manifest)
        print("[OK] manifesto em: %s" % run_dir)
    except Exception as exc:                                   # noqa: BLE001
        print("[ERROR] falha ao gravar manifesto: %r" % (exc,))
        manifest["status"] = STATUS_FATAL

    totals = manifest["totals"]
    print("[INFO] dispositivos=%d com_set=%d com_erro=%d parametros=%d"
          % (totals["devices"], totals["devices_with_set"],
             totals["devices_with_errors"], totals["parameters"]))
    code = EXIT_BY_STATUS.get(manifest["status"], EXIT_BY_STATUS[STATUS_FATAL])
    print("[INFO] status=%s exit=%d (o status do manifesto e autoritativo)"
          % (manifest["status"], code))
    print("=" * 68)
    sys.exit(code)


main()

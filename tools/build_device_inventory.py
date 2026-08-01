#!/usr/bin/env python
"""Monta o inventário de configuração de dispositivo a partir de uma ou mais
runs de export por dispositivo (`probes/25`).

Offline por completo: não abre o MasterTool, não reexporta, não toca o
repositório de dispositivos. Lê apenas artefatos de run já produzidos.

Uso:

    python tools/build_device_inventory.py \\
        --run <run_dir>:<estado>:<sha256_do_projeto> \\
        [--run <outra_run>:<estado>:<sha256>] \\
        [--topology <run_do_probe_21>] \\
        --output <diretorio_fora_do_repositorio>

`--run` pode repetir. Quando as runs vierem de hashes de projeto diferentes,
o inventário é declarado `composite` — ele deixa de ser um snapshot único, e
dizer o contrário seria falso.

**Os artefatos gerados contêm dados do projeto real** (nomes de equipamento,
endereços, configuração). Eles ficam FORA do repositório, e `--output` recusa
qualquer caminho dentro dele.
"""

from __future__ import annotations

import argparse
import codecs
import csv
import io
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(REPO_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from mastertool_bridge.inventory import device_inventory as di  # noqa: E402

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

RAW_COLUMNS = [
    "seq", "device_name", "device_node_id", "project_state", "project_sha256",
    "parameter_id", "index_in_devdesc", "type", "name", "visible_name", "unit",
    "value_state", "value", "value_children", "online_access",
    "offline_access", "description", "xml_path", "source_file",
    "source_sha256", "parse_status",
]
INVENTORY_COLUMNS = [
    "device_name", "project_state", "concept", "raw_value", "value_state",
    "unit", "confidence", "rule", "evidence", "protocol_context",
    "source_parameter_id", "source_type", "source_name", "ambiguity",
    "xml_path", "source_file", "source_sha256",
]


def _write_json(path, data):
    with codecs.open(path, "w", "utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _write_csv(path, rows, columns):
    with io.open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            clean = {}
            for key in columns:
                value = row.get(key)
                if isinstance(value, (list, tuple)):
                    value = "; ".join(str(item) for item in value)
                elif isinstance(value, dict):
                    value = json.dumps(value, sort_keys=True, ensure_ascii=False)
                clean[key] = "" if value is None else value
            writer.writerow(clean)


def _parse_run(spec):
    parts = spec.split(":")
    if len(parts) < 3:
        raise argparse.ArgumentTypeError(
            "--run espera <run_dir>:<estado>:<sha256>, recebido %r" % spec)
    digest = parts[-1]
    state = parts[-2]
    run_dir = ":".join(parts[:-2])
    return di.RunSource(run_dir=run_dir, state=state, project_sha256=digest)


def _discover(source):
    """Lê o manifesto da run e devolve os dispositivos que exportaram."""
    manifest_path = os.path.join(source.run_dir, "manifest.json")
    with codecs.open(manifest_path, "r", "utf-8") as handle:
        manifest = json.load(handle)
    found = []
    for device in manifest.get("devices", []):
        name = device.get("device_name")
        if device.get("error") or not device.get("target_path"):
            continue
        if not os.path.isfile(device["target_path"]):
            continue
        if source.only_devices is not None and name not in source.only_devices:
            continue
        if name in source.exclude_devices:
            continue
        found.append({"device_name": name, "node_id": device["node_id"],
                      "path": device["target_path"], "source": source})
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, type=_parse_run,
                        help="<run_dir>:<estado>:<sha256_do_projeto>")
    parser.add_argument("--topology", help="run do probe 21 (flat-nodes.json)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--prefer-latest-run", action="store_true",
                        help="quando o mesmo dispositivo aparece em mais de uma "
                             "run, mantem o da run informada por ultimo")
    args = parser.parse_args(argv)

    output = os.path.abspath(args.output)
    normalized = os.path.normcase(output)
    repo = os.path.normcase(REPO_ROOT)
    if normalized == repo or normalized.startswith(repo + os.sep):
        print("[FATAL] --output aponta para dentro do repositorio: %s" % output)
        print("        artefatos de inventario carregam dados do projeto real "
              "e nunca entram na arvore do repo.")
        return EXIT_USAGE

    device_files = []
    seen = {}
    for source in args.run:
        for entry in _discover(source):
            key = entry["node_id"]
            if key in seen and not args.prefer_latest_run:
                print("[FATAL] dispositivo %r aparece em mais de uma run. Use "
                      "--prefer-latest-run para escolher explicitamente."
                      % entry["device_name"])
                return EXIT_USAGE
            seen[key] = entry
    device_files = list(seen.values())
    if not device_files:
        print("[FATAL] nenhuma exportacao de dispositivo encontrada nas runs")
        return EXIT_FAILED

    topology_nodes = []
    if args.topology:
        flat = os.path.join(args.topology, "flat-nodes.json")
        if os.path.isfile(flat):
            with codecs.open(flat, "r", "utf-8") as handle:
                topology_nodes = json.load(handle)

    inventory = di.build_inventory(args.run, device_files, topology_nodes)

    if not os.path.isdir(output):
        os.makedirs(output)
    _write_json(os.path.join(output, "parameters-raw.json"), inventory["raw"])
    _write_csv(os.path.join(output, "parameters-raw.csv"),
               inventory["raw"], RAW_COLUMNS)
    _write_json(os.path.join(output, "communication-inventory.json"),
                inventory["interpreted"])
    _write_csv(os.path.join(output, "communication-inventory.csv"),
               inventory["interpreted"], INVENTORY_COLUMNS)
    _write_json(os.path.join(output, "unresolved-parameters.json"),
                inventory["unresolved"])
    _write_json(os.path.join(output, "device-coverage.json"), {
        "coverage": inventory["coverage"], "devices": inventory["devices"],
        "validations": inventory["validations"]})

    outputs = {}
    for name in sorted(os.listdir(output)):
        path = os.path.join(output, name)
        if name != "manifest.json" and os.path.isfile(path):
            outputs[name] = {"bytes": os.path.getsize(path),
                             "sha256": di.sha256_file(path)}
    _write_json(os.path.join(output, "manifest.json"), {
        "schema_version": inventory["schema_version"],
        "inventory_snapshot_kind": inventory["inventory_snapshot_kind"],
        "runs": [{"run_dir": s.run_dir, "state": s.state,
                  "project_sha256": s.project_sha256} for s in args.run],
        "topology_run": args.topology,
        "coverage": inventory["coverage"],
        "validations": inventory["validations"],
        "interpretation_rules": {
            "hierarchy": ["type_token (high)",
                          "parameter_id corroborado pelo nome (high)",
                          "nome + forma do valor + contexto (medium)",
                          "nome isolado -> nao interpreta"],
            "type_tokens": [c for c, _ in di.TYPE_TOKENS],
            "parameter_ids": di.PARAMETER_IDS,
            "structural_names": [[c, r, s, list(x)]
                                 for c, r, s, x in di.STRUCTURAL_NAMES],
            "device_name_as_evidence": False,
        },
        "output_hashes": outputs,
        "manifest_hash_note": ("o manifesto nao contem o proprio hash: e escrito "
                               "por ultimo, depois de hashear as demais saidas"),
    })

    coverage = inventory["coverage"]
    print("[OK] dispositivos: %d (com parametros: %d)"
          % (coverage["devices_observed"], coverage["devices_with_parameters"]))
    print("[OK] parametros  : %d" % inventory["validations"]["parameters_total"])
    print("[OK] interpretado: %d   unresolved: %d"
          % (len(inventory["interpreted"]), len(inventory["unresolved"])))
    print("[OK] snapshot    : %s" % inventory["inventory_snapshot_kind"])
    print("[OK] saida       : %s" % output)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

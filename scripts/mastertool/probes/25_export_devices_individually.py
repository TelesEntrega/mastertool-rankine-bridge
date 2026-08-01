# -*- coding: utf-8 -*-
r"""25_export_devices_individually.py — exportar PLCopen XML DISPOSITIVO A
DISPOSITIVO, para contornar o truncamento reprodutivel do export monolitico.

PROBLEMA QUE ISTO ATACA
    O export do projeto inteiro trunca de forma REPRODUTIVEL na subarvore do
    scanner EtherNet/IP: duas exportacoes independentes, modos diferentes, 42
    min de intervalo, abortaram no mesmo no, e o arquivo nem fecha
    `</project>`. Como o serializador e monolitico, uma subarvore que falha
    leva junto os 1636 elementos `<Parameter>` de todos os outros
    dispositivos.

    A API permite escapar disso: `export_xml` vive em `IScriptObject` — ou
    seja, em QUALQUER no da arvore, nao so no projeto. Exportando um
    dispositivo por vez, a subarvore problematica falha sozinha.

INVOCACAO — identica a ja comprovada pelo probe 19 (reflexao) e exercitada
pelo probe 20 (invocacao real):

    target.export_xml(st_path, recursive, False, False)

    4 argumentos explicitos, sobrecarga SEM `IExportReporter`. NUNCA
    `MethodInfo.Invoke()`. NUNCA `import_xml`, que segue permanentemente fora
    de escopo.

DIFERENCA DE PERFIL EM RELACAO AO PROBE 20 — declarada, nao escondida
    O probe 20 autoriza EXATAMENTE UMA invocacao. Este autoriza UMA POR
    DISPOSITIVO da lista fechada. A contencao muda de "uma escrita" para "N
    escritas, cada uma num diretorio proprio, vazio, criado por este probe
    dentro da sua run, com o caminho de destino inexistente antes da chamada".
    Nenhuma escrita fora da run. Nenhum arquivo sobrescrito, nunca.

O QUE E MEDIDO POR DISPOSITIVO
    arquivo criado, tamanho, SHA-256, e se o conteudo FECHA `</project>` —
    assinatura direta do truncamento. Um export que nao fecha e registrado
    como truncado, jamais apresentado como completo.

ISOLAMENTO
    Falha de um dispositivo vira registro naquele dispositivo e a varredura
    continua. E o oposto do serializador monolitico, e e o ponto do probe.

NAO FAZ: save, build, import, online, download, force, leitura de `.text`,
`dir()`, `getattr` dinamico, `setattr`, escrita fora da run.

A LISTA DE DISPOSITIVOS E OBRIGATORIA e vem de fora (`--node-ids`), sempre
como caminho de INDICES produzido pela varredura do probe 21. Nao ha lista
default: uma lista embutida seria a estrutura de UM projeto especifico dentro
do repositorio.

EXECUCAO (COPIA DESCARTAVEL, offline, sem salvar):
    --scriptargs:"--output=C:\saida-export --recursive=0 --node-ids=root/1/1/0,root/1/1/0/2"
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

MAX_DEVICES = 64

SAFETY_DECLARATION = {
    "read_only": False,
    "writes_to_disk": True,
    "writes_confined_to_run_dir": True,
    "overwrites_existing_file": False,
    "invocation": "target.export_xml(st_path, recursive, False, False)",
    "uses_method_info_invoke": False,
    "uses_export_reporter_overload": False,
    "import_xml": False,
    "project_write": False,
    "project_save": False,
    "compilation": False,
    "online_access": False,
    "uses_dir": False,
    "uses_dynamic_getattr": False,
}


# Argumentos, navegacao por indice, identidade do runtime, slug ASCII,
# deteccao de truncamento e classificacao vivem em `common/probe_cli.py` e
# `common/device_export_inspection.py` — com teste. Probe que roda dentro do
# MasterTool nao e testavel; modulo comum e.

def main():
    print("=" * 68)
    print("[INFO] probes/25_export_devices_individually.py")
    print("[INFO] ESCREVE EM DISCO, confinado a run. Nao salva o projeto.")
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        sys.exit(1)
        return

    try:
        from common import (checksums, device_export_inspection, file_io,
                            probe_cli, project_access)
    except Exception as exc:                                   # noqa: BLE001
        print("[FATAL] falha ao importar modulos comuns: %r" % (exc,))
        sys.exit(1)
        return

    dei = device_export_inspection
    problems = []
    argv = list(sys.argv or [])
    out_root = probe_cli.validate_output_path(
        probe_cli.find_arg(argv, "output"), REPO_ROOT, problems)
    node_ids = probe_cli.parse_node_id_list(
        probe_cli.find_arg(argv, "node-ids"), problems, MAX_DEVICES)
    recursive = probe_cli.parse_bool(
        probe_cli.find_arg(argv, "recursive"), False, "--recursive", problems)
    if problems:
        print("[FATAL] argumentos recusados:")
        for item in problems:
            print("        - %s" % item)
        sys.exit(dei.exit_code_for(dei.STATUS_FATAL))
        return

    manifest = {
        "schema_version": "1.0",
        "script": "probes/25_export_devices_individually.py",
        "mode": "write_confined",
        "generated_at": file_io.iso_now(),
        "mastertool": probe_cli.runtime_identity(),
        "invocation": SAFETY_DECLARATION["invocation"],
        "recursive": recursive,
        "devices": [],
        "totals": {"devices": 0, "exported": 0, "closed_ok": 0,
                   "truncated": 0, "errors": 0},
        "status": dei.STATUS_FATAL,
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
                                         file_io.safe_filename(slug) + "_expdev")
        exports_root = os.path.join(run_dir, "exports")
        file_io.ensure_dir(exports_root)
        print("[INFO] saida    : %s" % run_dir)
        print("[INFO] recursive: %s" % recursive)

        position = 0
        for node_text, indexes in node_ids:
            position += 1
            entry = {"node_id": node_text, "device_name": None,
                     "descent_trace": [], "target_path": None,
                     "returned": None, "output": None, "error": None}
            manifest["devices"].append(entry)
            manifest["totals"]["devices"] += 1
            try:
                node = probe_cli.descend(project, indexes, entry["descent_trace"])
                if node is None:
                    entry["error"] = "no inalcancavel"
                    manifest["totals"]["errors"] += 1
                    continue
                name = entry["descent_trace"][-1].get("name")
                entry["device_name"] = name
                folder = os.path.join(
                    exports_root, "%02d_%s" % (position, dei.ascii_slug(name, "dev")))
                if os.path.exists(folder):
                    entry["error"] = "diretorio de destino ja existe: %s" % folder
                    manifest["totals"]["errors"] += 1
                    continue
                file_io.ensure_dir(folder)
                target_path = os.path.join(folder, "export")
                if os.path.exists(target_path):
                    entry["error"] = "arquivo de destino ja existe"
                    manifest["totals"]["errors"] += 1
                    continue
                entry["target_path"] = target_path

                # UNICA invocacao por dispositivo, 4 argumentos explicitos.
                returned = node.export_xml(target_path, recursive, False, False)
                entry["returned"] = None if returned is None else str(returned)

                info = dei.inspect_export_file(target_path, sha256_fn=checksums.sha256_file)
                entry["output"] = info
                if info.get("exists"):
                    manifest["totals"]["exported"] += 1
                    if info.get("closes_root_element"):
                        manifest["totals"]["closed_ok"] += 1
                    else:
                        manifest["totals"]["truncated"] += 1
                print("[INFO] %-26s bytes=%-9s fecha=%s"
                      % (name, info.get("size"), info.get("closes_root_element")))
            except Exception as exc:                           # noqa: BLE001
                entry["error"] = repr(exc)
                manifest["totals"]["errors"] += 1
                print("[INFO] %-26s ERRO %r" % (entry["device_name"], exc))

        manifest["status"] = dei.classify_export_run(manifest["totals"])
    except Exception as exc:                                   # noqa: BLE001
        manifest["status"] = dei.STATUS_FATAL
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
            run_dir = file_io.new_export_dir(out_root, "expdev_fatal")
        file_io.write_json(os.path.join(run_dir, "manifest.json"), manifest)
        print("[OK] manifesto em: %s" % run_dir)
    except Exception as exc:                                   # noqa: BLE001
        print("[ERROR] falha ao gravar manifesto: %r" % (exc,))
        manifest["status"] = dei.STATUS_FATAL

    totals = manifest["totals"]
    print("[INFO] dispositivos=%d exportados=%d fechados=%d truncados=%d erros=%d"
          % (totals["devices"], totals["exported"], totals["closed_ok"],
             totals["truncated"], totals["errors"]))
    code = dei.exit_code_for(manifest["status"])
    print("[INFO] status=%s exit=%d" % (manifest["status"], code))
    print("=" * 68)
    sys.exit(code)


main()

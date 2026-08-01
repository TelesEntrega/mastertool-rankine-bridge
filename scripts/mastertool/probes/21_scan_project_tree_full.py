# -*- coding: utf-8 -*-
r"""21_scan_project_tree_full.py — varredura recursiva SOMENTE LEITURA da
arvore completa de um projeto, com limites recebidos por argumento e saida
fora do repositorio.

Motivacao (2026-07-30): o `export_xml` do MasterTool e um serializador
MONOLITICO — uma subarvore que falha derruba o arquivo inteiro. Num projeto
real observou-se truncamento REPRODUTIVEL na subarvore de um scanner
EtherNet/IP: duas exportacoes independentes, 42 min de intervalo, abortaram
no mesmo no, deixando de fora servidores/clientes MODBUS, escravos e
adaptadores. Este probe usa o caminho oposto: navegacao no a no com
isolamento de erro POR NO (`ReadOnlyProjectScanner`), onde uma subarvore
problematica vira diagnostico naquele no e a varredura continua.

Runner FINO: toda a logica de navegacao e de seguranca vive em
`common/read_only_project_scanner.py`. Este arquivo so parseia argumentos,
chama `scan()` uma vez, classifica o resultado e grava.

O QUE ESTE SCRIPT NAO FAZ
    - nao importa, reativa ou substitui `tree_walker` (SUSPENSO desde
      2026-07-23; toda funcao dele levanta TreeNavigationSuspended);
    - nao altera `ReadOnlyProjectScanner` nem nenhum probe existente;
    - nao le parametro de dispositivo e nao toca `ScriptDriverDeviceObject`:
      enumerar a arvore NAO autoriza ler parametro. Isso exige contrato
      proprio, ainda nao escrito;
    - nao toca `device_repository` nem nada de `online`;
    - nao compila, nao salva, nao fecha, nao cria e nao modifica objeto.

LIMITES
    Todos finitos e configuraveis. Profundidade ILIMITADA nao e oferecida:
    uma arvore ciclica ou um bug de navegacao viraria varredura infinita.
    `expected_root_count` e sempre None — a quantidade de raizes do
    `ExemploPlanta` (4) nao se presume em nenhum outro projeto.

STATUS E CODIGO DE SAIDA
    complete                  todas as raizes visitadas, nenhum erro de no
    complete_with_node_errors erros isolados, devidamente registrados
    truncated                 QUALQUER limite atingido — arvore INCOMPLETA
    fatal                     nao foi possivel varrer

    exit 0 -> complete / complete_with_node_errors
    exit 2 -> truncated
    exit 1 -> fatal

    ATENCAO: que o MT8500.exe PROPAGUE este codigo para o processo host nunca
    foi observado — so `exit_code=0` apareceu ate hoje (docs/15). Portanto o
    `status` do manifesto e a fonte autoritativa; o exit code e best-effort.
    Nenhuma varredura `truncated` pode ser apresentada como arvore completa.

EXECUCAO (pelo USUARIO, nunca pelo agente, com a UI VISIVEL, sobre uma COPIA
DESCARTAVEL, offline, sem salvar):

    MT8500.exe --project="<...>\_descartavel\<Projeto> COPIA.project"
               --runscript="<repo>\scripts\mastertool\probes\21_scan_project_tree_full.py"
               --scriptargs:"--output=C:\scan-out --max-depth=32"

    O caminho de --output NAO pode conter espaco: o probe 15 observou que o
    MT8500 QUEBRA valores com espaco em `--scriptargs`. O script recusa
    antecipadamente em vez de gravar no lugar errado.
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

DEFAULT_MAX_DEPTH = 32
DEFAULT_MAX_TOTAL_NODES = 20000
DEFAULT_MAX_CHILDREN_PER_NODE = 1024

STATUS_COMPLETE = "complete"
STATUS_COMPLETE_WITH_NODE_ERRORS = "complete_with_node_errors"
STATUS_TRUNCATED = "truncated"
STATUS_FATAL = "fatal"

EXIT_BY_STATUS = {
    STATUS_COMPLETE: 0,
    STATUS_COMPLETE_WITH_NODE_ERRORS: 0,
    STATUS_TRUNCATED: 2,
    STATUS_FATAL: 1,
}


# Argumentos, validacao de caminho e identidade do runtime vivem em
# `common/probe_cli.py`: sao identicos entre os probes que recebem
# `--scriptargs`, e la eles tem teste. Probe que roda dentro do MasterTool
# nao e testavel; modulo comum e.

def _project_sha256(project_path):
    if not project_path:
        return None, "caminho do projeto indisponivel"
    try:
        from common import checksums
        if not os.path.isfile(project_path):
            return None, "arquivo do projeto nao encontrado: %s" % project_path
        return checksums.sha256_file(project_path), None
    except Exception as exc:                                   # noqa: BLE001
        return None, repr(exc)


def _observed_depth(flat_nodes):
    depth = 0
    for node in flat_nodes or []:
        try:
            if node["depth"] > depth:
                depth = node["depth"]
        except Exception:                                      # noqa: BLE001
            continue
    return depth


def _classify(scan_result, flat_nodes):
    """truncated tem precedencia sobre erro de no: uma arvore incompleta nao
    pode ser reportada como completa so porque os nos visitados foram bem."""
    limits = scan_result.get("limits") or {}
    hit = sorted([k for k, v in limits.items() if v])
    if hit:
        return STATUS_TRUNCATED, hit
    if scan_result.get("errors"):
        return STATUS_COMPLETE_WITH_NODE_ERRORS, hit
    if not flat_nodes:
        return STATUS_FATAL, hit
    return STATUS_COMPLETE, hit


def main():
    print("=" * 68)
    print("[INFO] probes/21_scan_project_tree_full.py — SOMENTE LEITURA")
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel: nao da para localizar os modulos "
              "comuns nem provar que a saida esta fora do repo")
        sys.exit(EXIT_BY_STATUS[STATUS_FATAL])
        return

    try:
        from common import (file_io, probe_cli, project_access,
                            read_only_project_scanner)
    except Exception as exc:                                   # noqa: BLE001
        print("[FATAL] falha ao importar modulos comuns: %r" % (exc,))
        sys.exit(EXIT_BY_STATUS[STATUS_FATAL])
        return

    problems = []
    argv = list(sys.argv or [])
    out_root = probe_cli.validate_output_path(
        probe_cli.find_arg(argv, "output"), REPO_ROOT, problems)
    max_depth = probe_cli.positive_int(
        probe_cli.find_arg(argv, "max-depth"),
        DEFAULT_MAX_DEPTH, "--max-depth", problems)
    max_total = probe_cli.positive_int(
        probe_cli.find_arg(argv, "max-total-nodes"),
        DEFAULT_MAX_TOTAL_NODES, "--max-total-nodes", problems)
    max_children = probe_cli.positive_int(
        probe_cli.find_arg(argv, "max-children-per-node"),
        DEFAULT_MAX_CHILDREN_PER_NODE, "--max-children-per-node", problems)

    if problems:
        print("[FATAL] argumentos recusados:")
        for item in problems:
            print("        - %s" % item)
        print("[FATAL] status=%s" % STATUS_FATAL)
        sys.exit(EXIT_BY_STATUS[STATUS_FATAL])
        return

    manifest = {
        "schema_version": "1.1",
        "script": "probes/21_scan_project_tree_full.py",
        "mode": "read_only",
        "generated_at": file_io.iso_now(),
        # argv CRU, ao lado de limits_configured. Sem ele, um limite igual ao
        # default e ambiguo: nao da para distinguir "o argumento chegou" de "o
        # argumento foi descartado e o default valeu" — e as duas hipoteses tem
        # causas opostas (defeito do parser aqui dentro, ou perda no
        # --scriptargs/launcher la fora). Medido em 2026-07-31 no MasterTool X.
        "argv": list(argv),
        "mastertool": probe_cli.runtime_identity(),
        "project": {"path": None, "sha256": None, "sha256_error": None},
        "limits_configured": {
            "max_depth": max_depth,
            "max_total_nodes": max_total,
            "max_children_per_node": max_children,
            "expected_root_count": None,
        },
        "observed": {"root_count": None, "total_nodes": None, "max_depth": None},
        "limits_hit": None,
        "node_errors": [],
        "node_error_count": 0,
        "statistics": None,
        "safety_declaration": None,
        "status": STATUS_FATAL,
        "fatal_error": None,
    }

    run_dir = None
    try:
        project, err = project_access.get_primary_project(globals())
        if project is None:
            manifest["fatal_error"] = "sem projeto primario: %s" % (err,)
            raise RuntimeError(manifest["fatal_error"])

        project_path = project_access.get_project_path(project)
        manifest["project"]["path"] = project_path
        digest, digest_err = _project_sha256(project_path)
        manifest["project"]["sha256"] = digest
        manifest["project"]["sha256_error"] = digest_err

        slug = "projeto"
        if project_path:
            slug = os.path.splitext(os.path.basename(project_path))[0]
        run_dir = file_io.new_export_dir(out_root, file_io.safe_filename(slug) + "_tree")
        print("[INFO] saida: %s" % run_dir)
        print("[INFO] limites: depth=%d nodes=%d children=%d expected_root_count=None"
              % (max_depth, max_total, max_children))

        scanner = read_only_project_scanner.ReadOnlyProjectScanner(
            max_depth=max_depth,
            max_total_nodes=max_total,
            max_children_per_node=max_children,
            expected_root_count=None)
        scan_result = scanner.scan(project)

        flat_nodes = read_only_project_scanner.flatten_tree(scan_result["tree"])
        node_indexes = read_only_project_scanner.build_node_indexes(flat_nodes)

        status, hit = _classify(scan_result, flat_nodes)
        manifest["status"] = status
        manifest["limits_hit"] = scan_result.get("limits")
        manifest["node_errors"] = scan_result.get("errors") or []
        manifest["node_error_count"] = len(manifest["node_errors"])
        manifest["statistics"] = scan_result.get("statistics")
        manifest["safety_declaration"] = scan_result.get("safety_declaration")
        manifest["observed"]["total_nodes"] = len(flat_nodes)
        manifest["observed"]["max_depth"] = _observed_depth(flat_nodes)
        try:
            manifest["observed"]["root_count"] = len(scan_result["tree"]["children"])
        except Exception:                                      # noqa: BLE001
            manifest["observed"]["root_count"] = None

        file_io.write_json(os.path.join(run_dir, "project-tree.json"), scan_result["tree"])
        file_io.write_json(os.path.join(run_dir, "flat-nodes.json"), flat_nodes)
        file_io.write_json(os.path.join(run_dir, "node-indexes.json"), node_indexes)
        file_io.write_json(os.path.join(run_dir, "errors.json"), manifest["node_errors"])

        print("[INFO] nos: %d   profundidade maxima: %s   raizes: %s"
              % (manifest["observed"]["total_nodes"],
                 manifest["observed"]["max_depth"],
                 manifest["observed"]["root_count"]))
        if status == STATUS_TRUNCATED:
            print("[AVISO] VARREDURA TRUNCADA — limites atingidos: %s" % ", ".join(hit))
            print("[AVISO] esta arvore esta INCOMPLETA e nao pode ser "
                  "apresentada como completa.")
        elif status == STATUS_COMPLETE_WITH_NODE_ERRORS:
            print("[AVISO] %d no(s) com erro isolado, registrados em errors.json"
                  % manifest["node_error_count"])
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
            run_dir = file_io.new_export_dir(out_root, "scan_fatal")
        file_io.write_json(os.path.join(run_dir, "manifest.json"), manifest)
        lines = [
            "# Varredura recursiva somente leitura da arvore do projeto", "",
            "- Script: `probes/21_scan_project_tree_full.py`",
            "- Status: **%s**" % manifest["status"],
            "- MasterTool: `%s` (file_version=%s)"
            % (manifest["mastertool"].get("executable"),
               manifest["mastertool"].get("file_version")),
            "- Projeto: `%s`" % manifest["project"]["path"],
            "- SHA-256 do arquivo aberto: `%s`" % manifest["project"]["sha256"],
            "- Limites: depth=%s nodes=%s children=%s (expected_root_count=None)"
            % (max_depth, max_total, max_children),
            "- Observado: raizes=%s, nos=%s, profundidade maxima=%s"
            % (manifest["observed"]["root_count"],
               manifest["observed"]["total_nodes"],
               manifest["observed"]["max_depth"]),
            "- Limites atingidos: `%s`" % (manifest["limits_hit"],),
            "- Nos com erro: %d" % manifest["node_error_count"],
            "",
            "Enumerar a arvore NAO autoriza ler parametro de dispositivo.",
        ]
        file_io.write_text(os.path.join(run_dir, "report.md"), "\n".join(lines) + "\n")
        print("[OK] artefatos em: %s" % run_dir)
    except Exception as exc:                                   # noqa: BLE001
        print("[ERROR] falha ao gravar manifesto: %r" % (exc,))
        manifest["status"] = STATUS_FATAL

    code = EXIT_BY_STATUS.get(manifest["status"], EXIT_BY_STATUS[STATUS_FATAL])
    print("[INFO] status=%s exit=%d (o status do manifesto e autoritativo; a "
          "propagacao do exit code pelo MT8500 nunca foi observada)"
          % (manifest["status"], code))
    print("=" * 68)
    sys.exit(code)


main()

# -*- coding: utf-8 -*-
"""05_children_collection.py — PRIMEIRA chamada de metodo na arvore.

Vive em `scripts/mastertool/probes/` desde a criacao (2026-07-23) — nao
colide com `05_export_selected_object.py`, que mantem sua numeracao
funcional original em `scripts/mastertool/`.

Escopo aprovado (2026-07-23), o primeiro metodo de navegacao efetivamente
chamado neste projeto:

    children = projects.primary.get_children(False)

Marco previsto apos `is_root`/`handle`/`active_application` confirmados:
obter a colecao de filhos, confirmar SEU tipo e tamanho, SEM iterar nenhum
elemento ainda (isso fica para um ciclo separado).

Operacoes PERMITIDAS nesta execucao:
  - resolver `projects.primary` (reutilizado, sem re-resolver);
  - chamar `get_children(False)` UMA UNICA vez;
  - verificar se o retorno e nulo;
  - registrar o tipo Python (`capabilities.python_type_info`);
  - registrar o tipo CLR pelo helper ja testado (`capabilities.dotnet_type_info`);
  - ler `Count` UMA UNICA vez, DESDE QUE a reflection sobre o TIPO do
    retorno (via `GetType().GetInterfaces()` — metadados, nao dados)
    confirme que ele implementa `ICollection` ou `IList`;
  - gerar relatorio e checksums.

Operacoes PROIBIDAS nesta execucao:
  - iterar a colecao (nenhum `for`, nenhuma list comprehension);
  - acessar qualquer indice (`children[0]`);
  - chamar `GetEnumerator()`;
  - usar `list(children)`;
  - usar `repr()`/`str()`/formatacao da colecao (representacao SEMPRE via
    `capabilities.build_representation()`, que nunca toca a instancia se o
    tipo nao for confirmado seguro);
  - acessar propriedades de elementos;
  - chamar `find()`, `active_application`, ou navegar recursivamente;
  - reativar `tree_walker.py`.

Contagem: `count = getattr(children, "Count")` — SEM fallback para
`len(children)` (o protocolo dinamico pode encaminhar `len()` de forma nao
explicita/imprevisivel) e SEM fallback para `Length` ou qualquer outro nome
se `Count` falhar. `AttributeError` -> unsupported; qualquer outra excecao ->
unknown. O sucesso de `get_children(False)` e a falha de `Count` sao
registrados SEPARADAMENTE — a colecao pode ser confirmada mesmo sem sua
quantidade.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys
import time

# Bootstrap (script vive em scripts/mastertool/probes/): sys.path recebe a
# pasta 'mastertool' (onde vive 'common/'), nao a propria pasta 'probes/'.
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
LOG_ROOT = os.path.join(REPO_ROOT, "workspace", "logs") if REPO_ROOT else None

COLLECTION_COUNT_MEMBER = "Count"
COLLECTION_COUNT_EVIDENCE = (
    "ICollection<T>/IList<T>.Count — membro padrao e documentado da BCL do "
    ".NET (nao do catalogo estatico customizado deste projeto). Sondado "
    "SOMENTE se GetType().GetInterfaces() confirmar ICollection/IList no "
    "tipo runtime real do retorno de get_children().")

# Interfaces .NET cujo nome (curto, via Type.Name) confirma que a colecao
# suporta .Count de forma padrao e documentada. Checagem por PREFIXO porque
# genericos aparecem como "ICollection`1"/"IList`1".
_COUNT_BEARING_INTERFACE_PREFIXES = ("ICollection", "IList")


def _implements_count_bearing_interface(value):
    """Reflection sobre o TIPO do valor (GetType().GetInterfaces()) — NUNCA
    toca os DADOS/elementos da colecao. Retorna (implementa: bool,
    nomes_interfaces: list, erro: str|None)."""
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


def main():
    print("=" * 60)
    print("[INFO] probes/05_children_collection.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. UMA chamada: get_children(False). "
         "Sem iteracao, sem stringificar colecao/elementos, sem fallback.")

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[BLOQUEADO] __file__ indisponivel: execucao recusada.")
        print("=" * 60)
        return

    try:
        from common import capabilities, compatibility, checksums, file_io, project_access
    except Exception as exc:
        print("[ERROR] Falha ao importar modulos comuns: %r" % (exc,))
        print("=" * 60)
        return

    report = {
        "schema_version": "1.0",
        "script": "probes/05_children_collection.py",
        "generated_at": file_io.iso_now(),
        "mode": "read_only",
        "baseline": {
            "projects.primary": {
                "previously_confirmed": False,
                "note": "Reutilizado sem re-resolver (ja confirmado em execucoes anteriores).",
            }
        },
        "primary_project_dotnet_type": None,
        "invocation": {
            "method": "get_children",
            "arguments": [False],
            "call_count": 0,
            "state": None,
            "started_at": None,
            "finished_at": None,
            "duration_ms": None,
            "exception_type": None,
            "exception_message": None,
            "traceback": None,
        },
        "collection": {
            "is_null": None,
            "python_type": {"module": None, "name": None},
            "dotnet_type": {"full_name": None, "available": False},
            "representation": None,
            "stringification_performed": False,
            "iteration_performed": False,
            "implements_count_bearing_interface": None,
            "type_interfaces_observed": [],
            "type_interface_check_error": None,
        },
        "count_probe": {
            "member": COLLECTION_COUNT_MEMBER,
            "evidence": COLLECTION_COUNT_EVIDENCE,
            "attempted": False,
            "state": None,
            "value": None,
            "exception_type": None,
            "exception_message": None,
            "duration_ms": None,
        },
        "errors": [],
        "safety_declaration": {
            "project_write": False,
            "project_save": False,
            "project_close": False,
            "object_creation": False,
            "object_modification": False,
            "collection_iteration": False,
            "element_access": False,
            "recursive_navigation": False,
            "compilation": False,
            "online_access": False,
            "device_repository_access": False,
            "download": False,
            "force": False,
            "note": ("Primeira chamada de metodo de navegacao autorizada "
                     "neste projeto. Uma unica chamada, sem argumentos "
                     "alternativos, sem iteracao/indexacao dos elementos "
                     "retornados. Count so tentado apos confirmar via "
                     "GetType().GetInterfaces() que o tipo retornado "
                     "implementa ICollection/IList."),
        },
    }

    def _write_artifacts():
        run_dir = file_io.new_export_dir(LOG_ROOT, "05_children_collection")
        file_io.write_json(os.path.join(run_dir, "report.json"), report)

        md = ["# Probe de coleção de filhos — get_children(False)", "",
             "Modo: **somente leitura**. Uma única chamada de método, sem "
             "iteração, sem stringificar coleção/elementos, sem fallback.",
             "", "## Invocação",
             "- Método: `%s(%s)`" % (report["invocation"]["method"],
                                    report["invocation"]["arguments"]),
             "- Chamadas realizadas: %s" % report["invocation"]["call_count"],
             "- Estado: **%s**" % report["invocation"]["state"],
             "- Duração: %s ms" % report["invocation"]["duration_ms"]]
        if report["invocation"].get("exception_type"):
            md.append("- Exceção: `%s`: %s" % (report["invocation"]["exception_type"],
                                              report["invocation"]["exception_message"]))
        col = report["collection"]
        md += ["", "## Coleção",
              "- is_null: %s" % col["is_null"],
              "- Tipo .NET: `%s`" % col["dotnet_type"]["full_name"],
              "- Tipo Python: `%s`" % col["python_type"]["name"],
              "- Implementa ICollection/IList (via GetType().GetInterfaces()): %s"
              % col["implements_count_bearing_interface"],
              "- Stringificação da instância realizada: %s" % col["stringification_performed"],
              "- Iteração realizada: %s" % col["iteration_performed"]]
        if col.get("representation"):
            rep = col["representation"]
            md.append("- Representação: modo=`%s`, valor=`%s`" % (rep["mode"], rep["value"]))
        cp = report["count_probe"]
        md += ["", "## Count",
              "- Evidência: %s" % cp["evidence"],
              "- Tentado: %s" % cp["attempted"],
              "- Estado: %s" % cp["state"],
              "- Valor: %s" % cp["value"],
              "- Duração: %s ms" % cp["duration_ms"]]
        if cp.get("exception_type"):
            md.append("- Exceção: `%s`: %s" % (cp["exception_type"], cp["exception_message"]))
        md += ["", "## Declaração de segurança"]
        for k, v in sorted(report["safety_declaration"].items()):
            if k == "note":
                continue
            md.append("- %s: %s" % (k, v))
        file_io.write_text(os.path.join(run_dir, "report.md"), "\n".join(md) + "\n")

        checksums.write_checksums_file(run_dir, os.path.join(run_dir, "checksums.sha256"))
        print("[OK] Relatorio gravado em: %s" % run_dir)

    project, err = project_access.get_primary_project(globals())
    if project is None:
        report["baseline"]["projects.primary"]["error"] = err
        print("[WARN] Projeto primario indisponivel: %s" % err)
        _write_artifacts()
        print("=" * 60)
        return

    report["baseline"]["projects.primary"]["previously_confirmed"] = True
    report["primary_project_dotnet_type"] = compatibility.safe_type_name(project)
    print("[OK] projects.primary reutilizado (tipo %s)."
         % report["primary_project_dotnet_type"])

    inv = report["invocation"]
    inv["started_at"] = file_io.iso_now()
    t0 = time.time()
    children = None
    try:
        inv["call_count"] = 1
        # UNICA chamada. Se falhar, a excecao e registrada e a execucao
        # encerra sem tentar outra assinatura.
        children = project.get_children(False)
        inv["state"] = "confirmed"
    except Exception as exc:
        inv["state"] = ("unsupported" if type(exc).__name__ == "AttributeError" else "unknown")
        inv["exception_type"] = type(exc).__name__
        inv["exception_message"] = compatibility.safe_repr(exc)
        try:
            import traceback as _tb
            inv["traceback"] = _tb.format_exc()
        except Exception:
            inv["traceback"] = "<traceback indisponivel>"
        report["errors"].append({"where": "get_children",
                                 "message": inv["exception_message"],
                                 "traceback": inv["traceback"]})
    finally:
        inv["finished_at"] = file_io.iso_now()
        inv["duration_ms"] = int((time.time() - t0) * 1000)

    print("[%s] get_children(False) -> %s (duracao=%sms)"
         % ("OK" if inv["state"] == "confirmed" else "INFO", inv["state"], inv["duration_ms"]))

    if inv["state"] == "confirmed":
        col = report["collection"]
        col["is_null"] = children is None
        if children is not None:
            col["python_type"] = capabilities.python_type_info(children)
            col["dotnet_type"] = capabilities.dotnet_type_info(children)
            # Representacao ESTRITA: nunca repr()/str()/ToString() no proprio
            # `children` (colecao de tipo desconhecido) — so tipo, a menos
            # que seja um primitivo (nao e o caso para uma colecao).
            col["representation"] = capabilities.build_representation(
                children, col["python_type"], col["dotnet_type"])
            col["stringification_performed"] = (
                col["representation"]["instance_stringification_performed"])

            implements, iface_names, iface_err = _implements_count_bearing_interface(children)
            col["implements_count_bearing_interface"] = implements
            col["type_interfaces_observed"] = iface_names
            col["type_interface_check_error"] = iface_err

            print("[INFO] tipo .NET=%s | implementa ICollection/IList=%s"
                 % (col["dotnet_type"]["full_name"], implements))

            cp = report["count_probe"]
            if implements:
                cp["attempted"] = True
                t1 = time.time()
                try:
                    # SEM fallback para len(children)/Length: so Count,
                    # SOMENTE porque a interface foi confirmada acima.
                    count_value = getattr(children, COLLECTION_COUNT_MEMBER)
                    cp["state"] = "confirmed"
                    cp["value"] = (count_value
                                   if isinstance(count_value, (bool, int, float)) else None)
                except Exception as exc:
                    cp["state"] = ("unsupported" if type(exc).__name__ == "AttributeError"
                                   else "unknown")
                    cp["exception_type"] = type(exc).__name__
                    cp["exception_message"] = compatibility.safe_repr(exc)
                    report["errors"].append({"where": "children.Count",
                                             "message": cp["exception_message"],
                                             "traceback": None})
                cp["duration_ms"] = int((time.time() - t1) * 1000)
                print("[%s] children.Count -> %s (valor=%s, duracao=%sms)"
                     % ("OK" if cp["state"] == "confirmed" else "INFO",
                        cp["state"], cp["value"], cp["duration_ms"]))
            else:
                print("[INFO] Count NAO tentado: tipo nao confirmou "
                     "ICollection/IList via GetType().GetInterfaces().")

    _write_artifacts()
    print("=" * 60)


main()

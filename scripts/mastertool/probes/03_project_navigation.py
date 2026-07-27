# -*- coding: utf-8 -*-
"""03_project_navigation.py — sondagem MINIMA de navegacao do projeto.

Movido para `scripts/mastertool/probes/` em 2026-07-23 (era
`03_probe_project_navigation.py` na raiz — renomeado para evitar colisao de
numeracao com `03_list_project_tree.py`, que mantem sua numeracao funcional
original). Corrigido nesta mudanca: a serializacao usava uma funcao local
(`_safe_value_for_json`) que chamava `str(value)` em QUALQUER valor nao
bool/int/float — mesmo padrao de violacao de politica encontrado depois em
`04_project_identity.py` (so nao se manifestou aqui porque `is_root`/`handle`
sao sempre primitivos). Trocado pelas funcoes centralizadas e testadas de
`common/capabilities.py` (`python_type_info`/`dotnet_type_info`/
`build_representation`), que nunca chamam repr()/str()/ToString() em
objetos CLR desconhecidos.

Escopo aprovado (2026-07-23, apos correcao conceitual):

    projects.primary          -> BASELINE ja confirmado (00_smoke_test.py),
                                  NAO re-testado aqui.
    projects.primary.is_root  -> NOVO probe (IScriptTreeObject.is_root)
    projects.primary.handle   -> NOVO probe (IScriptTreeObject.handle)

IMPORTANTE (correcao conceitual): `primary` NAO e membro de `IScriptProject`
que estivessemos testando aqui. `ScriptProjects.primary` (o global `projects`
tem uma propriedade `primary`) retorna `IExtendedObject<IScriptProject>` — e
o "baseline" ja confirmado. Ha TAMBEM uma propriedade booleana chamada
`primary` dentro de `IScriptProject` (coincidencia de nome, tipo diferente,
dono diferente) — para evitar ambiguidade no relatorio, essa propriedade
booleana NAO faz parte do escopo aprovado desta execucao e nao e testada.

Regras desta execucao:
  - NENHUM metodo com parametros e chamado;
  - `active_application`, `get_children`, `find`, `get_name`, `type`, `guid`,
    `is_folder`, documentos textuais: EXCLUIDOS deste ciclo;
  - NENHUMA compilacao, criacao, alteracao, salvamento, fechamento, operacao
    online ou consulta a device_repository;
  - NENHUMA varredura via dir() (nem para diagnostico nesta execucao);
  - NENHUMA tentativa de unwrap do ExtendedObject;
  - NENHUMA navegacao pelos filhos;
  - cada membro e testado isoladamente via `capabilities.probe_member`; uma
    falha em `is_root` NAO impede o teste de `handle` (ambos partem
    exclusivamente do `projects.primary` ja resolvido, sem re-resolver nada);
  - sem fallback para nomes alternativos em caso de falha;
  - `handle` NAO tem tipo presumido — registramos representacao ESTRITA
    (nunca repr/str/ToString em objeto desconhecido), tipo runtime real, se
    e nulo, e uma nota explicita de que a estabilidade entre execucoes NAO
    foi comprovada (nao usar como identificador persistente ate prova em
    contrario).

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

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

# Escopo aprovado: SOMENTE estes 2 novos membros, ambos sem parametros,
# ambos declarados em IScriptTreeObject (catalogo estatico:
# workspace/analysis/static-api/reachable-types.json).
NEW_PROBE_TARGETS = [
    {
        "member": "is_root",
        "interface_source": "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptTreeObject",
        "static_evidence": ("IScriptTreeObject.is_root : System.Boolean, sem "
                            "setter (assembly ScriptEngine3) — ver "
                            "workspace/analysis/static-api/reachable-types.json"),
    },
    {
        "member": "handle",
        "interface_source": "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptTreeObject",
        "static_evidence": ("IScriptTreeObject.handle : System.Int32 (tipo NAO "
                            "presumido nesta execucao), sem setter (assembly "
                            "ScriptEngine3) — ver "
                            "workspace/analysis/static-api/reachable-types.json"),
    },
]


def _enrich_probe_record(capabilities, record, target):
    """Enriquece o record de probe_member(capture_value=True) SEM um segundo
    getattr — usa record['raw_value'], ja capturado na unica tentativa.
    Representacao SEMPRE via capabilities.build_representation() (nunca
    repr()/str()/ToString() em objeto CLR desconhecido)."""
    record["interface_source"] = target["interface_source"]
    record["static_evidence"] = target["static_evidence"]
    record["python_type"] = {"module": None, "name": None}
    record["dotnet_type"] = {"full_name": None, "available": False}
    record["representation"] = None
    if record["state"] == "confirmed" and "raw_value" in record:
        value = record.pop("raw_value")  # nao serializavel em JSON de forma bruta
        record["python_type"] = capabilities.python_type_info(value)
        record["dotnet_type"] = capabilities.dotnet_type_info(value)
        record["representation"] = capabilities.build_representation(
            value, record["python_type"], record["dotnet_type"])
        if target["member"] == "handle":
            record["handle_details"] = {
                "is_null": value is None,
                "representation": record["representation"],
                "stability_note": ("Estabilidade do handle ENTRE execucoes "
                                   "NAO foi comprovada nesta rodada (uma "
                                   "unica execucao). NAO usar como "
                                   "identificador persistente do projeto "
                                   "ate confirmar estabilidade em runs "
                                   "separados."),
            }
    return record


def main():
    print("=" * 60)
    print("[INFO] probes/03_project_navigation.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. Escopo: projects.primary (baseline) + "
         "is_root/handle (novos probes). Sem parametros, sem dir(), sem "
         "unwrap, sem navegacao de filhos.")

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
        "script": "probes/03_project_navigation.py",
        "generated_at": file_io.iso_now(),
        "mode": "read_only",
        "baseline": {
            "projects.primary": {
                "previously_confirmed": False,
                "note": ("Acessor ja confirmado em runtime por "
                        "00_smoke_test.py (2026-07-23). NAO re-testado "
                        "nesta execucao."),
            }
        },
        "new_probes": {},
        "primary_project_dotnet_type": None,
        "errors": [],
        "safety_declaration": {
            "project_write": False,
            "project_save": False,
            "project_close": False,
            "object_creation": False,
            "object_modification": False,
            "compilation": False,
            "online_access": False,
            "device_repository_access": False,
            "download": False,
            "force": False,
            "note": ("Garantido por construcao deste arquivo: nao ha call "
                     "site para nenhuma dessas operacoes."),
        },
    }

    project, err = project_access.get_primary_project(globals())
    if project is None:
        report["baseline"]["projects.primary"]["error"] = err
        print("[WARN] Projeto primario indisponivel: %s" % err)
    else:
        report["baseline"]["projects.primary"]["previously_confirmed"] = True
        report["primary_project_dotnet_type"] = compatibility.safe_type_name(project)
        print("[OK] Baseline projects.primary confirmado nesta sessao "
             "tambem (tipo %s) — NAO recontado como novo probe."
             % report["primary_project_dotnet_type"])

        for target in NEW_PROBE_TARGETS:
            # capture_value=True: guarda o valor bruto para enriquecimento,
            # SEM uma segunda chamada getattr (unica tentativa real).
            record = capabilities.probe_member(
                project, "project", target["member"],
                capabilities.EVIDENCE_STATIC_METADATA, capture_value=True)
            record["source_object_dotnet_type"] = report["primary_project_dotnet_type"]
            record = _enrich_probe_record(capabilities, record, target)
            report["new_probes"][target["member"]] = record
            print("[%s] %s -> %s (dotnet_type=%s, python_type=%s, "
                 "duracao=%sms)"
                 % ("OK" if record["state"] == "confirmed" else "INFO",
                    target["member"], record["state"],
                    record["dotnet_type"]["full_name"], record["python_type"]["name"],
                    record["duration_ms"]))
            if record.get("exception_type"):
                report["errors"].append({
                    "where": target["member"],
                    "message": record["exception_message"],
                    "traceback": record["traceback"],
                })

    run_dir = file_io.new_export_dir(LOG_ROOT, "03_project_navigation")
    report_json_path = os.path.join(run_dir, "report.json")
    file_io.write_json(report_json_path, report)

    md = ["# Probe mínimo de navegação — is_root / handle", "",
         "Modo: **somente leitura**. Escopo aprovado: baseline "
         "`projects.primary` (não re-testado) + 2 novos probes "
         "(`is_root`, `handle`), sem parâmetros, sem `dir()`, sem unwrap, "
         "sem navegação de filhos.", "",
         "## Baseline",
         "- `projects.primary`: previously_confirmed = %s"
         % report["baseline"]["projects.primary"]["previously_confirmed"],
         "", "## Novos probes"]
    for member, record in sorted(report["new_probes"].items()):
        md.append("### `%s`" % member)
        md.append("- Interface de origem: `%s`" % record["interface_source"])
        md.append("- Tipo .NET do objeto-fonte: `%s`" % record["source_object_dotnet_type"])
        md.append("- Método de acesso: `%s`" % record["access_method"])
        md.append("- Estado: **%s**" % record["state"])
        if record.get("representation"):
            rep = record["representation"]
            md.append("- Representação: modo=`%s`, valor=`%s`"
                     % (rep["mode"], rep["value"]))
        md.append("- Tipo .NET do retorno (GetType().FullName): `%s`" % record["dotnet_type"]["full_name"])
        md.append("- Tipo Python/IronPython observado: `%s`" % record["python_type"]["name"])
        md.append("- Duração: %s ms" % record["duration_ms"])
        if record.get("exception_type"):
            md.append("- Exceção: `%s`: %s" % (record["exception_type"], record["exception_message"]))
        if record.get("handle_details"):
            hd = record["handle_details"]
            md.append("- Detalhes do handle: is_null=%s" % hd["is_null"])
            md.append("  - %s" % hd["stability_note"])
        md.append("")
    if report["errors"]:
        md.append("## Exceções (completas em report.json)")
        for e in report["errors"]:
            md.append("- em `%s`: %s" % (e["where"], e["message"]))
        md.append("")
    md.append("## Declaração de segurança")
    for k, v in sorted(report["safety_declaration"].items()):
        if k == "note":
            continue
        md.append("- %s: %s" % (k, v))
    report_md_path = os.path.join(run_dir, "report.md")
    file_io.write_text(report_md_path, "\n".join(md) + "\n")

    checksums_path = os.path.join(run_dir, "checksums.sha256")
    checksums.write_checksums_file(run_dir, checksums_path)

    print("[OK] Relatorio gravado em: %s" % run_dir)
    print("=" * 60)


main()

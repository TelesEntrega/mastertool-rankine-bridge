# -*- coding: utf-8 -*-
"""04_project_identity.py — sondagem MINIMA de identidade/aplicacao.

Movido para `scripts/mastertool/probes/` em 2026-07-23 (era
`04_probe_project_identity.py` na raiz — renomeado para evitar colisao de
numeracao com `04_export_project.py`, que mantem sua numeracao funcional
original).

Escopo aprovado (2026-07-23), 3 probes isolados sobre `projects.primary`
(o mesmo objeto ja confirmado — NAO re-resolvido, so reutilizado):

    projects.primary.type                (hipotese — ver nota abaixo)
    projects.primary.guid                (hipotese — ver nota abaixo)
    projects.primary.active_application  (confirmado por evidencia estatica
                                          em IScriptProject; getter/setter)

NOTA IMPORTANTE sobre `type`/`guid`: o catalogo estatico
(workspace/analysis/static-api/reachable-types.json) declara `type`/`guid`
em `IScriptObject`, NAO em `IScriptProject`/`IScriptTreeObject`. `IScriptProject`
so foi confirmado implementando `IScriptTreeObject` + `IBaseObject<T>` +
`IEquatable<T>` — nao `IScriptObject`. Testar `project.type`/`project.guid`
aqui e testar a HIPOTESE de que a classe CONCRETA por tras de
`projects.primary` tambem implementa `IScriptObject` (algo que a reflection
sobre a INTERFACE declarada nao pode confirmar nem negar). Um resultado
`confirmed` ou `unsupported` aqui e informacao nova, nao contradiz nada
registrado antes.

Regras desta execucao:
  - cada probe usa SOMENTE `getattr(project, nome)`, uma unica vez;
  - NENHUM fallback, NENHUM nome alternativo em caso de falha;
  - uma falha em um probe NAO impede os demais (todos partem do MESMO
    `projects.primary` ja resolvido, sem re-resolver nada);
  - `active_application`: SOMENTE leitura da propriedade. PROIBIDO usar o
    setter, atribuir None, trocar a aplicacao ativa, chamar QUALQUER metodo
    no objeto retornado, acessar filhos, acessar declaracao/implementacao,
    ou tentar resolver uma aplicacao alternativa. Se retornar um objeto,
    registramos SOMENTE: se e nulo, tipo runtime, representacao estrita, e o
    estado 'confirmed' — nao tocamos `.path`/`.type`/`.guid`/`.get_children()`
    nesse objeto retornado neste ciclo;
  - NENHUM metodo e chamado em lugar nenhum (nem `get_children`, nem `find`);
  - NENHUM dir(), NENHUM unwrap, NENHUMA navegacao de filhos;
  - NENHUMA compilacao, escrita, criacao, alteracao, operacao online.

Diagnostico de tipo (duas camadas, sem dir()/hasattr para decidir se
GetType existe — soh tenta direto, em try/except, e soh apos confirmar que
o getattr do MEMBRO teve sucesso):

    python_type: {module, name}   — de type(value)
    dotnet_type: {full_name, available} — de value.GetType().FullName,
                                           tentado uma unica vez

CORRECAO DE POLITICA (2026-07-23, apos primeira execucao real): a versao
original deste script usava repr()/str() para "representacao segura" de
objetos retornados — em IronPython, isso tipicamente invoca ToString() no
objeto .NET, o que e uma CHAMADA DE METODO na instancia, fora do escopo
aprovado ("proibido chamar metodos no objeto retornado"). ToString() e so
convencao (nao garantia tecnica) — uma classe pode sobrescreve-lo com
qualquer efeito. Corrigido: a politica de serializacao ESTRITA agora vive
centralizada em `common/capabilities.py` (`build_representation()`,
reutilizavel por outros scripts) e NUNCA chama repr()/str()/ToString()/
formatacao implicita em objetos CLR desconhecidos. So
serializa o valor em si quando e primitivo Python nativo ou um tipo .NET
CONFIRMADO como seguro (System.String/System.Guid/numericos — value types
selados da BCL, ToString() documentado e nao sobrescrevivel). Qualquer outro
tipo vira representacao 'type_only' (`<NomeDoTipo>`), montada so do nome do
tipo ja obtido via GetType(). A execucao real que motivou esta correcao
(2026-07-23, `active_application` confirmado) permanece VALIDA — o acesso
via getattr foi limpo; so a etapa de serializacao subsequente teve o desvio
de politica, sem efeito colateral observado. Os artefatos ORIGINAIS dessa
execucao foram perdidos por um incidente de limpeza separado (`rm -rf` com
glob por sufixo) e RECONSTRUIDOS a partir de conteudo ja capturado — ver
`docs/api/mastertool-api-observations.md` e o `POLICY-DEVIATION-NOTE.md` no
diretorio da execucao (`workspace/logs/2026-07-23_11-34-20_04_probe_project_identity/`).
Os arquivos reconstruidos NAO devem ser tratados como artefatos originais de
runtime (ver marcadores de proveniencia no proprio report.json).

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

# Escopo aprovado: exatamente estes 3 probes, cada um testado isoladamente.
PROBE_TARGETS = [
    {
        "member": "type",
        "interface_source": "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptObject (HIPOTESE)",
        "static_evidence": ("Declarado em IScriptObject.type : System.Guid, "
                            "NAO em IScriptProject/IScriptTreeObject — "
                            "testar aqui verifica se a classe concreta de "
                            "projects.primary tambem implementa IScriptObject "
                            "(nao confirmavel so pela interface declarada). "
                            "Ver workspace/analysis/static-api/reachable-types.json"),
    },
    {
        "member": "guid",
        "interface_source": "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptObject (HIPOTESE)",
        "static_evidence": ("Declarado em IScriptObject.guid : System.Guid, "
                            "mesma ressalva do membro 'type' acima — "
                            "hipotese, nao confirmacao estatica direta em "
                            "IScriptProject."),
    },
    {
        "member": "active_application",
        "interface_source": "_3S.CoDeSys.ScriptEngine.BasicFunctionality.IScriptProject",
        "static_evidence": ("IScriptProject.active_application : "
                            "IExtendedObject<IScriptObject>, COM setter "
                            "(can_write=True) — usamos SOMENTE o getter "
                            "nesta execucao; setter jamais e chamado."),
    },
]


def build_probe_record(capabilities, project, target):
    """Sonda UM membro isoladamente. Retorna um dict SEM usar 'type' como
    chave estrutural generica (usa 'member_name' e campos especificos)."""
    base = capabilities.probe_member(
        project, "project", target["member"], capabilities.EVIDENCE_STATIC_METADATA,
        capture_value=True)

    record = {
        "member_name": target["member"],
        "interface_source": target["interface_source"],
        "static_evidence": target["static_evidence"],
        "access_method": base["access_method"],
        "state": base["state"],
        "duration_ms": base["duration_ms"],
        "exception_type": base.get("exception_type"),
        "exception_message": base.get("exception_message"),
        "traceback": base.get("traceback"),
        "python_type": {"module": None, "name": None},
        "dotnet_type": {"full_name": None, "available": False},
    }

    if base["state"] == "confirmed" and "raw_value" in base:
        value = base["raw_value"]
        record["python_type"] = capabilities.python_type_info(value)
        record["dotnet_type"] = capabilities.dotnet_type_info(value)
        # Serializacao ESTRITA (politica centralizada em common/capabilities.py):
        # nunca repr()/str()/ToString() em objeto CLR desconhecido — so no
        # valor em si (primitivo) ou tipo confirmado seguro.
        record["representation"] = capabilities.build_representation(
            value, record["python_type"], record["dotnet_type"])
        record["is_null"] = value is None

        if target["member"] == "type":
            # Nao usar "type" como chave estrutural — campo especifico
            # pedido explicitamente: reported_object_type. So preenchido
            # quando o valor foi confirmado como System.Guid (serializavel);
            # caso contrario fica None (representacao so por tipo).
            record["reported_object_type"] = (
                record["representation"]["value"]
                if record["representation"]["mode"] == "value" else None)

        elif target["member"] == "guid":
            record["guid_details"] = {
                "is_null": value is None,
                "confirmed_as_system_guid": record["dotnet_type"].get("full_name") == "System.Guid",
                "representation": record["representation"],
            }

        elif target["member"] == "active_application":
            # SOMENTE leitura registrada. NADA MAIS e feito com `value`:
            # nenhum metodo chamado, nenhum filho acessado, nenhum
            # .path/.type/.guid/.get_children() neste objeto. A
            # representacao NAO chama repr/str/ToString (objeto CLR
            # complexo, desconhecido) — so tipo.
            record["active_application_details"] = {
                "is_null": value is None,
                "representation": record["representation"],
                "capability_state": "confirmed",
                "property_access": "compliant",
                "post_access_stringification": "not_performed",
                "side_effect_observed": False,
                "note": ("Somente o getter foi lido. Setter NAO foi usado. "
                        "Nenhum metodo ou membro do objeto retornado foi "
                        "acessado neste ciclo. Representacao estrita: sem "
                        "repr()/str()/ToString() no objeto (2026-07-23)."),
            }
    return record


def main():
    print("=" * 60)
    print("[INFO] probes/04_project_identity.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. Escopo: type/guid/active_application "
         "sobre projects.primary. Sem setter, sem metodos, sem filhos, "
         "sem dir(), sem navegacao de arvore.")

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
        "script": "probes/04_project_identity.py",
        "generated_at": file_io.iso_now(),
        "mode": "read_only",
        "baseline": {
            "projects.primary": {
                "previously_confirmed": False,
                "note": "Ja confirmado por 00_smoke_test.py; reutilizado aqui sem re-resolver.",
            }
        },
        "primary_project_dotnet_type": None,
        "probes": {},
        "errors": [],
        "safety_declaration": {
            "active_application_set": False,
            "project_write": False,
            "object_modification": False,
            "tree_navigation": False,
            "compilation": False,
            "online_access": False,
            "device_repository_access": False,
            "project_save": False,
            "project_close": False,
            "download": False,
            "force": False,
            "alternative_names_tried_on_failure": False,
            "methods_called_on_returned_objects": False,
            "note": ("Garantido por construcao deste arquivo: nao ha call "
                     "site para nenhuma dessas operacoes; active_application "
                     "e lido apenas via getattr, setter nunca invocado."),
        },
    }

    project, err = project_access.get_primary_project(globals())
    if project is None:
        report["baseline"]["projects.primary"]["error"] = err
        print("[WARN] Projeto primario indisponivel: %s" % err)
    else:
        report["baseline"]["projects.primary"]["previously_confirmed"] = True
        report["primary_project_dotnet_type"] = compatibility.safe_type_name(project)
        print("[OK] projects.primary reutilizado (tipo %s)."
             % report["primary_project_dotnet_type"])

        for target in PROBE_TARGETS:
            record = build_probe_record(capabilities, project, target)
            report["probes"][target["member"]] = record
            print("[%s] %s -> %s (python_type=%s, duracao=%sms)"
                 % ("OK" if record["state"] == "confirmed" else "INFO",
                    target["member"], record["state"],
                    record["python_type"]["name"], record["duration_ms"]))
            if record.get("exception_type"):
                report["errors"].append({
                    "where": target["member"],
                    "message": record["exception_message"],
                    "traceback": record["traceback"],
                })

    run_dir = file_io.new_export_dir(LOG_ROOT, "04_project_identity")
    file_io.write_json(os.path.join(run_dir, "report.json"), report)

    md = ["# Probe mínimo de identidade/aplicação — type / guid / active_application", "",
         "Modo: **somente leitura**. Cada probe isolado, sem setter, sem "
         "métodos, sem filhos, sem `dir()`, sem navegação de árvore.", "",
         "## Baseline",
         "- `projects.primary`: previously_confirmed = %s"
         % report["baseline"]["projects.primary"]["previously_confirmed"],
         "", "## Probes"]
    for member, record in report["probes"].items():
        md.append("### `%s`" % record["member_name"])
        md.append("- Interface de origem: `%s`" % record["interface_source"])
        md.append("- Estado: **%s**" % record["state"])
        md.append("- Tipo Python: módulo=`%s`, nome=`%s`"
                  % (record["python_type"]["module"], record["python_type"]["name"]))
        md.append("- Tipo .NET: full_name=`%s`, disponível=%s"
                  % (record["dotnet_type"]["full_name"], record["dotnet_type"]["available"]))
        md.append("- Duração: %s ms" % record["duration_ms"])
        if record.get("representation"):
            rep = record["representation"]
            md.append("- Representação: modo=`%s`, valor=`%s`, stringificação_da_instância=%s"
                     % (rep["mode"], rep["value"], rep["instance_stringification_performed"]))
        if "reported_object_type" in record:
            md.append("- reported_object_type: `%s`" % record["reported_object_type"])
        if "guid_details" in record:
            gd = record["guid_details"]
            md.append("- GUID: is_null=%s, confirmed_as_system_guid=%s"
                     % (gd["is_null"], gd["confirmed_as_system_guid"]))
        if "active_application_details" in record:
            ad = record["active_application_details"]
            md.append("- active_application: is_null=%s, capability_state=%s, "
                     "property_access=%s, post_access_stringification=%s, side_effect_observed=%s"
                     % (ad["is_null"], ad["capability_state"], ad["property_access"],
                        ad["post_access_stringification"], ad["side_effect_observed"]))
            md.append("  - %s" % ad["note"])
        if record.get("exception_type"):
            md.append("- Exceção: `%s`: %s" % (record["exception_type"], record["exception_message"]))
        md.append("")
    md.append("## Declaração de segurança")
    for k, v in sorted(report["safety_declaration"].items()):
        if k == "note":
            continue
        md.append("- %s: %s" % (k, v))
    file_io.write_text(os.path.join(run_dir, "report.md"), "\n".join(md) + "\n")

    checksums.write_checksums_file(run_dir, os.path.join(run_dir, "checksums.sha256"))

    print("[OK] Relatorio gravado em: %s" % run_dir)
    print("=" * 60)


main()

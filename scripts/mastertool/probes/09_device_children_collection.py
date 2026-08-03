# -*- coding: utf-8 -*-
"""09_device_children_collection.py — PRIMEIRO teste de navegacao
hierarquica REAL (2 niveis): projects.primary -> Device -> get_children(False).

Motivo (2026-07-23): `active_application` e um atalho direto fornecido pelo
projeto — nao prova que a descida pela arvore funciona de forma GENERICA
(pelo mesmo caminho que qualquer outro no usaria). `Device` (children[1] da
raiz, ja identificado nos probes 06/07/08) e o no escolhido para validar
isso, porque exige repetir, em um SEGUNDO nivel, exatamente a mesma cadeia
ja confirmada no primeiro nivel (get_children(False) -> Count -> indexador).

Escopo aprovado (2026-07-23):

    project = projects.primary                    # reutilizado
    root_children = project.get_children(False)    # 1 chamada
    device = root_children[1]                      # SO o indice 1
    device_name = device.get_name(False)           # revalidacao de identidade
    device.type / device.guid                      # revalidacao de identidade
    device_children = device.get_children(False)   # 1 chamada, SO se identidade bater
    device_children.Count                          # 1 leitura

O indice 1 SO pode ser acessado apos revalidar (nesta MESMA execucao, sem
reaproveitar dados de probes anteriores): `root_children.Count == 4`,
`root_children[1].get_name(False) == "Device"`, `root_children[1].type ==
225bfe47-7336-4dbc-9419-4105a7c831fa` e `root_children[1].guid ==
ec2ca054-836f-492f-a95f-f296c4785352`. Qualquer divergencia registra
`device_identity_mismatch` e ENCERRA sem chamar `device.get_children(False)`.

Escopo autorizado SOMENTE no no `Device`, apos identidade confirmada:
  - `device.get_children(False)`, 1 chamada;
  - verificar se o retorno e nulo;
  - registrar tipo Python/tipo .NET (via capabilities, sem repr/str/ToString);
  - confirmar via GetType().GetInterfaces() (metadados, nao dados) se
    implementa ICollection/IList;
  - ler `Count` UMA UNICA vez, SOMENTE se a interface foi confirmada;
  - `Count < 0` -> invalido (rejeitado); `Count > max_device_children` (64)
    -> invalido (rejeitado, limite de seguranca); `Count == 0` -> resultado
    valido (colecao vazia); `0 < Count <= 64` -> confirmado, SEM acessar
    nenhum elemento.

PROIBIDO nesta execucao: indexar os filhos de Device; iterar a colecao de
Device; ler nomes dos filhos de Device; acessar active_application; usar
find(); navegar recursivamente; acessar configuracao de hardware; acessar
documentos textuais; acessar dispositivos online; qualquer escrita,
compilacao, salvamento ou exportacao; repr()/str()/ToString() em objeto CLR
desconhecido (representacao SEMPRE via
common/capabilities.py: build_representation()).

Quantidade maxima de chamadas/leituras, cada uma SEM fallback para nome
alternativo: projects.primary (1 resolucao), get_children (1, na raiz) + (1,
em Device) = 2 chamadas de metodo distintas, root_children.Count (1),
root_children[1] (1), device.get_name(False) (1), device.type (1),
device.guid (1), device_children.Count (1, condicional a interface
confirmada).

`tree_walker.py` NAO e reativado por este script.

Compatibilidade: IronPython 2.7.
"""
from __future__ import print_function

import datetime
import os
import sys

EXPECTED_ROOT_COUNT = 4
DEVICE_INDEX = 1
EXPECTED_DEVICE_NAME = "Device"
EXPECTED_DEVICE_TYPE_GUID = "225bfe47-7336-4dbc-9419-4105a7c831fa"
EXPECTED_DEVICE_OBJECT_GUID = "ec2ca054-836f-492f-a95f-f296c4785352"
MAX_DEVICE_CHILDREN = 64

# Interfaces .NET cujo nome (curto, via Type.Name) confirma que a colecao
# suporta .Count de forma padrao e documentada. Mesma checagem usada em
# probes/05_children_collection.py — checagem por PREFIXO porque genericos
# aparecem como "ICollection`1"/"IList`1". So reflection sobre o TIPO
# (metadados), nunca sobre os dados/elementos da colecao.
_COUNT_BEARING_INTERFACE_PREFIXES = ("ICollection", "IList")

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


def _empty_type_info():
    return {"module": None, "name": None}


def _empty_dotnet_info():
    return {"full_name": None, "available": False}


def _implements_count_bearing_interface(value):
    """Reflection sobre o TIPO do valor (GetType().GetInterfaces()) — NUNCA
    toca os DADOS/elementos da colecao. Identica a
    probes/05_children_collection.py. Retorna (implementa: bool,
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
    print("[INFO] probes/09_device_children_collection.py")
    print("[INFO] Data/hora: %s" % datetime.datetime.now().isoformat())
    print("[INFO] MODO SOMENTE LEITURA. root_children[1] revalidado (Count==4, "
         "nome/type/guid batem) -> SO ENTAO device.get_children(False) 1x -> "
         "is_null/tipo/interface/Count. Sem indexar/iterar filhos de Device, "
         "sem active_application, sem find(), sem recursao.")

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
        "script": "probes/09_device_children_collection.py",
        "generated_at": file_io.iso_now(),
        "mode": "read_only",
        "limits": {
            "expected_root_count": EXPECTED_ROOT_COUNT,
            "max_device_children": MAX_DEVICE_CHILDREN,
        },
        "root_validation": {
            "get_children_call_count": 0,
            "get_children_state": None,
            "count_state": None,
            "count": None,
            "count_matches_expected": None,
            "device_index": DEVICE_INDEX,
            "element_access_state": None,
            "identity": {
                "name": {"state": None, "value": None, "expected": EXPECTED_DEVICE_NAME,
                         "matches_expected": None},
                "type_guid": {"state": None, "value": None, "expected": EXPECTED_DEVICE_TYPE_GUID,
                              "matches_expected": None},
                "object_guid": {"state": None, "value": None, "expected": EXPECTED_DEVICE_OBJECT_GUID,
                                "matches_expected": None},
            },
            "identity_confirmed": False,
        },
        "device": {
            "name": None,
            "type_guid": None,
            "object_guid": None,
        },
        "children_collection": {
            "attempted": False,
            "get_children_call_count": 0,
            "state": None,
            "is_null": None,
            "python_type": _empty_type_info(),
            "dotnet_type": _empty_dotnet_info(),
            "representation": None,
            "stringification_performed": False,
            "implements_count_bearing_interface": None,
            "type_interfaces_observed": [],
            "type_interface_check_error": None,
            "count_probe": {
                "attempted": False,
                "state": None,
                "value": None,
                "valid": None,
                "validation_error": None,
            },
            "iteration_performed": False,
            "element_access_performed": False,
        },
        "errors": [],
        "safety_declaration": {
            "project_write": False,
            "project_save": False,
            "project_close": False,
            "object_creation": False,
            "object_modification": False,
            "device_configuration_access": False,
            "device_repository_access": False,
            "collection_iteration": False,
            "device_child_element_access": False,
            "recursive_navigation": False,
            "text_document_access": False,
            "compilation": False,
            "online_access": False,
            "download": False,
            "force": False,
            "root_bounded_index_access": True,
            "device_children_collection_access": True,
            "note": ("Garantido por construcao: root_children[1] so e "
                     "acessado apos Count==4 confirmado; device.get_children"
                     "(False) so e chamado apos nome/type/guid de "
                     "root_children[1] baterem com os valores esperados "
                     "(revalidados nesta execucao, nao reaproveitados de "
                     "probes anteriores). Nenhum filho de Device e "
                     "indexado, iterado ou lido nesta execucao."),
        },
    }

    def _finish():
        run_dir = file_io.new_export_dir(LOG_ROOT, "09_device_children_collection")
        file_io.write_json(os.path.join(run_dir, "report.json"), report)

        rv = report["root_validation"]
        dv = report["device"]
        cc = report["children_collection"]
        md = ["# Probe de navegação hierárquica — filhos de Device", "",
             "Modo: **somente leitura**. `root_children[1]` revalidado "
             "(Count==4, nome/type/guid batem) → `device.get_children(False)` "
             "1x → is_null/tipo/interface/Count. Sem indexar/iterar filhos "
             "de Device, sem `active_application`, sem `find()`, sem "
             "recursão.",
             "", "## Validação da raiz",
             "- `get_children(False)`: estado=**%s** | chamadas=%s"
             % (rv["get_children_state"], rv["get_children_call_count"]),
             "- `Count`: estado=%s | valor=%s | esperado=%s | bate=%s"
             % (rv["count_state"], rv["count"], report["limits"]["expected_root_count"],
                rv["count_matches_expected"]),
             "- Acesso a `root_children[%s]`: estado=%s"
             % (rv["device_index"], rv["element_access_state"]),
             "", "### Identidade revalidada"]
        for field_name, field in sorted(rv["identity"].items()):
            md.append("- `%s`: estado=%s valor=%s esperado=%s bate=%s"
                     % (field_name, field["state"], field["value"], field["expected"],
                        field["matches_expected"]))
        md.append("- **Identidade confirmada**: %s" % rv["identity_confirmed"])

        md += ["", "## Device",
              "- Nome: %s | type_guid: %s | object_guid: %s"
              % (dv["name"], dv["type_guid"], dv["object_guid"])]

        md += ["", "## Coleção de filhos de Device (`device.get_children(False)`)",
              "- Tentativa: %s | chamadas: %s | Estado: **%s**"
              % (cc["attempted"], cc["get_children_call_count"], cc["state"]),
              "- is_null: %s" % cc["is_null"],
              "- Tipo .NET: `%s`" % cc["dotnet_type"]["full_name"],
              "- Tipo Python: `%s`" % cc["python_type"]["name"],
              "- Implementa ICollection/IList: %s" % cc["implements_count_bearing_interface"],
              "- Stringificação da instância realizada: %s" % cc["stringification_performed"]]
        if cc.get("representation"):
            rep = cc["representation"]
            md.append("- Representação: modo=`%s`, valor=`%s`" % (rep["mode"], rep["value"]))
        cp = cc["count_probe"]
        md += ["", "### Count dos filhos de Device",
              "- Tentativa: %s | Estado: %s | Valor: %s | Válido: %s"
              % (cp["attempted"], cp["state"], cp["value"], cp["valid"])]
        if cp.get("validation_error"):
            md.append("- Erro de validação: %s" % cp["validation_error"])
        md.append("- Iteração realizada: %s | Acesso a elementos realizado: %s"
                 % (cc["iteration_performed"], cc["element_access_performed"]))

        if report["errors"]:
            md.append("")
            md.append("## Erros (completos em report.json)")
            for e in report["errors"]:
                md.append("- em `%s`: %s" % (e["where"], e["message"]))
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

    project, err = project_access.get_primary_project(globals())
    if project is None:
        report["errors"].append({"where": "projects.primary", "message": err})
        print("[WARN] Projeto primario indisponivel: %s" % err)
        _finish()
        return

    rv = report["root_validation"]

    # --- 1. get_children(False) na RAIZ, EXATAMENTE 1 chamada ------------------
    gc_record = capabilities.probe_method_call(
        project, "project", "get_children", (False,),
        capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
    rv["get_children_call_count"] = 1
    rv["get_children_state"] = gc_record["state"]
    print("[%s] project.get_children(False) -> %s"
         % ("OK" if gc_record["state"] == "confirmed" else "INFO", gc_record["state"]))

    if gc_record["state"] != "confirmed" or "raw_value" not in gc_record:
        report["errors"].append({"where": "get_children",
                                 "message": gc_record.get("exception_message")})
        _finish()
        return
    root_children = gc_record["raw_value"]

    # --- 2. root_children.Count, EXATAMENTE 1 leitura, DEVE ser == 4 -----------
    count_record = capabilities.probe_member(
        root_children, "root_children", "Count", capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    rv["count_state"] = count_record["state"]
    if count_record["state"] == "confirmed" and "raw_value" in count_record:
        raw_count = count_record["raw_value"]
        rv["count"] = raw_count if isinstance(raw_count, (bool, int, float)) else None
    print("[%s] root_children.Count -> %s (valor=%s)"
         % ("OK" if rv["count_state"] == "confirmed" else "INFO", rv["count_state"], rv["count"]))

    rv["count_matches_expected"] = (rv["count_state"] == "confirmed"
                                    and rv["count"] == EXPECTED_ROOT_COUNT)
    if not rv["count_matches_expected"]:
        report["errors"].append({
            "where": "root_children.Count",
            "message": ("root_count_mismatch: esperado Count == %s, obtido "
                       "state=%s count=%s. Abortando SEM acessar "
                       "root_children[%s]." % (EXPECTED_ROOT_COUNT, rv["count_state"],
                                              rv["count"], DEVICE_INDEX)),
        })
        print("[BLOQUEADO] root_count_mismatch. Encerrando sem acessar root_children[%s]."
             % DEVICE_INDEX)
        _finish()
        return

    # --- 3. root_children[1], EXATAMENTE 1 acesso por indice ---------------------
    idx_record = capabilities.probe_indexer_access(
        root_children, "root_children", DEVICE_INDEX, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    rv["element_access_state"] = idx_record["state"]
    print("[%s] root_children[%s] -> %s"
         % ("OK" if idx_record["state"] == "confirmed" else "INFO", DEVICE_INDEX, idx_record["state"]))

    if idx_record["state"] != "confirmed" or "raw_value" not in idx_record:
        report["errors"].append({"where": "root_children[%s]" % DEVICE_INDEX,
                                 "message": idx_record.get("exception_message")})
        _finish()
        return
    device = idx_record["raw_value"]

    # --- 4. Revalidacao de identidade: name/type/guid, 1 leitura/chamada cada ----
    def _identity_probe_property(member_name):
        record = capabilities.probe_member(
            device, "device", member_name, capabilities.EVIDENCE_RUNTIME_CONFIRMED,
            capture_value=True)
        if record["state"] != "confirmed" or "raw_value" not in record:
            return record["state"], None
        value = record["raw_value"]
        python_type = capabilities.python_type_info(value)
        dotnet_type = capabilities.dotnet_type_info(value)
        rep = capabilities.build_representation(value, python_type, dotnet_type)
        return record["state"], (rep["value"] if rep["value_available"] else None)

    name_record = capabilities.probe_method_call(
        device, "device", "get_name", (False,), capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    if name_record["state"] == "confirmed" and "raw_value" in name_record:
        value = name_record["raw_value"]
        python_type = capabilities.python_type_info(value)
        dotnet_type = capabilities.dotnet_type_info(value)
        rep = capabilities.build_representation(value, python_type, dotnet_type)
        name_value = rep["value"] if rep["value_available"] else None
    else:
        name_value = None
    identity = rv["identity"]
    identity["name"]["state"] = name_record["state"]
    identity["name"]["value"] = name_value
    identity["name"]["matches_expected"] = (name_value == EXPECTED_DEVICE_NAME)

    type_state, type_value = _identity_probe_property("type")
    identity["type_guid"]["state"] = type_state
    identity["type_guid"]["value"] = type_value
    identity["type_guid"]["matches_expected"] = (type_value == EXPECTED_DEVICE_TYPE_GUID)

    guid_state, guid_value = _identity_probe_property("guid")
    identity["object_guid"]["state"] = guid_state
    identity["object_guid"]["value"] = guid_value
    identity["object_guid"]["matches_expected"] = (guid_value == EXPECTED_DEVICE_OBJECT_GUID)

    print("[INFO] identidade: name=%s(bate=%s) type=%s(bate=%s) guid=%s(bate=%s)"
         % (identity["name"]["value"], identity["name"]["matches_expected"],
            identity["type_guid"]["value"], identity["type_guid"]["matches_expected"],
            identity["object_guid"]["value"], identity["object_guid"]["matches_expected"]))

    rv["identity_confirmed"] = (identity["name"]["matches_expected"]
                                and identity["type_guid"]["matches_expected"]
                                and identity["object_guid"]["matches_expected"])

    if not rv["identity_confirmed"]:
        report["errors"].append({
            "where": "root_children[%s]" % DEVICE_INDEX,
            "message": ("device_identity_mismatch: name/type/guid de "
                       "root_children[%s] nao batem com os valores "
                       "esperados nesta execucao. Abortando SEM chamar "
                       "device.get_children(False)." % DEVICE_INDEX),
        })
        print("[BLOQUEADO] device_identity_mismatch. Encerrando sem chamar device.get_children(False).")
        _finish()
        return

    report["device"]["name"] = identity["name"]["value"]
    report["device"]["type_guid"] = identity["type_guid"]["value"]
    report["device"]["object_guid"] = identity["object_guid"]["value"]

    # --- 5. device.get_children(False), EXATAMENTE 1 chamada — SO com identidade
    # confirmada acima -----------------------------------------------------------
    cc = report["children_collection"]
    cc["attempted"] = True
    dgc_record = capabilities.probe_method_call(
        device, "device", "get_children", (False,), capabilities.EVIDENCE_RUNTIME_CONFIRMED,
        capture_value=True)
    cc["get_children_call_count"] = 1
    cc["state"] = dgc_record["state"]
    print("[%s] device.get_children(False) -> %s"
         % ("OK" if cc["state"] == "confirmed" else "INFO", cc["state"]))

    if cc["state"] != "confirmed" or "raw_value" not in dgc_record:
        report["errors"].append({"where": "device.get_children",
                                 "message": dgc_record.get("exception_message")})
        _finish()
        return
    device_children = dgc_record["raw_value"]

    cc["is_null"] = device_children is None
    if device_children is not None:
        cc["python_type"] = capabilities.python_type_info(device_children)
        cc["dotnet_type"] = capabilities.dotnet_type_info(device_children)
        # Representacao ESTRITA: nunca repr()/str()/ToString() na propria
        # colecao (tipo desconhecido) — so tipo, a menos que seja primitivo
        # (nao e o caso de uma colecao).
        cc["representation"] = capabilities.build_representation(
            device_children, cc["python_type"], cc["dotnet_type"])
        cc["stringification_performed"] = cc["representation"]["instance_stringification_performed"]

        implements, iface_names, iface_err = _implements_count_bearing_interface(device_children)
        cc["implements_count_bearing_interface"] = implements
        cc["type_interfaces_observed"] = iface_names
        cc["type_interface_check_error"] = iface_err
        print("[INFO] filhos de Device: tipo .NET=%s | implementa ICollection/IList=%s"
             % (cc["dotnet_type"]["full_name"], implements))

        cp = cc["count_probe"]
        if implements:
            cp["attempted"] = True
            count_record2 = capabilities.probe_member(
                device_children, "device_children", "Count",
                capabilities.EVIDENCE_RUNTIME_CONFIRMED, capture_value=True)
            cp["state"] = count_record2["state"]
            if count_record2["state"] == "confirmed" and "raw_value" in count_record2:
                raw = count_record2["raw_value"]
                is_int_like = isinstance(raw, (bool, int, float)) and not isinstance(raw, bool)
                if is_int_like:
                    cp["value"] = raw
                    if raw < 0:
                        cp["valid"] = False
                        cp["validation_error"] = "Count negativo (%s) - rejeitado." % raw
                    elif raw > MAX_DEVICE_CHILDREN:
                        cp["valid"] = False
                        cp["validation_error"] = ("Count (%s) excede max_device_children "
                                                 "(%s) - rejeitado por limite de "
                                                 "seguranca." % (raw, MAX_DEVICE_CHILDREN))
                    else:
                        cp["valid"] = True
                else:
                    cp["valid"] = False
                    cp["validation_error"] = ("Count nao e um inteiro valido (tipo: %s)."
                                             % compatibility.safe_type_name(raw))
            else:
                report["errors"].append({"where": "device_children.Count",
                                         "message": count_record2.get("exception_message")})
            print("[%s] device_children.Count -> %s (valor=%s, valido=%s)"
                 % ("OK" if cp["state"] == "confirmed" else "INFO", cp["state"],
                    cp["value"], cp["valid"]))
        else:
            print("[INFO] Count NAO tentado: tipo nao confirmou ICollection/IList "
                 "via GetType().GetInterfaces().")

    _finish()


main()

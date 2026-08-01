# -*- coding: utf-8 -*-
r"""22_probe_device_parameter_set_link.py — FASE 0: comprovar UM elo, e nada
mais.

    no da arvore  ->  extensao de device  ->  IScriptDeviceParameterSet

Este probe NAO le valor de parametro. Nao le `value`, nao le `default_value`,
nao itera a colecao. Ele responde uma unica pergunta: o membro que leva do no
ao conjunto de parametros existe neste runtime?

POR QUE ISOLAR ISTO
    O elo e o unico ponto da cadeia sem observacao. A evidencia estatica diz
    que `IScriptDeviceObject3` declara `device_parameters { get; }` devolvendo
    `IScriptDeviceParameterSet` — mas declaracao em metadado nao prova que o
    membro chega ao objeto Python. O mesmo padrao de extensao ja FALHOU antes
    neste projeto: o probe 18 observou que `Extender` devolve o mesmo
    `ScriptObject`, nao um provider, e `dir()` e vazio em proxies
    `ExtendedObject`. Se o elo nao existir, a cadeia inteira cai — e e melhor
    descobrir isso lendo nada.

LISTA FECHADA DE CANDIDATOS — escrita literalmente no codigo, nesta ordem:
    1. `device_parameters`  (alvo; IScriptDeviceObject3, getter-only)
    2. `connectors`         (SO se 1 falhar; IScriptDeviceObject3, getter-only)
       Serve unicamente para distinguir "a extensao nao esta no objeto" de
       "a extensao esta, mas este membro nao". Nao e alvo.

PROIBIDO NESTE PROBE, e nada disto aparece no arquivo:
    dir()                         enumeracao generica de extensoes
    getattr com nome em variavel  setattr
    PropertyInfo.SetValue         GetExtensions()
    iteracao de parametros        leitura de value/default_value/min/max
    read_online_value             qualquer membro com setter
    metodos de IList              qualquer metodo desconhecido
    alteracao do probe 21

O QUE E REGISTRADO
    tipo .NET devolvido, interfaces desse tipo (reflection sobre o TIPO, nao
    sobre a instancia) e, se o tipo implementar a interface esperada, o `Count`
    — unico getter escalar comprovadamente somente-leitura
    (`Int32 Count { get; }`). Mais nada.

VEREDITOS
    parameter_set_found      membro existe e o tipo implementa IScriptDeviceParameterSet
    parameter_set_not_found  membro ausente ou inacessivel
    unexpected_type          membro existe, tipo NAO e o esperado
    fatal                    nao foi possivel chegar ao no alvo

    exit 0 -> parameter_set_found
    exit 2 -> parameter_set_not_found / unexpected_type
    exit 1 -> fatal
    O `verdict` do manifesto e autoritativo; a propagacao do exit code pelo
    MT8500 nunca foi observada.

EXECUCAO (pelo USUARIO, UI VISIVEL, sobre a COPIA DESCARTAVEL, offline, sem
salvar). O no alvo e OBRIGATORIO e vem da varredura do probe 21 — nao ha
default, porque um default seria a estrutura de UM projeto especifico:

    --scriptargs:"--output=C:\saida-fase0 --node-id=root/1/1/0/2"
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

EXPECTED_INTERFACE = ("_3S.CoDeSys.ScriptEngine.BasicFunctionality."
                      "IScriptDeviceParameterSet")
MAX_PATH_STEPS = 12
MAX_CHILDREN_PER_STEP = 1024

VERDICT_FOUND = "parameter_set_found"
VERDICT_NOT_FOUND = "parameter_set_not_found"
VERDICT_UNEXPECTED = "unexpected_type"
VERDICT_FATAL = "fatal"

EXIT_BY_VERDICT = {
    VERDICT_FOUND: 0,
    VERDICT_NOT_FOUND: 2,
    VERDICT_UNEXPECTED: 2,
    VERDICT_FATAL: 1,
}

SAFETY_DECLARATION = {
    "read_only": True,
    "reads_parameter_value": False,
    "iterates_parameters": False,
    "uses_dir": False,
    "uses_dynamic_getattr": False,
    "uses_setattr": False,
    "uses_property_setvalue": False,
    "uses_get_extensions": False,
    "calls_online_api": False,
    "project_write": False,
    "project_save": False,
    "closed_candidate_list": True,
}


def _find_arg(argv, name):
    prefix = "--" + name
    for i, raw in enumerate(argv):
        if raw == prefix:
            if i + 1 < len(argv):
                return argv[i + 1]
            return ""
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
        problems.append("--output contem espaco: %r (o MT8500 quebra valores "
                        "com espaco em --scriptargs)" % path)
        return None
    absolute = os.path.abspath(path)
    normalized = os.path.normcase(absolute)
    if normalized == os.path.normcase(REPO_ROOT) or \
            normalized.startswith(os.path.normcase(REPO_ROOT) + os.sep):
        problems.append("--output aponta para dentro do repositorio: %s" % absolute)
        return None
    return absolute


def _parse_node_id(raw, problems):
    """`root/1/1/0/2` -> [1, 1, 0, 2]. Indices, nunca nomes: nome depende
    de encoding e de idioma do projeto."""
    text = str(raw or "").strip()
    parts = [p for p in text.split("/") if p != ""]
    if text == "":
        problems.append("--node-id e obrigatorio: o no alvo vem da varredura "
                        "do projeto, nunca embutido no repositorio")
        return None, text
    if not parts or parts[0] != "root":
        problems.append("--node-id deve comecar por 'root': %r" % text)
        return None, text
    indexes = []
    for part in parts[1:]:
        try:
            value = int(part)
        except (TypeError, ValueError):
            problems.append("--node-id tem segmento nao numerico: %r" % part)
            return None, text
        if value < 0:
            problems.append("--node-id tem indice negativo: %r" % part)
            return None, text
        indexes.append(value)
    if not indexes:
        problems.append("--node-id aponta para a raiz; escolha um dispositivo")
        return None, text
    if len(indexes) > MAX_PATH_STEPS:
        problems.append("--node-id tem %d passos (maximo %d)"
                        % (len(indexes), MAX_PATH_STEPS))
        return None, text
    return indexes, text


def _clr_type_info(obj):
    """Reflection sobre o TIPO, nunca sobre a instancia: nenhum membro de
    instancia e invocado aqui."""
    info = {"python_type": None, "clr_type": None, "interfaces": [], "error": None}
    try:
        info["python_type"] = str(type(obj))
    except Exception as exc:                                   # noqa: BLE001
        info["error"] = repr(exc)
        return info
    try:
        import clr
        clr_type = clr.GetClrType(type(obj))
        info["clr_type"] = clr_type.FullName
        names = []
        for iface in clr_type.GetInterfaces():
            names.append(iface.FullName)
        info["interfaces"] = sorted(names)
    except Exception as exc:                                   # noqa: BLE001
        info["error"] = repr(exc)
    return info


def _descend(project, indexes, trace):
    """Descida por UM caminho, por indice. Nao e varredura: em cada passo le
    a colecao de filhos uma vez e acessa UM indice."""
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


def _try_device_parameters(node):
    """Candidato 1. Acesso LITERAL, escrito no codigo. Nao ha nome em
    variavel, nao ha getattr dinamico."""
    return node.device_parameters


def _try_connectors(node):
    """Candidato 2, diagnostico apenas. Acesso LITERAL."""
    return node.connectors


CANDIDATES = (
    ("device_parameters", _try_device_parameters, "alvo"),
    ("connectors", _try_connectors, "diagnostico: a extensao esta no objeto?"),
)


def main():
    print("=" * 68)
    print("[INFO] probes/22_probe_device_parameter_set_link.py — FASE 0")
    print("[INFO] Nenhum valor de parametro e lido neste probe.")
    print("=" * 68)

    problems = []
    argv = list(sys.argv or [])
    out_root = _validate_output(_find_arg(argv, "output"), problems)
    indexes, node_text = _parse_node_id(_find_arg(argv, "node-id"), problems)
    if not _FILE_AVAILABLE:
        problems.append("__file__ indisponivel")

    if problems:
        print("[FATAL] argumentos recusados:")
        for item in problems:
            print("        - %s" % item)
        sys.exit(EXIT_BY_VERDICT[VERDICT_FATAL])
        return

    try:
        from common import file_io, project_access
    except Exception as exc:                                   # noqa: BLE001
        print("[FATAL] falha ao importar modulos comuns: %r" % (exc,))
        sys.exit(EXIT_BY_VERDICT[VERDICT_FATAL])
        return

    manifest = {
        "schema_version": "1.0",
        "script": "probes/22_probe_device_parameter_set_link.py",
        "phase": "0",
        "mode": "read_only",
        "generated_at": file_io.iso_now(),
        "target_node_id": node_text,
        "expected_interface": EXPECTED_INTERFACE,
        "candidates_declared": [name for name, _fn, _why in CANDIDATES],
        "descent_trace": [],
        "attempts": [],
        "result": None,
        "verdict": VERDICT_FATAL,
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
                                         file_io.safe_filename(slug) + "_fase0")
        print("[INFO] saida    : %s" % run_dir)
        print("[INFO] no alvo  : %s" % node_text)

        node = _descend(project, indexes, manifest["descent_trace"])
        if node is None:
            manifest["fatal_error"] = "nao foi possivel chegar ao no alvo"
            raise RuntimeError(manifest["fatal_error"])
        print("[INFO] no alcancado: %s" % manifest["descent_trace"][-1].get("name"))

        # --- lista fechada, na ordem; para no primeiro sucesso -------------
        for name, accessor, why in CANDIDATES:
            attempt = {"member": name, "role": why, "accessed": False,
                       "error": None, "type_info": None}
            try:
                value = accessor(node)
                attempt["accessed"] = True
            except Exception as exc:                           # noqa: BLE001
                attempt["error"] = repr(exc)
                manifest["attempts"].append(attempt)
                print("[INFO] '%s' indisponivel: %r" % (name, exc))
                continue

            if value is None:
                attempt["error"] = "membro existe mas devolveu None"
                manifest["attempts"].append(attempt)
                print("[INFO] '%s' devolveu None" % name)
                continue

            info = _clr_type_info(value)
            attempt["type_info"] = info
            manifest["attempts"].append(attempt)
            print("[INFO] '%s' -> %s" % (name, info.get("clr_type")))

            if name != "device_parameters":
                # `connectors` nunca decide o veredito: e so diagnostico.
                continue

            implements = EXPECTED_INTERFACE in (info.get("interfaces") or [])
            result = {"member": name, "clr_type": info.get("clr_type"),
                      "implements_expected_interface": implements,
                      "count": None, "count_error": None}
            if implements:
                # Unico getter escalar comprovadamente somente-leitura
                # (`Int32 Count { get; }`). Nenhuma iteracao.
                try:
                    result["count"] = value.Count
                except Exception as exc:                       # noqa: BLE001
                    result["count_error"] = repr(exc)
                manifest["verdict"] = VERDICT_FOUND
            else:
                manifest["verdict"] = VERDICT_UNEXPECTED
            manifest["result"] = result
            break

        if manifest["verdict"] == VERDICT_FATAL and manifest["attempts"]:
            manifest["verdict"] = VERDICT_NOT_FOUND

    except Exception as exc:                                   # noqa: BLE001
        manifest["verdict"] = VERDICT_FATAL
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
            run_dir = file_io.new_export_dir(out_root, "fase0_fatal")
        file_io.write_json(os.path.join(run_dir, "manifest.json"), manifest)
        print("[OK] manifesto em: %s" % run_dir)
    except Exception as exc:                                   # noqa: BLE001
        print("[ERROR] falha ao gravar manifesto: %r" % (exc,))
        manifest["verdict"] = VERDICT_FATAL

    code = EXIT_BY_VERDICT.get(manifest["verdict"], EXIT_BY_VERDICT[VERDICT_FATAL])
    print("[INFO] verdict=%s exit=%d (o verdict do manifesto e autoritativo)"
          % (manifest["verdict"], code))
    print("=" * 68)
    sys.exit(code)


main()

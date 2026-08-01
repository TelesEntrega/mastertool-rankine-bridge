# -*- coding: utf-8 -*-
r"""33_verify_program_edit_w1_3b_readonly.py -- verificador SOMENTE LEITURA de
W1.3B (editar o PROGRAM `PRG_AI_TESTE` em `W1-A2.project`).

Contrato: `docs/28`. Plano: `docs/31` secao W1.3B.

Dois modos LITERAIS, de conjunto fechado, no mesmo espirito do probe 29:

    preflight  -- antes da mutacao. Resolve o container, acha o PROGRAM
                  UNICO, confere `type`, le os DOIS documentos e exige que
                  sejam EXATAMENTE os textos iniciais medidos (normalizados).
                  Enumera a arvore do container como linha de base para o
                  diff estrutural do modo `postsave`.
    postsave   -- depois do `save_as`. Reabre o arquivo de SAIDA, confere o
                  hash contra o registrado apos a mutacao, exige os DOIS
                  textos finais medidos, e produz diff estrutural exigindo
                  ZERO objetos acrescentados ou removidos -- nenhum objeto
                  novo, nem mesmo o proprio alvo, porque `replace` nunca cria
                  nem apaga objeto.

NAO faz, por construcao -- nenhuma destas chamadas existe neste arquivo:
`create_program`, `create_pou`, `create_gvl`, `create_folder`, `create_dut`,
`save`, `save_as`, `remove`, `rename`, `build`, `import_xml`, e nenhuma
chamada do documento de texto que nao seja o getter `text`.

O acesso ao membro de tipo e LITERAL: `obj.type`, nunca `obj.type_guid` --
esse ultimo nome nao existe no proxy e devolveria None em silencio (achado
real de W1.1/W1.2, registrado em probes/29 e probes/30).

Compatibilidade: IronPython 2.7.12.
"""
from __future__ import print_function

import hashlib
import json
import os
import re
import sys
import traceback

_FILE_AVAILABLE = True
try:
    _SCRIPT_PATH = os.path.abspath(__file__)
    _SCRIPT_DIR = os.path.dirname(_SCRIPT_PATH)
except NameError:
    _FILE_AVAILABLE = False
    _SCRIPT_PATH = None
    _SCRIPT_DIR = None

_MASTERTOOL_DIR = os.path.dirname(_SCRIPT_DIR) if _SCRIPT_DIR else None
if _MASTERTOOL_DIR and _MASTERTOOL_DIR not in sys.path:
    sys.path.insert(0, _MASTERTOOL_DIR)
REPO_ROOT = os.path.abspath(os.path.join(_MASTERTOOL_DIR, "..", "..")) if _MASTERTOOL_DIR else None

SCRIPT_NAME = "33_verify_program_edit_w1_3b_readonly.py"
SCHEMA_VERSION = "1.0"

EXPECTED_PHASE = "W1_3B_EDIT_PROGRAM"
EXPECTED_PROGRAM_NAME = "PRG_AI_TESTE"

# Medidos, congelados em docs/31 secao W1.3B. Constantes de MODULO -- o plano
# pode DECLARAR os mesmos valores para registro, mas nunca os substitui: uma
# divergencia entre plano e constante reprova o preflight (ver validate_plan
# de probes/34, que compartilha estas mesmas constantes por valor literal).
EXPECTED_PROGRAM_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
EXPECTED_CONTAINER_TYPE_GUID = "639b491f-5557-464c-af91-1471bac9f549"

# EXPECTED_ST_LANGUAGE_GUID foi REMOVIDA daqui em 2026-07-31, ao apurar os
# criterios de W1.3B: ela existia neste modulo e nunca era usada. Constante que
# aparenta verificar linguagem e nao verifica e pior que ausente, porque le
# como cobertura -- e foi assim que "linguagem continua ST" chegou a lista de
# criterios sem instrumento por tras.
#
# A causa nao e descuido: NAO HA API CATALOGADA que devolva a linguagem de um
# objeto existente. `language` aparece so como parametro de ENTRADA em
# create_pou/create_program/create_function/create_function_block, e
# `IScriptImplementationLanguages` so fornece um Guid POR LINGUAGEM (docs/27).
# Ler de volta exigiria API nao catalogada, proibido por contrato.
#
# O GUID de ST continua em probes/34, onde tem uso real: conferir que o valor
# DECLARADO no plano coincide com a constante medida. Isso valida o plano, e
# nao o objeto -- e la o comentario diz exatamente isso.
#
# Quem for provar a linguagem: o caminho e o `build` de W1.4. ST que compila e
# ST, e isso prova mais que um rotulo conferido (docs/34 secao 6).

# Textos canonicos, medidos -- ver docs/31. Repr exato, inclusive quebras.
INITIAL_DECLARATION = "PROGRAM PRG_AI_TESTE\nVAR\nEND_VAR\n"
INITIAL_IMPLEMENTATION = ""
FINAL_DECLARATION = "PROGRAM PRG_AI_TESTE\nVAR\n    xLocal : BOOL;\nEND_VAR\n"
FINAL_IMPLEMENTATION = "xLocal := FALSE;\n"

INITIAL_DECLARATION_SHA256 = "6a2401fa5915a354eae0895d290e4bb6d3483c4d3ca4e05cb7e5b230f4435841"
INITIAL_IMPLEMENTATION_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
FINAL_DECLARATION_SHA256 = "6e4b13ab8010577533f0a25061cb285b6fe6288eb61494c4f80af26abdfa80f5"
FINAL_IMPLEMENTATION_SHA256 = "313cdb1f7a9f98cd6a0b8c99d26f82402ba1aaa5c74ab8d1d9e6715e1347d517"

# --- estados, vocabulario fechado -------------------------------------------
PREFLIGHT_VERIFIED = "preflight_verified"
POSTSAVE_VERIFIED = "postsave_verified"
CONTAINER_NOT_FOUND = "container_not_found"
CONTAINER_AMBIGUOUS = "container_ambiguous"
PROGRAM_MISSING = "program_missing"
PROGRAM_DUPLICATED = "program_duplicated"
PROGRAM_TYPE_MISMATCH = "program_type_mismatch"
INITIAL_TEXT_MISMATCH = "initial_text_mismatch"
FINAL_TEXT_MISMATCH = "final_text_mismatch"
OUTPUT_HASH_MISMATCH = "output_hash_mismatch"
STRUCTURAL_DIFF_UNEXPECTED = "structural_diff_unexpected"
TEXT_READ_GAP = "text_read_gap"
RUNTIME_MISMATCH = "runtime_mismatch"
STATUS_FATAL = "fatal"

MODE_PREFLIGHT = "preflight"
MODE_POSTSAVE = "postsave"
VALID_MODES = (MODE_PREFLIGHT, MODE_POSTSAVE)

ALL_STATUSES = (
    PREFLIGHT_VERIFIED, POSTSAVE_VERIFIED, CONTAINER_NOT_FOUND,
    CONTAINER_AMBIGUOUS, PROGRAM_MISSING, PROGRAM_DUPLICATED,
    PROGRAM_TYPE_MISMATCH, INITIAL_TEXT_MISMATCH, FINAL_TEXT_MISMATCH,
    OUTPUT_HASH_MISMATCH, STRUCTURAL_DIFF_UNEXPECTED, TEXT_READ_GAP,
    RUNTIME_MISMATCH, STATUS_FATAL,
)

# `text_read_gap` NAO e sucesso: limitacao registrada, veredito pendente de
# revisao humana -- mesmo vocabulario do probe 29.
SUCCESS_STATUSES = (PREFLIGHT_VERIFIED, POSTSAVE_VERIFIED)

EXIT_BY_STATUS = {
    PREFLIGHT_VERIFIED: 0,
    POSTSAVE_VERIFIED: 0,
    CONTAINER_NOT_FOUND: 2,
    CONTAINER_AMBIGUOUS: 2,
    PROGRAM_MISSING: 2,
    PROGRAM_DUPLICATED: 2,
    PROGRAM_TYPE_MISMATCH: 2,
    RUNTIME_MISMATCH: 2,
    INITIAL_TEXT_MISMATCH: 3,
    FINAL_TEXT_MISMATCH: 3,
    OUTPUT_HASH_MISMATCH: 3,
    STRUCTURAL_DIFF_UNEXPECTED: 3,
    TEXT_READ_GAP: 4,
    STATUS_FATAL: 1,
}

VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp")

try:
    _STRING_TYPES = (basestring,)  # noqa: F821
except NameError:
    _STRING_TYPES = (str,)


def is_text(value):
    return isinstance(value, _STRING_TYPES) and value != ""


def sha256_of_text(text):
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except Exception:                                          # noqa: BLE001
        return None


def sha256_of_file(path):
    """(digest, erro). Nunca levanta. Usado pelo modo postsave para conferir o
    arquivo salvo contra o hash registrado logo apos o save_as."""
    try:
        digest = hashlib.sha256()
        handle = open(path, "rb")
        try:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
        finally:
            handle.close()
        return digest.hexdigest(), None
    except Exception as exc:                                   # noqa: BLE001
        return None, repr(exc)


def load_json_file(path):
    handle = open(path, "rb")
    try:
        raw = handle.read()
    finally:
        handle.close()
    return json.loads(raw.decode("utf-8"))


def normalize_text(text):
    """CRLF e LF equivalentes; espaco em branco no fim de cada linha
    ignorado; UMA quebra de linha final ignorada; qualquer outra diferenca e
    divergencia. Regra congelada em docs/29 e reafirmada em docs/31.

    Implementada com `re.sub`, nunca com o metodo de string homonimo ao da
    API mutavel: este arquivo prova, por busca literal, que nenhuma chamada
    de mutacao existe aqui, e uma chamada de string com o mesmo nome nao
    pode contaminar essa prova.
    """
    if text is None:
        return None
    sem_cr = re.sub(r"\r\n|\r", "\n", text)
    linhas = [linha.rstrip() for linha in sem_cr.split("\n")]
    resultado = "\n".join(linhas)
    if resultado.endswith("\n"):
        resultado = resultado[:-1]
    return resultado


def texts_match(observed, expected):
    return normalize_text(observed) == normalize_text(expected)


# --- identidade -------------------------------------------------------------

def object_identity(obj):
    """Membros lidos pelo nome LITERAL. `type` e o membro; `type_guid` e o
    nome do campo na saida -- a troca dos dois reprovou um preflight real em
    W1.1/W1.2."""
    identity = {"name": None, "type_guid": None, "is_folder": None,
                "is_transient": None, "has_textual_declaration": None,
                "has_textual_implementation": None, "errors": []}
    try:
        identity["name"] = str(obj.get_name(False))
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("get_name: %r" % (exc,))
    try:
        if hasattr(obj, "type"):
            identity["type_guid"] = str(obj.type)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("type: %r" % (exc,))
    try:
        if hasattr(obj, "is_folder"):
            identity["is_folder"] = bool(obj.is_folder)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("is_folder: %r" % (exc,))
    try:
        if hasattr(obj, "is_transient_object"):
            identity["is_transient"] = bool(obj.is_transient_object)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("is_transient_object: %r" % (exc,))
    try:
        if hasattr(obj, "has_textual_declaration"):
            identity["has_textual_declaration"] = bool(obj.has_textual_declaration)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("has_textual_declaration: %r" % (exc,))
    try:
        if hasattr(obj, "has_textual_implementation"):
            identity["has_textual_implementation"] = bool(obj.has_textual_implementation)
    except Exception as exc:                                   # noqa: BLE001
        identity["errors"].append("has_textual_implementation: %r" % (exc,))
    return identity


def enumerate_children(container):
    snapshot = {"persistent": [], "transient": [], "count": None, "error": None}
    try:
        children = container.get_children(False)
        if children is None:
            snapshot["error"] = "get_children devolveu None"
            return snapshot
        snapshot["count"] = children.Count
        index = 0
        while index < children.Count:
            identity = object_identity(children[index])
            if identity.get("is_transient") is True:
                snapshot["transient"].append(identity)
            else:
                snapshot["persistent"].append(identity)
            index = index + 1
    except Exception as exc:                                   # noqa: BLE001
        snapshot["error"] = repr(exc)
    return snapshot


def count_matching_siblings(parent, expected_name, expected_type_guid):
    matches = 0
    try:
        children = parent.get_children(False)
        if children is None:
            return None
        index = 0
        while index < children.Count:
            identity = object_identity(children[index])
            name_ok = (expected_name is None or identity.get("name") == expected_name)
            guid_ok = (expected_type_guid is None
                       or identity.get("type_guid") == expected_type_guid)
            if name_ok and guid_ok:
                matches = matches + 1
            index = index + 1
    except Exception:                                          # noqa: BLE001
        return None
    return matches


def child_by_name(container, name):
    try:
        children = container.get_children(False)
        if children is None:
            return None
        index = 0
        while index < children.Count:
            child = children[index]
            try:
                if str(child.get_name(False)) == name:
                    return child
            except Exception:                                  # noqa: BLE001
                pass
            index = index + 1
    except Exception:                                          # noqa: BLE001
        return None
    return None


def read_text_documents(obj):
    """Declaracao E implementacao. Somente leitura -- o getter `text`, nada
    alem disso."""
    result = {"declaration": None, "declaration_sha256": None,
              "implementation": None, "implementation_sha256": None,
              "gap": None, "error": None}
    try:
        if hasattr(obj, "textual_declaration"):
            document = obj.textual_declaration
            if document is not None and hasattr(document, "text"):
                text = document.text
                if text is not None:
                    result["declaration"] = str(text)
                    result["declaration_sha256"] = sha256_of_text(result["declaration"])
            else:
                result["gap"] = "textual_declaration sem documento ou sem text"
        else:
            result["gap"] = "objeto nao expoe textual_declaration"
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = "declaration: %r" % (exc,)
    try:
        if hasattr(obj, "textual_implementation"):
            document = obj.textual_implementation
            if document is not None and hasattr(document, "text"):
                text = document.text
                if text is not None:
                    result["implementation"] = str(text)
                    result["implementation_sha256"] = sha256_of_text(
                        result["implementation"])
            elif result["gap"] is None:
                result["gap"] = "textual_implementation sem documento ou sem text"
        elif result["gap"] is None:
            result["gap"] = "objeto nao expoe textual_implementation"
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = "implementation: %r" % (exc,)
    return result


def multiset_difference(before_names, after_names):
    counts = {}
    for name in before_names:
        counts[name] = counts.get(name, 0) + 1
    added = []
    for name in after_names:
        pending = counts.get(name, 0)
        if pending > 0:
            counts[name] = pending - 1
        else:
            added.append(name)
    missing = []
    for name in before_names:
        if counts.get(name, 0) > 0:
            counts[name] = counts[name] - 1
            missing.append(name)
    return added, missing


def find_unique_program(snapshot, result):
    """(objeto identidade, status_de_erro_ou_None). `snapshot` e a arvore
    completa (persistente + transiente) do container."""
    encontrados = []
    for item in (snapshot.get("persistent") or []) + (snapshot.get("transient") or []):
        if item.get("name") == EXPECTED_PROGRAM_NAME:
            encontrados.append(item)
    result["program_matches"] = len(encontrados)
    if not encontrados:
        result["problems"].append("%r nao existe no container"
                                  % (EXPECTED_PROGRAM_NAME,))
        return None, PROGRAM_MISSING
    if len(encontrados) > 1:
        result["problems"].append("%d objetos chamados %r"
                                  % (len(encontrados), EXPECTED_PROGRAM_NAME))
        return None, PROGRAM_DUPLICATED
    identidade = encontrados[0]
    if identidade.get("type_guid") != EXPECTED_PROGRAM_TYPE_GUID:
        result["problems"].append(
            "type do PROGRAM e %r, esperado %r"
            % (identidade.get("type_guid"), EXPECTED_PROGRAM_TYPE_GUID))
        return identidade, PROGRAM_TYPE_MISMATCH
    if identidade.get("is_folder") is True:
        result["problems"].append("o objeto encontrado e uma pasta")
        return identidade, PROGRAM_TYPE_MISMATCH
    return identidade, None


# --- orquestracao dos dois modos --------------------------------------------

def run_preflight(container, result):
    snapshot = enumerate_children(container)
    result["container_tree"] = snapshot
    if snapshot.get("error"):
        result["problems"].append("enumeracao falhou: %s" % snapshot["error"])
        return STATUS_FATAL

    identidade, erro = find_unique_program(snapshot, result)
    if erro is not None:
        return erro

    node = child_by_name(container, EXPECTED_PROGRAM_NAME)
    if node is None:
        result["problems"].append(
            "%r encontrado na enumeracao mas nao localizado por nome"
            % (EXPECTED_PROGRAM_NAME,))
        return PROGRAM_MISSING

    textos = read_text_documents(node)
    result["program_texts"] = textos
    if textos.get("gap") or textos.get("declaration") is None \
            or textos.get("implementation") is None:
        result["problems"].append(
            "texto inicial do PROGRAM nao pode ser lido por completo: %s"
            % (textos.get("gap") or textos.get("error")))
        return TEXT_READ_GAP

    if not texts_match(textos.get("declaration"), INITIAL_DECLARATION):
        result["problems"].append(
            "declaracao inicial diverge do texto canonico medido (sha "
            "esperado %s)" % INITIAL_DECLARATION_SHA256)
        return INITIAL_TEXT_MISMATCH
    if not texts_match(textos.get("implementation"), INITIAL_IMPLEMENTATION):
        result["problems"].append(
            "implementacao inicial diverge do texto canonico medido (sha "
            "esperado %s)" % INITIAL_IMPLEMENTATION_SHA256)
        return INITIAL_TEXT_MISMATCH

    return PREFLIGHT_VERIFIED


def run_postsave(container, baseline, opened_path, plan, expected_output_hash,
                 result):
    output_path = (plan.get("output_project") or {}).get("path")
    if not is_text(opened_path) or not is_text(output_path) or \
            os.path.normcase(os.path.abspath(opened_path)) != \
            os.path.normcase(os.path.abspath(output_path)):
        result["problems"].append(
            "projeto aberto (%r) nao e o output previsto (%r)"
            % (opened_path, output_path))
        return OUTPUT_HASH_MISMATCH

    observed, hash_error = sha256_of_file(opened_path)
    result["output_sha256_observed"] = observed
    if hash_error:
        result["problems"].append("sha256 do output ilegivel: %s" % hash_error)
        return OUTPUT_HASH_MISMATCH
    if is_text(expected_output_hash) and observed != expected_output_hash:
        result["problems"].append("sha256 do output diverge do registrado apos save_as")
        return OUTPUT_HASH_MISMATCH

    snapshot = enumerate_children(container)
    result["container_tree"] = snapshot
    if snapshot.get("error"):
        result["problems"].append("enumeracao falhou: %s" % snapshot["error"])
        return STATUS_FATAL

    identidade, erro = find_unique_program(snapshot, result)
    if erro is not None:
        return erro

    antes = [i.get("name") for i in ((baseline or {}).get("persistent") or [])]
    depois = [i.get("name") for i in (snapshot.get("persistent") or [])]
    antes_transiente = [i.get("name") for i in ((baseline or {}).get("transient") or [])]
    depois_transiente = [i.get("name") for i in (snapshot.get("transient") or [])]
    added, missing = multiset_difference(antes, depois)
    added_transient, missing_transient = multiset_difference(
        antes_transiente, depois_transiente)
    result["structural_diff"] = {
        "persistent_added": added, "persistent_missing": missing,
        "transient_added": added_transient, "transient_missing": missing_transient,
        "allowed_additions": [],
    }
    # ZERO objetos acrescentados ou removidos -- nem mesmo o proprio alvo:
    # `replace` nunca cria nem apaga objeto, ao contrario de W1.2.
    if added or missing:
        result["problems"].append(
            "diff estrutural persistente inesperado: acrescimos=%r, "
            "sumicos=%r (permitido: nenhum)" % (added, missing))
        return STRUCTURAL_DIFF_UNEXPECTED

    node = child_by_name(container, EXPECTED_PROGRAM_NAME)
    if node is None:
        result["problems"].append(
            "%r encontrado na enumeracao mas nao localizado por nome"
            % (EXPECTED_PROGRAM_NAME,))
        return PROGRAM_MISSING

    textos = read_text_documents(node)
    result["program_texts"] = textos
    if textos.get("gap") or textos.get("declaration") is None \
            or textos.get("implementation") is None:
        result["problems"].append(
            "texto final do PROGRAM nao pode ser lido por completo: %s"
            % (textos.get("gap") or textos.get("error")))
        return TEXT_READ_GAP

    if not texts_match(textos.get("declaration"), FINAL_DECLARATION):
        result["problems"].append(
            "declaracao final diverge do texto planejado (sha esperado %s)"
            % FINAL_DECLARATION_SHA256)
        return FINAL_TEXT_MISMATCH
    if not texts_match(textos.get("implementation"), FINAL_IMPLEMENTATION):
        result["problems"].append(
            "implementacao final diverge do texto planejado (sha esperado %s)"
            % FINAL_IMPLEMENTATION_SHA256)
        return FINAL_TEXT_MISMATCH

    return POSTSAVE_VERIFIED


def run_verify(script_globals, argv, project_access, file_io, probe_cli,
              now=None):
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": None,
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "problems": [],
        "runtime": None,
        "opened_project": None,
        "container_node_path": None,
        "container_identity": None,
        "container_tree": None,
        "program_texts": None,
        "artifacts_dir": None,
        "exit_code": EXIT_BY_STATUS[STATUS_FATAL],
    }

    def finish(status):
        result["status"] = status
        result["finished_at"] = now()
        result["exit_code"] = EXIT_BY_STATUS.get(status, EXIT_BY_STATUS[STATUS_FATAL])
        return result

    problems = []
    plan_path = probe_cli.find_arg(argv, "plan")
    artifacts_dir = probe_cli.validate_output_path(
        probe_cli.find_arg(argv, "output"), REPO_ROOT, problems)
    result["artifacts_dir"] = artifacts_dir

    raw_mode = probe_cli.find_arg(argv, "mode")
    if raw_mode is None or raw_mode == "":
        mode = MODE_PREFLIGHT
    elif raw_mode == MODE_PREFLIGHT:
        mode = MODE_PREFLIGHT
    elif raw_mode == MODE_POSTSAVE:
        mode = MODE_POSTSAVE
    else:
        mode = None
        problems.append("--mode invalido: %r (esperado %r ou %r)"
                        % (raw_mode, MODE_PREFLIGHT, MODE_POSTSAVE))
    result["mode"] = mode
    baseline_path = probe_cli.find_arg(argv, "baseline")
    expected_output_hash = probe_cli.find_arg(argv, "output-sha256")
    result["output_sha256_expected"] = expected_output_hash

    if not is_text(plan_path) or not os.path.isfile(plan_path):
        problems.append("--plan obrigatorio e existente: %r" % (plan_path,))
    if problems:
        result["problems"].extend(problems)
        return finish(STATUS_FATAL)

    baseline = None
    if mode == MODE_POSTSAVE:
        if not is_text(baseline_path) or not os.path.isfile(baseline_path):
            result["problems"].append(
                "--baseline obrigatorio no modo postsave: sem a arvore do "
                "preflight nao existe diff estrutural")
            return finish(STATUS_FATAL)
        try:
            baseline = load_json_file(baseline_path)
        except Exception as exc:                               # noqa: BLE001
            result["problems"].append("baseline ilegivel: %r" % (exc,))
            return finish(STATUS_FATAL)

    try:
        plan = load_json_file(plan_path)
    except Exception as exc:                                   # noqa: BLE001
        result["problems"].append("plano ilegivel: %r" % (exc,))
        return finish(STATUS_FATAL)

    result["runtime"] = probe_cli.runtime_identity()
    expected_version = (plan.get("mastertool") or {}).get("version")
    observed_version = (result["runtime"] or {}).get("file_version")
    if observed_version != expected_version:
        result["problems"].append(
            "instalacao inesperada: observada %r, plano espera %r"
            % (observed_version, expected_version))
        return finish(RUNTIME_MISMATCH)

    if plan.get("phase") != EXPECTED_PHASE:
        result["problems"].append(
            "phase do plano e %r, esperado %r" % (plan.get("phase"), EXPECTED_PHASE))
        return finish(STATUS_FATAL)
    if plan.get("program_name") != EXPECTED_PROGRAM_NAME:
        result["problems"].append(
            "program_name do plano e %r, esperado %r"
            % (plan.get("program_name"), EXPECTED_PROGRAM_NAME))
        return finish(STATUS_FATAL)

    project, access_error = project_access.get_primary_project(script_globals)
    if project is None:
        result["problems"].append("sem projeto primario: %s" % (access_error,))
        return finish(STATUS_FATAL)
    result["opened_project"] = project_access.get_project_path(project)

    container_spec = plan.get("container") or {}
    node_path = container_spec.get("node_path")
    result["container_node_path"] = node_path
    node_problems = []
    indexes = probe_cli.parse_node_id(node_path, node_problems,
                                      label="container.node_path")
    if indexes is None:
        result["problems"].extend(node_problems)
        return finish(CONTAINER_NOT_FOUND)

    trace = []
    container = probe_cli.descend(project, indexes, trace)
    if container is None:
        result["problems"].append("container nao alcancado pelo node_path")
        return finish(CONTAINER_NOT_FOUND)

    identity = object_identity(container)
    result["container_identity"] = identity
    expected_name = container_spec.get("expected_name")
    expected_type_guid = container_spec.get("expected_type_guid")
    if is_text(expected_type_guid) and expected_type_guid != EXPECTED_CONTAINER_TYPE_GUID:
        result["problems"].append(
            "plano declara container.expected_type_guid %r, divergente da "
            "constante medida %r" % (expected_type_guid, EXPECTED_CONTAINER_TYPE_GUID))
        return finish(STATUS_FATAL)
    if expected_name is not None and identity.get("name") != expected_name:
        result["problems"].append(
            "container resolvido e %r, plano espera %r"
            % (identity.get("name"), expected_name))
        return finish(CONTAINER_NOT_FOUND)
    if identity.get("type_guid") != EXPECTED_CONTAINER_TYPE_GUID:
        result["problems"].append(
            "type do container e %r, esperado %r"
            % (identity.get("type_guid"), EXPECTED_CONTAINER_TYPE_GUID))
        return finish(CONTAINER_NOT_FOUND)

    if len(indexes) > 1:
        parent_trace = []
        parent = probe_cli.descend(project, indexes[:-1], parent_trace)
        if parent is not None:
            matches = count_matching_siblings(parent, expected_name,
                                              EXPECTED_CONTAINER_TYPE_GUID)
            result["sibling_matches"] = matches
            if matches is not None and matches > 1:
                result["problems"].append(
                    "%d irmaos casam com a identidade do container; o caminho "
                    "por indice nao e estavel" % matches)
                return finish(CONTAINER_AMBIGUOUS)

    if mode == MODE_POSTSAVE:
        return finish(run_postsave(container, baseline, result["opened_project"],
                                   plan, expected_output_hash, result))
    return finish(run_preflight(container, result))


# --- artefatos --------------------------------------------------------------

def build_completion(result):
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": result.get("mode"),
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "opened_project": result.get("opened_project"),
        "container_node_path": result.get("container_node_path"),
        "program_texts_sha256": {
            "declaration": (result.get("program_texts") or {}).get("declaration_sha256"),
            "implementation": (result.get("program_texts") or {}).get("implementation_sha256"),
        },
        "structural_diff": result.get("structural_diff"),
        "errors": result.get("problems"),
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    textos = result.get("program_texts") or {}
    lines = [
        "# Probe 33 -- verificacao W1.3B (PROGRAM PRG_AI_TESTE)",
        "",
        "Somente leitura. Nenhuma API mutavel existe neste probe.",
        "",
        "- modo: `%s`" % result.get("mode"),
        "- status: **%s**" % result.get("status"),
        "- projeto aberto: `%s`" % result.get("opened_project"),
        "- container: `%s`" % result.get("container_node_path"),
        "",
        "## Textos observados",
        "",
        "- sha256 declaracao: `%s`" % textos.get("declaration_sha256"),
        "- sha256 implementacao: `%s`" % textos.get("implementation_sha256"),
        "",
        "## Diff estrutural",
        "",
        "- `%s`" % (result.get("structural_diff"),),
        "",
        "## Problemas",
        "",
    ]
    for problem in result.get("problems") or []:
        lines.append("- %s" % problem)
    if not (result.get("problems") or []):
        lines.append("- nenhum")
    lines.append("")
    return "\n".join(lines)


def write_artifacts(result, file_io):
    artifacts_dir = result.get("artifacts_dir")
    if not artifacts_dir:
        return None
    file_io.ensure_dir(artifacts_dir)
    written = []
    prefix = "w1-3b-postsave" if result.get("mode") == MODE_POSTSAVE else "w1-3b-preflight"
    file_io.write_json(os.path.join(artifacts_dir, prefix + "-tree.json"),
                       result.get("container_tree") or {})
    written.append(prefix + "-tree.json")
    file_io.write_json(os.path.join(artifacts_dir, prefix + "-program-texts.json"),
                       result.get("program_texts") or {})
    written.append(prefix + "-program-texts.json")
    if result.get("mode") == MODE_POSTSAVE:
        file_io.write_json(os.path.join(artifacts_dir, "w1-3b-structural-diff.json"),
                           result.get("structural_diff") or {})
        written.append("w1-3b-structural-diff.json")
    file_io.write_text(os.path.join(artifacts_dir, prefix + "-report.md"),
                       build_report_markdown(result))
    written.append(prefix + "-report.md")
    file_io.write_json(os.path.join(artifacts_dir, prefix + "-completion.json"),
                       build_completion(result))
    written.append(prefix + "-completion.json")
    return written


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s -- SOMENTE LEITURA" % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access

    try:
        result = run_verify(script_globals, list(sys.argv or []),
                            project_access, file_io, probe_cli)
    except Exception as exc:                                   # noqa: BLE001
        print("[FATAL] %r" % (exc,))
        try:
            traceback.print_exc()
        except Exception:                                      # noqa: BLE001
            pass
        return EXIT_BY_STATUS[STATUS_FATAL]

    try:
        write_artifacts(result, file_io)
    except Exception as exc:                                   # noqa: BLE001
        print("[ERROR] falha ao gravar artefatos: %r" % (exc,))

    print("[INFO] modo=%s status=%s" % (result.get("mode"), result.get("status")))
    for problem in result.get("problems") or []:
        print("[PROBLEM] %s" % problem)
    print("=" * 68)
    return result.get("exit_code")


if "projects" in globals():
    sys.exit(main())

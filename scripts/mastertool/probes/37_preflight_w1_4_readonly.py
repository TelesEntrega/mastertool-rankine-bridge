# -*- coding: utf-8 -*-
r"""37_preflight_w1_4_readonly.py -- verificador SOMENTE LEITURA de W1.4
(cadeia integrada `create_gvl` + `create_program` + tres `replace` + `save_as`,
seguida de `build` em abertura separada).

Contrato: `docs/28`. Plano normativo: `docs/32`.

Dois modos LITERAIS, de conjunto fechado:

    preflight  -- ANTES de qualquer mutacao, sobre a copia de trabalho.
                  Confere o `node_path` do container transportado pelo plano
                  contra a identidade MEDIDA (`Application`, type_guid), exige
                  que `GVL_AI_TESTE` e `PRG_AI_TESTE` NAO existam em lugar
                  nenhum da arvore, e congela a varredura RECURSIVA como
                  linha de base do diff estrutural.
    postsave   -- DEPOIS do `build`, sobre o arquivo de SAIDA reaberto.
                  Confere o hash do arquivo, exige que o diff recursivo
                  contenha EXATAMENTE os dois objetos novos da secao 6 de
                  `docs/32`, le os tres textos persistidos e confere as tres
                  presencas exigidas pela secao 7.

Por que varredura RECURSIVA e nao `get_children(False)`: W1.3B fechou com o
criterio "nenhum outro objeto foi alterado" verificado SO no nivel do
`Application`, porque `get_children(False)` devolve apenas filhos diretos
(`docs/34` secao 6). Aqui a varredura reaproveita
`common/read_only_project_scanner.ReadOnlyProjectScanner` -- o mesmo caminhador
de `probes/21`, com limite de profundidade e de nos --, e o diff e sobre a
arvore inteira.

Por que o `node_path` vem do plano e mesmo assim e CONFERIDO: `node_path` e
caminho de INDICES, e cartoes de I/O deslocam indices (`docs/32` secao 2). O
plano transporta o valor medido; este probe o resolve, compara nome e
`type_guid` contra as constantes deste modulo e ABORTA quando divergem. Um
plano que declarasse a identidade do container validaria a si mesmo.

NAO faz, por construcao -- nenhuma destas chamadas existe neste arquivo:
`create_gvl`, `create_program`, `create_pou`, `create_folder`, `create_dut`,
`save`, `save_as`, `replace`, `replace_line`, `insert`, `append` sobre
documento textual, `remove`, `rename`, `build`, `rebuild`, `clean`,
`import_xml`. Do documento textual so se le o getter `text`.

O acesso ao membro de tipo e LITERAL: `obj.type`, nunca `obj.type_guid` --
esse ultimo nome nao existe no proxy e devolveria None em silencio (achado
real de W1.1/W1.2).

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

SCRIPT_NAME = "37_preflight_w1_4_readonly.py"
SCHEMA_VERSION = "1.0"

EXPECTED_PHASE = "W1_4_INTEGRATED_BUILD"
EXPECTED_GVL_NAME = "GVL_AI_TESTE"
EXPECTED_PROGRAM_NAME = "PRG_AI_TESTE"
EXPECTED_CONTAINER_NAME = "Application"

# Medidos e congelados: container em `docs/29`, GVL em `docs/29`, POU em
# `docs/30`, linguagem ST em `docs/30`. Constantes de MODULO -- o plano pode
# DECLARAR os mesmos valores para registro, mas nunca os substitui.
EXPECTED_CONTAINER_TYPE_GUID = "639b491f-5557-464c-af91-1471bac9f549"
EXPECTED_GVL_TYPE_GUID = "ffbfa93a-b94d-45fc-a329-229860183b1d"
EXPECTED_PROGRAM_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
EXPECTED_ST_LANGUAGE_GUID = "cc393387-a21c-4f68-a3e3-84c36951965d"

# Textos canonicos de W1.4. CONSTANTES DESTE MODULO -- nunca vindas do plano:
# um plano que carregasse o texto final aprovaria a si mesmo.
#
# O prefixo `GVL_AI_TESTE.` na implementacao e OBRIGATORIO por causa do pragma
# `{attribute 'qualified_only'}`, que a GVL carrega desde o nascimento (medido
# em W1.1). Sem ele o `build` falharia por simbolo nao resolvido -- achado
# sobre CONTEUDO, que este marco existe para nao confundir com capacidade.
GVL_DECLARATION = (
    "{attribute 'qualified_only'}\n"
    "VAR_GLOBAL\n"
    "    g_xTesteCriacao : BOOL;\n"
    "END_VAR"
)
PROGRAM_DECLARATION = "PROGRAM PRG_AI_TESTE\nVAR\n    xLocal : BOOL;\nEND_VAR\n"
PROGRAM_IMPLEMENTATION = "xLocal := GVL_AI_TESTE.g_xTesteCriacao;\n"

# As TRES presencas da secao 7 de `docs/32`. Sao conferidas no texto
# PERSISTIDO, depois do build: um `build` sem erro e um indice que nao
# encontra a variavel seriam contraditorios, e a contradicao e achado.
REQUIRED_GVL_TOKENS = ("g_xTesteCriacao", "BOOL")
REQUIRED_IMPLEMENTATION_TOKENS = ("GVL_AI_TESTE.g_xTesteCriacao", "xLocal :=")

# --- estados, vocabulario fechado -------------------------------------------
PREFLIGHT_VERIFIED = "preflight_verified"
POSTSAVE_VERIFIED = "postsave_verified"
CONTAINER_NOT_FOUND = "container_not_found"
CONTAINER_AMBIGUOUS = "container_ambiguous"
NAME_CONFLICT = "name_conflict"
SCAN_INCOMPLETE = "scan_incomplete"
OBJECT_MISSING = "object_missing"
OBJECT_DUPLICATED = "object_duplicated"
OBJECT_TYPE_MISMATCH = "object_type_mismatch"
FINAL_TEXT_MISMATCH = "final_text_mismatch"
ST_PRESENCE_MISSING = "st_presence_missing"
OUTPUT_HASH_MISMATCH = "output_hash_mismatch"
STRUCTURAL_DIFF_UNEXPECTED = "structural_diff_unexpected"
TEXT_READ_GAP = "text_read_gap"
RUNTIME_MISMATCH = "runtime_mismatch"
PLAN_REJECTED = "plan_rejected"
STATUS_FATAL = "fatal"

MODE_PREFLIGHT = "preflight"
MODE_POSTSAVE = "postsave"
VALID_MODES = (MODE_PREFLIGHT, MODE_POSTSAVE)

ALL_STATUSES = (
    PREFLIGHT_VERIFIED, POSTSAVE_VERIFIED, CONTAINER_NOT_FOUND,
    CONTAINER_AMBIGUOUS, NAME_CONFLICT, SCAN_INCOMPLETE, OBJECT_MISSING,
    OBJECT_DUPLICATED, OBJECT_TYPE_MISMATCH, FINAL_TEXT_MISMATCH,
    ST_PRESENCE_MISSING, OUTPUT_HASH_MISMATCH, STRUCTURAL_DIFF_UNEXPECTED,
    TEXT_READ_GAP, RUNTIME_MISMATCH, PLAN_REJECTED, STATUS_FATAL,
)

# `text_read_gap` NAO e sucesso: limitacao registrada, veredito pendente de
# revisao humana -- mesmo vocabulario dos probes 29/31/33.
SUCCESS_STATUSES = (PREFLIGHT_VERIFIED, POSTSAVE_VERIFIED)

EXIT_BY_STATUS = {
    PREFLIGHT_VERIFIED: 0,
    POSTSAVE_VERIFIED: 0,
    CONTAINER_NOT_FOUND: 2,
    CONTAINER_AMBIGUOUS: 2,
    NAME_CONFLICT: 2,
    SCAN_INCOMPLETE: 2,
    OBJECT_MISSING: 2,
    OBJECT_DUPLICATED: 2,
    OBJECT_TYPE_MISMATCH: 2,
    RUNTIME_MISMATCH: 2,
    PLAN_REJECTED: 2,
    FINAL_TEXT_MISMATCH: 3,
    ST_PRESENCE_MISSING: 3,
    OUTPUT_HASH_MISMATCH: 3,
    STRUCTURAL_DIFF_UNEXPECTED: 3,
    TEXT_READ_GAP: 4,
    STATUS_FATAL: 1,
}

VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp")

# Limites da varredura recursiva: os mesmos de `probes/21` (docs/22). Limite
# infinito nao e oferecido -- arvore ciclica ou bug de navegacao viraria
# varredura sem fim.
SCAN_MAX_DEPTH = 32
SCAN_MAX_TOTAL_NODES = 20000
SCAN_MAX_CHILDREN_PER_NODE = 1024

# O diff da secao 6 de `docs/32`, literal. Nada alem disto e aceito.
ALLOWED_ADDITIONS = (
    (EXPECTED_GVL_NAME, EXPECTED_GVL_TYPE_GUID),
    (EXPECTED_PROGRAM_NAME, EXPECTED_PROGRAM_TYPE_GUID),
)

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
    """(digest, erro). Nunca levanta."""
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
    """CRLF equivale a LF; espaco em branco no fim de cada linha e ignorado;
    UMA quebra final e ignorada. Regra congelada em `docs/29` e reafirmada em
    `docs/31`.

    Via `re.sub`, nunca pelo metodo de string homonimo ao da API mutavel: ha
    um teste de busca LITERAL provando que a forma "ponto mais o nome do
    mutador mais parentese" nao aparece em lugar nenhum deste arquivo -- nem
    em codigo, nem em comentario, nem em docstring. Uma chamada de string com
    o mesmo nome contaminaria essa prova, e a propria frase que a explica
    tambem contaminaria, se fosse escrita com a grafia proibida.
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


def contains_all_tokens(text, tokens):
    """Presenca literal de cada token. Devolve a lista dos AUSENTES."""
    faltando = []
    if text is None:
        return list(tokens)
    for token in tokens:
        if token not in text:
            faltando.append(token)
    return faltando


# --- identidade --------------------------------------------------------------

def object_identity(obj):
    """Membros lidos pelo nome LITERAL. `type` e o membro; `type_guid` e o
    nome do campo na saida."""
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


def read_declaration(obj):
    """Somente o getter `text` do documento de declaracao."""
    result = {"text": None, "sha256": None, "gap": None, "error": None}
    try:
        if not hasattr(obj, "textual_declaration"):
            result["gap"] = "objeto nao expoe textual_declaration"
            return result
        document = obj.textual_declaration
        if document is None or not hasattr(document, "text"):
            result["gap"] = "textual_declaration sem documento ou sem text"
            return result
        text = document.text
        if text is not None:
            result["text"] = str(text)
            result["sha256"] = sha256_of_text(result["text"])
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = "declaration: %r" % (exc,)
    return result


def read_implementation(obj):
    """Somente o getter `text` do documento de implementacao."""
    result = {"text": None, "sha256": None, "gap": None, "error": None}
    try:
        if not hasattr(obj, "textual_implementation"):
            result["gap"] = "objeto nao expoe textual_implementation"
            return result
        document = obj.textual_implementation
        if document is None or not hasattr(document, "text"):
            result["gap"] = "textual_implementation sem documento ou sem text"
            return result
        text = document.text
        if text is not None:
            result["text"] = str(text)
            result["sha256"] = sha256_of_text(result["text"])
    except Exception as exc:                                   # noqa: BLE001
        result["error"] = "implementation: %r" % (exc,)
    return result


# --- nucleo puro sobre a varredura recursiva ---------------------------------

def node_signatures(flat_nodes):
    """Multiconjunto de `(name, type_guid)` da arvore INTEIRA.

    Assinatura por identidade, e nao por `node_id`: acrescentar um objeto
    desloca os indices dos irmaos seguintes, e um diff por caminho acusaria
    como "alterado" tudo o que so mudou de posicao.
    """
    assinaturas = []
    for entry in (flat_nodes or []):
        assinaturas.append((entry.get("name"), entry.get("type_guid")))
    return assinaturas


def multiset_difference(before, after):
    counts = {}
    for item in before:
        counts[item] = counts.get(item, 0) + 1
    added = []
    for item in after:
        pending = counts.get(item, 0)
        if pending > 0:
            counts[item] = pending - 1
        else:
            added.append(item)
    missing = []
    for item in before:
        if counts.get(item, 0) > 0:
            counts[item] = counts[item] - 1
            missing.append(item)
    return added, missing


def structural_diff(baseline_nodes, observed_nodes):
    """Diff recursivo. `allowed` e a lista LITERAL da secao 6 de `docs/32`."""
    added, missing = multiset_difference(node_signatures(baseline_nodes),
                                         node_signatures(observed_nodes))
    esperado = list(ALLOWED_ADDITIONS)
    inesperados, faltando_do_esperado = multiset_difference(esperado, added)
    return {
        "added": [list(item) for item in added],
        "missing": [list(item) for item in missing],
        "unexpected_additions": [list(item) for item in inesperados],
        "expected_additions_absent": [list(item) for item in faltando_do_esperado],
        "allowed_additions": [list(item) for item in esperado],
        "baseline_node_count": len(baseline_nodes or []),
        "observed_node_count": len(observed_nodes or []),
    }


def diff_is_exact(diff):
    """Exatamente os dois objetos novos, nada removido, nada a mais."""
    return (not diff.get("missing")
            and not diff.get("unexpected_additions")
            and not diff.get("expected_additions_absent"))


def find_unique_node(flat_nodes, name, expected_type_guid):
    """(entry, status_ou_None). Busca na arvore INTEIRA, por nome."""
    encontrados = [entry for entry in (flat_nodes or [])
                   if entry.get("name") == name]
    if not encontrados:
        return None, OBJECT_MISSING
    if len(encontrados) > 1:
        return None, OBJECT_DUPLICATED
    if encontrados[0].get("type_guid") != expected_type_guid:
        return encontrados[0], OBJECT_TYPE_MISMATCH
    return encontrados[0], None


def name_conflicts(flat_nodes):
    """`node_id` de cada objeto que ja usa um dos nomes-alvo. Vazio == livre."""
    conflitos = {}
    for name in (EXPECTED_GVL_NAME, EXPECTED_PROGRAM_NAME):
        conflitos[name] = [entry.get("node_id") for entry in (flat_nodes or [])
                           if entry.get("name") == name]
    return conflitos


def scan_is_usable(scan_result):
    """(ok, motivo). Varredura truncada NAO serve de linha de base: um diff
    contra arvore incompleta acusaria remocao onde houve so limite."""
    limites = (scan_result or {}).get("limits") or {}
    for chave in ("max_depth_reached", "max_total_nodes_reached",
                  "max_children_per_node_reached"):
        if limites.get(chave):
            return False, "varredura truncada: %s" % chave
    estatisticas = (scan_result or {}).get("statistics") or {}
    if estatisticas.get("scan_complete") is not True:
        return False, "varredura nao concluida (scan_complete != True)"
    if estatisticas.get("failed_nodes"):
        return False, ("%d no(s) falharam na varredura"
                       % estatisticas.get("failed_nodes"))
    return True, None


# --- orquestracao dos dois modos ---------------------------------------------

def run_preflight(container, flat_nodes, result):
    conflitos = name_conflicts(flat_nodes)
    result["name_conflicts"] = conflitos
    ocupados = [nome for nome in conflitos if conflitos[nome]]
    if ocupados:
        result["problems"].append(
            "nome(s)-alvo ja existentes no projeto de entrada: %s" % (ocupados,))
        return NAME_CONFLICT

    # A declaracao do container, apos as conferencias de identidade, e a
    # unica leitura extra: serve para registrar que o container nao e um
    # objeto textual sendo confundido com aplicacao.
    result["container_children_direct"] = count_matching_siblings(
        container, None, None)
    return PREFLIGHT_VERIFIED


def run_postsave(project, opened_path, plan, expected_output_hash, baseline,
                 flat_nodes, probe_cli, result):
    output_path = (plan.get("output_project") or {}).get("path")
    if not is_text(opened_path) or not is_text(output_path) or \
            os.path.normcase(os.path.abspath(opened_path)) != \
            os.path.normcase(os.path.abspath(output_path)):
        result["problems"].append(
            "projeto aberto (%r) nao e o output previsto (%r)"
            % (opened_path, output_path))
        return OUTPUT_HASH_MISMATCH

    observado, erro_hash = sha256_of_file(opened_path)
    result["output_sha256_observed"] = observado
    if erro_hash:
        result["problems"].append("sha256 do output ilegivel: %s" % erro_hash)
        return OUTPUT_HASH_MISMATCH
    if is_text(expected_output_hash) and observado != expected_output_hash:
        result["problems"].append(
            "sha256 do output diverge do registrado apos o save_as")
        return OUTPUT_HASH_MISMATCH

    baseline_nodes = baseline if isinstance(baseline, list) else \
        (baseline or {}).get("flat_nodes")
    if not baseline_nodes:
        result["problems"].append("baseline recursiva vazia ou ilegivel")
        return STATUS_FATAL

    diff = structural_diff(baseline_nodes, flat_nodes)
    result["structural_diff"] = diff
    if not diff_is_exact(diff):
        result["problems"].append(
            "diff estrutural fora da secao 6 de docs/32: acrescimos "
            "inesperados=%r, sumicos=%r, esperados ausentes=%r"
            % (diff.get("unexpected_additions"), diff.get("missing"),
               diff.get("expected_additions_absent")))
        return STRUCTURAL_DIFF_UNEXPECTED

    entrada_gvl, erro_gvl = find_unique_node(
        flat_nodes, EXPECTED_GVL_NAME, EXPECTED_GVL_TYPE_GUID)
    if erro_gvl is not None:
        result["problems"].append(
            "%s: %s" % (EXPECTED_GVL_NAME, erro_gvl))
        return erro_gvl
    entrada_prg, erro_prg = find_unique_node(
        flat_nodes, EXPECTED_PROGRAM_NAME, EXPECTED_PROGRAM_TYPE_GUID)
    if erro_prg is not None:
        result["problems"].append(
            "%s: %s" % (EXPECTED_PROGRAM_NAME, erro_prg))
        return erro_prg

    problemas_de_caminho = []
    indices_gvl = probe_cli.parse_node_id(
        entrada_gvl.get("node_id"), problemas_de_caminho, label="gvl.node_id")
    indices_prg = probe_cli.parse_node_id(
        entrada_prg.get("node_id"), problemas_de_caminho, label="program.node_id")
    if indices_gvl is None or indices_prg is None:
        result["problems"].extend(problemas_de_caminho)
        return OBJECT_MISSING

    trace_gvl = []
    objeto_gvl = probe_cli.descend(project, indices_gvl, trace_gvl)
    trace_prg = []
    objeto_prg = probe_cli.descend(project, indices_prg, trace_prg)
    if objeto_gvl is None or objeto_prg is None:
        result["problems"].append(
            "objeto encontrado na varredura mas nao alcancado por node_id "
            "(gvl=%r, program=%r)" % (trace_gvl, trace_prg))
        return OBJECT_MISSING

    texto_gvl = read_declaration(objeto_gvl)
    texto_prg_decl = read_declaration(objeto_prg)
    texto_prg_impl = read_implementation(objeto_prg)
    result["persisted_texts"] = {
        "gvl_declaration": texto_gvl,
        "program_declaration": texto_prg_decl,
        "program_implementation": texto_prg_impl,
    }
    for rotulo, leitura in (("gvl_declaration", texto_gvl),
                            ("program_declaration", texto_prg_decl),
                            ("program_implementation", texto_prg_impl)):
        if leitura.get("gap") or leitura.get("error") or leitura.get("text") is None:
            result["problems"].append(
                "texto persistido de %s nao pode ser lido: %s"
                % (rotulo, leitura.get("gap") or leitura.get("error")))
            return TEXT_READ_GAP

    if not texts_match(texto_gvl.get("text"), GVL_DECLARATION):
        result["problems"].append(
            "declaracao persistida da GVL diverge do texto canonico do modulo")
        return FINAL_TEXT_MISMATCH
    if not texts_match(texto_prg_decl.get("text"), PROGRAM_DECLARATION):
        result["problems"].append(
            "declaracao persistida do PROGRAM diverge do texto canonico")
        return FINAL_TEXT_MISMATCH
    if not texts_match(texto_prg_impl.get("text"), PROGRAM_IMPLEMENTATION):
        result["problems"].append(
            "implementacao persistida do PROGRAM diverge do texto canonico")
        return FINAL_TEXT_MISMATCH

    ausentes_gvl = contains_all_tokens(texto_gvl.get("text"), REQUIRED_GVL_TOKENS)
    ausentes_impl = contains_all_tokens(texto_prg_impl.get("text"),
                                        REQUIRED_IMPLEMENTATION_TOKENS)
    result["st_presences"] = {
        "gvl_declaration_missing": ausentes_gvl,
        "program_implementation_missing": ausentes_impl,
    }
    if ausentes_gvl or ausentes_impl:
        result["problems"].append(
            "presencas exigidas pela secao 7 de docs/32 ausentes: gvl=%r, "
            "implementacao=%r" % (ausentes_gvl, ausentes_impl))
        return ST_PRESENCE_MISSING

    return POSTSAVE_VERIFIED


def run_verify(script_globals, argv, project_access, file_io, probe_cli,
               scan_module, now=None):
    """Executa UM dos dois modos. Injecao explicita dos modulos para teste com
    dubles -- `scan_module` fornece `ReadOnlyProjectScanner` e `flatten_tree`,
    o MESMO caminhador de `probes/21`, nunca um segundo caminhador."""
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": None,
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "phase_expected": EXPECTED_PHASE,
        "problems": [],
        "runtime": None,
        "opened_project": None,
        "container_node_path": None,
        "container_identity": None,
        "container_children_direct": None,
        "flat_nodes": None,
        "scan_statistics": None,
        "name_conflicts": None,
        "structural_diff": None,
        "persisted_texts": None,
        "st_presences": None,
        "output_sha256_expected": None,
        "output_sha256_observed": None,
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
        problems.append("--mode invalido: %r (esperado um de %s)"
                        % (raw_mode, ", ".join(VALID_MODES)))
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
                "--baseline obrigatorio no modo postsave: sem a varredura "
                "recursiva do preflight nao existe diff estrutural")
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
        return finish(PLAN_REJECTED)
    if plan.get("gvl_name") != EXPECTED_GVL_NAME:
        result["problems"].append(
            "gvl_name do plano e %r, esperado %r"
            % (plan.get("gvl_name"), EXPECTED_GVL_NAME))
        return finish(PLAN_REJECTED)
    if plan.get("program_name") != EXPECTED_PROGRAM_NAME:
        result["problems"].append(
            "program_name do plano e %r, esperado %r"
            % (plan.get("program_name"), EXPECTED_PROGRAM_NAME))
        return finish(PLAN_REJECTED)
    if plan.get("st_language_guid") != EXPECTED_ST_LANGUAGE_GUID:
        result["problems"].append(
            "st_language_guid do plano (%r) diverge da constante medida (%r)"
            % (plan.get("st_language_guid"), EXPECTED_ST_LANGUAGE_GUID))
        return finish(PLAN_REJECTED)

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

    declarado = container_spec.get("expected_type_guid")
    if declarado is not None and declarado != EXPECTED_CONTAINER_TYPE_GUID:
        result["problems"].append(
            "plano declara container.expected_type_guid %r, divergente da "
            "constante medida %r" % (declarado, EXPECTED_CONTAINER_TYPE_GUID))
        return finish(PLAN_REJECTED)

    trace = []
    container = probe_cli.descend(project, indexes, trace)
    if container is None:
        result["problems"].append(
            "container nao alcancado pelo node_path %r (trace=%r). node_path e "
            "caminho de INDICES: cartoes de I/O deslocam indices."
            % (node_path, trace))
        return finish(CONTAINER_NOT_FOUND)

    identity = object_identity(container)
    result["container_identity"] = identity
    if identity.get("name") != EXPECTED_CONTAINER_NAME:
        result["problems"].append(
            "container resolvido e %r, esperado %r"
            % (identity.get("name"), EXPECTED_CONTAINER_NAME))
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
            matches = count_matching_siblings(parent, EXPECTED_CONTAINER_NAME,
                                              EXPECTED_CONTAINER_TYPE_GUID)
            result["sibling_matches"] = matches
            if matches is not None and matches > 1:
                result["problems"].append(
                    "%d irmaos casam com a identidade do container; o caminho "
                    "por indice nao e estavel" % matches)
                return finish(CONTAINER_AMBIGUOUS)

    scanner = scan_module.ReadOnlyProjectScanner(
        max_depth=SCAN_MAX_DEPTH,
        max_total_nodes=SCAN_MAX_TOTAL_NODES,
        max_children_per_node=SCAN_MAX_CHILDREN_PER_NODE)
    scan_result = scanner.scan(project)
    result["scan_statistics"] = (scan_result or {}).get("statistics")
    usavel, motivo = scan_is_usable(scan_result)
    if not usavel:
        result["problems"].append(
            "varredura recursiva inutilizavel: %s. Sem arvore completa nao "
            "existe a afirmacao 'nenhum outro objeto foi alterado'." % motivo)
        return finish(SCAN_INCOMPLETE)
    flat_nodes = scan_module.flatten_tree(scan_result["tree"])
    result["flat_nodes"] = flat_nodes

    if mode == MODE_POSTSAVE:
        return finish(run_postsave(project, result["opened_project"], plan,
                                   expected_output_hash, baseline, flat_nodes,
                                   probe_cli, result))
    return finish(run_preflight(container, flat_nodes, result))


# --- artefatos ---------------------------------------------------------------

def build_completion(result):
    textos = result.get("persisted_texts") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": result.get("mode"),
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "phase_expected": result.get("phase_expected"),
        "opened_project": result.get("opened_project"),
        "container_node_path": result.get("container_node_path"),
        "name_conflicts": result.get("name_conflicts"),
        "structural_diff": result.get("structural_diff"),
        "st_presences": result.get("st_presences"),
        "output_sha256_expected": result.get("output_sha256_expected"),
        "output_sha256_observed": result.get("output_sha256_observed"),
        "persisted_texts_sha256": {
            "gvl_declaration": (textos.get("gvl_declaration") or {}).get("sha256"),
            "program_declaration": (textos.get("program_declaration") or {}).get("sha256"),
            "program_implementation": (textos.get("program_implementation") or {}).get("sha256"),
        },
        "scan_statistics": result.get("scan_statistics"),
        "errors": result.get("problems"),
        "generated_at": result.get("finished_at"),
    }


def build_report_markdown(result):
    textos = result.get("persisted_texts") or {}
    lines = [
        "# Probe 37 -- verificacao W1.4 (cadeia integrada + build)",
        "",
        "Somente leitura. Nenhuma API mutavel existe neste probe.",
        "",
        "- modo: `%s`" % result.get("mode"),
        "- status: **%s**" % result.get("status"),
        "- projeto aberto: `%s`" % result.get("opened_project"),
        "- container: `%s`" % result.get("container_node_path"),
        "- nos na varredura recursiva: `%s`"
        % len(result.get("flat_nodes") or []),
        "",
        "## Conflito de nomes-alvo",
        "",
        "- `%s`" % (result.get("name_conflicts"),),
        "",
        "## Diff estrutural recursivo",
        "",
        "- `%s`" % (result.get("structural_diff"),),
        "",
        "## Textos persistidos",
        "",
        "- sha256 declaracao GVL: `%s`"
        % (textos.get("gvl_declaration") or {}).get("sha256"),
        "- sha256 declaracao PROGRAM: `%s`"
        % (textos.get("program_declaration") or {}).get("sha256"),
        "- sha256 implementacao PROGRAM: `%s`"
        % (textos.get("program_implementation") or {}).get("sha256"),
        "- presencas ausentes: `%s`" % (result.get("st_presences"),),
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
    prefix = "w1-4-postsave" if result.get("mode") == MODE_POSTSAVE else "w1-4-preflight"
    file_io.write_json(os.path.join(artifacts_dir, prefix + "-flat-nodes.json"),
                       result.get("flat_nodes") or [])
    written.append(prefix + "-flat-nodes.json")
    file_io.write_json(os.path.join(artifacts_dir, prefix + "-container.json"),
                       result.get("container_identity") or {})
    written.append(prefix + "-container.json")
    if result.get("mode") == MODE_POSTSAVE:
        file_io.write_json(os.path.join(artifacts_dir, "w1-4-structural-diff.json"),
                           result.get("structural_diff") or {})
        written.append("w1-4-structural-diff.json")
        file_io.write_json(os.path.join(artifacts_dir, "w1-4-persisted-texts.json"),
                           result.get("persisted_texts") or {})
        written.append("w1-4-persisted-texts.json")
    file_io.write_text(os.path.join(artifacts_dir, prefix + "-report.md"),
                       build_report_markdown(result))
    written.append(prefix + "-report.md")
    # Por ULTIMO: a completion e o sinal de conclusao. Artefato de conclusao
    # ausente e falha de ARTEFATO, categoria propria (docs/28 secao 11).
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
    from common import read_only_project_scanner

    try:
        result = run_verify(script_globals, list(sys.argv or []),
                            project_access, file_io, probe_cli,
                            read_only_project_scanner)
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

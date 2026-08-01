# -*- coding: utf-8 -*-
"""Infraestrutura pura de autoria textual: normalizacao, hash, diff, journal e
manifesto/completion genericos.

Existe porque `sha256_of_text`, `sha256_of_file`, `multiset_difference`,
`Journal`, `build_completion`, a normalizacao textual e `object_identity`
apareciam DUPLICADOS, quase linha a linha, entre
`probes/29_preflight_program_w1_2_readonly.py` e
`probes/30_create_program_w1_2.py` (docs/31). Consolidar aqui evita que a
proxima fase (W1.3, escrita textual controlada) duplique de novo, e permite
testar a logica pura sem MasterTool, sem CLR e sem I/O real.

Este modulo e BIBLIOTECA PURA: nenhuma funcao aqui abre projeto, cria objeto,
salva arquivo, decide fase ou seleciona operacao. A unica excecao declarada e
`Journal.record`, que escreve no arquivo do journal SOMENTE se uma funcao de
escrita for injetada pelo chamador -- o modulo nunca importa `file_io` para
isso, exatamente para continuar testavel sem tocar disco.

IronPython 2.7: sem f-string, sem pathlib, sem dataclass, sem anotacao de
tipo, identificadores somente ASCII. Compativel tambem com CPython 3 (onde
roda a suite de testes).
"""
from __future__ import print_function

import hashlib

try:
    _STRING_TYPES = (basestring,)  # noqa: F821
except NameError:
    _STRING_TYPES = (str,)


def is_text(value):
    """Texto nao vazio. Usado nas checagens defensivas deste modulo."""
    return isinstance(value, _STRING_TYPES) and value != ""


# --- normalizacao textual ----------------------------------------------------

def normalize_text(text):
    """Aplica a regra congelada de normalizacao (docs/29, repetida em
    docs/31 Sec. Normalizacao) e NADA MAIS:

        CRLF e LF equivalentes
        espaco em branco no fim de cada linha ignorado
        UMA quebra de linha final ignorada
        qualquer outra diferenca e DIVERGENCIA

    Existe centralizada porque a regra e a MESMA em toda fase de escrita
    textual controlada (W1.2, W1.3...); duplica-la por probe e o tipo exato
    de risco que fez este modulo nascer. Nunca levanta: entrada que nao e
    texto vira string vazia normalizada, e o chamador decide se isso e
    divergencia.
    """
    if not isinstance(text, _STRING_TYPES):
        text = ""
    # CRLF -> LF primeiro, para as linhas ficarem em base unica antes do
    # rstrip por linha.
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = unified.split("\n")
    stripped_lines = [line.rstrip(" \t\f\v") for line in lines]
    # Uma quebra de linha final ignorada: se o texto terminava em "\n", o
    # split produz uma ultima linha vazia -- remove exatamente UMA, nao mais.
    if len(stripped_lines) > 1 and stripped_lines[-1] == "":
        stripped_lines = stripped_lines[:-1]
    return "\n".join(stripped_lines)


def texts_equivalent(a, b):
    """Igualdade sob a normalizacao congelada. Nunca levanta."""
    return normalize_text(a) == normalize_text(b)


# --- hash ---------------------------------------------------------------

def sha256_of_text(text):
    """SHA-256 hexadecimal do texto bruto (sem normalizar), UTF-8.

    Deliberadamente do texto BRUTO, nao do normalizado: comparar hash bruto
    e hash normalizado lado a lado (ver `text_diff_report`) e o que permite
    provar que uma mudanca e so de fim-de-linha/espaco, e nao de conteudo.
    Nunca levanta -- entrada invalida vira None, e quem chama decide se isso
    e falha de precondicao.
    """
    try:
        if not isinstance(text, _STRING_TYPES):
            return None
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except Exception:                                          # noqa: BLE001
        return None


def sha256_of_file(path):
    """(digest, erro). Nunca levanta.

    Devolve o par para que o chamador registre o erro no manifesto/journal
    em vez de o probe morrer no meio de uma sequencia de mutacoes -- o mesmo
    padrao ja usado nos probes 29/30, agora com um unico dono.
    """
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


# --- diff textual -------------------------------------------------------

def _split_lines(text):
    if not isinstance(text, _STRING_TYPES):
        text = ""
    return text.split("\n")


def _first_divergent_line(expected_normalized, observed_normalized):
    """Indice 1-based da primeira linha normalizada que diverge, ou None
    quando os textos normalizados sao identicos.

    1-based porque e assim que um humano le um relatorio de diff (docs/31
    fala em "linha certa" para revisao humana); indice de lista comecaria em
    0 e obrigaria o leitor a somar 1 de cabeca toda vez.
    """
    expected_lines = _split_lines(expected_normalized)
    observed_lines = _split_lines(observed_normalized)
    limit = max(len(expected_lines), len(observed_lines))
    for index in range(limit):
        expected_line = expected_lines[index] if index < len(expected_lines) else None
        observed_line = observed_lines[index] if index < len(observed_lines) else None
        if expected_line != observed_line:
            return index + 1, expected_line, observed_line
    return None, None, None


def text_diff_report(expected, observed):
    """Relatorio completo de comparacao textual sob a normalizacao
    congelada. Nunca levanta -- e o unico jeito de um probe decidir
    "divergiu ou nao" sem arriscar excecao no meio de uma sequencia de
    mutacoes ja em andamento.

    Devolve sha256 do bruto e do normalizado de cada lado: o bruto prova o
    que o MasterTool realmente escreveu/leu; o normalizado prova que a
    divergencia (se houver) e so de conteudo, nao de fim de linha.
    """
    try:
        expected_normalized = normalize_text(expected)
        observed_normalized = normalize_text(observed)
        equivalent = (expected_normalized == observed_normalized)
        divergent_line, expected_line, observed_line = (
            (None, None, None) if equivalent
            else _first_divergent_line(expected_normalized, observed_normalized))
        return {
            "equivalent": equivalent,
            "expected_sha256": sha256_of_text(expected),
            "observed_sha256": sha256_of_text(observed),
            "expected_normalized_sha256": sha256_of_text(expected_normalized),
            "observed_normalized_sha256": sha256_of_text(observed_normalized),
            "first_divergent_line": divergent_line,
            "expected_line": expected_line,
            "observed_line": observed_line,
            "line_counts": {
                "expected": len(_split_lines(expected_normalized)),
                "observed": len(_split_lines(observed_normalized)),
            },
        }
    except Exception as exc:                                   # noqa: BLE001
        return {
            "equivalent": False,
            "expected_sha256": None,
            "observed_sha256": None,
            "expected_normalized_sha256": None,
            "observed_normalized_sha256": None,
            "first_divergent_line": None,
            "expected_line": None,
            "observed_line": None,
            "line_counts": {"expected": None, "observed": None},
            "error": repr(exc),
        }


# --- diff estrutural ------------------------------------------------------

def multiset_difference(before_names, after_names):
    """Diferenca de multiconjuntos (respeita repeticao de nome).

    Existe porque nomes de objeto NAO sao unicos na arvore do MasterTool
    (achado real: `MainPrg` aparece duas vezes, como POU e como referencia de
    chamada, docs/29/30) -- um `set()` engoliria a repeticao e mentiria sobre
    quantos objetos realmente mudaram.
    """
    counts = {}
    for name in (before_names or []):
        counts[name] = counts.get(name, 0) + 1
    added = []
    for name in (after_names or []):
        pending = counts.get(name, 0)
        if pending > 0:
            counts[name] = pending - 1
        else:
            added.append(name)
    missing = []
    for name in (before_names or []):
        if counts.get(name, 0) > 0:
            counts[name] = counts[name] - 1
            missing.append(name)
    return added, missing


def object_identity(obj):
    """Identidade estrutural minima de UM objeto da arvore, lida por membro
    LITERAL (sem reflexao/dispatch dinamico).

    Consolidado aqui porque os probes 29 e 30 tinham a MESMA funcao,
    caractere por caractere -- inclusive o comentario sobre a troca
    `type`/`type_guid` ter reprovado um preflight real em W1.1. `getattr` nao
    e usado de proposito: cada membro e acessado pelo nome escrito no
    codigo, para que o modulo nunca invente acesso a uma API nao catalogada.
    """
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


def structural_diff(before_snapshot, after_snapshot, allowed_additions):
    """Compara dois snapshots `{"persistent": [...], "transient": [...]}`
    (cada item com ao menos `name`) e devolve o veredito estrutural que os
    probes 29/30 calculavam inline apos cada mutacao.

    `allowed_additions` e uma allowlist FECHADA e ORDENADA de nomes
    persistentes que podem aparecer -- exatamente a mesma logica de
    `ALLOWED_PERSISTENT_ADDITIONS` do probe 29 e do `verify_created_object`
    do probe 30, generalizada para qualquer numero de adicoes esperadas.
    Nunca levanta: snapshot malformado vira listas vazias, e o chamador ve
    isso no resultado (`within_allowlist=False`).
    """
    def names_of(snapshot, key):
        try:
            return [item.get("name") for item in ((snapshot or {}).get(key) or [])]
        except Exception:                                      # noqa: BLE001
            return []

    before_persistent = names_of(before_snapshot, "persistent")
    after_persistent = names_of(after_snapshot, "persistent")
    before_transient = names_of(before_snapshot, "transient")
    after_transient = names_of(after_snapshot, "transient")

    added, missing = multiset_difference(before_persistent, after_persistent)
    transient_added, _transient_missing = multiset_difference(
        before_transient, after_transient)

    allowed = list(allowed_additions or [])
    within_allowlist = (not missing) and (added == allowed)

    return {
        "added": added,
        "missing": missing,
        "transient_added": transient_added,
        "within_allowlist": within_allowlist,
    }


# --- journal --------------------------------------------------------------

class Journal(object):
    """Registro append-only. Cada entrada leva `sequence` (0-based, ordem de
    insercao) e `timestamp` (via a funcao `now` injetada).

    A escrita em arquivo e OPCIONAL e feita por uma funcao `writer` injetada
    pelo chamador -- nunca por `import common.file_io` direto neste modulo.
    Isso preserva a biblioteca pura e testavel sem tocar disco; quem precisa
    do arquivo real passa `file_io.append_text` (ou equivalente) como
    `writer`. `path` e mantido apenas como metadado repassado ao `writer`,
    nunca aberto por este objeto.
    """

    def __init__(self, now, writer=None, path=None):
        self.now = now
        self.writer = writer
        self.path = path
        self.entries = []

    def record(self, entry):
        """Acrescenta uma entrada. Nunca sobrescreve nem remove uma
        anterior -- e o que faz o journal ser prova de ordem, nao so um log."""
        ordered = {}
        for key in entry:
            ordered[key] = entry[key]
        ordered["timestamp"] = self.now()
        ordered["sequence"] = len(self.entries)
        self.entries.append(ordered)
        if self.writer is not None and self.path:
            try:
                import json
                self.writer(self.path, json.dumps(ordered, sort_keys=True) + "\n")
            except Exception:                                  # noqa: BLE001
                pass
        return ordered


# --- manifesto / completion genericos --------------------------------------

VOLATILE_FIELDS = ("generated_at", "started_at", "finished_at", "timestamp")


def strip_volatile(payload):
    """Copia de `payload` sem os campos declarados em `VOLATILE_FIELDS`.

    Existe para permitir provar DETERMINISMO: duas execucoes com a mesma
    entrada devem produzir o mesmo payload uma vez removidos os campos que
    so variam por causa do relogio. Nunca levanta; entrada que nao e dict
    devolve dict vazio.
    """
    try:
        result = {}
        for key in payload:
            if key in VOLATILE_FIELDS:
                continue
            result[key] = payload[key]
        return result
    except Exception:                                          # noqa: BLE001
        return {}


def build_manifest(result, artifact_names, exit_code_by_status,
                   volatile_fields=None):
    """Manifesto generico: todo o `result` (exceto `journal`, que tem
    artefato proprio) mais os metadados fixos de artefatos e codigos de
    saida.

    Generico e parametrizado porque cada probe declara seu proprio conjunto
    de nomes de arquivo e de codigos de saida -- este modulo nao escolhe
    fase nem operacao, so monta a forma comum do manifesto.
    """
    manifest = {}
    for key in result:
        if key == "journal":
            continue
        manifest[key] = result[key]
    manifest["artifact_names"] = list(artifact_names or [])
    manifest["volatile_fields"] = list(volatile_fields or VOLATILE_FIELDS)
    manifest["exit_code_by_status"] = dict(exit_code_by_status or {})
    return manifest


def build_completion(status, exit_code, extra_fields, schema_version,
                     script_name, finished_at):
    """Registro final generico de conclusao, escrito por ULTIMO em cada
    probe -- e o sinal de que a execucao terminou (ver probes 29/30).

    Os campos especificos de cada fase (ex.: `st_language_guid`,
    `created_declaration_sha256`) entram via `extra_fields`, que este modulo
    apenas mescla por cima dos campos fixos; nenhuma logica de fase mora
    aqui.
    """
    completion = {
        "schema_version": schema_version,
        "script": script_name,
        "status": status,
        "exit_code": exit_code,
        "generated_at": finished_at,
    }
    for key in (extra_fields or {}):
        completion[key] = extra_fields[key]
    return completion

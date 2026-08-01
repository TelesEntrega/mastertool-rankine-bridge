# -*- coding: utf-8 -*-
r"""45_author_w3_idiomatic_call.py -- W3: a chamada IDIOMATICA.

Contrato: `docs/41`. Motivo: `docs/39` secao 1 -- o build de W2 devolveu um
aviso do FABRICANTE dizendo que o padrao correto e outro.

DUAS invocacoes mutaveis, e so duas, cada uma com a guarda na linha
IMEDIATAMENTE anterior:

    assert_controlled_write_allowed("replace")
    documento.replace(texto_final)

    assert_controlled_write_allowed("save_as")
    project.save_as(caminho_de_saida)

O QUE MUDA EM RELACAO A W2. W2 acrescentou o PROGRAM a lista de chamadas da
task -- funciona, compila, e o fabricante desaconselha. Aqui a chamada vai para
dentro da POU de perfil (`UserPrg`), que e onde a Altus manda pendurar codigo de
usuario. A capacidade e a mesma que W1.3B ja provou (`replace` sobre
`IScriptTextDocument`); o que muda e ONDE.

`replace` SUBSTITUI O DOCUMENTO INTEIRO. Nao existe "acrescentar" na API. Por
isso o texto final e montado AQUI, a partir do texto que o preflight leu, e o
probe recusa rodar se o texto entregue nao conferir com o SHA-256 registrado:
escrever sem ter lido apagaria o codigo do fabricante, e escrever a partir de
uma leitura velha apagaria o que mudou no meio.

A MONTAGEM E DETERMINISTICA e esta em `compose_implementation`, funcao pura,
testada sem MasterTool nenhum. Ela nao inventa nada: preserva o texto original
integralmente, acrescenta um comentario de origem e a chamada, e nunca duplica
a chamada se ela ja estiver la.

NAO faz: `create_*`, `add`, `insert`, `remove`, `build`, `save`, `import_*`.

Compatibilidade: IronPython 2.7.12.
"""
from __future__ import print_function

import hashlib
import json
import os
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
REPO_ROOT = (os.path.abspath(os.path.join(_MASTERTOOL_DIR, "..", ".."))
             if _MASTERTOOL_DIR else None)

SCRIPT_NAME = "45_author_w3_idiomatic_call.py"
SCHEMA_VERSION = "1.0"

EXPECTED_PHASE = "W3_IDIOMATIC_CALL"
EXPECTED_OPERATION_ID = "w3-idiomatic-call"
EXPECTED_PLAN_OPERATIONS = ("replace", "save_as")

CALL_SITE_REPLACE = "probes/45_author_w3_idiomatic_call.py::replace_guarded"
CALL_SITE_SAVE_AS = "probes/45_author_w3_idiomatic_call.py::save_as_guarded"

# Repetidas aqui de proposito, e nao importadas do probe 44: os dois arquivos
# rodam em processos SEPARADOS, e um import entre probes criaria acoplamento
# que o produto nao garante. A duplicacao e conferida por teste.
PROFILE_POU_NAMES = ("StartPrg", "UserPrg", "ActivePrg", "NonSkippedPrg")
POU_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"

# O comentario que marca a origem da linha. Existe para que quem abrir o
# projeto no MasterTool saiba de onde veio a chamada -- um projeto gerado que
# nao diz que foi gerado obriga o proximo engenheiro a adivinhar.
ORIGIN_COMMENT = "(* chamada acrescentada por mastertool-rankine-bridge (W3) *)"

MAX_DEPTH = 8
MAX_TOTAL_NODES = 1024
MAX_CHILDREN_PER_NODE = 128

STATUS_SAVED_AS = "saved_as"
STATUS_PRECONDITION_FAILED = "precondition_failed"
STATUS_HOST_NOT_FOUND = "call_host_not_found"
STATUS_TEXT_DRIFTED = "text_drifted"
STATUS_CALL_ALREADY_PRESENT = "call_already_present"
STATUS_REPLACE_FAILED = "replace_failed"
STATUS_SAVE_FAILED = "save_failed"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_SAVED_AS, STATUS_PRECONDITION_FAILED, STATUS_HOST_NOT_FOUND,
    STATUS_TEXT_DRIFTED, STATUS_CALL_ALREADY_PRESENT, STATUS_REPLACE_FAILED,
    STATUS_SAVE_FAILED, STATUS_FATAL,
)

SUCCESS_STATUSES = (STATUS_SAVED_AS,)

EXIT_BY_STATUS = {
    STATUS_SAVED_AS: 0,
    STATUS_PRECONDITION_FAILED: 2,
    STATUS_HOST_NOT_FOUND: 2,
    STATUS_TEXT_DRIFTED: 2,
    STATUS_CALL_ALREADY_PRESENT: 2,
    STATUS_REPLACE_FAILED: 3,
    STATUS_SAVE_FAILED: 3,
    STATUS_FATAL: 1,
}

ARTIFACT_NAMES = ("w3-manifest.json", "w3-authored-text.json",
                  "w3-completion.json")

try:
    _STRING_TYPES = (basestring,)                                  # noqa: F821
except NameError:
    _STRING_TYPES = (str,)


def is_text(value):
    return isinstance(value, _STRING_TYPES) and value != ""


def as_text(value):
    if value is None:
        return None
    if isinstance(value, _STRING_TYPES):
        return value
    try:
        return str(value)
    except Exception:                                              # noqa: BLE001
        return None


def sha256_of_text(text):
    if text is None:
        return None
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except Exception:                                              # noqa: BLE001
        return None


def sha256_of_file(path):
    if not is_text(path) or not os.path.isfile(path):
        return None, "arquivo inexistente: %r" % (path,)
    try:
        digest = hashlib.sha256()
        handle = open(path, "rb")
        try:
            while True:
                bloco = handle.read(65536)
                if not bloco:
                    break
                digest.update(bloco)
        finally:
            handle.close()
        return digest.hexdigest(), None
    except Exception as exc:                                       # noqa: BLE001
        return None, "leitura falhou: %r" % (exc,)


# =============================================================================
# a montagem do texto -- funcao PURA, sem MasterTool
# =============================================================================

def normalize(text):
    """As tres regras congeladas desde W1.3A."""
    if text is None:
        return None
    unificado = text.replace("\r\n", "\n").replace("\r", "\n")
    linhas = [linha.rstrip() for linha in unificado.split("\n")]
    while linhas and linhas[-1] == "":
        linhas.pop()
    return "\n".join(linhas)


def call_line(program_name):
    return "%s();" % (program_name,)


def already_calls(text, program_name):
    if text is None or not is_text(program_name):
        return False
    return call_line(program_name) in normalize(text)


def compose_implementation(original, program_name):
    """Texto final = original + comentario de origem + chamada.

    PURA e DETERMINISTICA -- a mesma entrada produz sempre a mesma saida, o que
    e condicao para que este marco possa ser medido como determinista do mesmo
    jeito que W1.4 foi (docs/40).

    Preserva o original INTEGRALMENTE. `replace` substitui o documento inteiro,
    entao "acrescentar" e sempre "reescrever com o que ja estava mais o novo" --
    e se o que ja estava nao entrar aqui, ele desaparece do projeto.

    Termina com UMA quebra de linha: e a forma que a regra de normalizacao trata
    como equivalente, e a que o produto devolve nas leituras medidas.
    """
    if not is_text(program_name):
        raise ValueError("program_name vazio")
    base = normalize(original) if original is not None else ""
    partes = []
    if base != "":
        partes.append(base)
    partes.append(ORIGIN_COMMENT)
    partes.append(call_line(program_name))
    return "\n".join(partes) + "\n"


# =============================================================================
# leitura da arvore
# =============================================================================

def read_children(node):
    try:
        colecao = node.get_children(False)
    except Exception as exc:                                       # noqa: BLE001
        return [], "get_children falhou: %r" % (exc,)
    if colecao is None:
        return [], "get_children devolveu None"
    try:
        total = colecao.Count
    except Exception as exc:                                       # noqa: BLE001
        return [], "Count falhou: %r" % (exc,)
    if total is None or total < 0 or total > MAX_CHILDREN_PER_NODE:
        return [], "Count fora de faixa: %r" % (total,)
    filhos = []
    for indice in range(total):
        try:
            filhos.append(colecao[indice])
        except Exception as exc:                                   # noqa: BLE001
            return filhos, "indexador falhou em %d: %r" % (indice, exc)
    return filhos, None


def read_name(node):
    try:
        return as_text(node.get_name(False))
    except Exception:                                              # noqa: BLE001
        return None


def read_type_guid(node):
    try:
        return as_text(node.type)
    except Exception:                                              # noqa: BLE001
        return None


def find_call_host(project, host_name):
    """Acha a POU de perfil por NOME **e** TIPO. Devolve `(no, node_id, erros)`.

    Duplicata NAO e desempatada: com dois candidatos validos, o probe devolve
    None e registra -- escolher um por ordem de varredura seria acertar por
    sorte, e a mutacao iria para o objeto errado sem ninguem perceber.
    """
    erros = []
    if project is None:
        return None, None, ["projeto indisponivel"]
    achado = None
    achado_id = None
    pilha = [(project, "root", 0)]
    visitados = 0
    while pilha:
        if visitados >= MAX_TOTAL_NODES:
            erros.append("varredura truncada em %d nos" % MAX_TOTAL_NODES)
            break
        no_atual, node_id, profundidade = pilha.pop()
        visitados += 1
        if read_name(no_atual) == host_name:
            tipo = read_type_guid(no_atual)
            if tipo == POU_TYPE_GUID:
                if achado is None:
                    achado, achado_id = no_atual, node_id
                else:
                    erros.append("nome de perfil duplicado: %s em %s e %s"
                                 % (host_name, achado_id, node_id))
                    return None, None, erros
            else:
                erros.append("%s em %s tem type %r, e nao o de PROGRAM"
                             % (host_name, node_id, tipo))
        if profundidade >= MAX_DEPTH:
            continue
        filhos, erro = read_children(no_atual)
        if erro:
            erros.append("%s: %s" % (node_id, erro))
        indice = len(filhos) - 1
        while indice >= 0:
            pilha.append((filhos[indice], "%s/%d" % (node_id, indice),
                          profundidade + 1))
            indice -= 1
    return achado, achado_id, erros


def read_implementation_document(node):
    """`(documento, texto, erro)`. O indicador e conferido ANTES."""
    try:
        if not hasattr(node, "has_textual_implementation"):
            return None, None, "objeto nao expoe has_textual_implementation"
        if not node.has_textual_implementation:
            return None, None, "has_textual_implementation e falso"
        documento = node.textual_implementation
    except Exception as exc:                                       # noqa: BLE001
        return None, None, "acesso ao documento falhou: %r" % (exc,)
    if documento is None:
        return None, None, "textual_implementation devolveu None"
    try:
        texto = as_text(documento.text)
    except Exception as exc:                                       # noqa: BLE001
        return documento, None, "leitura de .text falhou: %r" % (exc,)
    return documento, texto, None


# =============================================================================
# as DUAS chamadas mutaveis
# =============================================================================

def replace_guarded(document, final_text, safety):
    """Primeira mutacao. Entre a guarda e a chamada nao ha ramo, laco, wrapper
    nem log."""
    safety.assert_controlled_write_allowed("replace")
    document.replace(final_text)
    return True


def save_as_guarded(project, output_path, safety):
    """Segunda mutacao. `save_as`, nunca `save`: `save` sobrescreveria a copia
    de trabalho e destruiria a testemunha do estado inicial."""
    safety.assert_controlled_write_allowed("save_as")
    project.save_as(output_path)
    return True


# =============================================================================
# orquestracao
# =============================================================================

def run_author(script_globals, argv, safety, project_access, file_io, probe_cli,
               now=None):
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "phase_expected": EXPECTED_PHASE,
        "phase_observed": None,
        "plan_path": None,
        "plan_sha256": None,
        "artifacts_dir": None,
        "opened_project": None,
        "output_project_path": None,
        "output_sha256": None,
        "call_host_name": None,
        "call_host_node_id": None,
        "program_name": None,
        "text": {"original": None, "original_sha256": None,
                 "final": None, "final_sha256": None},
        "operations_requested": [],
        "operations_authorized": [],
        "operations_executed": [],
        "problems": [],
        "gap_notes": [],
        "journal": [],
    }

    def finish(status):
        result["status"] = status
        result["finished_at"] = now()
        result["exit_code"] = EXIT_BY_STATUS.get(status, 1)
        result["is_success"] = status in SUCCESS_STATUSES
        return result

    problems = result["problems"]

    saida_artefatos = probe_cli.find_arg(argv, "output")
    if is_text(saida_artefatos):
        result["artifacts_dir"] = os.path.abspath(saida_artefatos)

    caminho_plano = probe_cli.find_arg(argv, "plan")
    if not is_text(caminho_plano):
        problems.append("--plan e obrigatorio")
        return finish(STATUS_PRECONDITION_FAILED)
    result["plan_path"] = caminho_plano
    hash_plano, erro_plano = sha256_of_file(caminho_plano)
    if erro_plano:
        problems.append("plano ilegivel: %s" % erro_plano)
        return finish(STATUS_PRECONDITION_FAILED)
    result["plan_sha256"] = hash_plano

    try:
        handle = open(caminho_plano, "rb")
        try:
            plano = json.loads(handle.read().decode("utf-8"))
        finally:
            handle.close()
    except Exception as exc:                                       # noqa: BLE001
        problems.append("plano nao e JSON valido: %r" % (exc,))
        return finish(STATUS_PRECONDITION_FAILED)

    if result["artifacts_dir"] is None and is_text(plano.get("artifacts_dir")):
        result["artifacts_dir"] = os.path.abspath(plano["artifacts_dir"])

    if plano.get("operation_id") != EXPECTED_OPERATION_ID:
        problems.append("operation_id do plano e %r, esperado %r"
                        % (plano.get("operation_id"), EXPECTED_OPERATION_ID))
        return finish(STATUS_PRECONDITION_FAILED)
    if plano.get("phase") != EXPECTED_PHASE:
        problems.append("phase do plano e %r, esperado %r"
                        % (plano.get("phase"), EXPECTED_PHASE))
        return finish(STATUS_PRECONDITION_FAILED)

    operacoes = tuple(op.get("kind") for op in (plano.get("operations") or [])
                      if isinstance(op, dict))
    if operacoes != EXPECTED_PLAN_OPERATIONS:
        problems.append("cadeia do plano e %r, esperada %r"
                        % (list(operacoes), list(EXPECTED_PLAN_OPERATIONS)))
        return finish(STATUS_PRECONDITION_FAILED)

    fase = getattr(safety, "CONTROLLED_WRITE_PHASE", None)
    result["phase_observed"] = fase
    if fase != EXPECTED_PHASE:
        problems.append("fase ativa e %r, esperada %r" % (fase, EXPECTED_PHASE))
        return finish(STATUS_PRECONDITION_FAILED)

    hospedeira = plano.get("call_host")
    if hospedeira not in PROFILE_POU_NAMES:
        problems.append("call_host %r nao e POU de perfil. Aceitos: %s"
                        % (hospedeira, ", ".join(PROFILE_POU_NAMES)))
        return finish(STATUS_PRECONDITION_FAILED)
    result["call_host_name"] = hospedeira

    programa = plano.get("program_name")
    if not is_text(programa):
        problems.append("program_name ausente no plano")
        return finish(STATUS_PRECONDITION_FAILED)
    result["program_name"] = programa

    caminho_saida = ((plano.get("output_project") or {}).get("path"))
    if not is_text(caminho_saida):
        problems.append("output_project.path ausente no plano")
        return finish(STATUS_PRECONDITION_FAILED)
    result["output_project_path"] = caminho_saida
    if os.path.exists(caminho_saida):
        problems.append("a saida ja existe: %r. Este probe nunca sobrescreve."
                        % (caminho_saida,))
        return finish(STATUS_PRECONDITION_FAILED)

    # O texto que o PREFLIGHT leu, entregue pelo host. Sem ele nao ha como
    # provar que a leitura na qual a montagem se apoia continua valendo.
    caminho_original = probe_cli.find_arg(argv, "original-implementation")
    sha_original = probe_cli.find_arg(argv, "original-implementation-sha256")
    if not is_text(caminho_original) or not is_text(sha_original):
        problems.append("--original-implementation e "
                        "--original-implementation-sha256 sao obrigatorios")
        return finish(STATUS_PRECONDITION_FAILED)
    try:
        handle = open(caminho_original, "rb")
        try:
            texto_do_preflight = handle.read().decode("utf-8")
        finally:
            handle.close()
    except Exception as exc:                                       # noqa: BLE001
        problems.append("texto do preflight ilegivel: %r" % (exc,))
        return finish(STATUS_PRECONDITION_FAILED)
    if sha256_of_text(texto_do_preflight) != sha_original:
        problems.append("o texto entregue nao confere com o sha256 declarado")
        return finish(STATUS_PRECONDITION_FAILED)

    projeto, erro_projeto = project_access.get_primary_project(script_globals)
    if projeto is None:
        problems.append("projeto indisponivel: %s" % (erro_projeto,))
        return finish(STATUS_PRECONDITION_FAILED)
    try:
        result["opened_project"] = project_access.get_project_path(projeto)
    except Exception:                                              # noqa: BLE001
        result["opened_project"] = None

    no, node_id, erros = find_call_host(projeto, hospedeira)
    for erro in erros:
        result["gap_notes"].append(erro)
    if no is None:
        problems.append("POU de perfil %r nao resolvida" % (hospedeira,))
        return finish(STATUS_HOST_NOT_FOUND)
    result["call_host_node_id"] = node_id

    documento, texto_atual, erro_doc = read_implementation_document(no)
    if erro_doc or documento is None or texto_atual is None:
        problems.append("implementacao de %s ilegivel: %s"
                        % (hospedeira, erro_doc))
        return finish(STATUS_PRECONDITION_FAILED)

    # O TEXTO NO PROJETO MUDOU DESDE O PREFLIGHT? Escrever a partir de uma
    # leitura velha apagaria o que mudou no meio.
    if sha256_of_text(texto_atual) != sha_original:
        problems.append(
            "a implementacao de %s mudou entre o preflight e agora "
            "(%r no projeto, %r no preflight)"
            % (hospedeira, sha256_of_text(texto_atual), sha_original))
        return finish(STATUS_TEXT_DRIFTED)

    if already_calls(texto_atual, programa):
        problems.append("%s ja chama %s. Nada a fazer, e este probe nao "
                        "duplica chamada." % (hospedeira, programa))
        return finish(STATUS_CALL_ALREADY_PRESENT)

    texto_final = compose_implementation(texto_atual, programa)
    result["text"]["original"] = texto_atual
    result["text"]["original_sha256"] = sha256_of_text(texto_atual)
    result["text"]["final"] = texto_final
    result["text"]["final_sha256"] = sha256_of_text(texto_final)

    result["operations_authorized"] = sorted(
        getattr(safety, "PHASE_ALLOWED_OPERATIONS", {}).get(fase, []))

    # --- mutacao 1: replace --------------------------------------------------
    result["operations_requested"].append("replace")
    result["journal"].append({"event": "mutation_attempt",
                              "operation": "replace", "phase": fase,
                              "call_site": CALL_SITE_REPLACE,
                              "node_id": node_id,
                              "state_before": {
                                  "sha256": result["text"]["original_sha256"]}})
    try:
        replace_guarded(documento, texto_final, safety)
    except safety.SafetyError as exc:
        problems.append("autorizacao de replace recusada: %s" % (exc,))
        result["journal"].append({"event": "mutation_denied",
                                  "operation": "replace", "error": repr(exc)})
        return finish(STATUS_PRECONDITION_FAILED)
    except Exception as exc:                                       # noqa: BLE001
        problems.append("replace levantou: %r" % (exc,))
        result["journal"].append({"event": "mutation_failed",
                                  "operation": "replace", "error": repr(exc)})
        return finish(STATUS_REPLACE_FAILED)
    result["operations_executed"].append("replace")
    result["journal"].append({"event": "mutation_done", "operation": "replace"})

    # --- mutacao 2: save_as --------------------------------------------------
    result["operations_requested"].append("save_as")
    result["journal"].append({"event": "mutation_attempt",
                              "operation": "save_as", "phase": fase,
                              "call_site": CALL_SITE_SAVE_AS,
                              "output": caminho_saida})
    try:
        save_as_guarded(projeto, caminho_saida, safety)
    except safety.SafetyError as exc:
        problems.append("autorizacao de save_as recusada: %s" % (exc,))
        result["journal"].append({"event": "mutation_denied",
                                  "operation": "save_as", "error": repr(exc)})
        return finish(STATUS_PRECONDITION_FAILED)
    except Exception as exc:                                       # noqa: BLE001
        problems.append("save_as levantou: %r" % (exc,))
        result["journal"].append({"event": "mutation_failed",
                                  "operation": "save_as", "error": repr(exc)})
        return finish(STATUS_SAVE_FAILED)
    result["operations_executed"].append("save_as")

    hash_saida, erro_saida = sha256_of_file(caminho_saida)
    result["output_sha256"] = hash_saida
    result["journal"].append({"event": "mutation_done", "operation": "save_as",
                              "output_sha256": hash_saida})
    if erro_saida:
        problems.append("saida ilegivel apos save_as: %s" % erro_saida)
        return finish(STATUS_SAVE_FAILED)

    return finish(STATUS_SAVED_AS)


def build_completion(result):
    """Escrito por ULTIMO: e o sinal de conclusao."""
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "phase": result.get("phase_observed"),
        "opened_project": result.get("opened_project"),
        "output_project_path": result.get("output_project_path"),
        "output_sha256": result.get("output_sha256"),
        "call_host_name": result.get("call_host_name"),
        "call_host_node_id": result.get("call_host_node_id"),
        "program_name": result.get("program_name"),
        "original_sha256": (result.get("text") or {}).get("original_sha256"),
        "final_sha256": (result.get("text") or {}).get("final_sha256"),
        "operations_requested": result.get("operations_requested"),
        "operations_authorized": result.get("operations_authorized"),
        "operations_executed": result.get("operations_executed"),
        "no_other_mutator_requested":
            tuple(result.get("operations_requested") or ()) in
            ((), ("replace",), ("replace", "save_as")),
        "errors": result.get("problems"),
        "gap_notes": result.get("gap_notes"),
        "generated_at": result.get("finished_at"),
    }


def write_artifacts(result, file_io):
    destino = result.get("artifacts_dir")
    if not is_text(destino):
        return []
    escritos = []
    try:
        if not os.path.isdir(destino):
            os.makedirs(destino)
    except Exception:                                              # noqa: BLE001
        return escritos

    def grava(nome, conteudo):
        try:
            file_io.write_json(os.path.join(destino, nome), conteudo)
            escritos.append(nome)
        except Exception:                                          # noqa: BLE001
            pass

    grava("w3-manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "plan_path": result.get("plan_path"),
        "plan_sha256": result.get("plan_sha256"),
        "phase": result.get("phase_observed"),
        "journal": result.get("journal"),
    })
    grava("w3-authored-text.json", {"text": result.get("text")})
    grava("w3-completion.json", build_completion(result))
    return escritos


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 66)
    print("[INFO] probes/%s -- W3, chamada idiomatica" % SCRIPT_NAME)
    print("=" * 66)

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access, safety

    try:
        result = run_author(script_globals, list(sys.argv or []), safety,
                            project_access, file_io, probe_cli)
    except BaseException as exc:                                   # noqa: BLE001
        print("[FATAL] %r" % (exc,))
        try:
            traceback.print_exc()
        except Exception:                                          # noqa: BLE001
            pass
        return EXIT_BY_STATUS[STATUS_FATAL]

    try:
        write_artifacts(result, file_io)
    except Exception as exc:                                       # noqa: BLE001
        print("[ERROR] falha ao gravar artefatos: %r" % (exc,))

    print("[INFO] status=%s" % result.get("status"))
    for problema in result.get("problems") or []:
        print("[PROBLEM] %s" % problema)
    print("=" * 66)

    _encerrar_plataforma(script_globals)
    return result.get("exit_code")


def _encerrar_plataforma(script_globals):
    """`system.exit(0)` DEPOIS de os artefatos estarem no disco."""
    try:
        system = script_globals.get("system") if script_globals else None
    except Exception:                                              # noqa: BLE001
        system = None
    if system is None:
        print("[INFO] `system` indisponivel: feche a janela manualmente.")
        return
    try:
        print("[INFO] encerrando o MasterTool por system.exit(0)...")
        system.exit(0)
    except Exception as exc:                                       # noqa: BLE001
        print("[INFO] system.exit falhou (%r): feche a janela manualmente."
              % (exc,))


if "projects" in globals():
    sys.exit(main())

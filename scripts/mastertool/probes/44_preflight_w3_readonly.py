# -*- coding: utf-8 -*-
r"""44_preflight_w3_readonly.py -- W3, chamada IDIOMATICA: leitura das POUs de
perfil do projeto Altus. SOMENTE LEITURA.

Contrato: `docs/41`. Motivo: `docs/39` secao 1.

POR QUE ESTE MARCO EXISTE. W2 provou que da para vincular um PROGRAM a uma
task, e o build devolveu um AVISO DO FABRICANTE dizendo que o padrao e outro:

    "A tarefa MainTask deveria conter apenas a chamada do programa MainPrg.
     Chamadas adicionais de outros programas devem ser realizadas a partir das
     POUs correspondentes do Perfil de Projeto (StartPrg, UserPrg, ActivePrg e
     NonSkippedPrg)"

O aviso NOMEIA as POUs. A fabrica nao deveria gerar projetos que o fabricante
desaconselha, e "funciona" nao e o mesmo que "esta certo".

DOIS MODOS LITERAIS, conjunto fechado, no mesmo espirito dos probes 37 e 33:

    preflight  -- antes da mutacao. Acha as POUs de perfil, le os DOIS
                  documentos de cada uma, e registra o texto e o SHA-256 do
                  que ESTAVA la. Sem essa leitura a mutacao seria escrita as
                  cegas: `replace` substitui o documento INTEIRO, e escrever
                  sem ter lido apagaria o codigo do fabricante.
    postsave   -- depois do `save_as`. Reabre a SAIDA, confere o hash contra o
                  registrado, e exige que o texto final contenha a chamada E
                  preserve integralmente o texto inicial.

COMO AS POUs SAO ACHADAS. Por nome E por tipo, nunca por um so:

  - o NOME entra porque a convencao do fabricante e por nome -- o aviso cita
    `StartPrg`, `UserPrg`, `ActivePrg` e `NonSkippedPrg` textualmente, e um
    projeto que chamasse a POU de outra coisa nao seria do perfil;
  - o TYPE GUID entra porque nome sozinho nao distingue objeto algum: uma
    pasta chamada `UserPrg` casaria. So o par decide.

Uma POU do perfil que o template NAO tenha nao e erro deste probe: ela e
registrada como `absent`, com o motivo. `ActivePrg` e `NonSkippedPrg` nao
existem no `TemplateExemplo v1.project` -- o aviso cita o perfil COMPLETO da Altus, e o
template implementa parte dele.

NAO faz, por construcao: `replace`, `save`, `save_as`, `create_*`, `build`,
`remove`, `rename`, `import_*`. Nenhuma dessas cadeias aparece neste arquivo.

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

SCRIPT_NAME = "44_preflight_w3_readonly.py"
SCHEMA_VERSION = "1.0"

EXPECTED_OPERATION_ID = "w3-idiomatic-call"
EXPECTED_PHASE = "W3_IDIOMATIC_CALL"

# --- as POUs do perfil, LITERAIS, na ordem em que o aviso as cita ------------
#
# Lista FECHADA. Acrescentar nome aqui e decisao humana: um probe que aceitasse
# "a POU que o plano disser" nao verificaria perfil algum -- verificaria o que
# o plano quisesse.
PROFILE_POU_NAMES = ("StartPrg", "UserPrg", "ActivePrg", "NonSkippedPrg")

# A POU onde a fabrica deve pendurar a chamada. `UserPrg` e a POU de codigo de
# usuario do perfil; `StartPrg` roda na partida, e nao ciclicamente.
DEFAULT_CALL_HOST = "UserPrg"

# GUID de tipo do PROGRAM, medido na arvore do `TemplateExemplo v1.project` (probe 37,
# run-025: `MainPrg`, `SpecialVariablesPrg`, `StartPrg` e `UserPrg` todos com
# este type). Nome sem tipo nao distingue objeto algum.
POU_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
CONTAINER_TYPE_GUID = "639b491f-5557-464c-af91-1471bac9f549"

MODE_PREFLIGHT = "preflight"
MODE_POSTSAVE = "postsave"
ALL_MODES = (MODE_PREFLIGHT, MODE_POSTSAVE)

MAX_DEPTH = 8
MAX_TOTAL_NODES = 1024
MAX_CHILDREN_PER_NODE = 128
MAX_DOCUMENT_CHARACTERS = 200000

# --- vocabulario fechado -----------------------------------------------------
STATUS_PREFLIGHT_VERIFIED = "preflight_verified"
STATUS_POSTSAVE_VERIFIED = "postsave_verified"
STATUS_HOST_NOT_FOUND = "call_host_not_found"
STATUS_TEXT_READ_GAP = "text_read_gap"
STATUS_CALL_ABSENT = "call_absent"
STATUS_ORIGINAL_TEXT_LOST = "original_text_lost"
STATUS_PRECONDITION_FAILED = "precondition_failed"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_PREFLIGHT_VERIFIED, STATUS_POSTSAVE_VERIFIED,
    STATUS_HOST_NOT_FOUND, STATUS_TEXT_READ_GAP, STATUS_CALL_ABSENT,
    STATUS_ORIGINAL_TEXT_LOST, STATUS_PRECONDITION_FAILED, STATUS_FATAL,
)

SUCCESS_STATUSES = (STATUS_PREFLIGHT_VERIFIED, STATUS_POSTSAVE_VERIFIED)

EXIT_BY_STATUS = {
    STATUS_PREFLIGHT_VERIFIED: 0,
    STATUS_POSTSAVE_VERIFIED: 0,
    STATUS_PRECONDITION_FAILED: 2,
    STATUS_HOST_NOT_FOUND: 2,
    STATUS_CALL_ABSENT: 3,
    STATUS_ORIGINAL_TEXT_LOST: 3,
    STATUS_TEXT_READ_GAP: 4,
    STATUS_FATAL: 1,
}

ARTIFACT_NAMES = ("w3-preflight-manifest.json", "w3-profile-pous.json",
                  "w3-preflight-completion.json")

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
    """SHA-256 do texto em UTF-8, sem normalizar.

    Sem normalizacao de proposito: a normalizacao (CRLF/LF, espaco ao fim da
    linha, uma quebra final) e regra de COMPARACAO, e vive em quem compara. Um
    hash ja normalizado nao poderia responder "o arquivo mudou byte a byte?".
    """
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
# normalizacao e comparacao de texto -- regras congeladas em docs/31
# =============================================================================

def normalize(text):
    """CRLF equivale a LF; espaco ao fim de cada linha e ignorado; UMA quebra
    final e ignorada. As tres regras estao congeladas desde W1.3A."""
    if text is None:
        return None
    unificado = text.replace("\r\n", "\n").replace("\r", "\n")
    linhas = [linha.rstrip() for linha in unificado.split("\n")]
    while linhas and linhas[-1] == "":
        linhas.pop()
    return "\n".join(linhas)


def contains_call(text, program_name):
    """A chamada aparece no texto?

    Compara sobre o texto NORMALIZADO e exige a forma `NOME();` -- com os
    parenteses e o ponto e virgula. Procurar so pelo nome casaria com um
    comentario que o citasse, e um comentario nao chama nada.
    """
    if text is None or not is_text(program_name):
        return False
    return ("%s();" % program_name) in normalize(text)


def preserves(original, final):
    """O texto final PRESERVA o inicial?

    Toda linha nao vazia do original tem de continuar presente. Nao basta o
    final ser maior: `replace` substitui o documento inteiro, e a unica coisa
    que distingue "acrescentou" de "reescreveu por cima" e conferir o que
    estava la.
    """
    if original is None or final is None:
        return False
    finais = set(linha for linha in normalize(final).split("\n"))
    for linha in normalize(original).split("\n"):
        if linha != "" and linha not in finais:
            return False
    return True


# =============================================================================
# leitura da arvore -- a cadeia ja confirmada pelos probes 05-10
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
    """`obj.type`, LITERAL. `obj.type_guid` nao existe no proxy e devolveria
    None em silencio -- achado real de W1.1/W1.2."""
    try:
        return as_text(node.type)
    except Exception:                                              # noqa: BLE001
        return None


def read_document(node, indicator_name, document_name):
    """Le UM documento textual, com o indicador conferido ANTES.

    Devolve `{state, text, sha256, error}`. Nunca levanta. O indicador e
    consultado primeiro porque acessar `textual_*` num objeto que nao tem
    documento levanta -- e a excecao nao distingue "nao tem" de "falhou".
    """
    resultado = {"state": None, "text": None, "sha256": None, "error": None}
    try:
        if not hasattr(node, indicator_name):
            resultado["state"] = "indicator_unsupported"
            return resultado
        indicador = getattr(node, indicator_name)
    except Exception as exc:                                       # noqa: BLE001
        resultado["state"] = "indicator_failed"
        resultado["error"] = "%s: %r" % (indicator_name, exc)
        return resultado
    if not isinstance(indicador, bool):
        resultado["state"] = "indicator_not_boolean"
        return resultado
    if not indicador:
        resultado["state"] = "indicator_false"
        return resultado
    try:
        documento = getattr(node, document_name)
    except Exception as exc:                                       # noqa: BLE001
        resultado["state"] = "document_failed"
        resultado["error"] = "%s: %r" % (document_name, exc)
        return resultado
    if documento is None:
        resultado["state"] = "document_none"
        return resultado
    try:
        texto = as_text(documento.text)
    except Exception as exc:                                       # noqa: BLE001
        resultado["state"] = "text_failed"
        resultado["error"] = "%s.text: %r" % (document_name, exc)
        return resultado
    if texto is None:
        resultado["state"] = "text_none"
        return resultado
    if len(texto) > MAX_DOCUMENT_CHARACTERS:
        resultado["state"] = "text_too_large"
        resultado["error"] = "documento com %d caracteres" % (len(texto),)
        return resultado
    resultado["state"] = "read"
    resultado["text"] = texto
    resultado["sha256"] = sha256_of_text(texto)
    return resultado


def read_pou_entry(node, node_id):
    """Identidade e os DOIS documentos de uma POU."""
    return {
        "node_id": node_id,
        "name": read_name(node),
        "type_guid": read_type_guid(node),
        "declaration": read_document(node, "has_textual_declaration",
                                     "textual_declaration"),
        "implementation": read_document(node, "has_textual_implementation",
                                        "textual_implementation"),
    }


def find_profile_pous(project):
    """DFS iterativa procurando as POUs de perfil por NOME **e** TIPO.

    Devolve `(achadas, varredura)`. `achadas` mapeia nome -> entrada; nomes do
    perfil que nao aparecerem simplesmente nao entram, e quem classifica
    registra a ausencia com motivo.
    """
    varredura = {"visited": 0, "truncated": False, "errors": []}
    achadas = {}
    if project is None:
        varredura["errors"].append("projeto indisponivel")
        return achadas, varredura

    pilha = [(project, "root", 0)]
    visitados = 0
    while pilha:
        if visitados >= MAX_TOTAL_NODES:
            varredura["truncated"] = True
            break
        no_atual, node_id, profundidade = pilha.pop()
        visitados += 1

        nome = read_name(no_atual)
        if nome in PROFILE_POU_NAMES:
            tipo = read_type_guid(no_atual)
            if tipo == POU_TYPE_GUID:
                if nome not in achadas:
                    achadas[nome] = read_pou_entry(no_atual, node_id)
                else:
                    # DOIS objetos com o mesmo nome do perfil e o tipo certo.
                    # Nao e escolha deste probe qual vale: registrar e recusar
                    # e melhor que escolher e acertar por sorte.
                    varredura["errors"].append(
                        "nome de perfil duplicado: %s em %s e %s"
                        % (nome, achadas[nome]["node_id"], node_id))
            else:
                varredura["errors"].append(
                    "%s em %s tem type %r, e nao o de PROGRAM"
                    % (nome, node_id, tipo))

        if profundidade >= MAX_DEPTH:
            continue
        filhos, erro = read_children(no_atual)
        if erro:
            varredura["errors"].append("%s: %s" % (node_id, erro))
        indice = len(filhos) - 1
        while indice >= 0:
            pilha.append((filhos[indice], "%s/%d" % (node_id, indice),
                          profundidade + 1))
            indice -= 1

    varredura["visited"] = visitados
    return achadas, varredura


# =============================================================================
# classificacao
# =============================================================================

def profile_report(achadas):
    """Uma entrada por nome do perfil, presente ou nao.

    Ausencia e registrada como `absent`, e nao omitida: `ActivePrg` e
    `NonSkippedPrg` nao existem no `TemplateExemplo v1.project`, e omiti-las faria a lista
    parecer completa. O aviso do fabricante cita o perfil da Altus INTEIRO; o
    template implementa parte dele.
    """
    relatorio = []
    for nome in PROFILE_POU_NAMES:
        entrada = achadas.get(nome)
        if entrada is None:
            relatorio.append({"name": nome, "present": False,
                              "reason": "nao encontrada na arvore com o type "
                                        "de PROGRAM"})
        else:
            copia = dict(entrada)
            copia["present"] = True
            relatorio.append(copia)
    return relatorio


def classify_preflight(host_entry, varredura):
    if host_entry is None:
        return STATUS_HOST_NOT_FOUND
    implementacao = host_entry.get("implementation") or {}
    if implementacao.get("state") != "read":
        return STATUS_TEXT_READ_GAP
    if varredura.get("truncated"):
        return STATUS_PRECONDITION_FAILED
    return STATUS_PREFLIGHT_VERIFIED


def classify_postsave(host_entry, program_name, original_text):
    if host_entry is None:
        return STATUS_HOST_NOT_FOUND
    implementacao = host_entry.get("implementation") or {}
    if implementacao.get("state") != "read":
        return STATUS_TEXT_READ_GAP
    texto = implementacao.get("text")
    if not preserves(original_text, texto):
        return STATUS_ORIGINAL_TEXT_LOST
    if not contains_call(texto, program_name):
        return STATUS_CALL_ABSENT
    return STATUS_POSTSAVE_VERIFIED


def resolve_mode(argv, probe_cli, problems):
    bruto = probe_cli.find_arg(argv, "mode")
    if not is_text(bruto):
        problems.append("--mode e obrigatorio (%s)" % ("|".join(ALL_MODES),))
        return None
    if bruto not in ALL_MODES:
        problems.append("--mode invalido: %r (aceitos: %s)"
                        % (bruto, "|".join(ALL_MODES)))
        return None
    return bruto


# =============================================================================
# orquestracao
# =============================================================================

def run_probe(script_globals, argv, project_access, file_io, probe_cli,
              now=None):
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "mode": None,
        "plan_path": None,
        "plan_sha256": None,
        "artifacts_dir": None,
        "opened_project": None,
        "call_host_name": None,
        "program_name": None,
        "profile_pous": [],
        "scan": {},
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

    # O destino dos artefatos e fixado ANTES de qualquer validacao. Um relatorio
    # de erro que so funciona quando o plano esta certo nao relata justamente o
    # caso em que ele esta errado (achado de W2, docs/39).
    saida = probe_cli.find_arg(argv, "output")
    if is_text(saida):
        result["artifacts_dir"] = os.path.abspath(saida)

    modo = resolve_mode(argv, probe_cli, problems)
    result["mode"] = modo
    if modo is None:
        return finish(STATUS_PRECONDITION_FAILED)

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

    if plano.get("operation_id") != EXPECTED_OPERATION_ID:
        problems.append("operation_id do plano e %r, esperado %r"
                        % (plano.get("operation_id"), EXPECTED_OPERATION_ID))
        return finish(STATUS_PRECONDITION_FAILED)
    if plano.get("phase") != EXPECTED_PHASE:
        problems.append("phase do plano e %r, esperado %r"
                        % (plano.get("phase"), EXPECTED_PHASE))
        return finish(STATUS_PRECONDITION_FAILED)

    hospedeira = plano.get("call_host") or DEFAULT_CALL_HOST
    if hospedeira not in PROFILE_POU_NAMES:
        problems.append(
            "call_host %r nao e POU de perfil. Aceitos: %s"
            % (hospedeira, ", ".join(PROFILE_POU_NAMES)))
        return finish(STATUS_PRECONDITION_FAILED)
    result["call_host_name"] = hospedeira
    programa = plano.get("program_name")
    if not is_text(programa):
        problems.append("program_name ausente no plano")
        return finish(STATUS_PRECONDITION_FAILED)
    result["program_name"] = programa

    projeto, erro_projeto = project_access.get_primary_project(script_globals)
    if projeto is None:
        problems.append("projeto indisponivel: %s" % (erro_projeto,))
        return finish(STATUS_PRECONDITION_FAILED)
    try:
        result["opened_project"] = project_access.get_project_path(projeto)
    except Exception:                                              # noqa: BLE001
        result["opened_project"] = None

    achadas, varredura = find_profile_pous(projeto)
    result["scan"] = varredura
    result["profile_pous"] = profile_report(achadas)
    for erro in varredura.get("errors") or []:
        result["gap_notes"].append(erro)

    entrada = achadas.get(hospedeira)
    result["journal"].append({"event": "profile_scanned",
                              "found": sorted(achadas.keys()),
                              "call_host": hospedeira,
                              "visited": varredura.get("visited")})

    if modo == MODE_PREFLIGHT:
        return finish(classify_preflight(entrada, varredura))

    texto_original = probe_cli.find_arg(argv, "original-implementation-sha256")
    caminho_original = probe_cli.find_arg(argv, "original-implementation")
    original = None
    if is_text(caminho_original):
        try:
            handle = open(caminho_original, "rb")
            try:
                original = handle.read().decode("utf-8")
            finally:
                handle.close()
        except Exception as exc:                                   # noqa: BLE001
            problems.append("texto original ilegivel: %r" % (exc,))
            return finish(STATUS_PRECONDITION_FAILED)
    if original is None:
        problems.append("--original-implementation e obrigatorio no postsave: "
                        "sem o texto inicial nao da para provar que ele foi "
                        "preservado")
        return finish(STATUS_PRECONDITION_FAILED)
    if is_text(texto_original) and sha256_of_text(original) != texto_original:
        problems.append("o texto original entregue nao confere com o sha256 "
                        "registrado no preflight")
        return finish(STATUS_PRECONDITION_FAILED)

    return finish(classify_postsave(entrada, programa, original))


def build_completion(result):
    """Escrito por ULTIMO: e o sinal de conclusao."""
    hospedeira = None
    for entrada in result.get("profile_pous") or []:
        if entrada.get("name") == result.get("call_host_name"):
            hospedeira = entrada
            break
    implementacao = (hospedeira or {}).get("implementation") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "mode": result.get("mode"),
        "opened_project": result.get("opened_project"),
        "call_host_name": result.get("call_host_name"),
        "call_host_node_id": (hospedeira or {}).get("node_id"),
        "program_name": result.get("program_name"),
        "implementation_state": implementacao.get("state"),
        "implementation_sha256": implementacao.get("sha256"),
        "profile_pous_present": [e.get("name") for e in
                                 (result.get("profile_pous") or [])
                                 if e.get("present")],
        "profile_pous_absent": [e.get("name") for e in
                                (result.get("profile_pous") or [])
                                if not e.get("present")],
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

    grava("w3-preflight-manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "mode": result.get("mode"),
        "plan_path": result.get("plan_path"),
        "plan_sha256": result.get("plan_sha256"),
        "opened_project": result.get("opened_project"),
        "scan": result.get("scan"),
        "journal": result.get("journal"),
    })
    grava("w3-profile-pous.json", {"profile_pous": result.get("profile_pous")})
    # Por ULTIMO, sempre: a presenca deste arquivo e o sinal de que a sessao
    # chegou ao fim.
    grava("w3-preflight-completion.json", build_completion(result))
    return escritos


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 66)
    print("[INFO] probes/%s -- W3, SOMENTE LEITURA" % SCRIPT_NAME)
    print("[INFO] POUs de perfil: %s" % (", ".join(PROFILE_POU_NAMES),))
    print("=" * 66)

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access, safety

    if not safety.READ_ONLY_PHASE:
        print("[FATAL] READ_ONLY_PHASE desligado.")
        return EXIT_BY_STATUS[STATUS_FATAL]

    try:
        result = run_probe(script_globals, list(sys.argv or []),
                           project_access, file_io, probe_cli)
    except Exception as exc:                                       # noqa: BLE001
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

    # ENCERRA O MASTERTOOL, e so DEPOIS de os artefatos estarem no disco --
    # mesma razao do probe 42: `CloseMainWindow()` cai no dialogo modal de
    # salvar e a janela nao fecha sozinha.
    _encerrar_plataforma(script_globals)
    return result.get("exit_code")


def _encerrar_plataforma(script_globals):
    """Chama `system.exit(0)` se o global existir. Nunca levanta.

    O codigo de saida ja foi decidido e gravado no artefato; este encerramento
    e sobre a JANELA, e nao sobre o veredito.
    """
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

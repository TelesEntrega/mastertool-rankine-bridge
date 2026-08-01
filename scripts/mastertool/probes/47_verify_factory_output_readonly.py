# -*- coding: utf-8 -*-
r"""47_verify_factory_output_readonly.py -- o passo `verify` da fabrica.
SOMENTE LEITURA.

Contrato: `docs/42`. Ele fecha uma lacuna que o proprio executor nomeava: o
plano declara `reopen` e `verify`, o `probes/46` os registra como `delegated`
-- e ninguem os executava. "Delegado" sem destinatario e so um jeito educado de
dizer "nao feito".

O QUE ELE RESPONDE, e que o executor NAO pode responder: o executor sabe o que
escreveu, e nao o que ficou no arquivo. Ele afirma sobre a memoria da sessao que
mutou. Este probe reabre a SAIDA numa sessao NOVA e le do disco -- e e essa
diferenca que separa "existiu na sessao" de "foi persistido" (docs/32 secao 3).

TRES CAMADAS, e a terceira e a que torna o resultado comparavel entre execucoes:

  1. cada objeto declarado na spec existe, com o TIPO certo
  2. o texto lido de volta tem o HASH que o plano autorizou
  3. a arvore inteira, achatada, com posicao e tipo de cada no

A terceira existe para alimentar `automation.generation_equivalence`: duas
execucoes da mesma spec produzem `.project` de bytes diferentes -- ha GUID e
timestamp -- e a unica forma de perguntar "e o mesmo projeto?" e comparar
conteudo, nunca arquivo.

NAO faz, por construcao: `create_*`, `replace`, `save`, `save_as`, `build`,
`add`, `remove`, `rename`, `import_*`. Nenhuma dessas cadeias aparece aqui.

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

SCRIPT_NAME = "47_verify_factory_output_readonly.py"
SCHEMA_VERSION = "1.0"

EXPECTED_PLAN_KIND = "authoring_plan"

# GUIDs de tipo medidos na arvore do TemplateExemplo v1 (probe 37, run-025). POU cobre
# PROGRAM, FUNCTION_BLOCK e FUNCTION -- o `type_guid` NAO distingue os tres
# (docs/35 secao 4), e por isso a verificacao de familia por tipo so consegue
# afirmar "e uma POU", nunca "e um FUNCTION_BLOCK". A distincao fica como
# limite declarado, e nao como afirmacao.
POU_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
GVL_TYPE_GUID = "ffbfa93a-b94d-45fc-a329-229860183b1d"
# MEDIDO na run-032 (docs/46), por busca so-por-nome sobre a saida da fabrica.
# O MESMO valor para `ST_EIXO` (STRUCT) e `EN_ESTADO` (ENUM) -- o `type_guid`
# nao distingue subtipo de DUT, exatamente como docs/35 secao 4 previa para as
# familias de POU.
DUT_TYPE_GUID = "2db5746d-d284-4425-9f7f-2663a34b0ebc"

FAMILY_TYPE_GUID = {
    "gvls": GVL_TYPE_GUID,
    "programs": POU_TYPE_GUID,
    "function_blocks": POU_TYPE_GUID,
    "functions": POU_TYPE_GUID,
    "duts": DUT_TYPE_GUID,
}

# Qual documento cada campo de texto da spec nomeia. Literal.
FIELD_TO_DOCUMENT = {
    "declaration": ("has_textual_declaration", "textual_declaration"),
    "implementation": ("has_textual_implementation", "textual_implementation"),
}

MAX_DEPTH = 10
MAX_TOTAL_NODES = 2048
MAX_CHILDREN_PER_NODE = 256
MAX_DOCUMENT_CHARACTERS = 400000

STATUS_VERIFIED = "factory_output_verified"
STATUS_OBJECT_MISSING = "object_missing"
STATUS_TYPE_MISMATCH = "type_mismatch"
STATUS_TEXT_MISMATCH = "text_mismatch"
STATUS_TEXT_UNREADABLE = "text_unreadable"
# Objeto de familia sem `type_guid` catalogado. NAO e sucesso: "nao consegui
# verificar" nunca pode sair como "verificado".
STATUS_FAMILY_NOT_VERIFIABLE = "family_not_verifiable"
STATUS_PRECONDITION_FAILED = "precondition_failed"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_VERIFIED, STATUS_OBJECT_MISSING, STATUS_TYPE_MISMATCH,
    STATUS_TEXT_MISMATCH, STATUS_TEXT_UNREADABLE,
    STATUS_FAMILY_NOT_VERIFIABLE, STATUS_PRECONDITION_FAILED, STATUS_FATAL,
)

SUCCESS_STATUSES = (STATUS_VERIFIED,)

EXIT_BY_STATUS = {
    STATUS_VERIFIED: 0,
    STATUS_PRECONDITION_FAILED: 2,
    STATUS_OBJECT_MISSING: 3,
    STATUS_TYPE_MISMATCH: 3,
    STATUS_TEXT_MISMATCH: 3,
    STATUS_TEXT_UNREADABLE: 4,
    STATUS_FAMILY_NOT_VERIFIABLE: 4,
    STATUS_FATAL: 1,
}

ARTIFACT_NAMES = ("factory-verify-flat-nodes.json",
                  "factory-verify-texts.json",
                  "factory-verify-completion.json")

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


def read_json(path):
    try:
        handle = open(path, "rb")
        try:
            return json.loads(handle.read().decode("utf-8")), None
        finally:
            handle.close()
    except Exception as exc:                                       # noqa: BLE001
        return None, "%r" % (exc,)


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
    """`obj.type`, LITERAL -- `obj.type_guid` nao existe no proxy."""
    try:
        return as_text(node.type)
    except Exception:                                              # noqa: BLE001
        return None


def read_object_guid(node):
    try:
        return as_text(node.guid)
    except Exception:                                              # noqa: BLE001
        return None


def flatten_tree(project):
    """Achata a arvore inteira. DFS iterativa, ordem estavel por indice.

    Os campos sao os MESMOS que `automation.generation_equivalence` compara --
    `node_id`, `parent_node_id`, `depth`, `index`, `name`, `type_guid`,
    `child_count` -- mais `object_guid`, que ele EXCLUI da assinatura de
    proposito (e sorteado a cada criacao) e usa como contraprova de que as duas
    execucoes sao independentes.
    """
    nos = []
    varredura = {"visited": 0, "truncated": False, "errors": []}
    if project is None:
        varredura["errors"].append("projeto indisponivel")
        return nos, varredura

    pilha = [(project, "root", None, 0, None)]
    while pilha:
        if len(nos) >= MAX_TOTAL_NODES:
            varredura["truncated"] = True
            break
        atual, node_id, parent_id, profundidade, indice = pilha.pop()
        filhos, erro = read_children(atual)
        if erro:
            varredura["errors"].append("%s: %s" % (node_id, erro))
        nos.append({
            "node_id": node_id,
            "parent_node_id": parent_id,
            "depth": profundidade,
            "index": indice,
            "name": read_name(atual),
            "type_guid": read_type_guid(atual),
            "object_guid": read_object_guid(atual),
            "child_count": len(filhos),
        })
        if profundidade >= MAX_DEPTH:
            continue
        posicao = len(filhos) - 1
        while posicao >= 0:
            pilha.append((filhos[posicao], "%s/%d" % (node_id, posicao),
                          node_id, profundidade + 1, posicao))
            posicao -= 1

    varredura["visited"] = len(nos)
    return nos, varredura


def find_by_name_and_type(project, nome, type_guid):
    """Casa NOME **e** TIPO. Duplicata NAO e desempatada."""
    achado = None
    pilha = [project]
    visitados = 0
    while pilha:
        if visitados >= MAX_TOTAL_NODES:
            return None, "varredura truncada"
        atual = pilha.pop()
        visitados += 1
        if read_name(atual) == nome:
            tipo = read_type_guid(atual)
            if tipo == type_guid:
                if achado is not None:
                    return None, "mais de um %r com o mesmo tipo" % (nome,)
                achado = atual
        filhos, _erro = read_children(atual)
        for filho in filhos:
            pilha.append(filho)
    if achado is None:
        return None, "nao encontrado com o tipo esperado"
    return achado, None


def find_by_name_only(project, nome):
    """Busca SO por nome. Usada apenas para MEDIR o `type_guid` de familia nao
    catalogada -- nunca para verificar.

    Achar por nome nao distingue objeto algum, e e por isso que o resultado
    dela alimenta uma nota de medicao, e nao um veredito.
    """
    achado = None
    pilha = [project]
    visitados = 0
    while pilha:
        if visitados >= MAX_TOTAL_NODES:
            return None, "varredura truncada"
        atual = pilha.pop()
        visitados += 1
        if read_name(atual) == nome:
            if achado is not None:
                return None, "mais de um objeto chamado %r" % (nome,)
            achado = atual
        filhos, _erro = read_children(atual)
        for filho in filhos:
            pilha.append(filho)
    if achado is None:
        return None, "nenhum objeto chamado %r" % (nome,)
    return achado, None


def read_document_text(node, indicator_name, document_name):
    """`(texto, erro)`. Indicador conferido ANTES."""
    try:
        if not hasattr(node, indicator_name):
            return None, "objeto nao expoe %s" % (indicator_name,)
        if not getattr(node, indicator_name):
            return None, "%s e falso" % (indicator_name,)
        documento = getattr(node, document_name)
    except Exception as exc:                                       # noqa: BLE001
        return None, "acesso a %s falhou: %r" % (document_name, exc)
    if documento is None:
        return None, "%s devolveu None" % (document_name,)
    try:
        texto = as_text(documento.text)
    except Exception as exc:                                       # noqa: BLE001
        return None, "%s.text falhou: %r" % (document_name, exc)
    if texto is not None and len(texto) > MAX_DOCUMENT_CHARACTERS:
        return None, "documento com %d caracteres" % (len(texto),)
    return texto, None


# =============================================================================
# o que o plano autorizou, por objeto
# =============================================================================

def expected_texts(plano):
    """`{(familia, nome, campo): sha256}` a partir de `text_hashes` do plano.

    A fonte e o PLANO, e nao a spec: o plano e o que passou pela validacao e
    tem hash proprio. Conferir contra a spec de novo mediria a spec contra ela
    mesma.
    """
    esperado = {}
    for chave, valor in (plano.get("text_hashes") or {}).items():
        partes = chave.split(":")
        if len(partes) != 3:
            continue
        if not isinstance(valor, dict):
            continue
        esperado[(partes[0], partes[1], partes[2])] = valor.get("raw_sha256")
    return esperado


def classify(objetos):
    """Status a partir das entradas verificadas. Ordem de severidade: objeto
    ausente antes de tipo, tipo antes de texto.

    `unknown_family` BLOQUEIA. A primeira versao o tratava como nota e devolvia
    `factory_output_verified` -- e a run-032 saiu com "1 de 3 verificados" e o
    veredito verde. Um objeto que ninguem conseguiu verificar nao pode sair como
    verificado; e o mesmo modo de falha que este projeto persegue desde o
    `no_build_messages`, escrito por mim no mesmo dia em que o documentei.
    """
    if any(o["outcome"] == "unknown_family" for o in objetos):
        return STATUS_FAMILY_NOT_VERIFIABLE
    if any(o["outcome"] == "missing" for o in objetos):
        return STATUS_OBJECT_MISSING
    if any(o["outcome"] == "type_mismatch" for o in objetos):
        return STATUS_TYPE_MISMATCH
    if any(o["outcome"] == "unreadable" for o in objetos):
        return STATUS_TEXT_UNREADABLE
    if any(o["outcome"] == "text_mismatch" for o in objetos):
        return STATUS_TEXT_MISMATCH
    return STATUS_VERIFIED


def run_verify(script_globals, argv, project_access, file_io, probe_cli,
               now=None):
    if now is None:
        now = file_io.iso_now

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "plan_path": None,
        "plan_sha256": None,
        "artifacts_dir": None,
        "opened_project": None,
        "output_sha256_declared": None,
        "output_sha256_observed": None,
        "objects": [],
        "nodes": [],
        "scan": {},
        "problems": [],
        "gap_notes": [],
    }

    def finish(status):
        result["status"] = status
        result["finished_at"] = now()
        result["exit_code"] = EXIT_BY_STATUS.get(status, 1)
        result["is_success"] = status in SUCCESS_STATUSES
        return result

    problems = result["problems"]

    saida = probe_cli.find_arg(argv, "output")
    if is_text(saida):
        result["artifacts_dir"] = os.path.abspath(saida)

    caminho_plano = probe_cli.find_arg(argv, "plan")
    if not is_text(caminho_plano):
        problems.append("--plan e obrigatorio")
        return finish(STATUS_PRECONDITION_FAILED)
    result["plan_path"] = caminho_plano
    hash_plano, _e = sha256_of_file(caminho_plano)
    result["plan_sha256"] = hash_plano

    plano, erro = read_json(caminho_plano)
    if erro or not isinstance(plano, dict):
        problems.append("plano ilegivel: %s" % (erro,))
        return finish(STATUS_PRECONDITION_FAILED)
    if plano.get("kind") != EXPECTED_PLAN_KIND:
        problems.append("kind do plano e %r, esperado %r"
                        % (plano.get("kind"), EXPECTED_PLAN_KIND))
        return finish(STATUS_PRECONDITION_FAILED)

    projeto, erro_projeto = project_access.get_primary_project(script_globals)
    if projeto is None:
        problems.append("projeto indisponivel: %s" % (erro_projeto,))
        return finish(STATUS_PRECONDITION_FAILED)
    try:
        aberto = project_access.get_project_path(projeto)
    except Exception:                                              # noqa: BLE001
        aberto = None
    result["opened_project"] = aberto

    # O HASH DA SAIDA E CONFERIDO CONTRA O QUE O HOST DECLAROU. Sem isso, este
    # probe poderia estar lendo outro arquivo e afirmando sobre ele.
    declarado = probe_cli.find_arg(argv, "output-sha256")
    result["output_sha256_declared"] = declarado
    if is_text(aberto):
        observado, _e = sha256_of_file(aberto)
        result["output_sha256_observed"] = observado
        if is_text(declarado) and observado != declarado:
            problems.append(
                "o projeto aberto (%s) nao e o que o host declarou (%s)"
                % (observado, declarado))
            return finish(STATUS_PRECONDITION_FAILED)

    esperado = expected_texts(plano)
    if not esperado:
        problems.append("plano sem `text_hashes`: nao ha o que verificar")
        return finish(STATUS_PRECONDITION_FAILED)

    # --- camada 1 e 2: objeto por objeto ------------------------------------
    por_objeto = {}
    for (familia, nome, campo), sha in esperado.items():
        por_objeto.setdefault((familia, nome), []).append((campo, sha))

    for (familia, nome) in sorted(por_objeto):
        entrada = {"family": familia, "name": nome, "outcome": "verified",
                   "node_id": None, "type_guid": None, "texts": []}
        tipo_esperado = FAMILY_TYPE_GUID.get(familia)
        if tipo_esperado is None:
            # Sem `type_guid` catalogado a verificacao nao acontece -- mas o
            # tipo OBSERVADO e medido e registrado, por nome, para que a lacuna
            # possa ser FECHADA depois. Medir nao e verificar, e o `outcome`
            # continua bloqueando o veredito.
            entrada["outcome"] = "unknown_family"
            observado, erro_busca = find_by_name_only(projeto, nome)
            entrada["type_guid_observed"] = (read_type_guid(observado)
                                             if observado is not None else None)
            result["gap_notes"].append(
                "familia %r nao tem type_guid catalogado; objeto %r NAO "
                "verificado. type_guid observado: %r (%s)"
                % (familia, nome, entrada["type_guid_observed"],
                   erro_busca or "achado por nome"))
            result["objects"].append(entrada)
            continue
        no, erro = find_by_name_and_type(projeto, nome, tipo_esperado)
        if no is None:
            entrada["outcome"] = "missing"
            entrada["error"] = erro
            result["objects"].append(entrada)
            continue
        entrada["type_guid"] = read_type_guid(no)
        for campo, sha_esperado in sorted(por_objeto[(familia, nome)]):
            indicador, documento = FIELD_TO_DOCUMENT.get(campo, (None, None))
            if indicador is None:
                entrada["texts"].append({"field": campo,
                                         "outcome": "unknown_field"})
                continue
            texto, erro_texto = read_document_text(no, indicador, documento)
            if erro_texto or texto is None:
                entrada["outcome"] = "unreadable"
                entrada["texts"].append({"field": campo,
                                         "outcome": "unreadable",
                                         "error": erro_texto})
                continue
            obtido = sha256_of_text(texto)
            igual = (obtido == sha_esperado)
            if not igual:
                entrada["outcome"] = "text_mismatch"
            entrada["texts"].append({
                "field": campo,
                "outcome": "match" if igual else "mismatch",
                "sha256_expected": sha_esperado,
                "sha256_observed": obtido,
            })
        result["objects"].append(entrada)

    # --- camada 3: a arvore inteira -----------------------------------------
    nos, varredura = flatten_tree(projeto)
    result["nodes"] = nos
    result["scan"] = varredura
    for erro in varredura.get("errors") or []:
        result["gap_notes"].append(erro)

    return finish(classify(result["objects"]))


def build_completion(result):
    """Escrito por ULTIMO: e o sinal de conclusao."""
    objetos = result.get("objects") or []
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "plan_sha256": result.get("plan_sha256"),
        "opened_project": result.get("opened_project"),
        "output_sha256_observed": result.get("output_sha256_observed"),
        "objects_verified": len([o for o in objetos
                                 if o.get("outcome") == "verified"]),
        "objects_total": len(objetos),
        "objects_by_outcome": sorted(set(o.get("outcome") for o in objetos)),
        "node_count": len(result.get("nodes") or []),
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

    grava("factory-verify-flat-nodes.json", {"nodes": result.get("nodes"),
                                             "scan": result.get("scan")})
    grava("factory-verify-texts.json", {"objects": result.get("objects")})
    grava("factory-verify-completion.json", build_completion(result))
    return escritos


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s -- verificacao da saida, SOMENTE LEITURA"
          % SCRIPT_NAME)
    print("=" * 68)

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access, safety

    if not safety.READ_ONLY_PHASE:
        print("[FATAL] READ_ONLY_PHASE desligado.")
        return EXIT_BY_STATUS[STATUS_FATAL]

    try:
        result = run_verify(script_globals, list(sys.argv or []),
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
    print("[INFO] objetos: %d de %d verificados; nos: %d"
          % (len([o for o in (result.get("objects") or [])
                  if o.get("outcome") == "verified"]),
             len(result.get("objects") or []),
             len(result.get("nodes") or [])))
    for problema in result.get("problems") or []:
        print("[PROBLEM] %s" % problema)
    print("=" * 68)

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

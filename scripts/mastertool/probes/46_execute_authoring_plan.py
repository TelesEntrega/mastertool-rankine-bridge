# -*- coding: utf-8 -*-
r"""46_execute_authoring_plan.py -- o EXECUTOR: roda um plano de autoria
produzido por `mastertool_bridge.planner` contra o MasterTool.

Contrato: `docs/42`. Plano: saida de `build_authoring_plan` (host, offline).

E o elo que faltava. Ate aqui cada marco tinha um probe proprio com nomes e
textos FIXOS no fonte -- `probes/38` cria exatamente uma GVL chamada
`GVL_AI_TESTE` e um PROGRAM chamado `PRG_AI_TESTE`, e nada mais. Isso provou as
operacoes; nao faz fabrica. Este arquivo executa o que o PLANO disser, dentro
de um vocabulario FECHADO.

DESPACHO LITERAL, e nao dinamico. A escolha da operacao e uma cadeia de
`if`/`elif` sobre constantes deste modulo:

    if operacao == OP_CREATE_GVL:
        ...
    elif operacao == OP_CREATE_PROGRAM:
        ...

Nao ha `eval`, `exec`, dicionario de funcoes nem nome de metodo do MasterTool
montado a partir de dados do plano. Uma operacao que o plano trouxesse e que
ninguem escreveu aqui NAO cai num ramo generico: ela reprova em
`unknown_operation`. O planner ja recusa emitir operacao fora do conjunto; esta
e a segunda porta, e as duas sao literais.

Sobre `getattr`, com precisao -- ele aparece QUATRO vezes e nenhuma escolhe
operacao: duas leem `has_textual_*`/`textual_*` com nome vindo de CONSTANTE
LITERAL passada pelo chamador (mesmo padrao do probe 44), e duas leem
`CONTROLLED_WRITE_PHASE` e `PHASE_ALLOWED_OPERATIONS` do modulo `safety`.
Nenhum recebe string derivada do plano ou da spec. Ha teste por AST exigindo
exatamente isso -- a alternativa seria escrever "nao ha getattr" e ficar
falso na primeira leitura de documento.

O TEXTO VEM DA SPEC, NUNCA DO PLANO -- e nem do fonte. Herdado de `probes/32` e
mantido pelo planner: um plano que carregasse o texto final autorizaria a si
mesmo a escrever qualquer coisa. O plano carrega o HASH
(`planned_after_sha256`); a spec carrega o texto; o executor le da spec, confere
contra o hash do passo e so entao escreve. Hash divergente e
`text_hash_mismatch`, antes de qualquer mutacao.

`probes/38` resolveu o mesmo problema fixando os textos no proprio fonte. Para
um marco de uma GVL e um PROGRAM aquilo bastava e era mais restrito. Para uma
fabrica nao serve: os textos sao do cliente. O par plano+spec amarrado por hash
substitui a constante no fonte sem afrouxar a regra.

O QUE ESTE ARQUIVO **NAO** EXECUTA, mesmo o plano trazendo:

    reopen, build, verify   -> etapas de VERIFICACAO, com fase e abertura
                               proprias (docs/32 §3, docs/38 §5). Compilar na
                               sessao que acabou de escrever provaria, no
                               maximo, que o texto EM MEMORIA compila.

Elas sao reconhecidas e REGISTRADAS como delegadas -- nunca ignoradas em
silencio, porque "o plano tinha 10 passos e eu executei 6" precisa aparecer no
artefato.

PROGRAM CALL E A FORMA IDIOMATICA. `create_program_call` NAO acrescenta o
PROGRAM a lista da task: ele escreve a chamada DENTRO de uma POU do Perfil de
Projeto. W2 (docs/39) mediu que `MainTask.pous.add(nome)` compila e que o
FABRICANTE avisa contra; W3 (docs/41) mediu a forma de dentro da `UserPrg` com
ZERO avisos. A API consumida e `replace`, e `add` nao aparece neste arquivo.

SEM ROLLBACK. `create_*` devolve o objeto JA inserido, e a API nao tem
transacao. Qualquer falha no meio invalida a COPIA INTEIRA -- a unidade
descartada e a copia, nunca uma operacao isolada. Este arquivo registra e para:
nunca chama `remove`, `rename` nem `save`.

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

SCRIPT_NAME = "46_execute_authoring_plan.py"
SCHEMA_VERSION = "1.0"

# Fases sob as quais este executor pode rodar. Conjunto LITERAL e FECHADO,
# pelo mesmo motivo de `ACCEPTED_BUILD_PHASES` no probe 40: acrescentar fase
# aqui e decisao humana no mesmo commit que a abre, e nao consequencia de um
# plano trazer um nome novo.
ACCEPTED_PHASES = ("W9_PROVE_TASK_TIMING", "W8_PROVE_TASK_WITH_POU",
                   "W4_EXECUTE_PLAN", "W5_PROVE_IEC_PACKAGE",
                   "W6_PROVE_DUT_AND_TASK", "W7_FACTORY_FULL")
EXPECTED_PLAN_KIND = "authoring_plan"
EXPECTED_PLAN_SCHEMA_VERSION = 1

# Espelha `GAP_OPERATION_NOT_FIELD_PROVEN` do planner. Duplicado porque os
# dois rodam em runtimes diferentes; teste confere que nao divergiram.
GAP_OPERATION_NOT_FIELD_PROVEN = "operation_not_field_proven"

# --- vocabulario de operacoes, LITERAL e FECHADO ----------------------------
#
# Espelha `PLAN_OPERATIONS` do planner. A duplicacao e deliberada: os dois
# arquivos rodam em PROCESSOS e RUNTIMES diferentes -- CPython 3 no host,
# IronPython 2.7 aqui --, e um import entre eles nao existe. O teste
# `test_probe_46_executor.py` confere que as duas listas nao divergiram.
OP_CREATE_DUT = "create_dut"
OP_CREATE_GVL = "create_gvl"
OP_CREATE_FUNCTION = "create_function"
OP_CREATE_FUNCTION_BLOCK = "create_function_block"
OP_CREATE_PROGRAM = "create_program"
OP_CREATE_TASK = "create_task"
OP_CREATE_PROGRAM_CALL = "create_program_call"
OP_BIND_PROGRAM_TO_TASK = "bind_program_to_task"
OP_CONFIGURE_TASK = "configure_task"
OP_REPLACE = "replace"
OP_SAVE_AS = "save_as"
OP_REOPEN = "reopen"
OP_BUILD = "build"
OP_VERIFY = "verify"

ALL_PLAN_OPERATIONS = (
    OP_CREATE_DUT, OP_CREATE_GVL, OP_CREATE_FUNCTION,
    OP_CREATE_FUNCTION_BLOCK, OP_CREATE_PROGRAM, OP_CREATE_TASK,
    OP_CREATE_PROGRAM_CALL, OP_BIND_PROGRAM_TO_TASK, OP_CONFIGURE_TASK,
    OP_REPLACE, OP_SAVE_AS, OP_REOPEN, OP_BUILD, OP_VERIFY,
)

# As que ESTE arquivo executa. Conjunto proprio, e menor que o vocabulario:
# uma operacao pode ser legitima no plano e nao ser deste executor.
EXECUTED_OPERATIONS = (
    OP_CREATE_GVL, OP_CREATE_PROGRAM, OP_CREATE_FUNCTION_BLOCK,
    OP_CREATE_FUNCTION, OP_CREATE_DUT, OP_CREATE_TASK, OP_REPLACE,
    OP_CREATE_PROGRAM_CALL, OP_BIND_PROGRAM_TO_TASK, OP_CONFIGURE_TASK,
    OP_SAVE_AS,
)

# IMPLEMENTADAS AQUI E AINDA NAO PROVADAS EM CAMPO.
#
# Existe um ovo-e-galinha real: o planner e fail-closed em `field_proven` e nao
# emite plano executavel com uma operacao nao provada -- e sem executar nao ha
# como prova-la. Marcar `field_proven: True` antes de medir seria DECLARAR em
# vez de MEDIR, que e exatamente o fail-open fechado em docs/42 secao 4.
#
# A saida nao e um bypass: e a FASE. Abrir uma fase cuja allowlist LITERAL
# contem `create_function_block` E a decisao humana de "esta execucao existe
# para exercer esta operacao". O executor aceita um plano bloqueado APENAS por
# `operation_not_field_proven`, e apenas quando TODA operacao nao provada esta
# nesta tupla E o verbo dela esta na allowlist da fase ativa. Lacuna de
# qualquer outro tipo continua reprovando.
#
# Esta tupla ENCOLHE: assim que a operacao for provada, ela sai daqui e o
# contrato do planner ganha `field_proven: True` com a run citada. Uma tupla
# que so crescesse seria a lista de tudo que o executor faz sem prova.
# VAZIA desde a run-028: `create_function_block` e `create_function` foram
# provadas (docs/43) e sairam daqui, ganhando `field_proven: True` no
# contrato do planner com a run citada. A tupla ENCOLHEU, que e a unica
# direcao aceitavel -- uma lista que so crescesse seria o inventario do que
# o executor faz sem prova, indefinidamente.
# `create_dut` saiu daqui na run-033 (docs/46), provado.
#
# `create_task` e `bind_program_to_task` sairam JUNTAS na run-036 (docs/48),
# como tinham de sair: uma task cheia e uma cadeia so. O aviso da run-032 --
# "No POU is defined for task" -- sumiu, e a saida reaberta foi medida com a
# task presente e `PRG_DIAG` na posicao 0 da lista dela.
#
# `configure_task` saiu na run-037 (docs/49), provada: as quatro escritas
# foram relidas do objeto e depois do projeto salvo e reaberto.
#
# VAZIA de novo, que e a unica direcao aceitavel para esta tupla.
PROVING_OPERATIONS = ()

# Delegadas a outra fase/abertura. Registradas, nunca ignoradas em silencio.
DELEGATED_OPERATIONS = (OP_REOPEN, OP_BUILD, OP_VERIFY)

# Qual verbo do MasterTool cada operacao EXECUTADA consome. Literal, e so para
# as que este arquivo executa.
#
# Existe porque a primeira versao comparava o `required_allowlist` do PLANO
# INTEIRO com a allowlist da fase -- e reprovou na run-027 com "faltam:
# ['build']". A recusa estava certa e a pergunta estava errada: o plano
# descreve a cadeia inteira, INCLUSIVE o build, e o build tem fase propria. Um
# executor tem de pedir autorizacao para o que ELE faz, nao para o que o plano
# descreve.
#
# Note que `create_program_call` consome `replace`: a chamada idiomatica e uma
# escrita de texto na POU de perfil, e nao uma operacao estrutural (docs/41).
OPERATION_TO_MASTERTOOL_VERB = {
    OP_CREATE_GVL: "create_gvl",
    OP_CREATE_PROGRAM: "create_program",
    OP_CREATE_FUNCTION_BLOCK: "create_function_block",
    OP_CREATE_FUNCTION: "create_function",
    OP_CREATE_DUT: "create_dut",
    OP_CREATE_TASK: "create_task",
    OP_REPLACE: "replace",
    OP_CREATE_PROGRAM_CALL: "replace",
    OP_BIND_PROGRAM_TO_TASK: "add",
    OP_SAVE_AS: "save_as",
}

# `configure_task` NAO entra no mapa acima, e a ausencia e o desenho.
#
# Aquele mapa responde "qual METODO esta operacao consome", e esta operacao nao
# consome metodo nenhum: ela ATRIBUI. O que ela precisa autorizado sai do
# proprio passo -- uma escrita por propriedade declarada --, com o prefixo que
# o registro do gate exige.
PROPERTY_WRITE_PREFIX = "set:"

# As QUATRO propriedades com ramo literal escrito. Nome de propriedade que nao
# esteja aqui reprova com nome proprio, em vez de virar `setattr` -- que nao
# existe neste arquivo, e ha teste afirmando isso.
CONFIGURABLE_TASK_PROPERTIES = ("kind_of_task", "interval", "interval_unit",
                                "priority")

# Reconhecidas pelo vocabulario e NAO implementadas aqui, porque nenhuma delas
# foi provada em cadeia (o planner ja marca `field_proven: False` e recusa
# emitir plano executavel com elas). O ramo existe para que a recusa tenha
# NOME, em vez de cair no `else` generico junto com lixo.
# VAZIA: o vocabulario inteiro tem ramo escrito. Ela existe para que uma
# operacao NOVA no planner reprove com nome proprio em vez de cair no `else`
# generico junto com lixo.
NOT_IMPLEMENTED_OPERATIONS = ()

# --- POU hospedeira da chamada idiomatica -----------------------------------
#
# Lista FECHADA, na ordem em que o aviso do fabricante as cita (docs/41). A
# escolha da hospedeira mora AQUI, e nao no plano, porque ela depende do que
# existe no template -- e o planner e offline, nao abre projeto nenhum.
#
# `UserPrg` e a POU de codigo de usuario do perfil; `StartPrg` roda na partida,
# e nao ciclicamente. Se a hospedeira nao existir, isto e `precondition_failed`
# -- nunca um fallback para outra POU, que mudaria a semantica do projeto sem
# ninguem pedir.
PROFILE_POU_NAMES = ("StartPrg", "UserPrg", "ActivePrg", "NonSkippedPrg")
PROGRAM_CALL_HOST = "UserPrg"
ORIGIN_COMMENT = "(* chamada acrescentada por mastertool-rankine-bridge *)"

# A TASK A QUE AS POUs DE PERFIL PERTENCEM.
#
# O caminho idiomatico (docs/41) escreve a chamada DENTRO de `UserPrg` -- e
# `UserPrg` roda pela cadeia da `MainTask`. Para uma task DIFERENTE, escrever
# ali ligaria o programa ao ciclo ERRADO, em silencio: a spec pediria
# "TaskNova chama PRG_X" e o projeto executaria PRG_X sob MainTask.
#
# Para a task que a spec CRIA o caminho e outro, e e `OP_BIND_PROGRAM_TO_TASK`:
# a lista de POUs da propria task. O aviso do fabricante que W2 mediu nomeia a
# `MainTask` -- ele fala da task DO PERFIL. Uma task nova nao e ela, o perfil
# nao diz nada sobre ela, e `UserPrg` seria justamente o caminho errado.
#
# O que continua sem caminho e a task PREEXISTENTE que nao e a do perfil: dela
# nao se sabe o que ja esta na lista. O planner marca lacuna, e aqui embaixo ha
# recusa com nome proprio -- as duas portas, como sempre.
PROFILE_TASK_NAME = "MainTask"

# `dut_kind` do plano -> membro do enum `DutType`. Mapa LITERAL nos dois lados.
#
# O enum e injetado no escopo do script (`script_globals["DutType"]`, medido na
# run-031, docs/45). O membro e lido por nome LITERAL deste mapa -- nunca por
# nome montado a partir do dado da spec, que deixaria a spec escolher qual
# membro do enum tocar.
DUT_KIND_TO_MEMBER = {
    "STRUCT": "Structure",
    "ENUM": "Enumeration",
}

POU_TYPE_GUID = "6f9dac99-8de1-4efc-8465-68ac443b7d08"
# GUID de tipo da GVL, medido na arvore do TemplateExemplo v1 (probe 37, run-025).
GVL_TYPE_GUID = "ffbfa93a-b94d-45fc-a329-229860183b1d"
EXPECTED_CONTAINER_NAME = "Application"
EXPECTED_CONTAINER_TYPE_GUID = "639b491f-5557-464c-af91-1471bac9f549"
CONTAINER_NODE_PATH = "root/1/0/0"

MAX_DEPTH = 8
MAX_TOTAL_NODES = 1024
MAX_CHILDREN_PER_NODE = 128
MAX_STEPS = 512
# Teto de leitura da lista de POUs de uma task. Nao e limite de projeto: e a
# faixa em que `len(pous)` ainda e um numero plausivel, e nao um objeto que
# respondeu qualquer coisa (mesmo teto do probe 43).
MAX_POUS_PER_TASK = 256

CALL_SITE = "probes/46_execute_authoring_plan.py"

# --- vocabulario de estados, FECHADO ----------------------------------------
STATUS_EXECUTED = "plan_executed"
STATUS_PRECONDITION_FAILED = "precondition_failed"
STATUS_PLAN_NOT_EXECUTABLE = "plan_not_executable"
STATUS_UNKNOWN_OPERATION = "unknown_operation"
STATUS_OPERATION_NOT_IMPLEMENTED = "operation_not_implemented"
STATUS_TEXT_HASH_MISMATCH = "text_hash_mismatch"
STATUS_TEXT_MISSING = "text_missing"
STATUS_TARGET_NOT_FOUND = "target_not_found"
STATUS_MUTATION_FAILED = "mutation_failed"
STATUS_SAVE_FAILED = "save_failed"
STATUS_FATAL = "fatal"

ALL_STATUSES = (
    STATUS_EXECUTED, STATUS_PRECONDITION_FAILED, STATUS_PLAN_NOT_EXECUTABLE,
    STATUS_UNKNOWN_OPERATION, STATUS_OPERATION_NOT_IMPLEMENTED,
    STATUS_TEXT_HASH_MISMATCH, STATUS_TEXT_MISSING, STATUS_TARGET_NOT_FOUND,
    STATUS_MUTATION_FAILED, STATUS_SAVE_FAILED, STATUS_FATAL,
)

SUCCESS_STATUSES = (STATUS_EXECUTED,)

EXIT_BY_STATUS = {
    STATUS_EXECUTED: 0,
    STATUS_PRECONDITION_FAILED: 2,
    STATUS_PLAN_NOT_EXECUTABLE: 2,
    STATUS_UNKNOWN_OPERATION: 2,
    STATUS_OPERATION_NOT_IMPLEMENTED: 2,
    STATUS_TEXT_HASH_MISMATCH: 2,
    STATUS_TEXT_MISSING: 2,
    STATUS_TARGET_NOT_FOUND: 3,
    STATUS_MUTATION_FAILED: 3,
    STATUS_SAVE_FAILED: 3,
    STATUS_FATAL: 1,
}

ARTIFACT_NAMES = ("execution-manifest.json", "execution-steps.json",
                  "execution-completion.json")

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
# texto: a spec e a fonte, o plano e o lacre
# =============================================================================

def normalize(text):
    """As tres regras congeladas desde W1.3A: CRLF equivale a LF, espaco ao fim
    de linha e ignorado, UMA quebra final e ignorada."""
    if text is None:
        return None
    unificado = text.replace("\r\n", "\n").replace("\r", "\n")
    linhas = [linha.rstrip() for linha in unificado.split("\n")]
    while linhas and linhas[-1] == "":
        linhas.pop()
    return "\n".join(linhas)


def text_from_spec(spec, source_location):
    """Le o texto que `source_location` aponta na spec.

    Formato: `familia:nome:campo` -- o mesmo que o planner grava em
    `text_hashes`. A navegacao e por igualdade de nome, sem `getattr` e sem
    montar atributo a partir de dado.

    Devolve `(texto, erro)`.
    """
    if not is_text(source_location):
        return None, "source_location vazio"
    partes = source_location.split(":")
    if len(partes) != 3:
        return None, "source_location %r nao tem a forma familia:nome:campo" % (
            source_location,)
    familia, nome, campo = partes
    entradas = spec.get(familia)
    if not isinstance(entradas, list):
        return None, "spec nao tem a familia %r" % (familia,)
    for entrada in entradas:
        if not isinstance(entrada, dict):
            continue
        if entrada.get("name") != nome:
            continue
        if campo not in entrada:
            return None, "%s:%s nao tem o campo %r" % (familia, nome, campo)
        return as_text(entrada.get(campo)), None
    return None, "%s nao tem objeto chamado %r" % (familia, nome)


def resolve_step_text(spec, step):
    """`(texto, erro_de_precondicao, status)`.

    O hash do passo e a AUTORIZACAO: o executor so pode escrever o texto cujo
    hash o plano fixou. Divergencia reprova ANTES de qualquer mutacao, e nao
    e tratada como texto "atualizado" -- plano e spec que discordam nao
    descrevem a mesma intencao.
    """
    texto, erro = text_from_spec(spec, step.get("source_location"))
    if erro:
        return None, erro, STATUS_TEXT_MISSING
    if texto is None:
        return None, "texto ausente em %r" % (step.get("source_location"),), \
            STATUS_TEXT_MISSING
    esperado = step.get("planned_after_sha256")
    if not is_text(esperado):
        return None, "passo sem planned_after_sha256", STATUS_TEXT_HASH_MISMATCH
    obtido = sha256_of_text(texto)
    if obtido != esperado:
        return None, ("hash do texto da spec (%s) diverge do que o plano "
                      "autorizou (%s) em %s"
                      % (obtido, esperado, step.get("source_location"))), \
            STATUS_TEXT_HASH_MISMATCH
    return texto, None, None


# =============================================================================
# arvore
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


def resolve_container(project):
    """Desce `CONTAINER_NODE_PATH` por indice e confere nome E tipo.

    Por indice, e nao por nome: o caminho e a rota medida do template, e
    procurar "o no chamado Application" acharia qualquer coisa que se chamasse
    assim. Nome e tipo entram DEPOIS, como conferencia.
    """
    if project is None:
        return None, "projeto indisponivel"
    indices = CONTAINER_NODE_PATH.split("/")[1:]
    atual = project
    for bruto in indices:
        try:
            indice = int(bruto)
        except ValueError:
            return None, "node_path invalido: %r" % (CONTAINER_NODE_PATH,)
        filhos, erro = read_children(atual)
        if erro:
            return None, erro
        if indice >= len(filhos):
            return None, "indice %d fora da arvore em %r" % (
                indice, CONTAINER_NODE_PATH)
        atual = filhos[indice]
    nome = read_name(atual)
    if nome != EXPECTED_CONTAINER_NAME:
        return None, "container em %s se chama %r, esperado %r" % (
            CONTAINER_NODE_PATH, nome, EXPECTED_CONTAINER_NAME)
    tipo = read_type_guid(atual)
    if tipo != EXPECTED_CONTAINER_TYPE_GUID:
        return None, "container tem type %r, esperado %r" % (
            tipo, EXPECTED_CONTAINER_TYPE_GUID)
    return atual, None


def find_by_name_and_type(project, nome, type_guid):
    """DFS bounded, casando NOME **e** TIPO. Duplicata nao e desempatada."""
    if project is None:
        return None, "projeto indisponivel"
    achado = None
    pilha = [(project, 0)]
    visitados = 0
    while pilha:
        if visitados >= MAX_TOTAL_NODES:
            return None, "varredura truncada em %d nos" % MAX_TOTAL_NODES
        atual, profundidade = pilha.pop()
        visitados += 1
        if read_name(atual) == nome and read_type_guid(atual) == type_guid:
            if achado is not None:
                return None, "mais de um objeto chamado %r com o mesmo tipo" % (
                    nome,)
            achado = atual
        if profundidade >= MAX_DEPTH:
            continue
        filhos, _erro = read_children(atual)
        indice = len(filhos) - 1
        while indice >= 0:
            pilha.append((filhos[indice], profundidade + 1))
            indice -= 1
    if achado is None:
        return None, "objeto %r do tipo esperado nao encontrado" % (nome,)
    return achado, None


def read_document(node, indicator_name, document_name):
    """`(documento, erro)`. O indicador e conferido ANTES: acessar `textual_*`
    num objeto sem documento levanta, e a excecao nao distingue "nao tem" de
    "falhou"."""
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
    return documento, None


def document_for_target_kind(node, target_kind):
    """Qual dos dois documentos o `target_kind` do passo nomeia.

    Cadeia de `if` sobre constantes, e nao tabela: o mapeamento e conhecimento
    de API, e a tabela esconderia o `else` que reprova.
    """
    if target_kind in ("gvl_declaration", "program_declaration",
                       "dut_declaration", "function_declaration",
                       "function_block_declaration"):
        return read_document(node, "has_textual_declaration",
                             "textual_declaration")
    if target_kind in ("program_implementation", "function_implementation",
                       "function_block_implementation"):
        return read_document(node, "has_textual_implementation",
                             "textual_implementation")
    return None, "target_kind %r nao nomeia documento conhecido" % (target_kind,)


def to_clr_guid(text):
    """(System.Guid, erro). Nunca levanta.

    ACHADO da run-005: `create_program` recusa texto com
    `TypeError: expected Nullable[Guid], got str`. A conversao acontece na
    PRECONDICAO, nunca entre a guarda e a chamada. `System.Guid` e tipo do .NET
    base, nao API do MasterTool: converter nao e inventar superficie.
    """
    try:
        from System import Guid
    except Exception as exc:                                       # noqa: BLE001
        return None, "System.Guid indisponivel: %r" % (exc,)
    try:
        return Guid(text), None
    except Exception as exc:                                       # noqa: BLE001
        return None, "texto nao converte para Guid: %r (%r)" % (text, exc)


def resolve_dut_type(script_globals, dut_kind):
    """`(membro_do_enum, erro)`. Nunca levanta.

    O enum vem do escopo do script; o NOME do membro vem do mapa literal deste
    modulo. Um `dut_kind` que o mapa nao conhece reprova -- e nao vira
    `Structure` por conveniencia, que criaria o objeto errado calado.
    """
    nome_membro = DUT_KIND_TO_MEMBER.get(dut_kind)
    if nome_membro is None:
        return None, ("dut_kind %r nao esta no mapa literal deste executor "
                      "(aceitos: %s)" % (dut_kind,
                                         ", ".join(sorted(DUT_KIND_TO_MEMBER))))
    if not isinstance(script_globals, dict):
        return None, "escopo do script indisponivel"
    enum = script_globals.get("DutType")
    if enum is None:
        return None, ("`DutType` ausente do escopo do script. Ele foi medido "
                      "como presente na run-031 (docs/45); ausente aqui, e "
                      "achado, e nao motivo para adivinhar o valor.")
    try:
        return getattr(enum, nome_membro), None
    except Exception as exc:                                       # noqa: BLE001
        return None, "DutType nao expoe %s: %r" % (nome_membro, exc)


def find_task_configuration(project):
    """Acha o no de configuracao de tasks pelo MARCADOR DE TIPO, nunca por
    nome. `is_task_configuration` e o mesmo discriminador que `probes/42`
    usou."""
    if project is None:
        return None, "projeto indisponivel"
    achado = None
    pilha = [(project, 0)]
    visitados = 0
    while pilha:
        if visitados >= MAX_TOTAL_NODES:
            return None, "varredura truncada"
        atual, profundidade = pilha.pop()
        visitados += 1
        try:
            marcado = bool(atual.is_task_configuration)
        except Exception:                                          # noqa: BLE001
            marcado = False
        if marcado:
            if achado is not None:
                return None, "mais de uma configuracao de tasks na arvore"
            achado = atual
        if profundidade >= MAX_DEPTH:
            continue
        filhos, _erro = read_children(atual)
        for filho in filhos:
            pilha.append((filho, profundidade + 1))
    if achado is None:
        return None, "nenhum no com `is_task_configuration` verdadeiro"
    return achado, None


def compose_call(original, program_name):
    """Texto final da POU hospedeira: original + comentario + chamada.

    PURA. Preserva o original INTEGRALMENTE -- `replace` substitui o documento
    inteiro, entao "acrescentar" e sempre "reescrever com o que ja estava mais
    o novo", e o que nao entrar aqui desaparece do projeto.
    """
    base = normalize(original) if original is not None else ""
    partes = []
    if base != "":
        partes.append(base)
    partes.append(ORIGIN_COMMENT)
    partes.append("%s();" % (program_name,))
    return "\n".join(partes) + "\n"


def already_calls(text, program_name):
    if text is None or not is_text(program_name):
        return False
    return ("%s();" % (program_name,)) in normalize(text)


# =============================================================================
# as CINCO chamadas mutaveis -- guarda na linha IMEDIATAMENTE anterior
# =============================================================================

def create_gvl_guarded(container, name, safety):
    safety.assert_controlled_write_allowed("create_gvl")
    created = container.create_gvl(name)
    return created


def create_program_guarded(container, name, language_guid, safety):
    """`language_guid` chega como System.Guid JA CONVERTIDO: nada e calculado
    depois da guarda."""
    safety.assert_controlled_write_allowed("create_program")
    created = container.create_program(name, language_guid)
    return created


def create_function_block_guarded(container, name, language_guid, safety):
    """Sem `base_type` nem `interfaces`: os dois sao opcionais catalogados
    (docs/27 secao 7), e passar valor decidiria de antemao algo que ninguem
    mediu. Mesma forma exercida por `probes/39` em W1.5."""
    safety.assert_controlled_write_allowed("create_function_block")
    created = container.create_function_block(name, language_guid)
    return created


def create_function_guarded(container, name, return_type, language_guid,
                            safety):
    """`return_type` e obrigatorio na assinatura catalogada e vem do PLANO --
    nunca escolhido aqui."""
    safety.assert_controlled_write_allowed("create_function")
    created = container.create_function(name, return_type, language_guid)
    return created


def create_dut_guarded(container, name, dut_type, safety):
    """`dut_type` chega como membro do enum JA RESOLVIDO (ver
    `resolve_dut_type`): nada e calculado depois da guarda.

    `baseType` e omitido -- obrigatorio so para `Alias`, e este executor nao
    emite `Alias`."""
    safety.assert_controlled_write_allowed("create_dut")
    created = container.create_dut(name, dut_type)
    return created


def create_task_guarded(task_configuration, name, safety):
    """`create_task(name)` vive em `ScriptTaskConfigObject`, e nao no container
    IEC -- receptor diferente de todas as outras criacoes deste arquivo."""
    safety.assert_controlled_write_allowed("create_task")
    created = task_configuration.create_task(name)
    return created


def resolve_kind_of_task(script_globals, nome):
    """Membro do enum `KindOfTask`, lido do escopo do script por nome LITERAL.

    Mesmo desenho de `resolve_dut_type`: o enum e injetado no escopo (medido na
    run-031, docs/45), e o membro e alcancado por um nome que ESTE arquivo
    escreve -- nunca montado a partir do dado da spec, que deixaria a spec
    escolher qual membro do enum tocar.
    """
    enum = script_globals.get("KindOfTask")
    if enum is None:
        return None, ("KindOfTask nao esta no escopo do script "
                      "(script_globals['KindOfTask'])")
    # Literal por literal. Um `getattr(enum, nome)` faria a spec escolher.
    if nome == "Cyclic":
        return enum.Cyclic, None
    if nome == "Freewheeling":
        return enum.Freewheeling, None
    return None, ("membro %r de KindOfTask sem ramo literal neste executor "
                  "(escritos: Cyclic, Freewheeling)" % (nome,))


def read_task_property(task, propriedade):
    """Le UMA propriedade da task, por ramo literal. `(valor, erro)`.

    Existe para a releitura: escrever e nao conferir seria aceitar que a
    atribuicao possa nao pegar. Atribuicao que falha em silencio e o modo de
    falha proprio desta classe de mutacao -- um metodo que nao funciona ao
    menos levanta.
    """
    try:
        if propriedade == "kind_of_task":
            return as_text(task.kind_of_task), None
        if propriedade == "interval":
            return as_text(task.interval), None
        if propriedade == "interval_unit":
            return as_text(task.interval_unit), None
        if propriedade == "priority":
            return as_text(task.priority), None
    except Exception as exc:                                       # noqa: BLE001
        return None, "leitura de %r falhou: %r" % (propriedade, exc)
    return None, "propriedade %r sem ramo literal de leitura" % (propriedade,)


def read_pou_names(pou_collection):
    """Nomes da lista de POUs de uma task, por `len` e indexador.

    NENHUMA chamada de metodo sobre a colecao -- ela herda de `list`, e um
    metodo qualquer poderia mutar. A entrada e a tupla `(name, comment)` que o
    stub documenta e que W2 mediu (docs/39).

    Devolve `(nomes, erro)`. Lista vazia e MEDIDA: e o estado da task recem
    criada, e distingui-lo de "nao consegui ler" e o ponto.
    """
    if pou_collection is None:
        return None, "task.pous devolveu None"
    try:
        total = len(pou_collection)
    except Exception as exc:                                       # noqa: BLE001
        return None, "len(pous) falhou: %r" % (exc,)
    if total is None or total < 0 or total > MAX_POUS_PER_TASK:
        return None, "len(pous) fora de faixa: %r" % (total,)
    nomes = []
    for indice in range(total):
        try:
            item = pou_collection[indice]
        except Exception as exc:                                   # noqa: BLE001
            return None, "pous[%d] falhou: %r" % (indice, exc)
        try:
            nomes.append(as_text(item[0]))
        except Exception as exc:                                   # noqa: BLE001
            return None, ("pous[%d] nao e a tupla (name, comment) que o stub "
                          "documenta: %r" % (indice, exc))
    return nomes, None


def add_program_call_guarded(pou_collection, program_name, safety):
    """A OUTRA forma de vincular: a lista de POUs da task que este plano criou.

    O receptor se chama `pou_collection` de proposito -- e por RECEPTOR que a
    verificacao estatica distingue este `.add` de um `.add` de `set` do Python,
    e a mesma escolha de nome que o probe 43 fez (docs/39). Entre a guarda e a
    chamada nao ha ramo, laco, wrapper nem log.

    O `comment` opcional do stub nao e passado: menos superficie mutavel.
    """
    safety.assert_controlled_write_allowed("add")
    pou_collection.add(program_name)
    return True


def set_kind_of_task_guarded(task, value, safety):
    """As QUATRO funcoes abaixo sao a classe de mutacao NOVA: atribuicao.

    Uma funcao por propriedade, e nao uma com o nome vindo do passo, pelo mesmo
    motivo de sempre: `setattr(task, passo["property"], valor)` deixaria o
    PLANO escolher que campo do produto tocar. Aqui o campo esta escrito no
    codigo, e o plano so decide SE aquela linha roda.

    A guarda e a linha imediatamente anterior, como nas chamadas -- mas ela e
    OUTRA funcao (`assert_controlled_property_write_allowed`), porque a
    verificacao estatica de atribuicao e outra: `Assign` com alvo `Attribute`,
    e nao `Call`.
    """
    safety.assert_controlled_property_write_allowed("set:kind_of_task")
    task.kind_of_task = value
    return True


def set_interval_guarded(task, value, safety):
    safety.assert_controlled_property_write_allowed("set:interval")
    task.interval = value
    return True


def set_interval_unit_guarded(task, value, safety):
    safety.assert_controlled_property_write_allowed("set:interval_unit")
    task.interval_unit = value
    return True


def set_priority_guarded(task, value, safety):
    safety.assert_controlled_property_write_allowed("set:priority")
    task.priority = value
    return True


def replace_guarded(document, final_text, safety):
    safety.assert_controlled_write_allowed("replace")
    document.replace(final_text)
    return True


def replace_call_host_guarded(document, final_text, safety):
    """A chamada idiomatica. Funcao SEPARADA de `replace_guarded` de proposito:
    as duas pedem o mesmo verbo, e sao passos diferentes do plano -- juntar
    faria o journal registrar `replace` sem dizer qual dos dois."""
    safety.assert_controlled_write_allowed("replace")
    document.replace(final_text)
    return True


def save_as_guarded(project, output_path, safety):
    """`save_as`, nunca `save`: `save` sobrescreveria a copia de trabalho e
    destruiria a testemunha do estado inicial."""
    safety.assert_controlled_write_allowed("save_as")
    project.save_as(output_path)
    return True


# =============================================================================
# orquestracao
# =============================================================================

class Journal(object):
    """Append-only. `mutation_attempt` antes do efeito, `mutation_done` depois.
    Uma excecao entre os dois deixa `attempt` sem `done` -- a assinatura de "a
    copia esta em estado desconhecido"."""

    def __init__(self):
        self.entries = []

    def record(self, entry):
        self.entries.append(entry)


def run_executor(script_globals, argv, safety, project_access, file_io,
                 probe_cli, now=None):
    if now is None:
        now = file_io.iso_now

    journal = Journal()
    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": STATUS_FATAL,
        "started_at": now(),
        "finished_at": None,
        "phase_expected": list(ACCEPTED_PHASES),
        "phase_observed": None,
        "plan_path": None,
        "plan_sha256": None,
        "spec_path": None,
        "spec_sha256": None,
        "artifacts_dir": None,
        "opened_project": None,
        "output_project_path": None,
        "output_sha256": None,
        "steps_total": 0,
        "steps_executed": 0,
        "steps_delegated": 0,
        "step_log": [],
        "created_objects": [],
        "operations_requested": [],
        "operations_authorized": [],
        "operations_required": [],
        "proving_operations": [],
        "problems": [],
        "gap_notes": [],
        "journal": journal.entries,
    }

    def finish(status):
        result["status"] = status
        result["finished_at"] = now()
        result["exit_code"] = EXIT_BY_STATUS.get(status, 1)
        result["is_success"] = status in SUCCESS_STATUSES
        return result

    problems = result["problems"]

    # Destino dos artefatos ANTES de qualquer validacao: um relatorio de erro
    # que depende de o plano estar certo nao relata o caso em que ele esta
    # errado (achado de W2, docs/39).
    saida_artefatos = probe_cli.find_arg(argv, "output")
    if is_text(saida_artefatos):
        result["artifacts_dir"] = os.path.abspath(saida_artefatos)

    caminho_plano = probe_cli.find_arg(argv, "plan")
    caminho_spec = probe_cli.find_arg(argv, "spec")
    caminho_saida = probe_cli.find_arg(argv, "output-project")
    for rotulo, valor in (("--plan", caminho_plano), ("--spec", caminho_spec),
                          ("--output-project", caminho_saida)):
        if not is_text(valor):
            problems.append("%s e obrigatorio" % (rotulo,))
    if problems:
        return finish(STATUS_PRECONDITION_FAILED)

    result["plan_path"] = caminho_plano
    result["spec_path"] = caminho_spec
    result["output_project_path"] = caminho_saida

    if os.path.exists(caminho_saida):
        problems.append("a saida ja existe: %r. Este probe nunca sobrescreve."
                        % (caminho_saida,))
        return finish(STATUS_PRECONDITION_FAILED)

    plano, erro = read_json(caminho_plano)
    if erro or not isinstance(plano, dict):
        problems.append("plano ilegivel: %s" % (erro,))
        return finish(STATUS_PRECONDITION_FAILED)
    spec, erro = read_json(caminho_spec)
    if erro or not isinstance(spec, dict):
        problems.append("spec ilegivel: %s" % (erro,))
        return finish(STATUS_PRECONDITION_FAILED)

    hash_plano, _e = sha256_of_file(caminho_plano)
    hash_spec, _e = sha256_of_file(caminho_spec)
    result["plan_sha256"] = hash_plano
    result["spec_sha256"] = hash_spec

    if plano.get("kind") != EXPECTED_PLAN_KIND:
        problems.append("kind do plano e %r, esperado %r"
                        % (plano.get("kind"), EXPECTED_PLAN_KIND))
        return finish(STATUS_PRECONDITION_FAILED)
    if plano.get("schema_version") != EXPECTED_PLAN_SCHEMA_VERSION:
        problems.append("schema_version do plano e %r, esperado %r"
                        % (plano.get("schema_version"),
                           EXPECTED_PLAN_SCHEMA_VERSION))
        return finish(STATUS_PRECONDITION_FAILED)

    fase = getattr(safety, "CONTROLLED_WRITE_PHASE", None)
    result["phase_observed"] = fase
    autorizadas = sorted(
        getattr(safety, "PHASE_ALLOWED_OPERATIONS", {}).get(fase, []))
    result["operations_authorized"] = autorizadas

    # FAIL-CLOSED: plano com lacuna de medicao descreve corretamente o que
    # fazer e admite que parte disso nunca foi provada. Executa-lo seria
    # inventar MasterTool no meio de uma cadeia de mutacoes.
    #
    # UMA EXCECAO, NOMEADA E ESTREITA -- a execucao de PROVA. Um plano bloqueado
    # APENAS por `operation_not_field_proven`, cujas operacoes nao provadas
    # estejam TODAS em `PROVING_OPERATIONS` e cujos verbos estejam TODOS na
    # allowlist LITERAL da fase ativa, e executavel.
    #
    # Isto NAO e um bypass, e a diferenca esta em quem decide: abrir uma fase
    # com `create_function_block` na allowlist e a decisao HUMANA, escrita a
    # mao em `safety.py`, de que aquela execucao existe para exercer aquela
    # operacao. Sem isso haveria um ovo-e-galinha real -- o planner nao emite
    # plano executavel com operacao nao provada, e sem executar nao ha prova --
    # e a saida errada seria marcar `field_proven` antes de medir, que e
    # exatamente o fail-open fechado em docs/42 secao 4.
    #
    # Lacuna de QUALQUER outro tipo (API nao catalogada, GUID de linguagem nao
    # medido) continua reprovando, e a fase nao a redime.
    if fase not in ACCEPTED_PHASES:
        problems.append("fase ativa e %r, esperada uma de %s"
                        % (fase, list(ACCEPTED_PHASES)))
        return finish(STATUS_PRECONDITION_FAILED)

    lacunas = plano.get("measurement_gaps") or []
    if plano.get("executable") is not True:
        tipos = sorted({str(g.get("kind")) for g in lacunas})
        nao_provadas = sorted({
            str(g.get("detail", "")).split("'")[1]
            for g in lacunas
            if g.get("kind") == GAP_OPERATION_NOT_FIELD_PROVEN
            and "'" in str(g.get("detail", ""))})
        so_falta_prova = tipos == [GAP_OPERATION_NOT_FIELD_PROVEN]
        todas_em_prova = bool(nao_provadas) and all(
            op in PROVING_OPERATIONS for op in nao_provadas)
        verbos = [OPERATION_TO_MASTERTOOL_VERB.get(op) for op in nao_provadas]
        fase_autoriza = all(v in autorizadas for v in verbos if v)
        if so_falta_prova and todas_em_prova and fase_autoriza:
            result["proving_operations"] = nao_provadas
            result["gap_notes"].append(
                "EXECUCAO DE PROVA: %s ainda nao foi provada em campo, e a "
                "fase %s a autoriza explicitamente. O resultado desta execucao "
                "e o que decide se ela pode ser marcada como provada."
                % (", ".join(nao_provadas), fase))
            journal.record({"event": "proving_run",
                            "operations": nao_provadas, "phase": fase})
        else:
            problems.append(
                "plano nao executavel. Lacunas: %s. Nao provadas: %s. Fase %s "
                "autoriza: %s"
                % (tipos or "(nenhuma declarada, e ainda assim "
                   "executable != true)", nao_provadas, fase, autorizadas))
            return finish(STATUS_PLAN_NOT_EXECUTABLE)

    # O plano amarra a spec: `spec_sha256` e calculado sobre o JSON CANONICO da
    # spec, pelo host. Aqui a conferencia possivel e a de identidade do par --
    # que o plano declare um `spec_sha256`, e que o host o tenha conferido.
    if not is_text(plano.get("spec_sha256")):
        problems.append("plano sem spec_sha256: o par plano+spec nao esta "
                        "amarrado, e o texto poderia vir de outra spec")
        return finish(STATUS_PRECONDITION_FAILED)

    passos = plano.get("steps")
    if not isinstance(passos, list) or not passos:
        problems.append("plano sem passos")
        return finish(STATUS_PRECONDITION_FAILED)
    if len(passos) > MAX_STEPS:
        problems.append("plano com %d passos, acima do limite de %d"
                        % (len(passos), MAX_STEPS))
        return finish(STATUS_PRECONDITION_FAILED)
    result["steps_total"] = len(passos)

    # TODA operacao do plano tem de ser conhecida ANTES de a primeira mutacao
    # acontecer. Descobrir no meio que o passo 7 e desconhecido deixaria a
    # copia com seis mutacoes e nenhuma forma de desfaze-las.
    for passo in passos:
        operacao = passo.get("operation") if isinstance(passo, dict) else None
        if operacao not in ALL_PLAN_OPERATIONS:
            problems.append("operacao desconhecida no passo %r: %r"
                            % (passo.get("sequence"), operacao))
            return finish(STATUS_UNKNOWN_OPERATION)
        if operacao in NOT_IMPLEMENTED_OPERATIONS:
            problems.append(
                "a operacao %r pertence ao vocabulario mas NAO esta "
                "implementada neste executor: ela nunca foi exercida contra o "
                "produto dentro de uma cadeia que persistiu e compilou"
                % (operacao,))
            return finish(STATUS_OPERATION_NOT_IMPLEMENTED)

    # A AUTORIZACAO E PEDIDA PARA O QUE ESTE EXECUTOR FAZ, e nao para o que o
    # plano descreve. O plano inclui `build`, que tem fase PROPRIA -- exigir a
    # allowlist do plano inteiro reprovaria toda execucao de autoria, que foi o
    # que aconteceu na run-027.
    #
    # A exigencia e DERIVADA dos passos, e conferida contra uma allowlist
    # LITERAL. A direcao importa: derivar o requisito e legitimo, derivar a
    # PERMISSAO seria a fase deixando de autorizar coisa alguma.
    exigidas = sorted({OPERATION_TO_MASTERTOOL_VERB[p.get("operation")]
                       for p in passos
                       if p.get("operation") in OPERATION_TO_MASTERTOOL_VERB})
    result["operations_required"] = exigidas
    faltando = [op for op in exigidas if op not in autorizadas]
    if faltando:
        problems.append(
            "os passos executaveis exigem %s, e a fase %s autoriza %s -- "
            "faltam: %s" % (exigidas, fase, autorizadas, faltando))
        return finish(STATUS_PRECONDITION_FAILED)

    # Todo texto e resolvido e conferido contra o hash ANTES da primeira
    # mutacao, pelo mesmo motivo.
    textos = {}
    for passo in passos:
        if passo.get("operation") != OP_REPLACE:
            continue
        texto, erro, status = resolve_step_text(spec, passo)
        if erro:
            problems.append("passo %r: %s" % (passo.get("sequence"), erro))
            return finish(status)
        textos[passo.get("sequence")] = texto

    projeto, erro_projeto = project_access.get_primary_project(script_globals)
    if projeto is None:
        problems.append("projeto indisponivel: %s" % (erro_projeto,))
        return finish(STATUS_PRECONDITION_FAILED)
    try:
        result["opened_project"] = project_access.get_project_path(projeto)
    except Exception:                                              # noqa: BLE001
        result["opened_project"] = None

    container, erro_container = resolve_container(projeto)
    if container is None:
        problems.append("container nao resolvido: %s" % (erro_container,))
        return finish(STATUS_PRECONDITION_FAILED)

    # GUIDs de linguagem convertidos na PRECONDICAO.
    guids = {}
    OPERACOES_COM_LINGUAGEM = (OP_CREATE_PROGRAM, OP_CREATE_FUNCTION_BLOCK,
                               OP_CREATE_FUNCTION)
    for passo in passos:
        if passo.get("operation") not in OPERACOES_COM_LINGUAGEM:
            continue
        bruto = passo.get("language_guid")
        if not is_text(bruto):
            problems.append("passo %r sem language_guid"
                            % (passo.get("sequence"),))
            return finish(STATUS_PRECONDITION_FAILED)
        convertido, erro = to_clr_guid(bruto)
        if erro:
            problems.append("passo %r: %s" % (passo.get("sequence"), erro))
            return finish(STATUS_PRECONDITION_FAILED)
        guids[passo.get("sequence")] = convertido

    for passo in passos:
        if passo.get("operation") != OP_CREATE_FUNCTION:
            continue
        if not is_text(passo.get("return_type")):
            problems.append(
                "passo %r cria FUNCTION sem `return_type`. O tipo de retorno e "
                "obrigatorio na assinatura catalogada e vem do plano -- este "
                "executor nao escolhe um." % (passo.get("sequence"),))
            return finish(STATUS_PRECONDITION_FAILED)

    # O MEMBRO DO ENUM E RESOLVIDO NA PRECONDICAO, nunca entre a guarda e a
    # chamada -- mesma regra do `System.Guid` em `create_program`.
    tipos_dut = {}
    for passo in passos:
        if passo.get("operation") != OP_CREATE_DUT:
            continue
        membro, erro = resolve_dut_type(script_globals, passo.get("dut_kind"))
        if erro:
            problems.append("passo %r: %s" % (passo.get("sequence"), erro))
            return finish(STATUS_PRECONDITION_FAILED)
        tipos_dut[passo.get("sequence")] = membro

    # O no de configuracao de tasks tambem: resolver no meio da cadeia deixaria
    # a copia com mutacoes e sem para onde ir.
    configuracao_de_tasks = None
    if any(p.get("operation") == OP_CREATE_TASK for p in passos):
        configuracao_de_tasks, erro = find_task_configuration(projeto)
        if configuracao_de_tasks is None:
            problems.append("configuracao de tasks nao resolvida: %s" % (erro,))
            return finish(STATUS_TARGET_NOT_FOUND)

    # A CHAMADA IDIOMATICA SO SERVE A TASK DO PERFIL. Escrever em `UserPrg` uma
    # chamada que a spec pediu para OUTRA task ligaria o programa ao ciclo
    # errado, em silencio.
    for passo in passos:
        if passo.get("operation") != OP_CREATE_PROGRAM_CALL:
            continue
        task = passo.get("task_name")
        if task != PROFILE_TASK_NAME:
            problems.append(
                "o passo %r pede chamada de %r sob a task %r pela forma "
                "idiomatica, que escreve dentro de %r -- e %r roda pela cadeia "
                "de %r. Para uma task que nao e a do perfil o caminho e %r, a "
                "lista de POUs da propria task."
                % (passo.get("sequence"), passo.get("program_name"), task,
                   PROGRAM_CALL_HOST, PROGRAM_CALL_HOST, PROFILE_TASK_NAME,
                   OP_BIND_PROGRAM_TO_TASK))
            return finish(STATUS_PRECONDITION_FAILED)

    # E O ESPELHO: a lista de POUs so serve a task que ESTE plano cria.
    #
    # Numa task preexistente ha uma lista cujo conteudo, ordem e comentarios
    # ninguem leu, e o `add` entraria no fim dela. Numa task criada aqui o
    # estado inicial e conhecido -- vazia -- e por isso o `add` e verificavel.
    # A task do perfil tambem nao entra: ela tem a forma idiomatica, e o
    # fabricante avisa contra esta.
    criadas_pelo_plano = set(
        p.get("target_name") for p in passos
        if p.get("operation") == OP_CREATE_TASK)
    for passo in passos:
        if passo.get("operation") not in (OP_BIND_PROGRAM_TO_TASK,
                                          OP_CONFIGURE_TASK):
            continue
        task = passo.get("task_name")
        if task not in criadas_pelo_plano:
            problems.append(
                "o passo %r vincula %r a task %r pela lista de POUs, e este "
                "plano nao cria essa task. Numa task preexistente o estado "
                "inicial da lista nao foi lido, e acrescentar no fim dela "
                "mudaria a ordem de execucao de um projeto que nao foi gerado "
                "aqui. Se a intencao era a task do perfil (%r), a operacao e "
                "%r."
                % (passo.get("sequence"), passo.get("program_name"), task,
                   PROFILE_TASK_NAME, OP_CREATE_PROGRAM_CALL))
            return finish(STATUS_PRECONDITION_FAILED)

    # Objeto criado nesta sessao, indexado pela sequencia do passo que o
    # criou. E como o plano liga `replace` ao `create_*` correspondente
    # (`created_by_sequence`), e evita uma busca na arvore que dependeria de
    # `type_guid` -- nao medido para DUT.
    objetos_por_sequencia = {}
    # Task criada nesta sessao, indexada pelo NOME. Uma task so entra aqui se
    # `create_task` devolveu objeto; o vinculo procura NESTE dicionario e em
    # lugar nenhum -- nao ha busca por nome na arvore que pudesse alcancar uma
    # task preexistente.
    tasks_por_nome = {}

    journal.record({"event": "preconditions_passed",
                    "steps": len(passos),
                    "phase": fase,
                    "authorized": autorizadas})

    # --- o laco de execucao: DESPACHO LITERAL -------------------------------
    for passo in passos:
        sequencia = passo.get("sequence")
        operacao = passo.get("operation")
        alvo = passo.get("target_name")

        if operacao in DELEGATED_OPERATIONS:
            result["steps_delegated"] += 1
            result["step_log"].append({
                "sequence": sequencia, "operation": operacao,
                "outcome": "delegated",
                "reason": ("etapa de verificacao, com fase e abertura proprias "
                           "(docs/32 secao 3)")})
            continue

        result["operations_requested"].append(operacao)
        journal.record({"event": "mutation_attempt", "operation": operacao,
                        "sequence": sequencia, "target": alvo,
                        "call_site": CALL_SITE})

        try:
            if operacao == OP_CREATE_GVL:
                criado = create_gvl_guarded(container, alvo, safety)
                objetos_por_sequencia[sequencia] = criado
                if criado is None:
                    problems.append("create_gvl devolveu None em %r" % (alvo,))
                    return finish(STATUS_MUTATION_FAILED)
                result["created_objects"].append(
                    {"kind": "gvl", "name": alvo, "sequence": sequencia})

            elif operacao == OP_CREATE_PROGRAM:
                criado = create_program_guarded(container, alvo,
                                                guids.get(sequencia), safety)
                objetos_por_sequencia[sequencia] = criado
                if criado is None:
                    problems.append("create_program devolveu None em %r"
                                    % (alvo,))
                    return finish(STATUS_MUTATION_FAILED)
                result["created_objects"].append(
                    {"kind": "program", "name": alvo, "sequence": sequencia})

            elif operacao == OP_CREATE_FUNCTION_BLOCK:
                criado = create_function_block_guarded(
                    container, alvo, guids.get(sequencia), safety)
                objetos_por_sequencia[sequencia] = criado
                if criado is None:
                    problems.append("create_function_block devolveu None em %r"
                                    % (alvo,))
                    return finish(STATUS_MUTATION_FAILED)
                result["created_objects"].append(
                    {"kind": "function_block", "name": alvo,
                     "sequence": sequencia})

            elif operacao == OP_CREATE_FUNCTION:
                tipo_retorno = passo.get("return_type")
                criado = create_function_guarded(
                    container, alvo, tipo_retorno, guids.get(sequencia), safety)
                objetos_por_sequencia[sequencia] = criado
                if criado is None:
                    problems.append("create_function devolveu None em %r"
                                    % (alvo,))
                    return finish(STATUS_MUTATION_FAILED)
                result["created_objects"].append(
                    {"kind": "function", "name": alvo, "sequence": sequencia,
                     "return_type": tipo_retorno})

            elif operacao == OP_CREATE_DUT:
                criado = create_dut_guarded(container, alvo,
                                            tipos_dut.get(sequencia), safety)
                objetos_por_sequencia[sequencia] = criado
                if criado is None:
                    problems.append("create_dut devolveu None em %r" % (alvo,))
                    return finish(STATUS_MUTATION_FAILED)
                result["created_objects"].append(
                    {"kind": "dut", "name": alvo, "sequence": sequencia,
                     "dut_kind": passo.get("dut_kind")})

            elif operacao == OP_CREATE_TASK:
                criado = create_task_guarded(configuracao_de_tasks, alvo,
                                             safety)
                if criado is None:
                    problems.append("create_task devolveu None em %r" % (alvo,))
                    return finish(STATUS_MUTATION_FAILED)
                # Indexada por NOME, e nao por sequencia como os objetos IEC: o
                # passo que vincula o programa se refere a task pelo nome que a
                # spec escreveu, e nao pela sequencia que a criou.
                tasks_por_nome[alvo] = criado
                result["created_objects"].append(
                    {"kind": "task", "name": alvo, "sequence": sequencia})

            elif operacao == OP_REPLACE:
                # O OBJETO CRIADO NESTA SESSAO E O ALVO, quando o plano liga os
                # dois por `created_by_sequence`. Procurar de novo na arvore
                # seria buscar o que ja esta na mao -- e a busca depende de
                # `type_guid`, que para DUT nunca foi medido. A referencia
                # direta nao tem ambiguidade nenhuma.
                criado_em = passo.get("created_by_sequence")
                no = objetos_por_sequencia.get(criado_em)
                if no is None:
                    no, erro = find_by_name_and_type(projeto, alvo,
                                                     POU_TYPE_GUID)
                if no is None:
                    no, erro_gvl = find_by_name_and_type(
                        projeto, alvo, GVL_TYPE_GUID)
                    if no is None:
                        problems.append("alvo %r de replace nao resolvido: %s "
                                        "| %s" % (alvo, erro, erro_gvl))
                        return finish(STATUS_TARGET_NOT_FOUND)
                documento, erro = document_for_target_kind(
                    no, passo.get("target_kind"))
                if documento is None:
                    problems.append("documento de %r nao resolvido: %s"
                                    % (alvo, erro))
                    return finish(STATUS_TARGET_NOT_FOUND)
                replace_guarded(documento, textos.get(sequencia), safety)

            elif operacao == OP_CREATE_PROGRAM_CALL:
                hospedeira, erro = find_by_name_and_type(
                    projeto, PROGRAM_CALL_HOST, POU_TYPE_GUID)
                if hospedeira is None:
                    problems.append(
                        "POU de perfil %r nao resolvida: %s. Este executor NAO "
                        "cai para outra POU nem para a lista da task."
                        % (PROGRAM_CALL_HOST, erro))
                    return finish(STATUS_TARGET_NOT_FOUND)
                documento, erro = read_document(
                    hospedeira, "has_textual_implementation",
                    "textual_implementation")
                if documento is None:
                    problems.append("implementacao de %r ilegivel: %s"
                                    % (PROGRAM_CALL_HOST, erro))
                    return finish(STATUS_TARGET_NOT_FOUND)
                try:
                    atual = as_text(documento.text)
                except Exception as exc:                           # noqa: BLE001
                    problems.append("leitura de %r falhou: %r"
                                    % (PROGRAM_CALL_HOST, exc))
                    return finish(STATUS_TARGET_NOT_FOUND)
                programa = passo.get("program_name")
                if already_calls(atual, programa):
                    result["step_log"].append({
                        "sequence": sequencia, "operation": operacao,
                        "outcome": "already_present", "host": PROGRAM_CALL_HOST})
                    journal.record({"event": "mutation_skipped",
                                    "operation": operacao,
                                    "sequence": sequencia,
                                    "reason": "chamada ja presente"})
                    continue
                final = compose_call(atual, programa)
                # LIMITE ESTRUTURAL, registrado em vez de escondido: este e o
                # UNICO texto que o plano nao lacra por hash. O planner e
                # offline e nao pode saber o que ha dentro de `UserPrg`, entao
                # nao ha `planned_after_sha256` a conferir. O que o plano fixa
                # e o NOME do programa chamado; o resto do texto e o que ja
                # estava la. Os dois hashes ficam no log para que a diferenca
                # seja auditavel depois.
                result["step_log"].append({
                    "sequence": sequencia, "operation": operacao,
                    "outcome": "composed_at_runtime",
                    "host": PROGRAM_CALL_HOST,
                    "host_sha256_before": sha256_of_text(atual),
                    "host_sha256_after_planned": sha256_of_text(final),
                    "not_hash_sealed_by_plan": True})
                replace_call_host_guarded(documento, final, safety)

            elif operacao == OP_BIND_PROGRAM_TO_TASK:
                nome_da_task = passo.get("task_name")
                programa = passo.get("program_name")
                task = tasks_por_nome.get(nome_da_task)
                if task is None:
                    # Inalcancavel pela precondicao acima, e o ramo fica: a
                    # precondicao le o PLANO, e isto le o que a execucao de
                    # fato criou. Se `create_task` tivesse devolvido objeto e
                    # ele nao chegasse aqui, o `add` iria para lugar nenhum.
                    problems.append(
                        "a task %r nao esta entre as criadas nesta sessao: %r"
                        % (nome_da_task, sorted(tasks_por_nome)))
                    return finish(STATUS_TARGET_NOT_FOUND)
                try:
                    colecao = task.pous
                except Exception as exc:                           # noqa: BLE001
                    problems.append("lista de POUs de %r ilegivel: %r"
                                    % (nome_da_task, exc))
                    return finish(STATUS_TARGET_NOT_FOUND)
                # ANTES e DEPOIS, medidos. A task nasce vazia, e por isso a
                # lista e uma grandeza verificavel: `add` que nao acrescentasse
                # nada passaria despercebido sem esta conta.
                antes, erro = read_pou_names(colecao)
                if antes is None:
                    problems.append("lista de POUs de %r ilegivel antes do "
                                    "vinculo: %s" % (nome_da_task, erro))
                    return finish(STATUS_TARGET_NOT_FOUND)
                add_program_call_guarded(colecao, programa, safety)
                depois, erro = read_pou_names(colecao)
                if depois is None:
                    problems.append("lista de POUs de %r ilegivel depois do "
                                    "vinculo: %s" % (nome_da_task, erro))
                    return finish(STATUS_MUTATION_FAILED)
                result["step_log"].append({
                    "sequence": sequencia, "operation": operacao,
                    "outcome": "executed", "task": nome_da_task,
                    "program": programa,
                    "pous_before": antes, "pous_after": depois})
                if depois != antes + [programa]:
                    problems.append(
                        "a lista de POUs de %r era %r e ficou %r -- esperado "
                        "exatamente %r no fim"
                        % (nome_da_task, antes, depois, programa))
                    return finish(STATUS_MUTATION_FAILED)

            elif operacao == OP_CONFIGURE_TASK:
                nome_da_task = passo.get("task_name")
                task = tasks_por_nome.get(nome_da_task)
                if task is None:
                    problems.append(
                        "a task %r nao esta entre as criadas nesta sessao: %r"
                        % (nome_da_task, sorted(tasks_por_nome)))
                    return finish(STATUS_TARGET_NOT_FOUND)
                escritas = []
                for escrita in (passo.get("task_properties") or []):
                    propriedade = escrita.get("property")
                    valor = escrita.get("value")
                    antes, _erro = read_task_property(task, propriedade)
                    # DESPACHO LITERAL, propriedade por propriedade. O `else`
                    # reprova com nome proprio: uma propriedade nova no planner
                    # nao escorrega para o passo seguinte.
                    if propriedade == "kind_of_task":
                        membro, erro = resolve_kind_of_task(script_globals,
                                                            valor)
                        if membro is None:
                            problems.append("passo %r: %s" % (sequencia, erro))
                            return finish(STATUS_PRECONDITION_FAILED)
                        set_kind_of_task_guarded(task, membro, safety)
                    elif propriedade == "interval":
                        set_interval_guarded(task, valor, safety)
                    elif propriedade == "interval_unit":
                        set_interval_unit_guarded(task, valor, safety)
                    elif propriedade == "priority":
                        set_priority_guarded(task, valor, safety)
                    else:
                        problems.append(
                            "propriedade %r sem ramo de escrita neste executor "
                            "(escritas: %s)"
                            % (propriedade,
                               ", ".join(CONFIGURABLE_TASK_PROPERTIES)))
                        return finish(STATUS_UNKNOWN_OPERATION)
                    # RELEITURA, e nao confianca. Atribuicao que nao pega e o
                    # modo de falha proprio desta classe: um metodo que falha
                    # ao menos levanta, e um campo simplesmente continua com o
                    # valor antigo.
                    depois, erro = read_task_property(task, propriedade)
                    if depois is None:
                        problems.append(
                            "%r de %r ilegivel apos a escrita: %s"
                            % (propriedade, nome_da_task, erro))
                        return finish(STATUS_MUTATION_FAILED)
                    escritas.append({"property": propriedade,
                                     "planned": valor,
                                     "before": antes, "after": depois})
                    if depois != valor:
                        problems.append(
                            "%r de %r foi escrito como %r e releu %r -- a "
                            "atribuicao nao pegou"
                            % (propriedade, nome_da_task, valor, depois))
                        return finish(STATUS_MUTATION_FAILED)
                result["step_log"].append({
                    "sequence": sequencia, "operation": operacao,
                    "outcome": "executed", "task": nome_da_task,
                    "property_writes": escritas})

            elif operacao == OP_SAVE_AS:
                save_as_guarded(projeto, caminho_saida, safety)

            else:
                # Inalcancavel: o vocabulario ja foi conferido acima. O ramo
                # existe para que uma operacao nova sem `elif` proprio reprove,
                # em vez de escorregar para o passo seguinte.
                problems.append("operacao sem ramo de execucao: %r" % (operacao,))
                return finish(STATUS_UNKNOWN_OPERATION)

        except safety.SafetyError as exc:
            problems.append("autorizacao recusada em %r (passo %r): %s"
                            % (operacao, sequencia, exc))
            journal.record({"event": "mutation_denied", "operation": operacao,
                            "sequence": sequencia, "error": repr(exc)})
            return finish(STATUS_PRECONDITION_FAILED)
        except Exception as exc:                                   # noqa: BLE001
            problems.append("%r levantou no passo %r: %r"
                            % (operacao, sequencia, exc))
            journal.record({"event": "mutation_failed", "operation": operacao,
                            "sequence": sequencia, "error": repr(exc)})
            if operacao == OP_SAVE_AS:
                return finish(STATUS_SAVE_FAILED)
            return finish(STATUS_MUTATION_FAILED)

        result["steps_executed"] += 1
        # As duas formas de vincular ja escreveram o proprio registro, com o
        # que so elas sabem: a idiomatica, os hashes de antes e depois da POU
        # hospedeira; a lista de POUs, a lista antes e depois.
        if operacao not in (OP_CREATE_PROGRAM_CALL, OP_BIND_PROGRAM_TO_TASK,
                            OP_CONFIGURE_TASK):
            result["step_log"].append({"sequence": sequencia,
                                       "operation": operacao,
                                       "outcome": "executed", "target": alvo})
        journal.record({"event": "mutation_done", "operation": operacao,
                        "sequence": sequencia})

    hash_saida, erro_saida = sha256_of_file(caminho_saida)
    result["output_sha256"] = hash_saida
    if erro_saida:
        problems.append("saida ilegivel apos a execucao: %s" % (erro_saida,))
        return finish(STATUS_SAVE_FAILED)

    return finish(STATUS_EXECUTED)


# GUID de tipo da GVL, medido na arvore do TemplateExemplo v1 (probe 37).
GVL_TYPE_GUID = "ffbfa93a-b94d-45fc-a329-229860183b1d"


def build_completion(result):
    """Escrito por ULTIMO: e o sinal de conclusao."""
    return {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "is_success": result.get("status") in SUCCESS_STATUSES,
        "phase": result.get("phase_observed"),
        "plan_sha256": result.get("plan_sha256"),
        "spec_sha256": result.get("spec_sha256"),
        "opened_project": result.get("opened_project"),
        "output_project_path": result.get("output_project_path"),
        "output_sha256": result.get("output_sha256"),
        "steps_total": result.get("steps_total"),
        "steps_executed": result.get("steps_executed"),
        "steps_delegated": result.get("steps_delegated"),
        "created_objects": result.get("created_objects"),
        "operations_requested": result.get("operations_requested"),
        "operations_authorized": result.get("operations_authorized"),
        "operations_required": result.get("operations_required"),
        "proving_operations": result.get("proving_operations"),
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

    grava("execution-manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "script": "probes/" + SCRIPT_NAME,
        "plan_path": result.get("plan_path"),
        "plan_sha256": result.get("plan_sha256"),
        "spec_path": result.get("spec_path"),
        "spec_sha256": result.get("spec_sha256"),
        "phase": result.get("phase_observed"),
        "journal": result.get("journal"),
    })
    grava("execution-steps.json", {"steps": result.get("step_log")})
    grava("execution-completion.json", build_completion(result))
    return escritos


def main(script_globals=None):
    if script_globals is None:
        script_globals = globals()
    print("=" * 68)
    print("[INFO] probes/%s -- executor de plano de autoria" % SCRIPT_NAME)
    print("[INFO] executa: %s" % (", ".join(EXECUTED_OPERATIONS),))
    print("[INFO] delega : %s" % (", ".join(DELEGATED_OPERATIONS),))
    print("=" * 68)

    if not _FILE_AVAILABLE or not REPO_ROOT:
        print("[FATAL] __file__ indisponivel")
        return EXIT_BY_STATUS[STATUS_FATAL]

    from common import file_io, probe_cli, project_access, safety

    try:
        result = run_executor(script_globals, list(sys.argv or []), safety,
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
    print("[INFO] passos: %s executados, %s delegados, de %s"
          % (result.get("steps_executed"), result.get("steps_delegated"),
             result.get("steps_total")))
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
